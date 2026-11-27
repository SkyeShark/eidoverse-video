// eidoverse/sets/desert/look.js — the desert's materials in TSL: eidoblend.sets.desert.look's desert.ground and
// desert.scrub, node for node, over the town's own ground (eidoverse/sets/town/look.js: its kit and groundPlain, the same
// functions in the same metres, so where the desert rises out of the town's plane there is no seam).
//
//   const look = await makeLook(THREE, { renderer, masks, marks });  // -> { ground, scrub, plain, textures, dispose }
//
// THE SETS. The ground reads sixteen CC0 photographs: the town's sand, dry ground, gravel ground and dry grass (its
// plain) and its cracked mud, and the desert's eleven in cc0_sets.json beside this file, fetched by ID on first use
// (fetchPBR). WebGPU binds at most 16 sampled textures to a shader stage, and the marks, the sun's shadow and the sky's
// light need their room too, so the sixteen are ONE texture array (2048 x 2048 x 16, each layer with the CPU mip chain
// loadImageTexture gives the town's own maps); the relief of the two sets the ground bumps with (the dune ripples, the
// cliff rock) rides in their alpha. Each set is read at its real size as the town reads its own (tile, mean), its
// colour divided by its own mean.
// THE MASKS are the land's own, per vertex (dmA: the distance from the town, the sand's depth, the escarpment's and the
// ranges' heights; dmB: the sand sheet, the wadi bed, the bars' and the aprons' heights), read at the pixel's covered
// sample (centroid: never extrapolated past a triangle); what is finer than the mesh (the tracks, the beds and bars,
// the floor's drainage lines, the sand sheet) from the two marks pictures (1 m within 2 km, 4 m out to 8 km).
// THE RELIEF is Blender's Bump (strength 1, distance 1) from the height's screen derivatives, as EEVEE draws it.
// THE AIR past the town's haze: the land thinned into the sky's low colour by its distance from the lens (AIR), the
// Blender material's emission mix; the scene's fog (the town's dust, world()) goes on top of it, as EEVEE's volume does.
import { kit, groundFns, REG as TOWN_REG, DUST } from '../town/look.js';

const HERE = new URL('./', import.meta.url);
export const REG = JSON.parse(Deno.readTextFileSync(new URL('cc0_sets.json', HERE))).sets;
const SETS = { ...TOWN_REG, ...REG };                                // (the town's names and the desert's: none shared)
// the array's layers: the town's sets the ground reads, then the desert's
export const LAYERS = ['sand', 'dry_ground', 'gravel_ground', 'dry_grass', 'mud_cracked', 'stony', 'sandy_gravel', 'gravel_sand', 'pale_sand',
    'dune_ripples', 'cliff_rock', 'cliff_warm', 'scree', 'caprock', 'dark_gravel', 'dark_rock'];
const RELIEF = ['dune_ripples', 'cliff_rock'];
// THE AIR past the town's haze box: extinction per metre past d0, and the colour the far land goes to (the sky low down,
// dusty): it starts where the town's dust has already greyed the land and thins it slowly to the ranges at 25 km
export const AIR = { d0: 4000.0, sigma: 2.5e-5, color: [0.60, 0.62, 0.66], strength: 1.0 };
// the escarpment's beds by its own height over the floor (the plateau stands about 200 m): the lower slopes, then
// [middle, half width, colour] up the wall: a grey-green marl band, a pale ledge, the buff cliff, the caprock
const STRATA = { base: [0.36, 0.32, 0.26], beds: [[0.34, 0.03, [0.43, 0.41, 0.35]], [0.55, 0.015, [0.50, 0.45, 0.36]],
    [0.61, 0.02, [0.44, 0.38, 0.29]], [0.84, 0.012, [0.54, 0.49, 0.40]]] };
const SCRUB = [[0.075, 0.085, 0.05], [0.12, 0.125, 0.08], [0.16, 0.13, 0.08], [0.10, 0.11, 0.075], [0.19, 0.17, 0.12]];

