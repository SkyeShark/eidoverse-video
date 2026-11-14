// beetle_cuticle.js — the STAG BEETLE's runtime materials (STAGED: work/bestiary/patches/beetle_b58_runtime.md lands this
// file verbatim as eidoverse/bestiary/runtime/beetle_cuticle.js, for bestiary.js's beetle species when the rig round adds
// it; until then the beetle scenes import it from here). three r184 WebGPU / TSL, over the forge's packs
// (forge/species/stag_beetle_skin.py; the glb's material extras name every channel):
//   map               albedo (sRGB, the exact curve)
//   normalMap         the macro bake with the micro relief composed (glTF +Y)
//   roughnessMap      ORM: R occlusion, G BASE roughness, B COAT roughness (metallicFactor 0)
//   thicknessMap      MASKS (KHR_materials_volume slot): R soft / thin, G setae, B accent, A chestnut pattern zone (0 / 1)
//   emissiveMap       DISPLAY (factor 0): R part id, G iridophore mask, B per-cell random (B7b: B wax bloom 0, A the
//                     per-cell random)
//   iridescenceMap    IRID (factor 0): R the setae's SHEEN amount, G film thickness (0..1), B coat amount (B7b: R film
//                     mask = DISPLAY G, A the sheen)
// (10-30, B8) THE PACKS' LAYOUT: the engine's image path divides a PNG's colour by its alpha where 0 < a < 255, so the forge
// moved every datum out of partial alpha (stag_beetle_skin's 'no partial alpha'; the material's extras say pack_layout
// 'b8_opaque'): DISPLAY and IRID ship as RGB. Both layouts read the same values here (B7b's film mask WAS DISPLAY's G)
//
// THE LAYERS (stag_beetle_skin's model): ONE strong specular interface, the epicuticle, as three's CLEAR COAT (F0 0.04),
// its roughness per texel by form (ORM B: polished on the high points, duller in the punctures and the dust); the base the
// pigmented cuticle under it with almost no specular of its own (specularIntensity 0.2 at ior 1.56: ~0.049 in all at
// normal incidence, inside the measured chitin's 0.046-0.062); setae and thin edges a little warm translucency (MeshSSS:
// the soft mask). THE IRIDESCENT OPTION: three's thin-film iridescence on the base specular, driven by the IRID pack's
// thickness between the family's [lo, hi] nm at its film ior, masked by the film mask and the iridophore zone; the
// albedo darkened toward the melanin backing, the coat thinned (a jewel beetle's multilayer under a thin epicuticle).
// (10-29, the look check) every pack ANISOTROPICALLY filtered: the glb's sampler is trilinear only, so a grazing view
// took a mip chosen by its footprint's long axis and the micro relief went flat there (the pronotum's punctures vanished
// at the turntable's oblique views, where M1d shows them as a fine sparkle); and where the film acts its lobe is
// POLISHED, FILM_POLISH x the coat's roughness (a jewel beetle's multilayer is mirror-smooth: at the coat's own 0.24-0.38
// the films read as brushed brass and satin paint; polished, the colour gathers in crisp highlights over the dark backing)
// (10-29, B5, the close-range round) TOKSVIG: three's GGX takes a roughness per texel but never widens it when the normal
// map is MINIFIED (getGeometryRoughness reads only the geometry normal), so a relief finer than the screen pixel averaged
// to a flat normal and left the coat's close-range gloss: the elytra read as smooth satin with round hotspots at every
// distance where M1d's microsculpture breaks the highlight. Each mip's filtered (unnormalised) normal is SHORTER by the
// relief it averaged; its length r gives the von Mises-Fisher concentration kappa = (3r - r^3) / (1 - r^2) and the
// slope variance 2 / kappa is added to alpha^2 (alpha = roughness^2) of both lobes (Toksvig; LEAN's variance term).
// Mip 0's own sub-texel spread is the bake's (b07 'nlen', folded into the ORM by stag_beetle_skin), so this adds only what
// the filtering averages. TOKSVIG_DEAD: the 8-bit codes' own length error, read as no variance (measured on B5's page 0:
// mip 0 decoded |len - 1| p50 0.00035, p95 0.0027, max 0.0035 with b08's quantize_unit; the 8-bit mips' box filter adds
// ~+-0.0025; the relief's own shortening is 1 - len p95 0.068 / 0.124 / 0.100 at mips 1 / 2 / 3)
const TOKSVIG_DEAD = 0.0035;
// (10-29, B5) the SETAE as a SHEEN: the golden hairs lie ON the epicuticle; painted into the albedo with the coat removed
// under them they read as matte cork (M3v: glossy black chitin with the gold as a sheen over it). three's Charlie sheen
// (r184 adds it AFTER the clear coat in PhysicalLightingModel.finish: on top of the coat, as the hairs are), its amount the
// IRID pack's A (the forge's coverage x SHEEN_W per zone), its colour M3v's golden pubescence brightened to a reflectance
// [E: look-dev beside M3v], its roughness a fibre layer's
const SETAE_SHEEN = [0.95, 0.66, 0.32];
const SETAE_SHEEN_ROUGH = 0.45;
// (10-30, B8; the M2c fresh eyes' finding on the crossbreed's part, the same lobe) THE SHEEN LOBE'S NaN: three r184's sheen
// visibility V_Neubelt = 1 / (4 (NdotL + NdotV - NdotL NdotV)) has no floor (its GGX term has max(EPSILON)): a fragment
// whose shading normal faces away from the eye and from a direct light (both clamped to 0: along the silhouettes, where
// the normal map tilts the normal past the limb) gives Inf, and Inf times its zero irradiance (or the zero sheen of bare
// chitin) is NaN: pure-black slivers on every outline, the MSAA resolve blackening whole edge pixels (the lights at
// intensity 0 in the comparison stills still run the BRDF). The lobe runs on the WHOLE cuticle material (useSheen:
// sheenNode !== null), so the shading normal is kept a hair on the eye's side, N.V >= SHEEN_NV_MIN, before Toksvig, the
// specular AA and the coat read it: the term stays finite and only those grazing fragments move
const SHEEN_NV_MIN = 1.0e-3;
// (10-30, B8) THE BASE LOBE'S FRESNEL (the head's back reading silver at grazing, open since B5). The model has ONE strong specular
// interface, the coat; the base under it adds its F0 and nothing more (the index contrast under the epicuticle is tiny: stag_beetle_
// skin's layer model). three r184 breaks that twice: direct light's Schlick is hard-coded f90 = 1 (PhysicalLightingModel.direct: no
// specularIntensity in it), and the environment's lobe climbs to specularF90 = the intensity, 0.2. So at grazing the base was a whole
// second lobe at roughness 0.5: a tan veil under the coat's highlight, each pale enough alone that switching off either lobe left
// the head silver (b8/out/t_head3_lobes.png: coat off AND this lobe off is black). flatBaseFresnel holds it at its F0 in both paths.
// Where the film acts nothing changes: there the lobe IS the film (its airy reflectance replaces this Schlick). The comparison
// stills, lit by the dome through the environment, do not move (L ratio 0.999, no pixel over 8 levels; b8/out); key-lit shots lose
// the veil (hero x0.95). BASE_SPEC: the intensity, BASE_IOR: the base's ior, F0 0.0096
const BASE_SPEC = 0.2;
const BASE_IOR = 1.56;
const THREE = globalThis.THREE;
const ANISOTROPY = 16;
const FILM_POLISH = 0.45;
// (10-29, B7) THE FILM LINES THE PITS. In the iridescent families the pronotum's punctures read as black pepper (the B6
// check's families sheet). The film is three's iridescence on the BASE lobe (the coat is apart), polished FILM_POLISH x
// the coat's roughness: a pit's walls tilt 20-45 deg, so that mirror-sharp lobe sends their reflection past the dome's band
// (or into the dark lens) and the pit goes black, where a real multilayer lines the puncture and its walls hand the light
// on to each other: the pit reads coloured, a little darker. Stood in for by the film's lobe BROADENING with the coat's
// deficit (the IRID pack's B: the skin's PIT_OCC takes the coat in the punctures, a quarter under dust and setae), to
// FILM_PIT_ROUGH at a full pit, so the walls gather the light round them in the film's colour
const FILM_PIT_ROUGH = 0.55;
// (10-29, B7) SPECULAR ANTI-ALIASING, the lead's call should glints still crawl once the relief is at M1d's scale: Toksvig
// widens the lobe by what the MIP FILTER averaged, but at the stations' push-ins a screen pixel still spans a texel or two
// of mip 0 whose normals differ, and a glossy lobe narrower than that spread flickers from frame to frame (the B6 check's
// station holds). Tokuyoshi & Kaplanyan's geometric specular AA on the SHADING normal: its screen-space derivatives give
// the normal's variance over the pixel footprint, SAA_SIGMA2 x (|dn/dx|^2 + |dn/dy|^2), twice which (capped at SAA_KAPPA)
// joins Toksvig's variance in alpha^2 of every lobe. (B7's films without it: the station holds crawled harder than B6's,
// the relief now resolved at mip 0 as sharp glossy facets: base pronotum-grazing hold 1079 px / frame of shimmer against
// B6's 882 and B5's 93, the emerald elytra hold 1928 against 1084: on)
const SPEC_AA = true;
const SAA_SIGMA2 = 0.15915494;
const SAA_KAPPA = 0.18;
// (10-29, the CRYSTAL BEETLE; 10-30, B8: folded in here from its private copy, so every variant takes the fixes above)
// THE GROWTH PACK on the cuticle: a variant whose crystals grow out of the chitin carries the octopus's GROWTH pack (R the
// growth's share of the texel, G its iridescence, B the emissive mask, A the pulse phase; forge/growth_overlay.py bakes
// the crystals' feet into it: the druse, the hidden texels under a crystal, the breach's cracks when they glow) in
// KHR_materials_iridescence's THICKNESS texture (src.iridescenceThicknessMap), since the beetle's iridescenceTexture holds
// its IRID pack; the material's extras name it (growth_pack). Where R holds a texel the cuticle's own terms stand aside
// (the palette tint, the iridophore film, the setae's sheen, the warm translucency, the clear coat) and the texel shades
// as the growths mesh does (bestiary.js growthMaterial: one full dielectric lobe, the family's metalness, the forge's
// baked roughness and colour); the glow is the growths' (bestiary.js displayGrowth's pulse). A glb without the pack
// builds the very material it did. (B8) The pack's A is BINARY (two pulse groups): only partial alpha is divided by the
// engine's image path (the header), and the private copy's specularIntensityNode was never read by three r184, so that
// 'one full lobe' first holds now, through flatBaseFresnel's grow

