# Corner set — build scripts

[Pack README](../corner/README.md) · [Sources](../corner/SOURCES.md) · [Blender guide](../../../../tools-guides/blender.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-corner)

The scripts that built `glb/*.glb` and the sign atlas in
[`../corner/`](../corner/README.md). They are copied as they were run for the
DAISY film, and the rebuild from this folder has not been re-run since the
copy. Each Blender build models its asset at real scale, in metres, with its
front facing Blender −Y (+Z in the engine). It then gives the asset two UV
maps: `TexUV`, a world-scaled projection that the layered AmbientCG material
samples, and `BakeUV`, a packed atlas. It bakes colour, ORM and normal onto
`BakeUV` and exports a GLB that carries only the baked maps. Objects that the
module drives with its own material keep a plain role material and are
exported unbaked: `SCREEN`, `PAGE`, `SHADE`, `BULB` and `GLASS`.

| File | Role |
| --- | --- |
| `blender/clib.py` | The shared kit: scene reset, Cycles bake settings (GPU, OptiX), UV and bake helpers, GLB export and preview sheets. |
| `blender/props_util.py`, `blender/helpers_wcl.py` | Helpers for the room props, and for the window, curtain and laptop builds. |
| `blender/camp_lib.py`, `blender/camp_logs.py` | Helpers for the camp: tents, bulb, pole, fire and bench, plus log geometry with bark, end-grain and split faces. |
| `blender/build_<asset>.py` | One GLB each: `bench`, `books`, `bulb`, `chair`, `clock`, `curtain`, `desk`, `fire`, `lamp`, `laptop`, `marchers`, `mug`, `notebook`, `pages`, `pen`, `pole`, `rug`, `sign`, `tent_dome` (all three colours) and `window`. Some write their own art first, for example `clock` writes `art/clock_dial.png`. |
| `art/paint_signs.py` | System Python with numpy, Pillow and SciPy. Paints the eight protest signs as layers: card, poster paint, marker, duct tape, lettering. Writes `art/sign_art_{color,normal,orm}.jpg` at 2048 × 768, and `_hi` versions at 4096 × 1536. |
| `art/paint_sign_back.py` | System Python with Pillow. Writes `art/sign_back_print.png`, the shipping-box print on the sign backs. |
| `acg_get.py` | Downloads AmbientCG sets into `tex/<ID>/`, keeping their zip names (`<ID>_2K-JPG_<Map>.jpg`), which are the names the module and the builds look for. |

## Rebuild

The scripts resolve paths relative to the folder they sit in: `blender/..` is
their root, with `tex/`, `glb/`, `art/`, `baked/` and `previews/` under it.
That root was the DAISY film's `work/daisy/sets/corner_assets/`. Recreate it
under `work/`, which git ignores, and run from the repository root:

```bash
mkdir -p work/daisy/sets/corner_assets
cp -r eidoverse/assets/sets/corner_src/. work/daisy/sets/corner_assets/
cd work/daisy/sets/corner_assets
python acg_get.py 2K Asphalt033 Bark012 Cardboard002 Carpet015 Fabric019 Fabric030 Fabric036 Fabric061 \
  Fabric062 Fabric083 Ground037 Ground106 Leather037 Metal032 Metal048A Metal048B Metal049A Metal050A \
  PaintedPlaster017 PaintedWood009C Paper001 Paper003 Plastic006 Plastic012B Porcelain001 Rock058 Rope001 \
  TreeEnd003 TreeEnd004 Wood049 Wood066 Wood092 WoodFloor064
python art/paint_signs.py && python art/paint_sign_back.py
cd ../../../..
bash run_blender.sh work/daisy/sets/corner_assets/blender/build_sign.py      # one asset -> glb/camp_sign.glb
```

- Build the signs' art before `build_sign.py`, which reads
  `art/sign_art_color.jpg` and `art/sign_back_print.png`.
- The module reads a power-of-two copy of the sign atlas. No script makes it,
  so resample each of the three maps to 2048 × 1024. The atlas UVs are
  relative, so a plain resize keeps the cells:
  ```bash
  python -c "from PIL import Image; import sys; [Image.open(f'art/sign_art_{k}.jpg').resize((2048, 1024), Image.LANCZOS).save(f'art/sign_art_{k}_pot.jpg', quality=92) for k in ('color', 'normal', 'orm')]"
  ```
  Run it from `work/daisy/sets/corner_assets/`, then copy the three `_pot`
  files into `eidoverse/assets/sets/corner/art/`.
- Copy the rebuilt GLBs into `eidoverse/assets/sets/corner/glb/`.
- `run_blender.sh` is the repository's isolated headless runner (see the
  [Blender guide](../../../../tools-guides/blender.md)). The run line in
  `clib.py`'s docstring is the bare Blender command it was first written with.
  Do not use it.
- The bakes run Cycles on the GPU (OptiX), so wait for any render to finish
  first. The clock numerals and the laptop legends use `georgia.ttf` and
  `arial.ttf` from `C:/Windows/Fonts`. The lettering uses the repository's
  fonts in `eidoverse/assets/fonts/`.
- Check a rebuild with the library check scene
  ([guide](../../../../tools-guides/props-and-sets.md#verify)).

## Credits

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09).
See [SOURCES](../corner/SOURCES.md) and [CREDITS](../../../../CREDITS.md).