// the sixteen sets as one sRGB texture array with its mip chain; the levels past the first are written to the GPU by
// hand when three uploads the array (three's own upload of an array texture writes its first level only)
async function setArray(THREE, renderer, { res = null, log = console.log } = {}) {
    const N = LAYERS.length;
    let size = 0, levels = null;
    for (let L = 0; L < N; L++) {
        const key = LAYERS[L], s = SETS[key];
        const { files } = await globalThis.fetchPBR(s.id, { res: res || s.res });
        const col = await globalThis.loadImageTexture(Deno.readFileSync(files.diff), { srgb: true });
        const rel = RELIEF.includes(key) ? await globalThis.loadImageTexture(Deno.readFileSync(files.displacement)) : null;
        const mips = col.mipmaps && col.mipmaps.length ? col.mipmaps : [col.image];
        if (L === 0) {
            size = col.image.width;
            levels = mips.map((m) => ({ data: new Uint8Array(m.width * m.height * 4 * N), width: m.width, height: m.height, depth: N }));
        }
        if (col.image.width !== size || col.image.height !== size || mips.length !== levels.length) {
            throw new Error(`[desert] the set ${key} (${s.id}) is ${col.image.width} x ${col.image.height}: every set in the array must be ${size} x ${size} (res)`);
        }
        const rmips = rel ? (rel.mipmaps && rel.mipmaps.length ? rel.mipmaps : [rel.image]) : null;
        mips.forEach((m, i) => {
            const n = m.width * m.height, dst = levels[i].data, off = n * 4 * L;
            dst.set(m.data, off);
            const r = rmips ? rmips[i].data : null;
            for (let p = 0; p < n; p++) dst[off + p * 4 + 3] = r ? r[p * 4] : 128;
        });
    }
    const tex = new THREE.DataArrayTexture(levels[0].data, size, size, N);
    tex.format = THREE.RGBAFormat;
    tex.type = THREE.UnsignedByteType;
    tex.colorSpace = THREE.SRGBColorSpace;                           // (sRGB decodes the colour; the alpha stays linear)
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = levels.length > 1 ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.anisotropy = 8;
    tex.mipmaps = levels;
    tex.name = 'desert.sets';
    tex.onUpdate = () => {
        const gpu = renderer.backend.get(tex).texture, device = renderer.backend.device;
        if (!gpu || !device) return;
        for (let i = 1; i < levels.length; i++) {
            const { data, width, height } = levels[i];
            for (let L = 0; L < N; L++) {
                device.queue.writeTexture({ texture: gpu, mipLevel: i, origin: { x: 0, y: 0, z: L } }, data,
                    { offset: width * height * 4 * L, bytesPerRow: width * 4 }, { width, height, depthOrArrayLayers: 1 });
            }
        }
    };
    tex.needsUpdate = true;
    log(`[desert] look: ${N} CC0 sets in one ${size} x ${size} array, ${levels.length} levels`);
    return tex;
}

