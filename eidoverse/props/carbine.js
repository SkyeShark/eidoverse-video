// eidoverse/props/carbine.js — an M4A1-pattern carbine as a hard-surface game asset: the Blender edition's
// eidoblend.props.carbine (a 499 k-triangle high drawn as a 21 k-triangle low of the same 64 parts, the high baked onto
// the low on the GPU) with its ONE layered material rebuilt in TSL on its baked maps (eidoverse/layered_material.js).
// Function markings only (the rail's numbers, the selector's SAFE / SEMI / AUTO): no maker's marks, no serial.
//
//   const C = await import(new URL('props/carbine.js', EIDOVERSE_DIR).href);
//   const rifle = await C.build(THREE, { condition: { wear: 1.0, dust: 1.0 } });   // -> { group, parts, materials, dispose }
//   scene.add(rifle.group);
//   rifle.parts.magazine.visible = false;                 // the parts by name are its anatomy
//
// Its space (metres): +X to the muzzle, +Y up, +Z the carbine's right; the origin on the bore's axis at the receiver's
// rear face (the butt at x -0.1785, the flash hider's end at 0.582); every part at identity, so the group carries it.
// condition scales the wear, the polish, the dust and the grime together (1: as built; 0.3 nearly new; 1.6 hard
// used). The CC0 photographs the material reads (six ambientCG sets) are fetched once into eidoverse/assets/cache/.
// Assets: eidoverse/assets/models/carbine/ (carbine.glb, its maps, carbine_layered.json: the look's tables).
// Guide: tools-guides/props-and-sets.md ("The carbine").

const HERE = new URL('../assets/models/carbine/', import.meta.url);

export const NAME = 'carbine';

// the made asset's tables (the Blender edition's eidoblend.props.carbine.look), read once
let _tables = null;
export async function tables() {
    if (!_tables) _tables = JSON.parse(new TextDecoder().decode(await Deno.readFile(new URL('carbine_layered.json', HERE))));
    return _tables;
}

async function parseGLB(bytes) {
    const buf = bytes instanceof ArrayBuffer ? bytes : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return await new globalThis.GLTFLoader().parseAsync(buf, '');
}

// build(THREE, opts) -> { group, parts: { name: Mesh }, materials: { layered, lens }, tables, dispose() }
//   opts.condition: { wear, polish, dust, grime } scales (each 1 by default)
//   opts.glb: the GLB's bytes instead of the library's file; opts.photos: layered_material.photos() already loaded
//   (share them between several carbines); opts.maps: loadBake()'s textures already loaded
export async function build(THREE, opts = {}) {
    const LM = await import(new URL('../layered_material.js', import.meta.url).href);
    const T = await tables();
    const gltf = await parseGLB(opts.glb ?? await Deno.readFile(new URL('carbine.glb', HERE)));
    const maps = opts.maps ?? await LM.loadBake(THREE, HERE, NAME);
    const photos = opts.photos ?? await LM.photos(THREE, {
        grainSets: T.grain_sets, extra: Object.fromEntries(Object.entries(T.photos).map(([k, v]) => [k, v])),
    });
    const layered = LM.bakedMaterial(THREE, maps, T.substrates, {
        photos, hands: T.hands, knocks: T.knocks, stains: T.stains, condition: opts.condition ?? null,
        markColor: T.mark_color, dustColor: T.dust_color, sootColor: T.soot_color, name: 'carbine.layered',
    });
    const lens = new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(...T.lens.color), roughness: T.lens.roughness,
        metalness: T.lens.metalness });
    lens.name = 'carbine.lens_coated';
    const group = new THREE.Group();
    group.name = NAME;
    group.add(gltf.scene);
    const parts = {};
    gltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const old = o.material;
        o.material = /lens/.test(o.name) ? lens : layered;
        if (old && old !== o.material) old.dispose?.();
        o.castShadow = true;
        o.receiveShadow = true;
        parts[o.name] = o;
    });
    return {
        group, parts, materials: { layered, lens }, tables: T, maps, photos,
        dispose() {
            group.removeFromParent();
            for (const o of Object.values(parts)) o.geometry.dispose();
            layered.dispose();
            lens.dispose();
            if (!opts.maps) for (const t of Object.values(maps)) if (t?.isTexture) t.dispose();
        },
    };
}
