# WebXR — scenes in a headset browser (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Blender](blender.md)

The renderer makes videos. To stand *inside* a piece — walk round a city while
its choreography plays, hold it on a table in front of you — the same world can
be shown live in a headset's browser with WebXR. Everything here was worked out
on a Quest 3 in the Quest Browser with three r184; other headsets with a WebXR
browser should work the same way but have not been tried.

This is a live page, not a render: it runs at the headset's frame rate on a
phone-class GPU, twice (once per eye). In the Blender edition a film's scene is
**exported**: Blender's glTF exporter writes it to a GLB with its animation
baked and its materials made into things glTF can hold, and the kit's page
plays that GLB on the kit's rig. The kit itself (`eidoverse/xr/`) carries over
as it is: the page is a three.js page on its WebGL2 backend, the servers and
`quest.py` are the same Python, the stills come from the same `shot.mjs`. The
package is `blender/eidoblend/xr/`.

The work that stays is making the set light enough for the headset: fewer,
bigger meshes, no post effects (they do not run in XR here), glowing colours
brightened instead of bloomed. The export reports what a set costs and cuts
nothing unless asked (`max_image` scales its textures down for the headset).

## A Blender scene in the headset

Inside Blender (a scene script, or a built `.blend`):

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.xr.export import set_xr, export_xr, survey_xr

set_xr(scene, street=1.0, table=0.04, start=(0, -4, 0), facing=(0, 1, 0), table_centre=(0, 0.5, 0))
print(survey_xr(scene))               # what the export would do, changing nothing
man = export_xr('work/<id>/vr')       # the context scene; returns the manifest + a report
print(man['counts'], man['quest'], man['warnings'])
```

or headless, from a built `.blend` (it is opened, changed to fit glTF,
exported and NOT saved):

```sh
bash run_blender.sh blender/eidoblend/xr/export_cli.py work/<id>/scene.blend --survey      # nothing written
bash run_blender.sh blender/eidoblend/xr/export_cli.py work/<id>/scene.blend work/<id>/vr
bash run_blender.sh blender/eidoblend/xr/export_cli.py work/<id>/scene.blend work/<id>/vr \
    --street 0.25 --table 0.01 --start 0,-10 --compress meshopt --images WEBP --choreo crow_peck,cam
