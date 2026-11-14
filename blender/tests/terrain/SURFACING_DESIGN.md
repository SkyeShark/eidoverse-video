# The terrain's surface and its plants: design

Blender edition (`blender/eidoblend/terrain/`), 2026-11-13, revised 2026-11-14. One design, for the agents who build
it and the lead who reviews it. It builds on `DESIGN.md` (the landforms) and changes how the ground is coloured,
shaded, tiled and planted. The levels, solvers, recipes and masks stay as they are; the ring mesh's density is
measured against stride 1 before the material is built on it (8.12).

---

## Changes since the first version (2026-11-14)

An independent critique of the first version raised nineteen issues; every one is answered here, by a change or, where
I disagree in part, with the evidence in section 8. Each row names the change, the sections it rewrites and the
packages it touches. "Interface" marks a change to section 5.3, a map's name or meaning, a format or file ownership;
everything else stays inside one package. Packages already building: reconcile against this table first.

| # | change | sections | packages | interface |
|---|---|---|---|---|
| 1 | **Steep faces: fixed sector frames.** u = P·t_k and v = P·b_k, b_k a fixed up-dip axis tilted 65°: constant linear maps of the world position. Two slots (even and odd sectors) are weighted by the azimuth of the field normal from D; a slot's weight is exactly 0 within 4.5° of where it changes sector. The first version's v = P·(N20 × t_k) turned with the 20 m normal: walls drawn 3-4.5× off scale (p50) | 3.4, 1.3 | 2 | none |
| 2 | **The reader reads each atlas twice:** even levels in one slot, odd levels in the other, same image and sampler state, so no sampler is added. A slot changes level only at a window edge: outside it the slot's weight is exactly 0 by the nesting, and inside it a dead band of 3 pixel footprints (capped only by the room before the next finer window) holds the finer level's weight at exactly 0. Renders use 16× anisotropic filtering. One read per atlas made every 2×2 quad on a window edge read the coarsest mips | 2.4, 2.6, 1.3 | 2 (1: gutters stay ≥ 32 texels, as built) | none |
| 3 | **The far hand-off is one monotone distance per material.** It fades in over D0 to 1.5 D0, D0 = main texel / (2.5 × pixel angle), never inside the hero windows, on every ring. C is the near material's expectation there: every colour term, 4 × 4 sub-samples per texel, scans at their mean colour and height, on the ring mesh's own surface. A footprint fade widens a smoothstep by the faded noise's spread instead of flattening the noise | 2.3, 3.2, 3.3, 3.7 | 1, 2 | option `far_handoff_px` becomes `far_m` (package 2's own) |
| 4 | **The context rings keep the near material.** The far blend is per pixel. The cheap far material goes only on rings lying beyond 1.5 D0 from every camera the caller passes. Three eye-level views that stand on context rings join the acceptance | 3.7, 5.3, 5.4 | 2, 5 | `apply_surface(..., cameras=None)`, `make_terrain(..., cameras=None)` |
| 5 | **Costs re-based on package 1's measurements.** The atlas files are the cache every process loads. Surface files move to their own cache root with their own cap, one bake per terrain, 8-bit maps stored as uint8. Hero re-routing warm-starts from the parent's area. P is routed once over the converged weights, or deferred | 2.3, 2.7, 7 | 1 | cache location only |
| 6 | **`settle` leaves gentle ground.** It reads 0.5 ("unmoved") on almost all ground under 10-15°, so gentle-ground rules read −`crest`, `valley`, `cavity` and `wetness` instead. settle stays for benches, ledges and slope feet. Package 1's sheets check every map's spread under 15° and parent/child agreement | 2.2, 3.2, 3.9, 5.4 | 1, 3, 4 | meaning documented; encoding unchanged |
| 7 | **One forest rule.** The ecotope's tree density makes `canopy_expected` on every level whenever the palette has a canopy layer, with plants or without. The palettes' forest and chaparral weights read it; their crowns read `canopy_far`. A layer's old expression stays as `fallback` for a material without baked data | 4.7, 3.2, 5.3 | 3, 4, 5 (1 registers `canopy_far`; 2 reads `fallback`) | `plants.expected_cover(...)`; layer key `fallback`; map `canopy_far` |
| 8 | **The measures become diagnostics.** They sit beside the boards, each compared with the same measure on the place's reference, and the board read is the only pass. "Largest region ≤ 35 %" becomes "no larger than the reference's own share"; the repetition test gains a high-frequency energy floor | 5.4, 6 | 5, 3 | none |
| 9 | **Plants.** Shrubs, grasses and forbs are never realised; only trees that sway are realised near, under the 300-tree cap. Hero LOD0 is picked per frame by the camera, at most 64 trees. Billboards are matched to LOD2's shading before use. Densities read level-independent terms, checked either side of each window edge. The spot fields each instancer honours are listed, and flora's occupancy list is reset after a plan's strokes | 4.2, 4.4, 4.6, 5.4 | 4 | none |
| 10 | **The LUT is read Closest** (its own image: no sampler added) | 2.6 | 2 | none |
| 11 | **`fresh` no longer clears the varnish.** On steep ground it is threshold exceedance only; stream power counts only on ground under 30° | 2.2, 2.3, 3.1 | 1, 3 | meaning of `fresh` |
| 12 | **The cache-key rule is written down,** with a test of every recipe's key against HEAD | 5.1, 5.4 | 3 (2: new options default in `surfacing.py`) | none |
| 13 | **Metre scales.** `crest` is at fixed metre scales (8-128 m) on every level, and the gully octaves are keyed by world wavelength | 2.2, 2.3 | 1 | meaning of `crest` |
| 14 | **One climatological sun per place** (`latitude_deg`), shared by the bake, the plants and the material; never the render's sun | 2.2 | 3 (owner), 1, 2, 4 | `CONSTANTS['latitude_deg']`, `palettes.climate_sun()` |
| 15 | **The `eido_<mask>` attributes stay on the mesh by default** (a documented interface); `mask_attributes=False` drops them. A node group reads any baked map by name | 2.7, 2.8 | 2, 5 | `make_terrain(..., mask_attributes=True)`; node group `eido_terrain_map` |
| 16 | **D and E at half the cell only on levels of 2 m cells or coarser** | 2.2, 2.6 | 1 | none |
| 17 | **Package 2 measures the full material cold** before building on it. The sampler table counts 5-7 M atlases (26-27 samplers on the alpine palettes), so package 1 should expect to pack the M families into one shared image, and package 2's reader counts distinct images from the start | 1.3, 2.6, 7, 8 | 2, 1 | `images()` may return one Image for several families |
| 18 | **Provenance.** `src_strata` is the area-weighted mean of the source face; `grain` is the position along each fall path | 2.2, 2.3 | 1 | meanings |
| 19 | **Stride 1 is measured.** Package 2 renders the canyon with stride-1 rings beside the D normals before choosing | 0, 5.4, 8 | 2 | none |

New measurements behind these rows are in 1.3 and the appendix (probes C, D and E).

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
   the cell, and half the cell for the normal and detail images on levels of 2 m cells and coarser. Maps are packed
   four to an image, and all levels of one kind into one tall atlas image, so the material reads each kind with one
   sampler. The material finds the finest level per pixel from the nested windows and reads each atlas in two slots,
   even levels and odd levels, so a slot changes level only where its weight is exactly 0 and the GPU's mip choice
   never sees a jump. Every map's border band is pinned to its parent's, as the heights and masks already are, so the
   two levels agree where the slots blend them.
2. **New maps from the terrain's own data:** a normal from the full-resolution height plus analytic gullies below the
   cell; cavity; convexity at five metre scales; settled soil; snowpack that settles and slides; freshness (threshold
   exceedance on steep ground, stream power on gentle ground); valley-bottom flatness; provenance (the rock column height a debris' source sits at, and the
   colour sediment carries down the drainage); talus grain; wind streaks.
3. **Colour from data.** A layer's colour becomes a ramp read at a terrain mask (Gaea's CLUT idea), with stops
   measured from the photographs. Rock gets freshness and patina. Debris and sediment take their source's colour. The
   strata column colours the cliffs only. A per-texel far colour, baked as the near material's expectation, takes over
   past one distance per shot and carries the ground to the horizon.
4. **Placement from terrain structure.** Layer weights move from world fbm to terrain terms. Every transition is an
   overlay of the macro data and the scans' heights, then the existing height blend. Noise stays as a small residual,
   and every noise term fades with the pixel's footprint.
5. **Projection and tiling.** Planar reads are hex-tiled (three reads on a triangle grid, each turned and offset,
   sharpened weights). Steep faces are read in eight fixed frames tilted to the dip, picked by the face's own normal,
   instead of the Box projection.
6. **Plants as data.** A plant layer turns ecosystem rules, written in the same mask language, into spots: position,
   scale, yaw, age, species, tint. Sampling is clustered Poisson, and trees thin the undergrowth. The spots are saved
   with the terrain in a format a three.js placer can read. In Blender they instance flora plants and SeedThree trees
   grown once, switched by camera distance, and they give the material its canopy cover.
7. **Kept:** the node group, the mask language, the height blend, `'Auto'` filtering, the strata column with its
   relief and ledges, streaks, ripples, patches (fewer, terrain-limited), the canopy (now driven by the ecotope's tree
   density), the mesh's mask attributes and the rock dressing.

**Measured (section 1.3).** One EEVEE material here samples at most 30 images (32 samplers, 2 kept by the engine). A
UDIM image costs 2 samplers. A second read of one image costs another sampler when its extension or interpolation
state differs (Linear and Cubic share). So the data travels in atlases, one sampler each, every read of an atlas
with the same state. On a real canyon's walls, fixed sector frames weighted by the face's own normal stay within
4-13 % of the scan's scale (p50 to p99), where the Box projection is 30-81 % off (probe C). The probes' frame costs of hex
tiling, sector projection and the data reads, and the two-slot reader's seams, are in section 1.3.

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
| how far each steep-face projection draws a scan off its true scale on a real terrain | the cached canyon (`e67bc9fe`), levels of 7.8, 1.95 and 0.98 m, every cell steeper than 47°. The off-scale factor is max(s_max, 1/s_min), the singular values of the texture mapping against surface distance; 1 is true scale. Box projection: p50 1.30-1.37, p99 1.81. The first version's frames, as a shader evaluates them (v = P·b with b turning per pixel): p50 2.96-4.49, p99 45-52 (the critique's run of the same check). Fixed vertical frames (u = P·t_k, v = z) picked by the 20 m normal: p50 1.24-2.00, p99 1.80-14.7. The worst cases are small steep features on the fine levels, where the 20 m normal faces elsewhere. Fixed frames tilted to a 62-68° dip, two slots weighted by the azimuth of the cell's own normal: p50 1.04-1.07, p90 1.07-1.11, p99 1.09-1.13 on all three levels. The same frames weighted by the normal blurred at 4 m: p99 1.10-1.56; at 8 m: 1.11-2.4; at 20 m: 1.31-14.5. All values weight-averaged over the two slots | C |
| the reader at a window edge, in EEVEE | the critique's probe scene (three nested levels of 1024 texels, 32-texel gutters, 16-cell pins, an emission plane at 960×540, factory anisotropic filtering), the error against a Cubic read with no mips, on pixels within 2 px of a window edge. Single read → plain two slots → two slots with the 3-footprint dead band: oblique 20.0 % over 0.05 → 0.54 % → 0.0 % (mean 0.036 → 0.0038 → 0.0029, max 0.57 → 0.16 → 0.033; elsewhere mean 0.0029, p99 0.014); camera at 6 m 22.7 % → 3.9 % → 1.9 % (max 0.44 → 0.36 → 0.12; elsewhere mean 0.007); camera at 2 m 31.5 % → 10.2 % → 7.0 % (elsewhere 0.007, p99 0.034). A switch 24 cells out in the gutter, without the dead band, does as well at the oblique view but worse at the low ones (2.5 % and 8.4 %); with the dead band added it equals the dead band alone. At 3× the single read's render shows a grey one-pixel line along each window edge; the dead band's shows none | D |
| the ramp LUT under minification | a 256 × 8 LUT of flat colours read on one row at a T that varies across a 1.2 km ground plane. Other rows' colours on the ground: Linear (mipmapped) 87.5 % of pixels, up to 5.4× the right colour; Cubic 100 %, up to 0.38; Closest 0. The anisotropy preference set between renders of one session changed nothing (a GPU texture keeps the filter it was made with), so a render script sets it before any image is drawn | D |
| atlas files loaded from disk | package 1's eleven Toroweap atlas files (643 MB; D a 399 MB float32 EXR, E a PNG of the same size, eight M PNGs) loaded with `bpy.data.images.load` into a material already compiled on stand-ins: decode 12.3 s in all (D 4.3 s, E 1.6 s, F 1.9 s, each M 0.3-1.2 s); the first frame with them 3.0 s against 0.8 s after: about 2.2 s of upload | D |
| the reader at a window edge, emulated | the same scene emulated in numpy: one derivative per 2×2 quad, trilinear mips, 16× anisotropic filtering; the error against the right level read with no mips. Edge pixels over 0.05, single read → plain two slots → two slots with the 3-footprint dead band: oblique view 13.1 % → 0.6 % → 0.0 % (max 0.46 → 0.22 → 0.031; elsewhere the error is 0.0014 mean, p99 0.013); low view 17.3 % → 2.8 % → 0.5 % (max 0.44 → 0.44 → 0.084). A switch moved 24 cells out into the gutter, without the dead band, helps the oblique view only (low view: max 0.33). A dead band capped at 4-8 cells is as bad at the low view. At a 2 m grazing camera, about 20 % stay over 0.05 in every variant: there the dead band shows the parent across metres of the child, a smooth blend, against a no-mip reference that aliases (the error elsewhere is p99 0.05 too). With isotropic filtering, every grazing read blurs, edges or not | E |

