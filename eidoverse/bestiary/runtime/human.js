// human.js (B1, wave 6; ROADMAP §3 B1): THE HUMAN THROUGH create(), on the VRM path. bestiary.js create() hands
// { species: 'human' } here (unless opts.vrm === false: then A1's limbed biped on the plain glb, the solver's case).
//
//   const h = await Bestiary.create({ species: 'human', sex: 'F', seed: 3,
//       hair: 'bob' | { style: 'bob', colour: 'black' | 0x2a1d14 | { eumelanin, pheomelanin, ... } },
//       outfit: 'tee' | 'shirt_ss' | 'shirt_ls' | 'shirt_ls_tie' | { top, shirt, pants, shoes, tie } | null,
//       hand: 'robot' | { L: 'robot', R: null } | null,
//       skin: 0xc99170 | { melanin, blood, tint, freckles, moles, mottle },  eyes: 0x433a2c | { iris, irisInner },
//       glasses: true | { palette }, hat: 'peaked_cap' | 'top_hat' | { name, palette },
//       position: [x, y, z], heading, groundY, collisionMeshes, idles: { blink }, auto });
//   scene.add(h.group);
//   h.walkTo(2, 1);  h.speed(0.8); h.turn(0.3); h.setHeading(a);       // the spine (vrmSpine over vrmLocomotion)
//   h.say('Some words');  h.talking = true;  h.setTalkEnvelope((t) => amp);  h.say({ visemes: track })  // voicebox track
//   h.anchor('head' | 'chest' | 'back' | 'hips' | 'wristL' | 'wristR');  h.parts('garment_tee');  h.wear(acc)
//   h.palette({ skin, tint, hair, shirt, pants, shoes, tie });  h.pose();  h.emote('wave_goodbye', 3)
//
// THE SLOTS (each a forge output; the body is one glb per (sex, outfit, hand) and the hair a coat on its bones):
//   BODY    the canonical base, H4d (human/h4d/build/glb/human_<sex>.glb, 116 joints, T rest, VRM 1.0);
//   OUTFIT  B2's clothed glbs (human/clothing_b2/glb/human_<sex>_<top>_base.glb: the base with garment_* skinned meshes on
//           skin 0, the body under them culled by its index, the MASKS colour zones; garment_material.js shades them);
//   HAND    C3's robot hands (cyborg_robot/c3/glb/human_<sex>_c3.glb: both wrists grafted, 114 joints, VRMC node
//           constraints; robot_hand_dof.js keeps every finger on its pin). One side only: the other hand is the canonical
//           body's (the glb is grafted on both; a one-sided build is a forge job, so { L: 'robot' } shows both: noted);
//   OUTFIT + HAND  composed HERE when both are asked (no forge build of the pair exists yet): the c3 glb, with the outfit
//           glb's garments re-bound to the c3 skeleton by joint name and the c3 skin_BODY culled where the outfit's was
//           (the hidden triangles matched by their vertices' bind positions; the c3 body is the base's minus the hands);
//   HAIR    B6's coats (human/hair_b3/out_b6/human_<style>_b6_<sex>/coat_human_<style>_b6_<sex>.glb) through coat.js
//           (attachCoat on the body's bones, the scalp layer on skin_HEAD), the colour by the pigment model.
// THE MOTION is the house's controller's (EidoverseRobotController: physics locomotion, the walk clip, foot IK, and on live
// the foot lock); its pre-VRM hook runs the hand pass (C3), then installHumanDrivers' face driver, arm opening and twists
// (L1). The talk is vrmSpine's (the VRM visemes), the blink its idle (on by default here: a person blinks).
// THE GROUP: h.group is the human's PLACEMENT, as on every creature: scene.add(h.group), move it to place her (a move
// between updates re-plants the controller there: a teleport); walkTo / speed carry it. The controller works in the world
// frame; each update the group's local transform is set so its world is the identity while the controller runs, then the
// controller's pose is handed back to it (the VRM's scene node stays at identity inside the group), so the world matrices
// are the controller's either way and a scene reading h.group.position sees where she is.
const THREE = globalThis.THREE;

import { makeFaceEval } from './human_face_eval.js';
import { installHumanDrivers } from './human_drivers.js';
import { smoothVisemes } from './human_visemes.js';
import { initGraftDOF, applyGraftDOF, applyGraftContact, keepArmPose, restoreArmPose, graftTwists } from './robot_hand_dof.js';
import { attachCoat, loadCoat, scalpLayer } from './coat.js';
import { accessory, wear } from './accessories.js';
import { vrmLocomotion } from './locomotion.js';
import { vrmSpine } from './spine.js';
import * as HS from './human_skin.js';
import { garmentMaterial } from './garment_material.js';
import { SPECIES, manifestOf } from './species.js';
import { parseShared, fileBytes } from './gltf_cache.js';

// ------------------------------------------------------------------------------------------------ where the slots live
const W = 'work/bestiary';
export const HUMAN_SLOTS = {
    // the base: the species manifest's human row (A1's species.js: H4d's canonical glbs, M its variant)
    base: (sex) => (sex === 'M' ? SPECIES.human?.variants?.M?.path : SPECIES.human?.path) || `${W}/human/h4d/build/glb/human_${sex}.glb`,
    outfits: ['tee', 'shirt_ss', 'shirt_ls', 'shirt_ls_tie'],
    outfit: (sex, top) => `${W}/human/clothing_b2/glb/human_${sex}_${top}_base.glb`,
    hand: (sex) => `${W}/cyborg_robot/c3/glb/human_${sex}_c3.glb`,
    // B6's styles by sex (bob is the woman's only)
    hairs: { F: ['bob', 'bun', 'crop', 'curly', 'long', 'mohawk', 'ponytail', 'spiky'],
        M: ['bun', 'crop', 'curly', 'long', 'mohawk', 'ponytail', 'spiky'] },
    hair: (style, sex) => `${W}/human/hair_b3/out_b6/human_${style}_b6_${sex}/coat_human_${style}_b6_${sex}.glb`,
    lut: { albedo: `${W}/human/h3/material/lut/skin_lut_albedo.f16`, trans: `${W}/human/h3/material/lut/skin_lut_trans.f16`,
        preint: `${W}/human/h3/material/lut/skin_lut_preint.f16` },
    capConform: (sex) => `${W}/human/h4/rig/seats/cap_conform_${sex}.bin`,
};
// THE REFERENCE IDENTITIES (H3b's, the films'): the hazel-eyed woman, the brown-eyed man; a seed that is not given
// keeps them (so create('human') is the human of every H4b..C3 film); a given seed rolls an identity
// (HB1 S1, the body fix 11-09: Skye, "freckles are actually rare") no freckles and 15 moles each (were the woman 0.40 / 35,
// the man 0 / 30); mottle 1.0 is now ordinary adult skin (human_skin.js K.MOTTLE, the skin study's candidate B)
const REF_ID = { F: { freckles: 0.0, moles: 15, mottle: 1.0, seed: 3, iris: 0x433a2c, irisInner: [1.95, 1.51, 0.91] },
    M: { freckles: 0.0, moles: 15, mottle: 1.0, seed: 5, iris: 0x563d29, irisInner: [0.71, 0.77, 0.93] } };

