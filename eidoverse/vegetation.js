// grass2 — asset-driven ground flora: grass tuft cards, shrub clusters, rosettes.
//
// Look:   generated map sets (SeedThree convention) — <species>_{albedo,normal,
//         roughness,translucency}.png under eidoverse/assets/grass/. Albedo alpha
//         is the cutout. Translucency drives the backlit term.
// Motion: derived from CK42BB/procedural-grass-threejs (MIT) — 3-layer wind
//         (global sway / gust fronts with a noise envelope / per-instance
//         flutter) and quadratic-falloff pushers, all ×height², constants kept.
// Bodies: our own card models — curved, cupped strips; tufts of 3 crossed cards;
//         shrub clusters of outward-fanned cards with bent (sphere-blended)
//         normals so the bush shades as a volume; rosettes as crossed fans.
//
// const { createFlora, FLORA_SPECIES } = await import(...grass2.js);
// const field = await createFlora({ species: 'creosote', width: 30, depth: 30,
//     heightFn: terrain.heightAt, sunDir: [-0.5, 0.8, 0.3] });
// scene.add(field.mesh);
// field.setPushers([{ x, y, z, r: 1.4 }]);     // characters part the flora
// // wind self-updates via the engine loop; nothing to call per frame.

const T3 = globalThis.THREE;
const {
    positionLocal, attribute, uniform, uniformArray, texture: texNode,
    float, vec2, vec3, vec4, sin, cos, dot, normalize, smoothstep, max: tmax,
    pow, saturate, step, positionWorld, cameraPosition, Fn, tanh, luminance, min: tmin,
    normalLocal, transformNormalToView, uv: uvNode, mix,
} = T3;

const ASSET_DIR = 'eidoverse/assets/grass/';

// grass colours — the seasonal palette, one word each. Multipliers over the
// green blade atlas, hand-balanced so luminance stays in range.
//   spring/summer: lime, emerald, blue (switchgrass/blue-grama powder),
//                  blue-green, gray-green (dry-climate)
//   fall/winter:   burgundy, rust, copper, orange (little bluestem),
//                  straw, brown
// `color:` accepts a name below or a custom [r,g,b] multiplier.
// Values are LUMINANCE-PRESERVING vs the atlas mean — a hue swap, not a
// darkening (naive multipliers crushed every fall colour to muck).
export const GRASS_COLORS = {
    // multipliers (green family) + luminance recolors (hue-changers),
    // NORMALIZED against Sol's blade atlas (opaque mean 91/138/35)
    lime:          [1.15, 1.13, 0.48],
    emerald:       [0.56, 1.04, 0.61],
    blue:          [0.64, 1.05, 1.61],
    'blue-green':  [0.6, 1.07, 1.18],
    // GREEN is a recolor, not a multiplier: a species whose sheet is
    // authored another hue (galleta's straw) can only be brought BACK to
    // green by discarding hue and re-tinting. Value reproduces the blade
    // atlas's own mean green from its luminance.
    green:         { recolor: [0.755, 1.145, 0.29] },
    'gray-green':  { recolor: [0.92, 0.97, 0.83] },
    burgundy:      { recolor: [1.95, 0.57, 0.81] },
    rust:          { recolor: [1.93, 0.79, 0.32] },
    copper:        { recolor: [1.72, 0.93, 0.3] },
    orange:        { recolor: [1.83, 0.98, 0.19] },
    straw:         { recolor: [1.35, 1.14, 0.64] },
    brown:         { recolor: [1.24, 0.91, 0.52] },
};

import { buildShrubGeometry } from './vegetation_shrub_gen.js';
import { buildCornGeometry } from './vegetation_corn_gen.js';
import { buildSunflowerGeometry } from './vegetation_sunflower_gen.js';

// ── species registry ─────────────────────────────────────────────────────────
// card:    { w, h, curve, cup, segH } — one curved strip, full sheet per card
// tuft:    N cards crossed around a shared root (grass archetype)
// shrub:   N cards fanned outward on a shell around the cluster centre
// rosette: crossed vertical fans + a low horizontal card (radial sheet)
export const FLORA_SPECIES = {
    grass: {
        // THE standard green grass — the Halo blade-card hybrid: segmented
        // planes fitted to an individual-blade alpha atlas (blades_meadow_* —
        // Sol's art replaces the stand-in by filename). clump: 1 disables the
        // bare-patch gate — turf is CONTINUOUS; bunches are a desert habit.
        // `height` (metres) sets blade length AND scales the wind response:
        // a lawn barely stirs, tallgrass sways hard (see createFlora).
        archetype: 'blades', maps: 'blades_meadow',
        // SPREAD habit, not the desert bunch: few blades per instance thrown
        // WIDE (bunchR > instance spacing) so neighbours interleave into an
        // even carpet — a 14-blade tight bunch shares one shade tint and reads
        // as a tussock; 5 wide-scattered blades put shade variation at blade
        // scale instead
        blades: { perBunch: 8, bunchR: 0.5, h: 0.38, w: 0.042, lean: 0.42 },
        colors: { jitter: 0.22 },
        baseScale: [0.8, 1.3], density: 22.0, clump: 1.0,
        wind: { base: 0.35, gust: 0.7, gustFreq: 0.3, flutter: 0.5 },
        sss: 0.5, rough: 0.6, pushScale: 1.0,
    },
    galleta_dry: {
        // Mojave BUNCH grass (big galleta / indian ricegrass): the bunch habit
        // is the realistic one for desert. SAME blade atlas as 'grass' — a
        // species is habit params + colour, not its own texture set
        archetype: 'blades', maps: 'blades_meadow',
        leafRecolor: GRASS_COLORS.straw.recolor,
        blades: { perBunch: 34, bunchR: 0.26, h: 0.44, w: 0.036, lean: 0.75 },
        colors: { jitter: 0.26 },
        baseScale: [0.7, 1.25], density: 0.9, clump: 0.55,
        wind: { base: 0.28, gust: 0.5, gustFreq: 0.3, flutter: 0.7 },
        sss: 0.55, rough: 0.7, pushScale: 1.0,
    },
    // the three Mojave shrubs grow from the vendored SeedThree dichotomous
    // math (shrub_gen.js): a real multi-stem crown skeleton, welded tube wood
    // with bark maps, spray cards anchored on the terminal twigs. `gen` picks
    // the growth preset; wind/density/pushScale stay the field-approved values.
    blackbrush: {
        archetype: 'shrub', gen: 'blackbrush', maps: 'blackbrush',
        stem: 'blackbrush_stem', stemColor: 0x6d5a46,
        // halfway between the dark namesake tile and the sheet's pale spiny
        // twigs (painted stem 122/113/99 vs tile 86/78/72) — old wood dark,
        // young growth pale
        stemTint: [1.7, 1.75, 1.6],
        footRadius: 0.75,
        baseScale: [0.7, 1.25], density: 0.06, clump: 0.5,
        wind: { base: 0.06, gust: 0.14, gustFreq: 0.3, flutter: 1.1 },
        sss: 0.35, rough: 0.9, pushScale: 0.4,
    },
    creosote: {
        archetype: 'shrub', gen: 'creosote', maps: 'creosote',
        stem: 'creosote_stem', stemColor: 0x8a7358,
        // linear lift matching the bark tile to the sheet's own painted stem
        // (tile mean 75/62/53 sRGB vs painted stem 117/99/67 — the wood must
        // read as the same branch the card art continues)
        stemTint: [2.6, 2.7, 1.7],
        footRadius: 1.1,
        baseScale: [0.7, 1.3], density: 0.035, clump: 0.3,
        wind: { base: 0.10, gust: 0.22, gustFreq: 0.3, flutter: 1.3 },
        sss: 0.45, rough: 0.85, pushScale: 0.7,
    },
    sagebrush: {
        archetype: 'shrub', gen: 'sagebrush', maps: 'sagebrush',
        stem: 'blackbrush_stem', stemColor: 0x8b8378,  // no own bark set yet — borrows blackbrush's
        // lift toward the sheet's pale shredded-silver stem (painted 189/180/162
        // vs tile 86/78/72) — the full measured ×6 washed the fissures to chalk,
        // this keeps the grain readable while staying silver
        stemTint: [3.2, 3.5, 3.3],
        footRadius: 0.65,
        baseScale: [0.75, 1.3], density: 0.05, clump: 0.45,
        wind: { base: 0.08, gust: 0.18, gustFreq: 0.3, flutter: 1.0 },
        sss: 0.4, rough: 0.9, pushScale: 0.45,
    },
    yucca: {
        // real geometry rosette — ~30 V-folded spike leaves (crossed cards
        // read as crossed cards; a yucca is structural)
        archetype: 'yucca', maps: 'yucca_kit',
        rosette: { r: 0.55, spikes: 64 },   // density is what hides the crown bases
        footRadius: 0.6,
        baseScale: [1.0, 1.6], density: 0.10, clump: 0.15,
        wind: { base: 0.03, gust: 0.06, gustFreq: 0.3, flutter: 0.5 },
        sss: 0.5, rough: 0.8, pushScale: 0.12,
    },
    corn: {
        // the crop (corn_gen.js): cane stalk, ranked arching leaves, husked
        // ear, silk, tassel — one geometry on the ONE corn_ trim sheet, her
        // baked cob included (peel: true stands it up bare on the first ear).
        // Pair with `rows` for a planted field; without rows it volunteers as
        // a wild patch. Crop uniformity: tight baseScale, near-vertical.
        archetype: 'corn', maps: 'corn',
        corn: { height: 2.3, leaves: 10, leafLen: 0.95, ears: 3, peel: false },
        // plume art is dark red-brown; a mature field's tassels read tan-straw
        regionTint: { u0: 0.5, u1: 1.0, v0: 0.7, v1: 1.0, mul: [1.9, 2.7, 2.2] },
        footRadius: 0.32,
        baseScale: [0.88, 1.14], density: 1.4, clump: 0.85,
        wind: { base: 0.05, gust: 0.11, gustFreq: 0.3, flutter: 1.2 },
        sss: 0.55, rough: 0.75, pushScale: 0.55,
    },
    sunflower: {
        // the sunflower (sunflower_gen.js): cane stalk, spiral heart-leaves,
        // one nodding head — seed-disc lathe (Skye's highpoly cut + baked),
        // ray-petal card ring, bract star behind — all on the ONE sunflower_
        // trim sheet. Pair with `rows` for a planted field.
        archetype: 'sunflower', maps: 'sunflower',
        sunflower: { height: 1.9, leaves: 11, leafLen: 0.62, headR: 0.20, petals: 26 },
        footRadius: 0.3,
        baseScale: [0.9, 1.12], density: 1.2, clump: 0.8,
        // stiffer cane than corn, and the heavy head barely flutters
        wind: { base: 0.04, gust: 0.09, gustFreq: 0.3, flutter: 0.8 },
        sss: 0.5, rough: 0.8, pushScale: 0.4,
    },
};

