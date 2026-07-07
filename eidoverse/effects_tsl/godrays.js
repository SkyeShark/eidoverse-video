// godrays.js — wraps three's `godrays()` (display/GodraysNode.js).
// Volumetric light shafts radiating from a directional / point light's
// screen-space position, occluded by scene depth so god rays only pass
// through gaps in geometry.
//
// Public API: GodraysFX.applyTo({ scene, camera, opts });
//
// Auto-discovers the scene's first DirectionalLight (or the light passed
// via opts.light) and renders rays from its world-space position.
//
// (For shafts breaking through a cloudy SKY, prefer the sky system's own
// cloud shafts — they march the actual cloud density. godrays is the tool
// for rays through GEOMETRY gaps: windows, trees, pillars.)
//
// Recognised opts:
//   light          THREE.DirectionalLight | THREE.PointLight — light source
//                    (default: first DirectionalLight in scene).
//   strength       Float — final additive strength of the rays (default 0.5).
//   opacity        Float — final blend (default 1.0).
//   cloudOpacityTex TextureNode (optional) — per-pixel occluder opacity
//                    (0=clear, 1=opaque). When set, godrays output is
//                    multiplied by (1 - opacity) per pixel so dense cover
//                    occludes the rays.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[godrays] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const { scene, camera } = args;
        if (!camera) throw new Error('GodraysFX.applyTo: opts.camera required');
        if (!scene)  throw new Error('GodraysFX.applyTo: opts.scene required (auto-discovers light)');
        const opts = args.opts ?? args;
        if (typeof THREE.godrays !== 'function') {
            throw new Error('[godrays] THREE.godrays missing — render_common.mjs must import display/GodraysNode.js');
        }
        let light = opts.light;
        if (!light) {
            scene.traverse((obj) => {
                if (!light && (obj.isDirectionalLight || obj.isPointLight)) light = obj;
            });
        }
        if (!light) throw new Error('[godrays] no DirectionalLight/PointLight found in scene');

        const u = {
            strength: THREE.uniform(opts.strength ?? 0.5),
            opacity:  THREE.uniform(opts.opacity  ?? 1.0),
        };

        // Optional occluder mask — a TextureNode whose alpha channel
        // represents per-pixel cover opacity (0=clear, 1=opaque).
        const cloudOpacityTex = opts.cloudOpacityTex ?? null;

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth /*, sceneNormal, sceneMR */) => {
            const { Fn, vec4, vec3, float, mix, uv, convertToTexture, clamp } = THREE;
            const colorTex = convertToTexture(colorOut);
            const depthTex = convertToTexture(sceneDepth);
            const raysNode = THREE.godrays(depthTex, camera, light);
            return Fn(() => {
                const screenUV = uv();
                const orig = colorTex.sample(screenUV);
                let rays = convertToTexture(raysNode).sample(screenUV).rgb;
                // Per-pixel cloud occlusion: where clouds are dense
                // (opacity → 1), block the rays. Models the cloud
                // physically blocking the sun beam at this view direction.
                if (cloudOpacityTex) {
                    const opacity = clamp(
                        convertToTexture(cloudOpacityTex).sample(screenUV).a,
                        0, 1,
                    );
                    rays = rays.mul(float(1).sub(opacity));
                }
                const composed = orig.rgb.add(rays.mul(u.strength));
                return mix(orig, vec4(composed, orig.a), u.opacity);
            })();
        };

        return { uniforms: u, update() {} };
    }

    globalThis.GodraysFX = { applyTo };
    console.log('[godrays] GodraysFX.applyTo registered');
})();