```

`export_cli.py` also takes `--facing X,Y`, `--name`, `--shadows`,
`--texel-density N`, `--max-texture N`, `--max-image N`, `--no-bake`,
`--no-motion` (instances and deformation go out still, at the first frame),
`--no-world`, `--world-frame F` and `--world-width W` (its docstring has them
all). A `.blend` opened headless starts without add-ons: the export turns the
VRM add-on on itself when the file holds a cast, so its MToon materials are
read as MToon. Then serve the bundle and open it in the headset:

```sh
python blender/eidoblend/xr/server.py --home /work/<id>/vr/index.html --log work/<id>/vr/results.jsonl
python3 eidoverse/xr/quest.py open https://<lan-ip>:8892/work/<id>/vr/index.html
```

`set_xr` saves the scene's XR settings with the `.blend` (in Blender's axes):
`street` is room metres per Blender unit when you stand in it (1.0: life
size), `table` metres per unit on the table (left out: the set's width fits
about 0.6 m), `start` and `facing` where you stand first (left out: where the
scene camera stands, looking where it looks, levelled), `table_centre` the
point in the middle of the table, `eye_height`, `name`, and `shadows` (the
page casts sun and spot shadows: a desktop cost, off by default). It also
writes the same two places as VR landmarks for Blender's own VR session
(below). `export_xr(out_dir, scene)` and `survey_xr(scene)` take any scene of
the file: it is made the context scene while they run (`context_scene`), as
the glTF exporter, the depsgraph and the bakes all read the context's.

`survey_xr(scene)` (and `--survey`) is cheap — no bake, no GLB — and says
what an export would do: objects by type, what glTF cannot hold, which
materials would be baked and which channels, the motion it would convert, the
animated values it carries or cannot, the lights, the world, the view, the
triangles rendering now, and the film's own image textures as the headset
would hold them, graded (`over` asks for `max_image`). Run it on a film before
exporting it.

### What the export writes

| File | What it is |
| --- | --- |
| `scene.glb` | Blender's glTF exporter: the whole timeline as ONE glTF animation sampled every frame (`export_animation_mode='SCENE'`), punctual lights, cameras, materials as below; only the page's own `xr_*` custom properties ride along as extras |
| `world.hdr` | the world rendered alone as an equirectangular Radiance image (Cycles), in three's equirect convention: the page's sky dome and its image-based light |
| `textures/` | the bakes (base colour + alpha, metallic-roughness, normal, emission) |
| `choreo.json` | timeline markers, the property tracks glTF cannot carry, and any `--choreo` object tracks |
| `scene.xr.json` | the manifest the page reads: the XR settings in three's axes, the view transform, area lights, page-side materials, counts and Quest grades, warnings |
| `index.html` | the page ([xr_page.html](../blender/eidoblend/xr/page/xr_page.html)), which imports `/eidoverse/xr/xr_kit.js` |

### What glTF carries, and what the export teaches it

| In the film | In the GLB |
| --- | --- |
| keyed transforms, NLA strips, VRMA clips on a VRM, drivers, constraints (Follow Path, Track To, Child Of ...), parenting | sampled every frame from the evaluated scene: TRS channels, skins with their joints |
| shape-key values | morph target weights |
| Geometry Nodes, particle or collection instances that move | `instances_to_objects`: one object per instance, keyed every frame, the mesh shared |
| a still scatter (or kit pieces placed by collection instances) | linked duplicates under one empty: `EXT_mesh_gpu_instancing` (one draw, three's InstancedMesh) |
| a mesh deformed by Geometry Nodes, Wave, a cloth or ocean cache | `deform_to_shape_keys`: a shape key per sampled frame (48 at most, 64 MB of morph data at most), cross-faded: morph targets |
| metaballs | their surface at the export frame, as a mesh |
| curves, surfaces, text | the exporter's own conversion to meshes |
| a procedural material (noise, ramps, bump, attributes, the camera) | `bake_for_gltf`: exactly the channels the exporter would drop, baked with Cycles onto a `gltf_bake` UV map |
| image textures through UV Map / Mapping / Normal Map / Separate Color | written as they are (no bake) |
| an unlit material (a colour into the output) | `KHR_materials_unlit`, baked when procedural |
| emission | the colour (normalised) and its strength: `KHR_materials_emissive_strength` |
| a VRM's MToon | its glTF-shaped settings on a Principled stand-in (base colour, normal, emission, alpha); outlines off |
| sun, point, spot lights | `KHR_lights_punctual` in Blender's own watts (lighting mode COMPAT, below) |
| area lights | three `RectAreaLight`s from the manifest (glTF has no area light) |
| light energy / colour, emission strength, visibility, keyed | `choreo.json` tracks the page applies every frame |
| the world | `world.hdr` (or, with `--no-world`, one flat colour, its radiance averaged over the sphere — measured with a 64 × 32 Cycles render when it is procedural — as the background and a uniform environment, which lights metals too) |
| an object tagged `xr_material` | drawn by the page with its own TSL material (below) |
| a haze or fog box (a mesh whose materials are volumes only) | left out and named in the warnings: the exporter would write it as an opaque grey box round the set |
| volume objects, Grease Pencil, hair curves, strand particles, speakers, light probes | not glTF: named in the warnings |

Two faults of Blender 5.2's glTF exporter are handled inside `export_xr`.
When it folds still instances into `EXT_mesh_gpu_instancing` it renumbers the
nodes but not the animation channels' targets, so a channel on a node listed
after the folded ones lands on another node (a spinning cube's rotation landed
40 nodes too far after 40 rocks were folded): the export re-points each
channel at its own node while the exporter runs, and `check_channels` reads the
GLB back for any channel past the end or any moving object without one. And
its own instance nodes (`export_gn_mesh`) double what it meshes itself — Blender
5.2 lists a text's or a curve's surface as instances — and break its
slide-to-zero pass: with the motion bake every instance is an object already,
so that option is off.

A baked normal map needs one tangent frame from end to end. Blender 5.2's
tangent-space normal bake writes its texels on the bake's UV map but in the
tangent frame of the mesh's *active* UV map (measured with three maps turned
against each other), and the exporter computes the GLB's `TANGENT` attribute
on the active map too. So `bake_for_gltf` makes its `gltf_bake` map the active
one (the active *render* map, which the film's own image textures read, stays):
the normal map, the GLB's tangents and the normal texture's own `texCoord`
then agree, and the page lights a baked bump's slopes as EEVEE does — on a
mesh with its own UV map too, in a viewer that makes its tangents again from
the texture's UVs as glTF prescribes, and through Draco.

Nothing is decimated. The manifest's `counts` (triangles, draws, texture
megabytes on the GPU, joints, morph targets) and `quest` grade the set against
the budgets measured in the performance notes below: triangles ok to 1.5 M
(heavy to 2.2 M), draws ok to 60 (heavy to 150), textures ok to 256 MB (heavy
to 512). Textures are the one budget the export can meet for you without
touching the set: `max_image=2048` (`--max-image 2048`) scales the film's own
image textures down to 2048 px on the long side for the bundle (in memory; the
`.blend` is not saved), since the headset uploads every texture uncompressed —
a 4096 px map with its mips is about 90 MB of its memory. My robot body's 4K
maps grade its walk `over` (783 MB) as they are, and `ok` (246 MB) at 2048.

The pieces work on their own too:

```python
from eidoblend.xr import materials as M, motion as MO, world as W
M.survey(bpy.data.materials)        # {'ground': {'kind': 'principled', 'lost': ['Base Color', 'Roughness', 'Normal']}, ...}
MO.detect(scene)                    # {'instances': [...], 'still_instances': [...], 'deforming': [...], 'skinned': [...]}
MO.animated_properties(scene)       # [('light', lamp_data, 'energy'), ('visibility', popper, 'hide_render'), ...]
MO.instances_to_objects(bpy.data.objects['crowd'])
MO.deform_to_shape_keys(bpy.data.objects['flag'], max_keys=48)
M.convert_mtoon(objects)            # a cast's MToon -> glTF-shaped Principled stand-ins
M.bake_for_gltf(meshes, 'work/<id>/vr/textures', texel_density=24)   # Cycles on the GPU: a GPU job
M.cap_images(meshes, max_size=2048)  # their image textures scaled down for the headset (in memory)
W.bake_world_equirect(scene, 'work/<id>/vr/world.hdr', width=2048)  # also a GPU job
MO.light_intensity(bpy.data.objects['key'])   # what a three light takes: lux, candela, or an area light's radiance
```

### Light, colour and the sky

- **Lights in Blender's units.** The export uses the exporter's COMPAT mode:
  a sun's W/m² is written as lux and a point or spot light's W as W / 4π
  candela, with no 683. three's physical lights read those exactly as Blender
  means them: a white diffuse surface facing a sun of S W/m² has the radiance
  S / π in both, and a point light of P W at d metres gives P / (4π d²) of
  irradiance in both. A Blender area light of P W and area A is a one-sided
  Lambertian emitter of radiance P / (π A), which is a three
  `RectAreaLight`'s intensity. A light's colour temperature is folded into
  its colour; with Normalize off, its power is multiplied by its area, as the
  exporter does. Keyed energy and colour play on the page for every kind,
  area lights included (`choreo.json`).
- **Area lights face where they face in Blender.** Blender's area light and
  three's `RectAreaLight` both shine down their local -z with the width along
  their local x, so the light keeps its own axes in three's world: its rotation
  there is M R (M the Blender-to-three turn), not the M R M⁻¹ a mesh's node
  takes (that leaves the light shining 90° off, at the sky). The glTF exporter
  corrects cameras and lights the same way; `choreo.quat_to_three` does it for
  the tracks.
- **Light at any scale.** The stage scales the set and the lights in it, but
  light does not scale by itself: a point or spot light falls off with the
  square of the distance the stage shrinks (on a 1:25 table a lamp would light
  the set 625 times brighter), and three sizes a `RectAreaLight` without its
  parents' scale. So every frame the page gives point and spot lights their
  intensity × s² (their range × s), area lights s times their size, and the
  spot lights' shadow cameras s times their range, s being the stage's scale:
  the table view is lit as the set is at life size (the tests hold the 1:25
  table against EEVEE through a camera 25 times farther away).
- **A sun's shadow is framed on the set.** three draws a directional light's
  shadow from a camera *at* the light, looking along it, but a Blender sun has
  no place: eidoblend's robot example and the flora tests leave theirs at the
  origin, under the set, where a box round the light sees nothing above the
  ground (no shadow at all). So each frame the page fits the sun's shadow box
  round the set's bounds as the light sees them (its near plane may lie
  behind the light), at any stage scale or turn, with its bias measured in
  shadow texels (two along the surface normal, one in depth), so a low sun
  across the fitted box leaves no acne.
- **Textures are filtered anisotropically** (8x, or the GPU's most): a film's
  floor at a grazing angle stays as sharp as EEVEE draws it.
- **The view transform.** The page tone-maps as the scene does: Standard →
  none, AgX → `AgXToneMapping`, Khronos PBR Neutral → `NeutralToneMapping`,
  Filmic → ACES (the nearest; a warning); the exposure carries over. Looks are
  not carried (a warning). three's AgX is Filament's fit of the earlier AgX,
  not Blender 5.2's: it draws darks a little lighter (a dusk sky Blender shows
  at 58 of 255 comes out at 71; mid-tones within about 5).
- **The sky.** `world.hdr` is the world at the export's first frame (or
  `world_frame`), linear and unclipped. The page draws it on a dome round your
  head that turns with the stage, and lights with it (`scene.environment`,
  turned with the stage too).

### Page-side materials

Some materials cannot become a texture: a grid whose lines stay one pixel wide
at every distance needs screen derivatives. Tag the object in Blender with the
custom property `xr_material` (and `xr_params`, a JSON string); the export
gives it a flat fallback material and the page draws it with its own TSL
material from the `PAGE_MATERIALS` registry in the page. The registry has
`grid` (the kit example's ground); add others there.

### The page

`index.html` is the kit example with the GLB as its stage: the same controls
(headset: left stick walks, right stick flicks 30°, X back to the start, Y
swaps street and table, the table slides, turns and scales, grip re-centres
it, the right trigger flashes; desktop: WASD and drag, V, F), telemetry to the
server, the veil and the laser. The film's clock loops. Stills take the
example's query (`?t=4&street=x,z&look=deg&pitch=deg`, `?t=4&view=table`;
`street` is three's x, z, so a Blender ground point (x, y) is `street=x,-y`)
and three more: `camera=cam_film` looks through an exported camera with the
world at life size (the same frame EEVEE rendered), `face=deg` turns the
facing you stand with, `shadows=1` turns shadows on.

## The kit's example in Blender

`EXAMPLES['city']` (`eidoblend.xr.examples`) builds
[example.html](../eidoverse/xr/example.html)'s small city in Blender from the
page's own numbers: its Park-Miller generator (seed 11) for the 36 towers, its
window shader (one window a unit at 0.8, 40 % lit) and neon roofs, its
antialiased grid (lines about 1.2 px wide at any distance, from the camera's
pixel footprint, since Blender's shader nodes have no screen derivatives), its
sky gradient as the world, and its 24 walkers moved by Geometry Nodes with the
page's formula. Two cameras stand where the page's views stand: `cam_street`
(the street view at 25 cm a unit) and `cam_table` (the desktop table view at
1 cm a unit). It renders with EEVEE under the Standard view, as the page draws
without a tone curve, and exports to a page that draws the same picture:

```python
from eidoblend.xr.examples import EXAMPLES
city = EXAMPLES['city'](bpy.context.scene)       # towers, ground, walkers, cameras, world; XR settings set
```

## Standing in the Blender scene itself

Blender's own VR session (the bundled *VR Scene Inspection* add-on, OpenXR; a
Quest through Quest Link or Air Link) shows the `.blend` itself in a headset,
lit by EEVEE, in Blender's window. `set_xr` writes the export's two places as
VR landmarks and the page's view as the session's settings;
`eidoblend.xr.landmarks` makes others:

```python
from eidoblend.xr import landmarks as LM
LM.stand_at(scene, (0, -10, 0), facing=(0, 1, 0), street=0.25, name='street')   # eyes 1.6 m at 25 cm a unit
LM.to_table(scene, centre=(0, 0, 0), table=0.01, name='table')                   # 1:100, 0.45 m ahead
LM.activate(scene, 'street')
LM.session_settings(scene)               # controller rays, no floor grid, 2 cm - 400 m clip, 2.6 m/s fly speed
cam = LM.view_camera(scene, 'table')     # a camera where the session starts: render what it will show
```

A session starts with your head AT the landmark (absolute tracking off),
turned by its angle about Z (0 looks along +Y), and `base_scale` world units
to a room metre: street 0.25 is base scale 4 with the eyes 6.4 units up. The
table follows `WorldRig.toTable`'s rule: the centre 0.45 m ahead, 75 cm below
the eyes and kept between 0.6 and 1.05 m off the floor (for `eye_height`), or
at `height`. Start it from the 3D view's sidebar (VR > Start VR Session). In a
session the add-on's own controls move you (teleport, fly on the sticks,
grab, reset); the kit's controls belong to the page.

## A piece's data

A built scene is all keys and baked caches (see [scene format](scene-format.md)),
so its positions and timings read straight out of the `.blend`, in three's axes
(Blender `(x, y, z)` is three's `(x, z, -y)`; `eidoblend.common.to_three`):

```python
from eidoblend.xr import choreo
data = choreo.sample_tracks(scene, ['crow_peck', 'crow_caw', 'cam'], step=2, rotation=True)
# {'fps': 24, 'track': {'crow_peck': [[t, x, y, z, qx, qy, qz, qw], ...], ...}}
choreo.markers(scene)                    # [{'name', 't', 'frame', 'camera'}]: cuts and cues
choreo.write(scene, 'work/<id>/vr/choreo.json', names=['crow_peck', 'cam'])   # + markers + property tracks
```

A track's rotation is the one a three object of that kind takes: a camera's
or a light's is the one a three camera or light takes (it looks down its own
-z: `camera.quaternion.set(qx, qy, qz, qw)` as it is); anything else's is the
one its converted geometry takes (a GLB node's).

## The kit

| File | What it is |
| --- | --- |
| [eidoverse/xr/serve.py](../eidoverse/xr/serve.py) | HTTPS server for the headset (+ HTTP on 127.0.0.1 for the desktop), self-signed certificate, `/report` telemetry log |
| [eidoverse/xr/xr_kit.js](../eidoverse/xr/xr_kit.js) | Browser module: renderer, session loop, world rig (street/table), controllers, desktop preview, head veil |
| [eidoverse/xr/example.html](../eidoverse/xr/example.html) | A complete minimal page on the kit |
| [eidoverse/xr/shot.mjs](../eidoverse/xr/shot.mjs) | Stills of a page from headless Chrome, through the same WebGL2 backend |
| [eidoverse/xr/quest.py](../eidoverse/xr/quest.py) | The headset over adb: Wi-Fi debugging, open a page, keep awake, pull recordings |
| [blender/eidoblend/xr/](../blender/eidoblend/xr/__init__.py) | The Blender edition: `export` (+ `export_cli.py`), `materials`, `motion`, `world`, `choreo`, `landmarks`, `examples`, the page template, `server.py`, `shots.py`, `glb` |

Pages import three.js from `node_modules` (run `python eido.py bootstrap`
once), so they use exactly the renderer's three version — no copied builds.

```sh
python3 eidoverse/xr/serve.py            # prints the headset URL: https://<this machine's LAN address>:8892/
python3 eidoverse/xr/quest.py wireless   # once per headset restart, over USB
python3 eidoverse/xr/quest.py open https://<lan-ip>:8892/eidoverse/xr/example.html
python3 eidoverse/xr/quest.py awake      # keep it rendering off-head
python3 eidoverse/xr/quest.py pull --sheet   # the newest recording, and a contact sheet of it
```

On the headset, accept the certificate once per address and port (Advanced ->
Proceed), then press ENTER VR. `serve.py --home /work/<id>/vr/index.html` makes
`/` open your page; `--log work/<id>/vr/results.jsonl` keeps its reports with
the piece. `blender/eidoblend/xr/server.py` is the same server (it runs
`serve.py`'s own handler) with the same options, and also serves `/blender/`
and takes `--node-modules <a checkout>/node_modules`: a git worktree has no
`node_modules` of its own. From Python, `server.start(...)` runs it in a
thread on a free port (`srv.url`, `srv.stop()`, or `with server.start() as
srv:`).

## Rules the kit encodes (learned in the headset)

1. **`WebGPURenderer` on its WebGL2 backend** (`forceWebGL: true`): the Quest
   browser has WebGPU for flat pages but no `XRGPUBinding` yet, so XR needs the
   WebGL2 path. TSL node materials work unchanged on it.
2. **Move the world, never the camera.** three r184's XR manager ignores the
   camera's parent in a session: a camera rig either does nothing (you spawn at
   the origin) or freezes head-locked. Put the whole world in a `stage` group
   and move that — `WorldRig` does.
3. **Never `renderer.setSize()` while presenting.** Entering VR fires a window
   resize; reconfiguring the swapchain kills the XR layer. `keepSized()` guards it.
4. **Arm a session by polling** `renderer.xr.getSession()` in the loop; the
   `sessionstart` event is not reliable. Count the session's own frames next to
   the loop's: if the loop runs and the session's frames stop, the XR layer has
   died (the heartbeat's `xrAlive`).
5. **In a headset there is no console.** Report to the server: heartbeats,
   measured fps, errors with their stacks. That log is how a session is read
   back afterwards — including where the viewer went.
6. **Fades and flashes go on a sphere round the head** (`makeVeil`): there is
   no screen for a full-screen quad.
7. **Stop screen mirroring (scrcpy) before a session**: its encoder load
   freezes immersive sessions. Record with the headset's own recorder and
   `quest.py pull`.

## A page on the kit

The exported page and the example are the references; the parts:

```js
import { telemetry, createRenderer, keepSized, startLoop, WorldRig, Pads, BTN, makeLaser, Desktop, makeVeil } from '/eidoverse/xr/xr_kit.js';
const report = telemetry('my_piece');                    // POSTs to /report; uncaught errors too
const { renderer } = await createRenderer();             // WebGL2 backend, local-floor, VR button
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.02, 400);
scene.add(camera); keepSized(renderer, camera);
const stage = new THREE.Group(); scene.add(stage);       // the world, in its own units, y up
const rig = new WorldRig({ renderer, camera, stage, street: 0.25, table: 0.01 });   // metres per unit
const pads = new Pads(renderer, scene), desk = new Desktop({ camera, dom: renderer.domElement });
rig.standAt(new THREE.Vector3(0, 0, 10), { facing: new THREE.Vector3(0, 0, -1) });
startLoop(renderer, scene, camera, {
  report,
  onSession: () => setTimeout(() => rig.standAt(START, { facing }), 300),   // once the head pose is live
  heartbeat: () => ({ mode: rig.mode, at: rig.where().toArray() }),
  onFrame: (now, dt, inXR) => {
    if (inXR) { pads.poll(); const L = pads.hand('left'), R = pads.hand('right');
      if (rig.mode === 'street') { rig.walk(L.x, -L.y, dt); rig.flick(R.x); } }
    else desk.update(dt);
  },
});
```

- **`WorldRig`** — `standAt(point, { facing, scale })` puts you at a stage
  point (on the ground) facing a stage direction; `toTable({ centre, scale,
  distance, height, at })` puts the world in front of you (or at room point
  `at`); `walk(right, forward, dt, speed)`, `turn(radians)`,
  `flick(stickX, step)` (30° snap turns), `spin`/`zoom`/`slide` for the
  table, `groundHit(origin, dir)` (where a controller ray meets the ground, in
  stage units), `where()` (you, in stage units). Street scale is metres per
  stage unit: at 0.12 a 1.7 m person stands 14 units tall. A Blender export is
  in metres, so `street: 1` is life size.
- **`Pads`** — `poll()` once a frame, then `hand('left'|'right')` gives the
  dead-zoned stick `x`/`y`, `pressed[i]`, `edge(i)`, `released(i)` and the
  pointing `ray`. `BTN`: `TRIGGER`, `GRIP`, `STICK`, `AX` (A right / X left),
  `BY` (B right / Y left).
- **`Desktop`** — the preview without a headset: WASD + drag to look in the
  street, drag to orbit and wheel to zoom on the table. On the desktop the
  camera moves; in a session the rig moves the world.
- **`startLoop`** — reports `sessionarmed`, `hb` every 3 s (frames, the
  session's frames, `loopAlive`, `xrAlive`, triangles + your `heartbeat()`),
  `measured` (fps over the first 10 s) and `contextlost`. `still: true` sets
  `window.__shot = 'ready'` after three frames, for `shot.mjs`.
- **`makeLaser`**, **`makeVeil`** — a pointing laser; a sphere round your head
  for fades and flashes.

## Checking without a headset

```sh
node eidoverse/xr/shot.mjs http://127.0.0.1:8894/work/<id>/vr/index.html work/<id>/shots \
    "t=4&camera=cam_film" "t=4&street=0,4&look=30&pitch=5" "t=4&view=table"
