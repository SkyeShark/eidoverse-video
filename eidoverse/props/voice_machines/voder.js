// voder.js — the Bell Labs Voder, 1939 New York World's Fair (DAISY, verse 1).
//
// Homer Dudley's Voder: the vocoder's synthesis half, played by hand. Ten finger
// keys set the levels of ten band-pass filters (0–7500 Hz); a left-wrist bar
// switches buzz (voiced, bar down) and hiss (unvoiced, bar up); three right-thumb
// keys make the stop pairs t-d, p-b, k-g; a right-thumb "quiet" key drops ~20 dB;
// a right-foot pedal sets pitch. Sources: Dudley, Riesz & Watkins 1939 (dossier §1,
// §14.5–14.6), the Franklin Institute photo of the console, 1940 Bell Telephone
// Quarterly exhibit photos (reference sources: eidoverse/assets/models/voice_machines/SOURCES.md).
//
// HERO ASSET: modelled in Blender (eidoverse/assets/models/voice_machines/blender/era1_voder.py →
// voder.glb): face-modelled masses with real chamfers, speed-line
// grooves with chrome inlays, slotted key bed, meter with bezel/glass/needle, jewel
// lamp, fluted knobs, whisper toggle + switch bank, cast pedal with spring, stepped
// loudspeaker tower with louvres, fins, sunburst and braided cable. Materials are
// layered here: AmbientCG PBR sets (tex/) on UV0 + baked AO/edge/cavity masks on UV1
// + curvature edge wear + fingerprints/smears. Labels are canvas decals.
// Nobody is modelled at it — the console plays itself, keys going down.
//
//   const { build } = await import(new URL('props/voice_machines/voder.js', EIDOVERSE_DIR).href);
//   const voder = await build(THREE, {});
//   scene.add(voder.group);
//   voder.update(t, { voice: 0..1, power: 0..1 });          // it sings: plays its own keys to the voice
//   voder.update(t, { keys: [10 × 0..1], wrist, stops: [3], quiet, pedal, level, power });  // or full control
//
// update(t, st): st.voice (0..1, this era's voice loudness) animates everything when
//   keys aren't given: the demo fingering (pattern(t)) gated by the voice, needle and
//   grille glow on the voice. st.keys etc. override. Deterministic in t.
// parts: keys[0..9] (userData.band = [lo, hi] Hz), stopKeys[3] (t-d, p-b, k-g), quietKey,
//   wristBar, pedal, dial { needle, face }, lamp (pilot jewel), grille (backlit cloth),
//   console, speaker, uniforms { power, level }.
// Metres, +Y up, floor y = 0, facing +Z. ≈ 1.3 m wide × 1.35 m deep, tower 1.70 m.

