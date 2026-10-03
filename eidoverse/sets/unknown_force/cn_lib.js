// cn_lib.js — shared helpers for the UNKNOWN FORCE corridor (verse 2) and news (verse 5) sets.
// Texture/PBR loading, canvas → DataTexture (rows flipped, CPU mips: this stack ignores flipY on uploads and its
// automatic mip pass samples zeros), relief (height → normal) maps for engraved/embossed/embroidered material,
// geometry merging with metre UVs, a procedural HDR environment, seeded randomness and a few TSL helpers.
// Everything is deterministic; nothing here runs per frame except what a caller asks for.

export async function makeLib(THREE, here) {
    const T = THREE;
    const { createCanvas, GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
    const BGU = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');
    const owned = [];
    const own = (x) => { owned.push(x); return x; };

    // ───────────── paths / fonts ─────────────
    const urlPath = (u) => {
        let p = decodeURIComponent(new URL(u).pathname);
        if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1);
        return p;
    };
    const FONT_DIR = new URL('../../../eidoverse/assets/fonts/', here);
    const FONTS = {
        michroma: 'Michroma-Regular', blackops: 'BlackOpsOne-Regular', rajdhani: 'Rajdhani-Bold', exo: 'Exo2',
        sedgwick: 'SedgwickAveDisplay-Regular', kalam: 'Kalam-Bold', caveat: 'CaveatBrush-Regular',
        elite: 'SpecialElite-Regular', mono: 'ShareTechMono-Regular', audiowide: 'Audiowide-Regular',
    };
    const fam = {};
    for (const [k, f] of Object.entries(FONTS)) {
        const name = 'UF_' + f;
        try { GlobalFonts.registerFromPath(urlPath(new URL(f + '.ttf', FONT_DIR)), name); } catch (e) { console.warn('[cn_lib] font', f, e.message); }
        fam[k] = `"${name}"`;
    }

    // ───────────── seeded random ─────────────
    const rng = (seed = 1) => {
        let a = seed >>> 0;
        return () => {
            a |= 0; a = (a + 0x6D2B79F5) | 0;
            let t = Math.imul(a ^ (a >>> 15), 1 | a);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    };
    const clamp01 = (x) => Math.min(1, Math.max(0, x));
    const smooth = (a, b, x) => { const k = clamp01((x - a) / (b - a)); return k * k * (3 - 2 * k); };

    // ───────────── image textures ─────────────
    const texCache = new Map();
    const exists = (u) => { try { Deno.statSync(u); return true; } catch { return false; } };
    async function tex(u, srgb) {
        const k = String(u) + '|' + srgb;
        if (!texCache.has(k)) {
            const t = await globalThis.loadImageTexture(Deno.readFileSync(u), { srgb });
            t.wrapS = t.wrapT = T.RepeatWrapping;
            t.anisotropy = 8;
            if (srgb) t.colorSpace = T.SRGBColorSpace;
            texCache.set(k, own(t));
        }
        return texCache.get(k);
    }
    // a CC0 PBR set from the shared texture library (globalThis.fetchPBR: fetched once, on first use). Colour, normal
    // and roughness always; ao / met / disp only when asked for (a set picks its maps; an unasked one is not loaded).
    async function pbr(id, { res = '1k', ao = false, met = false, disp = false } = {}) {
        const { files: F } = await globalThis.fetchPBR(id, { res });
        const S = { id, col: await tex(F.diff, true), nrm: await tex(F.normal, false), rgh: await tex(F.rough, false) };
        if (ao && F.ao) S.ao = await tex(F.ao, false);
        if (met && F.metal) S.met = await tex(F.metal, false);
        if (disp && F.displacement) S.disp = await tex(F.displacement, false);
        return S;
    }

    // ───────────── canvas → texture ─────────────
    function buildMips(data, w, h) {
        const levels = [{ data, width: w, height: h }];
        let sw = w, sh = h, src = data;
        while (sw > 1 || sh > 1) {
            const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1), dst = new Uint8Array(dw * dh * 4);
            for (let y = 0; y < dh; y++) {
                const y0 = Math.min(sh - 1, 2 * y), y1 = Math.min(sh - 1, 2 * y + 1);
                for (let x = 0; x < dw; x++) {
                    const x0 = Math.min(sw - 1, 2 * x), x1 = Math.min(sw - 1, 2 * x + 1);
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
    // RGBA8 rows in canvas order (top row first) → DataTexture with v = 0 at the bottom
    function dataTex(rgbaTopDown, W, H, { srgb = true, mips = true, wrap = T.ClampToEdgeWrapping, tx = null } = {}) {
        const data = tx ? tx.image.data : new Uint8Array(W * H * 4);
        for (let y = 0; y < H; y++) data.set(rgbaTopDown.subarray(y * W * 4, (y + 1) * W * 4), (H - 1 - y) * W * 4);
        if (!tx) {
            tx = own(new T.DataTexture(data, W, H, T.RGBAFormat, T.UnsignedByteType));
            tx.colorSpace = srgb ? T.SRGBColorSpace : T.NoColorSpace;
            tx.magFilter = T.LinearFilter;
            tx.generateMipmaps = false;
            tx.anisotropy = 8;
            tx.wrapS = tx.wrapT = wrap;
            tx.flipY = false;
        }
        if (mips) { tx.mipmaps = buildMips(data, W, H); tx.minFilter = T.LinearMipmapLinearFilter; } else tx.minFilter = T.LinearFilter;
        tx.needsUpdate = true;
        return tx;
    }
    const canvasPixels = (cv) => {
        const id = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
        return new Uint8Array(id.data.buffer, id.data.byteOffset, id.data.byteLength);
    };
    const canvasTex = (cv, o = {}) => dataTex(canvasPixels(cv), cv.width, cv.height, o);
    // a canvas whose texture is rebuilt (with mips) only when redraw() is called
    function dynCanvas(W, H, draw, o = {}) {
        const cv = createCanvas(W, H);
        const g = cv.getContext('2d');
        const self = { canvas: cv, ctx: g, W, H, texture: null };
        self.redraw = (...args) => {
            draw(g, W, H, ...args);
            self.texture = dataTex(canvasPixels(cv), W, H, { ...o, tx: self.texture });
            return self.texture;
        };
        return self;
    }

    // ───────────── relief: grey height canvas → normal map (+ cavity) ─────────────
    // height in [0,1] from the canvas luminance (white = high). blur = box-blur radius (px, 2 passes) for bevels.
    function heightField(cv, { blur = 2, channel = 'lum' } = {}) {
        const W = cv.width, H = cv.height, p = canvasPixels(cv);
        let h = new Float32Array(W * H);
        for (let i = 0; i < W * H; i++) {
            h[i] = channel === 'a' ? p[i * 4 + 3] / 255 : (p[i * 4] * 0.2126 + p[i * 4 + 1] * 0.7152 + p[i * 4 + 2] * 0.0722) / 255;
        }
        if (blur > 0) h = boxBlur(h, W, H, blur, 2);
        return { h, W, H };
    }
    function boxBlur(src, W, H, r, passes = 1) {
        let a = src, b = new Float32Array(W * H);
        for (let p = 0; p < passes; p++) {
            for (let y = 0; y < H; y++) {           // horizontal
                let acc = 0; const row = y * W;
                for (let x = -r; x <= r; x++) acc += a[row + Math.min(W - 1, Math.max(0, x))];
                for (let x = 0; x < W; x++) {
                    b[row + x] = acc / (2 * r + 1);
                    acc += a[row + Math.min(W - 1, x + r + 1)] - a[row + Math.max(0, x - r)];
                }
            }
            const c = new Float32Array(W * H);
            for (let x = 0; x < W; x++) {           // vertical
                let acc = 0;
                for (let y = -r; y <= r; y++) acc += b[Math.min(H - 1, Math.max(0, y)) * W + x];
                for (let y = 0; y < H; y++) {
                    c[y * W + x] = acc / (2 * r + 1);
                    acc += b[Math.min(H - 1, y + r + 1) * W + x] - b[Math.max(0, y - r) * W + x];
                }
            }
            a = c;
        }
        return a;
    }
    // tangent-space normal map (OpenGL, +V up) from a top-down height field; strength = height units per pixel step
    function normalTex(hf, strength = 4, o = {}) {
        const { h, W, H } = hf;
        const out = new Uint8Array(W * H * 4);
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                const xm = Math.max(0, x - 1), xp = Math.min(W - 1, x + 1), ym = Math.max(0, y - 1), yp = Math.min(H - 1, y + 1);
                const dx = (h[y * W + xp] - h[y * W + xm]) * 0.5 * strength;
                const dyc = (h[yp * W + x] - h[ym * W + x]) * 0.5 * strength;   // canvas y (down)
                let nx = -dx, ny = dyc, nz = 1;                                  // dh/dv = -dh/dy_canvas
                const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
                const i = (y * W + x) * 4;
                out[i] = (nx * 0.5 + 0.5) * 255; out[i + 1] = (ny * 0.5 + 0.5) * 255; out[i + 2] = (nz * 0.5 + 0.5) * 255; out[i + 3] = 255;
            }
        }
        return dataTex(out, W, H, { srgb: false, ...o });
    }
    // packs up to four grey canvases / fields into one linear RGBA texture (masks)
    function packTex(chans, W, H, o = {}) {
        const out = new Uint8Array(W * H * 4);
        for (let c = 0; c < 4; c++) {
            const s = chans[c];
            if (s == null) { for (let i = 0; i < W * H; i++) out[i * 4 + c] = c === 3 ? 255 : 0; continue; }
            if (s instanceof Float32Array) { for (let i = 0; i < W * H; i++) out[i * 4 + c] = Math.max(0, Math.min(255, s[i] * 255)); continue; }
            const p = canvasPixels(s);
            for (let i = 0; i < W * H; i++) out[i * 4 + c] = p[i * 4];
        }
        return dataTex(out, W, H, { srgb: false, ...o });
    }

    // ───────────── geometry ─────────────
    const prep = (g, m) => {
        let q = g.index ? g.toNonIndexed() : g.clone();
        if (m) q.applyMatrix4(m);
        for (const k of Object.keys(q.attributes)) if (!['position', 'normal', 'uv'].includes(k)) q.deleteAttribute(k);
        if (!q.attributes.normal) q.computeVertexNormals();
        if (!q.attributes.uv) q.setAttribute('uv', new T.BufferAttribute(new Float32Array(q.attributes.position.count * 2), 2));
        q.morphAttributes = {};
        return q;
    };
    // box-projected metre UVs from each triangle's face normal (axis-aligned faces get exact world-metre UVs)
    function boxUV(g, scale = 1, off = [0, 0, 0]) {
        const p = g.attributes.position, uv = g.attributes.uv, n = p.count;
        const a = new T.Vector3(), b = new T.Vector3(), c = new T.Vector3(), e1 = new T.Vector3(), e2 = new T.Vector3();
        for (let i = 0; i < n; i += 3) {
            a.fromBufferAttribute(p, i); b.fromBufferAttribute(p, i + 1); c.fromBufferAttribute(p, i + 2);
            e1.subVectors(b, a); e2.subVectors(c, a); const fn = e1.cross(e2);
            const ax = Math.abs(fn.x), ay = Math.abs(fn.y), az = Math.abs(fn.z);
            for (let k = 0; k < 3; k++) {
                const v = k === 0 ? a : k === 1 ? b : c;
                const x = v.x + off[0], y = v.y + off[1], z = v.z + off[2];
                let u, w;
                if (ax >= ay && ax >= az) { u = fn.x > 0 ? -z : z; w = y; }
                else if (ay >= az) { u = x; w = fn.y > 0 ? -z : z; }
                else { u = fn.z > 0 ? x : -x; w = y; }
                uv.setXY(i + k, u / scale, w / scale);
            }
        }
        uv.needsUpdate = true;
        return g;
    }
    // collector: add(geometry, matrix?, {uv:'box'|'keep', scale}) … then mesh(material)
    function bucket(name) {
        const list = [];
        const B = {
            name,
            add(g, m = null, o = {}) {
                const q = prep(g, m);
                if ((o.uv ?? 'box') === 'box') boxUV(q, o.scale ?? 1, o.off);
                else if (o.uvScale) { const uv = q.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * o.uvScale[0], uv.getY(i) * o.uvScale[1]); }
                list.push(q);
                return B;
            },
            box(w, h, d, x, y, z, o = {}) {
                const g = new T.BoxGeometry(w, h, d);
                const m = new T.Matrix4();
                if (o.ry || o.rx || o.rz) m.makeRotationFromEuler(new T.Euler(o.rx || 0, o.ry || 0, o.rz || 0));
                m.setPosition(x, y, z);
                B.add(g, m, o);
                g.dispose();
                return B;
            },
            count: () => list.length,
            geometry() {
                if (!list.length) return null;
                const g = BGU.mergeGeometries(list, false);
                list.forEach((q) => q.dispose());
                list.length = 0;
                g.computeBoundingBox(); g.computeBoundingSphere();
                return own(g);
            },
            mesh(mat, o = {}) {
                const g = B.geometry();
                if (!g) return null;
                const m = new T.Mesh(g, mat);
                m.name = name;
                m.castShadow = o.castShadow ?? false;
                m.receiveShadow = o.receiveShadow ?? true;
                Object.assign(m.userData, o.userData || {});
                return m;
            },
        };
        return B;
    }
    const M4 = (x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, s = 1) => {
        const m = new T.Matrix4().compose(new T.Vector3(x, y, z), new T.Quaternion().setFromEuler(new T.Euler(rx, ry, rz)),
            Array.isArray(s) ? new T.Vector3(...s) : new T.Vector3(s, s, s));
        return m;
    };

    // ───────────── a procedural HDR environment (equirect, HalfFloat; PMREM'd by the material's envMap path) ─────────────
    function envTex(fn, W = 256, H = 128) {
        const data = new Uint16Array(W * H * 4);
        const toH = T.DataUtils.toHalfFloat;
        for (let j = 0; j < H; j++) {
            const v = (j + 0.5) / H, lat = (v - 0.5) * Math.PI, cy = Math.sin(lat), cr = Math.cos(lat);
            for (let i = 0; i < W; i++) {
                const u = (i + 0.5) / W, phi = (u - 0.5) * 2 * Math.PI;
                const d = [Math.cos(phi) * cr, cy, Math.sin(phi) * cr];
                const c = fn(d);
                const o = (j * W + i) * 4;
                data[o] = toH(c[0]); data[o + 1] = toH(c[1]); data[o + 2] = toH(c[2]); data[o + 3] = toH(1);
            }
        }
        const t = own(new T.DataTexture(data, W, H, T.RGBAFormat, T.HalfFloatType));
        t.mapping = T.EquirectangularReflectionMapping;
        t.colorSpace = T.LinearSRGBColorSpace;
        t.magFilter = T.LinearFilter; t.minFilter = T.LinearFilter; t.generateMipmaps = false;
        t.needsUpdate = true;
        return t;
    }

    // ───────────── TSL helpers ─────────────
    const { Fn, vec2, vec3, vec4, float, fract, dot, sin, cos, mix, smoothstep, clamp, max, min, abs, floor, texture,
        normalMap, uv, positionLocal, mx_noise_float, mx_fractal_noise_float, length } = T;
    // hash without sine (Hoskins), vec2 → [0,1); a pure expression (usable outside Fn)
    const hash21 = (p) => {
        const p3 = fract(vec3(p.x, p.y, p.x).mul(0.1031));
        const p4 = p3.add(dot(p3, vec3(p3.y, p3.z, p3.x).add(33.33)));
        return fract(p4.x.add(p4.y).mul(p4.z));
    };
    const hash21f = Fn(([p]) => hash21(p));
    const lum = (c) => dot(c, vec3(0.2126, 0.7152, 0.0722));
    const hex = (h, k = 1) => { const c = new T.Color(h); return vec3(c.r * k, c.g * k, c.b * k); };

    // a textured PBR material from an AmbientCG set. o:
    //   tile (metres per tile, number | [u,v]), uvNode (default uv()), offset [u,v]
    //   tint (hex | [r,g,b]), recolor(col) → col, macro (0..1 large-scale albedo variation), macroScale
    //   rough: [mul, add], metal (number) | 'map', nrm (normal strength), ao (bool)
    //   post({ col, rough, metal, uvN, P }) → { col?, rough?, metal?, emissive? }   — the material's own logic
    //   physical (bool) + physical props (sheen, clearcoat…), env (texture), envI (env intensity), side, transparent…
    function pbrMat(S, o = {}) {
        const Cls = o.physical ? T.MeshPhysicalNodeMaterial : T.MeshStandardNodeMaterial;
        const m = own(new Cls({ side: o.side ?? T.FrontSide }));
        m.name = o.name || S.id;
        const [tu, tv] = Array.isArray(o.tile) ? o.tile : [o.tile ?? 1, o.tile ?? 1];
        const base = o.uvNode ?? uv();
        const uvN = base.mul(vec2(1 / tu, 1 / tv)).add(vec2(...(o.offset ?? [0, 0])));
        const P = o.P ?? positionLocal;
        let col = texture(S.col, uvN).rgb;
        if (o.recolor) col = o.recolor(col, { uvN, P });
        if (o.tint != null) col = col.mul(Array.isArray(o.tint) ? vec3(...o.tint) : hex(o.tint));
        if (o.macro) {
            const mac = mx_fractal_noise_float(P.mul(o.macroScale ?? 0.35), 3, 2.0, 0.5);
            col = col.mul(mac.mul(o.macro).add(1.0));
        }
        let rough = texture(S.rgh, uvN).r;
        if (o.rough) rough = rough.mul(o.rough[0]).add(o.rough[1]);
        let metal = o.metal === 'map' && S.met ? texture(S.met, uvN).r : float(typeof o.metal === 'number' ? o.metal : 0);
        let emissive = null;
        if (o.post) {
            const r = o.post({ col, rough, metal, uvN, P });
            if (r.col) col = r.col;
            if (r.rough) rough = r.rough;
            if (r.metal) metal = r.metal;
            if (r.emissive) emissive = r.emissive;
            if (r.normal) m.normalNode = r.normal;
            if (r.opacity) m.opacityNode = r.opacity;
        }
        m.colorNode = col;
        m.roughnessNode = clamp(rough, 0.03, 1.0);
        m.metalnessNode = metal;
        if (!m.normalNode) m.normalNode = normalMap(texture(S.nrm, uvN), vec2(o.nrm ?? 1, o.nrm ?? 1));
        if (o.ao !== false && S.ao) m.aoNode = texture(S.ao, uvN).r.mul(o.aoAmt ?? 1).add(1 - (o.aoAmt ?? 1));
        if (emissive) m.emissiveNode = emissive;
        if (o.env) { m.envMap = o.env; m.envMapIntensity = o.envI ?? 1; }
        for (const k of ['sheen', 'sheenRoughness', 'clearcoat', 'clearcoatRoughness', 'transparent', 'opacity', 'depthWrite',
            'alphaTest', 'polygonOffset', 'polygonOffsetFactor', 'polygonOffsetUnits']) if (o[k] != null) m[k] = o[k];
        if (o.sheenColor) m.sheenColor = new T.Color(o.sheenColor);
        if (o.lightsNode) m.lightsNode = o.lightsNode;
        return m;
    }

    function disposeAll() {
        for (const x of owned) { try { x.dispose?.(); } catch { /* already gone */ } }
        owned.length = 0;
    }

    return {
        T, createCanvas, GlobalFonts, BGU, fam, own, owned, urlPath, rng, clamp01, smooth, exists,
        tex, pbr, buildMips, dataTex, canvasPixels, canvasTex, dynCanvas, heightField, boxBlur, normalTex, packTex,
        prep, boxUV, bucket, M4, envTex, hash21, hash21f, lum, hex, pbrMat, disposeAll,
    };
}

// fit a single line of text into a box (canvas units); returns the font size used
export function fitText(g, text, { x, y, maxW, maxH, family, weight = '', align = 'center', baseline = 'middle', track = 0 }) {
    let size = maxH;
    g.font = `${weight} ${size}px ${family}`.trim();
    const wOf = () => g.measureText(text).width + track * size * Math.max(0, text.length - 1);
    let w = wOf();
    if (w > maxW) { size = size * maxW / w; g.font = `${weight} ${size}px ${family}`.trim(); }
    g.textAlign = track ? 'left' : align;
    g.textBaseline = baseline;
    if (!track) { g.fillText(text, x, y); return size; }
    // tracked: draw glyph by glyph
    const total = wOf();
    let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
    for (const ch of text) { g.fillText(ch, cx, y); cx += g.measureText(ch).width + track * size; }
    return size;
}
