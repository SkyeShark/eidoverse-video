// c64.js — a 1982 home computer (the brown/beige "breadbin" wedge) with its 13" colour monitor behind it, for
// DAISY's museum of voices. Era marks as homage, drawn by us (blender/era_logos.py, baked): the commodore badge with
// the C= mark, rainbow stripes and 64, the C= key, and the monitor's commodore plate.
//
//   const { build } = await import(new URL('props/voice_machines/c64.js', EIDOVERSE_DIR).href);
//   const c = await build(THREE, {});
//   scene.add(c.group);
//   c.parts.screen.setText(['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'], true);
//   // per frame: c.update(t, { power: 0..1, voice: 0..1 })
//   //   power = monitor raster (CRT switch-on) + monitor LED;  voice = its own voice loudness → the raster
//   //   brightens on each syllable and the monitor's power LED pulses with it
//
// Screen: 40 × 25 characters, 8 × 8 pixel font drawn for this prop (C64-style: 2-px verticals, 1-px
// horizontals), light-blue text on a blue field inside a lighter border, blinking block cursor. cursorOn:
// true = blinks with t (period 2/3 s), 'solid' = always on, false = hidden.
// Pack: eidoverse/assets/models/voice_machines/ (README.md, SOURCES.md).
// Geometry + materials: the pack's c64.glb from blender/build_c64.py — the wedge case as one filleted profile mass
// with a real keyboard well cut along the 8.7° deck, rear grooves, badge recess, parting line, DE-9 control ports
// with metal D-shells and pins, back edge connectors; 70 dished, tapered keycaps with legends projected along the
// deck; the monitor cabinet with a real bezel opening, a sloping dark bezel that hugs the bulged glass, a lower
// panel with flap seam, jacks and button, vents cut in top and sides, and a tapered rear housing. AmbientCG
// Plastic013B/012B scans, AO grime, edge wear and yellowing baked to 2048 maps.
// Real sizes: computer 404 × 216 × 75 mm; monitor ≈ 368 × 342 × 400 mm. Metres, +Y up, on y = 0, facing +Z.
// parts: computer, keys, monitor, screen {mesh, setText, lines, power, screen}, leds {computer, monitor},
//        speaker {mesh, set(v)} (the monitor's side vents, lit from inside).
// Draw calls: 8.

