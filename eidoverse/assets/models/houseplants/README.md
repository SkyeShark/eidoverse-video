# Houseplants

[Props and sets guide](../../../../docs/props-and-sets.md#the-houseplants) · [Sources and licences](SOURCES.md) · [How they were made](../houseplants_src/README.md)

Four houseplants and a watering can, each grown as it grows, made for the SAME
SEED film's lab and kitchen. [`eidoverse/props/houseplants.js`](../../../props/houseplants.js)
loads them and makes their materials in TSL.

| File | Contents |
| --- | --- |
| `rubber_plant.glb` (1.3 MB) | Ficus elastica in a glazed stoneware pot with its nursery liner: 5 parts, 131,586 triangles; 1.6 m tall, the pot 0.32 m across. |
| `monstera.glb` (2.0 MB) | Monstera deliciosa on its coir pole, tied, in terracotta on a saucer: 7 parts, 184,420 triangles; 1.2 m tall, the pot 0.3 m across. |
| `corn_plant.glb` (1.8 MB) | Dracaena fragrans 'Massangeana', three canes in a fibre-clay planter on expanded-clay pebbles: 6 parts, 192,644 triangles; 1.85 m tall, the planter 0.4 m across. |
| `basil.glb` (0.6 MB) | Sweet basil in a 9 cm clay pot on its saucer: 5 parts, 62,726 triangles; 0.25 m tall. |
| `watering_can.glb` (0.06 MB) | A yellow plastic watering can: 7,252 triangles; 0.41 m long, 0.26 m high. |

Each plant stands on y = 0 at its pot's centre and faces +Z, in metres. The
leaves are thin closed solids carrying their own data as vertex attributes:
`_LEAFDATA` (along the blade 0..1, across it 0..1 with the midrib at 0.5, which
leaf, how old; the underside's age is below zero) and, on the Monstera,
`_LEAFQ` (where a point lies across its vein's field, 0 on the vein). The parts
keep their builders' names (`plant_monstera_leaves`, `plant_monstera_pole`,
...), which choose their materials. Packed with `EXT_meshopt_compression`.

## Use

```js
// In setup()
const HP = await import(new URL('props/houseplants.js', EIDOVERSE_DIR).href);
const library = await HP.library(THREE);                       // share the CC0 sets between plants
const plant = await HP.build(THREE, 'monstera', { library });  // or rubber_plant, corn_plant, basil, watering_can, coir_pole
scene.add(plant.group);
```

The worked example is [`eidoverse/examples/houseplants/`](../../../examples/houseplants/scene.js).
