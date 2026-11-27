// pack_glb.mjs: what export_desert.py wrote, made small for the library (Deno, glTF-Transform + meshoptimizer).
//
//   deno run -A --no-lock eidoverse/assets/models/desert_src/pack_glb.mjs work/desert_web eidoverse/assets/models/desert
//
// (--no-lock: its packages are a tool's, not the renderer's, and stay out of the repository's deno.lock)
//
// Each raw GLB (<src>/raw/*.glb) keeps the numbers export_desert.py gave it (the positions already quantized, the
// normals 8-bit, the masks 8- and 16-bit): its vertices are reordered for the GPU's cache and every stream is
// compressed with EXT_meshopt_compression, which loses nothing of them. three's GLTFLoader reads the result once a
// MeshoptDecoder is set (eidoverse/sets/desert/ sets its own). desert.json and the marks are copied beside the GLBs.
// The packages are fetched from npm on first use.
import { NodeIO } from 'npm:@gltf-transform/core@4.1.1';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from 'npm:@gltf-transform/extensions@4.1.1';
import { reorder } from 'npm:@gltf-transform/functions@4.1.1';
import { MeshoptDecoder, MeshoptEncoder } from 'npm:meshoptimizer@0.22.0';

const [src, dst] = Deno.args;
if (!src || !dst) {
    console.error('usage: deno run -A --no-lock pack_glb.mjs <export_desert.py --out folder> <library folder>');
    Deno.exit(2);
}
const join = (...p) => p.join('/').replace(/\\/g, '/').replace(/\/+/g, '/');
await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
Deno.mkdirSync(dst, { recursive: true });
const names = [...Deno.readDirSync(join(src, 'raw'))].map((e) => e.name).filter((n) => n.endsWith('.glb')).sort();
for (const name of names) {
    const doc = await io.read(join(src, 'raw', name));
    let verts = 0, tris = 0;
    for (const mesh of doc.getRoot().listMeshes()) {
        for (const prim of mesh.listPrimitives()) {
            verts += prim.getAttribute('POSITION').getCount();
            tris += (prim.getIndices()?.getCount() ?? 0) / 3;
        }
    }
    await doc.transform(reorder({ encoder: MeshoptEncoder, target: 'size' }));
    doc.createExtension(EXTMeshoptCompression).setRequired(true)
        .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
    await io.write(join(dst, name), doc);
    const raw = Deno.statSync(join(src, 'raw', name)).size, packed = Deno.statSync(join(dst, name)).size;
    console.log(JSON.stringify({ out: join(dst, name), mb: +(packed / 1e6).toFixed(2), raw_mb: +(raw / 1e6).toFixed(2), vertices: verts, triangles: tris }));
}
for (const name of ['desert.json', 'near_marks.png', 'mid_marks.png']) Deno.copyFileSync(join(src, name), join(dst, name));
