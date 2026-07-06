// lensflare.js — wraps three's `lensflare()` (display/LensflareNode.js).
// Renders ghost-style lens flares (multiple bright dots / chromatic
// halos) around bright spots. Distinct aesthetic from anamorphic_flare:
//   - anamorphic: long single coloured streaks
//   - lensflare: pivoted ghost-spots cluster (think Star Trek)
//
// Both use the pre-bloom hook so they sample raw HDR (anamorphic and
// lensflare can be stacked together — they install different hook
// instances, but since both target `_autoEnhancePreBloomHook`, only the
// LAST applyTo'd wins. Use one or the other per scene; combining would
// require chaining like nuclear_explosion does for clouds).
//
// Public API: LensflareFX.applyTo({ opts });
//
// Recognised opts:
//   threshold        Float — bright-spot threshold (default 4.0 for HDR).
//   ghostTint        [r,g,b] — ghost colour (default [1, 1, 1] white).
//   ghostSamples     Int — flares per bright spot (default 4).
//   ghostSpacing     Float — radial spacing of the ghosts (default 0.25).
//   ghostAttenuation Float — how fast ghosts fade with distance (default 25).
//   strength         Float — final additive strength (default 0.4).
//   opacity          Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[lensflare] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.lensflare !== 'function') {
            throw new Error('[lensflare] THREE.lensflare missing — render_common.mjs must import display/LensflareNode.js');
        }

        const tint = opts.ghostTint ?? [1.0, 1.0, 1.0];
        const u = {
            threshold:    THREE.uniform(opts.threshold        ?? 4.0),
            ghostTint:    THREE.uniform(new THREE.Vector3(tint[0], tint[1], tint[2])),
            ghostSpacing: THREE.uniform(opts.ghostSpacing     ?? 0.25),
            ghostAttn:    THREE.uniform(opts.ghostAttenuation ?? 25.0),
            strength:     THREE.uniform(opts.strength         ?? 0.4),
            opacity:      THREE.uniform(opts.opacity          ?? 1.0),
        };
        const GHOST_SAMPLES = Math.max(1, Math.floor(opts.ghostSamples ?? 4));

        // Pre-bloom hook: same reasoning as anamorphic_flare. lensflare
        // wants raw HDR brightness so its threshold gates real highlights,
        // not bloom-amplified mid-tones.
        globalThis._autoEnhancePreBloomHook = (colorOut /*, sceneDepth, sceneNormal, sceneMR */) => {
            const { Fn, vec4, mix, uv, convertToTexture, float } = THREE;
            const colorTex = convertToTexture(colorOut);
            const flareNode = THREE.lensflare(colorTex, {
                threshold:               u.threshold,
                ghostTint:               u.ghostTint,
                ghostSamples:            float(GHOST_SAMPLES),
                ghostSpacing:            u.ghostSpacing,
                ghostAttenuationFactor:  u.ghostAttn,
            });
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const flares = convertToTexture(flareNode).sample(uv());
                const composed = orig.rgb.add(flares.rgb.mul(u.strength));
                return mix(orig, vec4(composed, orig.a), u.opacity);
            })();
        };

        return {
            uniforms: u,
            update() {},
            setTint(c)      { u.ghostTint.value.set(c[0], c[1], c[2]); },
            setThreshold(v) { u.threshold.value = v; },
        };
    }

    globalThis.LensflareFX = { applyTo };
    console.log('[lensflare] LensflareFX.applyTo registered');
})();
