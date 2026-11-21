// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (SURFACING_DESIGN.md 4.4, 4.6; PORT_PLAN.md
// 3.5 row plant_instances.js, 8.2 row P15).
//
// The plan's spots as plants in three.js: flora-family plants through createFlora (eidoverse/vegetation_loader.js)
// and SeedThree species through SeedThree's own generators (eidoverse/seedthree_api.js makeSeedTree, the same
// checkout), each individual grown once and instanced on its spots, the level of detail chosen every frame by the
// camera's distance in a compute pass, the draws indirect.
//
//     import * as PL from './build/plants.js';
//     import * as PI from './build/plant_instances.js';
//     const spots = await PL.planPlants(t, { focus, data: sd });
//     const plants = await PI.instancePlants(spots, t, { renderer, camera, scene });   // a still shot (design 4.4)
//     world.add(plants.group);            // in the terrain's frame: three.js (x, z, -y) of Blender's (x, y, z)
//     await plants.bindSun(sunDirection); // once the sky's sun is final (the terrain's shade on the billboards)
//     plants.update(camera);              // the LOD pass (with { scene, camera } it runs on every render of that camera)
//     plants.dispose();
//
// SeedThree species (source { seedthree, dials, seeds }):
//   - one individual per seed: SeedThree's createTree (its textured materials) with the source's dials, its material
//     dials applied as SeedThree's app applies them (its headless API leaves bark and leaf tints to the app), its
//     card level (LOD2) built over branch cards SeedThree bakes (bakeBranchCards, the app's set: 512 px, three
//     exemplars, the deepest level), and its billboard baked from the full level (LOD0) by SeedThree's
//     bakeGroupToTextures at BILLBOARD_RES, framed on the plant's axis as the Blender add-on's
//     bake_impostor(centered='axis') frames it. Grown per process (the Blender edition keeps a .blend library of grown
//     plants because SeedThree's Blender build takes minutes; SeedThree's three.js build takes seconds).
//   - a still shot (instance_plants(wind=False), the default; design 4.4): per individual and level an InstancedMesh
//     per part, its matrices written every frame by the LOD pass from the spots (st_rot = yaw, st_scale = the
//     spot's scale x the individual's measured size, st_ground = z, the base `sink` x scale under the ground and
//     deeper on a slope by the drop across the foot): the full level (LOD0) on the hero_k nearest the camera within
//     hero_m (HERO_MAX trees in all, shared over the tree species; HERO_SHRUBS per shrub species), the card level
//     (LOD2) on the others within the card distance, and the billboard pair beyond it (independently of the hero
//     choice, as Blender's two Geometry Nodes groups choose). The billboard's material is an eidoverse-side copy of
//     SeedThree's card material (makeCardMaterial), changed as plant_instances.py's _still_billboard_material changes
//     Blender's: its canopy dome about each plant's own card centre, the baked detail normal turned by the plant's
//     yaw, the measured colour gain (BILLBOARD_GAIN, a tree's on its foliage only), the source's tone (TONE_DIAL) on
//     bark and foliage alike, each plant's tint, the soft cut-out (alpha to coverage) that keeps a small plant's
//     share of its pixel, and the terrain's and the crowns' shade under the sun (bindSun); it casts the sun's shadow
//     and receives none. The card and full levels keep SeedThree's materials, copied per instance part: their dome
//     about each plant's own canopy centre (SeedThree's hero material reads one centre for the one tree), the
//     source's tone, and each plant's tint (1 + TINT_AMOUNT (tint - 0.5), the instance colour).
//   - the card distance (card_distance): min(billboard_m, sqrt(NEAR_TREES / (pi x the stand's density round the
//     focus))) for trees; for shrubs also the distance a plant of mean size spans 4 pixels, at most NEAR_SHRUBS.
// Flora species (source { flora, options, seeds }): per individual one still createFlora stroke (wind 0) with
// explicit placements [x, -y, s] in three.js' frame and each spot's own base height (half the foot's drop); the
// stroke draws its own yaw and colour variation per plant (flora's rule, as in Blender); the source's gain on its
// materials; flora's occupancy list reset after the plan's strokes.
//
// Where this differs from plant_instances.py, and why (each a forced deviation; the look is Blender's):
//   - A level's foliage: SeedThree's three.js levels hold their leaves and cards as InstancedMeshes, and a plant
//     instanced on many spots cannot instance an InstancedMesh, so each foliage part is merged once into one plain
//     mesh (a GPU kernel, plants/merge_instances: every leaf's matrix applied to its card's vertices, its instanced
//     numbers copied onto them): the mesh data Blender's grown plant holds. Its wind attributes ride along; a still
//     shot sets SeedThree's wind to 0 (Blender grows the plants with wind=False).
//   - The LOD choice: Blender's Geometry Nodes sort the points by their camera distance and read the hero_k-th; here
//     a compute pass counts the distances within hero_m in 4096 bins, collects the bin holding the hero_k-th and takes
//     it there exactly (the same threshold), then writes each bucket's matrices and the indirect draws' instance
//     counts. A bucket's instances are written in an order the atomics pick (the image does not depend on it).
//   - The card level's and billboard's bakes are SeedThree's three.js bakes (its branch cards and bakeGroupToTextures),
//     not its Blender add-on's: the same generators' textures by another renderer.
//   - wind=True (SeedThree's forest_group grove) is not ported: SeedThree's three.js API has no grove function (its
//     app's grove lives in its main.js); a still shot is what the design's renders use.
//   - The billboard cut-out: Blender's dithered blend takes a fraction of the 16 samples; here alpha to coverage over
//     the renderer's MSAA samples (alpha hashed without MSAA), the shadow pass cut at ALPHA_CUT.
//   - Flora: createFlora takes its placements as JavaScript arrays and loops over them itself (vegetation.js); the
//     spots' numbers it needs (base height, stroke scale) come from a GPU pass and are handed over as they are.

import * as PL from './plants.js';
import * as E from './ecotopes.js';
import { prims, lineGroups } from '../core/prims.js';

export const LIBRARY_VERSION = 2;
export const NEAR_TREES = 300;           // trees at their card level at once (design 4.4)
export const HERO_MAX = 64;              // trees at their full level in any frame, over every species (design 4.4)
export const HERO_SHRUBS = 96;           // shrubs at their full level per species
export const NEAR_SHRUBS = 4000;         // shrubs at their card level at once
export const PIXEL_ANGLE = 1.0e-3;       // radians a pixel spans (960 pixels over 55 degrees)
export const HERO_TRIANGLES = 1.5e6;     // (with wind, not ported: a species' realised full levels)
export const BILLBOARD_RES = 1024;
export const TINT_AMOUNT = 0.25;         // a plant's albedo x (1 + TINT_AMOUNT (tint - 0.5))
// the billboard matched to its source level (plant_instances.py BILLBOARD_GAIN, match_billboards.py's measurements
// with both rendered at the card distance under make_sky), keyed `species|seed|dials as Python's sorted JSON`
export const BILLBOARD_GAIN = Object.freeze({
    'sagebrush|3|{}': { gain: [0.764, 0.796, 0.872], alpha: 0.35 },
    'blackbrush|7|{"barkTint": 11847908}': { gain: [1.304, 1.283, 1.293], alpha: 0.35 },
    'blackbrush|19|{"barkTint": 11847908}': { gain: [1.311, 1.288, 1.298], alpha: 0.35 },
    'creosote|3|{}': { gain: [0.872, 0.917, 1.28], alpha: 0.35 },
    'creosote|3|{"leafColorize": 5069356, "leafTintAmount": 0.55}': { gain: [0.851, 0.881, 1.287], alpha: 0.35 },
    'blackbrush|7|{"barkTint": 11847908, "leafColorize": 5660719, "leafTintAmount": 0.45}': { gain: [1.321, 1.278, 1.42], alpha: 0.35 },
    'douglasFir|11|{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": {"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, "2": 0.42}}}': { gain: [0.728, 0.811, 1.044], alpha: 0.698 },
    'douglasFir|23|{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": {"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, "2": 0.42}}}': { gain: [0.731, 0.813, 1.05], alpha: 0.698 },
    'douglasFir|37|{"branchDensity": 78, "height": 30, "leafSize": 0.9, "leavesPerBranch": 16, "paramOverrides": {"branches": {"2": 24}, "curve": {"1": -18}, "downAngle": {"1": 106}, "length": {"1": 0.22, "2": 0.42}}}': { gain: [0.734, 0.809, 1.04], alpha: 0.698 },
    'redMaple|5|{}': { gain: [0.72, 0.705, 1.518], alpha: 0.35 },
    'redMaple|17|{}': { gain: [0.738, 0.723, 1.527], alpha: 0.35 },
    'redMaple|29|{}': { gain: [0.743, 0.73, 1.511], alpha: 0.35 },
    'redMaple|41|{}': { gain: [0.717, 0.704, 1.505], alpha: 0.35 },
    'pine|9|{"height": 20}': { gain: [0.971, 1.006, 1.346], alpha: 0.35 },
    'whiteOak|1737|{"height": 9}': { gain: [0.788, 0.72, 1.735], alpha: 0.2 },
    'whiteOak|1737|{"branchAngle": 82, "crownShape": 2, "height": 7, "leafSize": 0.35}': { gain: [0.764, 0.731, 1.648], alpha: 0.35 },
    'americanSycamore|5|{"height": 16}': { gain: [0.722, 0.679, 1.167], alpha: 0.35 },
    'sweetgum|5|{"crownShape": 1, "height": 14}': { gain: [1.004, 0.873, 1.961], alpha: 0.35 },
    'sweetgum|17|{"crownShape": 1, "height": 14}': { gain: [1.026, 0.886, 2.0], alpha: 0.35 },
});
export const ALPHA_CUT = 0.35;           // SeedThree's billboard cut-out threshold
export const ALPHA_SOFT_PX = Object.freeze([24.0, 4.0]);   // the cut-out hard at 24 pixels tall, the whole alpha at 4
export const SHADE_ALBEDO = 0.3;         // a billboard in the terrain's shadow takes this share of its light
export const CANOPY_SHADE = 0.85;        // ... below its neighbours' shadow line, this share of that shade
export const CANOPY_REACH_M = 40.0;      // how far toward the sun a neighbour's crown is looked for
export const CANOPY_NONE = -1.0e4;       // the canopy line where no crown shades the card (and before bindSun)
export const TONE_DIAL = 'eidoGain';     // a SeedThree source's eidoverse-side tone, (r, g, b) on its albedo
export const FOLIAGE_EDGE = 0.04;        // albedo green over its red and blue that counts as foliage
export const FLORA_OPTS = Object.freeze(['height', 'color', 'blades', 'daisy', 'corn', 'sunflower', 'head_scale', 'normals',
    'rough', 'specular', 'lod', 'variants', 'wind', 'sss', 'translucency']);
