// eidoverse/layered_material.js — ONE layered material that reads a baked asset's maps, in the order things happen to
// it, in TSL: the three.js edition's port of the Blender edition's eidoblend.materials.layered (its baked_material and
// the node layer it is written in). Dynamic ESM; scene scripts import it inside setup():
//
//   const LM = await import(new URL('layered_material.js', EIDOVERSE_DIR).href);
//   const maps = await LM.loadBake(THREE, new URL('../assets/models/my_prop/', import.meta.url), 'my_prop');
//   const photos = await LM.photos(THREE);                       // the CC0 grain, fingerprints, chips, scratches
//   const mat = LM.bakedMaterial(THREE, maps, substrates, { photos, hands, knocks, stains, condition });
//
// The maps are what the Blender edition's GPU baker (blender/tools/gpu_bake.py) writes from a high and its low:
// normal (OpenGL, MikkTSpace: the GLB carries its tangents), masks_a (R AO, G cavity, B fine curvature), masks_b (R
// exposed-edge nearness, G broad curvature, B inside-corner nearness), id (the substrate ID x 16 per texel), and
// optionally marks (markings at real size) and relief (moulded detail the normal map carries). Each layer is a whole
// material blended over the one below by one factor, each factor from a cause:
//
//   SUBSTRATE  chosen per texel by the baked ID through its row of the tables (Substrate: base and worn colours,
//              roughness, metalness, how much it wears, polishes, dusts and grimes, its mottle, rub and scratches);
//              each takes the grain of a CC0 photograph laid in the asset's millimetres by box projection
//   MARKINGS   a pale fill under the wear;  GRIME in the cavities;  WEAR in two stages from the edge map (RUB: the
//              coating thinned paler and smoother; CHIP: down to what lies beneath, its outline broken by a
//              photographed chip pattern, only where knocks go);  HANDLING polish and fingerprints where hands go;
//              DUST in the cavities and on what faces up;  STAINS with their causes; then cavity and AO into the
//              colour, the normal map, and a whisper of bump for a chip's lip and the dust's film.
//
// The asset's space is its Blender space (+Z up), in which every table is written: a glTF exported Y-up from Blender
// holds (x, y, z) as (x, z, -y), and kit() reads the local position and normal back that way (axes: 'blender' for a
// geometry already Z-up). Every number of the stack is the substrate's or the call's; `condition` scales wear,
// polish, dust and grime together. kit(THREE) is the node layer the stack is written in (smoothstep, Blender's fBm
// noise and Voronoi, box projection, pictures laid square through a rectangle, the bump), for asset looks of their own.
// Guide: docs/props-and-sets.md ("The layered material on baked maps").

export const LUM = [0.2126, 0.7152, 0.0722];

// The CC0 photographs the stack reads (ambientCG, fetched once into eidoverse/assets/cache/ by fetchPBR):
// [id, res, colour power, colour tiles/m, roughness amount, roughness tiles/m]: 0 anodised aluminium's satin,
// 1 phosphated steel's crystal, 2 moulded polymer's smudged roughness (no colour)
export const GRAIN_SETS = [['Metal027', '2k', 0.8, 5.0, 0.35, 5.0], ['Metal063', '2k', 0.35, 10.0, 0.4, 6.0],
    ['Plastic013A', '2k', null, null, 0.5, 4.0]];
export const PHOTOS = { fingerprints: ['Fingerprints008', '2k', 'opacity'], chips: ['Metal021', '2k', 'displacement'],
    scratches: ['Metal008', '1k', 'rough'] };

// One substrate's row: base / worn colours (linear RGB); base_rough, base_metal; worn_metal, worn_rough (what a chip
// shows); wear, polish, dust, grime (how much of each layer it takes); grain (0, 1, 2: the photograph set; 4: none);
// mottle (slow tone variation), rub (how much paler a rub reads), scratches (fine scratch roughness)
export const SUBSTRATE_DEFAULTS = { base_rough: 0.45, base_metal: 0.0, worn_metal: 1.0, worn_rough: 0.30, wear: 1.0,
    polish: 0.5, dust: 0.6, grime: 0.7, grain: 4, mottle: 0.05, rub: 1.0, scratches: 0.3 };

// ------------------------------------------------------------------------------------------------ the node layer ---