// ════════════════════════════════════════════════════════════════════════════
// CRAFT KIT — the same block heads voder.js / mainframe.js / teletype.js.
// Self-contained on purpose (the prop contract allows only THREE + addons).
// Assets (GLB, baked masks, AmbientCG sets) are read from the library pack
// eidoverse/assets/models/voice_machines/, resolved from this module's own URL.
// Canvas labels become DataTextures with a CPU-built mip chain (the stack's
// automatic mip pass samples zeros).
// ════════════════════════════════════════════════════════════════════════════
async function craftKit(THREE) {
    const { RoundedBoxGeometry } = await import('npm:three@0.184.0/addons/geometries/RoundedBoxGeometry.js');
    const BGU = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');
    const {
        float, vec2, vec3, mix, smoothstep, max, dot, uv, texture, attribute, normalMap,
        positionLocal, positionWorld, positionView, normalView, normalWorldGeometry,
        dFdx, dFdy, faceDirection, mx_fractal_noise_float, mx_noise_float,
    } = THREE;

    const owned = new Set();
    const own = (x) => { owned.add(x); return x; };
    const rgb = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };
    const seedN = attribute('aSeed', 'float');
    const LUM = vec3(0.2126, 0.7152, 0.0722);

    // ── assets: eidoverse/assets/models/voice_machines/ (relative to this module, cwd-independent) ──
    const HERE = new URL('../../assets/models/voice_machines/', import.meta.url);
    const readBytes = async (rel) => await Deno.readFile(new URL(rel, HERE));
    async function loadTex(rel, { srgb = false, flipY = true, repeat = true } = {}) {
        const t = await globalThis.loadImageTexture(await readBytes(rel), { srgb, flipY });
        t.wrapS = t.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
        return own(t);
    }
    const sets = new Map();
    async function pbr(id, { metal = false, rough = true, normal = true } = {}) {
        const key = id + (metal ? '+m' : '') + (rough ? '+r' : '') + (normal ? '+n' : '');
        if (sets.has(key)) return sets.get(key);
        const b = `./tex/${id}/${id}_`;
        const s = { id, map: await loadTex(b + 'Color.jpg', { srgb: true }) };
        if (normal) s.normal = await loadTex(b + 'NormalGL.jpg');
        if (rough) { try { s.rough = await loadTex(b + 'Roughness.jpg'); } catch (_) { s.rough = null; } }
        if (metal) { try { s.metal = await loadTex(b + 'Metalness.jpg'); } catch (_) { s.metal = null; } }
        sets.set(key, s);
        return s;
    }
    async function loadGLB(rel) {
        const bytes = await readBytes(rel);
        const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        return await new globalThis.GLTFLoader().parseAsync(buf, '');
    }
    async function loadJSON(rel) { return JSON.parse(new TextDecoder().decode(await readBytes(rel))); }

    // ── canvas textures ───────────────────────────────────────────────────
    function mipChain(data, w, h) {
        const levels = [{ data, width: w, height: h }];
        let sw = w, sh = h, src = data;
        while (sw > 1 || sh > 1) {
            const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
            const dst = new Uint8Array(dw * dh * 4);
            for (let y = 0; y < dh; y++) {
                const y0 = Math.min(sh - 1, y * 2), y1 = Math.min(sh - 1, y * 2 + 1);
                for (let x = 0; x < dw; x++) {
                    const x0 = Math.min(sw - 1, x * 2), x1 = Math.min(sw - 1, x * 2 + 1);
                    const o = (y * dw + x) * 4;
                    for (let c = 0; c < 4; c++) {
                        dst[o + c] = (src[(y0 * sw + x0) * 4 + c] + src[(y0 * sw + x1) * 4 + c]
                            + src[(y1 * sw + x0) * 4 + c] + src[(y1 * sw + x1) * 4 + c]) >> 2;
                    }
                }
            }
            levels.push({ data: dst, width: dw, height: dh });
            sw = dw; sh = dh; src = dst;
        }
        return levels;
    }
    // draw(ctx, w, h) in canvas space (y down). gltf: true for quads that came from a
    // GLB (glTF UVs have v = 0 at the image top), false for three-convention UVs.
    function canvasTex(w, h, draw, { srgb = true, repeat = false, mips = true, gltf = false } = {}) {
        const cv = document.createElement('canvas');
        cv.width = w; cv.height = h;
        const ctx = cv.getContext('2d');
        const tex = new THREE.DataTexture(new Uint8Array(w * h * 4), w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        tex.wrapS = tex.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
        tex.magFilter = THREE.LinearFilter;
        tex.minFilter = mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
        tex.generateMipmaps = false;
        tex.anisotropy = 8;
        const upload = () => {
            const src = ctx.getImageData(0, 0, w, h).data;
            const data = new Uint8Array(w * h * 4), row = w * 4;
            if (gltf) data.set(src);
            else for (let y = 0; y < h; y++) data.set(src.subarray(y * row, (y + 1) * row), (h - 1 - y) * row);
            tex.image = { data, width: w, height: h };
            tex.mipmaps = mips ? mipChain(data, w, h) : [];
            tex.needsUpdate = true;
        };
        draw(ctx, w, h);
        upload();
        own(tex);
        return { tex, ctx, canvas: cv, redraw(fn) { if (fn) fn(ctx, w, h); upload(); } };
    }
    function spacedText(ctx, str, x, y, spacing, align = 'center') {
        const widths = [...str].map(ch => ctx.measureText(ch).width);
        const total = widths.reduce((a, b) => a + b, 0) + spacing * Math.max(0, str.length - 1);
        let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
        const prev = ctx.textAlign; ctx.textAlign = 'left';
        [...str].forEach((ch, i) => { ctx.fillText(ch, cx, y); cx += widths[i] + spacing; });
        ctx.textAlign = prev;
    }

    // ── geometry (for runtime-built parts) ────────────────────────────────
    const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _e = new THREE.Euler();
    const _p = new THREE.Vector3(), _s = new THREE.Vector3();
    function xf(g, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) {
        _e.set(rx, ry, rz); _q.setFromEuler(_e);
        g.applyMatrix4(_m.compose(_p.set(x, y, z), _q, _s.set(sx, sy, sz)));
        return g;
    }
    const rbox = (w, h, d, r = 0.004, seg = 2) =>
        new RoundedBoxGeometry(w, h, d, seg, Math.max(1e-4, Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4)));
    function prep(g) {
        let q = g.index ? g.toNonIndexed() : g;
        if (!q.attributes.normal) q.computeVertexNormals();
        if (!q.attributes.uv) q.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(q.attributes.position.count * 2), 2));
        for (const k of Object.keys(q.attributes)) {
            if (k !== 'position' && k !== 'normal' && k !== 'uv' && !/^a[A-Z]/.test(k)) q.deleteAttribute(k);
        }
        return q;
    }
    const merge = (list) => BGU.mergeGeometries(list.map(prep), false);
    function mesh(g, mat, seed = 0, name = '') {
        const q = prep(g);
        q.setAttribute('aSeed', new THREE.Float32BufferAttribute(new Float32Array(q.attributes.position.count).fill(seed), 1));
        own(q);
        const m = new THREE.Mesh(q, mat);
        m.name = name; m.castShadow = true; m.receiveShadow = true;
        return m;
    }

    // ── materials ─────────────────────────────────────────────────────────
    function curvature() {                       // convex curvature, 1/m, from the geometric normal
        const nW = normalWorldGeometry, pW = positionWorld;
        const dNx = dFdx(nW), dPx = dFdx(pW), dNy = dFdy(nW), dPy = dFdy(pW);
        return dot(dNx, dPx).div(max(dot(dPx, dPx), float(1e-12)))
            .add(dot(dNy, dPy).div(max(dot(dPy, dPy), float(1e-12))));
    }
    // A layered role material: an AmbientCG set on UV0 (metres × repeat), recoloured
    // by luminance when `lum` is given; baked masks on UV1 (R = AO, G = edges,
    // B = cavity) drive AO, grime in cavities and edge wear on convex edges; an
    // optional imperfection map breaks roughness (fingerprints, smears, scratches).
    function roleMat(o = {}) {
        const {
            set = null, flat = 0x808080, repeat = 2.0, tint = 0xffffff, lum = null, lumContrast = 1.0,
            roughMul = 1.0, roughAdd = 0.0, roughMin = 0.03, roughMax = 1.0, rough = 0.5,
            metal = 0.0, metalMap = false, normalScale = 1.0, clearcoat = 0, coatRough = 0.08,
            mask = null, ao = 1.0, grime = 0, grimeColor = 0x2a241c, edge = 0, edgeColor = 0x888888,
            edgeRough = 0.35, edgeMetal = null, edgeR = 0.005, dust = 0, dustColor = 0x8e877a,
            imperf = null, imperfRepeat = 1.5, imperfAmt = 0.15, emissive = null, mottle = 0.0,
            transparent = false, opacity = 1, side = THREE.FrontSide, local = true,
        } = o;
        const Mat = clearcoat > 0 ? THREE.MeshPhysicalNodeMaterial : THREE.MeshStandardNodeMaterial;
        const m = own(new Mat({ transparent, opacity, side }));
        if (clearcoat > 0) { m.clearcoat = clearcoat; m.clearcoatRoughness = coatRough; }
        const uvT = uv().mul(repeat);
        let col, r;
        if (set) {
            const c = texture(set.map, uvT).rgb;
            col = lum ? vec3(dot(c, LUM).div(lum).sub(1).mul(lumContrast).add(1)).mul(rgb(tint)) : c.mul(rgb(tint));
            r = set.rough ? texture(set.rough, uvT).g.mul(roughMul).add(roughAdd) : float(rough);
        } else {
            col = rgb(flat);
            r = float(rough);
        }
        let mt = (set && set.metal && metalMap) ? texture(set.metal, uvT).r.mul(metal) : float(metal);
        const p = (local ? positionLocal : positionWorld);
        const broad = mx_fractal_noise_float(p.mul(2.3), 3, 2.0, 0.5).mul(0.5).add(0.5);
        const fine = mx_fractal_noise_float(p.mul(38.0), 2, 2.0, 0.5).mul(0.5).add(0.5);
        if (mottle > 0) col = col.mul(broad.sub(0.5).mul(2 * mottle).add(1)).mul(fine.sub(0.5).mul(mottle).add(1));
        if (imperf) {
            const im = texture(imperf.map, uv().mul(imperfRepeat)).r;
            r = r.add(im.mul(imperfAmt));
        }
        let aoN = float(1), edgeM = float(0), cav = float(1);
        if (mask) { const mk = texture(mask, uv(1)); aoN = mk.r; edgeM = mk.g; cav = mk.b; }
        if (grime > 0) {
            const g = float(1).sub(cav).mul(0.85).add(float(1).sub(aoN).mul(0.45))
                .mul(broad.mul(0.8).add(0.4)).mul(grime).clamp(0, 1);
            col = mix(col, rgb(grimeColor), g.mul(0.7));
            r = r.add(g.mul(0.18));
        }
        if (edge > 0) {
            const cv = smoothstep(0.3, 0.85, curvature().mul(edgeR).clamp(0, 1));
            const convex = mask ? max(cv, edgeM.mul(smoothstep(0.78, 0.97, cav)).mul(0.9)) : cv;
            const chip = convex.mul(smoothstep(0.42, 0.62, fine)).mul(smoothstep(0.25, 0.6, broad)).mul(edge).clamp(0, 1);
            col = mix(col, rgb(edgeColor), chip);
            r = mix(r, float(edgeRough), chip);
            if (edgeMetal !== null) mt = mix(mt, float(edgeMetal), chip);
        }
        if (dust > 0) {
            const up = smoothstep(0.75, 0.98, normalWorldGeometry.y).mul(broad.mul(0.7).add(0.3)).mul(dust).mul(aoN.mul(0.5).add(0.5));
            col = mix(col, rgb(dustColor), up.mul(0.5));
            r = mix(r, float(0.85), up);
        }
        m.colorNode = col;
        m.roughnessNode = r.clamp(roughMin, roughMax);
        m.metalnessNode = mt;
        if (set && set.normal && normalScale > 0) m.normalNode = normalMap(texture(set.normal, uvT), vec2(normalScale, normalScale));
        if (mask) m.aoNode = mix(float(1), aoN.mul(cav.mul(0.35).add(0.65)), ao);
        if (emissive) m.emissiveNode = emissive;
        return m;
    }
    function glass(o = {}) {
        const { color = 0x0c0e11, opacity = 0.3, rough = 0.035, smudge = 0.1, side = THREE.FrontSide, imperf = null } = o;
        const m = own(new THREE.MeshPhysicalNodeMaterial({ color, transparent: true, opacity, side, depthWrite: false }));
        let r = float(rough);
        if (imperf) r = r.add(texture(imperf.map, uv().mul(3.0)).r.mul(smudge));
        else r = r.add(smoothstep(0.55, 0.85, mx_fractal_noise_float(positionLocal.mul(7.0), 3, 2.0, 0.6).mul(0.5).add(0.5)).mul(smudge));
        m.roughnessNode = r;
        m.metalnessNode = float(0);
        return m;
    }
    // a decal: canvas art on a GLB quad (lit, alpha-blended paint/print)
    function decalMat(tex, { rough = 0.4, metal = 0, emissive = null, alpha = true } = {}) {
        const m = own(new THREE.MeshStandardNodeMaterial({ transparent: alpha, depthWrite: !alpha }));
        const s = texture(tex, uv());
        m.colorNode = s.rgb;
        if (alpha) m.opacityNode = s.a;
        m.roughnessNode = float(rough);
        m.metalnessNode = float(metal);
        m.polygonOffset = true; m.polygonOffsetFactor = -2; m.polygonOffsetUnits = -2;
        if (emissive) m.emissiveNode = emissive;
        return m;
    }

    return {
        THREE, own, owned, rgb, seedN, readBytes, loadTex, pbr, loadGLB, loadJSON, canvasTex, spacedText,
        xf, rbox, prep, merge, mesh, curvature, roleMat, glass, decalMat,
        dispose() { for (const x of owned) x.dispose?.(); owned.clear(); },
    };
}
// ═══════════════════════════════ end craft kit ══════════════════════════════

