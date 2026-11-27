# Desert — how it was made

[Pack README](../desert/README.md) · [Sources](../desert/SOURCES.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-desert)

The desert is made by the Blender edition (branch `blender`), whose
`eidoblend.sets.desert` composes it from the terrain family's simulations by a
chain of steps into a work folder: `sources` (three terrain recipes in
Blender: star dunes, mesas and buttes, a fluvial range), `mask` (the town's
footprint and its tracks' ends), `land` (the land composed in three nested
rasters, and the marks finer than the mesh), `mesh` (a crack-free quadtree
mesh and the scrub's places). Its `look` step only builds the Blender
collection; this library takes the chain's output from the `mesh` step on.
These scripts do that.

| File | Role |
| --- | --- |
| `export_desert.py` | Plain Python with numpy and Pillow: the work folder's mesh as three GLBs, one a ring round the town in square tiles (the quads split as Blender draws them, Blender's angle-weighted normals over the whole mesh, the land's eight masks as 16- and 8-bit vertex attributes, positions quantized one way for every tile so the tiles meet exactly); the scrub as one GLB of four shrubs placed by `EXT_mesh_gpu_instancing` (the shrubs and their numbers drawn as the Blender look draws them, numpy's generator seeded 41); the two marks pictures re-stored losslessly; and `desert.json`, with the lenses the Blender look finds in the land. |
| `pack_glb.mjs` | Deno with glTF-Transform and meshoptimizer: each raw GLB's vertices reordered for the GPU's cache and every stream compressed with `EXT_meshopt_compression`, which keeps every number as it is; the rest copied beside them. |

## Rebuild

In a checkout of the Blender edition, from its root (about 4 minutes on a
laptop GPU; the `mask` step builds the town once, and fetches the town's CC0
sets into the shared library the first time):

```bash
python blender/eidoblend/sets/desert/make.py --work work/desert --to mesh        # sources, mask, land, mesh
```

Then, from this repository's root, with a Python that has numpy and Pillow
(about 10 s, and half a minute to pack):

```bash
python eidoverse/assets/models/desert_src/export_desert.py --work <blender checkout>/work/desert --out work/desert_web
deno run -A --no-lock eidoverse/assets/models/desert_src/pack_glb.mjs work/desert_web eidoverse/assets/models/desert
```

The chain is deterministic: run with its defaults it makes this library's
desert again, 2,493,312 vertices and 5,657 shrubs (two runs gave the same
vertex, face and shrub counts, the same rasters' height ranges and the same
close looks).
`make.py`'s own options make another: `--town WxH` (the desert round a town
of another extent) or `--plain WxH` (round a plain rectangle and no town),
`--quality draft` (4, 16 and 64 m rasters, 8 m cells). Where the dunes, the
escarpment, the inselbergs and the tracks stand is `land.PLAN` in the Blender
edition. The exporter quantizes x and y in 2 m steps, exact on the
quadtree's grid at `mesh.py`'s film and draft levels (2 m and 8 m cells); it
stops with a message on a finer mesh (`--max-level 11`). Packed, the default
desert is 16.3 MB of GLBs (120 MB raw) and 3.3 MB of marks;
`eidoverse/sets/desert/desert_test.mjs` checks the files against their
manifest and the default desert's numbers.