const CARD_RES = 512, CARD_VARIANTS = 3;  // SeedThree's app's branch-card bake (src/main.js optState)
const NB = 4096;                         // the hero threshold's distance bins
const LCAP = 1024;                       // distances collected from the bin holding the hero_k-th
const F = Object.fromEntries(PL.FIELDS.map((f, i) => [f, i]));

let THREE = null, T = null;
async function three(opts = {}) {
    if (!THREE || (opts.THREE && opts.THREE !== THREE)) {
        THREE = opts.THREE ?? globalThis.THREE ?? await import('three/webgpu');
        T = opts.TSL ?? THREE.TSL ?? await import('three/tsl');
    }
    return THREE;
}

// ------------------------------------------------------------------------------------------- the sources ---

/** A SeedThree source's dials as SeedThree grows them: the eidoverse side's tone (TONE_DIAL) left out. */
export function grownDials(dials) {
    const out = {};
    for (const [k, v] of Object.entries(dials ?? {})) if (k !== TONE_DIAL) out[k] = v;
    return out;
}

/** BILLBOARD_GAIN's entry of an individual as { gain: [r, g, b], alpha }, or null. */
export function billboardGain(species, seed, dials) {
    const e = BILLBOARD_GAIN[`${species}|${Math.trunc(Number(seed))}|${E.pyJsonSorted(dials ?? {})}`];
    if (!e) return null;
    return { gain: [...(e.gain ?? [1, 1, 1])], alpha: Number(e.alpha ?? ALPHA_CUT) };
}

/** The SeedThree checkout seedthree_api.js grows from: SEEDTHREE_DIR (a global or the environment), else a SeedThree
 * checkout beside the working directory, or in it (the bridge's own resolution). */
export function seedthreeDir() {
    const cands = [globalThis.SEEDTHREE_DIR];
    try { cands.push(Deno.env.get('SEEDTHREE_DIR')); } catch (_e) { /* no env access */ }
    cands.push(Deno.cwd() + '/../SeedThree', Deno.cwd() + '/SeedThree');
    for (const c of cands) {
        if (!c) continue;
        try {
            Deno.statSync(c + '/src/api/seedthree.js');
            return String(c).replace(/[\\/]+$/, '');
        } catch (_e) { /* the next */ }
    }
    throw new Error('[plants] no SeedThree checkout: set SEEDTHREE_DIR (seedthree_api.js resolves it the same way)');
}

let ST = null;
/** SeedThree's modules from that checkout: its API (the bridge's raw()), its bakes (impostor, branch cards), wind. */
async function seedthree() {
    if (ST) return ST;
    const dir = seedthreeDir();
    const base = 'file:///' + dir.replace(/\\/g, '/').replace(/^\/+/, '') + '/src/';
    const api = typeof globalThis.makeSeedTree?.raw === 'function' ? await globalThis.makeSeedTree.raw()
        : await import(base + 'api/seedthree.js');
    ST = { dir, api, impostor: await import(base + 'core/impostor.js'), cards: await import(base + 'core/branch-cards.js'),
        wind: await import(base + 'core/wind.js') };
    return ST;
}

// SeedThree's app applies its material dials to the built materials (src/main.js applyMaterialTweaks); its headless
// createTree builds them from the species alone. The same dials, the same way.
function applyMaterialDials(a, c) {
    if (c.leafColorize !== undefined) { a.leafTintNode?.value.set(c.leafColorize); a.clusterTintNode?.value.set(c.leafColorize); }
    if (c.leafTintAmount !== undefined) {
        if (a.leafTintAmount) a.leafTintAmount.value = c.leafTintAmount;
        if (a.clusterTintAmount) a.clusterTintAmount.value = c.leafTintAmount;
    }
    if (c.leafAlpha !== undefined) {
        for (const m of [a.leafMat, a.clusterMat]) if (m && m.alphaTest !== c.leafAlpha) { m.alphaTest = c.leafAlpha; m.needsUpdate = true; }
    }
    if (c.barkTint !== undefined) {
        if (a.barkMat?.userData?.barkTint) {
            const lin = new THREE.Color(c.barkTint).convertSRGBToLinear();
            a.barkMat.userData.barkTint.value.set(lin.r, lin.g, lin.b);
        } else a.barkMat?.color.set(c.barkTint);
    }
    if (c.barkFlat !== undefined && a.barkMat && a.barkMat.flatShading !== c.barkFlat) { a.barkMat.flatShading = c.barkFlat; a.barkMat.needsUpdate = true; }
    if (c.barkDamage !== undefined && a.barkMat?.userData?.barkDamage) a.barkMat.userData.barkDamage.value = c.barkDamage;
    if (c.frondGreenTint !== undefined) a.frondGreenTint?.value.set(c.frondGreenTint).convertSRGBToLinear();
    if (c.frondDryTint !== undefined) a.frondDryTint?.value.set(c.frondDryTint).convertSRGBToLinear();
    if (c.frondDryestTint !== undefined) a.frondDryestTint?.value.set(c.frondDryestTint).convertSRGBToLinear();
    if (c.frondDryness !== undefined && a.frondDryness) a.frondDryness.value = c.frondDryness;
    if (c.spineTint !== undefined) a.spineMat?.color.set(c.spineTint);
}

const GROWN = new Map();

/** One SeedThree individual, ready to instance (plant_instances.py grow_seedthree): { levels: { LOD0, LOD2 }, card
 * materials (a Set), centres (the foliage domes' tree-local centres: leaf, cluster, card), billboard { textures (front,
 * side: albedo, normal, rough, trans), halfW, halfH, centreY }, top_m and bottom_m (how far its full level reaches
 * above and below its base), height_m and width_m (SeedThree's whole extent), seconds }. Grown once per process. */
