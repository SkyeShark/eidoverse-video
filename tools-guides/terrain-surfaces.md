# Terrain and surface materials

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition. Heightfields, material layers and
texel density help shape the surfaces in a scene. Use the tools that fit the
intended terrain, manufacture and wear. Foliage has its own
[vegetation guide](vegetation.md).

Everything here is Python in `blender/eidoblend/terrain/`, in Blender axes
(Z up, metres). The engine's three.js axes map as three (x, y, z) →
Blender (x, −z, y), so the engine's `heightAt(x, z)` is `height_at(x, −z)`
here. Probes: `blender/tests/terrain/`.

## `make_terrain` — procedural heightfield ground

The engine's heightfield, to the bit: the same mulberry32 lattice, fbm,
clearing blend, plane grid and triangle split. `test_parity.py` runs the
engine's own `terrain.js` under Node and compares every vertex height
(bit-identical) and `heightAt` (within 1e-15 m). Three texture layers are
blended by height, slope and noise, baked into the colour attribute
`eido_blend` (R base, G mid, B steep) exactly as the engine bakes them.

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.terrain import make_terrain

terrain, height_at = make_terrain(size=80, segments=256, amplitude=3, seed=7, flat_radius=8,
    high_start=-0.2,            # the mid layer on the meadow floor, not only on hilltops
    slope_steep=(0.02, 0.05),   # the steep layer on banks of 11-18 degrees
    layers=[{'set': 'Ground106', 'tile_metres': 2.3, 'roughness': 1.35},              # base: low ground, the clearing
            {'set': 'withered_grass', 'tile_metres': 2.0, 'tint': (0.6, 0.58, 0.52)},  # mid: high ground
            {'set': 'coast_sand_01', 'tile_metres': 2.6}])                            # steep: banks
