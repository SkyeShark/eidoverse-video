// eidoverse/sets/town/index.js — a concrete-frame town on a street grid, its edge thinning out into the plain: the
// three.js edition's port of the Blender edition's eidoblend.sets.town (registered there as 'places.town'). Dynamic
// ESM; import it inside setup():
//
//   const TOWN = await import(new URL('sets/town/index.js', EIDOVERSE_DIR).href);
//   const town = await TOWN.build(THREE);                          // 840 x 300 m of blocks, seed 7, intact
//   const town = await TOWN.build(THREE, { extent: [260, 160], edge: 60, things: false });       // a small one
//   const town = await TOWN.build(THREE, { damage: true });        // struck round strikes the seed places
//   const town = await TOWN.build(THREE, { signs: [yourText, anotherText, 'path/to/a_picture.png'], signFont: 'Anton-Regular.ttf' });
//   scene.add(town.group);
//   const W = await TOWN.world(THREE, { scene, camera, renderer, root: town.group });   // its sun, makeSky's sky, its air
//   for (const [name, pos, target, lens] of town.views()) TOWN.aim(THREE, camera, town.group, pos, target, lens);
//   per frame: W.update(t)
//
// The plan is the Blender edition's, draw for draw: the same seed and extent build the same town, building for
// building (pyrandom.js is Python's random; layout.js, house.js, kit.js, street.js port their modules). Every unique
// mesh is built once as a BufferGeometry and drawn as ONE InstancedMesh with every placing of it; its per-face masks
// (masks.js, three-mesh-bvh) are vertex attributes; its look (look.js) is TSL over CC0 sets fetched by ID on first use.
// Everything is in the town's own metres, +Z up, under group (turned -90 degrees about x into three's +Y up; world()
// may also turn it about the vertical to meet the sky's sun). Every placing carries its random number, how near a strike
// it stands (0 in an intact town) and its lot (town.plan.placements[i].tn: dust, w, d, h, in).
import { plan as makePlan } from './layout.js';
import { annotate, FAR } from './masks.js';
import { makeLook, BOARDS } from './look.js';
import { place, placingMatrix } from './things.js';
import { views as townViews, aim } from './views.js';
export { world, SUN_DIR, SKY_FAMILY, AIR } from './world.js';
export { aim };
export { YSTREETS, MOSQUE, planStrikes } from './layout.js';

const PICTURE = /\.(png|jpe?g|webp)$/i;

// the Blender edition's per-object random number (EEVEE's Object Info > Random): Jenkins' final mix of the name's
// string hash (BLI_hash_string: h = h * 37 + c)
export function objectRandom(name) {
    let h = 0;
    for (const ch of new TextEncoder().encode(name)) h = (Math.imul(h, 37) + ch) >>> 0;
    const rot = (x, k) => ((x << k) | (x >>> (32 - k))) >>> 0;
    let a, b, c;
    a = b = c = (0xdeadbeef + (2 << 2) + 13) >>> 0;
    a = (a + h) >>> 0; b = (b + 0) >>> 0;
    c ^= b; c = (c - rot(b, 14)) >>> 0;
    a ^= c; a = (a - rot(c, 11)) >>> 0;
    b ^= a; b = (b - rot(a, 25)) >>> 0;
    c ^= b; c = (c - rot(b, 16)) >>> 0;
    a ^= c; a = (a - rot(c, 4)) >>> 0;
    b ^= a; b = (b - rot(a, 14)) >>> 0;
    c ^= b; c = (c - rot(b, 24)) >>> 0;
    return (c >>> 0) / 0xFFFFFFFF;
}