export async function growSeedThree(species, seed, dials, { renderer, log = null } = {}) {
    await three();
    const grown = grownDials(dials);
    const key = `${species}|${Math.trunc(Number(seed))}|${E.pyJsonSorted(grown)}`;
    if (GROWN.has(key)) return GROWN.get(key);
    const t0 = performance.now();
    const S = await seedthree();
    S.api.setWind({ strength: 0 });                       // a still shot (Blender grows them with wind=False)
    const loadTexture = async (path, o) => globalThis.loadImageTexture(await Deno.readFile(path), o || {});
    const res0 = await S.api.createTree({ species, seed: Math.trunc(Number(seed)), controls: grown, level: null, loadTexture,
        assetsDir: S.dir + '/assets' });
    const assets = res0.assets, shaped = res0.shaped;
    applyMaterialDials(assets, grown);
    // the card level over baked branch cards, as SeedThree's app bakes them (ensureBranchCards)
    let facade = null;
    const cardMats = new Set();
    if (shaped?.foliage && (shaped.foliage.leavesPerBranch ?? 1) > 0 && shaped.foliageType !== 'rosette' && renderer) {
        const maxLevel = (shaped.params.levels ?? 3) - 1;
        const set = await S.cards.bakeBranchCards(renderer, shaped, assets, { size: CARD_RES, variants: CARD_VARIANTS,
            cardLevel: maxLevel, foliageOnly: true, crossViews: !!shaped.crossedLod2Cards, noFlutter: !!shaped.crossedLod2Cards });
        if (set) {
            facade = { byLevel: new Map([[`${maxLevel}:fol`, set]]), variants: set.variants, centerUniform: set.centerUniform };
            for (const v of set.variants ?? []) for (const x of Object.values(v)) if (x?.isMaterial) cardMats.add(x);
        }
    }
    const res = facade ? S.api.generate({ species, seed: Math.trunc(Number(seed)), controls: grown, lod: { branchCards: facade },
        assets }) : res0;
    const group = res.group;
    const lv = (name) => group.levels.find((l) => (l.object.userData?.lodName ?? '') === name)?.object ?? null;
    const lod0 = lv('LOD0') ?? group.levels[0].object;
    const lod2 = lv('LOD2') ?? lod0;
    for (const o of [lod0, lod2]) { o.position.set(0, 0, 0); o.rotation.set(0, 0, 0); o.scale.set(1, 1, 1); o.visible = true; o.updateMatrixWorld(true); }
    const centres = {
        leaf: assets.leafCenter?.value?.toArray() ?? [0, 0, 0],
        cluster: assets.clusterCenter?.value?.toArray() ?? [0, 0, 0],
        card: facade?.centerUniform?.value?.toArray() ?? [0, 0, 0],
    };
    const box0 = new THREE.Box3().setFromObject(lod0);
    // the billboard: SeedThree's bake of the full level, framed on the plant's axis (the add-on's centered='axis')
    let billboard = null;
    if (renderer) {
        const halfH = ((box0.max.y - box0.min.y) / 2) * 1.03;
        const cy = (box0.max.y + box0.min.y) / 2;
        const halfW = Math.max(Math.abs(box0.min.x), Math.abs(box0.max.x), Math.abs(box0.min.z), Math.abs(box0.max.z)) * 1.03;
        const depth = 2 * halfW + 5;
        const views = [];
        for (const [name, dir] of [['front', new THREE.Vector3(0, 0, 1)], ['side', new THREE.Vector3(1, 0, 0)]]) {
            const cam = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 0.1, depth * 2);
            cam.position.set(0, cy, 0).addScaledVector(dir, depth);
            cam.lookAt(0, cy, 0);
            cam.updateMatrixWorld(true);
            views.push({ name, camera: cam });
        }
        const clone = lod0.clone(true);
        clone.visible = true;
        const baked = await S.impostor.bakeGroupToTextures(renderer, clone, views, { size: BILLBOARD_RES, dilate: 12 });
        billboard = { textures: baked, halfW, halfH, centreY: cy };
    }
    const summary = res.stats?.summary ?? {};
    const out = { species, seed: Math.trunc(Number(seed)), dials: grown, key, levels: { LOD0: lod0, LOD2: lod2 }, cardMats,
        assets, centres, billboard, top_m: box0.max.y, bottom_m: box0.min.y, height_m: Number(summary.heightMeters ?? box0.max.y),
        width_m: Number(summary.widthMeters ?? 0), seconds: +((performance.now() - t0) / 1000).toFixed(1) };
    if (log) {
        log(`[plants] SeedThree ${species} seed ${out.seed}: ${out.height_m.toFixed(1)} m tall, ${out.width_m.toFixed(1)} m wide, ` +
            `grown and baked in ${out.seconds} s`);
    }
    GROWN.set(key, out);
    return out;
}

// ------------------------------------------------------------------------------------ a level's parts ---

// a geometry's attribute as a plain float array (the merge kernel's input)
const arrOf = (a, n, size) => {
    if (!a) return new Float32Array(Math.max(n * size, 1));
    if (a.isInterleavedBufferAttribute) throw new Error('[plants] an interleaved SeedThree attribute: not expected');
    return a.array instanceof Float32Array ? a.array : Float32Array.from(a.array);
};

const PARTS = new WeakMap();

/** A level's parts as plain geometries in the level's frame: [{ geometry, material, castShadow, receiveShadow,
 * foliage }]; an InstancedMesh part merged by plants/merge_instances (its leaves' matrices applied on the GPU), a
 * plain mesh as it is (SeedThree's meshes stand at the level's origin). Made once per level. */
async function levelParts(level, R) {
    if (PARTS.has(level)) return PARTS.get(level);
    const P = prims(R);
    const parts = [];
    level.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(level.matrixWorld).invert();
    const meshes = [];
    level.traverse((o) => { if (o.isMesh && o.visible !== false) meshes.push(o); });
    for (const m of meshes) {
        const local = new THREE.Matrix4().multiplyMatrices(inv, m.matrixWorld);
        const geo = m.geometry;
        if (!m.isInstancedMesh) {
            let g = geo;
            if (!local.equals(new THREE.Matrix4())) { g = geo.clone(); g.applyMatrix4(local); }
            parts.push({ geometry: g, material: m.material, castShadow: m.castShadow, receiveShadow: m.receiveShadow, foliage: false });
            continue;
        }
        const k = m.count, nv = geo.attributes.position.count;
        if (!k || !nv) continue;
        const mats = new Float32Array(k * 16);
        const tmp = new THREE.Matrix4(), M = new THREE.Matrix4();
        // the part's own transform in each instance's matrix (an identity for SeedThree's levels: one copy then)
        if (local.equals(new THREE.Matrix4())) mats.set(m.instanceMatrix.array.subarray(0, k * 16));
        else for (let j = 0; j < k; j++) { m.getMatrixAt(j, tmp); M.multiplyMatrices(local, tmp); mats.set(M.elements, 16 * j); }
        const ga = geo.attributes;
        const lists = {
            pos: P.list(nv * 3, 'f32', arrOf(ga.position, nv, 3)), nrm: P.list(nv * 3, 'f32', arrOf(ga.normal, nv, 3)),
            uvs: P.list(nv * 2, 'f32', arrOf(ga.uv, nv, 2)), mats: P.list(k * 16, 'f32', mats),
            ith: P.list(k, 'f32', arrOf(ga.aThickness, k, 1)), iwv: P.list(k * 3, 'f32', arrOf(ga.aWindVec, k, 3)),
            iap: P.list(k * 3, 'f32', arrOf(ga.aAnchorPos, k, 3)),
        };
        const outV = P.list(k * nv * 15, 'f32');
        R.run(R.kernel('plants/merge_instances'), lists, { outV }, { uNv: nv, uCount: k * nv }, lineGroups(k * nv));
        const ni = geo.index ? geo.index.count : nv;
        const idx = P.list(Math.max(ni, 1), 'u32', geo.index ? Uint32Array.from(geo.index.array) : null);
        const outI = P.list(k * ni, 'u32');
        R.run(R.kernel('plants/merge_index'), { idx }, { outI }, { uNi: ni, uNv: nv, uIdentity: geo.index ? 0 : 1, uCount: k * ni },
            lineGroups(k * ni));
        const [V, I] = await R.readAll([outV, outI]);
        for (const f of [...Object.values(lists), outV, idx, outI]) f.destroy();
        const g = new THREE.BufferGeometry();
        const ib = new THREE.InterleavedBuffer(new Float32Array(V.buffer, V.byteOffset, k * nv * 15), 15);
        g.setAttribute('position', new THREE.InterleavedBufferAttribute(ib, 3, 0));
        g.setAttribute('normal', new THREE.InterleavedBufferAttribute(ib, 3, 3));
        g.setAttribute('uv', new THREE.InterleavedBufferAttribute(ib, 2, 6));
        g.setAttribute('aThickness', new THREE.InterleavedBufferAttribute(ib, 1, 8));
        g.setAttribute('aWindVec', new THREE.InterleavedBufferAttribute(ib, 3, 9));
        g.setAttribute('aAnchorPos', new THREE.InterleavedBufferAttribute(ib, 3, 12));
        g.setIndex(new THREE.BufferAttribute(new Uint32Array(I.buffer, I.byteOffset, k * ni), 1));
        parts.push({ geometry: g, material: m.material, castShadow: m.castShadow, receiveShadow: m.receiveShadow, foliage: true });
    }
    PARTS.set(level, parts);
    return parts;
}

