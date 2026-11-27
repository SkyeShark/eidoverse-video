// eidoverse/sets/wake_another_one/hall/world.js — the hall's light and outdoors in three.js: the look's light plan
// (look.js) as three.js lights, the sky family's sky through the dock door with its sun on the dock sun, the yard's
// CC0 fence and fittings by ID, SeedThree's trees, the hall's own reflections, and its air.
//
// THE LAMPS. A Blender area light of power P (W) over w x h is a RectAreaLight of P / (pi w h) (the SAME SEED rooms'
// rule). Every strip row is continuous light: the Blender look's segments, none casting a shadow (as there), each
// ending at the reach EEVEE gives it (its custom distance, as three's point lights end theirs, from its centre).
// Blender's split over the hero aisle (diffuse from a baked volume probe, highlights from the lamps) has no volume
// probe here: the lamps light diffuse and specular everywhere, the hall's bounce comes from a capture of the hall
// itself (a cube from the hero line's reflection probe's place, as its reflections and its diffuse fill), and the
// renderer's own N8AO and SSR do the contact shade and the floor's mirror.
// THE SUN is the dock's: 13 W/m2 at 3000 K balanced to the lamps, its shadow over the door and the yard; it is held
// to the door's corridor and the outdoors (outside its map's reach the hall's roof would let it through).
// THE OUTDOORS is the sky family's Earth sky (eidoverse/sky_worlds.js makeSky, clear) at the hour that stands its sun
// 17.82 degrees up; the hall's root turns about the vertical so the dock's sun meets the sky's (the town's way). The
// lens sees it whole through the door; it lights at sky_fill (0.06), as the Blender look's make_sky ambient.
import { M4 } from './graph.js';
import { balanced, blackbody, LAMP_K, SUN_K } from './look.js';
import { TREES } from './shell.js';
import { skyHours } from '../../town/world.js';

// the look's options (build()'s keywords): the Blender look's (strip W/m of row, far_lamp, bounce, sun W/m2, sky_fill,
// haze per metre, drum_lamp W, exposure stops) and this edition's own: reflect, dielectric and fill, the hall's
// captured environment as reflections (paint and plastic at `dielectric` of them) and as diffuse fill (set against
// the Blender stills, see the guide)
export const OPT = { strip: 36.0, far_lamp: 0.6, bounce: 1.0, sun: 13.0, sky_fill: 0.06, haze: 0.0012, drum_lamp: 0.35, exposure: 0.0, reflect: 1.0, dielectric: 0.35, fill: 0.1 };

const parseGLB = (bytes, base = '') => {
    const loader = new globalThis.GLTFLoader();
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return new Promise((res, rej) => loader.parse(buf, base, res, rej));
};

// a glTF material as a node material with the same maps (the SAME SEED rooms' nodeify)
export function nodeify(T, m) {
    if (!m || m.isNodeMaterial) return m;
    const n = m.isMeshPhysicalMaterial ? new T.MeshPhysicalNodeMaterial() : new T.MeshStandardNodeMaterial();
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'alphaMap']) if (m[k]) n[k] = m[k];
    for (const k of ['color', 'emissive']) if (m[k] && n[k]) n[k].copy(m[k]);
    for (const k of ['roughness', 'metalness', 'emissiveIntensity', 'aoMapIntensity', 'opacity', 'alphaTest']) if (typeof m[k] === 'number') n[k] = m[k];
    if (m.normalScale) n.normalScale.copy(m.normalScale);
    n.transparent = m.transparent; n.side = m.side; n.name = m.name;
    return n;
}

