# Volumetric fire and smoke simulation

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

`eidoblend.fx.fire` is the Blender edition of `fluid_grid.js`, which is itself a
verbatim port of three.js's `webgpu_volume_fire` example. The solver is the
engine's, kernel for kernel, as GLSL compute through Blender's `gpu` module:
rgba16float 3D textures, linear samplers, the same constants and the same
dispatch order. Each 1/120 s × `sim_speed` substep advects velocity (buoyancy,
thermal and ambient curl turbulence, damping, wind from the burning mesh, a
soft border), takes the divergence, runs an even number of Jacobi pressure
sweeps, projects, advects the dye (density, temperature, age) and emits from
the burning mesh.

A fire has three phases. **Build** makes the Volume object, its material and
the fire's lights. **Bake** steps the simulation over the shot and writes one
`.vdb` per frame. **Playback** is Blender's own: scrubbing, re-rendering and
render passes read the cache, so nothing is replayed.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.fire import create_volume_fire, configure_eevee_for_fire, create_fire_compose

fire = create_volume_fire(burning_mesh, key_light=key_spot, cache_dir='//fire_cache')   # look='engine'
fire.make_lava_emissive(burning_mesh.active_material)     # optional: the example's glowing cracks
fire.make_fire_glow(burning_mesh.active_material)         # optional: the fire's glow on the mesh (below)
fire.bake(1, 240)                                         # warmup, then one step per frame
configure_eevee_for_fire(scene, fire, camera)             # froxels, volume shadows, a tight depth range
create_fire_compose(scene, fire)                          # saturation 1.1, then bloom
```

Set the scene's view transform, display and exposure before
`create_volume_fire`: its look is matched to them when it is built.

The bake leaves the Volume playing its files as Blender plays any `.vdb`
sequence: scene frame f reads file f, and frames outside the bake read
none. Render in the session that baked, or save the `.blend` and render
that: both read the files. Leave the Volume's grids to the depsgraph and
never call `fire.volume_object.data.grids.load()`. On the datablock, a load
reads the frame the datablock last played, which is 0 until the sequence
has played (right after the first bake, for one), so it asks for
`<name>_0000.vdb`, a file a bake from frame 1 never writes. Blender keeps
that failed load's error on the datablock, and every viewport and render
copy inherits it: the copy reads its frame's grids but reports the load as
failed and its bounds as empty, and EEVEE draws no volume until the file is
opened again (`test_fire_bake.py`).

Bake a fire again in the same Blender session and its frames go to
`<name>_bake2_####.vdb` (then `_bake3`, and so on), with its shadow maps,
and the Volume plays those; `fire.stem` names them. Blender keeps the grids
of every `.vdb` it reads for the rest of the session, by the file's path.
Frames written over files the session has played would go on playing the
first grids, through the same Volume, a new Volume datablock,
`VolumeGrids.unload()` or the `.blend` opened again in the same Blender
alike: an empty bake written over the teapot's frames still played the
teapot's gas (`test_fire_bake.py`, rebake). The bake takes the first of
`<name>`, `<name>_bake2` ... that no fire has played in this session and no
Volume in the open file plays. The earlier frames stay on disk, for any
Volume still playing them. A new session, with no Volume in its open file
playing `<name>_####.vdb`, bakes under `<name>` again.

The bake runs on the GPU, so on a shared GPU run it one at a time, like a
render. The full 100 × 200 × 100 grid bakes in well under a minute: on a
busy shared GPU the teapot's 400 warmup substeps plus 48 frames took 26 s,
12 s of it waiting on the GPU and 10 s writing the `.vdb` files, about
2.8 MB a frame.

Every frame advances 1/fps × `sim_speed` seconds of simulation, at any frame
rate. The engine's `step()` capped a frame's delta at 1/30 s, and its
accumulator at 8 substeps, so a browser that dropped frames could not
spiral. A bake drops none, and that cap would run a 24 fps film at 0.8×
speed (0.04 s of simulation a frame instead of 0.05 s). The engine's own
films rendered at 120 fps, where the cap never acted, so the bake leaves it
out. The teapot probe ends frame 48 at 6.41 s of simulation: 4 s of warmup
plus 48 / 24 × 1.2.

## The mesh that burns

