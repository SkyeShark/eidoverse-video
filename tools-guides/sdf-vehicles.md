# SDF vehicles — two sedans, a sci-fi car and a fighter jet

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [SDF engine](sdf-volumes.md)

The SDF engine's four vehicles come to the Blender edition as
`EXAMPLES['stylized_modern_sedan']`, `['stylized_cyberpunk_sedan']`,
`['stylized_sci_fi_sleek_car']` and `['stylized_fighter_jet']`. Their
geometry is the engine's own GLSL `map()`, dual-contoured into a mesh at a
few millimetres, so the shut-lines, louvers, badge plate and missile fins
are real geometry that EEVEE lights, shadows and reflects. Their look is one
Blender material per part. Every pattern the engine's `shade()` drew per
pixel is drawn per pixel again: the paint fleck, the racing stripes, the hex
hubcaps, the badge glyphs, the camo edges and the lamps' bright cores. The
engine had to fake the environment with `sampleEnvMap` and procedural sky
domes; here the car reflects the actual scene.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.sdf import EXAMPLES

car = EXAMPLES['stylized_cyberpunk_sedan'].make(paint_color=0xff2bd6, paint_roughness=0.12,
                                                 decal_text='ALETH8APO', cache_dir='//sdf_cache')
car.place_on_ground(0.0)                     # the lowest vertex on the ground
car.object.rotation_euler.z = -0.45          # three's rotation.y = -0.45

