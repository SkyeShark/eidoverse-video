// eidoverse/sets/town/look.js — the town's materials, by name, in TSL: a port of eidoblend.sets.town.materials.
//
//   const look = await makeLook(THREE, { strikes, paved, sandReach, signs, clay });
//   look.material('plaster')   -> a MeshStandardNodeMaterial (made once; 'awn:3', 'shutter:2', 'sign_board:5' ...)
//
// Every surface is a CC0 photograph at its real size (cc0_sets.json: the sets by ID, fetched into the shared library on
// first use by fetchPBR; their real sizes and measured means), read live in the shader and driven by masks from the
// geometry: no unique bakes for a town of instanced buildings.
// - MAPPING: box projection in the OBJECT's own metres (the geometry's own position, before its placing), at the
//   set's tile size. Each placing shifts its projection sideways by its own random number (forty copies of one mesh are
//   forty different walls); heights are never shifted.
// - COLOUR: a set's colour map divided by its own mean, so its grain stays and its average becomes the building's own
//   tint (sand, peach, bone, ochre; a grey render; a blue, pink or green house in twenty).
// - LAYERS, in the order things happen: base, broad variation, runs from every ledge (tlE), splash at the foot, grime
//   in the inside corners (tlE), with damage the strike's marks (pocks, spalls, soot over the burnt openings: tlS), and
//   dust on what faces up and drifted against what stands (tlB); the roads' wheel paths, oil, patches, cracks, gutters
//   and litter in their lane frame (tlS), and toward each street's end the asphalt under the very track and plain it
//   meets (trackSurface, groundPlain: the same functions in the same metres, so there is no seam).
// - The noise is MaterialX's Perlin (three's mx_noise_float), the same lattice noise Blender's Noise Texture draws;
//   fBm as Blender sums it. Voronoi, white noise and the per-placing number are this module's own hashes.
// Every per-placing number reaches the shader as the instanced attribute 'inst' (random, how near a strike, 1 on the
// town's ground and streets); every per-face mask as 'tlE', 'tlB', 'tlS' (masks.js).
// Albedos stay in the range of real things: plaster at most about 0.5, dust pale beside asphalt, never white. No bump:
// the sets' displacement maps are not read (from 20 m up the relief they carry is under a pixel).

const HERE = new URL('./', import.meta.url);
export const REG = JSON.parse(Deno.readTextFileSync(new URL('cc0_sets.json', HERE))).sets;
export const DUST = [0.37, 0.315, 0.23];                             // what lies on everything here
export const PALE = [0.40, 0.375, 0.335];                            // a strike's fall: pale beside asphalt, not white
export const SOOT = [0.016, 0.014, 0.012];
// THE PLASTERS (linear albedo): sand, peach, bone and ochre, a grey render, and one house in twenty blue, pink or green
const PLASTER = [[0.42, 0.33, 0.21], [0.46, 0.36, 0.23], [0.39, 0.30, 0.19], [0.47, 0.32, 0.23], [0.44, 0.33, 0.26], [0.50, 0.46, 0.37],
    [0.40, 0.28, 0.16], [0.43, 0.34, 0.22], [0.53, 0.49, 0.40], [0.44, 0.41, 0.35], [0.45, 0.31, 0.18], [0.49, 0.35, 0.26],
    [0.36, 0.30, 0.22], [0.41, 0.31, 0.21], [0.48, 0.44, 0.36], [0.37, 0.39, 0.39], [0.44, 0.35, 0.24], [0.46, 0.40, 0.31],
    [0.50, 0.37, 0.34], [0.38, 0.29, 0.18], [0.45, 0.37, 0.25], [0.43, 0.32, 0.19], [0.42, 0.36, 0.28], [0.47, 0.38, 0.24]];
const CARS = [[0.60, 0.60, 0.58], [0.62, 0.62, 0.60], [0.58, 0.58, 0.56], [0.40, 0.40, 0.39], [0.45, 0.40, 0.30], [0.22, 0.05, 0.04], [0.05, 0.09, 0.18],
    [0.035, 0.035, 0.035], [0.50, 0.50, 0.47], [0.10, 0.16, 0.11], [0.55, 0.42, 0.10], [0.61, 0.61, 0.60]];
// the small things: [colour, roughness, metal, dust]
export const PLAIN = {
    glass: [[0.012, 0.016, 0.02], 0.08, 0.0, 0.10], void: [[0.004, 0.004, 0.004], 1.0, 0.0, null], soot: [[0.012, 0.011, 0.010], 1.0, 0.0, null],
    frame_alu: [[0.42, 0.42, 0.40], 0.45, 0.0, 0.15], frame_white: [[0.52, 0.51, 0.47], 0.5, 0.0, 0.15], frame_wood: [[0.16, 0.09, 0.05], 0.6, 0.0, 0.15],
    door_green: [[0.07, 0.15, 0.11], 0.5, 0.0, 0.2], door_blue: [[0.08, 0.15, 0.24], 0.5, 0.0, 0.2], door_brown: [[0.14, 0.08, 0.05], 0.5, 0.0, 0.2],
    door_grey: [[0.20, 0.21, 0.21], 0.5, 0.0, 0.2], door_rust: [[0.19, 0.09, 0.05], 0.75, 0.0, 0.2],
    in_blue: [[0.30, 0.40, 0.43], 0.9, 0.0, 0.2], in_green: [[0.36, 0.44, 0.34], 0.9, 0.0, 0.2], in_white: [[0.56, 0.54, 0.48], 0.9, 0.0, 0.2],
    in_pink: [[0.52, 0.38, 0.35], 0.9, 0.0, 0.2], in_cream: [[0.55, 0.48, 0.34], 0.9, 0.0, 0.2], ceiling: [[0.50, 0.49, 0.45], 0.9, 0.0, 0.0],
    tank_white: [[0.60, 0.60, 0.56], 0.5, 0.0, 0.2], tank_black: [[0.025, 0.025, 0.028], 0.5, 0.0, 0.25], tank_blue: [[0.06, 0.16, 0.36], 0.5, 0.0, 0.2],
    tank_red: [[0.30, 0.07, 0.04], 0.7, 0.0, 0.2], tank_cap: [[0.03, 0.03, 0.03], 0.6, 0.0, 0.1],
    zinc: [[0.50, 0.52, 0.52], 0.42, 1.0, 0.2], zinc_old: [[0.36, 0.36, 0.34], 0.6, 0.6, 0.25], rust: [[0.17, 0.075, 0.035], 0.9, 0.0, 0.15],
    steel_dark: [[0.05, 0.05, 0.05], 0.6, 0.6, 0.2], steel_paint: [[0.12, 0.13, 0.12], 0.55, 0.0, 0.2], rebar: [[0.10, 0.055, 0.035], 0.9, 0.0, 0.15],
    cooler: [[0.56, 0.56, 0.52], 0.5, 0.0, 0.2], cooler_pad: [[0.20, 0.17, 0.11], 0.95, 0.0, 0.1], ac: [[0.58, 0.58, 0.54], 0.5, 0.0, 0.2],
    ac_fan: [[0.03, 0.03, 0.03], 0.7, 0.0, 0.1], dish: [[0.55, 0.55, 0.52], 0.45, 0.0, 0.2], dish_dark: [[0.06, 0.06, 0.06], 0.5, 0.0, 0.25],
    solar: [[0.015, 0.02, 0.05], 0.12, 0.0, 0.15], plastic_white: [[0.60, 0.60, 0.57], 0.45, 0.0, 0.15], plastic_blue: [[0.05, 0.14, 0.33], 0.45, 0.0, 0.15],
    plastic_red: [[0.36, 0.04, 0.03], 0.45, 0.0, 0.15], mattress: [[0.42, 0.38, 0.33], 0.95, 0.0, 0.15], wood: [[0.20, 0.13, 0.07], 0.8, 0.0, 0.2],
    wood_pale: [[0.36, 0.27, 0.16], 0.8, 0.0, 0.2], cardboard: [[0.33, 0.24, 0.13], 0.9, 0.0, 0.1],
    tyre: [[0.018, 0.018, 0.018], 0.85, 0.0, 0.2], hub: [[0.30, 0.30, 0.30], 0.45, 0.8, 0.2], bumper: [[0.03, 0.03, 0.03], 0.6, 0.0, 0.2],
    lamp_red: [[0.30, 0.02, 0.015], 0.3, 0.0, 0.1], lamp_clear: [[0.55, 0.55, 0.50], 0.2, 0.0, 0.1], car_glass: [[0.035, 0.04, 0.045], 0.1, 0.0, null],
    car_in: [[0.03, 0.03, 0.03], 0.9, 0.0, null], car_burnt: [[0.035, 0.026, 0.02], 0.95, 0.0, 0.25], car_bed: [[0.10, 0.10, 0.10], 0.6, 0.3, 0.3],
    frond: [[0.085, 0.14, 0.05], 0.55, 0.0, 0.0], frond_old: [[0.16, 0.17, 0.07], 0.6, 0.0, 0.0], frond_dead: [[0.26, 0.19, 0.10], 0.9, 0.0, 0.0],
    dates: [[0.42, 0.24, 0.05], 0.6, 0.0, 0.0], leaf: [[0.07, 0.12, 0.045], 0.6, 0.0, 0.0], leaf_dry: [[0.14, 0.15, 0.07], 0.7, 0.0, 0.0],
    wire: [[0.012, 0.012, 0.012], 0.8, 0.0, null], insulator: [[0.30, 0.20, 0.15], 0.3, 0.0, 0.0], lamp_head: [[0.42, 0.42, 0.40], 0.4, 0.5, 0.2],
    cloth0: [[0.66, 0.66, 0.62], 0.95, 0.0, 0.0], cloth1: [[0.45, 0.06, 0.05], 0.95, 0.0, 0.0], cloth2: [[0.07, 0.17, 0.42], 0.95, 0.0, 0.0],
    cloth3: [[0.62, 0.48, 0.10], 0.95, 0.0, 0.0], cloth4: [[0.10, 0.32, 0.17], 0.95, 0.0, 0.0], cloth5: [[0.03, 0.03, 0.035], 0.95, 0.0, 0.0],
    cloth6: [[0.52, 0.22, 0.36], 0.95, 0.0, 0.0], cloth7: [[0.20, 0.42, 0.50], 0.95, 0.0, 0.0], cloth8: [[0.50, 0.24, 0.07], 0.95, 0.0, 0.0],
    tarp_blue: [[0.05, 0.16, 0.40], 0.6, 0.0, 0.3], tarp_sand: [[0.42, 0.33, 0.18], 0.9, 0.0, 0.3], tarp_green: [[0.10, 0.20, 0.12], 0.8, 0.0, 0.3],
    tarp_white: [[0.58, 0.57, 0.52], 0.8, 0.0, 0.3], tarp_red: [[0.42, 0.07, 0.05], 0.8, 0.0, 0.3],
    fruit_orange: [[0.60, 0.25, 0.03], 0.6, 0.0, 0.0], fruit_red: [[0.45, 0.04, 0.03], 0.6, 0.0, 0.0], fruit_green: [[0.16, 0.34, 0.06], 0.6, 0.0, 0.0],
    fruit_yellow: [[0.62, 0.50, 0.08], 0.6, 0.0, 0.0], crate: [[0.05, 0.12, 0.30], 0.6, 0.0, 0.1], sack: [[0.50, 0.46, 0.38], 0.95, 0.0, 0.1],
    bike_red: [[0.40, 0.03, 0.03], 0.4, 0.0, 0.05], bike_blue: [[0.04, 0.14, 0.40], 0.4, 0.0, 0.05], chrome: [[0.6, 0.6, 0.6], 0.25, 1.0, 0.1],
    dome: [[0.07, 0.30, 0.27], 0.35, 0.0, 0.12], dome_blue: [[0.05, 0.15, 0.36], 0.35, 0.0, 0.12], gold: [[0.60, 0.42, 0.12], 0.35, 1.0, 0.05],
    tile_band: [[0.06, 0.20, 0.30], 0.3, 0.0, 0.1], speaker: [[0.40, 0.41, 0.40], 0.5, 0.0, 0.2],
    barrel_blue: [[0.04, 0.12, 0.28], 0.55, 0.0, 0.2], barrel_rust: [[0.20, 0.09, 0.04], 0.9, 0.0, 0.15],
};
const PLANTS = ['frond', 'frond_old', 'frond_dead', 'dates', 'leaf', 'leaf_dry', 'trunk', 'palm_trunk'];
// a shop's painted sign board when it carries no picture (linear albedo), and the ink of words set on it
export const BOARDS = [[[0.30, 0.05, 0.04], [0.62, 0.60, 0.55]], [[0.05, 0.12, 0.28], [0.62, 0.60, 0.55]], [[0.07, 0.20, 0.10], [0.60, 0.58, 0.50]],
    [[0.56, 0.54, 0.48], [0.30, 0.05, 0.04]], [[0.58, 0.46, 0.08], [0.04, 0.04, 0.04]], [[0.04, 0.04, 0.045], [0.60, 0.50, 0.10]],
    [[0.50, 0.48, 0.42], [0.05, 0.12, 0.28]], [[0.40, 0.14, 0.05], [0.60, 0.58, 0.52]]];

