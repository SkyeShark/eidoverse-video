// cross_hatch.js — a TSL pencil cross-hatch effect (the sketched
// "TAKE ON ME" pencil look). The crucial
// detail the procedural-noise port missed: the original samples a
// 256×256 noise TEXTURE with linear filter + uvSmooth() anti-banding,
// not a hash() — the texture has correlated/banded statistics that
// give the proper graphite-grain look. Procedural fract-sin noise is
// pure white-noise and reads as paint blobs instead of pencil strokes.
//
// Other fixes vs the prior port:
//   - matrix uses cos(ang - 1.6) instead of sin(ang) (original quirk).
//   - ramp resets to 0 before the hatch loop (so getVal inside reads
//     the scene cleanly, no wiggle jitter on the per-tap luma).
//   - paper grain is hardcoded `0.95 + 0.06·r.xxx + 0.06·r.xyz` using
//     the subtractive r vec4 from the outline pre-roll — preserves
//     monochrome + colour grain mix.
//   - vignette is hardcoded sin-attenuated (no separate knob).
//
// Public API:
//   CrossHatchFX.applyTo({ opts });
//
// Options:
//   wiggle          float — pencil jitter on every sample (default 1.0)
//   flicker         float — temporal scrolling of the wiggle (default 1.0)
//   outlineStrength float — multiplier on the contour band (default 1.0)
//   hatchStrength   float — multiplier on hatch darkness (default 1.0)
//   opacity         float — final blend (default 1.0)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[cross_hatch] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    // 256×256 RGBA noise texture — generated once, reused. Statistics
    // an independent uint8 per
    // channel, uniform distribution).
    let _noiseTex = null;
    function getNoiseTexture() {
        if (_noiseTex) return _noiseTex;
        const size = 256;
        const data = new Uint8Array(size * size * 4);
        // Deterministic seed so frame-to-frame the texture is stable.
        let s = 0x12345678 | 0;
        const rng = () => {
            s = (s * 1103515245 + 12345) | 0;
            return ((s >>> 16) & 0xff);
        };
        for (let i = 0; i < data.length; i++) data[i] = rng();
        const tex = new THREE.DataTexture(
            data, size, size,
            THREE.RGBAFormat, THREE.UnsignedByteType,
        );
        tex.wrapS = THREE.RepeatWrapping;
        tex.wrapT = THREE.RepeatWrapping;
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.needsUpdate = true;
        _noiseTex = tex;
        return tex;
    }

    function applyTo(args) {
        args = args || {};
        const camera = args.camera;
        const opts = args.opts ?? args;
        const w = opts.width  ?? globalThis.WIDTH  ?? 1280;
        const h = opts.height ?? globalThis.HEIGHT ?? 720;

        const u = {
            time:                 THREE.uniform(0),
            iResolution:          THREE.uniform(new THREE.Vector2(w, h)),
            wiggle:               THREE.uniform(opts.wiggle               ?? 1.0),
            flicker:              THREE.uniform(opts.flicker              ?? 1.0),
            outlineStrength:      THREE.uniform(opts.outlineStrength      ?? 1.4),
            hatchStrength:        THREE.uniform(opts.hatchStrength        ?? 0.85),
            opacity:              THREE.uniform(opts.opacity              ?? 1.0),
            // Depth-edge contribution to the outline pass. Object
            // silhouettes have strong depth gradients regardless of
            // lighting/colour contrast, so this catches outlines that
            // the colour-gradient pass misses on uniformly-bright scenes.
            // Strength 0.9 + threshold 0.05 keeps lines thin (only sharp
            // silhouette jumps fire) instead of bleeding into adjacent
            // pixels when the smoothstep range was too wide.
            depthOutlineStrength: THREE.uniform(opts.depthOutlineStrength ?? 0.9),
            depthOutlineThresh:   THREE.uniform(opts.depthOutlineThresh   ?? 0.05),
            camNear:              THREE.uniform(camera ? camera.near : 0.1),
            camFar:               THREE.uniform(camera ? camera.far  : 100),
        };

        const noiseTex = getNoiseTexture();
        const noiseNode = THREE.texture(noiseTex);

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal /*, sceneMR */) => {
            const {
                Fn, vec2, vec3, vec4, float, uv, sin, cos, exp, fract, floor, sqrt, length, abs, mat2,
                mix, clamp, max, min, dot, normalize, smoothstep, pow, Loop, Break, If,
                convertToTexture, perspectiveDepthToViewZ,
            } = THREE;

            const colorTex  = convertToTexture(colorOut);
            const depthTex  = sceneDepth  ? convertToTexture(sceneDepth)  : null;
            const normalTex = sceneNormal ? convertToTexture(sceneNormal) : null;
            const PI2 = float(Math.PI * 2);

            // uvSmooth(uv, res) = uv + 0.6 * sin(uv*res*PI2) / PI2 / res
            // Anti-banding for linear-filtered texture sampling.
            const uvSmooth = (uvN, res) =>
                uvN.add(sin(uvN.mul(res).mul(PI2)).mul(0.6).div(PI2).div(res));

            // getRand(pos) — sample noise texture at pixel-space pos.
            // Returns vec4. RepeatWrapping handles pos > 256.
            const getRand = (pos) => Fn(() => {
                const tres = vec2(256.0);
                const uvN = uvSmooth(pos.div(tres), tres);
                return noiseNode.sample(uvN);
            })();

            // getCol(pos, ramp, rsc, sc) — sample scene at pixel-space
            // pos with per-sample wiggle jitter scaled by ramp & rsc.
            const getCol = (pos, ramp, rsc, sc) => Fn(() => {
                const r1 = getRand(
                    pos.mul(0.05).mul(rsc).div(sc).add(u.time.mul(131.0).mul(u.flicker))
                ).sub(0.5).mul(10).mul(ramp).mul(u.wiggle);
                const uvN = pos.add(r1.xy.mul(sc)).div(u.iResolution);
                return colorTex.sample(uvN);
            })();

            // getVal: luminance for hatch density + outline gradients.
            // Reinhard tonemap brings the autoenhance HDR sample into a
            // perceptually-distributed [0,1] so the algorithm's [0,1]-
            // tuned thresholds engage instead of saturating high.
            const getVal = (pos, ramp, rsc, sc) => {
                const c = getCol(pos, ramp, rsc, sc).xyz;
                const tm = c.div(c.add(vec3(1)));
                return clamp(dot(tm, vec3(0.333)), 0, 1);
            };

            const getGrad = (pos, eps, ramp, rsc, sc) => Fn(() => {
                const dx = vec2(eps, 0);
                const dy = vec2(0, eps);
                const gx = getVal(pos.add(dx), ramp, rsc, sc).sub(getVal(pos.sub(dx), ramp, rsc, sc));
                const gy = getVal(pos.add(dy), ramp, rsc, sc).sub(getVal(pos.sub(dy), ramp, rsc, sc));
                return vec2(gx, gy).div(eps).div(2);
            })();

            return Fn(() => {
                const uvNode = uv();
                const orig = colorTex.sample(uvNode);
                const fragCoord = uvNode.mul(u.iResolution);
                const sc = max(u.iResolution.x.div(600.0), float(0.5));
                const sqSc = sqrt(sc);

                // r = getRand(pos*1.2/sqrt(sc)) - getRand(pos*1.2/sqrt(sc) + (1,-1)*1.5)
                const rPos = fragCoord.mul(1.2).div(sqSc);
                const r  = getRand(rPos).sub(getRand(rPos.add(vec2(1.5, -1.5))));
                const r2 = getRand(rPos);

                // ---- Depth-edge term: object silhouettes ----
                // Linearised depth Sobel-cardinal differencing. Object
                // boundaries have strong depth gradients regardless of
                // lighting / colour contrast, so this catches outlines
                // the colour-gradient pass misses on uniformly-bright
                // scenes (e.g. autoenhance HDR output where bloom flattens
                // luminance variation but silhouettes are still distinct).
                const depthEdge = float(0).toVar();
                // Center world-space distance from camera, in scene units
                // (large = sky/no-geo). Exposed so hatch + perspective-
                // darken steps can read it. Default `u.camFar` so the
                // null-depth fallback acts like "everything is sky".
                const centerDepth = float(0).toVar();
                centerDepth.assign(u.camFar);
                if (depthTex) {
                    const px = vec2(1).div(u.iResolution);
                    const sampleD = (off) => {
                        const d = depthTex.sample(uvNode.add(off.mul(px))).r;
                        // perspectiveDepthToViewZ → negative-z forward of
                        // camera. Negate to get positive world distance.
                        return perspectiveDepthToViewZ(d, u.camNear, u.camFar).negate();
                    };
                    const dC = max(sampleD(vec2(0, 0)), 0.0001);
                    centerDepth.assign(dC);
                    const d0 = sampleD(vec2(-1, -1));
                    const d1 = sampleD(vec2( 0, -1));
                    const d2 = sampleD(vec2( 1, -1));
                    const d3 = sampleD(vec2(-1,  0));
                    const d5 = sampleD(vec2( 1,  0));
                    const d6 = sampleD(vec2(-1,  1));
                    const d7 = sampleD(vec2( 0,  1));
                    const d8 = sampleD(vec2( 1,  1));
                    const dDepth = abs(d1.sub(d7)).add(abs(d5.sub(d3)))
                        .add(abs(d0.sub(d8))).add(abs(d2.sub(d6))).div(dC);
                    // Smoothstep into [0,1] above the threshold so noise
                    // (e.g. depth quantization on flat surfaces) doesn't
                    // produce spurious lines.
                    depthEdge.assign(smoothstep(
                        u.depthOutlineThresh,
                        u.depthOutlineThresh.mul(8),
                        dDepth,
                    ));
                }

                // ---- Outlines: 3 iterations × 2 flavours each ----
                const NUM = 3;
                const NUM_F_M1 = float(NUM - 1);
                const br = float(0).toVar();
                Loop({ start: 0, end: NUM, type: 'int' }, ({ i }) => {
                    const fi = float(i).div(NUM_F_M1);
                    const t = float(0.03).add(fi.mul(0.25));
                    const wBand = t.mul(2);
                    // Flavour 1.
                    const ramp1 = float(0.15).mul(pow(float(1.3), fi.mul(5.0)));
                    const rs1   = float(1.7).mul(pow(float(1.3), fi.mul(-5.0)));
                    const g1len = length(getGrad(fragCoord, sc.mul(0.4), ramp1, rs1, sc)).mul(sc);
                    const e1 = smoothstep(t.sub(wBand.mul(0.5)), t.add(wBand.mul(0.5)), g1len);
                    br.addAssign(e1.mul(float(0.6)).mul(float(0.5).add(fi)));
                    // Flavour 2.
                    const ramp2 = float(0.30).mul(pow(float(1.3), fi.mul(5.0)));
                    const rs2   = float(10.7).mul(pow(float(1.3), fi.mul(-5.0)));
                    const g2len = length(getGrad(fragCoord, sc.mul(0.4), ramp2, rs2, sc)).mul(sc);
                    const e2 = smoothstep(t.sub(wBand.mul(0.5)), t.add(wBand.mul(0.5)), g2len);
                    br.addAssign(e2.mul(float(0.4)).mul(float(0.2).add(fi)));
                });
                // colorOut starts white, gets darkened by br. Original
                // multiplies br by `(.5 + .5*r2.z) * 3 / num` so it's
                // jittered + scaled per pixel. Depth-edge term is added
                // separately (no /NUM division — single contribution) and
                // gets the same per-pixel jitter so it visually matches
                // the colour-gradient outlines.
                const colorOutline = br.mul(u.outlineStrength).mul(0.7)
                    .mul(float(0.5).add(r2.z.mul(0.5)))
                    .mul(float(3).div(float(NUM)));
                const depthOutline = depthEdge.mul(u.depthOutlineStrength)
                    .mul(float(0.5).add(r2.z.mul(0.5)));
                // Cap the subtraction at 0.6 so even saturated outline
                // pixels settle at colVar≈0.4 (mid-grey) instead of pure
                // black — reads as a graphite line, not a solid ink line.
                const totalOutline = clamp(colorOutline.add(depthOutline), 0, 0.6);
                const colVar = vec3(1).sub(totalOutline).toVar();
                colVar.assign(clamp(colVar, 0, 1));

                // ---- Hatch: 5 rotated layers ----
                const HNUM = 5;
                const HNUM_F = float(HNUM);
                const hatch  = float(0).toVar();
                const hatch2 = float(0).toVar();
                const hSum   = float(0).toVar();

                Loop({ start: 0, end: HNUM, type: 'int' }, ({ i }) => {
                    const fi = float(i);
                    // valJit: getVal at fragCoord jittered by ±1.5*sc
                    // pixels via a flicker-driven noise sample.
                    const seedJ = fragCoord.mul(0.02).add(u.time.mul(1120.0));
                    const rj = getRand(seedJ).xy.sub(0.5);
                    const jitterPos = fragCoord.add(rj.mul(1.5).mul(sc).mul(clamp(u.flicker, -1, 1)));
                    // ramp = 0 here so the val sample is unjittered.
                    const valJit = getVal(jitterPos, float(0), float(1), sc).mul(1.7);

                    // Adaptive early-out — bright pixels skip late layers.
                    If(fi.greaterThan(float(1).sub(valJit).mul(HNUM_F))
                        .and(fi.greaterThanEqual(2)), () => {
                        Break();
                    });

                    // Original matrix: mat2(CS(ang), N(CS(ang)))
                    //   CS(ang) = cos(ang - vec2(0, 1.6))
                    //   N(v)    = v.yx * vec2(-1, 1)  i.e. (-v.y, v.x)
                    //
                    // Per-pixel angle offset: object pixels (close depth)
                    // get +π/2 so their hatch reads in a perpendicular
                    // direction to the floor/overlay hatch — separates
                    // object surfaces from the background pencil texture
                    // visually instead of having them blend into one big
                    // overlay.
                    const isObject = depthTex
                        ? float(1).sub(smoothstep(
                            u.camFar.mul(0.08), u.camFar.mul(0.18), centerDepth,
                        ))
                        : float(0);
                    const angOffset = isObject.mul(Math.PI / 2);
                    const ang = float(-0.5).sub(fi.mul(fi).mul(0.08)).add(angOffset);
                    const cs0 = cos(ang);
                    const cs1 = cos(ang.sub(1.6));
                    // mat2 column-major: cols (cs0, cs1) and (-cs1, cs0)
                    const rot = mat2(cs0, cs1, cs1.negate(), cs0);
                    const uvh = rot.mul(fragCoord).div(sqSc).mul(vec2(0.05, 1.0)).mul(1.3);
                    const uvhT = uvh.add(vec2(sin(uvh.y), 0)).add(u.time.mul(1003.123).mul(u.flicker));
                    // pow(getRand(...), vec4(1)) is identity in the original.
                    const rh = getRand(uvhT);
                    const contrib = float(1).sub(smoothstep(float(0.5), float(1.5), rh.x.add(valJit)))
                        .sub(abs(r.z).mul(0.3));
                    hatch.addAssign(contrib);
                    hatch2.assign(max(hatch2, contrib));
                    hSum.addAssign(1);
                });
                // farFade was previously fading hatch to 0 on far pixels
                // (sky) — that killed the sky's pencil texture. Disabled
                // so sky gets the same blank-paper-with-hatching treatment
                // as the floor. Kept as a no-op uniform 1 in case future
                // tuning wants to re-enable it.
                const farFade = float(1);

                // Normal-based shading boost. The colour-luminance hatch
                // pass alone produces uniform fill on objects whose
                // post-bloom HDR colour is similar across faces (flat-
                // faceted cars / laptops / pillars). View-space normal's
                // |z| tells us "how directly is this face pointing at the
                // camera": ~1 means facing cam (lit highlight), ~0 means
                // grazing (rim/shadow). Each face of a faceted object has
                // a distinct |n.z|, so even a uniformly-coloured object
                // produces face-by-face shading variation and the algo
                // hatches accordingly.
                //
                // BG sentinel: depth (centerDepth ≥ ~camFar = sky/no-geo)
                // — robust against MRT normal-tex BG values that aren't
                // pure zero.
                const shadingBoost = float(1).toVar();
                if (normalTex && depthTex) {
                    const nRaw = normalTex.sample(uvNode).rgb;
                    const n = nRaw.mul(2).sub(1);
                    // Camera-facing intensity: 1 at face-on, 0 at silhouette.
                    const facing = abs(n.z);
                    // Map facing → hatch boost [1.2, 0.7]:
                    //   silhouette/grazing (facing=0) → 1.2× hatch (shadow)
                    //   face-on            (facing=1) → 0.7× hatch (highlight)
                    // Gentler than before (was [1.5, 0.5]) so face-on
                    // ground-plane pixels don't over-hatch into near-black
                    // when combined with the boosted hatchStrength.
                    const boost = mix(float(1.2), float(0.7), clamp(facing, 0, 1));
                    // Only apply on actual geometry. centerDepth near camFar
                    // means BG/sky — keep shadingBoost at 1 there.
                    const isGeo = float(1).sub(smoothstep(
                        u.camFar.mul(0.85), u.camFar.mul(0.99), centerDepth,
                    ));
                    shadingBoost.assign(mix(float(1), boost, isGeo));
                }

                const hatchAmt = clamp(
                    mix(hatch.div(max(hSum, 0.0001)), hatch2, 0.5)
                        .mul(u.hatchStrength).mul(farFade).mul(shadingBoost),
                    0, 1,
                );
                colVar.assign(colVar.mul(float(1).sub(hatchAmt)));

                // Pencil flatten: prevent absolute black but preserve
                // outline punch. Coefficient 0.92 lets dark outlines stay near 0
                // (lifts only to ~0.08
                // instead of 0.3), so silhouettes pop instead of being
                // washed into mid-grey.
                colVar.assign(float(1).sub(float(1).sub(colVar).mul(0.92)));

                // Hardcoded paper grain — uses the subtractive r vec4
                // from the pre-roll. r.xxx is monochrome variation,
                // r.xyz adds a colour shift.
                colVar.assign(colVar.mul(
                    float(0.95).add(r.xxx.mul(0.06)).add(r.xyz.mul(0.06))
                ));

                // Sin-attenuated vignette — gentle (0.3 strength) so the floor corners
                // don't darken into the contrast-killing zone the
                // s-curve below would crush further.
                const scc = fragCoord.sub(u.iResolution.mul(0.5)).div(u.iResolution.x);
                let vign = float(1).sub(dot(scc, scc).mul(0.15));
                vign = vign.mul(float(1).sub(exp(sin(uvNode.x.mul(Math.PI)).mul(-40.0)).mul(0.3)));
                vign = vign.mul(float(1).sub(exp(sin(uvNode.y.mul(Math.PI)).mul(-20.0)).mul(0.3)));
                colVar.assign(colVar.mul(vign));

                // Atmospheric / perspective darken: applied LAST so the
                // pencil-flatten step (which lifts darks toward 0.3) doesn't
                // eat the recession. Geometry darkens with distance from
                // camera; bare-paper sky stays bright. The contrast at the
                // horizon between distance-darkened floor and bright sky
                // creates a visible horizon contour. Without this step,
                // post-bloom HDR floor and sky luminance are similar and
                // both render as identical blank paper.
                // Perspective darken intentionally OFF — stacking with
                // the s-curve below crushed the floor to near-black. The
                // depth-edge outline + s-curve contrast already create a
                // visible horizon contour without distance-fading the
                // floor brightness.

                // Final contrast lift: gentle s-shaped remap that pushes
                // dark outlines slightly toward black and bright paper
                // toward white without crushing the mid-grey floor. The
                // [0.15, 0.85] range steepens the centre slope ~30% while
                // preserving the perspective-darkened floor as visible
                // mid-grey vs near-pure-white sky.
                colVar.assign(mix(
                    colVar,
                    smoothstep(float(0.15), float(0.85), colVar),
                    float(0.6),
                ));

                return mix(orig, vec4(clamp(colVar, 0, 1), 1.0), u.opacity);
            })();
        };

        return {
            uniforms: u,
            update(t) { u.time.value = t; },
            setResolution(width, height) { u.iResolution.value.set(width, height); },
        };
    }

    globalThis.CrossHatchFX = { applyTo };
    console.log('[cross_hatch] CrossHatchFX.applyTo (pencil cross-hatch + DataTexture noise) registered');
})();
