// sky_worlds.js — THE scene-facing sky API. One call selects a whole world.
//
//   eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
//   const sky = await globalThis.makeSky({
//       scene, camera, renderer, world: 'ringworld', sun, hemi });
//   // per frame, ONE call — it owns the ordering:
//   sky.update(t);
//
// WHY THIS EXISTS
// Scenes used to ASSEMBLE a world from parts: load the ring GLB, the landmask,
// the solar-panel PBR set, the band normal/AO, a planet texture, place the band
// at its authored height, set its composite order, hand the sky its curvature
// and the planet's angular size, then add a hand-aimed light to make the band
// visible. Consequences, all of which bit:
//   * the world was defined by scene config in work/ (gitignored scratch), so a
//     probe config could point the ringworld's companion body at Earth's moon
//     and nothing objected — the wrong planet rendered silently;
//   * scene-side lighting of a sky element was fixed in place and unrelated to
//     the time of day, so the band read as night in the day and day at night;
//   * the same freedom let a stale per-state weather table and retired state
//     names drift out of step with the engine.
// A world is not a bag of assets a scene fills in. Selecting 'ringworld' must
// GIVE you the ringworld, period. So every asset, mesh, celestial body, curve,
// placement and per-frame call now lives in here, and the scene cannot
// substitute any of it.
//
// THE WHOLE SCENE-FACING SURFACE (there is deliberately nothing else):
//   sky.setTime(hours)                      set time of day
//   sky.dayCycle({ startHour, seconds })    run a day/night cycle
//   sky.setClouds(type)                     clear | cumulus | stratus | cirrus
//   sky.setWeather(name, k)                 clear|fair|sunshower|overcast|
//                                           rain|storm|cyclone|darkstorm
//   sky.transitionTo(name, k, seconds)      eased weather change
//   sky.setColors({ cloud, sun, rain, star, shield })   per-channel retints
//   sky.update(t)                           REQUIRED per frame; owns ordering
//
// Look-dev internals (cloud morphology, terminator shaping, cache tiers,
// atmospheric terms, band lighting) are NOT exposed. They belong to the world.
(function () {
    const A = 'eidoverse/assets/sky/';
    const C = A + 'celestial/';
    const readTex = async (p, srgb) => globalThis.loadImageTexture(
        Deno.readFileSync(p), srgb ? { srgb: true } : {},
    );
    // Engine-side debug gates. These are ENGINE knobs, deliberately read here
    // rather than accepted as parameters — a scene tuning cache tiers or cloud
    // pass counts is a scene doing look development it does not own.
    const env = (k) => globalThis.Deno?.env?.get?.(k);

    // ---- THE THREE WORLDS ------------------------------------------------
    // Names as they appear in Eanpa. Each entry is complete: nothing here may
    // be overridden by a scene.
    const WORLDS = {
        earth: {
            label: 'Earth',
            starmap: A + 'starmap_tycho_4k.jpg',
            moonmap: A + 'moon_color_1k.jpg',
            sky: { moonAngularDeg: 0.55 },
        },
        ringworld: {
            label: 'Orbital / Halo',
            starmap: A + 'starmap_tycho_4k.jpg',
            // the companion body is a ROCK GIANT of orange mineral — not a
            // grey moon, and not swappable
            moonmap: C + 'rock_giant.png',
            // what it reflects is a warm near-white. A grey moon reflects cool
            // light because it is GREY; moonlight is not intrinsically blue.
            planetShine: [1.00, 0.92, 0.82],
            sky: {
                ringCurve: 5000,          // the cloud deck bows up along the arc
                moonAngularDeg: 16,       // ~10x luna: a looming companion world
            },
            band: {
                glb: C + 'RINGWORLDskyelement.glb',
                landmask: C + 'ringworldlandmask.png',
                solarColor: C + 'SolarPanel001_1K-JPG_Color.jpg',
                solarNormal: C + 'SolarPanel001_1K-JPG_NormalGL.jpg',
                solarRough: C + 'SolarPanel001_1K-JPG_Roughness.jpg',
                solarMetal: C + 'SolarPanel001_1K-JPG_Metalness.jpg',
                bandNormal: C + 'ring_band_normal.png',
                bandAO: C + 'ring_band_ao.png',
                // the height field the normal map was derived from — SPOM
                // ray-marches this so ridges actually occlude what is behind them
                bandHeight: C + 'ring_band_height.png',
                // AUTHORED placement — the export framed it this way: ring
                // centre ~4940 m up, so the lowest arc plunges into the ground
                // ~1.2 km away, the band rises from the horizon at your feet
                // and crests ~9.8 km overhead. Straight up: no lateral offset,
                // no tilt. This is world geometry, not scene dressing.
                centerY: 4940,
            },
        },
        shieldworld: {
            label: 'Earth 5129323011 CE (Red Giant)',
            // the ONLY package with a shield, so the only one where a shield
            // colour means anything
            shield: true,
            starmap: A + 'starmap_tycho_4k.jpg',
            // NO moonmap. This world's companion is not a disc composited into
            // the sky — it is the SHATTERED MOON, a real GLB cluster of fragments
            // strung along its orbit, so giving the sky a moon texture as well
            // would hang a second moon next to it.
            moon: {
                glb: C + 'asteroid_cluster_v3.glb',
                baked: C + 'asteroid_moon_baked.png',
                normal: C + 'asteroid_moon_normal.png',
                // CINEMATIC scale: ~4x the astronomically-true 0.5 deg. The
                // assembly HEIGHT reads like the familiar moon, spread wider
                // since the breakup (~14 deg of crumble at spread 1.75). True
                // scale reads as a speck at 52 deg FOV.
                scale: 1400,
                spread: 1.75,
                // draw slot: sky background < moon < shield < clouds. The
                // fragments are in space BEHIND the shield, so the lattice
                // overlays them.
                renderOrder: -99.5,
            },
            // this moon reflects the RED GIANT, so its light is orange
            planetShine: [1.00, 0.60, 0.32],
            sky: {
                // the star subtends ~32 deg, so sunset must stretch across the
                // disc's real width instead of switching at its centre
                sourceAngularRadiusDeg: 0.28 * 180 / Math.PI,
                // the Mie phase peaks ~180x forward, correct only for a ~0.5
                // deg sun; a star this wide needs the lobe broadened
                cloudPhaseSoften: 0.85,
                moonLightIntensity: 1.15,
            },
        },
    };

    globalThis.SKY_WORLDS = Object.freeze(
        Object.fromEntries(Object.entries(WORLDS).map(([k, v]) => [k, v.label])),
    );

    globalThis.makeSky = async function makeSky({
        scene, camera, renderer, world = 'earth', hours = 12, clouds = 'cumulus',
        weather = 'clear', weatherK = 1, sun, hemi, audio = true,
    } = {}) {
        const W = WORLDS[world];
        if (!W) {
            throw new Error(`makeSky: unknown world '${world}'. `
                + `Pick one of: ${Object.keys(WORLDS).join(' | ')}`);
        }
        const balanced = env('TIER') === 'balanced';
        // CACHE=0 kills both; DCACHE=0 / LCACHE=0 bisect them separately. Kept
        // separable because the density cache has a measured backend fault behind
        // it (the fragment stage's reads of its Data3DTexture drift over a run on
        // Deno-wgpu while a compute readback of the same object stays exact), so
        // "is this artifact the density cache?" has to be answerable on its own.
        const noDensity = env('CACHE') === '0' || env('DCACHE') === '0';
        const noLight = env('CACHE') === '0' || env('LCACHE') === '0';

        // ---- the sky itself ------------------------------------------------
        eval(Deno.readTextFileSync('eidoverse/sky_system.js'));
        const textures = { stars: await readTex(W.starmap, true) };
        if (W.moonmap) textures.moon = await readTex(W.moonmap, true);

        // celestial module FIRST where the world has one: the red giant's star
        // must exist before the sky that composites it
        let celestialMod = null, celestialOpts = {};
        if (world === 'shieldworld') {
            eval(Deno.readTextFileSync('eidoverse/redgiant.js'));
            // the shield is part of the package, not a scene choice — it is what
            // makes this world a shieldworld
            celestialMod = await globalThis.makeRedGiant({ opts: { shield: true } });
            celestialOpts = {
                celestial: celestialMod.celestial,
                paletteTint: celestialMod.paletteTint,
            };
        }

        const sky = await globalThis.makeSkySystem({
            scene, textures,
            opts: {
                hours, clouds,
                ...W.sky,
                ...celestialOpts,
                ...(W.planetShine ? { moonLightColor: W.planetShine } : {}),
                // Balanced tier: both caches on. The density cache reads
                // unreliably in the fragment stage on this backend, but
                // disabling it was measured NOT to fix the artifact it was
                // blamed for and costs real speed, so it stays.
                densityCache: noDensity ? undefined : {},
                lightCache: noLight ? undefined : {},
                cloudPasses: balanced ? 3 : undefined,
            },
        });

        // ---- the world's own geometry --------------------------------------
        let band = null;
        if (W.band) {
            eval(Deno.readTextFileSync('eidoverse/ringworld.js'));
            band = await globalThis.makeRingworld({
                glbBytes: Deno.readFileSync(W.band.glb),
                textures: {
                    landmask: await readTex(W.band.landmask, false),
                    solarColor: await readTex(W.band.solarColor, true),
                    solarNormal: await readTex(W.band.solarNormal, false),
                    solarRough: await readTex(W.band.solarRough, false),
                    solarMetal: await readTex(W.band.solarMetal, false),
                    bandNormal: await readTex(W.band.bandNormal, false),
                    bandAO: await readTex(W.band.bandAO, false),
                    bandHeight: await readTex(W.band.bandHeight, false),
                },
                opts: { waves: 'lightweight', planetShineColor: W.planetShine },
            });
            band.group.position.set(0, W.band.centerY, 0);
            // SKY-ELEMENT DEPTH: the viewer is ON the ring, so the far side is
            // beyond the atmosphere and ALL local clouds must render in front of
            // it. The band must NOT write depth — its ~1.2 km world position
            // would beat the cloud dome's ~3 km shell in the depth test and clip
            // low clouds behind it. Composite order:
            //   bg dome (-100) < ring (-99) < cloud dome (-98)
            // and foreground opaques draw later, painting over the depthless
            // band. Getting this wrong is silent and looks like a cloud bug.
            band.group.traverse((o) => {
                if (!o.isMesh) return;
                o.renderOrder = -99;
                const mats = Array.isArray(o.material) ? o.material : [o.material];
                for (const m of mats) if (m) m.depthWrite = false;
            });
            scene.add(band.group);
        }
        // ---- the world's companion body, where it is a MESH rather than a
        // disc composited into the sky --------------------------------------
        let moon = null;
        if (W.moon) {
            // the ENGINE copy. A work/ fork of this module had drifted from it,
            // and because the scene eval'd the fork, engine-side fixes silently
            // did nothing there.
            eval(Deno.readTextFileSync('eidoverse/asteroid_moon.js'));
            moon = await globalThis.makeShatteredMoon({
                glbBytes: Deno.readFileSync(W.moon.glb),
                spread: W.moon.spread,
            });
            moon.group.scale.setScalar(W.moon.scale);
            moon.pieces?.forEach((p) => { p.renderOrder = W.moon.renderOrder; });
            scene.add(moon.group);
            console.log(`[sky_worlds] shattered moon — ${moon.pieces?.length ?? 0} fragments`);
        }
        if (celestialMod?.attach) celestialMod.attach({ scene, sky });

        // ---- weather -------------------------------------------------------
        eval(Deno.readTextFileSync('eidoverse/weather_system.js'));
        const wx = await globalThis.makeWeatherSystem({
            scene, sky,
            opts: {
                textures: {
                    bolt: await readTex('eidoverse/assets/particle_textures/trace_06.png', false),
                    drop: await readTex(A + 'rain_streak.png', true),
                },
            },
        });
        wx.wrapScene();
        // weather: null means "leave the weather system at its own default", which
        // is NOT the same as asking for 'clear'. Every weather state carries a
        // cloud preset — `clear` is `{ clouds: 'clear', ... }` — so naming a state
        // here OVERRIDES the `clouds` argument above. Asking for cumulus clouds and
        // clear weather in the same call silently yields an empty sky, which is
        // exactly what a cloud-preset showcase must not do.
        if (weather) wx.setWeather(weather, weatherK);
        if (band) band.bindWeather(wx, sky);

        // ---- weather audio -------------------------------------------------
        let wxAudio = null;
        if (audio) {
            eval(Deno.readTextFileSync('eidoverse/weather_audio.js'));
            wxAudio = globalThis.makeWeatherAudio({ weather: wx, camera, quiet: true });
        }

        let cyc = null;   // { startHour, seconds } when a day cycle is running
        const L = () => ({
            sun: sun ?? globalThis._sun,
            hemi: hemi ?? globalThis._hemi,
        });

        const api = {
            get world() { return world; },
            get label() { return W.label; },

            setTime(h) { cyc = null; sky.setTime(((h % 24) + 24) % 24); return api; },
            dayCycle({ startHour = 6, seconds = 60 } = {}) {
                cyc = { startHour, seconds };
                return api;
            },
            setClouds(type, shape) { sky.setClouds(type, shape); return api; },
            // eased cloud-preset change: morphs coverage, vertical profile and the
            // 2D/high-cloud terms together rather than snapping the field
            transitionClouds(type, seconds = 2.5) {
                sky.transitionClouds(type, seconds); return api;
            },
            setWeather(name, k = 1) { wx.setWeather(name, k); return api; },
            transitionTo(name, k = 1, seconds = 45) {
                wx.transitionTo(name, k, seconds); return api;
            },
            // FIVE channels, every one optional and independent. Omit a channel
            // and it keeps the package's authored colour; setColors({}) changes
            // nothing. These are tints over a dialled-in look, not replacements
            // for it.
            //   star    the star's light and its disc
            //   cloud   tints every cloud layer together
            //   sky     the atmosphere: zenith + horizon, and everything reading
            //           them (fog, haze, the rain curtain)
            //   rain    the raindrops and their splashes
            //   shield  RED GIANT ONLY — the other packages have no shield
            setColors(c = {}) {
                if (c.shield !== undefined && !W.shield) {
                    console.warn(`[sky_worlds] setColors: '${world}' has no shield, so `
                        + 'a shield colour has nothing to apply to — ignored. The shield '
                        + 'belongs to the red giant package.');
                }
                sky.setColors?.({
                    cloud: c.cloud,
                    star: c.star ?? c.sun,
                    sky: c.sky,
                    shield: W.shield ? c.shield : undefined,
                });
                if (c.rain) wx.setColors?.({ rain: c.rain });
                return api;
            },
            // the weather finds whatever ground the SCENE built and wraps its
            // materials for wetness and puddles — the engine supplies no ground
            // and makes no assumption about what one looks like. Already run at
            // construction; call it again after adding geometry later.
            wrapScene() { wx.wrapScene(); return api; },

            // ONE per-frame call. The ordering below is not arbitrary and
            // getting it wrong fails silently, which is exactly why scenes
            // should not be doing it by hand:
            //   time -> sky -> weather (writes the strike/flash state)
            //   -> audio (reads that state) -> band -> lights -> caches
            update(t) {
                const cam = camera ?? globalThis._c;
                if (cyc) {
                    const h = (cyc.startHour + t * (24 / cyc.seconds)) % 24;
                    sky.setTime(h);
                }
                // the companion body's own orbit, on the SAME clock the sky runs
                // on, so it rises and sets with the cycle instead of sitting in
                // one spot wiggling. Rises ~22.3h into the night, transits in
                // 6.2h so the full fall completes before dawn. The arc stays
                // outside the shield's 21k lattice at every point — a smaller
                // radius punches the fragments through it.
                if (moon) {
                    const hM = cyc
                        ? (cyc.startHour + t * (24 / cyc.seconds)) % 24
                        : sky.state.hours;
                    const th = (((hM - 22.3) + 24) % 24) / 6.2 * Math.PI;
                    moon.group.position.set(
                        Math.cos(th) * 34000, Math.sin(th) * 22000 + 2000, -12000);
                    moon.group.rotation.set(t * 0.01, t * 0.017, 0);
                }
                sky.update(t, cam);
                wx.update(t, cam);
                wxAudio?.update(t);
                band?.update(t);
                celestialMod?.update?.(t);
                // LIGHTING IS NOT OPT-IN. The palette drives the scene's sun, hemi
                // and fog here, every frame, because a sky that does not light the
                // world is not a working sky — an agent should never have to call
                // something to get basic lighting, and one that forgets gets the
                // frozen-noon bug that this owning-the-ordering exists to prevent.
                //
                // A scene that garnishes the result (an eclipse dimming, a night
                // ambient floor) layers it AFTER update(t), which is the natural
                // frame order anyway: update, then adjust, then render.
                api.applyToLights();
                // the cloud light cache must be refreshed EVERY frame or it
                // stays pinned to a stale camera/sun and draws a hard straight
                // line across the clouds; it self-throttles internally
                sky.prepareOptimizedCaches?.(renderer ?? globalThis._r, cam);
                return api;
            },

            // Bakes the environment. Where the world has a band, the band goes
            // INTO the bake — it is part of this world's sky, so reflections and
            // env-IBL must carry the arc. The scene does not know that, and
            // should not have to.
            async bakeEnv(extra = {}) {
                const opts = { ...extra };
                if (band) {
                    opts.ringworld = {
                        centerY: W.band.centerY,
                        radius: band.info.radius,
                        halfWidth: band.info.halfWidth,
                        repeat: band.info.repeat,
                        map: band.info.mapTex,
                        mask: band.info.maskTex,
                    };
                }
                await sky.bakeEnv(renderer ?? globalThis._r, opts);
                return api;
            },
            enableReflections(o) { sky.enableReflections?.(camera ?? globalThis._c, o); return api; },
            // Called by update() automatically — a scene does not need this. It
            // stays public only for the setup-time call, before the first frame.
            applyToLights() {
                const { sun: s, hemi: h } = L();
                sky.applyToLights({ sun: s, hemi: h, fog: scene.fog });
                if (s) s.intensity *= wx.sunDim();
                if (h) h.intensity *= (0.5 + wx.sunDim() * 0.5);
                return api;
            },
            audioTimeline() { return wxAudio?.toJSON?.() ?? null; },
            get audio() { return wxAudio; },
            get planetShine() { return W.planetShine ? [...W.planetShine] : null; },

            // escape hatch for engine work ONLY — not a scene surface
            _internals: { sky, wx, band, celestialMod, wxAudio, moon },
        };
        console.log(`[sky_worlds] ${world} — ${W.label}`
            + (band ? ` (band r=${band.info.radius} at y=${W.band.centerY})` : ''));
        return api;
    };
})();
