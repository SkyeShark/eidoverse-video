// hash_blur.js — wraps three's `hashBlur()` (display/hashBlur.js).
// Random-pattern blur — single pass, samples in a hash-randomised
// pattern. Result has a slight noisy / dreamy quality. Cheaper than
// Gaussian for similar perceived blur amount, but with characteristic
// graininess that reads as artistic (good for dreamy / impressionistic).
//
// Public API: HashBlurFX.applyTo({ opts });
//
// Recognised opts:
//   amount   Float — blur radius [0..0.3 useful range] (default 0.05).
//   repeats  Float — sample count per pixel (default 45).
//                    Higher = smoother (less grainy), more cost.
//   opacity  Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[hash_blur] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.hashBlur !== 'function') {
            throw new Error('[hash_blur] THREE.hashBlur missing — render_common.mjs must import display/hashBlur.js');
        }

        const u = {
            amount:  THREE.uniform(opts.amount  ?? 0.05),
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };
        const REPEATS = Math.max(8, Math.floor(opts.repeats ?? 45));

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec4, mix, uv, convertToTexture, float } = THREE;
            const colorTex = convertToTexture(colorOut);
            const blurred = THREE.hashBlur(colorTex, u.amount, {
                repeats: float(REPEATS),
            });
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const bCol = convertToTexture(blurred).sample(uv());
                return mix(orig, vec4(bCol.rgb, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.HashBlurFX = { applyTo };
    console.log('[hash_blur] HashBlurFX.applyTo registered');
})();