function hash01(i, seed) {
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 8) / 16777216;
}
const bytesOf = (o, key, path) => o?.[key] || globalThis.ASSETS?.[key] || Deno.readFileSync(path);
const toBuf = (b) => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
// A CROWD SHARES ITS TEXTURES (gltf_cache.js): every human of one glb reads the first one's textures, and each file is read once
const parseVRM = (bytes, key = null) => parseShared(bytes, key, { vrm: true });

// ------------------------------------------------------------------------------------------------ colours
const lin = (hex) => new THREE.Color(hex);           // sRGB hex -> the working (linear) colour
function lab(c) {
    // linear RGB -> CIE L*a*b* (D65)
    const X = 0.4124 * c.r + 0.3576 * c.g + 0.1805 * c.b, Y = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
    const Z = 0.0193 * c.r + 0.1192 * c.g + 0.9505 * c.b;
    const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    const fx = f(X / 0.9505), fy = f(Y), fz = f(Z / 1.089);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}
function half2float(h) {
    const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, f = h & 0x3ff;
    if (e === 0) return s * Math.pow(2, -14) * (f / 1024);
    if (e === 31) return f ? NaN : s * Infinity;
    return s * Math.pow(2, e - 15) * (1 + f / 1024);
}
// THE SKIN TONE FROM A HEX (the old creator's skin / color): the identity's base melanin and blood whose LUT albedo is
// nearest in L*a*b* (the LUT: 64 x 64 over u = sqrt(mel / MEL_MAX), v = sqrt(blood / BLOOD_MAX), human_skin.js K); a hex
// past the human gamut (dE > 20: a green alien, Hege's red) keeps the nearest tone and takes the rest as the tint
// (human_skin's tint: beyond-human skins). The old colour is a display albedo of the whole skin: matched to the LUT cell
// (the inner arm's, the zones' multipliers on top), so it is mapped approximately
export function skinFromHex(hex, lutBytes) {
    const K = HS.K;
    const u16 = new Uint16Array(lutBytes.buffer, lutBytes.byteOffset, lutBytes.byteLength / 2);
    const want = lab(lin(hex));
    let best = null;
    for (let j = 0; j < 64; j++) {
        for (let i = 0; i < 64; i++) {
            const k = 4 * (j * 64 + i);
            const c = { r: half2float(u16[k]), g: half2float(u16[k + 1]), b: half2float(u16[k + 2]) };
            const L = lab(c);
            const d = Math.hypot(L[0] - want[0], L[1] - want[1], L[2] - want[2]);
            if (!best || d < best.d) best = { d, i, j, c };
        }
    }
    const u = best.i / 63, v = best.j / 63;
    const out = { melanin: K.MEL_MAX * u * u, blood: K.BLOOD_MAX * v * v, dE: best.d };
    // (a display hex of a natural skin lands within ~13 of the LUT: makeCreature's default 0xd9a37f at 12.8; only a hex
    // clearly past it takes a tint)
    if (best.d > 20) {
        const t = lin(hex);
        out.tint = new THREE.Color(t.r / Math.max(1e-4, best.c.r), t.g / Math.max(1e-4, best.c.g), t.b / Math.max(1e-4, best.c.b))
            .getHex(THREE.LinearSRGBColorSpace);
    }
    return out;
}
// THE HAIR'S COLOUR (coat.js's pigment model: absorption exp(-(eu sigma_eu + pheo sigma_pheo) path), a dye, a tint, grey
// strands): a preset by name (the coat glb's: blonde, brown, black; + red, grey, white here), a look object as is, or a
// HEX: natural tones by the presets (black / brown / blonde by value, red by hue, grey by low chroma at a high value), and
// any other hue as a dye over the bleached blonde, the value by the tint (the old hairColor's display colours: mapped
// approximately)
const HAIR_PRESETS = {
    red: { eumelanin: 0.15, pheomelanin: 1.15 },
    auburn: { eumelanin: 0.6, pheomelanin: 0.9 },
    grey: { eumelanin: 0.35, pheomelanin: 0.08, grey: 0.75 },
    white: { eumelanin: 0.05, pheomelanin: 0.02, grey: 1.0 },
};
// every pigment key at its neutral (coat.js COAT_LOOK's: path 4 fibres, no dye, no tint, no grey) under a preset, so a colour
// never inherits another's (blonde over brown kept brown's short path, cool dye and half tint: a muddy blonde, b1_loads 11-09)
export const HAIR_NEUTRAL = { pigment: 1.0, eumelanin: 0.3, pheomelanin: 0.12, pigmentPath: 4.0, dye: [0.5, 0.5, 0.5],
    dyeAmount: 0.0, tint: [1.0, 1.0, 1.0], grey: 0.0 };
