// box_blur.js — wraps three's `boxBlur()` (display/boxBlur.js).
// Cheap single-pass box blur — blockier than Gaussian but faster.
// Use for performance-restricted softening; pair `separation` to widen
// without sample cost.
//
// Public API: BoxBlurFX.applyTo({ opts });
//
// Recognised opts:
//   size       Int — kernel half-size [1..3] (default 1 → 3x3 kernel).
//                    Larger = quadratic cost; prefer separation for wider blur.
//   separation Int — pixel spacing between kernel taps (default 1).
//                    Higher = wider blur same cost.
//   opacity    Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[box_blur] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.boxBlur !== 'function') {
            throw new Error('[box_blur] THREE.boxBlur missing — render_common.mjs must import display/boxBlur.js');
        }

        const u = {
            opacity: THREE.uniform(opts.opacity ?? 1.0),
        };
        const SIZE       = Math.max(1, Math.min(3, Math.floor(opts.size ?? 1)));
        const SEPARATION = Math.max(1, Math.floor(opts.separation ?? 1));

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const { Fn, vec4, mix, uv, convertToTexture, int } = THREE;
            const colorTex = convertToTexture(colorOut);
            const blurred = THREE.boxBlur(colorTex, {
                size:       int(SIZE),
                separation: int(SEPARATION),
            });
            return Fn(() => {
                const orig = colorTex.sample(uv());
                const bCol = convertToTexture(blurred).sample(uv());
                return mix(orig, vec4(bCol.rgb, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.BoxBlurFX = { applyTo };
    console.log('[box_blur] BoxBlurFX.applyTo registered');
})();
