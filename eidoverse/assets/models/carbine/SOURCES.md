# Carbine — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-carbine)

## Original work

Every file in this folder was made for this repository and is released with it
(see [LICENSE](../../../../LICENSE)): the geometry of the high and the low, the
UVs, the GPU bakes, the drawn markings and the layered look. They are made by the
Blender edition's `eidoblend.props.carbine` (branch `blender`) and exported by
the scripts in [`../carbine_src/`](../carbine_src/README.md). No third-party
mesh or image data is included. The design is the M4A1 pattern as the type's
published dimensions give it; it carries function markings only, no maker's
mark, no serial.

## CC0 photographs read at run time (not shipped)

The material reads these [ambientCG](https://ambientcg.com) sets
([CC0 1.0](https://docs.ambientcg.com/license/)), box-projected at their real
size on the carbine. They are fetched once into `eidoverse/assets/cache/` by
`fetchPBR` (or `python fetch_texture.py <ID> <res> --cache`) and never
committed.

| Set | Map | Used for |
| --- | --- | --- |
| Metal027 (2k) | colour, roughness | the hard anodise's satin grain |
| Metal063 (2k) | colour, roughness | the phosphate's finer crystal |
| Plastic013A (2k) | roughness | the moulded polymer's smudged roughness |
| Fingerprints008 (2k) | opacity | fingerprints where hands go |
| Metal021 (2k) | displacement | the outline of a chip |
| Metal008 (1k) | roughness | fine scratches |
