# Terrain and surface materials

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition. Landforms, material layers and
texel density help shape the surfaces in a scene. Use the tools that fit the
intended terrain, manufacture and wear. Foliage has its own
[vegetation guide](vegetation.md).

Everything here is Python in `blender/eidoblend/terrain/`, in Blender axes
(Z up, metres). The engine's three.js axes map as three (x, y, z) →
Blender (x, −z, y), so a point the engine places at (x, z) on its ground is
(x, −z) here. Probes: `blender/tests/terrain/`.

## `make_terrain` — landforms by process

**`make_terrain`** makes ground that reads as its name next to the real
place: a stratovolcano beside Mount Fuji, a canyon beside the Grand Canyon at
Toroweap, star dunes beside the Namib. Every landform comes from what makes it
in nature, run on grids in metres and years: rivers cutting into rising rock,
hillslopes creeping and failing at their threshold angle, sediment settling in
valley floors, ice carving troughs, wind moving sand, waves cutting cliffs
back. A volcano's cone, a crater's bowl or a karst tower is only the starting
surface those processes work on. The grid passes are GLSL compute shaders run
through Blender's GPU module, so `make_terrain` runs inside Blender
(headless too).

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.terrain import make_terrain, recipes, describe

recipes()                    # {name: title} of every recipe
describe('alpine_valley')    # its stages, knobs (unit, default, range, what each does) and references

t = make_terrain('alpine_valley', seed=7,
                 params={'ela_m': 2000, 'trough_width_m': 1400},   # the recipe's knobs, in their units
                 focus=(480, 1640))      # hero levels down to 0.5 m around the camera's standing point
