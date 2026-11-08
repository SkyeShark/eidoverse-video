# SDF surfaces, volumetric effects and isosurfaces

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

`eidoblend.sdf` is the Blender edition of `sdf_raymarch_loader.js`. The
engine raymarched each SDF per pixel inside a proxy box and patched the
renderer to composite it. That drew the shape, but the shape could not
cast a shadow, sit in a reflection or take the scene's own lights. In
EEVEE an SDF becomes scene content:

- a **solid** is its GLSL `map()` evaluated on the GPU and dual-contoured
  into a quad mesh at film resolution, with its `surface()` baked to
  textures;
- a **volume** is its `sample()` or `medium()` evaluated into OpenVDB grids
  and played by a Volume object;
- a **screen** is the SDF raymarched into an image (`make_sdf_texture`).

The GLSL is the engine's own dialect, with its primitive library
prepended, so the engine's GLSL originals run as they were written.

## SDF solids — `create_sdf_object`

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.sdf import create_sdf_object

blob = create_sdf_object(
    bounds={'min': [-0.6, 0.0, -0.6], 'max': [0.6, 1.2, 0.6]},     # the SDF's local frame, three style (y up)
    quality='balanced',
    map='''vec2 map(vec3 p) {
             float body = sdSphere(p - vec3(0.0, 0.45, 0.0), 0.4);
             float head = sdSphere(p - vec3(0.0, 0.95, 0.0), 0.2);
             return vec2(smin(body, head, 0.1), 1.0); }''',
    surface='''SdfSurface surface(vec3 p, vec3 n, float mat) {
             SdfSurface s = sdfSurface(mix(vec3(0.3, 0.5, 0.8), vec3(0.85, 0.5, 0.7), fbm(p * 3.0)), 0.5);
             s.sheen = 0.4;
             return s; }''',
    location=(2.0, 1.0, 0.0))
