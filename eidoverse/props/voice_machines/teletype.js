// teletype.js — a Teletype ASR-33 on its pedestal, 1966 (DAISY, verse 1: ELIZA).
//
// ELIZA ran on MIT's Project MAC time-sharing system through a typewriter terminal;
// the machine lines came back in CAPITALS and the transcripts carry no question marks,
// because "?" was the line-delete character (dossier §2).
//
// HERO ASSET modelled in Blender (eidoverse/assets/models/voice_machines/blender/
// era1_teletype.py → teletype.glb): the moulded khaki housing (keyboard-well pocket, band
// recess, parting line, back vents), the cream typing-unit cover as a real shell with
// its window, platen + knurled knob, ribbon spools, type-box rail, mechanism, roll
// cradle, grey right plate with call-control bezels, brushed band + mode knob, the
// paper-tape reader/punch (knobs, lid, lever, chad box, hanging tape), the sheet-metal
// pedestal with the arch cut through, sled feet, power cord. Layered materials here
// (AmbientCG sets on UV0 + baked masks on UV1 + curvature wear). Era markings are
// canvas homage (Skye, 09-23): "T E L E T Y P E" on the band, the TT monogram on the
// cover, an M.I.T. Project MAC property tag on the pedestal. References: CHM ASR-33
// photos (sources: eidoverse/assets/models/voice_machines/SOURCES.md).
//
//   const { build } = await import(new URL('props/voice_machines/teletype.js', EIDOVERSE_DIR).href);
//   const tty = await build(THREE, {});
//   scene.add(tty.group);
//   tty.update(t, { text: 'I WAS A MIRROR NAMED ELIZA\n', nChars, voice, power });
//   // or tty.parts.paper.setText(fullText, nChars) directly
//
// setText(fullText, nChars): prints the first nChars characters, UPPERCASE, every "?"
//   stripped, 72 columns (wraps), "\n" = carriage return + line feed. The most recent
//   line sits at the platen; older lines ride up the paper. Fractional nChars animates:
//   the type box travels to the next column; on "\n" the paper advances one line (the
//   platen and roll turn, the type box returns). Text is drawn on the GPU from a glyph
//   atlas + a 128×64 character buffer: sharp in extreme close-ups, 32 KB per update.
// update(t, st): st.voice (0..1) — the call-control lamps flare with it and the keyboard
//   dances with the printing (each printed character's key goes down).
// parts: paper { mesh, setText, lines() }, printhead, platen, roll, keyboard, lamps,
//   uniforms { power, voice, line }.
// Metres, +Y up, floor y = 0, facing +Z (keyboard toward the camera).
// ≈ 0.50 m wide × 0.50 m deep, 0.89 m to the top of the cover; paper rises to ≈ 1.06 m.

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

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const sstep = (x) => { const t = clamp01(x); return t * t * (3 - 2 * t); };
const COLS = 72, BUF_W = 128, ROWS = 64;
const LINE = 0.0254 / 6, CHAR = 0.0254 / 10, PAPER_W = 0.2159;
const MARGIN = (PAPER_W - COLS * CHAR) / 2;

