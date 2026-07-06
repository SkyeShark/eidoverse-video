// bleach_bypass.js — wraps three's `bleach()` TSL Fn (display/BleachBypass.js).
// Cinema "bleach bypass" film process: high-contrast desaturated look with
// crushed shadows and silver-highlight halos. Common in war / gritty films
// (Saving Private Ryan, Three Kings).
//
// Public API: BleachBypassFX.applyTo({ opts });
//
// Recognised opts:
//   amount   Float — blend toward bleached [0..1] (default 1.0).
//   opacity  Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[bleach_bypass] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.bleach !== 'function') {
            throw new Error('[bleach_bypass] THREE.bleach missing — render_common.mjs must import display/BleachBypass.js');
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
                const bleached = THREE.bleach(orig.rgb, u.amount);
                return mix(orig, vec4(bleached, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.BleachBypassFX = { applyTo };
    console.log('[bleach_bypass] BleachBypassFX.applyTo registered');
})();
