# Draft for liquids.md: the other waters (step water3d)

These sections replace liquids.md's "Not yet ported" bullets for `WaterMesh`
and `fluid_sim`. They are written in that guide's voice and go after its
shallow-water sections. The 3D water has its own guide
([free-surface-water.md](../free-surface-water.md)).

---

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

One engine scene used `WaterMesh`: the night coast of the antad_response
film (`waterColor 0x3d525c`, `sunColor 0xfff2e0`, `sunDirection (0.2, 0.4,
−0.9)`, `distortionScale 4.5`, `size 1.1`, a 4000 m plane). Its options run
verbatim in `probe_water_mesh_normals.py`, from a jetty at a person's
height.

`lake.set_uniform(key, value)` and `lake.key_uniform(key, frame)` drive the
uniforms over time.

### The sky above it (SkyMesh)

liquids.md's example puts three's `SkyMesh` over the water.
`create_sky_mesh` is that sky as the scene's world: its colorNode term for
term in shader nodes. That covers the Preetham optical depths, the Rayleigh
and Mie phases, the extinction and in-scattering, the sun disc, and the fbm
cloud layer drifting with time.

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
(against its `preview.jpg`) and the helper expo's pool in its torus rim,
with the engine's normals and with `normals='surface'` side by side.

## 2D dye fluids (fluid_sim)

`eidoblend.fx.stable_fluids` is `fluid_sim.js`: screen-space stable fluids
for ink, smoke, trails behind a subject and swirling backdrops. The engine
wrapped the npm package three-fluid-fx 0.1.0 (MIT, after
PavelDoGreat/WebGL-Fluid-Simulation, MIT). This ports that package's solver
and effects, with its notices carried in the module.

```python
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
bilinear weights. It is CPU work: measured on the shared machine, a
`performance` frame takes 0.1–0.4 s, a `balanced` one 0.8–1.7 s and a
`quality` one 3–7 s. Bake it on its own (no GPU needed) and render later
with `load_bake`; the probe runs as `phase=bake`, then `phase=render`.

Behaviour kept as the engine had it:

- `step(dt)` clamps dt to 1/60, so a 30 fps film advances 1/60 s a frame.
- `splat(x, y, dx, dy, colour)` writes the colour into the density and, as
  the package does, into the velocity too. A coloured splat drifts by its
  colour, and vorticity (`curl_strength` 3–7 in the production scenes)
  turns that into swirls. Leave the colour out and the velocity is
  `(dx, dy)`, with density `(dx, dy, 1)`: the package's cursor use.
- The default `density_dissipation` of 0.91 per frame erases a trail in
  half a second. The production scenes use about 0.976.

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

The engine scenes that used `fluid_sim.js` are rendered side by side in
`test_stable_fluids.py`, each with its own options and splats:

- the fluid showcase (its `preview.jpg` is the reference);
- the neon backdrop of the burning-agents piece;
- the unit-test panel (liquids.md's example options);
- the helper expo's ink panel;
- the options of the neuro dish (the `quality` profile).

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

---

### Lines for liquids.md's "Not yet ported"

Drop the `WaterMesh` and `fluid_sim` bullets (both ported above) and add:

- `WaterMesh`'s `resolutionScale` (EEVEE's planar probe renders at the
  frame's resolution) and `receivedShadowPositionNode` (the port's surface
  takes no shadow term). Both are kept in `params` and have no effect.
- `water_compute.js`'s `envMap`: EEVEE reflects the scene's world and probes.
- `SkyMesh`'s box `scale` and its depth trick (`z = w`): the world is
  infinitely far by construction.
- `fluid_sim.js`'s `_eidoToolUsage` registration (the engine's telemetry).
- The production engine's pour showcase (`work/_showcase/pour`). It pours
  with `createPour` from `pour_water.js`, a module that no longer exists
  there. Its `water_compute` half, a rippling pool in a vessel, is the basin
  pool in `test_water_flat.py`.

The intro's "(both are in "Not yet ported" below)" becomes "(see Flat
reflective water and 2D dye fluids below)".