export function kit(THREE, { axes = 'gltf' } = {}) {
    const { float, vec2, vec3, abs, clamp, mix, max, select, smoothstep, texture, dot, cross, normalize, sign, dFdx,
        dFdy, length, positionLocal, normalLocal, positionView, faceDirection, mx_noise_float, mx_worley_noise_float } = THREE;
    const num = (x) => (typeof x === 'number' ? float(x) : x);
    // per-pixel screen derivatives (WGSL's fine ones; both axes read the same way, so the bump's frame is consistent)
    const fineX1 = THREE.wgslFn('fn eido_dxf1(v: f32) -> f32 { return dpdxFine(v); }');
    const fineY1 = THREE.wgslFn('fn eido_dyf1(v: f32) -> f32 { return dpdyFine(v); }');
    const fineX3 = THREE.wgslFn('fn eido_dxf3(v: vec3<f32>) -> vec3<f32> { return dpdxFine(v); }');
    const fineY3 = THREE.wgslFn('fn eido_dyf3(v: vec3<f32>) -> vec3<f32> { return dpdyFine(v); }');
    // the point and the normal in the asset's own (Blender) space; metres, and the point in millimetres
    const P = axes === 'gltf' ? vec3(positionLocal.x, positionLocal.z.negate(), positionLocal.y) : positionLocal;
    const N = normalize(axes === 'gltf' ? vec3(normalLocal.x, normalLocal.z.negate(), normalLocal.y) : normalLocal);
    const Pmm = P.mul(1000.0);
    const sm = (x, lo, hi) => smoothstep(num(lo), num(hi), num(x));
    const inv = (x) => float(1.0).sub(x);
    const lin = (x, a0, a1, b0 = 0.0, b1 = 1.0, cl = false) => {
        let f = num(x).sub(a0).div(num(a1).sub(a0));
        if (cl) f = clamp(f, 0.0, 1.0);
        return num(b0).add(f.mul(num(b1).sub(b0)));
    };
    const mixc = (f, a, b) => mix(num(a), num(b), clamp(num(f), 0.0, 1.0));       // Blender's Mix: the factor clamped
    const value = (c, v) => num(c).mul(num(v));                                     // Hue/Saturation/Value's Value
    const lum = (c) => dot(c.rgb ?? c, vec3(...LUM));
    const rgb = (c) => vec3(c[0], c[1], c[2]);
    // Blender's Noise Texture (fBm of Perlin noise, normalized to 0..1, lacunarity 2) of a vector at `scale` per unit:
    // detail octaves past the first (fractional ones blended), rough the amplitude kept per octave; off / stretch: a
    // Mapping (scale, then location) before it. Every octave is kept, as Blender evaluates them: a fine noise then
    // speckles at a pixel's scale as it does in Blender's renders. antialias: true fades each octave to its mean as it
    // passes a pixel (from one cycle a pixel to two), for a smoother surface far off.
    function noise(p, scale, detail = 2.0, { off = null, stretch = null, rough = 0.5, antialias = false } = {}) {
        let q = p;
        if (stretch) q = q.mul(vec3(...stretch));
        if (off) q = q.add(vec3(...off));
        q = q.mul(scale);
        const fw = antialias ? length(abs(dFdx(q)).add(abs(dFdy(q)))) : null;
        const octave = (fs) => {
            const n = mx_noise_float(fs === 1.0 ? q : q.mul(fs));
            return antialias ? n.mul(float(1.0).sub(smoothstep(1.0, 2.0, fw.mul(fs)))) : n;
        };
        let sum = null, amp = 1.0, maxamp = 0.0, fs = 1.0;
        const oct = Math.floor(detail);
        for (let i = 0; i <= oct; i++) {
            const n = octave(fs).mul(amp);
            sum = sum ? sum.add(n) : n;
            maxamp += amp; amp *= rough; fs *= 2.0;
        }
        let v = sum.div(maxamp).mul(0.5).add(0.5);
        const rmd = detail - oct;
        if (rmd > 1e-6) {
            const s2 = sum.add(octave(fs).mul(amp));
            v = mix(v, s2.div(maxamp + amp).mul(0.5).add(0.5), rmd);
        }
        return v;
    }
    // Blender's Voronoi (F1, Euclidean) distance at `scale` per unit
    const voronoi = (p, scale) => mx_worley_noise_float(p.mul(scale), 1.0);
    // Blender's BOX projection of an image at `co` (texture space), blended across `blend` as EEVEE blends it, by the
    // asset-space normal: three samples, each face's picture unflipped
    function boxWeights(n, blend) {
        const a = abs(n), nn = a.div(a.x.add(a.y).add(a.z));
        const limit = 0.5 + 0.5 * blend;
        const w0 = clamp(nn.div(vec3(nn.x.add(nn.y), nn.y.add(nn.z), nn.x.add(nn.z))).sub(0.5 * (1.0 - blend))
            .div(Math.max(1e-8, blend)), 0.0, 1.0);
        const wA = vec3(w0.x, inv(w0.x), 0.0), wB = vec3(0.0, w0.y, inv(w0.y)), wC = vec3(inv(w0.z), 0.0, w0.z);
        const wD = nn.mul(2.0 - limit).add(limit - 1.0).div(Math.max(1e-8, 2.0 * limit - 1.0));
        return select(nn.z.lessThan(nn.y.add(nn.x).mul(1.0 - limit)), wA,
            select(nn.x.lessThan(nn.y.add(nn.z).mul(1.0 - limit)), wB,
                select(nn.y.lessThan(nn.x.add(nn.z).mul(1.0 - limit)), wC, wD)));
    }
    function boxAt(tex, co, n = N, blend = 0.25) {
        const w = boxWeights(n, blend);
        const ux = vec2(select(n.x.lessThan(0.0), inv(co.y), co.y), co.z);
        const uy = vec2(select(n.y.greaterThan(0.0), inv(co.x), co.x), co.z);
        const uz = vec2(select(n.z.greaterThan(0.0), inv(co.y), co.y), co.x);
        return texture(tex, ux).mul(w.x).add(texture(tex, uy).mul(w.y)).add(texture(tex, uz).mul(w.z));
    }
    // a photograph laid by box projection on the asset (metres), per_m tiles a metre
    const box = (tex, perM, blend = 0.25, p = P) => boxAt(tex, p.mul(perM), N, blend);
    // a ramp along one axis in mm: ('x' | 'y' | 'z', a, b): rising smoothstep a -> b when a < b, else falling
    function ramp(spec) {
        const c = Pmm[spec[0]];
        const a = spec[1], b = spec[2];
        return a < b ? sm(c, a, b) : inv(sm(c, b, a));
    }
    function softBox(lo, hi, soft) {
        let g = null;
        for (let i = 0; i < 3; i++) {
            const c = Pmm['xyz'[i]];
            const f = sm(c, lo[i] - soft, lo[i] + soft).mul(inv(sm(c, hi[i] - soft, hi[i] + soft)));
            g = g ? g.mul(f) : f;
        }
        return g;
    }
    const foldMax = (items) => items.reduce((acc, s) => (acc ? max(acc, s) : s), null);
    // Blender's 'Cubic' image interpolation (a cubic B-spline from four bilinear taps) of a texture at uv
    function cubic(tex, uvn) {
        const size = vec2(tex.image.width, tex.image.height);
        const co = uvn.mul(size), tc = co.sub(0.5).floor().add(0.5), f = co.sub(tc);
        const f2 = f.mul(f), f3 = f2.mul(f);
        const w3 = f3.div(6.0), w0 = w3.negate().add(f2.mul(0.5)).sub(f.mul(0.5)).add(1.0 / 6.0);
        const w1 = f3.mul(0.5).sub(f2).add(2.0 / 3.0), w2 = vec2(1.0).sub(w0).sub(w1).sub(w3);
        const s0 = w0.add(w1), s1 = w2.add(w3);
        const a = tc.sub(1.0).add(w1.div(s0)).div(size), b = tc.add(1.0).add(w3.div(s1)).div(size);
        return texture(tex, a).mul(s0.x.mul(s0.y)).add(texture(tex, vec2(b.x, a.y)).mul(s1.x.mul(s0.y)))
            .add(texture(tex, vec2(a.x, b.y)).mul(s0.x.mul(s1.y))).add(texture(tex, b).mul(s1.x.mul(s1.y)));
    }
    // a picture drawn at real size laid square through its own rectangle: {u: [axis, mm0, mm1], v: [axis, mm0, mm1]}
    // (mm1 -> mm0 shows a picture drawn for the other side unmirrored), read with Blender's Cubic interpolation;
    // outside it the picture is clipped (0); facing: [axis 0..2, sign]: only faces that look that way -> { color, gate }
    function picture(tex, spec, facing = null) {
        const u = lin(Pmm[spec.u[0]], spec.u[1], spec.u[2]);
        const v = lin(Pmm[spec.v[0]], spec.v[1], spec.v[2]);
        const inside = u.greaterThanEqual(0.0).and(u.lessThanEqual(1.0)).and(v.greaterThanEqual(0.0)).and(v.lessThanEqual(1.0));
        const color = select(inside, cubic(tex, vec2(u, v)), THREE.vec4(0.0));
        const gate = facing ? sm(N['xyz'[facing[0]]].mul(facing[1]), 0.6, 0.85) : float(1.0);
        return { color, gate };
    }
    // Blender's Bump node (Strength 1, Distance 1): a height in metres over a view-space normal, from its screen
    // derivatives (per pixel, not per 2 x 2 block: a relief a few pixels wide would step), as EEVEE computes it
    // (seen edge-on, where a pixel's footprint stretches along the view, the bend fades out: one sample a pixel there
    // gives a random normal, which Blender's many samples average away)
    function bump(h, nView) {
        const dPdx = fineX3(positionView), dPdy = fineY3(positionView);
        const Rx = cross(dPdy, nView), Ry = cross(nView, dPdx);
        const det = dot(dPdx, Rx);
        const grad = Rx.mul(fineX1(h)).add(Ry.mul(fineY1(h)));
        const b = abs(det).mul(nView).sub(sign(det).mul(grad).mul(faceDirection));
        const bent = select(dot(b, b).greaterThan(1e-30), normalize(b), nView);       // (a degenerate footprint: unbent)
        const facing = abs(det).div(length(Rx).mul(length(Ry)).add(1e-30));
        return normalize(mix(nView, bent, smoothstep(0.02, 0.15, facing)));
    }
    // a vertex attribute the stack reads (vec4), read at the pixel's covered sample (centroid: never extrapolated
    // past its triangle at a multisampled edge) and kept within 0..1
    const vertexData = (name) => clamp(THREE.varying(THREE.attribute(name, 'vec4')).setInterpolation('perspective', 'centroid'), 0.0, 1.0);
    return { P, N, Pmm, sm, inv, lin, mixc, value, lum, rgb, num, noise, voronoi, box, boxAt, boxWeights, ramp, softBox,
        foldMax, cubic, picture, bump, vertexData };
}

