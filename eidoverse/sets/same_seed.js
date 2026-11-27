// sets/same_seed.js — the four rooms of the SAME SEED music video, made in Blender (the blender branch's
// eidoblend.sets.same_seed) and brought into this edition as they look there:
//
//   sealed_room  a sealed room in an old government building: painted block, plated windows, a door with no handle,
//                a welded steel bench, a stool, a camera in the corner, one fluorescent batten
//   kitchen      a kitchen at noon: cupboards, a cooker, a fridge, a farmhouse table with homework, basil on the sill,
//                a garden through the window
//   lab          a lab full of light: a ribbon of windows, a bench, a whiteboard, LED panels, a task chair and the
//                houseplants
//   desk         the room at 2 a.m.: a desk with a lit screen, a guitar, shelves of books, the desk lamp, the square at
//                night outside
//
//   const SS = await import(new URL('sets/same_seed.js', EIDOVERSE_DIR).href);
//   const room = await SS.build('kitchen', { THREE });     // { shadows: false } builds it without shadow maps
//   scene.add(room.group);                 // metres, +Y up; move or turn room.group to place it
//   room.applyTo(scene, renderer);         // its background (the world it was made in), AgX as Blender draws it, its exposure
//   room.camera('wide', camera);           // one of room.cams (the film's lenses): position, aim, field of view
//   room.marks.stand                       // { position, yaw, about }: where a body stands, things are set down
//   room.dispose();
//
// What loads: the parts with UV 'atlas' (the lows) as one GLB per atlas, their look baked by Cycles to base colour,
// ORM and normal (eidoverse/assets/models/same_seed_<room>_<atlas>.glb); everything else (walls, floors, trim, the
// small things) from same_seed_<room>_rest.glb with its Blender materials rebuilt in TSL by sets/same_seed/nodes.js
// from the node graphs in eidoverse/assets/sets/same_seed/<room>/materials.json, over CC0 photographs fetched by ID
// (fetchPBR); the Poly Haven models by ID as they ship (fetchModelFile), placed where the Blender room has them; the
// HDRIs by ID from the shared library; the lights as three.js lights; the bounce of the Blender room's volume probe as
// a baked irradiance grid and its reflection probe as an environment (sets/same_seed/light.js).
// Guide: tools-guides/props-and-sets.md, "The SAME SEED rooms". Rebuild: eidoverse/assets/sets/same_seed_src/.

import { makeGraphs } from './same_seed/nodes.js';
import { makeLight } from './same_seed/light.js';

export const ROOMS = ['sealed_room', 'kitchen', 'lab', 'desk'];

const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
const SETS = fsPath(new URL('../assets/sets/same_seed/', import.meta.url));
const MODELS = fsPath(new URL('../assets/models/', import.meta.url));
const CACHE = fsPath(new URL('../assets/cache/', import.meta.url));
const REPO = fsPath(new URL('../../', import.meta.url));

const readJSON = (p) => JSON.parse(Deno.readTextFileSync(p));

// an HDRI by ID in the shared library (eidoverse/assets/cache/hdris/<id>_<res>/hdri.hdr), fetched once by
// fetch_hdri.py when it is missing (EIDO_NO_FETCH=1: an error naming the command instead)
export async function fetchHDRIFile(id, res = '4k') {
    const dir = `${CACHE}hdris/${id}_${res}/`;
    const file = dir + 'hdri.hdr';
    try { Deno.statSync(file); return file; } catch { /* fetch it */ }
    const cmd = `python fetch_hdri.py ${id} ${res}   (run in ${dir})`;
    if (Deno.env.get('EIDO_NO_FETCH') === '1') throw new Error(`fetchHDRIFile: ${id} (${res}) is not in the library; ${cmd}`);
    console.log(`[same_seed] HDRI ${id} (${res}): not in the library yet; fetching once (CC0) ...`);
    Deno.mkdirSync(dir, { recursive: true });
    for (const py of [Deno.env.get('PYTHON'), 'python', 'python3', 'py'].filter(Boolean)) {
        try {
            await new Deno.Command(py, { args: [REPO + 'fetch_hdri.py', id, res], cwd: dir, stdout: 'piped', stderr: 'piped' }).output();
            try { Deno.removeSync(dir + 'hdri_b64.txt'); } catch { /* (its base64 sidecar, not read here) */ }
            break;
        } catch (e) { if (!(e instanceof Deno.errors.NotFound)) throw e; }
    }
    try { Deno.statSync(file); return file; } catch { throw new Error(`fetchHDRIFile: ${id} (${res}) could not be fetched; ${cmd}`); }
}

