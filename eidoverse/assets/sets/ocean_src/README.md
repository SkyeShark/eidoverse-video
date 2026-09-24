# Ocean set — build scripts

[Pack README](../ocean/README.md) · [Sources](../ocean/SOURCES.md) · [Blender guide](../../../../tools-guides/blender.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md#the-ocean)

The scripts that built the GLBs in [`../ocean/`](../ocean/README.md). They
are copied unchanged from the DAISY film, and the rebuild from this folder has
not been re-run since the copy. The folder mirrors the film's
`work/daisy/sets/ocean_assets/` layout: `figures/scripts/` and `house/`.

| File | Role |
| --- | --- |
| `figures/scripts/build_robot.py` | Models the robot archetype as face-modelled masses and writes `<out>/wip/robot_clay.blend` (and a clay GLB). `-- <out_dir> [clay\|final]` |
| `figures/scripts/build_robot_final.py` | Opens `wip/robot_clay.blend`, layers the looks, bakes them to one 2K atlas on the CPU (AO, base colour, roughness, metallic and normal, packed as ORM), and writes `robot.blend` and `robot.glb`. `-- <figures_dir>` |
| `figures/scripts/reexport_robot.py` | Run with `robot.blend` open. Marks the closed solids single-sided and re-exports `robot.glb`. `-- <out_dir>` |
| `figures/scripts/build_human.py` | Run with Blender Studio's Human Base Meshes bundle `.blend` open (v1.4.1, CC0). Neutralises the realistic body cage into a sculptural mannequin and re-poses the arms, then writes `<tag>.blend` and `.glb`. `-- <out_dir> [female\|male] [tag]` |
| `figures/scripts/reexport_human.py` | Run with the human `.blend` open. Names the mesh `human` and re-exports `human.glb`. `-- <out_dir>` |
| `figures/scripts/make_paper_maps.py` | System Python with numpy and Pillow. Makes the per-page paper maps from AmbientCG Paper001 in `../tex/Paper001/` and writes them to `../tex/pages/`: `page_2023_color.jpg`, `page_2026_color.jpg`, `paper_orm.jpg` and `paper_normal.png`, at 1536 × 2048. |
| `figures/scripts/build_pages.py` | Bends the two US Letter sheets isometrically, applies the `tex/pages/` maps, and writes `pages.blend` and `pages.glb`. `-- <out_dir>` |
| `house/build_house.py` | Models the cottage and its layered source materials, and writes `house_src.blend`. `-- [--render neutral\|night\|lamp\|all] [--quick]` |
| `house/house_mats.py` | The house's layered source materials: a library PBR base, then AO grime, rain streaks, splash, salt, edge wear, rust and lichen. `texset()` finds maps in `tex/<ID>/` by name. |
| `house/bake_export.py` | Opens `house_src.blend`, bakes each object to colour, normal and ORM on the CPU, and exports `house.glb`. `-- [--samples 24] [--scale 1.0] [--only name]` |

## Rebuild

Recreate the layout under `work/`, which git ignores, so a rebuild never
writes into the library:

```bash
mkdir -p work/daisy/sets/ocean_assets
cp -r eidoverse/assets/sets/ocean_src/. work/daisy/sets/ocean_assets/
```

**Inputs.** None of these ship with the library.

- AmbientCG sets, fetched with `python fetch_texture.py <ID> 2k` from inside
  each target folder:
  - `figures/tex/Metal028/`, `Metal012/` and `Rubber004/` for the robot;
  - `figures/tex/Paper001/` for the pages;
  - `house/tex/<ID>/` for the house: WoodSiding010, PaintedWood009C,
    PaintedWood008A, PaintedWood009A, Metal027 and Rust007.
- Poly Haven 2K maps, downloaded into `house/tex/<id>/`: concrete_block_wall,
  grey_roof_01, blue_painted_planks, weathered_planks and rough_linen.
  `fetch_texture.py <id> 2k` prints their CDN links; `texset()` accepts the
  standard `<id>_diff_2k.jpg` names.
- The robot's painted dial, `figures/tex/robot/dial_face.png`. It is an
  authored texture that no script here makes, and it is not in the library.
- The Human Base Meshes bundle from
  [blender.org's demo files](https://www.blender.org/download/demo-files/).

**Running.** Run the scripts that need no open `.blend` from the repository
root with the isolated runner, for example:

```bash
bash run_blender.sh work/daisy/sets/ocean_assets/house/build_house.py
bash run_blender.sh work/daisy/sets/ocean_assets/house/bake_export.py --samples 24
python work/daisy/sets/ocean_assets/figures/scripts/make_paper_maps.py
bash run_blender.sh work/daisy/sets/ocean_assets/figures/scripts/build_pages.py work/daisy/sets/ocean_assets/figures
```

`run_blender.sh` cannot open a `.blend` before the script. For
`build_human.py` and the two `reexport_*.py` scripts, start Blender yourself
with the same sandbox the runner uses:

```bash
BLENDER_USER_RESOURCES="${TMP:-/tmp}/blender_user_isolated" "$BLENDER" --background --factory-startup \
  path/to/robot.blend --python work/daisy/sets/ocean_assets/figures/scripts/reexport_robot.py -- work/daisy/sets/ocean_assets/figures
```

Never run `--factory-startup` against your real Blender user folder: it
deletes your installed extensions' Python packages (see the
[Blender guide](../../../../tools-guides/blender.md)). Copy the finished GLBs
into `eidoverse/assets/sets/ocean/figures/` and `…/house/`, then check them
with the library check scene
([guide](../../../../tools-guides/props-and-sets.md#verify)).

## Credits

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09). The
human figure derives from Blender Studio's CC0 Human Base Meshes. See
[SOURCES](../ocean/SOURCES.md) and [CREDITS](../../../../CREDITS.md).
