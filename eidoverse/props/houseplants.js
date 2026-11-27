// eidoverse/props/houseplants.js — four houseplants and a watering can, each grown as it grows (the Blender edition's
// eidoblend.props.houseplants, made for the SAME SEED film's lab and kitchen), with their materials rebuilt in TSL: a
// rubber plant (Ficus elastica) in a glazed stoneware pot, a Monstera deliciosa on its coir pole in terracotta, a corn
// plant (Dracaena fragrans 'Massangeana') in a fibre-clay planter on expanded-clay pebbles, a pot of sweet basil, and a
// yellow watering can.
//
//   const HP = await import(new URL('props/houseplants.js', EIDOVERSE_DIR).href);
//   const plant = await HP.build(THREE, 'monstera');      // -> { group, parts, materials, dispose }
//   plant.group.position.set(1.0, 0, -2.0);              // it stands on y = 0 and faces +Z
//   scene.add(plant.group);
//
// SPECIES: rubber_plant (1.6 m tall in a 0.32 m pot), monstera (1.2 m on its pole in a 0.3 m pot), corn_plant (1.85 m
// in a 0.4 m planter), basil (0.25 m in a 9 cm pot), watering_can (0.41 m long, 0.26 m high), and coir_pole (the
// Monstera's moss pole and its ties alone). Metres, +Y up. The leaves are thin closed solids carrying their own data
// (_leafdata: along the blade, across it with the midrib at 0.5, which leaf, how old, the underside's age below zero;
// _leafq on the Monstera: where a point lies across its vein's field), which the leaf material reads: each species'
// green, the newest leaves paler or bronzed, the veins where the species has them, a waxy coat, a paler underside,
// light through the blade. Nothing moves (no wind). The pots, soil, bark, coir and plastic read seven CC0 sets
// (ambientCG and Poly Haven) fetched once into eidoverse/assets/cache/. Share one library between several plants:
// `const lib = await HP.library(THREE)`, then build(THREE, species, { library: lib }).
// Assets: eidoverse/assets/models/houseplants/ (one GLB per species, EXT_meshopt_compression-packed; this module
// decodes them itself). Guide: docs/props-and-sets.md ("The houseplants").

const HERE = new URL('../assets/models/houseplants/', import.meta.url);
export const SPECIES = ['rubber_plant', 'monstera', 'corn_plant', 'basil', 'watering_can', 'coir_pole'];
// the CC0 sets at their real sizes (metres a tile): [id, res, tile]
const SETS = { clay: ['Clay005', '2k', 0.4], soil: ['Ground048', '2k', 0.6], speckle: ['Granite005A', '2k', 0.35],
    prints: ['Fingerprints002', '2k', 0.2], concrete: ['Concrete017', '1k', 0.8], plastic: ['Plastic013A', '2k', 0.4],
    tile: ['floor_tiles_08', '2k', 1.525] };
// part name (the builders' prefixes) -> material key
const PARTS = [['plant_rubber_leaves', 'leaf_rubber'], ['plant_monstera_leaves', 'leaf_monstera'],
    ['plant_dracaena_leaves', 'leaf_dracaena'], ['plant_rubber_stems', 'rubber_stems'],
    ['plant_monstera_stems', 'monstera_petioles'], ['plant_dracaena_shoots', 'dracaena_shoots'],
    ['plant_dracaena_canes', 'dracaena_bark'], ['plant_monstera_pole', 'coir_pole'], ['plant_monstera_ties', 'tie_wire'],
    ['plant_rubber_soil', 'soil'], ['plant_monstera_soil', 'soil'], ['plant_dracaena_soil', 'soil'],
    ['plant_dracaena_pebbles', 'leca'], ['plant_monstera_pot', 'terracotta_pot'], ['plant_monstera_saucer', 'terracotta_saucer'],
    ['plant_rubber_pot_liner', 'nursery_pot'], ['plant_rubber_pot', 'glazed_pot'], ['plant_dracaena_pot', 'fibre_clay'],
    ['watering_can', 'watering_can'], ['basil_leaves', 'basil_leaf'], ['basil_stems', 'basil_stem'], ['basil_pot', 'basil_pot'],
    ['basil_saucer', 'basil_pot'], ['basil_compost', 'compost']];
