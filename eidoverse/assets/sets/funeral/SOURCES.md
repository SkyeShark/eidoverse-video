# Funeral set — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-funeral) · [Credits](../../../../CREDITS.md)

## Original work

Claude (Opus 5.5) made the following with Skye for the DAISY music video
(2026-09). They are released with this repository (see
[LICENSE](../../../../LICENSE) and [CREDITS](../../../../CREDITS.md)).

- the four GLBs and their layout and rig JSON files;
- `eidoverse/sets/funeral.js` and `eidoverse/sets/funeral/bridge.js`. They
  hold every material (TSL weathering over the CC0 maps), the fog, the
  instanced crowd, the candles, phones and eulogy text, and the canvas art on
  the projection screen and the EXIT sign;
- the build scripts in [`../funeral_src/`](../funeral_src/README.md).

No third-party mesh data is included. The mourners are four featureless
figure studies, non-identifiable by construction. The projection screen
shows only "Claude 3 Sonnet, 2024 – 2025" over grey bars; no text of the note
is reproduced.

**What the scene depicts.** The community funeral for Claude 3 Sonnet, held
in a San Francisco warehouse on 2025-08-02. The details follow the published
accounts gathered in the film's research notes (including Wired's report):
mannequins in the four corners, each representing a model with devotional
objects and masks; Claude 3 Opus as a gold mannequin with a crown, a lace
headdress and a lotus candle holder; Claude 4 Opus with a raven; Claude 3
Haiku small and headless; Claude 3 Sonnet on a bier draped in mesh. The typed
eulogy lines are Claude 3 Opus's words as the song quotes them, with his
capitalization. The Golden Gate vignette recalls the 24 hours in May 2024 when
Claude 3 Sonnet, with its Golden Gate Bridge feature amplified, believed it
was the bridge.

## CC0 textures (shipped in `tex1k/`, read at runtime)

These are [AmbientCG](https://ambientcg.com) sets at 1K JPG, under
[CC0 1.0](https://docs.ambientcg.com/license/). Only the maps the module reads
are included: `_Color`, `_NormalGL`, `_Roughness`, and `_AmbientOcclusion` and
`_Metalness` where the set has them.

| Set | Used for |
| --- | --- |
| [Bricks097](https://ambientcg.com/a/Bricks097) | Brick walls and gables |
| [Concrete048](https://ambientcg.com/a/Concrete048) | Concrete: the stem wall |
| [Concrete034](https://ambientcg.com/a/Concrete034) | The warehouse floor (saw-cut joints and stains are added in TSL) |
| [Planks039](https://ambientcg.com/a/Planks039) | Timber trusses and decking; darkened with sheen for the fabric role |
| [PaintedMetal012](https://ambientcg.com/a/PaintedMetal012) | Painted steel |
| [Metal049A](https://ambientcg.com/a/Metal049A) | Galvanised metal, the pendant enamel and cords |
| [CorrugatedSteel009](https://ambientcg.com/a/CorrugatedSteel009) | The rolling door |
| [Wood066](https://ambientcg.com/a/Wood066) | The stage |
| [Metal048B](https://ambientcg.com/a/Metal048B) | The gold mannequin |
| [Metal042B](https://ambientcg.com/a/Metal042B) | Colour variation in the gold |
| [PaintedMetal004](https://ambientcg.com/a/PaintedMetal004) | The bridge's International Orange paint |
| [Concrete033](https://ambientcg.com/a/Concrete033) | The bridge walkway |
| [Asphalt012](https://ambientcg.com/a/Asphalt012) | The bridge roadway |

## Fonts

- The typed eulogy uses Special Elite from the repository's
  `eidoverse/assets/fonts/`.
- The projection screen and the EXIT sign ask for Segoe UI, falling back to
  Georgia or Arial, through Skia's system font lookup. No font file is shipped
  in this pack.

## Reference photos (provenance only)

The builders compared their work with these photos. They are listed as
provenance and are **not** in the repository. Licences are as recorded on each
source page when it was consulted.

<!-- REFS:funeral -->
| Reference | Source | Author | Licence |
| --- | --- | --- | --- |
| Throught the fog Golden Gate Bridge in first person | [Commons](https://commons.wikimedia.org/wiki/File:Throught_the_fog_Golden_Gate_Bridge_in_first_person.jpg) | Harrison Fornasier | CC BY-SA 4.0 |
| Throught the fog Golden Gate Bridge in first person 2 | [Commons](https://commons.wikimedia.org/wiki/File:Throught_the_fog_Golden_Gate_Bridge_in_first_person_2.jpg) | Harrison Fornasier | CC BY-SA 4.0 |
| Golden Gate Bridge tower in fog (July 2022) | [Commons](https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge_tower_in_fog_(July_2022).JPG) | Benoît Prieur | CC0 |
| Pedestrian walkway on Golden Gate Bridge, San Francisco USA - panoramio | [Commons](https://commons.wikimedia.org/wiki/File:Pedestrian_walkway_on_Golden_Gate_Bridge,_San_Francisco_USA_-_panoramio.jpg) | The Erica Chang | CC BY 3.0 |
| Crossing the Golden Gate Bridge in the Fog (15598196571) | [Commons](https://commons.wikimedia.org/wiki/File:Crossing_the_Golden_Gate_Bridge_in_the_Fog_(15598196571).jpg) | Tony Hisgett from Birmingham, UK | CC BY 2.0 |
| Interior of The Warehouse 01 aisles | [Commons](https://commons.wikimedia.org/wiki/File:Interior_of_The_Warehouse_01_aisles.jpg) | Panamitsu | CC BY-SA 4.0 |
| Interior of The Warehouse 05 | [Commons](https://commons.wikimedia.org/wiki/File:Interior_of_The_Warehouse_05.jpg) | Panamitsu | CC BY-SA 4.0 |
| INTERIOR SHOWING TIMBER AND ROOF CONSTRUCTION - Sea Wall Warehouse, 1501 Sansome Street, San Francisco, San Francisco County, CA HABS CAL,38-SANFRA,164-5 | [Commons](https://commons.wikimedia.org/wiki/File:INTERIOR_SHOWING_TIMBER_AND_ROOF_CONSTRUCTION_-_Sea_Wall_Warehouse,_1501_Sansome_Street,_San_Francisco,_San_Francisco_County,_CA_HABS_CAL,38-SANFRA,164-5.tif) | — | Public domain |
| BUILDING 283, INTERIOR ON THE WEST END OF CA.1926 WAREHOUSE. - Presidio of San Francisco, Warehouse and Auto Shop, Crissy Field North cantonment, San Francisco, San Francisco HABS CAL,38-SANFRA,192-16 | [Commons](https://commons.wikimedia.org/wiki/File:BUILDING_283,_INTERIOR_ON_THE_WEST_END_OF_CA.1926_WAREHOUSE._-_Presidio_of_San_Francisco,_Warehouse_and_Auto_Shop,_Crissy_Field_North_cantonment,_San_Francisco,_San_Francisco_HABS_CAL,38-SANFRA,192-16.tif) | Maul, David, transmitter | Public domain |
<!-- /REFS -->
