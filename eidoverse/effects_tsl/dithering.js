// dithering.js — Bayer ordered dithering using the three/addons
// `bayerDither` helper. Adds structured 4×4 (or 16×16 via bayer16)
// noise before colour quantisation to break visible banding in
// gradients while keeping a clean retro look. Replaces a hand-rolled
// 8×8 Bayer matrix in the original custom_effects.dithering.
//
// Public API:
//   DitheringFX.applyTo({ opts });
//
// Options:
//   levels  float — quantisation steps per channel (default 8)
//   opacity float — final blend (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[dithering] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.bayerDither !== 'function') {
            throw new Error('[dithering] THREE.bayerDither missing — render_common.mjs must import addons/tsl/math/Bayer.js');
        }

        const u = {
            levels:  THREE.uniform(opts.levels  ?? 8.0),
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };

        globalThis._autoEnhanceColorHook = (colorOut /*, sceneDepth, sceneNormal, sceneMR */) => {
            const {
                Fn, vec3, vec4, uv, floor, mix, sqrt, convertToTexture, bayerDither,
            } = THREE;
            const baseTex = convertToTexture(colorOut);

            return Fn(() => {
                const uvNode = uv();
                const orig = baseTex.sample(uvNode);
                // The autoenhance hook receives linear scene-referred
                // colour. Quantising in linear produces non-perceptual
                // bands — after ACES + sRGB downstream the result
                // looks hue-shifted (a dark blue floor lands on the
                // wrong band and tone-maps to olive-yellow). Move into
                // a perceptual-ish space with a gamma-2 sqrt, dither +
                // quantise there, then square back so the value going
                // into renderOutput is still linear and ACES + sRGB
                // does the right thing on top. This is the same trick
                // most retro shaders use to "dither in screen space".
                const perceptual = sqrt(orig.rgb);
                const dithered = bayerDither(perceptual, u.levels);
                // Use levels-1 quant so the brightest band reaches 1.0
                // (otherwise white tops out at (levels-1)/levels and
                // everything darkens slightly).
                const stepCount = u.levels.sub(1);
                const quantised = floor(dithered.mul(stepCount).add(0.5)).div(stepCount);
                const linearOut = quantised.mul(quantised);
                const out = vec4(linearOut, orig.a);
                return mix(orig, out, u.opacity);
            })();
        };

        return {
            uniforms: u,
            update(/* t */) { /* stateless */ },
        };
    }

    globalThis.DitheringFX = { applyTo };
    console.log('[dithering] DitheringFX.applyTo registered');
})();