export const keyOf = (name) => (PARTS.find(([p]) => name.replace(/\.\d+$/, '') === p) || [])[1] ?? null;
// linear colours of each species' leaves, taken down to an albedo; the rubber plant's thick leathery blade lets little
// light through
const LEAF = {
    rubber: { top: [0.010, 0.034, 0.010], young: [0.05, 0.045, 0.016], under: [0.06, 0.085, 0.04], rib: [0.20, 0.25, 0.08],
        rib_w: 0.012, trans: [0.16, 0.24, 0.03], r_top: 0.16, r_under: 0.45, coat: 0.22, through: 0.06, lat: 0.06 },
    monstera: { top: [0.016, 0.060, 0.018], young: [0.04, 0.12, 0.028], under: [0.06, 0.12, 0.045], rib: [0.15, 0.28, 0.06],
        rib_w: 0.014, trans: [0.16, 0.32, 0.04], r_top: 0.32, r_under: 0.5, coat: 0.12, through: 0.16, lat: 0.05 },
    dracaena: { top: [0.034, 0.120, 0.020], young: [0.05, 0.15, 0.025], under: [0.06, 0.12, 0.03], rib: [0.14, 0.21, 0.025],
        rib_w: 0.004, trans: [0.26, 0.38, 0.035], r_top: 0.40, r_under: 0.55, coat: 0.04, through: 0.28, lat: 0.25 },
};

// the CC0 sets the materials read, each { files, tex: { map: texture }, mean }, loaded once
export async function library(THREE) {
    const LM = await import(new URL('../layered_material.js', import.meta.url).href);
    const lib = { LM, sets: {} };
    lib.get = async (k, maps) => {
        const [id, res] = SETS[k];
        const s = lib.sets[k] ?? (lib.sets[k] = { files: (await globalThis.fetchPBR(id, { res })).files, tex: {} });
        for (const m of maps) {
            if (!s.tex[m]) s.tex[m] = await LM.loadTexture(THREE, s.files[m], { srgb: m === 'diff' });
        }
        return s.tex;
    };
    lib.dispose = () => { for (const s of Object.values(lib.sets)) for (const t of Object.values(s.tex)) t.dispose(); };
    return lib;
}

// Blender's Translucent BSDF mixed in by `through`: light from behind the blade, Lambertian through it (direct lights)
function leafMaterialClass(THREE) {
    const { normalView, float } = THREE;
    class LeafLighting extends THREE.PhysicalLightingModel {
        constructor(trans, ...flags) { super(...flags); this.trans = trans; }
        direct({ lightDirection, lightColor, reflectedLight }, builder) {
            const back = normalView.negate().dot(lightDirection).max(0.0);
            reflectedLight.directDiffuse.addAssign(this.trans.mul(back).mul(lightColor).mul(float(1.0 / Math.PI)));
            super.direct({ lightDirection, lightColor, reflectedLight }, builder);
        }
    }
    return class LeafMaterial extends THREE.MeshPhysicalNodeMaterial {
        constructor(p) { super(p); this.translucencyNode = null; }
        setupLightingModel() {
            if (!this.translucencyNode) return super.setupLightingModel();
            return new LeafLighting(this.translucencyNode, this.useClearcoat, this.useSheen, this.useIridescence,
                this.useAnisotropy, this.useTransmission, this.useDispersion);
        }
    };
}

