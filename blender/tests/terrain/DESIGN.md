# The new make_terrain: design

Blender edition (`blender/eidoblend/terrain/`), 2026-11-08. One design, for the agents who build it and the lead
who reviews it. It replaces both round one's noise `make_terrain` and the Ekigar port as the way the Blender edition
makes ground.

---

## 0. The design in one page

**The goal.** `make_terrain(recipe='alpine_valley', ...)` returns ground that reads as its name next to real
elevation data of that landform: a stratovolcano beside Mount Fuji, a canyon beside Toroweap, star dunes beside the
Namib. It has to hold up from an establishing aerial down to a character walking at 1.7 m eye height, under
`make_sky` daylight, at the level of World Machine and Gaea.

**The decisions.**

1. **Processes, not stamps.** Every landform comes from what makes it in nature, run on grids in metres and years:
   - rivers cutting into rising rock (stream-power incision);
   - hillslopes creeping, and failing at their threshold angle;
   - sediment settling in valley floors, fans and lakes;
   - ice carving troughs;
   - wind moving sand;
   - waves cutting cliffs back.

   Shapes built by geometry (a volcano's cone, a crater's bowl, karst towers) are only the starting surface that the
   processes then work on. Ekigar failed because every landform was a per-pixel function that knew nothing about where
   water goes (triage cause 1: 15-56 % of its tiles fill as closed lakes; real terrain 0.1-3 %).
2. **GPU compute shaders, with numpy twins as test oracles.** I measured Blender 5.2's compute shaders in headless
   Blender on this machine (section 1.2). One 3×3-neighbourhood pass costs 0.06 ms at 1024² and 0.23 ms at 2048²,
   3,400-9,700 times faster than the same pass in numpy. A whole coarse-to-fine stream-power run from 256² to 2048²
   took 5 s. Ekigar's plan counted compute shaders as missing in Blender and called that a blocker (its section 3);
   they work in Blender 5.2 here (the fx family's water solver and `harness/gpu_check.py` already dispatch them, and
   so did my probes). Every grid pass of a solver is a GLSL compute kernel; the few global or sequential steps
   (lakes, lava walkers, blue-noise points) stay in numpy. Each kernel has a numpy twin that runs at 64-128² in
   tests; the twins are not a production fallback.
3. **Nested levels around the shot.** No single grid serves both an aerial and an eye-level shot. A terrain is a
   stack of square windows (levels), each with the same cell count, each half its parent's size and twice as fine:
   - context levels for the horizon;
   - the main tile;
   - hero levels around the camera, down to 0.25-0.5 m cells.

   A level starts as its parent upsampled, keeps its border pinned to its parent, and is refined by the same
   processes at its own scale. The mesh is the same stack drawn as concentric rings, so vertex density falls off with
   distance from the camera.
4. **Recipes are data.** A recipe is an ordered list of stages (a process, its parameters in metres, years and
   degrees, and the levels it runs on) plus a few named knobs. It is not Ekigar's per-pixel node graph: that
   evaluator is the reason three chained thermals took 98 s at 128² (triage cause 9), and the Blender edition has no
   node editor to show a graph in.
5. **Masks come from the processes:** drainage area, eroded depth, deposit, talus, sand, snow, exposed rock. Geometry
   adds slope in degrees, aspect, and curvature at a scale in metres. The masks are written as point attributes on
   the ring mesh, and the material reads them.
6. **Judged against real terrain at the same pixel size.** Each recipe is generated at its reference's extent, and
   the field is box-averaged to the reference's pixel before measuring. The tests: slope percentiles, closed
   depressions, grid-direction bias, the power spectrum, and the landform's own numbers. Then come the three probe
   views beside the reference's three, a textured render, and at the end a review video.
7. **The old code goes; a few parts move into the new package first.** Ekigar's port, its tests and the old noise
   `make_terrain` are deleted at integration. These parts move into the new package before that:
   - Ekigar's analytic noise and tile snapping;
   - its hydrology (fill, routing, accumulation, horizon occlusion);
   - the mesh triangulation convention and `height_at`;
   - the height, angle and peaks masks;
   - the crater profile's structure;
   - the PNG16/R32 heightmap export;
   - from the old film material: de-tiling, `'Auto'` texture filtering and the height blend's normalisation.

---

## 1. What I worked from, and what I measured

### 1.1 Inputs (all in `blender/tests/terrain/`)

- `triage/`: 172 Ekigar subjects rendered and judged. Of 57 landforms, 2 are useful, 43 fixable and 12 broken. The
  causes that run through all of them:
  - nothing drains;
  - units are tile fractions, not metres;
  - Voronoi slicing;
  - stamps on flat planes;
  - cliffs one texel wide;
  - dead or inverted style options;
  - a wrong carried gradient;
  - a per-pixel evaluator that recomputes everything upstream for each neighbour.

  I looked at the compare sheets myself. Ekigar's alpine range is a field of needles; its volcano is a lumpy massif
  covered in dash-like gullies; its mesa is a cake on a plate; its star dunes are a honeycomb of crater cells.
- `research/research.md`: the process toolbox, the professional tools' pipelines and the stream-power prototypes. I
  adopt its recommendation (uplift + stream power + hillslopes as the backbone, then the family-specific process, then
  talus and deposition, then detail, with masks from the simulation) and change the solver platform (decision 2) and
  the multi-scale scheme (decision 3).
- `reference/`: 14 real elevation datasets with a numpy loader (`landform_refs.py`) and a Blender render rig
  (`render_references.render_probe`). I looked at the contact sheet and at the Lauterbrunnen, Toroweap, Badlands
  detail, Great Sand Dunes and Fuji renders. Toroweap's eye view shows what a canyon needs: horizontal benches, tall
  walls and talus slopes between them. Lauterbrunnen's shows a flat valley floor between sheer walls. At 8-40 m
  pixels every reference is smooth clay at 1.7 m, which is why the hero levels exist.

### 1.2 GPU throughput (my probe: `design_probes/gpu_bench.py`, numbers in `design_probes/results.json`)

Setup: RTX 5090 Laptop GPU, Blender 5.2.0 headless, OpenGL 4.6, `gpu.compute.dispatch`. The kernel does one
stream-power gather step: 8 neighbour reads, slopes, a drainage-area gather, incision and uplift. It reads one
RGBA32F 2D texture and writes another (ping-pong).

| grid | GPU per pass | Python issue cost per dispatch | readback RGBA32F | same pass in numpy |
|---|---|---|---|---|
| 512² | 0.016 ms | 0.005 ms | 7.6 ms | 55 ms |
| 1024² | 0.061 ms | 0.004 ms | 18.5 ms | 592 ms |
| 2048² | 0.23 ms | 0.010 ms | 148 ms | - |
| 4096² | 0.49 ms | 0.004 ms | 485 ms | - |

### 1.3 Stream power on the GPU (my probe: `design_probes/gpu_spl.py`; the sheets beside it)

I ported the research's gather scheme to three compute kernels (flow weights, area gather + incision + uplift,
nonlinear creep), then added a fourth (threshold relaxation). I ran it on a 20 km range with uplift up to 3 mm/yr.

| run | what | cost | slope p50 / p90 / p99 | closed depressions |
|---|---|---|---|---|
| direct 1024² | rough dome start, 8000 steps, no threshold pass | 1.2 s | 42 / 73 / 81° | 4.1 % |
| coarse-to-fine 256→1024, hillslope length shrunk per level | no threshold pass | 0.4 s | 53 / 73 / 78° | 2.6 % |
| direct 2048² | 16000 steps, no threshold pass | 12.8 s | 61 / 82 / 86° | 7.6 % |
| coarse-to-fine 256→2048 + threshold pass | hillslope length 45 m on every level | 4.8 s | 33.5 / 44 / 49° | 0.1 % |
| the same, hillslope length shrunk ×¼ per level below 512 | adds tributary gullies | 5.6 s | 41 / 49 / 53° | 0.4 % |

For comparison, the real Bernese Alps at 9.8 m give p50 29° and p99 66°.

What I take from them, as numbers and as an environment artist reading the hillshades:

1. **A threshold pass is required.** With creep alone (capped nonlinear creep), slopes run away as cells get finer:
   p99 81-86°, a field of blades. Four iterations per step of a mass-conserving threshold relaxation (section 4.1)
   bring the coarse-to-fine runs to p50 31-34° and p90 41-44°. A single 1024² level started from a dome stays
   steeper (p90 49°) and leaves an undissected plateau in its interior after 2 Myr, so the coarsest level is itself
   grown coarse-to-fine (section 2.2).
2. **Inputs must be functions of world position.** My first coarse-to-fine run regenerated its uplift noise per
   level (an FFT of a different size has different phases). Each level then saw a different range, and the centre
   came out as an undissected plateau with speckle. Uplift, erodibility and threshold must be evaluated from world
   metres at every level (decision 3).
3. **Cells per valley remove the grid combing; a cleverer slope estimate doesn't.** At 256² the research's ranges
   comb into straight ridges along the grid axes. I tried a direction-free slope estimate (the larger of the
   Rouy-Tourin upwind gradient and the steepest-descent slope), with contour-length flow weights and isotropic
   9-point creep. It changed nothing visible (`numpy256_slope_estimator_compare.png`). At 1024-2048² after a
   coarse-to-fine run, valleys curve and branch with no grid-direction preference.
4. **The backbone alone looks like plastic.** With a fixed hillslope length, threshold hillslopes are smooth planar
   facets between crease-sharp ridges and V-valleys. Shrinking the hillslope length on the fine levels adds small
   tributary gullies along the ridges (closer to real), but it steepens p50 to 41°, so the threshold has to be tuned
   with it. Every valley stays a V all the way to the outlet: there are no flats anywhere except at the map edge.
   Sediment deposition (section 4.1), talus, rock breakup and the hydraulic detail pass are what's missing, not
   optional polish.
