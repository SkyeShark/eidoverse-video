// underwater.js — screen-space underwater effect for the WebGPU/TSL
// pipeline. Drops onto any scene without needing waterY/bounds/etc.
// Architecture:
//   - The underlying scene is rendered normally (whatever the agent built).
//   - A screen-space post-pass wraps the rendered colour with:
//       * Where scene depth = far plane (sky): render an "ethereal wispy
//         water roof" — caustic pattern displayed in the upward-facing
//         pixels, fading to horizon color near grazing angles.
//       * Where scene depth = hit: reconstruct world position, sample
//         caustic at worldPos.xz weighted by surface normal (caustic
//         lands on up-facing surfaces). Depth-based fog mixing toward
//         horizon color.
//       * Screen-space god rays via the 1D caustic-X formula.
//       * Screen-space bubble specks at procedural positions.
//
// Usage:
//   UnderwaterFX.applyTo({ scene, camera });
//   // ...autoenhance runs as normal; the underwater hook is registered
//   //    via globalThis._autoEnhanceColorHook.
//
// Pipeline rules: NodeMaterial only (none used here — we operate on the
// existing rendered colour), no CPU per-frame loops, no fallback chains.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[underwater] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    // ---------------------------------------------------------------------
    // Caustic 2D — returns a single float caustic value
    // at the given 2D coord, animated by time.
    // ---------------------------------------------------------------------
    function buildCaustic2DFn() {
        const { Fn, vec2, float, sin, cos, length, abs, pow, mod, clamp, Loop } = THREE;
        return Fn(([uvIn, t]) => {
            const TAU = float(6.28318530718);
            const pp = uvIn.mul(TAU).mod(TAU).sub(250);
            const tt = t.mul(0.5).add(23);
            const ii = pp.toVar();
            const c = float(1).toVar();
            const inten = float(0.005);
            Loop({ start: 0, end: 5, type: 'int' }, ({ i }) => {
                const tn = tt.mul(float(1).sub(float(3.5).div(float(i).add(1))));
                const newI = pp.add(vec2(
                    cos(tn.sub(ii.x)).add(sin(tn.add(ii.y))),
                    sin(tn.sub(ii.y)).add(cos(tn.add(ii.x))),
                ));
                ii.assign(newI);
                const denomX = sin(ii.x.add(tn)).div(inten);
                const denomY = cos(ii.y.add(tn)).div(inten);
                const lenV = length(vec2(pp.x.div(denomX), pp.y.div(denomY)));
                c.addAssign(float(1).div(lenV));
            });
            const cFinal = float(1.17).sub(pow(c.div(5), 1.4));
            return clamp(pow(abs(cFinal), 8), 0, 2);
        });
    }

    // ---------------------------------------------------------------------
    // Caustic 1D — same formula but along a single axis. Used for the
    // 1D-streak god rays (the caustic sampled along a single axis).
    // ---------------------------------------------------------------------
    function buildCaustic1DFn() {
        const { Fn, float, sin, cos, abs, pow, length, Loop } = THREE;
        return Fn(([x, power, gtime]) => {
            const TAU = float(6.28318530718);
            const pp = x.mul(TAU).mod(TAU).sub(250);
            const tt = gtime.mul(0.5).add(23);
            const ii = pp.toVar();
            const c = float(1).toVar();
            const inten = float(0.005);
            Loop({ start: 0, end: 2, type: 'int' }, ({ i }) => {
                const tn = tt.mul(float(1).sub(float(3.5).div(float(i).add(1))));
                const newI = pp.add(cos(tn.sub(ii)).add(sin(tn.add(ii))));
                ii.assign(newI);
                const denom = sin(ii.add(tn)).div(inten);
                c.addAssign(float(1).div(abs(pp.div(denom))));
            });
            const cFinal = float(1.17).sub(pow(c.div(5), power));
            return cFinal;
        });
    }

    // ---------------------------------------------------------------------
    // Build the underwater post-process colour hook. Returns a function
    // (colorOut, sceneDepth, sceneNormal) → vec4 that the autoenhance
    // pipeline can splice in via globalThis._autoEnhanceColorHook.
    // ---------------------------------------------------------------------
    function buildUnderwaterHook({ camera, opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv, sample,
            length, exp, mix, clamp, sin, cos, abs, pow, max, min, dot,
            screenUV,
        } = THREE;

        const u = {
            time:        uniform(0),
            opacity:     uniform(opts.opacity ?? 1.0),
            horizonCol:  uniform(new THREE.Vector3(...(opts.horizonColor ?? [0.0, 0.05, 0.2]))),
            shallowCol:  uniform(new THREE.Vector3(...(opts.shallowColor ?? [0.18, 0.45, 0.55]))),
            fogDensity:  uniform(opts.fogDensity ?? 0.3),
            fogPower:    uniform(opts.fogPower ?? 1.0),
            causticAmt:  uniform(opts.causticAmt ?? 1.4),
            // Tile period of the caustic formula = TAU/causticScale in
            // world units. 0.5 → ~12.5m period — visible detail but tile
            // boundaries usually outside immediate visible patch.
            causticScale:uniform(opts.causticScale ?? 0.5),
            godrayAmt:   uniform(opts.godrayAmt ?? 0.6),
            bubbleAmt:   uniform(opts.bubbleAmt ?? 0.5),
            // Camera matrices — re-uploaded per frame so we can reconstruct
            // world positions (SSR pattern).
            projInv:     uniform(camera.projectionMatrixInverse),
            camWorld:    uniform(camera.matrixWorld),
            camPos:      uniform(camera.position),
        };

        const caustic2D = buildCaustic2DFn();
        const caustic1D = buildCaustic1DFn();

        // The hook itself.
        return {
            uniforms: u,
            update(t) {
                u.time.value = t;
                camera.updateMatrixWorld();
                u.projInv.value = camera.projectionMatrixInverse;
                u.camWorld.value = camera.matrixWorld;
                u.camPos.value = camera.position;
            },
            hook(colorIn, sceneDepth, sceneNormal /*, sceneMR */) {
                // Wrap inputs as TextureNodes so we can .sample() them.
                const colorTex = THREE.convertToTexture(colorIn);
                const depthTex = THREE.convertToTexture(sceneDepth);

                return Fn(() => {
                    const screenUVn = uv();
                    const baseCol = colorTex.sample(screenUVn);
                    const d = depthTex.sample(screenUVn).r;

                    // Reconstruct view + world position via SSR-style helper.
                    const { getViewPosition } = THREE;
                    const viewPos = getViewPosition(screenUVn, d, u.projInv);
                    const worldPos = u.camWorld.mul(vec4(viewPos, 1)).xyz;
                    const dist = length(viewPos);

                    // Centered NDC for screen-space sky/godray sampling.
                    const p = screenUVn.mul(2).sub(1);

                    // ----- Far-plane pixels = "ethereal wispy water roof" -----
                    // d ≈ 1.0 means scene rendered nothing here = sky region.
                    // Build a screen-space wispy roof: caustic pattern at the
                    // top of frame fading toward horizon color near the
                    // bottom (= grazing/horizon angles when underwater).
                    const isFar = clamp(d.sub(0.999).mul(1000), 0, 1);
                    const rdy = p.y;
                    const skyMask = clamp(float(0.8).mul(float(1).sub(rdy.add(0.8).mul(2.5))), 0, 1);
                    const skyBaseCol = u.shallowCol.mul(skyMask);
                    const causticSky1 = caustic2D(vec2(p.x, p.y),         u.time);
                    const causticSky2 = caustic2D(vec2(p.x, p.y.mul(2.7)), u.time);
                    const causticSkyCol = u.shallowCol.mul(
                        causticSky1.mul(0.3).add(causticSky2.mul(0.3)).mul(pow(p.y, 4)),
                    );
                    const horizonCol = u.horizonCol;
                    const skyColor = mix(
                        skyBaseCol.add(causticSkyCol),
                        horizonCol,
                        pow(float(1).sub(pow(rdy, 4)), 20),
                    );

                    // ----- Hit-plane pixels = scene surface — apply caustic + fog -----
                    // Caustic at world XZ (anchors to surface, slides as camera moves)
                    // weighted by surface normal.y (caustics fall on up-facing).
                    const causticIn = vec2(
                        worldPos.x.add(worldPos.y.mul(0.2)),
                        worldPos.z.add(worldPos.y.mul(0.2)),
                    ).mul(u.causticScale);
                    const causticVal = caustic2D(causticIn, u.time);
                    let normalUpFactor = float(1);
                    if (sceneNormal) {
                        const n = sceneNormal.sample(screenUVn);
                        normalUpFactor = clamp(n.y, 0, 1);
                    }
                    const causticContrib = causticVal.mul(u.causticAmt).mul(normalUpFactor);
                    // Beer-Lambert-ish fog: mix scene color toward horizon as distance grows
                    const fogT = float(1).sub(exp(pow(dist, u.fogPower).mul(u.fogDensity).negate()));
                    const sceneColored = baseCol.rgb.mul(causticContrib.add(0.7));
                    const sceneFogged = mix(sceneColored, horizonCol, fogT);

                    // Pick scene vs sky based on isFar (depth = far plane).
                    let outRgb = mix(sceneFogged, skyColor, isFar);

                    // ----- God rays: 1D-caustic-driven streaks in screen space -----
                    // Reverted back to screen-space — anchoring to worldPos
                    // collapsed all rays into long aligned lines.
                    const gr1 = pow(caustic1D(p.x.add(p.y.mul(0.08)).div(1.7).add(0.5), float(1.8), u.time.mul(0.65)), 10).mul(0.05);
                    const gr2 = pow(caustic1D(sin(p.x), float(0.3), u.time.mul(0.7)), 9).mul(0.4);
                    const gr3 = pow(caustic1D(cos(p.x.mul(2.3)), float(0.3), u.time.mul(1.3)), 4).mul(0.1);
                    // p.y is negative at TOP in TSL postproc, positive at
                    // BOTTOM. (1 + p.y) → 0 at top, 2 at bottom — so the
                    // falloff zeros out at the water line and grows as the
                    // rays descend.
                    const grFalloff1 = pow(float(1).add(p.y).mul(0.3), 2).mul(0.2);
                    const grFalloff2 = pow(float(1).add(p.y).mul(0.3), 3);
                    const godRays = clamp(gr1.add(gr2).add(gr3).sub(grFalloff1).sub(grFalloff2), 0, 1).mul(u.godrayAmt);
                    const godRayCol = vec3(0.7, 1.0, 1.0).mul(godRays).mul(mix(u.shallowCol.length(), float(1), p.y.mul(p.y)));
                    outRgb = outRgb.add(godRayCol);

                    // (Bubbles are real 3D depth-aware refractive geometry
                    // added to the scene, not screen-space specks. See
                    // createBubbles() — they render as part of the scene and
                    // arrive here already composited into baseCol.)

                    // ----- Output, blended with original by opacity -----
                    return mix(baseCol, vec4(outRgb, baseCol.a), u.opacity);
                })();
            },
        };
    }

    // ---------------------------------------------------------------------
    // Real 3D bubbles — InstancedMesh of small refractive icosahedrons
    // around the camera. Per-instance stable offsets from the camera.
    // Position = cameraPos + baseOffset + rise(time) computed GPU-side
    // via TSL positionNode (no CPU per-frame loop).
    // ---------------------------------------------------------------------
    function createBubbles({ scene, camera, count = 600, radius = 6, rangeY = 8 }) {
        const { Fn, vec3, attribute, time, mod, sin, cos, float, instanceIndex, uniform } = THREE;

        // Per-instance buffer attribute: baseOffset (xyz from camera origin)
        // and animation params (speed, phase, wobble).
        const baseOffsets = new Float32Array(count * 3);
        const params = new Float32Array(count * 3);  // speed, phase, wobble
        for (let i = 0; i < count; i++) {
            // Distribute roughly within a sphere of given radius around camera
            const theta = Math.random() * Math.PI * 2;
            const r = Math.cbrt(Math.random()) * radius;
            const yOff = (Math.random() - 0.5) * rangeY;
            baseOffsets[i * 3]     = Math.cos(theta) * r;
            baseOffsets[i * 3 + 1] = yOff;
            baseOffsets[i * 3 + 2] = Math.sin(theta) * r;
            // Slow rise — bubbles drift up gently, not rocketing.
            params[i * 3]     = 0.15 + Math.random() * 0.25;    // speed (m/s rise)
            params[i * 3 + 1] = Math.random() * Math.PI * 2;    // phase
            params[i * 3 + 2] = 0.04 + Math.random() * 0.08;    // wobble
        }

        const geo = new THREE.IcosahedronGeometry(0.025, 1);  // small base radius
        geo.setAttribute('iBaseOffset', new THREE.InstancedBufferAttribute(baseOffsets, 3));
        geo.setAttribute('iParams',     new THREE.InstancedBufferAttribute(params, 3));

        const mat = new THREE.MeshPhysicalNodeMaterial({
            color: 0xffffff,           // pure clear, no tint
            transmission: 1.0,
            ior: 1.06,                  // air-in-water — small refraction step
            thickness: 0.04,
            attenuationDistance: 100,   // effectively no attenuation
            roughness: 0.0,
            metalness: 0.0,
            clearcoat: 1.0,
            clearcoatRoughness: 0.0,
            transparent: true,
        });

        // World-anchored bubble cluster — snapshot the initial camera
        // position, don't track. Bubbles stay put in world space; as the
        // camera moves around it sees them from different angles. Avoids
        // the "bubbles drift sideways with the camera" artifact.
        const anchorPos = camera.position.clone();
        const camPos = uniform(anchorPos);
        const yRange = float(rangeY);

        mat.positionNode = Fn(() => {
            const baseO = attribute('iBaseOffset');
            const par   = attribute('iParams');
            const speed = par.x;
            const phase = par.y;
            const wob   = par.z;
            const t = time;
            // Rising y wraps within [-rangeY/2, +rangeY/2] of camera.y
            const yLocal = mod(baseO.y.add(t.mul(speed)).add(yRange.mul(0.5)), yRange).sub(yRange.mul(0.5));
            const xLocal = baseO.x.add(sin(t.mul(0.4).add(phase)).mul(wob));
            const zLocal = baseO.z.add(cos(t.mul(0.3).add(phase.mul(1.3))).mul(wob));
            // Local mesh vertex offset, scaled by rise progression so
            // bubbles grow as they ascend (real-bubble pressure-drop effect).
            // riseT in [0,1] = how high through the rangeY this bubble is
            const riseT = yLocal.add(yRange.mul(0.5)).div(yRange);
            const sizeScale = float(0.6).add(riseT.mul(1.5));  // 0.6× → 2.1×
            const { positionLocal } = THREE;
            return vec3(
                camPos.x.add(xLocal).add(positionLocal.x.mul(sizeScale)),
                camPos.y.add(yLocal).add(positionLocal.y.mul(sizeScale)),
                camPos.z.add(zLocal).add(positionLocal.z.mul(sizeScale)),
            );
        })();

        const mesh = new THREE.InstancedMesh(geo, mat, count);
        mesh.frustumCulled = false;
        scene.add(mesh);

        return { mesh, material: mat, camPosUniform: camPos };
    }

    // ---------------------------------------------------------------------
    // Public API: applyTo(scene, camera) — registers the autoenhance hook
    // AND adds real 3D bubble particles to the scene. The agent calls this
    // once. No waterY, no bounds, no per-effect knobs required.
    // ---------------------------------------------------------------------
    function applyTo(opts) {
        opts = opts || {};
        const { scene, camera } = opts;
        if (!scene) throw new Error('UnderwaterFX.applyTo(): opts.scene required');
        if (!camera) throw new Error('UnderwaterFX.applyTo(): opts.camera required');

        const built = buildUnderwaterHook({ camera, opts });
        const bubbles = createBubbles({
            scene, camera,
            count: opts.bubbleCount ?? 600,
            radius: opts.bubbleRadius ?? 6,
            rangeY: opts.bubbleRangeY ?? 8,
        });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) {
                built.update(t);
                // Bubble anchor is fixed (world-anchored); no per-frame
                // re-sync needed.
            },
            uniforms: built.uniforms,
            bubbles,
        };
    }

    globalThis.UnderwaterFX = { applyTo };
    console.log('[underwater] UnderwaterFX.applyTo (screen-space post) registered');
})();
