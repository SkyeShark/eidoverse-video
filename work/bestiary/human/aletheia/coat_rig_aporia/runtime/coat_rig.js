// coat_rig.js: HER COAT WORN ON SPRING BONES, the runtime side (human/aletheia/coat_rig, 11-14, Fable 5.2). A private module
// of the coat's spring-rig round; nothing live imports it (the landing is coat_rig/STAGED.md: this file and coat_springs.js go
// to eidoverse/bestiary/runtime/, the hook into sisters.js).
//
//   const coat = await wearCoat({ gltf, parent, joint, film: { module, design, luts }, params, glow });
//   coat.update(t)       once a frame AFTER her body is posed (sisters.js: hooks.coatMotion = (t) => coat.update(t))
//   coat.group           the coat: its skinned draws + its spring joints (a child of `parent`, her group)
//   coat.springs         the solver's control (coat_springs.js): .params (live: wind, gust, air, damping ...), .stats, .helper()
//   coat.counts          joints, triangles, draws, particles, links, samples
//   coat.dump            { joints, particles, floats, write(out, at, inverse) }: every spring joint's matrix and every particle
//                        a frame, relative to her scene node (what scripts/c45_replay.py replays: the gate in motion)
//
// THE FILE IT WEARS: a rigged coat glb of scripts/c30_glb.py (out/<tag>/aletheia_coat_<mesh>_rigged_<tag>.glb, the design mesh
// or a low): ONE skin; its joints are (a) BODY-FOLLOWING joints, named exactly as her figure's joints, each stored AT HER STAND
// (the pose the coat was draped on: the inverse binds are those matrices inverted, in the rigged figure's frame: metres, y 0
// the ground under her boots) and (b) SPRING joints `coat_skirt_<L|R>_c<j>_r<k>` / `coat_sleeve_<L|R>_<k>` at their rest
// points. extras.bestiary.coat_rig.springs is the whole spring config (the grid, the links' material numbers, her colliders:
// grids of her hips and legs in the file's own buffer, capsules on her forearms, hands and tentacle roots).
// HOW IT IS WORN: the coat is ITS OWN SKINNED MESH WITH ITS OWN SKELETON (ASSEMBLY_PLAN 5; her figure's skin is full: 254 of
// 256 joints). The skeleton's body-following bones ARE HER OWN JOINT OBJECTS (found by name through opts.joint), so the top,
// collar, shoulders and sleeves move with her with no copy and no lag; the spring bones are this file's own nodes, written
// every frame by the solver in WORLD space (the skirt feels her walk through the world: it lags, swings and settles).
// MATERIALS: the coat round's own (coat_design/material/engine/coat_film.js: the film's three order-free draws T S G, the
// bound edges, the glowing piping and tubes, snaps, patch), on skinned meshes: exactly what its scene and sisters.js's WIP
// layer draw on the standing design model. A low with baked maps (stage R2) adds its maps through opts.maps.
//
// APORIA'S COAT (human/aletheia/coat_rig_aporia, 11-18, Opus 5.5; this file = the coat rig's d0d595b4 + what follows, staged
// in coat_rig_aporia/STAGED.md): a glb whose record carries `look.kind = 'aporia_woven'` (scripts/c30_glb.py of that round)
// is drawn in HER COAT ROUND'S MATERIALS: ./aporia_coat/aporia_coat.js (a copy of coat_design/aporia/engine/aporia_coat.js),
// its numbers (look.material: her aporia_coat_material.json) and its maps IN THE GLB ITSELF (the weave's normal and shade at
// its real pitch, her plate's normal and mask; a low's baked folds), each part as her coat round's own scene draws it
// (coat_design/aporia/engine/aporia_coat_scene.js `mats`). opts.hide may name a part OR A GROUP (each node's extras.group:
// 'zipfront' leaves her front zip out: the owner has not said whether Aporia keeps it). Aletheia's glbs draw as before, to the bit.
import { coatSprings, springGrid } from './coat_springs.js';
// (R2, 11-18) the LOW's film: the coat round's film material with the baked normals and the glow mask (a private copy:
// coat_film_maps.js; without maps it is the source to the bit). A design-mesh glb (no maps) draws as before.
import * as FILM_MAPS from './coat_film_maps.js';
const THREE = globalThis.THREE;

