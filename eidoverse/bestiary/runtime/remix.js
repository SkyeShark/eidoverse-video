// remix.js: Claude's Creatures at runtime. It applies a recipe's RUNTIME layers to a Bestiary creature: the palette
// recolour from the mask packs, the display recipe (moods, a mood cycle, passing clouds, blue rings, photophores,
// iridophores, leucophores), the element (zone recolour, glow, surface layer), shader affixes, accessories on sockets
// and bone tweaks. Everything is deterministic from the seed.
//
//   import { create as createCreature } from './bestiary.js';
//   import { apply } from './remix.js';
//   const oct = await createCreature({ species: 'octopus', seed: 3 });
//   const rx = await apply(oct, block, { seed: 3, proxies: true });
//   rx.setMood('alarm_rings');                  // or let block.display.cycle run in rx.update(t)
//   rx.palette({ primary: '#3a6ea8' });         // a live zone recolour
//
// `block` is the RESOLVED runtime block from eidoverse/bestiary/remix/recipe.py resolve_runtime(recipe, manifest).
// That function is the one resolver over the one global element table (remix/elements.py). This file holds no
// element numbers of its own: study G's parts drifted because each carried its own palette (study G §4.4), and a copy
// here would drift the same way. What this file adds is per-instance JITTER from the instance seed. applyJitter() is
// the twin of recipe.apply_jitter(), and the rolls are the same bits as recipe.roll() (FNV-1a on the key, then
// bestiary.js's lowbias32 mix).
//
// Written against bestiary.js's api: group, bones (Map), sockets ({socket_*: Object3D}), uniforms (U: tint, darkAll,
// dark, eyering, spots, mottle, wet, fuzz, clouds, cloudK, cloudW, cloudApex, rings, ringFlash, ringScale, ringR, glow,
// glowScale, glowRate, glowColor, night, t; and the growth term's growGlow, growGlowI, growRate, growFade, growTint,
// filmIOR, filmLo, filmHi, filmThick, seeded from the glb's extras), setDisplay, palette, gltf; and against its exports,
// the display's builders (the skin's, the eye's and the growth pack's displayGrowth), growthMaterial and DISPLAY_KEYS.
// The display recipe drives bestiary's own display uniforms through
// api.setDisplay, and writes a key only when its recipe value CHANGES (a mood cycle, a crossfade, setMood): a static
// display is written once, so a scene's own oct.setDisplay() calls persist as they do without a remix (the engine runs
// _autoCreatures before renderFrame, so a scene that sets the display every frame wins either way). The keys are
// bestiary's DISPLAY_KEYS; one the recipe never names (darkAll, ringFlash: recipe.MOODS carries neither) is never
// written, so it stays the scene's. api.palette({tint}) keeps working: the tint multiplies after the zone remaps, as in
// bestiary.js, on the skin and (displayEye) the eye.
//
// The skin materials are REBUILT so the remix layers sit in the forge's colour-stack order (guide SKIN_AND_DETAIL §6):
// palette and element zones on the base pigment; the tint; bestiary's display (its display masks, the passing clouds);
// leucophores; bestiary's blue rings; the surface layer; the fuzz rim; bestiary's photophores. bestiary's display terms
// are bestiary.js's own builders (displayMasks ... displayPhotophores), called at those places over the remapped colour
// as skinMaterial() calls them over the base colour: one source, so a remixed creature shows the plain one's display
// (this file's mirror of them drifted behind the r4 review's corrections). bestiary places the photophores (ventral,
// about a third of the cells): a remix's photophore recipe drives their strength, colour, scale and rate, never their
// placement.
//
// A GROWN creature (work/bestiary/patches/material_ids_v2.md: the GROWTH pack on its skin, a growths mesh in its own
// material) remixes as bestiary.js shows it. The remix recolours the SKIN, never the crystals: on the skin every remix
// and display term is blended back by the pack's skinOnly where it lands, as skinMaterial() does with its own, so a
// growth texel keeps its family's look (its pigment under U.growTint, the ORM's roughness and metalness, the film and
// the glow from the glb's extras). The growths mesh renders in bestiary's growthMaterial(). The creature-wide affixes
// (rim_pulse, glint, cloak: they read no skin pack) reach both. A glb without the pack builds exactly the graphs it
// built before the growth term.
//
// Accessory items follow one contract (the fit proxies here are built to it): +Y up, +Z the item's front, +X its left,
// the origin the fit's seat point (a hat: its opening's centre; glasses: the bridge point). Glasses carry lens_L (+X)
// and lens_R (-X) whose pivots are the LENS CENTRES at (+-spacing / 2, 0, 0) in the item's authored units: the fit
// moves the lens line bridge_arch behind the bridge and turns each lens by lens_yaw toward its eye, in place. A rigged
// prop hinged elsewhere (the accessories fit system's glasses: work/bestiary/patches/accessories_fit.md §4) is seated
// by accessories.js wear(), not here. (B10c) A monocle is worn through accessories.js wear() from here (its chain hung
// to the wearer, as a worn one's), unless opts.items gives the item or the prop does not load.
//
// The ZONE BLEND has three twins that must agree: elements.zone_remap() (numpy, the reference), zoneRemapRGB() (scalar,
// checked by selfTest() against vectors printed by `python eidoverse/bestiary/remix/recipe.py --vectors`) and remapN()
// (the TSL graph, written term by term from the scalar). selfTest() runs in plain node. On the CPU the skin material
// builds to WGSL through three's WGSLNodeBuilder over bestiary.js's own create()
// (work/bestiary/patches/remix_sync/remix_skin_check.mjs); the render is untested until the engine probe.
import { DISPLAY_KEYS, displayPosition, displayMasks, displayClouds, displayRings, displayFuzz, displayPhotophores,
    displayEye, displayGrowth, growthMaterial } from './bestiary.js';
// THE COAT (runtime/coat.js; work/bestiary/patches/coat_runtime.md): the cloak on the cards keeps their coverage test
import { setCoatOpacity } from './coat.js';

const THREE = globalThis.THREE;

export const LUMA = [0.2126, 0.7152, 0.0722];
export const ENVELOPE = [0.010, 0.65];
const TAU = 6.283185307179586;
const ROLES = ['primary', 'soft', 'accent', 'pattern'];
// STAGE 2B (work/bestiary/patches/landing2b_remix.md): the skin's ground occlusion, as bestiary.js's skin takes it (its
// own import line here, apart from the one above, which the coat's hunk R1 reads as its anchor)
import { groundOcclusion } from './bestiary.js';
// (B10c) a recipe's monocle is worn through accessories.js (seatAccessories): the prop's loader
import { accessory as loadAccessory } from './accessories.js';

// ============================================================================================ deterministic rolls
export function keyId(key) {
    // FNV-1a 32 over the key's char codes (ASCII keys: the same bits as recipe.key_id)
    let h = 0x811C9DC5;
    for (let i = 0; i < key.length; i++) {
        h ^= key.charCodeAt(i);
        h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h >>> 0;
}

export function hash01(i, seed) {
    // bestiary.js's hash01, bit for bit (lowbias32 over i and seed) to [0, 1)
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 8) / 16777216;
}

export function roll(seed, key, i = 0) { return hash01((keyId(key) + i) >>> 0, seed); }

export function jitterRGB(rgb, seed, key, hueDeg, val) {
    // the twin of recipe.jitter_rgb: rotate about the grey axis by +-hueDeg, scale by 1 +- val
    const u1 = roll(seed, key + '.h'), u2 = roll(seed, key + '.v');
    const a = ((2.0 * u1 - 1.0) * hueDeg) * Math.PI / 180.0;
    const k = 1.0 / Math.sqrt(3.0), c = Math.cos(a), s = Math.sin(a);
    const [r, g, b] = rgb;
    const dot = k * (r + g + b);
    const cx = k * (b - g), cy = k * (r - b), cz = k * (g - r);
    const out = [r * c + cx * s + k * dot * (1 - c), g * c + cy * s + k * dot * (1 - c), b * c + cz * s + k * dot * (1 - c)];
    const f = 1.0 + (2.0 * u2 - 1.0) * val;
    return out.map((x) => Math.max(0.0, x * f));
}

export function applyJitter(block, seed) {
    // the twin of recipe.apply_jitter (keys and order identical; keys sorted as Python sorts ASCII)
    const b = JSON.parse(JSON.stringify(block));
    const J = b.jitter;
    for (const role of Object.keys(b.palette || {}).sort()) {
        const z = b.palette[role];
        if (z.target) z.target = jitterRGB(z.target, seed, 'pal.' + role, J.palette.hue_deg, J.palette.val);
    }
    if (b.element) {
        for (const role of Object.keys(b.element.zones || {}).sort()) {
            const z = b.element.zones[role];
            if (z.target && (z.absolute ?? 0) < 0.5) {
                z.target = jitterRGB(z.target, seed, 'el.' + role, J.element.hue_deg, J.element.val);
            }
        }
        const g = b.element.glow;
        if (g) g.rate = g.rate * (1.0 + J.glow.rate * (2.0 * roll(seed, 'glow.rate') - 1.0));
    }
    const cl = b.display.clouds;
    cl.k = cl.k * (1.0 + J.clouds.k * (2.0 * roll(seed, 'clouds.k') - 1.0));
    cl.w = cl.w * (1.0 + J.clouds.w * (2.0 * roll(seed, 'clouds.w') - 1.0));
    b.display.cycle_offset = roll(seed, 'display.cycle');
    return b;
}