obj, height_at, masks = t    # or t.obj, t.height_at(x, y), t.mask('slope').at(x, y)
```

Each call prints one line: the recipe, its levels, cache hit or miss, the
seconds per phase and the triangle count.

### The recipes

| recipe | what it makes | main tile | judged against |
|---|---|---|---|
| `fluvial_range` | a mountain range carved by rivers: threshold hillslopes, branching valleys, alluvial floors | 12 km | San Gabriel Mountains |
| `alpine_valley` | a glacial U-valley: a flat floor between sheer walls, hanging side valleys, cirques, arêtes and horns, talus | 8 km | Lauterbrunnen; Yosemite Valley |
| `stratovolcano` | an exponential cone with a summit crater, radial gullies, rift cones, lava flows and an apron, among river-carved ranges | 40 km | Mount Fuji |
| `caldera` | a collapse caldera: an eroded edifice, scalloped cliff-banded walls over talus, a lake at its own level, an inner cone | 14 km | Crater Lake |
| `cinder_cones` | a cinder cone field: a young cone at repose with its flow among older, rounder, breached cones on a lava plateau | 8 km | SP Crater |
| `impact_crater` | a simple impact crater: a square-ish rim, cliff-banded walls over talus, a flat infilled floor, hummocky ejecta | 3 km | Meteor Crater |
| `canyon` | a canyon in layered plateau rock: stepped cliffs and benches, tributaries, an inner gorge | 8 km | Grand Canyon at Toroweap |
| `incised_meanders` | an entrenched meandering canyon: a river looping through flat-lying beds, stepped spurs, thin necks | 6 km | Goosenecks of the San Juan |
| `mesas_buttes` | caprock remnants, sheer walls over talus pedestals, a broad desert floor | 8 km | Monument Valley |
| `badlands` | dense rills and knife-edge ridges in soft banded rock between flat prairies | 3 km | Badlands Wall, South Dakota |
| `dunes` | dunes from the wind regime and the sand supply: `kind='star'` (default), `'barchan'`, `'transverse'` or `'linear'` | 8 km | Namib star dunes; Great Sand Dunes; White Sands; Namib linear dunes |
| `tower_karst` | fenglin towers on a river plain, or `kind='fengcong'`: cones over closed dolines | 8 km | Guilin |
| `sea_cliffs` | a cliffed coast: a wave-cut platform, beaches in bays, stacks; `rock='chalk'` or `'layered'` | 6 km | Seven Sisters; Cliffs of Moher |
| `rolling_hills` | soil-mantled rolling hills: convex tops, dense dendritic drainage | 4 km | the Palouse |
| `meadow` | small gentle ground: swales, low rises, rills and hummocks, for a meadow scene | 160 m | its look with grass |
| `real_place` | real elevation data as the main tile, refined below its pixel ([Real places](#real-places)) | the data's | the data itself |

A recipe is a list of stages (a process, its parameters in metres, years and
degrees, and the levels it runs on) plus a few named knobs: relief, valley
spacing, threshold angle, age, the wind regime, the rock column... Set knobs
with `params=`; `describe(name)` lists them with units, ranges and what each
does, and an unknown knob, recipe, keyword, quality, mask or flatten key
raises with the nearest valid names.

### Levels: from the horizon to the feet

A terrain is a stack of square levels with the same cell count, coarsest
first:
- context levels for the horizon, each twice the size of the next, centred
  on the tile (`context=4` gives a 32 km horizon around an 8 km tile); they
  also carry the rivers past the tile's edges;
- the main tile, `size` metres at `resolution` cells;
- with a `focus`, hero levels around it, each half its parent's side and
  twice as fine, down to `hero_cell`.

A finer level starts as its parent upsampled, keeps a 16-cell border pinned
to its parent, and is refined by the same processes at its own scale. Rivers
entering a hero window bring their catchment with them, and the gullies,
rills, talus and broken rock a 1.7 m eye sees grow where it sees them. An
8 km alpine valley at film quality with a focus is seven levels of 1024²:
32 km at 31 m, 16 km at 15.6 m, the main 8 km at 7.8 m, then 4 km, 2 km,
1 km and 500 m at 0.49 m.

| `quality` | main tile | hero levels down to |
|---|---|---|
| `'draft'` | 512 cells | none (fewer steps) |
| `'film'` (default) | 1024 cells | 0.5 m |
| `'hero'` | 2048 cells | 0.25 m |

- `focus` is (x, y), a list of points, a camera object (its location) or a
  list of camera positions. Give it where the camera stands for an eye-level
  shot, or the points a camera move passes. A focus outside the main tile
  raises. A hero window holds at most 2048 cells (1 km at 0.5 m): a wider
  focus stops the cell shrinking there, with a warning.
- The mesh is the same stack drawn as concentric rings, so vertex density
  falls off with distance from the focus: each level at every second cell
  corner, and around the focus the finest level down to every corner (about
  3.3M triangles for seven levels; `mesh_res` sets the vertices per side a
  level is drawn at). The rings are stitched at their seams (no gaps, no
  T-junctions), and the outermost ring hangs a 50 m skirt so a low camera
  never sees under the world.

### The call

```python
t = make_terrain(
    recipe='alpine_valley',  # a name from recipes(), a Recipe, a recipe dict, or a list of stages
    size=None,               # metres, the main tile's side (default: the recipe's; real_place: the data's)
    resolution=None,         # cells across the main tile (default: the quality's 512 / 1024 / 2048)
    seed=7,                  # every stage's random seed
    params=None,             # the recipe's knobs, in their units: {'relief_m': 2800, 'ela_m': 2300}
    focus=None,              # (x, y), [(x, y), ...], a camera, or camera positions: the hero levels
    hero_cell=None,          # metres, the finest cell around the focus (default 0.5; quality 'hero' 0.25)
    context=None,            # the horizon's extent multiplier (default the recipe's)
    flatten=None,            # [{'at': (x, y), 'radius': 15, 'falloff': 10, 'height': None}, ...]
    sea_level=None,          # metres (Blender z), or None
    base_elevation_m=None,   # the altitude of z = 0 (snowline, treeline, the glaciers' equilibrium line)
    palette='auto',          # 'auto', a palette name, a palette dict, or None (grey clay)
    dress=True,              # rocks on the talus and rock-toe masks near the focus
    quality='film',          # 'draft' | 'film' | 'hero'
    cache=True,              # read and write eidoverse/assets/cache/terrain/<key>
    name='terrain', collection=None, mesh_res=None)
