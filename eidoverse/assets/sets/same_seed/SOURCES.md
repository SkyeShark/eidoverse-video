# The SAME SEED rooms — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-same-seed-rooms) · [Credits](../../../../CREDITS.md)

## Original work

Released with this repository (see [LICENSE](../../../../LICENSE)):

- the rooms themselves, as the Blender edition builds them (`eidoblend.sets.same_seed` on the `blender` branch): their
  geometry, UVs, materials, lights and cameras;
- the GLBs `same_seed_*.glb` in `eidoverse/assets/models/`, and each room's `room.json`, `materials.json` and
  `reflection.hdr`;
- the pictures in each room's `prints/`, drawn by the Blender edition's builders with the repository's OFL fonts
  (the kitchen's `garden_view.png` is cut from Poly Haven's CC0 `suburban_garden`, and its `notebook.png` cover
  marbled from ambientCG's CC0 `Marble016`);
- `eidoverse/sets/same_seed.js` and `eidoverse/sets/same_seed/`, and the export in
  [`../same_seed_src/`](../same_seed_src/README.md).

## CC0 photographs, models and HDRIs

All CC0 1.0: [Poly Haven](https://polyhaven.com/license) and [ambientCG](https://docs.ambientcg.com/license/).

**Fetched by ID, never shipped.** The rooms name the IDs they read and the
[shared library](../../../../tools-guides/assets.md#the-shared-library--library-code-names-ids-never-commits-them)
fetches each once into `eidoverse/assets/cache/` (`fetchPBR`, `fetchModelFile`; the HDRIs through `fetch_hdri.py`),
each with its licence file beside it:

| Room | Texture sets (2K unless marked) | Poly Haven models (1K unless marked) | HDRI (4K) |
| --- | --- | --- | --- |
| `sealed_room` | Poly Haven concrete_block_wall, linoleum_brown; ambientCG Metal038, Paint004, PaintedPlaster017, Rubber004 | metal_stool_02, mounted_fluorescent_lights, security_camera_02 | none |
| `kitchen` | Poly Haven coated_pine, floor_tiles_08, gingham_check; ambientCG Fabric039 (1K), Fabric062, Fingerprints002, Fingerprints008, Granite005A, Metal009, Paint004, PaintedPlaster017, Paper001, Plastic013A, Rubber004 | bananas, food_apple_01, food_pears_asian_01, wooden_bowl_01, wooden_cutting_board | suburban_garden (the garden through the window) |
| `lab` | Poly Haven linoleum_brown; ambientCG Cardboard002 (1K), Clay005, Concrete017 (1K), Fabric034, Fabric062, Fingerprints002, Fingerprints008, Granite005A, Ground048, Metal009, Paint004, PaintedPlaster017, Paper001, Plaster001, Plastic013A, Rubber004 | office_notepads, stationery_supplies, wall_clock | pretoria_gardens (the park and the sky) |
| `desk` | Poly Haven book_pattern, oak_wood_planks, rough_linen, white_maple_veneer; ambientCG Carpet016, Fabric023 (1K), Fabric034, Fingerprints002, Fingerprints008, Granite005A, Metal009, Paint004, PaintedPlaster017, Paper001, Plaster001, Plastic013A, Rubber004 | book_encyclopedia_set_01, boombox, desk_lamp_arm_01 (2K), dining_chair_02, potted_plant_02, potted_plant_04, standing_picture_frame_01, stationery_supplies, steel_frame_shelves_01, steel_frame_shelves_02, wall_clock; and the materials of hanging_picture_frame_01 and modern_ceiling_lamp_01 | hansaplatz (the square at night) |

**Shipped, as the rooms changed them.** The desk room's `same_seed_desk_rest.glb` carries the meshes of two Poly
Haven models as its look changed them: `hanging_picture_frame_01` (a UV map added so the poster lies on its board) and
`modern_ceiling_lamp_01` (hung shorter); their materials still load by ID.

**Baked in.** The lows' looks were baked by Cycles over CC0 sets, so those photographs are in the GLBs' base colour,
ORM and normal maps: sets from the table above, and these, which only the bakes read: in the sealed room ambientCG
Metal009, Metal021, Metal027 and PaintedMetal014; in the desk room Poly Haven lacquered_cherry_wood, oak_veneer_01
and rosewood_veneer1, and ambientCG Fabric039, Leather037 and Metal038.