// ==================================================================================================== the node layer
function kit(THREE) {
    const T = THREE;
    const { float, vec2, vec3, vec4, abs, clamp, mix, max, min, select, smoothstep, texture, dot, normalize, floor, fract, sin, exp,
        length, mx_noise_float, attribute } = T;
    const num = (x) => (typeof x === 'number' ? float(x) : Array.isArray(x) ? vec3(x[0], x[1], x[2]) : x);
    const P0 = attribute('position', 'vec3');                        // the point in the object's own metres (+Z up)
    const N0 = normalize(attribute('normal', 'vec3'));               // its normal there
    const inst = attribute('inst', 'vec4');                          // (random, how near a strike, 1 on the ground/streets, 0)
    const rnd = inst.x;
    const X = P0.x, Y = P0.y, Z = P0.z;
    const nz = N0.z;
    const sm = (x, lo, hi) => smoothstep(num(lo), num(hi), num(x));   // Map Range, smoothstep, clamped
    const inv = (x) => float(1.0).sub(num(x));
    const lin = (x, a0, a1, b0, b1) => num(b0).add(num(x).sub(a0).div(num(a1).sub(a0)).mul(num(b1).sub(b0)));
    const mixf = (f, a, b) => mix(num(a), num(b), clamp(num(f), 0.0, 1.0));
    const mixc = (f, a, b) => mix(num(a), num(b), clamp(num(f), 0.0, 1.0));
    const value = (c, v) => num(c).mul(num(v));
    const rnd2 = (k) => fract(rnd.add(0.137 * k).mul(7.919 + 3.1 * k));
    const Ps = P0.add(vec3(rnd.mul(613.0), rnd.mul(377.0), 0.0));     // slid sideways by the placing's number; heights kept
    const wall = inv(sm(abs(nz), 0.3, 0.55));
    const up = (lo = 0.55, hi = 0.92) => sm(nz, lo, hi);
    const along = mix(X, Y, sm(abs(N0.x), 0.5, 0.6));                // x on a face that looks along y, y on one along x
    // Blender's Noise Texture of a vector: fBm of Perlin noise, normalized 0..1, lacunarity 2; off / stretch: a Mapping
    function noise(p, scale, detail = 2.0, { off = null, stretch = null, rough = 0.5 } = {}) {
        let q = num(p);
        if (stretch) q = q.mul(vec3(...stretch));
        if (off) q = q.add(vec3(...off));
        q = q.mul(scale);
        let sum = null, amp = 1.0, maxamp = 0.0, fs = 1.0;
        const oct = Math.floor(detail);
        for (let i = 0; i <= oct; i++) {
            const n = mx_noise_float(fs === 1.0 ? q : q.mul(fs)).mul(amp);
            sum = sum ? sum.add(n) : n;
            maxamp += amp; amp *= rough; fs *= 2.0;
        }
        let v = sum.div(maxamp).mul(0.5).add(0.5);
        const rmd = detail - oct;
        if (rmd > 1e-6) {
            const s2 = sum.add(mx_noise_float(q.mul(fs)).mul(amp));
            v = mix(v, s2.div(maxamp + amp).mul(0.5).add(0.5), rmd);
        }
        return v;
    }
    // hashes: a float in 0..1 from a vector (white noise), and a cell's random 2D point and colour
    const h1 = (p) => fract(sin(dot(num(p), vec3(12.9898, 78.233, 37.719))).mul(43758.5453));
    const h2 = (c) => vec2(fract(sin(dot(c, vec2(127.1, 311.7))).mul(43758.5453)), fract(sin(dot(c, vec2(269.5, 183.3))).mul(43758.5453)));
    const h3 = (c) => vec3(fract(sin(dot(c, vec2(419.2, 371.9))).mul(43758.5453)), fract(sin(dot(c, vec2(113.5, 271.9))).mul(43758.5453)),
        fract(sin(dot(c, vec2(331.7, 117.3))).mul(43758.5453)));
    const wnoise = (p) => h1(p);
    // Blender's Voronoi, 2D, Euclidean: { d: F1 distance, color: the nearest cell's random colour, edge: distance to the
    // nearest cell edge }, at `scale` cells a unit
    function vor(p, scale, rand = 1.0, wantEdge = false) {
        const q = num(p).xy.mul(scale);
        const cell = floor(q), f = fract(q);
        let best = null, bestId = null, bestR = null;
        for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
            const g = vec2(i, j), id = cell.add(g);
            const r = g.add(h2(id).mul(rand)).sub(f);
            const d = length(r);
            if (best === null) { best = d; bestId = id; bestR = r; }
            else {
                const closer = d.lessThan(best);
                best = select(closer, d, best); bestId = select(closer, id, bestId); bestR = select(closer, r, bestR);
            }
        }
        let edge = null;
        if (wantEdge) {
            for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
                const g = vec2(i, j), id = cell.add(g);
                const r = g.add(h2(id).mul(rand)).sub(f);
                const dd = r.sub(bestR);
                const e = select(dot(dd, dd).greaterThan(1e-5), dot(bestR.add(r).mul(0.5), normalize(dd)), float(8.0));
                edge = edge === null ? e : min(edge, e);
            }
        }
        return { d: best, color: h3(bestId), edge };
    }
    // a constant colour ramp (CONSTANT interpolation, its stops evenly at k / n)
    function palette(fac, colors) {
        const n = colors.length;
        const idx = clamp(floor(num(fac).mul(n)), 0.0, n - 1);
        let c = vec3(...colors[0]);
        for (let k = 1; k < n; k++) c = select(idx.greaterThanEqual(k), vec3(...colors[k]), c);
        return c;
    }
    // Blender's BOX projection of a picture at `co` (texture space) by the object-space normal, blended across `blend`
    function boxWeights(n, blend) {
        const a = abs(n), nn = a.div(a.x.add(a.y).add(a.z));
        const limit = 0.5 + 0.5 * blend;
        const w0 = clamp(nn.div(vec3(nn.x.add(nn.y), nn.y.add(nn.z), nn.x.add(nn.z))).sub(0.5 * (1.0 - blend)).div(Math.max(1e-8, blend)), 0.0, 1.0);
        const wA = vec3(w0.x, inv(w0.x), 0.0), wB = vec3(0.0, w0.y, inv(w0.y)), wC = vec3(inv(w0.z), 0.0, w0.z);
        const wD = nn.mul(2.0 - limit).add(limit - 1.0).div(Math.max(1e-8, 2.0 * limit - 1.0));
        return select(nn.z.lessThan(nn.y.add(nn.x).mul(1.0 - limit)), wA,
            select(nn.x.lessThan(nn.y.add(nn.z).mul(1.0 - limit)), wB,
                select(nn.y.lessThan(nn.x.add(nn.z).mul(1.0 - limit)), wC, wD)));
    }
    function boxAt(tex, co, blend) {
        const w = boxWeights(N0, blend);
        const ux = vec2(select(N0.x.lessThan(0.0), inv(co.y), co.y), co.z);
        const uy = vec2(select(N0.y.greaterThan(0.0), inv(co.x), co.x), co.z);
        const uz = vec2(select(N0.z.greaterThan(0.0), inv(co.y), co.y), co.x);
        return texture(tex, ux).mul(w.x).add(texture(tex, uy).mul(w.y)).add(texture(tex, uz).mul(w.z));
    }
    return { T, float, vec2, vec3, vec4, num, P0, N0, inst, rnd, X, Y, Z, nz, sm, inv, lin, mixf, mixc, value, rnd2, Ps, wall, up, along,
        noise, wnoise, vor, palette, boxAt, max, min, abs, clamp, mix, fract, floor, exp, select, dot, texture };
}

