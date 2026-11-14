# The terrain's surface and its plants: design

Blender edition (`blender/eidoblend/terrain/`), 2026-11-13. One design, for the agents who build it and the lead who
reviews it. It builds on `DESIGN.md` (the landforms) and changes how the ground is coloured, shaded, tiled and
planted. The levels, solvers, recipes, masks and ring mesh stay as they are.

---

## 0. The design in one page

**The goal.** Every recipe's surface reads at World Machine / Gaea quality beside the photographs of its place, from
the establishing aerial down to a walker at 1.7 m:

- colour and materials follow the landform at every scale: ridges, gullies, benches, fans, aprons, slope breaks;
- no area reads as one flat material, and nothing tiles at any distance;
- relief reads below the mesh's vertex spacing;
- steep faces in any orientation carry no smear;
- plants stand where the place grows them: as objects near the camera, as canopy far away, one forest.

The impact crater's layered, ribbed walls and the rock dressing stay exactly as good as they are.

**Why it falls short today (section 1).** The material sees the terrain only through vertex attributes on rings
drawn every second cell (every 31 m on a 16 km main level). It reads 18 of the 30 masks and gives each layer one
constant colour. It breaks every threshold with world noise that knows nothing about the ground, colours debris by
its height in the rock column, shades with smooth vertex normals, smears diagonal cliffs with the Box projection and
tiles its scans on two lattices. Plants are a Voronoi texture.

**The decisions.**

1. **Data per texel, not per vertex.** A GPU bake turns each level's fields into images at the field's own texel:
   the cell, and half the cell for the normal and detail images on the main and hero levels. Maps are packed four to
   an image, and all levels of one kind into one tall atlas image, so the material reads each kind with one sampler.
   The material finds the finest level per pixel from the nested windows. Every map's border band is pinned to its
   parent's, as the heights and masks already are, so one read per kind meets the next level with no seam.
2. **New maps from the terrain's own data:** a normal from the full-resolution height plus analytic gullies below the
   cell; cavity; convexity at five scales; settled soil; snowpack that settles and slides; freshness (stream power and
   threshold exceedance); valley-bottom flatness; provenance (the rock column height a debris' source sits at, and the
   colour sediment carries down the drainage); talus grain; wind streaks.
3. **Colour from data.** A layer's colour becomes a ramp read at a terrain mask (Gaea's CLUT idea), with stops
   measured from the photographs. Rock gets freshness and patina. Debris and sediment take their source's colour. The
   strata column colours the cliffs only. A per-texel far colour baked from the same palette carries the ground to the
   horizon and is the whole material of the context rings.
4. **Placement from terrain structure.** Layer weights move from world fbm to terrain terms. Every transition is an
   overlay of the macro data and the scans' heights, then the existing height blend. Noise stays as a small residual,
   and every noise term fades with the pixel's footprint.
5. **Projection and tiling.** Planar reads are hex-tiled (three reads on a triangle grid, each turned and offset,
   sharpened weights). Steep faces are read in eight aspect sectors instead of the Box projection.
6. **Plants as data.** A plant layer turns ecosystem rules, written in the same mask language, into spots: position,
   scale, yaw, age, species, tint. Sampling is clustered Poisson, and trees thin the undergrowth. The spots are saved
   with the terrain in a format a three.js placer can read. In Blender they instance flora plants and SeedThree trees
   grown once, switched by camera distance, and they give the material its canopy cover.
7. **Kept:** the node group, the mask language, the height blend, `'Auto'` filtering, the strata column with its
   relief and ledges, streaks, ripples, patches (fewer, terrain-limited), the canopy (now driven by plant cover) and
   the rock dressing.

**Measured (section 1.3).** One EEVEE material here samples at most 30 images (32 samplers, 2 kept by the engine). A
UDIM image costs 2 samplers. A second read of one image costs another sampler when its extension or interpolation
state differs (Linear and Cubic share). So the data travels in atlases, one sampler each, every read of an atlas
with the same state. The probes' frame costs of hex tiling, sector projection and the data reads are in section 1.3.

---

## 1. What I worked from, and what I measured

### 1.1 Inputs

- `DESIGN.md` sections 2, 6, 7, 8 and 11, and the code they name: `build/surfacing.py`, `build/palettes.py`,
  `masks.py`, `build/mesh.py`, `build/dressing.py`, `surface_layers.py`, `core/gpu.py`, `core/cache.py`, `api.py`,
  `solvers/detail.py`, the kernels, the flora family, the trees family's SeedThree bridge, and SeedThree's Blender
  add-on (`seedthree/bl/forest.py`, `core/forest.py`).
- The review of the textured renders and videos of 11-12 and 11-13 (`out/surfacing/review/boards/`). The ground reads
  as flat cut-offs by height, with no curvature in its colour; large areas are one material and show their tiling.
  The impact crater's walls read as layered, with their materials applied by the terrain's own structure. The rock
  placement and the geometry read right.
- The lead's study of World Machine, Gaea and engine practice (fifteen techniques, gaps against our stack, plant
  placement in engines and research) and the lead's per-recipe audit of the current surfacing (sixteen recipes, with
  layer maps, coverage, height-line and repetition measurements). Both are summarised where they are used.
- The fix round's package reports of 11-13 (DESIGN.md's packages 3 and 6-11: fluvial, surfacing, glacial, wind and
  sand, volcanoes and craters, layered rock, karst and coasts): what they left to surfacing (section 3.9). Below,
  "package 1-5" always means this design's packages (section 5).

### 1.2 What the code does today (checked against the files)

| what | today | where |
|---|---|---|
| masks | 30 per level (`masks.DEFAULT_NAMES`), numpy, about 5 s per 1024² level (the logs: 21-45 s for 6-7 levels) | `masks.py` |
| how the material sees them | FLOAT point attributes `eido_<mask>`, sampled at the ring's vertices: stride `round(n / 512)` (2 at 1024 cells, 4 at 2048), each vertex the 2×2 cell average at its corner, interpolated across triangles. On a 16 km 1024² main level that is every 31.25 m | `mesh.plan_rings`, `mesh._lattice_bilinear` |
| attribute limit | a material reading 15 attributes fails to compile (FLOAT, FLOAT_VECTOR and FLOAT_COLOR alike); palettes reading more than 10 masks pack three to a FLOAT_VECTOR | `surfacing.ATTRS_DIRECT`, `pack_masks` |
| masks read | 18 of 30 over all palettes. Never `wear`, `channels`, `eastness`, `height_norm`, `rock`; `peaks` only in the cinder-cone look; curvature only at 20 m | `palettes.material_masks` |
| colour | one constant per layer (the scan rescaled from its mean), or the strata column; debris reads the column at `zs + strata_offset_m` (desert talus at 0.75 and +25 m, soil 0.35, wash 0.2) | `surfacing.surface_group` |
| variation | world noise only: patches, five landscape macro octaves (±10-12 % value at 14, 75, 320 and 1600 m, plus hue and saturation), the far read's `macro_mod` | `palettes.LANDSCAPE_MACRO` |
| thresholds | moved by fbm: `_CLIFF` by ±6° at 80 m and ±2.5° at 12 m; `_TALUS`, `_SNOW` and the forest weights alike | `palettes.py` |
| normals | smooth vertex normals, the planar scans' normal maps, and a Bump node over box layers' heights, ripples, canopy and strata relief (EEVEE evaluates a Bump's height input three times, so the bump is weighted by cheap coverages) | `surfacing.surface_group` |
| projection | Image Texture BOX, blend 0.3, switched in over nz 0.80-0.68 | `surfacing._Reader.tex` |
| de-tiling | `'rotate'`: a second planar read at 0.7071× the scale, turned, switched by noise and the two heights; box layers keep `'offset'`; past 40-200 m a far read at 8× the tile, toned down (`far_contrast`, `macro_mod`) | `surfacing._Reader`, `_far_reads` |
| cost | the material bench's 1.6 km scene, 960×540, 16 samples: alpine 1.31 s of material per frame, desert 0.86 s, volcanic 0.70 s (`out/surfacing/bench_b3.json`); first frames with a cold shader compile 15-110 s, by palette and machine load (the bench, the audit's compile probe, probe B) | `tests/terrain/surfacing/bench_material.py` |
| plants | none placed. Dressing scatters rocks only; flora paints strokes or explicit placements; SeedThree's forest ring puts 64 slots in rings 38-200 m around the origin | `dressing.py`, `flora/vegetation.py`, `SeedThree/blender/seedthree/core/forest.py` |
| cache keys | `core/cache.code_hash` hashes `core/*.py`, `kernels/*.glsl`, `solvers/*.py` and `run.py`; `api._code_hash` hashes `recipes/*.py` and `masks.py`. Editing any of them invalidates every cached terrain (minutes per recipe to regenerate) | `core/cache.py`, `api.py` |

Every new file in this design lies outside those globs, and no package edits a file inside them (section 5).

### 1.3 EEVEE's limits and the new pieces' cost (my probes; scripts in the lead's scratch folder, numbers here)