```

### The `Terrain` it returns

| member | what it is |
|---|---|
| `t.obj` | the ring mesh: one object at the origin, the masks as point attributes, the material applied, `obj['trimesh_collider'] = True` so the placement helpers treat it as the ground, and `obj['eido_terrain']` holding the recipe, knobs, seed, level plan and cache key |
| `t.height_at(x, y)` | metres at Blender (x, y), exactly on the rendered triangles of the finest ring holding the point (floats or numpy arrays) |
| `t.normal_at(x, y)` | the shading normal there (`smooth=False`: the triangle's) |
| `t.masks`, `t.mask(name)` | a `MaskSet`: `t.mask('slope').at(x, y)` samples the finest level holding each point, `.array('main')` is one level's array (row 0 the south edge), `t.masks.names()` lists them |
| `t.levels` | each level's window (`x0`, `y0`, `side`, `cell`, `n`) and `role` (`'context'`, `'main'`, `'hero'`) |
| `t.fields(level)` | a level's raw arrays (`h`, `bed`, `water`, `deposit` ...), by index or role |
| `t.flats` | the flattened areas and the heights they resolved to |
| `t.water` | `{'lakes': [objects], 'sea': object or None}` |
| `t.rocks` | the scattered rocks (collection, count, sizes), or None |
| `t.viewpoint(target, distance, ...)` | a standing point about `distance` m from `target` from which a 1.7 m eye sees the target over the ground, on footing under 30° (`prefer='low'`: a valley floor, `'high'`: a rim; `heading=` compass degrees); `place_camera(vp, cam)` from `eidoblend.terrain.api` aims a camera from it |
| `t.metrics(pixel_m=None)` | the main tile's relief, slope percentiles, closed depressions, power spectrum and grid-direction numbers |
| `t.preview(path)` | a north-up hillshade with the hero windows outlined, the finest level's hillshade and mask PNGs: a look before a render |
| `t.save(path)`, `Terrain.load(path)` | write and read every level's fields and masks |
| `terrain_height_at(obj)` | `height_at` again after a `.blend` is reopened, from the object alone |

**Placing things.** `place_on`, `snap_to_ground` and `scatter_on`
([placement.md](placement.md)) ray-cast the terrain's mesh, and
`t.height_at` lands on the same triangles (within 0.1 mm across rings and
seams), so a character stood at `t.height_at(x, y)` stands on the ground.
For an eye-level camera, ask `t.viewpoint` for the spot: it keeps the camera
from facing a wall or a rise at its feet.

```python
from eidoblend.terrain.api import place_camera
vp = t.viewpoint(target=(0, -3000), distance=1500, prefer='low')
place_camera(vp, cam)        # 1.7 m over the ground, level horizon, looking at the target
```

### Masks

The masks come from the processes (drainage area, eroded depth, deposit,
talus, sand, snow, exposed rock) and from the final surface (slope, aspect,
curvature at a scale in metres). They are FLOAT point attributes named
`eido_<mask>` on the mesh, which an Attribute node reads, and they are in
metres and degrees on every level, so a mask means the same in a hero ring
and on the horizon.

| mask | what it is |
|---|---|
| `height`, `height_norm` | metres above base; 0-1 over the main tile |
| `slope`, `aspect`, `northness`, `eastness` | degrees; the compass bearing the slope faces; its cosine and sine (a material reads these: interpolated aspect tears at north) |
| `curv_profile`, `curv_plan`, `convex`, `concave` | curvature at twice the cell; `convex_20m`, `curv_plan_100m` ... at a scale in metres |
| `peaks` | high and convex: summits and ridgelines |
| `flow`, `channels`, `wetness` | log drainage area; channels (1 km² on the main tile, down to 1,000 m² rills on the hero levels); topographic wetness |
| `wear`, `deposit`, `talus`, `sand`, `lava` | eroded depth, sediment, talus and sand thickness (metres), the lava flows' footprint |
| `water` | lake or sea depth |
| `rock`, `rock_toe` | exposed rock; the ground below it where fallen rock gathers |
| `snow` | above the snowline, held lower on north faces and in hollows |
| `strata` | stratigraphic height: where the rock column's bands sit |
| `occlusion` | sky-view factor |
| `vegetation` | suitability for plants from moisture, slope, altitude band, light and bare ground: a density for the flora |

Plants follow the masks through the flora's own options:

```python
from eidoblend.flora import create_flora
veg = t.mask('vegetation')
create_flora('grass', size=60, center=(x, y), height_fn=t.height_at,
             clip_fn=lambda x, y: veg.at(x, y) < 0.35)    # no grass on rock, scree, sand or water
