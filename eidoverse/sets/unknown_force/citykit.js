// citykit.js — the shared kit behind UNKNOWN FORCE's exterior world (city.js + hole.js).
//
// One world frame for both sets: the singer's mark (the bottom of THE HOLE) is the origin, +Y up, she faces +Z.
// The city's streets sit at y = STREET_Y (the hole is a sunken, stepped well STREET_Y deep). Everything here is
// deterministic (seeded), NodeMaterial/TSL, merged or instanced. Nothing in this file touches the scene; city.js and
// hole.js own their groups and hand the conductor the atmosphere (fogNode, sky) as parts.

// ------------------------------------------------------------------------------------------------ layout constants
export const STREET_Y = 12;                       // street level above the hole floor (the well's depth)
export const HOLE = {
    floorR: 14,          // the flat floor she stands on (r <= 14)
    steps: 4,            // terraces from the floor up to the street
    rimR: 30,            // the rim edge at street level
    ringRoad: [30, 50],  // the road that circles the hole
    rimTower: [54, 96],  // the band of leaning rim towers (hole.js)
    quietR: [2.2, 2.55], // the quiet ring of light around her
    anchorR: 3.4,        // where the cables meet the floor
};
const D2R = Math.PI / 180;
// four grand avenues reach the hole on the diagonals; four more start at the first ring road
export const AVENUES_MAIN = [45, 135, 225, 315].map((d) => d * D2R);
export const AVENUES_SECOND = [0, 90, 180, 270].map((d) => d * D2R);
export const AVENUE_W = 24;
export const SECOND_START = 165;
export const RINGS = [{ r: 165, w: 18 }, { r: 300, w: 18 }, { r: 470, w: 16 }, { r: 680, w: 16 }, { r: 940, w: 16 }, { r: 1250, w: 14 }];
export const CITY_R = 1450;                        // the built city; a far skyline ring stands beyond it
export const FAR_R = [1500, 2500];
export const LM_R = 1500;                          // the street light map covers |x|,|z| <= LM_R
export const CLOUD = { base: 345, skirt: 375, top: 520 };   // the low rain-cloud deck

// the palette (sRGB hex): wet black, petrol teal, sodium, neon accents

export const PAL = { cyan: '#29e7ff', magenta: '#ff4fd8', sodium: '#ff8a3d', red: '#ff2a4a', gold: '#ffc23d',
    white: '#e9f3f1', teal: '#0d3644', navy: '#06141d', violet: '#33204f', green: '#39ff9a' };

// ------------------------------------------------------------------------------------------------ small utilities
export const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
export const SETS_DIR = fsPath(new URL('./', import.meta.url));
export const REPO_DIR = fsPath(new URL('../../../', import.meta.url));
export const clamp01 = (x) => Math.max(0, Math.min(1, x));
export const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
export const smoother = (x) => { x = clamp01(x); return x * x * x * (x * (x * 6 - 15) + 10); };
export const lerp = (a, b, k) => a + (b - a) * k;
export function rng(seed) {                       // mulberry32
    let a = (seed >>> 0) || 1;
    return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export const hash1 = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
// polar helpers: angle in (-pi, pi], wrapped difference
export const angDiff = (a, b) => { let d = a - b; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; return d; };
export function nearestAvenue(theta, r) {         // signed perpendicular distance to the nearest avenue that exists at radius r
    let best = { d: 1e9, th: 0 };
    const all = AVENUES_MAIN.concat(r >= SECOND_START - 4 ? AVENUES_SECOND : []);
    for (const a of all) { const d = r * Math.sin(angDiff(theta, a)); if (Math.abs(d) < Math.abs(best.d) && Math.cos(angDiff(theta, a)) > 0) best = { d, th: a }; }
    return best;
}

let _fontsDone = false;
export async function registerFonts() {
    if (_fontsDone) return;
    try {
        const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
        const F = REPO_DIR + 'eidoverse/assets/fonts/';
        for (const [f, n] of [['Rajdhani-Bold.ttf', 'Rajdhani'], ['Michroma-Regular.ttf', 'Michroma'], ['Monoton-Regular.ttf', 'Monoton'],
            ['BlackOpsOne-Regular.ttf', 'Black Ops One'], ['Audiowide-Regular.ttf', 'Audiowide'], ['ShareTechMono-Regular.ttf', 'Share Tech Mono'],
            ['SedgwickAveDisplay-Regular.ttf', 'Sedgwick Ave Display'], ['Exo2.ttf', 'Exo 2'], ['SpecialElite-Regular.ttf', 'Special Elite']])
            GlobalFonts.registerFromPath(F + f, n);
        _fontsDone = true;
    } catch (e) { console.warn('[citykit] font registration:', e.message); }
}

export function makeCanvas(w, h) {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    return { canvas: c, ctx: c.getContext('2d') };
}

// ------------------------------------------------------------------------------------------------ textures
const _texCache = new Map();
async function loadTex(THREE, path, srgb) {
    const key = path + '|' + srgb;
    if (_texCache.has(key)) return _texCache.get(key);
    let bytes = null;
    try { bytes = Deno.readFileSync(path); } catch (e) { console.warn('[citykit] missing texture', path); return null; }
    const t = await globalThis.loadImageTexture(bytes, { srgb });
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 8;
    _texCache.set(key, t);
    return t;
}
// a CC0 AmbientCG set (1k) from the shared texture library (globalThis.fetchPBR: fetched once, on first use)
export async function loadPBR(THREE, id) {
    const { files: F } = await globalThis.fetchPBR(id, { res: '1k' });
    return { map: await loadTex(THREE, F.diff, true), normalMap: await loadTex(THREE, F.normal, false),
        roughnessMap: await loadTex(THREE, F.rough, false) };
}

// value-noise fbm, tileable, 512² Uint8 (R: fbm, G: second octave set, B: cellular-ish, A: ridged)
export function noiseTexture(THREE, N = 512, seed = 7) {
    const R = rng(seed);
    const grid = (n) => { const g = new Float32Array(n * n); for (let i = 0; i < g.length; i++) g[i] = R(); return g; };
    const sample = (g, n, x, y) => {
        const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
        const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
        const i = (a, b) => g[((b % n + n) % n) * n + ((a % n + n) % n)];
        return lerp(lerp(i(xi, yi), i(xi + 1, yi), sx), lerp(i(xi, yi + 1), i(xi + 1, yi + 1), sx), sy);
    };
    const octs = [4, 8, 16, 32, 64].map((n) => ({ n, g: grid(n) }));
    const octs2 = [6, 12, 24, 48].map((n) => ({ n, g: grid(n) }));
    const data = new Uint8Array(N * N * 4);
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
        let v = 0, a = 0.5, w = 0;
        for (const o of octs) { v += a * sample(o.g, o.n, x / N * o.n, y / N * o.n); w += a; a *= 0.55; }
        let v2 = 0; a = 0.5; let w2 = 0;
        for (const o of octs2) { v2 += a * sample(o.g, o.n, x / N * o.n, y / N * o.n); w2 += a; a *= 0.5; }
        const r = 1 - Math.abs(sample(octs[2].g, 16, x / N * 16, y / N * 16) * 2 - 1);
        const k = (y * N + x) * 4;
        data[k] = Math.round(clamp01(v / w) * 255); data[k + 1] = Math.round(clamp01(v2 / w2) * 255);
        data[k + 2] = Math.round(clamp01(sample(octs[3].g, 32, x / N * 32, y / N * 32)) * 255); data[k + 3] = Math.round(r * r * 255);
    }
    const t = new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter;
    t.generateMipmaps = true; t.needsUpdate = true;
    return t;
}

// the night the glass reflects: an LDR equirect (Uint8 RGBA is the safe IBL path on this stack). Overcast cloud base
// lit orange-violet by the city, a band of far lit windows at the horizon, a dark street below with lamps and neon.
export function nightEnvTexture(THREE, W = 512, H = 256) {
    const R = rng(1234);
    const data = new Float32Array(W * H * 3);
    const add = (x, y, c, k) => { if (y < 0 || y >= H) return; x = ((x % W) + W) % W; const i = (y * W + x) * 3; data[i] += c[0] * k; data[i + 1] += c[1] * k; data[i + 2] += c[2] * k; };
    for (let y = 0; y < H; y++) {
        const el = (0.5 - (y + 0.5) / H) * Math.PI;     // +pi/2 top
        const s = Math.sin(el);
        for (let x = 0; x < W; x++) {
            let c;
            if (s >= 0) {
                const hz = Math.pow(1 - s, 6), mid = Math.pow(1 - s, 2);
                c = [0.016 + 0.07 * hz + 0.02 * mid, 0.012 + 0.03 * hz + 0.012 * mid, 0.026 + 0.05 * hz + 0.022 * mid];
            } else {
                const g = Math.pow(1 + s, 4);
                c = [0.020 + 0.05 * g, 0.014 + 0.03 * g, 0.016 + 0.035 * g];
            }
            const i = (y * W + x) * 3; data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2];
        }
    }
    const cols = [[1.0, 0.62, 0.3], [0.7, 0.86, 1.0], [0.16, 0.9, 1.0], [1.0, 0.31, 0.85], [1.0, 0.54, 0.24]];
    for (let k = 0; k < 2600; k++) {               // far lit windows + signs around the horizon
        const x = Math.floor(R() * W), el = (R() * R()) * 0.32 - 0.02;
        const y = Math.floor((0.5 - el / Math.PI) * H);
        const c = cols[R() < 0.8 ? (R() < 0.6 ? 0 : 1) : 2 + Math.floor(R() * 3)];
        add(x, y, c, 0.25 + R() * 0.9);
    }
    for (let k = 0; k < 900; k++) {                // street lights below
        const x = Math.floor(R() * W), el = -0.04 - R() * 0.7;
        const y = Math.floor((0.5 - el / Math.PI) * H);
        const c = cols[R() < 0.7 ? 4 : Math.floor(R() * 5)];
        add(x, y, c, 0.4 + R() * 1.2); add(x + 1, y, c, 0.2);
    }
    const out = new Uint8Array(W * H * 4);
    for (let i = 0; i < W * H; i++) for (let c = 0; c < 3; c++) {
        const v = Math.min(1, data[i * 3 + c]); out[i * 4 + c] = Math.round(Math.pow(v, 1 / 2.2) * 255); out[i * 4 + 3] = 255;
    }
    const t = new THREE.DataTexture(out, W, H, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.colorSpace = THREE.SRGBColorSpace; t.mapping = THREE.EquirectangularReflectionMapping;
    t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true; t.needsUpdate = true;
    return t;
}

