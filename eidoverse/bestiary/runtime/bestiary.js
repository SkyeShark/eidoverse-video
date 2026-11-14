// bestiary.js — globalThis.Bestiary: creatures built by the Bestiary forge (eidoverse/bestiary: SDF anatomy ->
// authored low -> voxel sculpt -> baked maps -> layered procedural materials -> rig -> glb), brought to life here:
// the runtime material (TSL over the baked maps) and procedural motion.
//
//   const oct = await Bestiary.create({ species: 'octopus', seed: 3 });
//   scene.add(oct.group);          // self-animating via the engine loop (auto:true default, like makeCreature)
//   oct.setDisplay({ dark: 0.8, spots: 1 });      // the colour change: drive the display patterns (0..1 each)
//   oct.setDisplay({ clouds: 1 });                // passing clouds: dark waves travelling out from the crown
//   oct.setDisplay({ rings: 1, ringFlash: f });   // blue rings: the alarm display (flood + borders), its blue flashing
//   oct.setDisplay({ glow: 1 });                  // photophores: bioluminescent spots pulsing cell by cell
//   oct.palette({ tint: 0xffd8c8 });              // a runtime recolour (remixes: Claude's Creatures)
//   oct.wear(await Bestiary.accessory('top_hat'));  // accessories seat on anatomy's sockets (accessories.js)
//   oct.growth({ glow: 0x9fe4ff, intensity: 1 });  // a creature with growths: their glow and tint at runtime
//   oct.cyborg({ glow: [0, 0.5, 1], intensity: 2 });  // a creature with cyborg parts (an eye implant): their glow
//   // the organic eye's glow variant: create({ eyeGlow: { side: 'R', mask: 'pupil' } }), then oct.cyborg({ eye: 1.5 })
//   // manual drive: { auto: false } and call oct.update(t) in renderFrame.
//
// The glb comes from ASSETS (opts.asset, raw bytes) or a file (opts.path, else the species' forge output). Its
// materials carry the forge's maps: base colour (sRGB), normal (glTF, +Y), ORM (occlusion R, roughness G, metalness
// B), the MASKS pack in KHR_materials_volume's thickness slot (R thin tissue, G ventral, B sucker parts, A patch
// random) and the DISPLAY pack in the emissive slot at factor 0 (R white spots, G eye ring, B dark bands and
// blotches, A mottle). A creature with GROWTHS (work/bestiary/patches/material_ids_v2.md) adds the metalness in the
// ORM's B (round a root also the element halo's, which lives in the skin's own channels: patches/halo_v2.md) and a
// GROWTH pack in KHR_materials_iridescence's texture slot at factor 0 (R the growth id mask, G iridescence, B emissive
// mask, A pulse phase), and a GROWTHS mesh in its own material (growthMaterial: its masks pack
// is R subsurface, G film thickness, B frost / patina layer, A crystal random); the family's glow colour and film come
// from the glb's extras (bestiary.growth: forge/growth.py's table, never a copy here). Motion is a pure function of
// time and the seed (animation craft guide 00.5): arm waves
// whose phase travels toward the tip, each arm on its own seeded phases (no twinning, AG 00.17), a breathing
// mantle, eyes in saccades between fixations (AG 00.62).
// CYBORG PARTS (work/bestiary/research/CYBORG_PLAN.md §5.5, §6.5; work/bestiary/patches/cyborg_c4_eye.md): a material
// whose extras say bestiary 'cyborg' (the eye implant: forge/cyborg_eye.py; the mech tentacle: forge/cyborg_limb.py)
// is routed by its extras FIRST, whatever its name (cyborgMaterial); every other material by name, as before. The
// organic eye's glow variant (§4.3.2) is built only when create() asks for it (opts.eyeGlow): a creature without
// either builds the very shaders it did.
import { accessory, wear } from './accessories.js';
// (AX12) THE AXOLOTL (runtime/axolotl.js; work/bestiary/patches/axolotl_ax12_runtime.md): its wet skin and eye, its rig's
// drivers on the pose rotation over the bind, the salamander motion (the stand, the walk, the swim, the idles)
import { axolotlSetup } from './axolotl.js';

const THREE = globalThis.THREE;

// C5d: the hose's cable (runtime/cyborg_cable.js: the hose re-made every frame on the rendered skin; mountCyborgParts)
import { mountCable } from './cyborg_cable.js';

// THE COAT (runtime/coat.js; work/bestiary/patches/coat_runtime.md): fur and hair as a generator part on any base
import { attachCoat, loadCoat } from './coat.js';

// THE STAG BEETLE's materials (runtime/beetle_cuticle.js: the B58 round's builders with B8's fixes and the crystal beetle's
// GROWTH pack folded in; work/bestiary/patches/beetle_b11_runtime.md): the cuticle's clear coat over its pigmented base, the
// compound eye, the articular membranes, dispatched by the material's extras key
import { beetleMaterial, beetleUniforms, useFamilies as useBeetleFamilies, setFamily as setBeetleFamily,
    FAMILIES as BEETLE_FAMILIES } from './beetle_cuticle.js';

// (A1) THE SPECIES TABLE IS A MANIFEST (runtime/species.js): each glb's extras.bestiary says what the creature is (family, chains,
// sockets, life scale, its locomotion case); species.js keeps where each known glb lives and the rows' gated numbers (moved there
// verbatim). A new base is a glb: create({ path }) or Bestiary.register(name, { path })
import { SPECIES, registerSpecies, manifestOf } from './species.js';
// (A1) THE GAIT SCHEDULER and the step solvers per anatomy (runtime/locomotion.js): the B11 hexapod moved there as its first case
// (the same arithmetic in the same order), the limbed case (quad / biped on any base's leg chains)
import { hexapodMotion, limbedMotion } from './locomotion.js';
// (A1) THE ONE CONTRACT on every creature (runtime/spine.js): speed / turn / walkTo / setHeading / fly / land / anchor / parts /
// say / talking / setTalkEnvelope / idles, the node-constraint pass; nothing runs until its call is made
import { attachSpine } from './spine.js';

// the display weights setDisplay drives (0..1 each; ringFlash: the rings' blue, 0 covered .. 1 exposed). remix.js's
// mood recipes drive the same keys
export const DISPLAY_KEYS = ['darkAll', 'dark', 'eyering', 'spots', 'mottle', 'clouds', 'rings', 'ringFlash', 'glow'];

function hash01(i, seed) {
    // lowbias32 (the forge's hash), to [0, 1)
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 8) / 16777216;
}

// THE SKIN DISPLAY (DESIGN.md skin display families), one builder per family: each takes the colour so far, the
// uniforms (create()'s U), the packs it reads (MASKS, DISPLAY) and the position its pattern reads, and returns what the
// stack needs next. skinMaterial() runs them in order over the tinted skin; remix.js runs the same ones at the same
// places over its palette-remapped skin (its own layers between them), so a remixed creature shows this display and
// setDisplay drives both alike (remix.js's mirror of these terms drifted behind the r4 review's corrections)
export function displayPosition() {
    // the procedural patterns ride the SKIN: the bind-pose position (positionLocal is the skinned position, and every
    // pattern slid over the arms as they moved)
    return THREE.positionGeometry || THREE.positionLocal;
}

export function displayMasks(col, U, disp) {
    // the DISPLAY pack's chromatophores and leucophores, weighted by the uniforms: a whole-body darkening through the
    // mottle (the dark state the white spots stand out against), the dark bands and blotches, the eye ring, the white
    // spots, the mottle
    const { vec3, float, mix } = THREE;
    col = mix(col, col.mul(0.32), U.darkAll.mul(disp.a.mul(0.5).add(0.5)));
    col = mix(col, col.mul(0.42), disp.b.mul(U.dark));
    col = mix(col, col.mul(0.55), disp.g.mul(U.eyering));
    // leucophores reflect broadband, at most ~70 % (REAL_OCTOPUS_COLOUR §1 row 15; 0.86 sat above the skin envelope)
    col = mix(col, vec3(0.62, 0.60, 0.56), disp.r.mul(U.spots));
    return col.mul(float(1.0).add(disp.a.sub(0.5).mul(U.mottle)));
}

export function displayClouds(col, U, disp, masks, pg) {
    // PASSING CLOUDS (cuttlefish, octopus): one or two broad, soft dark fronts per body length sweeping out from the
    // crown (~0.15 m/s), mostly over the mantle, head and webs, fading out along the arms, going dark brown (r4 review:
    // eight narrow maroon bands on every arm read as tiger stripes; scaling the colour kept the brick's red). The phase
    // runs on the scene's time (U.t), so offline renders are deterministic.
    // The fronts sweep one way, posterior to anterior: from the mantle's apex over the mantle and the head, then out
    // along the webs and arms (the arc coordinate: the distance from the apex point, U.cloudApex, the creature's own
    // socket_mantle_apex at bind; r4 review: measured from the crown they ran up the mantle; r4's height below the apex
    // ran backward over v4's mantle, which lies level). Returns { col, dAn }: the photophores' wave travels along the
    // same arc
    const { vec3, float, mix, sin, smoothstep } = THREE;
    const dArm = pg.xz.length();
    const dAn = pg.sub(U.cloudApex).length();
    const vnoise = THREE.mx_noise_float ? THREE.mx_noise_float(pg.mul(9.0)) : float(0.0);
    const phase = dAn.mul(U.cloudK).add(disp.a.sub(0.5).mul(1.4)).add(vnoise.mul(1.0));
    const wave = sin(phase.sub(U.t.mul(U.cloudW)));
    const cloud = smoothstep(0.30, 0.85, wave).mul(smoothstep(0.05, 0.8, disp.a.add(vnoise.mul(0.25)).add(0.2)))
        .mul(float(1.0).sub(smoothstep(0.30, 0.55, dArm))).mul(float(1.0).sub(masks.g.mul(0.7))).mul(U.clouds);
    return { col: mix(col, vec3(0.040, 0.030, 0.025), cloud.mul(0.85)), dAn };
}

export function displayRings(col, U, masks, pg) {
    // BLUE RINGS (the blue-ringed octopus's alarm display; iridophores): rings on a near-regular cell network in the
    // creature's own space (low jitter, so no two rings touch and no small cell fills solid: r4 review, a giraffe
    // print), each a dark brown disc inside a thin iridescent blue band (~13 % of its diameter) with black borders on
    // both sides, on an ochre flood; not on the sucker discs or the oral side. The flood and the borders hold for the
    // whole display; only the blue FLASHES (muscles round each ring expose and conceal its iridophores, Mathger et al.
    // 2012), going from a covered blue-black to full blue at one hue. The blue lives in the albedo (a thin film at
    // 260 nm peaked toward lilac, and an emissive ring term glowed in shade; r4 review). Flat, they read as stickers
    // (the v4 engine render: one ring size everywhere, perfect circles, an ochre flood that replaced the skin): the
    // flood and the discs now TINT the skin, keeping its own light and dark; the rings vary in size over the body and
    // shrink out along the arms (Hapalochlaena: the mantle's rings the largest, the arms' small); their outlines wander a
    // little. Needs the MaterialX noise in three's TSL; without it the rings are skipped, never broken
    const { vec3, float, mix, smoothstep, dot, clamp } = THREE;
    const worley = THREE.mx_worley_noise_float;
    if (!worley) return col;
    const noise = THREE.mx_noise_float || (() => float(0.0));
    const scale = U.ringScale.mul(float(1.0).add(smoothstep(0.10, 0.40, pg.xz.length()).mul(1.2)));
    const f1 = worley(pg.mul(scale), float(0.35));
    const dr = f1.sub(U.ringR.mul(float(0.84).add(noise(pg.mul(6.0)).mul(0.16)))).add(noise(pg.mul(80.0)).mul(0.012));
    const band = float(1.0).sub(smoothstep(0.022, 0.038, dr.abs()));
    const border = float(1.0).sub(smoothstep(0.050, 0.070, dr.abs())).sub(band).max(0.0);
    const inside = float(1.0).sub(smoothstep(-0.05, -0.03, dr)).mul(float(1.0).sub(band).sub(border).max(0.0));
    const rk = U.rings.mul(float(1.0).sub(masks.b)).mul(float(1.0).sub(masks.g.mul(0.8)));
    const blue = vec3(0.0, 0.32, 1.0);
    // the skin's own light and dark under the flood (its luminance against the resting skin's ~0.11)
    const shade = clamp(dot(col, vec3(0.2126, 0.7152, 0.0722)).div(0.11), 0.55, 1.45);
    col = mix(col, vec3(0.62, 0.48, 0.10).mul(shade), rk.mul(0.85));
    col = mix(col, vec3(0.050, 0.034, 0.022).mul(shade), inside.mul(rk));
    col = mix(col, vec3(0.006, 0.006, 0.008), border.mul(rk));
    return mix(col, mix(blue.mul(0.06), blue, U.ringFlash), band.mul(rk));
}

export function displayFuzz(col, U, ndv, w = U.fuzz) {
    // a rim term for remixed velvety skins only (wet skin's grazing response is its Fresnel: r4 review, the fuzz read
    // as pale dusty silhouettes): U.fuzz, 0 by default; remix.js weights it by its surface layer and metalness (w)
    const { float, pow } = THREE;
    return col.add(pow(float(1.0).sub(ndv), 2.5).mul(0.10).mul(w));
}

export function displayPhotophores(col, U, masks, pg, dAn) {
    // PHOTOPHORES: a remix family (no benthic octopus has them): small organs on about a third of the cells, VENTRAL
    // (counter-illumination), flashing in a wave that travels out from the apex along the clouds' arc (dAn). Each
    // organ sits inside its own lattice cell (its centre jittered at most 0.2 cell), so its id and its disc agree and
    // none is clipped (r4 review: Worley discs cut by floor(p) ids into ovals). By day an organ reads as a dark cup with
    // a glint; it glows in the dark (U.night). Returns { col, emissive }, or null without the MaterialX noise in three's
    // TSL (skipped, never broken)
    const { vec3, float, mix, sin, smoothstep } = THREE;
    const cellNoise = THREE.mx_cell_noise_float;
    if (!cellNoise) return null;
    const pp = pg.mul(U.glowScale);
    const cell = pp.floor();
    const id = cellNoise(cell);
    const jit = vec3(cellNoise(cell.add(vec3(17.0, 0.0, 0.0))), cellNoise(cell.add(vec3(0.0, 31.0, 0.0))),
        cellNoise(cell.add(vec3(0.0, 0.0, 47.0)))).sub(0.5).mul(0.4);
    const dd = pp.fract().sub(0.5).sub(jit).length();
    const organ = float(1.0).sub(smoothstep(0.07, 0.11, dd)).mul(smoothstep(0.62, 0.70, id)).mul(masks.g)
        .mul(U.glow);
    const pulse = sin(U.t.mul(U.glowRate).sub(dAn.mul(40.0)).add(id.mul(1.2))).mul(0.5).add(0.5);
    return {
        col: mix(col, vec3(0.025, 0.022, 0.024), organ.mul(0.85)),
        emissive: U.glowColor.mul(organ.mul(pulse.mul(0.85).add(0.15)).mul(U.night.mul(0.9).add(0.1)).mul(6.0)),
    };
}

export function displayGrowth(src, U, st) {
    // the GROWTH pack (work/bestiary/patches/material_ids_v2.md) in KHR_materials_iridescence's texture slot at factor
    // 0: R the growth id mask, G iridescence, B emissive mask, A the pulse's phase. null without the pack (an existing
    // glb takes no growth term at all). Returns { grow, skinOnly, emissive }: skinOnly (1 - R) holds the skin-only
    // terms off growth texels (the element halo round a root is skin: the forge bakes it into the skin's albedo, the
    // ORM's B and the thin mask, so these terms act on it; patches/halo_v2.md); the glow is R10's colour x mask^2 x
    // intensity x a pulse whose phase is the crystal's or the vein cell's
    const { texture, float, sin } = THREE;
    if (!src.iridescenceMap) return null;
    src.iridescenceMap.colorSpace = THREE.NoColorSpace;
    const grow = texture(src.iridescenceMap, st);
    const pulse = sin(U.t.mul(U.growRate).add(grow.a.mul(6.2832))).mul(0.5).add(0.5).add(U.growFade).clamp(0.0, 1.0);
    return { grow, skinOnly: float(1.0).sub(grow.r),
        emissive: U.growGlow.mul(grow.b.mul(grow.b)).mul(U.growGlowI).mul(pulse) };
}

// C5d (the lead's call 3): the hose pads' CONTACT darkening on the skin (padContactAO): at most this many pads, the
// darkening at a footprint's edge, and its profile across the edge (m: full this far inside, none this far outside;
// none this far off the footprint's plane)
const PAD_CONTACTS = 6;
const PAD_AO = 0.55;
const PAD_AO_IN = -0.0008, PAD_AO_OUT = 0.0030, PAD_AO_OFF = 0.006;

// C5e (the lead's C5e call 3): the pads' CONTACT SHADOW on the DIRECT light (padContactShadow, through three's
// receivedShadowNode: every shadow-casting light's term on the skin, the sun's): the direct light kept at 1 - PAD_SH at
// a footprint's edge, back to full PAD_SH_OUT outside it (full PAD_SH_IN inside), within PAD_SH_OFF of its plane. The
// AO above darkens only the indirect light (the sky's, the environment's), so in sun the pads read pasted on
function padFootprint(P, pg, S = null) {
    // a pad's footprint (C5d's contact; C5e: the bind space's image of the pad's underside rectangle by an affine map,
    // runtime/cyborg_cable.js contacts): the bind position pg read through the map's DUAL axes (P.x.xyz along the hose,
    // P.n.xyz across it) as the pad's own coordinates (m, at the reference pose), their signed distance to the rectangle
    // of half-sizes P.c.w x P.x.w round P.c.xyz (rounded outside its corners), and pg's distance off the footprint's
    // plane (its normal the two axes' cross product). C5f: with S (a vec4 uniform, its xy a sweep in the pad's own
    // coordinates) the rectangle SWEPT along it: the box round the sweep, its centre moved half of it, its half-sizes
    // grown by half of it on each axis
    const { vec2, max, min } = THREE;
    const d = pg.sub(P.c.xyz);
    let u = d.dot(P.x.xyz), v = d.dot(P.n.xyz), hl = P.c.w, hw = P.x.w;
    if (S) {
        u = u.sub(S.x.mul(0.5));
        v = v.sub(S.y.mul(0.5));
        hl = hl.add(S.x.abs().mul(0.5));
        hw = hw.add(S.y.abs().mul(0.5));
    }
    const q = vec2(u.abs().sub(hl), v.abs().sub(hw));
    return { sd: max(q, 0.0).length().add(min(max(q.x, q.y), 0.0)), off: d.dot(P.x.xyz.cross(P.n.xyz).normalize()).abs() };
}

const PAD_SH = 0.85;
const PAD_SH_IN = -0.0005, PAD_SH_OUT = 0.0014, PAD_SH_OFF = 0.003;

// CROSSBREED M2c: a part's CHITIN takes the beetle's own coat rules (work/bestiary/engine_test/beetle_cuticle.js, the
// same values: one constant each once the beetle's material lands here): the 8-bit normal codes' own length error read as
// no variance (Toksvig), the specular AA's footprint variance scale and its cap, the maps' anisotropic filtering
const TOKSVIG_DEAD = 0.0035;
const SAA_SIGMA2 = 0.15915494, SAA_KAPPA = 0.18;
const CHITIN_ANISOTROPY = 16;
// (the M2c restart) and its SETAE as the beetle's own sheen (beetle_cuticle.js SETAE_SHEEN / SETAE_SHEEN_ROUGH: the hairs'
// forward-scattered gold, three's Charlie lobe), its amount per texel the part's masks G (arthropod_skin: the hairs'
// coverage x the zone's SHEEN_W; the tibia's inner-edge fringe, the tarsi's ventral brushes)
const SETAE_SHEEN = [0.95, 0.66, 0.32], SETAE_SHEEN_ROUGH = 0.45;