// ============================================================================================ the zone blend (scalar)
const lum = (c) => c[0] * LUMA[0] + c[1] * LUMA[1] + c[2] * LUMA[2];
const clamp = (x, a, b) => Math.min(Math.max(x, a), b);

export function isIdentity(z) {
    return !z || (z.w === 0 && z.sat === 1 && z.val === 1 && (z.absolute ?? 0) === 0 && (z.rough ?? 0) === 0
        && (z.rough_w ?? 0) === 0 && (z.metal === null || z.metal === undefined));
}

function envelope(c, lo, hi) {
    const L = lum(c);
    const k = clamp(L, lo, hi) / Math.max(L, 1e-6);
    return c.map((x) => x * k);
}

function gamut(c) {
    const L = lum(c);
    const mx = Math.max(c[0], c[1], c[2]), mn = Math.min(c[0], c[1], c[2]);
    const kHi = (1.0 - L) / Math.max(mx - L, 1e-6), kLo = L / Math.max(L - mn, 1e-6);
    const k = Math.min(1.0, kHi, kLo);
    return c.map((x) => L + (x - L) * k);
}

export function zoneRemapRGB(c, z, lref, m = 1.0) {
    // the twin of elements.zone_remap: luminance-matched target, hue/chroma move, chroma x sat, luminance x val, the
    // skin envelope and gamut (rel); the absolute (metal) mode with its painted variation; mixed in by the mask
    if (isIdentity(z)) return c.slice();
    const L = lum(c);
    const T = z.target || null;
    const Tn = T ? T.map((x) => x * (L / Math.max(lum(T), 1e-4))) : c;
    const c1 = c.map((x, i) => x + (Tn[i] - x) * z.w);
    const c2 = c1.map((x) => L + (x - L) * z.sat);
    let out = gamut(envelope(c2.map((x) => x * z.val), ENVELOPE[0], ENVELOPE[1]));
    if ((z.absolute ?? 0) > 0 && T) {
        const ratio = clamp(Math.exp(z.detail * Math.log(Math.max(L / lref, 1e-4))), 0.25, 4.0);
        const ab = gamut(envelope(T.map((x) => x * ratio), 0.0, 1.0));
        out = out.map((x, i) => x + (ab[i] - x) * z.absolute);
    }
    return c.map((x, i) => x + (out[i] - x) * m);
}

// ============================================================================================ self-test (plain node)
// vectors printed by `python eidoverse/bestiary/remix/recipe.py --vectors` (2026-10-20)
const VECTORS = {
    keyId: { '': 2166136261, a: 3826002220, element: 1330461687, 'pal.primary': 3587389650, 'clouds.k': 2831928144 },
    roll: [[1, 'element', 0.6787837147712708], [7, 'affix.chance', 0.190476655960083],
        [123456, 'pal.soft.h', 0.4902210235595703], [2147483646, 'clouds.w', 0.5829058885574341],
        [0, 'display.cycle', 0.06478935480117798]],
    jitter: [[[0.46, 0.72, 0.83], 5, 'pal.primary', 6.0, 0.06, [0.45204888928086884, 0.7133133093268483, 0.8148977225377219]],
        [[1.0, 0.3, 0.03], 99, 'el.soft', 3.0, 0.04, [1.0219536804682225, 0.3102894225392604, 0.02823213588793331]]],
    remap: [
        [[0.292, 0.074, 0.037], { target: [1.0, 0.3, 0.03], w: 0.85, sat: 1.15, val: 1.1, absolute: 0.0, detail: 1.0, rough: 0.0, rough_to: null, rough_w: 0.0, metal: null }, 0.308, 0.8, [0.3186647345265158, 0.08222459373554636, 0.007399999999999997]],
        [[0.292, 0.074, 0.037], { target: null, w: 0.0, sat: 0.3, val: 0.8, absolute: 0.0, detail: 1.0, rough: 0.12, rough_to: null, rough_w: 0.0, metal: null }, 0.118, 0.8, [0.16718257920000001, 0.0817265792, 0.06722257920000001]],
        [[0.571, 0.242, 0.184], { target: [0.15, 0.55, 0.65], w: 0.8, sat: 1.0, val: 1.05, absolute: 0.0, detail: 1.0, rough: 0.0, rough_to: null, rough_w: 0.0, metal: null }, 0.308, 0.8, [0.27582749222754027, 0.3299541381676479, 0.3524097996526749]],
        [[0.292, 0.074, 0.037], { target: [0.562, 0.565, 0.578], w: 1.0, sat: 1.0, val: 1.0, absolute: 1.0, detail: 0.35, rough: 0.0, rough_to: 0.45, rough_w: 1.0, metal: 0.9 }, 0.118, 0.8, [0.5075667390576957, 0.4663644262768647, 0.46935440422659785]],
        [[0.776, 0.617, 0.515], { target: [0.8, 0.8, 0.8], w: 1.0, sat: 1.0, val: 1.0, absolute: 1.0, detail: 0.0, rough: 0.0, rough_to: 0.03, rough_w: 1.0, metal: 1.0 }, 0.644, 0.8, [0.7952, 0.7634000000000001, 0.7430000000000001]],
        [[0.05, 0.02, 0.6], { target: [1.0, 0.92, 0.08], w: 0.8, sat: 1.0, val: 1.15, absolute: 0.0, detail: 1.0, rough: 0.0, rough_to: null, rough_w: 0.0, metal: null }, 0.308, 0.8, [0.0765222693870099, 0.060416487836049096, 0.23498578155096073]],
        [[0.235, 0.06, 0.031], { target: [0.2, 0.01, 0.03], w: 0.8, sat: 1.0, val: 0.45, absolute: 0.0, detail: 1.0, rough: 0.0, rough_to: null, rough_w: 0.0, metal: null }, 0.095, 0.8, [0.16960318839461397, 0.021604159419730692, 0.024284478259192097]],
    ],
};

