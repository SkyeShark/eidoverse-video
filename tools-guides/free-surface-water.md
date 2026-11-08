# Three-dimensional free-surface water

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

`eidoblend.fx.water3d` is the Blender edition of the engine's `fluid_water.js`:
water with a three-dimensional level-set surface, gravity, solid walls,
mesh colliders, moving sphere colliders and emitters. Use it when water must
fold over, pour, splash or run around a body. For terrain ponds, rivers and
erosion, [liquids.md](liquids.md) describes the cheaper shallow-water solver
(`eidoblend.fx.swe`), which stores one height per column. These are
different simulation APIs.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.water3d import create_water_sim, configure_eevee

configure_eevee(scene, samples=64)              # ray-traced refraction and reflections
water = create_water_sim(
    scene=scene, name='tank', cache_dir='//water_cache',
    grid_size=(64, 64, 48), world_size=(2.0, 2.0, 1.5),   # Blender (x, y, z), z up: CUBIC cells
    domain_center=(0, 0, 0.75),
    column_depth=0.62, measure_volume=True, smooth_surface=True)
water.bake(1, 180)                               # one 1/fps step per frame, the surface meshed per frame
```

`bake()` steps the solver once per frame and meshes the φ = 0 surface of
every frame into `<cache>/<name>_####.ply`. A Geometry Nodes modifier on
`water.surface_mesh` plays the sequence by frame number, so the saved
`.blend` renders any frame with no Python. The engine's camelCase option
names are accepted too (`columnDepth`, `measureVolume`). Blender axes go in
and come out; the solver runs in three.js's y-up frame inside, so every
kernel reads like its source.

## The solver

The engine's kernels, one for one, as GLSL compute on Blender's `gpu`
module. They use the same rgba16float 3D textures, linear samplers and
dispatch order. Each substep runs the paper's Algorithm 1: velocity
extrapolation (6 passes), redistancing, the volume controller, advection
with gravity (MacCormack for φ, with the extrema limiter and the §3.4
clamps), the multigrid pressure solve (4 levels, 2 V-cycles, damped Jacobi
ω 0.8, ghost-fluid free surface) and the viscosity blend.

Parity with the engine itself: `engine_trace_water.mjs` runs `fluid_water.js`
under deno's WebGPU and records its own volume sensor. With the engine's
solver (`ENGINE_SOLVER`, below) the watertest dam break's trace matches
within 0.27 % over 6 s with volume control on. With control off it matches
within 0.6 % over 3 s, where both lose 16 % to the collapse. It is fast: 180
frames of the 64 × 48 × 64 dam break simulate in about 1 s. A 128³ pour
bakes 240 frames, including meshing of 55 of them on the 2× surface grid,
in about 80 s.

### Falling water keeps falling: redistancing and breadth-first extrapolation

Two of this edition's defaults change the engine's solver, both for water
that falls onto water:

- **Redistancing is on.** The engine leaves it off: its kernel takes |∇φ|
  from central differences, which is unstable, and its notes name Godunov
  upwinding as the condition for turning it on. Here that kernel exists
  (`reinit_scheme='godunov'`: the same equation, freeze and clamp, with
  Godunov's one-sided differences) and runs every substep (`reinit_every=1`,
  8 sweeps).
- **The velocity extrapolation is breadth-first** (`extrapolation='bfs'`):
  an air cell takes the velocity of the water nearest it in steps. The
  engine's (`'phi'`) takes it from the neighbours deeper in φ, which needs φ
  to be a distance.

Without them, φ below a falling body stops being a distance: the advection
packs the body's profile against the pool's, the extrapolation then reaches
one cell under the body, and the MAC trace averages that cell's lower face
with the pool's still air. The body's underside slows while its top keeps
falling. Measured on a 0.12 m ball thrown down at 2 m/s into a still pool
0.4 m deep (2 × 2 × 1.5 m):

- at 64³ with the engine's solver its underside leaves free fall 18 cm above
  the pool; the ball flattens into a disc, lands 2 frames late and the pool
  barely moves. With redistancing it holds free fall to about 8 cm and
  punches a crater: the surface at the impact point drops from 0.39 m to
  0.31 m;
- at 128³ with the engine's solver it leaves free fall 35 cm up and never
  reaches the pool: it hovers and spreads into a sheet. With redistancing it
  holds free fall to about 10 cm and lands 2 frames (at 60 fps) after a free
  fall would; with the breadth-first extrapolation too it keeps free-fall
  speed to about 5 cm, lands a frame sooner and carves a crater 13 cm deep.

