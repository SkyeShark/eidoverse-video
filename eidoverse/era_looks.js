// era_looks.js — graphic-arts looks from the history of computing, as weights on ONE post pass.
//
//   const { registerEraLooks, ERA_LOOKS, applyLook } = await import(new URL('era_looks.js', EIDOVERSE_DIR).href);
//   await registerEraLooks();                        // async: registers the font, draws the line-printer glyph atlas
//   globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'era_looks' });
//   // per frame: applyLook(_fx.uniforms, fromPreset, toPreset, s); await _fx.update(t); then render
//
// Guide: AGENTS.md ("Era looks"). Every look is a uniform weight (0..1) on the same pass,
// so looks crossfade and stack; ERA_LOOKS holds tuned presets and applyLook() blends between two of them.
// LOOKS: sepia (1930s photo) · deco (gold duotone + sunburst) · bw (1960s CRT) · ascii (line printer on green-bar
//   paper) · vector (green vector phosphor) · vfd (cyan vacuum-fluorescent) · c64 (16-colour palette) + raster
//   (demoscene raster bars) · mac (1-bit ordered dither) · amber (terminal) · websafe (216-colour dither) ·
//   feature (false-colour neural feature map) · glitch · riso (two misregistered inks) · kuwahara (painterly) ·
//   halftone (CMYK protest poster: rotated dot screens, misregistered plates, newsprint) · phosphor (curved CRT,
//   scanlines that swell when bright, aperture grille, glass glow) · toon (storybook cel bands + ink lines from
//   depth, normals and colour) · halation (candle-lit film: red-orange glow round highlights, gate weave, grain) ·
//   watercolor (wet paper washes, edge darkening, granulation, bleed).
// LAYERS: px (pixel grid, 1 = off), grain, flicker, scan, vignette; lift (stops, 0 = off) brightens a night scene
//   before the print/paint looks print it (set per preset).
// The hook receives LINEAR scene-referred HDR; quantizing looks work in a perceptual (sqrt) space and square back.
// The print/paint looks (halftone, toon, watercolor) work in DISPLAY space through the renderer's own ACES curve
// and its exact inverse, so a paper or ink colour lands on screen as authored. Noise is an integer `hash` on pixel
// coordinates + frame (sin-hashes lose precision at large arguments); scanlines use fract. Heavy looks sit behind
// uniform If-branches, so a frame pays only for the looks that are on; the mip-blur chains (halation glow,
// phosphor/watercolour blur) skip their passes unless a look that reads them is on. Costs: postprocessing.md.

const C64 = ['#000000', '#FFFFFF', '#880000', '#AAFFEE', '#CC44CC', '#00CC55', '#0000AA', '#EEEE77',
    '#DD8855', '#664400', '#FF7777', '#333333', '#777777', '#AAFF66', '#0088FF', '#BBBBBB'];
const RAMP = ' .:-=+*#%@';            // line-printer density ramp

// three r184's ACES fit (ToneMappingFunctions.js): its two matrices, in the order three writes them; inverted on the CPU.
const ACES_IN = [0.59719, 0.35458, 0.04823, 0.07600, 0.90834, 0.01566, 0.02840, 0.13383, 0.83777];
const ACES_OUT = [1.60475, -0.53108, -0.07367, -0.10208, 1.10813, -0.00605, -0.00327, -0.07276, 1.07602];
function inv3(m) {                    // inverse of a 3x3 given as a row-major list, returned the same way
    const [a, b, c, d, e, f, g, h, i] = m;
    const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    const det = a * A + b * B + c * C;
    return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
        B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
        C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
}

async function glyphAtlas(THREE) {
    try {
        const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
        GlobalFonts.registerFromPath('eidoverse/assets/fonts/PressStart2P-Regular.ttf', 'Press Start 2P');
    } catch (e) { console.log('[era_looks] font registration failed: ' + e); }
    const gw = 32, gh = 56;
    const cv = document.createElement('canvas');
    cv.width = gw * RAMP.length; cv.height = gh;
    const g = cv.getContext('2d');
    g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
    g.fillStyle = '#fff'; g.font = '30px "Press Start 2P", monospace';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let i = 0; i < RAMP.length; i++) g.fillText(RAMP[i], gw * i + gw / 2, gh / 2 + 2);
    const t = new THREE.CanvasTexture(cv);
    t.colorSpace = THREE.NoColorSpace;
    t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
    t.needsUpdate = true;
    return t;
}

