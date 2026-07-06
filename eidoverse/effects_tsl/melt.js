// melt.js — TSL port of custom_effects.js::melt.
// HSV-driven swirl: pixel rotation is keyed by hue + screen-angle,
// rotation amount keyed by saturation. Saturated colour patches melt
// more than grey areas, producing slow rotational eddies that smear
// bright colours through the frame.
//
// Public API:
//   MeltFX.applyTo({ opts });
//
// Options:
//   speed    float — overall eddy rotation speed (default 0.7)
//   swirl    float — distortion amount per step (default 0.2)
//   opacity  float — final blend with original (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[melt] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv,
            sin, cos, atan, log, max, min, mix, step, abs,
        } = THREE;

        const u = {
            time:    uniform(0),
            speed:   uniform(opts.speed   ?? 0.7),
            swirl:   uniform(opts.swirl   ?? 0.2),
            opacity: uniform(opts.opacity ?? 1.0),
        };

        // RGB → HSV (IQ-style mix-based conversion). Returns vec3 (h, s, v).
        const rgb2hsv = (c) => {
            const K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
            const p = mix(
                vec4(c.b, c.g, K.w, K.z),
                vec4(c.g, c.b, K.x, K.y),
                step(c.b, c.g),
            );
            const q = mix(
                vec4(p.x, p.y, p.w, c.r),
                vec4(c.r, p.y, p.z, p.x),
                step(p.x, c.r),
            );
            const d = q.x.sub(min(q.w, q.y));
            const e = float(1e-10);
            return vec3(
                abs(q.z.add(q.w.sub(q.y).div(d.mul(6).add(e)))),
                d.div(q.x.add(e)),
                q.x,
            );
        };

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const origIn = colorTex.sample(uvBase);
                    const hsv = rgb2hsv(origIn.rgb);

                    const ctr = uvBase.sub(0.5);
                    const angle = hsv.x.add(atan(ctr.y, ctr.x)).add(u.time.mul(0.1));
                    const cs = cos(angle);
                    const sn = sin(angle);
                    // R * vec2(radius, 0) — 2x2 rotation applied to (r, 0)
                    // gives (r*cos, r*sin). We multiply by hsv.y after.
                    const radius = log(
                        max(sin(u.time.mul(u.speed)).mul(0.5).add(0.3), 0)
                            .mul(u.swirl).add(1.0),
                    );
                    const offset = vec2(cs.mul(radius), sn.mul(radius)).mul(hsv.y);
                    const col = colorTex.sample(uvBase.add(offset)).rgb;
                    return mix(origIn, vec4(col, origIn.a), u.opacity);
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

    globalThis.MeltFX = { applyTo };
    console.log('[melt] MeltFX.applyTo registered');
})();
