# Desert — sources and licences

[Pack README](README.md) · [Main instructions, "The desert"](../../../../AGENTS.md)

## Original work

Every file in this folder was made for this repository and is released with it
(see [LICENSE](../../../../LICENSE)): the land, its masks, the marks finer than
the mesh, the shrubs and their places. They are made by the Blender edition's
`eidoblend.sets.desert` (branch `blender`), which composes the land from the
terrain family's own simulations (`eidoblend.terrain`: star dunes by Werner
transport, mesas and buttes by caprock retreat, a fluvial range by stream
power, each run from its seed), and exported and packed by the scripts in
[`../desert_src/`](../desert_src/README.md). No third-party mesh, elevation or
image data is included.

The packing step uses [glTF-Transform](https://gltf-transform.dev) (MIT) and
[meshoptimizer](https://github.com/zeux/meshoptimizer) (MIT), fetched from npm
when the script runs; neither is shipped. three's MeshoptDecoder, which reads
the files, is part of three.js (MIT).

## CC0 sets read at run time (not shipped)

The ground's look reads these sets at their real size. They are fetched once
into `eidoverse/assets/cache/` by `fetchPBR` (or
`python fetch_texture.py <ID> <res> --cache`) and never committed. All are CC0
1.0: [ambientCG](https://docs.ambientcg.com/license/) and
[Poly Haven](https://polyhaven.com/license). The first five are the town's
(`eidoverse/sets/town/cc0_sets.json`), the rest the desert's own
(`eidoverse/sets/desert/cc0_sets.json`).

| Set | Maps | Used for |
| --- | --- | --- |
| Poly Haven coast_sand_01 (2k) | colour | the town's plain: sand with grit |
| Poly Haven dry_ground_01 (2k) | colour | the town's plain in patches; the floor's drainage lines |
| Poly Haven rock_ground_02 (2k) | colour | the town's plain in patches; the tracks; the far floor's varnished gravel |
| Poly Haven withered_grass (2k) | colour | the town's plain at its scrub |
| Poly Haven mud_cracked_dry_03 (2k) | colour | pale silt where the sheet floods dried |
| Poly Haven rocks_ground_02 (2k) | colour | desert pavement |
| Poly Haven sandy_gravel_02 (2k) | colour | the wadis' bars, the aprons' fans |
| Poly Haven gravelly_sand (2k) | colour | the wadi beds |
| ambientCG Ground093B (2k) | colour | the sand sheet, the dunes' slip faces |
| ambientCG Ground100 (2k) | colour, displacement | the dunes' windward ripples |
| Poly Haven rock_face_03 (2k) | colour, displacement | the escarpment's cliff band and the ranges' rock |
| Poly Haven marble_cliff_02 (2k) | colour | the cliff band's other beds |
| Poly Haven rocks_ground_06 (2k) | colour | the talus under the cliffs |
| Poly Haven worn_rock_natural_01 (2k) | colour | the plateau's caprock |
| ambientCG Gravel024 (2k) | colour | the ranges' debris |
| ambientCG Rock031 (2k) | colour | the inselbergs' and the ranges' dark rock |
