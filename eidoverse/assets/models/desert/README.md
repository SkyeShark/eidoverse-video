# Desert

[Props and sets guide](../../../../tools-guides/props-and-sets.md#the-desert) · [Sources and licences](SOURCES.md) · [How it was made](../desert_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

The desert round the town, out to 32.8 km, as the Blender edition makes it
(`eidoblend.sets.desert`, branch `blender`): a basin floor rising out of the
town's plane, a braided wadi and its tributaries, star dunes, an escarpment
with its outliers, inselbergs and ranges drowned in their own alluvium, tracks
going on from the town's, and low scrub on the sand it caught.
[`eidoverse/sets/desert/`](../../../sets/desert/index.js) loads it and draws
its look in TSL.

| File | Contents |
| --- | --- |
| `desert_A.glb` (2.7 MB) | The land within 2,048 m of the town's middle, in 16 tiles of 1,024 m: 551,536 vertices and 1,094,016 triangles, the cells 2 m round the town and along the line the lenses fly. |
| `desert_B.glb` (12.5 MB) | The ring out to 8,192 m, in tiles of 4,096 m: 1,786,160 vertices and 3,559,744 triangles (the dunes and the escarpment, finest on crests and rims). |
| `desert_C.glb` (0.9 MB) | The ring out to the edge at 32,768 m, in tiles of 16,384 m: 167,856 vertices and 329,984 triangles, the cells to 256 m. |
| `desert_scrub.glb` (0.2 MB) | Four shrubs (their twigs, and the mound of sand each caught) placed 5,657 times by `EXT_mesh_gpu_instancing`, each place with its own number (`_RND`). |
| `near_marks.png`, `mid_marks.png` | What is finer than the mesh, 4096² each: at 1 m over ±2,048 m and at 4 m over ±8,192 m, north up. R the tracks, G the wadi beds (0.6) and their bars (up to 1), B the floor's drainage lines, A the sand sheet. |
| `desert.json` | The manifest: the rings and their tiles, the quantization, the masks' scales, the Blender edition's lenses on the desert, and what the chain was run with. |

Every vertex of the land has its normal (Blender's, over the whole mesh, so the
tiles meet without a seam) and the land's eight masks in two attributes, each
0..1 of its scale in the manifest: `_DMA` (16-bit: the distance from the town,
to 5 km; the sand's depth; the escarpment's and the ranges' heights) and
`_DMB` (8-bit: the sand sheet, the wadi bed, the bars' and the aprons'
heights). The positions are in the town's metres with +Z up, under a root node
turned to glTF's +Y up, and quantized one way for every tile
(`KHR_mesh_quantization`, the tile node's scale and translation): x and y in
2 m steps, which is exact, since every vertex of the quadtree lies on that
grid; z in 1/128 m steps. The quads are split along their first diagonal, as
Blender draws them. The GLBs are packed with `EXT_meshopt_compression` (120 MB
unpacked), which keeps every number as the export wrote it.

## Use

```js
// In setup()
const DESERT = await import(new URL('sets/desert/index.js', EIDOVERSE_DIR).href);
const desert = await DESERT.build(THREE, { renderer });     // its own GLTFLoader with three's MeshoptDecoder
scene.add(desert.group);                                    // the town's metres: put it with the town's group, unscaled
```

To read a GLB with a loader of your own, give it the decoder:
`loader.setMeshoptDecoder(MeshoptDecoder)` from
`npm:three@0.184.0/addons/libs/meshopt_decoder.module.js`; each tile's node
carries its scale and translation. The worked example is
[`eidoverse/examples/desert/`](../../../examples/desert/scene.js).
