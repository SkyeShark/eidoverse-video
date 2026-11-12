# Shallow water, pours, flat water and 2D fluids

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Free-surface water](free-surface-water.md)

Choose the water representation by its motion and spatial needs.
`eidoblend.fx.swe` models a shallow-water heightfield over `bed_fn(x, y) → z`,
with coupled pours, droplets, foam and sphere interactions. It is the
Blender edition of `fluid_swe.js`. Use [3D free-surface water](free-surface-water.md)
when the surface must fold over or flow around volumetric moving colliders.
A flat reflective water surface suits distant water without those
interactions, a wave-equation pool suits puddles and basins, and the 2D dye
solver is for panels and fields of swirling colour (see Flat reflective
water, A rippling pool and 2D dye fluids below).

The solver is the engine's, kernel for kernel, in numpy:

- flux-form shallow water with per-cell pipe outflows and proportional
  rescale, so h ≥ 0 and mass is exact;
- semi-Lagrangian velocity with surface gravity, Bingham yield, Manning bed
  friction and drag;
- disc emitters and sphere coupling for bodies;
- foam advected and fed by churn, crests, wakes and landings;
- rain with squall bands, and hydraulic erosion with talus slumping;
- the spray exchange: field promotion into droplets that carry volume, and
  pour droplets that return volume, momentum and foam where they land.

It runs in three.js's frame internally, on the same (NZ, NX) layout as the
engine's textures. Fields are rounded to half float after every kernel, as
the engine's rgba16float storage was (`precision='half'`, the default). The
presets, rain rates and thresholds were all tuned on that storage. Pass
`precision='single'` to keep float32.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.swe import create_water_swe

swe = create_water_swe(
    bed_fn=lambda x, y: ground_z(x, y),       # the terrain IS the bed (Blender world, vectorised if it can be)
    world_size=(16, 16), grid_size=(256, 256), domain_center=(0, 0, 0),
    spray_max=6144,                           # whitewater budget (0 = off)
    cache_dir='//swe_cache')

def controls(frame, t, swe):                  # the engine's per-frame calls, Blender coordinates
    swe.set_pours([dict(x=4.7, y=1.0, z=0.53, vx=-0.35, vy=-1.7, vz=-0.4, rate=0.5)])
    swe.set_spheres([dict(x=bx, y=by, z=bz, r=0.42, vx=vx, vy=vy, vz=vz)])   # vz matters: entry splash