// the shop signs from what the town is given: a picture's path, words (drawn on a canvas in the board's paint and ink,
// set in `font`: a file of eidoverse/assets/fonts/ (all OFL) or a path of your own, its licence travelling with it),
// { image } or { text, font }. The town ships no sign texts. A script that joins or runs right to left must be checked
// by a reader of the language.
async function prepareSigns(THREE, signs, font) {
    if (!signs || !signs.length) return [];
    const C = await import('npm:@napi-rs/canvas@0.1.69');
    const fontsDir = new URL('../../assets/fonts/', import.meta.url);
    const fontPath = (f) => {
        f = f || 'Anton-Regular.ttf';
        for (const p of [f, new URL(f, fontsDir)]) { try { Deno.statSync(p); return p instanceof URL ? decodeURIComponent(p.pathname).replace(/^\/([A-Za-z]:)/, '$1') : p; } catch { /* next */ } }
        throw new Error(`[town] sign font ${f}: not a file, nor one of eidoverse/assets/fonts/`);
    };
    const s2 = (v) => Math.round(255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055));
    const css = (c) => `rgb(${s2(c[0])}, ${s2(c[1])}, ${s2(c[2])})`;
    const out = [];
    for (let k = 0; k < signs.length; k++) {
        let s = signs[k];
        if (typeof s === 'string') s = PICTURE.test(s) ? { image: s } : { text: s };
        if (s.image) { out.push({ texture: await globalThis.loadImageTexture(Deno.readFileSync(s.image), { srgb: true }) }); continue; }
        const fam = `townsign${k}`;
        C.GlobalFonts.registerFromPath(fontPath(s.font || font), fam);
        const [board, ink] = BOARDS[k % BOARDS.length];
        const W = 1536, H = 256, cv = C.createCanvas(W, H), g = cv.getContext('2d');
        g.fillStyle = css(board); g.fillRect(0, 0, W, H);
        g.fillStyle = css(ink); g.textAlign = 'center'; g.textBaseline = 'middle';
        let px = H * 0.76;
        g.font = `${px}px ${fam}`;
        const w = g.measureText(String(s.text)).width;
        if (w > W * 0.88) { px *= W * 0.88 / w; g.font = `${px}px ${fam}`; }
        g.fillText(String(s.text), W / 2, H / 2);
        out.push({ texture: await globalThis.loadImageTexture(new Uint8Array(cv.toBuffer('image/png')), { srgb: true, wrap: THREE.ClampToEdgeWrapping }) });
    }
    return out;
}

