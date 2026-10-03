# UNKNOWN FORCE sets — sources and licences

[Set index](README.md) · [Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Shared texture library](../../../AGENTS.md) · [Credits](../../../CREDITS.md)

## Original work

Claude (Opus 5.5) and its subagents made the following with Skye for the UNKNOWN FORCE music video (2026-10). They
are released with this repository (see [LICENSE](../../../LICENSE) and [CREDITS](../../../CREDITS.md)).

- the fourteen modules in this folder: every mesh they
  build (the city, the hole, the two interiors, the corridor, the data centre, the race with its car and riders, the
  paper canyon), their TSL materials, and everything they draw at runtime: the signs and ads, the whiteboards, the
  essay, the ENGINE sheet, the toaster's WARNING, the poll board, the post card, the AI FORCE patch, the picket signs,
  the CLANKER tag, the chyron, the billboards' machine-god face, the manifesto page, the march atlas and the 24
  pages of the bin.

All text on the sets is invented, or quoted from public-domain sources (below). No real person, logo, seal, insignia,
account handle or masthead is reproduced; the pickets and the marching column are featureless silhouettes.

## CC0 textures (fetched, not shipped)

All from [AmbientCG](https://ambientcg.com), [CC0 1.0](https://docs.ambientcg.com/license/). None is committed: each
set names the IDs it reads, and the shared texture library fetches each once (`fetchPBR`, which runs
`fetch_texture.py <ID> <res> --cache` into `eidoverse/assets/cache/textures/`). The sets load only the maps they name
(colour, normal and roughness, plus the ambient occlusion, metalness or displacement noted below). Each set is at
`https://ambientcg.com/view?id=<ID>`.

### The city and the hole (1K)

| ID | Used for |
| --- | --- |
| Asphalt025C | the wet streets |
| Concrete031 | concrete towers, podiums, the hole's terrace risers |
| MetalPlates013 | metal and glass towers, frames, fins, lift shafts |
| PavingStones128 | sidewalks and block slabs |
| Marble016 | the hole's floor, terraces and stairs (black marble) |

### The quiet room and the showroom (1K; ambient occlusion for Carpet012, Carpet013 and CorrugatedSteel005)

| ID | Used for |
| --- | --- |
| Carpet012 | the quiet room's carpet tiles (desaturated to charcoal, quarter-turned 0.5 m tiles); the showroom's auditorium carpet |
| Carpet013 | the quiet room's aisle runner (deep red, with a painted brass and black binding) |
| Fabric031 | office-chair upholstery, ceiling felt and baffles, theatre-seat fabric |
| Chipboard004 | the shipping crate's OSB panels |
| Wood096 | the crate's pine battens and pallet |
| Wood027 | the walnut lectern |
| Terrazzo003 | the quiet room's black terrazzo dais |
| Terrazzo005 | the showroom's white-grey stage |
| Concrete017 | the quiet room's core wall |
| Metal009 | brushed aluminium (board frames, nosing, turntable drum, truss, conveyor rollers) |
| Metal027 | black powder-coated steel (diagrid, mullions, conveyor rails, fixtures) |
| CorrugatedSteel005 | the hatch's roller shutter |

### The corridor (metalness for the four metals)

| ID | Res | Used for |
| --- | --- | --- |
| Marble016 | 2K | black marble with white veins, recoloured to gold veins in the shader |
| Metal042A | 1K | polished, lightly hammered gold (pilasters, frames, ribs) |
| Metal048B | 1K | gold with fingerprints (trim, plaque, braid, badge) |
| Metal048C | 1K | impure rough gold (the door leaves) |
| Metal008 | 1K | scratched bronze (door recesses, skirting) |
| Fabric023 | 1K | cut pile (the red runner, the velvet cushion, the sash; recoloured) |
| Fabric077 | 1K | twill (the uniform and the cap's crown; recoloured navy) |

### The evening news

| ID | Res | Used for |
| --- | --- | --- |
| Asphalt025C | 2K | wet asphalt, the yard and the road (with its ambient occlusion); its displacement map places the puddles |
| Gravel041 | 1K | gravel (the verge, the transformer yard), with its ambient occlusion |
| Cardboard002 | 1K | corrugated cardboard (the picket signs) |

### Shared with the DAISY sets

The same library IDs the DAISY funeral and corner read:

| ID | Res | Set | Used for |
| --- | --- | --- | --- |
| PaintedMetal012 | 1K | corridor, news | black lacquer (the ceiling coffers, the poll board, the patent visor); the news' housings, transformers and van (with its ambient occlusion) |
| Wood066 | 1K | corridor | the tailor's stand |
| Concrete048 | 1K | news | the monolith's precast panels (with its ambient occlusion) |
| Concrete033 | 1K | news | weathered concrete (with its ambient occlusion) |
| Concrete034 | 2K | news | light concrete |
| Metal049A | 1K | news | galvanised steel: fence, poles, gantry (with its metalness) |
| CorrugatedSteel009 | 2K | news | the cooling towers (with its ambient occlusion) |
| Asphalt012 | 1K | news | house roofs |
| Ground037, Ground106 | 2K | news | lawns and mud (with their ambient occlusion) |
| PaintedWood009C | 2K | news | house siding (with its ambient occlusion) |

## CC0 model (fetched, not shipped)

| Model | What | Source | Licence |
| --- | --- | --- | --- |
| `metal_trash_can` (2K) | "Metal Trash Can" by GurJas Studios: two ribbed metal cans (clean and rusted), lids, handles, 2K PBR maps embedded | [Poly Haven](https://polyhaven.com/a/metal_trash_can), fetched by the model library (`fetchModelFile`, which runs `fetch_model.py metal_trash_can --cache --res 2k`) | [CC0 1.0](https://polyhaven.com/license); the fetcher writes `metal_trash_can_embedded.license.json` beside it |

## From the model library

The DAISY funeral's four featureless crowd figures, `eidoverse/assets/models/funeral_crowd.glb` with
`eidoverse/assets/sets/funeral/crowd_rig.json`, instanced as the pickets: original work, see
[funeral SOURCES](../../assets/sets/funeral/SOURCES.md).

## Fonts

No font file is in this folder. The sets use the kit's bundled fonts in `eidoverse/assets/fonts/` (SIL Open Font
License), among them the nine faces added with `eidoverse/parole.js` (their `OFL-*.txt` licences beside them; the bin
sets its pages in them). Some lettering asks for Windows system faces, used at render time and not redistributed:
Impact and Arial Black (the race's amounts; fallback Rajdhani), Georgia (the essay, the radiator number, the
manifesto page; fallback Special Elite or a serif).

## Text from public-domain sources

- The race's manifesto page: F. T. Marinetti, "Fondazione e Manifesto del Futurismo" (1909), the title and points 1,
  2, 4 and 9 in the Italian of *I Manifesti del futurismo* (Florence, 1914), checked against it.wikisource.
- The city's Futurist supergraphics are single Futurist words (VELOCITÀ, DINAMISMO, SIMULTANEITÀ …), the film's
  title in Italian (FORZA IGNOTA) and the titles of public-domain Futurist works: *Uccidiamo il chiaro di luna!*
  (1909), *Parole in libertà* (1912–19) and *Zang Tumb Tumb* (1914).

## The race

No third-party asset: `race.js` loads no mesh, texture, scan or image file. The viaduct, towers, billboards, car,
riders, boot, roadworks and crane are geometry built at runtime; the materials are TSL; the canvas art is drawn in
code. The billboards' amounts, `$100,000,000` and `$20,000,000`, name no organisation; the machine-god face is an
original drawing of no real person. The car is a 1908 Grand Prix pattern, not a copy of any one machine, and carries
no maker's badge.

## Reference and influence only (not in this repository)

Tullio Crali's aeropittura (*Incuneandosi nell'abitato*, 1939, © the estate) for the dive; Sant'Elia's *Città Nuova*
for the towers; Balla's *Street Light* and *Mercury Passing Before the Sun*; Carrà's *Interventionist Demonstration*
(1914) for the bin's cut wedge and disc of words; the 1907 Fiat 130 HP and the 1908 Itala Grand Prix cars (Wikimedia
Commons photographs), Russolo's *Dinamismo di un'automobile* (1913) and Balla's *Velocità astratta + rumore* (1913–14)
for the race.