function padContactAO(U, pg) {
    // the skin's occlusion under and round each pad of the hose (C5d, the lead's call 3): its footprint in the BIND
    // space (the cable's contacts: centre, axis along the hose, normal, half-length and half-width), a rounded
    // rectangle whose distance darkens the skin from PAD_AO at the edge to none PAD_AO_OUT outside it; it follows the
    // skin because it lives where the skin's own bind positions are (the baked AO knows nothing of the pads, and the
    // shadow map's ~1.2 mm texel cannot resolve them)
    const { float, smoothstep } = THREE;
    let occ = float(1.0);
    for (const P of U.padAO) {
        const { sd, off } = padFootprint(P, pg);
        const near = float(1.0).sub(smoothstep(PAD_AO_OFF, PAD_AO_OFF * 2.0, off));
        occ = occ.mul(float(1.0).sub(float(1.0).sub(smoothstep(PAD_AO_IN, PAD_AO_OUT, sd)).mul(near).mul(P.n.w)));
    }
    return occ;
}

function padContactShadow(U, pg) {
    // C5e: the direct light's contact factor round each pad (the same footprints; a pad's weight P.n.w 0 leaves an unused
    // slot dark-free): 1 - PAD_SH at the edge, a steeper profile than the AO's so it reads as the line where the rigid
    // pad meets the skin. C5f (the lead's call 9: right but faint at 1080p, a little wider on the sun side): each
    // footprint swept TOWARD the sun (P.s: the cable's contactSweeps, set every update), so the line widens on the
    // pad's sunlit base, the only side it shows (beyond the pad the hose's own cast shadow already takes the sun's
    // light) and keeps PAD_SH_OUT elsewhere
    const { float, smoothstep, step } = THREE;
    let sh = float(1.0);
    for (const P of U.padAO) {
        const { sd, off } = padFootprint(P, pg, P.s);
        const near = float(1.0).sub(smoothstep(PAD_SH_OFF, PAD_SH_OFF * 2.0, off));
        const on = step(1e-6, P.n.w).mul(PAD_SH);
        sh = sh.mul(float(1.0).sub(float(1.0).sub(smoothstep(PAD_SH_IN, PAD_SH_OUT, sd)).mul(near).mul(on)));
    }
    return sh;
}

// STAGE 2B (work/bestiary/patches/landing2b_bestiary.md): the skin's GROUND OCCLUSION on its indirect light. The baked AO
// was made at the open bind pose and three's environment has no ground, so every posed surface near the sand that faces
// it took the whole lower hemisphere of the sky map: the oral web under the margins' arches, the arms' undersides and the
// sucker discs read pale grey-white (98 % of the her frame wedge's light was the environment's; with the sun alone they
// are black), where the live animal shows a dark cavity under its arches (CROWN_STUDY c226, c228). A surface facing down
// at height h over the creature's sand takes its indirect light from the sand round it, cosine-weighted R^2 / (R^2 + h^2)
// of it within R; under the creature (its VENTRAL side, the masks pack's G: the oral web, the arms' oral faces, the cups)
// that sand lies in the creature's own shadow, out at a flank (GO_SIDE of it) much of it is lit. So its indirect light is
// cut by U.groundAO x how far it faces down x R^2 / (R^2 + h^2) x (GO_SIDE .. 1 by the ventral mask)
const GO_R = 0.10;                 // m: the shadowed sand's reach round the crown (half the term at this height)
const GO_UP = 0.35;                // a normal this far over the horizontal (its world y) is not occluded
const GO_SIDE = 0.5;               // the term's share on a non-ventral surface (a flank facing the lit sand beside it)

export function groundOcclusion(U, ventral) {
    // (remix.js's skin takes it too) ventral: the surface's ventral weight (0..1, a node)
    const { positionWorld, normalWorldGeometry, float, smoothstep, mix } = THREE;
    const down = smoothstep(-GO_UP, 1.0, normalWorldGeometry.y.negate());
    const h = positionWorld.y.sub(U.groundY);
    const near = float(GO_R * GO_R).div(h.mul(h).add(GO_R * GO_R));
    return float(1.0).sub(down.mul(near).mul(mix(float(GO_SIDE), float(1.0), ventral)).mul(U.groundAO));
}

function skinMaterial(src, U) {
    const { texture, uv, vec3, vec4, float, mix, normalMap, normalView, positionViewDirection } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap]) {
        if (t) t.colorSpace = THREE.NoColorSpace;
    }
    const m = new THREE.MeshSSSNodeMaterial();
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    const disp = src.emissiveMap ? texture(src.emissiveMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    const pg = displayPosition();
    // CROSSBREED M2 (patches/crossbreed_m2_bestiary.md): the GRAFT pack (CROSSBREED §2.8, ASSEMBLE's: in
    // KHR_materials_sheen's colour texture at factor 0; R the CLASS, 0 the base's soft skin and 1 CHITIN; G the
    // membrane dressing; B harmonize; A z / L_band), only on a crossbreed's part: a plain glb has no sheen map and builds
    // exactly the skin it did. Per pixel inside this one material: chitin takes its own albedo (no palette tint, no
    // display, no fuzz, no photophores) and the beetle's cuticle layers (the B8 round's model, forge/species/
    // stag_beetle_skin.py: the epicuticle a hard CLEAR COAT whose roughness the ORM's B carries, polished on the high
    // points and duller in the punctation; under it the pigmented base at its baked roughness, specularIntensity 0.2 at
    // the cuticle's ior: a total F0 ~0.05, the measured chitin's 0.046-0.062, BEETLE_PLAN §5.1; no wet roughening), a
    // faint warm rim transmission on the thin mask only, and, as a remix option, the jewel-beetle thin film over the
    // iridophore mask (display G; U.chitinIrid, 0 on the realistic stag beetle: §5.5; M2b: one of the beetle's own
    // families, read by name from the part material's extras: create's opts.chitin.family); the membrane keeps the
    // skin's lobe and loses the chromatophore display
    let gpk = null, jw = null;
    if (src.sheenColorMap) {
        src.sheenColorMap.colorSpace = THREE.NoColorSpace;
        gpk = texture(src.sheenColorMap, st);
        jw = U.chitinIrid.mul(disp.g);            // the film's weight: its strength over the iridophore mask
        // (M2c, the lead's call 4) the part's maps ANISOTROPICALLY filtered (the beetle's own runtime's rule,
        // beetle_cuticle.js: a grazing view took a mip chosen by its footprint's long axis and the relief went flat there)
        for (const t of [src.map, src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap, src.sheenColorMap]) {
            if (t) { t.anisotropy = CHITIN_ANISOTROPY; t.needsUpdate = true; }
        }
    }
    // the GROWTH pack (null without one). Where its id mask holds a texel, the skin-only terms (the palette tint, the
    // display masks with their whole-body darkening, the clouds, the rings, the fuzz, the photophores, wet roughening,
    // the subsurface floor) hold off: each family's builder runs as on a plain creature and its result is blended back
    // by skinOnly here, so the builders remix.js shares stay as they are. A growth texel takes the growths' tint
    // (U.growTint, as growthMaterial), so a crystal's foot in the skin set matches the growths mesh beside it
    const gr = displayGrowth(src, U, st);
    const gate = (before, after) => (gr ? mix(before, after, gr.skinOnly) : after);
    // the colour change: the display patterns over the baked resting skin, family by family (the builders above)
    const tinted = base.rgb.mul(gr ? mix(U.growTint, U.tint, gr.skinOnly) : U.tint);
    let col = gate(tinted, displayMasks(tinted, U, disp));
    const clouds = displayClouds(col, U, disp, masks, pg);
    col = gate(col, clouds.col);
    col = gate(col, displayRings(col, U, masks, pg));
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    col = gate(col, displayFuzz(col, U, ndv));
    // CROSSBREED M2: the membrane, the chitin (M2b: darkened toward the melanin backing where a jewel family's film acts)
    if (gpk) col = mix(mix(col, tinted, gpk.g), base.rgb.mul(mix(float(1.0), U.chitinDarken, jw)), gpk.r);
    m.colorNode = col;
    const ntex = texture(src.normalMap, st);
    m.normalNode = normalMap(ntex);
    // ONE wet lobe at water's F0 0.020 (the study's skin contract; a clear coat over a base lobe doubled the specular)
    // with the baked roughness; drying (wet -> 0) roughens it (skin only: a growth keeps its baked roughness)
    m.ior = 1.33;
    const rough = mix(orm.g.add(0.18).min(1.0), orm.g, U.wet);
    m.roughnessNode = gr ? mix(rough, orm.g, gr.grow.r) : rough;
    if (gpk) {
        // CROSSBREED M2: chitin's coat over its base (the skin's clear coat stays 0: its one wet lobe as before)
        m.iorNode = mix(float(1.33), U.chitinIOR, gpk.r);
        // (the M2c fresh eyes) THE SHEEN LOBE'S NaN: three r184's sheen visibility V_Neubelt = 1 / (4 (NdotL + NdotV -
        // NdotL NdotV)) has no floor (its GGX term has max(EPSILON)): a back-lit fragment whose shading normal faces away
        // from the eye (both clamped to 0: along the part's silhouettes and creases) gives Inf, and Inf times its zero
        // irradiance, or the zero sheen of the skin and the bare chitin, is NaN: pure-black slivers in the close-ups, the
        // MSAA resolve blackening whole edge pixels. The lobe runs on the whole part material (useSheen: sheenNode !==
        // null), so the part's shading normal is kept a hair on the eye's side (N.V >= 1e-3): the term stays finite and
        // only those grazing fragments move
        const nEye = m.normalNode.dot(positionViewDirection);
        m.normalNode = m.normalNode.add(positionViewDirection.mul(float(1.0e-3).sub(nEye).max(0.0))).normalize();
        // (M2c, the lead's call 4: the coat mirrored the beach sky as a smooth grey pipe) THE BEETLE'S OWN COAT RULES
        // (beetle_cuticle.js): TOKSVIG, each mip's filtered normal shorter by the relief it averaged, its length r giving
        // the von Mises-Fisher concentration and the slope variance 2 (1 - r^2) / (3 r - r^3) joining alpha^2 of both
        // lobes (mip 0's own sub-texel spread is the forge's, folded into the ORM by arthropod_skin), and SPECULAR AA,
        // the shading normal's variance over the pixel footprint; on chitin only (the skin's lobe as before)
        const rl = ntex.rgb.mul(2.0).sub(1.0).length().add(TOKSVIG_DEAD).min(1.0), r2 = rl.mul(rl);
        const dnx = THREE.dFdx(m.normalNode), dny = THREE.dFdy(m.normalNode);
        const varN = r2.oneMinus().mul(2.0).div(rl.mul(3.0).sub(r2.mul(rl)).max(1.0e-4)).min(0.5)
            .add(dnx.dot(dnx).add(dny.dot(dny)).mul(2.0 * SAA_SIGMA2).min(SAA_KAPPA)).mul(gpk.r);
        const toksvig = (r) => r.mul(r).mul(r).mul(r).add(varN).pow(0.25).min(1.0);
        // (the jewel option, where it acts: the film's base lobe at full strength under a thinner coat, the B8 recipe;
        // M2b: and POLISHED, the beetle's own runtime's rule, beetle_cuticle.js FILM_POLISH: the lobe at 0.45 of the coat's
        // roughness, the multilayer as smooth as the epicuticle: on the base's 0.55-0.6 the film's colour spread as a
        // painted wash)
        m.roughnessNode = mix(rough, toksvig(mix(orm.g, orm.b.mul(0.45), jw)), gpk.r);
        const si = mix(float(1.0), mix(float(0.2), float(1.0), jw), gpk.r);
        m.specularIntensityNode = si;
        // three r184 never reads specularIntensityNode (MeshPhysicalNodeMaterial.setupSpecular takes the material's
        // specularIntensity property): the chitin's base lobe ran at full strength (F0 0.056, F90 1 at the base's
        // roughness) under the coat, a broad grey sheen over the dark cuticle. So this one material's setupSpecular is
        // three's own with si per pixel in place of that property (1 on the skin and the membrane: unchanged there)
        m.setupSpecular = function () {
            const T = THREE.TSL;
            T.ior.assign(float(this.iorNode));
            T.specularColor.assign(T.min(T.pow2(T.ior.sub(1.0).div(T.ior.add(1.0))), vec3(1.0)).mul(si));
            T.specularColorBlended.assign(mix(T.specularColor, T.diffuseColor.rgb, T.metalness));
            T.specularF90.assign(mix(si, float(1.0), T.metalness));
        };
        // (M2b: the family's coat thinning; M2c: the coat a quarter lost under full setae coverage, the beetle's own rule,
        // arthropod_skin SETAE_COAT_LOSS; 0 off the setae. M2d: and lost on the hairs themselves and on the young cuticle at
        // the socket, graft_socket.GROWN_ROOT) its loss per texel in the GRAFT pack's B (M2d: the packs opaque, as the
        // engine's image decode divides colour by a partial alpha: in M2c's masks A it zeroed the thin rims, the sheen and
        // the accents wherever the loss was 0; the graft pack's B, harmonize, is 0 and unread on a part)
        const coatLoss = gpk.b;
        m.clearcoatNode = gpk.r.mul(mix(float(1.0), U.chitinCoat, jw)).mul(float(1.0).sub(coatLoss));
        m.clearcoatRoughnessNode = toksvig(orm.b);                          // (M2c: Toksvig, as the base lobe)
        m.clearcoatNormalNode = m.normalNode;     // the coat on the shell's own relief (three's default: the geometry's)
        // (the M2c restart) the setae's golden sheen on chitin only (the skin and the membrane: none)
        m.sheenNode = vec3(...SETAE_SHEEN).mul(masks.g.mul(gpk.r));
        m.sheenRoughnessNode = float(SETAE_SHEEN_ROUGH);
    }
    // the growth families' metalness and the halo's from the ORM's B (shipped lossless with the pack; no pack: skin, 0)
    m.metalnessNode = gr ? orm.b : float(0.0);
    m.aoNode = orm.r;
    if (U.aoFloors) {
        // a mounted mech arm's AO FLOOR (the lead's C5c decision 5; mountCyborgParts sets it): the suckers the cut hides
        // short of the ring (kept, they would pass 1.1-1.8 mm through the collar) sat on skin baked black under them,
        // shown as a black line once they were hidden. On that strip (chord 7's frame: x from the hidden suckers' start
        // to the ring, within the angle round the oral side, -y, they span) the occlusion is floored at AO_FLOOR, the
        // skin's own round them; elsewhere, and on a creature without a mech arm, the occlusion is the baked one. C5d
        // (the lead's call 4): ONE FLOOR PER MECH PART, each its own uniform triple (C5c's single one: a second arm's
        // mount overwrote the first's strip, which rendered black again)
        const { smoothstep, max } = THREE;
        let ao = orm.r;
        for (const F of U.aoFloors) {
            const q = F.M.mul(vec4(pg, 1.0)).xyz;
            const B = F.box;
            const inX = smoothstep(B.x.sub(B.w), B.x, q.x).mul(float(1.0).sub(smoothstep(B.y, B.y.add(B.w), q.x)));
            const inA = smoothstep(B.z.sub(0.04), B.z, q.y.negate().div(q.yz.length().max(1e-6)));
            ao = max(ao, F.floor.mul(inX).mul(inA));
        }
        m.aoNode = ao;
    }
    if (U.padAO) {
        m.aoNode = m.aoNode.mul(padContactAO(U, pg));
        // C5e (call 3): and the direct light's contact shadow (each shadow-casting light's received shadow scaled)
        const cs = padContactShadow(U, pg);
        m.receivedShadowNode = (shadow) => shadow.mul(cs);
    }
    // STAGE 2B: the posed surfaces near the sand (groundOcclusion), on the indirect light only, after the baked AO
    m.aoNode = m.aoNode.mul(groundOcclusion(U, masks.g));
    const ph = displayPhotophores(col, U, masks, pg, clouds.dAn);
    if (ph) {
        m.colorNode = gate(col, ph.col);
        m.emissiveNode = gr ? ph.emissive.mul(gr.skinOnly).add(gr.emissive) : ph.emissive;
        if (gpk) {                          // CROSSBREED M2: no photophores on chitin or the membrane
            const soft = float(1.0).sub(gpk.r).mul(float(1.0).sub(gpk.g));
            m.colorNode = mix(col, gate(col, ph.col), soft);
            m.emissiveNode = ph.emissive.mul(soft);
        }
    } else if (gr) {
        m.emissiveNode = gr.emissive;
    }
    if (gpk && !gr) {
        // CROSSBREED M2: the remix's jewel-beetle film over the chitin's iridophore mask (0 on the realistic base); (M2b)
        // its thickness inside the family's range, per chitin cell (the display's A: real structural colour drifts
        // across a beetle; the beetle's own pages drive it from their IRID pack, which a part has none of)
        m.iridescenceNode = gpk.r.mul(jw);
        m.iridescenceIORNode = U.chitinFilmIOR;
        m.iridescenceThicknessNode = mix(U.chitinFilmLo, U.chitinFilmHi, disp.a);
    }
    if (gr) {
        // the growths' thin film where their crystals meet the skin (bismuth's oxide); the rings carry their blue in the
        // albedo, so the skin's iridescence is the growths' alone
        m.iridescenceNode = gr.grow.g;
        m.iridescenceIORNode = U.filmIOR;
        m.iridescenceThicknessNode = U.filmThick;
    }
    // subsurface through thin tissue (the webs' margins, the arm tips): warm transmitted light, AMBER (haemocyanin
    // blood, no red flesh glow; the ommochrome pigment absorbs blue: REAL_OCTOPUS_COLOUR §1 row 16; the pink-flesh
    // profile added salmon at every back-lit margin), on the thin mask alone (the forge fades it on a growth texel).
    // (STAGE 4: a 0.06 floor on all skin lit THICK flesh. The lobe faces away from the light, and three draws a
    // single-sided material's shadow map from its BACK faces, so a back-lit receiver is shadowed only by other parts'
    // back faces, never by its own body: looking toward the sun (her ring at az 225-270) the arm roots' oral sides,
    // 30 mm of flesh, glowed gold at floor x lobe scale 3.5, cut by hard terminators where another part's back face fell
    // across them: patches/stage4_skin_transmission.md)
    m.thicknessColorNode = vec3(0.80, 0.45, 0.15).mul(masks.r.mul(0.85));
    if (gpk) {
        // CROSSBREED M2: chitin transmits only at its thin rims (teeth, spurs, claws: BEETLE_PLAN §5.4's faint warm rim)
        m.thicknessColorNode = mix(m.thicknessColorNode, vec3(0.55, 0.20, 0.06).mul(masks.r.mul(0.35)), gpk.r);
    }
    m.thicknessDistortionNode = float(0.12);
    m.thicknessAmbientNode = float(0.02);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(3.0);
    m.thicknessScaleNode = float(3.5);
    m.name = (src.name || 'skin') + '_bestiary';
    return m;
}

export function displayEye(col, U, masks) {
    // the skin's display in the EYE, through its MASKS pack (eyeMaterial below): the palette tint and the whole-body
    // darkening act on the iris's chromatophores (R) alone, and the dark display spreads them over the gold (A) and
    // covers the iridophore band (G). Returns { col, band }: the colour and the band's iridescence weight. remix.js's
    // eye runs it over its palette-remapped iris, so setDisplay({ darkAll }) and palette({ tint }) reach a remixed eye
    const { vec3, float, mix } = THREE;
    col = mix(col, col.mul(U.tint), masks.r);
    // the dark display: the chromatophores darken as the skin's do (x 0.32 under darkAll) and spread over the gold
    // between them (A), taking the expanded pigment's dark red-brown
    col = mix(col, col.mul(0.32), masks.r.mul(U.darkAll));
    col = mix(col, vec3(0.105, 0.035, 0.012).mul(U.tint), masks.a.mul(U.darkAll));
    return { col, band: masks.g.mul(float(1.0).sub(U.darkAll.mul(0.75))) };
}

