// crt.js — TSL port of custom_effects.js::crt.
// Cathode-ray-tube monitor simulation: barrel-screen curvature, RGB
// chromatic-aberration channel offset, phosphor afterglow trail,
// vignette, scanlines, mains-hum flicker, aperture-grille slot mask.
//
// Public API:
//   CRTFX.applyTo({ opts });
//
// Options:
//   opacity float — final blend with original (default 1.0)
//   width/height int — output resolution (defaults to globalThis.WIDTH/HEIGHT)
//
// Architecture mirrors vhs_tape.js — single hook spliced into the
// autoenhance pipeline via globalThis._autoEnhanceColorHook.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[crt] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildCRTHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv,
            sin, mod, mix, clamp, pow, step, abs, floor,
        } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1920;
        const h = opts.height ?? globalThis.HEIGHT ?? 1080;

        const u = {
            time:        uniform(0),
            opacity:     uniform(opts.opacity ?? 1.0),
            iResolution: uniform(new THREE.Vector2(w, h)),
        };

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            setResolution(width, height) { u.iResolution.value.set(width, height); },
            hook(colorIn /*, depth, normal, mr */) {
                const colorTex = THREE.convertToTexture(colorIn);

                return Fn(() => {
                    const uvBase = uv();
                    const time = u.time;
                    const iRes = u.iResolution;

                    // ---- Barrel curve ----
                    // (q - 0.5) * 2 → [-1,1]; multiply by 1.1; quadratic warp;
                    // back to [0,1] with a small inset.
                    const q = uvBase;
                    const c0 = q.sub(0.5).mul(2.0).mul(1.1);
                    // c0.x *= 1 + (|c0.y|/5)^2;  c0.y *= 1 + (|c0.x|/4)^2
                    const c1x = c0.x.mul(float(1).add(pow(abs(c0.y).div(5), 2)));
                    const c1y = c0.y.mul(float(1).add(pow(abs(c0.x).div(4), 2)));
                    const c1 = vec2(c1x, c1y);
                    const cuv = c1.div(2).add(0.5).mul(0.92).add(0.04);

                    // ---- Horizontal scan-jitter offset (triple-sine product) ----
                    const x = sin(time.mul(0.3).add(cuv.y.mul(21))).mul(
                        sin(time.mul(0.7).add(cuv.y.mul(29)))
                    ).mul(
                        sin(time.mul(0.33).add(0.3).add(cuv.y.mul(31)))
                    ).mul(0.0017);

                    // ---- Per-channel sample with chromatic aberration ----
                    const sR = colorTex.sample(vec2(x.add(cuv.x).add(0.001), cuv.y.add(0.001))).x.add(0.05);
                    const sG = colorTex.sample(vec2(x.add(cuv.x).add(0.000), cuv.y.sub(0.002))).y.add(0.05);
                    const sB = colorTex.sample(vec2(x.add(cuv.x).sub(0.002), cuv.y.add(0.000))).z.add(0.05);
                    let col = vec3(sR, sG, sB).toVar();

                    // ---- Phosphor afterglow: small displaced second sample per channel ----
                    const aR = colorTex.sample(vec2(x.add(0.025), -0.027).mul(0.75).add(vec2(cuv.x.add(0.001), cuv.y.add(0.001)))).x;
                    const aG = colorTex.sample(vec2(x.add(-0.022), -0.020).mul(0.75).add(vec2(cuv.x, cuv.y.sub(0.002)))).y;
                    const aB = colorTex.sample(vec2(x.add(-0.020), -0.018).mul(0.75).add(vec2(cuv.x.sub(0.002), cuv.y))).z;
                    col.assign(col.add(vec3(aR.mul(0.08), aG.mul(0.05), aB.mul(0.08))));

                    // ---- Tone curve: 0.6c + 0.4c² (boosted highlights) ----
                    col.assign(clamp(col.mul(0.6).add(col.mul(col).mul(0.4)), 0, 1));

                    // ---- Vignette ----
                    const vig = float(16).mul(cuv.x).mul(cuv.y)
                                .mul(float(1).sub(cuv.x))
                                .mul(float(1).sub(cuv.y));
                    col.assign(col.mul(vec3(pow(vig, 0.3))));

                    // ---- Phosphor green tint + brightness boost ----
                    col.assign(col.mul(vec3(0.95, 1.05, 0.95)).mul(2.8));

                    // ---- Scanlines (driven by post-curve UV.y × resolution) ----
                    const scans = clamp(
                        float(0.35).add(float(0.35).mul(sin(time.mul(3.5).add(cuv.y.mul(iRes.y).mul(1.5))))),
                        0, 1,
                    );
                    const s = pow(scans, 1.7);
                    col.assign(col.mul(vec3(float(0.4).add(s.mul(0.7)))));

                    // ---- Mains-hum flicker ----
                    col.assign(col.mul(float(1).add(float(0.01).mul(sin(time.mul(110))))));

                    // ---- Off-screen guard (curve can push uv past [0,1]) ----
                    const inX = step(0, cuv.x).mul(step(cuv.x, 1));
                    const inY = step(0, cuv.y).mul(step(cuv.y, 1));
                    col.assign(col.mul(inX).mul(inY));

                    // ---- Aperture grille — dim every other column by 65% ----
                    // Original: clamp((mod(gl_FragCoord.x, 2.0) - 1.0)*2.0, 0, 1)
                    const fragX = floor(uvBase.x.mul(iRes.x));
                    const grille = clamp(mod(fragX, 2).sub(1).mul(2), 0, 1);
                    col.assign(col.mul(float(1).sub(grille.mul(0.65))));

                    // ---- Final blend with original ----
                    const origIn = colorTex.sample(uvBase);
                    return mix(origIn, vec4(col, 1.0), u.opacity);
                })();
            },
        };
    }

    function applyTo(opts) {
        opts = opts || {};
        const built = buildCRTHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.CRTFX = { applyTo };
    console.log('[crt] CRTFX.applyTo registered');
})();