```

### Palettes, rocks and water

`palette='auto'` takes the recipe's palette (the place's, for `real_place`);
a name picks one of `alpine`, `desert_sandstone`, `volcanic`, `dunes`,
`badlands`, `karst`, `chalk_coast`, `farmland` and `meadow`; `None` gives
grey clay (albedo 0.18) for shape comparisons. A palette is up to six CC0
scan layers in one node group, each weighted by a mask expression such as
`'max(smoothstep(0.35, 0.6, rock), smoothstep(24, 31, slope))'`, projected
from above on gentle ground and box-projected (triplanar) on steep faces, and
height-blended in order so the layers interlock at their own detail. The
layered-rock recipes add their rock column's colour bands at the
stratigraphic height, so the bands sit on the benches the erosion cut.

- Each map is read twice at unrelated scales and offsets, switched by world
  noise in patches about a tile across (`detile_patch`), so a tile seldom
  repeats.
- Texture reads hold still in motion. EEVEE's `'Linear'` is mipmapped but
  not anisotropic, so ground at grazing angles blurs; `'Cubic'` reads the
  full-resolution image but has no mipmaps, so past a few metres the ground
  crawls when the camera moves. `interpolation='Auto'` (the default) reads
  Cubic within `detail_distance` (4, 9) metres of the camera and Linear past
  it.
- `dress=True` scatters CC0 rock models within 150 m of the focus on the
  talus, rock-toe and channel masks: sizes from a power law, half-buried and
  turned to the ground, as collection instances.
- Lakes are flat surfaces at their spill levels (`t.water['lakes']`);
  `sea_level` adds a sea plane. Both carry a dark, glossy water material
  tinted by depth.

### Real places

`real_place` loads real elevation data as the main tile and refines it below
its pixel: on the hero levels the detail stages (rills, talus, rock breakup,
the shallow-water pass) add what a 1.7 m eye sees without moving the
landform.

```python
t = make_terrain('real_place', params={'dem': 'lauterbrunnen'}, focus=(480, 1640), seed=1)
t = make_terrain('real_place', params={'dem': 'C:/dems/my_place.json'})   # your own, in the same format
```

`dem` names one of the reference sites in
`blender/tests/terrain/reference/data/` (`lauterbrunnen`,
`yosemite_valley`, `grand_canyon_toroweap`, `goosenecks`,
`monument_valley`, `badlands_sd`, `badlands_sd_detail`, `mount_fuji`,
`crater_lake`, `sp_crater`, `meteor_crater`, `great_sand_dunes`,
`white_sands`, `namib_star_dunes`, `namib_linear_dunes`, `guilin_karst`,
`seven_sisters`, `cliffs_of_moher`, `palouse_hills`,
`san_gabriel_mountains`), or the path of a JSON (or PNG) of the same kind:
a north-up square 16-bit PNG with a JSON giving its pixel size, height range,
source and licence. The size and resolution default to the data's, and its
wider surround, where the site has one, becomes the context levels. Data from
GSI (Fuji), Copernicus (Guilin, the Namib, Moher) and swisstopo
(Lauterbrunnen) needs its attribution line in the film's credits:
`t.info['attribution']`. USGS 3DEP data is public domain.

### Flat ground

`flatten=[{'at': (40, -12), 'radius': 15, 'falloff': 10, 'height': None}]`
makes level ground after the erosion: exactly `height` inside the radius
(None: the area's median), blended back to the terrain over `falloff`
metres. `'size': (w, l)` with `'angle_deg'` makes a rectangle instead.
`t.flats` holds the heights they resolved to, for placing a set or a path on
them.

### Recipes are data

`recipes.get('canyon').to_dict()` is JSON: print it, change a stage, and
pass the dict back as `recipe=` (or pass a list of stages). A stage is
`{'op': 'fluvial', 'params': {...}, 'levels': 'all', 'where': None}`:
- `levels`: `'all'`, `'first'` (the coarsest), `'context'`, `'main'`,
  `'hero'`, `'cell>=30'` or `'cell<=2'` (by cell size in metres), a list of
  these, or `'resolves:<metres>'` (the first level whose cell is at most an
  eighth of that size: where a constructional shape is stamped);
- `where`: a mask expression that limits the stage to a region, built from
  numbers, masks and fields with `+ - * /`, `min`, `max`, `clamp`, `abs` and
  `smoothstep(a, b, x)`, such as `'1 - trough'` or
  `'smoothstep(20, 35, slope)'`.

### From the command line

```
bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe dunes --size 6000 --seed 3 --out <dir>
bash run_blender.sh blender/eidoblend/terrain/bake.py --recipe real_place --param dem=lauterbrunnen --focus 480,1640 --out <dir>
bash run_blender.sh blender/eidoblend/terrain/bake.py --describe canyon
```

`bake.py` fills the cache and writes the preview PNGs and
`<name>_bake.json` (the level plan, the timings, the cache key, the main
tile's numbers), so a recipe can be tried without building a scene.

### Cache and cost

The cache key hashes the recipe, knobs, size, resolution, seed, level plan,
focus and the bytes of the code that makes the fields, so an edited kernel or
stage never serves an old entry. Entries live in
`eidoverse/assets/cache/terrain/<key>/` (a few hundred MB for a film terrain
with hero levels); past `EIDO_TERRAIN_CACHE_GB` (default 8) the oldest go.
A cache hit loads the fields and builds the mesh in seconds. The first call
in a Blender process also compiles its kernels.

### Heightmaps for other tools

```python
from eidoblend.terrain.core import io
lv = t.main
io.export_heightmap(t.fields('main')['h'], '<dir>', lv.cell, x0=lv.x0, y0=lv.y0)   # height.png (16-bit) + height.r32
h, meta = io.read_heightmap('<dir>/height.json')     # metres, row 0 the south edge
io.export_mask(t.mask('slope').array('main'), '<dir>', 'slope', lo=0, hi=90)        # a mask as a PNG
```

The files are north-up (row 0 the north edge), as other tools expect; the
JSON sidecar carries the size, cell, world origin, row order and the height
range the 16-bit PNG is normalised over (the `.r32` is raw float32 metres).

### Judging a terrain against its place

`python blender/tests/terrain/judge/run.py --recipe canyon --textured`
generates a recipe at its real place's extent and writes its numbers (slope
percentiles, relief, closed depressions, the power spectrum, the landform's
own: benches, crater ratios, dune spacing...), the bands they must fall in,
and a sheet with the place's views beside the recipe's: top-down hillshade,
45° aerial and 1.7 m eye in grey clay, then the hero levels' eye view and the
textured aerial and eye. Use it when you change a recipe's stages.

## `layer_surface` — making built geometry look built

`layer_surface` combines density normalisation and layered surface masks
for geometry you built (lathes, extrusions, booleans). Use it when the piece
benefits from form-following wear, dust or material variation. Loaded
assets already carry authored maps and UVs; preserve those.

```python
from eidoblend.terrain import layer_surface