// a Radiance .hdr as an equirect DataTexture (rows flipped: DataTexture.flipY is ignored on WebGPU)
async function loadHDR(THREE, path) {
    const { HDRLoader } = await import('npm:three@0.184.0/addons/loaders/HDRLoader.js');
    const bytes = Deno.readFileSync(path);
    const hdr = new HDRLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    const row = hdr.width * 4, Ctor = hdr.data.constructor;
    const flipped = new Ctor(hdr.data.length);
    for (let y = 0; y < hdr.height; y++) flipped.set(hdr.data.subarray(y * row, (y + 1) * row), (hdr.height - 1 - y) * row);
    const t = new THREE.DataTexture(flipped, hdr.width, hdr.height, THREE.RGBAFormat, hdr.type || THREE.HalfFloatType);
    t.mapping = THREE.EquirectangularReflectionMapping;
    t.minFilter = THREE.LinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.wrapS = THREE.RepeatWrapping;
    t.colorSpace = THREE.LinearSRGBColorSpace;
    t.needsUpdate = true;
    return t;
}

// AgX as Blender 5.2 draws it (view AgX, look None, the sRGB display): three's AgXToneMapping follows Blender 4.0's
// and shows the mid-tones lighter (a linear grey of 0.1 is 100 of 255 there, 87 in Blender 5.2; 0.05 is 70 against 58).
// This is a fit to Blender's own view transform sampled on 2401 colours (49 levels from 2^-11 to 2^5, greys and four
// saturations of twelve hues): within 4 of 255 on greys and on colours up to half saturation, greys kept grey; the
// most saturated colours part by up to 26. Same form as three's: a matrix, log2, a degree-6 curve, a matrix, then
// power 2.4 (Blender's Rec.1886 encoding), the renderer's sRGB output encoding after it, as Blender's display does.
export function blenderAgX(THREE) {
    const { Fn, vec3, mat3, max, log2, clamp, pow } = THREE;
    const IN = mat3(vec3(0.736574695, 0.079445812, 0.059387554), vec3(0.202329113, 0.809665239, 0.119461389),
        vec3(0.061096192, 0.110888950, 0.821151056));
    const OUT = mat3(vec3(1.322293121, -0.090371980, -0.093314053), vec3(-0.237485211, 1.116302846, -0.153776730),
        vec3(-0.084807909, -0.025930867, 1.247090782));
    const LO = -7.867995672, HI = 3.696405273;
    const C = [0.062138114, 0.994685837, -6.868342789, 30.904943348, -49.199117261, 33.153705927, -8.051028486];
    return Fn(([color, exposure]) => {
        const c = IN.mul(vec3(color).mul(exposure));
        const t = clamp(log2(max(c, 1e-10)).sub(LO).div(HI - LO), 0.0, 1.0);
        let y = vec3(C[6]);
        for (let i = 5; i >= 0; i--) y = y.mul(t).add(C[i]);
        return clamp(pow(max(OUT.mul(y), 0.0), vec3(2.4)), 0.0, 1.0);
    }).setLayout({ name: 'blenderAgXToneMapping', type: 'vec3', inputs: [{ name: 'color', type: 'vec3' }, { name: 'exposure', type: 'float' }] });
}

function parseGLB(bytes, base = '') {
    const loader = new globalThis.GLTFLoader();
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return new Promise((res, rej) => loader.parse(buf, base, res, rej));
}