car.set_paint('acid')                        # live: the materials and the underglow lamps follow
car.key_uniform('uPaint', frame=1, value='cyan')
car.key_uniform('uPaint', frame=48, value='amber')     # LINEAR keys: the livery fades over two seconds
```

`make()` takes the engine's options in either spelling (`paintColor` or
`paint_color`) and returns a `VehicleSdf`, an `SdfObject` with the vehicle's
parts, live uniforms and lamps. `car.object` is the Blender object. The
vehicles face three's +z, which is Blender's −Y: the front of a car is
where a Blender front view looks.

## The four vehicles

| example | what | make() options (defaults) |
|---|---|---|
| `stylized_modern_sedan` | a 4-door notchback: rounded-box body and cabin, A/C-pillar planes, side-window tunnels, wheel arches, door / hood / trunk shut-lines, annular tyres with dished alloy rims and chrome caps, lamps, grille, mirrors, handles, belt trim | `paint_color` (pewter `0xc8c8d2`), `paint_roughness` (0.45) |
| `stylized_cyberpunk_sedan` | the same body with a full-width LED headlight bar, stacked round tail lamps, roof pods, gill vents, hood louvers, trunk chevrons, a hex grille, rocker underglow, accent strips, chrome dome hubcaps, asymmetric racing stripes and the ALETH8APO badge plate | `paint_color` (electric cyan `0x00e7ff`: the rim glow, underglow, accents and grille; the body stays near-black), `paint_roughness` (0.18), `decal_text` ('ALETH8APO') |
| `stylized_sci_fi_sleek_car` | a compact built from cylinder sections, with a pure-metal body, glass patches, sphere lamps and hex-tiled chrome hubcaps | `metal_color` (the body's F0, silver `(0.95, 0.93, 0.88)` linear), `paint_roughness` (0.15) |
| `stylized_fighter_jet` | hull, swept wings, stabilisers, canted fins, engine pods with bores, turbine faces and exhaust struts, a bubble canopy, emissive plumes, wing AAMs and a centreline bomb | `camo`: `'silver'`, `'sky'` (default), `'desert'`, `'forest'`, or 0 to 3 |

The geometry is the engine's own GLSL, taken from its GLSL backup; the
public engine's TSL edition kept every one of its numbers but one. The jet's
two canted fins splay outward there, F-18 style, as the comment beside them
says, and they splay outward here too. The backup turned them with
`pFin.xy *= _jetRot2(0.2)`, which multiplies the row vector and leans them
inward, the shape the April check frames show.

Colours take what `THREE.Color` took: an int `0xRRGGBB` or a `'#rrggbb'` /
`'#rgb'` string (sRGB, decoded to linear), or `(r, g, b)` floats, which are
linear. The sources documented `[r, g, b]` arrays too. `THREE.Color` ignored
those and left white; here a sequence means what the documentation said. Two
sets of presets are named: `METAL_PRESETS` (`silver`, `gold`, `copper`,
`aluminum`, `anodized_blue`, `anodized_purple`, the sleek car's F0 values)
and `ACCENT_PRESETS` (`cyan`, `magenta`, `acid`, `amber`, the cyberpunk
palette scene's liveries). `make(metal_color='gold')` works.

An option a vehicle does not have raises: `metal_color` on a sedan, `camo`
on a car, `decal_text` on anything but the cyberpunk sedan, or a misspelt
name. The engine's `make()` ignored those without a word, so a misplaced
option there did nothing. An unknown camo raises the engine's own message:
`unknown camo "polka". Use one of: silver, sky, desert, forest.`

## make()

Beyond the vehicle's own options, `make()` takes every `create_sdf_object`
option (`name`, `location`, `rotation`, `scale`, `scene`, `collection`,
`cache_dir`, `build`, `pack_images`, `uniforms` ...) and these:

- `quality`: `'fast'`, `'balanced'`, `'high'` (the examples' preset) or
  `'ultra'`. It sets the mesh voxel. `voxel=` (metres) or `cells=` (along
  the longest side) set it outright.
- `shading='parts'` (the default) builds the part materials below.
  `shading='baked'` builds the engine's generic path instead, described
  under [The baked path](#the-baked-path).
- `lamps=True` adds the real lamps; `lamp_power=1.0` scales them.
- `stripe_glow=0.45` (cyberpunk) is the racing stripes' self-light, the
  engine's `stripeCol * sm * 0.45`.
- `uniforms={'uPaint': {'value': 0xff2d95}, 'uRough': 0.22}` is the
  engine's full-control form, `createSdfObject({...spec, uniforms})`;
  `make()` reads any colour form above for a colour uniform. The generic
  `create_sdf_object(EXAMPLES[...], uniforms=...)` takes the SDF engine's
  typed forms, `('color', 0xff2d95)` or `{'value': 0xff2d95, 'type':
  'color'}`.

| voxel at 'high' | modern sedan | cyberpunk sedan | sleek car | fighter jet |
|---|---|---|---|---|
| size | 4 mm | 4 mm | 5 mm | 6 mm |
| quads | 3.35 M | 3.46 M | 1.43 M | 2.13 M |
| build (4090, shared) | 30-40 s | 45-60 s (the livery the first time) | 25 s | 40 s |

Each voxel puts a vehicle's finest feature across about three voxels: the
sedans' 12 mm shut-lines and 16 mm louvers, the sleek car's glass patches,
and the jet's 20 mm missile fins. `'balanced'` doubles the voxel, giving a
quarter of the quads at about a quarter of the time, and is right for a car
seen whole. `'fast'` quadruples it for a quick look. `'ultra'` is 0.75× the
voxel.

For a macro shot, pass `voxel=` yourself. One example is the sleek car's
hubcap filling the frame. Its rim meets the tyre at a right angle, 7.5 mm
from the disc's edge, and at 5 mm that crease steps; at 2.5 mm it is clean
(`blender/tests/sdf_vehicles/test_vehicles_check_scenes.py`, `sleek_wheel`).

## Live uniforms

The engine's `make()` set uniforms that `shade()` read every frame:
`uPaint`, `uRough`, `uMetalColor`, `uCamoMode` and the `uDecal` texture.
Here they are custom properties on the object, `car.object['uPaint']` and
the rest. The part materials read them through Attribute nodes (type
Object). Setting or keying one changes the render; nothing is rebuilt.

```python
car.set_paint('#ff8a1a'); car.set_paint_roughness(0.05)
car.live_uniforms['uPaint'] = 0x00e7ff        # the engine's mesh.userData.sdfLiveUniforms
jet.set_camo('desert')                        # the scheme switches per pixel, no rebuild
sleek.set_metal_color('anodized_purple')
car.set_decal_text('HELLO')                   # the badge canvas is redrawn (an image: switch it at a cut)
car.key_uniform('uRough', frame=1, value=0.6)
ctx.key(car.object, '["uPaint"]', frame=24)   # inside a harness scene: logged and made LINEAR
```

`key_uniform` keys are LINEAR, except the jet's camo. A camo scheme is a
switch (the engine set `uCamoMode` to 0, 1, 2 or 3, never between), and a
LINEAR key from silver to forest would pass through sky and desert, so its
keys hold (CONSTANT) unless `interpolation=` says otherwise.

`set_uniform` also updates the SDF program. Each object owns its uniforms,
as the GLSL original's per-instance uniforms did, so a lineup of four
liveries is four independent cars.

## The parts

Each part is one Principled material on the faces whose `map()` material id
is that part's (`car.parts['paint']`, `car.parts['glass']` ...). The
numbers are each `shade()`'s, read as physics. A mirror lookup `envR * F`
is the part's specular reflectance; the highlight exponent gives the
roughness; an unlit `emit * ...` term is emission. The hand AO, soft shadow
and sky fill are EEVEE's own light now. `vehicles/parts.py` holds the
table.

- **Car paint (modern sedan).** `uPaint` ± the engine's two-scale metallic
  fleck (`fract(sin(dot(floor(p * 320), ...)))`, per pixel), metallic 0.55,
  base roughness `max(uRough, 0.35)` (the engine's floor), and a clear coat.
  The engine's paint took its environment reflection along the mirror
  direction at every roughness, so the coat stays glossy: its roughness is
  a quarter of `paint_roughness` (0.45 gives 0.11; 0.18, factory
  semi-gloss, gives 0.045; 0 is wax). `opt_paint_roughness.png` shows the
  sweep in deep blue, where reflections read best.
- **Cyberpunk body.** The engine's body reflected `F = mix(0.04, 0.5, 0.7)`
  of the environment over a near-black diffuse. That is a dark gunmetal
  metal, here under a clear coat. The racing stripes are off-white
  dielectric decals with a faint self-light (`stripe_glow`). `uPaint` glows
  on the silhouette as `pow(1 - N.V, 4) * 0.55`, through a Layer Weight
  node: per pixel and view-dependent, as the engine had it.
- **Sleek body.** Pure metal: `uMetalColor` is F0 and goes white at grazing
  angles, roughness `max(uRough, 0.06)`. The hubcaps are the engine's hex
  tiling on the folded wheel frame: mirror cells, and a border at 0.35 F0
  and roughness 0.20.
- **Jet hull.** `_jetCamoColor` per pixel. The camo blobs are
  `smoothstep(0.50, 0.52, fbm(p * 1.6))`. The smooth fbm is stored per
  vertex (the engine's GLSL fbm, on the GPU) and thresholded per pixel, so
  the camo edges stay sharp at any distance. On top come the dark nose
  cone past z 1.5 and the wing pinstripes past |x| 0.6. The ordnance carries
  its warning bands. The plume fades from a hot white core to orange at the
  rim (`smoothstep(0, 0.7, N.V)`).
- **Glass** is a dark glossy dielectric, F0 0.08, as the engine's tint plus
  `envR * (0.08 + 0.9 fres)`: the cars have no interiors, and the windows
  read as tinted glass over a dark cabin. Tyres are rough rubber. The modern
  sedan's rims are polished alloy (metallic 0.85). Chrome is a 0.55 mirror
  on the modern sedan and a full mirror on the cyberpunk's dome hubcaps.
- **Lamps** keep the engine's view-dependent core: headlights `0.55 + 1.4
  (1 - fres)^3`, tail lamps `mix(0.7, 1.2, (1 - fres)^2)`, the sleek car's
  brighter pair, all under a clear lens (coat). The underglow and accent
  strips glow `uPaint`.

The cyberpunk's grille draws the engine's hex formula, so it glows evenly,
as it did in the engine: `hexD` never rises above 1/√3 = 0.577 between two
lattice centres, so `smoothstep(0.55, 0.78, hexD)` peaks at 0.04 and the
walls never show (`opt_grille.png`, EEVEE beside the engine's march). Its
`RIM` material id has no faces, as in the source; its material exists.

## The badge decal

`vehicles/badge.py` is `_BADGE_GLYPH_ATLAS` and `_buildBadgeDecal`: the 5×7
pixel font (`BADGE_GLYPH_ATLAS`: A, L, E, T, H, 8, P, O) drawn on the
engine's 1024×256 canvas. Each `#` is a 12 px square on a 14 px grid, with
a one-cell gap between glyphs, the line centred. A glyph not in the atlas
leaves its slot blank. A line of 13 glyphs or more runs off both edges, as
it did on the engine's canvas. Add letters to `BADGE_GLYPH_ATLAS` (seven
rows of five `#`/`.` cells) to widen the alphabet.