// the town. opts: seed (7), extent ([840, 300]: the blocks, in metres), damage (false | true | [[x, y, reach]]),
// signs, signFont, things (the CC0 models, true), masks (true), edge (170: metres of edge past the blocks), ystreets,
// mosque ('auto'), clay (one grey for every surface: the form judged before the look), res (a CC0 resolution for every
// set, e.g. '1k', in place of the manifest's), log
// -> { group, plan, parts { name: InstancedMesh }, things, views(), stats, update(), dispose() }
export async function build(THREE, { seed = 7, extent = [840.0, 300.0], damage = false, signs = null, signFont = null, things = true, masks = true,
    edge = 170.0, ystreets = null, mosque = 'auto', clay = false, res = null, log = console.log } = {}) {
    const t0 = performance.now();
    const S = await prepareSigns(THREE, signs, signFont);
    const P = makePlan({ seed, extent, damage, signs: S, edge, ystreets, mosque, log });
    const look = await makeLook(THREE, { strikes: P.strikes, paved: P.paved, sandReach: P.sandReach, signs: S, clay, res, log });
    const group = new THREE.Group();
    group.name = 'town';
    group.rotation.x = -Math.PI / 2;                                 // the town's +Z up into three's +Y up
    const stats = { masks: {} };
    const geos = new Map();
    const slots = new Map();
    const slotOf = (m) => { if (!slots.has(m)) slots.set(m, look.slot(m)); return slots.get(m); };
    for (const [name, b] of P.designs) {
        let fd = masks ? annotate(THREE, name, b, stats.masks) : null;
        const n = b.f.length;
        if (!fd) {                                                   // (no mask read here: the defaults, so every mesh has them)
            const e = new Float32Array(n * 4), bx = new Float32Array(n * 4), s = new Float32Array(n * 4);
            for (let i = 0; i < n; i++) { e.set([FAR, -FAR, FAR, 0], i * 4); bx.set([-FAR, -FAR, FAR, FAR], i * 4); }
            fd = { tlE: [e, 4], tlB: [bx, 4], tlS: [s, 4] };
        }
        const tmA = new Float32Array(n * 4), tmB = new Float32Array(n * 4);    // the shared materials' numbers, a face
        b.m.forEach((m, i) => { const [, a, c] = slotOf(m); tmA.set(a, i * 4); tmB.set(c, i * 4); });
        fd.tmA = [tmA, 4]; fd.tmB = [tmB, 4];
        geos.set(name, b.geometry(THREE, fd, (m) => slotOf(m)[0]));
    }
    log(`[town] masks ${JSON.stringify(stats.masks)}; ${geos.size} meshes built (${((performance.now() - t0) / 1000).toFixed(1)} s)`);
    const byMesh = new Map();
    for (const p of P.placements) { if (!byMesh.has(p.mesh)) byMesh.set(p.mesh, []); byMesh.get(p.mesh).push(p); }
    const parts = {};
    const m4 = new THREE.Matrix4();
    let placedTris = 0, uniqueTris = 0;
    for (const [name, ps] of byMesh) {
        const geo = geos.get(name);
        const mats = geo.userData.materials.map((m) => look.material(m));
        const inst = new Float32Array(ps.length * 4);
        const im = new THREE.InstancedMesh(geo, mats, ps.length);
        ps.forEach((p, i) => {
            im.setMatrixAt(i, m4.set(...placingMatrix(p)));
            inst.set([objectRandom(p.name), p.tn.dust || 0.0, (name === 'town_ground' || name === 'town_streets') ? 1.0 : 0.0, 0.0], i * 4);
        });
        geo.setAttribute('inst', new THREE.InstancedBufferAttribute(inst, 4));
        im.instanceMatrix.needsUpdate = true;
        im.computeBoundingBox?.();
        im.computeBoundingSphere();
        im.castShadow = true; im.receiveShadow = true;
        im.name = name;
        group.add(im);
        parts[name] = im;
        const tris = geo.index.count / 3;
        uniqueTris += tris; placedTris += tris * ps.length;
    }
    let T = null;
    if (things) {
        T = await place(THREE, P, { log });
        const byKey = new Map();
        for (const o of T.placings) { if (!byKey.has(o.key)) byKey.set(o.key, []); byKey.get(o.key).push(o); }
        for (const [key, ps] of byKey) {
            for (const [geo, mat] of T.models[key].parts) {
                const im = new THREE.InstancedMesh(geo, mat, ps.length);
                const inst = new Float32Array(ps.length * 4);
                ps.forEach((o, i) => {
                    im.setMatrixAt(i, m4.set(...placingMatrix(o)));
                    inst.set([objectRandom(`cc0_${key}.${String(i).padStart(4, '0')}`), o.dust, 0.0, 0.0], i * 4);
                });
                geo.setAttribute('inst', new THREE.InstancedBufferAttribute(inst, 4));
                im.instanceMatrix.needsUpdate = true;
                im.computeBoundingSphere();
                im.castShadow = true; im.receiveShadow = true;
                im.name = `cc0_${key}`;
                group.add(im);
                placedTris += ps.length * (geo.index ? geo.index.count : geo.attributes.position.count) / 3;
            }
        }
    }
    Object.assign(stats, {
        buildings: P.placements.filter((p) => p.kind === 'buildings').length, placings: P.placements.length + (T ? T.placings.length : 0),
        meshes: byMesh.size, uniqueTriangles: uniqueTris, placedTriangles: placedTris, strikes: P.strikes.length, things: T ? T.counts : {},
        materials: look.materials.size, seconds: +((performance.now() - t0) / 1000).toFixed(1),
    });
    log(`[town] built: ${JSON.stringify(stats)}`);
    return {
        group, plan: P, parts, things: T, look, stats, strikes: P.strikes, ystreets: P.ystreets, xstreets: P.xstreets, paved: P.paved, extent: P.extent,
        views: () => townViews(P),
        update() { /* the town stands still: its sky and its sun are world()'s */ },
        dispose() {
            group.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
            for (const m of look.materials.values()) m.dispose();
            for (const t of look.textures.values()) t.dispose();
            group.removeFromParent();
        },
    };
}