export async function build(THREE, opts = {}) {
    const K = await eraKit(THREE);
    const { uniform } = THREE;
    const disposables = [];
    const track = (x) => { disposables.push(x); return x; };
    const group = new THREE.Group(); group.name = 'c64';
    const root = await K.loadGLB(new URL('../../assets/models/voice_machines/c64.glb', import.meta.url));
    const meshes = [];
    root.traverse((o) => { if (o.isMesh) meshes.push(o); });
    const one = (n) => { const m = meshes.find((x) => x.name === n); if (!m) throw new Error('[c64] GLB is missing ' + n); return m; };
    const comp = one('c64_comp'), keys = one('c64_keys'), mon = one('c64_mon');
    for (const m of [comp, keys, mon]) { m.material = track(K.bakedMaterial(m.material)); m.castShadow = m.receiveShadow = true; group.add(m); }
    const metals = meshes.filter((x) => x.name.startsWith('metal_') || x.parent?.name?.startsWith('metal_'));
    const metalMat = track(K.metalMaterial('#c4c4c8', 0.3));
    for (const m of metals) { m.material = metalMat; group.add(m); }
    const ledA = K.ledMaterial('#ff2a14'); track(ledA.mat);
    const ledB = K.ledMaterial('#ff3018'); track(ledB.mat);
    const compLed = one('led_c64_power'), monLed = one('led_mon_power');
    compLed.material = ledA.mat; monLed.material = ledB.mat;
    group.add(compLed, monLed);
    // the monitor's speaker lives behind its side vents: the voice lights them from inside
    const glowMesh = meshes.find((x) => x.name === 'glow_vents');
    const G = K.glowMaterial('#a79bff');
    if (glowMesh) { glowMesh.material = track(G.mat); group.add(glowMesh); }

    // the tube: the C64 raster (makeScreen canvas) under the glass, CRT switch-on, scanlines, pincushion
    const TW = 0.282, TH = 0.218;
    const power = uniform(1), gain = uniform(1);
    const CW = 768, CH = 576;                               // 2 × (384 × 288): the frame at double pixels
    const scrState = { lines: [], cursor: true, blinkPhase: 1, dirty: true };
    const scr = K.eraScreen({ width: TW, height: TH, px: CW, draw: (ctx) => drawC64(ctx, scrState) });
    track(scr.tex);
    const tubeMesh = one('screen_crt');
    K.flipUV(tubeMesh.geometry);
    tubeMesh.material = track(K.screenMaterial({
        tex: scr.tex, power, gain: gain.mul(0.72), flipV: true, glass: '#0f1110', rough: 0.34, coatRough: 0.04,
        barrel: 0.05, scan: 288, scanAmt: 0.32, corner: 0.09, vignette: 0.35, bleed: 0.0009, crtOn: true,
    }));
    group.add(tubeMesh);

    const setText = (lines, cursorOn = true) => {
        const arr = Array.isArray(lines) ? lines : String(lines ?? '').split('\n');
        const flat = [];
        for (const ln of arr) { const s = String(ln).toUpperCase(); if (!s.length) flat.push(''); for (let i = 0; i < s.length; i += 40) flat.push(s.slice(i, i + 40)); }
        const next = flat.slice(-24);
        if (next.join('\n') !== scrState.lines.join('\n') || cursorOn !== scrState.cursor) { scrState.lines = next; scrState.cursor = cursorOn; scrState.dirty = true; }
    };
    setText(['', '    **** SPEECH BASIC V2 ****', '', ' 64K RAM SYSTEM  38911 BASIC BYTES FREE', '', 'READY.'], true);
    scr.redraw(0); scrState.dirty = false;
    const parts = {
        computer: comp, keys, monitor: mon,
        screen: { mesh: tubeMesh, setText, get lines() { return scrState.lines.slice(); }, power, screen: scr.scr },
        leds: { computer: { mesh: compLed, level: ledA.level }, monitor: { mesh: monLed, level: ledB.level } },
        speaker: { mesh: glowMesh || null, set(v) { G.level.value = Math.max(0, v); } },
    };
    function update(t, state = {}) {
        const p = Math.max(0, state.power ?? 1), v = Math.max(0, Math.min(1, state.voice ?? 0));
        power.value = p;
        gain.value = 1 + 0.4 * v;                                   // the raster flares with each syllable
        ledA.level.value = 1.0;                                     // the computer is on the whole scene
        ledB.level.value = p > 0.02 ? 0.75 + 0.6 * v : 0.0;
        parts.speaker.set(p > 0.02 ? v * 0.8 : 0);
        if (state.lines !== undefined) setText(state.lines, state.cursorOn ?? true);
        const ph = scrState.cursor === true ? (Math.floor(t * 3) % 2 === 0 ? 1 : 0) : (scrState.cursor ? 1 : 0);
        if (ph !== scrState.blinkPhase) { scrState.blinkPhase = ph; scrState.dirty = true; }
        if (scrState.dirty) { scr.redraw(t); scrState.dirty = false; }
    }
    function dispose() {
        group.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
        for (const d of disposables) d.dispose?.();
        scr.scr.mesh.geometry.dispose(); scr.scr.material.dispose();
    }
    return { group, parts, update, dispose };

    // ── the raster: border, field, 40×25 text in an 8×8 font drawn for this prop, block cursor ──
    function drawC64(ctx, st) {
        const S = 2, BORDER = '#6c5eb5', FIELD = '#352879', INK = '#6c5eb5';
        ctx.fillStyle = BORDER; ctx.fillRect(0, 0, CW, CH);
        const x0 = (CW - 320 * S) / 2, y0 = (CH - 200 * S) / 2;
        ctx.fillStyle = FIELD; ctx.fillRect(x0, y0, 320 * S, 200 * S);
        ctx.fillStyle = INK;
        let row = 0;
        for (const line of st.lines) {
            for (let c = 0; c < Math.min(40, line.length); c++) {
                const gl = FONT8[line[c]];
                if (!gl) continue;
                for (let y = 0; y < 8; y++) {
                    const bits = gl[y];
                    for (let x = 0; x < 8; x++) if (bits[x] === '#') ctx.fillRect(x0 + (c * 8 + x) * S, y0 + (row * 8 + y) * S, S, S);
                }
            }
            row++;
        }
        if (st.blinkPhase && st.cursor) ctx.fillRect(x0, y0 + Math.min(24, row) * 8 * S, 8 * S, 8 * S);
    }
}