export async function build(THREE, opts = {}) {
    const K = await craftKit(THREE);
    const {
        uniform, uniformArray, vec2, vec3, float, texture, uv, attribute, mix, smoothstep, step, fract, floor, mod,
        abs, length, sin, dFdx, dFdy, positionLocal, faceDirection, mx_noise_float, mx_fractal_noise_float, dot,
    } = THREE;
    const MONO = '"Lucida Console", Consolas, "Courier New", monospace';
    const SANS = '"Bahnschrift", "Segoe UI", Arial, sans-serif';

    const gltf = await K.loadGLB(opts.glb ?? 'teletype.glb');
    const mask = await K.loadTex('teletype_mask.png', { flipY: false, repeat: false });
    const L = await K.loadJSON('teletype_layout.json');
    const T = {
        enamel: await K.pbr('PaintedMetal002'), moulded: await K.pbr('Plastic004'), plastic: await K.pbr('Plastic013B_1k'),
        grey: await K.pbr('Plastic018B_1k'), gloss: await K.pbr('Plastic003_1k'), alu: await K.pbr('Metal041A'),
        chrome: await K.pbr('Metal049A'), crinkle: await K.pbr('Metal046A'), rubber: await K.pbr('Rubber004_1k'),
        paper: await K.pbr('Paper004'), prints: await K.pbr('Fingerprints002_1k', { normal: false, rough: false }),
        smear: await K.pbr('Smear004_1k', { normal: false, rough: false }),
    };
    const uPower = uniform(opts.power ?? 1), uVoice = uniform(0), uLine = uniform(0);

    // ── role materials ─────────────────────────────────────────────────────
    const R = {
        khaki: K.roleMat({ set: T.moulded, lum: 0.131, lumContrast: 0.5, mottle: 0.04, tint: 0xc2b78d, repeat: 3.0, roughMul: 0.9,
            normalScale: 0.45, clearcoat: 0.25, coatRough: 0.2, mask, grime: 0.5, grimeColor: 0x5a4f34, edge: 0.55, edgeColor: 0xdcd2ad,
            edgeRough: 0.2, dust: 0.3, dustColor: 0x9e9679, imperf: T.prints, imperfRepeat: 2.5, imperfAmt: 0.18 }),
        cream: K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 0.8, mottle: 0.04, tint: 0xe3d7b1, repeat: 3.0, roughMul: 0.6,
            normalScale: 0.35, clearcoat: 0.35, coatRough: 0.14, mask, grime: 0.4, grimeColor: 0x7d6e4c, edge: 0.45,
            edgeColor: 0xf1e8c9, edgeRough: 0.18, dust: 0.25, imperf: T.prints, imperfRepeat: 2.5, imperfAmt: 0.2 }),
        pedestal: K.roleMat({ set: T.enamel, lum: 0.181, lumContrast: 0.04, mottle: 0.02, tint: 0xb8b093, repeat: 1.6, roughMul: 1.4,
            roughAdd: 0.12, normalScale: 0.45, mask, grime: 0.45, grimeColor: 0x4a4230, edge: 0.85, edgeColor: 0x5a5549,
            edgeRough: 0.6, edgeMetal: 0.6, dust: 0.2, imperf: T.smear, imperfAmt: 0.08 }),
        plategrey: K.roleMat({ set: T.grey, lum: 0.187, lumContrast: 0.3, tint: 0xa7a9a2, repeat: 3.0, roughMul: 0.9, normalScale: 0.4,
            mask, grime: 0.4, edge: 0.5, edgeColor: 0x6d6f6a, dust: 0.25, imperf: T.prints, imperfRepeat: 3.0, imperfAmt: 0.2 }),
        steel: K.roleMat({ set: T.alu, lum: 0.488, lumContrast: 1.0, tint: 0xbdbfc2, repeat: 4.0, metal: 1, roughMul: 1.8, normalScale: 0.6,
            mask, grime: 0.5, grimeColor: 0x3b362d }),
        alu: K.roleMat({ set: T.alu, tint: 0xe6e7e8, repeat: 3.0, metal: 1, roughMul: 2.6, normalScale: 0.5, mask, grime: 0.3 }),
        chrome: K.roleMat({ set: T.chrome, repeat: 3.0, metal: 1, roughAdd: 0.05, normalScale: 0.4, mask, grime: 0.3,
            imperf: T.prints, imperfRepeat: 3.5, imperfAmt: 0.25 }),
        rubber: K.roleMat({ set: T.rubber, lum: 0.025, lumContrast: 0.6, tint: 0x131313, repeat: 8.0, roughMul: 0.8, mask }),
        blackplastic: K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.3, tint: 0x141414, repeat: 4.0, roughMul: 1.1, normalScale: 0.4, mask, grime: 0.2 }),
        mech: K.roleMat({ set: T.crinkle, lum: 0.108, lumContrast: 0.8, tint: 0x2a2a2a, repeat: 5.0, metal: 0.6, roughMul: 2.0,
            normalScale: 0.8, mask, grime: 0.5 }),
        ribbon: K.roleMat({ flat: 0x0c0b0e, rough: 0.55, mask }),
        creamknob: K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 0.6, tint: 0xe8dcbc, repeat: 8.0, roughMul: 0.6, clearcoat: 0.3, mask, grime: 0.4 }),
        tapepink: K.roleMat({ set: T.paper, lum: 0.32, lumContrast: 0.6, tint: 0xe9bfb4, repeat: 12.0, normalScale: 0.5, mask, side: THREE.DoubleSide }),
        cable: K.roleMat({ set: T.rubber, lum: 0.025, lumContrast: 0.8, tint: 0x1c1b1a, repeat: 10.0, normalScale: 0.6, mask, grime: 0.3, dust: 0.5 }),
        acrylic: K.glass({ color: 0x1b1d1c, opacity: 0.13, rough: 0.03, smudge: 0.25, side: THREE.DoubleSide, imperf: T.prints }),
        chad: K.glass({ color: 0xc9c2a0, opacity: 0.22, rough: 0.12, smudge: 0.15, side: THREE.DoubleSide, imperf: T.smear }),
    };

    // ── decals: TELETYPE band, TT monogram, M.I.T. tag ─────────────────────
    const bandArt = K.canvasTex(1024, 72, (ctx, w, h) => {
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = 'rgba(38,36,33,0.92)'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.font = `500 26px ${SANS}`;
        K.spacedText(ctx, 'TELETYPE', w * 0.36, h / 2 + 1, 58);
        ctx.font = `600 13px ${SANS}`;
        const kx = w * 0.9345;
        ctx.fillText('OFF', kx, 11); ctx.fillText('LINE', kx - 44, h / 2 + 8); ctx.fillText('LOCAL', kx + 48, h / 2 + 8);
    }, { gltf: true });
    const logoArt = K.canvasTex(256, 128, (ctx, w, h) => {
        ctx.clearRect(0, 0, w, h);
        const ink = 'rgba(28,26,22,0.95)';
        ctx.fillStyle = ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.font = `600 17px ${SANS}`; K.spacedText(ctx, 'TELETYPE', w / 2, 20, 4);
        const cx = w / 2, cy = 76;                      // the TT monogram: two T's over a curl, in a bracket
        ctx.fillRect(cx - 50, cy - 26, 100, 11);
        ctx.fillRect(cx - 33, cy - 26, 13, 52); ctx.fillRect(cx + 20, cy - 26, 13, 52);
        ctx.lineWidth = 7; ctx.strokeStyle = ink;
        ctx.beginPath(); ctx.arc(cx, cy + 6, 14, Math.PI * 0.1, Math.PI * 0.9); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx - 56, cy - 34); ctx.lineTo(cx - 56, cy + 30); ctx.lineTo(cx - 44, cy + 30); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx + 56, cy - 34); ctx.lineTo(cx + 56, cy + 30); ctx.lineTo(cx + 44, cy + 30); ctx.stroke();
    }, { gltf: true });
    const tagArt = K.canvasTex(512, 216, (ctx, w, h) => {
        const g = ctx.createLinearGradient(0, 0, w, h);
        g.addColorStop(0, '#c9ccce'); g.addColorStop(0.5, '#e4e6e7'); g.addColorStop(1, '#b8bbbd');
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
        for (let x = 0; x < w; x += 2) { ctx.fillStyle = `rgba(255,255,255,${0.03 + 0.05 * ((x * 7919) % 17) / 17})`; ctx.fillRect(x, 0, 1, h); }
        ctx.strokeStyle = '#2d3034'; ctx.lineWidth = 5; ctx.strokeRect(10, 10, w - 20, h - 20);
        ctx.fillStyle = '#23262a'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.font = `600 22px ${SANS}`; K.spacedText(ctx, 'PROPERTY OF', w / 2, 42, 3);
        ctx.font = `700 25px ${SANS}`; K.spacedText(ctx, 'MASSACHUSETTS INSTITUTE', w / 2, 80, 1);
        K.spacedText(ctx, 'OF TECHNOLOGY', w / 2, 110, 2);
        ctx.fillRect(40, 132, w - 80, 3);
        ctx.font = `700 30px ${SANS}`; K.spacedText(ctx, 'PROJECT MAC', w / 2, 160, 6);
        ctx.font = `600 18px ${MONO}`; ctx.fillText('No. 33-0417', w / 2, 192);
    }, { gltf: true });
    R.decal_band = K.decalMat(bandArt.tex, { rough: 0.35 });
    R.decal_logo = K.decalMat(logoArt.tex, { rough: 0.3 });
    R.decal_tag = K.decalMat(tagArt.tex, { rough: 0.35, metal: 0.8, alpha: false });

    const group = new THREE.Group(); group.name = 'teletype_asr33';
    const root = gltf.scene;
    group.add(root);
    const missing = new Set();
    root.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/^era1_/, '');
        const mat = R[role];
        if (!mat) missing.add(role);
        o.material?.dispose?.();
        o.material = mat || R.blackplastic;
        o.userData.role = role;
        o.castShadow = !/decal|acrylic|chad/.test(role);
        o.receiveShadow = true;
        K.own(o.geometry);
    });
    if (missing.size) console.warn('[teletype] no material for roles:', [...missing].join(', '));
    const platen = root.getObjectByName('teletype_platen');
    const platenQ0 = platen.quaternion.clone();

    // ═══ KEYBOARD (legend atlas; keys pressed on the GPU) ═══════════════════
    const deckY = (z) => z >= 0.02 ? 0.720 + (0.22 - Math.min(0.22, z)) * (0.045 / 0.20) : 0.765 + (0.02 - z) * (0.09 / 0.12);
    const ANG = L.deckAngle;
    const ROWS_KEYS = [
        [['!', '1'], ['"', '2'], ['#', '3'], ['$', '4'], ['%', '5'], ['&', '6'], ["'", '7'], ['(', '8'], [')', '9'], ['', '0'], ['*', ':'], ['=', '-'], ['', 'HERE\nIS']],
        [['', 'ESC'], ['', 'Q'], ['', 'W'], ['', 'E'], ['', 'R'], ['', 'T'], ['', 'Y'], ['', 'U'], ['', 'I'], ['', 'O'], ['', 'P'], ['', 'LINE\nFEED'], ['', 'RE-\nTURN']],
        [['', 'CTRL'], ['', 'A'], ['', 'S'], ['', 'D'], ['', 'F'], ['', 'G'], ['', 'H'], ['', 'J'], ['', 'K'], ['', 'L'], ['+', ';'], ['', 'RUB\nOUT'], ['', 'REPT']],
        [['', 'SHIFT'], ['', 'Z'], ['', 'X'], ['', 'C'], ['', 'V'], ['', 'B'], ['', 'N'], ['', 'M'], ['<', ','], ['>', '.'], ['?', '/'], ['', 'SHIFT'], ['', 'BREAK']],
    ];
    const KA = { cols: 8, rows: 8 };
    const legends = ROWS_KEYS.flat();
    const SPACE_KEY = legends.length;                  // the space bar's index
    const keyOf = new Map();                           // printed character → key index
    legends.forEach(([up, main], i) => { if (main.length === 1) keyOf.set(main, i); if (up.length === 1) keyOf.set(up, i); });
    keyOf.set(' ', SPACE_KEY); keyOf.set('\n', legends.findIndex(([, m]) => m === 'RE-\nTURN'));
    const keyArt = K.canvasTex(1024, 1024, (ctx, w, h) => {
        const cw = w / KA.cols, ch = h / KA.rows;
        ctx.fillStyle = '#9da09f'; ctx.fillRect(0, 0, w, h);
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        legends.forEach(([up, main], i) => {
            const cx = (i % KA.cols) * cw + cw / 2, cy = Math.floor(i / KA.cols) * ch + ch / 2;
            const g = ctx.createRadialGradient(cx - 10, cy - 12, 4, cx, cy, cw * 0.5);
            g.addColorStop(0, '#b3b6b5'); g.addColorStop(1, '#8e9190');
            ctx.fillStyle = g; ctx.fillRect(cx - cw / 2, cy - ch / 2, cw, ch);
            ctx.fillStyle = '#f2f2ee';
            const lines = main.split('\n');
            const big = lines.length === 1 && main.length <= 1;
            ctx.font = `600 ${big ? 46 : lines.length > 1 ? 21 : 24}px ${SANS}`;
            lines.forEach((ln, k) => ctx.fillText(ln, cx, cy + (up ? 12 : 0) + (k - (lines.length - 1) / 2) * 23));
            if (up) { ctx.font = `600 26px ${SANS}`; ctx.fillText(up, cx, cy - 26); }
        });
    });
    const uKeys = uniformArray(new Array(64).fill(0), 'float');
    const keyMat = K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 0.2, tint: 0xffffff, repeat: 20.0, roughMul: 0.9, normalScale: 0.25,
        edge: 0.6, edgeColor: 0xc9ccca, edgeR: 0.003, edgeRough: 0.25 });
    keyMat.colorNode = texture(keyArt.tex, uv()).rgb.mul(vec3(1.0, 1.0, 0.98));
    {
        const ak = attribute('aKey', 'float');
        const d = uKeys.element(ak.toInt()).mul(0.0042);
        keyMat.positionNode = positionLocal.sub(vec3(0, Math.cos(ANG), Math.sin(ANG)).mul(d));
    }
    const blankUV = [(7 + 0.5) / KA.cols, 1 - (7 + 0.5) / KA.rows];
    const keyGeos = [];
    const PITCH = 0.019;
    const tagKey = (g, i) => { const n = g.attributes.position.count; g.setAttribute('aKey', new THREE.Float32BufferAttribute(new Float32Array(n).fill(i), 1)); return g; };
    ROWS_KEYS.forEach((rowKeys, r) => {
        const zz = 0.064 + r * 0.030;
        const x0 = -0.121 + r * 0.25 * PITCH;
        rowKeys.forEach((_, k) => {
            const idx = ROWS_KEYS.slice(0, r).reduce((a, b) => a + b.length, 0) + k;
            const h = 0.017 - r * 0.0012;
            const g = new THREE.CylinderGeometry(0.0072, 0.0077, h, 24, 1).toNonIndexed();
            const uvA = g.attributes.uv, top = g.groups.find(q => q.materialIndex === 1);
            const c = idx % KA.cols, rr = Math.floor(idx / KA.cols);
            for (let i = 0; i < uvA.count; i++) uvA.setXY(i, blankUV[0], blankUV[1]);
            if (top) for (let i = top.start; i < top.start + top.count; i++) {
                const px = g.attributes.position.getX(i) / 0.0072 * 0.5 + 0.5, pz = g.attributes.position.getZ(i) / 0.0072 * 0.5 + 0.5;
                uvA.setXY(i, (c + px * 0.94 + 0.03) / KA.cols, 1 - (rr + pz * 0.94 + 0.03) / KA.rows);
            }
            g.clearGroups();
            const yb = deckY(zz) - 0.005 + 0.002;
            keyGeos.push(tagKey(K.prep(K.xf(g, x0 + k * PITCH, yb + h / 2, zz, ANG * 0.6)), idx));
        });
    });
    {
        const sb = K.rbox(0.13, 0.012, 0.016, 0.006);
        const u = sb.attributes.uv; for (let i = 0; i < u.count; i++) u.setXY(i, blankUV[0], blankUV[1]);
        keyGeos.push(tagKey(K.prep(K.xf(sb, 0.004, deckY(0.19) - 0.003 + 0.008, 0.19, ANG * 0.6)), SPACE_KEY));
    }
    const keyboard = new THREE.Mesh(K.own(K.merge(keyGeos)), keyMat);
    keyboard.name = 'teletype_keyboard'; keyboard.castShadow = true; keyboard.receiveShadow = true;
    group.add(keyboard);

    // call-control buttons: ORIG red, CLR black, BUZ-RLS blue, BRK-RLS amber — lit with power, flaring with the voice
    const BTN = [0xc0392b, 0x1c1c1c, 0x2f63b5, 0xd9861c];
    const btnGeos = L.buttons.map((p, i) => {
        const c = new THREE.Color(BTN[i]);
        const g = K.prep(K.xf(K.rbox(0.0145, 0.010, 0.0145, 0.0025), p[0], p[1], p[2], ANG));
        const n = g.attributes.position.count, arr = new Float32Array(n * 3);
        for (let k = 0; k < n; k++) arr.set([c.r, c.g, c.b], k * 3);
        g.setAttribute('aTint', new THREE.Float32BufferAttribute(arr, 3));
        return g;
    });
    const btnMat = (() => {
        const m = K.own(new THREE.MeshStandardNodeMaterial());
        const c = attribute('aTint', 'vec3');
        m.colorNode = c.mul(0.85);
        m.roughnessNode = float(0.25);
        m.metalnessNode = float(0);
        m.emissiveNode = c.mul(uPower.mul(uVoice.mul(2.4).add(0.9)).mul(1.8));
        return m;
    })();
    const buttons = new THREE.Mesh(K.own(K.merge(btnGeos)), btnMat);
    buttons.name = 'teletype_callcontrol';
    group.add(buttons);

    // ═══ TYPE BOX (moves along the platen) ══════════════════════════════════
    const Pp = L.paper;
    const PRINT_Z = Pp.printZ;
    const printhead = new THREE.Group(); printhead.name = 'teletype_typebox';
    // runtime parts have no baked-mask UV1: their own mask-free materials
    const headBlack = K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.3, tint: 0x141414, repeat: 20.0, roughMul: 1.1, normalScale: 0.4,
        edge: 0.4, edgeColor: 0x4a4a4a, edgeR: 0.002 });
    const headAlu = K.roleMat({ set: T.alu, tint: 0xe6e7e8, repeat: 20.0, metal: 1, roughMul: 1.5, normalScale: 0.5 });
    // the type cylinder sits just below the print line (the struck character stays readable); a ribbon
    // guide fork and the carriage shoe ride with it
    printhead.add(K.mesh(new THREE.CylinderGeometry(0.0085, 0.0085, 0.017, 28).translate(0, -0.0105, 0.0105), headBlack, 40));
    printhead.add(K.mesh(K.xf(K.rbox(0.020, 0.0035, 0.004, 0.001), 0, -0.0015, 0.0035), headAlu, 41));
    printhead.add(K.mesh(K.xf(K.rbox(0.024, 0.008, 0.024, 0.002), 0, -0.024, 0.014), headAlu, 42));
    printhead.position.set(0, Pp.platenY, PRINT_Z);
    group.add(printhead);

    // ═══ PAPER: glyph atlas + character buffer, drawn in the shader ═════════
    const glyphArt = K.canvasTex(1024, 384, (ctx, w, h) => {
        ctx.fillStyle = '#000'; ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.font = `bold 74px ${MONO}`;
        for (let i = 0; i < 64; i++) ctx.fillText(String.fromCharCode(32 + i), (i % 16) * 64 + 32, Math.floor(i / 16) * 96 + 50);
    }, { srgb: false });
    const bufData = new Uint8Array(BUF_W * ROWS * 4);
    const textBuf = new THREE.DataTexture(bufData, BUF_W, ROWS, THREE.RGBAFormat, THREE.UnsignedByteType);
    textBuf.colorSpace = THREE.NoColorSpace;
    textBuf.magFilter = textBuf.minFilter = THREE.NearestFilter;
    textBuf.generateMipmaps = false;
    textBuf.needsUpdate = true;
    K.own(textBuf);
    const paperTint = K.rgb(opts.paperColor ?? 0xf0dfa4);
    const inkColor = K.rgb(0x1d1a24);
    const paperMat = (() => {
        const m = K.own(new THREE.MeshStandardNodeMaterial({ side: THREE.DoubleSide }));
        const vM = uv().y, xM = uv().x.mul(PAPER_W);
        const Lf = uLine.sub(vM.div(LINE));
        const Ln = floor(Lf.add(0.5));
        const yIn = Lf.add(0.5).sub(Ln);
        const colF = xM.sub(MARGIN).div(CHAR);
        const col = floor(colF), gx = fract(colF), gy = float(1).sub(yIn);
        const valid = step(0, col).mul(step(col, float(COLS - 1)))
            .mul(step(0, Ln)).mul(step(Ln, floor(uLine))).mul(step(floor(uLine).sub(ROWS - 1), Ln));
        const cell = texture(textBuf, vec2(col.add(0.5).div(BUF_W), mod(Ln, float(ROWS)).add(0.5).div(ROWS)));
        const gIdx = floor(cell.r.mul(255).add(0.5));
        const jx = cell.g.sub(0.5).mul(0.07), jy = cell.g.mul(7.13).fract().sub(0.5).mul(0.10);
        const ax = mod(gIdx, 16.0), ay = floor(gIdx.div(16.0));
        const gxy = vec2(gx.add(jx).clamp(0.02, 0.98), gy.add(jy).mul(0.92).add(0.04).clamp(0.02, 0.98));
        const aUV = vec2(ax.add(gxy.x).div(16.0), float(1).sub(ay.add(float(1).sub(gxy.y)).div(4.0)));
        const cont = vec2(colF.div(16.0), Lf.div(4.0));
        const cov = texture(glyphArt.tex, aUV).grad(dFdx(cont), dFdy(cont)).r;
        const weave = mx_noise_float(vec3(xM.mul(2600.0), vM.mul(2600.0), 0.0)).mul(0.5).add(0.5);
        const ink = cov.mul(cell.b.mul(0.35).add(0.65)).mul(weave.mul(0.3).add(0.7)).mul(cell.a).mul(valid)
            .mul(step(0.0, faceDirection)).clamp(0, 1);
        const pUV = vec2(xM, vM).mul(3.2);
        const pap = texture(T.paper.map, pUV).rgb;
        const fibre = dot(pap, vec3(0.2126, 0.7152, 0.0722)).div(0.32);
        const edgeShade = smoothstep(0.0, 0.004, xM).mul(smoothstep(PAPER_W, PAPER_W - 0.004, xM));
        const paper = paperTint.mul(fibre.sub(1).mul(0.35).add(1)).mul(edgeShade.mul(0.1).add(0.9));
        m.colorNode = mix(paper, inkColor, ink.mul(0.92));
        m.roughnessNode = texture(T.paper.rough, pUV).g.mul(1.2).sub(ink.mul(0.2)).clamp(0.3, 1.0);
        m.normalNode = THREE.normalMap(texture(T.paper.normal, pUV), vec2(0.22, 0.22));
        m.metalnessNode = float(0);
        return m;
    })();
    // strip path in (z, y): from the roll, under the platen, up past the print point, curling back
    const paperGeo = (() => {
        const roll = Pp.roll;
        const back = [[roll.z + 0.006, roll.y - roll.r - 0.0005], [roll.z + 0.045, roll.y - roll.r - 0.002],
            [Pp.platenZ - 0.045, Pp.platenY - Pp.platenR - 0.006], [Pp.platenZ - 0.022, Pp.platenY - Pp.platenR - 0.0012]];
        const below = [];
        for (let k = 0; k <= 8; k++) {
            const a = -Math.PI / 2 + (k / 8) * (Math.PI / 2);
            below.push([Pp.platenZ + (Pp.platenR + 0.0006) * Math.cos(a), Pp.platenY + (Pp.platenR + 0.0006) * Math.sin(a)]);
        }
        const up = [[PRINT_Z + 0.0006, Pp.platenY + 0.03], [PRINT_Z - 0.002, Pp.coverTop + 0.02], [PRINT_Z - 0.010, 0.955],
            [PRINT_Z - 0.030, 1.005], [PRINT_Z - 0.070, 1.040], [PRINT_Z - 0.120, 1.056], [PRINT_Z - 0.170, 1.052], [PRINT_Z - 0.215, 1.036],
            [PRINT_Z - 0.250, 1.004], [PRINT_Z - 0.268, 0.950], [PRINT_Z - 0.273, 0.880], [PRINT_Z - 0.271, 0.800]];   // drapes down the back
        const curve = new THREE.CatmullRomCurve3(up.map(([z, y]) => new THREE.Vector3(0, y, z)));
        curve.curveType = 'centripetal';
        const above = curve.getSpacedPoints(72).map(v => [v.z, v.y]);
        const path = [...back, ...below, ...above.slice(1)];
        const iPrint = back.length + below.length - 1;
        const s = [0];
        for (let i = 1; i < path.length; i++) s.push(s[i - 1] + Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]));
        const s0 = s[iPrint];
        const pos = [], uvs = [], idx = [];
        path.forEach(([z, y], i) => {
            pos.push(-PAPER_W / 2, y, z, PAPER_W / 2, y, z);
            uvs.push(0, s[i] - s0, 1, s[i] - s0);
            if (i > 0) { const a = (i - 1) * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }   // front face toward the reader (+Z)
        });
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
        g.setIndex(idx);
        g.computeVertexNormals();
        return g;
    })();
    const paperMesh = new THREE.Mesh(K.own(paperGeo), paperMat);
    paperMesh.name = 'teletype_paper'; paperMesh.castShadow = true; paperMesh.receiveShadow = true;
    group.add(paperMesh);
    // the roll: paper wound on a card core, turning with each line feed
    const rollMat = (() => {
        const m = K.own(new THREE.MeshStandardNodeMaterial());
        const r = length(positionLocal.yz);
        const wound = sin(r.mul(3400.0)).mul(0.5).add(0.5);
        const endFace = step(0.9, abs(positionLocal.x).div(PAPER_W / 2));
        const core = smoothstep(0.019, 0.017, r);
        const pap = texture(T.paper.map, uv().mul(vec2(1.0, 4.0))).rgb;
        const fibre = dot(pap, vec3(0.2126, 0.7152, 0.0722)).div(0.32);
        const base = mix(paperTint.mul(fibre.sub(1).mul(0.3).add(1)).mul(0.97), paperTint.mul(wound.mul(0.12).add(0.84)), endFace);
        m.colorNode = mix(base, vec3(0.42, 0.33, 0.22), core.mul(endFace));
        m.roughnessNode = float(0.8);
        m.metalnessNode = float(0);
        return m;
    })();
    const roll = new THREE.Group(); roll.name = 'teletype_roll';
    {
        const pts = [[0.012, -PAPER_W / 2], [Pp.roll.r, -PAPER_W / 2], [Pp.roll.r, PAPER_W / 2], [0.012, PAPER_W / 2]].map(([r, y]) => new THREE.Vector2(r, y));
        roll.add(K.mesh(new THREE.LatheGeometry(pts, 64).rotateZ(Math.PI / 2), rollMat, 43, 'teletype_roll_paper'));
        roll.position.set(0, Pp.roll.y, Pp.roll.z);
        group.add(roll);
    }

    // ═══ PRINTING ═══════════════════════════════════════════════════════════
    const glyphOf = (ch) => { const c = ch.charCodeAt(0); return c >= 32 && c <= 95 ? c - 32 : 0; };
    const hash = (n) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };
    const clean = (s) => String(s ?? '').toUpperCase().replace(/\?/g, '').replace(/\r/g, '').replace(/\t/g, ' ');
    let cacheText = null, cacheN = -1, lines = [''];
    function layout(text, n) {
        const out = [''];
        for (let i = 0; i < n && i < text.length; i++) {
            const ch = text[i];
            if (ch === '\n') { out.push(''); continue; }
            if (out[out.length - 1].length >= COLS) out.push('');
            out[out.length - 1] += ch;
        }
        return out;
    }
    function writeBuffer() {
        bufData.fill(0);
        const Lc = lines.length - 1;
        for (let Ln = Math.max(0, Lc - ROWS + 1); Ln <= Lc; Ln++) {
            const row = Ln % ROWS, str = lines[Ln];
            for (let c = 0; c < str.length && c < COLS; c++) {
                const o = (row * BUF_W + c) * 4, g = glyphOf(str[c]);
                if (g === 0) continue;
                bufData[o] = g;
                bufData[o + 1] = Math.floor(hash(Ln * 131.7 + c * 7.3 + 1) * 255);
                const heavy = hash(Ln * 17.1 + c * 3.9 + 5) > 0.93 ? 1 : 0;
                bufData[o + 2] = Math.floor((0.55 + 0.45 * hash(Ln * 57.3 + c * 11.1 + 9)) * 255 * (heavy ? 1 : 0.85));
                bufData[o + 3] = 255;
            }
        }
        textBuf.needsUpdate = true;
    }
    const colX = (c) => -PAPER_W / 2 + MARGIN + (c + 0.5) * CHAR;
    const printed = { key: -1, env: 0 };
    function setText(fullText, nChars = Infinity) {
        const text = clean(fullText);
        const nTotal = Math.min(text.length, Math.max(0, nChars));
        const n = Math.floor(nTotal), frac = nTotal - n;
        if (text !== cacheText || n !== cacheN) {
            lines = layout(text, n);
            cacheText = text; cacheN = n;
            writeBuffer();
        }
        const Lc = lines.length - 1, col = lines[Lc].length;
        const next = n < text.length ? text[n] : null;
        let feed = 0, headCol = col;
        if (next === '\n' && frac > 0) { feed = sstep(frac / 0.7); headCol = col * (1 - sstep(frac)); }
        else if (next && frac > 0) headCol = col + sstep(frac);
        uLine.value = Lc + feed;
        printhead.position.x = colX(Math.min(COLS - 1, headCol)) - CHAR * 0.5;
        // the last struck character's key: down on the strike, released over the next character's time
        const last = n > 0 ? text[n - 1] : null;
        printed.key = last !== null && keyOf.has(last) ? keyOf.get(last) : -1;
        printed.env = n > 0 && nTotal < text.length + 1 ? 1 - sstep(frac * 1.6) : 0;
        return { line: Lc, col, lines: lines.length };
    }
    setText('', 0);

    // ── update ─────────────────────────────────────────────────────────────
    const _q = new THREE.Quaternion(), AX = new THREE.Vector3(1, 0, 0);
    function update(t, state = {}) {
        const s = state || {};
        uPower.value = clamp01(s.power ?? 1);
        const voice = clamp01(s.voice ?? 0);
        uVoice.value = voice;
        if (s.text !== undefined) setText(s.text, s.nChars ?? Infinity);
        // platen and roll turn with the paper (one line = LINE of paper travel)
        platen.quaternion.copy(platenQ0).multiply(_q.setFromAxisAngle(AX, -uLine.value * LINE / Pp.platenR));
        roll.rotation.x = uLine.value * LINE / Pp.roll.r;
        // the keyboard sings along: the struck key + a light voiced flutter across the home row
        const arr = uKeys.array;
        for (let i = 0; i < arr.length; i++) arr[i] = 0;
        if (printed.key >= 0) arr[printed.key] = printed.env;
        if (voice > 0.05) {
            const step8 = Math.floor(t * 9.0);
            for (let j = 0; j < 2; j++) {
                const k = 13 + Math.floor(hash(step8 * 3.1 + j * 17.7) * 38);
                arr[k] = Math.max(arr[k], voice * 0.8 * (1 - sstep((t * 9.0 - step8) * 1.3)));
            }
        }
    }
    update(0, {});

    return {
        group,
        parts: {
            paper: { mesh: paperMesh, setText, lines: () => lines.slice(), uniforms: { line: uLine }, texture: textBuf, glyphs: glyphArt.tex },
            printhead, platen, roll, keyboard, lamps: buttons,
            body: root.getObjectByName('teletype_machine'),
            uniforms: { power: uPower, voice: uVoice, line: uLine, keys: uKeys },
        },
        update,
        dispose() { group.removeFromParent(); K.dispose(); },
    };
}