// Dudley's ten filter bands (Hz), keys 1–10 left to right.
const BANDS = [[0, 225], [225, 450], [450, 700], [700, 1000], [1000, 1400],
    [1400, 2000], [2000, 2700], [2700, 3800], [3800, 5400], [5400, 7500]];

// Demo phrase: illustrative fingerings in the spirit of the Voder charts, not a
// transcription. keys are 1-based band numbers → depth; w = wrist bar (1 buzz, 0 hiss).
const PH = {
    sh: { k: { 7: 0.55, 8: 0.9, 9: 0.7 }, w: 0 },
    ee: { k: { 1: 0.45, 2: 0.35, 7: 0.85, 8: 0.45 }, w: 1 },
    s: { k: { 9: 0.75, 10: 1.0 }, w: 0 },
    aw: { k: { 1: 0.55, 3: 0.95, 4: 0.7 }, w: 1 },
    m: { k: { 1: 0.9 }, w: 1, q: 1 },
    k: { k: { 5: 0.5 }, w: 0, st: 2 },
    a: { k: { 2: 0.4, 4: 0.9, 6: 0.55 }, w: 1 },
    t: { k: { 9: 0.4 }, w: 0, st: 0 },
    _: { k: {}, w: 0 },
};
const SEQ = [['sh', 0.17], ['ee', 0.27], ['_', 0.07], ['s', 0.15], ['aw', 0.30], ['_', 0.05], ['m', 0.12],
    ['ee', 0.32], ['_', 0.30], ['k', 0.08], ['a', 0.26], ['t', 0.09], ['_', 0.40]];