```python
from eidoblend.sdf.vehicles import build_badge_decal, badge_image, BADGE_GLYPH_ATLAS
canvas = build_badge_decal('ALETH8APO')   # (256, 1024, 4), row 0 at the top, white glyphs, alpha 1
img = badge_image('ALETH8APO')            # a packed Blender image (three's flipY: row 0 at the bottom)
```

The badge material unwraps the plate from the object's own coordinates, as
the shade branch did. z walks u, reversed on the right side so the text
reads left to right from outside, and the ink shows only on the outward
faces. The glyphs are white and glowing (the engine's `glyphCol` 1.4), and
stay crisp at any distance; `opt_cyber_live.png` ends on `HELLO` up close.

## The racing-stripe livery

Each of `stripeMaskFn`'s thirteen strokes is gated by one normal test:
hood, trunk and roof strokes need n.y > 0.6, the right flank's n.x > 0.6,
the left flank's n.x < −0.6. Past the gate a stroke depends only on the
position in that view's plane. `vehicles/livery.py` therefore evaluates the
engine's own GLSL on the GPU over millimetre grids, giving a side image (R
the right flank, G the left) and a top image. The paint material looks them
up per pixel by position, gates them by the shading normal and the side of
the car, and cuts them out of the wheel arches as the GLSL did. The images
are written once into `<cache_dir>/vehicles/` and named by a hash of the
GLSL. `make(pack_images=True)` packs them into the .blend. The left / right
/ top probes (`veh_cyber_v1..v3_sheet.png`) match the engine's march stroke
for stroke.

