// vhs_tape.js — TSL port of custom_effects.js::vhs_tape.
// NTSC composite encode/decode simulation: real chroma bleed via YIQ
// modulation, soft tape-head gaussian blur, tape wave/crease/switching
// displacements, white dropouts, AC beat, color noise, YIQ tint wash.
//
// Architecture:
//   - Splices into the autoenhance pipeline via globalThis._autoEnhanceColorHook.
//   - All work done in TSL (NodeMaterial/no WebGL fallbacks).
//   - Noise: inline hash (fract(sin(...))) instead of CPU-baked DataTexture.
//
// Public API:
//   VHSTapeFX.applyTo({ camera, opts });   // camera optional, opts optional
//
// Options:
//   intensity float — strength of all analog artifacts (default 1.0)
//   opacity   float — final blend with original (default 1.0)
//   width/height int — output resolution (defaults to globalThis.WIDTH/HEIGHT or 1920x1080)
//
// NOT a tweak port of the WebGL ShaderPass — this is the same algorithm
// rewritten as TSL Fn graph compiled to WGSL by the WebGPURenderer.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[vhs_tape] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildVHSTapeHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv, Loop,
            sin, cos, fract, mod, mix, clamp, smoothstep, step, pow,
        } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1920;
        const h = opts.height ?? globalThis.HEIGHT ?? 1080;

        const u = {
            time:        uniform(0),
            intensity:   uniform(opts.intensity ?? 1.0),
            opacity:     uniform(opts.opacity ?? 1.0),
            iResolution: uniform(new THREE.Vector2(w, h)),
        };

        return {
            uniforms: u,
            update(t) {
                u.time.value = t;
            },
            setResolution(width, height) {
                u.iResolution.value.set(width, height);
            },
            hook(colorIn /*, sceneDepth, sceneNormal, sceneMR */) {
                const colorTex = THREE.convertToTexture(colorIn);
                if (typeof THREE.gaussianBlur !== 'function') {
                    throw new Error('[vhs_tape] THREE.gaussianBlur not available — render_common.mjs must import addons/tsl/display/GaussianBlurNode.js');
                }
                // One-shot soft-focus pre-pass on the raw input. Replaces
                // the per-pixel inline 9-tap that used to run 6× inside
                // the chroma-bleed loop (54 texture reads/pixel) — now
                // that loop samples this pre-blurred texture (1 read per
                // tap, 6 reads/pixel for chroma bleed). Sigma=1 gives a
                // 5-tap × 2-pass separable kernel — equivalent radius to
                // the old 2.5px-spaced 3×3 binomial.
                //
                // Note: gaussianBlur() returns a TempNode (vec4 inline at
                // current uv); the chroma-bleed loop needs to sample at
                // OFFSET uvs, so we grab the inner PassTextureNode via
                // getTextureNode() — that one has .sample(customUV).
                const preBlurNode = THREE.gaussianBlur(colorTex, null, 1);
                const preBlur = preBlurNode.getTextureNode();

                return Fn(() => {
                    const uvBase = uv();
                    const time = u.time;
                    const intensity = u.intensity;
                    const iRes = u.iResolution;
                    const origIn = colorTex.sample(uvBase);

                    // ---- Hash-based v2random (replaces texture2D(tNoise,...)) ----
                    const v2random = (p) =>
                        fract(sin(p.x.mul(127.1).add(p.y.mul(311.7))).mul(43758.5453));

                    // Sampler over the pre-blurred (soft-focus) texture.
                    // Used by the chroma-bleed loop and the dropout noise
                    // helper as a stand-in for the old vhsBlur(sUv).
                    const vhsBlur = (sampleUv) => preBlur.sample(sampleUv).rgb;

                    // ---- YIQ <-> RGB matrix conversions ----
                    const rgb2yiq = (rgb) => vec3(
                        rgb.x.mul(0.299).add(rgb.y.mul(0.587)).add(rgb.z.mul(0.114)),
                        rgb.x.mul(0.596).sub(rgb.y.mul(0.274)).sub(rgb.z.mul(0.322)),
                        rgb.x.mul(0.211).sub(rgb.y.mul(0.523)).add(rgb.z.mul(0.312)),
                    );
                    const yiq2rgb = (yiq) => vec3(
                        yiq.x.add(yiq.y.mul(0.956)).add(yiq.z.mul(0.621)),
                        yiq.x.sub(yiq.y.mul(0.272)).sub(yiq.z.mul(0.647)),
                        yiq.x.sub(yiq.y.mul(1.106)).add(yiq.z.mul(1.703)),
                    );

                    // ---- 6-tap chroma bleed in YIQ space ----
                    // Tap 0 contributes all luma + no chroma.
                    // Tap 5 contributes no luma + all chroma.
                    // Result: chroma signal smears -X relative to luma — the
                    // signature VHS reds-bleed-into-pinks look.
                    const SAMPLES = 6;
                    const SMINUS = float(SAMPLES - 1);
                    const vhsTex2D = (sampleUv, rot) => {
                        const yiqAccum = vec3(0).toVar();
                        Loop({ start: 0, end: SAMPLES, type: 'int' }, ({ i }) => {
                            const fi = float(i);
                            const fInv = SMINUS.sub(fi);
                            const sUv = sampleUv.sub(vec2(fi, 0).div(iRes));
                            const rgb = vhsBlur(sUv);
                            const yiqVal = rgb2yiq(rgb);
                            const wY = fInv.div(SMINUS);
                            const wC = fi.div(SMINUS);
                            const weighted = vec3(
                                yiqVal.x.mul(wY),
                                yiqVal.y.mul(wC),
                                yiqVal.z.mul(wC),
                            );
                            yiqAccum.assign(yiqAccum.add(weighted.div(float(SAMPLES)).mul(2.0)));
                        });
                        // Rotate chroma (yz) by `rot` — the original conditional
                        // `if (rot != 0.0)` is unnecessary since rot=0 produces identity.
                        const cs = cos(rot);
                        const sn = sin(rot);
                        const rotI = cs.mul(yiqAccum.y).add(sn.mul(yiqAccum.z));
                        const rotQ = sn.negate().mul(yiqAccum.y).add(cs.mul(yiqAccum.z));
                        return yiq2rgb(vec3(yiqAccum.x, rotI, rotQ));
                    };

                    // ===================================================================
                    // Per-pixel pipeline (mirrors original main())
                    // ===================================================================
                    const uvn = uvBase.toVar();

                    // Tape wave — fine horizontal noise displacement, two octaves
                    const wave1 = v2random(vec2(uvn.y.div(10), time.div(10))).sub(0.5)
                                    .div(iRes.x).mul(intensity);
                    const wave2 = v2random(vec2(uvn.y, time.mul(10))).sub(0.5)
                                    .div(iRes.x).mul(intensity);
                    uvn.assign(vec2(uvn.x.add(wave1).add(wave2), uvn.y));

                    // Tape crease — sine-banded corrupted rows
                    const tcRand = v2random(time.mul(vec2(0.67, 0.59)));
                    const tcAngle = uvn.y.mul(8).sub(time.add(tcRand.mul(0.14)).mul(3.769911));
                    const tcPhase = smoothstep(0.9, 0.96, sin(tcAngle));
                    const tcNoise = smoothstep(0.3, 1.0, v2random(vec2(uvn.y.mul(4.77), time)));
                    const tc = tcPhase.mul(tcNoise);
                    uvn.assign(vec2(
                        uvn.x.sub(tc.div(iRes.x).mul(8).mul(intensity)),
                        uvn.y,
                    ));

                    // Switching noise — bottom band of frame gets displaced
                    const snPhase = smoothstep(float(6).div(iRes.y), 0, uvn.y);
                    const snXJitter = v2random(vec2(uvBase.y.mul(100), time.mul(10))).sub(0.5)
                                        .div(iRes.x).mul(24).mul(intensity);
                    uvn.assign(vec2(
                        uvn.x.add(snPhase.mul(snXJitter)),
                        uvn.y.add(snPhase.mul(0.3).mul(intensity)),
                    ));

                    // Fetch with chroma bleed (rotated by tcPhase + snPhase contributions)
                    const col = vhsTex2D(uvn, tcPhase.mul(0.2).add(snPhase.mul(2))).toVar();

                    // White dropouts inside crease regions
                    const cn = tcNoise.mul(float(0.3).add(tcPhase.mul(0.7)));
                    const uvt = vec2(uvn.x, uvn.y.add(v2random(vec2(uvn.y, time))))
                                .mul(vec2(0.1, 1.0));
                    const n0 = v2random(uvt);
                    const n1 = v2random(uvt.add(vec2(0, 1).div(iRes.x)));
                    const dropoutTrigger = step(0.29, cn).mul(step(n1, n0));
                    col.assign(mix(col, vec3(2.0), dropoutTrigger.mul(pow(n0, 10))));

                    // AC beat — slow vertical brightness ripple
                    const acRand = v2random(vec2(0, uvBase.y.add(time.mul(0.2)).mul(0.1)).div(10));
                    const acBeat = float(1).add(float(0.1).mul(smoothstep(0.4, 0.6, acRand)));
                    col.assign(col.mul(acBeat));

                    // Color noise grain — three independent hashes for RGB
                    const grainUV = uvn.add(vec2(time.mul(5.97), time.mul(4.45)));
                    const grainR = v2random(mod(grainUV, 1));
                    const grainG = v2random(mod(grainUV.add(vec2(17.3, 23.1)), 1));
                    const grainB = v2random(mod(grainUV.add(vec2(43.7, 11.9)), 1));
                    col.assign(col.mul(float(0.9).add(vec3(grainR, grainG, grainB).mul(0.1))));
                    col.assign(clamp(col, 0, 1));

                    // YIQ signature tint — small luma lift + cool wash
                    const yiqOut = rgb2yiq(col);
                    const tinted = vec3(0.05, -0.02, 0.0).add(vec3(0.95, 1.0, 1.0).mul(yiqOut));
                    col.assign(yiq2rgb(tinted));

                    // Mix with original by opacity
                    return mix(origIn, vec4(col, origIn.a), u.opacity);
                })();
            },
        };
    }

    function applyTo(opts) {
        opts = opts || {};
        const built = buildVHSTapeHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.VHSTapeFX = { applyTo };
    console.log('[vhs_tape] VHSTapeFX.applyTo registered');
})();
