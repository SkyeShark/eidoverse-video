// mainframe.js — an IBM 7090-era computer room at Bell Labs, 1961 (DAISY, intro + verse 1).
//
// Kelly, Lochbaum and Mathews made a mainframe sing "Daisy Bell" in 1961 (the LP credits
// a 7090; dossier §3). HERO ASSET modelled in Blender (eidoverse/assets/models/
// voice_machines/blender/era1_mainframe.py → mainframe.glb): four 729-style tape drives (recessed
// reel deck behind smoked glass, door-leaf seams, header control strip, blue vacuum
// columns behind a glass door, side seams, back louvres; reels, head block, capstans,
// guides, tape runs), two-tone grey/blue frame cabinets (door leaves, louvre band,
// pulls, locks), a 7151-style operator console (recessed lamp field with brass bezels,
// paddle keys, emergency pull), floor cables into a grommet. Layered materials here:
// AmbientCG sets on UV0 + baked AO/edge/cavity masks on UV1 + curvature wear. Era logos
// are canvas homage (Skye, 09-23): the striped IBM wordmark on the drive plates and the
// console nameplate. (The striped mark is 1972; a 1961 room wore the solid 1956 one.)
//
//   const { build } = await import(new URL('props/voice_machines/mainframe.js', EIDOVERSE_DIR).href);
//   const room = await build(THREE, {});
//   scene.add(room.group);
//   room.update(t, { tapeSpeed, voice, power });   // per frame, in time order
//
// update(t, st):
//   tapeSpeed  1 = nominal (≈1.1 m/s of tape). The reels follow it EXACTLY: speed is
//              integrated frame to frame (trapezoid), so the film's curve — 1, then
//              (1-x)^1.6 to 0 — is the reels' angular speed. Negative rewinds.
//   tapeStop   { at, duration, curve } alternative: analytic in t (synthkit fx.tape_stop).
//   tapePos    metres of tape: overrides both.
//   voice      0..1 this era's voice loudness: the register lamps sparkle and brighten
//              with it (the machine visibly sings); the machine clock still freezes when
//              the tape stops.
//   power      0..1: every lamp, digit window and indicator (the lights dying).
// parts: reels[] { pivot, drive, side, packRadius }, lamps { bulbs, lenses, count, uniforms },
//   console (node; re-place freely), loops, row, uniforms { clock, power, voice }.
// Metres, +Y up, floor y = 0, facing +Z. Row ≈ 4.6 m wide; console front-right.

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
const TAPE_MPS = 1.1;

// striped homage of the IBM wordmark, drawn from rectangles and arcs (no font)
function drawIBM(ctx, x, y, h, ink, bg, stripes = 8) {
    const u = h / 10;                      // letter module
    const serif = u * 2.0, stem = u * 3.0;
    const drawSlab = (x0, w) => { ctx.fillRect(x0, y, w, serif); ctx.fillRect(x0, y + h - serif, w, serif); };
    ctx.fillStyle = ink;
    // I
    const Iw = u * 5.6;
    drawSlab(x, Iw); ctx.fillRect(x + (Iw - stem) / 2, y, stem, h);
    // B
    const Bx = x + Iw + u * 1.2, Bw = u * 8.4;
    ctx.fillRect(Bx, y, Bw - u * 2.4, serif); ctx.fillRect(Bx, y + h - serif, Bw - u * 2.4, serif);
    ctx.fillRect(Bx + u * 1.3, y, stem, h);
    ctx.fillRect(Bx, y + h / 2 - u * 0.9, Bw - u * 2.6, u * 1.8);
    for (const [cy, r] of [[y + h * 0.26, h * 0.26], [y + h * 0.735, h * 0.265]]) {
        ctx.beginPath(); ctx.arc(Bx + Bw - u * 2.4 - r * 0.05, cy, r, -Math.PI / 2, Math.PI / 2); ctx.closePath(); ctx.fill();
        ctx.fillStyle = bg;
        ctx.beginPath(); ctx.arc(Bx + Bw - u * 2.4 - r * 0.05, cy, r - stem * 0.95, -Math.PI / 2, Math.PI / 2); ctx.closePath(); ctx.fill();
        ctx.fillRect(Bx + u * 1.3 + stem, cy - (r - stem * 0.95), Bw - u * 2.4 - u * 1.3 - stem - r * 0.05, 2 * (r - stem * 0.95));
        ctx.fillStyle = ink;
    }
    // M
    const Mx = Bx + Bw + u * 1.2, Mw = u * 11.5;
    ctx.fillRect(Mx, y, u * 3.4, serif); ctx.fillRect(Mx + Mw - u * 3.4, y, u * 3.4, serif);
    ctx.fillRect(Mx, y + h - serif, u * 4.2, serif); ctx.fillRect(Mx + Mw - u * 4.2, y + h - serif, u * 4.2, serif);
    ctx.fillRect(Mx + u * 0.9, y, u * 2.1, h); ctx.fillRect(Mx + Mw - u * 3.2, y, stem, h);
    ctx.beginPath(); ctx.moveTo(Mx + u * 0.9, y); ctx.lineTo(Mx + u * 3.4, y); ctx.lineTo(Mx + Mw / 2 + u * 0.8, y + h * 0.78);
    ctx.lineTo(Mx + Mw - u * 3.4, y); ctx.lineTo(Mx + Mw - u * 3.2 + stem, y); ctx.lineTo(Mx + Mw - u * 3.2 + stem, y + u * 0.1);
    ctx.lineTo(Mx + Mw / 2 + u * 0.8, y + h); ctx.lineTo(Mx + Mw / 2 - u * 0.6, y + h); ctx.closePath(); ctx.fill();
    const wAll = Mx + Mw - x;
    // stripes: background gaps across the whole mark
    const g = h / (stripes * 1.7 - 0.7), s = g * 1.7;
    ctx.fillStyle = bg;
    for (let k = 1; k < stripes; k++) ctx.fillRect(x - 1, y + k * s - g, wAll + 2, g * 0.7);
    return wAll;
}

