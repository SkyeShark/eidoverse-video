// parallax_material.js — eidoverse's agent-facing wrapper around the
// silhouette-POM library `parallax_occlusion.js` (our own contribution to
// three.js, made with Fable). The library is a fully functional SPOM system:
// height-field ray-march, silhouette clipping, curved-surface silhouettes and
// self-shadowing. This file DOES NOT re-implement any of that — it imports
// `parallaxOcclusionUV` and wires its outputs ({ uv, missed, coverage, sample,
// shadow }) into a ready-to-render material, plus a one-call column builder.
//
// ─────────────────────────────────────────────────────────────────────────
// WHAT "SILHOUETTE" POM ACTUALLY IS (read this before you render)
// ─────────────────────────────────────────────────────────────────────────
// Plain POM fakes DEPTH on the INTERIOR of a flat quad — the outline still
// ends at the polygon edge. SILHOUETTE POM additionally carves the OUTLINE so
// the mesh edge follows the relief. You only SEE the difference by looking at
// the mesh EDGE against the background at a grazing angle:
//   • FLAT surfaces (wall/plate): the outline crenellates along the tile trim
//     instead of ending at the quad rectangle → use `silhouette:true` alone.
//   • CURVED surfaces (column/pipe/sphere): the relief must OVERHANG the base
//     cylinder's round outline. That needs THREE things together, and missing
//     any one renders as plain interior POM (the mistake that looks "flat"):
//        1. curvedSilhouette:true  + per-axis curvature   (clip past the horizon)
//        2. inflate: reliefWorld    → positionNode pushes the shell out so the
//           peaks physically extend beyond the base cylinder outline
//        3. a plain core cylinder just inside, to fill wherever the shell clips
//     `createReliefColumn()` wires all three for you — PREFER IT for columns.
//     Bold, DISCRETE protrusions (bolts, domes, blocks) read on the silhouette;
//     shallow ribs/grooves just scallop it faintly and look like shading.
//
// To evaluate a render: pull the camera BACK so the whole object, its silhouette
// against the background, AND its cast shadow on the floor are all in frame, put
// it in a LIT scene with a real floor, and ORBIT so the silhouette sweeps. A
// zoomed-in, barely-moving shot of a dark panel shows nothing.
//
// ─────────────────────────────────────────────────────────────────────────
// QUICK START
// ─────────────────────────────────────────────────────────────────────────
//   // A column whose flange rings overhang its round outline (full SPOM):
//   const col = createReliefColumn({
//       heightMap: hm, albedoMap: alb,   // white = peak in the height map
//       radius: 0.46, height: 3.4, aroundTiles: 3,
//       depthScale: 0.15, lightDir: KEY_DIR,   // KEY_DIR = world dir TOWARD the key light
//   });
//   scene.add(col);                      // returns a Group (shell + core + caps)
//
//   // A flat wall/plate that carves its outline along the relief trim:
//   const geo = new THREE.PlaneGeometry(9, 4.2);  geo.computeTangents(); // REQUIRED
//   const wall = new THREE.Mesh(geo, createParallaxMaterial({
//       heightMap: hm, albedoMap: alb, depthScale: 0.05, minViewZ: 0.14,
//       silhouette: true, lightDir: KEY_DIR,      // flat → curvedSilhouette stays off
//   }));
//   wall.castShadow = wall.receiveShadow = true;  scene.add(wall);
//
//   // Interior-only POM (no outline carving), e.g. a floor: silhouette:false.
//
// TANGENTS: the POM march runs in TANGENT space, so every POM mesh needs
// tangents — call `geometry.computeTangents()` after building the geometry.
// SAFETY NET: at first render the helper audits the scene; a POM mesh with no
// tangents gets them auto-computed (with a warning naming the mesh). If they
// can't be computed (non-indexed / missing uv or normal), the relief shading
// normal is disabled for that material instead of miscompiling the shader
// into an invisible mesh ("THREE.Node: Recursion detected" — that error on a
// POM surface means exactly this: a normal graph on tangent-less geometry).

import { parallaxOcclusionUV } from './parallax_occlusion.js';

