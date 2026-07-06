// old_bw_film.js — TSL port of custom_effects.js::old_bw_film.
// Early-cinema monochrome pass: 12fps stutter, gate-weave UV jitter,
// animated film-dirt noise, channel-modulated dust speckles, slow
// vignette, hard jump cut at the 7.7-8.2s mark of a 24s sequence loop,
// final luminance desat.
//
// Public API:
//   OldBWFilmFX.applyTo({ opts });
//
// Options:
//   opacity float — final blend with original (default 1.0)
//   width/height int — output resolution (defaults to globalThis.WIDTH/HEIGHT)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[old_bw_film] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildOldBWFilmHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv,
            sin, cos, mod, mix, clamp, pow, step, smoothstep, fract, dot, floor,
        } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1920;
        const h = opts.height ?? globalThis.HEIGHT ?? 1080;

        const u = {
            time:        uniform(0),
            opacity:     uniform(opts.opacity ?? 1.0),
            iResolution: uniform(new THREE.Vector2(w, h)),
        };

        const SEQUENCE_LENGTH = 24.0;
        const FPS = 12.0;

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            setResolution(width, height) { u.iResolution.value.set(width, height); },
            hook(colorIn /*, depth, normal, mr */) {
                const colorTex = THREE.convertToTexture(colorIn);

                return Fn(() => {
                    const uvBase = uv();
                    const iRes = u.iResolution;
                    const iTime = u.time;
                    const origIn = colorTex.sample(uvBase);

                    // ---- Hash + simplex-noise helpers (replace tNoise.sample) ----
                    // v2random: per-input hash, for places we need uncorrelated
                    // values (per-frame seed, jitter calcs).
                    const v2random = (p) =>
                        fract(sin(p.x.mul(127.1).add(p.y.mul(311.7))).mul(43758.5453));
                    // hash22: 2-channel hash, returns vec2 in [-1,+1] for
                    // simplex gradient lookup at lattice corners.
                    const hash22 = (p) => {
                        const q = vec2(
                            p.x.mul(127.1).add(p.y.mul(311.7)),
                            p.x.mul(269.5).add(p.y.mul(183.3)),
                        );
                        return fract(vec2(sin(q.x), sin(q.y)).mul(43758.5453))
                            .mul(2).sub(1);
                    };
                    // simplex2D: skewed-triangular noise, returns roughly
                    // [-1,+1]. Cells are NOT axis-aligned (tilted 30°), so
                    // the grid structure that value-noise shows after
                    // thresholding does NOT appear here — that was the source
                    // of the "seams + pixelation" we kept hitting. Output
                    // remapped to [0,1] for downstream threshold use.
                    const K1 = 0.366025404;       // (sqrt(3)-1)/2
                    const K2 = 0.211324865;       // (3-sqrt(3))/6
                    const K2_TIMES_2 = 0.42264973; // 2*K2 (precomputed)
                    const simplexNoise = (p) => {
                        const sumXY = p.x.add(p.y).mul(K1);
                        const i = floor(p.add(sumXY));
                        const sumI = i.x.add(i.y).mul(K2);
                        const a = p.sub(i).add(sumI);
                        // o = (a.x > a.y) ? (1,0) : (0,1)
                        const aGtY = step(a.y, a.x);
                        const o = vec2(aGtY, float(1).sub(aGtY));
                        const b = a.sub(o).add(K2);
                        const c = a.sub(1).add(K2_TIMES_2);
                        const h = clamp(
                            float(0.5).sub(vec3(
                                dot(a, a),
                                dot(b, b),
                                dot(c, c),
                            )),
                            0, 1,
                        );
                        const h4 = h.mul(h).mul(h).mul(h);
                        const n = h4.mul(vec3(
                            dot(a, hash22(i)),
                            dot(b, hash22(i.add(o))),
                            dot(c, hash22(i.add(vec2(1, 1)))),
                        ));
                        return dot(n, vec3(70)).mul(0.5).add(0.5);  // [0,1]
                    };
                    // 3 channels with LARGE non-integer offsets.
                    const noise3 = (p) => vec3(
                        simplexNoise(p),
                        simplexNoise(p.add(vec2(127.3, 911.7))),
                        simplexNoise(p.add(vec2(643.7, 311.9))),
                    );

                    // ---- 12fps time-quantization (silent-era cadence) ----
                    const tMod = mod(iTime, SEQUENCE_LENGTH);
                    const time = floor(tMod.mul(FPS)).div(FPS);

                    // ---- Jump cut at 7.7s → 8.2s within the sequence loop ----
                    // Only `.w` (toffset) is referenced by the original main(),
                    // so we skip the unused camoffset.xyz term.
                    const jct1 = float(7.7);
                    const jct2 = float(8.2);
                    const jc1 = step(jct1, time);
                    const jc2 = step(jct2, time);
                    const toffset = float(0.8).mul(jc1)
                                    .sub(jc2.sub(jc1).mul(time.sub(jct1)))
                                    .sub(float(0.9).mul(jc2));

                    // ---- Gate weave: small UV jitter per frame ----
                    const moveX = float(0.002).mul(cos(time.mul(3)).mul(sin(time.mul(12).add(0.25))));
                    const moveY = float(0.002).mul(sin(time.mul(1).add(0.5)).mul(cos(time.mul(15).add(0.25))));
                    const movedUV = vec2(uvBase.x.add(moveX), uvBase.y.add(moveY));
                    const image = colorTex.sample(movedUV);

                    // ---- Centered, aspect-corrected coords for dirt sampling ----
                    const qq = uvBase.mul(2).sub(1);
                    const aspect = iRes.x.div(iRes.y);
                    const pp = vec2(qq.x.mul(aspect), qq.y);

                    // ---- filmDirt: single value-noise sample, sparse spots ----
                    // The original GLSL summed 3 noise-texture taps at varying
                    // scales — but its lowest two octaves were nearly uniform
                    // per-frame so the spatial pattern came almost entirely
                    // from the highest octave. Replicating with a single
                    // value-noise call at the right scale gives the same look
                    // without the cross-octave gradient-seam artifacts that
                    // appeared with multi-octave or FBM stacking.
                    const dirtTime = time.add(toffset);
                    const nseLookup = pp.add(vec2(0.5, 0.9)).add(dirtTime.mul(100));
                    // Simplex at scale 8 → dust spots ~80px, organically
                    // shaped (no axis-aligned grid), with soft edges from
                    // the simplex falloff functions.
                    const nse2 = noise3(nseLookup.mul(8));

                    // Coarse "dust region" mask — a few blobs across the
                    // screen. Multiplies into the fine dust mask so dust
                    // only appears INSIDE those regions, leaving most of
                    // the frame clean. Without this, dust covers the whole
                    // screen uniformly.
                    const region1 = simplexNoise(nseLookup.mul(1.2));
                    const region2 = simplexNoise(nseLookup.mul(1.2).add(vec2(127.3, 911.7)));
                    const region3 = simplexNoise(nseLookup.mul(1.2).add(vec2(643.7, 311.9)));
                    // Keep only the top ~10% of region values — typically
                    // 0–1 dust-allowed blob per frame. Frame is mostly
                    // clean with one isolated cluster of specks when dust
                    // hits at all.
                    const regionMask1 = smoothstep(0.70, 0.88, region1);
                    const regionMask2 = smoothstep(0.70, 0.88, region2);
                    const regionMask3 = smoothstep(0.70, 0.88, region3);

                    // Threshold catches only the deepest noise valleys —
                    // sparse dust spots within the dust-allowed regions.
                    // The fine dust mask is then mixed with `1` outside the
                    // region (no dust) and the fine value inside (dust).
                    const fine1 = smoothstep(0.10, 0.30, nse2.x);
                    const fine2 = smoothstep(0.10, 0.30, nse2.y);
                    const fine3 = smoothstep(0.10, 0.30, nse2.z);
                    const mul1 = mix(float(1), fine1, regionMask1);
                    const mul2 = mix(float(1), fine2, regionMask2);
                    const mul3 = mix(float(1), fine3, regionMask3);

                    // Per-frame seed — same value across all pixels of a frame.
                    const seed = v2random(vec2(time.mul(0.35), time));

                    // Baseline dirt brightness with two slow ramps.
                    const easeInPair = (t0, t1, t) =>
                        smoothstep(t0, float(2).mul(t1).sub(t0), t).mul(2);
                    const baseDirt = clamp(seed.add(0.7), 0, 1)
                                     .add(easeInPair(float(0), float(SEQUENCE_LENGTH), time).mul(0.3))
                                     .add(easeInPair(float(19.2), float(19.4), time).mul(0.06));

                    // Seed bands trigger channel-specific dust speckles.
                    const band = float(0.05);
                    const inB1 = step(0.3, seed).mul(step(seed, float(0.3).add(band)));
                    const inB2 = step(0.6, seed).mul(step(seed, float(0.6).add(band)));
                    const inB3 = step(0.9, seed).mul(step(seed, float(0.9).add(band)));
                    let channelMul = mix(float(1), mul1, inB1);
                    channelMul = mix(channelMul, mul2, inB2);
                    channelMul = mix(channelMul, mul3, inB3);
                    const dirt = channelMul.mul(baseDirt);

                    // ---- Vignette (slow flicker via vig power modulation) ----
                    const vu = uvBase.mul(vec2(float(1).sub(uvBase.y), float(1).sub(uvBase.x)));
                    const vigBase = vu.x.mul(vu.y).mul(15);
                    const vigT = sin(time.mul(23)).mul(cos(time.mul(8).add(0.5)));
                    const vig = pow(vigBase, float(0.4).add(vigT.mul(0.05)));

                    // ---- B&W luma + composite ----
                    const lit = image.rgb.mul(dirt).mul(vig);
                    const luma = dot(lit, vec3(0.299, 0.587, 0.114));
                    const effect = vec4(vec3(luma), image.a);

                    return mix(origIn, effect, u.opacity);
                })();
            },
        };
    }

    function applyTo(opts) {
        opts = opts || {};
        const built = buildOldBWFilmHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.OldBWFilmFX = { applyTo };
    console.log('[old_bw_film] OldBWFilmFX.applyTo registered');
})();
