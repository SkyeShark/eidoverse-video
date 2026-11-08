# Ekigar terrain generator (generation core)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition of Ekigar, our WorldMachine/Gaea-class
terrain generator: the typed node graph and its compiler, every operator of
its registry, all 39 landforms, Phacelle erosion, the masks, Ekigar's display
grid and local area, its exports and its headless API, evaluated with numpy.
It replaces round one's `make_terrain` noise ground as the source of terrain;
surfacing (materials on top of the masks) builds on it.

Everything is Python in `blender/eidoblend/terrain/ekigar/`, in Blender axes
(Z up, metres). `build_mesh`, `build_lake_mesh`, `preview_material` and
`export_glb` need Blender; the generator itself is plain numpy. Inside
Blender, import it as `from eidoblend.terrain import ekigar`. In plain
Python (a CPU bake, a test) that import fails for now, because
`eidoblend/terrain/__init__.py` imports round one's `make_terrain`, which
imports `bpy`; load the subpackage on its own through the tests' loader
until that `__init__` imports lazily:

```python
import sys; sys.path.insert(0, '<repo>/blender/tests/terrain_ekigar')
import _ekigar_load
ekigar = _ekigar_load.load()        # the real package inside Blender, a standalone copy outside
```

Probes and tests: `blender/tests/terrain_ekigar/`.

The fields are Ekigar's own. The parity tests run Ekigar's real `compile.js`,
`registry.js`, landform files, `local_area.js`, `mixed.js`, `terrain_mesh.js`
and `model.js` under deno, with `three/tsl` swapped for a CPU evaluator
(`tsl_cpu_shim.mjs`, float64, one lane per pixel), and compare everything the
port produces: 194 operator probes (every enum arm, named output, mask wire,
warp, disabled node and all 24 Combine modes) and 345 landform probes (every
landform standing alone and on terrain, every output, every enum arm, the
scattered `count` path) agree on every texel and channel to 6e-14 of the
channel's scale at worst (operators 7e-15); the local area, the
display grid, the project migration and the registry schema match exactly,
and the map set (`export_maps`) and plain heightmaps (`export_heightmap`)
decode to the same samples as `bake.js` and `heightmap.js` write (the raw
formats byte for byte).
Project files written the way Ekigar's Save button writes them (portals,
groups, tabs, a disabled node, a mask target port, a Material Map beside the
terrain) load and evaluate to the same field (`test_project_files.py`).
`test_ekigar_suite.py` runs Ekigar's own unit suite against the port (field,
graph, wiring, registry schema, landform library, material contract,
projects, PNG and heightmap round trips, terrain masks) plus the plan's
section-14 harness.

## `generate` — a terrain from an operator, a graph or a project file

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.terrain import ekigar

hf = ekigar.generate('volcano', resolution=512, world_size=400)            # one operator, defaults
hf = ekigar.generate('mountainRange', params={'style': 'alpine', 'relief': 0.8},
                     resolution=1024, world_size=3000, z_base='min')
