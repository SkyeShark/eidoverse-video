// wavy.js — TSL port of custom_effects.js::wavy.
// Sinusoidal horizontal row shift: each row's X is offset by
// amplitude * sin(frequency * y_pixel + phase). Port of the
// glitch_effects.py wave_distort cousin.
//
// Public API:
//   WavyFX.applyTo({ opts });
//
// Options:
//   amplitude  float — max horizontal shift in pixels (default 10)
//   frequency  float — wave frequency along Y, cycles/px (default 0.1)
//   phase      float — initial phase offset in radians (default 0)
//   animate    bool  — animate phase over time (default false)
//   animSpeed  float — radians per second when animate=true (default 1.0)
//   opacity    float — final blend with original (default 1.0)
//   width/height int — output res (defaults to globalThis.WIDTH/HEIGHT)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[wavy] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const { uniform, Fn, vec2, float, uv, sin, mix } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1280;
        const h = opts.height ?? globalThis.HEIGHT ?? 720;

        const u = {
            time:        uniform(0),
            amplitude:   uniform(opts.amplitude ?? 10),
            frequency:   uniform(opts.frequency ?? 0.1),
            phase:       uniform(opts.phase ?? 0),
            animate:     uniform(opts.animate ? 1.0 : 0.0),
            animSpeed:   uniform(opts.animSpeed ?? 1.0),
            opacity:     uniform(opts.opacity ?? 1.0),
            iResolution: uniform(new THREE.Vector2(w, h)),
        };

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            setResolution(width, height) {
                u.iResolution.value.set(width, height);
            },
            hook(colorIn /*, sceneDepth, sceneNormal, sceneMR */) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const origIn = colorTex.sample(uvBase);

                    // y in pixels = vUv.y * resolution.y. Reference uses
                    // gl_FragCoord.y (0..res.y) directly; same effect.
                    const yPx = uvBase.y.mul(u.iResolution.y);
                    const p = u.phase.add(u.animate.mul(u.time).mul(u.animSpeed));
                    const shiftPx = u.amplitude.mul(sin(u.frequency.mul(yPx).add(p)));
                    const uvShift = vec2(
                        uvBase.x.add(shiftPx.div(u.iResolution.x)),
                        uvBase.y,
                    );
                    const effect = colorTex.sample(uvShift);
                    return mix(origIn, effect, u.opacity);
                })();
            },
        };
    }

    function applyTo(args) {
        const opts = (args && args.opts) ?? args ?? {};
        const built = buildHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.WavyFX = { applyTo };
    console.log('[wavy] WavyFX.applyTo registered');
})();
