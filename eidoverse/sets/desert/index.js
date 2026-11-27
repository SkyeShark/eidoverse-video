// eidoverse/sets/desert/index.js — the desert round a town, out to 32.8 km: a basin floor rising out of the town's plane,
// a braided wadi and its tributaries, star dunes, an escarpment with its outliers, inselbergs and ranges drowned in their
// own alluvium, tracks going on from the town's, low scrub on the sand it caught. The three.js edition's port of the
// Blender edition's eidoblend.sets.desert (registered there as 'places.desert'): the land is the Blender edition's own,
// made by its chain and exported (eidoverse/assets/models/desert/, made by desert_src/), its look TSL that goes on from
// the town's ground (look.js). Dynamic ESM; import it inside setup():
//
//   const DESERT = await import(new URL('sets/desert/index.js', EIDOVERSE_DIR).href);
//   const desert = await DESERT.build(THREE, { renderer });         // the land, its scrub and their look: about 5 s
//   scene.add(desert.group);
//   const TOWN = await import(new URL('sets/town/index.js', EIDOVERSE_DIR).href);
//   const town = await TOWN.build(THREE);                            // the town it was made round (840 x 300 m, seed 7)
//   scene.add(town.group);
//   const W = await DESERT.world(THREE, { scene, camera, renderer, roots: [desert.group, town.group] });
//   for (const [name, pos, target, lens] of desert.views()) DESERT.aim(THREE, camera, desert.group, pos, target, lens);
//   per frame: W.update(t)
//
// Everything is in the town's own metres, +Z up, under group (turned -90 degrees about x into three's +Y up, as the
// town's group is; world() turns them both about the vertical to meet the sky's sun). Put the two groups together,
// unscaled: the desert lies UNDER the town's plane (z -0.5) wherever the town has anything on the ground and rises
// through z 0 about 25 m out, so the town's own ground stays as it is. With no town, build(..., { plane: true }) lays
// the town's plane (its ground, 3.2 km square at z 0) where the town would stand. The camera wants its far plane at
// 33 km or more (the Blender lens: 1 m to 40 km). Guide: tools-guides/props-and-sets.md ("The desert").
import { makeLook } from './look.js';
import { aim } from '../town/views.js';
import { world as townWorld, AIR as TOWN_AIR } from '../town/world.js';
export { aim };
export { AIR, LAYERS, REG } from './look.js';

const MODELS = new URL('../../assets/models/desert/', import.meta.url);
// the town's dust as EEVEE holds it: a box 5.2 km across and 900 m high round the town (from 40 m under its plane),
// integrated along the lens's ray to 3.5 km (the Blender edition's town world.AIR and its volumes' end in town.eevee).
// What it gives back toward the lens is the lit dust: color (linear) times 1 + sun x its Henyey-Greenstein phase at
// the volume's anisotropy (0.45: brighter toward the sun), matched to the Blender edition's stills of the desert
export const HAZE = { size: [5200.0, 5200.0, 900.0], z0: -40.0, reach: 3500.0, density: TOWN_AIR.density, anisotropy: 0.45,
    color: [0.224, 0.203, 0.153], sun: 11.8 };
// the sun's shadow over the desert: one 8192 map 1.6 km across round the lens's ground point (the town's world()
// follows it), its texels 0.2 m as the town's own 320 m map has them, so the scrub's and the near dunes' shadows
// reach about 1.4 km past the lens and the town's stay sharp
export const SHADOW = { size: 8192, extent: 800 };

export function manifest() {
    return JSON.parse(Deno.readTextFileSync(new URL('desert.json', MODELS)));
}

// a vertex attribute as its own array (a meshopt-decoded one may be a view into a shared, interleaved buffer)
function own(THREE, a) {
    const n = a.count, k = a.itemSize, out = new a.array.constructor(n * k);
    for (let i = 0; i < n; i++) for (let c = 0; c < k; c++) out[i * k + c] = a.array[a.isInterleavedBufferAttribute ? a.offset + i * a.data.stride + c : i * k + c];
    return new THREE.BufferAttribute(out, k, a.normalized);
}