// a geometry of its own (its own indirect draw) over another's attributes and index (no copy)
function sharedGeometry(src) {
    const g = new THREE.BufferGeometry();
    for (const [k, a] of Object.entries(src.attributes)) g.setAttribute(k, a);
    if (!src.index) throw new Error('[plants] a SeedThree part without an index: not expected');
    g.setIndex(src.index);
    return g;
}

// ---------------------------------------------------------------------------------------- the materials ---

const tone3 = (tone) => (tone ?? [1, 1, 1]).map(Number);
const isOne = (g) => g.every((v) => Math.abs(v - 1.0) < 1e-12);

/** A SeedThree part's material for the card and full levels of a still shot (plant_instances.py _tinted_material):
 * SeedThree's own, with the canopy dome about each instance's own centre (a foliage part), the source's tone on its
 * albedo and backlight, and each instance's tint through the instance colour. */
function tintedMaterial(src, { foliage, centre, mats, cap, tone, card }) {
    const m = src.clone();
    m.userData = { ...src.userData, eidoTintOf: src.name || src.uuid };
    const g = tone3(tone);
    if (foliage) {
        const M = T.storage(mats, 'mat4', Math.max(cap, 1)).element(T.instanceIndex);
        const origin = T.varying(T.modelWorldMatrix.mul(M.mul(T.vec4(centre[0], centre[1], centre[2], 1.0))).xyz);
        if (card) {
            // SeedThree's branch-card material (branch-cards.js makeCardMaterial), its centre the instance's
            const base = T.positionWorld.sub(origin).normalize().add(T.vec3(0, 0.45, 0));
            const detail = src.normalMap ? T.texture(src.normalMap).xyz.mul(2).sub(1) : T.vec3(0, 0, 0);
            const nWorld = base.add(detail.mul(0.45)).normalize();
            m.normalNode = T.cameraViewMatrix.mul(T.vec4(nWorld, 0)).xyz.normalize();
        } else {
            // SeedThree's foliage material (leaf-cards.js makeFoliageMaterial), its centre the instance's
            const domeWorld = T.normalize(T.positionWorld.sub(origin)).add(T.vec3(0, 0.45, 0));
            const domeView = T.cameraViewMatrix.mul(T.vec4(domeWorld, 0)).xyz.normalize();
            const relief = src.normalMap ? T.normalMap(T.texture(src.normalMap)).sub(T.normalView) : T.float(0);
            m.normalNode = T.normalize(domeView.add(relief.mul(0.9)));
        }
    }
    if (!isOne(g)) {
        const tv = T.vec3(g[0], g[1], g[2]);
        if (src.colorNode) {
            const c = T.vec4(src.colorNode);
            m.colorNode = T.vec4(c.rgb.mul(tv), c.a);
        } else m.color = src.color.clone().multiply(new THREE.Color().setRGB(g[0], g[1], g[2]));
        if (src.thicknessColorNode) m.thicknessColorNode = T.vec3(src.thicknessColorNode).mul(tv);
    }
    return m;
}

/** The still billboard's material (plant_instances.py _still_billboard_material over SeedThree's impostor card
 * material, impostor.js makeCardMaterial): the baked albedo, roughness and translucency, the canopy dome about each
 * plant's card centre with the baked detail normal turned by its yaw, the gain (a tree's on its foliage only), the
 * tone, the tint, the terrain's and the crowns' shade, the soft cut-out. extras: per instance (height, yaw, shade,
 * canopy line over the card's centre). */
function billboardMaterial(tex, { mats, extras, cap, cardH, centreY, gain, alpha, foliage, tone, transmit, samples }) {
    const mat = new THREE.MeshSSSNodeMaterial({ map: tex.albedo, roughnessMap: tex.rough, side: THREE.DoubleSide, roughness: 1.0,
        metalness: 0.0 });
    const M = T.storage(mats, 'mat4', Math.max(cap, 1)).element(T.instanceIndex);
    const X = T.varying(T.storage(extras, 'vec4', Math.max(cap, 1)).element(T.instanceIndex));
    const origin = T.varying(T.modelWorldMatrix.mul(M.mul(T.vec4(0, centreY, 0, 1.0))).xyz);
    // the dome (SeedThree's: dropped 0.55 x the card's height below its centre, up-biased), the detail turned by yaw
    const dome = T.positionWorld.sub(origin).add(T.vec3(0, cardH * 0.55, 0)).normalize().add(T.vec3(0, 0.45, 0)).normalize();
    const d0 = T.texture(tex.normal).xyz.mul(2).sub(1);
    const cy = T.cos(X.y), sy = T.sin(X.y);
    const dYaw = T.vec3(d0.x.mul(cy).add(d0.z.mul(sy)), d0.y, d0.x.negate().mul(sy).add(d0.z.mul(cy)));
    const detail = T.modelWorldMatrix.mul(T.vec4(dYaw, 0)).xyz;
    const nWorld = dome.add(detail.mul(0.55)).normalize();
    mat.normalNode = T.cameraViewMatrix.mul(T.vec4(nWorld, 0)).xyz.normalize();
    // albedo x gain (a tree's where its bake is green: its green over its red and blue, 0 to FOLIAGE_EDGE) x tone
    const alb = T.texture(tex.albedo);
    const g = gain.map(Number), tn = tone3(tone);
    let rgb = alb.rgb;
    if (foliage && !isOne(g)) {
        const f = T.clamp(alb.g.sub(T.max(alb.r, alb.b)).div(FOLIAGE_EDGE), 0.0, 1.0);
        rgb = rgb.mul(T.vec3(g[0] - 1, g[1] - 1, g[2] - 1).mul(f).add(1.0));
        if (!isOne(tn)) rgb = rgb.mul(T.vec3(tn[0], tn[1], tn[2]));
    } else {
        rgb = rgb.mul(T.vec3(g[0] * tn[0], g[1] * tn[1], g[2] * tn[2]));
    }
    // the shade: the terrain's (X.z) or the crowns' toward the sun below their line over the card's centre (X.w),
    // the deeper, as SHADE_ALBEDO of the light
    const up = T.positionWorld.y.sub(origin.y);
    const ex = X.w.sub(up);
    const s = T.clamp(ex.add(1.0).div(2.5), 0.0, 1.0);
    const deep = T.max(X.z, s.mul(s).mul(T.float(3.0).sub(s.mul(2.0))).mul(CANOPY_SHADE));
    const lit = deep.mul(SHADE_ALBEDO - 1.0).add(1.0);
    mat.colorNode = T.vec4(rgb.mul(lit), 1.0);
    const tr = transmit ?? [0.42, 0.62, 0.24];
    const gt = [g[0] * tn[0], g[1] * tn[1], g[2] * tn[2]];
    mat.thicknessColorNode = T.texture(tex.trans).r.mul(0.7).mul(T.vec3(tr[0] * gt[0], tr[1] * gt[1], tr[2] * gt[2])).mul(lit);
    mat.thicknessDistortionNode = T.float(0.0);
    mat.thicknessAmbientNode = T.float(0.16);
    mat.thicknessAttenuationNode = T.float(1.0);
    mat.thicknessPowerNode = T.float(6.0);
    mat.thicknessScaleNode = T.float(0.0);
    // the soft cut: (alpha - cut) / w + cut, clamped, w from 0.02 (the plant 24 pixels tall or more) to 1 (4 pixels)
    const cut = Number(alpha ?? ALPHA_CUT);
    const per = T.positionView.length().div(T.max(X.x, 1e-3));
    const lo = 1.0 / (ALPHA_SOFT_PX[0] * PIXEL_ANGLE), hi = 1.0 / (ALPHA_SOFT_PX[1] * PIXEL_ANGLE);
    const tw = T.clamp(per.sub(lo).div(hi - lo), 0.0, 1.0);
    const w = tw.mul(tw).mul(T.float(3.0).sub(tw.mul(2.0))).mul(0.98).add(0.02);
    mat.opacityNode = T.clamp(alb.a.sub(cut).div(w).add(cut), 0.0, 1.0);
    if (samples > 1) mat.alphaToCoverage = true;
    else mat.alphaHash = true;
    mat.maskShadowNode = alb.a.greaterThan(cut);
    mat.mrtNode = T.mrt({ output: T.output, normal: T.normalView, aomask: T.float(0) });
    mat.userData.eidoBillboard = { gain: g, alpha: cut, foliage: !!foliage, tone: tn };
    return mat;
}

// ------------------------------------------------------------------------------------------ the LOD pass ---