const numeric = (o) => Object.fromEntries(Object.entries(o || {}).filter(([, v]) => typeof v === 'number' || Array.isArray(v)));
export function hairLook(colour, presets = {}) {
    if (colour == null) return {};
    if (typeof colour === 'object') return colour;
    if (typeof colour === 'string') return { ...numeric(presets[colour] || HAIR_PRESETS[colour] || {}) };
    const s = new THREE.Color(colour);
    const sr = { r: 0, g: 0, b: 0 };
    s.getRGB(sr, THREE.SRGBColorSpace);
    const L = 0.2126 * sr.r + 0.7152 * sr.g + 0.0722 * sr.b;   // sRGB luma
    const mx = Math.max(sr.r, sr.g, sr.b), mn = Math.min(sr.r, sr.g, sr.b), ch = mx - mn;
    let h = 0;
    if (ch > 1e-6) {
        if (mx === sr.r) h = ((sr.g - sr.b) / ch) % 6; else if (mx === sr.g) h = (sr.b - sr.r) / ch + 2; else h = (sr.r - sr.g) / ch + 4;
        h *= 60; if (h < 0) h += 360;
    }
    const sat = mx > 0 ? ch / mx : 0;
    if (sat < 0.18 && L > 0.42) return { ...HAIR_PRESETS[L > 0.8 ? 'white' : 'grey'] };
    const natural = (h <= 48 || h >= 345) && sat < 0.85;
    if (natural || sat < 0.25) {
        if (L < 0.10) return numeric(presets.black);
        if ((h <= 22 || h >= 345) && sat > 0.5 && L < 0.6) return { ...HAIR_PRESETS[L < 0.3 ? 'auburn' : 'red'] };
        if (L < 0.32) {
            // the brown preset with its value scaled to the hex's (the preset's root albedo ~(0.12, 0.065, 0.017) linear)
            const b = numeric(presets.brown);
            const tl = new THREE.Color(colour);
            const yl = 0.2126 * tl.r + 0.7152 * tl.g + 0.0722 * tl.b;
            const k = Math.max(0.15, Math.min(1.6, yl / 0.0727));
            b.tint = (b.tint || [0.5, 0.5, 0.5]).map((x) => x * k);
            return b;
        }
        return presets.blonde ? numeric(presets.blonde) : { eumelanin: 0.3, pheomelanin: 0.12 };
    }
    // a dyed colour: the bleached base x dye x 2 (dyeAmount 1), the value carried by the tint (coat.js: mix(pig, pig dye 2))
    const base = [0.553, 0.358, 0.117];             // the blonde preset's root albedo (eu 0.3, pheo 0.12, path 4)
    const t = new THREE.Color(colour);
    const D = [t.r / base[0], t.g / base[1], t.b / base[2]];
    const m = Math.max(...D);
    return { eumelanin: 0.3, pheomelanin: 0.12, pigmentPath: 4.0, dye: D.map((x) => x / (2 * m)), dyeAmount: 1.0,
        tint: [m, m, m].map((x) => Math.min(x, 3.0)) };
}

// ------------------------------------------------------------------------------------------------ OUTFIT + HAND composed
// the c3 body (the base minus its hands, re-indexed) culled where the outfit's body was: a base triangle the outfit hid
// is hidden here when its three vertices are c3 vertices (matched by bind position, 0.01 mm)
function cullLike(c3Body, outfitBody, outfitFullIndex) {
    const key = (x, y, z) => `${Math.round(x * 1e5)},${Math.round(y * 1e5)},${Math.round(z * 1e5)}`;
    const P3 = c3Body.geometry.attributes.position, PO = outfitBody.geometry.attributes.position;
    const at = new Map();
    for (let i = 0; i < P3.count; i++) at.set(key(P3.getX(i), P3.getY(i), P3.getZ(i)), i);
    const map = new Int32Array(PO.count).fill(-1);
    for (let i = 0; i < PO.count; i++) map[i] = at.get(key(PO.getX(i), PO.getY(i), PO.getZ(i))) ?? -1;
    const tri = (a, b, c) => [a, b, c].sort((p, q) => p - q).join(',');
    const kept = new Set();
    const ki = outfitBody.geometry.index.array;
    for (let k = 0; k < ki.length; k += 3) kept.add(tri(ki[k], ki[k + 1], ki[k + 2]));
    const hidden = new Set();
    const fi = outfitFullIndex.array;
    for (let k = 0; k < fi.length; k += 3) {
        if (kept.has(tri(fi[k], fi[k + 1], fi[k + 2]))) continue;
        const a = map[fi[k]], b = map[fi[k + 1]], c = map[fi[k + 2]];
        if (a >= 0 && b >= 0 && c >= 0) hidden.add(tri(a, b, c));
    }
    const ci = c3Body.geometry.index.array, out = [];
    let dropped = 0;
    for (let k = 0; k < ci.length; k += 3) {
        if (hidden.has(tri(ci[k], ci[k + 1], ci[k + 2]))) { dropped++; continue; }
        out.push(ci[k], ci[k + 1], ci[k + 2]);
    }
    const g = c3Body.geometry.clone();
    g.setIndex(out);
    c3Body.geometry = g;
    return { hidden: hidden.size, dropped, kept: out.length / 3 };
}
// a garment from the outfit glb re-bound to the c3 skeleton: the skin indices by joint name (a joint the c3 body lacks:
// its finger joints, which no garment weights; any weight found there goes to the hand), the c3 skin's own inverses
function rebindGarment(mesh, skC3) {
    const byName = new Map(skC3.bones.map((b, i) => [b.name, i]));
    const src = mesh.skeleton.bones.map((b) => b.name);
    const g = mesh.geometry.clone();
    const si = g.attributes.skinIndex, sw = g.attributes.skinWeight;
    let moved = 0;
    for (let v = 0; v < si.count; v++) {
        for (let c = 0; c < 4; c++) {
            const nm = src[si.getComponent(v, c)];
            let k = byName.get(nm);
            if (k === undefined) {
                if (sw.getComponent(v, c) > 0) moved++;
                k = byName.get(/_L$/.test(nm) ? 'hand_L' : /_R$/.test(nm) ? 'hand_R' : 'root') ?? 0;
            }
            si.setComponent(v, c, k);
        }
    }
    si.needsUpdate = true;
    const m = new THREE.SkinnedMesh(g, mesh.material);
    m.name = mesh.name;
    m.userData = { ...mesh.userData };
    m.bind(skC3, mesh.bindMatrix);
    return { mesh: m, moved };
}

