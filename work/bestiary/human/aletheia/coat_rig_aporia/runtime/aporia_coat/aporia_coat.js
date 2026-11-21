// aporia_coat.js: THE MATERIALS OF APORIA'S COAT, an opaque WOVEN FABRIC and its hardware (the Aporia coat round, 11-18,
// Fable 5.2). A design-round module in my folder; nothing live. three r184 WebGPU / TSL, NodeMaterials only. Its numbers
// are ../material/aporia_coat_material.json (every constant with its reason); the scene hands them in.
//
// WHY A NEW MODULE (the coat round's material/engine/coat_film.js has a `shellMaterial` for an Aporia coat): that one is
// "an opaque coated nylon" drawn on Aletheia's raincoat pattern, the coat the owner saw and turned down ("an opaque orange
// version of aletheia's ... should be an actual fabric techwear trenchcoat, not raincoat"). KEPT from it: the idea of the
// weave's normal at its real pitch from the pattern's flat uv in METRES, the sheen lobe's N.V clamp. NEW here:
//   1. THE WEAVE IS HER CLOTH'S (scripts/a23_weave_maps.py: a 41 x 25 / cm plain weave with its ripstop grid), with a
//      SHADE map beside the normal (the gaps between yarns, each yarn's tone): a woven is matt because of its relief;
//   2. A WOVEN'S ROUGHNESS (0.92) and a small sheen: no film gloss anywhere;
//   3. SEAM PUCKER as a ripple of the normal beside every stitched line (the shell's `_seam` attribute: the flat
//      distance in mm to the nearest seam or stitched row; a13), and a slow MOTTLE of the dye;
//   4. the contact shade round hardware from the shell's `_ao` attribute (a13);
//   5. the rib knit, the thread, the tapes and the metals each their own material.
const THREE = globalThis.THREE;

// one section of the json as { name: value }
export function flat(M, sec) {
    const o = {};
    for (const [k, v] of Object.entries(M[sec] || {})) if (v && typeof v === 'object' && 'value' in v) o[k] = v.value;
    return o;
}

// the shading normal kept a hair on the eye's side (three's sheen lobe divides by N.V: runtime/beetle_cuticle.js's fix,
// as the coat round's shell)
function eyeSide(nrm) {
    const { float, positionViewDirection } = THREE;
    return nrm.add(positionViewDirection.mul(float(1.0e-3).sub(nrm.dot(positionViewDirection)).max(0.0))).normalize();
}

// a height h (METRES, any node) laid over the normal N (view space): Mikkelsen's screen-space bump (three's BumpMapNode
// does the same from a texture; here the height is a formula of the cloth's flat place)
function bump(N, h) {
    const { positionView } = THREE;
    const dpdx = positionView.dFdx(), dpdy = positionView.dFdy();
    const R1 = dpdy.cross(N), R2 = N.cross(dpdx);
    const det = dpdx.dot(R1);
    const grad = det.sign().mul(h.dFdx().mul(R1).add(h.dFdy().mul(R2)));
    return det.abs().mul(N).sub(grad).normalize();
}

// ------------------------------------------------------------------------------------------------ the woven
// S: the json's `woven`; normalTex / shadeTex: a23's tile (loaded through loadImageTexture, flipY false) or null (a
// part without a flat uv: the rims); tile_mm [u, v]: the tile's size. opts: { seam: true (the geometry carries `_seam`),
// ao: true (it carries `_ao`), lighten: 0..1 (a rubbed crown), colour: [r, g, b] (a try) }
export function wovenMaterial(S, normalTex, shadeTex, tile_mm, opts = {}) {
    const { float, vec2, vec3, uv, texture, fwidth, normalMap, normalView, mix, attribute } = THREE;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const dye = vec3(...(opts.colour || S.dye));
    let col = dye;
    let nrm = normalView;
    const uvm = uv();                                            // the pattern's flat place, metres
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
        nrm = normalMap(vec3(nd.xy.mul(float(S.weave_strength)).mul(fade), 1.0).normalize().mul(0.5).add(0.5));
    }
    const uvmm = uvm.mul(1000.0);
    if (S.mottle > 0 && THREE.mx_noise_float && !opts.noMottle) {
        // a slow noise of the flat place: patches of 40-120 mm, +- S.mottle
        const n = THREE.mx_noise_float(vec3(uvmm.x.div(70.0), uvmm.y.div(95.0), 3.7)).mul(0.65)
            .add(THREE.mx_noise_float(vec3(uvmm.x.div(23.0), uvmm.y.div(31.0), 9.1)).mul(0.35));
        col = col.mul(float(1.0).add(n.mul(float(S.mottle))));
    }
    if (opts.lighten > 0) col = mix(col, col.mul(1.25).add(vec3(0.03)).min(vec3(1.0)), float(opts.lighten));
    if (opts.ao) col = col.mul(attribute('_ao', 'float').clamp(0.0, 1.0));
    m.colorNode = col;
    if (opts.seam && S.pucker_mm > 0 && THREE.mx_noise_float) {
        // SEAM PUCKER: a ripple beside the stitched line, strongest on it, gone `reach` away: the height in metres
        const d = attribute('_seam', 'float');
        const w = d.div(float(S.pucker_reach_mm));
        const band = w.mul(w).negate().exp();
        const rip = THREE.mx_noise_float(vec3(uvmm.x.div(float(S.pucker_wave_mm * 0.5)), uvmm.y.div(float(S.pucker_wave_mm * 0.5)), 1.3));
        nrm = bump(nrm, rip.mul(band).mul(float(S.pucker_mm * 0.5e-3)));
    }
    m.normalNode = eyeSide(nrm);
    m.roughnessNode = float(S.roughness);
    m.metalnessNode = float(0.0);
    // a yarn's fibres send the surface's own white reflection into the weave, where most of it is dyed before it
    // leaves: a woven's white gloss is a share of a smooth dielectric's (S.specular scales three's F0 0.04)
    // (three r184 reads the PLAIN property here: MeshPhysicalNodeMaterial.setupSpecular takes materialSpecularIntensity,
    // the uniform of material.specularIntensity; a `specularIntensityNode` is never looked at: MEASURED, two stills
    // with the node at 0.15 and at 0.05 were the same to the last digit)
    if (S.specular !== undefined) m.specularIntensity = S.specular;
    if (S.sheen > 0 && !opts.noSheen) {
        m.sheenNode = mix(dye.mul(1.6).min(vec3(1.0)), vec3(1.0), float(S.sheen_white)).mul(float(S.sheen));
        m.sheenRoughnessNode = float(S.sheen_roughness);
    }
    m.side = THREE.DoubleSide;
    m.name = 'aporia_woven';
    return m;
}