// the desert. opts: renderer (required: the look's texture array is written through it), scrub (true), plane (false:
// the town's plane where no town stands), shadows (true), res (one CC0 resolution for every set, e.g. '1k'), log
// -> { group, tiles, scrub, plane, look, manifest, views(), stats, update(), dispose() }
export async function build(THREE, { renderer, scrub = true, plane = false, shadows = true, res = null, log = console.log } = {}) {
    const t0 = performance.now();
    const M = manifest();
    const { MeshoptDecoder } = await import('npm:three@0.184.0/addons/libs/meshopt_decoder.module.js');
    await MeshoptDecoder.ready;
    const loader = new globalThis.GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    const load = async (name) => {
        const b = await Deno.readFile(new URL(name, MODELS));
        return loader.parseAsync(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), '');
    };
    const mark = async (reach) => {
        const m = M.marks.find((x) => x.reach === reach);
        return { texture: await globalThis.loadImageTexture(Deno.readFileSync(new URL(m.file, MODELS)), { wrap: THREE.ClampToEdgeWrapping }), reach };
    };
    const look = await makeLook(THREE, { renderer, masks: M.land.masks, marks: { near: await mark(2048), mid: await mark(8192) }, res, log });
    const group = new THREE.Group();
    group.name = 'desert';
    group.rotation.x = -Math.PI / 2;                                 // the town's +Z up into three's +Y up
    // THE LAND: each tile's positions back to metres (the tile node's quantization: x and y in 2 m steps, z in 1/128 m),
    // its normals to floats; the masks stay 16- and 8-bit (read normalized)
    const tiles = [];
    let verts = 0, tris = 0;
    for (const ring of Object.values(M.land.rings)) {
        const gltf = await load(ring.file);
        const meshes = [];
        gltf.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
        for (const o of meshes) {
            const g = o.geometry, pos = g.getAttribute('position'), nrm = g.getAttribute('normal');
            const s = o.scale, p = o.position, n = pos.count;
            const P = new Float32Array(n * 3), N = new Float32Array(n * 3);
            for (let i = 0; i < n; i++) {
                P[i * 3] = pos.getX(i) * s.x + p.x; P[i * 3 + 1] = pos.getY(i) * s.y + p.y; P[i * 3 + 2] = pos.getZ(i) * s.z + p.z;
                const x = nrm.getX(i), y = nrm.getY(i), z = nrm.getZ(i), l = Math.hypot(x, y, z) || 1.0;
                N[i * 3] = x / l; N[i * 3 + 1] = y / l; N[i * 3 + 2] = z / l;
            }
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(P, 3));
            geo.setAttribute('normal', new THREE.BufferAttribute(N, 3));
            geo.setAttribute('dmA', own(THREE, g.getAttribute('_dma')));
            geo.setAttribute('dmB', own(THREE, g.getAttribute('_dmb')));
            geo.setIndex(new THREE.BufferAttribute(new Uint32Array(g.index.array), 1));
            geo.computeBoundingBox();
            geo.computeBoundingSphere();
            g.dispose();
            const mesh = new THREE.Mesh(geo, look.ground);
            mesh.name = o.name;
            mesh.castShadow = mesh.receiveShadow = shadows;
            mesh.userData.noSupportCheck = true;                     // (the ground itself)
            group.add(mesh);
            tiles.push(mesh);
            verts += n;
            tris += geo.index.count / 3;
        }
    }
    // THE SCRUB: the four shrubs instanced at their places (EXT_mesh_gpu_instancing, in the land's metres), each with
    // its own number; the mounds of sand they caught are drawn with the ground's material, as in the Blender edition
    const shrubs = [];
    if (scrub) {
        const gs = await load(M.scrub.file);
        gs.scene.updateMatrixWorld(true);
        const ims = [];
        gs.scene.traverse((o) => { if (o.isInstancedMesh) ims.push(o); });
        for (const im of ims) {
            const g = im.geometry, r = g.getAttribute('_RND') ?? g.getAttribute('_rnd');
            g.deleteAttribute('_RND'); g.deleteAttribute('_rnd');
            const inst = new Float32Array(im.count * 4);
            for (let i = 0; i < im.count; i++) inst[i * 4] = r.getX(i);
            g.setAttribute('inst', new THREE.InstancedBufferAttribute(inst, 4));
            const mound = im.material.name === 'desert.ground';
            if (mound) {                                            // (no masks of the land's own: the ground's plain look)
                const n = g.getAttribute('position').count;
                g.setAttribute('dmA', new THREE.BufferAttribute(new Uint16Array(n * 4), 4, true));
                g.setAttribute('dmB', new THREE.BufferAttribute(new Uint8Array(n * 4), 4, true));
            }
            im.material = mound ? look.ground : look.scrub;
            im.removeFromParent();
            im.position.set(0, 0, 0); im.quaternion.identity(); im.scale.set(1, 1, 1);
            im.computeBoundingSphere();
            im.castShadow = im.receiveShadow = shadows;
            im.name = mound ? 'desert_scrub_mounds' : 'desert_scrub';
            im.userData.noSupportCheck = true;
            group.add(im);
            shrubs.push(im);
        }
    }
    let ground = null;
    if (plane) {                                                    // the town's plane where no town stands
        ground = new THREE.Mesh(new THREE.PlaneGeometry(3200.0, 3200.0), look.plain());
        ground.name = 'desert_plane';
        ground.receiveShadow = shadows;
        ground.userData.noSupportCheck = true;
        group.add(ground);
    }
    group.userData.noSupportCheck = true;
    const stats = { tiles: tiles.length, vertices: verts, triangles: tris, shrubs: M.scrub.shrubs, seconds: +((performance.now() - t0) / 1000).toFixed(1) };
    log(`[desert] built: ${JSON.stringify(stats)}`);
    return {
        group, tiles, scrub: shrubs, plane: ground, look, manifest: M, stats,
        views: () => M.views.map(([n, p, t, L]) => [n, p.slice(), t.slice(), L]),
        update() { /* the desert stands still: its sky and its sun are world()'s */ },
        dispose() {
            group.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
            look.dispose();
            group.removeFromParent();
        },
    };
}

