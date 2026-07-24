// weather_system.js — weather layer composing with the eidoverse sky system
// (v2, redesigned after lookdev review of v1).
//
// Replaces the old screenspace rain pass the way sky_system replaced the
// old screenspace clouds. v2 fixes the three v1 sins:
//   · SKY COUPLING: weather greys/darkens the live TOD palette every frame
//     (storms stay stormy through a day cycle), authors visible cloud form via
//     cloudRadiance, and keeps rain/shafts/Ring response on cloudDim.
//   · WORLD-ANCHORED RAIN: streak positions are tiled in WORLD space around
//     the camera (mod-wrap), so the field stands still while the camera moves
//     through it; billboards use the camera-right uniform (no overhead flip).
//   · WATER-LOOK STREAKS: bright-core/soft-edge cross profile, sun-forward
//     glint (backlit rain lights up), per-state length/speed/tilt/dashing.
// Plus deterministic LIGHTNING (separated storm events with bounded
// return-stroke clusters, no runtime RNG).
//
//   eval sky_system.js first, then:
//   const weather = await makeWeatherSystem({ scene, sky });
//   weather.wrapScene();                  // wetness on existing materials
//   weather.setWeather('storm', 1.0);     // see WEATHER table below
//   // per frame: weather.update(t, camera)
//
// States: clear · drizzle · sunshower · fair · overcast · rain · storm
// (great-plains towering deck + lightning) · hurricane (sheared sheets of
// rain) · cyclone (sealed canopy sheet; 'noreaster' accepted as a legacy
// alias) · darkstorm (near-black green-cast sky, heavy lightning).
// Colored/alien rain: uniforms.rainColor + wetTint.
(function () {
    const T3 = globalThis.THREE;
    const {
        uniform, Fn, vec2, vec3, vec4, float, instanceIndex, positionLocal,
        uv, fract, floor, mix, clamp, smoothstep, dot, normalize, max, min,
        pow, abs, exp, sin, cos, length, cameraPosition, normalWorld, positionWorld,
        materialColor, materialRoughness, materialMetalness,
    } = T3;
    const atan2w = T3.atan2 || T3.atan;
    const V = (x, y, z) => new T3.Vector3(x, y, z);

    // Lightning color is selected from the event seed rather than runtime RNG.
    // A captured event therefore reproduces the same bolt, scene light,
    // rain response, cloud glow, impact color, and audit result on every load.
    const jsHash = (n) => {
        const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
        return x - Math.floor(x);
    };
    const LIGHTNING_STYLES = Object.freeze({
        white: Object.freeze({ hex: 0xf2f6ff }),
        blue: Object.freeze({ hex: 0x5d9dff }),
        purple: Object.freeze({ hex: 0xb26cff }),
        red: Object.freeze({ hex: 0xff4438 }),
        green: Object.freeze({ hex: 0x54ff8a }),
    });
    const LIGHTNING_PALETTES = Object.freeze({
        standard: Object.freeze([
            Object.freeze(['white', 0.52]),
            Object.freeze(['blue', 0.44]),
            Object.freeze(['purple', 0.04]),
        ]),
        darkstorm: Object.freeze([
            Object.freeze(['white', 0.40]),
            Object.freeze(['blue', 0.36]),
            Object.freeze(['purple', 0.16]),
            Object.freeze(['red', 0.04]),
            Object.freeze(['green', 0.04]),
        ]),
    });
    const lightningStyleKeyAt = (interval, paletteName = 'standard') => {
        const palette = LIGHTNING_PALETTES[paletteName] ?? LIGHTNING_PALETTES.standard;
        const sample = jsHash(interval * 23.17 + 91.3);
        let cumulative = 0;
        for (const [key, weight] of palette) {
            cumulative += weight;
            if (sample < cumulative) return key;
        }
        return palette.at(-1)[0];
    };
    // A lightning *event* is separated from the next event by seconds of real
    // storm darkness. The fast pulses inside one event are return strokes on
    // the same channel, not new strikes. Keeping these as pure deterministic
    // helpers makes cadence reproducible and directly auditable.
    const LIGHTNING_CADENCE = Object.freeze({
        standard: Object.freeze({
            referenceLevel: 0.30,
            minGapSeconds: 16,
            maxGapSeconds: 38,
            maxStrokes: 2,
            clusterThresholds: Object.freeze([0.72]),
            strokeGapMinSeconds: 0.085,
            strokeGapMaxSeconds: 0.19,
        }),
        darkstorm: Object.freeze({
            referenceLevel: 0.85,
            initialGapMinSeconds: 6,
            initialGapMaxSeconds: 9,
            minGapSeconds: 12,
            maxGapSeconds: 28,
            maxStrokes: 2,
            clusterThresholds: Object.freeze([0.68]),
            strokeGapMinSeconds: 0.075,
            strokeGapMaxSeconds: 0.17,
            firstLocalCandidateWithinEvents: 1,
            maxRemoteEventsBetweenLocalCandidates: 6,
        }),
    });
    const lightningCadenceFor = (paletteName = 'standard') => (
        LIGHTNING_CADENCE[paletteName] ?? LIGHTNING_CADENCE.standard
    );
    const lightningEventGapAt = (eventIndex, paletteName = 'standard', level = 1) => {
        const cadence = lightningCadenceFor(paletteName);
        const safeLevel = Math.max(0.01, Math.min(1, Number(level) || 0));
        // Less electrical weather stretches the same natural base range. It
        // can never make events closer than the authored minimum.
        const rarityScale = Math.max(
            1,
            Math.min(2.75, Math.sqrt(cadence.referenceLevel / safeLevel)),
        );
        const spread = cadence.maxGapSeconds - cadence.minGapSeconds;
        return (cadence.minGapSeconds
            + jsHash(eventIndex * 47.17 + 19.73) * spread) * rarityScale;
    };
    const lightningInitialEventGapAt = (eventIndex, paletteName = 'standard', level = 1) => {
        const cadence = lightningCadenceFor(paletteName);
        if (!Number.isFinite(cadence.initialGapMinSeconds)
            || !Number.isFinite(cadence.initialGapMaxSeconds)) {
            return lightningEventGapAt(eventIndex, paletteName, level);
        }
        return cadence.initialGapMinSeconds
            + jsHash(eventIndex * 53.71 + 41.9)
                * (cadence.initialGapMaxSeconds - cadence.initialGapMinSeconds);
    };
    const lightningStrokePlanAt = (eventIndex, paletteName = 'standard') => {
        const cadence = lightningCadenceFor(paletteName);
        const clusterSample = jsHash(eventIndex * 61.31 + 7.91);
        let count = 1;
        for (const threshold of cadence.clusterThresholds) {
            if (clusterSample >= threshold) count++;
        }
        count = Math.max(1, Math.min(cadence.maxStrokes, count));
        const offsets = [0];
        const amplitudes = [0.78 + jsHash(eventIndex * 67.9 + 5.3) * 0.22];
        for (let stroke = 1; stroke < count; stroke++) {
            const gapMix = jsHash(eventIndex * 71.7 + stroke * 13.1 + 11.9);
            offsets.push(offsets.at(-1)
                + cadence.strokeGapMinSeconds
                + gapMix * (cadence.strokeGapMaxSeconds - cadence.strokeGapMinSeconds));
            amplitudes.push(0.42 + jsHash(eventIndex * 73.3 + stroke * 17.7 + 3.1) * 0.38);
        }
        return {
            count,
            offsets,
            amplitudes,
            // Long enough for the channel afterglow envelope below to decay
            // fully; the scene flash itself is ~1e-9 by this point.
            durationSeconds: offsets.at(-1) + 0.85,
        };
    };
    const lightningFlashAt = (elapsedSeconds, plan) => {
        if (!plan || !Number.isFinite(elapsedSeconds) || elapsedSeconds < 0) return 0;
        let flash = 0;
        for (let stroke = 0; stroke < plan.count; stroke++) {
            const age = elapsedSeconds - plan.offsets[stroke];
            if (age < 0) continue;
            flash += Math.exp(-age * 25) * plan.amplitudes[stroke];
        }
        return Math.max(0, Math.min(1, Number.isFinite(flash) ? flash : 0));
    };
    // The visible bolt channel decays ~4x slower than the scene flash. At
    // exp(-25t) the ribbon lived ~0.12 s — under ten frames, subliminal. The
    // scene/sky illumination keeps the snappy envelope; only the incandescent
    // channel ribbon lingers (~0.5 s) like a real return-stroke afterimage.
    const lightningChannelAt = (elapsedSeconds, plan) => {
        if (!plan || !Number.isFinite(elapsedSeconds) || elapsedSeconds < 0) return 0;
        let glow = 0;
        for (let stroke = 0; stroke < plan.count; stroke++) {
            const age = elapsedSeconds - plan.offsets[stroke];
            if (age < 0) continue;
            glow += Math.exp(-age * 6.5) * plan.amplitudes[stroke];
        }
        return Math.max(0, Math.min(1, Number.isFinite(glow) ? glow : 0));
    };
    const lightningLocalCandidateAt = (
        eventIndex,
        chance,
        {
            paletteName = 'standard',
            entryEventCount = 0,
            remoteEventsSinceLocal = 0,
            hasLocalStrike = false,
        } = {},
    ) => {
        const randomCandidate = jsHash(eventIndex * 101.9 + 43.7)
            < Math.max(0, Math.min(1, chance));
        if (paletteName !== 'darkstorm') return randomCandidate;
        const cadence = LIGHTNING_CADENCE.darkstorm;
        const entryGuarantee = !hasLocalStrike
            && entryEventCount >= cadence.firstLocalCandidateWithinEvents;
        const remoteRunGuarantee = remoteEventsSinceLocal
            >= cadence.maxRemoteEventsBetweenLocalCandidates;
        return randomCandidate || entryGuarantee || remoteRunGuarantee;
    };
    globalThis.EANPA_LIGHTNING_PROFILE = Object.freeze({
        styles: LIGHTNING_STYLES,
        palettes: LIGHTNING_PALETTES,
        styleKeyAt: lightningStyleKeyAt,
        cadence: LIGHTNING_CADENCE,
        eventGapAt: lightningEventGapAt,
        initialEventGapAt: lightningInitialEventGapAt,
        strokePlanAt: lightningStrokePlanAt,
        flashAt: lightningFlashAt,
        localCandidateAt: lightningLocalCandidateAt,
    });

    //           clouds     overrides                                              sunDim grey dark greyTint           rain  wet  windK len  fall dash lightning
    const WEATHER = {
        clear:     { clouds: 'clear',   over: {},                                                 sunDim: 1.00, grey: 0.00, dark: 1.00, greyTint: [1, 1, 1],        rain: 0.00, wet: 0.00, windK: 0.0, len: 0.30, fall: 1.0, dash: 0.0, lightning: 0.00 },
        // High/2D clouds are authored with each weather state too.  They are
        // no longer one generic grey sheet sitting above otherwise-different
        // volumetric bodies: fair skies get sparse warm veils, stratiform
        // weather gets broad cool sheets, and severe storms get fast sheared
        // slate filaments.  All of these fields lerp with the volume below.
        drizzle:   { clouds: 'stratus', over: { largeT: 0.10, finalMul: 0.14, wispOn: 0.64, wispThreshold: 0.38, wispStrength: 0.68, wispOpacity: 0.88, wispFilament: 0.03, wispStretch: [0.82, 0.25, 1.28], wispTint: [0.76, 0.83, 0.92] }, sunDim: 0.70, grey: 0.35, dark: 0.88, greyTint: [1, 1, 1], rain: 0.45, wet: 0.40, windK: 0.3, len: 0.09, fall: 0.5, dash: 0.8, lightning: 0.00, horMul: 0.92, cellLo: 0.35, cellHi: 0.65 },
        sunshower: { clouds: 'cumulus', over: { largeT: 0.50, weatherT: 0.34, wispOn: 0.16, wispThreshold: 0.58, wispStrength: 0.42, wispOpacity: 1.10, wispFilament: 0.20, wispStretch: [0.70, 0.32, 1.72], wispTint: [1.04, 0.99, 0.91] }, sunDim: 0.92, grey: 0.05, dark: 1.00, greyTint: [1, 1, 1], rain: 0.45, wet: 0.55, windK: 0.5, len: 0.2, fall: 0.9, dash: 0.0, lightning: 0.00, cellLo: 0.85, cellHi: 1.25 },
        fair:      { clouds: 'cumulus', over: { largeT: 0.58, largeA: 3.2, weatherT: 0.26, finalMul: 0.24, wispOn: 0.13, wispThreshold: 0.62, wispStrength: 0.38, wispOpacity: 1.06, wispFilament: 0.18, wispStretch: [0.72, 0.33, 1.66], wispTint: [1.02, 0.99, 0.94] }, sunDim: 0.88, grey: 0.15, dark: 1.00, greyTint: [1, 1, 1], rain: 0.00, wet: 0.00, windK: 0.5, len: 0.3, fall: 1.0, dash: 0.0, lightning: 0.00 },
        overcast:  { clouds: 'stratus', over: { largeT: 0.05, finalMul: 0.20, wispOn: 0.90, wispThreshold: 0.30, wispStrength: 0.90, wispOpacity: 0.96, wispFilament: 0.05, wispStretch: [0.92, 0.24, 1.18], wispTint: [0.66, 0.74, 0.84] }, sunDim: 0.45, grey: 0.60, dark: 0.75, greyTint: [1, 1, 1], rain: 0.00, wet: 0.15, windK: 0.4, len: 0.3, fall: 1.0, dash: 0.0, lightning: 0.00, horMul: 0.85, cellLo: 0.5, cellHi: 0.9 },
        rain:      { clouds: 'stratus', over: { largeT: 0.02, finalMul: 0.26, height: 320, wispOn: 0.94, wispScale: 0.00092, wispThreshold: 0.27, wispStrength: 0.96, wispOpacity: 1.00, wispFilament: 0.12, wispStretch: [0.66, 0.22, 1.65], wispTint: [0.57, 0.66, 0.78] }, sunDim: 0.30, grey: 0.75, dark: 0.55, greyTint: [1, 1, 1], rain: 0.70, wet: 0.85, windK: 1.0, len: 0.22, fall: 1.0, dash: 0.0, lightning: 0.00, horMul: 0.75, cellLo: 0.5, cellHi: 0.85 },
        storm:     { clouds: 'cumulus', over: { largeT: 0.12, largeA: 4.0, finalMul: 0.34, start: 550, height: 950, wispOn: 0.52, wispScale: 0.00096, wispThreshold: 0.36, wispStrength: 0.88, wispOpacity: 1.05, wispFilament: 0.32, wispStretch: [0.40, 0.20, 2.18], wispTint: [0.53, 0.60, 0.70] }, sunDim: 0.18, grey: 0.80, dark: 0.42, greyTint: [1, 1, 1], rain: 1.00, wet: 1.00, windK: 2.2, len: 0.3, fall: 1.2, dash: 0.0, lightning: 0.30, lightningPalette: 'standard', localStrikeChance: 0.018, horMul: 0.6, cellLo: 1.0, cellHi: 1.45, distant: 0.5 },
        hurricane: { clouds: 'stratus', over: { largeT: 0.00, finalMul: 0.40, start: 380, height: 520, wispOn: 1.00, wispScale: 0.00108, wispThreshold: 0.24, wispStrength: 1.00, wispOpacity: 1.10, wispFilament: 0.30, wispStretch: [0.18, 0.16, 3.00], wispTint: [0.48, 0.57, 0.68] }, sunDim: 0.12, grey: 0.90, dark: 0.30, greyTint: [1, 1, 1], rain: 1.00, wet: 1.00, windK: 4.5, len: 0.45, fall: 1.4, dash: 0.0, lightning: 0.12, lightningPalette: 'standard', localStrikeChance: 0.012, horMul: 0.55, cellLo: 0.35, cellHi: 0.7, dense: 1.4, distant: 0.3 },
        // Cyclone's upper sheet uses moderate anisotropy: the old
        // [0.14, 0.15, 3.30] stretch drew 20:1 straight streaks instead of
        // wind-torn cloud masses.
        cyclone:   { clouds: 'stratus', over: { largeT: 0.00, largeA: 2.2, finalMul: 0.50, start: 240, height: 400, wispOn: 1.00, wispScale: 0.00100, wispThreshold: 0.22, wispStrength: 1.00, wispOpacity: 1.12, wispFilament: 0.22, wispStretch: [0.46, 0.24, 1.95], wispTint: [0.45, 0.56, 0.72] }, sunDim: 0.10, grey: 0.95, dark: 0.26, greyTint: [0.92, 0.97, 1.06], rain: 1.00, wet: 1.00, windK: 6.5, len: 0.60, fall: 1.6, dash: 0.0, lightning: 0.05, lightningPalette: 'standard', localStrikeChance: 0.010, horMul: 0.5, cellLo: 0.10, cellHi: 0.35, dense: 1.9, distant: 0.15 },
        // ~19.3 km cumulonimbus system represented by its only visible part:
        // a shallow sealed 3D underside plus a running ordinary volumetric
        // underlayer, with the dark-tinted canopy sheet as the textured cloud
        // ceiling visible in the gaps between the low masses. Direct
        // sun/celestial input reaches exact zero; low skylight and lightning
        // remain, and rain has its own full-coverage gate below the canopy.
        // Settled Dark Storm keeps the ordinary volumetric marcher running as
        // a dense hole-free underlayer beneath the sealed canopy: the canopy
        // blots out the sky while the 3D cumulus mass gives the underside its
        // visible layering (the look of the mid Nor'easter transition, before
        // clear holes open between the volume clouds).
        darkstorm: { clouds: 'cumulus', over: { largeT: 0.00, largeA: 2.2, weatherT: 0.00, finalMul: 0.34, start: 500, height: 650, lightCacheDirect: 0, wispOn: 1.00, wispScale: 0.00085, wispThreshold: 0.16, wispStrength: 0.95, wispOpacity: 1.05, wispFloor: 0.55, wispFilament: 0.14, wispStretch: [0.42, 0.26, 1.60], wispTint: [0.30, 0.33, 0.38], stormCanopy: 1.00 }, stormTopMeters: 19300, sunDim: 0.00, hemiDim: 0.12, celestialVisibility: 0.00, cloudRadiance: 0.14, grey: 0.97, dark: 0.14, greyTint: [0.90, 0.95, 1.00], rain: 1.00, wet: 1.00, windK: 1.6, len: 0.40, fall: 1.25, dash: 0.0, lightning: 0.85, lightningPalette: 'darkstorm', localStrikeChance: 0.16, horMul: 0.22, cellLo: 0.9, cellHi: 1.4, dense: 1.75, distant: 0.8 },
    };

    globalThis.makeWeatherSystem = async function makeWeatherSystem({ scene, sky, opts = {} } = {}) {
        // A scene may rebuild its sky/weather attachment while an older lazy
        // attachment is still alive. More than one scheduler means individually
        // natural 12--28 second events combine into apparent continuous flashing.
        // Enforce one owning weather system per scene and let dispose() restore
        // wrapped materials before the replacement attaches.
        const weatherRegistry = globalThis.__eanpaWeatherByScene
            ?? (globalThis.__eanpaWeatherByScene = new WeakMap());
        weatherRegistry.get(scene)?.dispose?.();
        const N_RAIN = opts.rainCount ?? 16000;
        const RAD = opts.rainRadius ?? 45;     // world tile half-extent (m)
        const HGT = opts.rainHeight ?? 24;     // vertical recycle height (m)
        const N_SPLASH = opts.splashCount ?? 1200;
        const GROUND_Y = opts.groundY ?? 0;
        const P = RAD * 2;

        const u = {
            time: uniform(0),
            camPos: uniform(V(0, 0, 0)),
            camRight: uniform(V(1, 0, 0)),
            camUp: uniform(V(0, 1, 0)),
            rainK: uniform(0),
            fallSpeed: uniform(opts.fallSpeed ?? 11),
            fallMul: uniform(1),
            windVec: uniform(V(0, 0, 0)),        // horizontal wind (m/s), state-driven
            // Integrated motion phases keep velocity changes continuous.
            // Multiplying absolute time by an interpolating speed makes
            // d(time*speed)/dt reverse when a storm weakens, which was the
            // visible upward/backward rain suction during weather morphs.
            fallPhase: uniform(0),
            windOffset: uniform(V(0, 0, 0)),
            streakLen: uniform(0.4),
            streakW: uniform(0.014),
            dashK: uniform(0),
            rainColor: uniform(V(0.72, 0.78, 0.86)),   // alien rains recolor this
            rainLight: uniform(1),
            wetness: uniform(0),
            wetTint: uniform(V(1, 1, 1)),
            puddleK: uniform(opts.puddles ?? 1),
            cellLo: uniform(0.9),
            cellHi: uniform(1.45),
            denseA: uniform(1),
        };

        // ---------------- world-space rain (instanced streaks) ----------------
        // deterministic: every streak's world position is a pure function of
        // (instanceIndex, time, wind) tiled around the camera — same frame in,
        // same pixels out, and the field does NOT translate with the camera.
        const hashI = (n, k) => {
            const q = fract(float(n).mul(0.1031).add(k * 0.61803));
            const q2 = q.mul(q.add(33.33));
            return fract(q2.mul(q2.add(q)));
        };
        // ALL weather quads stay OUT of the auto-enhance G-buffer: alpha-blended
        // billboards smear garbage normals/metalrough over their footprint and
        // GTAO/SSR stamp hard dark marks on them (the task-#18 smoke-square
        // lesson — rain rendered as brown chunks until this).
        const noGBuffer = (mat) => {
            if (T3.mrt && T3.vec4 && !globalThis.EANPA_NO_MRT) mat.mrtNode = T3.mrt({ normal: T3.vec4(0), metalrough: T3.vec4(0) });   // EANPA: forward path — mrt stamps compile to empty structs in Chrome
            return mat;
        };
        const rainGeo = new T3.PlaneGeometry(1, 1);
        rainGeo.translate(0, 0.5, 0);            // pivot at streak bottom
        const rainMat = noGBuffer(new T3.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, fog: false, side: T3.DoubleSide }));
        {
            const h1 = hashI(instanceIndex, 1), h2 = hashI(instanceIndex, 2), h3 = hashI(instanceIndex, 3), h4 = hashI(instanceIndex, 4);
            const fall = u.fallSpeed.mul(u.fallMul);
            // world-tiled coordinates: streak lives at hash*P + k*P (+ wind drift),
            // rendered in the tile containing the camera
            const wtX = u.windOffset.x;
            const wtZ = u.windOffset.z;
            const px = u.camPos.x.add(fract(h1.add(wtX.sub(u.camPos.x).div(P))).sub(0.5).mul(P));
            const pz = u.camPos.z.add(fract(h2.add(wtZ.sub(u.camPos.z).div(P))).sub(0.5).mul(P));
            const py = u.camPos.y.add(fract(h3.sub(u.fallPhase.div(HGT)).sub(u.camPos.y.div(HGT))).sub(0.35).mul(HGT));
            const base = vec3(px, py, pz);
            // streak axis = velocity direction (wind shear tilts it)
            const streakDir = normalize(vec3(u.windVec.x, fall.negate(), u.windVec.z));
            // distance shaping: fade the nearest ~2 m (no lens-sized blobs) and
            // thicken far streaks so they don't alias away — rain must read as
            // LAYERS in depth, not a handful of near strokes at the camera
            const dist = base.sub(cameraPosition).length();
            const nearFade = smoothstep(0.9, 2.6, dist);
            // A circular overlap feather replaces the finite square edge of
            // the camera-centred rain tile. Severe states can raise density
            // without revealing a rectangular falling-rain block.
            const fieldDistance = vec2(px.sub(u.camPos.x), pz.sub(u.camPos.z)).length();
            // GLSL/WGSL leave smoothstep undefined when edge0 >= edge1.
            // Express the inward feather as one-minus a conventional ramp so
            // every backend produces the same circular, block-free boundary.
            const fieldFade = float(1).sub(smoothstep(RAD * 0.70, RAD, fieldDistance));
            // real rain is a POPULATION: drop sizes span small drizzle to fat
            // streaks (h1 skewed small via square), widths follow loosely
            const lenI = u.streakLen.mul(h1.mul(h1).mul(1.1).add(0.45));
            // width follows length at the drop texture's 1:8 aspect
            const wThick = lenI.mul(0.125).mul(h2.mul(0.8).add(0.55)).mul(float(1).add(dist.mul(0.012)));
            const wp = base
                .add(u.camRight.mul(positionLocal.x.mul(wThick)))
                .add(streakDir.mul(positionLocal.y.mul(lenI)));
            rainMat.positionNode = wp;
            // WATER DROP texture (user-supplied): glassy teardrop with trailing
            // tail — alpha is the streak shape, RGB carries the glass highlights.
            // Drop head must sit at the FALLING end (uv.y=1 along streakDir).
            const dropTexN = opts.textures?.drop ? T3.texture(opts.textures.drop) : null;
            // the supplied drop texture is authored upside-down — rotate UVs 180°
            const texC = dropTexN ? dropTexN.sample(vec2(float(1).sub(uv().x), float(1).sub(uv().y))).level(0) : null;   // EANPA: explicit LOD
            const xProf = pow(max(float(1).sub(abs(uv().x.mul(2).sub(1))), 0), 1.6);
            const endFade = smoothstep(0.0, 0.18, uv().y)
                .mul(float(1).sub(smoothstep(0.72, 1.0, uv().y)));
            const shapeA = texC ? texC.a : xProf.mul(endFade);
            const viewDir = normalize(base.sub(cameraPosition));
            const stormRainCover = sky
                ? clamp(sky.uniforms.stormCanopy, 0, 1)
                : float(0);
            const rawSunGlint = sky
                ? pow(max(dot(viewDir, sky.uniforms.sunDir), 0), 6).mul(1.6).add(0.6)
                : float(1);
            // A sealed canopy has no direct sun glint. Lightning/TOD still
            // reaches the drops through the bounded rainLight uniform.
            const sunGlint = mix(rawSunGlint, float(1), stormRainCover);
            // WORLD gating: streaks only materialize where the weather map says
            // this cell is raining — walk out from under the cell and the rain
            // stops around you while the far curtains keep falling on the cells
            const ordinaryCellGate = sky
                ? smoothstep(u.cellLo, u.cellHi, sky.tslCoverage(vec2(px, pz)))
                : float(1);
            const stormCellGate = h4.mul(0.18).add(0.82);
            const cellGate = mix(ordinaryCellGate, stormCellGate, stormRainCover);
            const countGate = smoothstep(h1, h1.add(0.001), u.rainK);
            // texture ALPHA is the shape; RGB under transparent pixels is black
            // (premultiplied-style) and drags dark fringes in if multiplied —
            // color comes from the lit rainColor alone
            // per-drop brightness: catchlights vary drop to drop (big slow
            // drops flare, fine drizzle nearly vanishes) — h4 spans 0.5-1.5×
            rainMat.colorNode = u.rainColor.mul(u.rainLight).mul(sunGlint).mul(h4.add(0.5)).mul(1.08);
            const stormRainVisibility = sky
                ? clamp(sky.uniforms.stormCanopy, 0, 1).mul(clamp(u.rainK, 0, 1))
                : float(0);
            const stormOpacityBoost = mix(float(1), float(1.28), stormRainVisibility);
            rainMat.opacityNode = clamp(shapeA.mul(nearFade).mul(fieldFade).mul(cellGate)
                .mul(float(0.075).add(h3.mul(0.125)).mul(u.denseA))
                .mul(countGate).mul(clamp(u.rainK.mul(2), 0, 1))
                .mul(stormOpacityBoost), 0, 0.72);
        }
        const rainInst = new T3.InstancedMesh(rainGeo, rainMat, N_RAIN);
        rainInst.frustumCulled = false;
        rainInst.userData.noSupportCheck = true;
        rainInst.userData.noWet = true;
        rainInst.visible = false;
        scene.add(rainInst);

        // ---------------- ground splashes (the world-anchor cue) ----------------
        // expanding rings at ground level, tiled in world space like the streaks;
        // each instance cycles ring-out on its own hash phase. Flat-ground v1
        // (opts.groundY) — terrain scenes can disable via splashCount: 0.
        const SP = RAD;   // splash tile half-extent (tighter than rain)
        const splashGeo = new T3.PlaneGeometry(1, 1);
        splashGeo.rotateX(-Math.PI / 2);
        const splashMat = noGBuffer(new T3.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, fog: false }));
        {
            const s1 = hashI(instanceIndex, 11), s2 = hashI(instanceIndex, 12), s3 = hashI(instanceIndex, 13);
            const px = u.camPos.x.add(fract(s1.sub(u.camPos.x.div(SP * 2))).sub(0.5).mul(SP * 2));
            const pz = u.camPos.z.add(fract(s2.sub(u.camPos.z.div(SP * 2))).sub(0.5).mul(SP * 2));
            const phase = fract(s3.mul(9.7).add(u.time.mul(2.4)));
            const ringR = phase.mul(0.13).add(0.015);
            splashMat.positionNode = vec3(px, GROUND_Y + 0.015, pz)
                .add(positionLocal.mul(vec3(ringR.mul(2), 1, ringR.mul(2))));
            const rr = uv().sub(0.5).length().mul(2);
            const ring = smoothstep(0.55, 0.8, rr)
                .mul(float(1).sub(smoothstep(0.85, 1.0, rr)));
            const ordinaryCellGateS = sky
                ? smoothstep(u.cellLo, u.cellHi, sky.tslCoverage(vec2(px, pz)))
                : float(1);
            const stormSplashCover = sky
                ? clamp(sky.uniforms.stormCanopy, 0, 1)
                : float(0);
            const stormCellGateS = s3.mul(0.18).add(0.82);
            const cellGateS = mix(
                ordinaryCellGateS, stormCellGateS, stormSplashCover,
            );
            const countGate = smoothstep(s1, s1.add(0.001), u.rainK);
            const fieldDistance = vec2(px.sub(u.camPos.x), pz.sub(u.camPos.z)).length();
            const fieldFade = float(1).sub(smoothstep(SP * 0.70, SP, fieldDistance));
            splashMat.colorNode = u.rainColor.mul(1.15);
            splashMat.opacityNode = ring.mul(float(1).sub(phase)).mul(0.30).mul(fieldFade).mul(cellGateS).mul(countGate).mul(clamp(u.rainK.mul(2), 0, 1));
        }
        const splashInst = new T3.InstancedMesh(splashGeo, splashMat, N_SPLASH);
        splashInst.frustumCulled = false;
        splashInst.userData.noSupportCheck = true;
        splashInst.userData.noWet = true;
        splashInst.visible = false;
        scene.add(splashInst);

        // ---------------- lightning (deterministic schedule + visible bolt) ----------------
        // A finite local flash must illuminate without turning wet dielectric
        // terrain into a clipped white sheet. The sky-volume flash remains
        // separately visible over distance.
        const LIGHTNING_LIGHT_PEAK = 12000;
        const LIGHTNING_LIGHT_RANGE = 900;
        const LOCAL_STRIKE_COOLDOWN = 45;
        const LOCAL_STRIKE_PLAYER_GUARD = 28;
        // The first Dark Storm event is deliberately framed in front of the
        // player: outside the safety guard, but near enough that its endpoint,
        // impact volume, and scorch can actually be inspected.
        const FORCED_LOCAL_STRIKE_MIN_RADIUS = 34;
        const FORCED_LOCAL_STRIKE_MAX_RADIUS = 58;
        const LOCAL_STRIKE_SURFACE_DAMAGE_RADIUS = 4.5;
        const IMPACT_POOL_SIZE = 2;
        const IMPACT_SPARK_COUNT = Math.max(24, Math.min(64, Math.round(N_RAIN / 250)));
        const IMPACT_PUFF_COUNT = Math.max(8, Math.min(16, Math.round(N_RAIN / 850)));
        const SCORCH_POOL_SIZE = 4;
        const SCORCH_LIFETIME = 90;
        const activeStrikeColor = new T3.Color(LIGHTNING_STYLES.white.hex);
        let activeStrikeKey = 'white';
        const bolt = new T3.PointLight(
            LIGHTNING_STYLES.white.hex, 0, LIGHTNING_LIGHT_RANGE, 2,
        );
        bolt.name = 'weather_lightning_scene_light';
        bolt.castShadow = false;
        // Keep the light in the WebGPU light topology for the weather system's
        // complete lifetime. A strike changes uniform data only.
        bolt.visible = true;
        bolt.userData.noSupportCheck = true;
        bolt.userData.noWet = true;
        scene.add(bolt);
        // Visible strike: jagged camera-facing ribbon, rebuilt once per event
        // from its seed; return strokes reuse that physical channel.
        const boltK = uniform(0);
        // Channel afterglow envelope: drives ONLY the ribbon's color/opacity.
        // Scene light, sky radiance, and terrain flash stay on boltK.
        const boltChannelK = uniform(0);
        const boltColor = uniform(V(
            activeStrikeColor.r, activeStrikeColor.g, activeStrikeColor.b,
        ));
        const boltMat = noGBuffer(new T3.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, fog: false,
            blending: T3.AdditiveBlending, side: T3.DoubleSide,
        }));
        {
            const prof = max(float(1).sub(abs(uv().x.mul(2).sub(1))), 0);
            const core = pow(prof, 6).mul(1.3).add(pow(prof, 1.6).mul(0.42)); // white-hot core + wide glow in one ribbon
            const cloudFade = smoothstep(0.0, 0.14, uv().y); // top dissolves INTO the deck
            const boltTexN = opts.textures?.bolt ? T3.texture(opts.textures.bolt) : null;
            // trace_06.png alpha dies to zero at both v ends (lens-shaped
            // streak): sampled 0..1 it erased the bottom ~10% of the channel,
            // so bolts visibly stopped ~50 m above their own impact point.
            // Sample only the dense 0.28-0.72 band; the ribbon's own core
            // profile and cloudFade handle the shaping at the ends.
            const texA = boltTexN
                ? boltTexN.sample(vec2(uv().x, uv().y.mul(0.44).add(0.28))).level(0).a
                : float(1);   // EANPA: explicit LOD
            // The narrow core can run hot without erasing the selected hue in
            // the wider channel and glow. Every other lightning consumer uses
            // this same linear color uniform.
            const coreTint = mix(boltColor, vec3(1, 1, 1), pow(prof, 10).mul(0.34));
            boltMat.colorNode = coreTint.mul(boltChannelK.mul(26));
            boltMat.opacityNode = core.mul(texA).mul(cloudFade).mul(clamp(boltChannelK.mul(3), 0, 1));
        }
        const boltGeo = new T3.BufferGeometry();
        // A strike changes the ribbon's contents, not its topology budget. The
        // old implementation replaced position/uv/index BufferAttributes on
        // every bolt. Three's WebGPU geometry-dispose listener only sees the
        // attributes that are still attached at final disposal, so every
        // superseded attribute could leave its GPU buffer behind. Keep one
        // bounded dynamic allocation for the lifetime of the weather system.
        // Maximum topology: 89-point fractal trunk (12 anchors, three
        // midpoint-displacement passes) + four 5-point branches + four
        // 3-point sub-branches = 242 ribbon vertices / 672 indices, budgeted
        // with headroom.
        const BOLT_MAX_VERTICES = 256;
        const BOLT_MAX_INDICES = 768;
        const boltPositionAttribute = new T3.BufferAttribute(new Float32Array(BOLT_MAX_VERTICES * 3), 3);
        const boltUvAttribute = new T3.BufferAttribute(new Float32Array(BOLT_MAX_VERTICES * 2), 2);
        const boltIndexAttribute = new T3.BufferAttribute(new Uint16Array(BOLT_MAX_INDICES), 1);
        boltPositionAttribute.setUsage(T3.DynamicDrawUsage);
        boltUvAttribute.setUsage(T3.DynamicDrawUsage);
        boltIndexAttribute.setUsage(T3.DynamicDrawUsage);
        boltGeo.setAttribute('position', boltPositionAttribute);
        boltGeo.setAttribute('uv', boltUvAttribute);
        boltGeo.setIndex(boltIndexAttribute);
        boltGeo.setDrawRange(0, 0);
        const boltMesh = new T3.Mesh(boltGeo, boltMat);
        boltMesh.frustumCulled = false; boltMesh.visible = false;
        boltMesh.userData.noSupportCheck = true; boltMesh.userData.noWet = true;
        scene.add(boltMesh);
        let lightningEventIndex = 0;
        let lightningEventStart = -Infinity;
        let lightningEventSeed = -1;
        let lightningEventPlan = null;
        let lightningSheetScale = 0;
        let lightningCadenceKey = 'none';
        let nextLightningEventAt = null;
        let lastLightningScheduleT = null;
        let darkstormEntryEventCount = 0;
        let remoteEventsSinceLocalStrike = 0;
        let darkstormHasLocalStrike = false;
        const clearLightningSchedule = () => {
            lightningEventStart = -Infinity;
            lightningEventSeed = -1;
            lightningEventPlan = null;
            lightningSheetScale = 0;
            lightningCadenceKey = 'none';
            nextLightningEventAt = null;
            lastLightningScheduleT = null;
            darkstormEntryEventCount = 0;
            remoteEventsSinceLocalStrike = 0;
            darkstormHasLocalStrike = false;
        };
        const rebuildBolt = (I, camera, gx, gz, bottomY = 2) => {
            const rng = (i) => jsHash(I * 131.7 + i * 17.3);
            // start slightly INSIDE the deck — bolts come from the clouds
            const topY = (sky ? sky.uniforms.cloudStart.value : 500) * 1.04;
            const pos = [], uvs = [], idx = [];
            const addRibbon = (pts, w0, w1) => {
                const b0 = pos.length / 3;
                const toCam = V(camera.position.x - gx, 0, camera.position.z - gz).normalize();
                for (let i = 0; i < pts.length; i++) {
                    const t = i / (pts.length - 1);
                    const dirSeg = (i < pts.length - 1)
                        ? V(...pts[i + 1]).sub(V(...pts[i])).normalize()
                        : V(...pts[i]).sub(V(...pts[i - 1])).normalize();
                    const right = dirSeg.clone().cross(toCam).normalize();
                    const w = (w0 + (w1 - w0) * t) / 2;
                    const p = pts[i];
                    pos.push(p[0] - right.x * w, p[1] - right.y * w, p[2] - right.z * w);
                    pos.push(p[0] + right.x * w, p[1] + right.y * w, p[2] + right.z * w);
                    uvs.push(0, t, 1, t);
                    if (i > 0) {
                        const a = b0 + (i - 1) * 2;
                        idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
                    }
                }
            };
            // main channel: multi-scale fractal trunk. A single random walk
            // has one feature size, and its straight inter-point segments read
            // as a laser at close range. Coarse anchors set the overall drift;
            // three midpoint-displacement passes then kink every segment at
            // half the previous scale — organic direction changes from ~60 m
            // wander down to ~3 m jitter, with both endpoints preserved so the
            // channel still leaves the deck and lands exactly on the impact.
            let trunk = [];
            const N0 = 12;
            let x = gx + (rng(2) - 0.5) * 70, z = gz + (rng(4) - 0.5) * 70;
            for (let i = 0; i < N0; i++) {
                const t = i / (N0 - 1);
                const y = topY * (1 - t) + bottomY * t;
                if (i > 0) {
                    const amp = 34 * (1 - t * 0.35);
                    x += (rng(10 + i) - 0.5) * amp + (gx - x) * 0.22;
                    z += (rng(30 + i) - 0.5) * amp + (gz - z) * 0.22;
                }
                if (i === N0 - 1) { x = gx; z = gz; }
                trunk.push([x, y, z]);
            }
            let displacementSeed = 500;
            for (let level = 0; level < 3; level++) {
                const refined = [trunk[0]];
                for (let i = 1; i < trunk.length; i++) {
                    const a = trunk[i - 1], b = trunk[i];
                    const span = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
                    const kink = span * 0.16;
                    refined.push([
                        (a[0] + b[0]) / 2 + (rng(displacementSeed + i * 3) - 0.5) * 2 * kink,
                        (a[1] + b[1]) / 2 + (rng(displacementSeed + i * 3 + 1) - 0.5) * 0.6 * kink,
                        (a[2] + b[2]) / 2 + (rng(displacementSeed + i * 3 + 2) - 0.5) * 2 * kink,
                    ], b);
                }
                trunk = refined;
                displacementSeed += 137;
            }
            const spine = trunk;
            addRibbon(spine, 3.6, 1.3);
            // recursive branching: forks off the trunk, sub-forks off forks
            const branchFrom = (parent, seed, w0, depth) => {
                const k = 3 + Math.floor(rng(seed) * (parent.length - 6));
                const bp = [];
                let bx = parent[k][0], bz = parent[k][2];
                const n = 7 - depth * 2;
                for (let i = 0; i < n; i++) {
                    const t = i / (n - 1);
                    bp.push([bx, parent[k][1] * (1 - t * (0.45 + rng(seed + 1) * 0.25)), bz]);
                    bx += (rng(seed + 10 + i) - 0.25) * 30; bz += (rng(seed + 40 + i) - 0.5) * 30;
                }
                addRibbon(bp, w0, w0 * 0.2);
                if (depth < 2 && rng(seed + 5) > 0.4) branchFrom(bp, seed * 3 + 7, w0 * 0.5, depth + 1);
            };
            const nBranch = 2 + Math.floor(rng(50) * 3);
            for (let b = 0; b < nBranch; b++) branchFrom(spine, 60 + b * 23, 1.5, 1);
            if (pos.length > boltPositionAttribute.array.length
                || uvs.length > boltUvAttribute.array.length
                || idx.length > boltIndexAttribute.array.length) {
                throw new Error(`[weather] bolt topology exceeded its fixed buffer budget (${pos.length / 3}v/${idx.length}i)`);
            }
            boltPositionAttribute.array.fill(0);
            boltUvAttribute.array.fill(0);
            boltIndexAttribute.array.fill(0);
            boltPositionAttribute.array.set(pos);
            boltUvAttribute.array.set(uvs);
            boltIndexAttribute.array.set(idx);
            boltPositionAttribute.needsUpdate = true;
            boltUvAttribute.needsUpdate = true;
            boltIndexAttribute.needsUpdate = true;
            boltGeo.setDrawRange(0, idx.length);
            boltGeo.computeBoundingSphere();
            return { gx, gz, bottomY };
        };

        // ---------------- pooled local lightning impact ----------------
        // No geometry, material, particle, decal, or light is allocated by a
        // strike. Two short effect slots and four long-lived scorch slots are
        // built once, oldest-recycled, then disposed with the weather system.
        const impactSparkGeometry = new T3.OctahedronGeometry(1, 0);
        // A crossed/billboard plane is not a volumetric impact. A small pooled
        // low-poly sphere keeps the puff readable from every view direction
        // without allocating anything when a strike occurs.
        const impactPuffGeometry = new T3.IcosahedronGeometry(1, 1);
        const scorchGeometry = new T3.CircleGeometry(1, 32);
        const impactObjects = [];
        const makeImpactSlot = (slotIndex) => {
            const sparkAlpha = uniform(0);
            const sparkColor = uniform(V(1, 1, 1));
            const sparkMaterial = noGBuffer(new T3.MeshBasicNodeMaterial({
                transparent: true,
                depthWrite: false,
                depthTest: true,
                fog: true,
                blending: T3.AdditiveBlending,
            }));
            sparkMaterial.colorNode = sparkColor.mul(sparkAlpha.mul(9.0));
            sparkMaterial.opacityNode = sparkAlpha;
            const sparks = new T3.InstancedMesh(
                impactSparkGeometry, sparkMaterial, IMPACT_SPARK_COUNT,
            );
            sparks.name = `weather_lightning_impact_sparks_${slotIndex}`;
            sparks.visible = false;
            sparks.frustumCulled = false;
            sparks.userData.noSupportCheck = true;
            sparks.userData.noWet = true;

            const puffAlpha = uniform(0);
            const puffColor = uniform(V(0.12, 0.14, 0.17));
            const puffGlowColor = uniform(V(1, 1, 1));
            const puffGlowK = uniform(0);
            const puffAge = uniform(0);
            const puffAge01 = uniform(0);
            const puffMaterial = noGBuffer(new T3.MeshBasicNodeMaterial({
                transparent: true,
                depthWrite: false,
                depthTest: true,
                fog: true,
            }));
            // Soft optical-thickness proxy for the 3D puff: front-facing
            // normals are dense, grazing normals fade to zero. A UV radial
            // mask on an icosphere would expose seams and painted patches.
            // The uniform proxy alone read as a smooth balloon: a per-instance
            // drifting lump field ruffles the silhouette and interior, an
            // age-driven dissolve breaks the cloud apart as it fades, and the
            // strike color glows from the dense core for the first half
            // second — a burn puff, not a grey sphere.
            // Gyroid-FBM explosion body (user-supplied reference shader,
            // recolored for lightning). abs(gyroid) FBM with z-feedback gives
            // billowing turbulent structure; its finite-difference normal
            // top-lights the smoke; power curves drive growth (fast then
            // slowing), burn (ember core dying quickly into soot), and fade
            // (hold, then die). Internal motion is a slow scroll through the
            // fixed field — churn without swirling interference bands.
            const puffGyroid = (p) => dot(cos(p), sin(vec3(p.y, p.z, p.x)));
            // The whole body lives inside ONE Fn() so toVar() emits real WGSL
            // temporaries. A functional unroll without variables inlined the
            // feedback chain as text and the shader grew multiplicatively per
            // octave — megabytes of WGSL, 30 s pipeline compiles, device
            // losses, and an impact puff that never rendered at all.
            const puffFbm = (pIn) => {
                const p = vec3(pIn).toVar();
                const result = float(0).toVar();
                let amp = 0.5;
                for (let octave = 0; octave < 6; octave++) {
                    p.assign(vec3(p.x, p.y, p.z.add(result.mul(0.1))));
                    result.addAssign(abs(puffGyroid(p.div(amp)).mul(amp)));
                    amp /= 1.7;
                }
                return result;
            };
            const puffRgba = Fn(() => {
                const puffSeed = fract(
                    float(instanceIndex).mul(0.6180339887).add(0.317),
                ).toVar();
                const puffLp = vec3(positionLocal).toVar();
                // staggered per-instance timeline on the shared slot clock
                const puffT = clamp(
                    puffAge01.mul(1.1).sub(puffSeed.mul(0.10)), 0, 1,
                ).toVar();
                const puffGrowth = pow(puffT, 0.2);
                const puffFade = float(1).sub(pow(puffT, 7.0));
                const puffBurn = float(1).sub(pow(puffT, 0.4));
                const puffScroll = pow(puffT, 0.4).mul(1.1)
                    .add(puffSeed.mul(196.128));
                const puffP = puffLp.mul(2.2)
                    .add(vec3(0, 0, puffScroll))
                    .add(puffSeed.mul(17.3)).toVar();
                const puffNoise = puffFbm(puffP).toVar();
                const puffNx = puffFbm(puffP.add(vec3(0.15, 0, 0))).toVar();
                const puffNy = puffFbm(puffP.add(vec3(0, 0.15, 0))).toVar();
                const puffNormal = normalize(vec3(
                    puffNoise.sub(puffNx),
                    puffNoise.sub(puffNy),
                    puffNoise.sub(1),
                )).toVar();
                const puffShade = puffNormal.y.mul(0.5).add(0.5).toVar();
                const puffSmoke = puffNoise.sub(puffBurn.mul(2.6)).toVar();
                // ember: white-hot lightning-tinted core while burn is high
                const puffEmber = mix(vec3(1.0, 1.0, 1.0), puffGlowColor, 0.55)
                    .mul(4.6)
                    .mul(float(0.75).add(puffShade.mul(0.45)))
                    .mul(float(1).add(puffGlowK.mul(0.5)));
                const puffSmokeGrey = clamp(puffSmoke.mul(puffShade), 0, 1.6);
                const puffSmokeCol = puffColor.mul(puffSmokeGrey.mul(1.2).add(0.15))
                    // rising smoke stays faintly lit by the strike afterglow
                    // instead of vanishing dark-on-dark under the sealed sky
                    .add(puffGlowColor.mul(puffGlowK).mul(0.35));
                const puffCol = mix(
                    puffEmber, puffSmokeCol, smoothstep(0.0, 0.1, puffSmoke),
                );
                // ragged expanding silhouette: noise-modulated radius
                const puffRadius = puffNoise.mul(puffGrowth).mul(0.5);
                const puffShape = float(1).sub(smoothstep(
                    0.0, 0.05, length(puffLp.xy).sub(puffRadius),
                ));
                const puffA = puffShape
                    .mul(puffFade)
                    .mul(float(0.82).add(puffSeed.mul(0.3)))
                    .mul(puffAlpha);
                return vec4(puffCol, puffA);
            })();
            puffMaterial.colorNode = puffRgba.rgb;
            puffMaterial.opacityNode = puffRgba.a;
            const puffs = new T3.InstancedMesh(
                impactPuffGeometry, puffMaterial, IMPACT_PUFF_COUNT,
            );
            puffs.name = `weather_lightning_impact_puff_${slotIndex}`;
            puffs.visible = false;
            puffs.frustumCulled = false;
            puffs.userData.noSupportCheck = true;
            puffs.userData.noWet = true;

            scene.add(sparks, puffs);
            impactObjects.push(sparks, puffs);
            return {
                active: false,
                birth: -Infinity,
                interval: -1,
                origin: V(0, -999, 0),
                normal: V(0, 1, 0),
                color: new T3.Color(LIGHTNING_STYLES.white.hex),
                sparks,
                puffs,
                sparkMaterial,
                puffMaterial,
                sparkAlpha,
                sparkColor,
                puffAlpha,
                puffColor,
                puffGlowColor,
                puffGlowK,
                puffAge,
                puffAge01,
                sparkVelocity: Array.from({ length: IMPACT_SPARK_COUNT }, () => V(0, 0, 0)),
                sparkLength: new Float32Array(IMPACT_SPARK_COUNT),
                puffOffset: Array.from({ length: IMPACT_PUFF_COUNT }, () => V(0, 0, 0)),
                puffDrift: Array.from({ length: IMPACT_PUFF_COUNT }, () => V(0, 0, 0)),
                puffSize: new Float32Array(IMPACT_PUFF_COUNT),
            };
        };
        const impactSlots = Array.from(
            { length: IMPACT_POOL_SIZE }, (_, index) => makeImpactSlot(index),
        );

        const makeScorchSlot = (slotIndex) => {
            const alpha = uniform(0);
            const color = uniform(V(0.025, 0.016, 0.010));
            const material = noGBuffer(new T3.MeshBasicNodeMaterial({
                transparent: true,
                depthWrite: false,
                depthTest: true,
                fog: true,
                side: T3.DoubleSide,
                polygonOffset: true,
                polygonOffsetFactor: -2,
                polygonOffsetUnits: -2,
            }));
            const scorchUv = uv().sub(0.5);
            const radius = scorchUv.length().mul(2);
            const angle = atan2w(scorchUv.y, scorchUv.x);
            const brokenEdge = sin(angle.mul(5).add(1.7)).mul(0.075)
                .add(sin(angle.mul(11).sub(0.8)).mul(0.038));
            const edgeRadius = float(0.91).add(brokenEdge);
            const charShape = float(1).sub(smoothstep(
                edgeRadius.sub(0.18), edgeRadius.add(0.045), radius,
            ));
            const tendrilAngular = pow(max(sin(angle.mul(7).add(0.6)), 0), 18);
            const tendrilBand = smoothstep(0.46, 0.84, radius)
                .mul(float(1).sub(smoothstep(0.88, 1.18, radius)));
            const brokenCharShape = max(charShape, tendrilAngular.mul(tendrilBand).mul(0.24));
            const charCore = float(1).sub(smoothstep(0.0, 0.72, radius)).mul(0.22).add(0.78);
            material.colorNode = color.mul(charCore);
            material.opacityNode = brokenCharShape.mul(alpha);
            const mesh = new T3.Mesh(scorchGeometry, material);
            mesh.name = `weather_lightning_scorch_${slotIndex}`;
            mesh.visible = false;
            mesh.renderOrder = 3;
            mesh.userData.noSupportCheck = true;
            mesh.userData.noWet = true;
            mesh.userData.noPuddles = true;
            mesh.raycast = () => {};
            scene.add(mesh);
            impactObjects.push(mesh);
            return {
                active: false,
                birth: -Infinity,
                mesh,
                material,
                alpha,
                color,
                strikeColor: new T3.Color(LIGHTNING_STYLES.white.hex),
            };
        };
        const scorchSlots = Array.from(
            { length: SCORCH_POOL_SIZE }, (_, index) => makeScorchSlot(index),
        );

        const impactBasisAxis = V(1, 0, 0);
        const impactBasisTangent = V(1, 0, 0);
        const impactBasisBitangent = V(0, 0, 1);
        const impactScratchPosition = V(0, 0, 0);
        const impactScratchDirection = V(0, 1, 0);
        const impactScratchScale = V(1, 1, 1);
        const impactScratchQuaternion = new T3.Quaternion();
        const impactScratchMatrix = new T3.Matrix4();
        const impactLocalY = V(0, 1, 0);
        const impactLocalZ = V(0, 0, 1);
        const chooseOldestSlot = (slots) => slots.reduce(
            (oldest, candidate) => candidate.birth < oldest.birth ? candidate : oldest,
            slots[0],
        );
        const triggerImpact = (interval, time, point, normal, color) => {
            const slot = chooseOldestSlot(impactSlots);
            slot.active = true;
            slot.birth = time;
            slot.interval = interval;
            slot.origin.copy(point);
            slot.normal.copy(normal).normalize();
            slot.color.copy(color);
            slot.sparkColor.value.set(color.r, color.g, color.b);
            // Ash grey, not soot black: on a Dark Storm scene near-black smoke
            // vanished entirely ("nothing at all except some tiny sparks").
            slot.puffColor.value.set(
                0.16 + color.r * 0.10,
                0.17 + color.g * 0.10,
                0.185 + color.b * 0.11,
            );
            slot.puffGlowColor.value.set(color.r, color.g, color.b);
            impactBasisAxis.set(Math.abs(normal.x) > 0.8 ? 0 : 1, 0, Math.abs(normal.x) > 0.8 ? 1 : 0);
            impactBasisTangent.crossVectors(impactBasisAxis, normal).normalize();
            impactBasisBitangent.crossVectors(normal, impactBasisTangent).normalize();
            for (let index = 0; index < IMPACT_SPARK_COUNT; index++) {
                const angle = jsHash(interval * 37.1 + index * 11.7 + 3) * Math.PI * 2;
                const side = 1.5 + jsHash(interval * 41.3 + index * 7.9 + 5) * 7.0;
                const lift = 4.0 + jsHash(interval * 43.7 + index * 13.1 + 7) * 9.5;
                slot.sparkVelocity[index]
                    .copy(normal).multiplyScalar(lift)
                    .addScaledVector(impactBasisTangent, Math.cos(angle) * side)
                    .addScaledVector(impactBasisBitangent, Math.sin(angle) * side);
                slot.sparkLength[index] = 0.07 + jsHash(interval * 47.9 + index * 5.3 + 9) * 0.20;
            }
            for (let index = 0; index < IMPACT_PUFF_COUNT; index++) {
                const angle = jsHash(interval * 53.3 + index * 9.1 + 11) * Math.PI * 2;
                const radius = jsHash(interval * 59.9 + index * 4.7 + 13) * 1.2;
                slot.puffOffset[index]
                    .copy(impactBasisTangent).multiplyScalar(Math.cos(angle) * radius)
                    .addScaledVector(impactBasisBitangent, Math.sin(angle) * radius)
                    .addScaledVector(normal, 0.30 + jsHash(interval * 61.7 + index * 8.3 + 15) * 0.75);
                slot.puffDrift[index]
                    .copy(impactBasisTangent).multiplyScalar((jsHash(interval * 67.1 + index * 3.7 + 17) - 0.5) * 0.75)
                    .addScaledVector(impactBasisBitangent, (jsHash(interval * 71.3 + index * 6.1 + 19) - 0.5) * 0.75)
                    .addScaledVector(normal, 0.45 + jsHash(interval * 73.9 + index * 2.9 + 21) * 0.75);
                // Sized for a lightning burn: the old 0.45-1.3 m bodies were a
                // 20 px smudge at the 35-60 m forced-strike distance.
                slot.puffSize[index] = 1.1 + jsHash(interval * 79.7 + index * 10.7 + 23) * 1.6;
            }

            const scorch = chooseOldestSlot(scorchSlots);
            scorch.active = true;
            scorch.birth = time;
            scorch.strikeColor.copy(color);
            scorch.mesh.position.copy(point).addScaledVector(normal, 0.018);
            scorch.mesh.quaternion.setFromUnitVectors(impactLocalZ, normal);
            const scorchSize = 0.9 + jsHash(interval * 83.9 + 29) * 1.2;
            scorch.mesh.scale.set(scorchSize, scorchSize, scorchSize);
            scorch.mesh.visible = true;
            return slot;
        };

        const updateImpactPool = (time, camera) => {
            for (const slot of impactSlots) {
                if (!slot.active) continue;
                const age = Math.max(0, time - slot.birth);
                const sparkLife = 0.82;
                if (age < sparkLife) {
                    slot.sparks.visible = true;
                    slot.sparkAlpha.value = Math.max(0, 1 - age / sparkLife);
                    for (let index = 0; index < IMPACT_SPARK_COUNT; index++) {
                        const velocity = slot.sparkVelocity[index];
                        impactScratchPosition.copy(slot.origin)
                            .addScaledVector(velocity, age)
                            .addScaledVector(slot.normal, -4.9 * age * age);
                        impactScratchDirection.copy(velocity)
                            .addScaledVector(slot.normal, -9.8 * age)
                            .normalize();
                        impactScratchQuaternion.setFromUnitVectors(impactLocalY, impactScratchDirection);
                        impactScratchScale.set(
                            0.038,
                            slot.sparkLength[index] * (1 - age / sparkLife * 0.65),
                            0.038,
                        );
                        impactScratchMatrix.compose(
                            impactScratchPosition, impactScratchQuaternion, impactScratchScale,
                        );
                        slot.sparks.setMatrixAt(index, impactScratchMatrix);
                    }
                    slot.sparks.instanceMatrix.needsUpdate = true;
                } else {
                    slot.sparks.visible = false;
                    slot.sparkAlpha.value = 0;
                }

                const puffLife = 4.5;
                if (age < puffLife && camera) {
                    slot.puffs.visible = true;
                    // Fade lives in the shader (hold, then die: 1 - t^7); JS
                    // supplies only the fast rise-in and the overall gain.
                    const rise = Math.min(1, age / 0.15);
                    slot.puffAlpha.value = rise;
                    slot.puffAge.value = age;
                    slot.puffAge01.value = age / puffLife;
                    slot.puffGlowK.value = Math.exp(-age * 3.4) * 1.1
                        + Math.exp(-age * 0.8) * 0.30;
                    for (let index = 0; index < IMPACT_PUFF_COUNT; index++) {
                        impactScratchPosition.copy(slot.origin)
                            .add(slot.puffOffset[index])
                            .addScaledVector(slot.puffDrift[index], age)
                            // hot gas accelerates upward as it cools and slows
                            .addScaledVector(slot.normal, 0.14 * age * age);
                        // fast initial expansion easing off, like the shader's
                        // pow(t, .2) growth — a linear ramp read as inflation
                        const growth01 = Math.pow(age / puffLife, 0.25);
                        const growthJitter = 0.85
                            + jsHash(slot.interval * 97.7 + index * 6.7 + 31) * 0.5;
                        const size = slot.puffSize[index]
                            * (0.6 + growth01 * 1.5 * growthJitter);
                        impactScratchScale.set(size, size, size);
                        // slow per-instance roll in the view plane: identical
                        // billboard orientations made the cluster read as one
                        // rigid object instead of independent smoke bodies
                        const roll = jsHash(slot.interval * 91.3 + index * 12.7 + 27)
                            * Math.PI * 2
                            + (jsHash(slot.interval * 89.1 + index * 15.1 + 33) - 0.5)
                                * 0.45 * age;
                        impactScratchQuaternion.setFromAxisAngle(impactLocalZ, roll)
                            .premultiply(camera.quaternion);
                        impactScratchMatrix.compose(
                            impactScratchPosition, impactScratchQuaternion, impactScratchScale,
                        );
                        slot.puffs.setMatrixAt(index, impactScratchMatrix);
                    }
                    slot.puffs.instanceMatrix.needsUpdate = true;
                } else {
                    slot.puffs.visible = false;
                    slot.puffAlpha.value = 0;
                    slot.puffGlowK.value = 0;
                }
                if (age >= puffLife) slot.active = false;
            }
            for (const scorch of scorchSlots) {
                if (!scorch.active) continue;
                const age = Math.max(0, time - scorch.birth);
                if (age >= SCORCH_LIFETIME) {
                    scorch.active = false;
                    scorch.mesh.visible = false;
                    scorch.alpha.value = 0;
                    continue;
                }
                const hot = Math.max(0, 1 - age / 1.4);
                const fade = age <= 65 ? 1 : Math.max(0, 1 - (age - 65) / 25);
                scorch.alpha.value = (0.62 - hot * 0.10) * fade;
                scorch.color.value.set(
                    0.018 + scorch.strikeColor.r * 0.22 * hot,
                    0.011 + scorch.strikeColor.g * 0.18 * hot,
                    0.007 + scorch.strikeColor.b * 0.14 * hot,
                );
                scorch.mesh.visible = true;
            }
        };

        const strikeRaycaster = new T3.Raycaster();
        const strikeRayHits = [];
        const strikeRayOrigin = V(0, 0, 0);
        const strikeRayDirection = V(0, -1, 0);
        const strikeForward = V(0, 0, -1);
        const strikeNormal = V(0, 1, 0);
        const strikePoint = V(0, 0, 0);
        const strikeNormalMatrix = new T3.Matrix3();
        const strikeInstanceMatrix = new T3.Matrix4();
        const strikeWorldMatrix = new T3.Matrix4();
        const localStrikeHit = {
            point: strikePoint,
            normal: strikeNormal,
            kind: 'surface',
            object: null,
        };
        let lastLocalStrikeAt = -Infinity;
        let debugForcedStrikePending = false;
        const strikeRoots = () => {
            const value = typeof opts.strikeTargets === 'function'
                ? opts.strikeTargets()
                : opts.strikeTargets;
            if (!value) return [];
            return (Array.isArray(value) ? value : [value]).filter(Boolean);
        };
        const blockedStrikeReceiver = (object) => {
            let node = object;
            while (node) {
                if (node.visible === false || node.userData?.noLightningStrike) return true;
                if (/orb|emitter|beam|fastener|decal|foliage|vegetation|cactus|joshua/i.test(node.name ?? '')) return true;
                node = node.parent;
            }
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            const material = materials[0];
            return !material || material.visible === false || material.transparent === true
                || Number(material.opacity ?? 1) < 0.95 || material.depthWrite === false;
        };
        const worldHitNormal = (hit) => {
            if (!hit?.face?.normal || !hit.object) return null;
            strikeWorldMatrix.copy(hit.object.matrixWorld);
            if (hit.object.isInstancedMesh && Number.isInteger(hit.instanceId)) {
                hit.object.getMatrixAt(hit.instanceId, strikeInstanceMatrix);
                strikeWorldMatrix.multiplyMatrices(hit.object.matrixWorld, strikeInstanceMatrix);
            }
            strikeNormalMatrix.getNormalMatrix(strikeWorldMatrix);
            return strikeNormal.copy(hit.face.normal).applyNormalMatrix(strikeNormalMatrix).normalize();
        };
        const fallbackTerrainStrike = (x, z, camera) => {
            if (typeof opts.strikeHeightAt !== 'function') return null;
            const playerDistance = Math.hypot(x - camera.position.x, z - camera.position.z);
            if (playerDistance < LOCAL_STRIKE_PLAYER_GUARD) return null;
            const epsilon = 0.75;
            const y = Number(opts.strikeHeightAt(x, z));
            const xLo = Number(opts.strikeHeightAt(x - epsilon, z));
            const xHi = Number(opts.strikeHeightAt(x + epsilon, z));
            const zLo = Number(opts.strikeHeightAt(x, z - epsilon));
            const zHi = Number(opts.strikeHeightAt(x, z + epsilon));
            if (![y, xLo, xHi, zLo, zHi].every(Number.isFinite)) return null;
            strikeNormal.set(
                -(xHi - xLo) / (epsilon * 2),
                1,
                -(zHi - zLo) / (epsilon * 2),
            ).normalize();
            if (strikeNormal.y < 0.72) return null;
            strikePoint.set(x, y, z);
            localStrikeHit.kind = 'terrain_heightfield';
            localStrikeHit.object = null;
            return localStrikeHit;
        };
        const findLocalStrike = (interval, camera, { preferForward = false } = {}) => {
            const roots = strikeRoots();
            // A heightfield fallback is intentionally valid even when every
            // visual terrain chunk is culled or no raycast root is registered.
            // Returning here used to defeat that fallback completely.
            if (!camera) return null;
            for (const root of roots) root.updateWorldMatrix?.(true, true);
            camera.getWorldDirection?.(strikeForward);
            strikeForward.y = 0;
            if (strikeForward.lengthSq() < 1e-5) strikeForward.set(0, 0, -1);
            strikeForward.normalize();
            const cloudTop = sky
                ? Number(sky.uniforms.cloudStart.value) + Number(sky.uniforms.cloudHeight.value) + 100
                : 1200;
            for (let candidate = 0; candidate < 8; candidate++) {
                const angleSpan = preferForward ? 0.28 : 0.84;
                const angle = (jsHash(interval * 89.3 + candidate * 17.1 + 31) - 0.5) * Math.PI * angleSpan;
                const radius = preferForward
                    ? FORCED_LOCAL_STRIKE_MIN_RADIUS
                        + jsHash(interval * 97.7 + candidate * 13.7 + 37)
                            * (FORCED_LOCAL_STRIKE_MAX_RADIUS
                                - FORCED_LOCAL_STRIKE_MIN_RADIUS)
                    : 45 + jsHash(interval * 97.7 + candidate * 13.7 + 37) * 125;
                const ca = Math.cos(angle), sa = Math.sin(angle);
                const dx = strikeForward.x * ca - strikeForward.z * sa;
                const dz = strikeForward.x * sa + strikeForward.z * ca;
                const x = camera.position.x + dx * radius;
                const z = camera.position.z + dz * radius;
                strikeRayOrigin.set(x, Math.max(cloudTop, camera.position.y + 700), z);
                strikeRaycaster.set(strikeRayOrigin, strikeRayDirection);
                strikeRaycaster.near = 0;
                strikeRaycaster.far = Math.max(2400, strikeRayOrigin.y + 1200);
                strikeRayHits.length = 0;
                strikeRaycaster.intersectObjects(roots, true, strikeRayHits);
                for (const hit of strikeRayHits) {
                    if (blockedStrikeReceiver(hit.object)) continue;
                    const normal = worldHitNormal(hit);
                    if (!normal || normal.y < 0.72) continue;
                    const playerDistance = Math.hypot(
                        hit.point.x - camera.position.x,
                        hit.point.z - camera.position.z,
                    );
                    if (playerDistance < LOCAL_STRIKE_PLAYER_GUARD) continue;
                    strikePoint.copy(hit.point);
                    localStrikeHit.kind = hit.object.name || 'upward_surface';
                    localStrikeHit.object = hit.object;
                    return localStrikeHit;
                }
                const terrainHit = fallbackTerrainStrike(x, z, camera);
                if (terrainHit) return terrainHit;
            }
            return null;
        };

        // ---------------- wetness material response ----------------
        // Hoskins-style hash: fract-product hashes correlate along the
        // lattice at large world coordinates — puddle shapes turned into
        // grid-aligned blocks that read as low-res (same fix as the waves)
        const hash2 = (p) => {
            const a = fract(vec3(p.x, p.y, p.x).mul(0.1031));
            const d = dot(a, vec3(a.y, a.z, a.x).add(33.33));
            const b = a.add(d);
            return fract(b.x.add(b.y).mul(b.z));
        };
        const vnoise2 = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(f).mul(f.mul(f.mul(6).sub(15)).add(10)); // quintic: C2, no lattice creases
            const a = hash2(i), b = hash2(i.add(vec2(1, 0)));
            const c = hash2(i.add(vec2(0, 1))), d = hash2(i.add(vec2(1, 1)));
            return mix(mix(a, b, sm.x), mix(c, d, sm.x), sm.y);
        };
        const wrapped = new Set();
        const wrappedRoots = new Map();
        const receiverMeshes = new Set();
        const receiverNames = [];
        const wetnessStats = {
            projection: 'per-fragment-world-position-and-world-normal',
            supportsArbitraryUpwardGeometry: true,
            wrappedMaterials: 0,
            receiverMeshes: 0,
            receiverNames,
            wetness: 0,
            puddleStrength: Number(u.puddleK.value),
        };
        const registerReceiver = (receiver) => {
            if (!receiver?.isMesh || receiverMeshes.has(receiver)) return;
            receiverMeshes.add(receiver);
            if (receiverNames.length < 96) receiverNames.push(receiver.name || receiver.uuid || '(unnamed mesh)');
            wetnessStats.receiverMeshes = receiverMeshes.size;
        };
        const wrapMaterial = (mat, receiver = null) => {
            if (!mat || !mat.isNodeMaterial) return false;
            registerReceiver(receiver);
            if (wrapped.has(mat)) return false;
            wrapped.add(mat);
            wrappedRoots.set(mat, {
                colorNode: mat.colorNode,
                roughnessNode: mat.roughnessNode,
                metalnessNode: mat.metalnessNode,
            });
            const upMask = clamp(normalWorld.y, 0, 1).pow(2).mul(u.wetness);
            // Crossed-card foliage deliberately carries upward normals for
            // soft clump lighting, so normalWorld.y cannot identify ground by
            // itself. Keep the wet sheen but let receivers opt out of the
            // ground-only puddle replacement path.
            const puddleGate = (mat.userData?.noPuddles || receiver?.userData?.noPuddles)
                ? float(0)
                : float(1);
            const flat = smoothstep(0.985, 0.998, normalWorld.y);
            // puddle mask: threshold value noise near its MIDDLE, never its
            // max — near-max iso-contours of value noise are blobs centered
            // on the lattice points in a grid arrangement (square puddles,
            // regardless of hash quality). The coarse octave also WARPS the
            // fine octave's domain so outlines meander instead of gridding.
            const warp = vec2(
                vnoise2(positionWorld.xz.mul(0.045)),
                vnoise2(positionWorld.xz.mul(0.045).add(vec2(37.7, 11.3)))
            ).sub(0.5).mul(2.2);   // gentle wobble only — strong warp smears puddles into stripes
            const pn = vnoise2(positionWorld.xz.mul(0.35).add(warp))
                .add(vnoise2(positionWorld.xz.mul(0.09)).mul(0.6));
            // distance-faded: procedural puddle detail aggregates at grazing
            // distance into a merged swamp read (no mips on procedural
            // noise) — far wet ground should read as uniform sheen instead
            const pDist = length(positionWorld.sub(cameraPosition));
            // SHAPE and AMPLITUDE are separate: the shape mask sharpens on
            // its own (crisp water edges), wetness then gates how much of
            // it applies. Sharpening AFTER the wetness multiply zeroes all
            // puddles in any state below full wet — shape × gate, always.
            const pShape = smoothstep(0.97, 1.13, pn).mul(flat).mul(u.puddleK).mul(puddleGate)
                .mul(float(1).sub(smoothstep(160, 450, pDist)));
            const puddle = smoothstep(0.25, 0.6, pShape).mul(smoothstep(0.35, 0.9, u.wetness));
            // Normalize color roots to RGBA once. TSL supplies alpha=1 for a
            // vec3 root and retains atlas alpha for a vec4 root, so every wet
            // color operation can remain RGB without accidentally promoting a
            // puddle's vec3 color to opaque vec4.
            const baseColor4 = vec4(mat.colorNode ?? materialColor);
            const baseRgb = baseColor4.rgb;
            const baseRough = mat.roughnessNode ?? materialRoughness;
            // wetness reads through GLOSS/reflection, not blackness — mild
            // darkening only (heavy albedo crush made black splotches)
            const darkened = baseRgb.mul(mix(float(1), float(0.68), upMask.mul(0.85)));
            const wetCol = darkened.mul(mix(vec3(1, 1, 1), u.wetTint, upMask.mul(0.6)));
            // Puddles receive sky through Three's native cloud PMREM/IBL and
            // local geometry through SSR. The metalness/roughness TSL
            // registers carry the final mapped values into the shared scene
            // G-buffer without a per-material override. Water is a dielectric:
            // Schlick fresnel
            // (F0≈0.06) makes it a mirror only toward grazing. Top-down, a
            // puddle is shallow water over the ground: albedo shows the
            // water-deepened wet ground (the "see-through" read), reflection
            // fades to a sheen. Distant ground is inherently grazing, so far
            // puddles go full mirror — the classic wet-road look.
            // Do not paint Fresnel into albedo or metalness. Three's native
            // dielectric BRDF already supplies angle-dependent PMREM/SSR.
            // The former near-white injection plus metalness=fresnel could
            // saturate broad wet terrain during a lightning flash.
            // pseudo-depth from the shape mask: shallow rims barely change
            // the ground, centers deepen + cool — the see-through read
            // survives top-down views and flat-colored ground
            const pDepth = smoothstep(0.3, 1.0, pShape);
            const waterFloor = wetCol.mul(mix(float(0.96), float(0.62), pDepth))
                .mul(mix(vec3(1, 1, 1), vec3(0.84, 0.91, 1.0), pDepth.mul(0.7)));
            const finalWetRgb = mix(wetCol, waterFloor, puddle);
            // Weather color must not replace the alpha channel used by
            // foliage/decals for cutout silhouettes. Losing it turns distant
            // crossed cards into solid rectangular planes.
            mat.colorNode = vec4(finalWetRgb, baseColor4.a);
            mat.roughnessNode = mix(mix(baseRough, float(0.10), upMask.mul(0.8)), float(0.045), puddle);
            // Water remains dielectric; low roughness provides its native
            // Fresnel reflection without a metallic or white-albedo shortcut.
            const baseMetal = mat.metalnessNode ?? materialMetalness;
            mat.metalnessNode = mix(baseMetal, float(0), puddle);
            mat.needsUpdate = true;
            wetnessStats.wrappedMaterials = wrapped.size;
            return true;
        };
        const wrapScene = () => {
            let n = 0;
            scene.traverse((o) => {
                if (!o.isMesh || o.userData.noWet) return;
                if (sky && sky.domes && sky.domes.includes(o)) return;
                const mats = Array.isArray(o.material) ? o.material : [o.material];
                for (const m of mats) if (wrapMaterial(m, o)) n++;
            });
            console.log(`[weather] wetness wrapped ${n} materials`);
            if (sky && sky.wrapCloudShadows) sky.wrapCloudShadows(scene, 0.5);
            return n;
        };

        const state = { name: 'clear', k: 1, def: WEATHER.clear };
        let disposed = false;
        let lastMotionT = null;
        let totalFallDistance = 0;
        const totalWindDistance = V(0, 0, 0);
        const diagnostics = {
            version: 'weather-acceptance-v3',
            transition: {
                active: false,
                from: 'clear',
                target: 'clear',
                durationSeconds: 0,
                elapsedSeconds: 0,
                rawProgress: 1,
                easedProgress: 1,
            },
            motion: {
                integration: 'positive-delta-time-velocity',
                verticalDirection: 'downward-only',
                fallVelocity: 0,
                lastDeltaSeconds: 0,
                totalFallDistance: 0,
                totalWindDistance: [0, 0],
                fallPhase: 0,
                windOffset: [0, 0],
            },
            precipitation: {
                fieldShape: 'camera-centred-circular-feather',
                darkstormCoverage: 'sealed-canopy-independent',
                volumetricCurtains: true,
                featherInnerRadius: RAD * 0.70,
                featherOuterRadius: RAD,
                opacityBaseRange: [0.075, 0.20],
                sceneLightResponsive: true,
                rainPopulation: N_RAIN,
                splashPopulation: N_SPLASH,
                rainVisible: false,
                intensity: 0,
                sceneLight: 1,
                sceneColor: [0.72, 0.78, 0.86],
            },
            lightning: {
                schedule: 'deterministic-separated-events-bounded-return-strokes',
                palette: 'standard',
                paletteWeights: LIGHTNING_PALETTES,
                cadence: LIGHTNING_CADENCE,
                eventCount: 0,
                activeEvent: false,
                activeStrokeCount: 0,
                eventElapsedSeconds: 0,
                nextEventAtSeconds: null,
                lastEventGapSeconds: null,
                activeStyle: 'white',
                flash: 0,
                lastStrike: null,
                sceneLight: {
                    peakIntensity: LIGHTNING_LIGHT_PEAK,
                    distance: LIGHTNING_LIGHT_RANGE,
                    decay: 2,
                    shadows: false,
                },
                localImpact: {
                    cooldownSeconds: LOCAL_STRIKE_COOLDOWN,
                    playerGuardMeters: LOCAL_STRIKE_PLAYER_GUARD,
                    upwardNormalMinimum: 0.72,
                    effectSlots: IMPACT_POOL_SIZE,
                    sparkInstancesPerSlot: IMPACT_SPARK_COUNT,
                    puffInstancesPerSlot: IMPACT_PUFF_COUNT,
                    scorchSlots: SCORCH_POOL_SIZE,
                    scorchLifetimeSeconds: SCORCH_LIFETIME,
                    strikes: 0,
                    candidateAttempts: 0,
                    forcedCandidates: 0,
                    firstCandidateWithinEvents: LIGHTNING_CADENCE.darkstorm.firstLocalCandidateWithinEvents,
                    maxRemoteEvents: LIGHTNING_CADENCE.darkstorm.maxRemoteEventsBetweenLocalCandidates,
                    remoteEventsSinceStrike: 0,
                    raycastMisses: 0,
                    lastSurfaceDamage: null,
                },
            },
            wetness: wetnessStats,
        };
        // ---- smooth weather transitions: lerp every uniform setWeather touches
        // plus a BLENDED live state.def, so per-frame readers (palette greying,
        // lightning probability, ring-cloud coverage) ease instead of popping
        const _transScalars = () => {
            const s = [u.rainK, u.wetness, u.denseA, u.streakLen, u.fallMul, u.dashK, u.cellLo, u.cellHi];
            if (sky) s.push(sky.uniforms.cloudDim, sky.uniforms.cloudRadiance, sky.uniforms.sunDiscI, sky.uniforms.precipK, sky.uniforms.precipLo, sky.uniforms.precipHi,
                sky.uniforms.largeT, sky.uniforms.largeA, sky.uniforms.weatherT, sky.uniforms.finalMul,
                sky.uniforms.wScale, sky.uniforms.dScale, sky.uniforms.cloudStart, sky.uniforms.cloudHeight, sky.uniforms.lightK,
                sky.uniforms.wispOn, sky.uniforms.wispScale, sky.uniforms.wispThreshold,
                sky.uniforms.wispStrength, sky.uniforms.wispOpacity, sky.uniforms.wispFloor,
                sky.uniforms.wispFilament, sky.uniforms.lightCacheDirect, sky.uniforms.stormCanopy,
                sky.uniforms.celestialVisibility);
            return s;
        };
        const _transVecs = () => {
            const v = [u.windVec];
            if (sky) {
                v.push(sky.uniforms.skyWind, sky.uniforms.stretch, sky.uniforms.wispStretch,
                    sky.uniforms.wispTint, sky.uniforms.wispColor);
            }
            return v;
        };
        const _capture = () => ({
            s: _transScalars().map((x) => x.value),
            v: _transVecs().map((x) => x.value.clone()),
        });
        const _apply = (a, b, k) => {
            _transScalars().forEach((x, i) => { x.value = a.s[i] + (b.s[i] - a.s[i]) * k; });
            _transVecs().forEach((x, i) => { x.value.lerpVectors(a.v[i], b.v[i], k); });
        };
        const DEF_DEFAULTS = { horMul: 1, dense: 1, distant: 0, localStrikeChance: 0, cellLo: 0.9, cellHi: 1.45 };
        const _lerpDef = (a, b, k) => {
            const out = {};
            // Use the union: target presets often omit optional storm fields.
            // Iterating only target keys made distant lightning, horizon
            // darkening, and density snap off at the beginning of a transition.
            for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
                const av = a[key], bv = b[key];
                if (typeof av === 'number' || typeof bv === 'number') {
                    const fallback = DEF_DEFAULTS[key];
                    const aa = typeof av === 'number' ? av
                        : key === 'hemiDim' ? 0.5 + (a.sunDim ?? 1) * 0.5
                            : (fallback ?? bv);
                    const bb = typeof bv === 'number' ? bv
                        : key === 'hemiDim' ? 0.5 + (b.sunDim ?? 1) * 0.5
                            : (fallback ?? av);
                    out[key] = aa + (bb - aa) * k;
                } else if (Array.isArray(av) || Array.isArray(bv)) {
                    const aa = Array.isArray(av) ? av : bv;
                    const bb = Array.isArray(bv) ? bv : av;
                    out[key] = bb.map((c, i) => aa[i] + (c - aa[i]) * k);
                } else {
                    out[key] = k < 0.5 ? (av ?? bv) : (bv ?? av);
                }
            }
            return out;
        };
        const sys = {
            uniforms: u, state, rain: rainInst, bolt, WEATHER, diagnostics,
            lightningProfile: globalThis.EANPA_LIGHTNING_PROFILE,
            // Debug/inspection: the next lightning event becomes a forced
            // close forward strike (34-58 m ahead), bypassing chance and
            // cooldown, so the impact puff and scorch can be examined. The
            // event itself is pulled to ~0.6 s out — waiting the natural
            // 12-28 s gap made the trigger look dead. Returns whether the
            // active weather can produce lightning at all.
            debugForceLocalStrike() {
                const level = Math.max(0, Number(state.def.lightning) || 0)
                    * Math.max(0, Math.min(1, Number(state.k) || 0));
                if (level <= 0.0001) return false;
                debugForcedStrikePending = true;
                const now = Number.isFinite(lastMotionT) ? lastMotionT : 0;
                if (!Number.isFinite(nextLightningEventAt)
                    || nextLightningEventAt > now + 0.6) {
                    nextLightningEventAt = now + 0.6;
                }
                return true;
            },
            // smooth transition to another weather state over `dur` seconds.
            // Fully agent-tunable — pass 60-120 for a naturally rolling front;
            // the default is a films-scale slow build, NOT the demo-reel pace.
            transitionTo(name, k = 1, dur = 45) {
                const fromDef = { ...state.def }, fromK = state.k, fromName = state.name;
                const cloudDome = sky?.domes?.[1] ?? null;
                const fromPreset = sky?.state?.preset ?? null;
                const fromCloudVisible = cloudDome?.visible ?? false;
                const snap = _capture();
                sys.setWeather(name, k);            // writes targets + swaps state
                const target = _capture();
                const toDef = { ...state.def }, toName = state.name;
                const toPreset = sky?.state?.preset ?? toDef.clouds ?? null;
                const toCloudVisible = cloudDome?.visible ?? false;
                _apply(snap, snap, 0);              // restore current values
                // A target preset of `clear` normally hides the dome inside
                // setClouds(). Keep it alive until its density/wisps have faded
                // to zero. Mark the semantic preset as transitional so the
                // optimized light cache and reflection bake do not take the
                // clear-sky shortcut while clouds are still present.
                const transitionHasClouds = fromCloudVisible || toCloudVisible;
                if (cloudDome) cloudDome.visible = transitionHasClouds;
                if (sky?.state) sky.state.preset = transitionHasClouds ? 'transition' : toPreset;
                const safeDur = Math.max(0.001, Number.isFinite(dur) ? dur : 45);
                sys._trans = { fromDef, fromK, fromName, fromPreset, toDef, toK: k, toName, toPreset, toCloudVisible, snap, target, t0: null, dur: safeDur };
                sys._transS = 0;
                Object.assign(diagnostics.transition, {
                    active: true,
                    from: fromName,
                    target: toName,
                    durationSeconds: safeDur,
                    elapsedSeconds: 0,
                    rawProgress: 0,
                    easedProgress: 0,
                });
                // Keep precipitation geometry present for the whole fade in or
                // fade out; rainK supplies the actual smooth opacity/count ramp.
                const transitionHasRain = (fromDef.rain * fromK) > 0.001 || (toDef.rain * k) > 0.001;
                rainInst.visible = transitionHasRain;
                splashInst.visible = transitionHasRain && N_SPLASH > 0;
                diagnostics.precipitation.rainVisible = transitionHasRain;
            },
            setWeather(name, k = 1) {
                if (name === 'noreaster') name = 'cyclone';   // state renamed; legacy alias
                // An immediate state application supersedes any old morph.
                // Without this, a caller applying a settled/debug/initial
                // state mid-transition was silently overwritten on the next
                // frame, making weather changes appear to do nothing until a
                // full None/rebuild cycle.
                sys._trans = null;
                diagnostics.transition.active = false;
                if (!WEATHER[name]) console.warn(`[weather] unknown state "${name}" — falling back to clear (valid: ${Object.keys(WEATHER).join(', ')})`);
                const resolvedName = WEATHER[name] ? name : 'clear';
                const w = WEATHER[resolvedName];
                Object.assign(diagnostics.transition, {
                    active: false,
                    from: resolvedName,
                    target: resolvedName,
                    durationSeconds: 0,
                    elapsedSeconds: 0,
                    rawProgress: 1,
                    easedProgress: 1,
                });
                state.name = resolvedName; state.k = k; state.def = w;
                if (sky) {
                    sky.setClouds(w.clouds, w.over);
                    sky.uniforms.cloudDim.value = Math.max(0.1, 1 - (1 - w.sunDim) * k);
                    const authoredCloudRadiance = w.cloudRadiance ?? w.sunDim;
                    sky.uniforms.cloudRadiance.value = Math.max(0.1, 1 - (1 - authoredCloudRadiance) * k);
                    sky.uniforms.sunDiscI.value = 48 * Math.max(0.02, 1 - w.grey * k * 0.98);
                    sky.uniforms.celestialVisibility.value = 1 - (1 - (w.celestialVisibility ?? 1)) * k;
                    sky.uniforms.precipK.value = w.rain * k * (w.dense ?? 1);   // world rain curtains under dense cells
                }
                u.rainK.value = w.rain * k;
                u.wetness.value = w.wet * k;
                u.windVec.value.set(1.0, 0, 0.22).normalize().multiplyScalar(w.windK * 3.2);
                u.denseA.value = w.dense ?? 1;
                if (sky && sky.uniforms.skyWind) {
                    // ONE wind: clouds aloft move with the surface wind (faster),
                    // so rain shear, cell drift, and cloud motion agree
                    sky.uniforms.skyWind.value.set(u.windVec.value.x * 1.6 + 2, 0, u.windVec.value.z * 1.6 + 6);
                }
                u.streakLen.value = w.len;
                u.fallMul.value = w.fall;
                u.dashK.value = w.dash;
                u.cellLo.value = w.cellLo ?? 0.9;
                u.cellHi.value = w.cellHi ?? 1.45;
                if (sky && sky.uniforms.precipLo) { sky.uniforms.precipLo.value = (w.cellLo ?? 0.9) + 0.05; sky.uniforms.precipHi.value = (w.cellHi ?? 1.45) + 0.1; }
                rainInst.visible = (w.rain * k) > 0.001;
                splashInst.visible = rainInst.visible && N_SPLASH > 0;
                diagnostics.precipitation.rainVisible = rainInst.visible;
                diagnostics.precipitation.intensity = u.rainK.value;
                wetnessStats.wetness = u.wetness.value;
                if ((w.lightning * k) <= 0.0001) {
                    clearLightningSchedule();
                    boltMesh.visible = false;
                    boltK.value = 0;
                    boltChannelK.value = 0;
                    bolt.intensity = 0;
                    if (state.strike) state.strike.flash = 0;
                    if (sky?.uniforms?.lightningStrike?.value) {
                        sky.uniforms.lightningStrike.value.w = 0;
                    }
                }
                return w;
            },
            sunDim() {
                const target = Number.isFinite(state.def.sunDim)
                    ? Math.max(0, Math.min(1, state.def.sunDim))
                    : 1;
                const amount = Number.isFinite(state.k)
                    ? Math.max(0, Math.min(1, state.k))
                    : 0;
                // No intensity floor: a settled sealed cumulonimbus canopy
                // fully occludes the directional sun/moon key. Lightning owns
                // its separate bounded PointLight and remains visible.
                return Math.max(0, Math.min(1, 1 - (1 - target) * amount));
            },
            hemiDim() {
                const ordinary = 0.5 + (state.def.sunDim ?? 1) * 0.5;
                const target = state.def.hemiDim ?? ordinary;
                return Math.max(0.08, 1 - (1 - target) * state.k);
            },
            wrapMaterial, wrapScene,
            // Every pooled weather mesh, for boot-time pipeline warmup. These
            // spawn invisible, and compileAsync skips invisible objects — so
            // their pipelines compiled mid-switch (a multi-second stall) or
            // mid-strike instead. The caller flashes them visible, compiles,
            // and restores.
            pipelineWarmupObjects() {
                return [
                    rainInst, splashInst, boltMesh,
                    ...impactObjects,
                    ...scorchSlots.map((slot) => slot.mesh),
                ];
            },
            update(t, camera) {
                // Registry replacement removes GPU objects, but callers may
                // still retain the old facade for a frame (or indefinitely).
                // A disposed/non-owning system must never keep advancing its
                // scheduler or writing flash values into the shared sky.
                if (disposed || weatherRegistry.get(scene) !== sys) return false;
                u.time.value = t;
                // drive an active weather transition
                if (sys._trans) {
                    const tr = sys._trans;
                    if (tr.t0 === null) tr.t0 = t;
                    const rawS = Math.max(0, Math.min(1, (t - tr.t0) / tr.dur));
                    let s = rawS;
                    s = s * s * (3 - 2 * s);                        // ease
                    diagnostics.transition.elapsedSeconds = Math.max(0, t - tr.t0);
                    diagnostics.transition.rawProgress = rawS;
                    diagnostics.transition.easedProgress = s;
                    _apply(tr.snap, tr.target, s);
                    state.def = _lerpDef(tr.fromDef, tr.toDef, s);
                    state.k = tr.fromK + (tr.toK - tr.fromK) * s;
                    sys._transS = s;
                    if (s >= 1) {
                        state.name = tr.toName; state.def = tr.toDef; state.k = tr.toK;
                        const cloudDome = sky?.domes?.[1] ?? null;
                        if (sky?.state) sky.state.preset = tr.toPreset;
                        if (cloudDome) cloudDome.visible = tr.toCloudVisible;
                        sky?.invalidateOptimizedCaches?.();
                        rainInst.visible = (state.def.rain * state.k) > 0.001;
                        splashInst.visible = rainInst.visible && N_SPLASH > 0;
                        sys._trans = null;
                        diagnostics.transition.active = false;
                    }
                }
                // Integrate the current velocity after applying the morph.
                // Both axes remain continuous even when wind/fall targets
                // decrease sharply between storm presets.
                const finiteT = Number.isFinite(t) ? t : 0;
                const motionDt = lastMotionT === null
                    ? 0
                    : Math.max(0, Math.min(finiteT - lastMotionT, 0.1));
                lastMotionT = finiteT;
                const fallVelocity = Math.max(
                    0.05,
                    Number(u.fallSpeed.value) * Math.max(0.05, Number(u.fallMul.value)),
                );
                totalFallDistance += fallVelocity * motionDt;
                totalWindDistance.x += u.windVec.value.x * motionDt;
                totalWindDistance.z += u.windVec.value.z * motionDt;
                u.fallPhase.value = totalFallDistance % HGT;
                u.windOffset.value.x = (
                    totalWindDistance.x % P + P
                ) % P;
                u.windOffset.value.z = (
                    totalWindDistance.z % P + P
                ) % P;
                Object.assign(diagnostics.motion, {
                    fallVelocity,
                    lastDeltaSeconds: motionDt,
                    totalFallDistance,
                    totalWindDistance: [totalWindDistance.x, totalWindDistance.z],
                    fallPhase: Number(u.fallPhase.value),
                    windOffset: [u.windOffset.value.x, u.windOffset.value.z],
                });
                if (camera) {
                    u.camPos.value.copy(camera.position);
                    const e = camera.matrixWorld.elements;
                    u.camRight.value.set(e[0], e[1], e[2]).normalize();
                    u.camUp.value.set(e[4], e[5], e[6]).normalize();
                }
                updateImpactPool(t, camera);
                // grey/darken the LIVE sky palette (tracks TOD changes) + flash
                if (sky) {
                    const w = state.def, k = state.k, pal = sky.state.palette;
                    let flash = 0;
                    const lightningLevel = Math.max(
                        0,
                        Math.min(1, (Number(w.lightning) || 0) * Math.max(0, Number(k) || 0)),
                    );
                    const transitionTargetName = sys._trans?.toName ?? null;
                    const cadenceKey = transitionTargetName === 'darkstorm'
                        || (transitionTargetName === null && w.lightningPalette === 'darkstorm')
                        ? 'darkstorm'
                        : 'standard';
                    let beganLightningEvent = false;
                    if (lightningLevel > 0.0001) {
                        const timeRewound = lastLightningScheduleT !== null
                            && finiteT + 0.001 < lastLightningScheduleT;
                        if (timeRewound || lightningCadenceKey !== cadenceKey
                            || !Number.isFinite(nextLightningEventAt)) {
                            if (lightningCadenceKey !== cadenceKey) {
                                darkstormEntryEventCount = 0;
                                remoteEventsSinceLocalStrike = 0;
                                darkstormHasLocalStrike = false;
                            }
                            lightningEventStart = -Infinity;
                            lightningEventSeed = -1;
                            lightningEventPlan = null;
                            lightningSheetScale = 0;
                            lightningCadenceKey = cadenceKey;
                            const firstGap = lightningInitialEventGapAt(
                                lightningEventIndex + 1, cadenceKey, lightningLevel,
                            );
                            nextLightningEventAt = finiteT + firstGap;
                            diagnostics.lightning.lastEventGapSeconds = firstGap;
                        }
                        lastLightningScheduleT = finiteT;

                        // At most one event can begin in one update. If a frame
                        // arrives late, schedule forward from *now* rather than
                        // replaying every missed event as a catch-up burst.
                        if (finiteT >= nextLightningEventAt) {
                            lightningEventIndex++;
                            lightningEventSeed = lightningEventIndex;
                            lightningEventStart = finiteT;
                            lightningEventPlan = lightningStrokePlanAt(
                                lightningEventSeed, cadenceKey,
                            );
                            const distantChance = Math.max(
                                0,
                                Math.min(1, (Number(w.distant) || 0) * Math.max(0, k)),
                            );
                            lightningSheetScale = jsHash(
                                lightningEventSeed * 83.71 + 29.3,
                            ) < distantChance
                                ? 0.10 + jsHash(lightningEventSeed * 89.17 + 37.1) * 0.12
                                : 0;
                            const nextGap = lightningEventGapAt(
                                lightningEventIndex + 1, cadenceKey, lightningLevel,
                            );
                            nextLightningEventAt = finiteT + nextGap;
                            diagnostics.lightning.eventCount++;
                            diagnostics.lightning.lastEventGapSeconds = nextGap;
                            if (cadenceKey === 'darkstorm') {
                                darkstormEntryEventCount++;
                                remoteEventsSinceLocalStrike++;
                                diagnostics.lightning.localImpact.remoteEventsSinceStrike
                                    = remoteEventsSinceLocalStrike;
                            }
                            beganLightningEvent = true;
                        }

                        const eventElapsed = finiteT - lightningEventStart;
                        let channelGlow = 0;
                        if (lightningEventPlan
                            && eventElapsed <= lightningEventPlan.durationSeconds) {
                            flash = lightningFlashAt(eventElapsed, lightningEventPlan);
                            channelGlow = lightningChannelAt(eventElapsed, lightningEventPlan);
                        } else {
                            lightningEventPlan = null;
                            lightningSheetScale = 0;
                        }

                        if (beganLightningEvent && camera) {
                            const I = lightningEventSeed;
                            activeStrikeKey = lightningStyleKeyAt(
                                I, w.lightningPalette ?? 'standard',
                            );
                            activeStrikeColor.setHex(
                                LIGHTNING_STYLES[activeStrikeKey].hex,
                            );
                            boltColor.value.set(
                                activeStrikeColor.r,
                                activeStrikeColor.g,
                                activeStrikeColor.b,
                            );
                            bolt.color.copy(activeStrikeColor);
                            // Strike a dense world cell. A rare local candidate
                            // atomically redirects this same bolt to its upward
                            // surface and creates its impact, scorch, and thunder.
                            const cx = opts.stormCenter?.[0] ?? 0;
                            const cz = opts.stormCenter?.[1] ?? 0;
                            const R = opts.stormRange ?? 700;
                            let sx = cx + (jsHash(I * 7 + 11) - 0.5) * 2 * R;
                            let sz = cz + (jsHash(I * 7 + 29) - 0.5) * 2 * R;
                            for (let q = 0; q < 12; q++) {
                                const qx = cx + (jsHash(I * 13 + q * 3 + 1) - 0.5) * 2 * R;
                                const qz = cz + (jsHash(I * 13 + q * 3 + 2) - 0.5) * 2 * R;
                                if (sky.weatherAt(qx, qz) > 1.3) {
                                    sx = qx;
                                    sz = qz;
                                    break;
                                }
                            }
                            let bottomY = 2;
                            let local = false;
                            let localHitObject = null;
                            let hitKind = 'distant_world_cell';
                            let hitNormal = [0, 1, 0];
                            const localChance = Math.max(0, w.localStrikeChance ?? 0) * k;
                            const forcedLocalCandidate = debugForcedStrikePending
                                || (cadenceKey === 'darkstorm'
                                && ((!darkstormHasLocalStrike
                                    && darkstormEntryEventCount
                                        >= LIGHTNING_CADENCE.darkstorm
                                            .firstLocalCandidateWithinEvents)
                                    || remoteEventsSinceLocalStrike
                                        >= LIGHTNING_CADENCE.darkstorm
                                            .maxRemoteEventsBetweenLocalCandidates));
                            const localCandidate = lightningLocalCandidateAt(
                                I,
                                localChance,
                                {
                                    paletteName: cadenceKey,
                                    entryEventCount: darkstormEntryEventCount,
                                    remoteEventsSinceLocal: remoteEventsSinceLocalStrike,
                                    hasLocalStrike: darkstormHasLocalStrike,
                                },
                            );
                            if (debugForcedStrikePending
                                || (finiteT - lastLocalStrikeAt >= LOCAL_STRIKE_COOLDOWN
                                && localCandidate)) {
                                diagnostics.lightning.localImpact.candidateAttempts++;
                                if (forcedLocalCandidate) {
                                    diagnostics.lightning.localImpact.forcedCandidates++;
                                }
                                const hit = findLocalStrike(I, camera, {
                                    preferForward: forcedLocalCandidate,
                                });
                                if (hit) {
                                    debugForcedStrikePending = false;
                                    local = true;
                                    sx = hit.point.x;
                                    sz = hit.point.z;
                                    bottomY = hit.point.y + 0.04;
                                    hitKind = hit.kind;
                                    localHitObject = hit.object ?? null;
                                    hitNormal = [hit.normal.x, hit.normal.y, hit.normal.z];
                                    lastLocalStrikeAt = finiteT;
                                    triggerImpact(
                                        I, finiteT, hit.point, hit.normal, activeStrikeColor,
                                    );
                                    diagnostics.lightning.localImpact.strikes++;
                                    if (cadenceKey === 'darkstorm') {
                                        darkstormHasLocalStrike = true;
                                        remoteEventsSinceLocalStrike = 0;
                                        diagnostics.lightning.localImpact
                                            .remoteEventsSinceStrike = 0;
                                    }
                                } else {
                                    diagnostics.lightning.localImpact.raycastMisses++;
                                }
                            }
                            const strikeId = Math.round(finiteT * 1000) * 1000 + I;
                            state.strike = {
                                id: strikeId,
                                interval: I,
                                time: finiteT,
                                x: sx,
                                y: bottomY,
                                z: sz,
                                cloudY: Number(sky.uniforms.cloudStart.value),
                                normal: hitNormal,
                                kind: hitKind,
                                colorKey: activeStrikeKey,
                                colorHex: LIGHTNING_STYLES[activeStrikeKey].hex,
                                local,
                                flash,
                            };
                            rebuildBolt(I, camera, sx, sz, bottomY);
                            if (local) {
                                // Persist a plain-data surface-damage record so
                                // world systems and tests can observe the same
                                // committed event as the bolt/VFX/scorch. The
                                // callback is notification only; an exception
                                // cannot roll back or suppress visible impact.
                                const surfaceDamage = {
                                    id: strikeId,
                                    interval: I,
                                    time: finiteT,
                                    point: [sx, bottomY, sz],
                                    normal: hitNormal.slice(),
                                    kind: hitKind,
                                    colorKey: activeStrikeKey,
                                    colorHex: LIGHTNING_STYLES[activeStrikeKey].hex,
                                    radiusMeters: LOCAL_STRIKE_SURFACE_DAMAGE_RADIUS,
                                    scorchLifetimeSeconds: SCORCH_LIFETIME,
                                };
                                state.lastImpact = surfaceDamage;
                                diagnostics.lightning.localImpact.lastSurfaceDamage
                                    = surfaceDamage;
                                if (localHitObject?.userData) {
                                    const receiverDamage = localHitObject.userData.lightningDamage
                                        ?? { strikes: 0, lastImpact: null };
                                    receiverDamage.strikes++;
                                    receiverDamage.lastImpact = surfaceDamage;
                                    localHitObject.userData.lightningDamage = receiverDamage;
                                }
                                try {
                                    opts.onLocalStrike?.(surfaceDamage);
                                } catch (error) {
                                    console.error('[weather] local-strike notification failed', error);
                                }
                            }
                            diagnostics.lightning.lastStrike = { ...state.strike };
                        }

                        const ownsActiveStrike = state.strike?.interval === lightningEventSeed;
                        boltMesh.visible = ownsActiveStrike && channelGlow > 0.02;
                        boltChannelK.value = ownsActiveStrike
                            ? Math.max(0, Math.min(1.15, channelGlow))
                            : 0;
                        if (ownsActiveStrike) {
                            state.strike.flash = flash;
                            const lightY = state.strike.local
                                ? state.strike.y + 10
                                : 120;
                            bolt.position.set(state.strike.x, lightY, state.strike.z);
                        }
                    } else {
                        clearLightningSchedule();
                        if (state.strike) state.strike.flash = 0;
                        boltMesh.visible = false;
                    }
                    // Protect every scene/terrain consumer from a non-finite or
                    // accidentally amplified flash value. Cadence controls
                    // *when* this occurs; this bound controls only radiance.
                    flash = Number.isFinite(flash)
                        ? Math.max(0, Math.min(1.15, flash))
                        : 0;
                    boltK.value = flash;
                    const impactAfterglow = w.lightning > 0 && state.strike?.local
                        ? Math.exp(-Math.max(0, finiteT - state.strike.time) * 18) * 0.18
                        : 0;
                    const boundedSceneFlash = Math.max(
                        0, Math.min(1, flash + impactAfterglow),
                    );
                    bolt.intensity = boundedSceneFlash * LIGHTNING_LIGHT_PEAK;
                    if (sky.uniforms.lightningFlashColor?.value) {
                        sky.uniforms.lightningFlashColor.value.set(
                            activeStrikeColor.r,
                            activeStrikeColor.g,
                            activeStrikeColor.b,
                        );
                    }
                    if (sky.uniforms.lightningStrike?.value) {
                        const strike = state.strike;
                        sky.uniforms.lightningStrike.value.set(
                            strike?.x ?? 0,
                            Number(sky.uniforms.cloudStart.value),
                            strike?.z ?? 0,
                            flash,
                        );
                    }
                    diagnostics.lightning.palette = w.lightningPalette ?? 'standard';
                    diagnostics.lightning.activeStyle = activeStrikeKey;
                    diagnostics.lightning.flash = flash;
                    diagnostics.lightning.activeEvent = lightningEventPlan !== null;
                    diagnostics.lightning.activeStrokeCount = lightningEventPlan?.count ?? 0;
                    diagnostics.lightning.eventElapsedSeconds = lightningEventPlan
                        ? Math.max(0, finiteT - lightningEventStart)
                        : 0;
                    diagnostics.lightning.nextEventAtSeconds = Number.isFinite(
                        nextLightningEventAt,
                    ) ? nextLightningEventAt : null;
                    if (state.strike
                        && state.strike.interval === lightningEventSeed) {
                        diagnostics.lightning.lastStrike = { ...state.strike };
                    }
                    // Sheet illumination may accompany the same storm event,
                    // but it never runs an independent rapid-fire scheduler.
                    const flashD = Math.max(
                        0,
                        Math.min(0.22, flash * lightningSheetScale),
                    );
                    // Rain is translucent water, not self-emissive paint.
                    // Couple its radiance to the live TOD palette, weather
                    // attenuation, and lightning while retaining a small
                    // overcast skylight floor.
                    const paletteLum = Math.max(
                        0,
                        pal.zen[0] * 0.22 + pal.zen[1] * 0.45 + pal.zen[2] * 0.13
                            + pal.hor[0] * 0.06 + pal.hor[1] * 0.10 + pal.hor[2] * 0.04,
                    );
                    const ambientRain = Math.max(0.06, Math.min(1, paletteLum * 1.35));
                    const weatherLight = 0.32 + Math.max(0.02, w.sunDim) * 0.68;
                    const stormCanopyLegibility = Math.max(
                        0,
                        Math.min(1, Number(sky.uniforms.stormCanopy?.value) || 0),
                    );
                    const stormCanopyRainLegibility = stormCanopyLegibility * Math.max(
                        0,
                        Math.min(1, Number(u.rainK.value) || 0),
                    );
                    // Heavy rain must remain readable under a canopy that has
                    // correctly removed direct sun. This is a low diffuse sky
                    // floor, not self-emission; ordinary weather is unchanged.
                    const rainAmbientFloor = 0.08 + stormCanopyRainLegibility * 0.14;
                    u.rainLight.value = Math.min(
                        2.4,
                        rainAmbientFloor
                            + ambientRain * weatherLight
                            + flash * 1.6
                            + flashD * 0.8,
                    );
                    // Water streaks inherit the live sky chroma as well as its
                    // luminance. This keeps rain warm under sunset/moonlight,
                    // cool under an overcast deck, and briefly blue-white in
                    // lightning instead of rendering as fixed emissive paint.
                    const sceneRgb = [
                        pal.zen[0] * 0.58 + pal.hor[0] * 0.42,
                        pal.zen[1] * 0.58 + pal.hor[1] * 0.42,
                        pal.zen[2] * 0.58 + pal.hor[2] * 0.42,
                    ];
                    const scenePeak = Math.max(0.04, ...sceneRgb);
                    const sceneTint = sceneRgb.map((channel) => Math.max(0.08, Math.min(1, channel / scenePeak)));
                    const waterBase = [0.72, 0.78, 0.86];
                    const localLightningTint = Math.min(1, flash * 1.5);
                    const distantLightningTint = Math.min(1, flashD * 0.6);
                    const litRain = waterBase.map((channel, i) => {
                        const skyTinted = channel * (0.68 + sceneTint[i] * 0.32);
                        const localColor = [
                            activeStrikeColor.r,
                            activeStrikeColor.g,
                            activeStrikeColor.b,
                        ][i];
                        const locallyLit = skyTinted
                            + (localColor - skyTinted) * localLightningTint;
                        const distantColor = [0.82, 0.90, 1.0][i];
                        return locallyLit
                            + (distantColor - locallyLit) * distantLightningTint;
                    });
                    u.rainColor.value.set(...litRain);
                    diagnostics.precipitation.sceneLight = Number(u.rainLight.value);
                    diagnostics.precipitation.sceneColor = [...litRain];
                    const g = w.grey * k, d = 1 - (1 - w.dark) * k, gt = w.greyTint;
                    // horMul: storms need the horizon DARKER than its luminance,
                    // not just desaturated — the bright haze band reads sunny
                    const horMul = 1 - (1 - (w.horMul ?? 1)) * k;
                    const mixG = (rgb, s) => {
                        const l = (rgb[0] * 0.35 + rgb[1] * 0.5 + rgb[2] * 0.15) * s;
                        return [
                            (rgb[0] + (l * gt[0] - rgb[0]) * g) * d * s + flash * activeStrikeColor.r * 0.44,
                            (rgb[1] + (l * gt[1] - rgb[1]) * g) * d * s + flash * activeStrikeColor.g * 0.44,
                            (rgb[2] + (l * gt[2] - rgb[2]) * g) * d * s + flash * activeStrikeColor.b * 0.44,
                        ];
                    };
                    sky.uniforms.zenith.value.set(...mixG(pal.zen, 1.0));
                    const hz = mixG(pal.hor, horMul);
                    sky.uniforms.horizon.value.set(hz[0] + flashD * 0.55, hz[1] + flashD * 0.60, hz[2] + flashD * 0.78);
                }
                diagnostics.precipitation.rainVisible = rainInst.visible;
                diagnostics.precipitation.intensity = Number(u.rainK.value);
                wetnessStats.wetness = Number(u.wetness.value);
                return true;
            },
            dispose() {
                if (disposed) return;
                disposed = true;
                if (weatherRegistry.get(scene) === sys) weatherRegistry.delete(scene);
                sys._trans = null;
                // Terrain and the reflection probe survive skybox rebuilds;
                // restore their original roots so wrappers cannot stack.
                for (const [mat, roots] of wrappedRoots) {
                    mat.colorNode = roots.colorNode ?? null;
                    mat.roughnessNode = roots.roughnessNode ?? null;
                    mat.metalnessNode = roots.metalnessNode ?? null;
                    mat.needsUpdate = true;
                }
                wrapped.clear();
                wrappedRoots.clear();
                receiverMeshes.clear();
                receiverNames.length = 0;
                bolt.intensity = 0;
                boltK.value = 0;
                boltChannelK.value = 0;
                boltMesh.visible = false;
                if (sky?.uniforms?.lightningStrike?.value) {
                    sky.uniforms.lightningStrike.value.w = 0;
                }
                scene.remove(rainInst, splashInst, bolt, boltMesh, ...impactObjects);
                rainInst.dispose?.();
                splashInst.dispose?.();
                for (const slot of impactSlots) {
                    slot.sparks.dispose?.();
                    slot.puffs.dispose?.();
                    slot.sparkMaterial.dispose();
                    slot.puffMaterial.dispose();
                }
                for (const scorch of scorchSlots) scorch.material.dispose();
                rainGeo.dispose();
                splashGeo.dispose();
                boltGeo.dispose();
                impactSparkGeometry.dispose();
                impactPuffGeometry.dispose();
                scorchGeometry.dispose();
                rainMat.dispose();
                splashMat.dispose();
                boltMat.dispose();
            },
        };
        weatherRegistry.set(scene, sys);
        return sys;
    };
    console.log('[weather_system] makeWeatherSystem v2 — world-tiled deterministic rain, water-look streaks, live palette greying, hash-scheduled lightning, wetness/puddles');
})();