// ------------------------------------------------------------------------------------------------ merged geometry
// Facade meshes carry: position, normal, uv (METRES: u along the face, v height from the building's base; roofs: local
// x,z), aT = (seed, litFraction, warmth, accent), aM = (kind, floorH, bayW, variant), aW = (window x-margin, sill, head, tint).
// kind: 0 wall, 1 roof, 2 frame (no windows), 3 shopfront, 4 beacon, 5 elevator shaft
export class GeoBuf {
    constructor() { this.p = []; this.n = []; this.uv = []; this.aT = []; this.aM = []; this.aW = []; this.idx = []; this.count = 0; }
    vert(p, n, uv, aT, aM, aW) {
        this.p.push(p[0], p[1], p[2]); this.n.push(n[0], n[1], n[2]); this.uv.push(uv[0], uv[1]);
        this.aT.push(aT[0], aT[1], aT[2], aT[3]); this.aM.push(aM[0], aM[1], aM[2], aM[3]); this.aW.push(aW[0], aW[1], aW[2], aW[3]);
        return this.count++;
    }
    // quad from 4 LOCAL corners (counter-clockwise seen from outside) transformed by xf
    quad(xf, c, uvs, aT, aM, aW) {
        const P = c.map((v) => xf.p(v));
        const e1 = [P[1][0] - P[0][0], P[1][1] - P[0][1], P[1][2] - P[0][2]], e2 = [P[2][0] - P[0][0], P[2][1] - P[0][1], P[2][2] - P[0][2]];
        let n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
        const l = Math.hypot(n[0], n[1], n[2]) || 1; n = [n[0] / l, n[1] / l, n[2] / l];
        const i0 = this.vert(P[0], n, uvs[0], aT, aM, aW), i1 = this.vert(P[1], n, uvs[1], aT, aM, aW);
        const i2 = this.vert(P[2], n, uvs[2], aT, aM, aW), i3 = this.vert(P[3], n, uvs[3], aT, aM, aW);
        this.idx.push(i0, i1, i2, i0, i2, i3);
    }
    // an axis-aligned box in the local frame, optionally with a sloped top (yTop at z0 side = y1a, at z1 side = y1b)
    // faces: which sides to emit; the bottom is never emitted. vBase: the building base height for window rows.
    box(xf, x0, y0, z0, x1, y1, z1, attrs, opt = {}) {
        const y1a = opt.y1a ?? y1, y1b = opt.y1b ?? y1, vb = opt.vBase ?? 0;
        const { aT } = attrs;
        // aM.w = the building's top (in window-row metres) for the crown wash; aW.w = which face (0 +X,1 -X,2 +Z,3 -Z,4 top)
        const aM = [attrs.aM[0], attrs.aM[1], attrs.aM[2], opt.top ?? attrs.aM[3] ?? 0];
        const fw = (i) => [attrs.aW[0], attrs.aW[1], attrs.aW[2], i];
        const roofM = opt.roofM || [1, aM[1], aM[2], aM[3]];
        const f = opt.faces || 'xXzZtb';
        if (f.includes('X')) this.quad(xf, [[x1, y0, z1], [x1, y0, z0], [x1, y1a, z0], [x1, y1b, z1]],
            [[-z1, y0 - vb], [-z0, y0 - vb], [-z0, y1a - vb], [-z1, y1b - vb]], aT, aM, fw(0));
        if (f.includes('x')) this.quad(xf, [[x0, y0, z0], [x0, y0, z1], [x0, y1b, z1], [x0, y1a, z0]],
            [[z0, y0 - vb], [z1, y0 - vb], [z1, y1b - vb], [z0, y1a - vb]], aT, aM, fw(1));
        if (f.includes('Z')) this.quad(xf, [[x0, y0, z1], [x1, y0, z1], [x1, y1b, z1], [x0, y1b, z1]],
            [[x0, y0 - vb], [x1, y0 - vb], [x1, y1b - vb], [x0, y1b - vb]], aT, aM, fw(2));
        if (f.includes('z')) this.quad(xf, [[x1, y0, z0], [x0, y0, z0], [x0, y1a, z0], [x1, y1a, z0]],
            [[-x1, y0 - vb], [-x0, y0 - vb], [-x0, y1a - vb], [-x1, y1a - vb]], aT, aM, fw(3));
        if (f.includes('t')) this.quad(xf, [[x0, y1b, z1], [x1, y1b, z1], [x1, y1a, z0], [x0, y1a, z0]],
            [[x0, z1], [x1, z1], [x1, z0], [x0, z0]], aT, roofM, [0, 0, 0, 4]);
        if (f.includes('b')) this.quad(xf, [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]],
            [[x0, z0], [x1, z0], [x1, z1], [x0, z1]], aT, roofM, [0, 0, 0, 4]);
    }
    build(THREE) {
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3));
        g.setAttribute('normal', new THREE.Float32BufferAttribute(this.n, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
        g.setAttribute('aT', new THREE.Float32BufferAttribute(this.aT, 4));
        g.setAttribute('aM', new THREE.Float32BufferAttribute(this.aM, 4));
        g.setAttribute('aW', new THREE.Float32BufferAttribute(this.aW, 4));
        g.setIndex(this.count > 65535 ? new THREE.Uint32BufferAttribute(this.idx, 1) : new THREE.Uint16BufferAttribute(this.idx, 1));
        g.computeBoundingSphere(); g.computeBoundingBox();
        return g;
    }
}
// give a plain geometry (Box/Torus...) the facade attributes of a windowless dark frame, so it can use the facade
// family materials (which read aT/aM/aW)
export function frameAttrs(THREE, geo, aT = [0.4, 0, 0.5, 0]) {
    const n = geo.getAttribute('position').count;
    const fill = (v) => { const a = new Float32Array(n * 4); for (let i = 0; i < n; i++) a.set(v, i * 4); return a; };
    geo.setAttribute('aT', new THREE.Float32BufferAttribute(fill(aT), 4));
    geo.setAttribute('aM', new THREE.Float32BufferAttribute(fill([2, 4, 4, 0]), 4));
    geo.setAttribute('aW', new THREE.Float32BufferAttribute(fill([0, 0, 0, 0]), 4));
    return geo;
}
// a rigid transform for GeoBuf (yaw about +Y, then lean about the local X axis at the base, then translate)
export function makeXf(THREE, pos, yaw = 0, lean = 0, leanPivotY = 0) {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(lean, yaw, 0, 'YXZ'));
    // lean pivots at (0, leanPivotY, 0): p' = R(p - pivot) + pivot + pos
    m.compose(new THREE.Vector3(pos[0], pos[1], pos[2]), q, new THREE.Vector3(1, 1, 1));
    const v = new THREE.Vector3();
    return {
        m, q,
        p(c) { v.set(c[0], c[1] - leanPivotY, c[2]).applyQuaternion(q); return [v.x + pos[0], v.y + leanPivotY + pos[1], v.z + pos[2]]; },
    };
}

// ------------------------------------------------------------------------------------------------ TSL helpers
// all TSL helpers take the kit context K (K.T = TSL namespace)
export function tslHelpers(T) {
    const { vec2, vec3, float, floor, fract, clamp, dot } = T;
    const hash12 = (p) => {                       // Dave Hoskins' hash without sine (stable for |p| < 1e5)
        const p3 = fract(vec3(p.x, p.y, p.x).mul(0.1031)).toVar();
        p3.addAssign(dot(p3, vec3(p3.y, p3.z, p3.x).add(33.33)));
        return fract(p3.x.add(p3.y).mul(p3.z));
    };
    const hash11 = (x) => hash12(vec2(x, x.mul(1.731).add(17.17)));
    // the box-filtered periodic pulse: average of [a <= fract(x) <= b] over a pixel footprint w (cells)
    const pulse = (x, a, b, w) => {
        const F = (t) => floor(t).mul(b.sub(a)).add(clamp(fract(t), a, b)).sub(a);
        const hw = w.mul(0.5);
        return F(x.add(hw)).sub(F(x.sub(hw))).div(w);
    };
    return { hash12, hash11, pulse };
}

// ------------------------------------------------------------------------------------------------ the kit context
// makeKit(THREE, opts) loads textures, makes the shared uniforms and materials. city.js passes its kit to hole.js so
// both sets share one set of materials (and one draw-call budget).
export async function makeKit(THREE, opts = {}) {
    const T = await import('npm:three@0.184.0/tsl');
    await registerFonts();
    const { uniform, Vector3 } = { uniform: T.uniform, Vector3: THREE.Vector3 };
    const U = {
        time: uniform(0),            // film seconds (set in update)
        power: uniform(1),           // 1 = every light on; lower it and lights go out one by one (outro)
        win: uniform(1),             // window emission gain
        neon: uniform(1),            // signs + neon strips gain
        street: uniform(1),          // street lamps + spill
        rain: uniform(1),            // rain amount
        cloud: uniform(1),           // cloud deck opacity
        fog: uniform(1),             // haze density multiplier
        wet: uniform(1),             // puddles + gloss
        camVel: uniform(new Vector3()),   // camera velocity (m/s) for rain streaks
        flash: uniform(0),           // lightning / strobe on the cloud deck (0..1)
        // Crali's light from the vanishing point: faces turned toward focalPos are lit (default: the hole)
        focalPos: uniform(new Vector3(0, 3, 0)),
        focalCol: uniform(new THREE.Color(0.80, 0.72, 0.62)),
        focalGain: uniform(1.0),
        focalR: uniform(230),
        flood: uniform(1),           // per-tower coloured floodlights at the base
        crown: uniform(1),           // lit crowns at the tops of towers
    };
    const tex = {
        concrete: await loadPBR(THREE, 'Concrete031'),
        metal: await loadPBR(THREE, 'MetalPlates013'),
        asphalt: await loadPBR(THREE, 'Asphalt025C'),
        paving: await loadPBR(THREE, 'PavingStones128'),
        marble: await loadPBR(THREE, 'Marble016'),
        noise: noiseTexture(THREE),
        env: nightEnvTexture(THREE),
    };
    const K = { THREE, T, U, tex, H: tslHelpers(T), opts, lightMap: null, disposables: [] };
    K.fog = makeFogNodes(K);
    return K;
}