// the remix families (palette data). ONE table: the forge's stag_beetle_skin.IRID_FAMILIES, written into the glb's
// extras.bestiary.iridophore_families (useFamilies takes it from there); these defaults are the same rows. Each: the
// film's strength, IOR and thickness range (nm; the IRID pack's G picks within it per texel), the albedo's darkening
// toward the melanin backing, the coat's thinning. three's ONE thin film over the base: a high film index stands in for
// a jewel beetle's chitin / melanin stack [E: look-dev]. (10-29, the look check) jewel is the EMERALD jewel beetle, the
// n 1.9 film's higher order (338-362 nm: green face-on, turquoise then cyan-blue toward the edges, so the colour walks
// with the form); gold the golden scarab the jewel row was (214-232 nm: inside its gold, without the blue-grey tarnish
// the old 202-238's thin end laid over the elytra)
export const FAMILIES = {
    none: { strength: 0.0, ior: 1.6, thickness: [250, 650], darken: 1.0, coat: 1.0 },
    jewel: { strength: 1.0, ior: 1.9, thickness: [338, 362], darken: 0.10, coat: 0.25 },
    sapphire: { strength: 1.0, ior: 1.9, thickness: [150, 190], darken: 0.35, coat: 0.50 },
    oilslick: { strength: 0.85, ior: 1.6, thickness: [180, 700], darken: 0.60, coat: 0.80 },
    gold: { strength: 1.0, ior: 1.9, thickness: [214, 232], darken: 0.10, coat: 0.25 },
};

