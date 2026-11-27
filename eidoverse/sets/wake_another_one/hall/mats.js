// eidoverse/sets/wake_another_one/hall/mats.js — the hall's materials in TSL: a port of the Blender edition's
// hall._mats (and look.py's post hooks). Every one is a CC0 scan (ambientCG, fetched by ID into the shared library on
// first use: fetchPBR) under LAYERS, as one would paint it:
//   1 the scan at its real size (UVs in metres), its colour brought to the paint's own colour, its roughness and
//     normal kept;
//   2 large-scale variation of value and roughness;
//   3 roughness breakup: smudges and scratches (the edition's generators, eidoverse/procedural_materials.js drawn the
//     same way, at 2048 px) and fine procedural grain;
//   4 EDGE WEAR from the vertex attribute `wear` (kit.js: 1 on an arris, 0 a wear-width in), multiplied by fine noise
//     and kept out of crevices by `cavity`: through the paint to primer, then to bare metal;
//   5 GRIME in the crevices from `cavity` multiplied by noise;
//   6 DUST on what faces up;
//   7 what use leaves there, per material (the floor's lanes, joints and tyre arcs; hand polish; grease).
// The procedural layers are Blender's own noise (sets/same_seed/noise.js: the same hash and gradients, so a stain falls
// where it fell in Blender); Map Range, Mix and Math as Blender's nodes compute them; the bump from screen derivatives
// as Blender's Bump node; the tangent-space normal maps on a frame from the UVs' derivatives.
//   const MT = await makeMats(THREE, { log });     MT.material(name, spec)   MT.setFrame(hallGroup)
import { makeNoise } from '../../same_seed/noise.js';

// the scans' means as the Blender edition measured them (the colour map at 64 x 64, linear; the roughness map's)
export const SCAN_MEAN = {
    Metal049A: [[0.972, 0.963, 0.922], 0.034], Metal027: [[0.027, 0.026, 0.035], 0.649], Rubber004: [[0.023, 0.025, 0.031], 0.591],
    Plastic010: [[0.367, 0.383, 0.409], 0.363], Metal009: [[0.288, 0.299, 0.313], 0.469], Concrete034: [[0.481, 0.481, 0.481], 0.516],
    Paper001: [[0.909, 0.9, 0.884], 0.631], Asphalt012: [[0.06, 0.057, 0.057], 0.805],
};