export async function makeLights(THREE, X, lay, group, opt) {
    const T = THREE;
    const { RectAreaLightTexturesLib } = await import('npm:three@0.184.0/addons/lights/RectAreaLightTexturesLib.js');
    T.RectAreaLightNode.setLTC(RectAreaLightTexturesLib.init());
    const LAMP = balanced(LAMP_K), SUN = balanced(SUN_K);
    const out = { strips: [], all: [] };
    // EEVEE's reach (its custom distance), as three's point lights end theirs: (1 - (d / r)^4)^2 from the centre
    const reach = (L, r) => {
        const tc = new T.Color(), tp = new T.Vector3();
        const c = T.uniform(new T.Color()).onRenderUpdate(() => tc.copy(L.color).multiplyScalar(L.intensity));
        const at = T.uniform(new T.Vector3()).onRenderUpdate(() => L.getWorldPosition(tp));
        const w = T.float(1.0).sub(T.positionWorld.sub(at).length().div(r).pow(4.0)).clamp(0.0, 1.0);
        L.colorNode = c.mul(w.mul(w));
    };
    for (const l of X.lights) {
        if (l.type === 'strip') {
            const P = opt.strip * l.size[1] * (l.far ? opt.far_lamp : 1.0);
            const L = new T.RectAreaLight(new T.Color(...LAMP), P / (Math.PI * l.size[0] * l.size[1]), l.size[0], l.size[1]);
            L.position.set(...l.pos);
            L.name = l.name;
            L.userData.specularOnly = !!l.hero;                              // (Blender: diffuse_factor 0 over the aisle probe)
            reach(L, l.reach);
            group.add(L);
            out.strips.push(L); out.all.push(L);
        } else if (l.type === 'bounce') {
            // what the floor throws back up at the roof: ONE wide lamp at 6 m that looks up (it lights nothing below it)
            const P = opt.bounce * 0.5 * l.size[0] * l.size[1];
            const L = new T.RectAreaLight(new T.Color(0.97, 0.98, 1.0), P / (Math.PI * l.size[0] * l.size[1]), l.size[0], l.size[1]);
            L.position.set(...l.pos);
            L.rotation.set(Math.PI, 0, 0);
            L.name = l.name;
            L.userData.diffuseOnly = true;                                  // (Blender: specular_factor 0)
            group.add(L);
            out.bounce = L; out.all.push(L);
        } else if (l.type === 'area') {
            const P = l.opt ? opt[l.opt] : l.power;
            const L = new T.RectAreaLight(new T.Color(...LAMP), P / (Math.PI * l.size[0] * l.size[1]), l.size[0], l.size[1]);
            L.position.set(...l.pos);
            L.rotation.set(...l.rot);
            L.name = l.name;
            if (l.reach) reach(L, l.reach);
            group.add(L);
            out.all.push(L);
        } else if (l.type === 'sun') {
            const L = new T.DirectionalLight(new T.Color(...SUN), opt.sun);
            L.name = l.name;
            out.sun = L; out.sunDir = l.dir;
            out.all.push(L);
        }
    }
    return out;
}

// the sun: a DirectionalLight whose map covers the door, its corridor into the hall and the yard by the door; held to
// the corridor and the outdoors (a colour node: 0 inside the hall's walls south of the corridor's end)
export function placeSun(THREE, sun, group, lay, { size = 4096, shadows = true } = {}) {
    const T = THREE;
    group.updateMatrixWorld(true);
    const m = new T.Matrix4().fromArray(group.matrixWorld.elements);
    const d = new T.Vector3(...lay.SUN_DIR).transformDirection(m).normalize();       // the way its light travels, in the world
    const c = new T.Vector3(-6.0, 26.0, 2.0).applyMatrix4(m);                          // the door, its corridor and the near yard
    sun.target.position.copy(c);
    sun.position.copy(c).addScaledVector(d, -120.0);
    sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
    if (shadows) {
        sun.castShadow = true;
        sun.shadow.mapSize.set(size, size);
        const e = 34.0;
        Object.assign(sun.shadow.camera, { left: -e, right: e, top: e, bottom: -e, near: 1.0, far: 260.0 });
        sun.shadow.camera.updateProjectionMatrix();
        sun.shadow.bias = -0.0003;
        sun.shadow.normalBias = 0.02;
        sun.shadow.radius = 2.0;
        sun.shadow.camera.layers.enable(1);                                            // (the hall's outer mass: shadow only)
    }
    // inside the hall, the sun reaches no further than its patch's corridor (y > 6 m): the map does not cover the rest
    const inv = T.uniform(new T.Matrix4().copy(m).invert());
    const p = inv.mul(T.vec4(T.positionWorld, 1.0)).xyz;
    const inside = T.step(lay.HX0 - 0.5, p.x).mul(T.step(p.x, lay.HX1 + 0.5)).mul(T.step(lay.HY0 - 0.5, p.y)).mul(T.step(p.y, lay.HY1 + 0.2)).mul(T.step(p.z, lay.L.hall.roof_z + 0.5));
    const keep = T.float(1.0).sub(inside.mul(T.float(1.0).sub(T.smoothstep(5.0, 6.0, p.y))));
    const col = new T.Color(), tc = T.uniform(new T.Color()).onRenderUpdate(() => col.copy(sun.color).multiplyScalar(sun.intensity));
    sun.colorNode = tc.mul(keep);
    sun.userData.frame = inv;
}

