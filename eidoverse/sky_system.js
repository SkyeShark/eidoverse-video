// sky_system.js — WORLD-SPACE volumetric sky for eidoverse.
//
// Replaces the screenspace volumetric_clouds pipeline's weak spots:
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
// Cloud density/lighting math ported from effects_tsl/volumetric_clouds.js
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
        sin, cos, fract, floor, mix, clamp, smoothstep, dot, length,
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
        cumulus: { largeT: 0.42, largeA: 3.0, weatherT: 0.30, finalMul: 0.20, wScale: 1.0, dScale: 1.0, start: 700, height: 520, stretch: [1, 1, 1], lightK: 1.0 },
        stratus: { largeT: 0.12, largeA: 2.0, weatherT: 0.08, finalMul: 0.16, wScale: 0.55, dScale: 0.7, start: 520, height: 170, stretch: [1, 0.7, 1], lightK: 0.7 },
        cirrus:  { largeT: 0.30, largeA: 2.2, weatherT: 0.22, finalMul: 0.08, wScale: 1.6, dScale: 1.4, start: 2600, height: 300, stretch: [0.22, 1.6, 3.2], lightK: 0.0 },
        clear:   { largeT: 0.95, largeA: 1.0, weatherT: 0.95, finalMul: 0.00, wScale: 1.0, dScale: 1.0, start: 700, height: 520, stretch: [1, 1, 1], lightK: 0.0 },
    };

    globalThis.makeSkySystem = async function makeSkySystem({ scene, textures = {}, opts = {} } = {}) {
        const R_EARTH = opts.earthRadius ?? 6371000;
        const DOME_R = opts.domeRadius ?? 3200;
        const N_MARCH = opts.skySamples ?? 60;
        const N_LIGHT = opts.lightSamples ?? 20;

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
            starFade: uniform(0),
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
            cloudTint: uniform(V(1, 1, 1)),
            cloudDim: uniform(1),      // weather-system hook: dims cloud radiance without touching palette state
            wispColor: uniform(V(0.25, 0.25, 0.25)),
            wispOn: uniform(1),
            shaftK: uniform(opts.shafts ?? 0),
            shaftDen: uniform(opts.shaftDensity ?? 3e-5),
            precipK: uniform(0),   // world rain: curtain density under dense weather cells (weather-system hook)
            precipLo: uniform(0.95), precipHi: uniform(1.55),
            skyWind: uniform(V(0, 0, 10.3)), // ONE wind drives cloud drift, weather-cell motion, and (via weather system) rain shear
            wallCloud: uniform(new T3.Vector4(0, 0, 1, 0)), // (x, z, radius, strength): local cloud-base LOWERING (tornado wall cloud)
            fadeDist: uniform(opts.cloudFadeDist ?? 26000),
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
            return noiseNode.sample(i.add(sm).add(0.5).div(NSZ)).r;
        };
        const noise3 = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(float(3).sub(f.mul(2)));
            const uvx = i.x.add(float(37).mul(i.z)).add(sm.x);
            const uvy = i.y.add(float(17).mul(i.z)).add(sm.y);
            const t = noiseNode.sample(vec2(uvx, uvy).add(0.5).div(NSZ));
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
        // EROSION NOISE: true-3D ALU noise, NOT the texture-slice fbm3. The
        // slice noise's diagonal correlation lattice prints PARALLELOGRAM
        // PLATES through the density field wherever the march can't integrate
        // it away — bare in thin night cloud, and the long-parked daytime
        // "lines rolling over the clouds" share its geometry. fbm3A is the
        // same octave structure with an artifact-free lattice (wisp-proven).
        // opts.texSliceNoise = legacy path for A/B.
        const fbmE = opts.texSliceNoise ? fbm3 : fbm3A;

        // ---------------- cloud density (reference two-stage erosion, preset-driven) ----------------
        // weather is sampled RAW like the reference (uv in tile units: one .r tile
        // = 20 km, one .g tile = 5 km) but from the 1/f weather map above — raw
        // WHITE noise reproduced the reference's single heavy-deck look (42% of
        // samples saturate the (x-0.18)*5 gain) and its y-less texels extrude
        // into 520 m curtain columns. The 1/f field gives thresholds real
        // coverage control with distinct masses.
        const wSampleL = (uvNode) => weatherNode.sample(uvNode).r;
        const wSampleS = (uvNode) => weatherNode.sample(uvNode).g;
        const earthC = vec3(0, -R_EARTH, 0);
        const wallLower = (pIn) => {
            // wallCloud packing: (.x = world x, .y = world z, .z = radius, .w = strength)
            const wdx = pIn.x.sub(u.wallCloud.x), wdz = pIn.z.sub(u.wallCloud.y);
            const r2 = u.wallCloud.z.mul(u.wallCloud.z);
            return u.wallCloud.w.mul(exp(wdx.mul(wdx).add(wdz.mul(wdz)).div(r2).negate()));
        };
        const cloudsAt = (pIn) => {
            const p = pIn.mul(u.stretch);
            const atmoH = atmoHeight(pIn);
            const ch = atmoH.sub(u.cloudStart.sub(wallLower(pIn).mul(260))).div(u.cloudHeight).clamp(0, 1);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const largeWeather = clamp(wSampleL(vec2(p1.z, p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const weather2 = max(wSampleS(vec2(p2.z, p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = largeWeather.mul(weather2).mul(smoothstep(0.0, 0.5, ch)).mul(smoothstep(1.0, 0.5, ch));
            const shapeExp = float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch)));
            const cloudShape = pow(weather.max(1e-6), shapeExp);
            const p3 = p2.add(vec3(u.time.mul(12.3), 0, 0));
            const den1 = max(cloudShape.sub(fbmE(p3.mul(float(0.01).mul(u.dScale))).mul(0.7)), 0);
            const p4 = p3.add(vec3(0, u.time.mul(15.2), 0));
            const den2 = max(den1.sub(fbmE(p4.mul(float(0.05).mul(u.dScale))).mul(0.2)), 0);
            return { density: largeWeather.mul(u.finalMul).mul(min(den2.mul(5), 1)), ch };
        };
        // light-march density = reference "fast" path: full weather + first
        // erosion. The old crude blob approximation self-shadowed a DIFFERENT
        // cloud field than the camera march saw — blotchy interior shading.
        const cheapDensity = (pIn) => {
            const p = pIn.mul(u.stretch);
            const atmoH = atmoHeight(pIn);
            const ch = atmoH.sub(u.cloudStart).div(u.cloudHeight).clamp(0, 1);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const lw = clamp(wSampleL(vec2(p1.z, p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const w2 = max(wSampleS(vec2(p2.z, p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = lw.mul(w2).mul(smoothstep(0.0, 0.5, ch)).mul(smoothstep(1.0, 0.5, ch));
            const shape = pow(weather.max(1e-6), float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch))));
            const p3 = p2.add(vec3(u.time.mul(12.3), 0, 0));
            const den = max(shape.sub(fbmE(p3.mul(float(0.01).mul(u.dScale))).mul(0.7)), 0);
            return lw.mul(u.finalMul).mul(min(den.mul(5), 1));
        };
        // erosion-free density proxy for SHAFT occlusion: real beams are cast by
        // cloud MASSES, not 20-100 m erosion froth — sampling the eroded field
        // with few samples makes beam visibility flicker as the sun crosses
        // cloud detail (user-observed noisy godrays). Weather coverage × height
        // profile only → stable, mass-shaped beams.
        const smoothDensity = (pIn) => {
            const p = pIn.mul(u.stretch);
            const ch = atmoHeight(pIn).sub(u.cloudStart.sub(wallLower(pIn).mul(260))).div(u.cloudHeight).clamp(0, 1);
            const p1 = p.add(vec3(u.skyWind.x.mul(u.time), 0, u.skyWind.z.mul(u.time)));
            const lw = clamp(wSampleL(vec2(p1.z, p1.x).mul(float(-0.00005).mul(u.wScale))).sub(u.largeT).mul(u.largeA), 0, 2);
            const p2 = p1.add(vec3(u.skyWind.z.mul(u.time).mul(0.4), 0, u.skyWind.x.mul(u.time).mul(-0.4)));
            const w2 = max(wSampleS(vec2(p2.z, p2.x).mul(float(0.00005).mul(u.wScale)).add(vec2(0.37, 0.11))).sub(u.weatherT), 0).div(0.72);
            const weather = lw.mul(w2).mul(smoothstep(0.0, 0.5, ch)).mul(smoothstep(1.0, 0.5, ch));
            const shape = pow(weather.max(1e-6), float(0.3).add(float(1.5).mul(smoothstep(0.2, 0.5, ch))));
            return lw.mul(u.finalMul).mul(min(shape.mul(3.5), 1));
        };
        const phaseMie = (c) => {
            const p1 = c.add(0.8194068);
            return exp(c.mul(-65.0).sub(55.0)).mul(9.805233e-6)
                .add(exp(p1.mul(p1).mul(-83.70334)).mul(0.1388198))
                .add(exp(c.mul(7.810083)).mul(2.054747e-3))
                .add(exp(c.mul(-4.552125e-12)).mul(2.600563e-2));
        };
        const lightRay = (p, phaseF, dC, mu, ch, jitL) => {
            const stepL = clamp(u.cloudHeight.mul(2.2), 380, 700).div(N_LIGHT);
            const den = float(0).toVar();
            // white per-pixel base phase + golden-ratio per-pass steps:
            // quasi-uniform staircase-phase coverage so the 8-pass average
            // truly integrates the sun-occlusion staircase (structured or
            // purely stratified phases leave periodic residual bands near
            // the sun quadrant)
            const j0 = jitL ?? float(0.5);
            for (let j = 0; j < N_LIGHT; j++) den.addAssign(cheapDensity(p.add(u.cloudLightDir.mul(stepL).mul(j0.add(j)))));
            const scatter = mix(float(0.008), float(1.0), smoothstep(0.96, 0.0, mu));
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
        // faint seam lines along the whole 7.5-degree triangle grid
        // (Skye's annotated parallel sky lines). Uniform-matrix math is
        // bit-identical per pixel -> seams impossible by construction.
        const screenRayDir = () => {
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
        // opts.ringCurve (= ring radius): RINGWORLD mode — the ground curves UP
        // along ±z (the ring plane), so the deck's reference surface rises with
        // it: subtract a capped cylindrical rise z²/2R. Flat across the band (x).
        const RING_R = opts.ringCurve ?? 0;
        const RING_RISE_MAX = 820;
        const atmoHeight = (pIn) => {
            const base = pIn.y.mul(pIn.y.add(2 * R_EARTH)).add(pIn.x.mul(pIn.x)).add(pIn.z.mul(pIn.z))
                .div(length(vec3(pIn.x, pIn.y.add(R_EARTH), pIn.z)).add(R_EARTH));
            return RING_R ? base.sub(min(pIn.z.mul(pIn.z).div(2 * RING_R), RING_RISE_MAX)) : base;
        };

        // ---------------- CLOUD DOME material ----------------
        // body parameterized on (dir, org) so the env bake below can evaluate
        // the SAME sky from equirect directions (dome pass uses screen rays)
        const cloudBody = (dirIn, orgIn, passesIn) => {
            const dir = dirIn;
            const org = orgIn;
            // ring mode: the deck rises up to RING_RISE_MAX above the spherical
            // shell — widen the march ceiling so risen clouds aren't cut
            const sTop = u.cloudStart.add(u.cloudHeight).add(RING_R ? RING_RISE_MAX : 0);
            const t0 = shellFar(org, dir, u.cloudStart);
            // clamp the march to the pre-fade range: near the horizon the full
            // shell chord is 30-80 km but everything past fadeDist is faded out
            // anyway — clamping concentrates the samples where edges resolve
            const t1 = min(shellFar(org, dir, sTop), u.fadeDist.mul(1.1));
            const stepS = max(t1.sub(t0), 0).div(N_MARCH);
            const mu = dot(u.cloudLightDir, dir);
            const phaseF = phaseMie(mu);
            // interleaved gradient noise on PIXEL coords: the jitter must be
            // stable per screen pixel, not per world direction — a dir-hash
            // rerolls every frame under camera motion, and at density edges
            // that reroll flips marginal samples in/out (frame-to-frame edge
            // shimmer, user-diagnosed). IGN is deterministic per pixel.
            // (opts.dirJitter = legacy dir-hash path, kept for A/B shimmer tests)
            const jit = opts.dirJitter
                ? hash11(dot(dir, vec3(12.256, 2.646, 6.356)))
                : fract(float(52.9829189).mul(fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715)))));
            // STRATIFIED MULTI-PASS MARCH (offline anti-noise): one random offset
            // per pixel displaces the perceived cloud boundary by up to a full
            // step along the ray — under ANY motion, edge pixels flip at random
            // times instead of sweeping as a front (frame-to-frame edge noise,
            // user-diagnosed on playback; codec-level diffs hid it). Averaging
            // M marches at offsets fract(jit + k/M) interleaves the samples:
            // edge statistics of an M× finer march, and edges converge to true
            // partial coverage (anti-aliased) WITHIN each frame.
            const M_PASS = Math.max(1, passesIn ?? opts.cloudPasses ?? 8);
            const colSum = vec3(0).toVar();
            const trSum = float(0).toVar();
            If(dir.y.greaterThan(0.008).and(t0.lessThan(u.fadeDist)), () => {
                for (let k = 0; k < M_PASS; k++) {
                    const Trk = float(1).toVar();
                    const colk = vec3(0).toVar();
                    const jitK = fract(jit.add(k / M_PASS));
                    const p = org.add(dir.mul(t0)).add(dir.mul(stepS).mul(jitK)).toVar();
                    Loop({ start: 0, end: N_MARCH, type: 'int' }, () => {
                        If(Trk.lessThanEqual(0.008), () => Break());
                        const s = cloudsAt(p);
                        If(s.density.greaterThan(0.0), () => {
                            const intensity = lightRay(p, phaseF, s.density, mu, s.ch, fract(fract(jit.mul(73.1063)).add(k * 0.6180339887)));
                            const amb = u.cloudAmbSky.mul(float(0.5).add(s.ch.mul(0.6)))
                                .add(u.cloudAmbGround.mul(max(float(1).sub(s.ch.mul(2)), 0)));
                            const radiance = amb.add(u.cloudLightColor.mul(intensity)).mul(u.cloudDim).mul(s.density);
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
            // cheap high-wisp layer (reference: fbm at the outer-shell hit,
            // painted through remaining transmittance — thin high cirrus for free)
            const pC = org.add(dir.mul(shellFar(org, dir, sTop.add(1000))));
            const wispD = max(fbm3A(pC.mul(vec3(1, 1, 1.8)).mul(0.002)).sub(0.45), 0).mul(u.wispOn);
            col.addAssign(Tr.mul(u.wispColor).mul(wispD).mul(u.cloudDim));
            const wispA = min(wispD.mul(2.2), 0.85);
            // distance fade into horizon haze — no hard clamp band
            const distFade = smoothstep(u.fadeDist, u.fadeDist.mul(0.35), t0);
            const horizFade = smoothstep(0.008, 0.06, dir.y);
            const fade = distFade.mul(horizFade);
            // PREMULTIPLIED output: the Hillaire accumulator yields premultiplied
            // radiance. Standard alpha blending multiplies it by alpha AGAIN,
            // double-attenuating thin edge pixels into dark fringes — the material
            // uses premultipliedAlpha blending (ONE / OneMinusSrcAlpha), so the
            // fades must be folded into the color here as well.
            const cover = float(1).sub(Tr.mul(float(1).sub(wispA)));
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
                const hp = org.add(dir.mul(stepH).mul(jit.mul(0.5).add(0.3))).toVar();
                for (let i = 0; i < 20; i++) {
                    const hEnter = max(u.cloudStart.sub(atmoHeight(hp)), 0).div(sy);
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
                    const precip = u.precipK.mul(smoothstep(u.precipLo, u.precipHi, cellCov)).mul(colMod).mul(2.1e-4 * (1 - (i / 20) * 0.5))
                        .mul(smoothstep(u.cloudStart, u.cloudStart.mul(0.55), atmoHeight(hp)).mul(0.5).add(0.5));
                    const rho = u.shaftDen.mul(u.shaftK).mul(exp(atmoHeight(hp).div(-900))).add(precip);
                    shaft.addAssign(trH.mul(vis.mul(0.75).add(0.25)).mul(rho).mul(stepH));
                    trH.assign(trH.mul(exp(rho.mul(stepH).negate())));
                    hp.assign(hp.add(dir.mul(stepH)));
                }
            });
            // curtains scatter AMBIENT skylight too — sun-only lighting rendered
            // distant rain as a black wall at the horizon
            const shaftCol = u.cloudLightColor.mul(u.cloudDim).mul(phaseF.mul(0.7).add(0.055))
                .add(u.cloudAmbSky.mul(u.cloudDim).mul(2.4))
                .mul(shaft).mul(horizFade);
            // curtains genuinely occlude the sky behind them (haze density is
            // tiny so clear days are unaffected)
            const coverT = float(1).sub(float(1).sub(cover.mul(fade)).mul(trH));
            const dg2 = fract(jit.add(fract(u.time.mul(7.31)))).sub(0.5).mul(0.006);
            return vec4(col.mul(u.cloudTint).mul(fade).add(shaftCol).add(vec3(dg2, dg2, dg2)), coverT);
        };
        const cloudOut = Fn(() => cloudBody(screenRayDir(), cameraPosition));
        // keep sky surfaces OUT of the auto-enhance G-buffer (GTAO/SSR must not
        // treat dome normals as scene geometry)
        const noGBuffer = (m) => {
            if (T3.mrt && T3.vec4) m.mrtNode = T3.mrt({ normal: T3.vec4(0), metalrough: T3.vec4(0) });
            return m;
        };
        const cloudMat = noGBuffer(new T3.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, side: T3.BackSide, fog: false, premultipliedAlpha: true }));
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
                const hdri = hdriNode.sample(equirectUV(dir)).rgb;
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
                const st = starsNode.sample(equirectUV(dR)).rgb;
                let starTerm = st.mul(st).mul(u.starFade).mul(1.6);   // st² boosts contrast
                if (moonDisc) starTerm = starTerm.mul(float(1).sub(moonDisc));
                col.addAssign(starTerm);
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
                const albedo = moonNode.sample(muv).rgb;
                const nWorld = u.moonRight.mul(lx).add(u.moonUp.mul(ly)).add(u.moonDir.mul(nz.negate()));
                const lit = max(dot(nWorld, u.sunDir), 0.03);
                // day floor 0.5 (was 0.15): the moon/planet is a DAYTIME object
                // too — a giant companion world must read against the blue sky
                col.addAssign(albedo.mul(lit).mul(inDisc).mul(2.2).mul(u.moonLightK.mul(0.5).add(0.5)));
            }
            // HDR sun disc + corona
            const disc = smoothstep(0.99995, 0.999985, mu);
            col.addAssign(u.sunColor.mul(disc).mul(u.sunDiscI));
            col.addAssign(u.sunColor.mul(pow(max(mu, 0.0), 900.0)).mul(3.0));
            col.addAssign(u.sunColor.mul(pow(max(mu, 0.0), 60.0)).mul(0.22));
            // anti-banding output dither (8-bit readback quantization)
            const dg = fract(fract(float(52.9829189).mul(fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715))))).add(fract(u.time.mul(7.31)))).sub(0.5).mul(0.006);
            col.addAssign(vec3(dg, dg, dg));
            return vec4(col, 1);
        };
        const bgOut = Fn(() => bgBody(screenRayDir()));
        const bgMat = noGBuffer(new T3.MeshBasicNodeMaterial({ side: T3.BackSide, depthWrite: false, fog: false }));
        bgMat.colorNode = bgOut().rgb;
        const bgDome = new T3.Mesh(new T3.SphereGeometry(DOME_R, 48, 24), bgMat);
        bgDome.renderOrder = -100; bgDome.frustumCulled = false; bgDome.userData.noSupportCheck = true;
        scene.add(bgDome);

        // ---------------- JS state + API ----------------
        // azSpanK: fraction of π the sun sweeps in azimuth over the day (0.9 ≈
        // 162°, realistic). A fixed camera can't hold that — compress to ~0.35
        // (63°) with elMax ~32 to keep the disc in one frame all day (timelapse).
        const state = { hours: 12, azBase: opts.azimuth ?? 1.9, elMax: opts.maxElevationDeg ?? 62, azSpanK: opts.azSpanK ?? 0.9, preset: 'cumulus', palette: todAt(40) };
        const sys = {
            uniforms: u, state, domes: [bgDome, cloudDome],
            sunDir: V(0, 1, 0), moonDir: V(0, -1, 0),
            setSun(azRad, elRad) {
                sys.sunDir.set(Math.cos(elRad) * Math.cos(azRad), Math.sin(elRad), Math.cos(elRad) * Math.sin(azRad)).normalize();
                u.sunDir.value.copy(sys.sunDir);
                const elDeg = elRad * 180 / Math.PI;
                const pal = todAt(elDeg);
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
                // high wisps: sun-tinted, tracking daylight (reference vec3(3.0) × donor 0.08)
                const wisp = V(...pal.sun).lerp(V(1, 1, 1), 0.55).multiplyScalar(0.25 * (0.25 + pal.int * 0.3));
                u.wispColor.value.copy(wisp);
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
                state.preset = name;
                const p = { ...(PRESETS[name] || PRESETS.cumulus), ...over };
                u.largeT.value = p.largeT; u.largeA.value = p.largeA;
                u.weatherT.value = p.weatherT; u.finalMul.value = p.finalMul;
                u.wScale.value = p.wScale; u.dScale.value = p.dScale;
                u.cloudStart.value = p.start; u.cloudHeight.value = p.height;
                u.stretch.value.set(...p.stretch);
                u.lightK.value = p.lightK;
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
            // cloud-shadow factor for a world position (multiply into a
            // material's colorNode). strength 0..1; skips when sun below horizon.
            // 4-sample march of smoothDensity (the shaft-occlusion mass proxy)
            // along the light through the deck. Macro coverage (.r) alone is
            // useless here: its 20 km tile is ~constant across a scene-sized
            // patch and the threshold gate zeroes it — visible shadow patches
            // come from the .r × .g cell product, which smoothDensity carries.
            tslCloudShadow(pWorld, strength = 0.55) {
                const dy = max(u.cloudLightDir.y, 0.12);
                const hEnter = max(u.cloudStart.sub(pWorld.y), 0).div(dy);
                const segL = u.cloudHeight.div(dy);
                const dAt = (j) => smoothDensity(pWorld.add(u.cloudLightDir.mul(hEnter.add(segL.mul((j + 0.5) / 4)))));
                const od = dAt(0).add(dAt(1)).add(dAt(2)).add(dAt(3));
                const occ = float(1).sub(exp(od.mul(segL.div(4)).negate()));
                return float(1).sub(occ.mul(strength).mul(clamp(u.cloudLightDir.y.mul(4), 0, 1)));
            },
            // wrap scene materials with cloud shadowing (composes with other
            // colorNode wrappers, e.g. the weather system's wetness)
            wrapCloudShadows(sceneRoot, strength = 0.55) {
                const done = new Set();
                let n = 0;
                (sceneRoot || scene).traverse((o) => {
                    if (!o.isMesh || o.userData.noCloudShadow || o.userData.noWet) return;
                    if (sys.domes.includes(o)) return;
                    const mats = Array.isArray(o.material) ? o.material : [o.material];
                    for (const m of mats) {
                        if (!m || done.has(m) || !m.isNodeMaterial) continue;
                        done.add(m);
                        const baseCol = m.colorNode ?? T3.materialColor;
                        m.colorNode = baseCol.mul(sys.tslCloudShadow(T3.positionWorld, strength));
                        m.needsUpdate = true;
                        n++;
                    }
                });
                console.log('[sky] cloud shadows wrapped', n, 'materials');
                return n;
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
                return clamp(weatherNode.sample(uvW).r.sub(u.largeT).mul(u.largeA), 0, 2);
            },
            // MOVING per-pixel cloud reflections on metals — the volumetric_clouds
            // technique, verbatim contract: register the engine autoenhance hooks
            // (_autoEnhanceCloudReflectHook + blur). The hook raymarches THIS sky
            // field along each metal pixel's reflect direction every frame, so
            // reflections drift with the clouds; autoenhance composes it as an
            // SSR-gated fallback with AO + N·up gating and suppresses env-IBL on
            // opaques (no double-count). Call from setup() with the scene camera.
            enableReflections(camera, ropts = {}) {
                const reflHook = (colorIn, sceneDepth, sceneNormal, sceneMR) => {
                    if (ropts.debug === 'null') return Fn(() => vec4(0, 0, 0, 1))(); // bisect: constant, no samples
                    const depthTex = T3.convertToTexture(sceneDepth);
                    return Fn(() => {
                        const suv = T3.uv();
                        const sceneD = depthTex.sample(suv).r;
                        const isSurface = T3.step(sceneD, 0.9999);
                        const mr = sceneMR.sample(suv);
                        const metalness = mr.r;
                        const oneMinusR = float(1).sub(mr.g);
                        // PBR env weighting: metalness × (1-roughness)² (split-sum approx)
                        const reflectivity = metalness.mul(oneMinusR.mul(oneMinusR));
                        const gateMask = smoothstep(0.1, 0.4, metalness).mul(isSurface);
                        const viewPos = T3.getViewPosition(suv, sceneD, u.projInv);
                        const worldPos = u.camWorld.mul(vec4(viewPos, 1)).xyz;
                        const camPos = u.camWorld.mul(vec4(0, 0, 0, 1)).xyz;
                        const viewDir = normalize(worldPos.sub(camPos));
                        const viewNormal = sceneNormal.sample(suv);
                        const worldNormal = normalize(u.camWorld.mul(vec4(viewNormal.xyz, 0)).xyz);
                        const reflDir = T3.reflect(viewDir, worldNormal);
                        const reflRO = worldPos.add(worldNormal.mul(0.05));
                        const cloudCol = vec3(0).toVar();
                        If(gateMask.greaterThan(0.05), () => {
                            if (ropts.debug === 'flat') {         // bisect: no sky eval at all
                                cloudCol.assign(vec3(4, 0, 0).mul(reflectivity).mul(gateMask));
                            } else if (ropts.debug === 'nocloud') { // bisect: bg dome only
                                cloudCol.assign(bgBody(reflDir).rgb.mul(reflectivity).mul(gateMask));
                            } else {
                                // 1-pass march: denoise + roughness blur downstream
                                // clean the variance (multi-pass here would be waste)
                                const cld = cloudBody(reflDir, reflRO, 1);
                                const bg = bgBody(reflDir).rgb;
                                // RAY-based sky visibility, not normal-based: the sky
                                // is world-space now, so occlusion is the SSR hit
                                // along this same ray (roof paints over sky in the
                                // compose). All that's left to gate here is "does the
                                // ray point at sky at all" — down-rays fade to 0 and
                                // SSR/ground takes them. (Replaces the engine's N·up
                                // gate, which cut a hard terminator at normal.y = 0.)
                                const skyVis = smoothstep(-0.06, 0.06, reflDir.y);
                                // gain: dome output is display-calibrated (donor 0.08
                                // scale) but the compose stacks AO on top —
                                // uncompensated, mirror metal reads several times
                                // darker than the sky it reflects
                                cloudCol.assign(bg.mul(float(1).sub(cld.a)).add(cld.rgb)
                                    .mul(ropts.gain ?? 1.4)
                                    .mul(skyVis)
                                    .mul(reflectivity).mul(gateMask));
                            }
                        });
                        return vec4(cloudCol, 1);
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
                        // sharp→light→heavy by roughness²; re-gate by metalness so
                        // the sigma-8 halo can't bleed onto neighbouring dielectrics
                        const stage1 = mix(sharp, lightBlur.rgb, smoothstep(0.0, 0.25, r2));
                        const stage2 = mix(stage1, heavyBlur.rgb, smoothstep(0.25, 1.0, r2));
                        return vec4(stage2.mul(smoothstep(0.1, 0.4, mr.r)), 1.0);
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
                console.log('[sky] cloud-reflect hooks registered — per-pixel MOVING reflections on metals (SSR-gated autoenhance compose)');
            },
            // bake sky+clouds into an equirect env (→ scene.environment). The
            // domes are transparent, depthless, and G-buffer-excluded, so SSR
            // can NEVER hit them — env-IBL is how clouds reach reflections
            // (port of volumetric_clouds.bakeEnvEquirect). One-shot; re-call
            // after big TOD / weather changes.
            // OVERRIDE SEMANTICS: when the sky system is active it OWNS
            // scene.environment — the bake replaces any agent-chosen HDRI by
            // default (the sky IS the world's light). Interior scenes that
            // want their own HDRI while keeping the sky outside the windows
            // pass { ifAbsent: true } (bake skipped if an env already exists).
            // bopts.ringworld = { centerY, radius, halfWidth, map, mask,
            // repeat } traces the ringworld band analytically into the bake so
            // reflections/env-IBL carry the arc.
            async bakeEnv(renderer, bopts = {}) {
                if (bopts.ifAbsent && (scene.environment || scene.environmentNode)) {
                    console.log('[sky] env bake skipped (ifAbsent + existing environment)');
                    return scene.environment;
                }
                const W = bopts.width ?? 512, H = bopts.height ?? 256;
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
                if (!target || target.width !== W) {
                    target = new T3.RenderTarget(W, H, { type: T3.HalfFloatType, format: T3.RGBAFormat, depthBuffer: false, stencilBuffer: false });
                    target.texture.mapping = T3.EquirectangularReflectionMapping;
                    target.texture.minFilter = T3.LinearFilter; target.texture.magFilter = T3.LinearFilter;
                    target.texture.colorSpace = T3.LinearSRGBColorSpace;
                    target.texture.name = 'sky_system_env';
                    sys._envTarget = target;
                }
                const bakeMat = new T3.NodeMaterial();
                const rw = bopts.ringworld;
                bakeMat.fragmentNode = Fn(() => {
                    const suv = T3.uv();
                    const lon = suv.x.mul(Math.PI * 2).sub(Math.PI);
                    const lat = suv.y.sub(0.5).mul(Math.PI);
                    const cl = cos(lat);
                    const dir = normalize(vec3(cl.mul(sin(lon)), sin(lat), cl.mul(cos(lon))));
                    let bg = bgBody(dir).rgb;
                    if (rw && rw.map) {
                        // analytic ring: ray (from ~ground) vs the ring cylinder
                        // (axis X through (0, centerY, 0), radius R). We're
                        // inside → far root. Terrain sampled with the authored
                        // 8×1 tiling; landmask-black = water (dark, glossy-ish).
                        const oy = float(2 - rw.centerY);
                        const a = dir.y.mul(dir.y).add(dir.z.mul(dir.z)).max(1e-6);
                        const b = oy.mul(dir.y).mul(2);
                        const cq = oy.mul(oy).sub(rw.radius * rw.radius);
                        const disc = b.mul(b).sub(a.mul(cq).mul(4)).max(0);
                        const tHit = b.negate().add(sqrt(disc)).div(a.mul(2));
                        const hx = dir.x.mul(tHit);
                        const hy = oy.add(dir.y.mul(tHit)), hz = dir.z.mul(tHit);
                        const inBand = smoothstep(rw.halfWidth + 30, rw.halfWidth - 30, hx.abs());
                        const theta = atan2f(hz, hy.negate());          // 0 at the overhead crest
                        const uT = theta.div(Math.PI * 2).mul(rw.repeat ?? 8);
                        const vT = hx.div(rw.halfWidth * 2).add(0.5);
                        const land = texture(rw.map, vec2(uT, vT)).rgb;
                        const mraw = rw.mask ? texture(rw.mask, vec2(uT, float(1).sub(vT))).r : float(1);
                        const wk = smoothstep(0.55, 0.45, mraw);        // mask BLACK = water
                        const ringAlbedo = mix(land, vec3(0.03, 0.055, 0.07), wk);
                        // radial-inward normal lambert vs the sun + ambient
                        const nrm = normalize(vec3(0, hy.negate(), hz.negate()));
                        const lit = clamp(dot(nrm, u.sunDir), 0, 1).mul(0.75).add(0.3);
                        const ringCol = ringAlbedo.mul(lit).mul(u.cloudDim);
                        // haze out where the band dives to the horizon (huge t)
                        const hazeK = smoothstep(3.2, 1.2, tHit.div(rw.radius));
                        bg = mix(bg, ringCol, inBand.mul(hazeK));
                    }
                    const cld = cloudBody(dir, vec3(0, 2, 0));
                    // premultiplied cloud over sky; below the horizon fade to a
                    // ground-bounce tone so floor reflections aren't sky-bright
                    return vec4(bg.mul(float(1).sub(cld.a)).add(cld.rgb)
                        .mul(mix(float(1), float(0.45), smoothstep(0.0, -0.35, dir.y))), 1);
                })();
                const bakeScene = new T3.Scene();
                const bakeCam = new T3.OrthographicCamera(-1, 1, 1, -1, 0, 1);
                bakeScene.add(new T3.Mesh(new T3.PlaneGeometry(2, 2), bakeMat));
                const prev = renderer.getRenderTarget?.();
                renderer.setRenderTarget(target);
                if (renderer.renderAsync) await renderer.renderAsync(bakeScene, bakeCam);
                else renderer.render(bakeScene, bakeCam);
                renderer.setRenderTarget(prev ?? null);
                target.texture.userData = target.texture.userData || {};
                target.texture.userData._pmremPreInit = true;
                scene.environment = target.texture;
                console.log(`[sky] env bake ${W}x${H} -> scene.environment (clouds reach reflections via env-IBL)`);
                return target.texture;
            },
            update(t, camera) {
                u.time.value = t;
                if (camera) {
                    camera.updateMatrixWorld();
                    u.projInv.value.copy(camera.projectionMatrixInverse);
                    u.camWorld.value.copy(camera.matrixWorld);
                    bgDome.position.set(camera.position.x, 0, camera.position.z);
                    cloudDome.position.set(camera.position.x, 0, camera.position.z);
                }
            },
            dispose() { scene.remove(bgDome, cloudDome); },
        };
        sys.setClouds(opts.clouds ?? 'cumulus');
        sys.setTime(opts.hours ?? 12);
        return sys;
    };
    console.log('[sky_system] makeSkySystem ready — world-space cloud dome + celestial layer (sun disc, NASA moon w/ phases, Tycho stars), TOD palette, cloud presets');
})();
