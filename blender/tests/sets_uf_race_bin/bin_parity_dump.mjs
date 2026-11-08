// bin_parity_dump.mjs: builds the WebGPU edition's bin (eidoverse/sets/unknown_force/bin.js, untouched) headless in
// Deno and dumps what the Blender port must reproduce: heapHeight on a grid, the can's scale and radius, every
// instanced sheet / boulder / falling sheet (matrix, cell, shade), the mark and focal for a few climbs, and the
// stickers and cut-shapes canvases as PNGs. A tiny glTF reader stands in for GLTFLoader (only geometry and node
// transforms matter here); the page atlas is drawn at a small scale (the placement does not read it).
//   cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/bin_parity_dump.mjs <gltf>
// Writes blender/tests/sets_uf_race_bin/out/parity/bin.json (bin_parity.py compares).
const W = await import('npm:three@0.184.0/webgpu');
const napi = await import('npm:@napi-rs/canvas@0.1.69');
globalThis.THREE = W;
const root = Deno.cwd().replace(/\\/g, '/');
globalThis.EIDOVERSE_DIR = new URL('file:///' + root.replace(/^\/+/, '') + '/eidoverse/');
const gltfPath = Deno.args[0];
globalThis.fetchModelFile = async () => gltfPath;
// a minimal glTF reader: meshes (positions, normals, uvs, indices) under their nodes' transforms
globalThis.GLTFLoader = class {
    async parseAsync(buf) {
        const g = JSON.parse(new TextDecoder().decode(new Uint8Array(buf)));
        const bufs = g.buffers.map((b) => Uint8Array.from(atob(b.uri.split(',')[1]), (c) => c.charCodeAt(0)));
        const acc = (i) => {
            const a = g.accessors[i], bv = g.bufferViews[a.bufferView], b = bufs[bv.buffer];
            const n = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[a.type];
            const T = { 5126: Float32Array, 5123: Uint16Array, 5125: Uint32Array, 5121: Uint8Array }[a.componentType];
            const off = (bv.byteOffset || 0) + (a.byteOffset || 0);
            return new T(b.buffer.slice(b.byteOffset + off, b.byteOffset + off + a.count * n * T.BYTES_PER_ELEMENT));
        };
        const scene = new W.Group();
        for (const nd of g.nodes) {
            if (nd.mesh === undefined) continue;
            const pr = g.meshes[nd.mesh].primitives[0];
            const geo = new W.BufferGeometry();
            geo.setAttribute('position', new W.BufferAttribute(acc(pr.attributes.POSITION), 3));
            if (pr.attributes.NORMAL !== undefined) geo.setAttribute('normal', new W.BufferAttribute(acc(pr.attributes.NORMAL), 3));
            if (pr.attributes.TEXCOORD_0 !== undefined) geo.setAttribute('uv', new W.BufferAttribute(acc(pr.attributes.TEXCOORD_0), 2));
            if (pr.indices !== undefined) geo.setIndex(new W.BufferAttribute(acc(pr.indices), 1));
            const mat = { map: new W.Texture(), normalMap: new W.Texture(), roughnessMap: new W.Texture(), metalnessMap: new W.Texture(), roughness: 1, metalness: 1 };
            const m = new W.Mesh(geo, new W.MeshStandardMaterial());
            Object.assign(m.material, mat);
            m.name = nd.name;
            if (nd.translation) m.position.fromArray(nd.translation);
            if (nd.rotation) m.quaternion.fromArray(nd.rotation);
            if (nd.scale) m.scale.fromArray(nd.scale);
            scene.add(m);
        }
        return { scene };
    }
};
const B = await import(new URL('sets/unknown_force/bin.js', globalThis.EIDOVERSE_DIR).href);
const outDir = root + '/blender/tests/sets_uf_race_bin/out/parity';
await Deno.mkdir(outDir, { recursive: true });
const bin = await B.build(W, { atlasScale: 0.125 });
const P = bin.parts;
const out = { R: P.R, H: P.H, yFill: P.yFill, cams: bin.cams };
out.heap = [];
for (let x = -26; x <= 26; x += 2.6) for (let z = -22; z <= 44; z += 3.3) out.heap.push([x, z, B.heapHeight(x, z, P.R), B.heapHeight(x, z)]);
const inst = {};
P.paper.traverse((o) => {
    if (!o.isInstancedMesh) return;
    const n = o.count, m = o.instanceMatrix.array, cell = o.geometry.attributes.aCell.array, shade = o.geometry.attributes.aShade.array;
    inst[o.name] = { n, m: Array.from(m.slice(0, n * 16)), cell: Array.from(cell.slice(0, n)), shade: Array.from(shade.slice(0, n)) };
});
const fall = bin.group.children.find((o) => o.name === 'bin:falling');
inst['bin:falling'] = { n: fall.count, cell: Array.from(fall.geometry.attributes.aCell.array), shade: Array.from(fall.geometry.attributes.aShade.array) };
out.instances = inst;
out.mark = [0, 0.3, 0.5, 0.75, 0.95, 1].map((c) => { bin.update(230, { climb: c }); return [c, P.mark.position.toArray()]; });
out.focal = bin.focalPoint(new W.Vector3()).toArray();
out.lid = { pos: P.lid.position.toArray(), q: P.lid.quaternion.toArray() };
out.toppled = { pos: P.toppled.position.toArray(), q: P.toppled.quaternion.toArray() };
out.lampPos = P.lamp.position.toArray();
out.lights = Object.fromEntries(Object.entries(P.lights).map(([k, l]) => [k, { pos: l.position.toArray(), i: l.intensity }]));
bin.update(240, { hush: 0.5, glow: 0.3 });
out.lightsHush = Object.fromEntries(Object.entries(P.lights).map(([k, l]) => [k, l.intensity]));
// the canvases the materials read (the stickers, the cut shapes) as PNGs
const seen = new Set(), canv = new Set();
const walk = (n, depth = 0) => {
    if (!n || typeof n !== 'object' || seen.has(n) || depth > 80) return; seen.add(n);
    if (n.isCanvasTexture && n.image?.toBuffer) canv.add(n);
    for (const k of Object.keys(n)) { const v = n[k]; if (v && typeof v === 'object' && (v.isNode || v.isTexture || Array.isArray(v) || k === 'value')) walk(v, depth + 1); }
};
bin.group.traverse((o) => { if (o.material) for (const k of Object.keys(o.material)) { const v = o.material[k]; if (v && v.isNode) walk(v); } });
for (const t of canv) { const c = t.image; if (c.width === 2048) await Deno.writeFile(`${outDir}/bin_canvas_${c.width}x${c.height}_${[...canv].indexOf(t)}.png`, c.toBuffer('image/png')); }
await Deno.writeTextFile(`${outDir}/bin.json`, JSON.stringify(out));
console.log('[bin_parity_dump] wrote', outDir, 'R', P.R, Object.fromEntries(Object.entries(inst).map(([k, v]) => [k, v.n])));
Deno.exit(0);