// the glb's own table (gltf.userData.bestiary.iridophore_families) over the defaults
export function useFamilies(table) {
    if (!table) return;
    for (const [k, f] of Object.entries(table)) {
        FAMILIES[k] = { strength: f.strength, ior: f.ior, thickness: f.thickness, darken: f.darken ?? 1.0,
                        coat: f.coat ?? 1.0 };
    }
}

export function beetleUniforms(opts = {}) {
    const f = FAMILIES[opts.family || 'none'];
    return {
        tint: THREE.uniform(new THREE.Color(opts.tint ?? 0xffffff)),
        tintPattern: THREE.uniform(new THREE.Color(opts.tintPattern ?? 0xffffff)),
        irid: THREE.uniform(opts.irid ?? f.strength),
        iridIor: THREE.uniform(f.ior),
        iridT0: THREE.uniform(f.thickness[0]),
        iridT1: THREE.uniform(f.thickness[1]),
        iridDarken: THREE.uniform(f.darken),
        iridCoat: THREE.uniform(f.coat),
        t: THREE.uniform(0.0),
        // (the crystal beetle) the growths' glow, tint, pulse and metalness: bestiary.js's growth uniforms and defaults,
        // the family's glow colour, metalness and film from opts.growth (the glb's extras.bestiary.growth: growth.py's
        // table); growthMaterial reads the same uniforms for the growths mesh
        growGlow: THREE.uniform(new THREE.Color().setRGB(...(opts.growth?.glow || [1.0, 1.0, 1.0]))),
        growGlowI: THREE.uniform(opts.growGlowI ?? 0.6),
        growRate: THREE.uniform(opts.growRate ?? 2.0),
        growFade: THREE.uniform(opts.growFade ?? 0.5),
        growTint: THREE.uniform(new THREE.Color(opts.growTint ?? 0xffffff)),
        growMetal: THREE.uniform(opts.growth?.metal ?? 0.0),
        filmIOR: THREE.uniform(opts.growth?.film_ior ?? 2.0),
        filmLo: THREE.uniform(opts.growth?.film?.[0] ?? 100.0),
        filmHi: THREE.uniform(opts.growth?.film?.[1] ?? 400.0),
    };
}