// ── map loading ──────────────────────────────────────────────────────────────
async function loadMap(name, { srgb = false } = {}) {
    try {
        const bytes = await Deno.readFile(ASSET_DIR + name);
        const t = await globalThis.loadImageTexture(bytes, srgb ? { srgb: true } : {});
        t.wrapS = t.wrapT = T3.ClampToEdgeWrapping;
        t.anisotropy = 4;
        return t;
    } catch { return null; }
}

async function loadSpeciesMaps(base) {
    const [albedo, normal, rough, transl] = await Promise.all([
        loadMap(`${base}_albedo.png`, { srgb: true }),
        loadMap(`${base}_normal.png`),
        loadMap(`${base}_roughness.png`),
        loadMap(`${base}_translucency.png`, { srgb: true }),
    ]);
    if (!albedo) throw new Error(`[grass2] missing ${base}_albedo.png in ${ASSET_DIR}`);
    return { albedo, normal, rough, transl };
}

// bark map set for shrub wood — the tube UVs wrap, so these tile
async function loadStemMaps(base) {
    const [albedo, rough] = await Promise.all([
        loadMap(`${base}_albedo.png`, { srgb: true }),
        loadMap(`${base}_roughness.png`),
    ]);
    for (const t of [albedo, rough]) if (t) t.wrapS = t.wrapT = T3.RepeatWrapping;
    return albedo ? { albedo, rough } : null;
}

// ── card geometry — a curved, cupped strip; aH = 0 root → 1 tip ─────────────
function cardGeometry({ w, h, curve = 0.2, cup = 0.08, segH = 3, segW = 2 }) {
    const g = new T3.PlaneGeometry(w, h, segW, segH);
    g.translate(0, h / 2, 0);                       // root at y=0
    const pos = g.attributes.position, uv = g.attributes.uv;
    const aH = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) {
        const t = pos.getY(i) / h;                  // 0 root → 1 tip
        const s = pos.getX(i) / (w / 2);            // -1 … 1 across
        // quadratic-bezier lean (p1 = curve at mid-height), like a blade
        pos.setZ(i, pos.getZ(i) + 2 * (1 - t) * t * curve * h + cup * s * s * w);
        aH[i] = t;
        uv.setY(i, t);                              // v runs root→tip
    }
    g.setAttribute('aH', new T3.BufferAttribute(aH, 1));
    g.computeVertexNormals();
    return g;
}

function mergeInto(acc, geo, mat4) {
    const g = geo.clone().applyMatrix4(mat4);
    acc.push(g);
    return g;
}

function mergeAll(list) {
    const { mergeGeometries } = T3.BufferGeometryUtils || globalThis.BufferGeometryUtils || {};
    if (mergeGeometries) return mergeGeometries(list, false);
    // tiny fallback merge (position/normal/uv/aH, indexed)
    let vtx = 0, idx = 0;
    for (const g of list) { vtx += g.attributes.position.count; idx += g.index.count; }
    const pos = new Float32Array(vtx * 3), nor = new Float32Array(vtx * 3),
        uv = new Float32Array(vtx * 2), aH = new Float32Array(vtx),
        index = new Uint32Array(idx);
    let vo = 0, io = 0;
    for (const g of list) {
        pos.set(g.attributes.position.array, vo * 3);
        nor.set(g.attributes.normal.array, vo * 3);
        uv.set(g.attributes.uv.array, vo * 2);
        aH.set(g.attributes.aH.array, vo);
        const gi = g.index.array;
        for (let i = 0; i < gi.length; i++) index[io + i] = gi[i] + vo;
        vo += g.attributes.position.count; io += gi.length;
    }
    const out = new T3.BufferGeometry();
    out.setAttribute('position', new T3.BufferAttribute(pos, 3));
    out.setAttribute('normal', new T3.BufferAttribute(nor, 3));
    out.setAttribute('uv', new T3.BufferAttribute(uv, 2));
    out.setAttribute('aH', new T3.BufferAttribute(aH, 1));
    out.setIndex(new T3.BufferAttribute(index, 1));
    return out;
}

const _m4 = new T3.Matrix4(), _q = new T3.Quaternion(), _v = new T3.Vector3(), _e = new T3.Euler();