What these decide:
- **Atlases, not UDIMs.** The palettes' scans already take 12-14 samplers. The data needs eight to ten kinds of
  image. As UDIMs that is 16-20 samplers, 28-34 in all; as atlases it is 8-10, 20-24 in all.
- **One sampler state per atlas:** every read Linear, EXTEND, mipmapped; the reader's two slots read the same image
  in the same state, so they share its sampler. A Closest or REPEAT read of the same atlas would cost a sampler more.
  The LUT is its own image, read only Closest, so Closest costs it nothing extra.
- **Sector frames are fixed and picked by the face's own normal** (probe C): a frame that turns with the pixel, or a
  sector picked by a smoothed normal, puts a scan several times off scale on real walls.
- **The reader reads each atlas in two slots with a dead band** (probes D, E): a single read draws a line along
  every window edge; two slots alone leave one at low cameras.
- **The atlas files are the cache** (probe D): loading them takes seconds; assembling atlases in memory took minutes.

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
  build/mesh.py               (package 2) material_index per ring (the far material only on rings beyond 1.5 D0 from
                              every camera passed, 3.7); the mask attributes kept by default
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
| D, detail normal | RGBA16F | half the cell on levels whose cell is 2 m or more and n ≤ 1024 (the main level and the coarse hero levels); the cell otherwise; at most 2048 per level. Finer levels gain under 1° of normal at half the cell (p90 0.13° at 1.95 m against 4.1° at 7.8 m), and their scans' own normals cover that band | the field normal's x, y; the sub-cell relief's gradient gx, gy |
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
- `slope_20m` from `n20` (the slope of the 20 m normal): a slope that means the same on every level, for rules that
  must not step at a window edge (the plants' densities, 4.2);
- `height` and `altitude` from the object z, which is the field's height at every pixel of the mesh;
- `insolation` = max(0, N_field · s), s the place's climatological sun: `palettes.climate_sun(constants)` turns the
  terrain constant `latitude_deg` (default 40; set per place, negative south of the equator) into the equinox noon
  sun, bearing 180° north of the equator and 0° south of it, elevation 90° − |latitude|. A palette may set
  `sun_azimuth_deg` and `sun_elevation_deg` outright. The bake (snowpack melt), the plants and the material read the
  same function. The render's sun is never passed: the ground's cover answers to the climate, not to the time of
  day of a shot, and the review lights each view from its own side.

**The map list.** Every existing mask keeps its name, unit and meaning: `flow`, `wetness`, `channels`, `occlusion`,
`deposit`, `talus`, `sand`, `lava`, `water`, `rock_toe`, `peaks`, `snow`, `rock`, `wear`, `vegetation`,
`height_norm`, and convex, concave and the curvatures at 20 m and at 2 × the cell. New:

| map | unit | made by | what it marks |
|---|---|---|---|
| `crest` | -1..1 | blur pyramid | multi-scale convexity at fixed metre scales, σ = 8, 16, 32, 64 and 128 m on every level, so a threshold on it means the same in a hero window and on the main level: + crests, rims, ribs, spurs; − creases, chutes, hollows (Gaea's SurfTex Sprinkling, our terms). A scale under one cell is left out on that level and the rest renormalised; a scale wider than the level's window comes from the parent's pass. On gentle ground, −`crest` is the soil-gathering term (hollows at 8-128 m) |
| `crest_fine` | -1..1 | blur on D's grid | each level's own finest convexity, σ = 1 and 2 texels of D. Its meaning changes with the level by design: it is read only for tone and fades with the footprint |
| `crease` | -1..1 | gully filter | the sub-cell gullies' curvature: floors −, crests + |
| `cavity` | 0-1 | horizon march on D's grid | short-radius occlusion, 2-32 texels: 1 open, low in creases |
| `settle` | 0-1 | `detail.relax` | where a thin loose layer comes to rest at a 20° repose: benches, ledges, slope feet. 0.5 where it stayed, toward 0 where it shed, toward 1 where it gathered. It moves only on ground steeper than about its repose, so on gentler ground it is 0.5 almost everywhere (94-100 % of cells under 10° on five cached main levels, the critique's check; package 1's Toroweap sheets of 11-14 show the plateau one flat 0.5 at 8 m and at 2 m, with benches and the river terrace gathering on the walls): gentle-ground rules never read it (3.2) |
| `snowpack` | m | `detail.relax` twice | snow settled at a 38° slip-off, melted by insolation, plus a flowing pass at 14° along the drainage |
| `fresh` | 0-1 | threshold, stream power | actively eroding ground. On ground steeper than 30°, the slope over the rock's threshold `Sc` (faces that are failing). On ground under 30°, stream power on bare ground (scoured channel floors). A solver's `wear_recent` where one exists. Stream power is never read on steep faces: it peaks at the pour-overs, where the varnish curtains are (3.1) |
| `spi` | 0-1 | stream power | log10(a tan S), normalised by the main tile's 5th-95th percentiles |
| `valley` | 0-1 | blur pyramid | flat and low at several scales (an MRVBF-like index, Gallant & Dowling 2003): valley floors, fans, basins |
| `src_strata` | m | routing | the stratigraphic height of the bare rock a debris cell's material came from: the mean zs of the whole source face above it, weighted by each source cell's area (z + `src_dz`), so a talus below a banded wall takes the wall's mix, not the bed at its foot |
| `grain` | 0-1 | carry kernel | where the cell sits along its own fall path: 0 at the apex below the source, 1 at the path's toe (fine debris high, boulders low), whatever the path's length; 1 where no rock stands above |
| `streak` | 0-1 | directional blur | wind exposure on convex ground, smeared 10:1 along the palette's wind |
| `n20` | 2 channels | blur pyramid | the 20 m normal's x and y (z rebuilt): direction terms across walls and `slope_20m`. The sector frames no longer read it (3.4) |
| `canopy`, `canopy_expected`, `canopy_far`, `shrubs` | 0-1 | plant layer | placed crowns' cover; the cover the ecotope's tree density implies, made on every level whenever the palette has a canopy layer, with plants or without (4.7); the part of it the instances leave to the material; undergrowth density |

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
3. **Relief below the cell.** Port `solvers/detail.py`'s `phacelle_noise` arithmetic (the kernel, its
   normalisation and masks) and `gully_relief`'s octave loop to `phacelle.glsl`, with the octaves keyed by world
   wavelength, so a wavelength has the same lattice and pattern on a parent and a child.
   - Octave o has λ_o = 4096 m × 2^−o, amplitude a_o = k λ_o (k the recipe's gully amplitude over its wavelength,
     0.08 by default: self-similar) and its lattice offset from (seed, o): the same numbers on every level.
     `op_gully`'s own sequence (λ0 = 12 cells, offsets by octave index) is level-keyed; the geometry keeps it (a
     solver, inside the cache key).
   - A level evaluates the octaves from the first one under 3 of its cells down to 2 texels. Coarser octaves are
     in its height already (the geometry's gullies) or belong to its parent.
   - The first octave is steered by the field's own gradient, which holds the geometry's gullies, smoothed over 2
     cells and turned toward the routed flow (`flow_x`, `flow_y`) where present. Each next octave is steered by the
     running gradient, so small gullies branch off the big ones as the filter intends.
   - They are masked to soil slopes of 10-35° and loose cover.
   - On bare rock the breakup strength's gradient (`solvers.detail.strength`, read-only) adds ribs instead.
   - Output: the relief's gradient (gx, gy) and its normalised Laplacian (`crease`).
4. **Cavity on D's grid.** A horizon march over h plus the sub-cell relief: 16 azimuths × radii of 2, 4, 8, 16 and
   32 texels. cavity = 1 − mean(sin θ), as `masks.sky_view` (Zakšek et al. 2011).
5. **Blur pyramid.** Separable Gaussian passes at fixed metre scales, σ = 8, 16, 32, 64 and 128 m (each at least
   one cell: finer ones are left out on that level), and at 1 and 2 texels of D for the fine terms.
   - crest = Σ_s a_s tanh(−(G_s h − h) / (τ σ_s)), rescaled to −1..1. In cells it shifted a threshold at every
     window edge: with crest > 0.3, the overlap of a main level and its children was 0.76, 0.51, 0.14 and 0.00 at
     3.9, 1.95, 0.98 and 0.49 m; in metres it is 0.68-0.90, correlation 0.92-0.97 (the critique's check on the
     cached canyon `e67bc9fe`);
   - `crest_fine` at 1 and 2 texels of D;
   - `valley` from flatness × lowness at each scale (already from 12 m up, in metres);
   - `n20` from the 20 m blur.
6. **Settle.** `solvers.detail.relax` with the cohesive ground at h (`Sc` huge, so nothing fails), a loose layer of
   0.5 m on top, repose 20°, 60 passes. settle = clamp(d / 0.5, 0, 2) / 2. If a child and its parent disagree over
   the same ground (acceptance 1), the finer levels relax the height low-passed at 4 m, so a bench means the same on
   every level.
7. **Snowpack** (palettes with a snowline).
   - Snowfall s0 from altitude against `snowline_m` and from northness, then `relax` at a 38° slip-off for 100
     passes.
   - Melt by insolation, and below the line.
   - A second `relax` at 14° on the flow lines (flow > 0.6).
   - The pack is the larger of the two passes (Gaea's resting and flowing snow, combined by max).
8. **Drainage repaired on hero levels.** The specific catchment a is routed again (`flow_weights`, `route_area`,
   read-only through `core/gpu`, to the runner's convergence test).
   - The routing starts from the parent's area, upsampled, not from zero: the Toroweap record spent 1,280-2,688
     passes and 2.3-28.5 s per hero level starting cold.
   - Inflow is pinned from the parent across the border band.
   - The border is closed to outflow except where the parent's flow leaves.
   - `flow`, `wetness` and `channels` are recomputed with `masks.py`'s formulas and the main tile's norms.
   - It earns its cost: on Lauterbrunnen's 2 m level the runner's flow loses the valley's trunk, and the bake's
     restores it (`out/surface_data/sheets/lauterbrunnen_L4_flow_runner_vs_bake.png`).
9. **Freshness.** fresh is the largest of:
   - on ground steeper than 30°: (slope − atan Sc) / 8° where `Sc` exists (strata recipes write it): failing faces;
   - on ground under 30° (faded over 25-35°): smoothstep on `spi` over bare ground: scoured channel floors;
   - a solver's `wear_recent` field where one exists (none does yet; section 8).
10. **Debris provenance** (`carry_src.glsl`, `route_colour.glsl`).
    - Sources are bare rock (slope over the rock angle, no cover), each weighted by its area.
    - The source zs is routed down the fall directions (the upslope-neighbour weights by slope that `carry_src`
      already draws, normalised per cell) as two channels, Σ w zs and Σ w, with `route_colour`'s scheme; a debris
      cell's src is their ratio: the area-weighted mean of the whole face above it. Beyond `rock_toe_reach_m`
      (300 m), src fades back to the local zs.
    - dist, the distance down the path from the source, is carried as now; a second Jacobi pass carries the
      distance to the path's toe back up (the toe: the first cell where talus thins under 0.1 m or the slope falls
      under 10°). grain = dist / (dist + to_toe), so a 50 m cone sorts from 0 at its apex to 1 at its toe.
    - Output: `src_dz` = src − h, and `grain`.
11. **Wind streaks** (palettes with a wind). Exposure max(0, n · w) on convex ground, blurred 10:1 along the wind.
12. **Pins.** Every map's outer 16 cells are blended to the parent's map with `masks.pin_band`'s ramp. Directions
    (`n20`) are blended as vectors.
13. **Gutters.** g texels around each tile (32 up to 1024 texels per level, 64 above) are filled from the parent's
    maps at those positions. The outermost level is edge-extended.
14. **Readback and encoding.** The maps are read back once per level and encoded per family. The cache stores the
    float16 arrays.

**The palette bake** (`surface/palette_bake.py`) runs on the same levels once per palette and is cached by the
palette's hash:
- **Far colour C: the near material's expectation at the hand-off distance.** Past D0 (3.7) the material shows C in
  place of its layers, so C must be what the near material's pixel averages to there, or a ring shows.
  - Every colour term the near material has goes in: weights with the overlay and the height blend, ramps, patches,
    the satmap, tone, streaks, relief shade, ledges, damp, and the canopy's crowns and gaps by their expected cover.
  - Each scan enters at its mean colour and its mean height: what its mip chain converges to at D0, where a pixel
    spans several metres of every scan.
  - Each texel is the mean of 4 × 4 sub-samples, so terms finer than a texel (patches at 4-7 m, fbm at 2 m, the
    1 m edge noise, 2.5 m streaks) are box-filtered, not point-sampled.
  - The height the terms read is the ring mesh's own surface: the vertex heights `mesh.plan_rings` samples,
    interpolated across its triangles, not the field's h. Strata bands then sit where the near material draws them.
  - `expr_glsl.py` compiles the palette and `noise.glsl` is Blender's own noise, so a term in the bake equals the
    same term in the shader. The strata column comes from `surfacing.strata_array`.
  - The exact fallback, if the measured hand-off (5.4, package 2, check 6) cannot reach ΔE ≤ 2: render C. An
    orthographic top-down emission of the node group's base colour per level, with the reader pinned to that level,
    4× supersampled. That is exact by construction and needs no GLSL port; it costs a shader compile per palette.
- **Provenance colour P.**
  - Sediment production: P = fresh × bare + a small background.
  - Source colour: c = the palette's bare-rock colour at zs.
  - Both are routed down the converged MFD weights the A routing left (`route_colour.glsl`, route_area's Jacobi
    scheme with four channels): Q = P + Σ f Q_up, R = P c + Σ f R_up. Then C_down = R / Q, and the share is
    Q / (Q + Q0). The passes run batched, with no readback between them, starting from the parent's values.
  - On hero levels the parent's values are pinned in as inflow, so a truncated catchment still carries its
    upstream colour.
  - Budget: 30 s per palette cold (7). Past it, P is deferred and sediment layers mix toward the debris' own
    provenance colour (the column at `src_strata`), which needs no routing.

**Twins.** Each kernel has a numpy twin in `surface/twins.py`. The gully filter's twin is
`solvers.detail.phacelle_noise` itself; the settle's is `detail.relax(backend='numpy')`. Parity is tested on a
96×80 field within 1e-4 of its range. The noise port is tested against Blender's Noise Texture node rendered
top-down, within 1e-3.

### 2.4 How the material reads them (`build/surfacing.py`)

**Why two reads.** The GPU picks a read's mip level from the screen-space derivative of its coordinate over each
2×2 pixel quad. Where the level changes inside a quad, the atlas coordinate jumps by a whole tile, so the quad reads
the coarsest mips, the whole atlas averaged. Pins make the values agree; they do not make the derivatives continuous.
On masks that feed thresholds, the single read drew a 1-2 px line of another layer along every window edge: on window
edge pixels the error against a read with no mips was mean 0.036-0.040 and max 0.34-0.38 of a 0..1 mask, 21-24 % of
them off by more than 0.05 (the critique's EEVEE probe, three nested levels). Two slots, each changing level only
where its weight is exactly 0, remove it. Rendered in EEVEE (probe D, 1.3): at the oblique view the single read draws
a grey one-pixel line along every window edge (20 % of edge pixels over 0.05, max 0.57); with the dead band below,
none is over 0.05 and the edge error equals the error elsewhere (mean 0.0029, max 0.033). At a 6 m camera: 22.7 %
→ 1.9 % (max 0.12).

Per pixel, in object coordinates (the terrain keeps an identity transform):

1. **The level.** e_k = max(|x − cx_k|, |y − cy_k|), inside_k = e_k < R_k (R_k = S_k / 2) for levels k = 1..K−1,
   and L = Σ inside_k. The windows are the mesh's (`t.levels`), so L is the level of the ring drawing the pixel. Its
   cores are the same level. δ_L = R_L − e_L is how far the pixel lies inside L's edge (telescoping, below).
2. **The footprint and the dead band.** f = view distance × pixel angle / max(|N · V|, 0.05) (the Camera Data node;
   `pixel_angle` is a terrain constant). z_L = min(3 f, r_L), r_L = g_{L+1} − 8 c_L: g_{L+1} is the smallest margin
   of window L + 1 inside window L, c_L the level's cell (constants of the plan; r_L is unbounded on the finest
   level). Three footprints cover a 2×2 quad straddling the window edge. The cap r_L only binds where a child sits
   close to its parent's edge: the level planner keeps g ≥ 16 parent cells (`core/levels.py` clamps a hero window
   inside its parent's band), so r_L ≥ 8 c_L, and a hero window centred on its focus has hundreds of cells.
3. **The weights.** ω = smoothstep(z_L, z_L + 8 c_L, δ_L): the finest level fades in over 8 cells, moved inward by the
   dead band, and reaches 1 before the next finer window begins. Level L gets ω, level L − 1 gets 1 − ω. Near the
   camera the dead band is millimetres, so a level's detail shows from its edge; where it is metres, a pixel spans
   metres and the parent's data is what it can show.
4. **Two slots.** The even slot reads the finest even level whose window holds the pixel, else level 0; the odd slot
   the same over odd levels, else level 1. So the slot of L's parity reads L and the other slot reads L − 1. A slot's
   coordinate jumps only at a window edge. Outside it, deep inside the parent, the slot's weight 1 − ω of the parent
   is exactly 0; inside it, the dead band holds the child's weight at exactly 0. So a quad that straddles the jump
   gives that slot no weight, and its coarse-mip read counts for nothing. In the tightest nesting at very large
   footprints, the cap can leave a straddling quad a small weight; check 1 (5.4) includes a hero window clamped
   against its parent's edge.
5. **Anisotropic filtering at 16×.** Renders set Blender's anisotropic filter to 16× before any image is drawn
   (`review_views.py` does already; the scene setup, the bench and the judge do too). A GPU texture keeps the filter
   it was made with, so setting it later changes nothing (probe D). With the factory 2×, every grazing read blurs,
   the reader's edges among them.
6. **The constants per slot.** Telescoping sums over that slot's levels give them: q = q_first + Σ_k sel_k
   (q_k − q_{k−2}). That covers the window (x0, y0, S), the cell, and the atlas rectangle (u0, v0, du, dv) of each of
   the two layouts (D/E, and the rest). δ_L, c_L and the level parity come from the same sums over all levels.
   About 300 math nodes for nine levels, twice the single read's, built once as a node group.
7. **The coordinates.** uv_s = (u0 + du (x − x0) / S, v0 + dv (y − y0) / S) per slot.
8. **Two reads per atlas.** Image Texture, Linear, EXTEND, mipmapped, the same image in the same state, so the
   second read adds no sampler (probe A).
9. **Decoding and blending.** A multiply-add per channel, or a square for the thicknesses, per slot; then the slots
   mix by their weights (directions, such as `n20`, renormalised).

**The pins and gutters still matter.** Every map is pinned to its parent across the child's outer 16 cells, so where
the slots blend the two levels they agree in value, and only sharpness changes across the band. The 32-64 texel
gutters hold the parent's data at the child's texel, so Linear filtering and the mips at a tile's edge read real
terrain.

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
- **`steep`, `steep_face` and the sector weights** read N_field, not the interpolated vertex normal (`n20` serves the
  terms that run across walls). This alone removes the chalk brow's teeth: the threshold cuts at the texel, not
  across 11.7 m triangles.
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

**A film terrain of seven levels** (Toroweap's plan: 2 context, main, 4 hero; cells of 32 m down to 0.5 m). Package
1 measured 820 MB with eight M atlases, D 2128 × 11,704. With D and E at half the cell only on the 8, 4 and 2 m levels
(change 16): D about 195 MB, E about 100 MB, six M atlases about 255 MB, F 85 MB, C and P 85 MB. That is about
**720 MB**, against about 270 MB for a palette's 2k scans.
- At hero quality (seven levels of 2048²) it is about 850 MB: the masks stay at 1024, two cells a texel, still finer
  than today's vertices at stride 4.
- Atlas sizes stay within the 32,768 limit (D at film: 2128 wide, about 8,500 tall with the change).

**The sampler budget per material:**

| reads | samplers |
|---|---|
| six layers' scans (albedo_height and normal_rough_ao each) | 12 |
| strata column and its relief | 1-2 |
| D, E, C, P (two reads each, one per slot, one sampler) | 4 |
| LUT (its own image, Closest) | 1 |
| M atlases (20-25 maps with the new ones: the in-progress looks read 11-18 names, 8-15 of them stored, and `crest`, `settle`, `fresh`, `valley`, `n20` (two channels), `canopy_expected`, `canopy_far`, `snowpack` and `streak` come on top) | 5-7 |
| F (when a layer reads `strata_dz` or `src_dz`) | 0-1 |
| total | 23-27 of 30 |

`surface_group` refuses a material past 28 with the count and what to drop, as `MAX_IMAGES` does today. The alpine
palettes come to 26-27, so the lever is named now and package 1 should expect to build it: the M families packed
into one shared image. Each family keeps its own per-level rectangles, which `layouts` already returns per family;
`images()` then returns one Image for several families, and the reader counts distinct images, which package 2's
reader does from the start. That takes the masks from 5-7 samplers to 1, whatever a palette reads. Package 2 measures
the full material first (8.1) and asks for it as soon as a palette passes 26.

**The LUT is read Closest.** A mipmapped Linear read of a 256 × R ramp image averages neighbouring rows wherever T
moves fast across the pixels; rows hold different layers' ramps, some colours and some gains, so a bleed is a wrong
colour. Probe D (1.3) measured it on a 256 × 8 LUT read on one row at a T that varies across the ground: Linear put
other rows' colours into 87.5 % of the ground (up to 5.4× the right row's), Cubic into all of it (up to 0.38), and
Closest into none. Closest reads one texel exactly (256 columns: a step of 1/256 in T, about one 8-bit level at
most on the palettes' ramps).

### 2.7 Caching, images and saving

- **The surface cache has its own root and cap.** `EIDO_SURFACE_CACHE`, else
  `<repo>/eidoverse/assets/cache/terrain_surface/<terrain key>/` (git-ignored, as the terrain cache is).
  - It keeps one bake per terrain key (a new bake replaces the old) and prunes whole terrain keys, oldest first,
    past 8 GB. The terrain cache's 20 GB prune never counts or removes surface files, so a surface bake can no
    longer push a terrain out (its entries took minutes to regenerate, and the cache went from 33 GB to 7.5 GB in
    one session). Nobody edits `core/`.
  - Arrays: `surface_<key>_L<i>.npz`; the 8-bit maps stored as uint8 in their encoding, the 16F ones as float16,
    the drainage area as float32. key = SHA-1 of the terrain's key, the bake's code (`surface/*.py`,
    `surface/kernels/*.glsl`) and its options. The palette bake adds the palette's hash.
  - With `cache=False` the bake runs in memory.
- **The atlas files are the cache every process loads.** Each family's atlas is written once per bake (OpenEXR half
  with ZIP for D and F, 8-bit PNG for the rest; C and P per palette, M per packing) and loaded with
  `bpy.data.images.load`. Colour space, half precision and `CHANNEL_PACKED` alpha are set before anything reads
  pixels (probes A2, A3). Package 1's `images()` already works this way. The npz arrays are read only by numpy
  consumers: the plant layer and the judge. A process that finds the atlas files never assembles an atlas (the
  Toroweap record spent 145 s building eleven atlas images in memory).
  - `SurfaceData.save_images(folder)` copies the files beside a .blend that must render on another machine, which
    then references them, as it references the scan cache. Images loaded from files read right in probe A.
  - `terrain_surface(obj)` (api) relinks them when a .blend is reopened, as `terrain_height_at` rebuilds
    `height_at`.
- **The mesh keeps its `eido_<mask>` attributes by default.** They are a documented interface for agents' own
  shaders and Geometry Nodes (`tools-guides/terrain-surfaces.md`, "Masks"). `make_terrain(..., mask_attributes=False)`
  drops them when memory matters: thirty FLOAT attributes on 3M vertices are 360 MB of RAM and seconds of build. The
  material never reads them when a bake exists. For per-texel reads in an agent's own material, package 2's node group
  `eido_terrain_map` reads any baked map by name through the same two-slot reader; the guide documents both.

### 2.8 What stays, what changes, and why

| piece | fate | why |
|---|---|---|
| `eido_terrain_surface`, its outputs, `surface_material` / `apply_surface` | kept; take `data=` | every caller keeps working |
| the mask language, `_Compiler`, `material_masks` | kept; masks come from atlases; new names (2.2) | the palettes are data agents already write |
| coverage composited in order; the height blend (`height_blend`, `blend_depth`) | kept; an overlay of the macro data comes before it (3.2) | measured with the shimmer probe; the crater's layering depends on it |
| `'Auto'` filtering (Cubic within 4-9 m, mipmapped Linear beyond) | kept on the scans | grazing sharpness near, stillness far |
| two-lattice de-tiling (`'rotate'`, `'offset'`) | replaced by `'hex'` on every planar read; `'offset'` stays an option | periodic within its patches (the talus dots 19 m apart) |
| the far read (`far_scale` 8, `far_contrast`, `macro_mod`) | replaced by the far colour past one distance per material (3.3, 3.7) once C lands; kept until then | an 8× magnified scan pattern, not the ground's own variation |
| Box projection on steep faces | replaced by fixed sector frames (3.4) | the diagonal smear: on the canyon's walls the Box projection is 1.30-1.37 off scale (p50), fixed tilted frames 1.04-1.07 |
| the strata column, bed relief, ledges | kept; on cliff and ledge layers only by default; debris reads `src_strata` | bands on talus and benches read as contour stripes |
| streaks | kept; widths of 5-30 m on big walls; where = flow × (1 − fresh) | varnish curtains, not 2.5 m pinstripes |
| patches | kept, fewer; `where` reads terrain terms; footprint fade | world-noise blotches are the camouflage |
| `LANDSCAPE_MACRO` | replaced by a data macro ramp plus one residual octave of at most ±3 % (3.1) | macro colour from the place's own structure |
| canopy | kept; the layer's weight from the ecotope's `canopy_expected`, its crowns from `canopy_far` (4.7) | one forest near and far, one rule |
| ripples, ledges, damp | kept | they work |
| the rock dressing | kept; an optional toe bias (4.6) | its placement reads right |
| `pack_masks`, `mask_packs`, the Attribute path | kept for meshes without a bake | tests, built geometry |
| the `eido_<mask>` mesh attributes | kept by default; `mask_attributes=False` drops them | a documented interface for agents' shaders and Geometry Nodes |
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
   - Varnish streaks fall where water pours over the brink (`streaks_where`: flow over the edge), and `fresh` never
     gates them. Stream power peaks at the pour-overs and chutes, exactly where the curtains form (tw_03, tw_07), so
     a rule of flow × (1 − fresh) would have removed the varnish the canyon keeps. Paler bleaching sits on
     `crest_fine`.
5. **The strata column colours cliffs only.** Cliff and ledge layers read it at zs. Debris reads it at `src_strata`.
   Soils and plateaus take their own ramps (Goosenecks' pale limestone rim, Toroweap's grey-green plateau).
6. **Tone from shape at every scale.** tone = a₁ crest + a₂ crest_fine − b (1 − cavity) − c crease, as × (1 + tone).
   This replaces the 20 m-only tone: crisp pale crests and dark creases at the field's scale are much of why World
   Machine and Gaea terrains read as eroded.
7. **The far colour C.** Past one distance per material (3.7) it makes the ground a unique colour per texel to the
   horizon, not a magnified scan. It is the near material's own expectation there (2.3), so the hand-off shows no
   ring.

### 3.2 Layers placed from many masks

**Terms per kind of layer** (the palettes' vocabulary from now on):

| layer kind | terrain terms |
|---|---|
| cliff, bare rock | slope (D), `crest` (ribs bare lower, chutes hold cover), `fresh`, `n20` and `curv_plan` across the wall (vertical structure), the column's hardness |
| talus, scree | `talus`, `rock_toe`, `grain`, `src_strata`, concave feet, the repose band only under walls |
| soil, regolith | on gentle ground −`crest`, `valley`, `wetness`, `cavity`; on slopes `settle` (benches, ledges, feet) as well |
| sediment, wash, fans | `deposit`, `valley`, `channels`, `flow`, C_down |
| forest, chaparral (any layer with a canopy) | `canopy_expected`, the ecotope's tree density (4.7); its crowns `canopy_far` |
| ground plants (grass, scrub litter) | `plants`, `insolation`, `wetness`, −`crest`, the plant layer's `shrubs` and `canopy_expected` |
| snow | `snowpack`, plus a dusting on N_final for powder and ash |
| sand | `sand`, `streak`, aspect against the wind (slip faces) |

**Rules.**
1. **Noise share.** A weight's noise terms span at most a quarter of its smoothstep window. The rest are terrain
   terms. fbm stays for raggedness at the metre scale.
2. **Transitions.**
   - First the overlay: cov′ = cov < 0.5 ? 2 cov d : 1 − 2 (1 − cov)(1 − d). Here d mixes the layer's scan height
     (near) with `crest`, `crest_fine` and `crease` (macro), faded by the footprint. Overlay leaves cov at 0 and 1
     unchanged (Frostbite's detail masks).
   - Then the existing height blend: a_i = w_i + h_i k, keep what lies within `blend_depth`, normalise.
   - Edges then follow the material's grain at metres and the landform's at tens of metres.
3. **Gradation zones.** A layer ends over a band driven by a terrain term, not at one line. Talus aprons fan into a
   floor by `grain` and `deposit`; scree thins into soil by `settle` on slopes and by −`crest` on gentle ground.
4. **Footprint.**
   - footprint = view distance × pixel angle / max(|N · V|, 0.25). The pixel angle is a terrain constant
     (`pixel_angle`, default 1/1000 rad; the scene script passes its camera's).
   - Every `noise()` and patch term's deviation from its mean is scaled by f = smoothstep(1, 4, scale / footprint).
   - Inside a smoothstep, flattening the noise alone would change the coverage: the mean of a threshold is not the
     threshold of the mean (smoothstep(0.62, 0.78, fbm) covers about 15 % of the ground near and 0 % with the fbm
     at its mean). So when a smoothstep's argument holds a faded term, its two edges move apart by (1 − f) times
     that term's half-spread: the 5-95 % half-range of its amplitude × (noise − 0.5), from a table of Blender's
     Noise Texture spread per Detail that package 2 measures once. The expected coverage then stays put as the
     noise fades. A term not inside a smoothstep only fades.
   - `fbm()`'s Detail input is set per pixel to log2(scale / (2 footprint)), clamped 0..5.
   - A term finer than a pixel then fades to its mean instead of shimmering, and a layer's cover does not drift with
     the camera's distance.
5. **Gentle ground never reads `settle`.** It is 0.5 there almost everywhere (2.2). Soil gathers in hollows by
   −`crest`, `valley` and `cavity`, and dampens by `wetness`.

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
  - far: past one distance per material, D0 (3.7), the C colour × a faint luminance grain of the dominant layer's
    scan. The first version handed off wherever a texel of the pixel's own level spanned under 2.5 pixels; every hero
    window's outer part passes that test and its child's does not, so the hand-off would have drawn rings at
    200-250, 400-500, 800-1000, 1600-2000 and 3200-4000 m around a camera at Toroweap's focus.
- **Cost and look:** probe B (1.3).

### 3.4 Steep faces in any orientation: fixed sector frames

Box layers read eight fixed frames, one per compass sector, each a constant linear map of the world position P:
- **Frame k** (φ_k = k × 45°, the azimuth from +x, counter-clockwise, that the face looks toward): u = P · t_k along
  the strike, t_k = (−sin φ_k, cos φ_k, 0); v = P · b_k up the dip, b_k = (−cos θ0 cos φ_k, −cos θ0 sin φ_k, sin θ0), a fixed
  axis tilted to θ0 = 65°, the middle of the steep faces' dips (47-90°). A face of dip θ facing φ_k is read with a
  stretch of 1/cos(θ − θ0) along its dip: at most 1.10 from 47° to 90°.
- **Why fixed.** A frame that turns per pixel, as the first version's v = P · (N20 × t_k) did, adds |P| times the
  frame's turn rate to v's derivative. P is hundreds to thousands of metres, so on the canyon's walls that drew
  scans 3-4.5× off scale (p50) and 45-52× (p99), and the critique's renders of a cached 0.98 m hero crop at its
  world position showed vertical streaks across the whole wall. A constant map has exactly the derivatives of its
  own scale.
- **Two slots.** The even slot reads the even sector nearest the face's bearing, the odd slot the odd one. The
  bearing is the azimuth of the field normal from D at the pixel, the face's own. Weights: with
  s = |2 ((φ mod 90°) / 90°) − 1| (1 at an even sector's centre, 0 at an odd one's), the even slot's weight is
  smoothstep(0.1, 0.9, s) and the odd slot's the rest. A slot changes sector only at the other parity's centres,
  where its weight is exactly 0 within 4.5°, so a quad straddling the change gives it no weight. This is the rule
  hex tiling's slots and the reader's slots follow.
- **Why the face's own normal.** Picking the sector by a smoothed normal faces small steep features with a sector
  that looks elsewhere. On the canyon's 0.98 m level, picking by the 20 m normal put p99 at 14×; by the normal at
  4 m, 1.6×; by the face's own, 1.13 (probe C). Where the bearing turns fast, on a sharp spur seen at a distance,
  a slot can change sector inside one quad; there the scan is read at a coarse mip, which at that distance is
  close to its mean, along a line of a pixel or two.
- **Probe C's numbers** (1.3): over all steep cells of the 7.8, 1.95 and 0.98 m levels, p50 1.04-1.07 and p99
  1.09-1.13, against the Box projection's p50 1.30-1.37 and p99 1.81.
- Each sector has its own offset. The two reads are height-blended by their weights.
- Within each frame the read is hex-tiled in (u, v), as the planar reads are (3.3). A sector read at true scale
  shows its tile's repeats on a big wall: probe B's 45° wall repeated a dark feature every 9-10 m, the tile. The Box
  projection's ghosting had hidden that.
- Planar below 37°, sectors above 47°, as now. The bump of the layer's own height, as now.

The Box projection is retired.

**Probe B (1.3).** On the 45° wall at 70 m, the Box projection drew two half-weighted crack networks, each stretched,
soft and doubled. The sectors drew one network at the scan's scale, crisp, at the same frame cost. That wall was
planar, so it could not show the turning frame's fault; the acceptance now looks at real walls at their world
positions (5.4). Hex tiling inside the sectors is package 2's to measure: with three reads per slot it is six reads
per map on steep faces.

Why sectors rather than biplanar mapping (Quílez): biplanar picks the two dominant axis projections and hides the
switch with explicit texture gradients, which shader nodes cannot pass. It also still reads a diagonal face through
axis frames. The two-slot sector blend changes a slot's frame only where its weight is 0, and each frame faces the
slope.

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

### 3.7 The far hand-off and the far material

- **One distance per material, monotone.** w_far = smoothstep(D0, 1.5 D0, view distance) × smoothstep(0, 64 c_main,
  the distance outside the outermost hero window), and the near material mixes to C × grain by w_far.
  - D0 = c_main / (2.5 × pixel_angle): where a main-level texel spans 2.5 pixels (3.1 km on a 7.8 m main level,
    1.2 km on the crater's 2.9 m one). The option `far_m` sets it outright.
  - The second factor keeps the far colour out of every hero window and fades it in over 64 main cells beyond the
    outermost one. Both factors are continuous, so nothing jumps at a window edge. On a terrain without hero
    levels it is 1.
  - It holds on every ring, whichever ring the camera stands on: whether a pixel is far depends on its distance,
    not on its ring. The eye-level views without a focus (`impact_crater` plain_north on an 11.7 m context ring,
    `real_place` ridge_schynige on a 32 m one, `alpine_valley` shoulder_wengen on a 15.6 m one) see their own
    foreground through the near material.
- **The far material** (material slot 1: D's normal, C's colour and roughness, one faint grain read, no layers) is a
  cost saving only. `apply_surface(obj, ..., cameras=[...])` assigns it to a ring whose nearest point lies beyond
  1.5 D0 from every camera position passed: the shot's cameras, or points along its camera path. With no cameras
  passed, no ring takes it. The review passes its camera.
- **Why.** Aerial frames, where the far context fills much of the picture, get cheaper (probe B: 0.03 s a frame over
  clay), and the horizon is coloured by its own data.
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
| `canyon` (tw_03, tw_04, tw_07) | strata stripes on talus and benches; walls only horizontal bands; scrub and slickrock noise blotches; a lattice of pale dots on talus aprons; the brink wall's smear; the plateau one soil at eye level; far caprock reads as snow | cliff-only strata, debris at `src_strata`, washes by C_down (3.1); vertical structure from `crest`, `curv_plan` and `fresh`, varnish curtains under pour-overs; scrub by `wetness`, −`crest` and `valley`; hex tiling and the far colour; sectors; shrubs, grass tufts and stones as plants and rocks (4); the top formations' looks and a plateau plant tone | the bands on the cliffs: ledges, recesses, varied beds, varnish |
| `impact_crater` (meteor_crater_01-03) | the floor a flat disc; a crisp pale ring at the walls' foot; plain soil showing between talus and floor; the plain one soil, no ejecta blanket | floor ramps by `valley`, −`crest` and deposit thickness, with crusted patches by `wetness`; aprons graded into the floor by `grain`; layers that give the base soil only the plain; an ejecta layer from the impact solver's deposit and talus outside the bowl; scrub as plants | the walls and the rim rocks (3.8) |
| `real_place` Lauterbrunnen (lauterbrunnen_01, 15) | the floor one lawn; forest hard-edged blobs and slope-foot lines; camouflage from the ridge; the walls' smear; forest a draped texture at eye level | pasture ramps by `wetness` and `valley`, and a mowing pattern; the forest from the plant layer (steep sides forested, meadows on the shoulders and terraces by `valley` at 100-500 m); sectors; spruce instances near, billboards mid, canopy far | the limestone walls' bedding, ochre zones, ledge plants; snow lying by shape |
| `alpine_valley` (lauterbrunnen_14, 15) | grey scree over most of the high ground; noise-isoline edges; smeared trough walls | alpine pasture and cushion plants on gentle ground above the treeline; scree only from `talus`, `rock_toe` and under walls; terrain-term edges; `snowpack`; sectors | - |
| `fluvial_range` (san_gabriel_mountains_02-04) | camouflage of chaparral, grass and granite; no denser brush in drainages or on north faces; no pale outcrops on ridges; the basin one material | chaparral continuous from `canopy_expected`, the ecotope's density (denser by `wetness` and `channels`, and on the shaded side by `insolation`), on slopes under 40°; pale decomposed granite on `crest` and `fresh`; bajada fans by `grain` and C_down | - |
| `incised_meanders` (gn_01, gn_05, gn_06) | walls a stack of even ledges; the plateau one red-brown soil | cliff-only strata with debris between ledges by `src_strata`; slickrock pavement where `crest` is high and `deposit` thin; the pale limestone rim | - |
| `mesas_buttes` (mv_02, mv_04, mv_05) | the floor one material, flat at every scale; walls soft bands, no fluting; caps the floor's soil; the close wall's smear | sand sheets by `streak`, −`crest` and `valley`; lag gravel on `crest`; washes by `channels` and C_down; grey shale pedestals by `src_strata`; the macro normal; the caprock rim by `crest` at the texel; sectors | the orange-red floor, the red caps |
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

**Densities read terms that mean the same on every level,** so stems per hectare do not step at a window edge:
`slope_20m` (not the cell's `slope`), the curvatures at 20 m and wider (not the unsuffixed ones at 2 × the cell),
`crest` (metre scales), `valley`, `wetness`, `altitude`, `insolation`, `occlusion`. The cell-scale terms (`slope`,
`convex`, `concave`, `crest_fine`, `crease`, `cavity`) may shape a species only through its placement jitter, never
its density. The expressions read every mask and map, plus derived names:
- `soil` = deposit + talus + sand, scaled up in hollows (−`crest`) and, on slopes, where `settle` gathered;
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
- **Instancing LOD.** Realised geometry is what costs: SeedThree's LOD0 trees have 35-90k triangles, and package 4's
  first smoke render spent 191 s instancing. So:
  - **Shrubs, grasses and forbs are never realised.** They are LOD2 instances (an eidoverse-side Geometry Nodes group
    on the spots' points) or flora's still strokes, out to the distance where a plant spans about 4 pixels
    (d = height / (4 × pixel_angle): 250 m for a 1 m shrub), or nearer where the eye-level frame would pass its 8 s
    (5.4), then billboards, or nothing for grasses, whose cover the material carries (`shrubs`). Shrubs barely sway, and the 300-tree cap below must not pull their billboards in to 36 m, inside
    eye-level frames (the blackbrush smoke render's hard ring).
  - **Trees that sway in the shot** (the scene's wind on) take SeedThree's `forest_group`, which realises its near
    trees so each can sway. Their LOD2 cards stand within billboard_m = min(120, √(300 / (π density))) of the active
    camera, about 300 realised trees (a spruce stand of 500 stems per hectare gets 44 m). Trees in a still shot are
    LOD2 instances, not realised, to the same distance.
  - **Hero LOD0 is picked per frame:** an eidoverse-side Geometry Nodes group takes the trees within `hero_m` (40 m)
    of the active camera, nearest first, at most 64. The first version chose them at build along the focus path,
    which grows with the path: a 500 m walk at 500 stems per hectare is about 2,000 trees, 120 M triangles.
  - **Billboards are matched to LOD2 before they are used.** Package 4's smoke renders show white billboards beyond
    dark LOD2 shrubs. One plant of each species is rendered as LOD2 and as its billboard at the switch distance under
    `make_sky`: mean colour within ΔE 3 and silhouette area within 10 %, else the billboard's bake is corrected
    (on the eidoverse side: SeedThree's bake is its own).
  - Billboards drop out between 0.8 and 1 × `max_radius_m` while the material canopy fades in (4.7).
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
- **What each instancer honours.** The spots carry more than every source uses; `plant_instances.py` documents per
  source which fields it takes, and the spots' JSON says it per species (`"honoured": [...]`):

  | source | honours | does not |
  |---|---|---|
  | flora strokes (`create_flora(placements=...)`) | x, y (z from `height_fn`), scale | yaw and tint: flora draws its own per plant from the stroke's seed; age and variant only through scale and the stroke's individual |
  | the eidoverse-side Geometry Nodes instancer (non-realised LOD2 shrubs, trees in a still shot, hero LOD0: 4.4) | x, y, z, yaw, scale, variant, tint (an instance attribute the plant's material reads) | age (through scale) |
  | SeedThree `forest_group` points | x, y, z (the points' position; `st_ground` is written but SeedThree does not read it), yaw (`st_rot`), scale (`st_scale`), variant (one points object per individual) | tint, age (through scale) |
  | `ph:` scans | as flora's instancing | as flora's instancing |
- **Flora's occupancy list** (`vegetation._placed_plants`, which later jittered strokes scan in pure Python per
  candidate) is cleared with flora's public `reset_flora_occupancy()` after each plan's strokes, so a second plan or
  a later stroke never pays for, or avoids, plants of the first.
- **Rocks and deadwood under trees** come from dressing specs on the litter.
- **Toe bias** (`dressing.py`, optional per palette): the smallest rock grows toward the toe by `grain`, the sorting
  real rockfall shows. With it off, the rocks are placed exactly as now.

### 4.7 The far field

**One rule places the forest.** The first version let two rules place it: the palettes' forest weights (package 3)
and the ecotopes' tree densities (package 4), written separately over different terms, so a recipe's forest changed
when plants were switched on, and near trees and far canopy could disagree. Now:
- **The ecotope's tree density is the rule.** `plants.expected_cover(terrain, ecotope='auto', data=None)` evaluates
  the tree and shrub densities (exclusions, shade and yield included) on every level as rasters, with no sampling and
  no plan: `canopy_expected` = 1 − exp(−Σ density × crown area), and `shrubs`. `make_terrain` stores them in the bake
  (`extra=`) whenever the palette has a canopy layer, with plants or without. With a plan, `PlantSpots.cover()` gives
  the same `canopy_expected` and adds `canopy` (the placed crowns) and `canopy_far` (the part the instances leave to
  the material).
- **The palettes read it.** A forest or chaparral layer's weight is a function of `canopy_expected`, its tone and
  ramps may still read terrain terms, and its stand-in crowns cover `canopy_far` (equal to `canopy_expected` without
  a plan). The layer's own expression of today stays as its `fallback` key, which the material uses only when it has
  no baked data (tests, hand-built meshes).
- **Inside the instanced radius,** the layer is the forest floor (litter) under the real trees, and its stand-in
  crowns are off there, because `canopy_far` is 0 where the instances stand.
- **Beyond it,** the crowns cover `canopy_far`, with clumps at the cluster process's σ.
- **The hand-off.** The billboards drop out and the material crowns fade in over the same 0.8-1 × radius band, both
  from one density.

So the forest's edge, density and clumping are one forest from 1.7 m to the horizon, the same with plants and
without, and the material and the instances never draw two forests over each other.

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
- **`palettes.py` is inside six recipes' keys too.** `strata.palette_for` deep-copies `PALETTES['desert_sandstone']`
  and `PALETTES['badlands']` into the defaults of `canyon`, `incised_meanders`, `mesas_buttes` and `badlands`;
  `tower_karst` and `sea_cliffs` keep `palettes.get()`'s output (with `DEFAULT_OPTIONS` filled in) in theirs, and
  `tower_karst` calls `palettes._cliff`. So:
  - new material options take their defaults in `surfacing.py` through `opt.get`, never in `DEFAULT_OPTIONS`;
  - the `PALETTES` entries, `DEFAULT_OPTIONS`, `_cliff` and the helpers those recipes reach change only through
    `RECIPE_LOOKS` and looks applied after them; constants written into every palette stay `_FILLED_CONSTANTS`;
  - package 3's `surface_look/test_cache_keys.py` computes every recipe's cache key with HEAD's `palettes.py` and
    with the working copy, and fails on any difference. Package 3's edits so far keep all fifteen keys.
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
| 1 | **Surface data** | `terrain/surface/*` (new), `blender/tests/terrain/surface_data/` | sections 2.2, 2.3, 2.6, 2.7: the registry (with `canopy_far` and `slope_20m`), the bake and its kernels (metre-scale crest, world-keyed gullies, warm-started routing, face-mean provenance), twins, atlases and their files, the surface cache's own root, the palette bake (C as the near material's expectation, P), the mask language in GLSL and the noise port | yes: short kernel runs, and renders for the noise parity |
| 2 | **Material** | `build/surfacing.py`, `build/mesh.py`; in `blender/tests/terrain/surfacing/`: `test_surfacing.py`, `test_shimmer.py`, `shimmer_metric.py`, `bench_material.py`, and new tests | sections 2.4, 2.5, 3.3-3.7: first the full-configuration measurement (8.1), then the two-slot reader, normals, hex tiling, fixed sector frames, the footprint with widened windows, the far hand-off and far material, material_index per ring by camera, the `fallback` weights, `strata_array`, the `eido_terrain_map` node group, and the stride-1 comparison (8.12) | yes: compiles, benches, renders |
| 3 | **Look** | `build/palettes.py`, `blender/tests/terrain/surface_look/` (new) | sections 3.1, 3.2, 3.6, 3.9: new mask names in `known_mask`, ramps and `ramp_rows`, satmap, provenance, patina and freshness keys, `snowpack` snow, cliff-only strata, terrain-term weights (no `settle` on gentle ground), canopy layers on `canopy_expected` with their `fallback`, `latitude_deg` and `climate_sun`, every recipe's look against its photographs, the photograph colour sampler, the cache-key test | yes: renders of sixteen recipes |
| 4 | **Plants** | `build/plants.py`, `build/ecotopes.py`, `build/plant_instances.py` (new), `build/dressing.py`, `blender/tests/terrain/plants/` (new) | section 4: rules on level-independent terms, sampling, spots and their format, `expected_cover` with no plan, cover rasters, flora and SeedThree instancing, LOD (shrubs never realised, hero LOD0 per frame, billboards matched), the far-field hand-off, the toe bias | yes: SeedThree bakes, renders |
| 5 | **Judge and integration** | `blender/tests/terrain/surfacing_judge/` (new); in `blender/tests/terrain/surfacing/`: `review_views.py`, `review_board.py`, `render_places.py`, `layer_map.py`, `sheet.py`, `_place.py`, `calibrate_light.py`; `terrain/api.py`, `terrain/__init__.py`, `tools-guides/terrain-surfaces.md`, the `docs/TOOLS.md` row | section 6's measures as diagnostics against each place's reference, and boards from wave 1; camera fixes for views that face walls; then the wiring: `make_terrain(..., surface='auto', plants=None, cameras=None, mask_attributes=True)`, `canopy_expected` stored in every bake whose palette has a canopy layer, `Terrain.surface`, `Terrain.plants`, `terrain_surface(obj)`, save and load; the guide (the mask attributes and `eido_terrain_map`); the review videos | yes: judge renders and videos |

### 5.3 Interfaces

- **Package 1 provides:**
  - `bake_surface(terrain, palette=None, options=None, cache=True, extra=None) -> SurfaceData`.
  - `SurfaceData.levels`, `.layouts` (per family: per level the atlas rectangle and texel), `.maps(level) -> {name:
    array}`, `.at(name, x, y)` (bilinear on the finest level, like `MaskSet.at`), `.channel(name) -> (family,
    channel, decode)`, `.images() -> {family: Image}`, `.save_images(folder)`.
  - `extra={'canopy': [array per level], ...}`, for the plant layer's rasters.
  - `maps.MAPS`, the registry, with `canopy_far` (and `shrubs_far`) registered beside `canopy`, `canopy_expected`
    and `shrubs` (package 4's `cover_extra` already makes them), and `slope_20m` as a derived name (from `n20`).
  - `images()` may return one Image for several families (the M lever, 2.6); readers count distinct images.
  - The surface cache's root: `EIDO_SURFACE_CACHE`, else `<repo>/eidoverse/assets/cache/terrain_surface/`.
  - The first deliverable is a `SurfaceData` that packs the existing masks into atlases with pins and gutters and
    no new kernels, so package 2 can build on it at once.
- **Package 2 provides:**
  - `surface_material(..., data=SurfaceData)` and `apply_surface(obj, ..., data=, cameras=None)`: `cameras`, a list
    of positions (or camera objects, or points along a path), decides which rings take the far material (3.7).
  - `strata_array(column, ...) -> (rgba, z_lo, z_hi)`, the numpy half of `strata_image`, for packages 1 and 4.
  - Options: `detile='hex'`, `hex_m`, `hex_rotate`, steep `'sector'`, `detail_strength`, `far_m` (the hand-off
    distance D0; it replaces the first version's `far_handoff_px`), `pixel_angle`. Their defaults live in
    `surfacing.py` (5.1).
  - The layer key `fallback`: an expression the material uses in place of `weight` when it has no baked data.
  - The node group `eido_terrain_map` (a map's name in, its decoded value out, through the two-slot reader), for
    agents' own materials.
  - `mesh.make_object(..., mask_attributes=True)`: the `eido_<mask>` attributes, kept by default.
- **Package 3 provides:**
  - Palette keys: `ramp`, `satmap`, `provenance` (`src` and `down` amounts), `patina`, `fresh_gain`, and `fallback`
    on every canopy layer (its weight of today).
  - `palettes.ramp_rows(pal) -> (rows (R, 256, 4) sRGB, {ramp: row})`. Package 2 makes the LUT image; package 1
    bakes C with the same rows.
  - `known_mask` accepts the names in `maps.MAPS`.
  - New terrain constants in `CONSTANTS`: `latitude_deg` (default 40, per place in the looks), `wind_azimuth_deg`
    (streaks, slip faces) and `pixel_angle` (the footprint). `sun_azimuth_deg` and `sun_elevation_deg` stay, as
    overrides a palette may set; otherwise `palettes.climate_sun(constants) -> (azimuth_deg, elevation_deg)` derives
    them from the latitude, for the bake, the plants and the material alike (2.2). The render's sun is never passed.
- **Package 4 provides:**
  - `plan_plants(terrain, ecotope='auto', focus=None, radius_m=None, seed=0, data=None) -> PlantSpots`.
  - `PlantSpots.save(base)`, `.load(base)`, `.cover(level) -> {'canopy', 'canopy_expected', 'canopy_far',
    'shrubs', 'shrubs_far'}`, `.cover_extra()`.
  - `expected_cover(terrain, ecotope='auto', data=None) -> {'canopy_expected': [array per level], 'canopy_far':
    [...], 'shrubs': [...]}`: the densities' rasters with no plan, in the form `bake_surface(extra=)` takes (4.7).
  - `instance_plants(spots, terrain, collection=None, lod=None) -> {species: objects}`.
- **Package 5 provides:**
  - `make_terrain(..., surface='auto', plants=None | 'auto' | dict, cameras=None, mask_attributes=True)` and
    `Terrain.surface`, `Terrain.plants`. With a palette that has a canopy layer, the bake always holds
    `canopy_expected` (from the plan when there is one, else from `expected_cover`).
  - `terrain_surface(obj)` for a reopened .blend.
  - The judge commands (section 6).

### 5.4 Acceptance: looked at beside the photographs first, measured second

**Package 1: Surface data.**
1. Map sheets, each map beside the hillshade at the main and one hero level: Toroweap, Lauterbrunnen, Meteor Crater,
   Great Sand Dunes and the Badlands (`real_place`), and the `canyon` and `alpine_valley` recipes. Each sheet is
   looked at and described:
   - `crest` picks ridges, rims and ribs at their scales;
   - `cavity` and `crease` pick the creases;
   - `settle` marks benches, ledges and slope feet on slopes;
   - `snowpack` fills gullies and benches with bare ribs between;
   - `src_strata` gives a talus below a banded wall the wall's mix, not the bed at its foot;
   - `grain` runs from 0 at a cone's apex to 1 at its toe on a 50 m cone as on a 300 m one;
   - C_down carries the upstream rock's colour into washes and fans;
   - `fresh` marks failing faces and scoured channel floors, not every slope, and not the pour-overs' curtains.
   Two further readings per sheet:
   - **Gentle ground.** On ground under 15°, each map's 5-95 % spread is reported. Every map a gentle-ground rule
     reads (`crest`, `valley`, `cavity`, `wetness`, `canopy_expected`) varies there; `settle`'s flat 0.5 is expected.
   - **Parent and child.** Over the same ground, each map on a child and on its parent: the overlap of the two at
     the palettes' thresholds (overlap over union) and their correlation, reported per map. A map whose two levels
     disagree (overlap under 0.6) is fixed before the looks read it. `crest` in cells measured 0.00-0.76 here; in
     metres 0.68-0.90.
2. Every kernel equals its twin (96×80, within 1e-4 of the range). The noise port equals Blender's Noise Texture node
   within 1e-3. `expr_glsl` equals `palettes.evaluate` on every palette's noise-free expressions within 1e-5.
3. Seams: at every window edge, every map's child equals its parent within 1 % of the map's range. A top-down render
   of D across a window edge shows no line at 2× zoom.
4. Hero drainage: at the `fluvial_range` canyon_road focus, the trunk's catchment stays within 15 % from the main
   level to the finest hero level (the fluvial package measured 37 → 1.5 km² there), with the routing warm-started.
5. Cost recorded, on a quiet slot, against section 7: cold, the seven-level Toroweap terrain (its record today: 200 s
   on a loaded machine, 6-86 s a level); a cache hit with the atlas files present (today 20 s); the palette bake
   (C and P); the disk per terrain.

**Package 2: Material.**
0. **First, the full configuration, measured cold** before anything is built on it: the two-slot reader, hex tiling in
   the planar and the sector reads, the footprint with widened windows, the ramps and the LUT, on the canyon's and
   the alpine palette. Record the samplers, the cold compile in one process and the material seconds per frame.
   Past 1.5× today's compile or 26 samplers, the levers of 8.1 come first.
1. **The reader, before anything else is built on it.** Grazing renders at 1× across each window edge, and a
   moving-camera video (a dolly crossing each edge), show no seam ring, on a plan with centred hero windows and on
   one whose focus sits near the main tile's edge (a hero window clamped 16 cells inside its parent). On edge pixels the error against a read with
   no mips stays within twice the error elsewhere (probe D's measure). Parity: a top-down emission render of maps
   read through the material equals the bake's arrays, within 1/255 for RGBA8 maps and 1e-3 relative for 16F, on
   every level.
2. **Sectors on real walls at their world positions:** the canyon's brink_down right-hand wall, and a 250 m crop of a
   cached 0.98 m hero level, each with a colour grid and then with the scans, beside the Box projection, at 2×
   crops. A planar test wall cannot show a frame that turns with the pixel, so it is not the check. Grid cells read
   square, with no streaks, no seam where the slots meet, and no visible repeat of the tile across a big wall.
3. Hex tiling: close-ups at 2-20 m (2× crops) show no mip seam lines. On the canyon plateau, the talus aprons and the
   Lauterbrunnen floor, the repetition peak is reported beside the photographs' (0.03-0.11; talus today 0.17-0.22),
   with the crop's high-pass energy against today's render, so blur cannot pass for de-tiling.
4. The shimmer probe scores no worse than the old material's + 0.02, and the review video frames hold still in
   motion.
5. Seven Sisters `from_the_sea`: a continuous chalk face, no teeth.
6. **The far hand-off:** an eye-level dolly and an aerial orbit across D0 on the canyon and `alpine_valley`. Across the
   band the mean colour changes by ΔE ≤ 2 (frames at the band's two edges, matched regions), and no ring shows at
   1× in motion. Past that, C is rendered instead (2.3's fallback).
7. **Eye-level views on context rings:** `impact_crater` plain_north, `real_place` ridge_schynige and
   `alpine_valley` shoulder_wengen show their foreground through the near material, beside their photographs.
8. **Stride 1** (8.12): the canyon's brink_down and approach_walk with rings at stride 1 (`MESH_RES` 1024) beside
   stride 2 with D's normals. Record vertices, build seconds, frame seconds and VRAM, and look at ledges and their
   shadows beside tw_03 and tw_04. The choice goes in the report with that evidence.
9. **The LUT:** at grazing angles, the material's own LUT reads no other row's colour (probe D's check, on the
   palette's ramps).
10. Cost on the bench scene, beside the old material in one process. A material switch can trigger a shader
   recompile: probe B's run cycling seven materials spent minutes recompiling. So every timed frame follows a
   discarded warm-up frame, never a switch. `bench_material.py`, which alternates materials frame by frame, is
   updated to do the same.
   - material at most 2.0 s per frame;
   - near material compile at most 1.5 × the palette's today, cold, in one process; far material compile at most
     10 s;
   - the viewport at one sample at 5 fps or more. A material at 1 fps is broken, not heavy.

**Package 3: Look.**
1. Every recipe's matched views beside the photographs (boards: photograph, v-current, new, layer map) read as the
   place, item by item against section 3.9's table, described per view.
2. The crater's walls and the rocks are unchanged or better beside `impact_crater_v5`; the canyon's varnish under
   the pour-overs is kept, beside tw_03 and tw_07.
3. The measures, with package 5's tools, sit beside each board as diagnostics, each against the same measure on the
   place's reference (6): the one-material share against the reference's own, the height-line index, repetition with
   its energy floor, ground colour after exposure matching. A measure that disagrees with the eye is named in the
   description, and the eye decides. The board read is the pass.
4. `surface_look/test_cache_keys.py` passes: every recipe's cache key equals HEAD's (5.1).
5. The forests and the chaparral read the same with `plants=None` and with plants, side by side: Lauterbrunnen,
   Crater Lake, the San Gabriels.
6. The three eye-level views on context rings (package 2's check 7) are in the boards.

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
   Each species' billboard beside its LOD2 at the switch distance under `make_sky` (4.4) is in the boards.
3. Eye-level frames render in at most 8 s at 960×540, 16 samples; instancing the review views takes at most 20 s;
   no shrub, grass or forb is realised, and at most 64 trees are LOD0 in any frame.
4. A plain JavaScript reader (Node, as `loft_dump.mjs` runs: fs and Float32Array) round-trips the format.
5. **No step at a window edge:** per species, stems per hectare in 50 m strips either side of every window edge on
   Lauterbrunnen and the canyon agree within 10 %.
6. `expected_cover` with no plan equals a plan's `canopy_expected` (the same densities), and `canopy_far` is 0 where
   the instances stand.

**Package 5: Judge and integration.**
1. The measures reproduce the audit's baseline numbers on the 11-13 renders (coverage, height-line index, repetition)
   within 10 %, and each is reported against the place's reference (6).
2. Every recipe's boards and review videos exist for the final state.
3. `make_terrain(..., surface='auto', plants='auto')` runs end to end and through save and load; with `plants=None`
   the bake still holds `canopy_expected` for a palette with a canopy layer; `cameras=` gives the far material only to
   rings beyond 1.5 D0; the `eido_<mask>` attributes are on the mesh by default.
4. The guide's examples run.

### 5.5 Waves

1. **Wave 1, all at once:**
   - package 1: atlases of the existing masks first, then the kernels;
   - package 4: planning on the numpy masks `t.masks` already gives, and instancing;
   - package 5: the measures and baseline boards on today's renders;
   - package 3: everything that needs no new map (cliff-only strata, ramps on today's masks, recipe looks), while
     the attribute path still works.
2. **Wave 2, as soon as package 1's first `SurfaceData` lands:** package 2, starting with its checks 0 (the full
   configuration, cold) and 1 (the reader's seams, in renders and a moving camera) before anything is built on them.
   Packages 3 and 4 move to the new maps as package 1 adds them, and agree on the forest now: the ecotopes' tree
   densities are the one rule, the palettes read `canopy_expected` (4.7).
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
2. No flat single material where the place is not one. A continuous chaparral, conifer forest, wheat field or dune sea
   is one material in the photograph too and reads right as one, with variation inside it.
3. No tiling at any distance.
4. Relief reads at every distance: rills and gullies at mid distance, crisp crests and dark creases.
5. Debris and sediment carry their source's colour.
6. Steep faces show no smear and have vertical structure.
7. Plants stand where the place grows them, as objects near and canopy far, as one forest.
8. Nothing changes as the camera moves: no shimmer, no seam ring, no LOD pop. Checked in the videos.

**The measures** (`blender/tests/terrain/surfacing_judge/`, numpy and Pillow) are diagnostics. They sit beside each
board and are never a pass line on their own: a scorer can be satisfied while the look gets worse. Blur passes a
repetition test. Noise or diagonal patches lower a height-line index on bedded walls, where the real cliff, talus and
bench boundaries do follow the beds. The means move with exposure and haze. So each look measure is computed the
same way on the place's reference and read against it: the matched photograph's ground region, and, if the lead
fetches them, an orthophoto over the place's DEM (NAIP for the US places, SWISSIMAGE for Lauterbrunnen). A measure
that disagrees with the eye is named in the read, and the eye decides. Shimmer, seams, plants' spacing and cost are
defect checks, not look measures; they do gate.

| measure | how | read against |
|---|---|---|
| one-material share | on the main tile (the layer weights evaluated on its maps, composited as the material does) and in each frame (the layer map): the share where one layer holds ≥ 90 % of the weight, and the largest connected region one layer dominates (the audit's `pure` and `largest`) | the reference's own share: its ground clustered into as many classes as the frame has layers (k-means on Lab and local contrast), its largest connected class region; flagged when the render's passes it by more than 10 points. A first-version line of 35 % would have split the San Gabriels' nearly continuous chaparral |
| within-layer variation | the spread of 32 px block mean luminance inside one layer, against the photograph's ground blocks | the photograph's ground blocks: flagged under half their spread |
| repetition | the second peak of the 2-D autocorrelation of high-passed luminance in ground crops (the audit's measure), with the crop's high-pass energy | the photographs' peaks (0.03-0.11), and an energy of at least 0.8 × today's render's in the same crop, so blur cannot pass |
| height-line index | on the main tile, the weight-gradient-weighted mean of \|cos\| between each layer's exclusive weight gradient and the height gradient (the audit's contour index): 1 when every boundary is a height line, 2/π = 0.64 at random; on all ground and on slopes over 25°, the strata bed edges excluded | today's render (0.77-0.94 on walls), random (0.64), and the board: where the place is bedded, its boundaries follow height lines in the photograph too |
| colour | Lab mean and the a*/b* spread of the ground region after matching the render's mean luminance to the photograph's; the hue relationships between regions (talus against cliff, floor against wall) | the photograph's: ΔE of the means and the spread ratio, read with the board; the hue relationships in the photograph's direction |
| shimmer | the existing probe | the old material's + 0.02 (gates) |
| seams | the mean colour difference across each window edge's band and across the far hand-off band, in grazing renders and in motion | ≤ 2 ΔE (gates) |
| plants | stems per hectare against the ecotope's range and either side of each window edge; the trees' pair correlation g(r): clustered at σ, inhibited below the core | in range, within 10 % across an edge, the right shape (gates) |
| cost | seconds per frame, compile seconds, VRAM | section 7 (gates) |

**The videos.** Per recipe, an 8 s aerial orbit and a 6 s eye-level dolly (`judge/video.py`), H.264 High yuv420p,
checked with ffprobe. They are watched, for shimmer, seams and pops.

---

## 7. The performance budget (this machine)

| what | budget | basis |
|---|---|---|
| bake, per level, cold | ≤ 15 s at 1024², ≤ 30 s at 2048², on a quiet slot | measured by package 1 (Toroweap, seven levels of 1000², a loaded machine): 6-86 s a level. Its largest parts: hero routing 2.3-28.5 s at 1,280-2,688 passes started cold (warm-started from the parent now), one fill 21 s, pins up to 12.6 s, input reads 0.5-10.6 s, detail readback 0.8-6 s. The kernels' arithmetic is small (about 0.06 ms per 3×3 pass at 1024², DESIGN.md 1.2); the time is in pass dispatch, readback and numpy, which is where the fixes go. The first version's 1.5 s assumed the arithmetic alone |
| bake, a seven-level film terrain, cold | ≤ 90 s | today 200 s |
| atlas files, written once per bake | ≤ 60 s | today 145 s to assemble eleven atlases and 65 s to save them |
| cache hit: atlas files present, images ready to render | ≤ 10 s, in every process | today 20 s (npz loads, before the images). Probe D loaded package 1's eleven Toroweap atlas files (643 MB, D a 399 MB float32 EXR) with `bpy.data.images.load`: 12.3 s to decode (D alone 4.3 s), then 2.2 s for their first upload. D and F as half EXRs and D and E at the cell on the fine levels (change 16) take about half of that |
| palette bake (C at 4 × 4 sub-samples, P) | ≤ 30 s per palette cold; cached by the palette's hash | C: one pass per level at sixteen sub-samples; P: routing over the converged weights, batched, or deferred past the budget (2.3) |
| disk per terrain, in the surface cache's own root | ≤ 1.2 GB | today 480 MB of npz (float16) and 643 MB of images (D as a 399 MB float32 EXR; half with ZIP is well under half of that) |
| plant planning | ≤ 10 s for 10⁴ trees and 10⁵ shrubs | numpy, like the rocks (400k) |
| plant instancing | ≤ 20 s, plus SeedThree's one-time growth and bakes (cached on its side) | |
| near material compile, cold | ≤ 1.5 × the same palette's today, measured cold in one process; never over 120 s | today 15-110 s cold, by palette and machine load; probe B: hex 87 s, hex + sectors 117 s (without hex inside the sectors, the reader, the footprint or the ramps), today's desert material and its data-read variants 83-110 s under load. The driver caches a compiled shader: the same GLSL again took 3-8 s. The margin is thin, so package 2 measures the full configuration first (5.4, check 0) |
| far material compile | ≤ 10 s | probe B: 3.2 s cold, 0.6 s cached |
| material build (Python creating the nodes) | ≤ 30 s | today 12-26 s for 1,001 nodes; probe B's hex variants as loose nodes 59-152 s, hence the node groups of 3.3; the two-slot reader is one more node group of about 300 nodes, built once |
| material cost per frame, bench scene, 960×540, 16 samples | ≤ 2.0 s | today 0.70-1.31 s by palette; probe B on the desert material (1.0 s today): hex, sectors or both 0.9-1.5 s, the far material 0.03 s |
| a review frame, 960×540, 16 samples | aerial ≤ 3 s; eye level with plants ≤ 8 s | today: aerials 1.5-2.4 s, eye views 3.5-6.0 s |
| a review frame, 1920×1080 | ≤ 4× the 960×540 frame | pixel count |
| viewport | ≥ 5 fps at one sample | a 1 fps material is broken |
| data texture memory | ≤ 900 MB at film quality, ≤ 1.2 GB at hero quality | 2.6 |
| VRAM per render | ≤ 4 GB (the slot) | data + scans (≈ 270 MB) + EEVEE + geometry |

---

## 8. Risks and open questions

1. **Compile time and samplers.** The two-slot reader adds about 300 nodes, hex tiling about 200 per planar layer
   (probe B: 1,001 → 1,688 nodes for three planar layers), sectors about 30 per box layer plus hex inside them.
   Compiles already take 15-110 s cold, probe B's hex plus sectors 117 s, and the samplers come to 23-27 of 28.
   - Package 2 measures the full configuration first, cold, in one process (5.4, check 0). The driver caches a
     compiled shader, so a repeat of the same GLSL is not a compile.
   - If a palette passes 1.5 × its old compile, the levers in order: hex only on the mipped Linear reads, with one
     Cubic near read; the bump's heights from the dominant slot only; share the hex grid across layers with the same
     `hex_m`; drop the far reads; move patches into C.
   - If it passes 26 samplers: the M families packed into one shared image (2.6).
2. **The Bump node evaluates its height input three times.** The cheap coverages now read atlases, and the sector and
   hex heights sit under the bump, so three times those reads. Package 2 measures it; the levers are to weight the
   bump by atlas values read once, outside the bump's input, and to take the bump's height from one slot.
3. **The hero inflow defect** in the level runner. The bake routes the hero levels' drainage again with pinned inflow
   (2.3, step 8), so the material and the plants get right `flow`, `wetness` and `channels`. The geometry's valley
   floors still need the fluvial package's fix in the runner, which is outside this round.
4. **Near against far colour.** If C and the near material differ, a ring shows at the hand-off. Mitigations: one
   monotone distance per material, never inside a hero window (3.7); C defined as the near material's expectation
   there, sub-sampled, on the mesh's own surface (2.3); the footprint fades that keep coverage (3.2); the measured
   check in motion (5.4, package 2, check 6); and the exact fallback, C rendered from the near material itself.
5. **Mip bleed across atlas tiles** at grazing angles. Mitigations: the two-slot reader keeps every quad that has
   weight on one level's tile (2.4); the gutters hold real data out to 32-64 texels; 16× anisotropic filtering.
   Package 2's check 1 looks for it in renders and in motion.
6. **Ramps from photographs can drift back to judging by eye.** Mitigation: measured Lab spreads per layer region.
   Orthophotos per mask bin are the stronger source, if the lead fetches them.
7. **No spruce in SeedThree.** Douglas fir stands in. If it reads wrong beside lauterbrunnen_01, the options are a
   SeedThree preset dialled on the eidoverse side, or flora shrubs and scanned plants near with billboards far.
8. **No recent-wear field.** No solver writes `wear_recent`, so freshness comes from threshold exceedance on steep
   ground and stream power on gentle ground (2.2). A post-pass that differences h between a run's last epochs would
   give real freshness, scars included. That touches the runner, outside this round.
9. **VRAM.** Data textures of about 0.7-0.85 GB beside other jobs on a shared GPU. The levers: masks capped at 1024,
   F only when read, D and E at the cell on fine levels (done), the M families in one image.
10. **Licences.**
    - Blender's shader noise is GPL-2.0-or-later, compatible with this AGPL-3.0 repository.
    - Hex tiling is implemented from the published description (Mikkelsen's demo is MIT; keep its notice if any code
      is copied).
    - The gully filter is our own `detail.py` port.
    - The Shadertoy erosion-noise ports (CC BY-NC-SA) are not to be copied.
11. **The cache.** Every new file lies outside the field cache's globs, and `masks.py` does not change. `palettes.py`
    reaches six recipes' keys through the palette copies they keep, so its rule and test (5.1) keep every terrain
    from regenerating for this round's work.
12. **Stride 1 is not measured yet.** Meshing the main and hero rings at stride 1 (about 4× those rings' vertices)
    would give ledge shadows from geometry, as World Machine and Gaea renders have, remove the gap between the mesh's
    z and the field's h, and sharpen the chalk brow. It does not give the material per-texel data or relief below
    the cell, so it complements D rather than replacing it. Package 2 renders the canyon both ways before choosing
    (5.4, check 8); the levels, the masks and the bake do not depend on the choice.
13. **Where this revision departs from the critique's proposals,** with the evidence:
    - *Sector frames.* The critique proposed vertical frames (v = z) with a second family tilted 45° blended by dip.
      One family tilted 65° measures p50 1.04-1.07 and p99 1.09-1.13 on the canyon's walls, where vertical frames
      measure p50 1.22-1.26 (probe C); a second family would double the steep faces' reads (twelve per map with hex
      tiling). The critique also proposed picking the sector by `n20`'s azimuth; on the 0.98 m level that put p99 at
      14×, the face's own normal 1.13 (probe C).
    - *The reader.* The design takes the critique's dead band as it proposed it. I also tried moving the switch 24
      cells out into the gutter, which needs no footprint: it helps only at oblique views (probes D, E), so it is
      not in the design. The critique's alternative, Cubic reads on M and E with no mips, aliases wherever a texel
      spans less than a pixel (aerials, grazing ground) and would shimmer; the two-slot reader keeps the mips. If it
      fails check 1, the Cubic alternative is measured with the shimmer probe before anything else.
    - *Hero re-routing.* The critique would keep it only if it changes the look. It does: on Lauterbrunnen's 2 m level
      it restores the valley's trunk the runner loses. It stays, warm-started.
    - *A new gentle-ground term.* The critique asked for one, in metres (a multi-scale depression depth, or a relax
      relative to the local trend). −`crest` at metre scales is that depression index, on the blur pyramid the bake
      already has, and it varies on gentle ground; no new map is needed. `settle` keeps its encoding so the rules
      already written against it do not break.
    - *C rendered from the near material.* The critique calls it the exact route. It stays the fallback: package 1
      has built the GLSL port of the mask language and Blender's noise, and the render route costs a near-material
      compile per palette (83-117 s cold in probe B). The check in motion decides.
    - *P in one sweep.* A topological sweep is sequential and does not map onto the bake's GPU passes; P keeps
      Jacobi passes, batched and started from the parent's values, and is deferred if it passes its budget.

---

## Appendix: the probes behind section 1.3

Scripts and logs are in the lead's scratch folder, not in this repository; the numbers are here.

| probe | what it ran | result |
|---|---|---|
| A, sampler limits | a 24 px emission plane, one material per case, 1 sample; a failed material renders magenta and logs "uses too many samplers (n/32)" | 28, 29, 30 distinct images compile; 31 (33/32) and 32 (34/32) fail. 13, 14, 15 two-tile UDIMs compile; 16 fail (34/32). 14 images + 7 or 8 UDIMs compile, + 9 fail (34/32). 28 images + one 7-tile UDIM read 12 times compile. 28 images + a Cubic, a Closest, an EXTEND and a CLIP read of four of them fail (33/32). A UDIM's tile 1003 reads its own value with Linear, Cubic and Closest |
| A2 and A3, images made in memory and float precision | as A, the material emitting (v − ⌊v⌋) × 100, so the half-float film does not hide the texture's own rounding | half (default): 1234.567 → 1235, 37.123 → 37.125. 32-bit (`use_half_precision` False): 1234.567 and 37.123 arrive intact. Colour space set after the pixels: 0 at every texel. A 1088 × 16,448 float atlas: its top tile read exactly; filled in 0.17-0.43 s. Packed 4 × 4 float image: 1.0 at every texel on the GPU, though the CPU pixels stay intact (a CPU-only check). The GPU reports OpenGL, max texture size 32768, 2048 layers, 32 fragment samplers |
| B, frame cost and look | the material bench's scene plus a 45° diagonal wall, 960×540, 16 samples, AgX; the desert_sandstone material as it is, with hex tiling on its planar layers, with sectors on its box layers, with both, plus twelve reads of six RGBA16F atlases (seven levels of 1024 with 32-texel gutters, the level chosen per pixel), and a far material of those reads alone | Per variant, one process: build, a warm-up frame, four timed frames, then clay beside it the same way. Material per frame, best frame minus best clay: today's 1.03 s (1,001 nodes); hex 1.50 s (1,688); sectors 1.03 s (1,091); both 0.92 s (1,778); far 0.03 s (142 nodes). Cold compiles 83-117 s for the full variants, 3.2 s for the far material; a repeated GLSL 2.5-8 s. A first pass that cycled seven materials frame by frame stalled for minutes recompiling, so timed frames never follow a switch. Look: on the 45° wall the Box projection drew two soft, doubled crack networks; the sectors drew one crisp network at the scan's scale, repeating every 9-10 m (hence hex inside the sectors). Hex tiling changed the planar ground's layout with no seam line at 3× zoom; this view had little planar ground. A run in A/B passes, every variant revisited each pass after a warm-up so the load falls on all alike, was stopped before its passes: the machine's CPU stood at 100 % and today's material alone took 127 s to build. That protocol is the one for package 2 |
| C, steep-face frames on a real terrain (numpy, 2026-11-14) | the cached canyon `e67bc9fe`, levels 1, 3 and 4 (7.8, 1.95 and 0.98 m; 159,918, 30,717 and 629 cells steeper than 47°). Per projection, the texture mapping (u, v) differentiated on the surface z = h(x, y) and its singular values taken against surface distance (the critique's `sector_stretch.py` method). Two slots, even and odd sectors, weighted with a 4.5° dead band; the off-scale factor weight-averaged over both slots | off-scale p50 / p99 by level (7.8, 1.95, 0.98 m). Box: 1.30 / 1.81, 1.32 / 1.83, 1.37 / 1.81. Fixed vertical frames picked by the 20 m normal: 1.24 / 1.80, 1.28 / 4.21, 2.00 / 14.7. Fixed frames tilted 68°, by the 20 m normal: 1.07 / 1.35, 1.08 / 2.23, 1.40 / 13.6; by the normal at 4 m: 1.06 / 1.13, 1.06 / 1.16, 1.10 / 1.56; by the cell's own normal: 1.05 / 1.13, 1.06 / 1.13, 1.07 / 1.13. Tilted 62°, by the cell's own normal: 1.04 / 1.09, 1.04 / 1.10, 1.04 / 1.09. Hence 65°, by the face's own normal |
| D, the reader, the LUT and atlas files (EEVEE, Blender 5.2, 2026-11-14) | the critique's `probe_reader.py` with two more reader variants (a switch 24 cells out in the gutter; that plus the dead band) and a load test, one Blender run through a GPU slot. A: a 256 × 8 LUT read Linear at anisotropy 2 and 16, Cubic and Closest. B: three nested levels, the reader variants against a Cubic read, three cameras (oblique; 6 m; 2 m). C: package 1's Toroweap atlas files loaded into a material compiled on 8 × 8 stand-ins | A: Linear 87.5 % of the ground bled (2× and 16× alike), Cubic 100 % (≤ 0.38), Closest 0. B: see 1.3. C: decode 12.3 s, first upload about 2.2 s. Renders and arrays looked at: the single read's grey edge line at 3×, none with the dead band |
| E, the reader's level switch, emulated (numpy, 2026-11-14) | `probe_reader.py`'s atlas, pins, field and three cameras (oblique, low at 6 m, grazing at 2 m), rendered as a GPU reads: each 2×2 quad takes one derivative from its own pixels, the LOD is log2 of the larger texel step (isotropic) or max(major / 16, minor) (16× anisotropic), the read is trilinear over a box-filtered mip chain. Variants: one read; two slots switching at the window edge; the same with a dead band of 3 footprints; a switch 24 cells out in the gutter; both, with the dead band uncapped or capped at 4 or 8 cells. Error against the right level read at mip 0 | 16× anisotropic, edge pixels over 0.05 (mean, max): oblique, one read 13.1 % (0.023, 0.46), two slots 0.57 % (0.0028, 0.22), dead band 0.0 % (0.0018, 0.031), gutter 0.0 % (0.0020, 0.031); low, one read 17.3 % (0.028, 0.44), two slots 2.8 % (0.0086, 0.44), dead band 0.50 % (0.0055, 0.084), gutter 1.2 % (0.0066, 0.33), dead band capped at 8 cells 1.1 % (0.0064, 0.33); grazing, every variant 20-22 % (one read 57 %). Elsewhere: mean 0.0013-0.0017, p99 0.013-0.053. Hence the dead band of 3 footprints, capped only by the nesting's room, and 16× filtering |