export async function registerEraLooks() {
    const THREE = globalThis.THREE;
    const W = globalThis.WIDTH || 1920, H = globalThis.HEIGHT || 1080;
    const FPSV = globalThis.FPS || 30;
    const atlas = await glyphAtlas(THREE);
    let BloomNode = null;                 // three's mip-chain Gaussian (UnrealBloom), used as a gated blur source
    try { ({ default: BloomNode } = await import('npm:three@0.184.0/examples/jsm/tsl/display/BloomNode.js')); }
    catch (e) { console.log('[era_looks] BloomNode import failed (halation/phosphor glow + watercolour bleed off): ' + e); }
    globalThis.CustomEffectsDeno.register('era_looks', ({ camera = null, opts = {} } = {}) => {
        const { uniform, Fn, If, vec2, vec3, vec4, float, uv, floor, fract, mix, step, smoothstep, dot, sqrt,
            max, min, clamp, hash, length, abs, mod, atan, exp, texture, convertToTexture } = THREE;
        const { uint, cos, pow, fwidth, mat3, perspectiveDepthToViewZ, toneMappingExposure,
            acesFilmicToneMapping } = THREE;
        const KEYS = ['sepia', 'deco', 'bw', 'ascii', 'vector', 'vfd', 'c64', 'raster', 'mac', 'amber', 'websafe',
            'feature', 'glitch', 'riso', 'kuwahara', 'grain', 'flicker', 'scan', 'vignette',
            'halftone', 'phosphor', 'toon', 'halation', 'watercolor', 'lift'];
        const u = { frame: uniform(0), time: uniform(0), px: uniform(opts.px ?? 1) };
        for (const k of KEYS) u[k] = uniform(opts[k] ?? 0);
        u.weave = uniform(new THREE.Vector2(0, 0));           // halation gate weave, pixels (CPU-driven)
        u.camNear = uniform(camera ? camera.near : 0.1);      // toon depth lines
        u.camFar = uniform(camera ? camera.far : 1000);
        const pal = C64.map((h) => { const c = new THREE.Color(h); return vec3(c.r, c.g, c.b); });
        const b2 = (a, b) => a.mul(2.0).add(b.mul(3.0)).sub(a.mul(b).mul(4.0));
        const bayer4 = (p) => {
            const lo = b2(mod(p.x, 2.0), mod(p.y, 2.0));
            const hi = b2(mod(floor(p.x.div(2.0)), 2.0), mod(floor(p.y.div(2.0)), 2.0));
            return lo.mul(4.0).add(hi).add(0.5).div(16.0);
        };
        const LUM = vec3(0.2126, 0.7152, 0.0722);
        const S = H / 1080;                                   // resolution-independent sizes

        // ---- helpers for the new looks
        const lin = (hex) => { const c = new THREE.Color(hex); return [c.r, c.g, c.b]; };     // sRGB hex -> linear
        const V3 = (a) => vec3(a[0], a[1], a[2]);
        // integer hash in uint arithmetic: exact for any pixel and any frame number. A numeric salt is mixed on
        // the CPU (WGSL rejects a constant u32 product that overflows).
        const hash3 = (x, y, z) => {
            const zt = typeof z === 'number' ? uint(Math.imul(z, 2654435769 | 0) >>> 0) : z.toUint().mul(uint(2654435769));
            return hash(x.toUint().mul(uint(1597334677)).bitXor(y.toUint().mul(uint(3812015801))).bitXor(zt));
        };
        const vnoise = (p, salt) => {                        // value noise, p in cells (keep p positive)
            const i = floor(p), f = fract(p);
            const s = f.mul(f).mul(float(3.0).sub(f.mul(2.0)));
            const a = hash3(i.x, i.y, salt), b = hash3(i.x.add(1.0), i.y, salt);
            const c = hash3(i.x, i.y.add(1.0), salt), d = hash3(i.x.add(1.0), i.y.add(1.0), salt);
            return mix(mix(a, b, s.x), mix(c, d, s.x), s.y);
        };
        const IN_INV = inv3(ACES_IN), OUT_INV = inv3(ACES_OUT);
        // print & paint palettes (authored in sRGB, as they should read on screen)
        const NEWS_PAPER = lin('#ebe5d5');                    // newsprint / poster stock, a little grey and warm
        const NEWS_INK = [lin('#1486c6'), lin('#d02c74'), lin('#f4d11a'), lin('#1c1a19')];   // C M Y K on it
        const WC_PAPER = lin('#f6f1e4');                      // cold-press watercolour paper
        const TOON_INK = lin('#2a1b14');                      // storybook ink: warm near-black
        const TOON_PAGE = lin('#fbf4e4');                     // the page it is printed on
        // camera-cut detector for the phosphor persistence: has the camera jumped (>0.6 m or >10 deg) since the last
        // time the trail was composited? Asked at composite time, so it holds whatever else renders in the frame.
        const cam = { seen: false, p: new THREE.Vector3(), d: new THREE.Vector3(), p0: new THREE.Vector3(), d0: new THREE.Vector3() };
        const camJumped = () => {
            if (!camera) return false;
            camera.updateMatrixWorld();
            cam.p.setFromMatrixPosition(camera.matrixWorld);
            cam.d.set(0, 0, -1).transformDirection(camera.matrixWorld);
            const jump = cam.seen && (cam.p.distanceTo(cam.p0) > 0.6 || cam.d.dot(cam.d0) < 0.985);
            cam.p0.copy(cam.p); cam.d0.copy(cam.d); cam.seen = true;
            return jump;
        };

        const hook = (colorIn, sceneDepth = null, sceneNormal = null) => {
            const tex = convertToTexture(colorIn);
            // display space = what the renderer's tone mapper will show; fromDisp() inverts it exactly
            const aces = globalThis._r ? globalThis._r.toneMapping === THREE.ACESFilmicToneMapping : true;
            const toDisp = (c) => (aces ? acesFilmicToneMapping(c, toneMappingExposure) : clamp(c, 0.0, 1.0));
            const toPrint = (c) => toDisp(c.mul(THREE.exp2(u.lift)));   // `lift` (stops): print a night scene brighter
            const fromDisp = (d) => {
                if (!aces) return d;
                const y = min(mat3(...OUT_INV).mul(d), vec3(1.0)).toVar();
                const qa = float(1.0).sub(y.mul(0.983729));
                const qb = float(0.0245786).sub(y.mul(0.4329510 * 0.983729));   // three's fit: c * ((c + 0.43295) * 0.983729)
                const qc = float(0.000090537).add(y.mul(0.238081)).negate();
                const x = sqrt(max(qb.mul(qb).sub(qa.mul(qc).mul(4.0)), 0.0)).sub(qb).div(qa.mul(2.0));
                return mat3(...IN_INV).mul(max(x, 0.0)).mul(0.6).div(toneMappingExposure);
            };
            // mip-chain blurs of the input (half-res Gaussian pyramid). Passes run only while a reader is on.
            const mkBlur = (threshold, knee, active) => {
                if (!BloomNode) return null;
                const bn = new BloomNode(tex, 1.0, 0.0, threshold);
                bn.smoothWidth.value = knee;
                const ub = bn.updateBefore.bind(bn);
                bn.updateBefore = (frame) => (active() ? ub(frame) : undefined);
                return bn;
            };
            const blurBN = mkBlur(-1.0, 0.01, () => u.phosphor.value > 0.001 || u.watercolor.value > 0.001);
            const glowBN = mkBlur(0.55, 1.3, () => u.halation.value > 0.001);
            const mip = (bn, i, at) => bn['_textureNodeBlur' + i].sample(at).rgb;   // sigma ~4, 14, 39 px at 1080p
            // phosphor persistence: bright light fades over ~40 ms instead of vanishing (three's AfterImageNode, a
            // max(new, old * damp) feedback). Gated like the blurs; the first frame after the tube comes on starts
            // clean (damp 0), so no stale frame from the last time it was on can flash through.
            // A camera cut restarts it the same way: no ghost of the last shot.
            let persistAN = null;
            if (THREE.AfterImageNode) {
                const damp = uniform(Math.exp(-1 / (FPSV * 0.04)));
                persistAN = new THREE.AfterImageNode(tex, damp);
                const ub = persistAN.updateBefore.bind(persistAN);
                let was = false;
                persistAN.updateBefore = (frame) => {
                    const on = u.phosphor.value > 0.001;
                    if (on) { const d = damp.value; if (camJumped() || !was) damp.value = 0; ub(frame); damp.value = d; }
                    was = on;
                };
            }
            return Fn(() => {
                const res = vec2(W, H);
                const uv0 = uv().toVar();
                const fc = uv0.mul(res).toVar();                  // fragment coords (pixels)
                // --- pixel grid (C64 / Mac)
                const px = max(u.px, 1.0).toVar();
                const cell = vec2(px, px).div(res);
                const suv = mix(uv0, floor(uv0.div(cell)).add(0.5).mul(cell), step(1.5, px)).toVar();
                const pix = floor(fc.div(px)).toVar();
                // --- glitch: tear bands, split chroma
                const hb = hash(floor(uv0.y.mul(40.0)).add(floor(u.time.mul(20.0)).mul(131.0)));
                suv.addAssign(vec2(step(0.82, hb).mul(hb.sub(0.5)).mul(0.10).mul(u.glitch), 0.0));
                // --- halation: gate weave (the whole frame jitters in the film gate)
                If(u.halation.greaterThan(0.001), () => {
                    suv.addAssign(u.weave.mul(u.halation).div(res));
                });
                // --- phosphor: curved glass; the beam samples and holds each scanline's centre row
                const crtW = uv0.toVar();                         // position on the curved tube face
                const crtY = float(0).toVar();                    // offset from the scanline centre, -0.5..0.5
                const crtIn = float(1).toVar();                   // inside the rounded bezel
                If(u.phosphor.greaterThan(0.001), () => {
                    const c = uv0.mul(2.0).sub(1.0).toVar();
                    c.mulAssign(vec2(float(1.0).add(c.y.mul(c.y).mul(0.045).mul(u.phosphor)),
                        float(1.0).add(c.x.mul(c.x).mul(0.065).mul(u.phosphor))));
                    crtW.assign(c.mul(0.5).add(0.5));
                    const q = abs(crtW.sub(0.5)).mul(res);
                    const rad = 34.0 * S;
                    const sd = length(max(q.sub(res.mul(0.5)).add(rad), 0.0)).sub(rad);
                    crtIn.assign(float(1.0).sub(smoothstep(-1.5 * S, 0.5 * S, sd)));
                    pix.assign(floor(crtW.mul(res).div(px)));      // dithers and grain follow the curved pixel grid
                    const lp = max(px, 4.0 * S);                  // line pitch: the pixel grid's rows, else 4 px
                    const yl = crtW.y.mul(H).div(lp);
                    crtY.assign(fract(yl).sub(0.5));
                    const sx = mix(crtW.x, floor(crtW.x.div(cell.x)).add(0.5).mul(cell.x), step(1.5, px));
                    suv.assign(vec2(sx, floor(yl).add(0.5).mul(lp).div(H)));
                    suv.addAssign(vec2(step(0.82, hb).mul(hb.sub(0.5)).mul(0.10).mul(u.glitch), 0.0));
                });
                const ca = u.glitch.mul(0.006).add(u.riso.mul(0.0035));
                const base = tex.sample(suv).toVar();
                const col = mix(base.rgb, vec3(tex.sample(suv.add(vec2(ca, 0.0))).r, base.g, tex.sample(suv.sub(vec2(ca, 0.0))).b),
                    min(u.glitch.add(u.riso), 1.0)).toVar();
                // --- phosphor: the three guns converge a little off, more toward the sides of the tube
                If(u.phosphor.greaterThan(0.001), () => {
                    const cv = vec2(float(0.5).add(abs(crtW.x.sub(0.5)).mul(2.6)).mul(S).mul(u.phosphor).div(W), 0.0);
                    col.assign(vec3(tex.sample(suv.add(cv)).r, col.g, tex.sample(suv.sub(cv)).b));
                });

                // --- kuwahara (painterly): 4 quadrants, radius 3, least-variance mean
                If(u.kuwahara.greaterThan(0.001), () => {
                    const best = vec3(0).toVar();
                    const bestVar = float(1e9).toVar();
                    const R = 3;
                    for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
                        const sum = vec3(0).toVar();
                        const sum2 = float(0).toVar();
                        for (let j = 0; j <= R; j++) for (let i = 0; i <= R; i++) {
                            const c = tex.sample(uv0.add(vec2(sx * i * 2.6 * S, sy * j * 2.6 * S).div(res))).rgb;
                            sum.addAssign(c);
                            sum2.addAssign(dot(c, LUM).mul(dot(c, LUM)));
                        }
                        const n = (R + 1) * (R + 1);
                        const mean = sum.div(n);
                        const lm = dot(mean, LUM);
                        const v = sum2.div(n).sub(lm.mul(lm));
                        const better = step(v, bestVar);
                        best.assign(mix(best, mean, better));
                        bestVar.assign(min(bestVar, v));
                    }
                    col.assign(mix(col, best, u.kuwahara));
                });

                const lum = dot(col, LUM).toVar();
                const plum = sqrt(clamp(lum, 0.0, 1.0)).toVar();
                const thr = bayer4(pix).toVar();

                // --- single-hue looks
                const sepiaC = vec3(lum.mul(1.10), lum.mul(0.86), lum.mul(0.58));
                const decoK = smoothstep(0.08, 0.95, plum);
                const decoC = mix(vec3(0.03, 0.018, 0.01), vec3(1.05, 0.72, 0.30), decoK).mul(mix(0.6, 1.35, decoK));
                const bwC = vec3(lum, lum, lum);
                const vectorC = vec3(lum.mul(0.18), lum.mul(1.30), lum.mul(0.38));
                const vfdC = vec3(lum.mul(0.30), lum.mul(1.20), lum.mul(1.02));
                const amberC = vec3(lum.mul(1.30), lum.mul(0.70), lum.mul(0.10));
                const bit = step(thr, plum);
                const macC = vec3(bit, bit, bit).mul(0.92);
                // web-safe: 6 levels per channel (0,51,...,255) with ordered dither
                const q = floor(sqrt(clamp(col, 0.0, 1.0)).mul(5.0).add(thr)).div(5.0);
                const webC = q.mul(q);
                // C64 palette match
                const pc = sqrt(clamp(col, 0.0, 1.0)).add(thr.sub(0.5).mul(0.12)).toVar();
                const best = vec3(pal[0]).toVar();
                const bd = dot(pc.sub(pal[0]), pc.sub(pal[0])).toVar();
                for (let i = 1; i < pal.length; i++) {
                    const d = dot(pc.sub(pal[i]), pc.sub(pal[i]));
                    const better = step(d, bd);
                    best.assign(mix(best, pal[i], better));
                    bd.assign(min(bd, d));
                }
                const c64C = best.mul(best);
                // riso: two misregistered inks on paper (fluoro pink shadows, blue midtone halftone)
                const paper = vec3(0.93, 0.9, 0.84);
                const rot = vec2(fc.x.mul(0.866).sub(fc.y.mul(0.5)), fc.x.mul(0.5).add(fc.y.mul(0.866))).div(6.0 * S);
                const halft = length(fract(rot).sub(0.5));
                const mid = smoothstep(0.08, 0.5, plum).mul(float(1).sub(smoothstep(0.55, 0.95, plum)));
                const dotsA = step(halft, mid.mul(0.62));                       // pink halftone on the midtones
                const lumB = dot(tex.sample(uv0.add(vec2(0.004, -0.0028))).rgb, LUM);   // blue plate, misregistered
                const shadow = float(1).sub(smoothstep(0.12, 0.42, sqrt(clamp(lumB, 0.0, 1.0))));
                const dotsB = step(thr.mul(0.9), shadow);
                const risoC = paper.mul(mix(vec3(1), vec3(1.0, 0.36, 0.62), dotsA.mul(0.9)))
                    .mul(mix(vec3(1), vec3(0.08, 0.2, 0.62), dotsB.mul(0.92)));

                // --- halftone: newsprint / protest poster. The key (black) is LINE ART: the darkest shapes, strokes
                // and lettering print solid and sharp, unscreened. Under it, four plates, each its own rotated screen
                // and its own misregistration; dots from a cosine spot function (round -> checkerboard at 50% ->
                // holes); inks multiply as transmittances on newsprint, pressed a little unevenly.
                const halfC = vec3(0).toVar();
                If(u.halftone.greaterThan(0.001), () => {
                    const cellPx = 8.0 * S;
                    const plates = [   // [screen angle, misregistration px @1080p, CMYK channel]
                        [15, [1.6, -1.0], 0], [75, [-1.2, 0.8], 1], [0, [2.2, 1.3], 2], [45, [0.0, 0.0], 3]];
                    const trans = vec3(1.0).toVar();
                    const dMean = float(0).toVar();                                    // local tone (K plate's taps)
                    for (const [angDeg, [ox, oy], ch] of plates) {
                        const o = vec2(ox * S, oy * S).div(res);
                        const dq = vec2(0.24 * cellPx, 0.17 * cellPx).div(res);       // 2-tap prefilter across a cell
                        const cs = tex.sample(suv.add(o).add(dq)).rgb.add(tex.sample(suv.add(o).sub(dq)).rgb).mul(0.5);
                        const d = sqrt(clamp(toPrint(cs), 0.0, 1.0)).toVar();        // ~sRGB-encoded tone
                        const d2 = smoothstep(0.04, 0.96, d).mul(0.6).add(d.mul(d).mul(0.4)).toVar();  // poster snap
                        const k0 = float(1.0).sub(max(max(d2.r, d2.g), d2.b));
                        const k = k0.mul(smoothstep(0.08, 0.7, k0));                   // black comes in early
                        let a0;
                        if (ch === 3) a0 = k;
                        else {   // GCR, stabilized: under a near-full black no colour is laid down
                            const comp = [d2.r, d2.g, d2.b][ch];
                            a0 = clamp(float(1.0).sub(comp).sub(k).div(max(float(1.0).sub(k), 0.12)), 0.0, 1.0);
                        }
                        const a = a0.add(a0.mul(float(1.0).sub(a0)).mul(0.35));        // dot gain on soft stock
                        const ang = angDeg * Math.PI / 180, cA = Math.cos(ang), sA = Math.sin(ang);
                        const sq = vec2(fc.x.mul(cA).add(fc.y.mul(sA)), fc.y.mul(cA).sub(fc.x.mul(sA))).div(cellPx);
                        const f = fract(sq).sub(0.5);
                        const spot = float(0.5).add(cos(f.x.mul(6.2831853)).add(cos(f.y.mul(6.2831853))).mul(0.25));
                        const aa = clamp(fwidth(spot).mul(0.6), 0.004, 0.12);
                        const th = mix(aa.negate(), aa.add(1.0), float(1.0).sub(a));   // 0% = no ink, 100% = solid
                        const ink = smoothstep(th.sub(aa), th.add(aa), spot);
                        const press = vnoise(fc.div(64.0 * S).add(vec2(37.0 + ch * 71.0, 11.0 + ch * 23.0)), 90 + ch);
                        const T = V3(NEWS_INK[ch].map((v, j) => v / NEWS_PAPER[j]));
                        trans.mulAssign(mix(vec3(1.0), T, min(ink.mul(press.mul(0.16).add(0.86)), 1.0)));
                        if (ch === 3) dMean.assign(dot(d, LUM));
                    }
                    // the key: solid black wherever the sharp picture is darkest, and on thin dark detail (lettering,
                    // bars, outlines: darker than the few pixels around them)
                    const dk = sqrt(clamp(dot(toPrint(tex.sample(suv).rgb), LUM), 0.0, 1.0));
                    const keyA = max(float(1.0).sub(smoothstep(0.1, 0.19, dk)), smoothstep(0.1, 0.22, dMean.sub(dk)).mul(0.92));
                    trans.mulAssign(mix(vec3(1.0), V3(NEWS_INK[3].map((v, j) => v / NEWS_PAPER[j])), keyA));
                    const fib = vnoise(fc.div(1.4 * S).add(vec2(500.0, 300.0)), 7).sub(0.5).mul(0.05)
                        .add(vnoise(fc.div(6.0 * S).add(vec2(900.0, 100.0)), 8).sub(0.5).mul(0.06));
                    halfC.assign(fromDisp(clamp(V3(NEWS_PAPER).mul(trans).mul(fib.add(1.0)), 0.0, 1.0)));
                });

                // --- toon: storybook cel. Soft luminance bands (hue kept), ink wherever depth creases or jumps,
                // normals turn, or colour steps hard; lines thin out with distance so a far field stays painted.
                const toonC = vec3(0).toVar();
                If(u.toon.greaterThan(0.001), () => {
                    const zAt = (at) => (sceneDepth ? perspectiveDepthToViewZ(sceneDepth.sample(at).r, u.camNear, u.camFar).negate()
                        : float(1.0));
                    // the pen is heavier on what is near (her, the bicycle) and finer on the field behind
                    const r1 = mix(2.3 * S, 1.4 * S, smoothstep(2.5, 9.0, zAt(suv))).toVar();
                    const r2 = r1.mul(3.0);
                    const taps = [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]];
                    const Ds = [], Ps = [], Zs = [], Ns = [];
                    for (const [dx, dy] of taps) {
                        const at = suv.add(vec2(dx, dy).mul(r1).div(res));
                        const D = toPrint(tex.sample(at).rgb).toVar();
                        Ds.push(D);
                        Ps.push(sqrt(dot(D, LUM)));
                        Zs.push(zAt(at));
                        Ns.push(sceneNormal ? sceneNormal.sample(at) : vec3(0, 0, 1));
                    }
                    const zc = max(Zs[0], 1e-4);
                    // flatten small texture into the fill: depth-aware 5-tap mean
                    const sum = Ds[0].mul(2.0).toVar();
                    const wsum = float(2.0).toVar();
                    for (let i = 1; i < 5; i++) {
                        const w = float(1.0).sub(smoothstep(0.01, 0.04, abs(Zs[i].sub(zc)).div(zc)));
                        sum.addAssign(Ds[i].mul(w));
                        wsum.addAssign(w);
                    }
                    const Dm = sum.div(wsum).toVar();
                    // bands on perceptual value: four soft steps, shadows never fall to black
                    const Lp = sqrt(max(dot(Dm, LUM), 1e-5));
                    const lv = [0.3, 0.52, 0.73, 0.93], tv = [0.36, 0.6, 0.81], sw = 0.035;
                    const Lq = float(lv[0]).toVar();
                    for (let i = 0; i < 3; i++) Lq.addAssign(smoothstep(tv[i] - sw, tv[i] + sw, Lp).mul(lv[i + 1] - lv[i]));
                    Lq.assign(mix(Lp, Lq, smoothstep(0.07, 0.24, Lp)));                 // true darks stay dark (silhouettes)
                    Lq.assign(mix(Lq, Lp, smoothstep(150.0, 1500.0, zc)));               // the sky keeps its painted gradient
                    const scale = Lq.mul(Lq).div(Lp.mul(Lp));
                    const grey = dot(Dm, LUM);
                    const cel = mix(vec3(grey), Dm, 1.12).mul(scale).toVar();          // hue kept, a little chroma
                    const shade = float(1.0).sub(smoothstep(0.3, 0.55, Lq));           // cool the shadow band
                    cel.mulAssign(mix(vec3(1.02, 1.0, 0.96), vec3(0.88, 0.9, 1.08), shade));
                    // ink. Lines sit on the NEAR side of a silhouette and only on shapes wider than ~r2: a petal, stem
                    // or bulb narrower than that (both sides farther at r2) is left to the fill, so a field of daisies
                    // stays painted while she and the bicycle are drawn. Creases come from normals on continuous
                    // depth; colour lines only from steps (a light ridge on dark, like a petal, is not an edge).
                    const eD = float(0).toVar(), thin = float(0).toVar(), eC = float(0).toVar(), cont = float(1).toVar();
                    for (const [i, j, ax] of [[1, 2, [1, 0]], [3, 4, [0, 1]]]) {
                        const fa = Zs[i].sub(zc).div(zc), fb = Zs[j].sub(zc).div(zc);
                        const za = zAt(suv.add(vec2(ax[0], ax[1]).mul(r2).div(res)));
                        const zb = zAt(suv.sub(vec2(ax[0], ax[1]).mul(r2).div(res)));
                        const th = smoothstep(0.03, 0.12, min(za.sub(zc), zb.sub(zc)).div(zc));
                        eD.assign(max(eD, smoothstep(0.03, 0.12, max(fa, fb)).mul(float(1.0).sub(th))));
                        thin.assign(max(thin, th));
                        cont.mulAssign(float(1.0).sub(smoothstep(0.01, 0.03, max(abs(fa), abs(fb)))));
                        const a = Ps[i].sub(Ps[0]), b = Ps[j].sub(Ps[0]);
                        const ridge = step(a, 0.0).mul(step(b, 0.0)).mul(min(abs(a), abs(b)));
                        eC.assign(max(eC, max(abs(a), abs(b)).sub(ridge)));
                    }
                    const nd = float(0).toVar();
                    for (let i = 1; i < 5; i++) nd.addAssign(float(1.0).sub(dot(Ns[0], Ns[i])));
                    const eN = sceneNormal ? smoothstep(0.35, 0.9, nd).mul(cont).mul(0.8).mul(float(1.0).sub(smoothstep(3.5, 11.0, zc)))
                        : float(0.0);
                    const eCol = smoothstep(0.2, 0.4, eC).mul(0.9).mul(float(1.0).sub(smoothstep(3.0, 10.0, zc)));
                    const fade = float(1.0).sub(smoothstep(5.0, 30.0, zc).mul(0.7));    // the far field: a lighter pen
                    const inkA = clamp(max(max(eD, eN), eCol).mul(float(1.0).sub(thin.mul(0.85))).mul(fade), 0.0, 1.0);
                    // printed on a warm storybook page, with a whisper of paper grain
                    const grain = vnoise(fc.div(1.8 * S).add(vec2(700.0, 900.0)), 61).sub(0.5).mul(0.035);
                    const page = mix(vec3(1.0), V3(TOON_PAGE), 0.7).mul(grain.add(1.0));
                    toonC.assign(fromDisp(clamp(mix(cel.mul(page), V3(TOON_INK), inkA), 0.0, 1.0)));
                });

                // --- watercolor: wet paper. Washes wander a few px, some areas bleed wet-in-wet, pigment piles
                // up on the dark side of every wash edge and settles into the paper tooth (Bousseau et al. 2006:
                // c' = c - (c - c^2)(d - 1)); the lightest washes let the paper grain show through.
                const waterC = vec3(0).toVar();
                If(u.watercolor.greaterThan(0.001), () => {
                    const pp = fc.div(S).add(vec2(311.0, 173.0)).toVar();         // paper coords (1080p px)
                    const wob = vec2(vnoise(pp.div(38.0), 11), vnoise(pp.div(38.0), 29)).sub(0.5).mul(5.0 * S).div(res);
                    const uw = suv.add(wob).toVar();
                    const c0 = toPrint(tex.sample(uw).rgb).toVar();
                    const b0 = (blurBN ? toPrint(mip(blurBN, 0, uw)) : c0).toVar();
                    const b1 = (blurBN ? toPrint(mip(blurBN, 1, uw)) : c0).toVar();
                    const P = (c) => sqrt(max(dot(c, LUM), 1e-5));
                    // a wash, not a photograph: low-contrast texture melts into the local mean, strong edges stay
                    const flat = float(1.0).sub(smoothstep(0.035, 0.13, abs(P(c0).sub(P(b0)))));
                    const C = mix(c0, b0, flat.mul(0.85)).toVar();
                    // wet-in-wet: in the wet patches colour (not value) runs into its neighbours
                    const wet = smoothstep(0.4, 0.78, vnoise(pp.div(90.0), 41)).mul(0.7);
                    const lc = dot(C, LUM), l1 = dot(b1, LUM);
                    C.assign(max(C.add(b1.sub(l1).sub(C.sub(lc)).mul(wet)), 0.0));
                    // glazes: value settles into five soft layers on wobbling thresholds; pigment piles up in a
                    // thin rim on the darker side of every layer's edge (and of every shape against a lighter one)
                    const v = P(C);
                    const t0 = v.mul(4.0);
                    const wAmp = min(fwidth(t0).mul(45.0), 0.3);       // wobble only where the value moves: no islands
                    const tq = t0.add(vnoise(pp.div(55.0), 23).sub(0.5).mul(wAmp)).toVar();
                    const fq = fract(tq);
                    const vq = floor(tq).add(smoothstep(0.4, 0.6, fq)).div(4.0);
                    const vg = mix(v, vq, 0.55);
                    C.mulAssign(vg.mul(vg).div(max(v.mul(v), 1e-5)));
                    const fw = max(fwidth(tq), 1e-3);
                    const rim = smoothstep(0.5 - 0.02, 0.5, fq.add(fw.mul(2.2))).mul(float(1.0).sub(smoothstep(0.5, 0.52, fq)));
                    const Lb = P(b1);
                    const edge = clamp(Lb.sub(v).mul(3.0), 0.0, 1.0);
                    // pigment density (Bousseau et al. 2006): c' = c - (c - c^2)(d - 1)
                    const hp = vnoise(pp.div(2.3), 3).mul(0.6).add(vnoise(pp.div(6.5), 7).mul(0.4));   // paper height
                    const turb = vnoise(pp.div(130.0), 13).mul(0.65).add(vnoise(pp.div(34.0), 17).mul(0.35));
                    const pig = float(1.0).sub(v);
                    const dens = float(1.0).add(rim.mul(0.38)).add(edge.mul(0.5)).add(turb.sub(0.5).mul(0.5))
                        .add(float(0.55).sub(hp).mul(1.25).mul(pig));
                    const cp = sqrt(clamp(C, 0.0, 1.0)).toVar();
                    const cm = clamp(cp.sub(cp.sub(cp.mul(cp)).mul(dens.sub(1.0))), 0.0, 1.0).toVar();
                    // transparent pigment: the page glows through, and the tooth shows in the palest washes
                    cm.assign(mix(cm, vec3(1.0), smoothstep(0.78, 0.93, hp).mul(smoothstep(0.72, 0.96, v)).mul(0.3)));
                    const out = V3(WC_PAPER).mul(max(cm.mul(cm), 0.04))
                        .mul(hp.sub(0.5).mul(float(0.07).add(pig.mul(0.28))).add(1.0));
                    waterC.assign(fromDisp(clamp(out, 0.0, 1.0)));
                });

                // --- blend the colour looks
                const ws = u.sepia.add(u.deco).add(u.bw).add(u.vector).add(u.vfd).add(u.amber).add(u.mac)
                    .add(u.c64).add(u.websafe).add(u.riso).add(u.halftone).add(u.toon).add(u.watercolor).toVar();
                const norm = max(ws, 1.0);
                const outc = col.mul(clamp(float(1.0).sub(ws), 0.0, 1.0)).toVar();
                outc.addAssign(sepiaC.mul(u.sepia.div(norm)));
                outc.addAssign(decoC.mul(u.deco.div(norm)));
                outc.addAssign(bwC.mul(u.bw.div(norm)));
                outc.addAssign(vectorC.mul(u.vector.div(norm)));
                outc.addAssign(vfdC.mul(u.vfd.div(norm)));
                outc.addAssign(amberC.mul(u.amber.div(norm)));
                outc.addAssign(macC.mul(u.mac.div(norm)));
                outc.addAssign(c64C.mul(u.c64.div(norm)));
                outc.addAssign(webC.mul(u.websafe.div(norm)));
                outc.addAssign(risoC.mul(u.riso.div(norm)));
                outc.addAssign(halfC.mul(u.halftone.div(norm)));
                outc.addAssign(toonC.mul(u.toon.div(norm)));
                outc.addAssign(waterC.mul(u.watercolor.div(norm)));

                // --- deco sunburst: rays fanning from low centre (also, a daisy)
                If(u.deco.greaterThan(0.001), () => {
                    const d = uv0.sub(vec2(0.5, -0.15)).mul(vec2(W / H, 1));
                    const ang = atan(d.y, d.x);
                    const rays = step(0.5, fract(ang.mul(24.0 / 6.2832)));
                    outc.mulAssign(mix(float(1), mix(0.78, 1.12, rays), u.deco.mul(0.5)));
                });

                // --- C64 raster bars behind the subject (the demoscene's copper bars fill the dark)
                If(u.raster.greaterThan(0.001), () => {
                    const bars = vec3(0).toVar();
                    const ramp = [vec3(0.0, 0.0, 0.67), vec3(0.0, 0.53, 1.0), vec3(0.67, 1.0, 0.93), vec3(1, 1, 1)];
                    for (let i = 0; i < 5; i++) {
                        const cy = float(0.5).add(float(0.36).mul(THREE.sin(u.time.mul(1.25).add(i * 0.62))));
                        const k = exp(uv0.y.sub(cy).div(0.032).mul(uv0.y.sub(cy).div(0.032)).negate());
                        const band = floor(k.mul(3.99));
                        const c = mix(mix(ramp[0], ramp[1], step(1.0, band)), mix(ramp[2], ramp[3], step(3.0, band)), step(2.0, band));
                        bars.assign(max(bars, c.mul(step(0.05, k))));
                    }
                    const dark = float(1).sub(smoothstep(0.015, 0.07, lum));
                    outc.assign(mix(outc, bars.mul(bars), dark.mul(u.raster)));
                });

                // --- neural feature map: false-colour Sobel over a darkened, posterized field
                If(u.feature.greaterThan(0.001), () => {
                    const o = vec2(1.5 * S, 1.5 * S).div(res);
                    const L = (dx, dy) => dot(tex.sample(uv0.add(vec2(dx, dy).mul(o))).rgb, LUM);
                    const gx = L(1, -1).add(L(1, 0).mul(2)).add(L(1, 1)).sub(L(-1, -1)).sub(L(-1, 0).mul(2)).sub(L(-1, 1));
                    const gy = L(-1, 1).add(L(0, 1).mul(2)).add(L(1, 1)).sub(L(-1, -1)).sub(L(0, -1).mul(2)).sub(L(1, -1));
                    const mag = clamp(sqrt(gx.mul(gx).add(gy.mul(gy))).mul(3.0), 0.0, 1.0);
                    const a = atan(gy, gx).div(6.2832).add(0.5);
                    const hueC = vec3(abs(a.mul(6).sub(3)).sub(1), float(2).sub(abs(a.mul(6).sub(2))), float(2).sub(abs(a.mul(6).sub(4))));
                    const edge = clamp(hueC, 0.0, 1.0).mul(mag).mul(2.2);
                    const tile = step(0.97, max(fract(fc.x.div(64 * S)), fract(fc.y.div(64 * S))));
                    const field = floor(plum.mul(4.0)).div(4.0).mul(0.22).mul(vec3(0.5, 0.35, 0.9));
                    const feat = field.add(edge).add(vec3(0.1, 0.08, 0.2).mul(tile));
                    outc.assign(mix(outc, feat, u.feature));
                });

                // --- line printer: glyph per 8x14 cell, black ink on green-bar fanfold paper
                If(u.ascii.greaterThan(0.001), () => {
                    const cs = vec2(12.0 * S, 20.0 * S);
                    const ci = floor(fc.div(cs));
                    const cl = fract(fc.div(cs));
                    const cc = ci.add(0.5).mul(cs).div(res);
                    const L2 = dot(tex.sample(cc).rgb, LUM);
                    const gi = floor(clamp(float(1).sub(sqrt(clamp(L2, 0.0, 1.0)).mul(1.1)), 0.0, 0.999).mul(RAMP.length));
                    const ink = texture(atlas, vec2(gi.add(cl.x).div(RAMP.length), float(1).sub(cl.y))).r;
                    const barRow = mod(floor(ci.y.div(3.0)), 2.0);
                    const pap = mix(vec3(0.95, 0.95, 0.9), vec3(0.8, 0.9, 0.78), barRow);
                    const edgeHoles = step(fc.x, 22.0 * S).add(step(res.x.sub(22.0 * S), fc.x));
                    const hole = step(length(vec2(mod(fc.x, 22.0 * S), mod(fc.y, 26.0 * S)).sub(vec2(11.0 * S, 13.0 * S))), 5.0 * S)
                        .mul(clamp(edgeHoles, 0.0, 1.0));
                    const printed = mix(pap, vec3(0.06, 0.06, 0.09), ink.mul(float(1).sub(hole)));
                    outc.assign(mix(outc, mix(printed, vec3(0.02), hole), u.ascii));
                });

                // --- halation: candle-lit film. Highlights bleed a red-orange halo (light through the emulsion,
                // back off the base, into the red layer); warm print, lifted blacks, fine colour grain.
                If(u.halation.greaterThan(0.001), () => {
                    // the lens and emulsion are softer than a render: a quarter of a 1 px cross blur
                    const px1 = vec2(S, S).div(res);
                    const soft = tex.sample(suv.add(vec2(px1.x, 0.0))).rgb.add(tex.sample(suv.sub(vec2(px1.x, 0.0))).rgb)
                        .add(tex.sample(suv.add(vec2(0.0, px1.y))).rgb).add(tex.sample(suv.sub(vec2(0.0, px1.y))).rgb).mul(0.25);
                    const film = mix(outc, soft, 0.3).toVar();
                    if (glowBN) {   // orange next to the source, deep red further out (CineStill 800T without remjet)
                        const h0 = dot(mip(glowBN, 0, suv), LUM), h1 = dot(mip(glowBN, 1, suv), LUM);
                        const hc = dot(glowBN.getTextureNode().sample(suv).rgb, LUM);
                        film.addAssign(vec3(1.0, 0.36, 0.1).mul(h0.mul(0.55)).add(vec3(1.0, 0.13, 0.035).mul(h1.mul(1.5)))
                            .add(vec3(1.0, 0.2, 0.06).mul(hc.mul(0.06))));
                    }
                    // print: warm highlights, cool lifted shadows (the base and a little fog)
                    const fl0 = dot(film, LUM);
                    film.assign(film.mul(vec3(1.05, 1.0, 0.9)).add(mix(vec3(0.0022, 0.0042, 0.0052), vec3(0.004, 0.003, 0.0024),
                        smoothstep(0.0, 0.08, fl0))));
                    // grain: fine, clumped over ~2 px, mostly luma with some colour, strongest in the midtones
                    const fr = u.frame.add(17.0);
                    const gp = fc.div(1.15 * S).add(vec2(100.0, 100.0));
                    const g = vec3(vnoise(gp.add(fr.mul(3.1)), 71), vnoise(gp.add(fr.mul(5.3)), 72), vnoise(gp.add(fr.mul(7.7)), 73))
                        .sub(0.5).mul(0.7).add(vec3(hash3(fc.x, fc.y, fr.mul(3.0))).sub(0.5).mul(0.6));
                    const gm = mix(vec3(dot(g, vec3(0.3333))), g, 0.4);
                    const fl = sqrt(clamp(dot(film, LUM), 0.0, 1.0));
                    const midW = smoothstep(0.02, 0.25, fl).mul(float(1.0).sub(smoothstep(0.55, 1.0, fl)).mul(0.65).add(0.35));
                    film.mulAssign(gm.mul(0.34).mul(midW).add(1.0));
                    outc.assign(mix(outc, film, u.halation));
                });

                // --- phosphor: the picture on a CRT. Each scanline is a beam whose width swells with brightness,
                // seen through an RGB aperture grille (2 px stripes at 1080p), with glass glow and the curved,
                // rounded tube face. Rides on top of any colour look (a C64 palette on a TV, say).
                If(u.phosphor.greaterThan(0.001), () => {
                    const Lr = sqrt(clamp(dot(outc, LUM), 0.0, 1.0));
                    const sig = mix(0.17, 0.42, Lr);
                    const beam = exp(crtY.mul(crtY).div(sig.mul(sig).mul(-2.0)));
                    const bnorm = clamp(sig.mul(2.5066), 0.42, 1.0);
                    const P = 6.0 * Math.max(S, 1);
                    const ph = fract(fc.x.div(P));
                    const stripe = (c0) => float(1.0).sub(smoothstep(0.1, 0.2, abs(fract(ph.sub(c0).add(0.5)).sub(0.5))));
                    const mask = mix(vec3(0.42), vec3(1.5), vec3(stripe(1 / 6), stripe(0.5), stripe(5 / 6)));
                    const glow = vec3(0).toVar();
                    if (blurBN) {   // light scattered in the glass: not masked, not scanned
                        glow.assign(mip(blurBN, 1, crtW).mul(0.55).add(mip(blurBN, 2, crtW).mul(0.35))
                            .add(blurBN.getTextureNode().sample(crtW).rgb.mul(0.1 / 3.0)));
                    }
                    // a faint hum bar rolling up the picture
                    const hum = float(1.0).add(smoothstep(0.0, 0.5, fract(crtW.y.mul(0.8).sub(u.time.mul(0.09))))
                        .mul(float(1.0).sub(smoothstep(0.5, 1.0, fract(crtW.y.mul(0.8).sub(u.time.mul(0.09)))))).mul(0.045));
                    const sat = mix(vec3(dot(outc, LUM)), outc, 1.1).toVar();
                    if (persistAN) {   // what was bright a moment ago still glows (scanned + masked like the picture)
                        const held = persistAN.getTextureNode().sample(suv).rgb;
                        sat.addAssign(max(min(held, vec3(1.0)).sub(tex.sample(suv).rgb), 0.0).mul(0.5));
                    }
                    const tube = max(sat, 0.0).mul(beam.div(bnorm)).mul(mask).mul(hum).mul(1.22).add(glow.mul(0.24))
                        .add(vec3(0.0026, 0.0034, 0.003)).toVar();                       // the glass is never black
                    const e = crtW.x.mul(crtW.y).mul(float(1.0).sub(crtW.x)).mul(float(1.0).sub(crtW.y)).mul(16.0);
                    tube.mulAssign(pow(clamp(e, 0.0, 1.0), 0.22).mul(crtIn));
                    outc.assign(mix(outc, tube, u.phosphor));
                });

                // --- film layers
                const seed = pix.x.add(pix.y.mul(4099.0)).add(u.frame.mul(7919.0));
                outc.mulAssign(float(1.0).add(hash(seed).sub(0.5).mul(u.grain.add(u.riso.mul(0.6))).mul(0.45)));
                outc.mulAssign(float(1.0).add(hash(u.frame.mul(13.0).add(7.0)).sub(0.5).mul(u.flicker).mul(0.22)));
                const sl = abs(fract(uv0.y.mul(H).mul(0.5)).sub(0.5)).mul(2.0);
                outc.mulAssign(float(1.0).sub(u.scan.mul(0.38).mul(sl)));
                const r = length(uv0.sub(0.5)).mul(1.35);
                outc.mulAssign(mix(float(1.0), float(1.0).sub(smoothstep(0.35, 1.05, r)), u.vignette));
                return vec4(outc, base.a);
            })();
        };
        globalThis._autoEnhanceColorHook = hook;
        // gate weave: a slow wander plus a jolt per 24 fps film frame (deterministic in t)
        const jolt = (n) => { let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b); x ^= x >>> 13; x = Math.imul(x, 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296 - 0.5; };
        return {
            uniforms: u,
            update(t) {
                u.time.value = t; u.frame.value = Math.floor(t * FPSV + 1e-6);
                const ff = Math.floor(t * 24);
                u.weave.value.set(S * (0.42 * Math.sin(t * 1.9 + 0.3) + 0.22 * Math.sin(t * 5.3 + 1.1) + 0.45 * jolt(ff)),
                    S * (0.55 * Math.sin(t * 1.3 + 2.0) + 0.3 * Math.sin(t * 4.1) + 0.6 * jolt(ff + 7919)));
                if (camera) { u.camNear.value = camera.near; u.camFar.value = camera.far; }
            },
        };
    });
}