`eval_glsl(extra, expr, points, normal=None)` is the tool under it. It
evaluates an expression of `p` (and `n`) in an example's GLSL at (N, 3)
points; it also computes the jet's camo field.

## Lamps

The engine's lamps glowed but lit nothing: a raymarched SDF cannot light its
scene. `make()` parents real lights to the body at the emissive parts.

| vehicle | lamps |
|---|---|
| sedans, sleek car | two headlight spots (55-60°, aimed 5° down, warm white), two red tail points |
| cyberpunk sedan | plus two 1.9 m area lights along the rocker strips, facing the ground, coloured by `uPaint` through drivers (a repaint or a keyed livery reaches the ground glow) |
| fighter jet | an orange point behind each plume (outside the mesh, so the plume does not shadow it) |

They are set for the daylight levels eidoblend scenes use, a sun of 3 to 5
W/m². There, as on a real street, a headlight pool on the road is faint,
the underglow is a soft tint under the sills, and the afterburners warm the
ground below the nozzles. For dusk and night, raise `lamp_power`
(`make(lamp_power=8)`). `car.set_lamps(False)` hides them;
`make(lamps=False)` leaves them out. Each has a custom cutoff distance, so
EEVEE's light threshold does not cull the weak ones.

At night (`night_lamps.png`, `test_vehicles_night_lamps.py`) the
headlights throw two pools each onto the road from about a metre ahead of
the bumper, the tail lamps a red glow behind, the underglow a magenta or
cyan wash under the sills, and the afterburners a wide orange pool under
the jet's tail. Every lamp sits one to six centimetres outside its own
lamp part, so its body never shadows it.