export function setFamily(U, name, strength) {
    const f = FAMILIES[name];
    if (!f) throw new Error(`[beetle] unknown iridophore family '${name}' (have: ${Object.keys(FAMILIES).join(', ')})`);
    U.irid.value = strength ?? f.strength;
    U.iridIor.value = f.ior;
    U.iridT0.value = f.thickness[0];
    U.iridT1.value = f.thickness[1];
    U.iridDarken.value = f.darken;
    U.iridCoat.value = f.coat;
}

function dataMaps(src) {
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap, src.iridescenceMap]) {
        if (t) t.colorSpace = THREE.NoColorSpace;
    }
    // (10-29) anisotropic filtering on every pack (see the header): the relief and its gloss keep reading at grazing views
    for (const t of [src.map, src.normalMap, src.roughnessMap, src.thicknessMap, src.emissiveMap, src.iridescenceMap]) {
        if (t) { t.anisotropy = ANISOTROPY; t.needsUpdate = true; }
    }
}

function growthPack(src, U, st) {
    // (the crystal beetle) the GROWTH pack (header) as bestiary.js displayGrowth reads the octopus's: { r, skinOnly,
    // emissive }, the glow R10's colour x mask^2 x intensity x a pulse whose phase is the crystal's
    const { texture, float, sin } = THREE;
    const t = src.iridescenceThicknessMap;
    t.colorSpace = THREE.NoColorSpace;
    t.anisotropy = ANISOTROPY;
    t.needsUpdate = true;
    const g = texture(t, st);
    const pulse = sin(U.t.mul(U.growRate).add(g.a.mul(6.2832))).mul(0.5).add(0.5).add(U.growFade).clamp(0.0, 1.0);
    return { r: g.r, skinOnly: float(1.0).sub(g.r), emissive: U.growGlow.mul(g.b.mul(g.b)).mul(U.growGlowI).mul(pulse) };
}

