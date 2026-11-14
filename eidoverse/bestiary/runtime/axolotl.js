// axolotl.js: THE AXOLOTL in the Bestiary's runtime (AX12; work/bestiary/research/AXOLOTL_PLAN.md §9.3, §11's AX12 row;
// the round's log work/bestiary/axolotl/ax12_notes/NOTES.md; the landing doc work/bestiary/patches/axolotl_ax12_runtime.md).
// bestiary.js builds the creature as it builds any species (the glb, its bones and sockets, its api), then hands it here
// (axolotlSetup, from create() for a species whose motion is 'salamander'):
//
//   const axo = await Bestiary.create({ species: 'axolotl', size: 'hero', morph: 'wild' });   // life size by default
//   axo.speed(0.02);              // m/s at the creature's size: the walk (Gamel 2024's lateral sequence) ...
//   axo.swim(true);               // ... or the swim (D'Aout & Aerts' travelling wave), else above swimAbove
//   axo.turn(0.3); axo.walkTo(x, z);   axo.morph('leucistic');   axo.crease(false);
//
//   * THE WET SKIN AND THE EYE (axolotlSkin, axolotlEye): AX7-AX10's composition, moved here from the offline look-dev
//     scene (work/bestiary/engine_test/axolotl_scene.js, whose terms it keeps one for one): the baked base colour is
//     the UNPIGMENTED ground and each MORPH a weight set over the one texture set (plan §5.11):
//       base = mix(ground, melanin, cover x M) x mix(1, xanthophore tint, xantho x X) x (1 - speckles x S), the
//       iridophores a gold body colour and a view-dependent glint x I, the thin tissue's transmitted colour
//       mix(blood / pale membrane, melanin brown, cover) through the thickness (MASKS R); the cover in the ORM's B.
//     The micro-relief (the glands' domes) lives in the specular only (the diffuse reads the baked normal); a scene's
//     own look-dev terms come in through create()'s options and are off by default: opts.water (the underwater IORs
//     relative to water, the lobe scaled away), opts.envDiffuse (the scene's irradiance look-up for the diffuse on the
//     baked normal), opts.studioWall (the studio's dark wall in the reflections).
//   * THE KNEE'S CREASE FADE (the lead's AX10b call: a wrinkle-map style fade): the baked normal map and AO carry the
//     knee's crease relief as the bind's 85 deg knee folds it; straightened (the swim's 155 deg) that relief reads as a
//     crumpled band. The knee_ext corrective's own zone (its morph target's moved vertices, read from the glb at load:
//     |D| over CREASE.d_full is the whole zone, its outer ring 0) is the mask, the corrective's weight the drive: the
//     relief fades to the low's own surface there (normal toward flat, AO toward 1) as the knee opens.
//   * THE RIG'S DRIVERS (the glb's extras.bestiary.driven_leaves / correctives, AX10b): every rule acts on the POSE
//     rotation over the bind, q_pose = q_bind^-1 q_node (the AX10b check: the bind rotations are 50-122 deg, and
//     reading the whole node rotation moves the skin up to 6.4 mm x4): the 12 half-angle helpers slerp(I, driver, 0.5),
//     the 8 twist leaves Rx(-/+ 0.5 x the driver's twist), the 10 correctives' morph weights smoothstep over their ramps
//     (the included angle of the posed joints, or the bone's fold atan2(R10, R00)). The motion computes the pose
//     rotations itself; without it (create({ motion: 'none' }): a scene, a clip or a cross posing the bones) every
//     update reads them back from the nodes, q_bind^-1 q_node (driveFromNodes), and api.axolotl.drive() does so on demand.
//   * THE SALAMANDER MOTION (salamanderMotion), species/axolotl_rig.py's walk_pose / swim_pose / idle_pose / stand_pose
//     ported (forge/families/sprawl.py posed / aim, limb_ik's hinges-kept IK), a pure function of time and the controls'
//     history (one fixed integration grid, cached: a --jump frame equals the one reached step by step):
//       THE STAND (extras.bestiary.stand: the wrists 2 mm and the ankles 3.5 mm life up over the planted digits, the
//       ankle's L) is where every standing pose starts; THE WALK the lateral sequence LH LF RH RF at duty 0.36 / 0.51,
//       each planted hand / foot fixed where it touched down (a turn or a speed change never slides it), swung from
//       plant to plant on an arc, the trunk's few degrees of sway; one settling cycle after a stop (no foot left in the
//       air); THE SWIM the wave A(s) = 0.097 (0.15 + 0.85 s^2) TL along the spine and the tail, lambda 0.60 TL,
//       f = speed / 0.345 TL, the limbs ADPRESSED along the flanks, the gills laid back, the body lifted off the floor;
//       THE IDLES the gill sway (each ramus its own rate, 0.35-0.75 Hz) with a flare every 7 s, the throat's buccal
//       pulse (1 Hz, 9 deg) with the jaw, a slow tail sway, eye drifts.
//   * THE REMIX (remixAxolotl, called by remix.js apply() through api.axolotl.remix): the palette and the element's zone
//     remaps, surface layer and glow rebuilt on the axolotl's OWN skin (remix.js's zone and surface builders, passed
//     in: one source), over the composed pigment; the eye kept.
const THREE = globalThis.THREE;

// ============================================================================================ tables
// THE CREASE FADE: the knee_ext zone's mask is smoothstep(0, d_full, |D|) of the corrective's delta (x4 m: 140 of its
// 143 vertices move over 0.2 mm, its outer ring 0: the zone, its edge one triangle's ramp, work/bestiary/axolotl/ax12/try/
// probe_crease.py); what fades: the normal map's relief toward the low's own normal, the baked AO toward 1
const CREASE = { targets: ['knee_ext'], d_full: 0.00025, ao: 1.0 };
// the micro-relief (axolotl_scene.js MICRO, the AX7b / AX7c checks' values): cells per UV unit, the slope's strength,
// the grain, the fade (cells per pixel), the fins' share, the lobe widening, the crease rounding
const MICRO = { cells: 260.0, strength: 0.15, grain: 0.18, fade: [0.12, 0.45], fin: 0.4, rough: 1.2, round: 0.30 };
// the morphs' colours (axolotl_scene.js: [E] tuned against p13 / p06 wild, p03 leucistic, p08 white albino; the gold
// patches' body colour p15's median, the open membrane p01's backlit fin)
const MELANIN = 0x2b2522, XANTHO = [1.08, 1.10, 0.62], IRID = 0xb9a366, GOLD = 0x6e5204;
const THIN_BLOOD = 0xc9787e, THIN_PALE = 0xe2d2c2, THK_SCALE = 0.65, MEL_PASS = 0.06, THIN_HAND = 0.35;
const BLUSH_THIN_FALLBACK = 0.50;
// the underwater look (axolotl_scene.js WATER: the skin's and the cornea's IORs relative to water; the skin takes no
// lobe there, the cornea a little)
const WATER = { ior_skin: 1.035, ior_eye: 1.032, spec: 0.0, spec_eye: 0.08 };
const DEG = Math.PI / 180;
const X_AX = new THREE.Vector3(1, 0, 0), Y_AX = new THREE.Vector3(0, 1, 0), Z_AX = new THREE.Vector3(0, 0, 1);

function linColor(hex) { return new THREE.Color().setHex(hex, THREE.SRGBColorSpace); }

function hash01(i, seed) {
    // lowbias32 (the forge's hash; bestiary.js's), to [0, 1)
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 0) / 4294967296;
}

// ============================================================================================ the skin and the eye
export function morphValues(morphs, name) {
    const mo = (morphs && morphs[name]) || { M: 1, X: 1, I: 1, thin: '#907563' };
    return { M: mo.M ?? 1, X: mo.X ?? 1, I: mo.I ?? 1, S: name === 'leucistic' ? 1.0 : 0.0,
        thin: linColor(parseInt(String(mo.thin || '#907563').replace('#', ''), 16)),
        eyePink: String(mo.eye || '').startsWith('pink') ? 1.0 : 0.0 };
}

export function axolotlUniforms(ex, opts = {}) {
    // the morph's weights and colours (the glb's extras.bestiary.morphs, opts.morph: wild by default), the bake's own
    // blush, the crease fade's drive (one weight per knee) and switch
    const name = opts.morph ?? 'wild';
    if (ex.morphs && !ex.morphs[name]) {
        throw new Error(`[axolotl] unknown morph '${name}' (have: ${Object.keys(ex.morphs).join(', ')})`);
    }
    const mv = morphValues(ex.morphs, name);
    const { uniform } = THREE;
    return {
        morph: name, morphs: ex.morphs,
        M: uniform(mv.M), X: uniform(mv.X), I: uniform(mv.I), S: uniform(mv.S),
        melanin: uniform(linColor(MELANIN)), xantho: uniform(new THREE.Color(...XANTHO)), irid: uniform(linColor(IRID)),
        gold: uniform(linColor(GOLD)), thinBlood: uniform(linColor(THIN_BLOOD)), thinMel: uniform(mv.thin),
        thinPale: uniform(linColor(THIN_PALE)), melPass: uniform(MEL_PASS), thkScale: uniform(THK_SCALE),
        eyePink: uniform(mv.eyePink),
        blushThin: uniform(Number.isFinite(ex.blush_thin) ? ex.blush_thin : BLUSH_THIN_FALLBACK),
        creaseL: uniform(0.0), creaseR: uniform(0.0), creaseOn: uniform(opts.crease === false ? 0.0 : 1.0),
    };
}