## The baked path

`create_sdf_object(EXAMPLES['stylized_modern_sedan'])`, the engine's
`createSdfObject(EXAMPLES.stylizedModernSedan)`, builds the example like any
other SDF example. Its `surface()` is baked from the same part table, and
its patterns are in GLSL: the fleck, `stripeMaskFn`, the hex grille, the
badge texture lookup, the hex hubcaps and `_jetCamoColor`. At the vehicles'
4 to 6 mm voxels the atlas passes its budget, so the channels go on the
vertices. Patterns are therefore at vertex size: stripes and camo edges
soften, and the badge glyphs blur. View-dependent terms are taken head-on:
the rim glow is a `uPaint` sheen, and the lamps sit at their head-on
brightness. `make(shading='baked')` is the same path with `make()`'s
options. Use it where a single baked material is wanted;
`opt_cyber_baked.png` sets it beside the part materials.

## Bounds

`bounds.min` must be the shape's real lowest point. That is the engine's
own placement contract (`position.y = groundY - bounds.min.y * scale`). A
mesh also closes at its bounds, so the bounds must hold the whole shape.
Two sources broke the contract, and their bounds are corrected here:

- **Sleek car:** y −0.63..1.10 became −0.0675..1.21. The tyres are tori
  about the axle at pre-scale y 0.20, radius 0.20 + 0.045, so they bottom
  out at −0.0675. The engine's rule floated the car 0.56 m up, which shows
  in its check frames. The roof crests at 1.203, so a box ending at 1.10
  cut 10 cm off it.
- **Fighter jet:** y −0.9 became −0.7374, the bomb fins' lowest corner,
  where the old value floated the jet 16 cm. z 3.4 became 4.30. The nose
  ellipsoid's distance bound shrinks the field tenfold along its axis, so
  `smin(k = 0.6)` with the hull carries the surface out to a long point at
  z 4.294.

The engine's march walked back out of its box and drew the roof and the
nose anyway, so the corrected bounds give the shape the engine showed. The
modern and cyberpunk sedans' bounds hold their shapes (x ±0.99, y 0..1.40
or 1.446, z −2.24..2.26 inside ±1.05, 0..1.55, ±2.4) and are kept.
`place_on_ground()` seats the mesh's lowest vertex either way.

## The engine's check scenes

The WebGL engine kept eleven regression scenes with its vehicles in the
production workspace's `_reality_check`. `test_vehicles_check_scenes.py`
rebuilds them from their scripts' numbers and sets each EEVEE frame beside
the engine's (`out/engine_<scene>.png`):

- the four-example lineup;
- three palettes: four cyberpunk liveries, four sleek metals and four jet
  camos;
- the sleek car at three quarters;
- three wheel close-ups: the modern rim, the cyberpunk's chrome dome and
  the sleek hex hubcap;
- the badge close-up;
- the forest jet in the rain;
- the SDF + GLB + VRM + underwater smoke test: the neon-pink modern sedan
  and the cyberpunk sedan side by side, the red shoggoth, Aporia idling
  between them and a Poly Haven chair, under the `underwater` effect.

