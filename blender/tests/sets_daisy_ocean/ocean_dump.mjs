// ocean_dump.mjs: runs the WebGPU edition's verse-3 set (eidoverse/sets/ocean.js and ocean/*.js, untouched) headless
// in Deno and dumps what the Blender port must reproduce: the coast (heights, signed distances, her mark, the house
// pad), the sky's moon and the layout's turn, every shot's camera and her mark through the verse, the pages' flights
// and highlights, the echoes' lights, the dune-grass plan, the sea's per-cell hash. Nothing renders: the TSL graphs
// are built and never compiled; the GLBs are not loaded (GLTFLoader is absent, so the set falls back exactly as it
// does when they are missing) and textures are stubs.
//   cd <worktree> && deno run --no-config --no-lock -A blender/tests/sets_daisy_ocean/ocean_dump.mjs <three build dir> <out.json>
const [threeDir, outPath] = Deno.args;
if (!threeDir || !outPath) throw new Error('usage: ocean_dump.mjs <node_modules/three/build dir> <out.json>');
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const W = await import(url(threeDir + '/three.webgpu.js'));
const THREE = { ...W, ...W.TSL };
globalThis.THREE = THREE;
globalThis.loadImageTexture = async () => new W.Texture();
const here = new URL('.', import.meta.url);
const eido = new URL('../../../eidoverse/', here);
const anyFile = decodeURIComponent(new URL('sets/ocean/util.js', eido).pathname).replace(/^\/([A-Za-z]:)/, '$1');
globalThis.fetchPBR = async () => ({ files: { diff: anyFile, normal: anyFile, arm: anyFile } });
const util = await import(new URL('sets/ocean/util.js', eido).href);
await util.initCanvas();
const { createCanvas } = await import('npm:@napi-rs/canvas@0.1.69');
// document.createElement('canvas') for land.js / daisies.js: the native canvas made at its final size on first use
globalThis.document = {
    createElement: () => {
        let w = 300, h = 150, cv = null;
        return {
            get width() { return w; }, set width(v) { w = v; }, get height() { return h; }, set height(v) { h = v; },
            getContext(k) { cv ??= createCanvas(w, h); return cv.getContext(k); },
        };
    },
};
const O = await import(new URL('sets/ocean.js', eido).href);
const { makeCoast } = await import(new URL('sets/ocean/land.js', eido).href);
const ocean = await O.build({ THREE, EIDOVERSE_DIR: eido.href });
const v3 = (v) => [v.x, v.y, v.z];
const out = {};

// ---- the coast
const coast = makeCoast();
out.coast = { markY: coast.markY, house: coast.house, samples: [] };
for (let i = 0; i < 400; i++) {
    const a = i * 2.399963, r = 0.3 + Math.pow(i / 400, 2) * 120;
    const x = Math.sin(a) * r, z = Math.cos(a) * r - 10;
    out.coast.samples.push([x, z, coast.sdist(x, z), coast.height(x, z)]);
}

// ---- the sky's moon, the layout's turn, her face
out.moon = v3(O.skyMoonDir(THREE));
out.SKY = O.SKY;
out.BAR = O.BAR;
out.PSI = ocean.layout.rotation.y;
out.E = v3(ocean.E);
out.mark = v3(ocean.mark);

// ---- every shot through the verse: camera, mark, and the state update() writes
out.frames = [];
for (let k = 0; k <= 33.75 * 20; k++) {
    const u = k / 20, t = 100 + u;
    ocean.update(t, { u, pulse: 0.5 });
    const c = ocean.camera(u), m = ocean.markAt(u);
    const p23 = ocean.pages.p23.holder, p26 = ocean.pages.p26.holder;
    out.frames.push({
        u, cam: { pos: v3(c.pos), target: v3(c.target), fov: c.fov }, mark: { pos: v3(m.pos), yaw: m.yaw },
        reveal: ocean.sea.U.reveal.value, glow: ocean.sea.U.glow.value,
        echoes: { sink: ocean.echoes.U.sink.value, level: ocean.echoes.U.level.value, visible: ocean.echoes.group.visible },
        p23: { on: p23.visible, pos: v3(p23.position), q: [p23.quaternion.x, p23.quaternion.y, p23.quaternion.z, p23.quaternion.w] },
        p26: { on: p26.visible, pos: v3(p26.position), q: [p26.quaternion.x, p26.quaternion.y, p26.quaternion.z, p26.quaternion.w] },
    });
}

// ---- the pages: highlight rects and centres
out.pages = {};
for (const p of ocean.pages.pages) out.pages[p.which] = { his: p.his, hiCenter: v3(p.hiCenter) };

// ---- the echoes' lights (one quad per light: every 4th vertex)
{
    const g = ocean.echoes.group.children.find((o) => o.name === 'ocean_echoes').geometry;
    const cen = g.attributes.center.array, col = g.attributes.ecol.array, prm = g.attributes.prm.array;
    out.echoes = [];
    for (let i = 0; i < cen.length / 12; i++) {
        out.echoes.push({ c: [cen[i * 12], cen[i * 12 + 1], cen[i * 12 + 2]], col: [col[i * 12], col[i * 12 + 1], col[i * 12 + 2]],
            prm: [prm[i * 16], prm[i * 16 + 1], prm[i * 16 + 2], prm[i * 16 + 3]] });
    }
}

// ---- the dune grass: count and every instance matrix
{
    let inst = null;
    ocean.group.traverse((o) => { if (o.isInstancedMesh && o.name === 'ocean_dunegrass') inst = o; });
    out.grass = { count: inst ? inst.count : 0, matrices: inst ? Array.from(inst.instanceMatrix.array) : [],
        tuft: inst ? { position: Array.from(inst.geometry.attributes.position.array), index: Array.from(inst.geometry.index.array) } : null };
}

// ---- the sea: the PCG hash three's TSL hash() runs (nodes/math/Hash.js), on the seeds cellOf makes
const pcg = (seed) => {
    const s = (Math.trunc(Math.max(0, seed)) >>> 0);
    const state = (Math.imul(s, 747796405) + 2891336453) >>> 0;
    const word = Math.imul(((state >>> (((state >>> 28) + 4) >>> 0)) ^ state) >>> 0, 277803737) >>> 0;
    return (((word >>> 22) ^ word) >>> 0) / 4294967296;
};
out.hash = [];
for (const s of [0, 1, 17, 2368, 37 * 64, 37 * 73, 537000, 541441, 1234567, 1600000.5, 16777215]) out.hash.push([s, pcg(s)]);
out.faceCellInfo = ocean.sea.faceCellInfo;

await Deno.writeTextFile(outPath, JSON.stringify(out));
console.log(`[ocean_dump] PSI ${out.PSI.toFixed(5)} markY ${coast.markY.toFixed(5)} echoes ${out.echoes.length} grass ${out.grass.count} -> ${outPath}`);