// ------------------------------------------------------------------------------------------------ the textures ---
// A material may sample 16 textures on this stack (WebGPU's default per-stage limit), and the renderer's own (the
// environment, a shadow map) count too, so the stack packs what it reads into 10: the bake's masks two to a texture
// with their marks and relief, each grain photograph's luminance and roughness in one.

const _bytes = async (u) => (u instanceof Uint8Array ? u : await Deno.readFile(u));

// a box-filtered mip chain over RGBA bytes (this stack's automatic mip pass samples zeros: the engine uploads its own)
export function mipChain(data, w, h) {
    const levels = [{ data, width: w, height: h }];
    let sw = w, sh = h, src = data;
    while (sw > 1 || sh > 1) {
        const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
        const dst = new Uint8Array(dw * dh * 4);
        for (let y = 0; y < dh; y++) {
            const y0 = Math.min(sh - 1, y * 2), y1 = Math.min(sh - 1, y * 2 + 1);
            for (let x = 0; x < dw; x++) {
                const x0 = Math.min(sw - 1, x * 2), x1 = Math.min(sw - 1, x * 2 + 1);
                const o = (y * dw + x) * 4, a = (y0 * sw + x0) * 4, b = (y0 * sw + x1) * 4, c = (y1 * sw + x0) * 4, d = (y1 * sw + x1) * 4;
                for (let k = 0; k < 4; k++) dst[o + k] = (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
            }
        }
        levels.push({ data: dst, width: dw, height: dh });
        sw = dw; sh = dh; src = dst;
    }
    return levels;
}

// RGBA bytes as a texture with its mip chain (or nearest and unfiltered)
export function dataTexture(THREE, data, w, h, { srgb = false, repeat = true, nearest = false } = {}) {
    const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.wrapS = t.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
    t.generateMipmaps = false;
    t.flipY = false;
    if (nearest) {
        t.magFilter = t.minFilter = THREE.NearestFilter;
    } else {
        t.magFilter = THREE.LinearFilter;
        t.minFilter = THREE.LinearMipmapLinearFilter;
        t.mipmaps = mipChain(data, w, h);
        t.anisotropy = 8;
    }
    t.needsUpdate = true;
    return t;
}

// one picture as a texture: data (linear) or colour (sRGB); flipY false for maps baked on a glTF's UVs
export async function loadTexture(THREE, src, { srgb = false, flipY = true, repeat = true, nearest = false } = {}) {
    const t = await globalThis.loadImageTexture(await _bytes(src), { srgb, flipY });
    t.wrapS = t.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
    if (nearest) {
        t.magFilter = t.minFilter = THREE.NearestFilter;
        t.mipmaps = [];
        t.generateMipmaps = false;
        t.needsUpdate = true;
    }
    return t;
}

// several pictures' channels in one RGBA texture: chans = four [texture, channel] (or null: 0), all one size
export function packChannels(THREE, chans, opts = {}) {
    const src = chans.find(Boolean)[0].image, w = src.width, h = src.height, n = w * h;
    const out = new Uint8Array(n * 4);
    chans.forEach((c, k) => {
        if (!c) return;
        const [tex, ch] = c, d = tex.image.data;
        if (tex.image.width !== w || tex.image.height !== h) throw new Error('packChannels: the pictures differ in size');
        for (let i = 0; i < n; i++) out[i * 4 + k] = d[i * 4 + ch];
    });
    return dataTexture(THREE, out, w, h, opts);
}

// sRGB <-> linear for 8-bit values
const _S2L = new Float32Array(256).map((_, i) => { const c = i / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
const _l2s = (l) => Math.round(255 * (l <= 0.0031308 ? 12.92 * l : 1.055 * l ** (1 / 2.4) - 0.055));

// the mean of a picture's stored values (its RGB, or one channel), every 97th pixel, as the Blender edition reads it
// (bpy's pixels of an 8-bit picture are its stored values, sRGB-encoded for a colour photograph)
export function meanOf(tex, ch = null) {
    const d = tex.image.data, n = d.length / 4;
    let s = 0, k = 0;
    for (let i = 0; i < n; i += 97) {
        const o = i * 4;
        s += ch === null ? (d[o] + d[o + 1] + d[o + 2]) / 3 : d[o + ch];
        k++;
    }
    return s / k / 255;
}

const _fileURL = (dir) => (dir instanceof URL ? dir
    : new URL(`file:///${String(dir).replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/?$/, '/')}`));

// gpu_bake.py's maps of a bake beside each other in `dir` (a file URL or a folder path) named <name>_<map>.png, as the
// stack reads them: { normal, masks (AO, cavity, fine curvature, marks), masks2 (edge, broad curvature, inside corner,
// relief), id (nearest, never filtered) }; marks and relief are 0 where the bake has none
export async function loadBake(THREE, dir, name) {
    const base = _fileURL(dir);
    const read = async (k, opts) => {
        const u = new URL(`${name}_${k}.png`, base);
        try { await Deno.stat(u); } catch { return null; }
        return await loadTexture(THREE, u, { flipY: false, repeat: false, ...opts });
    };
    const raw = {};
    for (const k of ['normal', 'masks_a', 'masks_b', 'id', 'marks', 'relief']) {
        raw[k] = await read(k, { nearest: k === 'id' });
        if (!raw[k] && ['normal', 'masks_a', 'masks_b', 'id'].includes(k)) throw new Error(`loadBake: ${name}_${k}.png is missing in ${base.pathname}`);
    }
    const masks = packChannels(THREE, [[raw.masks_a, 0], [raw.masks_a, 1], [raw.masks_a, 2], raw.marks ? [raw.marks, 0] : null], { repeat: false });
    const masks2 = packChannels(THREE, [[raw.masks_b, 0], [raw.masks_b, 1], [raw.masks_b, 2], raw.relief ? [raw.relief, 0] : null], { repeat: false });
    for (const k of ['masks_a', 'masks_b', 'marks', 'relief']) raw[k]?.dispose();
    return { normal: raw.normal, masks, masks2, id: raw.id, hasMarks: !!raw.marks, hasRelief: !!raw.relief };
}

// The CC0 photographs the stack reads, fetched into the shared library on first use (fetchPBR):
// { grain: [{ tex (R the colour's luminance, sRGB-encoded; G its roughness), spec, meanC, meanR }],
//   fingerprints, chips, scratches: { tex, mean } }. meanC is the colour's mean as Blender reads it (its stored RGB)
export async function photos(THREE, { grainSets = GRAIN_SETS, extra = PHOTOS } = {}) {
    const out = { grain: [] };
    for (const spec of grainSets) {
        const { files } = await globalThis.fetchPBR(spec[0], { res: spec[1] });
        const rough = await loadTexture(THREE, files.rough);
        const w = rough.image.width, h = rough.image.height, n = w * h;
        const data = new Uint8Array(n * 4), r = rough.image.data;
        let meanC = null;
        if (spec[2] !== null) {
            const colour = await loadTexture(THREE, files.diff, { srgb: true });
            if (colour.image.width !== w || colour.image.height !== h) throw new Error(`photos: ${spec[0]}'s maps differ in size`);
            meanC = meanOf(colour);
            const c = colour.image.data;
            for (let i = 0; i < n; i++) {
                const o = i * 4;
                data[o] = _l2s(0.2126 * _S2L[c[o]] + 0.7152 * _S2L[c[o + 1]] + 0.0722 * _S2L[c[o + 2]]);
            }
            colour.dispose();
        }
        for (let i = 0; i < n; i++) { data[i * 4 + 1] = r[i * 4]; data[i * 4 + 3] = 255; }
        out.grain.push({ tex: dataTexture(THREE, data, w, h), spec, meanC, meanR: meanOf(rough) });
        rough.dispose();
    }
    for (const [k, [id, res, map]] of Object.entries(extra)) {
        const { files } = await globalThis.fetchPBR(id, { res });
        const tex = await loadTexture(THREE, files[map]);
        out[k] = { tex, mean: meanOf(tex) };
    }
    return out;
}

// --------------------------------------------------------------------------------------------- the stack ---------

function rowsOf(substrates, condition) {
    const c = { wear: 1, polish: 1, dust: 1, grime: 1, ...(condition || {}) };
    const rows = {};
    for (const [i, s0] of Object.entries(substrates)) {
        const s = { ...SUBSTRATE_DEFAULTS, ...s0 };
        rows[+i] = { ...s, wear: s.wear * c.wear, polish: s.polish * c.polish, dust: s.dust * c.dust, grime: s.grime * c.grime };
    }
    return rows;
}

// The layered material (see the head of this file). maps: loadBake's textures; substrates: { ID: row } (1..15);
// photos: photos()'s textures (required); hands: [[lo mm], [hi mm], soft mm] soft boxes; knocks: [ramp] (an extremity);
// stains: [[[ramp, ...], amount]] (a product of ramps); condition: { wear, polish, dust, grime } scales; axes: 'gltf'
// (the default) or 'blender'; uvName: the UV attribute ('uv'). -> MeshStandardNodeMaterial; its .userData.layers holds
// the factors (ao, cavity, edge, chip, dust, hands) as nodes for probes.
export function bakedMaterial(THREE, maps, substrates, {
    photos: PH, hands = [], knocks = [], stains = [], condition = null, markColor = [0.55, 0.55, 0.53],
    dustColor = [0.40, 0.34, 0.25], sootColor = [0.012, 0.011, 0.010], axes = 'gltf', uvName = 'uv', name = 'layered',
    envAO = true,
} = {}) {
    if (!PH) throw new Error('bakedMaterial: pass { photos } (await photos(THREE))');
    const { float, vec3, max, min, clamp, texture, uv, attribute, uniformArray, normalMap, pow, select } = THREE;
    const K = kit(THREE, { axes });
    const { P, N, sm, inv, mixc, value, rgb, noise, box, ramp, softBox, foldMax, bump } = K;
    const UV = uvName === 'uv' ? uv() : attribute(uvName, 'vec2');
    // the six columns of the substrate rows in one table, 16 IDs each: row k of ID i at k * 16 + i
    const rows = rowsOf(substrates, condition);
    const cols = [(r) => r.base, (r) => r.worn, (r) => [r.base_rough, r.base_metal, r.worn_metal],
        (r) => [r.worn_rough, r.wear, r.polish], (r) => [r.dust, r.grime, r.grain], (r) => [r.mottle, r.rub, r.scratches]];
    const table = [];
    for (const f of cols) for (let i = 0; i < 16; i++) table.push(rows[i] ? new THREE.Vector4(...f(rows[i]), 0) : new THREE.Vector4(0, 0, f === cols[4] ? 4 : 0, 0));
    const TBL = uniformArray(table, 'vec4');
    const ma = texture(maps.masks, UV), mb = texture(maps.masks2, UV);
    const ao = ma.r, cav = ma.g, cfine = ma.b, markg = ma.a;
    const edge = mb.r, cbroad = mb.g, relief = mb.a;
    const id = texture(maps.id, UV).level(0).r.mul(255.0 / 16.0).round().toInt();
    const row = (k) => TBL.element(id.add(k * 16));
    const baseCol = row(0).xyz, wornCol = row(1).xyz;
    const c2 = row(2), c3 = row(3), c4 = row(4), c5 = row(5);
    const bRough = c2.x, bMetal = c2.y, wMetal = c2.z;
    const wRough = c3.x, wearAmt = c3.y, polAmt = c3.z;
    const dustAmt = c4.x, grimeAmt = c4.y, sel = c4.z;
    const mottle = c5.x, rubVal = c5.y, scrAmt = c5.z;
    const msk = [inv(sm(sel, 0.4, 0.6)), sm(sel, 0.4, 0.6).mul(inv(sm(sel, 1.4, 1.6))),
        sm(sel, 1.4, 1.6).mul(inv(sm(sel, 2.4, 2.6)))];
    const nMacro = noise(P, 16.0, 2.0), nMeso = noise(P, 85.0, 3.0), nFine = noise(P, 650.0, 2.0);
    const nGate = noise(P, 11.0, 2.0, { off: [3.1, 1.7, 0.4] });
    const cMacro = nMacro.sub(0.5), cMeso = nMeso.sub(0.5), cFine = nFine.sub(0.5);

    // 1. THE SUBSTRATE: tint x the photograph's own variation around 1, grain in roughness
    const toLinear = (c) => select(c.lessThanEqual(0.04045), c.div(12.92), pow(c.add(0.055).div(1.055), 2.4));
    let vs = null, ms = null, rs = null;
    PH.grain.slice(0, 3).forEach((g, gi) => {
        const sR = box(g.tex, g.spec[5]);
        if (g.meanC !== null) {
            const sC = g.spec[3] === g.spec[5] ? sR : box(g.tex, g.spec[3]);
            const bw = toLinear(sC.r);                         // the photograph's luminance in linear light
            const v = pow(max(bw.div(Math.max(g.meanC, 1e-3)), 0.0), g.spec[2]).mul(msk[gi]);
            vs = vs ? vs.add(v) : v;
            ms = ms ? ms.add(msk[gi]) : msk[gi];
        }
        const r = sR.g.sub(g.meanR).mul(msk[gi].mul(g.spec[4]));
        rs = rs ? rs.add(r) : r;
    });
    const variation = vs ? vs.add(inv(ms)) : float(1.0);
    let rough = rs ? bRough.add(rs) : bRough;
    let colr = value(baseCol, variation.mul(float(1.0).add(cMacro.mul(2.0).mul(mottle).add(cMeso.mul(mottle)))));
    rough = rough.add(cFine.mul(0.04).add(cMacro.mul(0.04)));
    const scr = box(PH.scratches.tex, 4.0).r.sub(PH.scratches.mean);
    rough = rough.add(scr.mul(scrAmt.mul(0.35)));
    let metal = bMetal;
    // 2. MARKINGS: a pale fill in the coating; relief: what a texel averages away goes into roughness
    if (maps.hasMarks) {
        colr = mixc(markg.mul(0.9), colr, rgb(markColor));
        rough = mixc(markg, rough, 0.6);
    }
    if (maps.hasRelief) rough = rough.add(relief.mul(0.08));
    // 3. GRIME in the cavities
    const gr = clamp(sm(inv(ao), 0.2, 0.7).mul(0.6).add(sm(inv(cav), 0.1, 0.5).mul(0.9))
        .mul(grimeAmt.mul(float(0.6).add(cMeso.mul(0.8)))), 0.0, 1.0);
    colr = value(colr, float(1.0).sub(gr.mul(0.6)));
    rough = rough.add(gr.mul(0.12));
    // 4. WEAR, two stages, where knocks go
    const chips = float(PH.chips.mean).sub(box(PH.chips.tex, 3.0, 0.3).r);
    const eRub = sm(edge, 0.68, 0.96), eChip = sm(edge, 0.88, 0.99);
    const drv = max(eRub, sm(cfine, 0.6, 0.85).mul(0.9)).add(sm(cbroad, 0.55, 0.75).mul(0.2));
    const ends = foldMax(knocks.map(ramp));
    const knock = sm(ao, 0.5, 0.85).mul(ends ? float(0.6).add(ends.mul(0.4)) : float(0.6));
    const gate = sm(nGate, 0.35, 0.7);
    let rub = sm(drv.mul(float(0.6).add(gate.mul(0.5))).add(cFine.mul(0.2)), 0.5, 0.6);
    rub = clamp(rub.mul(wearAmt), 0.0, 1.0);
    let chip = sm(eChip.mul(knock.mul(float(0.5).add(gate.mul(0.8)))).add(chips).add(cFine.mul(0.2)), 0.78, 0.84);
    chip = clamp(chip.mul(wearAmt), 0.0, 1.0);
    colr = value(colr, float(1.0).add(rub.mul(rubVal)));
    rough = rough.add(rub.mul(-0.07));
    colr = mixc(chip, colr, wornCol);
    metal = mixc(chip, metal, wMetal);
    rough = mixc(chip, rough, wRough);
    // 5. HANDLING: polish and fingerprints where hands go
    const hand = foldMax(hands.map(([lo, hi, soft]) => softBox(lo, hi, soft)));
    if (hand) {
        const fp = box(PH.fingerprints.tex, 5.0).r.mul(hand);
        const pol = hand.mul(polAmt).mul(float(0.5).add(gate.mul(0.5)));
        rough = rough.sub(pol.mul(0.12).add(fp.mul(polAmt.mul(0.14))));
        colr = value(colr, float(1.0).add(pol.mul(0.08)));
    }
    // 6. DUST: thin, in the cavities and on what faces up (the asset's own up)
    const lay = max(sm(inv(cav), 0.12, 0.55).mul(0.9).add(sm(inv(ao), 0.3, 0.8).mul(0.55)), sm(N.z, 0.55, 0.95).mul(0.25));
    const dust = clamp(sm(lay.add(cFine.mul(0.55).add(cMeso.mul(0.3))), 0.42, 0.78).mul(dustAmt).mul(inv(chip)), 0.0, 1.0);
    colr = mixc(dust.mul(0.5), colr, rgb(dustColor));
    rough = mixc(dust.mul(0.7), rough, 0.9);
    metal = metal.mul(inv(dust.mul(0.5)));
    // 7. STAINS with their causes
    const soot = foldMax(stains.map(([rs_, amount]) => rs_.map(ramp).reduce((a, b) => a.mul(b)).mul(amount)));
    if (soot) {
        const st = sm(soot.add(cMeso.mul(0.5)), 0.3, 0.8);
        colr = mixc(st.mul(0.9), colr, rgb(sootColor));
        rough = mixc(st, rough, 0.85);
        metal = metal.mul(inv(st));
    }
    // cavity and occlusion into the colour (a renderer's own AO reaches only screen scale)
    colr = value(colr, float(0.45).add(cav.mul(0.55)).mul(float(0.45).add(ao.mul(0.55))));
    const nMap = normalMap(texture(maps.normal, UV));
    const h = dust.mul(6e-6).sub(chip.mul(10e-6)).add(scr.mul(scrAmt.mul(2e-6)));
    const m = new THREE.MeshStandardNodeMaterial();
    m.name = name;
    m.colorNode = max(colr, vec3(0.0));
    m.roughnessNode = clamp(max(rough, 0.08), 0.0, 1.0);
    m.metalnessNode = min(max(metal, 0.0), 1.0);
    m.normalNode = bump(h, nMap);
    if (envAO) m.aoNode = ao;               // the baked AO also shades the environment's light in the recesses
    m.userData.layers = { ao, cavity: cav, curv: cfine, edge, chip, dust, hands: hand ?? float(0.0), id };
    return m;
}