z = height_at(x, y)        # exact ground height anywhere (floats or numpy arrays)
```

This example's mean layer weights are base 0.75, mid 0.24, steep 0.02.
With the engine's defaults (`high_start` 0.45 × amplitude, `slope_steep`
(0.25, 0.55)) the same terrain is base 0.987, mid 0.013, steep 0: one
layer, in effect. Gentle hills have few steep faces; raise `amplitude` or
lower `slope_steep` for more banks.

The options are the engine's, snake_cased: `size`, `segments`, `amplitude`,
`seed`, `layers` (up to three: base, mid, steep), `flat_radius` /
`flat_height` (a level clearing at the origin, blended over 0.6 ×
`flat_radius`), `slope_steep` (the (1 − normal.z) range where the steep
layer fades in), `high_start` (height where the mid layer starts; default
0.45 × `amplitude`), `octaves`, `frequency`. The object carries
`obj['eido_terrain']` (its options: `terrain_height_at(obj)` rebuilds
`height_at` after reopening a .blend) and `obj['trimesh_collider'] = True`.

A layer is a texture-set name from the shared library (`'Ground106'` takes
the best resolution, `'Ground106_2k'` a given one) or a dict: `set`, or the
maps directly (`map`, `normal_map`, `roughness_map`, `ao_map`,
`displacement_map`: paths or Blender images); `repeat` (tiles across the
whole terrain, the engine's key) or `tile_metres` (one tile spans this many
metres: match the scan's real size, about 2 m for most ground scans);
`roughness` (a multiplier on the roughness map), `tint`, `normal_strength`.
Sets are found in this checkout's `eidoverse/assets/cache/textures/`, then
`$EIDO_TEXTURE_CACHE`, `$EIDO_ASSET_CACHE/textures`, then the main
checkout's cache when this checkout is a git worktree.

**Two shadings.** `shading='film'` (the default) gives every layer its full
scanned set and shades it for film:
- each layer's albedo, normal, roughness and AO, not only the albedo;
- a height blend from the scans' own displacement maps, normalised per scan
  (Ground106 averages 0.65 and withered_grass 0.36: unnormalised, one scan
  would always win), so the layers interlock at their own detail;
- ragged layer edges: a ~1 m noise on the upper layers' blend, so a patch
  boundary is broken ground rather than a painted outline;
- de-tiling: each map is sampled twice at unrelated scales and offsets, and
  a narrow world-space switch shows one or the other (a 50/50 mix of two
  samples halves the contrast and the ground goes flat and sandy). The
  switch's patches are about a tile across (`detile_patch`, in tiles), so a
  tile seldom repeats inside one patch. Seen straight down on the probe's
  clearing, 1.7 m windows that match themselves one tile over: 86 % with
  de-tiling off, 11 % with 3.35-tile patches, 8 % with 1.2. From crane
  height the ground still reads as an even speckle: that is the scan's own
  clumps everywhere, which `macro` variation, not de-tiling, breaks up;
- world-scale colour drift (`macro`) and damp patches (`damp`: darker, a
  little less rough);
- texture reads that hold still in motion (`interpolation='Auto'`). EEVEE's
  `'Linear'` is mipmapped but not anisotropic, so ground at grazing angles
  blurs into smears: the anisotropic-filter preference does not reach EEVEE
  renders, even when it is set before the GPU starts. `'Cubic'` reads the
  full-resolution image and keeps about twice the detail, but it has no
  mipmaps. Past a few metres each pixel covers dozens of texels, the samples
  cannot average them, and the ground crawls when the camera moves. `'Auto'`
  reads Cubic near the camera and Linear past it, handing over across
  `detail_distance` (4, 9) metres. Measured with `test_meadow.py
  --shimmer` and `shimmer_metric.py` (the 'edge' view turned by half a
  pixel, 960 × 540, 16 samples; aliasing as a fraction of the real motion,
  where 1 means the crawl is as large as the motion):

  | | distant (28 m+) | middle (9–28 m) | near (3.5–6 m) |
  |---|---|---|---|
  | Cubic everywhere | 1.00 | 0.85 | 0.26 |
  | Linear everywhere | 0.14 | 0.11 | 0.08 |
  | **Auto (4, 9)** | **0.14** | **0.11** | 0.22 |

  The footprint of a pixel shrinks with resolution and focal length, so a
  1920-wide frame or a long lens can push `detail_distance` out, and more
  samples help Cubic. Check it with the shimmer probe before trusting a
  wider handover.

Tune it with `material_options={...}`: `anti_tile` (True), `detile_patch`
(1.2), `height_blend` (0.5), `blend_depth` (0.2), `edge_noise` (0.3), `ao`
(0.5), `macro` (0.14), `damp` (0.5), `specular` (0.5), `bump` (metres; 0 =
off), `interpolation` (`'Auto'`, `'Cubic'` or `'Linear'`),
`detail_distance` ((4, 9) metres).
`shading='parity'` is the engine's material exactly (albedo blended by the
weights at uv × repeat, layer 0's normal map only, roughness 0.95, colour
0x6b6f5e with no layers), for a like-for-like comparison.

Field notes from the probes (`test_meadow.py`):
- Scale the textures to the scan, not the terrain: `tile_metres` ≈ 2.3 for
  Ground106 puts its leaves at leaf size. The engine's default `repeat` 12
  on an 80 m terrain is 6.7 m per tile, three times too big.
- Ground106's roughness map averages 0.64; looking toward the sun, soil that
  glossy sheens like wet sand. `roughness: 1.35` brings it to dry earth.
- withered_grass scans at luminance 0.32 against the soil's 0.14 and reads
  as salt flats from eye height; a tint around 0.6 makes it litter.
- With the engine's default `high_start` (0.45 × amplitude) the mid layer
  only reaches hilltops (1–2 % of an amplitude-2.5 meadow). Lower it (0 to
  −0.2) for a meadow floor with patches; `slope_steep` around (0.05, 0.1)
  lets gentle banks show the steep layer.
- A probe camera at eye height sees the terrain's edge unless hills close
  the horizon: the test meadow is 160 m at `frequency` 5, the same hill
  scale as 80 m at 2.5.
- Backlit from eye height, bare soil reads as dry packed earth; its leaves
  and clods read from about 1–3 m. Under grass it is the dark ground between
  the blades the probe needs (`--grass` adds test-only tufts; grass itself is
  the vegetation family's).

Placement on terrain: `place_on`, `snap_to_ground` and `scatter_on`
([placement.md](placement.md)) ray-cast the terrain's evaluated mesh, and
land on it to a few micrometres. `height_at` is the analytic height; between
vertices the mesh is flat where it curves. Measured at 4000 random points:

| vertex spacing | median | 95 % | worst |
|---|---|---|---|
| 0.1 m (28 m / 280) | 0.07 mm | 0.29 mm | 0.68 mm |
| 0.25 m (160 m / 640) | 0.14 mm | 0.60 mm | 1.5 mm |
| 0.31 m (80 m / 256) | 0.27 mm | 1.1 mm | 3.5 mm |
| 0.63 m (80 m / 128, the engine's default) | 1.2 mm | 4.3 mm | 10 mm |

For contact that must be exact (a foot, a post), place on the mesh, not at
`height_at`.

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

Not yet ported. The engine's canvas generators (`scratches`, `smudges`,
`noise`, `voronoi`, `patches`, `pores`, `weave`, `grain`), `heightToNormal`,
`composite` and the factories (`createPaintedMetal`, `createRubber`,
`createSkin`, `createScaly`, `createFabric`, `createWornMetal`) are to become
numpy rasters (the same mulberry32 stream draws the same images) and
Principled node materials. Meanwhile, fetched scans plus `layer_surface`
cover most worn surfaces.

## Relief — real depth from a height map

The engine's silhouette parallax (SPOM) ray-marched a height field to fake
depth and an outline in a real-time raster. EEVEE 5.2 displaces real
vertices, so here the relief IS geometry: it casts and receives real
shadows, carves a true silhouette, and the placement rays and contact checks
see it. The names and options stay the engine's where they still mean
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
- `silhouette=True` (the default) carves inward: the peaks stay at the
  polygon, like the engine's flat SPOM. `create_relief_column` inflates
  outward instead, so its relief overhangs the round outline (the engine's
  inflate shell + core + caps is now one displaced cylinder with flat caps at
  radius + 0.95 × relief depth).
- The field notes' contrast stretch is built in (`contrast=(0.15, 1)`): the
  map's own 0.5–99.5 % range is mapped to (floor, 1), so a low-contrast
  mid-grey Poly Haven `_disp` carves visibly and no well goes full depth.
- Vertices are the cost: the 3 × 2.4 m probe wall (one quad) at 8 mm edges
  is nine Simple subdivision levels (512 × 512 = 262 k faces) and renders in
  seconds.
  `method='BUMP'` keeps the look without the vertices (no silhouette, no
  shadows from the relief).
- The march's own knobs (`minLayers`, `maxLayers`, `minViewZ`, `debugMarch`,
  `debugSilhouette`, the marched self-shadow, `heightNormal`) have nothing to
  do here: EEVEE shadows and shades the real surface.

Probe: `test_relief.py` (a carved brick wall beside the same material as
bump only, a relief column, under raking light, and the wall with an
unapplied scale in world and object space).

## Not yet ported

- `ProceduralMaterials`: generators, compositing, factories.
- Relief: the engine's per-face bounds (`faceBounds`, `silhouetteBounds`,
  `sampleBounds`) for world-UV merged boxes; `reliefFactor` is kept on the
  column only.
- True displacement on a dense hero patch of `make_terrain` for close ground
  shots (the film material is bump/normal only; `relief.subdivide` and a
  displacement material are the parts to build it from).
- A live (Geometry Nodes) curvature attribute for meshes that deform after
  `layer_surface`.
- The engine's warning about a texture's `repeat` became the Mapping-node
  warning; Blender images have no repeat of their own.