// the materials (look.py's makers): key -> async () => material
function makers(THREE, lib, z0 = 0.0) {
    const { float, vec3, max, abs, fract, clamp, hue, normalView, smoothstep, dFdx, dFdy } = THREE;
    const K = lib.LM.kit(THREE);
    const { P, Pmm, N, sm, inv, lin, mixc, value, lum, rgb, num, noise, voronoi, boxAt, bump } = K;
    const fwidthOf = (x) => abs(dFdx(x)).add(abs(dFdy(x)));
    const LeafMaterial = leafMaterialClass(THREE);
    const ROUGH_MIN = 0.02;
    // a set's maps at its real size through a vector in metres, by box projection
    const photo = async (k, maps, vec = P) => {
        const t = await lib.get(k, maps), w = SETS[k][2], out = {};
        for (const m of maps) out[m] = boxAt(t[m], vec.mul(1.0 / w), N, 0.25);
        return out;
    };
    // HSV saturation scaled by (1 - desat), then multiplied by rgb * gain (photo.Mat.tint)
    const tint = (c, k, desat = 0.0, gain = 1.0) => {
        let col = c.rgb ?? c;
        if (desat) { const v = max(max(col.r, col.g), col.b); col = v.sub(v.sub(col).mul(1.0 - desat)); }
        return col.mul(vec3(k[0] * gain, k[1] * gain, k[2] * gain));
    };
    const done = (col, rough, { metal = 0.0, coat = null, coatRough = null, sheen = null, sheenRough = null, h = null,
        roughMin = ROUGH_MIN, Mat = THREE.MeshPhysicalNodeMaterial } = {}) => {
        const m = new Mat();
        m.colorNode = max(col, vec3(0.0));
        m.roughnessNode = typeof rough === 'number' ? float(rough) : clamp(max(rough, roughMin), 0.0, 1.0);
        m.metalnessNode = float(metal);
        if (h) m.normalNode = bump(h, normalView);
        if (coat !== null) { m.clearcoatNode = typeof coat === 'number' ? float(coat) : coat; m.clearcoatRoughnessNode = float(coatRough); }
        if (sheen !== null) { m.sheenNode = vec3(sheen); m.sheenRoughnessNode = float(sheenRough); }
        return m;
    };
    const plastic = async (base, r0, bumpM = 0.00003) => {
        const p = await photo('plastic', ['rough', 'displacement']);
        return done(rgb(base), float(r0).add(p.rough.r.sub(0.5).mul(0.15)), { h: p.displacement.r.mul(bumpM) });
    };
    const soil = async (damp = 0.3) => {
        const p = await photo('soil', ['diff', 'rough', 'displacement']);
        return done(tint(p.diff, [0.75, 0.68, 0.6], 0.2, 0.8), lin(p.rough.r, 0.0, 1.0, 0.75 - damp * 0.3, 0.95),
            { h: p.displacement.r.mul(0.004) });
    };
    const terracotta = async (saucer) => {
        const p = await photo('clay', ['diff', 'rough', 'displacement']);
        let col = tint(p.diff, [1.25, 0.62, 0.42], 0.3, 0.62);
        const Z = z0 ? Pmm.z.sub(z0) : Pmm.z;
        const lime = inv(sm(Z, 40.0, 150.0)).mul(sm(noise(P, 18.0, 4.0), 0.45, 0.7));
        if (!saucer) col = value(col, float(1.0).sub(inv(sm(Z, 20.0, 60.0)).mul(0.6).mul(0.35)));
        col = mixc(lime.mul(saucer ? 0.2 : 0.4), col, rgb([0.62, 0.58, 0.52]));
        return done(col, lin(p.rough.r, 0.0, 1.0, 0.75, 0.95), { h: p.displacement.r.mul(0.0003) });
    };
    const glazed = async (base = [0.045, 0.06, 0.08]) => {
        const sp = (await photo('speckle', ['diff'])).diff, fp = (await photo('prints', ['diff'])).diff;
        const col = value(rgb(base), lin(lum(sp), 0.3, 0.7, 0.85, 1.25));
        return done(col, float(0.22).add(sm(lum(fp), 0.15, 0.5).mul(0.12)), { coat: 0.2, coatRough: 0.15 });
    };
    const fibreClay = async () => {
        const p = await photo('concrete', ['diff', 'rough', 'displacement']);
        const col = value(rgb([0.50, 0.49, 0.46]), lin(lum(p.diff), 0.2, 0.6, 0.85, 1.12));
        return done(col, lin(p.rough.r, 0.0, 1.0, 0.65, 0.85), { h: p.displacement.r.mul(0.0004) });
    };
    const leca = async () => {
        const p = await photo('clay', ['diff', 'displacement']);
        let col = tint(p.diff, [1.1, 0.55, 0.32], 0.2, 0.55);
        col = value(col, lin(voronoi(P, 160.0), 0.0, 0.6, 0.75, 1.1));
        return done(col, 0.9, { h: p.displacement.r.mul(0.0006) });
    };
    const bark = async (base) => {
        const p = await photo('soil', ['diff', 'displacement'], P.mul(vec3(1.0, 1.0, 0.25)));
        let col = value(rgb(base), lin(lum(p.diff), 0.1, 0.5, 0.75, 1.15));
        col = value(col, lin(noise(P, 14.0, 3.0), 0.3, 0.7, 0.85, 1.1));
        return done(col, 0.8, { h: p.displacement.r.mul(0.0006) });
    };
    const coir = async () => {
        const n1 = noise(P.mul(vec3(420.0, 420.0, 30.0)), 1.0, 8.0, { rough: 0.65 });
        const n2 = noise(P.mul(vec3(160.0, 160.0, 14.0)), 1.0, 4.0);
        const p = await photo('soil', ['diff', 'displacement']);
        const h = p.displacement.r.mul(0.3).add(n1.mul(0.5)).add(n2.mul(0.4)).mul(0.004);
        const col = value(rgb([0.075, 0.045, 0.022]), lin(n1.mul(0.6).add(n2.mul(0.4)), 0.3, 0.7, 0.55, 1.5));
        return done(col, 0.95, { h, sheen: 0.5, sheenRough: 0.6 });
    };
    const stem = async (base, tip = null, rough = 0.45) => {
        let col = value(rgb(base), lin(noise(P, 20.0, 3.0), 0.3, 0.7, 0.85, 1.15));
        if (tip) col = mixc(sm(Pmm.z, tip[1], tip[2]), col, rgb(tip[0]));
        return done(col, rough);
    };
    // the leaf's own data: the colour reads it at the pixel's covered sample (centroid: never extrapolated past its
    // triangle at a multisampled edge, where the underside's flag would flip); the bump reads it at the pixel's centre
    // (its screen derivatives need the regular sample), its edges at least a pixel and a half soft (a rib's or a vein's
    // edge narrower than that steps from pixel to pixel; Blender's many samples a pixel smooth it the same way)
    const leafData = (species, forBump) => {
        const at = (name, type) => {
            const v = THREE.varying(THREE.attribute(name, type));
            return forBump ? v : v.setInterpolation('perspective', 'centroid');
        };
        const st = forBump ? (x, lo, hi) => {
            const c = num(lo).add(hi).mul(0.5), w = max(num(hi).sub(lo).mul(0.5), fwidthOf(x).mul(1.5));
            return smoothstep(c.sub(w), c.add(w), x);
        } : sm;
        const L = LEAF[species];
        const ld = at('_leafdata', 'vec4');
        const along = ld.x, across = ld.y, ident = ld.z, age = ld.w;
        const dm = abs(across.sub(0.5));
        const ribW = float(L.rib_w).mul(float(1.0).sub(along.mul(0.65)));
        const rib = inv(st(dm, ribW.mul(0.6), ribW)).mul(inv(st(along, 0.9, 1.0)));
        let veins = float(0.0), q = null;
        if (species === 'monstera') {
            q = at('_leafq', 'float');
            const vw = float(0.05).mul(float(1.0).sub(dm.mul(1.2)));
            veins = inv(st(abs(q), vw.mul(0.5), vw)).mul(st(dm, 0.02, 0.05));
            veins = max(veins, st(abs(fract(q.mul(3.0)).sub(0.5)), 0.47, 0.5).mul(L.lat));
        } else if (species === 'rubber') {
            const lat = fract(along.sub(dm.mul(0.45)).mul(34.0));
            veins = st(abs(lat.sub(0.5)), 0.46, 0.5).mul(st(dm, 0.02, 0.06)).mul(L.lat);
        } else {
            veins = st(abs(fract(across.mul(46.0)).sub(0.5)), 0.42, 0.5).mul(L.lat);
        }
        return { along, across, ident, age, dm, rib, veins, q };
    };
    const leaf = async (species) => {
        const L = LEAF[species];
        const { along, across, ident, age, dm, rib, veins, q } = leafData(species, false);
        const under = inv(sm(age, -0.6, -0.4));
        const young = inv(sm(abs(age), 0.0, 0.25));
        let col = mixc(young.mul(0.8), rgb(L.top), rgb(L.young));
        col = value(col, float(0.88).add(ident.mul(0.24)));
        col = hue(col, ident.mul(0.02).sub(0.01).mul(2 * Math.PI));          // (each leaf its own green)
        const mott = noise(P, 60.0, 3.0);
        col = value(col, lin(mott, 0.3, 0.7, 0.92, 1.08));
        if (species === 'monstera') {
            col = value(col, float(1.0).add(sm(dm, 0.05, 0.4).mul(float(0.5).sub(abs(q))).mul(0.12)));
        } else if (species === 'rubber') {
            const rim = sm(dm, 0.475, 0.5);
            col = mixc(rim.mul(float(0.25).add(young.mul(0.6))), col, rgb([0.09, 0.05, 0.02]));
        } else {
            // 'Massangeana': a broad lime-yellow band down the middle, streaked along its length; fine parallel veins
            const streak = noise(vec3(across.mul(70.0), along.mul(2.0), ident.mul(10.0)), 1.0, 2.0);
            const bw = float(0.16).add(streak.sub(0.5).mul(0.10));
            let band = inv(sm(dm, bw.sub(0.03), bw.add(0.03)));
            band = band.mul(lin(noise(vec3(across.mul(140.0), along.mul(4.0), 0.0), 1.0, 2.0), 0.3, 0.7, 0.55, 1.0));
            col = mixc(band.mul(0.85), col, rgb([0.26, 0.34, 0.04]));
        }
        col = mixc(veins.mul(0.55), col, rgb(L.rib));
        col = mixc(rib, col, rgb(L.rib));
        col = mixc(under, col, mixc(rib.mul(0.5), rgb(L.under), rgb(L.rib)));
        const rough = mixc(under, float(L.r_top).add(mott.sub(0.5).mul(0.1)), L.r_under);
        const hd = leafData(species, true);
        const h = hd.rib.negate().sub(hd.veins.mul(0.5)).mul(0.0004);
        // Blender mixes the Principled BSDF with a Translucent one by `through`
        const m = done(col.mul(1.0 - L.through), rough, { h, coat: inv(under).mul(L.coat), coatRough: 0.12, Mat: LeafMaterial });
        m.translucencyNode = mixc(veins.mul(0.5), rgb(L.trans), rgb(L.trans.map((v) => v * 1.3))).mul(L.through);
        m.side = THREE.FrontSide;
        return m;
    };
    const basilLeaf = async (base = [0.022, 0.12, 0.014], isStem = false) => {
        let col = value(rgb(base), lin(noise(P, 90.0, 2.0), 0.3, 0.7, 0.8, 1.25));
        if (!isStem) col = hue(col, lin(noise(P, 25.0, 1.0), 0.3, 0.7, 0.47, 0.53).sub(0.5).mul(2 * Math.PI));
        const through = isStem ? 0.1 : 0.22;
        const m = done(col.mul(1.0 - through), isStem ? 0.5 : 0.34, { roughMin: 0.03, Mat: LeafMaterial });
        m.translucencyNode = value(col, 1.15).mul(through);
        return m;
    };
    const basilPot = async () => {
        const p = await photo('tile', ['diff', 'rough', 'displacement']);
        return done(tint(p.diff, [1.25, 0.62, 0.38], 0.2, 1.0), lin(p.rough.r, 0.0, 1.0, 0.7, 0.9),
            { h: p.displacement.r.mul(0.0002), roughMin: 0.03 });
    };
    const compost = async () => done(value(rgb([0.045, 0.03, 0.02]), lin(noise(P, 40.0, 3.0), 0.3, 0.7, 0.65, 1.35)), 0.95,
        { roughMin: 0.03 });
    return {
        leaf_rubber: () => leaf('rubber'), leaf_monstera: () => leaf('monstera'), leaf_dracaena: () => leaf('dracaena'),
        rubber_stems: () => stem([0.06, 0.09, 0.03], [[0.16, 0.05, 0.03], z0 + 900.0, z0 + 1350.0], 0.4),
        monstera_petioles: () => stem([0.05, 0.13, 0.04], null, 0.35),
        dracaena_shoots: () => stem([0.10, 0.12, 0.04], null, 0.5),
        dracaena_bark: () => bark([0.40, 0.31, 0.21]),
        coir_pole: () => coir(),
        tie_wire: () => plastic([0.03, 0.18, 0.04], 0.3),
        soil: () => soil(),
        leca: () => leca(),
        terracotta_pot: () => terracotta(false),
        terracotta_saucer: () => terracotta(true),
        glazed_pot: () => glazed(),
        nursery_pot: () => plastic([0.025, 0.025, 0.025], 0.55),
        fibre_clay: () => fibreClay(),
        watering_can: () => plastic([0.62, 0.40, 0.01], 0.3),
        basil_leaf: () => basilLeaf(),
        basil_stem: () => basilLeaf([0.06, 0.14, 0.03], true),
        basil_pot: () => basilPot(),
        compost: () => compost(),
    };
}

