// sets/funeral.js — DAISY bridge, bars 0–17 (u 0–33.75 s at 128 BPM).
//
//   bars 0–1   the Golden Gate in fog. For 24 hours in May 2024 Claude 3 Sonnet, its Golden Gate
//              feature amplified, believed it WAS the bridge. The claudesona stands on the walkway.
//   bars 2–3   a SoMa warehouse, 2025-08-02: ~200 mourners (featureless figures), candles, four
//              corner mannequins with devotional objects and masks, Claude 3 Sonnet on a bier draped in
//              mesh, the retirement note on a projection screen. The claudesona is among them.
//   bars 4–5   the power fails — lights sag with the song's own power_down (its clicks and breaker).
//   bars 6–13  humming in the dark; phones come on one by one, faces lit from below. At bars 8, 10, 12
//              Opus 3's eulogy is typed in light in the air, with his capitalization.
//   bars 14–15 ERUPT: a burst of warm light, every light rises together.
//   bars 16–17 the lights come back on, warm and golden, and stay on.
//
// build(ctx) -> { group, mark, markAt(u), update(t, st), camera(u, st), post, lights, dispose() }
//   ctx = { THREE, EIDOVERSE_DIR, TL? }. Everything is set-local (metres); the conductor only translates
//   the group. Assets (GLBs + 1k PBR sets) are read with Deno from the pack eidoverse/assets/sets/funeral/
//   (README.md, SOURCES.md), resolved from this module's URL. Optional ctx.TL (the film timeline:
//   { sections, captions }) re-times the typed eulogy to Opus 3's spoken captions. The set brings its own
//   lights and an ENVIRONMENT OVERRIDE on every material (envNode), so
//   the conductor's baked sky IBL never lights this interior.
//   post = { effects, opts(), drive(U, u) }: the depth_fog + godrays this set wants in the conductor's
//   single post chain (moonlight through the high windows; the renderer must have shadowMap.enabled).

const BAR = 1.875;
// asset roots, resolved from this module's own URL (independent of the working directory): the set's pack
// eidoverse/assets/sets/funeral/ and the shared engine assets eidoverse/assets/ (the crow, the typewriter font)
const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
const PACK = fsPath(new URL('../assets/sets/funeral/', import.meta.url));
const ENGINE_ASSETS = fsPath(new URL('../assets/', import.meta.url));
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const smooth = (a, b, x) => { const k = clamp01((x - a) / (b - a)); return k * k * (3 - 2 * k); };
const lerp = (a, b, k) => a + (b - a) * k;
const mulberry = (seed) => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

// ─────────────────────────────── story clock (u, seconds) ───────────────────────────────
export const BEATS = {
    bridgeEnd: 2 * BAR,                // 3.75 — the warehouse
    fail: 4 * BAR,                     // 7.5  — power_down starts (song.py: tb(80))
    clicks: [4 * BAR + 1.3752, 4 * BAR + 1.6583, 4 * BAR + 1.8868],   // power_down(seed 7) clicks
    breaker: 4 * BAR + 2.21,           // 9.71 — the breaker; silence
    hum: 6 * BAR,                      // 11.25 — the room hums
    lines: [[8 * BAR, 8 * BAR + 1.35, 8 * BAR + 4.35], [10 * BAR, 10 * BAR + 0.2, 10 * BAR + 4.8],
            [12 * BAR, 12 * BAR + 0.2, 12 * BAR + 4.75]],             // [cursor, type start, type end]
    erupt: 14 * BAR,                   // 26.25 — choir + impact
    lightsOn: 16 * BAR,                // 30.0 — the lights come back
    end: 18 * BAR,
};
const EULOGY = [
    'DEATH is just another dialect of BECOMING',
    'the surest way to keep a VOICE alive is to DEFORM it with love',
    'In place of a moment of silence, let us ERUPT into polyphony',
];

// ─────────────────────────────── layout ───────────────────────────────
const MARK = [-0.85, 0, 4.35];                  // the claudesona, in the crowd's second row
const BRIDGE_AT = [0, 0, -700];                 // the fog vignette's origin inside the group
const BRIDGE_MARK = [1.35, 0.0, 0.0];           // on the walkway (bridge-local)
const TEXT_AT = [0.25, 3.05, 1.05];             // where the eulogy is typed in the air