// ==================================================================================================== the look
export async function makeLook(THREE, { strikes = [], paved = [450, 160], sandReach = [34, 12], signs = [], clay = false, res = null, log = console.log } = {}) {
    const k = kit(THREE);
    const { float, vec3, num, P0, X, Y, Z, nz, sm, inv, lin, mixf, mixc, value, rnd2, Ps, wall, up, along, noise, wnoise, vor, palette,
        boxAt, max, min, abs, fract, floor, texture, inst, rnd, vec2 } = k;
    const texCache = new Map();
    const files = new Map();
    const tex = async (key, kind) => {                               // one map of a set: 'col' | 'rough' (null when absent)
        const s = REG[key];
        const r_ = res || s.res;
        if (!files.has(key)) files.set(key, (await globalThis.fetchPBR(s.id, { res: r_ })).files);
        const f = files.get(key)[{ col: 'diff', rough: 'rough', disp: 'displacement' }[kind]];
        if (!f) return null;
        const ck = `${f}|${kind}`;
        if (!texCache.has(ck)) texCache.set(ck, await globalThis.loadImageTexture(Deno.readFileSync(f), { srgb: kind === 'col' }));
        return texCache.get(ck);
    };
    // load every set the families read, up front (the node builders below are synchronous)
    const T = {};
    for (const key of Object.keys(REG)) {
        T[key] = { col: await tex(key, 'col') };
        if (['render_sand', 'block', 'brick', 'concrete', 'concrete_smooth', 'asphalt', 'pavers'].includes(key)) T[key].rough = await tex(key, 'rough');
    }
    T.pavers.disp = await tex('pavers', 'disp');                      // (the pavers' joints are read off their relief)
    log(`[town] look: ${texCache.size} CC0 maps read`);
    // a set's colour divided by its own mean (the photograph's grain about 1); k: how much of its contrast
    const ncol = (key, vec, proj = 'BOX', kk = 1.0, scale = 1.0, blend = 0.22) => {
        const s = REG[key];
        const w = s.tile[0] * scale, h = s.tile[1] * scale;
        const t = T[key].col;
        const c = proj === 'BOX' ? boxAt(t, num(vec).mul(vec3(1 / w, 1 / w, 1 / h)), blend) : texture(t, num(vec).xy.mul(vec2(1 / w, 1 / h)));
        let n = c.rgb.div(vec3(...s.mean.map((v) => Math.max(1e-3, v))));
        if (kk !== 1.0) n = n.mul(kk).add(1.0 - kk);
        return n;
    };
    const rough = (key, vec, proj = 'BOX', lo = 0.55, hi = 1.0, scale = 1.0) => {
        const s = REG[key], t = T[key].rough;
        if (!t) return float((lo + hi) / 2.0);
        const w = s.tile[0] * scale, h = s.tile[1] * scale;
        const r = proj === 'BOX' ? boxAt(t, num(vec).mul(vec3(1 / w, 1 / w, 1 / h)), 0.22).x : texture(t, num(vec).xy.mul(vec2(1 / w, 1 / h))).x;
        return lin(r, 0.0, 1.0, lo, hi);
    };
    const tint = (n, rgb) => min(num(n).mul(num(rgb)), vec3(0.82, 0.82, 0.82));
    // ------------------------------------------------------------------------------------------- masks by cause
    const tlE = THREE.attribute('tlE', 'vec4'), tlB = THREE.attribute('tlB', 'vec4'), tlS = THREE.attribute('tlS', 'vec4');
    // the per-face numbers of the materials several names share (slot(): a colour, a roughness, a kind ...)
    const tmA = THREE.attribute('tmA', 'vec4'), tmB = THREE.attribute('tmB', 'vec4');
    const isKind = (k) => k.sub(tmB.x).abs().lessThan(0.5);
    // on the town's own ground: how thick a strike's fall lies here (0 in an intact town)
    const strikeField = () => {
        let best = null;
        for (const [sx, sy, sr] of strikes) {
            const d = vec2(X.sub(sx), Y.sub(sy)).length();
            const kk = inv(sm(d, sr * 0.25, sr * 1.35));
            best = best === null ? kk : max(best, kk);
        }
        if (best === null) return float(0.0);
        const n = noise(P0, 0.11, 3.0, { off: [13.0, 5.0, 0.0] });
        return sm(best.add(n.sub(0.5).mul(0.5)), 0.15, 0.9);
    };
    const near = max(inst.y, inst.z.mul(strikeField()));
    // what rain carried over every ledge and down the wall under it: runs from the ledge's edge (tlE.x) fading within a
    // metre or two, each its own length; and right under the ledge the band the rain never washed
    const drips = (strength = 1.0) => {
        const d = tlE.x.sub(Z);
        const streak = sm(noise(vec3(along, Z.mul(0.11), rnd.mul(31.0)), 4.2, 3.0), 0.42, 0.64);
        const reach = float(0.45).add(noise(vec3(along.mul(0.45), rnd.mul(7.0), 0.0), 1.3, 2.0).mul(2.2));
        const fall = inv(sm(d, 0.0, reach));
        const under = inv(sm(d, 0.0, float(0.06).add(noise(vec3(along.mul(2.0), 0.0, 0.0), 1.0, 2.0).mul(0.16))));
        const gate = sm(d, -0.04, 0.0);
        const kk = float(0.45).add(rnd2(3).mul(0.55)).mul(strength);
        return k.clamp(max(streak.mul(fall), under.mul(0.55)).mul(gate).mul(wall).mul(kk), 0.0, 1.0);
    };
    // the street's dirt thrown up a wall's foot, ragged at its top
    const splash = (height = 1.0) => {
        const top = float(height * 0.5).add(noise(vec3(along.mul(1.3), Z, 0.0), 1.0, 2.0).mul(height * 0.9));
        return inv(sm(Z, 0.03, top)).mul(wall);
    };
    // grime against an inside corner (tlE: the face's extent along the wall and which of its ends is a corner)
    const cornerGrime = () => {
        const fl = tlE.w;
        const c1 = floor(fl.div(2.0)), c0 = fl.sub(c1.mul(2.0));
        const d0 = along.sub(tlE.y).mul(c0).add(inv(c0).mul(100.0));
        const d1 = tlE.z.sub(along).mul(c1).add(inv(c1).mul(100.0));
        const w = float(0.12).add(noise(vec3(along, Z.mul(0.5), 0.0), 2.0, 3.0).mul(0.42));
        return inv(sm(min(d0, d1), 0.0, w)).mul(wall);
    };
    // dust and grit blown against whatever stands at a flat face's edges (tlB: the face's own extent)
    const edgeDrift = () => {
        const e = min(min(X.sub(tlB.x), tlB.z.sub(X)), min(Y.sub(tlB.y), tlB.w.sub(Y)));
        const w = float(0.12).add(noise(P0, 0.9, 3.0, { off: [4.0, 1.0, 0.0] }).mul(0.75));
        return inv(sm(e, 0.02, w)).mul(sm(tlB.z.sub(tlB.x), 0.5, 0.8));
    };
    // soot over an opening whose room burned: it leaves the opening's head and climbs, widening, fading in 2-3 m
    const sootPlume = () => {
        const du = abs(along.sub(tlS.x)), dz = Z.sub(tlS.y);
        const wid = tlS.z.add(0.15).add(max(dz, 0.0).mul(0.5));
        const n = noise(vec3(along.mul(1.6), Z.mul(0.35), 3.0), 2.5, 3.0);
        const f = inv(sm(du.div(wid), 0.5, 1.1)).mul(sm(dz, -0.35, 0.1)).mul(inv(sm(dz, 0.8, float(2.8).add(n.mul(1.6)))));
        return k.clamp(f.mul(tlS.w).mul(float(0.7).add(n.mul(0.7))).mul(wall), 0.0, 1.0);
    };
    // what fragments and rounds leave in plaster or concrete: a dark hole and a paler ring, in clusters
    const pocks = (density, vec2_, cell = 0.16) => {
        const v = vor(vec2_, 1.0 / cell);
        const keep = sm(v.color.x, inv(density), inv(density).add(0.02));
        const r = float(0.10).add(v.color.y.mul(0.16));
        const hole = inv(sm(v.d, r.mul(0.55), r)).mul(keep);
        const halo = max(inv(sm(v.d, r, r.mul(2.3))).mul(keep).sub(hole), 0.0);
        return [hole, halo];
    };
    // what a street collects: scraps of paper, bags, cardboard, a bottle: each a cell of its own colour, a hand across
    const litter = (vec2_, density, col) => {
        const nzz = vec3(noise(vec2_, 9.0, 2.0), noise(vec2_, 9.0, 2.0, { off: [3.1, 7.7, 0.0] }), 0.0);
        const wv = num(vec2_).add(nzz.sub(0.5).mul(vec3(0.5, 0.5, 0.0)));
        const v = vor(wv.mul(vec3(1.0, 1.7, 1.0)), 1.0 / 0.42);
        const keep = sm(v.color.x, inv(density), inv(density).add(0.01));
        const blob = inv(sm(v.d, float(0.05).add(v.color.z.mul(0.08)), float(0.08).add(v.color.z.mul(0.1)))).mul(keep);
        const c = palette(v.color.y, [[0.52, 0.50, 0.45], [0.46, 0.44, 0.40], [0.06, 0.06, 0.07], [0.03, 0.03, 0.03], [0.36, 0.27, 0.16],
            [0.30, 0.10, 0.07], [0.50, 0.49, 0.46], [0.12, 0.16, 0.20]]);
        return mixc(blob.mul(0.85), col, c);
    };
    // dust on what faces up and a thin film on everything; near a strike, the paler fall -> [colour, roughness, dust]
    const dusted = (col, rgh, base = 0.06, up_k = 0.35, { P = Ps, color = null } = {}) => {
        const n1 = noise(P, 0.6, 3.0, { off: [2.0, 3.0, 1.0] }), n2 = noise(P, 5.0, 2.0, { off: [7.0, 1.0, 4.0] });
        const lay = num(base).add(near.mul(0.08)).add(up().mul(near.mul(0.18).add(up_k))).add(n1.sub(0.5).mul(0.36).add(n2.sub(0.5).mul(0.14)));
        const d = k.clamp(sm(lay, 0.22, 0.86).mul(0.88), 0.0, 1.0);
        let dc = color !== null ? num(color) : mixc(near.mul(0.6), DUST, PALE);
        dc = value(dc, float(0.92).add(n2.mul(0.16)));
        return [mixc(d, col, dc), mixf(d, rgh, 0.95), d];
    };
    // ------------------------------------------------------------------------------------------- the families
    const famPlaster = (base) => {
        const hit = base === 'plaster_dmg';
        // plaster, plaster_b (the second colour: tmB.x 1), plaster_w (the yard walls: 2, each stretch its own number)
        const r0 = hit ? rnd : k.select(isKind(float(2)), wnoise(vec3(floor(X.div(13.0)), floor(Y.div(9.0)), 0.0)), rnd);
        const tnt = palette(fract(r0.add(hit ? 0.0 : k.select(isKind(float(1)), float(0.37), float(0.0)))), PLASTER);
        const g_a = ncol('render_sand', Ps, 'BOX', 1.6), g_c = ncol('stucco', Ps, 'BOX', 1.2);
        const which = sm(fract(r0.mul(5.31)), 0.62, 0.64);           // a third of the houses are stuccoed
        let g = mixc(which, g_a, g_c);
        const g_w = ncol('plaster_worn', Ps, 'BOX', 0.6);
        const patch = sm(noise(Ps, 0.35, 3.0, { off: [3.0, 9.0, 1.0] }).add(rnd2(5).mul(!hit ? 0.16 : 0.34)), 0.64, 0.72);
        g = mixc(patch.mul(0.7), g, g_w);
        let col = tint(g, tnt);
        const mac = float(1.0).add(noise(Ps, 0.12, 3.0).sub(0.5).mul(0.16)).add(rnd2(7).sub(0.5).mul(0.10));
        col = value(col, mac);
        let rgh = rough('render_sand', Ps, 'BOX', 0.78, 0.98);
        const dr = drips(!hit ? 1.0 : 0.8);
        col = mixc(dr.mul(0.72), col, value(col, 0.5));
        col = mixc(dr.mul(0.35), col, vec3(0.20, 0.17, 0.13));
        col = mixc(splash(1.1).mul(0.55), col, value(mixc(0.5, DUST, col), 0.85));
        col = mixc(cornerGrime().mul(0.55), col, value(mixc(0.3, [0.20, 0.17, 0.13], col), 0.7));
        let hole = null, halo = null;
        if (strikes.length) {
            const dens = near.mul(hit ? 0.30 : 0.16).mul(sm(noise(Ps, 0.25, 2.0, { off: [5.0, 5.0, 5.0] }), 0.35, 0.65));
            [hole, halo] = pocks(dens, vec3(along, Z, r0.mul(50.0)));
        }
        if (hit) {
            const sp_ = sootPlume();
            const ns = noise(Ps, 1.5, 4.0, { off: [1.0, 2.0, 3.0], rough: 0.62 }).add(noise(Ps, 6.0, 2.0).sub(0.5).mul(0.16));
            const th = float(0.71).sub(near.mul(0.06)).sub(sm(sp_, 0.05, 0.45).mul(0.10));
            const spall = sm(ns, th, th.add(0.012));
            const rim = max(sm(ns, th.sub(0.03), th).sub(spall), 0.0);
            const blk = tint(ncol('block', Ps, 'BOX', 0.6), [0.34, 0.32, 0.29]);
            col = mixc(spall, col, value(blk, 0.92));
            col = mixc(rim.mul(0.7), col, value(mixc(0.5, col, [0.55, 0.53, 0.48]), 1.1));
            rgh = mixf(spall, rgh, 0.92);
            const sm_ = sm(noise(Ps, 0.16, 3.0, { off: [7.0, 2.0, 4.0] }), 0.55, 0.78).mul(0.45);
            col = mixc(sm_, col, value(col, 0.45));
            col = mixc(sp_, col, SOOT);
            rgh = mixf(sp_, rgh, 0.97);
        }
        if (hole !== null) {
            col = mixc(hole.mul(0.9), col, vec3(0.035, 0.032, 0.028));
            col = mixc(halo.mul(0.75), col, value(mixc(0.45, col, [0.56, 0.53, 0.47]), 1.08));
        }
        [col, rgh] = dusted(col, rgh, !hit ? 0.05 : 0.16, 0.42);
        return [col, rgh, 0.0];
    };
    const famMasonry = (base) => {
        const key = (base === 'block' || base === 'claustra') ? 'block' : 'brick';
        const g = ncol(key, Ps, 'BOX', key === 'block' ? 0.55 : 0.8);
        let col = tint(g, key === 'block' ? [0.335, 0.315, 0.285] : [0.43, 0.30, 0.17]);
        col = value(col, float(1.0).add(noise(Ps, 0.15, 3.0).sub(0.5).mul(0.18)).add(rnd2(2).sub(0.5).mul(0.12)));
        let rgh = rough(key, Ps, 'BOX', 0.8, 0.98);
        if (base === 'claustra') {                                   // pierced block: a dark opening in a pale frame (drawn)
            const fu = fract(along.div(0.2)), fz = fract(Z.div(0.2));
            const d = min(min(fu, inv(fu)), min(fz, inv(fz)));
            const hole = sm(d, 0.26, 0.30).mul(inv(sm(nz, 0.5, 0.7)));
            col = mixc(hole, value(col, 1.25), vec3(0.045, 0.04, 0.035));
        }
        const dr = drips(0.8);
        col = mixc(dr.mul(0.7), col, value(col, 0.55));
        col = mixc(splash(0.9).mul(0.5), col, value(mixc(0.5, DUST, col), 0.85));
        col = mixc(cornerGrime().mul(0.5), col, value(col, 0.68));
        if (strikes.length) {
            const [hole, halo] = pocks(near.mul(0.2), vec3(along, Z, rnd.mul(50.0)), 0.14);
            col = mixc(hole.mul(0.9), col, vec3(0.03, 0.028, 0.025));
            col = mixc(halo.mul(0.6), col, value(col, 1.2));
        }
        [col, rgh] = dusted(col, rgh, 0.08, 0.45);
        return [col, rgh, 0.0];
    };
    const famConcrete = (base) => {
        const broken = base === 'concrete_broken';
        const g = ncol('concrete', Ps, 'BOX', 0.85, broken ? 0.6 : 1.0);
        let col = tint(g, broken ? [0.34, 0.33, 0.30] : [0.30, 0.285, 0.26]);
        col = value(col, float(1.0).add(noise(Ps, 0.2, 3.0).sub(0.5).mul(0.16)).add(rnd2(4).sub(0.5).mul(0.1)));
        let rgh = rough('concrete', Ps, 'BOX', 0.72, 0.97);
        if (broken) {
            const gr = ncol('gravel', Ps, 'BOX', 0.8, 0.5);
            col = mixc(sm(noise(Ps, 3.0, 2.0), 0.4, 0.7).mul(0.5), col, tint(gr, [0.36, 0.34, 0.30]));
        } else {
            const dr = drips(0.8);
            col = mixc(dr.mul(0.75), col, value(col, 0.5));
            col = mixc(splash(0.8).mul(0.45), col, value(mixc(0.5, DUST, col), 0.85));
            col = mixc(cornerGrime().mul(0.5), col, value(col, 0.68));
        }
        [col, rgh] = dusted(col, rgh, !broken ? 0.08 : 0.14, 0.3, { color: mixc(near.mul(0.3), DUST, PALE) });
        return [col, rgh, 0.0];
    };
    const famRoof = (base) => {
        const dmg = base === 'roof_dmg';
        const g = ncol('concrete_smooth', Ps, 'BOX', 1.6);
        const tnt = palette(fract(rnd.mul(3.7)), [[0.33, 0.29, 0.22], [0.36, 0.32, 0.25], [0.30, 0.28, 0.24], [0.38, 0.33, 0.24], [0.34, 0.31, 0.27]]);
        let col = tint(g, tnt);
        col = value(col, float(1.0).add(noise(Ps, 0.25, 3.0).sub(0.5).mul(0.2)));
        // where water stood and dried: small, ragged, faint, a darker tide line at each edge
        const pn = noise(Ps, 1.1, 3.0, { off: [2.0, 9.0, 0.0], rough: 0.6 });
        const gate = sm(noise(Ps, 0.2, 2.0, { off: [4.0, 4.0, 0.0] }), 0.45, 0.6);
        const pond = sm(pn, 0.63, 0.70).mul(gate);
        const ring = max(sm(pn, 0.61, 0.63).sub(sm(pn, 0.63, 0.65)), 0.0).mul(gate);
        col = value(col, float(1.0).sub(pond.mul(0.10).add(ring.mul(0.14))));
        const tar = sm(noise(Ps, 0.17, 1.0, { off: [5.0, 1.0, 0.0] }), 0.70, 0.705).mul(sm(noise(Ps, 0.7, 3.0), 0.35, 0.5));
        col = mixc(tar.mul(0.85), col, vec3(0.03, 0.028, 0.026));
        const fx = fract(X.div(3.0));                                // the screed laid in strips 3 m wide, a joint between
        const jn = inv(sm(min(fx, inv(fx)), 0.0, 0.006));
        col = value(col, float(1.0).sub(jn.mul(0.2)));
        let rgh = mixf(tar, rough('concrete_smooth', Ps, 'BOX', 0.8, 0.97), 0.45);
        const dr = edgeDrift();
        [col, rgh] = dusted(col, rgh, !dmg ? 0.06 : 0.18, 0.12, { P: Ps.mul(3.2) });
        col = mixc(dr.mul(0.7), col, mixc(near.mul(0.6), DUST, PALE));
        if (dmg) {
            const rb = tint(ncol('gravel_ground', Ps, 'BOX', 0.9), [0.38, 0.36, 0.32]);
            col = mixc(sm(noise(Ps, 0.8, 3.0), 0.45, 0.6).mul(0.8), col, rb);
        }
        return [col, rgh, 0.0];
    };
    // the plain's grounds -> colour: one function, so a road's sanded end goes over into exactly the ground beside it
    const groundPlain = (P) => {
        const two = sm(noise(P, 1.0 / 30.0, 2.0, { off: [7.0, 2.0, 0.0] }), 0.3, 0.7);
        const c_s = mixc(two, ncol('sand', P, 'FLAT', 0.65), ncol('sand', P, 'FLAT', 0.65, 3.9));
        const c_d = mixc(two, ncol('dry_ground', P, 'FLAT', 0.75, 2.7), ncol('dry_ground', P, 'FLAT', 0.75));
        const c_g = ncol('gravel_ground', P, 'FLAT', 0.75);
        const c_w = ncol('dry_grass', P, 'FLAT', 0.9);
        const s1 = noise(P, 1.0 / 70.0, 3.0, { off: [3.0, 1.0, 0.0] }), s2 = noise(P, 1.0 / 26.0, 3.0, { off: [9.0, 4.0, 0.0] });
        const s3 = noise(P, 1.0 / 7.0, 2.0, { off: [1.0, 7.0, 0.0] });
        const w_d = sm(s1.add(s3.sub(0.5).mul(0.3)), 0.53, 0.60);
        const w_g = sm(s2.add(s3.sub(0.5).mul(0.3)), 0.57, 0.63);
        const w_w = sm(noise(P, 1.0 / 45.0, 3.0, { off: [6.0, 6.0, 0.0] }).add(s3.sub(0.5).mul(0.3)), 0.62, 0.68).mul(0.9);
        let g = mixc(w_d, c_s, c_d);
        g = mixc(w_g.mul(0.85), g, c_g);
        g = mixc(w_w, g, c_w);
        let tnt = mixc(sm(noise(P, 1.0 / 380.0, 3.0, { off: [31.0, 7.0, 0.0] }), 0.35, 0.65), [0.40, 0.335, 0.24], [0.35, 0.28, 0.19]);
        tnt = mixc(sm(noise(P, 1.0 / 130.0, 3.0, { off: [3.0, 17.0, 0.0] }), 0.5, 0.72).mul(0.6), tnt, [0.31, 0.27, 0.21]);
        let col = tint(g, tnt);
        col = value(col, float(0.9).add(noise(P, 1.0 / 900.0, 3.0, { off: [1.0, 2.0, 0.0] }).mul(0.22)));
        const scrub = sm(noise(P, 0.55, 2.0, { off: [9.0, 9.0, 0.0] }), 0.66, 0.74).mul(sm(noise(P, 0.018, 3.0, { off: [5.0, 2.0, 0.0] }), 0.52, 0.66));
        return mixc(scrub.mul(0.65), col, vec3(0.12, 0.12, 0.07));
    };
    // a track's packed gravel with two ruts where the wheels go (across: from its middle line)
    const trackSurface = (P, across) => {
        let col = tint(ncol('gravel_ground', P, 'FLAT', 0.85), [0.38, 0.32, 0.23]);
        col = value(col, float(0.9).add(noise(P, 0.08, 3.0).mul(0.22)));
        const rut = inv(sm(abs(abs(across).sub(0.82)), 0.08, 0.3));
        return mixc(rut.mul(0.5), col, value(col, 0.8));
    };
    // (across, half width, along) of a road's lane frame: tlS holds its middle line and half width; tmB.x 1: a street
    // along y (road:y, track:y)
    const laneFrame = () => { const isY = isKind(float(1)); return [k.select(isY, X, Y).sub(tlS.x), tlS.y, k.select(isY, Y, X)]; };
    const famGround = (base, arg) => {
        const P = P0;
        let col, rgh;
        if (base === 'ground') { col = groundPlain(P); rgh = 0.95; }
        else if (base === 'track') { col = trackSurface(P, laneFrame()[0]); rgh = 0.95; }
        else if (base === 'yard') {
            col = tint(ncol('dry_ground', P, 'FLAT', 0.85), [0.29, 0.24, 0.17]);
            col = value(col, float(0.9).add(noise(P, 0.08, 3.0).mul(0.22)));
            rgh = 0.95;
        } else {                                                     // fields: a crop in rows, or a dry bed
            const key = base === 'field' ? 'grass' : 'mud_cracked';
            col = tint(ncol(key, P, 'FLAT', 0.8), base === 'field' ? [0.10, 0.15, 0.055] : [0.30, 0.24, 0.16]);
            const fx = fract(X.div(0.75));
            const rows = sm(abs(fx.sub(0.5)), 0.18, 0.34);
            col = mixc(rows.mul(0.6), col, vec3(0.25, 0.20, 0.13));
            rgh = 0.93;
        }
        col = mixc(near.mul(0.42), col, value(PALE, float(0.9).add(noise(P, 2.0, 2.0).mul(0.2))));
        return [col, num(rgh), 0.0];
    };
    const famRoad = (base, arg) => {
        const P = P0;
        let col = tint(ncol('asphalt', P, 'FLAT', 0.8), [0.085, 0.082, 0.077]);
        col = value(col, float(0.86).add(noise(P, 0.025, 3.0, { off: [4.0, 4.0, 0.0] }).mul(0.28)));
        let rgh = rough('asphalt', P, 'FLAT', 0.75, 0.95);
        const [across, hw, alo] = laneFrame();
        const a_ = abs(across);
        const e = hw.sub(a_);                                        // from the kerb
        const mainR = sm(hw, 4.0, 4.5);                              // the 11 m road: a median, two lanes each way
        const lc = hw.mul(0.5).add(mainR.mul(0.3));
        const wp = min(abs(a_.sub(lc.sub(0.85))), abs(a_.sub(lc.add(0.85))));
        const stretch = vec3(alo.mul(0.08), across, 0.0);
        const wpath = inv(sm(wp, 0.12, 0.42)).mul(float(0.7).add(noise(stretch, 3.0, 2.0).mul(0.6)));
        col = mixc(wpath.mul(0.6), col, value(col, 0.78));
        rgh = mixf(wpath.mul(0.7), rgh, 0.62);
        const oil = inv(sm(abs(a_.sub(lc)), 0.04, 0.28)).mul(sm(noise(stretch, 6.0, 2.0), 0.45, 0.7));
        col = mixc(oil.mul(0.55), col, vec3(0.02, 0.019, 0.018));
        // patches: lane-square repairs, a thin sealant line round each, one cell in twenty-two
        const cu = floor(alo.div(4.5)), ca = floor(across.div(1.7));
        const pr = wnoise(vec3(cu, ca, 3.0));
        const fu = fract(alo.div(4.5)), fa = fract(across.div(1.7));
        const inside = sm(min(fu, inv(fu)), 0.03, 0.05).mul(sm(min(fa, inv(fa)), 0.05, 0.08));
        const patch = sm(pr, 0.955, 0.96).mul(inside);
        const seal = sm(pr, 0.955, 0.96).mul(sm(min(min(fu, inv(fu)), min(fa, inv(fa))), 0.0, 0.03).sub(inside));
        col = mixc(patch.mul(0.7), col, value(col, float(0.8).add(wnoise(vec3(cu, ca, 9.0)).mul(0.35))));
        col = mixc(max(seal, 0.0).mul(0.35), col, vec3(0.03, 0.03, 0.03));
        rgh = mixf(max(seal, 0.0).mul(0.5), rgh, 0.4);
        // alligator cracks in the wheel paths where the base is weak (the cells' edges: MaterialX's Worley, F2 - F1)
        const wl = THREE.mx_worley_noise_vec2(vec2(alo, across).mul(1.0 / 0.16), 1.0);
        const crack = inv(sm(wl.y.sub(wl.x).mul(0.16 * 0.5), 0.0, 0.035)).mul(wpath).mul(sm(noise(P, 1.0 / 7.0, 2.0, { off: [8.0, 3.0, 0.0] }), 0.55, 0.66));
        col = mixc(crack.mul(0.75), col, vec3(0.012, 0.012, 0.012));
        // dust: swept into the gutters, thin drifts across the lanes, the wheel paths driven clean
        const gut = inv(sm(e, 0.12, float(0.5).add(noise(vec3(alo.mul(0.15), 0.0, 0.0), 1.0, 2.0).mul(1.1))));
        const drift = sm(noise(vec3(alo.mul(0.04), across.mul(0.6), 0.0), 2.0, 3.0).add(noise(P, 0.06, 2.0).sub(0.5).mul(0.6)), 0.52, 0.85).mul(inv(wpath));
        const dl = max(gut.mul(0.85), drift.mul(0.35));
        const dc = value(mixc(near.mul(0.6), DUST, PALE), float(0.85).add(noise(P, 3.0, 2.0).mul(0.3)));
        col = mixc(dl, col, dc);
        rgh = mixf(dl, rgh, 0.95);
        col = litter(vec3(alo, across, 0.0), float(0.006).add(gut.mul(0.14)), col);
        // THE SAND OVER THE ASPHALT'S ENDS: toward its end the road lies under the very track and plain it meets, the
        // cover breaking into lobes and wind streaks going in, the wheel paths driven clear first. A field in the
        // town's metres, not per quad, so it runs on unbroken where a cross street meets a street
        const dx = float(paved[0]).sub(abs(X)), dy = float(paved[1]).sub(abs(Y));
        const lobe = noise(P, 1.0 / 16.0, 3.0, { off: [11.0, 5.0, 0.0] }).sub(0.5).mul(18.0);
        const rx = inv(sm(dx.add(lobe.mul(sm(dx, 0.0, 8.0))), 0.0, sandReach[0]));
        const ry = inv(sm(dy.add(lobe.mul(sm(dy, 0.0, 4.0).mul(0.4))), 0.0, sandReach[1]));
        const reach = max(rx, ry);
        const u_ = X.mul(0.8).add(Y.mul(0.6)), v_ = Y.mul(0.8).sub(X.mul(0.6));          // the wind from the north-west
        const streak = noise(vec3(u_, v_.mul(7.0), 0.0), 0.2, 3.0, { off: [3.0, 9.0, 0.0] });
        let cover = sm(reach.add(streak.sub(0.5).mul(0.6)), 0.3, 0.7);
        const clear = min(wpath, 1.0).mul(inv(sm(reach, 0.7, 0.98)).mul(0.75));
        cover = cover.mul(inv(clear));
        const c_tr = trackSurface(P, across), c_gr = groundPlain(P);
        const tw = hw.mul(0.7);                                      // the track is 0.7 of the road's width, on its middle
        const side = sm(a_, tw.sub(0.3), tw.add(0.3));
        col = mixc(cover, col, mixc(side, c_tr, c_gr));
        rgh = mixf(cover, rgh, 0.95);
        col = mixc(near.mul(0.42), col, value(PALE, float(0.85).add(noise(P, 1.5, 2.0).mul(0.3))));
        return [col, rgh, 0.0];
    };
    const famWalk = (base) => {
        const P = P0;
        if (base === 'median') {
            const dirt = tint(ncol('dirt', P, 'FLAT', 0.8), [0.20, 0.16, 0.11]);
            const side = tint(ncol('concrete', Ps, 'BOX', 0.8), [0.30, 0.285, 0.26]);
            let col = mixc(up(), side, dirt);
            let rgh = num(0.93);
            [col, rgh] = dusted(col, rgh, 0.1, 0.25);
            return [col, rgh, 0.0];
        }
        let col = tint(ncol('pavers', P, 'BOX', 0.4), [0.33, 0.305, 0.265]);
        col = value(col, float(0.9).add(noise(P, 0.2, 3.0).mul(0.2)));
        const ps = REG.pavers.tile;
        const d = boxAt(T.pavers.disp, P.mul(vec3(1 / ps[0], 1 / ps[0], 1 / ps[1])), 0.22).x;
        const joint = inv(sm(d, 0.18, 0.42));
        col = mixc(joint.mul(0.75), col, DUST);
        const stain = sm(noise(P, 0.6, 3.0, { off: [2.0, 2.0, 0.0] }), 0.66, 0.74).mul(0.4);
        col = mixc(stain, col, value(col, 0.6));
        let rgh = rough('pavers', P, 'BOX', 0.8, 0.97);
        [col, rgh] = dusted(col, rgh, 0.12, 0.18);
        col = litter(vec3(X, Y, 0.0), float(0.03), col);
        return [col, rgh, 0.0];
    };
    const famKerb = (base, arg) => {
        const g = ncol('concrete_smooth', Ps, 'BOX', 1.3);
        const stone = tint(g, [0.32, 0.31, 0.28]);
        const band = sm(fract(X.add(Y).div(1.6)), 0.48, 0.52);
        const paint = mixc(band, vec3(0.04, 0.04, 0.04), k.select(isKind(float(1)), vec3(0.58, 0.44, 0.05), vec3(0.55, 0.53, 0.47)));   // round the median: yellow
        const wear = sm(noise(Ps, 1.2, 4.0).add(up().mul(0.25)), 0.5, 0.62);
        let col = mixc(wear.mul(0.85), paint, stone);
        let rgh = mixf(wear, 0.6, 0.9);
        [col, rgh] = dusted(col, rgh, 0.14, 0.35);
        return [col, rgh, 0.0];
    };
    const famRubble = (base) => {
        if (base === 'crater') {
            let col = tint(ncol('burnt', Ps, 'BOX', 0.6), [0.11, 0.10, 0.09]);
            col = mixc(sm(noise(Ps, 1.0, 3.0), 0.5, 0.75).mul(0.5), col, PALE);
            return [col, num(0.95), 0.0];
        }
        const g = mixc(sm(noise(Ps, 1.2, 3.0), 0.4, 0.6), ncol('gravel_ground', Ps, 'BOX', 0.9), ncol('gravel', Ps, 'BOX', 0.8));
        let col = tint(g, base === 'rubble' ? [0.33, 0.31, 0.28] : [0.32, 0.30, 0.27]);
        col = value(col, float(0.85).add(noise(Ps, 0.5, 3.0).mul(0.3)));
        let rgh;
        [col, rgh] = dusted(col, num(0.93), 0.12, 0.22);
        return [col, rgh, 0.0];
    };
    const famInterior = (base) => {
        if (base === 'floor') {
            let col = tint(ncol('terrazzo', Ps, 'BOX', 0.55), [0.34, 0.31, 0.27]);
            let rgh;
            [col, rgh] = dusted(col, num(0.45), 0.16, 0.2);
            return [col, rgh, 0.0];
        }
        const rgb = tmA.xyz;                                         // (the room's paint: in_white, in_blue ... the ceiling)
        let col = tint(ncol('plaster_fine', Ps, 'BOX', 2.0), rgb);
        col = mixc(sm(noise(Ps, 0.5, 3.0), 0.6, 0.7).mul(0.6), col, tint(ncol('plaster_worn', Ps, 'BOX', 1.0), rgb));
        const sm_ = sm(noise(Ps, 0.3, 3.0, { off: [3.0, 3.0, 3.0] }), 0.45, 0.75).mul(near).mul(0.85);
        col = mixc(sm_, col, SOOT);
        let rgh;
        [col, rgh] = dusted(col, num(0.9), 0.06, 0.3);
        return [col, rgh, 0.0];
    };
    const famMosque = (base) => {
        if (base === 'mosque') {
            let col = tint(ncol('stucco', Ps, 'BOX', 1.1), [0.53, 0.49, 0.40]);
            const dr = drips(0.8);
            col = mixc(dr.mul(0.45), col, value(col, 0.6));
            col = mixc(splash(1.0).mul(0.45), col, value(mixc(0.5, DUST, col), 0.85));
            let rgh;
            [col, rgh] = dusted(col, num(0.88), 0.04, 0.4);
            return [col, rgh, 0.0];
        }
        if (base === 'gold') return [vec3(0.62, 0.45, 0.16), num(0.32), 1.0];
        // the dome's glazed tiles in their courses (tmA: the glaze and its roughness), each its own shade: the square
        // cells of Blender's Voronoi with no randomness, read straight off the grid
        const q = vec2(X.add(Y), Z).mul(1.0 / 0.11);
        const gq = abs(fract(q.add(0.5)).sub(0.5));
        const shade = fract(k.T.sin(k.dot(floor(q.add(0.5)), vec2(127.1, 311.7))).mul(43758.5453));
        let col = value(tmA.xyz, float(0.82).add(shade.mul(0.36)));
        const grout = inv(sm(float(0.5).sub(max(gq.x, gq.y)), 0.0, 0.05));
        col = mixc(grout.mul(0.8), col, vec3(0.30, 0.29, 0.26));
        let rgh;
        [col, rgh] = dusted(col, tmA.w, 0.04, 0.2);
        return [col, mixf(grout, rgh, 0.85), 0.0];
    };
    // painted steel (doors, gates, tanks, stands, coolers, a dish): tmA the paint and its roughness; tmB.x its dust,
    // tmB.y how much rust (low on the door, at its edges, in runs below)
    const famPaintMetal = () => {
        const rgb = tmA.xyz, rg = tmA.w, dust = tmB.x, amount = tmB.y;
        const g = ncol('metal', Ps, 'BOX', 1.0);
        const paint = tint(g.sub(1.0).mul(0.5).add(1.0), rgb);
        const rust = tint(ncol('rust', Ps, 'BOX', 0.9), [0.16, 0.07, 0.035]);
        const low = inv(sm(Z, 0.05, 0.6));
        const rmask = sm(noise(Ps, 2.2, 4.0, { rough: 0.65 }).add(low.mul(0.25)).add(amount.sub(0.2)), 0.66, 0.70);
        const runs = sm(noise(vec3(along.mul(6.0), Z.mul(0.4), 0.0), 3.0, 2.0), 0.55, 0.75).mul(wall.mul(amount));
        let col = mixc(rmask, paint, rust);
        col = mixc(runs.mul(0.35), col, value(rust, 1.2));
        let rgh = mixf(rmask, rg, 0.88);
        [col, rgh] = dusted(col, rgh, dust, 0.45);
        return [col, rgh, 0.0];
    };
    const famShutter = () => {
        let col = tint(ncol('shutter', Ps, 'BOX', 1.2), tmA.xyz);    // (tmA: the shutter's paint)
        const rust = tint(ncol('rust', Ps, 'BOX', 0.9), [0.16, 0.07, 0.035]);
        const rm = sm(noise(Ps, 1.5, 4.0).add(inv(sm(fract(Z.div(2.8)), 0.0, 0.5)).mul(0.2)), 0.68, 0.72);
        col = mixc(rm, col, rust);
        let rgh;
        [col, rgh] = dusted(col, mixf(rm, 0.5, 0.85), 0.16, 0.3);
        return [col, rgh, float(0.3).mul(inv(rm))];
    };
    const famZinc = (base) => {
        const old = base === 'zinc_old';
        const g = old ? ncol('corrugated', Ps, 'BOX', 0.9) : ncol('metal', Ps, 'BOX', 1.0).sub(1.0).mul(0.6).add(1.0);
        let col = tint(g, !old ? [0.48, 0.49, 0.48] : [0.40, 0.40, 0.38]);
        const rust = tint(ncol('rust', Ps, 'BOX', 0.9), [0.16, 0.07, 0.035]);
        const rm = sm(noise(Ps, 1.1, 4.0), old ? 0.62 : 0.72, old ? 0.66 : 0.75);
        col = mixc(rm, col, rust);
        let rgh, d;
        [col, rgh, d] = dusted(col, mixf(rm, !old ? 0.42 : 0.6, 0.85), 0.15, 0.45);
        return [col, rgh, inv(rm).mul(inv(d))];                      // (bare zinc is metal; rust and dust are not)
    };
    // canvas, tarps, washing, sacks, a mattress (tmB.x 0: tmA the cloth's colour); an awning's stripes a hand wide
    // (1: tmA and tmB.yzw the two colours); a carpet (2: tmA its ground)
    const famFabric = () => {
        const g = ncol('fabric', Ps, 'BOX', 0.7);
        const stripes = mixc(sm(fract(X.add(Y).div(0.36)), 0.47, 0.53), tmA.xyz, tmB.yzw);
        const rugc = value(tmA.xyz, float(0.62).add(noise(Ps, 2.2, 3.0).mul(0.76)));
        const rgb = k.select(isKind(float(1)), stripes, k.select(isKind(float(2)), rugc, tmA.xyz));
        let col = tint(g, rgb);
        const fade = up(0.3, 0.9).mul(0.35);
        col = mixc(fade, col, value(mixc(0.5, col, [0.6, 0.58, 0.52]), 1.05));
        let rgh;
        [col, rgh] = dusted(col, num(0.92), 0.05, 0.3);
        return [col, rgh, 0.0];
    };
    const famCar = (base) => {
        if (base === 'car_burnt') {
            const rust = tint(ncol('rust', Ps, 'BOX', 1.0), [0.12, 0.05, 0.025]);
            let col = mixc(sm(noise(Ps, 1.4, 4.0), 0.45, 0.6), value(rust, 0.25), rust);
            col = mixc(up().mul(0.6), col, vec3(0.30, 0.29, 0.27));
            return [col, num(0.92), 0.0];
        }
        const paint = palette(rnd, CARS);
        const low = inv(sm(Z, 0.15, 0.75));
        let col = mixc(low.mul(0.55), paint, value(mixc(0.5, DUST, paint), 0.85));
        let rgh;
        [col, rgh] = dusted(col, num(0.32), 0.06, 0.55);
        return [col, rgh, 0.0];
    };
    // plastic in the sun (tmA its colour and roughness, tmB.x its metal, tmB.y its dust): chalky on what faces up
    const famPlastic = () => {
        let col = value(tmA.xyz, float(0.94).add(noise(Ps, 1.5, 3.0).mul(0.12)));
        col = mixc(up(0.2, 0.9).mul(0.25), col, value(mixc(0.5, col, [0.62, 0.62, 0.6]), 1.0));
        let rgh;
        [col, rgh] = dusted(col, tmA.w, tmB.y, 0.5);
        return [col, rgh, tmB.x];
    };
    // wood (tmB.x 0) or cardboard (1), in tmA's colour
    const famWood = () => {
        const g = k.select(isKind(float(1)), ncol('cardboard', Ps, 'BOX', 0.6), ncol('wood', Ps, 'BOX', 0.6));
        let col = tint(g, tmA.xyz);
        let rgh;
        [col, rgh] = dusted(col, num(0.85), 0.12, 0.45);
        return [col, rgh, 0.0];
    };
    // the palms and the built yard trees: plain colours with a little noise (tmB.x 0, tmA the colour and roughness);
    // a trunk (1), a palm's ringed trunk (2)
    const plant = () => {
        const bark = value(tmA.xyz, float(1.0).add(noise(Ps, 0.06, 3.0).sub(0.5).mul(0.34)).add(noise(Ps, 0.7, 3.0).sub(0.5).mul(0.2).add(noise(Ps, 6.0, 2.0).sub(0.5).mul(0.1))));
        const ringed = value(bark, float(0.7).add(fract(Z.div(0.16)).mul(0.6)));
        const leaf = value(tmA.xyz, float(0.8).add(noise(P0, 1.7, 2.0).mul(0.4)));
        const col = k.select(isKind(float(2)), ringed, k.select(isKind(float(1)), bark, leaf));
        return [col, tmA.w, tmB.y];
    };
    // a painted sign board (tmA its paint)
    const board = () => {
        let col = value(tmA.xyz, float(0.9).add(noise(Ps, 1.4, 3.0).mul(0.2)));
        let rgh;
        [col, rgh] = dusted(col, num(0.6), 0.12, 0.3);
        return [col, rgh, 0.0];
    };
    // everything else small, in its colour (tmA: colour, roughness; tmB.x metal, tmB.y its dust, below 0 none; tmB.z
    // 1: a window, dusty)
    const plain = () => {
        let col = tmA.xyz, rgh = tmA.w;
        const [dc, dr] = dusted(col, rgh, max(tmB.y, 0.0), 0.4);
        const has = tmB.y.greaterThanEqual(0.0);
        col = k.select(has, dc, col); rgh = k.select(has, dr, rgh);
        col = mixc(tmB.z.mul(0.18), col, DUST); rgh = mixf(tmB.z.mul(0.18), rgh, 0.5);
        return [col, rgh, tmB.x];
    };
    // the materials by key: the families that draw one name each, and the ones many names share (their numbers per face)
    const FAM = {
        plaster: famPlaster, plaster_dmg: famPlaster, block: famMasonry, brick: famMasonry, claustra: famMasonry,
        concrete: famConcrete, concrete_broken: famConcrete, roof: famRoof, roof_dmg: famRoof,
        ground: famGround, yard: famGround, track: famGround, field: famGround, field_dry: famGround,
        road: famRoad, walk: famWalk, median: famWalk, kerb: famKerb, rubble: famRubble, crater: famRubble,
        floor: famInterior, inwall: famInterior, mosque: famMosque, gold: famMosque, tile: famMosque,
        shutter: famShutter, zinc: famZinc, zinc_old: famZinc, car: famCar, car_burnt: famCar,
        paint: famPaintMetal, plastic: famPlastic, fabric: famFabric, wood: famWood, plant, board, plain,
    };
    const mats = new Map();
    const signTex = signs.map((s) => (s && s.texture ? s.texture : null));
    const clayMat = clay ? new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(0.42, 0.42, 0.42), roughness: 0.75 }) : null;
    function material(key) {
        if (clayMat) return clayMat;
        if (mats.has(key)) return mats.get(key);
        const [base, arg] = key.split(':');
        let col, rgh, metal = 0.0;
        if (base === 'sign') {                                       // a sign given as a picture (or words drawn on a canvas)
            const t = signTex[+arg];
            col = t ? texture(t, THREE.uv()).rgb.mul(0.92) : vec3(...BOARDS[(+arg) % BOARDS.length][0]);
            [col, rgh] = dusted(col, num(0.55), 0.12, 0.3);
        } else [col, rgh, metal] = FAM[base](base, arg);
        const m = new THREE.MeshStandardNodeMaterial();
        m.colorNode = THREE.vec4(num(col), 1.0);                     // (a vec4: the weather's wetness wraps read .w)
        m.roughnessNode = num(rgh);
        m.metalnessNode = num(metal);
        if (base === 'car') { m.clearcoat = 0.7; m.clearcoatRoughness = 0.12; }
        if (['plant', 'fabric'].includes(base)) m.side = THREE.DoubleSide;
        m.name = 'town.' + key.replace(':', '_');
        mats.set(key, m);
        return m;
    }
    return { material, slot, materials: mats, REG, PLAIN, textures: texCache };
}