// a loaded glTF material (MeshStandardMaterial / MeshPhysicalMaterial) as a node material with the same maps
function nodeify(T, m) {
    if (!m || m.isNodeMaterial) return m;
    const phys = m.isMeshPhysicalMaterial;
    const n = phys ? new T.MeshPhysicalNodeMaterial() : new T.MeshStandardNodeMaterial();
    const keys = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'alphaMap', 'lightMap',
        'clearcoatMap', 'clearcoatRoughnessMap', 'clearcoatNormalMap', 'transmissionMap', 'thicknessMap', 'sheenColorMap',
        'sheenRoughnessMap', 'specularIntensityMap', 'specularColorMap', 'iridescenceMap', 'anisotropyMap'];
    for (const k of keys) if (m[k] !== undefined && m[k] !== null && k in n) n[k] = m[k];
    for (const k of ['color', 'emissive', 'sheenColor', 'specularColor', 'attenuationColor']) if (m[k] && n[k]) n[k].copy(m[k]);
    for (const k of ['roughness', 'metalness', 'emissiveIntensity', 'aoMapIntensity', 'opacity', 'alphaTest', 'clearcoat',
        'clearcoatRoughness', 'transmission', 'thickness', 'ior', 'sheen', 'sheenRoughness', 'specularIntensity',
        'attenuationDistance', 'envMapIntensity']) if (typeof m[k] === 'number' && k in n) n[k] = m[k];
    if (m.normalScale && n.normalScale) n.normalScale.copy(m.normalScale);
    if (m.clearcoatNormalScale && n.clearcoatNormalScale) n.clearcoatNormalScale.copy(m.clearcoatNormalScale);
    n.transparent = m.transparent; n.side = m.side; n.depthWrite = m.depthWrite; n.vertexColors = m.vertexColors;
    n.flatShading = m.flatShading;
    n.name = m.name;
    n.userData = { ...m.userData };
    return n;
}