function eyeMaterial(src, U) {
    // the octopus EYE (forge species/octopus_eye.py; work/bestiary/patches/eye.md). ONE specular lobe at the wet
    // cornea's ior 1.34 (F0 0.021) over a smooth surface: r4's clear coat 1.0 over three's default ior 1.5 stacked two
    // lobes (F0 ~0.08 at normal view, and the coat's environment veil lay over iris and pupil alike: the milky doll
    // eye). The iris's chromatophores take the skin's display through the eye's MASKS pack (KHR_materials_volume's
    // thickness slot, as the skin's: R chromatophore cover, G iridophore band, B pupil, A the cover the chromatophores
    // add as the display darkens): the palette tint and the whole-body darkening act on them alone, so the gold
    // between them and the pupil keep theirs. The iridophore BAND under the pupil is three's thin-film iridescence
    // (film ior 2.0, 220 nm: reflectance ~0.22 gold at normal view, turning green-gold toward grazing; the cornea
    // alone 0.021), view-dependent as the live eyes are (refs 05, 06: bright under a coaxial flash; body 04, 08: dark
    // under top light), and covered as the chromatophores spread in the dark display. An older glb without the pack
    // renders as its albedo under the one lobe
    const { texture, uv, vec4, float, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0);
    const eye = displayEye(texture(src.map, st).rgb, U, masks);
    m.colorNode = eye.col;
    if (src.normalMap) m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = texture(src.roughnessMap, st).g;
    m.metalnessNode = float(0.0);
    m.ior = 1.34;
    m.iridescenceNode = eye.band;
    m.iridescenceIORNode = float(2.0);
    m.iridescenceThicknessNode = float(220.0);
    if (U.eyeGlow) {
        // the ORGANIC GLOW VARIANT (CYBORG_PLAN §4.3.2; built only when create() asks for it: opts.eyeGlow): the eye's
        // own masks glow, the pupil (B: eyeshine) or the iridophore band (G) by U.eyeGlowBand (0 .. 1), in the
        // creature's one cyborg glow colour and pulse (U.cybGlow, cybRate, cybPulse: K16), at U.eyeGlow, on the eyes
        // U.eyeGlowSide picks (left, right: by the bind pose's x, the left eye at +x)
        const { mix, step } = THREE;
        const side = mix(U.eyeGlowSide.y, U.eyeGlowSide.x, step(0.0, displayPosition().x));
        m.emissiveNode = U.cybGlow.mul(mix(masks.b, masks.g, U.eyeGlowBand).mul(U.eyeGlow).mul(side)
            .mul(cyborgPulse(U)));
    }
    m.name = 'eye_bestiary';
    return m;
}

function cyborgUniforms(U, opts = {}, src = null) {
    // the creature's ONE cyborg glow (K16: one emissive family, one colour, one rate), made on first use: from
    // create()'s opts.cyborg ({ glow: a hex / CSS colour or linear [r, g, b], intensity, rate, pulse, tint }), else
    // the part's own extras (its glow row, forge/cyborg.py's), else cyan-blue (0, 0.5, 1), the common machine glow
    if (U.cybGlow) return U;
    const c = opts.cyborg || {};
    const g0 = src?.userData?.glow;
    const col = new THREE.Color();
    if (Array.isArray(c.glow)) col.setRGB(c.glow[0], c.glow[1], c.glow[2]);
    else if (c.glow != null) col.set(c.glow);
    else if (Array.isArray(g0)) col.setRGB(g0[0], g0[1], g0[2]);
    else col.setRGB(0.0, 0.5, 1.0);
    U.cybGlow = THREE.uniform(col);
    U.cybGlowI = THREE.uniform(c.intensity ?? 2.0);   // the old kit's LED iris 2.2, under the bloom's 3.2 (A.5.3)
    U.cybRate = THREE.uniform(c.rate ?? 1.0);         // rad/s: the recipe's glow rate (CYBORG_PLAN §6.1)
    U.cybPulse = THREE.uniform(c.pulse ?? 0.25);      // the pulse's depth (0: steady)
    U.cybTint = THREE.uniform(new THREE.Color(c.tint ?? 0xffffff));   // the primary tint region's colour (K4)
    U.cybAccent = THREE.uniform(new THREE.Color(c.accent ?? 0xffffff));   // the accent region's (masks G, id 70: L1)
    return U;
}

function cyborgPulse(U) {
    // a slow breath: (1 - depth) + depth x (0.5 + 0.5 sin(rate t)), on the scene's time (offline renders deterministic)
    const { float, sin } = THREE;
    return sin(U.t.mul(U.cybRate)).mul(0.5).add(0.5).mul(U.cybPulse).add(float(1.0).sub(U.cybPulse));
}

export function cyborgMaterial(src, U) {
    // a CYBORG PART (forge/cyborg_eye.py: the eye implant; forge/cyborg_limb.py: the mech tentacle): its own baked set
    // under ONE lobe (the metals by the ORM's B; every dielectric at F0 0.04: black oxide, the glazed glow strip, the
    // glass's 0.043 within a hair), the ORM (occlusion R, roughness G, metalness B) and the MASKS pack in
    // KHR_materials_volume's thickness slot (R the primary tint region, G the accent region, B the emissive mask, A
    // wear): the primary region takes U.cybTint, the accent region U.cybAccent (L1: KIT_PORT §3 item 4: masks G, id 70
    // cyb_paint_accent, was baked and never read); the glow is the creature's cyborg glow colour x its intensity x the
    // mask x the pulse (CYBORG_PLAN §5.5)
    const { texture, uv, vec4, mix, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshStandardNodeMaterial();
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0);
    const base = texture(src.map, st).rgb;
    const tinted = mix(base, base.mul(U.cybTint), masks.r);
    // mix(tinted, tinted x accent, masks.g), written so a white accent (the default) adds exactly 0: the colour unchanged
    m.colorNode = tinted.add(tinted.mul(U.cybAccent.sub(1.0)).mul(masks.g));
    if (src.normalMap) m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = orm.g;
    m.metalnessNode = orm.b;
    m.aoNode = orm.r;
    m.emissiveNode = U.cybGlow.mul(masks.b.mul(U.cybGlowI).mul(cyborgPulse(U)));
    m.name = (src.name || 'cyborg') + '_bestiary';
    return m;
}