Pass the object itself. With `emitter_points=None`, emission dispatches over
the evaluated mesh's raw vertices, as the example does. With a number, it
uses that many seeded, area-weighted surface samples instead, which suits
low-poly meshes with uneven vertex density. Either way the points are read
once at the first frame, in the object's local space. The object's animation
is sampled at every substep's subframe, so a moving or spinning emitter
stirs the fire and drives the wind term through its speed and velocity.

The warmup (`warmup_seconds`, 4 s of simulation) runs before the shot. The
engine kept moving the mesh through it, through `onTemporal` (the example's
teapot spins on simulation time). Here an animated mesh is evaluated at the
warmup's own pre-roll frames: the warmup ends at `frame_start − 1`, and its
clock runs `sim_speed` times faster than the scene's, as every frame's
does. Keys hold still before their first key unless their F-curves
extrapolate, so give the motion a linear extrapolation or a driver on
`frame`, as the teapot probe does:

```python
drv = teapot.driver_add('rotation_euler', 2).driver
drv.expression = '(4.0 + frame / 24 * 1.2) * 0.25'      # the example's rotation.y = simTime * 0.25
```

The wind term stays at rest through the warmup, as it did in the engine.

Scale and placement: the domain defaults to the example's 12 × 24 × 12 m
(`world_size`, Blender axes, Z up) at 100 × 200 × 100 cells. It is centred
on `origin` in X and Y and rises from it in Z. The example burns a teapot
about 1.6 m across (`emitter_radius` 1, `flame_height` 3.5). Put the mesh
inside the domain at that kind of scale. A small mesh, or one below the
domain's floor, emits little or nothing and reads as a faint glow.

## What `create_volume_fire` returns

| Attribute | Engine name | What it is |
|---|---|---|
| `volume_object` | `volumeMesh` | the Volume object playing the `.vdb` sequence (grids `density`, `temperature`, `age`) |
| `point_light` | `pointLight` (surfaces) | the fire's light on surfaces: no shadows, volume factor 0 |
| `volume_light` | `pointLight` (volume) | the same light's volume branch: at the flame column's centre, 1.2 m soft radius, volume only |
| `shadow_mesh` | `shadowMesh` | with `shadow_floor`: the smoke's shadow caster over the ground (below); otherwise `None` |
| `material` | `volumetricMaterial` | the volume material |
| `params` | `params` | the resolved options |
| `sim_time` | `simTime` | seconds of simulation after the last bake |
| `stem` | (none) | the last bake's frames are `<cache_dir>/<stem>_####.vdb`: the fire's `name`, or `<name>_bake2` ... for a fire baked again in the same session (above) |
| `bake()` | `warmup()` + `step()` | the whole shot, plus the light keys |
| `make_lava_emissive(mat)` | `makeLavaEmissive` | adds the lava cracks to a Principled material |
| `make_fire_glow(mat, strength=1)` | (the volume pass seen through the mesh) | the burning mesh glows with the gas round it (below) |

The engine's light was one light whose colour node took two branches: a
uniform colour and a soft column attenuation for the volume, and plain
inverse square for surfaces. EEVEE gives each light diffuse, specular and
volume factors, so the port uses two lights. `bake()` keys their energy,
colour, cutoff distance and position on every frame from the engine's CPU
`ImprovedNoise`: flicker, sway, flame height, colour noise and the 3 s
fade-in. Light power converts three's candela as P = 4π·I watts, which gives
the same irradiance under both renderers' BRDF conventions.

## Controls

The options are the engine's, in snake_case: `buoyancy`, `weight`,
`turbulence`, `turbulence_decay`, `turb_frequency`, `vel_damping`,
`fire_lifespan`, `smoke_lifespan`, `emit_density`, `emit_temperature`,
`motion_boost`, `wind_strength`, the three `fire_*_color`s, `fire_hue`,
`fire_glow_spread`, `fire_intensity`, `mesh_emissive_intensity`,
`saturation_amount`, `flame_height` and the light intensities. To change
any of them over the shot, pass a callback:

```python
fire.bake(1, 240, controls=lambda frame, t: {'wind_strength': 6.5 + 4 * (t > 3), 'emit_density': 7.0})
```

Eight of the engine's options shaped its own raymarch and light node:
`shadow_absorption`, `shadow_ambient`, `powder_strength`,
`multi_scattering` and the four `projection_*`. `create_volume_fire`
refuses each, in either spelling, with what EEVEE does in its place
(`fx.fire.ENGINE_ONLY`; see Not yet ported).

