# Blender — building assets for the kit

[Main instructions](../AGENTS.md)

Blender is an authoring tool here: model, weight, bake and export in it, then
judge the result in the engine. EEVEE is not the truth for these assets. The
engine's MToon, node materials, ACES tone mapping and post passes are, so
every Blender change is reviewed in an engine render. Everything below was
run headless on Blender 5.2 LTS. VRM and VRMA work needs the VRM Add-on for
Blender, installed once in normal Blender from extensions.blender.org
(extension id `vrm`).

## Run Blender headless — `run_blender.sh`

```bash
bash run_blender.sh path/to/script.py [args...]     # from the repository root
```

A bare `blender --background --factory-startup` is fast, but run against
your real Blender user folder it syncs the extension wheels to the empty set
that factory settings enable, and it deletes the Python packages your
installed extensions depend on. `run_blender.sh` avoids that:

- It points `BLENDER_USER_RESOURCES` at a scratch sandbox (`$TMP/blender_user_isolated`, or `BLENDER_SANDBOX`).
- It copies the extensions a script needs into the sandbox from your
  installed Blender, again whenever your installed copy changes. That is
  `vrm` by default; set `BLENDER_EXTS="vrm other"` for more.
- It finds Blender through `BLENDER`, then `PATH`, then the common install
  folders, newest first.

Arguments after the script reach it after Blender's `--`. Scripts enable
what they use and find the repository root themselves:

```python
import os, sys
import bpy

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')   # only when the script needs VRM
REPO = os.path.dirname(os.path.abspath(__file__))
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
```

Keep working files (stage `.blend`s, bake renders, look renders) under
`work/`. A library asset keeps its editable source in an `<asset>_src/`
folder next to it, with a README covering the files, the rebuild commands and
the credits. See `eidoverse/assets/vrms/claude_suit_wardrobe_src/`,
`eidoverse/assets/animations/performance_src/` and
`eidoverse/assets/grass/daisy_src/`. When a render may be reading the file
you export, write a temporary file and `os.replace` it into place, so the
render never loads half a file.

## Clothes and accessories for a VRM

Import with `bpy.ops.import_scene.vrm(filepath=...)`. Export every layer,
hidden ones included:

```python
res = bpy.ops.export_scene.vrm(filepath=tmp, export_invisibles=True, export_only_selections=False)
```

- **Weights come from what the garment lies on.** Build a garment by
  duplicating and pushing out the garment beneath it, or copy each vertex's
  weights from the nearest vertex of the surface below. Loose cloth is the
  exception: a skirt given nearest-vertex weights lets the legs pass through
  it. Write its weights on purpose, hips at the waist blending into each
  thigh toward the knee.
- **Rigid accessories are bone-parented.** Parent glasses and hats to
  `head`, and bow ties and pins to `chest`. Keep a hat's placement adjustable
  at runtime rather than baking a guess into the mesh.
- **A garment pushed out along normals cracks at split seams.** Skin shows
  through as coloured lines on dark paint. Wear the source garment
  underneath, painted to match.
- **Give every paintable surface its own named MToon material,** because
  runtime code paints by material name. The add-on exposes MToon on
  `material.vrm_addon_extension.mtoon1`:
  ```python
  ext = m.vrm_addon_extension.mtoon1
  ext.enabled = True
  ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
  mt = ext.extensions.vrmc_materials_mtoon
  mt.shade_color_factor = tuple(c * 0.58 for c in rgb)
  mt.outline_width_mode = 'worldCoordinates'
  mt.outline_width_factor = 0.004
  mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
  mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)   # a grey rim washes out small dark accessories
  ```

Review a garment in the engine with `vrm_turntable.py`
([AGENTS.md](../AGENTS.md), "Turntable sheets"). The claudesona's wardrobe
is the worked example: `eidoverse/assets/vrms/claude_suit_wardrobe_src/`.

## VRM animation clips (`.vrma`)

The add-on exports a baked action as VRMA:
`bpy.ops.export_scene.vrma(filepath=..., armature_object_name=arm.name)`.