```

```python
from eidoblend.xr import server, shots
with server.start(log='work/<id>/vr/results.jsonl') as srv:          # a free port, in a thread
    rows = shots.shoot(srv.url + '/work/<id>/vr/index.html', 'work/<id>/vr/shots',
                       ['t=4&camera=cam_film', 't=4&street=0,4', 't=4&view=table'], size=(960, 540))
# rows: query, status ('ready' / 'error: ...' / 'TIMEOUT'), seconds, path, info (window.__shotInfo), errors
```

A page decides what its query means and sets `window.__shot = 'ready'` when
that moment is drawn (`'error: ...'` when it failed). Through `camera=` a still
is the same frame EEVEE renders, so the two can be laid side by side: the
tests do exactly that. `shots.shoot` (and `python blender/eidoblend/xr/shots.py
<page> <out> <queries> --size 960x540`) runs `shot.mjs`, reads its report back
per still (each still's exceptions and console errors with it), takes
`chrome=` for another browser, and gives Chrome's throwaway profile a
temporary folder of its own, removed afterwards (on Windows Chrome can still
hold it when `shot.mjs` cleans up, and `shot.mjs` then exits 1 after writing
every still).

Stills show the geometry, the colours and where things are — not the frame
rate, the comfort of the motion, or anything only a headset shows. Try it in
the headset before calling it done, and read the session's reports. Shots draw
on the GPU: on a shared machine, run them through the GPU slot like any
render.

The tests (`blender/tests/xr/`, `run_all.sh` runs them in order) cover the
path end to end: the kit's example rebuilt in Blender against the original
page; a lit, animated set with one of each thing glTF must be taught, number
by number against Blender, and its 1:25 table view against EEVEE at life size;
a bump baked on meshes with UV maps of their own under a low sun left at the
origin (the baked normals read back the glTF way, the page's shadows and
ridges against EEVEE's), and an export of a scene that is not the context
scene; four films round one built (a product shot lit by two area lights, two
crows, my robot walking with its maps capped at 2048 px, the look family's
theatre with its spot lights, haze and a camera cut), each photographed in
the page through the camera it shows at each time beside EEVEE's frame (EEVEE
with no compositor and no volumes, as the page has neither); the compressed
bundles; every `export_cli.py` option; `survey_xr` on five films; every
function and option of `xr_kit.js` on an exported stage (`kit_check.html`,
with a stand-in session for the loop, the pads and the rig in a session); the
servers; and every `quest.py` command against a stand-in adb.

## Performance notes (Quest 3)

Frame rates measured on real pages: a voxel city with about 1.4 million
triangles, 70 creatures and about 30 draw calls held 85–90 fps at the 90 Hz
default; the busiest stretch (2.2–2.3 million triangles) dipped to 75–80 fps.
Frame hitches come from the CPU side more often than the GPU: re-uploading big
instance buffers (upload only the changed ranges), work that grows with the
whole world every frame, and more than about 14 simultaneous HRTF-panned
sounds. `setFramebufferScaleFactor(0.9)` and foveation 1 are the kit's
defaults. An exported set's moving instances are one node and one draw each
(still ones share one instanced draw), so the manifest's draw grade is the one
a crowd moves first.

## Not yet ported

- **A session in a headset.** No exported bundle has been tried in a Quest
  yet: pages are checked in headless Chrome (stills against EEVEE and the
  original example; the kit's functions against a stand-in session) and their
  reports in the server log. Blender's own VR session has not been started
  either (no headset or OpenXR runtime on the machine that built this); its
  landmarks and session settings are written and read back, and their first
  views rendered.
- **Animated material values other than emission strength, camera lens and
  world animation**: the export warns, the page does not play them
  (`KHR_animation_pointer` would carry them; three's GLTFLoader does not read
  it). An emission strength track on a BAKED material sets the strength as
  keyed, not relative to the bake.
- **A sky that changes over the film** (`eidoblend.sky`'s baked layers): one
  frame of it becomes `world.hdr`.
- **MToon's toon look**: shade colour, rim, matcap and outlines (the page draws
  the Principled stand-in; three-vrm's MToon material would draw the real one).
- **Volumes, Grease Pencil, hair curves, strand particles**: not glTF; the
  export names them and the page shows nothing there (a haze box's light
  shafts and a theatre's beams included).
- **Blender's AgX on the page**: three's `AgXToneMapping` is a fit of the
  earlier AgX, so darks come out a little lighter than in EEVEE (above).
- **Occlusion of the world's light**: the page lights with `world.hdr`
  unoccluded and has no ambient occlusion, so the contacts EEVEE darkens (under
  a walker's feet, in corners) are lighter on the page; its sun shadows are
  there, and soften less than EEVEE's.
- **A deforming mesh over the morph budget** (more than about 1.3 million
  vertices, or a vertex count that changes): exported still, at its first
  frame, with a warning. Wind on a big meadow wants a page-side material.
- **Post effects** (bloom, depth of field, motion blur, the compositor): the
  page has none, by the kit's rules.
- **Audio**: the film's sound is not exported with the page.
- **Area light shadows**: three's `RectAreaLight` casts none, so what an area
  light shades in EEVEE (a stool's soft shadow on the floor, a crow's on the
  boards) is lit on the page; and area light spread under 180°, light shapes
  other than a rectangle (a disk becomes a rectangle of the same area),
  point lights' shadows (the page casts sun and spot shadows only), and
  punctual lights' shadow softness (the page's shadow maps are hard).
- **Texture compression** (KTX2 / Basis): images go in as PNG, JPEG or WebP
  and are uploaded uncompressed; `max_image` caps their size instead.
- **The kit's controls in Blender's own VR session**: the add-on's action maps
  drive it (teleport, fly, grab); its rays are light or dark, not the kit's
  orange laser, and it has no veil.
- The kit is unchanged and still WebGL2-only in XR (rule 1).