Changing an option means baking again. The cache is the fire, and the
same scene bakes the same grids every time, byte for byte
(`test_fire_bake.py`: three bakes of the teapot). The engine's emission
kernel had each emitter point read its voxel, add its gas and write the
voxel back. Where points share a voxel, the GPU kept whichever store landed
last, a different one from run to run: three bakes gave frame 1 a peak
density of 3.26, 3.38 and 3.38. The port emits in two passes. The first
works out every point's store as the engine's kernel did. The second keeps
one store per voxel, drawn afresh every substep by a hash of the point's
index and the substep's number, as the race drew it.

Over the teapot's 48 frames that keeps the race's look: the grids' total
density and temperature come to 1.04 of the mean of six racy bakes, whose
own runs spread from 0.97 to 1.05. Over the first 12 frames they come to
1.09 and 1.06, where the racy runs spread from 0.95 to 1.03. A fixed order
would not keep the look: keeping the last point in buffer order every time
gave 0.71, a thinner fire whose smoke sits lower. The teapot renders show
the same fire either way: the same tongues, plume and drifting smoke. At
frames 1, 24 and 48 a render of the port's bake differs from a racy bake's
by 0.012 to 0.016 of full scale per pixel on average, where two racy bakes
differ by 0.010 to 0.011, and the port's flame and smoke column is a little
brighter. The second pass costs no measurable time: baking the teapot's 48
frames with each kernel in turn in one session, the GPU took 11.8 and
12.2 s with the engine's one pass, 12.1 and 12.8 s with the two.

## The look in EEVEE

The material keeps the engine's emission term:
`fireRamp(T) · T^(6 − glow_spread) · fire_intensity`, hue-rotated, ×
`(density + 0.15)` × 400/d² to the key light, × 0.01 per metre. It also keeps
the simplex detail noise on density, an exact node port of the TSL `snoise`
that matches the numpy port bit for bit. The velocity domain warp and the
box-edge fade are baked into the grids. Everything else is EEVEE's physically
based volume rendering: real extinction, volumetric shadows and the scene's
lights. Three Blender-side controls stand in for the engine's raymarch terms:

- `smoke_density` (0.15) is the extinction per metre per unit of density. At
  0.15 the smoke is as bright as the engine's, because its in-scatter was
  0.01 · ρ · I/d² per metre. The camera ray then stays nearly as clear as
  the engine's, which barely attenuated it.
- `flame_clarity` (0.85) is the share of that extinction that burning gas
  loses. EEVEE's extinction is physical, and without this the hot core hides
  inside the smoke it emits.
- `emission_scale` (1) multiplies the engine's per-metre emission.

`configure_eevee_for_fire(scene, fire, camera)` sets 1-pixel froxels, 128
depth slices and volumetric shadows. It also sets the froxel depth range
from the bake's bounds as the camera sees them over the shot. Without that,
the slices spread over the whole empty domain and the flame goes soft.

