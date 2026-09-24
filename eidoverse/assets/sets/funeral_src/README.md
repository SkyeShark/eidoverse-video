# Funeral set — build scripts

[Pack README](../funeral/README.md) · [Sources](../funeral/SOURCES.md) · [Blender guide](../../../../docs/blender.md) · [Props and sets guide](../../../../docs/props-and-sets.md#the-funeral)

The headless Blender scripts that built the GLBs and layout files in
[`../funeral/`](../funeral/README.md). They are copied as they were run for
the DAISY film, with two changes. `fx_core.py` finds the repository root by
walking up to `eido.py`; it used to hold a local absolute path. `run.sh` now
calls the repository's `run_blender.sh`. After the copy, `build_crowd.py` was
re-run from this folder in a scratch copy of the layout below. It wrote the
same `crowd_rig.json` and a `crowd.glb` of the same size and triangle count;
the file is not byte-identical. The other builders were not re-run.

The builders author in three.js space (x right, y up, z toward the camera)
and rotate into Blender's Z-up once per mesh, so their numbers match the
module's set-local numbers. Materials are named by role (`brick`, `concrete`,
`timber`, `steel`, `glass`, `planks`, `corrugated`, `enamel`, `stage`,
`galv`, …). Nothing is baked: the module binds the AmbientCG maps and the
weathering to those roles at runtime. The builds need core Blender only, no
add-ons, and they clear the start-up scene rather than resetting to factory
settings.

| File | Writes (to `work/daisy/sets/assets/`) |
| --- | --- |
| `fx_core.py` | Shared helpers: meshes in three space, role materials, modifiers, booleans, planar UVs in metres, skin chains, previews. |
| `build_warehouse.py` | `warehouse.glb`, `funeral_layout.json` |
| `build_props.py` | `props.glb`, `props_layout.json` |
| `build_crowd.py` | `crowd.glb`, `crowd_rig.json`: four figure variants. The phone arm is its own part pinned at the shoulder. `COLOR_0` holds R = arm mask, G = phone screen, B = head mask. |
| `build_bridge.py` | `bridge.glb`, `bridge_layout.json` |
| `run.sh` | `bash run.sh build_<x>.py [preview]`: runs a builder through `run_blender.sh` and filters Blender's registration noise. |

## Rebuild

`run.sh` expects to sit in the DAISY film's working layout,
`work/daisy/sets/blender/`, which is four levels below the repository root.
The outputs go to `work/daisy/sets/assets/`. Recreate the layout under
`work/`, which git ignores:

```bash
mkdir -p work/daisy/sets/blender
cp eidoverse/assets/sets/funeral_src/* work/daisy/sets/blender/
bash work/daisy/sets/blender/run.sh build_crowd.py                 # -> work/daisy/sets/assets/crowd.glb + crowd_rig.json
cp work/daisy/sets/assets/crowd.glb work/daisy/sets/assets/crowd_rig.json eidoverse/assets/sets/funeral/
```

The extra argument `preview` also renders a preview into `work/daisy/sets/probes/`. Keep the
object and role names and the layout keys: `funeral.js` reads them. Check a
rebuild with the library check scene
([guide](../../../../docs/props-and-sets.md#verify)).

## Credits

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09).
See [SOURCES](../funeral/SOURCES.md) and [CREDITS](../../../../CREDITS.md).