const SEQ_T = []; { let acc = 0; for (const [p, d] of SEQ) { SEQ_T.push([p, acc, acc + d]); acc += d; } }
const SEQ_LEN = SEQ_T[SEQ_T.length - 1][2];
const sstep = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const clamp01 = (x) => Math.max(0, Math.min(1, x));

export function pattern(t) {
    const tt = ((t % SEQ_LEN) + SEQ_LEN) % SEQ_LEN;
    const keys = new Array(10).fill(0), stops = [0, 0, 0];
    let wrist = 0, quiet = 0, voiced = 0, loud = 0;
    for (const [ph, a, b] of SEQ_T) {
        const env = sstep(a - 0.03, a + 0.03, tt) * (1 - sstep(b - 0.04, b + 0.04, tt));
        if (env <= 0) continue;
        const P = PH[ph];
        for (const [k, v] of Object.entries(P.k)) keys[k - 1] = Math.max(keys[k - 1], v * env);
        if (P.st !== undefined) stops[P.st] = Math.max(stops[P.st], env);
        if (P.q) quiet = Math.max(quiet, env);
        wrist = Math.max(wrist, P.w * env);
        if (ph !== '_') { loud = Math.max(loud, env); if (P.w) voiced = Math.max(voiced, env); }
    }
    const pedal = clamp01(0.42 + 0.18 * Math.sin(tt * 3.1) + 0.22 * sstep(0.62, 0.72, tt) * (1 - sstep(0.9, 1.2, tt)));
    const level = clamp01(loud * (0.55 + 0.4 * voiced) * (1 - 0.45 * quiet));
    return { keys, stops, quiet, wrist, pedal, level };
}

