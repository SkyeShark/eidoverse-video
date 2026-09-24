# The corner and the march (DAISY bridge, bars 18–29)

[Props and sets guide](../../../../tools-guides/props-and-sets.md#the-corner) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../corner_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

The runtime files of [`eidoverse/sets/corner.js`](../../../sets/corner.js). The
set is the second half of the DAISY bridge: how people kept Claude 3 Opus, and
how they marched when a model was taken offline. It has two areas, and each is
closed on its own:

- **Claude's Corner.** A walnut writing desk by a night window, a brass lamp,
  a notebook the pen writes in, a laptop that opens after midnight, a wall
  clock and pinned pages.
- **The camp.** Tents, string lights, a campfire, SeedThree woods and marchers
  with hand-painted signs, under the set's own night-sky dome.

The module loads everything from this folder, resolved from its own URL.

| Path | Contents | Size |
| --- | --- | --- |
| `glb/corner_*.glb` | The room: `desk`, `window`, `curtain`, `chair`, `rug`, `books`, `mug`, `lamp`, `notebook`, `pen`, `laptop` (the lid is a separate node), `clock` (the hands are separate nodes) and `pages`. Each is Blender-built with its layered look baked in. | 44.8 MB |
| `glb/camp_*.glb` | The camp: `tent_dome_{orange,green,mustard}` (with a baked lantern-glow map), `pole`, `bulb`, `fire` (a stone ring, charred logs and an ash bed with baked emissive coals), `bench`, `marchers` (four rigged-by-attribute marcher bodies, instanced on the GPU) and `sign` (a corrugated board taped to a lath stick; the painted front comes from the art atlas). | 43.9 MB |
| `tex/<ID>/` | AmbientCG 2K sets that the module tiles itself: `PaintedPlaster017` (walls), `WoodFloor064` (floor), `PaintedWood009C` (the skirting board) and `Ground037` with `Ground106` (the camp ground and its path). Each has `_Color`, `_NormalGL` and `_Roughness`, plus `_AmbientOcclusion` where the set has one. `Paper001` ships only its colour map, the notebook paper. | 78.9 MB |
| `art/sign_art_{color,normal,orm}_pot.jpg` | The painted-sign atlas: 8 signs in 4 × 2 cells, resampled to 2048 × 1024. | 1.7 MB |

The folder is 169.2 MB. The module picks each map in `tex/<ID>/` by its
suffix (`_color.jpg`, `_normalgl.jpg`, `_roughness.jpg`,
`_ambientocclusion.jpg`, ignoring case). A file it cannot find is logged as
`[corner] missing texture` or `not built yet — skipped`, and the set renders
without it.

The set also uses shared engine assets: the Kalam and Exo 2 fonts from
`eidoverse/assets/fonts/`, flame, spark and smoke sprites from
`eidoverse/assets/particle_textures/`, `createFlora` grass and, when the
optional SeedThree backend is installed, `makeSeedTree` trees.

## Use

See the [props and sets guide](../../../../tools-guides/props-and-sets.md#the-corner)
for the conductor contract, the beat map, costs and limitations. In short:

```js
const corner = await (await import(new URL('sets/corner.js', EIDOVERSE_DIR).href)).build({ THREE, EIDOVERSE_DIR });
corner.group.position.set(800, 0, 800);      // park it away from other sets
scene.add(corner.group);
// per frame: u = seconds since the bridge began (bars 18–29 = u 33.75–56.25 at 128 BPM)
corner.update(t, { u, bar: Math.floor(u / 1.875), BAR: 1.875, caption, kick, pulse });
const m = corner.markAt(u), c = corner.camera(u);   // set-local: add corner.group.position
```

## Provenance

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09).
[SOURCES](SOURCES.md) lists the CC0 scans, the fonts and the story sources of
the sign slogans. The Blender and PIL scripts that built the GLBs and the sign
atlas are in [`../corner_src/`](../corner_src/README.md).