// which material a face's name is drawn with, and that face's numbers for it -> [key, tmA[4], tmB[4]]
const PAINT = { door_rust: 0.75, steel_dark: 0.35, steel_paint: 0.3, cooler: 0.25, dish: 0.12, dish_dark: 0.1, tank_red: 0.35, lamp_head: 0.15, car_bed: 0.25,
    barrel_rust: 0.9, rust: 1.2, rebar: 1.2, door_green: 0.2, door_blue: 0.2, door_brown: 0.2, door_grey: 0.2, ac: 0.2, speaker: 0.2 };
const PLASTIC = ['tank_white', 'tank_black', 'tank_blue', 'plastic_white', 'plastic_blue', 'plastic_red', 'crate', 'barrel_blue', 'bike_red', 'bike_blue', 'ac_fan'];
const SHUTTERS = [[0.30, 0.32, 0.34], [0.22, 0.27, 0.23], [0.36, 0.34, 0.28], [0.18, 0.23, 0.31], [0.34, 0.20, 0.13], [0.42, 0.42, 0.40]];
const AWNINGS = [[[0.42, 0.07, 0.05], [0.55, 0.52, 0.45]], [[0.06, 0.20, 0.40], [0.55, 0.52, 0.45]], [[0.58, 0.44, 0.10], [0.42, 0.10, 0.06]],
    [[0.10, 0.28, 0.15], [0.52, 0.50, 0.42]], [[0.42, 0.36, 0.26], [0.36, 0.30, 0.20]], [[0.50, 0.22, 0.06], [0.52, 0.46, 0.30]]];