// the sky family's sky with its sun on the dock sun: the hall's root turned about the vertical to meet it
export async function sky(THREE, { scene, camera, renderer, group, lay, opt, log }) {
    const T = THREE;
    if (!globalThis.makeSky) eval(Deno.readTextFileSync(new URL('../../../sky_worlds.js', import.meta.url)));
    const toSun = lay.SUN_DIR.map((v) => -v);
    const el = Math.asin(toSun[2]) * 180 / Math.PI;
    const hours = skyHours(el);
    const skySun = new T.DirectionalLight(0xffffff, 1.0), skyHemi = new T.HemisphereLight(0xffffff, 0x000000, 0.0);   // (the sky keys them; the hall's sun is its own)
    const S = await globalThis.makeSky({ scene, camera, renderer, sun: skySun, hemi: skyHemi, world: 'earth', hours, clouds: 'clear', weather: 'clear', audio: false });
    S.setTime(hours);
    S.update(0);
    const sd = S.sunDir;
    const tw = new T.Vector3(toSun[0], toSun[2], -toSun[1]);
    const turn = Math.atan2(tw.z, tw.x) - Math.atan2(sd.z, sd.x);
    group.rotation.set(-Math.PI / 2, 0, 0);
    group.rotateOnWorldAxis(new T.Vector3(0, 1, 0), turn);
    group.updateMatrixWorld(true);
    log(`[hall] the sky family: hour ${hours.toFixed(3)} (its sun ${el.toFixed(2)} degrees up); the hall turned ${(turn * 180 / Math.PI).toFixed(1)} degrees to meet it`);
    await S.bakeEnv();
    scene.environmentIntensity = opt.sky_fill;
    return { S, hours, turn, skySun, skyHemi };
}

// the CC0 models by ID (Poly Haven, fetched once into the shared library), each placed as the Blender look fits them
export async function models(THREE, X, group, { log }) {
    const T = THREE;
    const cache = new Map();
    const load = async (id) => {
        if (!cache.has(id)) {
            const file = await globalThis.fetchModelFile(id, { res: '2k' });
            cache.set(id, await parseGLB(Deno.readFileSync(file), file.replace(/[\\/][^\\/]*$/, '/')));
        }
        return cache.get(id);
    };
    const mats = new Map();
    const conv = (m) => {
        if (!mats.has(m)) mats.set(m, nodeify(T, m));
        return mats.get(m);
    };
    for (const { asset, loc, rz } of X.models) {
        const gltf = await load(asset);
        const root = new T.Group();
        root.name = `fit_${asset}`;
        root.position.set(...loc);
        root.rotation.set(0, 0, rz);
        const yup = gltf.scene.clone(true);                              // (glTF is +Y up: stood up in the hall's +Z)
        yup.rotation.x = Math.PI / 2;
        yup.traverse((o) => {
            if (!o.isMesh) return;
            o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
            o.castShadow = true; o.receiveShadow = true;
        });
        root.add(yup);
        group.add(root);
    }
    // the fence: the kit's double panel instanced along the kerb, its wire thinned to what the gauge covers (dithered)
    let fence = null;
    if (X.fence) {
        const gltf = await load(X.fence.asset);
        let panel = null;                                              // (the kit's node; its two materials make it a group)
        gltf.scene.traverse((o) => { if (!panel && o.name === X.fence.mesh) panel = o; });
        if (panel) {
            const parts = [];
            gltf.scene.updateMatrixWorld(true);
            panel.traverse((o) => { if (o.isMesh) parts.push(o); });
            const yUp = new T.Matrix4().makeRotationX(Math.PI / 2);
            for (const o of parts) {
                const mat = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => {
                    const n = nodeify(T, m);
                    if (/wire/i.test(m.name)) {
                        // the link's cover thinned to what wire of that gauge covers at 40 m (x 0.32): Blender dithers
                        // it over its samples; one sample a pixel blends it
                        n.alphaTest = 0.0; n.transparent = true; n.depthWrite = false;
                        n.opacityNode = (m.alphaMap ? T.texture(m.alphaMap).g : (m.map ? T.texture(m.map).a : T.float(1.0))).mul(0.32);
                    }
                    n.side = T.DoubleSide;
                    return n;
                });
                const im = new T.InstancedMesh(o.geometry, mat.length === 1 ? mat[0] : mat, X.fence.pts.length);
                // (the panel's own placing dropped, as the Blender instancer's ORIGINAL space drops it; a part under it
                // keeps its place in the panel)
                const local = o === panel ? new T.Matrix4() : o.matrixWorld.clone().premultiply(panel.matrixWorld.clone().invert());
                const mm = new T.Matrix4();
                X.fence.pts.forEach((p, i) => {
                    mm.makeTranslation(p[0], p[1], p[2]).multiply(yUp).multiply(local);
                    im.setMatrixAt(i, mm);
                });
                im.instanceMatrix.needsUpdate = true;
                im.computeBoundingSphere();
                im.castShadow = true; im.receiveShadow = true;
                im.name = 'yard_fence';
                group.add(im);
                fence = im;
            }
        } else log('[hall] the fence kit has no double panel: no fence');
    }
    log(`[hall] CC0 models: ${X.models.map((m) => m.asset).join(', ')}${fence ? `, a fence of ${X.fence.pts.length} panels` : ''}`);
    return { cache, materials: mats, fence };
}