The range is one scene setting, and Blender 5.2 cannot key or drive it, so
it fits one camera at a time. A range fitted to one camera can leave the
fire outside another camera's slices, and then no volume renders at all.
With timeline markers bound to cameras (Blender's own camera cuts) and no
`camera` argument, it takes the union of every cut's range: no camera
clips the fire, but the slices spread thinner. A render script that
switches `scene.camera` any other way calls it again before each shot:

```python
for cam in (wide, close):
    scene.camera = cam
    configure_eevee_for_fire(scene, fire, cam)
    bpy.ops.render.render(write_still=True)
```

### The smoke's shadow on the ground

EEVEE's volumetric shadows act on volumes, not on surfaces: under a sun, a
spot or a point light straight above, a 1 m cube of smoke that Beer-Lambert
puts at 0.135 transmittance passes all of the light to the floor below
(`test_fire_shadows.py`: 1.000 with volumetric shadows on or off, where the
same cube made opaque passes 0.002 to 0.004). The engine cast the smoke's shadow
with a separate object, `shadowMesh`, and the port does the same with what
EEVEE has:

```python
fire = create_volume_fire(burning_mesh, key_light=key_spot, shadow_floor=0.8)   # the ground's height (Blender z)
fire.bake(1, 240)                       # also writes <name>_shadow_####.exr beside the .vdb frames
```

`fire.shadow_mesh` is a plane `shadow_lift` (5 cm) over the ground, seen by
shadow rays only. Its material is opaque where the smoke stops the key
light and clear where it does not, through EEVEE's transparent shadows. For
every baked frame, the bake marches each of its `shadow_resolution` ×
`shadow_resolution` texels toward the key light through that frame's grids,
64 steps across the domain, with the volume material's own extinction
(`smoke_density`, the burning gas clearer by `flame_clarity`, and the
detail noise's 0.85 on average), and writes the transmittance as an image
sequence the plane plays. Under a 2 m slab of smoke at density 1 the march
gives 0.769 against Beer-Lambert's 0.775. In the teapot scene the map moves
with the smoke: between frames 12 and 24 its shaded texels change by 0.040
in transmittance on average. A frame's map takes 0.6 to 0.9 s at 128 × 128;
the march's sample points are worked out again only when the key light
moves. The plane covers the ground the domain can shadow from
where the key light is when the fire is built, up to twice the domain
round it.

The lift keeps the caster clear of EEVEE's shadow bias. On the teapot
scene's floor, under the key spot, a caster 0.5 to 10 mm up passes all of
the light, 2 cm up 0.986 of it, 3 cm 0.914, 5 cm 0.868, 10 cm 0.885 and
20 cm 0.893, where the map says 0.825 (medians over the shaded floor in
view; `test_fire_shadows.py -- cases=heights`). Anything standing lower
than the lift inside the smoke's shadow takes the shadow too. In the
teapot still, with the fire's own lights on, the shadow is soft and faint:
on the floor to the right of the pot it takes 9 % of the light at the
median and 31 % where the smoke is densest (`fire_shadow_still.png`
against `fire_noshadow_still.png` in `blender/tests/fx/out/fire_shadows/`).

### The engine's look under AgX

The engine composited its volume pass with no depth test, so its fire glowed
through the teapot and its base read as a yellow-white ball. EEVEE occludes
physically: gas behind or inside the burning mesh is hidden, and gas in
front is not. The engine also tone-mapped with three's ACESFilmic, which
runs bright red to orange, then yellow, then white. The Blender edition's
AgX runs the same red to salmon, then pink. With the engine's own numbers
(`look=None`) the flame reads red-salmon with a red glowing plume, and the
lava teapot reads as pink plastic.

`create_volume_fire(look='engine')`, the default, gives back the engine's
look: orange tongues, a yellow-white core, grey smoke and a red-hot teapot.
It lays `fire.ENGINE_LOOK` over the engine's numbers, and any option you
pass wins over it:

- `display_match='aces'`: the flame and the lava display under the scene's
  view as three's ACESFilmic showed them in the engine. For each ramp colour
  and strength, a small table (`_look.py`, built from Blender's own OCIO
  config) holds the emission whose AgX display equals the engine's ACES
  display. Least squares where AgX cannot reach the target: AgX cannot show
  ACES's most saturated bright oranges, so the match comes within 2.4/255 on
  average and 34/255 at worst. The volume's table assumes `display_path`
  (2 m) of flame per pixel. The lava's is exact, because it is a surface.
- `emission_scale=2.0`: EEVEE's physical smoke dims the flame behind it more
  than the engine's raymarch did.
- `fire_glow_spread=4.0` (T² instead of T¹): cool gas dims faster, so less
  of the picture sits in the red end of the ramp.
- `fire_end_color='#ff2a00'`: the ramp's cool end a little toward orange.

The table matches at the scene's exposure, display, view and look when the
fire is created; build the fire after setting them. The renders are in
`blender/tests/fx/out/`: `fire_teapot_f*.png` are the default, and
`fire_teapot_raw_f0024.png` the engine's numbers (`preset=raw match=0`), both
at view exposure +1.74, which matches three's ACES at exposure 2. The lava
cracks stay faint in both: the engine's own formula gives this teapot a red
weight of 0.62 to 0.89 between its quartiles, and orange only in the top
percent.

`display_match='aces_compose'` matches the volume per pixel instead.
`create_fire_compose` then takes EEVEE's Volume Direct pass (the volume's
emission and in-scatter as composited into the frame) apart from the rest
of the frame and runs it through three's ACES and the view's own inverse,
`fire_display_match_group`. That is exact for whatever the volume
radiates, but it touches every volume in the view layer (fog, clouds), and
on the teapot it read redder than the table. EEVEE's flame radiance itself
differs from the engine's raymarch.

`create_fire_compose` keeps the engine's colour and bloom steps: saturation
`saturation_amount` (on the volume pass alone in `aces_compose`, as the
engine did; on the whole frame otherwise), then Bloom glare (threshold 0.5,
strength 0.1). The engine's half-resolution volume pass, its gaussian
denoise and its max/add composite existed because its volume was a separate
raymarch; EEVEE renders the volume in the frame.

### The fire's glow on the burning mesh

In EEVEE the burning mesh hides the gas inside and behind it, which the
engine's volume pass, composited with no depth test, showed through it.
`make_fire_glow` puts that light on the mesh itself:

```python
fire.make_lava_emissive(teapot_mat)     # the engine's lava cracks (they replace what fed Emission Color)
fire.make_fire_glow(teapot_mat)         # then the glow of the gas round the mesh, added on top
```

A Geometry Nodes modifier on the burning mesh, `fire_glow`, samples the
baked density and temperature at every vertex at each frame, live from the
volume object, into the attributes `fire_density` and `fire_temperature`.
The material emits what that gas emits per metre, through the flame's own
colour ramp and display match, over `display_path` metres (2 m): the light
the hidden gas sends toward the camera. Its strength is the material's
`fire_glow_strength` Value node, which takes keys; a second
`make_fire_glow(mat, strength=0.5)` sets it. The bake mutes the modifier
while the solver reads the mesh.

On the teapot the glow shows as yellow-white and orange patches over the
red-hot pot where the gas round it is hottest, brightest early in the shot,
where without it the pot reads as red with the flames standing over it.
Over the pot's silhouette its mean display colour goes from 0.860, 0.412,
0.291 to 0.931, 0.610, 0.525 at frame 24, and from 0.881, 0.426, 0.295 to
0.944, 0.623, 0.520 at frame 48. Both renders come from the same grids (a
bake repeats exactly), so the glow is the only difference: away from the
pot the two frames differ by 0.2/255 on average.

`test_fire_glow.py` writes a synthetic frame through the fire's own `.vdb`
writer and samples it on a sphere moved and turned inside the domain: its
vertices read the fields exactly, in the mesh's own frame. `test_fire_teapot.py`
renders the example with the glow, and with `glow=0` without it.

## Not yet ported

- The projected spoke pattern on surfaces (`projection_radius`,
  `projection_frequency`, `projection_noise_fade`,
  `projection_center_fade`): the engine's light colour node textured the
  floor with rotating radial noise. EEVEE ignores light node trees: a
  checker fed into a point light's Emission changes no pixel of the floor
  (`test_fire_shadows.py`, spokes).
- The powder term and the multiple-scattering octave of the smoke shading
  (`powder_strength`, `multi_scattering`), and the engine's own self-shadow
  march (`shadow_absorption`, `shadow_ambient`). Principled Volume has no
  powder or multiple-scattering term: EEVEE's volume light is single
  scattering under volumetric shadows, from the smoke's own extinction.
- The smoke's shadow from any light but the key light, and on anything but
  the ground under `shadow_floor`: the caster is a plane over the ground,
  its opacity worked out toward the key light. Another shadow-casting light
  sees the same pattern from its own direction.
- A `velocity` grid for motion blur on the volume.
- A numpy reference backend for machines without GPU compute. The kernels
  exist only as GLSL today, and the noise functions they use match their
  numpy ports (`blender/tests/fx/test_noise_parity.py`).
- `onTemporal` as a callback. Animate the mesh with keyframes or drivers
  instead; the bake samples them per substep, the warmup's pre-roll
  included.
- The gas inside and behind the burning mesh, as the engine showed it: its
  volume pass was composited with no depth test. In EEVEE the volume is
  depth tested like everything else, so the mesh hides that gas.
  `make_fire_glow` puts the glow of the gas at the mesh's surface on the
  mesh, over `display_path` metres, not the column behind it.
- The engine's look under views other than AgX, Standard, Filmic, the ACES
  views and Khronos PBR Neutral on an sRGB display: `aces_compose` needs the
  view's inverse colour space. The table works for any view OCIO can invert.