// the town's light and air over the desert: the town's world() (its sun 50 degrees up, makeSky's Earth sky at the
// hour that stands it there, the town and the desert turned together to meet it, the dusty tints, the exposure) with
// its dust as EEVEE holds it: in the box round the town and out to 3.5 km along each ray (HAZE), not a fog to the
// horizon, so the far ranges show through it as they do in the Blender edition; brighter toward the sun; and over the
// sky too (EEVEE draws the world through the volume): a dome inside the sky family's, drawn right after it and blended
// over it, before anything else. roots: [the desert's group, the town's group ...] (the first is the one world()
// turns; the others follow it). Other options are the town's world()'s. -> the town's world() result, and hazeColor
// (the dust's colour, a uniform), hazeDome
export async function world(THREE, { scene, camera, renderer, roots, haze = true, shadow = SHADOW, ...opts } = {}) {
    const [root, ...others] = roots;
    const W = await townWorld(THREE, { scene, camera, renderer, root, haze: false, shadow, ...opts });
    const follow = () => {
        for (const o of others) { o.position.copy(root.position); o.quaternion.copy(root.quaternion); o.scale.copy(root.scale); o.updateMatrixWorld(true); }
    };
    follow();
    let toBox = null, hazeColor = null, toSun = null, dome = null;
    if (haze) {
        const { uniform, vec3, vec4, float, min, max, exp, abs, select, dot, pow, cameraPosition, positionWorld, fog } = THREE;
        toBox = uniform(new THREE.Matrix4());                         // the world into the town's metres
        toSun = uniform(new THREE.Vector3(0, 1, 0));                  // (world space)
        hazeColor = uniform(new THREE.Color(...HAZE.color));
        const [sx, sy, sz] = HAZE.size;
        const lo = vec3(-sx / 2, -sy / 2, HAZE.z0), hi = vec3(sx / 2, sy / 2, HAZE.z0 + sz);
        const ray = positionWorld.sub(cameraPosition), view = ray.normalize();
        // metres of the ray in the dust, the box's slabs in the town's metres, to the point (to the sky: to the reach)
        const inDust = (toPoint) => {
            const c = toBox.mul(vec4(cameraPosition, 1.0)).xyz, p = toBox.mul(vec4(positionWorld, 1.0)).xyz;
            const d = p.sub(c), len = d.length(), dir = d.div(max(len, 1e-6));
            const safe = select(abs(dir).lessThan(vec3(1e-6)), vec3(1e-6), dir);
            const t1 = lo.sub(c).div(safe), t2 = hi.sub(c).div(safe);
            const tn = min(t1, t2), tf = max(t1, t2);
            const near = max(max(max(tn.x, tn.y), tn.z), 0.0);
            const far = min(min(min(tf.x, tf.y), tf.z), toPoint ? min(len, HAZE.reach) : float(HAZE.reach));
            return max(far.sub(near), 0.0);
        };
        const g = HAZE.anisotropy;
        const phase = float((1 - g * g) / (4 * Math.PI)).div(pow(float(1 + g * g).sub(dot(view, toSun).mul(2 * g)), 1.5));
        const lit = vec3(hazeColor).mul(phase.mul(HAZE.sun).add(1.0));
        scene.fogNode = fog(lit, float(1.0).sub(exp(inDust(true).mul(-HAZE.density))));
        const m = new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide, depthWrite: false, fog: false, transparent: false });
        m.blending = THREE.CustomBlending;                           // (drawn in the opaque pass, blended over the sky)
        m.blendSrc = THREE.SrcAlphaFactor; m.blendDst = THREE.OneMinusSrcAlphaFactor;
        m.blendSrcAlpha = THREE.ZeroFactor; m.blendDstAlpha = THREE.OneFactor;
        m.colorNode = vec4(lit, float(1.0).sub(exp(inDust(false).mul(-HAZE.density))));
        if (THREE.mrt) m.mrtNode = THREE.mrt({ normal: vec4(0), metalrough: vec4(0) });   // (out of the post chain's G-buffer, as the sky's)
        dome = new THREE.Mesh(new THREE.SphereGeometry(2500.0, 48, 24), m);
        dome.name = 'desert_haze_sky';
        dome.renderOrder = -99;                                      // (the sky family's dome is -100)
        dome.frustumCulled = false;
        dome.userData.noSupportCheck = true;
        scene.add(dome);
    }
    const settle = () => {
        if (!toBox) return;
        toBox.value.copy(root.matrixWorld).invert();
        toSun.value.copy(W.sunWorld());
        dome.position.copy(camera.position);
        dome.updateMatrixWorld();
    };
    root.updateMatrixWorld(true);
    settle();
    return {
        ...W, hazeColor, hazeDome: dome,
        update(t) { W.update(t); follow(); settle(); },
    };
}
