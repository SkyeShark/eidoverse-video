# Helicopter — how it was made

[Pack README](../helicopter/README.md) · [Sources](../helicopter/SOURCES.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-helicopter)

The helicopter is made by the Blender edition (branch `blender`), whose
`eidoblend.props.helicopter` builds it from one measured datum: the high, its
vertex masks (the arrises' and corners' nearness, the openness, measured by
rays after every part is cut to short edges), its drawn pictures and its
materials. These scripts take the made asset into this library.

| File | Role |
| --- | --- |
| `export_glb.py` | Blender, headless: `helicopter.blend`'s collection as `helicopter_raw.glb` (the modifiers applied, the masks as `_MASKS`, the blades' data as `_BLADE`, the rotor Empties, the materials by role with their base colours) and the pictures beside it. `--mask-caps` looks the made high again with other cut lengths, for a lighter file with the same parts. |
| `pack_glb.mjs` | Deno with glTF-Transform and meshoptimizer: normals to 8 bits, the masks to 8-bit unsigned normalized, vertices reordered for the GPU's cache, every stream compressed with `EXT_meshopt_compression`; positions stay float32 in the asset's metres, which the materials read. The houseplants are packed by the same script. |

## Rebuild

In a checkout of the Blender edition, from its root (about three minutes):

```bash
python blender/eidoblend/props/helicopter/make.py --out work/props/helicopter        # helicopter.blend, decals/
bash run_blender.sh <this repo>/eidoverse/assets/models/helicopter_src/export_glb.py \
    --blend work/props/helicopter/helicopter.blend --decals work/props/helicopter/decals \
    --out work/props/helicopter/web
```

Then, from this repository's root:

```bash
deno run -A --no-lock eidoverse/assets/models/helicopter_src/pack_glb.mjs <web>/helicopter_raw.glb \
    eidoverse/assets/models/helicopter/helicopter.glb --unit _MASKS,_BLADE
cp <web>/skin_side.png <web>/marks_left.png <web>/marks_right.png <web>/decals.json eidoverse/assets/models/helicopter/
```

The packed file is 19.8 MB (82 MB raw); the packing is deterministic. With
`--mask-caps 0.12,0.08,0.03` the same 290 parts come out at 1.10 M triangles,
9.3 MB packed, their wear coarser.