// the base lobe flat at its F0 in both light paths, the film's own lobe (irid) left as three draws it (BASE_SPEC's note, the
// header); grow (the GROWTH pack's share, or null): a growth texel is ONE FULL dielectric lobe, as the growths mesh
function flatBaseFresnel(m, irid, grow = null) {
    const { vec3, float, mix, positionViewDirection } = THREE;
    const T = THREE.TSL || THREE;
    const f0Full = Math.pow((BASE_IOR - 1.0) / (BASE_IOR + 1.0), 2.0);
    const f0 = BASE_SPEC * f0Full;
    const f90Skin = mix(float(f0), float(BASE_SPEC), irid);
    const f0Env = grow ? mix(float(f0), float(f0Full), grow) : float(f0);
    const f90Env = grow ? mix(f90Skin, float(1.0), grow) : f90Skin;
    const keep = grow ? irid.max(grow) : irid;
    m.setupSpecular = function () {           // three's own, with this F0 and F90 (it reads only the material's property)
        T.ior.assign(float(BASE_IOR));
        T.specularColor.assign(vec3(f0Env, f0Env, f0Env));
        T.specularColorBlended.assign(mix(T.specularColor, T.diffuseColor.rgb, T.metalness));
        T.specularF90.assign(f90Env);
    };
    const baseSetup = m.setupLightingModel.bind(m);
    m.setupLightingModel = (builder) => {
        const model = baseSetup(builder);
        const baseDirect = model.direct.bind(model);
        model.direct = (args, b) => {
            // each light's increment rescaled from Schlick's f0 + (1 - f0) (1 - V.H)^5 to f0 (the coat and the sheen have their
            // own accumulators: only the base lobe passes through directSpecular)
            const rl = args.reflectedLight;
            const s0 = rl.directSpecular.toVar();
            baseDirect(args, b);
            const voh = positionViewDirection.dot(positionViewDirection.add(args.lightDirection).normalize()).clamp(0.0, 1.0);
            const s5 = float(1.0).sub(voh).pow(5.0);
            const k = mix(float(f0).div(s5.mul(1.0 - f0).add(f0)), float(1.0), keep);
            rl.directSpecular.assign(s0.add(rl.directSpecular.sub(s0).mul(k)));
        };
        return model;
    };
}