// grass cards light like a ground carpet when their normals lean world-up —
// per-card normals leave half the yaw-rotated instances facing away from the
// sun and the field goes near-black in the mid-distance
function blendNormalsUp(g, k = 0.65) {
    const nor = g.attributes.normal;
    for (let i = 0; i < nor.count; i++) {
        const nx = nor.getX(i) * (1 - k), ny = nor.getY(i) * (1 - k) + k, nz = nor.getZ(i) * (1 - k);
        const l = Math.hypot(nx, ny, nz) || 1;
        nor.setXYZ(i, nx / l, ny / l, nz / l);
    }
    return g;
}

// tuft: N cards sharing a root, yaw-fanned with slight tilt scatter
function tuftGeometry(spec, rng) {
    const parts = [];
    const card = cardGeometry(spec.card);
    for (let i = 0; i < spec.cards; i++) {
        const yaw = (i / spec.cards) * Math.PI + (rng() - 0.5) * 0.5;
        const tilt = (rng() - 0.5) * 0.22;
        _e.set(tilt, yaw, (rng() - 0.5) * 0.12);
        _m4.makeRotationFromEuler(_e);
        mergeInto(parts, card, _m4);
    }
    return blendNormalsUp(mergeAll(parts), 1.0);   // grass cards: normals straight up — light like the ground plane
}

// (Shrub bodies now grow in shrub_gen.js — the vendored SeedThree dichotomous
// skeleton + spray-card cluster grammar. The old basal-stem cluster builder
// lives in git history.)

// blade cards, the Halo hybrid (Skye's own production technique): each blade
// is a segmented plane whose silhouette lives in the ALPHA of an individual-
// blade atlas column — and the card's loop widths/centres are FITTED to the
// measured envelope of that column's art (close, not exact: no tip modeling)
// so the empty-alpha margin, and with it the overdraw, mostly disappears.
function bunchGeometry(spec, rng, fit) {
    const { perBunch, bunchR, h, w, lean } = spec.blades;
    const COLS = 8;
    const cardW = w * 2;                  // full card width the atlas column maps to
    const pos = [], aH = [], uv = [], idx = [];
    let vb = 0;
    const LOOPS = 4;                      // horizontal segments carry the bend (4: smoother arcs AND tighter UV tracking of curved atlas blades — instanced, so the cost is per-blade-geometry only)
    for (let b = 0; b < perBunch; b++) {
        const ang = rng() * Math.PI * 2, rad = Math.sqrt(rng()) * bunchR;
        const bx = Math.cos(ang) * rad, bz = Math.sin(ang) * rad;
        const bh = h * (0.6 + rng() * 0.8), bw = cardW * (0.85 + rng() * 0.4);
        const roll = rng() * Math.PI * 2;
        const leanAmt = (0.25 + rng() * 0.75) * lean * bh;
        const cr = Math.cos(roll), sr = Math.sin(roll);
        const c = Math.floor(rng() * COLS);
        const bands = fit ? fit[c] : null;
        const s0 = vb;
        for (let lp = 0; lp <= LOOPS; lp++) {
            const t = lp / LOOPS;
            const [fcx, fhw] = bands ? bands[lp] : [0, 0.5];
            const bend = leanAmt * t * t;                 // pose lean (quadratic)
            const artC = fcx * bw;                        // follow the art's curve
            const px = bx + cr * (bend + artC), pz = bz + sr * (bend + artC);
            const py = t * bh;
            const hwW = fhw * bw;                         // fitted half-width
            pos.push(px - sr * hwW, py, pz + cr * hwW);
            pos.push(px + sr * hwW, py, pz - cr * hwW);
            // UVs sample exactly the strip of art the fitted card covers
            uv.push((c + 0.5 + fcx - fhw) / COLS, t, (c + 0.5 + fcx + fhw) / COLS, t);
            aH.push(t, t);
            vb += 2;
        }
        for (let lp = 0; lp < LOOPS; lp++) {
            const a = s0 + lp * 2;
            idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
        }
    }
    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    return blendNormalsUp(g, 1.0);   // blades: normals straight up — light like the ground plane
}

