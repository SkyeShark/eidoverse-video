// sky_system.js — WORLD-SPACE volumetric sky for eidoverse.
//
// Replaces the old screenspace cloud pipeline's weak spots:
//   · clouds live on a camera-centered DOME rendered in the scene pass —
//     depth-tests against geometry natively (no depth-keying), rays are
//     world-anchored (no off-frame-sun striping), edges get real MSAA
//   · a proper SUN: HDR disc + corona on the celestial layer, and a
//     time-of-day palette that drives cloud lighting AND scene lights
//   · night: NASA moon (real face from the LROC color map, real phases from
//     sun-relative lighting) + Tycho star map, slow sky rotation
//   · cloud TYPES: cumulus / stratus / cirrus / clear as uniform presets
//   · distance fade into horizon haze (kills the hard horizon clamp band)
//   · optional pure-sky HDRI backdrop blended under the procedural layers
//
// Cloud density/lighting math carried over from the old screenspace effect
// (two-stage FBM erosion, numerical Mie phase, Beer's law + powdered effect,
// Hillaire energy-conserving accumulation) — same look, new home.
//
//   const sky = await makeSkySystem({ scene, textures: { stars, moon, hdri? } });
//   sky.setTime(18.6);            // hours 0-24 (drives sun+moon arcs)
//   sky.setClouds('cumulus');     // cumulus | stratus | cirrus | clear
//   sky.applyToLights({ sun, hemi, fog: scene.fog });
//   // per frame: sky.update(t, camera)
(function () {
    const T3 = globalThis.THREE;
    const {
        uniform, Fn, vec2, vec3, vec4, float, Loop, Break, If,
        sin, cos, fract, floor, mix, clamp, smoothstep, step, dot, length,
        normalize, max, min, abs, exp, pow, sqrt, acos, asin,
        positionWorld, cameraPosition, screenCoordinate,
    } = T3;
    const atan2f = T3.atan2 || T3.atan;
    const V = (x, y, z) => new T3.Vector3(x, y, z);

    // ---------------- time-of-day palette (sun-elevation keyed, degrees) ----------------
    const TOD = [
        { el: -18, zen: [0.010, 0.016, 0.055], hor: [0.030, 0.042, 0.10], sun: [0.55, 0.65, 0.95], int: 0.00, star: 1.00 },
        { el: -6,  zen: [0.022, 0.045, 0.115], hor: [0.190, 0.120, 0.19], sun: [1.00, 0.42, 0.22], int: 0.10, star: 0.85 },
        { el: 0,   zen: [0.070, 0.130, 0.300], hor: [1.000, 0.560, 0.32], sun: [1.00, 0.48, 0.23], int: 0.55, star: 0.25 },
        { el: 8,   zen: [0.160, 0.340, 0.700], hor: [1.000, 0.760, 0.55], sun: [1.00, 0.69, 0.41], int: 1.60, star: 0.00 },
        { el: 30,  zen: [0.150, 0.380, 0.820], hor: [0.620, 0.780, 0.92], sun: [1.00, 0.94, 0.86], int: 2.60, star: 0.00 },
        { el: 70,  zen: [0.110, 0.350, 0.800], hor: [0.600, 0.760, 0.90], sun: [1.00, 1.00, 1.00], int: 3.00, star: 0.00 },
    ];
    const lerpA = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
    const todAt = (elDeg) => {
        if (elDeg <= TOD[0].el) return TOD[0];
        if (elDeg >= TOD[TOD.length - 1].el) return TOD[TOD.length - 1];
        for (let i = 0; i < TOD.length - 1; i++) {
            const a = TOD[i], b = TOD[i + 1];
            if (elDeg >= a.el && elDeg <= b.el) {
                const k = (elDeg - a.el) / (b.el - a.el);
                return { el: elDeg, zen: lerpA(a.zen, b.zen, k), hor: lerpA(a.hor, b.hor, k), sun: lerpA(a.sun, b.sun, k), int: a.int + (b.int - a.int) * k, star: a.star + (b.star - a.star) * k };
            }
        }
        return TOD[2];
    };

    // ---------------- cloud presets ----------------
    const PRESETS = {
        // thresholds tuned for the 1/f weather map (mean ~0.5): largeT sets
        // sky fraction covered by macro masses, weatherT carves puffs inside
        // them. finalMul 0.2 = reference density.
        // The high 2D layer is part of each preset rather than one generic
        // grey sheet.  wispOpacity converts procedural coverage to alpha;
        // wispColor remains straight radiance and is premultiplied by that
        // alpha in cloudBody below.
        cumulus: { largeT: 0.42, largeA: 3.0, weatherT: 0.30, finalMul: 0.20, wScale: 1.0, dScale: 1.0, start: 700, height: 520, stretch: [1, 1, 1], lightK: 1.0, lightCacheDirect: 0,
            wispOn: 0.28, wispScale: 0.00125, wispThreshold: 0.48, wispStrength: 0.70, wispOpacity: 1.45, wispFloor: 0.0, wispStretch: [0.75, 0.35, 1.65], wispFilament: 0.18, wispTint: [1.0, 0.98, 0.94] },
        stratus: { largeT: 0.12, largeA: 2.0, weatherT: 0.08, finalMul: 0.16, wScale: 0.55, dScale: 0.7, start: 520, height: 170, stretch: [1, 0.7, 1], lightK: 0.7, lightCacheDirect: 0,
            wispOn: 0.72, wispScale: 0.00082, wispThreshold: 0.36, wispStrength: 0.82, wispOpacity: 1.05, wispFloor: 0.0, wispStretch: [0.90, 0.28, 1.15], wispFilament: 0.04, wispTint: [0.72, 0.79, 0.88] },
        // Cirrus is a sparse ice veil led by the filament layer, not the
        // cumulus density model crushed into horizontal scanlines.
        cirrus:  { largeT: 0.48, largeA: 2.0, weatherT: 0.34, finalMul: 0.0, wScale: 1.2, dScale: 1.0, start: 3400, height: 230, stretch: [0.55, 1.1, 1.8], lightK: 0.16, lightCacheDirect: 0,
            wispOn: 1.0, wispScale: 0.00030, wispThreshold: 0.43, wispStrength: 1.08, wispOpacity: 1.00, wispFloor: 0.0, wispStretch: [0.052, 0.14, 2.05], wispFilament: 1.0, wispTint: [0.98, 0.99, 1.0] },
        clear:   { largeT: 0.95, largeA: 1.0, weatherT: 0.95, finalMul: 0.00, wScale: 1.0, dScale: 1.0, start: 700, height: 520, stretch: [1, 1, 1], lightK: 0.0, lightCacheDirect: 0,
            wispOn: 0.0, wispScale: 0.001, wispThreshold: 1.0, wispStrength: 0.0, wispOpacity: 0.0, wispFloor: 0.0, wispStretch: [1, 1, 1], wispFilament: 0.0, wispTint: [1, 1, 1] },
    };

    globalThis.makeSkySystem = async function makeSkySystem({ scene, textures = {}, opts = {} } = {}) {
        const R_EARTH = opts.earthRadius ?? 6371000;
        const DOME_R = opts.domeRadius ?? 3200;
        const N_MARCH = opts.skySamples ?? 60;
        const N_LIGHT = opts.lightSamples ?? 20;
        // Dark Thunderstorm uses a bounded lowest-layer integration. Two
        // interleaved eight-step strata resolve real foreground/deep overlap
        // without marching the invisible remainder of the 19.3 km system.
        const N_STORM_STEPS = 12;
        const N_STORM_PASSES = 2;
        // Cloud shadows are a sky-budget item, but 2-6 taps integrated a
        // fine erosion-bearing density so coarsely that a drifting cloud
        // edge SNAPPED whole flat surfaces between shaded and unshaded.
        // A 12-tap floor keeps the travelling patches while their edges
        // sweep smoothly; each tap is one cheapDensity fbm evaluation.
        const N_CLOUD_SHADOW = Math.max(12, Math.min(16,
            Math.round(opts.cloudShadowSamples ?? (N_MARCH / 3))));
        // The old animated interleaved-gradient output dither becomes visible
        // as diagonal line grain after the optimized pass is downsampled and
        // enlarged. These domes render in HDR (including the offscreen cloud
        // target), so quantization dither belongs after tone mapping, not in
        // cloud radiance. Keep an explicit lookdev opt-in, but ship it off.
        const OUTPUT_DITHER = Math.max(0, opts.outputDither ?? 0);

        // ---------------- uniforms (JS-driven state) ----------------
        const u = {
            time: uniform(0),
            sunDir: uniform(V(0, 0.3, 1).normalize()),        // true sun (disc, palette)
            cloudLightDir: uniform(V(0, 0.3, 1).normalize()), // sun by day, moon by night
            cloudLightColor: uniform(V(1, 0.9, 0.8)),
            cloudAmbSky: uniform(V(0.2, 0.5, 1.0)),
            cloudAmbGround: uniform(V(0.8, 0.8, 0.8)),
            zenith: uniform(V(0.15, 0.38, 0.82)),
            horizon: uniform(V(0.62, 0.78, 0.92)),
            sunColor: uniform(V(1, 0.95, 0.9)),
            sunDiscI: uniform(48),
            sunGlowI: uniform(1),      // forward-scatter glow lobes gate — scenes with a custom celestial body AS the sun zero this (the disc obeys sunDiscI; these lobes previously bled a bright white core through any body riding sunDir)
            frameJit: uniform(0),      // EANPA: per-frame golden-ratio phase for temporal blue-noise jitter (fed by the cloud frame graph)
            starFade: uniform(0),
            // additive night skyglow (light pollution): a scene with a glowing
            // shield/city lifts the sky background and drowns faint stars.
            // Default black = zero change anywhere it isn't driven.
            skyGlow: uniform(new T3.Color(0, 0, 0)),
            moonDir: uniform(V(0, -1, 0)),
            moonRight: uniform(V(1, 0, 0)),
            moonUp: uniform(V(0, 1, 0)),
            moonCos: uniform(Math.cos((opts.moonAngularDeg ?? 1.6) * Math.PI / 360 * 2)),
            moonLightK: uniform(0),
            hdriMix: uniform(textures.hdri ? (opts.hdriMix ?? 0.55) : 0),
            hdriDim: uniform(1),
            // cloud preset uniforms
            largeT: uniform(0.18), largeA: uniform(3.0), weatherT: uniform(0.28), finalMul: uniform(0.40),
            wScale: uniform(1.0), dScale: uniform(1.0),
            cloudStart: uniform(700), cloudHeight: uniform(520),
            stretch: uniform(V(1, 1, 1)),
            lightK: uniform(1.0),
            // Dense storms expose the light froxel's fixed integration phase
            // as dark contour rims. Their authored override switches only the
            // lighting back to the live stratified sun march; density caching
            // remains active.
            lightCacheDirect: uniform(0),
            cloudTint: uniform(V(1, 1, 1)),
            cloudDim: uniform(1),      // weather-system hook for rain, shafts, and Ringworld reflection response
            cloudRadiance: uniform(1), // cloud-form readability; severe weather may lift this without brightening rain/shafts/ring
            wispColor: uniform(V(0.8, 0.8, 0.8)),
            wispTint: uniform(V(1, 1, 1)),
            wispStretch: uniform(V(1, 1, 1)),
            wispOn: uniform(0.28),
            wispScale: uniform(0.00125),
            wispThreshold: uniform(0.48),
            wispStrength: uniform(0.7),
            wispOpacity: uniform(1.45),
            // Dense weather fronts can require a continuous high-cloud canopy
            // between volumetric masses. Zero for ordinary cloud presets;
            // weather transitions author and interpolate it explicitly.
            wispFloor: uniform(0),
            wispFilament: uniform(0.18),
            // Dark Thunderstorm renders only the lowest part of its semantic
            // ~19.3 km cumulonimbus system: a bounded 1.1-1.45 km core/scud
            // volume. Settled storms keep the ordinary volumetric march as a
            // foreground underlayer (upper wisps stay off), while Beer
            // extinction supplies the sealed backing behind it.
            stormCanopy: uniform(0),
            celestialVisibility: uniform(1),
            lightningFlashColor: uniform(V(1, 1, 1)),
            // xyz = world strike origin; w = instantaneous flash strength.
            lightningStrike: uniform(new T3.Vector4(0, 500, 0, 0)),
            shaftK: uniform(opts.shafts ?? 0),
            shaftDen: uniform(opts.shaftDensity ?? 3e-5),
            precipK: uniform(0),   // world rain: curtain density under dense weather cells (weather-system hook)
            precipLo: uniform(0.95), precipHi: uniform(1.55),
            skyWind: uniform(V(0, 0, 10.3)), // ONE wind drives cloud drift, weather-cell motion, and (via weather system) rain shear
            wallCloud: uniform(new T3.Vector4(0, 0, 1, 0)), // (x, z, radius, strength): local cloud-base LOWERING (tornado wall cloud)
            fadeDist: uniform(opts.cloudFadeDist ?? 26000),
            cloudShadowStrength: uniform(1),
            projInv: uniform(new T3.Matrix4()),
            camWorld: uniform(new T3.Matrix4()),
        };

        // ---------------- shared noise (donor pattern: data-texture value noise) ----------------
        const NSZ = 256;
        const pix = new Uint8Array(NSZ * NSZ * 4);
        let seed = 987654321 >>> 0;
        const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
        for (let i = 0; i < pix.length; i++) pix[i] = (rnd() * 256) | 0;
        const noiseTex = new T3.DataTexture(pix, NSZ, NSZ, T3.RGBAFormat);
        noiseTex.wrapS = noiseTex.wrapT = T3.RepeatWrapping;
        noiseTex.minFilter = noiseTex.magFilter = T3.LinearFilter;
        noiseTex.needsUpdate = true;
        const noiseNode = T3.texture(noiseTex);

        const noise2 = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            return noiseNode.sample(i.add(sm).add(0.5).div(NSZ)).level(0).r;   // EANPA: explicit LOD — Chrome/Tint forbids implicit-derivative sampling in divergent flow
        };
        const noise3 = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            const uvx = i.x.add(float(37).mul(i.z)).add(sm.x);
            const uvy = i.y.add(float(17).mul(i.z)).add(sm.y);
            const t = noiseNode.sample(vec2(uvx, uvy).add(0.5).div(NSZ)).level(0);   // EANPA: explicit LOD
            return mix(t.r, t.g, sm.z);
        };
        // tileable 1/f WEATHER map — thresholding white noise gives fuzz, not
        // cloud MASSES (equal power at all scales); masses need low-frequency
        // dominance. 5-octave fbm, .r = macro coverage field, .g = independent
        // puff-scale field. One-time startup fill (~ms), not per-frame work.
        const WSZ = 512;
        const wpix = new Uint8Array(WSZ * WSZ * 4);
        const wHash = (i, j, s) => {
            let n = (i * 374761393 + j * 668265263 + s * 2246822519) >>> 0;
            n = Math.imul(n ^ (n >>> 13), 1274126177) >>> 0;
            return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
        };
        const fbmAt = (uu, vv, seedBase, baseCells = 8) => {
            let val = 0, amp = 0.5, cells = baseCells, norm = 0;
            for (let o = 0; o < 5; o++) {
                const x = uu * cells, y = vv * cells;
                const xi = Math.floor(x), yi = Math.floor(y);
                const xf = x - xi, yf = y - yi;
                const sx = xf * xf * xf * (xf * (xf * 6 - 15) + 10), sy = yf * yf * yf * (yf * (yf * 6 - 15) + 10);
                const w = (a, b) => wHash(((a % cells) + cells) % cells, ((b % cells) + cells) % cells, seedBase + o);
                const n0 = w(xi, yi) + (w(xi + 1, yi) - w(xi, yi)) * sx;
                const n1 = w(xi, yi + 1) + (w(xi + 1, yi + 1) - w(xi, yi + 1)) * sx;
                val += amp * (n0 + (n1 - n0) * sy);
                norm += amp; amp *= 0.55; cells *= 2;
            }
            return Math.min(1, Math.max(0, ((val / norm) - 0.5) * 1.9 + 0.5));
        };
        for (let wy = 0; wy < WSZ; wy++) for (let wx = 0; wx < WSZ; wx++) {
            const k = (wy * WSZ + wx) * 4;
            wpix[k] = (fbmAt(wx / WSZ, wy / WSZ, 11) * 255) | 0;
            // .g starts 4 octaves up (cells 32..512): same puff feature sizes as
            // before but the tile is the full 20 km — the old 5 km repeat put ~5
            // copies of the same puff layout across the visible deck (read as
            // seams/pinches where the pattern met itself)
            wpix[k + 1] = (fbmAt(wx / WSZ, wy / WSZ, 137, 32) * 255) | 0;
            wpix[k + 2] = 0; wpix[k + 3] = 255;
        }
        const weatherTex = new T3.DataTexture(wpix, WSZ, WSZ, T3.RGBAFormat);
        weatherTex.wrapS = weatherTex.wrapT = T3.RepeatWrapping;
        weatherTex.minFilter = weatherTex.magFilter = T3.LinearFilter;
        weatherTex.needsUpdate = true;
        const weatherNode = T3.texture(weatherTex);

        const m0 = vec3(0.0, 0.8, 0.6), m1 = vec3(-0.8, 0.36, -0.48), m2 = vec3(-0.6, -0.48, 0.64);
        const applyM = (p) => vec3(dot(p, m0), dot(p, m1), dot(p, m2));
        const fbm3 = (p) => {
            const pp = p.toVar();
            const f = noise3(pp).mul(0.5).toVar();
            pp.assign(applyM(pp).mul(2.02));
            f.addAssign(noise3(pp).mul(0.25));
            pp.assign(applyM(pp).mul(2.03));
            f.addAssign(noise3(pp).mul(0.125));
            return f;
        };
        const hash11 = (n) => fract(sin(n).mul(43758.5453));
        // Pixel jitter needs a genuine 2D decorrelating hash. Feeding screen
        // XY plus a constant Z through hash3 leaves one factor constant and
        // exposes product-hash ridges as intermittent diagonal/line grain in
        // low-resolution Ringworld and storm passes. Hoskins' bounded 2D→1D
        // hash is stable frame-to-frame but has no directional ramp lattice.
        const hashScreen = (pIn) => {
            const a = fract(vec3(pIn.x, pIn.y, pIn.x).mul(vec3(0.1031, 0.1030, 0.0973)));
            const d = dot(a, vec3(a.y, a.z, a.x).add(33.33));
            const b = a.add(d);
            return fract(b.x.add(b.y).mul(b.z));
        };
        // analytic 3D value noise — the texture-slice noise3 (uv = xy + (37,17)·z)
        // carries a periodic diagonal correlation lattice; inside the cloud march
        // it's integrated away, but painted bare (wisp layer, one sample/pixel)
        // it renders as parallelogram shards. ALU hash + trilinear is artifact-free
        // and only runs once per pixel. The hash must be sin-FREE: the wisp domain
        // reaches ±250 lattice units and GPU sin() argument reduction breaks down
        // there, banding fract(sin(big)*43758) into straight-edged plates (bisect-
        // verified with wispOn=0). Bounded products only.
        const hash3 = (pIn) => {
            const q = fract(pIn.mul(0.3183099).add(vec3(0.1, 0.17, 0.13))).mul(17);
            return fract(q.x.mul(q.y).mul(q.z).mul(q.x.add(q.y).add(q.z)));
        };
        const noise3A = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            const nx0 = mix(hash3(i), hash3(i.add(vec3(1, 0, 0))), sm.x);
            const nx1 = mix(hash3(i.add(vec3(0, 1, 0))), hash3(i.add(vec3(1, 1, 0))), sm.x);
            const nx2 = mix(hash3(i.add(vec3(0, 0, 1))), hash3(i.add(vec3(1, 0, 1))), sm.x);
            const nx3 = mix(hash3(i.add(vec3(0, 1, 1))), hash3(i.add(vec3(1, 1, 1))), sm.x);
            return mix(mix(nx0, nx1, sm.y), mix(nx2, nx3, sm.y), sm.z);
        };
        const fbm3A = (p) => {
            const pp = p.toVar();
            const f = noise3A(pp).mul(0.5).toVar();
            pp.assign(applyM(pp).mul(2.02));
            f.addAssign(noise3A(pp).mul(0.25));
            pp.assign(applyM(pp).mul(2.03));
            f.addAssign(noise3A(pp).mul(0.125));
            return f;
        };
        // Optional optimized-tier 3D density BASIS. This caches the random
        // lattice used by the erosion FBM, not the animated cloudsAt result:
        // weather, height, wind, both erosion stages, and all FBM octaves stay
        // live. Cinematic never constructs or samples this texture.
        const densityCacheOpts = opts.densityCache || null;
        const densityCacheSize = densityCacheOpts ? Math.max(32, densityCacheOpts.size ?? 128) : 0;
        let densityBasisTex = null;
        let fbm3Cached = null;
        if (densityCacheSize) {
            const basisStore = globalThis._eanpaDensityBasisCache ??= new Map();
            densityBasisTex = basisStore.get(densityCacheSize);
            if (!densityBasisTex) {
                const P = densityCacheSize;
                const data = new Uint8Array(P * P * P);
                const fractJS = (v) => v - Math.floor(v);
                let k = 0;
                for (let z = 0; z < P; z++) for (let y = 0; y < P; y++) for (let x = 0; x < P; x++) {
                    const qx = fractJS(x * 0.3183099 + 0.10) * 17;
                    const qy = fractJS(y * 0.3183099 + 0.17) * 17;
                    const qz = fractJS(z * 0.3183099 + 0.13) * 17;
                    data[k++] = Math.min(255, Math.max(0, Math.floor(fractJS(qx * qy * qz * (qx + qy + qz)) * 256)));
                }
                densityBasisTex = new T3.Data3DTexture(data, P, P, P);
                densityBasisTex.format = T3.RedFormat;
                densityBasisTex.type = T3.UnsignedByteType;
                densityBasisTex.wrapS = densityBasisTex.wrapT = densityBasisTex.wrapR = T3.RepeatWrapping;
                densityBasisTex.minFilter = densityBasisTex.magFilter = T3.LinearFilter;
                densityBasisTex.generateMipmaps = false;
                densityBasisTex.flipY = false;
                densityBasisTex.unpackAlignment = 1;
                densityBasisTex.colorSpace = T3.NoColorSpace;
                densityBasisTex.name = `eanpa_density_basis_${P}`;
                densityBasisTex.needsUpdate = true;
                basisStore.set(P, densityBasisTex);
            }
            const P = densityCacheSize;
            const basisNode = T3.texture3D(densityBasisTex);
            const noise3Cached = (p) => {
                const i = floor(p), f = fract(p);
                const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
                const uvw = fract(i.div(P)).add(sm.add(0.5).div(P));
                return basisNode.sample(uvw).level(0).r;
            };
            fbm3Cached = (p) => {
                const pp = p.toVar();
                const f = noise3Cached(pp).mul(0.5).toVar();
                pp.assign(applyM(pp).mul(2.02));
                f.addAssign(noise3Cached(pp).mul(0.25));
                pp.assign(applyM(pp).mul(2.03));
                f.addAssign(noise3Cached(pp).mul(0.125));
                return f;
            };
        }
        // EROSION NOISE: true-3D ALU noise, NOT the texture-slice fbm3. The
        // slice noise's diagonal correlation lattice prints PARALLELOGRAM
        // PLATES through the density field wherever the march can't integrate
        // it away — bare in thin night cloud, and the long-parked daytime
        // "lines rolling over the clouds" share its geometry. fbm3A is the
        // same octave structure with an artifact-free lattice (wisp-proven).
        // opts.texSliceNoise = legacy path for A/B.
        const fbmE = fbm3Cached ?? (opts.texSliceNoise ? fbm3 : fbm3A);

        // ---------------- cloud density (reference two-stage erosion, preset-driven) ----------------
        // weather is sampled RAW like the reference (uv in tile units: one .r tile
        // = 20 km, one .g tile = 5 km) but from the 1/f weather map above — raw
        // WHITE noise reproduced the reference's single heavy-deck look (42% of
        // samples saturate the (x-0.18)*5 gain) and its y-less texels extrude
        // into 520 m curtain columns. The 1/f field gives thresholds real
        // coverage control with distinct masses.
        const wSampleL = (uvNode) => weatherNode.sample(uvNode).level(0).r;   // EANPA: explicit LOD
        const wSampleS = (uvNode) => weatherNode.sample(uvNode).level(0).g;   // EANPA: explicit LOD
        const earthC = vec3(0, -R_EARTH, 0);
        const wallLower = (pIn) => {
            // wallCloud packing: (.x = world x, .y = world z, .z = radius, .w = strength)
            const wdx = pIn.x.sub(u.wallCloud.x), wdz = pIn.z.sub(u.wallCloud.y);
            const r2 = u.wallCloud.z.mul(u.wallCloud.z);
            return u.wallCloud.w.mul(exp(wdx.mul(wdx).add(wdz.mul(wdz)).div(r2).negate()));
        };
        // slope-aware weather decorrelation: the weather map is y-less, so a
        // coverage column paints ONE value up the whole layer — fine on a
        // flat deck, but on the ring corner's climb every column extrudes
        // into a slope-length streamer (drape and sample-count A/Bs both
        // left the streaks — they're density structure). Shearing the
        // lookup by in-layer height, gated by |slope|, breaks the climb
        // into stacked cells and is an exact no-op wherever the deck is flat.
        const ringZShear = (pIn, ch) => RING_R
            ? ringSlopeAt(pIn).mul(ch).mul(RING_THICK * 2.0)
            : float(0);
        const cloudsAt = (pIn) => {
            const p = pIn.mul(u.stretch);
            const atmoH = atmoHeight(pIn);
            const ch = atmoH.sub(u.cloudStart.sub(wallLower(pIn).mul(260))).div(u.cloudHeight).clamp(0, 1);
            const zW = ringZShear(pIn, ch);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const largeWeather = clamp(wSampleL(vec2(p1.z.add(zW), p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const weather2 = max(wSampleS(vec2(p2.z.add(zW), p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = largeWeather.mul(weather2)
                .mul(smoothstep(0.0, 0.5, ch))
                .mul(float(1).sub(smoothstep(0.5, 1.0, ch)));
            const shapeExp = float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch)));
            const cloudShape = pow(weather.max(1e-6), shapeExp);
            const p3 = p2.add(vec3(u.time.mul(12.3), 0, 0));
            const den1 = max(cloudShape.sub(fbmE(p3.mul(float(0.01).mul(u.dScale))).mul(0.7)), 0);
            const p4 = p3.add(vec3(0, u.time.mul(15.2), 0));
            const den2 = max(den1.sub(fbmE(p4.mul(float(0.05).mul(u.dScale))).mul(0.2)), 0);
            return { density: largeWeather.mul(u.finalMul).mul(min(den2.mul(5), 1)).mul(ringStrip(pIn)), ch };
        };
        // light-march density = reference "fast" path: full weather + first
        // erosion. The old crude blob approximation self-shadowed a DIFFERENT
        // cloud field than the camera march saw — blotchy interior shading.
        const cheapDensity = (pIn) => {
            const p = pIn.mul(u.stretch);
            const atmoH = atmoHeight(pIn);
            const ch = atmoH.sub(u.cloudStart).div(u.cloudHeight).clamp(0, 1);
            const zW = ringZShear(pIn, ch);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const lw = clamp(wSampleL(vec2(p1.z.add(zW), p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const w2 = max(wSampleS(vec2(p2.z.add(zW), p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = lw.mul(w2)
                .mul(smoothstep(0.0, 0.5, ch))
                .mul(float(1).sub(smoothstep(0.5, 1.0, ch)));
            const shape = pow(weather.max(1e-6), float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch))));
            const p3 = p2.add(vec3(u.time.mul(12.3), 0, 0));
            const den = max(shape.sub(fbmE(p3.mul(float(0.01).mul(u.dScale))).mul(0.7)), 0);
            return lw.mul(u.finalMul).mul(min(den.mul(5), 1)).mul(ringStrip(pIn));
        };
        // Erosion-free density proxy for sparse light integration. Real beams
        // and severe-weather shadows are cast by cloud MASSES, not 20-100 m
        // erosion froth: undersampling the detailed field makes shafts flicker
        // and prints dark contour rims across dense storm faces. Weather
        // coverage × height profile only → stable, mass-shaped lighting.
        const smoothDensity = (pIn) => {
            const p = pIn.mul(u.stretch);
            const ch = atmoHeight(pIn).sub(u.cloudStart.sub(wallLower(pIn).mul(260))).div(u.cloudHeight).clamp(0, 1);
            const zW = ringZShear(pIn, ch);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const lw = clamp(wSampleL(vec2(p1.z.add(zW), p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const w2 = max(wSampleS(vec2(p2.z.add(zW), p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = lw.mul(w2)
                .mul(smoothstep(0.0, 0.5, ch))
                .mul(float(1).sub(smoothstep(0.5, 1.0, ch)));
            const shape = pow(weather.max(1e-6), float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch))));
            return lw.mul(u.finalMul).mul(min(shape.mul(3.5), 1)).mul(ringStrip(pIn));
        };
        const phaseMie = (c) => {
            const p1 = c.add(0.8194068);
            return exp(c.mul(-65.0).sub(55.0)).mul(9.805233e-6)
                .add(exp(p1.mul(p1).mul(-83.70334)).mul(0.1388198))
                .add(exp(c.mul(7.810083)).mul(2.054747e-3))
                .add(exp(c.mul(-4.552125e-12)).mul(2.600563e-2));
        };
        const lightCacheOpts = opts.lightCache || null;
        const DIRECT_LIGHT_MASS_SCALE = 0.25;
        let sampleLightCache = null;
        const lightRay = (p, phaseF, dC, mu, ch, jitL) => {
            const stepL = clamp(u.cloudHeight.mul(2.2), 380, 700).div(N_LIGHT);
            const den = float(0).toVar();
            const j0 = jitL ?? float(0.5);
            const addDetailedLight = (target) => {
                for (let j = 0; j < N_LIGHT; j++) target.addAssign(
                    cheapDensity(p.add(u.cloudLightDir.mul(stepL).mul(j0.add(j)))),
                );
            };
            const addMassLight = (target) => {
                for (let j = 0; j < N_LIGHT; j++) target.addAssign(
                    smoothDensity(p.add(u.cloudLightDir.mul(stepL).mul(j0.add(j)))).mul(DIRECT_LIGHT_MASS_SCALE),
                );
            };
            // A stable base phase plus golden-ratio per-pass steps provides
            // quasi-uniform staircase-phase coverage without introducing a
            // camera-moving random sequence into the nested light march.
            if (lightCacheOpts) {
                // Keep one persistent graph, but restore the live per-pass
                // phase for optically dense states where the cached midpoint
                // becomes visible as nested dark slice boundaries. Weather
                // morphs this route over 45 seconds, so blend the two density
                // estimates rather than snapping branches at the midpoint.
                const cachedDen = float(0).toVar();
                const directDen = float(0).toVar();
                If(u.lightCacheDirect.lessThan(0.999), () => {
                    cachedDen.assign(sampleLightCache(p));
                });
                If(u.lightCacheDirect.greaterThan(0.001), () => {
                    // Severe weather keeps the detailed visible density, but
                    // its sparse sun march follows the low-frequency cloud
                    // mass. Sampling the erosion froth here turns every
                    // under-resolved noise crossing into a dark contour rim.
                    addMassLight(directDen);
                });
                den.assign(mix(cachedDen, directDen, clamp(u.lightCacheDirect, 0, 1)));
            } else {
                // Cache-disabled lookdev must preserve the same severe-weather
                // semantics. Blend detailed and mass densities during the
                // authored transition instead of silently returning to the
                // erosion-rim path whenever ?cache=none is used.
                const detailedDen = float(0).toVar();
                const massDen = float(0).toVar();
                If(u.lightCacheDirect.lessThan(0.999), () => { addDetailedLight(detailedDen); });
                If(u.lightCacheDirect.greaterThan(0.001), () => { addMassLight(massDen); });
                den.assign(mix(detailedDen, massDen, clamp(u.lightCacheDirect, 0, 1)));
            }
            const scatter = mix(
                float(0.008), float(1.0),
                float(1).sub(smoothstep(0.0, 0.96, mu)),
            );
            const beers = exp(stepL.mul(den).negate())
                .add(exp(stepL.mul(den).negate().mul(0.1)).mul(scatter).mul(0.5))
                .add(exp(stepL.mul(den).negate().mul(0.02)).mul(scatter).mul(0.4));
            const powdered = float(0.05).add(pow(min(dC.mul(8.5), 1).max(1e-6), float(0.3).add(ch.mul(5.5))).mul(1.5));
            const lit = mix(powdered, float(1), clamp(den.mul(0.4), 0, 1));
            return beers.mul(phaseF).mul(mix(float(1), lit, u.lightK));
        };
        // SCREEN-RAY direction: from camera matrices + screen UV, NOT from
        // interpolated mesh position. Along shared dome-triangle edges, MSAA
        // shades the pixel from both triangles at slightly different
        // interpolation positions; the nonlinear march amplifies that into
        // faint parallel seam lines along the whole 7.5-degree triangle
        // grid. Uniform-matrix math is bit-identical per pixel -> seams
        // impossible by construction.
        const screenRayDir = () => {
            // The previous offscreen workaround fell back to an interpolated
            // sphere position in optimized modes. That made the ray differ
            // across dome triangles, and dense Ringworld/Dark Storm clouds
            // exposed the triangle grid as intermittent line grain. Three's
            // WebGPU getViewPosition already applies the framebuffer-origin
            // conversion for both canvas and render targets; a second manual
            // target flip points the upper half of the pass below the horizon.
            // Reconstruct the same orientation-true ray per pixel everywhere.
            if (T3.getViewPosition && T3.screenUV) {
                const vp = T3.getViewPosition(T3.screenUV, float(0.5), u.projInv);
                return normalize(u.camWorld.mul(vec4(normalize(vp), 0)).xyz);
            }
            return normalize(positionWorld.sub(cameraPosition));
        };

        // far-root shell intersection, numerically STABLE at planet scale.
        // The textbook (−b+√D)/2 cancels catastrophically in fp32: b² sits at
        // ~1.6e14 where one ulp ≈ 1.7e7, quantizing t into ~12 m stair-bands —
        // iso-distance arcs that render as SEAMS in thin cloud layers. Same for
        // |oc|²−rad² (two ~4e13 operands). Fixes: c expanded so small quantities
        // stay small (s = shell height above ground, NOT planet radius), and
        // t₊ = −2c/(b+√D) instead of the cancelling numerator.
        const shellFar = (org, dir, s) => {
            const ocy = org.y.add(R_EARTH);
            const b = dot(dir, vec3(org.x, ocy, org.z)).mul(2);
            const c = org.x.mul(org.x).add(org.z.mul(org.z))
                .add(org.y.sub(s).mul(org.y.add(s).add(2 * R_EARTH)));
            const D = max(b.mul(b).sub(c.mul(4)), 0);
            return c.mul(-2).div(b.add(sqrt(D)));
        };
        // altitude above ground without |p−earthC|−R cancellation (0.5 m ulp
        // steps → horizontal micro-bands in the density height profile).
        // opts.ringCurve (= ring radius): RINGWORLD mode — the atmosphere is
        // RING-NATIVE: cloud "altitude" = radial distance INWARD from the
        // band's surface, h = R − dist(p, ring axis). The deck hugs the
        // ring's interior all the way around BY CONSTRUCTION — no rise hack,
        // no follow clamp. (Every flat-ground correction we stacked — capped
        // parabola, true-circle rise, tangent extension — still read as "an
        // earth sky bolted over a ring" the moment an exterior lookdev
        // camera saw the shape from outside.) Near the bottom this equals
        // the old y-height, so the ground-level look is unchanged; the
        // march window (sTop shell) bounds how far up the arc the volumetric
        // lining renders, and the band's 2D sheet carries the rest.
        const RING_R = opts.ringCurve ?? 0;
        const RING_RISE_MAX = RING_R ? RING_R * 0.60 : 0;   // march-ceiling allowance up the arc
        const RING_BASE = opts.ringCloudBase ?? 450;        // deck base over the local scene (m)
        const RING_THICK = opts.ringCloudThick ?? 280;      // deck thickness (m)
        // THE PROFILE IS A ROUNDED-CORNER CHORD (a square with beveled
        // edges): dead-flat across the local scene, then a TRUE CIRCULAR
        // ARC lifting the far deck, then a clean density fade-out.
        // BAND-MATCHING IS DELIBERATELY ABSENT: the ring band renders at
        // renderOrder −99 with no depth write and the cloud dome composites
        // over it at −98, so clouds ALWAYS draw in front of the halo — any
        // geometric "hug/kiss the band" is unobservable by construction.
        // The profile is a pure LOOK: flat local ceiling + a far upward
        // sweep.
        // The arc is a circular fillet (a smoothstep ramp is near-linear
        // mid-window — it read as "a flat plane that angled"): radius from
        // window W and rise D in closed form, r = (W² + D²) / 2D. The arc
        // top's slope is W/(r−D) — keep it ≤ ~1.7 (W ≳ 1.7·D) or cloud
        // forms smear along the climb.
        // HARDCODED — recovered wide profile (tuned at R=5000, expressed
        // R-relative so the shape scales with the ring): flat 4200, crest
        // 4900, rise 350, end 4975. Both sides use abs(z), so the 8.4 km
        // middle is centered and the circular turns begin at ±4.2 km.
        // Deliberately NOT config/opts: this is the ringworld sky's
        // authored shape, not a user knob.
        const RING_ZFLAT  = RING_R * 0.84;   // flat chord half-span (m)
        const RING_ZCREST = RING_R * 0.98;   // arc crest z — the climb ends here
        const RING_RISE   = RING_R * 0.07;   // crest height above the base (m)
        const RING_ZEND   = RING_R * 0.995;  // density fade-out completes (m)
        const RING_ARC_W  = Math.max(RING_ZCREST - RING_ZFLAT, 1);
        const RING_ARC_RAD = (RING_ARC_W * RING_ARC_W + RING_RISE * RING_RISE) / (2 * Math.max(RING_RISE, 1));
        // Density must finish on the actual crest, even though the recovered
        // profile keeps a farther terminal domain bound. Otherwise the clamped
        // deck creates a faint flat shelf after the circular turn. Keep most
        // of the authored rise fully visible, feathering only its final 20%.
        const RING_VISIBLE_END = Math.min(RING_ZEND, RING_ZCREST);
        const RING_END_FADE = Math.max(RING_ARC_W * 0.20, 1);
        // JS mirror of the profile (slab precompute + external probes)
        const _deckY = (z) => {
            const uz = Math.min(Math.max(Math.abs(z) - RING_ZFLAT, 0), RING_ARC_W * 0.999);
            return RING_BASE + RING_ARC_RAD - Math.sqrt(Math.max(RING_ARC_RAD * RING_ARC_RAD - uz * uz, 1));
        };
        // the whole deck lives in a thin horizontal SLAB the march clips
        // to — without the clip the samples stretch over ~10 km for a
        // ~300 m layer and the deck dissolves into slicing noise
        let RING_SLAB_LO = 0, RING_SLAB_HI = 0;
        if (RING_R) {
            RING_SLAB_LO = RING_BASE - 20;
            RING_SLAB_HI = RING_BASE + RING_THICK + 20;
            for (let z = 0; z <= Math.min(RING_ZEND, RING_R); z += 25) {
                // draped layer: vertical extent = thick·√(1+slope²)
                const sl = (_deckY(z + 50) - _deckY(z - 50)) / 100;
                RING_SLAB_HI = Math.max(RING_SLAB_HI, _deckY(z) + RING_THICK * Math.sqrt(1 + sl * sl) + 20);
            }
        }
        // TSL mirror of the deck profile — used by atmoHeight AND by the
        // density functions' slope-aware weather decorrelation below
        const ringDeckY = (zq) => {
            const uz = clamp(zq.abs().sub(float(RING_ZFLAT)), float(0), float(RING_ARC_W * 0.999));
            return float(RING_BASE + RING_ARC_RAD)
                .sub(sqrt(max(float(RING_ARC_RAD * RING_ARC_RAD).sub(uz.mul(uz)), float(1))));
        };
        const ringSlopeAt = (pIn) => RING_R
            ? ringDeckY(pIn.z.add(60)).sub(ringDeckY(pIn.z.sub(60))).div(120)
            : float(0);
        const atmoHeight = (pIn) => {
            const base = pIn.y.mul(pIn.y.add(2 * R_EARTH)).add(pIn.x.mul(pIn.x)).add(pIn.z.mul(pIn.z))
                .div(length(vec3(pIn.x, pIn.y.add(R_EARTH), pIn.z)).add(R_EARTH));
            if (!RING_R) return base;
            const bigY = ringDeckY(pIn.z);
            // DRAPE the layer on the slope: layer height is measured NORMAL
            // to the envelope, not vertically — with vertical h, every
            // coverage cell on the arc's climb becomes a tall leaning
            // wafer (the streak-column artifact); normal h lays cells along
            // the slope like orographic cloth. Slope by finite difference
            // (the profile is pure arithmetic, no texture taps).
            const slope = ringSlopeAt(pIn);
            const cosT = float(1).div(sqrt(slope.mul(slope).add(1)));
            return u.cloudStart.add(pIn.y.sub(bigY).mul(cosT).mul(u.cloudHeight).div(float(RING_THICK)));
        };
        // RINGWORLD cloud containment: clouds live in the band's atmosphere —
        // but the air BULGES above the edge walls (real containment spills),
        // so the strip is wider than the walls with a soft shoulder, and the
        // local volumetric deck FADES OUT with distance along the ring: a
        // hard-edged narrow corridor converges by perspective into a wedge
        // ("triangular cloud" artifact); beyond a few km the far side's cloud
        // sheet carries the fiction instead. Scattering still fills the dome.
        // Local cloud air deliberately extends far through the Ringworld's
        // open sides across the complete flat run. Only the rising ends taper
        // inward, so their curvature does not read as an outward flare.
        // Even the tapered end remains much wider than the physical band.
        const uLocalHalf = uniform(opts.ringLocalHalf ?? 4000);
        const uBandHalf = uniform(opts.ringBandHalf ?? 483);
        const uWispCurveHalf = uniform(
            opts.ringWispCurveHalf ?? (opts.ringLocalHalf ?? 4000) * 0.5,
        );
        // PROPORTIONAL soft shoulder: a hard cut folds perspective into the
        // wedge artifact. Width-only masks are valid at ANY distance (the
        // ring curves in Y-Z, so x is the width axis globally).
        const ringWidth = (pIn) => RING_R
            ? float(1).sub(smoothstep(
                uLocalHalf.mul(0.66), uLocalHalf.mul(1.3), pIn.x.abs(),
            ))
            : float(1);
        const ringStrip = (pIn) => {
            if (!RING_R) return float(1);
            // WIDTH is an authored bound in ALL weather states — never
            // weather-widened. (A grey-driven flood toward a 26 km full-sky
            // ceiling reads as infinite outward clouds over the empty
            // horizon perpendicular to the ring.)
            const wMask = float(1).sub(smoothstep(
                uLocalHalf.mul(0.66), uLocalHalf.mul(1.3), pIn.x.abs(),
            ));
            // along-ring terminal fade — the deck just ENDS cleanly (clouds
            // composite in front of the ring regardless, so no band contact
            // is needed). Density dies across the final fifth of the curve,
            // leaving most of the authored rise visible, and
            // the end NEVER exceeds the arc crest — past the crest the
            // profile holds crest height, so any density there reads as an
            // extra flat shelf hanging off the curve's tip. Weather never
            // overrides this bound either.
            return wMask.mul(float(1).sub(smoothstep(
                float(RING_VISIBLE_END - RING_END_FADE),
                float(RING_VISIBLE_END),
                pIn.z.abs(),
            )));
        };

        // Lowest visible Dark Thunderstorm layers. This field is genuinely 3D:
        // a broad warp feeds macro, billow, and fine cells, while independent
        // vertical windows form a guaranteed deep core and lower hanging scud.
        // The nonzero extinction floor seals the sky through optical depth;
        // there is deliberately no opaque plane/backstop in the compositor.
        const stormLayerBottom = () => u.cloudStart.sub(280);
        const stormLayerDepth = () => clamp(u.cloudHeight.mul(2.85), 1100, 1450);
        const stormContainAt = (pIn) => {
            if (!RING_R) return float(1);
            const progress = smoothstep(
                float(RING_ZFLAT), float(RING_VISIBLE_END), pIn.z.abs(),
            );
            const halfWidth = mix(uLocalHalf, uWispCurveHalf, progress);
            const width = float(1).sub(smoothstep(
                halfWidth.mul(0.72), halfWidth.mul(1.22), pIn.x.abs(),
            ));
            const end = float(1).sub(smoothstep(
                float(RING_VISIBLE_END - RING_END_FADE),
                float(RING_VISIBLE_END),
                pIn.z.abs(),
            ));
            return width.mul(end);
        };
        const stormFieldAt = (
            pIn, mediumDetail = float(1), fineDetail = float(1),
        ) => {
            const bottom = stormLayerBottom();
            const depth = stormLayerDepth();
            const layerBase = RING_R
                ? ringDeckY(pIn.z).sub(RING_BASE).add(bottom)
                : bottom;
            const altitude = (RING_R ? pIn.y : atmoHeight(pIn)).sub(layerBase);
            const h = clamp(altitude.div(depth), 0, 1);
            const envelope = smoothstep(0.0, 0.045, h).mul(
                float(1).sub(smoothstep(0.94, 1.0, h)),
            );

            const drift = pIn.add(vec3(
                u.skyWind.x.mul(u.time).mul(0.62),
                u.time.mul(1.15),
                u.skyWind.z.mul(u.time).mul(0.62),
            ));
            const warp = noise3A(
                applyM(drift.mul(0.00031)).add(vec3(1.7, -3.1, 4.6)),
            );
            const warpCentered = warp.sub(0.5);
            const warped = drift.add(vec3(
                warpCentered.mul(380),
                warpCentered.mul(-180),
                warpCentered.mul(280),
            ));
            const macro = noise3A(
                applyM(warped.mul(0.00062)).add(vec3(3.7, -1.9, 5.1)),
            );
            // Kilometres-scale variation. The macro octave repeats its ~1.6 km
            // feature scale uniformly across an 18 km grazing path, which read
            // as a tiled texture. This incommensurate ~5 km field varies the
            // underside silhouette and mass density regionally. It never
            // reduces the floor extinction, so the seal guarantee is intact.
            const giant = noise3A(
                applyM(drift.mul(0.000117)).add(vec3(-2.9, 6.3, -7.7)),
            );
            const rawBillow = noise3A(
                applyM(warped.mul(0.00185)).add(vec3(-6.2, 2.7, 1.4)),
            );
            const rawDetail = noise3A(
                applyM(warped.mul(0.0054)).add(vec3(8.4, -4.3, -2.6)),
            );
            // Medium and fine octaves converge independently when their feature
            // size falls below the grazing-ray step. Macro form remains fully
            // spatial instead of fading the whole storm to a flat 0.5 card.
            const billow = mix(
                float(0.5), rawBillow, clamp(mediumDetail, 0, 1),
            );
            const detail = mix(float(0.5), rawDetail, clamp(fineDetail, 0, 1));

            const ruffledH = h
                .add(macro.sub(0.5).mul(0.38))
                .add(giant.sub(0.5).mul(0.20))
                .add(billow.sub(0.5).mul(0.16));
            const organicCore = smoothstep(0.13, 0.56, ruffledH);
            const guaranteedCore = smoothstep(0.30, 0.58, h).mul(
                float(1).sub(smoothstep(0.92, 0.985, h)),
            );
            const core = max(organicCore.mul(0.92), guaranteedCore);

            const lowerWindow = smoothstep(0.01, 0.065, h).mul(
                float(1).sub(smoothstep(0.30, 0.52, h)),
            );
            const middleWindow = smoothstep(0.10, 0.20, h).mul(
                float(1).sub(smoothstep(0.50, 0.72, h)),
            );
            const scudField = macro.mul(0.28)
                .add(billow.mul(0.44))
                .add(detail.mul(0.28));
            const lowerScud = smoothstep(
                0.48, 0.70,
                scudField.add(float(0.22).sub(h).mul(0.28)),
            ).mul(lowerWindow);
            const middleScud = smoothstep(
                0.56, 0.78,
                macro.mul(0.40).add(detail.mul(0.60))
                    .add(float(0.42).sub(h).mul(0.16)),
            ).mul(middleWindow);
            const scud = max(lowerScud, middleScud.mul(0.74));

            // Keep the lower air open enough to see separated scud in front of
            // the core. Macro/billow displacement ruffles even the guaranteed
            // deep mass boundary; its worst-case delayed column still exceeds
            // seven optical depths before organic core density is added.
            const deepCoreH = h
                .add(macro.sub(0.5).mul(0.14))
                .add(billow.sub(0.5).mul(0.04));
            const floorExtinction = mix(
                float(0.00035), float(0.0160), smoothstep(0.38, 0.55, deepCoreH),
            );
            const regionVar = float(0.85).add(giant.mul(0.30));
            const coreExtinction = core.mul(float(0.010).add(billow.mul(0.015))).mul(regionVar);
            const scudExtinction = scud.mul(float(0.015).add(detail.mul(0.018))).mul(regionVar);
            const extinction = envelope
                .mul(floorExtinction.add(coreExtinction).add(scudExtinction))
                .mul(stormContainAt(pIn));
            return {
                extinction,
                mass: clamp(extinction.div(0.028), 0, 1),
                h,
                macro,
                billow,
                detail,
                core,
                scud,
            };
        };
        // Per-material cloud shadows must stay tiny: this function is embedded
        // into every wrapped world PBR shader. Reusing stormFieldAt here would
        // multiply its four analytic noise fields across the entire scene and
        // can prevent world pipelines from becoming ready. The remaining
        // transition key only needs the same continuous sealed mass envelope;
        // settled Darkstorm has zero celestial key and skips this path entirely.
        const stormShadowExtinctionAt = (pIn) => {
            const bottom = stormLayerBottom();
            const depth = stormLayerDepth();
            const layerBase = RING_R
                ? ringDeckY(pIn.z).sub(RING_BASE).add(bottom)
                : bottom;
            const altitude = (RING_R ? pIn.y : atmoHeight(pIn)).sub(layerBase);
            const h = clamp(altitude.div(depth), 0, 1);
            const envelope = smoothstep(0.0, 0.045, h).mul(
                float(1).sub(smoothstep(0.94, 1.0, h)),
            );
            const extinction = mix(
                float(0.00035), float(0.0160), smoothstep(0.38, 0.55, h),
            );
            return envelope.mul(extinction).mul(stormContainAt(pIn));
        };

        // ---------------- optimized light/froxel cache ----------------
        // Store the full 20-tap light-ray density sum. Visible fragments then
        // retain the original Beer/powder/Mie evaluation but replace its
        // nested light march with one trilinear volume lookup.
        let lightCacheTex = null, lightCacheCompute = null;
        let lightCacheMin = null, lightCacheSpan = null, lightCacheInvSpan = null;
        let lightCacheDirty = !!lightCacheOpts;
        let lightCacheReady = false;
        let lightCacheLastT = -Infinity;
        const lightCacheOrigin = new T3.Vector3(Infinity, Infinity, Infinity);
        const lightCacheSun = new T3.Vector3(Infinity, Infinity, Infinity);
        let lightCacheDims = null;
        if (lightCacheOpts) {
            const requested = lightCacheOpts.size ?? [128, 32, 128];
            const round4 = (n) => Math.max(4, Math.ceil(n / 4) * 4);
            const LX = round4(requested[0]), LY = round4(requested[1]), LZ = round4(requested[2]);
            lightCacheDims = [LX, LY, LZ];
            lightCacheTex = new T3.Storage3DTexture(LX, LY, LZ);
            // rgba16float is a universally valid filterable WebGPU storage
            // format; only .r carries the optical-density sum.
            lightCacheTex.format = T3.RGBAFormat;
            lightCacheTex.type = T3.HalfFloatType;
            lightCacheTex.minFilter = lightCacheTex.magFilter = T3.LinearFilter;
            lightCacheTex.wrapS = lightCacheTex.wrapT = lightCacheTex.wrapR = T3.ClampToEdgeWrapping;
            lightCacheTex.generateMipmaps = false;
            lightCacheTex.colorSpace = T3.NoColorSpace;
            lightCacheTex.name = `eanpa_light_froxel_${LX}x${LY}x${LZ}`;

            lightCacheMin = uniform(V(0, 0, 0));
            lightCacheSpan = uniform(V(1, 1, 1));
            lightCacheInvSpan = uniform(V(1, 1, 1));
            const lightVolumeNode = T3.texture3D(lightCacheTex);
            sampleLightCache = (p) => {
                // A Cartesian Y lattice wastes most of its slices below/above
                // the Ringworld deck as that deck climbs the curved profile.
                // Address Y by the deck-local normalized cloud height instead:
                // every z column then spends its full LY resolution on cloud,
                // eliminating the coarse horizontal lighting bands that were
                // enlarged by Balanced's half-resolution compositor.
                const uvw = RING_R
                    ? vec3(
                        p.x.sub(lightCacheMin.x).mul(lightCacheInvSpan.x),
                        atmoHeight(p).sub(u.cloudStart).div(max(u.cloudHeight, 1)),
                        p.z.sub(lightCacheMin.z).mul(lightCacheInvSpan.z),
                    ).clamp(0, 1)
                    : clamp(p.sub(lightCacheMin).mul(lightCacheInvSpan), 0, 1);
                return lightVolumeNode.sample(uvw).level(0).r;
            };

            const fillLightCache = Fn(() => {
                const gid = T3.globalId;
                const uvw = vec3(gid).add(0.5).div(vec3(LX, LY, LZ));
                const flatP = lightCacheMin.add(uvw.mul(lightCacheSpan));
                // In Ringworld mode reconstruct the physical Y position from
                // the same curved deck profile used by visible density. This
                // makes cache fill and lookup exact inverses in cloud-height
                // space instead of sampling an unrelated horizontal box.
                const ringSlope = ringSlopeAt(flatP);
                const ringCos = float(1).div(sqrt(ringSlope.mul(ringSlope).add(1)));
                const p = RING_R
                    ? vec3(
                        flatP.x,
                        ringDeckY(flatP.z).add(uvw.y.mul(RING_THICK).div(ringCos)),
                        flatP.z,
                    )
                    : flatP;
                const stepL = clamp(u.cloudHeight.mul(2.2), 380, 700).div(N_LIGHT);
                const den = float(0).toVar();
                for (let j = 0; j < N_LIGHT; j++) {
                    den.addAssign(cheapDensity(p.add(u.cloudLightDir.mul(stepL).mul(j + 0.5))));
                }
                T3.textureStore(lightCacheTex, gid, vec4(den, 0, 0, 1)).toWriteOnly();
            });
            lightCacheCompute = fillLightCache().compute([LX / 4, LY / 4, LZ / 4], [4, 4, 4]);
        }

        // ---------------- CLOUD DOME material ----------------
        // body parameterized on (dir, org) so the env bake below can evaluate
        // the SAME sky from equirect directions (dome pass uses screen rays)
        // CLOUDDBG=1: lookdev build that strips every under-the-deck camera
        // assumption — no upward-ray gate, march from the camera over the
        // full range, no distance/horizon fades. Coarse (N_MARCH over the
        // whole fadeDist) but it SHOWS THE SHAPE from any vantage, which is
        // the entire point of a debug view — never cull the subject of a
        // debug. Proper any-vantage rendering is future work.
        const CLOUD_DBG = globalThis.Deno?.env?.get?.('CLOUDDBG') === '1';
        const cloudBody = (
            dirIn, orgIn, passesIn, jitterOverride = null,
            transientLightScale = float(1),
        ) => {
            const dir = dirIn;
            const org = orgIn;
            // ring mode: the deck rises up to RING_RISE_MAX above the spherical
            // shell — widen the march ceiling so risen clouds aren't cut
            const sTop = u.cloudStart.add(u.cloudHeight).add(RING_R ? RING_RISE_MAX : 0);
            // RING MODE MARCH WINDOW: the deck is an annular tube around the
            // ring axis — a spherical-shell ceiling would cut every ray at a
            // flat altitude and the deck's risen far ends would never render.
            // March from the camera to the ray's exit from the ring cylinder
            // (we're inside → far root), fadeDist-clamped.
            let t0, t1;
            if (RING_R) {
                const oy = org.y, oz = org.z;   // ring axis at y≈0 (sensor-measured vs the real mesh)
                const aQ = dir.y.mul(dir.y).add(dir.z.mul(dir.z)).add(1e-6);
                const bQ = dir.y.mul(oy).add(dir.z.mul(oz));
                const cQ = oy.mul(oy).add(oz.mul(oz)).sub(RING_R * RING_R * 0.99);
                const tFar = bQ.negate().add(sqrt(max(bQ.mul(bQ).sub(aQ.mul(cQ)), float(0)))).div(aQ);
                // clip the march to the deck's SLAB — without it, 64 steps
                // stretch over ~10 km for a ~300 m layer and the sunlit deck
                // dithers into checkerboard noise
                const dyMag = max(abs(dir.y), float(1e-4));
                const dyS = dir.y.div(max(abs(dir.y), float(1e-6)));
                const dySafe = dyS.mul(dyMag);
                const tA = float(RING_SLAB_LO).sub(org.y).div(dySafe);
                const tB = float(RING_SLAB_HI).sub(org.y).div(dySafe);
                t0 = max(min(tA, tB), float(0));
                t1 = min(min(max(tA, tB), tFar), u.fadeDist);
            } else {
                t0 = CLOUD_DBG ? float(0) : shellFar(org, dir, u.cloudStart);
                // clamp the march to the pre-fade range: near the horizon the full
                // shell chord is 30-80 km but everything past fadeDist is faded out
                // anyway — clamping concentrates the samples where edges resolve
                t1 = CLOUD_DBG ? u.fadeDist : min(shellFar(org, dir, sTop), u.fadeDist.mul(1.1));
            }
            const stepS = max(t1.sub(t0), 0).div(N_MARCH);
            const mu = dot(u.cloudLightDir, dir);
            const phaseF = phaseMie(mu);
            // The current-frame optimized pass has no temporal history, so its
            // production phase is centered and deterministic. Direction hash,
            // screen hash, and blue noise remain only for non-stable lookdev
            // A/Bs; frameJit stays zero in the spatial production pass.
            // STRATIFIED MULTI-PASS MARCH: M offsets at fract(jit + k/M)
            // interleave the samples within the current frame. Stable mode
            // integrates the same centered M sub-steps every frame; a non-
            // stable lookdev phase may still offset that complete stratum set.
            const M_PASS = Math.max(1, passesIn ?? opts.cloudPasses ?? 8);
            // The optimized compositor has no history/reprojection. A tiled
            // screen phase therefore follows pixels, not world features: when
            // a curved Ringworld or dense storm edge moves across a half-res
            // pixel it acquires a different phase and becomes crawling grain.
            // Centered deterministic strata integrate the same M sub-steps in
            // every current frame. Full-resolution/direct lookdev can still
            // opt into the blue-noise or bounded-hash phase for spatial A/Bs.
            const stablePhase = opts.stableCloudPhase ?? opts.worldRayDir;
            const baseJit = jitterOverride ?? (stablePhase
                ? float(0.5 / M_PASS)
                : (opts.blueNoise
                    ? fract(T3.texture(opts.blueNoise, screenCoordinate.xy.div(64)).level(0).r.add(u.frameJit))
                    : (opts.dirJitter
                        ? hash11(dot(dir, vec3(12.256, 2.646, 6.356)))
                        : hashScreen(screenCoordinate.xy))));
            const colSum = vec3(0).toVar();
            const trSum = float(0).toVar();
            const marchVisible = CLOUD_DBG
                ? float(1).greaterThan(0)
                : dir.y.greaterThan(0.008).and(t0.lessThan(u.fadeDist));
            // Wisp-only Cirrus keeps finalMul at zero. Gate before cloudsAt()
            // so its two FBMs and the complete volumetric march do no work;
            // weather transitions can turn the branch back on dynamically.
            If(marchVisible.and(u.finalMul.greaterThan(0.0001)), () => {
                for (let k = 0; k < M_PASS; k++) {
                    const Trk = float(1).toVar();
                    const colk = vec3(0).toVar();
                    const jitK = fract(baseJit.add(k / M_PASS));
                    const p = org.add(dir.mul(t0)).add(dir.mul(stepS).mul(jitK)).toVar();
                    Loop({ start: 0, end: N_MARCH, type: 'int' }, () => {
                        If(Trk.lessThanEqual(0.008), () => Break());
                        const s = cloudsAt(p);
                        If(s.density.greaterThan(0.0), () => {
                            const intensity = lightRay(p, phaseF, s.density, mu, s.ch, fract(fract(baseJit.mul(73.1063)).add(k * 0.6180339887)));
                            const amb = u.cloudAmbSky.mul(float(0.5).add(s.ch.mul(0.6)))
                                .add(u.cloudAmbGround.mul(max(float(1).sub(s.ch.mul(2)), 0)));
                            // A sealed cumulonimbus canopy removes direct sun
                            // from everything beneath it. The underlayer keeps
                            // its shape readable via a dim top-weighted canopy
                            // skylight instead of noon sunlight punching
                            // through "holes" in a storm that blots out the sun.
                            const celestialK = clamp(u.celestialVisibility, 0, 1);
                            const canopyGate = smoothstep(0.6, 0.98, u.stormCanopy)
                                .mul(float(1).sub(celestialK));
                            // Near-neutral charcoal, NOT skylight blue: under a
                            // sealed storm the only illumination is multiple
                            // scattering off dark water-laden cloud, and the
                            // sky must sit as dark as the near-night scene
                            // lighting below it.
                            const canopySkylight = vec3(0.028, 0.029, 0.032)
                                .mul(float(0.30).add(s.ch.mul(0.70)))
                                .mul(canopyGate);
                            // The daytime blue zenith ambient also has no path
                            // through the canopy — collapse it toward its own
                            // darkened grey luminance as the storm seals.
                            const ambGrey = mix(
                                amb,
                                vec3(dot(amb, vec3(0.34, 0.45, 0.21))).mul(0.42),
                                canopyGate,
                            );
                            const radiance = ambGrey.add(u.cloudLightColor.mul(intensity).mul(celestialK))
                                .mul(u.cloudRadiance).add(canopySkylight).mul(s.density);
                            const trStep = exp(s.density.mul(stepS).negate());
                            colk.addAssign(Trk.mul(radiance.sub(radiance.mul(trStep)).div(max(s.density, 1e-6))));
                            Trk.assign(Trk.mul(trStep));
                        });
                        p.assign(p.add(dir.mul(stepS)));
                    });
                    colSum.addAssign(colk);
                    trSum.addAssign(Trk);
                }
            }).Else(() => {
                trSum.assign(M_PASS);
            });
            const col = colSum.div(M_PASS).toVar();
            const Tr = trSum.div(M_PASS);
            const wispA = float(0).toVar();
            // Severe sealed weathers (Cyclone, Dark Storm) run this shared
            // high-cloud graph as their textured canopy sheet — the coherent
            // cloud ceiling seen between the low volumetric masses. The gate
            // still skips all of its work whenever wispOn is zero.
            If(u.wispOn.greaterThan(0.0001), () => {
            // High clouds share the live cloud material and weather uniforms.
            // Earth/Shieldworld intersect the preset's upper spherical shell.
            // Ringworld keeps that SAME semantic altitude and SAME cloud field,
            // adding only the authored deck displacement at the curved ends.
            // The former fixed 1550 m surface compressed Cirrus from 4630 m and
            // clipped most of the shared upper layer out of the visible sky.
            const ringWispFlatY = u.cloudStart.add(u.cloudHeight).add(1000);
            const ringWispYAt = (zq) => ringDeckY(zq).sub(RING_BASE).add(ringWispFlatY);
            const ringWispDy = max(dir.y, 0.008);
            // The ray's flat-height hit and maximum-rise hit bracket every
            // possible intersection with this bounded circular profile.
            // Bisection stays stable at the near-tangent curved ends where the
            // former two fixed-point guesses could float tens of metres off
            // the authored surface or fabricate a shelf hit.
            const ringWispTLo = ringWispFlatY.sub(org.y).div(ringWispDy).toVar();
            const ringWispTHi = ringWispFlatY.add(RING_RISE).sub(org.y).div(ringWispDy).toVar();
            for (let solveStep = 0; solveStep < 8; solveStep++) {
                const ringWispTMid = ringWispTLo.add(ringWispTHi).mul(0.5);
                const ringWispPMid = org.add(dir.mul(ringWispTMid));
                If(org.y.add(ringWispDy.mul(ringWispTMid)).lessThan(ringWispYAt(ringWispPMid.z)), () => {
                    ringWispTLo.assign(ringWispTMid);
                }).Else(() => {
                    ringWispTHi.assign(ringWispTMid);
                });
            }
            const ringWispT = ringWispTLo.add(ringWispTHi).mul(0.5);
            const wispHitT = RING_R ? ringWispT : shellFar(org, dir, sTop.add(1000));
            const pC = org.add(dir.mul(wispHitT));
            // Preserve the full open-side footprint across the complete flat
            // middle, then contract only after the authored curve begins.
            const ringWispProgress = smoothstep(
                float(RING_ZFLAT), float(RING_VISIBLE_END), pC.z.abs(),
            );
            const ringWispHalf = mix(uLocalHalf, uWispCurveHalf, ringWispProgress);
            const ringWispWidthMask = float(1).sub(smoothstep(
                ringWispHalf.mul(0.72), ringWispHalf.mul(1.22), pC.x.abs(),
            ));
            const ringWispEndMask = float(1).sub(smoothstep(
                float(RING_VISIBLE_END - RING_END_FADE),
                float(RING_VISIBLE_END),
                pC.z.abs(),
            ));
            const wispW = RING_R ? ringWispWidthMask.mul(ringWispEndMask) : float(1);
            // The old sheet inherited the low deck's t0 fade. At shallow view
            // angles t0 can still be near while this higher shell hit is tens
            // of kilometres farther away, collapsing kilometres of texture
            // into stretched horizon copies. Fade from the sheet's own range.
            const wispRange = float(1).sub(smoothstep(
                u.fadeDist.mul(0.55), u.fadeDist.mul(1.25), wispHitT,
            ));
            // Restore the authored, domain-warped high-cloud field instead of
            // thresholding four coarse 2D map reads into distant slabs. The
            // optimized tiers reuse the existing filtered 3D density basis via
            // fbmE, retaining the organic field without the former ALU lattice
            // cost. Advect the complete domain at the same world velocity as
            // the volume below so both sheet masses and cirrus cells visibly
            // move rather than only changing their internal noise.
            const wispAdvected = pC.add(vec3(
                u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time),
            ));
            const wispPatch = fbmE(wispAdvected.mul(0.00016).add(vec3(4.7, 1.3, -2.1)));
            const wispWarp = fbmE(wispAdvected.mul(0.00031).add(vec3(-1.7, 3.1, 5.3))).sub(0.44);
            const wispBend = fbmE(wispAdvected.mul(0.00009).add(vec3(8.2, -1.4, 2.7))).sub(0.44);
            const wispP = wispAdvected.mul(u.wispStretch).mul(u.wispScale)
                .add(vec3(
                    wispWarp.mul(1.8).add(wispBend.mul(1.4)),
                    wispWarp.mul(0.35),
                    wispWarp.mul(-1.2).add(wispBend.mul(0.7)),
                ));
            const wispN = fbmE(wispP);
            const authoredSheet = smoothstep(u.wispThreshold, u.wispThreshold.add(0.24), wispN)
                .mul(smoothstep(0.30, 0.62, wispPatch));
            const sheet = authoredSheet;
            // Finite mares'-tail plumes. Every safely inset cell may carry one
            // independently centered, rotated, sized and curved ice plume;
            // many cells are empty. Because the envelope is zero well before
            // cell borders, random per-cell parameters never form seams. This
            // keeps recognizable feathered cirrus without either the old
            // evenly spaced dashes or a horizon-wide anisotropic stripe field.
            const cirrusCellP = wispAdvected.xz.mul(0.00013);
            const cirrusId = floor(cirrusCellP);
            const cirrusLocal = fract(cirrusCellP).sub(vec2(0.5));
            const cirrusAngleR = hash3(vec3(cirrusId.x, cirrusId.y, 1.7));
            const cirrusShapeR = hash3(vec3(cirrusId.x, cirrusId.y, 5.9));
            const cirrusWidthR = hash3(vec3(cirrusId.x, cirrusId.y, 9.2));
            const cirrusPresenceR = hash3(vec3(cirrusId.x, cirrusId.y, 13.6));
            const cirrusCenterX = hash3(vec3(cirrusId.x, cirrusId.y, 17.3)).sub(0.5).mul(0.13);
            const cirrusCenterY = hash3(vec3(cirrusId.x, cirrusId.y, 21.8)).sub(0.5).mul(0.13);
            const cirrusX = cirrusLocal.x.sub(cirrusCenterX);
            const cirrusY = cirrusLocal.y.sub(cirrusCenterY);
            // A normalized hash vector avoids two transcendental trig calls
            // per pixel while preserving fully varied plume orientation.
            const cirrusDirX = cirrusAngleR.sub(0.5);
            const cirrusDirY = cirrusShapeR.sub(0.5);
            const cirrusDirInv = float(1).div(max(length(vec2(cirrusDirX, cirrusDirY)), 0.08));
            const cirrusCos = cirrusDirX.mul(cirrusDirInv);
            const cirrusSin = cirrusDirY.mul(cirrusDirInv);
            const cirrusAlong = cirrusX.mul(cirrusCos).add(cirrusY.mul(cirrusSin));
            const cirrusAcross0 = cirrusY.mul(cirrusCos).sub(cirrusX.mul(cirrusSin));
            const cirrusLength = cirrusShapeR.mul(0.13).add(0.28);
            const cirrusWidth = cirrusWidthR.mul(0.046).add(0.048);
            const cirrusU = cirrusAlong.div(cirrusLength);
            const cirrusBend = cirrusU.mul(cirrusAngleR.sub(0.5)).mul(cirrusWidth.mul(0.42))
                .add(cirrusU.mul(cirrusU).mul(cirrusShapeR.sub(0.5)).mul(cirrusWidth.mul(1.55)));
            const cirrusAcross = cirrusAcross0.sub(cirrusBend);
            const cirrusTaper = float(1).sub(smoothstep(0.52, 1.0, abs(cirrusU)));
            const cirrusCoreW = cirrusWidth.mul(cirrusTaper.mul(0.72).add(0.20)).mul(0.34);
            const cirrusCore = float(1).sub(smoothstep(cirrusCoreW.mul(0.16), cirrusCoreW, abs(cirrusAcross)));
            const cirrusBranchGate = smoothstep(-0.18, 0.72, cirrusU).mul(cirrusTaper);
            const cirrusSep = cirrusWidth.mul(smoothstep(-0.4, 0.85, cirrusU).mul(1.05).add(0.42));
            const cirrusUpperD = cirrusAcross.sub(cirrusSep);
            const cirrusLowerD = cirrusAcross.add(cirrusSep.mul(0.78));
            const cirrusUpper = float(1).sub(smoothstep(cirrusCoreW.mul(0.10), cirrusCoreW.mul(0.82), abs(cirrusUpperD)))
                .mul(0.52).mul(cirrusBranchGate);
            const cirrusLower = float(1).sub(smoothstep(cirrusCoreW.mul(0.08), cirrusCoreW.mul(0.72), abs(cirrusLowerD)))
                .mul(0.36).mul(cirrusBranchGate);
            const cirrusPlumeW = cirrusWidth.mul(2.85);
            const cirrusPlume = float(1).sub(smoothstep(cirrusWidth.mul(0.55), cirrusPlumeW, abs(cirrusAcross)))
                .mul(wispN.mul(0.08).add(0.12)).mul(cirrusTaper);
            // Reuse the already evaluated warped wisp noise for feather
            // breakup; a dedicated three-octave FBM here cost ~15 fps.
            const cirrusBreakMask = smoothstep(0.36, 0.70, wispN).mul(0.72).add(0.28);
            const cirrusPresence = smoothstep(0.20, 0.48, cirrusPresenceR);
            const fibers = min(cirrusCore.add(cirrusUpper).add(cirrusLower).add(cirrusPlume), 0.96)
                .mul(cirrusTaper)
                .mul(cirrusBreakMask)
                .mul(cirrusPresence)
                .mul(smoothstep(0.08, 0.60, wispPatch).mul(0.32).add(0.68));
            // Do not execute the cirrus plume graph for ordinary cumulus,
            // stratus, Ringworld, or storm sheets. A narrow transition band
            // still crossfades both fields when weather morphs to/from High
            // Cirrus, so there is no hard visual swap. This restores the
            // optimized tiers' budget without removing either cloud element.
            const wispShape = float(0).toVar();
            If(u.wispFilament.lessThan(0.55), () => {
                wispShape.assign(sheet);
            }).Else(() => {
                If(u.wispFilament.greaterThan(0.85), () => {
                    wispShape.assign(fibers);
                }).Else(() => {
                    wispShape.assign(mix(sheet, fibers, smoothstep(0.55, 0.85, u.wispFilament)));
                });
            });
            // Severe weather needs broad coverage, not a constant-opacity card.
            // Treat wispFloor as the strength of a second low-frequency organic
            // canopy so Dark Storm keeps holes, folds, and soft boundaries.
            const canopyField = smoothstep(
                0.18, 0.56,
                wispPatch.mul(0.72).add(wispBend.add(0.44).mul(0.28)),
            );
            // Keep broad severe-weather coverage while preserving internal
            // cloud structure.  Multiplying the low-frequency canopy by the
            // already-filtered authored noise prevents its dense interiors
            // from reading as one flat grey card overhead.
            const canopyDetail = smoothstep(0.20, 0.82, wispN).mul(0.45).add(0.55);
            const canopyShape = max(wispShape, canopyField.mul(u.wispFloor).mul(canopyDetail));
            const wispD = canopyShape.mul(u.wispOn).mul(u.wispStrength).mul(wispW);
            const wispAlpha = min(wispD.mul(u.wispOpacity), 0.88).mul(wispRange);
            wispA.assign(wispAlpha);
            // cloudBody speaks premultiplied RGBA: multiply the straight wisp
            // radiance by its actual coverage (the old density-vs-alpha split
            // made every thin sheet intrinsically dark grey).
            col.addAssign(Tr.mul(u.wispColor).mul(wispAlpha).mul(u.cloudRadiance));
            });

            // SEALED LOW CUMULONIMBUS VOLUME. The semantic storm can be roughly
            // 19.3 km tall, but only its lowest 1.1-1.45 km are rendered. Two
            // interleaved strata integrate foreground scud and the deeper core
            // through one continuous 3D field. Alpha comes only from Beer
            // transmittance: no constant-color ceiling or opaque backstop can
            // collapse the result into a projected sky texture.
            const stormA = float(0).toVar();
            const stormRgb = vec3(0).toVar();
            If(u.stormCanopy.greaterThan(0.0001).and(dir.y.greaterThan(0.0005)), () => {
                const stormBaseY = stormLayerBottom();
                const stormDepth = stormLayerDepth();
                const stormTopY = stormBaseY.add(stormDepth);
                const stormDy = max(dir.y, 0.003);
                const stormRingTAt = (layerOffset) => {
                    const layerY = stormBaseY.add(layerOffset);
                    const layerRingYAt = (zq) => ringDeckY(zq).sub(RING_BASE).add(layerY);
                    const tLo = layerY.sub(org.y).div(stormDy).toVar();
                    const tHi = layerY.add(RING_RISE).sub(org.y).div(stormDy).toVar();
                    for (let solveStep = 0; solveStep < 6; solveStep++) {
                        const tMid = tLo.add(tHi).mul(0.5);
                        const pMid = org.add(dir.mul(tMid));
                        If(org.y.add(stormDy.mul(tMid)).lessThan(layerRingYAt(pMid.z)), () => {
                            tLo.assign(tMid);
                        }).Else(() => {
                            tHi.assign(tMid);
                        });
                    }
                    return tLo.add(tHi).mul(0.5);
                };
                const stormNearT = RING_R
                    ? stormRingTAt(float(0))
                    : shellFar(org, dir, stormBaseY);
                const stormFarT = RING_R
                    ? stormRingTAt(stormDepth)
                    : shellFar(org, dir, stormTopY);
                // At grazing angles the shell path can span many kilometres.
                // Keep the visible low-layer budget finite; its guaranteed
                // extinction floor still seals the column, while only the fine
                // octave is filtered at distance so broad form never flattens.
                const stormSegment = min(max(stormFarT.sub(stormNearT), 1), 18000);
                const stormStep = stormSegment.div(N_STORM_STEPS);
                const stormMediumRange = float(1).sub(
                    smoothstep(6500, 16000, stormNearT),
                );
                const stormFineRange = float(1).sub(
                    smoothstep(3000, 10500, stormNearT),
                );
                const stormTrSum = float(0).toVar();
                const stormVolumeSum = vec3(0).toVar();
                const boundedStormFlash = clamp(u.lightningStrike.w, 0, 1.15)
                    .mul(transientLightScale);
                for (let stormPass = 0; stormPass < N_STORM_PASSES; stormPass++) {
                    const stormTr = float(1).toVar();
                    const stormVolumeRgb = vec3(0).toVar();
                    // Centered strata phase, shared by every ray. A direction-
                    // hashed phase was tried against the shell-stripe banding:
                    // it swapped stripes for static per-pixel speckle whenever
                    // the camera stopped. Banding is attacked with a finer
                    // step count instead; the phase stays deterministic.
                    const stormJitter = fract(baseJit.add(stormPass / N_STORM_PASSES));
                    const stormP = org.add(dir.mul(
                        stormNearT.add(stormStep.mul(stormJitter)),
                    )).toVar();
                    Loop({ start: 0, end: N_STORM_STEPS, type: 'int' }, () => {
                        If(stormTr.lessThanEqual(0.0015), () => Break());
                        const sample = stormFieldAt(
                            stormP, stormMediumRange, stormFineRange,
                        );
                        const stormTrStep = exp(
                            sample.extinction.mul(stormStep).negate(),
                        );

                        // Beer attenuation through the mass above and below the
                        // sample gives continuous internal ambient self-occlusion.
                        // Foreground scud remains darker and separable from the
                        // deeper core without drawing any fixed sample plane.
                        const overheadTau = sample.extinction
                            .mul(stormDepth.mul(float(1).sub(sample.h)))
                            .mul(0.42);
                        const groundTau = sample.extinction
                            .mul(stormDepth.mul(sample.h))
                            .mul(0.12);
                        const upwardVisibility = exp(overheadTau.negate());
                        const groundVisibility = exp(groundTau.negate());
                        // Billow/detail carry more of the fold shading than
                        // macro alone: from directly below, the visible canopy
                        // patch spans only a couple of macro features, which
                        // read as one solid colour between the low clouds.
                        // The ~540 m and ~185 m octaves keep the gap ceiling
                        // visibly cloud-textured at zenith.
                        const foldLight = clamp(
                            float(0.06)
                                .add(sample.macro.mul(0.11))
                                .add(sample.billow.mul(0.15))
                                .add(sample.detail.mul(0.08))
                                .add(upwardVisibility.mul(0.38))
                                .add(groundVisibility.mul(0.18))
                                .sub(sample.scud.mul(0.10)),
                            0, 1,
                        );
                        // Near-neutral charcoal ramp: the previous blue-leaning
                        // constants made the sealed sky read as bright blue
                        // cloud over a near-night scene.
                        const stormBaseRadiance = mix(
                            vec3(0.0040, 0.0044, 0.0052),
                            vec3(0.046, 0.048, 0.052),
                            pow(foldLight, 1.32),
                        ).add(
                            u.cloudAmbGround.mul(groundVisibility).mul(0.007),
                        ).add(
                            u.cloudAmbSky.mul(upwardVisibility).mul(0.0032),
                        );
                        const strikeDistance = length(
                            stormP.xz.sub(u.lightningStrike.xz),
                        );
                        const strikeReach = exp(strikeDistance.mul(-0.00082))
                            .mul(0.94).add(0.025);
                        const strikeRadiance = u.lightningFlashColor
                            .mul(boundedStormFlash)
                            .mul(strikeReach)
                            .mul(float(0.42).add(sample.scud.mul(0.24))
                                .add(sample.core.mul(0.10)));
                        const sampleRadiance = stormBaseRadiance.add(strikeRadiance);
                        stormVolumeRgb.addAssign(
                            stormTr.mul(sampleRadiance)
                                .mul(float(1).sub(stormTrStep)),
                        );
                        stormTr.assign(stormTr.mul(stormTrStep));
                        stormP.assign(stormP.add(dir.mul(stormStep)));
                    });
                    stormTrSum.addAssign(stormTr);
                    stormVolumeSum.addAssign(stormVolumeRgb);
                }
                const stormTr = stormTrSum.div(N_STORM_PASSES);
                const stormBoundary = u.stormCanopy.mul(
                    smoothstep(0.0005, 0.012, dir.y),
                );
                // Density-derived premultiplied output. The extinction floor
                // makes this effectively opaque at settled zenith, but never by
                // substituting a constant alpha or painted top surface.
                stormA.assign(float(1).sub(stormTr).mul(stormBoundary));
                stormRgb.assign(
                    stormVolumeSum.div(N_STORM_PASSES).mul(stormBoundary),
                );
            });
            // distance fade into horizon haze — no hard clamp band
            const distFade = CLOUD_DBG ? float(1) : float(1).sub(smoothstep(
                u.fadeDist.mul(0.35), u.fadeDist, t0,
            ));
            const horizFade = CLOUD_DBG ? float(1) : smoothstep(0.008, 0.06, dir.y);
            const fade = distFade.mul(horizFade);
            // PREMULTIPLIED output: the Hillaire accumulator yields premultiplied
            // radiance. Standard alpha blending multiplies it by alpha AGAIN,
            // double-attenuating thin edge pixels into dark fringes — the material
            // uses an explicit premultiplied blend (ONE / OneMinusSrcAlpha), so the
            // fades must be folded into the color here as well.
            const cover = float(1).sub(Tr.mul(float(1).sub(wispA)));
            const ordinaryA = cover.mul(fade);
            const ordinaryRgb = col.mul(u.cloudTint).mul(fade);
            // During a weather morph the sealed underside is in front of the
            // outgoing ordinary clouds. Premultiplied over avoids pale additive
            // puffs. The union alpha is order-independent, so the seal cannot
            // open regardless of which layer's RGB is in front.
            const cloudA = stormA.add(ordinaryA.mul(float(1).sub(stormA)));
            // Settled Dark Storm reads flat with storm-front RGB: the >9 OD
            // Beer canopy suppresses the volumetric underlayer by ~20,000x.
            // Only at the sealed, no-celestial endpoint does the ordinary
            // volumetric RGB come forward — its 3D masses render against the
            // opaque canopy backing, so gaps show dark storm, never sky.
            const stormFrontRgb = stormRgb.add(
                ordinaryRgb.mul(float(1).sub(stormA)),
            );
            const underlayerFrontRgb = ordinaryRgb.add(
                stormRgb.mul(float(1).sub(ordinaryA)),
            );
            const settledUnderlayerFront = smoothstep(
                0.96, 0.995, u.stormCanopy,
            ).mul(
                float(1).sub(
                    smoothstep(0.005, 0.08, u.celestialVisibility),
                ),
            );
            const cloudRgb = mix(
                stormFrontRgb,
                underlayerFrontRgb,
                settledUnderlayerFront,
            );
            // BELOW-CLOUD ATMOSPHERE march: haze shafts (crepuscular rays) +
            // WORLD RAIN CURTAINS. Both live in the slab between camera and
            // cloud base; precipitation density hangs under DENSE weather
            // cells (same world-space weather map as the clouds), so rain is
            // a property of the WORLD — visible from any distance under the
            // cells that produce it, drifting with them — never a camera FX.
            const shaft = float(0).toVar();
            const trH = float(1).toVar();
            If(u.shaftK.greaterThan(0.0005).or(u.precipK.greaterThan(0.0005)).and(dir.y.greaterThan(0.0)), () => {
                // 20 steps over 6 km (NOT 12 over 12 km): 1 km steps against
                // 10-60 m curtain texture = step-aliasing that painted hard
                // vertical seam bands across the whole sub-cloud sky
                const tEnd = min(t0, float(6000));
                const stepH = tEnd.div(20);
                const sy = max(u.cloudLightDir.y, 0.08);
                const segL = u.cloudHeight.div(sy);
                const hp = org.add(dir.mul(stepH).mul(baseJit.mul(0.5).add(0.3))).toVar();
                for (let i = 0; i < 20; i++) {
                    // ring mode: atmoHeight is a remapped PROFILE coordinate,
                    // not meters — the shaft/altitude math needs physical y
                    // (this is what silently killed the god rays)
                    const hEnter = RING_R
                        ? max(float(RING_SLAB_LO + 20).sub(hp.y), 0).div(sy)
                        : max(u.cloudStart.sub(atmoHeight(hp)), 0).div(sy);
                    const od = float(0).toVar();
                    for (let j = 0; j < 6; j++) {
                        od.addAssign(smoothDensity(hp.add(u.cloudLightDir.mul(hEnter.add(segL.mul((j + 0.5) / 6))))));
                    }
                    const vis = exp(od.mul(segL.div(6)).negate());
                    // rain curtains: dense macro cells rain; fine xz column
                    // noise gives the falling-shaft texture
                    const cp1z = hp.z.add(u.skyWind.z.mul(u.time));
                    const cp1x = hp.x.add(u.skyWind.x.mul(u.time));
                    const cellCov = clamp(wSampleL(vec2(cp1z, cp1x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
                    // column texture coarsened + faded to smooth murk with
                    // distance — fine detail must stay below the step size
                    const tCur = stepH.mul(i + 0.5);
                    const colTex = wSampleS(vec2(cp1z, cp1x).mul(0.0008).add(vec2(0.61, 0.23)));
                    const colMod = mix(colTex.mul(1.1).add(0.25), float(0.8), smoothstep(900, 2600, tCur));
                    const belowBase = RING_R
                        ? float(1).sub(smoothstep(
                            float((RING_SLAB_LO + 20) * 0.55),
                            float(RING_SLAB_LO + 20),
                            hp.y,
                        ))
                        : float(1).sub(smoothstep(
                            u.cloudStart.mul(0.55), u.cloudStart, atmoHeight(hp),
                        ));
                    const ordinaryPrecipGate = smoothstep(u.precipLo, u.precipHi, cellCov);
                    // The sealed storm intentionally disables the ordinary
                    // weather/cloud density field. Keep its rain on a separate
                    // full-coverage path, with wind-advected column variation,
                    // instead of asking the disabled field for permission.
                    const stormPrecipGate = mix(float(0.72), float(1.0), colTex);
                    const precipGate = mix(
                        ordinaryPrecipGate,
                        stormPrecipGate,
                        clamp(u.stormCanopy, 0, 1),
                    );
                    const precip = u.precipK.mul(precipGate).mul(colMod).mul(2.1e-4 * (1 - (i / 20) * 0.5))
                        .mul(belowBase.mul(0.5).add(0.5));
                    const altPhys = RING_R ? hp.y : atmoHeight(hp);
                    // ring mode: curtains OFF pending their own tune — they were
                    // silently dead here (t0 was 0 so the curtain march never ran)
                    // until the slab fix restored t0, and they woke up as hard
                    // rectangular walls that hide the deck's curve
                    const rho = u.shaftDen.mul(u.shaftK).mul(exp(altPhys.div(-900))).add(RING_R ? float(0) : precip);
                    shaft.addAssign(trH.mul(vis.mul(0.75).add(0.25)).mul(rho).mul(stepH));
                    trH.assign(trH.mul(exp(rho.mul(stepH).negate())));
                    hp.assign(hp.add(dir.mul(stepH)));
                }
            });
            // curtains scatter AMBIENT skylight too — sun-only lighting rendered
            // distant rain as a black wall at the horizon. Under a sealed
            // canopy there is no direct sun to scatter: the sun term is gated
            // by celestial visibility and the skylight term is dimmed, so
            // full-coverage storm rain reads as dark falling water instead of
            // bright god rays under a storm that blots out the sun.
            const shaftSun = clamp(u.celestialVisibility, 0, 1);
            const shaftSkylight = mix(float(1), float(0.30), clamp(u.stormCanopy, 0, 1));
            const shaftCol = u.cloudLightColor.mul(u.cloudDim).mul(phaseF.mul(0.7).add(0.055)).mul(shaftSun)
                .add(u.cloudAmbSky.mul(u.cloudDim).mul(2.4).mul(shaftSkylight))
                .mul(shaft).mul(horizFade);
            // curtains genuinely occlude the sky behind them (haze density is
            // tiny so clear days are unaffected)
            const coverT = float(1).sub(float(1).sub(cloudA).mul(trH));
            const dg2 = OUTPUT_DITHER > 0
                ? hashScreen(screenCoordinate.xy.add(vec2(17.3, 41.7))).sub(0.5).mul(OUTPUT_DITHER).mul(coverT)
                : float(0);
            return vec4(cloudRgb.add(shaftCol).add(vec3(dg2, dg2, dg2)), coverT);
        };
        const cloudOut = Fn(() => cloudBody(screenRayDir(), cameraPosition));
        // analytic ringworld band along a ray — SHARED by the env bake and the
        // live reflection hook. The band mesh is depthless by design (local
        // clouds must render in front of it), so SSR can never return it: any
        // reflection path that wants the arc has to trace it analytically.
        // Ray from ~ground vs the ring cylinder (axis X through (0, centerY,
        // 0), radius R), inside → far root; terrain sampled with the authored
        // tiling; landmask-black = water (dark, glossy-ish).
        const ringEnvTrace = (dir, rw) => {
            const oy = float(2 - rw.centerY);
            const a = dir.y.mul(dir.y).add(dir.z.mul(dir.z)).max(1e-6);
            const b = oy.mul(dir.y).mul(2);
            const cq = oy.mul(oy).sub(rw.radius * rw.radius);
            const disc = b.mul(b).sub(a.mul(cq).mul(4)).max(0);
            const tHit = b.negate().add(sqrt(disc)).div(a.mul(2));
            const hx = dir.x.mul(tHit);
            const hy = oy.add(dir.y.mul(tHit)), hz = dir.z.mul(tHit);
            const inBand = float(1).sub(smoothstep(
                rw.halfWidth - 30, rw.halfWidth + 30, hx.abs(),
            ));
            const theta = atan2f(hz, hy.negate());          // 0 at the overhead crest
            const uT = theta.div(Math.PI * 2).mul(rw.repeat ?? 8);
            const vT = hx.div(rw.halfWidth * 2).add(0.5);
            const land = T3.texture(rw.map, vec2(uT, vT)).rgb;   // T3-qualified: bare texture() is NOT in this scope — the bake's original inline trace used it and silently died for every ringworld bake (the long-standing 'MeshBasicNodeMaterial invalid pipeline' audit noise)
            const mraw = rw.mask ? T3.texture(rw.mask, vec2(uT, float(1).sub(vT))).r : float(1);
            const wk = float(1).sub(smoothstep(0.45, 0.55, mraw)); // mask BLACK = water
            const ringAlbedo = mix(land, vec3(0.03, 0.055, 0.07), wk);
            // radial-inward normal lambert vs the sun + ambient
            const nrm = normalize(vec3(0, hy.negate(), hz.negate()));
            const lit = clamp(dot(nrm, u.sunDir), 0, 1).mul(0.75).add(0.3);
            const col = ringAlbedo.mul(lit).mul(u.cloudDim);
            // haze out where the band dives to the horizon (huge t)
            const hazeK = float(1).sub(smoothstep(
                1.2, 3.2, tHit.div(rw.radius),
            ));
            return { col, k: inBand.mul(hazeK) };
        };
        // keep sky surfaces OUT of the auto-enhance G-buffer (GTAO/SSR must not
        // treat dome normals as scene geometry)
        const noGBuffer = (m) => {
            if (T3.mrt && T3.vec4 && !globalThis.EANPA_NO_MRT) m.mrtNode = T3.mrt({ normal: T3.vec4(0), metalrough: T3.vec4(0) });   // EANPA: forward path — mrt stamps compile to empty structs in Chrome
            return m;
        };
        // cloudBody already returns premultiplied RGB. NodeMaterial's
        // premultipliedAlpha flag would multiply RGB by alpha a second time,
        // so select premultiplied blending explicitly without enabling that
        // shader transform.
        const cloudMat = noGBuffer(new T3.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, side: T3.BackSide, fog: false,
            premultipliedAlpha: false,
            blending: T3.CustomBlending,
            blendEquation: T3.AddEquation,
            blendSrc: T3.OneFactor,
            blendDst: T3.OneMinusSrcAlphaFactor,
            blendEquationAlpha: T3.AddEquation,
            blendSrcAlpha: T3.OneFactor,
            blendDstAlpha: T3.OneMinusSrcAlphaFactor,
        }));
        {
            const o = cloudOut();
            cloudMat.colorNode = o.rgb;
            cloudMat.opacityNode = o.a;
        }
        const cloudDome = new T3.Mesh(new T3.SphereGeometry(DOME_R * 0.96, 48, 24), cloudMat);
        cloudDome.renderOrder = -98; cloudDome.frustumCulled = false; cloudDome.userData.noSupportCheck = true;
        scene.add(cloudDome);

        // ---------------- BACKGROUND + CELESTIAL dome ----------------
        const starsNode = textures.stars ? T3.texture(textures.stars) : null;
        const moonNode = textures.moon ? T3.texture(textures.moon) : null;
        const hdriNode = textures.hdri ? T3.texture(textures.hdri) : null;
        const equirectUV = (d) => vec2(
            atan2f(d.z, d.x).div(Math.PI * 2).add(0.5),
            acos(clamp(d.y, -1, 1)).div(Math.PI),
        );
        const bgBody = (dirIn) => {
            const dir = dirIn;
            // gradient
            const upK = pow(clamp(dir.y.mul(1.35).add(0.02), 0, 1), 0.55);
            let col = mix(u.horizon, u.zenith, upK).toVar();
            // sun-forward warm lobe
            const mu = dot(dir, u.sunDir);
            col.addAssign(u.sunColor.mul(pow(max(mu, 0.0), 6.0)).mul(0.35).mul(float(1).sub(upK)));
            // optional HDRI base
            if (hdriNode) {
                const hdri = hdriNode.sample(equirectUV(dir)).level(0).rgb;   // EANPA: explicit LOD
                col.assign(mix(col, hdri.mul(u.hdriDim), u.hdriMix));
            }
            // moon disc mask FIRST — the planet/moon is an opaque body: stars
            // must not shine through it (they're additive layers otherwise)
            let moonDisc = null;
            if (moonNode) {
                const cosA = dot(dir, u.moonDir);
                moonDisc = smoothstep(u.moonCos, u.moonCos.add(0.0004), cosA);
            }
            // stars (rotated slowly, faded by sun elevation, occluded by the moon)
            if (starsNode) {
                const ra = u.time.mul(0.004);
                const dR = vec3(
                    dir.x.mul(cos(ra)).sub(dir.z.mul(sin(ra))),
                    dir.y,
                    dir.x.mul(sin(ra)).add(dir.z.mul(cos(ra))),
                );
                const st = starsNode.sample(equirectUV(dR)).level(0).rgb;   // EANPA: explicit LOD
                let starTerm = st.mul(st).mul(u.starFade).mul(1.6);   // st² boosts contrast
                if (moonDisc) starTerm = starTerm.mul(float(1).sub(moonDisc));
                col.addAssign(starTerm);
                col.addAssign(vec3(u.skyGlow));                        // pollution veil over the stars
            }
            // moon: orthographic disc → sphere normal → real texture + real phase
            if (moonNode) {
                const inDisc = moonDisc;
                const lx = dot(dir, u.moonRight).div(sqrt(float(1).sub(u.moonCos.mul(u.moonCos))));
                const ly = dot(dir, u.moonUp).div(sqrt(float(1).sub(u.moonCos.mul(u.moonCos))));
                const r2 = clamp(lx.mul(lx).add(ly.mul(ly)), 0, 1);
                const nz = sqrt(float(1).sub(r2));
                const lon = atan2f(nz, lx), lat = asin(clamp(ly, -1, 1));
                const muv = vec2(lon.div(Math.PI * 2).add(0.25), float(0.5).sub(lat.div(Math.PI)));
                const albedo = moonNode.sample(muv).level(0).rgb;   // EANPA: explicit LOD
                const nWorld = u.moonRight.mul(lx).add(u.moonUp.mul(ly)).add(u.moonDir.mul(nz.negate()));
                const lit = max(dot(nWorld, u.sunDir), 0.03);
                // day floor 0.5 (was 0.15): the moon/planet is a DAYTIME object
                // too — a giant companion world must read against the blue sky
                col.addAssign(albedo.mul(lit).mul(inDisc).mul(2.2).mul(u.moonLightK.mul(0.5).add(0.5)));
            }
            // CUSTOM CELESTIAL hook: a scene-authored body (procedural star,
            // gas giant, megastructure…) composited after the moon/stars and
            // before the default sun disc. Receives (dir, col) and returns
            // the new column — opaque bodies replace, glows add. Evaluated
            // here so the body appears in the sky, in the reflection hook,
            // AND in the env bake with one function.
            if (opts.celestial) col.assign(opts.celestial(dir, col));
            // HDR sun disc + corona
            const disc = smoothstep(0.99995, 0.999985, mu);
            col.addAssign(u.sunColor.mul(disc).mul(u.sunDiscI).mul(u.celestialVisibility));
            col.addAssign(u.sunColor.mul(pow(max(mu, 0.0), 900.0)).mul(3.0).mul(u.sunGlowI).mul(u.celestialVisibility));
            col.addAssign(u.sunColor.mul(pow(max(mu, 0.0), 60.0)).mul(0.22).mul(u.sunGlowI).mul(u.celestialVisibility));
            // Optional stable lookdev dither. Production output is HDR here;
            // animated pre-tone-map dither produced visible crawling lines.
            const dg = OUTPUT_DITHER > 0
                ? hashScreen(screenCoordinate.xy.add(vec2(53.1, 9.7))).sub(0.5).mul(OUTPUT_DITHER)
                : float(0);
            col.addAssign(vec3(dg, dg, dg));
            return vec4(col, 1);
        };
        const bgOut = Fn(() => bgBody(screenRayDir()));
        const bgMat = noGBuffer(new T3.MeshBasicNodeMaterial({ side: T3.BackSide, depthWrite: false, fog: false }));
        // CLOUDDBG: dim the background dome so cloud VOLUMES read against
        // dark — the below-horizon haze otherwise whites out exterior views
        bgMat.colorNode = CLOUD_DBG ? bgOut().rgb.mul(0.12) : bgOut().rgb;
        const bgDome = new T3.Mesh(new T3.SphereGeometry(DOME_R, 48, 24), bgMat);
        bgDome.renderOrder = -100; bgDome.frustumCulled = false; bgDome.userData.noSupportCheck = true;
        scene.add(bgDome);

        // ---------------- JS state + API ----------------
        // azSpanK: fraction of π the sun sweeps in azimuth over the day (0.9 ≈
        // 162°, realistic). A fixed camera can't hold that — compress to ~0.35
        // (63°) with elMax ~32 to keep the disc in one frame all day (timelapse).
        // opts.paletteTint = { zen:[r,g,b], hor:[...], sun:[...] } — per-band
        // multipliers over the TOD palette (alien-star color families: a red
        // giant's world reddens every hour of its day). Applied where the
        // palette is COMPUTED so lights, cloud radiance, and weather greying
        // all inherit it — and idempotent, unlike mutating the uniforms
        // per-frame (a compounding lerp on these collapsed a sky to black).
        const PT = opts.paletteTint;
        const tintPal = (p) => !PT ? p : {
            ...p,
            zen: PT.zen ? p.zen.map((v, i) => v * PT.zen[i]) : p.zen,
            hor: PT.hor ? p.hor.map((v, i) => v * PT.hor[i]) : p.hor,
            sun: PT.sun ? p.sun.map((v, i) => v * PT.sun[i]) : p.sun,
        };
        const state = { hours: 12, azBase: opts.azimuth ?? 1.9, elMax: opts.maxElevationDeg ?? 62, azSpanK: opts.azSpanK ?? 0.9, preset: 'cumulus', palette: tintPal(todAt(40)) };
        // Cloud-type changes use the same persistent material graph as weather.
        // Capture every authored preset uniform so coverage, vertical profile,
        // lighting, and the 2D/high-cloud morphology all move continuously.
        const CLOUD_SCALAR_KEYS = [
            'largeT', 'largeA', 'weatherT', 'finalMul', 'wScale', 'dScale',
            'cloudStart', 'cloudHeight', 'lightK', 'lightCacheDirect', 'wispOn', 'wispScale',
            'wispThreshold', 'wispStrength', 'wispOpacity', 'wispFloor', 'wispFilament',
            'stormCanopy',
        ];
        const CLOUD_VECTOR_KEYS = ['stretch', 'wispStretch', 'wispTint'];
        const cloudTransitionInfo = {
            active: false,
            from: 'cumulus',
            target: 'cumulus',
            durationSeconds: 0,
            elapsedSeconds: 0,
            rawProgress: 1,
            easedProgress: 1,
        };
        const captureCloudState = () => ({
            scalars: CLOUD_SCALAR_KEYS.map((key) => Number(u[key].value)),
            vectors: CLOUD_VECTOR_KEYS.map((key) => u[key].value.clone()),
        });
        const applyCloudState = (from, to, k) => {
            CLOUD_SCALAR_KEYS.forEach((key, i) => {
                u[key].value = from.scalars[i] + (to.scalars[i] - from.scalars[i]) * k;
            });
            CLOUD_VECTOR_KEYS.forEach((key, i) => {
                u[key].value.lerpVectors(from.vectors[i], to.vectors[i], k);
            });
        };
        const updateWispColor = () => {
            const pal = state.palette;
            u.wispColor.value.set(...pal.sun).lerp(V(1, 1, 1), 0.62)
                .multiplyScalar(0.22 + pal.int * 0.34)
                .multiply(u.wispTint.value);
        };
        // Material wrappers live on persistent local-scene materials while a
        // sky instance is replaceable. Track exact roots so repeated calls do
        // not stack TSL graphs and disposal can sever references to this sky's
        // uniforms/textures. Weather may restore an earlier root first, hence
        // the identity check during cleanup.
        const cloudShadowRoots = new Map();
        let disposed = false;
        const sys = {
            uniforms: u, state, cloudTransitionInfo,
            domes: [bgDome, cloudDome],
            sunDir: V(0, 1, 0), moonDir: V(0, -1, 0),
            stormCanopyInfo: {
                representation: 'sealed-low-layer-core-scud-volume',
                samples: N_STORM_STEPS * N_STORM_PASSES,
                semanticTopMeters: 19300,
                renderedLayerMeters: [1100, 1450],
                density: 'smooth-continuous-extinction',
                noise: 'warped-four-scale-analytic-3d-non-texture',
                layers: 'foreground-scud-plus-deep-core',
                coverage: 'beer-transmittance-optical-depth-floor',
                alpha: 'one-minus-averaged-transmittance',
                materialShadows: true,
                ordinaryVolumeAtSettledTarget: true,
            },
            cacheInfo: {
                densityBasis: densityBasisTex ? { size: densityCacheSize, texture: densityBasisTex } : null,
                lightVolume: lightCacheTex ? {
                    size: lightCacheDims,
                    texture: lightCacheTex,
                    refreshes: 0,
                    refreshSeconds: lightCacheOpts.refreshSeconds ?? 0.18,
                } : null,
            },
            cloudShadowInfo: {
                mode: 'world-space-sun-column',
                samples: N_CLOUD_SHADOW,
                followsCloudWind: true,
                arbitraryGeometry: true,
                qualityAffectsBudgetOnly: true,
                densityField: 'first-erosion-visible-cloud-mass',
            },
            reflectionInfo: {
                mode: 'native-equirectangular-pmrem',
                transientLightningInBake: false,
                cloudSamplePhase: 'quality-budgeted-multipass-bake',
                temporalHistory: false,
                highLayerHorizonFade: 'own-shell-distance',
                materialSource: 'three-native-resolved-material-brdf',
                materialWeighting: 'pmrem-environment-brdf',
                fresnelResponse: 'three-native-environment-fresnel',
                roughnessResponse: 'three-pmrem-angular-prefilter',
                receiverAoResponse: 'three-native-ibl-occlusion',
                screenSpaceCloudLayer: false,
            },
            celestialInfo: {
                earthMoonTexture: Boolean(textures.moon),
                earthMoonVisibility: textures.moon
                    ? 'tod-elevation-cloud-occlusion'
                    : 'texture-missing',
                earthMoonTone: 'neutral-cool-lunar-albedo',
            },
            invalidateOptimizedCaches() {
                lightCacheDirty = !!lightCacheCompute;
            },
            async prepareOptimizedCaches(renderer, camera, force = false) {
                if (!lightCacheCompute || state.preset === 'clear' || u.finalMul.value <= 0.0001
                    || u.lightCacheDirect.value >= 0.999) return false;
                const cam = camera ?? globalThis._c;
                if (!cam) return false;
                const [LX, , LZ] = lightCacheDims;
                // Ordinary skies follow the camera over the full fade range.
                // Ringworld clouds occupy a narrow, fixed band; spending the
                // same froxels over 59.8 km left only ~20x14 useful X/Z cells.
                const halfX = RING_R ? uLocalHalf.value * 1.3 : u.fadeDist.value * 1.15;
                const halfZ = RING_R ? RING_ZEND + 200 : u.fadeDist.value * 1.15;
                const spanX = halfX * 2, spanZ = halfZ * 2;
                // Ringworld's cache Y coordinate is normalized deck-local
                // height (see sample/fill above); ordinary skies remain world Y.
                const yMin = RING_R ? 0 : u.cloudStart.value - 360;
                const yMax = RING_R ? 1 : u.cloudStart.value + u.cloudHeight.value + 180;
                const cellX = spanX / LX, cellZ = spanZ / LZ;
                const centerX = RING_R ? 0 : Math.floor(cam.position.x / cellX) * cellX;
                const centerZ = RING_R ? 0 : Math.floor(cam.position.z / cellZ) * cellZ;
                const nextMin = V(centerX - halfX, yMin, centerZ - halfZ);
                const simT = u.time.value;
                const refreshEvery = lightCacheOpts.refreshSeconds ?? 0.18;
                // Camera clip-volume crossings are hard invalidations. A
                // weather transition also lerps the Y bounds every frame;
                // let the normal refresh cadence absorb that gradual change
                // instead of dispatching one full volume per display frame.
                const originMoved = !lightCacheReady
                    || lightCacheOrigin.x !== nextMin.x
                    || lightCacheOrigin.z !== nextMin.z;
                const sunMoved = !lightCacheReady || lightCacheSun.dot(u.cloudLightDir.value) < 0.9995;
                const timeDue = simT < lightCacheLastT || simT - lightCacheLastT >= refreshEvery;
                if (!force && lightCacheReady && !lightCacheDirty && !originMoved && !sunMoved && !timeDue) return false;

                const span = V(spanX, Math.max(1, yMax - yMin), spanZ);
                lightCacheMin.value.copy(nextMin);
                lightCacheSpan.value.copy(span);
                lightCacheInvSpan.value.set(1 / span.x, 1 / span.y, 1 / span.z);
                await renderer.computeAsync(lightCacheCompute);
                lightCacheOrigin.copy(nextMin);
                lightCacheSun.copy(u.cloudLightDir.value);
                lightCacheLastT = simT;
                lightCacheDirty = false;
                lightCacheReady = true;
                sys.cacheInfo.lightVolume.refreshes++;
                sys.cacheInfo.lightVolume.lastTime = simT;
                globalThis._cloudCacheStats = {
                    density: densityBasisTex ? densityCacheSize : 0,
                    light: lightCacheDims,
                    refreshes: sys.cacheInfo.lightVolume.refreshes,
                    preset: state.preset,
                };
                return true;
            },
            setSun(azRad, elRad) {
                sys.sunDir.set(Math.cos(elRad) * Math.cos(azRad), Math.sin(elRad), Math.cos(elRad) * Math.sin(azRad)).normalize();
                u.sunDir.value.copy(sys.sunDir);
                const elDeg = elRad * 180 / Math.PI;
                const pal = tintPal(todAt(elDeg));
                state.palette = pal;
                u.zenith.value.set(...pal.zen);
                u.horizon.value.set(...pal.hor);
                u.sunColor.value.set(...pal.sun);
                u.starFade.value = pal.star;
                u.hdriDim.value = Math.max(0.04, Math.min(1, 0.1 + pal.int * 0.45));
                // cloud lighting: sun by day, MOON by night (smooth handoff in twilight)
                const nightK = Math.max(0, Math.min(1, (-elDeg - 2) / 8));
                u.moonLightK.value = nightK;
                // donor calibration: reference shader is HDR-native and the engine
                // effect rescales by colorScale 0.08 for ACES (cloud bodies ~1-3,
                // sky bg ~0.1-0.5). Baked into these coefficients.
                const sunCol = V(...pal.sun).multiplyScalar(pal.int * 7);
                const moonCol = V(0.45, 0.55, 0.85).multiplyScalar(1.3 * nightK);
                u.cloudLightColor.value.copy(sunCol.lerp(moonCol, nightK));
                u.cloudLightDir.value.copy(nightK > 0.5 ? sys.moonDir : sys.sunDir);
                const ambDay = V(...pal.zen).multiplyScalar(0.34 * (0.25 + pal.int * 0.55));
                const ambNight = V(0.04, 0.055, 0.10).multiplyScalar(0.6);
                u.cloudAmbSky.value.copy(ambDay.lerp(ambNight, nightK));
                u.cloudAmbGround.value.set(0.8, 0.8, 0.8).multiplyScalar(Math.max(0.008, pal.int * 0.027));
                // High ice/sheet layer: straight radiance, sun-tinted and
                // bright enough to scatter rather than read as charcoal.
                // Preset tint differentiates cool stratus from warm cumulus
                // and clean white cirrus.
                updateWispColor();
            },
            setTime(hours) {
                state.hours = hours;
                const dayK = (hours - 6) / 12;                       // 6h sunrise → 18h sunset
                const el = Math.sin(dayK * Math.PI) * state.elMax * Math.PI / 180;
                const az = state.azBase + (dayK - 0.5) * Math.PI * state.azSpanK;
                // moon: opposite arc
                const mK = (hours + 6) % 24 / 12 - 0.5;
                const mel = Math.sin(((hours + 12 - 6) / 12) * Math.PI) * 48 * Math.PI / 180;
                const maz = state.azBase + mK * Math.PI * 0.8 + Math.PI;
                sys.moonDir.set(Math.cos(mel) * Math.cos(maz), Math.sin(mel), Math.cos(mel) * Math.sin(maz)).normalize();
                u.moonDir.value.copy(sys.moonDir);
                const mr = V(0, 1, 0).cross(sys.moonDir).normalize();
                u.moonRight.value.copy(mr);
                u.moonUp.value.copy(sys.moonDir.clone().cross(mr).normalize());
                sys.setSun(az, el);
            },
            setClouds(name, over = {}) {
                // An immediate set supersedes a cloud-only morph. Weather's
                // transitionTo() deliberately uses this setter to capture its
                // target, then restores/interpolates the same uniform set.
                sys._cloudTransition = null;
                const resolvedName = PRESETS[name] ? name : 'cumulus';
                state.preset = resolvedName;
                Object.assign(cloudTransitionInfo, {
                    active: false,
                    from: resolvedName,
                    target: resolvedName,
                    durationSeconds: 0,
                    elapsedSeconds: 0,
                    rawProgress: 1,
                    easedProgress: 1,
                });
                const p = { ...PRESETS[resolvedName], ...over };
                u.largeT.value = p.largeT; u.largeA.value = p.largeA;
                u.weatherT.value = p.weatherT; u.finalMul.value = p.finalMul;
                u.wScale.value = p.wScale; u.dScale.value = p.dScale;
                u.cloudStart.value = p.start; u.cloudHeight.value = p.height;
                u.stretch.value.set(...p.stretch);
                u.lightK.value = p.lightK;
                u.lightCacheDirect.value = p.lightCacheDirect ?? 0;
                u.wispOn.value = p.wispOn;
                u.wispScale.value = p.wispScale;
                u.wispThreshold.value = p.wispThreshold;
                u.wispStrength.value = p.wispStrength;
                u.wispOpacity.value = p.wispOpacity;
                u.wispFloor.value = p.wispFloor ?? 0;
                u.wispFilament.value = p.wispFilament;
                u.stormCanopy.value = p.stormCanopy ?? 0;
                u.wispStretch.value.set(...p.wispStretch);
                u.wispTint.value.set(...p.wispTint);
                // Skip the expensive transparent dome when the semantic
                // preset contributes neither volume nor high wisps. Weather
                // transitions call setClouds again and restore visibility.
                cloudDome.visible = p.finalMul > 0 || p.wispOn > 0 || (p.stormCanopy ?? 0) > 0;
                updateWispColor();
                lightCacheDirty = !!lightCacheCompute;
                return resolvedName;
            },
            transitionClouds(name, duration = 45, over = {}) {
                if (disposed) return false;
                const resolvedName = PRESETS[name] ? name : 'cumulus';
                const fromPreset = state.preset;
                const fromVisible = cloudDome.visible;
                const from = captureCloudState();

                // Apply once to obtain the exact authored target, including an
                // optional weather-style override, then restore the live frame.
                sys.setClouds(resolvedName, over);
                const to = captureCloudState();
                const toVisible = cloudDome.visible;
                applyCloudState(from, from, 0);
                updateWispColor();

                const transitionHasClouds = fromVisible || toVisible;
                cloudDome.visible = transitionHasClouds;
                state.preset = transitionHasClouds ? 'transition' : resolvedName;
                const safeDuration = Math.max(0.001, Number.isFinite(duration) ? duration : 45);
                sys._cloudTransition = {
                    fromPreset,
                    toPreset: resolvedName,
                    from,
                    to,
                    toVisible,
                    t0: null,
                    duration: safeDuration,
                };
                Object.assign(cloudTransitionInfo, {
                    active: true,
                    from: fromPreset,
                    target: resolvedName,
                    durationSeconds: safeDuration,
                    elapsedSeconds: 0,
                    rawProgress: 0,
                    easedProgress: 0,
                });
                lightCacheDirty = !!lightCacheCompute;
                return true;
            },
            applyToLights({ sun, hemi, fog } = {}) {
                const pal = state.palette;
                const nightK = u.moonLightK.value;
                if (sun) {
                    sun.color.setRGB(...pal.sun).lerp(new T3.Color(0.5, 0.6, 0.95), nightK);
                    sun.intensity = Math.max(0.08, pal.int * 1.15) * (1 - nightK) + 0.35 * nightK;
                    const d = nightK > 0.5 ? sys.moonDir : sys.sunDir;
                    sun.position.copy(d.clone().multiplyScalar(120));
                }
                if (hemi) {
                    hemi.color.setRGB(...pal.zen).multiplyScalar(2.2);
                    hemi.groundColor.setRGB(pal.hor[0] * 0.25, pal.hor[1] * 0.2, pal.hor[2] * 0.18);
                    hemi.intensity = 0.25 + pal.int * 0.25 + nightK * 0.06;
                }
                if (fog && fog.color) fog.color.setRGB(...pal.hor).multiplyScalar(0.5 + pal.int * 0.12);
                return pal;
            },
            // world weather-field access — the SAME macro coverage the clouds
            // use, so consumers (rain, lightning, gameplay) agree with the sky.
            // JS sampler (bilinear over the CPU weather map, drift-aware):
            weatherAt(x, z) {
                const sc = 0.00005 * u.wScale.value;
                const t = u.time.value;
                const wrap = (v) => { let f = v % 1; if (f < 0) f += 1; return f; };
                const wv = u.skyWind.value;
                const uu = wrap(-((z + t * wv.z) * sc)) * WSZ;
                const vv = wrap(-((x + t * wv.x) * sc)) * WSZ;
                const x0 = Math.floor(uu) % WSZ, y0 = Math.floor(vv) % WSZ;
                const x1 = (x0 + 1) % WSZ, y1 = (y0 + 1) % WSZ;
                const fx = uu - Math.floor(uu), fy = vv - Math.floor(vv);
                const rAt = (xx, yy) => wpix[(yy * WSZ + xx) * 4] / 255;
                const val = (rAt(x0, y0) * (1 - fx) + rAt(x1, y0) * fx) * (1 - fy)
                          + (rAt(x0, y1) * (1 - fx) + rAt(x1, y1) * fx) * fy;
                return Math.max(0, Math.min(2, (val - u.largeT.value) * u.largeA.value));
            },
            // Cloud-shadow factor for an arbitrary world position (multiply
            // into a material's colorNode). It traces from that receiver toward
            // the actual sun through the same moving density field as the sky.
            // The fixed quality tier controls only N_CLOUD_SHADOW.
            // cheapDensity includes the first erosion octave from the visible
            // cloud mass. The erosion-free shaft proxy has a ~20 km footprint
            // and merely pulses the whole local scene darker/brighter; it is
            // stable for godrays but cannot draw travelling ground patches.
            tslCloudShadow(pWorld, strength = 0.55) {
                return Fn(() => {
                    const dy = max(u.sunDir.y, 0.08);
                    const stormK = clamp(u.stormCanopy, 0, 1);
                    const shadowBottom = mix(u.cloudStart, stormLayerBottom(), stormK);
                    const shadowDepth = mix(u.cloudHeight, stormLayerDepth(), stormK);
                    const hEnter = max(shadowBottom.sub(pWorld.y), 0).div(dy);
                    const segL = shadowDepth.div(dy);
                    // Distant receivers sample the animated FBM at world+time
                    // coordinates where float precision breaks down, so their
                    // shadow patches pop bright/dark. Blend the noisy density
                    // toward a stable coverage-mean extinction with receiver
                    // distance: near ground keeps travelling patches, far
                    // ground keeps steady weather-correct dimming.
                    const farK = smoothstep(
                        float(1800), float(5200),
                        length(pWorld.sub(cameraPosition)),
                    );
                    const meanExtinction = clamp(u.finalMul, 0, 1).mul(0.030);
                    const od = float(0).toVar();
                    // Once a settled canopy has made celestial visibility zero,
                    // the real scene key is already exactly zero; skip every
                    // per-material storm-noise tap instead of shadowing a light
                    // that cannot contribute. During the transition, this same
                    // field continuously occludes the remaining key.
                    If(u.celestialVisibility.greaterThan(0.001), () => {
                        for (let j = 0; j < N_CLOUD_SHADOW; j++) {
                            const along = hEnter.add(segL.mul((j + 0.5) / N_CLOUD_SHADOW));
                            const sampleP = pWorld.add(u.sunDir.mul(along));
                            const ordinaryExtinction = float(0).toVar();
                            const stormExtinction = float(0).toVar();
                            If(stormK.lessThan(0.999), () => {
                                ordinaryExtinction.assign(mix(
                                    cheapDensity(sampleP).mul(0.018),
                                    meanExtinction,
                                    farK,
                                ));
                            });
                            If(stormK.greaterThan(0.001), () => {
                                stormExtinction.assign(stormShadowExtinctionAt(sampleP));
                            });
                            od.addAssign(mix(ordinaryExtinction, stormExtinction, stormK));
                        }
                    });
                    // Both paths are converted to extinction per metre before
                    // integration, so storm core/scud casts the same continuous
                    // moving material shadow as the visible Beer volume.
                    const opticalDepth = od.mul(segL.div(N_CLOUD_SHADOW));
                    const occ = float(1).sub(exp(opticalDepth.negate()));
                    const daylight = smoothstep(0.02, 0.16, u.sunDir.y)
                        .mul(clamp(u.celestialVisibility, 0, 1));
                    const cloudMass = max(
                        smoothstep(0.0001, 0.02, u.finalMul),
                        smoothstep(0.0001, 0.02, u.stormCanopy),
                    );
                    // cloudShadowStrength is a live debug/isolation multiplier.
                    return float(1).sub(
                        occ.mul(strength)
                            .mul(u.cloudShadowStrength)
                            .mul(daylight)
                            .mul(cloudMass),
                    );
                })();
            },
            // wrap scene materials with cloud shadowing (composes with other
            // colorNode wrappers, e.g. the weather system's wetness)
            wrapCloudShadows(sceneRoot, strength = 0.55) {
                const done = new Set();
                let n = 0;
                (sceneRoot || scene).traverse((o) => {
                    if (!o.isMesh || o.userData.noCloudShadow) return;
                    if (sys.domes.includes(o)) return;
                    const mats = Array.isArray(o.material) ? o.material : [o.material];
                    for (const m of mats) {
                        const isPbrNode = m?.isMeshStandardNodeMaterial
                            || m?.isMeshPhysicalNodeMaterial
                            || (m?.isNodeMaterial
                                && m.roughness !== undefined
                                && m.metalness !== undefined);
                        if (!isPbrNode || m.userData?.keepEnv
                            || done.has(m) || cloudShadowRoots.has(m)) continue;
                        done.add(m);
                        const original = m.colorNode;
                        // Shade RGB only. Multiplying the complete RGBA root
                        // raises alpha-test cutoffs under clouds and can erase
                        // thin foliage long before its lighting changes.
                        const baseColor4 = T3.vec4(original ?? T3.materialColor);
                        const shade = sys.tslCloudShadow(T3.positionWorld, strength);
                        const wrapped = T3.vec4(baseColor4.rgb.mul(shade), baseColor4.a);
                        cloudShadowRoots.set(m, { original, wrapped });
                        m.colorNode = wrapped;
                        m.needsUpdate = true;
                        n++;
                    }
                });
                console.log('[sky] cloud shadows wrapped', n, 'materials');
                return cloudShadowRoots.size;
            },
            // JS: sun dimming factor from coverage directly over a point
            // (drive DirectionalLight intensity for "sun behind cloud")
            sunCoverageDim(x, z, strength = 0.7) {
                const dy = Math.max(0.12, u.cloudLightDir.value.y);
                const t = (u.cloudStart.value) / dy;
                const cov = sys.weatherAt(x + u.cloudLightDir.value.x * t, z + u.cloudLightDir.value.z * t);
                const k = Math.min(1, Math.max(0, (cov - 0.35) / 1.05));
                return 1 - k * strength;
            },
            // TSL coverage node for shader-side gating (xz = world coords):
            tslCoverage(xz) {
                const uvW = vec2(xz.y.add(u.skyWind.z.mul(u.time)), xz.x.add(u.skyWind.x.mul(u.time))).mul(float(-0.00005).mul(u.wScale));
                return clamp(weatherNode.sample(uvW).level(0).r.sub(u.largeT).mul(u.largeA), 0, 2);   // EANPA: explicit LOD
            },
            // MOVING per-pixel cloud reflections on metals. The hook raymarches
            // THIS sky along the current reflected ray and returns a sharp live
            // cloud delta with the same sharp receiver weight as pinned r184
            // SSR: opacity * final MRT metalness * Fresnel. The browser then
            // builds and samples the matching roughness mip lobe.
            // shared env-target creation: bakeEnv renders into it; the
            // reflection hook samples it as the below-horizon fallback
            _ensureEnvTarget(W = 512, H = 256) {
                if (sys._envTarget) return sys._envTarget;
                const target = new T3.RenderTarget(W, H, { type: T3.HalfFloatType, format: T3.RGBAFormat, depthBuffer: false, stencilBuffer: false });
                target.texture.mapping = T3.EquirectangularReflectionMapping;
                target.texture.minFilter = T3.LinearFilter; target.texture.magFilter = T3.LinearFilter;
                target.texture.colorSpace = T3.LinearSRGBColorSpace;
                target.texture.name = 'sky_system_env';
                sys._envTarget = target;
                return target;
            },
            enableReflections(camera, ropts = {}) {
                // EIDOVERSE PORT: the hook suppresses material env-IBL and SSR
                // only covers camera-visible ground — below-horizon rays whose
                // target the camera cannot see (e.g. the ground directly under
                // a mirror ball) previously reflected NOTHING. Sample the baked
                // env (its ground-bounce band) for those rays instead.
                // The node starts on an INITIALIZED 1x1 black placeholder —
                // binding a never-rendered RenderTarget texture at pipeline
                // compile races texture init on the wgpu backend (intermittent
                // "OutputType is invalid" shader rejections that silently drop
                // whole materials). bakeEnv swaps the real texture in after
                // its first render.
                const envFbPlaceholder = new T3.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1);
                envFbPlaceholder.needsUpdate = true;
                const envFbNode = T3.texture(envFbPlaceholder);
                sys._envFbNode = envFbNode;
                // debug modes REPLACE the final image (render_scene checks this
                // flag in the deferred compose) — additive debug over a lit
                // beauty is unreadable and misled a whole night of bisects
                if (ropts.debug) globalThis._cloudReflDebugReplace = true;
                const reflHook = (colorIn, sceneDepth, sceneNormal, sceneMR) => {
                    if (ropts.debug === 'null') return Fn(() => vec4(0, 0, 0, 1))(); // bisect: constant, no samples
                    if (ropts.debug === 'mr') {
                        // bisect: visualize the raw G-buffer this hook sees —
                        // R = metalness, G = roughness, B = depth ×10 (reversed-z:
                        // scene depths live in 0..~0.1, unscaled they read black)
                        const dTex = T3.convertToTexture(sceneDepth);
                        return Fn(() => {
                            const suv = T3.uv();
                            const mrV = sceneMR.sample(suv);
                            return vec4(mrV.r, mrV.g, clamp(dTex.sample(suv).r.mul(10), 0, 1), 1);
                        })();
                    }
                    const depthTex = T3.convertToTexture(sceneDepth);
                    return Fn(() => {
                        const suv = T3.uv();
                        const sceneD = depthTex.sample(suv).r;
                        const isSurface = T3.step(sceneD, 0.9999);
                        const mr = sceneMR.sample(suv);
                        const metalness = mr.r;
                        const viewPos = T3.getViewPosition(suv, sceneD, u.projInv);
                        const worldPos = u.camWorld.mul(vec4(viewPos, 1)).xyz;
                        const camPos = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                        const viewDir = normalize(worldPos.sub(camPos));
                        const viewNormal = sceneNormal.sample(suv);
                        const worldNormal = normalize(u.camWorld.mul(vec4(viewNormal.xyz, 0)).xyz);
                        const reflDir = T3.reflect(viewDir, worldNormal);
                        // Exact coefficient used by Three r184 SSRNode. Its dot
                        // product is invariant under the view-to-world rotation.
                        const fresnelCoe = dot(viewDir, reflDir).add(1).div(2);
                        // Match SSRNode's ordering exactly: op begins as
                        // opacity * metalness, receives Fresnel, and is written
                        // into the sharp source before roughness mip filtering.
                        // Environment rays have no finite geometry-hit distance,
                        // so SSR's hit-distance attenuation is intentionally 1.
                        const op = float(ropts.gain ?? 1.0).mul(metalness).toVar();
                        op.mulAssign(fresnelCoe);
                        const reflRO = worldPos.add(worldNormal.mul(0.05));
                        const cloudCol = vec3(0).toVar();
                        // The horizon transition is metadata for the final
                        // reflection compositor. Keeping it in alpha prevents
                        // a post-process blur from spreading sky reflection
                        // across unrelated materials or silhouettes.
                        const skyVis = smoothstep(-0.10, 0.10, reflDir.y);
                        // Match SSR's authored receiver contract: skip only an
                        // exact zero-metal pixel. Metalness is already present
                        // in `op`; it must not be reapplied after mip filtering.
                        If(metalness.greaterThan(0.0).and(isSurface.greaterThan(0.5)), () => {
                            if (ropts.debug === 'flat') {         // bisect: no sky eval at all
                                cloudCol.assign(vec3(4, 0, 0).mul(op));
                            } else if (ropts.debug === 'nocloud') { // bisect: bg dome only
                                cloudCol.assign(bgBody(reflDir).rgb.mul(op));
                            } else {
                                // 1-pass march: denoise + roughness blur downstream
                                // clean the variance (multi-pass here would be waste)
                                // A screen-pixel hash is appropriate for the
                                // current visible frame, but a reflected world
                                // feature crosses pixels under camera motion and
                                // would reroll that one-sample offset. A fixed
                                // stratified midpoint makes the same ray evaluate
                                // deterministically with no temporal history.
                                const cld = cloudBody(reflDir, reflRO, 1, float(0.5));
                                let bg = bgBody(reflDir).rgb;
                                // ringworld scenes: the arc is part of this
                                // world's sky — trace it into reflections
                                // (bg < ring < clouds, the on-screen stack)
                                const rw = sys._envRingworld;
                                if (rw && rw.map) {
                                    const rt = ringEnvTrace(reflDir, rw);
                                    bg = mix(bg, rt.col, rt.k);
                                }
                                // RAY-based sky visibility, not normal-based: the sky
                                // is world-space now, so occlusion is the SSR hit
                                // along this same ray (roof paints over sky in the
                                // compose). All that's left to gate here is "does the
                                // ray point at sky at all" — down-rays fade to 0 and
                                // SSR/ground takes them. (Replaces the engine's N·up
                                // gate, which cut a hard terminator at normal.y = 0.)
                                // gain: dome output is display-calibrated (donor 0.08
                                // scale) but the compose stacks AO on top —
                                // uncompensated, mirror metal reads several times
                                // darker than the sky it reflects
                                const liveEnvironment = ropts.deltaOnly === true
                                    ? cld.rgb.sub(bg.mul(cld.a))
                                    : bg.mul(float(1).sub(cld.a)).add(cld.rgb);
                                // EIDOVERSE PORT: this host's deferred compose
                                // (render_scene.mjs) gates cloud rgb only by SSR
                                // miss and never reads the alpha metadata — bake
                                // the ray-based horizon fade into rgb here (as
                                // the pre-port core did) so down-rays contribute
                                // nothing where SSR misses. Alpha still carries
                                // skyVis for compositors that consume it.
                                cloudCol.assign(liveEnvironment
                                    .mul(op).mul(skyVis));
                                // below-horizon fallback: baked-env sample
                                // along the same ray (SSR hits still override
                                // via the compositor's 1-ssrAlpha gate). The
                                // bake target stores rows Y-FLIPPED (see the
                                // bake fragment's inverse mapping) — flip v.
                                const envUV = equirectUV(reflDir);
                                cloudCol.addAssign(envFbNode.sample(
                                    vec2(envUV.x, float(1).sub(envUV.y))).rgb
                                    .mul(op).mul(float(1).sub(skyVis)));
                            }
                        });
                        return vec4(cloudCol, skyVis.mul(isSurface));
                    })();
                };
                const reflBlur = (cloudReflTex, sceneDepth, sceneNormal, sceneMR) => {
                    if (typeof T3.gaussianBlur !== 'function') return null;
                    const cloudTex = T3.convertToTexture(cloudReflTex);
                    // bilateral denoise (depth+normal aware) kills raymarch speckle
                    // within a surface while preserving silhouettes
                    const sharpInputTex = (typeof T3.denoise === 'function' && camera && ropts.denoise !== false)
                        ? T3.convertToTexture(T3.denoise(cloudTex, sceneDepth, sceneNormal, camera))
                        : cloudTex;
                    const lightBlur = T3.gaussianBlur(sharpInputTex, null, 2);
                    const heavyBlur = T3.gaussianBlur(sharpInputTex, null, 8);
                    return Fn(() => {
                        const suv = T3.uv();
                        const mr = sceneMR.sample(suv);
                        const rough = clamp(mr.g, 0, 1);
                        const r2 = rough.mul(rough);
                        const sharp = sharpInputTex.sample(suv).rgb;
                        // Legacy optional hook: if a caller enables it, retain
                        // the same roughness² shape and one linear metalness
                        // multiply as the production five-mip path.
                        const stage1 = mix(sharp, lightBlur.rgb, smoothstep(0.0, 0.25, r2));
                        const stage2 = mix(stage1, heavyBlur.rgb, smoothstep(0.25, 1.0, r2));
                        return vec4(stage2.mul(mr.r), 1.0);
                    })();
                };
                globalThis._autoEnhanceCloudReflectHook = reflHook;
                // this hook gates by REFLECTION DIRECTION internally — tell the
                // engine to skip its blunt N·up multiply (kept for the old
                // screenspace effect, whose hook doesn't self-gate)
                globalThis._autoEnhanceCloudReflectHook.selfGated = true;
                if (ropts.blur !== false) globalThis._autoEnhanceCloudReflectBlurHook = reflBlur;
                // standalone godrays effect can't see these clouds — trip its
                // mutual-exclusion sentinel (the sky carries its own shafts)
                globalThis._volumetricCloudsActive = true;
                console.log('[sky] cloud-reflect hooks registered — SSR prefilter metal/Fresnel + shared roughness mip response');
            },
            // Bake sky+clouds into an equirect environment returned to the
            // caller for per-material assignment. The browser branch never
            // writes scene.environment because that suppresses Basic-family
            // sky domes in Chrome.
            // domes are transparent, depthless, and G-buffer-excluded, so SSR
            // can NEVER hit them — env-IBL is how clouds reach reflections.
            // Re-call after meaningful TOD / weather changes. bopts.cloudPasses
            // can force a cheap one-pass reflection bake independently of the
            // visible cloud quality tier.
            // bopts.ringworld = { centerY, radius, halfWidth, map, mask,
            // repeat } traces the ringworld band analytically into the bake so
            // reflections/env-IBL carry the arc.
            async bakeEnv(renderer, bopts = {}) {
                const W = bopts.width ?? 512, H = bopts.height ?? 256;
                if (lightCacheCompute && state.preset !== 'clear' && u.finalMul.value > 0.0001
                    && u.lightCacheDirect.value < 0.999) {
                    await sys.prepareOptimizedCaches(renderer, bopts.camera ?? globalThis._c, true);
                }
                // three's WebGPU backend redundantly re-creates RT textures that
                // a later pass samples ("Texture already initialized" throw) —
                // same idempotency patch the engine's env fallback installs
                // (that fallback is skipped once we set our own environment)
                try {
                    const tu = renderer.backend?.textureUtils;
                    if (tu && !tu._patchedForPMREM) {
                        const orig = tu.createTexture.bind(tu);
                        tu.createTexture = function (texture, options) {
                            try { if (this.backend.get(texture)?.initialized) return; } catch {}
                            return orig(texture, options);
                        };
                        tu._patchedForPMREM = true;
                    }
                } catch {}
                // re-bakes REUSE the target: a fresh RT texture bound mid-render
                // is what trips the redundant-createTexture throw, and callers
                // re-bake on TOD / weather changes (day cycle, scene segments)
                let target = sys._envTarget;
                if (!target) {
                    target = sys._ensureEnvTarget(W, H);
                } else if (target.width !== W || target.height !== H) {
                    // EIDOVERSE PORT: resize IN PLACE — the reflection hook's
                    // env-fallback node captured this texture object; a
                    // dispose/recreate would leave it sampling a dead texture.
                    target.setSize(W, H);
                }
                const rw = bopts.ringworld;
                if (rw) sys._envRingworld = rw;   // the reflection hook traces the same band (built post-setup, after this bake)
                if (rw && rw.halfWidth) uBandHalf.value = rw.halfWidth;
                if (rw && rw.localHalf) uLocalHalf.value = rw.localHalf;
                // (deliberately NOT adopting rw.centerY for the deck — the
                // bake's 4940 convention is not the mesh axis; sensor-proven)
                // The bake material/scene are CACHED across re-bakes: building
                // a fresh node graph per bake recompiled the entire volumetric
                // march pipeline every refresh interval — a main-thread freeze
                // on every weather/cloud reflection update. Everything the
                // graph reads at render time is uniform-driven; only the
                // baked-in branches below participate in the cache key.
                const cloudsOn = bopts.includeClouds !== false && state.preset !== 'clear';
                const bakeKey = `${W}x${H}|p${bopts.cloudPasses ?? 'd'}|c${cloudsOn ? 1 : 0}`;
                let bake = sys._envBake;
                if (!bake || bake.key !== bakeKey || bake.rw !== (rw ?? null)) {
                    bake?.dispose();
                    const bakeMat = new T3.NodeMaterial();
                    bakeMat.fragmentNode = Fn(() => {
                        const suv = T3.uv();
                        const lon = suv.x.sub(0.5).mul(Math.PI * 2);
                        const lat = float(0.5).sub(suv.y).mul(Math.PI);
                        const cl = cos(lat);
                        // Exact inverse of Three r184's equirectUV() after its
                        // mandatory render-target Y flip. The previous donor axes
                        // transformed reflected directions as (x,y,z)->(z,-y,x):
                        // the sun/ring were quarter-turned and vertically inverted
                        // on metals while the live reflection hook stayed correct.
                        const dir = normalize(vec3(cl.mul(cos(lon)), sin(lat), cl.mul(sin(lon))));
                        let bg = bgBody(dir).rgb;
                        if (rw && rw.map) {
                            const rt = ringEnvTrace(dir, rw);
                            bg = mix(bg, rt.col, rt.k);
                        }
                        const cld = !cloudsOn
                            ? vec4(0, 0, 0, 0)
                            // Do not freeze a millisecond lightning pulse into the
                            // PMREM for an entire refresh interval. The visible
                            // cloud layer and bounded scene PointLight still flash;
                            // the persistent environment contains storm ambient.
                            : cloudBody(
                                dir, vec3(0, 2, 0), bopts.cloudPasses, null, float(0),
                            );
                        // premultiplied cloud over sky; below the horizon fade to a
                        // ground-bounce tone so floor reflections aren't sky-bright
                        const belowHorizon = float(1).sub(
                            smoothstep(-0.35, 0.0, dir.y),
                        );
                        return vec4(bg.mul(float(1).sub(cld.a)).add(cld.rgb)
                            .mul(mix(float(1), float(0.45), belowHorizon)), 1);
                    })();
                    const bakeScene = new T3.Scene();
                    const bakeCam = new T3.OrthographicCamera(-1, 1, 1, -1, 0, 1);
                    const bakeGeo = new T3.PlaneGeometry(2, 2);
                    bakeScene.add(new T3.Mesh(bakeGeo, bakeMat));
                    bake = {
                        key: bakeKey,
                        rw: rw ?? null,
                        scene: bakeScene,
                        camera: bakeCam,
                        dispose() {
                            bakeMat.dispose();
                            bakeGeo.dispose();
                        },
                    };
                    sys._envBake = bake;
                }
                const prev = renderer.getRenderTarget?.();
                try {
                    renderer.setRenderTarget(target);
                    if (renderer.renderAsync) await renderer.renderAsync(bake.scene, bake.camera);
                    else renderer.render(bake.scene, bake.camera);
                } finally {
                    renderer.setRenderTarget(prev ?? null);
                }
                target.texture.userData = target.texture.userData || {};
                target.texture.userData._pmremPreInit = true;
                // Reused render-target textures need an explicit PMREM version
                // bump or rough materials keep sampling the first bake forever.
                target.texture.needsPMREMUpdate = true;
                // hand the now-rendered bake to the reflection hook's
                // below-horizon fallback (it boots on a 1x1 placeholder)
                if (sys._envFbNode) sys._envFbNode.value = target.texture;
                // EIDOVERSE PORT: in the offline host the sky owns the world's
                // light — assign the bake to scene.environment like the
                // pre-port core (the browser branch skips this because Chrome
                // suppresses Basic-family sky domes when it is set).
                // bopts.ifAbsent respects an agent-set HDRI; bopts.assign =
                // false opts out entirely (per-material assignment workflows).
                if (bopts.assign !== false && !(bopts.ifAbsent && scene.environment)) {
                    scene.environment = target.texture;
                    console.log(`[sky] env bake ${W}x${H} -> scene.environment (clouds reach reflections via env-IBL)`);
                } else {
                    console.log(`[sky] env bake ${W}x${H} ready for per-material reflection assignment`);
                }
                return target.texture;
            },
            update(t, camera) {
                const finiteT = Number.isFinite(t) ? t : 0;
                u.time.value = finiteT;
                if (sys._cloudTransition) {
                    const transition = sys._cloudTransition;
                    if (transition.t0 === null) transition.t0 = finiteT;
                    const raw = Math.max(0, Math.min(
                        1,
                        (finiteT - transition.t0) / transition.duration,
                    ));
                    const eased = raw * raw * (3 - 2 * raw);
                    applyCloudState(transition.from, transition.to, eased);
                    // Tint is a preset vector, while radiance also depends on
                    // the current TOD palette. Recompute instead of lerping a
                    // stale RGB captured before a time-of-day change.
                    updateWispColor();
                    cloudTransitionInfo.elapsedSeconds = Math.max(0, finiteT - transition.t0);
                    cloudTransitionInfo.rawProgress = raw;
                    cloudTransitionInfo.easedProgress = eased;
                    if (raw >= 1) {
                        state.preset = transition.toPreset;
                        cloudDome.visible = transition.toVisible;
                        sys._cloudTransition = null;
                        cloudTransitionInfo.active = false;
                        lightCacheDirty = !!lightCacheCompute;
                    }
                }
                if (camera) {
                    camera.updateMatrixWorld();
                    u.projInv.value.copy(camera.projectionMatrixInverse);
                    u.camWorld.value.copy(camera.matrixWorld);
                    bgDome.position.set(camera.position.x, 0, camera.position.z);
                    cloudDome.position.set(camera.position.x, 0, camera.position.z);
                }
            },
            dispose() {
                if (disposed) return;
                disposed = true;
                sys._cloudTransition = null;
                cloudTransitionInfo.active = false;
                for (const [material, roots] of cloudShadowRoots) {
                    if (material.colorNode !== roots.wrapped) continue;
                    material.colorNode = roots.original ?? null;
                    material.needsUpdate = true;
                }
                cloudShadowRoots.clear();
                scene.remove(bgDome, cloudDome);
                cloudDome.geometry.dispose();
                bgDome.geometry.dispose();
                cloudMat.dispose();
                bgMat.dispose();
                noiseTex.dispose();
                weatherTex.dispose();
                lightCacheTex?.dispose?.();
                lightCacheCompute?.dispose?.();
                sys._envTarget?.dispose?.();
                sys._envTarget = null;
                sys._envBake?.dispose();
                sys._envBake = null;
                sys._envRingworld = null;
            },
        };
        sys.setClouds(opts.clouds ?? 'cumulus');
        sys.setTime(opts.hours ?? 12);
        return sys;
    };
    console.log('[sky_system] makeSkySystem ready — world-space cloud dome + celestial layer (sun disc, NASA moon w/ phases, Tycho stars), TOD palette, cloud presets');
})();
