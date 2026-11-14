// B2 (11-08): THE GARMENT MATERIAL (TSL), for the clothed human's garment_* meshes (forge/garments/export.py). Staged for
// runtime/ (patches/garments_runtime.md); the scenes import this copy until the landing.
//
// The glb's maps: baseColor = the UNDYED cloth (luminance: weave mottling, thread, wear), normal = the baked folds + the
// construction's height (seams, stitches, hems, plackets, lacing), ORM = AO / roughness / metal, the emissive slot at
// factor 0 = MASKS (R the dye zone, G the trim zone, B the third zone, A wear). The extras name the WEAVE tile (a texture
// in the glb: the yarns' normal at their real pitch) and its size in mm, so the tile repeats at the cloth's real scale.
// The colour options of the old outfit map to the zones: outfit.shirt / pants / shoes -> R of that garment, the trim
// (thread, rib, buttons, laces) -> G, a shoe's sole -> B.
//
//   const m = await garmentMaterial(mesh, gltf, { dye: 0x3a6ea8, trim: 0xe8e4dc, third: 0x1a1816 });
export async function garmentMaterial(o, gltf, opts = {}) {
    const { texture, uv, vec3, vec4, float, mix, normalMap, normalView, positionViewDirection, pow, normalize } = THREE;
    const src = o.material;
    const ex = src.userData || {};
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.emissiveMap]) {
        if (t) { t.colorSpace = THREE.NoColorSpace; t.needsUpdate = true; }
    }
    const lin = (c, d) => new THREE.Color(c ?? d);      // THREE.Color from hex: sRGB in, linear working colour
    const U = {
        dye: THREE.uniform(lin(opts.dye, 0x3a6ea8)),
        trim: THREE.uniform(lin(opts.trim, 0xe6e2da)),
        third: THREE.uniform(lin(opts.third, 0x1c1a18)),
        fuzz: THREE.uniform(opts.fuzz ?? (ex.fabric === 'leather' ? 0.0 : 0.10)),
        weaveStrength: THREE.uniform(opts.weave ?? 0.4),
    };
    const m = new THREE.MeshPhysicalNodeMaterial();
    const alb = texture(src.map, st);
    const orm = texture(src.roughnessMap || src.aoMap, st);
    const masks = src.emissiveMap ? texture(src.emissiveMap, st) : vec4(1, 0, 0, 0);
    const zone = U.dye.mul(masks.r).add(U.trim.mul(masks.g)).add(U.third.mul(masks.b));
    let col = alb.rgb.mul(zone.div(masks.r.add(masks.g).add(masks.b).max(1e-3)));
    // the cloth's rim fuzz (the accessories' cloth layer: Fresnel exponent ~2)
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    col = col.add(pow(float(1.0).sub(ndv), 2.0).mul(U.fuzz).mul(zone.add(0.15)));
    m.colorNode = col;
    // the macro normal + the weave tile at the cloth's real scale (UDN blend in tangent space)
    let nrm = texture(src.normalMap, st).xyz.mul(2.0).sub(1.0);
    if (ex.weave_texture != null && ex.weave_tile_mm && !opts.noWeave) {
        const wt = await gltf.parser.getDependency('texture', ex.weave_texture);
        wt.colorSpace = THREE.NoColorSpace;
        wt.wrapS = wt.wrapT = THREE.RepeatWrapping;
        wt.generateMipmaps = true;
        wt.minFilter = THREE.LinearMipmapLinearFilter;
        wt.anisotropy = 8;
        wt.needsUpdate = true;
        const rep = (ex.size / (ex.texel_px_per_m || 3600.0)) * 1000.0 / ex.weave_tile_mm;
        const wuv = st.mul(rep);
        let nd = texture(wt, wuv).xyz.mul(2.0).sub(1.0);
        if (opts.weaveFlip) nd = nd.mul(vec3(opts.weaveFlip[0], opts.weaveFlip[1], 1.0));     // diagnostic
        // the yarns FADE where a pixel covers more than a quarter of a tile: a minified tile aliases into a coherent
        // tilt over whole panels (look/e03: one half-shirt 30 % darker), so the weave is a close-range detail only
        const fp = THREE.fwidth(wuv);
        const fade = float(1.0).sub(fp.x.max(fp.y).sub(0.04).div(0.12)).clamp(0.0, 1.0);
        nrm = normalize(vec3(nrm.xy.add(nd.xy.mul(U.weaveStrength).mul(fade)), nrm.z));
    }
    if (!opts.noNormal) m.normalNode = normalMap(nrm.mul(0.5).add(0.5));
    m.roughnessNode = orm.g;
    m.metalnessNode = float(0.0);
    m.aoNode = orm.r;
    if (ex.fabric === 'leather') {
        m.clearcoatNode = float(0.25).mul(masks.r);
        m.clearcoatRoughnessNode = float(0.35);
    }
    // NO three sheen lobe: its visibility term has no floor (human_skin.js's note: inf x 0 = NaN where N.L and N.V reach
    // 0); here it painted black blotches over the folds (look/e01: gone with 'gnosheen'). The cloth's soft rim is the
    // fuzz term above.
    m.side = THREE.DoubleSide;
    m.name = (src.name || 'garment') + '_b2';
    m.userData.garment = { uniforms: U, extras: ex };
    return m;
}