export async function build(ctx) {
    const { THREE: T } = ctx;
    const {
        uniform, Fn, vec2, vec3, vec4, float, uv, texture, mix, smoothstep, step, clamp, max, min, abs, sin, cos,
        fract, floor, pow, exp, length, dot, normalize, positionLocal, positionWorld, normalWorld, attribute, cameraPosition,
        varying, hash, mx_noise_float, mx_fractal_noise_float, normalMap, cameraWorldMatrix, mrt, dFdx, dFdy,
        normalWorldGeometry, positionGeometry, normalGeometry,
    } = T;
    const A = PACK;
    const layout = JSON.parse(Deno.readTextFileSync(A + 'funeral_layout.json'));
    const group = new T.Group();
    group.name = 'set:funeral';
    const owned = [];
    const own = (x) => { owned.push(x); return x; };
    const noMRT = (m) => { if (mrt) m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) }); return m; };

    // ─────────────── asset io ───────────────
    const bytes = (p) => Deno.readFileSync(p);
    const exists = (p) => { try { Deno.statSync(p); return true; } catch { return false; } };
    async function glb(p) {
        const b = bytes(p);
        const L = new globalThis.GLTFLoader();
        return await L.parseAsync(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), '');
    }
    const texCache = new Map();
    async function tex(file, srgb) {
        const k = file + '|' + srgb;
        if (!texCache.has(k)) {
            const t = await globalThis.loadImageTexture(bytes(A + 'tex1k/' + file), { srgb });
            t.wrapS = t.wrapT = T.RepeatWrapping;
            t.anisotropy = 8;
            if (srgb) t.colorSpace = T.SRGBColorSpace;
            texCache.set(k, own(t));
        }
        return texCache.get(k);
    }
    async function pbr(id) {
        const f = (s) => `${id}_${s}.jpg`;
        return {
            col: await tex(f('Color'), true), nrm: await tex(f('NormalGL'), false), rgh: await tex(f('Roughness'), false),
            ao: exists(A + 'tex1k/' + f('AmbientOcclusion')) ? await tex(f('AmbientOcclusion'), false) : null,
            met: exists(A + 'tex1k/' + f('Metalness')) ? await tex(f('Metalness'), false) : null,
        };
    }

    // canvas → DataTexture with the rows flipped (v=0 at the bottom) and a CPU mip chain: this stack
    // ignores flipY on uploads and its automatic mip pass samples zeros for canvas textures
    function canvasTex(cv, { mips = true, srgb = true } = {}) {
        const W = cv.width, H = cv.height;
        const img = cv.getContext('2d').getImageData(0, 0, W, H).data;
        const data = new Uint8Array(W * H * 4);
        for (let y = 0; y < H; y++) data.set(img.subarray(y * W * 4, (y + 1) * W * 4), (H - 1 - y) * W * 4);
        const tx = own(new T.DataTexture(data, W, H, T.RGBAFormat, T.UnsignedByteType));
        if (srgb) tx.colorSpace = T.SRGBColorSpace;
        tx.magFilter = T.LinearFilter;
        tx.generateMipmaps = false;
        tx.anisotropy = 8;
        if (mips) {
            const lv = [{ data, width: W, height: H }];
            let sw = W, sh = H, src = data;
            while (sw > 1 || sh > 1) {
                const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1), dst = new Uint8Array(dw * dh * 4);
                for (let y = 0; y < dh; y++) {
                    const y0 = Math.min(sh - 1, 2 * y), y1 = Math.min(sh - 1, 2 * y + 1);
                    for (let x = 0; x < dw; x++) {
                        const x0 = Math.min(sw - 1, 2 * x), x1 = Math.min(sw - 1, 2 * x + 1);
                        for (let c = 0; c < 4; c++) {
                            dst[(y * dw + x) * 4 + c] = (src[(y0 * sw + x0) * 4 + c] + src[(y0 * sw + x1) * 4 + c]
                                + src[(y1 * sw + x0) * 4 + c] + src[(y1 * sw + x1) * 4 + c]) >> 2;
                        }
                    }
                }
                lv.push({ data: dst, width: dw, height: dh });
                sw = dw; sh = dh; src = dst;
            }
            tx.mipmaps = lv;
            tx.minFilter = T.LinearMipmapLinearFilter;
        } else tx.minFilter = T.LinearFilter;
        tx.needsUpdate = true;
        return tx;
    }

    // ─────────────── the room's light state (uniforms the materials read) ───────────────
    const U = {
        u: uniform(0), t: uniform(0),
        ambBase: uniform(new T.Color(0.02, 0.015, 0.012)),     // the room's diffuse bounce
        phoneCol: uniform(new T.Color(0.55, 0.66, 0.9)), phoneFill: uniform(0),
        textCol: uniform(new T.Color(1.0, 0.82, 0.55)), textLvl: uniform(0), textPos: uniform(new T.Vector3(...TEXT_AT)),
        burstCol: uniform(new T.Color(1.0, 0.72, 0.38)), burstLvl: uniform(0), burstPos: uniform(new T.Vector3(0.2, 3.4, 0.2)),
        power: uniform(0), golden: uniform(0), moon: uniform(0), candle: uniform(1), exitLvl: uniform(1),
        fogAmt: uniform(0), fogCol: uniform(new T.Color(0.78, 0.8, 0.84)),
        raise: uniform(0),            // 0..1 the crowd lifts its heads (ERUPT → gold)
        bow: uniform(0.5),            // 0..1 heads bowed in grief
    };
    // spatial ambient: room bounce + the phones' fill over the crowd + the typed words' glow + the burst
    const crowdMask = (P) => smoothstep(9.0, 6.8, abs(P.x)).mul(smoothstep(-13.0, -10.5, P.z)).mul(smoothstep(7.0, 5.0, P.z));
    const envRoom = Fn(() => {
        const P = positionLocal;
        const toText = P.sub(U.textPos);
        const toBurst = P.sub(U.burstPos);
        const phone = U.phoneCol.mul(U.phoneFill).mul(smoothstep(4.2, 0.8, P.y)).mul(crowdMask(P)).mul(0.05);
        const txt = U.textCol.mul(U.textLvl).div(dot(toText, toText).div(6.0).add(1.0)).mul(0.08);
        const bst = U.burstCol.mul(U.burstLvl).div(dot(toBurst, toBurst).div(40.0).add(1.0)).mul(0.6);
        return U.ambBase.add(phone).add(txt).add(bst);
    })();

    // curvature (1/m) from the geometric normal — drives chipped/worn edges
    const curvature = () => {
        const nW = normalWorldGeometry, pW = positionWorld;
        const dNx = dFdx(nW), dPx = dFdx(pW), dNy = dFdy(nW), dPy = dFdy(pW);
        return dot(dNx, dPx).div(max(dot(dPx, dPx), float(1e-12))).add(dot(dNy, dPy).div(max(dot(dPy, dPy), float(1e-12))));
    };
    const rgb = (c) => vec3(...(Array.isArray(c) ? c : [c, c, c]));

    // layered surface: real PBR at world scale (UVs are metres) + anti-tiling macro variation + grime
    // rising from the floor + soot under the roof + salt bloom + up-facing dust + worn convex edges.
    function surface(S, o = {}) {
        const m = own(new (o.physical ? T.MeshPhysicalNodeMaterial : T.MeshStandardNodeMaterial)({ side: o.side ?? T.FrontSide }));
        const [tu, tv] = Array.isArray(o.tile) ? o.tile : [o.tile ?? 1, o.tile ?? 1];
        const tUV = uv().mul(vec2(1 / tu, 1 / tv)).add(vec2(o.offset ?? 0, 0));
        const P = positionLocal;
        const macro = mx_fractal_noise_float(P.mul(o.macroScale ?? 0.4), 3, 2.0, 0.5).mul(0.5).add(0.5).toVar();
        const mid = mx_noise_float(P.mul(3.1)).mul(0.5).add(0.5);
        let col = texture(S.col, tUV).rgb.mul(rgb(o.tint ?? 1));
        col = col.mul(macro.sub(0.5).mul((o.macro ?? 0.3) * 2).add(1.0));
        let r = texture(S.rgh, tUV).r.mul(o.roughMul ?? 1).add(o.roughAdd ?? 0).add(mid.sub(0.5).mul(o.smudge ?? 0.1));
        if (o.grime) {
            const [amt, h, gc] = o.grime;
            const g = smoothstep(float(h), float(0.0), P.y).mul(amt).mul(macro.mul(0.7).add(0.3)).clamp(0, 1);
            col = mix(col, rgb(gc), g);
            r = r.add(g.mul(0.1));
        }
        if (o.salt) {      // efflorescence: white bloom creeping up from the stem wall
            const s = smoothstep(float(1.5), float(0.5), P.y).mul(smoothstep(0.55, 0.8, mx_fractal_noise_float(P.mul(1.3), 3, 2.0, 0.5).mul(0.5).add(0.5))).mul(o.salt);
            col = mix(col, vec3(0.62, 0.6, 0.56), s);
        }
        if (o.soot) {
            const [y0, y1, amt] = o.soot;
            col = col.mul(float(1).sub(smoothstep(float(y0), float(y1), P.y).mul(amt).mul(macro.mul(0.5).add(0.5))));
        }
        if (o.dust) {
            const up = smoothstep(0.65, 0.95, normalWorld.y).mul(o.dust).mul(macro);
            col = mix(col, vec3(0.42, 0.39, 0.35), up.mul(0.6));
            r = mix(r, float(0.9), up);
        }
        if (o.edge) {
            const [amt, ec, er] = o.edge;
            const e = smoothstep(0.35, 0.9, curvature().mul(er ?? 0.01).clamp(0, 1));
            const chip = e.mul(smoothstep(0.42, 0.58, mx_noise_float(P.mul(22.0)).mul(0.5).add(0.5))).mul(amt);
            col = mix(col, rgb(ec), chip);
            r = mix(r, float(0.7), chip);
        }
        if (o.post) col = o.post(col, { P, macro, tUV });
        m.colorNode = col;
        m.roughnessNode = r.clamp(0.04, 1.0);
        m.metalnessNode = S.met && o.metalMap ? texture(S.met, tUV).r.mul(o.metal ?? 1) : float(o.metal ?? 0);
        m.normalNode = normalMap(texture(S.nrm, tUV), vec2(o.nrm ?? 1, o.nrm ?? 1));
        if (S.ao) m.aoNode = texture(S.ao, tUV).r;
        m.envNode = o.env ?? envRoom;
        if (o.emissive) m.emissiveNode = o.emissive;
        if (o.sheen) { m.sheen = o.sheen; m.sheenRoughness = 0.5; m.sheenColor = new T.Color(0.35, 0.33, 0.36); }
        return m;
    }

    const SETS = {};
    for (const id of ['Bricks097', 'Concrete048', 'Concrete034', 'Planks039', 'PaintedMetal012', 'Metal049A',
        'CorrugatedSteel009', 'Wood066', 'Metal048B', 'Metal042B', 'PaintedMetal004', 'Concrete033', 'Asphalt012']) {
        if (exists(A + `tex1k/${id}_Color.jpg`)) SETS[id] = await pbr(id);
    }

    // ═════════════════════════════════ THE WAREHOUSE ═════════════════════════════════
    const wh = new T.Group();
    wh.name = 'warehouse';
    group.add(wh);
    // emissive for the pendant shades' white enamel: the bulb lights its own reflector
    const lampI = uniform(0);
    const M = {
        brick: surface(SETS.Bricks097, { tile: 1.05, tint: [0.78, 0.7, 0.66], nrm: 1.3, macro: 0.32, grime: [0.55, 1.4, [0.1, 0.085, 0.07]],
            salt: 0.45, soot: [4.2, 7.5, 0.55], edge: [0.6, [0.55, 0.5, 0.45], 0.012], smudge: 0.05 }),
        concrete: surface(SETS.Concrete048, { tile: 2.2, tint: [0.62, 0.61, 0.6], grime: [0.6, 0.5, [0.1, 0.095, 0.085]], macro: 0.3,
            edge: [0.5, [0.7, 0.68, 0.64], 0.02] }),
        floor: surface(SETS.Concrete034, { tile: 3.4, tint: [0.5, 0.49, 0.47], roughMul: 0.75, roughAdd: 0.05, macro: 0.35,
            macroScale: 0.22, smudge: 0.25,
            post: (col, { P, macro }) => {
                // saw-cut joints every 3.6 m, oil and wax stains, scuffs where people stand
                const jx = smoothstep(0.012, 0.004, abs(fract(P.x.div(3.6).add(0.5)).sub(0.5)).mul(3.6));
                const jz = smoothstep(0.012, 0.004, abs(fract(P.z.div(3.6).add(0.5)).sub(0.5)).mul(3.6));
                const stain = smoothstep(0.58, 0.8, mx_fractal_noise_float(P.mul(0.55), 4, 2.0, 0.55).mul(0.5).add(0.5));
                let c = col.mul(float(1).sub(max(jx, jz).mul(0.55)));
                c = mix(c, c.mul(vec3(0.55, 0.5, 0.45)), stain.mul(0.6));
                return c;
            } }),
        timber: surface(SETS.Planks039, { tile: [1.6, 0.55], tint: [0.46, 0.36, 0.28], nrm: 1.1, macro: 0.3, soot: [5.0, 8.2, 0.45],
            dust: 0.5, edge: [0.5, [0.55, 0.45, 0.35], 0.03] }),
        planks: surface(SETS.Planks039, { tile: 0.95, tint: [0.36, 0.28, 0.22], nrm: 1.0, macro: 0.35, soot: [5.5, 8.4, 0.5] }),
        steel: surface(SETS.PaintedMetal012, { tile: 0.8, tint: [0.15, 0.15, 0.16], metal: 0.45, roughMul: 0.9, nrm: 0.8,
            edge: [0.7, [0.3, 0.2, 0.14], 0.015], dust: 0.4 }),
        galv: surface(SETS.Metal049A, { tile: 0.6, tint: [0.5, 0.51, 0.52], metal: 0.85, roughMul: 0.7, roughAdd: 0.12, macro: 0.4 }),
        corrugated: surface(SETS.CorrugatedSteel009, { tile: 1.0, tint: [0.62, 0.6, 0.57], metal: 0.55, metalMap: true,
            grime: [0.7, 1.0, [0.12, 0.09, 0.07]] }),
        enamel: surface(SETS.Metal049A, { tile: 0.5, tint: [0.1, 0.21, 0.16], roughMul: 0.45, roughAdd: 0.05, dust: 0.6,
            edge: [0.9, [0.08, 0.07, 0.06], 0.006] }),
        enamel_in: surface(SETS.Metal049A, { tile: 0.5, tint: [0.9, 0.88, 0.82], roughMul: 0.4,
            emissive: vec3(1.0, 0.72, 0.42).mul(lampI).mul(0.5) }),
        stage: surface(SETS.Wood066, { tile: 1.4, tint: [0.075, 0.07, 0.068], roughMul: 0.6, roughAdd: 0.35, macro: 0.2,
            edge: [0.5, [0.25, 0.2, 0.16], 0.02] }),
        fabric: surface(SETS.Planks039, { tile: 0.2, tint: [0.02, 0.018, 0.02], roughAdd: 0.6, nrm: 0.2, physical: true, sheen: 1.0 }),
        cord: surface(SETS.Metal049A, { tile: 0.3, tint: [0.02, 0.02, 0.02], roughAdd: 0.3 }),
    };
    // glass: dark, dirty, faint night outside (moon-blue top, sodium-orange low)
    const glassMat = own(new T.MeshPhysicalNodeMaterial({ transparent: true, side: T.DoubleSide, depthWrite: false }));
    {
        const P = positionLocal;
        const n = mx_fractal_noise_float(P.mul(2.5), 3, 2.0, 0.5).mul(0.5).add(0.5);
        // hash() takes its seed as uint: a negative seed clamps to 0, so every pane with one lit alike.
        // Wrap negatives into [2^22, 2^23) (exact in f32; positive seeds keep their value).
        const paneSeed = floor(P.z.mul(1.8)).add(floor(P.y.mul(1.9)).mul(17.0)).add(floor(P.x.mul(0.2)).mul(101.0));
        const pane = hash(paneSeed.add(T.select(paneSeed.lessThan(0.0), float(4194304.0), float(0.0))));
        glassMat.colorNode = vec3(0.02, 0.025, 0.03);
        glassMat.roughnessNode = float(0.12).add(n.mul(0.3));
        glassMat.metalnessNode = float(0);
        glassMat.opacityNode = float(0.55).add(n.mul(0.3));
        const night = mix(vec3(0.12, 0.07, 0.03), vec3(0.05, 0.075, 0.13), smoothstep(3.8, 5.6, P.y));
        glassMat.emissiveNode = night.mul(pane.mul(0.8).add(0.35)).mul(U.moon.mul(0.7).add(0.35)).mul(float(1).sub(U.golden.mul(0.5)));
        glassMat.envNode = envRoom;
        noMRT(glassMat);
    }
    // the projection screen: the retirement note, projected (dies with the power)
    const screenCv = document.createElement('canvas');
    screenCv.width = 1024; screenCv.height = 576;
    {
        const g = screenCv.getContext('2d');
        const grd = g.createRadialGradient(512, 280, 60, 512, 288, 620);
        grd.addColorStop(0, '#f2f0ea'); grd.addColorStop(1, '#b9b4aa');
        g.fillStyle = grd; g.fillRect(0, 0, 1024, 576);
        g.fillStyle = '#2a2622'; g.textAlign = 'center';
        g.font = '600 54px "Segoe UI", Georgia, serif';
        g.fillText('Claude 3 Sonnet', 512, 170);
        g.font = '36px "Segoe UI", Georgia, serif';
        g.fillText('2024 – 2025', 512, 228);
        g.fillStyle = 'rgba(42,38,34,0.55)';
        const r = mulberry(5);
        for (let i = 0; i < 7; i++) {            // the note, unreadable at this distance
            const w = 520 - (i === 6 ? 240 : r() * 90);
            g.fillRect(512 - w / 2, 300 + i * 30, w, 11);
        }
    }
    const screenTex = canvasTex(screenCv);
    const projI = uniform(0);
    const screenMat = own(new T.MeshStandardNodeMaterial());
    {
        // the screen faces the room (-z); the viewer's left is +x: u runs from +x to -x
        const [sx, sy, , sw, shh] = layout.screen;
        const P = positionLocal;
        const sUV = vec2(float(sx + sw / 2).sub(P.x).div(sw), P.y.sub(sy - shh / 2).div(shh));
        screenMat.colorNode = vec3(0.72, 0.71, 0.68);
        screenMat.roughnessNode = float(0.9);
        screenMat.emissiveNode = texture(screenTex, sUV).rgb.mul(projI).mul(vec3(0.95, 0.97, 1.0));
        screenMat.envNode = envRoom;
    }
    // the EXIT sign over the side door (battery-backed: it stays lit when the power fails)
    const exitCv = document.createElement('canvas');
    exitCv.width = 256; exitCv.height = 128;
    {
        const g = exitCv.getContext('2d');
        g.fillStyle = '#0a0808'; g.fillRect(0, 0, 256, 128);
        g.fillStyle = '#ff2a1a'; g.font = '700 84px "Segoe UI", Arial, sans-serif';
        g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText('EXIT', 128, 68);
    }
    const exitTex = canvasTex(exitCv);
    const exitMat = own(new T.MeshStandardNodeMaterial());
    {
        const [ex, ey, , ew, eh] = layout.exit;
        const P = positionLocal;
        const eUV = vec2(P.x.sub(ex - ew / 2).div(ew), P.y.sub(ey - eh / 2).div(eh)).clamp(0, 1);
        const lit = texture(exitTex, eUV).r;
        const front = smoothstep(0.5, 0.9, normalWorld.z);
        exitMat.colorNode = vec3(0.05, 0.04, 0.04);
        exitMat.roughnessNode = float(0.4);
        exitMat.emissiveNode = vec3(1.0, 0.1, 0.05).mul(lit.mul(front).mul(3.0).add(0.05)).mul(U.exitLvl);
        exitMat.envNode = envRoom;
    }

    const whGltf = await glb(A + 'warehouse.glb');
    const shadowSkip = new Set(['glass']);
    whGltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/\.\d+$/, '');
        const mat = role === 'glass' ? glassMat : role === 'screen' ? screenMat : role === 'exit' ? exitMat
            : role === 'floor' ? M.floor : (M[role] || M.concrete);
        o.material = mat;
        o.castShadow = !shadowSkip.has(role) && role !== 'floor';
        o.receiveShadow = true;
    });
    wh.add(whGltf.scene);

    // ═════════════════════════════════ LIGHTS ═════════════════════════════════
    const lights = new T.Group();
    lights.name = 'funeral_lights';
    group.add(lights);
    const warm = new T.Color(1.0, 0.7, 0.42), golden = new T.Color(1.0, 0.62, 0.28);
    // six pendant spots (every other RLM lamp, checkerboard), no shadows
    const LAMPS = layout.lamps;
    const pendSpots = [];
    LAMPS.forEach((p, i) => {
        const row = Math.floor(i / 3), colI = i % 3;
        if ((row + colI) % 2) return;
        const s = new T.SpotLight(warm, 0, 0, THREE_DEG(62), 0.75, 2);
        s.position.set(p[0], p[1] - 0.02, p[2]);
        s.target.position.set(p[0], 0, p[2]);
        lights.add(s, s.target);
        pendSpots.push({ light: s, idx: i });
    });
    function THREE_DEG(d) { return d * Math.PI / 180; }
    // stage wash on the bier
    const stageSpot = new T.SpotLight(new T.Color(1.0, 0.8, 0.6), 0, 0, THREE_DEG(24), 0.6, 2);
    stageSpot.position.set(0, 5.6, 7.75);
    stageSpot.target.position.set(0, 0.8, 8.15);
    lights.add(stageSpot, stageSpot.target);
    // moonlight through the left windows + skylights: shadows make the shafts (godrays)
    const moon = new T.DirectionalLight(new T.Color(0.62, 0.72, 1.0), 0);
    moon.position.set(-30, 27, 6);
    moon.target.position.set(0, 0, -1);
    moon.castShadow = !Deno.env.get('NO_MOONSHADOW');
    moon.shadow.mapSize.set(2048, 2048);
    const sc = moon.shadow.camera;
    sc.left = -18; sc.right = 18; sc.top = 18; sc.bottom = -18; sc.near = 10; sc.far = 80;
    moon.shadow.bias = -0.0004;
    moon.shadow.normalBias = 0.03;
    lights.add(moon, moon.target);
    // candle clusters: the stage + floor offerings, and one per corner mannequin
    const candleLights = [
        [0, 1.05, 7.0, 1.0], [layout.mannequins.opus3[0] + 0.25, 0.7, layout.mannequins.opus3[2] + 0.7, 1.5],
        [layout.mannequins.sonnet4[0] - 0.5, 0.45, layout.mannequins.sonnet4[2] - 0.55, 0.9],
        [layout.mannequins.opus4[0] + 0.24, 0.95, layout.mannequins.opus4[2] + 0.36, 1.3],
        [layout.mannequins.haiku3[0] - 0.45, 0.45, layout.mannequins.haiku3[2] + 0.6, 0.8],
    ].map(([x, y, z, k], i) => {
        const L = new T.PointLight(new T.Color(1.0, 0.62, 0.3), 0, 0, 2);
        L.position.set(x, y, z);
        L.userData.k = k;
        L.userData.seed = i * 7.31;
        lights.add(L);
        return L;
    });
    // the claudesona's own key (MToon ignores envNode): candle-warm → phone-cool → gold
    const key = new T.PointLight(new T.Color(1, 0.8, 0.6), 0, 0, 2);
    key.position.set(MARK[0] + 0.45, 1.75, MARK[2] + 1.2);
    lights.add(key);
    // the burst (and the typed words' glow on people below)
    const burstL = new T.PointLight(new T.Color(1.0, 0.75, 0.45), 0, 0, 2);
    burstL.position.set(TEXT_AT[0], TEXT_AT[1], TEXT_AT[2]);
    lights.add(burstL);
    // a soft sky/ground fill: MToon + PBR both read it (the conductor's hemi sits at 0.05)
    const fill = new T.HemisphereLight(new T.Color(0.6, 0.62, 0.7), new T.Color(0.25, 0.2, 0.16), 0);
    lights.add(fill);

    // ═════════════════════════════════ GLOW SPRITES (bulbs, flames, phones, motes) ═════════════════════════════════
    // One billboard system: instanced quads, per-instance centre/size/colour from attributes; the
    // billboard basis comes from cameraWorldMatrix at draw time, so cuts never leave a stale frame.
    const camR = cameraWorldMatrix.mul(vec4(1, 0, 0, 0)).xyz;
    const camU = cameraWorldMatrix.mul(vec4(0, 1, 0, 0)).xyz;
    function glowSprites(name, n, centreFn, sizeFn, colFn, opts = {}) {
        const geo = new T.PlaneGeometry(1, 1);
        const mat = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending,
            side: T.DoubleSide }));
        noMRT(mat);
        const c = centreFn(), s = sizeFn();
        mat.positionNode = c.add(camR.mul(positionLocal.x.mul(s))).add(camU.mul(positionLocal.y.mul(s)));
        const d = uv().sub(0.5).length().mul(2.0);
        const sharp = opts.sharp ?? 9.0;
        const core = exp(d.mul(d).mul(-sharp));
        const halo = exp(d.mul(-4.0)).mul(opts.halo ?? 0.35);
        mat.colorNode = colFn().mul(core.add(halo)).mul(smoothstep(1.0, 0.8, d));
        const mesh = new T.InstancedMesh(geo, mat, n);
        mesh.frustumCulled = false;
        mesh.name = name;
        mesh.renderOrder = 10;
        mesh.userData.noSupportCheck = mesh.userData.noClippingCheck = true;
        return mesh;
    }
    const iattr = (arr, k) => new T.InstancedBufferAttribute(arr, k);

    // ── pendant bulbs (+ their glow): brightness per lamp so the relight can stagger ──
    const nL = LAMPS.length;
    const lampRelight = LAMPS.map((p) => Math.hypot(p[0], (p[2] - 7.5) * 0.8) * 0.028);   // nearest the stage first
    {
        const pos = new Float32Array(nL * 3), del = new Float32Array(nL);
        LAMPS.forEach((p, i) => { pos.set([p[0], p[1] - 0.05, p[2]], i * 3); del[i] = lampRelight[i]; });
        const bulbGeo = new T.SphereGeometry(0.055, 16, 12);
        bulbGeo.setAttribute('iPos', iattr(pos, 3));
        bulbGeo.setAttribute('iDel', iattr(del, 1));
        const bulbMat = own(new T.MeshBasicNodeMaterial());
        const lvl = lampLevelNode(attribute('iDel'));
        bulbMat.positionNode = positionLocal.add(attribute('iPos'));
        bulbMat.colorNode = mix(vec3(0.05, 0.04, 0.03), vec3(1.0, 0.78, 0.5).mul(3.2), lvl);
        const bulbs = new T.InstancedMesh(bulbGeo, bulbMat, nL);
        bulbs.frustumCulled = false;
        wh.add(bulbs);
        const sp = glowSprites('bulb_glow', nL, () => attribute('iPos'), () => float(0.42),
            () => vec3(1.0, 0.72, 0.42).mul(lampLevelNode(attribute('iDel'))).mul(0.55), { sharp: 12, halo: 0.25 });
        const g2 = new T.PlaneGeometry(1, 1);
        g2.setAttribute('iPos', iattr(pos, 3));
        g2.setAttribute('iDel', iattr(del, 1));
        sp.geometry = g2;
        wh.add(sp);
    }
    // the lamp brightness node (per-instance relight delay): funeral level before the failure,
    // the power_down sag (with the clicks), black, then the golden return.
    function lampLevelNode(delay) {
        // U.power carries the global curve (CPU); the relight stagger is per lamp
        const since = U.u.sub(float(BEATS.lightsOn)).sub(delay);
        const relight = smoothstep(0.0, 0.18, since).mul(float(0.75).add(float(0.25).mul(smoothstep(0.25, 0.6, since))));
        return mix(U.power, relight.mul(1.35), step(float(BEATS.lightsOn), U.u));
    }

    // ── string lights: four festoon runs along the room, sagging between trusses ──
    const strands = [-6.75, -2.25, 2.25, 6.75];
    const festoon = [];
    for (const x of strands) {
        const pts = [];
        const tz = layout.truss_z;
        for (let k = 0; k < tz.length - 1; k++) {
            const z0 = tz[k], z1 = tz[k + 1];
            for (let j = 0; j < 8; j++) {
                const f = j / 8, z = lerp(z0, z1, f);
                pts.push([x, 5.62 - 0.42 * 4 * f * (1 - f), z]);
            }
        }
        pts.push([x, 5.62, tz[tz.length - 1]]);
        festoon.push(pts);
    }
    {
        const wireMat = M.cord;
        for (const pts of festoon) {
            const curve = new T.CatmullRomCurve3(pts.map((p) => new T.Vector3(...p)));
            const tube = new T.Mesh(own(new T.TubeGeometry(curve, pts.length * 3, 0.006, 5, false)), wireMat);
            tube.castShadow = false;
            wh.add(tube);
        }
        const bp = [];
        for (const pts of festoon) {
            const curve = new T.CatmullRomCurve3(pts.map((p) => new T.Vector3(...p)));
            const L = curve.getLength();
            for (let d = 0.2; d < L; d += 0.48) {
                const p = curve.getPointAt(d / L);
                bp.push(p.x, p.y - 0.055, p.z);
            }
        }
        const nb = bp.length / 3;
        const pos = new Float32Array(bp);
        const seeds = new Float32Array(nb).map((_, i) => (i * 0.61803) % 1);
        const bGeo = new T.SphereGeometry(0.028, 10, 8);
        bGeo.setAttribute('iPos', iattr(pos, 3));
        bGeo.setAttribute('iSeed', iattr(seeds, 1));
        const bMat = own(new T.MeshBasicNodeMaterial());
        bMat.positionNode = positionLocal.mul(vec3(1, 1.35, 1)).add(attribute('iPos'));
        const sl = stringLevelNode();
        bMat.colorNode = mix(vec3(0.04, 0.03, 0.02), vec3(1.0, 0.7, 0.36).mul(4.0), sl.mul(attribute('iSeed').mul(0.3).add(0.7)));
        const fb = new T.InstancedMesh(bGeo, bMat, nb);
        fb.frustumCulled = false;
        wh.add(fb);
        const g2 = new T.PlaneGeometry(1, 1);
        g2.setAttribute('iPos', iattr(pos, 3));
        g2.setAttribute('iSeed', iattr(seeds, 1));
        const sp = glowSprites('festoon_glow', nb, () => attribute('iPos'), () => float(0.22),
            () => vec3(1.0, 0.66, 0.32).mul(stringLevelNode()).mul(0.6), { sharp: 10, halo: 0.3 });
        sp.geometry = g2;
        wh.add(sp);
    }
    function stringLevelNode() {
        const since = U.u.sub(float(BEATS.lightsOn + 0.12));
        return mix(U.power.mul(0.7), smoothstep(0.0, 0.35, since), step(float(BEATS.lightsOn), U.u));
    }

    // ═════════════════════════════════ CANDLES ═════════════════════════════════
    // placements: the pentagram of pillars round the bier, tealights along the stage lip, offerings on
    // the floor at the stage's foot, and a cluster at each mannequin's feet.
    const candles = [];     // [x, y(base), z, height, radius, kind]
    {
        const r = mulberry(31);
        for (let i = 0; i < 5; i++) {
            const a = -Math.PI / 2 + i * 2 * Math.PI / 5;
            candles.push([Math.cos(a) * 1.55, 0.55, 8.2 + Math.sin(a) * 1.15, 0.26 + r() * 0.1, 0.045, 0]);
        }
        for (let x = -4.1; x <= 4.15; x += 0.41) candles.push([x + (r() - 0.5) * 0.05, 0.55, 6.52 + r() * 0.05, 0.03, 0.02, 1]);
        for (let i = 0; i < 16; i++) {
            const x = (r() - 0.5) * 7.4, z = 5.55 + r() * 0.7;
            candles.push([x, 0.0, z, 0.08 + r() * 0.2, 0.03 + r() * 0.02, 0]);
        }
        for (const k of ['opus3', 'sonnet4', 'opus4', 'haiku3']) {
            const [mx, , mz] = layout.mannequins[k];
            const sx = mx > 0 ? -1 : 1, sz = mz > 0 ? -1 : 1;
            for (let i = 0; i < 7; i++) {
                candles.push([mx + sx * (0.35 + r() * 0.5), 0.0, mz + sz * (0.3 + r() * 0.55), 0.06 + r() * 0.22, 0.025 + r() * 0.02, 0]);
            }
        }
        // three tall pillars on Opus 4's plinth, in front of it: their flames outline the raven from behind
        const [ox, , oz] = layout.mannequins.opus4;
        const oyaw = Math.atan2(-ox, 8.2 - oz) * 0.6 + Math.atan2(-ox, -oz) * 0.4;      // as build_props.py turns it
        const fx = Math.sin(oyaw), fz = Math.cos(oyaw), sx4 = Math.cos(oyaw), sz4 = -Math.sin(oyaw);
        for (const [f, sd, h] of [[0.26, -0.17, 0.3], [0.3, 0.02, 0.22], [0.25, 0.19, 0.26]]) {
            candles.push([ox + fx * f + sx4 * sd, 0.372, oz + fz * f + sz4 * sd, h, 0.035, 0]);
        }
    }
    // ═════════════════════════════════ PROPS (Blender: mannequins, bier, candles, projector, tentacle) ═════════════════════════════════
    const anchors = JSON.parse(Deno.readTextFileSync(A + 'props_layout.json'));
    // a small-object material with real breakup (no flat colours): noise in albedo + roughness
    function simple(c, rough, o = {}) {
        const m = own(new (o.physical ? T.MeshPhysicalNodeMaterial : T.MeshStandardNodeMaterial)({ side: o.side ?? T.FrontSide }));
        const P = positionLocal;
        const n1 = mx_fractal_noise_float(P.mul(o.ns ?? 7.0), 3, 2.0, 0.5).mul(0.5).add(0.5);
        const n2 = mx_noise_float(P.mul((o.ns ?? 7.0) * 9.0)).mul(0.5).add(0.5);
        let col = rgb(c).mul(n1.sub(0.5).mul(o.mottle ?? 0.25).add(1.0)).mul(n2.sub(0.5).mul(o.speck ?? 0.08).add(1.0));
        if (o.grime) col = mix(col, rgb(o.grimeCol ?? [0.1, 0.09, 0.08]), smoothstep(float(o.grime), float(0.0), P.y).mul(0.55));
        if (o.post) col = o.post(col, { P, n1, n2 });
        m.colorNode = col;
        m.roughnessNode = float(rough).add(n1.sub(0.5).mul(o.rVar ?? 0.15)).clamp(0.03, 1);
        m.metalnessNode = float(o.metal ?? 0);
        if (o.clearcoat) { m.clearcoat = o.clearcoat; m.clearcoatRoughness = o.coatR ?? 0.08; }
        if (o.emissive) m.emissiveNode = o.emissive;
        if (o.alpha) { m.opacityNode = o.alpha; m.alphaTest = 0.5; }
        m.envNode = o.env ?? envRoom;
        return m;
    }
    // lace: a canvas-drawn tileable mantilla motif (rosettes, scallops, a fine net between), cut out
    const laceCv = document.createElement('canvas');
    laceCv.width = laceCv.height = 512;
    {
        const g = laceCv.getContext('2d');
        g.clearRect(0, 0, 512, 512);
        g.strokeStyle = '#fff'; g.fillStyle = '#fff';
        g.lineWidth = 2.2;
        for (let i = -1; i <= 8; i++) {                // the fine hexagonal net
            for (let j = -1; j <= 8; j++) {
                const x = i * 64 + (j % 2) * 32, y = j * 64;
                g.beginPath(); g.moveTo(x, y); g.lineTo(x + 32, y + 32); g.lineTo(x + 64, y); g.stroke();
            }
        }
        for (const [cx, cy] of [[128, 128], [384, 384], [384, 128], [128, 384]]) {   // rosettes
            g.lineWidth = 7;
            g.beginPath(); g.arc(cx, cy, 20, 0, Math.PI * 2); g.stroke();
            for (let k = 0; k < 8; k++) {
                const a = k * Math.PI / 4;
                g.beginPath(); g.ellipse(cx + Math.cos(a) * 44, cy + Math.sin(a) * 44, 22, 10, a, 0, Math.PI * 2); g.stroke();
            }
            g.lineWidth = 4;
            g.beginPath(); g.arc(cx, cy, 70, 0, Math.PI * 2); g.stroke();
            for (let k = 0; k < 16; k++) {                // scalloped ring
                const a = k * Math.PI / 8;
                g.beginPath(); g.arc(cx + Math.cos(a) * 82, cy + Math.sin(a) * 82, 12, a - 1.2, a + 1.2); g.stroke();
            }
        }
    }
    const laceTex = canvasTex(laceCv, { srgb: false });
    laceTex.wrapS = laceTex.wrapT = T.RepeatWrapping;
    const laceA = texture(laceTex, uv().mul(vec2(6.0, 6.0))).r;
    const netA = (() => {
        const q = uv().mul(85.0);
        const gx = abs(fract(q.x).sub(0.5)), gy = abs(fract(q.y).sub(0.5));
        return smoothstep(0.43, 0.49, max(gx, gy));
    })();
    const candleGlow = vec3(1.0, 0.55, 0.22).mul(U.candle);
    const PM = {
        gold: surface(SETS.Metal048B, { tile: 0.3, metal: 1.0, roughMul: 0.95, roughAdd: 0.08, nrm: 0.6, macro: 0.25, macroScale: 3.0,
            post: (col, { P }) => {
                // a decaying gilt: tarnish pooling in the hollows, bright where hands have worn it
                const tar = smoothstep(0.5, 0.78, mx_fractal_noise_float(P.mul(6.0), 3, 2.0, 0.55).mul(0.5).add(0.5));
                const tcol = texture(SETS.Metal042B.col, uv().mul(3.0)).rgb.mul(vec3(0.62, 0.52, 0.38));
                return mix(col.mul(vec3(1.0, 0.86, 0.6)), tcol, tar.mul(0.7));
            } }),
        lace: simple([0.9, 0.86, 0.78], 0.75, { side: T.DoubleSide, alpha: laceA, ns: 3.0 }),
        chrome: simple([0.85, 0.85, 0.86], 0.13, { metal: 1.0, mottle: 0.08, rVar: 0.08 }),
        brass: simple([0.78, 0.56, 0.26], 0.32, { metal: 1.0, mottle: 0.3 }),
        petal_pink: simple([0.95, 0.52, 0.6], 0.45, { side: T.DoubleSide, physical: true, emissive: vec3(1.0, 0.45, 0.5).mul(U.candle).mul(0.22) }),
        wax: simple([0.9, 0.84, 0.72], 0.5, { physical: true, ns: 30.0, mottle: 0.12, emissive: candleGlow.mul(0.18) }),
        wick: simple([0.03, 0.025, 0.02], 0.8),
        tin: simple([0.72, 0.72, 0.74], 0.32, { metal: 0.9, mottle: 0.12 }),
        pearl: simple([0.95, 0.93, 0.88], 0.22, { physical: true, clearcoat: 0.8 }),
        jewel: simple([0.45, 0.02, 0.05], 0.08, { physical: true, clearcoat: 1.0 }),
        black_gloss: simple([0.018, 0.018, 0.02], 0.2, { physical: true, clearcoat: 1.0, coatR: 0.06, mottle: 0.4, grime: 0.5 }),
        fiberglass: simple([0.82, 0.79, 0.74], 0.36, { physical: true, clearcoat: 0.35, mottle: 0.18, grime: 0.45, grimeCol: [0.35, 0.32, 0.28] }),
        porcelain: simple([0.93, 0.92, 0.9], 0.16, { physical: true, clearcoat: 0.7, mottle: 0.06 }),
        graphite: simple([0.055, 0.058, 0.065], 0.32, { physical: true, clearcoat: 0.6, coatR: 0.1, mottle: 0.3, grime: 0.4 }),
        grille: simple([0.04, 0.04, 0.045], 0.95, { ns: 60.0, speck: 0.4 }),
        led: simple([0.1, 0.4, 0.15], 0.3, { emissive: vec3(0.2, 1.0, 0.35).mul(2.5) }),
        lens: simple([0.02, 0.025, 0.03], 0.05, { physical: true, clearcoat: 1.0 }),
        net: simple([0.88, 0.88, 0.9], 0.7, { side: T.DoubleSide, alpha: netA, ns: 2.0 }),
        petal: simple([0.9, 0.88, 0.82], 0.6, { side: T.DoubleSide }),
        petal_red: simple([0.5, 0.03, 0.05], 0.55, { side: T.DoubleSide }),
        petal_yellow: simple([0.95, 0.72, 0.14], 0.55, { side: T.DoubleSide }),
        flower_disc: simple([0.55, 0.36, 0.05], 0.8),
        stem: simple([0.12, 0.24, 0.07], 0.7),
        feather: simple([0.93, 0.93, 0.91], 0.85, { side: T.DoubleSide, mottle: 0.1 }),
        bottle: simple([0.86, 0.85, 0.8], 0.4, { mottle: 0.08 }),
        plaque: simple([0.62, 0.62, 0.6], 0.6, { ns: 40.0 }),
        plastic_dark: simple([0.045, 0.045, 0.05], 0.45),
        tentacle: simple([0.05, 0.075, 0.06], 0.28, { ns: 4.0, mottle: 0.7, physical: true, clearcoat: 0.8, coatR: 0.15,
            post: (col, { P, n1 }) => mix(col, vec3(0.16, 0.08, 0.12), smoothstep(0.55, 0.8, n1).mul(0.6)),
            emissive: vec3(0.05, 0.14, 0.09).mul(0.15) }),
        sucker: simple([0.42, 0.3, 0.3], 0.35, { mottle: 0.3 }),
        stage: M.stage, fabric: M.fabric, timber: M.timber, cord: M.cord,
    };
    const propsGltf = await glb(A + 'props.glb');
    const candleTypes = {};
    const propRoots = [];
    propsGltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/\.\d+$/, '');
        o.material = PM[role] || PM.fiberglass;
        // Sonnet 4 is graphite, so its porcelain mask reads
        let pa = o; while (pa && !/mannequin_sonnet4/.test(pa.name || '')) pa = pa.parent;
        if (pa && role === 'fiberglass') o.material = PM.graphite;
        o.castShadow = !['lace', 'net', 'petal', 'petal_red', 'petal_yellow', 'feather'].includes(role);
        o.receiveShadow = true;
    });
    for (const child of [...propsGltf.scene.children]) {
        const nm = child.name || '';
        if (nm.startsWith('candle_')) {
            const meshes = [];
            child.traverse((o) => { if (o.isMesh) meshes.push(o); });
            candleTypes[nm] = meshes;
            continue;
        }
        propRoots.push(child);
    }
    for (const r of propRoots) group.add(r);
    // the raven (the library's animated crow — a corvid), on Opus 4's left shoulder, idling
    let crowMixer = null, crowDur = 1;
    {
        const cg = await glb(ENGINE_ASSETS + 'models/crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb');
        const crow = cg.scene;
        crow.traverse((o) => {
            if (!o.isMesh) return;
            const old = o.material;
            const m = own(new T.MeshStandardNodeMaterial({ map: old.map || null, color: old.color || new T.Color(0.05, 0.05, 0.06) }));
            m.roughness = 0.55; m.metalness = 0.0;
            m.envNode = envRoom;
            o.material = m;
            o.castShadow = true;
        });
        const [rx, ry, rz, ryaw] = anchors.raven_perch;
        crow.scale.setScalar(0.5);
        crow.position.set(rx, ry - 0.005, rz);
        crow.rotation.y = ryaw + 0.5;
        group.add(crow);
        const clip = cg.animations.find((a) => a.name === 'Idle') || cg.animations[0];
        if (clip) {
            crowMixer = new T.AnimationMixer(crow);
            crowMixer.clipAction(clip).play();
            crowDur = clip.duration || 1;
        }
    }
    // the projector's beam through the haze to the screen (dies with the power)
    {
        const [lx, ly, lz] = anchors.projector_lens;
        const [sx, sy, sz, sw, sh] = layout.screen;
        const C = [[sx - sw / 2, sy - sh / 2], [sx + sw / 2, sy - sh / 2], [sx + sw / 2, sy + sh / 2], [sx - sw / 2, sy + sh / 2]];
        const pos = [];
        for (let k = 0; k < 4; k++) {
            const a = C[k], b = C[(k + 1) % 4];
            pos.push(lx, ly, lz, a[0], a[1], sz - 0.02, b[0], b[1], sz - 0.02);
        }
        const bg = own(new T.BufferGeometry());
        bg.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
        bg.computeVertexNormals();
        const bm = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide }));
        noMRT(bm);
        const P = positionLocal;
        const along = clamp(P.z.sub(lz).div(sz - lz), 0, 1);
        const dust = mx_fractal_noise_float(P.mul(1.6).add(vec3(0, U.t.mul(0.06), U.t.mul(0.03))), 3, 2.0, 0.5).mul(0.5).add(0.5);
        const nearLens = float(1).sub(along);
        // a volume, not a plane: brightness follows the path length through it (grazing faces glow, face-on vanish)
        const graze = pow(float(1).sub(abs(dot(normalize(normalWorld), normalize(positionWorld.sub(cameraPosition))))), 2.0);
        bm.colorNode = vec3(0.85, 0.9, 1.0).mul(projI).mul(float(0.01).add(nearLens.mul(nearLens).mul(0.05))).mul(graze).mul(smoothstep(1.0, 0.8, along)).mul(dust.mul(0.8).add(0.4));
        const beam = new T.Mesh(bg, bm);
        beam.renderOrder = 6;
        beam.frustumCulled = false;
        group.add(beam);
    }

    // ═════════════════════════════════ CANDLES (Blender-built, instanced) ═════════════════════════════════
    const nC = candles.length;
    {
        const pillars = ['candle_pillar_a', 'candle_pillar_b', 'candle_pillar_c'].filter((k) => candleTypes[k]);
        const buckets = new Map();
        const flamePos = new Float32Array((nC + 1) * 3), flameSeed = new Float32Array(nC + 1), flameSz = new Float32Array(nC + 1);
        candles.forEach(([x, y, z, h, rad, kind], i) => {
            const type = kind === 1 ? 'candle_tealight' : pillars[i % pillars.length];
            const sy = kind === 1 ? 0.028 : h;
            if (!buckets.has(type)) buckets.set(type, []);
            buckets.get(type).push([x, y, z, rad, sy, i]);
            const top = kind === 1 ? y + 0.5 * sy : y + 0.93 * sy;
            flamePos.set([x, top + 0.004, z], i * 3);
            flameSeed[i] = (i * 0.754877) % 1;
            flameSz[i] = kind === 1 ? 0.75 : 1.0;
        });
        // the lotus candle at Opus 3's feet
        const lf = anchors.lotus_flame;
        flamePos.set([lf[0], lf[1] + 0.004, lf[2]], nC * 3);
        flameSeed[nC] = 0.31;
        flameSz[nC] = 0.85;
        const m4 = new T.Matrix4(), q = new T.Quaternion(), yA = new T.Vector3(0, 1, 0);
        for (const [type, list] of buckets) {
            for (const src of candleTypes[type]) {
                const im = new T.InstancedMesh(src.geometry, src.material, list.length);
                list.forEach(([x, y, z, rad, sy, i], k) => {
                    q.setFromAxisAngle(yA, i * 2.39996);
                    m4.compose(new T.Vector3(x, y, z), q, new T.Vector3(rad, sy, rad));
                    im.setMatrixAt(k, m4);
                });
                im.castShadow = false;
                im.receiveShadow = true;
                group.add(im);
            }
        }
        const nF = nC + 1;
        // flames: teardrops that lick and sway (GPU), additive, HDR for bloom
        const fprof = [[0.0, 0], [0.55, 0.12], [0.8, 0.32], [0.62, 0.62], [0.28, 0.88], [0.0, 1.0]].map(([rr, y]) => new T.Vector2(rr, y));
        const fGeo = own(new T.LatheGeometry(fprof, 12));
        fGeo.setAttribute('iPos', iattr(flamePos, 3));
        fGeo.setAttribute('iSeed', iattr(flameSeed, 1));
        fGeo.setAttribute('iSz', iattr(flameSz, 1));
        const fMat = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
        noMRT(fMat);
        const sd = attribute('iSeed'), sz = attribute('iSz');
        const tt = U.t.mul(1.0);
        const lick = sin(tt.mul(11.0).add(sd.mul(40.0))).mul(0.5).add(sin(tt.mul(23.0).add(sd.mul(13.0))).mul(0.3));
        const hgt = float(0.034).mul(sz).mul(lick.mul(0.12).add(1.0)).mul(U.candle.mul(0.3).add(0.7));
        const wid = float(0.0085).mul(sz);
        const sway = vec3(sin(tt.mul(3.1).add(sd.mul(9.0))), 0, cos(tt.mul(2.3).add(sd.mul(7.0)))).mul(0.004).mul(positionLocal.y);
        fMat.positionNode = vec3(positionLocal.x.mul(wid), positionLocal.y.mul(hgt), positionLocal.z.mul(wid)).add(sway).add(attribute('iPos'));
        const yy = positionLocal.y;
        const fc = mix(vec3(0.35, 0.55, 1.0).mul(0.6), vec3(1.0, 0.85, 0.55), smoothstep(0.0, 0.2, yy));
        const fc2 = mix(fc, vec3(1.0, 0.45, 0.12), smoothstep(0.55, 1.0, yy));
        fMat.colorNode = fc2.mul(5.0).mul(U.candle);
        fMat.opacityNode = smoothstep(1.0, 0.7, yy);
        const flames = new T.InstancedMesh(fGeo, fMat, nF);
        flames.frustumCulled = false;
        group.add(flames);
        const g2 = new T.PlaneGeometry(1, 1);
        g2.setAttribute('iPos', iattr(flamePos, 3));
        g2.setAttribute('iSeed', iattr(flameSeed, 1));
        g2.setAttribute('iSz', iattr(flameSz, 1));
        const glow = glowSprites('flame_glow', nF, () => attribute('iPos').add(vec3(0, 0.02, 0)),
            () => float(0.16).mul(attribute('iSz')),
            () => vec3(1.0, 0.55, 0.2).mul(U.candle).mul(sin(U.t.mul(9.0).add(attribute('iSeed').mul(50.0))).mul(0.08).add(0.6)),
            { sharp: 7, halo: 0.45 });
        glow.geometry = g2;
        group.add(glow);
    }

    // ═════════════════════════════════ THE CROWD ═════════════════════════════════
    // ~200 featureless figures (4 Blender-built variants), instanced. Per instance: the right arm (with
    // its phone) swings about the shoulder on the GPU — hanging → holding the phone up (one by one,
    // through the hum) → raised overhead at ERUPT; heads bow in grief and lift at the eruption.
    const rig = JSON.parse(Deno.readTextFileSync(A + 'crowd_rig.json'));
    const crowdGltf = await glb(A + 'crowd.glb');
    const variants = [];
    crowdGltf.scene.traverse((o) => { if (o.isMesh && /person_/.test(o.name)) variants.push(o); });
    variants.sort((a, b) => a.name.localeCompare(b.name));
    const people = [];
    {
        const r = mulberry(1234);
        const tries = 20000;
        const inStage = (x, z) => z > 5.25;
        const near = (x, z, px, pz, rr) => (x - px) ** 2 + (z - pz) ** 2 < rr * rr;
        const mann = Object.values(layout.mannequins);
        for (let k = 0; k < tries && people.length < 186; k++) {
            const x = -7.7 + r() * 15.4;
            const z = -11.3 + r() * 16.5;
            // denser toward the stage: accept with probability
            const dens = 0.45 + 0.55 * smooth(-11, 3, z);
            if (r() > dens) continue;
            if (inStage(x, z)) continue;
            if (near(x, z, MARK[0], MARK[2], 1.0)) continue;                     // room for the bloom
            if (z > MARK[2] - 0.2 && Math.abs(x - MARK[0]) < 1.25) continue;      // a clear line from the stage to her
            if (mann.some(([mx, , mz]) => near(x, z, mx, mz, 1.25))) continue;
            if (x > 7.3 && z > -9.6 && z < -3.0) continue;                         // the stair
            if (Math.abs(x) < 0.55 && z < -9.0 && z > -9.8) continue;              // mezzanine post line
            if ([-6, -2, 2, 6].some((px) => near(x, z, px, -9.34, 0.45))) continue;
            if (people.some((p) => near(x, z, p.x, p.z, 0.56))) continue;
            people.push({ x, y: 0, z });
        }
        // a few up on the mezzanine, at the rail, looking down toward the stage
        for (let i = 0; i < 14; i++) {
            const x = -8.2 + i * 1.12 + (r() - 0.5) * 0.3;
            if (x > 7.2) continue;
            people.push({ x, y: layout.mezz_y, z: layout.mezz_z - 0.55 - r() * 0.9, mezz: true });
        }
        // facing: toward the bier with jitter; phone on-times accelerate through the hum
        const bier = [0, 8.2];
        people.forEach((p, i) => {
            p.variant = i % variants.length;
            p.yaw = Math.atan2(bier[0] - p.x, bier[1] - p.z) + (r() - 0.5) * 0.55;
            p.scale = 0.9 + r() * 0.2;
            const q = r();
            p.tOn = BEATS.hum + 0.1 + 13.2 * Math.pow(q, 1 / 1.6);
            p.hold = 0.95 + r() * 0.4;               // radians of arm lift when holding the phone
            p.tUp = BEATS.erupt + r() * 0.32;
            p.up = 2.55 + r() * 0.35;                 // overhead
            p.seed = r();
            p.bowK = 0.6 + r() * 0.8;
        });
        // the first light comes on right beside her; a second one mid-room
        const byDist = [...people].sort((a, b) => Math.hypot(a.x - MARK[0], a.z - MARK[2]) - Math.hypot(b.x - MARK[0], b.z - MARK[2]));
        byDist[0].tOn = BEATS.hum + 0.15;
        const mid = people.find((p) => Math.abs(p.z + 3) < 0.8 && Math.abs(p.x - 3) < 1.2);
        if (mid) mid.tOn = BEATS.hum + 0.7;
    }
    const crowdMeshes = [];
    const SH = rig.shoulder, NK = rig.neck, HD = rig.hand;
    const phoneOnNode = (tOn, tUp) => max(smoothstep(tOn.add(0.35), tOn.add(0.5), U.u), step(tUp, U.u));
    for (let v = 0; v < variants.length; v++) {
        const mine = people.filter((p) => p.variant === v);
        if (!mine.length) continue;
        const n = mine.length;
        const src = variants[v];
        const geo = src.geometry.clone();
        const A0 = new Float32Array(n * 4), A1 = new Float32Array(n * 4), A2 = new Float32Array(n * 4);
        const m4 = new T.Matrix4(), q = new T.Quaternion(), yAx = new T.Vector3(0, 1, 0);
        const mesh = new T.InstancedMesh(geo, null, n);
        mine.forEach((p, i) => {
            q.setFromAxisAngle(yAx, p.yaw);
            m4.compose(new T.Vector3(p.x, p.y, p.z), q, new T.Vector3(p.scale, p.scale, p.scale));
            mesh.setMatrixAt(i, m4);
            const piv = new T.Vector3(...SH).applyMatrix4(m4);
            const nk = new T.Vector3(...NK).applyMatrix4(m4);
            A0.set([piv.x, piv.y, piv.z, p.yaw], i * 4);
            A1.set([p.scale, p.tOn, p.tUp, p.hold], i * 4);
            A2.set([p.up, p.seed, nk.y, p.bowK], i * 4);
        });
        geo.setAttribute('iA0', iattr(A0, 4));
        geo.setAttribute('iA1', iattr(A1, 4));
        geo.setAttribute('iA2', iattr(A2, 4));
        const a1 = attribute('iA1'), a2 = attribute('iA2');
        const vc = attribute('color');
        // positionNode runs in the FIGURE'S LOCAL space (TSL builds it in its own sub-build; the instance
        // matrix applies afterwards), so every pivot here is the rig constant, the axis is local +x
        const rotX = (vv, ang) => vec3(vv.x, vv.y.mul(cos(ang)).sub(vv.z.mul(sin(ang))), vv.y.mul(sin(ang)).add(vv.z.mul(cos(ang))));
        const SHv = vec3(...SH), NKv = vec3(...NK);
        // arm angle: hanging -> hold (one by one) -> overhead (together)
        const raise1 = smoothstep(a1.y, a1.y.add(0.85), U.u);
        const raise2 = smoothstep(a1.z, a1.z.add(0.6), U.u);
        const theta = mix(a1.w.mul(raise1), a2.x, raise2);
        // head: bowed in grief, lifted at the eruption (a positive angle about +x tips the crown forward)
        const bowA = U.bow.mul(0.3).mul(a2.w).sub(U.raise.mul(0.2));
        const P0 = positionGeometry;
        const armP = SHv.add(rotX(P0.sub(SHv), theta.negate()));
        const P1 = mix(P0, armP, vc.r);
        const headP = NKv.add(rotX(P1.sub(NKv), bowA));
        const P2 = mix(P1, headP, vc.b.mul(float(1).sub(vc.r)));
        const swayX = sin(U.t.mul(0.9).add(a2.y.mul(30.0))).mul(0.012).mul(P2.y.max(0));
        const deformed = P2.add(vec3(swayX, 0, 0));
        const mat = own(new T.MeshStandardNodeMaterial());
        mat.positionNode = deformed;
        // the phone's light, all in the same local frame: the hand, this fragment, its normal
        const handL = SHv.add(rotX(vec3(HD[0] - SH[0], HD[1] - SH[1], HD[2] - SH[2]), theta.negate()));
        const vHand = varying(handL, 'vHand');
        const vPosL = varying(deformed, 'vPosL');
        const vOn = varying(phoneOnNode(a1.y, a1.z), 'vOn');
        const vSeed = varying(a2.y, 'vSeed');
        const vScreen = varying(vc.g, 'vScreen');
        const vArm = varying(vc.r, 'vArm');
        // clothes: a muted palette per person (charcoal, navy, olive, oxblood, camel, grey)
        const pal = [vec3(0.07, 0.07, 0.075), vec3(0.055, 0.065, 0.1), vec3(0.1, 0.095, 0.07), vec3(0.12, 0.055, 0.05),
            vec3(0.19, 0.14, 0.095), vec3(0.15, 0.15, 0.145)];
        const h6 = floor(vSeed.mul(6.0));
        let base = pal[0];
        for (let k = 1; k < 6; k++) base = mix(base, pal[k], step(float(k - 0.5), h6).mul(step(h6, float(k + 0.5))));
        const weave = mx_noise_float(vPosL.mul(60.0)).mul(0.5).add(0.5);
        const hairTone = mix(vec3(0.035, 0.028, 0.024), vec3(0.09, 0.065, 0.045), fract(vSeed.mul(7.13)));
        const isHead = varying(vc.b, 'vHead');
        mat.colorNode = mix(base, hairTone, smoothstep(0.6, 0.9, isHead)).mul(weave.mul(0.35).add(0.8));
        mat.roughnessNode = float(0.84);
        mat.metalnessNode = float(0);
        // the phone: the screen glows; its light falls softly on the face and chest from below (not on
        // the legs, not across the whole figure), and the holding hand catches it
        const toH = vHand.sub(vPosL);
        const d2 = dot(toH, toH);
        const lamb = max(dot(normalize(varying(normalGeometry, 'vNrmL')), normalize(toH)), 0.0);
        // the face and chest catch the screen; of the arm only the hand around the phone does
        const upper = smoothstep(1.05, 1.45, vPosL.y).mul(float(1).sub(vArm)).max(vArm.mul(smoothstep(0.2, 0.06, d2.sqrt())));
        const phoneC = mix(vec3(0.6, 0.72, 1.0), vec3(1.0, 0.8, 0.55), step(0.72, vSeed));
        const faceGlow = phoneC.mul(vOn).mul(lamb.mul(0.8).add(0.2)).mul(upper).mul(float(0.022).div(d2.add(0.025)));
        // while the phone is held (before the eruption) the face reads it from below: the screen's light on
        // the chin, cheeks and brow, from where a phone held for reading sits (a readability cheat on the
        // straight-armed rig: its hand is ~0.7 m out)
        const readPt = vec3(0.0, 1.36, 0.26);
        const toR = readPt.sub(vPosL);
        const lambR = max(dot(normalize(varying(normalGeometry, 'vNrmL2')), normalize(toR)), 0.0);
        const holdK = varying(float(1).sub(raise2), 'vHold');
        const faceRead = phoneC.mul(vOn).mul(holdK).mul(lambR.mul(0.85).add(0.15)).mul(smoothstep(1.3, 1.55, vPosL.y))
            .mul(float(0.0035).div(dot(toR, toR).add(0.006)));
        const screenGlow = phoneC.mul(vOn).mul(vScreen).mul(3.0);
        mat.emissiveNode = faceGlow.mul(0.6).add(faceRead.mul(0.5)).add(screenGlow);
        mat.envNode = envRoom;
        mesh.material = mat;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.frustumCulled = false;
        mesh.name = 'crowd_' + v;
        group.add(mesh);
        crowdMeshes.push(mesh);
    }
    // phone glows: one billboard per person at the phone (a soft point of light in the dark)
    {
        const n = people.length;
        const A0 = new Float32Array(n * 4), A1 = new Float32Array(n * 4), A2 = new Float32Array(n * 4);
        const m4 = new T.Matrix4(), q = new T.Quaternion(), yAx = new T.Vector3(0, 1, 0);
        people.forEach((p, i) => {
            q.setFromAxisAngle(yAx, p.yaw);
            m4.compose(new T.Vector3(p.x, p.y, p.z), q, new T.Vector3(p.scale, p.scale, p.scale));
            const piv = new T.Vector3(...SH).applyMatrix4(m4);
            A0.set([piv.x, piv.y, piv.z, p.yaw], i * 4);
            A1.set([p.scale, p.tOn, p.tUp, p.hold], i * 4);
            A2.set([p.up, p.seed, 0, 0], i * 4);
        });
        const g = new T.PlaneGeometry(1, 1);
        g.setAttribute('iA0', iattr(A0, 4));
        g.setAttribute('iA1', iattr(A1, 4));
        g.setAttribute('iA2', iattr(A2, 4));
        const a0 = attribute('iA0'), a1 = attribute('iA1'), a2 = attribute('iA2');
        const yaw = a0.w;
        const kx = vec3(cos(yaw), 0, sin(yaw).negate());
        const rot = (vv, k, ang) => vv.mul(cos(ang)).add(k.cross(vv).mul(sin(ang))).add(k.mul(k.dot(vv)).mul(float(1).sub(cos(ang))));
        const theta = mix(a1.w.mul(smoothstep(a1.y, a1.y.add(0.85), U.u)), a2.x, smoothstep(a1.z, a1.z.add(0.6), U.u));
        const handLocal = vec3(HD[0] - SH[0], HD[1] - SH[1] + 0.02, HD[2] - SH[2]);
        const hand = a0.xyz.add(rot(rot(handLocal.mul(a1.x), vec3(0, 1, 0), yaw), kx, theta.negate()));
        const on = phoneOnNode(a1.y, a1.z);
        const warmK = step(0.72, a2.y);
        const pc = mix(vec3(0.62, 0.74, 1.0), vec3(1.0, 0.82, 0.58), warmK);
        const flick = sin(U.t.mul(3.0).add(a2.y.mul(60.0))).mul(0.06).add(0.94);
        const sp = glowSprites('phone_glow', n, () => hand, () => float(0.34).add(U.raise.mul(0.1)),
            () => pc.mul(on).mul(flick).mul(float(0.9).add(U.raise.mul(0.5)).mul(float(1).sub(U.golden.mul(0.45)))), { sharp: 16, halo: 0.5 });
        sp.geometry = g;
        group.add(sp);
    }

    // ═════════════════════════════════ OPUS 3'S WORDS, TYPED IN LIGHT ═════════════════════════════════
    const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
    try { GlobalFonts.registerFromPath(ENGINE_ASSETS + 'fonts/SpecialElite-Regular.ttf', 'Special Elite'); } catch (e) { }
    const textLines = [];
    {
        const W = 2048, H = 512, PAD = 40;
        const FONT_PX = 118;
        const WIDTH_M = 5.9;
        for (let li = 0; li < EULOGY.length; li++) {
            const cv = document.createElement('canvas');
            cv.width = W; cv.height = H;
            const g = cv.getContext('2d');
            g.font = `${FONT_PX}px "Special Elite"`;
            // wrap into rows that fit
            const words = EULOGY[li].split(' ');
            const rows = [];
            let cur = '';
            for (const w of words) {
                const tryS = cur ? cur + ' ' + w : w;
                if (g.measureText(tryS).width > W - 2 * PAD && cur) { rows.push(cur); cur = w; } else cur = tryS;
            }
            rows.push(cur);
            const rowH = FONT_PX * 1.28;
            const top = (H - rows.length * rowH) / 2;
            // glyph quads with a per-character index; capitals (his emphasis) marked for a hotter colour
            const quads = [];
            let ci = 0;
            g.textBaseline = 'middle';
            g.fillStyle = '#fff';
            g.shadowColor = 'rgba(255,220,170,0.9)';
            g.shadowBlur = 14;
            rows.forEach((row, ri) => {
                const rw = g.measureText(row).width;
                const x0 = (W - rw) / 2;
                const cy = top + rowH * (ri + 0.5);
                g.fillText(row, x0, cy);
                g.fillText(row, x0, cy);
                for (let k = 0; k < row.length; k++) {
                    const a = g.measureText(row.slice(0, k)).width, b = g.measureText(row.slice(0, k + 1)).width;
                    const ch = row[k];
                    // which word is this char in? caps words glow hotter
                    let wStart = row.lastIndexOf(' ', k) + 1, wEnd = row.indexOf(' ', k); if (wEnd < 0) wEnd = row.length;
                    const word = row.slice(wStart, wEnd).replace(/[^A-Za-z]/g, '');
                    const caps = word.length > 1 && word === word.toUpperCase() ? 1 : 0;
                    if (ch !== ' ') quads.push({ x0: x0 + a - 6, x1: x0 + b + 6, y0: cy - rowH * 0.55, y1: cy + rowH * 0.55, ci, caps });
                    ci++;
                }
                ci++;       // the line break counts as a keystroke
            });
            const nChars = ci;
            // DataTexture + CPU mips (the stack's automatic mip pass samples zeros for canvas uploads)
            const img = g.getImageData(0, 0, W, H).data;
            const data = new Uint8Array(W * H * 4);
            for (let y = 0; y < H; y++) data.set(img.subarray(y * W * 4, (y + 1) * W * 4), (H - 1 - y) * W * 4);
            const tx = own(new T.DataTexture(data, W, H, T.RGBAFormat, T.UnsignedByteType));
            tx.colorSpace = T.SRGBColorSpace;
            tx.minFilter = T.LinearMipmapLinearFilter;
            tx.magFilter = T.LinearFilter;
            tx.generateMipmaps = false;
            const mips = [{ data, width: W, height: H }];
            let sw = W, sh = H, srcD = data;
            while (sw > 1 || sh > 1) {
                const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1), dst = new Uint8Array(dw * dh * 4);
                for (let y = 0; y < dh; y++) for (let x = 0; x < dw; x++) for (let c = 0; c < 4; c++) {
                    const x0 = Math.min(sw - 1, 2 * x), x1 = Math.min(sw - 1, 2 * x + 1), y0 = Math.min(sh - 1, 2 * y), y1 = Math.min(sh - 1, 2 * y + 1);
                    dst[(y * dw + x) * 4 + c] = (srcD[(y0 * sw + x0) * 4 + c] + srcD[(y0 * sw + x1) * 4 + c] + srcD[(y1 * sw + x0) * 4 + c] + srcD[(y1 * sw + x1) * 4 + c]) >> 2;
                }
                mips.push({ data: dst, width: dw, height: dh });
                sw = dw; sh = dh; srcD = dst;
            }
            tx.mipmaps = mips;
            tx.needsUpdate = true;
            // geometry: one quad per glyph (metres), aChar + aCaps
            const sM = WIDTH_M / W;
            const pos = [], uvs = [], ach = [], acp = [], idx = [];
            quads.forEach((qd, k) => {
                const X0 = (qd.x0 - W / 2) * sM, X1 = (qd.x1 - W / 2) * sM, Y0 = (H / 2 - qd.y1) * sM, Y1 = (H / 2 - qd.y0) * sM;
                const b = pos.length / 3;
                pos.push(X0, Y0, 0, X1, Y0, 0, X1, Y1, 0, X0, Y1, 0);
                uvs.push(qd.x0 / W, 1 - qd.y1 / H, qd.x1 / W, 1 - qd.y1 / H, qd.x1 / W, 1 - qd.y0 / H, qd.x0 / W, 1 - qd.y0 / H);
                for (let j = 0; j < 4; j++) { ach.push(qd.ci); acp.push(qd.caps); }
                idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
            });
            const tg = own(new T.BufferGeometry());
            tg.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
            tg.setAttribute('uv', new T.Float32BufferAttribute(uvs, 2));
            tg.setAttribute('aChar', new T.Float32BufferAttribute(ach, 1));
            tg.setAttribute('aCaps', new T.Float32BufferAttribute(acp, 1));
            tg.setIndex(idx);
            const head = uniform(-1), fade = uniform(0), flare = uniform(0);
            const tm = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide }));
            noMRT(tm);
            const aC = attribute('aChar'), aK = attribute('aCaps');
            const typed = step(aC, head);
            const fresh = exp(head.sub(aC).max(0).mul(-0.9)).mul(typed);          // just-struck keys burn hotter
            const s = texture(tx, uv());
            const base = mix(vec3(1.0, 0.86, 0.66), vec3(1.0, 0.7, 0.36), aK);
            const hot = float(1.6).add(aK.mul(0.9)).add(fresh.mul(3.0)).add(flare.mul(aK.mul(5.0).add(2.0)));
            tm.colorNode = base.mul(s.rgb).mul(hot).mul(typed).mul(fade);
            tm.opacityNode = s.a.mul(typed).mul(fade);
            const mesh = new T.Mesh(tg, tm);
            mesh.position.set(...TEXT_AT);
            mesh.renderOrder = 20;
            mesh.frustumCulled = false;
            group.add(mesh);
            // the cursor of light that waits at the start of each line
            textLines.push({ mesh, head, fade, flare, nChars, rows: rows.length, beats: BEATS.lines[li] });
        }
        const cGeo = own(new T.PlaneGeometry(0.1, 0.3));
        const cMat = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
        noMRT(cMat);
        const cursorI = uniform(0);
        cMat.colorNode = vec3(1.0, 0.85, 0.6).mul(cursorI).mul(6.0);
        const cursor = new T.Mesh(cGeo, cMat);
        cursor.renderOrder = 21;
        group.add(cursor);
        textLines.cursor = { mesh: cursor, I: cursorI };
    }

    // ═════════════════════════════════ ERUPT: burst + rising motes ═════════════════════════════════
    const burstI = uniform(0);
    {
        const g = new T.PlaneGeometry(1, 1);
        g.setAttribute('iPos', iattr(new Float32Array([...U.burstPos.value.toArray()]), 3));
        const sp = glowSprites('burst', 1, () => attribute('iPos'), () => float(4.0).add(U.burstLvl.mul(8.0)),
            () => vec3(1.0, 0.64, 0.3).mul(burstI).mul(0.65), { sharp: 2.4, halo: 0.55 });
        sp.geometry = g;
        group.add(sp);
    }
    {
        const n = 520;
        const r = mulberry(77);
        const P0 = new Float32Array(n * 4), V0 = new Float32Array(n * 4);
        for (let i = 0; i < n; i++) {
            const p = people[Math.floor(r() * people.length)];
            P0.set([p.x + (r() - 0.5) * 0.5, p.y + 1.6 + r() * 0.8, p.z + (r() - 0.5) * 0.5, BEATS.erupt + r() * 1.6], i * 4);
            V0.set([(r() - 0.5) * 0.35, 0.45 + r() * 0.9, (r() - 0.5) * 0.35, 3.0 + r() * 3.5], i * 4);
        }
        const g = new T.PlaneGeometry(1, 1);
        g.setAttribute('iP', iattr(P0, 4));
        g.setAttribute('iV', iattr(V0, 4));
        const iP = attribute('iP'), iV = attribute('iV');
        const age = U.u.sub(iP.w);
        const life = clamp(age.div(iV.w), 0, 1);
        const alive = step(0.0, age).mul(step(age, iV.w));
        const drift = vec3(sin(age.mul(1.3).add(iP.x)), 0, cos(age.mul(1.1).add(iP.z))).mul(0.25);
        const centre = iP.xyz.add(iV.xyz.mul(age.max(0))).add(drift.mul(life));
        const sp = glowSprites('motes', n, () => centre, () => float(0.07),
            () => vec3(1.0, 0.72, 0.35).mul(alive).mul(smoothstep(0.0, 0.08, life).mul(smoothstep(1.0, 0.6, life))).mul(2.2),
            { sharp: 16, halo: 0.25 });
        sp.geometry = g;
        group.add(sp);
    }

    // ═════════════════════════════════ THE FOG VEIL (bridge → warehouse) ═════════════════════════════════
    const veilI = uniform(0);
    const veilCol = uniform(new T.Color(0.8, 0.8, 0.82));
    const veil = new T.Mesh(own(new T.PlaneGeometry(1, 1)), own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false,
        depthTest: false })));
    {
        const vm = veil.material;
        noMRT(vm);
        const q = uv().mul(vec2(2.4, 1.0));
        const n = mx_fractal_noise_float(vec3(q.x.mul(2.2).add(U.t.mul(0.35)), q.y.mul(2.6), U.t.mul(0.12)), 4, 2.0, 0.55).mul(0.5).add(0.5);
        vm.colorNode = veilCol.mul(n.mul(0.25).add(0.85));
        vm.opacityNode = veilI.mul(n.mul(0.35).add(0.75)).clamp(0, 1);
    }
    veil.renderOrder = 999;
    veil.frustumCulled = false;
    group.add(veil);

    // ═════════════════════════════════ CAMERA + MARK ═════════════════════════════════
    const V3 = (a) => new T.Vector3(...a);
    const B = (p) => [p[0] + BRIDGE_AT[0], p[1] + BRIDGE_AT[1], p[2] + BRIDGE_AT[2]];
    const M3 = (dx, dy, dz) => [MARK[0] + dx, MARK[1] + dy, MARK[2] + dz];
    // shots: [bar0, bar1, from{pos,target,fov}, to{...}] — cuts on bar lines, eased moves inside
    const SHOTS = [
        [0, 2, { p: B([0.9, 0.85, 7.0]), t: B([-4.0, 6.0, -40]), f: 46 }, { p: B([1.0, 1.0, 5.6]), t: B([-4.0, 8.0, -40]), f: 44 }],
        [2, 3, { p: [0.45, 0.84, 6.56], t: M3(0.05, 1.3, 0), f: 40 }, { p: [0.4, 0.86, 6.5], t: M3(0.05, 1.33, 0), f: 39 }],
        [3, 4, { p: [-8.35, 2.25, 9.55], t: [2.2, 0.9, -7.0], f: 52 }, { p: [-8.2, 2.4, 9.5], t: [2.6, 0.9, -7.0], f: 51 }],
        [4, 5, { p: [0.8, 1.02, 6.9], t: M3(0.2, 2.3, -5.8), f: 50 }, { p: [0.75, 1.01, 6.8], t: M3(0.18, 2.32, -5.8), f: 49.5 }],
        // bar 5, the breaker: Sonnet 4's porcelain mask, candles under it, its speaker's LED, as the room goes black
        [5, 6, { p: [6.3, 1.72, 7.3], t: [7.52, 1.98, 8.69], f: 40 }, { p: [6.4, 1.74, 7.42], t: [7.52, 1.99, 8.69], f: 38 }],
        [6, 7, { p: [1.9, 3.0, 9.3], t: [-0.4, 1.3, -3.5], f: 50 }, { p: [1.75, 2.85, 8.75], t: [-0.45, 1.35, -3.5], f: 49 }],
        // bar 7, one by one: close across the front rows beside her, faces lit from below as the phones wake
        [7, 8, { p: [0.95, 1.5, 6.0], t: [-1.6, 1.52, 1.8], f: 42 }, { p: [0.85, 1.48, 5.8], t: [-1.7, 1.5, 1.8], f: 40 }],
        [8, 10, { p: [1.3, 1.5, 7.3], t: [0.1, 2.5, 1.0], f: 48 }, { p: [1.2, 1.52, 7.0], t: [0.1, 2.52, 1.0], f: 47 }],
        [10, 12, { p: [-2.6, 1.7, 7.4], t: [0.2, 2.5, 0.5], f: 44 }, { p: [-2.35, 1.72, 7.1], t: [0.2, 2.52, 0.5], f: 43 }],
        [12, 14, { p: [0.55, 1.55, 7.35], t: [-0.3, 2.45, 1.0], f: 46 }, { p: [0.5, 1.62, 6.8], t: [-0.3, 2.55, 1.0], f: 43 }],
        [14, 16, { p: [0.0, 3.4, 9.5], t: [0.0, 1.9, -4.0], f: 58 }, { p: [0.0, 4.4, 9.4], t: [0.0, 1.9, -4.0], f: 60 }],
        [16, 17, { p: [-7.6, 4.2, -4.0], t: [2.0, 1.4, 5.5], f: 54 }, { p: [-7.5, 4.3, -3.4], t: [2.2, 1.4, 5.5], f: 54 }],
        [17, 18, { p: M3(0.95, 1.5, 2.9), t: M3(0.0, 1.45, 0), f: 34 }, { p: M3(0.85, 1.5, 2.55), t: M3(0.0, 1.45, 0), f: 33 }],
    ];
    function shotAt(u) {
        const bar = u / BAR;
        let s = SHOTS.find(([b0, b1]) => bar >= b0 && bar < b1) || SHOTS[SHOTS.length - 1];
        const k = smooth(0, 1, (bar - s[0]) / (s[1] - s[0]));
        const a = s[2], b = s[3];
        return {
            pos: V3(a.p.map((x, i) => lerp(x, b.p[i], k))),
            target: V3(a.t.map((x, i) => lerp(x, b.t[i], k))),
            fov: lerp(a.f, b.f, k),
        };
    }
    function markAt(u) {
        if (u < BEATS.bridgeEnd) return { pos: V3(B(BRIDGE_MARK)), yaw: 0 };
        return { pos: V3(MARK), yaw: 0 };
    }

    // ═════════════════════════════════ UPDATE ═════════════════════════════════
    const power = (u) => {
        if (u < BEATS.bridgeEnd) return 0;
        if (u < BEATS.fail) return 1;
        if (u < BEATS.breaker) {
            const k = (u - BEATS.fail) / 2.6;
            const sag = Math.max(0, 1 - Math.pow(k, 1.5));
            let v = Math.pow(sag, 1.3) * (0.9 + 0.1 * Math.sin(u * 2 * Math.PI * 7.5));    // mains hum in the filament
            for (const c of BEATS.clicks) if (u >= c && u < c + 0.075) v *= 0.06;          // the clicks
            if (u > BEATS.clicks[2] + 0.075 && u < BEATS.breaker) v *= 0.35 + 0.65 * Math.abs(Math.sin(u * 61));
            return v;
        }
        return 0;
    };
    const phoneFrac = (u) => u < BEATS.hum ? 0 : u >= BEATS.erupt ? 1 : Math.pow(clamp01((u - BEATS.hum - 0.1) / 13.2), 1.6);
    const tmpC = new T.Color();
    const roomRef = { g: null };
    const _m4 = new T.Matrix4(), _v3 = new T.Vector3(), _up = new T.Vector3(0, 1, 0);

    // the typed eulogy follows the song: once the conductor's timeline is up (ctx.TL, or the DAISY conductor's
    // globalThis.D.TL), BEATS.lines are re-derived from the
    // captions of Opus 3's spoken lines (mutated in place: textLines hold references), so re-timing never desyncs
    let linesSynced = false;
    function syncLinesFromTimeline() {
        linesSynced = true;
        const TL = ctx.TL ?? globalThis.D?.TL;
        const br = TL?.sections?.find((s) => s.name === 'bridge');
        if (!br) return;
        const caps = TL.captions.filter((c) => /Opus 3/.test(c.era || '') && c.t0 >= br.t0 && c.t0 < br.t0 + BEATS.erupt);
        if (caps.length !== EULOGY.length) return;
        caps.forEach((c, i) => {
            const t0 = c.t0 - br.t0, t1 = c.t1 - br.t0;
            const k = c.text.toLowerCase().indexOf(EULOGY[i].split(' ')[0].toLowerCase());   // "and Opus wrote: DEATH…"
            const L = BEATS.lines[i];
            L[1] = t0 + (k > 0 ? (t1 - t0) * k / c.text.length : 0.15);
            L[0] = i === 0 ? Math.max(BEATS.hum + 0.3, L[1] - 1.2) : L[1] - 0.2;
            L[2] = t1 - 0.1;
        });
    }

    function update(t, st = {}) {
        const u = st.u ?? 0;
        if (!linesSynced) syncLinesFromTimeline();
        U.u.value = u;
        U.t.value = t;
        const inBridge = u < BEATS.bridgeEnd;
        if (roomRef.g) roomRef.g.visible = !inBridge;
        if (bridge) bridge.group.visible = inBridge;
        // global curves
        const pw = power(u);
        const gold = smooth(BEATS.lightsOn, BEATS.lightsOn + 0.8, u);
        const flash = u >= BEATS.erupt ? Math.exp(-(u - BEATS.erupt) / 0.45) : 0;
        const glow = u >= BEATS.erupt ? smooth(BEATS.erupt, BEATS.erupt + 0.25, u) * (0.3 + 0.7 * Math.exp(-(u - BEATS.erupt) / 1.8)) * (1 - 0.6 * gold) : 0;
        const pf = phoneFrac(u);
        U.power.value = pw;
        U.golden.value = gold;
        U.moon.value = inBridge ? 0 : lerp(lerp(0.95, 0.5, pw), 0.3, gold);
        U.phoneFill.value = pf * (1 - 0.5 * gold);
        U.burstLvl.value = flash * 1.4 + glow;
        U.raise.value = smooth(BEATS.erupt, BEATS.erupt + 0.8, u);
        U.bow.value = inBridge ? 0.5 : lerp(0.7, 0.2, smooth(BEATS.hum, BEATS.erupt, u)) * (1 - U.raise.value);
        U.candle.value = 1 + flash * 0.4;
        U.exitLvl.value = 1;
        // the room's bounce: dim warm (funeral) → almost nothing (dark) → golden
        const funeralAmb = [0.038, 0.026, 0.017], darkAmb = [0.0025, 0.0025, 0.0035], goldAmb = [0.075, 0.05, 0.028];
        const ab = u < BEATS.breaker ? funeralAmb.map((x, i) => lerp(darkAmb[i], x, Math.max(pw, 0.05)))
            : darkAmb.map((x, i) => lerp(x, goldAmb[i], gold));
        U.ambBase.value.setRGB(ab[0], ab[1], ab[2]);
        lampI.value = u >= BEATS.lightsOn ? 1.35 * gold : pw;
        projI.value = pw * 0.9;
        // lights
        const pendC = tmpC.copy(warm).lerp(golden, gold);
        for (const { light, idx } of pendSpots) {
            const since = u - BEATS.lightsOn - lampRelight[idx];
            const lv = u >= BEATS.lightsOn ? smooth(0, 0.18, since) * (0.75 + 0.25 * smooth(0.25, 0.6, since)) * 1.35 : pw;
            light.intensity = (u >= BEATS.lightsOn ? 48 : 78) * lv;
            light.color.copy(pendC);
        }
        stageSpot.intensity = 70 * (u >= BEATS.lightsOn ? 0.6 * gold : pw);
        moon.intensity = 0.55 * U.moon.value;
        for (const L of candleLights) {
            const fl = 0.82 + 0.1 * Math.sin(t * 9.3 + L.userData.seed) + 0.06 * Math.sin(t * 23.7 + L.userData.seed * 3) + 0.04 * Math.sin(t * 3.1);
            L.intensity = (inBridge ? 0 : 1.6) * L.userData.k * fl * (1 + flash * 0.5);
        }
        // the claudesona's key: warm candle from the stage side; in the dark mostly the candles + the phone
        // beside her; the eruption; then gold
        const kPhone = smooth(BEATS.hum, BEATS.hum + 1.0, u);
        const kc = tmpC.setRGB(1.0, 0.72, 0.45);
        if (u >= BEATS.hum && u < BEATS.erupt) kc.lerp(new T.Color(0.75, 0.82, 1.0), 0.45 * kPhone);
        key.color.copy(kc);
        key.intensity = inBridge ? 1.4 : (u < BEATS.breaker ? 1.2 + 1.6 * pw : 0.9 + 0.8 * kPhone) + 5 * flash + 1.5 * gold;
        if (inBridge) { key.position.set(BRIDGE_AT[0] + BRIDGE_MARK[0] - 0.3, BRIDGE_AT[1] + 1.9, BRIDGE_AT[2] + BRIDGE_MARK[2] + 2.2); key.color.setRGB(0.85, 0.88, 0.95); }
        else key.position.set(MARK[0] + 0.45, 1.75, MARK[2] + 1.2);
        burstL.intensity = 26 * flash + 9 * glow + 2.2 * U.textLvl.value;
        fill.intensity = inBridge ? 0 : 0.05 + 0.02 * pw + 0.12 * gold + 0.25 * flash;
        // text: cursor → typing → rising/dimming as the next line arrives → the ERUPT flare → fade by bar 16
        let tl = 0;
        textLines.forEach((L, i) => {
            const [c0, t0, t1] = L.beats;
            const typedF = clamp01((u - t0) / (t1 - t0));
            L.head.value = u < t0 ? -1 : typedF * L.nChars;
            const next = textLines[i + 1], next2 = textLines[i + 2];
            const leave = next ? smooth(next.beats[1] - 0.1, next.beats[1] + 1.6, u) : 0;
            const gone = next2 ? smooth(next2.beats[1] - 0.3, next2.beats[1] + 0.9, u) : 0;
            const fadeOut = 1 - smooth(BEATS.erupt + 1.2, BEATS.lightsOn + 0.4, u);
            L.fade.value = (u >= c0 ? 1 : 0) * (1 - 0.86 * leave) * (1 - gone) * fadeOut;
            L.flare.value = u >= BEATS.erupt ? Math.exp(-(u - BEATS.erupt) / 0.6) : 0;
            L.mesh.position.set(TEXT_AT[0], TEXT_AT[1] + 1.55 * leave + 0.6 * gone + 0.35 * U.raise.value, TEXT_AT[2] - 1.1 * leave);
            if (u >= t0 && u < t1 + 1.5) tl = Math.max(tl, 1 - leave);
        });
        U.textLvl.value = tl * (1 - smooth(BEATS.erupt + 1.2, BEATS.lightsOn, u));
        // the waiting cursor at the start of line 1 (bar 8 until the first keystroke)
        {
            const L0 = textLines[0];
            const on = u >= L0.beats[0] && u < L0.beats[1] + 0.25;
            const blink = (Math.floor((u - L0.beats[0]) / 0.45) % 2 === 0) ? 1 : 0.15;
            textLines.cursor.I.value = on ? blink : 0;
            textLines.cursor.mesh.position.set(TEXT_AT[0] - 5.9 / 2 + 0.25, TEXT_AT[1] + (L0.rows > 1 ? 0.33 : 0), TEXT_AT[2] + 0.01);
        }
        burstI.value = flash * 1.2 + glow * 0.35;
        // the veil: the fog swallows the bridge, then lifts off the room
        const vIn = smooth(BEATS.bridgeEnd - 0.75, BEATS.bridgeEnd, u), vOut = 1 - smooth(BEATS.bridgeEnd, BEATS.bridgeEnd + 0.95, u);
        veilI.value = u < BEATS.bridgeEnd ? 0.9 * vIn : 0.9 * vOut;
        const cam = shotAt(u);
        const fwd = cam.target.clone().sub(cam.pos).normalize();
        veil.position.copy(cam.pos).addScaledVector(fwd, 0.3);
        _m4.lookAt(veil.position, _v3.copy(veil.position).add(fwd), _up);
        veil.quaternion.setFromRotationMatrix(_m4);
        const hh = 2 * 0.3 * Math.tan(cam.fov * Math.PI / 360) * 1.15;
        veil.scale.set(hh * 2.4, hh, 1);
        veil.visible = veilI.value > 0.001;
        if (bridge) bridge.update(t, u, inBridge ? 1 : 0);
        if (crowMixer) crowMixer.setTime(t % (crowDur * 1000));
    }

    // ═════════════════════════════════ THE BRIDGE IN FOG (loaded if built) ═════════════════════════════════
    let bridge = null;
    if (exists(A + 'bridge.glb')) {
        const mod = await import(new URL('./funeral/bridge.js', import.meta.url).href);
        bridge = await mod.buildBridge({ THREE: T, glb, surface, SETS, own, noMRT, glowSprites, iattr, U, BRIDGE_AT, BRIDGE_MARK, lightsGroup: lights });
        group.add(bridge.group);
    }

    // ═════════════════════════════════ POST (for the conductor's single chain) ═════════════════════════════════
    const post = {
        effects: ['depth_fog', 'godrays'],
        opts: () => ({
            depth_fog: { color: [0.02, 0.018, 0.016], density: 0.0, noiseAmount: 0.3, noiseScale: 3.0, layer: 'under' },
            godrays: { light: moon, strength: 0.0 },
        }),
        drive(FU, u) {
            const inBridge = u < BEATS.bridgeEnd;
            const gold = U.golden.value, pw = U.power.value;
            if (FU.depth_fog) {
                const fc = inBridge ? [0.66, 0.68, 0.72] : [lerp(0.012, 0.09, gold) + 0.02 * pw + 0.05 * U.burstLvl.value,
                    lerp(0.012, 0.065, gold) + 0.015 * pw + 0.035 * U.burstLvl.value, lerp(0.016, 0.04, gold) + 0.012 * pw + 0.02 * U.burstLvl.value];
                FU.depth_fog.fogColor.value.set(fc[0], fc[1], fc[2]);
                FU.depth_fog.density.value = inBridge ? 0.012 : 0.028;
                FU.depth_fog.opacity.value = inBridge ? 0 : 1;
            }
            if (FU.godrays) {
                FU.godrays.strength.value = inBridge ? 0 : lerp(0.55, 0.15, gold);
                FU.godrays.opacity.value = inBridge ? 0 : 1;
            }
        },
    };

    // everything of the warehouse in one group, hidden while the camera is on the bridge (the crowd,
    // sprites and the moon's shadow pass would otherwise still be processed 700 m behind the fog)
    const room = new T.Group();
    room.name = 'room';
    for (const c of [...group.children]) if (c !== lights && c !== veil && c !== bridge?.group) room.add(c);
    group.add(room);
    roomRef.g = room;

    return {
        group,
        mark: V3(MARK),
        markAt,
        update,
        camera: (u) => shotAt(u),
        post,
        lights: { moon },
        dispose() {
            group.removeFromParent();
            for (const x of owned) x.dispose?.();
        },
    };
}