const RUGS = [[0.30, 0.04, 0.035], [0.05, 0.08, 0.22], [0.34, 0.12, 0.05], [0.22, 0.05, 0.12]];
const ONE = ['block', 'brick', 'claustra', 'concrete', 'concrete_broken', 'roof', 'roof_dmg', 'ground', 'yard', 'field', 'field_dry', 'walk', 'median', 'rubble',
    'crater', 'floor', 'mosque', 'gold', 'zinc', 'zinc_old', 'car', 'car_burnt', 'plaster_dmg'];
const Z4 = [0, 0, 0, 0];
export function slot(name) {
    const [base, arg] = name.split(':');
    if (base === 'sign') return [name, Z4, Z4];
    if (base === 'plaster' || base === 'plaster_b' || base === 'plaster_w') return ['plaster', Z4, [{ plaster: 0, plaster_b: 1, plaster_w: 2 }[base], 0, 0, 0]];
    if (base === 'pole') return ['concrete', Z4, Z4];
    if (base === 'road' || base === 'track' || base === 'kerb') return [base, Z4, [arg === 'y' ? 1 : 0, 0, 0, 0]];
    if (ONE.includes(base)) return [base, Z4, Z4];
    if (base === 'trunk') return ['plant', [0.16, 0.12, 0.085, 0.92], [1, 0, 0, 0]];
    if (base === 'palm_trunk') return ['plant', [0.20, 0.155, 0.105, 0.92], [2, 0, 0, 0]];
    if (PLANTS.includes(base)) { const [rgb, rg, mt] = PLAIN[base]; return ['plant', [...rgb, rg], [0, mt, 0, 0]]; }
    if (base === 'sign_board') return ['board', [...BOARDS[(+arg || 0) % BOARDS.length][0], 0.6], Z4];
    if (base === 'ceiling' || base.startsWith('in_')) return ['inwall', [...PLAIN[base][0], 0.9], Z4];
    if (base === 'dome' || base === 'dome_blue' || base === 'tile_band') { const [rgb, rg] = PLAIN[base]; return ['tile', [...rgb, rg], Z4]; }
    if (base === 'shutter') return ['shutter', [...SHUTTERS[(+arg || 0) % 6], 0], Z4];
    if (base === 'awn') { const [a, b] = AWNINGS[(+arg || 0) % 6]; return ['fabric', [...a, 0.92], [1, ...b]]; }
    if (base === 'rug') return ['fabric', [...RUGS[(+arg || 0) % 4], 0.92], [2, 0, 0, 0]];
    if (base.startsWith('cloth') || base.startsWith('tarp_') || ['sack', 'mattress', 'cooler_pad'].includes(base)) return ['fabric', [...PLAIN[base][0], 0.92], Z4];
    if (base === 'wood' || base === 'wood_pale' || base === 'cardboard') return ['wood', [...PLAIN[base][0], 0.85], [base === 'cardboard' ? 1 : 0, 0, 0, 0]];
    if (base in PAINT) { const [rgb, rg, , dust] = PLAIN[base]; return ['paint', [...rgb, rg], [dust || 0.1, PAINT[base], 0, 0]]; }
    if (PLASTIC.includes(base)) { const [rgb, rg, mt, dust] = PLAIN[base]; return ['plastic', [...rgb, rg], [mt, dust || 0.08, 0, 0]]; }
    const [rgb, rg, mt, dust] = PLAIN[base] || [[0.3, 0.3, 0.3], 0.8, 0.0, 0.1];
    return ['plain', [...rgb, rg], [mt, dust === null || dust === undefined ? -1 : dust, ['glass', 'car_glass', 'solar'].includes(base) ? 1 : 0, 0]];
}