export function cuticleMaterial(src, U) {
    const { texture, uv, vec3, vec4, float, mix, normalMap, positionViewDirection } = THREE;
    dataMaps(src);
    const st = uv();
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.0);
    // (10-30, B8) the packs' layout (header): the sheen and the film mask by it
    const opaque = src.userData?.pack_layout === 'b8_opaque';
    const disp = src.emissiveMap ? texture(src.emissiveMap, st) : vec4(0.0, 1.0, 0.0, 0.5);
    const ir = src.iridescenceMap ? texture(src.iridescenceMap, st)
        : (opaque ? vec4(0.5, 0.5, 1.0, 1.0) : vec4(1.0, 0.5, 1.0, 0.5));
    const filmMask = opaque ? disp.g : ir.r;
    const sheenAmt = opaque ? ir.r : ir.a;
    // (the crystal beetle) the GROWTH pack, null without it (and then every node below is the one it was)
    const gp = (src.userData?.growth_pack && src.iridescenceThicknessMap && U.growGlow) ? growthPack(src, U, st) : null;
    const m = new THREE.MeshSSSNodeMaterial();
    // the palette: the chestnut pattern zone (masks A) and the primary chitin tinted apart (remix.js's zone remaps
    // land on these two roles)
    let col = base.rgb.mul(mix(U.tint, U.tintPattern, masks.a));
    let irid = U.irid.mul(filmMask).mul(disp.g);
    if (gp) {
        // a growth texel takes the growths' tint, never the palette's, and no iridophore film (the cuticle's alone)
        col = mix(col, base.rgb.mul(U.growTint), gp.r);
        irid = irid.mul(gp.skinOnly);
    }
    col = mix(col, col.mul(U.iridDarken), irid);
    m.colorNode = col;
    const nt = texture(src.normalMap, st);
    // (10-30, B8) the shading normal kept on the eye's side (SHEEN_NV_MIN, the header): the sheen lobe's NaN
    const nrm0 = normalMap(nt);
    const nrm = nrm0.add(positionViewDirection.mul(float(SHEEN_NV_MIN).sub(nrm0.dot(positionViewDirection)).max(0.0)))
        .normalize();
    m.normalNode = nrm;
    // (10-29, B5) TOKSVIG (header): the filtered normal's length -> the relief's variance at this mip -> both lobes
    const rl = nt.rgb.mul(2.0).sub(1.0).length().add(TOKSVIG_DEAD).min(1.0);
    const r2 = rl.mul(rl);
    let varN = r2.oneMinus().mul(2.0).div(rl.mul(3.0).sub(r2.mul(rl)).max(1.0e-4)).min(0.5);
    if (SPEC_AA) {
        // (10-29, B7) the shading normal's variance over the pixel footprint (header)
        const dx = THREE.dFdx(nrm), dy = THREE.dFdy(nrm);
        varN = varN.add(dx.dot(dx).add(dy.dot(dy)).mul(2.0 * SAA_SIGMA2).min(SAA_KAPPA));
    }
    const toksvig = (r) => r.mul(r).mul(r).mul(r).add(varN).pow(0.25).min(1.0);
    // where the film acts, the base lobe it rides takes the COAT's roughness (ORM B): a jewel beetle's multilayer is as
    // smooth as its epicuticle, and on the base's own 0.55-0.6 the film's colour spread as a broad wash, a painted look
    // (10-28 restart); (10-29) polished further, FILM_POLISH x the coat's (0.11-0.17 on the elytra and head)
    // (10-29, B7) and broadened in the punctures (FILM_PIT_ROUGH, the header): the film lines the pits
    const filmR = mix(orm.b.mul(FILM_POLISH), float(FILM_PIT_ROUGH), ir.b.oneMinus().clamp(0.0, 1.0));
    m.roughnessNode = toksvig(mix(orm.g, filmR, irid));
    m.metalnessNode = float(0.0);
    m.aoNode = orm.r;
    m.ior = BASE_IOR;
    m.specularIntensity = BASE_SPEC;
    flatBaseFresnel(m, irid, gp ? gp.r : null);       // (10-30, B8) the base lobe at its F0 at every angle (the header)
    m.clearcoatNode = ir.b.mul(mix(float(1.0), U.iridCoat, irid));
    m.clearcoatRoughnessNode = toksvig(orm.b);
    // (10-29, B5) the setae's golden SHEEN over the kept coat (header)
    m.sheenNode = vec3(...SETAE_SHEEN).mul(sheenAmt);
    m.sheenRoughnessNode = float(SETAE_SHEEN_ROUGH);
    // the coat IS the epicuticle's surface: it follows the same relief (the punctures, the microsculpture, the setae);
    // three's clear coat otherwise takes the geometry normal and would gloss over every pit (10-28)
    m.clearcoatNormalNode = nrm;
    m.iridescenceNode = irid;
    m.iridescenceIORNode = U.iridIor;
    m.iridescenceThicknessNode = mix(U.iridT0, U.iridT1, ir.g);
    // a faint warm transmission through the soft / thin mask (setae, thin edges: shell 0.06-0.12, REF R9)
    m.thicknessColorNode = vec3(0.85, 0.55, 0.25).mul(masks.r.mul(0.35));
    m.thicknessDistortionNode = float(0.1);
    m.thicknessAmbientNode = float(0.0);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(4.0);
    m.thicknessScaleNode = float(2.0);
    if (gp) {
        // (the crystal beetle) a growth texel shades as the growths mesh (header): the family's metalness, one full
        // dielectric lobe at the forge's roughness (ORM G and B both hold it there: flatBaseFresnel's grow), no coat, sheen
        // or warm translucency; the glow the growths'
        m.metalnessNode = gp.r.mul(U.growMetal);
        m.clearcoatNode = ir.b.mul(mix(float(1.0), U.iridCoat, irid)).mul(gp.skinOnly);
        m.sheenNode = vec3(...SETAE_SHEEN).mul(sheenAmt).mul(gp.skinOnly);
        m.thicknessColorNode = vec3(0.85, 0.55, 0.25).mul(masks.r.mul(0.35)).mul(gp.skinOnly);
        m.emissiveNode = gp.emissive;
    }
    m.name = (src.name || 'cuticle') + '_beetle';
    return m;
}