// Mojave yucca (Yucca schidigera) — built to reference (Red Rock NV habit
// photos): a DENSE golden-spiral crown of straight stiff bayonets — near-
// vertical at the centre grading to sub-horizontal at the rim, each base on
// its own point of a small dome so there is no shared convergence point to
// see — over a thatch-skinned trunk whose upper half wears a thick skirt of
// downswept dried leaves. Density is what hides the bases: you can't see
// into a real schidigera crown.
function yuccaGeometry(spec, rng) {
    const { r, spikes } = spec.rosette;
    const pos = [], uv = [], aH = [], idx = [];
    let vb = 0;
    const S = new T3.Vector3(), A = new T3.Vector3(), UPL = new T3.Vector3(), RAD = new T3.Vector3();
    const YUP = new T3.Vector3(0, 1, 0);
    const GA = 2.399963;   // golden angle
    // atlas thirds (the approved composition sheet): live fronds | dry fronds
    // | trunk thatch — each spike maps its column window; the art's alpha
    // carves the silhouettes
    const LIVE = [0.012, 0.32], DRY = [0.345, 0.655], BARK = [0.67, 0.996];
    const liveCol = () => LIVE;
    const dryCol = () => DRY;
    // a real column, not a ground collar; heroes scale this up per instance
    const trunkH = 0.22 + rng() * 0.28;
    const trunkR = 0.06 + rng() * 0.02;
    // decades of lean baked into the column: a smooth arc — some plants nearly
    // straight, some properly bendy — and the crown rides the arc's END
    // tangent, so the whole head tips off-vertical like the old veterans
    const bendA = rng() * Math.PI * 2;
    const bendAmt = (0.1 + rng() * 0.55) * trunkH;
    const bcx = Math.cos(bendA) * bendAmt, bcz = Math.sin(bendA) * bendAmt;
    const trunkPoint = (t) => [bcx * t * t, t * trunkH, bcz * t * t];
    const qAt = (t) => {                    // frame of the arc at height fraction t
        A.set(2 * bcx * t, trunkH, 2 * bcz * t).normalize();
        return new T3.Quaternion().setFromUnitVectors(YUP, A);
    };

    // one straight V-folded bayonet from an explicit base point; qRot tips its
    // whole frame (axis, side, fold) with the column so leaves follow the lean
    function spike(yaw, pitch, len, u0, u1, bx, by, bz, droopK, qRot) {
        const w0 = len * 0.145 * (0.9 + rng() * 0.3);    // fuller blades, mild jitter
        A.set(Math.cos(yaw) * Math.cos(pitch), Math.sin(pitch), Math.sin(yaw) * Math.cos(pitch));
        S.set(-Math.sin(yaw), 0, Math.cos(yaw));
        UPL.set(0, 1, 0);
        if (qRot) { A.applyQuaternion(qRot); S.applyQuaternion(qRot); UPL.applyQuaternion(qRot); }
        const segs = 3, s0 = vb;
        for (let sg = 0; sg <= segs; sg++) {
            const t = sg / segs;
            const wHere = w0 * (1 - t * 0.94);
            const droop = droopK * len * t * t;   // gravity sag stays world-down
            const cxp = bx + A.x * len * t, cyp = by + A.y * len * t + droop, czp = bz + A.z * len * t;
            const foldUp = wHere * 0.55;
            pos.push(cxp - S.x * wHere, cyp - S.y * wHere, czp - S.z * wHere); uv.push(u0, t); aH.push(t * 0.3);
            pos.push(cxp + UPL.x * foldUp, cyp + UPL.y * foldUp, czp + UPL.z * foldUp); uv.push((u0 + u1) / 2, t); aH.push(t * 0.3);
            pos.push(cxp + S.x * wHere, cyp + S.y * wHere, czp + S.z * wHere); uv.push(u1, t); aH.push(t * 0.3);
            vb += 3;
        }
        for (let sg = 0; sg < segs; sg++) {
            const a = s0 + sg * 3, b = a + 3;
            idx.push(a, a + 1, b, a + 1, b + 1, b, a + 1, a + 2, b + 1, a + 2, b + 2, b + 1);
        }
    }

    // trunk: rings along the arc, base sunk below grade, real thatch skin
    {
        const n = 10, rings = 4, s0 = vb;
        for (let g = 0; g <= rings; g++) {
            const t = g / rings;
            const [cx, cy, cz] = trunkPoint(t);
            const rad = trunkR * (1.12 - 0.27 * t);
            const y = g === 0 ? -0.05 : cy;
            for (let i = 0; i <= n; i++) {
                const a = (i / n) * Math.PI * 2;
                const u = BARK[0] + (BARK[1] - BARK[0]) * (i / n);
                pos.push(cx + Math.cos(a) * rad, y, cz + Math.sin(a) * rad);
                uv.push(u, 0.02 + t * trunkH * 0.9); aH.push(0);
                vb += 1;
            }
        }
        for (let g = 0; g < rings; g++) for (let i = 0; i < n; i++) {
            const a = s0 + g * (n + 1) + i, b = a + n + 1;
            idx.push(a, b, a + 1, a + 1, b, b + 1);
        }
        const [tx, ty, tz] = trunkPoint(1);
        const cTop = vb;
        pos.push(tx, ty + 0.01, tz); uv.push((BARK[0] + BARK[1]) / 2, 0.6); aH.push(0); vb += 1;
        const lastRing = s0 + rings * (n + 1);
        for (let i = 0; i < n; i++) idx.push(lastRing + i, cTop, lastRing + i + 1);
    }

    // dried skirt: dense, in a tight band just under the crown, downswept and
    // hugging the column — bases and directions follow the arc's local frame
    const nSkirt = Math.round(spikes * 0.8);
    for (let i = 0; i < nSkirt; i++) {
        const tS = i / nSkirt;
        const yaw = i * GA + rng() * 0.3;
        const hFrac = Math.min(1, 0.72 + 0.26 * tS + rng() * 0.04);
        const [cx, cy, cz] = trunkPoint(hFrac);
        const qR = qAt(hFrac);
        const pitch = -(0.35 + rng() * 0.8);
        const len = r * (0.3 + 0.2 * tS + rng() * 0.14);          // oldest (lowest) slightly shorter
        const col = tS < 0.35 ? BARK : dryCol();                  // oldest thatch weathers to trunk colour
        RAD.set(Math.cos(yaw) * trunkR * 0.9, 0, Math.sin(yaw) * trunkR * 0.9).applyQuaternion(qR);
        spike(yaw, pitch, len, col[0], col[1], cx + RAD.x, cy + RAD.y, cz + RAD.z, -0.28, qR);
    }

    // live crown: golden-spiral spherical burst riding the arc's end tangent.
    // t=0 centre → near-vertical bayonets, t=1 rim plunging into the skirt;
    // each base on its own dome point. Mid-dome leaves run longest.
    const qTop = qAt(1);
    const [tpx, tpy, tpz] = trunkPoint(1);
    for (let i = 0; i < spikes; i++) {
        const t = (i + 0.5) / spikes;
        const yaw = i * GA + rng() * 0.25;
        const pitch = 1.45 - t * 2.1 + rng() * 0.12;              // ~83° → ~-37°
        const baseR = trunkR * (0.15 + 0.8 * Math.sqrt(t));
        const hDome = 0.02 + 0.055 * (1 - t * t);                 // dome: centre sits higher
        const len = r * (0.6 + 0.42 * Math.sin(Math.min(Math.PI, (0.25 + t * 0.75) * Math.PI)) + rng() * 0.12);
        RAD.set(Math.cos(yaw) * baseR, hDome, Math.sin(yaw) * baseR).applyQuaternion(qTop);
        const lc = liveCol();
        spike(yaw, pitch, len, lc[0], lc[1], tpx + RAD.x, tpy + RAD.y, tpz + RAD.z, -0.04, qTop);
    }

    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setIndex(idx);
    g.computeVertexNormals();
    return blendNormalsUp(g, 0.35);
}

// rosette: crossed vertical fans + optional low horizontal card
function rosetteGeometry(spec, rng) {
    const { r, cards, topCard } = spec.rosette;
    const parts = [];
    const fan = cardGeometry({ w: r * 2, h: r * 1.5, curve: 0.05, cup: 0.02, segH: 2 });
    for (let i = 0; i < cards; i++) {
        _e.set(0, (i / cards) * Math.PI + (rng() - 0.5) * 0.2, 0);
        _m4.makeRotationFromEuler(_e);
        mergeInto(parts, fan, _m4);
    }
    if (topCard) {
        const flat = cardGeometry({ w: r * 2, h: r * 2, curve: 0, cup: 0, segH: 1 });
        _e.set(-Math.PI / 2, rng() * Math.PI, 0);
        _m4.makeRotationFromEuler(_e).setPosition(0, r * 0.55, 0);
        mergeInto(parts, flat, _m4);
    }
    return blendNormalsUp(mergeAll(parts), 0.5);
}

// ── cross-field occupancy — content-aware overlap ───────────────────────────
// Structural plants (species with footRadius) claim their canopy footprint
// here as they place; later fields skip candidates that would clip an
// existing claim. One registry per render process = per scene build.
// Shrub canopies may touch (×0.75 of summed radii); grasses ignore it all.
const _placedPlants = [];
export function resetFloraOccupancy() { _placedPlants.length = 0; }
function occupancyConflict(x, z, r) {
    for (let i = 0; i < _placedPlants.length; i++) {
        const p = _placedPlants[i];
        const rr = (r + p.r) * 0.75;
        const dx = x - p.x, dz = z - p.z;
        if (dx * dx + dz * dz < rr * rr) return true;
    }
    return false;
}

// ── placement — jittered grid, slope rejection, bare patches (CK42BB) ───────
function valueNoise2D(seed) {
    const h = (x, y) => { const s = Math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453; return s - Math.floor(s); };
    return (x, y) => {
        const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
        const ux = xf * xf * (3 - 2 * xf), uy = yf * yf * (3 - 2 * yf);
        return (h(xi, yi) * (1 - ux) + h(xi + 1, yi) * ux) * (1 - uy)
            + (h(xi, yi + 1) * (1 - ux) + h(xi + 1, yi + 1) * ux) * uy;
    };
}

// `surface` support: any mesh(es) become a height field by raycasting straight
// down — height from the hit point, slope from the hit normal. This is what
// frees the brush from the terrain system: rocks, rooftops, sculpted ground,
// any geometry at all. Returns null where the ray misses (no placement).
function surfaceSampler(surface) {
    const meshes = Array.isArray(surface) ? surface : [surface];
    for (const m of meshes) m.updateWorldMatrix(true, false);
    const ray = new T3.Raycaster();
    const down = new T3.Vector3(0, -1, 0);
    const from = new T3.Vector3();
    return (x, z) => {
        from.set(x, 10000, z);
        ray.set(from, down);
        const hits = ray.intersectObjects(meshes, true);
        if (!hits.length) return null;
        const h = hits[0];
        const n = h.normal ?? new T3.Vector3(0, 1, 0);
        if (n.y < 0) n.negate();
        return { y: h.point.y, slope: Math.acos(Math.min(1, Math.abs(n.y))), nx: n.x, ny: n.y, nz: n.z };
    };
}

