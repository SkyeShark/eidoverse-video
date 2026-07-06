// nuclear_explosion.js — TSL port of the SDF-mushroom-cloud raymarcher.
//
// Mirrors volumetric_clouds.js's hook scaffold:
//   - _autoEnhancePreSSRHook  : composite the explosion over scene pixels
//                               along the view ray (clamped to scene depth)
//   - _autoEnhanceCloudReflectHook : on metallic surfaces, raymarch the
//                               explosion along the reflection direction
//                               and contribute as reflection
//   - _autoEnhanceCloudReflectBlurHook : roughness-weighted blur of the
//                               reflection contribution (same as clouds)
//
// Differences vs volumetric_clouds:
//   - Bounded volume (mushroom cloud SDF) instead of infinite atmosphere
//     shell. Ray ends at min(maxT, sceneDepth) so opaque geometry occludes
//     the explosion correctly.
//   - Density derived from SDF-falloff × multi-octave value noise at
//     advected sample positions.
//   - Heat-to-colour palette: hot core → warm fire → grey smoke as the
//     animation progresses, with full dispersal by loop end.
//
// Public API: NuclearExplosionFX.applyTo({ scene, camera, opts });
//
// Recognised opts:
//   origin       [x, y, z] world position of explosion ground-zero (default [0,0,0]).
//   scale        Float — overall size multiplier (default 1.0).
//                Real-world reference: 1 scene unit ≈ 100 m. So scale=1.0
//                gives a ~900 m mushroom cap with a ~2 km base-surge ring
//                — i.e. a small tactical nuke (W54 ~10 kt class). Bump to
//                ~3-5 for a strategic-yield Hiroshima-style cloud, drop to
//                ~0.5 for a tabletop demo against a 25-30 unit camera.
//   timeOffset   Float — phase offset in seconds. Useful for staggering
//                multiple explosions (default 0).
//   loopSeconds  Float — cycle period (default 20).
//   maxT         Float — maximum view-ray march distance in world units
//                (default 80; bump if scale > 2.0 so the volume tail isn't
//                clipped).
//   surfSteps    Int   — surface-march iterations to find SDF entry (default 64).
//   volSteps     Int   — volumetric-march iterations inside the volume (default 96).
//   reflectSteps Int   — march iterations for the reflection-path contribution (default 48).
//
// Effect stacking: nuclear_explosion + volumetric_clouds compose
// automatically. Apply volumetric_clouds FIRST, then nuclear_explosion —
// the explosion's hooks capture any previously-installed sky / cloud-
// reflect hooks at applyTo() time, call them first to get the cloud-
// rendered scene, then composite the mushroom volume over that. So
// view-ray sky pixels get clouds + nuke, metal reflections get clouds +
// nuke reflection, all in one pipeline. Apply order matters — clouds
// first, nuke second.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[nuclear_explosion] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const { scene, camera } = args;
        if (!camera) throw new Error('NuclearExplosionFX.applyTo: opts.camera required');
        if (!scene)  throw new Error('NuclearExplosionFX.applyTo: opts.scene required');
        const opts = args.opts ?? args;

        const {
            uniform, Fn, vec2, vec3, vec4, float, uv, Loop, Break, If, Continue,
            sin, cos, fract, floor, mix, clamp, smoothstep, dot, length,
            normalize, max, min, step, abs, sign, reflect, exp, pow, sqrt,
            mat2, convertToTexture, getViewPosition,
        } = THREE;

        const originArr = opts.origin ?? [0, 0, 0];
        const u = {
            time:         uniform(0),
            iResolution:  uniform(new THREE.Vector2(
                opts.width  ?? globalThis.WIDTH  ?? 1280,
                opts.height ?? globalThis.HEIGHT ?? 720,
            )),
            origin:       uniform(new THREE.Vector3(originArr[0], originArr[1], originArr[2])),
            scale:        uniform(opts.scale       ?? 1.0),
            timeOffset:   uniform(opts.timeOffset  ?? 0.0),
            loopSeconds:  uniform(opts.loopSeconds ?? 20.0),
            maxT:         uniform(opts.maxT        ?? 80.0),
            opacity:      uniform(opts.opacity     ?? 1.0),
            // Camera matrices (volumetric_clouds pattern).
            projInv:  uniform(camera.projectionMatrixInverse),
            camWorld: uniform(camera.matrixWorld),
            camNear:  uniform(camera.near),
            camFar:   uniform(camera.far),
        };
        const SURF_STEPS    = opts.surfSteps    ?? 64;
        const VOL_STEPS     = opts.volSteps     ?? 96;
        const REFLECT_STEPS = opts.reflectSteps ?? 48;

        // ============== noise & helpers ==============
        const hash3 = (p) => Fn(() => {
            const q = fract(p.mul(0.3183099).add(vec3(0.71, 0.113, 0.419)));
            const q2 = q.mul(17.0);
            return fract(q2.x.mul(q2.y).mul(q2.z).mul(q2.x.add(q2.y).add(q2.z)));
        })();
        const vnoise = (p) => Fn(() => {
            const i = floor(p);
            const f = fract(p);
            const fs = f.mul(f).mul(vec3(3).sub(f.mul(2)));
            const a = hash3(i.add(vec3(0, 0, 0)));
            const b = hash3(i.add(vec3(1, 0, 0)));
            const c = hash3(i.add(vec3(0, 1, 0)));
            const d = hash3(i.add(vec3(1, 1, 0)));
            const e = hash3(i.add(vec3(0, 0, 1)));
            const g = hash3(i.add(vec3(1, 0, 1)));
            const h = hash3(i.add(vec3(0, 1, 1)));
            const k = hash3(i.add(vec3(1, 1, 1)));
            return mix(
                mix(mix(a, b, fs.x), mix(c, d, fs.x), fs.y),
                mix(mix(e, g, fs.x), mix(h, k, fs.x), fs.y),
                fs.z,
            );
        })();
        const sminCubic = (a, b, k) => Fn(() => {
            const h = max(k.sub(abs(a.sub(b))), 0).div(k);
            return min(a, b).sub(h.mul(h).mul(h).mul(k).div(6));
        })();
        const easeOutCubic = (t) => float(1).sub(pow(float(1).sub(t), 3));
        const rotate2 = (v, a) => Fn(() => {
            const c = cos(a);
            const s = sin(a);
            return vec2(
                v.x.mul(c).sub(v.y.mul(s)),
                v.x.mul(s).add(v.y.mul(c)),
            );
        })();

        // ============== component SDFs ==============
        const sdCap = (p, capCenter, capR) => Fn(() => {
            const q = p.sub(capCenter);
            const qStretch = q.div(vec3(1, 0.78, 1));
            return length(qStretch).sub(capR);
        })();
        const sdStem = (p, stemTop, baseR, topR) => Fn(() => {
            const h = clamp(p.y.div(max(stemTop, 0.001)), 0, 1);
            const r = mix(baseR, topR, pow(h, 0.7));
            const radial = length(p.xz).sub(r);
            const yClip = max(p.y.sub(stemTop), p.y.negate());
            return max(radial, yClip);
        })();
        const sdTrail = (p, trailY, trailR) => Fn(() => {
            const q = p.sub(vec3(0, trailY, 0));
            return length(q.div(vec3(1.3, 0.9, 1.3))).sub(trailR);
        })();
        const sdBaseSurgeTorus = (p, surgeR, ringTube) => Fn(() => {
            const radial = length(p.xz).sub(surgeR);
            return length(vec2(radial, p.y.sub(ringTube.mul(0.6)))).sub(ringTube);
        })();
        const sdBaseSurgePad = (p, padR, padH) => Fn(() => {
            const heightAtR = padH.mul(smoothstep(padR, padR.mul(0.2), length(p.xz)));
            const radial = length(p.xz).sub(padR);
            const yClip = max(p.y.sub(heightAtR), p.y.negate());
            return max(radial, yClip);
        })();

        // Compute timeline-derived TSL nodes for the explosion's animation.
        // Plain JS function (NOT wrapped in Fn) — Fn can only return TSL
        // node values, not plain objects, so we build the per-pixel
        // timeline as a struct of TSL nodes that get inlined wherever
        // they're referenced. The nodes themselves are uniforms or pure
        // functions of `u.time`, so the cost stays minimal regardless of
        // how many sites read them.
        const timelineParams = () => {
            const tWithOffset = u.time.add(u.timeOffset);
            const tnLoop = fract(tWithOffset.div(u.loopSeconds));
            const tn = clamp(tnLoop.div(0.6), 0, 1);
            const capRaiseT = clamp(tn.div(0.55), 0, 1);
            const capExpT   = clamp(tn.div(0.50), 0, 1);
            const capY = mix(float(1.0), float(8.0), easeOutCubic(capRaiseT)).add(tn);
            const capR = mix(float(0.5), float(4.6), easeOutCubic(capExpT)).add(tn.mul(0.5));
            const stemBaseR = mix(float(0.30), float(1.1), easeOutCubic(clamp(tn.div(0.40), 0, 1)));
            const stemTopR  = mix(float(0.70), float(2.2), easeOutCubic(clamp(tn.div(0.50), 0, 1)));
            const stemTop   = capY.sub(0.6);
            const trailRise = clamp(tn.sub(0.10).div(0.5), 0, 1);
            const trailY = mix(float(1.0), capY.mul(0.60), trailRise);
            const trailR = mix(float(0.4), float(2.4), trailRise);
            const surgeR = mix(float(2.0), float(16.0), easeOutCubic(clamp(tn.div(0.7), 0, 1)))
                .add(tn.mul(4));
            const ringPeak = smoothstep(0.0, 0.4, tn);
            const ringFade = float(1).sub(smoothstep(0.4, 1.0, tn));
            const ringTube = mix(float(0.4), float(2.2), ringPeak)
                .mul(mix(float(0.15), float(1), ringFade));
            const padH = mix(float(0.6), float(1.8), easeOutCubic(clamp(tn.div(0.5), 0, 1)))
                .mul(mix(float(0.3), float(1), ringFade));
            return {
                tnLoop, tn,
                capY, capR,
                stemTop, stemBaseR, stemTopR,
                trailRise, trailY, trailR,
                surgeR, ringTube, padH, ringFade,
            };
        };

        // ============== unified scene SDF ==============
        const mapScene = (pIn) => Fn(() => {
            // Move to local space (centred on `origin`, divided by `scale`).
            const p = pIn.sub(u.origin).div(u.scale);
            const tp = timelineParams();
            const dCap = sdCap(p, vec3(0, tp.capY, 0), tp.capR);
            const dStem = sdStem(p, tp.stemTop, tp.stemBaseR, tp.stemTopR);
            const dTrail = sdTrail(p, tp.trailY, tp.trailR);
            const dRing = sdBaseSurgeTorus(p, tp.surgeR, tp.ringTube);
            const dPad  = sdBaseSurgePad(p, tp.surgeR.sub(tp.ringTube.mul(0.4)), tp.padH);
            const dSurge = sminCubic(dRing, dPad, float(0.6));

            const dStemCap = sminCubic(dStem, dCap, float(0.6));
            const dWithTrail = sminCubic(
                dStemCap, dTrail, mix(float(0.2), float(0.5), tp.trailRise),
            );
            const dFinal = sminCubic(
                dWithTrail, dSurge, mix(float(0.3), float(1), tp.ringFade),
            );
            // Re-scale distance by `scale` so the marcher uses world units.
            return dFinal.mul(u.scale);
        })();

        // ============== sample-position advection ==============
        const advectSamplePos = (pIn) => Fn(() => {
            const p = pIn.sub(u.origin).div(u.scale);
            const tp = timelineParams();
            const radialDist = length(p.xz);

            const torusW = exp(abs(radialDist.sub(tp.surgeR)).mul(-0.4))
                .mul(exp(abs(p.y.sub(1.0)).mul(-0.4)));
            const capW = exp(abs(p.y.sub(tp.capY)).mul(-0.18))
                .mul(exp(max(radialDist.sub(tp.capR), 0).mul(-0.3)));

            const advected = p.toVar();

            // BASE SURGE rolling
            If(torusW.greaterThan(0.01).and(radialDist.greaterThan(0.5)), () => {
                const outward = normalize(p.xz);
                const radial = radialDist.sub(tp.surgeR);
                const cross = vec2(radial, p.y.sub(1));
                const rolled = rotate2(cross, u.time.mul(0.25));
                const newXZ = outward.mul(rolled.x.add(tp.surgeR));
                const torusPos = vec3(newXZ.x, rolled.y.add(1), newXZ.y);
                advected.assign(mix(advected, torusPos, torusW));
            });

            // CAP rolling
            If(capW.greaterThan(0.005).and(radialDist.greaterThan(0.3)), () => {
                const outward = normalize(p.xz);
                const tubeRingR = tp.capR.mul(0.65);
                const radial = radialDist.sub(tubeRingR);
                const cross = vec2(radial, p.y.sub(tp.capY));
                const rolled = rotate2(cross, u.time.mul(0.35));
                const newXZ = outward.mul(rolled.x.add(tubeRingR));
                const capPos = vec3(newXZ.x, rolled.y.add(tp.capY), newXZ.y);
                advected.assign(mix(advected, capPos, capW));
            });

            // Return advected position (in local space, since SDF/density
            // operations downstream all use local coords).
            return advected;
        })();

        const sampleDensity = (pIn, surfaceDist) => Fn(() => {
            // surfaceDist arrives in world units (SDF was rescaled by `scale`);
            // bring back to local units for the falloff calc.
            const surfaceDistLocal = surfaceDist.div(u.scale);
            const falloff = clamp(surfaceDistLocal.div(-0.8), 0, 1);
            const result = float(0).toVar();
            If(falloff.lessThanEqual(0), () => {
                result.assign(0);
            });
            If(falloff.greaterThan(0), () => {
                const sp = advectSamplePos(pIn);
                const d0 = vnoise(sp.mul(0.8)).mul(0.8);
                const d1 = vnoise(sp.mul(2.2)).mul(0.4);
                const d2 = vnoise(sp.mul(5.0)).mul(0.2);
                const dBase = d0.add(d1).add(d2).toVar();
                const d3 = vnoise(sp.mul(13.0)).mul(0.45).mul(dBase);
                dBase.assign(dBase.add(d3));

                const density = falloff.mul(dBase).toVar();

                // Mushroom dispersal — raise threshold over time so wisps
                // dissolve first, dense core last. Clamps to zero by loop end.
                const tp = timelineParams();
                const pLocal = pIn.sub(u.origin).div(u.scale);
                const radialDist = length(pLocal.xz);
                const mushroomRegion = clamp(
                    smoothstep(2.5, 5.0, pLocal.y).add(
                        float(1).sub(smoothstep(2.5, 6.0, radialDist))
                            .mul(smoothstep(0.5, 2.5, pLocal.y)),
                    ),
                    0, 1,
                );
                const dispersal = smoothstep(0.75, 1.0, tp.tnLoop).mul(mushroomRegion);
                const lowThresh = mix(float(0.3), float(1.1), dispersal);
                const highThresh = lowThresh.add(0.6);
                const shaped = clamp(
                    density.sub(lowThresh).div(highThresh.sub(lowThresh)),
                    0, 1,
                );
                result.assign(shaped);
            });
            return result;
        })();

        const densityToHeat = (pIn, density) => Fn(() => {
            const tp = timelineParams();
            const pLocal = pIn.sub(u.origin).div(u.scale);
            const corePos = vec3(0, tp.capY.mul(0.85), 0);
            const coreDist = length(pLocal.sub(corePos));
            const coreTerm = exp(coreDist.mul(-0.18));
            const coolFactor = float(1).sub(smoothstep(0.4, 0.85, tp.tnLoop));
            const heat = density.mul(coreTerm).mul(coolFactor)
                .add(coreTerm.mul(0.6).mul(coolFactor));
            return clamp(heat, 0, 1);
        })();

        const heatToColor = (heat) => Fn(() => {
            const out = vec3(0).toVar();
            // Smoke band heat<0.08 — grey scaling
            const smokeMix = clamp(heat.div(0.08), 0, 1);
            const smokeCol = mix(vec3(0.012), vec3(0.18, 0.16, 0.14), smokeMix);
            // Fire band — embers → orange → yellow-white
            const c1 = mix(
                vec3(0, 0, 0),
                vec3(1.0, 0.30, 0.0),
                clamp(heat.mul(12).sub(1), 0, 1),
            );
            const c2 = mix(c1, vec3(1.6, 1.0, 0.5), clamp(heat.mul(14).sub(5), 0, 1));
            const c3 = mix(c2, vec3(2.5, 1.9, 1.2), clamp(heat.mul(30).sub(18), 0, 1));
            const isSmoke = step(heat, float(0.08));
            out.assign(mix(c3, smokeCol, isSmoke));
            return out;
        })();

        // ============== raymarch the explosion volume ==============
        // Returns vec4(rgb, alpha) — premultiplied. Caller composites
        // over scene/background.
        const marchExplosion = (ro, rd, maxDist, surfSteps, volSteps) => Fn(() => {
            const tEntry = float(0).toVar();
            const entered = float(0).toVar();
            const surfMaxIters = surfSteps;

            // Surface march — find entry into bounding volume.
            Loop({ start: 0, end: surfMaxIters, type: 'int' }, () => {
                If(tEntry.greaterThanEqual(maxDist), () => Break());
                const q = ro.add(rd.mul(tEntry));
                const d = mapScene(q);
                If(d.lessThan(0.1), () => {
                    entered.assign(1);
                    Break();
                });
                tEntry.addAssign(max(d.mul(0.9), 0.15));
            });

            const col = vec4(0).toVar();
            If(entered.greaterThan(0.5), () => {
                const tCur = tEntry.toVar();
                const volMaxIters = volSteps;
                Loop({ start: 0, end: volMaxIters, type: 'int' }, () => {
                    If(tCur.greaterThanEqual(maxDist), () => Break());
                    If(col.a.greaterThan(0.98), () => Break());
                    const q = ro.add(rd.mul(tCur));
                    const d = mapScene(q);
                    If(d.lessThan(0.2), () => {
                        const density = sampleDensity(q, d);
                        If(density.greaterThan(0.001), () => {
                            const heat = densityToHeat(q, density);
                            const dcol = heatToColor(heat);
                            const dWeight = density.mul(0.22);
                            const oneMinusA = float(1).sub(col.a);
                            col.assign(vec4(
                                col.rgb.add(oneMinusA.mul(dWeight).mul(dcol)),
                                col.a.add(oneMinusA.mul(dWeight)),
                            ));
                        });
                    });
                    // Adaptive step size
                    const stepLen = float(0).toVar();
                    If(d.lessThan(0.2), () => stepLen.assign(0.08));
                    If(d.greaterThanEqual(0.2), () => stepLen.assign(max(d.mul(0.6), 0.15)));
                    tCur.addAssign(stepLen);
                });
            });
            return col;
        })();

        // ============== hooks ==============
        function buildHook() {
            return {
                uniforms: u,
                update(t) {
                    u.time.value = t;
                    camera.updateMatrixWorld();
                    u.projInv.value  = camera.projectionMatrixInverse;
                    u.camWorld.value = camera.matrixWorld;
                    u.camNear.value  = camera.near;
                    u.camFar.value   = camera.far;
                },
                // Pre-SSR view-ray composite. Reads scene depth so opaque
                // geometry occludes the explosion at the right distance.
                hook(colorIn, sceneDepth /*, normal, mr */) {
                    const colorTex = convertToTexture(colorIn);
                    const depthTex = convertToTexture(sceneDepth);
                    return Fn(() => {
                        const screenUV = uv();
                        const sceneColor = colorTex.sample(screenUV);
                        const sceneD = depthTex.sample(screenUV).r;

                        // Ray origin (camera world pos) + direction.
                        const view = getViewPosition(screenUV, float(0.5), u.projInv);
                        const ro = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                        const worldH = u.camWorld.mul(vec4(view, 1)).xyz;
                        const rd = normalize(worldH.sub(ro));

                        // Convert depth to world-distance for ray clamping.
                        // perspectiveDepthToViewZ returns negative-z; take |
                        // and use as march cap so explosion is occluded by
                        // closer geometry.
                        const viewZ = THREE.perspectiveDepthToViewZ(sceneD, u.camNear, u.camFar);
                        const sceneDist = viewZ.negate();
                        const marchMax = min(sceneDist, u.maxT);

                        const expl = marchExplosion(ro, rd, marchMax, SURF_STEPS, VOL_STEPS);
                        // Composite explosion over scene: color = scene*(1-a) + expl.
                        const composed = sceneColor.rgb.mul(float(1).sub(expl.a)).add(expl.rgb);
                        return mix(sceneColor, vec4(composed, 1), u.opacity);
                    })();
                },
                // Reflection-path contribution for metallic surfaces.
                reflectHook(colorIn, sceneDepth, sceneNormal, sceneMR) {
                    const colorTex = convertToTexture(colorIn);
                    const depthTex = convertToTexture(sceneDepth);
                    return Fn(() => {
                        const screenUV = uv();
                        const sceneD = depthTex.sample(screenUV).r;
                        const isSurface = step(sceneD, 0.9999);

                        const mr = sceneMR.sample(screenUV);
                        const metalness = mr.r;
                        const roughness = mr.g;
                        const oneMinusR = float(1).sub(roughness);
                        const reflectivity = metalness.mul(oneMinusR.mul(oneMinusR));
                        const isReflective = smoothstep(0.1, 0.4, metalness);
                        const gateMask = isReflective.mul(isSurface);

                        const viewPos = getViewPosition(screenUV, sceneD, u.projInv);
                        const worldPos = u.camWorld.mul(vec4(viewPos, 1)).xyz;
                        const camPos = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                        const viewDir = normalize(worldPos.sub(camPos));

                        const viewNormal = sceneNormal.sample(screenUV);
                        const worldNormal = normalize(u.camWorld.mul(vec4(viewNormal, 0)).xyz);

                        const reflDir = reflect(viewDir, worldNormal);
                        const reflRO = worldPos.add(worldNormal.mul(0.05));

                        const cloudCol = vec3(0).toVar();
                        If(gateMask.greaterThan(0.05), () => {
                            const expl = marchExplosion(
                                reflRO, reflDir, u.maxT, REFLECT_STEPS, REFLECT_STEPS,
                            );
                            cloudCol.assign(expl.rgb.mul(reflectivity).mul(gateMask));
                        });
                        return vec4(cloudCol, 1);
                    })();
                },
                // Roughness-weighted blur of the reflection contribution.
                // Same algorithm as volumetric_clouds.reflectBlur.
                reflectBlur(reflContribIn, sceneDepth, sceneNormal, sceneMR) {
                    const cloudTex = convertToTexture(reflContribIn);
                    if (typeof THREE.gaussianBlur !== 'function') {
                        throw new Error('[nuclear_explosion] THREE.gaussianBlur not available');
                    }
                    const lightBlur = THREE.gaussianBlur(cloudTex, null, 2);
                    const heavyBlur = THREE.gaussianBlur(cloudTex, null, 8);
                    return Fn(() => {
                        const screenUV = uv();
                        const mr = sceneMR.sample(screenUV);
                        const metalness = mr.r;
                        const roughness = clamp(mr.g, 0, 1);
                        const r2 = roughness.mul(roughness);
                        const sharp = cloudTex.sample(screenUV).rgb;
                        const lightMix = smoothstep(0.0, 0.25, r2);
                        const heavyMix = smoothstep(0.25, 1.0, r2);
                        const stage1 = mix(sharp,  lightBlur.rgb, lightMix);
                        const stage2 = mix(stage1, heavyBlur.rgb, heavyMix);
                        const isReflective = smoothstep(0.1, 0.4, metalness);
                        return vec4(stage2.mul(isReflective), 1);
                    })();
                },
            };
        }

        const built = buildHook();
        if (opts.disableForPerfTest) {
            console.log('[nuclear_explosion] PERF TEST: hooks disabled');
            return { update(t) { built.update(t); }, uniforms: u };
        }

        // Capture any previously-installed hooks (e.g. volumetric_clouds)
        // so we can compose over them. Apply order at the call site:
        //   1) clouds.applyTo  — installs preSSR / cloudReflect / blur
        //   2) nuke.applyTo    — captures clouds' hooks, wraps them
        // Then the autoenhance pipeline calls OUR hook, which
        //   a) calls clouds' hook first (sky-replaced colorOut + cloud-reflect contrib)
        //   b) raymarches the explosion as the front layer
        //   c) returns the composited result
        const priorPreSSR     = globalThis._autoEnhancePreSSRHook       ?? null;
        const priorCloudRefl  = globalThis._autoEnhanceCloudReflectHook ?? null;
        const priorReflBlur   = globalThis._autoEnhanceCloudReflectBlurHook ?? null;

        globalThis._autoEnhancePreSSRHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            // If a prior preSSR hook exists (volumetric clouds), run it first
            // so our explosion sees a sky-replaced colour input and composes
            // over the cloudy sky.
            const upstream = priorPreSSR
                ? priorPreSSR(colorOut, sceneDepth, sceneNormal, sceneMR)
                : colorOut;
            return built.hook(upstream, sceneDepth, sceneNormal, sceneMR);
        };
        globalThis._autoEnhanceCloudReflectHook =
            (colorOut, sceneDepth, sceneNormal, sceneMR) => {
                const ourContrib = built.reflectHook(colorOut, sceneDepth, sceneNormal, sceneMR);
                if (!priorCloudRefl) return ourContrib;
                // Sum the two reflection contributions. Both are
                // gateMask-multiplied premultiplied vec4(rgb,1) — adding
                // them keeps each effect's contribution on its respective
                // surface fraction.
                const priorContrib = priorCloudRefl(colorOut, sceneDepth, sceneNormal, sceneMR);
                return Fn(() => {
                    const screenUV = uv();
                    const a = THREE.convertToTexture(ourContrib).sample(screenUV);
                    const b = THREE.convertToTexture(priorContrib).sample(screenUV);
                    return vec4(a.rgb.add(b.rgb), 1);
                })();
            };
        // Blur: only one blur pass needed since the contributions are summed
        // upstream. Our gaussianBlur(sigma=2/8) chain works fine on the
        // combined cloud+nuke reflection texture.
        globalThis._autoEnhanceCloudReflectBlurHook =
            (cloudReflTex, sceneDepth, sceneNormal, sceneMR) =>
                built.reflectBlur(cloudReflTex, sceneDepth, sceneNormal, sceneMR);

        return {
            update(t) { built.update(t); },
            uniforms: u,
        };
    }

    globalThis.NuclearExplosionFX = { applyTo };
    console.log('[nuclear_explosion] NuclearExplosionFX.applyTo registered');
})();
