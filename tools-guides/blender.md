# Blender — headless runs and asset authoring

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Scene format](scene-format.md) · [Blender and EEVEE notes](stack-notes.md)

In this edition Blender is both the studio's renderer and its workshop. The
runner builds and renders every scene in Blender 5.2 with EEVEE
([scene format](scene-format.md)); this guide covers running your own Blender
scripts headless and authoring assets for the library: garments and
accessories for VRMs, VRMA animation clips, hard-surface props exported as
GLBs, the hard-surface kit (a measured high, a low from the same tables, a GPU
bake, the judging room), and trim sheets. Judge every asset in an EEVEE render of the scene it is
for, from the angles the shot will see it. The library's assets are shared
with the WebGPU editions, where they were first made; an asset meant for both
is checked in each. VRM and VRMA work needs the VRM Add-on for Blender
(extension id `vrm`, [setup](../docs/SETUP.md#4-the-vrm-add-on-for-blender)).

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
what they use and find the repository root themselves; with the root on
`sys.path` as `<repo>/blender`, the whole `eidoblend` package is importable:

```python
import os, sys
import bpy

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')   # only when the script needs VRM
REPO = os.path.dirname(os.path.abspath(__file__))
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido_blender.py')):
    REPO = os.path.dirname(REPO)
sys.path.insert(0, os.path.join(REPO, 'blender'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
```

Blender returns 0 even when a script raises: check that every output exists,
and give a command-line tool its own exit code (`look/probe_cli.py` prints
the traceback and calls `os._exit(code)`). A scene for the runner needs none
of this: `eido_blender.py` runs `setup(ctx)` and `render_frame(ctx, t, i)` for
you.

Keep working files (stage `.blend`s, bake renders, look renders) under
`work/`. A library asset keeps its editable source in an `<asset>_src/`
folder next to it, with a README covering the files, the rebuild commands and
the credits. See `eidoverse/assets/vrms/claude_suit_wardrobe_src/`,
`eidoverse/assets/animations/performance_src/`,
`eidoverse/assets/animations/performance_uf_src/` and
`eidoverse/assets/grass/daisy_src/`. When a render may be reading the file
you export, write a temporary file and `os.replace` it into place, so the
render never loads half a file.

## Clothes and accessories for a VRM

Import with `bpy.ops.import_scene.vrm(filepath=...)`
(`set_view_transform_to_standard_on_import=False` keeps the scene's AgX), or
with the characters family's `load_vrm` in a scene. Export every layer,
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
  the wardrobe paints by material name. The add-on exposes MToon on
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

Review a garment with `blender/tools/vrm_turntable.py`: outfit, clip, face
and PBR sheets, and spin reels
([claudesona](claudesona.md#turntable-sheets--blendertoolsvrm_turntablepy)).
The claudesona's wardrobe is the worked example:
`eidoverse/assets/vrms/claude_suit_wardrobe_src/`. Its last stage,
`build_tuta.py`, builds a whole outfit (the TuTa) by script from that `.blend`
and exports the library VRM: it welds digi's split seams before pushing the
garment out, places bone-parented badges from a JSON spec, and leaves the
surface (seams, piping, colour blocking) to the wardrobe's shaders
(`characters.claudesona.tuta`).

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
  `.vrma`'s own rest skeleton, then play it on the character in a short
  probe (`characters.vrma`, [characters](characters.md#vrma-animations)).

`eidoverse/assets/animations/performance_src/` holds the complete authoring
script and a checker. Its README and the script's CONVENTIONS block describe
the rest: interpolation, follow-through lag, hold loops and mirroring.

When the tempo gives no whole frame rate, sample in beats.
`eidoverse/assets/animations/performance_uf_src/` (92.90 BPM) sets the scene's
`fps = 40` and `fps_base = beat`, so beat k is exactly frame 40k. It also adds:

- world-space arm targets, converted through each key's torso pose;
- per-frame arm locks for hands that hold something fixed in the world;
- hanging arms that stay out of the breath layers;
- a checker that skins the real rest mesh to measure the hands' clearance
  from the petals and the body.

## Hard-surface props and baked GLBs

- Model in masses: profile prisms, lofts, EXACT booleans and angle-limited
  bevels.
- Several overlapping cutters joined into one operand need `use_self=True`,
  or the target can come back empty. Log vertex counts per boolean.
- A fine bevel after a boolean can send a few vertices to millions of metres.
  Snapshot the mesh, compare bounds after the bevel, and retry gentler.
- Custom normals are interpolated across the sliver triangles that a boolean
  leaves on a flat face, which shows as fan-shaped streaks. At the end, clear
  the custom split normals, shade smooth by angle, then set flat normals on
  coplanar regions larger than about 1 cm². A weighted-normal modifier cannot
  fix it after the booleans.
- A dished top made from stacked insets folds along a diagonal. Build it from
  concentric scaled rings down to a centre vertex.
- Bake the textures a GLB carries. With an NVIDIA GPU, bake on it with
  `blender/tools/gpu_bake.py` ([below](#high-to-low-baked-on-the-gpu)). Without
  one, Blender's own texture bake does it (it runs on Cycles, so switch the
  scene's engine for the bake): colour at 2048, roughness, normal and AO at
  1024. Bake the normal pass with 16 samples or more: a scan bump finer than a
  texel otherwise becomes per-texel noise that reads as granite under a
  grazing light. Bake every call with margin 0 into images whose alpha starts
  at 0 (the bake writes alpha 1 where it bakes, so alpha is the coverage), and
  dilate once at the end: a margin per call paints over the islands an earlier
  call baked.
- Labels and logos are images projected onto the surface, not geometry.
- Export one GLB, its objects named for their runtime roles (`screen_*`,
  `led_*`, `metal_*`). `harness.assets.import_model` loads it with its maps
  ([assets](assets.md)); the props built this way, and the Blender modules
  that give them their runtime parts (screens, LEDs, grilles), are in
  [props and sets](props-and-sets.md) and [voice machines](voice-machines.md).

Colours: the films render under AgX, which rolls bright emitters toward
white. Judge an emissive screen's colour in an EEVEE render at the film's
exposure, and match printed colours to a reference photo under the same
exposure rather than by hex. Dark gloss plastic turns scan micro-variation
into glitter under a spotlight, so keep its texture mix and bump tiny and its
roughness band narrow.

## High to low, baked on the GPU

The hard-surface kit, `eidoblend.props.hardsurface`, builds a prop the way it
is made and gives it a game-asset's surface: a detailed HIGH of measured
masses, a LOW drawn from the same tables (never decimated or remeshed), the
high baked onto the low on the GPU, and one layered material reading the
bakes ([procedural materials](procedural-materials.md#a-layered-material-on-baked-maps)).
The carbine and the helicopter in [props and sets](props-and-sets.md#the-carbine)
are built with it; their packages are worked examples of every step.

| Module | What it does |
| --- | --- |
| `hardsurface.masses` | the mass constructor: prisms, boxes, cylinders, turned parts, lofts, sweeps, revolves; EXACT booleans; `finish` (one bevel, flats flat); edge groups (`tagged`, `finish_forged`); the low from the same tables |
| `hardsurface.sections` | a lofted body from control sections: `Body(keys, n_edge, n_corner, breaks)`, `stations` (plain Python) |
| `hardsurface.skins` | skins and openings: `loft_body`, `Surface`, `border`, `frame`, `screws`, `pane`, `round_poly`, `prism` |
| `hardsurface.lowpoly` | `prepare_low`: the low's normals, seams, UVs at one texel density, the pack |
| `hardsurface.uv_pack` | the raster UV packer (58-78 % of the square) |
| `hardsurface.bake_export` | `write_high` / `write_low`: the baker's inputs |
| `hardsurface.chain` | an asset's steps run from plain Python: Blender, the bake, `EIDO_GPU_WRAP` |
| `blender/tools/gpu_bake.py` | the bake itself, outside Blender (NVIDIA Warp; the CPU without CUDA) |
| `look.studio` | the judging room: `studio(scene)` -> `shoot(path, centre, pos)` |

### The masses

A part is ONE mass. Intersect the prisms of its measured outlines (the side's,
the section's, the plan's), union its forged-in features with a clear overlap,
cut its recesses with cutters that go all the way through, then `finish` it:
welded, degenerate and coplanar leftovers dissolved, open edges reported, one
angle-limited bevel with hardened normals, and a weighted-normal modifier that
keeps flats flat. Separate hardware stays a separate part. Every table is in
millimetres; the scene is in metres.

```python
from eidoblend.props.hardsurface import masses as hs
from eidoblend.props.hardsurface.masses import EG_BODY, EG_FEATURE, EG_MACHINED, EG_CUT

def block(low=False):
    hs.start('block_low' if low else 'block_high', low=low)     # the parts' collection and a workbench
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    b = hs.boolean(hs.tagged(hs.prism_side('block', [(0, 0), (120, 0), (120, 40), (100, 60), (0, 60)], -20, 20), EG_BODY),
                   hs.tagged(hs.prism_section('sec', [(-20, 0), (20, 0), (20, 50), (14, 60), (-14, 60), (-20, 50)], -5, 125), EG_BODY),
                   'INTERSECT')
    b = hs.boolean(b, hs.tagged(hs.cyl('boss', (40, -18, 30), (40, -26, 30), 24.0), EG_FEATURE), 'UNION')
    b = hs.boolean(b, hs.tagged(hs.box('channel', (20, -8, 52), (90, 8, 70)), EG_MACHINED), 'DIFFERENCE')
    b = hs.detail(b, hs.tagged(hs.cyl('pin_hole', (40, -40, 30), (40, 40, 30), 8.0), EG_CUT), 'DIFFERENCE')
    hs.finish_forged(b, lambda ka, kb, convex: 0.3 if EG_MACHINED in (ka, kb) else 0.5 if EG_CUT in (ka, kb)
                     else (1.5 if convex else 2.0) if ka == kb else (1.0 if convex else 2.5), clay)
    hs.finish(hs.cyl('pin', (40, -27.5, 30), (40, 21, 30), 7.8, seg=32), 0.3, clay)
    hs.sweep_tmp()
    hs.apply_transforms()                         # every part's mesh in the asset's space, its object at identity

hs.new_file(); block()                            # the high
hs.new_file(); block(low=True)                    # the low: the same tables
```

- **Edge groups by construction.** `tagged(o, group)` marks an operand's
  faces; a boolean carries the tags into its result. `finish_forged(o, width,
  m)` reads each edge's group from the pair of tags it parts and whether it is
  convex, and bevels it as a round of `width(tag_a, tag_b, convex)` mm: a
  forging's soft outer radius, a fillet where a forged-in mass meets the body,
  crisp machining. A round of radius R across a dihedral a is set back
  R tan(a / 2), so a fillet running tangent into a tube thins away, and no
  bevel is wider than 0.45 of the narrower face beside it.
- **The low.** `start(name, low=True)`: round parts take the radial count
  their chord sagitta allows (`nseg`, 0.12 mm by default: half a pixel of a
  close view), `detail()` booleans are left to the bake (pin holes, bores
  inside the asset, knurls), `finish` only cleans, and a low a boolean left
  open is closed. `cyl(..., keep=True)` keeps the high's count where cutters
  must meet a tube exactly.
- **Skins.** A moulded or pressed part is one skin of fitted sections:
  `rings` (each ring the same count and winding), `sweep` along a path with
  rotation-minimising frames, `revolve` about any axis. Round a skin's rim IN
  the surface (rows of an arc from the cut plane to the wall), never with a
  boolean cut and a bevel: a plane through a dense loft leaves slivers the
  bevel dents or tears. Fine relief (chequering, ribs under a millimetre)
  belongs to the bake, as height.
- **Lofted bodies.** `sections.Body` describes a body whose section changes
  kind along its length (a nose, a canopy of flat panes, a slab-sided cabin, a
  boom): a control polygon per station with a reach per corner, carried
  between stations by monotone cubics. `skins.loft_body` skins it;
  `skins.Surface` asks the uncut skin where a ray meets it; `border` lays an
  opening's outline on it, `frame` sweeps a retainer or a seal round it,
  `screws` dots heads along it, `pane` sets the skin's own patch into the
  opening as glass. The helicopter is built this way.
- Build into an empty file (`hs.new_file()`): the asset scripts find their
  parts by name.

### The low, finished, and the bake

```python
from eidoblend.props.hardsurface import bake_export, lowpoly
# in the session that holds the high (bevels and normals still modifiers):
bake_export.write_high(high_parts, 'work/block/bake', 'block')
# in the session that holds the low:
rep = lowpoly.prepare_low(low_parts, sharp_deg=40.0, hide_dir=(0.0, -0.45, -0.89), cells=1024)
bake_export.write_low(low_parts, 'work/block/bake', 'block', size=4096, substrate={'block': 1, 'pin': 5},
                      options={'ao_mm': 30.0, 'cav_mm': 2.0, 'edge_mm': 4.0, 'corner_mm': 8.0})
```

```bash
python blender/tools/gpu_bake.py --bake work/block/bake --name block [--ss 2] [--device auto|cuda|cpu]
```

`prepare_low` finishes the low in place: coplanar runs merged and triangulated
(BEAUTY); custom normals weighted by each face's coplanar region, so a big
flat shades dead flat however it is triangulated; every hard edge (over
`sharp_deg`) split and a UV seam; an island that would not flatten cut once
more along its cheapest line, toward the side seen least (`hide_dir`); one
texel density everywhere, a fifth of it on islands inside other parts; then
the raster packer (`cells` x `cells`: the carbine's 1,009 islands take about
12 minutes of prep at 1024 and fill 58 % of the set, about 5 minutes at 512
for 30 %; 256 cannot hold them, and the packer says so at once rather than
searching). The triangulation is frozen there: the bake's tangents come from
it, and it is what renders.

The baker reads the inputs and writes `<name>_normal.png` (16-bit, OpenGL, in
the low's MikkTSpace frame as EEVEE's normal-map node builds it, so it decodes
exactly), `<name>_masks_a.png` (AO, cavity, fine curvature),
`<name>_masks_b.png` (the nearness of the part's exposed convex arrises, broad
curvature, the nearness of its inside corners), `<name>_id.png` (the
substrate per texel, x 16, never filtered), proofs (`<name>_coverage.png`,
`<name>_layout.png`) and `<name>_report.json`. A low part bakes from the high
part of its own name only, so no ray lands on a neighbour; the cage and the
reach per part come from the measured low-to-high distance (or the options'
`cage_mm` / `reach_mm`); rays from a hard-edged flat lean square to it away
from its UV borders; a ray that starts inside the high or finds only back
faces is tried again from further out; AO and cavity are cast against every
high and the occluders `write_high` was given. Every map is padded from its
nearest baked texel through the gutters. `--layers FILE` hands the computed
maps to an asset's own code before they are written (the carbine lays its
markings and its grip's chequering in that way: `props/carbine/layers.py`).

Blender's selected-to-active bake casts every texel's ray in a serial loop on
the CPU, so a dense high keeps the GPU idle for many minutes; this one casts
them all at once with NVIDIA Warp's BVH queries: the carbine's 4096 set, 9.9 M
texels at 2 x 2 samples against a 500 k-triangle high, in about 8 seconds on a
laptop RTX 5090 (45 s for the whole run, maps written). Without CUDA, Warp
runs the same kernels on the CPU (`--device cpu`), more slowly; without Warp,
use Blender's texture bake as above. Dependencies: numpy, scipy, Pillow and
`warp-lang` (the bake tier of `requirements-local.txt`).

Run an asset's whole chain from plain Python with `hardsurface.chain`
(`chain.blender(script, *args)`, `chain.python(script, *args)`, `has_warp()`,
`has_cuda()`): each step is its own process from the repository root, queued
through `EIDO_GPU_WRAP` when it is set. `props/carbine/make.py` is the example.

### The judging room

Judge a material in `look.studio`, not in a film's light first: a gradient
with three softboxes in it that the lens never sees (camera rays see flat
0.07 grey), an area key that casts the shadow and a rim, both re-aimed from
the side the camera stands on, and an 18 % grey ball and a mirror ball beside
the asset. Under AgX at the default level the grey ball's lit side reads
about 120-136 of 255; if it does not, the exposure is wrong, not the
material.

```python
from eidoblend.look import studio
shoot = studio.studio(bpy.context.scene, balls_at=(0.30, 0.09, -0.16), ball_r=0.02, samples=16)
shoot('work/block/stills/three_quarter.png', centre=(0.06, 0.0, 0.03), pos=(0.16, -0.22, 0.14), lens=50, res=(960, 540))
```

`studio()` replaces the scene's lights, camera and world (its own are in the
collection `lookdev_only`); `reach` scales the lights' distance for a bigger
asset (a room's furniture: 3-5).

### Measurements from a photograph

`blender/tools/grid_crop.py PHOTO OUT.png --scale MM_PER_PX --origin X,Y --box
X0,Y0,X1,Y1` enlarges a crop of a square-on reference photograph under a
millimetre grid in the part's own coordinates (x to the right of the origin
pixel, z up), so an outline is traced by reading numbers. Keep the photographs
and the crops out of the repository; the numbers go in the builder's tables.

Tests: `blender/tests/props_hardsurface/` (`test_kit.py`: the kit on a sample
block in Blender, no render; `test_bake.py`: the GPU bake of its high onto its
low, checked map by map; `test_stills.py`: three stills under the layered
material in the studio).

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
`create_flora`'s daisy ([vegetation](vegetation.md)).

## Not yet ported

- Nothing is missing from this guide's tools: `run_blender.sh`, the add-on
  operators and the authoring scripts are Blender already. The WebGPU
  edition's habit of judging an asset in its own render (three's MToon, its
  node materials and its ACES tone map) applies only where an asset is also
  meant for that edition.