function beakMaterial(src) {
    // keratinised chitin (n ~1.55), tanned near-black at the rostrum, amber in the wings; wet in the mouth
    const { texture, uv, float, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    m.colorNode = texture(src.map, st).rgb;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = texture(src.roughnessMap, st).g;
    m.metalnessNode = float(0.0);
    m.ior = 1.55;
    m.clearcoatNode = float(0.5);
    m.clearcoatRoughnessNode = float(0.08);
    m.name = 'beak_bestiary';
    return m;
}

// SPECULAR ANTIALIASING for the growths' facets (growthMaterial): Tokuyoshi & Kaplanyan 2019, "Improved Geometric
// Specular Antialiasing" (I3D): GGX's alpha^2 (alpha = roughness^2) plus the variance the SHADING normal takes across
// the pixel's footprint, 2 SIGMA2 (|dn/dx|^2 + |dn/dy|^2), clamped at KAPPA (their constants: SIGMA2 = 1 / 2 pi, the
// pixel filter's variance; KAPPA 0.18). three's own geometric AA (MeshStandardNodeMaterial.setupVariants ->
// getRoughness -> getGeometryRoughness) adds max |d normalViewGeometry| to every roughness, a growth's too, but it reads
// the interpolated VERTEX normal only. The forge's growths low is hard-edged (growth.low_mesh: vertices split per face,
// flat normals), so that term is 0 over every facet of the low and acts only along its edges; and it never reads the
// normal map, which carries much of a growth's facet detail (bismuth's hopper terraces, the crystals' growth steps and
// bevels: baked from the high onto the low's faces). Those facets, a few pixels or less across, kept their baked
// 0.05-0.13 and caught the sun for a single frame (the gallery check: bismuth's one-frame glints). Read from the
// normal-mapped normal, the variance widens a facet as the mip chain and the pixel footprint average it with its
// neighbours, and leaves a large facet's interior at its baked roughness (work/bestiary/patches/gallery_v2.md)
const GROWTH_AA = { SIGMA2: 1.0 / (2.0 * Math.PI), KAPPA: 0.18 };

function growthSpecularAA(rough, nrm) {
    // the roughness after the specular antialiasing (GROWTH_AA above): nrm the shading normal (view space, the normal
    // map's); three then clamps it at 0.0525 and adds its own geometric term (getRoughness)
    const sq = (v) => v.dot(v);
    const k2 = sq(nrm.dFdx()).add(sq(nrm.dFdy())).mul(2.0 * GROWTH_AA.SIGMA2).min(GROWTH_AA.KAPPA);
    return rough.mul(rough).mul(rough).mul(rough).add(k2).min(1.0).sqrt().sqrt();
}

// THE SHARD'S OWN DEPTH, per pixel, for refracting growths (growthMaterial's growTrans). three's Beer's law runs over
// thickness x the model's scale (PhysicalLightingModel getVolumeTransmissionRay): ONE length for every pixel unless the
// thickness node varies, and a shard's depth does vary. Through ice_clear's prisms the refracted view ray crosses p50
// 1.3 mm where it grazes a side and 4.3 mm through the core (ray-cast from the gallery's camera:
// work/bestiary/patches/gallery_v2.md §1.2). The forge's crystals are regular hexagonal prisms with a pyramidal tip
// (growth.py THE STROKE), each its own connected component of the growths mesh. At load each is measured from its welded
// points: the principal axis, the axial extent, the circumradius off the axis. Every vertex then carries its shard's
// axis and the way to the axis's midpoint in its own tangent frame (the normal, the tangent made normal to it, three's
// bitangent cross(n, t) x t.w), so both follow the skin as the normal and the tangent do. Per pixel the depth is the
// refracted view ray's exit from the cylinder inscribed in the prism (radius the apothem, Rc cos 30), held at the
// shard's axial extent, in the mesh's local units (three scales the thickness by the model's scale). Against the
// ray-cast: |error| p50 0.24 mm, 75 % within 0.5 mm (one constant thickness: 1.07 mm, 29 %). Adds the attributes
// shardAxis (the axis in the tangent frame, the apothem) and shardCentre (the way to the axis's midpoint, half the axial
// extent) to geo; null (the caller keeps a constant) without an index, normals or tangents
function growthShardDepth(geo, ior) {
    const P = geo.attributes.position, Nm = geo.attributes.normal, Tg = geo.attributes.tangent, ix = geo.index;
    if (!P || !Nm || !Tg || !ix) return null;
    const nv = P.count, ia = ix.array, ni = ix.count;
    // the shards: positions welded at 1 um, connected over the triangles (union-find)
    const weld = new Map(), wid = new Int32Array(nv).fill(-1);
    for (let k = 0; k < ni; k++) {
        const v = ia[k];
        if (wid[v] >= 0) continue;
        const key = `${Math.round(P.getX(v) * 1e6)},${Math.round(P.getY(v) * 1e6)},${Math.round(P.getZ(v) * 1e6)}`;
        if (!weld.has(key)) weld.set(key, weld.size);
        wid[v] = weld.get(key);
    }
    const nw = weld.size, up = Int32Array.from({ length: nw }, (_, i) => i), wp = new Float64Array(nw * 3);
    const root = (x) => { while (up[x] !== x) x = up[x] = up[up[x]]; return x; };
    for (let k = 0; k < ni; k += 3) {
        const r = root(wid[ia[k]]);
        up[root(wid[ia[k + 1]])] = r;
        up[root(wid[ia[k + 2]])] = r;
    }
    for (let v = 0; v < nv; v++) if (wid[v] >= 0) wp.set([P.getX(v), P.getY(v), P.getZ(v)], 3 * wid[v]);
    const members = new Map();
    for (let w = 0; w < nw; w++) {
        const r = root(w);
        if (!members.has(r)) members.set(r, []);
        members.get(r).push(w);
    }
    // each shard's frame: the axis's midpoint, the axis (its welded points' principal direction: power iteration from
    // the coordinate axis of largest variance), the apothem, half the axial extent
    const frame = new Map();
    for (const [r, ws] of members) {
        const c = [0, 0, 0], C = [0, 0, 0, 0, 0, 0];
        for (const w of ws) for (let i = 0; i < 3; i++) c[i] += wp[3 * w + i] / ws.length;
        for (const w of ws) {
            const x = wp[3 * w] - c[0], y = wp[3 * w + 1] - c[1], z = wp[3 * w + 2] - c[2];
            C[0] += x * x; C[1] += x * y; C[2] += x * z; C[3] += y * y; C[4] += y * z; C[5] += z * z;
        }
        let a = C[0] >= C[3] && C[0] >= C[5] ? [1, 0, 0] : C[3] >= C[5] ? [0, 1, 0] : [0, 0, 1];
        for (let it = 0; it < 64; it++) {
            const b = [C[0] * a[0] + C[1] * a[1] + C[2] * a[2], C[1] * a[0] + C[3] * a[1] + C[4] * a[2],
                C[2] * a[0] + C[4] * a[1] + C[5] * a[2]];
            const l = Math.hypot(b[0], b[1], b[2]) || 1.0;
            a = [b[0] / l, b[1] / l, b[2] / l];
        }
        let h0 = Infinity, h1 = -Infinity, rc = 0.0;
        for (const w of ws) {
            const x = wp[3 * w] - c[0], y = wp[3 * w + 1] - c[1], z = wp[3 * w + 2] - c[2];
            const h = x * a[0] + y * a[1] + z * a[2];
            h0 = Math.min(h0, h);
            h1 = Math.max(h1, h);
            rc = Math.max(rc, Math.hypot(x - h * a[0], y - h * a[1], z - h * a[2]));
        }
        const hm = 0.5 * (h0 + h1);
        frame.set(r, [c[0] + hm * a[0], c[1] + hm * a[1], c[2] + hm * a[2], a[0], a[1], a[2],
            rc * Math.cos(Math.PI / 6), 0.5 * (h1 - h0)]);
    }
    // per vertex: the axis and the way to its midpoint, in the vertex's tangent frame
    const ax4 = new Float32Array(nv * 4), ce4 = new Float32Array(nv * 4);
    const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
    for (let v = 0; v < nv; v++) {
        if (wid[v] < 0) continue;
        const f = frame.get(root(wid[v]));
        const n = [Nm.getX(v), Nm.getY(v), Nm.getZ(v)];
        const ln = Math.hypot(n[0], n[1], n[2]) || 1.0;
        for (let i = 0; i < 3; i++) n[i] /= ln;
        const t = [Tg.getX(v), Tg.getY(v), Tg.getZ(v)];
        const tn = dot(t, n);
        for (let i = 0; i < 3; i++) t[i] -= n[i] * tn;
        const lt = Math.hypot(t[0], t[1], t[2]) || 1.0;
        for (let i = 0; i < 3; i++) t[i] /= lt;
        const s = Tg.getW(v) < 0 ? -1.0 : 1.0;
        const b = [(n[1] * t[2] - n[2] * t[1]) * s, (n[2] * t[0] - n[0] * t[2]) * s, (n[0] * t[1] - n[1] * t[0]) * s];
        const a = [f[3], f[4], f[5]];
        const d = [f[0] - P.getX(v), f[1] - P.getY(v), f[2] - P.getZ(v)];
        ax4.set([dot(a, t), dot(a, b), dot(a, n), f[6]], 4 * v);
        ce4.set([dot(d, t), dot(d, b), dot(d, n), f[7]], 4 * v);
    }
    geo.setAttribute('shardAxis', new THREE.BufferAttribute(ax4, 4));
    geo.setAttribute('shardCentre', new THREE.BufferAttribute(ce4, 4));
    // per pixel: the same frame from the skinned normal and tangent (view space), the view ray refracted as three
    // refracts it (the shading normal, 1 / ior), its exit from the inscribed cylinder, held at the axial extent
    const { attribute, float, normalView, normalViewGeometry, tangentView, tangentGeometry, positionViewDirection,
        refract, select } = THREE;
    const A4 = attribute('shardAxis', 'vec4'), C4 = attribute('shardCentre', 'vec4');
    const ng = normalViewGeometry;
    const tg = tangentView.sub(ng.mul(ng.dot(tangentView))).normalize();
    const bg = ng.cross(tg).mul(tangentGeometry.w);
    const axis = tg.mul(A4.x).add(bg.mul(A4.y)).add(ng.mul(A4.z)).normalize();
    const q = tg.mul(C4.x).add(bg.mul(C4.y)).add(ng.mul(C4.z)).negate();       // the entry off the axis's midpoint
    const dir = refract(positionViewDirection.negate(), normalView, float(1.0 / ior));
    const qa = q.dot(axis), ta = dir.dot(axis);
    const qp = q.sub(axis.mul(qa)), tp = dir.sub(axis.mul(ta));
    const uu = tp.dot(tp).max(1.0e-8), qu = qp.dot(tp);
    const disc = qu.mul(qu).sub(uu.mul(qp.dot(qp).sub(A4.w.mul(A4.w))));
    const sCyl = select(disc.greaterThan(0.0), qu.negate().add(disc.max(0.0).sqrt()).div(uu), float(0.0));
    const sAx = C4.w.sub(qa.mul(ta.sign())).div(ta.abs().max(1.0e-4));
    return sCyl.min(sAx).max(0.0);
}

export function growthMaterial(src, U, opts = {}, geo = null) {
    // the GROWTHS mesh (material_ids_v2.md; study T ships growths as their own mesh in their own material): the family's
    // surface baked by the forge (growth.run_growths), metalness in the ORM's B; no micro normal, fuzz or wetness
    // (REF_SKIN_STUDY R7, R1). Thin film from the growth pack's G with the masks' G as the film's thickness (one per
    // facet: bismuth's terraces each their own colour); the glow as the skin's (displayGrowth); refraction only on
    // request (opts.growTrans: a transmission pass per frame), coloured by absorption through each shard's own depth
    // when geo (the growths mesh's geometry) is passed (growthShardDepth); the baked roughness widened by the specular
    // antialiasing (growthSpecularAA, GROWTH_AA above)
    const { texture, uv, vec3, vec4, float, mix, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    const gr = displayGrowth(src, U, st);
    m.colorNode = texture(src.map, st).rgb.mul(U.growTint);
    const nrm = normalMap(texture(src.normalMap, st));
    m.normalNode = nrm;
    m.roughnessNode = growthSpecularAA(orm.g, nrm);
    m.metalnessNode = orm.b;
    m.aoNode = orm.r;
    if (gr) {
        m.iridescenceNode = gr.grow.g;
        m.iridescenceIORNode = U.filmIOR;
        m.iridescenceThicknessNode = mix(U.filmLo, U.filmHi, masks.g);
        m.emissiveNode = gr.emissive;
    }
    if ((opts.growTrans ?? 0) > 0) {
        // clear ice: refraction through the shards, blocked where frost covers them (masks B). Its colour is VOLUME
        // ABSORPTION (Beer's law), never a surface multiply: three multiplies what shows through by the base colour
        // (getIBLVolumeRefraction: transmittance = diffuseColor x volumeAttenuation), and the forge's albedo is an opaque
        // surface's (ice_clear: the ice crab's measured colour, sRGB8 167,219,231), which turned the backdrop slate-teal
        // (gallery_v2.md §1.2). So the surface is white and the albedo is the ABSORPTION colour (held above 0: three
        // takes its log): light crossing d of ice keeps albedo^(d / D) (three's attenuationColor, attenuationDistance).
        // D = opts.growAttenuation, by default 4.3 mm, the measured core of ice_clear's shards on the octopus [M]: the
        // refracted view ray crosses p50 4.3 mm of ice through a shard's core (the albedo itself) and 1.3 mm where it
        // grazes a side (albedo^0.3, near clear). d is the shard's own depth along that ray, per pixel
        // (growthShardDepth), when the mesh's geometry is passed; else opts.growThickness, three's thickness node, one
        // length for every pixel (remix.js builds its growths without the geometry): by default 4.0 mm, the median
        // depth the camera sees through ice_clear's shards [M]
        const ior = opts.growIOR ?? 1.31;
        m.colorNode = vec3(1.0);
        m.attenuationColorNode = texture(src.map, st).rgb.mul(U.growTint).max(1.0e-3);
        m.attenuationDistanceNode = float(opts.growAttenuation ?? 0.0043);
        m.transmissionNode = float(opts.growTrans).mul(float(1.0).sub(masks.b));
        m.thicknessNode = (opts.growThickness == null && geo ? growthShardDepth(geo, ior) : null)
            ?? float(opts.growThickness ?? 0.004);
        m.ior = ior;
    }
    m.name = (src.name || 'growth') + '_bestiary';
    return m;
}

function suckerMaterial(src, U) {
    // the octopus's GEOMETRIC SUCKERS (forge species/octopus_suckers.py; work/bestiary/patches/sucker_geometry.md):
    // one template texture set stacked by every sucker, its own primitive of the skinned mesh. The skin's lighting
    // contract (MeshSSSNodeMaterial, one wet lobe at ior 1.33, amber subsurface) so the cup's wall and the arm meet
    // without a seam. MASKS (KHR_materials_volume's thickness slot, the skin's channels): R thin tissue (the rim's
    // fringe, the infundibulum's cuticle), G ventral (1), B sucker parts (rim 1, disc .66, cup .33, wall 0), A the WALL
    // (the arm's skin carried up the cup). COLOR_0 per sucker: rgb the arm's skin colour round its base (linear), a its
    // dark band display there: the wall takes the skin's own colour (the ratio to the template's mean wall colour,
    // extras.wall_ref, keeps the template's detail), and the pigmented parts (the wall and the rim band) take the
    // skin's display (displayMasks / displayClouds / displayRings over a per-sucker display pack: dark bands from
    // COLOR_0.a, mottle 0.5), so a dark display or a passing cloud crosses the cups as it crosses the arm; the pale disc
    // keeps its colour
    const { texture, uv, vec3, vec4, float, mix, normalMap } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshSSSNodeMaterial();
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 1.0, 0.0, 0.0);
    const wr = src.userData?.wall_ref || [0.31, 0.125, 0.08];
    const wallRef = vec3(wr[0], wr[1], wr[2]);
    const vc = THREE.vertexColor ? THREE.vertexColor() : vec4(wallRef, 0.0);
    const wall = masks.a;
    const pig = wall.add(masks.b.sub(0.83).mul(6.0).clamp(0.0, 1.0)).min(1.0);   // the wall and the rim band
    let col = mix(base.rgb, base.rgb.mul(vc.rgb.div(wallRef).clamp(0.25, 4.0)), wall).mul(U.tint);
    const disp = vec4(0.0, 0.0, vc.a, 0.5);
    const pg = displayPosition();
    const shown = displayMasks(col, U, disp);
    const clouds = displayClouds(shown, U, disp, masks, pg);
    col = mix(col, displayRings(clouds.col, U, masks, pg), pig);
    m.colorNode = col;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.ior = 1.33;
    m.roughnessNode = mix(orm.g.add(0.18).min(1.0), orm.g, U.wet);
    m.metalnessNode = float(0.0);
    m.aoNode = orm.r.mul(groundOcclusion(U, masks.g));    // (STAGE 2B: the cups facing the sand, as the skin round them)
    m.thicknessColorNode = vec3(0.80, 0.45, 0.15).mul(masks.r.mul(0.85));     // (STAGE 4: the thin mask alone, as the skin's)
    m.thicknessDistortionNode = float(0.12);
    m.thicknessAmbientNode = float(0.02);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(3.0);
    m.thicknessScaleNode = float(3.5);
    m.name = 'sucker_bestiary';
    return m;
}

// CYBORG PARTS MOUNTED (work/bestiary/patches/cyborg_c5b_bestiary.md; forge/cyborg_octopus.py, forge/cyborg_hose.py;
// research/CYBORG_PLAN.md §4.4; the lead's C5b decisions 2-4). create({ cyborg: { parts: [...] } }) loads each part's
// glb (part.bytes, the ASSETS name part.asset, or part.path) and joins it to the creature, ONE SKELETON per creature:
//   { kind: 'eye_implant', socket: 'socket_eye_L' }  the implant rides that socket (its glb is in the socket's frame:
//        forge/cyborg_eye.py export_glb); the organic eyeball on that side is hidden (t13's cyborg_cut eye ranges)
//   { kind: 'mech_tentacle', chain: 'arm7' }         its joints arm_07..arm_23 ride that arm's own bones by the bind's
//        chord frames: bone k's inverse bind [M_k | -M_k X_k] (M_k = chordQ^-1, the chord frame in the bone's own axes;
//        X_k the joint on the part's straight bind, its extras' bind_x; M_23 = I); each helper joint (cross, shell, rod,
//        crest) a new bone under its parent, posed every frame by its rule (the part's extras: cyborg_limb.HELPER_RULES)
//        from its knuckle's cardan angles; the arm's distal triangles and suckers hidden and its cut ring and the ring
//        before pinned to joint 7 (t13's cyborg_cut: patches/cyborg_c5b_t13.md); the arm's ground line read from the
//        part's radius table (groundProfile)
//   { kind: 'hose', chain: 'arm7' }                  forge/cyborg_hose.py: its skin's joints the creature's own bones by
//        name (the glb carries the creature's inverse binds); its hardware primitive (material extras shares
//        'mech_tentacle') takes the mounted tentacle's material
//   { kind: 'feed', asset: 'cyborg_feed_0' }         forge/cyborg_feed.py (C3d): a plated look's FEED LINES as C5d's
//        cables (each line's glb carries bestiary.cable: re-made every frame on the rendered skin, the hose's path) and
//        their collars and clamps (one glb more, skinned; material extras shares 'mech_tentacle': the mounted tentacle's
//        material, else its own maps under cyborgMaterial)
// C5c (work/bestiary/patches/cyborg_c5c_bestiary.md; the lead's C5c decisions 5-6): every part's hidden ranges dropped
// in ONE pass per primitive (dropRanges: implants on both eyes, two mech arms on two chains), the mounted arm's AO floor
// over the skin its hidden near-roll suckers sat on, and every flesh arm's ground line on its true reach (fleshReach).
// C5d (work/bestiary/patches/cyborg_c5d_bestiary.md; the lead's C5d calls 1-4): the root's reach a SUPPORT FUNCTION of
// each joint's section (fleshSupport, radialMotion's contactPitch); a hose whose glb carries the cable's data
// (forge/cyborg_cable.py) is re-made every frame on the rendered skin (runtime/cyborg_cable.js: its sleeve and pads plain
// meshes the cable drives, its fittings skinned as before), its pads darkening the skin under them (padContactAO); one
// AO floor per mech part.
// A creature without parts runs none of the parts' code: its shaders are the ones it had.
function chordBasis(loc) {
    // a bone's chord frame in its own axes as radialMotion makes it (its chordQ is the inverse): loc the child's rest
    // offset made unit, yref world-up made normal to it, z = loc x yref
    const x = loc.clone().normalize();
    const y = new THREE.Vector3(0, 1, 0).addScaledVector(x, -x.y).normalize();
    return new THREE.Matrix4().makeBasis(x, y, new THREE.Vector3().crossVectors(x, y));
}

// C5c: a flesh arm's lowest point (its skin or a sucker) rests this far into the sand (forge/cyborg_octopus.py
// GROUND_PRESS)
const GROUND_PRESS = 0.0005;

function fleshY(reach, k, rad) {
    // the FLESH arms' ground line (forge/cyborg_octopus.py flesh_line; the lead's C5c decision 6): joint k's centreline
    // height over the ground, its true reach (fleshReach) less GROUND_PRESS, or r4's 0.92 rad where none was measured
    return reach && reach[k] > 0 ? reach[k] - GROUND_PRESS : 0.92 * rad;
}

// CROSSBREED M1 (work/bestiary/patches/crossbreed_m1_bestiary.md; research/CROSSBREED_DESIGN.md review R1, the lead's
// decision 4): the radial base's ARM CHAINS from the glb's own chain records (extras.bestiary.chains: C0b's, which
// ASSEMBLE, forge/assemble.py, rewrites for a GRAFTED chain, whose joints past its root are the part's own: arm0_00 ..
// arm0_08, arm0_g09 .. arm0_g23), in the records' order, each the bones its record names and its per-joint radius; a
// glb without records (every glb before C0b lands) keeps the name scan arm<j>_<kk> from 0 until a name is missing, so
// its motion is the one it had. A record of another anatomy is no arm here (its base's own motion reads it)
export function armChains(gltf, bones) {
    const recs = gltf?.userData?.bestiary?.chains;
    const out = [];
    if (Array.isArray(recs) && recs.length) {
        for (const r of recs) {
            if ((r.anatomy || r.kind) !== 'tentacle') continue;
            const chain = r.joints.map((n) => bones.get(n));
            const miss = r.joints.filter((n, k) => !chain[k]);
            if (miss.length) throw new Error(`[Bestiary] chain ${r.name}: joints ${miss.join(', ')} are no bones of this glb`);
            // CROSSBREED M2: a graft of another ANATOMY on this chain (the record's graft.anatomy: 'arthropod_leg', the
            // beetle's tibia, tarsomeres and claws from joint graft.first on): its own step solver poses it (solveLeg)
            // (M2b: the native arm's bind length, the plain resting path's, where the record carries it)
            const g = r.graft;
            const leg = g?.anatomy === 'arthropod_leg'
                ? { first: g.first, roles: g.roles, knee: g.knee, nativeLength: g.native_length ?? null } : null;
            out.push({ name: r.name, bones: chain, radius: Array.isArray(r.radius) ? r.radius : null, leg });
        }
        return out;
    }
    for (let j = 0; bones.get(`arm${j}_00`); j++) {
        const chain = [];
        for (let k = 0; bones.get(`arm${j}_${String(k).padStart(2, '0')}`); k++) {
            chain.push(bones.get(`arm${j}_${String(k).padStart(2, '0')}`));
        }
        out.push({ name: `arm${j}`, bones: chain, radius: null });
    }
    return out;
}

export function fleshReach(group, bones, chains = null) {
    // every arm's TRUE REACH below each joint's chord axis at the bind (forge/cyborg_octopus.py Octopus.flesh_reach,
    // term by term): over the skin's vertices (one shared vertex set) and the suckers' whose heaviest bone is arm{j}_kk,
    // the farthest under bone k's chord frame (its y the chord's 'up': chordBasis; the last joint its own frame). r4's
    // 0.92 x taper put the arms' skin 3-8 mm into the sand and their suckers 6-14 mm (c05c p10). Read before any part
    // is mounted (the cut's pin moves the ring's weights). Returns [arm] -> Float64Array per joint (m), 0 where no vertex
    // names the bone. CROSSBREED M1: the chains armChains read (a grafted chain's part vertices name its own joints;
    // none given: the name scan)
    group.updateMatrixWorld(true);
    const gi = new THREE.Matrix4().copy(group.matrixWorld).invert();
    const out = [], info = new Map();
    for (const ch of (chains || armChains(null, bones))) {
        const chain = ch.bones;
        const r = new Float64Array(chain.length);
        out.push(r);
        chain.forEach((b, k) => {
            const W = new THREE.Matrix4().copy(gi).multiply(b.matrixWorld);
            if (k + 1 < chain.length) W.multiply(chordBasis(chain[k + 1].position));
            const P = new THREE.Vector3().setFromMatrixPosition(W);
            const Y = new THREE.Vector3().setFromMatrixColumn(W, 1).normalize();
            info.set(b, { r, k, P, Y });
        });
    }
    const seen = new Set(), v = new THREE.Vector3();
    group.traverse((o) => {
        if (!o.isSkinnedMesh || seen.has(o.geometry.attributes.position)) return;
        seen.add(o.geometry.attributes.position);
        const pos = o.geometry.attributes.position, si = o.geometry.attributes.skinIndex;
        const sw = o.geometry.attributes.skinWeight, sb = o.skeleton.bones;
        for (let i = 0; i < pos.count; i++) {
            let c = 0, w = sw.getX(i);
            for (let q = 1; q < 4; q++) if (sw.getComponent(i, q) > w) { w = sw.getComponent(i, q); c = q; }
            const e = info.get(sb[si.getComponent(i, c)]);
            if (!e) continue;
            const d = -v.fromBufferAttribute(pos, i).sub(e.P).dot(e.Y);
            if (d > e.r[e.k]) e.r[e.k] = d;
        }
    });
    return out;
}

function hull2(xy) {
    // the 2D convex hull's vertices of points [x0, y0, x1, y1, ...] (Andrew's monotone chain; the forge's
    // c5d_motion.hull2): a flat Float64Array
    const P = [];
    for (let i = 0; i < xy.length; i += 2) P.push([xy[i], xy[i + 1]]);
    P.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const U = P.filter((p, i) => i === 0 || p[0] !== P[i - 1][0] || p[1] !== P[i - 1][1]);
    if (U.length < 3) return Float64Array.from(U.flat());
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lo = [], up = [];
    for (const p of U) {
        while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop();
        lo.push(p);
    }
    for (let i = U.length - 1; i >= 0; i--) {
        const p = U[i];
        while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop();
        up.push(p);
    }
    return Float64Array.from(lo.slice(0, -1).concat(up.slice(0, -1)).flat());
}

export function fleshSupport(group, bones, chains = null) {
    // C5d (the lead's call 1): every arm joint's SUPPORT OUTLINE (forge/cyborg_octopus.py Octopus.flesh_support, term by
    // term): its section (the skin's and the suckers' bind vertices whose heaviest bone is arm{j}_kk) in the frame its
    // pitch is read in (chord k's; the last joint chord n - 2's), from the joint, reduced to the convex hull of its
    // (x, y): radialMotion aims every chord with no roll (its y from world up), so the section's reach along world
    // down at pitch phi is max -(x sin phi + y cos phi) over the outline. Read at the bind, before any part is mounted.
    // Returns [arm] -> [joint] -> Float64Array [x0, y0, ...] (empty where no vertex names the bone). CROSSBREED M1: the
    // chains armChains read, as fleshReach (none given: the name scan), so a grafted chain's hulls pair with its reach
    group.updateMatrixWorld(true);
    const gi = new THREE.Matrix4().copy(group.matrixWorld).invert();
    const out = [], info = new Map();
    for (const ch of (chains || armChains(null, bones))) {
        const chain = ch.bones;
        const n = chain.length, pts = chain.map(() => []);
        out.push(pts);
        chain.forEach((b, k) => {
            const kk = Math.min(k, n - 2);
            const W = new THREE.Matrix4().copy(gi).multiply(chain[kk].matrixWorld).multiply(chordBasis(chain[kk + 1].position));
            const P = new THREE.Vector3().setFromMatrixPosition(new THREE.Matrix4().copy(gi).multiply(b.matrixWorld));
            info.set(b, { pts: pts[k], P, X: new THREE.Vector3().setFromMatrixColumn(W, 0).normalize(),
                Y: new THREE.Vector3().setFromMatrixColumn(W, 1).normalize() });
        });
    }
    const seen = new Set(), v = new THREE.Vector3();
    group.traverse((o) => {
        if (!o.isSkinnedMesh || seen.has(o.geometry.attributes.position)) return;
        seen.add(o.geometry.attributes.position);
        const pos = o.geometry.attributes.position, si = o.geometry.attributes.skinIndex;
        const sw = o.geometry.attributes.skinWeight, sb = o.skeleton.bones;
        for (let i = 0; i < pos.count; i++) {
            let c = 0, w = sw.getX(i);
            for (let q = 1; q < 4; q++) if (sw.getComponent(i, q) > w) { w = sw.getComponent(i, q); c = q; }
            const e = info.get(sb[si.getComponent(i, c)]);
            if (!e) continue;
            v.fromBufferAttribute(pos, i).sub(e.P);
            e.pts.push(v.dot(e.X), v.dot(e.Y));
        }
    });
    return out.map((arm) => arm.map((p) => hull2(p)));
}

function supportReach(hull, phi) {
    // a section's reach along world down at its chord's pitch phi (the max over its outline)
    const s = Math.sin(phi), c = Math.cos(phi);
    let m = -Infinity;
    for (let i = 0; i < hull.length; i += 2) m = Math.max(m, -(hull[i] * s + hull[i + 1] * c));
    return m;
}

function contactPitch(hull, y, floor, sinLo) {
    // C5d: the pitch at which a segment's section rests on `floor` (forge c5d_motion.contact_pitch, term by term): the
    // least steep turn up from asin(sinLo) at which y - reach(phi) (the section's lowest point, y the joint's height)
    // reaches the floor, by bisection below the top of y - reach on [asin(sinLo), pi / 2] (a scan of 65); sinLo itself
    // where the section already clears the floor. Returns the sine
    const lo = Math.asin(Math.min(1, Math.max(-1, sinLo)));
    if (y - supportReach(hull, lo) >= floor) return sinLo;
    let best = lo, bestH = -Infinity;
    for (let i = 0; i <= 64; i++) {
        const ph = lo + (0.5 * Math.PI - lo) * (i / 64);
        const h = y - supportReach(hull, ph);
        if (h > bestH) { bestH = h; best = ph; }
    }
    if (bestH < floor) return Math.sin(best);
    let a = lo, b = best;
    for (let it = 0; it < 48; it++) {
        const m = 0.5 * (a + b);
        if (y - supportReach(hull, m) >= floor) b = m; else a = m;
    }
    return Math.sin(b);
}

export function groundProfile(table, len, r0, rTip, cut = 8, firstCardan = 16, ramp = 3, reach = null) {
    // the REPLACED arm's ground line (forge/cyborg_octopus.py ground_profile, term by term): per joint the centreline's
    // height over the ground, null where r4's taper holds. From the part's radius table T (joint -> the machine's reach
    // below its centreline): the cardan section (firstCardan..) rests on each joint's reach; the clevis section
    // (cut..firstCardan) cannot pitch, so ONE straight line from joint cut to firstCardan, as low as no reach sinks
    // under it and never under T[cut] (the flange's soft roll); joint cut - 1 level with joint cut (the flange flat);
    // the `ramp` flesh joints before it rising by arc length from the flesh line (C5c: the arm's true reach, fleshY;
    // r4's without one) onto that height
    const T = {};
    for (const r of table) T[r.joint] = r.oral;
    const n = len.length + 1, s = [0.0];
    for (let k = 0; k < len.length; k++) s.push(s[k] + len[k]);
    const L = s[n - 1] / 0.985;
    const r4 = (k) => fleshY(reach, k, rTip + (r0 - rTip) * Math.pow(Math.max(1.0 - s[k] / L, 0.0), 0.92));
    const H = new Array(n).fill(null);
    for (let k = firstCardan; k < n; k++) H[k] = T[k];
    const t = (k) => (s[k] - s[cut]) / (s[firstCardan] - s[cut]);
    let g0 = T[cut];
    for (let k = cut + 1; k < firstCardan; k++) g0 = Math.max(g0, (T[k] - T[firstCardan] * t(k)) / (1.0 - t(k)));
    for (let k = cut; k < firstCardan; k++) H[k] = g0 + (T[firstCardan] - g0) * t(k);
    H[cut - 1] = H[cut];
    const ka = cut - 1 - ramp;
    if (ramp > 0 && ka >= 1) {
        const ha = r4(ka);
        for (let k = ka + 1; k < cut - 1; k++) H[k] = ha + (H[cut - 1] - ha) * (s[k] - s[ka]) / (s[cut - 1] - s[ka]);
    }
    return H;
}

const _mR = new THREE.Matrix4(), _mA = new THREE.Matrix4(), _mB = new THREE.Matrix4();
const _qH = new THREE.Quaternion(), _vH = new THREE.Vector3();
const _AX = new THREE.Vector3(1, 0, 0), _AY = new THREE.Vector3(0, 1, 0);

export function cardanAngles(R) {
    // a knuckle's relative rotation R (the child's chord frame in the parent's) as its cardan takes it: R = Ry(yaw)
    // Rz(pitch) Rx(roll) (cyborg_limb.cardan_angles: yaw = atan2(-R20, R00), pitch = asin(R10), roll = atan2(M21, M11)
    // with M = (Ry(yaw) Rz(pitch))^T R)
    const e = R.elements;
    const yaw = Math.atan2(-e[2], e[0]);
    const pitch = Math.asin(Math.min(1, Math.max(-1, e[1])));
    _mA.makeRotationY(yaw).multiply(_mB.makeRotationZ(pitch)).transpose().multiply(R);
    const f = _mA.elements;
    return { yaw, pitch, roll: Math.atan2(f[6], f[5]) };
}

function poseHelpers(a) {
    // every helper joint of the arm's mounted part set by its rule (cyborg_limb.pose_joints in local terms) from its
    // knuckle's cardan angles: the knuckle's relative rotation R = M_{k-1}^T L_k M_k (L_k bone k's local rotation);
    // the cross M_{k-1} Ry(yaw) and the crest M_{k-1} Ry(yaw / 2) at the pivot (bone k's rest offset in bone k - 1),
    // the turning shell M_k Rx(-roll) at joint k, the rod slid lc sin(pitch) along its shell's x
    const ang = {};
    for (const h of a.mount.helpers) {
        const k = h.k;
        if (!ang[k]) {
            _mR.copy(a.Minv[k - 1]).multiply(_mB.makeRotationFromQuaternion(a.chain[k].b.quaternion)).multiply(a.M[k]);
            ang[k] = cardanAngles(_mR);
        }
        const g = ang[k];
        if (h.kind === 'cross' || h.kind === 'crest') {
            h.bone.position.copy(a.chain[k].b.position);
            h.bone.quaternion.copy(a.qM[k - 1]).multiply(_qH.setFromAxisAngle(_AY, h.kind === 'cross' ? g.yaw : 0.5 * g.yaw));
        } else if (h.kind === 'shell') {
            h.bone.position.set(0, 0, 0);
            h.bone.quaternion.copy(a.qM[k]).multiply(_qH.setFromAxisAngle(_AX, -g.roll));
        } else if (h.kind === 'rod') {
            _vH.set(h.lc * Math.sin(g.pitch), 0, 0);
            if (h.onShell) {
                h.bone.position.copy(_vH);
                h.bone.quaternion.identity();
            } else {
                h.bone.position.copy(_vH.applyQuaternion(a.qM[k]));
                h.bone.quaternion.copy(a.qM[k]);
            }
        }
    }
}

async function loadPart(part) {
    let bytes = part.bytes || globalThis.ASSETS?.[part.asset];
    if (!bytes) bytes = Deno.readFileSync(part.path);
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return await new globalThis.GLTFLoader().parseAsync(buf, '');
}

function primitiveMeshes(gltf, group) {
    // the creature's meshes by their glTF material's name (the parser's associations: three names a primitive's mesh
    // after its glTF mesh, not its material)
    const out = {}, json = gltf.parser.json;
    group.traverse((o) => {
        if (!o.isMesh) return;
        const as = gltf.parser.associations?.get(o);
        if (as && as.meshes !== undefined && as.primitives !== undefined) {
            const mi = json.meshes[as.meshes].primitives[as.primitives].material;
            if (mi !== undefined) out[json.materials[mi].name] = o;
        }
    });
    return out;
}

export function dropRanges(mesh, ranges) {
    // a primitive's triangles in each [start, start + count) (index units into its ORIGINAL index buffer: t13's
    // cyborg_cut) left out, all of them in ONE pass (C5c, the lead's decision 6: dropped one range at a time, the
    // second range's offsets read the already shortened buffer, so implants on both eyes or two mech arms dropped the
    // wrong triangles); ranges may overlap
    const idx = mesh.geometry.index.array;
    const keep = new Uint8Array(idx.length).fill(1);
    for (const [a, n] of ranges) keep.fill(0, a, a + n);
    let m = 0;
    for (let i = 0; i < idx.length; i++) m += keep[i];
    const out = new idx.constructor(m);
    for (let i = 0, j = 0; i < idx.length; i++) if (keep[i]) out[j++] = idx[i];
    mesh.geometry.setIndex(new THREE.BufferAttribute(out, 1));
}

// the AO floor over the skin the hidden near-roll suckers sat on (the lead's C5c decision 5; skinMaterial): the skin's
// own occlusion round those footprints (work/bestiary/patches/scratch_cyborg_c5c/p14_ao.py: median 0.79, p25 0.70)
const AO_FLOOR = 0.70;

export function cableMeshes(cable, meshes, x) {
    // C5d: the hose's SLEEVE and PADS as plain meshes the cable drives (positions, normals and tangents its arrays,
    // updated each frame; the glb's UVs and triangles), its HARDWARE (the fittings) left skinned: meshes the hose glb's,
    // x its extras (vertex_offsets). Returns [{ mesh, role }]
    const out = [];
    for (const m of meshes) {
        const nm = m.material?.name || '';
        const role = /sleeve/.test(nm) ? 'sleeve' : /pads/.test(nm) ? 'pads' : null;
        if (!role) continue;
        const g0 = m.geometry, g = new THREE.BufferGeometry();
        const off = role === 'sleeve' ? x.vertex_offsets.sleeve : x.vertex_offsets.pads;
        const n = role === 'sleeve' ? cable.sleevePos.length / 3 : cable.padPos.length / 3;
        const dyn = (a, k) => new THREE.BufferAttribute(a, k).setUsage(THREE.DynamicDrawUsage);
        g.setAttribute('position', dyn(role === 'sleeve' ? cable.sleevePos : cable.padPos, 3));
        g.setAttribute('normal', dyn(role === 'sleeve' ? cable.sleeveNrm : cable.padNrm, 3));
        g.setAttribute('tangent', dyn(role === 'sleeve' ? cable.sleeveTan : cable.padTan, 4));
        g.setAttribute('uv', new THREE.BufferAttribute(g0.attributes.uv.array.slice(2 * off, 2 * (off + n)), 2));
        const idx = g0.index.array, ix = new Uint32Array(idx.length);
        for (let i = 0; i < idx.length; i++) ix[i] = idx[i] - off;
        g.setIndex(new THREE.BufferAttribute(ix, 1));
        const mesh = new THREE.Mesh(g, m.material);
        mesh.name = m.name + '_cable';
        out.push({ mesh, role, src: m });
    }
    return out;
}

async function mountCyborgParts(api, parts, opts, U) {
    const { group, bones, sockets, gltf } = api;
    const cut = gltf.parser.json.meshes?.[0]?.extras?.cyborg_cut || null;
    const prims = primitiveMeshes(gltf, group);
    const out = { parts: [], mounts: {}, cables: [] };
    const asPart = (m, kind) => {
        m.castShadow = true;
        m.receiveShadow = true;
        m.frustumCulled = false;
        m.userData.cyborgPart = kind;
    };
    let mechMaterial = null;
    let nMech = 0;
    const later = [];
    // every primitive's hidden ranges, gathered from every part and dropped together at the end (dropRanges)
    const drops = new Map();
    const drop = (mesh, range) => {
        if (!drops.has(mesh)) drops.set(mesh, []);
        drops.get(mesh).push(range);
    };
    for (const part of parts) {
        const pg = await loadPart(part);
        const meshes = [];
        pg.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
        if (part.kind === 'eye_implant') {
            const sock = sockets[part.socket];
            if (!sock) throw new Error(`[Bestiary] cyborg eye_implant: no ${part.socket} on this creature`);
            for (const m of meshes) {
                m.removeFromParent();
                m.material = cyborgMaterial(m.material, cyborgUniforms(U, opts, m.material));
                asPart(m, part.kind);
                sock.add(m);
            }
            const side = /_R$/.test(part.socket) ? 'eye_R' : 'eye_L';
            if (cut?.eyes?.[side] && prims.octopus_eye) drop(prims.octopus_eye, cut.eyes[side]);
            else console.warn(`[bestiary] eye_implant on ${part.socket}: the glb carries no eye ranges (t13 BESTIARY_CUT)`);
            out.parts.push({ kind: part.kind, socket: part.socket, meshes });
        } else if (part.kind === 'mech_tentacle') {
            const x = pg.userData?.bestiary || {};
            const j = part.chain;
            const chain = [];
            for (let k = 0; ; k++) {
                const b = bones.get(`${j}_${String(k).padStart(2, '0')}`);
                if (!b) break;
                chain.push(b);
            }
            const k0 = parseInt(x.joints[0].slice(4, 6), 10);
            const X = (k) => x.bind_x[k - k0];
            const m = meshes[0];
            const helper = {}, nb = [], inv = [];
            for (const b of m.skeleton.bones) {
                const nm = b.name, k = parseInt(nm.slice(4, 6), 10);
                if (nm.length === 6) {
                    const M = k + 1 < chain.length ? chordBasis(chain[k + 1].position) : new THREE.Matrix4();
                    const B = M.clone().setPosition(new THREE.Vector3().setFromMatrixColumn(M, 0).multiplyScalar(-X(k)));
                    nb.push(chain[k]);
                    inv.push(B);
                } else {
                    const hb = new THREE.Bone();
                    hb.name = `${j}_${nm.slice(4)}`;
                    helper[nm] = hb;
                    nb.push(hb);
                    inv.push(new THREE.Matrix4().makeTranslation(-X(k), 0, 0));
                }
            }
            const helpers = [];
            for (const h of x.helpers) {
                const hb = helper[h.name];
                const onShell = h.parent.length > 6;
                (onShell ? helper[h.parent] : chain[parseInt(h.parent.slice(4, 6), 10)]).add(hb);
                bones.set(hb.name, hb);
                helpers.push({ bone: hb, kind: h.kind, k: h.knuckle, onShell, lc: x.cardan?.crank_lc?.[String(h.knuckle)] ?? 0 });
            }
            m.removeFromParent();
            m.bind(new THREE.Skeleton(nb, inv), new THREE.Matrix4());
            m.material = cyborgMaterial(m.material, cyborgUniforms(U, opts, m.material));
            mechMaterial = m.material;
            asPart(m, part.kind);
            group.add(m);
            // the replaced arm: its distal triangles and suckers hidden, its cut ring and the ring before pinned
            const ca = cut?.arms?.[j];
            // this part's own AO floor (C5d: one uniform triple per mech part, in the parts' order)
            const fl = U.aoFloors?.[nMech++];
            if (ca) {
                if (fl && prims.octopus_suckers && chain.length > 8) {
                    // the AO FLOOR's strip (skinMaterial): in chord 7's frame at the bind, x from the hidden suckers
                    // short of the cut ring (the suckers primitive's cut range, read before any range is dropped) to
                    // the ring (its pinned vertices' mean), within the angle round the oral side they span (+0.1 rad)
                    group.updateMatrixWorld(true);
                    const G7i = new THREE.Matrix4().copy(group.matrixWorld).invert().multiply(chain[7].matrixWorld)
                        .multiply(chordBasis(chain[8].position)).invert();
                    const v = new THREE.Vector3(), pa = prims.octopus_arms.geometry.attributes.position;
                    let xr = 0;
                    for (const i of ca.pin.vertices) xr += v.fromBufferAttribute(pa, i).applyMatrix4(G7i).x;
                    xr /= ca.pin.vertices.length;
                    const sk = prims.octopus_suckers, ps = sk.geometry.attributes.position, ix = sk.geometry.index.array;
                    let x0 = Infinity, cmin = 1.0;
                    for (let i = ca.suckers[0]; i < ca.suckers[0] + ca.suckers[1]; i++) {
                        v.fromBufferAttribute(ps, ix[i]).applyMatrix4(G7i);
                        if (v.x >= xr) continue;
                        x0 = Math.min(x0, v.x);
                        cmin = Math.min(cmin, -v.y / Math.max(Math.hypot(v.y, v.z), 1e-9));
                    }
                    if (x0 < xr) {
                        fl.M.value.copy(G7i);
                        fl.box.value.set(x0 - 0.001, xr, Math.cos(Math.min(Math.acos(cmin) + 0.1, Math.PI)), 0.0015);
                        fl.floor.value = AO_FLOOR;
                    }
                }
                drop(prims.octopus_arms, ca.distal);
                if (prims.octopus_suckers) drop(prims.octopus_suckers, ca.suckers);
                const sk = prims.octopus_arms;
                const bi = sk.skeleton.bones.indexOf(bones.get(ca.pin.joint));
                const si = sk.geometry.attributes.skinIndex, sw = sk.geometry.attributes.skinWeight;
                for (const v of ca.pin.vertices) {
                    si.setXYZW(v, bi, 0, 0, 0);
                    sw.setXYZW(v, 1, 0, 0, 0);
                }
                si.needsUpdate = true;
                sw.needsUpdate = true;
            } else {
                console.warn(`[bestiary] mech_tentacle on ${j}: the glb carries no cut (t13 BESTIARY_CUT): its arm stays`);
            }
            out.mounts[parseInt(j.slice(3), 10)] = { chain: j, table: x.radius_table, cut: x.cut,
                firstCardan: x.cardan?.knuckles?.[0] ?? 16, helpers };
            out.parts.push({ kind: part.kind, chain: j, meshes, helpers: helpers.map((h) => h.bone.name) });
        } else if (part.kind === 'hose' || part.kind === 'feed') {
            // (C3d: the feed's cables and hardware mount as the hose's: ONE cable system, runtime/cyborg_cable.js)
            later.push({ part, meshes, pg });
        } else {
            throw new Error(`[Bestiary] cyborg part kind '${part.kind}': not a part this runtime mounts`);
        }
    }
    for (const [mesh, ranges] of drops) dropRanges(mesh, ranges);
    for (const { part, meshes, pg } of later) {
        for (const m of meshes) {
            const nb = m.skeleton.bones.map((b) => {
                const o = bones.get(b.name);
                if (!o) throw new Error(`[Bestiary] cyborg hose: no bone ${b.name} on this creature`);
                return o;
            });
            const inv = m.skeleton.boneInverses.map((b) => b.clone());
            m.removeFromParent();
            m.bind(new THREE.Skeleton(nb, inv), new THREE.Matrix4());
            const shares = m.material?.userData?.shares;
            // (C3d: a shared material with no tentacle mounted takes its own maps under cyborgMaterial, as the parts do)
            m.material = shares ? (mechMaterial || cyborgMaterial(m.material, cyborgUniforms(U, opts, m.material)))
                : cyborgMaterial(m.material, cyborgUniforms(U, opts, m.material));
            asPart(m, part.kind);
        }
        // C5d: a hose glb carrying the CABLE's data (forge/cyborg_cable.py) is re-made every frame on the rendered skin
        // (runtime/cyborg_cable.js): its sleeve and pads plain meshes the cable drives, its fittings skinned; an older
        // hose glb stays skinned as it was
        const x = pg.userData?.bestiary || {};
        const cd = x.cable;
        let shown = meshes;
        if (cd) {
            const skin = prims[cd.skin] || prims.octopus_head;
            const cable = mountCable(cd, skin, bones);
            const cm = cableMeshes(cable, meshes, x);
            shown = meshes.filter((m) => !cm.some((c) => c.src === m)).concat(cm.map((c) => c.mesh));
            for (const c of cm) asPart(c.mesh, part.kind);
            const attrs = cm.flatMap((c) => ['position', 'normal', 'tangent'].map((k) => c.mesh.geometry.attributes[k]));
            out.cables.push({ cable, attrs });
            if (U.padAO) {
                // (C5e: the footprint's dual axes, along the hose in the x slot and across it in the n slot: padFootprint)
                cable.contacts.slice(0, PAD_CONTACTS).forEach((c, k) => {
                    U.padAO[k].c.value.set(c.c.x, c.c.y, c.c.z, c.hl);
                    U.padAO[k].x.value.set(c.gx.x, c.gx.y, c.gx.z, c.hw);
                    U.padAO[k].n.value.set(c.gz.x, c.gz.y, c.gz.z, PAD_AO);
                });
                // (C5f: the cable whose pads fill the slots, for the contact shadow's sweeps each update)
                if (cable.contacts.length) out.padCable = cable;
            }
        }
        for (const m of shown) group.add(m);
        out.parts.push({ kind: part.kind, chain: part.chain, meshes: shown, cable: !!cd });
    }
    return out;
}

export function radialMotion(bones, seed, group, sp, opts = {}, mounts = {}, reach = null, chains = null) {
    // REST POSE (anatomy review r4: the bind pose plus a sway read as an eight-spoke star). A resting octopus settles low
    // on its web with the mantle tilted back, its arms lying in curves on the ground, the distal parts coiling. Every
    // frame each arm's resting PATH is solved on the ground: a heading from the crown, a wandering curvature, a distal
    // spiral whose curvature rises toward the tip, and a height profile that drapes from the crown down to contact
    // (the arm's centreline one local radius above the ground; C5c: its true reach, fleshReach). Its chain is then AIMED
    // along that path at the bind segment lengths. The life motion is the same path's parameters moving (the coils curl
    // and uncurl, the tips explore), so the proximal arms stay planted.
    // C5d (the lead's call 1): the ROOT's reach a support function of each section (fleshSupport): the drape anchored on
    // the flesh line it blends into at joint 1 and scaled so joint 1 lies AT the crown's height (no root rises above
    // the crown), and within the drape every segment's section held on the sand at the pitch it takes (contactPitch: its
    // lowest point along world down no lower than the ground less GROUND_PRESS plus the drape there)
    // STAGE 2B (patches/landing2b_tent.md): that drape times P.tent, 0 by default: joint 1 rests on its flesh line and
    // the root falls to it from the crown (a tent near the crown: no root rises above the crown, none sinks the web)
    const body = sp.body || {};
    const P = {
        lower: opts.lower ?? 0.020,               // the crown settles this far onto its web (bind: a tent of arms)
        tent: opts.tent ?? 0.0,                   // the share of the crown's height over joint 1's flesh line that
                                                  // joint 1 keeps (1: C5d's, joint 1 at the crown's height)
                                                  // STAGE 2B (patches/landing2b_tent.md): lower 0.040 -> 0.020 and
                                                  // tent 1 -> 0. The web near the crown is ~43 % the body's (its skin
                                                  // weights), so the crown's 40 mm settle sank it into a valley 18-22
                                                  // mm under the margins, which a sand-level camera looked into (Skye's
                                                  // frame); CROWN_STUDY §5: "a tent near the crown ... no step between
                                                  // web and arm root". Now the root falls from the crown to joint 1 on
                                                  // its flesh line, the arms rest on the sand from there, the valley
                                                  // is 4-7 mm (forge/cyborg_octopus.py REST_LOWER / REST_TENT: the same)
        mantlePitch: opts.mantlePitch ?? 0.0,     // radians, about the mantle's lateral axis (+ toward its dorsal side):
                                                  // the v4 bind pose already lies the mantle back as resting animals do
                                                  // (r4's upright mantle needed 0.45)
        groundY: opts.groundY ?? 0.0,
        r0: body.armR0 ?? 0.026, rTip: body.armTipR ?? 0.0011,
        // CROSSBREED M2, a grafted LEG's solver (solveLeg): the time its stepping starts (s; null: it rests), the step
        // period (s); the HIP joint (the soft arm before it lies on the plain arm's resting path), the share of the femur
        // its rise comes in over, the ankle's flex range about the bind (rad: the beetle's tibio-tarsal flex,
        // BEETLE_PLAN §6.3: -20 / +45 deg), the tarsomeres' share of the ankle's flex. (M2c, the lead's call 2: the stag
        // beetle's fore leg is a DIGGING leg, posed as the limb this octopus would use it as) the READY pose at rest,
        // raised clear of the sand: the femur's rise (its steepest chord) and curl, the knee's flex (+ folds the tibia
        // toward the oral side), the ankle's flex (rad), each swaying slowly about it; the claws' tip at least
        // legReadyClear over the sand (m: the gate's bar). A STEP: the foot swings from the ready pose to over a target on
        // the sand, comes straight down onto it, STANDS (the claws' tip and the foot's pitch held where it touched down,
        // while the soft femur's curl levers through legDig (rad): a dig), lifts straight up and swings back to the
        // ready pose. The
        // TOUCHDOWN keyframe per step: the femur's rise legTouchRise (+- legTouchSpread, drawn per step: the reach), the
        // knee's flex legTouchKnee, the ankle's flex legStandTrim (the tarsus hanging down to the sand, the claws into
        // it), the coxa's yaw drawn within +- legYaw; its curl solved so the claws' tip stands on the sand. legHover the
        // straight descent's and lift's height (m), legRiseMax the femur's rise bound and legKnee the knee's flex range
        // in a solve (rad)
        legStepAt: opts.legStepAt ?? null, legPeriod: opts.legPeriod ?? 4.0, legHip: opts.legHip ?? 3,
        // ((M2c) the TARSUS SHARES the foot's flex: the ankle alone at 0.5 rad opened the tibia's apex on its flexor side
        // past the ankle sleeve's cover (the sleeve gate: 23 of its 48 triangles out in every stance, read as an orange
        // chip), so the stance's ankle is 0.25 (legStandTrim) and the tarsomeres take the rest. legCurl is PER TARSAL
        // JOINT (t1 -> t2, t2 -> t3, t3 -> t4, t4 -> t5; a number: every joint alike), each a share of the ankle's flex.
        // Each joint's clearance, as G-R8 counts it, over the skinned motion (m2c_tools/m2c_pen.py on pose dumps; the
        // child turned rigidly about its hinge, m2c_flex.py, missed what the skin's blend across each joint adds):
        // t1 -> t2 and t4 -> t5 press from +3 deg (0.35 at all four: G-R8's 4 vertices at rest, 7 stepping), t3 -> t4
        // from +3.5 (0.5 of the ankle: 1 vertex at rest), t2 -> t3 not through +10.6 (0.8 of the ankle: 4 vertices at
        // +13.2); and t2 -> t3's SLEEVE pokes out of both shells past +8.2 deg (m2c_tools/m2c_sleeves.py posed: 0.65 of
        // the ankle, 4 triangles at a touchdown; 0.5, none). So the curl lives in t2 -> t3 (0.5 of the ankle's flex, up to
        // 8.3 deg in a stance) and a little in t3 -> t4 (0.15, up to 2.5 deg), the first and last joints held: the foot's
        // whole flex at a touchdown 0.41 rad)
        legRiseSpan: opts.legRiseSpan ?? 0.45, legTrim: opts.legTrim ?? [-0.349, 0.785],
        legCurl: opts.legCurl ?? [0.0, 0.5, 0.15, 0.0],
        // (the ready angles chosen on m2c_pose_scan.mjs's grid and LOOKED at, m2c_runs/probe/readyleg_*: the arm rises off
        // the sand and arches over, the tibia angles down-forward (~20 deg) with its toothed apex ~70 mm over the sand, the
        // tarsus cocked up, the claws hooked forward ~110 mm up: a limb held ready, not a rod laid down. The knee's flex
        // stays within legKnee: the collar's crest rides arm0_08 by ~15 %, so each 0.1 rad of knee moves the lip ~0.3 mm
        // off the shell (G-R8's bar 0.5 mm), and 0.4 rad turned the membrane over; the ankle's flex stays positive (a
        // dorsiflexed ankle, -0.1, pushed tarsus 1 into the tibia's apex: G-R8). (M2d, the lead's call 1: at rise 1.3 the
        // femur's steepest chord stood 65-68 deg and in 3-4 of the turntable's 9 views it read as a POLE carrying the leg)
        // the rise LOWERED to 0.85, the curl to 1.30 with it, so the leg keeps its ready shape lower: the femur's steepest
        // chord 42-45 deg (M2b's old 45 deg bound), the knee 104-120 mm over the sand (M2c 137-148), the tibia ~18 deg
        // down-forward (M2c ~24), the tarsus still cocked, the claws' tip 92-150 mm up (the gate's 40 mm kept with room).
        // Over the turntable's 360 frames the femur stands upright in 35 (M2c 63; m2d/tools/pole_scan.mjs), all within
        // ~20 deg of the one view along the leg's own plane, where any planar limb reads as a line (a side curl of the
        // femur only moved that view round the orbit: tried, m2d/look/r1/tt_side*_9.png))
        legReadyRise: opts.legReadyRise ?? 0.85, legReadyCurl: opts.legReadyCurl ?? 1.30,
        legReadyKnee: opts.legReadyKnee ?? 0.10, legReadyTrim: opts.legReadyTrim ?? 0.12,
        legReadyClear: opts.legReadyClear ?? 0.04,
        // (the touchdown keyframe on the same grid: the tarsus flicks down and forward, the claws hooked into the sand at
        // ~-70 deg, the tibia sloping toward it ~17 deg with the ankle ~80 mm up; (the M2c restart) the flex shared with
        // the tarsomeres, legCurl above: the ankle 0.25 rad)
        legTouchRise: opts.legTouchRise ?? 1.12, legTouchSpread: opts.legTouchSpread ?? 0.06,
        legTouchKnee: opts.legTouchKnee ?? 0.0, legStandTrim: opts.legStandTrim ?? 0.25, legDig: opts.legDig ?? -0.08,
        legYaw: opts.legYaw ?? 0.12, legHover: opts.legHover ?? 0.025, legRiseMax: opts.legRiseMax ?? 1.45,
        legKnee: opts.legKnee ?? [-0.15, 0.15],
    };
    const v3 = () => new THREE.Vector3(), q4 = () => new THREE.Quaternion();
    const bodyBone = bones.get('body');
    if (bodyBone) bodyBone.position.y -= P.lower;
    group.updateMatrixWorld(true);
    const UP = new THREE.Vector3(0, 1, 0);
    const arms = [];
    // CROSSBREED M1: the chains from the glb's records (armChains: a grafted arm's part joints posed as its own; none
    // given, the name scan)
    const chainList = chains || armChains(null, bones);
    for (let j = 0; j < chainList.length; j++) {
        const chain = chainList[j].bones.map((b) => ({ b, rest: b.quaternion.clone() }));
        if (!chain.length) break;
        // bind data in the creature's space: joint positions, segment lengths, the chord to the next joint in each
        // joint's own frame (so the child lands exactly on the path), the arm's azimuth
        const inv = new THREE.Matrix4().copy(group.matrixWorld).invert();
        const pos = chain.map((c) => c.b.getWorldPosition(v3()).applyMatrix4(inv));
        const len = [], chordQ = [];
        for (let k = 0; k < chain.length - 1; k++) {
            len.push(pos[k + 1].distanceTo(pos[k]));
            const loc = chain[k + 1].b.position.clone().normalize();
            const yref = new THREE.Vector3(0, 1, 0).addScaledVector(loc, -loc.y).normalize();
            const m = new THREE.Matrix4().makeBasis(loc, yref, v3().crossVectors(loc, yref));
            chordQ.push(q4().setFromRotationMatrix(m).invert());
        }
        const total = len.reduce((a, b) => a + b, 0) / 0.985;
        const d0 = v3().subVectors(pos[1], pos[0]);
        const h = (i) => hash01(j * 31 + i, seed);
        arms.push({
            chain, len, chordQ, total, d0: d0.setY(0).normalize(),
            // seeded per arm (no twinning, AG 00.17): the spacing jitter, a slow wander along the length, the distal
            // spiral (its side, where it starts, how tight it ends), the tips that rise off the ground
            dAz: (h(1) - 0.5) * 0.45,
            wanderK: (h(2) - 0.5) * 2.0 * 2.2, wanderL: 0.30 + 0.30 * h(3), wanderPh: h(4) * 6.2832,
            coilSide: h(5) < 0.5 ? -1 : 1, coilS0: 0.50 + 0.22 * h(6), coilG: 0.28 + 0.30 * h(7),
            tipLift: h(8) < 0.35 ? 0.015 + 0.03 * h(9) : 0.0, drape: 0.10 + 0.08 * h(10),
            ph0: h(11) * 6.2832, ph1: h(12) * 6.2832,
            reach: reach?.[j] || null,
            radius: chainList[j].radius,          // CROSSBREED M1: the record's per-joint radius (decision 4)
        });
        // CROSSBREED M2: a grafted LEG (armChains' leg). (M2b, the stance) The soft arm from the crown to the HIP (joint
        // legHip) lies on the PLAIN arm's resting path (solveLeg runs solveArm first, on the native arm's length, the
        // record's native_length: its first chords land where the plain arm's do, so the crown's web between this arm
        // and its neighbours lies as on the plain octopus; the M2 look's pale torn sheet was a femur rising off the
        // crown itself). The FEMUR is the soft arm from the hip to the graft root (its chords legHip .. the graft root's
        // parent), the tibia the knee to the ankle, the tarsus the ankle on to the claws' tip (the chain's tip socket,
        // under the claw bone)
        if (chainList[j].leg) {
            const a = arms[arms.length - 1], lg = chainList[j].leg, nf = lg.first;
            if (lg.nativeLength) a.total = lg.nativeLength / 0.985;
            const tipSock = chain[chain.length - 1].b.children.find((c) => c.name && c.name.startsWith('socket_'));
            // the femur's chords from the hip: the RISE coming in over its first 45 % (U: no kink where it leaves the
            // sand) and the CURL over its distal 70 % (w: the soft arm bends toward its distal end, the way an octopus
            // arm curls; the collar itself stays at rest)
            const ns = nf - 1, kh = Math.min(Math.max(1, Math.round(P.legHip)), ns - 2);
            const Lr = len.slice(kh, ns).reduce((s, x) => s + x, 0);
            const sm = (e0, e1, x) => { const u = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return u * u * (3 - 2 * u); };
            const U = [], w = [];
            let s = 0;
            for (let k = kh; k < ns; k++) {
                const m = (s + 0.5 * len[k]) / Lr;
                U.push(sm(0.0, P.legRiseSpan, m));
                w.push(sm(0.30, 1.0, m));
                s += len[k];
            }
            a.leg = { nf, kh, tip: tipSock || null, U, w, W: w.reduce((acc, x, i) => acc + x * len[kh + i], 0),
                qh: new THREE.Quaternion(), p0: 0.0, h0: 0.0, al: 0.0, th: 0.0, res: 0.0, trim: 0.0,
                // (M2c) the solution's knee, sway and phase; the stance's target (world) while a foot stands; the
                // seeded draws of the step targets
                knee: 0.0, sway: 0.0, phase: 'ready', target: null, hash: (i) => hash01(j * 31 + 977 + i, seed) };
            // (the solver's state per frame, read by the tests through the chain list: never read back as a start)
            Object.defineProperty(lg, 'state', { value: a.leg, enumerable: false, configurable: true });
        }
        // a MOUNTED cyborg part on this arm (mountCyborgParts): its ground line from the part's radius table, its chord
        // frames (M, their transposes and quaternions) for the helper joints' rules
        const mt = mounts?.[j];
        if (mt) {
            const a = arms[arms.length - 1];
            a.H = groundProfile(mt.table, len, P.r0, P.rTip, mt.cut, mt.firstCardan, 3, a.reach);
            a.M = chordQ.map((q) => new THREE.Matrix4().makeRotationFromQuaternion(q.clone().invert()))
                .concat([new THREE.Matrix4()]);
            a.Minv = a.M.map((m) => m.clone().transpose());
            a.qM = a.M.map((m) => q4().setFromRotationMatrix(m));
            a.mount = mt;
        }
    }
    const mantle0 = bones.get('mantle_0'), mantle1 = bones.get('mantle_1'), funnel1 = bones.get('funnel_1');
    const m0Rest = mantle0 ? mantle0.quaternion.clone() : null;
    const eyes = ['eye_L', 'eye_R'].map((n) => bones.get(n)).filter(Boolean)
        .map((b) => ({ b, rest: b.quaternion.clone() }));
    const qa = new THREE.Quaternion(), qb = new THREE.Quaternion(), qp = new THREE.Quaternion(), qg = q4();
    const Z = new THREE.Vector3(0, 0, 1), Y = new THREE.Vector3(0, 1, 0);
    const mBasis = new THREE.Matrix4(), dir = v3(), yv = v3(), zv = v3(), cur = v3();
    const smooth = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
    function solveArm(a, t) {
        const n = a.chain.length, L = a.total;
        const parent = a.chain[0].b.parent;
        parent.updateWorldMatrix(true, false);
        parent.getWorldQuaternion(qp);
        cur.copy(a.chain[0].b.getWorldPosition(v3()));
        const y0 = cur.y;
        // C5d: the drape's crown anchor the flesh line it blends into at joint 1 (its level reach), the drape scaled so
        // joint 1 lies at the crown's height; without the section outlines (no reach measured), r4's 0.92 r0 (C5c)
        const hulls = a.reach?.hulls || null;
        const lvl1 = a.reach && a.reach[1] > 0 ? a.reach[1] - GROUND_PRESS : null;
        const sup = hulls && lvl1 != null;
        const anchor = sup ? lvl1 : 0.92 * P.r0;
        const crownK = sup ? 1.0 - smooth(0.0, a.drape, a.len[0]) : 1.0;
        // the coils curl and uncurl slowly; the tips explore
        const coilMul = 1.0 + 0.10 * Math.sin(6.2832 * 0.06 * t + a.ph0);
        dir.copy(a.d0).applyQuaternion(group.getWorldQuaternion(qg));
        let theta = Math.atan2(dir.x, dir.z) + a.dAz, s = 0.0;
        for (let k = 0; k < n - 1; k++) {
            const sm = s + 0.5 * a.len[k], u = sm / L;
            // curvature (1/m) in the ground plane: the wander, then the spiral rising toward the tip
            let kap = a.wanderK * Math.sin(6.2832 * sm / a.wanderL + a.wanderPh) * (0.3 + 0.7 * smooth(0.05, 0.3, u));
            const rem = Math.max(L - sm, 0.0);
            kap += a.coilSide * coilMul * smooth(a.coilS0, a.coilS0 + 0.12, u) / (0.010 + a.coilG * rem);
            kap += 0.9 * Math.sin(6.2832 * 0.21 * t - 9.0 * u + a.ph1) * smooth(0.75, 1.0, u);
            theta += kap * a.len[k];
            // the height: the drape from the crown to contact, the arm's centreline on its flesh line (its true reach,
            // fleshY) over the ground (a mounted part's arm: its ground profile where it has one)
            const s1 = s + a.len[k], u1 = s1 / L;
            // (where no vertex names the joint, its chain record's radius in place of r4's taper: CROSSBREED M1)
            const rad = a.radius ? a.radius[k + 1] : P.rTip + (P.r0 - P.rTip) * Math.pow(Math.max(1.0 - u1, 0.0), 0.92);
            const hk = a.H && a.H[k + 1] != null ? a.H[k + 1] : null;
            const yg = P.groundY + (hk != null ? hk : fleshY(a.reach, k + 1, rad));
            const drape = (y0 - (P.groundY + anchor)) * P.tent * (1.0 - smooth(0.0, a.drape, s1)) / crownK;
            const yT = yg + drape + a.tipLift * smooth(0.82, 1.0, u1) * (1.0 + 0.4 * Math.sin(6.2832 * 0.17 * t + a.ph1));
            let sinPhi = Math.min(1, Math.max(-1, (yT - cur.y) / a.len[k]));
            if (sup && hk == null && hulls[k].length && s < a.drape) {
                // C5d: in the drape, the segment's section never under the sand (contactPitch)
                sinPhi = contactPitch(hulls[k], cur.y, P.groundY - GROUND_PRESS + drape, sinPhi);
            }
            const cosPhi = Math.sqrt(1 - sinPhi * sinPhi);
            dir.set(cosPhi * Math.sin(theta), sinPhi, cosPhi * Math.cos(theta));
            // aim: the joint's chord along dir, its aboral side (local y) up
            yv.copy(UP).addScaledVector(dir, -dir.dot(UP)).normalize();
            zv.crossVectors(dir, yv);
            mBasis.makeBasis(dir, yv, zv);
            qa.setFromRotationMatrix(mBasis).multiply(a.chordQ[k]);        // the bone's world rotation
            const c = a.chain[k];
            c.b.quaternion.copy(qp).invert().multiply(qa);
            qp.copy(qa);
            cur.addScaledVector(dir, a.len[k]);
            s = s1;
        }
        // the last joint follows its parent's heading
        a.chain[n - 1].b.quaternion.copy(a.chain[n - 1].rest);
    }
    // CROSSBREED M2 (patches/crossbreed_m2_bestiary.md): THE ARTHROPOD LEG SOLVER on a grafted leg (BEETLE_PLAN §6.4;
    // CROSSBREED §4.5: the base's gait schedules the step, the slot's anatomy realises it). The soft arm from the crown to
    // the HIP lies on the plain arm's resting path (solveArm, as on the plain octopus: the crown's web lies as the plain
    // octopus's, M2b); from the hip the FEMUR rises: its chords' pitch from the path's toward al (its steepest) over the
    // femur's first legRiseSpan, curling down by th over its distal 70 %, its heading turned from the path's by the
    // coxa's yaw (sway: the leg's plane); the graft root and the knee (the tibia, inside the collar) keep their BIND
    // relation but for the knee's flex about its hinge (+ folds it toward the oral side), so the membrane, not the rigid
    // shell, takes the bend; the TARSUS keeps the beetle's own rest curl and flexes, the ankle by trim and each tarsal
    // joint by its own legCurl share of it, inside the beetle's ranges (§6.3). (M2c, the lead's call 2: M2b laid the leg
    // on the sand and re-solved a foot that slid there every frame, 11 mm/s at rest and 50 mm/s raked through a step.) The
    // stag beetle's fore leg is a DIGGING leg. At REST it is held READY, raised clear of the sand (fixed angles, each
    // swaying slowly: nothing touches the sand). A STEP swings the foot to over a target on the sand, brings it STRAIGHT
    // DOWN, and while it STANDS the claws' tip and the foot's pitch are held exactly where they touched down (legSolve: the
    // rise, the curl, the ankle and the coxa's yaw for the tip's three coordinates and the foot's pitch) as the knee levers
    // through legDig (the dig); then it lifts STRAIGHT UP and swings back to the ready pose. Every frame is solved afresh
    // from fixed starts (the ready angles): the motion stays a pure function of time and seed
    const _u = new THREE.Vector3(), _R = new THREE.Vector3(), _t = new THREE.Vector3();
    function legPose(a, al, th, knee, sway) {
        // the femur's chords from the hip (legHip .. the graft root's parent chord): their pitch from the plain path's at
        // the hip (p0) toward al by U, less the curl (each chord's w(s) th / sum(w len)); their heading from the path's
        // (h0) by the coxa's yaw, by U; then the graft root and the knee from their bind
        const g = a.leg, ns = g.nf - 1;
        qp.copy(g.qh);
        let cu = 0.0;
        for (let i = 0, k = g.kh; k < ns; i++, k++) {
            const dk = g.w[i] * a.len[k] * th / g.W;
            cu += 0.5 * dk;
            const ps = g.p0 + (al - g.p0) * g.U[i] - cu, hd = g.h0 + sway * g.U[i];
            cu += 0.5 * dk;
            dir.set(Math.cos(ps) * Math.sin(hd), Math.sin(ps), Math.cos(ps) * Math.cos(hd));
            yv.copy(UP).addScaledVector(dir, -dir.dot(UP)).normalize();
            zv.crossVectors(dir, yv);
            mBasis.makeBasis(dir, yv, zv);
            qa.setFromRotationMatrix(mBasis).multiply(a.chordQ[k]);
            a.chain[k].b.quaternion.copy(qp).invert().multiply(qa);
            qp.copy(qa);
        }
        a.chain[ns].b.quaternion.copy(a.chain[ns].rest);
        a.chain[g.nf].b.quaternion.copy(a.chain[g.nf].rest).multiply(qb.setFromAxisAngle(Z, knee));
        for (let k = g.nf + 1; k < a.chain.length; k++) a.chain[k].b.quaternion.copy(a.chain[k].rest);
        const p = a.chain[g.nf + 1].b.getWorldPosition(_t).sub(_R);
        return [p.dot(_u), p.dot(UP)];
    }
    // THE WHOLE LEG at v = (rise al, curl th, knee flex, coxa yaw sway, ankle flex trim): legPose's femur and knee, then
    // the ankle flexed by trim about its hinge (local z: + folds it anatomically) and each tarsal joint by its legCurl share;
    // returns the claws' tip (world: the chain's tip socket), the foot's pitch (the claw joint -> the tip, rad) and the
    // ankle's height
    const _tp = new THREE.Vector3(), _cj = new THREE.Vector3();
    function legState(a, v) {
        const g = a.leg, nf = g.nf;
        _u.set(Math.sin(g.h0 + v[3]), 0, Math.cos(g.h0 + v[3]));
        legPose(a, v[0], v[1], v[2], v[3]);
        const ankle = a.chain[nf + 1], nt = Math.max(0, a.chain.length - nf - 3);
        ankle.b.quaternion.copy(ankle.rest).multiply(qb.setFromAxisAngle(Z, v[4]));
        for (let k = nf + 2; k < nf + 2 + nt; k++) {
            const wc = Array.isArray(P.legCurl) ? (P.legCurl[k - nf - 2] ?? 0.0) : P.legCurl;
            a.chain[k].b.quaternion.copy(a.chain[k].rest).multiply(qb.setFromAxisAngle(Z, v[4] * wc));
        }
        const last = a.chain[a.chain.length - 1].b;
        const tip = (g.tip || last).getWorldPosition(_tp);
        const d = _t.subVectors(tip, last.getWorldPosition(_cj));
        return [tip.x, tip.y, tip.z, Math.asin(Math.min(1, Math.max(-1, d.y / Math.max(d.length(), 1e-9)))),
            ankle.b.getWorldPosition(_cj).y];
    }
    // LEVENBERG-MARQUARDT on the FREE entries of v (the rise, the knee, the ankle and the coxa's yaw; the curl stays as
    // given: the rise and the curl move the femur's end almost alike, and with both free the knee railed on its bound)
    // for the claws' tip at tgt (three coordinates, m) and the foot's pitch phi (weighed 0.1 m per rad); each variable
    // projected into its bounds; from v0 to convergence (a step that does not lower the residual raises the damping).
    // Leaves the leg at the best v; returns [v, |r|^2]
    const FREE = [0, 2, 4, 3];
    function legSolve(a, v0, tgt, phi) {
        const LO = [-0.2, 0.0, P.legKnee[0], -0.6, P.legTrim[0]], HI = [P.legRiseMax, 3.2, P.legKnee[1], 0.6, P.legTrim[1]];
        const lo = FREE.map((i) => LO[i]), hi = FREE.map((i) => HI[i]);
        const full = (xx) => { const v = v0.slice(); FREE.forEach((i, j) => { v[i] = xx[j]; }); return v; };
        const resid = (xx) => {
            const s = legState(a, full(xx));
            return [s[0] - tgt.x, s[1] - tgt.y, s[2] - tgt.z, 0.1 * (s[3] - phi)];
        };
        let x = FREE.map((i, j) => Math.min(hi[j], Math.max(lo[j], v0[i])));
        let r = resid(x), n2 = r.reduce((s, v) => s + v * v, 0), mu = 1e-6;
        for (let it = 0; it < 60 && n2 > 1e-14; it++) {
            const J = [];                                       // J[j][i] = d r_i / d x_j
            for (let j = 0; j < 4; j++) {
                const xh = x.slice();
                xh[j] += 1e-5;
                const rh = resid(xh);
                J.push(rh.map((v, i) => (v - r[i]) / 1e-5));
            }
            const A = [0, 1, 2, 3].map((p) => [0, 1, 2, 3].map((q) => J[p].reduce((s, v, i) => s + v * J[q][i], 0)));
            const b = [0, 1, 2, 3].map((p) => -J[p].reduce((s, v, i) => s + v * r[i], 0));
            for (let p = 0; p < 4; p++) A[p][p] += mu * (1.0 + A[p][p]);
            for (let p = 0; p < 4; p++) {                       // Gaussian elimination with partial pivoting
                let m = p;
                for (let q = p + 1; q < 4; q++) if (Math.abs(A[q][p]) > Math.abs(A[m][p])) m = q;
                [A[p], A[m]] = [A[m], A[p]];
                [b[p], b[m]] = [b[m], b[p]];
                for (let q = p + 1; q < 4; q++) {
                    const f = A[q][p] / A[p][p];
                    for (let c = p; c < 4; c++) A[q][c] -= f * A[p][c];
                    b[q] -= f * b[p];
                }
            }
            const dx = [0, 0, 0, 0];
            for (let p = 3; p >= 0; p--) {
                let s = b[p];
                for (let c = p + 1; c < 4; c++) s -= A[p][c] * dx[c];
                dx[p] = s / A[p][p];
            }
            const sc = Math.min(1, 0.3 / Math.max(...dx.map(Math.abs), 1e-12));
            const x1 = x.map((v, i) => Math.min(hi[i], Math.max(lo[i], v + sc * dx[i])));
            const r1 = resid(x1), n21 = r1.reduce((s, v) => s + v * v, 0);
            if (n21 < n2) {
                x = x1;
                r = r1;
                n2 = n21;
                mu = Math.max(mu / 3, 1e-12);
            } else {
                mu *= 10;
                if (mu > 1e4) break;
            }
        }
        const v = full(x);
        legState(a, v);
        return [v, n2];
    }
    // THE READY POSE at time t (raised, every angle swaying slowly about its own: nothing touches the sand): v
    const readyV = (a, t) => [P.legReadyRise + 0.035 * Math.sin(6.2832 * 0.05 * t + a.ph0),
        P.legReadyCurl + 0.06 * Math.sin(6.2832 * 0.06 * t + a.ph1 + 1.0),
        P.legReadyKnee + 0.03 * Math.sin(6.2832 * 0.09 * t + a.ph0 + 2.0), 0.05 * Math.sin(6.2832 * 0.07 * t + a.ph1),
        P.legReadyTrim + 0.04 * Math.sin(6.2832 * 0.11 * t + a.ph1 + 3.0)];
    // step k's TOUCHDOWN keyframe: the rise (its reach drawn per step), the knee, the ankle, the coxa's yaw (drawn); the
    // curl bisected until the claws' tip stands at the contact height (more curl lowers it over the range). Returns
    // { v, tip, phi }: exactly reachable by construction, so a standing foot is held, never chased
    function touchdown(a, k) {
        const g = a.leg;
        const al = P.legTouchRise + (g.hash(2 * k) - 0.5) * 2.0 * P.legTouchSpread;
        const sw = (g.hash(2 * k + 1) - 0.5) * 2.0 * P.legYaw, yC = P.groundY + 0.0015;
        let lo = 0.0, hi = 3.2;
        for (let it = 0; it < 44; it++) {
            const mid = 0.5 * (lo + hi);
            if (legState(a, [al, mid, P.legTouchKnee, sw, P.legStandTrim])[1] > yC) lo = mid; else hi = mid;
        }
        const v = [al, 0.5 * (lo + hi), P.legTouchKnee, sw, P.legStandTrim], s = legState(a, v);
        return { v, tip: { x: s[0], y: s[1], z: s[2] }, phi: s[3] };
    }
    const mixv = (A, B, s) => A.map((v, i) => v + (B[i] - v) * s);
    function solveLeg(a, t) {
        const g = a.leg;
        // the plain arm's resting path: the chords before the hip keep it (the femur's are re-laid below); the hip, the
        // world rotation of its parent chord, and that chord's pitch and heading (the femur leaves the sand along it)
        solveArm(a, t);
        a.chain[g.kh - 1].b.getWorldQuaternion(g.qh);
        const pPrev = a.chain[g.kh - 1].b.getWorldPosition(v3());
        _R.copy(a.chain[g.kh].b.getWorldPosition(v3()));
        dir.subVectors(_R, pPrev).normalize();
        g.p0 = Math.asin(Math.min(1, Math.max(-1, dir.y)));
        g.h0 = Math.atan2(dir.x, dir.z);
        const vR = readyV(a, t);
        let v = vR, res = 0.0;
        g.phase = 'ready';
        g.target = null;
        if (P.legStepAt != null && t >= P.legStepAt) {
            // THE STEP CYCLE from legStepAt (its phase 0 IS the ready pose: no blend), step k's TOUCHDOWN keyframe T and
            // its HOVER (the claws' tip legHover straight over T's, solved from T): out [0, 0.25) the angles from the
            // ready pose's to the hover's (the ankle flexing the cocked tarsus down to legStandTrim: a paw's strike);
            // down [0.25, 0.33) the tip STRAIGHT DOWN onto T's; STAND [0.33, 0.65) the tip and the foot's pitch HELD at
            // T's while the soft femur's curl levers through legDig (the dig: the arm hauls on the planted claws, the
            // tibia and the knee rock over them, the ankle taking it up); up [0.65, 0.73) straight up; back [0.73, 1)
            // the angles from the hover's to the ready pose's
            const u = (t - P.legStepAt) / P.legPeriod, k = Math.floor(u), ph = u - k;
            const T = touchdown(a, k);
            const vH = legSolve(a, T.v, { x: T.tip.x, y: T.tip.y + P.legHover, z: T.tip.z }, T.phi)[0];
            const line = (h) => ({ x: T.tip.x, y: T.tip.y + h, z: T.tip.z });
            if (ph < 0.25) {
                v = mixv(vR, vH, smooth(0, 1, ph / 0.25));
                g.phase = 'out';
            } else if (ph < 0.33) {
                const sol = legSolve(a, vH, line(P.legHover * (1.0 - smooth(0, 1, (ph - 0.25) / 0.08))), T.phi);
                v = sol[0];
                res = Math.sqrt(sol[1]);
                g.phase = 'down';
            } else if (ph < 0.65) {
                const v0 = T.v.slice();
                v0[1] += P.legDig * Math.sin(Math.PI * (ph - 0.33) / 0.32);
                const sol = legSolve(a, v0, T.tip, T.phi);
                v = sol[0];
                res = Math.sqrt(sol[1]);
                g.phase = 'stand';
                g.target = T.tip;
            } else if (ph < 0.73) {
                const sol = legSolve(a, T.v, line(P.legHover * smooth(0, 1, (ph - 0.65) / 0.08)), T.phi);
                v = sol[0];
                res = Math.sqrt(sol[1]);
                g.phase = 'up';
            } else {
                v = mixv(vH, vR, smooth(0, 1, (ph - 0.73) / 0.27));
                g.phase = 'back';
            }
        }
        legState(a, v);
        g.al = v[0];                           // (the solution, for the tests: never read back as a start)
        g.th = v[1];
        g.knee = v[2];
        g.sway = v[3];
        g.trim = v[4];
        g.res = res;
    }
    return function (t) {
        // the mantle: tilted back, and VENTILATING (a radial pulse ~0.4 Hz; the funnel's tip pulses in counter-phase)
        if (mantle0) mantle0.quaternion.copy(m0Rest).multiply(qa.setFromAxisAngle(Z, P.mantlePitch));
        const vent = Math.sin(6.2832 * 0.4 * t);
        if (mantle1) mantle1.scale.set(1.0, 1.0 + 0.035 * vent, 1.0 + 0.035 * vent);
        if (funnel1) funnel1.scale.set(1.0, 1.0 - 0.06 * vent, 1.0 - 0.06 * vent);
        for (const a of arms) {
            if (a.leg) solveLeg(a, t);          // CROSSBREED M2: a grafted leg's own anatomy solver
            else solveArm(a, t);
            if (a.mount) poseHelpers(a);
        }
        // saccades: hold a fixation, jump fast to the next (both eyes together, seeded schedule)
        const seg = Math.floor(t / 1.7), f = t / 1.7 - seg;
        const pick = (s, o) => (hash01(s * 13 + o, seed) - 0.5);
        const w = Math.min(1, f / 0.04);                         // ~70 ms saccade
        const yaw = (pick(seg - 1, 1) + (pick(seg, 1) - pick(seg - 1, 1)) * w) * 0.35;
        const pitch = (pick(seg - 1, 2) + (pick(seg, 2) - pick(seg - 1, 2)) * w) * 0.18;
        for (const e of eyes) {
            e.b.quaternion.copy(e.rest).multiply(qa.setFromAxisAngle(Y, yaw)).multiply(qb.setFromAxisAngle(Z, pitch));
        }
    };
}

// (A1) THE HEXAPOD GAIT moved to runtime/locomotion.js (hexapodMotion: the gait scheduler's first case, the tarsus solver, the
// beetle's life and pistons; its header there)

export async function create(opts = {}) {
    // (B1) THE HUMAN on the VRM path (runtime/human.js: the controller's walk, the face driver, the talk visemes; the body glb by
    // sex, outfit and hand, the hair a coat on its bones); opts.vrm false (or motion 'limbed' / 'none') keeps A1's limbed biped on
    // the plain glb below (the solver's case). Loaded only when asked: a scene without a human never reads human.js
    if (opts.species === 'human' && opts.vrm !== false && opts.motion !== 'limbed' && opts.motion !== 'none') {
        const { createHuman } = await import('./human.js');
        return await createHuman(opts);
    }
    // (A1) a known species by name (its row: where its glb lives, the gated numbers), or ANY glb by bytes / asset / path with no
    // name: what it is comes from the glb's manifest (species.js manifestOf)
    const own = !opts.species && (opts.bytes || opts.path || opts.asset);
    const row = own ? {} : SPECIES[opts.species || 'octopus'];
    if (!row) throw new Error(`[Bestiary] unknown species '${opts.species}' (have: ${Object.keys(SPECIES).join(', ')})`);
    // (B11) a VARIANT built on the species (the stag beetle's crystal, ice, cyborg, cyborg_crystal): its own glb, the same rig
    const vr = opts.variant ? row.variants?.[opts.variant] : null;
    if (opts.variant && !vr) {
        throw new Error(`[Bestiary] ${opts.species} has no variant '${opts.variant}' (have: ${Object.keys(row.variants || {}).join(', ')})`);
    }
    if (vr?.opts) opts = { ...vr.opts, ...opts };
    let bytes = opts.bytes || globalThis.ASSETS?.[opts.asset || (vr ? vr.asset : row.asset)];
    // (A2) a glb read from a path: its bytes read once and its TEXTURES SHARED by every creature made from it (gltf_cache.js: a
    // crowd of one glb decodes and uploads them once); bytes a caller passes or ASSETS hold parse as they did
    const path = bytes ? null : (opts.path || (vr ? vr.path : row.path));
    if (!bytes) bytes = fileBytes(path);
    const gltf = await parseShared(bytes, path);
    // (A1) THE MANIFEST: the glb's record under the row's numbers (for a known species every key the code reads is the row's, as
    // before: motion, materials, lifeScale, gait, body, swim, variants)
    const sp = manifestOf(gltf, row, own ? null : (opts.species || 'octopus'));
    const name = sp.species;
    const group = gltf.scene;
    group.name = `bestiary_${name}`;
    const gx = gltf.userData?.bestiary?.growth || {};          // the growth family's runtime data (t13's extras)
    // CROSSBREED M2b: a crossbreed part's chitin, its iridescent remix FAMILIES (the beetle's own table, ASSEMBLE's part
    // material extras: one source with the beetle's glb) and the one opts.chitin names; explicit fields override it
    const chitinFamilies = (gltf.parser.json.materials || []).find((mt) => mt.extras?.iridophore_families)
        ?.extras.iridophore_families || {};
    const chitinOf = (c = {}) => {
        const f = (c.family && chitinFamilies[c.family]) || {};
        return { ior: c.ior, irid: c.irid ?? f.strength, filmIOR: c.filmIOR ?? f.ior, filmLo: c.filmLo ?? f.thickness?.[0],
            filmHi: c.filmHi ?? f.thickness?.[1], darken: c.darken ?? f.darken, coat: c.coat ?? f.coat };
    };
    const ch0 = chitinOf(opts.chitin);
    const nMechParts = opts.cyborg?.parts?.filter?.((p) => p.kind === 'mech_tentacle').length || 0;
    const U = {
        tint: THREE.uniform(new THREE.Color(opts.tint ?? 0xffffff)),
        dark: THREE.uniform(opts.display?.dark ?? 0.0),
        eyering: THREE.uniform(opts.display?.eyering ?? 0.0),
        spots: THREE.uniform(opts.display?.spots ?? 0.0),
        mottle: THREE.uniform(opts.display?.mottle ?? 0.0),
        darkAll: THREE.uniform(opts.display?.darkAll ?? 0.0),
        wet: THREE.uniform(opts.wet ?? 1.0),
        fuzz: THREE.uniform(opts.fuzz ?? 0.0),            // a velvety remix's rim; wet skin keeps 0
        // passing clouds: strength, wavenumber (rad/m: ~20 cm between fronts), angular speed (rad/s: ~0.15 m/s
        // outward), and the fronts' origin: the mantle's apex point in the bind pose (set from socket_mantle_apex below)
        clouds: THREE.uniform(opts.display?.clouds ?? 0.0),
        cloudK: THREE.uniform(opts.cloudK ?? 32.0),
        cloudW: THREE.uniform(opts.cloudW ?? 4.8),
        cloudApex: THREE.uniform(new THREE.Vector3().fromArray(opts.cloudApex ?? [0.0, 0.13, -0.23])),
        // blue rings: the display's strength, the blue's flash (0 concealed .. 1 exposed), the network's cells per metre
        // (~3 cm), the ring radius in cell units (~7.5 mm rings at low jitter: neighbours stay clear)
        rings: THREE.uniform(opts.display?.rings ?? 0.0),
        ringFlash: THREE.uniform(opts.display?.ringFlash ?? 1.0),
        ringScale: THREE.uniform(opts.ringScale ?? 22.0),
        ringR: THREE.uniform(opts.ringR ?? 0.24),
        // photophores: strength, cells per metre, pulse rate (rad/s), colour (firefly-squid blue)
        glow: THREE.uniform(opts.display?.glow ?? 0.0),
        glowScale: THREE.uniform(opts.glowScale ?? 45.0),
        glowRate: THREE.uniform(opts.glowRate ?? 3.0),
        glowColor: THREE.uniform(new THREE.Color(opts.glowColor ?? 0x3fb8ff)),
        night: THREE.uniform(opts.night ?? 0.0),          // the scene's darkness: the organs glow only in low light
        // STAGE 2B: the ground occlusion (groundOcclusion): its strength (0 none: a creature off the sand) and the
        // sand's world height (the rest pose's: opts.pose.groundY)
        groundAO: THREE.uniform(opts.groundAO ?? 0.85),
        groundY: THREE.uniform(opts.pose?.groundY ?? 0.0),
        // C5c (the lead's decision 5) / C5d (call 4): ONE AO FLOOR PER MECH PART (skinMaterial; set by
        // mountCyborgParts), made before the skin's shaders and only when the parts hold a mech tentacle (a creature
        // without one builds the shaders it did)
        ...(nMechParts ? { aoFloors: Array.from({ length: nMechParts }, () => ({ floor: THREE.uniform(0.0),
            M: THREE.uniform(new THREE.Matrix4()), box: THREE.uniform(new THREE.Vector4(0.0, 0.0, 1.0, 0.001)) })) } : {}),
        // C5d (call 3): the hose pads' contact darkening (padContactAO; set by mountCyborgParts from the cable's
        // contacts), made only when the parts hold a hose
        ...(opts.cyborg?.parts?.some?.((p) => p.kind === 'hose') ? { padAO: Array.from({ length: PAD_CONTACTS }, () => ({
            c: THREE.uniform(new THREE.Vector4(0.0, -10.0, 0.0, 0.0)), x: THREE.uniform(new THREE.Vector4(1.0, 0.0, 0.0, 0.0)),
            n: THREE.uniform(new THREE.Vector4(0.0, 1.0, 0.0, 0.0)),
            // (C5f, the lead's call 9: the contact shadow's sweep toward the sun, the pad's own coordinates (m): set
            // every update from the cable's contactSweeps)
            s: THREE.uniform(new THREE.Vector4(0.0, 0.0, 0.0, 0.0)) })) } : {}),
        // GROWTHS (material_ids_v2.md): the glow's colour (default the family's, linear, from the glb's extras, else its
        // vein family's), intensity, pulse rate (rad/s) and fade (1 = steady), a tint over the growths' albedo, the thin
        // film's IOR and thickness range (nm; the family's from the extras, else three's iridescence default range) and
        // the skin's one film thickness (the range's middle) [I: the intensity, rate, fade and fallbacks chosen]
        growGlow: THREE.uniform(opts.growGlow != null ? new THREE.Color(opts.growGlow)
            : new THREE.Color().setRGB(...(gx.glow || gx.vein_glow || [1.0, 1.0, 1.0]))),
        growGlowI: THREE.uniform(opts.growGlowI ?? 0.6),
        growRate: THREE.uniform(opts.growRate ?? 2.0),
        growFade: THREE.uniform(opts.growFade ?? 0.5),
        growTint: THREE.uniform(new THREE.Color(opts.growTint ?? 0xffffff)),
        filmIOR: THREE.uniform(opts.filmIOR ?? gx.film_ior ?? 2.0),
        // CROSSBREED M2: a crossbreed part's CHITIN (skinMaterial's graft pack, R = 1): its lobe's ior (BEETLE_PLAN §5.1:
        // the melanised cuticle 1.60-1.66), and the jewel-beetle thin film over its iridophore mask, off on the
        // realistic stag beetle (§5.5): (M2b) a family of the beetle's own (chitinOf: strength, the film's ior, its
        // thickness range in nm, the albedo's darkening toward the melanin backing, the coat's thinning); read only by
        // a part with the pack (a plain glb's shaders never name them)
        chitinIOR: THREE.uniform(ch0.ior ?? 1.62),
        chitinIrid: THREE.uniform(ch0.irid ?? 0.0),
        chitinFilmIOR: THREE.uniform(ch0.filmIOR ?? 1.6),
        chitinFilmLo: THREE.uniform(ch0.filmLo ?? 250.0),
        chitinFilmHi: THREE.uniform(ch0.filmHi ?? 650.0),
        chitinDarken: THREE.uniform(ch0.darken ?? 1.0),
        chitinCoat: THREE.uniform(ch0.coat ?? 1.0),
        filmLo: THREE.uniform(opts.filmLo ?? gx.film?.[0] ?? 100.0),
        filmHi: THREE.uniform(opts.filmHi ?? gx.film?.[1] ?? 400.0),
        filmThick: THREE.uniform(opts.filmThick ?? (gx.film ? 0.5 * (gx.film[0] + gx.film[1]) : 250.0)),
        t: THREE.uniform(0.0),
    };
    // CYBORG (CYBORG_PLAN §4.3.2): the organic eye's glow variant, only on request (its node exists only then: a
    // creature without it builds the very eye it did): { side: 'L' | 'R' | 'both', mask: 'pupil' | 'band', intensity };
    // the cyborg glow's uniforms come with it, or with the first cyborg part (cyborgUniforms)
    if (opts.eyeGlow) {
        const g = opts.eyeGlow === true ? {} : opts.eyeGlow;
        const sd = g.side ?? 'both';
        cyborgUniforms(U, opts);
        U.eyeGlow = THREE.uniform(g.intensity ?? 1.5);
        U.eyeGlowBand = THREE.uniform(g.mask === 'band' ? 1.0 : 0.0);
        U.eyeGlowSide = THREE.uniform(new THREE.Vector2(sd === 'R' ? 0.0 : 1.0, sd === 'L' ? 0.0 : 1.0));
    }
    // (B11) THE BEETLE'S MATERIALS (beetle_cuticle.js), made only for a species whose materials are the beetle's (a creature
    // without builds the very shaders it did): the glb's own iridophore families over the defaults, its uniforms (the remix
    // family, the tint; the crystal variant's GROWTH pack shares bestiary's growth uniforms, so api.growth drives the cuticle's
    // crystal feet and the growths mesh alike)
    if (sp.materials === 'beetle') {
        useBeetleFamilies(gltf.userData?.bestiary?.iridophore_families);
        const fam = opts.family ?? 'none';
        if (!BEETLE_FAMILIES[fam]) {
            throw new Error(`[Bestiary] unknown iridophore family '${fam}' (have: ${Object.keys(BEETLE_FAMILIES).join(', ')})`);
        }
        U.beetle = beetleUniforms({ family: fam, tint: opts.tint, growth: gx });
        // (the tint too: api.palette({ tint }) recolours the cuticle's ground as it does the octopus's skin)
        for (const k of ['tint', 'growGlow', 'growGlowI', 'growRate', 'growFade', 'growTint', 'filmIOR', 'filmLo', 'filmHi', 't']) {
            U.beetle[k] = U[k];
        }
    }
    const bones = new Map(), sockets = {};
    group.traverse((o) => {
        if (o.isBone) bones.set(o.name, o);
        if (o.name && o.name.startsWith('socket_')) sockets[o.name] = o;
        // (B11) the beetle's own kinds, by the material's extras key (BEETLE_PLAN §5.5: a name regex would hand beetle_eye_p0
        // the octopus's iris); its growths and cyborg parts fall through to their own builders below
        const bk = o.isMesh ? o.material?.userData?.bestiary : null;
        if (U.beetle && (bk === 'cuticle' || bk === 'compound_eye' || bk === 'membrane')) {
            o.material = beetleMaterial(o.material, U.beetle);
            o.castShadow = true;
            o.receiveShadow = true;
            o.frustumCulled = false;
            return;
        }
        if (o.isMesh && o.material?.userData?.bestiary === 'cyborg') {
            // a CYBORG PART: routed by its extras FIRST (CYBORG_PLAN §6.5; by its name an implant called "eye..." would
            // build the organic eye), the name routing below left as it was
            o.material = cyborgMaterial(o.material, cyborgUniforms(U, opts, o.material));
            o.castShadow = true;
            o.receiveShadow = true;
            o.frustumCulled = false;
            return;
        }
        // a COAT primitive in this glb (its extras say bestiary 'coat'): coat.js builds it below, never the skin's
        if (o.isMesh && o.material?.userData?.bestiary === 'coat') return;
        if (o.isMesh) {
            const src = o.material;
            const nm = src.name || '';
            o.material = /eye/.test(nm) ? eyeMaterial(src, U) : /beak/.test(nm) ? beakMaterial(src)
                : /growth/.test(nm) ? growthMaterial(src, U, opts, o.geometry) : /sucker/.test(nm) ? suckerMaterial(src, U)
                : skinMaterial(src, U);
            o.castShadow = true;
            o.receiveShadow = true;
            o.frustumCulled = false;           // skinned: bind-pose bounds would cull curled arms (AG 00.72)
        }
    });
    // the clouds' origin: the apex socket where the bind pose puts it (before the rest pose moves a bone), in the
    // group's space, which is the skin's bind space (the glb's mesh node carries no transform)
    if (!opts.cloudApex && sockets.socket_mantle_apex) {
        group.updateMatrixWorld(true);
        U.cloudApex.value.copy(group.worldToLocal(sockets.socket_mantle_apex.getWorldPosition(new THREE.Vector3())));
    }
    // CROSSBREED M1: the arm chains from the glb's chain records (armChains; a grafted arm's part joints are its own)
    const chains = sp.motion === 'radial' ? armChains(gltf, bones) : null;
    // C5c: every arm's true reach, read at the bind before any part is mounted (the flesh arms' ground line); C5d: with
    // each joint's section outline (the root's support function)
    const reach = sp.motion === 'radial' ? fleshReach(group, bones, chains) : null;
    if (reach) fleshSupport(group, bones, chains).forEach((h, j) => { if (reach[j]) reach[j].hulls = h; });
    // CYBORG PARTS (mountCyborgParts): joined before the motion reads the bind (only when create() is given parts)
    const cyb = opts.cyborg?.parts?.length ? await mountCyborgParts({ group, bones, sockets, gltf }, opts.cyborg.parts,
        opts, U) : null;
    // C5d: opts.motion 'none' leaves every bone where the caller sets it (a recorded pose, the swim record), the cable
    // still re-made on the skin each update
    // (B11) THE SIZE: a species authored at another scale (the stag beetle at x10) shows at its real size (sp.lifeScale) unless
    // opts.size says 'hero' (the authored scale) or a number; the group carries it (its sockets and accessories with it)
    const size = opts.size === 'hero' ? 1.0 : (typeof opts.size === 'number' ? opts.size : (sp.lifeScale ?? 1.0));
    if (size !== 1.0) group.scale.setScalar(size);
    // (B11) the HEXAPOD gait (hexapodMotion) for a species that walks on six legs; (B10b) standing on its claws by the rig's stand
    // record (extras.bestiary.rig.stand), unless opts.stand gives another or false
    const stand = opts.stand === false ? null : (opts.stand ?? gltf.userData?.bestiary?.rig?.stand ?? null);
    const hex = sp.motion === 'hexapod' && opts.motion !== 'none'
        ? hexapodMotion(bones, opts.seed ?? 1, group, sp, { ...opts, stand }) : null;
    // (A1) THE LIMBED CASE (locomotion.js limbedMotion): a base on leg chains with no motion of its own (a new quad or biped glb; the
    // human's non-VRM path), or any limbed base asked for it (opts.motion 'limbed': the axolotl's rig on the generic scheduler)
    const limbed = opts.motion !== 'none' && (opts.motion === 'limbed' || (sp.motion === 'limbed' && !opts.motion))
        ? limbedMotion(bones, opts.seed ?? 1, group, sp, { ...opts, stand: opts.stand ?? gltf.userData?.bestiary?.stand ?? null },
            sp.chains) : null;
    const loco = hex || limbed;
    const motion = opts.motion === 'none' ? () => {}
        : limbed ? limbed.motion
        : sp.motion === 'radial' ? radialMotion(bones, opts.seed ?? 1, group, sp, opts.pose, cyb?.mounts, reach, chains)
        : hex ? hex.motion : () => {};
    const cables = cyb?.cables || [];
    // C5f (the lead's call 9): the contact shadow's sweep toward the sun. The scene's brightest shadow-casting
    // directional light, looked for from the group's root when the creature joins a scene (the first update can come
    // before it is in one), when its light leaves the scene, and every 60 updates while it has none (a scene without a
    // shadow-casting sun is not walked every frame); its direction toward the light in the group's space (the skin's),
    // each pad's sweep from its clamp frame (the cable's contactSweeps) into its slot's uniform, none without a sun
    let sunLight = null, sunRoot = null, sunWait = 0;
    const sunP = new THREE.Vector3(), sunT = new THREE.Vector3(), sunM = new THREE.Matrix4();
    const sunL = new Float64Array(3), sweeps = new Float64Array(2 * PAD_CONTACTS);
    function padSweeps() {
        let root = group, lr = sunLight;
        while (root.parent) root = root.parent;
        while (lr && lr.parent) lr = lr.parent;
        if (root !== sunRoot || (sunLight && lr !== root) || (!sunLight && ++sunWait >= 60)) {
            sunRoot = root;
            sunWait = 0;
            sunLight = null;
            root.traverse((o) => {
                if (o.isDirectionalLight && o.castShadow && (!sunLight || o.intensity > sunLight.intensity)) sunLight = o;
            });
            if (!sunLight) for (const P of U.padAO) P.s.value.set(0.0, 0.0, 0.0, 0.0);
        }
        if (!sunLight || !cyb.padCable) return;
        // (its world matrices as of now: the renderer refreshes them only when it draws)
        sunLight.updateWorldMatrix(true, false);
        sunLight.target.updateWorldMatrix(true, false);
        sunP.setFromMatrixPosition(sunLight.matrixWorld).sub(sunT.setFromMatrixPosition(sunLight.target.matrixWorld));
        sunP.transformDirection(sunM.copy(group.matrixWorld).invert());
        sunL[0] = sunP.x; sunL[1] = sunP.y; sunL[2] = sunP.z;
        cyb.padCable.contactSweeps(sunL, sweeps);
        const n = Math.min(PAD_CONTACTS, cyb.padCable.contacts.length);
        for (let k = 0; k < n; k++) U.padAO[k].s.value.set(sweeps[2 * k], sweeps[2 * k + 1], 0.0, 0.0);
    }
    // (B10b) THE SHADOW FIT FROM THE JOINTS: every skinned vertex's bind position in its heaviest bone's frame, one box per bone (in
    // that bone's frame), built once at the first fit; a fit then carries each box's 8 corners by its bone's world matrix (~830
    // points for the beetle's 104 bones), never the vertices (B11's precise Box3 skinned all the six primitives' vertices on every
    // call, and the test scene fits every frame). The unskinned meshes under the group (a worn hat, a monocle) count by their
    // geometry's bounding box
    let boneBoxes = null;
    const sbP = new THREE.Vector3(), sbB = new THREE.Box3();
    function shadowBox() {
        if (!boneBoxes) {
            const acc = new Map(), v = new THREE.Vector3();
            group.traverse((o) => {
                if (!o.isSkinnedMesh || !o.skeleton) return;
                const g = o.geometry, pos = g.attributes.position, si = g.attributes.skinIndex, sw = g.attributes.skinWeight;
                if (!pos || !si || !sw) return;
                let used = null;
                if (g.index) {
                    used = new Uint8Array(pos.count);
                    const ia = g.index.array;
                    for (let i = 0; i < ia.length; i++) used[ia[i]] = 1;
                }
                for (let i = 0; i < pos.count; i++) {
                    if (used && !used[i]) continue;
                    let k = 0, wMax = -1;
                    for (let c = 0; c < 4; c++) {
                        const w = sw.getComponent(i, c);
                        if (w > wMax) { wMax = w; k = si.getComponent(i, c); }
                    }
                    const bone = o.skeleton.bones[k];
                    if (!bone) continue;
                    v.fromBufferAttribute(pos, i).applyMatrix4(o.bindMatrix).applyMatrix4(o.skeleton.boneInverses[k]);
                    let b = acc.get(bone);
                    if (!b) acc.set(bone, (b = new THREE.Box3()));
                    b.expandByPoint(v);
                }
            });
            boneBoxes = [...acc];
        }
        const box = new THREE.Box3();
        for (const [bone, b] of boneBoxes) {
            for (let c = 0; c < 8; c++) {
                sbP.set(c & 1 ? b.max.x : b.min.x, c & 2 ? b.max.y : b.min.y, c & 4 ? b.max.z : b.min.z);
                box.expandByPoint(sbP.applyMatrix4(bone.matrixWorld));
            }
        }
        group.traverse((o) => {
            if (!o.isMesh || o.isSkinnedMesh || !o.geometry || o.visible === false) return;
            if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
            box.union(sbB.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld));
        });
        return box;
    }
    const api = {
        group, bones, sockets, uniforms: U, gltf,
        // (B11) the hexapod's controls (metres and radians per second at the creature's size; walkTo a point of its parent),
        // the beetle's remix family (beetle_cuticle.js setFamily: 'none' the realistic base, 'jewel', 'sapphire', 'oilslick',
        // 'gold'), and a directional light's shadow frustum fitted to the creature (its size: a life-size beetle is 6 cm)
        size,
        speed(v) { loco?.controls.speed(v); },
        turn(w) { loco?.controls.turn(w); },
        walkTo(x, z, o) { return loco?.controls.walkTo(x, z, o); },
        gait: loco ? { probe: loco.probe, pistons: hex?.probePistons ?? (() => []), controls: loco.controls, case: loco.case }
            : null,
        manifest: sp,
        family(name, strength) { if (U.beetle) setBeetleFamily(U.beetle, name, strength); },
        fitShadow(light, margin = 1.3) {
            group.updateMatrixWorld(true);
            const box = shadowBox();
            const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.5 * margin;
            const dir = light.position.clone().sub(light.target.position).normalize();
            light.target.position.copy(c);
            light.position.copy(c).addScaledVector(dir, 4 * r);
            light.target.updateMatrixWorld();
            const sc = light.shadow.camera;
            sc.left = -r; sc.right = r; sc.top = r; sc.bottom = -r; sc.near = 0.5 * r; sc.far = 8 * r;
            sc.updateProjectionMatrix();
            // the biases in the frustum's units: a texel's size (the 4096 map's at r) and a fraction of it
            const texel = 2 * r / (light.shadow.mapSize.x || 2048);
            light.shadow.bias = -0.5 * texel / (8 * r);
            light.shadow.normalBias = 1.5 * texel;
            return { centre: c, radius: r, texel };
        },
        chains: chains || [],
        cyborgParts: cyb ? cyb.parts : [],
        cables: cables.map((c) => c.cable),
        update(t) {
            U.t.value = t;
            motion(t);
            if (cables.length) {
                // the hose's cable after the bones (its anchors read the skin as rendered this frame)
                group.updateMatrixWorld(true);
                for (const c of cables) {
                    c.cable.update();
                    for (const a of c.attrs) a.needsUpdate = true;
                }
                if (U.padAO) padSweeps();
            }
            if (api.coatCtl) api.coatCtl.update();      // the coat's wind in the creature's space
        },
        setDisplay(d = {}) {
            for (const k of DISPLAY_KEYS) {
                if (d[k] != null) U[k].value = d[k];
            }
        },
        palette(p = {}) { if (p.tint != null) U.tint.value.set(p.tint); },
        // CROSSBREED M2: a part's chitin: { family (M2b: one of the beetle's, by name; 'none' turns the film off), ior,
        // irid, filmIOR, filmLo, filmHi, darken, coat }
        chitin(c = {}) {
            const v = chitinOf(c);
            for (const [k, u] of [['ior', 'chitinIOR'], ['irid', 'chitinIrid'], ['filmIOR', 'chitinFilmIOR'],
                ['filmLo', 'chitinFilmLo'], ['filmHi', 'chitinFilmHi'], ['darken', 'chitinDarken'], ['coat', 'chitinCoat']]) {
                if (v[k] != null) U[u].value = v[k];
            }
        },
        growth(g = {}) {                    // the growths' glow and tint at runtime: { glow, intensity, rate, fade, tint }
            if (g.glow != null) U.growGlow.value.set(g.glow);
            if (g.tint != null) U.growTint.value.set(g.tint);
            for (const [k, u] of [['intensity', 'growGlowI'], ['rate', 'growRate'], ['fade', 'growFade']]) {
                if (g[k] != null) U[u].value = g[k];
            }
        },
        cyborg(c = {}) {                    // the cyborg glow: { glow, intensity, rate, pulse, tint, accent, eye, eyeBand }
            if (!U.cybGlow) return;         // (no cyborg part and no organic glow: nothing to drive)
            if (Array.isArray(c.glow)) U.cybGlow.value.setRGB(c.glow[0], c.glow[1], c.glow[2]);
            else if (c.glow != null) U.cybGlow.value.set(c.glow);
            if (c.tint != null) U.cybTint.value.set(c.tint);
            if (c.accent != null) U.cybAccent.value.set(c.accent);
            for (const [k, u] of [['intensity', 'cybGlowI'], ['rate', 'cybRate'], ['pulse', 'cybPulse'],
                ['eye', 'eyeGlow'], ['eyeBand', 'eyeGlowBand']]) {
                if (c[k] != null && U[u]) U[u].value = c[k];
            }
        },
    };
    api.wear = (acc, o = {}) => wear(api, acc, o);
    // (AX12) A SALAMANDER (the axolotl: runtime/axolotl.js): its own skin and eye in place of the routing's above, its size,
    // its motion and controls (speed, turn, walkTo, swim, morph, crease), the remix's hook (api.axolotl)
    // ((A1) on the limbed case the salamander's own motion stays off: its drivers read the bones the scheduler posed)
    if (sp.motion === 'salamander') {
        const gait = api.gait;
        Object.assign(api, await axolotlSetup(api, gltf, sp, limbed ? { ...opts, motion: 'none' } : opts));
        if (limbed) api.gait = gait;
    }
    // THE COAT (runtime/coat.js): a coat primitive in this glb, or opts.coat = { bytes | asset | path, look, force,
    // skinLayer, shadows } (a style's coat glb, e.g. work/bestiary/coat/out/octopus_shaggy/coat_octopus_shaggy.glb), on
    // the creature's own bones; the skin's display families reach the fur at its roots. api.coat({ ...look, force })
    // drives it live; api.coatCtl is the controller (meshes, uniforms, lod, rebuild for a remix)
    const coatBytes = opts.coat ? (opts.coat.bytes || globalThis.ASSETS?.[opts.coat.asset]
        || (opts.coat.path ? Deno.readFileSync(opts.coat.path) : null)) : null;
    let coatGltf = coatBytes ? await loadCoat(coatBytes) : null;
    if (!coatGltf) group.traverse((o) => { if (o.isMesh && o.material?.userData?.bestiary === 'coat') coatGltf = gltf; });
    if (coatGltf) {
        // (coat g5) the host's ground term for the cards and shells (coat.js opts.groundOcclusion; opts.coat may override)
        api.coatCtl = await attachCoat(api, coatGltf, { groundOcclusion, ...(opts.coat || {}), auto: false,
            display: { masks: displayMasks, clouds: displayClouds } });
        api.coat = (c = {}) => {
            if (c.force !== undefined) api.coatCtl.force(c.force);
            api.coatCtl.look(c);
        };
    }
    // (A1) THE SPINE (runtime/spine.js): the one contract over the creature's own motion (its update wrapped; nothing runs until a
    // call is made, so a scene that never calls it renders what it did)
    attachSpine(api, { gltf, sp, opts, bones, sockets, group, locomotion: loco });
    if (opts.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(api.update);
    api.update(0);
    return api;
}

// (AX12) THE AXOLOTL's row (its gait, swim and body numbers) moved with the others to runtime/species.js (A1)

// (A2) THE OLD CREATOR'S CALLS (runtime/compat.js): Bestiary.fromMakeCreature(opts) (the async creature with the old api),
// Bestiary.makeCreature(opts) (the drop-in: a group now, the creature loading; Bestiary.ready() awaits every one), the key table
// over every makeCreature option, installCompat() (the global swap, opt-in), and random(seed) (one call: a whole creature)
import { fromMakeCreature, compatMakeCreature, installCompat, ready, random, KEY_TABLE, keyReport } from './compat.js';
import { parseShared, fileBytes } from './gltf_cache.js';

// (A1) register: a new base by name (its glb; the rest from its manifest)
globalThis.Bestiary = { create, accessory, register: registerSpecies, species: [...Object.keys(SPECIES)],
    random, fromMakeCreature, makeCreature: compatMakeCreature, installCompat, ready, keyTable: KEY_TABLE, keyReport };
console.log(`[bestiary] Bestiary ready — species: ${Object.keys(SPECIES).join(', ')}`);