export async function build(name, ctx = {}) {
    const T = ctx.THREE || globalThis.THREE;
    if (!ROOMS.includes(name)) throw new Error(`same_seed: no room ${name} (${ROOMS.join(', ')})`);
    const DIR = `${SETS}${name}/`;
    const room = readJSON(DIR + 'room.json');
    const mats = readJSON(DIR + 'materials.json');
    const log = (...a) => console.log(`[same_seed ${name}]`, ...a);
    const t0 = performance.now();

    const group = new T.Group();
    group.name = `same_seed:${name}`;
    const parts = [], disposables = [];

    // ------------------------------------------------------------------------------------- pictures
    const texCache = new Map();
    async function image(ref, { interp } = {}) {
        if (!ref) return null;
        let path = null;
        if (ref.kind === 'cc0') path = (await globalThis.fetchPBR(ref.id, { res: ref.res })).dir + ref.file;
        else if (ref.kind === 'print') path = DIR + ref.file;
        else if (ref.kind === 'hdri') path = await fetchHDRIFile(ref.id, ref.res);
        else { console.warn(`[same_seed ${name}] picture ${JSON.stringify(ref)} has no source here`); return null; }
        const srgb = ref.colorspace === 'srgb';
        const key = path + '|' + srgb + '|' + (interp || '');
        if (!texCache.has(key)) texCache.set(key, (async () => {
            let t;
            if (path.toLowerCase().endsWith('.hdr')) t = await loadHDR(T, path);
            else t = await globalThis.loadImageTexture(Deno.readFileSync(path), { srgb });
            t.wrapS = t.wrapT = T.RepeatWrapping;
            if (interp === 'Closest') { t.magFilter = T.NearestFilter; }
            t.anisotropy = 8;
            disposables.push(t);
            return t;
        })());
        return texCache.get(key);
    }

    // ------------------------------------------------------------------------------------- light
    const isCameraRay = T.uniform(1.0);
    const G = makeGraphs(T, { image, isCameraRay });
    const LL = makeLight(T);
    const reflection = room.reflection ? await loadHDR(T, DIR + room.reflection.file) : null;
    if (reflection) disposables.push(reflection);
    const lighting = LL.environment(room, reflection);
    const bounds = boundsOf(room);
    const lights = await LL.lights(room.lights, { shadows: ctx.shadows !== false, bounds });
    for (const l of lights) group.add(l);

    // ------------------------------------------------------------------------------------- the rest (TSL from graphs)
    const graphMats = new Map();
    function graphMaterial(mname, attrs) {
        const sig = mname + '|' + [...attrs].filter((a) => a.startsWith('_')).sort().join(',');
        if (!graphMats.has(sig)) graphMats.set(sig, (async () => {
            const g = mats.materials[mname];
            if (!g) { console.warn(`[same_seed ${name}] material ${mname} has no graph`); return new T.MeshStandardNodeMaterial({ color: 0xff00ff }); }
            const m = await G.material(g, { name: mname, lighting, attrs });
            disposables.push(m);
            return m;
        })());
        return graphMats.get(sig);
    }

    // CC0 models by ID, loaded once each
    const modelCache = new Map();
    function cc0Model(id, res) {
        const key = id + '_' + res;
        if (!modelCache.has(key)) modelCache.set(key, (async () => {
            const file = await globalThis.fetchModelFile(id, { res });
            const dir = file.replace(/[\\/][^\\/]*$/, '/');
            const gltf = await parseGLB(Deno.readFileSync(file), dir);
            return gltf;
        })());
        return modelCache.get(key);
    }
    const cc0Mats = new Map();
    function cc0Material(id, m, override = undefined) {
        const key = id + '|' + m.uuid + '|' + JSON.stringify(override ?? null);
        if (!cc0Mats.has(key)) {
            const n = nodeify(T, m);
            const ov = override !== undefined ? override : (room.model_overrides || {})[m.name];
            if (ov) {
                if (ov.emissive) n.emissive.setRGB(ov.emissive[0], ov.emissive[1], ov.emissive[2]);
                if (typeof ov.emissiveIntensity === 'number') n.emissiveIntensity = ov.emissiveIntensity;
                if (ov.emissive) n.emissiveMap = null;      // (a lamp the Blender look lit or put out: one colour)
            }
            n.setupEnvironment = function () { return lighting(); };
            disposables.push(n);
            cc0Mats.set(key, n);
        }
        return cc0Mats.get(key);
    }
    async function cc0MaterialByName(ref, override) {
        const gltf = await cc0Model(ref.id, ref.res);
        let found = null;
        gltf.scene.traverse((o) => {
            if (found || !o.isMesh) return;
            for (const m of (Array.isArray(o.material) ? o.material : [o.material])) if (m && m.name === ref.material) found = m;
        });
        if (!found) { console.warn(`[same_seed ${name}] ${ref.id} has no material ${ref.material}`); return new T.MeshStandardNodeMaterial(); }
        return cc0Material(ref.id, found, override);
    }

    function place(o, extras = {}) {
        // glass and films let their light through (Blender's transparent shadows), so they cast none here
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        o.castShadow = extras.shadow !== false && !ms.every((m) => m && m.transparent);
        o.receiveShadow = true;
        if (extras.camera === false) o.visible = false;
        parts.push(o);
    }

    const rest = await parseGLB(Deno.readFileSync(MODELS + room.rest.file));
    const restMeshes = [];
    rest.scene.traverse((o) => { if (o.isMesh) restMeshes.push(o); });
    for (const o of restMeshes) {
        const attrs = new Set(Object.keys(o.geometry.attributes));
        // (the UV map the mesh carries as TEXCOORD_0, which the export does not write twice: _uv_<name>=uv)
        if (o.userData.uv0 && attrs.has('uv')) attrs.add('_uv_' + String(o.userData.uv0).replace(/[^A-Za-z0-9]/g, '_').toLowerCase() + '=uv');
        const list = Array.isArray(o.material) ? o.material : [o.material];
        const out = [];
        for (const m of list) {
            const ex = (m && m.userData) || {};
            if (ex.cc0) out.push(await cc0MaterialByName(ex.cc0, ex.override));
            else out.push(await graphMaterial(ex.graph || m.name, attrs));
        }
        o.material = Array.isArray(o.material) ? out : out[0];
        const node = o.parent && o.parent !== rest.scene && !o.parent.isScene ? o.parent : o;
        place(o, node.userData || {});
    }
    group.add(rest.scene);

    // ------------------------------------------------------------------------------------- the lows (baked)
    for (const a of Object.values(room.lows || {})) {
        const g = await parseGLB(Deno.readFileSync(MODELS + a.file));
        g.scene.traverse((o) => {
            if (!o.isMesh) return;
            const list = Array.isArray(o.material) ? o.material : [o.material];
            const out = list.map((m) => {
                const n = nodeify(T, m);
                if (!(m.userData && m.userData.backfaceCulling)) n.side = T.DoubleSide;     // (Blender draws both sides)
                n.aoMap = null;            // (the bake's occlusion is already in the colour, as the Blender look put it)
                n.setupEnvironment = function () { return lighting(); };
                disposables.push(n);
                return n;
            });
            o.material = Array.isArray(o.material) ? out : out[0];
            place(o, o.userData || {});
        });
        group.add(g.scene);
    }

    // ------------------------------------------------------------------------------------- CC0 models as they ship
    for (const r of room.models || []) {
        const gltf = await cc0Model(r.id, r.res);
        const meshes = [];
        gltf.scene.traverse((o) => {
            if (!o.isMesh) return;
            const as = gltf.parser.associations.get(o);
            if (as && as.meshes === r.mesh) meshes.push(o);
        });
        if (!meshes.length) { console.warn(`[same_seed ${name}] ${r.id}: no mesh ${r.mesh}`); continue; }
        for (const src of meshes) {
            const list = Array.isArray(src.material) ? src.material : [src.material];
            const m = list.map((x) => cc0Material(r.id, x));
            const o = new T.Mesh(src.geometry, Array.isArray(src.material) ? m : m[0]);
            o.name = r.name;
            o.matrixAutoUpdate = false;
            o.matrix.fromArray(r.matrix);
            o.matrix.decompose(o.position, o.quaternion, o.scale);
            o.updateMatrix();
            place(o, { camera: r.camera, shadow: r.shadow });
            group.add(o);
        }
    }

    // ------------------------------------------------------------------------------------- cameras, marks, world
    const cams = room.cameras || {};
    const marks = {};
    for (const [k, m] of Object.entries(room.marks || {})) marks[k] = { ...m, position: new T.Vector3().fromArray(m.position) };
    const world = mats.world ? await G.world(mats.world) : null;

    // a camera set to one of the room's lenses (Blender's 36 mm sensor across the wider side), in the group's space
    function camera(cname, cam) {
        const c = cams[cname];
        if (!c) throw new Error(`same_seed ${name}: no camera ${cname} (${Object.keys(cams).join(', ')})`);
        const aspect = cam.aspect || 16 / 9;
        const hfov = 2 * Math.atan(c.sensor / 2 / c.lens);
        const vfov = aspect >= 1 ? 2 * Math.atan(Math.tan(hfov / 2) / aspect) : hfov;
        group.updateMatrixWorld(true);
        cam.position.fromArray(c.position).applyMatrix4(group.matrixWorld);
        cam.lookAt(new T.Vector3().fromArray(c.target).applyMatrix4(group.matrixWorld));
        cam.fov = vfov * 180 / Math.PI;
        cam.near = Math.min(cam.near, 0.05);
        cam.updateProjectionMatrix();
        return cam;
    }

    // the room's world behind its windows and its render settings on a scene and renderer: AgX as Blender draws it
    // (blenderAgX, as the renderer's CustomToneMapping) at the room's exposure
    function applyTo(scene, renderer = null) {
        if (world) scene.backgroundNode = world.color;
        else scene.background = new T.Color(0, 0, 0);
        if (reflection && !scene.environment) scene.environment = reflection;      // (for what the room does not own)
        if (renderer) {
            renderer.library.addToneMapping(blenderAgX(T), T.CustomToneMapping);
            renderer.toneMapping = T.CustomToneMapping;
            renderer.toneMappingExposure = Math.pow(2, room.render?.exposure || 0);
        }
    }

    function dispose() {
        group.removeFromParent();
        for (const d of disposables) { try { d.dispose(); } catch { /* already gone */ } }
        rest.scene.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
    }

    log(`built in ${((performance.now() - t0) / 1000).toFixed(1)} s: ${parts.length} parts, ${lights.filter((l) => l.isLight).length} lights,`
        + ` ${graphMats.size} rebuilt materials, ${modelCache.size} CC0 models${room.grid ? `, a ${room.grid.res.join(' x ')} bounce grid` : ''}`);
    return { name, group, parts, lights, cams, marks, camera, applyTo, dispose, isCameraRay, lighting, json: room, bounds };
}

function boundsOf(room) {
    if (room.grid) return { min: room.grid.min, max: room.grid.max };
    const ps = Object.values(room.cameras || {}).flatMap((c) => [c.position, c.target]);
    if (!ps.length) return null;
    const min = [0, 1, 2].map((i) => Math.min(...ps.map((p) => p[i])));
    const max = [0, 1, 2].map((i) => Math.max(...ps.map((p) => p[i])));
    return { min, max };
}