swe.bake(1, 1350, controls=controls, track_spheres=[(wader, 0.42)])
```

`bake()` runs the engine's `step(dt)` once per frame and writes per-frame
OpenEXR data images. Geometry Nodes reads them back by frame number:

- `water`: surface height, depth, foam and foam noise;
- `bed`: erosion;
- `spray`: one texel per droplet slot;
- `stream`: the pour tubes' vertices.

The `.blend` then plays the water with no Python at render time.
`track_spheres` feeds animated objects as spheres, with their velocities,
every frame.

The returned object holds:

- `surface_object`, the displaced water surface;
- `terrain_object`, the eroding ground patch (erosion only);
- `spray_object`, the droplets: points from the cache, each a small sphere
  stretched along its velocity;
- `stream_object`, the pour tubes;
- `material`, the surface material;
- `solver`, the numpy state (`solver.volume()` for conservation checks);
- the setters `set_pours`, `set_emitters`, `set_spheres` and `set_rain`.

The probe `blender/tests/fx/test_swe_basin.py` is the engine's `swe_demo`: a
bowl filling from three rim spouts, then a chrome wader breaching. It bakes
288 frames at 256² with 6144 spray slots in about 40 s on the CPU.

**Liquid presets**: exported as `LIQUID_PRESETS`. One word selects a whole
material behaviour (`preset='water' | 'gel' | 'goo' | 'lava' | 'mud'`), and
any option still overrides it. Presets drive both the sim and the look:

- `yield_slope`: Bingham yield, so gel holds its mounds instead of levelling;
- `wave_scale`: a gloopy, slow response;
- `spec_pow`: highlight tightness, which sets the surface roughness;
- `spray_stretch`: needles or blobs;
- `stream_aeration`: water whitens as it falls; honey and gel stay glassy
  filaments;
- `droplet_visibility`;
- `foam_gain`: gel barely froths.

```python
gel = create_water_swe(bed_fn, preset='gel', deep_color='#6e2603', shallow_color='#ff7d1f')
```

**Pour styles**: `set_pours([dict(..., style='seep', seep_width=0.8)])`.
`'jet'` (the default) renders the ballistic stream tube and the droplet
breakup. `'seep'` is a slow dribbling curtain at the mouth, for a rock
spring or a weeping wall; a seep must not render a jet parabola. The mass
ledger is identical. Put pour mouths on the visible geometry's lip.

The pour throttle is the engine's (`fluid_swe.js` cycleEst 1.05 s, a
−0.22 s cooldown, a −0.03 s re-roll). It assumes a droplet cycles in
1.05 s, but droplets are born in the arc's breakup band and recycle much
faster, so a pour delivers more than its `rate`:

- a jet delivers 2–3×: three 0.5 m³/s pours on the demo filled at about
  3.4 m³/s;
- a seep at ground level, whose droplets land almost at once, delivers
  about 15×: a 0.05 m³/s seep in the erosion probe added 0.75 m³ in its
  first second, and the field held 15.7 m³ after 30 s against 2.27 m³ of
  nominal rain plus pour.

The films were tuned on that behaviour (their surge was a seep), so it is
kept. Size a pour by what it delivers, not by its label: bake a few
seconds, read `swe.solver.volume()` and scale `rate`.

**Hydraulic erosion and rain: the bed can be alive.** Pass `erosion={}` and
the terrain under the water becomes dynamic. Fast flow picks the bed up as
suspended sediment, so the water visibly muddies. It carries it downstream
and lays it down where the current slackens. Rills capture into a braided
wash, the wash incises, cut banks cave to the angle of repose, and a silt
fan builds at the outlet.

Pair erosion with `rain_rate`: distributed rainfall over the whole domain,
in m/s of depth. 4.6e-5 is a violent cloudburst, and `rain_patchiness`
animates squall bands. Rain is the natural source for wash formation; a
lone jet pour reads as a garden hose. `swe.set_rain(v)` inside `controls`
ramps the storm. Build with `rain_rate > 0` so the rain term exists.

Under half-float storage, rain increments smaller than half an fp16 step
vanish on wet cells, as they did in the engine. A 17 m valley gathered
about 60% of its nominal rain in the first 20 s.

```python
swe = create_water_swe(
    bed_fn, world_size=(17, 17), grid_size=(256, 256), rain_rate=4.6e-5, rain_patchiness=0.6,
    erosion=dict(capacity=0.30, erode=0.32, deposit=0.42, bank=1.2,
                 talus_slope=0.5,         # wet-sand repose ~29 degrees: banks slump WIDE
                 talus_rate=3.0, max_delta=0.35,
                 terrain_maps=dict(albedo='soil_diff.jpg', rough='soil_rough.jpg', normal='soil_nor.jpg'),
                 terrain_tex_period=120 / 26))   # metres per tile, WORLD-locked like the static ground
