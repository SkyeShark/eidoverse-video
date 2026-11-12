# Procedural materials — generated textures and PBR factories

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Terrain and surfaces](terrain-surfaces.md)

This is the Blender 5.2 EEVEE edition of `procedural_materials.js`
(`window.ProceduralMaterials`). Reach for it when no fetched texture set
fits — most often plastic, painted metal, skin and fabric wear — and for
layering procedural wear over a fetched scan so a surface looks used rather
than catalogue-fresh. For terrain and built geometry with fetched sets, see
[terrain-surfaces.md](terrain-surfaces.md) (`layer_surface`); this guide is
the generators those layers can borrow from.

```python
from eidoblend.materials import procedural as PM

mat = PM.create_painted_metal(color=0x8a1c1c, scratches=True, smudges=True, repeat=(3, 3))
obj.data.materials.append(mat)
PM.help()                                   # the reference card, printed
```

## Generators — textures

Each generator returns a Blender image, **packed into the .blend** (a saved
file renders on its own), with the engine's colour space: Non-Color for
data (heights, roughness, normals), sRGB for `patches`. The image's rows sit
on the UVs as the engine's canvas did (the canvas's top row at v = 1).

```python
s = 512
noise_tx = PM.noise(s, s, scale=12, octaves=5, contrast=0.7)        # fBm; warp=True for domain warping
scratch_tx = PM.scratches(s, s, density=0.5, depth=0.6)             # direction=radians for brushed marks
smudge_tx = PM.smudges(s, s, amount=0.5)                            # fingerprints, wipes
cells = PM.voronoi(s, s, scale=8, mode='edges', edge_width=0.05)    # 'cells' | 'edges' | 'distance'
cow = PM.patches(s, s, base_color=0xfff0e0, patch_color=0x1a1a1a, shape='blob')   # 'blob' | 'voronoi' | 'spots'
pores_tx = PM.pores(s, s, density=0.5, depth=0.3)                   # a normal map
cloth = PM.weave(s, s, density=30, variation=0.2)                   # threads per tile
wood = PM.grain(s, s, scale=3, stretch=14, contrast=1.6)            # elongated along u
```

The engine's call shape works too, camelCase keys and all:
`PM.voronoi(512, 512, {'mode': 'edges', 'edgeWidth': 0.05})`.

- `height_to_normal(image, strength=1.4)` — a normal map from any grayscale
  height (its red channel), central differences, wrapped at the borders.
- `composite(a, b, mode, strength=)` — `multiply` | `add` | `screen` |
  `overlay` | `max` | `min`; `strength` mixes the result over `a`; `b` is
  resampled to `a`'s size. Works on any image, so a fetched scan's
  roughness can take procedural wear:
  `PM.composite(tex['roughness'], PM.smudges(1024, 1024, amount=0.6), 'add', strength=0.25)`.

