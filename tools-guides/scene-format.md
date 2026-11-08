# Scene format — config, script shape, the build and the render

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition. A scene is a `scene.json` config and a
Python script with `setup(ctx)`. The runner builds the scene into a `.blend`
(keyed, baked, audited), then renders that `.blend` with EEVEE straight to
H.264, or to PNG stills.

## Invoking the renderer

Everything runs headless through `run_blender.sh` (an isolated Blender user
folder, so `--factory-startup` never touches your real add-ons). It needs
Blender 5.2 and, on Windows, Git Bash; `python eido_blender.py doctor` checks
both and renders a 64x64 test frame.

```bash
python eido_blender.py render work/<id>/scene.json                    # the whole film -> H.264 + 3 probe frames
python eido_blender.py render work/<id>/scene.json --probe --frames 12  # the first 12 frames, probe caps
python eido_blender.py render work/<id>/scene.json --at 12.5 --at 40  # PNG stills mid-film, at film settings
python eido_blender.py build  work/<id>/scene.json                    # the .blend only, no render
python eido_blender.py bench  work/<id>/scene.json                    # seconds a frame, and the film's total
python eido_blender.py open   work/<id>/scene.json                    # the built .blend in Blender's window
```

All paths in scene configs resolve from the repository root (absolute paths
work too). The exit code is honest: 0 rendered, 1 failed, 3 refused (a
hand-edited `.blend`, below). The runner also checks that every expected file
exists and that the digest says `normal completion`.

## scene.json

```json
{
    "width": 1920, "height": 1080, "fps": 24, "duration": 12,
    "script": "work/<id>/scene.py",
    "outputVideo": "work/<id>/scene.mp4",
    "assets": {
        "crow": "eidoverse/assets/models/crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb"
    },
    "frame_start": 1,
    "render": {"samples": 32, "motion_blur": true}
}
```

The WebGPU edition's keys keep their meaning. `assets` is whatever the scene
actually uses: each key becomes an absolute, checked path in `ctx.assets`
(a missing or empty file stops the run before Blender starts; a URL is
downloaded once into `_assets/` beside the config). Declare only what the
scene reads: a declared asset the script never reads, and a model beside the
script the config never declares, are findings in the digest.

Two keys are new:

- `frame_start` (default 1, as in my films). `t = (frame - frame_start) / fps`.
- `render`, applied **after** `setup()`, so it overrides what the script set:
  use it for per-run choices, and set the look in the script.

| `render` key | Meaning |
| --- | --- |
| `preset` | `film` (default) or `probe`: `probe` renders this scene at the probe caps every time (applied at render time, never saved) |
| `samples` | EEVEE render samples |
| `motion_blur`, `shutter` | motion blur on/off; shutter in frames (0.5 = a 180° shutter) |
| `raytracing` | EEVEE ray tracing on/off |
| `volume_tile`, `volume_samples` | volumetric tile size (px) and samples |
| `exposure`, `look` | view exposure (stops) and AgX look (`AgX - Base Contrast`, `AgX - Punchy`, `None`) |
| `bloom` | `true` or `{"threshold": 1, "size": 0.5, "strength": 1}`: a compositor Glare pass. A hot emitter in the dark blooms across the whole frame at strength 1; start near 0.3 for a lens's glow |
| `film_transparent` | transparent background (PNG stills keep alpha) |
| `resolution_percentage` | render at a percentage of width x height |

`width` and `height` must be even (H.264 in yuv420p). The WebGPU edition's
`inlineScript` is not supported: put the script in a file. Without
`outputVideo`, the film is `composedOutput`, else `<outputDir>.mp4`, as in
`render_scene.mjs`; with none of the three it is `<config name>.mp4` beside
the config. The film has `ceil(duration x fps)` frames (3 s at 24 fps is 72;
1.01 s at 24 fps is 25).

## Minimum scene script