```

The probe `blender/tests/fx/test_swe_erosion.py` is the WebGPU erosion
film's own setup: its ground, its erosion parameters and soil maps, rain set
per frame and the seep surge. It bakes
720 frames at 256² in about 3 minutes on the CPU and renders the dry patch
at frame 1, the braided wash at frames 240 and 720, and a 2 m crop of the
domain rim (`swe_erosion_{low,top,rim}_f*.png`).

`terrain_object` is the eroding patch, displaced from the live bed. Lay it
over the static terrain built from the same `bed_fn`. The static mesh must
drop well away (about 1.5 m, feathered) under the patch interior and meet
it flush only at the feathered rim. Sunk only a few centimetres, it fills
every deeper cut from inside: cuts vanish, deposits still rise, and the
piece reads as ground growing around the water. Pass all three maps.
Albedo alone leaves the patch glass-smooth beside a normal-mapped world, and
the domain prints as a square even when the heights meet flush.

Scene craft for a wash that reads: shape the domain as a broad valley.
Damp the dune noise inside it and add a gentle cross-fall; a raw dune field
breaks rain into scattered pools and no channel ever organises. Widening
versus slot-cutting is the tuning axis. `bank` plus a low `talus_slope` and
a small `max_delta` give flood-broad washes. Raise `max_delta` and
`talus_slope` and drop `bank` for a young slot gully.

Key options:

- `init_level` pre-fills to a waterline. A scene whose point is the fill
  must start dry.
- `foam_decay` tightens or loosens churn patches.
- The palette is `deep_color`, `shallow_color` and `absorption`, plus
  `foam_color`.
- `emissive_color`, `emissive_strength` and `emissive_falloff` make water
  glow with depth, as the demo's palette and lava do.

Give runup a tall containment. Water that slops over a low rim pools on the
outer apron. A wading character needs a local sphere or a few spheres
(`track_spheres`); the whole body's bounds read as walking on the water.

What it cannot do: overhangs, curling breakers, submerged interiors. A
heightfield stores one surface height per column.

**The look in EEVEE.** The surface is one Principled water BSDF:

- IOR 1.333, ray-traced refraction and reflections of the scene's own world;
- clear water tinted by depth, the engine's depth-tinted body
  (`1 − exp(−h · absorption)` × `surface_opacity` of it) and the engine's
  eroded foam coverage through its flow-advected foam noise, in the
  engine's proportions;
- suspended-sediment muddying;
- the shore fade as alpha;
- the engine's emissive mix.

The engine's `envTex`, `skyColor` and hand-tuned specular are not needed:
reflections come from the world. Set `scene.eevee.use_raytracing = True`.
The surface material uses dithered transparency with ray-traced refraction.

Clear water refracts, and body or foam is diffuse. EEVEE's G-buffer keeps
one of refraction or diffuse per pixel (measured in
`blender/tests/water3d/probe_partial_transmission.py`). Given both at once (a transmission
weight between 0 and 1, or BSDFs mixed by Mix Shader), it picks one per
pixel with a pattern that stays the same every sample, and the water shows
a sandpaper grain that 64 samples do not clear. So the material makes the
choice itself. A white-noise hash of the shaded position, new at every
sample because EEVEE jitters each sample, picks clear water with
probability (1 − body)(1 − foam). The Principled renders that pick with
transmission exactly 0 or 1. The samples average to the engine's blend, the
way hashed transparency does: a faint grain at 16 samples, smooth at 64
(`swe_basin_natural_s64_f0072.png`). Film renders want 64 or more.

The surface casts no shadow, like the engine's. EEVEE would treat the
refractive sheet as opaque and shade the bed under the water.

Dry columns (under 1 mm) are drawn `dry_sink` under the bed: 1 cm or a
quarter cell, whichever is more. The engine drew them on the bed, where
they were invisible, because its surface was alpha-blended with no depth
write. In EEVEE, a refractive fragment lying exactly on an opaque surface
renders black even at alpha 0. Black z-fight speckle covered a dry erosion
patch, and a black seam ran along the domain rim, where the rain gate keeps
h at 0. Raise `dry_sink` (an argument of `create_water_swe`) for shots from
far away, where depth precision is coarser. Keep it under the wall
thickness of a vessel the water fills.

Keep the domain rim out of frame where water pools against it. The rim is
a closed wall, so a pool there ends in a cut face that shows the water's
depth colour: a dark band at the edge of the patch.

Droplets are white-grey aerated water, never a clear liquid. Each is a
small sphere stretched along its velocity. It fades by size instead of
alpha, so centimetre drops carry no dither noise. Streams are glassy tubes
that aerate as they fall. Their streak noise is a value noise with the
engine's quintic weights over Blender's White Noise hash, because the
engine's PCG hash needs integer operations that shader nodes lack.

**Pours and streams into containers**: shape `bed_fn` as the vessel's
interior: a bowl, cup, barrel or basin is a heightfield. Share one profile
function between the visible vessel (a lathe of it) and the sim's `bed_fn`.
The container the liquid fills is then the prop's interior, and the pour
lands on a rippling, rising level that conserves mass to the brim.

## Flat reflective water (WaterMesh)

`eidoblend.fx.water_flat.create_water_mesh` is three's `WaterMesh`, the
lake or sea plane eidoverse scenes lay under a sky. It covers distant water
with no interaction.

```python
from eidoblend.fx.water_flat import create_water_mesh

lake = create_water_mesh(size_xy=(300, 300), location=(0, 60, 0),
                         sun_object=sun_lamp,          # drives sun_direction and sun_color
                         water_color='#001e0f', distortion_scale=3.7, size=1.0)