export function compoundEyeMaterial(src, U) {
    // the compound eye: dark, glossy (its facets ~25 um are the runtime's micro-normal: BEETLE_PLAN §4.8 tier R, not
    // built this round); the coat at its baked roughness
    const { texture, uv, float, normalMap } = THREE;
    dataMaps(src);
    const st = uv();
    const m = new THREE.MeshPhysicalNodeMaterial();
    m.colorNode = texture(src.map, st).rgb;
    const nrm = normalMap(texture(src.normalMap, st));
    m.normalNode = nrm;
    m.roughnessNode = float(0.35);
    m.metalnessNode = float(0.0);
    m.ior = 1.55;
    m.specularIntensity = 0.3;
    m.clearcoatNode = float(1.0);
    m.clearcoatRoughnessNode = texture(src.roughnessMap, st).b;
    m.clearcoatNormalNode = nrm;
    m.name = 'compound_eye_beetle';
    return m;
}

export function membraneMaterial(src, U) {
    // the articular membranes (the sleeves): soft, translucent, no coat. (10-29, B5: the neck sleeve read as a smooth orange
    // disc under the head in the hero view, the shipped albedo the brightest, most saturated zone (sRGB 74, 46, 36) and a
    // strong amber transmission on top; M3v's membranes are dark red-brown) the transmission a dim red-brown glow
    const { texture, uv, vec3, float, normalMap } = THREE;
    dataMaps(src);
    const st = uv();
    const m = new THREE.MeshSSSNodeMaterial();
    m.colorNode = texture(src.map, st).rgb;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = texture(src.roughnessMap, st).g;
    m.metalnessNode = float(0.0);
    m.ior = 1.45;
    m.thicknessColorNode = vec3(0.55, 0.25, 0.12).mul(0.25);
    m.thicknessDistortionNode = float(0.15);
    m.thicknessAmbientNode = float(0.02);
    m.thicknessAttenuationNode = float(0.8);
    m.thicknessPowerNode = float(3.0);
    m.thicknessScaleNode = float(3.0);
    m.side = THREE.DoubleSide;
    m.name = 'membrane_beetle';
    return m;
}

// dispatch by the material's extras key (bestiary.js today dispatches by name: the beetle's 'compound_eye' would
// take the octopus's eye: BEETLE_PLAN §5.5's fix)
export function beetleMaterial(src, U) {
    const key = src.userData?.bestiary || 'cuticle';
    if (key === 'compound_eye') return compoundEyeMaterial(src, U);
    if (key === 'membrane') return membraneMaterial(src, U);
    return cuticleMaterial(src, U);
}
