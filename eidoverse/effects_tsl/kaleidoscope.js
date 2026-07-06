// kaleidoscope.js — TSL port of custom_effects.js::kaleidoscope.
// Radial mirror / pie-slice symmetry: each pixel is mapped into a
// single segment of a circular pattern, producing the classic
// kaleidoscope multiplied-symmetry look.
//
// Public API:
//   KaleidoscopeFX.applyTo({ opts });
//
// Options:
//   segments  int   — number of mirrored slices (default 6)
//   rotate    float — fixed rotation offset in radians (default 0)
//   opacity   float — final blend with original (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[kaleidoscope] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const {
            uniform, Fn, vec2, vec4, float, uv,
            sin, cos, atan, length, mod, abs, mix, clamp,
        } = THREE;

        const u = {
            segments: uniform(opts.segments ?? 6),
            rotate:   uniform(opts.rotate   ?? 0.0),
            opacity:  uniform(opts.opacity  ?? 1.0),
        };

        return {
            uniforms: u,
            update(/* t */) {},
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const orig = colorTex.sample(uvBase);
                    const p = uvBase.sub(0.5);
                    const r = length(p);
                    const a0 = atan(p.y, p.x).add(u.rotate);
                    const seg = float(6.2831853).div(u.segments);
                    const a1 = mod(a0, seg);
                    const a = abs(a1.sub(seg.mul(0.5)));
                    const np = clamp(
                        vec2(cos(a), sin(a)).mul(r).add(0.5),
                        vec2(0.001),
                        vec2(0.999),
                    );
                    const col = colorTex.sample(np);
                    return mix(orig, vec4(col.rgb, 1.0), u.opacity);
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

    globalThis.KaleidoscopeFX = { applyTo };
    console.log('[kaleidoscope] KaleidoscopeFX.applyTo registered');
})();