// the materials. masks: { _DMA: [[name, scale] x 4], _DMB: [...] } (desert.json); marks: { near, mid }, each
// { texture, reach } (the picture and its half extent in metres: 2048 and 8192)
export async function makeLook(THREE, { renderer, masks, marks, res = null, log = console.log } = {}) {
    if (!renderer?.backend) throw new Error('[desert] makeLook needs the renderer (its texture array is written through it)');
    const { float, vec2, vec3, vec4, int, texture, select, positionLocal, normalLocal, normalView, positionView, attribute, varying, mix } = THREE;
    const arr = await setArray(THREE, renderer, { res, log });
    const textures = new Set([arr, marks.near.texture, marks.mid.texture]);
    const S = (L, uv) => texture(arr, uv).depth(int(L));
    const sampler = (k) => {                                         // ncol and height over the array, for one material
        const { num, inv, N0, boxWeights } = k;
        const cache = new Map();
        const box = (L, co) => {
            const w = boxWeights(N0, 0.22);
            const ux = vec2(select(N0.x.lessThan(0.0), inv(co.y), co.y), co.z);
            const uy = vec2(select(N0.y.greaterThan(0.0), inv(co.x), co.x), co.z);
            const uz = vec2(select(N0.z.greaterThan(0.0), inv(co.y), co.y), co.x);
            return S(L, ux).mul(w.x).add(S(L, uy).mul(w.y)).add(S(L, uz).mul(w.z));
        };
        const samp = (key, P, proj, scale) => {
            const ck = `${key}|${proj}|${scale}`;                     // (one point node per material)
            if (!cache.has(ck)) {
                const s = SETS[key], w = s.tile[0] * scale, h = s.tile[1] * scale, L = LAYERS.indexOf(key);
                if (L < 0) throw new Error(`[desert] the set ${key} is not in the array`);
                cache.set(ck, proj === 'BOX' ? box(L, num(P).mul(vec3(1 / w, 1 / w, 1 / h))) : S(L, num(P).xy.mul(vec2(1 / w, 1 / h))));
            }
            return cache.get(ck);
        };
        const ncol = (key, P, proj = 'BOX', kk = 1.0, scale = 1.0) => {
            let n = samp(key, P, proj, scale).rgb.div(vec3(...SETS[key].mean.map((v) => Math.max(1e-3, v))));
            if (kk !== 1.0) n = n.mul(kk).add(1.0 - kk);
            return n;
        };
        const height = (key, P, proj = 'BOX', scale = 1.0, kk = 1.0) => samp(key, P, proj, scale).a.sub(0.5).mul(SETS[key].relief * kk * scale);
        return { ncol, height };
    };
    // the land's point and normal in its own metres: three's positionLocal and normalLocal, so the scrub's instanced
    // mounds read the ground's metres too
    const kitOf = () => kit(THREE, { position: positionLocal, normal: normalLocal });
    const scaleOf = Object.fromEntries([...masks._DMA, ...masks._DMB]);
    const maskNodes = () => {
        const a = varying(attribute('dmA', 'vec4')).setInterpolation('perspective', 'centroid');
        const b = varying(attribute('dmB', 'vec4')).setInterpolation('perspective', 'centroid');
        const out = {}, C = ['x', 'y', 'z', 'w'];
        masks._DMA.forEach(([n], i) => { out[n] = a[C[i]].mul(scaleOf[n]); });
        masks._DMB.forEach(([n], i) => { out[n] = b[C[i]].mul(scaleOf[n]); });
        return out;
    };

    // ------------------------------------------------------------------------------------------- desert.ground
    function groundMaterial() {
        const k = kitOf();
        const { num, P0: P, X, Y, nz, sm, inv, mixf, mixc, value, noise, max, abs, exp } = k;
        const { ncol, height } = sampler(k);
        const { groundPlain, tint } = groundFns(k, ncol);
        const a = maskNodes();
        // 1. THE TOWN'S OWN GROUND (its sets, its fronts, its regional tint, its scrub dots): the plain goes on from it
        let col = groundPlain(P), rough = num(0.95), h = float(0.0);
        const away = sm(a.town, 40.0, 260.0);                        // (nothing of the desert's own at the crossing)
        // the marks finer than the mesh: the 1 m picture within 2 km over the 4 m one to 8 km (R tracks, G beds and
        // bars, B the floor's drainage lines, A the sand sheet), each faded out over its last 50 m
        const markAt = ({ texture: t, reach }) => [texture(t, vec2(X.add(reach).div(2.0 * reach), Y.add(reach).div(2.0 * reach))),
            inv(sm(abs(X), reach - 60.0, reach - 10.0)).mul(inv(sm(abs(Y), reach - 60.0, reach - 10.0)))];
        const [cn, wn] = markAt(marks.near), [cm, wm] = markAt(marks.mid);
        const MK = mix(cm.mul(wm), cn, wn);
        const [R, G, B, A] = [MK.x, MK.y, MK.z, MK.w];
        // 2. desert pavement on the older surfaces between the channels, and the aprons' gravel; the floor past 1.5 km
        //    going to the grey-brown of varnished gravel
        const nOld = noise(P, 1.0 / 650.0, 3.0, { off: [11.0, 3.0, 0.0] });
        const clear = inv(max(G, A));
        let pav = max(sm(nOld, 0.50, 0.62), sm(noise(P, 1.0 / 210.0, 3.0, { off: [2.0, 8.0, 0.0] }), 0.56, 0.66).mul(0.7));
        pav = pav.mul(away).mul(clear);
        col = mixc(pav.mul(0.86), col, tint(ncol('stony', P, 'FLAT', 0.55), [0.20, 0.175, 0.145]));
        const silt = inv(sm(nOld, 0.37, 0.46)).mul(away).mul(clear);      // (pale silt where the sheet floods dried)
        col = mixc(silt.mul(0.65), col, tint(ncol('mud_cracked', P, 'FLAT', 0.6), [0.47, 0.41, 0.31]));
        const far = sm(a.town, 1200.0, 4500.0).mul(0.42);
        col = mixc(far, col, tint(ncol('gravel_ground', P, 'FLAT', 0.6), [0.30, 0.27, 0.22]));
        const rill = sm(B, 0.12, 0.75).mul(away);                    // (the floor's drainage lines: finer, darker silt)
        col = mixc(rill.mul(0.8), col, tint(ncol('dry_ground', P, 'FLAT', 0.7), [0.20, 0.17, 0.13]));
        const apr = sm(a.apron, 1.5, 30.0).mul(away);
        col = mixc(apr.mul(0.75), col, tint(ncol('sandy_gravel', P, 'FLAT', 0.7), [0.43, 0.38, 0.30]));
        // 3. the wadis: pale beds of sand and grit, their bars greyer with the scrub on them
        const inBed = max(sm(G, 0.30, 0.55), sm(a.bed, 0.3, 0.9).mul(inv(sm(abs(X), 7900.0, 8100.0))));
        col = mixc(inBed.mul(0.85), col, tint(ncol('gravel_sand', P, 'FLAT', 0.75), [0.47, 0.41, 0.32]));
        col = mixc(sm(G, 0.68, 0.95).mul(0.8), col, tint(ncol('sandy_gravel', P, 'FLAT', 0.8), [0.37, 0.33, 0.26]));
        // 4. the tracks: packed, paler, in the town's own track set and tint
        const trk = sm(R, 0.08, 0.6);
        const cTrk = value(tint(ncol('gravel_ground', P, 'FLAT', 0.85), [0.38, 0.32, 0.23]), float(0.95).add(noise(P, 0.08, 3.0).mul(0.22)));
        col = mixc(trk.mul(0.9), col, cTrk);
        rough = mixf(trk, rough, 0.88);
        // 5. the sand sheet round the dunes, and the dunes: ripples on the windward sides, smooth slip faces
        col = mixc(sm(A, 0.15, 0.9).mul(away).mul(0.7), col, tint(ncol('pale_sand', P, 'FLAT', 1.0), [0.47, 0.37, 0.25]));
        const dune = sm(a.sand, 0.25, 2.5);
        const slip = inv(sm(nz, 0.86, 0.93));
        let cDune = mixc(slip, tint(ncol('dune_ripples', P, 'FLAT', 0.9), [0.56, 0.40, 0.24]), tint(ncol('pale_sand', P, 'FLAT', 1.0), [0.58, 0.43, 0.27]));
        cDune = value(cDune, float(0.9).add(sm(a.sand, 2.0, 40.0).mul(0.12)));          // (thin sand in the troughs greyer)
        col = mixc(dune, col, cDune);
        h = mixf(dune, h, height('dune_ripples', P, 'FLAT').mul(inv(slip)));
        // 6. the escarpment: beds in its cliff band, scree on its talus, caprock on its top
        const esc = sm(a.esc, 0.5, 6.0);
        const cliff = inv(sm(nz, 0.45, 0.72));
        const talus = inv(sm(nz, 0.80, 0.95)).mul(inv(cliff));
        const top = sm(nz, 0.93, 0.985).mul(sm(a.esc, 110.0, 170.0));
        // (a 3.6 m rock tile is a pixel at 1.5 km: the same scans again at 40 m and 112 m give the joints and ledges at
        //  the size the lens sees; desert varnish runs down from the rim)
        const grain = ncol('cliff_rock', P, 'BOX', 0.8).mul(ncol('cliff_rock', P, 'BOX', 0.9, 11.0).mul(ncol('cliff_warm', P, 'BOX', 0.7, 28.0)));
        const varnish = sm(noise(P, 1.0, 3.0, { off: [7.0, 2.0, 0.0], stretch: [1.0 / 21.0, 1.0 / 21.0, 1.0 / 240.0] }), 0.47, 0.70);
        const warp = noise(P, 1.0 / 380.0, 2.0, { off: [3.0, 1.0, 0.0] }).sub(0.5).mul(12.0);
        const f = a.esc.add(warp).div(200.0);
        let beds = vec3(...STRATA.base);
        for (const [lo, w, rgb] of STRATA.beds) beds = mixc(sm(f, lo - w, lo + w), beds, rgb);
        const cCliff = value(tint(grain, beds), inv(varnish.mul(0.42)));
        col = mixc(esc.mul(talus.mul(0.9)), col, tint(ncol('scree', P, 'BOX', 0.6), [0.37, 0.32, 0.26]));
        col = mixc(esc.mul(top.mul(0.8)), col, tint(ncol('caprock', P, 'FLAT', 0.8), [0.36, 0.31, 0.24]));
        col = mixc(esc.mul(cliff), col, cCliff);
        // 7. the ranges and inselbergs: dark rock on the steep, dark debris below it
        const mtn = sm(a.mtn, 0.5, 6.0);
        const deb = inv(sm(nz, 0.88, 0.975));
        const steep = inv(sm(nz, 0.55, 0.85));
        col = mixc(mtn.mul(deb), col, tint(ncol('dark_gravel', P, 'FLAT', 0.6), [0.135, 0.12, 0.105]));
        col = mixc(mtn.mul(steep), col, tint(ncol('dark_rock', P, 'BOX', 0.45).mul(ncol('cliff_rock', P, 'BOX', 0.8, 14.0)), [0.075, 0.07, 0.064]));
        const rocky = max(esc.mul(max(cliff, talus)), mtn.mul(deb));
        h = mixf(rocky, h, height('cliff_rock', P, 'BOX', 1.0, 0.6).add(height('cliff_rock', P, 'BOX', 11.0, 0.35)));
        rough = mixf(rocky, rough, 0.9);
        // 8. the land's slow variation at the kilometre
        col = value(col, float(0.93).add(noise(P, 1.0 / 2400.0, 2.0, { off: [5.0, 9.0, 0.0] }).mul(0.14)));
        const m = new THREE.MeshStandardNodeMaterial();
        m.colorNode = vec4(num(col), 1.0);
        m.roughnessNode = num(rough);
        m.metalnessNode = float(0.0);
        // THE RELIEF (Blender's Bump, strength 1, distance 1): the surface gradient from the height's screen derivatives
        const N = normalView, dPdx = positionView.dFdx(), dPdy = positionView.dFdy();
        const Rx = dPdy.cross(N), Ry = N.cross(dPdx), det = dPdx.dot(Rx);
        const grad = Rx.mul(h.dFdx()).add(Ry.mul(h.dFdy()));
        m.normalNode = det.abs().mul(N).sub(det.sign().mul(grad)).normalize();
        // THE AIR past the town's haze box, mixed in before the scene's fog (which is the town's dust, world())
        const airF = float(1.0).sub(exp(max(positionView.length().sub(AIR.d0), 0.0).mul(-AIR.sigma)));
        const airC = vec3(...AIR.color.map((v) => v * AIR.strength));
        const setupFog = m.setupFog;
        m.setupFog = function (builder, outputNode) {
            return setupFog.call(this, builder, vec4(mix(outputNode.rgb, airC, airF), outputNode.a));
        };
        m.name = 'desert.ground';
        return m;
    }

    // ------------------------------------------------------------------------------------------- desert.scrub
    function scrubMaterial() {
        const k = kitOf();
        const { P0: P, nz, sm, mixc, value, noise, palette, float: f } = k;
        const r = attribute('inst', 'vec4').x;                       // (the shrub's own number)
        let col = value(palette(r, SCRUB), f(0.7).add(noise(P, 3.5, 3.0).mul(0.6)));      // (twigs and the gaps between)
        col = mixc(sm(nz, 0.4, 0.95).mul(0.35), col, DUST);          // (the dust on what faces up)
        const m = new THREE.MeshStandardNodeMaterial();
        m.colorNode = vec4(col, 1.0);
        m.roughnessNode = float(0.9);
        m.metalnessNode = float(0.0);
        m.side = THREE.DoubleSide;                                   // (EEVEE draws both sides)
        m.name = 'desert.scrub';
        return m;
    }

    // ------------------------------------------------------------------------------------------- the town's plane
    // the town's own ground where no town stands (its 'ground': groundPlain), for a desert with no town in it
    function plainMaterial() {
        const k = kitOf();
        const { ncol } = sampler(k);
        const m = new THREE.MeshStandardNodeMaterial();
        m.colorNode = vec4(groundFns(k, ncol).groundPlain(k.P0), 1.0);
        m.roughnessNode = float(0.95);
        m.metalnessNode = float(0.0);
        m.name = 'desert.plain';
        return m;
    }

    const ground = groundMaterial(), scrub = scrubMaterial();
    let plain = null;
    return {
        ground, scrub, textures, array: arr,
        plain() { return plain || (plain = plainMaterial()); },
        dispose() {
            for (const m of [ground, scrub, plain]) if (m) m.dispose();
            for (const t of textures) t.dispose();
        },
    };
}