export function setMorph(A, name) {
    if (A.morphs && !A.morphs[name]) throw new Error(`[axolotl] unknown morph '${name}' (have: ${Object.keys(A.morphs).join(', ')})`);
    const mv = morphValues(A.morphs, name);
    A.M.value = mv.M; A.X.value = mv.X; A.I.value = mv.I; A.S.value = mv.S;
    A.thinMel.value.copy(mv.thin); A.eyePink.value = mv.eyePink;
    A.morph = name;
}

// three r184 adds each direct light's specular with f90 = 1 (axolotl_scene.js's note): scale what each light adds by k
function scaleDirectSpecular(m, k) {
    const baseSetup = m.setupLightingModel.bind(m);
    m.setupLightingModel = (builder) => {
        const model = baseSetup(builder);
        const baseDirect = model.direct.bind(model);
        model.direct = (args, b) => {
            const rl = args.reflectedLight;
            const s0 = rl.directSpecular.toVar();
            baseDirect(args, b);
            rl.directSpecular.assign(s0.add(rl.directSpecular.sub(s0).mul(k)));
        };
        return model;
    };
}

// the micro-relief is the specular's (the AX7c check): the direct diffuse (and, given the scene's irradiance look-up
// env, the environment's) reads the BAKED normal nBaked
function diffuseOnBakedNormal(m, nBaked, env) {
    const baseSetup = m.setupLightingModel.bind(m);
    m.setupLightingModel = (builder) => {
        const model = baseSetup(builder);
        const baseDirect = model.direct.bind(model);
        model.direct = (args, b) => {
            baseDirect(args, b);
            const L = args.lightDirection;
            const dn = nBaked.dot(L).clamp().sub(THREE.normalView.dot(L).clamp());
            args.reflectedLight.directDiffuse.addAssign(dn.mul(args.lightColor).mul(THREE.diffuseColor.rgb).mul(1.0 / Math.PI));
        };
        if (env) {
            const baseIndirect = model.indirectDiffuse.bind(model);
            model.indirectDiffuse = (b) => {
                baseIndirect(b);
                const de = env(nBaked.transformDirection(THREE.cameraViewMatrix)).sub(env(THREE.normalWorld));
                b.context.reflectedLight.indirectDiffuse.addAssign(de.mul(THREE.diffuseColor.rgb));
            };
        }
        return model;
    };
}

// a studio's dark set in the environment's reflections (axolotl_scene.js wallInReflections; a scene's term: opts.studioWall
// = { top: [sin lo, sin hi], k })
function wallInReflections(m, nBaked, W) {
    const { smoothstep, float, positionViewDirection, cameraViewMatrix } = THREE;
    const baseSetup = m.setupLightingModel.bind(m);
    m.setupLightingModel = (builder) => {
        const model = baseSetup(builder);
        const baseSpecular = model.indirectSpecular.bind(model);
        model.indirectSpecular = (b) => {
            const Ry = positionViewDirection.negate().reflect(nBaked).transformDirection(cameraViewMatrix).y;
            const wall = smoothstep(-0.03, 0.03, Ry).mul(float(1.0).sub(smoothstep(W.top[0], W.top[1], Ry)));
            b.context.radiance.mulAssign(float(1.0).sub(wall.mul(1.0 - W.k)));
            baseSpecular(b);
        };
        return model;
    };
}

export function axolotlSkin(src, A, U, o = {}, geo = null, rx = null) {
    // the wet skin (the header); A: axolotlUniforms, U: bestiary's (tint, t), o: the scene options, geo: the skin's
    // geometry (its crease attribute when the fade is built), rx: a remix's layers ({ block, R, lib }: remixAxolotl)
    const { texture, uv, vec3, float, mix, normalMap, normalView, positionViewDirection, pow, smoothstep } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshSSSNodeMaterial();
    const ground = texture(src.map, st).rgb;
    const orm = texture(src.roughnessMap, st);
    const masks = texture(src.thicknessMap, st);
    const disp = texture(src.emissiveMap, st);
    const cover = orm.b.mul(A.M).clamp(0.0, 1.0);
    // the blush is the blood and the melanophores lie over it (axolotl_scene.js's AX7c note): read back out of the ground
    // where the pigment covers it, the stalks and filaments keeping their red
    const blushed = masks.r.mul(A.blushThin).mul(float(1.0).sub(smoothstep(0.7, 0.85, masks.b))).clamp(0.0, 0.9);
    const unblushed = ground.sub(A.thinBlood.mul(blushed)).div(float(1.0).sub(blushed)).max(vec3(0.0));
    let col = mix(mix(ground, unblushed, smoothstep(0.25, 0.7, cover)), A.melanin, cover);
    col = col.mul(mix(vec3(1.0), A.xantho, disp.g.mul(A.X).clamp(0.0, 1.5)));
    col = col.mul(float(1.0).sub(disp.b.mul(A.S).mul(0.8)));
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    col = mix(col, A.gold, disp.r.mul(A.I).clamp(0.0, 1.0).sqrt().mul(0.95));
    const glint = mix(A.gold.mul(1.5), A.irid, smoothstep(0.2, 0.45, masks.g));
    col = col.add(glint.mul(disp.r.mul(A.I)).mul(float(0.03).add(pow(float(1.0).sub(ndv), 2.0).mul(0.25))));
    let rough = null, metal = null, emis = null, S = null;
    if (rx) ({ col, rough, metal, emis, S } = remixLayers(col, orm, masks, disp, ndv, rx, U));
    m.colorNode = col.mul(U?.tint ?? vec3(1.0));
    // THE MICRO-NORMAL (axolotl_scene.js's): the glands' domes less a finer grain, the slope by central differences in
    // cell units added to the baked normal's tangent xy, faded by the cells' screen footprint and by the zone
    const { mx_worley_noise_vec2, fwidth, max: tmax, normalize } = THREE;
    const pm = st.mul(MICRO.cells);
    const dist = (p) => {
        const f = mx_worley_noise_vec2(p, 0.9);
        const e1 = f.x.sqrt(), e2 = f.y.sqrt();
        const kk = tmax(float(MICRO.round).sub(e2.sub(e1)), 0.0);
        return e1.sub(kk.mul(kk).div(4.0 * MICRO.round));
    };
    const hgt = (p) => float(1.0).sub(dist(p).pow(2.0)).sub(dist(p.mul(3.3)).pow(2.0).mul(MICRO.grain));
    const e = 0.06;
    const dhu = hgt(pm.add(THREE.vec2(e, 0.0))).sub(hgt(pm.sub(THREE.vec2(e, 0.0)))).div(2.0 * e);
    const dhv = hgt(pm.add(THREE.vec2(0.0, e))).sub(hgt(pm.sub(THREE.vec2(0.0, e)))).div(2.0 * e);
    const fw = fwidth(pm);
    const fade = float(1.0).sub(smoothstep(MICRO.fade[0], MICRO.fade[1], tmax(fw.x, fw.y)));
    const zoneW = masks.b.greaterThan(0.95).select(float(0.0),
        mix(float(1.0), float(MICRO.fin), masks.b.sub(0.2).div(0.4).clamp(0.0, 1.0)));
    const k = fade.mul(zoneW).mul(MICRO.strength);
    let nb = texture(src.normalMap, st).xyz.mul(2.0).sub(1.0);
    let ao = orm.r;
    // THE KNEE'S CREASE FADE (the header): the zone's mask (+ the left knee, - the right) by the knee's corrective weight
    if (geo?.attributes?.bestiaryCrease) {
        const c = THREE.attribute('bestiaryCrease', 'float');
        const w = c.max(0.0).mul(A.creaseL).add(c.negate().max(0.0).mul(A.creaseR)).clamp(0.0, 1.0).mul(A.creaseOn);
        nb = normalize(mix(nb, vec3(0.0, 0.0, 1.0), w));
        ao = mix(ao, float(1.0), w.mul(CREASE.ao));
    }
    const nm = normalize(vec3(nb.x.sub(dhu.mul(k)), nb.y.sub(dhv.mul(k)), nb.z));
    m.normalNode = normalMap(nm.mul(0.5).add(0.5));
    const Ng = THREE.normalViewGeometry, Tv = THREE.tangentView;
    const Bv = Ng.cross(Tv).mul(THREE.tangentGeometry.w);
    const nBaked = normalize(Tv.mul(nb.x).add(Bv.mul(nb.y)).add(Ng.mul(nb.z)));
    diffuseOnBakedNormal(m, nBaked, o.envDiffuse || null);
    if (o.studioWall && !o.water) wallInReflections(m, nBaked, o.studioWall);
    const kLost = float(1.0).sub(fade).mul(zoneW).mul(MICRO.strength * MICRO.rough);
    m.ior = o.water ? WATER.ior_skin : 1.33;
    if (o.water) {
        m.specularIntensity = WATER.spec;
        scaleDirectSpecular(m, WATER.spec);
    }
    const r0 = orm.g.mul(orm.g).add(kLost.mul(kLost)).sqrt();
    m.roughnessNode = rough ? rough(r0).clamp(0.02, 1.0) : r0;
    m.metalnessNode = metal ?? float(0.0);
    m.aoNode = ao;
    if (emis) m.emissiveNode = emis;
    // the thin tissue's transmitted light (axolotl_scene.js's AX7b / AX7c notes): its colour mix(open tissue, melanin
    // brown, the transmission's own cover), its strength the light between the melanophores; none through a gold patch
    const handW = smoothstep(0.05, 0.08, masks.b).mul(float(1.0).sub(smoothstep(0.2, 0.4, masks.b)));
    const thinT = masks.r.mul(mix(float(1.0), float(THIN_HAND), handW));
    const coverT = mix(cover, cover.sub(0.5).div(0.5).clamp(0.0, 1.0).pow(2.0), thinT);
    const pass = float(1.0).sub(coverT).add(coverT.mul(A.melPass));
    let thinOpen = mix(A.thinPale, A.thinBlood, smoothstep(0.75, 0.95, masks.b));
    if (rx) thinOpen = mix(thinOpen, rx.R.thinT, rx.R.thinW);           // (an element's thin tint: remix.js's)
    m.thicknessColorNode = mix(thinOpen, A.thinMel, coverT).mul(pass).mul(thinT.mul(0.94))
        .mul(float(1.0).sub(disp.r.mul(A.I).mul(0.95).clamp(0.0, 1.0)));
    m.thicknessDistortionNode = float(0.12);
    m.thicknessAmbientNode = float(0.02);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(3.0);
    m.thicknessScaleNode = A.thkScale;
    const thinLift = thinT.mul(0.9);
    m.receivedShadowNode = (shadow) => THREE.max(shadow, thinLift);
    m.name = rx ? 'axolotl_skin_remix' : 'axolotl_skin_bestiary';
    return m;
}