```python
import bpy
from eidoblend.harness import assets


def setup(ctx):
    scene = ctx.scene
    floor_mat = assets.load_pbr('Concrete031', res='1k', maps=('diff', 'normal', 'rough'), repeat=(2, 2))
    bpy.ops.mesh.primitive_plane_add(size=6)
    floor = bpy.context.object
    floor.data.materials.append(floor_mat)

    stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='stool')
    assets.rest_on(stool, 0.0, xy=(0, 0))

    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA'))
    key.data.size, key.data.energy = 1.5, 250
    key.location, key.rotation_euler = (-1.2, -1.0, 1.8), (0.9, 0, -0.8)
    scene.collection.objects.link(key)

    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam


def render_frame(ctx, t, i):
    cam = ctx.scene.camera
    cam.location = (0.4 * t / DURATION, -2.0, 0.9)
    cam.rotation_euler = (1.45, 0, 0)
    ctx.key(cam, 'location')
    ctx.key(cam, 'rotation_euler')
```

The script is plain Python: top-level imports work. The runner puts
`<repo>/blender` and the script's own folder on `sys.path`, so it can import
the `eidoblend` families and helper modules beside it. A worked example lives
in [blender/tests/pipeline/example/](../blender/tests/pipeline/example/scene.py).

### The hooks

- **`setup(ctx)`** (required) builds the scene with ordinary `bpy`: data,
  materials, modifiers, Geometry Nodes, lights, cameras, keys.
- **`render_frame(ctx, t, i)`** (optional) runs **once per frame at build
  time**, with the scene already at that frame (`scene.frame_set`), and keys
  what it changes with `ctx.key(...)` / `ctx.key_transform(...)`. Once it has
  run over the film, the runner sets those keys LINEAR, so sub-frame motion
  blur interpolates straight between the frames you set (Python's
  `keyframe_insert` always makes BEZIER keys in 5.2, whatever the preference
  says); `interpolation='CONSTANT'` keeps a step a step (a light switched at a
  cut). `i` is the frame index from 0; `t` is seconds. Nothing runs per frame
  at render time, so the saved `.blend` plays and scrubs on its own, and a
  frame renders the same whether the render jumps to it or plays up to it.
- **A change `render_frame` does not key is lost.** The literal port of a
  WebGPU `renderFrame` (`lamp.data.energy = 20 if t < 1 else 600`) builds a
  film that shows the **last** value on every frame. The build catches it: it
  notes what `render_frame` set at a handful of frames (both ends, eight
  evenly spaced, both sides of every cut), jumps to those frames in the saved
  scene, and names every value that differs under `build.unkeyed`, with the
  `ctx.key(...)` call that fixes it. It compares object transforms and
  visibility, pose bones, shape-key values, Geometry Nodes modifier inputs,
  lights, cameras, the scene camera (switch cameras with `ctx.cut`), exposure,
  and every unlinked node input of the world and the materials.
- **`cleanup(ctx)`** (optional) runs after the build is saved.

