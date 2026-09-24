# Voice machines — build scripts

[Pack README](../voice_machines/README.md) · [Sources](../voice_machines/SOURCES.md) · [Blender guide](../../../../tools-guides/blender.md) · [Props and sets guide](../../../../tools-guides/props-and-sets.md)

These are the headless Blender 5.2 scripts that built the files in
[`../voice_machines/`](../voice_machines/README.md). They are copied as they
were run for the DAISY film, with two changes. `era1_kit.py` no longer holds
the local absolute repository path; it finds the repository root by walking
up to the folder that holds `eido.py`. And the run lines in the comments now
use the repository's `run_blender.sh`. The rebuild from this
folder has not been re-run since the copy.

| File | Builds |
| --- | --- |
| `era1_kit.py` | Shared kit for the era-1 machines: bmesh face modelling, angle-limited bevels, role material slots `era1_<role>`, a second UV set packed as the mask atlas, `bake_masks()` (Cycles EMIT bake: R = AO over 0.30 m, G = edge intensity, B = AO over 4 cm) and GLB export. The top docstring's channel list is older than `bake_masks()`; the function is right. |
| `era1_voder.py` | `voder.glb`, `voder_mask.png`, `voder_layout.json` |
| `era1_mainframe.py` | `mainframe.glb`, `mainframe_mask.png`, `mainframe_layout.json` |
| `era1_teletype.py` | `teletype.glb`, `teletype_mask.png`, `teletype_layout.json` |
| `era_bkit.py` | Shared kit for the era-2 machines: profile prisms, lofts, exact booleans, bake-source materials (AmbientCG scans box-projected at real scale, AO grime, pointiness edge wear, yellowing, dust, projected label decals), CPU bakes (colour 2048, roughness/normal/AO 1024, normal at 16 samples) and GLB export. |
| `era_logos.py` | The PIL-drawn period-mark homages (TI, Speak & Spell, Commodore, rainbow apple, DEC, the four-tile flag) that the era-2 builds project as decals. |
| `build_speakspell.py`, `build_c64.py`, `build_mac1984.py`, `build_dectalk.py`, `build_desktop2001.py` | One era-2 machine each: `<name>.glb` |

## Rebuild

The scripts find their inputs and outputs relative to the working layout they
were written in, the DAISY film's `work/daisy/props/`. Recreate that layout
under `work/`, which git ignores, so a rebuild never writes into the library.
Run everything from the repository root:

```bash
mkdir -p work/daisy/props/blender
cp eidoverse/assets/models/voice_machines_src/*.py work/daisy/props/blender/
# era-2 inputs: AmbientCG 2K sets as work/daisy/props/tex/<ID>/<ID>_{Color,Roughness,NormalGL,Displacement}.jpg
for id in Plastic012B Plastic013B Plastic018B Rubber004 Fabric082A; do
  mkdir -p work/daisy/props/tex/$id && (cd work/daisy/props/tex/$id && python ../../../../../fetch_texture.py $id 2k)
done
bash run_blender.sh work/daisy/props/blender/era1_voder.py        # -> work/daisy/props/assets/era1/
bash run_blender.sh work/daisy/props/blender/build_dectalk.py     # -> work/daisy/props/assets/dectalk.glb
cp work/daisy/props/assets/era1/voder* work/daisy/props/assets/dectalk.glb eidoverse/assets/models/voice_machines/
```

- `run_blender.sh` is the isolated headless runner (see the
  [Blender guide](../../../../tools-guides/blender.md)). Never start
  `blender --factory-startup` against your real user folder: it deletes the
  Python packages that your installed extensions depend on.
- On the machine where the film was made, `work/daisy/props/` already exists
  with its textures. Build there directly.
- The era-1 mask bake runs Cycles on the GPU (OptiX, then CUDA), so wait for
  any render to finish first. The era-2 bakes run on the CPU.
- The label decals are drawn with Windows fonts from `C:/Windows/Fonts/`.
  Other systems need those files, or a changed `FONTS` path.
- After a rebuild, run the library check scene
  ([props and sets guide](../../../../tools-guides/props-and-sets.md#verify))
  and compare the frames with the previous ones. The era-1 modules expect the
  object and role names, and the layout keys, that these scripts write.

## Credits

Modelled, baked and coded by Claude (Opus 5.5) with Skye for the DAISY music
video (2026-09). The CC0 scans and the homages are listed in
[SOURCES](../voice_machines/SOURCES.md). See
[CREDITS](../../../../CREDITS.md).