hf = ekigar.generate('valley.ekigar.json')                                   # an ekigar-project/3 file
```

`generate` returns a `Heightfield`:

- `hf.height` — Ekigar's field height (one unit of height is
  `vertical_scale × world_size` metres; Ekigar's defaults are 0.3 and 400 m).
- `hf.heights_m` — Blender z of every texel, metres; `z_base` says what sits
  at z = 0: `'field'` (Ekigar's frame), `'min'`, `'mid'`, `'max'` or a value.
- `hf.field` — all four channels: height, the carried gradient dh/dx, dh/dy,
  and aux (the erosion's ridge map, or the operator's own channel).
- `hf.mask(name)` / `hf.masks()` — every mask by name (below).
- `hf.height_at(x, y)` — metres at Blender (x, y), on the mesh `build_mesh`
  makes: it uses the triangle split Blender renders a quad with, so feet and
  props sit on the rendered surface (ray casts at 400 random points land
  within 1.2e-5 m). `height_at(x, y, side=N)` reads a display-grid mesh,
  `height_at(x, y, wrap=True)` continues across a periodic tile's edge.
- `hf.normal_at`, `hf.sample(mask, x, y)`, `hf.stats()`, `hf.hydrology()`,
  `hf.save('t.npz')` / `Heightfield.load('t.npz')`.

The tile spans x, y in [−W/2, W/2] around `origin`; texel (i, j) sits at
x = (i + ½)/N·W − W/2, y = (j + ½)/N·W − W/2. Arrays are `[row, column]` =
`[y, x]`, row 0 the south (−y) edge. Ekigar's three.js frame maps as
(u − ½, h·vs, −(v − ½))·W → Blender ((u − ½)W, (v − ½)W, h·vs·W).

Speed (numpy, row bands on 8 threads), measured on the shared workstation:
fBm under erosion 0.6 s at 512², 6–7 s at 1024², 35 s at 2048²; the alpine
range 53 s at 2048²; the cinder cone field 27 s at 1024²; every gallery
scene and option arm at Ekigar's preview size of 256² in 2.5 s or less.
Evaluate a terrain once and `save` it; a shot loads it. The result is the
same byte for byte whatever the banding and the core count, in both
derivative modes (next section): the tests evaluate graphs that
differentiate a value built from a derivative, under erosion, in one band
and in bands of two rows, and compare every byte.

### Screen-space derivatives: `derivatives='coarse'` (Ekigar) or `'central'`

Twelve operators take a screen-space derivative (TSL `dFdx` / `dFdy`) of
something they built: `slopeMask`, `angleMask` and the ten wave-3
landforms (terraceStair, waveCutPlatform, playa, planationSurface,
towerKarst, cockpitKarst, limestonePavement, bornhardt, badlands,
patternedGround), which rebuild their gradient that way. On the GPU a
derivative is a difference inside a 2×2 pixel quad, held constant across
the quad. `generate` and `evaluate_graph` take it the same way by default,
`derivatives='coarse'`, so a graph or a project evaluates to the field
Ekigar draws; every parity test runs this mode.

`derivatives='central'` measures the slope at every texel instead
(`(h[x+1] − h[x−1]) / 2`): smoother slope and angle masks, without the 2×2
blocks. It is not Ekigar's field: on the gallery fixtures the slope and
angle masks change by up to their whole range, the wave-3 landforms carry a
different gradient, and an erosion after a wave-3 landform turns that into
different heights (an fBm under tower karst under erosion: up to 22 m, rms
1.5 m, on 224 m of relief at 512² over 1000 m). Graphs without those twelve
operators are identical in both modes (the alpine film composite is).
Use it when the masks matter more than matching Ekigar, and say so:

```python
hf = ekigar.generate(g, target=ero, resolution=1024, derivatives='central')
ekigar.derivative_depth(g, ero)      # 2: how deeply its derivatives nest (0 = none)
```

A derivative of a derivative needs neighbours two texels out, and so on;
`central` pads every band by the graph's nesting depth plus one ring of
margin. `derivative_depth` measures that depth: nine small windows of the
real grid are evaluated with each derivative's one-sided edge overwritten,
once with huge values of random sign and once with NaN (the one flips
branches, the other survives the clamps that would hide a huge value), and
the depth is the smallest pad that keeps every window's core unchanged. So
the result is exact at band and tile edges. Measuring costs a fraction of a
second; graphs without screen derivatives skip it.

A neighbourhood operator re-evaluates everything upstream of it at each of
its offsets, as Ekigar's compiler does, so its cost multiplies the chain's:
an alpine range, a glacial trough and erosion under `snow` (nine offsets)
took 244 s at 1024² where the same chain without snow takes 27 s. Put
snow, blur, thermal and the curvature masks after the expensive part only
when the look needs it, and cache the result.

Resolution is more texels, not a different terrain. Ekigar measures
neighbourhood radii (blur, thermal, snow, curvature ...) in texels of the
field, so a project authored at `res` 1024 and generated at 4096 keeps its
radii in 1024ths of the tile (`generate` does this by itself for a project;
pass `field_resolution=` for a graph). A 64-texel blur-and-slope graph
evaluated at 128 correlates 0.97 with the 64 result, same mean.

## Graphs — Ekigar's node graph, as data

A graph is Ekigar's: nodes with typed ports, wires, an optional mask wire on
every filter, named outputs, portals, groups, notes and tabs.

```python
g = ekigar.create_graph()
base = ekigar.add_node(g, 'mountainRange', params={'style': 'eroded', 'frequency': 3})
ero = ekigar.add_node(g, 'phacelle', params={'strength': 0.3, 'octaves': 5})
snow = ekigar.add_node(g, 'snow', params={'line': 0.62})
P = ekigar.graph_ports
ekigar.connect(g, {'node': base, 'port': 'out'}, {'node': ero, 'port': 'in'}, P)
ekigar.connect(g, {'node': ero, 'port': 'out'}, {'node': snow, 'port': 'in'}, P)
# erosion only on the high ground: a Height mask wired into the bottom (mask) port
hm = ekigar.add_node(g, 'heightMask', params={'lo': 0.55, 'hi': 2})
ekigar.connect(g, {'node': base, 'port': 'out'}, {'node': hm, 'port': 'in'}, P)
ekigar.connect(g, {'node': hm, 'port': 'out'}, {'node': ero, 'port': 'mask'}, P)
hf = ekigar.generate(g, target=snow, resolution=1024, world_size=2500)
ekigar.save_project('peaks.ekigar.json', g, target=snow, world_size=2500, res=1024)
```

`connect` refuses a wire of the wrong type, to a port that does not exist, or
one that would close a loop, and says why; a second wire into a full input
replaces the first. `chain_graph([(op, params), ...])` builds a linear chain;
`operator_example(op, params)` builds the scene Ekigar's visual suite judges
that operator on. Portals (`create_portal`, `connect_via_portal`,
`convert_to_portal`, `available_portals`), groups, notes and tabs
(`move_to_tab` turns crossing wires into portals) round-trip through the
project file. The wiring heuristics of Ekigar's canvas are here too:
`choose_input_port`, `choose_connection_target`, `downstream_terminal`,
`target_after_add`.

The project format is `ekigar-project/3`: `load_project` migrates older
files the way Ekigar does (a legacy Surface node becomes a one-driver
Material Map; the wiring it cannot represent is archived with a warning) and
keeps every field it does not know.

What the compiler does, as in Ekigar: an output feeding several consumers is
evaluated once; neighbourhood operators (blur, thermal, snow, curvature,
peaks, Texture Base, seamless, dilate, median ...) re-evaluate their input at
offset positions; a Warp node passes its warped position downstream, so the
generators after it build organic landforms rather than a warped copy; a
disabled node passes its input through; a wire into the mask port mixes the
node's result back toward its input. Lattice frequencies snap to whole cells
per tile and every snap is reported in `hf.warnings`, each distinct warning
once (Ekigar's compiler repeats a snap for every resampled evaluation, so a
snow after an erosion reported it nine times).
`compile_preview_graph` is the viewport's safe preview: a mask output keeps
its terrain in xyz and the mask in w.

## Operators and landforms

`ekigar.list_operators()` gives all 99 (with `category`, `doc`);
`ekigar.api.describe(op)` prints one with its ports and every parameter's
range and meaning. Parameter names are Ekigar's (camelCase), so a project
file's params load unchanged.

- Primitives: constant, gradient, radialGradient, fbm, ridged, voronoi,
  perlin, cellular, dotNoise, lineNoise, cracks, shape, cone, hemisphere,
  pattern.
- Simulate: phacelle (erosion), thermal, snow.
- Surface: terrace, stratify, roughen, steps, fractalTerraces, sandstone,
  sand. Modify: curves, clampOp, warp, invert, clip, threshold, softClip,
  gamma, fold, blur, sharpen, median, dilate, recurve.
- Terrain: crater, mountain, mountainRange, canyon, island, volcano, rugged,
  and the 39 landforms: caldera, impactCrater, cinderConeField, maar, cirque,
  basinField, moundField, volcanicPlug, lavaDome, mesa, glacialTrough,
  meanderBelt, faultScarp, graben, dipSlope, esker, moraineSet, streamform,
  oceanRidge, invertedChannel, terraceStair, waveCutPlatform, playa,
  planationSurface, towerKarst, cockpitKarst, limestonePavement, bornhardt,
  badlands, patternedGround, duneField (barchan, transverse, barchanoid,
  linear, star, dome, parabolic), alluvialFan, sandur, delta, spitBar,
  reefRing, beachCusps, lavaField, rockGlacier.
- Derive (masks as nodes): heightMask, slopeMask, angleMask, curvatureMask,
  peaksMask, textureBase. Utility: combine (24 blend modes, three inputs),
  seamless, edgeFade, math, route, switchOp, compare. Material Map is
  declared (its graph contract and band migration) but builds materials, not
  terrain: that belongs to the surfacing step.

Every landform layers onto its input when one is wired and stands alone when
not; most emit coverage masks (a caldera's floor, wall, terrace, rim, dome,
breach; a delta's channel, levee, mouthBar ...). `render_variants.py`
renders every option arm of every operator (132, plus a part-subsided guyot)
into `out/variants/`, on the gallery's camera and light; Combine's 24 modes
there blend the fixture with a ridged field, because Ekigar's gallery wires
the same fixture into both inputs and every mode then blends a field with
itself. One arm to know: `reefRing` with `guyot` at its default full
subsidence is a flat sea floor (Ekigar's own result); lower `subsidence` to
see the flat-topped seamount.

## Masks

`hf.masks()` holds two kinds, all `(N, N)` arrays in 0..1:

- From the finished height by finite differences (Ekigar's `masks.js`,
  every constant kept): `height`, `slope`, `aspect`, `aspectEast`,
  `curvProfile`, `curvPlan`, `curvMean` (0.5 = flat), `concave`, `convex`,
  `converge`, `ridge`, `constant`. Slope and curvature are in world units
  (they depend on `world_size` and `vertical_scale`, as in Ekigar).
- The target node's named outputs: erosion `wear`, `ridge`, `flow`;
  thermal `talus`; snow `depth`; crater `rim`, `ejecta`; canyon `depth`;
  volcano `crater`, `rim`, `breach`; strata `layers`; every landform's
  coverage masks.

Masks for material layering never use the carried gradient: under erosion it
is 28° off and 0.44× in magnitude (measured, as Ekigar's own test locks
it), which is fine for steering the next gully octave and wrong for picking
cliffs. For an intermediate node's masks, `generate(g, target=that_node)`.
`converge` and `curvPlan` are noisy on near-flat ground: plan curvature divides
by |∇h|³ with Ekigar's 1e-6 floor, so it is a channel-and-ridge selector on
slopes, not on plains.

## Hydrology — lakes, flow and the masks on them

The plan's tier-B masks (flow accumulation, lakes, wetness, deposition,
occlusion, vegetation) are not in Ekigar yet; its STATUS lists them as gaps.
They are built here to the plan's specification, from the finished height:

```python
H = hf.hydrology()                         # cached; hf.hydrology(sea_level=0.05) recomputes
hf.mask('channels'), hf.mask('lake'), hf.mask('wetness'), hf.mask('moisture')
hf.mask('deposition'), hf.mask('occlusion'), hf.mask('vegetation'), hf.mask('accumulation')
H['lakeDepth_m'], H['filled'], H['catchment_m2']           # raw arrays
lakes = ekigar.build_lake_mesh(hf, min_depth_m=0.5)        # (Blender) flat water at each spill level
```

- Depressions fill to their spill level exactly (the priority-flood result,
  computed on the graph of D8 basins). Outlets: an open edge (a non-periodic
  tile axis), the sea (`sea_level`, a field height), and on a tile periodic
  on both axes with no sea, the lowest basin. After filling, exactly one pit
  remains on a closed periodic tile.
- Flow routes strictly downhill on the filled surface and across lakes and
  flats toward the spill, so every texel's water reaches exactly one
  terminal: the accumulation at the terminals equals the texel count (the
  plan's conservation check), for D8, Tarboton's D-infinity and
  multiple-flow-direction routing.
- `accumulation` (log of upstream area) and `channels` (fully on at
  `channel_area` of the tile, default 0.4 %) route D-infinity: narrow, and
  free of D8's eight-direction bias (on a smooth cone D8 draws eight straight
  spokes; around a flank ring its catchments vary 0.60 std/mean against
  D-infinity's 0.05). Channels stay off dead-flat ground, where any route to
  the spill is a straight, arbitrary walk; there the area-based masks
  (accumulation, wetness, moisture, deposition) read the routed area
  averaged over the surrounding flat (`flat_radius`, 3 % of the tile, in log
  space), so a plateau or a plain reads as one smooth field instead of the
  walk's diagonal hatching. The raw arrays keep the routed values.
  `wetness` is the topographic wetness index ln(a / tan β) on MFD routing;
  `moisture` is wetness raised near water; `deposition` is large upstream
  area arriving on gentle, concave ground; `occlusion` is horizon ambient
  occlusion (16 azimuths, 6 % of the tile); `vegetation` is the reference
  demo's `GetTreesAmount` (tree line, occlusion, slope, off the creases of the
  ridge channel) times wetness. Lakes count as water in every mask.
- Fill, routing and accumulation at 1024² take 2–3 s (the plan's budget is
  3 s); the whole mask set about 8 s at 1024², 33 s at 2048².

Noise terrains have closed basins everywhere: on a closed periodic tile an
eroded mountain range holds lakes on 45 % of its area, the deepest 178 m.
That is what the ground does with rain and nowhere to drain; give it a
`sea_level` or open edges (`generate(..., tile=(0, 0))`) for a coast or a
valley that drains. Glacial troughs fill their rock basins (paternoster
lakes) and canyons hold floor pools, which reads right.

## `build_mesh`, `build_lake_mesh`, `preview_material`, `export_glb` (Blender)

```python
obj = ekigar.build_mesh(hf, name='Peaks')                    # one vertex per texel, true height
obj.data.materials.append(ekigar.preview_material('grey'))   # clay; 'shaded' = Ekigar's rock preview
far = ekigar.build_mesh(hf, name='PeaksFar', side=512)       # Ekigar's display grid, 512 a side
cut = ekigar.cut_for(hf, (1200.0, 600.0), radius_m=450.0, fade_m=100.0)
near = ekigar.build_mesh(hf, name='PeaksNear', crop=cut)    # that circle only, at full resolution
ekigar.export_glb(hf, 'out/peaks.glb', side='auto')          # binary glTF through Blender's exporter
W = hf.world_size                                            # tiled copies of a periodic tile, no slit:
tiles = [ekigar.build_mesh(hf, name=f'Tile{k}', wrap=True, location=(k * W, 0, 0)) for k in range(3)]
z = hf.height_at(1.7 * W, 25.0, wrap=True)                   # on whichever copy is there
```

The mesh has a `UVMap` in tile space and a FLOAT point attribute per mask
(`ekigar_slope`, `ekigar_wear`, `ekigar_floor`, and the hydrology masks once
computed) plus `ekigar_height` and `ekigar_hnorm`: a material reads them with
an Attribute node (type Geometry).

- `side=None` (default) puts one vertex on every texel. `side='auto'` is
  Ekigar's `terrainVertexSide` policy (1:1 between 256 and 2048 a side);
  `side=N` builds an N×N grid on its own texel centres with the heights read
  bilinearly, which at a whole ratio is an exact box average (a sinusoid read
  2:1 keeps cos(πf/R) of its amplitude, as Ekigar measured; a nearest read
  would alias it). `terrain_geometry_cost(N)` says what a grid costs before
  building it.
- The vertices sit on texel centres, so a mesh stops half a texel inside
  each tile edge, and copies laid at multiples of `world_size` would leave a
  one-texel slit between them. `wrap=True` adds the seam row and column of a
  periodic tile (one more vertex past the last texel centre, reading texel
  0), so a copy spans exactly `world_size` and the next copy's first
  vertices sit exactly on this one's last ones, at the same height (on a
  display grid too). `hf.height_at(x, y, wrap=True)` reads that surface, on
  any copy. Only periodic axes get the extra row; a film shot of one terrain
  does not need it.
- `crop=cut` builds a local circle's crop window at full resolution, wrapping
  across a periodic edge, with the local weight as `ekigar_local_weight`.
  The local-area tools are Ekigar's `local_area.js`: `resolve_cut` takes
  metres or fractions (metres win, conflicts are reported), `weight_field`,
  `seam_ring`, `area_downsample`, `crop_local`, `split_field`,
  `rasterise_local_masks`. Two Ekigar quirks are kept: its local-mask aux
  read clamps where its height read wraps, so a crop across a periodic seam
  takes the edge texel's ridge value there; and on a periodic tile
  `resolve_cut` measures "the farthest corner" with wrapped deltas, where all
  four corners are one point, so a small circle near that point is reported
  as covering the whole tile (centre (30, 380) m on a 400 m tile: radius 80 m,
  "farthest point 36.1 m", `surroundVanishes` true). Read that warning with
  this in mind.
- `build_lake_mesh` lays a flat water mesh at each lake's spill level over
  all its water (every lake at least `min_depth_m` deep somewhere, shallows
  included, so no plane edge hangs over the ground), grown one texel under
  the shore so the waterline is where the plane meets the ground.
- `preview_material` modes: `grey`, `shaded` (Ekigar's rock ramp by height,
  darkened on slopes, roughness 0.92), Ekigar's unlit diagnostics `height`,
  `slope`, `aspect`, `curvProfile`, `curvPlan` (blue concave, red convex) and
  `ridge`, and `'mask:<name>'` for any one mask, grey and unlit.

## Exports and the headless API

```python
ekigar.export_heightmap(hf.height, 'out/peaks', formats=('png16', 'r32'), world_size=2500)
ekigar.export_maps(hf.height, hf.aux, 'out/peaks', world_size=2500)   # height16, normal, slope, ridge + terrain.json
```

The heightmap sidecar carries what the files cannot (dimensions, row order,
the elevation range in metres); r32/r16/raw are headerless little-endian, and
a non-square field warns that they will be misread. One thing to know about
the map set: Ekigar's `ekigar_normal.png` is labelled OpenGL (+Y up) but its
green channel runs in DirectX order (a slope rising north writes green above
0.5, measured: 146 of 255). `export_maps` writes it Ekigar's way by default;
`green='opengl'` writes what the label says, which is what Blender's Normal
Map node and glTF expect.

`ekigar.api` is the plan's agent API over the same code: `list_operators`,
`get_schema`, `describe`, `default_project`, `validate` (unknown operators,
wrong wires, cycles, unwired required inputs), `tiling_report`, `evaluate`
(a Heightfield), `point_field` (the design tier's field: `evaluate(x, y)` and
`gradient_fd` at any points, no grid; a graph that takes screen-space
derivatives refuses and says to use `generate`), `stats_of` (height range,
slope histogram, non-finite count, water fraction), `to_project` /
`from_project`, `bake`.

`ekigar.make_field(default_config())` is Ekigar's CPU height field (the M0
base terrain: fBm under the reference demo's erosion tuning) with
`gradient_fd`; `ekigar.phacelle_noise` and `erosion_operator` are the erosion
core for anyone building their own field; `reference_trees` is the demo's
tree layer over it.

## Tiling

Every lattice snaps to whole cells per tile, so a terrain made of periodic
operators tiles: shifting the whole field by one tile changes nothing (to
1e-6) for 81 of the gallery's operators, and on every map tested (height,
slope, plan curvature of fBm, ridged, an eroded range, erosion, a canyon,
star dunes) the wrap seam is no worse than the worst interior texel pair. As
in Ekigar these do not tile: the gradient ramp; the eroded volcano and the
alpine mountain range (their built-in erosion runs at scale 0.12 and 0.1,
11.9 and 14.3 cells per tile, which nothing snaps); the rock glacier (its
lobes follow a direction mixed toward downhill, off the lattice). A tile only
matters for repeated ground; a film shot of one terrain does not need it.
Lay repeated copies with `build_mesh(hf, wrap=True)` (above): Ekigar's
tile-strip proof, three copies of an eroded range side by side, is
`render_heroes.py`'s `tile_strip_*` shots, with close looks straight down a
seam built with and without the seam row.

Ridged noise and cellular noise correlate with their own transpose at about
r = 0.12 at any tile size, and as much with the anti-diagonal mirror: that is
lattice regularity (gradient noise is zero on every lattice point, so ridged
noise peaks on a square grid in every octave), not a diagonal crease. fBm,
Perlin and Voronoi do not.

## For the surfacing step

The interface `make_terrain` builds on: `generate(...)` → `Heightfield`;
`build_mesh(hf, side=..., crop=..., wrap=...)` for the geometry (one object
per detail level); the masks as point attributes for the material;
`hf.height_at` / `hf.normal_at` / `hf.sample` for placement;
`hf.hydrology()` and `build_lake_mesh` for water; `hf.save` / `load` for the
cache. Everything is in metres, Blender axes.

## Tests and probes

Plain Python (numpy, deno for the parity runs), from the repository root:
`python blender/tests/terrain_ekigar/test_parity_operators.py`, and likewise
`test_parity_landforms.py`, `test_schema_parity.py`, `test_project_parity.py`,
`test_project_files.py`, `test_local_area_parity.py`, `test_display_grid.py`,
`test_bake_parity.py`, `test_heightmap_parity.py`, `test_ekigar_suite.py`
(`--quick` skips the 2048² timing; wall-clock times are reported as `PERF`
lines against the plan's budgets, and only a gross regression fails),
`test_generator_properties.py`, `test_landform_shape.py` (Ekigar's
`test/gpu/landform_shape.mjs`: the canyon's flat floor and real wall, the
mountain range's coverage, active-footprint detail) and
`test_operator_response.py` (Ekigar's `test/gpu/operator_response.mjs`:
every operator does something, every filter visibly changes its input,
every parameter moves the output, the carried gradient agrees in sign with
the height in every style arm, bedding transfers are monotone, every named
output is its own channel, seamless closes a real seam; about 3,200
evaluations at 64², under two minutes). In Blender (renders
nothing): `bash run_blender.sh
blender/tests/terrain_ekigar/test_blender_mesh.py`. Probes: generate the
caches on the CPU (`hero_scenes.py`, `gallery_scenes.py`,
`variant_scenes.py`, `render_probes.py --generate`), render them in one
slot booking with `render_all.py`, then `contact_sheets.py` and
`compare_ekigar_captures.py` (Ekigar's own captures, flipped, beside the
port's renders, each labelled with whether the capture is newer than the
Ekigar source of that operator); `mask_sheets.py` and `hydrology_sheets.py`
draw top-down mask sheets without a GPU.

Ekigar's two audits were written on 07-27, before its 07-29 and 07-30
edits, and some of their gates fail on Ekigar's current code. The ported
tests re-measure every failure on Ekigar's own field (its JS under deno, the
same graph at the same size) and print it as `EKIGAR` when the field and
the verdict are the same, so they do not count as port failures:

- the mountain range covers 73.4 % of the tile in relief, under the 80 %
  gate (the range was revised after the gate was set);
- `duneField.arms` does nothing, in any dune type: Ekigar declares it and
  never reads it (a dead slider);
- the star-dune controls (`armWidth`, `nodeBoost`, `basinLevel`,
  `crestPower`, `anisotropy`) do nothing at the default type `barchan`; with
  `type='star'` they all move the field (the audit predates them and has no
  star context for them);
- Phacelle's `offset` does nothing at the default `preserve` 1 (the preserve
  mix replaces it); at `preserve` 0 it raises and lowers the field;
- default Phacelle on the audit's 64² fixture changes it by 0.96 % rms of its
  range, under the 3 % visibility gate.

## Not yet ported

- Surfacing: Material Map's material stack and band blending
  (`materials/layer_stack.js`, `library.js`, `triplanar.js`,
  `mask_stack.js`, `texture_arrays.js`, `nodes/material_chain.js`), the
  material zip and remote libraries, and the export paths built on them
  (`layer_kernel.js`, `mixed.js` boundary measurement and `buildMixedExport`,
  `mixed_manifest.js`, `surround_bake*.js`, `ops.js` planeSampler): the
  surfacing step's.
- A local/surround mesh stitched along the seam ring (the geometry half of
  Ekigar's mixed export): the numbers are here (`seam_ring`,
  `area_downsample`, `crop`), the composed mesh belongs with the mixed
  export.
- An offscreen-GPU path for the erosion: numpy bakes 1024² in seconds and
  2048² in under a minute; 4096² (not measured here; four times the texels,
  so roughly two to three minutes) is where a fragment pass would start to
  pay.
- The browser application (`main.js`, `ui/*`, canvas, inspector, outliner)
  and live-uniform plumbing (`releaseNodeUniforms`, `liveParamUniform`): a
  Blender scene has no live slider loop; parameters are plain values.
- Ekigar's WebGPU-only test scripts (the registry and graph smoke renders,
  `mesh_filter`, `mesh_shading`, `mesh_limits`, `mesh_geometry`,
  `mesh_display`'s render half) test the browser's shader and display path,
  which Blender replaces; what they measure about the field is covered by the
  parity tests, `test_display_grid.py` and `test_blender_mesh.py`.
- Ekigar's own gaps that the plan leaves open: routed rivers that carve the
  terrain (the hydrology here reads the ground, it does not change it),
  overhangs (one height per (x, y)), presets and macros.