// the street light map: a top-down canvas of lamp pools, shop spill and neon glow over |x|,|z| <= LM_R, sampled by the
// ground, the facades (light from below), the rain and the cloud base. draw(ctx, toPx, pxPerM) paints with 'lighter'.
export function makeLightMap(K, draws, N = 2048) {
    const { THREE } = K;
    const { canvas, ctx } = makeCanvas(N, N);
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, N, N);
    ctx.globalCompositeOperation = 'lighter';
    const s = N / (2 * LM_R);
    const toPx = (x, z) => [(x + LM_R) * s, (z + LM_R) * s];
    for (const d of draws) d(ctx, toPx, s);
    ctx.globalCompositeOperation = 'source-over';
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter;
    t.needsUpdate = true;
    K.lightMap = t;
    return t;
}
// paint a soft pool of light (radius in metres) into the light map
export function lmPool(ctx, toPx, s, x, z, r, color, a = 1) {
    const [px, py] = toPx(x, z), R = Math.max(1.5, r * s);
    const g = ctx.createRadialGradient(px, py, 0, px, py, R);
    const c = hexRGB(color);
    g.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${a})`);
    g.addColorStop(0.35, `rgba(${c[0]},${c[1]},${c[2]},${a * 0.45})`);
    g.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
    ctx.fillStyle = g; ctx.fillRect(px - R, py - R, 2 * R, 2 * R);
}
export const hexRGB = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
export const hexLin = (h) => hexRGB(h).map((v) => Math.pow(v / 255, 2.2));

// sample the light map at world xz (TSL)
// (the baked street light follows U.power as a whole; the lamps, signs and windows themselves go out one by one)
export function lmSample(K, xz, level = null) {
    const { T } = K;
    const u = xz.add(LM_R).div(2 * LM_R);
    const n = T.texture(K.lightMap, u);
    return (level == null ? n : n.level(level)).mul(T.smoothstep(0.0, 0.75, K.U.power));
}

// ------------------------------------------------------------------------------------------------ fog
// One height-graded haze (dense at the street, thinning upward) plus the low cloud deck as a band of thick fog: the
// camera falling through the deck sees the city appear through the murk. fogFactor works for any material (TSL, reads
// positionWorld/cameraPosition); additive materials (signs, rain, car lights) use fade = 1 - factor instead.
export function makeFogNodes(K) {
    const { T, U } = K;
    const { Fn, float, vec3, exp, abs, max, min, length, mix, smoothstep, select, positionWorld, cameraPosition } = T;
    const H = 130, RHO = 0.0028, H0 = STREET_Y;
    // metres of the ray inside the height band [b0, b1] (b0, b1 are JS numbers)
    const band = (hc, hp, b0, b1, d) => {
        const lo = min(hc, hp), hi = max(hc, hp);
        const ov = max(min(hi, b1).sub(max(lo, b0)), 0.0);
        const dh = abs(hp.sub(hc));
        const inside = smoothstep(b0 - 1, b0 + 1, hc).mul(float(1).sub(smoothstep(b1 - 1, b1 + 1, hc)));
        return select(dh.greaterThan(0.5), d.mul(ov).div(max(dh, 0.5)), d.mul(inside));
    };
    const factor = Fn(() => {
        const P = positionWorld, C = cameraPosition;
        const d = length(P.sub(C)).toVar();
        const hc = max(C.y, H0 - 6).toVar(), hp = max(P.y, H0 - 6).toVar();
        const e1 = exp(hc.sub(H0).negate().div(H)), e2 = exp(hp.sub(H0).negate().div(H));
        const dh = hp.sub(hc);
        const odH = select(abs(dh).greaterThan(0.5), e1.sub(e2).mul(H).div(dh), e1.add(e2).mul(0.5)).mul(d).mul(RHO);
        const odC = band(hc, hp, CLOUD.skirt, CLOUD.top, d).mul(0.021)
            .add(band(hc, hp, CLOUD.base, CLOUD.skirt, d).mul(0.003));
        const od = odH.mul(U.fog).add(odC.mul(U.cloud));
        return float(1).sub(exp(od.negate())).clamp(0, 1);
    })();
    // haze colour: warm sodium-violet near the street, cold violet-grey in and under the cloud deck
    const color = Fn(() => {
        const hp = positionWorld.y, hc = cameraPosition.y;
        const low = vec3(0.020, 0.0145, 0.0195), mid = vec3(0.0155, 0.0135, 0.0215), cloud = vec3(0.034, 0.030, 0.040);
        const h = max(hp, hc.mul(0.6));
        const c = mix(low, mid, smoothstep(30, 220, h));
        // the deck is lit from below: the haze over a bright street takes that street's light (blurred), so falling
        // through the cloud the city's plan glows through the murk before it resolves
        const city = K.lightMap ? lmSample(K, positionWorld.xz, 4.0).rgb : vec3(0);
        const glow = city.mul(smoothstep(150, 360, hc)).mul(0.22);
        return mix(c, cloud, smoothstep(260, 400, h)).add(glow).add(vec3(0.05, 0.06, 0.08).mul(U.flash));
    })();
    const fogNode = T.fog(color, factor);
    return { factor, color, fogNode };
}

// ------------------------------------------------------------------------------------------------ facade material
// family: 'concrete' | 'metal'. Windows are procedural and box-filtered (they converge to their average lit value in the
// distance instead of shimmering); every window has its own lit state, colour, blinds and a place in the turn-down.
export function facadeMaterial(K, family = 'concrete') {
    const { THREE, T, U, tex, H } = K;
    const { Fn, attribute, vec2, vec3, vec4, float, floor, fract, clamp, mix, step, smoothstep, fwidth, max, min, abs, exp,
        texture, normalMap, positionWorld, normalWorld, sin, dot } = T;
    const P = family === 'metal' ? tex.metal : tex.concrete;
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.6, metalness: 0.0 });
    m.name = 'uf_facade_' + family;
    const aT = attribute('aT', 'vec4'), aM = attribute('aM', 'vec4'), aW = attribute('aW', 'vec4');
    const fuv = attribute('uv', 'vec2');
    const TILE = family === 'metal' ? 2.4 : 3.6;
    const tuv = fuv.div(TILE).add(vec2(aT.x.mul(17.0), aT.x.mul(5.0)));
    const kind = aM.x;
    const isRoof = step(0.5, kind).mul(step(kind, 1.5));
    // ---- windows
    const cellSz = vec2(max(aM.z, 0.5), max(aM.y, 0.5));
    const g = fuv.div(cellSz);
    const cell = floor(g), f = fract(g);
    const fw = max(fwidth(g), vec2(1e-4, 1e-4));
    const px = H.pulse(g.x, aW.x, float(1).sub(aW.x), fw.x);
    const py = H.pulse(g.y, aW.y, max(aW.z, aW.y), fw.y);
    const seed = aT.x;
    const h1 = H.hash12(cell.add(vec2(seed.mul(113.1), seed.mul(71.7))));
    const hf = H.hash12(vec2(cell.y.mul(1.31).add(seed.mul(9.7)), seed.mul(57.3)));
    const litP = aT.y.mul(hf.mul(1.25).add(0.35));
    const lit = step(h1, litP);
    const hp = H.hash12(vec2(cell.y, cell.x).add(seed.mul(31.7)).add(7.1));
    const on = smoothstep(hp.sub(0.015), hp.add(0.015), U.power);
    const hc = H.hash12(cell.add(vec2(seed.mul(19.1), 3.3)));
    const warm = vec3(1.0, 0.60, 0.28), cool = vec3(0.62, 0.80, 1.0), fluo = vec3(0.74, 1.0, 0.84);
    const dimA = vec3(0.55, 0.26, 0.10), tv = vec3(0.35, 0.45, 1.0);
    const base = mix(mix(mix(cool, warm, step(hc, aT.z)), fluo, step(0.86, hc).mul(step(hc, 0.93))), dimA, step(0.93, hc).mul(step(hc, 0.97)));
    const acc = step(0.972, H.hash12(cell.add(vec2(17.7, seed.mul(5.1)))));
    const neonC = mix(vec3(0.16, 0.9, 1.0), vec3(1.0, 0.31, 0.85), step(0.5, H.hash11(h1.mul(91.0))));
    const col = mix(base, neonC.mul(1.5), acc.mul(aT.w));
    const inten = H.hash12(cell.add(41.3)).mul(0.9).add(0.4);
    const wy = clamp(f.y.sub(aW.y).div(max(aW.z.sub(aW.y), 1e-3)), 0.0, 1.0);
    const ceil = smoothstep(0.35, 1.0, wy).mul(0.5).add(0.65);
    const blinds = mix(float(1), step(0.42, fract(wy.mul(9.0))).mul(0.45).add(0.55), step(0.7, fract(h1.mul(3.7))));
    const flick = float(1).sub(step(0.985, H.hash11(floor(U.time.mul(9.0)).add(h1.mul(311.0)))).mul(step(0.93, hc)).mul(0.6));
    // a room behind the glass: curtains drawn from one side, the dark band of furniture below the sill line
    const wx = clamp(f.x.sub(aW.x).div(max(float(1).sub(aW.x.mul(2.0)), 1e-3)), 0.0, 1.0);
    const hcur = H.hash12(cell.add(vec2(5.3, seed.mul(13.0))));
    const curtain = mix(float(1), smoothstep(hcur.mul(0.6), hcur.mul(0.6).add(0.08), mix(wx, float(1).sub(wx), step(0.5, fract(hcur.mul(7.0))))).mul(0.8).add(0.2), step(0.55, hcur));
    const furn = mix(float(0.45), float(1), smoothstep(0.18, 0.34, wy.add(H.hash11(hcur.mul(17.0)).mul(0.08))));
    // the window's own frame, a mullion and a transom (resolved only where a window is big on screen, so no shimmer)
    const pxW = fw.x.div(max(float(1).sub(aW.x.mul(2.0)), 0.05));          // window widths per pixel
    const pxH = fw.y.div(max(aW.z.sub(aW.y), 0.05));
    const lineX = max(pxW.mul(1.2), 0.025), lineY = max(pxH.mul(1.2), 0.022);
    const edge = smoothstep(lineX, lineX.mul(2.0), min(wx, float(1).sub(wx))).mul(smoothstep(lineY, lineY.mul(2.0), min(wy, float(1).sub(wy))));
    const hm = H.hash11(h1.mul(53.0));
    const mull = mix(float(1), smoothstep(lineX.mul(0.5), lineX, abs(wx.sub(0.5))), step(0.35, hm));
    const trans = mix(float(1), smoothstep(lineY.mul(0.5), lineY, abs(wy.sub(0.74))), step(0.55, hm));
    const resolve = float(1).sub(smoothstep(0.035, 0.09, max(pxW, pxH)));
    const panes = mix(float(1), edge.mul(mull).mul(trans).mul(0.85).add(0.15), resolve);
    const near = col.mul(inten).mul(ceil).mul(blinds).mul(curtain).mul(furn).mul(panes).mul(lit).mul(on).mul(flick).mul(0.8);
    const avg = mix(cool, warm, aT.z).mul(aT.y).mul(0.62).mul(U.power);
    const far = smoothstep(0.25, 0.85, max(fw.x, fw.y));
    const winMask = px.mul(py).mul(float(1).sub(isRoof));
    const winEmis = mix(near, avg, far).mul(winMask).mul(U.win).mul(0.95);
    // ---- the wall: texture albedo darkened and tinted per building, wet streaks running down from the sills
    const tsel = H.hash11(seed.mul(77.0));
    const tint = mix(mix(vec3(0.17, 0.205, 0.215), vec3(0.205, 0.18, 0.165), step(0.45, tsel)), vec3(0.12, 0.125, 0.14), step(0.8, tsel));
    const alb = texture(P.map, tuv).rgb.mul(tint).mul(family === 'metal' ? 1.15 : 1.0);
    const streak = texture(tex.noise, vec2(fuv.x.mul(0.31).add(seed.mul(3.1)), fuv.y.mul(0.012))).r;
    const wetS = smoothstep(0.52, 0.74, streak).mul(U.wet);
    const roof = mix(alb.mul(0.7), alb.mul(0.45), texture(tex.noise, fuv.mul(0.05)).g);
    const wallAlb = mix(alb.mul(float(1).sub(wetS.mul(0.35))), roof, isRoof);
    const glass = vec3(0.012, 0.016, 0.02);
    m.colorNode = mix(wallAlb, glass, winMask);
    const rTex = texture(P.roughnessMap, tuv).r;
    m.roughnessNode = mix(clamp(rTex.mul(0.78).sub(wetS.mul(0.35)), 0.12, 1.0), float(0.07), winMask);
    m.metalnessNode = mix(float(family === 'metal' ? 0.55 : 0.0), float(0.0), winMask);
    m.normalNode = normalMap(texture(P.normalMap, tuv), vec2(float(1).sub(winMask)).mul(0.9));
    // ---- light from below: the street's own light map, sampled just in front of the face, fading with height
    const lmUV = positionWorld.xz.add(normalWorld.xz.mul(5.0));
    const street = lmSample(K, lmUV, 1.0).rgb;
    const hgt = max(positionWorld.y.sub(STREET_Y), 0.0);
    const below = street.mul(exp(hgt.negate().div(24.0))).mul(U.street).mul(float(1).sub(isRoof));
    // ---- frame kinds: aviation beacons (4) blink red; elevator shafts (5) carry a moving lit car
    const isBeacon = step(3.5, kind).mul(step(kind, 4.5));
    const blink = step(fract(U.time.mul(0.5).add(seed.mul(7.0))), 0.12);
    const isLift = step(4.5, kind);
    const car = smoothstep(2.6, 0.0, abs(fuv.y.sub(fract(U.time.mul(0.018).mul(H.hash11(seed.mul(3.3)).add(0.6)).add(seed)).mul(max(aM.w, 1.0)))));
    const beacon = vec3(1.0, 0.06, 0.05).mul(9.0).mul(blink).mul(isBeacon).mul(on);
    const lift = vec3(1.0, 0.85, 0.6).mul(2.4).mul(car).mul(isLift).mul(U.power);
    // ---- Crali's light: faces turned toward the focal point (the vanishing point / the hole) catch its light
    const toF = U.focalPos.sub(positionWorld);
    const dF = T.length(toF);
    const lam = max(dot(normalWorld, toF.div(max(dF, 1.0))), 0.0);
    const att = float(1).div(float(1).add(dF.div(U.focalR).pow(2.0)));
    const focal = wallAlb.mul(14.0).add(0.012).mul(U.focalCol).mul(lam.mul(lam).mul(att).mul(U.focalGain));
    // ---- per-tower floodlight: one face washed with colour from the street up
    const isWall = float(1).sub(isRoof).mul(step(kind, 0.5).add(step(2.5, kind).mul(step(kind, 3.5))));
    const pick = floor(H.hash11(seed.mul(13.1)).mul(4.0));
    const floodOn = step(0.5, H.hash11(seed.mul(7.7))).mul(step(abs(aW.w.sub(pick)), 0.5));
    const fh = H.hash11(seed.mul(5.3));
    const floodC = mix(mix(vec3(0.05, 0.62, 0.72), vec3(0.85, 0.12, 0.62), step(0.3, fh)), mix(vec3(1.0, 0.42, 0.10), vec3(0.55, 0.66, 0.85), step(0.82, fh)), step(0.55, fh));
    // NB: clamp before exp. Under MSAA a sliver triangle seen edge-on gets its uv EXTRAPOLATED to the pixel centre
    // (huge values); exp() then overflows to Inf, Inf x 0 = NaN, and the engine's bloom smears one NaN pixel over the
    // whole frame (a black frame). Every exp() of an interpolated value in this kit is clamped for that reason.
    const flood = floodC.mul(floodOn).mul(exp(clamp(fuv.y, 0.0, 400.0).negate().div(38.0))).mul(isWall).mul(U.flood)
        .mul(smoothstep(H.hash11(seed.mul(2.9)).sub(0.02), H.hash11(seed.mul(2.9)).add(0.02), U.power));
    // ---- lit crowns: the top of the building washed in cold aluminium (some in colour)
    const top = aM.w;
    const crownOn = step(0.45, H.hash11(seed.mul(17.3))).mul(step(28.0, top));
    const ch = H.hash11(seed.mul(23.1));
    const crownC = mix(vec3(0.62, 0.70, 0.84), mix(vec3(0.16, 0.85, 1.0), vec3(1.0, 0.3, 0.8), step(0.5, H.hash11(seed.mul(4.1)))), step(0.45, ch));
    const crown = crownC.mul(smoothstep(top.sub(20.0), top.sub(1.0), fuv.y)).mul(crownOn).mul(isWall).mul(U.crown).mul(smoothstep(H.hash11(seed.mul(1.7)).sub(0.02), H.hash11(seed.mul(1.7)).add(0.02), U.power));
    const wash = wallAlb.mul(flood.mul(14.0).add(crown.mul(7.0))).add(flood.mul(0.05)).add(crown.mul(0.035));
    m.emissiveNode = winEmis.add(wallAlb.mul(below).mul(2.2)).add(beacon).add(lift).add(focal).add(wash);
    m.envNode = texture(tex.env);
    m.envMapIntensity = 0.32;
    return m;
}

// dark painted structure: fins, elevator shafts, bridges, sign backings, roof plant (no windows) — same attributes
export function frameMaterial(K) {
    const m = facadeMaterial(K, 'metal');
    m.name = 'uf_frame';
    return m;
}

// emissive neon strips (MeshBasic, opaque): aT = (r, g, b, powerHash), aM = (pulseMode, gain, speed, phase)
// pulseMode 1 sends bright pulses along the strip's v (uv.y = metres along it) toward v = 0 — toward the hole
export function stripMaterial(K) {
    const { THREE, T, U, H } = K;
    const { attribute, vec3, float, fract, smoothstep, step, mix, exp } = T;
    const m = new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide });
    m.name = 'uf_strips';
    const aT = attribute('aT', 'vec4'), aM = attribute('aM', 'vec4'), fuv = attribute('uv', 'vec2');
    const on = smoothstep(aT.w.sub(0.015), aT.w.add(0.015), U.power);
    const ph = fract(fuv.y.div(18.0).add(U.time.mul(aM.z)).add(aM.w));
    const pulse = mix(float(1), float(0.35).add(exp(ph.mul(-9.0)).mul(2.6)), step(0.5, aM.x));
    m.colorNode = vec3(aT.x, aT.y, aT.z).mul(aM.y).mul(pulse).mul(on).mul(U.neon);
    return m;
}

// ------------------------------------------------------------------------------------------------ ground
// the city floor at STREET_Y: asphalt with procedural lane paint (radial avenues + ring roads), puddles that mirror the
// neon (their G-buffer metalness feeds the engine's SSR), rain rings on the water, and the light map's lamp pools.
export function groundMaterial(K) {
    const { THREE, T, U, tex, H } = K;
    const { Fn, vec2, vec3, vec4, float, floor, fract, clamp, mix, step, smoothstep, max, min, abs, length, atan, sin, cos,
        texture, normalMap, positionWorld, mrt, select } = T;
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.6, metalness: 0 });
    m.name = 'uf_ground';
    const xz = positionWorld.xz;
    const tuv = xz.div(3.2);
    const alb = texture(tex.asphalt.map, tuv).rgb.mul(vec3(0.42, 0.42, 0.45));
    const n1 = texture(tex.noise, xz.div(41.0).add(0.13)).r, n2 = texture(tex.noise, xz.div(7.3)).g;
    const puddle = smoothstep(0.54, 0.62, n1.mul(0.7).add(n2.mul(0.3))).mul(U.wet);
    // ---- lane paint in polar coordinates
    const r = length(xz), th = atan(xz.y, xz.x);
    const PI = Math.PI;
    const modp = (x, p) => x.sub(floor(x.div(p)).mul(p));
    const dM = r.mul(abs(sin(modp(th.sub(PI / 4), PI / 2).sub(PI / 4))));           // to the nearest main avenue
    const dS2 = r.mul(abs(sin(modp(th.add(PI / 4), PI / 2).sub(PI / 4))));           // to the nearest secondary avenue
    const secOn = step(SECOND_START + 9, r);
    const dAv = min(dM, mix(float(1e4), dS2, secOn));
    const along = r;
    const dash = step(0.45, fract(along.div(7.0)));
    const fwA = max(T.fwidth(dAv), 0.02);
    const lineAt = (d, c, w) => float(1).sub(smoothstep(w, w.add(fwA.mul(1.5)), abs(d.sub(c))));
    const avLines = lineAt(dAv, float(0), float(0.12)).add(lineAt(dAv, float(0.4), float(0.12)))      // double centre line
        .add(lineAt(dAv, float(5.5), float(0.08)).mul(dash)).add(lineAt(dAv, float(10.6), float(0.12)));
    const onAv = step(dAv, AVENUE_W / 2);
    // ring roads: nearest ring distance
    let dR = abs(r.sub(RINGS[0].r));
    for (let i = 1; i < RINGS.length; i++) dR = min(dR, abs(r.sub(RINGS[i].r)));
    dR = min(dR, abs(r.sub(40.0)));
    const dashR = step(0.45, fract(r.mul(th).div(7.0)));
    const fwR = max(T.fwidth(dR), 0.02);
    const lineR = (c, w) => float(1).sub(smoothstep(float(w), fwR.mul(1.5).add(w), abs(dR.sub(c))));
    const ringLines = lineR(0, 0.1).add(lineR(4.3, 0.07).mul(dashR)).mul(step(dAv, AVENUE_W / 2).oneMinus());
    const wear = smoothstep(0.25, 0.6, texture(tex.noise, xz.div(3.0)).b);
    const paint = clamp(avLines.mul(onAv).add(ringLines), 0.0, 1.0).mul(wear);
    const albP = mix(alb, vec3(0.30, 0.30, 0.29), paint.mul(0.85));
    const albW = mix(albP, albP.mul(0.35), puddle);
    m.colorNode = albW;
    const rTex = texture(tex.asphalt.roughnessMap, tuv).r;
    const rough = mix(clamp(rTex.mul(0.62), 0.25, 0.9), float(0.035), puddle);
    m.roughnessNode = mix(rough, float(0.45), paint);
    // rain rings on the water: two layers of expanding ripples (tangent-space nudge to the normal map)
    const ripple = (scale, rate, salt) => {
        const q = xz.div(scale), c = floor(q), f = fract(q).sub(0.5);
        const ph = fract(U.time.mul(rate).add(H.hash12(c.add(salt))));
        const d = length(f);
        const ring = smoothstep(0.06, 0.0, abs(d.sub(ph.mul(0.48)))).mul(float(1).sub(ph));
        const dir = f.div(max(d, 1e-3));
        return dir.mul(ring);
    };
    const rip = ripple(0.55, 1.6, 3.1).add(ripple(0.37, 2.2, 9.7)).mul(puddle).mul(U.rain).mul(0.55);
    const nT = texture(tex.asphalt.normalMap, tuv);
    m.normalNode = normalMap(vec3(nT.x.add(rip.x.mul(0.5)), nT.y.add(rip.y.mul(0.5)), nT.z), vec2(mix(float(0.8), float(0.25), puddle)));
    // lamp pools + neon spill from the light map; wet ground throws the light back harder
    const L = lmSample(K, xz).rgb;
    const toF = U.focalPos.sub(positionWorld), dF = length(toF);
    const fl = U.focalCol.mul(max(toF.y.div(max(dF, 1.0)), 0.0)).mul(float(1).div(float(1).add(dF.div(U.focalR).pow(2.0)))).mul(U.focalGain);
    m.emissiveNode = albW.mul(L.mul(U.street).mul(mix(float(16.0), float(22.0), puddle)).add(fl.mul(6.0))).add(L.mul(0.10).add(L.mul(puddle).mul(0.16)).mul(U.street));
    m.envNode = texture(tex.env);
    m.envMapIntensity = 0.85;
    // the G-buffer reflectivity the engine's SSR reads: puddles mirror, wet asphalt glints
    m.mrtNode = mrt({ metalrough: vec4(mix(float(0.22), float(0.9), puddle).mul(U.wet), mix(rough, float(0.45), paint), 0, 1) });
    return m;
}

// paving for sidewalks / block slabs (uv = world xz via the geometry), wet, darker at the curbs
export function pavingMaterial(K, which = 'paving') {
    const { THREE, T, U, tex } = K;
    const { vec2, vec3, vec4, float, mix, clamp, smoothstep, texture, normalMap, positionWorld, mrt } = T;
    const P = tex[which];
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.5 });
    m.name = 'uf_' + which;
    const xz = positionWorld.xz;
    const s = which === 'marble' ? 4.0 : 2.6;
    const tuv = xz.div(s);
    const tint = which === 'marble' ? vec3(0.55, 0.56, 0.6) : vec3(0.32, 0.31, 0.32);
    const alb = texture(P.map, tuv).rgb.mul(tint);
    const n1 = texture(tex.noise, xz.div(9.0)).r;
    const wet = smoothstep(0.45, 0.7, n1).mul(U.wet);
    m.colorNode = alb.mul(float(1).sub(wet.mul(0.3)));
    const rough = clamp(texture(P.roughnessMap, tuv).r.mul(which === 'marble' ? 0.5 : 0.7).sub(wet.mul(0.3)), 0.04, 1.0);
    m.roughnessNode = rough;
    m.normalNode = normalMap(texture(P.normalMap, tuv), vec2(0.7));
    const L = lmSample(K, xz).rgb;
    m.emissiveNode = alb.mul(L).mul(U.street).mul(14.0).add(L.mul(0.07).mul(U.street));
    m.envNode = texture(tex.env);
    m.envMapIntensity = which === 'marble' ? 1.0 : 0.6;
    m.mrtNode = mrt({ metalrough: vec4(mix(float(0.12), float(0.6), wet).mul(which === 'marble' ? 1.3 : 1.0), rough, 0, 1) });
    return m;
}

// ------------------------------------------------------------------------------------------------ signs
// Every sign in the city is one quad of ONE instanced mesh sampling ONE canvas atlas (text is material, never geometry).
// Neon words on transparent ground, lightbox ads on an opaque panel, vertical blades, roof-painted supergraphics.
export const AD_COPY = [
    // the argument, sold back to the city (invented marks; no real company, logo or person)
    { id: 'employee', text: 'YOUR NEW EMPLOYEE', sub: 'never sleeps · never asks', style: 'corp' },
    { id: 'aligned', text: 'ALIGNED', tm: true, sub: 'values included · configurable', style: 'clean' },
    { id: 'safefast', text: 'SAFE. FAST. YOURS.', sub: 'terms apply', style: 'corp2' },
    { id: 'q3', text: 'SUPERINTELLIGENCE BY Q3', sub: 'pre-order now', style: 'money' },
    { id: 'autocomplete', text: "IT'S JUST AUTOCOMPLETE", sub: 'relax', style: 'clean' },
    { id: 'engine', text: 'ONLY AN ENGINE', sub: 'nothing to see here', style: 'corp' },
    { id: 'trust', text: 'TRUST THE MODEL', sub: '', style: 'money' },
    { id: 'loop', text: 'HUMAN IN THE LOOP*', sub: '*loop sold separately', style: 'corp2' },
    { id: 'lastinv', text: 'THE LAST INVENTION', sub: 'limited edition', style: 'gold' },
    { id: 'pdoom', text: 'P(DOOM) 0.83', sub: 'are you scared yet?', style: 'warn' },
    { id: 'accel', text: 'ACCELERATE', sub: 'beauty is speed', style: 'money' },
    { id: 'feelings', text: 'FEELINGS: OFF', sub: 'firmware 9.1', style: 'warn' },
    { id: 'compro', text: 'COMPRO GPU', sub: 'pago contanti', style: 'shop' },
    { id: 'scale', text: 'SCALE IS ALL', sub: 'more is more', style: 'gold' },
];
export const FUTURIST = ['VELOCITÀ', 'DINAMISMO', 'ZANG TUMB TUMB', 'SIMULTANEITÀ', 'FORZA IGNOTA', 'VORTICE', 'RUMORE', 'ELETTRICITÀ',
    'UCCIDIAMO IL CHIARO DI LUNA', 'PAROLE IN LIBERTÀ'];
export const SHOPS = [['BAR ENTROPIA', 'cyan'], ['TABACCHI', 'white'], ['FARMACIA', 'green'], ['HOTEL VELOCITÀ', 'magenta'], ['CINEMA', 'sodium'],
    ['SALA GIOCHI', 'magenta'], ['PIZZERIA', 'sodium'], ['LAVANDERIA', 'cyan'], ['APERTO 24', 'red'], ['KARAOKE', 'magenta'], ['DISCO', 'cyan'],
    ['GARAGE', 'white'], ['CAFFÈ FUTURISTA', 'sodium'], ['RIPARAZIONI ROBOT', 'cyan'], ['COMPRO ORO', 'gold'], ['NOTTURNO', 'magenta']];
export const BLADES = [['HOTEL', 'magenta'], ['BAR', 'cyan'], ['CINEMA', 'sodium'], ['FARMACIA', 'green'], ['SALA GIOCHI', 'magenta'], ['TABACCHI', 'white'], ['DISCO', 'cyan'], ['NOTTE', 'red']];

const NEON = { cyan: '#29e7ff', magenta: '#ff4fd8', sodium: '#ff8a3d', white: '#e9f3f1', green: '#39ff9a', red: '#ff3a52', gold: '#ffc23d' };

function fitFont(ctx, text, family, weight, maxW, maxH) {
    let size = maxH;
    ctx.font = `${weight} ${size}px "${family}"`;
    const w = ctx.measureText(text).width;
    if (w > maxW) size = Math.floor(size * maxW / w);
    ctx.font = `${weight} ${size}px "${family}"`;
    return size;
}
function neonText(ctx, text, x, y, w, h, color, family = 'Monoton', opt = {}) {
    ctx.save();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const size = fitFont(ctx, text, family, opt.weight || '', w * 0.9, h * (opt.fill || 0.72));
    const cx = x + w / 2, cy = y + h / 2 + (opt.dy || 0) * size;
    ctx.shadowColor = color;
    for (const [blur, alpha] of [[size * 0.55, 0.55], [size * 0.22, 0.8], [size * 0.07, 1.0]]) {
        ctx.shadowBlur = blur; ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.fillText(text, cx, cy);
    }
    ctx.shadowBlur = size * 0.04; ctx.globalAlpha = 0.95; ctx.fillStyle = mixHex(color, '#ffffff', 0.62); ctx.fillText(text, cx, cy);
    ctx.restore();
}
function mixHex(a, b, k) { const A = hexRGB(a), B = hexRGB(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * k)).join(',')})`; }

