// rgb_shift.js — wraps three's `rgbShift()` (display/RGBShiftNode.js).
// Per-channel screen-space offset (R/G/B sampled at slightly different
// uvs). Different from chromatic_aberration_alpha (which is radial-
// distance-based fringing) — this is a uniform directional split,
// classic "glitch" / "bad TV" look.
//
// Public API: RGBShiftFX.applyTo({ opts });
//
// Recognised opts:
//   amount   Float — pixel offset magnitude (default 0.005).
//   angle    Float — direction of the shift in radians (default 0 = horizontal).
//   opacity  Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[rgb_shift] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.rgbShift !== 'function') {
            throw new Error('[rgb_shift] THREE.rgbShift missing — render_common.mjs must import display/RGBShiftNode.js');
        }

        const u = {
            amount:  THREE.uniform(opts.amount  ?? 0.005),
            angle:   THREE.uniform(opts.angle   ?? 0.0),
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec4, mix, uv, convertToTexture } = THREE;
            const colorTex = convertToTexture(colorOut);
            const shifted = THREE.rgbShift(colorTex, u.amount, u.angle);
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const sCol = convertToTexture(shifted).sample(uv());
                return mix(orig, vec4(sCol.rgb, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.RGBShiftFX = { applyTo };
    console.log('[rgb_shift] RGBShiftFX.applyTo registered');
})();
