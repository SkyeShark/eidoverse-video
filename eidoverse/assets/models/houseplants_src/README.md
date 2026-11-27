# Houseplants — how they were made

[Pack README](../houseplants/README.md) · [Sources](../houseplants/SOURCES.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-houseplants)

The plants are grown by the Blender edition (branch `blender`), whose
`eidoblend.props.houseplants` builds each species from its own tables: blades
as thin closed solids carrying their data, petioles, canes, the coir pole and
its ties, the soil, the pots and the watering can. `export_glb.py` grows each
species alone at the origin and writes it as a GLB; the helicopter's
[`pack_glb.mjs`](../helicopter_src/pack_glb.mjs) packs it.

## Rebuild

In a checkout of the Blender edition, from its root (under a minute):

```bash
bash run_blender.sh <this repo>/eidoverse/assets/models/houseplants_src/export_glb.py --out work/props/houseplants/web
```

Then, from this repository's root, for each species:

```bash
deno run -A --no-lock eidoverse/assets/models/helicopter_src/pack_glb.mjs <web>/monstera.glb eidoverse/assets/models/houseplants/monstera.glb
```

The leaf data stays float32 (its underside flag is below zero), so no `--unit`
attribute is named. The plants grown in a group in the Blender edition
(`build_group`) clear each other's blades; these are each grown alone.
