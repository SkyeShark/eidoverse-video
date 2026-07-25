// weather_audio.js — RAIN + THUNDER for the world-space weather system.
//
//   eval(Deno.readTextFileSync('eidoverse/weather_audio.js'));
//   const wxAudio = globalThis.makeWeatherAudio({ weather, camera });
//   // per frame, AFTER weather.update(t, camera):
//   wxAudio.update(t);
//   // once the render finishes (globalThis.cleanup is a good place):
//   Deno.writeTextFileSync('work/<id>/wx_audio.json', wxAudio.toJSON());
//   // bake it to a track and mux it onto the video:
//   //   python bake_weather_audio.py work/<id>/wx_audio.json --out wx.wav --duration <d>
//   //   python merge_av.py --video scene.mp4 --audio wx.wav --out final.mp4
//
// WHY THIS RECORDS INSTEAD OF PLAYS
// The Eanpa browser build drives these clips through Web Audio — gain nodes,
// HRTF PannerNodes, scheduled sources. Deno has no Web Audio API, and this
// renderer writes frames to ffmpeg rather than to a speaker, so there is no
// audio graph to build and no realtime clock to schedule against. This
// records WHAT fires, WHEN, and WHERE; the baker renders that offline.
//
// SPATIALIZATION IS NOT LOST — it moves offline, where it is actually
// cheaper. Each event carries its distance and listener-relative azimuth,
// and the Web Audio 'inverse' distance model is evaluated here in closed
// form (identical formula, same per-path refDistance/maxDistance/rolloff as
// the browser panners) so the baker only has to apply a gain and a pan.
// Offline has no realtime budget, so a bake can go further than a browser
// ever could — full HRTF convolution via ffmpeg's sofalizer, for one.
//
// Rain and thunder only, deliberately: footsteps, birds, doors, flashlight
// and the desert-wind bed belong to the Eanpa sample scene, not to weather.
(function () {
    const A = 'eidoverse/assets/sky/audio/';
    const CLIPS = {
        rain: A + 'rain_desert_loop.ogg',
        thunderClose: [A + 'thunder_close_01.ogg', A + 'thunder_close_02.ogg', A + 'thunder_close_03.ogg'],
        thunderDistant: [A + 'thunder_distant_01.ogg', A + 'thunder_distant_02.ogg', A + 'thunder_distant_03.ogg'],
        thunderExplosive: [A + 'thunder_explosive_01.wav', A + 'thunder_explosive_02.wav', A + 'thunder_explosive_03.wav'],
    };
    // Measured onsets of the licensed close takes: each recording has dead air
    // before its first transient, so playback starts just before the onset and
    // the clap lands on the beat instead of trailing it.
    const THUNDER_CLOSE_ONSETS = [0.156, 0.118, 0.274];
    const SPEED_OF_SOUND = 343;          // m/s — flash-to-clap delay
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

    // Web Audio 'inverse' distance model, evaluated in closed form.
    // Spec: gain = ref / (ref + rolloff * (clamp(d, ref, max) - ref))
    const distanceGain = (d, { refDistance, maxDistance, rolloffFactor }) => {
        const c = clamp(d, refDistance, maxDistance);
        return refDistance / (refDistance + rolloffFactor * (c - refDistance));
    };

    globalThis.makeWeatherAudio = function makeWeatherAudio({
        weather, camera, rainGain = 0.72, thunderGain = 1, quiet = false,
    } = {}) {
        const events = [];
        const rainCurve = [];
        let previousStrike = null;
        let variation = 0;
        let lastRain = -1;
        const stats = {
            strikes: 0, explosive: 0, close: 0, distant: 0, cracks: 0,
            maxRain: 0, nearestMeters: null, farthestMeters: null,
        };

        // Listener-relative azimuth: 0 = dead ahead, +PI/2 = hard right.
        // Uses the camera's world basis, so it tracks a moving/turning camera.
        const azimuthOf = (cam, sx, sy, sz) => {
            if (!cam?.matrixWorld) return 0;
            const e = cam.matrixWorld.elements;
            const rx = e[0], ry = e[1], rz = e[2];          // camera right (+X)
            const fx = -e[8], fy = -e[9], fz = -e[10];      // camera forward (-Z)
            let dx = sx - cam.position.x, dy = sy - cam.position.y, dz = sz - cam.position.z;
            const len = Math.hypot(dx, dy, dz) || 1;
            dx /= len; dy /= len; dz /= len;
            return Math.atan2(dx * rx + dy * ry + dz * rz, dx * fx + dy * fy + dz * fz);
        };

        const emit = (clip, t, distance, azimuth, opts = {}) => {
            const sp = opts.spatial;
            const dg = sp ? distanceGain(distance, sp) : 1;
            events.push({
                clip,
                t: Math.max(0, Number(t.toFixed(4))),
                gain: Number(((opts.gain ?? 1) * thunderGain * dg).toFixed(5)),
                rate: Number((opts.rate ?? 1).toFixed(4)),
                offset: Number((opts.offset ?? 0).toFixed(4)),
                // pan: -1 hard left .. +1 hard right (sin of azimuth; a stereo
                // bus cannot express front/back, and sin folds rear sources to
                // the correct side, which is the standard 2-channel reduction)
                pan: Number(Math.sin(azimuth).toFixed(4)),
                distance: Math.round(distance),
                ...(opts.lowpassHz ? { lowpassHz: opts.lowpassHz } : {}),
                ...(opts.highpassHz ? { highpassHz: opts.highpassHz } : {}),
                ...(opts.stopAfter ? { stopAfter: opts.stopAfter } : {}),
            });
        };

        // Ported from the standalone's triggerThunder, decision for decision.
        const triggerThunder = (t, { distant, local, distance, delay, azimuth }) => {
            const i = variation++;
            const rate = 0.93 + ((i * 11) % 11) * 0.014;
            const at = t + delay;
            stats.strikes++;
            if (stats.nearestMeters === null || distance < stats.nearestMeters) stats.nearestMeters = Math.round(distance);
            if (stats.farthestMeters === null || distance > stats.farthestMeters) stats.farthestMeters = Math.round(distance);

            if (distant) {
                stats.distant++;
                emit(CLIPS.thunderDistant[i % 3], at, distance, azimuth, {
                    gain: 0.64, rate,
                    spatial: { refDistance: 100, maxDistance: 2600, rolloffFactor: 0.38 },
                });
                return;
            }

            // Strikes near the listener get the synthesized explosive clap —
            // sharp crack, tearing mid, deep sub boom — with the licensed
            // rolling take blended in behind it as the long tail. The rolling
            // recordings alone read as distant thunder at any gain.
            if (local || distance <= 150) {
                stats.explosive++; stats.cracks++;
                emit(CLIPS.thunderExplosive[i % 3], at, distance, azimuth, {
                    gain: 1.9, rate,
                    spatial: { refDistance: 80, maxDistance: 1600, rolloffFactor: 0.4 },
                });
                emit(CLIPS.thunderClose[i % 3], at + 0.35, distance, azimuth, {
                    gain: 0.62, rate, lowpassHz: 5200,
                    offset: Math.max(0, THUNDER_CLOSE_ONSETS[i % 3] - 0.035),
                    spatial: { refDistance: 90, maxDistance: 2200, rolloffFactor: 0.34 },
                });
                return;
            }

            stats.close++;
            const onset = THUNDER_CLOSE_ONSETS[i % 3];
            emit(CLIPS.thunderClose[i % 3], at, distance, azimuth, {
                gain: 0.90, rate, lowpassHz: 8200,
                offset: Math.max(0, onset - 0.035),
                spatial: { refDistance: 90, maxDistance: 2200, rolloffFactor: 0.34 },
            });
            // The 150-360 m ring still layers an immediate high-passed crack
            // over the rolling body so mid-range strikes keep electrical snap.
            if (distance <= 180) {
                stats.cracks++;
                emit(CLIPS.thunderClose[i % 3], at, distance, azimuth, {
                    gain: 0.92, rate, highpassHz: 1150, stopAfter: 0.72, offset: onset,
                    spatial: { refDistance: 55, maxDistance: 1400, rolloffFactor: 0.44 },
                });
            }
        };

        return {
            stats,
            // Call once per frame with the SAME t the renderer uses.
            update(t) {
                const wx = weather ?? globalThis._weather;
                const cam = camera ?? globalThis._c;
                if (!wx) return;

                // rain bed — squared so light rain stays under the mix,
                // matching the standalone's rainGain curve
                const rain = clamp(Number(wx.uniforms?.rainK?.value ?? 0), 0, 1);
                const g = rain * rain * rainGain;
                if (Math.abs(g - lastRain) > 0.01) {
                    rainCurve.push({ t: Number(t.toFixed(3)), gain: Number(g.toFixed(4)) });
                    lastRain = g;
                }
                if (rain > stats.maxRain) stats.maxRain = rain;

                // thunder — one event per NEW strike, gated on the flash
                const strike = wx.state?.strike;
                if (!strike) return;
                const key = strike.id
                    ?? `${strike.x?.toFixed?.(2)},${strike.y ?? 0},${strike.z?.toFixed?.(2)}`;
                if (key === previousStrike || !(Number(strike.flash ?? 0) > 0.03)) return;
                previousStrike = key;

                const sx = Number(strike.x), sy = Number(strike.y ?? 0), sz = Number(strike.z);
                const distance = Math.hypot(
                    sx - Number(cam?.position?.x ?? 0),
                    sy - Number(cam?.position?.y ?? 0),
                    sz - Number(cam?.position?.z ?? 0),
                );
                triggerThunder(t, {
                    distant: distance > 360,
                    local: strike.local === true,
                    distance,
                    delay: distance / SPEED_OF_SOUND,
                    azimuth: azimuthOf(cam, sx, sy, sz),
                });
                if (!quiet) {
                    console.log(`[weather_audio] strike t=${t.toFixed(2)}s d=${distance.toFixed(0)}m `
                        + `delay=${(distance / SPEED_OF_SOUND).toFixed(2)}s`);
                }
            },
            timeline() {
                return { rainClip: CLIPS.rain, rain: rainCurve, events, stats };
            },
            toJSON() { return JSON.stringify(this.timeline(), null, 1); },
        };
    };
})();