// SeedThree's trees: the five individuals the Blender edition grows (species, seed, height), each copy placed as its
// numpy draws placed it (shell.TREE_PLACES); wind as the Blender look sets it. Their full-detail level (LOD0: the
// yard's trees stand 60 to 120 m from the lenses, where SeedThree's own LOD would hand over its thinned crowns), and
// they cast the sun's shadow, as Blender's do: on the trailers and the yard, and into their own crowns (a crown lit
// through and through glows evenly, like frosted glass; the Blender look gives its trees a probe of their own for it)
export async function trees(THREE, X, group, { sun = null, log, sunStrength = 13.0 } = {}) {
    const T = THREE;
    if (!X.trees.length) return null;
    if (!globalThis.makeSeedTree) { log('[hall] trees: makeSeedTree is not loaded: the yard has none'); return null; }
    const grown = [];
    // the leaves' back-lit glow (SeedThree's SSS: a term in proportion to each light, set for its own sun of 3.0)
    // brought to that sun's measure under the dock's 13; and their cut-out at 0.15 of the leaf's alpha, not 0.4 (60 to
    // 120 m off, a leaf's mipmapped alpha falls under 0.4 and the crown thins to its twigs, where Blender's samples
    // add the leaves' partial cover up): on these trees' materials only, SeedThree untouched
    const k = 3.0 / sunStrength, scaled = new Set();
    for (const [species, seed, height] of TREES) {
        const t0 = performance.now();
        const t = await globalThis.makeSeedTree({ species, seed, controls: { height }, level: 'LOD0', sunLight: sun || undefined });
        t.object.traverse((o) => {
            if (!o.isMesh) return;
            for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
                if (!m || scaled.has(m)) continue;
                if (m.thicknessColorNode) m.thicknessColorNode = m.thicknessColorNode.mul(k);
                if (m.alphaTest > 0.15) { m.alphaTest = 0.15; m.needsUpdate = true; }
                scaled.add(m);
            }
        });
        grown.push(t);
        const s = t.stats?.summary || {};
        log(`[hall]    tree ${species} seed ${seed}: ${JSON.stringify({ heightMeters: s.heightMeters, widthMeters: s.widthMeters, lod0Triangles: s.lod0Triangles })} in ${((performance.now() - t0) / 1000).toFixed(1)} s`);
    }
    try { await globalThis.makeSeedTree.setWind({ strength: 0.35, speed: 0.9 }); } catch { /* (a build without wind) */ }
    const root = new T.Group();
    root.name = 'yard_trees';
    for (const [i, x, y, rot, s] of X.trees) {
        const holder = new T.Group();
        holder.position.set(x, y, 0.0);
        holder.rotation.set(0, 0, rot);
        holder.scale.setScalar(s);
        const up = grown[i].object.clone(true);
        up.rotation.x = Math.PI / 2;                                    // (three's +Y up stood up in the hall's +Z)
        holder.add(up);
        root.add(holder);
    }
    root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    group.add(root);
    log(`[hall] trees: ${X.trees.length} placed (the five individuals copied)`);
    return { root, grown };
}