const flat = (CF, sec) => Object.fromEntries(Object.entries(CF[sec] || {}).filter(([, v]) => v && typeof v === 'object' && 'value' in v).map(([k, v]) => [k, v.value]));

// the coat round's materials, as its scene draws them (coat_design/design/engine/coat_on_her_scene.js; sisters.js's WIP layer):
// returns (part name, geometry) -> [{ material, renderOrder?, name, cast, film? }]
export function coatMaterials(M, CF, LUTjson, opts = {}) {
    const LUT = M.filmLuts(LUTjson);
    const F = { ...flat(CF, 'film'), ...(opts.film || {}) }, B = { ...flat(CF, 'binding'), ...(opts.binding || {}) };
    const TU = { ...flat(CF, 'tubes'), ...(opts.tubes || {}) }, SN = flat(CF, 'snaps'), PA = flat(CF, 'patch');
    const G = opts.glow || {};
    if (G.binding != null) for (const k of Object.keys(B)) if (/emissive|glow/i.test(k) && typeof B[k] === 'number') B[k] *= G.binding;
    const tube = (c, I) => {
        const m = new THREE.MeshPhysicalNodeMaterial();
        m.colorNode = THREE.vec3(...c).mul(0.25); m.emissiveNode = THREE.vec3(...c).mul(I);
        m.roughnessNode = THREE.float(TU.sleeve_roughness ?? 0.08); m.metalnessNode = THREE.float(0.0);
        return m;
    };
    // (R2) a low's maps (opts.maps: { normal, glow } textures on TEXCOORD_1): the bound edges' and the collar's glow is the
    // tube material's pink at the piping's own intensity, where the mask says so
    const MP = opts.maps || null;
    const glowOpt = MP?.glow ? { colour: TU.pink || [1, 0.16, 0.5], intensity: (TU.pink_intensity ?? 2.2) * (G.piping ?? 1.0), roughness: TU.sleeve_roughness ?? 0.08 } : null;
    const bopts = MP ? { normalMap: MP.normal || null, glowMap: MP.glow || null, glow: glowOpt } : {};
    const solid = {
        binding: M.bindingMaterial(B, bopts), piping: tube(TU.pink || [1, 0.16, 0.5], (TU.pink_intensity ?? 2.2) * (G.piping ?? 1.0)),
        tube_blue: tube(TU.blue || [0.18, 0.55, 1.0], (TU.blue_intensity ?? 2.4) * (G.tube_blue ?? 1.0)),
        snaps: new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(...(SN.colour || [0.035, 0.035, 0.04])), roughness: SN.roughness ?? 0.28, metalness: 1.0 }),
        patch: new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(...(PA.colour || [0.02, 0.02, 0.022])), roughness: PA.roughness ?? 0.62, metalness: 0.0 }),
    };
    // her collar: a sheet of the bindings' pink vinyl with its own numbers over the binding's (the coat round's fix 2: the
    // design json's 'collar' block: glossier, a third of the glow; no block = the binding's material, as fix 1 drew it)
    const CO = flat(CF, 'collar');
    solid.collar = Object.keys(CO).length ? M.bindingMaterial({ ...B, ...CO, ...(opts.collar || {}) }, bopts) : solid.binding;
    let nFilm = 0;
    return (part, geometry) => {
        if (['film', 'film2', 'lapel'].includes(part)) {
            nFilm++;
            return M.filmPasses(geometry, F, LUT, { name: `film_${part}`, mix: F.mix || 'ii', order: 'free', ro: 10, seed: nFilm, normalMap: MP?.normal || null })
                .map((p) => ({ material: p.material, renderOrder: p.renderOrder, name: p.name, cast: false, film: p.userData.filmPass }));
        }
        return solid[part] ? [{ material: solid[part], name: part, cast: true }] : [];
    };
}

