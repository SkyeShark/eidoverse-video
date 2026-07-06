// blueprint.js — TSL "engineering blueprint" post-process. Replaces
// the rendered scene with a classic technical-blueprint look: deep
// blue paper background, white ink outlines on object silhouettes,
// fine grid rulings printed onto the paper (not alpha-overlaid),
// horizontal scanline highlights on the ink, soft paper grain,
// vignette. An engineering-wireframe blueprint look, generalised so it
// runs on any agent-rendered scene.
//
// Edge detection combines three signals so silhouettes don't fade at
// corners and backs:
//   1. 3×3 depth-difference (catches geometry stacked at different
//      distances).
//   2. 3×3 normal-difference (catches creases between faces with the
//      same depth).
//   3. Rim term `pow(1 - |n_view.z|, k)` (catches silhouette edges
//      where a surface curves away from camera — these survive even
//      when depth+normal differencing yields nothing because the
//      neighbour pixels are off-mesh).
//
// Grid is rendered as SOLID printed lines (gridStrength=1 by default)
// in a lighter shade of the paper colour — looks like graph paper
// printed at the press, not a translucent overlay sitting in front of
// the drawing. Ink edges are drawn on top of the grid+paper, so the
// drawing always reads as ON the page.
//
// Public API:
//   BlueprintFX.applyTo({ camera, opts });
//
// Options (defaults in [brackets]):
//   paperColor     [r,g,b]  [deep blueprint blue]
//   gridColor      [r,g,b]  [printed-line shade — slightly lighter than paper]
//   inkColor       [r,g,b]  [near-white]
//   cellPx         float    [22] pixels per grid cell. At 1280×720
//                           default → ~58 lines across width, ~32 down.
//   majorEvery     float    [5] every Nth grid line is heavier (engineering rule)
//   minorLineW     float    [1.0] minor line width in pixels
//   majorLineW     float    [2.0] major line width in pixels
//   gridStrength   float    [1.0] 0..1 mix toward grid colour at lines
//   majorStrength  float    [1.0] 0..1 mix toward grid colour at major lines
//   edgeStrength   float    [1.6] multiplier on combined edge signal
//   threshold      float    [0.06] minimum signal that draws ink
//   sharpness      float    [1.4] exponent on edge intensity
//   depthWeight    float    [0.6] weight of depth-difference term
//   normalWeight   float    [1.0] weight of normal-difference term
//   rimWeight      float    [0.45] weight of rim-silhouette term
//   rimSharpness   float    [6.0] exponent on rim term — high values
//                           keep the rim band a tight outline rather
//                           than a wide halo
//   shadeHi        float    [0.78] luminance threshold above which the
//                           original scene becomes solid ink (hot
//                           highlight pixels)
//   shadeMid       float    [0.50] luminance threshold for scanline-cut
//                           ink. Pixels between shadeMid and shadeHi
//                           render as parallel ink lines (the "solid
//                           surface drawn as multiple lines" trick from
//                           real blueprints).
//   shadeStripePx  float    [3] period in screen-y pixels of the
//                           parallel ink rules. Density is 2× this
//                           because |cos(...)| produces a line at every
//                           peak AND every trough — so default 3 px
//                           gives a line every ~1.5 px in screen-y.
//   shadeLineWidth float    [0.92] inner edge of the smoothstep that
//                           keeps each ink line thin. Higher = thinner
//                           line + wider paper cut. Range (0..1).
//   paperGrain     float    [0.025]
//   vignette       float    [0.55]
//   opacity        float    [1.0]

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[blueprint] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const camera = args.camera;
        if (!camera) throw new Error('BlueprintFX.applyTo: opts.camera required (depth conversion needs camera.near/far)');
        const opts = args.opts ?? args;

        const paper = opts.paperColor ?? [0.04, 0.12, 0.30];
        const grid  = opts.gridColor  ?? [0.12, 0.23, 0.46];   // lighter shade — printed line
        const ink   = opts.inkColor   ?? [0.93, 0.97, 1.0];
        const u = {
            time:          THREE.uniform(0),
            paperCol:      THREE.uniform(new THREE.Vector3(paper[0], paper[1], paper[2])),
            gridCol:       THREE.uniform(new THREE.Vector3(grid[0],  grid[1],  grid[2])),
            inkCol:        THREE.uniform(new THREE.Vector3(ink[0],   ink[1],   ink[2])),
            cellPx:        THREE.uniform(opts.cellPx        ?? 22.0),
            majorEvery:    THREE.uniform(opts.majorEvery    ?? 5.0),
            minorLineW:    THREE.uniform(opts.minorLineW    ?? 1.0),
            majorLineW:    THREE.uniform(opts.majorLineW    ?? 2.0),
            gridStrength:  THREE.uniform(opts.gridStrength  ?? 1.0),
            majorStrength: THREE.uniform(opts.majorStrength ?? 1.0),
            edgeStrength:  THREE.uniform(opts.edgeStrength  ?? 1.8),
            threshold:     THREE.uniform(opts.threshold     ?? 0.035),  // lower → small geometry still gets edges
            sharpness:     THREE.uniform(opts.sharpness     ?? 1.4),
            depthWeight:   THREE.uniform(opts.depthWeight   ?? 0.6),
            normalWeight:  THREE.uniform(opts.normalWeight  ?? 1.0),
            rimWeight:     THREE.uniform(opts.rimWeight     ?? 0.95),
            rimSharpness:  THREE.uniform(opts.rimSharpness  ?? 2.4),
            shadeHi:        THREE.uniform(opts.shadeHi        ?? 0.78),
            shadeMid:       THREE.uniform(opts.shadeMid       ?? 0.45),
            shadeStripePx:  THREE.uniform(opts.shadeStripePx  ?? 5.0),
            shadeLineWidth: THREE.uniform(opts.shadeLineWidth ?? 0.86),
            paperGrain:    THREE.uniform(opts.paperGrain    ?? 0.025),
            vignette:      THREE.uniform(opts.vignette      ?? 0.55),
            opacity:       THREE.uniform(opts.opacity       ?? 1.0),
            camNear:       THREE.uniform(camera.near),
            camFar:        THREE.uniform(camera.far),
            iResolution:   THREE.uniform(new THREE.Vector2(
                opts.width  ?? globalThis.WIDTH  ?? 1280,
                opts.height ?? globalThis.HEIGHT ?? 720,
            )),
        };

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal /*, sceneMR */) => {
            const {
                Fn, vec2, vec3, vec4, float, uv, sin, asin, cos, fract, abs, mix, max, min, length, dot,
                clamp, pow, sqrt, smoothstep, convertToTexture, mod, floor,
            } = THREE;

            const baseTex = convertToTexture(colorOut);
            const depthTex = convertToTexture(sceneDepth);
            const normalTex = sceneNormal ? convertToTexture(sceneNormal) : null;

            return Fn(() => {
                const uvNode = uv();
                const orig = baseTex.sample(uvNode);
                const px = vec2(1).div(u.iResolution);

                const sampleD = (off) => {
                    const linNear = u.camNear;
                    const linFar  = u.camFar;
                    const d = depthTex.sample(uvNode.add(off.mul(px))).r;
                    return float(2).mul(linNear).div(
                        linFar.add(linNear).sub(d.mul(linFar.sub(linNear)))
                    );
                };
                const sampleN = (off) => {
                    if (!normalTex) return vec3(0, 0, 1);
                    return normalTex.sample(uvNode.add(off.mul(px))).rgb.mul(2).sub(1);
                };

                // ---- Depth differencing (3×3 cardinal pairs) ----
                const dC = max(sampleD(vec2(0, 0)), 0.0001);
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

                // ---- Normal differencing ----
                const nC = sampleN(vec2(0, 0));
                const n0 = sampleN(vec2(-1, -1));
                const n1 = sampleN(vec2( 0, -1));
                const n2 = sampleN(vec2( 1, -1));
                const n3 = sampleN(vec2(-1,  0));
                const n5 = sampleN(vec2( 1,  0));
                const n6 = sampleN(vec2(-1,  1));
                const n7 = sampleN(vec2( 0,  1));
                const n8 = sampleN(vec2( 1,  1));
                const dNormal = max(float(0), float(1).sub(dot(n1, n7)))
                    .add(max(float(0), float(1).sub(dot(n5, n3))))
                    .add(max(float(0), float(1).sub(dot(n0, n8))))
                    .add(max(float(0), float(1).sub(dot(n2, n6))));

                // ---- Rim term: silhouettes where view-space normal.z → 0.
                // Catches the "back side curving away from camera" case
                // that depth+normal sobel can miss when neighbours are
                // both off-mesh.
                const rim = pow(float(1).sub(abs(nC.z)), u.rimSharpness);

                // Split the edge signal into two paths so the right
                // pixels get cut and the right ones stay solid:
                //   - outlineEdge : ONLY depth jumps. These are real
                //     object boundaries (silhouette against
                //     background, one object passing in front of
                //     another). Drawn solid — the user wants outlines
                //     uncut.
                //   - normalEdge  : normal differencing fires on
                //     INTERIOR curvature (cone surface, torus surface,
                //     anywhere a smooth curved face changes orientation
                //     fast). It looks like "bright highlights" but is
                //     actually just curvature contrast. These get cut
                //     so the bright bands on smooth curves break up
                //     into parallel lines.
                //   - rimInk      : silhouette glow band — also cut.
                const depthSig  = u.depthWeight.mul(dDepth);
                const normalSig = u.normalWeight.mul(dNormal);
                const outlineEdge = clamp(
                    pow(max(depthSig.sub(u.threshold), 0).mul(u.edgeStrength), u.sharpness),
                    0, 1,
                );
                const normalEdge = clamp(
                    pow(max(normalSig.sub(u.threshold), 0).mul(u.edgeStrength), u.sharpness),
                    0, 1,
                );
                const rimInk = clamp(rim.mul(u.rimWeight), 0, 1);

                // ---- Grid: pixel-space repeating lines ----
                // Working in pixel space so line widths stay the same
                // physical thickness regardless of cell size, and high-
                // frequency grids don't go sub-pixel-wide. minorPos is
                // 0..cellPx within each cell; minorEdgeDist is 0 at a
                // grid line and cellPx/2 in the middle of a cell. We
                // pick the smaller of the X-edge-dist and Y-edge-dist
                // so a pixel near EITHER kind of line lights up.
                const fragCoord = uvNode.mul(u.iResolution);
                const minorPos = fract(fragCoord.div(u.cellPx)).mul(u.cellPx);
                const minorEdgeX = min(minorPos.x, u.cellPx.sub(minorPos.x));
                const minorEdgeY = min(minorPos.y, u.cellPx.sub(minorPos.y));
                const minorDist = min(minorEdgeX, minorEdgeY);
                // smoothstep so lines have ~1.5 px of antialiased
                // falloff at their edges — solid in centre, fading at
                // 1 px past the line-half-width.
                const gridLine = smoothstep(
                    u.minorLineW.mul(0.5).add(0.5),
                    u.minorLineW.mul(0.5).sub(0.5),
                    minorDist,
                );
                const majorPx = u.cellPx.mul(u.majorEvery);
                const majorPos = fract(fragCoord.div(majorPx)).mul(majorPx);
                const majorEdgeX = min(majorPos.x, majorPx.sub(majorPos.x));
                const majorEdgeY = min(majorPos.y, majorPx.sub(majorPos.y));
                const majorDist = min(majorEdgeX, majorEdgeY);
                const gridLine5 = smoothstep(
                    u.majorLineW.mul(0.5).add(0.5),
                    u.majorLineW.mul(0.5).sub(0.5),
                    majorDist,
                );

                // Solid printed grid — gridStrength=1 puts the line at
                // gridCol's full saturation. Major lines drawn on top
                // are slightly brighter so they read as the heavy
                // engineering rule. Grid covers the whole frame
                // including under the geometry — that's how real
                // blueprint paper works (drawings are outlines, not
                // fills, so the printed grid stays visible everywhere).
                let outRgb = mix(u.paperCol, u.gridCol, gridLine.mul(u.gridStrength)).toVar();
                outRgb.assign(mix(outRgb, u.gridCol, gridLine5.mul(u.majorStrength)));

                // Horizontal-line mask: thin ink lines at every cos
                // peak AND trough (so line density is 2× the raw
                // period). smoothstep(shadeLineWidth, 0.99, |cos|)
                // keeps the line narrow + the cut wide.
                const stripeArg = uvNode.y.mul(u.iResolution.y).mul(Math.PI).div(u.shadeStripePx);
                const lineMask = smoothstep(u.shadeLineWidth, float(0.99), abs(cos(stripeArg)));

                // Per-pixel checkerboard dither — used to guarantee
                // EVEN tiny bright highlights (specular spots on small
                // spheres / nuts) get cut. The 1-pixel checker can't
                // be missed by a horizontal line that happens to land
                // on the highlight; no matter how small the spot, half
                // its pixels go to paper. Only kicks in for the
                // brightest source-luminance pixels — moderate areas
                // get only the line mask.
                const checker = mod(floor(fragCoord.x).add(floor(fragCoord.y)), 2);
                const origLum = dot(orig.rgb, vec3(0.299, 0.587, 0.114));
                const hotInkRaw = smoothstep(u.shadeMid, u.shadeMid.add(0.10), origLum);
                // hotMask = 1 for the very brightest interior pixels,
                // 0 for mid/dim. Drives the checker engagement so only
                // hot spots get the dither cut on top of the line mask.
                const hotMask = smoothstep(float(0.6), float(0.95), origLum);
                // Combined cut: line mask everywhere; for hot spots,
                // additionally multiply by checker so half of the
                // remaining ink pixels go to paper.
                const checkerCut = mix(float(1), checker, hotMask);

                // Pool everything cuttable: rim band, normal-curvature
                // edges (the apparent "highlights" on smooth curves),
                // and the bright luminance highlights from the
                // rendered scene. ALL of these get reduced to thin ink
                // lines + checker dither.
                const interiorRaw = max(normalEdge, max(rimInk, hotInkRaw));
                const interiorInk = interiorRaw.mul(lineMask).mul(checkerCut);

                // Compose: depth-jump outlines drawn solid (those are
                // true silhouettes); everything else cut by horizontal
                // lines + per-pixel checker on hot spots.
                const inkAmount = clamp(max(outlineEdge, interiorInk), 0, 1);
                outRgb.assign(mix(outRgb, u.inkCol, inkAmount));

                // ---- Paper grain — small per-pixel hash, stays subtle ----
                const hash = fract(sin(uvNode.x.mul(127.1).add(uvNode.y.mul(311.7))).mul(43758.5453));
                outRgb.assign(outRgb.add(vec3(hash.sub(0.5).mul(u.paperGrain))));

                // ---- Vignette ----
                const r = length(uvNode.sub(0.5)).mul(1.41421);
                const vign = float(1).sub(u.vignette.mul(r.mul(r)));
                outRgb.assign(outRgb.mul(vign));
                outRgb.assign(clamp(outRgb, 0, 1));

                return mix(orig, vec4(outRgb, orig.a), u.opacity);
            })();
        };

        return {
            uniforms: u,
            update(t) {
                u.time.value = t;
                u.camNear.value = camera.near;
                u.camFar.value  = camera.far;
            },
            setResolution(width, height) { u.iResolution.value.set(width, height); },
        };
    }

    globalThis.BlueprintFX = { applyTo };
    console.log('[blueprint] BlueprintFX.applyTo registered');
})();