layer_surface(my_meshes, metres_per_tile=1.15,          # one texture tile per 1.15 m, on everything
    grunge={'scale': 0.55, 'seed': 7},
    layers=[
        {'mask': 'cavity', 'scale': 0.75, 'color': 0x2b2419, 'roughness': 1.0, 'amount': 0.9,
         'range': (0.15, 0.72), 'grunge': 0.35},
        {'mask': 'edges', 'scale': 0.08, 'color': 0xc9bda0, 'roughness': 0.62, 'amount': 0.6,
         'range': (0.2, 0.72)},
        {'mask': 'up', 'color': 0x8a7859, 'amount': 0.38, 'power': 3, 'grunge': 0.8},
        {'mask': 'below', 'z': 0.14, 'fade': 0.16, 'color': 0x3a2c1e, 'amount': 0.8},
    ])
```

**Masks** (each remapped through `range: (a, b)`, scaled by `amount`,
optionally broken up by `grunge: 0..1`):

| mask | driven by | use it for |
|---|---|---|
| `cavity` | concave curvature × `scale` m | grime, moss, soot — the workhorse |
| `crease` | the same, `scale` 0.05 m | sharp dirt lines in inside corners |
| `edges` | convex curvature × `scale` m | polish, chipping, bleached exposure on bevels |
| `up` | geometry normal z ^ `power` | dust, silt, ash, snow |
| `slope` | 1 − \|geometry normal z\| | runoff streaking on vertical faces |
| `below` / `above` | world Z, `z` + `fade` | waterlines, tide marks, buried bases |
| `grunge` | the seamless fbm alone | breakup on its own |

`color` is `0xRRGGBB` (sRGB, as the engine's) or a linear `(r, g, b)`. Each
layer mixes colour, and roughness / metalness when given, over what is
under it; later layers sit on top. `below` / `above` read world height for
everything they cover: a waterline drawn on a basin also stains its outside
foot below that height, so give such a layer its own call on the pieces it
belongs to.

**These tools are for geometry you built, and they refuse fetched assets.**
Rescaling an authored unwrap makes every island sample outside its region
and the model comes out as confetti. Refused (and named in the log): objects
or meshes stamped `eido_loaded_asset` (every GLB/VRM import should stamp
it), children of one, armature-deformed meshes, meshes with shape keys,
MToon materials. `force=True` overrides, loudly.

- **`normalize_texel_density(objects, metres_per_tile)`** measures each
  mesh's real UV-per-metre (median over its triangles, in world space, so a
  scaled copy is measured at its apparent size) and scales the existing UVs
  to a common target, keeping every island's layout. A mesh shared at
  another density gets a single-user copy. It warns about a Mapping node
  scale that is not 1 (it multiplies on top) and images that do not repeat.
- **Curvature is measured on the mesh** (`add_curvature(obj)`, which
  `layer_surface` calls when a curvature mask is asked for): the engine's
  `dot(dN, dP) / |dP|²` taken along each triangle's edges instead of screen
  axes, with the corner normals, averaged per face and then per corner over
  the faces that share its vertex and normal, in 1/metres (+ convex, −
  concave; a sphere of radius R reads 2/R). Shader nodes have no
  derivatives, so this is the route; it is stored as the corner attribute
  `eido_curvature`. As in the engine, a bevelled or filleted edge gives the
  band its curvature and a flat-shaded or sharp-edged (split-normal) corner
  gives none: model the fillet (a Bevel modifier with Harden Normals,
  applied). It reads the mesh as built: apply generating modifiers first,
  and run `add_curvature` again after reshaping.
- `up` / `slope` and the grunge's projection read the geometry normal, the
  engine's `normalWorldGeometry`: smooth across smooth faces, split at sharp
  edges, never the shading normal (a normal map or bump would light every
  mortar line). `add_geometry_normal(obj)` (which `layer_surface` runs on
  every mesh) stores the corner normals as the attribute
  `eido_geometry_normal`, and the material turns them to world space each
  frame: moving or rotating the object needs nothing, reshaping it needs
  another run. On a mesh without the attribute (`make_layered_material`
  assigned by hand) the masks read Geometry › Normal, which a material
  displacement's bump bends. `below` / `above` read world Z.
- The grunge is the engine's own seamless fbm image (`grunge_texture(size,
  seed)`: the same LCG, the same 16-cell lattice, the same rows) on the
  engine's world-space triplanar projection: three reads at world (x, −y),
  (−y, z) and (x, z) (three's xz, zy and xy planes), weighted by the
  geometry normal's absolute components over their sum. So the noise holds
  world scale on every face of a rotated or boolean'd solid, and pieces that
  touch share it. (Blender's Box projection blends by the OBJECT's normal and
  streaks on anything rotated.) At the example's scale it breaks masks into
  soft clouds; a larger `scale` gives finer, grittier breakup.
- `layer_surface` keeps each source material whole (its normal map, its
  textures) and inserts the layers between what fed the Principled BSDF's
  Base Color, Roughness and Metallic and the BSDF: one layered copy per
  source material. `make_layered_material(base, layers, grunge)` builds one
  from a base dict (`color`, `map`, `roughness`, `roughness_map` (its G
  channel, like the engine), `normal_map`, `metalness`, `metalness_map`).

## `loft` — skin a surface through cross sections

Loft lives with this family (`eidoblend.terrain.loft`); its guide section
is in [geometry.md](geometry.md).

## `ProceduralMaterials` — generated PBR surfaces

Ported whole as `eidoblend.materials.procedural` — guide:
[procedural-materials.md](procedural-materials.md). The canvas generators
become packed images (the maths ones byte-identical to the engine's);
`height_to_normal`, `composite` and the six factories become Principled
materials. Generated wear layers over a fetched scan too:
`PM.composite(tex['roughness'], PM.smudges(1024, 1024, amount=0.6), 'add', strength=0.25)`.

## Relief — real depth from a height map

The engine's silhouette parallax (SPOM) ray-marched a height field to fake
depth and an outline in a real-time raster. EEVEE 5.2 displaces real
vertices at render time, so in the render the relief IS geometry: it casts
and receives real shadows and carves a true silhouette. It exists only in
the render: the evaluated mesh, and with it every Python ray, placement
helper and contact check, still sees the flat polygons, so measure a relief
in a render. The names and options stay the engine's where they still mean
something (`eidoblend.terrain.relief`):

```python
from eidoblend.terrain import relief, find_set
tex = find_set('Bricks097')
mat = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], tex['roughness'],
                                      uv_scale=(3.0, 2.4),      # tiles across the mesh's UVs
                                      tile_metres=1.0,          # one tile's world size
                                      depth_metres=0.03,        # or depth_scale (tile units) x tile_metres
                                      method='BOTH')            # vertex displacement + finer detail as bump