// ------------------------------------------------------------------------------------------------ the rib knit
// her black cuffs and collar band: ridges of a 2 x 2 rib as a normal from the flat uv; along: 'v' (the ribs run up
// the piece: the cuffs) or 'u' (they run along it: her collar band)
export function ribMaterial(R, along) {
    const { float, vec3, uv, normalMap, fwidth } = THREE;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const col = vec3(...R.colour);
    const q = (along === 'v' ? uv().x : uv().y).mul(1000.0 / R.pitch_mm);         // ribs counted across their run
    const ph = q.mul(2.0 * Math.PI);
    // a rib's section: two round wales up, a narrow deep valley: the slope of a cosine sharpened toward the valley
    const slope = ph.sin().mul(float(R.depth)).mul(float(1.0).sub(fwidth(q).sub(0.15).div(0.35)).clamp(0.0, 1.0));
    const tn = along === 'v' ? vec3(slope, 0.0, 1.0) : vec3(0.0, slope, 1.0);
    m.colorNode = col.mul(float(0.72).add(ph.cos().mul(0.28)));                    // the valleys darker
    m.normalNode = eyeSide(normalMap(tn.normalize().mul(0.5).add(0.5)));
    m.roughnessNode = float(R.roughness);
    m.metalnessNode = float(0.0);
    m.sheenNode = vec3(0.5, 0.5, 0.52).mul(float(R.sheen));
    m.sheenRoughnessNode = float(0.7);
    m.name = 'aporia_rib_' + along;
    return m;
}

// ------------------------------------------------------------------------------------------------ plain parts
export function plainMaterial(C, { metal = false, double = false, name = 'aporia_plain' } = {}) {
    const m = new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(...C.colour), roughness: C.roughness, metalness: metal ? 1.0 : 0.0 });
    if (double) m.side = THREE.DoubleSide;
    m.name = name;
    return m;
}

export function lightMaterial(L) {
    const { vec3, float } = THREE;
    const m = new THREE.MeshStandardNodeMaterial();
    m.colorNode = vec3(...L.colour).mul(0.3);
    m.emissiveNode = vec3(...L.colour).mul(float(L.intensity));
    m.roughnessNode = float(0.25);
    m.metalnessNode = float(0.0);
    m.name = 'aporia_light';
    return m;
}

// her name plate: METAL, her dark carbon steel, the raised letters and the worn edges bright bare steel (the study's
// plateMaterial, copied). normalTex / maskTex: scripts/a12_plate_maps.py (R the letters' tops, G the border's crown,
// B the worn edges); uv = the plate's own face 0..1
export function plateMaterial(P, normalTex, maskTex) {
    const { float, vec3, uv, texture, mix, normalMap } = THREE;
    for (const t of [normalTex, maskTex]) { t.colorSpace = THREE.NoColorSpace; t.anisotropy = 8; }
    const mk = texture(maskTex, uv());
    const bright = mk.r.max(mk.g).max(mk.b.mul(float(P.edge_wear)));
    const m = new THREE.MeshStandardNodeMaterial();
    m.colorNode = mix(vec3(...P.steel), vec3(...P.letters), bright.clamp(0.0, 1.0));
    m.metalnessNode = float(1.0);
    m.roughnessNode = mix(float(P.roughness), float(P.letters_roughness), mk.r.max(mk.g));
    m.normalNode = normalMap(texture(normalTex, uv()));
    m.name = 'aporia_plate';
    return m;
}
