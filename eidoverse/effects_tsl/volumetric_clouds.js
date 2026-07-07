// volumetric_clouds.js — physically-motivated volumetric cloud system.
//
// ⚠️ DEPRECATED — superseded by the WORLD-SPACE sky system
// (eidoverse/sky_system.js + eidoverse/weather_system.js). This screenspace
// effect paints clouds as a post-process keyed on depth: geometry can never
// occlude the sky naturally, rays are camera-anchored, and reflections need
// the bespoke hook pipeline. makeSkySystem() puts the clouds IN the world
// (real depth interaction, sun/moon/stars/day-cycle, weather states, moving
// metal reflections, env bake) — use it for anything new. This file remains
// only so existing scenes keep rendering.
//
// The cloud math: spherical-shell
// atmosphere on a 6300 km Earth, 800-m cloud base, 600-m thick
// cumulus band, two-stage subtractive FBM erosion of a height-shaped
// 2D weather field, light-ray-march toward the sun with multi-scale
// Beer's law, numerical Mie phase function, Sebastian Hillaire's
// energy-conserving radiance accumulator.
//
// Things substituted because we don't have the inputs the reference
// shader assumed:
//   - `iChannel0` 2D weather noise texture → procedural single-octave
//     value noise (`noise2`) sampled at the same coordinates.
//   - `iChannel1` 3D noise texture → hash-based 3D value noise
//     (`noise3`).
// Sample counts are dialed to roughly the reference's "fast" path so
// per-pixel WGSL stays compact (Naga has historically been touchy on
// this backend) and so cost stays close to the reference's ~30% GPU.
//
// Scene-light tracking: SUN_POWER's colour/magnitude track the
// scene's first DirectionalLight (color × intensity × sunPowerScale).
// Sun direction comes from the same light. Ambient blend is left
// exactly as the reference (sky-blue scaled by cloud height +
// bright bottom kick) so cloud lighting reads correctly.
//
// Cloud reflections on metallic surfaces come from a second post-SSR
// hook that calls skyRay along the reflection direction (fast path).
//
// Public API: VolumetricCloudsFX.applyTo({ scene, camera, opts });
// Recognised opts:
//   sunPowerScale  — HDR sun-power multiplier (default 80; reference
//                    used 750 for HDR; ACES tonemap brings ours down).
//   cloudStart     — cloud-base altitude in scene units (default 800).
//   cloudHeight    — cloud-band thickness in scene units (default 600).
//   skySamples     — outer raymarch sample count (default 13).
//   lightSamples   — inner sun-march sample count (default 7).
//   tint           — RGB multiplier on final cloud colour (default 1).

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[volumetric_clouds] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    const EARTH_RADIUS_M_DEFAULT = 6300e3;

    function applyTo(args) {
        console.warn('[volumetric_clouds] DEPRECATED: use the world-space sky system instead — eval eidoverse/sky_system.js and call makeSkySystem({scene, textures}) (+ eidoverse/weather_system.js for rain/storms). This screenspace effect is kept only for old scenes.');
        args = args || {};
        const { scene, camera } = args;
        if (!camera) throw new Error('VolumetricCloudsFX.applyTo: opts.camera required');
        if (!scene)  throw new Error('VolumetricCloudsFX.applyTo: opts.scene required (auto-discovers lights)');
        const opts = args.opts ?? args;

        // Auto-discover scene lights.
        let dirLight = null, ambLight = null;
        scene.traverse((obj) => {
            if (!dirLight && obj.isDirectionalLight) dirLight = obj;
            if (!ambLight && obj.isAmbientLight)     ambLight = obj;
        });
        if (!dirLight) {
            console.warn('[volumetric_clouds] no DirectionalLight in scene — clouds will only see ambient');
        }

        const {
            uniform, Fn, vec2, vec3, vec4, float, uv, Loop, Break, If,
            sin, cos, fract, floor, mix, clamp, smoothstep, dot, length,
            normalize, max, min, step, abs, sign, reflect, exp, pow, sqrt,
        } = THREE;

        // === Tunable JS constants ===
        const EARTH_RADIUS_M = opts.earthRadius  ?? EARTH_RADIUS_M_DEFAULT;
        const CLOUD_START_M  = opts.cloudStart   ?? 800.0;
        const CLOUD_HEIGHT_M = opts.cloudHeight  ?? 600.0;
        // Sparseness presets — agent-selectable cloud-cover regime.
        // Stored as JS objects; loaded into TSL uniforms below so they
        // can be swapped at runtime via fx.setSparseness(name).
        const SPARSENESS_PRESETS = {
            // Higher largeT = fewer XZ regions pass the threshold = sparser
            low:      { largeT: 0.40, largeA: 5.0, weatherT: 0.45, finalMul: 0.18 },
            medium:   { largeT: 0.24, largeA: 5.0, weatherT: 0.32, finalMul: 0.20 },
            overcast: { largeT: 0.05, largeA: 6.0, weatherT: 0.10, finalMul: 0.32 },
        };
        // Mood presets — agent-selectable colour grading. Affects cloud
        // tint (overall colour cast) and effective sun-power.
        // Stormy = nearly-neutral dark grey (slight cool cast), not the
        // blue-cast it had before.
        const MOOD_PRESETS = {
            normal: { tint: [1.00, 1.00, 1.00], sunMul: 1.0 },
            stormy: { tint: [0.42, 0.44, 0.48], sunMul: 0.30 },
        };
        const validateSparseness = (name) => {
            if (!SPARSENESS_PRESETS[name]) {
                throw new Error(
                    `[volumetric_clouds] unknown sparseness "${name}". `
                    + `Valid: ${Object.keys(SPARSENESS_PRESETS).join(', ')}`,
                );
            }
        };
        const validateMood = (name) => {
            if (!MOOD_PRESETS[name]) {
                throw new Error(
                    `[volumetric_clouds] unknown mood "${name}". `
                    + `Valid: ${Object.keys(MOOD_PRESETS).join(', ')}`,
                );
            }
        };
        validateSparseness(opts.sparseness ?? 'medium');
        validateMood(opts.mood ?? 'normal');
        // Reference samples weather at 0.00005 / 0.0002 — tuned for 800m
        // clouds. With smaller cloud altitudes the visible sky covers a
        // smaller XZ region at cloud altitude → fewer noise cells → all-
        // cloud or no-cloud per frame. Auto-scale frequencies up so we
        // get similar in-frame cloud variation regardless of cloudStart.
        const WEATHER_SCALE = (800 / CLOUD_START_M) * (opts.weatherScale ?? 1.0);
        // Erosion fbm frequencies scale with cloud band thickness so
        // detail features stay relatively-sized to the cloud body.
        const DETAIL_SCALE  = (600 / CLOUD_HEIGHT_M) * (opts.detailScale ?? 1.0);
        // Sample counts. OUTER (skySamples) controls cloud silhouette
        // edge crispness — undersampling shows as per-pixel noise where
        // jitter-induced ray-start offsets straddle the density edge.
        // We oversize outer to 60 (vs reference's 35) to crush that edge
        // noise; Mesa 26 has the headroom. INNER (lightSamples) only
        // affects shading smoothness; 20 stays at reference.
        const SKY_SAMPLES_CAMERA = opts.skySamples   ?? 60;
        const SKY_SAMPLES_REFL   = Math.max(7, Math.floor((opts.skySamples ?? 60) * 0.3));
        const LIGHT_SAMPLES_CAMERA = opts.lightSamples ?? 20;
        const LIGHT_SAMPLES_REFL   = Math.max(4, Math.floor((opts.lightSamples ?? 20) * 0.3));

        // === Uniforms ===
        const u = {
            time:          uniform(0),
            sunColor:      uniform(new THREE.Vector3(1, 1, 1)),
            sunDir:        uniform(new THREE.Vector3(0, 1, 0)),
            sunIntensity:  uniform(0),
            ambColor:      uniform(new THREE.Vector3(1, 1, 1)),
            ambIntensity:  uniform(0),
            sunPowerScale: uniform(opts.sunPowerScale ?? 80.0),
            // Reference shader is HDR-native (values up to ~100s pre tone
            // mapping) and assumes gentle highlight clipping. Our
            // pipeline applies ACES Filmic at exposure 1.1, which
            // saturates above ~5 → without scaling, sky and clouds both
            // blow out to white. 0.08 brings the range into ACES's
            // pleasant region (cloud bodies ~1-3, sky bg ~0.1-0.5).
            colorScale:    uniform(opts.colorScale ?? 0.08),
            tint:          uniform(new THREE.Vector3(...(opts.tint ?? [1, 1, 1]))),
            // cloudColor — agent-facing per-cloud tint multiplier. Unlike
            // `tint` (which multiplies the FINAL cloud+bg+sun composite),
            // `cloudColor` multiplies ONLY the accumulated cloud radiance
            // BEFORE the background sky and sun-disk are added. Cloud
            // brightness/density variations are preserved (multiplication
            // keeps relative differences), but the overall colour of cloud
            // bodies shifts toward the agent's chosen hue. Set to `[1,1,1]`
            // (default) for no effect; e.g. `[1.0, 0.6, 0.5]` for sunset-
            // pink clouds; `[0.6, 0.7, 0.95]` for pre-storm cool blue;
            // `[0.4, 0.3, 0.5]` for purple twilight. Background sky and
            // horizon gradient stay neutral so the silhouette remains
            // legible.
            cloudColor:    uniform(new THREE.Vector3(...(opts.cloudColor ?? [1, 1, 1]))),
            projInv:       uniform(camera.projectionMatrixInverse),
            camWorld:      uniform(camera.matrixWorld),
            // Cloud-shaft (god rays through clouds) controls. Disabled
            // by default since it adds raymarch cost and only reads
            // properly when the sun is visible in-frame.
            shaftEnabled:  uniform(opts.cloudShafts?.enabled ? 1 : 0),
            // Defaults dialed for visible-but-not-blown-out cloud shafts.
            // strength × exposure controls overall brightness; decay
            // controls how fast each successive sample's contribution
            // falls off (lower = more localized halo around sun).
            shaftStrength: uniform(opts.cloudShafts?.strength ?? 4.0),
            shaftDecay:    uniform(opts.cloudShafts?.decay    ?? 0.95),
            shaftExposure: uniform(opts.cloudShafts?.exposure ?? 0.8),
            // Cloud shadows on geometry. Reuses the same shaft transmission
            // computation: for each scene pixel, transmission along path
            // to sun = how much sun reaches this point through clouds.
            // (1 - transmission) × shadowStrength = darkening factor.
            // Default off; turn on alongside cloudShafts for full effect.
            shadowEnabled:  uniform(opts.cloudShadows?.enabled ? 1 : 0),
            shadowStrength: uniform(opts.cloudShadows?.strength ?? 0.6),
            // Sun screen-space position, refreshed each frame in update()
            // by projecting sun's world position through view+proj.
            sunScreenPos:  uniform(new THREE.Vector2(0.5, 0.5)),
            sunInFront:    uniform(0),  // 1 if sun is in front of camera, 0 if behind
            // For the cloud-reflect screen-space hit check: project a
            // world-space reflection ray onto screen UVs to query the
            // depth buffer, the same technique SSR uses to detect when a
            // reflection ray hits scene geometry before reaching the sky.
            proj:          uniform(camera.projectionMatrix),
            viewMat:       uniform(camera.matrixWorldInverse),
            // Sparseness uniforms — set from preset, mutable at runtime
            sparseLargeT:    uniform(0.0),
            sparseLargeA:    uniform(0.0),
            sparseWeatherT:  uniform(0.0),
            sparseFinalMul:  uniform(0.0),
            // Mood uniforms — colour cast on cloud + sun multiplier
            moodTint:        uniform(new THREE.Vector3(1, 1, 1)),
            moodSunMul:      uniform(1.0),
            // Output resolution (used by reflectBlur for screen-space
            // pixel-size kernel offsets).
            iResolution: uniform(new THREE.Vector2(
                opts.width  ?? globalThis.WIDTH  ?? 1280,
                opts.height ?? globalThis.HEIGHT ?? 720,
            )),
        };
        const setSparseness = (name) => {
            validateSparseness(name);
            const SP = SPARSENESS_PRESETS[name];
            u.sparseLargeT.value   = SP.largeT;
            u.sparseLargeA.value   = SP.largeA;
            u.sparseWeatherT.value = SP.weatherT;
            u.sparseFinalMul.value = SP.finalMul;
        };
        const setMood = (name) => {
            validateMood(name);
            const MD = MOOD_PRESETS[name];
            u.moodTint.value.set(...MD.tint);
            u.moodSunMul.value = MD.sunMul;
        };
        setSparseness(opts.sparseness ?? 'medium');
        setMood(opts.mood ?? 'normal');

        // === Noise texture (precomputed) ===
        // Reference uses iChannel1 — a 256×256 RGBA noise texture — and
        // gets cheap hardware-bilinear-interpolated lookups instead of
        // per-pixel hash math. We replicate that: build the texture
        // once, sample with TSL TextureNode. The IQ "slicing" trick
        // simulates 3D noise from the 2D texture by shifting the UV
        // by (37, 17) per integer z, then mixing channels by z's
        // fractional. Replaces ~24 hash31 calls per fbm with a single
        // texture sample.
        const NOISE_TEX_SIZE = 256;
        const noisePixels = new Uint8Array(NOISE_TEX_SIZE * NOISE_TEX_SIZE * 4);
        for (let i = 0; i < noisePixels.length; i++) {
            noisePixels[i] = (Math.random() * 256) | 0;
        }
        const noiseDataTex = new THREE.DataTexture(
            noisePixels, NOISE_TEX_SIZE, NOISE_TEX_SIZE,
            THREE.RGBAFormat,
        );
        noiseDataTex.wrapS = THREE.RepeatWrapping;
        noiseDataTex.wrapT = THREE.RepeatWrapping;
        noiseDataTex.minFilter = THREE.LinearFilter;
        noiseDataTex.magFilter = THREE.LinearFilter;
        noiseDataTex.needsUpdate = true;
        const noiseTexNode = THREE.texture(noiseDataTex);

        // === Hash + noise helpers ===
        // 1D hash kept for ray-jitter (cheap and only called once).
        const hash11 = (n) => fract(sin(n).mul(43758.5453));

        // 2D value noise → [0, 1]. IQ-style: shift integer position by
        // smoothstepped fractional, sample texture with hardware
        // bilinear filtering. The smoothstep-on-fractional gives true
        // smoothstep interpolation between cells (vs. linear from raw
        // bilinear).
        const noise2 = (p) => {
            const i = floor(p);
            const f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            const uv = i.add(sm).add(0.5).div(NOISE_TEX_SIZE);
            return noiseTexNode.sample(uv).r;
        };

        // 3D value noise → [0, 1]. IQ slicing trick: pack z-axis into
        // 2D UV via (37, 17) per-unit-z shift; channels R and G provide
        // adjacent z-slices mixed by smoothstep(f.z).
        const noise3 = (p) => {
            const i = floor(p);
            const f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            const uvx = i.x.add(float(37).mul(i.z)).add(sm.x);
            const uvy = i.y.add(float(17).mul(i.z)).add(sm.y);
            const uv = vec2(uvx, uvy).add(0.5).div(NOISE_TEX_SIZE);
            const t = noiseTexNode.sample(uv);
            return mix(t.r, t.g, sm.z);
        };
        // 3-octave fbm — exact reference:
        //   mat3 m = mat3(0.0, 0.8, 0.6, -0.8, 0.36, -0.48, -0.6, -0.48, 0.64);
        //   f  = 0.5*noise(p);  p = m*p*2.02
        //   f += 0.25*noise(p); p = m*p*2.03
        //   f += 0.125*noise(p)
        // We roll the matrix multiply by hand (3 dot products) to keep TSL
        // happy without a mat3 type.
        const m_row0 = vec3(0.0, 0.8, 0.6);
        const m_row1 = vec3(-0.8, 0.36, -0.48);
        const m_row2 = vec3(-0.6, -0.48, 0.64);
        const applyM = (p) => vec3(dot(p, m_row0), dot(p, m_row1), dot(p, m_row2));
        const fbm3 = (p) => {
            const pp = p.toVar();
            const f = noise3(pp).mul(0.5).toVar();
            pp.assign(applyM(pp).mul(2.02));
            f.addAssign(noise3(pp).mul(0.25));
            pp.assign(applyM(pp).mul(2.03));
            f.addAssign(noise3(pp).mul(0.125));
            return f;
        };

        // === clouds(p, fast) ===
        // Returns { density, cloudHeight }.
        // - `fast=true` skips the second 0.05-scale erosion pass.
        // - We rebuild p as separate p1/p2/p3/p4 nodes after each wind shift
        //   instead of mutating components (TSL component-write isn't
        //   guaranteed across backends).
        const clouds = (p, fast) => {
            const earthCenter = vec3(0, -EARTH_RADIUS_M, 0);
            const atmoHeight = length(p.sub(earthCenter)).sub(EARTH_RADIUS_M);
            const cloudHeight = atmoHeight.sub(CLOUD_START_M).div(CLOUD_HEIGHT_M).clamp(0, 1);

            // p.z += iTime * 10.3
            // Sparseness presets drive the threshold values. Reference
            // is "medium" (0.18/0.28). Higher thresholds = sparser, more
            // blue sky between distinct cumulus. Lower = overcast.
            const p1 = p.add(vec3(0, 0, u.time.mul(10.3)));
            const largeWeather = clamp(
                noise2(vec2(p1.z, p1.x).mul(-0.00005 * WEATHER_SCALE)).sub(u.sparseLargeT).mul(u.sparseLargeA),
                0, 2,
            );

            // p.x += iTime * 8.3
            const p2 = p1.add(vec3(u.time.mul(8.3), 0, 0));
            const weather2 = max(noise2(vec2(p2.z, p2.x).mul(0.0002 * WEATHER_SCALE)).sub(u.sparseWeatherT), 0)
                .div(0.72);
            const weather = largeWeather.mul(weather2)
                .mul(smoothstep(0.0, 0.5, cloudHeight))
                .mul(smoothstep(1.0, 0.5, cloudHeight));

            const shapeExp = float(0.3).add(
                float(1.5).mul(smoothstep(0.2, 0.5, cloudHeight)),
            );
            // pow(0, n) is undefined-ish in some impls; clamp before pow.
            const cloudShape = pow(weather.max(1e-6), shapeExp);

            // p.x += iTime * 12.3 (cumulative on top of p2)
            const p3 = p2.add(vec3(u.time.mul(12.3), 0, 0));
            const fbmA = fbm3(p3.mul(0.01 * DETAIL_SCALE));
            const den1 = max(cloudShape.sub(fbmA.mul(0.7)), 0);

            let denFinal;
            if (fast) {
                denFinal = den1;
            } else {
                // p.y += iTime * 15.2
                const p4 = p3.add(vec3(0, u.time.mul(15.2), 0));
                const fbmB = fbm3(p4.mul(0.05 * DETAIL_SCALE));
                denFinal = max(den1.sub(fbmB.mul(0.2)), 0);
            }

            const density = largeWeather.mul(u.sparseFinalMul).mul(min(denFinal.mul(5), 1));
            return { density, cloudHeight };
        };

        // === Phase function ===
        // Numerical Mie fit (4-exp empirical). Captures both forward-scatter
        // peak and the broad backscatter shoulder, more accurate than
        // single-lobe HG. Mesa 26 perf budget makes the 4 exp calls
        // affordable.
        const phaseMie = (costh) => {
            const p1 = costh.add(0.8194068);
            const e0 = exp(costh.mul(-65.0).sub(55.0));
            const e1 = exp(p1.mul(p1).mul(-83.70334));
            const e2 = exp(costh.mul(7.810083));
            const e3 = exp(costh.mul(-4.552125e-12));
            return e0.mul(9.805233e-6)
                .add(e1.mul(0.1388198))
                .add(e2.mul(2.054747e-3))
                .add(e3.mul(2.600563e-2));
        };

        // === Cheap density estimate for the light-march ===
        // The light-ray's purpose is to estimate "how much cloud is between
        // this sample and the sun" for Beer's-law shadowing. That doesn't
        // need the full clouds() pipeline (4 fbm calls + pow + erosion).
        // A single noise2 lookup + height profile gives a usable estimate
        // at ~1/8 the cost — critical for realtime perf.
        const cheapDensityAt = (p) => {
            const earthCenter = vec3(0, -EARTH_RADIUS_M, 0);
            const atmoHeight = length(p.sub(earthCenter)).sub(EARTH_RADIUS_M);
            const cloudHeight = atmoHeight.sub(CLOUD_START_M)
                .div(CLOUD_HEIGHT_M).clamp(0, 1);
            const vProfile = smoothstep(0.0, 0.5, cloudHeight)
                .mul(smoothstep(1.0, 0.5, cloudHeight));
            const wx = vec2(p.z, p.x).mul(-0.00005 * WEATHER_SCALE);
            return max(noise2(wx).sub(0.30), 0).mul(2.0).mul(vProfile);
        };

        // === lightRay(p, phaseFunction, dC, mu, sun_direction, cloudHeight, fast) ===
        // Marches a short ray toward the sun, accumulates density, applies
        // Beer's law (slow path uses 3-term multi-scale + powdered effect).
        // Inner sample loop is JS-unrolled (fixed count → cheap WGSL).
        const lightRay = (p, phaseFunction, dC, mu, sun_direction, cloudHeight, fast) => {
            const nbSamples = fast ? LIGHT_SAMPLES_REFL : LIGHT_SAMPLES_CAMERA;
            const zMaxL = 600.0;
            const stepL = float(zMaxL / nbSamples);

            const startJit = hash11(
                dot(p, vec3(12.256, 2.646, 6.356)).add(u.time),
            );
            const pStart = p.add(sun_direction.mul(stepL).mul(startJit));

            const lighRayDen = float(0).toVar();
            for (let j = 0; j < nbSamples; j++) {
                const samplePos = pStart.add(
                    sun_direction.mul(stepL).mul(j),
                );
                lighRayDen.addAssign(cheapDensityAt(samplePos));
            }

            if (fast) {
                // 0.5*exp(-0.4*stepL*den) + max(0, -mu*0.6+0.3)*exp(-0.02*stepL*den)
                const a = exp(stepL.mul(lighRayDen).negate().mul(0.4)).mul(0.5);
                const b = exp(stepL.mul(lighRayDen).negate().mul(0.02))
                    .mul(max(mu.negate().mul(0.6).add(0.3), 0));
                return a.add(b).mul(phaseFunction);
            }
            // Slow path:
            const scatterAmount = mix(
                float(0.008), float(1.0),
                smoothstep(0.96, 0.0, mu),
            );
            const beersLaw = exp(stepL.mul(lighRayDen).negate())
                .add(exp(stepL.mul(lighRayDen).negate().mul(0.1))
                    .mul(scatterAmount).mul(0.5))
                .add(exp(stepL.mul(lighRayDen).negate().mul(0.02))
                    .mul(scatterAmount).mul(0.4));
            // Powdered effect: mix(0.05 + 1.5*pow(min(1,dC*8.5), 0.3+5.5*h), 1, clamp(den*0.4, 0, 1))
            const powderedExp = float(0.3).add(cloudHeight.mul(5.5));
            const powdered = float(0.05).add(
                pow(min(dC.mul(8.5), 1).max(1e-6), powderedExp).mul(1.5),
            );
            const blend = clamp(lighRayDen.mul(0.4), 0, 1);
            const lit = mix(powdered, float(1), blend);
            return beersLaw.mul(phaseFunction).mul(lit);
        };

        // === intersectShellFar ===
        // Returns the FAR positive root of ray-vs-sphere where origin is
        // inside the sphere. Used for both ATM_START and ATM_END shells
        // (we pick the far root because we're below both shells looking
        // outward/upward).
        const intersectShellFar = (origin, dir, sphereRad) => {
            const earthCenter = vec3(0, -EARTH_RADIUS_M, 0);
            const oc = origin.sub(earthCenter);
            const b = dot(dir, oc).mul(2);
            const c = dot(oc, oc).sub(sphereRad * sphereRad);
            const disc = b.mul(b).sub(c.mul(4));
            return b.negate().add(sqrt(max(disc, 0))).mul(0.5);
        };

        // === skyRay(org, dir, sun_direction, fast) ===
        // Returns HDR vec3 — clouds composited over background
        // sky gradient, plus optional sun disk on the slow path.
        const skyRay = (org, dir, sun_direction, fast) => {
            const ATM_START = EARTH_RADIUS_M + CLOUD_START_M;
            const ATM_END   = ATM_START + CLOUD_HEIGHT_M;
            const nbSample  = fast ? SKY_SAMPLES_REFL : SKY_SAMPLES_CAMERA;

            const distToAtmStart = intersectShellFar(org, dir, ATM_START);
            const distToAtmEnd   = intersectShellFar(org, dir, ATM_END);
            const stepS = distToAtmEnd.sub(distToAtmStart).div(nbSample);

            const T = float(1).toVar();
            const color = vec3(0).toVar();
            const mu = dot(sun_direction, dir);
            const phaseFunction = phaseMie(mu);

            const startJit = hash11(
                dot(dir, vec3(12.256, 2.646, 6.356)).add(u.time),
            );
            const pStart = org.add(dir.mul(distToAtmStart))
                .add(dir.mul(stepS).mul(startJit));
            const p = pStart.toVar();

            // Reference: `if (dir.y > 0.015) for(...) { ... }`
            If(dir.y.greaterThan(0.015), () => {
                Loop({ start: 0, end: nbSample, type: 'int' }, () => {
                    If(T.lessThanEqual(0.05), () => Break());
                    const sample = clouds(p, fast);
                    If(sample.density.greaterThan(0.0), () => {
                        const intensity = lightRay(
                            p, phaseFunction, sample.density, mu,
                            sun_direction, sample.cloudHeight, fast,
                        );

                        // ambient = (0.5 + 0.6*h)*vec3(0.2, 0.5, 1.0)*6.5
                        //         + vec3(0.8) * max(0, 1 - 2*h)
                        const skyAmb = vec3(0.2, 0.5, 1.0)
                            .mul(6.5)
                            .mul(float(0.5).add(sample.cloudHeight.mul(0.6)));
                        const groundAmb = vec3(0.8, 0.8, 0.8).mul(
                            max(float(1).sub(sample.cloudHeight.mul(2)), 0),
                        );
                        const ambient = skyAmb.add(groundAmb);

                        // SUN_POWER tracks scene's DirectionalLight,
                        // attenuated by mood (stormy = darker clouds).
                        const SUN_POWER = u.sunColor
                            .mul(u.sunIntensity)
                            .mul(u.sunPowerScale)
                            .mul(u.moodSunMul);

                        const radiance = ambient.add(SUN_POWER.mul(intensity))
                            .mul(sample.density);

                        // Sebastian Hillaire's energy-conserving accumulator:
                        // color += T * (radiance - radiance*exp(-density*stepS)) / density;
                        // T *= exp(-density*stepS);
                        const transStep = exp(sample.density.mul(stepS).negate());
                        const inc = radiance.sub(radiance.mul(transStep))
                            .div(max(sample.density, 1e-6));
                        color.addAssign(T.mul(inc));
                        T.assign(T.mul(transStep));
                    });
                    p.assign(p.add(dir.mul(stepS)));
                });
            });

            // cloudColor tint applied here — multiplies the accumulated
            // cloud radiance only. Background sky and sun disk added below
            // are unaffected, so the silhouette/horizon stay neutral.
            color.assign(color.mul(u.cloudColor));

            // Background sky:
            // bg = 6 * mix(vec3(0.2,0.52,1), vec3(0.8,0.95,1), pow(0.5+0.5*mu, 15))
            //    + mix(vec3(3.5), vec3(0), min(1, 2.3*dir.y))
            const sunBlend = pow(float(0.5).add(mu.mul(0.5)).max(1e-6), 15.0);
            const bgGradient = mix(
                vec3(0.2, 0.52, 1.0), vec3(0.8, 0.95, 1.0), sunBlend,
            ).mul(6.0);
            const horizonBlend = clamp(dir.y.mul(2.3), 0, 1);
            const bgFinal = bgGradient.add(
                mix(vec3(3.5, 3.5, 3.5), vec3(0, 0, 0), horizonBlend),
            );
            color.addAssign(bgFinal.mul(T));

            // Sun disk only on slow (camera) path. Scale down from the
            // reference's 1e4 magnitude to something ACES can handle —
            // 50 keeps the sun visibly bright without overwhelming.
            if (!fast) {
                const sunDisk = vec3(50, 50, 50)
                    .mul(smoothstep(0.9998, 1.0, mu))
                    .mul(T);
                color.addAssign(sunDisk);
            }

            // Bring HDR cloud math values into ACES-friendly range.
            // Returns vec4(rgb, cloudOpacity). Alpha = 1-T = how much
            // light the cloud band absorbed/scattered along this ray.
            // Opacity=0 → clear sky (sun fully visible), 1 → opaque
            // cloud (sun fully blocked). Used by godrays for occlusion
            // and any other per-pixel cloud-density consumer.
            const opacityOut = float(1).sub(T);
            return vec4(color.mul(u.tint).mul(u.moodTint).mul(u.colorScale), opacityOut);
        };

        // Cache the sky-only RT (set inside the preSSR hook) so external
        // consumers — godrays, agent code — can read per-pixel cloud
        // opacity from its alpha channel via getCloudOpacityTex().
        let cachedSkyOnlyTex = null;

        function buildHook() {
            return {
                uniforms: u,
                getCloudOpacityTex() {
                    if (!cachedSkyOnlyTex) {
                        console.warn(
                            '[volumetric_clouds] getCloudOpacityTex called before preSSR hook ran — texture not yet built',
                        );
                    }
                    return cachedSkyOnlyTex;
                },
                update(t) {
                    u.time.value = t;
                    camera.updateMatrixWorld();
                    u.projInv.value  = camera.projectionMatrixInverse;
                    u.camWorld.value = camera.matrixWorld;
                    u.proj.value     = camera.projectionMatrix;
                    u.viewMat.value  = camera.matrixWorldInverse;

                    if (dirLight) {
                        const c = dirLight.color;
                        u.sunColor.value.set(c.r, c.g, c.b);
                        u.sunIntensity.value = dirLight.intensity;
                        // DirectionalLight points FROM .position TOWARD .target;
                        // sun_direction conventionally points TOWARD the sun.
                        u.sunDir.value
                            .copy(dirLight.position)
                            .sub(dirLight.target.position)
                            .normalize();

                        // Project sun world position to screen UV for the
                        // cloud-shafts raymarch. Distant directional lights
                        // are at huge world coords; project a point along
                        // sun direction at large distance from camera.
                        const _v = new THREE.Vector3();
                        _v.copy(u.sunDir.value).multiplyScalar(10000)
                          .add(camera.position);
                        _v.project(camera);  // mutates to NDC [-1, 1]
                        u.sunInFront.value = _v.z < 1 ? 1 : 0;
                        u.sunScreenPos.value.set(
                            _v.x * 0.5 + 0.5,
                            _v.y * 0.5 + 0.5,
                        );
                    } else {
                        u.sunIntensity.value = 0;
                        u.sunInFront.value = 0;
                    }
                    if (ambLight) {
                        const c = ambLight.color;
                        u.ambColor.value.set(c.r, c.g, c.b);
                        u.ambIntensity.value = ambLight.intensity;
                    } else {
                        u.ambIntensity.value = 0;
                    }
                },
                // PRE-SSR hook: replace sky pixels with skyRay(camera direction).
                hook(colorIn, sceneDepth, sceneNormal /*, sceneMR */) {
                    const colorTex = THREE.convertToTexture(colorIn);
                    const depthTex = THREE.convertToTexture(sceneDepth);
                    // Render JUST the sky raymarch output to its own texture
                    // (alpha=isSky), so we can denoise the sky in isolation
                    // without smoothing the rendered scene. Per-pixel skyRay
                    // sample variance shows up as faint speckle on uniform
                    // sky regions; denoise smooths that within sky pixels.
                    // Non-sky pixels are zero in this RT and stay untouched
                    // by the final composite below.
                    const skyOnly = THREE.convertToTexture(Fn(() => {
                        const screenUV = uv();
                        const sceneD = depthTex.sample(screenUV).r;
                        const isSky = step(0.9999, sceneD);
                        // skyRay returns vec4(rgb, cloudOpacity).
                        const sky = vec4(0).toVar();
                        If(isSky.greaterThan(0.5), () => {
                            const { getViewPosition } = THREE;
                            const view = getViewPosition(screenUV, float(0.5), u.projInv);
                            const ro = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                            const worldH = u.camWorld.mul(vec4(view, 1)).xyz;
                            const rd = normalize(worldH.sub(ro));
                            sky.assign(skyRay(ro, rd, u.sunDir, false));
                        });
                        // Pack: rgb = sky color, alpha = cloud opacity ×
                        // isSky (so non-sky pixels read opacity=0). The
                        // composite Fn below uses sceneDepth to detect sky
                        // (not alpha), so packing opacity into alpha
                        // doesn't affect compositing — opacity is exposed
                        // separately via getCloudOpacityTex().
                        return vec4(sky.rgb.mul(isSky), sky.a.mul(isSky));
                    })());
                    // Cache for getCloudOpacityTex().
                    cachedSkyOnlyTex = skyOnly;
                    const denoisedSky = (typeof THREE.denoise === 'function' && sceneNormal)
                        ? THREE.convertToTexture(
                            THREE.denoise(skyOnly, sceneDepth, sceneNormal, camera),
                        )
                        : skyOnly;
                    // Composite denoised sky over scene only on sky pixels.
                    // Optionally add cloud-shaft (god rays through clouds)
                    // raymarched from the sun's screen position through
                    // cloud opacity texture.
                    const SHAFT_SAMPLES = Math.max(8, Math.floor(opts.cloudShafts?.samples ?? 32));
                    return Fn(() => {
                        const screenUV = uv();
                        const sceneColor = colorTex.sample(screenUV);
                        const skySample = denoisedSky.sample(screenUV);
                        const sceneD = depthTex.sample(screenUV).r;
                        const isSky = step(0.9999, sceneD);

                        // Beer's-law screen-space god rays: march N
                        // samples along the line from this pixel toward
                        // the sun's screen position. Track MULTIPLICATIVE
                        // transmission through cloud opacity tex —
                        // densely-clouded paths drop transmission toward
                        // 0 (dark, no shaft); clear paths hold it near 1
                        // (bright shaft). Multiplicative gives proper
                        // dark/bright shaft contrast vs the additive
                        // averaging which smooths everything to uniform
                        // glow.
                        const shaftCol = vec3(0).toVar();
                        If(u.shaftEnabled.greaterThan(0.5).and(u.sunInFront.greaterThan(0.5)), () => {
                            const dirToSun = u.sunScreenPos.sub(screenUV);
                            const stepUV = dirToSun.div(float(SHAFT_SAMPLES));
                            const samplePos = screenUV.toVar();
                            const trans = float(1).toVar();
                            const illumDecay = float(1).toVar();
                            Loop({ start: 0, end: SHAFT_SAMPLES, type: 'int' }, () => {
                                samplePos.assign(samplePos.add(stepUV));
                                // Sample the UN-denoised skyOnly tex —
                                // we want CRISP cloud edges to make
                                // shafts read as clear bands, not a soft
                                // gradient. denoisedSky's smoothed alpha
                                // gives a uniform halo instead of shafts.
                                const tap = skyOnly.sample(samplePos);
                                trans.assign(trans.mul(float(1).sub(tap.a.mul(0.5))));
                                illumDecay.assign(illumDecay.mul(u.shaftDecay));
                            });
                            // Distance-from-sun falloff: bright halo
                            // immediately around sun, fades out across
                            // the screen. illumDecay accumulated over
                            // the loop ≈ shaftDecay^N at the pixel-end
                            // of the march.
                            const dist = length(dirToSun);
                            // Mild distance falloff so shafts extend across
                            // the screen (not just a small halo around the
                            // sun). exp(-1) at dist=1.0 (full screen) → 37%.
                            const distFalloff = exp(dist.mul(-1.0));
                            const shaftAmount = trans.mul(distFalloff)
                                .mul(u.shaftStrength).mul(u.shaftExposure);
                            shaftCol.assign(
                                u.sunColor.mul(u.sunIntensity).mul(shaftAmount),
                            );
                        });

                        // Cloud shadow on geometry: same shaft transmission
                        // value, but used INVERSELY to darken non-sky
                        // pixels. (1-trans) × shadowStrength = how much
                        // cloud blocks sun light reaching this surface.
                        // Reuses the same per-pixel cloud-opacity march
                        // that produced shaftCol — no extra shader cost
                        // for the shadow application itself.
                        const shadowFactor = float(1).toVar();
                        If(u.shadowEnabled.greaterThan(0.5).and(u.sunInFront.greaterThan(0.5)), () => {
                            const dirToSun2 = u.sunScreenPos.sub(screenUV);
                            const stepUV2 = dirToSun2.div(float(SHAFT_SAMPLES));
                            const samplePos2 = screenUV.toVar();
                            const trans2 = float(1).toVar();
                            Loop({ start: 0, end: SHAFT_SAMPLES, type: 'int' }, () => {
                                samplePos2.assign(samplePos2.add(stepUV2));
                                const tap2 = skyOnly.sample(samplePos2);
                                trans2.assign(trans2.mul(float(1).sub(tap2.a.mul(0.5))));
                            });
                            shadowFactor.assign(
                                float(1).sub(float(1).sub(trans2).mul(u.shadowStrength)),
                            );
                        });
                        const shadowedScene = vec4(sceneColor.rgb.mul(shadowFactor), sceneColor.a);

                        // Composite: shadowed scene OR sky+shaft.
                        const composedSky = vec4(skySample.rgb.add(shaftCol), 1);
                        return mix(shadowedScene, composedSky, isSky);
                    })();
                },
                // POST-SSR cloud-reflect hook: for reflective surfaces, shoot
                // a fast skyRay along the reflection direction and add its
                // contribution scaled by reflectivity.
                reflectHook(colorIn, sceneDepth, sceneNormal, sceneMR) {
                    const colorTex = THREE.convertToTexture(colorIn);
                    const depthTex = THREE.convertToTexture(sceneDepth);
                    return Fn(() => {
                        const screenUV = uv();
                        const sceneColor = colorTex.sample(screenUV);
                        const sceneD = depthTex.sample(screenUV).r;
                        const isSurface = step(sceneD, 0.9999);

                        const mr = sceneMR.sample(screenUV);
                        const metalness = mr.r;
                        const roughness = mr.g;
                        // PBR env-reflection weighting (matches how HDRI env-IBL
                        // and SSR weight reflections in the same scene):
                        //   contribution ∝ metalness × (1 - roughness)²
                        // The (1-roughness)² factor is the standard envBRDF
                        // approximation for the "high view angle" region of
                        // the split-sum approximation — rough surfaces fade
                        // toward zero specular contribution as energy is spread
                        // across the hemisphere, while smooth metals retain
                        // full reflection. The previous code floored the
                        // reflectivity at 0.4 × metalness regardless of
                        // roughness, which kept rough metals over-bright and
                        // blew out the ACES tonemap at any HDR cloud value.
                        const oneMinusR = float(1).sub(roughness);
                        const oneMinusR2 = oneMinusR.mul(oneMinusR);
                        const reflectivity = metalness.mul(oneMinusR2);
                        const isReflective = smoothstep(0.1, 0.4, metalness);
                        const gateMask = isReflective.mul(isSurface);
                        // Cloud-reflect contribution is composed in
                        // render_scene.mjs's autoenhance as a SSR-gated
                        // fallback (1 - SSR.alpha), so where SSR finds in-
                        // screen geometry the cloud is killed — no need
                        // for a per-hook screen-space delta gate here.

                        const { getViewPosition } = THREE;
                        const viewPos = getViewPosition(screenUV, sceneD, u.projInv);
                        const worldPos = u.camWorld.mul(vec4(viewPos, 1)).xyz;
                        const camPos = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                        const viewDir = normalize(worldPos.sub(camPos));

                        const viewNormal = sceneNormal.sample(screenUV);
                        const worldNormal = normalize(
                            u.camWorld.mul(vec4(viewNormal, 0)).xyz,
                        );
                        // Compute SHARP cloud reflection contribution.
                        // The autoenhance pipeline RTTs this output and
                        // hands it to `reflectBlurHook` for a screen-
                        // space Gaussian blur (kernel size scales with
                        // per-pixel roughness). Direction-jitter blur
                        // here would land taps on sharp cloud silhouette
                        // edges → high variance per pixel = speckle.
                        // Spatial blur on neighbouring pixels of the
                        // sharp result is much cleaner.
                        const reflDir = reflect(viewDir, worldNormal);
                        const reflRO = worldPos.add(worldNormal.mul(0.05));

                        // No SSR-style screen-space hit check here. An earlier
                        // version marched the reflection ray through space and
                        // marked the pixel "blocked" if any sample's screen-UV
                        // landed behind a closer object's depth (within a
                        // tolerance window). That produced a hard rectangular
                        // artifact on metallic floors — the screen-space
                        // silhouette of every tall scene object (laptops,
                        // pillars, brain) was cast onto the floor's reflection
                        // because the ray, while travelling upward through
                        // empty world space, projected to pixels owned by
                        // those objects. The N·up gate applied downstream in
                        // render_scene.mjs handles the brainstem /
                        // downward-normal case correctly (worldNormal.y < 0 →
                        // contribution clamped to 0), so the screen-space
                        // hit check is not needed.
                        const cloudCol = vec3(0).toVar();
                        If(gateMask.greaterThan(0.05), () => {
                            // skyRay now returns vec4(rgb, opacity) — only
                            // the rgb is needed for the reflection signal.
                            const skyRefl = skyRay(reflRO, reflDir, u.sunDir, true);
                            cloudCol.assign(
                                skyRefl.rgb.mul(reflectivity)
                                    .mul(gateMask),
                            );
                        });
                        // Return JUST the contribution (alpha=1 where
                        // contribution exists) so the blur pass can work
                        // on a clean per-pixel reflection signal. The
                        // pipeline adds it back to the scene after blur.
                        return vec4(cloudCol, 1.0);
                    })();
                },
                // Prefiltered cloud-reflection blur. Two `gaussianBlur`
                // (TSL built-in, two-pass separable) chains run on the
                // sharp cloud-reflect RT — sigma=2 (light, ~7-tap halo)
                // and sigma=8 (heavy, ~19-tap halo). Compose lerps
                // sharp → light → heavy by roughness² in two stages, so
                // mirrors get the sharp tap, brushed metals get the
                // light blur, rough surfaces get the heavy. Replaces the
                // old hand-rolled 9-tap binomial whose offsets were
                // stretched per-pixel by roughness — that pattern was
                // spatially undersampled at high roughness (9 taps over
                // a 12px halo) and left visible noise patches in the
                // reflection. Built-in chain is properly sampled at
                // every kernel size, so reflections of cloud silhouette
                // edges are clean regardless of roughness.
                reflectBlur(cloudReflContribIn, sceneDepth, sceneNormal, sceneMR) {
                    const cloudTex = THREE.convertToTexture(cloudReflContribIn);
                    if (typeof THREE.gaussianBlur !== 'function') {
                        throw new Error('[volumetric_clouds] THREE.gaussianBlur not available — render_common.mjs must import addons/tsl/display/GaussianBlurNode.js');
                    }
                    // Bilateral denoise on cloud-reflect BEFORE the gaussian
                    // chain. The per-pixel skyRay raymarch produces small
                    // per-pixel sample variance — visible as faint speckle
                    // on metallic surfaces' cloud reflection. denoise()
                    // is depth+normal aware so it smooths within a single
                    // metal surface (where depth+normal are uniform) while
                    // preserving silhouettes between surfaces. Subsequent
                    // gaussian chain then handles the roughness-weighted
                    // soft-mirror falloff on a noise-cleaned input.
                    const sharpInputTex = (typeof THREE.denoise === 'function')
                        ? THREE.convertToTexture(
                            THREE.denoise(cloudTex, sceneDepth, sceneNormal, camera),
                        )
                        : cloudTex;
                    const lightBlur = THREE.gaussianBlur(sharpInputTex, null, 2);
                    const heavyBlur = THREE.gaussianBlur(sharpInputTex, null, 8);
                    return Fn(() => {
                        const screenUV = uv();
                        const mr = sceneMR.sample(screenUV);
                        const metalness = mr.r;
                        const roughness = clamp(mr.g, 0, 1);
                        const r2 = roughness.mul(roughness);
                        const sharp = sharpInputTex.sample(screenUV).rgb;
                        // Two-stage lerp: 0..0.25 sharp→light, 0.25..1.0 light→heavy.
                        // Heavy weighting kicks in early so brushed and rough
                        // surfaces both get strong noise reduction.
                        const lightMix = smoothstep(0.0, 0.25, r2);
                        const heavyMix = smoothstep(0.25, 1.0, r2);
                        const stage1 = mix(sharp,  lightBlur.rgb, lightMix);
                        const stage2 = mix(stage1, heavyBlur.rgb, heavyMix);
                        // Re-gate by metalness AFTER the blur. Without this,
                        // the gaussianBlur(sigma=8) heavy pass spreads bright
                        // cloud contribution from metallic pixels across ~19
                        // neighbouring pixels in each direction — pixels of
                        // dielectric surfaces (cyborg organ flesh, plastic
                        // laptop body, concrete wall) sitting next to a metal
                        // edge pick up the bled-over reflection and look
                        // tinted blue. The reflectHook upstream already gates
                        // contribution by `smoothstep(0.1, 0.4, metalness)`
                        // for the per-pixel evaluation; we need the same gate
                        // again here so the blur output also respects the
                        // surface's actual metalness.
                        const isReflective = smoothstep(0.1, 0.4, metalness);
                        return vec4(stage2.mul(isReflective), 1.0);
                    })();
                },
                setSparseness,
                setMood,
                /**
                 * Bake the skyRay raymarch into an equirect texture for use
                 * as `scene.environment`. The volumetric clouds output is a
                 * post-process per-frame raymarch — it's not in the scene
                 * background and so doesn't naturally feed the env-IBL/
                 * transmission backbuffer. Baking once at applyTo() time
                 * gives transmissive materials (glass, refraction) a real
                 * cloud-sky env to sample (consistent with what the cloud-
                 * reflect hook produces on opaque metals).
                 *
                 * Returns a `THREE.RenderTarget.texture` with mapping set to
                 * EquirectangularReflectionMapping. Suitable for assignment
                 * directly to `scene.environment`, or as the input to a
                 * PMREMGenerator.fromEquirectangular() if a prefiltered
                 * cubemap is needed.
                 *
                 * @param {THREE.WebGPURenderer} renderer
                 * @param {{width?: number, height?: number}} [opts]
                 * @returns {Promise<THREE.Texture>} resolves once render done
                 */
                async bakeEnvEquirect(renderer, opts = {}) {
                    const W = opts.width  ?? 512;
                    const H = opts.height ?? 256;
                    const target = new THREE.RenderTarget(W, H, {
                        type: THREE.HalfFloatType,
                        format: THREE.RGBAFormat,
                        depthBuffer: false,
                        stencilBuffer: false,
                    });
                    target.texture.mapping = THREE.EquirectangularReflectionMapping;
                    target.texture.minFilter = THREE.LinearFilter;
                    target.texture.magFilter = THREE.LinearFilter;
                    target.texture.colorSpace = THREE.LinearSRGBColorSpace;
                    target.texture.name = 'volumetric_clouds_env';

                    // Update sun uniform first so the bake reflects the
                    // current scene lighting (caller may have changed
                    // sun colour/intensity since applyTo()).
                    if (typeof this.update === 'function') this.update(0);

                    const PI = Math.PI;
                    const bakeMat = new THREE.NodeMaterial();
                    bakeMat.fragmentNode = Fn(() => {
                        const screenUV = uv();
                        const lon = screenUV.x.mul(PI * 2).sub(PI);
                        const lat = screenUV.y.sub(0.5).mul(PI);
                        const cosLat = cos(lat);
                        const dir = normalize(vec3(
                            cosLat.mul(sin(lon)),
                            sin(lat),
                            cosLat.mul(cos(lon)),
                        ));
                        const ro = vec3(0, 0, 0);
                        // skyRay returns vec4(rgb, opacity) — keep opacity
                        // in alpha for any future env-IBL use.
                        return skyRay(ro, dir, u.sunDir, false);
                    })();

                    const bakeScene = new THREE.Scene();
                    const bakeCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
                    const bakeQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bakeMat);
                    bakeScene.add(bakeQuad);

                    const prevTarget = renderer.getRenderTarget?.();
                    renderer.setRenderTarget(target);
                    if (typeof renderer.renderAsync === 'function') {
                        await renderer.renderAsync(bakeScene, bakeCam);
                    } else {
                        renderer.render(bakeScene, bakeCam);
                    }
                    renderer.setRenderTarget(prevTarget ?? null);

                    bakeQuad.geometry.dispose();
                    bakeMat.dispose?.();
                    return target.texture;
                },
            };
        }

        const built = buildHook();
        if (opts.disableForPerfTest) {
            console.log('[volumetric_clouds] PERF TEST: hooks disabled');
            return { update(t) { built.update(t); }, uniforms: u, setSparseness: built.setSparseness, setMood: built.setMood };
        }

        // Screen-space cloud rendering pipeline:
        //   - preSSR-hook: replaces sky pixels with skyRay raymarched colour
        //   - reflectHook: per-metal-pixel raymarch in reflection direction
        //   - reflectBlur: roughness-weighted blur of the reflection contribution
        // This is the per-frame mechanism for moving cloud reflections on
        // metals (PMREM is one-time prefilter — not the right tool for
        // animated env). The cloud-reflect compose in render_scene.mjs's
        // autoenhance gates this contribution by (1 - SSR.alpha) so where
        // SSR finds in-screen geometry to reflect, cloud-reflect is killed.
        // For enclosed scenes the screen-space algorithm has known limits
        // (off-frustum walls/ceiling can't be sampled by SSR → cloud may
        // bleed into directions that should reflect interior geometry),
        // but the resulting clouds-at-the-silhouette read more naturally
        // than they harm — and agents picking volumetric_clouds for an
        // enclosed scene is a rare combination anyway.
        // Sentinel for mutual-exclusion: standalone `godrays` effect
        // throws if this is set, since godrays' shadow-map approach can't
        // see screen-space cloud occlusion. Cloud shafts are computed
        // internally below via the cloudShafts opt instead.
        globalThis._volumetricCloudsActive = true;

        globalThis._autoEnhancePreSSRHook = (colorOut, sceneDepth, sceneNormal, sceneMR) =>
            built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        globalThis._autoEnhanceCloudReflectHook =
            (colorOut, sceneDepth, sceneNormal, sceneMR) =>
                built.reflectHook(colorOut, sceneDepth, sceneNormal, sceneMR);
        globalThis._autoEnhanceCloudReflectBlurHook =
            (cloudReflTex, sceneDepth, sceneNormal, sceneMR) =>
                built.reflectBlur(cloudReflTex, sceneDepth, sceneNormal, sceneMR);
        return {
            update(t) { built.update(t); },
            uniforms: u,
            setSparseness: built.setSparseness,
            setMood: built.setMood,
            bakeEnvEquirect: built.bakeEnvEquirect.bind(built),
            // Returns the per-pixel cloud-opacity TextureNode (alpha
            // channel of the sky-only RT). Consumers like godrays can
            // use this to attenuate by cloud occlusion. Only valid AFTER
            // the preSSR hook has run at least once (which builds the RT).
            getCloudOpacityTex() { return built.getCloudOpacityTex(); },
        };
    }

    globalThis.VolumetricCloudsFX = { applyTo };
    console.log('[volumetric_clouds] registered');
})();
