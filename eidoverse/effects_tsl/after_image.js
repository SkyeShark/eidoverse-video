// after_image.js — wraps three's `afterImage()` (display/AfterImageNode.js).
// Frame-feedback temporal trail: previous-frame contribution dampens
// over time, producing motion smear / persistence-of-vision look.
//
// Public API: AfterImageFX.applyTo({ opts });
//
// Recognised opts:
//   damp     Float — feedback persistence [0..1] (default 0.96).
//                    Higher = longer trails, lower = quicker fade.
//   opacity  Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[after_image] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.afterImage !== 'function') {
            throw new Error('[after_image] THREE.afterImage missing — render_common.mjs must import display/AfterImageNode.js');
        }

        const u = {
            damp:    THREE.uniform(opts.damp    ?? 0.96),
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec4, mix, uv, convertToTexture } = THREE;
            const colorTex = convertToTexture(colorOut);
            const trailNode = THREE.afterImage(colorTex, u.damp);
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const trailed = convertToTexture(trailNode).sample(uv());
                return mix(orig, vec4(trailed.rgb, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.AfterImageFX = { applyTo };
    console.log('[after_image] AfterImageFX.applyTo registered');
})();