wall.data.materials.append(mat)
relief.subdivide(wall, edge=0.008)      # vertices for the displacement to move (Simple subdivision)
relief.check_relief_geometry(wall)      # UVs present, edges short enough for the relief's features

col = relief.create_relief_column(tex['displacement'], tex['color'], tex['normal'],
                                  radius=0.42, height=2.6, around_tiles=3, depth_scale=0.05)
```

- The albedo and normal maps are read like the terrain's (`interpolation=
  'Auto'`, `detail_distance=(4, 9)`): full resolution near the camera,
  mipmapped past it. The height map is always read Cubic, because it moves
  vertices and the geometry must not change with the camera. Straight on at
  7 m the probe's walls crawl little either way (`test_relief.py --shimmer`:
  0.18 with 'Auto', 0.20 all Cubic; a brick still spans about 9 pixels
  there). The mipmapped reads earn their keep at grazing angles and further
  out, as on the terrain.
- The depth is world metres (`space='WORLD'`, the default): an unapplied
  scale on the object leaves `depth_metres` alone (the probe's wall scaled
  2× along its normal renders like the applied one). `space='OBJECT'` scales
  the depth with the object; `create_relief_column` uses it, so scaling the
  column's root scales its relief and its caps together.
- The relief carves inward with `silhouette=True` (the default) and
  `silhouette=False` alike: the peaks stay at the polygon, like the engine's
  flat SPOM and its interior POM (`silhouette: false`, e.g. a floor), so
  what stands on the polygon stands on the peaks; `True` also lets
  `silhouette_bounds` cut the outline. `color` takes the engine's
  `0xRRGGBB` / `'#rrggbb'` (sRGB) or a linear `(r, g, b)` and multiplies
  the albedo map. `create_relief_column` inflates outward instead, so its
  relief overhangs the round outline (the engine's inflate shell + core +
  caps is now one displaced cylinder with flat caps at radius + 0.95 ×
  relief depth).
- The field notes' contrast stretch is built in (`contrast=(0.15, 1)`): the
  map's own 0.5–99.5 % range is mapped to (floor, 1), so a low-contrast
  mid-grey Poly Haven `_disp` carves visibly and no well goes full depth.
- Vertices are the cost: the 3 × 2.4 m probe wall (one quad) at 8 mm edges
  is nine Simple subdivision levels (512 × 512 = 262 k faces) and renders in
  seconds.
  `method='BUMP'` keeps the look without the vertices (no silhouette, no
  shadows from the relief).
- The march's own knobs (`minLayers`, `maxLayers`, `minViewZ`,
  `curvedSilhouette`, `curvature`, the horizon trim, the marched
  self-shadow and `reliefShadow`, `heightNormal`) are accepted, camelCase
  too, and have nothing to do here: EEVEE shadows and shades the real
  surface. A misspelt option raises.

### The relief's bounds

The engine's three bounds are `create_parallax_material` options, in the
engine's scaled-UV space (UV x `uv_scale`), each `[lo, hi]` or
`[[u_lo, u_hi], [v_lo, v_hi]]`.

```python
mat = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], uv_scale=(3.0, 2.4),
                                      depth_metres=0.03,
                                      silhouette_bounds=[[0.4, 2.6], [0.3, 2.1]])  # cut to a UV rectangle: the cut edge shows the bricks' depth
