// aporia_coat_low.js: THE WOVEN LOOK ON THE LOW OF APORIA'S COAT (human/aletheia/coat_rig_aporia, stage R2, 11-20, Fable 5.2).
// A private module of her coat's spring-rig round; nothing live imports it (the landing: coat_rig_aporia/STAGED.md).
// three r184 WebGPU / TSL, NodeMaterials only. Beside ./aporia_coat.js (her coat round's materials, a copy to the bit: the
// design mesh and every part the low keeps as geometry are still drawn by it).
//
// WHAT THE LOW DOES NOT MODEL IS IN ITS TWO MAPS (scripts/c52_bake.py, on TEXCOORD_1, the atlas):
//   normal  the drape's folds + the relief of the felled laps, the placket band, the welts, every row of thread, the seam
//           pucker (tangent space, the TANGENT attribute's frame)
//   mask    R thread (its share of the texel), G a lap (the cloth's rubbed crowns), B the contact shade round her hardware
// and HER WEAVE IS A TILING DETAIL OVER THEM at its real pitch (TEXCOORD_0 = the pattern in metres, as the design mesh's):
// the same tile, strength, shade and distance fade as her coat round's wovenMaterial; its normal is laid over the baked one.
// THE ONE DIFFERENCE OF FRAME: the tile lies in the pattern's own frame (x along +u, y along +v); the low's tangents are
// built from TEXCOORD_1, where the pattern's v runs DOWN the image: T = +u, B = -v. So the tile's y is turned over.
const THREE = globalThis.THREE;

// the shading normal kept a hair on the eye's side (three's sheen lobe divides by N.V; as aporia_coat.js)
function eyeSide(nrm) {
    const { float, positionViewDirection } = THREE;
    return nrm.add(positionViewDirection.mul(float(1.0e-3).sub(nrm.dot(positionViewDirection)).max(0.0))).normalize();
}

// S: her json's `woven`; TH: her json's `thread`; normalTex / shadeTex / tile_mm: the weave's tile (as wovenMaterial);
// maps: { normal, mask } the low's baked maps (textures, flipY false, no colour space). opts: { lighten: 0..1 }
export function wovenLowMaterial(S, TH, normalTex, shadeTex, tile_mm, maps, opts = {}) {
    const { float, vec2, vec3, uv, texture, fwidth, normalMap, mix } = THREE;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const dye = vec3(...S.dye);
    let col = dye;
    const uvm = uv();                                            // the pattern's flat place, metres
    const uva = uv(1);                                           // the atlas
    const nb = texture(maps.normal, uva).xyz.mul(2.0).sub(1.0);
    let nxy = nb.xy;
    if (normalTex && tile_mm) {
        for (const t of [normalTex, shadeTex]) {
            if (!t) continue;
            t.colorSpace = THREE.NoColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
        }
        const wuv = uvm.mul(vec2(1000.0 / tile_mm[0], 1000.0 / tile_mm[1]));
        const fp = fwidth(wuv);
        const fade = float(1.0).sub(fp.x.max(fp.y).sub(S.fade[0]).div(S.fade[1] - S.fade[0])).clamp(0.0, 1.0);
        if (shadeTex) {
            const sh = texture(shadeTex, wuv).r.div(0.80);       // a23 stores the shade x 0.80
            col = col.mul(mix(float(1.0), sh, fade.mul(float(S.shade_strength))));
        }
        const nd = texture(normalTex, wuv).xyz.mul(2.0).sub(1.0);
        nxy = nxy.add(vec2(nd.x, nd.y.negate()).mul(float(S.weave_strength)).mul(fade));
    }
    const uvmm = uvm.mul(1000.0);
    if (S.mottle > 0 && THREE.mx_noise_float) {
        // a slow noise of the flat place: patches of 40-120 mm, +- S.mottle (as wovenMaterial)
        const n = THREE.mx_noise_float(vec3(uvmm.x.div(70.0), uvmm.y.div(95.0), 3.7)).mul(0.65)
            .add(THREE.mx_noise_float(vec3(uvmm.x.div(23.0), uvmm.y.div(31.0), 9.1)).mul(0.35));
        col = col.mul(float(1.0).add(n.mul(float(S.mottle))));
    }
    let rough = float(S.roughness);
    if (maps.mask) {
        const mk = texture(maps.mask, uva);
        // a lap's crown is rubbed a little lighter (the design draws its laps with `lighten: edge_wear`)
        col = mix(col, col.mul(1.25).add(vec3(0.03)).min(vec3(1.0)), mk.g.mul(float(opts.lighten ?? S.edge_wear ?? 0.1)));
        col = mix(col, vec3(...TH.colour), mk.r);
        rough = mix(rough, float(TH.roughness), mk.r);
        col = col.mul(mk.b.clamp(0.0, 1.0));
    }
    m.colorNode = col;
    m.normalNode = eyeSide(normalMap(vec3(nxy, nb.z).normalize().mul(0.5).add(0.5)));
    m.roughnessNode = rough;
    m.metalnessNode = float(0.0);
    // (three r184 reads the PLAIN property: aporia_coat.js's note)
    if (S.specular !== undefined) m.specularIntensity = S.specular;
    if (S.sheen > 0) {
        m.sheenNode = mix(dye.mul(1.6).min(vec3(1.0)), vec3(1.0), float(S.sheen_white)).mul(float(S.sheen));
        m.sheenRoughnessNode = float(S.sheen_roughness);
    }
    m.side = THREE.DoubleSide;
    m.name = 'aporia_woven_low';
    return m;
}

// A ZIP'S TEETH AS A STRIP (the low: scripts/c50_low.py draws each zip's teeth as one strip; its uv: x 0 at the teeth's roots
// to +-1 at their tips, the sign = the half, y the flat height in METRES). The teeth are drawn at their real pitch: bright
// crowns, the black tape in the gaps, a dome's slope across each tooth; the two halves sit half a pitch apart. Under about
// three pixels a tooth it fades to the even grey of teeth and gaps. Cm: her json's metal (colour, roughness)
export function teethMaterial(Cm, pitch_mm, { name = 'aporia_teeth' } = {}) {
    const { float, vec3, uv, fwidth, mix, normalMap, smoothstep } = THREE;
    const m = new THREE.MeshStandardNodeMaterial();
    const q = uv().y.mul(1000.0 / pitch_mm).add(uv().x.sign().mul(0.25));
    const w = fwidth(q).max(1.0e-4);
    const far = w.sub(0.3).div(0.5).clamp(0.0, 1.0);             // 0 near (a tooth over 3 px) .. 1 far (under 1.2 px)
    const tri = q.fract().sub(0.5).abs();                        // 0 at a tooth's middle .. 0.5 between two
    const tooth = float(1.0).sub(smoothstep(float(0.31).sub(w), float(0.31).add(w), tri));
    const cover = mix(tooth, float(0.62), far);
    m.colorNode = mix(vec3(0.012, 0.012, 0.014), vec3(...Cm.colour), cover);
    m.metalnessNode = cover;                                     // (a gap shows the black tape under it)
    m.roughnessNode = mix(float(0.85), float(Cm.roughness), cover);
    const slope = q.fract().sub(0.5).mul(2.0 * Math.PI).sin().mul(0.8).mul(float(1.0).sub(far));
    m.normalNode = normalMap(vec3(0.0, slope, 1.0).normalize().mul(0.5).add(0.5));
    m.side = THREE.DoubleSide;
    m.name = name;
    return m;
}
