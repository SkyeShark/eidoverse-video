# Carbine — how it was made

[Pack README](../carbine/README.md) · [Sources](../carbine/SOURCES.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-carbine)

The carbine is made by the Blender edition (branch `blender`), whose
`eidoblend.props.carbine` builds it from nothing: the high from the type's
measured tables, the low from the same tables, the low's UVs, the GPU bake
(`blender/tools/gpu_bake.py`, NVIDIA Warp) and the layered look. These scripts
take the made asset into this library.

| File | Role |
| --- | --- |
| `export_glb.py` | Blender, headless: `carbine.blend`'s collection as `carbine.glb` (tangents, one UV set, the materials by name), the bake's maps beside it, and `carbine_layered.json` (the look's tables from `eidoblend.props.carbine.look`, the photographs' means as Blender reads them). |
| `compress_maps.py` | Plain Python with Pillow: every PNG in the folder stored again losslessly at the best zlib level, its pixels checked unchanged. |

## Rebuild

In a checkout of the Blender edition, from its root (about 15 minutes, most of
it the UV pack; the bake needs `pip install warp-lang` and runs on the CPU
without CUDA):

```bash
python blender/eidoblend/props/carbine/make.py --out work/props/carbine            # carbine.blend, bake/
bash run_blender.sh <this repo>/eidoverse/assets/models/carbine_src/export_glb.py \
    --blend work/props/carbine/carbine.blend --bake work/props/carbine/bake --out work/props/carbine/web
python <this repo>/eidoverse/assets/models/carbine_src/compress_maps.py work/props/carbine/web
cp work/props/carbine/web/* <this repo>/eidoverse/assets/models/carbine/
```

`export_glb.py` reads the look's six CC0 photographs through the edition's
library (fetched once; `EIDO_ASSET_CACHE` reads an existing one) to record
their means. `make.py --condition wear=..,dust=..` changes only the Blender
look; this library's condition is `build(THREE, { condition })`.