```

The options are WaterMesh's own (camelCase accepted): `alpha`, `size`,
`sun_color`, `sun_direction`, `water_color`, `distortion_scale`,
`water_normals` and `resolution_scale`. `sun_object` binds the sun to a
lamp: drivers read the lamp's world rotation and colour, so the glint
follows the lamp as it is keyed. The normal map tiles every 103 m at
`size` 1, so a lake seen from a person's height reads as swells; raise
`size` for finer ripples. Its colour formula is ported term for term:

- four samples of the water normal map, scrolled by time, at the world
  position times `size` over 103, 107, (8907, 9803) and (1091, 1027);
- the rippled normal `normalize(noise.xzy · (1.5, 1, 1.5))`;
- the sun's `pow(·, 100) · 2` specular and 0.5 diffuse;
- the scatter `max(0, n·eye) · water_color`;
- the Schlick reflectance with F0 0.02.

The engine's `reflector()` was a planar render of the scene, its lookup
pushed by `normal.xz · (0.001 + 1 / distance) · distortion_scale` in screen
units. Here the mirror is EEVEE's own: a Glossy closure reflecting through a
planar light probe made with the water, on the rippled normal tilted by the
same push turned into an angle (about half a 48° field of view per screen
width). Near water ripples the reflection hard and far water stays calm, as
in the engine. The water itself is left out of the probe's capture
(`hide_probe_plane`), as three's reflector clipped at its plane: lying on
the mirror's own plane, it covered the whole mirrored scene, and the lake
reflected a blur of the sky with no pier and no posts in it
(`probe_water_mesh_mirror.py` holds the mirror image of two posts to the
ray-traced one). `resolution_scale` has no Blender counterpart: the probe
renders at the frame's resolution. The engine's shadow offset
(`receivedShadowPositionNode`) has none either: the surface is an emission
and a mirror, which take no shadow term.

Pass your own normal map as `water_normals=path`, or let it make one:
`make_water_normals(path)` synthesises a tileable map from an ocean
spectrum. Three's `waternormals.jpg`, which every engine WaterMesh sampled,
is not in the CC0 cache, so the generated map is made to its statistics: a
mean slope of 12° with 90 % under 21°, about equal in x and y, some 35
ripples a tile. An earlier, four times steeper map broke the sea into white
blotches wherever the reflectance term met a grazing normal
(`probe_water_mesh_normals.py` renders the sea with three's map, the
generated one and that steep one, row by row). The generated map is packed
into the `.blend`: it is written to Blender's session temp folder, which
goes when Blender exits, unless `normals_dir` names a folder of your own.

The engine's one WaterMesh scene, a night coast (`waterColor 0x3d525c`,
`sunColor 0xfff2e0`, `sunDirection (0.2, 0.4, −0.9)`, `distortionScale
4.5`, `size 1.1`, a 4000 m plane), runs with its options verbatim in
`probe_water_mesh_normals.py`, from a jetty at a person's height.

`lake.set_uniform(key, value)` and `lake.key_uniform(key, frame)` drive the
uniforms over time.

### The sky above it (SkyMesh)

The WebGPU water examples put three's `SkyMesh` over the water.
`create_sky_mesh` is that sky as the scene's world: its colorNode term for
term in shader nodes. That covers the Preetham optical depths, the Rayleigh
and Mie phases, the extinction and in-scattering, the sun disc, and the fbm
cloud layer drifting with time. For the toolkit's own volumetric sky, use
`make_sky` ([sky and weather](sky-weather.md)).

```python
from eidoblend.fx.water_flat import create_sky_mesh, create_water_mesh

sky = create_sky_mesh(sun_position=(0.5, -0.2, 0.8), turbidity=10, rayleigh=2,
                      cloud_coverage=0.4)                  # or sun_object=sun_lamp
sea = create_water_mesh(size_xy=(10000, 10000), sun_direction=(0.5, 0.8, 0.2),
                        water_color=0x285f66, distortion_scale=3.7)
```

The options are SkyMesh's uniforms (`turbidity`, `rayleigh`,
`mie_coefficient`, `mie_directional_g`, `sun_position`, `up`, `cloud_scale`,
`cloud_speed`, `cloud_coverage`, `cloud_density`, `cloud_elevation`,
`show_sun_disc`). `sun_position` and `up` take Blender axes;
`sun_direction` on the water takes three's, as the engine's code passed
it. `sky_mesh_radiance(directions, sky.params)` is the same formula in
numpy: the probe renders the cloudless sky to a linear EXR and holds it to
that. Unlike the engine's background box, the world also lights the scene.
The engine's examples render it at `toneMappingExposure` 0.5 (exposure −1
here).

## A rippling pool (water_compute)

`create_water_compute` is the engine's `water_compute.js`: a wave-equation
height field for puddles, basins, fountains and rain-struck surfaces. It
answers `disturb()` calls. It is not 3D liquid.

```python
from eidoblend.fx.water_flat import create_water_compute

