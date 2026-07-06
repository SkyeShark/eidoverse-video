// full_toon.js — TSL port of custom_effects.js::full_toon. Cel shading
// with depth-ramped bands + 3-stop palette tint, plus a depth+normal
// sobel outline (same algorithm as blueprint.js's outlineEdge).
//
// Pipeline per pixel:
//   1. depth-aware 9-tap celBlur — smooths out texture detail (dirt,
//      panel-line micro contrast) so the band quantizer doesn't shatter
//      smooth surfaces into noisy bands. depth weighting skips taps
//      that cross silhouettes so edges stay crisp.
//   2. Luminance compute → contrast push → bandStep quantize at L
//      levels (depth-ramped: nearLevels near, farLevels far).
//   3. Hue-preserving rgb rescale (smoothed * stepped/lum).
//   4. 3-stop tint palette: shadowTint → midtoneTint → highlightTint.
//      hueShift mixes between (1,1,1) and the tint multiplier so 0
//      preserves original hue, 1 pushes fully to palette.
//   5. Outline: 3×3 depth-difference + normal-difference, pow falloff,
//      mixed toward outlineColor.
//   6. Final mix(orig, toon, opacity).
//
// Public API: FullToonFX.applyTo({ camera, opts });

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[full_toon] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const camera = args.camera;
        if (!camera) throw new Error('FullToonFX.applyTo: opts.camera required');
        const opts = args.opts ?? args;

        const shadow    = opts.shadowTint    ?? [0.16, 0.20, 0.42];
        const midtone   = opts.midtoneTint   ?? [0.52, 0.48, 0.56];
        const highlight = opts.highlightTint ?? [1.00, 0.96, 0.88];
        const outline   = opts.outlineColor  ?? [0.05, 0.05, 0.08];

        const u = {
            time:              THREE.uniform(0),
            iResolution:       THREE.uniform(new THREE.Vector2(
                opts.width  ?? globalThis.WIDTH  ?? 1280,
                opts.height ?? globalThis.HEIGHT ?? 720,
            )),
            opacity:           THREE.uniform(opts.opacity      ?? 1.0),
            nearLevels:        THREE.uniform(opts.nearLevels   ?? 4.0),
            farLevels:         THREE.uniform(opts.farLevels    ?? 2.0),
            bandSoftness:      THREE.uniform(opts.bandSoftness ?? 0.015),
            hueShift:          THREE.uniform(opts.hueShift     ?? 0.0),
            // Saturation boost: 1.0 = identity, >1 pulls colours away
            // from greyscale toward original chroma. Default 1.4 makes
            // toon look "colour poppy" — saturated cel-shaded look.
            saturation:        THREE.uniform(opts.saturation   ?? 1.4),
            contrast:          THREE.uniform(opts.contrast     ?? 1.0),
            smoothRadius:      THREE.uniform(opts.smoothRadius ?? 3.0),
            shadowTint:        THREE.uniform(new THREE.Vector3(shadow[0],    shadow[1],    shadow[2])),
            midtoneTint:       THREE.uniform(new THREE.Vector3(midtone[0],   midtone[1],   midtone[2])),
            highlightTint:     THREE.uniform(new THREE.Vector3(highlight[0], highlight[1], highlight[2])),
            outlineColor:      THREE.uniform(new THREE.Vector3(outline[0],   outline[1],   outline[2])),
            outlineStrength:   THREE.uniform(opts.outlineStrength     ?? 1.0),
            outlineThreshold:  THREE.uniform(opts.outlineThreshold    ?? 0.5),
            outlineSharpness:  THREE.uniform(opts.outlineSharpness    ?? 5.0),
            outlineDepthW:     THREE.uniform(opts.outlineDepthWeight  ?? 0.5),
            outlineNormalW:    THREE.uniform(opts.outlineNormalWeight ?? 1.0),
            camNear:           THREE.uniform(camera.near),
            camFar:            THREE.uniform(camera.far),
        };

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal /*, sceneMR */) => {
            const {
                Fn, vec2, vec3, vec4, float, uv, fract, floor, abs, mix, max, min, dot, length, pow,
                clamp, smoothstep, step, convertToTexture,
            } = THREE;

            const baseTex   = convertToTexture(colorOut);
            const depthTex  = convertToTexture(sceneDepth);
            const normalTex = sceneNormal ? convertToTexture(sceneNormal) : null;

            return Fn(() => {
                const uvNode = uv();
                const orig = baseTex.sample(uvNode);
                const px = vec2(1).div(u.iResolution);

                const linDepth = (uvN) => {
                    const d = depthTex.sample(uvN).r;
                    return float(2).mul(u.camNear).div(
                        u.camFar.add(u.camNear).sub(d.mul(u.camFar.sub(u.camNear)))
                    );
                };
                const sampleN = (off) => {
                    if (!normalTex) return vec3(0, 0, 1);
                    return normalTex.sample(uvNode.add(off.mul(px))).rgb.mul(2).sub(1);
                };

                const dC = max(linDepth(uvNode), 0.0001);

                // ---- celBlur: 9-tap depth-aware gaussian over the
                // ORIGINAL colour. Smooths material noise but preserves
                // silhouettes (depth-divergent taps zero-weighted).
                const radius = u.smoothRadius;
                const offs = [
                    [-1, -1, 1], [ 0, -1, 2], [ 1, -1, 1],
                    [-1,  0, 2], [ 0,  0, 4], [ 1,  0, 2],
                    [-1,  1, 1], [ 0,  1, 2], [ 1,  1, 1],
                ];
                const sumRGB = vec3(0).toVar();
                const wsum   = float(0).toVar();
                for (const [ox, oy, kw] of offs) {
                    const ouv = uvNode.add(vec2(ox, oy).mul(px).mul(radius));
                    const tapD = linDepth(ouv);
                    const depthW = float(1).sub(smoothstep(0.001, 0.02, abs(tapD.sub(dC))));
                    const w = depthW.mul(kw);
                    sumRGB.addAssign(baseTex.sample(ouv).rgb.mul(w));
                    wsum.addAssign(w);
                }
                const smoothed = sumRGB.div(max(wsum, 0.0001));

                // ---- Band quantize on luminance with depth-ramped levels.
                const L = max(mix(u.nearLevels, u.farLevels, clamp(dC, 0, 1)), 1.0);
                const lum = clamp(dot(smoothed, vec3(0.299, 0.587, 0.114)), 0, 1);
                const adj = clamp(lum.sub(0.5).mul(u.contrast).add(0.5), 0, 1);
                // bandStep(x, bands, softness) — soft-edged posterize.
                const s = adj.mul(L);
                const stepped = floor(s).add(smoothstep(0.0, max(u.bandSoftness, 0.0001), fract(s))).div(L);

                // ---- Hue-preserving rgb rescale: scene's chroma stays,
                // brightness gets snapped to band levels.
                const scale = stepped.div(max(lum, 0.001));
                const baseCelRaw = clamp(smoothed.mul(scale), 0, 1.5);
                // Saturation boost: pull colours away from greyscale to
                // give the cel-shaded scene a colour-poppy look. Mix
                // the rescaled cel with its luminance — `saturation > 1`
                // extrapolates beyond original chroma, < 1 desaturates.
                const baseCelLum = dot(baseCelRaw, vec3(0.299, 0.587, 0.114));
                const baseCel = clamp(
                    mix(vec3(baseCelLum), baseCelRaw, u.saturation),
                    0, 1.5,
                );

                // ---- 3-stop tint palette. Below 0.5 stepped: shadow→mid;
                // above: mid→highlight. Mix selector uses step(0.5, stepped)
                // since TSL's If inside an Fn return value path is awkward.
                const tintLow  = mix(u.shadowTint,  u.midtoneTint,   smoothstep(float(0.0), float(0.5), stepped));
                const tintHigh = mix(u.midtoneTint, u.highlightTint, smoothstep(float(0.5), float(1.0), stepped));
                const tint     = mix(tintLow, tintHigh, step(float(0.5), stepped));
                const tintLum  = max(dot(tint, vec3(0.299, 0.587, 0.114)), 0.001);
                const tintMult = tint.div(tintLum);
                const colCel   = baseCel.mul(mix(vec3(1.0), tintMult, u.hueShift));

                // ---- Outline: 3×3 depth + normal pairs (same algo as
                // blueprint's outlineEdge but with both terms summed
                // and a pow falloff).
                const d0 = linDepth(uvNode.add(vec2(-1, -1).mul(px)));
                const d1 = linDepth(uvNode.add(vec2( 0, -1).mul(px)));
                const d2 = linDepth(uvNode.add(vec2( 1, -1).mul(px)));
                const d3 = linDepth(uvNode.add(vec2(-1,  0).mul(px)));
                const d5 = linDepth(uvNode.add(vec2( 1,  0).mul(px)));
                const d6 = linDepth(uvNode.add(vec2(-1,  1).mul(px)));
                const d7 = linDepth(uvNode.add(vec2( 0,  1).mul(px)));
                const d8 = linDepth(uvNode.add(vec2( 1,  1).mul(px)));
                const dDepth = abs(d1.sub(d7)).add(abs(d5.sub(d3)))
                    .add(abs(d0.sub(d8))).add(abs(d2.sub(d6))).div(dC);

                const n0 = sampleN(vec2(-1, -1));
                const n1 = sampleN(vec2( 0, -1));
                const n2 = sampleN(vec2( 1, -1));
                const n3 = sampleN(vec2(-1,  0));
                const n5 = sampleN(vec2( 1,  0));
                const n6 = sampleN(vec2(-1,  1));
                const n7 = sampleN(vec2( 0,  1));
                const n8 = sampleN(vec2( 1,  1));
                const dNormal = max(float(0), float(1).sub(dot(n1, n7)))
                    .add(max(float(0), float(1).sub(dot(n5, n3))))
                    .add(max(float(0), float(1).sub(dot(n0, n8))))
                    .add(max(float(0), float(1).sub(dot(n2, n6))));

                const signal = u.outlineDepthW.mul(dDepth).add(u.outlineNormalW.mul(dNormal));
                const edge = clamp(
                    pow(max(signal.sub(u.outlineThreshold), 0), u.outlineSharpness).mul(u.outlineStrength),
                    0, 1,
                );
                const colInked = mix(colCel, u.outlineColor, edge);

                return mix(orig, vec4(clamp(colInked, 0, 1), orig.a), u.opacity);
            })();
        };

        return {
            uniforms: u,
            update(/* t */) {
                u.camNear.value = camera.near;
                u.camFar.value  = camera.far;
            },
            setResolution(width, height) { u.iResolution.value.set(width, height); },
        };
    }

    globalThis.FullToonFX = { applyTo };
    console.log('[full_toon] FullToonFX.applyTo registered');
})();