export function installParallaxMaterial(THREE) {
    const {
        Fn, If, float, vec2, vec3, vec4, uv, dot, max, min, clamp, mix, normalize,
        color, texture, textureLevel, normalMap,
        positionLocal, normalLocal, positionWorld, normalWorld, tangentWorld, bitangentWorld,
        cameraViewMatrix, cameraProjectionMatrix, normalWorldGeometry, attribute, Discard,
    } = THREE;

    // Make the raw library callable from scene scripts too (advanced use).
    globalThis.parallaxOcclusionUV = parallaxOcclusionUV;

    const asPair = (v, d) => (Array.isArray(v) ? v : [v ?? d, v ?? d]);
    const boundsClamp = (coord, bounds) => {
        if (!bounds) return coord;
        const [bu, bv] = Array.isArray(bounds[0]) ? bounds : [bounds, bounds];
        return vec2(clamp(coord.x, float(bu[0]), float(bu[1])), clamp(coord.y, float(bv[0]), float(bv[1])));
    };

    // Warn (once per message key) so an agent gets actionable feedback in the
    // log without per-fragment/per-frame spam. Feedback is the point — a
    // silent flat render is the failure mode we are trying to prevent.
    const _warned = new Set();
    const warnOnce = (key, msg) => { if (!_warned.has(key)) { _warned.add(key); console.warn('[parallax] ' + msg); } };

    // ── first-render scene audit: heal tangent-less POM meshes ──────────────
    // The normal graph (NormalMapNode) needs REAL geometry tangents; without
    // them three falls back to a screen-derivative tangent frame that forms a
    // cycle with the marched UV → "Recursion detected" → invalid shader → the
    // mesh silently disappears. Materials never see their geometry, so the
    // check runs on the scene at render time: auto-compute where possible,
    // degrade (drop the relief normal) where not, and say exactly what to fix.
    const auditScene = (scene) => {
        if (!scene || !scene.isScene || scene.userData._parallaxTangentsAudited) return;
        scene.userData._parallaxTangentsAudited = true;
        scene.traverse((o) => {
            const m = o.isMesh ? o.material : null;
            if (!m || !m.userData || !m.userData.isParallaxMaterial) return;
            const g = o.geometry;
            if (!g || !g.attributes || g.attributes.tangent) return;
            const label = o.name || (g.type || 'mesh');
            // computeTangents() does NOT throw on unsupported geometry (it
            // console.errors and returns) — judge by whether the attribute
            // actually appeared.
            try { g.computeTangents(); } catch (e) { /* judged below */ }
            if (g.attributes.tangent) {
                warnOnce('healed-' + (o.uuid),
                    `${label}: POM geometry had no tangents — auto-computed them. The march runs in ` +
                    `tangent space; call geometry.computeTangents() after building POM geometry.`);
            } else if (m.normalNode) {
                m.normalNode = null; m.needsUpdate = true;
                warnOnce('degraded-' + (o.uuid),
                    `${label}: POM geometry has no tangents and computeTangents() could not add them ` +
                    `(needs indexed geometry with uv + normal). Disabled the relief shading normal for ` +
                    `this material so the shader compiles (would otherwise recurse → invisible mesh). ` +
                    `For full quality, build the geometry indexed, or add tangent attributes yourself.`);
            } else {
                warnOnce('notangent-' + (o.uuid),
                    `${label}: POM geometry has no tangents and computeTangents() could not add them — ` +
                    `the parallax march may be degraded on this mesh.`);
            }
        });
    };
    // Hook both render entry points once (pass-node pipelines go through
    // render(); direct scenes through renderAsync()).
    if (THREE.WebGPURenderer && !THREE.WebGPURenderer.prototype._parallaxAuditHooked) {
        THREE.WebGPURenderer.prototype._parallaxAuditHooked = true;
        for (const fn of ['render', 'renderAsync']) {
            const orig = THREE.WebGPURenderer.prototype[fn];
            if (typeof orig !== 'function') continue;
            THREE.WebGPURenderer.prototype[fn] = function (scene, camera, ...rest) {
                auditScene(scene);
                return orig.call(this, scene, camera, ...rest);
            };
        }
    }

    // Ray-march the height field and derive a shading normal from it by central
    // differences — so relief shades like real geometry WITHOUT a normal map.
    // (This is the single biggest reason a POM surface looks flat: no relief
    // normal → it shades like a printed decal.) Two marches: the normal graph
    // compiles in its own sub-build (library TSL note), and behind an
    // alpha-test discard the taps fetch at an explicit LOD (screen-derivative
    // sampling behind a discard miscompiles on some drivers).
    function buildRelief(heightMap, o) {
        const pomOpts = {
            uvNode: o.uvNode, scale: o.scale, minLayers: o.minLayers, maxLayers: o.maxLayers,
            minViewZ: o.minViewZ, silhouette: o.silhouette, silhouetteBounds: o.silhouetteBounds,
            curvedSilhouette: o.curvedSilhouette, curvature: o.curvature, sampleBounds: o.sampleBounds,
        };
        const main = parallaxOcclusionUV(heightMap, pomOpts);
        const forNormal = parallaxOcclusionUV(heightMap, pomOpts);

        const texel = o.texel;
        const strength = float(o.scale).div(float(4.0 * texel));
        const clipped = main.coverage !== null; // alpha-test path active
        // any texture fetched inside the normalNode graph obeys the same rule:
        const sampleForNormal = clipped
            ? (map, coord = forNormal.uv) => textureLevel(map, boundsClamp(coord, o.sampleBounds), 0)
            : (map, coord = forNormal.uv) => forNormal.sample(map, coord);

        const nUV = forNormal.uv;
        const tapAt = (coord) => sampleForNormal(heightMap, coord).r;
        const left = tapAt(nUV.sub(vec2(texel * 2.0, 0.0)));
        const right = tapAt(nUV.add(vec2(texel * 2.0, 0.0)));
        const bottom = tapAt(nUV.sub(vec2(0.0, texel * 2.0)));
        const top = tapAt(nUV.add(vec2(0.0, texel * 2.0)));
        const packed = vec3(left.sub(right).mul(strength), bottom.sub(top).mul(strength), 1.0)
            .normalize().mul(0.5).add(0.5);

        return { pomUV: main.uv, sample: main.sample, coverage: main.coverage, missed: main.missed,
            shadow: main.shadow, normalNode: normalMap(packed), sampleForNormal };
    }

    // ── low-level: build a material from a height map ────────────────────────
    // opts (all optional except heightMap):
    //   heightMap            THREE.Texture — height in .r, white = peak, RepeatWrapping for tiling
    //   albedoMap            THREE.Texture — surface color sampled at the marched UV
    //   depthScale  0.1      relief depth in UV-tile units (the library `scale`)
    //   minLayers 16 / maxLayers 96   march steps (head-on / grazing)
    //   silhouette  true     carve the outline (coverage → alpha test). false = interior POM only
    //   uvScale     1        number, or [uAround, vAlong] per-axis (cylinders tile ≠ per axis)
    //   curvedSilhouette false + curvature [2π/tilesAround, 0]   → curved outline (columns/pipes)
    //   inflate     0        world height to push the shell out along normals (flanges overhang)
    //   reliefShadow false   recesses self-shadow through the shadow map (needs worldPerTile+reliefWorld)
    //   worldPerTile [wU,wV] / reliefWorld   world size of one tile / relief peak, for reliefShadow
    //   lightDir  [x,y,z]    WORLD dir TOWARD the key light — drives self-shadow (+ reliefShadow)
    //   selfShadow true      surface self-shadow march;  shadowStrength/Steps/Bias/Floor tune it
    //   normalMap            explicit tangent-space normal map, sampled at the marched UV
    //   heightNormal         derive the shading normal from the height field by central
    //                        differences. Default: true when no normalMap is given, false when
    //                        one is (the explicit map wins) — pass heightNormal:true to override.
    //   silhouetteBounds     null → [0,1] flat / [-1e6,1e6] under curved; or explicit
    //   sampleBounds         end a tiling relief cleanly (see library docs)
    //   faceBounds  false    world-UV merged boxes: per-face bounds via uvMin/uvMax attributes
    //   lambert / selfLit    legacy escape hatches (unlit manual lambert) — rarely needed
    //   ...std material opts (color, roughness, metalness, roughnessMap, …)
    globalThis.createParallaxMaterial = function (opts = {}) {
        const {
            heightMap, albedoMap, normalMap: normalMapTex,
            depthScale = 0.1, minLayers = 16, maxLayers = 96,
            silhouette = true, uvScale = 1, minViewZ = 0.05,
            curvedSilhouette = false, curvature = null,
            silhouetteBounds = null, sampleBounds = null, faceBounds = false,
            inflate = 0,
            reliefShadow = false, worldPerTile = null, reliefWorld = null,
            selfShadow, lightDir,
            shadowStrength = 8, shadowSteps = 16, shadowBias = 0.03, shadowFloor = 0.2,
            heightNormal,
            ...stdOpts
        } = opts;
        if (!heightMap) throw new Error('[createParallaxMaterial] heightMap is required');

        const sil = !!silhouette && silhouette !== 'off';
        // an explicit normal map wins by default; the height-derived normal is
        // the default when none is given (relief shades like geometry).
        const useHeightNormal = heightNormal ?? !normalMapTex;

        // ── agent feedback: catch the exact mistakes that render "flat" ──
        if (curvedSilhouette && sil && !inflate && !faceBounds) {
            warnOnce('curved-no-inflate',
                'curvedSilhouette + silhouette but inflate:0 — the relief will clip to the base ' +
                'cylinder outline but the flanges will NOT overhang it (looks like plain interior POM). ' +
                'Pass inflate ≈ depthScale*(2π*radius/aroundTiles), or just use createReliefColumn().');
        }
        if (!sil && curvedSilhouette) {
            warnOnce('curved-no-sil', 'curvedSilhouette has no effect with silhouette:false (no outline is carved).');
        }
        if (reliefShadow && (!worldPerTile || reliefWorld == null)) {
            warnOnce('relief-no-world', 'reliefShadow needs worldPerTile:[wU,wV] and reliefWorld — skipping the marched shadow depth.');
        }

        const [su, sv] = asPair(uvScale, 1);
        const uvIn = (su === 1 && sv === 1) ? uv() : uv().mul(vec2(su, sv));
        // Under a curved silhouette, disable the tile-bounds clip so ONLY the
        // curve horizon clips (the library's column recipe); flat surfaces clip
        // to the tile [0,1].
        const bounds = silhouetteBounds ?? (curvedSilhouette ? [-1e6, 1e6] : [0, 1]);

        // faceBounds (world-UV merged boxes) supplies PER-FACE bounds from geometry
        // attributes, which a constant silhouetteBounds can't express — march
        // without the library's own silhouette there and clip via attributes.
        const libSil = sil && !faceBounds;
        const texel = 1.0 / ((heightMap.image && heightMap.image.width) || 1024);

        const relief = buildRelief(heightMap, {
            uvNode: uvIn, texel, scale: depthScale, minLayers, maxLayers, minViewZ,
            silhouette: libSil, silhouetteBounds: bounds, curvedSilhouette, curvature, sampleBounds,
        });
        const { pomUV, sample, coverage, missed, shadow, normalNode, sampleForNormal } = relief;

        // Self-shadow: world light dir → view space for the library shadow().
        const sunWorld = lightDir || (opts.selfLit && opts.selfLit.sunDir) || [0.5, 0.8, 0.4];
        let shadowFactor = null;
        if (selfShadow !== false && shadow) {
            const sw = new THREE.Vector3(...sunWorld).normalize();
            const lightView = cameraViewMatrix.mul(vec4(sw.x, sw.y, sw.z, 0.0)).xyz;
            const s = shadow(lightView, { steps: shadowSteps, strength: shadowStrength, bias: shadowBias });
            shadowFactor = s.mul(1.0 - shadowFloor).add(shadowFloor);
        }

        // material (real lit MeshStandard by default; legacy unlit hatches kept)
        let mat, litManual = false;
        if (opts.selfLit) {
            const o = { ...stdOpts }; delete o.lambert; delete o.selfLit;
            mat = new THREE.MeshStandardNodeMaterial(o); mat.lights = false; litManual = true;
        } else if (opts.lambert) {
            const o = { ...stdOpts }; delete o.roughness; delete o.metalness; delete o.lambert;
            mat = new THREE.MeshLambertNodeMaterial(o);
        } else {
            mat = new THREE.MeshStandardNodeMaterial(stdOpts);
        }
        mat.userData.isParallaxMaterial = true;    // → first-render tangent audit

        const albedoRGB = () => (albedoMap ? sample(albedoMap).rgb : vec3(0.8, 0.8, 0.8));
        const manualLambert = (rgb) => {
            const sl = opts.selfLit;
            const sd = new THREE.Vector3(...(sl.sunDir || [0.5, 0.8, 0.4])).normalize();
            return rgb.mul(vec3(...(sl.ambient || [0.35, 0.35, 0.35]))
                .add(vec3(...(sl.sunColor || [1, 1, 1])).mul(max(dot(normalWorldGeometry, vec3(sd.x, sd.y, sd.z)), 0.0))));
        };
        const shade = () => {
            let rgb = albedoRGB();
            if (shadowFactor) rgb = rgb.mul(shadowFactor);
            if (litManual) rgb = manualLambert(rgb);
            return rgb;
        };

        if (opts.debugMarch) {
            mat.colorNode = Fn(() => vec3(pomUV.x.fract(), pomUV.y.fract(), 0.5))();
            mat.lights = !!opts.debugMarchLit;
            return mat;
        }

        const faceMissed = faceBounds
            ? pomUV.x.lessThan(attribute('uvMin').x).or(pomUV.x.greaterThan(attribute('uvMax').x))
                .or(pomUV.y.lessThan(attribute('uvMin').y)).or(pomUV.y.greaterThan(attribute('uvMax').y))
            : null;

        if (sil) {
            if (opts.debugSilhouette) {
                const miss = faceBounds ? faceMissed : missed;
                mat.colorNode = Fn(() => { const out = shade().toVar(); If(miss, () => { out.assign(vec3(1.0, 0.0, 1.0)); }); return out; })();
            } else if (faceBounds) {
                mat.colorNode = Fn(() => { const out = shade().toVar(); If(faceMissed, () => { Discard(); }); return out; })();
            } else {
                // the library's coverage → the alpha-test silhouette path
                mat.colorNode = Fn(() => shade())();
                mat.opacityNode = coverage;
                mat.alphaTestNode = float(0.5);
                mat.alphaToCoverage = true;
                // cast shadows follow the carved outline, not the quad edge
                mat.maskShadowNode = coverage.greaterThanEqual(0.5);
            }
        } else {
            mat.colorNode = Fn(() => shade())();
        }

        // Shading normal (both variants need geometry tangents — see the
        // first-render audit above): height-derived by default, or an explicit
        // normal map sampled at the marched UV (dedicated sub-build march).
        if (useHeightNormal) {
            mat.normalNode = normalNode;
        } else if (normalMapTex) {
            mat.normalNode = normalMap(sampleForNormal(normalMapTex).xyz);
        }
        if (opts.roughnessMap) mat.roughnessNode = sample(opts.roughnessMap).r;
        if (opts.metalnessMap) mat.metalnessNode = sample(opts.metalnessMap).r;
        if (opts.aoMap) mat.aoNode = sample(opts.aoMap).r;

        // Shell inflation: push the rendered shell out along its normals by the
        // relief height (world units), so the peaks extend BEYOND the base mesh
        // silhouette — the parallax analogue of true displacement. The height
        // field floor stays at the original surface.
        if (inflate) mat.positionNode = positionLocal.add(normalLocal.mul(float(inflate)));

        // Relief cast/received shadow: write the marched hit's depth into the
        // shadow map and read it back at the same hit, so recesses genuinely
        // shadow themselves instead of projecting onto the smooth base surface.
        if (reliefShadow && sil && !faceBounds && worldPerTile && reliefWorld != null) {
            const height = sample(heightMap).r;
            const reliefOffset = pomUV.sub(uvIn);
            const reliefDrop = float(1.0).sub(height).mul(float(reliefWorld));
            const marched = positionWorld
                .add(tangentWorld.normalize().mul(reliefOffset.x.mul(float(worldPerTile[0]))))
                .add(bitangentWorld.normalize().mul(reliefOffset.y.mul(float(worldPerTile[1]))))
                .sub(normalWorld.normalize().mul(reliefDrop));
            const marchedClip = cameraProjectionMatrix.mul(cameraViewMatrix).mul(vec4(marched, 1.0));
            mat.depthNode = marchedClip.z.div(marchedClip.w);
            mat.receivedShadowPositionNode = marched;
        }

        return mat;
    };

    // Pre-flight check a mesh's geometry before building your own POM meshes
    // (createReliefColumn and the first-render audit already cover the common
    // paths; this is for explicit early feedback in scene setup).
    globalThis.checkReliefGeometry = function (geometry, label = 'mesh') {
        if (!geometry || !geometry.attributes || !geometry.attributes.tangent) {
            warnOnce('tangents-' + label,
                `${label}: geometry has no tangents — POM marches in tangent space. ` +
                `Call geometry.computeTangents() (needs indexed geometry with uv + normal).`);
            return false;
        }
        return true;
    };

    // ── high-level: a column/pipe whose flange relief OVERHANGS its outline ──
    // One call → a Group (inflated SPOM shell + fill core + end caps), wired
    // with curved silhouette, per-axis curvature, shell inflation and the
    // relief self-shadow. This is the correct way to get full silhouette POM
    // on a curved surface — reach for it before hand-wiring.
    //   opts: heightMap (req), albedoMap, radius 0.5, height 3, aroundTiles 3,
    //         depthScale 0.15, reliefFactor 1 (tame depth on thin pipes),
    //         lightDir [x,y,z] (toward key light), segments 64, caps true,
    //         coreColor, capColor, + any material opts (roughness, metalness…).
    // Rotate the returned Group to lay a pipe on its side.
    globalThis.createReliefColumn = function (opts = {}) {
        const {
            heightMap, albedoMap,
            radius = 0.5, height = 3.0, aroundTiles = 3,
            depthScale = 0.15, reliefFactor = 1.0,
            lightDir = [0.5, 0.8, 0.4], segments = 64, caps = true,
            coreColor = 0x272c34, capColor = 0x333944,
            ...matOpts
        } = opts;
        if (!heightMap) throw new Error('[createReliefColumn] heightMap is required');

        const group = new THREE.Group();
        const tileAround = 2 * Math.PI * radius / aroundTiles;
        const ringTiles = Math.max(2, Math.round(height / tileAround));
        const reliefWorld = depthScale * reliefFactor * tileAround;

        // inflated SPOM shell (open-ended cylinder)
        const shellGeo = new THREE.CylinderGeometry(radius, radius, height, segments, 1, true);
        shellGeo.computeTangents();
        const shell = new THREE.Mesh(shellGeo, createParallaxMaterial({
            heightMap, albedoMap,
            depthScale: depthScale * reliefFactor,
            uvScale: [aroundTiles, ringTiles],
            silhouette: true, curvedSilhouette: true, curvature: [2 * Math.PI / aroundTiles, 0],
            inflate: reliefWorld,
            reliefShadow: true, worldPerTile: [tileAround, height / ringTiles], reliefWorld,
            lightDir, ...matOpts,
        }));
        shell.castShadow = shell.receiveShadow = true;
        group.add(shell);

        // plain core just inside the shell fills wherever the shell clips
        const core = new THREE.Mesh(
            new THREE.CylinderGeometry(radius - 0.005, radius - 0.005, height, segments),
            new THREE.MeshStandardNodeMaterial({ color: coreColor, roughness: 0.6, metalness: 0.25 }));
        core.castShadow = core.receiveShadow = true;
        group.add(core);

        // flat end caps sized to the flange radius the relief cannot fake
        if (caps) {
            const capR = radius + reliefWorld * 0.95;
            const capGeo = new THREE.CylinderGeometry(capR, capR, 0.07, segments);
            const capMat = new THREE.MeshStandardNodeMaterial({ color: capColor, roughness: 0.5, metalness: 0.3 });
            for (const end of [-1, 1]) {
                const cap = new THREE.Mesh(capGeo, capMat);
                cap.position.y = end * (height / 2 + 0.02);
                cap.castShadow = cap.receiveShadow = true;
                group.add(cap);
            }
        }

        group.userData.reliefWorld = reliefWorld;
        group.userData.shell = shell;
        return group;
    };
}