// 8×8 glyphs drawn for this prop in the home-computer style (2-px verticals, 1-px horizontals). Not a ROM dump.
const G = (s) => s.trim().split(/\s+/);
const FONT8 = {
    ' ': G('........ ........ ........ ........ ........ ........ ........ ........'),
    A: G('...##... ..####.. .##..##. .######. .##..##. .##..##. .##..##. ........'),
    B: G('.#####.. .##..##. .##..##. .#####.. .##..##. .##..##. .#####.. ........'),
    C: G('..####.. .##..##. .##..... .##..... .##..... .##..##. ..####.. ........'),
    D: G('.####... .##.##.. .##..##. .##..##. .##..##. .##.##.. .####... ........'),
    E: G('.######. .##..... .##..... .####... .##..... .##..... .######. ........'),
    F: G('.######. .##..... .##..... .####... .##..... .##..... .##..... ........'),
    G: G('..####.. .##..##. .##..... .##.###. .##..##. .##..##. ..####.. ........'),
    H: G('.##..##. .##..##. .##..##. .######. .##..##. .##..##. .##..##. ........'),
    I: G('..####.. ...##... ...##... ...##... ...##... ...##... ..####.. ........'),
    J: G('...####. ....##.. ....##.. ....##.. ....##.. .##.##.. ..###... ........'),
    K: G('.##..##. .##.##.. .####... .###.... .####... .##.##.. .##..##. ........'),
    L: G('.##..... .##..... .##..... .##..... .##..... .##..... .######. ........'),
    M: G('.##...## .###.### .####### .##.#.## .##...## .##...## .##...## ........'),
    N: G('.##..##. .###.##. .######. .######. .##.###. .##..##. .##..##. ........'),
    O: G('..####.. .##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ........'),
    P: G('.#####.. .##..##. .##..##. .#####.. .##..... .##..... .##..... ........'),
    Q: G('..####.. .##..##. .##..##. .##..##. .##..##. ..####.. ....###. ........'),
    R: G('.#####.. .##..##. .##..##. .#####.. .####... .##.##.. .##..##. ........'),
    S: G('..####.. .##..##. .##..... ..####.. .....##. .##..##. ..####.. ........'),
    T: G('.######. ...##... ...##... ...##... ...##... ...##... ...##... ........'),
    U: G('.##..##. .##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ........'),
    V: G('.##..##. .##..##. .##..##. .##..##. .##..##. ..####.. ...##... ........'),
    W: G('.##...## .##...## .##...## .##.#.## .####### .###.### .##...## ........'),
    X: G('.##..##. .##..##. ..####.. ...##... ..####.. .##..##. .##..##. ........'),
    Y: G('.##..##. .##..##. .##..##. ..####.. ...##... ...##... ...##... ........'),
    Z: G('.######. .....##. ....##.. ...##... ..##.... .##..... .######. ........'),
    0: G('..####.. .##..##. .##.###. .###.##. .##..##. .##..##. ..####.. ........'),
    1: G('...##... ...##... ..###... ...##... ...##... ...##... .######. ........'),
    2: G('..####.. .##..##. .....##. ....##.. ..##.... .##..... .######. ........'),
    3: G('..####.. .##..##. .....##. ...###.. .....##. .##..##. ..####.. ........'),
    4: G('.....##. ....###. ...####. .##..##. .####### .....##. .....##. ........'),
    5: G('.######. .##..... .#####.. .....##. .....##. .##..##. ..####.. ........'),
    6: G('..####.. .##..##. .##..... .#####.. .##..##. .##..##. ..####.. ........'),
    7: G('.######. .##..##. ....##.. ...##... ...##... ...##... ...##... ........'),
    8: G('..####.. .##..##. .##..##. ..####.. .##..##. .##..##. ..####.. ........'),
    9: G('..####.. .##..##. .##..##. ..#####. .....##. .##..##. ..####.. ........'),
    '.': G('........ ........ ........ ........ ........ ...##... ...##... ........'),
    ',': G('........ ........ ........ ........ ........ ...##... ...##... ..##....'),
    ':': G('........ ........ ...##... ........ ........ ...##... ........ ........'),
    ';': G('........ ........ ...##... ........ ........ ...##... ...##... ..##....'),
    '"': G('.##..##. .##..##. .##..##. ........ ........ ........ ........ ........'),
    "'": G('.....##. ....##.. ...##... ........ ........ ........ ........ ........'),
    '!': G('...##... ...##... ...##... ...##... ........ ........ ...##... ........'),
    '?': G('..####.. .##..##. .....##. ....##.. ...##... ........ ...##... ........'),
    '*': G('........ .##..##. ..####.. ######## ..####.. .##..##. ........ ........'),
    '-': G('........ ........ ........ .######. ........ ........ ........ ........'),
    '+': G('........ ...##... ...##... .######. ...##... ...##... ........ ........'),
    '=': G('........ ........ .######. ........ .######. ........ ........ ........'),
    '/': G('........ ......## .....##. ....##.. ...##... ..##.... .##..... ........'),
    '(': G('....##.. ...##... ..##.... ..##.... ..##.... ...##... ....##.. ........'),
    ')': G('..##.... ...##... ....##.. ....##.. ....##.. ...##... ..##.... ........'),
    '#': G('.##..##. .##..##. ######## .##..##. ######## .##..##. .##..##. ........'),
    '$': G('...##... ..#####. .##..... ..####.. .....##. .#####.. ...##... ........'),
    '<': G('....###. ...###.. ..###... .###.... ..###... ...###.. ....###. ........'),
    '>': G('.###.... ..###... ...###.. ....###. ...###.. ..###... .###.... ........'),
    '%': G('.##...## .##..##. ....##.. ...##... ..##.... .##..##. ##...##. ........'),
};

