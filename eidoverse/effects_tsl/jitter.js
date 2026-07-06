// jitter.js — TSL port of custom_effects.js::jitter.
// Per-frame whole-frame RGB-shift driven by a fast-advecting noise
// sample. The shift's strength is `pow(noise, 8)` so most frames are
// quiet and occasional bursts kick a hard chromatic offset. Looks
// like a shaky tape transport / signal jitter.
//
// Public API:
//   JitterFX.applyTo({ opts });
//
// Options:
//   speed      float — noise advection rate (default 10.0)
//   amplitude  float — max channel offset in UV units (default 0.2)
//   opacity    float — final blend with original (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[jitter] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const { uniform, Fn, vec2, vec4, float, uv, sin, fract, mix, pow } = THREE;

        const u = {
            time:       uniform(0),
            speed:      uniform(opts.speed     ?? 10.0),
            amplitude:  uniform(opts.amplitude ?? 0.2),
            opacity:    uniform(opts.opacity   ?? 1.0),
        };

        // Hash-based 2D noise — replacement for the reference's tNoise
        // 256px wraparound texture. We use a 4-channel hash so we can
        // mimic the reference's noise.x/y/z/w channel access.
        const hash4 = (p) => {
            // Four independent hash channels from one seed pair.
            const a = fract(sin(p.x.mul(127.1).add(p.y.mul(311.7))).mul(43758.5453));
            const b = fract(sin(p.x.mul(269.5).add(p.y.mul(183.3))).mul(13257.13));
            const c = fract(sin(p.x.mul(419.2).add(p.y.mul(371.9))).mul(28371.59));
            const d = fract(sin(p.x.mul(531.7).add(p.y.mul(207.4))).mul(91234.71));
            return vec4(a, b, c, d);
        };

        const vec4pow = (v, p) => vec4(pow(v.x, p), pow(v.y, p), pow(v.z, p), v.w);

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const origIn = colorTex.sample(uvBase);

                    // Single noise sample per frame (uv is whole-frame
                    // constant, advancing in time).
                    const noiseSeed = vec2(
                        u.speed.mul(u.time),
                        u.speed.mul(u.time).mul(2.0).div(25.0),
                    );
                    const noise = hash4(noiseSeed);
                    const shift = vec4pow(noise, 8.0).mul(
                        vec4(u.amplitude, u.amplitude, u.amplitude, 1.0),
                    );
                    // signed shift = shift * (2*shift.w - 1)
                    const sShift = shift.mul(shift.w.mul(2.0).sub(1.0));
                    const rs = vec2(sShift.x, sShift.y.negate());
                    const gs = vec2(sShift.y, sShift.z.negate());
                    const bs = vec2(sShift.z, sShift.x.negate());
                    const r = colorTex.sample(uvBase.add(rs)).x;
                    const g = colorTex.sample(uvBase.add(gs)).y;
                    const b = colorTex.sample(uvBase.add(bs)).z;
                    const effect = vec4(r, g, b, 1.0);
                    return mix(origIn, effect, u.opacity);
                })();
            },
        };
    }

    function applyTo(args) {
        const opts = (args && args.opts) ?? args ?? {};
        const built = buildHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            uniforms: built.uniforms,
        };
    }

    globalThis.JitterFX = { applyTo };
    console.log('[jitter] JitterFX.applyTo registered');
})();
