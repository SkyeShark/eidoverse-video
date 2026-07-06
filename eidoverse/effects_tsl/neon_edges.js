// neon_edges.js — TSL port of custom_effects.js::neon_edges.
// 4-tap luminance Sobel-ish edge detector. Edges are replaced with a
// glowing tinted color, with a softer halo around the core. Looks like
// neon signs tracing silhouettes.
//
// Public API:
//   NeonEdgesFX.applyTo({ opts });
//
// Options:
//   glowColor [r,g,b] — edge colour (default [1.0, 0.2, 0.8] hot pink)
//   threshold float   — edge-magnitude cutoff (default 0.05)
//   strength  float   — glow intensity multiplier (default 1.0)
//   opacity   float   — final blend with original (default 1.0)
//   width/height int  — output res (defaults to globalThis.WIDTH/HEIGHT)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[neon_edges] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv,
            abs, dot, smoothstep, mix,
        } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1280;
        const h = opts.height ?? globalThis.HEIGHT ?? 720;
        const glow = opts.glowColor ?? [1.0, 0.2, 0.8];

        const u = {
            iResolution: uniform(new THREE.Vector2(w, h)),
            glowColor:   uniform(new THREE.Vector3(glow[0], glow[1], glow[2])),
            threshold:   uniform(opts.threshold ?? 0.05),
            strength:    uniform(opts.strength  ?? 1.0),
            opacity:     uniform(opts.opacity   ?? 1.0),
        };

        const luma = (rgb) => dot(rgb, vec3(0.299, 0.587, 0.114));

        return {
            uniforms: u,
            update(/* t */) {},
            setResolution(width, height) {
                u.iResolution.value.set(width, height);
            },
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const orig = colorTex.sample(uvBase);
                    const px = vec2(1).div(u.iResolution);
                    const lC = luma(colorTex.sample(uvBase).rgb);
                    const lL = luma(colorTex.sample(uvBase.sub(vec2(px.x, 0))).rgb);
                    const lR = luma(colorTex.sample(uvBase.add(vec2(px.x, 0))).rgb);
                    const lU = luma(colorTex.sample(uvBase.sub(vec2(0, px.y))).rgb);
                    const lD = luma(colorTex.sample(uvBase.add(vec2(0, px.y))).rgb);
                    const e = abs(lC.mul(4).sub(lL).sub(lR).sub(lU).sub(lD));
                    const core = smoothstep(u.threshold, u.threshold.mul(2.0), e);
                    const halo = smoothstep(u.threshold.mul(0.3), u.threshold.mul(1.5), e);
                    const glowAdd = u.glowColor.mul(core.add(halo.mul(0.5))).mul(u.strength);
                    const col = orig.rgb.add(glowAdd);
                    return mix(orig, vec4(col, 1.0), u.opacity);
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
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.NeonEdgesFX = { applyTo };
    console.log('[neon_edges] NeonEdgesFX.applyTo registered');
})();