// THE LIGHT THE BLENDER LOOK BAKES, as an environment for the hall's materials (interiorEnv's lighting(), set as
// their setupEnvironment, the SAME SEED rooms' way). Three things stand in for its probes:
//   the capture   the hall seen from its hero line's mirror probe's place (Blender's refl_line), prefiltered
//                 (PMREMGenerator.fromScene): the reflections indoors at `reflect` (paint and plastic at `dielectric`
//                 of it, metal whole), its diffuse light the fill everywhere indoors at `fill`. capture() renders it
//                 twice into a work target and copies each pass into the one target the materials sample (a pass
//                 never samples what it writes, the second sees the first's light, and the materials' bindings never
//                 change: a texture swapped in mid-frame reaches a shared bind group only at the next frame on this
//                 stack). Run it inside the frame loop: drawn during setup, a scene comes out black here
//   the aisle     the hero aisle's fine volume probe (hall_probe_aisle, baked from the hero rows, whose lamps give
//                 highlights only there): light from every side at once, so a carton's front takes nearly what the
//                 floor takes. Here it is the probe's low-order light, E(n) = A + B n.z in the hall's frame, the
//                 lamps' colour warmed by the cartons' bounce, over the probe's box and faded over a metre at its
//                 walls; A and B set against the Blender stills
//   outdoors      past the hall's walls: the sky's own environment at sky_fill and OUTDOOR (below)
export const AISLE = { A: 1.0, B: 0.45, tint: [1.0, 0.975, 0.93] };

// a material that honours the lamps' Blender factors: a lamp flagged userData.specularOnly gives no diffuse light
// (diffuse_factor 0), one flagged userData.diffuseOnly no highlight (specular_factor 0); the lighting model otherwise
// three's own
export function specularOnlyAware(THREE, m) {
    if (!m || !m.setupLightingModel || m.userData.hallLamps) return m;
    const orig = m.setupLightingModel.bind(m);
    m.setupLightingModel = function (builder) {
        const lm = orig(builder);
        if (!lm || !lm.directRectArea) return lm;
        const base = lm.directRectArea.bind(lm);
        lm.directRectArea = (p, b) => {
            const u = p.lightNode?.light?.userData || {};
            if (!u.specularOnly && !u.diffuseOnly) return base(p, b);
            const rl = p.reflectedLight, none = () => THREE.vec3().toVar();
            return base({ ...p, reflectedLight: { directSpecular: u.diffuseOnly ? none() : rl.directSpecular, directDiffuse: u.specularOnly ? none() : rl.directDiffuse,
                indirectDiffuse: rl.indirectDiffuse, indirectSpecular: rl.indirectSpecular } }, b);
        };
        return lm;
    };
    m.userData.hallLamps = true;
    return m;
}

// OUTDOORS (outside the hall's walls: the yard, the apron, the trailers) the materials take the sky's own environment
// at sky_fill, as Blender's world lights the yard, and the light EEVEE traces on screen there from the sunlit ground,
// trailers and walls around: an even irradiance of `A` W/m2 in the sun's colour (the Blender dock still's shade on the
// apron and a trailer's shaded end: about a third of the sun's irradiance on the ground)
export const OUTDOOR = { A: 1.1 };

