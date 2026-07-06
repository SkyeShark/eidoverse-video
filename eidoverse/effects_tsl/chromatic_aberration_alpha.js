// chromatic_aberration_alpha.js — TSL port of
// custom_effects.js::chromatic_aberration_alpha.
//
// RGB channel offset with alpha-awareness. The stock RGBShiftShader
// blindly samples R at +offset and B at -offset, so on transparent
// overlays the offset samples land on alpha=0 pixels and drag the
// shifted channels to 0 → green tint along edges. This variant
// alpha-weights each shifted channel: where the offset sample is
// transparent, that channel falls back to the centre's value, keeping
// UI/sprite edges colour-correct.
//
// Public API:
//   ChromaticAberrationAlphaFX.applyTo({ opts });
//
// Options:
//   amount   float — shift magnitude in UV units (default 0.005)
//   angle    float — shift direction in radians (default 0 = +x)
//   opacity  float — final blend with original (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[chromatic_aberration_alpha] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const { uniform, Fn, vec2, vec4, float, uv, sin, cos, mix, max } = THREE;

        const u = {
            amount:  uniform(opts.amount  ?? 0.005),
            angle:   uniform(opts.angle   ?? 0.0),
            opacity: uniform(opts.opacity ?? 1.0),
        };

        return {
            uniforms: u,
            update(/* t */) {
                // No animated state — knobs are static unless caller pokes uniforms.
            },
            hook(colorIn /*, sceneDepth, sceneNormal, sceneMR */) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const offset = vec2(cos(u.angle), sin(u.angle)).mul(u.amount);
                    const cr = colorTex.sample(uvBase.add(offset));
                    const cg = colorTex.sample(uvBase);
                    const cb = colorTex.sample(uvBase.sub(offset));
                    // Alpha-weighted channel mix
                    const r = mix(cg.r, cr.r, cr.a);
                    const b = mix(cg.b, cb.b, cb.a);
                    const a = max(cr.a, max(cg.a, cb.a));
                    const shifted = vec4(r, cg.g, b, a);
                    return mix(cg, shifted, u.opacity);
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

    globalThis.ChromaticAberrationAlphaFX = { applyTo };
    console.log('[chromatic_aberration_alpha] ChromaticAberrationAlphaFX.applyTo registered');
})();