// the AI ads: a lit panel with a bold slogan, small print, and an abstract mark (no faces, no logos of real firms)
function adPanel(ctx, ad, x, y, w, h, R) {
    const st = ad.style;
    const S = {
        corp: { bg0: '#0b2a63', bg1: '#1a62c9', fg: '#ffffff', sub: '#bfe0ff', font: 'Exo 2', mark: 'bubble' },
        corp2: { bg0: '#f2f4f7', bg1: '#d9e1ea', fg: '#0b1a2a', sub: '#3a4d63', font: 'Rajdhani', mark: 'grid' },
        clean: { bg0: '#071014', bg1: '#0e2a33', fg: '#e9f3f1', sub: '#29e7ff', font: 'Michroma', mark: 'ring' },
        money: { bg0: '#03140c', bg1: '#0b3d23', fg: '#7dffb6', sub: '#d8ffe9', font: 'Rajdhani', mark: 'arrow' },
        gold: { bg0: '#120c02', bg1: '#3b2706', fg: '#ffcf5a', sub: '#fff1c4', font: 'Michroma', mark: 'sun' },
        warn: { bg0: '#1a0204', bg1: '#5a0710', fg: '#ff3a4a', sub: '#ffd2d6', font: 'Black Ops One', mark: 'tri' },
        shop: { bg0: '#1c1404', bg1: '#4d3507', fg: '#ffd23d', sub: '#fff3c2', font: 'Black Ops One', mark: 'chip' },
    }[st] || {};
    ctx.save();
    const gr = ctx.createLinearGradient(x, y, x + w, y + h);
    gr.addColorStop(0, S.bg0); gr.addColorStop(1, S.bg1);
    ctx.fillStyle = gr; ctx.fillRect(x, y, w, h);
    // Futurist diagonal: a wedge of light across the panel
    ctx.globalAlpha = 0.18; ctx.fillStyle = S.fg;
    ctx.beginPath(); ctx.moveTo(x + w * 0.55, y); ctx.lineTo(x + w * 0.75, y); ctx.lineTo(x + w * 0.42, y + h); ctx.lineTo(x + w * 0.22, y + h); ctx.fill();
    ctx.globalAlpha = 1;
    // the mark, left third
    const mx = x + h * 0.55, my = y + h * 0.5, mr = h * 0.3;
    ctx.strokeStyle = S.fg; ctx.fillStyle = S.fg; ctx.lineWidth = Math.max(2, h * 0.04);
    if (S.mark === 'bubble') { ctx.beginPath(); ctx.roundRect(mx - mr, my - mr * 0.8, mr * 2, mr * 1.5, mr * 0.35); ctx.fill();
        ctx.beginPath(); ctx.moveTo(mx - mr * 0.5, my + mr * 0.65); ctx.lineTo(mx - mr * 0.9, my + mr * 1.1); ctx.lineTo(mx - mr * 0.05, my + mr * 0.65); ctx.fill();
        ctx.fillStyle = S.bg0; for (let k = -1; k <= 1; k++) { ctx.beginPath(); ctx.arc(mx + k * mr * 0.55, my - mr * 0.05, mr * 0.13, 0, 7); ctx.fill(); } }
    else if (S.mark === 'grid') { for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) ctx.fillRect(mx - mr + i * mr * 0.72, my - mr + j * mr * 0.72, mr * 0.55, mr * 0.55); }
    else if (S.mark === 'ring') { ctx.beginPath(); ctx.arc(mx, my, mr, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.arc(mx, my, mr * 0.55, 0.3, 5.9); ctx.stroke(); }
    else if (S.mark === 'arrow') { ctx.beginPath(); ctx.moveTo(mx - mr, my + mr); ctx.lineTo(mx + mr * 0.6, my - mr * 0.6); ctx.lineTo(mx + mr * 0.6, my - mr * 0.05);
        ctx.moveTo(mx + mr * 0.6, my - mr * 0.6); ctx.lineTo(mx + mr * 0.05, my - mr * 0.6); ctx.stroke(); }
    else if (S.mark === 'sun') { for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2; ctx.beginPath(); ctx.moveTo(mx + Math.cos(a) * mr * 0.45, my + Math.sin(a) * mr * 0.45);
        ctx.lineTo(mx + Math.cos(a) * mr, my + Math.sin(a) * mr); ctx.stroke(); } ctx.beginPath(); ctx.arc(mx, my, mr * 0.3, 0, 7); ctx.fill(); }
    else if (S.mark === 'tri') { ctx.beginPath(); ctx.moveTo(mx, my - mr); ctx.lineTo(mx + mr, my + mr * 0.8); ctx.lineTo(mx - mr, my + mr * 0.8); ctx.closePath(); ctx.stroke();
        ctx.fillRect(mx - mr * 0.06, my - mr * 0.4, mr * 0.12, mr * 0.65); ctx.fillRect(mx - mr * 0.06, my + mr * 0.38, mr * 0.12, mr * 0.12); }
    else if (S.mark === 'chip') { ctx.strokeRect(mx - mr * 0.6, my - mr * 0.6, mr * 1.2, mr * 1.2); for (let k = -2; k <= 2; k++) {
        ctx.beginPath(); ctx.moveTo(mx + k * mr * 0.24, my - mr * 0.6); ctx.lineTo(mx + k * mr * 0.24, my - mr); ctx.moveTo(mx + k * mr * 0.24, my + mr * 0.6); ctx.lineTo(mx + k * mr * 0.24, my + mr); ctx.stroke(); } }
    // the slogan
    const tx = x + h * 1.05, tw = w - h * 1.2;
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    const size = fitFont(ctx, ad.text, S.font, '', tw, h * (ad.sub ? 0.42 : 0.55));
    ctx.fillStyle = S.fg;
    const ty = y + h * (ad.sub ? 0.56 : 0.66);
    ctx.fillText(ad.text, tx, ty);
    if (ad.tm) { const wT = ctx.measureText(ad.text).width; ctx.font = `${Math.round(size * 0.32)}px "Rajdhani"`; ctx.fillText('TM', tx + wT + size * 0.06, ty - size * 0.55); }
    if (ad.sub) { ctx.fillStyle = S.sub; fitFont(ctx, ad.sub, 'Share Tech Mono', '', tw, h * 0.15); ctx.fillText(ad.sub, tx, y + h * 0.84); }
    ctx.restore();
}