export function axolotlEye(src, A, o = {}) {
    const { texture, uv, float, mix, vec3 } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const masks = texture(src.thicknessMap, st);
    // the albinos' pink eye: the ring and the outer iris to the blood's pink, the pupil to a dark red
    const base = texture(src.map, st).rgb;
    const pink = mix(vec3(0.55, 0.18, 0.20), vec3(0.20, 0.03, 0.04), masks.g);
    m.colorNode = mix(base, pink, A.eyePink);
    m.normalNode = THREE.normalMap(texture(src.normalMap, st));
    m.roughnessNode = float(0.04);
    m.metalnessNode = float(0.0);
    m.ior = o.water ? WATER.ior_eye : 1.376;
    if (o.water) {
        m.specularIntensity = WATER.spec_eye;
        scaleDirectSpecular(m, WATER.spec_eye);
    } else if (o.studioWall) {
        wallInReflections(m, THREE.normalView, o.studioWall);
    }
    m.name = 'axolotl_eye_bestiary';
    return m;
}

// AX13's PEARLS (species/axolotl_pearls.py: four glass droplets on the lower lip, a primitive whose material kind is
// 'pearl'; axolotl_scene.js pearlMaterial, ported): the clarity is the MATERIAL's, read from the glb's factors (the colour,
// the opacity with alphaMode BLEND, transmission, ior, the clear coat, roughness, thickness), never a texture alpha (the
// engine's image decode divides it); the opacity carries the see-through, the transmission the refraction; underwater it
// keeps the glb's ior and clear coat (AX13, 15:5x 11-02: the cornea's underwater recipe, relative ior ~1.02 and the lobes
// scaled, left faint discs with no glint; p14 / p15 keep a glint on each droplet), only the studio's wall dropped
export function axolotlPearl(src, o = {}) {
    const m = new THREE.MeshPhysicalNodeMaterial();
    m.color.copy(src.color || new THREE.Color(0.82, 0.86, 0.83));
    m.metalness = 0.0;
    m.roughness = Number.isFinite(src.roughness) ? src.roughness : 0.05;
    m.transparent = true;
    m.opacity = Number.isFinite(src.opacity) ? src.opacity : 0.3;
    m.transmission = Number.isFinite(src.transmission) ? src.transmission : 0.9;
    m.thickness = Number.isFinite(src.thickness) && src.thickness > 0 ? src.thickness : 0.0036;
    if (src.attenuationColor) m.attenuationColor.copy(src.attenuationColor);
    if (Number.isFinite(src.attenuationDistance)) m.attenuationDistance = src.attenuationDistance;
    m.ior = Number.isFinite(src.ior) ? src.ior : 1.36;
    m.clearcoat = Number.isFinite(src.clearcoat) ? src.clearcoat : 1.0;
    m.clearcoatRoughness = Number.isFinite(src.clearcoatRoughness) ? src.clearcoatRoughness : 0.03;
    if (!o.water && o.studioWall) wallInReflections(m, THREE.normalView, o.studioWall);
    m.name = 'axolotl_pearl_bestiary';
    return m;
}

// the crease fade's per-vertex zone mask (the header): + on the left knee's zone, - on the right's
export function creaseMask(geo, mesh) {
    const dict = mesh.morphTargetDictionary || {};
    const P = geo.morphAttributes?.position;
    if (!P) return null;
    const n = geo.attributes.position.count;
    const out = new Float32Array(n);
    let any = 0;
    for (const base of CREASE.targets) {
        for (const [sd, sgn] of [['L', 1], ['R', -1]]) {
            const k = dict[`${base}_${sd}`];
            if (k == null || !P[k]) continue;
            const a = P[k].array, it = P[k].itemSize;
            for (let i = 0; i < n; i++) {
                const d = Math.hypot(a[i * it], a[i * it + 1], a[i * it + 2]);
                if (d <= 0) continue;
                const u = Math.min(d / CREASE.d_full, 1.0);
                const w = u * u * (3 - 2 * u);
                if (w > Math.abs(out[i])) { out[i] = sgn * w; any++; }
            }
        }
    }
    return any ? out : null;
}

// ============================================================================================ the remix on the skin
function remixLayers(col, orm, masks, disp, ndv, rx, U) {
    // remix.js's colour stack on the axolotl's composed pigment (remixSkinMaterial's order: palette then element zone
    // remaps, the surface layer, the element's glow on its glow zone, the thin tint), with remix.js's own builders
    // (rx.lib) and uniforms (rx.R); the axolotl's packs: masks (R thin, G ventral, B gill / fin / filament), display
    // (R iridophores, G xanthophores, B leucistic speckles), orm (R AO, G roughness, B the melanophore cover)
    const { float, vec3, mix } = THREE;
    const { block, R, lib } = rx;
    const packs = { masks, display: disp, orm };
    const zones = block.zones || {};
    const zc = {};
    const zone = (name) => lib.zoneMaskN(name, zones, packs, zc);
    let metal = float(0.0);
    const edits = [];
    for (const layer of [R.palette, R.element]) {
        for (const role of lib.ROLES) {
            const Z = layer[role];
            const zm = zone(role);
            col = lib.remapN(col, Z, zm);
            const mo = zm.mul(Z.on);
            edits.push([Z, mo]);
            metal = mix(metal, Z.metal, mo.mul(Z.metalW));
        }
    }
    const cells = lib.packChannel(zones.cells, packs, 0.5);
    const mottle = lib.packChannel(zones.mottle, packs, 0.5);
    const sk = block.element?.surface?.kind;
    const S = sk ? lib.surfaceTerms(sk, R, { ao: orm.r, ny: THREE.normalWorld.y, cells, mottle }) : null;
    if (S) {
        col = mix(col, S.albedo, S.w);
        if (S.metalTo) metal = mix(metal, S.metalTo, S.w);
        if (S.metalMul) metal = metal.mul(S.metalMul);
    }
    const rough = (r0) => {
        let r = r0;
        for (const [Z, mo] of edits) r = mix(r.add(Z.rough.mul(mo)), Z.roughTo, mo.mul(Z.roughW));
        if (S) {
            r = r.add(S.roughAdd);
            if (S.roughTo) r = mix(r, S.roughTo, S.w);
        }
        return r;
    };
    let emis = null;
    const g = block.element?.glow;
    if (g || S?.ember || (S && (sk === 'pustules' || sk === 'frost_recess'))) {
        const pulse = lib.pulseN(R.glowBands, R.glowRate, R.glowFade, cells, U.t);
        const gm = zone('glow');
        const gc = R.glowC.mul(R.glowGain);
        emis = vec3(0.0, 0.0, 0.0);
        if (g) emis = emis.add(gc.mul(gm.mul(gm)).mul(pulse));
        if (S?.ember) emis = emis.add(gc.mul(S.ember).mul(pulse));
        if (S && (sk === 'pustules' || sk === 'frost_recess')) emis = emis.add(gc.mul(S.glow).mul(pulse));
    }
    return { col, rough, metal: metal.clamp(0.0, 1.0), emis, S };
}