/** plant_instances.py card_distance: (metres, plants per m^2 round the focus), on the GPU. */
export async function cardDistance(entry, rec, focus, lod, R) {
    const n = rec.length / 12;
    const nearR = Math.max(2.0 * Math.min(Number(lod.billboard_m), 150.0), 60.0);
    let m = Number(lod.billboard_m);
    if (!n) return [m, 0.0];
    const P = prims(R);
    const fa = new Float32Array(4 * focus.length);
    focus.forEach((p, k) => fa.set([...PL.splitCoord(p[0]), ...PL.splitCoord(p[1])], 4 * k));
    const foc = P.list(fa.length, 'f32', fa), recs = P.list(n * 12, 'f32', rec);
    const outF = P.list(n, 'u32'), outS = P.list(n, 'f32');
    R.run(R.kernel('plants/near_count'), { foc, rec: recs }, { outF, outS }, { uR: nearR, uCount: n, uFocusN: focus.length },
        lineGroups(n));
    const cnt = (await P.statsU32(outF, { count: n })).nonzero;
    const dens = cnt / (Math.PI * nearR * nearR);
    let cap = NEAR_TREES;
    if (entry.kind !== 'tree') {
        const meanH = Number(entry.size_m[1]) * (await P.stats(outS, { count: n })).mean;
        m = Math.min(m, meanH / (4.0 * PIXEL_ANGLE));
        cap = NEAR_SHRUBS;
    }
    for (const f of [foc, recs, outF, outS]) f.destroy();
    if (dens > 0.0) m = Math.min(m, Math.sqrt(cap / (Math.PI * dens)));
    return [m, dens];
}

/** The per-frame LOD of one SeedThree species: the compute nodes (reset, distances, the hero threshold, one scatter
 * per bucket, the indirect counts) over the spots on the renderer's device. */
function lodPasses({ recAttr, n, V, k, centre, sink, foot, sizeH, heroM, heroK, cardM, buckets, partBucket, indAttr, sunAttr }) {
    const S = T;
    const NBK = buckets.length;
    const recs = S.storage(recAttr, 'float', n * 12);
    const distA = new THREE.StorageBufferAttribute(new Float32Array(Math.max(n, 1)), 1);
    const histA = new THREE.StorageBufferAttribute(new Uint32Array(NB), 1);
    const selA = new THREE.StorageBufferAttribute(new Uint32Array(4), 1);
    const lstA = new THREE.StorageBufferAttribute(new Float32Array(LCAP), 1);
    const lcntA = new THREE.StorageBufferAttribute(new Uint32Array(1), 1);
    const rkA = new THREE.StorageBufferAttribute(new Float32Array(1), 1);
    const cntA = new THREE.StorageBufferAttribute(new Uint32Array(Math.max(NBK, 1)), 1);
    const pbA = new THREE.StorageBufferAttribute(Uint32Array.from(partBucket.length ? partBucket : [0]), 1);
    const dist = S.storage(distA, 'float', Math.max(n, 1));
    const hist = S.storage(histA, 'uint', NB).toAtomic();
    const sel = S.storage(selA, 'uint', 4);
    const lst = S.storage(lstA, 'float', LCAP);
    const lcnt = S.storage(lcntA, 'uint', 1).toAtomic();
    const rk = S.storage(rkA, 'float', 1);
    const cnt = S.storage(cntA, 'uint', Math.max(NBK, 1)).toAtomic();
    const pb = S.storage(pbA, 'uint', Math.max(partBucket.length, 1));
    const ind = S.storage(indAttr, 'uint', Math.max(partBucket.length, 1) * 5);
    const sun = S.storage(sunAttr, 'vec2', Math.max(n, 1));
    const uCam = S.uniform(new THREE.Vector3());
    const uHeroM = S.uniform(Number(heroM)), uHeroK = S.uniform(Number(heroK)), uCardM = S.uniform(Number(cardM));
    const kU = k.map((v) => Number(v));
    void centre;                                          // (the billboard's centre rides in its material)
    // a spot's base (_base_z) and three.js position
    const basePos = (o) => {
        const x = recs.element(o), y = recs.element(o.add(1)), z = recs.element(o.add(2)), sc = recs.element(o.add(4));
        const nx = recs.element(o.add(7)), ny = recs.element(o.add(8)), nz = recs.element(o.add(9));
        const tn = S.sqrt(nx.mul(nx).add(ny.mul(ny))).div(S.max(nz, 0.2));
        const zb = z.sub(sc.mul(S.float(Number(sink)).add(S.float(Number(foot)).mul(S.min(tn, 2.0)))));
        return { x, y, zb, sc };
    };
    const reset = S.Fn(() => {
        const i = S.instanceIndex;
        S.If(i.lessThan(S.uint(NB)), () => { S.atomicStore(hist.element(i), S.uint(0)); });
        S.If(i.lessThan(S.uint(NBK)), () => { S.atomicStore(cnt.element(i), S.uint(0)); });
        S.If(i.equal(S.uint(0)), () => { S.atomicStore(lcnt.element(0), S.uint(0)); });
    })().compute(Math.max(NB, NBK), [64]);
    const binOf = (d) => S.min(S.uint(d.div(uHeroM).mul(NB)), S.uint(NB - 1));
    const prep = S.Fn(() => {
        const i = S.instanceIndex;
        S.If(i.lessThan(S.uint(n)), () => {
            const b = basePos(i.mul(12));
            const d = S.length(S.vec3(b.x, b.zb, b.y.negate()).sub(uCam));
            dist.element(i).assign(d);
            S.If(uHeroK.greaterThan(0.5).and(d.lessThanEqual(uHeroM)), () => { S.atomicAdd(hist.element(binOf(d)), S.uint(1)); });
        });
    })().compute(Math.max(n, 1), [64]);
    const find = S.Fn(() => {
        const acc = S.uint(0).toVar(), found = S.uint(NB).toVar(), need = S.uint(0).toVar();
        const kk = S.uint(uHeroK);
        S.Loop(NB, ({ i }) => {
            const c = S.atomicLoad(hist.element(i));
            S.If(found.equal(S.uint(NB)).and(acc.add(c).greaterThanEqual(kk)), () => {
                found.assign(S.uint(i));
                need.assign(kk.sub(acc));
            });
            acc.addAssign(c);
        });
        sel.element(0).assign(found);
        sel.element(1).assign(need);
        sel.element(2).assign(acc);
    })().compute(1, [1]);
    const collect = S.Fn(() => {
        const i = S.instanceIndex;
        S.If(i.lessThan(S.uint(n)), () => {
            const d = dist.element(i);
            S.If(uHeroK.greaterThan(0.5).and(d.lessThanEqual(uHeroM)).and(binOf(d).equal(sel.element(0))), () => {
                const s = S.atomicAdd(lcnt.element(0), S.uint(1));
                S.If(s.lessThan(S.uint(LCAP)), () => { lst.element(s).assign(d); });
            });
        });
    })().compute(Math.max(n, 1), [64]);
    const select = S.Fn(() => {
        const r = S.float(-1.0).toVar();
        S.If(uHeroK.greaterThan(0.5), () => {
            r.assign(uHeroM);
            S.If(sel.element(0).lessThan(S.uint(NB)), () => {
                const m = S.min(S.atomicLoad(lcnt.element(0)), S.uint(LCAP));
                const want = sel.element(1).sub(1);
                S.Loop({ start: S.uint(0), end: m, type: 'uint', condition: '<', name: 'ja' }, ({ ja }) => {
                    const v = lst.element(ja);
                    const below = S.uint(0).toVar();
                    S.Loop({ start: S.uint(0), end: m, type: 'uint', condition: '<', name: 'jb' }, ({ jb }) => {
                        const w = lst.element(jb);
                        S.If(w.lessThan(v).or(w.equal(v).and(jb.lessThan(ja))), () => { below.addAssign(1); });
                    });
                    S.If(below.equal(want), () => { r.assign(v); });
                });
            });
        });
        rk.element(0).assign(r);
    })().compute(1, [1]);
    const scatters = buckets.map((bk, bi) => S.Fn(() => {
        const i = S.instanceIndex;
        S.If(i.lessThan(S.uint(n)), () => {
            const o = i.mul(12);
            const vv = S.clamp(S.int(recs.element(o.add(10))), S.int(0), S.int(V - 1));
            S.If(vv.equal(S.int(bk.v)), () => {
                const d = dist.element(i);
                const hero = d.lessThanEqual(rk.element(0)).and(uHeroK.greaterThan(0.5));
                const pred = bk.lod === 0 ? hero : bk.lod === 1 ? d.lessThanEqual(uCardM).and(hero.not()) : d.greaterThan(uCardM);
                S.If(pred, () => {
                    const s = S.atomicAdd(cnt.element(bi), S.uint(1));
                    S.If(s.lessThan(S.uint(bk.cap)), () => {
                        const b = basePos(o);
                        const yaw = recs.element(o.add(3));
                        const sc = b.sc.mul(kU[bk.v]);
                        const cs = S.cos(yaw).mul(sc), sn = S.sin(yaw).mul(sc);
                        const mats = S.storage(bk.mats, 'mat4', bk.cap);
                        mats.element(s).assign(S.mat4(S.vec4(cs, 0, sn.negate(), 0), S.vec4(0, sc, 0, 0), S.vec4(sn, 0, cs, 0),
                            S.vec4(b.x, b.zb, b.y.negate(), 1)));
                        const tf = recs.element(o.add(6)).mul(TINT_AMOUNT).add(1.0 - 0.5 * TINT_AMOUNT);
                        S.storage(bk.cols, 'vec3', bk.cap).element(s).assign(S.vec3(tf, tf, tf));
                        if (bk.extras) {
                            const sv = sun.element(i);
                            S.storage(bk.extras, 'vec4', bk.cap).element(s).assign(S.vec4(b.sc.mul(Number(sizeH)), yaw, sv.x, sv.y));
                        }
                    });
                });
            });
        });
    })().compute(Math.max(n, 1), [64]));
    const args = S.Fn(() => {
        const p = S.instanceIndex;
        S.If(p.lessThan(S.uint(partBucket.length)), () => {
            const b = pb.element(p);
            ind.element(p.mul(5).add(1)).assign(S.atomicLoad(cnt.element(b)));
        });
    })().compute(Math.max(partBucket.length, 1), [64]);
    return { nodes: [reset, prep, find, collect, select, ...scatters, args], uCam, uHeroM, uHeroK, uCardM,
        debug: { distA, histA, selA, rkA, cntA }, dispose() { /* the attributes are freed with the renderer's */ } };
}

