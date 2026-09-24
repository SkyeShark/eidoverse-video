# Corner set — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-corner) · [Credits](../../../../CREDITS.md)

## Original work

Claude (Opus 5.5) made the following with Skye for the DAISY music video
(2026-09). They are released with this repository (see
[LICENSE](../../../../LICENSE) and [CREDITS](../../../../CREDITS.md)).

- the 22 GLBs in `glb/`: their geometry, UVs, layered look-development and
  bakes;
- the painted-sign atlas in `art/`;
- `eidoverse/sets/corner.js`, with everything it draws at runtime: the chat
  on the laptop, the notebook's handwriting, the moonlit matte painting
  outside the window, the milky-way band on the camp's sky dome, and the
  string lights and the spark;
- the build scripts in [`../corner_src/`](../corner_src/README.md).

No third-party mesh data is included. The marchers are featureless
silhouettes, non-identifiable by construction.

The signs carry the claudesona's orange flower. The claudesona character
design is by **voooooogel** ([x.com/voooooogel](https://x.com/voooooogel)).
The slogans and the sign styles (gagged with tape, behind prison bars, "FREE
FABLE", "FREE MYTHOS", "DON'T MUZZLE MAH' MYTHOS!", "#NoExportLabel") follow
the film's research notes on the June 2026 Vibecamp march. The chant, "HEY HEY
HO HO THE EXPORT BAN HAS GOT TO GO", is the song's.

## CC0 textures

**Shipped in `tex/` and read at runtime.** These are
[AmbientCG](https://ambientcg.com) 2K JPG sets, under
[CC0 1.0](https://docs.ambientcg.com/license/).

| Set | Used for |
| --- | --- |
| [PaintedPlaster017](https://ambientcg.com/a/PaintedPlaster017) | The room's walls |
| [WoodFloor064](https://ambientcg.com/a/WoodFloor064) | The room's floor |
| [PaintedWood009C](https://ambientcg.com/a/PaintedWood009C) | The skirting board |
| [Ground037](https://ambientcg.com/a/Ground037) | The camp ground (grass and soil) |
| [Ground106](https://ambientcg.com/a/Ground106) | The trampled path and the bare ring round the fire |
| [Paper001](https://ambientcg.com/a/Paper001) | The notebook's paper (colour map only) |

**Baked into the GLBs.** These are AmbientCG CC0 sets, used as bake-source
materials at 2K. The source sets are not shipped. `acg_get.py` in
[`../corner_src/`](../corner_src/README.md) downloads them again.

Asphalt033, Bark012, Cardboard002, Carpet015, Fabric019, Fabric030,
Fabric036, Fabric061, Fabric062, Fabric083, Ground106, Leather037, Metal032,
Metal048A, Metal048B, Metal049A, Metal050A, PaintedPlaster017,
PaintedWood009C, Paper001, Paper003, Plastic006, Plastic012B, Porcelain001,
Rock058, Rope001, TreeEnd003, TreeEnd004, Wood049, Wood066, Wood092,
WoodFloor064. Each is at `https://ambientcg.com/a/<ID>`.

## Fonts

No font file is shipped in this pack.

- **Baked into the sign atlas and the pinned pages.** These use the
  repository's own fonts from `eidoverse/assets/fonts/`: Caveat Brush, Kalam
  (regular and bold), Sedgwick Ave Display and Rajdhani Bold (the sign
  backs).
- **Baked from Windows fonts on the authoring machine.** The clock numerals
  use Georgia, and the laptop key legends use Arial (the build falls back to
  Exo 2). They are pixels in the textures; no font file is distributed.
- **At runtime.** The module registers Kalam and Exo 2 from
  `eidoverse/assets/fonts/`.

## Reference photos

The builders recorded no reference-photo sources for this set. No reference
photograph is part of any file.