// Mulberry32, as procedural_materials.js seeds its strokes
function rng(seed) {
    return () => {
        seed |= 0; seed = seed + 0x6D2B79F5 | 0;
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
}

// the edition's generators (eidoverse/procedural_materials.js' scratches and smudges, which the Blender edition
// replays), drawn at `size` px on a canvas, as PNG bytes
export async function generated(kind, size = 2048) {
    const C = await import('npm:@napi-rs/canvas@0.1.69');
    const cv = C.createCanvas(size, size), g = cv.getContext('2d');
    g.fillStyle = '#000';
    g.fillRect(0, 0, size, size);
    if (kind === 'scratches' || kind === 'scratches_fine') {
        const [density, depth] = kind === 'scratches' ? [0.55, 0.6] : [0.9, 0.35];
        const rand = rng(42);
        const count = Math.floor(size * density * 2.5);
        for (let i = 0; i < count; i++) {
            const x = rand() * size, y = rand() * size;
            const angle = rand() * Math.PI;
            const len = 8 + rand() * 50;
            const bright = Math.floor(depth * (100 + rand() * 155));
            g.strokeStyle = `rgb(${bright},${bright},${bright})`;
            g.lineWidth = 0.3 + rand() * 1.2;
            g.globalAlpha = 0.3 + rand() * 0.7;
            g.beginPath();
            g.moveTo(x - Math.cos(angle) * len / 2, y - Math.sin(angle) * len / 2);
            g.lineTo(x + Math.cos(angle) * len / 2, y + Math.sin(angle) * len / 2);
            g.stroke();
        }
        g.globalAlpha = 1;
    } else if (kind === 'smudges') {
        const amount = 0.55, scale = 1.0, rand = rng(123);
        const count = Math.floor(15 * amount * scale) + 3;
        for (let i = 0; i < count; i++) {
            const cx = rand() * size, cy = rand() * size;
            const radius = 20 + rand() * 80 * scale;
            const bright = Math.floor(128 + rand() * 127);
            const grad = g.createRadialGradient(cx, cy, 0, cx, cy, radius);
            const a1 = 0.3 + rand() * 0.5, a2 = 0.1 + rand() * 0.2;
            grad.addColorStop(0, `rgba(${bright},${bright},${bright},${a1})`);
            grad.addColorStop(0.6, `rgba(${bright},${bright},${bright},${a2})`);
            grad.addColorStop(1, 'rgba(0,0,0,0)');
            g.fillStyle = grad;
            g.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
        }
    } else throw new Error(`hall mats: no generator ${kind}`);
    return new Uint8Array(cv.toBuffer('image/png'));
}

export async function makeMats(THREE, { log = console.log, flat = false } = {}) {
    const T = THREE;
    const { Fn, float, vec2, vec3, vec4, mix, clamp, abs, floor, sin, sqrt, max, min, pow, normalize, cross, dot, sign, select,
        texture, attribute, uniform, positionWorld, normalWorld, frontFacing, transformDirection, cameraViewMatrix, dFdx, dFdy } = T;
    const N = makeNoise(T);
    // the hall's own frame (+Z up) from three's world: its root's matrix and inverse, set by setFrame()
    const hallMat = uniform(new T.Matrix4()), hallInv = uniform(new T.Matrix4());
    const toHallP = (p) => hallInv.mul(vec4(p, 1.0)).xyz;
    const toHallD = (d) => hallInv.mul(vec4(d, 0.0)).xyz;
    const fromHallD = (d) => hallMat.mul(vec4(d, 0.0)).xyz;
    const PW = toHallP(positionWorld);                                 // Geometry > Position (world)
    // Geometry > Normal, the side the camera sees: three's normalWorld is turned to the viewer already (in a normal
    // node, the geometry's; elsewhere, the shading normal)
    const NWh = normalize(toHallD(normalWorld));
    const OBJ = attribute('position', 'vec3');                         // Texture Coordinate > Object
    const ONRM = attribute('normal', 'vec3');                          // Texture Coordinate > Normal (the object's own)
    const UV3 = vec3(attribute('uv', 'vec2'), 0.0);                    // UVMap (metres)
    const num = (x) => (typeof x === 'number' ? float(x) : Array.isArray(x) ? vec3(x[0], x[1], x[2]) : x);
    const isNum = (x) => typeof x === 'number';

    // ---------------------------------------------------------------------------------------- Blender's nodes
    const g = {
        add: (a, b) => (isNum(a) && isNum(b) ? a + b : num(a).add(num(b))),
        sub: (a, b) => (isNum(a) && isNum(b) ? a - b : num(a).sub(num(b))),
        mul: (a, b) => (isNum(a) && isNum(b) ? a * b : num(a).mul(num(b))),
        madd: (a, b, c) => num(a).mul(num(b)).add(num(c)),
        div: (a, b) => (isNum(b) ? num(a).mul(1.0 / b) : select(num(b).equal(0.0), float(0.0), num(a).div(num(b)))),
        maximum: (a, b) => max(num(a), num(b)), minimum: (a, b) => min(num(a), num(b)),
        power: (a, b) => pow(max(num(a), 0.0), num(b)),
        absolute: (a) => abs(num(a)), floor: (a) => floor(num(a)), fract: (a) => num(a).sub(floor(num(a))),
        sine: (a) => sin(num(a)), sqrt: (a) => sqrt(max(num(a), 0.0)),
        clamp01: (a) => clamp(num(a), 0.0, 1.0),
        // Map Range, clamped: x from a..b -> c..d (smoothstep unless smooth=false); a > b turns it round
        ramp: (x, a, b, c = 0.0, d = 1.0, smooth = true) => {
            let f = clamp(num(x).sub(a).mul(1.0 / (b - a)), 0.0, 1.0);
            if (smooth) f = f.mul(f).mul(float(3.0).sub(f.mul(2.0)));
            return num(c).add(f.mul(g.sub(d, c)));
        },
        mixf: (f, a, b) => mix(num(a), num(b), clamp(num(f), 0.0, 1.0)),
        mixc: (f, a, b, blend = 'MIX') => {
            const ff = clamp(num(f), 0.0, 1.0), A = num(a), B = num(b);
            return blend === 'MULTIPLY' ? mix(A, A.mul(B), ff) : mix(A, B, ff);
        },
        scale: (v, s) => num(v).mul(num(s)),
        vadd: (a, b) => num(a).add(num(b)),
        rotz: (v, a) => { const c = Math.cos(a), s = Math.sin(a), V = num(v); return vec3(V.x.mul(c).sub(V.y.mul(s)), V.x.mul(s).add(V.y.mul(c)), V.z); },
        vec: (x, y, z) => vec3(num(x), num(y), num(z)),
        noise: (v, scale, detail = 2.0, rough = 0.5) => N.noise(num(v), { scale, detail, roughness: rough }),
        white: (v) => N.white(num(v)),
        // the Voronoi Texture's F1 colour (3D, Euclidean): the nearest cell's random colour
        voronoiColor: (v, scale, randomness = 1.0) => {
            const p = num(v).mul(scale), cell = floor(p), local = p.sub(cell);
            const cp = (c) => {                                        // (a cell's point and its colour: the same hash)
                const kx = T.uint(T.int(c.x)), ky = T.uint(T.int(c.y)), kz = T.uint(T.int(c.z));
                return vec3(toUnit(N.hashUint3(kx, ky, kz)), toUnit(N.hashUint4(kx, ky, kz, T.uint(1))), toUnit(N.hashUint4(kx, ky, kz, T.uint(2))));
            };
            let best = null, col = null;
            for (let k = -1; k <= 1; k++) for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
                const c = cell.add(vec3(i, j, k)), h = cp(c);
                const d = vec3(i, j, k).add(h.mul(randomness)).sub(local).length();
                if (!best) { best = d; col = h; } else { const closer = d.lessThan(best); best = select(closer, d, best); col = select(closer, h, col); }
            }
            return col;
        },
        img: (tex, v) => texture(tex, num(v).xy),
        // the tangent-space normal map on the frame of the UV's own screen derivatives (no tangents written), or an
        // object-space one; strength mixes from the geometry's normal, as Blender's Normal Map node does
        normalMap: (colour, strength = 1.0, space = 'TANGENT') => {
            const c = num(colour).xyz.mul(2.0).sub(1.0);
            const Nn = NWh;
            if (space === 'OBJECT') return normalize(mix(Nn, normalize(c), max(num(strength), 0.0)));
            const u = attribute('uv', 'vec2');
            const dp1 = toHallD(dFdx(positionWorld)), dp2 = toHallD(dFdy(positionWorld));
            const duv1 = dFdx(u), duv2 = dFdy(u);
            const dp2perp = cross(dp2, Nn), dp1perp = cross(Nn, dp1);
            const t = dp2perp.mul(duv1.x).add(dp1perp.mul(duv2.x)), b = dp2perp.mul(duv1.y).add(dp1perp.mul(duv2.y));
            const inv = float(1.0).div(sqrt(max(dot(t, t), dot(b, b))).max(1e-20));
            const n = normalize(t.mul(inv).mul(c.x).add(b.mul(inv).mul(c.y)).add(Nn.mul(c.z)));
            return normalize(mix(Nn, n, max(num(strength), 0.0)));
        },
        // Blender's Bump: the height's screen derivatives over the surface's
        bump: (height, distance = 1.0, strength = 1.0, normal = null) => {
            const Nt = normal ? normalize(normal) : NWh;
            const dist = select(frontFacing, num(distance), num(distance).negate());
            const dPdx = toHallD(dFdx(positionWorld)), dPdy = toHallD(dFdy(positionWorld));
            const Rx = cross(dPdy, Nt), Ry = cross(Nt, dPdx), det = dot(dPdx, Rx);
            const h = num(height);
            const surf = Rx.mul(dFdx(h)).add(Ry.mul(dFdy(h)));
            const r = normalize(abs(det).mul(Nt).sub(dist.mul(sign(det)).mul(surf)));
            return normalize(mix(Nt, r, num(strength)));
        },
    };
    const toUnit = (h) => float(h).div(4294967295.0);

    // ---------------------------------------------------------------------------------------- pictures
    const texCache = new Map();
    async function tex(path, srgb) {
        const key = `${path}|${srgb}`;
        if (!texCache.has(key)) {
            const t = await globalThis.loadImageTexture(Deno.readFileSync(path), { srgb });
            t.wrapS = t.wrapT = T.RepeatWrapping;
            t.anisotropy = 8;
            texCache.set(key, t);
        }
        return texCache.get(key);
    }
    const scans = new Map();
    async function scan(id, res) {
        const key = `${id}_${res}`;
        if (!scans.has(key)) {
            const files = (await globalThis.fetchPBR(id, { res })).files;
            const out = { id, res, mean: SCAN_MEAN[id][0], rmean: SCAN_MEAN[id][1] };
            out.color = await tex(files.diff, true);
            if (files.rough) out.rough = await tex(files.rough, false);
            if (files.normal) out.normal = await tex(files.normal, false);
            if (files.metal) out.metal = await tex(files.metal, false);
            scans.set(key, out);
            log(`[hall mats] scan ${id} ${res}`);
        }
        return scans.get(key);
    }
    const gens = new Map();
    async function gen(kind) {
        if (!gens.has(kind)) {
            const t = await globalThis.loadImageTexture(await generated(kind), { srgb: false });
            t.wrapS = t.wrapT = T.RepeatWrapping;
            t.anisotropy = 8;
            gens.set(kind, t);
        }
        return gens.get(kind);
    }

    // ---------------------------------------------------------------------------------------- the principled end
    // a Principled BSDF as a node material (physical when it has a coat or glass), drawn on both sides as EEVEE does
    function principled(name, C, R, M, nrm, { coat = null, coatRough = null, emission = null, transmission = null, ior = 1.5 } = {}) {
        const m = (coat !== null || transmission !== null) ? new T.MeshPhysicalNodeMaterial() : new T.MeshStandardNodeMaterial();
        m.name = name;
        m.colorNode = vec4(num(C), 1.0);
        m.roughnessNode = clamp(num(R), 0.0, 1.0);
        m.metalnessNode = clamp(num(M), 0.0, 1.0);
        // (world to view: the matrix first; TSL's transformDirection(v, M) is v times M, the transpose's way)
        if (nrm) m.normalNode = transformDirection(cameraViewMatrix, fromHallD(nrm)).normalize();
        if (emission) m.emissiveNode = num(emission);
        if (coat !== null) { m.clearcoatNode = clamp(num(coat), 0.0, 1.0); m.clearcoatRoughnessNode = clamp(num(coatRough), 0.0, 1.0); }
        if (transmission !== null) { m.transmissionNode = num(transmission); m.iorNode = float(ior); m.thicknessNode = float(0.0); m.transparent = true; }
        m.side = T.DoubleSide;
        return m;
    }

    // ---------------------------------------------------------------------------------------- post hooks
    const HAZARD_BLACK = [0.022, 0.022, 0.024];
    function uprightHoles(S, X) {
        const [u, v] = [X.uv.x, X.uv.y];
        const nx = abs(ONRM.x);
        const du = abs(abs(u).sub(0.017));
        const dv = abs(g.fract(v.mul(1.0 / 0.05)).sub(0.5)).mul(0.05);
        const q = max(dv.sub(0.0075), 0.0);
        const dist = sqrt(du.mul(du).add(q.mul(q))).sub(0.0048);
        const hole = g.ramp(dist, -0.0004, 0.0004, 1.0, 0.0).mul(g.ramp(nx, 0.85, 0.95));
        const rim = g.ramp(abs(dist), 0.0, 0.0016, 1.0, 0.0).mul(g.ramp(nx, 0.85, 0.95));
        S.C = g.mixc(hole, S.C, [0.008, 0.008, 0.009]);
        S.R = g.mixf(hole, S.R, 0.9);
        S.M = g.mixf(hole, S.M, 0.0);
        S.R = g.mixf(rim.mul(0.6), S.R, 0.22);
        S.H = g.add(S.H, hole.mul(-0.0025));
    }
    const POST = {
        fork_wear: (levels) => (S, X) => {
            uprightHoles(S, X);
            const z = X.P.z;
            let band = g.ramp(z, 0.02, 0.5, 1.0, 0.0);
            for (const lv of levels) band = max(band, g.ramp(z, lv - 0.02, lv + 0.05).mul(g.ramp(z, lv + 0.1, lv + 0.42, 1.0, 0.0)));
            const hit = band.mul(g.ramp(g.noise(X.P, 150.0, 3.0, 0.65).mul(0.6).add(g.noise(X.P, 21.0, 2.0, 0.5).mul(0.55)), 0.52, 0.66));
            const bare = band.mul(g.ramp(g.noise(X.P, 44.0, 3.0, 0.6), 0.60, 0.68));
            S.C = g.mixc(hit, S.C, [0.33, 0.34, 0.35]);
            S.C = g.mixc(bare, S.C, [0.56, 0.57, 0.58]);
            S.R = g.mixf(hit, S.R, 0.6);
            S.R = g.mixf(bare, S.R, 0.34);
            S.M = g.mixf(bare, S.M, 1.0);
        },
        roller_wear: () => (S, X) => {
            const P = X.P;
            const rings = g.noise(vec3(P.x.mul(420.0), P.y.mul(5.0), P.z.mul(5.0)), 1.0, 2.0, 0.5);
            const band = g.ramp(abs(P.x), 0.30, 0.41, 1.0, 0.0);
            S.R = g.add(S.R, g.ramp(rings, 0.2, 0.8, -0.07, 0.09));
            S.R = g.sub(S.R, band.mul(0.05));
            S.C = num(S.C).mul(g.ramp(band, 0.0, 1.0, 0.93, 1.05, false));
            S.H = g.add(S.H, rings.mul(0.00001));
        },
        tread: () => (S, X) => {
            const [u, v] = [X.uv.x, X.uv.y];
            const a = sin(u.add(v).mul(2.0 * Math.PI / 0.036)), b = sin(u.sub(v).mul(2.0 * Math.PI / 0.036));
            const lo = g.ramp(a.mul(b), 0.55, 0.8);
            S.H = g.add(S.H, lo.mul(0.0016));
            S.R = g.mixf(lo, S.R, num(S.R).mul(0.6));
            S.C = num(S.C).mul(g.ramp(lo, 0.0, 1.0, 0.92, 1.12, false));
        },
        hand_edge: () => (S, X) => {
            const front = g.ramp(X.P.y, -0.23, -0.12, 1.0, 0.0).mul(g.ramp(X.n_mid, 0.2, 0.8, 0.5, 1.0));
            S.R = g.mixf(front.mul(0.7), S.R, 0.16);
            S.C = num(S.C).mul(g.ramp(front, 0.0, 1.0, 1.0, 1.10, false));
        },
        hazard: () => (S) => {
            const band = g.ramp(abs(g.fract(PW.x.add(PW.y).add(PW.z).mul(1.0 / 0.14)).sub(0.5)), 0.245, 0.255);
            const paint = isNum(S.M) ? 1.0 : float(1.0).sub(clamp(num(S.M).mul(4.0), 0.0, 1.0));
            S.C = g.mixc(band.mul(paint), S.C, HAZARD_BLACK);
        },
        dado: () => (S, X) => {
            const { x, y, z } = { x: PW.x, y: PW.y, z: PW.z };
            const drift = g.noise(vec3(x.add(y).mul(0.9), z.mul(0.18), 3.0), 1.0, 3.0, 0.6);
            S.C = num(S.C).mul(g.ramp(drift, 0.25, 0.75, 0.90, 1.08));
            const foot = g.ramp(z, 0.02, 0.32, 1.0, 0.0).mul(g.ramp(X.n_mid, 0.2, 0.8, 0.45, 1.0));
            const marks = g.ramp(g.noise(vec3(x.add(y).mul(1.3), z.mul(22.0), 0.0), 1.0, 2.0, 0.5), 0.62, 0.72).mul(g.ramp(z, 0.05, 0.6, 1.0, 0.0));
            S.C = g.mixc(foot.mul(0.5), S.C, [0.10, 0.095, 0.088]);
            S.C = g.mixc(marks.mul(0.6), S.C, [0.045, 0.043, 0.040]);
            S.R = g.add(S.R, foot.mul(0.1));
            S.R = g.mixf(marks.mul(0.7), S.R, 0.5);
        },
    };

    // ---------------------------------------------------------------------------------------- the layered kind
    // a scan under the layers of this file's head (the Blender edition's _mats.layered, its options the same)
    async function layered(name, o) {
        const { scan: scanId = null, res = '2k', tile = 0.6, tint = null, rough = 0.45, metal = 0.0, normal = 0.6, var: vari = 1.0, world_var = true,
            chips = null, polish = 0.0, dirt = 0.5, dirt_col = [0.055, 0.048, 0.040], dust = 0.3, dust_col = [0.50, 0.48, 0.45], scratches = 0.3,
            smudges = 0.3, spangle = 0.0, grain = 1.0, coat = 0.0, post = null, post_arg = null, rough_span = 1.0, uv_rot = 0.0, fine = 1.0 } = o;
        let uv = UV3;
        if (uv_rot) uv = g.rotz(uv, uv_rot);
        const P = OBJ, PV = world_var ? PW : P;
        const n_macro = g.noise(PV, 0.55, 3.0, 0.55), n_mid = g.noise(P, 11.0, 3.0, 0.6), n_fine = g.noise(P, 130.0, 2.0, 0.6);
        const S = {};
        let nrm = null;
        if (scanId) {
            const sc = await scan(scanId, res);
            const suv = g.scale(uv, 1.0 / tile);
            const c0 = g.img(sc.color, suv).rgb;
            S.C = tint ? c0.mul(vec3(...tint.map((t, i) => t / Math.max(sc.mean[i], 1e-3)))) : c0;
            const r0 = sc.rough ? g.img(sc.rough, suv).x : float(sc.rmean);
            S.R = g.madd(r0.sub(sc.rmean), rough_span * rough / Math.max(sc.rmean, 0.05), rough);
            nrm = (sc.normal && normal) ? g.normalMap(g.img(sc.normal, suv), normal) : null;
            S.M = (metal === 'map' && sc.metal) ? g.img(sc.metal, suv).x : (metal === 'map' ? 1.0 : metal);
        } else { S.C = tint || [0.5, 0.5, 0.5]; S.R = rough; S.M = metal; }
        S.H = 0.0;
        const wear = attribute('wear', 'float'), cav = attribute('cavity', 'float');
        if (vari) {                                                    // 2 large-scale variation
            S.C = num(S.C).mul(g.ramp(n_macro, 0.25, 0.75, 1.0 - 0.07 * vari, 1.0 + 0.07 * vari));
            S.R = g.add(S.R, g.ramp(n_macro, 0.2, 0.8, -0.05 * vari, 0.05 * vari));
        }
        if (spangle) {                                                 // zinc crystals, each its own brightness and sheen
            const cv = g.voronoiColor(P, 62.0, 1.0).x;
            S.C = num(S.C).mul(g.ramp(cv, 0.0, 1.0, 1.0 - 0.16 * spangle, 1.0 + 0.10 * spangle, false));
            S.R = g.add(S.R, g.ramp(cv, 0.0, 1.0, -0.07 * spangle, 0.09 * spangle, false));
            const bloom = g.ramp(g.noise(PV, 2.3, 4.0, 0.65), 0.52, 0.75).mul(0.5 * spangle);
            S.C = g.mixc(bloom, S.C, [0.62, 0.63, 0.64]);
            S.R = g.mixf(bloom, S.R, 0.72);
            S.M = isNum(S.M) ? g.mixf(bloom, S.M, 0.55 * S.M) : g.mixf(bloom, S.M, 0.55);
        }
        if (smudges) {                                                 // 3 roughness breakup
            const sm = g.img(await gen('smudges'), g.scale(uv, 1.0 / (0.45 * fine))).x;
            S.R = g.add(S.R, g.ramp(sm, 0.0, 1.0, -0.10 * smudges, 0.16 * smudges, false));
        }
        if (scratches) {
            const sr = g.img(await gen('scratches'), g.scale(g.rotz(uv, 0.7), 1.0 / (0.52 * fine))).x;
            S.R = g.add(S.R, sr.mul(0.30 * scratches));
            S.C = num(S.C).mul(g.ramp(sr, 0.0, 1.0, 1.0, 1.0 + 0.22 * scratches, false));
            S.H = sr.mul(-0.00004 * scratches);
        }
        if (grain) S.R = g.add(S.R, g.ramp(n_fine, 0.25, 0.75, -0.035 * grain, 0.035 * grain));
        const weff = wear.mul(g.ramp(cav, 0.25, 0.7, 1.0, 0.0));        // 4 edge wear, kept out of crevices
        if (chips) {
            const a = chips.amount ?? 0.5;
            const cn = g.noise(P, 260.0, 3.0, 0.65).mul(0.6).add(g.noise(P, 37.0, 2.0, 0.5).mul(0.55));
            let x = weff.mul(g.ramp(cn, 0.25, 0.85, 0.15, 1.25, false));
            const dings = g.ramp(g.noise(P, 70.0, 4.0, 0.7), 0.74 - 0.05 * a, 0.78 - 0.05 * a).mul(0.9 * Math.min(1.0, a * 1.4));
            x = max(x, dings);
            const t1 = 1.02 - 0.5 * a;
            const pm = g.ramp(x, t1 - 0.22, t1 - 0.16), mm = g.ramp(x, t1 - 0.05, t1 + 0.01);
            S.C = g.mixc(pm, S.C, chips.primer || [0.33, 0.34, 0.35]);
            S.C = g.mixc(mm, S.C, chips.metal || [0.56, 0.57, 0.58]);
            S.R = g.mixf(pm, S.R, 0.62);
            S.R = g.mixf(mm, S.R, chips.metal_rough ?? 0.34);
            S.M = g.mixf(mm, S.M, 1.0);
            S.H = g.add(S.H, pm.add(mm).mul(-0.00006));
        }
        if (polish) {
            const pol = weff.mul(g.ramp(n_mid, 0.2, 0.8, 0.35, 1.0));
            S.R = g.mixf(pol.mul(polish), S.R, num(S.R).mul(0.55));
            S.C = num(S.C).mul(g.ramp(pol, 0.0, 1.0, 1.0, 1.0 + 0.22 * polish, false));
        }
        if (dirt) {                                                    // 5 grime where the surface is closed in
            const dm = g.ramp(cav, 0.12, 0.8).mul(g.ramp(n_mid, 0.15, 0.85, 0.3, 1.0)).mul(Math.min(1.0, dirt));
            S.C = g.mixc(dm.mul(0.8), S.C, dirt_col);
            S.R = g.mixf(dm, S.R, 0.82);
            S.M = g.mixf(dm.mul(0.8), S.M, 0.0);
        }
        if (dust) {                                                    // 6 dust on what faces up
            const up = pow(clamp(NWh.z, 0.0, 1.0), 3.0).mul(g.ramp(g.noise(PV, 4.5, 3.0, 0.6), 0.2, 0.8, 0.35, 1.0)).mul(dust);
            S.C = g.mixc(up.mul(0.55), S.C, dust_col);
            S.R = g.mixf(up.mul(0.8), S.R, 0.9);
            S.M = g.mixf(up.mul(0.5), S.M, 0.0);
        }
        if (post) POST[post](post_arg)(S, { P, PV, uv, wear: weff, cav, n_mid, n_fine, n_macro });
        S.R = max(min(num(S.R), 0.97), 0.045);
        S.H = g.add(S.H, g.noise(P, 900.0, 2.0, 0.5).mul(0.000012 * grain));
        nrm = g.bump(S.H, 1.0, 1.0, nrm);
        return principled(name, S.C, S.R, S.M, nrm, coat ? { coat, coatRough: 0.08 } : {});
    }

    // ---------------------------------------------------------------------------------------- the floor
    // polished concrete: the scan read twice at scales that never agree (3 m and 4.1 m, turned), each slab a pour of
    // its own, saw-cut joints, lanes that traffic has polished and marked, dust and a grime line where no sweeper
    // reaches under the racks, tyre arcs at the dock, a sealer coat; everything in WORLD metres from the layout
    async function floorMat(name, L, { racks_x, lanes }, joints = 6.0) {
        const s4 = await scan('Concrete034', '4k');
        const P = PW, x = P.x, y = P.y;
        const uva = P.mul(1.0 / 3.0), uvb = g.rotz(P, 0.61).mul(1.0 / 4.1).add(vec3(0.37, 0.11, 0.0));
        const blend = g.ramp(g.noise(P, 0.23, 2.0, 0.5), 0.38, 0.62);
        const k = 0.31 / Math.max((s4.mean[0] + s4.mean[1] + s4.mean[2]) / 3, 1e-3);
        let c = mix(g.img(s4.color, uva).rgb, g.img(s4.color, uvb).rgb, blend).mul(k);
        const r0 = mix(g.img(s4.rough, uva).x, g.img(s4.rough, uvb).x, blend);
        const jx = x.sub(3.0).mul(1.0 / joints), jy = y.sub(3.0).mul(1.0 / joints);
        const cell = vec3(floor(jx), floor(jy), 0.0);
        const slab = g.white(cell), slab2 = g.white(cell.add(vec3(17.0, 5.0, 0.0)));
        c = c.mul(g.ramp(slab, 0.0, 1.0, 0.89, 1.10, false));
        c = c.mul(g.ramp(g.noise(P, 0.05, 2.0, 0.5), 0.3, 0.7, 0.90, 1.10));
        c = c.mul(g.ramp(g.noise(P, 0.42, 3.0, 0.6), 0.25, 0.75, 0.93, 1.06));
        let R = r0.sub(s4.rmean).mul(0.55).add(0.21);
        R = R.add(g.ramp(g.noise(P, 1.3, 3.0, 0.6), 0.25, 0.75, -0.05, 0.06));
        R = R.add(g.ramp(slab2, 0.0, 1.0, -0.05, 0.07, false));
        const dx = abs(g.fract(jx).sub(0.5)).mul(joints), dy = abs(g.fract(jy).sub(0.5)).mul(joints);
        const dj = float(joints / 2.0).sub(max(dx, dy));
        const jm = g.ramp(dj, 0.0032, 0.0048, 1.0, 0.0);
        const spall = g.ramp(dj, 0.0045, 0.016, 1.0, 0.0).mul(g.ramp(g.noise(P, 70.0, 3.0, 0.7), 0.56, 0.68));
        const jh = g.ramp(dj, 0.004, 0.085, 1.0, 0.0).mul(g.ramp(g.noise(P, 5.0, 3.0, 0.6), 0.3, 0.8, 0.25, 1.0));
        const margin = g.ramp(dj, 0.05, 0.45, 1.0, 0.0);
        let lane = null;
        for (const [cx, half] of lanes.fixed) { const m = g.ramp(abs(x.sub(cx)), half * 0.45, half, 1.0, 0.0); lane = lane ? max(lane, m) : m; }
        if (lanes.periodic) {
            const [x0, pitch, half, xMax] = lanes.periodic;
            const dper = abs(g.fract(x.sub(x0).mul(1.0 / pitch).add(0.5)).sub(0.5)).mul(pitch);
            lane = max(lane, g.ramp(dper, half * 0.45, half, 1.0, 0.0).mul(g.ramp(x, xMax - 0.2, xMax + 0.2, 1.0, 0.0)));
        }
        for (const [cx0, cx1, cy, half] of lanes.cross || []) {
            lane = max(lane, g.ramp(abs(y.sub(cy)), half * 0.45, half, 1.0, 0.0).mul(g.ramp(x, cx0 - 1.0, cx0 + 1.0).mul(g.ramp(x, cx1 - 1.0, cx1 + 1.0, 1.0, 0.0))));
        }
        const edge = g.ramp(lane, 0.02, 0.35).mul(g.ramp(lane, 0.35, 0.9, 1.0, 0.0));
        const streak = g.noise(vec3(x.mul(5.0), y.mul(0.11), 0.0), 1.0, 3.0, 0.6);
        const lm = lane.mul(g.ramp(streak, 0.2, 0.8, 0.45, 1.0));
        const xw = x.add(sin(y.mul(0.31)).mul(0.55));
        let wheel = max(g.ramp(g.noise(vec3(x.mul(19.0), y.mul(0.03), 7.0), 1.0, 2.0, 0.5), 0.66, 0.74),
            g.ramp(g.noise(vec3(xw.mul(13.0), y.mul(0.045), 23.0), 1.0, 2.0, 0.5), 0.70, 0.77));
        wheel = wheel.mul(lane).mul(g.ramp(g.noise(P, 0.45, 2.0, 0.5), 0.38, 0.66));
        let under = null, foot = null, scrape = null;
        for (const [a, b, faces] of racks_x) {
            const u = g.ramp(x, a - 0.04, a + 0.04).mul(g.ramp(x, b - 0.04, b + 0.04, 1.0, 0.0));
            under = under ? max(under, u) : u;
            for (const fx of faces) {
                const dfx = abs(x.sub(fx));
                const f = g.ramp(dfx, 0.015, 0.10, 1.0, 0.0), s = g.ramp(dfx, 0.10, 0.75, 1.0, 0.0);
                foot = foot ? max(foot, f) : f;
                scrape = scrape ? max(scrape, s) : s;
            }
        }
        foot = foot.mul(g.ramp(g.noise(vec3(x.mul(9.0), y.mul(1.7), 3.0), 1.0, 3.0, 0.6), 0.25, 0.8, 0.25, 1.0));
        scrape = scrape.mul(g.ramp(under, 0.0, 0.5, 1.0, 0.0)).mul(g.ramp(g.noise(vec3(x.mul(1.1), y.mul(46.0), 11.0), 1.0, 2.0, 0.5), 0.63, 0.72)
            .mul(g.ramp(g.noise(P, 1.9, 2.0, 0.5), 0.42, 0.62)));
        const dk = L.dock;
        const cdoor = vec3((dk.door_x[0] + dk.door_x[1]) / 2, dk.wall_y + 5.0, 0.0);
        const rad = P.sub(cdoor).length();
        let arcs = g.ramp(g.noise(vec3(rad.mul(7.5), x.add(y).mul(0.09), 2.0), 1.0, 2.0, 0.5), 0.66, 0.74);
        arcs = arcs.mul(g.ramp(y, dk.wall_y - 11.0, dk.wall_y - 3.5)).mul(g.ramp(g.noise(P, 0.8, 2.0, 0.5), 0.36, 0.62));
        arcs = arcs.mul(g.ramp(under, 0.0, 0.5, 1.0, 0.0));
        const scr = g.img(await gen('scratches_fine'), g.rotz(P, 0.33).mul(1.0 / 1.45)).x;
        c = g.mixc(margin.mul(0.10), c, c.mul(1.12));
        c = g.mixc(lm.mul(0.55), c, c.mul(0.78));
        c = g.mixc(edge.mul(0.30), c, [0.36, 0.35, 0.33]);
        c = g.mixc(wheel.mul(0.62), c, [0.035, 0.033, 0.030]);
        c = g.mixc(under.mul(0.38), c, [0.40, 0.385, 0.36]);
        c = g.mixc(foot.mul(0.62), c, [0.075, 0.068, 0.060]);
        c = g.mixc(scrape.mul(0.55), c, [0.50, 0.49, 0.47]);
        c = g.mixc(arcs.mul(0.68), c, [0.032, 0.030, 0.028]);
        c = g.mixc(jh.mul(0.36), c, c.mul(0.68));
        c = g.mixc(spall.mul(0.7), c, c.mul(0.45));
        c = g.mixc(jm, c, [0.060, 0.060, 0.062]);
        R = R.sub(lm.mul(0.10)).add(edge.mul(0.16)).add(scr.mul(0.18).mul(g.ramp(lane, 0.0, 1.0, 0.35, 1.0))).add(wheel.mul(0.24)).add(under.mul(0.30))
            .add(foot.mul(0.36)).add(scrape.mul(0.34)).add(arcs.mul(0.26)).add(jh.mul(0.14)).add(margin.mul(0.05));
        R = g.mixf(spall, R, 0.8);
        R = g.mixf(jm, R, 0.62);
        R = max(min(R, 0.95), 0.07);
        let nrm = g.normalMap(g.img(s4.normal, uva), 0.32, 'OBJECT');
        const H = jm.mul(-0.0026).add(spall.mul(-0.0018)).add(g.noise(P, 760.0, 2.0, 0.5).mul(0.00005));
        nrm = g.bump(H, 1.0, 1.0, nrm);
        const coat = g.ramp(under, 0.0, 1.0, 0.36, 0.06).mul(g.ramp(max(jm, spall), 0.0, 1.0, 1.0, 0.0)).mul(g.ramp(edge.add(scrape), 0.0, 1.0, 1.0, 0.45));
        const coatR = float(0.085).add(scr.mul(0.10)).add(wheel.mul(0.2));
        return principled(name, c, R, 0.0, nrm, { coat, coatRough: coatR });
    }

    // the painted floor lines: a traffic paint worn through to the concrete in patches (the same scan at the same world
    // place as the floor under it, so a worn patch IS the floor). The mesh's UV: u = metres in from the line's nearer
    // edge (0 on both edges), v = metres along the line
    async function floorPaint(name, { colour = [0.70, 0.71, 0.70], stripes = null }) {
        const s4 = await scan('Concrete034', '4k');
        const P = PW, x = P.x, y = P.y;
        const k = 0.31 / Math.max((s4.mean[0] + s4.mean[1] + s4.mean[2]) / 3, 1e-3);
        const conc = g.img(s4.color, P.mul(1.0 / 3.0)).rgb.mul(k);
        const u = UV3.x, v = UV3.y;
        const fine = g.noise(P, 55.0, 3.0, 0.6);
        const ragged = g.ramp(u.add(fine.sub(0.5).mul(0.014)), 0.0005, 0.0035);
        const thin = g.ramp(u, 0.0, 0.02, 0.35, 0.0);
        const ride = g.noise(vec3(u.mul(70.0), v.mul(0.9), 5.0), 1.0, 3.0, 0.6);
        const crossN = g.noise(vec3(v.mul(2.3), 0.0, 9.0), 1.0, 2.0, 0.5);
        const wn = g.noise(P, 6.0, 4.0, 0.7).mul(0.45).add(fine.mul(0.30)).add(ride.mul(0.35).add(thin));
        const worn = g.ramp(wn.add(g.ramp(crossN, 0.5, 0.75).mul(0.32)), 0.74, 0.84);
        const scuff = g.ramp(g.noise(vec3(x.mul(14.0), y.mul(0.5), 0.0), 1.0, 3.0, 0.6), 0.45, 0.8);
        const rubber = g.ramp(g.noise(vec3(u.mul(6.0), v.mul(31.0), 3.0), 1.0, 2.0, 0.5), 0.68, 0.76).mul(g.ramp(crossN, 0.45, 0.7));
        let paint = vec3(...colour).mul(g.ramp(scuff, 0.0, 1.0, 1.0, 0.76));
        if (stripes) {
            const sb = g.ramp(abs(g.fract(x.add(y).mul(1.0 / stripes)).sub(0.5)), 0.245, 0.255);
            paint = g.mixc(sb, paint, [0.03, 0.03, 0.032]);
        }
        paint = g.mixc(rubber.mul(0.7), paint, [0.04, 0.04, 0.04]);
        const gone = max(worn, float(1.0).sub(ragged));
        const c = g.mixc(gone, paint, conc);
        const R = g.mixf(gone, float(0.40).add(scuff.mul(0.2)).add(rubber.mul(0.2)), 0.24);
        return principled(name, c, R, 0.0, g.bump(gone.mul(-0.0004), 1.0));
    }

    // profiled steel liner sheets, the hall's inner skin above the concrete dado (the ribs are geometry; the UV is
    // metres along the wall and height): every sheet its own tone, the side laps, the horizontal lap at lap_v with the
    // weep runs under its fixings, a scuffed band over the dado, a slow drift
    async function wallLiner(name, { sheet = 1.0, lap_v = 7.6, scuff = true, value = 0.72 }) {
        const sc = await scan('Metal049A', '2k');
        const u = UV3.x, v = UV3.y, P = PW;
        const uv = UV3.mul(1.0 / 0.9);
        const k = [1.0, 1.01, 1.015].map((t, i) => value * t / Math.max(sc.mean[i], 1e-3));
        let c = g.img(sc.color, uv).rgb.mul(vec3(...k));
        let R = g.img(sc.rough, uv).x.sub(sc.rmean).mul(0.8).add(0.40);
        const upper = g.ramp(v, lap_v - 0.001, lap_v + 0.001, 0.0, 1.0, false);
        const tone = g.white(vec3(floor(u.mul(1.0 / sheet)), upper, 0.0));
        c = c.mul(g.ramp(tone, 0.0, 1.0, 0.955, 1.035, false));
        c = c.mul(g.ramp(g.noise(P, 0.045, 2.0, 0.5), 0.3, 0.7, 0.93, 1.05));
        let side = abs(g.fract(u.mul(1.0 / sheet)).sub(0.5)).mul(sheet);
        side = g.ramp(float(sheet / 2.0).sub(side), 0.0008, 0.0022, 1.0, 0.0);
        const lap = g.ramp(abs(v.sub(lap_v)), 0.0015, 0.004, 1.0, 0.0);
        const lapSh = g.ramp(float(lap_v).sub(v), 0.0, 0.035, 1.0, 0.0).mul(g.ramp(v, lap_v - 0.036, lap_v, 0.0, 1.0, false));
        const runs = g.ramp(g.noise(vec3(u.mul(11.0), v.mul(0.22), 0.0), 1.0, 3.0, 0.6), 0.56, 0.82).mul(g.ramp(v, lap_v - 3.2, lap_v, 0.0, 1.0).mul(g.ramp(v, lap_v, lap_v + 0.01, 1.0, 0.0)));
        const low = g.ramp(v, 2.4, 3.3, scuff ? 1.0 : 0.0, 0.0).mul(g.ramp(g.noise(vec3(u.mul(2.2), v.mul(2.2), 1.0), 1.0, 4.0, 0.65), 0.3, 0.75, 0.15, 1.0));
        const sm = g.img(await gen('smudges'), UV3.mul(1.0 / 1.7)).x;
        c = g.mixc(runs.mul(0.13), c, [0.22, 0.21, 0.19]);
        c = g.mixc(low.mul(0.30), c, [0.30, 0.29, 0.27]);
        c = g.mixc(lapSh.mul(0.25), c, c.mul(0.6));
        c = g.mixc(max(side, lap), c, c.mul(0.32));
        R = R.add(low.mul(0.2).add(runs.mul(0.14)));
        R = R.add(g.ramp(sm, 0.0, 1.0, -0.07, 0.10, false));
        R = R.add(g.ramp(g.noise(P, 0.6, 3.0, 0.6), 0.2, 0.8, -0.05, 0.05));
        const H = max(side, lap).mul(-0.0012).add(g.noise(P, 700.0, 2.0, 0.5).mul(0.00001));
        return principled(name, c, max(min(R, 0.95), 0.12), 0.0, g.bump(H, 1.0, 1.0, g.normalMap(g.img(sc.normal, uv), 0.25)));
    }

    // the open ground beyond the yard's fence: dry verge grass seen at a grazing angle from far away
    async function field(name) {
        const sa = await scan('Asphalt012', '2k');
        const P = PW;
        const c0 = g.img(sa.color, P.mul(1.0 / 5.0)).rgb;
        let c = c0.mul(vec3(...[0.19, 0.17, 0.075].map((t, i) => t / Math.max(sa.mean[i], 1e-3))));
        const patch = g.noise(P, 0.035, 4.0, 0.6);
        c = g.mixc(g.ramp(patch, 0.35, 0.7), c, c.mul(0.62));
        c = g.mixc(g.ramp(g.noise(P, 0.4, 3.0, 0.7), 0.55, 0.8), c, [0.24, 0.20, 0.11]);
        return principled(name, c, float(0.82).add(patch.mul(0.12)), 0.0, g.normalMap(g.img(sa.normal, P.mul(1.0 / 5.0)), 1.5, 'OBJECT'));
    }

    // the dock's apron: a broom-finished concrete yard in slabs of 5 m, the trucks' wheel lanes worn dark
    async function yard(name) {
        const sc = await scan('Concrete034', '2k'), sa = await scan('Asphalt012', '2k');
        const P = PW, x = P.x, y = P.y;
        const uv = P.mul(1.0 / 3.7);
        const k = 0.27 / Math.max((sc.mean[0] + sc.mean[1] + sc.mean[2]) / 3, 1e-3);
        let c = g.img(sc.color, uv).rgb.mul(k);
        c = c.mul(g.ramp(g.noise(P, 0.06, 3.0, 0.6), 0.25, 0.75, 0.85, 1.12));
        const cell = vec3(floor(x.mul(1.0 / 5.0)), floor(y.mul(1.0 / 5.0)), 0.0);
        c = c.mul(g.ramp(g.white(cell), 0.0, 1.0, 0.92, 1.08, false));
        const dx = abs(g.fract(x.mul(1.0 / 5.0)).sub(0.5)).mul(5.0), dy = abs(g.fract(y.mul(1.0 / 5.0)).sub(0.5)).mul(5.0);
        const jm = g.ramp(float(2.5).sub(max(dx, dy)), 0.006, 0.012, 1.0, 0.0);
        const lanes = g.ramp(g.noise(vec3(x.mul(0.55), y.mul(0.02), 4.0), 1.0, 3.0, 0.6), 0.5, 0.72).mul(g.ramp(g.noise(P, 0.4, 3.0, 0.6), 0.3, 0.7, 0.3, 1.0));
        c = g.mixc(lanes.mul(0.5), c, g.img(sa.color, P.mul(1.0 / 2.6)).rgb.mul(1.3));
        c = g.mixc(jm, c, c.mul(0.3));
        const R = g.img(sc.rough, uv).x.sub(sc.rmean).mul(0.6).add(0.78).add(lanes.mul(-0.12));
        const nrm = g.normalMap(g.img(sc.normal, uv), 1.0, 'OBJECT');
        return principled(name, c, clamp(R, 0.0, 1.0), 0.0, g.bump(jm.mul(-0.004), 1.0, 1.0, nrm));
    }

    // a lamp's diffuser: it glows (the light itself is an area light beside it); falloff: the Object axis (0 or 1) and
    // the half width across which an opal lens dims toward its edges
    function emitter(name, { colour, strength, body = [0.9, 0.9, 0.9], falloff = null }) {
        let e = float(strength);
        if (falloff) e = g.ramp(abs(falloff[0] === 0 ? OBJ.x : OBJ.y), falloff[1] * 0.35, falloff[1], 1.0, 0.72).mul(strength);
        return principled(name, body, 0.35, 0.0, null, { emission: vec3(...colour).mul(e) });
    }

    // the office window: frosted glass lit from behind, the slats of a blind as faint bands, uneven where the lamp is
    function frosted(name, { colour, strength }) {
        const P = PW, y = P.y, z = P.z;
        const slat = g.ramp(sin(z.mul(2.0 * Math.PI / 0.05)), -0.2, 0.6, 0.80, 1.0);
        const pool = g.ramp(g.noise(vec3(y.mul(0.35), z.mul(0.5), 0.0), 1.0, 2.0, 0.5), 0.2, 0.8, 0.55, 1.15);
        const e = slat.mul(pool).mul(strength);
        const R = float(0.5).add(g.noise(P, 40.0, 3.0, 0.6).mul(0.2));
        const c = g.mixc(g.ramp(g.noise(vec3(y.mul(3.0), z.mul(0.6), 0.0), 1.0, 3.0, 0.6), 0.3, 0.7), [0.74, 0.73, 0.70], [0.80, 0.79, 0.76]);
        return principled(name, c, R, 0.0, g.bump(g.noise(P, 300.0, 2.0, 0.5), 0.00008), { emission: vec3(...colour).mul(e) });
    }

    // the meter's window: a thin pane, smudged
    async function glass(name) {
        const sm = g.img(await gen('smudges'), OBJ.mul(1.0 / 0.25)).x;
        const m = principled(name, [0.92, 0.96, 0.95], float(0.03).add(sm.mul(0.06)), 0.0, null, { transmission: 1.0, ior: 1.5 });
        return m;
    }

    // the layout's flat colours (look: false)
    function flatColour(name, s) {
        const m = new T.MeshStandardNodeMaterial({ color: new T.Color(...s.rgb), roughness: s.rough, metalness: s.metal });
        if (s.emit) { m.emissive = new T.Color(...s.emit); m.emissiveIntensity = s.strength; }
        m.name = name;
        m.side = T.DoubleSide;
        return m;
    }

    const made = new Map();
    async function material(name, spec, L = null) {
        if (made.has(name)) return made.get(name);
        let m;
        if (flat || !spec) m = flatColour(name, spec || { rgb: [0.6, 0.6, 0.6], rough: 0.5, metal: 0.0 });
        else if (spec.kind === 'layered') m = await layered(name, spec);
        else if (spec.kind === 'floor') m = await floorMat(name, L, spec);
        else if (spec.kind === 'floor_paint') m = await floorPaint(name, spec);
        else if (spec.kind === 'wall_liner') m = await wallLiner(name, spec);
        else if (spec.kind === 'field') m = await field(name);
        else if (spec.kind === 'yard') m = await yard(name);
        else if (spec.kind === 'emitter') m = emitter(name, spec);
        else if (spec.kind === 'frosted') m = frosted(name, spec);
        else if (spec.kind === 'glass') m = await glass(name);
        else if (spec.rgb) m = flatColour(name, spec);
        else throw new Error(`hall mats: ${name}: no kind ${spec.kind}`);
        made.set(name, m);
        return m;
    }

    return {
        material, made, textures: texCache, gens,
        // the hall's root (its matrixWorld) for the materials' world metres: call after moving or turning it
        setFrame(group) { group.updateMatrixWorld(true); hallMat.value.copy(group.matrixWorld); hallInv.value.copy(group.matrixWorld).invert(); },
        dispose() { for (const m of made.values()) m.dispose(); for (const t of texCache.values()) t.dispose(); for (const t of gens.values()) t.dispose(); },
    };
}