// ============================================================================================ the skeleton (FK)
// the creature's own frame (the root bone's: the bind's, +Z forward, +Y up, +X its left), x4 metres as authored: each
// joint's world = its parent's x T(bind translation) x R(q_bind q_pose)
class Skel {
    constructor(bones) {
        const root = bones.get('root');
        if (!root) throw new Error('[axolotl] the glb has no root bone');
        this.names = []; this.idx = new Map(); this.par = []; this.Pb = []; this.Qb = []; this.bone = [];
        const visit = (b, p) => {
            const i = this.names.length;
            this.names.push(b.name); this.idx.set(b.name, i); this.par.push(p); this.bone.push(b);
            this.Pb.push(b.position.clone()); this.Qb.push(b.quaternion.clone());
            for (const c of b.children) if (c.isBone) visit(c, i);
        };
        visit(root, -1);
        this.n = this.names.length;
        this.Qp = Array.from({ length: this.n }, () => new THREE.Quaternion());
        this.Qw = Array.from({ length: this.n }, () => new THREE.Quaternion());
        this.Pw = Array.from({ length: this.n }, () => new THREE.Vector3());
        this.kids = Array.from({ length: this.n }, () => []);
        for (let i = 1; i < this.n; i++) this.kids[this.par[i]].push(i);
        this._q = new THREE.Quaternion();
        this.fkAll();
        this.W0q = this.Qw.map((q) => q.clone());
        this.W0p = this.Pw.map((p) => p.clone());
    }
    i(name) {
        const k = this.idx.get(name);
        if (k == null) throw new Error(`[axolotl] no joint ${name}`);
        return k;
    }
    fk(i) {
        // joint i's world from its parent's (which must be current)
        const p = this.par[i];
        const ql = this._q.copy(this.Qb[i]).multiply(this.Qp[i]);
        if (p < 0) { this.Qw[i].copy(ql); this.Pw[i].copy(this.Pb[i]); return; }
        this.Pw[i].copy(this.Pb[i]).applyQuaternion(this.Qw[p]).add(this.Pw[p]);
        this.Qw[i].copy(this.Qw[p]).multiply(ql);
    }
    fkAll() { for (let i = 0; i < this.n; i++) this.fk(i); }
    fkSub(i) {
        // joint i and every descendant, parents first
        this.fk(i);
        for (const c of this.kids[i]) this.fkSub(c);
    }
    reset() { for (const q of this.Qp) q.identity(); }
    aim(i, d) {
        // the minimal swing turning joint i's x toward the world direction d under its posed parent (sprawl.aim)
        const p = this.par[i];
        const qf = new THREE.Quaternion().copy(this.Qw[p]).multiply(this.Qb[i]);
        const v = d.clone().normalize().applyQuaternion(qf.invert()).normalize();
        this.Qp[i].setFromUnitVectors(X_AX, v);
    }
}

function basisQ(x, n) {
    // the frame (columns x, n x x, n) of a bone direction x and a plane normal n, as a quaternion (axolotl_rig._basis)
    const xx = x.clone().normalize();
    const nn = n.clone().addScaledVector(xx, -n.dot(xx)).normalize();
    const yy = new THREE.Vector3().crossVectors(nn, xx);
    return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(xx, yy, nn));
}

function twoBone(S, T, L1, L2, pole, inc = null) {
    // the middle joint of a two-bone chain from S toward T, bent toward `pole` (axolotl_rig.two_bone); inc: the hinge's
    // included range (deg, the SPEC's r_elbow / r_knee), the reach clamped to it (a target past it is missed, the hinge
    // never folds or opens past its range)
    const d = T.clone().sub(S);
    const len = d.length();
    let lo = Math.abs(L1 - L2) + 1e-9, hi = L1 + L2 - 1e-9;
    if (inc) {
        const dAt = (deg) => Math.sqrt(L1 * L1 + L2 * L2 - 2.0 * L1 * L2 * Math.cos(deg * DEG));
        lo = Math.max(lo, dAt(inc[0]));
        hi = Math.min(hi, dAt(inc[1]));
    }
    const D = Math.min(Math.max(len, lo), hi);
    const u = d.divideScalar(Math.max(len, 1e-12));
    const a = (L1 * L1 - L2 * L2 + D * D) / (2.0 * D);
    const h = Math.sqrt(Math.max(L1 * L1 - a * a, 0.0));
    const p = pole.clone().addScaledVector(u, -pole.dot(u));
    p.divideScalar(Math.max(p.length(), 1e-12));
    // (E, and Tr: the target as reached, T itself unless the reach was clamped)
    return { E: S.clone().addScaledVector(u, a).addScaledVector(p, h), Tr: S.clone().addScaledVector(u, D) };
}

// ============================================================================================ the rig's drivers
function twistX(q) {
    // the twist about x of a rotation: atan2(R21 - R12, R11 + R22) (the forge's), = atan2(2 x w, w^2 - x^2)
    return Math.atan2(2.0 * q.x * q.w, q.w * q.w - q.x * q.x);
}

