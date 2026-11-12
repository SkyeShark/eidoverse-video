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
fire.bake(1, 240)                                         # warmup, then one step per frame
configure_eevee_for_fire(scene, fire, camera)             # froxels, volume shadows, a tight depth range
create_fire_compose(scene, fire)                          # saturation 1.1, then bloom
```

Set the scene's view transform, display and exposure before
`create_volume_fire`: its look is matched to them when it is built.

The bake runs on the GPU, so on a shared GPU run it one at a time, like a
render. The full 100 × 200 × 100 grid bakes in seconds: 400 warmup
substeps plus 48 frames took 4.5 s. Each frame writes about 2.7 MB of `.vdb`.

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
| `material` | `volumetricMaterial` | the volume material |
| `params` | `params` | the resolved options |
| `sim_time` | `simTime` | seconds of simulation after the last bake |
| `bake()` | `warmup()` + `step()` | the whole shot, plus the light keys |
| `make_lava_emissive(mat)` | `makeLavaEmissive` | adds the lava cracks to a Principled material |

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

Changing an option means baking again. The cache is the fire.

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

## Not yet ported

- The projected spoke pattern on surfaces: the engine's light colour node
  textured the floor with rotating radial noise. EEVEE ignores light node
  trees.
- The powder term and the multiple-scattering octave of the smoke shading.
  EEVEE's scattering replaces them; there is no node equivalent.
- The `shadowMesh`, the smoke's own soft shadow on the floor. The engine's
  test scene never shipped it either: it broke r184's shadow pass. EEVEE's
  volumetric shadows act on the volume. Whether they darken surfaces in 5.2
  is still unverified.
- A `velocity` grid for motion blur on the volume.
- A numpy reference backend for machines without GPU compute. The kernels
  exist only as GLSL today, and the noise functions they use match their
  numpy ports (`blender/tests/fx/test_noise_parity.py`).
- `onTemporal` as a callback. Animate the mesh with keyframes or drivers
  instead; the bake samples them per substep, the warmup's pre-roll
  included.
- The engine's fire glowing through the burning mesh: the volume behind the
  mesh is occluded in EEVEE, so the teapot's base is not the engine's
  yellow-white ball.
- The engine's look under views other than AgX, Standard, Filmic, the ACES
  views and Khronos PBR Neutral on an sRGB display: `aces_compose` needs the
  view's inverse colour space. The table works for any view OCIO can invert.