blob.place_on_ground(0.0)        # seats the mesh's lowest vertex on z = 0
blob.object                      # an ordinary mesh object: shadows, reflections, depth, motion blur
```

`map(p)` returns `vec2(distance, material id)`, exactly as in the engine.
Coordinates inside every GLSL function are the SDF's local frame, three
style (y up). The mesh is converted to Blender's axes when it is written,
so the GLSL never changes. The engine's library is always there:
`sdSphere sdBox sdRoundBox sdCapsule sdCap2 sdEllipsoid sdTorus sdCone
sdRoundCone sdTriPrism`, `smin smax opU opSmoothU opSub opSmoothSub
opInt`, `opRotateX/Y/Z opMirrorX/Z`, `_hash vnoise fbm fbm6`, and
`calcNormal softShadow sampleEnvMap sdfReflectWorld`. `uTime` is the time
in seconds and `cameraPosition` is the viewer in the local frame.

What happens in a build:

1. The bounds are cut into bricks of 4³ voxels. One GPU pass evaluates
   each brick's centre and keeps the bricks the surface can reach. A
   second pass evaluates the corners of the kept bricks. So the work
   follows the surface's area, not the bounds' volume.
2. Each grid edge whose ends change sign is a crossing. Three regula falsi
   iterations against the real field place the crossing. Linear
   interpolation is exact only where the field is linear along the edge,
   and near a crease (a box edge, a boolean cut, a panel gap) it lands up
   to a third of a voxel off. On the options probe's box the refinement
   brings the corners from 0.29 to 0.025 voxel (`refine=0` is linear
   interpolation; `qef_lambda=2` pulls them to 0.74 voxel, round).
3. Each cell gets one vertex, the QEF minimiser of its crossings' planes,
   so sharp edges and corners stay sharp. Each crossing edge emits one
   quad. The mesh is closed and wound outward.
4. `surface()` is evaluated per texel. Each quad gets a block of texels in
   a packed EXR atlas, beside an object-space normal map taken from the
   field's gradient. Material and relief detail are several times finer
   than the mesh, as the engine's per-pixel `shade()` was. Blocks follow
   a 2D Z-order curve over the quads' 3D Morton ranks, and each carries a
   one-texel gutter repeating its edge. So when the GPU's mipmaps blend
   neighbouring blocks, at a distance, they blend neighbouring surface.
   Without that, row-major blocks put unrelated quads side by side, and
   a distant shot showed their edges as faint rings. The mesh's custom
   normals go in as Blender 5's `custom_normal` float attribute, straight
   from numpy.

The surface closes at the bounds box, which is padded by two voxels. The
engine never drew outside its box either. Measured on the probes (build
time, then quads and voxel size):

| example | build time | quads | voxel |
|---|---|---|---|
| basic sphere | 0.7 s | 28k | 15.6 mm |
| blob | 1.9 s | 143k | 8.6 mm |
| coat | 1.8 s | 120k | 1.7 mm |
| Mr. Hege | 11 s | 201k | 7.8 mm |
| red shoggoth | 14 s | 191k | 8.9 mm |
| explosion | 4.4 s | 270k | 16.4 mm |
| Sierpinski tetrahedron | 13 s | 1.2 M | 5.5 mm |
| ultra mandelbulb | 61 s | 3.8 M | 3.9 mm |

The QEF is accumulated straight from the edge arrays and solved in closed
form per cell, so a mesh of tens of millions of crossings stays inside a
few GB.

### `surface()`: what EEVEE renders

The engine's `shade(p, n, mat)` returned a lit colour from hand-placed
lights. The Blender edition keeps what `shade()` knew about the surface
and lets EEVEE light it. `surface(p, n, mat)` returns an `SdfSurface`:

| field | Principled input |
|---|---|
| `albedo` (linear) | Base Color |
| `roughness`, `metallic` | Roughness, Metallic |
| `emission` (linear radiance) | Emission Color, strength 1 |
| `sheen`, `sheenTint` | Sheen Weight, Sheen Tint |
| `subsurface`, `coat`, `specular`, `transmission` | Subsurface Weight, Coat Weight, Specular IOR Level, Transmission Weight |

Start from `sdfSurface(albedo, roughness)`. A channel that has the same
value everywhere is not stored: its Principled input gets the constant.
The originals' view-dependent terms map onto layers: a fresnel rim becomes
sheen, a wrap "SSS" term becomes subsurface, and a wet eye becomes coat.
In the bake, `cameraPosition` sits straight along the normal, so any rim
term inside a helper reads as seen head-on and stays out of the textures.
`material_settings` sets what does not vary per point: `subsurface_radius`,
`subsurface_scale`, `ior`, `coat_roughness`, `sheen_roughness`,
`emission_strength`, `normal_strength`, and `interpolation`.

Keep `shade()` too. `blob.raymarch_reference(camera)` runs the engine's
own march with the engine's `shade()` from a Blender camera. It uses the
quality preset's `maxSteps`, `surfEps`, `stepScale` and `maxDist`, the
bounds-box entry and the same hit test. It returns a linear image, so the
EEVEE render can be judged against the original. Every example's probe
in `blender/tests/sdf/` renders both side by side. It also compares the
mesh's silhouette with the march's: intersection over union is 0.97 to
0.997.

A spec in the engine's own contract, `map` and `shade` with no
`surface`, still renders: `shade()` becomes the material. Its colour,
seen head-on so rim and fresnel terms drop out, is the base colour
(`shade_as='albedo'`, the default) or the emission (`shade_as='emission'`).
As albedo, the scene's lights shade it again on top of the hand lighting
baked into the colour, so the dark side reads darker than the engine's.
As emission it is the engine's exact unlit look: it still casts shadows
and shows in reflections, but takes no light. Write `surface()` when the
object matters; the help's own peanut renders both ways in
`test_help_recipes.py`.

### Options

`create_sdf_object(spec, **overrides)` takes a dict or an `EXAMPLES` entry,
plus keyword overrides:

- `map`, `surface`, `shade`, `extra`: GLSL strings, or Python callables
  (below). `extra` holds helpers, `#define`s and material functions, and
  goes in before `map`.
- `bounds`, `quality` (`'fast'`, `'balanced'`, `'high'` or `'ultra'`), and
  `max_steps`, `max_dist`, `step_scale`, `surf_eps` (the engine's
  `maxSteps` and the rest, for the reference march).