function placeInstances(o, spec) {
    const rng = (() => { let s = (o.seed ?? 7) * 2654435761 % 2147483647;
        return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; })();
    const noise = valueNoise2D(o.seed ?? 7);
    const W = o.width, D = o.depth, cx = o.center[0], cz = o.center[1];
    // `density` means the stand's INTERIOR fullness in every footprint mode:
    // the organic mask culls ~1/3 of placements, so it samples finer to keep
    // the same plants-per-square-metre as the circular default
    const step = 1 / Math.sqrt(spec.density * (o.density ?? 1) * (o.footprint === 'organic' ? 1.45 : 1));
    const out = [];
    // footprint: a stand is never square. Default cuts the W×D rectangle to
    // its inscribed ellipse with a feathered rim; footprint: 'organic' further
    // masks it with low-frequency noise so the stand reads as an irregular
    // lobed patch. (The rim feather is what keeps either shape from reading
    // as a stamped outline.)
    const organic = o.footprint === 'organic';
    const sstep = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };
    // the rim has no line: density feathers from 60% of the radius out, and a
    // sparse STRAGGLER tail runs past the nominal edge to 1.25R — isolated
    // outliers are what stop a foreshortened arc from reading as a stamped
    // boundary from a low camera
    const EXT = 1.25;
    for (let gx = -W * EXT / 2; gx < W * EXT / 2; gx += step) for (let gz = -D * EXT / 2; gz < D * EXT / 2; gz += step) {
        const x = cx + gx + (rng() - 0.5) * step, z = cz + gz + (rng() - 0.5) * step;
        if (o.clipFn && o.clipFn(x, z)) continue;
        const r = Math.sqrt(((x - cx) / (W / 2)) ** 2 + ((z - cz) / (D / 2)) ** 2);
        if (r > EXT) continue;
        if (r > 1) {
            if (rng() > 0.055 * (1 - (r - 1) / (EXT - 1))) continue;   // stragglers
        } else if (rng() < sstep(0.82, 1.04, r)) continue;             // feathered rim (outer ~18%)
        if (organic) {
            // lobe scale ADAPTS to the field: ~4 lobes per stand at any size.
            // A fixed wavelength made small stands lose half their area to a
            // single mask gap (and aligned gaps across stands left holes).
            const f = 3.4 / Math.max(W, D);
            const m = noise(x * f + 31.7, z * f + 17.3);
            if (m < 0.4 + 0.28 * Math.min(1, r)) continue;             // lobes shrink toward the rim
        }
        // bare patches + clumping via low-frequency noise (their density gate)
        const dN = noise(x * 0.05, z * 0.05);
        if (dN < 0.5 - spec.clump && rng() < 0.85) continue;
        const p = finishPlacement(x, z, o, spec, rng, step, true);
        if (p) out.push(p);
    }
    return out;
}

// the shared placement tail — surface raycast / heightFn, slope gate, scale,
// occupancy, tilt + jitter. Grid placement self-checks the occupancy registry
// (selfCheck true); row planting only CLAIMS (a planted field is authored, the
// way explicit `placements` are — later strokes avoid it, it avoids nothing).
function finishPlacement(x, z, o, spec, rng, step, selfCheck) {
    let y, ntx = 0, ntz = 0;
    if (o._surfaceAt) {
        const hit = o._surfaceAt(x, z);
        if (!hit) return null;                           // off the geometry
        if (o.maxSlope && hit.slope > o.maxSlope) return null;
        y = hit.y;
        // follow the geometry: tilt world-up toward the hit normal by the
        // stroke's align share (grass hugs its ground, shrubs grow to sky)
        const k = o._align;
        if (k > 0) {
            ntx = Math.atan2(hit.nz, hit.ny) * k;
            ntz = -Math.atan2(hit.nx, hit.ny) * k;
        }
    } else {
        y = o.heightFn ? o.heightFn(x, z) : (o.y ?? 0);
        if (o.heightFn && o.maxSlope) {
            const eps = step * 0.5;
            const sx = (o.heightFn(x + eps, z) - y) / eps, sz = (o.heightFn(x, z + eps) - y) / eps;
            if (Math.atan(Math.hypot(sx, sz)) > o.maxSlope) return null;
        }
    }
    const [s0, s1] = spec.baseScale;
    const scale = s0 + rng() * (s1 - s0);
    if (spec.footRadius && o.avoid !== false) {
        const r = spec.footRadius * scale;
        if (selfCheck && occupancyConflict(x, z, r)) return null;
        _placedPlants.push({ x, z, r });
    }
    const leanAz = rng() * Math.PI * 2, lean = (rng() - 0.5) * 0.16;
    // `heading` locks instance yaw to a shared world azimuth (± headingJitter,
    // default 0.15 rad) — sunflower fields face one way; omit for the usual
    // random spin. ONE rng draw either way so the stream stays aligned.
    const spin = rng();
    const yaw = o.heading != null
        ? o.heading + (spin - 0.5) * 2 * (o.headingJitter ?? 0.15)
        : spin * Math.PI * 2;
    return {
        x, y, z, yaw,
        scale, tilt: 0,
        tx: ntx + Math.cos(leanAz) * lean, tz: ntz + Math.sin(leanAz) * lean,
        colorVar: rng(), phase: rng() * Math.PI * 2,
    };
}

// ── row planting — the cultivated footprint ─────────────────────────────────
// A planted field IS rectangular: rows at `spacing`, plants every `plant`
// metres along them, small sowing jitter, a few misses (`skip` + the density
// deficit), ragged headlands where each row starts and stops a little short.
// No ellipse cut, no stragglers — those are wild-stand manners. `angle` turns
// the whole planting; stride/phase interleave two strokes through one field
// (e.g. every 4th row from a peeled-ear variant call).
function placeRows(o, spec) {
    const rng = (() => { let s = ((o.seed ?? 7) + 5) * 2654435761 % 2147483647;
        return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; })();
    const r = typeof o.rows === 'object' ? o.rows : {};
    // `density` works BOTH ways on a planted field, because a grid cannot
    // simply be told to hold more plants: below 1 it drops plants (skip),
    // above 1 it tightens the IN-ROW spacing — which is how a real field's
    // population is set, the row gap being fixed by the machinery. Without
    // the second half, every density >= 1 rendered the identical field.
    const k = o.density ?? 1;
    const gap = r.spacing ?? 0.76, inRow = (r.plant ?? 0.24) / Math.max(1, k);
    const ang = r.angle ?? 0, jit = r.jitter ?? 0.05;
    const skip = Math.min(0.95, (r.skip ?? 0.03) + Math.max(0, 1 - k));
    const stride = Math.max(1, r.stride ?? 1), phase = r.phase ?? 0;
    const ca = Math.cos(ang), sa = Math.sin(ang);
    const W = o.width, D = o.depth, cx = o.center[0], cz = o.center[1];
    const out = [];
    let rowI = 0;
    for (let rz = -D / 2 + gap * 0.5; rz <= D / 2 - gap * 0.2; rz += gap, rowI++) {
        if ((rowI + phase) % stride !== 0) continue;
        const end0 = -W / 2 + rng() * inRow * 1.6, end1 = W / 2 - rng() * inRow * 1.6;
        for (let rx = end0 + inRow * 0.5; rx <= end1; rx += inRow) {
            if (rng() < skip) continue;                   // the missing plants
            const lxx = rx + (rng() - 0.5) * jit * 2, lzz = rz + (rng() - 0.5) * jit * 2;
            const x = cx + lxx * ca - lzz * sa, z = cz + lxx * sa + lzz * ca;
            if (o.clipFn && o.clipFn(x, z)) continue;
            const p = finishPlacement(x, z, o, spec, rng, inRow, false);
            if (p) out.push(p);
        }
    }
    return out;
}