// ===== ERA KIT BEGIN — shared helpers for the DAISY era-2 machines (identical copy in speakspell/c64/mac1984/dectalk/desktop2001; edit all five together) =====
async function eraKit(THREE) {
    const {
        Fn, uniform, texture, uv, vec2, vec3, vec4, float, mix, clamp, smoothstep, abs, max, dot, pow, normalize,
        positionLocal, normalLocal, positionWorld, normalWorldGeometry, normalViewGeometry, positionView, dFdx, dFdy,
        cameraPosition, modelWorldMatrix, cos, fwidth, length, min,
    } = THREE;
    const { RoundedBoxGeometry } = await import('npm:three@0.184.0/addons/geometries/RoundedBoxGeometry.js');
    const { mergeGeometries, mergeVertices } = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');

    // deterministic rng (never Math.random)
    const rng = (seed) => {
        let s = ((seed | 0) * 2654435761) >>> 0;
        return () => {
            s = (s + 0x6D2B79F5) >>> 0;
            let t = s;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    };
    const lin = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };     // sRGB hex → linear vec3 node
    const makeCanvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };

    // ── CPU mip chains. The stack's auto-mipmap pass samples zero at non-base levels; explicit levels upload fine
    //    (same finding as render_scene.mjs _buildCpuMips). alphaWeighted: colour averaged by alpha, so transparent
    //    texels never darken a decal's edge.
    function buildMips(data, w, h, alphaWeighted) {
        const levels = [{ data, width: w, height: h }];
        let sw = w, sh = h, src = data;
        while (sw > 1 || sh > 1) {
            const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
            const dst = new Uint8Array(dw * dh * 4);
            for (let y = 0; y < dh; y++) {
                const r0 = Math.min(sh - 1, y * 2) * sw, r1 = Math.min(sh - 1, y * 2 + 1) * sw;
                for (let x = 0; x < dw; x++) {
                    const c0 = Math.min(sw - 1, x * 2), c1 = Math.min(sw - 1, x * 2 + 1);
                    const a = (r0 + c0) * 4, b = (r0 + c1) * 4, c = (r1 + c0) * 4, d = (r1 + c1) * 4, o = (y * dw + x) * 4;
                    if (alphaWeighted) {
                        const wa = src[a + 3], wb = src[b + 3], wc = src[c + 3], wd = src[d + 3], ws = wa + wb + wc + wd;
                        for (let k = 0; k < 3; k++) {
                            dst[o + k] = ws > 0
                                ? Math.round((src[a + k] * wa + src[b + k] * wb + src[c + k] * wc + src[d + k] * wd) / ws)
                                : (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                        }
                        dst[o + 3] = (ws + 2) >> 2;
                    } else {
                        for (let k = 0; k < 4; k++) dst[o + k] = (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                    }
                }
            }
            levels.push({ data: dst, width: dw, height: dh });
            sw = dw; sh = dh; src = dst;
        }
        return levels;
    }

    // ── canvas → DataTexture. Rows are flipped on the CPU so canvas-top lands at v = 1 on three.js UVs, which means
    //    the texture works with texture(tex, anyUV) — no hidden repeat/offset matrix to lose on a custom UV.
    function canvasTexture(cv, o = {}) {
        const { srgb = true, mips = true, repeat = false, nearest = false, alphaWeighted = true } = o;
        const w = cv.width, h = cv.height;
        const tex = new THREE.DataTexture(new Uint8Array(w * h * 4), w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        tex.wrapS = tex.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
        tex.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
        tex.minFilter = mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
        tex.generateMipmaps = false;
        tex.anisotropy = 8;
        tex.userData.noMips = true;
        tex.userData._era = { cv, mips, alphaWeighted };
        refreshCanvasTexture(tex);
        return tex;
    }
    function refreshCanvasTexture(tex) {
        const { cv, mips, alphaWeighted } = tex.userData._era;
        const w = cv.width, h = cv.height, row = w * 4;
        const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
        const data = new Uint8Array(w * h * 4);
        for (let y = 0; y < h; y++) data.set(src.subarray((h - 1 - y) * row, (h - y) * row), y * row);
        tex.image = { data, width: w, height: h };
        if (mips) tex.mipmaps = buildMips(data, w, h, alphaWeighted);
        tex.needsUpdate = true;
    }

    // ── makeScreen (eidoverse/screen.js) owns the canvas → texture path for every in-world display. Its texture
    //    uploads canvas rows top-down (it flips through repeat/offset, which a custom-UV sample skips), so screen
    //    materials sample it at (u, 1 - v). This adds CPU mips after each redraw (no shimmer when minified).
    function eraScreen({ width, height, px, draw, nearest = false }) {
        if (typeof globalThis.makeScreen !== 'function') throw new Error('[era] makeScreen missing — load inside the eidoverse renderer');
        const scr = globalThis.makeScreen({ width, height, px, draw, auto: false, transparent: false });
        const tex = scr.texture;
        tex.generateMipmaps = false;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
        tex.anisotropy = 8;
        const remip = () => {
            const im = tex.image;
            if (im && im.data) tex.mipmaps = buildMips(im.data, im.width, im.height, false);
        };
        remip();
        const redraw = (t) => { scr.update(t); remip(); tex.needsUpdate = true; };
        return { scr, tex, redraw };
    }

    // ── one shared tiling noise (4 independent periodic fbm channels: R period 4, G 8, B 32, A 64 cells per tile)
    function noiseTexture() {
        const KEY = '__daisyEraNoise_v1';
        if (globalThis[KEY]) return globalThis[KEY];
        const N = 256, data = new Uint8Array(N * N * 4);
        const chans = [[4, 5, 11], [8, 4, 23], [32, 3, 37], [64, 2, 53]];
        for (let ch = 0; ch < 4; ch++) {
            const [P, oct, seed] = chans[ch], r = rng(seed), lats = [];
            for (let o = 0; o < oct; o++) {
                const p = P << o, L = new Float32Array(p * p);
                for (let i = 0; i < L.length; i++) L[i] = r();
                lats.push([p, L]);
            }
            for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
                let v = 0, amp = 0.5, tot = 0;
                for (let o = 0; o < oct; o++) {
                    const [p, L] = lats[o], fx = x / N * p, fy = y / N * p;
                    const xi = Math.floor(fx), yi = Math.floor(fy), xf = fx - xi, yf = fy - yi;
                    const X0 = xi % p, X1 = (xi + 1) % p, Y0 = (yi % p) * p, Y1 = ((yi + 1) % p) * p;
                    const u = xf * xf * (3 - 2 * xf), w = yf * yf * (3 - 2 * yf);
                    const a = L[Y0 + X0], b = L[Y0 + X1], c = L[Y1 + X0], d = L[Y1 + X1];
                    v += amp * (a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w);
                    tot += amp; amp *= 0.5;
                }
                data[(y * N + x) * 4 + ch] = Math.round(255 * v / tot);
            }
        }
        const tex = new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.colorSpace = THREE.NoColorSpace;
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.magFilter = THREE.LinearFilter;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.generateMipmaps = false;
        tex.mipmaps = buildMips(data, N, N, false);
        tex.userData.noMips = true;
        tex.needsUpdate = true;
        globalThis[KEY] = tex;
        return tex;
    }
    const NOISE = noiseTexture();

    // object-space triplanar (the prop can roll in without the grain swimming)
    const triplanar = (scale) => {
        const p = positionLocal.mul(scale);
        const n = abs(normalLocal);
        const w = n.div(max(n.x.add(n.y).add(n.z), 1e-4));
        return texture(NOISE, p.yz).mul(w.x).add(texture(NOISE, p.xz).mul(w.y)).add(texture(NOISE, p.xy).mul(w.z));
    };
    // per-pixel curvature in 1/m (+ convex, − concave); reads the vertex normal, never the shading normal
    const curvature = () => {
        const dNx = dFdx(normalWorldGeometry), dPx = dFdx(positionWorld);
        const dNy = dFdy(normalWorldGeometry), dPy = dFdy(positionWorld);
        return dot(dNx, dPx).div(max(dot(dPx, dPx), 1e-12)).add(dot(dNy, dPy).div(max(dot(dPy, dPy), 1e-12)));
    };
    // surface-gradient bump (Mikkelsen) from a height node in metres → view-space normal
    const bumpNormal = (h) => {
        const N = normalViewGeometry;
        const dpx = dFdx(positionView), dpy = dFdy(positionView);
        const r1 = dpy.cross(N), r2 = N.cross(dpx);
        const det = dot(dpx, r1);
        const grad = det.sign().mul(dFdx(h).mul(r1).add(dFdy(h).mul(r2)));
        return normalize(abs(det).mul(N).sub(grad));
    };

    // ── moulded plastic: base colour + large-scale ageing (yellowing/fading, stronger on up-facing surfaces),
    //    mottling, grime in concave fillets, polished convex edges, a little dust on top, roughness speckle and a
    //    fine orange-peel bump. Optional printed decal (texture with alpha) through decalUV.
    function plastic(o = {}) {
        const {
            color = '#d6ccb0', aged = null, ageAmt = 0.3, grime = '#3e372d', grimeAmt = 0.5, dust = '#b9b3a4',
            dustAmt = 0.12, rough = 0.5, roughVar = 0.12, edge = 0.25, peel = 0.00006, scale = 1,
            decal = null, decalUV = null, decalRough = null, colorNode = null, emissive = null, clearcoat = 0,
            clearcoatRough = 0.12, side = THREE.FrontSide, mottle = 0.08,
        } = o;
        const mat = clearcoat > 0
            ? new THREE.MeshPhysicalNodeMaterial({ clearcoat, clearcoatRoughness: clearcoatRough, side })
            : new THREE.MeshStandardNodeMaterial({ side });
        mat.metalness = 0;
        const nb = triplanar(1.3 * scale);      // r: ~20 cm blotches, g: ~10 cm mottle
        const nm = triplanar(6.0 * scale);      // b: ~5 mm grime breakup, a: ~2.6 mm speckle
        const cv = curvature();
        const edgeM = smoothstep(0.25, 0.9, clamp(cv.mul(0.004), 0, 1));
        const cavM = smoothstep(0.2, 0.85, clamp(cv.mul(-0.004), 0, 1));
        const up = pow(clamp(normalWorldGeometry.y, 0, 1), 2.0);
        let c = colorNode || lin(color);
        c = c.mul(nb.g.sub(0.5).mul(mottle * 2).add(1.0));
        if (aged) c = mix(c, lin(aged), clamp(smoothstep(0.38, 0.72, nb.r.add(up.mul(0.22))).mul(ageAmt), 0, 1));
        c = mix(c, lin(grime), clamp(cavM.mul(grimeAmt).mul(nm.b.add(0.35)), 0, 1));
        c = mix(c, c.mul(1.12), edgeM.mul(edge));
        c = mix(c, lin(dust), clamp(up.mul(dustAmt).mul(smoothstep(0.3, 0.7, nm.r)), 0, 1));
        let r = float(rough).add(nm.a.sub(0.5).mul(roughVar * 2)).sub(edgeM.mul(0.12)).add(up.mul(dustAmt * 0.5));
        if (decal) {
            const duv = decalUV || uv();
            const d = texture(decal, duv);
            // faces mapped outside 0..1 (planarUVFacing) stay unprinted at every mip level
            const inside = THREE.step(0.0, duv.x).mul(THREE.step(0.0, duv.y)).mul(THREE.step(duv.x, 1.0)).mul(THREE.step(duv.y, 1.0));
            const da = d.a.mul(inside);
            c = mix(c, d.rgb, da);
            if (decalRough !== null) r = mix(r, float(decalRough), da);
        }
        mat.colorNode = c;
        mat.roughnessNode = clamp(r, 0.04, 1.0);
        if (peel > 0) mat.normalNode = bumpNormal(triplanar(42 * scale).b.mul(peel));
        if (emissive) mat.emissiveNode = emissive;
        return mat;
    }

    // ── a display behind glass: emissive image under a clear coat, so it reads as a lit screen and still catches
    //    reflections. tex = makeScreen texture (sample flipped) or a canvasTexture (flipV:false). Options:
    //    window [u0,v0,u1,v1] — where the image sits in this mesh's UV (outside: glass only);
    //    parallax (m) — image recessed behind the glass; barrel — CRT pincushion; scan — scanline count;
    //    corner — rounded tube mask radius (fraction of the window); gain — HDR multiplier (bloom).
    function screenMaterial(o) {
        const {
            tex, power, gain = 1.3, glass = '#0b0d0c', rough = 0.32, coat = 1.0, coatRough = 0.035, flipV = true,
            window: win = [0, 0, 1, 1], parallax = 0, faceSize = [1, 1], barrel = 0, scan = 0, scanAmt = 0.3,
            corner = 0, vignette = 0.0, tint = null, bleed = 0, glow = null,
            colorNode = null, roughnessNode = null, coatNode = null, crtOn = false,
        } = o;
        const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: rough, metalness: 0, clearcoat: coat, clearcoatRoughness: coatRough });
        mat.colorNode = colorNode || lin(glass);
        if (roughnessNode) mat.roughnessNode = roughnessNode;
        if (coatNode) mat.clearcoatNode = coatNode;
        mat.emissiveNode = Fn(() => {
            const st = uv().toVar();
            if (parallax > 0) {
                const vW = normalize(cameraPosition.sub(positionWorld));
                const ax = normalize(modelWorldMatrix.mul(vec4(1, 0, 0, 0)).xyz);
                const ay = normalize(modelWorldMatrix.mul(vec4(0, 1, 0, 0)).xyz);
                const az = normalize(modelWorldMatrix.mul(vec4(0, 0, 1, 0)).xyz);
                const vz = max(dot(vW, az), 0.25);
                st.subAssign(vec2(dot(vW, ax).div(vz).mul(parallax / faceSize[0]), dot(vW, ay).div(vz).mul(parallax / faceSize[1])));
            }
            // into window space
            const w = vec2(st.x.sub(win[0]).div(win[2] - win[0]), st.y.sub(win[1]).div(win[3] - win[1])).toVar();
            if (barrel > 0) {
                const cc = w.sub(0.5);
                w.assign(cc.mul(float(1).add(dot(cc, cc).mul(barrel))).add(0.5));
            }
            const wm = w.toVar();                                   // the tube mask never squeezes
            let squeeze = float(1);
            if (crtOn) {   // CRT switch-on: the raster opens from a bright horizontal line as power rises
                squeeze = smoothstep(0.05, 0.7, power).mul(0.99).add(0.01);
                w.assign(vec2(w.x, w.y.sub(0.5).div(squeeze).add(0.5)));
            }
            const s = vec2(w.x, flipV ? float(1).sub(w.y) : w.y);
            const col = texture(tex, s).rgb.toVar();
            if (bleed > 0) {   // horizontal phosphor/chroma bleed: a cheap 3-tap smear
                const dx = float(bleed);
                col.assign(col.mul(0.6).add(texture(tex, s.add(vec2(dx, 0))).rgb.mul(0.2)).add(texture(tex, s.sub(vec2(dx, 0))).rgb.mul(0.2)));
            }
            if (scan > 0) {
                const ph = w.y.mul(scan * Math.PI * 2);
                const fade = clamp(float(1.0).sub(fwidth(w.y.mul(scan)).mul(1.4)), 0, 1);   // no moire when small
                col.mulAssign(float(1).sub(cos(ph).mul(0.5).add(0.5).mul(scanAmt).mul(fade)));
            }
            // inside-the-window mask with rounded corners (the tube's mask), soft edge
            const q = abs(wm.sub(0.5)).mul(2);                      // 0 centre → 1 window edge
            let dist;
            if (corner > 0) {
                const cr = float(corner * 2);
                const k = q.sub(float(1).sub(cr));
                dist = length(max(k, 0)).add(min(max(k.x, k.y), 0)).sub(cr);
            } else dist = max(q.x, q.y).sub(1);
            const inside = float(1).sub(smoothstep(-0.01, 0.003, dist));
            let out = col.mul(inside);
            if (crtOn) {   // outside the opened raster: dark; a collapsed raster burns brighter
                const qy = abs(w.y.sub(0.5)).mul(2);
                out = out.mul(float(1).sub(smoothstep(0.98, 1.0, qy))).mul(float(1).div(squeeze.mul(0.85).add(0.15)).min(3.0));
            }
            if (vignette > 0) out = out.mul(float(1).sub(dot(q, q).mul(vignette * 0.5)));
            if (tint) out = out.mul(lin(tint));
            if (glow) out = out.add(lin(glow).mul(inside).mul(0.02));
            return out.mul(power).mul(gain);
        })();
        return mat;
    }

    // ── small emissive indicator (LED) — a clear-coated dome whose emission is a uniform
    function ledMaterial(color, lensColor = null) {
        const level = uniform(0);
        const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.25, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.05 });
        mat.colorNode = lin(lensColor || color).mul(0.25);
        mat.emissiveNode = lin(color).mul(level).mul(2.2);
        return { mat, level };
    }

    // ── geometry helpers
    const rbox = (w, h, d, r, seg = 3) => {
        const g = new RoundedBoxGeometry(w, h, d, seg, Math.min(r, w / 2 - 1e-5, h / 2 - 1e-5, d / 2 - 1e-5));
        return g;
    };
    const roundedRectShape = (w, h, r, cx = 0, cy = 0, hole = false) => {
        const s = hole ? new THREE.Path() : new THREE.Shape();
        const x0 = cx - w / 2, y0 = cy - h / 2;
        r = Math.min(r, w / 2, h / 2);
        s.moveTo(x0 + r, y0);
        s.lineTo(x0 + w - r, y0); s.quadraticCurveTo(x0 + w, y0, x0 + w, y0 + r);
        s.lineTo(x0 + w, y0 + h - r); s.quadraticCurveTo(x0 + w, y0 + h, x0 + w - r, y0 + h);
        s.lineTo(x0 + r, y0 + h); s.quadraticCurveTo(x0, y0 + h, x0, y0 + h - r);
        s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
        return s;
    };
    // bake a transform into a clone, keep only position/normal/uv, non-indexed (so anything merges)
    const bake = (geo, pos = [0, 0, 0], rot = [0, 0, 0], scl = [1, 1, 1]) => {
        let g = geo.index ? geo.toNonIndexed() : geo.clone();
        for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
        if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
        g.morphAttributes = {};
        g.clearGroups();
        const m = new THREE.Matrix4().compose(new THREE.Vector3(...pos),
            new THREE.Quaternion().setFromEuler(new THREE.Euler(...rot)), new THREE.Vector3(...scl));
        g.applyMatrix4(m);
        return g;
    };
    // weld coincident vertices and recompute smooth normals (ExtrudeGeometry ships faceted normals); drops uv
    const smooth = (geo) => {
        const g = geo.index ? geo.toNonIndexed() : geo.clone();
        for (const k of Object.keys(g.attributes)) if (k !== 'position') g.deleteAttribute(k);
        const m = mergeVertices(g, 1e-6);
        m.computeVertexNormals();
        return m;
    };
    const merge = (list) => {
        const g = mergeGeometries(list, false);
        g.computeBoundingBox(); g.computeBoundingSphere();
        return g;
    };
    // planar UV from a local-space rectangle (x0,y0)-(x1,y1) on the XY plane; used for printed cards/keys
    const planarUV = (geo, x0, y0, x1, y1, axes = 'xy') => {
        const p = geo.attributes.position, uvA = new Float32Array(p.count * 2);
        const gu = axes[0] === 'x' ? (i) => p.getX(i) : axes[0] === 'y' ? (i) => p.getY(i) : (i) => p.getZ(i);
        const gv = axes[1] === 'x' ? (i) => p.getX(i) : axes[1] === 'y' ? (i) => p.getY(i) : (i) => p.getZ(i);
        for (let i = 0; i < p.count; i++) {
            uvA[i * 2] = (gu(i) - x0) / (x1 - x0);
            uvA[i * 2 + 1] = (gv(i) - y0) / (y1 - y0);
        }
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvA, 2));
        return geo;
    };
    // rounded-rectangle outline points (CCW, n per corner) centred at (cx, cy)
    const rrPoints = (w, h, r, n = 6, cx = 0, cy = 0) => {
        r = Math.min(r, w / 2 - 1e-6, h / 2 - 1e-6);
        const pts = [], cs = [[w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, 0.5], [-w / 2 + r, -h / 2 + r, 1], [w / 2 - r, -h / 2 + r, 1.5]];
        for (const [x, y, a0] of cs) for (let i = 0; i <= n; i++) {
            const a = (a0 + 0.5 * i / n) * Math.PI;
            pts.push([cx + x + Math.cos(a) * r, cy + y + Math.sin(a) * r]);
        }
        return pts;
    };
    // skin a surface through closed rings of equal point count (arrays of [x,y,z]); smooth normals; uv: u around, v across
    const loftRings = (rings, { flip = false } = {}) => {
        const n = rings[0].length, pos = [], uvs = [], idx = [];
        rings.forEach((ring, j) => ring.forEach((q, i) => { pos.push(q[0], q[1], q[2]); uvs.push(i / n, j / (rings.length - 1)); }));
        for (let j = 0; j < rings.length - 1; j++) for (let i = 0; i < n; i++) {
            const a = j * n + i, b = j * n + (i + 1) % n, c = (j + 1) * n + (i + 1) % n, d = (j + 1) * n + i;
            if (flip) idx.push(a, c, b, a, d, c); else idx.push(a, b, c, a, c, d);
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
        g.setIndex(idx);
        g.computeVertexNormals();
        return g;
    };
    // a keycap: rounded box whose top face is narrower than its base (sculpted-key taper), y up
    const keycap = (wB, dB, wT, dT, h, r = 0.0012) => {
        const g = rbox(wB, h, dB, r, 2), p = g.attributes.position;
        for (let i = 0; i < p.count; i++) {
            const t = (p.getY(i) + h / 2) / h;
            p.setX(i, p.getX(i) * (1 + (wT / wB - 1) * t));
            p.setZ(i, p.getZ(i) * (1 + (dT / dB - 1) * t));
        }
        g.computeVertexNormals();
        return g;
    };
    // a polyline with rounded corners (quadratic fillets) as a Curve — for bent wire and tubing
    const roundedPolyline = (pts, radius) => {
        const P = pts.map((q) => new THREE.Vector3(...q));
        const path = new THREE.CurvePath();
        let cur = P[0].clone();
        for (let i = 1; i < P.length - 1; i++) {
            const a = P[i - 1], b = P[i], c = P[i + 1];
            const ra = Math.min(radius, a.distanceTo(b) * 0.45), rc = Math.min(radius, b.distanceTo(c) * 0.45);
            const p0 = b.clone().add(a.clone().sub(b).normalize().multiplyScalar(ra));
            const p1 = b.clone().add(c.clone().sub(b).normalize().multiplyScalar(rc));
            if (cur.distanceTo(p0) > 1e-6) path.add(new THREE.LineCurve3(cur.clone(), p0));
            path.add(new THREE.QuadraticBezierCurve3(p0, b.clone(), p1));
            cur = p1;
        }
        path.add(new THREE.LineCurve3(cur.clone(), P[P.length - 1].clone()));
        return path;
    };
    // planar UV only on faces turned toward dir (e.g. [0,0,1] = the front); every other face maps to uv (-0.25,-0.25),
    // which clamps to the canvas corner — keep that corner transparent and the back/bottom stay unprinted
    const planarUVFacing = (geo, x0, y0, x1, y1, axes = 'xy', dir = [0, 0, 1], minDot = 0.35) => {
        planarUV(geo, x0, y0, x1, y1, axes);
        const n = geo.attributes.normal, uvA = geo.attributes.uv;
        for (let i = 0; i < n.count; i += 3) {
            let dsum = 0;
            for (let k = 0; k < 3; k++) dsum += n.getX(i + k) * dir[0] + n.getY(i + k) * dir[1] + n.getZ(i + k) * dir[2];
            if (dsum / 3 < minDot) for (let k = 0; k < 3; k++) uvA.setXY(i + k, -0.25, -0.25);
        }
        uvA.needsUpdate = true;
        return geo;
    };
    const mesh = (geo, mat, name) => { const m = new THREE.Mesh(geo, mat); m.name = name || ''; m.castShadow = true; m.receiveShadow = true; return m; };

    // canvas drawing helpers
    const rr = (ctx, x, y, w, h, r) => {
        r = Math.min(r, w / 2, h / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    };
    const speckle = (ctx, w, h, n, seed, colors, rMax = 1.5, alpha = 0.08) => {
        const r = rng(seed);
        for (let i = 0; i < n; i++) {
            ctx.globalAlpha = alpha * (0.3 + r());
            ctx.fillStyle = colors[Math.floor(r() * colors.length)];
            ctx.beginPath(); ctx.arc(r() * w, r() * h, 0.3 + r() * rMax, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = 1;
    };

    // ── load one of the Blender-built machine GLBs from the library pack (eidoverse/assets/models/voice_machines/<name>.glb)
    async function loadGLB(url) {
        const bytes = await Deno.readFile(url);
        const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        const gltf = await new globalThis.GLTFLoader().parseAsync(buf, '');
        return gltf.scene;
    }
    // glTF material (baked colour / roughness / normal / occlusion maps) → MeshStandardNodeMaterial, same maps
    function bakedMaterial(m, o = {}) {
        const nm = new THREE.MeshStandardNodeMaterial({
            map: m.map || null, normalMap: m.normalMap || null, roughnessMap: m.roughnessMap || null,
            metalnessMap: m.metalnessMap || null, aoMap: m.aoMap || null, aoMapIntensity: o.ao ?? 1.0,
            color: m.color ? m.color.clone() : new THREE.Color(1, 1, 1), roughness: m.roughness ?? 1, metalness: m.metalness ?? 0,
        });
        if (m.normalScale) nm.normalScale.copy(m.normalScale);
        return nm;
    }
    // runtime brushed/plated metal for screws, connector shells and the like
    function metalMaterial(color = '#b8b8bc', rough = 0.32) {
        const mat = new THREE.MeshStandardNodeMaterial({ metalness: 1.0 });
        const n = triplanar(60);
        mat.colorNode = lin(color).mul(n.g.sub(0.5).mul(0.25).add(1));
        mat.roughnessNode = clamp(float(rough).add(n.a.sub(0.5).mul(0.3)), 0.08, 1.0);
        return mat;
    }
    // a surface lit by the machine's voice (behind grilles, cloth, slots): emissive = colour × level
    function glowMaterial(color, base = '#050505') {
        const level = uniform(0);
        const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
        mat.colorNode = lin(base);
        const n = triplanar(25);
        mat.emissiveNode = lin(color).mul(level).mul(n.g.mul(0.5).add(0.75)).mul(2.4);
        return { mat, level };
    }
    // glTF UVs are v-down; the screen material expects v-up like three's own geometry
    function flipUV(geo) {
        const uvA = geo.attributes.uv;
        if (!uvA) return geo;
        for (let i = 0; i < uvA.count; i++) uvA.setY(i, 1 - uvA.getY(i));
        uvA.needsUpdate = true;
        return geo;
    }

    return {
        loadGLB, bakedMaterial, metalMaterial, glowMaterial, flipUV,
        rng, lin, makeCanvas, buildMips, canvasTexture, refreshCanvasTexture, eraScreen, NOISE, triplanar, curvature,
        bumpNormal, plastic, screenMaterial, ledMaterial, rbox, roundedRectShape, bake, merge, planarUV, mesh, rr,
        speckle, uniform, roundedPolyline, smooth, rrPoints, loftRings, keycap, planarUVFacing,
    };
}
// ===== ERA KIT END =====
