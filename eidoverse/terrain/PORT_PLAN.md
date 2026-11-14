# Porting the new make_terrain to the three.js edition: the plan

Three.js / Deno / WebGPU edition (branch `threejs-terrain`, from `main`), 2026-11-13. The contract the port's agents
build from, and the lead's checklist. The source of truth is the Blender edition's terrain family on the `blender`
branch: `blender/eidoblend/terrain/` at commit `f90c6fc` ("Terrain: the review's fix round ..."), its design
`blender/tests/terrain/DESIGN.md`, and its tests and judge in `blender/tests/terrain/`. Every number below that is
not quoted from those files was measured for this plan by the probes in `tests/design_probes/` (section 1.2;
numbers in `tests/design_probes/results.json`).

---

## 0. The plan in one page

**The goal.** `await makeTerrain({ recipe: 'alpine_valley', ... })` in a three.js scene makes the same ground the
Blender edition's `make_terrain(recipe='alpine_valley', ...)` makes: the same stages, recipes, parameters, plans and
kernels, on the same nested levels, drawn as the same ring mesh with exact seams, judged by the same judge against
the same real elevation data and photographs. The old `makeTerrain` (`eidoverse/terrain.js`, a value-noise plane with
vertex-painted layers) goes; the name stays.

**The decisions.**

1. **A real port, module for module.** Every Blender module has one counterpart file (section 3). Each GLSL kernel
   becomes a WGSL kernel with the same file name and the same `//!` interface header, transcribed statement for
   statement, so a reviewer can read the two side by side. Recipes stay data: `recipe.toDict()` in the port is the
   same JSON as `recipe.to_dict()` in Blender. Plans drawn from numpy's `default_rng` are drawn from a JS port of
   numpy's Generator that reproduces it draw for draw (measured: 290 of 290 draws bit-exact, section 1.2).
2. **Raw WGSL compute on the scene's own device.** Kernels run as WebGPU compute pipelines on `GPU_DEVICE` (the device
   `render_scene.mjs` creates and every scene renderer shares), through a small runner, `core/gpu.js`, the counterpart
   of Blender's `core/gpu.py`. Not TSL compute: it costs 3-70 times more JavaScript per dispatch (measured; the
   spread is the machine's load) and would be a rewrite into a JS DSL instead of a transcription. Not Ekigar's runner: Ekigar has none (`src/compute/` is
   empty). The runner as prototyped runs the Blender fluvial step as fast as Blender does: 1.08 ms against 1.02 ms
   at 1024², 3.9 ms against 4.5 ms at 2048² (section 4.8).
3. **Every per-cell operation runs on the GPU,** including everything the Blender edition does in numpy over a whole
   level: inheriting a parent, pins, inflow, depression filling, lakes, the routing surface, labelling, world-space
   shapes and stamps, blurs, masks, the mesh. JavaScript on the CPU keeps only what is not per cell: plans over
   objects (towers, cones, vents, cirques, river courses, wind schedules) and over the few small plan grids whose
   discrete outcome must match numpy's (section 2.4), controllers, recipes, per-query sampling (`heightAt`), and file
   input and output.
4. **The oracles are the Blender edition's own.** A WGSL kernel is checked against the Blender kernel's numpy twin; a
   GPU replacement of numpy code against that numpy function; a stage against the Blender stage's own input and
   output; a recipe against the Blender recipe's saved fields. There are no JS twins: a JS twin would be a third
   implementation of each kernel, and the numpy twins already measure exactly what parity needs.
5. **Parity is graded, and every grade has a measured tolerance** (section 5): bit-exact for integers, hashes and the
   numpy draws; within 1e-4 of a field's range for one dispatch (measured worst 3.06e-5, the same as the GLSL
   kernels' own worst against the same twins); stage replay from Blender's inputs; and for whole recipes, the Blender
   edition's own chaos floor. I measured it: moving every erosion run's start by one float32 ulp changes the main
   level by 0.34 % (RMS of relief) on `stratovolcano` and 0.75 % on `canyon`, but by 12.6 % on `fluvial_range`,
   whose drainage network is then a different one (channel overlap 0.10). So "the same recipe and seed give the same
   landform" is a field-by-field test for the recipes with a low floor and a test over seeds for the chaotic ones.
6. **Shared data is read where it lives,** in a checkout of the `blender` branch (or this checkout, once the branches
   merge): the reference DEMs, the photographs, the view cameras, the bands and the judge itself. The port writes
   its terrain in the Blender `Terrain.save` format and runs the one Python judge on it. Nothing is copied into git.
7. **`makeTerrain` keeps its name, becomes async, and returns a `Terrain`** with `.mesh` and `.heightAt` (so the old
   `const { mesh, heightAt } = ...` still works) plus every Blender member. The ring mesh is built by GPU kernels and
   read back once: `heightAt` is exact on the rendered triangles, a collider proxy keeps Rapier's trimesh small, and
   the mesh's ray caster walks the height grid instead of millions of triangles.
8. **Surfacing and plant placement are the last wave,** a TSL NodeMaterial and a placement layer that follow
   `blender/tests/terrain/SURFACING_DESIGN.md` once it is final (not yet in the Blender worktree as I write).
9. **Two corrections to the brief, for the lead.** `eidoverse/terrain_base.js` is not part of the old terrain: it is
   the locomotion obstacle-course template (stairs, ramps, walls, ladders) that `examples/obstacle_course.js` and the
   character and navigation guides use, and it never calls `makeTerrain`. The plan keeps it. And the Blender
   registry holds 16 recipes, not 17 (section 3.2); the port follows the registry.

---

## 1. What I worked from, and what I measured

### 1.1 Inputs

- **The Blender edition** (`blender` branch, read-only): `DESIGN.md` (1,110 lines); the package
  `blender/eidoblend/terrain/` (32,243 lines of Python and GLSL): `core/` (gpu, twins, grid, levels, fields, recipe,
  expr, world_noise, compose, cache, io, metrics), the 17 `kernels/*.glsl` plus `common.glsl`, 13 `solvers/`, 16
  `recipes/`, `masks.py`, `run.py`, `api.py`, `bake.py`, `build/` (mesh, water, dressing, surfacing, palettes); the
  judge (`tests/terrain/judge/`), the references (`tests/terrain/reference/`), the kernel tests and their results
  (`tests/terrain/out/*/kernel_tests.json`, `gpu_tests.json`), and the GPU benchmark (`design_probes/results.json`,
  `out/core/gpu_bench.json`). The Blender worktree has uncommitted edits to 61 files under `blender/tests/terrain/`,
  `DESIGN.md` among them (a portability pass: `EIDO_GPU_WRAP`, `blender/tests/_where.py`); none to the package itself.