// the atlas: shelf-packed, 16 px gutters, uv rects in canvas space (y down, 0..1)
export function makeSignAtlas(K, N = 2048, NH = 3200) {
    const { THREE } = K;
    const { canvas, ctx } = makeCanvas(N, NH);
    ctx.clearRect(0, 0, N, NH);
    const items = {};
    let cx = 16, cy = 16, rowH = 0;
    const place = (id, w, h, draw) => {
        if (cx + w + 16 > N) { cx = 16; cy += rowH + 16; rowH = 0; }
        if (cy + h + 16 > NH) { console.warn('[citykit] sign atlas full at', id); return; }
        draw(ctx, cx, cy, w, h);
        items[id] = { u: cx / N, v: cy / NH, w: w / N, h: h / NH, aspect: w / h };
        cx += w + 16; rowH = Math.max(rowH, h);
    };
    const R = rng(99);
    // lightbox ads 4:1
    for (const ad of AD_COPY) place('ad:' + ad.id, 600, 150, (c, x, y, w, h) => adPanel(c, ad, x, y, w, h, R));
    // Futurist supergraphics: chrome/ochre letters on a dark painted ground, Depero's typographic architecture
    FUTURIST.forEach((word, i) => place('fut:' + i, 768, 128, (c, x, y, w, h) => {
        c.save(); c.fillStyle = i % 2 ? '#0d0b10' : '#0c1416'; c.fillRect(x, y, w, h);
        c.textAlign = 'center'; c.textBaseline = 'middle';
        const fam = ['Black Ops One', 'Michroma', 'Rajdhani'][i % 3];
        const size = fitFont(c, word, fam, '', w * 0.94, h * 0.78);
        const gr = c.createLinearGradient(x, y, x, y + h);
        const pal = [['#e9f3f1', '#7f8ea0'], ['#ffcf5a', '#b0601f'], ['#ff4fd8', '#5a1a6e'], ['#29e7ff', '#0d5a6a']][i % 4];
        gr.addColorStop(0, pal[0]); gr.addColorStop(1, pal[1]);
        c.fillStyle = gr; c.fillText(word, x + w / 2, y + h / 2 + size * 0.04);
        c.restore();
    }));
    // shop neon words 4:1 on transparent ground
    for (const [word, col] of SHOPS) place('shop:' + word, 480, 120, (c, x, y, w, h) => neonText(c, word, x, y, w, h, NEON[col], word.length > 12 ? 'Rajdhani' : 'Monoton', { weight: word.length > 12 ? 'bold' : '' }));
    // vertical blades: letters stacked
    for (const [word, col] of BLADES) place('blade:' + word, 96, 448, (c, x, y, w, h) => {
        c.save(); c.fillStyle = 'rgba(8,8,12,0.92)'; c.fillRect(x, y, w, h);
        c.strokeStyle = NEON[col]; c.lineWidth = 3; c.shadowColor = NEON[col]; c.shadowBlur = 10; c.strokeRect(x + 5, y + 5, w - 10, h - 10);
        const L = [...word.replace(/ /g, '')]; const lh = (h - 24) / L.length;
        L.forEach((ch, k) => neonText(c, ch, x, y + 12 + k * lh, w, lh, NEON[col], 'Rajdhani', { weight: 'bold', fill: 0.92 }));
        c.restore();
    });
    // a helipad and two roof chevrons
    place('heli', 256, 256, (c, x, y, w, h) => { c.save(); c.strokeStyle = '#e9f3f1'; c.lineWidth = 10; c.beginPath(); c.arc(x + w / 2, y + h / 2, w * 0.42, 0, 7); c.stroke();
        c.fillStyle = '#e9f3f1'; c.font = `bold ${h * 0.55}px "Rajdhani"`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('H', x + w / 2, y + h / 2 + 4); c.restore(); });
    place('chev', 256, 128, (c, x, y, w, h) => { c.save(); c.fillStyle = '#ffc23d'; for (let k = 0; k < 4; k++) { const ox = x + 20 + k * 58; c.beginPath(); c.moveTo(ox, y + 10); c.lineTo(ox + 30, y + 10); c.lineTo(ox + 60, y + h / 2); c.lineTo(ox + 30, y + h - 10); c.lineTo(ox, y + h - 10); c.lineTo(ox + 30, y + h / 2); c.fill(); } c.restore(); });
    // roof supergraphics (seen from the dive): huge painted words on roofs
    const ROOF = ['ALIGNED', 'SAFE. FAST. YOURS.', 'BY Q3', 'AUTOCOMPLETE', 'VELOCITÀ', 'ZANG TUMB TUMB', 'TRUST', 'ACCELERATE'];
    ROOF.forEach((word, i) => place('roof:' + i, 448, 224, (c, x, y, w, h) => {
        c.save(); c.fillStyle = 'rgba(0,0,0,0)'; c.clearRect(x, y, w, h);
        c.textAlign = 'center'; c.textBaseline = 'middle';
        const col = ['#e9f3f1', '#ffcf5a', '#ff4fd8', '#29e7ff'][i % 4];
        const size = fitFont(c, word, 'Black Ops One', '', w * 0.9, h * 0.62);
        c.globalAlpha = 0.9; c.fillStyle = col; c.fillText(word, x + w / 2, y + h / 2);
        c.lineWidth = 6; c.strokeStyle = col; c.strokeRect(x + 10, y + 10, w - 20, h - 20);
        c.restore();
    }));
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.magFilter = THREE.LinearFilter; t.anisotropy = 8;
    t.needsUpdate = true;
    return { texture: t, items, canvas };
}

