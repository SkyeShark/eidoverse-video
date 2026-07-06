// radial_blur.js — wraps three's `radialBlur()` (display/radialBlur.js).
// Circular blur radiating from a center point. Useful for fake light
// shafts ("god rays" without real geometry), zoom-blur action effects,
// or "looking through a kaleidoscope" stylization.
//
// Public API: RadialBlurFX.applyTo({ opts });
//
// Recognised opts:
//   centerX  Float — screen-uv center X [0..1] (default 0.5).
//   centerY  Float — screen-uv center Y [0..1] (default 0.5).
//   weight   Float — base sample weight [0..1] (default 0.9).
//   decay    Float — per-iteration decay [0..1] (default 0.95).
//                    Higher count needs higher decay to avoid darkening.
//   count    Int   — iteration count [16..64] (default 32).
//   exposure Float — exposure scale on the blur output (default 5.0).
//                    Note: high default because blur naturally darkens.
//                    For autoenhance HDR you may want to drop to 1-2.
//   opacity  Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[radial_blur] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.radialBlur !== 'function') {
            throw new Error('[radial_blur] THREE.radialBlur missing — render_common.mjs must import display/radialBlur.js');
        }

        const u = {
            centerX:  THREE.uniform(opts.centerX  ?? 0.5),
            centerY:  THREE.uniform(opts.centerY  ?? 0.5),
            weight:   THREE.uniform(opts.weight   ?? 0.9),
            decay:    THREE.uniform(opts.decay    ?? 0.95),
            // Lower default exposure than three's 5.0 because we feed
            // HDR autoenhance output — exposure*5 on already-bright HDR
            // blows highlights to white.
            exposure: THREE.uniform(opts.exposure ?? 1.5),
            opacity:  THREE.uniform(opts.opacity  ?? 1.0),
        };
        const COUNT = Math.max(8, Math.floor(opts.count ?? 32));

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec2, vec4, mix, uv, convertToTexture } = THREE;
            const colorTex = convertToTexture(colorOut);
            const blurred = THREE.radialBlur(colorTex, {
                center:   vec2(u.centerX, u.centerY),
                weight:   u.weight,
                decay:    u.decay,
                count:    THREE.int(COUNT),
                exposure: u.exposure,
            });
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const bCol = convertToTexture(blurred).sample(uv());
                return mix(orig, vec4(bCol.rgb, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.RadialBlurFX = { applyTo };
    console.log('[radial_blur] RadialBlurFX.applyTo registered');
})();