pool = create_water_compute(width=128, bounds=0.67, circular=True, location=(0, 0, 0.62),
                            viscosity=0.985, opacity=0.9)
def controls(frame, t, w):
    w.disturb(0.1, -0.05, 0.015, 0.0025)      # plane-local metres; one call = a one-step impulse
pool.bake(1, 96, controls=controls, cache_dir='//pool_cache')
```

The kernel is the engine's, step for step:

- `h' = ((N + S + E + W) / 2 − h_prev) · viscosity`;
- plus the cosine disturbance;
- clamped to ±`max_height` (12 % of `bounds` by default).

It takes one step per frame, as the engine's scenes call it. `bake()` writes
each frame's heights as an OpenEXR data image. Geometry Nodes displaces the
grid by them and stores the engine's shading normal, so the `.blend` plays
with no Python. `circular=True` fades the waves at the inscribed disc's rim
and clips the corners, for round vessels. Both measure each vertex's own
distance from the centre, as the engine's plane UVs did.

Three engine details are kept as they were:

- disturbances centre on the cell index times `bounds / width`, not on cell
  centres;
- the kernel's neighbour indices are unsigned, so row 0's north neighbour
  underflows and clamps to the last row, and column 0's west neighbour to
  the last column. South and east clamp to the edge, so waves at the far
  edges reach the near ones;
- the shading normal is the engine's finite difference. Its neighbour names
  are swapped against three's `webgpu_compute_water` example it came from,
  so both slopes are inverted (a raised ripple shades like a pit) and it is
  twice as steep as the displaced geometry's. `normals='surface'` uses the
  displaced surface's own normal instead.

The material is the engine's MeshStandardMaterial as a Principled BSDF
(`color`, `roughness`, `metalness`, `opacity`); like the engine's mesh it
receives shadows and casts none. `env_map` is superseded: EEVEE reflects the
scene's world and probes. A `segments` other than `width` is replaced by
`width`, with a note: the engine maps vertex index to cell index, which only
lines up when the two are equal.

`test_water_flat.py` renders the engine's own uses: the water showcase
(against its `preview.jpg`) and a pool in a torus rim, with the engine's
normals and with `normals='surface'` side by side.

## 2D dye fluids (fluid_sim)

`eidoblend.fx.stable_fluids` is `fluid_sim.js`: screen-space stable fluids
for ink, smoke, trails behind a subject and swirling backdrops. The engine
wrapped the npm package three-fluid-fx 0.1.0 (MIT, after
PavelDoGreat/WebGL-Fluid-Simulation, MIT). This ports that package's solver
and effects, with its notices carried in the module.

```python
import math
from eidoblend.fx.stable_fluids import create_fluid_sim

fluid = create_fluid_sim(profile='balanced', curl_strength=7.0)   # fluid_sim.js defaults: dye and vorticity on
fluid.resize(1240, 510)                                           # the panel's aspect: round splats
def controls(frame, t, f):
    f.splat(0.3 + 0.2 * math.sin(t), 0.5, 1.4, 0.0, [1.0, 0.08, 0.68])
fluid.bake(1, 240, controls=controls, cache_dir='//ink_cache')
panel = fluid.panel(size=(12.4, 5.1))                             # densityNode as the plane's unlit colour
```

The solver is the package's WGSL, kernel for kernel, in numpy:

- splats, curl and vorticity confinement;
- divergence with reflective walls;
- pressure decay and Jacobi sweeps, then the gradient subtract;
- semi-Lagrangian advection with the package's BFECC variant;
- dissipation scaled by `dt / base_delta`;
- half-float rounding after every kernel, as its rgba16float storage did.

Its options (`sim_resolution`, `dye_resolution`, `pressure_iterations`,
the four dissipations, `curl_strength`, `splat_radius`, `splat_force`,
`base_delta`, `enable_vorticity`, `bfecc`, `reflect_walls`) and the
`performance`, `balanced` and `quality` profiles are the package's. It
matches the package run on WebGPU (`test_stable_fluids_parity.py`) within
0.5–3 % RMS after 60 frames of chaotic flow. The residue is the GPU's
bilinear weights. It is CPU work: measured on a shared machine, a
`performance` frame takes 0.1–0.4 s, a `balanced` one 0.8–1.7 s and a
`quality` one 3–7 s. Bake it on its own (no GPU needed) and render later
with `load_bake`; the probe runs as `phase=bake`, then `phase=render`.

Behaviour kept as the engine had it:

- `step(dt)` clamps dt to 1/60, so a 30 fps film advances 1/60 s a frame.
- `splat(x, y, dx, dy, colour)` writes the colour into the density and, as
  the package does, into the velocity too. A coloured splat drifts by its
  colour, and vorticity (`curl_strength` 3–7 in the engine's scenes)
  turns that into swirls. Leave the colour out and the velocity is
  `(dx, dy)`, with density `(dx, dy, 1)`: the package's cursor use.
- The default `density_dissipation` of 0.91 per frame erases a trail in
  half a second. The engine's scenes use about 0.976.

One difference: the package's TSL constructor ignores `enableDye`, so in
the engine the dye texture stayed empty and the dye-driven overlays showed
nothing. Here `enable_dye` works, as `fluid_sim.js` meant it to.

The fields bake to OpenEXR half sequences that Blender plays by frame. The
engine's sampleable nodes are those sequences: `fluid.density_node`,
`fluid.velocity_node` and `fluid.dye_node` (`fluid.images` holds all
three). `fluid.density`, `.velocity` and `.dye` are the live arrays while it
bakes. The package's other nodes, which `fluid_sim.js` reached through
`_raw`, are `fluid.raw.pressure`, `.divergence` and `.curl`; name them in
`bake(fields=(..., 'pressure'))` to bake them as well. The pressure matches
the package's within 1.4–2.1 % RMS in the parity test.
`fluid.load_bake(cache_dir, first, last)` attaches a bake made earlier
without simulating again.

`test_stable_fluids.py` renders the engine's own uses of `fluid_sim.js` side
by side, each with its own options and splats: the fluid showcase (its
`preview.jpg` is the reference), a neon backdrop, the unit-test panel, an
ink panel, and a dish in the `quality` profile.

The effects are the package's 14 overlay styles and its density tint,
written once as node expressions:

- the styles: `default`, `volumeCursor`, `trail`, `oil`, `velocity`,
  `colorful`, `rainbowFish`, `glaze`, `burn`, `smoke`, `artInk`,
  `rainbowInk`, `colorWater` and `liquidLens`;
- `densityTint`, with its defaults.

The 5 distortions are written the same way: `simple`, `chromatic`,
`rgbShift`, `water` and `waterCaustics`. Each builds either way:

```python
mat = fluid.overlay_node(photo_image, style='smoke')                  # a panel material over an image
fluid.overlay_node('render', style='oil', target='compositor')        # over the rendered frame
fluid.distortion('render', 1.0, kind='waterCaustics', target='compositor')
```

The overlay options are the package's: `intensity`, `time` (default: scene
seconds), `texel`, `cursor_color`, `vibrance`, `velocity_scale` and
`opacity`. `fluid.distortion(scene, strength)` is `fluid_sim.js`'s:
`simpleDistortion` over the density texture.

`attach_pointer_splats` is the package's pointer helper, driven by a path in
place of DOM events. The path is a function `t → (x, y)` or an object
projected through the camera. It keeps the helper's gap reset, sub-pixel
skip, fire guard, `splat_force` scaling and coloured strokes:

```python
fluid.attach(lambda t: (0.5 + 0.3 * math.sin(1.3 * t), 0.5 + 0.25 * math.sin(2.1 * t)),
             size=(1920, 1080), colored_strokes=True)
```

## Not yet ported

- `WaterMesh`'s `resolutionScale` (EEVEE's planar probe renders at the
  frame's resolution) and `receivedShadowPositionNode` (the port's surface
  takes no shadow term). Both are kept in `params` and have no effect.
- `water_compute.js`'s `envMap`: EEVEE reflects the scene's world and probes.
- `SkyMesh`'s box `scale` and its depth trick (`z = w`): the world is
  infinitely far by construction.
- `fluid_sim.js`'s `_eidoToolUsage` registration (the engine's telemetry).
- `createPour` (`pour_water.js`), which one production showcase poured with:
  the module no longer exists in the engine either. Its `water_compute`
  half, a rippling pool in a vessel, is the basin pool in
  `test_water_flat.py`.
- The erosion valley renders (`test_swe_erosion.py`) and carves braided
  channels with banks and silt bars. It has not been compared frame by frame
  with the WebGPU film it was tuned on.
- The shallow-water presets other than water are ported but not yet
  rendered. Seep pours run in the erosion probe, but the seep's curtain is
  out of frame there.
- `SWE_DEBUG=promo`, the promotion-potential debug paint.
