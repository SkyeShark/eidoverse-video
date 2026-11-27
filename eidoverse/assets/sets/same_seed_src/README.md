# The SAME SEED rooms — how the files were made

[Pack README](../same_seed/README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-same-seed-rooms) · [Blender guide](../../../../tools-guides/blender.md)

The rooms are made in Blender by the Blender edition of this repository (branch
`blender`), then written out for this edition by `export_room.py`, run in Blender
over the made room. Nothing here is needed at run time.

| File | What it does |
| --- | --- |
| `export_room.py` | Blender script: one made room as this edition's files (its steps below). |
| `glb.py` | A small binary glTF 2.0 writer (numpy only) the export writes its GLBs with. |

## Make a room, then export it

On a checkout of the `blender` branch (Blender 4.2 or newer; the GPU bake wants
`warp-lang`):

```bash
python blender/eidoblend/sets/same_seed/make.py kitchen --out <made>/kitchen
```

Then, from this edition's checkout, with the Blender edition's `blender/` folder
and the shared CC0 library the room was made with:

```bash
blender --background --factory-startup <made>/kitchen/kitchen.blend \
    --python eidoverse/assets/sets/same_seed_src/export_room.py -- \
    --room kitchen --made <made>/kitchen --eidoblend <blender checkout>/blender \
    --cache <the library the room was made with: eidoverse/assets/cache> \
    --out eidoverse/assets/sets/same_seed/kitchen --models eidoverse/assets/models
```

`--steps` picks what is written (all four by default, `rest,lows,light,meta`):

- **rest**: every part that is not a low as `same_seed_<room>_rest.glb` (its
  transform, its material slots by name, every UV map by name, the first as
  `TEXCOORD_0` only, the tangents a normal map reads, Generated coordinates and
  colour attributes where a graph reads them) and every material's node graph,
  with the world's, as
  `materials.json` (groups flattened, reroutes and muted nodes passed through,
  each picture referred to by its CC0 ID, its HDRI ID or the room's print, which
  is copied to `prints/`). A Poly Haven part the room changed (a mesh edited,
  a material replaced) is written here too, its own materials still read from
  the model by ID. Every corner keeps the normal Blender shades it with (an
  n-gon is cut into triangles for its tangents, and a custom normal, a
  Weighted Normal modifier's, is carried across the cut), and the faces where
  two parts touch (a gasket on its bead, a pane on its gasket, a skirting on
  the floor) are each drawn 0.25 mm back into their own part, so three's depth
  test does not fight along the edge where one ends on the other.
- **lows**: the parts with UV `atlas`, one GLB per atlas, their look baked by
  Cycles at the atlas's size (`--max-size`, default 4096): base colour, ORM (the
  GPU bake's occlusion, roughness, metalness), a tangent-space normal (OpenGL,
  against the MikkTSpace tangents the GLB carries), and emission and alpha where
  a material glows or is cut out; each bake sees only the atlas's parts. JPEG at
  `--quality` (88; the normal 6 higher).
- **light**: every light as its three.js light (a sun's W/m² as a
  `DirectionalLight`, an area light's power over π w h as a `RectAreaLight`, a
  spot's or point's power over 4π) with the reach EEVEE gives it (its custom
  distance, or where its power falls under the scene's light threshold), the
  bounce of the room's volume probe as a grid of L2 spherical harmonics (twice
  the probe's resolution, `--grid-scale`, at most `--grid-max` cells; at each
  cell a Cycles panorama, `--grid-res` wide, of everything but the lamps, the
  probe's hidden parts left out and every "Is Camera Ray" read as 0; cells
  inside a solid or shut in a pocket take their neighbours'), and the reflection
  probe's panorama (`reflection.hdr`, `--reflection` 1024x512, Cycles with
  denoising).
- **meta**: `room.json`: cameras and marks (from the room's Blender module; a
  mark's yaw about +Y, 0 facing +Z, and its "facing" said in three's axes),
  render settings, the Poly Haven models placed (found by their mesh's bounds in
  the model's glTF) and the emissions the room's look changed on them.

Blender's (x, y, z) is three's (x, z, −y) throughout; a mesh keeps its vertices
in its own space, so a graph's Object coordinates mean what they meant.
Cycles runs on the GPU (OptiX, then CUDA) when it can.

The four rooms took about 40 minutes to export on an RTX 5090 Laptop GPU, most
of it the 4096 bakes.