export async function build(THREE, opts = {}) {
    const K = await craftKit(THREE);
    const {
        uniform, uniformArray, vec2, vec3, float, texture, uv, attribute, mix, smoothstep, step, select,
        fract, floor, mod, exp2, abs, max, length, positionLocal,
    } = THREE;
    const SANS = '"Bahnschrift", "Segoe UI", Arial, sans-serif';

    const gltf = await K.loadGLB(opts.glb ?? 'mainframe.glb');
    const mask = await K.loadTex('mainframe_mask.png', { flipY: false, repeat: false });
    const L = await K.loadJSON('mainframe_layout.json');
    const T = {
        enamel: await K.pbr('PaintedMetal002'), plastic: await K.pbr('Plastic013B_1k'), grey: await K.pbr('Plastic018B_1k'),
        gloss: await K.pbr('Plastic003_1k'), satin: await K.pbr('Plastic006_1k'), chrome: await K.pbr('Metal049A'),
        alu: await K.pbr('Metal041A'), crinkle: await K.pbr('Metal046A'), rubber: await K.pbr('Rubber004_1k'),
        prints: await K.pbr('Fingerprints002_1k', { normal: false, rough: false }),
        smear: await K.pbr('Smear004_1k', { normal: false, rough: false }),
    };
    const uClock = uniform(0), uPower = uniform(opts.power ?? 1), uVoice = uniform(0), uT = uniform(0);

    // ── lamp logic (GPU): aLamp = (kind, a, b) ────────────────────────────
    //   kind 0: register bit (a = row id, b = column) — random word, per-row rate
    //   kind 1: counter bit  (a = row id, b = bit)    — binary count of the clock
    //   kind 2: steady       (a = on 0/1, b = blink Hz)
    // the voice adds a sparkle: extra bits flicker at 12 Hz in proportion to loudness
    const hash11 = (x) => { let p = fract(x.mul(0.1031)); p = p.mul(p.add(33.33)); p = p.mul(p.add(p)); return fract(p); };
    const lampOn = (aL) => {
        const kind = aL.x, a = aL.y, b = aL.z;
        const rate = mix(float(2.2), float(9.0), hash11(a.mul(7.13).add(1.7)));
        const tr = uClock.mul(rate).add(hash11(a.mul(3.7).add(0.3)).mul(17.0));
        const k = floor(tr);
        const bitAt = (kk) => step(0.5, hash11(kk.mul(1.37).add(a.mul(57.1)).add(b.mul(13.97))));
        const reg = mix(bitAt(k.sub(1)), bitAt(k), smoothstep(0.0, 0.22, fract(tr)));
        const n = floor(uClock.mul(6.0).add(a.mul(29.0)));
        const cnt = mod(floor(n.div(exp2(b))), 2.0);
        const blink = select(b.greaterThan(0.001), step(0.5, fract(uT.mul(b))), float(1));
        const steady = a.mul(blink);
        const base = select(kind.lessThan(0.5), reg, select(kind.lessThan(1.5), cnt, steady));
        const sp = step(hash11(floor(uT.mul(12.0)).mul(0.91).add(a.mul(17.3)).add(b.mul(5.1))), uVoice.mul(0.55))
            .mul(step(kind, 1.5));
        return max(base, sp);
    };
    const aLamp = attribute('aLamp', 'vec3');
    const glow = uPower.mul(uVoice.mul(0.6).add(0.85));

    // ── role materials ─────────────────────────────────────────────────────
    const enamelArgs = { set: T.enamel, lum: 0.181, lumContrast: 0.07, mottle: 0.045, repeat: 1.4, roughMul: 1.3, roughAdd: 0.12,
        normalScale: 0.55, mask, grime: 0.6, edge: 0.8, edgeRough: 0.55, dust: 0.3, imperf: T.smear, imperfAmt: 0.12 };
    const R = {
        enamel: K.roleMat({ ...enamelArgs, tint: 0xdcd5c2, grimeColor: 0x4d463a, edgeColor: 0x8a8577 }),
        greyenamel: K.roleMat({ ...enamelArgs, tint: 0xb3b0a6, grimeColor: 0x49443a, edgeColor: 0x6e6b63 }),
        blue: K.roleMat({ ...enamelArgs, tint: 0x3a5573, grimeColor: 0x1f252a, edgeColor: 0x8f949a, dustColor: 0x7d8189 }),
        darkpaint: K.roleMat({ ...enamelArgs, tint: 0x2a2b2d, grimeColor: 0x141414, edgeColor: 0x5a5b5d, dust: 0.1 }),
        columnblue: K.roleMat({ ...enamelArgs, tint: 0x3f86d8, grime: 0.25, grimeColor: 0x1b2b3d, edge: 0.2, edgeColor: 0x8fb3dc, dust: 0.1, ao: 0.35 }),
        laminate: K.roleMat({ set: T.grey, lum: 0.187, lumContrast: 0.25, tint: 0xd2cec3, repeat: 1.2, roughMul: 0.8, normalScale: 0.3,
            mask, grime: 0.3, edge: 0.4, edgeColor: 0x8b877c, dust: 0.25, imperf: T.prints, imperfRepeat: 1.6, imperfAmt: 0.25 }),
        panelbase: K.roleMat({ set: T.grey, lum: 0.187, lumContrast: 0.2, tint: 0x5b5c5a, repeat: 2.0, normalScale: 0.3, mask }),
        plinth: K.roleMat({ set: T.satin, lum: 0.002, lumContrast: 0.2, tint: 0x242425, repeat: 2.0, roughMul: 1.8, mask, grime: 0.6, dust: 0.4 }),
        crinkle: K.roleMat({ set: T.crinkle, lum: 0.108, lumContrast: 0.8, tint: 0x232323, repeat: 3.0, metal: 0.3, roughMul: 3.0,
            normalScale: 1.4, mask, grime: 0.35, edge: 0.4, edgeColor: 0x6f6a62, edgeMetal: 1 }),
        alu: K.roleMat({ set: T.alu, tint: 0xe6e8ea, repeat: 3.0, metal: 1, roughMul: 1.5, normalScale: 0.5, mask, grime: 0.4,
            grimeColor: 0x46423a, imperf: T.prints, imperfRepeat: 3.0, imperfAmt: 0.2 }),
        chrome: K.roleMat({ set: T.chrome, repeat: 2.5, metal: 1, roughAdd: 0.05, normalScale: 0.4, mask, grime: 0.3,
            imperf: T.prints, imperfRepeat: 3.5, imperfAmt: 0.25 }),
        brass: K.roleMat({ set: T.alu, lum: 0.488, lumContrast: 1.2, tint: 0xcfa45a, repeat: 6.0, metal: 1, roughMul: 1.8,
            normalScale: 0.5, mask, grime: 0.5, grimeColor: 0x3b2a14 }),
        blackplastic: K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.3, tint: 0x141414, repeat: 3.0, roughMul: 1.2, normalScale: 0.4,
            mask, grime: 0.2, edge: 0.4, edgeColor: 0x3c3c3c }),
        keydark: K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 0.6, tint: 0x55575a, repeat: 6.0, roughMul: 0.7, normalScale: 0.3,
            mask, grime: 0.3, edge: 0.5, edgeColor: 0x9a9da0 }),
        keylight: K.roleMat({ set: T.plastic, lum: 0.807, lumContrast: 0.6, tint: 0xe4e1d8, repeat: 6.0, roughMul: 0.7, normalScale: 0.3,
            mask, grime: 0.45, grimeColor: 0x7d776a, edge: 0.3, edgeColor: 0xb8b3a6 }),
        red: K.roleMat({ set: T.gloss, lum: 0.006, lumContrast: 0.2, tint: 0xa3261d, repeat: 4.0, clearcoat: 0.4, mask }),
        rubber: K.roleMat({ set: T.rubber, lum: 0.025, lumContrast: 0.6, tint: 0x161616, repeat: 6.0, mask }),
        cable: K.roleMat({ set: T.rubber, lum: 0.025, lumContrast: 0.8, tint: 0x1c1c1d, repeat: 8.0, normalScale: 0.6, roughMul: 0.9,
            mask, grime: 0.3, dust: 0.5 }),
        tape: K.roleMat({ flat: 0x21150d, rough: 0.28, mask }),
        reelhub: K.roleMat({ set: T.alu, tint: 0xd6d9dc, repeat: 8.0, metal: 1, roughMul: 1.4, normalScale: 0.4, mask, grime: 0.3 }),
        smoked: K.glass({ color: 0x07090c, opacity: 0.30, rough: 0.02, smudge: 0.25, imperf: T.smear }),
        clearglass: K.glass({ color: 0x141b24, opacity: 0.14, rough: 0.02, smudge: 0.2, imperf: T.prints }),
    };
    // reels: one draw call each — the sub-material is chosen by position in the reel's
    // own frame (axis +Z toward the viewer): hub cap, knob, hub, flanges, tape pack
    const reelMat = (() => {
        const m = K.own(new THREE.MeshStandardNodeMaterial());
        const pl = positionLocal, r = length(pl.xy), az = abs(pl.z);
        const knob = step(0.0253, pl.z).mul(step(r, 0.0118));
        const cap = step(0.0132, pl.z).mul(step(r, 0.0357)).mul(float(1).sub(knob));
        const hub = step(r, 0.0527).mul(step(az, 0.0137)).mul(float(1).sub(cap)).mul(float(1).sub(knob));
        const flange = step(0.0068, az).mul(step(0.0527, r)).mul(float(1).sub(cap)).mul(float(1).sub(knob));
        const pack = float(1).sub(cap).sub(knob).sub(hub).sub(flange).clamp(0, 1);
        const band = THREE.sin(r.mul(2400.0)).mul(0.5).add(0.5).mul(0.06).add(THREE.sin(r.mul(310.0)).mul(0.03));
        const n = THREE.mx_noise_float(pl.mul(60.0)).mul(0.5).add(0.5);
        const cWhite = vec3(0.80, 0.79, 0.75).mul(n.mul(0.06).add(0.97));
        const cTape = vec3(0.028, 0.018, 0.012).mul(band.add(0.94));
        const cHub = vec3(0.62, 0.64, 0.66), cBlack = vec3(0.02, 0.02, 0.021);
        m.colorNode = cWhite.mul(flange).add(cTape.mul(pack)).add(cHub.mul(hub.add(knob))).add(cBlack.mul(cap));
        m.roughnessNode = float(0.34).mul(flange).add(float(0.22).add(band).mul(pack)).add(float(0.24).mul(hub.add(knob))).add(float(0.4).mul(cap));
        m.metalnessNode = hub.add(knob);
        return m;
    })();
    const reelClear = (() => {
        const m = K.own(new THREE.MeshPhysicalNodeMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide }));
        const r = length(positionLocal.xy);
        const rings = smoothstep(0.40, 0.5, abs(fract(r.mul(38.0)).sub(0.5)));
        const rim = smoothstep(0.125, 0.1332, r);
        m.colorNode = vec3(0.30, 0.34, 0.38);
        m.opacityNode = float(0.035).add(rings.mul(0.05)).add(rim.mul(0.6));
        m.roughnessNode = float(0.04).add(rings.mul(0.1));
        m.specularIntensity = 0.5;
        m.metalnessNode = float(0);
        return m;
    })();

    // ── decals: IBM homage plates, the console panel art ───────────────────
    const plateArt = K.canvasTex(1024, 128, (ctx, w, h) => {
        ctx.fillStyle = '#0f1011'; ctx.fillRect(0, 0, w, h);
        const wI = drawIBM(ctx, 40, 22, 84, '#e9e6de', '#0f1011');
        ctx.fillStyle = '#e9e6de'; ctx.textBaseline = 'middle';
        ctx.font = `600 70px ${SANS}`; ctx.fillText('729', 40 + wI + 34, 62);
        const w729 = ctx.measureText('729').width;
        ctx.font = `600 34px ${SANS}`; ctx.fillText('II', 40 + wI + 34 + w729 + 8, 44);
        ctx.font = `600 30px ${SANS}`; K.spacedText(ctx, 'MAGNETIC TAPE UNIT', w - 300, 64, 3);
    }, { gltf: true });
    const nameArt = K.canvasTex(1024, 104, (ctx, w, h) => {
        ctx.fillStyle = '#f1efe9'; ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#0d1015'; ctx.fillRect(0, 0, 390, h);
        const wI = drawIBM(ctx, 26, 18, 68, '#f1efe9', '#0d1015');
        ctx.fillStyle = '#f1efe9'; ctx.textBaseline = 'middle';
        ctx.font = `700 64px ${SANS}`; ctx.fillText('7090', 26 + wI + 28, 54);
        ctx.fillStyle = '#2a2d33'; ctx.font = `600 34px ${SANS}`; K.spacedText(ctx, 'DATA PROCESSING SYSTEM', 700, 54, 4);
    }, { gltf: true });
    const P = L.console.panel;
    const panelArt = K.canvasTex(1024, 280, (ctx, w, h) => {
        const px = (x) => (x / P.w + 0.5) * w, py = (z) => (0.5 - z / P.h) * h;
        ctx.fillStyle = '#d4d0c6'; ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#6d6f6f'; ctx.fillRect(px(-0.705), py(0.205), px(-0.19) - px(-0.705), py(0.02) - py(0.205));
        ctx.fillStyle = '#4c4e50'; ctx.fillRect(px(-0.19), py(0.205), px(0.70) - px(-0.19), py(0.02) - py(0.205));
        ctx.fillStyle = '#5a5b58'; ctx.fillRect(px(-0.705), py(-0.005), px(0.70) - px(-0.705), py(-0.195) - py(-0.005));
        const TONES = ['#8b8d8c', '#3e3f41', '#8a8674'];
        const rows = new Map();
        for (const [x, z, k] of L.console.lamps) { if (k === 2) continue; const key = z.toFixed(3); if (!rows.has(key)) rows.set(key, []); rows.get(key).push(x); }
        for (const [zk, xs] of rows) {
            xs.sort((p, q) => p - q);
            const z = +zk, dx = xs.length > 1 ? xs[1] - xs[0] : 0.03;
            for (let g = 0; g * 3 < xs.length; g++) {
                const x0 = xs[g * 3] - dx / 2, x1 = xs[Math.min(xs.length - 1, g * 3 + 2)] + dx / 2;
                ctx.fillStyle = TONES[g % 3];
                ctx.fillRect(px(x0), py(z + 0.022), px(x1) - px(x0), py(z - 0.028) - py(z + 0.022));
            }
        }
        ctx.fillStyle = '#e9e6dd'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const lab = (t, x, z, s = 11) => { ctx.font = `600 ${s}px ${SANS}`; ctx.fillText(t, px(x), py(z)); };
        lab('I N D E X   A', -0.45, 0.181); lab('I N D E X   B', -0.45, 0.131); lab('I N D E X   C', -0.45, 0.081);
        lab('I N S T R U C T I O N', 0.27, 0.134); lab('I N S T R U C T I O N   C O U N T E R', 0.32, 0.081);
        lab('S T O R A G E', 0.0, -0.019); lab('A C C U M U L A T O R', 0.0, -0.079); lab('M - Q', 0.0, -0.139);
        ['TRAP', 'SIMULATE', 'AC OVFL', 'MQ OVFL', 'R/W SEL', 'DIV CHK', 'SENSE 1', 'SENSE 2', 'SENSE 3', 'SENSE 4']
            .forEach((t, i) => lab(t, -0.03 + i * 0.064, 0.19, 9));
        ctx.font = `600 8px ${SANS}`;
        for (const [x, z, k, a, b] of L.console.lamps) if (k !== 2) ctx.fillText(String(b % 36), px(x), py(z + 0.015));
        ctx.fillStyle = '#e1ded6';
        ctx.fillRect(px(-0.172), py(0.19), px(-0.058) - px(-0.172), py(0.07) - py(0.19));
        ctx.strokeStyle = '#2b2b2c'; ctx.lineWidth = 3; ctx.strokeRect(px(-0.705), py(0.205), px(0.70) - px(-0.705), py(-0.195) - py(0.205));
    }, { gltf: true });
    R.decal_plate = K.decalMat(plateArt.tex, { rough: 0.3, alpha: false });
    R.decal_name = K.decalMat(nameArt.tex, { rough: 0.3, alpha: false });
    R.decal_panel = K.decalMat(panelArt.tex, { rough: 0.45, alpha: false });

    // ── assemble the GLB ───────────────────────────────────────────────────
    const group = new THREE.Group(); group.name = 'mainframe_room';
    const root = gltf.scene;
    group.add(root);
    const missing = new Set();
    const reelBody = /^mainframe_reel_\d+_(file|machine)$/;
    root.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/^era1_/, '');
        let mat = R[role];
        if (role === 'reelclear') mat = reelClear;
        else if (reelBody.test(o.name) || reelBody.test(o.parent?.name || '')) mat = reelMat;
        if (!mat) missing.add(role);
        o.material?.dispose?.();
        o.material = mat || R.darkpaint;
        o.castShadow = !/decal|glass|smoked|reelclear/.test(role);
        o.receiveShadow = true;
        K.own(o.geometry);
    });
    if (missing.size) console.warn('[mainframe] no material for roles:', [...missing].join(', '));
    // merge each reel body's primitives into ONE mesh (one draw call per reel)
    const BGU = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');
    const reels = [];
    for (const r of L.reels) {
        const pivot = root.getObjectByName(r.name);
        if (!pivot) continue;
        const body = pivot.children.find(c => reelBody.test(c.name));
        if (body && !body.isMesh) {
            const parts = []; body.traverse(c => { if (c.isMesh) parts.push(c); });
            const geos = parts.map(c => {
                let g = c.geometry.clone(); g.applyMatrix4(c.matrix);
                for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'uv1'].includes(k)) g.deleteAttribute(k);
                return g.index ? g.toNonIndexed() : g;
            });
            const mm = new THREE.Mesh(K.own(BGU.mergeGeometries(geos, false)), reelMat);
            mm.name = body.name; mm.castShadow = true; mm.receiveShadow = true;
            mm.position.copy(body.position); mm.quaternion.copy(body.quaternion);
            parts.forEach(c => c.geometry.dispose());
            pivot.remove(body); pivot.add(mm);
        }
        reels.push({ pivot, drive: r.drive, side: r.side, packRadius: r.packRadius });
    }
    const q0 = new Map(reels.map(r => [r.pivot, r.pivot.quaternion.clone()]));
    const consoleNode = root.getObjectByName('mainframe_console');
    const rowNode = root.getObjectByName('mainframe_row');

    // ── GPU lamps from the layout ──────────────────────────────────────────
    const lampAttr = (g, a) => { const n = g.attributes.position.count, arr = new Float32Array(n * 3); for (let i = 0; i < n; i++) arr.set(a, i * 3); g.setAttribute('aLamp', new THREE.Float32BufferAttribute(arr, 3)); return g; };
    const panelN = new THREE.Vector3(...P.normal), panelU = new THREE.Vector3(...P.up), panelC = new THREE.Vector3(...P.center);
    const panelR = new THREE.Vector3().crossVectors(panelU, panelN).normalize();
    const panelQ = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(panelR, panelU, panelN));
    const onPanel = (x, z, h) => panelC.clone().addScaledVector(panelR, x).addScaledVector(panelU, z).addScaledVector(panelN, h);
    const bulbGeo = () => new THREE.SphereGeometry(0.0062, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2).rotateX(Math.PI / 2);
    const lampGeos = [];
    for (const [x, z, k, a, b] of L.console.lamps) {
        const g = K.prep(bulbGeo());
        g.applyQuaternion(panelQ); const p = onPanel(x, z, 0.0012); g.translate(p.x, p.y, p.z);
        lampGeos.push(lampAttr(g, [k, a, b]));
    }
    const bulbMat = K.roleMat({ flat: 0x4a3d2a, rough: 0.18, emissive: vec3(1.0, 0.80, 0.48).mul(lampOn(aLamp).mul(glow).mul(4.2)) });
    const bulbs = new THREE.Mesh(K.own(K.merge(lampGeos)), bulbMat);
    bulbs.name = 'mainframe_console_bulbs';
    consoleNode.add(bulbs);
    // lens atlas: 8 × 4 cells — lamp lenses (0-4), buttons (8-12), digits (16-25), console status (26-29)
    const LENS = [['SELECT', '#e8d25a'], ['READY', '#f1eee4'], ['FILE\nPROTECT', '#d8472f'], ['HIGH\nDENSITY', '#f1eee4'], ['TAPE\nINDICATE', '#d8472f']];
    const BTN = ['LOAD\nREWIND', 'START', 'CHANGE\nDENSITY', 'UNLOAD', 'RESET'];
    const STATUS = [['PROGRAM\nSTOP', '#b8352a'], ['I/O\nCHECK', '#d8d6cf'], ['READY', '#e9e6dc'], ['AUTO-\nMATIC', '#e6cf57']];
    const COLS = [['POWER\nON', '#b8352a'], ['COMP\nON', '#d8d6cf'], ['TEMP', '#d8d6cf'], ['CHECK', '#d8d6cf']];
    const ATL = { cols: 8, rows: 4 };
    const atlas = K.canvasTex(1024, 256, (ctx, w, h) => {
        const cw = w / ATL.cols, ch = h / ATL.rows;
        ctx.fillStyle = '#111'; ctx.fillRect(0, 0, w, h);
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const cell = (i, bg, txt, fg, px) => {
            const x = (i % ATL.cols) * cw, y = Math.floor(i / ATL.cols) * ch;
            ctx.fillStyle = bg; ctx.fillRect(x + 2, y + 2, cw - 4, ch - 4);
            const g = ctx.createLinearGradient(x, y, x, y + ch);
            g.addColorStop(0, 'rgba(255,255,255,0.12)'); g.addColorStop(1, 'rgba(0,0,0,0.14)');
            ctx.fillStyle = g; ctx.fillRect(x + 2, y + 2, cw - 4, ch - 4);
            ctx.fillStyle = fg; ctx.font = `600 ${px}px ${SANS}`;
            const lines = txt.split('\n');
            lines.forEach((ln, k) => ctx.fillText(ln, x + cw / 2, y + ch / 2 + (k - (lines.length - 1) / 2) * px * 1.05));
        };
        LENS.forEach(([t, c], i) => cell(i, c, t, '#1a1712', 17));
        BTN.forEach((t, i) => cell(8 + i, '#ecebe6', t, '#23211d', 16));
        for (let d = 0; d < 10; d++) cell(16 + d, '#0b0b0b', String(d), '#f4f1e8', 50);
        STATUS.forEach(([t, c], i) => cell(26 + i, c, t, '#1b1814', 17));
        COLS.forEach(([t, c], i) => cell([5, 6, 7, 13][i], c, t, '#1b1814', 16));
    });
    const cellUV = (g, i) => {
        const c = i % ATL.cols, r = Math.floor(i / ATL.cols);
        const u0 = c / ATL.cols, u1 = (c + 1) / ATL.cols, v1 = 1 - r / ATL.rows, v0 = 1 - (r + 1) / ATL.rows;
        const uvA = g.attributes.uv;
        for (let k = 0; k < uvA.count; k++) uvA.setXY(k, u0 + uvA.getX(k) * (u1 - u0), v0 + uvA.getY(k) * (v1 - v0));
        return g;
    };
    const lensMat = K.roleMat({ flat: 0xffffff, rough: 0.22 });
    lensMat.colorNode = texture(atlas.tex, uv()).rgb;
    lensMat.emissiveNode = texture(atlas.tex, uv()).rgb.mul(lampOn(aLamp).mul(glow).mul(1.9));
    const lensGeos = [];
    L.drives.forEach((dv, d) => {
        const add = (pos, cell, w, h, dep, a) => {
            const g = K.prep(cellUV(K.rbox(w, h, dep, 0.002), cell)); g.translate(pos[0], pos[1], pos[2]);
            lensGeos.push(lampAttr(g, a));
        };
        add(dv.digit, 16 + ((d + 1) % 10), 0.050, 0.052, 0.004, [2, 1, 0]);
        const state = [[d !== 3 ? 1 : 0, d === 0 ? 1.5 : 0], [1, 0], [d % 2, 0], [1, 0], [d === 2 ? 1 : 0, 0]];
        dv.lens.forEach((p, j) => add(p, j, 0.066, 0.028, 0.006, [2, state[j][0], state[j][1]]));
        dv.buttons.forEach((p, j) => add([p[0], p[1], p[2] + 0.002], 8 + j, 0.066, 0.026, 0.010, [2, 0, 0]));
    });
    const lenses = new THREE.Mesh(K.own(K.merge(lensGeos)), lensMat);
    lenses.name = 'mainframe_lenses';
    root.add(lenses);
    const cl = [];
    L.console.status.forEach(([x, z], i) => {
        const g = K.prep(cellUV(K.rbox(0.050, 0.048, 0.006, 0.002), 26 + i)); g.applyQuaternion(panelQ);
        const p = onPanel(x, z, 0.004); g.translate(p.x, p.y, p.z); cl.push(lampAttr(g, [2, i >= 2 ? 1 : 0, 0]));
    });
    L.console.column.forEach(([x, z], i) => {
        const g = K.prep(cellUV(K.rbox(0.040, 0.034, 0.006, 0.002), [5, 6, 7, 13][i])); g.applyQuaternion(panelQ);
        const p = onPanel(x, z, 0.004); g.translate(p.x, p.y, p.z); cl.push(lampAttr(g, [2, i === 0 ? 1 : 0, 0]));
    });
    const statusMesh = new THREE.Mesh(K.own(K.merge(cl)), lensMat);
    statusMesh.name = 'mainframe_console_status';
    consoleNode.add(statusMesh);
    const cabGeos = [];
    L.cabinets.forEach((c, i) => c.lamps.forEach((p, k) => {
        const g = K.prep(bulbGeo()); g.translate(p[0], p[1], p[2]); cabGeos.push(lampAttr(g, [0, 60 + i * 6 + k, k]));
    }));
    const cabBulbs = new THREE.Mesh(K.own(K.merge(cabGeos)), bulbMat);
    cabBulbs.name = 'mainframe_cabinet_bulbs';
    root.add(cabBulbs);

    // ── vacuum-column tape loops (GPU-deformed) ────────────────────────────
    const LOOP_BASE = 0.47, nLoops = L.drives.length * 2;
    const uLoop = uniformArray(new Array(nLoops).fill(LOOP_BASE), 'float');
    const loopGeos = [];
    L.drives.forEach((dv, d) => dv.loops.forEach(([cx, cz], k) => {
        const li = d * 2 + k;
        const runs = [-1, 1].map(sx => K.prep(new THREE.BoxGeometry(0.0016, 0.9, 0.0127, 1, 8, 1).translate(cx + sx * 0.031, 0.5, cz)));
        const u = K.prep(new THREE.TorusGeometry(0.031, 0.0008, 6, 24, Math.PI).rotateZ(Math.PI)
            .applyMatrix4(new THREE.Matrix4().makeScale(1, 1, 8)).translate(cx, 0.05, cz));
        const nRun = runs[0].attributes.position.count + runs[1].attributes.position.count;
        const g = K.merge([...runs, u]);
        const n = g.attributes.position.count, arr = new Float32Array(n * 2);
        for (let i = 0; i < n; i++) { arr[i * 2] = li; arr[i * 2 + 1] = i < nRun ? 1 : 2; }
        g.setAttribute('aLoop', new THREE.Float32BufferAttribute(arr, 2));
        loopGeos.push(g);
    }));
    const loopMat = (() => {
        const m = K.own(new THREE.MeshStandardNodeMaterial());
        const aLp = attribute('aLoop', 'vec2');
        const depth = uLoop.element(aLp.x.toInt());
        const mouth = float(0.95);
        const stretch = mouth.sub(depth).div(mouth.sub(0.05));
        const yRun = mouth.sub(mouth.sub(positionLocal.y).mul(stretch));
        const yU = positionLocal.y.sub(0.05).add(depth);
        m.positionNode = vec3(positionLocal.x, select(aLp.y.lessThan(1.5), yRun, yU), positionLocal.z);
        m.colorNode = vec3(0.028, 0.019, 0.013);
        m.roughnessNode = float(0.3);
        m.metalnessNode = float(0);
        return m;
    })();
    const loops = new THREE.Mesh(K.own(K.merge(loopGeos)), loopMat);
    loops.name = 'mainframe_tape_loops'; loops.frustumCulled = false;
    root.add(loops);

    // ── update ─────────────────────────────────────────────────────────────
    let lastT = null, lastSpeed = 0, pos = 0;
    function tapePosition(t, s) {
        if (typeof s.tapePos === 'number') return s.tapePos;
        const base = s.tapeSpeed ?? 1;
        if (s.tapeStop && typeof s.tapeStop.at === 'number') {
            const { at, duration = 1, curve = 2 } = s.tapeStop;
            if (t <= at) return base * TAPE_MPS * t;
            const u = Math.min(1, (t - at) / duration);
            return base * TAPE_MPS * (at + duration * (1 - Math.pow(1 - u, curve + 1)) / (curve + 1));
        }
        if (lastT === null || t < lastT) pos = base * TAPE_MPS * t;
        else pos += 0.5 * (lastSpeed + base) * TAPE_MPS * (t - lastT);       // trapezoid: follows the curve exactly
        lastT = t; lastSpeed = base;
        return pos;
    }
    const SPEED_MULT = [1.0, 0.72, -1.35, 0.55, 0.9, -0.6];
    const _q = new THREE.Quaternion(), AZ = new THREE.Vector3(0, 0, 1);
    function update(t, state = {}) {
        const s = state || {};
        const X = tapePosition(t, s);
        for (const r of reels) {
            const m = SPEED_MULT[r.drive % 6];
            r.pivot.quaternion.copy(q0.get(r.pivot)).multiply(_q.setFromAxisAngle(AZ, -(X * m) / r.packRadius));
        }
        uClock.value = X / TAPE_MPS;
        uT.value = t;
        uPower.value = clamp01(s.power ?? 1);
        uVoice.value = clamp01(s.voice ?? 0);
        for (let i = 0; i < nLoops; i++) {
            const m = SPEED_MULT[Math.floor(i / 2) % 6];
            uLoop.array[i] = LOOP_BASE + 0.09 * Math.sin(X * Math.abs(m) * 2.3 + i * 1.7) * Math.min(1, Math.abs(m)) + (i % 2 ? 0.05 : -0.03);
        }
    }
    update(0, {});

    return {
        group,
        parts: {
            reels,
            lamps: { bulbs, lenses, status: statusMesh, cabinets: cabBulbs, count: L.console.lamps.length + L.drives.length * 11 + 12,
                uniforms: { clock: uClock, power: uPower, voice: uVoice } },
            console: consoleNode, row: rowNode, loops,
            uniforms: { clock: uClock, power: uPower, voice: uVoice, loops: uLoop },
        },
        update,
        dispose() { group.removeFromParent(); K.dispose(); },
    };
}