The placement and framing match. The chrome dome reflects the city HDRI
the way the engine's mirror lookup did. The engine frames come from older
versions of the examples than the GLSL backup: the palette's cyberpunk
bodies were then painted uPaint all over. On the two stages without an
HDRI (the badge close-up and the smoke test) the engine's `shade()` fell
back to reflecting a flat mid-grey, which lit its bodies far brighter than
those scenes' dim lights; EEVEE reflects the scene's own world, so the
bodies stay dark there. The jets' fins lean inward in the frames (see
[The four vehicles](#the-four-vehicles)). The smoke test's frame used the
WebGL `underwater` pass (bright cyan water, additive caustics; `waterY`,
`raySteps` and `depthFade` were its own options). The rebuilt scene runs
the public engine's WebGPU `underwater`, ported, with the options the two
share. Its fog thickens toward deep blue at 0.3 per metre and its caustics
multiply the lit colour, so at the scene's 9 m the sedans sit in murkier
water than the frame shows; they composite by real depth, which the
engine's march had to write itself. So the frames guide placement,
framing and character, not pixels. The cars now stand on the ground with
shadows, which the engine's could not cast. Tone mapping is AgX, not ACES.

## Tests

`blender/tests/sdf_vehicles/`. Each script's docstring gives its command,
one render at a time on a shared GPU.

- `test_vehicles_compile.py` checks the specs. Every kernel compiles; the
  surface carries the ids the part tables map; the shapes stay inside
  their bounds with `bounds.min.y` the lowest point; the jet's fins splay
  outward; and `create_sdf_object(EXAMPLES[...])` builds.
- `test_vehicles_render.py -- [vehicles=] [views=az,el,dist;...]` renders
  each vehicle at three quarters on a ground plane under a sun and the city
  HDRI, beside the engine's march from the same camera. It checks that the
  mesh is closed, the lowest point is on the ground, nothing is clipped,
  every part has faces, and the silhouette IoU against the march is 0.965
  (the jet side on) to 0.995.
- `test_vehicles_options.py` exercises every option: the colour parsing,
  the camo names, the badge canvas, the GPU evaluator against the numpy
  library, and the stripe masks at known points. It changes and keys the
  live uniforms (the camo's keys hold), redraws the badge, checks lamps and
  lamp power, two independent liveries, the `uniforms=` overrides, the
  errors, `quality` and `cells`, and the baked path. It also saves and
  reopens a .blend, which renders identically.
- `test_vehicles_check_scenes.py -- [scenes=] [t=]` rebuilds the engine's
  eleven check scenes.
- `test_vehicles_night_lamps.py` puts the four vehicles on a dark road at
  `lamp_power=8`. It checks that every lamp sits just outside its body at
  its own part, and that seen from above the headlights light the road
  ahead of each car, the underglow tints the road beside the cyberpunk's
  sills and the afterburners light the ground under the jet's tail. It also
  drives a car along keyed locations with a keyed repaint (the lamps and
  the underglow colour follow), and renders the jet from behind.

## Not yet ported

- **Features closer than a voxel or two.** The mesh holds one surface
  vertex per voxel. Where two features come closer than about two voxels,
  the crease between them steps at the voxel size. The sleek car's hubcap
  rim, 7.5 mm inside its tyre, steps at 5 mm and is clean at 2.5 mm; the
  same 5 mm render in one grey material shows the step too, so it is the
  geometry. Where two parts meet at a concave crease (a handle on a door),
  the material edge follows the mesh faces. Both show only in macro shots,
  which want `voxel=`. The engine resolved both per pixel.
- **The wheels do not turn.** As in the engine, each vehicle is one SDF and
  one mesh: a car keyed along a road slides. Turning wheels need the wheels
  as SDFs of their own.
- **The baked path's patterns are at vertex size.** See
  [The baked path](#the-baked-path).
- **The jet rain scenes have no world rain.** Their world rain was the
  WebGL engine's `depth_rain` pass (streaks by depth, puddles, splashes),
  which the public WebGPU engine dropped: `effects_tsl/` has only
  `rain_on_camera`, and its world rain is the weather system's
  (`eidoblend.weather`). So `sdf_jet_rain` renders with `rain_on_camera`
  alone, whose WebGPU edition blurs the frame behind its drops (the WebGL
  one did not), and `sdf_jet_rain_only`, the jet under `depth_rain` alone,
  is not rebuilt.
- **Lamps are not animated.** None of the engine's vehicles animated their
  lamps either. Key `lamp.data.energy` or `car.set_lamps()` at a cut.
