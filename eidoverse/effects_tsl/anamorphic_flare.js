// anamorphic_flare.js — wraps three's `anamorphic()` TSL built-in.
// Adds horizontal blue-tinted flares from bright (over-threshold) pixels,
// mimicking the lens-flare streaks you get on anamorphic cinema lenses.
//
// Public API: AnamorphicFlareFX.applyTo({ opts });
//
// Recognised opts:
//   threshold  Float — luminance cutoff (default 0.9). Lower → more pixels
//                      flare, larger overall flare presence.
//   scale      Float — vertical pixel-stretch of the flare (default 3).
//   samples    Int   — number of taps along the flare axis (default 32).
//                      Higher = longer/smoother flares, more GPU cost.
//   colorR/G/B Floats — per-channel flare tint (defaults [0.1, 0.0, 1.0]
//                      = blue, classic anamorphic look). Set to e.g.
//                      [1, 0.4, 0.05] for warm orange flares.
//   strength   Float — multiplier on the flare contribution before mixing
//                      back over the scene (default 1.0).
//   opacity    Float — final blend (default 1.0).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[anamorphic_flare] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        if (typeof THREE.anamorphic !== 'function') {
            throw new Error(
                '[anamorphic_flare] THREE.anamorphic missing — render_common.mjs must import display/AnamorphicNode.js',
            );
        }

        const colorArr = opts.color ?? [0.1, 0.0, 1.0];
        const u = {
            // Pre-bloom HDR luminance ranges: typical sky ~1-3, sun-lit
            // clouds ~3-5, sun disk / explosion fireball ~5-50. Three's
            // anamorphic uses
            //   contribution = color × max(luminance(pixel) - threshold, 0)
            // so threshold=2.0 ignores ambient sky and catches actual
            // highlights (sun, fireball, specular peaks). When we used
            // POST-bloom input the threshold needed to be ~15 because
            // bloom amplified everything 3-5×; pre-bloom we can use the
            // sane default.
            threshold: THREE.uniform(opts.threshold ?? 3.0),
            // Tighter scale (was 3.0) so streaks are SHORT lines from
            // each highlight, not full-screen vertical washes that tint
            // half the image blue.
            scale:     THREE.uniform(opts.scale     ?? 1.5),
            // Strength dialed to "subtle but clearly visible streaks"
            // — high enough that toggling the effect is obvious, low
            // enough that the rest of the scene reads unchanged.
            strength:  THREE.uniform(opts.strength  ?? 0.6),
            opacity:   THREE.uniform(opts.opacity   ?? 1.0),
            color:     THREE.uniform(new THREE.Vector3(colorArr[0], colorArr[1], colorArr[2])),
        };
        const SAMPLES = Math.max(1, Math.floor(opts.samples ?? 32));

        // Use the PRE-BLOOM hook slot (not the regular colour-hook). Bloom
        // runs AFTER us in the autoenhance pipeline; if anamorphic ran
        // post-bloom, it'd see already-amplified bright pixels and either
        // miss real highlights (high threshold) or saturate the whole
        // image violet (low threshold). Pre-bloom we see clean raw HDR;
        // bloom then softens our flare streaks like a real lens.
        globalThis._autoEnhancePreBloomHook = (colorOut /*, sceneDepth, sceneNormal, sceneMR */) => {
            const { Fn, vec3, vec4, mix, uv, convertToTexture } = THREE;
            const colorTex = convertToTexture(colorOut);
            const flareNode = THREE.anamorphic(colorTex, u.threshold, u.scale, SAMPLES);
            flareNode.colorNode = u.color;

            return Fn(() => {
                const screenUV = uv();
                const orig = colorTex.sample(screenUV);
                // anamorphic() output is the flare ALONE (over black bg).
                // Add it onto the original raw HDR scene; bloom downstream
                // will then see (scene + flare) and amplify accordingly.
                const flare = convertToTexture(flareNode).sample(screenUV);
                const composed = orig.rgb.add(flare.rgb.mul(u.strength));
                return mix(orig, vec4(composed, orig.a), u.opacity);
            })();
        };

        return {
            uniforms: u,
            update(/* t */) {},
            setColor(c) { u.color.value.set(c[0], c[1], c[2]); },
            setThreshold(v) { u.threshold.value = v; },
        };
    }

    globalThis.AnamorphicFlareFX = { applyTo };
    console.log('[anamorphic_flare] AnamorphicFlareFX.applyTo registered');
})();
