# Cameras and lighting

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The Blender edition's look family lives in `blender/eidoblend/look/` (Blender
5.2, EEVEE). Every example below runs inside Blender with
`sys.path.insert(0, '<repo>/blender')`. The tests in `blender/tests/look/`
build and photograph each piece and are working examples. Coordinates are
Blender's: Z up, metres. A three.js `(x, y, z)` is `(x, -z, y)`
(`camera.three_to_blender`).

## Lighting

Choose lighting for the piece: the world-space sky, a studio rig, practical
sources, or a combination. PBR surfaces need illumination and reflective metals
need an environment to reflect. Emissive or unlit imagery is also available
when that is the intended look.

- The sky and its sun come from the [sky system](sky-weather.md). An HDRI
  belongs to the [scene format](scene-format.md). A test with no sky of its own
  uses a neutral uniform world and a sun light, not a stock sky standing in for
  ours (the look family's own tests do), and exposure numbers measured under
  it are the test's, not a film's. Indoors, the room's thick walls and its
  volume probe keep the world's light outside ([interiors](#interiors)).
- Add lights where they help the image: a key, a rim, a nearby display or a
  lamp. A point light near a wall brightens that wall with less spill on a
  distant subject; a sun has no distance falloff.
- Stage and practical lights belong to a fixture you could point at. Build each
  light WITH its fixture (`look/stage_rig.py`: par cans and profile spots hung
  on pipes, aimed by construction, each lens glowing at its own light's level,
  a dark lens when it's off). A light at a hand-picked point reads as light from
  nowhere: a hot spot on an arch, a pool with no lamp above it. Front-of-house
  lights must clear the proscenium. From 3 m in front of the arch, a cone wider
  than about 20° half-angle paints it (`rig.clears()` checks a fixture against
  the arch's face). Real FOH profiles are narrow for exactly that reason.
- A light's radius is its softness: `shadow_soft_size` for point and spot,
  `size` for area, `angle` for sun (the real sun is 0.53°). Give each light the
  size of the thing that emits it.
- Every light casts shadows in EEVEE: virtual shadow maps, traced soft. A mesh
  that must not block light gets `obj.visible_shadow = False` (three's
  `castShadow = false`).
- Coarse smooth-shaded geometry close to a light can self-shadow into
  triangle-aligned bands. The object's `shadow_terminator_normal_offset` and
  `shadow_terminator_geometry_offset` are EEVEE's settings for it; leave the
  materials alone.
- If a metal looks black, check the world, the probes and ray tracing
  (`trace_max_roughness`) before the material. Don't lower authored metalness
  to disguise a lighting problem.
- Inspect bright surfaces at full resolution, and measure them:
  [exposure](#exposure-measured) says where highlights clip.

### Units

Blender's glTF importer (5.2, `io_scene_gltf2`, 'SPEC' mode) defines the port.
Relative levels carry over; absolute levels are judged again under AgX, by eye
and by `look.exposure`.

| three.js | Blender | `look.lighting` |
| --- | --- | --- |
| DirectionalLight, lux | SUN strength W/m² = lux / 683 | `lux_to_sun(lux)` |
| Point / SpotLight, candela | POINT / SPOT power W = cd × 4π / 683 | `candela_to_watts(cd)` |
| SpotLight `angle` (half), `penumbra` | `spot_size` = 2 × angle, `spot_blend` = penumbra | `three_spot(angle, penumbra)` |
| `distance` | `use_custom_distance` + `cutoff_distance` | |
| Ambient / Hemisphere light | the world's colour (Blender has no ambient light) | |
| colour | `use_temperature` + `temperature` (Kelvin), or `color` | `kelvin(light, k)` |

### The sun, key / fill / rim, practicals

```python
from eidoblend.look import lighting as L
sun = L.sun(scene, elevation_deg=16, azimuth_deg=-70, strength=4.5, kelvin_k=4800)   # azimuth from +Y toward +X
rig = L.key_fill_rim(scene, subject=arm, camera=cam, key_w=250, fill_ratio=0.25)    # area lights placed from the camera
lamp = L.practical(scene, bpy.data.objects['LampBulb'], watts=6, kelvin_k=2700, strength=40)
L.log_lights(scene)                     # once at setup: name, type, power, size, temperature, shadow
```

A practical is an emitting surface AND a real light of the same size and
colour. An emission alone lights nothing reliably in EEVEE; it reaches other
surfaces only through probes and screen-space GI. A light alone is light from
nowhere. `practical()` makes the emitter glow, puts a light at its centre, and
turns off the emitter's `visible_shadow` so it never shadows its own light. A
lampshade around a bulb SHOULD cast shadows: that makes the pool below and the
scallop above (`test_corner_room.py`).

A sky shader has no sun disc in EEVEE: pair the sky family's sky with a sun
light from the same direction. `lighting.sun` takes its azimuth from +Y toward
+X, the convention of Blender's Sky Texture `sun_rotation` (measured).

### Stage lights — `look/stage_rig.py`

```python
from eidoblend.look.stage_rig import create_stage_rig
rig = create_stage_rig(scene, ceiling=4.6)
foh = rig.pipe(x0=-2.4, x1=2.4, z=4.38, y=-4.9)            # Blender axes: z is the height, y the depth
key = rig.fixture(type='profile', pipe=foh, x=0, target=(0, 1.0, 1.25), kelvin_k=4200,
                  watts=1400, angle=0.16, penumbra=0.35)   # -> Fixture(light, body, lens, ...)
rig.fixture(type='par', pipe=foh, x=0.7, target=(0, 1, 1), lamp=False)   # a dark fixture: no light object at all
key.light.data.keyframe_insert('energy', frame=30)         # key the level: the lens follows
print(rig.clears(key, y=-1.0, z=3.2))                      # {'ok': True, 'edge_z': 2.90}: under the arch
```

Each lens's emission is driven by its light's energy over the energy it was
mounted with, and goes dark when the light is hidden. There is no per-frame
`update()` (it exists and does nothing, so ported code runs). The light sits
3 cm in front of its lens and the fixture's parts cast no shadow. Unlike the
WebGPU rig, the lights cast shadows by default. Shadow maps cost something
there; in EEVEE they are cheap, and a stage without shadows reads as a render.
`test_stage.py` shows two FOH keys throwing two shadows on the curtain, a
profile keyed from 1000 W to 100 W with its lens dimming, and the wide profile
that `clears()` rejects painting the whole arch.

## Ray-traced lighting — EEVEE

`rt_lighting.js` traced shadows, one bounce of GI and reflections against a
proxy, then denoised. EEVEE does all three in the renderer, and traces every
final frame from scratch: no history, no warm-up, no `resetHistory` on cuts.
A frame rendered alone matches the same frame rendered after its previous
frame (`test_probe_modes.py`).

```python
rt = L.create_rt_lighting(scene, shadows=True, gi=True, reflections=True, refl_max_rough=0.6, gi_distance=0.6)
rt.update(); rt.reset_history()          # no-ops, kept so ported scenes run
```

Fast GI is always on: `gi=False` raises. `reflections=False` takes the
reflections from the light probes alone (EEVEE's Light Probe tracing), the
ray tracing that hosts Fast GI still on.

| `rt_lighting.js` | EEVEE |
| --- | --- |
| traced soft shadows, 8 light slots, `rtRadius` | every light shadows: `shadow_ray_count` × `shadow_step_count`; radius = the light's size |
| one-bounce GI, `keepFill` | fast GI `GLOBAL_ILLUMINATION` (screen space, dynamic) over baked volume probes (static bounce), indoors and out |
| reflections up to `reflMaxRough` | `use_raytracing`, `trace_max_roughness`; rougher lobes and misses fall back to sphere probes and the world |
| SVGF / OIDN / the WebGPU U-Net | the ray-tracing denoiser (spatial, temporal, bilateral); OIDN is the compositor Denoise node, for low-sample previews only |
| debug views | `lighting.debug_passes(scene, out_dir, passes)`: light passes as EXRs |

The lessons carry over:

- Lights must be where their light can reach. A lamp above a ceiling slab
  shadows the whole room.
- A dark fixture carries no light object (`lamp=False`).
- A broad, even source the tracer has no light for goes dark. There is no
  `keepFill`: a hall's house light is real lights or emissive panels, plus a
  baked volume probe.
- When a subject goes dark under the set's own light, light it the way a stage
  would: a practical special on it (a riser top-light), not shadows or GI
  turned down.

**Probes.** Volume probes carry the static bounce; reflections come from ray
tracing plus sphere probes, which EEVEE refreshes itself. Bake the volume
probes once the scene's static light is in place, with what moves and the
haze left out (`exclude=`): a probe is static, and moving emitters carry
their light with real lights.

### Interiors

An interior holds its light as a real room does, with global illumination
on, Fast GI included:

- **Walls with real thickness.** Build the room as a closed shell of solid
  walls: the floor and ceiling run under and over the walls, the walls meet
  at the corners, and every piece is a closed mesh with its normals out (a
  box per wall, or a Solidify modifier), never single-sided planes, so the
  probe and the screen-space GI both see a closed room. A window is a hole in
  a wall; a glass wall is not solid, and what stands beyond it lights the
  room through it.
- **A volume probe that covers the room.** EEVEE lays a volume probe's
  samples inside its box and lights a surface near the box's faces, or
  outside it, from the world. `add_room_probe(scene, name, inner_min,
  inner_max, wall=)` takes the room's inside corners and its walls'
  thickness and reaches the box past every inside face: the outermost
  samples sit half a spacing inside the walls (the bake rejects them, as
  they see only the walls' back faces), and every inside surface lies
  between the room's own samples. The spacing defaults to the walls'
  thickness (at most 0.4 m); walls thinner than about 0.6 × the spacing are
  refused. `add_volume_probe` takes a box directly when the set isn't a
  room.
- **Real light sources.** A window lets the sun and sky in through its
  opening; a lamp is a light with its fixture (above). Light the room the way
  it would be lit, then measure the exposure.

```python
L.add_room_probe(scene, 'room', inner_min=(-2.2, -2.0, 0.0), inner_max=(2.2, 2.0, 2.7), wall=0.3)  # 0.3 m walls, samples 0.3 m apart
L.add_sphere_probe(scene, 'room_refl', centre=(-0.5, 0.6, 1.0), radius=3.0)
L.bake_light_probes(scene, exclude=[haze_collection])     # a GPU job: one render at a time
```

**Light passes.** `debug_passes` writes Diffuse Direct, Glossy Direct,
Shadow, Ambient Occlusion, Normal, Depth (and Vector, with motion blur off)
through one compositor File Output node per pass. See
[stack notes](stack-notes.md) for why it is one node per pass.

## Exposure, measured

AgX is the tone map (three's ACES becomes the scene's view transform). Where
it puts things, measured through Blender 5.2's own OCIO config with AgX Base
Contrast at exposure 0:

| scene-linear | 0.02 | 0.09 | 0.18 | 0.36 | 1.0 | 4 | 8 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| display (of 255) | 32 | 82 | 117.6 | 154 | 197 | 233 | 245 | 254.6 |

A grey channel reaches 250 about 6 stops above 18% grey; a saturated one
sooner. Against three's ACES Filmic, plain AgX lifts the deep darks and holds
the highlights lower; the look `AgX - Medium High Contrast`
(`sets.unknown_force.cn_lib.ACES_LIKE_LOOK`) comes closest to the WebGPU
frames' tones, for every scene in the file (the table is in
[props and sets](props-and-sets.md#light-tone-and-the-world)). The highlight rule: in a delivered frame, the share of pixels with any
channel at 250 or above stays near zero (0.1% by default). No 16 × 9 grid cell
may hold a clipped region (2%): a glint is small, an overlit wall fills a
cell.

`look.exposure` renders once and judges every exposure from that render, then
confirms its choice with real renders. `Image.save_render` applies the scene's
view transform at save time, so a sweep of 29 exposures costs one render plus
29 small saves. The sweep is exact on flat areas and approximate along
high-contrast edges. EEVEE's film accumulation sees the view exposure, so a
frame rendered at +2.25 differs from the exposure-0 render saved at +2.25 along
silhouettes, shadow edges and the horizon: up to 56 levels at single pixels,
6% of pixels over 2 levels. The clip shares moved by thousandths of a percent
and no verdict changed, but `auto_expose` renders at its ceiling and its pick
anyway. It walks either one a step down while a real render fails the
highlight check, and the ceiling a step up while one passes. `ae['confirmed']`
records what the renders said.

```python
from eidoblend.look import exposure as EX
scene.frame_set(60)                        # the shot's brightest moment: the subject in full sun
ae = EX.auto_expose(scene, out_dir, region=subject_box)   # metered to 18 % grey, the clip check as the ceiling
print(ae['pick']['reason'], ae['pick']['ceiling'], ae['pick']['headroom'])
```

Metering puts the frame's median at the view's own 18% grey
(`mid_grey_luma(scene)`: 117.6 for AgX Base Contrast, 88.3 for Punchy). If
that exposure clips, the pick is the brightest one below it that doesn't.
`key='region'` meters the subject's box instead, which is right for a dark
stage. `mode='brightest'` takes the ceiling itself. That is high key: it
pushes everything into AgX's shoulder, washed and flat, so it is a ceiling,
rarely an exposure. On the meadow test (the fixture's neutral world and its
sun, not a film's sky) the metered pick was +0.50 (median 119), and the
ceiling +2.25, both confirmed by real renders (+2.50 fails). One stop past the
ceiling, the sunlit white shells and the orange crown filled a grid cell at 22%
clipped, and the check named it a clipped region. `frame_stats.clip_mask`
paints those pixels magenta. In the dim corner room the metered exposure clipped
the window and the lamp, so the pick was the ceiling. The sweep put it at
+1.75, and real renders passed up to +2.25, which became the pick. These are the
fixtures' numbers: a film meters under its own sky and sets.

`probe.render_stills` measures every still it writes. `frame_stats.py` measures
PNGs or a video outside Blender (exit 1 when a frame fails). The False Color
view (`probe_cli.py --false-color`) shows AgX's exposure zones.

## Camera targets and framing

An asset's origin may sit at its feet, a mounting port or an authoring pivot.
For a bounds-based target:

```python
from eidoblend.look import camera as C
C.look_at_object(cam, arm, y_bias=0.3)       # an armature counts through its posed child meshes
target = C.focus_point(desk, y_bias=0.25)    # the evaluated world bounds' centre, raised by y_bias x the height
hips = C.bone_target(arm, 'hips')            # a VRM humanoid bone, as a function of the current frame
```

`y_bias` keeps the WebGPU name; in Blender it is a fraction of the height along
Z. Bounds are read from the evaluated objects, so a posed character is measured
in its pose. Check the actual composition for the current pose, especially with
skinned or asymmetric subjects. An explicit world-space target remains useful
for a chosen detail or empty space.

**Lens.** `make_camera(name, fov=34)` takes three's VERTICAL fov, or `lens=` in
mm. The sensor stays a real 36 mm full-frame one (fit AUTO), so depth of field
behaves as on that camera. `set_fov(cam, deg, 'vertical'|'horizontal')`;
`fov_of(cam, scene)` returns (horizontal, vertical). Three's 34° vertical at
16:9 is a 33.1 mm lens, 57.05° horizontal.

Keep the camera outside the geometry it photographs. Measure bounds and judge
the lens and standoff together. A fixed distance in metres is not right for
every asset scale or close-up.

## Camera moves

Every move is baked: the target is sampled at every frame of the shot, smoothed,
and the camera is keyed per frame with linear interpolation. A still at any
frame is therefore what the film shows there. The camera has one owner (its
keys), and the audits read what renders. Smoothing looks both ways: a centred
Gaussian over the target's track, sigma = `smooth_s`. Offline, the operator
knows where the subject is going, so the camera neither lags nor overshoots.
`lag_s` instead ports the WebGPU per-frame lerp, an exponential follow that
trails.

```python
# the meadow's tracking camera: low, ahead of me on my left, easing round as I come on
cam = C.make_camera('cam_track', fov=34, fstop=2.8)
C.track(scene, cam, (1, 120), hips, offset=lambda u: off(u), height=1.3, aim_height=1.05,
        aim_offset=(0, 0.25, 0), smooth_s=0.5)                 # offset: a Vector, or a function of u = 0..1
# its tripod shot: turning to follow me past
C.pan(scene, cam2, (121, 240), (-3.6, 1.2, 1.3), hips, follow='xy', aim_height=1.1, smooth_s=0.4)
C.dolly(scene, cam, (1, 96), start, end, aim, ease_kind='smooth')   # one eased move per shot
C.push(scene, cam, (1, 48), metres=0.6)                              # along the view axis
C.orbit(scene, cam, (1, 96), centre=hips, radius=3, height=0.5, deg_start=0, deg_end=60)   # 0.5 m above the hips
C.zoom(cam, (1, 48), 35, 50)
C.hold(scene, cam, (1, 48), position, aim, handheld={'deg': 0.25, 'metres': 0.004, 'hz': 0.5, 'seed': 3})
```

`follow='xy'` keeps a walk's hip bob out of the camera. The camera and the aim
then hold the target's mean height over the shot (`offset.z` above it for
`track`), unless `height` / `aim_height` set them; `aim_height` sets a pan's aim
whatever `follow` says. `orbit`'s `height` is above the centre point itself (an
object's bounds middle, a bone's head), not the ground. `orbit_offset(radius,
deg_start, deg_end)` builds a swinging offset for `track`. `handheld` adds
smooth noise (pitch, yaw, roll and a few millimetres of drift) baked into the
same keys. The default is subtle and passes the bounce audit. Choose pace and
amplitude for what the viewer should experience.

Unexpected bouncing usually comes from a noisy target (a bone that bobs), FOV
oscillation or competing owners. Smooth the target the camera follows, rather
than adding another layer on the camera.

## Depth of field and focus pulls

Depth of field is the lens's, not a post blur: the f-stop with the focal length
and sensor.

```python
C.focus_on(scene, cam, (1, 120), C.bone_target(arm, 'chest'), fstop=2.8)   # an empty keyed on the target every frame
mark = C.point_in_frame(scene, cam2, (0.30, 0.58), frame=121)   # the surface under that point of the picture
C.focus_on(scene, cam2, (121, 240), {'point': mark},
           rack={'to': chest, 'frames': (128, 150), 'ease': 'smooth'})      # a rack: the far meadow -> me
C.dof_limits(cam, 4.18)       # {'near': 3.20, 'far': 6.03, 'hyperfocal': ...}: the meadow's track, f/2.8 on 33 mm
C.view_depth(cam, point)      # the depth the lens focuses by: along the view axis, not the straight line
```

`focus_on` keys an empty (`focus_<camera>`) at the target and sets it as the
camera's focus object. Distances are view depths: Blender's plane of focus is
parallel to the sensor, and a focus object's distance is its depth along the
view axis (`focus_depth(cam)` reads it as the renderer does). A rack starts on
something the audience can see. `point_in_frame` picks the mark as a focus
puller would, the first surface under a point of the picture, instances
included. The meadow's rack first started on a point 1.5 m from the lens and
under the bottom edge of the frame, so for half a second nothing in the picture
was sharp. Now it starts on the meadow beyond the path, 12.9 m out, and pulls to
my chest at 3.7 m. `focus_audit` (below) checks the subject stays inside the
sharp zone and that something in the picture is sharp.

## Shots and cuts

A cut is a timeline marker bound to a camera; renders and playback switch
there.

```python
C.add_shot(scene, 'track', 1, cam1)
C.add_shot(scene, 'pan', 121, cam2)
C.shot_spans(scene)           # {'track': (1, 120, cam1), 'pan': (121, 240, cam2)}
C.camera_at(scene, 150)       # the camera that renders frame 150
```

## CameraSafety

`look/camera_safety.py`. Sightlines, clearance, and the whole keyed path,
checked frame by frame. Walking the animated path was too costly to do every
frame in WebGPU; in Blender it takes seconds.

```python
from eidoblend.look.camera_safety import CameraSafety
cs = CameraSafety(scene, padding=0.5, min_distance=0.3)
cs.exclude(*grass_scatters)                  # foliage the camera may look through (with what it instances), haze
cs.exclude(arm, sightline_only=True)         # the subject: never its own obstruction, still needs clearance
issues = cs.check_camera(cam, (1, 120), target=chest)
issues = cs.check_path([{'time': 0, 'position': (2, -7, 1.6), 'target': (0, -3, 1.2)},
                        {'time': 2, 'position': (0, 3, 1.6), 'target': (0, -3, 1.2)}], samples_per_segment=12)
pos = cs.safe_position(desired, target)
```

`check_camera` reports each problem once, as a run of frames:

- `inside`: the lens is behind a surface (inside a closed mesh, under the
  ground).
- `clip`: a surface is closer than the near clip plane.
- `tight`: a surface is closer than `min_distance`.
- `blocked` / `tight_sightline`: something sits on the sightline from what it
  looks at back to the lens.

`check_path` and `safe_position` are the WebGPU API: issues with a severity
and a suggested clear position on a sphere round the target.
`test_camera_checks.py` drives a dolly through a wall (flagged at the frames
where the lens meets it), a camera under the ground, and a planned key behind
the wall. `safe_position` during motion jumps as occluders change. Prefer
fixing the path, then review the rendered sequence.

**Instances.** A ray that meets a Geometry Nodes instance reports the
instanced object (the scatter's source, `grass_medium_02_d`), never the
scatter. So `exclude(scatter)` looks up the depsgraph's instance list and
excludes what the scatter instances, whether it is a Geometry Nodes scatter, a
collection instance or a particle system. Excluding the scatters alone used to
leave the grass blocking: a camera low in the grass was flagged blocked by
blades. An instanced object that also renders on its own, or through a scatter
that isn't excluded, is told apart per hit by the instance's matrix, and it
still blocks. `test_camera_checks.py` checks all three cases with posts on a
sightline. The meadow test has a long lens 12 cm up in the grass, its sightline
running from my ankle through 5 m of blades: without the exclusion, 6 of 61
frames are blocked by grass; with it, none. Clearance tests only what renders.
A scatter's sources in an excluded collection are skipped, and instanced
geometry has no clearance test, so check those in the stills.

## Camera audits

`look/camera_audit.py`, run per shot from the markers. Each returns ledger
records ([render review](render-review.md#structured-audit-records)).

```python
from eidoblend.look import camera_audit as CA
CA.camera_motion_audit(scene)                 # bounce: direction reversals of position, fov and aim
CA.framing_audit(scene, subject=arm)          # the subject's share of the frame, middle and last frame
CA.focus_audit(scene, chest, every=2, allow_soft={'pan': (121, 150)})   # a rack's soft start is by design
```

- **Bounce** keeps the WebGPU rule, restated in seconds so 24 and 30 fps judge
  alike: more than 5 reversals a second with a swing above 0.6 m/s (position),
  9°/s (fov) or 9°/s (aim, which the WebGPU audit didn't watch). Counting
  within a shot means a cut is not a reversal. A 3 Hz `sin()` dolly fails; one
  eased dolly and a hand-held camera pass.
- **Framing**: a subject under 6% of the frame is a speck and "RE-RENDER".
  Name the subject; without one it falls back to the mass-cluster heuristic.
- **Focus**: the subject's view depth against the near and far limits of
  sharpness at the focus distance, reported as runs of soft frames, one record
  each. A rack that leaves the subject soft is flagged at the frames where it
  is. `allow_soft` marks frames where a soft subject is intended (a rack's
  start, recorded as INFO); softness anywhere else in the shot is still its own
  WARN, so a late regression isn't hidden behind the shot's worst frame.
- **Something sharp**: `camera.focus_sharp` casts a grid of rays through the
  frame and asks what share of the picture lies inside the depth of field.
  Under 1%, the focus sits on something off-screen or in empty air. It flags a
  focus 1 m out in empty air at f/1.4. The meadow's rack holds at least 14% of
  the frame sharp at every checked frame.

None of these proves composition. View the probe stills.

## Not yet ported

- `scene_placement.js`'s camera helpers beyond `focusPoint` / `lookAtObject`
  (none of the others are camera-specific).
- The terminator offsets on the robotics kit's cast parts, checked in EEVEE.
- A per-frame `safe_position` follower (`safe_position` exists; a smoothed
  per-frame correction pass does not).
- Clearance against instanced geometry (a camera inside a scattered rock is
  not flagged `inside`; sightlines do see instances).
- A chrome sphere's reflection of what lies behind the camera, in a closed
  test room, shows thin bluish lines in the pattern of the room's edges: the
  sphere-probe setup for off-screen mirror reflections indoors is not settled.
- `oidn.js`, `nn_denoise.js` and their weights: Blender's denoisers are native
  (the compositor Denoise node), so these are dropped rather than ported.