The maths generators (`noise`, `voronoi`, `patches`, `weave`, `grain`,
`height_to_normal`, `composite`, the factories' own maps) are the engine's
canvas maths in numpy, **byte-identical** to the engine's images: same hash,
same fBm rotation, same truncation. The drawn ones (`scratches`, `smudges`,
`pores`) replay the engine's Mulberry32 draw list stroke for stroke and
rasterise with box-filtered coverage; they differ from Skia's anti-aliasing
by a mean of 0.05–1 grey levels, with the total ink within 4 %
(`blender/tests/terrain_extras/test_pm_parity.py` runs the engine's own file
under deno on its own canvas and compares every case).

## Factories — materials

Each returns a Principled BSDF material wired as three's
`MeshStandardMaterial` / `MeshPhysicalMaterial` reads its maps: `color`
multiplies the colour map, roughness multiplies the roughness map's green
channel, metalness the metalness map's blue, the clearcoat roughness its
map's green; normal maps go through a tangent-space Normal Map node at the
engine's `normalScale`.

```python
PM.create_painted_metal(color=0x1a3a6a, metalness=0.4, roughness=0.3, clearcoat=0.8,
                        clearcoat_roughness=0.1, scratches={'density': 0.6, 'direction': 1.2},
                        smudges=True)                              # car paint, server racks
PM.create_rubber(color=0x222222, grain_scale=20, bump_strength=0.5)   # tyres, gaskets, grips
PM.create_skin(color=0xcc8866, subsurface=0.15, pores={'density': 0.5},
               patches={'patch_color': 0x1a1a1a, 'shape': 'blob'})   # organic, animals
PM.create_scaly(color=0x2a5a3a, cell_size=12, clearcoat=0.3)        # reptile, fish
PM.create_fabric(color=0x4a4a6a, thread_density=30, wear={'amount': 0.5},
                 diffuse_map=tex['color'], roughness_map=tex['roughness'])   # over a fetched scan
PM.create_worn_metal(paint_color=0x3a5a3a, metal_color=0x888888, wear_amount=0.4)   # chipped paint
```

Every factory also takes `repeat=(u, v)` (three's `texture.repeat`: a
Mapping on the UVs), `uv_map=` and `name=`; `tex_size=` sets the generated
maps' resolution (512 by default).

Build your own from generated maps with `mesh_material(...)` — three's
material options as keywords (`color`, `map`, `roughness`,
`roughness_map`, `metalness`, `metalness_map`, `normal_map`,
`normal_scale`, `clearcoat`, `clearcoat_roughness`,
`clearcoat_roughness_map`, `transmission`, `thickness`, `ior`, `ao_map`;
anything else is ignored with three's warning, `'rougness' is not a
property`):

```python
# the engine's recipe: 90s computer plastic (no fetched texture exists for it)
noise_tx = PM.noise(512, 512, scale=12, octaves=5, contrast=0.7)
height_tx = PM.composite(noise_tx, PM.scratches(512, 512, density=0.5, depth=0.6), 'add', strength=0.5)
plastic = PM.mesh_material(color=0xc8c4b8, roughness=0.8, metalness=0.05,
                           normal_map=PM.height_to_normal(height_tx, strength=1.4), normal_scale=0.7,
                           roughness_map=PM.composite(PM.smudges(512, 512, amount=0.5), noise_tx, 'add'),
                           repeat=(3, 3))
# or, the same in one call:
plastic = PM.computer_plastic_90s(repeat=(3, 3))
```

Field notes:
- Set `repeat` on large surfaces, or one 512 px tile spreads as a blur
  across the mesh. On a mesh with UVs in metres (the course builder's
  pieces, `relief.world_uv_boxes`), `repeat=(0.5, 0.5)` is one tile per 2 m.
- The factories' `roughness` and `metalness` scale their maps:
  `roughness=0.5` halves the whole roughness map.
- `color` multiplies the colour map (the engine's rule), so a skin's own
  variation map, already in the skin colour, is multiplied by it again: the
  engine's skin is that deep, saturated orange, and so is this one.
- `create_painted_metal`'s clearcoat roughness is 0.1 × the scratch map, so
  the coat is a near mirror and the scratches show in reflections, not in
  diffuse light — as in the engine.
- The skin's `subsurface` was a partial transmission in the engine (its
  "subsurface approximation"); here it is Blender's own subsurface weight
  (radius from `thickness`: 0.8 → 8 mm), because EEVEE draws partial
  transmission as grain at any sample count.
- The normal maps keep the engine's channel signs. Red is right; green is
  the inverse of three's green-up reading (the engine differences toward the
  image's top), so a bump's upper and lower flanks swap their light.
  `height_to_normal(..., flip_green=True)` and
  `create_scaly(flip_green=True)` write green-up maps. On the engine's own
  maps the difference is slight: under a low light the two scaly maps side by
  side (`pm_raking.png`) differ only in which cell edges carry the dark
  streaks.
- Generation is numpy on the CPU: at 512 px the drawn generators take
  0.1–0.3 s, `noise`, `voronoi` and `height_to_normal` about 1 s each,
  `create_scaly` about 3 s (three Voronoi passes). Make materials once in
  `setup()`, never per frame; `tex_size=256` quarters the cost.

Probes: `blender/tests/terrain_extras/test_material_board.py` — every
generator as a swatch (`pm_generators.png`), every factory and the recipe
on spheres and bevelled boxes (`pm_factories.png`, each row closer in
`pm_factories_close_row1.png` / `_row2.png`), the normal-mapped ones under a
low raking light (`pm_raking.png`). `test_pm_parity.py` (system Python and
deno, no Blender) holds every generator, composite and factory map against
the engine's own canvas.

## Not yet ported

Nothing of `procedural_materials.js` is left out. Two differences in kind:
- The generators hand back images, not `CanvasTexture`s: there is no
  canvas object (or its `LinearFilter`) to return; the factories read the
  images Linear, which EEVEE mipmaps.
- three's `aoMap` is accepted by `mesh_material` and left unwired: EEVEE
  shades its own ambient occlusion.
