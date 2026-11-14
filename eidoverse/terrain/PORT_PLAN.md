# Porting the new make_terrain to the three.js edition: the plan

Three.js / Deno / WebGPU edition (branch `threejs-terrain`, from `main`), 2026-11-13, revised 2026-11-14 after an
independent review. The contract the port's agents build from, and the lead's checklist. The source of truth is the
Blender edition's terrain family on the `blender` branch: `blender/eidoblend/terrain/` at commit `f90c6fc`
("Terrain: the review's fix round ...", unchanged through `a3a72b9`), its design `blender/tests/terrain/DESIGN.md`,
the surfacing design `blender/tests/terrain/SURFACING_DESIGN.md` (final, `a3a72b9`; its code is landing), and the
tests and judge in `blender/tests/terrain/`. Every number below that is not quoted from those files was measured for
this plan by the probes in `tests/design_probes/` (section 1.2; numbers in `tests/design_probes/results.json` and, for
the revision, `results_revision.json`), or by the review's probes, which are named where they are used.

---

## Changes since the first version

For the builders of wave 1: each change, where it is, and whom it touches. Everything else stands.

| # | change | sections | packages |
|---|---|---|---|
| C1 | **The chaos floor is re-measured.** Every op (not only `FluvialRun`) is perturbed by one ulp at two points: its level's float fields at its entry, and each kernel's outputs after its first dispatch in the op call; the solvers' per-process memos are cleared before every sample; at least five patterns per recipe and seed; the field-class tolerance is 1.25 x the largest sample, never below the kernel grade; channel overlap passes at or above the smallest sample minus the samples' spread; the judge's numbers are compared within that tolerance, not its verdicts; the class boundary comes from the measured spread. `design_probes/blender_floor_patterns.py` is the reference hook. **P3: run the 16-recipe floor with this protocol, not the first one.** The floor runs are also the dump runs (C2) | 5.3, 5.4, 5.5 | P3; every recipe package's parity |
| C2 | **Dispatch-log parity and step snapshots.** Every Blender dump is made with a log of every `core/gpu.run` (op, kernel, uniforms, bound images) and every readback, and with the bound images read back after each kernel's 1st, 10th, 100th, 1,000th and 10,000th dispatch. `core/gpu.js` logs the same through one hook. The control code (step counts, dt, factors, pass order, pins) is then checked directly, and every evolving op is checked before chaos grows | 5.1, 5.2, 5.7 | P1 (the hook in `core/gpu.js`), P3 (the Blender side), every solver package (acceptance) |
| C3 | **The mesh's acceptance is restated for float32.** x and z (three.js) bit-equal: the lattice lines in JS doubles, `Math.fround` once, gathered by the kernel (measured: 20,485 of 20,485 equal). Heights in plain f32 within 14 ulp of the corner's largest tap (the analytic bound of any f32 evaluation of the stencil; measured worst 3 over 3.15 M corners on three cliff fields). Not "4 ulp of \|z\|": that fails where z crosses 0 beside a cliff (measured: 567 corners, up to 43,780 ulp of \|z\|). Not double-float: this machine's shader compiler does not keep two-sums (measured: 45-48 % of corners differ, worse than plain f32). `heightAt` within the same bound. Normals as Blender's (corner-angle-weighted unit face normals, skirt excluded) by a gather, no atomics. Cracks by an edge-manifold check, grazing renders along every seam and the port of `test_seam_crease.py` | 7.3, 7.4, 8.2 | P4 |
| C4 | **The surfacing design is final, so wave 1 reserves its interfaces.** `makeTerrain({ surface, plants })`, `t.surface`, `t.plants`; `Terrain.save` / `load` carry `<base>.plants.json` and `<base>.plants.<species>.f32` (and `load` reads Blender's, as a parity input). The mesh carries a material group per ring (context rings take the far material, index 1) and **no mask attributes**. The cache counts and prunes the bake's `surface_*` files with their entry. Wave 4 is re-planned module for module from the design: four packages (P14, P15, P17, P18), each starting when its Blender counterpart commits | 3.5, 7.1-7.3, 8.2, 8.3 | P2 (`cache.js`), P4 (API, mesh, save/load) |
| C5 | **Dependencies come from the recipes' stages** (the table in 8.4). `breakup` and `hydraulic` (P12) are stages of 10 of the 16 recipes, so P12 joins the critical path in wave 2, and whole-recipe acceptance waits for every op of the recipe. P3's views and its judge runs on port saves wait for P4's mesh and `Terrain.save`; P1's tests move to P3's `tests/_where.mjs` when it lands | 8.2, 8.3, 8.4 | P1, P3, P4, P6, P9-P13 |
| C6 | **Percentiles follow numpy 2.3.4 per call form**, as P1's `prims.js` already does; `quantile` is added (2 call sites, with its own rule). Every fixture is made by the Blender edition's own Python (3.13, numpy 2.3.4, zlib 1.3.1), never the system Python (numpy 2.5.2, zlib-ng), and records the versions | 2.3, 3.4, 5.1 | P1, P3 |
| C7 | **Kernels compile through `GPUDevice.prototype.createShaderModule.call(device, desc)`**, so `render_common.mjs`'s three.js rewrite of `u32(0)` never touches the terrain's WGSL; the self-test and fixtures also run on a `render_common` device | 4.2, 4.7 | P1 |
| C8 | **The cache keys mirror Blender's split:** a field hash over `core/*.js`, the solver kernels, `solvers/*.js` and `run.js`; the terrain hash adds `recipes/*.js`, `masks.js` and `kernels/masks/`; `build/`, `api.js`, `surface/` and the mesh, water and metrics kernels never enter. `prune({ keepGb: 20 })` and `clear()` ported | 3.2 | P2 |
| C9 | **PNG16 is compared by its pixels and filtered rows, not its compressed bytes** (measured: Blender's Python runs zlib 1.3.1, and Deno's `CompressionStream` equals neither it nor the system Python's zlib-ng in general); written through `CompressionStream('deflate')` with Blender's Up filter made on the GPU; read through `DecompressionStream` (it decodes Blender's bytes exactly), the Up filter undone on the GPU. Ekigar's `png_read.js` cannot read Blender's PNGs (stored blocks only). npz gets its own zip64-aware streaming reader and writer in `io.js` (numpy always writes zip64; Ekigar's `zip.js` refuses it) | 3.2, 10.1 | P2 |
| C10 | **Python's `round()` is half-to-even:** one `pyRound` in `core/levels.js`, used at every `round()` of `levels.py`, `mesh.py` and `api.py`; `round_half_up` only where Blender has it (`world_noise.py`, the quantisation in `io.py`) | 2.3, 3.2 | P2, P4 |
| C11 | **`_descend` (the routing surface) runs in the path-maximum form** (1 ulp from Blender's float64, measured by the review) instead of a float32 relaxation (up to 82 ulp, 5 mm) | 3.2 | P5 |

Where I disagree with the review, or a decision is the lead's, it is in section 10.

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
   output; a recipe against the Blender recipe's saved fields; and what a solver asks of the GPU against the Blender
   run's dispatch log. There are no JS twins: a JS twin would be a third implementation of each kernel, and the numpy
   twins already measure exactly what parity needs. (The material's maths in the last wave has a plain-number
   instantiation, but it is the shader's own source instantiated twice, not another implementation, 3.5.)
5. **Parity is graded, and every grade has a measured tolerance** (section 5): bit-exact for integers, hashes and the
   numpy draws; within 1e-4 of a field's range for one dispatch (measured worst 3.06e-5, the same as the GLSL
   kernels' own worst against the same twins); the control code by the dispatch log (every kernel, every uniform,
   every readback, in order); every evolving op after 1, 10, 100, 1,000 and 10,000 dispatches, before chaos grows;
   stage replay from Blender's inputs; and for whole recipes, the Blender edition's own chaos floor, sampled over
   several perturbations of every op. One ulp moves the main level of `stratovolcano` by 0.33-0.51 % (RMS of
   relief) depending on the pattern alone (five samples), `canyon` by 0.75 % (one sample), and `fluvial_range` by
   12.6 %, whose drainage network is then a different one (channel overlap 0.10). So "the same recipe and seed give
   the same landform" is a field-by-field test for the recipes with a low floor and a test over seeds for the chaotic
   ones, and for both the dispatch log proves the same computation was asked for.
6. **Shared data is read where it lives,** in a checkout of the `blender` branch (or this checkout, once the branches
   merge): the reference DEMs, the photographs, the view cameras, the bands and the judge itself. The port writes
   its terrain in the Blender `Terrain.save` format and runs the one Python judge on it. Nothing is copied into git.
7. **`makeTerrain` keeps its name, becomes async, and returns a `Terrain`** with `.mesh` and `.heightAt` (so the old
   `const { mesh, heightAt } = ...` still works) plus every Blender member, `surface` and `plants` included. The ring
   mesh is built by GPU kernels and read back once, its x and z bit-equal to Blender's (the lattice lines in JS
   doubles) and its heights within the float32 bound of the stencil: `heightAt` is exact on the rendered triangles, a
   collider proxy keeps Rapier's trimesh small, and the mesh's ray caster walks the height grid instead of millions of
   triangles. The mesh carries no mask attributes: the material reads per-level data textures.
8. **Surfacing and plant placement are the last wave,** ported module for module from
   `blender/tests/terrain/SURFACING_DESIGN.md` (final at `a3a72b9`) and the code its five Blender packages are landing
   now: the surface data bake as WGSL kernels, per-level 2D-array data textures, a TSL NodeMaterial whose maths is
   written once (Ekigar's `ops` backend) for both the shader and the far-colour bake, and the plant planner on the GPU
   (section 3.5). Wave 1 already reserves its interfaces (C4).
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
  `out/core/gpu_bench.json`). The portability pass of the tests (`EIDO_GPU_WRAP`, `blender/tests/_where.py`) is
  committed since (`72c9b41`). For the revision: `SURFACING_DESIGN.md` (1,045 lines, `a3a72b9`) and the code its
  packages are landing, uncommitted as I write: `surface/` (`__init__`, `maps`, `bake`, `atlas`, `palette_bake`,
  `far_colour`, `expr_glsl`, `noise.glsl` and its twin `noise.py`, `twins`, eleven kernels), `build/plants.py`,
  `ecotopes.py`, `plant_instances.py`, and edits to `dressing.py` and `palettes.py`.
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
| `blender_chaos_floor.py` | the Blender edition against itself: each recipe twice (determinism), then with every erosion run's start moved by one float32 ulp | reruns bit-identical; the floor per recipe in section 5.4 (one pattern: superseded by the next row) |
| `blender_floor_patterns.py` (revision) | the revised floor: every op perturbed by one ulp at its entry and after each kernel's first dispatch in the op call, the solvers' memos cleared, several patterns; the dispatch log; each kernel's images after its 1st-10,000th dispatch | section 5.4 and 5.7 |
| `mesh_f32_prep.py` + `mesh_f32_device.mjs` (revision) | the ring mesh's corner heights in float32 and in double-float against Blender's float64-then-float32 on three cliff fields; lattice lines in JS doubles; compiling through `GPUDevice.prototype.createShaderModule`; the adapter's texture and vertex limits | sections 4.7 and 7.3 |
| the review's probes (outside the repository; their numbers are cited where used) | the floor's sensitivity to the pattern (five perturbations of `stratovolcano`); the mesh's float32 corners on `alpine_valley`; `render_common`'s `u32(0)` rewrite; numpy 2.3.4's percentile arithmetic; zlib and `CompressionStream` | sections 2.3, 4.2, 5.4, 7.3, 10 |

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
- **Exact selection, not approximate quantiles.** `np.percentile`, `np.quantile` and `np.median` (the relief
  controller, the mask norms, the judge's metrics: 24, 2 and 16 call sites in the package) are reproduced by a GPU
  radix select of the exact order statistics on monotonic keys, then numpy 2.3.4's own arithmetic for that call
  form, on the CPU: for float32 data a Python-number q runs the virtual index, gamma and lerp in float32 (percentile
  divides q by `float32(100)`; quantile casts a Python or numpy float q to the data's dtype), a list of q runs them in
  float64 with the difference b - a in float32, float64 data is float64 throughout, and the median of float32 data is
  the float32 mean of the middle pair. The review measured the plain float64 rule against numpy 2.3.4: wrong in 1,154
  of 7,800 scalar-q cases, and at 2048² the float32 index can pick another order statistic. P1's `prims.js` follows
  numpy per call form already; every call site passes its form.
- **Python's rounding.** `round()` in Python is half-to-even. `core/levels.js` has one `pyRound` (half-to-even on
  doubles), used wherever the Blender code calls `round()`: `levels.py` (the parent offsets and sizes, the centred
  child `off = 2 * round(n / 8)`, the window size), `mesh.py` (`stride = round(n / mesh_res)`, the window snapping),
  `api.py` (the flatten windows, `_scaled_resolution`). `Math.round` (half up) differs on halves: n = 1280 at
  `meshRes` 512 is stride 2 in Python and 3 with `Math.round`. `round_half_up` is used only where Blender has it
  (`world_noise.py`'s wavelength snapping, `io.py`'s quantisation).
- **No error-free transformations on this GPU.** Two-sums and two-products (double-float arithmetic, Kahan
  summation) do not survive this machine's shader compiler: a double-float Catmull-Rom, with fused products or with
  products made exact by two-sums alone, differed from Blender's float64-then-float32 on 45-48 % of the corners, more
  than plain f32 (36-40 %) (`mesh_f32_device.mjs`). So where numpy computes in float64 and rounds once to float32,
  the port computes in f32 and is graded by the error bound of its arithmetic, measured relative to the largest input
  (section 7.3), never relative to the output, which can be near zero beside large inputs. Fixed-tree sums stay
  deterministic run to run (the order is fixed); they are not more accurate.
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
6. **File input and output:** zlib (`CompressionStream` and `DecompressionStream`) in PNG, the zip framing of npz,
   JSON. The per-texel parts of a PNG (the 16-bit quantisation, the byte order, the Up filter and its inverse) run on
   the GPU.

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
    surfacing.js  palettes.js  ops.js  plants.js  ecotopes.js  plant_instances.js  dressing.js   (the last wave, 3.5)
  surface/                 the surface data bake (the last wave, 3.5): index.js maps.js bake.js layers.js
                           palette_bake.js far_colour.js mask_expr.js noise.js, kernels/*.wgsl
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
| `core/levels.py` | `core/levels.js` | JS (no per-cell work): `plan_levels`, `select_levels`, `check_plan`, `QUALITY`, with Python's rounding: `pyRound` (half-to-even) at every `round()`, `math.ceil` and `math.floor` with the same epsilons (2.3); `pyRound` is exported for `build/mesh.js` and `api.js` |
| `core/fields.py` | `core/fields.js` | a level's named GPU buffers, CPU mirrors after readback; `inherit` through `kernels/grid/` |
| `core/recipe.py` | `core/recipe.js` | JS: Stage, Knob, Params, Recipe, the op registry; `toDict()` JSON-equal to Python's |
| `core/expr.py` | `core/expr.js` | the parser in JS; evaluation compiles an expression into a WGSL kernel over named buffers (cached by its text) |
| `core/world_noise.py` | `core/world_noise.js` + `kernels/world_noise_field.wgsl`, `kernels/noise.wgsl` | term tables (`_leaf_terms`, `lattice_offset`, `snap_wavelength`) in JS float64; evaluation on the GPU (already so in Blender, `field_gpu`); numpy's `field()` is the oracle, not ported |
| `core/compose.py` | `core/compose.js` + `kernels/compose/` | GPU: `shape` (cone, bowl, profile, array, dome, ridge, plateau, massif, field), `stamp` modes, `uplift`, `start_surface`, `flatten_mask`, `flatten_exact`; JS: the spur plan (numpy RNG), `resolve_flat_heights`' medians from an exact select |
| `core/cache.py` | `core/cache.js` | keys over the recipe, knobs, size, resolution, seed, plan, focus and two code hashes, split as Blender splits them (`core/cache.CODE_GLOBS`, `api._code_hash`): the **field hash** over `core/*.js`, `kernels/*.wgsl`, the solver kernels (`kernels/{prims,grid,compose,hydro,volcanic,impact,strata,karst,glacial,detail}/*.wgsl`), `solvers/*.js` and `run.js`; the **terrain hash** adds `recipes/*.js`, `masks.js` and `kernels/masks/*.wgsl`. `build/`, `api.js`, `index.js`, `bake.mjs`, `surface/` and `kernels/{mesh,water,metrics}/` never enter, so a mesh, API or material edit regenerates nothing. Entries under `eidoverse/assets/cache/terrain_threejs/<key>/` (that folder is already ignored; kept apart from Blender's `terrain/` so neither prunes the other); `prune({ keepGb: 20 })` drops least recently used entries as `cache.prune(keep_gb=20)` does, and `clear()`. An entry's size counts every file in it, so the surface bake's `surface_<key>_L<i>.npz` (and `_pal<hash>_`) files and the plant spots, which sit at the entry's top level (SURFACING_DESIGN.md 2.7, 4.5), are counted, pruned and cleared with it |
| `core/io.py` | `core/io.js` | npz read and write (uncompressed `np.savez`, float16 masks included) through its own zip reader and writer: stored entries, zip64 always (numpy's `savez` opens every entry with `force_zip64=True`), streamed per entry so a hero save over 4 GB never sits in one buffer; Ekigar's `materials/zip.js` refuses zip64 and caps an entry at 256 MB, so it is not used here. PNG16 / R32 with the `eidoverse-terrain-heightmap/1` sidecar: the 16-bit quantisation (half-up, as `_round_half_up`), the big-endian rows and Blender's Up filter run on the GPU and are read back once; the deflate is `CompressionStream('deflate')`. Reading: `DecompressionStream('deflate')` (it decodes Blender's zlib 1.3.1 bytes exactly, measured), then the Up filter undone on the GPU (one thread per byte column). Every reference PNG uses the Up filter only (checked: 44 of 44 in `reference/data`, as `encode_png` writes); another filter type raises, naming it. Ekigar's `png_read.js` is not usable as it is: it inflates stored blocks only and throws on Huffman-coded deflate, which every Blender PNG is; its chunk parsing is reused (MIT, notice kept). R32 is raw float32 |
| `core/metrics.py` | `core/metrics.js` + `kernels/metrics/` | GPU: slope percentiles (exact select), fractions, relief, hypsometric integral, anisotropy harmonics, cliff pairs, depressions (fill and label), the radial spectrum (a GPU FFT, then the 48-bin fit in JS) for `t.metrics()`; the Python judge stays the authority |
| `solvers/fluvial.py` (1,628) | `solvers/fluvial.js` | already GPU: the step. GPU: erodibility, threshold and fault inputs, composite uplift and start, `Sc` from the gradient, rigid masks, the lock's block means (fixed-tree sums), `d8_receivers`, `op_valley_floor`'s channel fills, `op_incise`'s carving; JS: the relief controller's arithmetic, step counts, the lock's phase schedule |
| `solvers/hillslope.py` (627) | `solvers/hillslope.js` | already GPU: creep, threshold, `soil_jacobi`. GPU: `gaussian_blur` (linear creep as a Gaussian, reflect padding of 4 sigma), the soil solve's pyramid, `_downstream` |
| `solvers/hydro.py` (776) | `solvers/hydro.js` + `kernels/hydro/` | already GPU: `route_area`. GPU: `fill_depressions` (a min-max relaxation, exact: min and max only), `flat_distance` (integer relaxation), `flow_receivers`, `path_steps` (pointer jumping), `_descend` in the path-maximum form rs = s eps + max over the path to the outlet of (f - s eps), by pointer jumping (the review measured it 1 ulp from Blender's float64 on `alpine_valley`'s main level, 0 cells over 1 mm, where a float32 relaxation along the receivers differs by up to 82 ulp, 5 mm, on 19,130 cells), `lakes` (labels, per-label maximum by `atomicMax`), `_parent_lake_water`, `inflow`, the convergence check (a reduction) |
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
| `build/mesh.py` (725) | `build/mesh.js` + `kernels/mesh/` | section 7.3: topology, positions (lattice lines in JS doubles), f32 heights and angle-weighted normals by kernels, read back once; one geometry group per ring (material 0 near, 1 far: the context rings), no mask attributes; `heightAt` / `normalAt` in JS per query |
| `build/water.py` (166) | `build/water.js` + `kernels/water/` | lake quads by stream compaction of lake cells, the sea grid, a dark glossy NodeMaterial tinted by the `water` mask |
| `build/dressing.py`, `surfacing.py`, `palettes.py`, `plants.py`, `ecotopes.py`, `plant_instances.py`, `surface/*` | section 3.5 | the last wave, module for module from `SURFACING_DESIGN.md` |
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
| radix select on monotonic float keys, then numpy 2.3.4's interpolation for the call form (2.3): `percentile(f, q)` with q a number or a list, `quantile(f, q)`, `median(f)`, each with the data's dtype | every `np.percentile`, `np.quantile` and `np.median` | bit-equal to numpy 2.3.4, per call form |
| histogram, prefix scan, stream compaction | lake quads, channel subsets, masks' norms | exact |
| key-value radix sort, segmented first, pointer jumping (list ranking, path maxima) | glacial streams, `path_steps`, receiver trees | exact (integer keys, numpy's tie order) |
| connected components (label propagation with pointer jumping, `atomicMin` hooks) | lakes, basins, coast cuts, cockpits | exact (minimum labels) |
| min-max relaxation (priority-flood fill) | `fill_depressions` and everything built on it | exact: the fixed point of `W = max(h, min_k W_k)` with the outlets held is the priority flood's spill surface, computed with min and max only |
| breadth-first relaxation, receiver trees | `flat_distance`, `flow_receivers` | exact |
| separable Gaussian with Blender's padding and decimation; box blur; dilation | masks, creep aging, aeolian smoothing | f32 against numpy float64 |
| jump flooding | glacial seeds, coast distances (already Blender kernels) | as the Blender kernels |
| radix-2 FFT | the spectrum metric, periodic Gaussians where a direct convolution is too wide | f32 |

### 3.5 The surface and the plants (the last wave), module for module

From `SURFACING_DESIGN.md` (final, `a3a72b9`) and the code its five Blender packages are landing. Each port file is
ported from its Blender file at the commit that file lands in (the header rule of 5.6); the design is the contract
until then. Wave 1 already reserves what these need from it (C4): the `surface` and `plants` options and members,
the spots files in save and load, one geometry group per ring, no mask attributes, the bake's files in the cache.

| Blender | port | GPU, and what stays JS |
|---|---|---|
| `surface/__init__.py` (`bake_surface`, `SurfaceData`, `MAPS`) | `surface/index.js` | JS: `bakeSurface(t, { palette, options, cache, extra })`, `SurfaceData` (`levels`, `layouts`, `maps(level)`, `at(name, x, z)`, `channel(name)`, `textures()`, `save(folder)`), as design 5.3 |
| `surface/maps.py` | `surface/maps.js` | data: the registry (name, unit, family, channel, encoding, maker), JSON-equal |
| `surface/bake.py` | `surface/bake.js` | GPU, coarsest level first: the inputs, the kernels, the pins (`masks.pin_band`'s ramp over the outer 16 cells, directions as vectors), the gutters from the parent, the encoding per family in the kernel (`pack4x8unorm`, `pack2x16float`, the square-root thickness code), one readback per level into the cache's float16 npz. JS: the level loop, the convergence test of the hero routing (step 8), cache keys |
| `surface/kernels/*.glsl` (`blur`, `carry_src`, `cavity`, `crest`, `field_normal`, `fill`, `phacelle`, `pin_inflow`, `route_colour`, `streak`, `upsample2`, and the design's `spi_valley` and `pin_gutter` as they land; the per-palette kernel `far_colour.py` generates becomes the TSL pass two rows down) | `surface/kernels/*.wgsl` | transcribed with the same names and `//!` headers, through `core/gpu.js`; the bake reuses `flow_weights` and `route_area` and the detail op's `pipes_thermal` (`relax`) and `breakup` (`strength`) read-only, as Blender's does. Outside `kernels/`, so no bake edit changes the field hash (C8) |
| `surface/atlas.py` | `surface/layers.js` | per family one `THREE.DataArrayTexture`, one layer per level, uploaded from the bake's packed bytes: D and F RGBA16F, E and M RGBA8, C and P RGBA8 sRGB, the LUT a plain 256 x rows RGBA8 texture. A layer is the family's largest tile (n + 2g texels square); a smaller level uses its sub-rectangle, with its own UV rectangle in the reader's constants. Not tall atlases: a film D atlas is 2,176 x about 12,000 texels (15,200 at hero), over a default device's 8,192 `maxTextureDimension2D` (measured, 4.7); arrays fit every default limit. Memory: D about 353 MB at film (seven 2,176² layers with mips) against the atlas's 277 MB; P17 may split D into a fine and a coarse array if VRAM asks |
| `surface/palette_bake.py`, `surface/far_colour.py` | `surface/palette_bake.js`, `surface/far_colour.js` | C, the far colour: one pass per level evaluating the palette's layer stack per texel with the material's own maths (the next rows), as a render-to-texture pass through the edition's renderer: a full-screen quad, float targets, one readback (the pattern of Ekigar's `export/surround_bake_gpu.js`). P, the provenance colour: `route_colour.wgsl` through `core/gpu.js` to convergence |
| `surface/expr_glsl.py` | `surface/mask_expr.js` | the mask language (`palettes.py`'s parse trees) compiled once into calls on an arithmetic backend, Ekigar's `export/ops.js` (MIT; copied to `build/ops.js` with its notice, extended with u32 operations): its TSL instantiation is the material's and the C bake's, its plain-number instantiation the JS test oracle. Cross-edition oracles: `palettes.evaluate` and `expr_glsl`'s output on the same maps |
| `surface/noise.glsl` (`noise.py` its twin) | `surface/noise.js` | Blender's shader noise (the Noise Texture's fBM in 3D and 4D, the Voronoi F1 colour; Jenkins' lookup3 hashes, Cycles' Perlin), written once against `ops`, so the material and the C bake share it; u32 hashes bit-exact (TSL's `uint` and bit operations; in the oracle, `Math.imul` and `>>>`). GPL-2.0-or-later (Blender) and Apache-2.0 (Cycles), both compatible with this AGPL-3.0 repository; notices kept |
| `surface/twins.py` | none | the oracle stays in Python: fixtures under Blender's Python (5.1) |
| `build/surfacing.py` | `build/surfacing.js` | a TSL NodeMaterial (never a WebGL material): the reader (the level by telescoping sums over the nested windows, one read per data array with `.depth(level)`, design 2.4), N_field from D, N_macro with the sub-cell relief and the grazing guard (2.5), hex tiling of planar reads (3.3), eight aspect sectors on steep faces (3.4), the footprint fade (3.2), the far material and the 64-cell cross-fade (3.7). Its maths is ported from Blender's `surface_group` and written against `ops`, as Ekigar's `export/layer_kernel.js` writes its stack, so the C bake evaluates the same expressions; `layer_kernel.js`'s functions are reused only where they compute what Blender's do. Reused as they are: Ekigar's `materials/texture_arrays.js` (the scans as two arrays, albedo-height and normal-roughness-AO, for every layer), the edition's texture cache and `loadImageTexture`. Sampled textures: 2 scan arrays + the strata column 1-2 + D, E, C, P, LUT + M + F = 10-12, under the default 16 |
| `build/mesh.py` (`material_index` per ring) | `build/mesh.js` | P4, now: one geometry group per ring (7.3) |
| `build/palettes.py` | `build/palettes.js` | data, ported as Blender's surfacing round leaves it (the port does not tune looks; a look that differs is a material or bake defect, fixed there): the palettes, the looks, `RECIPE_LOOKS`, ramps; `known_mask`, `ramp_rows` (the LUT's rows), the mask language's parser, which `mask_expr.js` compiles. P14's, since the palette bake (C, P) reads it |
| `build/plants.py` | `build/plants.js` + `kernels/plants/` | GPU, per species in priority order: candidates per world cell (splitmix64's finaliser over the key chain, emulated as u32 pairs, bit-exact; the 53-bit uniform kept as its integer), the Poisson counts by inversion, the density from the compiled expression on the data textures, the hard core as the greedy maximal independent set in mark order (rounds in which every candidate whose lower-mark rivals within reach are all decided is decided; the fixed point is the sequential inhibition's result exactly, in any order of evaluation), the margin test of `PAD_CORES`, ages, sizes, yaw, tint, ground normals by `heightAt`'s triangle rule on the GPU. JS: the species loop, the view selection's control, the spots files. The parity grade is the lead's call (section 10) |
| `build/ecotopes.py` | `build/ecotopes.js` | data: species tables per palette, recipe and place, `ecotope_hash`, JSON-equal |
| `build/plant_instances.py` | `build/plant_instances.js` | three.js: per species, individual and LOD one `InstancedMesh`, its matrices made by a kernel from the spots; SeedThree individuals grown once through `makeSeedTree` (`seedthree_api.js`) with its LOD ladder and billboards, flora through `createFlora` (`vegetation_loader.js`); the per-frame LOD choice over up to 3 x 10^5 instances is a compute pass (the edition's rule), not a loop |
| `build/dressing.py` | `build/dressing.js` | GPU: rock placement (a hash per candidate, mask densities, power-law sizes) and the toe bias; `InstancedMesh` of cached CC0 rocks (`fetch_model.py --cache`) |

The Blender design's five packages become four port packages and the integration (8.2): P14 surface data (Blender's
package 1), P15 plants and dressing (4), P17 material (2), P18 look (3), and P16 integration takes package 5's wiring,
its judge's measures (numpy and Pillow, run on the port's renders: one judge again), the guide and the videos.

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
- **Modules compile through `GPUDevice.prototype.createShaderModule.call(device, desc)`,** never
  `device.createShaderModule`. On the scene's device `render_common.mjs` replaces the instance's method with a
  wrapper that rewrites every `u32(0)`, `u32(0u)` and `u32(0.0)` to a bare `0` (a fix for three.js's TSL on Mesa's
  D3D12). On a terrain kernel that declares `var c = u32(0);` that makes an i32 counter, and the module fails only in
  a scene: the review compiled such a kernel unpatched and patched, and the patched one failed with "automatic
  conversions cannot convert elements of `i32` to `u32`". The prototype's method skips the instance wrapper (measured,
  section 4.7), so the terrain's WGSL compiles the same on every device. The runner's refusal of the pattern
  (`U32_ZERO` in P1's `gpu.js`) can go, or stay as a warning.
- **The dispatch hook.** `gpu.onDispatch(fn)` calls fn after every recorded dispatch with `{ op, kernel, blender,
  uniforms, images, samplers, count }` (`op` from `gpu.context.op`, which `run.js` sets as each op starts; `blender`
  true for a kernel transcribed from Blender; `count` that kernel's dispatches so far), and `gpu.onReadback(fn)`
  after every readback with `{ afterDispatch, op, name, shape, data }`: the port's half of the dispatch log and the
  step snapshots (5.7). A snapshot reads the bound images back at the counts it wants, after the batch is submitted.
  Off, it costs one branch per dispatch.

### 4.3 Fields

- **Storage buffers, not textures.** One `array<f32>`, `array<vec2<f32>>` or `array<vec4<f32>>` per field or pack,
  row-major `[row j][column i]`, row 0 south: the layout of the Blender textures, with the same RGBA packs (`st` =
  h, A, qs, carried; `mk` = wear, deposit, talus, loose; `par` = U, K, Sc, G; `pin` = pin_w, pin_h, A_in, qs_in).
  Measured on the probe kernel: buffers 0.026 ms against 0.035-0.038 ms for sampled-plus-storage textures at 1024²,
  equal at 2048², bit-identical results. Buffers have no format limits, are read-write, and take atomics.
- **Ping-pong** by binding: a `Pair` of buffers and a bind group cached per (kernel, buffers), so a pair costs two
  bind groups for the whole run.
- **Textures only where rendering wants them:** the surface data of the last wave, one 2D-array texture per family
  (3.5), uploaded from the bake's packed bytes (the level's one readback, which the cache also stores), so no
  per-texel work runs on the CPU and nothing reaches into three.js's backend.

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
- **The adapter against a default device** (measured, `mesh_f32_device.mjs`; the first version's
  `maxTextureDimension2D` 8192 was the device's default, not the adapter's):

  | limit | adapter | default device |
  |---|---|---|
  | `maxTextureDimension2D` | 32,768 | 8,192 |
  | `maxTextureArrayLayers` | 2,048 | 256 |
  | `maxSampledTexturesPerShaderStage`, `maxSamplersPerShaderStage` | 1,048,576 | 16 |
  | `maxStorageTexturesPerShaderStage` | 1,048,576 | 4 |
  | `maxStorageBuffersPerShaderStage` | 1,048,576 | 8 |
  | `maxVertexBuffers`, `maxVertexAttributes` | 16, 32 | 8, 16 |
  | `maxBindGroups` | 8 | 4 |
  | `maxComputeWorkgroupStorageSize` | 49,152 | 16,384 |

  The generator needs only the two limits P1 already requests. The surfacing wave stays inside the defaults (2D-array
  data textures of at most 2,176² a layer and 7-9 layers; at most 16 sampled textures in the material, 3.5), so it
  works on any WebGPU device and needs no new limit.
- **Self-test** at initialisation: one dispatch whose readback must be exact (`gpu_check.mjs`'s and `gpu.py`'s
  `_self_test`), so a broken driver fails loudly. P1 runs the self-test and the fixture cases twice: on a plain device
  and on a device made by `render_common.mjs`'s `setupRenderer` (the scene's `GPU_DEVICE`, with its shader-module
  wrapper), since the latter is the device a scene has. Measured: a kernel declaring `var c = u32(0)` fails through the
  wrapped instance method and compiles and runs exactly through `GPUDevice.prototype.createShaderModule.call` (4.2).
  On a software adapter (the edition supports one for hosted sandboxes) the runner warns that generation runs on the
  CPU and is many times slower; there is no CPU path in production.
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
| **dispatch logs** | the same run, with `core/gpu.run` and `core/gpu.read` wrapped from outside (the hook of `design_probes/blender_floor_patterns.py`): every dispatch's op, kernel, uniforms and bound images, every readback | the control code: kernel sequence, counts, uniforms (5.7) |
| **step snapshots** | the same run: each kernel's bound images read back after its 1st, 10th, 100th, 1,000th and 10,000th dispatch | every evolving op before chaos grows (5.7) |
| **floor samples** | the same runs perturbed (5.4): five patterns per recipe and seed, each with its own log and snapshots | the tolerances of every grade that follows a run |
| **saves** | the Blender CLI as it is: `bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe R --seed S --quality Q --save --out <dir>` | whole recipes, per level |

**Every fixture is made by the Blender edition's own Python**: Blender 5.2's bundled Python 3.13 with numpy 2.3.4 and
zlib 1.3.1, run as `<Blender's python> -I` for the numpy-only fixtures and through `run_blender.sh` for the rest.
Never the system Python: here it is Python 3.14 with numpy 2.5.2 and zlib-ng, and both differ from what makes the
Blender edition's numbers (numpy 2.5.2's percentile arithmetic is another rule again, 2.3; zlib-ng compresses
differently, 10). `tests/_where.mjs` finds that Python (`$EIDO_BLENDER_PYTHON`, else beside the Blender executable
`run_blender.sh` finds), and every fixture's manifest records the Python, numpy and zlib versions. One run per recipe
and seed makes the dumps, the log, the snapshots and a floor sample together (5.5). Fixture files go to
`eidoverse/terrain/tests/out/parity/` (ignored), keyed by the Blender commit and the Blender `code_hash()`.

### 5.2 The dump formats

- **A terrain** is the `Terrain.save` format both editions write and read: `<name>.npz` (uncompressed `np.savez`)
  with `L{i}__f__{field}` (float32 (n, n), row 0 south, metres) and `L{i}__m__{mask}` (float16 for bounded masks,
  float32 for metres and curvatures), and `<name>.json` with the info record, `recipe` (`to_dict()`), `knobs`, `plan`
  (each level's `to_dict()`: index, role, x0, y0, side, cell, n, parent, stride, prepass, band, depth) and
  `api_version`. The port adds `<name>_parity.json`: the edition, the commit, the code hash, the GPU, the numpy or
  Deno version, the date. The Blender judge's `--field` reads this file as it is. When a terrain has plants, beside
  it `<name>.plants.json` and one `<name>.plants.<species>.f32` per species (SURFACING_DESIGN.md 4.5: headerless
  little-endian float32 records of `x, y, z, yaw, scale, age, tint, nx, ny, nz, variant, level`, Blender frame);
  `Terrain.load` reads Blender's as they are.
- **A dispatch log** is `<run>/dispatch_log.jsonl.gz`, one JSON array per dispatch: `[op, kernel, [[uniform, value or
  [values]], ...] sorted by name, [[image, height, width, format], ...], [sampler names]]`, and
  `<run>/readbacks.jsonl.gz`, one `[index of the last dispatch before it, op, image or field, height, width, channels,
  [min, max, sum]]` per readback. Values are written as JSON numbers from float64 (`repr` round trip), so float32
  uniforms survive exactly. The port writes the same, with one more field per dispatch: `blender_kernel` (true for a
  kernel transcribed from Blender, false for the port's own, such as `prims` and the GPU replacements of numpy code).
- **Step snapshots** are `<run>/snap_<kernel>_<count>.npz` (every image bound to that dispatch, (H, W, C) float32).
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
| dispatch log, kernels | per op call, the sequence of Blender kernels dispatched (the port's own kernels set aside), run-length encoded | equal names and order; equal counts, except a loop that stops on a convergence test, whose count may differ by one test interval (the interval is named in the solver's port) | integer control flow; the probe of 5.7 measured which counts move under perturbation |
| dispatch log, uniforms | every uniform of every Blender-kernel dispatch | within 4 ulp of Blender's until the first uniform computed from a readback; after it, within 1.25 x the largest relative change the floor samples show at that dispatch, never below 4 ulp | uniforms are computed in JS doubles as numpy computes them, then rounded to f32 once; a readback carries the field's own difference into the control |
| step snapshots | each kernel's bound images after its 1st, 10th, 100th, 1,000th and 10,000th dispatch | ≤ max(1e-4 x range, 1.25 x the largest floor sample at that dispatch) | the kernel grade at the first dispatch; the measured growth after (5.7) |
| stage replay, non-evolving op | an op run once from Blender's input | ≤ 1e-4 x range | a few dispatches |
| stage replay, evolving op | an op that steps (fluvial, creep, talus, threshold, dunes, pipes, glacial, coast, karst) from Blender's input | ≤ max(1e-4 x range, 1.25 x the largest of five floor samples of that stage) | the stage's own floor: the dumped input replayed with the op-entry perturbation of 5.4, five patterns, by `blender_stage_dump.py --floor` |
| recipe, field class | per level: RMS(h_port - h_blender) / relief, p99 \|dh\| / relief; on the main level the channel overlap | RMS and p99 ≤ 1.25 x the largest of the recipe's floor samples on that level (never below 1e-4); overlap ≥ the smallest sample's overlap minus the samples' spread (largest minus smallest) | five samples of the floor bound what a correct port shows; one sample does not (5.4) |
| recipe, distribution class | the judge's numbers over seeds 1-4 | each metric's mean within half its band's tolerance of Blender's mean; every band Blender passes on 3 or more of the 4 seeds, the port passes on 3 or more | a chaotic recipe's numbers move by a band's width on one ulp |
| judge | the Blender judge's numbers on the port's saves | field class: each band's number within max(1.25 x the largest change the floor samples show in it, its quantisation step: one bin of the spectrum's 48, 1 % of the band's tolerance otherwise) of the Blender save's number for the same recipe and seed. Distribution class: the rule above. Verdicts are reported, not compared | a number near a band's edge flips its verdict on noise |
| mesh | ring topology; x and z; heights; `heightAt`; normals | indices equal; x, z bit-equal; heights within 14 ulp of the corner's largest tap (measured worst 3); `heightAt` within the same bound of its triangle's largest tap, and equal to Blender's `height_at` to 1e-12 relative where the triangle's three vertices are bit-equal; normals within 1e-5 rad | the analytic f32 bound of the stencil (7.3); `height_at` is float64 barycentrics on float32 vertices in both |
| look | the port's renders beside the photographs and beside Blender's renders | by eye: one paragraph per view naming what reads and what does not | DESIGN.md item 7 |

### 5.4 The chaos floor, measured

**The first protocol** (`blender_chaos_floor.py`, kept for its record): draft quality, seed 1, each recipe generated
twice as it is, then once with every `FluvialRun` start (layered rock's `StrataRun` included) moved by +1 ulp on a
random quarter of the cells and by -1 ulp on about a fifth. The reruns were bit-identical on every level of every
recipe.

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

**Why one sample is not a bound** (the review's probe, Blender 5.2, `stratovolcano`, draft, seed 1, main level 512²
at 78.1 m, relief 3,661 m, the same measures):

| perturbation | RMS / relief | p99 \|dh\| / relief | channel overlap |
|---|---|---|---|
| `FluvialRun` start ±1 ulp, the first protocol's pattern | 0.336 % | 1.60 % | 0.825 |
| the same, a second pattern | 0.514 % | 2.46 % | 0.817 |
| the same, a third pattern | 0.414 % | 2.04 % | 0.836 |
| the start ±16 ulp | 0.413 % | 1.96 % | 0.802 |
| the forcing (U, K, Sc, G) ±1 ulp at the start and every `set_par`, height untouched | 0.334 % | 1.56 % | 0.817 |

So 1.5 x the first sample (0.504 %) is below the second sample (0.514 %): a correct port can fail the first
protocol's test (taking any one of these five as the floor and another as the port, 2 of the 20 ordered pairs fail).
The size and the place of the perturbation barely matter; the pattern does.
The judge's slope percentiles, fraction under 5 degrees and spectrum knee did not move. Three more faults of the first
protocol: it perturbed only `FluvialRun`, which exists only in `solvers/fluvial.py` and `solvers/strata.py`, so
`dunes` (its one stage is `dune_field`) and `tower_karst` (`karst`, `threshold`) would get a floor of exactly 0, and
so would every evolving op that is not a `FluvialRun` (`hydraulic`, `glacial`, `dune_field`, the relaxations,
`coast`); its "≤ 1.5 x the floor" cannot be the rule for channel overlap, which is better when higher; and comparing
the judge's verdicts fails whenever a number sits near a band's edge.

**The revised protocol** (`design_probes/blender_floor_patterns.py` is the reference implementation; P3's
`blender_chaos_floor.py` takes its hooks):
1. **Every op is perturbed, at two points, from outside.** (a) At each op's entry: the level runner's `get_op` is
   wrapped, and every float32 field of the level is moved by one ulp (`np.nextafter`) on half the cells, +1 on a
   quarter and -1 on a quarter, with `default_rng([pattern, op call])`; this reaches the ops that run in numpy too.
   (b) Inside each op call: right after each kernel's first dispatch in the call, the images it wrote are read back,
   moved the same way (`default_rng([pattern, op call, kernel, 1])`) and copied back by a copy kernel, through the
   `core/gpu.run` hook; this reaches GPU state an op makes itself. Both are needed: `dune_field` grows its dune field
   on a tile from its own start fields (`aeolian.grow_tile`, `start_fields`) and never reads the level's height, so
   the op-entry point alone left `dunes` exactly unchanged (measured: RMS 0 on three patterns). A correct port's
   differences enter at every op and every kernel too (float32 where numpy was float64, fused multiply-adds, the
   built-ins). Where a kernel's state is exactly quantised (whole slabs, integer counts held as floats), a one-ulp
   nudge is a larger change than a correct port makes; the floor is then conservative (looser), never one a correct
   port fails.
   **Every sample starts clean:** the solvers keep per-process memos of results (`aeolian._TILES`: a dune tile is
   grown once per process and returned again; `volcanic._AGED_PATCHES`, `karst._PLANS` and `_DOMAINS`,
   `strata._COLUMN_CACHE`, `real_place._CACHE`), so each run clears them first (or runs in its own process), with
   `cache=False`. The first protocol and the review's probe ran their variants in one process without clearing them.
2. **Five patterns per recipe and seed**, at draft quality, seeds 1 and 2 (1-4 for the distribution class). Each
   perturbed run also writes its dispatch log and step snapshots (5.7).
3. **Field-class tolerance:** per level, RMS and p99 ≤ 1.25 x the largest of the five samples, never below the kernel
   grade (1e-4 of range). From the review's samples for `stratovolcano`'s main level: 1.25 x 0.514 % = 0.64 % RMS
   (mean + 3 sd would give 0.62 %: either works; the largest sample is simpler and does not assume a distribution).
4. **Channel overlap** (higher is better) passes at or above the smallest sample's overlap minus the samples' spread:
   for the review's samples, 0.802 - (0.836 - 0.802) = 0.768.
5. **The judge's numbers, not its verdicts** (5.3).
6. **The classes from the measured spread.** A recipe is in the field class when its largest main-level sample over
   both seeds stays under the boundary, and the boundary is put in the gap between the field-like recipes and the
   chaotic ones once all 16 are measured: from what is known, the samples sit at 0.3-0.8 % (`stratovolcano`,
   `canyon`) and at 12.6 % (`fluvial_range`), so 2 % is the provisional boundary and P3 moves it into the measured
   gap if one recipe falls near it. The channel overlap is tested within the class by its own sampled rule (item 4),
   and never decides the class: on `tower_karst` one ulp leaves the height within 1.3e-8 of relief and still moves the
   overlap to 0.61-0.71 (measured, three patterns), because flow on the flat plain between the towers turns on an
   ulp.
   Expected: `rolling_hills`, `meadow`, `badlands`, `alpine_valley` and probably `dunes` (up to 2.23 %, below)
   distribution;
   the volcanic, crater, karst, coast and `real_place` recipes field; the measurement decides.
7. **Stage floors** come from the same hook on one stage alone: `blender_stage_dump.py --floor` replays each evolving
   op from its dumped input five times with the op-entry perturbation and records the largest difference (5.3).

**Measured with the revised hooks** (`blender_floor_patterns.py`, draft, seed 1, main level 512²):

| recipe | perturbation | RMS / relief | p99 \|dh\| / relief | channel overlap | the judge's numbers |
|---|---|---|---|---|---|
| `dunes` | op entry only, memos not cleared (the first try) | 0 (three patterns) | 0 | 1.0 | unchanged: a memo hit, and the op never reads its input |
| `dunes` | both points, memos cleared (three patterns) | 1.98-2.23 %, the same on every level | 7.8-8.7 % | 0.16-0.18 | pattern 1: relief 323.4 against 321.8 m, slope p50 12.76 against 12.85 deg, fraction under 5 deg 0.346 against 0.346, spectrum knee 749 m both |
| `tower_karst` | op entry only (three patterns) | 1.29e-8 (1.4-1.9e-8 on the context levels) | 3.6e-8 | 0.61-0.71 | within 1e-6 relative |
| `tower_karst` | both points, memos cleared (pattern 1) | 1.8e-8 | 7.3e-8 | 0.64 | the same kernel sequence and counts as the base run, no uniform changed |

The dunes move as a field (the slab model's shadow and activation masks are discrete, so their snapshots go from
3e-8 of range after the first dispatch to 2.4 % after the tenth and 27 % after the 10,000th) while the place stays the
same place by every judge number; at 1.98-2.23 % their samples straddle the provisional boundary, which is why the
boundary is set from the measured gap (item 6) and from the largest sample, not one. `tower_karst` stays within ulps
of itself; its tolerance is the kernel grade.

### 5.5 The gate

- Every recipe at draft quality at its reference's extent: seeds 1 and 2 (field class), seeds 1-4 (distribution
  class); the port's save judged by the Blender judge, its numbers beside the Blender save's (5.3).
- Film quality with a focus (hero levels, seams, collider, mesh): `real_place` Lauterbrunnen and `alpine_valley`,
  seed 1.
- Hero quality once (time and memory at 2048²): `real_place` Lauterbrunnen.
- Dispatch-log parity, step snapshots and stage replay for every op, on the dumps of the draft runs above.
- **The Blender side's cost.** One base run and five perturbed runs per recipe and seed, each also making the dumps,
  the log and the snapshots: 16 recipes x 2 seeds x 6 = 192 draft runs, plus 2 x 6 = 12 more for each
  distribution-class recipe's seeds 3 and 4 (48 if four recipes are in that class): about 240 runs. A draft run took
  14-74 s in the first measurement and 44-478 s in the review's under heavier load, so at 45-180 s a run the set is
  about 3-12 hours of one GPU slot, 3-12 times the first plan's hour; P3 runs it in the background through the
  queue, recipe by recipe, and the packages that need a recipe's dumps start when its runs are in. The stage floors
  add about a tenth.

### 5.6 Keeping up with the Blender edition

The Blender edition is being finished while the port is built. So:
- every port file starts with `// Port of blender/eidoblend/terrain/<file> at <commit>.`;
- `tests/parity/sync_status.mjs` lists, per port file, the Blender files changed since its recorded commit
  (`git -C $EIDO_BLENDER_EDITION log` on the `blender` branch: read-only);
- fixtures and dumps are keyed by the Blender commit and `code_hash()`, so a stale fixture is never compared with
  new code;
- a package re-ports a changed Blender file as its own change, with the twin fixtures regenerated, before it moves on.

### 5.7 The dispatch log and the step snapshots

**Why.** The kernel fixtures take each kernel's uniforms as given, and for a chaotic recipe stage replay and the
judge are as loose as the landform's own variability: on one ulp `fluvial_range` moves 12.6 % RMS with a channel
overlap of 0.10, and its fraction under 5 degrees by 0.064. So a port with K off by 10-20 %, a wrong step count or a
dropped threshold pass would pass them all while it made a different landform. What a solver asks of the GPU is
checked directly instead: the solvers' control code (step counts, dt, the K, U and Sc factors, the relief
controller's schedule, the pass order, the boundary modes, the pins) is what the uniforms and the kernel sequence
are made of.

**How, in Blender, from outside** (no change to the Blender branch): `core/gpu.run` is the one function every
dispatch goes through (`Kernel.run` calls it, and so does `solvers/fluvial.py`'s `GPUDevice.run`, through the
module), and `core/gpu.read` every readback, so wrapping the two module attributes logs everything
(`design_probes/blender_floor_patterns.py` does it). The level runner's `get_op` gives the op of each dispatch. The
twin device of `solvers/fluvial.py` (`TwinDevice.run`) is a test device and is never logged.

**How, in the port:** `core/gpu.js`'s `onDispatch` and `onReadback` (4.2) write the same records (5.2), marking the
port's own kernels (`prims`, the GPU replacements of numpy code) so the comparison sets them aside: they replace
numpy code that Blender runs on the CPU, so they have no Blender dispatch to match.

**What is compared** (`tests/parity/dispatch_parity.mjs`, P3's):
1. Per op call, the run-length-encoded sequence of Blender kernels: names and order equal; counts equal, except for
   a loop that ends on a convergence test (routing to convergence every 128 iterations, fills and labels every 256,
   the hero bake's routing), whose count may differ by one test interval. Each solver's port names its convergence
   loops in its header.
2. Every uniform: within 4 ulp of Blender's value up to the first uniform computed from a readback (the relief
   controller's first update, a convergence decision); after it, within 1.25 x the largest relative change the floor
   samples show at that dispatch (never below 4 ulp). Integer uniforms (iteration indices for the hashes, the lock's
   phase, jump-flood steps) are exact.
3. Every readback's summary (min, max, sum) within the field grade of that point.
4. The bound images' names, sizes and formats: equal.

The device's self-test dispatch (`_self_test`, once per process at first use) is not part of a run's log, and every
compared run starts with the solvers' memos cleared (5.4), or a run that follows another in the same process skips
work the first one did.

**The step snapshots.** Each kernel's bound images after its 1st, 10th, 100th, 1,000th and 10,000th dispatch of the
run, and after its 1st, 10th and 100th dispatch within each op call on the main level, in the Blender run and in the
port, compared at max(1e-4 x range, 1.25 x the largest floor sample at that dispatch): at the first dispatch the
kernel grade, then the measured growth of a one-ulp difference. This checks every evolving op before chaos has grown,
where the whole-op and whole-recipe comparisons can no longer see a small error; the log checks every dispatch's
uniforms besides. Storage: the base run of each recipe and seed keeps its snapshots (about 0.35 GB at draft, about
11 GB for the whole floor set, in `tests/out/parity/`, regenerable); a perturbed run keeps only its differences from
them.

**Measured** (`blender_floor_patterns.py`, draft, seed 1):

| recipe | dispatches | by kernel | readbacks | log, gzipped | a one-ulp perturbation at each op's entry |
|---|---|---|---|---|---|
| `dunes` | 460,521 | `dune_avalanche` 377,874; `dune_activate`, `dune_shadow`, `dune_transport` 26,991 each (the growth loop's iterations); `route_area` 1,664; `world_noise_field` 6; `flow_weights` 3 | 65 | 0.52 MB | not reached (the op grows its own tile, 5.4) |
| `tower_karst` | 2,883 | `route_area` 2,688; `threshold_excess`, `threshold` 96 each; `flow_weights` 3 | 29 | 2 KB | the same kernel sequence and counts, no uniform changed (three patterns); the heights within 1.3-1.9e-8 of relief on every level; the main level's channel overlap 0.61-0.71; `threshold`'s images within 5.9e-8 of range after its 1st and 10th dispatch; `route_area`'s within 0.7 % after its 1st and 1.6 % after its 1,000th: the drainage area on the flat plain turns on an ulp |

So the log is small (repeated loops compress well), a perturbation need not change the kernel sequence or any
uniform, and the step snapshots separate the quantities that stay within ulps (heights, the relaxation) from the ones
that are chaotic on flats from the first dispatch (drainage area), which is why their tolerance comes from the
samples, not from one number.

### 5.8 Known Blender defects the port reproduces

The port reproduces the source of truth, defects included, so parity stays measurable; the fix lands in Blender
first and is ported as a change (5.6). The list, with where each is handled:
- **The hero-level inflow** (reported by the Blender fluvial package on 11-13; SURFACING_DESIGN.md 2.2, 2.3 step 8,
  risk 3): on hero levels the level runner's pinned inflow truncates the trunk's catchment (37 km² on the main level
  to 1.5 km² on the finest hero level at the `fluvial_range` `canyon_road` focus). `run.js` (P5) reproduces it; the
  surface bake's re-routing with pinned inflow (P14) reproduces the workaround.
- Every other defect a package finds in the Blender code goes to the lead with its evidence and is added here when
  the lead decides it stays for parity.

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
| `out/review/views_plan.json` (the surfacing judge's 50 matched cameras over 16 recipes, 45 matched to a photograph) | no (`blender/tests/*/out/` is ignored) | 30 KB | the Blender review scripts; the surfacing wave reads it in place, like the photographs |
| the surfacing judge's code (`surfacing_judge/`, landing) and the material bench and shimmer probe (`surfacing/`) | yes, as they land | small | the Blender surfacing round's package 5; run as they are on the port's renders (P16) |

### 6.2 How the port reads it

`tests/_where.mjs` mirrors the Blender branch's `blender/tests/_where.py` (committed there in `72c9b41`):
- **The Blender edition:** `blender/` in this checkout when it is a `blender`-branch checkout (that branch merges
  `main`, so after the merge it holds both editions), else `$EIDO_BLENDER_EDITION` (the root of a checkout of the
  `blender` branch, such as a worktree).
- **Blender's Python** (every fixture, the judge, 5.1): `$EIDO_BLENDER_PYTHON`, else the bundled Python beside the
  Blender executable that `run_blender.sh` finds (`$BLENDER`, then `blender` on the path, then the usual install
  folders), as `<version>/python/bin/python(.exe)`; run with `-I`.
- **DEMs for `real_place`:** `$EIDO_TERRAIN_DEMS` (the Blender edition's variable: folders separated by the path
  separator), then the Blender edition's `reference/data`. A name that is in neither raises, naming both.
- **GPU jobs:** `$EIDO_GPU_WRAP` is put in front of every Deno or Blender job a test starts (the Blender branch's
  convention); unset, the job runs directly.
- **Missing inputs:** a test that needs one of these and cannot find it skips, printing the variable to set and the
  fetch command, as `_where.external()` does. Nothing has a default path of one machine.

### 6.3 One judge, the port's own renders

- **Numbers and bands:** `tests/judge/judge.mjs` saves the port's terrain in the `Terrain.save` format (P4's
  `api.js`) and runs the Blender judge on it with Blender's Python (C6): `<Blender's python> -I
  blender/tests/terrain/judge/run.py --field <save.npz> --reference <name> --no-render --out <dir>` from the Blender
  checkout. It reads `verdicts.json`, numbers and verdicts; parity compares the numbers (5.3). One judge, so a
  difference in a number is a difference in the ground.
- **Views:** the port renders the reference's three views itself, in the three.js edition's renderer: a scene made
  from `<name>_views.json` (camera, target, lens, sun, sky `earth` at the given hour, axes converted as in 2.2), the
  DEM drawn by P4's `build/mesh.js` (no second mesh builder), grey clay at albedo 0.18 like the reference rig,
  rendered through `eidoverse/render_scene.mjs` at 960 x 540.
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
    surface: 'auto',             // the surface data bake (SURFACING_DESIGN.md 2.3): 'auto' | null | options; last wave
    plants: null,                // the plant layer (4): null | 'auto' | { ecotope, focus, radiusM, seed }; last wave
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
| `surface='auto'`, `plants=None \| 'auto' \| dict` (SURFACING_DESIGN.md 5.3, package 5) | `surface: 'auto'`, `plants: null \| 'auto' \| {...}`; until the last wave lands, `'auto'` resolves to null with one notice, as `palette: 'auto'` gives clay |
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
| `t.surface` | the surface data (`SurfaceData`: per-family data textures, layouts, `maps(level)`, `at(name, x, z)`, `channel(name)`), or null; last wave (3.5) |
| `t.plants` | the plant spots (`PlantSpots`: `names()`, `array(species)` as the saved records, `field(species, name)`, `cover(level)`, `stats`), or null. Wave 1 fills it only from `Terrain.load` of a save that carries spots (Blender's or the port's); the planner is the last wave's |
| `t.metrics(pixelM)` | the judge's generic numbers of the main tile (`core/metrics.js`) |
| `t.viewpoint(target, distance, opts)` | a standing point that sees the target, as Blender's `viewpoint` (the judge's eye spots), in three.js axes |
| `t.preview(path)` | hillshade and mask PNGs |
| `t.save(path)`, `Terrain.load(path)` | the `Terrain.save` format (5.2), with the plant spots beside it when there are any: a port save loads in Blender and the reverse |
| `t.dispose()` | releases the GPU buffers and geometry |

### 7.3 The ring mesh as a BufferGeometry

The same construction as `build/mesh.py`, built by kernels:
- **Windows on the integer lattice** of the finest cell (`_integer_windows`), rings as each level's window minus its
  child's, `stride = round(n / meshRes)` (2 at 1024 cells), cores on the finest level down to stride 1 when there is a
  focus. The ring specs are a handful of integers per level, computed in JS exactly as `plan_rings` does.
- **Positions in the ground plane, bit-equal.** Blender writes each lattice line as `np.float32(origin + xs * unit)`
  in float64 (`_assemble`, `RingMesh._line`). The port computes the same lines in JS doubles, `Math.fround(origin + xs
  * unit)`: a few thousand values per terrain, not a per-vertex loop. The vertex kernel gathers them by lattice index;
  the axis conversion only negates (exact). Measured: 20,485 of 20,485 lattice values equal for five real (origin,
  unit) pairs.
- **Heights** by a kernel per ring: each level's height at the cell corners by Catmull-Rom (weights -1, 9, 9, -1
  over 16, rows first and then columns, taps clamped at the edge, as `_sample`), the seam row overridden by the
  parent's straight edge, shared vertices where two rings meet. Blender evaluates `_sample` in float64 and rounds once
  to float32; the port evaluates in f32. The bound, for any f32 evaluation order with or without fused
  multiply-adds: |z_port - z_blender| < 13.5 ulp(H), H the largest |h| of the corner's 16 taps (12.5 from the two
  length-4 dot products, whose weights sum to 20/16 in magnitude, 1 from Blender's own rounding). Measured on three
  1024² fields (`alpine_valley` 116-2,828 m; a layered-rock field -23 to 657 m with 73 m steps a cell; a chalk coast -15
  to 195 m): 36-40 % of the corners differ, all by at most 3 ulp(H). Measured relative to z instead, the same corners
  reach 43,780 ulp(|z|) where z crosses 0 beside a 5 m tap, so the bound is relative to the taps. A double-float
  evaluation was tried and is not used (2.3). No mask attributes: the material reads data textures (3.5); a debug
  option `meshMasks: [names]` adds up to eight as attributes (WebGPU's default `maxVertexAttributes` is 16).
- **Indices** by a kernel per ring: every quad split along its (i, j) - (i + 1, j + 1) diagonal, the parent's cells
  along the hole drawn as fans through the child's in-between vertices (no T-junction), the outer skirt 50 m below
  the lowest border vertex. The topology is a pure function of the ring specs, so it is compared index for index
  with Blender's `RingMesh` (after the axis conversion). The index buffer is written ring by ring, and each ring is
  one geometry group (`geometry.addGroup(start, count, materialIndex)`): material 0 (the near material) for the main
  and hero rings and the cores, material 1 (the far material, SURFACING_DESIGN.md 3.7) for the context rings, as
  Blender's `material_index` per ring; the skirt takes the index Blender's `build/mesh.py` gives it when the surfacing
  round's package 2 lands (until then, its outer ring's). Until the last wave both slots hold the clay.
- **Normals** by a kernel: Blender's `RingMesh.vertex_normals`, as written: the corner-angle-weighted sum of the unit
  face normals of every triangle at the vertex, the skirt's triangles excluded, then normalised. As a gather, with no
  atomics: on the regular part of a ring each vertex's six triangles are known from its lattice position; the fans
  along the seams get a vertex-to-triangle table made once by a key-value radix sort of (vertex, triangle) pairs
  (`prims`), so every vertex sums its triangles in a fixed order. Within 1e-5 rad of Blender's (f32 cross products and
  `acos` against float64).
- **No cracks**, shown three ways: every edge of the terrain's triangles belongs to exactly two triangles except the
  outer border's, which the skirt closes (an exact check of the index buffer, by a sort of the edges); grazing
  renders along every seam (a camera 2 m above the ground, looking along the seam, over an emissive backdrop, at 2x
  crops: a top-down view cannot show a vertical gap); and the port of `blender/tests/terrain/mesh_api/test_seam_crease.py`
  on `real_place` Lauterbrunnen (the crease across each ring border within 25 % + 0.1 degree of the ordinary lattice
  lines at p50 and p99, its own criterion).
- **Read back once** (positions, normals, indices: about 80 MB for 3.3 M triangles, about 0.3 s), then a plain
  `BufferGeometry` (`Uint32` index) with `boundingBox` and `boundingSphere` set from the GPU's height range, so nothing
  walks the vertices on the CPU. The host copies serve `heightAt` and the collider.

### 7.4 `heightAt`, `normalAt`, `viewpoint`

- `heightAt(x, z)`: Blender `height_at(x, -z)`: the finest ring whose window holds the point, the cell, the triangle
  by the diagonal rule or the fan rule, barycentric in float64 on the float32 vertices, transcribed in Blender's
  order. Exact on the rendered triangles, as Blender's; outside the outermost window, its edge. Against Blender's:
  equal to 1e-12 relative where the triangle's vertices are bit-equal, and within the vertices' bound (7.3)
  elsewhere, since a barycentric blend never exceeds its vertices' largest error.
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
- The clay material (`palette: null`) and the water material are NodeMaterials; `t.mesh.material` is the array
  `[near, far]` the ring groups index (7.3), both the clay until the last wave; until then `palette: 'auto'` gives
  the clay with a warning.

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
- **Every op a package ports is accepted by four checks before its recipes are:** kernel fixtures, stage replay,
  dispatch-log parity and step snapshots (5.3, 5.7), on the dumps of P3's floor runs. Whole-recipe parity and the
  bands come after, once every op of the recipe exists (8.4).
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
| P1 | **Runner and primitives** | `core/gpu.js`, `core/prims.js`, `core/np_random.js`, `kernels/common.wgsl`, `kernels/prims/*`, `tests/core_runner/*`; the `.gitignore` line and the limits list in `eidoverse/render_common.mjs` | `core/gpu.py`, `common.glsl`, numpy's Generator | `tests/design_probes/mini_runner.mjs`, `wgsl/common.wgsl`, `np_random_probe.mjs`; `gpu_check.mjs` | - | round trips exact; the 46 design-probe fixture cases pass through the production runner, on a plain device and on a `render_common` device (4.7); modules compile through `GPUDevice.prototype.createShaderModule.call` (C7); `onDispatch` / `onReadback` hooks (4.2, 5.7); every primitive against its numpy original (fill and labels bit-exact, selections bit-equal to numpy 2.3.4 for every call form the package uses: `percentile` with a number and with a list, `quantile`, `median`, float32 and float64 data, with ties, at 512², 1024² and 2048²; sorts and scans exact; Gaussian within 1e-5); `np_random.js` draw for draw against Blender's numpy for `random`, `uniform`, `integers`, `normal`, `standard_normal`, `exponential`, `poisson`, `choice` (the ziggurat tables come from numpy's source, BSD-3, with the notice) over 50 seeds and every call form the terrain uses; every fixture made by Blender's Python, its versions recorded (C6); the 4.8 benchmark re-run; determinism. Its tests take the Blender edition from P3's `tests/_where.mjs` once that lands | moderate |
| P2 | **Core inputs** | `core/levels.js`, `grid.js`, `fields.js`, `recipe.js`, `expr.js`, `world_noise.js`, `compose.js`, `cache.js`, `io.js`, `kernels/grid/*`, `kernels/compose/*`, `kernels/world_noise_field.wgsl`, `kernels/noise.wgsl`, `tests/core_inputs/*` | `core/*.py` but gpu, twins and metrics | the design probe's `world_noise_field.wgsl`; Ekigar's `src/export/png.js`, `png_read.js` | P1's interfaces | `plan_levels` JSON-equal for 20 focus cases at every quality, including half-way cases of `pyRound` (C10); recipe `to_dict` / `resolve` equal; expressions equal in parse and within 1e-6 in value; world noise (sums, products, warps, periodic) within 1e-6 of range; shapes and stamps within 1e-5; resampling within f32 rounding; a Blender `Terrain.save` (zip64, float16 masks; a hero save over 4 GB streamed) read and written back with every array byte-identical; PNG16: pixels and the filtered rows byte-identical to Blender's `export_heightmap`, IHDR and the sidecar equal, the compressed IDAT not compared (C9); R32 byte-identical; the cache's two hashes over exactly the globs of C8, `prune` and `clear` with the `surface_*` files and the spots counted (C4) | light |
| P3 | **Parity and judge** | `tests/_where.mjs`, `tests/parity/*` (`fixtures.py`, `blender_stage_dump.py`, `blender_chaos_floor.py`, `replay.mjs`, `field_parity.mjs`, `sync_status.mjs`), `tests/judge/*` (`judge.mjs`, `views.mjs`, `sheets.mjs`), `core/metrics.js`, `kernels/metrics/*` | `core/metrics.py`; the harness, not the judge | the Blender judge, bands, references, view JSONs and photographs in place; `bake.py --save`; the op-entry and dispatch hooks of `design_probes/blender_floor_patterns.py` | P1, P2; P4 for the views and for judging port saves | the adapter's numbers on Blender's own saves equal `run.py`'s; the chaos floor of all 16 recipes, seeds 1-2, by the revised protocol (C1, 5.4): five patterns each, every op perturbed, with the dispatch logs, readbacks, step snapshots and stage dumps of the same runs (C2), the per-stage floors (`blender_stage_dump.py --floor`), and the classes set from the measured spread; the reference views of five places rendered by the three.js edition through P4's mesh and framed like the Blender reference renders (a sheet); `core/metrics.js` equal to `metrics.py` on five reference DEMs (percentiles exact per call form, the rest within 1e-6 relative, the spectrum within 1e-4); `sync_status.mjs` lists the changed Blender files; `tests/_where.mjs` finds Blender's Python (C6) | heavy (Blender: about 190 draft runs, 5.5) |
| P4 | **Mesh and API** | `api.js`, `index.js`, `bake.mjs`, `build/mesh.js`, `build/water.js`, `build/collider.js`, `kernels/mesh/*`, `kernels/water/*`, `recipes/index.js`, `recipes/real_place.js`, `tests/mesh_api/*` | `api.py`, `bake.py`, `build/mesh.py`, `build/water.py`, `recipes/__init__.py`, `recipes/real_place.py` | Ekigar's `terrain_mesh.js` measurements; `scene_placement.js` and `robot_controller.js` contracts | P1, P2; builds from Blender saves before any solver exists | from a Blender save: ring topology index-equal to Blender's `RingMesh`; x and z bit-equal (lattice lines in JS doubles, C3); heights within 14 ulp of each corner's largest tap; normals within 1e-5 rad of `vertex_normals` (angle-weighted, skirt excluded, a gather); one geometry group per ring with Blender's material index, no mask attributes; `layout()` JSON equal; `heightAt` at 2,000 points (a Python dump) equal to Blender's `height_at` to 1e-12 relative on bit-equal triangles and within the tap bound elsewhere; no cracks: the edge-manifold check exact, grazing renders along every seam over an emissive backdrop, and the port of `test_seam_crease.py` on Lauterbrunnen within its criterion; the ray caster equal to a brute-force triangle ray cast on 1,000 rays; the collider's surface within 1e-3 m of `heightAt`, built by Rapier in under 2 s; `real_place` Lauterbrunnen with a hero window: no seams, a VRM placed by `heightAt` stands on the ground (render); `surface` and `plants` accepted (null until the last wave), `t.plants` loaded from a Blender save with spots and written back with every record byte-identical; unknown options and knobs name the nearest; a cache hit at film quality in under 5 s | moderate |
| P5 | **Hydrology and level runner** (critical path) | `run.js`, `solvers/hydro.js`, `kernels/flow_weights.wgsl`, `kernels/route_area.wgsl`, `kernels/hydro/*`, `tests/hydro/*` | `run.py`, `solvers/hydro.py` | the design probe's `flow_weights.wgsl` | P1, P2, P3 | kernel fixtures; function fixtures (fill and lakes exact; the routing surface's `_descend` in the path-maximum form within 2 ulp of Blender's float64 (C11); drainage area within its tolerance; inflow within 1e-6); the runner's inherit, pins and `where` on stage dumps; the runner's own dispatch-log parity (the pre-passes, the level loop); level seams (\|dh\| ≤ 0.05 m at the border, slope jump ≤ 3 degrees); determinism | heavy |
| P6 | **Fluvial backbone and hillslopes** | `solvers/fluvial.js`, `solvers/hillslope.js`, `kernels/{route_incise,creep,threshold,threshold_excess,h_keep,creep_layers,lock_restrict,lock_apply,soil_jacobi}.wgsl`, `recipes/{fluvial_range,rolling_hills,meadow}.js`, `tests/fluvial/*` | `solvers/fluvial.py`, `solvers/hillslope.py`, the three recipes | the design probe's six transcribed kernels | P5; for `fluvial_range` and `meadow` whole, P12's `breakup` and `hydraulic` (8.4) | kernel fixtures for all nine kernels and every Blender variant; creep and threshold conserve the sum of h within 1e-5 over 300 iterations; stage replay, dispatch-log parity and step snapshots of `uplift`, `fluvial`, `valley_floor`, `incise`, `creep`, `talus`, `threshold`, `soil_hills`, `hummocks` (the relief controller's schedule, K, U and Sc factors, step counts and the lock's phases checked in the log); parity in each recipe's class: `rolling_hills` first (its ops are all P6's), then `fluvial_range` and `meadow`; the bands against the San Gabriels and the Palouse, the meadow's probe criteria; the step within 1.25 x Blender's measured cost | heavy |
| P7 | **Masks** | `masks.js`, `kernels/masks/*`, `tests/masks/*` | `masks.py` | - | P2, P3 | `masks.compute` on five reference DEMs: every mask within 1e-4 of range; slope equal to the references' JSON; `compute_stack` on a Blender save (padding, norms, border pins) equal; scale independence on 2x resampled fields, as Blender tests it | moderate |
| P8 | **Wind and sand** | `solvers/aeolian.js`, `kernels/{dune_activate,dune_shadow,dune_transport,dune_avalanche}.wgsl`, `recipes/dunes.js`, `tests/wind_sand/*` | `solvers/aeolian.py`, `recipes/dunes.py` | - | P5 (`dunes`'s only stage is `dune_field`) | kernel fixtures (the hash decisions identical); sand mass conserved; the wind schedules equal (numpy draws); stage replay, dispatch-log parity and step snapshots of `dune_field`; parity in class for star, barchan, transverse and linear; the bands against the Namib, Great Sand Dunes, White Sands and the Namib linear dunes | heavy |
| P9 | **Volcanoes and craters** | `solvers/volcanic.js`, `solvers/impact.js`, `kernels/volcanic/*`, `kernels/impact/*`, `recipes/{stratovolcano,caldera,cinder_cones,impact_crater}.js`, `tests/volcanoes_craters/*` | `solvers/volcanic.py`, `solvers/impact.py`, the four recipes | - | P2 (shapes), then P5, P6 (aging: `FluvialRun`; `talus`, `threshold`); for `stratovolcano` whole, P12 (8.4) | profiles against numpy (Fuji's slopes at 0, 10 and 15 km; Pike's and Wood's ratios); cone and vent plans equal; the lava walkers' visits equal to numpy's for the same height field; `quantile` per numpy 2.3.4 at `volcanic.py:2865` (C6); stage replay, dispatch-log parity and step snapshots of every op; parity in class (`stratovolcano`'s floor: five samples, 0.33-0.51 % of relief, 5.4): `caldera`, `cinder_cones`, `impact_crater` first, `stratovolcano` once P12 lands; the bands against Fuji, Crater Lake, SP Crater and Meteor Crater | moderate |
| P10 | **Layered rock and rivers** | `solvers/strata.js`, `solvers/rivers.js`, `kernels/{strata_threshold,strata_cell,strata_creep,strata_weather}.wgsl`, `kernels/strata/*`, `recipes/{canyon,incised_meanders,mesas_buttes,badlands}.js`, `tests/layered_rock/*` | `solvers/strata.py`, `solvers/rivers.py`, the four recipes | - | P5, P6; for every one of its recipes whole, P12's `breakup` (and `hydraulic` for `badlands`) (8.4) | kernel fixtures; column tables equal; river courses equal (plan fixtures); stage replay, dispatch-log parity and step snapshots of `strata`, `plateau`, `river_path`, `strata_fluvial`; parity in class (`canyon`'s floor: 0.75 % in the first protocol's one sample; re-measured by C1); the bands against Toroweap, the Goosenecks, Monument Valley and the Badlands | heavy |
| P11 | **Karst and coast** | `solvers/karst.js`, `solvers/coast.js`, `kernels/{coast_fetch,coast_seed,coast_jfa}.wgsl`, `kernels/karst/*`, `recipes/{tower_karst,sea_cliffs}.js`, `tests/karst_coast/*` | `solvers/karst.py`, `solvers/coast.py`, the two recipes | - | P2, then P5, P6 (`threshold`, `fluvial`, `creep`); for `sea_cliffs` whole, P12's `breakup` (8.4) | the karst plan equal (Poisson disc, Dijkstra course, towers) within 1e-12, its cluster threshold by `quantile` per numpy 2.3.4 (`karst.py:744`, C6); kernel fixtures (the fetch's exact traversal, the jump flood); `evaluate` within 1e-5 of range; stage replay, dispatch-log parity and step snapshots of `karst`, `coast_land`, `coast`; parity in class: `tower_karst` first, `sea_cliffs` once P12 lands; the bands against Guilin (with its photographs), the Seven Sisters and Moher | moderate |
| P12 | **Detail** | `solvers/hydraulic.js`, `solvers/detail.js`, `kernels/{pipes_flux,pipes_water,pipes_transport,pipes_thermal,breakup}.wgsl`, `kernels/detail/*`, `tests/detail/*` | `solvers/hydraulic.py`, `solvers/detail.py` | Ekigar's `src/nodes/phacelle.js` | P1, P2 (noise), P5; for `real_place` whole, P4 (`dem`) and P6 (`fluvial`, `talus`) (8.4) | on the critical path (C5): `breakup` and `hydraulic` are stages of 10 recipes. Kernel fixtures; water and sediment conserved; breakup at 40 km from the origin; stage replay, dispatch-log parity and step snapshots of `breakup`, `hydraulic`, `gully`, `planation`; then on `real_place` Lauterbrunnen the hero levels add detail without moving the landform (main metrics within 1 %); eye views show rills, ribs and talus | heavy |
| P13 | **Glacial** | `solvers/glacial.js`, `kernels/{ice_flux,jump_flood,u_carve}.wgsl`, `kernels/glacial/*`, `recipes/alpine_valley.js`, `tests/glacial/*` | `solvers/glacial.py`, `recipes/alpine_valley.py` | - | P5, P6; for `alpine_valley` whole, P12 (8.4) | kernel fixtures (the jump flood's candidates identical); the ice-flux balance closes; streams and centrelines equal to numpy's on stage dumps (the GPU sort against `lexsort`); stage replay, dispatch-log parity and step snapshots of `valley_uplift` and `glacial`; the U-shape fit; the bands against Lauterbrunnen and Yosemite | heavy |
| P14 | **Surface data** (last wave; Blender's package 1) | `surface/*` (`index.js`, `maps.js`, `bake.js`, `layers.js`, `palette_bake.js`, `far_colour.js`, `mask_expr.js`, `noise.js`, `kernels/*.wgsl`), `build/ops.js`, `build/palettes.js`, `tests/surface_data/*` | `surface/*`, `build/palettes.py` as data (3.5) | `core/gpu.js`; `flow_weights`, `route_area`, the detail op's `relax` and `strength`; Ekigar's `export/ops.js` and the pattern of `export/surround_bake_gpu.js` | Blender's `surface/` and `palettes.py` committed; P4, P7, P12 | the design's package-1 acceptance on the port: `palettes.js` JSON-equal to `palettes.py`; every kernel equal to `surface/twins.py` within 1e-4 of range on the 96 x 80 field; `noise.js` equal to `surface/noise.py` (u32 hashes bit-exact, values within 1e-6) and to Blender's Noise Texture within 1e-3; `mask_expr.js` equal to `palettes.evaluate` within 1e-5 on every palette's noise-free expressions; every map of a Blender-made terrain (from its save) equal to Blender's bake (`SurfaceData.maps`) within the twin grade, C and P within 1/255; seams within 1 % of range; the hero drainage within 15 % (the design's item 4); map sheets beside the hillshade, looked at; cost within the design's 7 | heavy |
| P15 | **Plants and dressing** (last wave; Blender's package 4) | `build/plants.js`, `build/ecotopes.js`, `build/plant_instances.js`, `build/dressing.js`, `kernels/plants/*`, `tests/plants/*` | `build/plants.py`, `ecotopes.py`, `plant_instances.py`, `dressing.py` | `createFlora` (`vegetation_loader.js`), `makeSeedTree` (`seedthree_api.js`) and SeedThree's LOD ladder and billboards, `fetch_model.py --cache` rocks | Blender's `plants.py` committed; P4, P14 | spots against Blender's spots files for the same terrain, ecotope and focus at the grade the lead sets (section 10): candidates bit-exact, decisions equal except counted near-ties, positions within f32 rounding; or stems per hectare and the pair correlation g(r) within the design's ranges; deterministic bytes; a larger radius keeps the inner spots; no two plants closer than their core; none floats or is buried (`heightAt` at every spot); renders beside the photographs at the design's six views, objects near and canopy far, no hand-off ring at 2x; the per-frame LOD a compute pass; eye frames within the edition's frame budget | heavy |
| P17 | **Material** (last wave; Blender's package 2) | `build/surfacing.js`, `tests/surfacing/*` | `build/surfacing.py` (3.5) | Ekigar's `materials/texture_arrays.js` and `export/layer_kernel.js`'s pattern; `build/ops.js` (P14); the edition's texture cache, `loadImageTexture`, the shimmer measurement | Blender's package 2 committed; P4, P14 | the design's package-2 acceptance in this renderer: the reader's top-down emission render equal to the bake's arrays within 1/255 (RGBA8) and 1e-3 relative (16F) on every level; grazing renders across every window edge without a seam ring at 2x; sectors on the canyon's brink wall and a 45-degree wall without smear; hex tiling without mip seams at 2-20 m and the repetition peak ≤ 0.12; the shimmer probe; the Seven Sisters' chalk face without teeth; C and the near material matching across the 64-cell cross-fade; at most 16 sampled textures; frame cost and compile time recorded beside Blender's | heavy |
| P18 | **Look** (last wave; Blender's package 3) | `tests/surface_look/*` | Blender's package 3's judgement, on the port: the port tunes no look (the palettes are P14's data port) | the design's review views and boards, its measures' Python tools | Blender's package 3 committed; P14, P15, P17 | `palettes.js` JSON-equal to the committed `palettes.py` (checked here, owned by P14); every recipe's matched views beside the photographs and beside Blender's renders of the same views, read item by item against the design's 3.9 table; the crater's walls and rocks unchanged or better beside `impact_crater_v5`; the design's measures by its own Python tools on the port's renders beside Blender's; each difference sent to its owner (P17 material, P14 bake, P15 plants) with the crops that show it | heavy |
| P16 | **Integration** | `eidoverse/terrain.js`, `render_scene.mjs` (the comment), `robot_controller.js` (the proxy condition and its comment), `README.md`, `tools-guides/terrain-surfaces.md`, `tools-guides/vegetation.md`, `docs/TOOLS.md`, `AGENTS.md`, `eidoverse/examples/terrain/*`, `techniques_archive.md` (appended) | the old implementation's removal; Blender's integration package and the surfacing design's package 5 (the wiring of `surface` and `plants`, its judge) | every package; the surfacing judge's measures (`blender/tests/terrain/surfacing_judge/`, numpy and Pillow) run on the port's renders as they are | all | the whole gate (5.5) in one run; `makeTerrain({ ..., surface: 'auto', plants: 'auto' })` end to end and through save and load, and a Blender save with its surface and spots loaded and rendered; every recipe's sheet and the surfacing design's boards (photograph, Blender, port, layer map); the design's measures (one-material share, repetition, height-line index, colour, seams, plants) beside Blender's numbers; review videos per recipe (an 8 s aerial orbit and a 6 s eye-level dolly, 960 x 540, H.264 High yuv420p, checked with ffprobe) through `python eido.py render`, watched for shimmer, seams and pops; the callers work: a scene with flora on `terrain.heightAt`, the robot walking on a `real_place` hero window, `snapToGround` on the new mesh | heavy |

### 8.3 The waves

1. **Wave 1, now:** P1 Runner and primitives, P2 Core inputs, P3 Parity and judge, P4 Mesh and API. P1 lands the
   runner first (it starts from the prototype) and P3 lands `tests/_where.mjs` and the fixture generator first (it
   starts from `make_twin_fixtures.py`); the others code against sections 3-5 meanwhile. P4 builds from Blender
   saves, so the mesh, `heightAt`, the collider and the views are on screen before any solver runs; P3's view sheet
   and its judge runs on port saves follow P4's mesh and `Terrain.save`. P3 runs the chaos floor of every recipe by
   the revised protocol (C1), and those runs make the dumps, logs and snapshots every later package is checked by.
2. **Wave 2, when the runner and the fixtures are in:** the critical path, P5 Hydrology and level runner, P6 Fluvial
   backbone and P12 Detail together (P6 and P12 begin with their kernels' fixtures, stage replay, dispatch logs and
   snapshots, which need only P1-P3; whole recipes follow `run.js` and each other's ops, 8.4: `rolling_hills` is the
   first whole recipe, P6's alone), then P7 Masks and P9's analytic shapes as slots free.
3. **Wave 3, when `run.js`, the fluvial step, `breakup` and `hydraulic` are in:** P8 Wind and sand (it needs only
   P5, so it may start in wave 2 when a slot frees), P10 Layered rock, P11 Karst and coast, P13 Glacial, and P9's
   aging and flows.
4. **Wave 4, package by package as each Blender surfacing package commits** (the design is final, `a3a72b9`; its code
   is landing): P14 Surface data (after Blender's `surface/`), then P15 Plants and dressing and P17 Material, then P18
   Look. P4 has already reserved their interfaces (C4).
5. **Wave 5:** P16 Integration. The old `makeTerrain` is removed only here, when the new one has its material, so no
   scene loses textured ground in between.

No more than four packages at once on this machine (the session-load rule); a wave's later packages start as earlier
ones finish. The critical path: P1 → P2 → P5 → P6 + P12 → the whole recipes of P9, P10, P11, P13 → P16.

### 8.4 Which packages each recipe needs

From the registry's stages (imported in Blender's Python; `recipes/__init__._collect_ops` for the owners). A recipe
is judged whole only when every op of its stages is ported; the package that owns the recipe file runs that gate.

| recipe (owner) | stages | ops' packages | judged whole after |
|---|---|---|---|
| `rolling_hills` (P6) | uplift, fluvial, incise, soil_hills, valley_floor | P6 | P5, P6 |
| `fluvial_range` (P6) | uplift, fluvial, valley_floor, **breakup, hydraulic** | P6, P12 | P5, P6, P12 |
| `meadow` (P6) | uplift, fluvial, soil_hills, **hydraulic**, hummocks | P6, P12 | P5, P6, P12 |
| `dunes` (P8) | dune_field | P8 | P5, P8 |
| `stratovolcano` (P9) | volcano_setting, fluvial, volcano_plain, stratovolcano, volcano_age, lava_flows, lava_rubble, talus, **breakup, hydraulic**, volcano_lakes | P9, P6, P12 | P5, P6, P9, P12 |
| `caldera` (P9) | volcano_setting, stratovolcano, volcano_age, lava_flows, caldera_collapse, threshold, talus, volcano_age, talus, caldera_lake | P9, P6 | P5, P6, P9 |
| `cinder_cones` (P9) | volcano_setting, lava_flows, cinder_cones, lava_flows, lava_rubble, cone_rills, talus, volcano_lakes | P9, P6 | P5, P6, P9 |
| `impact_crater` (P9) | volcano_setting, fluvial, impact_crater, volcano_age, talus, crater_blocks, volcano_lakes | P9, P6 | P5, P6, P9 |
| `canyon`, `incised_meanders`, `mesas_buttes` (P10) | strata, plateau, river_path, strata_fluvial, **breakup** | P10, P12 | P5, P6, P10, P12 |
| `badlands` (P10) | strata, plateau, strata_fluvial, **breakup, hydraulic** | P10, P12 | P5, P6, P10, P12 |
| `tower_karst` (P11) | karst, threshold | P11, P6 | P5, P6, P11 |
| `sea_cliffs` (P11) | coast_land, fluvial, creep, coast, **breakup** | P11, P6, P12 | P5, P6, P11, P12 |
| `alpine_valley` (P13) | valley_uplift, fluvial, fluvial, glacial, talus, **breakup, hydraulic** | P13, P6, P12 | P5, P6, P12, P13 |
| `real_place` (P4) | dem, fluvial, talus, **breakup, hydraulic** | P4, P6, P12 | P4, P5, P6, P12 |

So `breakup` is a stage of nine recipes and `hydraulic` of six, ten recipes in all; only `rolling_hills`, `dunes`,
`caldera`, `cinder_cones`, `impact_crater` and `tower_karst` can be judged whole without P12. The dependency between
P6 and P12 runs both ways only at the level of whole recipes (P6's `fluvial_range` needs P12's ops, P12's
`real_place` needs P6's), never at the level of ops, so neither waits for the other's acceptance.

---

## 9. Risks

1. **Chaos (measured).** A float difference anywhere changes a fluvial range's network (section 5.4); exact fields are
   unattainable for those recipes even between two Blender machines, and even a field-like recipe's floor depends on
   the pattern of the difference (0.33-0.51 % over five patterns). Handled by the classes, tolerances from five
   samples of every op's perturbation, the dispatch log (the same computation asked for, whatever chaos does to its
   result), step snapshots before chaos grows, stage replay from Blender's own inputs, and the judge's numbers over
   seeds.
2. **Float precision on the GPU.** f32 only, fused multiply-adds, the built-ins' errors (2.3), and Blender's numpy
   parts in float64. And measured in the revision: this machine's shader compiler does not keep error-free
   transformations (a double-float evaluation came out worse than plain f32), so compensated arithmetic is not a
   tool here. Handled by per-grade tolerances relative to a computation's inputs (the mesh: 14 ulp of the largest
   tap); plans and uniforms in float64 JS; angles to tangents on the CPU; integer paths exact; where an f32 form
   loses to float64 by much, a better-conditioned form of the same quantity (`_descend`'s path maximum: 1 ulp against
   82).
3. **Atomics and reductions.** No float atomics; order-dependent float sums would make runs differ. Handled: gathers
   as in Blender, integer atomics only on order-independent quantities, fixed-tree sums, exact selections.
4. **Deno WebGPU on this machine.** The storage-buffer limit (default 8, two kernels need 9: request it; fail loudly
   below); about 16 ms per GPU-to-CPU sync and about 3 ms per MB (no waits inside steps; reductions, not fields);
   0.72-0.80 ms per dispatch if each is submitted alone (batching); no subgroups (shared-memory reductions); the
   scene device's shader-module wrapper (compile through the prototype, C7, measured); the default device's texture
   limits (8,192 a side, 16 sampled textures a stage), which the surfacing wave fits by 2D-array textures (4.7); only
   Deno 2.8.1 is installed here, and `eido.py` also accepts 2.9.5, whose wgpu may compile WGSL differently: the parity
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
13. **Two Pythons, two numpys, two zlibs (measured).** Blender's bundled Python 3.13 carries numpy 2.3.4 and zlib
    1.3.1; this machine's system Python 3.14 carries numpy 2.5.2 and zlib-ng; Deno's deflate is a third. Percentiles
    and compressed bytes differ between them. Handled: every fixture comes from Blender's Python and records its
    versions (5.1); PNGs are compared by pixels and filtered rows (C9).
14. **The plant planner's numbers are float64 hashes.** Blender draws every plant number from a splitmix64 hash made
    into a 53-bit float64 uniform and compares float64 densities; WGSL has neither u64 nor f64. The hashes and the
    candidates can be bit-exact (u64 emulated as u32 pairs); a decision can flip only where a float64 comparison is a
    near-tie in f32. The grade (near-exact with counted ties, or statistical) is the lead's (section 10).
15. **A second moving source of truth.** The surfacing code lands while the port is planned; its files are
    uncommitted as I write. Handled: wave 4 starts package by package when each Blender package commits, ported from
    the committed file (5.6), and the surface options, members and files are reserved in wave 1 so no wave-1 file has
    to change for it.

---

## 10. Open questions, disagreements, and decisions for the lead

### 10.1 Where I disagree with the review, where I changed my mind, and why

1. **PNG byte identity through `CompressionStream`: no.** The review measured Deno's `CompressionStream('deflate')`
   byte-identical to "Python's `zlib.compress` at level 6" on a 2 MB heightmap payload. That Python was the system
   one, with zlib-ng; Blender's `encode_png` runs in Blender's Python, with zlib 1.3.1. On the review's payload
   (2,097,152 bytes): Blender's zlib 1,923,935 bytes, Deno and zlib-ng 1,941,671, Deno equal to zlib-ng and not to
   Blender. On a second payload made as `encode_png` makes one (`zlib_payload.py`, 2,098,176 bytes): Blender's zlib
   1,788,895, zlib-ng 1,809,363, Deno 1,809,370, equal to neither (`deflate_vs_zlib.mjs`, Deno 2.8.1). Byte identity
   would need a JavaScript port of zlib 1.3.1's deflate, a per-byte CPU loop that changes no landform. So PNGs are
   compared by their pixels, their filtered rows, IHDR and the sidecar (C9), and R32 and npz arrays byte for byte.
   Also, "keep Ekigar's reader" does not work: `png_read.js` inflates stored blocks only and throws on Huffman-coded
   deflate, which every Blender PNG is; `DecompressionStream` decodes both zlibs' bytes exactly (measured).
2. **Mesh heights within "4 ulp of |z|": no; within 14 ulp of the largest tap.** Measured on three 1024² fields
   (`mesh_f32_device.mjs`): on `alpine_valley` (116-2,828 m) the review's numbers hold (max 3 ulp). On a layered-rock
   field that crosses 0 m beside 70 m steps, 567 corners exceed 4 ulp of |z|, up to 43,780 (z = 5.7e-6 m beside a
   5.5 m tap: the error is the taps' rounding, the output is near zero); on a chalk coast at sea level, 47 corners, up
   to 3,072. Relative to the largest of the corner's 16 taps, every corner of all three is within 3 ulp, and the
   analytic bound of any f32 evaluation is 13.5. A test relative to the output would fail a correct port.
3. **Where the floor's perturbation enters: at both points, where I first chose one.** The review proposed nudging
   the outputs of every evolving op's kernels at the start of each op through a hook on `core/gpu.py`. I first
   preferred the op's entry alone (wrapping `get_op`), since it also reaches the ops that run in numpy (`compose`
   shapes, `dem`, `plateau`, the plans fed by fields) without a list of "evolving" kernels. Measured, the op's entry
   alone does not reach `dune_field`, which grows its field from its own start fields (RMS exactly 0 over three
   patterns), so the protocol uses both: the op's entry, and each kernel's outputs after its first dispatch in each op
   call (5.4, item 1); with both, the dunes move by 1.98-2.23 % of relief. The review was right that the dispatch
   point is needed. The same probe found that the solvers'
   per-process memos (`aeolian._TILES` and others) return a base run's result to a perturbed run in the same process,
   which neither the first protocol nor the review's probe cleared.
4. **Dispatch counts "exactly": except a loop that stops on a convergence test.** A one-ulp difference can move a
   convergence decision by one test interval in Blender against itself; requiring equal counts there would fail a
   correct port. Measured on `tower_karst`, the routing to convergence kept its count (2,688) under three patterns;
   the dune field's growth loop stops on a height-and-slip-face test every `grow_check` iterations (`grow_tile`), which
   is exactly the kind of loop a one-ulp difference can move by one interval (5.7).
5. **Ekigar's `nodes/masks.js` for the slope and aspect the shader derives: no.** It derives its masks by finite
   differences of a height texture's red channel, with its own conventions (its `slope`, `aspect`, `aspectEast`,
   curvatures). The surfacing design derives `slope`, `aspect`, `northness` and `eastness` in the shader from the bake's
   field normal (D), "with `masks.py`'s definitions (northness faded to 0 under 3 degrees)" (SURFACING_DESIGN.md
   2.2). Taking Ekigar's would substitute another definition for the source of truth's. The material ports
   `masks.py`'s definitions, reading D; Ekigar's `texture_arrays.js` and `ops.js` are the pieces that fit (3.5).
6. **One more change the review's own data asked for**: its f32 probe also measured the routing surface's `_descend`
   (82 ulp, 5 mm as a float32 relaxation; 1 ulp in the path-maximum form). That is C11.

### 10.2 Decisions for the lead

1. **The plant planner's parity grade.** Recommended: the GPU planner of 3.5, near-exact: the hashes and candidates
   bit-exact (splitmix64 as u32 pairs), decisions equal to Blender's except where a float64 comparison is a near-tie
   in f32, each such spot counted and traced (|u - p| below 2^-20 of p), positions within f32 rounding. The
   alternative, a JavaScript port with exact spots, is a per-candidate CPU loop over 10^5-10^6 candidates, against the
   edition's rule; a purely statistical grade (density, pair correlation) gives up the spot-for-spot comparison the
   saved spots files make possible.
2. **Orthophotos per mask bin** (SURFACING_DESIGN.md 3.1: NAIP, SWISSIMAGE) are the lead's to fetch, as reference
   data; if fetched, the port reads them in place like the DEMs (6.2).
3. **Seeds 3-4 of the distribution class:** run up front with the floor (12 more draft runs per recipe, about 48)
   or when a distribution-class recipe is first judged. I would run them up front, so no package waits on the queue.
4. **Commits and pushes** are the lead's; no package commits or pushes.

### 10.3 Open questions each package answers first, by a small experiment

- P14 and P17: sampling a `DataArrayTexture` layer with `.depth(level)` in TSL in a headless Deno render (Ekigar's
  surround bake does it in its own harness); the material's sampled textures staying at 16 or fewer; the memory of
  the D array at film quality.
- P15: indirect draws in three r184's WebGPU backend for the plant LOD pass; a per-frame readback is not an option
  (about 16 ms a sync, 4.5).
- P3: whether any recipe's floor samples sit near the 2 % boundary (5.4, item 6).

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
| `blender_chaos_floor.py` | the Blender edition's chaos floor, the first protocol (5.4) |
| `blender_floor_patterns.py` | the revised floor (every op perturbed at its entry and inside, the memos cleared, several patterns), the dispatch log and the step snapshots (5.4, 5.7) |
| `mesh_f32_prep.py`, `mesh_f32_device.mjs` | the mesh's float32 corner heights (plain and double-float) against Blender's, the lattice lines, the shader-module bypass, the adapter's limits (4.7, 7.3, 10.1) |
| `zlib_payload.py`, `deflate_vs_zlib.mjs` | a PNG payload as `encode_png` makes it, compressed by each Python's zlib, against Deno's `CompressionStream`, and `DecompressionStream` on each (C9, 10.1) |
| `results.json` | every number above, with notes on the noisy measurements |
| `results_revision.json` | the revision's numbers: the mesh and device probe, the zlib comparison, the PNG filters, both floor runs |

To re-run: `python eidoverse/terrain/tests/design_probes/make_twin_fixtures.py <dir>` (it finds the Blender edition
beside `eidoverse/` or at `$EIDO_BLENDER_EDITION`), then each `.mjs` with `deno run --no-config --no-lock
--unstable-webgpu --allow-all <probe> [args]`, and `bash run_blender.sh
eidoverse/terrain/tests/design_probes/blender_chaos_floor.py <out.json> [recipe ...]` from a Blender checkout; on a
shared machine, each behind `$EIDO_GPU_WRAP`. The revision's: `bash run_blender.sh
eidoverse/terrain/tests/design_probes/blender_floor_patterns.py -- <out.json> <patterns> <recipe> [...]`;
`<Blender's python> -I eidoverse/terrain/tests/design_probes/mesh_f32_prep.py <dir> <name>=<npz with h> [...]`, then
`deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/design_probes/mesh_f32_device.mjs
<dir>`.