export async function build(THREE, opts = {}) {
    const K = await craftKit(THREE);
    const { uniform, vec3, float, texture, uv, mix, smoothstep, max, dot } = THREE;
    const DECO = '"Bahnschrift", "Segoe UI", Arial, sans-serif';

    const gltf = await K.loadGLB(opts.glb ?? 'voder.glb');
    const mask = await K.loadTex('voder_mask.png', { flipY: false, repeat: false });
    const L = await K.loadJSON('voder_layout.json');
    const T = {
        enamel: await K.pbr('PaintedMetal002'), gloss: await K.pbr('Plastic003_1k'), satin: await K.pbr('Plastic006_1k'),
        plastic: await K.pbr('Plastic013B_1k'), chrome: await K.pbr('Metal049A'), metal: await K.pbr('Metal041A'),
        crinkle: await K.pbr('Metal046A'), rubber: await K.pbr('Rubber004_1k'), fabric: await K.pbr('Fabric030'),
        prints: await K.pbr('Fingerprints002_1k', { normal: false, rough: false }),
        smear: await K.pbr('Smear004_1k', { normal: false, rough: false }),
    };
    const uPower = uniform(opts.power ?? 1);
    const uLevel = uniform(0);

    // ── role materials ─────────────────────────────────────────────────────
    const R = {
        cream: K.roleMat({ set: T.enamel, lum: 0.181, lumContrast: 0.07, mottle: 0.05, tint: 0xe4d6b6, repeat: 1.6, roughMul: 1.1, roughAdd: 0.08,
            normalScale: 0.6, clearcoat: 0.35, coatRough: 0.12, mask, grime: 0.65, grimeColor: 0x4a3c2a, edge: 0.9,
            edgeColor: 0x6d6150, edgeRough: 0.6, dust: 0.3, imperf: T.smear, imperfAmt: 0.12 }),
        lacquer: K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.25, tint: 0x100d0d, repeat: 1.4, roughMul: 0.6, roughAdd: 0.02,
            normalScale: 0.35, clearcoat: 0.9, coatRough: 0.04, mask, grime: 0.25, edge: 0.7, edgeColor: 0x4a3a2b,
            edgeRough: 0.5, dust: 0.25, dustColor: 0x5e574d, imperf: T.prints, imperfRepeat: 2.2, imperfAmt: 0.35 }),
        satin: K.roleMat({ set: T.satin, lum: 0.002, lumContrast: 0.2, tint: 0x141112, repeat: 2.0, roughMul: 1.2, roughAdd: 0.08,
            normalScale: 0.5, clearcoat: 0.3, coatRough: 0.3, mask, grime: 0.3, edge: 0.6, edgeColor: 0x4d3f31, dust: 0.2,
            imperf: T.prints, imperfRepeat: 3.0, imperfAmt: 0.25 }),
        chrome: K.roleMat({ set: T.chrome, tint: 0xffffff, repeat: 2.5, metal: 1, roughMul: 1.0, roughAdd: 0.05, normalScale: 0.4,
            mask, grime: 0.35, grimeColor: 0x3a342a, imperf: T.prints, imperfRepeat: 3.5, imperfAmt: 0.25 }),
        ivory: K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 1.5, tint: 0xeee0bf, repeat: 6.0, roughMul: 0.45, normalScale: 0.4,
            clearcoat: 0.6, coatRough: 0.06, mask, grime: 0.35, grimeColor: 0x8a7550, edge: 0.4, edgeColor: 0xcfb88a, edgeRough: 0.25 }),
        bakelite: K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.5, tint: 0x2b1a10, repeat: 4.0, roughMul: 0.8, normalScale: 0.5,
            clearcoat: 0.5, coatRough: 0.1, mask, grime: 0.3, edge: 0.5, edgeColor: 0x6a4428, edgeRough: 0.3 }),
        rubber: K.roleMat({ set: T.rubber, lum: 0.025, lumContrast: 0.6, tint: 0x1a1918, repeat: 5.0, normalScale: 1.0, mask, grime: 0.3, dust: 0.4 }),
        crinkle: K.roleMat({ set: T.crinkle, lum: 0.108, lumContrast: 0.8, tint: 0x2a2826, repeat: 3.0, metal: 0.3, roughMul: 3.0,
            normalScale: 1.4, mask, grime: 0.4, edge: 0.5, edgeColor: 0x6f6a62, edgeMetal: 1, dust: 0.3 }),
        brass: K.roleMat({ set: T.metal, lum: 0.488, lumContrast: 1.2, tint: 0xd8ae62, repeat: 4.0, metal: 1, roughMul: 1.6,
            normalScale: 0.5, mask, grime: 0.5, grimeColor: 0x3b2a14, edge: 0.6, edgeColor: 0xf2d9a0, edgeRough: 0.15 }),
        cable: K.roleMat({ set: T.fabric, lum: 0.105, lumContrast: 1.6, tint: 0x241f1a, repeat: 14.0, normalScale: 1.2, mask, grime: 0.3 }),
        dark: K.roleMat({ flat: 0x0a0a0a, rough: 0.7, mask }),
        glass: K.glass({ color: 0x15171a, opacity: 0.16, rough: 0.02, smudge: 0.2, imperf: T.smear }),
        lamp_pilot: K.roleMat({ flat: 0x6e3208, rough: 0.12, clearcoat: 0.8, emissive: vec3(1.0, 0.5, 0.11).mul(uPower.mul(6.0)) }),
    };
    // grille cloth: woven fabric, lamp light through the gaps (glows with the voice)
    {
        const m = K.roleMat({ set: T.fabric, lum: 0.105, lumContrast: 1.8, tint: 0x5a4731, repeat: 22.0, normalScale: 1.4, mask });
        const weave = dot(texture(T.fabric.map, uv().mul(22.0)).rgb, vec3(0.2126, 0.7152, 0.0722)).div(0.105);
        const gap = smoothstep(1.05, 0.6, weave);
        m.emissiveNode = vec3(1.0, 0.6, 0.28).mul(gap.mul(0.8).add(0.08)).mul(uPower.mul(uLevel.mul(0.9).add(0.1)).mul(2.6));
        R.cloth = m;
    }

    // ── decals: canvas art on the GLB quads (glTF UV convention) ───────────
    const panelArt = K.canvasTex(1024, 358, (ctx, w, h) => {
        const P = L.panel, px = (x) => (x / P.w + 0.5) * w, py = (s) => (0.5 - s / P.h) * h;
        ctx.clearRect(0, 0, w, h);
        ctx.strokeStyle = 'rgba(214,202,172,0.92)'; ctx.lineWidth = 2.5;
        ctx.strokeRect(22, 22, w - 44, h - 44);
        ctx.lineWidth = 1.2; ctx.strokeRect(31, 31, w - 62, h - 62);
        ctx.fillStyle = 'rgba(214,202,172,0.92)';
        for (let i = 0; i < 3; i++) {
            ctx.fillRect(44, 46 + i * 9, 110 - i * 28, 3);
            ctx.fillRect(w - 154 + i * 28, h - 52 - i * 9, 110 - i * 28, 3);
        }
        ctx.textBaseline = 'middle';
        const lab = (txt, x, s, size = 20, sp = 5) => { ctx.font = `600 ${size}px ${DECO}`; K.spacedText(ctx, txt, px(x), py(s), sp); };
        lab('PITCH', P.knobs.pitch, -0.058); lab('GAIN', P.knobs.gain, -0.058);
        lab('LOW', P.knobs.pitch - 0.05, -0.030, 13, 2); lab('HIGH', P.knobs.pitch + 0.05, -0.030, 13, 2);
        lab('0', P.knobs.gain - 0.046, -0.030, 13, 2); lab('10', P.knobs.gain + 0.046, -0.030, 13, 2);
        lab('NORMAL', P.whisper[0], 0.040, 15, 3); lab('WHISPER', P.whisper[0], -0.040, 15, 3);
        lab('PILOT', P.pilot.x, 0.040, 15, 3);
        lab('LEVEL', P.dial.x, -0.082, 18, 5);
        const b = P.bank;
        ['ON', 'VIB', 'HISS', 'BUZZ', 'LINE'].forEach((t, i) => lab(t, b.x0 + i * 0.031, b.s + 0.031, 11, 1));
        ctx.strokeStyle = 'rgba(214,202,172,0.92)';
        for (let k = 0; k <= 10; k++) {                       // knob dial ticks
            for (const kx of [P.knobs.pitch, P.knobs.gain]) {
                const a = Math.PI * (0.75 + 1.5 * k / 10);
                const cx = px(kx), cy = py(0), r0 = 0.037 / P.w * w, r1 = 0.042 / P.w * w;
                ctx.lineWidth = k % 5 === 0 ? 2.2 : 1.2;
                ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
                ctx.lineTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1); ctx.stroke();
            }
        }
    }, { gltf: true });
    const stripArt = K.canvasTex(1024, 32, (ctx, w, h) => {
        const S = L.keystrip;
        ctx.fillStyle = '#e8dbba'; ctx.fillRect(0, 0, w, h);
        const g = ctx.createLinearGradient(0, 0, 0, h); g.addColorStop(0, 'rgba(255,255,255,0.18)'); g.addColorStop(1, 'rgba(0,0,0,0.12)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#1b1612'; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
        const px = (x) => (x / S.w + 0.5) * w;
        ctx.font = `600 19px ${DECO}`;
        S.keyX.forEach((x, i) => ctx.fillText(String(i + 1), px(x), h / 2 + 1));
        ctx.font = `600 12px ${DECO}`;
        ['T-D', 'P-B', 'K-G'].forEach((s, i) => ctx.fillText(s, px(S.stopX[i]), h / 2 + 1));
        ctx.fillText('Q', px(S.quietX), h / 2 + 1);
        ctx.fillRect(4, 3, w - 8, 1.4); ctx.fillRect(4, h - 4.4, w - 8, 1.4);
    }, { gltf: true });
    const nameArt = K.canvasTex(512, 152, (ctx, w, h) => {
        ctx.clearRect(0, 0, w, h);
        const gold = ctx.createLinearGradient(0, 0, w, h);
        gold.addColorStop(0, '#caa05a'); gold.addColorStop(0.45, '#f1d692'); gold.addColorStop(1, '#b8904c');
        ctx.fillStyle = gold; ctx.textBaseline = 'middle';
        ctx.font = `700 76px ${DECO}`;
        K.spacedText(ctx, 'VODER', w / 2, h / 2 - 8, 22);
        ctx.font = `600 17px ${DECO}`;
        K.spacedText(ctx, 'BELL TELEPHONE LABORATORIES', w / 2, h - 30, 3);
        ctx.font = `700 76px ${DECO}`;
        for (let i = 0; i < 3; i++) {
            ctx.fillRect(20, 42 + i * 13, 56 - i * 14, 5);
            ctx.fillRect(w - 76 + i * 14, h - 47 - i * 13, 56 - i * 14, 5);
        }
        ctx.strokeStyle = gold; ctx.lineWidth = 4; ctx.strokeRect(8, 8, w - 16, h - 16);
    }, { gltf: true });
    const dialArt = K.canvasTex(512, 512, (ctx, w, h) => {
        // the card quad is 0.128 m (it overfills the 0.124 m bore); the needle pivot is 0.0232 m below centre
        const k = 0.116 / 0.128, cx = w / 2, cy = h * 0.70;          // cy is pre-scale: lands on the pivot after ctx.scale(k)
        const g = ctx.createRadialGradient(cx, h * 0.45, 20, cx, h * 0.5, w * 0.55);
        g.addColorStop(0, '#f6ead0'); g.addColorStop(1, '#d9c59e');
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
        ctx.save(); ctx.translate(cx, h / 2); ctx.scale(k, k); ctx.translate(-cx, -h / 2);
        const Rr = w * 0.36, a0 = -Math.PI / 2 - 0.87, a1 = -Math.PI / 2 + 0.87;
        ctx.strokeStyle = '#1c1611'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.arc(cx, cy, Rr, a0, a1); ctx.stroke();
        ctx.strokeStyle = '#a3261c'; ctx.lineWidth = 14;
        ctx.beginPath(); ctx.arc(cx, cy, Rr + 9, a0 + (a1 - a0) * 0.78, a1); ctx.stroke();
        ctx.fillStyle = '#1c1611'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.font = `600 26px ${DECO}`;
        for (let i = 0; i <= 20; i++) {
            const a = a0 + (a1 - a0) * i / 20, big = i % 4 === 0;
            ctx.lineWidth = big ? 4 : 2;
            ctx.beginPath();
            ctx.moveTo(cx + Math.cos(a) * (Rr - (big ? 30 : 16)), cy + Math.sin(a) * (Rr - (big ? 30 : 16)));
            ctx.lineTo(cx + Math.cos(a) * Rr, cy + Math.sin(a) * Rr);
            ctx.stroke();
            if (big) ctx.fillText(String(i / 2), cx + Math.cos(a) * (Rr - 56), cy + Math.sin(a) * (Rr - 56));
        }
        ctx.font = `700 34px ${DECO}`;
        K.spacedText(ctx, 'LEVEL', cx, h * 0.83, 10);
        ctx.font = `600 16px ${DECO}`;
        K.spacedText(ctx, 'SPEECH  OUTPUT', cx, h * 0.91, 5);
        ctx.restore();
    }, { gltf: true });
    // Bell System roundel, 1939 style (homage): bell in a double ring, BELL SYSTEM lettered round the top
    const bellArt = K.canvasTex(512, 512, (ctx, w, h) => {
        const cx = w / 2, cy = h / 2, blue = '#1d3f73', cream = '#efe6cf';
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = cream; ctx.beginPath(); ctx.arc(cx, cy, 236, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = blue; ctx.lineWidth = 16; ctx.beginPath(); ctx.arc(cx, cy, 226, 0, Math.PI * 2); ctx.stroke();
        ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(cx, cy, 160, 0, Math.PI * 2); ctx.stroke();
        ctx.fillStyle = blue; ctx.font = `700 46px ${DECO}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const arcText = (txt, r, a0, a1, flip) => {
            const n = txt.length;
            for (let i = 0; i < n; i++) {
                const a = a0 + (a1 - a0) * (n === 1 ? 0.5 : i / (n - 1));
                ctx.save(); ctx.translate(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
                ctx.rotate(a + (flip ? -Math.PI / 2 : Math.PI / 2)); ctx.fillText(txt[i], 0, 0); ctx.restore();
            }
        };
        arcText('BELL SYSTEM', 193, -Math.PI * 0.85, -Math.PI * 0.15, false);
        ctx.font = `600 26px ${DECO}`;
        arcText('LABORATORIES', 196, Math.PI * 0.78, Math.PI * 0.22, true);
        // the bell: dome, flared lip, clapper
        ctx.beginPath();
        ctx.moveTo(cx - 92, cy + 76);
        ctx.bezierCurveTo(cx - 92, cy + 56, cx - 66, cy + 44, cx - 64, cy + 6);
        ctx.bezierCurveTo(cx - 62, cy - 58, cx - 40, cy - 96, cx, cy - 98);
        ctx.bezierCurveTo(cx + 40, cy - 96, cx + 62, cy - 58, cx + 64, cy + 6);
        ctx.bezierCurveTo(cx + 66, cy + 44, cx + 92, cy + 56, cx + 92, cy + 76);
        ctx.closePath(); ctx.fill();
        ctx.fillRect(cx - 12, cy - 118, 24, 24);
        ctx.beginPath(); ctx.arc(cx, cy + 96, 16, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = cream; ctx.fillRect(cx - 96, cy + 70, 192, 4);
    }, { gltf: true });
    R.decal_bell = K.decalMat(bellArt.tex, { rough: 0.35 });
    R.decal_panel = K.decalMat(panelArt.tex, { rough: 0.3 });
    R.decal_keystrip = K.decalMat(stripArt.tex, { rough: 0.25, alpha: false });
    R.decal_name = K.decalMat(nameArt.tex, { rough: 0.22, metal: 0.85 });
    R.decal_dial = K.decalMat(dialArt.tex, { rough: 0.6, alpha: false,
        emissive: texture(dialArt.tex, uv()).rgb.mul(vec3(1.0, 0.8, 0.52)).mul(uPower.mul(uLevel.mul(0.45).add(0.75)).mul(1.1)) });

    // ── assemble ───────────────────────────────────────────────────────────
    const group = new THREE.Group(); group.name = 'voder';
    const root = gltf.scene;
    group.add(root);
    const missing = new Set();
    root.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/^era1_/, '');
        const mat = R[role];
        if (!mat) missing.add(role);
        o.material?.dispose?.();
        o.material = mat || R.dark;
        o.castShadow = !/decal|glass/.test(role);
        o.receiveShadow = true;
        K.own(o.geometry);
    });
    if (missing.size) console.warn('[voder] no material for roles:', [...missing].join(', '));
    const node = (n) => { const o = root.getObjectByName(n); if (!o) throw new Error('[voder] missing node ' + n); return o; };
    const keys = Array.from({ length: 10 }, (_, i) => { const k = node(`voder_key_${String(i + 1).padStart(2, '0')}`); k.userData.band = BANDS[i]; return k; });
    const stopKeys = ['td', 'pb', 'kg'].map(s => node(`voder_stop_${s}`));
    const quietKey = node('voder_quiet'), wristBar = node('voder_wristbar'), pedal = node('voder_pedal');
    const needle = node('voder_needle'), jewel = node('voder_pilot'), cloth = root.getObjectByName('voder_grille_cloth') || null;
    const consoleG = node('voder_console'), speakerG = node('voder_speaker');
    const q0 = new Map();
    for (const o of [...keys, ...stopKeys, quietKey, wristBar, pedal, needle]) q0.set(o, o.quaternion.clone());
    const _q = new THREE.Quaternion(), AX = new THREE.Vector3(1, 0, 0), AY = new THREE.Vector3(0, 1, 0);
    const turn = (o, axis, a) => o.quaternion.copy(q0.get(o)).multiply(_q.setFromAxisAngle(axis, a));

    // ── update ─────────────────────────────────────────────────────────────
    const KEY_MAX = 0.10, STOP_MAX = 0.12, WRIST_MAX = 0.12;
    function update(t, state = {}) {
        const s = state || {};
        uPower.value = clamp01(s.power ?? 1);
        const voice = s.voice !== undefined ? clamp01(s.voice) : null;
        let src = s;
        if (!s.keys && voice !== null) {                     // it sings: its own fingering, gated by the voice
            const p = pattern(t);
            const g = sstep(0.02, 0.35, voice);
            src = { keys: p.keys.map(k => k * g), stops: p.stops.map(k => k * g), quiet: p.quiet * g,
                wrist: p.wrist * g, pedal: 0.3 + (p.pedal - 0.3) * g, level: voice };
        }
        const kv = src.keys || [];
        let sum = 0;
        for (let i = 0; i < 10; i++) { const v = clamp01(kv[i] ?? 0); turn(keys[i], AX, KEY_MAX * v); sum += v; }
        const st = src.stops || [];
        for (let i = 0; i < 3; i++) turn(stopKeys[i], AX, STOP_MAX * clamp01(st[i] ?? 0));
        const quiet = clamp01(src.quiet ?? 0);
        turn(quietKey, AX, STOP_MAX * quiet);
        turn(wristBar, AX, WRIST_MAX * clamp01(src.wrist ?? 0));
        turn(pedal, AX, 0.22 - 0.19 * clamp01(src.pedal ?? 0.3));
        const level = src.level !== undefined ? clamp01(src.level) : clamp01(sum * 0.3 * (1 - 0.45 * quiet));
        uLevel.value = level;
        // needle: 0 → left stop, 1 → right, a deterministic flutter while it speaks
        turn(needle, AY, 0.87 - 1.74 * clamp01(level * 0.92 + 0.02 * Math.sin(t * 23.0) * level));   // +Y = out of the face: CCW = left
    }
    update(0, {});

    return {
        group,
        parts: {
            keys, stopKeys, quietKey, wristBar, pedal,
            dial: { needle, face: root.getObjectByName('voder_dial_face'), texture: dialArt.tex },
            lamp: jewel, grille: cloth, console: consoleG, speaker: speakerG,
            uniforms: { power: uPower, level: uLevel },
        },
        update,
        pattern,
        dispose() { group.removeFromParent(); K.dispose(); },
    };
}
