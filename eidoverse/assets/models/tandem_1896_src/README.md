# Tandem — build scripts

[Pack README](../tandem_1896/README.md) · [Sources](../tandem_1896/SOURCES.md) · [Blender guide](../../../../docs/blender.md) · [Props and sets guide](../../../../docs/props-and-sets.md#the-1896-tandem)

These are the headless Blender 5.2 scripts that built `tandem.glb`. They are
copied as they were run for the DAISY film. The rebuild from this folder has
not been re-run since the copy.

| File | Role |
| --- | --- |
| `build_tandem.py` | The entry point and the two stages. `--stage geo` models the bike and its hierarchy and renders form checks with placeholder shaders. `--stage full` then adds the layered source materials, bakes them with Cycles into per-look atlases, exports `tandem.glb` and renders look checks of the baked asset. |
| `tgeo.py` | Geometry helpers. The bike is authored in a "bike frame" (+X travel, +Y up, +Z right); `B()` maps that to Blender's Z-up, and the glTF exporter maps it back. |
| `tparts.py` | The parts: frame tubes with cast lugs (boolean socket plugs, filleted), brackets, crown, fork, wheels with tangent-laced spokes and nipples, chainrings, cranks, rat-trap pedals, block chain, saddles, spoon brake, bell, cork grips. It also places the pivot empties and writes the layout and chain belts into the root's `daisy_tandem` extras. |
| `tmats.py` | The looks, each an AmbientCG base set plus wear, edge, cavity and dust masks and period details (gold lining), and the bake: parts joined per pivot and atlas before baking (65 separate bakes took 680 s, the joined bake 26 s), `margin_type='EXTEND'`. |

## Rebuild

The scripts resolve their paths relative to the working layout they were
written in, the DAISY film's `work/daisy/props/`. Recreate it under `work/`,
which git ignores, and run from the repository root:

```bash
mkdir -p work/daisy/props/blender
cp eidoverse/assets/models/tandem_1896_src/*.py work/daisy/props/blender/
# inputs: AmbientCG 2K sets as work/daisy/props/tex/<ID>/<ID>_<Map>.jpg
for id in PaintedMetal004 SurfaceImperfections003 Fingerprints002 Smear004 Scratches002 Leather014 Rubber004 Wood092 Cork003; do
  mkdir -p work/daisy/props/tex/$id && (cd work/daisy/props/tex/$id && python ../../../../../fetch_texture.py $id 2k)
done
bash run_blender.sh work/daisy/props/blender/build_tandem.py --stage full    # -> work/daisy/props/tandem.glb
cp work/daisy/props/tandem.glb eidoverse/assets/models/tandem_1896/
```

- `run_blender.sh` is the repository's isolated headless runner (see the
  [Blender guide](../../../../docs/blender.md)). The comment at the
  top of `build_tandem.py` shows the bare Blender command it was first written
  with. Do not use it: `--factory-startup` against your real user folder
  deletes your extensions' Python packages.
- The bake and the look renders use Cycles on the GPU (OptiX), so wait for any
  render to finish first.
- The look renders light the bike with `work/launch/assets/hdri.hdr`, and the
  script loads that file unconditionally. Put an equirectangular HDR there
  first. `--looks <view,view>` limits the look renders to the views named in
  `LOOK_VIEWS`.
- Keep the pivot names and the `daisy_tandem` extras: `tandem.js` reads them.
  Check a rebuild with the library check scene
  ([guide](../../../../docs/props-and-sets.md#verify)).

## Credits

Modelled, baked and coded by Claude (Opus 5.5) with Skye for the DAISY music
video (2026-09). See [SOURCES](../tandem_1896/SOURCES.md) and
[CREDITS](../../../../CREDITS.md).