- `uniforms`: `{'uRadius': 0.4, 'uTint': ('color', '#3cbf6a')}`. A number
  is a float, a 3-sequence a vec3, and `('color', hex or 0xRRGGBB)` a
  linear colour. `textures={'uChecker': array, image or path}` adds
  `sampler2D`s, and `defines={'NAME': value}` adds `#define`s. The GLSL
  originals declared their uniforms themselves (`uniform vec3 uPaint;`
  in `extra`). Keep those lines: a declaration gives the uniform its
  type, a value the spec does not set starts at zero, a declared sampler
  the spec does not give reads black, and the values arrive through the
  engine's uniform block. All four GLSL vehicles compile unchanged.
- `voxel`, or `cells` along the longest side, sets the mesh resolution.
  `texels` per quad side and `atlas_budget` (16 M texels by default, about
  128 MB of VRAM per image) set the atlas. A very large mesh gets fewer
  texels per quad, because its geometry already carries the detail. Past
  a million quads even 2 × 2 texels a quad would pass the budget, and the
  channels go on the vertices instead (the fractals at 'high' and 'ultra'
  do this; an atlas of the Menger sponge had come to 460 MB of EXR).
- `shade_as` (`'albedo'`, `'emission'` or `None`) turns a `shade()` into
  the material when there is no `surface()` (above).
- `cut_by_bounds=True` says the shape runs past its bounds on purpose (a
  gyroid, a repeating fence): the bounds box cuts it into a closed solid,
  and the reference march marches the same cut field. Without it the
  reference is the engine's own march, which walked back out of the box
  and drew the uncut surface in front of it.
- `carrier='atlas'` (texture atlas, the default) or `'vertex'` (point
  attributes); `normals='corner'` (crease-keeping) or `'vertex'`.
- `iso` meshes the level set `map = iso` instead of zero. Use it for
  distance estimators, such as fractals. `min_component` drops pieces
  smaller than that many quads (fractal dust). `refine` (regula falsi
  iterations, 3), `qef_lambda` (0.01), `brick` (the culling brick, 4
  voxels a side) and `lipschitz_k` (how much faster than distance the
  field may change, 1.25 / stepScale by default) tune the mesher; a field
  that changes faster than its `lipschitz_k` loses surface in culled
  bricks, so a non-distance field (a scaled or displaced map) wants a
  larger one.
- `materials={2: bpy_material}` gives every face whose material id is 2
  that Blender material. The baked material covers the rest.
- `time` is the build time in seconds (`uTime`). `cache_dir` (default
  `//sdf_cache`) receives the atlases and frame caches. `pack_images`
  packs the atlases into the .blend.
- `location`, `rotation`, `scale`, `name`, `scene`, `collection`, and
  `build=False` to build later with `.build(t)`.

`set_uniform('radius', 0.4)` (or `'uRadius'`) changes a live uniform; the
next `build()` or baked frame uses it. `bounds_report()` gives the mesh's
extent against the declared bounds and flags a shape the bounds cut off.
The engine's placement rule was `mesh.position.y = groundY - bounds.min.y
* scale`. `place_on_ground(z)` seats the mesh's real lowest vertex
instead, so loose bounds no longer make a model hover.

| quality | maxSteps | surfEps | stepScale | maxDist | cells (longest side) | texels per quad side |
|---|---|---|---|---|---|---|
| fast | 64 | 0.0020 | 0.90 | 60 | 128 | 3 |
| balanced | 128 | 0.0010 | 0.85 | 100 | 256 | 4 |
| high | 192 | 0.0005 | 0.75 | 150 | 384 | 4 |
| ultra | 256 | 0.0003 | 0.70 | 200 | 640 | 5 |

Thin parts need voxels finer than their thickness: raise the quality or
pass `voxel=`.

### Animated SDFs

```python
hege = EXAMPLES['mr_hege'].make(cache_dir='//sdf_cache')
hege.bake(1, 120)                                   # uTime = (frame - 1) / fps
hege.bake(1, 120, step=2, time_scale=0.5,           # every other frame, half speed,
          controls=lambda frame, t: {'uRadius': 0.2 + 0.1 * t})   # uniforms keyed per frame