5. **Cost is not a constraint any more.** Every stage in this design fits in seconds per level at 1024-2048². The
   budget goes to quality: more levels, more steps, more processes.

---

## 2. Architecture

### 2.1 Frames and units

- **Blender axes:** Z up, metres, XY in the ground plane.
- **Arrays:** `[row j, column i]` with row 0 the south edge. A cell centre is at
  `x = x0 + (i + 0.5) * cell`, `y = y0 + (j + 0.5) * cell`. The reference loader returns row 0 = north, so the judge
  flips it once on load.
- **Units in every public parameter:**
  - metres (heights, sizes, spacings);
  - years (durations);
  - degrees (angles; stored as their tangent inside the kernels);
  - m/yr (uplift, deposition);
  - m²/yr (creep diffusivity).

  The erodibility K is in the units the stream-power law makes it (`m^(1-2m)/yr`) and appears only inside recipes.
  Agents set knobs such as relief and valley spacing, and the recipe turns those into U, K and D.
- **Heights** are relative to base level (0 m at the outermost context edge or at sea level) plus
  `base_elevation_m`, which matters for the snowline, the glacier equilibrium line and the strata column.
- **Nothing is a fraction of the tile** (triage cause 2).

### 2.2 Levels

`plan_levels(size, resolution, centre, context, focus, hero)` returns a list of levels, coarsest first. Each level
is a square window `(x0, y0, side, cell, n)`.

- **Context levels.** `ceil(log2(context))` levels, each twice the size of the next, all centred on the tile
  centre. They give the horizon and carry the drainage past the main tile's edges, so the main tile has no artefact
  of water running straight to its edge.
- **The coarsest level grows coarse-to-fine on its own window.** Before its full-resolution run, it is solved at
  256², then 512², then its own cell count, each upsampled into the next. A single fine level started from a dome
  leaves an undissected plateau in its interior (my direct 1024² runs, section 1.3); the coarse pre-passes reach a
  branching network within seconds and the fine pass inherits it.
- **The main tile:** `size` metres at `resolution` cells (cell = size / resolution).
- **Hero levels.** Only when a `focus` (a point, a list of points or a camera path) is given. Each hero level is half
  its parent's side, but never smaller than the focus's bounding box plus a margin. Its cells are half its parent's
  and it is centred on the focus. Its window edges are snapped to its parent's grid lines and it stays
  inside its parent by at least the border band. Hero levels continue down to `hero_cell` (default 0.5 m; 0.25 m for
  close-ups). When the focus is large (a long walk), the cell count grows up to 2048, then the cell stops shrinking.
- **The border band** is 16 cells. There, a child's height, drainage area and sediment flux are pinned to its parent,
  upsampled with weights that ramp from 1 at the edge to 0 at 16 cells in. The child's drainage area at the border is
  the parent's, so rivers that enter the window carry their upstream catchment with them.
- **Defaults:**

  | quality | main cells | hero down to | stages |
  |---|---|---|---|
  | `draft` | 512 | no hero | fewer steps |
  | `film` | 1024 | 0.5 m | all |
  | `hero` | 2048 | 0.25 m | all |

- **Example.** An 8 km alpine valley, context 4, focus at a camera, film quality: 32 km at 31 m, 16 km at 15.6 m,
  8 km at 7.8 m (main), 4 km, 2 km, 1 km and 512 m at 0.5 m. That is seven levels of 1024².

### 2.3 Stages and recipes

```python
Stage(op='fluvial', params={...}, levels='all', where=None)
```

- **`levels`** is one of:
  - `'all'`;
  - `'first'` (the coarsest level);
  - `'context'`, `'main'`, `'hero'`;
  - `'cell>=30'` or `'cell<=2'` (by cell size in metres);
  - `'resolves:<metres>'`: the first level whose cell is at most 1/8 of that size, for a constructional shape.
- **`where`** is an optional mask expression that limits the stage to a region. Masks are combined with
  `* + - min max` and `smoothstep(a, b, mask)`.
- **`Recipe(name, title, references, defaults, knobs, stages)`.**
  - `defaults` holds size, resolution, context, hero cell and palette.
  - Each knob is `Knob(default, unit, range, doc, apply)`, where `apply(params)` writes derived stage parameters
    (for example valley spacing → D).
  - `recipe.to_dict()` is JSON, so an agent can print a recipe, copy it, change a stage and pass the dict back as
    `recipe=`.
- **Recipe modules** live in `terrain/recipes/`, one file per family. The registry imports every module in the
  folder and collects their `RECIPES`, so no package edits a shared list.

### 2.4 Fields

Each level holds named float32 arrays (`Fields`, a dict with the level attached):

| field | meaning |
|---|---|
| `h` | surface height |
| `bed` | top of rock; sediment, sand and talus thickness is `h - bed` |
| `A` | drainage area, m² |
| `qs` | sediment flux, m³/yr |
| `U`, `K`, `Sc` | uplift, erodibility, threshold slope (tangent) |
| `G` | deposition coefficient |
| `pin_w`, `pin_h` | Dirichlet pins: borders, sea, flatten areas |
| `wear`, `deposit`, `talus`, `sand`, `ice`, `lava`, `water` | accumulated outputs that become masks |

Ops read and write fields by name. A child level starts from its parent's fields:
- Catmull-Rom ×2, cell-centred, for `h` and `bed`;
- bilinear for the masks;
- `U`, `K` and `Sc` are never upsampled: they are re-evaluated from world-space functions at the child's cells.

### 2.5 GPU runner and kernels

`core/gpu.py` follows the pattern of `eidoblend/fx/_gpu.py`; the family contract keeps families self-contained, so I
copy the pattern, not the import. It provides:
- `gpu.init()` in background mode;
- RGBA32F 2D textures from numpy and back;
- a kernel cache keyed by source hash;
- `run(kernel, groups, samplers, images, uniforms)`;
- ping-pong pairs, and readback.

The kernels:
- are `.glsl` files in `terrain/kernels/`, each prefixed with `common.glsl`. It holds the 8-neighbour offset and
  length tables, the isotropic 9-point weights, `inside()`, the boundary modes (open / periodic / pinned) and a
  32-bit PCG hash;
- use a 16×16 local size;
- bind every input as a sampler (`texelFetch`, no filtering) and every output as an `image2D`.

Each kernel has a numpy twin in `core/twins.py`: the same arithmetic in float32 with array shifts. The parity test
runs one dispatch against its twin on a non-square random field (96×80, so axis mix-ups fail) with pins and
boundaries, and passes at `max |gpu - twin| <= 1e-4 × field range`. Multi-step runs diverge chaotically, so those
are compared by metrics, not texels.

The runner fails loudly without compute support; there is no CPU path in production. Kernel compilation is cached
per process, so the first `make_terrain` in a Blender process pays each kernel's compile once (not yet measured per
kernel; the core package records it).

### 2.6 Cache

The key is a SHA-1 of the recipe dict, knobs, size, resolution, seed, level plan, focus and `TERRAIN_CODE_VERSION`
(bumped whenever a kernel or op changes its output). Each level's fields go to
`eidoverse/assets/cache/terrain/<key>/level_<i>.npz` (that folder is already gitignored) with a `meta.json`. A cache
hit loads the fields and builds the mesh. GPU results are deterministic on one machine (gathers only, no atomics);
across GPUs they can differ in the last bits, so the cache is per machine and tests compare metrics, not bytes.

### 2.7 Package layout (new)

```
blender/eidoblend/terrain/
  __init__.py          make_terrain, Terrain, recipes, describe, terrain_height_at  (+ layer_surface etc., unchanged)
  api.py               make_terrain, Terrain, MaskSet, describe, recipes, viewpoint helper
  bake.py              CLI: bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe ... (cache + preview)
  run.py               the level runner: plan -> per level: inherit, pins, inputs, stages, readback, cache
  masks.py             every mask (section 6)
  core/  grid.py levels.py fields.py world_noise.py gpu.py twins.py cache.py io.py metrics.py compose.py
  kernels/  common.glsl + one .glsl per pass
  solvers/  fluvial.py hillslope.py hydro.py hydraulic.py glacial.py aeolian.py volcanic.py impact.py strata.py
            rivers.py karst.py coast.py detail.py
  recipes/  __init__.py (registry) + one module per family
  build/    mesh.py surfacing.py palettes.py dressing.py water.py
  surface_layers.py relief.py loft.py _pbr.py _nodes.py      (kept as they are: tools for built geometry)
```

---

## 3. What happens to Ekigar's port and the old make_terrain

