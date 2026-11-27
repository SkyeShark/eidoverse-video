# Helicopter — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-helicopter)

## Original work

Every file in this folder was made for this repository and is released with it
(see [LICENSE](../../../../LICENSE)): the measured high, its vertex masks, the
drawn rivets, seams, fasteners and stencils, and the look. They are made by the
Blender edition's `eidoblend.props.helicopter` (branch `blender`) and exported
and packed by the scripts in [`../helicopter_src/`](../helicopter_src/README.md).
The stencils are set in the repository's Archivo Black (OFL). No third-party
mesh or image data is included, and nothing is read from a third party at run
time. The design follows the UH-60 pattern as the type's published dimensions
give it; it carries function stencils only, no service title, no serial and no
unit's mark.

The packing step uses [glTF-Transform](https://gltf-transform.dev) (MIT) and
[meshoptimizer](https://github.com/zeux/meshoptimizer) (MIT), fetched from npm
when the script runs; neither is shipped. three's MeshoptDecoder, which reads
the file, is part of three.js (MIT).