export function interiorEnv(THREE, group, renderer, { size = 256, at = [2.2, 4.0, 1.7], fill = 1.0, reflect = 1.0, dielectric = 0.35, aisle = null, lamp = [1, 1, 1],
    hall = null, sky = null, skyFill = 0.06, sunColour = null } = {}) {
    const T = THREE;
    const { positionViewDirection, normalView, normalWorld, cameraViewMatrix, roughness, clearcoatRoughness, clearcoatNormalView, pow, float, metalness, mix, vec3, vec4, smoothstep, step } = T;
    // the hall's frame from three's world (the root may turn to meet the sky)
    const inv = new T.Matrix4();
    const hallInv = T.uniform(new T.Matrix4()).onRenderUpdate(() => inv.copy(group.matrixWorld).invert());
    const P = () => hallInv.mul(vec4(T.positionWorld, 1.0)).xyz;
    const Nh = () => hallInv.mul(vec4(normalWorld, 0.0)).xyz.normalize();
    const box = (v, lo, hi, f = 1.0) => smoothstep(lo - f, lo, v).mul(smoothstep(hi + f, hi, v));
    const probeTerm = () => {
        if (!aisle) return null;
        const p = P(), n = Nh();
        const k = box(p.x, aisle.lo[0], aisle.hi[0]).mul(box(p.y, aisle.lo[1], aisle.hi[1])).mul(box(p.z, aisle.lo[2] - 2.0, aisle.hi[2]));
        const col = vec3(...lamp.map((c, i) => c * AISLE.tint[i]));
        return col.mul(float(AISLE.A).add(n.z.mul(AISLE.B))).mul(k).mul(uAisle);
    };
    const uAisle = T.uniform(1.0);
    // 1 inside the hall's walls, 0 outdoors (faded over half a metre at the walls)
    const insideOf = () => {
        if (!hall) return null;
        const p = P();
        return box(p.x, hall.lo[0], hall.hi[0], 0.5).mul(box(p.y, hall.lo[1], hall.hi[1], 0.5)).mul(step(p.z, hall.hi[2]));
    };
    const pm = new T.PMREMGenerator(renderer);
    const target = pm.fromScene(new T.Scene(), 0, 0.05, 600, { size });   // (what the materials sample: black, until captured)
    let work = null;
    // dielectric: the share of the capture a paint or a plastic reflects (EEVEE's probe reflections lie dimmer on them
    // than a plain prefiltered capture does; metals keep it whole): set against the Blender stills
    const uFill = T.uniform(fill), uReflect = T.uniform(reflect), uDiel = T.uniform(dielectric);
    const dirOf = (rough, nView) => pow(rough, 4).mix(positionViewDirection.negate().reflect(nView), nView).normalize().transformDirection(cameraViewMatrix);
    const tex0 = target.texture;
    const nodes = {
        irradiance: T.pmremTexture(tex0, normalWorld, float(1.0)),
        radiance: T.pmremTexture(tex0, dirOf(roughness, normalView), roughness),
        coat: T.pmremTexture(tex0, dirOf(clearcoatRoughness, clearcoatNormalView), clearcoatRoughness),
    };
    const uSky = T.uniform(skyFill);
    const outdoor = sky ? {
        irradiance: T.pmremTexture(sky, normalWorld, float(1.0)),
        radiance: T.pmremTexture(sky, dirOf(roughness, normalView), roughness),
        coat: T.pmremTexture(sky, dirOf(clearcoatRoughness, clearcoatNormalView), clearcoatRoughness),
    } : null;
    class HallEnvironmentNode extends T.LightingNode {
        static get type() { return 'HallEnvironmentNode'; }
        setup(builder) {
            const k = insideOf();
            const pick = (a, b) => (k && b ? mix(b, a, k) : a);       // (a indoors, b outdoors)
            const dielectric = mix(uDiel, float(1.0), metalness.clamp(0.0, 1.0));
            let irr = nodes.irradiance.mul(Math.PI).mul(uFill);
            const pr = probeTerm();
            if (pr) irr = irr.add(pr);
            const out = outdoor ? outdoor.irradiance.mul(Math.PI).mul(uSky) : null;
            const around = sunColour ? vec3(...sunColour).mul(OUTDOOR.A) : null;
            builder.context.iblIrradiance.addAssign(pick(irr, out && around ? out.add(around) : (out || around)));
            builder.context.radiance.addAssign(pick(nodes.radiance.mul(uReflect).mul(dielectric), outdoor ? outdoor.radiance.mul(uSky) : null));
            // (a coat is a dielectric too: the floor's sealer, whose mirror EEVEE traces on screen from the real hall)
            const cc = builder.context.lightingModel.clearcoatRadiance;
            if (cc) cc.addAssign(pick(nodes.coat.mul(uReflect).mul(uDiel), outdoor ? outdoor.coat.mul(uSky) : null));
        }
    }
    return {
        fill: uFill, reflect: uReflect, dielectric: uDiel, aisle: uAisle, skyFill: uSky, nodes,
        lighting: () => new HallEnvironmentNode(),
        capture(scene, passes = 2, log = null) {
            group.updateMatrixWorld(true);
            const position = new T.Vector3(...at).applyMatrix4(group.matrixWorld);
            for (let i = 0; i < passes; i++) {
                work = pm.fromScene(scene, 0, 0.05, 600, { size, position, renderTarget: work || undefined });
                renderer.copyTextureToTexture(work.texture, target.texture);
            }
            if (log) log(`[hall] the reflections captured: ${passes} passes into ${target.width} x ${target.height}`);
        },
        dispose() { target.dispose(); if (work) work.dispose(); pm.dispose(); },
    };
}
