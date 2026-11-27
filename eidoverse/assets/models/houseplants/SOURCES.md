# Houseplants — sources and licences

[Pack README](README.md) · [Props and sets guide](../../../../docs/props-and-sets.md#the-houseplants)

## Original work

Every file in this folder was made for this repository and is released with it
(see [LICENSE](../../../../LICENSE)): the plants grown in code (blades, petioles,
canes, the coir pole and its ties, the soil, the pots, the pebbles, the
watering can) and their leaf data. They are made by the Blender edition's
`eidoblend.props.houseplants` (branch `blender`) and exported and packed by the
scripts in [`../houseplants_src/`](../houseplants_src/README.md). No
third-party mesh or image data is included.

## CC0 sets read at run time (not shipped)

The pots, the soil, the canes' bark, the coir and the plastic read these sets,
box-projected at their real size. They are fetched once into
`eidoverse/assets/cache/` by `fetchPBR` (or
`python fetch_texture.py <ID> <res> --cache`) and never committed. All are CC0
1.0: [ambientCG](https://docs.ambientcg.com/license/) and
[Poly Haven](https://polyhaven.com/license).

| Set | Maps | Used for |
| --- | --- | --- |
| ambientCG Clay005 (2k) | colour, roughness, displacement | the terracotta pot and saucer, the expanded-clay pebbles |
| ambientCG Ground048 (2k) | colour, roughness, displacement | the potting mix; the corn plant's bark; the coir's fibre |
| ambientCG Granite005A (2k) | colour | the glazed pot's speckle |
| ambientCG Fingerprints002 (2k) | colour | the glazed pot's fingerprints |
| ambientCG Concrete017 (1k) | colour, roughness, displacement | the fibre-clay planter |
| ambientCG Plastic013A (2k) | roughness, displacement | the nursery liner, the ties, the watering can |
| Poly Haven floor_tiles_08 (2k) | colour, roughness, displacement | the basil's clay pot and saucer |