Prefer native animation where it exists: keyframes, NLA strips of imported
clips (`assets.play_model_animations`), constraints, Geometry Nodes driven by
the scene time, simulation zones and point caches (the build bakes them).
`render_frame` is for motion you compute in Python. Python-expression drivers
do not evaluate when Blender opens a file with auto-run off, as the render
reopens a reused build (Blender's documented behaviour; not tested here): use
keys or simple-expression drivers.

### What the script gets

`ctx` holds `scene`, `width`, `height`, `fps`, `duration`, `total_frames`,
`frame_start`, `frame_end`, `assets` (`{key: absolute path}`, reads recorded),
`repo`, `eidoverse_dir`, `scene_dir`, `out_dir` and `mode` (setup should not
depend on it), plus:

| Method | Does |
| --- | --- |
| `ctx.frame_at(t)`, `ctx.time_at(frame)` | seconds and frames, from `frame_start` |
| `ctx.key(target, data_path, index=-1, frame=None, interpolation='LINEAR')` | a key at the current frame (any animatable property, custom properties as `'["name"]'`); LINEAR, or `'CONSTANT'` / `'BEZIER'` |
| `ctx.key_transform(ob, frame=None, interpolation='LINEAR')` | location, rotation (the object's rotation mode) and scale |
| `ctx.cut(t_or_frame, camera)` | a shot cut: a timeline marker bound to the camera (an int is a frame, a float is seconds) |
| `ctx.flag(ob, name)` | an audit flag on an object, e.g. `'no_motion_check'` ([render review](render-review.md)) |
| `ctx.record(check, outcome, message)` | your own finding in the digest (`PASS`, `WARN` or `SKIPPED`) |
| `ctx.log(*msg)` | a tagged log line |

The module namespace also holds the WebGPU edition's globals: `WIDTH`,
`HEIGHT`, `FPS`, `DURATION`, `TOTAL_FRAMES`, `FRAME_START`, `FRAME_END`,
`ASSETS`, `EIDOVERSE_DIR` and `REPO`. Scene-wide audit flags are module-level
names: `_no_motion_check = True`, `_no_auto_placement_check = True`, ...

## The build

`render` and `build` first build the scene into `<out>.blend` beside the
output video, with its record `<out>.build.json`:

1. A fresh empty file; the **film** preset (below); the config's size, rate
   and frame range; AgX.
2. `setup(ctx)`. If it changed the resolution, engine or frame range, the
   config wins and the digest says so.
3. The config's `render` block, then the engine's post stack with the
   script's hooks and overlay layer (below).
4. `render_frame` baked over every frame; its keys set LINEAR (or as asked).
5. Caches baked: point caches (particles, cloth, soft bodies, dynamic paint,
   rigid bodies), Geometry Nodes simulation zones, volume light probes
   (`--no-probe-bake` skips those). Blender's default cache range is 1-250
   (10.4 s at 24 fps): every unbaked cache that stops short is first
   **stretched to the film's last frame**, or a longer film's simulation would
   freeze at frame 250 while everything else moves on. A cache the script
   baked itself keeps its range, and preflight warns if it ends before the
   film does. Fluid domains are not baked here (their range is stretched, and
   preflight warns while they are unbaked).
6. The check that `render_frame` keyed everything it changed
   (`build.unkeyed`, above).
7. The audits: placement (on every build, whether or not the script imports
   the placement family, as the WebGPU runner's checks ran after every
   `setup()`), preflight, coverage, motion, framing, palette, assets
   ([render review](render-review.md)). A scene with no camera stops here.
8. The `.blend` saved (no `.blend1`), and `build.json`: its inputs, the
   settings, each step's time, the audit ledger.

The build's **inputs** are the config, the script, every module it imported
from the repository or from beside the script (md5s), the declared assets
(sizes and times), and **every file and folder the script read through
Python while it built**: a plan file beside it, a JSON of shots, a glTF the
importer read, a folder it listed (its entry names), plus the sources of
packed images. The digest names the undeclared ones (`build.inputs`). A later
run whose inputs are unchanged **reuses** the build and goes straight to
rendering (`--rebuild` forces a new one); an edit to any input rebuilds, and
the digest says which input changed. Reads made in C are not seen (Blender's
image loader, the OBJ / PLY / STL importers): declare such files under
`assets`. What the build writes itself is an output, never an input: an
`html_mesh` panel painted to a PNG and read back, a map it bakes, a folder it
makes for them.

You can open the `.blend` (`eido_blender.py open`), edit it by hand and save:
the next run renders it as edited and re-runs the audits on it, with the
families the script imported (its top-level imports run again, nothing else
of it), so a scene that seats things with the placement family's `place_on`
gets those audits on the hand edit too. A rebuild over a hand-edited `.blend`
is refused (exit 3) unless `--force`, which loses the edits: move them into
the script.

## Coordinates and units

Blender is **Z-up, in metres**; the WebGPU engine was three.js, Y-up.
`eidoblend.common` converts:

```python
from eidoblend import common
common.from_three(x, y, z)          # three point/direction -> Blender (x, -z, y)
common.quat_from_three(x, y, z, w)  # three quaternion -> mathutils.Quaternion order (w, x, -z, y)
common.ground_from_three(x, z)      # three ground (x, z) -> Blender (x, y), y = -z
common.matrix_from_three(m.elements)  # a three Matrix4 -> Blender rows
```

APIs that took a ground point `(x, z)` take `(x, y)`. glTF files import with
the importer's own conversion: a model whose nose points along glTF `+z`
faces Blender `-y`.

## Light and the world

There is no default environment: a scene with no world renders a black
background and no sky light, and the digest says so. A set that needs a sky
uses the sky family's `make_sky`; an interior lights itself with area lights,
emissive fixtures and windows onto that world; a studio may use a dim world
colour for its bounce. `assets.load_hdri(path)` is for lookdev and studio
light only, never a stand-in for the sky.

## Render settings

| Preset | Settings |
| --- | --- |
| **film** (default) | EEVEE, AgX `AgX - Base Contrast`; ray tracing (screen traces at full resolution, spatial/temporal/bilateral denoise, quality 0.5, thickness 0.05, max roughness 0.5); fast GI (global illumination, resolution 2, 8 steps, 2 rays, 0.6 m); shadows 2 rays x 12 steps; volumes 16 px tiles x 32 samples, ray depth 16, volumetric shadows; indirect clamp 10; 32 samples; motion blur, shutter 0.5; filter 1.5 px |
| **probe** | the film's look, cheaper: at most 960x540 (aspect kept), at most 16 samples, traces at half resolution |

These are my films' settings (episode three's house, and the render-time
volumes measured there to look like 4 px x 128 at 60 % of the time). `--probe`
applies the probe caps at render time; `--preset probe` does the same for
`--at` or a full render. Render-time changes are never saved into the build.

Bloom is a compositor pass: `"render": {"bloom": true}` puts the Glare
stage into the compositor chain (`eidoblend.look.post.chain`), the same stage
`_bloom_params` sets below. Other compositing belongs to
[post-processing](postprocessing.md). Extra render passes (vectors, depth)
leave only through a compositor File Output node: in 5.2 a render's own
multilayer EXR holds Combined only.

## The post stack, its hooks and the overlay layer

The WebGPU runner built one post graph after `setup()` (N8AO, SSR, bloom,
FXAA) and let a script hook into it through globals. This runner does the
same after `setup()` and the `render` block: EEVEE's own ray tracing and fast
GI stand in for the screen-space passes, and each hook becomes a stage of the
compositor chain, in the engine's order:

```
Render Layers -> pre-bloom hook -> bloom -> colour hook -> overlay -> screen hook -> AgX
```

A script names them at module level, snake_cased from the engine's globals
(the JS spellings are read too), or sets them in `setup()` with `global`:

```python
from eidoblend.harness import post

_bloom_params = {'strength': 0.4, 'radius': 0.6, 'threshold': 1.0}   # strength 0: no bloom
_ao_params = {'ao_radius': 0.4, 'quality': 'high'}                  # enabled, half_res, quality, ao_radius
_ssr_params = {'thickness': 0.1, 'max_roughness': 0.6}              # enabled, thickness, quality, max_roughness


def _auto_enhance_color_hook(scene, tree):        # after the bloom, before the overlay: the lit world only
    n = tree.nodes.new('CompositorNodeHueSat')
    n.inputs['Saturation'].default_value = 0.6
    return n                                      # one node with an Image in and out (a node group for more)


def _auto_enhance_screen_hook(scene, tree):       # after the overlay: the HUD is part of the signal
    return tree.nodes.new('CompositorNodeInvert')


def setup(ctx):
    global _overlay
    _overlay = post.make_overlay_layer(ctx.scene)   # makeOverlayLayer: a static camera at the origin
    _overlay.add(title_plane)                       # screen-locked at z = -1 (half_w, half_h: the frame there)
```

A hook gets the scene and its compositor tree and returns a node;
`chain.source_pass(scene, 'Depth')` (or `'Normal'`) gives it the passes the
engine's hooks received. `_auto_enhance_pre_bloom_hook` runs just before the
bloom (an anamorphic flare). `post.make_overlay_layer(scene, fov=None,
near=0.01, far=10)` makes the overlay scene (transparent, its camera the film
camera's field of view, or `fov` degrees vertical) on the media family's
overlay, so its `panel()` and subtitles work on it; the film's render renders
it frame for frame through its own Render Layers node. A script may instead
set `_overlay_scene` (and `_overlay_camera`) to a scene it built. The overlay
passes through the film's AgX, as the engine's passed through its tone map;
for graphics whose colours must land exactly as drawn, use the media family's
display-space edit pass ([motion graphics](motion-graphics.md)).
`_no_auto_enhance = True` (or `NO_AUTOENHANCE=1`) turns EEVEE's ray tracing
and fast GI off and adds no runner stages; a scene's own chain stages stay.
The digest's `render.auto_enhance` record says what was installed, like the
engine's `[auto-enhance] TSL pipeline: ...` line.

A lower third as a film uses all of this is
[blender/tests/pipeline2/lower_third/scene.py](../blender/tests/pipeline2/lower_third/scene.py):
a warm grade (colour hook) and a vignette (screen hook) each returned as a
compositor node group with one `Image` in and out (Blender 5's compositor mixes
with `ShaderNodeMix`; `MixRGB` is gone), and an `html_mesh` card on the overlay
layer, placed with `_overlay.place(obj, x, y)` (frame fractions: centre
origin, y up) and keyed sliding in with `ctx.key(obj, 'location', ...)`; the
overlay scene renders each film frame at that frame. Two traps: `html_mesh` is
1 mm a pixel and a 50 mm lens frames only 0.72 m at the overlay's depth, so
size a card as a fraction of `2 * half_w`; and the overlay scene is not the one
`view_layer.update()` evaluates, so read a card's size from its mesh's
`bound_box` times its scale, not from `obj.dimensions` (a stale matrix there).

## Outputs

| Run | Writes (beside `outputVideo`) |
| --- | --- |
| `render` | `<out>.mp4` (H.264 High, near-lossless CRF, GOP 24, no audio) and `<out>_probe1..3.png` (frames at 15/50/85 %) |
| `render --probe` | `<out>_probe.mp4` and `<out>_probe_probe1..3.png` |
| `render --at T` | `<out>_probe_at<T>s.png` (T is the frame's own time, two decimals) |
| every run | `<out>.audit.txt` + `.audit.json` (the digest), `<out>.blend`, `<out>.build.json`, `<out>.job.json` |

Output safety: an existing video is moved to `<out>.mp4.prev`, the render
writes `<out>.mp4.part`, and only a finished render is renamed into place.
No `<out>.mp4` means the render did not finish; never review a `.prev` as new.
The digest gets a `running` stamp first and is rewritten on every exit path.
Sound is muxed afterwards with `merge_av.py` ([audio](audio.md)). A film
render prints a progress line every 15 frames; `RENDER_CQ`, `RENDER_BITRATE`
and `RENDER_CODEC` set Blender's writer as they set the engine's ffmpeg pipe
([production](production.md#plan-the-render)).

## The render_*.mjs helpers

`render_common.mjs` was the shared kit of the WebGPU render tools; what
means something in Blender is `eidoblend.harness.render_common`:

```python
from eidoblend.harness import render_common as RC
rig = RC.setup_scene({'background': '#202028', 'camera': {'fov': 40, 'position': [0, 1.5, 4]}})
RC.key_camera_path(rig['camera'], [{'time': 0, 'position': [0, 1.6, 6], 'target': [0, 1, 0]},
                                   {'time': 4, 'position': [3, 2, 4]}])   # three coordinates, smoothstep keys
```

`setup_scene(config)` builds a config's `background`, `lights` and `camera`
(three coordinates; without lights, the engine's default rig of an ambient,
a key sun and a blue and a pink point); `get_camera_at_time` /
`key_camera_path` are its camera path (smoothstep per segment, keyed on every
frame); `alpha_composite` lays a premultiplied RGBA layer over a frame
(numpy); `log_progress` and `ffmpeg_rate_control` are what the runner uses.
`setupRenderer`, the readback and the ffmpeg pipe have no meaning here
(Blender renders and writes the video itself); `rasterizeUI` (Satori) is
superseded by the media family's canvases and `html_mesh`.

## Not yet ported

- `--jump` is accepted and changes nothing: a built scene is a pure function
  of the frame. `--preroll S` steps the timeline through S seconds before each
  `--at` still, unrendered, for state that is still live at render time (VRM
  spring bones left unbaked: unverified).
- The WebGPU per-frame registries (`_autoMixers`, particle, screen, creature
  and robot updates) are not a runtime here: each system keys or bakes its own
  motion at build time.
- Two of the engine's hooks have nothing to hook into: the pre-SSR hook
  (EEVEE traces reflections inside the renderer, with no pass between shading
  and reflection) and the cloud-reflect hooks (the sky family's world lights
  metals and glass itself). A script that names them is told so in the digest.
  `_aoParams`' intensity and distance falloff and `_ssrParams`' max distance
  have no EEVEE knob and are ignored, said in the digest.
- The env fallback (a sky-gradient environment the engine installed when a
  scene set none) is deliberately absent: a scene with no world renders black
  and the digest says so.
- Panoramic (`PANO`) cameras in EEVEE: untested.
- Build inputs read in C (images, OBJ / PLY / STL imports) are not tracked:
  declare them. Fluid (Mantaflow) domains are not baked by the build.
- The un-keyed check compares the property families listed under the hooks;
  a change elsewhere (a particle setting, a compositor value, a node group's
  own node) is not compared.
