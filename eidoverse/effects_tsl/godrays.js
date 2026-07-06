// godrays.js — wraps three's `godrays()` (display/GodraysNode.js).
// Volumetric light shafts radiating from a directional / point light's
// screen-space position, occluded by scene depth so god rays only pass
// through gaps in geometry.
//
// Public API: GodraysFX.applyTo({ scene, camera, opts });
//
// Auto-discovers the scene's first DirectionalLight (or the light passed
// via opts.light) and renders rays from its world-space position. Same
// scene-light tracking pattern as volumetric_clouds.
//
// Recognised opts:
//   light          THREE.DirectionalLight | THREE.PointLight — light source
//                    (default: first DirectionalLight in scene).
//   strength       Float — final additive strength of the rays (default 0.5).
//   opacity        Float — final blend (default 1.0).
//   cloudOpacityTex TextureNode (optional) — per-pixel cloud opacity from
//                    volumetric_clouds.getCloudOpacityTex(). When set,
//                    godrays output is multiplied by (1 - opacity) per
//                    pixel so dense clouds occlude the rays. Pattern:
//                      const fx  = applyTo({ effects:'volumetric_clouds', ... });
//                      const gfx = applyTo({ effects:'godrays', opts:{
//                                    godrays: { cloudOpacityTex: fx.getCloudOpacityTex() }
//                                  }});
//                    (Apply clouds first so the texture exists when godrays asks.)

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
        // Mutually exclusive with volumetric_clouds: GodraysNode uses
        // shadow maps for occlusion, but volumetric_clouds is a screen-
        // space post-process and never participates in shadow casting,
        // so combining them produces "rays + uniform glow" rather than
        // proper cloud-shaped shafts. Use volumetric_clouds' built-in
        // cloudShafts opt instead — it raymarches from the sun's screen
        // position through the cloud OPACITY texture, producing real
        // shaft-through-clouds patterns.
        if (globalThis._volumetricCloudsActive) {
            throw new Error(
                '[godrays] cannot stack with volumetric_clouds (screen-space clouds aren\'t in the shadow map). ' +
                'Use opts.volumetric_clouds.cloudShafts instead — same effect, cloud-aware.',
            );
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

        // Optional cloud occlusion — a TextureNode whose alpha channel
        // represents per-pixel cloud opacity (0=clear, 1=opaque cloud).
        // Provided by volumetric_clouds via getCloudOpacityTex().
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
