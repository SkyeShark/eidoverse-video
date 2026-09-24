# The ocean of faces (DAISY verse 3)

[Props and sets guide](../../../../tools-guides/props-and-sets.md#the-ocean) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../ocean_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

The runtime files of [`eidoverse/sets/ocean.js`](../../../sets/ocean.js) and
its submodules in [`eidoverse/sets/ocean/`](../../../sets/ocean/). The
claudesona stands on a small rise at the tip of a headland at night. Below her
the swells of the sea are made of faces, surfacing and sinking with each
two-bar swell. Echoes of older voices hang over the water. Two constitution
pages drift past, from 2023 and 2026. A movie robot and a human made of light
rise from the sea and dissolve. Across the cove, a small house on a sand spit
turns its porch light on at "on".

| Path | Contents | Size |
| --- | --- | --- |
| `figures/robot.glb` | A generic 1950s science-fiction robot archetype, 2.2 m to the antenna tips. The layered look is baked to one 2K atlas (colour, ORM, normal); its lenses and lamps are emission-ready. | 13.5 MB |
| `figures/human.glb` | A neutral, sculptural human figure (1.75 m, geometry only). The module turns it into points of light sampled from its surface, with a faint fresnel shell. | 1.7 MB |
| `figures/pages.glb` | Two curled US Letter sheets, `page_2023` and `page_2026`, bent isometrically. Their paper maps are embedded; the words are drawn on them at runtime. | 7.5 MB |
| `house/house.glb` | The beach cottage: shingle siding, a broken-pitch roof, a porch with a screen door, one window and a lantern. Baked per object into colour, normal and ORM maps. | 21.8 MB |
| `tex/sand/`, `tex/grass/` | Poly Haven 2K maps for the land: `coast_sand_01` and `sand_03` (the beach and the wet edge) and `withered_grass` (the rise). Each has `_diff`, `_nor_gl` and `_arm`. | 36.0 MB |

The folder is 80.5 MB. The sea of faces, the echoes, the dune grass and the
daisies are generated in code. The faces are procedural line drawings, and
the daisies come from `ocean/daisies.js`, the film's instanced daisy field,
which is shipped with the set. The pages use the Special Elite and Exo 2
fonts from `eidoverse/assets/fonts/`. When Georgia and Segoe UI are installed
in `C:/Windows/Fonts/`, the pages use them first.

## Use

The set is open to the engine sky: `SKY.hours` puts the moon low over the
open sea, and the whole layout is rotated to meet it. See the
[guide](../../../../tools-guides/props-and-sets.md#the-ocean).

```js
const O = await import(new URL('sets/ocean.js', EIDOVERSE_DIR).href);
const ocean = await O.build({ THREE, EIDOVERSE_DIR });
scene.add(ocean.group);
// per frame (u = seconds since verse 3 began, 0–33.75):
sky.setTime(ocean.SKY.hours); sky.update(t);     // makeSky from eidoverse/sky_worlds.js; keep the sun off
ocean.update(t, { u, bar: Math.floor(u / 1.875), BAR: 1.875, caption, kick, pulse });
const m = ocean.markAt(u); /* place the VRM */ const c = ocean.camera(u); /* place the camera */
ocean.perform(u, vrm, camera.position);          // after placing her, before the render
```

## Provenance

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09).
The human figure derives from Blender Studio's CC0 Human Base Meshes. The
[sources](SOURCES.md) list every CC0 input and the page quotations. The
Blender scripts are in [`../ocean_src/`](../ocean_src/README.md).