The engine's coarse multigrid levels were suspected first and ruled out: an
air-preferring φ restriction changed nothing, and so did a Jacobi-only
solve.

On the dam break the two keep the settled pool flat (0.13 mm surface
deviation at 14 s, against the engine's 0.16 mm) and the volume trace
within 5 % of the engine's through the collapse, ending 1.3 % under its
target where the engine ends 0.4 % over. `create_water_sim(**ENGINE_SOLVER,
...)` (`reinit_every=0`, `reinit_scheme='central'`, `extrapolation='phi'`)
is the engine's solver exactly; the parity probes run that way.

The engine's hard-won rules hold here, because they are its kernels:

- **Cubic cells are required.** The divergence and the projection gradient
  are raw face differences. A non-cubic grid logs a warning naming the grid
  to use (`gridSize [64, 48, 64]` for a 2 × 1.5 × 2 m tank).
- **The staggered MAC layout.** The velocity texture holds face velocities.
- **φ is never forced to air inside solids.** That was the mass sink that
  made the first version evaporate.
- **Gravity acts only in the fluid and a 2-cell band.** Velocity is zeroed
  beyond 4 cells into the air.
- **The central-difference redistancing stays off.** It is unstable; the
  Godunov kernel above replaces it.

The Blender edition adds three more things to the engine's solver. Each was
measured on a pour into a stone basin, a case the engine's tank never ran:

- **Collider walls survive coarsening.** The engine read the baked collider
  field at a coarse cell centre with one linear tap and a 0.5 threshold. A
  wall under about three fine cells thick (a vessel's side, a one-cell ground
  slab) vanished from the coarse grids, which then solved an open, floorless
  box. Each coarse level now gets the 2×2×2 maximum of the level below. This
  is the engine's own per-level wall-margin rule, applied to the baked field.
- **φ extends into solids.** A solid cell takes the mean φ of its non-solid
  neighbours: a zero-gradient contact, so the waterline meets a wall square.
  Without it, a back-trace that dips into a wall reads stale air and erodes
  the water touching it. Two dispatches run per substep. It is on by default
  only with baked colliders or spheres (`extend_phi_into_solids=None`), so
  walls-only scenes stay identical to the engine.
- **The collider voxeliser steps past each hit far enough for float32.** A
  fixed 1e-6 m step re-hit the same face of a 24 m slab and broke the ray
  parity in 40 % of its rows.

## Pours: emitters and the volume target

Emitters are spheres that stamp water into φ and drive the velocity inside
them. `set_emitters([{x, y, z, r, vx, vy, vz}])` takes Blender metres and m/s;
`r <= 0` or `None` switches a slot off. Call it in `controls(frame, t, water)`.
`water.emitter_flux()` gives the live inflow (each sphere's cross-section
times its speed).

A level set cannot hold a sheet thinner than about a cell. A jet spreading
into a shallow pool makes exactly such sheets, and loses them as fast as it
pours. The engine counters drift with its PI volume controller (Kim 2007),
which injects a divergence source towards a target. Its documented filling
workflow sets the target to the measured volume every frame, then stops when
the emitters stop. That bakes the losses into the target: a 2-cell jet into a
basin stalled at 4 litres of the 19 poured, and so did the engine's own tank.
`bake(fill_target='poured')` uses the volume actually poured instead: each
frame's flux, plus a sphere's volume when an emitter switches on. Then the
controller restores what the sheets lose:

```python
water = create_water_sim(..., walls=False, collider_meshes=[basin, ground_slab],
                         initial_level=-1.0,          # an empty start: all air
                         max_emitters=2, measure_volume=True)
def controls(frame, t, w):
    w.set_emitters([dict(x=0.41, y=0, z=0.985, r=0.045, vx=-1.0, vz=-0.2) if t < 4.6 else None])
water.bake(1, 240, controls=controls, fill_target='poured', fill_rate=1.5, fill_kp=3.0)
```

`fill_rate` and `fill_kp` raise the controller's cap and gain while water
is added, and until the volume is back within 2 % of the target. Then the
controller's integral is cleared, a bumpless hand-over to holding. Without
that, an integral wound up during a long fill overshot by 10 %.

Measured on `test_water3d_pour_basin.py` at 128³:

- the basin rose from 8.6 to 24 litres while the spout ran;
- it held 30 litres of the 29.8 poured;
- after the splash it settled within 2 % of its target.

`fill_target='measured'` is the engine's workflow, kept as it was.

Stay inside what the method does well. Bulk water is fine: a deep vessel
fills, a dish would not. A jet needs at least 4 cells across. A body of
water dropped into a pool needs the default redistancing (see above): with
the engine's settings it flattens and hovers before it lands.

## Colliders and spheres

Three solid layers combine with OR, as in the engine:

- `walls=True` is the analytic tank: floor and four sides, top open.
- `collider_meshes=[objects]` are baked once at setup by ray parity along +X
  from every cell centre, with children included. Give it closed meshes. A
  ground the water lands on must be a solid slab at least a cell thick
  inside the domain.
- `max_spheres=n` reserves dynamic sphere slots. Feed them with
  `set_spheres([{x, y, z, r}])` every frame, or with
  `bake(track_spheres=[(object, r), (armature, r, 'bone')])`. A sphere is
  solid for the substep: it blocks flow and gets the contact foam ring. As
  in the engine it carries no velocity, so a moving sphere does not push
  water ahead of it.

With `walls=False` the domain's sides and top are open, and water that leaves
them is gone. Keep spills inside the domain, or out of frame.

## The surface

Each baked frame the solver's φ is meshed with OpenVDB's volume-to-mesh, and
the engine's render-side field operations keep their meaning:

- the solid mask blends φ to air across the soft collider occupancy, so
  water never draws inside walls and shorelines are smooth;
- `render_blur` applies 1–2 passes of [1 2 1]/4, which round torn silhouettes;
- `smooth_surface` meshes the engine's cubic B-spline reconstruction on a
  2× grid (the paper's finer surface grid, for the look only);
- `surface_bias` draws the φ = −bias contour, so films thinner than about
  2 × bias do not render.

Turn blur and bias on for splash-heavy shots and off for filling: both erase
thin real water. `mesh_adaptivity` reduces polygons on flat water. Each
vertex carries:

- `thick`, the water behind the point: along the inward normal, or along
  the scene camera's ray with `thickness_mode='view'`, which is the engine's
  view-ray march;
- `ring`, the solid proximity for the contact foam;
- `speed`, the flow speed.

## The look

`shading='lit'` (the default) is the film material, lit by the scene. It uses
IOR 1.333 with ray-traced refraction and reflections of the world. The
engine's terms keep their formulas: the depth tint
`mix(shallow, deep, 1 − exp(−thick · absorption))`, the opacity, the
emissive glow by thickness, the contact and shore foam, and the sparkle.
`foam_churn` and `churn_speed` add white water where the flow is fast,
which suits a pour's landing.

All of the water refracts, and the depth tint, weighted by
`surface_opacity`, colours the light that passes through it: thick water
reads deep, thin water nearly clear (`body='tint'`). EEVEE keeps one of
refraction or diffuse per pixel, so foam is picked per sample with a hash of
the position, and one Principled renders the pick with transmission exactly
0 or 1. `body='stochastic'` is the shallow-water surface's split instead: an
opaque depth-tinted body picked the same way, with probability
`(1 − exp(−thick · absorption)) · opacity`. Where that probability is
middling it stays grainy: a 128³ basin still read as sand at 64 samples.
Make the scene give the water something to reflect: a sky or HDRI world. In
a dark studio, lit water reads as murky glass.

`shading='engine'` is the WebGPU look, unlit, term for term:
`fresnel = (1 − n·v)³ · 0.85 + 0.04`, the depth tint mixed toward
`sky_color` by fresnel, the `key_light_dir` specular, the emissive mix, the
foam and the sparkle, alpha-blended at the engine's opacity with only the
nearest surface drawn. Pair it with `thickness_mode='view'`. The engine drew
to an sRGB canvas with no tone mapping, so the palette is display-matched to
the scene's view (`engine_display='standard'`). Under AgX the teal reads as
the engine's frames did. Use it to match engine shots; use `lit` for film.

Every look value is a named node: `water.uniforms.shallow_color = '#ff0000'`
writes through, and `key_look(water.material, 'absorption', frame, 4.0)`
keys it. The solver's live uniforms (`gravity`, `vel_damping`, `max_speed`,
`vel_smooth`, `mg_omega`, `vol_target`, `vc_kp`, `vc_ki`, `vc_max_rate`)
take effect at the next substep. The uniforms hold values, snake_case: the
engine's `water.uniforms.volTarget.value = 40` is
`water.uniforms.vol_target = 40`. `surface_bias` is a uniform too, applied
to every frame meshed after the change; `world_size` and `wall_m` read the
fixed domain.

## The rest of the API

- `step(delta)` is the engine's real-time step: delta is clamped to 1/30 s,
  with at most `max_sub_steps` substeps.
- `warmup(seconds)`, `reset()` and `dispose()` behave as in the engine.
- `measure_volume()` reads the GPU sensor, in m³.
- `capture(frame)` meshes the current state for a manual loop;
  `attach_player()` plays the frames meshed so far.
- `write_grids=True`, or the engine's `__debugPhi` / `__debugFields`,
  writes φ, velocity, pressure and divergence per frame as OpenVDB. That
  replaces the engine's heat-map shaders: open the files in Blender or any
  VDB viewer.
- `__noClamp`, `__noReinit`, `__noPressure` and `__noMultigrid` are the
  engine's bisect switches.

## The engine's scenes in Blender

Three engine scenes drove `fluid_water.js`. Each is ported as a probe with
its own options, so their settings carry over as written:

- **watertest** (the dam break): `test_water3d_dam_break.py`, the engine's
  tank, camera and lights. It runs the engine's solver so its volume trace
  can be held to the engine's.
- **spheretest** (a ball driven per frame descends into the settled pool and
  sweeps through it): `test_water3d_spheretest.py`. The ball is a keyed
  object fed to `bake(track_spheres=...)`; the water parts round it, meets it
  in a waterline ring and closes in behind it.
- **chorus** (a basin filled on camera by spouts, a wader as sphere
  colliders, the luminous jade palette): `test_water3d_spouts_wader.py`, at a
  fifth of the scale, with its `velSmooth: 0`, `maxSpeed: 15`,
  `foamShore: 0`, `smoothSurface` and palette. The scene had to set
  `uniforms.volTarget` by hand because its basin starts empty; here
  `fill_target='poured'` sets it from what the spouts pour.

## Probes

`blender/tests/water3d/`:

- `test_water3d_dam_break.py`: the watertest, above. It checks the volume
  trace against the engine's and renders in both shadings
  (`shading=engine` matches `watertest/_sheet_final2.png`); `solver=edition`
  runs this edition's defaults instead.
- `test_water3d_pour_basin.py` is a bronze spout pouring into a stone basin,
  then a thrown slug that splashes. It renders every sixth frame and every
  frame of the splash, with contact sheets to judge frame by frame.
- `test_water3d_spheretest.py` and `test_water3d_spouts_wader.py`: the
  spheretest and chorus scenes, above.
- `test_water3d_options.py` covers every option and API call, a wading pool
  with an armature's bone and an empty as spheres, the view from under the
  water, and an emissive goo.
- `test_water3d_guide_example.py` runs the engine guide's own example with
  its camelCase options verbatim (numbers only): the still pool, a sphere
  lowered into it, an emitter, and the controller holding its initial
  target without `fill_target`.

The engine's camelCase names keep the engine's meaning, so an engine
config ports verbatim: `gridSize: [64, 48, 64]`, `worldSize: [2, 1.5, 2]`
and `domainCenter: [0, 0.75, 0]` are three.js axes (y up) and become
`grid_size=(64, 64, 48)`, `world_size=(2, 2, 1.5)` and
`domain_center=(0, 0, 0.75)`. The snake_case names take Blender axes.

## Not yet ported

- The engine's raymarcher (`raymarch_steps`, `bisection_steps`,
  `march_mode`, `march_iters`). The surface is a mesh that EEVEE rasterises,
  so these options are accepted and have no effect.
- `inside_domain` is a raymarch-box setting. A mesh is seen from anywhere,
  so here it only shows back faces, for a camera under the water.
- Tall cells, spray particles and the 2× finer φ grid of the paper. None of
  these were in the engine.
- Moving solids that push water: sphere velocities in the divergence and
  projection. Not in the engine.
- The last 8–10 cm before a falling body meets a pool. The frozen cells
  beside its leading edge keep the jump in φ the fast advection leaves
  there, so the extrapolation still hands the cell under it the pool's
  still velocity, and the MAC trace averages the two: the underside slows
  and lands about two 60 fps frames late. A breadth-first velocity
  extrapolation (by distance from the water, not by φ) would not depend on
  that jump; re-estimating the frozen cells from their zero crossings every
  sweep was tried and drifts (a 0.12 m ball melted at 64³).
- `fluid_3d.js`, the production engine's MLS-MPM particle liquid, is the
  module `fluid_water.js` replaced; the public engine's guide says not to
  import it, and liquid surfaces here stay level sets. Its container,
  emitters, sphere colliders and surface map to `collider_meshes`,
  `set_emitters`, `set_spheres` and the meshed surface.