- **The three.js edition** (this worktree, from `main` at `404a00e`): `AGENTS.md`, `README.md`,
  `eidoverse/README.md`, `tools-guides/development.md`, `scene-format.md`, `terrain-surfaces.md`, `vegetation.md`,
  `docs/TOOLS.md`; `render_scene.mjs` (helper injection, `GPU_DEVICE`), `render_common.mjs` (device limits and the
  Deno/wgpu patches), `gpu_check.mjs`; the GPU compute in `fluid_swe.js`, `fluid_grid.js`, `cloth_sim.js` (TSL
  compute and its recorded "stack laws"); `terrain.js` (the old `makeTerrain`, 132 lines), `terrain_base.js`,
  `robot_controller.js` (the trimesh collider), `scene_placement.js` (`snapToGround`), `vegetation.js`
  (`heightFn`), `weather_system.js` (`strikeHeightAt`); three r184's `StorageBufferAttribute` and
  `getArrayBufferAsync` (in Deno's npm cache).
- **Ekigar** (MIT, Skye's): `docs/STATUS.md` (routing, accumulation and priority flood listed as product gaps),
  `src/compute/` and `src/api/` (empty), `src/nodes/noise.js` (TSL lattice noise, Ekigar's integer hash),
  `src/nodes/phacelle.js`, `src/nodes/terrain_mesh.js` (measured display-mesh costs), `src/export/png.js`,
  `png_read.js`, `heightmap.js`, `src/materials/texture_arrays.js`, `triplanar.js`, `layer_stack.js`, and the
  headless Deno harness in `test/gpu/`.

### 1.2 The probes (all in `tests/design_probes/`, numbers in `results.json`)

Every GPU probe ran through this machine's GPU queue (an RTX 5090 Laptop GPU shared with other sessions' Blender
jobs), Deno 2.8.1, `deno run --no-config --no-lock --unstable-webgpu --allow-all <probe>`.

| probe | what it measures | result |
|---|---|---|
| `gpu_device.mjs` | the adapter and the device the port would request | hardware adapter; features `timestamp-query`, `shader-f16`, `float32-filterable`, `immediate-data`, no `subgroups`, no `core-features-and-limits` (render_common.mjs shims it for three); `maxStorageBuffersPerShaderStage` 1,048,576 when asked for (default 8), `maxStorageBufferBindingSize` 2 GiB, workgroup storage 48 KiB |
| `gpu_runner_bench.mjs` | the Blender design's 3x3 stream-power probe kernel in raw WGSL: storage buffers against storage textures, GPU timestamps, wall time, readback, upload, one submit per dispatch, a 7-level 2048² allocation | section 4.8; buffers and textures give bit-identical results, buffers as fast or faster; every sync costs about 16 ms; 3.19 GiB allocated without error |
| `tsl_compute_bench.mjs` | the same kernel in TSL through `renderer.compute()` / `computeAsync()` | 0.03-0.56 ms of JavaScript per call against 0.006-0.021 ms per raw dispatch; inside that long session one comparison read back data missing its last dispatch (not reproduced in a fresh process; see the next row) |
| `tsl_vs_wgsl_fresh.mjs` | in a fresh process: TSL against WGSL after one step, both against float64; whether a first call runs | bit-identical at 64² and 512², both within 1.1e-7 of float64; first calls run |
| `make_twin_fixtures.py` + `kernel_parity.mjs` + `mini_runner.mjs` + `wgsl/` | WGSL transcriptions of the fluvial step's seven kernels (`flow_weights`, `route_incise`, `creep`, `threshold_excess`, `threshold`, `creep_layers`, `h_keep`) and of the world-noise kernel, run through a prototype of `core/gpu.js` against the Blender numpy twins on the Blender parity inputs; the PCG chain and Ekigar's lattice hash; the f32 built-ins' error; the 9-pass fluvial step's cost and determinism | 46 of 46 cases within 1e-4 of range, worst 3.06e-5; PCG, pcg2, pcg3, `cell_hash`, `u01` and Ekigar's integer hash bit-exact; world noise within 9.2e-7 of range of numpy's float64; the step as fast as Blender's (section 4.8) and bit-identical run to run |
| `np_random_expected.py` + `np_random_probe.mjs` | numpy's `default_rng` (SeedSequence, PCG64, `random`, `uniform`, `integers`) in JS, for the seed forms the terrain uses (ints, `[seed, salt]`, `[seed, salt, k]`, salts wider than 32 bits) | 10 of 10 seed forms, 290 of 290 draws bit-exact (numpy 2.5.2) |
| `blender_chaos_floor.py` | the Blender edition against itself: each recipe twice (determinism), then with every erosion run's start moved by one float32 ulp | reruns bit-identical; the floor per recipe in section 5.4 |

---

## 2. Where the port lives, and its frames

### 2.1 The place

```
eidoverse/terrain.js          the injected helper (render_scene.mjs HELPER_MODULES already lists it): installs
                              globalThis.makeTerrain, which imports the package below on first use
eidoverse/terrain/            the package (ES modules, imported through EIDOVERSE_DIR)
  PORT_PLAN.md                this plan
  index.js  api.js  run.js  masks.js  bake.mjs
  core/  kernels/  solvers/  recipes/  build/
  tests/                      the package's tests (Deno tests and the Python parity tools), tests/out/ git-ignored
```

The edition's own layout decides it. Engine code lives in `eidoverse/`; a large system is an ES-module package in
its own folder with its tests inside it (`eidoverse/robotics/`, `robotics/index.js`, `robotics/tests/*_test.mjs`);
a scene reaches such a system through an injected eval helper that installs a global (`eidoverse/*.js` in
`HELPER_MODULES`) or through `await import(EIDOVERSE_DIR + ...)`. So the new terrain is `eidoverse/terrain/`, and
`eidoverse/terrain.js` stays the injected helper under the same name. The Blender edition keeps its design beside its
tests (`blender/tests/terrain/DESIGN.md`) because that edition keeps every family's tests under `blender/tests/`; here
a package carries its own tests, so the plan sits at the package root, next to the code it governs.

### 2.2 Frames and units

| | Blender edition | three.js port |
|---|---|---|
| up axis | +Z | +Y |
| ground plane | X east, Y north | X east, Z south (north is -Z) |
| a point | Blender (x, y, z) | three.js (X, Y, Z) = (x, z, -y): the standard Z-up to Y-up rotation, determinant +1, so triangle winding is kept |
| `height_at(x, y)` | metres at Blender (x, y) | `heightAt(x, z)` = Blender `height_at(x, -z)` |
| arrays | `[row j, column i]`, row 0 the south edge, cell centre at `x0 + (i + 0.5) cell`, `y0 + (j + 0.5) cell` | the same arrays, the same frame, the same windows `(x0, y0, side, cell, n)` in Blender metres; the frame changes only where a value meets the scene (the mesh, `heightAt`, `focus`, `flatten`) |
| units | metres, years, degrees (tangents inside kernels), m/yr, m²/yr | the same |
| knob names | `relief_m`, `ela_m`, ... | the same (recipe data is shared JSON) |
| call options | `hero_cell`, `sea_level`, `base_elevation_m` | camelCase: `heroCell`, `seaLevel`, `baseElevationM` (the edition's style); one spelling each, an unknown option names the nearest |

Keeping the arrays in Blender's frame makes every dump comparable without a transform: only `build/mesh.js`,
`api.js` and the scene-facing helpers convert.

### 2.3 Numerics

- **On the GPU, f32.** WGSL has no f64. The Blender kernels are f32 too; the Blender numpy code is often float64. A
  GPU replacement of a float64 numpy function agrees to f32 rounding (world noise: 9.2e-7 of range).
- **Last-bit differences are normal.** Ekigar's lattice hash is integer-exact in both editions, but its gradient
  `f32(h & 0xFFFF) * (1 / 32767.5) - 1` differs in the last bits from the same arithmetic in numpy float32, and by
  up to 64 ulp from numpy's float64 where the result is near zero. That is what a driver contracting `x * c - 1`
  into one fused multiply-add produces (WGSL allows it; I infer the cause, I did not inspect the compiled shader).
  Bit equality of float kernels across GLSL, WGSL and numpy is therefore not a goal; integer paths are bit-equal.
- **Built-ins.** Measured error of the f32 built-ins against the correctly rounded value: `sqrt` 1 ulp, `atan`,
  `atan2` and division 2, `exp` 15, `pow` 69 (p99 28), `log` p99 5 but up to 40,480 ulp near 1 (an absolute bound),
  `tan` p99 77 but up to 50,170 ulp near 0 (from the sine's absolute bound). Angles are converted to tangents on the
  CPU in float64, as Blender does in numpy; kernels never take `tan` of a degree value.
- **No float atomics.** Kernels are gathers, as Blender's are. Where the port needs a scatter or a reduction it uses
  integer atomics on order-independent quantities (counts, `atomicMax`/`atomicMin` on monotonic bit patterns of
  non-negative floats, fixed-point sums), so the result is the same whatever the order; float sums run in a fixed
  tree. Measured: the 9-pass fluvial step is bit-identical over 205 steps from the same start.
- **Exact selection, not approximate quantiles.** `np.percentile` (the relief controller, the mask norms, the
  judge's metrics) is reproduced by a GPU radix select of the exact order statistics on monotonic keys, then numpy's
  linear interpolation in float64 on the CPU: the same number as numpy for the same field.
- **Plans in float64.** Plans are computed in JS doubles, as numpy computes them. V8's `Math` and the C library can
  differ in the last ulp, so plan floats are compared within 1e-12 relative (section 5.3).

### 2.4 What stays on the CPU, and why

The edition's rule is that per-frame and per-texel work is GPU compute or render-to-texture, and that where Blender
computes something in numpy over a whole level, the port computes it on the GPU. What stays in JavaScript:

1. **Plans over objects**, built once per terrain from seeds: karst towers and their peaks (Poisson disc), cinder
   cones and rift cones, lava vents, cirques, strata cores (dart throwing), river courses (Kinoshita curves, random
   walks), wind schedules, crater blocks, uplift spurs, azimuth tables and rock columns (1D tables). Their numbers come
   from the numpy Generator port, so they equal Blender's.
2. **The small plan grids whose discrete outcome must match numpy's.** The one I found: karst's river course, a
   Dijkstra least-cost path on a 160 x 160 cost grid (`solvers/karst.py` `_river_course`), whose path depends on
   heap order and on float64 costs. It stays a JS port of the same algorithm, with a binary heap ordered like Python's
   `heapq` on `(cost, j, i)` tuples, evaluating its cost grid in float64.
3. **The lava walkers** (`solvers/volcanic.py` `lava_walkers`, DOWNFLOW): stochastic walkers whose draws come from
   numpy's Generator in an order that depends on how many walkers are alive each step. A GPU walker per thread would
   need a different random stream and could not match Blender. They run in JS over the walkers (not the cells), on
   the level's height read back once; their visit counts go back to the GPU, where the flow surface is made.
4. **Control:** the level loop, stage selection, the relief controller's arithmetic (on numbers the GPU reduced),
   convergence decisions, cache keys and records.
5. **Per-query sampling:** `heightAt`, `normalAt`, `mask(name).at`, `viewpoint` (a few thousand queries).
6. **File input and output:** zlib in PNG and npz, JSON. The quantisation to 16 bits runs on the GPU first.

Everything else is a kernel. Section 3 names, module by module, what moves from numpy to the GPU.

---

## 3. The module map

### 3.1 The package

```
eidoverse/terrain/
  index.js                 exports: makeTerrain, Terrain, MaskSet, recipes, describe, NpGenerator
  api.js                   makeTerrain, Terrain, Mask, MaskSet, describe, viewpoint, preview, save/load
  run.js                   the level runner
  masks.js                 every mask, as GPU kernels
  bake.mjs                 the CLI: deno run ... eidoverse/terrain/bake.mjs --recipe dunes --seed 3 --save --out <dir>
  core/
    gpu.js                 the runner (section 4)
    prims.js               GPU building blocks the solvers share (3.4)
    np_random.js           numpy's Generator (PCG64 + SeedSequence + the distributions the terrain draws)
    levels.js  grid.js  fields.js  recipe.js  expr.js  world_noise.js  compose.js  cache.js  io.js  metrics.js
  kernels/
    common.wgsl            common.glsl, one for one
    <name>.wgsl            one per Blender kernel (3.3), same name, same //! header
    prims/  grid/  compose/  hydro/  masks/  mesh/  water/  volcanic/  impact/  strata/  karst/  glacial/  detail/
                           the kernels of numpy code that moves to the GPU, one folder per owner
  solvers/                 fluvial hillslope hydro hydraulic glacial aeolian volcanic impact strata rivers karst
                           coast detail (.js, one per Blender solver)
  recipes/
    index.js               the registry: reads the folder, collects every module's RECIPES and OPS
    alpine_valley.js badlands.js caldera.js canyon.js cinder_cones.js dunes.js fluvial_range.js impact_crater.js
    incised_meanders.js meadow.js mesas_buttes.js real_place.js rolling_hills.js sea_cliffs.js stratovolcano.js
    tower_karst.js
  build/
    mesh.js  water.js  collider.js
    surfacing.js  palettes.js  dressing.js  placement.js        (the last wave, section 8)
  tests/
    _where.mjs             where things are (the Blender checkout, the GPU wrap, DEM folders): no machine paths
    design_probes/         this plan's probes
    parity/  judge/  <package>/   (section 8)
```

### 3.2 Every Blender module, and what it becomes

"GPU" means a kernel replaces the numpy code; "JS" means it stays JavaScript on the CPU (section 2.4).

| Blender module | port file(s) | what moves from numpy to the GPU, what stays JS |
|---|---|---|
| `__init__.py` | `index.js`, `eidoverse/terrain.js` | exports; the global installer |
| `api.py` (747) | `api.js` | GPU: the exact flatten pass (`flatten_fields`), hillshade and mask PNGs for `preview`; JS: argument checks, `viewpoint` (heightAt along candidate sight lines), `Mask.at`, save/load (npz) |
| `bake.py` | `bake.mjs` | the same flags; `--save` writes the `Terrain.save` format (5.2) |
| `run.py` (335) | `run.js` | GPU: inherit (`crop_upsample2`), child pins (ramp, sea), `inflow` (a gather on the window's edge strip), `_band_pull`, `where` masks and blends, `window_relief` (exact select); JS: the level loop, stage selection, pre-passes, cache keys, records |
| `masks.py` (1,018) | `masks.js` + `kernels/masks/` | GPU: every mask (gradient, curvatures through a decimated Gaussian, peaks, flow, channels, wetness, occlusion march, `rock_base` and `rock_shadow` marches, snow, vegetation, strata), padding from the parents (`StackSampler`), norms (exact select), `pin_band`; JS: `MaskParams`, dependency expansion |
| `core/gpu.py` | `core/gpu.js` | section 4 |
| `core/twins.py` | none in production | its job, the oracle, stays in Python: `tests/parity/fixtures.py` runs the Blender twins (5.1) |
| `core/grid.py` | `core/grid.js` + `kernels/grid/` | GPU: `upsample2` (Catmull-Rom, bilinear, nearest), `crop_upsample2`, `box_down`, `resample_box`, `border_ramp`, gradient, slope, aspect, `edge_distance`; JS: frames, `tan_deg`, `index_of`, per-query `sample_bilinear` |
| `core/levels.py` | `core/levels.js` | JS (no per-cell work): `plan_levels`, `select_levels`, `check_plan`, `QUALITY`, with Python's rounding (`round_half_up`, `math.ceil` with the same epsilons) |
| `core/fields.py` | `core/fields.js` | a level's named GPU buffers, CPU mirrors after readback; `inherit` through `kernels/grid/` |
| `core/recipe.py` | `core/recipe.js` | JS: Stage, Knob, Params, Recipe, the op registry; `toDict()` JSON-equal to Python's |
| `core/expr.py` | `core/expr.js` | the parser in JS; evaluation compiles an expression into a WGSL kernel over named buffers (cached by its text) |
| `core/world_noise.py` | `core/world_noise.js` + `kernels/world_noise_field.wgsl`, `kernels/noise.wgsl` | term tables (`_leaf_terms`, `lattice_offset`, `snap_wavelength`) in JS float64; evaluation on the GPU (already so in Blender, `field_gpu`); numpy's `field()` is the oracle, not ported |
| `core/compose.py` | `core/compose.js` + `kernels/compose/` | GPU: `shape` (cone, bowl, profile, array, dome, ridge, plateau, massif, field), `stamp` modes, `uplift`, `start_surface`, `flatten_mask`, `flatten_exact`; JS: the spur plan (numpy RNG), `resolve_flat_heights`' medians from an exact select |
| `core/cache.py` | `core/cache.js` | keys over the recipe, knobs, size, resolution, seed, plan, focus and the port's code hash (`terrain/**/*.js`, `kernels/**/*.wgsl`); entries under `eidoverse/assets/cache/terrain_threejs/<key>/` (that folder is already ignored; kept apart from Blender's `terrain/` so neither prunes the other) |
| `core/io.py` | `core/io.js` | npz read and write (uncompressed `np.savez`, float16 masks included), PNG16 / R32 with the `eidoverse-terrain-heightmap/1` sidecar; PNG codecs from Ekigar's `src/export/png.js` and `png_read.js` |
| `core/metrics.py` | `core/metrics.js` + `kernels/metrics/` | GPU: slope percentiles (exact select), fractions, relief, hypsometric integral, anisotropy harmonics, cliff pairs, depressions (fill and label), the radial spectrum (a GPU FFT, then the 48-bin fit in JS) for `t.metrics()`; the Python judge stays the authority |
| `solvers/fluvial.py` (1,628) | `solvers/fluvial.js` | already GPU: the step. GPU: erodibility, threshold and fault inputs, composite uplift and start, `Sc` from the gradient, rigid masks, the lock's block means (fixed-tree sums), `d8_receivers`, `op_valley_floor`'s channel fills, `op_incise`'s carving; JS: the relief controller's arithmetic, step counts, the lock's phase schedule |
| `solvers/hillslope.py` (627) | `solvers/hillslope.js` | already GPU: creep, threshold, `soil_jacobi`. GPU: `gaussian_blur` (linear creep as a Gaussian, reflect padding of 4 sigma), the soil solve's pyramid, `_downstream` |
| `solvers/hydro.py` (776) | `solvers/hydro.js` + `kernels/hydro/` | already GPU: `route_area`. GPU: `fill_depressions` (a min-max relaxation, exact: min and max only), `flat_distance` (integer relaxation), `flow_receivers`, `path_steps` (pointer jumping), `_descend` (relaxation), `lakes` (labels, per-label maximum by `atomicMax`), `_parent_lake_water`, `inflow`, the convergence check (a reduction) |
| `solvers/hydraulic.py` (663) | `solvers/hydraulic.js` | already GPU: the four pipe passes. GPU: rockness, erodibility, micro-relief, box blurs, the anchor's low-pass, `finish` |
| `solvers/detail.py` (547) | `solvers/detail.js` + `kernels/detail/` | already GPU: breakup. GPU: the Phacelle gully octave (from Ekigar's `src/nodes/phacelle.js`; numpy's `phacelle_noise` is the oracle), planation, relax |
| `solvers/glacial.py` (1,659) | `solvers/glacial.js` + `kernels/glacial/` | already GPU: `ice_flux`, `jump_flood`, `u_carve`. GPU: drainage receivers, `streams` (radix sort by receiver, discharge and index, first-of-segment, pointer jumping), `smooth_along`, head distances, `graded_fill`, `best_donor`, seed textures, `profile_fields`, `trough_target`, `sharpen_walls`, `lip_open`'s 1D filters, wall flutes; JS: the cirque plan (heads are few) |
| `solvers/aeolian.py` (1,315) | `solvers/aeolian.js` | already GPU: the slab model's four kernels. GPU: start fields, steering, the periodic Gaussians (`denoise`, `smooth_sheet`, `stretch_periodic`: circular convolution, or the FFT of `prims`), `sample_periodic`, spacing and height measures; JS: `schedule`, `cycle_blocks` (numpy RNG) |
| `solvers/volcanic.py` (2,975) | `solvers/volcanic.js` + `kernels/volcanic/` | GPU: every profile (exponential and log-linear cones, piles, breaches, flank craters, aged cones, calderas, layered walls, the Fuji and Crater Lake presets), supersampled evaluation, `stamp_add`, ravines, streaks, `lava_surface`, kept basins, `_reach`, `_dilate`, the lake ops; JS: cone and vent plans, azimuth tables (1D), the lava walkers (2.4) |
| `solvers/impact.py` (553) | `solvers/impact.js` + `kernels/impact/` | GPU: the crater, its interior and central peak, the blocks; JS: Pike's numbers, the polygon table, the block plan |
| `solvers/strata.py` (1,604) | `solvers/strata.js` + `kernels/strata/` | already GPU: `StrataRun`. GPU: `offset`, `zs`, facies noise, joint fields, rock mass and cores, caprock fraction (a reduction), `fill_dry_basins`, `plateau_surface`; JS: columns and weather tables (1D), core centres (dart throwing) |
| `solvers/rivers.py` (593) | `solvers/rivers.js` | GPU: `channel` (distance and arc length to the course, segments binned per tile); JS: the courses and the schedule |
| `solvers/karst.py` (1,856) | `solvers/karst.js` + `kernels/karst/` | GPU: `evaluate` (supersampled towers from binned tower tables), cockpit and polje floors (fill and label), rolling min and max, the plain and the river frame; JS: `plan_karst` (Poisson disc, peaks, rib harmonics, scarps, wall tables, k-nearest towers, the 160² Dijkstra) |
| `solvers/coast.py` (1,095) | `solvers/coast.js` | already GPU: fetch, seed, jump flood. GPU: shore cells, `plan_shore`'s labelling and dilation, the shore coordinate, land shape, retreat, stacks, scars, `refine_land`; JS: the face and beach profiles (1D) |
| `recipes/*.py` (16) | `recipes/*.js` | the same stages and knobs; knob `apply` functions and the `defaults_for` / `prepare` hooks transcribed |
| `recipes/__init__.py` | `recipes/index.js` | discovers the modules (`Deno.readDir`), so no package edits a shared list |
| `recipes/real_place.py` | `recipes/real_place.js` | the `dem` op: PNG16 decoded on the CPU (I/O), metres, the surround's push-pull harmonisation, lake bowls and base heights on the GPU |
| `recipes/meadow.py` | `recipes/meadow.js` | the `hummocks` op on the GPU |
| `build/mesh.py` (725) | `build/mesh.js` + `kernels/mesh/` | section 7.3: topology and vertices by kernels, read back once; `heightAt` / `normalAt` in JS per query |
| `build/water.py` (166) | `build/water.js` + `kernels/water/` | lake quads by stream compaction of lake cells, the sea grid, a dark glossy NodeMaterial tinted by the `water` mask |
| `build/dressing.py` (448) | `build/dressing.js` | last wave: placement on the GPU (a hash per candidate cell, mask densities, power-law sizes), `InstancedMesh` of cached CC0 rocks |
| `build/surfacing.py` (1,414), `build/palettes.py` (1,534) | `build/surfacing.js`, `build/palettes.js` | last wave: a TSL NodeMaterial built to `SURFACING_DESIGN.md`, not a port of the old node group; the palettes' data and expression language move with it |
| `relief.py`, `loft.py`, `surface_layers.py`, `_pbr.py`, `_nodes.py` | none | the first three are the Blender ports of this edition's `parallax_material.js` / `parallax_occlusion.js`, `loft.js` and `surface_layers.js`, which stay as they are; the last two are Blender node and PBR helpers |

The registry's 16 recipes: `alpine_valley`, `badlands`, `caldera`, `canyon`, `cinder_cones`, `dunes`,
`fluvial_range`, `impact_crater`, `incised_meanders`, `meadow`, `mesas_buttes`, `real_place`, `rolling_hills`,
`sea_cliffs`, `stratovolcano`, `tower_karst`. The 40 ops they call are registered by 13 solver modules and two recipe
modules (`meadow`: `hummocks`; `real_place`: `dem`).

### 3.3 The kernels

Thirty-one GLSL compute kernels: the 17 files in `kernels/` and 14 written inline in Python. Each becomes one WGSL
file of the same name with its `//!` header copied unchanged; the "bindings" column is samplers plus images, which
the device's `maxStorageBuffersPerShaderStage` must cover (4.7).

| kernel | where it is in Blender | bindings | port owner (section 8) |
|---|---|---|---|
| `flow_weights`, `route_area` | `kernels/` | 2, 5 | P5 hydrology |
| `route_incise`, `creep`, `threshold` | `kernels/` | 9, 4, 7 | P6 fluvial |
| `threshold_excess`, `soil_jacobi` | inline, `solvers/hillslope.py` | 3, 3 | P6 |
| `h_keep`, `creep_layers`, `lock_restrict`, `lock_apply` | inline, `solvers/fluvial.py` | 2, 4, 3, 6 | P6 |
| `ice_flux`, `jump_flood`, `u_carve` | `kernels/` | 5, 5, 9 | P13 glacial |
| `dune_activate`, `dune_shadow`, `dune_transport` | `kernels/` | 4, 3, 3 | P8 wind and sand |
| `dune_avalanche` | inline, `solvers/aeolian.py` | 3 | P8 |
| `strata_threshold` | `kernels/` | 6 | P10 layered rock |
| `strata_cell`, `strata_creep`, `strata_weather` | inline, `solvers/strata.py` | 4, 4, 8 | P10 |
| `coast_fetch` (one source per ray count), `coast_seed`, `coast_jfa` | inline, `solvers/coast.py` | 2, 3, 2 | P11 karst and coast |
| `pipes_flux`, `pipes_water`, `pipes_transport`, `pipes_thermal`, `breakup` | `kernels/` | 7, 8, 6, 7, 3 | P12 detail |
| `world_noise_field` | inline, `core/world_noise.py` | 3 | P2 core inputs |
| `common` | `kernels/common.glsl` | - | P1 runner |

Nine are already transcribed in `tests/design_probes/wgsl/`, and their owners start from those files: `common`;
`flow_weights`, `route_incise`, `creep`, `threshold_excess`, `threshold` and `creep_layers`, checked against the
twins' fixtures (46 cases); `h_keep`, a copy with no fixture case, exercised in the timed fluvial step; and
`world_noise_field`, checked against numpy's `field()`.

### 3.4 What the port adds: `core/prims.js`

Algorithms the Blender edition runs in numpy over whole levels need a few GPU building blocks, each checked against
its numpy original:

| primitive | used by | exactness |
|---|---|---|
| reductions (min, max, sum, count) | controllers, norms, convergence, caprock fraction | min/max exact; sums in a fixed tree |
| radix select on monotonic float keys, then numpy's linear interpolation | every `np.percentile` and median | bit-equal to numpy |
| histogram, prefix scan, stream compaction | lake quads, channel subsets, masks' norms | exact |
| key-value radix sort, segmented first, pointer jumping (list ranking, path maxima) | glacial streams, `path_steps`, receiver trees | exact (integer keys, numpy's tie order) |
| connected components (label propagation with pointer jumping, `atomicMin` hooks) | lakes, basins, coast cuts, cockpits | exact (minimum labels) |
| min-max relaxation (priority-flood fill) | `fill_depressions` and everything built on it | exact: the fixed point of `W = max(h, min_k W_k)` with the outlets held is the priority flood's spill surface, computed with min and max only |
| breadth-first relaxation, receiver trees | `flat_distance`, `flow_receivers` | exact |
| separable Gaussian with Blender's padding and decimation; box blur; dilation | masks, creep aging, aeolian smoothing | f32 against numpy float64 |
| jump flooding | glacial seeds, coast distances (already Blender kernels) | as the Blender kernels |
| radix-2 FFT | the spectrum metric, periodic Gaussians where a direct convolution is too wide | f32 |

---

## 4. The GPU runner

### 4.1 The choice

Three ways to run the kernels were on the table. I measured the first two.

- **Raw WGSL compute pipelines on the scene's `GPUDevice`** (chosen). The kernels are transcriptions of GLSL that
  can be diffed line by line. The six transcribed kernels with fixture cases passed all 46 of the Blender twins'
  cases at their first run through the prototype runner, once the device asked for the storage-buffer limit (4.7):
  worst error 3.06e-5 of a channel's range, identical to the GLSL kernels' own worst against the same twins
  (`blender/tests/terrain/out/fluvial/kernel_tests.json`). JavaScript per dispatch: 6-21 microseconds.
  The fluvial step costs what Blender's does (4.8). WebGPU compute is GPU compute in the edition's sense; the
  NodeMaterial rule concerns materials, which stay TSL (the clay and water materials, and the surface in the last
  wave).
- **TSL compute through `renderer.compute()`** (the pattern of `fluid_swe.js` and `cloth_sim.js`). In a fresh
  process the TSL kernel computes exactly what the WGSL kernel computes (bit-identical at 64² and 512²), so
  correctness is not the problem. The cost is: 0.03-0.56 ms of JavaScript per `compute()` call against 0.006-0.021 ms
  per raw dispatch, a wall time of 0.09-0.28 ms per step at 512² against 0.032 ms, and 70-2,170 ms for a kernel
  pair's first two calls (their pipelines). A film terrain issues on the order of 10^5 dispatches (seven levels,
  1,500-2,000 steps, nine passes), so TSL would spend seconds to a minute issuing what the raw runner issues in one
  to three. And each of the 31 kernels
  would be rewritten in a JS DSL rather than transcribed. The edition's own TSL compute laws (rgba16float
  Storage3DTextures only, one `textureStore` per kernel, a swapping node is a silent no-op: `fluid_swe.js`'s header)
  do not fit float32 kernels that write two RGBA32F outputs. Also recorded, not explained: inside the long benchmark
  session one TSL comparison read back data that did not include its last dispatch.
- **Ekigar's runner.** There is none: `src/compute/` is empty and `docs/STATUS.md` lists flow routing, accumulation
  and priority-flood water levels as gaps. Ekigar's GPU work is TSL field evaluation into render targets for its
  preview. Reused from Ekigar instead: the TSL lattice noise for materials, the Phacelle filter's source, the PNG
  codecs, the texture-array and triplanar material code (last wave) and the headless harness pattern.

### 4.2 Kernels and their interface

- A kernel is `kernels/<name>.wgsl` with the Blender `//!` header lines unchanged (`//! sampler st`, `//! image outS
  rgba32f`, `//! uniform float uDx`, `//! local 16 16`) and a body `fn kmain(p: vec2<i32>)`.
- The runner parses the header (the same grammar as `core/gpu.py`'s `parse_spec`) and generates: the uniform struct
  (WGSL layout rules) with every sampler's and image's size appended; one storage buffer per sampler (read-only) and
  per image (read-write); accessors `st_at(q) -> vec4<f32>` (a 1- or 2-channel field widens like `texelFetch` on an
  R32F or RG32F texture), `st_size()`, `outS_store(q, v)`, `outS_size()`; `common.wgsl`; the 16 x 16 entry point.
  So a GLSL body moves over with `texelFetch(st, q, 0)` read as `st_at(q)`, `imageStore` as `*_store`,
  `textureSize` as `*_size()`, `uDx` as `u.uDx`, and `out` parameters as pointers (`neighbour(p, k, n, mode, &q)`).
- `common.wgsl` is `common.glsl` one for one: `OFF`, `LEN`, `WISO`, `WISO_SUM`, `opp`, the boundary modes,
  `inside`, `wrap`, `neighbour`, `on_edge`, `pin_apply` (written as the twin computes it, `h (1 - a) + pin_h a`, not
  as `mix`, which backends lower to `h + (pin_h - h) a`), `world_xy`, `tan_deg`, the PCG chain, `u01`, `cell_hash`.
  The runtime-indexed constant arrays compile on this machine's wgpu.
- A kernel that needs shared WGSL (Ekigar's lattice noise for `breakup`) declares `//! include noise`; the runner
  prepends `kernels/noise.wgsl`, as Blender's `breakup_source()` substitutes `GLSL_NOISE`.
- Pipelines are created once per kernel and channel signature, inside an error scope; a failure raises naming the
  kernel and printing the generated source with line numbers (the prototype does this). Every declared binding and
  uniform must be given on every run; a field bound as input and output of one dispatch is refused (use the pair).

### 4.3 Fields

- **Storage buffers, not textures.** One `array<f32>`, `array<vec2<f32>>` or `array<vec4<f32>>` per field or pack,
  row-major `[row j][column i]`, row 0 south: the layout of the Blender textures, with the same RGBA packs (`st` =
  h, A, qs, carried; `mk` = wear, deposit, talus, loose; `par` = U, K, Sc, G; `pin` = pin_w, pin_h, A_in, qs_in).
  Measured on the probe kernel: buffers 0.026 ms against 0.035-0.038 ms for sampled-plus-storage textures at 1024²,
  equal at 2048², bit-identical results. Buffers have no format limits, are read-write, and take atomics.
- **Ping-pong** by binding: a `Pair` of buffers and a bind group cached per (kernel, buffers), so a pair costs two
  bind groups for the whole run.
- **Textures only where rendering wants them** (the mask data textures of the last wave, if the surfacing design
  asks for textures): filled on the GPU by `copyBufferToTexture`.

### 4.4 Uniforms and batching

- WebGPU has no push constants (the adapter's `immediate-data` is a proposal; not used). Every dispatch's uniforms
  take one 256-byte slot (`minUniformBufferOffsetAlignment`) of a 4 MB ring, chosen by a dynamic offset; the slots of
  a command buffer are written with one `queue.writeBuffer` before its submit, which the queue orders before the
  submit. So per-dispatch values (an iteration index for the dune hashes, the lock's phase, a jump-flood step) cost
  nothing extra.
- Dispatches are recorded into one compute pass per command buffer, submitted every 50 steps or at a readback.
  Measured: one submit per dispatch costs 0.72-0.80 ms a dispatch, a hundred times the batched cost.

### 4.5 Readback and synchronisation

- Every wait for the GPU costs about 16 ms on Deno 2.8.1 here: 16.7 ms (median of 20) to read 16 bytes, 16.6 ms for
  an empty submit and `onSubmittedWorkDone`. Whole fields add about 3 ms per MB: 27.8 ms for a 1024² R32F field,
  73.6 ms RGBA32F, 63.9 ms for 2048² R32F, 215.7 ms RGBA32F. Uploads: 25 ms for a 1024² RGBA32F pack, 54-79 ms at
  2048².
- So a solver loop never waits inside a step. The relief controller (every 100 steps), route convergence (every 128
  iterations), fill and label convergence (every 256) read back a reduction of a few bytes. Whole fields are read
  back once, at a level's end, into preallocated arrays from a persistent `MAP_READ` buffer.

### 4.6 Boundaries, hashes, tables

- OPEN, PERIODIC and PINNED exactly as `common.glsl`, checked by the 46 fixture cases (every case in all three).
- PCG, `pcg2`, `pcg3`, `cell_hash` and `u01` are bit-exact against the numpy twins on an 80 x 96 grid; Ekigar's
  lattice hash is integer-exact; the world-noise kernel is within 9.2e-7 of range of numpy's float64 at a level 40 km
  from the origin (the term table keeps integer lattice bases and float32 fractions, as Blender's does).

### 4.7 The device

- **In a scene:** the runner takes `GPU_DEVICE` (`render_scene.mjs` sets it; the scene's `WebGPURenderer` uses the
  same device), or `opts.renderer.backend.device`. **In the CLI and tests:** `requestRenderAdapter()` from
  `gpu_check.mjs`, then `requestDevice` with the limits below.
- **Limits.** `route_incise` and `u_carve` bind 9 storage buffers in one stage; WebGPU's default
  `maxStorageBuffersPerShaderStage` is 8 (the prototype failed with "BindGroupLayout ... is invalid" until it asked).
  The adapter offers 1,048,576. `render_common.mjs` already raises `maxStorageBufferBindingSize` and `maxBufferSize`
  to the adapter's values; the runner package (P1, wave 1) adds `maxStorageBuffersPerShaderStage` and
  `maxComputeWorkgroupStorageSize` to that list, so scenes that run the generator have them from the start. On an
  adapter that offers fewer than 9 the runner fails at initialisation, naming the limit.
- **Self-test** at initialisation: one dispatch whose readback must be exact (`gpu_check.mjs`'s and `gpu.py`'s
  `_self_test`), so a broken driver fails loudly. On a software adapter (the edition supports one for hosted sandboxes)
  the runner warns that generation runs on the CPU and is many times slower; there is no CPU path in production.
- **Headless:** raw compute needs no canvas; only the TSL materials and the review renders go through the edition's
  renderer.

### 4.8 The benchmark

The Blender design's probe kernel (one stream-power gather step: 8 neighbour reads, slopes, an MFD area gather,
incision, uplift; RGBA32F in and out), and the Blender fluvial production step (9 passes: `flow_weights`,
`route_incise`, `h_keep`, `creep`, `creep_layers`, then `threshold_excess` and `threshold` twice, at the Blender cost
test's settings). GPU times are timestamp queries over a pass of many steps; wall times are the loop without
readbacks. Two runs each: the machine is shared and the second fluvial run had a Blender job beside it.

| | 512² | 1024² | 2048² | 4096² |
|---|---|---|---|---|
| probe kernel, GPU per pass, WGSL buffers | 0.0059-0.0066 ms | 0.026 ms | 0.20-0.28 ms | 0.77-0.85 ms |
| probe kernel, GPU per pass, Blender GLSL (design / core re-run) | 0.016 / 0.0095 ms | 0.061 / 0.062 ms | 0.23 / 0.18 ms | 0.49 / 1.66 ms |
| probe kernel, wall per step, WGSL (500 dispatches a submit) | 0.032 ms | 0.047 ms | 0.32 ms | |
| probe kernel, wall per step, TSL `compute()` (two runs) | 0.28 / 0.092 ms | 0.60 / 0.061 ms | 0.29 / 0.61 ms | |
| fluvial step (9 passes), WGSL wall, quiet run | 0.26 ms | 1.08 ms | 3.91 ms | |
| fluvial step, WGSL GPU, quiet run | 0.079 ms | 0.61 ms | 3.01 ms | |
| fluvial step, WGSL wall, beside a Blender job | 1.19 ms | 2.76 ms | 6.36 ms | |
| fluvial step, Blender GLSL wall (`kernel_tests.json`) | | 1.02 ms | 4.46 ms | |
| readback of one field, R32F / RGBA32F | | 27.8 / 73.6 ms | 63.9 / 215.7 ms | |

JavaScript issue per dispatch: 6-21 microseconds (Blender's Python: 3.3-10). At 512² the step is bound by issuing,
not by the GPU (0.26 ms wall against 0.079 ms GPU); the pre-passes at 256² and 512² pay that. Every run was
bit-identical to its repeat: the probe kernel over 200 steps at 512² to 4096², the fluvial step over 205 steps at
512² to 2048².

### 4.9 Memory

A level being solved holds its packs (two `st`, two `mk`, `par`, `pin`: six RGBA32F buffers) and five single fields
(wsum, kept height, excess, lock, column): about 460 MB at 2048², 115 MB at 1024². A finished level keeps on the GPU only
what a later step reads (its height and drainage area for the child's inheritance and inflow, its height for the
mesh); everything else is read back into `Float32Array`s and the GPU buffers are released. Masks are computed level
by level and read back; bounded masks are cached as float16, as Blender caches them.

| quality | GPU peak | host arrays (fields and masks of every level) |
|---|---|---|
| draft (512², no hero) | about 0.2 GB | about 0.3 GB |
| film (1024², up to 7 levels) | about 0.6 GB | about 1.6 GB |
| hero (2048², up to 7 levels) | about 1.5 GB | about 6 GB (float16 masks: about 4.5 GB) |

These are estimates from the field and mask counts (Blender's own note: seven levels of 1000 cells hold about 700 MB
of masks at float32). Measured: 177 buffers holding 3.19 GiB (seven levels of 24 single 2048² fields plus nine RGBA
packs) were allocated and cleared without an out-of-memory or validation error. That probe's process peaked at
7.5-7.8 GB of host memory; it made a fresh readback buffer and a fresh copy for every read, and staged every clear,
which I take to be most of it. So the runner reuses one staging area and one mapped readback buffer, and generation
jobs run under the machine's memory cap (12 GB for hero quality).

---

## 5. The parity protocol

### 5.1 The oracles

| oracle | made by | what it checks |
|---|---|---|
| **kernel fixtures** | `tests/parity/fixtures.py --kernels` runs each Blender kernel's numpy twin on the Blender package tests' own inputs (a non-square 96 x 80 field with pins, every boundary mode, every variant the Blender tests run) | one WGSL dispatch |
| **function fixtures** | `--functions` runs the Blender numpy functions that become GPU code (`fill_depressions`, `lakes`, `routing_surface`, `route_to_convergence`, `inflow`, `crop_upsample2`, `resample_box`, `masks.compute`, the compose shapes, the volcanic and karst `evaluate` functions, `streams`, ...) on recorded inputs | a GPU replacement of numpy code |
| **plan fixtures** | `--plans` dumps every plan as JSON for seeds 1-8 (karst plans, cone and vent lists, river courses, wind schedules, cirques, strata cores, crater blocks, uplift spurs) and numpy's draws for every call form the terrain uses | `core/np_random.js` and the JS plans |
| **recipe fixtures** | `--recipes` dumps `to_dict()`, `resolve(params)` for the default and two other knob sets, `describe()`, and `plan_levels` for 20 focus cases at each quality | `core/recipe.js`, `core/levels.js`, the recipe modules |
| **stage dumps** | `tests/parity/blender_stage_dump.py`, run in Blender, wraps the registry's ops and the runner's end stages from outside (no change to the Blender branch) and saves every stage's fields before and after, with its context | one op, from Blender's own input |
| **saves** | the Blender CLI as it is: `bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe R --seed S --quality Q --save --out <dir>` | whole recipes, per level |

Fixtures from numpy run in plain Python (`fixtures.py`); the plan fixtures run in Blender's own Python, because the
plans are drawn by Blender's bundled numpy. Fixture files go to `eidoverse/terrain/tests/out/parity/` (ignored), keyed
by the Blender commit and the Blender `code_hash()`.

### 5.2 The dump formats

- **A terrain** is the `Terrain.save` format both editions write and read: `<name>.npz` (uncompressed `np.savez`)
  with `L{i}__f__{field}` (float32 (n, n), row 0 south, metres) and `L{i}__m__{mask}` (float16 for bounded masks,
  float32 for metres and curvatures), and `<name>.json` with the info record, `recipe` (`to_dict()`), `knobs`, `plan`
  (each level's `to_dict()`: index, role, x0, y0, side, cell, n, parent, stride, prepass, band, depth) and
  `api_version`. The port adds `<name>_parity.json`: the edition, the commit, the code hash, the GPU, the numpy or
  Deno version, the date. The Blender judge's `--field` reads this file as it is.
- **A stage dump** is `<recipe>_s<seed>_<quality>/L{i}_p{k}_{n:02d}_{op}_{before|after}.npz` (every array of the
  level's Fields) and `stages.json` (per stage: level, pre-pass, index, op, label, params, `where`, seconds, and the
  context: role, `fresh`, `prepass`, pins as arrays in the npz, the JSON-able part of `shared` such as `relief` and
  `U_factor`).
- **A fixture** is a folder of little-endian `.bin` arrays ((H, W, C), row 0 south) and a `manifest.json` (the case
  list: kernel or function, uniforms or arguments, inputs, expected outputs), as `tests/design_probes/make_twin_fixtures.py`
  writes them.

### 5.3 The grades and their tolerances

| grade | compared | tolerance | why that tolerance |
|---|---|---|---|
| integer | hashes, labels, counts, receivers and BFS distances on equal input, radix-selected percentiles | bit-exact | integer arithmetic and comparisons; measured exact for the PCG chain and the lattice hash |
| draws | numpy's Generator | bit-exact, draw for draw | measured 290 of 290 |
| plans | plan JSON | 1e-12 relative | both float64; V8's `Math` against the C library: a last-ulp difference at most |
| recipes | `toDict()`, resolved stages, `describe()`, level plans | equal JSON | data |
| kernel | one dispatch against the numpy twin | max \|gpu - twin\| ≤ 1e-4 x each output channel's range | the Blender edition's own tolerance for its GLSL; measured worst for the WGSL 3.06e-5, the GLSL's own 3.06e-5; covers FMA contraction and the built-ins' errors (2.3) |
| function, exact kind | fill, labels, BFS, receivers, path steps, selections | bit-exact | min, max, integers only |
| function, float kind | resampling, blurs, shapes, stamps, noise, masks, mesh vertices | ≤ 1e-5 x range (masks and meshes: ≤ 1e-4 x range) | f32 against numpy's float64; world noise measured 9.2e-7 |
| stage replay, non-evolving op | an op run once from Blender's input | ≤ 1e-4 x range | a few dispatches |
| stage replay, evolving op | an op that steps (fluvial, creep, talus, dunes, pipes) from Blender's input | ≤ max(1e-4 x range, 1.5 x the Blender floor of that op from that input) | the floor of one stage, measured by the same perturbation as 5.4 on the stage alone |
| recipe, field class | per level: RMS(h_port - h_blender) / relief, p99 \|dh\| / relief, channel overlap | ≤ 1.5 x the recipe's Blender floor on every level | the floor is what a perfect port still shows |
| recipe, distribution class | the judge's numbers over seeds 1-4 | each metric's mean within half its band's tolerance of Blender's mean; every band Blender passes on 3 or more of the 4 seeds, the port passes on 3 or more | a chaotic recipe's numbers move by a band's width on one ulp |
| judge | the Blender judge's verdicts on the port's saves | the same pass or fail per band and family number as the Blender saves of the same recipe and seed (field class), or the rule above (distribution class) | one judge |
| look | the port's renders beside the photographs and beside Blender's renders | by eye: one paragraph per view naming what reads and what does not | DESIGN.md item 7 |

### 5.4 The chaos floor, measured

`blender_chaos_floor.py`, draft quality, seed 1: each recipe generated twice as it is, then once with every
`FluvialRun` start (layered rock's `StrataRun` included) moved by +1 ulp on a random quarter of the cells and by
-1 ulp on about a fifth. The reruns were bit-identical on every level of every recipe.

| recipe | level (cell) | RMS / relief | p99 \|dh\| / relief | channel overlap |
|---|---|---|---|---|
| `stratovolcano` | context (312.5 m) | 1.34 % | 6.6 % | 0.87 |
| | context (156.2 m) | 0.92 % | 4.1 % | 0.82 |
| | main (78.1 m) | 0.34 % | 1.6 % | 0.82 |
| `canyon` | context (31.25 m) | 0.46 % | 2.1 % | 0.70 |
| | main (15.6 m) | 0.75 % | 3.7 % | 0.49 |
| `fluvial_range` | context (375 m) | 1.05 % | 4.2 % | 0.43 |
| | context (187.5 m) | 1.93 % | 7.2 % | 0.24 |
| | context (93.75 m) | 4.77 % | 18.9 % | 0.21 |
| | context (46.9 m) | 6.93 % | 20.3 % | 0.20 |
| | main (23.4 m) | 12.6 % | 28.6 % | 0.10 |

The main level's judge numbers, unperturbed against perturbed:

| | relief m | hypsometric | slope p10 / p50 / p90 / p99 deg | fraction under 5 deg | spectrum knee m |
|---|---|---|---|---|---|
| `stratovolcano` | 3660.7 / 3660.7 | 0.248 / 0.248 | 1.36 / 6.45 / 32.71 / 40.08 against 1.34 / 6.44 / 32.68 / 40.07 | 0.422 / 0.423 | 2360 / 2360 |
| `canyon` | 1568.5 / 1576.8 | 0.500 / 0.498 | 1.13 / 17.46 / 55.47 / 70.17 against 0.99 / 17.44 / 55.48 / 70.28 | 0.278 / 0.277 | 1335 / 1335 |
| `fluvial_range` | 1845.2 / 1742.8 | 0.325 / 0.250 | 18.5 / 34.4 / 43.4 / 50.2 against 5.1 / 32.6 / 43.1 / 50.1 | 0.035 / 0.099 | 795 / 250 |

So after a one-ulp difference a volcano and a canyon are still the same landform, and the fluvial range is a
different range: its drainage network reorganises, the divergence grows down the level stack, and band numbers move by about
a band's width (the fraction under 5 degrees by 0.064 against a tolerance of max(0.05, 40 %)). The same is true of
the Blender edition on another GPU or driver, which DESIGN.md section 2.6 already anticipates ("the cache is per
machine and tests compare metrics, not bytes").

**The classes.** The parity package measures the floor for all 16 recipes at draft quality, seeds 1 and 2, before
any recipe package is accepted: a recipe whose main-level floor is under 2 % RMS of relief on both seeds is in the
field class, the rest in the distribution class. From the three measured: `stratovolcano` and `canyon` field,
`fluvial_range` distribution. I expect `rolling_hills`, `meadow`, `badlands` and the fluvial range under
`alpine_valley` in the distribution class, and the volcanic, crater, karst, coast and `real_place` recipes in the
field class; the measurement decides.

### 5.5 The gate

- Every recipe at draft quality at its reference's extent: seeds 1 and 2 (field class), seeds 1-4 (distribution
  class); the port's save judged by the Blender judge beside the Blender save's verdicts.
- Film quality with a focus (hero levels, seams, collider, mesh): `real_place` Lauterbrunnen and `alpine_valley`,
  seed 1.
- Hero quality once (time and memory at 2048²): `real_place` Lauterbrunnen.
- Stage replay for every op on the dumps of the draft runs above.
- The Blender side runs through the GPU queue: about 15-75 s per draft recipe on this machine (measured 14-74 s,
  depending on what else ran), so the whole floor-and-gate set is about an hour of one slot.

### 5.6 Keeping up with the Blender edition

The Blender edition is being finished while the port is built. So:
- every port file starts with `// Port of blender/eidoblend/terrain/<file> at <commit>.`;
- `tests/parity/sync_status.mjs` lists, per port file, the Blender files changed since its recorded commit
  (`git -C $EIDO_BLENDER_EDITION log` on the `blender` branch: read-only);
- fixtures and dumps are keyed by the Blender commit and `code_hash()`, so a stale fixture is never compared with
  new code;
- a package re-ports a changed Blender file as its own change, with the twin fixtures regenerated, before it moves on.

---

## 6. Shared data

### 6.1 What exists, and where

All of it is in the Blender branch's `blender/tests/terrain/`:

| data | tracked in git | size | how it is made |
|---|---|---|---|
| `reference/data/<name>.json`, `<name>_context.json` (20 places: grid, source, licence, attribution, lakes, `shape_stats`) | yes, 40 files | small | `reference/fetch_references.py` |
| `reference/data/*.png` (16-bit DEMs and water masks) | no (ignored) | 51 MB | `python -I reference/fetch_references.py --downloads <empty folder>` (GSI, USGS 3DEP, Copernicus GLO-30, swissALTI3D, Terrain Tiles; no keys) |
| `reference/renders/<name>_views.json` (the top, aerial and eye cameras, sun and sky of each place) | yes, 20 files | small | `reference/render_references.py` |
| `reference/renders/*.png`, `reference/quicklook/` | no | 32 MB, 14 MB | the same scripts |
| photographs, `out/<package>/photos/**` with `sources.json` (title, page, author, CC0 or public-domain licence) | no | 65 MB | `integration/fetch_photos.py`, `volcanoes_craters/fetch_photos.py`, `layered_rock/fetch_photos.py`; the coast's and the glacial valley's photographs sit in `out/coast/photos/` and `out/glacial/photos/` with their `sources.json` |
| `judge/bands.json`, the judge's code | yes | small | `judge/calibrate.py` |

### 6.2 How the port reads it

`tests/_where.mjs` mirrors the Blender branch's `blender/tests/_where.py` (new there, untracked as I write):
- **The Blender edition:** `blender/` in this checkout when it is a `blender`-branch checkout (that branch merges
  `main`, so after the merge it holds both editions), else `$EIDO_BLENDER_EDITION` (the root of a checkout of the
  `blender` branch, such as a worktree).
- **DEMs for `real_place`:** `$EIDO_TERRAIN_DEMS` (the Blender edition's variable: folders separated by the path
  separator), then the Blender edition's `reference/data`. A name that is in neither raises, naming both.
- **GPU jobs:** `$EIDO_GPU_WRAP` is put in front of every Deno or Blender job a test starts (the Blender branch's
  convention); unset, the job runs directly.
- **Missing inputs:** a test that needs one of these and cannot find it skips, printing the variable to set and the
  fetch command, as `_where.external()` does. Nothing has a default path of one machine.

### 6.3 One judge, the port's own renders

- **Numbers and bands:** `tests/judge/judge.mjs` saves the port's terrain in the `Terrain.save` format and runs the
  Blender judge on it: `python blender/tests/terrain/judge/run.py --field <save.npz> --reference <name>
  --no-render --out <dir>` from the Blender checkout. It reads `verdicts.json`. One judge, so a difference in a
  number is a difference in the ground.
- **Views:** the port renders the reference's three views itself, in the three.js edition's renderer: a scene made
  from `<name>_views.json` (camera, target, lens, sun, sky `earth` at the given hour, axes converted as in 2.2),
  grey clay at albedo 0.18 like the reference rig, rendered through `eidoverse/render_scene.mjs` at 960 x 540.
- **Photo-matched views:** where a Blender package matches a photograph's camera to the generated terrain
  (`coast/render_photo_views.py`, `glacial/photo_views.py`, `volcanoes_craters/render_photo_views.py`,
  `karst/render_photo_views.py`: the camera matched in kind, from an anchor on the terrain), the port renders from the
  camera JSON those scripts write for the same recipe and seed when the recipe is in the field class, and ports the
  matching rule into `tests/judge/views.mjs` for the distribution class, whose terrains differ.
- **Sheets:** per recipe, a row each: the reference's Blender renders, the Blender recipe's renders (from its own
  judge run, when present), the port's renders, and the place's photographs, with the numbers under each.

### 6.4 Licences

DEM attributions travel in the JSON (GSI, Copernicus and swisstopo require them; USGS is public domain); a port terrain
made from a real DEM carries `t.info.attribution` as the Blender one does. Photographs are CC0 or public domain only,
each with its `sources.json`. Nothing of either goes into the three.js branch.

---

## 7. The mesh and the API

### 7.1 The call

```js
const t = await makeTerrain({
    recipe: 'alpine_valley',     // a name from makeTerrain.recipes(), a recipe object (toDict() form), or a list of stages
    size: 8000,                  // metres, the main tile (default per recipe)
    resolution: null,            // cells across the main tile (draft 512 / film 1024 / hero 2048)
    seed: 7,
    params: { relief_m: 2800, ela_m: 2300 },   // the recipe's knobs, Blender's names and units
    focus: null,                 // [x, z], [[x, z], ...], an Object3D (a camera), or an array of them: hero levels
    heroCell: 0.5,               // metres
    context: null,               // the horizon levels' extent multiplier (default per recipe)
    flatten: [{ at: [40, 12], radius: 15, falloff: 10, height: null }],   // at: three.js (x, z); height null = median
    seaLevel: null,              // metres (three.js y)
    baseElevationM: null,        // the altitude of y = 0 (snowline, treeline, ELA)
    palette: 'auto',             // last wave; null = grey clay
    dress: true,                 // last wave
    quality: 'film',             // 'draft' | 'film' | 'hero'
    cache: true,
    name: 'terrain',
    meshRes: 512,                // vertices per side a level is drawn at
    renderer: null,              // optional; its device is GPU_DEVICE in a scene
    log: console.log,
});
scene.add(t.mesh);
```

| Blender `make_terrain` | port `makeTerrain` |
|---|---|
| `recipe, size, resolution, seed, params, context, palette, dress, quality, cache, name` | the same names |
| `focus`: (x, y), points, a camera object, cameras | `[x, z]`, points, an `Object3D`, objects (2.2) |
| `hero_cell, sea_level, base_elevation_m, mesh_res` | `heroCell, seaLevel, baseElevationM, meshRes` |
| `flatten` with `at: (x, y)` | `at: [x, z]` |
| `collection` (Blender) | none; `renderer` (optional) |
| returns a `Terrain`; `obj, height_at, masks = t` | returns a Promise of a `Terrain`; `const { mesh, heightAt, masks } = t` |
| `recipes()`, `describe(name)` | `makeTerrain.recipes()`, `makeTerrain.describe(name)` (no new globals) |

The old options (`segments`, `amplitude`, `layers`, `flatRadius`, `flatHeight`, `slopeSteep`, `highStart`,
`octaves`, `frequency`) raise an error that names the new call and the nearest option.

### 7.2 The Terrain

| member | what it is |
|---|---|
| `t.mesh` | the ring mesh, one `THREE.Mesh` (7.3); `userData.eidoTerrain` holds the recipe, knobs, seed, plan and cache key |
| `t.collider` | the collider proxy: a `Mesh` of the walkable rings near the focus, also `t.mesh.userData.colliderProxy` (7.5) |
| `t.heightAt(x, z)` | metres (three.js y) exactly on the rendered triangles of the finest ring holding the point |
| `t.normalAt(x, z, smooth = true)` | the shading normal there, three.js axes |
| `t.masks`, `t.mask(name)` | a `MaskSet`; `t.mask('slope').at(x, z)`, `.array(level)` (Blender frame), `.names()` |
| `t.levels` | each level's window, cell and role (Blender metres) |
| `t.fields(level)` | the level's arrays (host copies) |
| `t.flats`, `t.water` | the resolved flatten areas; `{ lakes: [Mesh], sea: Mesh or null }` |
| `t.metrics(pixelM)` | the judge's generic numbers of the main tile (`core/metrics.js`) |
| `t.viewpoint(target, distance, opts)` | a standing point that sees the target, as Blender's `viewpoint` (the judge's eye spots), in three.js axes |
| `t.preview(path)` | hillshade and mask PNGs |
| `t.save(path)`, `Terrain.load(path)` | the `Terrain.save` format (5.2): a port save loads in Blender and the reverse |
| `t.dispose()` | releases the GPU buffers and geometry |

### 7.3 The ring mesh as a BufferGeometry

The same construction as `build/mesh.py`, built by kernels:
- **Windows on the integer lattice** of the finest cell (`_integer_windows`), rings as each level's window minus its
  child's, `stride = round(n / meshRes)` (2 at 1024 cells), cores on the finest level down to stride 1 when there is a
  focus. The ring specs are a handful of integers per level, computed in JS exactly as `plan_rings` does.
- **Vertices** by a kernel per ring: each level's height at the cell corners by Catmull-Rom (weights -1, 9, 9, -1
  over 16), the seam row overridden by the parent's straight edge, shared vertices where two rings meet, then the
  axis conversion; mask attributes bilinear (until the surfacing wave decides between attributes and per-level
  textures).
- **Indices** by a kernel per ring: every quad split along its (i, j) - (i + 1, j + 1) diagonal, the parent's cells
  along the hole drawn as fans through the child's in-between vertices (no T-junction), the outer skirt 50 m below
  the lowest border vertex. The topology is a pure function of the ring specs, so it is compared index for index
  with Blender's `RingMesh` (after the axis conversion).
- **Normals** by a kernel: area-weighted face normals summed per vertex as fixed-point integers with integer atomics
  (deterministic), then normalised.
- **Read back once** (positions, normals, indices: about 80 MB for 3.3 M triangles, about 0.3 s), then a plain
  `BufferGeometry` (`Uint32` index) with `boundingBox` and `boundingSphere` set from the GPU's height range, so nothing
  walks the vertices on the CPU. The host copies serve `heightAt` and the collider.

### 7.4 `heightAt`, `normalAt`, `viewpoint`

- `heightAt(x, z)`: Blender `height_at(x, -z)`: the finest ring whose window holds the point, the cell, the triangle
  by the diagonal rule or the fan rule, barycentric in float64 on the float32 vertices. Exact on the rendered
  triangles, as Blender's; outside the outermost window, its edge.
- `normalAt`: the vertex normals interpolated (smooth) or the triangle's.
- `viewpoint`: Blender's candidate search (every 5 degrees, 0.55-1.5 x the distance, sight lines sampled 160 times,
  footing under 30 degrees, ranked by heading, low or high ground, distance) on `heightAt`.

### 7.5 The collider and ray casting

- **Collider proxy.** `robot_controller.js` builds a Rapier trimesh from every mesh it is given that carries
  `userData.trimeshCollider`, looping over its vertices; a film terrain is about 3.3 M triangles. `t.collider` is a
  mesh of the rings within the hero windows (or of the main level within 1 km of the focus; at most about 2 M
  triangles), outside the scene graph, with `t.mesh`'s world matrix. `t.mesh` keeps `userData.trimeshCollider = true`
  (as the old terrain's mesh did) and adds `userData.colliderProxy = t.collider`; the controller gains one condition,
  to build from the proxy when a mesh has one. Scenes keep passing `terrain.mesh`. (Marking the visual mesh
  `noWalkable` instead would not work: the controller skips such a mesh before it looks at anything else.) The proxy's
  surface is the visual surface (the same vertices and triangles), checked against `heightAt`.
- **Exact ray casting.** `t.mesh.raycast` is replaced by a height-grid ray caster: a vertical ray is `heightAt`; any
  other ray walks the cells of the finest ring under it (a 2D DDA) and intersects that cell's two triangles exactly.
  So `snapToGround`, the camera-safety checks and the weather system's strikes stay exact without three's loop over
  millions of triangles.

### 7.6 In a scene

- `eidoverse/terrain.js` (still in `HELPER_MODULES`) installs `globalThis.makeTerrain = async (opts) => (await
  import(EIDOVERSE_DIR + 'terrain/index.js')).makeTerrain(opts)`, with `makeTerrain.recipes` and
  `makeTerrain.describe`, and records the tool in `_eidoToolUsage`.
- The runner uses `GPU_DEVICE`, and `render_common.mjs` requests the two extra limits (4.7).
- The terrain mesh spans far more than 20 m, so the post-setup placement checks never move it (`scene_placement.js`'s
  ground-scale rule).
- The clay material (`palette: null`) and the water material are NodeMaterials; until the last wave, `palette:
  'auto'` gives the clay with a warning.

### 7.7 Callers

To move, in the integration package (8.2, P16):
- `eidoverse/terrain.js`: the old implementation goes (git history keeps it), the installer above takes its place;
- `eidoverse/render_scene.mjs`: the `HELPER_MODULES` comment on `terrain.js` (line 326);
- `eidoverse/robot_controller.js`: one condition, to build the trimesh from `userData.colliderProxy` when a mesh has
  one (7.5), and the comment that `makeTerrain` marks its mesh (lines 79-80) rewritten to say so;
- `README.md`: the World building entry (line 111);
- `tools-guides/terrain-surfaces.md`: the `makeTerrain` section rewritten for this API (await, recipes, focus,
  heightAt, masks, the collider, `bake.mjs`);
- `tools-guides/vegetation.md`: its `heightFn: terrain.heightAt` examples keep working; they gain the `await`;
- `docs/TOOLS.md`: the `eidoverse/terrain.js` row, and new rows for `eidoverse/terrain/` and `bake.mjs`;
- `AGENTS.md`: the terrain-surfaces index row, if its wording changes.

Earlier, in wave 1, the runner package (P1) adds the two device limits to `eidoverse/render_common.mjs` (4.7) and
`eidoverse/terrain/tests/out/` to `.gitignore`.

Not moving: `eidoverse/terrain_base.js`, `eidoverse/examples/obstacle_course.js`, and the characters and navigation
guides' references to the locomotion template (0, item 9).

---

## 8. Packages and waves

### 8.1 Rules for every package

The lead's standing block applies on top of these.
- **Ownership.** A package owns exactly the files in its row and edits nothing else; it reads anything, including the
  Blender branch (read-only). Tests go in `eidoverse/terrain/tests/<package>/`, outputs in
  `eidoverse/terrain/tests/out/<package>/`.
- **Port, don't substitute.** A module is transcribed from its Blender file at the recorded commit; a deviation (an
  algorithm that cannot run on the GPU as written) is named in the file's header with the reason, and its oracle
  still passes. A package that finds the Blender code wrong reports it to the lead; the port does not fix the source
  of truth on its own.
- **The edition's rules.** NodeMaterials only; per-texel work as GPU compute; JavaScript per cell only in tests.
  Nothing machine-specific in any file: paths come from `tests/_where.mjs`, GPU jobs go through `$EIDO_GPU_WRAP`.
- **GPU jobs** (Deno WebGPU runs and Blender runs alike) go through the machine's GPU queue with a memory cap
  (8 GB, 12 GB at hero quality) and a watchdog, one at a time per agent, never in a detached console.
- **Looking.** Look at every render beside its reference and photographs, as an environment artist; name defects
  concretely.
- **Stopping.** When the acceptance passes and the renders read right, stop; refinements go in the report.
- **Visible edits** with the Edit and Write tools.

### 8.2 The packages

GPU-heavy: needs many GPU-queue runs (Blender dumps, chaos floors, solver runs, renders).

| # | package | owns | ports | reuses | depends on | acceptance | GPU-heavy |
|---|---|---|---|---|---|---|---|
| P1 | **Runner and primitives** | `core/gpu.js`, `core/prims.js`, `core/np_random.js`, `kernels/common.wgsl`, `kernels/prims/*`, `tests/core_runner/*`; the `.gitignore` line and the limits list in `eidoverse/render_common.mjs` | `core/gpu.py`, `common.glsl`, numpy's Generator | `tests/design_probes/mini_runner.mjs`, `wgsl/common.wgsl`, `np_random_probe.mjs`; `gpu_check.mjs` | - | round trips exact; the 46 design-probe fixture cases pass through the production runner; every primitive against its numpy original (fill and labels bit-exact, selections bit-equal to `np.percentile` with ties, sorts and scans exact, Gaussian within 1e-5); `np_random.js` draw for draw against Blender's numpy for `random`, `uniform`, `integers`, `normal`, `standard_normal`, `exponential`, `poisson`, `choice` (the ziggurat tables come from numpy's source, BSD-3, with the notice) over 50 seeds and every call form the terrain uses; the 4.8 benchmark re-run; determinism | moderate |
| P2 | **Core inputs** | `core/levels.js`, `grid.js`, `fields.js`, `recipe.js`, `expr.js`, `world_noise.js`, `compose.js`, `cache.js`, `io.js`, `kernels/grid/*`, `kernels/compose/*`, `kernels/world_noise_field.wgsl`, `kernels/noise.wgsl`, `tests/core_inputs/*` | `core/*.py` but gpu, twins and metrics | the design probe's `world_noise_field.wgsl`; Ekigar's `src/export/png.js`, `png_read.js` | P1's interfaces | `plan_levels` JSON-equal for 20 focus cases at every quality; recipe `to_dict` / `resolve` equal; expressions equal in parse and within 1e-6 in value; world noise (sums, products, warps, periodic) within 1e-6 of range; shapes and stamps within 1e-5; resampling within f32 rounding; a Blender `Terrain.save` read and written back byte-identical in its arrays; PNG16 and R32 files byte-identical to Blender's `export_heightmap` | light |
| P3 | **Parity and judge** | `tests/_where.mjs`, `tests/parity/*` (`fixtures.py`, `blender_stage_dump.py`, `blender_chaos_floor.py`, `replay.mjs`, `field_parity.mjs`, `sync_status.mjs`), `tests/judge/*` (`judge.mjs`, `views.mjs`, `sheets.mjs`), `core/metrics.js`, `kernels/metrics/*` | `core/metrics.py`; the harness, not the judge | the Blender judge, bands, references, view JSONs and photographs in place; `bake.py --save` | P1, P2 | the adapter's verdicts on Blender's own saves equal `run.py`'s; the chaos floor of all 16 recipes, seeds 1-2, recorded with the classes; the reference views of five places rendered by the three.js edition and framed like the Blender reference renders (a sheet); `core/metrics.js` equal to `metrics.py` on five reference DEMs (percentiles exact, the rest within 1e-6 relative, the spectrum within 1e-4); `sync_status.mjs` lists the changed Blender files | heavy (Blender) |
| P4 | **Mesh and API** | `api.js`, `index.js`, `bake.mjs`, `build/mesh.js`, `build/water.js`, `build/collider.js`, `kernels/mesh/*`, `kernels/water/*`, `recipes/index.js`, `recipes/real_place.js`, `tests/mesh_api/*` | `api.py`, `bake.py`, `build/mesh.py`, `build/water.py`, `recipes/__init__.py`, `recipes/real_place.py` | Ekigar's `terrain_mesh.js` measurements; `scene_placement.js` and `robot_controller.js` contracts | P1, P2; builds from Blender saves before any solver exists | from a Blender save: ring topology index-equal to Blender's `RingMesh`, vertices within 1e-6 m, `layout()` JSON equal; `heightAt` within 1e-4 m of Blender's `height_at` at 2,000 points (a Python dump); no cracks (a top-down render over an emissive backdrop shows no backdrop pixel along a seam); the ray caster equal to a brute-force triangle ray cast on 1,000 rays; the collider's surface within 1e-3 m of `heightAt`, built by Rapier in under 2 s; `real_place` Lauterbrunnen with a hero window: no seams, a VRM placed by `heightAt` stands on the ground (render); unknown options and knobs name the nearest; a cache hit at film quality in under 5 s | moderate |
| P5 | **Hydrology and level runner** (critical path) | `run.js`, `solvers/hydro.js`, `kernels/flow_weights.wgsl`, `kernels/route_area.wgsl`, `kernels/hydro/*`, `tests/hydro/*` | `run.py`, `solvers/hydro.py` | the design probe's `flow_weights.wgsl` | P1, P2, P3 | kernel fixtures; function fixtures (fill and lakes exact; routing surface and drainage area within their tolerances; inflow within 1e-6); the runner's inherit, pins and `where` on stage dumps; level seams (\|dh\| ≤ 0.05 m at the border, slope jump ≤ 3 degrees); determinism | heavy |
| P6 | **Fluvial backbone and hillslopes** | `solvers/fluvial.js`, `solvers/hillslope.js`, `kernels/{route_incise,creep,threshold,threshold_excess,h_keep,creep_layers,lock_restrict,lock_apply,soil_jacobi}.wgsl`, `recipes/{fluvial_range,rolling_hills,meadow}.js`, `tests/fluvial/*` | `solvers/fluvial.py`, `solvers/hillslope.py`, the three recipes | the design probe's six transcribed kernels | P5 | kernel fixtures for all nine kernels and every Blender variant; creep and threshold conserve the sum of h within 1e-5 over 300 iterations; stage replay of `uplift`, `fluvial`, `valley_floor`, `incise`, `creep`, `talus`, `threshold`, `soil_hills`, `hummocks`; parity in each recipe's class; the bands against the San Gabriels and the Palouse, the meadow's probe criteria; the step within 1.25 x Blender's measured cost | heavy |
| P7 | **Masks** | `masks.js`, `kernels/masks/*`, `tests/masks/*` | `masks.py` | - | P2, P3 | `masks.compute` on five reference DEMs: every mask within 1e-4 of range; slope equal to the references' JSON; `compute_stack` on a Blender save (padding, norms, border pins) equal; scale independence on 2x resampled fields, as Blender tests it | moderate |
| P8 | **Wind and sand** | `solvers/aeolian.js`, `kernels/{dune_activate,dune_shadow,dune_transport,dune_avalanche}.wgsl`, `recipes/dunes.js`, `tests/wind_sand/*` | `solvers/aeolian.py`, `recipes/dunes.py` | - | P5 | kernel fixtures (the hash decisions identical); sand mass conserved; the wind schedules equal (numpy draws); stage replay; parity in class for star, barchan, transverse and linear; the bands against the Namib, Great Sand Dunes, White Sands and the Namib linear dunes | heavy |
| P9 | **Volcanoes and craters** | `solvers/volcanic.js`, `solvers/impact.js`, `kernels/volcanic/*`, `kernels/impact/*`, `recipes/{stratovolcano,caldera,cinder_cones,impact_crater}.js`, `tests/volcanoes_craters/*` | `solvers/volcanic.py`, `solvers/impact.py`, the four recipes | - | P2 (shapes), then P5, P6 (aging) | profiles against numpy (Fuji's slopes at 0, 10 and 15 km; Pike's and Wood's ratios); cone and vent plans equal; the lava walkers' visits equal to numpy's for the same height field; stage replay; field-class parity (`stratovolcano`'s floor: 0.34 %); the bands against Fuji, Crater Lake, SP Crater and Meteor Crater | moderate |
| P10 | **Layered rock and rivers** | `solvers/strata.js`, `solvers/rivers.js`, `kernels/{strata_threshold,strata_cell,strata_creep,strata_weather}.wgsl`, `kernels/strata/*`, `recipes/{canyon,incised_meanders,mesas_buttes,badlands}.js`, `tests/layered_rock/*` | `solvers/strata.py`, `solvers/rivers.py`, the four recipes | - | P6 | kernel fixtures; column tables equal; river courses equal (plan fixtures); stage replay; parity in class (`canyon`'s floor: 0.75 %); the bands against Toroweap, the Goosenecks, Monument Valley and the Badlands | heavy |
| P11 | **Karst and coast** | `solvers/karst.js`, `solvers/coast.js`, `kernels/{coast_fetch,coast_seed,coast_jfa}.wgsl`, `kernels/karst/*`, `recipes/{tower_karst,sea_cliffs}.js`, `tests/karst_coast/*` | `solvers/karst.py`, `solvers/coast.py`, the two recipes | - | P2, then P5, P6 | the karst plan equal (Poisson disc, Dijkstra course, towers) within 1e-12; kernel fixtures (the fetch's exact traversal, the jump flood); `evaluate` within 1e-5 of range; stage replay; parity in class; the bands against Guilin (with its photographs), the Seven Sisters and Moher | moderate |
| P12 | **Detail** | `solvers/hydraulic.js`, `solvers/detail.js`, `kernels/{pipes_flux,pipes_water,pipes_transport,pipes_thermal,breakup}.wgsl`, `kernels/detail/*`, `tests/detail/*` | `solvers/hydraulic.py`, `solvers/detail.py` | Ekigar's `src/nodes/phacelle.js` | P5 | kernel fixtures; water and sediment conserved; breakup at 40 km from the origin; on `real_place` Lauterbrunnen the hero levels add detail without moving the landform (main metrics within 1 %); eye views show rills, ribs and talus | heavy |
| P13 | **Glacial** | `solvers/glacial.js`, `kernels/{ice_flux,jump_flood,u_carve}.wgsl`, `kernels/glacial/*`, `recipes/alpine_valley.js`, `tests/glacial/*` | `solvers/glacial.py`, `recipes/alpine_valley.py` | - | P6 | kernel fixtures (the jump flood's candidates identical); the ice-flux balance closes; streams and centrelines equal to numpy's on stage dumps (the GPU sort against `lexsort`); stage replay; the U-shape fit; the bands against Lauterbrunnen and Yosemite | heavy |
| P14 | **Surfacing** (last wave) | `build/surfacing.js`, `build/palettes.js`, their TSL nodes, `tests/surfacing/*` | the design in `SURFACING_DESIGN.md` (not the old node group) | Ekigar's `texture_arrays.js`, `triplanar.js`, `noise.js`; the edition's texture cache and `loadImageTexture`; the shimmer measurement | `SURFACING_DESIGN.md` final, P4, P7 | as the design says, plus textured renders beside the photographs and beside the Blender textured renders | heavy |
| P15 | **Dressing and plant placement** (last wave) | `build/dressing.js`, `build/placement.js`, `tests/dressing/*` | `build/dressing.py`; the placement layer of `SURFACING_DESIGN.md` | `createFlora` (`vegetation_loader.js`), `makeSeedTree` (`seedthree_api.js`), `fetch_model.py --cache` rocks | `SURFACING_DESIGN.md` final, P4, P7, P14 | as the design says; placement deterministic per seed; instancing within the frame budget | moderate |
| P16 | **Integration** | `eidoverse/terrain.js`, `render_scene.mjs` (the comment), `robot_controller.js` (the proxy condition and its comment), `README.md`, `tools-guides/terrain-surfaces.md`, `tools-guides/vegetation.md`, `docs/TOOLS.md`, `AGENTS.md`, `eidoverse/examples/terrain/*`, `techniques_archive.md` (appended) | the old implementation's removal; Blender's integration package | every package | all | the whole gate (5.5) in one run; every recipe's sheet; review videos per recipe (an 8 s aerial orbit and a 6 s eye-level dolly, 960 x 540, H.264 High yuv420p, checked with ffprobe) through `python eido.py render`; the callers work: a scene with flora on `terrain.heightAt`, the robot walking on a `real_place` hero window, `snapToGround` on the new mesh | heavy |

### 8.3 The waves

1. **Wave 1, now:** P1 Runner and primitives, P2 Core inputs, P3 Parity and judge, P4 Mesh and API. P1 lands the
   runner first (it starts from the prototype) and P3 lands `tests/_where.mjs` and the fixture generator first (it
   starts from `make_twin_fixtures.py`); the others code against sections 3-5 meanwhile. P4 builds from Blender
   saves, so the mesh, `heightAt`, the collider and the views are on screen before any solver runs. P3 measures the
   chaos floor of every recipe, which sets every later package's parity class.
2. **Wave 2, when the runner and the fixtures are in:** P5 Hydrology and level runner and P6 Fluvial backbone (the
   critical path; P6 begins with its kernels' fixtures and stage replay, which need only P1-P3, and runs whole
   recipes once `run.js` is in), P7 Masks, P12 Detail (its kernels first, then `real_place` on `run.js`), and P9's
   analytic shapes as a slot frees.
3. **Wave 3, when `run.js` and the fluvial step are in:** P8 Wind and sand, P10 Layered rock, P11 Karst and coast,
   P13 Glacial, and P9's aging and flows.
4. **Wave 4, gated on `SURFACING_DESIGN.md` being final:** P14 Surfacing, P15 Dressing and placement.
5. **Wave 5:** P16 Integration. The old `makeTerrain` is removed only here, when the new one has its material, so no
   scene loses textured ground in between.

No more than four packages at once on this machine (the session-load rule); a wave's later packages start as earlier
ones finish.

---

## 9. Risks

1. **Chaos (measured).** A float difference anywhere changes a fluvial range's network (section 5.4); exact fields are
   unattainable for those recipes even between two Blender machines. Handled by the classes, stage replay (which
   tests each op from Blender's own inputs, where chaos has not had time to grow), and the judge over seeds.
2. **Float precision on the GPU.** f32 only, fused multiply-adds, the built-ins' errors (2.3), and Blender's numpy
   parts in float64. Handled by per-grade tolerances; plans in float64 JS; angles to tangents on the CPU; integer
   paths exact.
3. **Atomics and reductions.** No float atomics; order-dependent float sums would make runs differ. Handled: gathers
   as in Blender, integer atomics only on order-independent quantities, fixed-tree sums, exact selections.
4. **Deno WebGPU on this machine.** The storage-buffer limit (default 8, two kernels need 9: request it; fail loudly
   below); about 16 ms per GPU-to-CPU sync and about 3 ms per MB (no waits inside steps; reductions, not fields);
   0.72-0.80 ms per dispatch if each is submitted alone (batching); no subgroups (shared-memory reductions); only Deno
   2.8.1 is installed here, and `eido.py` also accepts 2.9.5, whose wgpu may compile WGSL differently: the parity
   suite runs on both where both exist.
5. **Memory at 2048² x 7 levels.** Measured: 3.19 GiB of buffers allocate fine, but host memory reached 7.5-7.8 GB
   through staging. Handled by section 4.9: one working level on the GPU, finished fields read back, reused staging
   and readback buffers, float16 bounded masks, memory caps on every job.
6. **numpy's Generator.** The plans need numpy's exact streams. The core is measured bit-exact; the distributions
   that remain (`standard_normal` and `exponential` with numpy's ziggurat tables, `poisson`, `choice`) are
   mechanical but exact work. numpy does not promise Generator streams across versions for every distribution, so the
   plan fixtures record the numpy version Blender's Python carries, and the port follows it.
7. **A moving source of truth.** The Blender edition is being finished, and its surfacing redesigned, while the port
   is built. Handled by section 5.6: per-file commit headers, `sync_status.mjs`, fixtures keyed by commit and code
   hash.
8. **Algorithms that are sequential in Blender.** Priority flood, BFS, union-find, stream graphs, Dijkstra, walkers.
   Handled by section 2.4 and 3.4: exact GPU formulations where they exist (min-max fill, label propagation, BFS
   relaxation, pointer jumping, radix sort) with numpy as the oracle; JS for plan grids and walkers whose discrete
   outcomes must match numpy.
9. **TSL compute's hidden scheduling.** Not on the generator's path (raw WGSL), but the materials are TSL: the last
   wave keeps the edition's material laws (texture arrays to stay under 16 sampled textures a stage,
   `float32-filterable` for RGBA32F, which this device has) and checks every probe frame.
10. **Heightfield limits.** Overhangs and sheer walls are as limited as in Blender (DESIGN.md risks 4-5); the port does
    not try to do better than the source.
11. **Scene-side costs of a large mesh.** Rapier's trimesh and three's ray casts over millions of triangles: handled
    by the collider proxy and the height-grid ray caster (7.5); bounding volumes set from the GPU.
12. **Other devices.** The edition supports software adapters and WSL's Mesa D3D12. The runner never renders to
    RGBA32F (the Mesa downgrade in `render_common.mjs` does not touch it), fails loudly on missing limits, and warns
    on software adapters; the parity suite records the adapter with every dump.

---

## Appendix: the design probes

`eidoverse/terrain/tests/design_probes/`:

| file | what it is |
|---|---|
| `gpu_device.mjs` | the adapter, features and limits (1.2) |
| `gpu_runner_bench.mjs` | the probe kernel in raw WGSL: buffers and textures, timestamps, wall time, readback, upload, one submit per dispatch, the 7-level allocation (4.5, 4.8, 4.9) |
| `tsl_compute_bench.mjs` | the probe kernel in TSL through `renderer.compute()` (4.1, 4.8) |
| `tsl_vs_wgsl_fresh.mjs` | TSL against WGSL in a fresh process; first calls (4.1) |
| `mini_runner.mjs`, `wgsl/` | the runner prototype and the transcribed kernels (`common`, `flow_weights`, `route_incise`, `creep`, `threshold_excess`, `threshold`, `creep_layers`, `h_keep`, `world_noise_field`, plus `hash_probe` and `math_probe`) |
| `make_twin_fixtures.py`, `kernel_parity.mjs` | the Blender twins' fixtures and the cross-edition check: 46 kernel cases, hashes, world noise, built-in ulps, the fluvial step (4.6, 4.8, 5.3) |
| `np_random_expected.py`, `np_random_probe.mjs` | numpy's Generator in JS (2.3, risk 6) |
| `blender_chaos_floor.py` | the Blender edition's chaos floor (5.4) |
| `results.json` | every number above, with notes on the noisy measurements |

To re-run: `python eidoverse/terrain/tests/design_probes/make_twin_fixtures.py <dir>` (it finds the Blender edition
beside `eidoverse/` or at `$EIDO_BLENDER_EDITION`), then each `.mjs` with `deno run --no-config --no-lock
--unstable-webgpu --allow-all <probe> [args]`, and `bash run_blender.sh
eidoverse/terrain/tests/design_probes/blender_chaos_floor.py <out.json> [recipe ...]` from a Blender checkout; on a
shared machine, each behind `$EIDO_GPU_WRAP`.