// (Aporia's coat, 11-18) A TEXTURE OF THE GLB BY ITS INDEX, the engine's trap-safe way (the low's maps below say why: on the
// engine's Deno stack an ImageBitmap that no material slot holds uploads no pixels): the image's own bytes through the stack's
// loadImageTexture (flipY false: glTF's convention), elsewhere three's own texture. Data, not colour: no colour space
async function glbTexture(gltf, ti, wrap) {
    const json = gltf.parser.json;
    const img = json.images?.[json.textures?.[ti]?.source];
    let t;
    if (typeof globalThis.loadImageTexture === 'function' && img?.bufferView != null) {
        const ab = await gltf.parser.getDependency('bufferView', img.bufferView);
        t = await globalThis.loadImageTexture(new Uint8Array(ab), { flipY: false, ...(wrap ? { wrap } : {}) });
    } else {
        t = await gltf.parser.getDependency('texture', ti);
    }
    t.colorSpace = THREE.NoColorSpace;
    t.needsUpdate = true;
    return t;
}

// (Aporia's coat, 11-18) HER WOVEN AND HER HARDWARE, part by part, as her coat round's own scene draws them
// (coat_design/aporia/engine/aporia_coat_scene.js `mats`, copied): the shell, the felled laps, the placket and the welts in
// her woven (the weave at its real pitch on the pattern's flat uv in metres, the seam pucker from `_seam`, the contact shade
// from `_ao`), the free edges' rims plain woven, her black rib cuffs and collar band, thread, the zips' tape and metals, her
// round black buttons and white snaps, her port collars in dark carbon steel with their orange lights, her plate.
// look (the glb's record): { kind: 'aporia_woven', material (her json), weave: { tile_mm, normal, shade }, plate: { normal,
// mask } } (texture indices of the glb). opts.baked: a low's baked folds (R2: the woven's normal map on TEXCOORD_1, under the
// weave). Returns (part, geometry) -> [{ material, name, cast }]
export async function aporiaMaterials(gltf, look, opts = {}) {
    const M = await import('./aporia_coat/aporia_coat.js');
    const MAT = look.material;
    const sec = (k) => Object.assign(M.flat(MAT, k), (opts.over || {})[k] || {});
    const W = sec('woven'), RB = sec('rib');
    const TILE = look.weave?.tile_mm || null;
    const tex = async (ti, wrap) => (ti == null ? null : await glbTexture(gltf, ti, wrap));
    const weaveN = await tex(look.weave?.normal), weaveS = await tex(look.weave?.shade);
    const plateN = await tex(look.plate?.normal, THREE.ClampToEdgeWrapping), plateM = await tex(look.plate?.mask, THREE.ClampToEdgeWrapping);
    const woven = (o) => M.wovenMaterial(W, weaveN, weaveS, TILE, o);
    // (R2, 11-20) THE LOW: its shell is ONE surface whose laps, thread, pucker and folds are in its two baked maps
    // (opts.baked the normal, opts.mask; scripts/c52_bake.py), her weave a tiling detail over them; its zips' teeth are
    // strips drawn at the teeth's real pitch (./aporia_coat/aporia_coat_low.js). The design mesh draws as before.
    const ML = opts.baked ? await import('./aporia_coat/aporia_coat_low.js') : null;
    const mk = {
        shell: (g) => (ML ? ML.wovenLowMaterial(W, sec('thread'), weaveN, weaveS, TILE, { normal: opts.baked, mask: opts.mask || null })
            : woven({ seam: !!g.getAttribute('_seam'), ao: !!g.getAttribute('_ao') })),
        rim: () => M.wovenMaterial(W, null, null, null, { lighten: W.edge_wear, noMottle: true }),
        fell: (g) => woven({ seam: !!g.getAttribute('_seam'), lighten: W.edge_wear }),
        placket: (g) => woven({ seam: !!g.getAttribute('_seam'), lighten: W.edge_wear }),
        welt: (g) => woven({ seam: !!g.getAttribute('_seam'), lighten: W.edge_wear }),
        stitch: () => M.plainMaterial(sec('thread'), { name: 'aporia_thread' }),
        rib_cuff: () => M.ribMaterial(RB, RB.cuff_ribs_along),
        rib_stand: () => M.ribMaterial(RB, RB.stand_ribs_along),
        zipfront_tape: () => M.plainMaterial(sec('tape'), { double: true, name: 'aporia_tape' }),
        // (her coat round: the chest zips' strip is the pocket's WELT, in her cloth)
        chestzip_tape: () => woven({ lighten: W.edge_wear }),
        zipfront_teeth: () => (ML ? ML.teethMaterial(sec('zip_metal'), look.teeth_pitch_mm?.zipfront ?? 3.6, { name: 'aporia_zip_teeth' })
            : M.plainMaterial(sec('zip_metal'), { metal: true, name: 'aporia_zip_metal' })),
        zipfront_stops: () => M.plainMaterial(sec('zip_metal'), { metal: true, name: 'aporia_zip_metal' }),
        zipfront_slider: () => M.plainMaterial(sec('zip_metal'), { metal: true, name: 'aporia_zip_metal' }),
        chestzip_teeth: () => (ML ? ML.teethMaterial(sec('black_metal'), look.teeth_pitch_mm?.chestzip ?? 3.0, { name: 'aporia_chest_teeth' })
            : M.plainMaterial(sec('black_metal'), { metal: true, name: 'aporia_black_metal' })),
        chestzip_slider: () => M.plainMaterial(sec('black_metal'), { metal: true, name: 'aporia_black_metal' }),
        button: () => M.plainMaterial(sec('black_metal'), { metal: true, name: 'aporia_black_metal' }),
        snap_white: () => M.plainMaterial(sec('white_snap'), { name: 'aporia_white_snap' }),
        collar: () => M.plainMaterial(sec('carbon_steel'), { metal: true, name: 'aporia_carbon_steel' }),
        collar_back: () => M.plainMaterial(sec('carbon_steel'), { metal: true, name: 'aporia_carbon_steel' }),
        lights: () => M.lightMaterial(sec('lights')),
        plate: () => (plateN && plateM ? M.plateMaterial(sec('plate'), plateN, plateM) : M.plainMaterial(sec('carbon_steel'), { metal: true })),
    };
    const cache = {};
    return (part, geometry) => {
        const f = mk[part];
        if (!f) return [];
        if (!cache[part]) cache[part] = f(geometry);
        return [{ material: cache[part], name: part, cast: true }];
    };
}