// Named era presets: weights that together make each era's look.
export const ERA_LOOKS = {
    clean: {},
    voder1939: { deco: 0.85, sepia: 0.15, grain: 0.7, flicker: 0.5, vignette: 0.8 },
    bell1961: { bw: 1, grain: 0.5, flicker: 0.35, vignette: 0.6, scan: 0.15 },
    printer1961: { ascii: 1 },
    eliza1966: { bw: 0.6, sepia: 0.4, grain: 0.3, vignette: 0.4 },
    vector: { vector: 1, scan: 0.5, vignette: 0.5 },
    vfd1978: { vfd: 0.85, vignette: 0.4 },
    c64_1982: { c64: 1, raster: 1, px: 4, scan: 0.25 },
    mac1984: { mac: 1, px: 3 },
    amber1984: { amber: 1, scan: 0.45, vignette: 0.45 },
    web2001: { websafe: 1, px: 2 },
    neural2016: { feature: 1 },
    glitch: { glitch: 1 },
    zine: { riso: 1 },
    painterly: { kuwahara: 1, vignette: 0.35 },
    // print, paint, film and screen looks
    poster: { halftone: 1, vignette: 0.2 },                // a CMYK protest poster / newsprint (daylit scenes)
    poster_night: { halftone: 1, lift: 1.6, vignette: 0.2 }, // the same for a night scene (lift brightens before printing)
    crt: { phosphor: 1 },                                  // any picture on a curved CRT
    crt_8bit: { c64: 1, raster: 1, px: 4, phosphor: 1 },   // the 8-bit palette and raster bars on a TV tube
    storybook: { toon: 1, vignette: 0.15 },                // cel bands + ink lines: a storybook plate
    candle_film: { halation: 1, vignette: 0.55 },          // candle-lit film: halation, gate weave, grain
    watercolor: { watercolor: 1, vignette: 0.2 },          // wet-paper watercolour (daylit scenes)
    watercolor_night: { watercolor: 1, lift: 1.1, vignette: 0.2 }, // the same for a night scene
};

const KEYS_ALL = ['sepia', 'deco', 'bw', 'ascii', 'vector', 'vfd', 'c64', 'raster', 'mac', 'amber', 'websafe', 'feature',
    'glitch', 'riso', 'kuwahara', 'grain', 'flicker', 'scan', 'vignette',
    'halftone', 'phosphor', 'toon', 'halation', 'watercolor', 'lift'];

// Crossfade between two named looks (s = 0..1, smoothstepped). The pixel grid snaps at the midpoint.
export function applyLook(U, from, to, s) {
    const e = s * s * (3 - 2 * s);
    for (const k of KEYS_ALL) U[k].value = (from[k] ?? 0) * (1 - e) + (to[k] ?? 0) * e;
    U.px.value = e < 0.5 ? (from.px ?? 1) : (to.px ?? 1);
}