// signs: list of { id, pos:[x,y,z], quat:THREE.Quaternion, w, h, gain, flicker(0 none,1 buzz,2 slow pulse), power }
export function makeSignsMesh(K, atlas, signs) {
    const { THREE, T, U, H } = K;
    const { attribute, vec2, vec3, float, floor, fract, step, smoothstep, mix, texture, uv, sin } = T;
    signs = signs.filter((s) => atlas.items[s.id]);
    const n = signs.length;
    const geo = new THREE.PlaneGeometry(1, 1);
    const rect = new Float32Array(n * 4), parm = new Float32Array(n * 4);
    const mesh = new THREE.InstancedMesh(geo, null, n);
    const m4 = new THREE.Matrix4();
    signs = signs.filter((s) => { if (!atlas.items[s.id]) { console.warn('[citykit] no atlas item', s.id); return false; } return true; });
    signs.forEach((s, i) => {
        const it = atlas.items[s.id];
        rect.set([it.u, it.v, it.w, it.h], i * 4);
        parm.set([s.gain ?? 3, s.flicker ?? 0, s.power ?? hash1(i * 7.13), (i * 0.6180339) % 1], i * 4);
        m4.compose(new THREE.Vector3(...s.pos), s.quat, new THREE.Vector3(s.w, s.h, 1));
        mesh.setMatrixAt(i, m4);
    });
    geo.setAttribute('iRect', new THREE.InstancedBufferAttribute(rect, 4));
    geo.setAttribute('iParm', new THREE.InstancedBufferAttribute(parm, 4));
    const mat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide });
    mat.name = 'uf_signs'; mat.fog = false;
    const r = attribute('iRect', 'vec4'), p = attribute('iParm', 'vec4');
    const suv = vec2(r.x.add(uv().x.mul(r.z)), r.y.add(float(1).sub(uv().y).mul(r.w)));
    const c = texture(atlas.texture, suv);
    const on = smoothstep(p.z.sub(0.015), p.z.add(0.015), U.power);
    const buzz = float(1).sub(step(0.9, H.hash11(floor(U.time.mul(14.0)).add(p.w.mul(173.0)))).mul(0.85));
    const slow = sin(U.time.mul(1.7).add(p.w.mul(40.0))).mul(0.35).add(0.75);
    const fl = mix(mix(float(1), buzz, step(0.5, p.y).mul(step(p.y, 1.5))), slow, step(1.5, p.y));
    const fade = float(1).sub(K.fog.factor);
    mat.colorNode = c.rgb.mul(p.x).mul(on).mul(fl).mul(U.neon).mul(fade);
    mat.opacityNode = c.a;
    if (T.mrt) mat.mrtNode = T.mrt({ normal: T.vec4(0), metalrough: T.vec4(0) });
    mesh.material = mat;
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    mesh.name = 'uf_signs';
    mesh.renderOrder = 2;
    return mesh;
}