export function selfTest(log = console.log) {
    const fails = [];
    const near = (a, b, tol) => Math.abs(a - b) <= tol;
    for (const [k, v] of Object.entries(VECTORS.keyId)) if (keyId(k) !== v) fails.push(`keyId(${JSON.stringify(k)}) ${keyId(k)} != ${v}`);
    for (const [s, k, v] of VECTORS.roll) if (roll(s, k) !== v) fails.push(`roll(${s}, ${k}) ${roll(s, k)} != ${v}`);
    for (const [c, s, k, h, v, want] of VECTORS.jitter) {
        const got = jitterRGB(c, s, k, h, v);
        if (!got.every((x, i) => near(x, want[i], 1e-12))) fails.push(`jitterRGB(${k}) ${got} != ${want}`);
    }
    for (const [c, z, lref, m, want] of VECTORS.remap) {
        const got = zoneRemapRGB(c, z, lref, m);
        if (!got.every((x, i) => near(x, want[i], 1e-12))) fails.push(`zoneRemapRGB(${JSON.stringify(z.target)}) ${got} != ${want}`);
    }
    let mean = 0;
    for (let s = 0; s < 20000; s++) mean += roll(s, 'dist') / 20000;
    if (!near(mean, 0.5, 0.01)) fails.push(`roll mean ${mean}`);
    const n = Object.keys(VECTORS.keyId).length + VECTORS.roll.length + VECTORS.jitter.length + VECTORS.remap.length + 1;
    log(`[remix] selfTest: ${n - fails.length}/${n} ok` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
    return { ok: fails.length === 0, fails };
}

// ============================================================================================ TSL helpers
function lumN(c) { return THREE.dot(c, THREE.vec3(LUMA[0], LUMA[1], LUMA[2])); }

function rampN(x, lo, hi) { return x.sub(lo).div(Math.max(hi - lo, 1e-6)).clamp(0.0, 1.0); }

function envelopeN(c, lo, hi) {
    const L = lumN(c);
    return c.mul(L.clamp(lo, hi).div(L.max(1e-6)));
}

function gamutN(c) {
    const { vec3, float, max, min } = THREE;
    const L = lumN(c);
    const mx = max(c.x, max(c.y, c.z)), mn = min(c.x, min(c.y, c.z));
    const kHi = float(1.0).sub(L).div(mx.sub(L).max(1e-6));
    const kLo = L.div(L.sub(mn).max(1e-6));
    const k = min(float(1.0), min(kHi, kLo));
    return vec3(L).add(c.sub(vec3(L)).mul(k));
}

function lshN(c, kl, ks) {
    const L = lumN(c);
    const g = THREE.vec3(L);
    return g.add(c.sub(g).mul(ks)).mul(kl);
}

function remapN(c, Z, m) {
    // the TSL twin of zoneRemapRGB, term by term (uniforms, so remixes change without recompiling)
    const { vec3, mix } = THREE;
    const L = lumN(c);
    const Tn = Z.T.mul(L.div(lumN(Z.T).max(1e-4)));
    const c1 = mix(c, Tn, Z.w);
    const c2 = vec3(L).add(c1.sub(vec3(L)).mul(Z.sat));
    const rel = gamutN(envelopeN(c2.mul(Z.val), ENVELOPE[0], ENVELOPE[1]));
    const ratio = L.div(Z.lref).max(1e-4).log().mul(Z.detail).exp().clamp(0.25, 4.0);
    const ab = gamutN(envelopeN(Z.T.mul(ratio), 0.0, 1.0));
    return mix(c, mix(rel, ab, Z.abs), m.mul(Z.on));
}

function zoneUniforms(z, lref) {
    const { uniform } = THREE;
    const U = {
        T: uniform(new THREE.Vector3(1, 1, 1)), w: uniform(0.0), sat: uniform(1.0), val: uniform(1.0),
        abs: uniform(0.0), detail: uniform(1.0), lref: uniform(lref ?? 0.2), on: uniform(0.0), rough: uniform(0.0),
        roughTo: uniform(0.0), roughW: uniform(0.0), metal: uniform(0.0), metalW: uniform(0.0),
    };
    setZoneUniforms(U, z, lref);
    return U;
}

function setZoneUniforms(U, z, lref) {
    const id = isIdentity(z);
    const t = z && z.target ? z.target : [1, 1, 1];
    U.T.value.set(t[0], t[1], t[2]);
    // no target, no hue move (the scalar twin's Tn = c): w would otherwise pull toward the grey placeholder target
    U.w.value = z?.target ? (z.w ?? 0.0) : 0.0;
    U.sat.value = z?.sat ?? 1.0;
    U.val.value = z?.val ?? 1.0;
    U.abs.value = z?.target ? (z.absolute ?? 0.0) : 0.0;
    U.detail.value = z?.detail ?? 1.0;
    if (lref != null) U.lref.value = lref;
    U.on.value = id ? 0.0 : 1.0;
    U.rough.value = z?.rough ?? 0.0;
    U.roughTo.value = z?.rough_to ?? 0.0;
    U.roughW.value = z?.rough_to != null ? (z.rough_w ?? 0.0) : 0.0;
    U.metal.value = z?.metal ?? 0.0;
    U.metalW.value = z?.metal != null ? 1.0 : 0.0;
}

function zoneMaskN(name, zones, packs, cache) {
    // a zone from the species' mask map (block.zones): max of weighted linear ramps over pack channels, or 1 - another
    if (cache[name]) return cache[name];
    const z = zones[name];
    let m = null;
    if (!z) m = THREE.float(0.0);
    else if (z.one_minus) m = zoneMaskN(z.one_minus, zones, packs, cache).oneMinus();
    else {
        for (const [ch, w, lo, hi] of z.max || []) {
            const [pk, c] = ch.split('.');
            if (!packs[pk]) continue;
            const t = rampN(packs[pk][c], lo, hi).mul(w);
            m = m ? THREE.max(m, t) : t;
        }
        if (!m) m = THREE.float(0.0);
    }
    cache[name] = m;
    return m;
}

function packChannel(spec, packs, fallback) {
    // 'masks.a' -> the node, or a constant
    if (typeof spec !== 'string') return THREE.float(fallback);
    const [pk, c] = spec.split('.');
    return packs[pk] ? packs[pk][c] : THREE.float(fallback);
}

function smoothN(a, b, x) { return THREE.smoothstep(a, b, x); }

function pulseN(bands, rate, fade, phase, t) {
    // the creature skin material's pulse (REF §1, R10): saturate(0.5 + 0.5 sin(2 pi (bands * phase + rate * t)) + fade)
    return THREE.sin(phase.mul(bands).add(t.mul(rate)).mul(TAU)).mul(0.5).add(0.5).add(fade).clamp(0.0, 1.0);
}

function gainOf(colour, L, scale) { return L / Math.max(lum(colour), 1e-4) * scale; }

// ============================================================================================ the uniforms of a remix
function buildUniforms(block, api) {
    const { uniform } = THREE;
    const zones = block.zones || {};
    const el = block.element || {};
    const R = { palette: {}, element: {} };
    for (const role of ROLES) {
        const lref = zones[role]?.lref ?? 0.2;
        R.palette[role] = zoneUniforms(block.palette?.[role], lref);
        R.element[role] = zoneUniforms(el.zones?.[role], lref);
    }
    R.paletteEye = zoneUniforms(block.palette?.eye, 0.25);
    R.palettePart = zoneUniforms(block.palette?.part, 0.25);
    R.partElement = zoneUniforms((block.element_policy ?? 'inherit') === 'inherit' ? el.zones?.primary : null, 0.05);
    const th = el.thin;
    R.thinT = uniform(new THREE.Vector3(...(th ? th.colour : [0.80, 0.45, 0.15])));
    R.thinW = uniform(th ? th.w : 0.0);
    const g = el.glow;
    R.glowC = uniform(new THREE.Vector3(...(g ? g.colour : [0, 0, 0])));
    R.glowGain = uniform(g ? (g.gain ?? gainOf(g.colour, g.L, block.glow_scale ?? 1.6)) : 0.0);
    R.glowBands = uniform(g ? g.bands : 1.0);
    R.glowRate = uniform(g ? g.rate : 0.0);
    R.glowFade = uniform(g ? g.fade : 0.0);
    R.glowTravel = uniform(g && g.phase === 'travel' ? 1.0 : 0.0);
    R.glowK = uniform(g ? (g.travel_k ?? 40.0) : 40.0);
    const s = el.surface;
    R.surface = uniform(s ? s.amount : 0.0);
    R.surfaceBreak = uniform(0.5);
    const d = block.display || {};
    R.leuco = uniform(d.base?.leuco ?? d.weights?.leuco ?? 0.0);
    const ir = d.iridophores;
    R.irid = uniform(ir ? ir.strength : 0.0);
    R.iridIor = uniform(ir ? ir.ior : 1.3);
    R.iridT0 = uniform(ir ? ir.thickness[0] : 100.0);
    R.iridT1 = uniform(ir ? ir.thickness[1] : 400.0);
    R.affix = {};
    for (const a of block.affixes || []) {
        if (a.kind === 'fx') continue;
        R.affix[a.name] = {
            C: uniform(new THREE.Vector3(...(a.colour || [1, 1, 1]))),
            gain: uniform(a.colour ? gainOf(a.colour, a.L ?? 1.0, block.glow_scale ?? 1.6) : 0.0),
            rate: uniform(a.rate ?? 1.0), density: uniform(a.density ?? 0.02), power: uniform(a.power ?? 3.0),
            period: uniform(a.period ?? 3.0), width: uniform(a.width ?? 0.04), opacity: uniform(a.opacity ?? 0.25),
            edge: uniform(a.edge ?? 0.9),
        };
    }
    // the glint's sweep range: the meshes' bind-pose bounds in y, in the space the glint reads (positionLocal: mesh-local;
    // the group's world box would shift with wherever the scene had placed the creature)
    const box = new THREE.Box3();
    api.group.traverse((o) => {
        if (!o.isMesh || !o.geometry) return;
        if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
        if (o.geometry.boundingBox) box.union(o.geometry.boundingBox);
    });
    R.y0 = uniform(Number.isFinite(box.min.y) ? box.min.y : 0.0);
    R.y1 = uniform(Number.isFinite(box.max.y) ? box.max.y : 1.0);
    return R;
}

// ============================================================================================ materials
function surfaceTerms(kind, R, ctx) {
    // the element's surface layer at runtime (elements.SURFACES): coverage w by AO and world-up, broken by the mottle
    const { vec3, float, mix } = THREE;
    const { ao, ny, cells, mottle } = ctx;
    const amt = R.surface;
    const brk = mix(float(1.0), smoothN(0.2, 0.8, mottle), R.surfaceBreak);
    const out = { w: float(0.0), albedo: vec3(0, 0, 0), roughAdd: float(0.0), roughTo: null, metalTo: null,
        metalMul: null, fuzz: null, spec: null, glow: float(0.0), ember: null, rim: false };
    if (kind === 'frost_exposed') {
        out.w = amt.mul(smoothN(0.3, 1.0, ao)).mul(ny.mul(0.15).add(0.55)).mul(brk).clamp(0, 1);
        out.albedo = vec3(0.46, 0.72, 0.83); out.roughAdd = out.w.mul(0.10); out.metalMul = float(1.0).sub(out.w.mul(0.5));
        out.fuzz = out.w;
    } else if (kind === 'frost_recess') {
        out.w = amt.mul(float(1.0).sub(smoothN(0.4, 0.95, ao)).mul(0.75).add(0.2)).mul(brk).clamp(0, 1);
        out.albedo = vec3(0.46, 0.72, 0.83); out.roughAdd = out.w.mul(-0.15); out.spec = float(1.0).sub(out.w.mul(0.5));
        out.fuzz = out.w; out.glow = out.w.mul(0.5);
    } else if (kind === 'char') {
        out.w = amt.mul(smoothN(0.55, 0.95, ao)).mul(smoothN(-0.2, 0.8, ny).mul(0.6).add(0.4)).mul(brk).clamp(0, 1);
        out.albedo = vec3(0.035, 0.030, 0.028); out.roughTo = float(0.85);
        out.ember = float(1.0).sub(smoothN(0.2, 0.55, ao)).mul(amt);
    } else if (kind === 'rust') {
        out.w = amt.mul(float(1.0).sub(smoothN(0.45, 0.95, ao)).mul(0.65).add(smoothN(0.1, 0.9, ny).mul(0.35))).mul(brk).clamp(0, 1);
        out.albedo = vec3(0.305, 0.065, 0.019); out.roughTo = float(0.85); out.metalTo = float(0.0);
    } else if (kind === 'patina') {
        out.w = amt.mul(float(1.0).sub(smoothN(0.35, 0.9, ao)).mul(0.85).add(smoothN(0.3, 0.9, ny).mul(0.15))).mul(brk).clamp(0, 1);
        out.albedo = vec3(0.056, 0.451, 0.423); out.roughTo = float(0.90); out.metalTo = float(0.0);
    } else if (kind === 'pustules') {
        const lo = float(1.0).sub(amt.mul(0.15));
        out.w = cells.sub(lo).div(0.004).clamp(0.0, 1.0);
        out.albedo = vec3(0.70, 0.80, 0.18); out.roughTo = float(0.08); out.glow = out.w.mul(0.6);
    } else if (kind === 'rim_arc') {
        out.rim = true;
    }
    return out;
}

function affixGlow(a, A, R, ndv, t) {
    // a CREATURE-WIDE affix's glow: rim_pulse (a pulsing rim) and glint (a band sweeping up the bind-pose height). They
    // read no skin pack (the pustules and the sparkle ride the skin's patch cells), so they mark the whole creature: a
    // grown skin's growth texels and the growths mesh take them too. null for the other effects
    const { float, pow, sin, smoothstep, fract, positionLocal } = THREE;
    if (a.effect === 'rim_pulse') {
        return A.C.mul(A.gain).mul(pow(float(1.0).sub(ndv), A.power)).mul(sin(t.mul(A.rate).mul(TAU)).mul(0.5).add(0.5));
    }
    if (a.effect === 'glint') {
        const y01 = positionLocal.y.sub(R.y0).div(R.y1.sub(R.y0).max(1e-3));
        const sweep = fract(t.div(A.period));
        const band = float(1.0).sub(smoothstep(0.0, A.width.div(R.y1.sub(R.y0).max(1e-3)), y01.sub(sweep).abs()));
        return A.C.mul(A.gain).mul(band).mul(float(1.0).sub(ndv).mul(0.7).add(0.3));
    }
    return null;
}

function affixOpacity(A, ndv) {
    // the cloak (stealthy): the whole creature see-through, its silhouette edges held; the growths too (a cloaked body
    // under opaque crystals would leave them hanging in the air)
    const { float, mix, pow } = THREE;
    return mix(A.opacity, float(1.0), pow(float(1.0).sub(ndv), 2.0).mul(A.edge));
}

function remixSkinMaterial(src, U, R, block, report) {
    const { texture, uv, vec3, vec4, float, mix, normalMap, normalView, normalWorld, positionViewDirection, pow, sin,
        fract } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshSSSNodeMaterial();
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    const disp = src.emissiveMap ? texture(src.emissiveMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    if (!src.thicknessMap || !src.emissiveMap) {
        report.push({ severity: 'error', code: 'packs.missing', message: `${src.name}: no ${!src.thicknessMap ? 'masks' : 'display'} pack: zones fall back to constants` });
    }
    const packs = { masks, display: disp };
    const zones = block.zones || {};
    const zc = {};
    const zone = (name) => zoneMaskN(name, zones, packs, zc);
    const cells = packChannel(zones.cells, packs, 0.5);
    const mottle = packChannel(zones.mottle, packs, 0.5);
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    const ao = orm.r;
    const ny = normalWorld.y;
    const pg = displayPosition();
    // the GROWTH pack (bestiary.js displayGrowth; null without one, and then this builds exactly the graph it built
    // before the growth term). Where its id mask holds a texel, the remix's terms hold off as skinMaterial's own do:
    // each is computed as on a plain skin and blended back by skinOnly where it lands (the zone remaps, the tint,
    // bestiary's display, the leucophores, the surface layer, the fuzz, the photophores, the skin's glow, the
    // iridophores, the roughness and metal edits, the subsurface floor), so a growth texel keeps its family's look
    const gr = displayGrowth(src, U, st);
    const gate = (before, after) => (gr ? mix(before, after, gr.skinOnly) : after);
    // ---- 1-3: palette and element zone remaps on the base pigment (broad to specific), the bestiary tint (a growth
    // texel: its own pigment under the growths' tint, U.growTint, as skinMaterial)
    let col = base.rgb;
    const pigment = col;
    let rough = mix(orm.g.add(0.18).min(1.0), orm.g, U.wet);          // bestiary.js's wet / dry lobe
    let metal = float(0.0);
    // a grown skin's metal runs the same chain from the skin's own metal in the ORM's B (round a root the element
    // halo's: patches/halo_v2.md), so the edits that lower metal (rust, verdigris, frost) act on it. The ORM's B also
    // holds a growth texel's metal, at most its share R, so the skin's is the part above R per unit of skin (B itself
    // where R is 0); the remix's own metal (from 0) still weights the fuzz and the subsurface cut
    let skinMetal = gr ? orm.b.sub(gr.grow.r).max(0.0).div(gr.skinOnly.max(1e-4)) : null;
    for (const layer of [R.palette, R.element]) {
        for (const role of ROLES) {
            const Z = layer[role];
            const zm = zone(role);
            col = remapN(col, Z, zm);
            const mo = zm.mul(Z.on);
            rough = mix(rough.add(Z.rough.mul(mo)), Z.roughTo, mo.mul(Z.roughW));
            metal = mix(metal, Z.metal, mo.mul(Z.metalW));
            if (skinMetal) skinMetal = mix(skinMetal, Z.metal, mo.mul(Z.metalW));
        }
    }
    col = gate(pigment, col).mul(gr ? mix(U.growTint, U.tint, gr.skinOnly) : U.tint);
    // ---- 4: bestiary's display, bestiary.js's own builders on the remapped colour (its uniforms, so api.setDisplay
    // works as on a plain creature): the display masks and the passing clouds, then the blue rings over the blanch
    col = gate(col, displayMasks(col, U, disp));
    const clouds = displayClouds(col, U, disp, masks, pg);
    col = gate(col, clouds.col);
    // leucophores (blanch: the skin scattering white, DESIGN.md skin display families): under the rings' iridophores
    col = gate(col, mix(col, envelopeN(lshN(col, 2.4, 0.35), ENVELOPE[0], ENVELOPE[1]), R.leuco));
    col = gate(col, displayRings(col, U, masks, pg));
    // ---- 5: the surface layer over everything so far (frost, char, rust bloom, patina, pustules; the rim fuzz and the
    // photophores' cups follow it)
    const sk = block.element?.surface?.kind;
    const S = sk ? surfaceTerms(sk, R, { ao, ny, cells, mottle }) : null;
    let fuzzW = U.fuzz;
    if (S) {
        col = gate(col, mix(col, S.albedo, S.w));
        rough = rough.add(S.roughAdd);
        if (S.roughTo) rough = mix(rough, S.roughTo, S.w);
        if (S.metalTo) metal = mix(metal, S.metalTo, S.w);
        if (S.metalMul) metal = metal.mul(S.metalMul);
        if (skinMetal && S.metalTo) skinMetal = mix(skinMetal, S.metalTo, S.w);
        if (skinMetal && S.metalMul) skinMetal = skinMetal.mul(S.metalMul);
        if (S.fuzz) fuzzW = mix(fuzzW, float(1.0), S.fuzz);
        if (S.spec) m.specularIntensityNode = gr ? mix(float(1.0), S.spec, gr.skinOnly) : S.spec;
    }
    // ---- 6: bestiary's rim fuzz (REF §1: albedo += 0.10 (1 - N.V)^2.5 on soft skin) at the surface layer's weight,
    // none on metal; then bestiary's photophores, last as in bestiary.js: by day each organ a dark cup in the albedo
    col = gate(col, displayFuzz(col, U, ndv, fuzzW.mul(float(1.0).sub(metal))));
    const ph = displayPhotophores(col, U, masks, pg, clouds.dAn);
    m.colorNode = ph ? gate(col, ph.col) : col;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.ior = 1.33;
    // a growth texel: its baked roughness (skinMaterial's) and its family's metalness (the ORM's B, which the forge
    // weights by the growth's share), the remix's roughness and metal edits held off: the growth's part of B,
    // min(B, R), plus the skin's chain by skinOnly. Within 1 on every texel, and B + m x skinOnly (the sum before the
    // halo) exactly wherever B <= R, the growths' partial-share edges among them
    m.roughnessNode = gr ? mix(rough.clamp(0.02, 1.0), orm.g, gr.grow.r) : rough.clamp(0.02, 1.0);
    m.metalnessNode = gr ? orm.b.min(gr.grow.r).add(skinMetal.clamp(0.0, 1.0).mul(gr.skinOnly))
        : metal.clamp(0.0, 1.0);
    m.aoNode = orm.r.mul(groundOcclusion(U, masks.g));    // (STAGE 2B: the surfaces near the sand, as bestiary.js's skin)
    // ---- emissive: bestiary's photophores (their glow, scaled by the night), the element glow on the glow mask
    // (mask^2, as the creature skin material; a travelling glow runs along the clouds' arc), embers, frost glow, pustule glow, the
    // arc rim, shader affixes. On a grown skin these are the skin's (held off growth texels) but for the creature-wide
    // affixes' glow (whole), and the growth glow is added (skinMaterial's)
    let emis = ph ? ph.emissive : vec3(0.0, 0.0, 0.0);
    let whole = null;
    const wholeGlow = (e) => { if (gr) whole = whole ? whole.add(e) : e; else emis = emis.add(e); };
    const t = U.t;
    const g = block.element?.glow;
    if (g || S?.ember || (S && (sk === 'pustules' || sk === 'frost_recess')) || S?.rim) {
        const phase = mix(cells, clouds.dAn.mul(R.glowK).div(TAU), R.glowTravel);
        const pulse = pulseN(R.glowBands, R.glowRate, R.glowFade, phase, t);
        const gm = zone('glow');
        const gc = R.glowC.mul(R.glowGain);
        if (g) emis = emis.add(gc.mul(gm.mul(gm)).mul(pulse));
        if (S?.ember) emis = emis.add(gc.mul(S.ember).mul(pulse));
        if (S && (sk === 'pustules' || sk === 'frost_recess')) emis = emis.add(gc.mul(S.glow).mul(pulse));
        if (S?.rim) {
            const flick = sin(t.mul(TAU * 9.0)).mul(0.5).add(0.5).mul(sin(t.mul(TAU * 2.3).add(1.7)).mul(0.5).add(0.5));
            emis = emis.add(gc.mul(pow(float(1.0).sub(ndv), 4.0)).mul(flick).mul(R.surface));
        }
    }
    for (const a of block.affixes || []) {
        const A = R.affix[a.name];
        if (!A) continue;
        if (a.effect === 'rim_pulse' || a.effect === 'glint') {
            wholeGlow(affixGlow(a, A, R, ndv, t));
        } else if (a.effect === 'ticking_pustules') {
            const on = cells.sub(float(1.0).sub(A.density)).div(0.004).clamp(0.0, 1.0);
            const tick = pow(sin(t.mul(A.rate).mul(TAU)).mul(0.5).add(0.5), 8.0);
            emis = emis.add(A.C.mul(A.gain).mul(on).mul(tick));
        } else if (a.effect === 'sparkle') {
            const sp = fract(cells.mul(91.7).add(t.mul(A.rate).floor().mul(0.618))).sub(float(1.0).sub(A.density)).div(0.002).clamp(0.0, 1.0);
            emis = emis.add(A.C.mul(A.gain).mul(sp));
        } else if (a.effect === 'cloak') {
            m.transparent = true;
            m.opacityNode = affixOpacity(A, ndv);
        }
    }
    m.emissiveNode = gr ? (whole ? emis.mul(gr.skinOnly).add(whole) : emis.mul(gr.skinOnly)).add(gr.emissive) : emis;
    // ---- thin-film iridescence: the remix's zone-masked iridophores (bestiary's rings carry their blue in the albedo).
    // A grown skin: the growths' film on growth texels (the pack's G at the family's film IOR, the skin's one thickness:
    // skinMaterial's), the iridophores held off them (one film per material: its weight, IOR and thickness by skinOnly)
    const ir = block.display?.iridophores;
    if (ir) {
        const irid = R.irid.mul(zone(ir.zone || 'accent'));
        const iridT = mix(R.iridT0, R.iridT1, cells);
        m.iridescenceNode = gr ? irid.mul(gr.skinOnly).add(gr.grow.g) : irid;
        m.iridescenceIORNode = gr ? mix(U.filmIOR, R.iridIor, gr.skinOnly) : R.iridIor;
        m.iridescenceThicknessNode = gr ? mix(U.filmThick, iridT, gr.skinOnly) : iridT;
    } else if (gr) {
        m.iridescenceNode = gr.grow.g;
        m.iridescenceIORNode = U.filmIOR;
        m.iridescenceThicknessNode = U.filmThick;
    }
    // ---- subsurface through thin tissue (bestiary.js's terms: the amber of haemocyanin-tinted tissue, tinted by the
    // element, off where metal). A grown skin: the metal cut is the skin's alone (the forge already fades the thin
    // channel on growth texels). (STAGE 4: on the thin mask alone, as skinMaterial's: its 0.06 floor lit thick flesh
    // gold where the sun backlit it, patches/stage4_skin_transmission.md)
    const thinC = mix(vec3(0.80, 0.45, 0.15), R.thinT, R.thinW);
    m.thicknessColorNode = gr
        ? thinC.mul(masks.r.mul(0.85)).mul(float(1.0).sub(metal.mul(gr.skinOnly)))
        : thinC.mul(masks.r.mul(0.85)).mul(float(1.0).sub(metal));
    m.thicknessDistortionNode = float(0.12);
    m.thicknessAmbientNode = float(0.02);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(3.0);
    m.thicknessScaleNode = float(3.5);
    m.name = (src.name || 'skin') + '_remix';
    return m;
}

function remixEyeMaterial(src, U, R) {
    // bestiary.js eyeMaterial() with the palette's eye remap (iris recolour; the dark pupil keeps its luminance): its
    // one lobe at the cornea's ior 1.34, and bestiary's eye display (displayEye) over the remapped iris, so the tint and
    // the dark display reach the chromatophores and cover the iridophore band (the masks pack's G; patches/eye.md) as
    // on a plain creature (this eye read neither U.tint nor U.darkAll)
    const { texture, uv, float, vec4, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0);
    const eye = displayEye(remapN(texture(src.map, st).rgb, R.paletteEye, float(1.0)), U, masks);
    m.colorNode = eye.col;
    if (src.normalMap) m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = texture(src.roughnessMap, st).g;
    m.metalnessNode = float(0.0);
    m.ior = 1.34;
    m.iridescenceNode = eye.band;
    m.iridescenceIORNode = float(2.0);
    m.iridescenceThicknessNode = float(220.0);
    m.name = 'eye_remix';
    return m;
}

function remixPartMaterial(src, R, Zel = R.partElement) {
    // bestiary.js beakMaterial() with the palette's part remap and, when the part inherits the body's element, the
    // element's PRIMARY zone (study G: every part takes the primary colour; one element instance for body and parts, study G
    // study §8.3). Zel: this part's element zone (its row's element_policy: inherit -> the primary zone, else identity)
    const { texture, uv, float, normalMap, mix } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    let col = remapN(texture(src.map, st).rgb, R.palettePart, float(1.0));
    col = remapN(col, Zel, float(1.0));
    const Z = Zel;
    m.colorNode = col;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = mix(texture(src.roughnessMap, st).g.add(Z.rough.mul(Z.on)), Z.roughTo, Z.roughW.mul(Z.on)).clamp(0.02, 1.0);
    m.metalnessNode = Z.metal.mul(Z.metalW).mul(Z.on);
    m.ior = 1.55;
    m.clearcoatNode = float(0.5);
    m.clearcoatRoughnessNode = float(0.08);
    m.name = 'part_remix';
    return m;
}

function remixGrowthMaterial(src, U, R, block, opts) {
    // the GROWTHS mesh (material extras bestiary 'growth'): bestiary.js growthMaterial() over the glTF source, as the
    // plain creature renders it (the family's surface baked by the forge, metalness in the ORM's B, the film and the
    // glow from the glb's extras through bestiary's uniforms, U.growTint and api.growth(); refraction when asked:
    // opts.growTrans, growThickness, growIOR). Never recoloured: the palette, the element's zones, glow, thin tint and
    // surface layer, the display and the iridophores are the skin's, read through the skin's packs (the growths' masks
    // pack means other things), and every one of them is held off the skin's growth texels too. Only the creature-wide
    // affixes reach it, as they reach those texels: rim_pulse and glint (glow), the cloak (opacity)
    const { normalView, positionViewDirection } = THREE;
    const m = growthMaterial(src, U, opts);
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    let whole = null;
    for (const a of block.affixes || []) {
        const A = R.affix[a.name];
        if (!A) continue;
        const e = affixGlow(a, A, R, ndv, U.t);
        if (e) {
            whole = whole ? whole.add(e) : e;
        } else if (a.effect === 'cloak') {
            m.transparent = true;
            m.opacityNode = affixOpacity(A, ndv);
        }
    }
    if (whole) m.emissiveNode = m.emissiveNode ? m.emissiveNode.add(whole) : whole;
    m.name = (src.name || 'growth') + '_remix';
    return m;
}

async function sourceOf(api, mesh) {
    // the glTF material a mesh was loaded with (bestiary.js replaced it): through the parser's associations, else by
    // name; its maps are the textures bestiary.js bound
    const parser = api.gltf?.parser;
    if (!parser) return null;
    let idx = null;
    const as = parser.associations?.get(mesh);
    if (as && as.meshes !== undefined && as.primitives !== undefined) {
        idx = parser.json.meshes[as.meshes].primitives[as.primitives].material ?? null;
    }
    if (idx === null) {
        // by name: bestiary.js names a skin material '<glTF name>_bestiary' but its eye and beak 'eye_bestiary' and
        // 'beak_bestiary' (this file: 'eye_remix', 'part_remix'), so those match the one glTF material of their kind;
        // its growths '<glTF name>_bestiary' (this file: '_remix'), a nameless one 'growth_...'. A part is neither skin,
        // eye nor growths (on a grown creature the growths would make the beak's 'part' ambiguous)
        const defs = parser.json.materials || [];
        const nm = String(mesh.material?.name || '').replace(/_(bestiary|remix)$/, '');
        let k = defs.findIndex((d) => d.name === nm);
        if (k < 0 && (nm === 'eye' || nm === 'beak' || nm === 'part' || nm === 'growth')) {
            const kindOf = (d) => d.extras?.bestiary || (/eye/.test(d.name || '') ? 'eye' : /beak/.test(d.name || '') ? 'beak'
                : /growth/.test(d.name || '') ? 'growth' : 'skin');
            const want = (d) => (nm === 'part' ? !['skin', 'eye', 'growth'].includes(kindOf(d)) : kindOf(d) === nm);
            const hits = defs.map((d, i) => (want(d) ? i : -1)).filter((i) => i >= 0);
            if (hits.length === 1) k = hits[0];
        }
        idx = k >= 0 ? k : null;
    }
    if (idx === null) return null;
    return { src: await parser.getDependency('material', idx), def: parser.json.materials[idx], index: idx };
}

// ============================================================================================ accessories
function proxyFor(arch, item, entry) {
    // FIT PROXIES (primitives at the item's authored size, named proxy_*, built to the item contract in the header):
    // for checking a fit before the AAA props exist. Not a deliverable look. Sizes from the resolved entry's authored
    // sizes (recipe.resolve_accessory), else the catalog's (opts.catalog), else a human head's
    const { Group, Mesh, CylinderGeometry, TorusGeometry, SphereGeometry, BoxGeometry } = THREE;
    const au = entry.authored || item?.authored || {};
    const mat = (hex, rough = 0.6, metal = 0.0) => {
        const mm = new THREE.MeshStandardNodeMaterial();
        mm.color = new THREE.Color(hex);
        mm.roughness = rough;
        mm.metalness = metal;
        return mm;
    };
    const g = new Group();
    g.name = `proxy_${entry.item}`;
    g.userData.proxy = true;
    const main = entry.colour ?? 0x2e2b28;
    if (arch === 'hat' || arch === 'helmet') {
        const r = au.radius ?? (arch === 'hat' ? 0.091 : 0.095);
        if (arch === 'hat') {
            // the crown's OPENING is the authored radius: scaled by fit.radius / authored it lands on the seat's section
            // (it was 0.82 r: the walls sank 9 mm into the octopus's mantle); a slight flare to the top
            const tube = new Mesh(new CylinderGeometry(r * 1.04, r * 1.0, r * 1.3, 32), mat(main));
            tube.position.y = r * 0.65;
            const brim = new Mesh(new CylinderGeometry(r * 1.45, r * 1.45, r * 0.05, 32), mat(main));
            brim.position.y = r * 0.025;
            const band = new Mesh(new CylinderGeometry(r * 1.015, r * 1.01, r * 0.22, 32), mat(entry.band ?? 0x7a1f2a, 0.55));
            band.position.y = r * 0.16;
            g.add(tube, brim, band);
        } else {
            // a hemisphere at 1.2 r: on the octopus it clears the mantle by >= 1.0 mm (verify/fit_check_sdf.py); the old
            // 0.55-pi dome reached below the seat plane and cut 5.4 mm into the dorsal mantle
            const dome = new Mesh(new SphereGeometry(r * 1.2, 32, 12, 0, TAU, 0, Math.PI * 0.5), mat(main, 0.45));
            g.add(dome);
        }
    } else if (arch === 'glasses') {
        const sp = au.spacing ?? 0.064;
        const lr = sp * 0.36;
        for (const [side, name] of [[1, 'lens_L'], [-1, 'lens_R']]) {
            // each lens pivots at its own centre (+X is the creature's left): seatAccessories moves the lens line back by
            // the fit's bridge_arch and turns each lens by lens_yaw toward its eye in place (the old hinge at the bridge
            // centre swung the lenses 35 mm off the octopus's eyes)
            const hinge = new Group();
            hinge.name = name;
            hinge.position.x = side * sp * 0.5;
            const ring = new Mesh(new TorusGeometry(lr, lr * 0.08, 8, 32), mat(main, 0.35, 0.4));
            const glass = new Mesh(new CylinderGeometry(lr * 0.95, lr * 0.95, lr * 0.03, 32), mat(0xcfe4f0, 0.05));
            glass.rotation.x = Math.PI / 2;
            hinge.add(ring, glass);
            g.add(hinge);
        }
        const bridge = new Mesh(new BoxGeometry(sp * 0.3, lr * 0.12, lr * 0.12), mat(main, 0.35, 0.4));
        bridge.name = 'bridge';                         // at the origin: the fit's bridge point
        g.add(bridge);
    } else if (arch === 'monocle') {
        const r = au.radius ?? 0.016;
        const ring = new Mesh(new TorusGeometry(r, r * 0.1, 8, 32), mat(0xc9a637, 0.25, 1.0));
        const glass = new Mesh(new CylinderGeometry(r * 0.95, r * 0.95, r * 0.04, 32), mat(0xcfe4f0, 0.05));
        glass.rotation.x = Math.PI / 2;
        g.add(ring, glass);
    } else if (arch === 'tie') {
        const w = au.width ?? 0.06;
        const c = entry.colour ?? 0x8a1f2c;
        const knot = new Mesh(new SphereGeometry(w * 0.16, 12, 8), mat(c, 0.5));
        g.add(knot);
        for (const side of [1, -1]) {
            const wing = new Mesh(new CylinderGeometry(0.0, w * 0.32, w * 0.7, 3), mat(c, 0.5));
            wing.rotation.z = side * Math.PI / 2;
            wing.position.x = side * w * 0.38;
            g.add(wing);
        }
    } else if (arch === 'mask') {
        const r = au.radius ?? 0.105;
        const face = new Mesh(new CylinderGeometry(r, r, r * 0.08, 32), mat(entry.colour ?? 0xf2c930, 0.5));
        face.rotation.x = Math.PI / 2;
        g.add(face);
    }
    return g;
}

async function itemObject(entry, opts) {
    // the item: opts.items[item] (an Object3D, a factory or a promise), else ASSETS['accessory_<item>'] (glb bytes),
    // else a fit proxy when opts.proxies, else null (reported)
    const it = opts.items?.[entry.item];
    if (it) return typeof it === 'function' ? await it(entry) : await it;
    const bytes = globalThis.ASSETS?.['accessory_' + entry.item];
    if (bytes && globalThis.GLTFLoader) {
        const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        return (await new globalThis.GLTFLoader().parseAsync(buf, '')).scene;
    }
    if (opts.proxies) return proxyFor(entry.archetype, opts.catalog?.[entry.item], entry);
    return null;
}

async function monocleProp(item) {
    // (B10c) the monocle's parsed prop for accessories.js wear(): its glb under remix.js's own ASSETS key, else accessories.js's
    // (its ASSETS key, else its file); null when neither loads (a browser page without the bytes)
    try {
        const bytes = globalThis.ASSETS?.['accessory_' + item];
        return await loadAccessory(item, bytes ? { bytes, path: 'accessory_' + item } : {});
    } catch (e) {
        return null;
    }
}

async function seatAccessories(api, list, opts, report) {
    const seated = [];
    for (const a of list || []) {
        const seat = a.seat;
        const parent = !seat ? null : seat.startsWith('bone:') ? api.bones.get(seat.slice(5)) : api.sockets[seat];
        if (!parent) { report.push({ severity: 'error', code: 'socket.missing', message: `${a.item}: seat ${seat} not on this creature` }); continue; }
        if (!a.fit) { report.push({ severity: 'error', code: 'accessory.fit_missing', message: `${a.item} on ${seat}: no fit` }); continue; }
        // (B10c) a MONOCLE is WORN, through accessories.js wear() as a worn one is (forge/props/monocle.py: the lens, its rim and its
        // cord ring on the eye socket by the socket's own fit.monocle, else the prop's conform record for the species; its CHAIN
        // hung to its end on the wearer every frame): the rigid seat below had no chain, so a remixed beetle and a worn one looked
        // different. The recipe's fit is passed only when it is the recipe's own (an override), or when the creature carries no
        // measured fit (no chain then); an item from opts.items, or a prop that will not load, keeps the rigid seat
        if (a.archetype === 'monocle' && !opts.items?.[a.item] && api.wear && !seat.startsWith('bone:')) {
            const acc = await monocleProp(a.item);
            if (acc) {
                let h = null, used = a.fit_source === 'override';
                try {
                    try {
                        h = api.wear(acc, used ? { socket: seat, fit: a.fit } : { socket: seat });
                    } catch (e) {
                        if (used) throw e;
                        h = api.wear(acc, { socket: seat, fit: a.fit });
                        used = true;
                    }
                } catch (e) {
                    report.push({ severity: 'warning', code: 'accessory.wear', message: `${a.item}: ${e.message || e}; seated rigidly` });
                }
                if (h) {
                    seated.push({ item: a.item, seat, holder: h.holder, handle: h, proxy: false, fit_source: a.fit_source, worn: true });
                    if (used && a.fit_source !== 'socket' && a.fit_source !== 'seat') {
                        report.push({ severity: 'warning', code: 'accessory.fit_override', message: `${a.item}: fit from the recipe (${a.fit_source}), not socket data` });
                    }
                    continue;
                }
            }
        }
        const obj = await itemObject(a, opts);
        if (!obj) { report.push({ severity: 'missing', code: 'accessory.asset', message: `${a.item}: no asset (opts.items, ASSETS.accessory_${a.item}) and no proxies` }); continue; }
        const holder = new THREE.Group();
        holder.name = `accessory_${a.item}`;
        holder.position.fromArray(a.fit.offset);
        holder.quaternion.fromArray(a.fit.rotation);
        holder.scale.setScalar(a.scale ?? 1.0);
        if (a.fit.contact_depth) holder.translateY(-a.fit.contact_depth);      // seated into the skin along its up
        if (a.fit.bridge_arch || a.fit.lens_yaw) {
            // glasses (the item contract): the lens line bridge_arch behind the bridge point (the holder's origin), each
            // lens turned toward its eye about its own centre (lens_L on +X, the creature's left, turns +lens_yaw). On
            // the octopus this puts both lens centres within 0.04 mm of the measured ones, 4 mm proud of the mounds
            const s = a.scale ?? 1.0;
            for (const [name, sgn] of [['lens_L', 1], ['lens_R', -1]]) {
                const L = obj.getObjectByName?.(name);
                if (!L) continue;
                if (a.fit.bridge_arch) L.position.z -= a.fit.bridge_arch / s;
                if (a.fit.lens_yaw) L.rotateY(sgn * a.fit.lens_yaw * Math.PI / 180);
            }
        }
        obj.traverse?.((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
        holder.add(obj);
        parent.add(holder);
        seated.push({ item: a.item, seat, holder, proxy: !!obj.userData?.proxy, fit_source: a.fit_source });
        if (a.fit_source && a.fit_source !== 'socket' && a.fit_source !== 'seat') {
            report.push({ severity: 'warning', code: 'accessory.fit_override', message: `${a.item}: fit from the recipe (${a.fit_source}), not socket data` });
        }
    }
    return seated;
}

// ============================================================================================ bones and display
function applyBones(api, ops, report) {
    for (const op of ops || []) {
        const rx = op.match ? new RegExp(op.match) : new RegExp('^' + String(op.bone).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$');
        const s = typeof op.scale === 'number' ? [op.scale, op.scale, op.scale] : (op.scale || [1, 1, 1]);
        let n = 0;
        for (const [name, b] of api.bones) if (rx.test(name)) { b.scale.set(s[0], s[1], s[2]); n++; }
        if (!n) report.push({ severity: 'error', code: 'bone.missing', message: `${op.match || op.bone} matches no bone` });
    }
}

function moodWeights(d, t, rest = {}) {
    // the display weights at time t: the cycle's mood (with its seeded offset), crossfading into the next over the
    // last `crossfade` seconds; or the resting weights. A key a mood leaves out keeps the RESTING value (d.base: the
    // recipe's weights and its photophore strength; a key only some moods name, the creature's own value in rest:
    // ringFlash rests at 1, and a 0 there would cover every ring's blue). Pure in (d, t, rest)
    const moods = d.moods || {};
    const base = { ...rest, ...(d.base || d.weights || {}) };
    const cyc = d.cycle || [];
    const val = (mood, k) => (mood && mood[k] != null ? mood[k] : (base[k] ?? 0));
    if (!cyc.length) {
        const out = {};
        for (const k of [...DISPLAY_KEYS, 'leuco']) out[k] = base[k] ?? 0;
        out._flash = [d.mood, d.mood, 0];
        return out;
    }
    const total = cyc.reduce((s, c) => s + c[1], 0);
    if (!(total > 0)) {
        // a cycle with no duration (the validator's display.cycle error): the resting weights, never NaN
        const out = {};
        for (const k of [...DISPLAY_KEYS, 'leuco']) out[k] = base[k] ?? 0;
        out._flash = [d.mood, d.mood, 0];
        return out;
    }
    let tt = ((t + (d.cycle_offset ?? 0) * total) % total + total) % total;
    let i = 0;
    while (tt >= cyc[i][1] && i < cyc.length - 1) { tt -= cyc[i][1]; i++; }
    const a = moods[cyc[i][0]], b = moods[cyc[(i + 1) % cyc.length][0]];
    const cf = Math.min(d.crossfade ?? 0.4, cyc[i][1]);
    let f = clamp((tt - (cyc[i][1] - cf)) / Math.max(cf, 1e-6), 0, 1);
    f = f * f * (3 - 2 * f);
    const out = {};
    for (const k of [...DISPLAY_KEYS, 'leuco']) out[k] = val(a, k) + (val(b, k) - val(a, k)) * f;
    out._flash = [cyc[i][0], cyc[(i + 1) % cyc.length][0], f];
    return out;
}

function setColour(u, rgb) { if (u && rgb) u.value.setRGB(rgb[0], rgb[1], rgb[2]); }

// ============================================================================================ apply / create
export async function apply(api, block, opts = {}) {
    // apply a resolved runtime block to a Bestiary creature; returns the remix controller. opts: seed (the instance
    // seed for the jitter; default block.seed), jitter (false to skip it), proxies (fit proxies for missing items),
    // items ({item: Object3D | factory}), catalog (recipe.ACCESSORIES: proxy sizes for a block whose accessory entries
    // lack their authored sizes; resolve_accessory now writes them), auto (default true: join the engine's
    // auto-update list like bestiary.js), growTrans / growThickness / growIOR (the growths' refraction, as bestiary.js
    // create() takes them: the growths material is rebuilt here, and create() below passes opts.create's)
    if (!THREE) throw new Error('[remix] globalThis.THREE (three r184 webgpu + TSL) is required');
    const report = [];
    const seed = opts.seed ?? block.seed ?? 1;
    const b = opts.jitter === false ? JSON.parse(JSON.stringify(block)) : applyJitter(block, seed);
    const U = api.uniforms;
    const R = buildUniforms(b, api);
    if (Array.isArray(b.envelope) && (Math.abs(b.envelope[0] - ENVELOPE[0]) > 1e-12 || Math.abs(b.envelope[1] - ENVELOPE[1]) > 1e-12)) {
        report.push({ severity: 'error', code: 'remap.envelope', message: `the block's skin envelope ${b.envelope} is not this file's ${ENVELOPE}: elements.ENVELOPE and remix.js disagree (re-sync ENVELOPE and the selfTest vectors)` });
    }
    // the element's wetness and fuzz, the display recipe's clouds, rings and photophores: bestiary.js's own uniforms.
    // The clouds' fronts start at the creature's mantle apex (cloudApex: its socket_mantle_apex at bind, a point; a
    // block may name another point as clouds.apex [x, y, z])
    if (b.element?.wet != null) U.wet.value = b.element.wet;
    if (b.element?.fuzz != null) U.fuzz.value = b.element.fuzz;
    const d = b.display || {};
    if (d.clouds) {
        U.cloudK.value = d.clouds.k;
        U.cloudW.value = d.clouds.w;
        if (Array.isArray(d.clouds.apex)) U.cloudApex.value.fromArray(d.clouds.apex);
    }
    if (d.rings) { U.ringScale.value = d.rings.scale; U.ringR.value = d.rings.r; }
    if (d.photophores) {
        const p = d.photophores;
        if (p.scale != null) U.glowScale.value = p.scale;
        if (p.rate != null) U.glowRate.value = p.rate;
        setColour(U.glowColor, p.colour);
    }
    // a part's element policy: its slot row's (block.parts, by the material it renders with), else the recipe's
    const topPolicy = b.element_policy ?? 'inherit';
    const policyOf = (matName) => {
        for (const row of Object.values(b.parts || {})) if (row && row.material === matName) return row.element_policy ?? topPolicy;
        return topPolicy;
    };
    const partZones = {};
    let beetleKinds = 0;                               // (B11) the beetle's cuticle / eye / membrane meshes kept as built
    // rebuild the materials
    const meshes = [];
    api.group.traverse((o) => { if (o.isMesh) meshes.push(o); });
    for (const o of meshes) {
        if (o.userData?.cyborgPart) continue;          // (a mounted cyborg part: its own glb, its own material)
        if (o.userData?.bestiaryCoat) continue;        // (the coat's cards: rebuilt below through coat.js)
        if (o.userData?.bestiaryAxolotl) continue;     // (AX12: the axolotl's own skin and eye, axolotl.js: its layers below)
        const s = await sourceOf(api, o);
        if (!s) { report.push({ severity: 'warning', code: 'material.source', message: `${o.name}: no glTF source material; left as is` }); continue; }
        // (bestiary.js routes by name alone: eye, beak, growth, else skin; t13 writes the kind into the extras)
        const kind = s.def?.extras?.bestiary || (/eye/.test(s.def?.name || '') ? 'eye' : /beak/.test(s.def?.name || '') ? 'beak'
            : /growth/.test(s.def?.name || '') ? 'growth' : 'skin');
        // a CYBORG PART keeps the material bestiary.js built for it (cyborgMaterial: its own set; the remix's palette
        // and element layers are the skin's; CYBORG_PLAN C9 brings the cyborg branch): the parts mounted from their own
        // glbs (skipped above) and any material whose extras say 'cyborg' (an implant spliced into the creature's glb)
        if (kind === 'cyborg') continue;
        // (B11) THE BEETLE'S OWN KINDS keep the materials bestiary.js built (beetle_cuticle.js: the clear coat, the compound eye,
        // the membranes): the remix's palette and element layers read the skin's packs as an octopus's, and remixPartMaterial
        // would draw the cuticle as a plain part. Its display.iridophores reach the cuticle's own film below (beetle_b58_runtime
        // .md's rule: never a second film over the one the builder carries)
        if (kind === 'cuticle' || kind === 'compound_eye' || kind === 'membrane') { beetleKinds++; continue; }
        const old = o.material;
        let Zel = R.partElement;
        if (kind !== 'skin' && kind !== 'eye' && kind !== 'growth') {
            const pol = policyOf(s.def?.name);
            if (pol === 'element_only') {
                report.push({ severity: 'missing', code: 'part.element_only', message: `${s.def?.name}: element_only parts render in the element's growth material, which the runtime does not have (the forge's growth families); drawn with its own material` });
            }
            if (pol !== topPolicy) {
                partZones[s.def?.name] ??= zoneUniforms(pol === 'inherit' ? b.element?.zones?.primary : null, 0.05);
                Zel = partZones[s.def?.name];
            }
        }
        if (kind === 'growth' && old?.transmissionNode && !((opts.growTrans ?? 0) > 0)) {
            report.push({ severity: 'warning', code: 'growth.refraction', message: `${s.def?.name}: the creature's growths refract (bestiary create()'s growTrans); apply() rebuilds them without it unless its opts carry growTrans (growThickness, growIOR)` });
        }
        o.material = kind === 'skin' ? remixSkinMaterial(s.src, U, R, b, report)
            : kind === 'eye' ? remixEyeMaterial(s.src, U, R)
                : kind === 'growth' ? remixGrowthMaterial(s.src, U, R, b, opts) : remixPartMaterial(s.src, R, Zel);
        if (old && old !== o.material && old.dispose) old.dispose();
    }
    R.partElements = partZones;
    // (B11) the beetle's iridescent FAMILY (recipe.resolve_display fills the named row in): the cuticle builder's own film through
    // api.family (beetle_cuticle.js setFamily), driven by its baked thickness; a recipe without a family leaves the base's
    if (beetleKinds && d.iridophores?.family && api.family) {
        try {
            api.family(d.iridophores.family, d.iridophores.strength);
        } catch (e) {
            report.push({ severity: 'error', code: 'display.iridophores', message: String(e.message || e) });
        }
    }
    // THE COAT (runtime/coat.js): the skin's coat layer again on the rebuilt skins (a material without a coat pack is
    // left as it is), then the cards' materials rebuilt with this remix's zone remap read at each card's root (the chain
    // remixSkinMaterial runs on the base pigment, palette then element, the tint after) and the creature-wide affixes as
    // the growths take them: rim_pulse and glint as glow, the cloak through setCoatOpacity (the cards keep their coverage
    // test: three multiplies alpha by the opacity before it)
    if (api.coatCtl) {
        for (const o of meshes) if (!o.userData?.bestiaryCoat && o.material) api.coatCtl.relayer(o.material);
        api.coatCtl.rebuild({
            remap: (col, packs) => {
                const zc = {};
                const zone = (name) => zoneMaskN(name, b.zones || {}, packs, zc);
                for (const layer of [R.palette, R.element]) for (const role of ROLES) col = remapN(col, layer[role], zone(role));
                return col;
            },
            affix: (m, ndv) => {
                let whole = null;
                for (const a of b.affixes || []) {
                    const A = R.affix[a.name];
                    if (!A) continue;
                    const e = affixGlow(a, A, R, ndv, U.t);
                    if (e) whole = whole ? whole.add(e) : e;
                    else if (a.effect === 'cloak') setCoatOpacity(m, affixOpacity(A, ndv));
                }
                if (whole) m.emissiveNode = m.emissiveNode ? m.emissiveNode.add(whole) : whole;
            },
        });
    }
    // (AX12) THE AXOLOTL'S OWN SKIN (runtime/axolotl.js: the pigment layers composed at runtime, the crease fade): this
    // remix's palette and element zone remaps, surface layer and glow rebuilt on it by axolotl.js with this file's own
    // builders (one source); its eye kept (the palette's eye remap reads an octopus iris)
    if (api.axolotl?.remix) {
        api.axolotl.remix(b, R, { ROLES, remapN, zoneMaskN, packChannel, surfaceTerms, pulseN });
        if (b.palette?.eye) report.push({ severity: 'warning', code: 'palette.eye', message: 'the axolotl keeps its own eye (no eye remap)' });
    }
    applyBones(api, b.bones, report);
    const seated = await seatAccessories(api, b.accessories, opts, report);
    for (const a of b.affixes || []) {
        if (a.needs_fx) report.push({ severity: 'missing', code: 'fx.contract', message: `${a.name}: ${a.fx} needs FX sockets and a particle system (not drawn)` });
    }
    const ir = d.iridophores;
    let fixedMood = null;
    const written = {};
    // the display keys the recipe drives: the ones its weights or a mood name. A key it never names (darkAll, ringFlash:
    // recipe.MOODS carries neither) is never written, so a scene's setDisplay owns it as on a plain creature, through the
    // cycle and setMood alike (written with the creature's own value, setMood reset a scene's darkAll). A key only some
    // moods name rests between them at the creature's own value when the remix arrives (rest, moodWeights)
    const named = d.base || d.weights || {};
    const driven = DISPLAY_KEYS.filter((k) => named[k] != null
        || Object.values(d.moods || {}).some((m) => m?.[k] != null));
    const rest = {};
    for (const k of DISPLAY_KEYS) rest[k] = U[k].value;
    const ctl = {
        block: b, uniforms: R, report, accessories: seated, seed,
        update(t) {
            let w;
            if (fixedMood) {
                const mood = (d.moods || {})[fixedMood] || {};
                w = {};
                for (const k of [...DISPLAY_KEYS, 'leuco']) w[k] = mood[k] ?? d.base?.[k] ?? rest[k] ?? 0;
                w._flash = [fixedMood, fixedMood, 0];
            } else {
                w = moodWeights(d, t, rest);
            }
            // a display key is written only when its recipe value CHANGES: a static display once, a cycle or a crossfade
            // every frame it moves, so the scene's own oct.setDisplay calls persist between changes (bestiary.js's
            // semantics: a value stays until something sets it)
            const dd = {};
            for (const k of driven) {
                if (written[k] !== w[k]) { dd[k] = w[k]; written[k] = w[k]; }
            }
            if (Object.keys(dd).length) api.setDisplay(dd);
            R.leuco.value = w.leuco ?? 0;
            if (ir && ir.flash) {
                const [m0, m1, f] = w._flash;
                const k0 = ir.flash[m0] ?? 1.0, k1 = ir.flash[m1] ?? 1.0;
                R.irid.value = ir.strength * (k0 + (k1 - k0) * f);
            }
        },
        setMood(name) {
            if (name && !(d.moods || {})[name]) report.push({ severity: 'warning', code: 'display.mood', message: `unknown mood ${name} (recipe.MOODS)` });
            fixedMood = name || null;
            for (const k of Object.keys(written)) delete written[k];          // a mood change re-asserts every key
            this.update(U.t.value);
        },
        palette(p = {}) {
            // live zone recolour: {role: '#rrggbb' | {colour, strength, keep_value}} (sRGB hex, as recipe palettes)
            for (const [role, e] of Object.entries(p)) {
                const Z = R.palette[role];
                if (!Z) continue;
                const ent = typeof e === 'string' ? { colour: e } : e;
                const c = new THREE.Color(ent.colour);                     // hex -> linear working space
                const T = [c.r, c.g, c.b];
                const lref = b.zones?.[role]?.lref ?? 0.2;
                setZoneUniforms(Z, { target: T, w: ent.strength ?? 1.0, sat: ent.sat ?? 1.0, val: ent.keep_value ? 1.0 : lum(T) / Math.max(lref, 1e-4), absolute: 0, detail: 1, rough: 0, rough_to: null, rough_w: 0, metal: null }, lref);
            }
        },
        setSurface(amount) { R.surface.value = amount; },
        dispose() {
            // (B10c) a WORN item (the monocle) leaves through its handle: its chain's end sits on a bone, outside the holder
            for (const s of seated) {
                if (s.handle?.remove) s.handle.remove();
                else s.holder.parent?.remove(s.holder);
            }
            for (const o of meshes) o.material?.dispose?.();
        },
    };
    if (opts.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push((t) => ctl.update(t));
    ctl.update(U.t.value ?? 0);
    for (const r of report) if (r.severity !== 'warning') console.warn(`[remix] ${r.severity} ${r.code}: ${r.message}`);
    return ctl;
}

export async function create(block, opts = {}) {
    // a Bestiary creature built and remixed in one call (bestiary.js from opts.bestiary, globalThis.Bestiary, or the
    // sibling module); the growths' refraction the creature is built with (opts.create's growTrans, growThickness,
    // growIOR) reaches the remix's growths material
    const B = opts.bestiary || globalThis.Bestiary || await import(new URL('./bestiary.js', import.meta.url).href);
    const c = opts.create || {};
    // the recipe's cyborg parts (recipe.resolve_runtime's cyborg block: patches/cyborg_c5b_bestiary.md) mounted by
    // bestiary.js create({ cyborg }), each part's glb from opts.create.cyborg's or the block's asset names (ASSETS)
    const cy = block.cyborg ? { cyborg: { ...(block.cyborg.glow || {}), ...(c.cyborg || {}),
        parts: c.cyborg?.parts || block.cyborg.parts } } : {};
    const api = await B.create({ ...c, ...cy, species: block.base, seed: opts.seed ?? block.seed, auto: opts.auto });
    api.remix = await apply(api, block, { growTrans: c.growTrans, growThickness: c.growThickness, growIOR: c.growIOR, ...opts });
    return api;
}

globalThis.BestiaryRemix = { apply, create, applyJitter, roll, keyId, hash01, jitterRGB, zoneRemapRGB, selfTest };