// --------------------------------------------------------------------------------------- the instancing ---

/** A still shot's SeedThree species (plant_instances.py _instance_seedthree_still): { objects, card_m, hero_m, pass }. */
async function instanceSeedThreeStill(entry, rec, focus, group, lod, base, ctx, heroK) {
    const src = entry.source;
    const species = src.seedthree, dials = src.dials ?? {}, seeds = src.seeds?.length ? src.seeds : [1];
    const tone = tone3(dials[TONE_DIAL]);
    const grown = grownDials(dials);
    const [cardM, dens] = await cardDistance(entry, rec, focus, lod, ctx.R);
    const heroM = Number(lod.hero_m);
    const n = rec.length / 12;
    // which individuals the spots use (a count per variant, on the GPU), grown then
    const V = seeds.length;
    const counts = await variantCounts(rec, V, ctx.R);
    const plants = [];
    for (let v = 0; v < V; v++) {
        plants.push(counts[v] > 0 ? await growSeedThree(species, seeds[v], grown, { renderer: ctx.renderer, log: ctx.log }) : null);
    }
    const k = plants.map((p) => (p ? Number(entry.size_m[1]) / p.top_m : 1.0));
    const centre = plants.map((p) => (p?.billboard ? p.billboard.centreY : 0.0));
    const recAttr = new THREE.StorageBufferAttribute(rec, 1);
    const sunData = new Float32Array(Math.max(n, 1) * 2);
    for (let i = 1; i < sunData.length; i += 2) sunData[i] = CANOPY_NONE;      // (fill: no crown's shadow until bindSun)
    const sunAttr = new THREE.StorageBufferAttribute(sunData, 2);
    const buckets = [], partBucket = [], meshes = [];
    const indParts = [];
    const tag = `${base}_${PL.filePart(entry.name)}`;
    const gains = seeds.map((sd) => billboardGain(species, sd, grown));
    const useHero = heroM > 0 && heroK > 0;
    for (let v = 0; v < V; v++) {
        const p = plants[v];
        if (!p) continue;
        const cap = counts[v];
        for (const lodI of [0, 1, 2]) {
            if (lodI === 0 && !useHero) continue;
            if (lodI === 2 && !p.billboard) continue;
            const mats = new THREE.StorageInstancedBufferAttribute(new Float32Array(cap * 16), 16);
            // the instance colour as WGSL's array<vec3<f32>> lays it out (a 16-byte stride), what three.js would pad to
            const cols = new THREE.StorageInstancedBufferAttribute(new Float32Array(cap * 4).fill(1.0), 4);
            const extras = lodI === 2 ? new THREE.StorageInstancedBufferAttribute(new Float32Array(cap * 4), 4) : null;
            const bi = buckets.length;
            buckets.push({ v, lod: lodI, cap, mats, cols, extras });
            let parts;
            if (lodI === 2) {
                const bb = p.billboard;
                const e = gains[v];
                parts = [0, 1].map((side) => {
                    const g = new THREE.PlaneGeometry(2 * bb.halfW, 2 * bb.halfH, 1, 1);
                    const L = new THREE.Matrix4().makeTranslation(0, bb.centreY, 0);
                    if (side) L.multiply(new THREE.Matrix4().makeRotationY(-Math.PI / 2));
                    g.applyMatrix4(L);
                    const tex = side ? bb.textures.side : bb.textures.front;
                    return { geometry: g, material: billboardMaterial(tex, { mats, extras, cap, cardH: 2 * bb.halfH, centreY: bb.centreY,
                        gain: e?.gain ?? [1, 1, 1], alpha: e?.alpha ?? ALPHA_CUT, foliage: entry.kind === 'tree', tone,
                        transmit: undefined, samples: ctx.samples }), castShadow: true, receiveShadow: false, billboard: true };
                });
            } else {
                const level = lodI === 0 ? p.levels.LOD0 : p.levels.LOD2;
                const src = await levelParts(level, ctx.R);
                parts = src.map((q) => {
                    const card = p.cardMats.has(q.material);
                    const which = card ? p.centres.card : q.material === p.assets.clusterMat ? p.centres.cluster : p.centres.leaf;
                    return { geometry: sharedGeometry(q.geometry), material: tintedMaterial(q.material, { foliage: q.foliage, centre: which,
                        mats, cap, tone, card }), castShadow: q.castShadow !== false, receiveShadow: q.receiveShadow !== false };
                });
            }
            for (const q of parts) {
                const pi = partBucket.length;
                partBucket.push(bi);
                indParts.push({ geometry: q.geometry, ic: q.geometry.index.count, pi });
                // made for one instance, then given the bucket's matrices: InstancedMesh fills its own with identities
                const mesh = new THREE.InstancedMesh(q.geometry, q.material, 1);
                mesh.instanceMatrix = mats;
                mesh.instanceColor = cols;
                mesh.count = Math.max(cap, 1);
                mesh.frustumCulled = false;
                mesh.castShadow = q.castShadow;
                mesh.receiveShadow = q.receiveShadow;
                mesh.name = `${tag}_v${v}_${['full', 'cards', 'billboard'][lodI]}`;
                mesh.userData.noSupportCheck = mesh.userData.noClippingCheck = mesh.userData.noCameraCollide = true;
                mesh.userData.noMotionCheck = mesh.userData.noWalkable = true;
                mesh.userData.allowIntersect = true;
                meshes.push(mesh);
                group.add(mesh);
            }
        }
    }
    // the indirect draws: per part [index count, instances, first index, base vertex, first instance]
    const ind = new Uint32Array(Math.max(indParts.length, 1) * 5);
    for (const q of indParts) ind[5 * q.pi] = q.ic;
    const indAttr = new THREE.IndirectStorageBufferAttribute(ind, 5);
    for (const q of indParts) q.geometry.setIndirect(indAttr, 20 * q.pi);
    const pass = lodPasses({ recAttr, n, V, k, centre, sink: Number(entry.sink), foot: Number(entry.foot_m), sizeH: Number(entry.size_m[1]),
        heroM: useHero ? heroM : 0.0, heroK: useHero ? heroK : 0, cardM, buckets, partBucket, indAttr, sunAttr });
    for (const m of meshes) {
        m.userData.eidoPlants = { species: entry.name, source: src, billboard_m: +cardM.toFixed(1), hero_m: +heroM.toFixed(1),
            hero_k: heroK, still: true, matched: gains.map((e) => (e ? { gain: e.gain, alpha: e.alpha } : null)) };
    }
    if (ctx.log) {
        ctx.log(`[plants] ${entry.name}: ${n.toLocaleString('en-US')} spots of SeedThree ${species} x${seeds.length}, still: full ` +
            `level on the nearest ${heroK} within ${heroM.toFixed(0)} m of the camera, cards within ${cardM.toFixed(0)} m ` +
            `(${(dens * 1e4).toFixed(0)} per ha there), billboards beyond` +
            (gains.every(Boolean) ? '' : ` (${gains.filter((g) => !g).length} of ${gains.length} without a measured gain)`));
    }
    return { objects: meshes, card_m: cardM, hero_m: heroM, hero_k: heroK, pass, recAttr, sunAttr, rec, n, plants, k, centre,
        entry, buckets };
}

