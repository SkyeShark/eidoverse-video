// depth_rain.js — full WORLD-SPACE weather pass, TSL port of the WebGL-era
// custom_effects.js depth_rain. Distinct from rain_on_camera (lens droplets):
// everything here is driven by depth + reconstructed world position so the
// rain interacts with the scene geometry:
//   1. falling streaks (3 parallax layers, wind tilt, depth-attenuated)
//   2. ground detection + organic puddle splotches (world.xz fbm) with
//      refractive ripples, fresnel sky reflection, splash rings
//   3. splash droplets on ANY upward-facing surface (roofs, hoods, wings)
//   4. screen-space cover occlusion — surfaces under an overhang stay dry
//
// Public API: DepthRainFX.applyTo({ camera, opts })
// opts: intensity (0.7) · streakSpeed (1.0) · windTilt (0.10) ·
//   rainColor ([0.78,0.86,1.0]) · puddleStrength (0.7) ·
//   puddleColor ([0.70,0.80,0.95]) · puddleCoverage (0.45) · groundY (0.0) ·
//   groundBand (50.0) · groundNormalThreshold (0.85) ·
//   splashNormalThreshold (0.50) · splashRate (1.5, auto-scales with
//   intensity) · coverHeight (3.0) · wetDarken (0.35 — global wet-surface
//   darkening, port improvement) · rainHaze (0.15 — depth haze, port
//   improvement) · opacity (1.0)
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[depth_rain] THREE global not present — skipping'); return; }

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        const camera = args.camera || globalThis._c || globalThis._camera;
        if (!camera) throw new Error('[depth_rain] camera required (args.camera or globalThis._c)');

        const { uniform } = THREE;
        const u = {
            iTime:        uniform(0),
            opacity:      uniform(opts.opacity ?? 1.0),
            intensity:    uniform(opts.intensity ?? 0.7),
            streakSpeed:  uniform(opts.streakSpeed ?? 1.0),
            windTilt:     uniform(opts.windTilt ?? 0.10),
            rainColor:    uniform(new THREE.Color(...(opts.rainColor || [0.78, 0.86, 1.0]))),
            puddleStrength: uniform(opts.puddleStrength ?? 0.7),
            puddleColor:  uniform(new THREE.Color(...(opts.puddleColor || [0.70, 0.80, 0.95]))),
            puddleCoverage: uniform(opts.puddleCoverage ?? 0.45),
            groundY:      uniform(opts.groundY ?? 0.0),
            groundBand:   uniform(opts.groundBand ?? 50.0),
            groundNormalThreshold: uniform(opts.groundNormalThreshold ?? 0.85),
            splashNormalThreshold: uniform(opts.splashNormalThreshold ?? 0.50),
            splashRate:   uniform(opts.splashRate ?? 1.5),
            coverHeight:  uniform(opts.coverHeight ?? 3.0),
            wetDarken:    uniform(opts.wetDarken ?? 0.35),   // global wet-surface darkening on upward faces
            rainHaze:     uniform(opts.rainHaze ?? 0.15),    // depth-driven atmospheric haze toward rainColor
            invProj:      uniform(new THREE.Matrix4()),
            camWorld:     uniform(new THREE.Matrix4()),
            proj:         uniform(new THREE.Matrix4()),
            view:         uniform(new THREE.Matrix4()),
            resolution:   uniform(new THREE.Vector2(globalThis.WIDTH || 1280, globalThis.HEIGHT || 720)),
        };

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth) => {
            const {
                Fn, vec2, vec3, vec4, float, uv, convertToTexture,
                fract, floor, sin, cos, dot, mix, smoothstep, step, clamp,
                length, abs, max, min, normalize, cross, pow, sign, Loop, mat2,
            } = THREE;
            const colorTex = convertToTexture(colorOut);
            const depthTex = convertToTexture(sceneDepth);

            const hash21 = (p) => {
                const q = fract(p.mul(vec2(123.34, 456.21)));
                const q2 = q.add(dot(q, q.add(45.32)));
                return fract(q2.x.mul(q2.y));
            };
            const puddleFbm = (p) => {
                const a = sin(p.x.mul(0.55).add(0.7)).mul(cos(p.y.mul(0.45).sub(0.3)));
                const b = sin(p.x.mul(1.30).add(4.1)).mul(cos(p.y.mul(1.10).add(2.7)));
                const pr = vec2(p.x.mul(0.866).add(p.y.mul(0.5)), p.x.mul(-0.5).add(p.y.mul(0.866)));
                const c = sin(pr.x.mul(0.85).add(1.5)).mul(cos(pr.y.mul(0.95).add(5.1)));
                const d = sin(p.x.mul(2.80).add(1.9)).mul(cos(p.y.mul(2.30).add(0.4)));
                return a.mul(0.55).add(b.mul(0.27)).add(c.mul(0.30)).add(d.mul(0.10)).mul(0.5).add(0.5);
            };
            const viewFromDepthUV = (uvN, d) => {
                const ndc = vec4(uvN.mul(2.0).sub(1.0), d.mul(2.0).sub(1.0), 1.0);
                const v = u.invProj.mul(ndc);
                return v.xyz.div(v.w);
            };
            const worldFromDepthUV = (uvN, d) =>
                u.camWorld.mul(vec4(viewFromDepthUV(uvN, d), 1.0)).xyz;

            // streak layer: tiled falling streaks, hash-gated per cell
            const rainLayer = (uvN, t, grid, density, dropLen) => {
                const sUv = vec2(uvN.x, uvN.y.sub(t));
                const id = floor(sUv.mul(grid));
                const h = hash21(id);
                const gate = step(float(1.0).sub(density), h);
                const local = fract(sUv.mul(grid)).sub(vec2(0.5, 0.5));
                const lx = local.x.add(h.sub(0.5).mul(0.7));
                const sx = smoothstep(0.05, 0.0, abs(lx));
                const sy = smoothstep(dropLen, dropLen.mul(0.5), abs(local.y.add(0.2)));
                return sx.mul(sy).mul(h.mul(0.6).add(0.4)).mul(gate);
            };

            // splash sampler → { ring, core, dir }
            const sampleSplash = (worldXZ, t, rate) => {
                const cellUV = worldXZ.mul(2.0);
                const cellID = floor(cellUV);
                const ch1 = hash21(cellID);
                const ch2 = hash21(cellID.add(vec2(13.0, 27.0)));
                const ch3 = hash21(cellID.add(vec2(47.0, 91.0)));
                const ch4 = hash21(cellID.add(vec2(73.0, 5.0)));
                const fires = step(0.25, ch1);
                const maxRad = mix(float(0.10), float(0.36), ch2);
                const ringW = mix(float(0.020), float(0.052), ch3);
                const period = float(1.0).div(max(rate, 0.05)).mul(mix(float(0.55), float(1.7), ch4));
                const ph = fract(t.div(period).add(ch1));
                const sRad = ph.mul(maxRad);
                const aPh = fires.mul(float(1.0).sub(ph)).mul(step(0.05, ph));
                const cellLraw = fract(cellUV).sub(vec2(0.5, 0.5));
                const jitter = vec2(hash21(cellID.add(17.0)), hash21(cellID.add(31.0))).sub(vec2(0.5, 0.5)).mul(0.5);
                const cellL = cellLraw.add(jitter);
                const r = length(cellL);
                const ring0 = smoothstep(ringW, 0.0, abs(r.sub(sRad))).mul(aPh);
                const coreF = float(1.0).sub(smoothstep(0.0, 0.18, ph)).mul(fires);
                const core0 = smoothstep(ringW.mul(1.4), 0.0, r).mul(coreF);
                const edgeFade = float(1.0).sub(smoothstep(0.35, 0.50, abs(cellLraw.x)))
                    .mul(float(1.0).sub(smoothstep(0.35, 0.50, abs(cellLraw.y))));
                const dir = cellL.div(max(r, 0.001));
                return { ring: ring0.mul(edgeFade), core: core0.mul(edgeFade), dir };
            };

            return Fn(() => {
                const screenUV = uv();
                const orig = colorTex.sample(screenUV);
                const col = orig.rgb.toVar();

                // 1. world position + normal from depth
                const depth = depthTex.sample(screenUV).r;
                const notSky = float(1.0).sub(step(0.9999, depth));
                const worldP = worldFromDepthUV(screenUV, depth);
                const rayOrigin = u.camWorld.mul(vec4(0.0, 0.0, 0.0, 1.0)).xyz;
                const px = vec2(1.0, 1.0).div(u.resolution);
                const dE = depthTex.sample(screenUV.add(vec2(px.x, 0.0))).r;
                const dN = depthTex.sample(screenUV.add(vec2(0.0, px.y))).r;
                const pE = worldFromDepthUV(screenUV.add(vec2(px.x, 0.0)), dE);
                const pN = worldFromDepthUV(screenUV.add(vec2(0.0, px.y)), dN);
                const nRaw = normalize(cross(pE.sub(worldP), pN.sub(worldP)));
                const V = normalize(rayOrigin.sub(worldP));
                const worldN = nRaw.mul(sign(dot(nRaw, V).add(1e-5)));

                // 2. ground band + puddle splotches
                const gNorm = smoothstep(u.groundNormalThreshold, u.groundNormalThreshold.add(0.05), worldN.y);
                const gBand = float(1.0).sub(smoothstep(u.groundBand, u.groundBand.mul(1.3), abs(worldP.y.sub(u.groundY))));
                const groundMask = gNorm.mul(gBand).mul(notSky);
                const puddleNoise = puddleFbm(worldP.xz.mul(0.35).add(vec2(13.7, 9.1)));
                const pTh = mix(float(0.65), float(0.40), clamp(u.puddleCoverage, 0.0, 1.0));
                const puddleMask = smoothstep(pTh.sub(0.10), pTh.add(0.10), puddleNoise).mul(groundMask);

                // 3. cover occlusion (world-vertical column march, branchless)
                const hits = float(0.0).toVar();
                Loop({ start: 0, end: 6, type: 'int', name: 'ci' }, ({ ci }) => {
                    const h = mix(float(0.15), u.coverHeight, float(ci).div(5.0));
                    const testW = worldP.add(vec3(0.0, h, 0.0));
                    const clip = u.proj.mul(u.view.mul(vec4(testW, 1.0)));
                    const wOk = step(0.001, clip.w);
                    const ndc = clip.xyz.div(max(clip.w, 0.001));
                    const inX = step(abs(ndc.x), 1.0);
                    const inY = step(abs(ndc.y), 1.0);
                    const uvT = ndc.xy.mul(0.5).add(0.5);
                    const sceneD = depthTex.sample(uvT).r;
                    const notSkyT = float(1.0).sub(step(0.9999, sceneD));
                    const sceneWorld = worldFromDepthUV(uvT, sceneD);
                    const xzDist = length(sceneWorld.xz.sub(worldP.xz));
                    const xzGate = float(1.0).sub(smoothstep(0.4, 1.0, xzDist));
                    const yAbove = sceneWorld.y.sub(worldP.y);
                    const yBand = smoothstep(0.05, 0.15, yAbove)
                        .mul(float(1.0).sub(smoothstep(u.coverHeight.mul(0.8), u.coverHeight, yAbove)));
                    hits.addAssign(xzGate.mul(yBand).mul(wOk).mul(inX).mul(inY).mul(notSkyT));
                });
                const coverF = smoothstep(0.10, 0.90, clamp(hits.div(1.5), 0.0, 1.0)).mul(notSky);

                // sky colour: averaged top-of-frame taps (uniform per pass)
                const skyCol = vec3(0.0, 0.0, 0.0).toVar();
                Loop({ start: 0, end: 16, type: 'int', name: 'si' }, ({ si }) => {
                    const fx = float(si).div(15.0);
                    skyCol.addAssign(colorTex.sample(vec2(fx, 0.02)).rgb);
                    skyCol.addAssign(colorTex.sample(vec2(fx, 0.06)).rgb);
                });
                skyCol.divAssign(32.0);

                // 4. puddles: ripple refraction + fresnel sky + splash rings
                const rUV = worldP.xz.mul(1.4).add(vec2(0.0, u.iTime.mul(0.25)));
                const n0 = puddleFbm(rUV);
                const nx = puddleFbm(rUV.add(vec2(0.06, 0.0)));
                const ny = puddleFbm(rUV.add(vec2(0.0, 0.06)));
                const rippleBase = vec2(nx.sub(n0), ny.sub(n0)).mul(3.5);
                const sp = sampleSplash(worldP.xz, u.iTime, u.splashRate.mul(u.intensity.mul(0.8).add(0.4)));
                const ripple = rippleBase.add(sp.dir.mul(sp.ring).mul(8.0));
                const warped = colorTex.sample(screenUV.add(ripple.mul(0.0025))).rgb;
                const wet0 = warped.mul(mix(float(1.0), float(0.55), u.puddleStrength));
                const wet1 = mix(wet0, wet0.mul(u.puddleColor), u.puddleStrength.mul(0.55));
                const Nw = normalize(vec3(ripple.x.mul(0.25), 1.0, ripple.y.mul(0.25)));
                const fres = float(0.10).add(pow(float(1.0).sub(clamp(dot(Nw, V), 0.0, 1.0)), 2.0).mul(0.90));
                const wet = wet1
                    .add(skyCol.mul(fres).mul(u.puddleStrength).mul(1.6))
                    .add(skyCol.mul(sp.core).mul(0.45));
                col.assign(mix(col, wet, puddleMask.mul(float(1.0).sub(coverF))));

                // 5. dry top-surface splashes (fresnel wet glints)
                const drySurf = smoothstep(u.splashNormalThreshold.mul(0.6), 0.95, worldN.y)
                    .mul(float(1.0).sub(coverF)).mul(float(1.0).sub(puddleMask)).mul(notSky);
                const bumpedN = normalize(worldN.add(vec3(sp.dir.x, 0.0, sp.dir.y).mul(sp.ring).mul(0.55)));
                const fresD = pow(float(1.0).sub(clamp(dot(bumpedN, V), 0.0, 1.0)), 2.0);
                const coreM = sp.core.mul(u.intensity).mul(drySurf);
                const ringM = sp.ring.mul(u.intensity).mul(drySurf);
                col.assign(mix(col, col.mul(0.78), coreM.mul(0.6)));
                col.addAssign(skyCol.mul(fresD).mul(ringM).mul(0.9));

                // 5.5 global wet-surface look: every upward face that isn't
                // under cover darkens + cools slightly — the world reads as
                // RAINED ON everywhere, not only inside puddle splotches.
                const wetAll = smoothstep(0.35, 0.8, worldN.y)
                    .mul(float(1.0).sub(coverF)).mul(notSky).mul(u.wetDarken);
                const wetTone = col.mul(0.72).mul(vec3(0.92, 0.96, 1.05));
                col.assign(mix(col, wetTone, wetAll));

                // 6. falling streaks — 3 layers, depth-attenuated, cover-dimmed
                const sUV = vec2(screenUV.x.add(screenUV.y.mul(u.windTilt)), screenUV.y);
                const density = clamp(u.intensity, 0.0, 1.0).mul(0.18);
                const t1 = u.iTime.mul(u.streakSpeed).mul(1.6);
                const t2 = u.iTime.mul(u.streakSpeed).mul(2.3);
                const t3 = u.iTime.mul(u.streakSpeed).mul(3.4);
                const wNear = float(1.0).sub(smoothstep(0.0, 0.40, depth));
                const wMid = float(1.0).sub(smoothstep(0.20, 0.75, depth));
                const streaks = rainLayer(sUV, t1, vec2(60.0, 6.0), density, float(0.42)).mul(0.55).mul(wNear)
                    .add(rainLayer(sUV, t2, vec2(90.0, 9.0), density.mul(1.15), float(0.36)).mul(0.40).mul(wMid))
                    .add(rainLayer(sUV, t3, vec2(140.0, 14.0), density.mul(1.30), float(0.30)).mul(0.28));
                col.addAssign(u.rainColor.mul(streaks.mul(float(1.0).sub(coverF.mul(0.85)))).mul(1.8));

                // 7. rain haze: distance desaturation toward a cool rain tone —
                // far geometry softens into the weather (sky excluded; it's
                // already the brightest thing in frame).
                const hazeAmt = smoothstep(0.55, 0.98, depth).mul(u.rainHaze).mul(notSky);
                const hazeCol = u.rainColor.mul(0.55).add(skyCol.mul(0.35));
                col.assign(mix(col, hazeCol, hazeAmt));

                return vec4(mix(orig.rgb, col, u.opacity), orig.a);
            })();
        };

        const update = (t) => {
            u.iTime.value = t;
            if (camera) {
                camera.updateMatrixWorld();
                u.invProj.value.copy(camera.projectionMatrixInverse);
                u.camWorld.value.copy(camera.matrixWorld);
                u.proj.value.copy(camera.projectionMatrix);
                u.view.value.copy(camera.matrixWorldInverse);
            }
        };
        update(0);
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('depth_rain');
        return { uniforms: u, update };
    }

    globalThis.DepthRainFX = { applyTo };
    console.log('[depth_rain] DepthRainFX.applyTo registered');
})();