// ── the shared gust-envelope noise texture (proven on-stack pattern) ────────
let _gustTex = null;
function gustTex() {
    if (_gustTex) return _gustTex;
    const n = 256, d = new Uint8Array(n * n * 4);
    const nz = valueNoise2D(3);
    for (let i = 0; i < n * n; i++) {
        const x = i % n, y = (i / n) | 0;
        let v = 0, amp = 0.55, f = 0.035;
        for (let o = 0; o < 4; o++) { v += nz(x * f, y * f) * amp; amp *= 0.5; f *= 2; }
        const c = Math.max(0, Math.min(255, v * 255)) | 0;
        d[i * 4] = c; d[i * 4 + 1] = c; d[i * 4 + 2] = c; d[i * 4 + 3] = 255;
    }
    _gustTex = new T3.DataTexture(d, n, n, T3.RGBAFormat);
    _gustTex.wrapS = _gustTex.wrapT = T3.RepeatWrapping;
    _gustTex.magFilter = _gustTex.minFilter = T3.LinearFilter;
    _gustTex.needsUpdate = true;
    return _gustTex;
}

// ── main ─────────────────────────────────────────────────────────────────────
export async function createFlora(opts = {}) {
    let spec = FLORA_SPECIES[opts.species === 'meadow_blades' ? 'grass' : opts.species];
    if (!spec) throw new Error(`[grass2] unknown species '${opts.species}' — have: ${Object.keys(FLORA_SPECIES).join(', ')}`);
    const o = {
        width: 24, depth: 24, center: [0, 0], y: 0, seed: 7,
        maxSlope: 0.9, sunDir: [-0.5, 0.8, 0.3], windDir: [1, 0.3],
        ...opts,
    };
    // `size` = stand diameter (stands are circular by default); width/depth
    // remain available for elliptical stands
    if (opts.size) {
        if (!opts.width) o.width = opts.size;
        if (!opts.depth) o.depth = opts.size;
    }
    // `surface` = mesh or mesh array to grow on (raycast placement) — frees
    // the brush from terrain: any geometry works. heightFn still wins if both
    // are given; explicit `placements` keep their own y handling below.
    if (opts.surface && !opts.heightFn) o._surfaceAt = surfaceSampler(opts.surface);
    // `align` = how much plants tilt with the surface normal (0 world-up …
    // 1 full normal). Grass hugs its ground; woody plants grow toward the sky.
    o._align = opts.align ?? (spec.blades ? 0.75 : 0.15);
    // `height` = grass height in metres for blade fields (lawn 0.1, meadow
    // 0.35-0.5, tallgrass 0.8+). Overrides the species' authored blade length
    // AND scales the wind response with it — short turf is stiff (a lawn
    // barely stirs), long blades are compliant levers (tallgrass sways hard,
    // flutters more). windK ~ (h/authored)^1.4, clamped 0.25..2.2; the h²
    // height factor in the shader then compounds it naturally per vertex.
    // Silently irrelevant to shrub/yucca fields (their size is the plant's).
    // `color` = seasonal grass colour: a GRASS_COLORS name ('emerald',
    // 'copper', 'straw'...) or a custom [r,g,b] multiplier over the atlas.
    // BLADE GRASSES ONLY — shrub/yucca foliage always renders its authored
    // sheet colours (no API path tints them; asset changes are art changes)
    if (opts.color) {
        if (!spec.blades) throw new Error(`[grass2] 'color' applies to blade grasses only — '${opts.species}' keeps its authored sheet colours`);
        const entry = Array.isArray(opts.color) ? opts.color : GRASS_COLORS[opts.color];
        if (!entry) throw new Error(`[grass2] unknown color '${opts.color}' — have: ${Object.keys(GRASS_COLORS).join(', ')} (or a custom [r,g,b])`);
        if (Array.isArray(entry)) spec = { ...spec, leafTint: entry };
        else spec = { ...spec, leafRecolor: entry.recolor };
    }
    if (opts.height && spec.blades) {
        const hK = Math.min(2.2, Math.max(0.25, (opts.height / spec.blades.h) ** 1.4));
        spec = {
            ...spec,
            blades: { ...spec.blades, h: opts.height },
            wind: {
                ...spec.wind,
                base: spec.wind.base * hK,
                gust: spec.wind.gust * hK,
                flutter: spec.wind.flutter * Math.sqrt(hK),
            },
        };
    }
    const maps = spec.maps ? await loadSpeciesMaps(spec.maps) : null;
    let bladeFit = null;
    if (spec.archetype === 'blades' && spec.maps) {
        try { bladeFit = JSON.parse(await Deno.readTextFile(ASSET_DIR + spec.maps + '_fit.json')); }
        catch { /* no fit data — unfitted rectangles still render */ }
    }

    // base geometry: one tuft / cluster / rosette (seeded, so fields differ by seed)
    const gRng = (() => { let s = (o.seed + 13) * 48271 % 2147483647;
        return () => { s = (s * 48271) % 2147483647; return s / 2147483647; }; })();
    let shrubAnchor = null;
    if (spec.archetype === 'shrub') {
        try { shrubAnchor = JSON.parse(await Deno.readTextFile(ASSET_DIR + 'shrub_anchors.json'))[spec.maps] ?? null; }
        catch { /* unmeasured sheets still place by card base */ }
    }
    let shrubGeos = null;
    if (spec.archetype === 'shrub') {
        shrubGeos = buildShrubGeometry(spec.gen, `${spec.gen}:${o.seed}:${o.variant ?? 0}`, shrubAnchor);
        console.log(`[grass2] ${spec.gen} skeleton: ${shrubGeos.stats.stems} stems, ${shrubGeos.stats.terminals} terminals, ${shrubGeos.stats.woodVerts}+${shrubGeos.stats.leafVerts} verts`);
    }
    let cornBuild = null;
    if (spec.archetype === 'corn') {
        cornBuild = buildCornGeometry('corn', `corn:${o.seed}:${o.variant ?? 0}`,
            { ...spec.corn, ...(opts.corn ?? {}) });
        blendNormalsUp(cornBuild.geo, 0.3);
        console.log(`[grass2] corn plant: ${cornBuild.stats.verts} verts, ${cornBuild.stats.tris} tris`);
    }
    if (spec.archetype === 'sunflower') {
        // fitted card envelopes measured from the delivered art (overdraw
        // pull-in); the gen has a stand-in fallback if the json is absent
        let sunFit = null;
        try { sunFit = JSON.parse(await Deno.readTextFile(ASSET_DIR + 'sunflower_fit.json')); }
        catch { /* fallback envelopes in the gen */ }
        cornBuild = buildSunflowerGeometry('sunflower', `sunflower:${o.seed}:${o.variant ?? 0}`,
            { fit: sunFit, ...spec.sunflower, ...(opts.sunflower ?? {}) });
        // the gen owns its normals (bent head volume + up-blended blades) —
        // a generic re-blend here would undo that treatment
        console.log(`[grass2] sunflower plant: ${cornBuild.stats.verts} verts, ${cornBuild.stats.tris} tris`);
    }
    const baseGeo = shrubGeos ? shrubGeos.leaf
        : cornBuild ? cornBuild.geo
        : spec.archetype === 'rosette' ? rosetteGeometry(spec, gRng)
        : spec.archetype === 'yucca' ? yuccaGeometry(spec, gRng)
        : spec.archetype === 'blades' ? bunchGeometry(spec, gRng, bladeFit)
        : tuftGeometry(spec, gRng);

    const inst = o.placements
        ? o.placements.map((pl, pi) => {
            // seeded, not Math.random(): authored placements must reproduce
            // exactly per seed — run-to-run scale/yaw drift broke every
            // like-for-like lookdev comparison
            const pr = (() => { let sN = ((o.seed ?? 7) * 131 + pi * 37 + 5) % 2147483647;
                return () => { sN = (sN * 16807) % 2147483647; return sN / 2147483647; }; })();
            const scale = pl[2] ?? 1;
            if (spec.footRadius) _placedPlants.push({ x: pl[0], z: pl[1], r: spec.footRadius * scale });
            const sy = o._surfaceAt ? (o._surfaceAt(pl[0], pl[1])?.y ?? 0) : null;
            return {
                x: pl[0], y: sy ?? (o.heightFn ? o.heightFn(pl[0], pl[1]) : (o.y ?? 0)), z: pl[1],
                yaw: pr() * Math.PI * 2,
                scale, tilt: 0, colorVar: pr(),
                phase: pr() * Math.PI * 2,
            };
        })
        : o.rows ? placeRows(o, spec)
        : placeInstances(o, spec);
    if (!inst.length) { console.warn('[grass2] zero instances placed'); }
    const count = inst.length;
    const posRot = new Float32Array(count * 4), scaleVar = new Float32Array(count * 4),
        phase = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const p = inst[i];
        posRot.set([p.x, p.y, p.z, p.yaw], i * 4);
        scaleVar.set([p.scale, p.scale * (0.85 + p.colorVar * 0.3), p.tilt, p.colorVar], i * 4);
        phase.set([p.phase, p.tx ?? 0, p.tz ?? 0], i * 3);
    }
    const geo = baseGeo;
    geo.setAttribute('aPosRot', new T3.InstancedBufferAttribute(posRot, 4));
    geo.setAttribute('aScaleVar', new T3.InstancedBufferAttribute(scaleVar, 4));
    geo.setAttribute('aPhase', new T3.InstancedBufferAttribute(phase, 3));

    // ── material ────────────────────────────────────────────────────────────
    const isBlades = spec.archetype === 'blades';
    const hasTransl = !!(maps && maps.transl);
    const MatClass = hasTransl ? T3.MeshSSSNodeMaterial : T3.MeshStandardNodeMaterial;
    const mat = new MatClass({
        side: T3.DoubleSide, metalness: 0, roughness: spec.rough,
        alphaTest: maps ? 0.35 : 0, transparent: false,
    });
    // (vertex colour is read in colorNode below — setting material.vertexColors
    // too would apply it twice and square the colour toward black)

    const uT = uniform(0);
    const uWindDir = uniform(new T3.Vector2(o.windDir[0], o.windDir[1]).normalize());
    const uBase = uniform(spec.wind.base * (o.wind ?? 1));
    const uGust = uniform(spec.wind.gust * (o.wind ?? 1));
    const uGustFreq = uniform(spec.wind.gustFreq);
    const uSunDir = uniform(new T3.Vector3(...o.sunDir).normalize());
    const pushArr = uniformArray([new T3.Vector4(0, 0, 0, 0), new T3.Vector4(0, 0, 0, 0),
        new T3.Vector4(0, 0, 0, 0), new T3.Vector4(0, 0, 0, 0)]);

    const aPR = attribute('aPosRot'), aSV = attribute('aScaleVar'),
        aPh = attribute('aPhase'), aHgt = attribute('aH');

    // full instance transform in the vertex stage (the CK42BB layout):
    // scale → tilt(X) → yaw(Y) → translate → wind → push
    mat.positionNode = Fn(() => {
        let p = positionLocal.mul(vec3(aSV.x, aSV.y, aSV.x)).toVar();
        const cR = cos(aPR.w), sR = sin(aPR.w);
        p = vec3(p.x.mul(cR).sub(p.z.mul(sR)), p.y, p.x.mul(sR).add(p.z.mul(cR))).toVar();
        // world tilt (aPhase.yz): random lean + the stroke's surface-normal
        // share, applied post-yaw about world X then Z — plants follow the
        // geometry they grow from
        const cX = cos(aPh.y), sX = sin(aPh.y);
        p = vec3(p.x, p.y.mul(cX).sub(p.z.mul(sX)), p.y.mul(sX).add(p.z.mul(cX))).toVar();
        const cZ = cos(aPh.z), sZ = sin(aPh.z);
        p = vec3(p.x.mul(cZ).sub(p.y.mul(sZ)), p.x.mul(sZ).add(p.y.mul(cZ)), p.z).toVar();
        const world = p.add(aPR.xyz).toVar();

        const hF = aHgt, h2 = hF.mul(hF);
        // layer 1 — global sway
        const gPhase = dot(world.xz, uWindDir).mul(0.5).add(uT.mul(1.2));
        const gSway = uWindDir.mul(sin(gPhase)).mul(uBase).toVar();
        // layer 2 — gust fronts rolled by a noise envelope
        const gustPhase = dot(world.xz, uWindDir).mul(uGustFreq).add(uT.mul(2.5));
        const env = smoothstep(0.3, 0.7,
            texNode(gustTex(), world.xz.mul(0.02).add(vec2(uT.mul(0.3 / 8))) ).r);
        const gustSway = uWindDir.mul(sin(gustPhase)).mul(uGust).mul(env).toVar();
        // layer 3 — per-instance flutter
        const tPhase = uT.mul(3.0).add(aPh.x);
        const turb = vec2(sin(tPhase), cos(tPhase.mul(0.7))).mul(0.1 * spec.wind.flutter).toVar();

        const windXZ = gSway.add(gustSway).add(turb).mul(h2).toVar();

        // pushers — quadratic falloff ×h² (CK42BB layout), evaluated PER
        // INSTANCE from the plant's root so the whole plant leans coherently
        // away (per-vertex directions made clusters pinwheel), with a species
        // stiffness and a SOFT lean ceiling
        const pushK = spec.pushScale ?? 1.0;
        const push = vec2(0, 0).toVar();
        for (let i = 0; i < 4; i++) {
            const P = pushArr.element(i);
            const delta = aPR.xz.sub(P.xz);                 // root → pusher, stable per plant
            const dTrue = delta.length();
            // direction floor: delta/0.3 fades the response smoothly to zero
            // at the pusher centre instead of whipping 180° as the character
            // steps over a root — the field stays continuous through the
            // origin, so plants ease around a passing body
            const d = tmax(dTrue, 0.3);
            const live = step(0.001, P.w);                  // 0 when this pusher slot is off
            // strength falls off from the CLOSER of root and vertex — root-only
            // falloff let a metre-long corn leaf reach a walker whose radius
            // never saw its far-away root, and the blade clipped through the
            // body untouched. Direction stays root-based (per-vertex direction
            // is the old pinwheel bug).
            const vDist = world.xz.sub(P.xz).length();
            const s = float(1).sub(smoothstep(0.0, tmax(P.w, 0.001), tmin(dTrue, vDist))).toVar();
            push.addAssign(delta.div(d).mul(s.mul(s)).mul(1.35 * pushK).mul(live));
        }
        // soft saturation: tanh approaches the 0.6 lean ceiling asymptotically.
        // The old hard min() parked every close plant AT the cap, so walking
        // by snapped them between capped and easing states
        const pLen = tmax(push.length(), 1e-4);
        const pushCapped = push.mul(float(0.6).mul(tanh(pLen.div(0.6))).div(pLen));
        // push yields the WHOLE plant (roots 30%, tips 100%) — pure h² left
        // low branches pinned through a character's legs mid-crossing
        const pushH = hF.mul(0.7).add(0.3);
        const disp = windXZ.add(pushCapped.mul(pushH));
        return world.add(vec3(disp.x, float(0), disp.y));
    })();

    // per-instance yaw-rotated normals — the geometry turns in positionNode,
    // so the authored (bent) normals must turn with it or every plant is lit
    // as if the sun sat somewhere else (and the SSS lobe points wrong)
    const rotNormal = Fn(() => {
        const cR = cos(aPR.w), sR = sin(aPR.w);
        return transformNormalToView(vec3(
            normalLocal.x.mul(cR).sub(normalLocal.z.mul(sR)),
            normalLocal.y,
            normalLocal.x.mul(sR).add(normalLocal.z.mul(cR))));
    })();
    // base = instance-rotated vertex normal (up for grass, bent for shrub
    // sprays — a LIGHT-GATHER direction); detail = the tangent map's deviation
    // from the interpolated surface normal, decoded in the true geometric
    // frame. base + delta keeps the volume shading AND the surface relief.
    if (maps && maps.normal) {
        const relief = T3.normalMap(texNode(maps.normal)).sub(T3.normalView);
        mat.normalNode = normalize(rotNormal.add(relief.mul(0.85)));
    } else {
        mat.normalNode = rotNormal;
    }

    // colour: sheet albedo (or baked blade vertex colour) × per-instance shade
    const shade = float(1.0).add(aSV.w.sub(0.5).mul(0.15));
    let albRGB = maps ? texNode(maps.albedo).rgb : attribute('color');
    if (spec.leafTint) albRGB = albRGB.mul(vec3(...spec.leafTint));
    // recolor mode: hue from the target, detail from the atlas luminance —
    // the atlas's own hue is fully discarded (multiply can't unmake green)
    if (spec.leafRecolor) albRGB = luminance(albRGB).mul(vec3(...spec.leafRecolor));
    // regionTint: the stemTint idea scoped to one UV window of a trim sheet —
    // lets one part of a single-material plant shift hue (corn's plume region
    // toward tan) with no extra vertex buffer spent on a part id
    if (spec.regionTint) {
        const rt = spec.regionTint;
        const u = uvNode();
        const inR = step(float(rt.u0), u.x).mul(step(u.x, float(rt.u1)))
            .mul(step(float(rt.v0), u.y)).mul(step(u.y, float(rt.v1)));
        albRGB = albRGB.mul(mix(vec3(1, 1, 1), vec3(...rt.mul), inR));
    }
    mat.colorNode = albRGB.mul(shade);
    if (maps) {
        mat.opacityNode = texNode(maps.albedo).a;
        if (maps.rough) mat.roughnessNode = texNode(maps.rough).r.mul(spec.rough);
    }

    // backlit translucency: light coming from behind glows through the sheet
    const sssAmt = (o.sss ?? 1) * spec.sss;
    if (hasTransl) {
        // real per-light translucency (Barre-Brisebois via MeshSSSNodeMaterial)
        // — SeedThree's tuned foliage values, verbatim
        mat.thicknessColorNode = texNode(maps.transl).r.mul(float(sssAmt * 2.2));
        mat.thicknessDistortionNode = float(0.3);
        mat.thicknessAmbientNode = float(0.0);
        mat.thicknessAttenuationNode = float(1.0);
        mat.thicknessPowerNode = float(6.0);
        mat.thicknessScaleNode = float(3.0);
        mat.emissiveNode = albRGB.mul(0.08);     // faint fill so backfaces never go dead
    } else {
        // no translucency map — keep the cheap backlit approximation
        const V = normalize(cameraPosition.sub(positionWorld));
        const backlit = pow(saturate(dot(V.negate(), uSunDir)), 3.0);
        const sssTerm = albRGB.mul(0.5).mul(backlit).mul(sssAmt).mul(aHgt.mul(0.5).add(0.5));
        mat.emissiveNode = albRGB.mul(isBlades ? 0.2 : 0.1).add(sssTerm);
    }

    // shrub wood: second instanced mesh, same placement, real bark maps riding
    // the tube network's wrapped UVs (flat colour on visible branches is a
    // defect; stemColor is only the no-asset fallback)
    let stemMesh = null, stemMapsRef = null;
    if (shrubGeos && shrubGeos.stem) {
        {
            const stemGeo = shrubGeos.stem;
            stemGeo.setAttribute('aPosRot', new T3.InstancedBufferAttribute(posRot, 4));
            stemGeo.setAttribute('aScaleVar', new T3.InstancedBufferAttribute(scaleVar, 4));
            stemGeo.setAttribute('aPhase', new T3.InstancedBufferAttribute(phase, 3));
            stemMapsRef = spec.stem ? await loadStemMaps(spec.stem) : null;
            const stemMaps = stemMapsRef;
            const smat = new T3.MeshStandardNodeMaterial({
                metalness: 0, roughness: 0.9,
                color: spec.stemColor ?? 0x7a6a55,
            });
            if (stemMaps) {
                const tint = spec.stemTint ?? [1, 1, 1];
                smat.colorNode = texNode(stemMaps.albedo).rgb.mul(vec3(...tint)).mul(shade);
                if (stemMaps.rough) smat.roughnessNode = texNode(stemMaps.rough).r.mul(0.95);
            }
            smat.positionNode = mat.positionNode;           // same instance transform + wind
            smat.normalNode = mat.normalNode;               // same rotated lighting
            stemMesh = new T3.InstancedMesh(stemGeo, smat, count);
            for (let i = 0; i < count; i++) stemMesh.setMatrixAt(i, _m4.identity());
            stemMesh.instanceMatrix.needsUpdate = true;
            stemMesh.frustumCulled = false;
            stemMesh.userData.noSupportCheck = stemMesh.userData.noClippingCheck = true;
            stemMesh.userData.noCameraCollide = stemMesh.userData.noMotionCheck = true;
            stemMesh.userData.noWalkable = true;
            stemMesh.castShadow = true;             // solid wood casts honestly
        }
    }

    const mesh = new T3.InstancedMesh(geo, mat, count);
    for (let i = 0; i < count; i++) mesh.setMatrixAt(i, _m4.identity());
    mesh.instanceMatrix.needsUpdate = true;
    mesh.frustumCulled = false;
    mesh.userData.noSupportCheck = mesh.userData.noClippingCheck = true;
    mesh.userData.noCameraCollide = true; mesh.userData.noMotionCheck = true;
    mesh.userData.noWalkable = true;   // never a collider, even if passed to a controller
    mesh.receiveShadow = true;
    mesh.castShadow = false;                 // alpha cards stamp rectangles in the shadow pass

    const update = (t) => { uT.value = t || 0; };
    (globalThis._autoParticleSystems || (globalThis._autoParticleSystems = [])).push(update);

    const dispose = () => {
        const i = (globalThis._autoParticleSystems ?? []).indexOf(update);
        if (i >= 0) globalThis._autoParticleSystems.splice(i, 1);
        geo.dispose();
        mat.dispose();
        for (const t of maps ? [maps.albedo, maps.normal, maps.rough, maps.transl] : []) t?.dispose?.();
        if (stemMesh) { stemMesh.geometry.dispose(); stemMesh.material.dispose(); }
        for (const t of stemMapsRef ? [stemMapsRef.albedo, stemMapsRef.rough] : []) t?.dispose?.();
    };

    const setPushers = (list = []) => {
        for (let i = 0; i < 4; i++) {
            const p = list[i];
            pushArr.array[i].set(p ? p.x : 0, p ? (p.y ?? 0) : 0, p ? p.z : 0, p ? (p.r ?? 1.2) : 0);
        }
    };

    if (stemMesh) mesh.add(stemMesh);                    // rides along into the scene
    console.log(`[grass2] ${opts.species}: ${count} instances × ${geo.attributes.position.count} verts (${spec.archetype}${stemMesh ? '+stems' : ''})`);
    return { mesh, stemMesh, material: mat, update, setPushers, dispose,
        uniforms: { time: uT, windDir: uWindDir, base: uBase, gust: uGust, sunDir: uSunDir },
        count };
}

// helper-injection registration (HELPER_MODULES imports this file as an ES
// module; scenes call the globals like every other eidoverse helper)
globalThis.createFlora = createFlora;
globalThis.FLORA_SPECIES = FLORA_SPECIES;
globalThis.GRASS_COLORS = GRASS_COLORS;
globalThis.resetFloraOccupancy = resetFloraOccupancy;