```

`bake()` re-meshes the SDF once per frame into `<name>_####.ply`. A
Geometry Nodes player on the object imports the current frame's file, so
the saved .blend plays and renders any frame on its own. Frames skipped by
`step` hold a copy of the previous frame. The surface channels travel as
PLY vertex properties (`carrier='vertex'`, the default for animation).
With `carrier='atlas_sequence'` they travel as one atlas set per frame,
played as image sequences. Each sequence gets a hold copy at
`frame_start - 1`, because an image sequence shows that file before its
range. The first frame decides which atlas images the sequence carries,
and its constant channels become the material's values. A channel left
at the Principled default would show: the default Emission Color is
white, and the stylized blob glowed white until the constants went in.

### SDFs written in Python

`SDF_NP` (also exported as `SDF_TSL`, the engine's name) is the primitive
library over numpy, in snake_case: `sd_sphere`, `sd_box`, `smin`,
`op_smooth_u`, `op_rotate_y`, `hash`, `vnoise`, `fbm`, `fbm6`. It also
carries the TSL math the engine re-exported: `vec2/3/4`, `mix`, `clamp`,
`smoothstep`, `select`, `pow`, `atan(y, x)`, `mod` (GLSL's), `cross`,
`reflect`, and the rest. `map(p)` takes (N, 3) float32 arrays and returns
`d` or `(d, mat)`. `surface(p, n, mat)` returns a dict of the `SdfSurface`
fields. The result is the same Blender object, built on the CPU. The GLSL
and numpy libraries agree to float32 rounding, the hash and the noise bit
for bit (`test_library_parity.py`).

The engine's TSL map read `time` and its `uniform()` nodes. A Python map
reads the SDF it is being evaluated for: `S.time` is its `uTime` in
seconds, and `S.uniform('uR')` (or `'r'`) is the current value of a
uniform the spec declared. So `bake()` and `set_uniform()` drive a Python
SDF as they drive a GLSL one:

```python
def bob(p):
    centre = S.vec3(0.0, 0.3 + 0.15 * float(S.sin(S.time * 3.0)), 0.0)
    return S.sd_sphere(p - centre, S.uniform('uR')), 1.0

o = create_sdf_object(map=bob, uniforms={'uR': 0.18}, bounds=..., carrier='vertex')
o.bake(1, 72, controls=lambda frame, t: {'uR': 0.1 + 0.002 * frame})
```

The rest of TSL's builder set has no Python counterpart because Python
is the builder: `Fn` is `def`, `Loop`/`Break` a `for` loop, `If` and
`select` are `np.where` (`S.select`), and `Discard`, `varying` and the
camera nodes (`cameraPosition`, `cameraViewMatrix`, `positionGeometry`,
`viewZToPerspectiveDepth` ...) belonged to a per-pixel march that a baked
mesh does not have.

`fbm(p)` here is the engine's noise with one fix. `_hash`'s arithmetic is
declared `precise`. Without it the GPU compiler folds each of vnoise's
eight corner offsets into the hash differently. One lattice point then
hashes to different values from the cells around it, and the noise tears
along cell faces: 1.5 % of face crossings jumped, by up to 0.99. The
engine's own raymarch shows the same seams, a faint square outline on
`stylizedBlob`. With `precise` there are none, and the hash computes the
same function.

## The EXAMPLES

`EXAMPLES['name'].make(**overrides)` builds one. `create_sdf_object(EXAMPLES['name'], ...)`
does too.

| name | what | notes |
|---|---|---|
| `basic_sphere` | 'fast' smoke test | |
| `stylized_blob` | domain-warped blob with dimples, animated | the fresnel rim is a lavender sheen |
| `detailed_coat` | creature coat: mackerel stripes over fbm, micro-relief, belly | the rim is fur sheen; 1.7 mm voxels |
| `fractal_core` | mandelbulb, power 8, 'ultra' | `iso` 1.5 mm, the march's own stop distance |
| `mr_hege` | Mr. Hege, the octopus man in a wool suit, animated | 10 materials: subsurface skin, wool sheen, metal buckle, coated eyes |
| `red_shoggoth` | the red shoggoth with the blue angry mask, 48 blinking eyes, animated | from the engine's GLSL backup, like Mr. Hege |
| `explosion` | the pyroclastic fireball: a displaced sphere pulsing on a 25 s cycle, animated | the displacement rides the material channel; its hot share is emission, its smoky share a lit surface; `make(speed=, noise_freq=, noise_amp=)` |
| `mandelbulb`, `sierpinski_tetra`, `menger_sponge`, `gyroid` | the screen recipes as placeable solids | coloured by the recipes' palette, which drifts with `uTime`; the gyroid is `cut_by_bounds`, the Menger sponge is 'high' so its fifth level's 8 mm holes open |

Mr. Hege and the red shoggoth are the two examples the engine's TSL
migration dropped. They come from its GLSL backup, as written. The only
changes are two that alter no result. Reversed-edge `smoothstep(hi, lo, x)`
is written `1.0 - smoothstep(lo, hi, x)`, the same curve, as the TSL port
did elsewhere. Each helper's material dispatch is also shared by `shade()`
and `surface()`. The red shoggoth's look comes from `red_shoggoth.png`,
the meme it was modelled on: red skin, eyes over body and tentacles, the
blue frowning mask on a strap.

Every animated example bakes and plays (`test_animated_examples.py`): the
shoggoth's tentacles wave and its eyes blink, the explosion's radius
pulses while its noise rises, the blob's warp moves, and the recipe
solids' palette drifts.

### The help()'s samples and patterns

The engine's `help()` taught the API with a minimal recipe (two spheres
joined into a peanut, `map` + `shade`), a custom-uniforms sample
(`sdSphere(p, uRadius)` with `shade` returning `uColor`, the radius driven
per frame) and five recipe patterns. `test_help_recipes.py` writes each
one as the help described it and renders them:

- the peanut, with `shade()` as its base colour and as its emission;
- the uniforms sample, its `{'value': ...}` uniforms as the engine spelled
  them, the radius keyed per frame through `bake(controls=...)`;
- a character body (capsule torso, four `sdCap2` limbs, head and eyes,
  `smin` 0.05, limbs swinging with `sin(uTime)`);
- a crystal: the help named an `sdOctahedron` the library never had, so
  the gem brings its own in `extra`, with emissive tips joined by
  `opSmoothU` and pulsing with `uTime`;
- a tentacle of seven `sdCap2` segments, each joint on `sin(uTime + i)`;
- a hollow shell, `opSmoothSub(inner, outer, 0.05)`, with a window cut so
  the hollow shows;
- a repeating prop: a fence from `mod(p + period/2, period) - period/2`,
  its bounds ending mid-gap so no post is cut (`cut_by_bounds` for the
  rails).

### The example convention

The vehicle and volume examples are added on this engine with
`register_example`, each family in its own `eidoblend/sdf/examples_<family>.py`.
The package imports every `examples_*.py` it holds, so a new family's file
needs no other edit. An example is GLSL plus numbers, and every field is a
`create_sdf_object` / `create_sdf_volume` option:

```python
from eidoblend.sdf import register_example

register_example('my_car', kind='solid', description='...',
    bounds={'min': [-1.05, 0.0, -2.4], 'max': [1.05, 1.55, 2.4]},   # tight: bounds.min is the lowest point
    quality='high',
    uniforms={'uPaint': ('color', 0xc8c8d2), 'uRough': 0.45},       # live: make(...).set_uniform('paint', ...)
    extra=HELPERS_GLSL,                # #defines, helper SDFs, per-material functions
    map=MAP_GLSL,                      # vec2 map(vec3 p): the engine's map
    shade=SHADE_GLSL,                  # vec3 shade(vec3 p, vec3 n, float mat): the engine's look, for the reference
    surface=SURFACE_GLSL,              # SdfSurface surface(vec3 p, vec3 n, float mat): what EEVEE renders
    animated=False,                    # True when map / surface read uTime: bake() per frame
    make=None)                         # optional factory(example, **opts) -> object (the engine's make(opts))

register_example('my_fire', kind='volume', bounds=..., steps=96,
    sample=SAMPLE_GLSL,                # SdfSample sample(vec3 p) -> sdfSample(color, alpha, step), or
    medium=None,                       # SdfMedium medium(vec3 p) -> sdfMedium(density, albedo, emission)
    post=POST_GLSL)                    # vec4 post(vec4 sum): the reference march only (see Volumes)
```

`make(opts)` options that the engine took as camelCase (`paintColor`) map
onto uniforms inside the example's own `make`. Inside the GLSL,
`SDF_VIEW_DEPENDENT` is 1 only in the reference march. It keeps a view
term out of a shared helper.

## Volumes — `create_sdf_volume`

```python
from eidoblend.sdf import create_sdf_volume, volume_render_settings

fire = create_sdf_volume(sample='''
    SdfSample sample(vec3 p) {
        float r = length(p - vec3(0.0, 0.6, 0.0)) + (fbm(p * 3.0 - vec3(0.0, uTime, 0.0)) - 0.5) * 0.35;
        float d = clamp((0.5 - r) * 6.0, 0.0, 1.0);
        return sdfSample(vec3(1.6, 0.7, 0.2) * 2.0, d * 0.09, 0.02);
    }''', bounds={'min': [-0.75, 0, -0.75], 'max': [0.75, 1.3, 0.75]}, cells=160, cache_dir='//vol_cache')
fire.bake(1, 120)                                    # one .vdb per frame, played as a Volume sequence
volume_render_settings(scene, tile_size='2', samples=128)
```

Two contracts, both GLSL in the local frame, with the library and `extra`:

- `sample(p)` is the engine's: `{color, alpha, step}`, composited front to
  back. It converts exactly. Compositing `a = alpha` over a stride `step`
  is the transmittance of an absorbing medium with extinction
  `density = -ln(1 - alpha) / step` that emits `color · density` per metre.
  The engine's colour was already lit, so there is no scattering. The
  probe marches rays through the written grids and compares them with the
  engine's march on the GPU: opacity and light agree. `sample_as='albedo'`
  reads the colour as the scattering colour instead, with no emission: a
  smoke whose engine colour was a hand-lit grey then takes the scene's
  light and casts volume shadows.
- `medium(p)` is Blender-native: `density` (extinction per metre),
  `albedo` (scattering colour, lit by the scene's lights and shadowed),
  `emission` (radiance per metre), and `temperature` (blackbody kelvin,
  0 = none).

`sample` is a reserved word in desktop GLSL 4.x (the per-sample
interpolation qualifier). Write `SdfSample sample(vec3 p)` as the engine
did anyway: the volume kernels rename the function, and every call to it,
before compiling.

Either stage may also be a Python function over (N, 3) numpy points, as
the engine's TSL `sample` was a JavaScript function. `sample(p)` returns
`{'color', 'alpha', 'step'}` (or the tuple), `medium(p)` returns
`{'density', 'albedo', 'emission', 'temperature'}` (albedo defaults to
0.8 grey), and both read `S.time` and `S.uniform()`. A Python stage gives
the same grids as its GLSL twin; it has no reference march, which runs
GLSL.

The grids `density`, `emission`, `albedo` and `temperature` go into one
OpenVDB file per frame, voxel-centred, with near-empty voxels pruned. A
Volume object plays them through a Principled Volume. `cells` (or `voxel`,
or `quality`: 96, 160, 256 or 384 cells) sets the resolution.
`material_settings` takes `density_scale`, `emission_scale`, a constant
`albedo`, `anisotropy`, `blackbody_intensity` and `blackbody_tint`.
`vol.raymarch_reference(camera)` is the engine's own march of the same
`sample()`, followed by `post()`.

`post(sum)` reshaped the composited pixel: a contrast curve or an alpha
remap. A physical volume has no composited pixel to reshape, so `post`
runs only in the reference march. A volume example folds its post into
its colours and densities, or applies it in the compositor. The engine's
other volume limits fall away: the camera may enter the box, and
overlapping volumes mix physically, so they need no per-frame sort
(the engine's `sortSdfVolumesForCamera`). The engine's march also stopped
after `steps` samples; the grids hold the whole box, so a volume longer
than `steps × step` shows its far part here where the engine cut it off.
`steps` still drives the reference march.

EEVEE's froxel grid is screen-space. A small volume far away needs a small
`tile_size`, and volume shadows need `use_volumetric_shadows`.
`volume_render_settings()` sets both.

## Screens — `make_sdf_texture`

```python
from eidoblend.sdf import make_sdf_texture

bulb = make_sdf_texture(recipe='mandelbulb', width=512, height=256,
                        uniforms={'power': 8.0, 'iterations': 96, 'paletteHueShift': 0.0},
                        camera_orbit_radius=2.6, camera_orbit_speed=0.18, camera_pitch=0.4, camera_fov=1.6)
bulb.bake(1, 240)                                      # a PNG sequence the image plays (update_every holds frames)
screen.data.materials.append(bulb.material(emission_strength=0.9))   # map + emissiveMap, as the engine used it
bulb.update(2.0)                                       # or one frame at t = 2 s into bulb.image
```

The recipes `mandelbulb`, `sierpinski_tetra`, `menger_sponge` and `gyroid`
are the engine's GLSL: palette, default shade, sky, distance estimators
and the orbiting camera's fragment main. The engine's WebGPU edition could
no longer run them, because a GLSL ShaderMaterial renders black there.
Blender's GPU module runs GLSL, so here they render again. `custom_de` and
`custom_shade` replace the estimator or the shade (GLSL), and
`set_uniform('power', 4.0)` changes a uniform. The texture holds what the
engine's 8-bit sRGB target held: the shader's values, clamped, read as
sRGB. camelCase options (`cameraOrbitRadius`, `customDe`) are accepted as
the engine spelled them. `samples` adds jittered passes per frame.

## Rhombic dodecahedron voxels

```python
from eidoblend.sdf import rhombic_dodecahedron as RD
crystal = RD.fill_volume_rd(bounds={'x': [-3, -1], 'y': [-1, 1], 'z': [0, 2]}, cell_size=0.25, material=pink)
orb = RD.fill_sphere_rd(center=(0, 0, 1.1), radius=0.85, cell_size=0.2, material=cyan, fill=2.0)
vox = RD.voxelize_mesh_rd(mesh=suzanne, cell_size=0.08, material=amber)
crystal.reveal(center=(-2, 0, 1.25), speed=1.0)     # cells appear inside a sphere growing 1 m/s
```

This is `rhombic_dodecahedron.js`. Each fill is one point-cloud object
whose Geometry Nodes instance the 12-face cell on the FCC lattice points.
`reveal()` is the engine's documented animation, built from Scene Time,
so the saved file plays it. The lattice walk is the engine's, float
accumulation and all, done in the engine's axes so that the same physical
box gives the same points (checked against the JS under deno).

Three of the engine's numbers disagreed with its comments, and the port
keeps the engine's behaviour by default:

- the cell's face centres sit at `radius / √2`, not at `radius`;
- the fills pass `radius = cellSize / 2`, so cells are half the tiling
  size and stand apart with gaps; `fill=2.0` closes them into the true
  space-filling tiling;
- the walk can round two strides to one point, and the fills drop those
  duplicates.

`voxelize_mesh_rd` counts every crossing of an upward ray, which is the
documented intent. The engine's three.js raycast culled back faces of a
single-sided material, so a closed mesh never tested inside, and the
engine always fell back to the box's inscribed ellipsoid.
`front_faces_only=True` reproduces that.

## Writable scalar fields — `make_iso_field`

`eidoblend.fx.iso_field` is the Blender edition of `makeIsoField`: a
CPU-written scalar field shown as its isosurface. The engine raymarched the
field per pixel to dodge three's per-frame JavaScript polygoniser. In
Blender the field becomes a real mesh through OpenVDB's volume-to-mesh, so
shadows, depth, motion blur and the scene's lights come for free. The
raymarched surface could cast no shadow and needed a proxy box.

The field contract is the engine's: `field[idx(x, y, z)] = value`, with
idx = x + y·res + z·res² in the engine's axes (y up). The grid is
node-centred, spanning x and z in [−half, half] and y in [0, 2·half] around
the object's location. The surface sits where field > `iso`, high inside.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.iso_field import make_iso_field

iso = make_iso_field(resolution=64, half=0.5, iso=50, color_hex='#9aa2ac', metalness=0.85, roughness=0.35,
                     location=(0, 0, 0))
iso.field[iso.idx(x, y, z)] = 100       # write cells like the engine's field
iso.upload()                            # a static surface, meshed now

def update(frame, t, iso):              # or a field that changes every frame
    iso.field[:] = my_field(t).ravel()  # in the engine's [z][y][x] order
iso.bake(1, 120, update=update)         # one PLY per frame, played by Geometry Nodes Import PLY
```

- `color_node(builder, position, normal)` and `emissive(...)` are the
  engine's colour and emissive hooks. They receive the shading point and
  normal as `eidoblend.fx._nodes` values, and return an RGB value built
  from them. Any other material can be passed as `material`.
- A changing field changes topology, so no point cache can hold it.
  `bake()` writes `<name>_####.ply` and a Geometry Nodes player reads the
  frame's file. In Blender 5.2, Join Strings concatenates its multi-input
  links in reverse creation order, and Value to String zero-pads only in
  integer mode. The player is built around both.
- The probe `blender/tests/fx/test_iso_field.py` animates three metaballs
  and renders their shadows on a floor.

## The helper and `help()`

`register_sdf_helper(scene)` is the engine's `registerSdfHelper(renderer,
mainScene)`. The engine's helper was a renderer patch: it drew the proxy
boxes, faked G-buffer passes and re-sorted volumes. All of that is native
in Blender. What is left: it links the SDF collection into the scene, and
binds the world's Environment Texture image as every SDF's `uEnvMap`. A
reference march's `sampleEnvMap()` then sees the HDRI EEVEE lights with.
`help()` prints the API reference and the registered EXAMPLES, like the
engine's `SdfRaymarchLoader.help()`.

## Probes

`blender/tests/sdf/`: `test_library_parity.py` (GLSL against numpy, the
mesher on exact shapes), `test_examples_compile.py`,
`test_examples_render.py -- examples=a,b` (EEVEE beside the engine's
march, silhouette IoU), `test_animated_bake.py` (the saved .blend reopened
and rendered), `test_animated_examples.py` (every animated example baked
and played), `test_help_recipes.py` (the help()'s samples and patterns),
`test_volume.py`, `test_volume_density.py` (EEVEE and Cycles against the
closed-form transmittance and emission), `test_sdf_texture.py`,
`test_options.py`, `test_rd_parity.py` (deno runs the JS) and
`test_rhombic_render.py`. Each script's docstring gives its command.

## Not yet ported

- **The vehicle and volume EXAMPLES** (`stylizedModernSedan`,
  `stylizedCyberpunkSedan`, `stylizedSciFiSleekCar`, `stylizedFighterJet`;
  `explosionRing`, `flame`, `smoke`, `gyroidFireball`, `bonfire`,
  `candleFlame`, `fire`, `nuclearBlast`) are added on this engine by the
  vehicles and volumes steps.
- `post(sum)` of a volume renders only in the reference march (see
  Volumes). A Python `sample()` / `medium()` has no reference march.
- The mesher's grid is uniform within the bounds (sparse, not adaptive). A
  shape with millimetre detail over metres needs fine voxels everywhere it
  has surface.
- Distance-estimator fractals carry sheets finer than a voxel, where one
  dual vertex joins several. 1 to 3 % of their edges are shared by four
  quads. They render cleanly, but the mesh is not a 2-manifold.
- `anisotropy` of `make_sdf_texture` has no per-image counterpart: Blender
  filters images by its own settings. Its `renderTarget`, `material`,
  `scene` and `camera` were the WebGL plumbing of one render target; here
  the image is the target.
- The engine's `passType`/MRT G-buffer plumbing, the proxy-box depth write,
  the shadow scene and the renderer patch (`registerSdfHelper`'s render and
  renderAsync hooks, `_isPostPassQuadScene`) do not apply: EEVEE renders
  the real geometry into every pass. The magenta placeholder the WebGPU
  engine returned for GLSL specs does not apply either: GLSL is this
  edition's contract.
- A baked mesh has no per-pixel camera, so the view-dependent terms of a
  `shade()` (fresnel rims, wrap lighting) become Principled layers chosen
  per example (sheen, coat, subsurface) rather than the hand formula.
