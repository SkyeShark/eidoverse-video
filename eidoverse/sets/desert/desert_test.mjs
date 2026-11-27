// eidoverse/sets/desert/desert_test.mjs — the library's desert is the Blender edition's, and its files agree with their
// manifest:
//   deno test -A eidoverse/sets/desert/desert_test.mjs
// The numbers on the right are the Blender edition's (eidoblend.sets.desert, its chain at its defaults: the default
// town, film quality): what its mesh step and its look's lenses give. Only the GLBs' JSON is read (no decoding).
const MODELS = new URL('../../assets/models/desert/', import.meta.url);
const M = JSON.parse(Deno.readTextFileSync(new URL('desert.json', MODELS)));
const assert = (x, m = 'Assertion failed') => { if (!x) throw Error(m); };
const near = (a, b, e, m = '') => assert(Math.abs(a - b) <= e, `${m} ${a} versus ${b}`);

// a GLB's JSON chunk
function gltf(name) {
    const b = Deno.readFileSync(new URL(name, MODELS));
    const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
    assert(v.getUint32(0, true) === 0x46546C67 && v.getUint32(4, true) === 2, `${name}: not a GLB 2`);
    const n = v.getUint32(12, true);
    assert(v.getUint32(16, true) === 0x4E4F534A, `${name}: no JSON chunk`);
    return JSON.parse(new TextDecoder().decode(b.subarray(20, 20 + n)));
}

Deno.test('the land is the Blender edition\'s mesh', () => {
    assert(M.land.vertices === 2493312, `${M.land.vertices} vertices`);
    assert(M.land.faces === 2506656, `${M.land.faces} faces`);
    assert(M.chain.mesh.k === 0.0016 && M.chain.mesh.max_level === 10, 'mesh.py at the film quality');
    assert(M.scrub.shrubs === 5657 && M.scrub.kinds.reduce((a, b) => a + b, 0) === 5657, `${M.scrub.shrubs} shrubs`);
    // the close looks the Blender look finds in the land (look.views)
    const v = Object.fromEntries(M.views.map(([n, p, t, L]) => [n, { p, t, L }]));
    assert(M.views.length === 14, `${M.views.length} lenses`);
    near(v.close_cliff_and_talus.t[0], -930, 1e-6, 'the cliff x'); near(v.close_cliff_and_talus.t[1], 2354, 1e-6, 'the cliff y');
    near(v.close_dunes.t[0], -250, 1e-6, 'the dunes x'); near(v.close_dunes.t[1], -1938, 1e-6, 'the dunes y');
    near(v.close_dunes.t[2] / 0.6, 37, 0.5, 'the dune\'s height');
    assert(v.ring_c_mY.p.join() === '0,0,75' && v.ring_c_mY.L === 35, 'ring_c_mY');
});

Deno.test('each ring\'s GLB holds what the manifest says, quantized one way', () => {
    let verts = 0, tris = 0;
    for (const [name, ring] of Object.entries(M.land.rings)) {
        const g = gltf(ring.file);
        for (const ext of ['KHR_mesh_quantization', 'EXT_meshopt_compression']) assert(g.extensionsRequired.includes(ext), `${ring.file}: ${ext}`);
        assert(g.meshes.length === ring.tiles, `${ring.file}: ${g.meshes.length} tiles`);
        let v = 0, t = 0;
        for (const mesh of g.meshes) {
            const p = mesh.primitives[0];
            v += g.accessors[p.attributes.POSITION].count;
            t += g.accessors[p.indices].count / 3;
            for (const a of ['NORMAL', '_DMA', '_DMB']) assert(a in p.attributes, `${mesh.name}: ${a}`);
            assert(g.accessors[p.attributes.POSITION].componentType === 5122, `${mesh.name}: positions are 16-bit`);
        }
        assert(v === ring.vertices && t === ring.triangles, `${name}: ${v} vertices, ${t} triangles`);
        for (const node of g.nodes.filter((n) => n.mesh !== undefined)) {
            assert(node.scale.join() === M.land.quantization.scale.join(), `${node.name}: its scale`);
            assert(node.translation.join() === M.land.quantization.offset.join(), `${node.name}: its translation`);
        }
        verts += v; tris += t;
    }
    // (the tiles share their edges' vertices: a little more than the mesh's; the mesh's 2,477,088 quads two triangles
    //  each, and its 29,568 triangles)
    assert(verts >= M.land.vertices && verts < M.land.vertices * 1.01, `${verts} tile vertices`);
    assert(tris === 2 * 2477088 + 29568, `${tris} triangles`);
});

Deno.test('the scrub is instanced at every place', () => {
    const g = gltf(M.scrub.file);
    let n = 0;
    for (const node of g.nodes) {
        const inst = node.extensions?.EXT_mesh_gpu_instancing;
        if (!inst) continue;
        for (const k of ['TRANSLATION', 'ROTATION', 'SCALE', '_RND']) assert(k in inst.attributes, `${node.name}: ${k}`);
        n += g.accessors[inst.attributes.TRANSLATION].count;
    }
    assert(n === M.scrub.shrubs, `${n} shrubs placed`);
    assert(g.meshes.length === 4 && g.meshes.every((m) => m.primitives.length === 2), 'four shrubs, twigs and mound');
});