// ------------------------------------------------------------------------------------------------ the builder
export async function createHuman(opts = {}) {
    const sex = /^m/i.test(opts.sex || '') ? 'M' : 'F';
    const outfitOpt = typeof opts.outfit === 'string' ? { top: opts.outfit } : (opts.outfit || null);
    const top = outfitOpt ? (outfitOpt.top || (outfitOpt.tie != null ? 'shirt_ls_tie' : 'tee')) : null;
    if (top && !HUMAN_SLOTS.outfits.includes(top)) {
        throw new Error(`[Bestiary] human outfit '${top}' (have: ${HUMAN_SLOTS.outfits.join(', ')})`);
    }
    const handOpt = opts.hand === 'robot' || opts.hand === true ? { L: 'robot', R: 'robot' }
        : (opts.hand && typeof opts.hand === 'object' ? opts.hand : null);
    const robotHand = !!(handOpt && (handOpt.L === 'robot' || handOpt.R === 'robot'));
    const report = [];
    // ---- the body glb (and the outfit's, when both slots are filled)
    const bodyPath = opts.path || (robotHand ? HUMAN_SLOTS.hand(sex) : top ? HUMAN_SLOTS.outfit(sex, top) : HUMAN_SLOTS.base(sex));
    const own = opts.bytes || globalThis.ASSETS?.[opts.asset];
    const gltf = await parseVRM(own || fileBytes(bodyPath), own ? null : bodyPath);
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error(`[Bestiary] human: ${bodyPath} did not load as a VRM (is VRMLoaderPlugin injected?)`);
    const bx = gltf.userData?.bestiary || gltf.parser?.json?.extras?.bestiary || {};
    const human = bx.human || {};
    let outfitGltf = top && !robotHand ? gltf : null;
    if (top && robotHand) {
        outfitGltf = await parseVRM(fileBytes(HUMAN_SLOTS.outfit(sex, top)), HUMAN_SLOTS.outfit(sex, top));
        report.push(`outfit '${top}' composed on the robot-handed body (no forge build of the pair)`);
    }
    if (handOpt && (handOpt.L !== handOpt.R)) report.push(`hand ${JSON.stringify(handOpt)}: the c3 glb is grafted on both wrists (a one-sided build waits on the forge)`);
    const vscene = vrm.scene;
    // ---- the materials (human_skin.js: the skin, eyes, mouth; garment_material.js: the cloth)
    const lutBytes = {
        albedo: bytesOf(opts.lut, 'lut_albedo', HUMAN_SLOTS.lut.albedo),
        trans: bytesOf(opts.lut, 'lut_trans', HUMAN_SLOTS.lut.trans),
        preint: bytesOf(opts.lut, 'lut_preint', HUMAN_SLOTS.lut.preint),
    };
    const lut = HS.skinLUT(lutBytes);
    const seeded = opts.seed != null && opts.identity !== 'reference';
    const ref = REF_ID[sex];
    const id = seeded ? {
        // a rolled identity (HB1 S1, BODY_FIX_PLAN SK2 / SK3 / D2): freckles a rare trait, 8 % of women and 5 % of men
        // (were 40 / 30 %), at half the old strength, and only on light skin (checked below, once the skin is known);
        // moles 5-30 (were 10-50); the mottle of ordinary adult skin
        freckles: hash01(31, opts.seed) < (sex === 'F' ? 0.08 : 0.05) ? 0.08 + 0.17 * hash01(32, opts.seed) : 0.0,
        moles: Math.round(5 + 25 * hash01(33, opts.seed)), mottle: 1.0, seed: opts.seed | 0,
        iris: ref.iris, irisInner: ref.irisInner,
    } : { ...ref };
    const skinO = typeof opts.skin === 'number' ? { hex: opts.skin } : (opts.skin || {});
    if (skinO.hex != null) {
        const s = skinFromHex(skinO.hex, lutBytes.albedo);
        Object.assign(id, { melanin: s.melanin, blood: s.blood }, s.tint != null ? { tint: s.tint } : {});
        report.push(`skin 0x${skinO.hex.toString(16)}: melanin ${s.melanin.toFixed(4)} blood ${s.blood.toFixed(5)} (dE ${s.dE.toFixed(1)}${s.tint != null ? ', + tint' : ''})`);
    }
    for (const k of ['melanin', 'blood', 'tint', 'freckles', 'moles', 'mottle', 'flush', 'wet']) if (skinO[k] != null) id[k] = skinO[k];
    // (HB1 S1) a rolled identity's freckles only on light skin (base melanin under 0.15, the LUT's fair third: dark skin
    // freckles rarely and shows it less); freckles asked for in opts.skin always stand
    if (seeded && skinO.freckles == null && (id.melanin ?? 0.1045) >= 0.15) id.freckles = 0.0;
    const eyesO = typeof opts.eyes === 'number' ? { iris: opts.eyes } : (opts.eyes || {});
    if (eyesO.iris != null) { id.iris = eyesO.iris; id.irisInner = eyesO.irisInner ?? [1.0, 1.0, 1.0]; }
    const U = HS.humanUniforms(id);
    // the eye's parts from the glb (n05: skinned to the lids), their shell AO reference
    const PART_KEYS = ['human_eye_shell', 'human_eye_ring'];
    const glbParts = [];
    let aoRef = null;
    vscene.traverse((o) => {
        aoRef = aoRef ?? o.userData?.shell_ao_ref ?? null;
        if (o.isMesh && PART_KEYS.includes(o.material?.userData?.bestiary)) glbParts.push(o);
    });
    HS.K.EYE_PARTS = glbParts.length > 0;
    // OUTFIT + HAND: the garments re-bound, the body culled like the outfit's
    let garments = [];
    let bodySkin = null;
    vscene.traverse((o) => { if (o.isSkinnedMesh && o.name === 'skin_BODY') bodySkin = o; });
    if (outfitGltf && outfitGltf !== gltf) {
        let oBody = null;
        const src = [];
        outfitGltf.scene.traverse((o) => {
            if (o.isSkinnedMesh && o.name === 'skin_BODY') oBody = o;
            if (o.isSkinnedMesh && o.name.startsWith('garment_')) src.push(o);
        });
        const obx = outfitGltf.userData?.bestiary || outfitGltf.parser?.json?.extras?.bestiary || {};
        const full = obx.body_index_full != null ? await outfitGltf.parser.getDependency('accessor', obx.body_index_full) : null;
        if (oBody && full && bodySkin) {
            const c = cullLike(bodySkin, oBody, full);
            report.push(`body culled like the outfit's: ${c.dropped} of the robot-handed body's triangles hidden (${c.kept} kept)`);
        }
        for (const o of src) {
            const r = rebindGarment(o, bodySkin.skeleton);
            bodySkin.parent.add(r.mesh);
            garments.push(r.mesh);
            if (r.moved) report.push(`${o.name}: ${r.moved} weights on joints the robot hand dropped, moved to the hand`);
        }
    }
    const partOrder = { eyeshell: 1, eyering: 2, caruncle: 3 };
    vscene.traverse((o) => {
        if (!o.isMesh) return;
        const isPart = glbParts.includes(o);
        o.castShadow = !isPart;
        o.receiveShadow = true;
        o.frustumCulled = false;
        if (isPart) o.renderOrder = partOrder[o.name.split('_')[0]] ?? 1;
        if (o.userData?.globe_mm) o.userData.ao_ref = aoRef?.[o.userData.eye_side] ?? 0.88;
        if (o.name.startsWith('garment_')) { if (!garments.includes(o)) garments.push(o); return; }
        o.material = HS.humanMaterial(o, U, lut);
    });
    // the garments: the outfit's colours by zone (the glb's record, then the call's), the trim as B2's scene set it
    const obx = (outfitGltf && (outfitGltf.userData?.bestiary || outfitGltf.parser?.json?.extras?.bestiary)) || {};
    const oc = { ...(obx.outfit || {}), ...(outfitOpt || {}) };
    const hex = (s, d) => (typeof s === 'string' ? parseInt(s.replace('#', ''), 16) : (s ?? d));
    const garmentU = {};
    for (const o of garments) {
        const g = o.name.replace('garment_', '');
        const dye = g === 'trousers' ? hex(oc.pants, 0x35322e) : g === 'shoes' ? hex(oc.shoes, 0x221d18)
            : g === 'tie' ? hex(oc.tie, 0x8a1f2c) : hex(oc.shirt, 0x3a6ea8);
        const trim = g === 'shoes' ? 0x15120f : g === 'tee' ? dye : 0xeceae4;
        o.material = await garmentMaterial(o, outfitGltf || gltf, { dye, trim, third: 0x1a1816 });
        o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
        garmentU[g] = o.material;
    }
    vscene.updateMatrixWorld(true);
    const mcal = HS.apertureCalibration ? HS.apertureCalibration(vscene) : null;
    // ---- the group (the placement: opts.group, a caller's own, e.g. the compat adapter's) and the sockets
    const group = opts.group || new THREE.Group();
    if (!opts.group) group.name = `bestiary_human_${sex}`;
    group.add(vscene);
    const sockets = {}, bones = new Map();
    vscene.traverse((o) => {
        if (o.name?.startsWith('socket_')) sockets[o.name] = o;
        if (o.isBone) bones.set(o.name, o);
    });
    // ---- the face's driver, the twists and arm opening (L1), the robot hand's pass (C3)
    const faceEval = human.face ? makeFaceEval(vrm, human.face) : null;
    const c3 = bx.c3 || null;
    let handStats = null;
    if (c3) {
        initGraftDOF(vrm, c3);          // (C3-MOTION) the wrist's three stages, the pins, the thumb's rotor, the tips, the contact
        handStats = {};
    }
    // ---- the hair (B6's coats on the body's bones; the scalp layer on skin_HEAD)
    let coat = null, hairStyle = null;
    const hairO = typeof opts.hair === 'string' ? { style: opts.hair } : (opts.hair || null);
    if (hairO && hairO.style && hairO.style !== 'none') {
        hairStyle = hairO.style;
        if (!HUMAN_SLOTS.hairs[sex].includes(hairStyle)) {
            const alt = sex === 'M' && hairStyle === 'bob' ? 'crop' : null;
            if (!alt) throw new Error(`[Bestiary] human hair '${hairStyle}' (have for ${sex}: ${HUMAN_SLOTS.hairs[sex].join(', ')})`);
            report.push(`hair '${hairStyle}' has no ${sex} build: '${alt}'`);
            hairStyle = alt;
        }
        const cg = await loadCoat(hairO.bytes || fileBytes(HUMAN_SLOTS.hair(hairStyle, sex)));
        // a robot-handed body has no finger joints: the coat's entries for them (no hair vertex weights them) ride the hand
        const have = new Set(bodySkin.skeleton.bones.map((b) => b.name));
        cg.scene.traverse((o) => {
            if (!o.isSkinnedMesh) return;
            const sw = o.geometry.attributes.skinWeight, si = o.geometry.attributes.skinIndex;
            o.skeleton.bones.forEach((b, i) => {
                if (have.has(b.name)) return;
                let w = 0;
                for (let v = 0; v < si.count && w === 0; v++) for (let c = 0; c < 4; c++) if (si.getComponent(v, c) === i) w = Math.max(w, sw.getComponent(v, c));
                if (w > 0) report.push(`hair joint ${b.name} (weight ${w.toFixed(3)}) is not on this body: ridden by the hand`);
                b.name = /_L$/.test(b.name) ? 'hand_L' : /_R$/.test(b.name) ? 'hand_R' : 'head';
            });
        });
        const man = cg.userData?.bestiary?.coat || cg.parser?.json?.extras?.bestiary?.coat || {};
        const pre = man.pigment_presets || {};
        const look = { ...HAIR_NEUTRAL, ...hairLook(hairO.colour ?? hairO.color ?? 'brown', pre), ...(hairO.look || {}) };
        coat = await attachCoat({ group: vscene, gltf, uniforms: null }, cg,
            { look, skinLayer: false, temporalAA: globalThis._taa === true });
        let headSkin = null;
        vscene.traverse((o) => { if (o.isMesh && o.name === 'skin_HEAD') headSkin = o; });
        if (headSkin && coat.packs?.human_skin_HEAD) scalpLayer(headSkin.material, coat.packs.human_skin_HEAD, coat.uniforms);
        for (const m of coat.meshes) { m.castShadow = true; m.receiveShadow = true; }
        report.push(`hair ${hairStyle} (${sex}): ${coat.meshes.length} coat meshes, look ${JSON.stringify(look).slice(0, 160)}`);
    }
    // ---- the accessories (accessories.js wear() on the glb's seats; the peaked cap's conform for this wearer)
    const wearer = { sockets, gltf, group: vscene };
    const worn = {};
    async function wearProp(name, o = {}) {
        const acc = await accessory(name, o.bytes ? { bytes: o.bytes } : {});
        const h = wear(wearer, acc, o);
        if (name === 'peaked_cap') {
            let raw = null;
            try { raw = o.conform || globalThis.ASSETS?.cap_conform || fileBytes(HUMAN_SLOTS.capConform(sex)); } catch (_) { raw = null; }
            if (raw) {
                const D = new Float32Array(toBuf(raw));
                h.object.traverse((m) => {
                    const pos = m.geometry?.attributes?.position;
                    if (!m.isMesh || !pos || pos.count * 3 !== D.length) return;
                    const g2 = m.geometry.clone(), p2 = g2.attributes.position;
                    for (let i = 0; i < p2.count; i++) p2.setXYZ(i, p2.getX(i) + D[3 * i], p2.getY(i) + D[3 * i + 1], p2.getZ(i) + D[3 * i + 2]);
                    p2.needsUpdate = true;
                    g2.computeBoundingSphere();
                    m.geometry = g2;
                });
            }
        }
        h.object?.traverse?.((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
        return h;
    }
    if (opts.glasses) worn.glasses = await wearProp('round_glasses', typeof opts.glasses === 'object' ? opts.glasses : {});
    if (opts.hat) {
        const ho = typeof opts.hat === 'string' ? { name: opts.hat } : opts.hat;
        worn.hat = await wearProp(ho.name || 'peaked_cap', ho);
    }

    // ---- the api (the spine's once the controller runs; the controller starts now, or at start() for a deferred caller)
    let ctrl = null, loco = null, spine = null, slab = null;
    const idleWant = opts.idles ?? { blink: true };
    let lastT = null;
    const last = { p: new THREE.Vector3(), q: new THREE.Quaternion(), set: false };
    // the controller's pose of the VRM node. Its rotation is kept as the EULER the controller wrote ((0, heading, 0)), not as
    // a quaternion: the controller writes only vrm.scene.rotation.y (character_controller.js step 9), and a quaternion put
    // back on the node comes back as the Euler (-180, 180 - a, -180) for any yaw a past 90 deg, so the next write of
    // rotation.y drew her at 180 - a: mirrored on every other frame (the L5 check, 11-09)
    const vpose = { p: new THREE.Vector3(), r: new THREE.Euler() };
    const tmpM = new THREE.Matrix4(), tmpP = new THREE.Vector3(), tmpQ = new THREE.Quaternion(), tmpS = new THREE.Vector3();
    const worldPose = () => {
        group.updateWorldMatrix(true, false);
        group.matrixWorld.decompose(tmpP, tmpQ, tmpS);
        const e = new THREE.Euler().setFromQuaternion(tmpQ, 'YXZ');
        return { p: tmpP.clone(), heading: e.y };
    };
    // the group's local transform whose world is M (its parent's inverse x M; its own scratch: M may be tmpM)
    const tmpL = new THREE.Matrix4();
    const setGroupWorld = (M) => {
        if (group.parent) {
            group.parent.updateWorldMatrix(true, false);
            tmpL.copy(group.parent.matrixWorld).invert().multiply(M);
        } else tmpL.copy(M);
        tmpL.decompose(group.position, group.quaternion, group.scale);
        group.updateMatrixWorld(true);
    };
    let visTrack = null;
    const api = {
        // the manifest as every base's (species.js manifestOf: the glb's record under the species row), the VRM case and the
        // slots this human was built with
        group, vrm, gltf, bones, sockets, uniforms: U,
        manifest: { ...manifestOf(gltf, SPECIES.human || {}, 'human'), path: own ? null : bodyPath, motion: 'vrm', sex, top, robotHand,
            hair: hairStyle },
        coatCtl: coat, worn, garments: garmentU, report, size: 1.0,
        get controller() { return ctrl; },
        // THE START (the controller made at the group's world placement, on a ground at groundY): create() calls it unless
        // opts.deferStart (the compat adapter places the group first, then starts)
        async start(o = {}) {
            if (ctrl) return api;
            const wp = worldPose();
            const pos = o.position || opts.position || [wp.p.x, wp.p.y, wp.p.z];
            const heading = o.heading ?? opts.heading ?? wp.heading;
            const gy = o.groundY ?? opts.groundY ?? pos[1] ?? 0;
            let coll = o.collisionMeshes || opts.collisionMeshes || null;
            if (!coll) {
                // the ground: an invisible slab whose top is groundY (the controller's colliders are AABBs of these), under
                // her start and 2 km across (11-09: it was 120 m at the world's origin, and tokenization_siren's analysts,
                // placed at x 65 on their panel floor, stood past its edge and fell through: the AFTER showed an empty panel)
                slab = new THREE.Mesh(new THREE.BoxGeometry(2000, 0.1, 2000), new THREE.MeshBasicNodeMaterial());
                slab.position.set(pos[0], gy - 0.05, pos[2]);
                slab.visible = false;
                slab.updateMatrixWorld(true);
                coll = [slab];
            }
            // the controller's frame is the world: the group's world at identity while it is made (the scene's scale on the
            // group kept: the controller walks the life-size human, the group shows her at the scene's size about her feet)
            const sc0 = group.scale.clone();
            setGroupWorld(new THREE.Matrix4());
            ctrl = await globalThis.EidoverseRobotController.create(vrm, null, {}, {
                collisionMeshes: coll, startPosition: [pos[0], gy, pos[2]], startHeading: heading, skipVrmOptimize: true,
                footLock: true,     // (11-09) the foot lock is opt-in on live (robot_controller.js 13:06): the humans take it
                ...(o.walkSpeed != null || opts.walkSpeed != null ? { walkSpeed: o.walkSpeed ?? opts.walkSpeed } : {}),
            });
            // the pre-VRM hook: the robot hand's pass first (C3-MOTION: the clip's arm pose kept for the wrist's turn limit,
            // then the wrist's stages, the pins, the thumb, the tips), then the face driver, the arm opening, the twists
            // (L1; the forearm's twist joints left off a grafted hand: its roll stage turns inside the house)
            if (c3) ctrl.onPreVrmUpdate = (hdt) => { keepArmPose(vrm); applyGraftDOF(vrm, handStats, hdt); };
            installHumanDrivers(vrm, ctrl, c3 ? { ...human, twists: graftTwists(human.twists, vrm, c3) } : human,
                { face: faceEval });
            // the arrival radius: 5 cm (the controller walks ~1.5 m/s with no braking: a 1 cm radius is missed by a
            // straight pass at 5 cm a frame and she circles the point; b1_motion F_tee, 11-09)
            loco = vrmLocomotion(ctrl, { radius: opts.arriveRadius ?? 0.05 });
            spine = vrmSpine(vrm, ctrl, loco, { seed: opts.seed ?? 1 });
            if (idleWant) spine.idles(idleWant);
            // the placement handed back to the group (the controller's start pose)
            vscene.updateMatrixWorld(true);
            vpose.p.copy(vscene.position); vpose.r.copy(vscene.rotation);
            tmpM.compose(vscene.position, vscene.quaternion, sc0);
            vscene.position.set(0, 0, 0); vscene.quaternion.identity();
            setGroupWorld(tmpM);
            const wp2 = worldPose();
            last.p.copy(wp2.p); last.q.copy(group.getWorldQuaternion(new THREE.Quaternion())); last.set = true;
            return api;
        },
        // the spine's controls (before start: nothing to drive yet)
        speed(v) { return loco?.controls.speed(v); },
        turn(w) { return loco?.controls.turn(w); },
        walkTo(x, z, o = {}) { return loco?.controls.walkTo(x, z, o); },
        // a heading: on the spot (the controller's own heading; vrmLocomotion's is a short step toward it), or o.step
        setHeading(a, o = {}) {
            if (!ctrl) return null;
            if (o.step) return loco.controls.setHeading(a);
            ctrl.heading = a;
            return null;
        },
        pose() {
            const p = loco?.controls.pose();
            if (p) p.heading = Math.atan2(Math.sin(p.heading), Math.cos(p.heading));    // (the controller's accumulates)
            return p ?? null;
        },
        moving() { return !!loco?.controls.moving(); },
        anchor(n) { return spine?.anchor(n) ?? ({ head: vrm.humanoid.getNormalizedBoneNode('head'), hips: vrm.humanoid.getNormalizedBoneNode('hips') }[n] || null); },
        parts(n) { const out = []; vscene.traverse((o) => { if (o.name === n || o.material?.userData?.bestiary === n) out.push(o); }); return out; },
        say(o) {
            if (o && typeof o === 'object' && o.visemes) {
                // a voicebox viseme track ({ fps, frames: [{ aa, ih, ou, ee, oh }] }), smoothed (L1's human_visemes.js)
                visTrack = { S: smoothVisemes(o.visemes, { gain: o.gain ?? 0.68 }), t0: o.t0 ?? (lastT ?? 0) };
                return api;
            }
            spine?.say(o);
            return api;
        },
        get talking() { return !!visTrack || !!spine?.talking; },
        set talking(v) { if (spine) spine.talking = v; if (!v) visTrack = null; },
        setTalkEnvelope(fn) { spine?.setTalkEnvelope(fn); return api; },
        get hasJaw() { return true; },
        idles(o) { return spine ? spine.idles(o) : { blink: true, flick: false, tailWhip: false }; },
        fly() { console.warn('[Bestiary] human fly(): the human walks (the controller has no flight)'); },
        land() {},
        get flying() { return false; },
        emote(name, dur = 2) { return ctrl?.forceAction(name, dur); },
        wear(acc, o = {}) { return wear(wearer, acc, o); },
        palette(p = {}) {
            if (p.skin != null) {
                const s = skinFromHex(p.skin, lutBytes.albedo);
                U.melanin.value = s.melanin; U.blood.value = s.blood;
                U.tint.value.set(s.tint ?? 0xffffff);
            }
            if (p.tint != null) U.tint.value.set(p.tint);
            if (p.hair != null && coat) coat.look({ ...HAIR_NEUTRAL, ...hairLook(p.hair, coat.manifest?.pigment_presets || {}) });
            const z = { shirt: ['tee', 'shirt_ss', 'shirt_ls'], pants: ['trousers'], shoes: ['shoes'], tie: ['tie'] };
            for (const [k, gs] of Object.entries(z)) {
                if (p[k] == null) continue;
                for (const g of gs) garmentU[g]?.userData?.garment?.uniforms?.dye?.value?.set?.(p[k]);
            }
        },
        fitShadow(light, margin = 1.3) {
            group.updateMatrixWorld(true);
            const box = new THREE.Box3().setFromObject(vscene, true);
            const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.5 * margin;
            const dir = light.position.clone().sub(light.target.position).normalize();
            light.target.position.copy(c);
            light.position.copy(c).addScaledVector(dir, 4 * r);
            light.target.updateMatrixWorld();
            const sc = light.shadow.camera;
            sc.left = -r; sc.right = r; sc.top = r; sc.bottom = -r; sc.near = 0.5 * r; sc.far = 8 * r;
            sc.updateProjectionMatrix();
            return { centre: c, radius: r };
        },
        update(t) {
            const dt = lastT == null ? 1 / 30 : Math.min(0.1, Math.max(1e-4, t - lastT));
            lastT = t;
            U.t.value = t;
            if (ctrl) {
                // a move of the group since the last update: the controller re-planted there (a teleport)
                const wp = worldPose();
                const q = group.getWorldQuaternion(new THREE.Quaternion());
                // (a height nudge under 5 cm is a scene pinning her soles to its floor after each update, as code_commit_neon
                // does for makeCreature: not a move; the controller keeps her on its ground)
                const dxz = Math.hypot(wp.p.x - last.p.x, wp.p.z - last.p.z), dy = Math.abs(wp.p.y - last.p.y);
                if (last.set && (dxz > 1e-4 || dy > 0.05 || q.angleTo(last.q) > 1e-4)) {
                    const cc = ctrl.charCtrl, cur = cc.body.translation(), f = cc.feetWorldPosition;
                    cc.body.setTranslation({ x: wp.p.x, y: cur.y + (wp.p.y - f.y), z: wp.p.z }, true);
                    if (cc._bodyYTarget != null) cc._bodyYTarget += wp.p.y - f.y;
                    cc._lastX = wp.p.x; cc._lastZ = wp.p.z;
                    f.set(wp.p.x, wp.p.y, wp.p.z);
                    ctrl.heading = wp.heading;
                }
                const sc = group.scale.clone();          // the scene's size for her (kept across the update)
                setGroupWorld(new THREE.Matrix4());
                // the controller's own last pose back on the VRM's node for its update (it reads and writes it: the
                // position from the feet, rotation.y eased toward an emote's facing)
                vscene.position.copy(vpose.p);
                vscene.rotation.copy(vpose.r);
                spine.update(t);
                // the spine's syllables open 'aa' to the envelope (0.85 at full energy: a full vowel, the jaw ~15 deg): the
                // human films' conversational gain (0.68, H4's: "conversational speech opens about two thirds of that"), or
                // the open mouth reads as a dark hole (b1_walktalk_F 6.4 s, 11-09)
                if (spine.talking && !visTrack && vrm.expressionManager) {
                    const em = vrm.expressionManager;
                    for (const k of ['aa', 'oh']) em.setValue(k, (em.getValue(k) || 0) * (opts.talkGain ?? 0.68));
                }
                if (visTrack && vrm.expressionManager) {
                    for (const [k, v] of Object.entries(visTrack.S.at(t - visTrack.t0))) vrm.expressionManager.setValue(k, v);
                    if (t - visTrack.t0 > visTrack.S.duration) visTrack = null;
                }
                if (c3) restoreArmPose(vrm);             // (C3-MOTION) the clip's arm pose back before the mixer runs
                ctrl.update(t, dt);
                vscene.updateMatrixWorld(true);
                // (C3-MOTION round 2) the frame final: the thumb off the fingers, the hand off her own skin
                if (c3) { applyGraftContact(vrm, handStats); vscene.updateMatrixWorld(true); }
                vpose.p.copy(vscene.position); vpose.r.copy(vscene.rotation);
                tmpM.compose(vscene.position, vscene.quaternion, sc);
                vscene.position.set(0, 0, 0); vscene.quaternion.identity();
                setGroupWorld(tmpM);
                const wp2 = worldPose();
                last.p.copy(wp2.p); last.q.copy(group.getWorldQuaternion(new THREE.Quaternion())); last.set = true;
            } else {
                // before the start (a deferred caller's setup): the face and drivers on the rest, the VRM updated
                if (c3) applyGraftDOF(vrm, handStats, dt);
                faceEval?.update();
                vrm.update(dt);
                if (c3) { vrm.scene.updateMatrixWorld(true); applyGraftContact(vrm, handStats); }
            }
            if (mcal && HS.setAperture) HS.setAperture(U, vscene, mcal);
            if (coat) coat.update();
        },
    };
    // the old creator's skeleton handles (the compat adapter reads these): the head bone, the skin's skeleton, the LIMBS as its
    // records were ({ isArm, side, hip, knee, ankle, foot }: shoulder / elbow / wrist for an arm). Its side -1 is the limb at -X
    // (it names it 'L': wristL), so the records follow SPACE, not anatomy: side -1 is her right (-X when she faces +Z). The bones
    // are the humanoid's NORMALIZED nodes (rest frames aligned to the world, as the old bones' were); the controller's clip owns
    // them each update, so a scene's own pose written into them after the update is not shown (a mixer-driven body)
    const nb = (n) => vrm.humanoid.getNormalizedBoneNode(n);
    api.headBone = vrm.humanoid.getRawBoneNode('head');
    api.skeleton = bodySkin?.skeleton || null;
    const limb = (isArm, side, s) => isArm
        ? { isArm, side, hip: nb(`${s}UpperArm`), knee: nb(`${s}LowerArm`), ankle: nb(`${s}Hand`), foot: nb(`${s}Hand`) }
        : { isArm, side, hip: nb(`${s}UpperLeg`), knee: nb(`${s}LowerLeg`), ankle: nb(`${s}Foot`), foot: nb(`${s}Toes`) || nb(`${s}Foot`) };
    api.limbs = [limb(true, -1, 'right'), limb(true, 1, 'left'), limb(false, -1, 'right'), limb(false, 1, 'left')];
    if (opts.position) group.position.set(opts.position[0], opts.position[1], opts.position[2]);
    if (opts.heading != null) group.rotation.y = opts.heading;
    if (!opts.deferStart) await api.start();
    // self-animating (the engine's loop swallows an update's throw: the first one is printed here)
    let thrown = false;
    const auto = (t) => {
        try { api.update(t); } catch (e) { if (!thrown) { thrown = true; console.error(`[bestiary human] update: ${e.message}\n${e.stack}`); } }
    };
    if (opts.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(auto);
    api.update(0);
    for (const r of report) console.log(`[bestiary human] ${r}`);
    return api;
}
