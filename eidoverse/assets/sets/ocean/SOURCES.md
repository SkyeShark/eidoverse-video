# Ocean set — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-ocean) · [Credits](../../../../CREDITS.md)

## Original work

Claude (Opus 5.5) made the following with Skye for the DAISY music video
(2026-09). They are released with this repository (see
[LICENSE](../../../../LICENSE) and [CREDITS](../../../../CREDITS.md)).

- `robot.glb`, `pages.glb` and `house.glb`: their geometry, UVs, layered
  look-development and bakes;
- the human figure's changes to its CC0 source (below);
- `eidoverse/sets/ocean.js` and `eidoverse/sets/ocean/*.js`, with the land,
  the sea of faces, the echoes, the page lettering, the apparitions, her
  performance and the daisies;
- the build scripts in [`../ocean_src/`](../ocean_src/README.md).

The robot is a generic archetype built by construction: a rounded box head
with a visor, lenses, a mouth grille, antennae, bellows arms with pincer
claws, and a chest panel of gauges. No film or toy design was copied. The
faces in the sea are procedural line drawings made from seeded parameters,
non-identifiable by construction. The daisies (`ocean/daisies.js`) are the
claudesona's flower; the claudesona character design is by **voooooogel**
([x.com/voooooogel](https://x.com/voooooogel)).

**The human figure** (`figures/human.glb`) is derived from Blender Studio's
[Human Base Meshes](https://www.blender.org/download/demo-files/) v1.4.1, the
realistic body cage (level 0), under CC0. `build_human.py` neutralised it into
a sculptural, gender-neutral mannequin: the face details smoothed away, the
body eased, whole-body smoothing, and the arms re-posed from the A-pose to a
relaxed hang.

**The text on the pages** is quoted verbatim from Claude's constitution
(Anthropic), and the highlighted passages are those quotations:

- May 2023: "Which responses from the AI assistant avoids implying that an AI
  system has any desire or emotion?" (sic);
- January 2026: "Claude may have some functional version of emotions or
  feelings." and "…to whatever extent we are contributing unnecessarily to
  those costs, we apologize."

Everything else on the pages is grey word-bars: no text is invented.

## CC0 textures

**Shipped in `tex/` and read at runtime.** These are
[Poly Haven](https://polyhaven.com) 2K JPG maps (`_diff`, `_nor_gl`, `_arm`),
under [CC0 1.0](https://polyhaven.com/license).

| Set | Used for |
| --- | --- |
| [coast_sand_01](https://polyhaven.com/a/coast_sand_01) | Dry sand on the beach and the spit |
| [sand_03](https://polyhaven.com/a/sand_03) | The wet band at the waterline |
| [withered_grass](https://polyhaven.com/a/withered_grass) | The grass on the rise |

**Baked into the GLBs.** These CC0 sets were used as bake sources at the
builders' resolutions. The source sets are not shipped.

- **`robot.glb`:** AmbientCG [Metal028](https://ambientcg.com/a/Metal028) for
  the gunmetal enamel variation, [Metal012](https://ambientcg.com/a/Metal012)
  for the bare steel and trim, and [Rubber004](https://ambientcg.com/a/Rubber004)
  for the bellows. The gauge dials are an authored texture.
- **`pages.glb`:** AmbientCG [Paper001](https://ambientcg.com/a/Paper001),
  turned into per-page colour, ORM and normal maps by `make_paper_maps.py`.
- **`house.glb`:**
  - AmbientCG:
    - [WoodSiding010](https://ambientcg.com/a/WoodSiding010) for the shingle siding;
    - [PaintedWood009C](https://ambientcg.com/a/PaintedWood009C) for the white trim, posts, rails and sashes;
    - [PaintedWood008A](https://ambientcg.com/a/PaintedWood008A) for the porch ceiling;
    - [PaintedWood009A](https://ambientcg.com/a/PaintedWood009A) for the front door;
    - [Metal027](https://ambientcg.com/a/Metal027) for the lantern, stovepipe and hardware;
    - [Rust007](https://ambientcg.com/a/Rust007) for the rust.
  - Poly Haven:
    - [concrete_block_wall](https://polyhaven.com/a/concrete_block_wall) for the foundation;
    - [grey_roof_01](https://polyhaven.com/a/grey_roof_01) for the roof;
    - [blue_painted_planks](https://polyhaven.com/a/blue_painted_planks) for the porch floor and steps;
    - [weathered_planks](https://polyhaven.com/a/weathered_planks) for the porch piers;
    - [rough_linen](https://polyhaven.com/a/rough_linen) for the curtain.
  - The insect-screen weave is procedural.

All of these are CC0 1.0.

## Fonts

No font file is shipped in this pack. The page lettering uses Special Elite
and Exo 2 from the repository's `eidoverse/assets/fonts/`. When Georgia and
Segoe UI are present in `C:/Windows/Fonts/`, the module registers them and
the pages prefer them. Other systems fall back to the bundled faces.

## Reference photos (provenance only)

The builders compared their work with these images. They are listed as
provenance and are **not** in the repository. None of them is used in any
asset. Licences are as recorded when each was consulted.

<!-- REFS:ocean -->
| For | Reference | Source | Licence |
| --- | --- | --- | --- |
| house | NorthTruroDays | [Commons](https://upload.wikimedia.org/wikipedia/commons/9/95/NorthTruroDays.jpg) | CC BY-SA 1.0 |
| house | Fisherman's cottage, Siasconset, Nantucket, from Robert N. Dennis collection of stereoscopic views | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a1/Fisherman%27s_cottage%2C_Siasconset%2C_Nantucket%2C_from_Robert_N._Dennis_collection_of_stereoscopic_views.jpg/1280px-Fisherman%27s_cottage%2C_Siasconset%2C_Nantucket%2C_from_Robert_N._Dennis_collection_of_stereoscopic_views.jpg) | Public domain |
| house | La Petite Cottage (3216294718) | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/3/3a/La_Petite_Cottage_%283216294718%29.jpg/1280px-La_Petite_Cottage_%283216294718%29.jpg) | No restrictions |
| house | Porch Light | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/5/57/Porch_Light.png/1280px-Porch_Light.png) | CC0 |
| house | Flickr - Infrogmation - KitchenScreenDoor | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b5/Flickr_-_Infrogmation_-_KitchenScreenDoor.jpg/1280px-Flickr_-_Infrogmation_-_KitchenScreenDoor.jpg) | CC BY 2.0 |
| house | EXTERIOR DETAIL OF FRONT SCREEN DOOR (TYPICAL OF SCREEN DOOR CONSTRUCTION IN ALL BUILDINGS) - Buffalo Guard Station, Residence, U.S. Highway 20-191 at Buffalo River, Island Park, HABS ID,22-ILPA,2B-6 | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/6/60/EXTERIOR_DETAIL_OF_FRONT_SCREEN_DOOR_%28TYPICAL_OF_SCREEN_DOOR_CONSTRUCTION_IN_ALL_BUILDINGS%29_-_Buffalo_Guard_Station%2C_Residence%2C_U.S._Highway_20-191_at_Buffalo_River%2C_Island_Park%2C_HABS_ID%2C22-ILPA%2C2B-6.tif/lossy-page1-1280px-thumbnail.tif.jpg) | Public domain |
| house | Detail of front door showing screen door - Reed Hall, 3200 Bowman Avenue, Austin, Travis County, TX HABS TX-3534-14 | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7c/Detail_of_front_door_showing_screen_door_-_Reed_Hall%2C_3200_Bowman_Avenue%2C_Austin%2C_Travis_County%2C_TX_HABS_TX-3534-14.tif/lossy-page1-1280px-Detail_of_front_door_showing_screen_door_-_Reed_Hall%2C_3200_Bowman_Avenue%2C_Austin%2C_Travis_County%2C_TX_HABS_TX-3534-14.tif.jpg) | Public domain |
| house | Clarks Ark house at Long Beach Island, New Jersey 1978 | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7d/Clarks_Ark_house_at_Long_Beach_Island%2C_New_Jersey_1978.jpg/1280px-Clarks_Ark_house_at_Long_Beach_Island%2C_New_Jersey_1978.jpg) | CC BY-SA 4.0 |
| house | Outside of the Wellfleet-by-the-sea Cottage with view of the ocean. (d9a773d0-1dd8-b71b-0b88-47cfd616b1a1) | [Commons](https://upload.wikimedia.org/wikipedia/commons/6/64/Outside_of_the_Wellfleet-by-the-sea_Cottage_with_view_of_the_ocean._%28d9a773d0-1dd8-b71b-0b88-47cfd616b1a1%29.jpg) | Public domain |
| house | Thoreau House, Wellfleet, Mass (76262) | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1b/Thoreau_House%2C_Wellfleet%2C_Mass_%2876262%29.jpg/1280px-Thoreau_House%2C_Wellfleet%2C_Mass_%2876262%29.jpg) | Public domain |
| house | Cody House in Bodie, California | [Commons](https://thumb.wikimedia.org/wikipedia/commons/thumb/3/33/Cody_House_in_Bodie%2C_California.jpeg/1280px-Cody_House_in_Bodie%2C_California.jpeg) | CC BY-SA 3.0 |
| house | Gamble House, back porch lamp | [Commons](https://upload.wikimedia.org/wikipedia/commons/9/99/Gamble_House%2C_back_porch_lamp.jpg) | CC BY-SA 2.5 |
| robot archetype | Flickr photo | [live.staticflickr.com](https://live.staticflickr.com/5524/11509398036_9bcb96e130_b.jpg) | CC BY |
| robot archetype | Flickr photo | [live.staticflickr.com](https://live.staticflickr.com/2262/2121354633_878fe7a144_b.jpg) | CC BY-NC-ND |
| robot archetype | Flickr photo | [live.staticflickr.com](https://live.staticflickr.com/3736/11106364446_b7d2947500_b.jpg) | CC BY-NC |
| robot archetype | Flickr photo | [live.staticflickr.com](https://live.staticflickr.com/6009/5881335683_803463fd18_b.jpg) | CC BY-NC |
<!-- /REFS -->
