// makeRingworld — loads the authored RINGWORLDskyelement.glb (v2 export:
// "walls" and "terrain" pre-split) and dresses it for alien skies (task #41):
//   · WALLS: fresh cylindrical-planar UVs (arc-length u, radial v, in
//     panel-tile units, per-triangle seam unwrap) + tiled solar-panel PBR —
//     the authored wall UVs were smeared band UVs
//   · TERRAIN: authored geometry/normals/map untouched; landmask-gated
//     ANIMATED WATER (dark reflective color, scrolling shimmer on
//     color/roughness) — water = the mask's BLACK blobs (ground truth from
//     the authored Blender render: majority terrain, reflective lakes)
//
//   const ring = await globalThis.makeRingworld({ glbBytes: ASSETS.ring,
//       textures: { landmask, solarColor, solarNormal, solarRough, solarMetal },
//       opts: { panelTile: 60 } });
//   scene.add(ring.group);   // per frame: ring.update(t)
(function () {
    const T3 = globalThis.THREE;

    globalThis.makeRingworld = async function ({ glbBytes, textures = {}, opts = {} } = {}) {
        const { texture, uv, mix, smoothstep, float, vec2, vec3, fract, floor, uniform } = T3;
        // Debug/override gates, declared at function entry because consumers are
        // spread through the build (RINGNSAT in the terrain shading, RINGNOCLOUD
        // at the cloud sheet, RINGFOGWALL/RINGRAINWALL at the horizon walls).
        const _envRG = (k) => globalThis.Deno?.env?.get?.(k);

        // ---- parse GLB, find the split meshes ----
        const buf = glbBytes.buffer.slice(glbBytes.byteOffset, glbBytes.byteOffset + glbBytes.byteLength);
        const gltf = await new Promise((res, rej) => new globalThis.GLTFLoader().parse(buf, '', res, rej));
        gltf.scene.updateMatrixWorld(true);
        let walls = null, terrain = null;
        // GLTFLoader owns these decoded textures. The scene wrapper replaces
        // the source materials, but still samples the authored color/normal
        // maps from its node graph. Expose the complete owned set so a
        // Ringworld preset rebuild can explicitly retire their GPU storage.
        const sourceTextures = new Set();
        const sourceMaterials = new Set();
        gltf.scene.traverse((o) => {
            if (!o.isMesh) return;
            const meshMaterials = Array.isArray(o.material) ? o.material : [o.material];
            for (const material of meshMaterials) {
                if (!material) continue;
                sourceMaterials.add(material);
                for (const value of Object.values(material)) {
                    if (value?.isTexture) sourceTextures.add(value);
                }
            }
            if (/wall/i.test(o.name)) walls = o;
            else if (/terrain|band|ground/i.test(o.name)) terrain = o;
        });
        if (!walls || !terrain) throw new Error(`[ringworld] expected "walls" + "terrain" meshes, got walls=${!!walls} terrain=${!!terrain}`);
        const origMat = Array.isArray(terrain.material) ? terrain.material[0] : terrain.material;
        console.log(`[ringworld] walls=${walls.geometry.getAttribute('position').count}v terrain=${terrain.geometry.getAttribute('position').count}v`);

        // ---- shared ARC LIGHT + AERIAL PERSPECTIVE state (engine-owned) ----
        // The arc is never shaded by scene lights (they leak — layer masking
        // doesn't mask on this backend), but it IS seen through the local
        // atmosphere: per-channel transmittance by apparent elevation with
        // longer optical paths at low local sun, inscatter toward the local
        // horizon palette, and a fixed-tonemap exposure emulation so the arc
        // tracks the day cycle instead of blazing constant-noon (Halo Infinite
        // behavior, not classic-Halo baked textures).
        const uSunDir = new T3.Vector3(0, 1, 0);      // TRUE astronomical sun (fed by update() from the bound sky)
        const uRingC = new T3.Vector3(0, 4940, 0);    // ring center world (read from the group's world pose)
        const uSunDirN = T3.uniform(uSunDir);
        const uRingCN = T3.uniform(uRingC);
        const uHazeCol = T3.uniform(new T3.Color(0.55, 0.62, 0.72));   // local HORIZON palette (fed per frame)
        const uSunCol = T3.uniform(new T3.Color(1, 0.98, 0.94));       // local SUN color (fed per frame)
        const uSunElev = T3.uniform(0.5);                              // local sun elevation (sunDir.y)
        const uMoonDirN = T3.uniform(new T3.Vector3(0, 1, 0));         // moon/planet dir — night-side relief light (planet-shine)
        const uRainHazeN = T3.uniform(0);                              // blended rain strength — sub-cloud rain veil (fed per frame)
        const tU = T3.uniform(0);                                      // module time — declared HERE because arcShade's curtain field builds before the sheet block (TDZ)
        // Research-verified model (Halo Infinite / Hillaire): the arc is SUNLIT
        // TERRAIN inside the same TOD sim — its radiance TRACKS the local sun
        // (dayFactor, wrap floor), is seen through per-channel air-mass
        // transmittance, gains a palette inscatter veil that collapses at
        // night, and a day/night gain guards the fixed-exposure ACES shoulder.
        const arcShade = () => {
            const { vec3: v3, float: f, mix: mx, smoothstep: ss, clamp: cl } = T3;
            const Pw = T3.positionWorld;
            const inward = T3.normalize(v3(f(0), uRingCN.y.sub(Pw.y), uRingCN.z.sub(Pw.z)));
            const dSun = T3.dot(inward, uSunDirN);
            const litK = ss(f(-0.22), f(0.30), dSun);                                       // WIDE terminator — a penumbra that blends, never a hard line
            const warmT = mx(v3(1.14, 0.82, 0.55), v3(1, 1, 1), cl(dSun.mul(2), f(0), f(1))); // golden band eases across the same width
            const pVis = ss(f(-0.38), f(0.48), T3.dot(inward, uMoonDirN)).pow(0.8);          // planet-shine terminator: WIDE + lifted toe — the dot compresses fast near planetrise, so the band must be generous to stay soft on screen
            const dayF = ss(f(-0.10), f(0.15), uSunElev);                                    // how "day" it is locally
            const sunTerm = uSunCol.mul(mx(f(0.22), f(1), dayF));                            // radiance tracks the LOCAL sun (wrap floor = ring-shine/altitude)
            const viewD = T3.normalize(Pw.sub(T3.cameraPosition));
            const amass = f(1).div(T3.max(viewD.y, f(0.0264)));                              // air mass, horizon-capped ~38
            // ×0.55: the band sits at 5-8 km INSIDE the atmosphere — full
            // to-space optical depth overstates the haze and washes the arc
            const trans0 = T3.exp(v3(0.030, 0.072, 0.154).mul(amass).negate());              // Hillaire depths scaled to the band's altitude
            // SUB-CLOUD RAIN VEIL: in rain, everything seen through the falling
            // layer hazes toward the horizon palette. Path length = the ray's
            // run below the local cloud ceiling — the near arc plunging behind
            // the horizon crosses kilometres of rain and washes out, while
            // high-elevation rays exit the layer in a few hundred metres (rain
            // only exists UNDER the clouds; the deck itself hides what's above).
            const fragD = T3.length(Pw.sub(T3.cameraPosition));
            const underLen = T3.min(fragD, cl(f(730).sub(T3.cameraPosition.y), f(0), f(1e5)).div(T3.max(viewD.y, f(0.02))));
            // the veil hugs the RAIN LAYER: full on fragments below the cloud
            // ceiling, gone by ~3× ceiling — pure slant-path length also fogged
            // the HIGH arc (a flat fog band way above the weather, Skye's catch)
            const belowClouds = ss(f(2200), f(730), Pw.y);
            // RAIN CURTAINS: a uniform veil reads as white plaster (Skye's
            // catch). Real distance-rain falls in drifting sheets — a 2-octave
            // noise in view-direction space (near-columnar at the horizon,
            // where the veil lives) modulates the optical depth: dense bands
            // close over the arc, gaps let it ghost through, and the whole
            // field crawls with time like wind-blown curtains.
            const h2c2 = (p) => {
                const a3 = T3.fract(v3(p.x, p.y, p.x).mul(0.1031));
                const dd = T3.dot(a3, v3(a3.y, a3.z, a3.x).add(33.33));
                const b3 = a3.add(dd);
                return T3.fract(b3.x.add(b3.y).mul(b3.z));
            };
            const vn2 = (p) => {
                const i = T3.floor(p), fr = T3.fract(p);
                const smf = fr.mul(fr).mul(f(3).sub(fr.mul(2)));
                return mx(mx(h2c2(i), h2c2(i.add(T3.vec2(1, 0))), smf.x),
                    mx(h2c2(i.add(T3.vec2(0, 1))), h2c2(i.add(T3.vec2(1, 1))), smf.x), smf.y);
            };
            const cD = tU.mul(0.028);
            const curt = vn2(viewD.xz.mul(6).add(T3.vec2(cD, cD.mul(0.3)))).mul(0.65)
                .add(vn2(viewD.xz.mul(14).sub(T3.vec2(cD.mul(1.7), 0))).mul(0.35));
            const rainT = T3.exp(underLen.mul(uRainHazeN).mul(belowClouds)
                .mul(f(0.0018).mul(curt.mul(1.2).add(0.4))).negate());
            const veil = f(0.35).add(dayF.mul(0.65));                                        // the veil collapses at night
            // fold the rain layer into the air result: (surface·trans + insc)
            // attenuates by rainT and the rain's own inscatter fills the gap —
            // every arcShade consumer (terrain/walls/water/ring clouds)
            // inherits the veil from this one spot
            const trans = trans0.mul(rainT);
            // rain fill ×0.55: the palette horizon is brighter than the actual
            // rain sky (bg grey + cloud occlusion) — an un-dimmed fill made the
            // hazed arc GLOW ~35% brighter than the sky it should melt into.
            // The curtain field also shades the fill (dense sheets read a
            // touch darker-grey) so the murk itself has cloudy structure.
            // NIGHT COLLAPSE. Inscatter is light scattered INTO the view ray,
            // so it is proportional to the light available to scatter — at
            // night there is almost none. Left at full strength it is a flat
            // ADDITIVE veil that swamps every relief-modulated term on the
            // night side (which is scaled right down), and the arc reads as a
            // smooth blue wash with the normal-map detail visible but drowned.
            // Daytime is unaffected: there litArc dwarfs the veil anyway.
            const inscNight = mx(f(Number(globalThis.Deno?.env?.get?.('RINGINSCN') ?? 0.28)), f(1), dayF);
            const insc = uHazeCol.mul(f(1).sub(trans0)).mul(veil).mul(rainT)
                .add(uHazeCol.mul(f(1).sub(rainT)).mul(veil).mul(f(0.55))
                    .mul(f(1.08).sub(curt.mul(0.22))))
                .mul(inscNight);
            const gain = mx(f(0.15), f(1), dayF)                                             // NIGHT_GAIN..DAY_GAIN for fixed-exposure ACES
                .mul(mx(f(0.4), f(1), ss(f(-0.05), f(0.12), uSunElev)));                     // extra twilight rolloff — no sunset spike
            // the far arc is STILL fully sunlit at local midnight — its lit
            // segments are at THEIR noon (Niven's Arch never turns off).
            // Track the local sun through day/dusk (fixed-exposure emulation),
            // then HAND OVER to a dusk-level hold in WHITE daylight — never to
            // the night palette, which crushed the sunlit side below display
            // black and turned the night terminator into a hard cliff.
            const arch = ss(f(0.10), f(-0.06), uSunElev);
            const litCol = mx(sunTerm.mul(gain), v3(0.90, 0.93, 1).mul(f(0.24)), arch);
            const foot = f(1).sub(ss(f(0.0), f(0.022), viewD.y));                            // only the true FOOT dissolves — not the low arc's detail
            return { litK, warmT, trans, insc, expK: gain, litCol, dSun, sunTerm, foot, dayF, pVis };
        };

        // ---- WALL UVs: cylindrical-planar, tiles in panel units ----
        // u = arc length around the ring / tile, v = radius / tile. Non-indexed
        // so the ±π seam triangles can unwrap independently instead of
        // interpolating the whole range across one face.
        const R_REF = 5000;
        const tile = opts.panelTile ?? 60;
        {
            const g = walls.geometry.index ? walls.geometry.toNonIndexed() : walls.geometry;
            walls.geometry = g;
            const wp = g.getAttribute('position');
            const wu = new Float32Array(wp.count * 2);
            for (let t = 0; t < wp.count / 3; t++) {
                const th = [], rr = [];
                for (let k = 0; k < 3; k++) {
                    const y = wp.getY(t * 3 + k), z = wp.getZ(t * 3 + k);
                    th.push(Math.atan2(z, y)); rr.push(Math.hypot(y, z));
                }
                const mx = Math.max(...th), mn = Math.min(...th);
                for (let k = 0; k < 3; k++) {
                    let a = th[k];
                    if (mx - mn > Math.PI && a < 0) a += Math.PI * 2;  // seam unwrap
                    wu[(t * 3 + k) * 2] = a * R_REF / tile;
                    wu[(t * 3 + k) * 2 + 1] = rr[k] / tile;
                }
            }
            g.setAttribute('uv', new T3.BufferAttribute(wu, 2));
        }
        for (const key of ['solarColor', 'solarNormal', 'solarRough', 'solarMetal']) {
            if (textures[key]) { textures[key].wrapS = textures[key].wrapT = T3.RepeatWrapping; }
        }
        walls.material = new T3.MeshStandardNodeMaterial({
            map: textures.solarColor ?? null,
            normalMap: textures.solarNormal ?? null,
            roughnessMap: textures.solarRough ?? null,
            metalnessMap: textures.solarMetal ?? null,
            roughness: 1, metalness: textures.solarMetal ? 1 : 0.6, fog: false,
        });
        walls.material.userData.keepEnv = true;   // sky element: metal panels NEED the sky env or they render black under env suppression
        // walls follow the same arc rules: self-emissive (no scene lamps),
        // terminator'd, and seen through the local air
        if (textures.solarColor) {
            const { texture: texN, uv: uvN, float: fN, mix: mxN } = T3;
            const A = arcShade();
            const panel = texN(textures.solarColor, uvN()).rgb;
            const wallLit = panel.mul(A.warmT).mul(fN(0.55));
            const wallNight = panel.mul(fN(0.05));
            walls.material.emissiveNode = mxN(wallNight, wallLit, A.litK).mul(A.trans)
                .mul(T3.max(A.expK, fN(0.20)))   // Arch hold: sunlit panels stay dimly visible at local night, matching the band
                .add(A.insc.mul(fN(0.85)));
            walls.material.colorNode = T3.vec3(0);
        }

        // ---- TERRAIN: authored look + landmask water (mask BLACK = water) ----
        textures.landmask.wrapS = textures.landmask.wrapT = T3.RepeatWrapping;
        textures.landmask.colorSpace = T3.NoColorSpace;
        const bandMat = new T3.MeshStandardNodeMaterial({ roughness: 1, metalness: 0, fog: false });
        bandMat.userData.keepEnv = true;          // sky element — keeps the baked sky env under reflection-hook suppression
        let sysArcLight = null;                   // set inside the band block (terminator uniforms)
        // `lightweight` preserves moving water in the realtime skybox with two
        // filtered reads from the already-resident band normal. `full` retains
        // the older procedural value-noise field for offline/lookdev callers.
        // This mode is selected by the Ringworld wrapper, not by sky quality.
        const waterWaveMode = opts.waves === false ? 'off'
            : (opts.waves === 'lightweight' ? 'lightweight' : 'full');
        let waterWavesActive = false;
        {
            const uvB = uv();
            // the landmask is the MAP's texel-for-texel companion (same
            // 2172×724 layout) — it tiles with the map's KHR transform (8×1
            // around the ring), so water lines up with the water PAINTED IN
            // COLOR. Explicit-uv TSL sampling bypasses texture.matrix, so the
            // transform is applied by hand to BOTH.
            const repM = origMat.map.repeat, offM = origMat.map.offset;
            const uvT = uvB.mul(vec2(repM.x, repM.y)).add(vec2(offM.x, offM.y));
            // the mask arrives via loadImageTexture (row order as-displayed)
            // while the GLB map is GLTF-convention (flipY=false) — same image
            // space, OPPOSITE v at sample time. Without this flip the water
            // splotches render v-mirrored across the band from the painted seas.
            const mRaw = texture(textures.landmask, vec2(uvT.x, float(1).sub(uvT.y))).r;
            const k = smoothstep(0.45, 0.55, opts.waterWhite ? mRaw : float(1).sub(mRaw));
            // canonical sin-free hash21 (Hoskins) — the simple fract-product
            // hash correlates at large lattice coords (giant pseudo-tiling)
            const h2 = (p) => {
                const a = fract(vec3(p.x, p.y, p.x).mul(0.1031));
                const d = T3.dot(a, vec3(a.y, a.z, a.x).add(33.33));
                const b = a.add(d);
                return fract(b.x.add(b.y).mul(b.z));
            };
            const vn = (p) => {
                const i = floor(p), f = fract(p);
                const s = f.mul(f).mul(float(3).sub(f.mul(2)));
                const a = h2(i), b = h2(i.add(vec2(1, 0))), c = h2(i.add(vec2(0, 1))), d = h2(i.add(vec2(1, 1)));
                return mix(mix(a, b, s.x), mix(c, d, s.x), s.y);
            };
            // frequency ratio matches the band's physical aspect (u spans the
            // full 31 km ring, v ~1 km) so features stay isotropic
            const drift = tU.mul(0.012);
            const shimRaw = vn(uvB.mul(vec2(900, 30)).add(vec2(drift, drift.mul(0.7))))
                .add(vn(uvB.mul(vec2(1700, 56)).sub(vec2(drift.mul(1.6), drift)))).mul(0.5);
            // no mips on procedural noise: fade shimmer/waves to their mean
            // before the cells go sub-pixel and alias into stripes at distance
            const camDist = T3.length(T3.positionWorld.sub(T3.cameraPosition));
            const farK = smoothstep(float(2500), float(9000), camDist);
            const shim = mix(shimRaw, float(0.5), farK);
            const land = texture(origMat.map, uvT).rgb;
            // dark low-saturation water — the silvery authored look comes from
            // REFLECTION (low roughness + env/sun), not albedo blue
            const deep = vec3(0.020, 0.042, 0.055), shallow = vec3(0.055, 0.10, 0.115);
            const waterCol = mix(deep, shallow, shim).add(shim.pow(8).mul(0.3)); // sparkle crests
            // ARC LIGHTING + AERIAL PERSPECTIVE (shared arcShade): unlit
            // self-emissive terminator model, relief shaded against the TRUE
            // sun via the normal-mapped surface, then the whole thing seen
            // THROUGH the local air — transmittance dims/warms it, inscatter
            // washes it toward the local horizon palette, exposure tracks the
            // day cycle. Constant-noon Vegas and black-arc are both wrong.
            const A = arcShade();
            // baked cavity AO: sun-angle-INDEPENDENT relief — a normal map
            // goes flat when a segment's sun nears its local noon (light ∥
            // mean normal); valleys staying dark is what keeps the terrain
            // reading 3D at every time of day (Halo bakes this into vistas).
            // LAND only — seas stay flat (k = water mask).
            let albedoArc = mix(land, waterCol, k);
            let nightAO = float(1);
            if (textures.bandAO) {
                textures.bandAO.wrapS = textures.bandAO.wrapT = T3.RepeatWrapping;
                textures.bandAO.colorSpace = T3.NoColorSpace;
                const aoS = texture(textures.bandAO, vec2(uvT.x, float(1).sub(uvT.y))).r;
                const aoK = mix(mix(float(0.62), float(1.06), aoS), float(1), k);
                albedoArc = albedoArc.mul(aoK);
                nightAO = mix(aoS.mul(aoS).mul(1.15), float(1), k);   // deeper valley shadow under moonlight (land only)
            }
            // REAL normal-map relief in the UNLIT path: material.normalNode
            // only feeds LIT shading — an emissive band must perturb its own
            // normal. The band is a cylinder about X, so the tangent frame is
            // analytic and exact: radial, around-ring, and X̂ across the band.
            let relief, nightRelief;
            if (textures.bandNormal) {
                const PwB = T3.positionWorld;
                const rHat = T3.normalize(vec3(float(0), PwB.y.sub(uRingCN.y), PwB.z.sub(uRingCN.z)));  // radial OUT
                const nGeo = rHat.negate();                                        // inner-surface normal
                const tAround = T3.normalize(T3.cross(vec3(1, 0, 0), rHat));       // +u around the ring
                const nmS = texture(textures.bandNormal, vec2(uvT.x, float(1).sub(uvT.y))).xyz.mul(2).sub(1);
                const pertN = T3.normalize(tAround.mul(nmS.x).add(vec3(1, 0, 0).mul(nmS.y)).add(nGeo.mul(nmS.z)));
                // LIT-side face-on flatness — the mirror of the night problem
                // solved below. dot(N, sunDir) loses ALL slope response when
                // the star sits face-on to a segment, and that is exactly the
                // geometry of the far arc at LOCAL NIGHT: still fully sunlit,
                // but seen face-on, so the band reads as a painted map with no
                // relief. Rake the lit term the same way the night term is
                // raked, and blend it in by how face-on the light has become
                // (grazing segments keep the true dot, which is correct there).
                const nmL = T3.normalize(tAround.mul(nmS.x.mul(2.3)).add(vec3(1, 0, 0).mul(nmS.y.mul(2.3))).add(nGeo.mul(nmS.z)));
                const sTan = T3.normalize(uSunDirN.sub(nGeo.mul(T3.dot(uSunDirN, nGeo))).add(vec3(0.02, 0, 0.01)));
                const sRake1 = T3.normalize(sTan.add(nGeo.mul(0.35)));
                const sRake2 = T3.normalize(T3.cross(nGeo, sTan).add(nGeo.mul(0.35)));
                const litRake = T3.clamp(
                    float(0.22).add(T3.dot(nmL, sRake1).mul(1.05)).add(T3.dot(nmL, sRake2).abs().mul(0.45)),
                    float(0.08), float(1.4));
                // Never let the rake drop out entirely: a pure face-on test
                // leaves a band of intermediate angles where the plain dot is
                // ALREADY flattening but the rake has not faded in — the
                // "flat at certain lighting angles" gap. Floor the blend so
                // some slope response is always present, ramping to full when
                // the light goes face-on.
                const faceOn = T3.clamp(T3.dot(uSunDirN, nGeo).abs().sub(0.05).mul(1.8).add(0.38), float(0.38), float(1));
                relief = mix(T3.clamp(T3.dot(pertN, uSunDirN), float(0), float(1)), litRake, faceOn);
                // NIGHT: the planet illuminant sits near face-on to the visible
                // arc — dot(pertN, moonDir) ≈ nz ± a few % = noon-flatness all
                // over again. RAKE the night light instead: project the moon
                // dir onto the band's tangent plane (grazing, moonrise-style)
                // and exaggerate the night normal amplitude — relief responds
                // at full strength regardless of where the planet sits.
                const nmN = T3.normalize(tAround.mul(nmS.x.mul(2.3)).add(vec3(1, 0, 0).mul(nmS.y.mul(2.3))).add(nGeo.mul(nmS.z)));
                const mTan = T3.normalize(uMoonDirN.sub(nGeo.mul(T3.dot(uMoonDirN, nGeo))).add(vec3(0.02, 0, 0.01)));
                // BI-DIRECTIONAL hillshade: a single rake has a blind axis —
                // ridges perpendicular to it read flat (the mid-planetrise
                // flat zone). The giant is a huge close disc + ring-shine, a
                // genuinely soft multi-directional source: main rake at ~20°
                // elevation plus an unsigned perpendicular secondary models
                // every slope orientation.
                const rake1 = T3.normalize(mTan.add(nGeo.mul(0.35)));
                const tPerp = T3.normalize(T3.cross(nGeo, mTan));
                const rake2 = T3.normalize(tPerp.add(nGeo.mul(0.35)));
                const s1 = T3.dot(nmN, rake1);
                const s2 = T3.dot(nmN, rake2).abs();
                nightRelief = T3.clamp(float(0.22).add(s1.mul(1.15)).add(s2.mul(0.5)), float(0.08), float(1.5));
            } else {
                relief = T3.clamp(T3.dot(T3.normalWorld, uSunDirN), float(0), float(1));
                nightRelief = relief;
            }
            // night side is PLANET-SHINE lit — the same relief that shapes the
            // day terrain shapes the night terrain under the giant's light.
            // CRITICAL: calibrated OUTSIDE the day exposure gain — the gain
            // exists to stop the LIT side clipping; multiplied into the night
            // term it crushed it to ~0.3% luminance (flat black cutout, only
            // the water/land albedo boundary surviving — Skye's catch).
            const nightVis = float(1).sub(A.dayF);
            // planet-shine only reaches segments with the giant above THEIR
            // horizon — elsewhere the night side drops to a starlight +
            // ring-shine floor. The floor must sit ABOVE display black: at
            // 0.15 everything past mid-gradient crushed under the ACES toe,
            // so the smooth pVis terminator READ as a hard edge and the
            // no-shine zone lost its relief entirely (flat black band).
            const shine = float(0.40).add(A.pVis.mul(0.60));
            // 0.42 -> 0.60: with the inscatter veil no longer propping up the
            // night side, that brightness has to come from the term that
            // actually RESPONDS to relief, or the arc goes flat-black again
            // (the failure the shine floor above was added to prevent).
            // NIGHT TINT — cool, but nowhere near as saturated as it was.
            // (0.30, 0.34, 0.50) put blue at 1.67x red, which overwhelmed the
            // terrain's own greens and browns: the relief resolved fine but
            // every biome read as the same uniform blue. This is the same
            // Rec.709 luma (0.343) with blue pulled back to 1.22x red, so the
            // arc keeps a moonlit cast while the albedo's chroma survives.
            // opts.nightTint overrides.
            const nt = opts.nightTint ?? [0.321, 0.345, 0.392];
            // SATURATION RECOVERY. Measured on an arc-only crop, the night side
            // has healthy CONTRAST (Y spread 112 vs day's 103) but its chroma
            // range collapses: V (red<->green) spans 39 by day and only 20 at
            // night, with nothing below neutral — the terrain's greens simply
            // vanish and the arc reads as a flat wash. That is not an additive
            // veil (inscatter was ruled out by bisect: V spread 20/20/19 at
            // insc 0.28/0.10/0.0); it is the night term being so dark that
            // 8-bit chroma quantises away. Expanding chroma about the term's
            // own luma restores the hue separation without touching contrast
            // or brightness. opts.nightSat overrides; 1 = off.
            const nSat = float(Number(_envRG('RINGNSAT') ?? opts.nightSat ?? 1.3));
            let nBase = albedoArc.mul(vec3(nt[0], nt[1], nt[2]));
            const nLum = T3.dot(nBase, vec3(0.2126, 0.7152, 0.0722));
            nBase = mix(vec3(nLum, nLum, nLum), nBase, nSat).max(vec3(0));
            // 0.60 -> 1.20. THE dominant cause of the washed-out night arc, and
            // it is not a colour bug: measured local detail was already fine
            // (high-pass energy 5.16 at night vs 5.44 by day, i.e. equal), but
            // the arc sat at mean luma 32/255 against day's 139 — deep in the
            // ACES toe, where the curve compresses AND desaturates. Chroma
            // range therefore grows SUPERLINEARLY as the level rises: V spread
            // 35 -> 52 -> 67 at levels 0.60 / 1.20 / 2.00. Lifting out of the
            // toe is what restores the terrain's hue separation; the small
            // nSat above only tops it up. opts.nightLevel / RINGNLEV override.
            const nLev = float(Number(_envRG('RINGNLEV') ?? opts.nightLevel ?? 1.20));
            const nightSide = nBase.mul(nightRelief).mul(nightAO).mul(shine).mul(nLev).mul(nightVis);
            // strong graze response: at a segment's local morning/evening the
            // ridges catch the sun and the valleys drop out — the flat-at-noon
            // residue is carried by the baked AO above
            const litArc = albedoArc.mul(A.warmT).mul(A.litCol).mul(float(0.22).add(relief.mul(1.05)));
            bandMat.colorNode = vec3(0);
            // animated water shimmer survives the day-cycle dimming: added
            // AFTER the air/exposure terms; lit seas glint by sun, night seas
            // glint by planet-shine (sun glints ride the day gain so the
            // night Arch doesn't glitter at full noon strength)
            const sparkle = k.mul(shim.pow(8)).mul(float(0.55))
                .mul(A.litK.mul(mix(float(0.35), float(1), A.dayF)).add(nightVis.mul(0.5)));
            const arcOut = litArc.mul(A.litK).mul(A.trans)
                .add(nightSide.mul(float(1).sub(A.litK)).mul(A.trans))
                .add(A.insc.mul(float(0.68)))
                .add(sparkle);
            // RINGFOOT0=1: debug — the foot veil assumes a GROUND camera (ray
            // near horizontal = band foot in local haze); from an exterior
            // camera it whitewashes the whole lower arc and impersonates a
            // cloud lining (Skye's catch)
            bandMat.emissiveNode = globalThis.Deno?.env?.get?.('RINGFOOT0') === '1'
                ? arcOut
                : mix(arcOut, uHazeCol, A.foot.mul(float(0.8)));   // foot -> local horizon haze
            if (globalThis.Deno?.env?.get?.('RINGDBG') === '1') {
                // TEMP diagnostic: R=sun terminator, G=planet-shine terminator, B=night relief
                bandMat.emissiveNode = vec3(A.litK, A.pVis, nightRelief.mul(float(0.4)));
            }
            bandMat.roughnessNode = mix(float(0.95), float(0.07).add(shim.mul(0.16)), k);
            bandMat.metalnessNode = float(0);
            sysArcLight = { sunDir: uSunDirN, center: uRingCN, hazeCol: uHazeCol, sunCol: uSunCol, sunElev: uSunElev, moonDir: uMoonDirN };
            // optional SMOOTH terrain relief (textures.bandNormal): a height-
            // derived normal map (blurred landmask plateaus + broad interior
            // swell — no high-frequency noise) so grazing light models the
            // band instead of reading flat. Same uv convention as the mask
            // (loadImageTexture row order -> v flipped vs the GLB map).
            if (textures.bandNormal) {
                textures.bandNormal.wrapS = textures.bandNormal.wrapT = T3.RepeatWrapping;
                textures.bandNormal.colorSpace = T3.NoColorSpace;
                const nSample = texture(textures.bandNormal, vec2(uvT.x, float(1).sub(uvT.y)));
                const ns = opts.bandNormalScale ?? 1.4;
                bandMat.normalNode = T3.normalMap(nSample, vec2(ns, ns));
            }
            // ANALYTIC tangent frame — the band is a cylinder around X, so no
            // NormalMapNode/tangent attributes needed (its derivative-TBN
            // fallback emits WGSL that dies whenever shadow-map code is woven
            // into the material — the black-band-in-shadowed-scenes bug):
            //   T = around-ring direction, B = ring axis, N = authored normal
            const landTS = origMat.normalMap ? texture(origMat.normalMap, uvT).rgb : vec3(0.5, 0.5, 1);
            const lightweightWaveTexture = textures.bandNormal ?? origMat.normalMap ?? null;
            const canBuildWaves = waterWaveMode !== 'off'
                && T3.transformNormalToView && T3.positionLocal && T3.normalLocal
                && (waterWaveMode !== 'lightweight' || lightweightWaveTexture);
            if (canBuildWaves) {
                const posL = T3.positionLocal;
                const Tn = T3.normalize(vec3(0, posL.z.negate(), posL.y));
                const Bn = vec3(1, 0, 0);
                const Nn = T3.normalLocal;
                const landV = landTS.mul(2).sub(1);
                const landN = T3.normalize(Tn.mul(landV.x).add(Bn.mul(landV.y)).add(Nn.mul(landV.z)));
                let waveSlope;
                if (waterWaveMode === 'lightweight') {
                    // Two scrolling reads of the existing filtered normal map.
                    // uvT already repeats 8×1; 28×7 and 44×11 preserve the
                    // Ringworld band's ~32:1 physical aspect, so ripples stay
                    // approximately isotropic instead of stretching into lines.
                    lightweightWaveTexture.wrapS = lightweightWaveTexture.wrapT = T3.RepeatWrapping;
                    lightweightWaveTexture.colorSpace = T3.NoColorSpace;
                    const waveClock = tU.mul(opts.lightweightWaveSpeed ?? 0.0065);
                    const waveUv0 = vec2(uvT.x.mul(28), float(1).sub(uvT.y).mul(7))
                        .add(vec2(waveClock, waveClock.mul(0.31)));
                    const waveUv1 = vec2(uvT.x.mul(44), float(1).sub(uvT.y).mul(11))
                        .sub(vec2(waveClock.mul(1.37), waveClock.mul(0.53)))
                        .add(vec2(0.37, 0.61));
                    const wave0 = texture(lightweightWaveTexture, waveUv0).xyz.mul(2).sub(1);
                    const wave1 = texture(lightweightWaveTexture, waveUv1).xyz.mul(2).sub(1);
                    waveSlope = vec2(
                        wave0.x.add(wave1.y.mul(0.52)),
                        wave0.y.sub(wave1.x.mul(0.52)),
                    ).mul(opts.lightweightWaveAmp ?? 0.26)
                        // Mip filtering carries the far field; retain a 42%
                        // floor so night water never loses its moving glint.
                        .mul(mix(float(1), float(0.42), farK))
                        .mul(shimRaw.mul(0.18).add(0.87));
                } else {
                    // Full procedural lookdev field. Kept available explicitly,
                    // but the realtime wrapper does not pay its many hash/FBM
                    // evaluations merely because the GPU happens to be idle.
                    const h2m = (p, rep) => h2(T3.mod(p, rep));
                    const vnT = (p, rep) => {
                        const i = floor(p), f = fract(p);
                        const s = f.mul(f).mul(float(3).sub(f.mul(2)));
                        return mix(mix(h2m(i, rep), h2m(i.add(vec2(1, 0)), rep), s.x),
                            mix(h2m(i.add(vec2(0, 1)), rep), h2m(i.add(vec2(1, 1)), rep), s.x), s.y);
                    };
                    const wSpd = tU.mul(1.2);
                    const rep1 = vec2(32, 1e6), rep2 = vec2(44, 1e6);
                    const q1 = uvB.mul(vec2(12320, 385)), q2 = uvB.mul(vec2(24640, 770));
                    const F = (o) => vnT(q1.add(vec2(wSpd, wSpd.mul(0.35))).add(o), rep1)
                        .add(vnT(q2.sub(vec2(wSpd.mul(1.7), wSpd.mul(0.6))).add(o.mul(2)), rep2).mul(0.5));
                    const eC = 0.5;
                    const h0 = F(vec2(0, 0)), hx = F(vec2(eC, 0)), hy = F(vec2(0, eC));
                    waveSlope = vec2(h0.sub(hx), h0.sub(hy))
                        .mul(opts.waveAmp ?? 0.55)
                        .mul(shimRaw.mul(0.8).add(0.5))
                        .mul(float(1).sub(farK));
                }
                const waveN = T3.normalize(Nn.add(Tn.mul(waveSlope.x)).add(Bn.mul(waveSlope.y)));
                bandMat.normalNode = T3.transformNormalToView(T3.normalize(mix(landN, waveN, k)));
                // NIGHT WATER: normalNode only reaches env/lit shading — the
                // unlit emissive needs its own term. Same tangential rake as
                // the night land: exaggerated ANIMATED wave normals glinting
                // under grazing planet-light, water areas only, faded by day.
                const waveNN = T3.normalize(Nn.add(Tn.mul(waveSlope.x.mul(3.2))).add(Bn.mul(waveSlope.y.mul(3.2))));
                const mTanW = T3.normalize(uMoonDirN.sub(Nn.mul(T3.dot(uMoonDirN, Nn))).add(vec3(0.02, 0, 0.01)));
                const rakeW = T3.clamp(T3.dot(waveNN, mTanW).mul(1.6), float(-1), float(1));
                const rakePositive = T3.clamp(rakeW, float(0), float(1));
                const glintW = rakePositive.pow(2).mul(0.6).add(rakePositive.mul(0.14)).add(float(0.05));
                // seas in a segment whose sky holds no giant get the LOW state:
                // dim water with only a starlight whisper — the shimmer belongs
                // to planet-lit segments alone. Floor raised with the land's:
                // below ~0.3 the whole low state fell under display black and
                // the pVis gradient cut a hard line across the band.
                const shineW = float(0.30).add(A.pVis.mul(0.70));
                const waterNight = vec3(0.30, 0.36, 0.55).mul(glintW).mul(shineW)
                    .mul(k).mul(float(1).sub(A.dayF)).mul(float(1).sub(A.litK)).mul(A.trans).mul(float(0.85));
                bandMat.emissiveNode = bandMat.emissiveNode.add(waterNight);
                waterWavesActive = true;
            } else {
                bandMat.normalMap = origMat.normalMap ?? null; // fallback: no waves
                if (waterWaveMode !== 'off') console.warn('[ringworld] animated water unavailable (missing wave texture or TSL accessors)');
            }
        }
        const debugBandMaterial = opts.debugBand === 'basic';
        terrain.material = debugBandMaterial
            ? new T3.MeshStandardNodeMaterial({ color: 0xff2020, fog: false })  // bisect: geometry/placement vs material graph
            : bandMat;
        if (debugBandMaterial) bandMat.dispose();
        // The GLB source materials have now been replaced on both authored
        // meshes. Their textures remain intentionally alive (and are exposed
        // below), but the unused material objects need no renderer lifetime.
        for (const material of sourceMaterials) material.dispose?.();

        // ---- RING CLOUD LAYER: animated 2D procedural cloud sheet floating
        // above the band ("up" = toward the ring axis, so SMALLER radius).
        // Look is driven by the weather/sky state from update() — coverage per
        // weather name, storm greying, palette tint, wind-matched drift.
        const cloudH = opts.cloudHeight ?? 60;
        const cu = {
            cover: uniform(0.45), grey: uniform(0), dens: uniform(1), rad: uniform(1),
            tintSun: uniform(new T3.Vector3(1, 0.97, 0.9)),
            tintAmb: uniform(new T3.Vector3(0.72, 0.78, 0.9)),
            wind: uniform(new T3.Vector2(0.0035, 0.0008)),
        };
        const cloudGeo = new T3.CylinderGeometry(R_REF - cloudH, R_REF - cloudH, 940, 256, 1, true);
        cloudGeo.rotateZ(Math.PI / 2);  // cylinder axis Y → ring axis X
        // Standard-family, NOT Basic: with shadow maps enabled, a Basic sheet's
        // pipeline compiles to an EMPTY fragment output struct — Dawn tolerates
        // it, Deno's naga rejects it ("Structure types must have at least one
        // member") and the sheet silently dies. Standard is proven under
        // shadows here; the clouds stay visually unlit by routing colour
        // through emissiveNode.
        const cloudMat = new T3.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, side: T3.FrontSide, fog: false, roughness: 1, metalness: 0 });
        {
            // SATELLITE-IMAGERY clouds: the ring is a super-Earth-scale
            // megastructure, so the sheet reads like weather systems seen from
            // orbit — km-scale masses, domain-warped filament detail,
            // isotropic cells (v cells = u cells / 33.4, the band's aspect).
            const cuv = uv();
            const h2c = (pp) => {                     // sin-free hash21 (Hoskins)
                const a = fract(vec3(pp.x, pp.y, pp.x).mul(0.1031));
                const d = T3.dot(a, vec3(a.y, a.z, a.x).add(33.33));
                const b = a.add(d);
                return fract(b.x.add(b.y).mul(b.z));
            };
            const vnc = (pp, rep) => {                // wrap-safe: lattice mod rep
                const i = T3.mod(floor(pp), rep), i1 = T3.mod(floor(pp).add(vec2(1, 0)), rep);
                const i2 = T3.mod(floor(pp).add(vec2(0, 1)), rep), i3 = T3.mod(floor(pp).add(vec2(1, 1)), rep);
                const f = fract(pp);
                const s = f.mul(f).mul(float(3).sub(f.mul(2)));
                return mix(mix(h2c(i), h2c(i1), s.x), mix(h2c(i2), h2c(i3), s.x), s.y);
            };
            const drift = cu.wind.mul(tU);
            // octave sampler: N integer cells around (exact cylinder wrap),
            // isotropic v, wind drift, optional warp offset
            const oct = (N, w, dir, warpOff) => {
                const sc = vec2(N, N / 33.4);
                let pp = cuv.add(drift.mul(dir)).mul(sc);
                if (warpOff) pp = pp.add(warpOff.mul(N * 0.012));
                return vnc(pp, vec2(N, 1e6)).mul(w);
            };
            // macro weather systems (~5 km) + a coarse vec2 warp field that
            // swirls the filament octaves (the satellite-swirl look)
            const sysM = oct(6, 1, 1);
            const wX = oct(10, 1, 0.6).sub(0.5), wY = oct(10, 1, -0.7).sub(0.5);
            const warp = vec2(wX, wY);
            const fil = oct(40, 0.38, 1, warp).add(oct(80, 0.26, -0.8, warp))
                .add(oct(160, 0.19, 1.3, warp)).add(oct(320, 0.12, -1.1, warp))
                .add(oct(640, 0.07, 0.9, warp));
            const field = sysM.mul(0.62).add(fil.mul(0.55));   // macro systems lead — READABLE cloud masses
            // threshold rides coverage so low-cover states leave most of the
            // band clear (distinct systems), high-cover states close over.
            // Field distribution: mean ~0.59, realistic max ~0.94.
            const th = float(0.88).sub(cu.cover.mul(0.55));
            const cov = smoothstep(th, th.add(0.15), field);   // tight window: defined masses, not gauze
            // soft edges at the strip borders so clouds never touch the walls
            const edge = smoothstep(0.02, 0.15, cuv.y).mul(smoothstep(0.98, 0.85, cuv.y));
            const bright = mix(cu.tintSun, cu.tintAmb, smoothstep(0.2, 0.9, field)); // dense cores shade toward ambient
            cloudMat.colorNode = vec3(0);   // no lit response — self-coloured via emissive
            // ring clouds follow the ARC's day/night + air: night-side systems
            // dim toward moon-grey, and the whole sheet is seen through the
            // local atmosphere like the band beneath it
            const Ac = arcShade();
            // cu.rad is the sky's own cloudRadiance — the same readability
            // multiplier the volumetric march is dimmed by (clear 1.0,
            // overcast 0.45, storm 0.18, cyclone 0.10). Using it instead of a
            // local grey approximation is what makes the far sheet read as the
            // SAME weather as the deck overhead rather than a bright sheet
            // pasted behind a dark storm.
            cloudMat.emissiveNode = bright.mul(cu.rad)
                .mul(float(0.22).add(Ac.litK.mul(0.78)))
                .mul(Ac.trans).mul(Ac.expK)
                .add(Ac.insc.mul(float(0.35)));
            // NEAR FADE: the sheet's local section would clip through the scene
            // floor (it passes ~ground level near the viewer) — and clouds HERE
            // are the local weather, already carried by the volumetric deck.
            // The sheet only dresses the FAR side.
            const sheetDist = T3.length(T3.positionWorld.sub(T3.cameraPosition));
            // cu.dens carries the volumetric field's own density (finalMul), so
            // a thin overcast sheet and a dense cyclone deck read differently
            // here rather than at one fixed opacity.
            cloudMat.opacityNode = cov.mul(edge)
                .mul(smoothstep(float(3500), float(7000), sheetDist))
                .mul(float(0.85).sub(cu.grey.mul(0.12)))
                .mul(cu.dens).clamp(0, 1);
        }
        // No G-buffer wrap needed: the engine's pass MRT weights aux
        // attachments by material alpha, so this sheet's invisible near
        // section (opacity 0) contributes nothing. Its geometry lies tangent
        // to y=0 at the local origin — with alpha-1 padding it would silently
        // ERASE the metalness of any scene floor beneath it.
        // opts.ringClouds = false (or RINGNOCLOUD=1) drops the sheet. It exists
        // because the shared sky cloud field is a CAMERA-CENTERED dome and so
        // cannot reach the far arc kilometres away or the overhead crossing —
        // those are the sheet's whole job. The near fade above keeps it out of
        // the local scene, where the volumetric deck is the right owner.
        let ringClouds = null;
        if (opts.ringClouds !== false && _envRG('RINGNOCLOUD') !== '1') {
            const cloudMatBack = cloudMat.clone();
            cloudMatBack.side = T3.BackSide;
            ringClouds = new T3.Group();
            ringClouds.name = 'ring_clouds';
            for (const m of [new T3.Mesh(cloudGeo, cloudMat), new T3.Mesh(cloudGeo, cloudMatBack)]) {
                m.userData.noSupportCheck = true; m.userData.noWet = true;
                ringClouds.add(m);
            }
            ringClouds.userData.noSupportCheck = true; ringClouds.userData.noWet = true;
        }

        // ---- FOG BOUNDARY (engine-owned): a soft palette-colored haze wall
        // ringing the local scene so ANY consumer's arbitrary terrain blends
        // into the distant band instead of cutting against it. Opaque-ish at
        // horizon level, dissolving upward; local opaques occlude it by depth.
        let fogWall = null;
        // RINGFOGWALL=0 / RINGRAINWALL=0 — bisect the two horizon walls
        if (opts.fogWall !== false && _envRG('RINGFOGWALL') !== '0') {
            const fwR = opts.fogWallRadius ?? 1250;
            const fogGeo = new T3.CylinderGeometry(fwR, fwR, 90, 96, 1, true);
            const fogMat = new T3.MeshStandardNodeMaterial({
                transparent: true, depthWrite: false, side: T3.BackSide,
                fog: false, roughness: 1, metalness: 0,
            });
            fogMat.colorNode = vec3(0);
            fogMat.emissiveNode = uHazeCol;
            fogMat.opacityNode = smoothstep(float(0.62), float(0.16), uv().y).mul(float(0.78));   // a low haze band, not a wall of soup
            fogWall = new T3.Mesh(fogGeo, fogMat);
            fogWall.name = 'ring_fog_boundary';
            fogWall.userData.noSupportCheck = true; fogWall.userData.noWet = true;
            fogWall.userData.allowIntersect = true;
        }
        // ---- RAIN WALL (Skye's design): the horizon fade band already has
        // the depth read — DUPLICATE it, lighten it, stretch it up to the
        // cloud base, and sit it slightly behind the boundary wall. It
        // carries the rain murk 360° around the local area (the arc veil
        // only covers the halo directions); opacity rides the blended rain
        // gate, so it simply isn't there outside real rain.
        let rainWall = null;
        if (opts.fogWall !== false && _envRG('RINGRAINWALL') !== '0') {
            const rwR = (opts.fogWallRadius ?? 1250) + 130;
            const rainGeoW = new T3.CylinderGeometry(rwR, rwR, 730, 96, 1, true);
            const rainMatW = new T3.MeshStandardNodeMaterial({
                transparent: true, depthWrite: false, side: T3.BackSide,
                fog: false, roughness: 1, metalness: 0,
            });
            rainMatW.colorNode = vec3(0);
            // Lighter than the haze band, but PROPORTIONALLY. Mixing toward
            // absolute white pinned this curtain at a 0.22 floor regardless of
            // conditions: fine in daylight where the haze is bright, but under
            // a darkstorm sky (~0.02) it read as a hard WHITE STRIP along the
            // horizon, brighter than the storm it was supposedly made of.
            // Scaling keeps the same "a touch brighter than haze" intent and
            // follows the sky all the way down to night.
            rainMatW.emissiveNode = uHazeCol.mul(1.28);
            rainMatW.opacityNode = smoothstep(float(0.9), float(0.12), uv().y)
                .mul(float(0.7)).mul(uRainHazeN);
            rainWall = new T3.Mesh(rainGeoW, rainMatW);
            rainWall.name = 'ring_rain_wall';
            rainWall.userData.noSupportCheck = true; rainWall.userData.noWet = true;
            rainWall.userData.allowIntersect = true; rainWall.userData.noFacingCheck = true;
        }

        // ---- assemble (keep ONLY the two known meshes — stray helper objects
        // like Blender's default cube ship in the GLB) ----
        const group = new T3.Group();
        group.name = 'ringworld';
        for (const m of [terrain, walls]) {
            m.userData.noSupportCheck = true; m.userData.noWet = true;
            group.add(m);
        }
        // the export frames the ring lifted into the sky (mesh translation) —
        // recenter on the ring axis so scenes place it explicitly via the
        // group; the local wall-UV math (atan2 in geometry space) is unaffected
        const ctr = new T3.Box3().setFromObject(group).getCenter(new T3.Vector3());
        for (const m of [terrain, walls]) m.position.sub(ctr);
        if (fogWall) {
            // group sits at the ring center (~y 4940); the wall belongs at the
            // WORLD origin around the local scene: [-30..140] m of soft haze
            fogWall.position.set(0, -4915, 0);   // world span ≈ [-70..+20] m — hugs the horizon line
            group.add(fogWall);
        }
        if (rainWall) {
            rainWall.position.set(0, -4620, 0);   // same convention: world span ≈ [-45..+685] m — foot at ground, head at the cloud base
            group.add(rainWall);
        }

        group.add(ringClouds);   // built origin-centered — no recenter needed

        const sys = {
            group, band: terrain, walls, clouds: ringClouds, cloudUniforms: cu,
            arcLight: sysArcLight,
            bindWeather(weather, sky) { sys._wx = weather; sys._sky = sky; },
            update(t) {
                tU.value = t;
                const wx = sys._wx, sk = sys._sky;
                // arc lighting self-drives: center from the group's world pose
                // (once), the terminator from the bound sky's TRUE sun vector —
                // consumers wire nothing per frame (engine behavior, not scene)
                if (sysArcLight) {
                    if (!sysArcLight._centered) {
                        group.getWorldPosition(sysArcLight.center.value);
                        sysArcLight._centered = true;
                    }
                    if (sk?.sunDir) {
                        sysArcLight.sunDir.value.copy(sk.sunDir).normalize();
                        sysArcLight.sunElev.value = sk.sunDir.y;
                    }
                    if (sk?.moonDir) sysArcLight.moonDir.value.copy(sk.moonDir).normalize();
                    // haze + sun color follow the LOCAL palette — the arc's
                    // radiance tracks the same sun that lights the ground
                    const pal = sk?.state?.palette;
                    // HAZE COLOUR MUST COME FROM THE WEATHERED SKY, not the raw
                    // time-of-day palette. state.palette is the clean TOD
                    // colour; the weather system greys and darkens the actual
                    // sky (darkstorm: grey 0.97, dark 0.14, horMul 0.22) by
                    // writing sky.uniforms.horizon. Reading pal.hor instead
                    // left the haze band at a BRIGHT DAYTIME horizon under a
                    // near-black storm — a white strip along the horizon, with
                    // the world rain curtains (which mix toward white on top of
                    // it) brighter still. Fall back to pal.hor only if the
                    // uniform is missing.
                    const hz = sk?.uniforms?.horizon?.value;
                    if (hz) sysArcLight.hazeCol.value.setRGB(hz.x ?? hz.r, hz.y ?? hz.g, hz.z ?? hz.b);
                    else if (pal?.hor) sysArcLight.hazeCol.value.setRGB(pal.hor[0], pal.hor[1], pal.hor[2]);
                    if (pal?.sun) sysArcLight.sunCol.value.setRGB(pal.sun[0], pal.sun[1], pal.sun[2]).lerp(new T3.Color(1, 1, 1), 0.35);
                }
                if (wx && wx.state && wx.state.def) {
                    cu.grey.value = (wx.state.def.grey ?? 0) * (wx.state.k ?? 1);
                    // sub-cloud rain veil: gated ABOVE the light states —
                    // sunshower (rain 0.45) gets NONE, rain (0.7) a moderate
                    // wash, storms (0.9-1.0) the full murk
                    const rk = (wx.state.def.rain ?? 0) * (wx.state.k ?? 1);
                    const rg = Math.min(1, Math.max(0, (rk - 0.45) / 0.5));
                    uRainHazeN.value = rg * rg * (3 - 2 * rg);
                }
                // MATCH THE LOCAL VOLUMETRICS. Coverage, density and colour all
                // come from the very uniforms the volumetric march reads, not
                // from a parallel per-state table here — a second table drifts
                // from the clouds it is supposed to match the moment either
                // side is retuned, and it cannot follow a weather transition
                // that the sky is already lerping.
                //   largeT  = coverage THRESHOLD (lower = more sky covered)
                //   finalMul= field density
                //   cloudLightColor / cloudAmbSky = the clouds' own lit/fill
                //     colours, so paletteTint worlds (the red giant) match too
                if (sk?.uniforms) {
                    const U = sk.uniforms;
                    if (U.largeT) {
                        cu.cover.value = Math.max(0, Math.min(1, 1 - U.largeT.value));
                    }
                    if (U.finalMul) {
                        // 0.24 is the fair-weather reference density
                        cu.dens.value = Math.max(0.55, Math.min(1.5, U.finalMul.value / 0.24));
                    }
                    // cloudLightColor is HDR-calibrated (sunBase * pal.int * 7);
                    // /7 puts it back on the palette scale this sheet's own
                    // exposure term expects.
                    if (U.cloudLightColor) {
                        cu.tintSun.value.copy(U.cloudLightColor.value).multiplyScalar(0.42 / 7);
                    }
                    if (U.cloudAmbSky) cu.tintAmb.value.copy(U.cloudAmbSky.value);
                    if (U.cloudRadiance) cu.rad.value = U.cloudRadiance.value;
                }
                if (sk && sk.state && sk.state.palette) {
                    if (sk.uniforms.skyWind) {
                        const w = sk.uniforms.skyWind.value;
                        // TRUE-scale drift: the far side is km away, so its
                        // clouds must crawl SLOWER than the local raymarch
                        // deck, never faster.
                        cu.wind.value.set(w.x / 31400 * 1.2, w.z / 31400 * 0.5);
                    }
                }
            },
            info: {
                radius: R_REF,
                tile,
                halfWidth: 483,
                repeat: origMat.map?.repeat?.x ?? 8,
                mapTex: origMat.map,
                maskTex: textures.landmask,
                waterWaveMode,
                waterWavesActive,
                sourceTextures: [...sourceTextures],
            },
            // 0 = light fully eclipsed by the band, 1 = clear. Analytic ray vs
            // the ring cylinder from the stage origin toward the light — the
            // classic ringworld sun-eclipse ("arch night"), soft penumbra.
            eclipseK(dir, originY = 0) {
                const oy = originY - group.position.y;
                const a = dir.y * dir.y + dir.z * dir.z;
                if (a < 1e-9) return 1;
                const b = 2 * oy * dir.y, c = oy * oy - R_REF * R_REF;
                const disc = b * b - 4 * a * c;
                if (disc <= 0) return 1;
                const t = (-b + Math.sqrt(disc)) / (2 * a);
                if (t <= 0) return 1;
                const hx = dir.x * t - group.position.x;
                const pen = 70;
                return Math.min(1, Math.max(0, (Math.abs(hx) - (483 - pen)) / (2 * pen)));
            },
        };
        return sys;
    };
    console.log('[ringworld] makeRingworld ready (v2 split GLB)');
})();
