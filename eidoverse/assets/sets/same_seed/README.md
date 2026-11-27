# The SAME SEED rooms

[Props and sets guide](../../../../docs/props-and-sets.md#the-same-seed-rooms) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../same_seed_src/README.md) · [Main instructions](../../../../AGENTS.md)

The runtime files of [`eidoverse/sets/same_seed.js`](../../../sets/same_seed.js): the
four rooms of the SAME SEED music video, made in Blender on the Blender edition
(branch `blender`, `eidoblend.sets.same_seed`) and written out for this edition
by [`same_seed_src/export_room.py`](../same_seed_src/README.md).

```js
const SS = await import(new URL('sets/same_seed.js', EIDOVERSE_DIR).href);
const room = await SS.build('kitchen', { THREE });
scene.add(room.group);
room.applyTo(scene, renderer);
room.camera('wide', camera);
```

Per room (`sealed_room/`, `kitchen/`, `lab/`, `desk/`):

| File | Contents |
| --- | --- |
| `room.json` | Its cameras and marks (metres, +Y up), its render settings (AgX and the exposure), its lights as three.js lights (with EEVEE's reach), the bounce grid (L1 spherical harmonics per cell, x fastest, then y, then z), the reflection probe's place and harmonics, the Poly Haven models it places (ID, resolution, mesh index, matrix) and the emissions its look changed on them, and the lists of its GLBs. |
| `materials.json` | The node graph of every material on the rest of the room (and the world's), with the pictures they read: CC0 sets by ID, HDRIs by ID, or the room's own prints. |
| `prints/` | The pictures the room's builder drew (worksheets, a notebook, a clock face, a notice, a screen, the whiteboard's ghosts, the poster), read by its materials. |
| `reflection.hdr` | The reflection probe's panorama (Cycles, at the probe), the reflections of the room's own materials (the kitchen, the lab and the desk room; the sealed room has no probes, as in Blender). |

The models are in the model library, `eidoverse/assets/models/`:

| File | Contents |
| --- | --- |
| `same_seed_<room>_<atlas>.glb` | The lows of one atlas, their look baked by Cycles at the atlas's size: base colour, ORM (occlusion, roughness, metalness) and a tangent-space normal (with the tangents it was baked against); emission and alpha where a part glows or is cut out. Normals and tangents are int8 (`KHR_mesh_quantization`). |
| `same_seed_<room>_rest.glb` | Every other part of the room, each at its place, its material slots by name (`extras.graph`: the graph in `materials.json`; `extras.cc0`: a Poly Haven model's own material, for the two models the desk room's look changed, kept here as changed) and every UV map by name as `_uv_<name>` (Blender's own UVs; the first map is `TEXCOORD_0` only, its name in the mesh's `extras.uv0`), with `_tangent_<uv>` where a normal map reads it, `_orco` (Generated coordinates) and `_attr_<name>` (colour attributes) where a graph reads them. |

The CC0 photographs, the Poly Haven models and the HDRIs are not here: the
module names their IDs and the shared library fetches each once
(`fetchPBR`, `fetchModelFile`, and `fetchHDRIFile` from the module), about
650 MB for the four rooms.
