// effects_tsl/aeropittura.js — the futurist post pass from the UNKNOWN FORCE music video (2026-10): the frame repainted as a
// FUTURIST painting of a DARK CYBERPUNK night. One registry effect, 'aeropittura', with a weight per ingredient and
// one master `force`.
//
//   // the engine loads this with the other effects_tsl/ helpers and registers it; a scene just asks for it:
//   globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'aeropittura',
//                                                opts: { aeropittura: { layer: 'under' } } });   // the HUD stays crisp
//   const A = AeropitturaFX, U = _fx.uniforms;
//   // per frame:  A.applyLook(U, A.LOOKS.storm, 1);         // or applyLook(U, from, force, to, s) to crossfade looks
//   //             A.setPlanes(U, A.PLANES.balla_sun);       // the plane family (change it on cuts)
//   //             U.focal.value.set(x, y);                  // uv, y DOWN; always finite (see HAZARD)
//   //             U.spare.value.set(x, y, r);               // a face kept readable (uv, y down; r in frame heights)
//   //             await _fx.update(t);  then render
//   // on a camera cut: U.cut()  (the time echoes restart from the new shot)
//
// Guide: AGENTS.md ("Aeropittura"). globalThis.AeropitturaFX: applyTo (the registry calls it), LOOKS (off · hush · argue ·
// storm), PLANES (balla_sun · revolt · race_sun · iridescent · dive · quiet), applyLook(U, look, force, other, s),
// setPlanes(U, family), RAMP (the palette, dark to light).
// HAZARD: a non-finite `focal` (a point projected from behind the camera, a NaN handed back by a set) blacks out the
// WHOLE frame: the planes' slip is hash(id) × weight, and 0 × NaN = NaN. Check Number.isFinite before writing it.
// The HDR input is sanitized for the same reason (one Inf/NaN pixel would spread through the halos' blur pyramid).
// Cost: about 6–8 ms per frame at 1920×1080 at `storm` (RTX 5090 Laptop GPU).
//
// WHAT MAKES IT FUTURIST (the paintings it was tuned against):
//  - Divisionist brushwork (Boccioni's "The City Rises", early Balla): the picture is rebuilt from separate, oriented
//    STROKES of paint, each one colour sampled from the scene and pushed warmer/cooler, a few toward the complement,
//    so colours mix in the eye. Two layers: broad strokes over the flats, fine strokes where there is detail.
//  - Balla's "Street Light" (1909): every bright light is surrounded by radiating V-shaped strokes of its own colour
//    and its complement. On a neon night this is the whole sky.
//  - Interpenetrating planes (Balla's sun cones in "Mercury Passing Before the Sun", Russolo's wedges in "The
//    Revolt", Balla's "Iridescent Interpenetrations"): the frame is cut into planes that slip, darken or glow.
//  - Simultaneity (Balla's "Dynamism of a Dog on a Leash"): moving things repeat; R/G/B show different instants.
//  - Crali's aeropittura: a vortex warp around the focal point for the dives.
//  - Carrà's dark grounds: the palette keeps the night black, with neon as accents.
//
// INGREDIENTS (0..1, all multiplied by `force`):
//   echo     simultaneity: R shows the frame 2·gap ago, G 1·gap, B now (gap ≈ 50 ms); still things are untouched.
//   multi    Balla's repetition: up to four older copies of anything that moves, fading.
//   strokes  the divisionist stroke layers.
//   under    the anisotropic-Kuwahara underpainting the strokes are laid on (Kyprianidis et al. 2009).
//   halo     Balla's street-light V-strokes around bright lights.
//   planes   the plane families (choose with setPlanes): slips, shadow planes, neon glazes, painted plane edges.
//   lines    lines of force: drags along the contours of moving things + sparse speed lines toward the focal point.
//   palette  the dark-cyberpunk gradient map (saturated light keeps its own hue).
//   canvas   canvas weave + VHS scanline + grain.
//   crisp    how much fine detail (text, eyes, the mouth line) is handed back sharp.
// UNIFORMS: focal (uv, y DOWN), spin (rad), swirl (rad at the centre) + swirlR (frame heights): Crali's vortex,
// spare (x, y, r: a face kept readable), brushAngle (rad: stroke direction where the picture has no contours —
// Futurist diagonals by default), chevDir (vec2: the wedges' direction), plane families rays/rings/diag/chev/tri.
// The hook receives LINEAR scene-referred HDR; everything paints in DISPLAY space (toDisp = the renderer's own ACES,
// fromDisp its exact inverse, as in DAISY's era_fx), so the palette lands on screen as authored.