mat = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=(3.0, 2.4), depth_metres=0.03,
                                      sample_bounds=[[0, 1.5], [0, 2.4]],
                                      silhouette_bounds=[[0, 1.5], [0, 2.4]])     # end a tiling relief cleanly at u = 1.5
boxes = relief.world_uv_boxes([((6, 6, 1), (3, 1.2, 2)), ((4.9, 7.8, 1), (0.8, 2.4, 2))], tile_metres=1.0)
boxes.data.materials.append(relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=1.0,
                                                            depth_metres=0.03, face_bounds=True))
relief.face_bounds(boxes); relief.subdivide(boxes, edge=0.01)
```

- `silhouette_bounds` cuts the surface where its UV leaves the bounds, with
  the library's coverage (feathered over 0.02 UV, clipped at 0.5): alpha
  exactly 0 or 1, dithered, and the shadows follow the cut. The engine's
  default ([0, 1]) clipped march rays leaving a one-tile plate; a displaced
  surface sends none out, so the default here cuts nothing.
- `sample_bounds` clamps every map read into the region: past it the border
  texels continue as streaks; pair it with `silhouette_bounds` on the same
  region to end the relief cleanly.
- `face_bounds`: each face displaces along its own normal (the Edge Split),
  so where a mortar well meets a box's edge the faces part and the corner
  notches; back faces are culled, so the notch shows what is behind, as the
  engine's per-face discard did. As in the engine, it replaces
  `silhouette_bounds`' cut. The `uv_min` / `uv_max` FACE attributes are the
  engine's `uvMin` / `uvMax`, for a custom node tree (a displaced point's UV
  never leaves its own face, so the material does not read them).
- `debug_silhouette=True` paints the cut region magenta; `debug_march=True`
  shows fract(UV) unlit (`debug_march_lit` lit).
  `parallax_occlusion_uv(tree, height_map, ...)` is the library call for a
  custom node tree (`.uv`, `.coverage`, `.missed`, `.sample(image)`,
  `.shadow()`).

Probe: `blender/tests/terrain_extras/test_relief_bounds.py`
(`relief_bounds_sheet.png`; it reads the cut, the notches and the floor
relief's peak height from film-transparent renders).

Probe: `test_relief.py` (a carved brick wall beside the same material as
bump only, a relief column, under raking light, and the wall with an
unapplied scale in world and object space).

## Not yet ported

- A live (Geometry Nodes) curvature attribute for meshes that deform after
  `layer_surface`.
- The engine's warning about a texture's `repeat` became the Mapping-node
  warning; Blender images have no repeat of their own.

## Not yet built

- `make_terrain`: river water ribbons along the channels (they hand off to
  the water family), graded paths and roads cut after the erosion, and the
  later recipes: shield volcano, lava field, playa with bajada fans,
  inselberg plain, braided outwash plain, river valley with floodplain and
  oxbows, complex crater, volcanic island, fjord.