| part | what happens | where it goes / why |
|---|---|---|
| `ekigar/noise.py` (hash2, noised, fractal_noise, wrap_cell), `field_cpu.snap_freq` | **move** | `core/world_noise.py`, evaluated in world metres; frequency snapping kept for periodic tiles (dunes) |
| `ekigar/hydrology.py` (fill_depressions, route, accumulate, horizon_occlusion, box_blur, flat_average) | **move** | `solvers/hydro.py`: lakes, the drainage check, routed masks; the triage found its fill and routing accurate |
| `ekigar/mesh.py` quad convention, wrap seam row, point attributes; `Heightfield.height_at` | **move, rewritten** | `build/mesh.py`; the new mesh writes triangles explicitly, so the split never depends on Blender's tessellation |
| `ekigar/mesh.py` `build_lake_mesh` | **move** | `build/water.py` |
| heightMask, angleMask, peaksMask | **move** | `masks.py` (`height`, `aspect`, `peaks`), in metres and degrees on the final height |
| impactCrater's structure (lobate rim, flat floor, central peak) | **move, rebuilt** | `solvers/impact.py` with Pike's numbers in metres |
| planationSurface (knobs on a pediment plain) | **move, rebuilt** | a `planation` stage in `solvers/detail.py` for desert plains (a later recipe) |
| `ekigar/export.py` PNG16/R32 encode/decode | **move** | `core/io.py`: export heightmaps and masks for other tools |
| Phacelle filter | **move, demoted** | an optional detail octave in `solvers/detail.py`, steered by the routed flow direction instead of its own gradient |
| graph/project model, compiler, registry, all `ops_*`, landforms waves 1-4, landform_shared, local_area, display_grid, examples, api, terrain.Heightfield | **delete at integration** | replaced by stages, levels, ring mesh and `Terrain`; per-pixel evaluation is the cost problem, the landforms are the quality problem |
| old `make_terrain` (`heightfield.py`, `_noise.py`) | **delete at integration** | its film material's de-tiling switch, `'Auto'` interpolation, height-blend normalisation (`_height_stats`) and macro/damp variation move to `build/surfacing.py` |
| `surface_layers.py`, `relief.py`, `loft.py`, `_pbr.py`, `_nodes.py` | **keep** | tools for built geometry and shared node helpers |
| `tests/terrain_ekigar/`, `tests/terrain/test_parity.py`, `parity_dump.mjs`, the old-heightfield parts of `tests/terrain/_fixture.py` | **delete at integration** | the parity tests prove fidelity to code we are replacing |
| `tests/terrain/shimmer_metric.py` and the shimmer probe in `test_meadow.py` | **move** | `tests/terrain/surfacing/`: the texture-filtering measurement still matters |

Ekigar's own repository on the Desktop is untouched. The deletions follow the house rule for superseded tools: the
code goes, git history keeps it.

---

## 4. The solvers

Each entry gives the physics, the discrete method, the kernels, the parameters with defaults, and the failure
modes to look for.

### 4.1 Fluvial backbone: uplift, stream power, creep, threshold, sediment (`solvers/fluvial.py`, `hillslope.py`)

**Physics.** `dh/dt = U - K A^m S^n + G qs / A + creep + threshold failure`:
- `m = 0.5`, `n = 1`;
- `qs` is the sediment flux arriving from upstream (the Yuan et al. 2019 deposition term; JGR Earth Surface 124, an
  extension of the Braun & Willett solver; its `G` is dimensionless: 0 for pure bedrock incision, about 1 for
  alluvial floors);
- creep is Roering et al. 1999's nonlinear law;
- threshold failure keeps slopes at or under `Sc`.

**Per step (`dt` years), four passes, as in my probe:**

1. `flow_weights`: `wsum = Σ_k max(s_k, 0)^p`, where `s_k = (h - h_k) / (L_k · cell)` and `p = 1`.
2. `route_incise`:
   - `A = cell² + Σ_{h_k > h} A_k · w_{k→c} + A_in` (border pins);
   - `qs_in = Σ qs_k · w_{k→c}`;
   - `S` = the steepest downhill slope;
   - `E = K A^m S^n`;
   - `Dp = G qs_in / A`;
   - `h' = max(h - dt E, min(h_low, h)) + dt (U + Dp)`, with `h_low` the lowest neighbour;
   - `qs_out = qs_in + (E - Dp) · cell²`.

   One Jacobi iteration of the routing per step; the area lags the terrain by a step, which the slow terrain tolerates.
3. `creep`: flux to all 8 neighbours with the isotropic weights (2/3 sides, 1/6 diagonals) and the factor
   `min(1 / (1 - (s/Sc)²), cap)`, cap 5. Sub-stepped so `dt_sub <= 0.9 cell² / (3.4 D cap)`.
4. `threshold` (4 iterations per step): for each neighbour pair,
   `Δh = -sign(h - h_k) · rate · max(|h - h_k| - Sc_pair · L_k · cell, 0)`, with `rate = 0.06`. The exchange is
   symmetric, so mass is conserved; the moved material lands where the rivers carry it away. `Sc_pair` is the mean
   of the two cells' `Sc`, or the strata composite (section 4.9). It also accumulates `talus` (the height each cell
   gained).

**Parameters per level:**
- `dt` = 1000 yr × (cell / 78 m).
- The coarsest level (with its coarse-to-fine pre-passes) runs to near steady state, about 2 Myr. The finer levels
  run 0.25-0.5 Myr each, 1000-2000 steps.
- `D` comes from the valley-spacing knob: `D = K · (spacing / 6.5)²`. That is the research's measured ratio (valleys
  every 4-6 cells at √(D/K) = 45-70 m and 78 m cells); the fluvial package re-calibrates it against the spectrum
  peak.
- Below the main level, `D` shrinks ×¼ per level when the recipe asks for gullies, and `Sc` is re-tuned with it
  (finding 4).

**Knobs:**
- `relief_m` drives a controller on the coarsest level: every 200 steps it reads back `h`, measures p99.5 above base,
  and scales `U` by `(target / current)^0.5`, clamped to 0.8-1.25.
- `valley_spacing_m` (default 400).
- `threshold_deg` (default 35, ±15 % noise at a 400 m scale).
- `age_myr`.
- `roughness`: erodibility noise `K · (1 + a·noise)` at 2 km, 300 m and 50 m scales, amplitude 0.6 (the research's
  run J was its most natural).
- `deposition` (`G`, default 0.5).
- `uplift`: a `core/compose.py` shape; one of ridge spine + spurs, dome, plateau, massif, or a painted array. It is
  always evaluated in world space, with multi-scale texture and no creases (the research saw an edge fade's creases
  print straight divides).
- `start`: the uplift shape scaled to a rough 600 m surface. A flat start makes corduroy for millions of years.

**Boundaries:**
- the outermost context edge is base level;
- sea cells (`h <= sea_level`) are base level;
- inner levels are pinned to their parent;
- flatten areas are rigid blocks (`U = K = 0`) during erosion and flattened exactly afterwards (section 4.13), so
  rivers route around them or fill against them instead of being dammed by a pinned plate.

**After the last step:**
- run `route` (area only) to convergence (stop when the largest relative change is under 1e-4, checked every 128
  iterations) for the masks;
- fill and record lakes (section 4.3);
- `wear = h_inherited - h_final` (positive part);
- `deposit` = the accumulated `Dp · dt`.

**Failure modes and their checks:**

| failure | check |
|---|---|
| plastic facets | the eye and aerial look; the spectrum has no power below the valley scale |
| combing along grid axes | the anisotropy test (section 10) |
| an undissected plateau | the coarse level is not at steady state; check that relief stopped rising |
| spokes at the base-level edge | only allowed in the outer context ring |
| runaway slopes | p99 above the reference band |
| pits | closed depressions above 0.5 % |

### 4.2 Talus and hillslopes on their own (`solvers/hillslope.py`)

- The same `threshold` and `creep` kernels as standalone stages:
  - `talus` (repose 33-37°, acting only on loose material `h - bed > 0`, or with a hardness field);
  - `creep` (age a surface: linear diffusion with `κ·t` in m², for cinder cones and craters).
- Rock walls keep their own `Sc` (60-85°). The repose angle applies to the debris.
- `talus` thickness feeds the scree mask and the rock-scatter density.

### 4.3 Hydrology (`solvers/hydro.py`)

- **Lakes and the drainage check:** the moved Ekigar `fill_depressions` (exact, via the basin graph; fast when there
  are few basins, as on eroded terrain) on the CPU. A depression deeper than `max(1 m, 0.2 % of relief)` becomes a
  lake (flat water at its spill level, `water` field, lake mesh) unless the recipe fills it with sediment
  (`fill='sediment'`: flat floors, glacial overdeepenings, caldera floors).
- **Drainage area:** the GPU route pass to convergence.
- **The masks on it:** wetness, channels, moisture (section 6).

### 4.4 Hydraulic detail (`solvers/hydraulic.py`)

- **The method:** the virtual-pipe shallow-water model (Mei, Decaudin & Hu 2007; Jako 2011), all local passes:
  1. rain;
  2. outflow flux through 4 pipes;
  3. water depth and velocity;
  4. capacity `C = Kc · sinα · |v|`;
  5. erosion `Ks (C - s)` or deposition `Kd (s - C)`;
  6. semi-Lagrangian sediment advection;
  7. evaporation;
  8. a thermal pass.
- **Jako's values:** dt 0.02, rain 0.012, Ks 0.5, Kd 1, Ke 0.015, Kc 1. They are scaled with the cell size.
- **When it runs:** on the hero levels (0.25-4 m cells) for 2,000-5,000 steps. It gives rain rills, small sediment
  fans and the wet/dry pattern on the ground near the camera.
- **It is not the backbone.** It can't build a valley network in any affordable time.

### 4.5 Glacial (`solvers/glacial.py`)

A procedural carve guided by the fluvial network. The research shows the cheap ice physics (the shallow-ice
approximation) carves narrow defiles, not U-valleys.

1. **Ice discharge.** Mass balance `b(z) = clamp(β (z - ELA), -b_abl, b_acc)`, with β 0.005/yr, b_acc 2 m/yr,
   b_abl 6 m/yr. It is routed down the same flow weights as water: `Q_ice = max(0, b · cell² + Σ upstream Q_ice)`,
   iterated to convergence. The terminus is where `Q_ice` falls to 0.
2. **Centrelines.** Glaciated channel cells (`Q_ice > 0` and drainage area above the channel threshold).
3. **Jump flooding** (Rong & Tan 2006, log2 N passes) gives every cell its nearest and second-nearest centreline
   seed.
4. **U-carve.** Each seed has `depth = c_d (Q/Q_ref)^0.4` and `W = c_w (Q/Q_ref)^0.4` (my starting exponents; tune
   them against Lauterbrunnen and Yosemite trough widths and depths). The target bed is
   `z_floor + depth · (r/W)²` for `r < W`; the two nearest seeds' targets are combined by smooth minimum, so no
   creases where regions meet; then `h = min(h, target)`. Trunks carve deeper than tributaries, so tributary floors
   hang. Depth grows with discharge, not with the downstream floor, so overdeepened basins appear.