| question | answer | probe |
|---|---|---|
| images one material can sample | 30 compile; 31 fail with "uses too many samplers (33/32)". The GPU reports 32 fragment samplers; EEVEE keeps 2 | A (and the audit's probe) |
| a UDIM image | 2 samplers: 15 UDIM images compile, 16 fail (34/32); 14 images + 8 UDIMs compile, + 9 fail | A |
| one UDIM read at 12 different tiles | costs its 2 samplers once (28 images + it compile) | A |
| Cubic on a UDIM | compiles, and reads the right tile at its centre | A |
| the same image read with another state | Linear and Cubic share a sampler; Closest, EXTEND and CLIP each add one (28 images plus those four variants: 33/32) | A |
| mesh attributes | 14 compile, 15 fail | the audit's probe |
| GPU limits | OpenGL backend; max texture size 32768; 2048 array layers; 32 fragment samplers | A2 |
| float precision | a float image with `use_half_precision` True (the default for a new one) is half on the GPU: 1234.567 reads 1235, 37.123 reads 37.125. With it False the shader reads 32-bit values | A, A3 |
| images made in memory | a generated image must get its colour space and precision before its pixels: set after, every texel read 0. Set first, the values arrive intact (half by default; 32-bit with `use_half_precision` False), and a 1088 × 16,448 float atlas read its top tile exactly. `pack()` stores a float image as an OpenEXR with its pixels intact on the CPU (checked), yet a packed 4 × 4 float image read 1.0 at every texel on the GPU (unexplained; the packed strata images render right) | A2, A3 |
| frame cost of hex tiling, sectors, data reads | today's desert_sandstone material on the material bench's scene (960×540, 16 samples) costs about 1.0 s of material per frame. Hex tiling on its three planar layers measured 0.9-1.5 s; sectors on its three box layers about 1.0 s; both together 0.9 s. A far material of twelve atlas reads and a Principled BSDF costs 0.03 s over clay. Twelve atlas reads added to today's material were lost in the load: the clay frame read 1.0-1.2 s beside them. The GPU was shared throughout, and the clay frame varied 0.34-1.2 s between variants, so these are ranges, not a ranking. Package 2 measures again on a quiet machine | B |

What these decide:
- **Atlases, not UDIMs.** The palettes' scans already take 12-14 samplers. The data needs eight to ten kinds of
  image. As UDIMs that is 16-20 samplers, 28-34 in all; as atlases it is 8-10, 20-24 in all.
- **One sampler state per atlas:** every read Linear, EXTEND, mipmapped. A Closest or REPEAT read of the same atlas
  would cost a sampler more.

### 1.4 What I looked at

The boards `canyon_v5`, `impact_crater_v5`, `real_place_v9` and `overview_textured_11-13`, at full size, beside their
photographs:

- **Canyon, approach walk.** One mauve-red soil runs to the horizon, with flat dark scrub decals. The photograph shows
  stones, grass tufts, sage and flowers.
- **Canyon, aerial.** Every wall and every talus slope is striped at the same heights, and lakes stand on the
  benches (geometry).
- **Canyon, brink.** The near right-hand wall, diagonal to the axes, is drawn in long diagonal strokes: the Box
  projection's smear.
- **Crater.** The walls are bands broken by ribs and chutes, and they read right. The floor is a flat beige disc
  ending in a crisp pale ring at the walls' foot. The plain is one soil with a uniform speckle.
- **Lauterbrunnen.** The floor is one even lawn. The forest is a dark texture draped over the slope with a hard edge.
  From Schynige Platte, forest and meadow are a camouflage of blobs, and the foreground slope is smooth plastic.
- **Others.** Fuji's lower cone carries hard white snow splats. The Palouse fields are flat polygons. The Namib
  interdune grass is pale stains. The Seven Sisters' brow is a comb of green teeth. The San Gabriels are camouflage.

My probe B renders of the bench scene also show the Box projection's diagonal strokes on its 45-degree wall.

---

## 2. Architecture

### 2.1 The pieces and where they live

```
blender/eidoblend/terrain/
  surface/                    NEW (package 1): the surface data bake
    __init__.py               bake_surface, SurfaceData, MAPS
    maps.py                   the map registry: name, unit, family, channel, encoding, how it is made
    bake.py                   per level: inputs -> kernels -> maps, pins, gutters, readback, cache
    atlas.py                  atlas layouts, atlas arrays, Blender images (one per family)
    palette_bake.py           the palette's maps: far colour (C), provenance colour (P)
    expr_glsl.py              the mask language compiled to GLSL (its twin: palettes.evaluate)
    noise.glsl                Blender's shader noise (GPL-2.0-or-later), ported for the bake
    twins.py                  the numpy twins of the bake kernels
    kernels/*.glsl            field_normal, phacelle, cavity, blur, crest, carry_src, route_colour, spi_valley,
                              streak, far_colour, pin_gutter
  build/surfacing.py          (package 2) the reader, normals, hex tiling, sectors, footprint, far material
  build/mesh.py               (package 2) material_index per ring (context rings take the far material)
  build/palettes.py           (package 3) new mask names, ramps, provenance, patina, the looks
  build/plants.py             NEW (package 4) ecosystem rules -> spots; the spots format
  build/ecotopes.py           NEW (package 4) species tables per palette, recipe and place
  build/plant_instances.py    NEW (package 4) instancing in Blender: flora, SeedThree, LOD
  build/dressing.py           (package 4) the toe bias only
  api.py, __init__.py         (package 5) wiring, save and load
```

The bake's kernels live in `terrain/surface/kernels/`, not `terrain/kernels/`, so a bake change never touches the
field cache's code hash. They load through `core/gpu.kernel(path=...)` with `common.glsl` prefixed, as every kernel
does. The bake reuses existing kernels by name, read-only: `flow_weights` and `route_area`. It also calls
`solvers.detail.relax` (the threshold relaxation, `pipes_thermal.glsl`), `solvers.detail.strength` (the rock breakup
strength, `breakup.glsl`) and `solvers.detail.phacelle_noise` (the gully filter's twin). It edits none of them.

### 2.2 The maps (`surface/maps.py`)

**Families.** Each is one atlas image holding every level:

| family | format | texel | channels |
|---|---|---|---|
| D, detail normal | RGBA16F | half the cell on the main and hero levels at film quality (n ≤ 1024); the cell otherwise; at most 2048 per level | the field normal's x, y; the sub-cell relief's gradient gx, gy |
| E, detail scalars | RGBA8 | as D | `crease` (signed), `cavity`, `crest_fine` (signed), `grain` |
| M0..Mk, masks | RGBA8 | the cell, at most 1024 per level | four maps each: the ones the palette and the plant layer read, packed at material build |
| F, metres | RGBA16F | as M | `strata_dz`, `src_dz` (each relative to a per-level reference the material adds back, so half precision keeps 0.03-0.25 m), two spare; only when read |
| C, far colour | RGBA8 sRGB | as M | far albedo; far roughness in the linear alpha |
| P, provenance colour | RGBA8 sRGB | as M | the colour sediment carries (C_down); the sediment share in alpha |
| LUT, ramps | RGBA8 sRGB, 256 × rows, a plain image | - | one row per ramp of the palette |

**Encodings in RGBA8.**
- 0-1 maps are stored as they are.
- Signed maps are stored as 0.5 + 0.5 v.
- Curvatures are stored as the dimensionless bend κ × scale, clamped to ±1. The material divides by the scale.
- Thicknesses in metres (deposit, talus, sand, snowpack, water) are stored as √(t / t_max) with a per-map t_max
  (64 m by default), and squared back. At 1 m the step is 6 cm.
- The 20 m normal (`n20`) is stored as its x and y, two signed channels; z is rebuilt.

**Derived in the shader, never stored:**
- `slope`, `aspect`, `northness`, `eastness` from D's field normal, with `masks.py`'s definitions (northness faded
  to 0 under 3°);
- `height` and `altitude` from the object z, which is the field's height at every pixel of the mesh;
- `insolation` = max(0, N_field · s), from the terrain constants `sun_azimuth_deg` and `sun_elevation_deg` (palette
  defaults; the scene's sun when the scene script passes it).

**The map list.** Every existing mask keeps its name, unit and meaning: `flow`, `wetness`, `channels`, `occlusion`,
`deposit`, `talus`, `sand`, `lava`, `water`, `rock_toe`, `peaks`, `snow`, `rock`, `wear`, `vegetation`,
`height_norm`, and convex, concave and the curvatures at 20 m and at 2 × the cell. New:

| map | unit | made by | what it marks |
|---|---|---|---|
| `crest` | -1..1 | blur pyramid | multi-scale convexity, σ = 1, 2, 4, 8, 16 cells: + crests, rims, ribs, spurs; − creases, chutes, hollows (Gaea's SurfTex Sprinkling, our terms) |
| `crest_fine` | -1..1 | blur on D's grid | the same at one texel of D |
| `crease` | -1..1 | gully filter | the sub-cell gullies' curvature: floors −, crests + |
| `cavity` | 0-1 | horizon march on D's grid | short-radius occlusion, 2-32 texels: 1 open, low in creases |
| `settle` | 0-1 | `detail.relax` | where a thin loose layer comes to rest at a 20° repose: benches, ledges, crevices, slope feet |
| `snowpack` | m | `detail.relax` twice | snow settled at a 38° slip-off, melted by insolation, plus a flowing pass at 14° along the drainage |
| `fresh` | 0-1 | stream power, threshold | actively eroding ground: stream power on bare ground, slope over the rock's threshold `Sc`, or a solver's `wear_recent` |
| `spi` | 0-1 | stream power | log10(a tan S), normalised by the main tile's 5th-95th percentiles |
| `valley` | 0-1 | blur pyramid | flat and low at several scales (an MRVBF-like index, Gallant & Dowling 2003): valley floors, fans, basins |
| `src_strata` | m | carry kernel | the stratigraphic height of the bare rock a debris cell's material came from (z + `src_dz`) |
| `grain` | 0-1 | carry kernel | distance down the fall path from the source over the reach: fine near the apex, boulders at the toe |
| `streak` | 0-1 | directional blur | wind exposure on convex ground, smeared 10:1 along the palette's wind |
| `n20` | 2 channels | blur pyramid | the 20 m normal's x and y (z rebuilt): the sector frames' azimuth and dip |
| `canopy`, `canopy_expected`, `shrubs` | 0-1 | plant layer | placed crowns' cover; the cover the tree density implies; undergrowth density |

`flow`, `wetness` and `channels` on hero levels come from the bake's own routing (2.3, step 8), which works around
the hero-level inflow defect the fluvial package reported on 11-13. The palettes keep reading the same names.

### 2.3 The bake (`surface/bake.py`)

Levels run coarsest first, because a level's pins and gutters read its parent's maps. Per level:

1. **Inputs.**
   - the level's fields: `h`, `bed`, `A`, `wear`, `deposit`, `talus`, `sand`, `lava`, `water`, `Sc`, `zs`, and
     `flow_x` / `flow_y` where present;
   - its `Masks`;
   - the parent's maps.
2. **Field normal on D's grid.** h by the mesh's Catmull-Rom (weights (−1, 9, 9, −1)/16 at cell corners, the full
   cubic at quarter offsets), then central differences at the texel spacing. On the cell grid this is `masks.slope`'s
   arithmetic.
3. **Relief below the cell.** Port `solvers/detail.py`'s `phacelle_noise` and `gully_relief` octave loop to
   `phacelle.glsl`, with the same arithmetic, seed, octave sequence (λ0 × 2^−o) and per-octave lattice offsets.
   - The kernel runs the whole loop from `op_gully`'s λ0, so each octave is steered as the geometry's was, and adds
     only the octaves `op_gully` stops at (λ < 3 cells) down to 2 texels. Where `op_gully` ran on a level, the
     material's gullies continue the geometry's octave by octave; elsewhere they start at λ = 3 cells.
   - They are steered by the routed flow (`flow_x`, `flow_y`), else by the descent smoothed over 2 cells.
   - They are masked to soil slopes of 10-35° and loose cover.
   - On bare rock the breakup strength's gradient (`solvers.detail.strength`, read-only) adds ribs instead.
   - Output: the relief's gradient (gx, gy) and its normalised Laplacian (`crease`).
4. **Cavity on D's grid.** A horizon march over h plus the sub-cell relief: 16 azimuths × radii of 2, 4, 8, 16 and
   32 texels. cavity = 1 − mean(sin θ), as `masks.sky_view` (Zakšek et al. 2011).
5. **Blur pyramid.** Separable Gaussian passes at σ = 1, 2, 4, 8 and 16 cells.
   - crest = Σ_s a_s tanh(−(G_s h − h) / (τ_s σ_s)), rescaled to −1..1;
   - `crest_fine` at one texel of D;
   - `valley` from flatness × lowness at each scale;
   - `n20` from the 20 m blur.
6. **Settle.** `solvers.detail.relax` with the cohesive ground at h (`Sc` huge, so nothing fails), a loose layer of
   0.5 m on top, repose 20°, 60 passes. settle = clamp(d / 0.5, 0, 2) / 2.
7. **Snowpack** (palettes with a snowline).
   - Snowfall s0 from altitude against `snowline_m` and from northness, then `relax` at a 38° slip-off for 100
     passes.
   - Melt by insolation, and below the line.
   - A second `relax` at 14° on the flow lines (flow > 0.6).
   - The pack is the larger of the two passes (Gaea's resting and flowing snow, combined by max).
8. **Drainage repaired on hero levels.** The specific catchment a is routed again (`flow_weights`, `route_area`,
   read-only through `core/gpu`, to the runner's convergence test).
   - Inflow is pinned from the parent across the border band.
   - The border is closed to outflow except where the parent's flow leaves.
   - `flow`, `wetness` and `channels` are recomputed with `masks.py`'s formulas and the main tile's norms.
9. **Freshness.** fresh is the largest of:
   - smoothstep on `spi` over bare ground;
   - (slope − atan Sc) / 8° where `Sc` exists (strata recipes write it);
   - a solver's `wear_recent` field where one exists (none does yet; section 8).
10. **Debris provenance** (`carry_src.glsl`).
    - Sources are bare rock (slope over the rock angle, no cover): src = zs and dist = 0.
    - Every other cell takes src, and dist plus the step, from its steepest upslope neighbour that is a source or
      carries one. Jacobi passes run until nothing changes, at most reach / texel.
    - Beyond `rock_toe_reach_m` (300 m), src fades back to the local zs.
    - Output: `src_dz` = src − h, and grain = clamp(dist / reach, 0, 1).
11. **Wind streaks** (palettes with a wind). Exposure max(0, n · w) on convex ground, blurred 10:1 along the wind.
12. **Pins.** Every map's outer 16 cells are blended to the parent's map with `masks.pin_band`'s ramp. Directions
    (`n20`) are blended as vectors.
13. **Gutters.** g texels around each tile (32 up to 1024 texels per level, 64 above) are filled from the parent's
    maps at those positions. The outermost level is edge-extended.
14. **Readback and encoding.** The maps are read back once per level and encoded per family. The cache stores the
    float16 arrays.

**The palette bake** (`surface/palette_bake.py`) runs on the same levels whenever a material is built:
- **Far colour C.** `expr_glsl.py` compiles the palette's weights, ramps, patches, tone and macro, and `noise.glsl`
  is Blender's own noise, so a term evaluated in the bake equals the same term in the shader. One kernel pass per
  level evaluates the layer stack per texel, with each layer's scan at its mean: coverages composited in order
  without scan heights, then each layer's colour logic. The strata column comes from `surfacing.strata_array`.
- **Provenance colour P.**
  - Sediment production: P = fresh × bare + a small background.
  - Source colour: c = the palette's bare-rock colour at zs.
  - Both are routed down the MFD weights (`route_colour.glsl`, route_area's Jacobi scheme with four channels):
    Q = P + Σ f Q_up, R = P c + Σ f R_up. Then C_down = R / Q, and the share is Q / (Q + Q0).
  - On hero levels the parent's values are pinned in as inflow, so a truncated catchment still carries its
    upstream colour.

**Twins.** Each kernel has a numpy twin in `surface/twins.py`. The gully filter's twin is
`solvers.detail.phacelle_noise` itself; the settle's is `detail.relax(backend='numpy')`. Parity is tested on a
96×80 field within 1e-4 of its range. The noise port is tested against Blender's Noise Texture node rendered
top-down, within 1e-3.

### 2.4 How the material reads them (`build/surfacing.py`)

Per pixel, in object coordinates (the terrain keeps an identity transform):

1. **The level.** inside_k = max(|x − cx_k|, |y − cy_k|) < S_k / 2 for levels k = 1..K−1, and L = Σ inside_k. The
   windows are the mesh's (`t.levels`), so L is the level of the ring drawing the pixel. Its cores are the same
   level.
2. **The level's constants.** Telescoping sums give them: q_L = q_0 + Σ_k inside_k (q_k − q_{k−1}). That covers the
   window (x0, y0, S), the texel, and the atlas rectangle (u0, v0, du, dv) of each of the two layouts (D/E, and the
   rest). It costs one multiply-add per level per constant, about 150 math nodes for nine levels.
3. **The coordinate.** uv = (u0 + du (x − x0) / S, v0 + dv (y − y0) / S).
4. **One read per atlas.** Image Texture, Linear, EXTEND, mipmapped, in the same state on every read.
5. **Decoding.** A multiply-add per channel, or a square for the thicknesses.

**No read of the parent.** Every map is pinned to its parent across the child's outer 16 cells, so at the window
edge the child's value is the parent's, and only sharpness changes across the band. The gutters hold real terrain
data, so Linear filtering and the mips at a tile's edge read real terrain data.

**`_Compiler.attr(name)`.**
- A baked map name returns its decoded channel.
- `slope`, `aspect`, `northness`, `eastness` and `insolation` are derived from D.
- `height` returns the object z.
- Anything else keeps the old Attribute node, so a mesh without a bake (the tests, hand-built meshes) still works.
- The window and atlas constants differ per terrain, so the reader is part of each terrain's material, as its
  terrain constants are today.

### 2.5 Normals

- **N_field** comes from D.rg. The macro normal adds the sub-cell relief: N_macro = normalize(−(h_x + s g_x),
  −(h_y + s g_y), 1). The palette option `detail_strength` sets s (default 0.5; `op_gully`'s calibration gives
  tilts of about ±27° at s = 1).
- **A guard.** Where N_macro · V < 0.05, it is pulled toward the geometric normal, so a grazing pixel never turns
  black.
- **Planar layers' scan normals** sit in N_macro's tangent frame (`_xy_tangent_normal(N_macro)` in place of the
  geometric normal).
- **The bump** of box and sector layers, ripples, canopy and strata relief goes on top through the Bump node's Normal
  input, as now.
- **`steep`, `steep_face` and the sector frames** read N_field and `n20`, not the interpolated vertex normal. This
  alone removes the chalk brow's teeth: the threshold cuts at the texel, not across 11.7 m triangles.
- **Shadows** stay geometric. The cavity in the albedo stands in for micro-shadowing (Battlefield 3's colour-map
  occlusion).

### 2.6 Formats, memory and samplers

Per level, with gutters (+13 %) and mips (+33 %):

| family | film, 1024² level | film, main or hero at 2× | hero quality, 2048² level |
|---|---|---|---|
| D (RGBA16F) | 12.6 MB | 50 MB | 50 MB |
| E (RGBA8) | 6.3 MB | 25 MB | 25 MB |
| each M (RGBA8, at most 1024) | 6.3 MB | 6.3 MB | 6.3 MB |
| F (RGBA16F, at most 1024) | 12.6 MB | 12.6 MB | 12.6 MB |
| C, P (RGBA8 sRGB) | 6.3 MB each | 6.3 MB each | 6.3 MB each |

**A film terrain of seven levels** (2 context, main, 4 hero), with four M atlases and F: D 277 MB, E 138 MB, M 176 MB,
F 88 MB, C and P 88 MB. That is about **770 MB**, against about 270 MB for a palette's 2k scans.
- At hero quality (seven levels of 2048²) it is about 880 MB: the masks stay at 1024, two cells a texel, still finer
  than today's vertices at stride 4.
- Atlas sizes: D at film is 2176 wide × about 12,000 tall (two context tiles share a shelf); at hero quality
  2176 × 15,200. Both are within the 32,768 limit.

**The sampler budget per material:**

| reads | samplers |
|---|---|
| six layers' scans (albedo_height and normal_rough_ao each) | 12 |
| strata column and its relief | 1-2 |
| D, E, C, P, LUT | 5 |
| M atlases (13-16 maps, by palette) | 3-4 |
| F (when a layer reads `strata_dz` or `src_dz`) | 0-1 |
| total | 21-24 of 30 |

`surface_group` refuses a material past 28 with the count and what to drop, as `MAX_IMAGES` does today.

### 2.7 Caching, images and saving

- **The bake cache.** `<terrain cache entry>/surface_<key>_L<i>.npz`, float16 maps.
  - key = SHA-1 of the entry's key, the bake's code (`surface/*.py`, `surface/kernels/*.glsl`) and its options.
  - The palette bake adds the palette's hash: `surface_<key>_pal<hash>_L<i>.npz`.
  - The files sit at the entry's top level, so `core/cache` counts them in its size, prunes them with the entry, and
    `clear()` removes them. Nobody edits `core/`.
  - A new bake of an entry deletes that entry's surface files beyond the newest two.
  - With `cache=False` the bake runs in memory.
- **The images** are made in memory at material build, colour space and `use_half_precision` set before
  `pixels.foreach_set` and never changed after (probes A2, A3). They are not packed.
  - `SurfaceData.save_images(folder)` writes them as OpenEXR (D and F half, as on the GPU) and 8-bit PNG (the RGBA8
    families), and switches the images to those files. A .blend that must render on another machine then
    references them, as it references the scan cache. Images loaded from files read right in probe A.
  - `terrain_surface(obj)` (api) rebuilds them from the cache when a .blend is reopened, as `terrain_height_at`
    rebuilds `height_at`.
- **The mesh** carries no mask attributes when a bake exists. Thirty FLOAT attributes on 3M vertices are 360 MB of
  RAM and seconds of build. An option keeps them for debugging.

### 2.8 What stays, what changes, and why

| piece | fate | why |
|---|---|---|
| `eido_terrain_surface`, its outputs, `surface_material` / `apply_surface` | kept; take `data=` | every caller keeps working |
| the mask language, `_Compiler`, `material_masks` | kept; masks come from atlases; new names (2.2) | the palettes are data agents already write |
| coverage composited in order; the height blend (`height_blend`, `blend_depth`) | kept; an overlay of the macro data comes before it (3.2) | measured with the shimmer probe; the crater's layering depends on it |
| `'Auto'` filtering (Cubic within 4-9 m, mipmapped Linear beyond) | kept on the scans | grazing sharpness near, stillness far |
| two-lattice de-tiling (`'rotate'`, `'offset'`) | replaced by `'hex'` on every planar read; `'offset'` stays an option | periodic within its patches (the talus dots 19 m apart) |
| the far read (`far_scale` 8, `far_contrast`, `macro_mod`) | replaced by the far colour hand-off (3.3, 3.7) once C lands; kept until then | an 8× magnified scan pattern, not the ground's own variation |
| Box projection on steep faces | replaced by aspect sectors (3.4) | the diagonal smear |
| the strata column, bed relief, ledges | kept; on cliff and ledge layers only by default; debris reads `src_strata` | bands on talus and benches read as contour stripes |
| streaks | kept; widths of 5-30 m on big walls; where = flow × (1 − fresh) | varnish curtains, not 2.5 m pinstripes |
| patches | kept, fewer; `where` reads terrain terms; footprint fade | world-noise blotches are the camouflage |
| `LANDSCAPE_MACRO` | replaced by a data macro ramp plus one residual octave of at most ±3 % (3.1) | macro colour from the place's own structure |
| canopy | kept; coverage from the plant layer's cover (4.7) | one forest near and far |
| ripples, ledges, damp | kept | they work |
| the rock dressing | kept; an optional toe bias (4.6) | its placement reads right |
| `pack_masks`, `mask_packs`, the Attribute path | kept for meshes without a bake | tests, built geometry |
| `surface_layers.py` | unchanged | a tool for built geometry, not the terrain |

---

## 3. The look

### 3.1 Colour follows the geomorphology at every scale

1. **Ramps, not constants.**
   - A layer key `ramp=dict(t='<expr 0..1>', stops=[(t, '#rrggbb'), ...])` reads its colour from a row of the
     palette's LUT at T. `colour` stays, as the ramp's centre.
   - The stops come from measured spreads, not one swatch. In each matched review view, sample the photograph where
     the layer covers the matched render (from the layer map), and record the Lab 10th, 50th and 90th percentiles
     per brightness bin.
   - Orthophotos of each reference DEM's own area, sampled per mask bin, would give our own SatMaps (NAIP for the US
     places, SWISSIMAGE for Lauterbrunnen). Fetching them is the lead's call: they are reference data, like the DEMs.
2. **Macro colour from the place's structure.** `options['satmap'] = dict(t='<expr>', stops=[...], amount)`
   replaces the world-noise macro octaves.
   - T comes from the terrain at 100-500 m: `valley`, `crest`, `wetness`, `insolation`, `fresh`.
   - It multiplies the albedo as a ratio around 1.
   - One residual noise octave of at most ±3 % stays.
3. **Provenance.**
   - Talus, scree, wash, fan and bar layers read the strata column at `src_strata` instead of zs + `strata_offset_m`.
     A red talus cone then runs down over grey beds, and the bands no longer climb the debris.
   - Sediment layers mix toward C_down by smoothstep(0.1, 1.5 m, deposit) × share.
   - Bars and channels take C_down a little paler, as sorted gravel is.
4. **Fresh against weathered rock.**
   - Rock albedo = column(zs) × mix(patina, fresh_gain, fresh).
   - Patina is set per palette: brown-black desert varnish, grey-green alpine lichen, orange iron stain.
   - Varnish streaks fall where flow × (1 − fresh); paler bleaching sits on `crest_fine`.
5. **The strata column colours cliffs only.** Cliff and ledge layers read it at zs. Debris reads it at `src_strata`.
   Soils and plateaus take their own ramps (Goosenecks' pale limestone rim, Toroweap's grey-green plateau).
6. **Tone from shape at every scale.** tone = a₁ crest + a₂ crest_fine − b (1 − cavity) − c crease, as × (1 + tone).
   This replaces the 20 m-only tone: crisp pale crests and dark creases at the field's scale are much of why World
   Machine and Gaea terrains read as eroded.
7. **The far colour C.** It makes the ground a unique colour per texel to the horizon, not a magnified scan.

### 3.2 Layers placed from many masks

**Terms per kind of layer** (the palettes' vocabulary from now on):

| layer kind | terrain terms |
|---|---|
| cliff, bare rock | slope (D), `crest` (ribs bare lower, chutes hold cover), `fresh`, `n20` and `curv_plan` across the wall (vertical structure), the column's hardness |
| talus, scree | `talus`, `rock_toe`, `grain`, `src_strata`, concave feet, the repose band only under walls |
| soil, regolith | `settle`, `valley`, `wetness`, −`crest`, `cavity` |
| sediment, wash, fans | `deposit`, `valley`, `channels`, `flow`, C_down |
| ground plants (grass, scrub litter) | `plants`, `insolation`, `wetness`, `settle`, the plant layer's `shrubs` and `canopy` |
| snow | `snowpack`, plus a dusting on N_final for powder and ash |
| sand | `sand`, `streak`, aspect against the wind (slip faces) |

**Rules.**
1. **Noise share.** A weight's noise terms span at most a quarter of its smoothstep window. The rest are terrain
   terms. fbm stays for raggedness at the metre scale.
2. **Transitions.**
   - First the overlay: cov′ = cov < 0.5 ? 2 cov d : 1 − 2 (1 − cov)(1 − d). Here d mixes the layer's scan height
     (near) with `settle`, `crest_fine` and `crease` (macro), faded by the footprint. Overlay leaves cov at 0 and 1
     unchanged (Frostbite's detail masks).
   - Then the existing height blend: a_i = w_i + h_i k, keep what lies within `blend_depth`, normalise.
   - Edges then follow the material's grain at metres and the landform's at tens of metres.
3. **Gradation zones.** A layer ends over a band driven by a terrain term, not at one line. Talus aprons fan into a
   floor by `grain` and `deposit`; scree thins into soil by `settle`.
4. **Footprint.**
   - footprint = view distance × pixel angle / max(|N · V|, 0.25). The pixel angle is a terrain constant
     (`pixel_angle`, default 1/1000 rad; the scene script passes its camera's).
   - Every `noise()` and patch term's deviation from its mean is scaled by smoothstep(1, 4, scale / footprint).
   - `fbm()`'s Detail input is set per pixel to log2(scale / (2 footprint)), clamped 0..5.
   - A term finer than a pixel then fades to its mean instead of shimmering.

### 3.3 Anti-tiling: hex tiling and distance blending

- **Planar reads are hex-tiled** (Mikkelsen 2022, from the published description).
  1. Skew world XY / hex_m onto a triangle grid.
  2. For each of the three vertices, take a random offset and a random turn from a White Noise Texture of the vertex.
  3. Read the texture at the three turned and offset coordinates.
  4. Weight each read by w⁷ × mix(1, 2h, 0.6), with h the read's own height, and normalise.
  5. Turn each normal map's xy back by the transpose of its turn.
  6. Assign reads to slots by vertex class, (v.x − v.y) mod 3. A slot's coordinate then jumps only where its weight
     is 0, so the implicit derivatives' mip jump is hidden.
- **Per-layer options.** `hex_m` defaults to the tile; `hex_rotate` is False for directional scans (ripples,
  ploughed fields).
- **Built once, used per layer.** The hex grid (skew, barycentric weights, vertex classes, hashes, turns) is one
  node group, built once and placed once per layer with its scale as an input; so are the sector frames and the
  level reader. In probe B, building the hex variants as loose nodes took 59-152 s of Python for 1,688-1,778
  nodes, against 25-26 s for today's 1,001 and the sector variant's 1,091 in the same process, on a shared machine.
  Node creation grows faster than the node count. The compiled shader is the same either way.
- **No new samplers:** all three reads of a map share its image and state.
- **No histogram preservation** (Heitz and Neyret): the luminance-weighted, sharpened blend keeps the contrast,
  and normals need none.
- **Distance blending of scales:**
  - near: Cubic within 4-9 m, hex-tiled;
  - mid: mipmapped Linear, hex-tiled;
  - far: the C colour × a faint luminance grain of the dominant layer's scan, wherever one texel of the level spans
    under 2.5 pixels.
- **Cost and look:** probe B (1.3).

### 3.4 Steep faces in any orientation: aspect sectors

Box layers read eight vertical frames turned to face the slope:
- φ is the azimuth of `n20` (the 20 m normal: a frame never twists on small bumps).
- The two nearest sectors k0 and k0 + 1 of 8 are read.
- Frame k: u along the strike t_k = (−sin φ_k, cos φ_k, 0); v up the dip, b = N20 × t_k, with N20 the 3D 20 m
  normal. A 45° slope and a vertical wall both keep the scan's true scale.
- Each sector has its own offset. The two reads are height-blended by the sector fraction.
- Within each frame the read is hex-tiled in (u, v), as the planar reads are (3.3). A sector read at true scale
  shows its tile's repeats on a big wall: probe B's 45° wall repeated a dark feature every 9-10 m, the tile. The Box
  projection's ghosting had hidden that.
- Planar below 37°, sectors above 47°, as now. The bump of the layer's own height, as now.

The stretch is at most 1/cos 22.5° = 1.08 across the face and none along the dip; the Box projection stretches 1.4-2×
on a face diagonal to the axes. The Box projection is retired.

**Probe B (1.3).** On the 45° wall at 70 m, the Box projection drew two half-weighted crack networks, each stretched,
soft and doubled. The sectors drew one network at the scan's scale, crisp, at the same frame cost. Hex tiling inside
the sectors is package 2's to measure: with three reads per sector it is six reads per map on steep faces.

Why sectors rather than biplanar mapping (Quílez): biplanar picks the two dominant axis projections and hides the
switch with explicit texture gradients, which shader nodes cannot pass. It also still reads a diagonal face through
axis frames. The sector blend is continuous by construction, and each frame faces the slope.

### 3.5 Relief below the cell, at every distance

- **The sub-cell gullies** enter through N_macro (2.5), and `crease` and `cavity` through the tone (3.1).
- **Distant ground** then shades every rill, gully and ledge the field resolves, plus the octaves below it. A smooth
  slope of 31 m triangles stops reading as plastic: the Schynige foreground, the canyon's approach plateau.
- **Near the camera** the scans' own normals take over: the detail's gradient fades by smoothstep(tile_m, 2 tile_m,
  λ_min). Its finest octave never doubles the scan's relief.

### 3.6 Snow and dust

- **`snowpack`** drives the snow layer: weight = smoothstep(0.05, 0.4 m, snowpack + a small edge noise). It fills
  gullies and benches with bare ribs between, which is the snowcap look. The current `_SNOW` expression stays as the
  fallback for a terrain without a bake.
- **Dusting**, per pixel: amount × smoothstep(cos θ₁, cos θ₀, N_final.z). It catches every ledge and grain the scans
  and the macro normal draw: alpine powder, volcanic ash.

### 3.7 The far material

- **Context rings** get material slot 1: D's normal, C's colour and roughness, and one faint grain read. No layers.
- **The seam.** In the main ring's outer 64 cells, the near material cross-fades to C, so the seam between the main
  and context rings is invisible.
- **Why.** Aerial frames, where the context fills much of the picture, get cheaper. The horizon is coloured by its
  own data.
- Its compile is a few seconds (probe B).

### 3.8 Keep

- **The impact crater's walls.** The Moenkopi red rim, the Kaibab buff ledges, the Coconino under the talus, and the
  bands broken by rock ribs and talus chutes. This is the case where today's terms already cross the contours,
  because the chutes cut the wall.
- **The rock dressing** on the talus and the rim.

Both must render unchanged or better side by side with `impact_crater_v5`.

### 3.9 The looks, recipe by recipe

Each recipe is checked in its matched review views beside the photographs (section 6).

| recipe (photographs) | what reads wrong now | what fixes it | keep |
|---|---|---|---|
| `canyon` (tw_03, tw_04, tw_07) | strata stripes on talus and benches; walls only horizontal bands; scrub and slickrock noise blotches; a lattice of pale dots on talus aprons; the brink wall's smear; the plateau one soil at eye level; far caprock reads as snow | cliff-only strata, debris at `src_strata`, washes by C_down (3.1); vertical structure from `crest`, `curv_plan` and `fresh`, varnish curtains under pour-overs; scrub by `settle` and `wetness`; hex tiling and the far colour; sectors; shrubs, grass tufts and stones as plants and rocks (4); the top formations' looks and a plateau plant tone | the bands on the cliffs: ledges, recesses, varied beds, varnish |
| `impact_crater` (meteor_crater_01-03) | the floor a flat disc; a crisp pale ring at the walls' foot; plain soil showing between talus and floor; the plain one soil, no ejecta blanket | floor ramps by `valley`, `settle` and deposit thickness, with crusted patches by `wetness`; aprons graded into the floor by `grain`; layers that give the base soil only the plain; an ejecta layer from the impact solver's deposit and talus outside the bowl; scrub as plants | the walls and the rim rocks (3.8) |
| `real_place` Lauterbrunnen (lauterbrunnen_01, 15) | the floor one lawn; forest hard-edged blobs and slope-foot lines; camouflage from the ridge; the walls' smear; forest a draped texture at eye level | pasture ramps by `wetness` and `valley`, and a mowing pattern; the forest from the plant layer (steep sides forested, meadows on the shoulders and terraces by `valley` at 100-500 m); sectors; spruce instances near, billboards mid, canopy far | the limestone walls' bedding, ochre zones, ledge plants; snow lying by shape |
| `alpine_valley` (lauterbrunnen_14, 15) | grey scree over most of the high ground; noise-isoline edges; smeared trough walls | alpine pasture and cushion plants on gentle ground above the treeline; scree only from `talus`, `rock_toe` and under walls; terrain-term edges; `snowpack`; sectors | - |
| `fluvial_range` (san_gabriel_mountains_02-04) | camouflage of chaparral, grass and granite; no denser brush in drainages or on north faces; no pale outcrops on ridges; the basin one material | chaparral continuous where `settle` holds and slopes stay under 40°; density by `wetness`, `channels` and `insolation`; pale decomposed granite on `crest` and `fresh`; bajada fans by `grain` and C_down | - |
| `incised_meanders` (gn_01, gn_05, gn_06) | walls a stack of even ledges; the plateau one red-brown soil | cliff-only strata with debris between ledges by `src_strata`; slickrock pavement where `settle` is thin and `crest` high; the pale limestone rim | - |
| `mesas_buttes` (mv_02, mv_04, mv_05) | the floor one material, flat at every scale; walls soft bands, no fluting; caps the floor's soil; the close wall's smear | sand sheets by `settle` and `streak`; lag gravel on `crest`; washes by `channels` and C_down; grey shale pedestals by `src_strata`; the macro normal; the caprock rim by `crest` at the texel; sectors | the orange-red floor, the red caps |
| `badlands` (bl_01-03) | the prairie an olive lawn; walls even painted bands; a cool blue-grey slope foot | tall golden grass as flora near and a ramp by `wetness` and `valley`; rills from the sub-cell gullies with `crease` darkening; `fresh` against weathered; the clay layer's colour and roughness | the pastel bands |
| `dunes` (namib_star_dunes_02, 03; great_sand_dunes_02) | sand mottled by world-noise blotches; interdune pans a flat sheet with a hard edge; grass as pale stains | sand colour from data only (stoss, lee and crest by aspect against the wind and `crest`), no macro octaves; gravel lag graded by sand thickness, damp margins by `wetness`; grass tufts as flora | the iron-red sand, the near ripples |
| `tower_karst` (guilin_karst_01, 03, 04) | uniform broccoli crowns; streaked forest on 60-85° flanks; a lawn sheen on the plain; dark pebbles | crowns from the plant layer (density by slope, soil and aspect; size by age); the forest layer read in sectors on steep flanks; paddy patterns and ramps by `wetness`; dressing colour | - |
| `sea_cliffs` (ss_*) | teeth along the chalk brow; the downland one green | slope from D (2.5); downland ramps and grass as flora near | - |
| `stratovolcano` (mount_fuji_04) | hard white snow splats on the lower cone; green gullies to the summit | `snowpack` in the gullies; vegetation cut by altitude in the ecotope and ramps | - |
| `cinder_cones` (sp_crater_01, 02) | a uniform black cone | oxidised red rims and fresh cinders by `crest` and `fresh`; rills from the sub-cell relief | - |
| `caldera` (crater_lake_01-03) | a forest and grass mosaic along the drainage | continuous conifer forest from the ecotope, grass only on the pumice flats; a caldera look | - |
| `rolling_hills` (palouse_hills_02-04) | fields too dark; flat polygons | field ramps from the photographs' tans; fields along the contours (`cells` with `z_stretch`) | - |
| `meadow` | swales too subtle | `wetness` and `valley` ramps; flora | - |

Geometry and camera items stay with their owners and are not surfacing: the canyon's lakes on the benches, the
crater's even buttresses, the alpine flutes, and the review cameras that face walls.

---

## 4. The plant-placement layer

### 4.1 What it makes

**Spots.** Per species, arrays of x, y, z (metres, Blender frame), yaw, scale, age (0-1), tint (0-1), the ground
normal (nx, ny, nz), the individual (variant) and the level that placed it.

**Per level, cover rasters for the material:**
- `canopy`: the placed crowns rasterised as discs, a fraction per texel;
- `canopy_expected`: 1 − exp(−density × π r_c²) from the tree density, everywhere;
- `shrubs`: the undergrowth density.

### 4.2 Ecotopes (`build/ecotopes.py`)

Per palette there is a species list, overridden per recipe and per place the way `RECIPE_LOOKS` overrides palettes.

**A species entry:**

| key | meaning |
|---|---|
| `name`, `kind` | tree, shrub, grass, forb or groundcover |
| `source` | `('seedthree', species, dials, seeds)`, `('flora', species, opts)` or `('ph', asset)` |
| `density` | a mask-language expression, plants per m² at full size |
| `size_m` | (min, max) by age |
| `age` | a Weibull shape and scale |
| `cluster` | κ (parents per ha), μ (offspring each), σ_m |
| `core_m` | the hard-core radius at scale 1 (flora's `footRadius`; a SeedThree crown's half-width) |
| `priority` | the placing order |
| `shade` | a tolerance 0-1 and a radius in crowns |
| `ground` | the material layer it implies (litter under conifers) |
| `max_radius_m` | how far from the focus it is placed |
| `lod` | `hero_m`, `billboard_m` |
| `align`, `sink` | how it sits on the ground |

The expressions read every mask and map, plus derived names:
- `soil` = deposit + talus + sand, scaled by `settle`;
- `insolation`;
- `dist_channel` (m), a distance transform of `channels`, through the existing `jump_flood` kernel or numpy;
- `shade`, from the plants already placed;
- `altitude` and the terrain constants;
- `ledge`, the strata relief's ledge channel at (x, y, zs), from `surfacing.strata_array`.

**Exclusions.** Every species stays off water (`water` > 0.05 m), snow (`snowpack` > 0.2 m), bare rock (`bare`
> 0.5), and talus or sand thicker than its roots hold, unless its own rule says otherwise: lichen, cushion plants
on ledges, dune grass on thin sand. The palettes' `plants` term (slope, wetness, sky view `occlusion`, the
treeline) is the base suitability. `masks.vegetation` is not, because it multiplies by `rock`, which reads nearly 1
on eroded landforms.

**Rules,** in the spirit of Far Cry 5's biomes and EcoBrush:
- forest on north-facing, concave, moist ground; grass on convex, exposed ground;
- riparian belts along the channels, falling off as exp(−dist_channel / L);
- shrubs at talus margins and `rock_toe` edges; cushion plants and lichen on ledges;
- krummholz near the treeline: smaller, sparser, clumped;
- avalanche tracks (flow on steep slopes) kept clear.

**What it fixes:**
- Crater Lake's continuous conifer forest, with grass only on the pumice flats;
- Lauterbrunnen's forested steep sides and meadow clearings on the shoulders;
- the San Gabriels' continuous chaparral;
- the Namib's interdune grass tufts;
- the canyon plateau's shrubs and grass (tw_04);
- karst forest density by soil.

**Sources.** SeedThree has beech, sycamore, apple, cherry, Douglas fir, dogwood, loblolly, pine, birch, aspen, maple,
sweetgum, tulip poplar, weeping willow, white oak, Joshua tree, saguaro, blackbrush, creosote and sagebrush. Flora has
grass and dry galleta grass, blackbrush, creosote, sagebrush, yucca, daisy, sunflower and corn, plus scanned grasses
and herbs. There is no spruce: Douglas fir dialled narrow stands in for Lauterbrunnen's spruce, and the reviewer judges
it beside lauterbrunnen_01.

### 4.3 Sampling (`build/plants.py`, numpy, no bpy)

1. **World cells.** Each species has a cell of 4 × its mean spacing, at least 8 m. A cell's seed hashes (ix, iy,
   species index, terrain seed). A camera move or a larger radius keeps every plant already inside.
2. **A Thomas cluster process per cell.**
   - Parents are Poisson(κ c²); each has Poisson(μ) offspring at a Gaussian σ.
   - Each offspring is kept with probability density / d_max: the rejection `dressing.place_rocks` uses.
3. **Hard core.** A candidate is rejected within core_m × scale of an accepted plant of the same or higher priority,
   through an occupancy grid (flora's `_occupancy_conflict` idea, vectorised). Cells go in row-major order, so runs
   repeat bit for bit.
4. **Order.**
   1. canopy trees;
   2. small trees and shrubs, density × (1 − shade (1 − tolerance));
   3. grass and forbs, thinned under canopy and boosted in gaps and at edges;
   4. ground cover.

   Shade-tolerant understory also seeds around the big trees (Ghost Recon Wildlands' cascade).
5. **Age and size.** Ages are drawn from the species' Weibull, sharing an offset within a cluster (stands); size =
   size_max (1 − e^(−3 age)).

### 4.4 Levels as payloads; LOD by distance

- **Placing by level** (Battlefield 3's coarse-to-fine payloads):
  - trees from the main level outward to `max_radius_m` (2-3 km), each at the finest level holding it;
  - shrubs on hero levels with cells of 4 m or less, within 300-500 m;
  - grass and forbs in the finest cores, within 60-150 m of the focus or along a camera path.
- **Distance thinning.** The smallest size kept grows with distance (`lod_m_per_m`, as the rocks).
- **Instancing LOD** (SeedThree's ladder):
  - LOD0 for spots within `hero_m` (40 m) of the focus path, chosen at build;
  - LOD2 cards within `billboard_m` of the active camera, switched per frame by SeedThree's `forest_group`.
    `forest_group` realises its near trees so each can sway, so `billboard_m` shrinks with density to keep about 300
    near trees: billboard_m = min(120, √(300 / (π density))). A spruce stand of 500 stems per hectare gets 44 m;
  - billboards beyond, dropping out between 0.8 and 1 × `max_radius_m` while the material canopy fades in (4.7).
- **Counts.** A forested 2 km radius at 500 stems per hectare is up to about 3 × 10⁵ billboard instances of four
  triangles. Instances, not realised geometry, as the rocks' 4 × 10⁵ are. `max_count` per species caps it.

### 4.5 The data format

Two files per terrain, `<base>.plants.json` and `<base>.plants.<species>.f32`. The records are headerless
little-endian float32, the convention `core/io.py`'s heightmap sidecar uses for r32:

```json
{"format": "eidoverse-terrain-plants/1",
 "frame": {"axes": "x east, y north, z up, metres (Blender)", "three": "position (x, z, -y)",
           "yaw": "radians about +z, counter-clockwise from +x; three rotation.y = yaw"},
 "terrain": {"cache_key": "...", "recipe": "alpine_valley", "seed": 7, "levels": [[x0, y0, side, cell, n], ...]},
 "focus": [[x, y], ...], "seed": 7, "ecotope": "<name>#<hash>",
 "species": [{"name": "spruce", "kind": "tree",
              "source": {"seedthree": "douglasFir", "seeds": [11, 23, 37], "dials": {"crownShape": 1}},
              "size_m": [8, 35], "count": 10234, "file": "<base>.plants.spruce.f32",
              "fields": ["x", "y", "z", "yaw", "scale", "age", "tint", "nx", "ny", "nz", "variant", "level"]}]}
```

- **Where it is saved.** In the terrain cache entry, keyed by the ecotope's hash, seed, focus and the plant code;
  `Terrain.save` writes it beside the .npz.
- **The three.js contract.** A placer reads the JSON and fetches each .f32 as a Float32Array (stride = len(fields)).
  It grows the named SeedThree species and seeds with SeedThree's own generators, and instances them as one
  InstancedMesh per variant and LOD. No Blender format and no glTF are involved.
- **SeedThree's attribute names** (`st_rot`, `st_scale`, `st_ground`) are built from these fields on the eidoverse
  side.

### 4.6 Instancing in Blender (`build/plant_instances.py`)

- **Flora.**
  - One `create_flora` stroke per species and individual, with `placements` [[x, y, s]] in Blender metres
    (`create_flora` turns them into flora's three-space itself) and `height_fn` = the terrain's height_at.
  - The plant is grown once per stroke and instanced by Geometry Nodes, with flora's wind and pushers.
  - Scanned plants (`ph:`) take the same path.
- **SeedThree.**
  - Per species, N individuals (seeds) are grown once through `eidoblend.trees.make_seed_tree(level='ALL',
    billboard=True)`: its LOD ladder and its card and billboard bakes, cached on SeedThree's side.
  - Per individual, a points mesh carries `st_rot` = yaw, `st_scale` = scale and `st_ground` = z, with
    `seedthree.bl.forest.forest_group(name, near LOD2 collection, billboard collection, billboard_m, half_h)` on it.
    It is set up the way SeedThree's `make_forest_ring` sets up its grove: a near object and a billboard object on
    the same points. That function's slots are a fixed ring, so the eidoverse side builds its own points and source
    collections, copying the pattern rather than importing private helpers.
  - A second object carries LOD0 for the hero spots.
  - Everything goes through SeedThree's public functions. SeedThree's main branch never changes for eidoverse.
- **Rocks and deadwood under trees** come from dressing specs on the litter.
- **Toe bias** (`dressing.py`, optional per palette): the smallest rock grows toward the toe by `grain`, the sorting
  real rockfall shows. With it off, the rocks are placed exactly as now.

### 4.7 The far field

The same density drives both halves:
- **Inside the instanced radius,** the canopy layer's coverage becomes the forest floor (litter), and its stand-in
  crowns are off, because the trees there are real.
- **Beyond it,** the crowns cover `canopy_expected`, with clumps at the cluster process's σ.
- **The hand-off.** The billboards drop out and the material crowns fade in over the same 0.8-1 × radius band.

So the forest's edge, density and clumping are one forest from 1.7 m to the horizon, and the material and the
instances never draw two forests over each other.

---

## 5. The packages

### 5.1 Rules for every package

The lead's standing block applies on top of these.

- **Ownership.**
  - You own the files listed for your package and nothing else. Read anything; edit only yours.
  - Changes another package needs go in your report as a request to its owner.
  - Tests go in `blender/tests/terrain/<package folder>/`, outputs in `blender/tests/terrain/out/<package folder>/`.
- **Never touch the cache keys.** Nobody edits `core/*.py`, `kernels/*.glsl`, `solvers/*.py`, `run.py`,
  `recipes/*.py` or `masks.py`: every cached terrain would regenerate. Per-recipe looks go in `RECIPE_LOOKS` and the
  ecotopes' recipe table. Recipe modules stay as they are.
- **Pieces that already exist:** reuse them, never rebuild them worse. The node group and its options, the mask
  language and `palettes.evaluate`, `masks.pin_band` and `gaussian_blur`, `detail.phacelle_noise` and `relax`, the
  routing kernels, `dressing.place_rocks`, flora's placements, SeedThree's `forest_group` and LOD ladder, the shimmer
  probe, the review views and boards.
- **GPU.** Every Blender run that dispatches kernels or renders is a GPU job: 4 GB VRAM, 12 GB RAM cap, through the
  shared slots. Renders are at most 960×540 at 16 samples, under `make_sky` daylight.
- **Looking.**
  - Look at every image you produce, close up where a defect would show, beside the photograph of the same place
    from the same camera.
  - Name defects concretely.
  - Numbers support the eye. They are never the target.
- **Stopping.** When your acceptance reads right, stop. Refinements go in the report.
- **Visible edits.** Edit with the Edit and Write tools.

### 5.2 The packages

| # | package | owns | builds | GPU |
|---|---|---|---|---|
| 1 | **Surface data** | `terrain/surface/*` (new), `blender/tests/terrain/surface_data/` | sections 2.2, 2.3, 2.6, 2.7: the registry, the bake and its kernels, twins, atlases and images, the cache, the palette bake (C, P), the mask language in GLSL and the noise port | yes: short kernel runs, and renders for the noise parity |
| 2 | **Material** | `build/surfacing.py`, `build/mesh.py`; in `blender/tests/terrain/surfacing/`: `test_surfacing.py`, `test_shimmer.py`, `shimmer_metric.py`, `bench_material.py`, and new tests | sections 2.4, 2.5, 3.3-3.7: the reader, normals, hex tiling, sectors, the footprint, the far hand-off and far material, material_index per ring, `strata_array` | yes: compiles, benches, renders |
| 3 | **Look** | `build/palettes.py`, `blender/tests/terrain/surface_look/` (new) | sections 3.1, 3.2, 3.6, 3.9: new mask names in `known_mask`, ramps and `ramp_rows`, satmap, provenance, patina and freshness keys, `snowpack` snow, cliff-only strata, terrain-term weights, every recipe's look against its photographs, the photograph colour sampler | yes: renders of sixteen recipes |
| 4 | **Plants** | `build/plants.py`, `build/ecotopes.py`, `build/plant_instances.py` (new), `build/dressing.py`, `blender/tests/terrain/plants/` (new) | section 4: rules, sampling, spots and their format, cover rasters, flora and SeedThree instancing, LOD, the far-field hand-off, the toe bias | yes: SeedThree bakes, renders |
| 5 | **Judge and integration** | `blender/tests/terrain/surfacing_judge/` (new); in `blender/tests/terrain/surfacing/`: `review_views.py`, `review_board.py`, `render_places.py`, `layer_map.py`, `sheet.py`, `_place.py`, `calibrate_light.py`; `terrain/api.py`, `terrain/__init__.py`, `tools-guides/terrain-surfaces.md`, the `docs/TOOLS.md` row | section 6's measures and boards from wave 1; camera fixes for views that face walls; then the wiring: `make_terrain(..., surface='auto', plants=None)`, `Terrain.surface`, `Terrain.plants`, `terrain_surface(obj)`, the ring mesh built without mask attributes when a bake exists, save and load; the guide; the review videos | yes: judge renders and videos |

### 5.3 Interfaces

- **Package 1 provides:**
  - `bake_surface(terrain, palette=None, options=None, cache=True, extra=None) -> SurfaceData`.
  - `SurfaceData.levels`, `.layouts` (per family: per level the atlas rectangle and texel), `.maps(level) -> {name:
    array}`, `.at(name, x, y)` (bilinear on the finest level, like `MaskSet.at`), `.channel(name) -> (family,
    channel, decode)`, `.images() -> {family: Image}`, `.save_images(folder)`.
  - `extra={'canopy': [array per level], ...}`, for the plant layer's rasters.
  - `maps.MAPS`, the registry.
  - The first deliverable is a `SurfaceData` that packs the existing masks into atlases with pins and gutters and
    no new kernels, so package 2 can build on it at once.
- **Package 2 provides:**
  - `surface_material(..., data=SurfaceData)` and `apply_surface(obj, ..., data=)`.
  - `strata_array(column, ...) -> (rgba, z_lo, z_hi)`, the numpy half of `strata_image`, for packages 1 and 4.
  - Options: `detile='hex'`, `hex_m`, `hex_rotate`, steep `'sector'`, `detail_strength`, `far_handoff_px`,
    `pixel_angle`.
- **Package 3 provides:**
  - Palette keys: `ramp`, `satmap`, `provenance` (`src` and `down` amounts), `patina`, `fresh_gain`.
  - `palettes.ramp_rows(pal) -> (rows (R, 256, 4) sRGB, {ramp: row})`. Package 2 makes the LUT image; package 1
    bakes C with the same rows.
  - `known_mask` accepts the names in `maps.MAPS`.
  - New terrain constants in `CONSTANTS`: `sun_azimuth_deg`, `sun_elevation_deg` (insolation), `wind_azimuth_deg`
    (streaks, slip faces) and `pixel_angle` (the footprint).
- **Package 4 provides:**
  - `plan_plants(terrain, ecotope='auto', focus=None, radius_m=None, seed=0, data=None) -> PlantSpots`.
  - `PlantSpots.save(base)`, `.load(base)`, `.cover(level) -> {'canopy', 'canopy_expected', 'shrubs'}`.
  - `instance_plants(spots, terrain, collection=None, lod=None) -> {species: objects}`.
- **Package 5 provides:**
  - `make_terrain(..., surface='auto', plants=None | 'auto' | dict)` and `Terrain.surface`, `Terrain.plants`.
  - `terrain_surface(obj)` for a reopened .blend.
  - The judge commands (section 6).

### 5.4 Acceptance: looked at beside the photographs first, measured second

**Package 1: Surface data.**
1. Map sheets, each map beside the hillshade at the main and one hero level: Toroweap, Lauterbrunnen, Meteor Crater,
   Great Sand Dunes and the Badlands (`real_place`), and the `canyon` and `alpine_valley` recipes. Each sheet is
   looked at and described:
   - `crest` picks ridges, rims and ribs at their scales;
   - `cavity` and `crease` pick the creases;
   - `settle` marks benches, ledges and slope feet;
   - `snowpack` fills gullies and benches with bare ribs between;
   - `src_strata` puts each talus below its beds;
   - C_down carries the upstream rock's colour into washes and fans;
   - `fresh` marks gullies and scars, not every slope.
2. Every kernel equals its twin (96×80, within 1e-4 of the range). The noise port equals Blender's Noise Texture node
   within 1e-3. `expr_glsl` equals `palettes.evaluate` on every palette's noise-free expressions within 1e-5.
3. Seams: at every window edge, every map's child equals its parent within 1 % of the map's range. A top-down render
   of D across a window edge shows no line at 2× zoom.
4. Hero drainage: at the `fluvial_range` canyon_road focus, the trunk's catchment stays within 15 % from the main
   level to the finest hero level (the fluvial package measured 37 → 1.5 km² there).
5. Cost recorded:
   - at most 1.5 s per 1024² level (3 s at 2048²), at most 12 s for a seven-level film terrain cold;
   - a cache hit in at most 2 s;
   - the palette bake in at most 3 s.

**Package 2: Material.**
1. Reader parity: a top-down emission render of maps read through the material equals the bake's arrays, within
   1/255 for RGBA8 maps and 1e-3 relative for 16F, on every level. Grazing renders across each window edge show no
   seam ring at 2× zoom.
2. Sectors: the canyon's brink_down right-hand wall, and a 45° wall on the bench scene, beside the Box projection, at
   2× crops. There is no smear, no seam where sectors meet, and no visible repeat of the tile across a big wall.
3. Hex tiling: close-ups at 2-20 m (2× crops) show no mip seam lines. The repetition peak on the canyon plateau,
   talus aprons and Lauterbrunnen floor is at most 0.12 (talus today 0.17-0.22; photographs 0.03-0.11).
4. The shimmer probe scores no worse than the old material's + 0.02, and the review video frames hold still in
   motion.
5. Seven Sisters `from_the_sea`: a continuous chalk face, no teeth.
6. Cost on the bench scene, beside the old material in one process. A material switch can trigger a shader recompile:
   probe B's run cycling seven materials spent minutes recompiling. So every timed frame follows a discarded
   warm-up frame, never a switch. `bench_material.py`, which alternates materials frame by frame, is updated to do
   the same.
   - material at most 2.0 s per frame;
   - near material compile at most 1.5 × the palette's today, cold, in one process; far material compile at most
     10 s;
   - the viewport at one sample at 5 fps or more. A material at 1 fps is broken, not heavy.

**Package 3: Look.**
1. Every recipe's matched views beside the photographs (boards: photograph, v-current, new, layer map) read as the
   place, item by item against section 3.9's table, described per view.
2. The crater's walls and the rocks are unchanged or better beside `impact_crater_v5`.
3. Measured with package 5's tools:
   - the largest one-material region at most 35 % of the ground (except a place whose photograph is one material:
     dune sand, a snowfield);
   - the layer boundaries' height-line index (the audit's contour index) at most 0.72, on all ground and on slopes
     over 25°, with the strata beds' own edges excluded (today 0.77-0.94 on walls; 0.64 is random);
   - ground colour against the photograph: ΔE of the means at most 10, and the spread of 32 px block means within
     0.6-1.6 of the photograph's.

**Package 4: Plants.**
1. Spots are deterministic: the same inputs give the same bytes, and a larger radius keeps the inner spots. No two
   plants are closer than their hard core. Density per hectare lies within the ecotope's range. No plant floats or is
   buried (height_at at every spot).
2. Renders beside the photographs show plants where the photographs show them, as objects near and canopy far, with
   no hand-off ring at 2× zoom:
   - Lauterbrunnen floor_lischmaad and ridge_schynige;
   - canyon approach_walk;
   - caldera rim_east;
   - fluvial_range canyon_road;
   - dunes interdune_floor.
3. Eye-level frames render in at most 8 s at 960×540, 16 samples.
4. A plain JavaScript reader (Node, as `loft_dump.mjs` runs: fs and Float32Array) round-trips the format.

**Package 5: Judge and integration.**
1. The measures reproduce the audit's baseline numbers on the 11-13 renders (coverage, height-line index, repetition)
   within 10 %.
2. Every recipe's boards and review videos exist for the final state.
3. `make_terrain(..., surface='auto', plants='auto')` runs end to end and through save and load.
4. The guide's examples run.

### 5.5 Waves

1. **Wave 1, all at once:**
   - package 1: atlases of the existing masks first, then the kernels;
   - package 4: planning on the numpy masks `t.masks` already gives, and instancing;
   - package 5: the measures and baseline boards on today's renders;
   - package 3: everything that needs no new map (cliff-only strata, ramps on today's masks, recipe looks), while
     the attribute path still works.
2. **Wave 2, as soon as package 1's first `SurfaceData` lands:** package 2. Packages 3 and 4 move to the new maps as
   package 1 adds them.
3. **Wave 3:** package 5's integration: wiring, guide, every recipe's boards and videos. One reviewer reads every
   board and video beside the photographs and sends concrete defects to the owning package once.

---

## 6. The judge protocol

**The views.** For every recipe, the review's matched cameras (`out/review/views_plan.json`: 50 views over 16
recipes, 45 of them matched to a photograph), plus whichever of these the recipe lacks:
- an establishing aerial;
- a low oblique;
- a 1.7 m eye view from `t.viewpoint`.

All are rendered at 960×540, 16 samples, under `make_sky`, with the rocks and plants.

**The boards.** Per view: the photograph | the render before | the render after | the layer map (`debug='layers'`).
Two crops at 2× where a defect would show (walls, slope feet, edges, near ground).

**The read.**
- The reviewer, an environment artist's eye, writes one paragraph per view naming what reads and what doesn't, against
  the checklist below.
- The bar is World Machine and Gaea: the look of a colour map at the heightfield's texel, made from erosion data.
- Numbers come second and support the read.

The checklist:
1. Colour follows the landform: boundaries at slope breaks, gullies, ridges and fans, and across the contours.
2. No flat single material over a third of the ground.
3. No tiling at any distance.
4. Relief reads at every distance: rills and gullies at mid distance, crisp crests and dark creases.
5. Debris and sediment carry their source's colour.
6. Steep faces show no smear and have vertical structure.
7. Plants stand where the place grows them, as objects near and canopy far, as one forest.
8. Nothing changes as the camera moves: no shimmer, no seam ring, no LOD pop. Checked in the videos.

**The measures** (`blender/tests/terrain/surfacing_judge/`, numpy and Pillow):

| measure | how | target |
|---|---|---|
| one-material share | on the main tile (the layer weights evaluated on its maps, composited as the material does) and in each frame (the layer map): the share where one layer holds ≥ 90 % of the weight, and the largest connected region one layer dominates (the audit's `pure` and `largest`) | largest region ≤ 35 % of the ground, unless the photograph is one material |
| within-layer variation | the spread of 32 px block mean luminance inside one layer, against the photograph's ground blocks | at least half the photograph's |
| repetition | the second peak of the 2-D autocorrelation of high-passed luminance in ground crops (the audit's measure) | ≤ 0.12 (photographs 0.03-0.11) |
| height-line index | on the main tile, the weight-gradient-weighted mean of \|cos\| between each layer's exclusive weight gradient and the height gradient (the audit's contour index): 1 when every boundary is a height line, 2/π = 0.64 at random; on all ground and on slopes over 25°, the strata bed edges excluded | ≤ 0.72 |
| colour | Lab mean and the a*/b* spread of the ground region against the photograph's; the hue relationships between regions (talus against cliff, floor against wall) in the photograph's direction | ΔE ≤ 10; spread ratio 0.6-1.6 |
| shimmer | the existing probe | ≤ the old material's + 0.02 |
| seams | the mean colour difference across each window edge's band in grazing renders | ≤ 2 ΔE |
| plants | stems per hectare against the ecotope's range; the trees' pair correlation g(r): clustered at σ, inhibited below the core | in range; the right shape |
| cost | seconds per frame, compile seconds, VRAM | section 7 |

**The videos.** Per recipe, an 8 s aerial orbit and a 6 s eye-level dolly (`judge/video.py`), H.264 High yuv420p,
checked with ffprobe. They are watched, for shimmer, seams and pops.

---

## 7. The performance budget (this machine)

| what | budget | basis |
|---|---|---|
| bake, per 1024² level | ≤ 1.5 s (kernels ≤ 0.3 s, readback and encoding the rest) | about 0.06 ms per 3×3 pass at 1024² and 18.5 ms per RGBA32F readback (DESIGN.md 1.2); routing to convergence 0.1-0.2 s |
| bake, per 2048² level | ≤ 3 s | 0.23 ms per pass, 148 ms per readback |
| bake, a seven-level film terrain, cold | ≤ 12 s | |
| bake, cache hit | ≤ 2 s | npz loads plus atlas assembly; the probe filled a 1088×16,448 float image in 0.17-0.43 s |
| palette bake (C, P) | ≤ 3 s | one far-colour pass per level; colour routing as A |
| plant planning | ≤ 10 s for 10⁴ trees and 10⁵ shrubs | numpy, like the rocks (400k) |
| plant instancing | ≤ 20 s, plus SeedThree's one-time growth and bakes (cached on its side) | |
| near material compile, cold | ≤ 1.5 × the same palette's today, measured cold in one process; never over 120 s | today 15-110 s cold, by palette and machine load; probe B: hex 87 s, hex + sectors 117 s, today's desert material and its data-read variants 83-110 s under load. The driver caches a compiled shader: the same GLSL again took 3-8 s |
| far material compile | ≤ 10 s | probe B: 3.2 s cold, 0.6 s cached |
| material build (Python creating the nodes) | ≤ 30 s | today 12-26 s for 1,001 nodes; probe B's hex variants as loose nodes 59-152 s, hence the node groups of 3.3 |
| material cost per frame, bench scene, 960×540, 16 samples | ≤ 2.0 s | today 0.70-1.31 s by palette; probe B on the desert material (1.0 s today): hex, sectors or both 0.9-1.5 s, the far material 0.03 s |
| a review frame, 960×540, 16 samples | aerial ≤ 3 s; eye level with plants ≤ 8 s | today: aerials 1.5-2.4 s, eye views 3.5-6.0 s |
| a review frame, 1920×1080 | ≤ 4× the 960×540 frame | pixel count |
| viewport | ≥ 5 fps at one sample | a 1 fps material is broken |
| data texture memory | ≤ 900 MB at film quality, ≤ 1.2 GB at hero quality | 2.6 |
| VRAM per render | ≤ 4 GB (the slot) | data + scans (≈ 270 MB) + EEVEE + geometry |

---

## 8. Risks and open questions

1. **Compile time.** The reader adds about 150 nodes, hex tiling about 200 per planar layer (probe B: 1,001 → 1,688
   nodes for three planar layers), sectors about 30 per box layer. Compiles already take 15-110 s cold.
   - Package 2 measures first, cold, in one process. The driver caches a compiled shader, so a repeat of the same
     GLSL is not a compile.
   - If a palette passes 1.5 × its old compile, the levers in order: share the hex grid across layers with the same
     `hex_m`; drop the far reads; move patches into C; the far material for the context rings.
2. **The Bump node evaluates its height input three times.** The cheap coverages now read atlases, so three times
   the reads under the bump. Package 2 measures it; the lever is to weight the bump by atlas values read once,
   outside the bump's input.
3. **The hero inflow defect** in the level runner. The bake routes the hero levels' drainage again with pinned inflow
   (2.3, step 8), so the material and the plants get right `flow`, `wetness` and `channels`. The geometry's valley
   floors still need the fluvial package's fix in the runner, which is outside this round.
4. **Near against far colour.** If C and the near material differ, a ring shows at the main/context seam and at the
   hand-off distance. Mitigations: the parity tests (the shader's own noise in the bake), the 64-cell cross-fade, and
   the hand-off by texel and pixel ratio rather than a fixed distance.
5. **Mip bleed across atlas tiles** at grazing angles past 32-64 gutter texels. Mitigations: the gutters hold real
   data, and the level structure keeps minification under about 4×. Package 2's seam probe looks for it.
6. **Ramps from photographs can drift back to judging by eye.** Mitigation: measured Lab spreads per layer region.
   Orthophotos per mask bin are the stronger source, if the lead fetches them.
7. **No spruce in SeedThree.** Douglas fir stands in. If it reads wrong beside lauterbrunnen_01, the options are a
   SeedThree preset dialled on the eidoverse side, or flora shrubs and scanned plants near with billboards far.
8. **No recent-wear field.** No solver writes `wear_recent`, so freshness comes from stream power and threshold
   exceedance. A post-pass that differences h between a run's last epochs would give real freshness. That touches
   the runner, outside this round.
9. **VRAM.** Data textures of about 0.8-1.1 GB beside other jobs on a shared GPU. The levers: masks capped at 1024,
   F only when read, D at the cell at hero quality.
10. **Licences.**
    - Blender's shader noise is GPL-2.0-or-later, compatible with this AGPL-3.0 repository.
    - Hex tiling is implemented from the published description (Mikkelsen's demo is MIT; keep its notice if any code
      is copied).
    - The gully filter is our own `detail.py` port.
    - The Shadertoy erosion-noise ports (CC BY-NC-SA) are not to be copied.
11. **The cache.** Every new file lies outside the field cache's globs, and `masks.py` does not change, so no
    terrain regenerates for this round's work.

---

## Appendix: the probes behind section 1.3

Scripts and logs are in the lead's scratch folder, not in this repository; the numbers are here.

| probe | what it ran | result |
|---|---|---|
| A, sampler limits | a 24 px emission plane, one material per case, 1 sample; a failed material renders magenta and logs "uses too many samplers (n/32)" | 28, 29, 30 distinct images compile; 31 (33/32) and 32 (34/32) fail. 13, 14, 15 two-tile UDIMs compile; 16 fail (34/32). 14 images + 7 or 8 UDIMs compile, + 9 fail (34/32). 28 images + one 7-tile UDIM read 12 times compile. 28 images + a Cubic, a Closest, an EXTEND and a CLIP read of four of them fail (33/32). A UDIM's tile 1003 reads its own value with Linear, Cubic and Closest |
| A2 and A3, images made in memory and float precision | as A, the material emitting (v − ⌊v⌋) × 100, so the half-float film does not hide the texture's own rounding | half (default): 1234.567 → 1235, 37.123 → 37.125. 32-bit (`use_half_precision` False): 1234.567 and 37.123 arrive intact. Colour space set after the pixels: 0 at every texel. A 1088 × 16,448 float atlas: its top tile read exactly; filled in 0.17-0.43 s. Packed 4 × 4 float image: 1.0 at every texel on the GPU, though the CPU pixels stay intact (a CPU-only check). The GPU reports OpenGL, max texture size 32768, 2048 layers, 32 fragment samplers |
| B, frame cost and look | the material bench's scene plus a 45° diagonal wall, 960×540, 16 samples, AgX; the desert_sandstone material as it is, with hex tiling on its planar layers, with sectors on its box layers, with both, plus twelve reads of six RGBA16F atlases (seven levels of 1024 with 32-texel gutters, the level chosen per pixel), and a far material of those reads alone | Per variant, one process: build, a warm-up frame, four timed frames, then clay beside it the same way. Material per frame, best frame minus best clay: today's 1.03 s (1,001 nodes); hex 1.50 s (1,688); sectors 1.03 s (1,091); both 0.92 s (1,778); far 0.03 s (142 nodes). Cold compiles 83-117 s for the full variants, 3.2 s for the far material; a repeated GLSL 2.5-8 s. A first pass that cycled seven materials frame by frame stalled for minutes recompiling, so timed frames never follow a switch. Look: on the 45° wall the Box projection drew two soft, doubled crack networks; the sectors drew one crisp network at the scan's scale, repeating every 9-10 m (hence hex inside the sectors). Hex tiling changed the planar ground's layout with no seam line at 3× zoom; this view had little planar ground. A run in A/B passes, every variant revisited each pass after a warm-up so the load falls on all alike, was stopped before its passes: the machine's CPU stood at 100 % and today's material alone took 127 s to build. That protocol is the one for package 2 |