(function () {
    'use strict';
    if (!globalThis.THREE) { console.warn('[aeropittura] THREE global not present — skipping load'); return; }
    let _factory = null;

    const ACES_IN = [0.59719, 0.35458, 0.04823, 0.07600, 0.90834, 0.01566, 0.02840, 0.13383, 0.83777];
    const ACES_OUT = [1.60475, -0.53108, -0.07367, -0.10208, 1.10813, -0.00605, -0.00327, -0.07276, 1.07602];
    function inv3(m) {
        const [a, b, c, d, e, f, g, h, i] = m;
        const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
        const det = a * A + b * B + c * C;
        return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
            B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
            C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
    }

    // The palette ramp, dark to light (authored sRGB). DARK CYBERPUNK (Skye, 10-02: "more dark cyberpunk rather than
    // outrun"): wet black, teal-black, petrol teal, bruised violet, neon magenta, sodium orange, cold white. Most of
    // the range stays dark; neon is an accent, not the room.
    const RAMP = ['#020307', '#06141d', '#0d3644', '#33204f', '#b81f66', '#ff8a3d', '#e9f3f1'];

    const DIAG = [[18, 0.22], [-34, -0.18], [71, 0.31], [-62, 0.36], [8, -0.41]];   // [angle deg, offset] long diagonals
    const RAYS = 9;

    const LOOKS = {
        off: { echo: 0, multi: 0, strokes: 0, under: 0, halo: 0, planes: 0, lines: 0, palette: 0, canvas: 0, crisp: 0 },
        // the floor of the film: still a painting (there is no clean image under the paint), just a quiet one
        hush: { echo: 0.1, multi: 0, strokes: 0.6, under: 0.7, halo: 0.4, planes: 0.08, lines: 0.05, palette: 0.4, canvas: 0.55, crisp: 0.85 },
        argue: { echo: 0.5, multi: 0.25, strokes: 0.9, under: 0.85, halo: 0.75, planes: 0.55, lines: 0.4, palette: 0.6, canvas: 0.6, crisp: 0.7 },
        storm: { echo: 1, multi: 0.85, strokes: 1, under: 1, halo: 1, planes: 1, lines: 1, palette: 0.7, canvas: 0.7, crisp: 0.5 },
    };
    const KEYS = Object.keys(LOOKS.off);

    // plane families (each 0/1-ish; the planes' edges fade with the weight, their ids switch at 0.5 — change on cuts)
    const PLANES = {
        balla_sun: { rays: 1, rings: 1, diag: 0.6, chev: 0, tri: 0 },    // "Mercury Passing Before the Sun": the hole
        revolt: { rays: 0, rings: 0, diag: 0.5, chev: 1, tri: 0 },       // Russolo's "The Revolt" wedges
        race_sun: { rays: 1, rings: 0, diag: 0, chev: 1, tri: 0 },       // the race: the sun's rays from its idol + the wedges
        iridescent: { rays: 0, rings: 0, diag: 0, chev: 0, tri: 1 },     // Balla's interpenetrations: the corridor
        dive: { rays: 1, rings: 0, diag: 1, chev: 0, tri: 0 },           // Crali's dive
        quiet: { rays: 0, rings: 0, diag: 0.6, chev: 0, tri: 0 },        // a few long diagonals
    };
    const PKEYS = Object.keys(PLANES.balla_sun);

    function applyLook(U, look, force = 1, other = null, s = 0) {
        for (const k of KEYS) {
            const a = look[k] ?? 0, b = other ? (other[k] ?? 0) : a;
            U[k].value = a + (b - a) * s;
        }
        U.force.value = force;
    }
    function setPlanes(U, fam) { for (const k of PKEYS) U[k].value = fam[k] ?? 0; }

    async function registerAeropittura() {
        const THREE = globalThis.THREE;
        const W = globalThis.WIDTH || 1920, H = globalThis.HEIGHT || 1080;
        const FPSV = globalThis.FPS || 30;
        const W3 = await import('npm:three@0.184.0/webgpu');
        const T = await import('npm:three@0.184.0/tsl');
        const { RenderTarget, QuadMesh, NodeMaterial, RendererUtils, TempNode, NodeUpdateType, Vector2, Vector3 } = W3;
        let BloomNode = null;   // three's mip-chain Gaussian, used as the light field for the street-light halos
        try { ({ default: BloomNode } = await import('npm:three@0.184.0/examples/jsm/tsl/display/BloomNode.js')); }
        catch (e) { console.log('[aeropittura] BloomNode import failed (halos off): ' + e); }

        // ---- the history ring: the last N frames of the input, for simultaneity and Balla's repetitions
        const GAP = Math.max(1, Math.round(FPSV * 0.05));       // frames between echoes (3 at 60 fps, 2 at 30)
        const N = 4 * GAP + 1;
        const quad = new QuadMesh();
        const size = new Vector2();
        let rstate;
        class HistoryNode extends TempNode {
            static get type() { return 'UFHistoryNode'; }
            constructor(textureNode) {
                super('vec4');
                this.textureNode = textureNode;
                this.rts = Array.from({ length: N }, (_, i) => {
                    const rt = new RenderTarget(1, 1, { depthBuffer: false });
                    rt.texture.name = 'UFHistory.' + i;
                    return rt;
                });
                this.head = 0;
                this.fresh = true;            // first frame (or a cut): fill every slot with the current frame
                this.echoes = [];
                this.mat = null;
                this.updateBeforeType = NodeUpdateType.FRAME;
            }
            echo(k) {
                const n = T.passTexture(this, this.rts[0].texture);
                this.echoes.push([k, n]);
                return n;
            }
            updateBefore(frame) {
                const { renderer } = frame;
                rstate = RendererUtils.resetRendererState(renderer, rstate);
                renderer.getDrawingBufferSize(size);
                const type = this.textureNode.value.type;
                for (const rt of this.rts) { rt.texture.type = type; rt.setSize(size.x, size.y); }
                quad.material = this.mat;
                this.head = (this.head + 1) % N;
                const slots = this.fresh ? this.rts : [this.rts[this.head]];
                for (const rt of slots) { renderer.setRenderTarget(rt); quad.render(renderer); }
                this.fresh = false;
                for (const [k, n] of this.echoes) n.value = this.rts[(this.head - k + N * 4) % N].texture;
                RendererUtils.restoreRendererState(renderer, rstate);
            }
            setup(builder) {
                this.mat = this.mat || new NodeMaterial();
                this.mat.name = 'UFHistory';
                this.mat.fragmentNode = this.textureNode.sample(T.uv());
                builder.getNodeProperties(this).textureNode = this.textureNode;
                return this.textureNode;
            }
        }

        _factory = (({ opts = {} } = {}) => {
            const { uniform, Fn, If, Loop, vec2, vec3, vec4, float, int, uv, floor, fract, mix, step, smoothstep, dot,
                sqrt, max, min, clamp, hash, length, abs, exp, atan, cos, sin, normalize, pow, uint, mat3, log,
                convertToTexture, toneMappingExposure, acesFilmicToneMapping } = T;
            const u = {
                force: uniform(opts.force ?? 1), time: uniform(0), frame: uniform(0), spin: uniform(0),
                focal: uniform(new Vector2(0.5, 0.42)), spare: uniform(new Vector3(0.5, 0.4, 0.0)),
                swirl: uniform(0), swirlR: uniform(0.6), brushAngle: uniform(opts.brushAngle ?? 1.05),
                chevDir: uniform(new Vector2(1, 0)),
            };
            for (const k of KEYS) u[k] = uniform(opts[k] ?? 0);
            for (const k of PKEYS) u[k] = uniform(PLANES.balla_sun[k]);
            const S = H / 1080;
            const res = vec2(W, H);
            const px = vec2(1.0 / W, 1.0 / H);
            const aspect = W / H;
            const LUM = vec3(0.2126, 0.7152, 0.0722);
            const lin = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };
            const ramp = RAMP.map(lin);
            // integer hash in uint arithmetic; numeric arguments are pre-multiplied on the CPU (WGSL rejects a constant
            // u32 product that overflows). Coordinates must be >= 0.
            const hk = (v, k) => (typeof v === 'number' ? uint(Math.imul(v, k | 0) >>> 0) : v.toUint().mul(uint(k >>> 0)));
            const hash3 = (x, y, z) => hash(hk(x, 1597334677).bitXor(hk(y, 3812015801)).bitXor(hk(z, 2654435769)));
            const IN_INV = inv3(ACES_IN), OUT_INV = inv3(ACES_OUT);
            const W_ = (k) => u[k].mul(u.force);
            let hist = null;

            const hook = (colorIn) => {
                const tex = convertToTexture(colorIn);
                const aces = globalThis._r ? globalThis._r.toneMapping === THREE.ACESFilmicToneMapping : true;
                const toDisp = (c) => (aces ? acesFilmicToneMapping(c, toneMappingExposure) : clamp(c, 0.0, 1.0));
                const fromDisp = (d) => {
                    if (!aces) return d;
                    const y = min(mat3(...OUT_INV).mul(d), vec3(1.0)).toVar();
                    const qa = float(1.0).sub(y.mul(0.983729));
                    const qb = float(0.0245786).sub(y.mul(0.4329510 * 0.983729));
                    const qc = float(0.000090537).add(y.mul(0.238081)).negate();
                    const x = sqrt(max(qb.mul(qb).sub(qa.mul(qc).mul(4.0)), 0.0)).sub(qb).div(qa.mul(2.0));
                    return mat3(...IN_INV).mul(max(x, 0.0)).mul(0.6).div(toneMappingExposure);
                };
                hist = new HistoryNode(tex);
                const ech = [1, 2, 3, 4].map((k) => hist.echo(k * GAP));
                const fo = u.focal;
                const toQ = (p) => vec2(p.x.sub(fo.x).mul(aspect), p.y.sub(fo.y));   // focal-centred, square units

                // ---- A: Crali's vortex + simultaneity + Balla's repetitions, into display space. a = motion.
                const s1 = convertToTexture(Fn(() => {
                    const p0 = uv();
                    const q = toQ(p0);
                    const r = length(q);
                    const ang = u.swirl.mul(exp(r.mul(r).negate().div(max(u.swirlR.mul(u.swirlR), 1e-4))));
                    const cs = cos(ang), sn = sin(ang);
                    const q2 = vec2(q.x.mul(cs).sub(q.y.mul(sn)), q.x.mul(sn).add(q.y.mul(cs)));
                    const p = vec2(q2.x.div(aspect).add(fo.x), q2.y.add(fo.y)).toVar();
                    // sanitize: one overflowed (Inf) or NaN pixel in the HDR input would become NaN in toDisp and the
                    // light-field pyramid would spread it over the whole frame (a black film). min/max return the finite
                    // operand for NaN on the GPUs this runs on; 64 is far above any real scene radiance here.
                    const san = (c) => max(min(c, vec3(64.0)), vec3(0.0));
                    const c0 = toDisp(san(tex.sample(p).rgb)).toVar();
                    const c = ech.map((e) => toDisp(san(e.sample(p).rgb)));
                    const split = vec3(c[1].r, c[0].g, c0.b);
                    const m = W_('multi');
                    const ghost = max(c0, max(c[0].mul(mix(0.55, 0.75, m)), max(c[1].mul(mix(0.3, 0.6, m)),
                        max(c[2].mul(m.mul(0.5)), c[3].mul(m.mul(0.4))))));
                    const mv = length(c0.sub(c[1]));
                    const col = mix(c0, mix(split, ghost, m.mul(0.4).add(0.35)), clamp(W_('echo'), 0.0, 1.0));
                    return vec4(col, smoothstep(0.03, 0.25, mv));
                })());

                // ---- B: colour structure tensor (Sobel per channel): E, F, G
                const s2 = convertToTexture(Fn(() => {
                    const p = uv();
                    const at = (dx, dy) => s1.sample(p.add(vec2(dx, dy).mul(px).mul(S))).rgb;
                    const a = at(-1, -1), b = at(0, -1), c = at(1, -1), d = at(-1, 0), f = at(1, 0), g = at(-1, 1), h = at(0, 1), i = at(1, 1);
                    const gx = c.add(f.mul(2.0)).add(i).sub(a).sub(d.mul(2.0)).sub(g).mul(0.25);
                    const gy = g.add(h.mul(2.0)).add(i).sub(a).sub(b.mul(2.0)).sub(c).mul(0.25);
                    return vec4(dot(gx, gx), dot(gx, gy), dot(gy, gy), 1.0);
                })());

                // ---- C: the flow field: smoothed tensor -> stroke direction t, anisotropy A, edge energy
                const flowT = convertToTexture(Fn(() => {
                    const p = uv();
                    const acc = vec3(0).toVar();
                    const taps = [[0, 0, 4], [3, 0, 2], [-3, 0, 2], [0, 3, 2], [0, -3, 2], [3, 3, 1], [-3, 3, 1], [3, -3, 1], [-3, -3, 1],
                        [6, 0, 1], [-6, 0, 1], [0, 6, 1], [0, -6, 1]];
                    const wsum = taps.reduce((s, x) => s + x[2], 0);
                    for (const [dx, dy, w] of taps) acc.addAssign(s2.sample(p.add(vec2(dx, dy).mul(px).mul(S))).rgb.mul(w / wsum));
                    const E = acc.x, F = acc.y, G = acc.z;
                    const disc = sqrt(max(E.sub(G).mul(E.sub(G)).add(F.mul(F).mul(4.0)), 0.0));
                    const l1 = E.add(G).add(disc).mul(0.5), l2 = E.add(G).sub(disc).mul(0.5);
                    const tv0 = vec2(l1.sub(E), F.negate());
                    const def = vec2(cos(u.brushAngle), sin(u.brushAngle));
                    const tv = tv0.mul(mix(float(-1.0), float(1.0), step(0.0, dot(tv0, def))));   // same sign as the default
                    const energy = E.add(G);
                    const k = smoothstep(2e-5, 6e-4, energy).mul(step(1e-12, dot(tv, tv)));
                    const t = normalize(mix(def, normalize(tv.add(vec2(1e-9, 0.0))), k).add(vec2(1e-6, 0.0)));
                    const A = l1.sub(l2).div(l1.add(l2).add(1e-9)).mul(k);
                    return vec4(t.x, t.y, A, energy);
                })());

                // ---- D: the underpainting: anisotropic Kuwahara, 8 sectors, polynomial weights
                const RAD = Math.max(3, Math.round(8 * S));
                const s3 = convertToTexture(Fn(() => {
                    const p = uv();
                    const src = s1.sample(p).toVar();
                    const out = src.rgb.toVar();
                    If(W_('under').greaterThan(0.001), () => {
                        const fl = flowT.sample(p);
                        const A = fl.z;
                        const a = float(RAD).mul(A.add(1.0)), b = float(RAD).div(A.add(1.0));
                        const cphi = fl.x, sphi = fl.y;
                        const m = [], s = [], w = [];
                        for (let k = 0; k < 8; k++) { m.push(vec3(0).toVar()); s.push(vec3(0).toVar()); w.push(float(0).toVar()); }
                        const zeta = 2.0 / RAD, eta = 0.33;
                        Loop({ start: int(-RAD), end: int(RAD + 1), type: 'int', condition: '<' },
                            { start: int(-RAD), end: int(RAD + 1), type: 'int', condition: '<' }, ({ i, j }) => {
                                const d = vec2(float(i), float(j));
                                const v = vec2(d.x.mul(cphi).add(d.y.mul(sphi)).div(a), d.y.mul(cphi).sub(d.x.mul(sphi)).div(b)).toVar();
                                If(dot(v, v).lessThanEqual(1.0), () => {
                                    const c = s1.sample(p.add(d.mul(px).mul(S))).rgb.toVar();
                                    const cc = c.mul(c);
                                    let vxx = float(zeta).sub(v.x.mul(v.x).mul(eta)), vyy = float(zeta).sub(v.y.mul(v.y).mul(eta));
                                    const z0 = max(0.0, v.y.add(vxx)), z2 = max(0.0, v.x.negate().add(vyy));
                                    const z4 = max(0.0, v.y.negate().add(vxx)), z6 = max(0.0, v.x.add(vyy));
                                    const r = vec2(v.x.sub(v.y), v.x.add(v.y)).mul(0.70710678).toVar();
                                    vxx = float(zeta).sub(r.x.mul(r.x).mul(eta)); vyy = float(zeta).sub(r.y.mul(r.y).mul(eta));
                                    const z1 = max(0.0, r.y.add(vxx)), z3 = max(0.0, r.x.negate().add(vyy));
                                    const z5 = max(0.0, r.y.negate().add(vxx)), z7 = max(0.0, r.x.add(vyy));
                                    const ws = [z0, z1, z2, z3, z4, z5, z6, z7].map((z) => z.mul(z));
                                    const sum = ws.reduce((x, y) => x.add(y));
                                    const g = exp(dot(v, v).mul(-3.125)).div(sum.add(1e-6));
                                    for (let k = 0; k < 8; k++) {
                                        const wk = ws[k].mul(g);
                                        m[k].addAssign(c.mul(wk)); s[k].addAssign(cc.mul(wk)); w[k].addAssign(wk);
                                    }
                                });
                            });
                        const num = vec3(0).toVar(), den = float(0).toVar();
                        for (let k = 0; k < 8; k++) {
                            const mk = m[k].div(w[k].add(1e-6));
                            const vk = abs(s[k].div(w[k].add(1e-6)).sub(mk.mul(mk)));
                            const al = float(1.0).div(pow(vk.x.add(vk.y).add(vk.z).mul(255.0), 4.0).add(1.0));
                            num.addAssign(mk.mul(al)); den.addAssign(al);
                        }
                        out.assign(mix(src.rgb, num.div(den.add(1e-6)), clamp(W_('under'), 0.0, 1.0)));
                    });
                    return vec4(out, src.a);
                })());

                // ---- E: the light field for Balla's street-light halos (a Gaussian pyramid of the bright parts)
                let bloom = null;
                if (BloomNode) {
                    // only real light sources make halos: lamps, neon, screens (display value > ~0.8). A lit body or a
                    // white face is not a lamp — at a lower threshold the singer grew flames.
                    bloom = new BloomNode(s1, 1.0, 0.0, 0.8);
                    bloom.smoothWidth.value = 0.12;
                    const ub = bloom.updateBefore.bind(bloom);
                    bloom.updateBefore = (frame) => (u.halo.value * u.force.value > 0.001 ? ub(frame) : undefined);
                }
                // halo: (direction away from the light, mask) + the light's colour, one RTT
                const haloT = convertToTexture(Fn(() => {
                    const p = uv();
                    if (!bloom) return vec4(0.0, 1.0, 0.0, 0.0);
                    const Lf = (o) => dot(bloom._textureNodeBlur2.sample(p.add(o.mul(px).mul(S))).rgb, LUM);
                    const gx = Lf(vec2(7, 0)).sub(Lf(vec2(-7, 0))), gy = Lf(vec2(0, 7)).sub(Lf(vec2(0, -7)));
                    const g = vec2(gx, gy);
                    const dir = normalize(g.negate().add(vec2(1e-7, 0.0)));          // downhill = away from the light
                    const lw = clamp(dot(bloom._textureNodeBlur2.sample(p).rgb, LUM), 0.0, 8.0);
                    const own = dot(s1.sample(p).rgb, LUM);
                    const sd0 = length(vec2(p.x.sub(u.spare.x).mul(aspect), p.y.sub(u.spare.y)));
                    const spared = float(1.0).sub(smoothstep(u.spare.z.mul(0.8), u.spare.z.mul(1.3), sd0)).mul(step(1e-4, u.spare.z));
                    const mask = smoothstep(0.01, 0.09, lw).mul(float(1.0).sub(smoothstep(0.35, 0.7, own)))
                        .mul(smoothstep(0.0005, 0.004, length(g))).mul(float(1.0).sub(spared));
                    // keep the BloomNode in the graph (its updateBefore runs when its output is referenced)
                    const keep = bloom.getTextureNode().sample(p).r.mul(0.0);
                    return vec4(dir.x, dir.y, mask.add(keep), lw);
                })());
                const lightCol = (p) => (bloom ? bloom._textureNodeBlur1.sample(p).rgb : vec3(0));

                // ---- F: the divisionist strokes over the underpainting
                const s4 = convertToTexture(Fn(() => {
                    const p = uv();
                    const fc = p.mul(res);
                    const sharp = s1.sample(p).toVar();
                    const under = s3.sample(p).toVar();
                    const fl = flowT.sample(p).toVar();
                    const strokesW = W_('strokes'), haloW = W_('halo');
                    const layer = (C, Wk, salt) => {
                        const cell = floor(fc.div(C)).add(4096.0);
                        const best = float(-1.0).toVar();
                        const sc = vec3(0).toVar();
                        const cov = float(0).toVar();
                        for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
                            const cx = cell.x.add(dx), cy = cell.y.add(dy);
                            const h1 = hash3(cx, cy, salt), h2 = hash3(cx, cy, salt + 1), h3 = hash3(cx, cy, salt + 2);
                            const ctr = vec2(cx, cy).sub(4096.0).add(vec2(h1, h2).mul(0.9).add(0.05)).mul(C);
                            const cuv = ctr.div(res);
                            const f = flowT.sample(cuv);
                            const hl = haloT.sample(cuv);
                            const hm = hl.z.mul(haloW);
                            const t = normalize(mix(f.xy, hl.xy, clamp(hm.mul(1.5), 0.0, 1.0)).add(vec2(1e-6, 0.0)));
                            const n = vec2(t.y.negate(), t.x);
                            const d = fc.sub(ctr);
                            const al = dot(d, t), ac = dot(d, n);
                            const L = float(C).mul(h3.mul(0.8).add(0.9)).mul(f.z.mul(0.5).add(0.8));
                            const Wd = float(C * Wk).mul(h1.mul(0.5).add(0.75));
                            const acV = ac.sub(abs(al).mul(0.6).mul(clamp(hm.mul(2.0), 0.0, 1.0)));   // V strokes in halos
                            const tap = max(float(1.0).sub(al.div(L).mul(al.div(L))), 0.0);
                            const wv = Wd.mul(sqrt(tap));
                            const inside = smoothstep(wv.add(0.8 * S), wv.sub(0.8 * S), abs(acV)).mul(step(abs(al), L));
                            // paint: the underpainting at the stroke's centre, value-jittered, pushed warm or cool, a few
                            // strokes toward the complement (divisionism), plus the light's colour in a halo
                            const c = s3.sample(cuv).rgb.toVar();
                            c.mulAssign(h2.mul(0.3).add(0.85));
                            c.mulAssign(mix(vec3(0.9, 0.97, 1.12), vec3(1.12, 0.98, 0.88), h3));
                            const mxc = max(c.r, max(c.g, c.b)), mnc = min(c.r, min(c.g, c.b));
                            const comp = vec3(mxc.add(mnc)).sub(c);
                            c.assign(mix(c, mix(c, comp, 0.4), step(0.92, h1).mul(0.5)));
                            const lc = max(min(lightCol(cuv), vec3(8.0)), vec3(0.0));
                            const lcmx = max(lc.r, max(lc.g, lc.b)).add(1e-4);
                            const lcComp = vec3(lcmx.add(min(lc.r, min(lc.g, lc.b)))).sub(lc);
                            const halo = mix(lc, lcComp.mul(0.8), step(0.6, h2)).mul(hm).mul(h3.mul(1.2).add(0.6));
                            c.addAssign(halo);
                            const k = step(best, h3).mul(step(0.02, inside));
                            sc.assign(mix(sc, c, k.mul(inside)));
                            best.assign(mix(best, h3, k));
                            cov.assign(max(cov, inside.mul(k)));
                        }
                        return vec4(sc, cov);
                    };
                    const sd0 = length(vec2(p.x.sub(u.spare.x).mul(aspect), p.y.sub(u.spare.y)));
                    const spared = float(1.0).sub(smoothstep(u.spare.z.mul(0.6), u.spare.z, sd0)).mul(step(1e-4, u.spare.z));
                    const col = under.rgb.toVar();
                    If(strokesW.add(haloW).greaterThan(0.001), () => {
                        const coarse = layer(14 * S, 0.40, 101);
                        const fine = layer(6 * S, 0.38, 211);
                        const detail = max(smoothstep(0.004, 0.06, fl.w), spared);     // edges and the face get the fine brush
                        const sc = mix(coarse.rgb, fine.rgb, detail), cov = mix(coarse.a, fine.a, detail);
                        col.assign(mix(col, sc, cov.mul(clamp(strokesW, 0.0, 1.0))));
                    });
                    // crisp: dense multi-directional detail (lettering, eyes, the mouth line) comes back sharp; the
                    // spared face always keeps most of its drawing
                    // (lettering: lots of edge energy in every direction inside a few pixels; the threshold is low because the
                    // tensor is smoothed over ~12 px, which averages a letter's strokes down)
                    const crispK = max(smoothstep(0.006, 0.05, fl.w).mul(float(1.0).sub(fl.z.mul(0.7))).mul(u.crisp), spared.mul(0.75));
                    col.assign(mix(col, sharp.rgb, clamp(crispK, 0.0, 0.85)));
                    return vec4(col, under.a);
                })());

                // ---- G: planes, lines of force, palette, canvas — back to linear
                return Fn(() => {
                    const p = uv().toVar();
                    const fc = p.mul(res).toVar();
                    const q = toQ(p).toVar();
                    const sd0 = length(vec2(p.x.sub(u.spare.x).mul(aspect), p.y.sub(u.spare.y)));
                    const spared = float(1.0).sub(smoothstep(u.spare.z.mul(0.6), u.spare.z, sd0)).mul(step(1e-4, u.spare.z));
                    const planesW = W_('planes').mul(float(1.0).sub(spared.mul(0.85)));
                    const linesW = W_('lines');
                    const on = (k) => step(0.5, u[k]);
                    const ang = atan(q.y, q.x).add(u.spin);
                    const id = float(0).toVar();
                    const edge = float(1e3).toVar();
                    const addEdge = (e, k) => edge.assign(min(edge, mix(float(1e3), e, on(k))));
                    // rays (Balla's cones)
                    const sector = floor(ang.div(2 * Math.PI / RAYS).add(64.0));
                    id.addAssign(sector.mul(on('rays')));
                    const sa = fract(ang.div(2 * Math.PI / RAYS));
                    addEdge(min(sa, float(1.0).sub(sa)).mul(2 * Math.PI / RAYS).mul(length(q)).mul(H), 'rays');
                    // rings, logarithmic (they widen outward like a dive); none inside the light's own disc
                    const lr = log(max(length(q), 1e-3)).mul(2.6).add(u.time.mul(0.12));
                    const inDisc = step(length(q), 0.07);
                    id.addAssign(floor(lr).add(32.0).mul(977.0).mul(float(1.0).sub(inDisc)).mul(on('rings')));
                    const rf = fract(lr);
                    addEdge(mix(min(rf, float(1.0).sub(rf)).div(2.6).mul(length(q)).mul(H), float(1e3), inDisc), 'rings');
                    // long diagonals
                    for (let k = 0; k < DIAG.length; k++) {
                        const [deg, off] = DIAG[k];
                        const th = u.spin.mul(0.35 * (k % 2 ? 1 : -1)).add(deg * Math.PI / 180);
                        const sd = dot(q, vec2(sin(th), cos(th))).sub(off);
                        id.addAssign(step(0.0, sd).mul(Math.pow(2, k + 1) * 7.0).mul(on('diag')));
                        addEdge(abs(sd).mul(H), 'diag');
                    }
                    // chevrons (Russolo's wedges): V-shaped bands pointing along chevDir, travelling
                    const cd = normalize(u.chevDir.add(vec2(1e-6, 0.0)));
                    const along = dot(q, cd), acr = dot(q, vec2(cd.y.negate(), cd.x));
                    const vv = along.sub(abs(acr).mul(0.9)).mul(3.2).sub(u.time.mul(0.9));
                    id.addAssign(floor(vv).add(64.0).mul(331.0).mul(on('chev')));
                    const vf = fract(vv);
                    addEdge(min(vf, float(1.0).sub(vf)).div(3.2 * 1.345).mul(H), 'chev');
                    // triangles (Balla's iridescent interpenetrations): a skewed lattice, each cell split in two
                    const ts = q.mul(4.0);
                    const ta = ts.x.sub(ts.y.mul(0.57735)), tb = ts.y.mul(1.1547);
                    const tfa = fract(ta), tfb = fract(tb);
                    const upper = step(1.0, tfa.add(tfb));
                    id.addAssign(floor(ta).add(64.0).mul(53.0).add(floor(tb).add(64.0).mul(97.0)).add(upper.mul(7.0)).mul(on('tri')));
                    const te = min(min(min(tfa, float(1.0).sub(tfa)), min(tfb, float(1.0).sub(tfb))), abs(tfa.add(tfb).sub(1.0)).mul(0.7071));
                    addEdge(te.div(4.0 * 1.15).mul(H), 'tri');

                    const hA = hash3(id.add(1e5), 17, 3), hB = hash3(id.add(1e5), 29, 5), hC = hash3(id.add(1e5), 41, 7);
                    const slip = vec2(hA.sub(0.5), hB.sub(0.5)).mul(0.012).mul(planesW);
                    const sp = p.add(slip);
                    const base = s4.sample(sp).toVar();
                    const col = base.rgb.toVar();
                    const moving = base.a;

                    If(linesW.greaterThan(0.001), () => {
                        // lines of force 1: drag along the contour where things move
                        const t = flowT.sample(sp).xy;
                        const acc = vec3(0).toVar();
                        for (let k = -6; k <= 6; k++) acc.addAssign(s4.sample(sp.add(t.mul(k * 2.2 * S).mul(px))).rgb);
                        col.assign(mix(col, acc.div(13), clamp(moving.mul(linesW).mul(1.2), 0.0, 1.0)));
                        // lines of force 2: sparse speed lines toward the focal point, off the middle of frame
                        const dir = normalize(q.add(vec2(1e-5, 0.0)));
                        const dirUv = vec2(dir.x.div(aspect), dir.y);
                        const acc2 = vec3(0).toVar();
                        for (let k = 0; k < 10; k++) acc2.addAssign(s4.sample(sp.sub(dirUv.mul(k * 0.0045))).rgb);
                        const offC = smoothstep(0.22, 0.55, length(vec2(p.x.sub(0.5).mul(aspect), p.y.sub(0.5))));
                        const radial = smoothstep(0.2, 0.9, length(q)).mul(offC).mul(linesW);
                        const fine = hash3(floor(ang.mul(180.0 / Math.PI * 0.7).add(720.0)), 3, 11);
                        col.assign(mix(col, acc2.div(10), radial.mul(smoothstep(0.72, 0.95, fine))));
                    });

                    // palette FIRST: gradient map by perceptual luminance; saturated light keeps its own hue. (The planes
                    // come after it and shade the final colours, so a dark plane stays dark instead of jumping a band.)
                    const lum = dot(col, LUM);
                    const x = clamp(pow(max(lum, 0.0), 0.62).mul(1.02), 0.0, 1.0).mul(RAMP.length - 1).toVar();
                    const rc = ramp[0].toVar();
                    for (let k = 1; k < RAMP.length; k++) rc.assign(mix(rc, ramp[k], clamp(x.sub(k - 1), 0.0, 1.0)));
                    const chroma = col.div(max(lum, 1e-4)).mul(dot(rc, LUM));
                    const mxc = max(col.r, max(col.g, col.b)), mnc = min(col.r, min(col.g, col.b));
                    const sat = mxc.sub(mnc).div(mxc.add(1e-4));
                    col.assign(mix(col, mix(rc, chroma, clamp(sat.mul(0.8).add(0.2), 0.0, 0.85)), clamp(W_('palette'), 0.0, 1.0)));

                    // planes: lighter/darker, warmer/cooler (multiplicative: black stays black); SHADOW planes toward wet
                    // black; NEON planes glazed, but only where there is light to glaze (a glaze can't lift the night)
                    const shade = float(1.0).add(hC.sub(0.5).mul(0.6).mul(planesW));
                    const warm = mix(vec3(0.85, 0.95, 1.18), vec3(1.15, 0.97, 0.85), hA);
                    col.assign(col.mul(shade).mul(mix(vec3(1.0), warm, planesW.mul(0.6))));
                    col.assign(col.mul(float(1.0).sub(step(hC, 0.3).mul(planesW).mul(0.45))));
                    const neon = mix(lin('#1fd4e8'), lin('#ff3fa4'), step(0.5, hB));
                    const gn = hash3(floor(fc.x.div(5.0 * S).add(fc.y.div(17.0 * S))), floor(fc.y.div(5.0 * S)), 37);
                    const lit = smoothstep(0.02, 0.25, dot(col, LUM));
                    const glazeA = step(0.72, hC).mul(planesW).mul(gn.mul(0.10).add(0.08)).mul(lit);
                    col.assign(mix(col, float(1.0).sub(float(1.0).sub(col).mul(float(1.0).sub(neon))), glazeA));
                    // the plane edges: broken, brushy painted lines, light or dark
                    const wob = hash3(floor(fc.x.div(9.0 * S)), floor(fc.y.div(9.0 * S)), 13).mul(0.8).add(0.6);
                    const stroke = float(1.0).sub(smoothstep(1.0 * S, 2.6 * S, edge.div(wob))).mul(planesW).toVar();
                    stroke.mulAssign(smoothstep(0.18, 0.4, hash3(floor(fc.x.div(23.0 * S)), floor(fc.y.div(23.0 * S)), 31)));
                    const inkL = mix(vec3(0.02, 0.01, 0.05), vec3(1.0, 0.92, 0.85), step(0.5, hB));
                    col.assign(mix(col, inkL, stroke.mul(mix(0.12, 0.5, lit))));   // in the dark a plane edge is a hint

                    // canvas: weave + VHS scanline + grain (grain scales with the light: no grey veil on the blacks)
                    const cw = W_('canvas');
                    const wx = abs(fract(fc.x.div(3.0 * S)).sub(0.5)), wy = abs(fract(fc.y.div(3.0 * S)).sub(0.5));
                    const weave = mix(wx, wy, step(0.5, fract(fc.x.div(6.0 * S).add(floor(fc.y.div(3.0 * S)).mul(0.5)))));
                    const scan = smoothstep(0.25, 0.5, abs(fract(fc.y.div(3.0 * S)).sub(0.5)));
                    const grain = hash3(floor(fc.x), floor(fc.y), u.frame).sub(0.5);
                    col.assign(col.mul(float(1.0).sub(cw.mul(weave.mul(0.10).add(scan.mul(0.07)))))
                        .add(grain.mul(dot(col, LUM).mul(0.08).add(0.006)).mul(cw)));

                    return vec4(fromDisp(clamp(col, 0.0, 1.0)), 1.0);
                })();
            };
            globalThis._autoEnhanceColorHook = hook;
            u.cut = () => { if (hist) hist.fresh = true; };
            return {
                uniforms: u,
                update(t) { u.time.value = t; u.frame.value = Math.round(t * FPSV); },
            };
        });
    }

    const ready = registerAeropittura().catch((e) => { console.error('[aeropittura] setup failed: ' + (e && e.stack || e)); });
    (globalThis._effectsReady ||= []).push(ready);
    globalThis.AeropitturaFX = {
        ready,
        applyTo(args) {
            if (!_factory) throw new Error('AeropitturaFX: not ready (render_scene awaits globalThis._effectsReady before setup)');
            return _factory(args);
        },
        RAMP, LOOKS, PLANES, applyLook, setPlanes,
    };
})();