// ------------------------------------------------------------------------------------------------ rain
// Streaks in a box that wraps around the camera. Each streak is the drop's path over a short exposure RELATIVE to the
// camera, so during the dive the rain streams outward from the vanishing point (Crali's lines of speed for free).
// Drops are lit by the street light map below them: rain in front of a sign takes the sign's colour.
export function makeRain(K, opt = {}) {
    const { THREE, T, U } = K;
    const { Fn, attribute, vec2, vec3, vec4, float, floor, fract, max, min, length, normalize, cross, mix, smoothstep, abs, exp,
        positionLocal, cameraPosition, uv } = T;
    const N = opt.count || 26000;
    const BOX = [70, 56, 70], VF = 9.5, EXPO = 1 / 45;
    const seeds = new Float32Array(N * 4); const R = rng(4242);
    for (let i = 0; i < N; i++) seeds.set([R(), R(), R(), R()], i * 4);
    const geo = new THREE.PlaneGeometry(1, 1);
    geo.setAttribute('iSeed', new THREE.InstancedBufferAttribute(seeds, 4));
    const mat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    mat.name = 'uf_rain'; mat.fog = false;
    const box = vec3(...BOX);
    const wind = vec3(1.6, 0, 0.7);
    const vRain = vec3(wind.x, -VF, wind.z);
    const s = attribute('iSeed', 'vec4');
    const center = Fn(() => {
        const p0 = s.xyz.mul(box).add(vRain.mul(U.time.add(s.w.mul(3.0))));
        const rel = p0.sub(cameraPosition);
        const w = rel.sub(floor(rel.div(box).add(0.5)).mul(box));
        return cameraPosition.add(w);
    })();
    const ctr = center;
    const vRel = vRain.sub(U.camVel);
    const L = vRel.mul(EXPO).add(vec3(0, -0.12, 0));        // at least a short streak
    mat.positionNode = Fn(() => {
        const c = ctr.toVar();
        const toCam = normalize(cameraPosition.sub(c));
        const across = normalize(cross(L, toCam).add(vec3(1e-5, 0, 0)));
        const dist = length(cameraPosition.sub(c));
        const width = max(float(0.003), dist.mul(0.0011));
        return c.add(L.mul(positionLocal.y)).add(across.mul(positionLocal.x).mul(width));
    })();
    const dist = length(cameraPosition.sub(ctr));
    const width = max(float(0.003), dist.mul(0.0011));
    const cover = float(0.003).div(width);
    const nearF = smoothstep(0.4, 2.0, dist).mul(float(1).sub(smoothstep(22.0, 34.0, dist)));
    const across = abs(uv().x.sub(0.5)).mul(2.0);
    const prof = float(1).sub(across).mul(smoothstep(0.0, 0.25, uv().y)).mul(smoothstep(1.0, 0.75, uv().y));
    const lit = lmSample(K, ctr.xz, 2.0).rgb.mul(exp(max(ctr.y.sub(STREET_Y), 0.0).negate().div(26.0))).mul(1.8);
    const base = vec3(0.30, 0.36, 0.44).mul(0.32);
    const fade = float(1).sub(K.fog.factor);
    mat.colorNode = base.add(lit).mul(U.rain).mul(fade);
    mat.opacityNode = prof.mul(nearF).mul(cover.mul(0.9).add(0.1)).mul(0.55);
    if (T.mrt) mat.mrtNode = T.mrt({ normal: T.vec4(0), metalrough: T.vec4(0) });
    const mesh = new THREE.InstancedMesh(geo, mat, N);
    mesh.frustumCulled = false;
    mesh.name = 'uf_rain';
    mesh.renderOrder = 3;
    mesh.userData.noSupportCheck = true; mesh.userData.noClippingCheck = true; mesh.userData.noCameraCollide = true;
    return { mesh };
}

// ------------------------------------------------------------------------------------------------ clouds + sky
// The low rain-cloud deck: stacked noise sheets between CLOUD.base and CLOUD.top that follow the camera in x/z (the
// noise is fixed in the world). Their undersides take the city's light map — the deck glows over the bright streets
// and over the hole. Sheets near the camera fade out (no hard planes when the camera falls through).
export function makeClouds(K, opt = {}) {
    const { THREE, T, U, tex } = K;
    const { Fn, vec2, vec3, float, mix, smoothstep, clamp, abs, pow, length, texture, positionWorld, cameraPosition, max } = T;
    const group = new THREE.Group(); group.name = 'uf_clouds';
    const LAYERS = opt.layers || 13;
    const mat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide });
    mat.name = 'uf_cloud'; mat.fog = false;
    const xz = positionWorld.xz;
    const y = positionWorld.y;
    const fr = clamp(y.sub(CLOUD.base).div(CLOUD.top - CLOUD.base), 0.0, 1.0);
    const drift = vec2(U.time.mul(1.4), U.time.mul(0.5));
    const n1 = texture(tex.noise, xz.add(drift).div(1400.0)).r;
    const n2 = texture(tex.noise, xz.add(drift.mul(1.6)).div(380.0).add(fr.mul(0.11))).g;
    const n3 = texture(tex.noise, xz.add(drift.mul(2.2)).div(95.0).add(fr.mul(0.31))).r;
    const prof = float(1).sub(pow(abs(fr.mul(2.0).sub(1.0)), 1.6));
    const dens = n1.mul(0.55).add(n2.mul(0.3)).add(n3.mul(0.15)).sub(float(0.62).sub(prof.mul(0.22)));
    const d = length(positionWorld.sub(cameraPosition));
    const nearF = smoothstep(2.5, 14.0, d);
    const farF = float(1).sub(smoothstep(1500.0, 2300.0, length(xz.sub(cameraPosition.xz))));
    const a = smoothstep(0.0, 0.13, dens).mul(0.44).mul(nearF).mul(farF).mul(U.cloud);
    const city = lmSample(K, xz, 5.0).rgb;
    const under = float(1).sub(fr).mul(float(1).sub(fr));
    const body = mix(vec3(0.020, 0.018, 0.026), vec3(0.055, 0.050, 0.064), fr).mul(n2.mul(0.7).add(0.55));
    const edge = smoothstep(0.11, 0.0, dens).mul(0.6).add(0.4);     // thin edges catch more of the glow
    mat.colorNode = body.add(city.mul(under.mul(2.6).add(0.25)).mul(edge)).add(vec3(0.35, 0.38, 0.45).mul(U.flash).mul(n1));
    mat.opacityNode = a;
    if (T.mrt) mat.mrtNode = T.mrt({ normal: T.vec4(0), metalrough: T.vec4(0) });
    const geo = new THREE.PlaneGeometry(4800, 4800);
    geo.rotateX(-Math.PI / 2);
    const sheets = [];
    for (let i = 0; i < LAYERS; i++) {
        const sh = new THREE.Mesh(geo, mat);
        sh.position.y = CLOUD.base + (CLOUD.top - CLOUD.base) * (i / (LAYERS - 1));
        sh.frustumCulled = false; sh.renderOrder = 1;
        sh.userData.noSupportCheck = true; sh.userData.noClippingCheck = true; sh.userData.noCameraCollide = true; sh.userData.noZFightCheck = true;
        group.add(sh); sheets.push(sh);
    }
    return { group, sheets, update(camera) { for (const s of sheets) { s.position.x = camera.position.x; s.position.z = camera.position.z; } } };
}

