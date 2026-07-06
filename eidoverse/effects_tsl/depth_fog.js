// depth_fog.js — TSL depth-aware fog using the three/addons
// `depthAwareBlend` helper for silhouette-aware fog blending. The
// built-in does a Poisson-disk depth-discontinuity search and pushes
// blend samples away from edges so fog doesn't halo around foreground
// objects. We feed it a fog-density texture computed from view-Z plus a
// 2D noise field (gives volumetric-ish spatial features without an
// actual raymarch).
//
// Trade-off vs the original custom_effects.js depth_fog:
//   - LOST: full volumetric raymarch with worley noise, light scattering,
//           shadow march, height attenuation, wind drift.
//   - KEPT: depth-driven fog density, 2D noise modulation, fog colour,
//           edge-aware silhouette blending (the part the built-in adds).
//
// Public API:
//   DepthFogFX.applyTo({ camera, opts });
//
// Options:
//   color         [r,g,b] — fog tint (default cool grey-blue [0.55, 0.62, 0.72])
//   density       float — exponential falloff rate per unit (default 0.04)
//   noiseAmount   float — 0-1 strength of 2D noise modulation (default 0.4)
//   noiseScale    float — frequency of the noise field (default 6.0)
//   edgeRadius    int — Poisson-disk search radius in pixels (default 2)
//   edgeStrength  float — UV push-away amount (default 2.0)
//   opacity       float — final blend (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[depth_fog] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const camera = args.camera;
        if (!camera) throw new Error('DepthFogFX.applyTo: opts.camera required (depthAwareBlend reads camera.near/far via reference())');
        const opts = args.opts ?? args;
        if (typeof THREE.depthAwareBlend !== 'function') {
            throw new Error('[depth_fog] THREE.depthAwareBlend missing — render_common.mjs must import addons/tsl/display/depthAwareBlend.js');
        }
        if (typeof THREE.perspectiveDepthToViewZ !== 'function') {
            throw new Error('[depth_fog] THREE.perspectiveDepthToViewZ missing');
        }

        const fogCol = opts.color ?? [0.55, 0.62, 0.72];
        const u = {
            density:     THREE.uniform(opts.density     ?? 0.04),
            noiseAmount: THREE.uniform(opts.noiseAmount ?? 0.4),
            noiseScale:  THREE.uniform(opts.noiseScale  ?? 6.0),
            opacity:     THREE.uniform(opts.opacity     ?? 1.0),
            time:        THREE.uniform(0),
            camNear:     THREE.uniform(camera.near),
            camFar:      THREE.uniform(camera.far),
            fogColor:    THREE.uniform(new THREE.Vector3(fogCol[0], fogCol[1], fogCol[2])),
        };

        const edgeRadius   = opts.edgeRadius   ?? 2;
        const edgeStrength = opts.edgeStrength ?? 2.0;

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth /*, sceneNormal, sceneMR */) => {
            const {
                Fn, vec2, vec3, vec4, float, uv, sin, fract, exp, clamp, mix, floor,
                convertToTexture, perspectiveDepthToViewZ, depthAwareBlend,
            } = THREE;
            const baseTex = convertToTexture(colorOut);
            const depthTex = convertToTexture(sceneDepth);

            // RTT a fog-density mask: 1.0 = full fog, 0.0 = no fog.
            // depthAwareBlend treats blendNode as a sampleable texture
            // (.sample(uv).r), so we wrap the density Fn through
            // convertToTexture to get a TextureNode it can read.
            //
            // Smooth-interpolated value noise (hash at integer cells,
            // smoothstep between them) instead of raw per-pixel hash —
            // raw hash drifted hard between frames and looked like
            // jitter even with no time animation. This pattern is
            // spatially smooth and held constant in time so the fog
            // reads as still air, not wind.
            const densityTex = convertToTexture(Fn(() => {
                const uvNode = uv();
                const d = depthTex.sample(uvNode).r;
                const viewZ = perspectiveDepthToViewZ(d, u.camNear, u.camFar);
                const dist = viewZ.negate();      // viewZ is negative in front of camera
                const hash = (p) =>
                    fract(sin(p.x.mul(127.1).add(p.y.mul(311.7))).mul(43758.5453));
                const valueNoise = (p) => {
                    const i = floor(p);
                    const f = p.sub(i);
                    const u2 = f.mul(f).mul(vec2(3).sub(f.mul(2)));   // smoothstep
                    const a = hash(i);
                    const b = hash(i.add(vec2(1, 0)));
                    const c = hash(i.add(vec2(0, 1)));
                    const dh = hash(i.add(vec2(1, 1)));
                    return mix(
                        mix(a, b, u2.x),
                        mix(c, dh, u2.x),
                        u2.y,
                    );
                };
                const noise = valueNoise(uvNode.mul(u.noiseScale));
                const noiseMod = float(1).sub(u.noiseAmount).add(u.noiseAmount.mul(noise));
                const fog = float(1).sub(exp(dist.mul(u.density.negate()).mul(noiseMod)));
                return vec4(clamp(fog, 0, 1));    // .r = mask
            })());

            const fogged = depthAwareBlend(
                baseTex, densityTex, depthTex, camera,
                {
                    blockColor: u.fogColor,         // unused field guard for spec drift
                    blendColor: u.fogColor,
                    edgeRadius: edgeRadius,
                    edgeStrength: edgeStrength,
                },
            );

            return Fn(() => mix(
                baseTex.sample(uv()),
                fogged,
                u.opacity,
            ))();
        };

        return {
            uniforms: u,
            update(t) {
                u.time.value    = t;
                u.camNear.value = camera.near;
                u.camFar.value  = camera.far;
            },
        };
    }

    globalThis.DepthFogFX = { applyTo };
    console.log('[depth_fog] DepthFogFX.applyTo registered');
})();
