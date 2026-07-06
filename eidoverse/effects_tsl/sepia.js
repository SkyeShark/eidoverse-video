// sepia.js — wraps three's `sepia()` TSL Fn (display/Sepia.js).
// Old-photo brown-tint colour grading.
//
// Public API: SepiaFX.applyTo({ opts });
//
// Recognised opts:
//   amount   Float — blend toward sepia [0..1] (default 1.0 = full sepia).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[sepia] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.sepia !== 'function') {
            throw new Error('[sepia] THREE.sepia missing — render_common.mjs must import display/Sepia.js');
        }

        const u = {
            amount:  THREE.uniform(opts.amount  ?? 1.0),
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec4, mix, uv, convertToTexture } = THREE;
            const colorTex = convertToTexture(colorOut);
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const sepiaCol = THREE.sepia(orig.rgb);
                const blended = mix(orig.rgb, sepiaCol, u.amount);
                return mix(orig, vec4(blended, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.SepiaFX = { applyTo };
    console.log('[sepia] SepiaFX.applyTo registered');
})();