function foldZ(q) {
    // a local rotation's fold about z: atan2(R10, R00) (CORRECTIVES' 'fold' measure)
    return Math.atan2(2.0 * (q.x * q.y + q.z * q.w), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
}

function slerpIdentity(q, share, out) {
    // slerp(I, q, share), the short way: the same axis, share x the angle (axolotl_rig.half_turn)
    const s = q.w < 0 ? -1 : 1;
    const x = q.x * s, y = q.y * s, z = q.z * s, w = Math.min(1.0, q.w * s);
    const sn = Math.hypot(x, y, z);
    if (sn < 1e-12) return out.identity();
    const ang = 2.0 * Math.atan2(sn, w) * share;
    const k = Math.sin(0.5 * ang) / sn;
    return out.set(x * k, y * k, z * k, Math.cos(0.5 * ang));
}

export function driveLeaves(sk, leaves) {
    // the driven leaves' pose rotations from their drivers' (extras.bestiary.driven_leaves)
    for (const [nm, r] of Object.entries(leaves || {})) {
        const i = sk.idx.get(nm), j = sk.idx.get(r.driver);
        if (i == null || j == null) continue;
        const qd = sk.Qp[j];
        if (r.rule === 'half_angle') slerpIdentity(qd, r.share, sk.Qp[i]);
        else if (r.rule === 'twist_counter') sk.Qp[i].setFromAxisAngle(X_AX, -r.share * twistX(qd));
        else if (r.rule === 'twist_carry') sk.Qp[i].setFromAxisAngle(X_AX, r.share * twistX(qd));
        else throw new Error(`[axolotl] unknown driven leaf rule ${r.rule}`);
    }
}

export function correctiveWeights(sk, corr) {
    // each corrective's weight at the current pose (sk's worlds current): {name: [w, angle deg, target]}
    const out = {};
    const a = new THREE.Vector3(), b = new THREE.Vector3();
    for (const [nm, c] of Object.entries(corr || {})) {
        const [kind, arg] = c.measure;
        let ang;
        if (kind === 'included') {
            const [ja, jb, jc] = arg.map((n) => sk.i(`${n}_${c.side}`));
            a.copy(sk.Pw[ja]).sub(sk.Pw[jb]);
            b.copy(sk.Pw[jc]).sub(sk.Pw[jb]);
            ang = Math.acos(Math.min(1, Math.max(-1, a.dot(b) / Math.max(a.length() * b.length(), 1e-30)))) / DEG;
        } else {
            ang = foldZ(sk.Qp[sk.i(`${arg}_${c.side}`)]) / DEG;
        }
        const u = Math.min(Math.max((ang - c.ramp[0]) / (c.ramp[1] - c.ramp[0]), 0.0), 1.0);
        out[nm] = [u * u * (3.0 - 2.0 * u), ang, c.target];
    }
    return out;
}

export function driveFromNodes(sk, leaves, corr) {
    // THE DRIVERS WHEN THE POSE COMES FROM THE NODES (create({ motion: 'none' }) with a scene, a clip or a cross posing the
    // bones; api.axolotl.drive()): each joint's pose rotation read back over its bind, q_pose = q_bind^-1 q_node (never the
    // whole node rotation: the AX10b check), the driven leaves' set from their drivers' and written to their nodes
    // (q_bind q_pose), the FK on the pose, the correctives' weights (as correctiveWeights). The motion's own path computes
    // the same pose rotations directly (salamanderMotion: the node is written q_bind q_pose from them)
    const inv = new THREE.Quaternion();
    for (let i = 0; i < sk.n; i++) sk.Qp[i].copy(inv.copy(sk.Qb[i]).invert()).multiply(sk.bone[i].quaternion);
    driveLeaves(sk, leaves);
    for (const nm of Object.keys(leaves || {})) {
        const i = sk.idx.get(nm);
        if (i != null) sk.bone[i].quaternion.copy(sk.Qb[i]).multiply(sk.Qp[i]);
    }
    sk.fkAll();
    return correctiveWeights(sk, corr);
}

function applyCorrectives(w, meshes, A) {
    // the correctives' weights onto every primitive's morph influences and the crease fade's drive
    for (const o of meshes) {
        if (!o.morphTargetInfluences) continue;
        for (const [, [x, , k]] of Object.entries(w)) o.morphTargetInfluences[k] = x;
    }
    if (A) {
        A.creaseL.value = w.knee_ext_L?.[0] ?? 0.0;
        A.creaseR.value = w.knee_ext_R?.[0] ?? 0.0;
    }
}

// ============================================================================================ the salamander motion
function qLocal(fold = 0, splay = 0, twist = 0) {
    // a joint's local rotation from its anatomical angles (deg): Rz(fold) Ry(-splay) Rx(twist) (axolotl_rig.local)
    const q = new THREE.Quaternion().setFromAxisAngle(Z_AX, fold * DEG);
    if (splay) q.multiply(new THREE.Quaternion().setFromAxisAngle(Y_AX, -splay * DEG));
    if (twist) q.multiply(new THREE.Quaternion().setFromAxisAngle(X_AX, twist * DEG));
    return q;
}

const LIMBS = {
    fore: ['humerus', 'radius', 'carpus', 'metacarpus'],
    hind: ['femur', 'tibia', 'tarsus', 'metatarsus'],
};
const LIMB_ORDER = ['hind_L', 'fore_L', 'hind_R', 'fore_R'];      // walk_pose's order (and the walk's sequence)

export function salamanderMotion(bones, seed, group, sp, opts = {}, ex = {}, meshes = [], A = null) {
    const sk = new Skel(bones);
    // the motion's constants: the species row's (bestiary.js SPECIES.axolotl: AX10b's, the shipped glb's gated rig), under
    // a glb's own extras.bestiary.motion when it carries them (a rig round that re-tunes the swim writes them beside its
    // gates: the runtime follows the glb), under the caller's
    const XM = ex.motion || {};
    const G = { ...sp.gait, ...(XM.walk || {}), ...(opts.gait || {}) };
    const SW = { ...sp.swim, ...(XM.swim || {}), ...(opts.swim && typeof opts.swim === 'object' ? opts.swim : {}) };
    const KM = sp.body.k_mm;                   // x4 metres per life mm
    const TL = sp.body.TL_mm * KM;             // the total length, x4 m
    const size = group.scale.x || 1.0;         // the creature's size: controls are in metres at it
    const leaves = ex.driven_leaves || {};
    const corr = ex.correctives || {};
    const standRot = new Map(Object.entries(ex.stand?.rotations || {}).map(([k, q]) => [k, new THREE.Quaternion(...q)]));
    const useStand = opts.stand !== false && standRot.size > 0;
    // the bind's and the stand's limb points: the wrist / ankle (A), the metapodial joint (M), the digits' bases (tip:
    // the IK target on their centre, ik_hand / ik_foot, which the stand keeps planted)
    const limbIdx = {}, standPts = {};
    for (const k of LIMB_ORDER) {
        const [kind, sd] = k.split('_');
        const ids = LIMBS[kind].map((n) => sk.i(`${n}_${sd}`));
        const digits = sk.kids[ids[3]].filter((c) => /_digit\d_0_/.test(sk.names[c]));
        limbIdx[k] = { kind, sd, ids, digits, tipJ: sk.i(kind === 'fore' ? `ik_hand_${sd}` : `ik_foot_${sd}`) };
    }
    if (useStand) for (const [nm, q] of standRot) { const i = sk.idx.get(nm); if (i != null) sk.Qp[i].copy(q); }
    sk.fkAll();
    for (const k of LIMB_ORDER) {
        const L = limbIdx[k];
        standPts[k] = { A: sk.Pw[L.ids[2]].clone(), M: sk.Pw[L.ids[3]].clone(), tip: sk.W0p[L.tipJ].clone() };
    }
    const FOOT_SPOTS = LIMB_ORDER.map((k) => standPts[k].M);      // (the step rate's feet: each stand spot)
    sk.reset();
    sk.fkAll();
    // the axial chain's stations (swim_pose): neck_0, spine_6 .. spine_0, tail_0 .. tail_11, s from each joint's bind z
    const axial = ['neck_0', ...[6, 5, 4, 3, 2, 1, 0].map((k) => `spine_${k}`), ...Array.from({ length: 12 }, (_, k) => `tail_${k}`)];
    const axialI = axial.map((n) => sk.i(n));
    const ss = axialI.map((i) => sp.body.s_hip - (sk.W0p[i].z / KM) / sp.body.TL_mm);
    ss.push(1.0);
    const spineI = Array.from({ length: 7 }, (_, k) => sk.i(`spine_${k}`));
    const tailI = Array.from({ length: 12 }, (_, k) => sk.i(`tail_${k}`));
    const gillI = [];
    for (const r of [1, 2, 3]) for (const sd of ['L', 'R']) for (let j = 0; j < 4; j++) gillI.push([r, sd, j, sk.i(`gill_${r}_${j}_${sd}`)]);
    // the seeded phases: the walk's jitter (walk_pose's rng(11) uniform +-jitter; opts.gait.jitter: {limb: x}), the
    // idle's gill phases and rates (idle_pose's ph (3, 2, 4) and fr (3, 2); opts.idle: { ph, fr })
    const jit = {};
    LIMB_ORDER.forEach((k, n) => {
        jit[k] = G.jitter_phase?.[k] ?? (2.0 * hash01(101 + n, seed) - 1.0) * G.jitter;
    });
    const ID = opts.idle || {};
    const ph = ID.ph || [0, 1, 2].map((i) => [0, 1].map((kk) => [0, 1].map((c) => 2 * Math.PI * hash01(200 + 8 * i + 4 * kk + c, seed))));
    const fr = ID.fr || [0, 1, 2].map((i) => [0, 1].map((kk) => 0.35 + 0.4 * hash01(300 + 2 * i + kk, seed)));
    // ---------------------------------------------------------------------------------------- the controls
    // a step schedule [[t, v (m/s at the creature's size), w (rad/s), mode?], ...] (opts.walk.schedule), and live calls
    // appended at the last update's time; mode 'auto' swims above swimAbove (TL/s), 'walk' / 'swim' force it
    const cmds = [];
    for (const row of opts.walk?.schedule || []) cmds.push({ t: row[0], v: row[1], w: row[2] ?? 0, mode: row[3] });
    if (!cmds.length) cmds.push({ t: -1e9, v: (opts.walk?.speed ?? 0), w: (opts.walk?.turn ?? 0) });
    cmds.sort((p, q) => p.t - q.t);
    const mode0 = opts.mode ?? (opts.swim === true ? 'swim' : 'auto');
    let lastT = 0;
    const DT = 1.0 / 240.0, T0 = 0.0;
    const STRIDE = G.stride * TL, VMIN = G.v_settle * G.speed * TL, PIVOT = (G.pivot ?? 0.0) * TL;
    let cache = null;
    function resetCache() {
        // t = 0: at rest in the first command's mode, or (opts.walk.instant) already at its speed, the motion before 0
        // carried back from it (a walk under way: its plants made before 0 where that walk put them)
        const c0 = cmdAt(T0);
        const sw0 = modeAt(T0) === 'swim' ? 1 : 0;
        const v0 = opts.walk?.instant ? c0.v / size : 0;
        const vw0 = v0 * (1 - sw0);
        const f0 = vw0 > 1e-7 ? Math.max(vw0, VMIN) / STRIDE : 0;
        // (A1) A COMMAND NEVER MOVES A PLANTED FOOT: the plants of stances that touched down by the command's time (lastT) are kept
        // (each plant is the body's pose at its stance's MIDDLE, which can lie after the command: re-made under the new future, a
        // standing foot slid; A1 g02: 6 mm x4 when a turn followed the arrival); the history before lastT is the same, so the keys
        // (limb, cycle) still name the same stances
        const keep = new Map();
        if (cache) for (const [k, p] of cache.plants) if (p.td != null && p.td <= lastT) keep.set(k, p);
        cache = { t: [T0], x: [0], z: [0], psi: [0], c: [0], th: [0], v: [v0], sw: [sw0], settle: [vw0 > 1e-7 ? 1 : 0],
            vw: [vw0], fw: [f0], plants: keep };
    }
    function cmdAt(t) {
        let c = cmds[0];
        for (const q of cmds) { if (q.t <= t) c = q; else break; }
        return c;
    }
    function modeAt(t) {
        const c = cmdAt(t);
        const m = c.mode ?? mode0;
        if (m === 'swim' || m === 'walk') return m;
        return Math.abs(c.v / size) / TL > (SW.above ?? 0.25) ? 'swim' : 'walk';
    }
    function step() {
        const C = cache, n = C.t.length - 1;
        const t = C.t[n];
        const c = cmdAt(t);
        let vt = c.v / size, wt = c.w;
        // (A1) the walkTo in force is the command's own (cmds carry it: a speed or turn after it ends it from ITS time, the walk
        // before stays in the history, where live.target cleared it and a replay from 0 lost the walk: the creature jumped back)
        const live = { target: c.target || null };
        if (live.target && t >= live.target.t0) {
            // walkTo: steer toward the point (the group's parent's, carried into the group's frame at the call). (A1) The point
            // steered is the PIVOT (gait.pivot TL ahead of the root, the turn's centre), not the root: a turn about the pivot swings
            // the root w x pivot sideways, so a root aimed at a point nearer than ~ the pivot circled it (A1 g02: a 32 s orbit 16 cm
            // off). Inside the radius the walk ARRIVES (latched on the grid: speed and turn 0 from that step; a heading after it is
            // the caller's turn, about the pivot, which stays on the point)
            const qx = C.x[n] + Math.sin(C.psi[n]) * PIVOT, qz = C.z[n] + Math.cos(C.psi[n]) * PIVOT;
            const dx = live.target.x - qx, dz = live.target.z - qz;
            const dist = Math.hypot(dx, dz);
            if (live.target.arrived == null && dist < live.target.r) live.target.arrived = t;
            if (live.target.arrived != null && t >= live.target.arrived) {
                vt = 0; wt = 0;
            } else {
                const err = Math.atan2(Math.sin(Math.atan2(dx, dz) - C.psi[n]), Math.cos(Math.atan2(dx, dz) - C.psi[n]));
                wt = Math.max(-live.target.wmax, Math.min(live.target.wmax, 2.0 * err));
                // (A1) the approach at the speed it can stop from (v^2 = 2 a d to half the radius: the walk's accel limit brakes it
                // onto the point; the old dist / 4r ramp asked for more braking than accel allows and overshot ~6 mm x4)
                const brake = Math.sqrt(2.0 * G.accel * TL * Math.max(0, dist - 0.5 * live.target.r));
                vt = Math.min(live.target.v, brake) * Math.max(0, Math.cos(err));
            }
        }
        const swimT = modeAt(t) === 'swim' ? 1 : 0;
        const acc = (swimT ? SW.accel : G.accel) * TL;
        const v0 = C.v[n];
        const v = v0 + Math.max(-acc * DT, Math.min(acc * DT, vt - v0));
        const sw = C.sw[n] + Math.max(-DT / SW.blend, Math.min(DT / SW.blend, swimT - C.sw[n]));
        // the body turns about its PIVOT (gait.pivot TL ahead of the root, between the girdles: a salamander's trunk swings
        // both ends; about the pelvis the turn swept the forefeet twice as far and folded the outer elbow to 49 deg), so the
        // root swings out by w x pivot as the heading turns
        const psi = C.psi[n] + wt * DT;
        const x = C.x[n] + (Math.sin(psi) * v - Math.cos(psi) * wt * PIVOT) * DT;
        const z = C.z[n] + (Math.cos(psi) * v + Math.sin(psi) * wt * PIVOT) * DT;
        // the gait: the step rate from the FASTEST FOOT (the beetle's B11 rule): each stand spot's speed as the body walks
        // and turns, |(w z, v - w x)| in the root frame, over the stride, so in a turn no foot strides past the stride (the
        // outer feet), and a turn on the spot steps too; once it has walked, a stop keeps the clock at the walk's own rate
        // with no stride (the plants come home under the body within a cycle, every swing lands, the feet then step in
        // place by nothing: the creature stands); before any walk the clock is still
        const ww = wt * (1.0 - sw);
        let vf = 0.0;
        // (A1) the turn's share of a foot's speed counts 1 / turn_stride (0.25): a turning foot takes SHORTER steps. A sprawled limb
        // reaches less across than along: at a full stride a turn's plants (the stand spot swept tangentially) lay 4.8-7.3 mm x4
        // beyond the hinge-clamped reach of the hind and fore limbs and the planted digits slid with the clamp (A1 g02: 16 mm;
        // 0.5 left 2.7 mm on a turn on the spot, 0.35 2.0 mm, 0.25 none: every stance's IK miss 0)
        const TS = G.turn_stride ?? 0.25;
        for (const p of FOOT_SPOTS) vf = Math.max(vf, Math.hypot(ww * (p.z - PIVOT) / TS, v * (1.0 - sw) - ww * p.x / TS));
        const vw = vf;
        const settle = (C.settle[n] > 0 || vw > 1e-7) ? 1.0 : 0.0;
        const f = vw > 1e-7 ? Math.max(vw, VMIN) / STRIDE : (settle > 0 ? VMIN / STRIDE : 0.0);
        const fs = v * sw / TL / SW.stride + (sw > 0 ? SW.hover * (1 - Math.min(1, v / TL / 0.1)) : 0) * sw;
        C.t.push(t + DT); C.x.push(x); C.z.push(z); C.psi.push(psi); C.v.push(v); C.sw.push(sw); C.settle.push(settle);
        C.c.push(C.c[n] + f * DT); C.th.push(C.th[n] + fs * DT); C.vw.push(vw); C.fw.push(f);
    }
    function stateAt(t) {
        if (!cache) resetCache();
        t = Math.max(t, T0);
        while (cache.t.length < 2 || cache.t[cache.t.length - 1] < t) step();
        // linear interpolation between grid samples (every quantity continuous)
        const C = cache;
        const u = (t - T0) / DT;
        const i0 = Math.max(0, Math.min(C.t.length - 2, Math.floor(u)));
        const a = Math.min(1, Math.max(0, u - i0));
        const L = (arr) => arr[i0] + (arr[i0 + 1] - arr[i0]) * a;
        return { t, x: L(C.x), z: L(C.z), psi: L(C.psi), c: L(C.c), th: L(C.th), v: L(C.v), sw: L(C.sw), vw: L(C.vw),
            f: L(C.fw), i0, a };
    }
    function timeOfCycle(c) {
        // the first grid time at which the gait's cycles reach c (c non-decreasing), interpolated; -inf before the start
        const C = cache.c;
        if (c <= C[0]) return cache.t[0] - (C[0] - c) / Math.max(1e-9, (cache.fw[0] || 1e-9));
        let lo = 0, hi = C.length - 1;
        if (C[hi] < c) return cache.t[hi];
        while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (C[mid] < c) lo = mid; else hi = mid; }
        const a = (c - C[lo]) / Math.max(C[hi] - C[lo], 1e-15);
        return cache.t[lo] + a * DT;
    }
    function rootAt(t) {
        // the root's transform at time t (the group's frame): position (x, z), heading psi
        const u = (t - T0) / DT;
        const C = cache;
        if (u <= 0) {
            // before the grid: the first sample's motion carried back (instant: a constant walk since long before)
            const dtb = t - C.t[0];
            return { x: C.x[0] + Math.sin(C.psi[0]) * C.v[0] * dtb, z: C.z[0] + Math.cos(C.psi[0]) * C.v[0] * dtb, psi: C.psi[0] };
        }
        const i0 = Math.min(C.t.length - 2, Math.floor(u));
        const a = Math.min(1, u - i0);
        return { x: C.x[i0] + (C.x[i0 + 1] - C.x[i0]) * a, z: C.z[i0] + (C.z[i0 + 1] - C.z[i0]) * a,
            psi: C.psi[i0] + (C.psi[i0 + 1] - C.psi[i0]) * a };
    }
    function relPoint(p, from, to, out) {
        // a point of the root frame at `from` (a root transform) in the root frame at `to`
        const c0 = Math.cos(from.psi), s0 = Math.sin(from.psi);
        const wx = from.x + c0 * p.x + s0 * p.z, wz = from.z - s0 * p.x + c0 * p.z;
        const dx = wx - to.x, dz = wz - to.z;
        const c1 = Math.cos(to.psi), s1 = Math.sin(to.psi);
        return out.set(c1 * dx - s1 * dz, p.y, s1 * dx + c1 * dz);
    }
    // ---------------------------------------------------------------------------------------- the IK (limb_ik)
    const tmpQ = new THREE.Quaternion();
    function limbIK(L, T0_, M_, tip_, yaw) {
        // one limb onto its targets (the root frame), the hinges kept hinges; yaw: the planted hand's / foot's turn about
        // the vertical from the bind's orientation (a plant made before a turn keeps its heading); a wrist / ankle target
        // past the hinge's range is reached as far as the range allows (Tr) and the rest of the limb follows that point
        let T = T0_, M = M_, tip = tip_;
        const [i0, i1, i2, i3] = L.ids;
        const S0 = sk.W0p[i0], E0 = sk.W0p[i1], A0 = sk.W0p[i2];
        const L1 = E0.distanceTo(S0), L2 = A0.distanceTo(E0);
        const par = sk.par[i0];
        sk.fk(i0);
        const S = sk.Pw[i0].clone();
        const Rpar = sk.Qw[par].clone().multiply(sk.W0q[par].clone().invert());
        const u0 = A0.clone().sub(S0).normalize();
        const se = E0.clone().sub(S0);
        const pole0 = se.clone().addScaledVector(u0, -se.dot(u0));
        const tb = twoBone(S, T, L1, L2, pole0.clone().applyQuaternion(Rpar), G.hinge?.[L.kind] ?? null);
        const E = tb.E;
        if (tb.Tr.distanceToSquared(T) > 1e-18) {
            // (the reach clamped: the hand / foot slides with the wrist / ankle across the floor, flat, rather than its
            // palm tilting into the floor toward a plant it cannot reach)
            const dT = tb.Tr.clone().sub(T);
            dT.y = 0.0;
            M = M.clone().add(dT);
            if (tip) tip = tip.clone().add(dT);
        }
        T = tb.Tr;
        const n0 = new THREE.Vector3().crossVectors(E0.clone().sub(S0), A0.clone().sub(E0));
        let n1 = new THREE.Vector3().crossVectors(E.clone().sub(S), T.clone().sub(E));
        if (n1.length() < 1e-12) n1 = n0.clone().applyQuaternion(Rpar);
        const Rw = basisQ(E.clone().sub(S), n1).multiply(basisQ(E0.clone().sub(S0), n0).invert()).multiply(sk.W0q[i0]);
        const Fp = sk.Qw[par].clone().multiply(sk.Qb[i0]);
        sk.Qp[i0].copy(Fp.invert().multiply(Rw));
        sk.fk(i0);
        sk.fk(i1);
        const Fp1 = sk.Qw[i0].clone().multiply(sk.Qb[i1]);
        const xNow = X_AX.clone().applyQuaternion(Fp1);
        const want = T.clone().sub(E).normalize();
        const nn = n1.clone().normalize();
        const ang = Math.atan2(new THREE.Vector3().crossVectors(xNow, want).dot(nn), xNow.dot(want));
        sk.Qp[i1].setFromAxisAngle(nn.clone().applyQuaternion(Fp1.clone().invert()).normalize(), ang);
        sk.fk(i1);
        sk.fk(i2);
        sk.aim(i2, M.clone().sub(T));
        sk.fk(i2);
        sk.fk(i3);
        const Hy = new THREE.Quaternion().setFromAxisAngle(Y_AX, yaw || 0);
        if (!tip) {
            const Fp3 = sk.Qw[i2].clone().multiply(sk.Qb[i3]);
            sk.Qp[i3].copy(Fp3.invert().multiply(Hy.clone().multiply(sk.W0q[i3])));
            sk.fkSub(i3);
            return;
        }
        // the metapodial SQUARE (the AX10 check's palm fix): x toward the planted digits, its lateral axis the bind's
        const Fp3 = sk.Qw[i2].clone().multiply(sk.Qb[i3]);
        const xx = tip.clone().sub(M).normalize();
        const zb = Z_AX.clone().applyQuaternion(Hy.clone().multiply(sk.W0q[i3]));
        const zz = zb.addScaledVector(xx, -zb.dot(xx)).normalize();
        const yy = new THREE.Vector3().crossVectors(zz, xx);
        const Rw3 = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(xx, yy, zz));
        sk.Qp[i3].copy(Fp3.invert().multiply(Rw3));
        sk.fk(i3);
        for (const k of L.digits) {
            const Fpd = sk.Qw[i3].clone().multiply(sk.Qb[k]);
            sk.Qp[k].copy(Fpd.invert().multiply(Hy.clone().multiply(sk.W0q[k])));
        }
        sk.fkSub(i3);
    }
    // ---------------------------------------------------------------------------------------- the poses
    const probe = { limbs: {} };
    const P = { A: new THREE.Vector3(), M: new THREE.Vector3(), tip: new THREE.Vector3(), r: new THREE.Vector3() };
    function walkPose(st) {
        // walk_pose with planted feet (the header): the trunk's sway, then each limb onto its target
        const om = Math.min(1.0, st.vw / (G.speed * TL));
        for (let k = 0; k < 7; k++) {
            sk.Qp[spineI[k]].setFromAxisAngle(Y_AX, (G.yaw / 7.0) * om * Math.sin(2.0 * Math.PI * st.c - 0.4 * k) * DEG);
        }
        for (let k = 0; k < 12; k++) {
            sk.Qp[tailI[k]].setFromAxisAngle(Y_AX, 1.5 * om * Math.sin(2.0 * Math.PI * st.c - 0.5 - 0.35 * k) * DEG);
        }
        sk.fkAll();
        const now = rootAt(st.t);
        for (const k of LIMB_ORDER) {
            const L = limbIdx[k];
            const duty = L.kind === 'fore' ? G.duty[0] : G.duty[1];
            const lift = (L.kind === 'fore' ? G.lift[0] : G.lift[1]) * KM;
            const sp0 = standPts[k];
            const off = G.phase[k] + jit[k];
            const cyc = st.c + off;
            const n = Math.floor(cyc);
            const phase = cyc - n;
            let yaw, lifted = 0.0, u;
            const pa = plantOf(k, sp0, n, off, duty, st.t);
            if (phase < duty) {
                // STANCE: the plant of this cycle (in the group's frame), carried into the root frame now
                u = phase / duty;
                relPoint(P.r.set(pa.x, sp0.M.y, pa.z), WORLD, now, P.M);
                yaw = pa.psi - now.psi;
            } else {
                // SWING: from this cycle's plant to the next one's, on an arc lifted with the step's length (a swing the
                // clock's first start finds under way begins there: from rest no foot hangs mid-step)
                const c0 = fromRest() ? cache.c[0] + off : -Infinity;
                u = n + duty < c0 ? (cyc - c0) / Math.max(n + 1 - c0, 1e-9) : (phase - duty) / (1.0 - duty);
                const pb = plantOf(k, sp0, n + 1, off, duty, st.t);
                const travel = Math.hypot(pb.x - pa.x, pb.z - pa.z);
                lifted = lift * Math.min(1.0, travel / Math.max(STRIDE, 1e-9)) * Math.sin(Math.PI * u);
                // the path: the stand spot under the body as it stands between the two plants' times (the body's own arc in
                // a turn, where the chord cut inside it and folded the outer knee; at a constant walk the chord itself,
                // walk_pose's dz = stride x duty x (u - 1/2))
                const ta = pa.T ?? st.t, tb = pb.T ?? st.t;
                const rm = rootAt(ta + (tb - ta) * u);
                const cm = Math.cos(rm.psi), sm = Math.sin(rm.psi);
                relPoint(P.r.set(rm.x + cm * sp0.M.x + sm * sp0.M.z, sp0.M.y + lifted, rm.z - sm * sp0.M.x + cm * sp0.M.z),
                    WORLD, now, P.M);
                yaw = rm.psi - now.psi;
            }
            const Hy = new THREE.Quaternion().setFromAxisAngle(Y_AX, yaw);
            P.A.copy(sp0.A).sub(sp0.M).applyQuaternion(Hy).add(P.M);
            P.tip.copy(sp0.tip).sub(sp0.M).applyQuaternion(Hy).add(P.M);
            limbIK(L, P.A, P.M, P.tip, yaw);
            probe.limbs[k] = { phase, stance: phase < duty, u, lift: lifted, target: P.M.toArray(),
                miss: sk.Pw[L.ids[2]].distanceTo(P.A) };
        }
    }
    const WORLD = { x: 0, z: 0, psi: 0 };            // (the group's frame as a root transform: relPoint's identity)
    const HORIZON = 10.0;                            // s: how far ahead a coming plant is looked for
    const fromRest = () => !(cache.fw[0] > 0);       // (the clock began still: a walk started from the stand)
    function timeOfCycleExt(c, tNow) {
        // timeOfCycle with the grid extended into the future far enough for the coming plants; null when the clock has not
        // reached c within the horizon (a creature standing still before its first step)
        const C = cache;
        while (C.c[C.c.length - 1] < c && C.t[C.t.length - 1] < tNow + HORIZON) step();
        return C.c[C.c.length - 1] < c ? null : timeOfCycle(c);
    }
    function plantOf(k, sp0, n, off, duty, tNow) {
        // limb k's plant for its cycle n (the group's frame: the metapodial joint's point and the body's heading): its stand
        // spot under the body as the body will stand at the MIDDLE of that stance (the beetle's rule, B11: a turn or a speed
        // change splits the stance's drift about the stand; at a constant walk this is walk_pose's +-stride x duty / 2);
        // a stance the clock found under way when it first started is where the foot stood
        const key = `${k}:${n}`;
        const hit = cache.plants.get(key);
        if (hit) return hit;
        let T = null;
        // (from rest: the stance the clock found under way stands where the body stood until the clock left its start)
        if (fromRest() && n - off <= cache.c[0]) T = timeOfCycleExt(cache.c[0] + 1e-9, tNow);
        else T = timeOfCycleExt(n - off + 0.5 * duty, tNow);
        const r = rootAt(T == null ? tNow : T);
        const c = Math.cos(r.psi), s = Math.sin(r.psi);
        // (A1) td: the stance's touch-down time (resetCache keeps the plants touched down by a command's time)
        const td = fromRest() && n - off <= cache.c[0] ? T0 : timeOfCycleExt(n - off, tNow);
        const p = { x: r.x + c * sp0.M.x + s * sp0.M.z, z: r.z - s * sp0.M.x + c * sp0.M.z, psi: r.psi, T, td };
        if (T != null) cache.plants.set(key, p);
        return p;
    }
    const swimQ = Array.from({ length: sk.n }, () => new THREE.Quaternion());
    function swimPose(st) {
        // swim_pose (the header), its phase the integrated wave
        const y = (s) => SW.amp * (0.15 + 0.85 * s * s) * Math.sin(2.0 * Math.PI * (s / SW.wavelength - st.th));
        let prev = 0.0;
        for (let k = 0; k < axialI.length; k++) {
            const head = Math.atan2(y(ss[k + 1]) - y(ss[k]), ss[k + 1] - ss[k]);
            // (neck_share: the share of its turn neck_0 takes, AX13's swim: "the head yawing least but not zero")
            const turn = (head - prev) * (k === 0 ? (SW.neck_share ?? 1.0) : 1.0);
            prev = head;
            const sgn = axial[k].startsWith('tail') ? 1.0 : -1.0;
            sk.Qp[axialI[k]].setFromAxisAngle(Y_AX, sgn * turn);
        }
        for (const [r, , j, i] of gillI) sk.Qp[i].copy(qLocal(6.0 + 1.5 * Math.sin(2 * Math.PI * 1.3 * st.t + r + j)));
        sk.fkAll();
        // the limbs ADPRESSED along the body in their girdle's posed frame (adpressed)
        for (const k of ['fore_L', 'fore_R', 'hind_L', 'hind_R']) {
            const L = limbIdx[k];
            const dirs = SW.adpress[L.kind];
            const mir = L.sd === 'L' ? 1.0 : -1.0;
            const par = sk.par[L.ids[0]];
            const Rpar = sk.Qw[par].clone().multiply(sk.W0q[par].clone().invert());
            const d3 = (d) => new THREE.Vector3(d[0] * mir, d[1], d[2]).applyQuaternion(Rpar);
            for (let s = 0; s < 3; s++) { sk.fk(L.ids[s]); sk.aim(L.ids[s], d3(dirs[s])); sk.fk(L.ids[s]); }
            sk.fk(L.ids[3]);
            sk.aim(L.ids[3], d3(dirs[2]));
            sk.fkSub(L.ids[3]);
        }
        for (let i = 0; i < sk.n; i++) swimQ[i].copy(sk.Qp[i]);
    }
    function idlePose(st, w) {
        // idle_pose: the gills' sway and flare, the throat's pulse with the jaw, the eyes' drift; the tail's sway at w
        const t = st.t;
        const flare = Math.pow(0.5 + 0.5 * Math.sin(2.0 * Math.PI * t / 7.0), 6);
        const sw = st.sw;
        for (const [r, sd, j, i] of gillI) {
            const ii = r - 1, kk = sd === 'L' ? 0 : 1;
            const amp = (1.5 + 0.8 * j) * (1.0 - 0.6 * flare);
            const fold = amp * Math.sin(2.0 * Math.PI * fr[ii][kk] * t - 0.55 * j + ph[ii][kk][0]) - 6.0 * flare;
            const splay = 1.5 * Math.sin(2.0 * Math.PI * 0.5 * fr[ii][kk] * t + ph[ii][kk][1]) + (j === 0 ? 3.0 * flare : 0.0);
            const qi = qLocal(fold, splay);
            // (swimming, the gills lie back with the swim's own flutter: swimQ holds it)
            if (sw > 0) qi.slerp(swimQ[i], sw);
            sk.Qp[i].copy(qi);
        }
        const pulse = 0.5 - 0.5 * Math.cos(2.0 * Math.PI * t);
        sk.Qp[sk.i('throat')].copy(qLocal(9.0 * pulse));
        sk.Qp[sk.i('jaw')].copy(qLocal(0.8 * pulse));
        if (w > 0) {
            for (let k = 0; k < 12; k++) {
                tmpQ.copy(qLocal(0, 1.2 * (k + 1) / 12.0 * Math.sin(2.0 * Math.PI * 0.18 * t - 0.25 * k)));
                sk.Qp[tailI[k]].slerp(tmpQ.premultiply(sk.Qp[tailI[k]].clone()), w);
            }
        }
        const drift = Math.sin(2.0 * Math.PI * 0.07 * t);
        for (const sd of ['L', 'R']) sk.Qp[sk.i(`eye_${sd}`)].copy(qLocal(0, 3.0 * drift));
    }
    // ---------------------------------------------------------------------------------------- the frame
    const rootBone = bones.get('root');
    const walkQ = Array.from({ length: sk.n }, () => new THREE.Quaternion());
    let lastCorr = {};
    function motion(t) {
        lastT = t;
        const st = stateAt(t);
        sk.reset();
        if (st.sw > 0) swimPose(st);
        if (st.sw < 1) {
            sk.reset();
            walkPose(st);
            for (let i = 0; i < sk.n; i++) walkQ[i].copy(sk.Qp[i]);
            if (st.sw > 0) for (let i = 0; i < sk.n; i++) sk.Qp[i].copy(walkQ[i]).slerp(swimQ[i], st.sw);
        }
        // the idles over it (the tail's sway only standing still on the floor)
        const om = Math.min(1.0, st.vw / (G.speed * TL));
        idlePose(st, (1.0 - om) * (1.0 - st.sw));
        driveLeaves(sk, leaves);
        sk.fkAll();
        // the bones: each node's rotation the bind's times the pose's
        for (let i = 0; i < sk.n; i++) sk.bone[i].quaternion.copy(sk.Qb[i]).multiply(sk.Qp[i]);
        // the root: the travel, the heading, the swim's lift off the floor
        if (rootBone) {
            rootBone.position.set(st.x, st.sw * SW.height * TL, st.z);
            rootBone.quaternion.setFromAxisAngle(Y_AX, st.psi);
        }
        // the correctives' morph weights (both primitives), the crease fade's drive
        lastCorr = correctiveWeights(sk, corr);
        applyCorrectives(lastCorr, meshes, A);
        probe.t = t; probe.root = [st.x, st.sw * SW.height * TL, st.z]; probe.psi = st.psi; probe.sw = st.sw;
        probe.v = st.v; probe.cycles = st.c; probe.mode = st.sw > 0.5 ? 'swim' : (st.vw > 1e-7 ? 'walk' : 'stand');
    }
    // a live command holds from the last update's time (the history before it stays as it was: a jump back replays it)
    const add = (c) => { cmds.push({ ...cmdAt(lastT), ...c, t: lastT }); cmds.sort((p, q) => p.t - q.t); resetCache(); };
    const controls = {
        speed(v) { add({ v, target: null }); },
        turn(w) { add({ w, target: null }); },
        swim(on = true) { add({ mode: on === 'auto' ? undefined : (on ? 'swim' : 'walk') }); },
        walkTo(x, z, o = {}) {
            // a point of the group's parent: into the group's frame through its own position, rotation and scale ((A1) a command
            // in the history like speed and turn: v and w 0 under it, the steer drives both)
            group.updateMatrix();
            const p = new THREE.Vector3(x, 0, z).applyMatrix4(group.matrix.clone().invert());
            add({ v: 0, w: 0, target: { x: p.x, z: p.z, t0: lastT, v: (o.speed ?? G.speed * TL * size) / size, r: (o.radius ?? 0.02 * TL),
                wmax: o.turn ?? 0.6 } });
        },
        pivot: PIVOT,
    };
    return {
        motion, controls, sk,
        probe: () => JSON.parse(JSON.stringify(probe)),
        correctives: () => Object.fromEntries(Object.entries(lastCorr).map(([k, v]) => [k, v[0]])),
        pose: () => sk.names.map((n, i) => [n, sk.Qp[i].toArray()]),
        mode: () => probe.mode,
    };
}

