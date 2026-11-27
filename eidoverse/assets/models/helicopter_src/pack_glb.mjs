// pack_glb.mjs: a raw GLB from an export_glb.py made small for the library (Deno, gltf-transform + meshoptimizer).
//
//   deno run -A --no-lock eidoverse/assets/models/helicopter_src/pack_glb.mjs work/props/helicopter/web/helicopter_raw.glb \
//       eidoverse/assets/models/helicopter/helicopter.glb --unit _MASKS,_BLADE
//   deno run -A --no-lock eidoverse/assets/models/helicopter_src/pack_glb.mjs work/props/houseplants/web/monstera.glb \
//       eidoverse/assets/models/houseplants/monstera.glb
//
// (--no-lock: its packages are a tool's, not the renderer's, and stay out of the repository's deno.lock)
//
// Positions stay float32 in the asset's own metres (the materials read them as the asset's space, so they are not
// quantized into a node transform); normals become 8-bit; the custom attributes named by --unit (0..1 by
// construction: clamped) become 8-bit unsigned normalized, every other custom attribute stays as it is; vertices are
// reordered for the GPU's cache, and every stream is compressed with EXT_meshopt_compression (three's GLTFLoader
// decodes it once a MeshoptDecoder is set: the props' modules set their own). Node names, materials and extras are
// kept. The packages are fetched from npm on first use.
import { NodeIO, PropertyType } from 'npm:@gltf-transform/core@4.1.1';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from 'npm:@gltf-transform/extensions@4.1.1';
import { dedup, quantize, reorder, prune } from 'npm:@gltf-transform/functions@4.1.1';
import { MeshoptDecoder, MeshoptEncoder } from 'npm:meshoptimizer@0.22.0';

const args = [...Deno.args];
const ui = args.indexOf('--unit');
const unit = ui >= 0 ? args.splice(ui, 2)[1].split(',') : [];
const [src, dst] = args;
if (!src || !dst) {
    console.error('usage: deno run -A pack_glb.mjs <raw.glb> <out.glb> [--unit _A,_B]');
    Deno.exit(2);
}
await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(src);

// the unit attributes are 0..1 by construction: clamp what float rounding left outside, so they quantize as unsigned
// normalized
for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
        for (const sem of prim.listSemantics()) {
            if (!unit.includes(sem)) continue;
            const a = prim.getAttribute(sem), arr = a.getArray();
            for (let i = 0; i < arr.length; i++) arr[i] = Math.min(1, Math.max(0, arr[i]));
            a.setArray(arr);
        }
    }
}
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
await doc.transform(
    dedup({ propertyTypes: [PropertyType.ACCESSOR, PropertyType.MESH] }),   // (never materials: each is its role by name)
    prune({ keepLeaves: true, keepAttributes: true, keepExtras: true }),
    reorder({ encoder: MeshoptEncoder, target: 'performance' }),
    quantize({ pattern: new RegExp(`^(NORMAL${unit.map((u) => '|' + esc(u)).join('')})$`), quantizeNormal: 8, quantizeGeneric: 8 }),
);
doc.createExtension(EXTMeshoptCompression).setRequired(true)
    .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
await io.write(dst, doc);
const st = await Deno.stat(dst);
let verts = 0, tris = 0;
for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
        verts += prim.getAttribute('POSITION').getCount();
        tris += (prim.getIndices()?.getCount() ?? 0) / 3;
    }
}
console.log(JSON.stringify({ out: dst, mb: +(st.size / 1e6).toFixed(2), meshes: doc.getRoot().listMeshes().length, vertices: verts, triangles: tris }));
