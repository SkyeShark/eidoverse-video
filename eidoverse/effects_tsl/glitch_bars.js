// glitch_bars.js — TSL port of custom_effects.js::glitch_bars.
// Horizontal RGB-split bars scrolling vertically. Inside each bar the
// red and blue channels are offset by a sin-driven amount, producing
// classic broadcast-glitch / TikTok-beat-glitch chunks.
//
// Public API:
//   GlitchBarsFX.applyTo({ opts });
//
// Options:
//   barFreq      float — bar density along Y (default 20.0)
//   scrollSpeed  float — vertical scroll rate (default 3.0)
//   shift        float — per-channel UV shift inside bars (default 0.025)
//   opacity      float — final blend with original (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[glitch_bars] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv,
            sin, fract, step, mix,
        } = THREE;

        const u = {
            time:        uniform(0),
            barFreq:     uniform(opts.barFreq     ?? 20.0),
            scrollSpeed: uniform(opts.scrollSpeed ?? 3.0),
            shift:       uniform(opts.shift       ?? 0.025),
            opacity:     uniform(opts.opacity     ?? 1.0),
        };

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const orig = colorTex.sample(uvBase);
                    const bar = step(
                        0.7,
                        fract(uvBase.y.mul(u.barFreq).add(u.time.mul(u.scrollSpeed))),
                    );
                    const dir = sin(u.time.mul(12.0).add(uvBase.y.mul(50.0)));
                    const sh = bar.mul(u.shift).mul(dir);
                    const r = colorTex.sample(uvBase.add(vec2(sh, 0))).r;
                    const g = colorTex.sample(uvBase).g;
                    const b = colorTex.sample(uvBase.sub(vec2(sh, 0))).b;
                    const col = vec3(r, g, b);
                    return mix(orig, vec4(col, 1.0), u.opacity);
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
            uniforms: built.uniforms,
        };
    }

    globalThis.GlitchBarsFX = { applyTo };
    console.log('[glitch_bars] GlitchBarsFX.applyTo registered');
})();