// per variant its spots' count (np.clip(variant, 0, V - 1) == v), on the GPU
async function variantCounts(rec, V, R) {
    const n = rec.length / 12;
    const out = new Array(V).fill(0);
    if (!n) return out;
    const P = prims(R);
    const recs = P.list(n * 12, 'f32', rec), keys = P.list(n, 'u32');
    R.run(R.kernel('plants/variant_key'), { rec: recs }, { outK: keys }, { uVariants: V, uCount: n }, lineGroups(n));
    const bins = P.bincount(keys, Math.max(V, 1), { count: n });
    const c = await R.readRange(bins, 0, Math.max(V, 1));
    for (const f of [recs, keys, bins]) f.destroy();
    for (let v = 0; v < V; v++) out[v] = c[v];
    return out;
}

// the height of the plant a createFlora stroke grows for a source at scale 1 (plant_instances.py flora_height, which
// asks flora's planner; here one probe plant through createFlora itself): its geometry's top
const FLORA_HEIGHTS = new Map();
async function floraHeight(ident, seed, opts) {
    const key = JSON.stringify([ident, seed, opts ?? {}]);
    if (FLORA_HEIGHTS.has(key)) return FLORA_HEIGHTS.get(key);
    const probe = await globalThis.createFlora({ species: ident, placements: [[0, 0, 1]], seed, ...floraKw(opts), wind: 0 });
    probe.mesh.geometry.computeBoundingBox();
    let top = probe.mesh.geometry.boundingBox.max.y;
    if (probe.stemMesh) { probe.stemMesh.geometry.computeBoundingBox(); top = Math.max(top, probe.stemMesh.geometry.boundingBox.max.y); }
    probe.dispose?.();
    FLORA_HEIGHTS.set(key, top);
    return top;
}

function floraKw(opts) {
    const kw = {};
    for (const [k, v] of Object.entries(opts ?? {})) {
        if (!FLORA_OPTS.includes(k)) continue;
        kw[k === 'head_scale' ? 'headScale' : k] = v;
    }
    return kw;
}

// plant_instances.py _gained_material: a flora material's colour x gain where it reaches the diffuse and the backlight
function gainFlora(mat, gain) {
    if (!mat || !gain) return mat;
    const g = gain.map(Number), gv = T.vec3(g[0], g[1], g[2]);
    if (mat.colorNode) {
        const c = T.vec4(mat.colorNode);
        mat.colorNode = T.vec4(c.rgb.mul(gv), c.a);
    } else mat.color.multiply(new THREE.Color().setRGB(g[0], g[1], g[2]));
    if (mat.thicknessColorNode) mat.thicknessColorNode = T.vec3(mat.thicknessColorNode).mul(gv);
    mat.needsUpdate = true;
    return mat;
}

/** A flora species (plant_instances.py _instance_flora): one still createFlora stroke per individual. */
async function instanceFlora(entry, rec, group, base, ctx) {
    if (typeof globalThis.createFlora !== 'function') throw new Error('[plants] createFlora is not loaded (eidoverse/vegetation_loader.js)');
    const src = entry.source;
    const ident = src.flora ?? ('ph:' + src.ph);
    const opts = { ...(src.options ?? {}) };
    const seeds = src.seeds?.length ? src.seeds : [7];
    const n = rec.length / 12;
    const V = seeds.length;
    const h0 = [];
    for (const sd of seeds) {
        const h = ident.startsWith('ph:') ? null : await floraHeight(ident, Math.trunc(Number(sd)), opts);
        h0.push(h ?? Number(opts.natural_m ?? entry.size_m[1]));
    }
    const R = ctx.R, P = prims(R);
    const recs = P.list(n * 12, 'f32', rec);
    const h0l = P.list(V, 'f32', Float32Array.from(h0.map((h) => Number(entry.size_m[1]) / h)));
    const outP = P.list(n * 5, 'f32');
    R.run(R.kernel('plants/flora_place'), { rec: recs, h0: h0l }, { outP }, { uSink: Number(entry.sink),
        uFoot: 0.5 * Number(entry.foot_m), uVariants: V, uCount: n }, lineGroups(n));
    const pl = await R.readRange(outP, 0, n * 5);
    for (const f of [recs, h0l, outP]) f.destroy();
    // the strokes' placements, as createFlora takes them (one copy per plant: its own interface)
    const per = seeds.map(() => ({ placements: [], heights: [] }));
    for (let i = 0; i < n; i++) {
        const v = pl[5 * i + 4];
        per[v].placements.push([pl[5 * i], pl[5 * i + 1], pl[5 * i + 2]]);
        per[v].heights.push(pl[5 * i + 3]);
    }
    const out = [];
    for (let v = 0; v < V; v++) {
        const { placements, heights } = per[v];
        if (!placements.length) continue;
        let q = 0;
        // each spot's own base height, in placement order (createFlora asks heightFn once per placement, in order)
        const heightFn = (x, z) => {
            const pq = placements[q];
            const h = pq && pq[0] === x && pq[1] === z ? heights[q] : heights[placements.findIndex((p) => p[0] === x && p[1] === z)];
            q++;
            return h;
        };
        const field = await globalThis.createFlora({ species: ident, placements, heightFn, seed: Math.trunc(Number(seeds[v])),
            ...floraKw(opts), wind: 0, sunDir: ctx.sunDir ?? undefined });
        if (opts.gain) {
            gainFlora(field.material, opts.gain);
            if (field.stemMesh) gainFlora(field.stemMesh.material, opts.gain);
        }
        field.mesh.name = `${base}_${PL.filePart(entry.name)}_${v}`;
        field.mesh.userData.eidoPlants = { species: entry.name, source: src, motion: false };
        group.add(field.mesh);
        out.push(field);
    }
    if (ctx.log) {
        ctx.log(`[plants] ${entry.name}: ${n.toLocaleString('en-US')} spots of flora ${ident} x${seeds.length}, still strokes` +
            (opts.gain ? `, gain (${opts.gain.join(', ')})` : ''));
    }
    return out;
}

// ------------------------------------------------------------------------------------------------ the call ---

/** Instance a plan's spots (PlantSpots) for a still shot (plant_instances.py instance_plants(wind=False)).
 *
 *   terrain   the Terrain they were planned on (its name names the group), or null
 *   opts      renderer (required: the bakes and the LOD pass run on it), R (the terrain runner on its device; made if
 *             not given), camera and scene (the LOD pass then runs on every render of that camera), lod (overrides:
 *             { hero_m, billboard_m, near_m } for every species, or { species name: {...} }), log, sunDir
 *   returns   { group (a THREE.Group in the terrain's frame), made ({ species name: [objects] }), species (per SeedThree
 *             species its card distance, hero distance and count), update(camera), follow(scene, camera),
 *             bindSun(direction), dispose() } */
export async function instancePlants(spots, terrain = null, opts = {}) {
    await three(opts);
    const t0 = performance.now();
    const renderer = opts.renderer;
    if (!renderer) throw new Error('[plants] instancePlants needs { renderer }: the bakes and the per-frame LOD run on it');
    let R = opts.R;
    if (!R) {
        const G = await import('../core/gpu.js');
        R = await G.init({ renderer });
    }
    const log = opts.log === undefined ? console.log : opts.log;
    const name = terrain?.info?.name ?? terrain?.name ?? 'terrain';
    const base = `${name}_plants`;
    const group = new THREE.Group();
    group.name = base;
    const samples = Number(renderer.currentSamples ?? renderer.samples ?? renderer._samples ?? 0) || 1;
    const ctx = { renderer, R, log, samples, sunDir: opts.sunDir ?? null };
    const focus = spots.meta.focus.map((p) => [Number(p[0]), Number(p[1])]);
    const trees = spots.species.filter((e) => e.kind === 'tree' && e.source.seedthree !== undefined && spots.array(e.name).length);
    const treeK = Math.max(1, Math.floor(HERO_MAX / Math.max(trees.length, 1)));
    const made = {}, still = [], flora = [];
    for (const entry of spots.species) {
        const rec = spots.array(entry.name);
        if (!rec.length) { made[entry.name] = []; continue; }
        const L = { ...entry.lod };
        const over = opts.lod ?? {};
        for (const [k, v] of Object.entries(over)) if (v === null || typeof v !== 'object') L[k] = v;
        Object.assign(L, over[entry.name] ?? {});
        if (entry.source.seedthree !== undefined) {
            const kk = entry.kind === 'tree' ? treeK : HERO_SHRUBS;
            const r = await instanceSeedThreeStill(entry, rec, focus, group, L, base, ctx, kk);
            still.push(r);
            made[entry.name] = r.objects;
        } else {
            const fields = await instanceFlora(entry, rec, group, base, ctx);
            flora.push(...fields);
            made[entry.name] = fields.map((f) => f.mesh);
        }
    }
    globalThis.resetFloraOccupancy?.();
    const camLocal = new THREE.Vector3(), wp = new THREE.Vector3();
    const update = (camera) => {
        if (!camera || !still.length) return;
        camera.getWorldPosition(wp);
        group.updateWorldMatrix(true, false);
        camLocal.copy(wp);
        group.worldToLocal(camLocal);
        const nodes = [];
        for (const s of still) {
            s.pass.uCam.value.copy(camLocal);
            nodes.push(...s.pass.nodes);
        }
        renderer.compute(nodes);
    };
    const follow = (scene, camera) => {
        const prev = scene.onBeforeRender;
        scene.onBeforeRender = function (r, sc, cam, rt) {
            if (cam === camera) update(cam);
            if (typeof prev === 'function') prev.call(this, r, sc, cam, rt);
        };
    };
    if (opts.scene && opts.camera) follow(opts.scene, opts.camera);
    const out = {
        group, made, update, follow,
        species: Object.fromEntries(still.map((s) => [s.entry.name, { card_m: s.card_m, hero_m: s.hero_m, hero_k: s.hero_k, spots: s.n,
            individuals: s.plants.map((p) => (p ? { seed: p.seed, top_m: p.top_m, height_m: p.height_m, seconds: p.seconds } : null)) }])),
        _still: still, _flora: flora, seconds: 0,
        bindSun: async (dir) => bindSun(out, terrain, dir, ctx),
        dispose() {
            for (const f of flora) f.dispose?.();
            group.traverse((o) => { if (o.isInstancedMesh) { o.material?.dispose?.(); } });
            group.removeFromParent();
        },
    };
    out.seconds = +((performance.now() - t0) / 1000).toFixed(1);
    if (log) {
        log(`[plants] ${spots.names().reduce((a, nm) => a + spots.array(nm).length / 12, 0).toLocaleString('en-US')} plants of ` +
            `${spots.species.length} species instanced in ${out.seconds} s`);
    }
    return out;
}

