// retro_wireframe.js — pseudo-wireframe retro display effect
//
// Renders the scene with constant-pixel-width wireframe lines on every
// mesh's actual triangulation, plus a tri-count band filter that drops
// wireframe on meshes that fall outside a "useful poly density" range
// (out-of-band meshes render as flat silhouettes in the line color).
//
// Architecture:
//   - Per-mesh material override: every mesh's material is replaced with
//     a `MeshBasicNodeMaterial` whose colour node uses a per-vertex
//     `barycentric` attribute + screen-space `fwidth` derivative to
//     anti-alias 1-2 px wide lines along every triangle edge. Lines stay
//     constant pixel width regardless of viewing distance, so dense
//     meshes naturally drop their interior wireframe at distance (sub-
//     pixel triangles fall under the threshold) — automatic perspective-
//     based density equalization.
//   - Geometry is converted to non-indexed at install time so each
//     triangle vertex can carry its own `barycentric` (1,0,0) /
//     (0,1,0) / (0,0,1). This 3× the vertex count but is one-shot at
//     scene setup.
//   - Tri-count band filter: meshes with tri count < minTris or
//     > maxTris are rendered as flat silhouettes in the line colour
//     (no wireframe). Catches the "10k-tri model next to 10-tri
//     primitive look mismatched" case the user flagged.
//   - Multicolor mode: per-triangle palette pick via a per-vertex
//     `triHash` attribute baked at geometry preprocessing time. All 3
//     vertices of a triangle share the same hash → consistent color
//     across the triangle face.
//
// Usage:
//   CustomEffectsDeno.applyTo({
//     scene, camera,
//     effects: 'retro_wireframe',
//     opts: { retro_wireframe: { color: 'green' } },
//   });

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[retro_wireframe] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    // Agent-spec retro phosphor / terminal colours (2026-05-07).
    // green = #00AA00 (classic CRT phosphor)
    // amber = #FFB000 (terminal amber)
    // blue  = #150DF7 (bright vector-display blue)
    const PALETTES = {
        green:  [0.000, 0.667, 0.000],
        amber:  [1.000, 0.690, 0.000],
        blue:   [0.082, 0.051, 0.969],
    };

    const MULTI = [
        [1.0, 0.20, 0.20], [0.20, 1.0, 0.30], [0.30, 0.50, 1.0], [1.0, 1.0, 0.20],
        [0.30, 1.0, 1.0],  [1.0, 0.30, 1.0],  [1.0, 0.60, 0.10], [1.0, 1.0, 1.0],
    ];

    /**
     * Convert geometry to non-indexed and bake a per-vertex barycentric
     * attribute. Each triangle's 3 vertices get (1,0,0), (0,1,0), (0,0,1)
     * respectively. Optionally also bake a per-triangle `triHash` (same
     * value across the 3 vertices of a triangle) for multicolor mode.
     */
    function addWireframeAttributes(geometry) {
        const nonIndexed = geometry.index
            ? geometry.toNonIndexed()
            : geometry.clone();
        const vCount = nonIndexed.attributes.position.count;
        const triCount = vCount / 3;
        // Barycentric: 1,0,0 / 0,1,0 / 0,0,1 per triangle vertex.
        const bary = new Float32Array(vCount * 3);
        // triHash — per-triangle stable hash in [0,1). All three vertices
        // of a triangle share the same value so fragment interpolation
        // gives one consistent value across the triangle face. Used for the
        // multicolor palette pick.
        const hashes = new Float32Array(vCount);
        for (let t = 0; t < triCount; t++) {
            const o = t * 9;
            bary[o + 0] = 1; bary[o + 1] = 0; bary[o + 2] = 0;
            bary[o + 3] = 0; bary[o + 4] = 1; bary[o + 5] = 0;
            bary[o + 6] = 0; bary[o + 7] = 0; bary[o + 8] = 1;
            const h = ((t * 2654435761) % 0xffffffff) / 0xffffffff;
            hashes[t * 3 + 0] = h;
            hashes[t * 3 + 1] = h;
            hashes[t * 3 + 2] = h;
        }
        nonIndexed.setAttribute('barycentric', new THREE.BufferAttribute(bary, 3));
        nonIndexed.setAttribute('triHash', new THREE.BufferAttribute(hashes, 1));
        return nonIndexed;
    }

    function applyTo(args) {
        args = args || {};
        const { scene } = args;
        if (!scene) throw new Error('RetroWireframeFX.applyTo: opts.scene required');
        const opts = args.opts ?? args;

        const colorMode = opts.color ?? 'green';
        if (!PALETTES[colorMode] && colorMode !== 'multicolor') {
            throw new Error(
                `[retro_wireframe] unknown color "${colorMode}". `
                + `Valid: ${Object.keys(PALETTES).join(', ')}, multicolor`,
            );
        }

        const lineWidthPx  = opts.lineWidth    ?? 1.5;     // screen-space line thickness
        const bgColor      = opts.bgColor      ?? [0, 0, 0];
        // lineIntensity is the TARGET Rec.709 luminance every line pixel
        // hits after per-colour scaling. Bloom threshold ≈0.85 with a
        // 1.0-wide soft knee; target=1.0 sits 15% into the knee → mild
        // halo on every colour without blowing out dense regions. Bump to
        // 1.3-1.5 for a more aggressive phosphor look.
        const lineIntensity = opts.lineIntensity ?? 1.0;
        // hdrChannelCap — per-channel ceiling on the boosted line colour.
        // Tuned so saturated dim hues (#150DF7 blue: Rec.709 lum 0.124) and
        // bright hues (#FFB000 amber: lum 0.706) produce visually-similar
        // bloom output, NOT the same threshold contribution. Bloom in
        // three.js extracts the full RGB above threshold, so a single hot
        // channel (blue's 7.8) produces a much brighter halo than amber's
        // distributed RGB (max 1.4). At cap=6.3 the blue channel is clamped
        // so its luminance lands at 0.886 (just past threshold 0.85), giving
        // a tiny smoothstep contribution (0.036) that, multiplied by the
        // 6.3 channel value, yields ~0.23 bloom output — matching amber's
        // ~0.21. Tune up for stronger blue bloom, down for stronger amber.
        const hdrChannelCap = opts.hdrChannelCap ?? 6.3;
        const isMulti       = (colorMode === 'multicolor');
        const palette       = PALETTES[colorMode] ?? [0, 1, 0];

        const {
            uniform, Fn, vec3, vec4, float, attribute, fwidth, smoothstep,
            mix, min, max, step, floor, fract, sin, dot,
        } = THREE;

        // Luminance-aware HDR scaling so EVERY palette colour reaches the
        // autoenhance UnrealBloom threshold (~0.85 luminance, +1 soft knee)
        // at the same effective intensity. Three's BloomNode threshold uses
        // Rec.709 weights; pure blue (Rec.709 lum 0.072) is the worst case —
        // at intensity=1 it peaks at 0.07 luminance, two octaves below
        // threshold. Compute the multiplier per colour that brings its
        // luminance to the target. Hue/saturation preserved (uniform RGB
        // scale), value is scaled. This is a targetLum, NOT a max(target,
        // base) — every colour hits the target regardless of native lum.
        function effectiveIntensity(rgb, targetLum) {
            const lum709 = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
            return targetLum / Math.max(lum709, 0.01);
        }

        // Uniforms — kept on a single bag so setColor() can update at runtime.
        const u = {
            lineColor:   uniform(new THREE.Vector3(...palette)),
            bgColor:     uniform(new THREE.Vector3(...bgColor)),
            lineWidth:   uniform(lineWidthPx),
            // lineIntensity is the TARGET luminance (Rec.709) that every
            // line pixel hits. The shader computes per-pixel boost as
            // (lineIntensity / lum_709(lineColor)) so dim hues (blue) are
            // boosted more, bright hues (amber) less, and all bloom equally.
            lineIntensity: uniform(lineIntensity),
            hdrChannelCap: uniform(hdrChannelCap),
            isMultiColor: uniform(isMulti ? 1.0 : 0.0),
        };
        // Multicolor palette uniforms (8 slots).
        const multiVecs = MULTI.map(c => new THREE.Vector3(...c));
        u.multi0 = uniform(multiVecs[0]); u.multi1 = uniform(multiVecs[1]);
        u.multi2 = uniform(multiVecs[2]); u.multi3 = uniform(multiVecs[3]);
        u.multi4 = uniform(multiVecs[4]); u.multi5 = uniform(multiVecs[5]);
        u.multi6 = uniform(multiVecs[6]); u.multi7 = uniform(multiVecs[7]);

        function pickMulti(idx) {
            const i = floor(idx).max(0).min(7);
            return mix(
                mix(
                    mix(u.multi0, u.multi1, step(0.5, i)),
                    mix(u.multi2, u.multi3, step(2.5, i)),
                    step(1.5, i)),
                mix(
                    mix(u.multi4, u.multi5, step(4.5, i)),
                    mix(u.multi6, u.multi7, step(6.5, i)),
                    step(5.5, i)),
                step(3.5, i),
            );
        }

        // Build the wireframe NodeMaterial. `useTriHash=true` means this
        // material expects a `triHash` attribute (multicolor); otherwise
        // a single-colour wireframe.
        function makeWireMaterial() {
            // MeshStandardNodeMaterial (PBR) — autoenhance's MRT setup
            // expects metalness/roughness nodes available so it can build
            // the metalrough channel. Using MeshBasicNodeMaterial caused
            // texture() compile errors when MRT introspected it. We bypass
            // the lighting pipeline entirely via `outputNode`, which is
            // the final fragment-output override.
            const mat = new THREE.MeshStandardNodeMaterial({
                color: 0xffffff, metalness: 0, roughness: 1,
            });
            mat.toneMapped = false;
            const bary = attribute('barycentric', 'vec3');
            const e = fwidth(bary).mul(u.lineWidth.mul(0.5));
            const aa = smoothstep(vec3(0, 0, 0), e, bary);
            const minA = min(min(aa.x, aa.y), aa.z);
            const lineMask = float(1).sub(minA);
            const triHash = attribute('triHash', 'float');
            // ALWAYS include the multicolor branch — gated by the
            // isMultiColor uniform at runtime. This way `setColor('multi')`
            // can flip in/out of multicolor without rebuilding the material.
            const multiCol = pickMulti(triHash.mul(8.0));
            // Per-triangle luminance correction for multicolor — every
            // palette slot has different Rec.709 luminance (yellow=0.93,
            // blue=0.07, white=1.0). Without correction the dim slots don't
            // reach bloom threshold while bright slots over-bloom. Bring
            // every triangle's luminance to u.lineIntensity (which is now
            // the target luminance, not a multiplier).
            const multiLum = max(dot(multiCol, vec3(0.2126, 0.7152, 0.0722)), 0.01);
            const multiBoost = u.lineIntensity.div(multiLum);
            const multiHDR = multiCol.mul(multiBoost);
            // Single-colour path: u.lineIntensity is the target luminance,
            // u.lineColor is the raw palette RGB, so the shader-side scaling
            // is the same form as multicolor for consistency.
            const singleLum = max(dot(u.lineColor, vec3(0.2126, 0.7152, 0.0722)), 0.01);
            const singleBoost = u.lineIntensity.div(singleLum);
            const singleHDR = u.lineColor.mul(singleBoost);
            const lcHDRRaw = mix(singleHDR, multiHDR, u.isMultiColor);
            // Per-channel HDR cap — prevents the single hot channel of
            // pure-blue / pure-red palette colours from going extreme HDR
            // and blowing out bloom in dense regions. Each channel
            // independently clamped to hdrChannelCap.
            const lcHDR = min(lcHDRRaw, vec3(u.hdrChannelCap));
            const finalRGB = mix(u.bgColor, lcHDR, lineMask);
            mat.outputNode = vec4(finalRGB, 1.0);
            return mat;
        }

        // Flat silhouette material (used for out-of-band meshes — too dense
        // or too sparse for the wireframe to read well; render as a plain
        // line-coloured shape instead). Also Standard-node based so MRT
        // metalness/roughness compile cleanly.
        function makeSilhouetteMaterial() {
            const mat = new THREE.MeshStandardNodeMaterial({
                color: 0xffffff, metalness: 0, roughness: 1,
            });
            mat.toneMapped = false;
            mat.outputNode = vec4(u.lineColor, 1.0);
            return mat;
        }

        // Replace materials and bake attributes on every mesh.
        const originalState = []; // [{mesh, geometry, material}, ...]
        let wireCount = 0, silCount = 0, totalTris = 0;
        scene.traverse((obj) => {
            if (!obj.isMesh) return;
            const origGeo = obj.geometry;
            const origMat = obj.material;
            const tris = origGeo.index
                ? Math.floor(origGeo.index.count / 3)
                : Math.floor(origGeo.attributes.position.count / 3);
            totalTris += tris;
            originalState.push({ mesh: obj, geometry: origGeo, material: origMat });
            // Wireframe everything — no silhouette fallback. The earlier
            // band-filter approach turned low-poly meshes (2-tri floor)
            // into solid line-coloured fills which read as the scene
            // background. Pixel-width lines + perspective-shrink already
            // give natural density equalization across viewing distance,
            // so no per-mesh density adjustment is needed.
            obj.geometry = addWireframeAttributes(origGeo);
            obj.material = makeWireMaterial();
            wireCount++;
        });
        // Set scene background to match
        scene.background = new THREE.Color(...bgColor);

        console.log(`[retro_wireframe] active — color=${colorMode}, wireframed ${wireCount} mesh(es); total scene tris=${totalTris}`);

        return {
            update() { /* per-frame no-op; uniforms only change via setColor */ },
            uniforms: u,
            setColor(name) {
                // u.lineIntensity stays at the target-luminance value the
                // material was constructed with — the shader divides by
                // each pixel's palette luminance for correct per-colour
                // boost. Just swap u.lineColor and the multicolor flag.
                if (name === 'multicolor') {
                    u.isMultiColor.value = 1.0;
                } else if (PALETTES[name]) {
                    u.lineColor.value.set(...PALETTES[name]);
                    u.isMultiColor.value = 0.0;
                } else {
                    throw new Error(`[retro_wireframe] unknown color "${name}"`);
                }
            },
            cleanup() {
                // Restore original materials/geometries (for re-applying or removing).
                for (const { mesh, geometry, material } of originalState) {
                    mesh.geometry = geometry;
                    mesh.material = material;
                }
            },
        };
    }

    globalThis.RetroWireframeFX = { applyTo };
    console.log('[retro_wireframe] registered');
})();