// build(THREE, species, opts) -> { group, parts: { name: Mesh }, materials: { key: material }, dispose() }
//   opts.library: library(THREE) shared between plants (its textures are then disposed by its own dispose())
export async function build(THREE, species, opts = {}) {
    if (!SPECIES.includes(species)) throw new Error(`houseplants: no species ${species} (have: ${SPECIES.join(', ')})`);
    const lib = opts.library ?? await library(THREE);
    const { MeshoptDecoder } = await import('npm:three@0.184.0/addons/libs/meshopt_decoder.module.js');
    await MeshoptDecoder.ready;
    const file = species === 'coir_pole' ? 'monstera' : species;
    const bytes = await Deno.readFile(new URL(`${file}.glb`, HERE));
    const loader = new globalThis.GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    const mk = makers(THREE, lib);
    const materials = {}, parts = {}, drop = [];
    gltf.scene.traverse((o) => { if (o.isMesh) parts[o.name] = o; });
    for (const [name, o] of Object.entries(parts)) {
        const k = keyOf(name);
        if (species === 'coir_pole' && k !== 'coir_pole' && k !== 'tie_wire') { drop.push(o); continue; }
        if (!k) continue;
        if (!materials[k]) { materials[k] = await mk[k](); materials[k].name = `houseplant.${k}`; }
        o.material?.dispose?.();
        o.material = materials[k];
        o.castShadow = true;
        o.receiveShadow = true;
    }
    for (const o of drop) { o.removeFromParent(); o.geometry.dispose(); delete parts[o.name]; }
    const group = new THREE.Group();
    group.name = species;
    group.add(gltf.scene);
    return {
        group, parts, materials,
        dispose() {
            group.removeFromParent();
            for (const o of Object.values(parts)) o.geometry.dispose();
            for (const m of Object.values(materials)) m.dispose();
            if (!opts.library) lib.dispose();
        },
    };
}