// --------------------------------------------------------------------------------------------- the sun ---

/** plant_instances.py bind_sun: the sun the billboards are shaded under: each billboard's terrain shade (sun_shade's
 * sweep over the terrain's context and main heightfields) and the shadow line its neighbours' crowns cast on it
 * (canopy_line), on the GPU (plants/sun_shade, plants/canopy_line), into the LOD pass' per-spot numbers. dir: toward
 * the sun, three.js' frame ([x, y, z] or a Vector3). Returns the number of billboard spots shaded. */
export async function bindSun(plants, terrain, dir, ctx) {
    await three();
    const still = plants._still;
    if (!still.length) return 0;
    const R = ctx.R, P = prims(R);
    const d = Array.isArray(dir) ? dir : [dir.x, dir.y, dir.z];
    let bx = Number(d[0]), by = -Number(d[2]), bz = Number(d[1]);          // Blender's frame
    const L = Math.max(Math.hypot(bx, by, bz), 1e-9);
    bx /= L; by /= L; bz /= L;
    const hz = Math.hypot(bx, by);
    const mode = bz <= 0.0 ? 0 : hz < 1e-6 ? 2 : 1;                   // below the horizon: all shade; overhead: none
    const ux = mode === 1 ? bx / hz : 0.0, uy = mode === 1 ? by / hz : 0.0, tanEl = mode === 1 ? bz / hz : 0.0;
    const uDir = [ux, uy, tanEl, mode];
    // the terrain's sweeps (_shade_ground: its context and main levels' heights), one per level
    const sweeps = [];
    if (mode === 1) {
        (terrain?.levels ?? []).forEach((lv, i) => {
            if (String(lv.role ?? 'main') === 'hero') return;
            const n = lv.n, c = lv.side / n;
            const cx = [lv.x0, lv.x0 + lv.side, lv.x0, lv.x0 + lv.side], cy = [lv.y0, lv.y0, lv.y0 + lv.side, lv.y0 + lv.side];
            const sc = cx.map((x, k) => -(x * ux + cy[k] * uy)), wc = cx.map((x, k) => -x * uy + cy[k] * ux);
            const s0 = Math.min(...sc), w0 = Math.min(...wc);
            const ns = Math.ceil((Math.max(...sc) - s0) / c) + 1, nw = Math.ceil((Math.max(...wc) - w0) / c) + 1;
            const h = P.list(n * n, 'f32', terrain.fields(i).h);
            const pm = P.list(ns * nw, 'f32');
            R.run(R.kernel('plants/sun_sweep'), { h }, { outM: pm }, { uLv: [lv.x0, lv.y0, c, n], uDir, uGrid: [s0, w0, ns, nw] },
                lineGroups(nw));
            h.destroy();
            sweeps.push({ pm, grid: [s0, w0, ns, nw], c });
        });
    }
    // every SeedThree plant's crown (_crowns), on a hashed grid of the reach
    const nC = still.reduce((a, s) => a + s.n, 0);
    const crw = P.list(Math.max(nC, 1) * 6, 'u32');
    let first = 0;
    const lists = [];
    for (const s of still) {
        const rec = P.list(Math.max(s.n, 1) * 12, 'f32', s.rec);
        lists.push(rec);
        const e = s.entry;
        R.run(R.kernel('plants/crown_rec'), { rec }, { outC: crw }, { uS: [Number(e.size_m[1]), Number(e.crown_m ?? e.core_m), 0, 0],
            uFirst: first, uCount: s.n }, lineGroups(s.n));
        first += s.n;
    }
    let Tb = 1024;
    while (Tb < 2 * nC) Tb *= 2;
    const lv0 = terrain?.levels?.[0];
    const origin = lv0 ? [...PL.splitCoord(lv0.x0), ...PL.splitCoord(lv0.y0)] : [0, 0, 0, 0];
    const big = BigInt(Math.round(2 ** 40 / CANOPY_REACH_M));
    const gw = [Number(BigInt.asIntN(32, big >> 32n)), Number(BigInt.asIntN(32, big & 0xFFFFFFFFn))];
    const grid = { uGO: origin, uGW: gw, uGInv: Math.fround(1.0 / CANOPY_REACH_M), uGMask: Tb - 1 };
    const keys = P.list(Math.max(nC, 1), 'u32');
    R.run(R.kernel('plants/grid_key'), { rec: crw }, { outK: keys }, { ...grid, uStride: 6, uPos: 0, uCount: nC }, lineGroups(nC));
    const { keys: sk, vals: order } = P.sortPairs(keys, null, { count: nC, bits: Math.log2(Tb) });
    sk.destroy();
    const counts = P.bincount(keys, Tb, { count: nC });
    const starts = P.cumsum(counts, { count: Tb, exclusive: true });
    keys.destroy();
    let done = 0;
    for (const [si, s] of still.entries()) {
        const rec = lists[si];
        const e = s.entry;
        const vk = P.list(2 * s.k.length, 'f32', Float32Array.from(s.k.flatMap((k, v) => [k, s.centre[v]])));
        let ex = P.list(Math.max(s.n, 1), 'f32', new Float32Array(Math.max(s.n, 1)).fill(-1.0e9));
        for (const w of sweeps) {
            const ex2 = P.list(Math.max(s.n, 1), 'f32');
            R.run(R.kernel('plants/sun_sample'), { rec, vk, pm: w.pm, ex }, { outE: ex2 }, { uDir, uGrid: w.grid,
                uBase: [Number(e.sink), Number(e.foot_m), w.c, s.k.length], uCount: s.n }, lineGroups(s.n));
            ex.destroy();
            ex = ex2;
        }
        const outS = P.list(Math.max(s.n, 1) * 2, 'f32');
        R.run(R.kernel('plants/canopy_line'), { rec, vk, ex, crw, starts, counts, order }, { outS }, { ...grid, uDir,
            uBase: [Number(e.sink), Number(e.foot_m), s.k.length, CANOPY_REACH_M], uCount: s.n }, lineGroups(s.n));
        const a = await R.readRange(outS, 0, s.n * 2);
        s.sunAttr.array.set(a.subarray(0, s.n * 2));
        s.sunAttr.needsUpdate = true;
        for (const f of [vk, ex, outS]) f.destroy();
        done += s.n;
    }
    for (const f of [...lists, crw, order, counts, starts, ...sweeps.map((w) => w.pm)]) f.destroy();
    if (ctx.log) {
        ctx.log(`[plants] the terrain's and the crowns' shade on ${done.toLocaleString('en-US')} SeedThree plants' billboards ` +
            `(the sun ${(Math.asin(Math.min(1, Math.max(-1, bz))) * 180 / Math.PI).toFixed(1)} degrees up)`);
    }
    return done;
}

export { instancePlants as instance_plants, growSeedThree as grow_seedthree, billboardGain as billboard_gain,
    cardDistance as card_distance, bindSun as bind_sun, grownDials as grown_dials };