// ============================================================================================ the setup (bestiary.js)
export async function axolotlSetup(api, gltf, sp, opts = {}) {
    // the axolotl's materials (its skin and eye in place of the generic routing's), its size, the salamander motion and
    // its controls, the remix hook: called by bestiary.js create() once the api exists
    const group = api.group;
    const ex = gltf.userData?.bestiary || {};
    const A = axolotlUniforms(ex, opts);
    const so = { water: opts.water || null, envDiffuse: opts.envDiffuse || null, studioWall: opts.studioWall || null };
    const parser = gltf.parser;
    const meshes = [];
    group.traverse((o) => { if (o.isMesh) meshes.push(o); });
    const skinMeshes = [];
    for (const o of meshes) {
        const as = parser.associations?.get(o);
        const idx = as && as.meshes !== undefined ? parser.json.meshes[as.meshes].primitives[as.primitives].material : null;
        if (idx == null) continue;
        const def = parser.json.materials[idx];
        if (def?.extras?.recipe !== 'axolotl') continue;
        const src = await parser.getDependency('material', idx);
        const kind = def.extras.bestiary;
        if (kind === 'skin' && opts.crease !== false && !o.geometry.attributes.bestiaryCrease) {
            const m = creaseMask(o.geometry, o);
            if (m) o.geometry.setAttribute('bestiaryCrease', new THREE.BufferAttribute(m, 1));
        }
        const old = o.material;
        if (String(kind).includes('pearl')) {
            o.material = axolotlPearl(src, so);
            o.castShadow = false;                     // (the clear droplets cast none: axolotl_scene.js's AX13 note)
        } else {
            o.material = kind === 'eye' ? axolotlEye(src, A, so) : axolotlSkin(src, A, api.uniforms, so, o.geometry);
        }
        if (old && old !== o.material && old.dispose) old.dispose();
        o.userData.bestiaryAxolotl = kind;
        o.userData.bestiarySource = src;
        if (kind === 'skin') skinMeshes.push(o);
    }
    // THE SIZE (the beetle's rule, B11): life (sp.lifeScale) unless opts.size says 'hero' (the authored x4) or a number;
    // set, not multiplied, so a create() that already sized the group leaves it as it is
    const size = opts.size === 'hero' ? 1.0 : (typeof opts.size === 'number' ? opts.size : (sp.lifeScale ?? 1.0));
    group.scale.setScalar(size);
    // THE DRIVERS FROM THE NODES (driveFromNodes, on its own skeleton read at the bind, before anything poses it): with
    // create({ motion: 'none' }) every update re-derives the helpers, the twists and the correctives from the bones as a
    // scene, a clip or a cross posed them (opts.drive === false: never); api.axolotl.drive() runs them on demand (a scene
    // that poses bones after update, or over the motion's own pose)
    const skN = new Skel(api.bones);
    const leavesN = ex.driven_leaves || {}, corrN = ex.correctives || {};
    const drive = () => {
        const w = driveFromNodes(skN, leavesN, corrN);
        applyCorrectives(w, meshes, A);
        return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v[0]]));
    };
    const mo = opts.motion === 'none' ? null
        : salamanderMotion(api.bones, opts.seed ?? 1, group, sp, opts, ex, meshes, A);
    const autoDrive = !mo && opts.drive !== false;
    const baseUpdate = api.update;
    const out = {
        size,
        update(t) { baseUpdate(t); if (mo) mo.motion(t); else if (autoDrive) drive(); },
        speed(v) { mo?.controls.speed(v); },
        turn(w) { mo?.controls.turn(w); },
        walkTo(x, z, o) { return mo?.controls.walkTo(x, z, o); },
        swim(on = true) { mo?.controls.swim(on); },
        mode() { return mo ? mo.mode() : 'none'; },
        morph(name) { setMorph(A, name); },
        crease(on = true) { A.creaseOn.value = on ? 1.0 : 0.0; },
        gait: mo ? { probe: mo.probe, correctives: mo.correctives, pose: mo.pose } : null,
        axolotl: {
            uniforms: A, motion: mo, skins: skinMeshes,
            // the drivers from the bones as they stand now (driveFromNodes): the correctives' weights, by name
            drive,
            // remix.js apply(): the palette and the element rebuilt on the axolotl's own skin (remixAxolotl)
            remix: (block, R, lib) => remixAxolotl(api, A, so, block, R, lib),
        },
    };
    return out;
}

export function remixAxolotl(api, A, so, block, R, lib) {
    // the skins rebuilt with the remix's layers (axolotlSkin's rx), their crease attribute kept
    let n = 0;
    for (const o of api.axolotl.skins) {
        const src = o.userData.bestiarySource;
        const old = o.material;
        o.material = axolotlSkin(src, A, api.uniforms, so, o.geometry, { block, R, lib });
        if (old && old !== o.material && old.dispose) old.dispose();
        n++;
    }
    return n;
}