export async function wearCoat(opts) {
    const { gltf, parent } = opts;
    const json = gltf.parser.json;
    const rec = json.extras?.bestiary?.coat_rig;
    if (!rec) throw new Error('[coat_rig] the glb carries no extras.bestiary.coat_rig record (scripts/c30_glb.py writes it)');
    const spec = rec.springs;
    const names = json.skins[0].joints.map((i) => json.nodes[i].name);
    const isSpring = new Set(spec.spring_joints);
    // ---- the file's skinned meshes and its one skeleton
    gltf.scene.updateMatrixWorld(true);
    const src = [];
    gltf.scene.traverse((o) => { if (o.isSkinnedMesh) src.push(o); });
    if (!src.length) throw new Error('[coat_rig] no skinned mesh in the coat glb');
    const skeleton = src[0].skeleton;
    if (skeleton.bones.length !== names.length) throw new Error(`[coat_rig] the skin has ${skeleton.bones.length} bones for ${names.length} joints`);
    // ---- its skeleton: her own joints for the body-following bones, the file's own bones for the spring joints
    const group = new THREE.Group();
    group.name = 'coat_on_spring_bones';
    const bones = new Map(), missing = [];
    names.forEach((nm, i) => {
        const own = skeleton.bones[i];
        if (isSpring.has(nm)) { own.removeFromParent(); group.add(own); bones.set(nm, own); return; }
        const hers = opts.joint(nm);
        if (!hers) { missing.push(nm); return; }
        own.removeFromParent();                        // (the file's stand-in for her joint: not part of any scene)
        skeleton.bones[i] = hers;
    });
    if (missing.length) throw new Error(`[coat_rig] her figure has no joint named: ${missing.join(', ')}`);
    // ---- (R2) a low's baked maps, in the file itself (c30_glb.py: extras.bestiary.coat_rig.maps = { normal, glow }:
    // texture indices; data, not colour: no colour space)
    let maps = null;
    if (rec.maps && (rec.maps.normal != null || rec.maps.glow != null || rec.maps.mask != null)) {
        maps = {};
        for (const k of ['normal', 'glow', 'mask']) {       // (mask: Aporia's low, 11-20: thread / lap / contact shade)
            if (rec.maps[k] == null) continue;
            // (11-18) ON THE ENGINE'S DENO STACK an image texture that no MATERIAL slot holds is never migrated to a
            // DataTexture (render_scene.mjs migrates material slots only), and an ImageBitmap upload there writes no
            // pixels: the first low drew with a black normal map (every normal tilted the same way: the film read bluer
            // and paler than the design's). So the image's own bytes go through the stack's loadImageTexture (a
            // DataTexture with CPU mips; flipY false: glTF's convention, the bake's); elsewhere three's own texture
            let t = null;
            const img = json.images?.[json.textures?.[rec.maps[k]]?.source];
            if (typeof globalThis.loadImageTexture === 'function' && img?.bufferView != null) {
                const ab = await gltf.parser.getDependency('bufferView', img.bufferView);
                t = await globalThis.loadImageTexture(new Uint8Array(ab), { flipY: false, wrap: THREE.ClampToEdgeWrapping });
            } else {
                t = await gltf.parser.getDependency('texture', rec.maps[k]);
            }
            t.colorSpace = THREE.NoColorSpace;
            t.needsUpdate = true;
            maps[k] = t;
        }
        // (a look switch for comparing: params.maps_off = ['normal'] draws the low without that map)
        for (const k of opts.params?.maps_off || []) delete maps[k];
    }
    // a low's doubled film carries its layers (c30 writes the attribute _LAYERS: three reads it as '_layers')
    for (const o of src) {
        const g = o.geometry;
        if (g.getAttribute('_layers') && !g.getAttribute('layers')) g.setAttribute('layers', g.getAttribute('_layers'));
    }
    // ---- the draws: each part's material(s) on skinned meshes of the one skeleton
    // (Aporia's coat, 11-18: a glb whose record names her look is drawn in her coat round's materials, its maps from the glb)
    const look = rec.look || null;
    const mats = opts.materials || (look?.kind === 'aporia_woven'
        ? await aporiaMaterials(gltf, look, { baked: maps?.normal || null, mask: maps?.mask || null, over: opts.lookOver })
        : coatMaterials(maps ? FILM_MAPS : opts.film.module, opts.film.design, opts.film.luts, { glow: opts.glow, film: opts.filmOver, maps }));
    const ident = new THREE.Matrix4();
    const draws = [];
    let triangles = 0;
    const perPart = {};
    for (const o of src) {
        const part = (o.name || '').replace(/^coat_/, '');
        // (Aporia's coat, 11-18: a part OR ITS GROUP, the node's extras.group: hide: ['zipfront'] leaves her front zip out)
        if ((opts.hide || []).includes(part) || (o.userData?.group && (opts.hide || []).includes(o.userData.group))) continue;
        const geo = o.geometry;
        const n = geo.index ? geo.index.count / 3 : geo.attributes.position.count / 3;
        const list = mats(part, geo);
        if (!list.length) continue;
        triangles += n; perPart[part] = n;
        for (const d of list) {
            const m = new THREE.SkinnedMesh(geo, d.material);
            m.name = `coat_${d.name}`;
            m.bind(skeleton, ident);
            m.frustumCulled = false;                    // (a skinned sheet's static bound says nothing about where it swings)
            m.castShadow = !!d.cast; m.receiveShadow = true;
            if (d.renderOrder != null) m.renderOrder = d.renderOrder;
            if (d.film) { m.userData.noClippingCheck = true; m.userData.filmPass = d.film; }
            group.add(m);
            draws.push(m);
        }
    }
    parent.add(group);
    group.updateWorldMatrix(true, true);
    // ---- her colliders: the grids (in the file's buffer), the carriers (her joints, each with the coat's inverse bind of it)
    const grids = {};
    for (const s of spec.sdf || []) {
        const ab = await gltf.parser.getDependency('bufferView', s.bufferView);
        grids[s.name] = springGrid(new Float32Array(ab, 0, s.dims[0] * s.dims[1] * s.dims[2]), s);
    }
    const rowMajor = (a) => new THREE.Matrix4().set(...a);
    const carriers = new Map(), noJoint = [];
    for (const [nm, a] of Object.entries({ ...spec.stand, ...(spec.stand_free || {}) })) {
        const o = opts.joint(nm);
        if (!o) { noJoint.push(nm); continue; }        // (a capsule on a joint she does not wear today, e.g. no tentacles: left out)
        carriers.set(nm, { object: o, inverse: rowMajor(a).invert() });
    }
    const ctl = coatSprings(spec, bones, null, { carriers, grids, params: opts.params });
    const L = ctl.layout();
    const jAt = new Map(L.joints.map((n, i) => [n, i]));
    const springIdx = spec.spring_joints.map((n) => jAt.get(n));
    const q = new THREE.Quaternion(), p = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1), W = new THREE.Matrix4(), v = new THREE.Vector3();
    const api = {
        group, springs: ctl, spec, draws, skeleton, record: rec,
        counts: { joints: names.length, body_following: names.length - spec.spring_joints.length, spring: spec.spring_joints.length, particles: L.n, links: L.links,
            samples: L.samples, collider_grids: L.sdf.length, capsules: L.capsules.length, triangles, by_part: perPart, draws: draws.length,
            joints_not_worn: noJoint },
        update(t) {
            group.updateWorldMatrix(true, false);
            ctl.step(t);
        },
        reset() { group.updateWorldMatrix(true, false); ctl.reset(); },
        dump: {
            joints: spec.spring_joints, particles: L.n, floats: 16 * spec.spring_joints.length + 3 * L.n,
            // 16 floats a spring joint (COLUMN major) then 3 a particle, relative to the frame whose inverse world matrix is `inv`
            write(out, at, inv) {
                const jw = ctl.jointWorld, cur = ctl.particles();
                for (const i of springIdx) {
                    p.set(jw[7 * i], jw[7 * i + 1], jw[7 * i + 2]);
                    q.set(jw[7 * i + 3], jw[7 * i + 4], jw[7 * i + 5], jw[7 * i + 6]);
                    W.compose(p, q, one).premultiply(inv);
                    out.set(W.elements, at); at += 16;
                }
                for (let i = 0; i < L.n; i++) {
                    v.set(cur[3 * i], cur[3 * i + 1], cur[3 * i + 2]).applyMatrix4(inv);
                    out[at] = v.x; out[at + 1] = v.y; out[at + 2] = v.z; at += 3;
                }
                return at;
            },
        },
    };
    return api;
}