5. **Cirques.** At glacier heads within 300 m of the ELA: a bowl elongated down-glacier, its floor at ELA - 50 m,
   radius 400-800 m, headwall exponent 3, merged by smooth minimum. Walls between cirques become arêtes; where three
   or more cirques meet, a horn remains.
6. **Fresh walls** get `Sc` 60-70° (the threshold pass), so they stay steep.
7. **Afterwards:**
   - valley fill: overdeepenings filled with sediment to flat floors, or kept as lakes;
   - talus aprons at 35° on the debris;
   - lateral and terminal moraines: ridges 10-50 m high along the ice outline;
   - an optional cap on peaks at ELA + 1500 m (the glacial buzzsaw).
8. **Hero levels:** couloirs on the walls (erodibility noise plus hydraulic detail) with talus cones at their exits;
   a snow mask.

**Failure modes:**
- flat slots with vertical walls (Ekigar's trough);
- every valley the same width;
- tributaries graded to the trunk;
- troughs that ignore the drainage;
- creases;
- no talus, lakes or moraines.

### 4.6 Wind and sand (`solvers/aeolian.py`)

Werner's slab model (Werner 1995) with the Desertscapes numbers (Paris et al. 2019), on two layers (`bed`, `sand`),
written as gathers so it runs on the GPU.

**One iteration:**
1. **Activation.** A random 5-10 % of cells with sand (a PCG hash of cell and iteration) lift one slab.
2. **Shadow pass.** A cell is in shadow if any upwind cell within 20 cells rises above a 15° line from it.
3. **Transport, as a gather.** Each slab hops `L` cells along the wind. The hop vector is dithered per source cell
   between the two nearest integer vectors, so any wind direction works on average and crests don't lock to the
   grid. It deposits with probability 0.6 on sand, 0.4 on bare rock, or 1 in shadow, and makes up to 3 hops. A cell
   receives a slab from source `x - k·v` when that source chose `v`, lifted a slab, didn't deposit at hops `< k` and
   deposits at hop `k`. Every decision is a hash of (source, iteration, hop), so the gathering cell can evaluate it.
4. **Avalanche.** The threshold kernel on the sand layer at tan 0.60 (31°, the Desertscapes value), rock at tan 2.5.

**Wind regime:** a list of `(direction_deg, weight)` cycled in blocks of 200 iterations:

| dune type | wind | sand |
|---|---|---|
| barchan | one direction | thin sand |
| transverse | one direction | thick sand |
| linear | two directions more than 90° apart | any |
| star | three or more directions of similar weight | any |

(After Rubin & Hunter 1987, Courrech du Pont 2014 and Zhang 2012.)

**Scale.** Dunes coarsen slowly in Werner's model. Seed the sand surface with smooth world-space noise at the target
spacing (amplitude 10-20 % of the target height). Run until the spectrum's peak wavelength reaches the target, or up
to an iteration cap. Then a short run on the hero levels makes the small dunes on the big ones' flanks. Ripples
belong in the material.

**Periodic tiles** are allowed here: the frequencies snap to the tile.

**Failure modes:**
- symmetric profiles (no shadow rule);
- grid-aligned crests;
- noise blobs;
- slip faces above 34°;
- no interdune flats or exposed rock;
- one dune size.

### 4.7 Volcanoes (`solvers/volcanic.py`)

- **Stratovolcano profile.** An exponential cone:

  `z(r) = H · (e^{-(r - r_c)/λ} - e^{-(R - r_c)/λ}) / (1 - e^{-(R - r_c)/λ})`, with `λ = H / tan(upper_slope)`.

  With `H` 3700 m, upper slope 33° and `R` 18 km, this gives Fuji's steady fall from about 30° near the summit to
  about 2° at the foot (tan θ = (H/λ) e^{-r/λ}: 33° at the rim, 6.6° at 10 km, 2.8° at 15 km). A log + linear profile
  is the option for upper flanks that are straight rather than concave (Karátson et al. 2010). Azimuthal asymmetry:
  `R` and `H` modulated by low-frequency noise and an elongation along a rift axis.
- **Summit crater:** a bowl of radius `r_c` (default 0.03 R) and depth 0.4 r_c. Optional flank craters (Fuji's Hoei
  crater). An optional horseshoe breach (sector collapse).
- **Parasitic cones:** cinder-cone profiles (below) along the rift axis.
- **Growth and erosion.**
  - Growth: an uplift-like constructional term near the vent while the fluvial stage erodes for `age_kyr`.
  - Young (10-100 kyr): fine radial gullies.
  - Old (0.5-2 Myr): deep radial valleys with smooth ribs between them (planèzes).
- **Lava flows** (the DOWNFLOW idea, Favalli et al. 2005), on the CPU:
  - N stochastic steepest-descent walkers from each vent, vectorised over walkers; each step picks the steepest
    neighbour of `h + U(-Δh, Δh)`;
  - visit counts give a footprint probability;
  - the flow is `thickness · smoothstep` inside the footprint, with levées (+30 % at the margins) and a lobate front;
  - written into `h` and the `lava` field at the level where the flow is at least 4 cells wide.
- **Apron:** the deposition term at the foot (`G` higher where slope drops), forming fans and a debris apron.
- **Cinder cones** (Wood 1980 / Porter 1972):
  - height / basal width 0.18, crater / basal width 0.40;
  - flanks at the 30-33° repose, with a concave toe;
  - the crater bowl's walls at 30°;
  - aged by linear creep with `κ·t` (fresh: 0; old cones: several thousand m²) and a lower H/W;
  - optional breach with a lava flow from the base, as SP Crater has.
- **Calderas:**
  1. build and erode the edifice;
  2. collapse inside a ring fault (a scalloped ring: radius modulated by noise plus 4-8 scallops), lowering the
     inside to the floor depth;
  3. walls thresholded at 40-45° with talus below;
  4. the floor filled flat with sediment, or a lake to a level;
  5. an optional cone inside (Crater Lake's Wizard Island);
  6. the outer flanks keep their eroded valleys.

**Failure modes:**
- perfect symmetry;
- equal-depth gullies all round;
- the same bumps everywhere (Ekigar);
- a donut crater;
- no apron or flows;
- shield profiles steeper than strato (Ekigar's inversion).

### 4.8 Impact craters (`solvers/impact.py`)

- **Simple craters** (Pike 1977, as quoted by Holsapple 2022):
  - depth 0.2 D and rim height 0.036 D when fresh;
  - a parabolic bowl with a flat floor where infilled (Meteor Crater: rim to floor 0.14 D);
  - the rim crest a smooth peak at r = R;
  - ejecta thickness `h_rim · (r/R)^-3` out to 2-3 R, with hummocks and blocks (noise decaying with r) and faint
    rays;
  - a polygonal planform (4-6 sides from joint sets: Meteor Crater is nearly square);
  - rim height varying with azimuth.
- **Complex craters:**
  - depth `1.044 D^0.301` km, rim `0.236 D^0.399` km;
  - floor width `0.187 D^1.249` km above 20 km;
  - a central peak;
  - slumped terraces as irregular arcs, not rings;
  - the transition diameter scales with 1/g (a few km on Earth).
- **Aging:** creep `κ·t`, gullies on the inner walls (the fluvial stage with the crater as a closed basin), and the
  floor filled flat.
- **Failure modes:** a flat-ring donut with a dome; no ejecta; a perfect circle; the wrong depth for its diameter.

### 4.9 Layered rock (`solvers/strata.py`)

- **The column.** A stratigraphic column in world z: `[(thickness_m, K_factor, Sc_deg, colour_id, name), ...]`,
  with dip (degrees, azimuth), a warp (world noise, metres) and optional faults (offsets along lines). Stratigraphic
  height is `zs = z - tan(dip) · (x cos az + y sin az) - warp(x, y)`.
- **Erodibility.** `K(zs)` multiplies `K` in `route_incise`: a 1D texture of the column, sampled at each cell's
  current height. As the surface cuts down, it meets new layers.
- **The composite threshold** (my rule for stepped cliff-and-slope profiles). Between two cells at heights z1 < z2,
  each layer in between stands at its own angle. The pair can be no steeper than `Δz / (R(zs2) - R(zs1))`, where
  `R(zs) = ∫ dz / tan θ(z)` is the horizontal run of the column, tabulated at 0.5 m in a 1D texture. The threshold
  pass uses that limit instead of `Sc_pair`.
  - When a weak layer under a cliff is cut back, the pair's span takes in more weak rock and its limit drops, so the
    cliff fails and retreats.
  - Strong layers stand at 60-85°, weak ones at 25-35°.
  - The debris (`talus`) rests at 33-37° on the weak benches.
- **Headward growth.** Base-level fall at an outlet (a river leaving the tile) drives canyon cutting headward, with
  tributaries.
- **Mesas, buttes and spires** remain where the caprock is cut through. Stop at a target caprock fraction.
- **Columns shipped:**

  | column | layers |
  |---|---|
  | `colorado_plateau` | Kaibab cliff, Toroweap ledges, Coconino cliff, Hermit slope, Supai ledges (Esplanade bench), Redwall cliff, Muav/Bright Angel slope, Tapeats ledge, Vishnu inner gorge |
  | `monument_valley` | Shinarump cap, Moenkopi slope, De Chelly cliff 250 m, Organ Rock slope, Cedar Mesa bench |
  | `badlands` | Brule banded mudstone with thin sandstone and ash ledges, over Chadron clay |
  | `chalk` | uniform strong chalk with flint bands (bands are material only) |
  | `limestone` | |
  | `granite` | massive, with joint sets as erodibility noise |

  Thicknesses from the geology literature; check them against the Toroweap and Monument Valley wall profiles.
- **Colour bands** come from the same column in the material, in world space (section 7), so the bands sit on the
  layers that make the benches.
- **Failure modes:**
  - terraces that follow contours (Ekigar's strata, terrace and stratify);
  - level bands with no dip;
  - canyons with no tributaries;
  - no talus;
  - cliff bands thinner than 2-3 cells (stair-step aliasing): the hero levels resolve them.

### 4.10 Karst towers (`solvers/karst.py`)

- **Centres.** Blue-noise (Poisson-disc, on the CPU) centres with cluster modulation; spacing 200-400 m.
- **Each tower:**
  - height lognormal (median 120 m);
  - footprint radius 0.3-0.6 × height, modulated by azimuthal noise;
  - profile `z = H (1 - (r/R)^p)^(1/q)`, with `p` 6-12 for 70-85° walls and `q` about 2 for rounded tops;
  - irregular summits (noise);
  - a steepened foot standing in for the undercut notch (a heightfield can't overhang; the notch's dark band goes in
    the material).
- **Composition.** The towers are combined by max.
  - Fenglin (isolated towers): a flat alluvial plain with a river (`solvers/rivers.py`).
  - Fengcong (clustered cones): a raised common base 50-150 m with star-shaped dolines left unfilled. This is the
    one family where closed depressions are correct.
- **Then:** the threshold pass at limestone `Sc` 75° and light creep. On the hero levels: vertical fluting from
  erodibility noise stretched along z.
- **Failure modes:** smooth noise cones; regular spacing; equal heights; walls under 60°; no plain.

### 4.11 Coasts (`solvers/coast.py`)

1. **Sea level.** Cells at or below sea level are sea (base level).
2. **Distance to the shore** by jump flooding.
3. **Exposure:** the mean open-water fetch over 16 directions (a ray-march pass over the sea mask, up to 20 km),
   normalised.
4. **Retreat distance** = exposure × rock weakness × age. Land within it is cut to a platform at -1 to +1 m with a
   slight seaward slope; the cliff stands at the retreat line, as high as the land there; the threshold pass at the
   rock's `Sc` (chalk 80-85°, layered shale and sandstone with the strata composite); boulders and talus at the toe.
5. **Beaches** in low-exposure bays: the Dean profile `h = A y^(2/3)` below water (A 0.1 m^(1/3) for sand), with a
   berm above.
6. **Stacks** are left where retreat from two sides isolates a headland.
7. **Land behind:**
   - Seven Sisters: rolling chalk downland with dry valleys, so the cliff top rises and falls along the shore;
   - Moher: a layered plateau.
8. **Hero levels:** cliff-face bands (strata) and a notch at the waterline in the material.

### 4.12 Detail (`solvers/detail.py`)

- **Rock breakup.** Erodibility and threshold noise at 50, 15 and 5 m scales, plus joint sets (oriented line noise,
  2-3 directions). Applied to `K` and `Sc` on the hero levels, it turns planar threshold slopes into buttresses,
  ribs and couloirs.
- **Gully octave.** The Phacelle filter, moved from Ekigar, steered by the routed flow direction (the converged MFD
  vector) instead of its own gradient. Masked to soil-mantled slopes between 10° and 35°; amplitude in metres.
- **`planation`.** A pediment plain with residual knobs (inselbergs) for desert recipes, from Ekigar's
  planationSurface idea.
- **Below 0.25 m,** detail belongs to the material and to scattered rocks, not to the heightfield.

### 4.13 Composition ops (`core/compose.py`, `solvers/rivers.py`)

- **`stamp`.** Apply a world-space shape (cone, bowl, profile function, array) with a mode:
  - `add`, `max`, `min`;
  - `smooth_max` / `smooth_min` (smoothing width in metres);
  - `blend` by mask.
- **`flatten`.**
  - During erosion: a rigid block with `U = K = 0`.
  - After the last level: exact flattening to the target height (default: the area's median) with a C1 falloff of
    `falloff` metres. The resolved heights are recorded in `Terrain.flats`.
- **`river_path`.** A river course given as a polyline, or generated (a Kinoshita meander curve for incised
  meanders, or a smoothed random walk). It is carved as a base-level line: pinned low with a slope along it, so the
  fluvial stage builds the valley around it.
- **`paths`** (later). Graded trails and roads carved after erosion, with cut-and-fill and a drainage culvert rule.

---

## 5. The recipes

Defaults are for film quality. Sizes are the main tile; context is its multiple. Every recipe also runs the generic
end stages: route to convergence, lakes, masks.

| recipe | what it makes | stages, in order (levels) | key knobs (defaults) | judged against |
|---|---|---|---|---|
| `fluvial_range` | a mountain range carved by rivers, threshold hillslopes, branching valleys, alluvial floors | uplift ridge + spurs (all) → fluvial with threshold and sediment (all; hillslope length shrinks below main) → rock breakup + hydraulic detail (hero) | size 12 km, context 4, relief 2000 m, valley spacing 400 m, threshold 35°, age 2 Myr, deposition 0.5 | **to add:** the San Gabriel Mountains (USGS 3DEP 1 m; a well-studied river-carved range) and a crop of the river-carved mountains in `mount_fuji_context` (Misaka/Tanzawa); slope statistics also against the triage's Bernese Alps |
| `alpine_valley` | a glacial U-valley with a flat floor, sheer walls, hanging side valleys, cirques, arêtes and horns, talus | fluvial range (all, relief 3000 m) → glacial carve (levels with cell ≤ 40 m) → valley fill + lakes → talus → moraines → couloirs, talus cones, rock breakup (hero) → snow mask | size 8 km, base elevation 800 m, ELA 2400 m, trough width 1.2 km, wall threshold 65° | `lauterbrunnen` (8 km at 8 m); **to add:** Yosemite Valley at 3DEP 1 m |
| `stratovolcano` | an exponential cone with a summit crater, radial gullies, parasitic cones on a rift, lava flows, a debris apron | low fluvial surroundings (context, main) → cone + crater + rift cones (resolves: 2 km) → growth + fluvial for the age (all) → lava flows → apron deposition → lakes | size 40 km, context 3, H 3700 m, R 18 km, upper slope 33°, age 100 kyr | `mount_fuji` (40 km at 40 m) |
| `caldera` | an eroded edifice with a scalloped collapse caldera, talus walls, a flat floor or lake, an optional inner cone | stratovolcano (age 400 kyr) → ring-fault collapse → wall threshold 42° + talus → floor fill / lake → inner cinder cone | size 14 km, caldera 9 km, floor depth 1200 m, lake level -300 m below rim | `crater_lake` (14 km at 14 m) |
| `cinder_cones` | a field of cinder cones at repose, of mixed ages, some breached with flows, on a lava plateau | plateau (all) → cones by blue noise along vent lines (resolves: 300 m) → creep aging per cone → breaches + lava flows | size 8 km, count 12, H 60-250 m, age 0-500 kyr | **to add:** SP Crater (3DEP 1 m; the triage fetched it from Terrain Tiles) |
| `impact_crater` | a simple bowl crater: square-ish rim, infilled floor, hummocky ejecta; complex as an option | layered plateau (`colorado_plateau` top layers) → crater stamp (resolves: D) → aging: creep + wall gullies + floor fill → talus (hero) | D 1.2 km, rim 0.04 D, depth 0.15 D, sides 4, age 50 kyr | `meteor_crater` (3 km at 3 m) |
| `canyon` | a canyon in layered plateau rock: stepped cliffs and benches, tributaries, an inner gorge | plateau tilted 1° (all) → strata column → river path + base-level fall → fluvial with K(z) and the composite threshold (all) → talus → ledges, rock breakup (hero) | size 8 km, column `colorado_plateau`, depth 1400 m, dip 1° | `grand_canyon_toroweap` (8 km at 8 m) |
| `incised_meanders` | an entrenched meandering canyon | `canyon` with a Kinoshita river path | sinuosity 2.5 | **to add:** Goosenecks of the San Juan (3DEP 1 m) |
| `mesas_buttes` | flat caprock remnants, cliffs over talus slopes, a flat desert floor | plateau + column `monument_valley` → fluvial with base-level fall until the caprock fraction hits the target → talus → floor deposition → joint-guided spires (hero) | size 8 km, caprock fraction 6 % | `monument_valley` (8 km at 8 m) |
| `badlands` | dense rills and knife-edge ridges in soft banded rock, a sediment apron at the foot | plateau edge + column `badlands` → fluvial at fine cells (high K, √(D/K) ≈ 1.5 cells, threshold 42°, base-level fall) → hydraulic rills (hero) | size 3 km, relief 140 m | `badlands_sd` (3 km at 3 m), `badlands_sd_detail` (1.2 km at 1.2 m) |
| `dunes` (star by default) | dunes from wind regime and sand supply: star; barchan, transverse or linear via `kind=` | bedrock (all) → sand layer + seed at target spacing → wind slab model to the target spacing (main) → small dunes on the big ones (hero) | star: winds 0°/120°/240° equal, sand 120 m, spacing 900 m | `namib_star_dunes` (8 km at 10 m), `great_sand_dunes` (5 km at 5 m); **to add:** barchans, transverse and linear dunes (White Sands, the Namib linear dunes) |
| `tower_karst` | fenglin (towers on a river plain) or fengcong (cones over dolines) | alluvial plain + river path → towers (resolves: 200 m) → threshold 75° + light creep → fluting (hero) | size 8 km, spacing 300 m, median H 120 m, kind fenglin | `guilin_karst` (8 km at 8 m from 30 m radar data: soft; take wall angles from photographs) |
| `sea_cliffs` | sea cliffs on headlands, a wave-cut platform, beaches in bays, stacks | land recipe (`rolling_hills` chalk or a layered plateau) → sea level → exposure + retreat + cliffs + talus → Dean beaches → cliff bands (hero) | size 6 km, sea level 0, retreat 300 m, rock chalk | `seven_sisters` (2 m lidar), `cliffs_of_moher` |
| `rolling_hills` | soil-mantled rolling hills with convex tops and dense dendritic drainage | uplift plateau, low U/K → fluvial with large √(D/K) (creep dominates, threshold never reached) → slope asymmetry option | size 4 km, relief 120 m, valley spacing 250 m | `palouse_hills` (4 km at 4 m) |
| `meadow` | small-scale gentle ground with hummocks and rills, for the meadow-film use of the old `make_terrain` | `rolling_hills` at 80-400 m with relief 2-8 m → hydraulic rills → soil hummocks (hero) → `flatten` clearing | size 160 m, relief 4 m | no elevation reference at that scale: the old meadow probe's framing, slope p99 < 15°, no pits; judged by the look with grass |
| `real_place` | real elevation data as the main tile, refined by the detail stages below its pixel | load a DEM (reference name or file) into the main level → hero levels: fluvial refinement + talus + rock breakup + hydraulic | `dem='lauterbrunnen'` | that DEM, by definition; the test is that the hero levels add detail without moving the landform |

Later recipes (each builds on the solvers above): shield volcano, lava field, playa with bajada fans, inselberg plain,
braided outwash plain, river valley with floodplain and oxbows (needs meander migration), complex crater, volcanic
island, fjord.

---

## 6. Masks (`masks.py`)

Every mask is computed per level on the final fields, in numpy. A large-radius operation (occlusion, curvature at a
big scale) uses an FFT blur. All are defined in metres and degrees, so a mask means the same at every level. They are
written to the mesh as FLOAT point attributes named `eido_<mask>`.

| mask | definition |
|---|---|
| `height` | metres above base (and `height_norm` 0-1 over the main tile) |
| `slope` | degrees, central differences on the final surface, never clipped |
| `aspect` | degrees from north (Ekigar's angle mask) |
| `curvature` | signed profile and plan curvature of the height smoothed with σ = `scale` metres (default 2 × cell, and 20 m); `convex` / `concave` are smoothsteps of curvature × scale |
| `peaks` | high and convex (Ekigar's peaks mask, in metres) |
| `flow` | log10 of the converged drainage area, normalised over the main tile |
| `channels` | area above a threshold area per level: 1 km² at the main level, down to 1,000 m² on the hero levels (rills) |
| `wetness` | topographic wetness, ln(A / tan S), normalised |
| `wear` | eroded depth, metres (fresh rock) |
| `deposit` | sediment thickness, metres |
| `talus` | talus thickness, metres |
| `sand` | sand thickness, metres |
| `lava` | lava-flow footprint, with age |
| `snow` | altitude above the snowline, aspect bias, slope under 45°, concave bonus |
| `rock` | exposed rock: slope above the rock angle, or high wear with thin deposit |
| `strata` | stratigraphic height zs (the material reads the column from it) |
| `water` | lake or sea depth |
| `occlusion` | horizon occlusion (moved from Ekigar's hydrology) |
| `vegetation` | suitability from moisture, slope, altitude band and aspect: a density for the flora family, which the scene script passes on |

---

## 7. Surfacing, dressing, water (`build/surfacing.py`, `palettes.py`, `dressing.py`, `water.py`)

The material is part of the landform, not a pass at the end. The surfacing package starts on day one on the real
reference DEMs (whose masks the masks package computes), so the first renders of every recipe carry real textures.

### The node group

One node group, `eido_terrain_surface`, with up to six layers in order. Each layer has:
- a CC0 scan set (albedo, normal, roughness, AO and height map, from `_pbr.load_set`);
- `tile_metres`;
- a tint and a roughness factor;
- a projection: world-XY planar on gentle ground, the Image Texture node's Box projection with blend (triplanar) on
  slopes above 35°;
- a weight from the masks, written in the same small expression language as stage `where`. Example:
  `rock = smoothstep(32, 45, slope) + 0.5*wear - 2*deposit`.

### Blending and filtering

Layers are height-blended in order, using the old film material's normalised height blend. The two-sample de-tiling
switch, the macro tint variation, the damp patches, and the `'Auto'` filtering (Cubic within 4-9 m of the camera,
mipmapped Linear beyond) all move over unchanged. They were measured with the shimmer probe, which moves with them.

### Strata bands

On rock layers: a 1D image of the column (colour and roughness per layer, height in metres) read at the world-space
stratigraphic height (`Position.z` with the same dip and warp as the solver). Bands are level, continuous across
ridges, and sit on the benches the solver made.

### Palettes (`palettes.py`)

| palette | layers |
|---|---|
| `alpine` | grey rock, scree, alpine grass, gravel, snow |
| `desert_sandstone` | banded red sandstone, talus rubble, desert pavement, sand |
| `volcanic` | dark lava rock, scoria, ash and soil, sparse grass |
| `dunes` | sand with a ripple normal map, interdune crust or gravel |
| `badlands` | banded mudstone (grey, buff, red), crusted clay |
| `karst` | grey limestone, red soil, grass |
| `chalk_coast` | white chalk, flint shingle, downland grass |
| `farmland` | grass, soil, crop |
| `meadow` | the old meadow layers (Ground106, withered_grass) |

- **Sets in hand:** the shared texture cache (the main checkout's, which `_pbr` finds from this worktree) has
  Ground037, Ground106, Gravel041, coast_sand_01, sand_03 and withered_grass.
- **To fetch:** rock, scree, snow, lava and mudstone sets, with `fetch_texture.py "<term>" 2k --cache` (Poly Haven,
  ambientCG and TextureCan, all CC0). The package records each chosen ID in `palettes.py`.
- **`palette='auto'`** takes the recipe's palette. **`palette=None`** gives grey clay (albedo 0.18, the reference
  rig's) for shape comparisons.

### Dressing (`dressing.py`)

- **Rocks and boulders.** Scattered on the talus, rock-toe and channel masks with densities in metres⁻². Sizes are
  drawn from a power law. Each rock is snapped to the mesh, half-buried and aligned to the surface.
- **Assets.** CC0 rock models from Poly Haven, through `fetch_model.py --cache`.
- **Instancing.** Collection instances, so millions of stones cost little memory. Rocks are placed only on the hero
  levels plus the main level near the focus.
- **Vegetation is not imported.** The scene script passes `terrain.mask('vegetation')` (and wetness and altitude) to
  `create_flora` and to the trees family's scatter.

### Water (`water.py`)

- Lake surfaces: flat meshes at their spill levels, from the moved `build_lake_mesh`.
- A sea plane at `sea_level`.
- A simple water material: dark, glossy, with depth tint from the `water` mask.
- River water ribbons along channels come later; they hand off to the water family.

---

## 8. The API (`api.py`)

```python
from eidoblend.terrain import make_terrain, recipes, describe

t = make_terrain(
    recipe='alpine_valley',      # a name from recipes(), a Recipe, a recipe dict, or a list of stages
    size=8000.0,                 # metres, the main tile (default per recipe)
    resolution=None,             # cells across the main tile (draft 512 / film 1024 / hero 2048)
    seed=7,
    params={'relief_m': 2800, 'ela_m': 2300},     # the recipe's knobs, in their units
    focus=None,                  # (x, y), [(x, y), ...], a camera object or a list of camera positions
    hero_cell=0.5,               # metres: the finest cell around the focus
    context=None,                # extent multiplier for the horizon levels (default per recipe)
    flatten=[{'at': (40, -12), 'radius': 15, 'falloff': 10, 'height': None}],   # None = the area's median
    sea_level=None,              # metres, or None
    base_elevation_m=None,
    palette='auto',              # 'auto', a palette name, a palette dict, or None (grey clay)
    dress=True,                  # rocks on the talus and rock-toe masks near the focus
    quality='film',              # 'draft' | 'film' | 'hero'
    cache=True,
    name='terrain', collection=None)
```

The call returns a `Terrain`.

### Members

| member | what it is |
|---|---|
| `t.obj` | the ring mesh, one object. Masks are point attributes, the material is applied, and `obj['trimesh_collider'] = True` so placement treats it as the ground. `obj['eido_terrain']` holds the recipe, knobs, seed, level plan and cache key. |
| `t.height_at(x, y)` | metres at Blender (x, y), floats or arrays, exactly on the rendered triangles of the finest ring that covers the point |
| `t.normal_at(x, y)` | the surface normal there |
| `t.masks` | a `MaskSet`: `t.masks['slope'].at(x, y)`, `.array(level)`, `.names()` |
| `t.mask(name)` | shorthand for `t.masks[name]` |
| `t.levels` | each level's window, cell and role |
| `t.fields(level)` | the raw arrays |
| `t.flats` | the resolved flatten areas and their heights |
| `t.water` | `{'lakes': [obj, ...], 'sea': obj or None}` |
| `t.rocks` | the dressing collection |
| `t.metrics()` | the judge's generic numbers for the main tile |
| `t.viewpoint(target, distance, eye_height=1.7, ...)` | a standing point with a clear line of sight to the target: the reference rig's search, so eye-level cameras stop facing walls (triage caveat 2) |
| `t.preview(path)` | hillshade plus mask PNGs, for an agent to look at before a render |
| `t.save(path)`, `Terrain.load(path)` | write and read the terrain |
| `terrain_height_at(obj)` | rebuilds `height_at` after a `.blend` is reopened (from the cache, or by regenerating deterministically) |

`obj, height_at, masks = make_terrain(...)` also works, through `__iter__`.

### Discovery and errors

- `recipes()` lists the names and titles.
- `describe('alpine_valley')` prints the stages, knobs (unit, default, range, what each does) and references.
- An unknown recipe or knob raises an error that names the nearest valid ones.
- A focus outside the main tile is an error.
- A focus wider than the finest hero window allows coarsens the hero cell, with a warning.
- Every call prints one summary line: recipe, levels, cache hit or miss, generation time, triangle count.

### Baking from the command line

```
bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe dunes --size 6000 --seed 3 --out <dir>
```

This fills the cache and writes the preview PNGs, so an agent can try a recipe without building a scene.

### Callers to update at integration

- `blender/tests/look/fixtures.py`.
- Comments in `placement/audits.py` and `placement/helpers.py` that name `make_terrain`. The `trimesh_collider` flag
  keeps working.
- The `make_terrain` section of `tools-guides/terrain-surfaces.md`, rewritten for this API.

### The mesh (`build/mesh.py`)

**Rings.** One ring per level: the level's window minus its child's window. Each ring is a triangulated grid at
`cell × stride`:
- stride 1 on the hero levels;
- stride 2 on the main level and coarser (the default budget: about 3M triangles for seven levels of 1024²).

Triangles are written explicitly, each grid quad split along its (i, j) → (i+1, j+1) diagonal, and `height_at`
uses the same split.

**The seam between rings.** A child window's edges lie on its parent's grid lines. The child's outermost vertex row
is set to the parent's straight edge (a linear interpolation of the two parent vertices), so the two meet with no gap
in geometry. The parent cells next to the hole are triangulated as fans that include the child's midpoint vertices,
so no T-junction is left for the rasteriser to crack.

**`height_at`.** Picks, per point, the finest ring that contains it, then evaluates that ring's triangle (regular
cells by the diagonal rule, seam cells by the fan rule). It is exact to float precision, which the tests check with
ray casts.

**Context rings.** These get a skirt at the outer edge, dropping 50 m below the lowest edge vertex, so a low camera
never sees under the world.

---

## 9. Performance targets (this machine; the basis is section 1.2)

| what | target | basis |
|---|---|---|
| one fluvial step (4-7 passes) | ≤ 0.5 ms at 1024², ≤ 1.8 ms at 2048² | 0.06 / 0.23 ms per pass |
| one level of fluvial (2,000 steps) | ≤ 1 s at 1024², ≤ 4 s at 2048² | the coarse-to-fine probe: 0.74 s and 3.9 s |
| a film recipe, cold (7 levels of 1024², every stage, masks, mesh) | ≤ 45 s, excluding Blender start-up and the first shader compile | GPU ≈ 15-30 s; CPU (hydrology, masks, noise inputs, mesh) ≤ 15 s |
| a draft recipe, cold (512², no hero levels) | ≤ 10 s | |
| a cache hit (load fields, build mesh, material) | ≤ 5 s | |
| the dune model, 1024², 20,000 iterations | ≤ 60 s | about 6 passes per iteration at 0.06 ms |
| world-space input fields, numpy, per 1024² level | ≤ 1 s | port to GLSL with a twin if slower |
| mesh | ≤ 3M triangles by default, built in ≤ 5 s | stride-2 rings |
| render, EEVEE 960×540, 16 samples, full palette | ≤ 4 s a frame | measure in the surfacing package; cut layers or samples before raising it |
| VRAM during generation | ≤ 2 GB | twelve 2048² RGBA32F textures ≈ 200 MB; slots reserve 4 GB |
| numpy-twin tests at 64-128² | ≤ 5 s each, plain Python, no GPU | |

---

## 10. Judging (the validation harness: `blender/tests/terrain/judge/`)

### For every recipe and seed

1. **Generate at the reference's extent.** Box-average the main level to the reference's pixel size. Slope depends
   on pixel size, so numbers are only compared at matched pixels.
2. **Generic numbers** (`core/metrics.py`, numpy only, no scipy or scikit-image, so it runs in Blender):
   - relief and hypsometric integral;
   - slope p10, p50, p90 and p99;
   - the fractions under 5° and over 30°, 40° and 50°;
   - closed depressions (area fraction and count, through `hydro.fill_depressions`);
   - the radially averaged power spectrum's slope and its knee (the characteristic valley scale);
   - the grid-direction anisotropy: the 8-fold and 4-fold Fourier amplitude of the aspect histogram, weighted by
     slope over 10°;
   - texel-wide cliffs: the fraction of neighbour pairs steeper than 80°.
3. **Bands** (`bands.json`). By default, each number is compared with the reference's:

   | metric | allowed difference |
   |---|---|
   | slope p50 | ± max(3°, 25 %) |
   | slope p90 | ± max(4°, 15 %) |
   | slope p99 | ± max(5°, 10 %) |
   | hypsometric integral | ± 0.08 |
   | relief | ± 20 % |
   | fraction under 5° | ± max(0.05, 40 %) |
   | spectrum slope | ± 0.5 |
   | closed depressions | ≤ reference + 1 % |
   | anisotropy | ≤ 1.5 × the largest over all the references |
   | texel-wide cliffs | ≤ 2 × the reference |

   For depressions, the families with basins (craters, calderas, karst, dunes, glacial lakes) instead check that
   their basins have flat floors or water. The judge calibrates the anisotropy and spectrum bands by running every
   reference through itself.
4. **Family numbers:**

   | family | numbers |
   |---|---|
   | crater | d/D, rim height / D, wall slope p99 inside the rim, ejecta reach |
   | volcano | radial slope profile monotone (Spearman ρ ≤ -0.9 over 10 radial bins); ≥ 70 % of flank aspects within 30° of radial; summit crater depth |
   | cinder cones | H/W 0.15-0.2 and flank p90 28-33° per cone |
   | alpine valley | U-shape exponent b of the main trough in 1.5-2.5 (fit y = a·x^b to 5 cross-sections); hanging-valley step ≥ 100 m |
   | canyon | ≥ 3 benches in 5 wall cross-sections; a two-peaked slope histogram (under 10° and over 45°) |
   | mesas | caprock fraction; wall slope over 60° on the butte cliffs |
   | dunes | p99 ≤ 34° and ≥ 26°; spectral peak within ± 30 % of the target spacing; two-peaked aspect on lee faces |
   | karst | nearest-neighbour spacing of summits ± 25 %; plain fraction ± 30 % |
   | coast | cliff-top height along the shore (distribution ± 25 %); face angle ≥ 70° at 2 m cells; platform width |
   | rolling hills | the curvature sign on ridges (convex) |

5. **Views.** `reference/render_references.render_probe` renders the top-down hillshade, the 45° aerial and the
   1.7 m eye view. The eye spot comes from `t.viewpoint`, matched to the reference's kind of view (the gorge edge,
   the caldera rim, the valley floor). The grey clay is identical to the references'. A compare sheet sets the
   reference row above the generated rows, with the numbers printed on each.
6. **The textured row.** The same aerial and eye views with the palette, and rocks near the eye.
7. **The artist's read.** A recipe passes when its bands pass, its family numbers pass, and the compare sheet reads
   as the named landform:
   - at a glance in the top view and the aerial;
   - at eye level, the near ground is not smooth clay: the hero levels, the material and the rocks are all there.

   The package agent writes one paragraph per view on what reads and what doesn't, naming the features
   (benches, slip faces, cirques...).
8. **Review videos** (integration only). Per recipe: an 8 s aerial orbit and a 6 s eye-level dolly, 960×540,
   16 samples, H.264 High yuv420p, checked with ffprobe, into `blender/tests/terrain/out/videos/`. The review
   happens in motion.

### Sanity checks of the judge itself

- Every reference judged against itself passes.
- Ekigar's triage heightfields (cached by the triage scripts) fail.

---

## 11. Build plan

### Rules for every package

The lead's standing block applies on top of these.

- **Ownership.** You own the files listed for your package and nothing else. Read anything; edit only yours.
  - `recipes/__init__.py` discovers recipe modules on its own, so nobody edits a shared list.
  - Tests go in `blender/tests/terrain/<package>/`. Renders and other outputs go in
    `blender/tests/terrain/out/<package>/`: the ignore rule `blender/tests/*/out/` covers only the family's own
    `out/`, not an `out/` one folder deeper.
- **GPU.** Every Blender run that dispatches kernels or renders goes through a slot. From
  `C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01`:

  ```
  HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <script> [args]
  ```

  If that slot says "not started", try `heavy2.sh`, then `heavy3.sh`; if all are busy, wait 60 s and retry. Renders
  stay at most 960×540 and 16 samples, under `make_sky` daylight.
- **Units.** Metres, years and degrees in every interface. A tile fraction anywhere is a defect.
- **Looking.** Look at every image you produce, the reference beside it, as an environment artist. Name defects
  concretely.
- **No git, no installs.** Downloads are public elevation data and CC0 textures and models through the existing
  fetch scripts only.
- **Stopping.** When your bands pass and the sheet reads right, stop. Refinements go in the report as next steps;
  don't re-run checks that passed.
- **Visible edits.** Edit code with the Edit and Write tools.

### Packages

| # | package | files it owns | what it builds | its tests | done when |
|---|---|---|---|---|---|
| 1 | **Core** | `terrain/core/*`, `terrain/kernels/common.glsl` | frames and units; `plan_levels`; `Fields`; world-space noise (moved from Ekigar, evaluated in metres, frequency snapping); the GPU runner (section 2.5); the numpy-twin harness; the cache; `io.py` (moved PNG16/R32); `metrics.py` (section 10 item 2) | runner round-trip exact; a sample kernel (the probe's creep) equals its twin within 1e-4; `plan_levels` windows snapped and nested for 20 focus cases; metrics reproduce every reference JSON's slope percentiles within 0.1°; the GPU benchmark re-run and recorded | all tests pass, and the interfaces of sections 2.3-2.5 exist as written, so the other packages can build on them |
| 2 | **Judge** | `blender/tests/terrain/judge/*`; additions to `reference/sites.py` and `reference/fetch_references.py` | `judge(result, reference)` → numbers, bands, renders, compare sheet; `bands.json` calibrated on the references; the review-video renderer; new references: San Gabriel Mountains, SP Crater, Goosenecks, Yosemite (3DEP 1 m), White Sands, Namib linear dunes | every reference passes against itself; Ekigar's triage alpine range, volcano and star dunes fail with the expected reasons | a recipe agent can run one command and get numbers, bands and a sheet |
| 3 | **Fluvial backbone and hydrology** | `terrain/run.py`, `solvers/{fluvial,hillslope,hydro}.py`, `kernels/{flow_weights,route_incise,creep,threshold,route_area}.glsl`, `recipes/{fluvial_range,rolling_hills,meadow}.py` | section 4.1-4.3; the level runner (inherit, border pins with area inflow, world inputs per level, readback, cache); relief controller; the hillslope-length schedule; sediment deposition; lakes | every kernel against its twin; mass conservation of creep and threshold (sum unchanged within 1e-5); level seams (\|Δh\| ≤ 0.05 m at the border, slope jump ≤ 3°); determinism on one machine | `fluvial_range`, `rolling_hills` and `meadow` pass their bands and read right; the design probe's plastic facets are gone at eye level (hero levels with rock breakup from package 12, or the package's own breakup first) |
| 4 | **Masks** | `terrain/masks.py` | section 6 | on the reference DEMs: slope matches the reference JSON; curvature masks pick out valleys and ridges at their scale (overlay sheets); occlusion and wetness sane; each mask means the same on a 2× resampled field (scale independence) | mask sheets on five references read correctly |
| 5 | **Mesh and API** | `terrain/api.py`, `terrain/bake.py`, `terrain/__init__.py`, `terrain/recipes/__init__.py`, `build/{mesh,water}.py`, `recipes/real_place.py` | section 8: the ring mesh with stitched seams and skirts; attributes; `height_at` and `normal_at`; `Terrain` and `MaskSet`; `describe` and `recipes`; `viewpoint`; flatten (the exact post pass); the cache wiring; the `real_place` recipe (a DEM as the main level) | ray casts at 2,000 random points (across rings and seams) land within 1e-4 m of `height_at`; no cracks (a top-down render over an emissive backdrop below the terrain shows no backdrop pixels along the seams); triangle budget; unpacking; errors name the nearest valid knob | a `real_place` Lauterbrunnen with a hero window renders with no seams, and a character placed by `height_at` stands on the ground |
| 6 | **Surfacing and dressing** | `build/{surfacing,palettes,dressing}.py` | section 7; the moved film-material logic; the shimmer probe moved to `tests/terrain/surfacing/` | shimmer probe numbers no worse than the old material's; textured aerial and eye renders of Toroweap, Lauterbrunnen, Great Sand Dunes, Fuji and Badlands (`real_place`) beside photographs of those places; render time per frame | each palette reads as its place on the real DEMs |
| 7 | **Glacial** | `solvers/glacial.py`, `kernels/{ice_flux,jump_flood,u_carve}.glsl`, `recipes/alpine_valley.py` | section 4.5 | ice-flux mass balance closes; the jump-flood distance against a brute-force twin at 128²; U-shape fit on a synthetic valley | `alpine_valley` passes against Lauterbrunnen (and Yosemite once fetched) |
| 8 | **Wind and sand** | `solvers/aeolian.py`, `kernels/{dune_activate,dune_shadow,dune_transport}.glsl`, `recipes/dunes.py` | section 4.6 | sand mass conserved; gather and twin identical (integer hash); one wind gives slip faces on the lee side; the four wind regimes give four different dune families | `dunes` star passes against the Namib and Great Sand Dunes; barchan, transverse and linear read as their types |
| 9 | **Volcanoes and craters** | `solvers/{volcanic,impact}.py`, `recipes/{stratovolcano,caldera,cinder_cones,impact_crater}.py` | sections 4.7-4.8; the analytic profiles start in wave 1, aging and flows once package 3 lands | profile functions against their formulas (Fuji slopes at 0, 10 and 15 km; Pike ratios; Wood ratios); lava walkers deterministic per seed | all four recipes pass against Fuji, Crater Lake, Meteor Crater and SP Crater |
| 10 | **Layered rock** | `solvers/{strata,rivers}.py`, `kernels/{strata_threshold}.glsl`, `recipes/{canyon,incised_meanders,mesas_buttes,badlands}.py` | sections 4.9, 4.13 (`river_path`) | composite threshold on a synthetic column gives each layer its own angle in a 1D profile; K(z) lookup against the twin; meander curve geometry | all four pass against Toroweap, Goosenecks, Monument Valley and Badlands |
| 11 | **Karst and coast** | `solvers/{karst,coast}.py`, `recipes/{tower_karst,sea_cliffs}.py` | sections 4.10-4.11 | blue-noise spacing; tower profile wall angles; exposure against a brute-force ray count; the Dean profile | both pass against Guilin (plus photographs) and Seven Sisters / Moher |
| 12 | **Detail** | `solvers/{hydraulic,detail}.py`, `kernels/{pipes_*,breakup}.glsl` | sections 4.4 and 4.12 (rock breakup, flow-steered gully octave, planation) | pipe model conserves water plus sediment; twins; on `real_place` Lauterbrunnen hero levels: detail added without moving the landform (main-level metrics unchanged within 1 %) | hero-level eye views of `real_place` and `fluvial_range` show rills, ribs and talus, not clay |
| 13 | **Integration** | deletions in section 3; `tools-guides/terrain-surfaces.md` (the `make_terrain` section rewritten); `docs/TOOLS.md` row; callers (section 8); `tests/terrain/` cleanup; the review videos; moving `tests/terrain_new/` to `tests/terrain/` once the old tests are gone | the whole family, end to end | every package's tests in one run; every recipe's compare sheet; the videos play | the lead reviews the sheets and videos; the branch is ready for the lead's commit |

### Waves

1. **Wave 1, all at once:** Core (1), Judge (2), Masks (4), Mesh and API (5), Surfacing (6), the analytic half of
   Volcanoes and craters (9), and the tower field of Karst (11).
   - Packages 4-6 work on the real DEMs through `real_place`, so the material is on screen from the start.
   - Core lands the runner first; the others code against sections 2.3-2.5 meanwhile.
2. **Wave 2, as soon as the runner and twin harness are in:**
   - Fluvial backbone (3), the critical path;
   - Wind and sand (8);
   - Detail (12), whose hydraulic pass starts on real DEMs.
3. **Wave 3, as soon as `run.py` and the fluvial kernels are in:** Glacial (7), Layered rock (10), the aging and
   flows of package 9, and Coast (11).
4. **Wave 4:** Integration (13). One verifier reads every recipe's sheet and video and sends concrete defects back
   to the owning package once.

---

## 12. Risks and open questions

1. **The fluvial backbone at film quality is not proven yet.** My probes show the right drainage and slope numbers,
   but a plastic look. Sediment, rock breakup, the hillslope-length schedule and the hydraulic pass are designed to
   fix that. The fluvial package's acceptance is the eye-level look, not only the numbers. If facets survive all
   four, the next lever is a hillslope roughness term in the threshold pass (`Sc` noise at the 10-50 m scale).
2. **The glacial carve is procedural.** It can look tooled. The smooth unions, talus, valley fill, moraines and
   couloirs are there against that, and Lauterbrunnen and Yosemite judge it.
3. **The dune model's time to reach real dune sizes.** Seeding at the target spacing is my mitigation. If star dunes
   still don't form arms, the fallback inside the same solver is longer wind phases per direction.
4. **Heightfields can't overhang.** Karst notches, sea caves and arches go to the material, or to the SDF family's
   meshes placed on the terrain.
5. **Sheer walls are thin in a heightfield.** Triangles stretch on faces above 70°. The hero levels (0.25-0.5 m),
   triplanar projection and rocks at the toe cover close shots. A dedicated cliff mesh is a later option, if a shot
   needs it.
6. **Cross-machine determinism.** NVIDIA and Mesa d3d12 in the auto-blender container can differ in the last bits.
   The cache is per machine; tests compare metrics.
7. **Reference gaps:** a river-carved range, cinder cones, incised meanders, Yosemite, barchan and linear dunes
   (package 2 fetches them). Guilin, the Namib and Moher are 30 m radar data, so wall and crest sharpness must come
   from the lidar references or photographs.
8. **Repository size, for the lead before the commit.**
   - `triage/renders` (258 MB), `reference/renders` (22 MB) and `research/proto/out` (6 MB) sit outside `out/`, so
     they are not gitignored.
   - `reference/data` is 35 MB of elevation PNGs whose JSONs carry the licences. GSI, Copernicus and swisstopo need
     attribution lines; USGS is public domain.
   - `design_probes/` holds my probes' scripts, sheets and `results.json`, 3.7 MB.
9. **Long camera moves.** A hero window is at most 2048 cells, so 1 km at 0.5 m. A longer walk means a coarser hero
   cell or several focus windows, a later extension of `plan_levels`.

---

## Appendix: files from this design

`blender/tests/terrain/design_probes/`:

| file | what it is |
|---|---|
| `gpu_bench.py` | the compute-throughput probe (section 1.2) |
| `gpu_spl.py` | the stream-power kernels as compute shaders. The file holds the last run (coarse-to-fine with two hillslope-length schedules); the earlier runs' numbers are in `results.json` |
| `spl_iso.py` | the numpy slope-estimator comparison |
| `numpy256_slope_estimator_compare.png` | the slope-estimator runs side by side |
| `gpu_streampower_no_threshold.png` | the first three GPU runs, no threshold pass |
| `gpu_streampower_threshold_mismatched_inputs.png` | the threshold pass on, inputs regenerated per level |
| `gpu_streampower_coarse_to_fine_hillslope_schedules.png` | the final run: fixed and shrinking hillslope length, with 5 km crops |
| `results.json` | every number in sections 1.2-1.3 |