- Set `arm.data.vrm_addon_extension.vrm1.humanoid.pose = 'restPositionPose'`
  first. The exporter's T-pose reference is then the rig's own rest pose,
  which is the one three-vrm normalizes against.
- The exporter samples every frame from `frame_start` to `frame_end` at the
  scene fps, so dense per-frame keys are exactly what you get. Every humanoid
  bone gets a channel, fingers included; key relaxed fingers or the hands
  export as flat paddles. Hips translation is absolute, and three-vrm scales
  it by the ratio of hips heights.
- Pick the fps so the timing grid lands on whole frames. At 128 BPM, 64 fps
  gives exactly 30 frames per beat, and a loop's last sample equals its
  first.
- Author in three-vrm's normalized frame (x = the character's left, y = up,
  z = forward). The conversion is exact:
  `q_basis = Rrest⁻¹ · N · Rrest`, with the axes mapped
  (x, y, z)three → (x, −z, y)blender.
- Key arms by IK targets rather than joint angles: palm point, palm normal,
  finger direction and elbow pole. Plant the feet by leg IK on one shared
  stance, so any two clips crossfade without sliding.
- Check the exported file, not the intent. Run forward kinematics on the
  `.vrma`'s own rest skeleton, then look at it in the engine.

`eidoverse/assets/animations/performance_src/` holds the complete authoring
script and a checker. Its README and the script's CONVENTIONS block describe
the rest: interpolation, follow-through lag, hold loops and mirroring.

## Hard-surface props and baked GLBs

- Model in masses: profile prisms, lofts, EXACT booleans and angle-limited
  bevels.
- Several overlapping cutters joined into one operand need `use_self=True`,
  or the target can come back silently empty. Log vertex counts per boolean.
- A fine bevel after a boolean can send a few vertices to millions of metres.
  Snapshot the mesh, compare bounds after the bevel, and retry gentler.
- Custom normals are interpolated across the sliver triangles that a boolean
  leaves on a flat face, which shows as fan-shaped streaks. At the end, clear
  the custom split normals, shade smooth by angle, then set flat normals on
  coplanar regions larger than about 1 cm². A weighted-normal modifier cannot
  fix it after the booleans.
- A dished top made from stacked insets folds along a diagonal. Build it from
  concentric scaled rings down to a centre vertex.
- Bake with Cycles on the CPU: colour at 2048, roughness, normal and AO at
  1024. Never bake the normal pass at 1 sample. A scan bump finer than a
  texel then becomes per-texel noise that reads as granite under a grazing
  light; 16 samples average it into texel-scale relief.
- Labels and logos are images projected onto the surface, not geometry.
- Export one GLB. A module loads it with `GLTFLoader` and rebuilds node
  materials from the baked maps; name objects for their runtime roles
  (`screen_*`, `led_*`, `metal_*`). The props built this way and their modules
  are in [props and sets](props-and-sets.md).

Colours through the engine: three's ACES multiplies by exposure / 0.6 before
the curve, so emissive screens land about 1.7× brighter and paler than
authored. Pre-compensate the gain. Match printed colours to a reference photo
under the same exposure rather than by hex. Dark gloss plastic turns scan
micro-variation into glitter under a spotlight, so keep its texture mix and
bump tiny and its roughness band narrow.

## Trim sheets rendered from models

For foliage and other card geometry, draw the art first, then fit the cards
to it:
- Model each region of the sheet at real scale in Blender.
- Render it orthographically as emission passes, which give exact values:
  albedo with coverage alpha, roughness and translucency, world normal, and
  AO.
- Assemble the sheet in Python. Un-premultiply, bake AO into the albedo,
  convert world normals to tangent space, pad colour under empty alpha so
  mips never pull in the background, then measure each card's alpha
  envelope into a fit file that the geometry generator reads.

`eidoverse/assets/grass/daisy_src/` is the worked example behind
`createFlora`'s daisy ([vegetation](../AGENTS.md)).