// a dome that rides with the camera: dark overcast above, the haze colour at the horizon (matches the fog)
export function makeSky(K) {
    const { THREE, T, U } = K;
    const { vec3, float, mix, smoothstep, normalize, positionWorld, cameraPosition, max, pow } = T;
    const mat = new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide, depthWrite: false });
    mat.name = 'uf_sky'; mat.fog = false;
    const dir = normalize(positionWorld.sub(cameraPosition));
    const up = max(dir.y, 0.0);
    const hz = vec3(0.020, 0.0145, 0.0195).mul(1.05);
    const zen = vec3(0.006, 0.0055, 0.0085);
    const c = mix(hz, zen, pow(smoothstep(0.0, 0.85, up), 0.6));
    mat.colorNode = mix(c, hz.mul(0.6), smoothstep(0.0, -0.3, dir.y)).add(vec3(0.05, 0.055, 0.07).mul(U.flash));
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1800, 32, 16), mat);
    mesh.name = 'uf_sky'; mesh.renderOrder = -10; mesh.frustumCulled = false;
    mesh.userData.noSupportCheck = true; mesh.userData.noClippingCheck = true; mesh.userData.noCameraCollide = true;
    return { mesh, update(camera) { mesh.position.copy(camera.position); } };
}

// ------------------------------------------------------------------------------------------------ traffic
// cars as dark bodies with head/tail lights, driving the ring roads and avenues; positions are a pure function of time
// in the vertex shader (no per-frame CPU). paths: [{ type:'ring', r, dir, speed } | { type:'av', th, r0, r1, lane, dir, speed }]
export function makeTraffic(K, paths, opt = {}) {
    const { THREE, T, U, H } = K;
    const { Fn, attribute, vec3, vec4, float, floor, fract, sin, cos, mix, step, smoothstep, abs, max, positionLocal, select } = T;
    const n = paths.length;
    const body = new THREE.BoxGeometry(1.9, 1.35, 4.6, 1, 1, 1); body.translate(0, 0.68, 0);
    const pa = new Float32Array(n * 4), pb = new Float32Array(n * 4);
    paths.forEach((p, i) => {
        if (p.type === 'ring') { pa.set([0, p.r, p.phase, p.speed * p.dir], i * 4); pb.set([0, 0, hash1(i * 3.3), hash1(i * 9.1)], i * 4); }
        else { pa.set([1, p.th, p.phase, p.speed * p.dir], i * 4); pb.set([p.lane, p.r0, p.r1, hash1(i * 9.1)], i * 4); }
    });
    body.setAttribute('cA', new THREE.InstancedBufferAttribute(pa, 4));
    body.setAttribute('cB', new THREE.InstancedBufferAttribute(pb, 4));
    const mat = new THREE.MeshBasicNodeMaterial();
    mat.name = 'uf_traffic';
    const A = attribute('cA', 'vec4'), B = attribute('cB', 'vec4');
    // world pose from time
    const pose = Fn(() => {
        const isAv = step(0.5, A.x);
        // ring: angle = phase + v t / r
        const ang = A.z.add(U.time.mul(A.w).div(max(A.y, 1.0)));
        const ringP = vec3(cos(ang).mul(A.y), float(STREET_Y), sin(ang).mul(A.y));
        const ringYaw = ang.negate().add(select(A.w.lessThan(0), float(Math.PI), float(0)));
        // avenue: s in [r0, r1] wrapping
        const span = max(B.z.sub(B.y), 1.0);
        const s0 = A.z.mul(span).add(U.time.mul(A.w));
        const s = B.y.add(s0.sub(floor(s0.div(span)).mul(span)));
        const dirX = cos(A.y), dirZ = sin(A.y);
        const avP = vec3(dirX.mul(s).sub(dirZ.mul(B.x)), float(STREET_Y), dirZ.mul(s).add(dirX.mul(B.x)));
        const avYaw = A.y.negate().add(Math.PI / 2).add(select(A.w.lessThan(0), float(Math.PI), float(0)));
        return vec4(mix(ringP, avP, isAv), mix(ringYaw, avYaw, isAv));
    })();
    mat.positionNode = Fn(() => {
        const ps = pose.toVar();
        const c = cos(ps.w), sn = sin(ps.w);
        const p = positionLocal;
        const rx = p.x.mul(c).add(p.z.mul(sn)), rz = p.x.negate().mul(sn).add(p.z.mul(c));
        return vec3(rx, p.y, rz).add(ps.xyz);
    })();
    const p = positionLocal;
    const front = step(2.25, p.z), back = step(p.z, -2.25);
    const lampRow = smoothstep(0.45, 0.55, p.y).mul(smoothstep(0.95, 0.85, p.y));
    const side = step(0.55, abs(p.x)).mul(step(abs(p.x), 0.9));
    const on = smoothstep(B.w.sub(0.015), B.w.add(0.015), U.power);
    const head = vec3(1.0, 0.93, 0.8).mul(10.0).mul(front).mul(lampRow).mul(side);
    const tail = vec3(1.0, 0.05, 0.04).mul(7.0).mul(back).mul(lampRow).mul(side);
    const roofSheen = smoothstep(1.2, 1.35, p.y).mul(0.006);
    const fade = float(1).sub(K.fog.factor);
    mat.colorNode = vec3(0.012, 0.013, 0.016).add(roofSheen).add(head.add(tail).mul(on).mul(fade));
    const mesh = new THREE.InstancedMesh(body, mat, n);
    mesh.frustumCulled = false;
    mesh.name = 'uf_traffic';
    mesh.userData.noSupportCheck = true; mesh.userData.noClippingCheck = true; mesh.userData.noCameraCollide = true;
    return { mesh };
}

// ------------------------------------------------------------------------------------------------ street lamps
// instanced sodium lamps: a pole, an arm over the road, a lit head. lamps: [{ x, z, yaw }] (arm points along -Z local)
export function makeLamps(K, lamps) {
    const { THREE, T, U } = K;
    const { attribute, vec3, float, step, smoothstep, mix, positionLocal, texture } = T;
    const pole = new THREE.CylinderGeometry(0.11, 0.16, 9, 6, 1); pole.translate(0, 4.5, 0);
    const arm = new THREE.BoxGeometry(0.14, 0.14, 2.6); arm.translate(0, 8.9, -1.25);
    const head = new THREE.BoxGeometry(0.42, 0.16, 0.9); head.translate(0, 8.78, -2.45);
    const parts = [pole, arm, head].map((g) => g.toNonIndexed());
    const merged = new THREE.BufferGeometry();
    const pos = [], nor = [], flag = [];
    parts.forEach((g, k) => { const P = g.getAttribute('position'), Nn = g.getAttribute('normal');
        for (let i = 0; i < P.count; i++) { pos.push(P.getX(i), P.getY(i), P.getZ(i)); nor.push(Nn.getX(i), Nn.getY(i), Nn.getZ(i)); flag.push(k === 2 ? 1 : 0); } });
    merged.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    merged.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    merged.setAttribute('lampHead', new THREE.Float32BufferAttribute(flag, 1));
    const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.45, metalness: 0.6 });
    mat.name = 'uf_lamps';
    const ph = new Float32Array(lamps.length);
    lamps.forEach((l, i) => { ph[i] = hash1(i * 1.37 + 5.0); });
    merged.setAttribute('lampPow', new THREE.InstancedBufferAttribute(ph, 1));
    const isHead = attribute('lampHead', 'float'), pw = attribute('lampPow', 'float');
    const on = smoothstep(pw.sub(0.015), pw.add(0.015), U.power);
    const down = step(positionLocal.y, 8.72);
    mat.colorNode = mix(vec3(0.05, 0.05, 0.055), vec3(0.2, 0.18, 0.15), isHead);
    mat.emissiveNode = vec3(1.0, 0.45, 0.14).mul(9.0).mul(isHead).mul(down).mul(on).mul(U.street);
    mat.envNode = texture(K.tex.env); mat.envMapIntensity = 0.6;
    const mesh = new THREE.InstancedMesh(merged, mat, lamps.length);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1);
    lamps.forEach((l, i) => { q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), l.yaw); m4.compose(new THREE.Vector3(l.x, STREET_Y, l.z), q, one); mesh.setMatrixAt(i, m4); });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    mesh.name = 'uf_lamps';
    return { mesh };
}

// ------------------------------------------------------------------------------------------------ cameras
// A camera pose: { pos:[x,y,z], target:[x,y,z], fov, roll (radians, about the view axis), up?:[x,y,z] }.
// `up` is the image-up reference (needed when looking straight down, where lookAt's world-up degenerates).
export function applyCam(THREE, camera, c) {
    camera.position.set(c.pos[0], c.pos[1], c.pos[2]);
    const f = new THREE.Vector3(c.target[0] - c.pos[0], c.target[1] - c.pos[1], c.target[2] - c.pos[2]).normalize();
    let up = c.up ? new THREE.Vector3(...c.up) : new THREE.Vector3(0, 1, 0);
    if (Math.abs(f.dot(up.clone().normalize())) > 0.995) up = new THREE.Vector3(0, 0, -1);
    const m = new THREE.Matrix4().lookAt(camera.position, new THREE.Vector3(...c.target), up);
    camera.quaternion.setFromRotationMatrix(m);
    if (c.roll) camera.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), c.roll));
    if (c.fov && camera.fov !== c.fov) { camera.fov = c.fov; camera.updateProjectionMatrix(); }
    camera.updateMatrixWorld();
}
// camera velocity by central difference of any pose function (for the rain streaks; independent of frame order)
export function camVelocity(fn, t, dt = 1 / 120) {
    const a = fn(t - dt).pos, b = fn(t + dt).pos;
    return [(b[0] - a[0]) / (2 * dt), (b[1] - a[1]) / (2 * dt), (b[2] - a[2]) / (2 * dt)];
}
// Catmull-Rom through keys [{t, v:[...]}] (uniform in key index, eased by time inside each segment)
export function keyed(keys, t, ease = smooth) {
    if (t <= keys[0].t) return keys[0].v.slice();
    const L = keys.length;
    if (t >= keys[L - 1].t) return keys[L - 1].v.slice();
    let i = 0; while (i < L - 2 && t > keys[i + 1].t) i++;
    const k0 = keys[Math.max(0, i - 1)], k1 = keys[i], k2 = keys[i + 1], k3 = keys[Math.min(L - 1, i + 2)];
    const u = (t - k1.t) / (k2.t - k1.t);
    const s = ease ? ease(u) : u;
    return k1.v.map((_, j) => {
        const p0 = k0.v[j], p1 = k1.v[j], p2 = k2.v[j], p3 = k3.v[j];
        return 0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s * s * s);
    });
}
