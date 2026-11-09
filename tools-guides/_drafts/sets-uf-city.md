# The UNKNOWN FORCE city and the hole

[Props and sets guide](../props-and-sets.md) · [The WebGPU doc](../../eidoverse/sets/unknown_force/CITY_HOLE.md) · [Set index](../../eidoverse/sets/unknown_force/README.md)

This is the Blender 5.2 EEVEE edition of UNKNOWN FORCE's exterior world: **`city`**, a dark cyberpunk
megacity at night painted by a Futurist, **`hole`**, THE HOLE IN THE MIDDLE (a stage at the bottom of a
sunken well at its centre), and **`citykit`**, the kit they share (`blender/eidoblend/sets/unknown_force/`).
They were made for the UNKNOWN FORCE music video and are free sets for any piece. The port is line for
line from `city.js`, `hole.js` and `citykit.js`: the same seeded plan (1908 buildings, 4446 signs, 1967
lamps, 2161 cars, bit for bit), the same materials as shader nodes, the same canvas art, the same camera
moves. The package's `__init__.py` is the registry of every UNKNOWN FORCE set.

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sets import unknown_force as UF
from eidoblend.sets.unknown_force import citykit as KIT, city as C, hole as H

scene = bpy.context.scene
KIT.eevee_settings(scene, samples=32)          # EEVEE, AgX, screen-traced reflections, no fast GI
city = UF.build('city', scene)                 # ~27 s; the hole is inside it: city.parts.hole
city.parts.apply_atmosphere(scene)             # the city's World: the night sky, its hemisphere, its environment

cams = city.make_cameras()                     # the dive (Crali's, 40.8 s = 980 frames), keyed from frame 1
city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(1, 980))   # the clock, the focal light, the rain
```

`make_cameras` keys the dive on a new camera (location, quaternion, lens; near 0.25 m, far 6 km, as the
engine's) and binds it to a timeline marker; `animate` keys the set's moving parts on your own clock: the
clock (two LINEAR keys, linear extrapolation: t = (frame − first) / fps from then on), every control the
state function names, and the rain's streaks along the camera that renders each frame. Nothing runs per
frame at render time: a saved `.blend` plays and renders any frame on its own.

## The registry and the harness

`eidoblend.sets.unknown_force` imports no set. A set's module loads on first use, so building the city
never pulls in the race, and a set still being ported never breaks the others.

```python
UF.names()          # ['city', 'quiet_room', 'hole', 'corridor', 'race', 'showroom', 'news', 'bin']
UF.available()      # those whose module is on disk
UF.module('hole')   # the module (also UF.hole); the shared libraries too: UF.citykit, UF.cn_lib ...
UF.build('bin', ...)                    # = UF.module('bin').build(...)
UF.SETS['race']     # {'module', 'doc', 'focal', 'libs', 'what'}
UF.doc('hole')      # the WebGPU doc (its options and costs)
```

`build(first, opts, ctx=None, **kw)` takes the harness ctx, a bpy Scene or city.js's opts dict first, so
the family registry builds it as any other set, and every key the set makes then goes through `ctx.key`
(and its cuts through `ctx.cut`):

```python
from eidoblend import sets
def setup(ctx):
    city = sets.build('unknown_force.city', ctx, rain_count=26000)     # = C.build(ctx=ctx, rain_count=26000)
    city.parts.apply_atmosphere(ctx.scene)
    city.make_cameras()                                                # cut at frame_start, keyed through ctx.key
    city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(ctx.scene.frame_start, ctx.scene.frame_start + 979))
```

The set is a dict whose keys also read as attributes (`city.parts` is `city['parts']`); so are `parts`,
`parts.lights`, the plaza screen, every billboard and every ticker, as the engine's objects were. A key
wins over a dict method of the same name: `city.update(t, state)` is the set's update.

## One world frame

The mark at the bottom of the hole is the origin; its floor is z = 0 and **the city's streets are at
z = `STREET_Y` = 12 m**. Both sets are built untransformed in that frame: the dive, the hole's camera
moves and the static views share it. In Blender axes the mark faces −Y (three's +Z). Every pose, focal
point, light and object comes out in Blender axes; inside the kit the layout code still works in
three's axes, so its numbers port as they were (a point is converted once, when a mesh is made:
three (x, y, z) → Blender (x, −z, y)). `RIM`'s angles are in three's ground plane.

The set holds `group` (the root Empty, `set:city`, with `set:hole` under it), `collection`, `parts`,
`update`, `dispose`, `cams`, and the Blender additions `animate` and `make_cameras`.

| `city.parts` | |
| --- | --- |
| `meshes` | `uf_towers_concrete`, `uf_towers_metal`, `uf_frames`, `uf_strips`, `uf_far`, `uf_street`, `uf_blocks`: the merged buildings (each quad its own vertices with the `aT`/`aM`/`aW` colour attributes), the far skyline, the street disc, the raised blocks |
| `signs` | one mesh, one quad per sign (4470: the city's and the rim towers' outward ads and walls), UVs into one atlas |
| `lamps`, `traffic`, `rain`, `clouds` | the lamps (one mesh), the cars and the rain (Geometry Nodes per frame), the 13 cloud sheets |
| `plaza_screen` | the LED floor at the dive's crossing (below) |
| `sky`, `lights`, `wet_floors` | the World; `{'hemi': the World, 'moon': the sky-glow sun, 'moon_wet': its twin for the wet floors}`; the wet floors' collection (below) |
| `kit`, `uniforms`, `fog_node`, `fog_factor`, `fog_color` | the Kit, its uniforms (`K.U`), the fog group and its two outputs |
| `set_lights`, `set_focal`, `apply_atmosphere` | below |
| `plan`, `atlas`, `stats`, `hole`, `billboards` | the city plan, the sign atlas (`items`, `image`), counts and build time, the hole, its screens |

`city.js`'s other exports are here under their snake_case names: `plan_city(seed)`, `emit_building(lot,
ctx, over)` (over: `height`, `lean`, `style`, `type`), `sign_at`, `draw_plaza_sun`, `dive_cam`,
`dive_focal`, `DIVE_AV`, `DIVE_C` (the dive's crossing in Blender axes, (116.7, −116.7, 12); `DIVE_C3` is
city.js's three-axis one), `apply_camera`; the kit's `GeoBuf`, `make_xf`, `frame_attrs`, `rng`,
`hash1`, `keyed`, `nearest_avenue`, the materials (`facade_material`, `ground_material` ...), the canvas
(`make_canvas`, `make_sign_atlas`) and the systems (`make_rain`, `make_clouds`, `make_traffic`,
`make_lamps`) work alone too.

## The controls: the kit's uniforms

`K.U` is one node group (`uf_city_U`) of Value nodes every material reads; set them, or key them so
the `.blend` carries them (`animate` below keys them for you). Vectors are in Blender axes.

```python
U = city.parts.uniforms
U['power'] = 1.0; U.key('power', frame=700)               # all lit ...
U['power'] = 0.15; U.key('power', frame=1276)             # ... then the city goes out light by light
U.key('flash', 1200, 1.0); U.key('flash', 1203, 0.0)      # lightning on the cloud deck
city.parts.set_focal(H.chest(), {'gain': 1.0, 'radius': 230}, frame=1500)   # Crali's light from the mark, keyed
ctx.key(*U.paths('wet')[0])                               # the harness keys them too (tree, data path)
```

| Uniform | Effect |
| --- | --- |
| `power` | 1 = every light on; lower it and the city goes out light by light (windows, signs, strips, lamps, cars, floods, crowns, screens, tickers each at their own threshold); the street light fades as a whole; the quiet ring and the pillar stay |
| `win`, `neon`, `street` | window emission; signs and neon strips; lamps and the street light map |
| `rain`, `cloud`, `fog`, `wet` | rain amount; the cloud deck's opacity and fog; the haze; puddles and gloss |
| `flash` | lightning on the deck (the clouds, the sky and the haze) |
| `focal_pos`, `focal_col`, `focal_gain`, `focal_r` | Crali's light: faces turned toward the focal point light up (keep it on the post's focal) |
| `flood`, `crown` | the per-tower coloured floodlights; the lit crowns |
| `cable`, `column`, `screens`, `quiet` | the hole's cable pulses, the pillar of light, the screens and tickers, the quiet ring |
| `time`, `cam_vel` | the clock (seconds) and the camera velocity the rain streaks along (`animate` keys both) |
| `pix` | radians per pixel of the active scene camera (a driver; the windows' and lines' filtering) |

camelCase names (`focalPos`, `camVel` ...) are accepted as aliases. `update(t, state, frame, ctx)` sets
the clock, the rain's velocity (`state['cam_vel']`, or a `state['camera']` differenced between calls)
and any control the state names (`'power'`, `'focal'` ...), and keys them when given a frame; without
a frame it is a still. `set_focal(pos, {gain, radius, color}, frame=)` takes city.js's options dict (or
the same as keywords).

## Moving parts on your own clock: `animate` and `make_cameras`

`animate(state, frames, t0, fps, camera)` keys the set's moving parts over frames (both sets have it):

- **the clock** drives the rain, the traffic, the signs' flicker, the plaza's turning sun, the tickers,
  the cables' pulses: `t0` seconds at the first frame, then real time (or a `'time'` of your own in the
  state, for a slowed or held clock);
- **`state(t)`**, a function of those seconds (or one dict for every frame), names any control: the
  uniforms above, `'focal'` (a point, or an object whose position is followed), `'focal_col'`
  (RGB or `'#hex'`), `'cam_vel'`. Each is keyed where its value changes, so a hold costs two keys and a
  step stays a step;
- **the rain's streaks** follow the camera that renders each frame (the camera markers, else the
  scene's camera; `camera=` names one, `camera=False` leaves `cam_vel` alone).

`frames` is `(first, last)`, a range or a list (default the scene's range); `animate(range(...))` with
the frames first works too, as the other sets take it. `C.turn_down(t, start, length=24, to=0.15)` is the
city going out light by light (power `1 − (1 − to) · smooth((t − start) / length)`): each window, sign,
strip, lamp, car, flood, crown and screen at its own threshold, the quiet ring and the pillar staying.

```python
cams = city.make_cameras()                                # the dive from frame_start (its own 40.8 s)
city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(1, 980))
city.animate(lambda t: {'power': C.turn_down(t, 4.0), 'focal': H.chest()}, frames=(2000, 2720))
city.animate(lambda t: {'flash': 1.0 if 2.0 <= t < 2.12 else 0.0}, frames=(3000, 3100))   # a lightning strike
city.animate({'focal': lantern_empty}, frames=(4000, 4240))   # the focal light follows an object
cams = city.make_cameras(shots=[('spiral', 5000, 5288), ('closeSing', 5289, 5528)])   # the hole's moves, cut

stage = bpy.data.scenes.new('uf_stage')                   # the hole alone, in a scene of its own
KIT.eevee_settings(stage, samples=32)
hole = UF.build('hole', stage)
hole.parts.apply_atmosphere(stage)
reel = hole.make_cameras()                                # all eight camera moves back to back, cut by markers
hole.animate(lambda t: {'focal': H.chest(), 'quiet': 1.0})
```

`make_cameras()` without shots keys the dive (`t0` starts it partway); with shots `[(name, first,
last)]` it keys one camera per move of the hole, stretched over its frames, and binds each to a timeline
marker at its first frame.

### Several sets in one file

Every set builds its own kit, and every datablock a kit makes is its own: materials, the uniforms
group, the fog group, the Geometry Nodes trees, the canvases, the light map and the World. A second
set in the same file (the standalone hole beside the city, a city with another seed) gets new
datablocks, named with Blender's `.001` where the first set holds the name, and leaves the first set's
materials, keys and World alone; its own World waits for its `apply_atmosphere`. The five texture files
are shared: `dispose()` removes one only when no other set still uses it. The standalone hole stands
where the city's own hole is, so put it in a scene of its own (above) unless you build the city with
`hole=False`.

## Cameras

`dive_cam(t)` is the dive (`t` seconds into it, 0..40.8): Tullio Crali's *Incuneandosi nell'abitato*,
from the low rain clouds to a spiral down the towers and the pull-out down avenue 45° to the hole.
`hole_cam(name, t, opts)` gives the hole's eight camera moves (made for the film's choruses), `t`
seconds into the move (`opts['dur']` stretches it; an unknown name gives `closeSing`, as the engine's).
Both return `{'pos', 'target', 'fov' (vertical degrees), 'roll', 'up'}` in Blender axes;
`apply_cam(camera, pose, frame=None, keyer=None)` places (and keys) a camera, `key_dive(camera, K,
frame_start, fps)` and `key_hole_cam(camera, name, frame_start, fps, dur)` key a whole move,
`cam_velocity(fn, t)` differences any pose function, and `dive_cam_three` / `hole_cam_three` give the
engine's three-axis poses.

| `hole_cam` | Length | Move |
| --- | --- | --- |
| `spiral` | 12 s | a Crali dive down the well toward the performer's face, circling 540°, ends a close-medium at 2.25 m |
| `riseUp` | 12 s | from the face straight up the well to 190 m, looking down: the mark becomes the vanishing point |
| `closeSing` | 10 s | the close-up, a slow ±14° arc in front of the mark |
| `orbit` | 16 s | a full circle at 8.5 m |
| `low` | 10 s | from the floor between two cables, looking up past the mark at the leaning crown and the screens |
| `nadir` | 10 s | straight down from 70 m to 13 m, slowly turning |
| `screens` | 10 s | from beside the mark, a tilt up across the screens aimed at it |
| `enter` | 8 s | from the dive's last frame down the avenue, over the rim, down into the well |

The hole's moves are framed for a performer at scale 1 on the mark (face at 1.55 m); for a smaller one
set `H.HEAD[2] = 1.55 * 0.87` before building (the screens aim at it; `H.chest()` follows it).
`city.cams` holds static poses (`dive_clouds`, `dive_crali`, `dive_canyon`, `dive_end`, `avenue`,
`skyline`), `hole.cams` the hole's moves at mid-move. The numbers are the engine's own (the parity test
compares them), and the render test keeps the engine's promises: the dive never comes within 14 m of a
surface, the hole's moves stay 0.3 m clear of every surface and 0.74 m clear of the cables.

## Screens, tickers and the plaza

Every screen is canvas art (a canvas-2D context on numpy and Pillow, with the kit's nine bundled
faces), packed into the `.blend`.

```python
b = city.parts.billboards[3]                   # 12 screens, 18 x 10.125 m, aimed at the performer's head
b.set_canvas(lambda ctx, w, h: H.draw_camp_screen(ctx, w, h, H.CAMPS[7]))          # a still (1024 x 576)
b.set_canvas(draw, frames=range(1700, 1820), fps=24, out_dir='//uf_screens')       # draw(ctx, w, h, t): a keyed PNG sequence
b.reset()                                      # back to its camp
t = city.parts.hole.parts.tickers[0]           # the four riser rings, scrolling round the mark
t.set_items([['SHE IS A GOD', '#ff2a3a'], ['SHE WANTS OUT', '#ff8a3d']])
t.speed.default_value = -0.02                  # a keyable socket (so is t.gain, b.gain)
city.parts.plaza_screen.set_canvas(title_draw, frame=760)    # the LED floor at the crossing (1024²), from frame 760
city.parts.plaza_screen.reset(frame=880)                     # Balla's sun again from frame 880 (a keyed step)
```

A redrawn canvas is a PNG sequence (redraw at ≤ 15 fps or on cuts, as the engine advised), loaded with
the media family's sequence loader: a hold file before its range, the last file after it. `out_dir` may be
blend-relative, as the media family reads it: `'//uf_screens'` is beside the saved `.blend` (in a file
not saved yet, under the working folder). The plaza's
default (Balla's sun turning, a ring of slogans) is not a sequence: its rays and slogans are drawn once
and turned in the shader on the keyed clock at the engine's 10 redraws a second, its rings and core are
drawn analytically (the canvas test checks the composite against `draw_plaza_sun`).

## Light and atmosphere

- **The World** is the night: camera rays see the dome's colours (overcast above, the haze colour at the
  horizon, the flash); lighting and reflections see the city's dim hemisphere (three's
  `HemisphereLight(0x1d2a3a, 0x2a160c, 0.55)`) plus the night the glass reflects (`envNode`, the
  facades' 0.32: `env_intensity`). Like three's hemisphere, the World casts no shadow: no sun is
  extracted from it (EEVEE's default, a 1 mm sun shadow over a 6 km city, overflows the shadow pool).
- **The sky-glow** is a sun without shadows (`city.parts.lights.moon`). The wet floors take it from a
  twin, `lights.moon_wet`, whose specular is 0.04 / 0.9 (its energy and colour are driven by the
  sky-glow's, and it turns with it): three's lit materials took direct light with F0 0.04, while here the
  floors' reflectivity (street 0.22..0.9, the hole's marble up to 0.78: the G-buffer value the engine's
  SSR read) is their Principled IOR, so the full sky-glow glinted up to 22 times too bright wherever a
  puddle mirrored it, a field of white-blue specks in every view looking down at 60 to 70 degrees. The
  twin lights the street and the blocks (`city.parts.wet_floors`) and the whole hole; the sky-glow
  lights the rest. Put your own wet floor in `wet_floors` to give it the same.
- **The haze** lives in the set's own materials (the `uf_fog` group: the height-graded haze and the
  cloud deck, lit from below by the street). three's `scene.fogNode` fogged every material in the scene;
  here `apply_atmosphere(scene, objects=meshes)` wraps your own objects in the same haze
  (`KIT.fog_objects`; `KIT.unfog_material` takes it out). Seen from the top of `riseUp` (190 m up the
  well) a performer on the mark is a quarter fogged (factor 0.26), as in the WebGPU engine.
- **The hole's lights** (`hole.parts.lights`: `ring`, `screen0..3`, `kickL`, `kickR`) are light
  linked, as the engine's light lists were: the quiet ring lights the hole and the performer, the
  screens and the neon kickers light **the performer only**. Put the performer's meshes in
  `hole.parts.her` (a collection outside the scene; linking there does not render them twice). The
  screen and kicker lights also exclude the set's own collections, so with nobody on the mark they
  light nothing of the set (light linking ignores an include that holds no objects; without the
  exclusion the 1500 cd screen lights would wash the rim towers and the street in their colours).
  Keep the performer in a collection of your own, not inside `set:city` or `set:hole`.
- `set_lights(list)`: the set's surfaces see only these lights (and the World); every other scene light
  excludes the set's collection, and a listed light that was excluded before lights it again. Call it
  after adding lights (a key and rims on a performer). Both sets call it when they are built, as the
  engine's `setLights` did: the city with its sky-glow, the hole with `city_lights` (the city passes
  the sky-glow's wet twin; a standalone hole has none: its hemisphere is the World), so a light already
  in the scene before the build does not reach their surfaces. A light that lights only what it
  includes (the twin) takes a collection back as an include when `set_lights` lists it again.
- **Units.** Lights keep three's balance against emission, which is what the city's look was tuned on:
  a point light of `cd` candela is `4π cd` W, a directional light's lux is a sun's W/m² (`light_scale`
  scales them all; `1 / 683` gives the glTF importer's photometric reading). three's decay and distance
  window are folded in at a performer's chest on the mark, and its distance is the light's custom cutoff.
- **Crali's light.** The kit's default is gain 1 over 230 m from (0, 0, 3), the hole. For a dark,
  moody well the WebGPU probe stage lit the dive at gain 0.6 and the hole from (0, 0, 3) at gain 0.35
  over 70 m, which keeps the rim towers dark round the screens; the render test lights its stills that
  way so they compare with the probe stage's stills. Gain 1 on `dive_focal` or `H.chest()` is the
  brighter, warmer reading.

## The windows, as the film rendered them

Every window's lit state, colour, curtains and flicker, and every tower's floods, crowns and tint, come
from citykit.js's `hash12`. The JS writes Dave Hoskins' hash, but its `p3.addAssign(...)` runs outside a
`Fn()`, where three r184 skips the assignment (the film's probe logs carry `No stack defined for assign
operation` at `citykit.js:256` for every call). So every frame of the film was rendered, and its windows
tuned, on `fract((a + b) a)`: lower than uniform on average (mean 0.37), with whole columns of windows
lit or dark. The kit renders that by default; the kit or build option `hash='hoskins'` gives the hash
as the source reads.

| Per window | the film's hash (`'film'`) | as written (`'hoskins'`) |
| --- | --- | --- |
| lit, at a lit fraction of 0.10 / 0.18 / 0.26 | 18 / 28 / 37 % | 10 / 18 / 26 % |
| warm, at a warmth of 0.3 / 0.55 / 0.8 | 48 / 72 / 89 % | 30 / 55 / 80 % |
| columns lit on ≥ 80 % of their floors / never lit (lit fraction 0.2) | 20 / 18 % | 0 / 0 % |

```python
city = UF.build('city', scene, hash='hoskins')     # the source's hash: sparser, cooler windows, no lit columns
```

The windows are box-filtered by their footprint on screen, as the engine's `fwidth` did: close up, each
window resolves its frame, a mullion and a transom; far away it converges to its building's average.
The footprint is what the GPU measured on a plane (`KIT.pixel_steps`: where the next pixel's view ray
meets the face), so the panes resolve where the film's resolved them.

## What EEVEE receives

| WebGPU | Blender |
| --- | --- |
| TSL node materials | shader node trees written by `NB`, an expression layer (`+ - * /`, `mix`, `smoothstep`, `step`, `fract`, `hash12`, `pulse` ...) that writes the TSL maths as nodes, constant-folded; `tsl_helpers(nb)` hands out the three helpers by their engine names |
| `hash12` (every window's lit state, colour, curtains and flicker; the floods, crowns, tints; the rain rings; the signs' buzz) | the hash the film rendered with: `fract((a + b) a)`, `a = fract(x · 0.1031)`, `b = fract(y · 0.1031)` (below) |
| `fwidth` on the facades (the windows' box filter, their frames and mullions, the far average) | what the GPU measured on a plane: where the next pixel's ray meets the face (`pixel_steps`: the camera's axes, the depth, `pix`), along the face's UV tangent and bitangent |
| `fwidth` of the lane paint and the LED grids | the view distance times `pix` over the foreshortening |
| `U.*` uniforms | `uf_city_U`, keyed Value nodes; Geometry Nodes read them through drivers |
| `scene.fogNode` | the `uf_fog` group (factor, colour) mixed into every set material, as three mixed the fragment; additive materials fade by 1 − factor; your own objects through `apply_atmosphere(scene, objects)` |
| the vertex stage (rain, traffic, cables) | Geometry Nodes per frame from the keyed clock and the scene's active camera |
| MRT `metalrough` (the puddles' SSR reflectivity) | the Principled IOR (F0 = the reflectivity) under ray-traced reflections; the sky-glow reaches the wet floors through its twin at specular 0.04 / 0.9, so its glints keep three's F0 0.04 |
| three's lighting model (`getRoughness`: roughness at least 0.0525) | the same floor on every lit material (`KIT.ROUGHNESS_FLOOR`) |
| canvas textures | packed images, the right way up (RGB and alpha channel-packed; the materials multiply by alpha as three did) |
| `lmSample(…, level)` | the light map and its blurred levels 1, 2, 4, 5 as images, averaged in linear light |
| the clouds following the camera (`update(camera)`) | the 13 sheets (4.8 km, as the engine's) ride the scene camera in x and y by drivers on the active camera, evaluated every frame and across cuts; the noise stays fixed in the world (`follow=False` keeps them still) |
| the sky dome | the World |
| `envNode` per material (0.32 facades, 0.85 street, 1.0 marble) | one World environment at `env_intensity` |
| `lightsNode` lists (`setLights`) | light linking (receiver collections) |
| `userData.noSupportCheck` … | the audit flags as custom properties (`no_support_check` …) |

## Render settings and costs

`KIT.eevee_settings(scene, samples)` sets EEVEE, AgX, screen-traced reflections up to roughness 0.5
and no fast GI (the engine had none). The WebGPU post (bloom 0.55 / 0.5 / 0.7, aeropittura) is the
look's, not the set's; the render test's `--bloom` adds it through the look family's chain
(`eidoblend.look.post.chain.set_bloom(scene, strength=0.55, size=0.5, threshold=0.7)`, the compositor's
Glare on scene-linear light before AgX, as three's bloom ran before its tone map).

Measured on the RTX 5090 Laptop shared with other jobs: building the city with the hole takes 15 to
27 s (the plan, 1908 buildings, the sign atlas, the light map and the canvases, in Python; the engine
built in 1.6 s), the hole alone about 14 to 21 s (with its own kit, sign atlas and extras). A 960 × 540
still at 16 samples renders in 0.6 to 1 s in the city and in the standalone hole once the shaders are
compiled (the first still of a session takes 4 to 6 s). The merged buffers hold
533 k vertices (concrete 109 k, metal 45 k, frames 327 k, strips 41 k, far skyline 10 k), the rain
104 k (26 000 streaks) and the cars 17 k, both rebuilt by Geometry Nodes each frame from the keyed clock.

## Tests

`blender/tests/sets_uf_city/`:

- `parity_dump.mjs` + `test_parity.py` (no GPU): the kit against the WebGPU originals, number for
  number (45 checks: the plan, every building and sign, the buffers, lamps, traffic, the far skyline,
  the dive and the hole's camera moves, the rim towers, the cables, the noise and environment textures, the
  atlas packing).
- `test_canvas_art.py` (no GPU): the camp screens, tickers, the plaza sun against its decomposition,
  the light map.
- `test_hash_film.py` (no GPU): `hash12` / `hash11` written as nodes, evaluated by Geometry Nodes on
  100 000 window cells, against the film's formula and Hoskins' (both modes); the lit, warm and column
  statistics the film's hash gives the facades.
- `test_window_footprint.py`: the facades' `fwidth` against the truth (rays through a pixel and its
  neighbours on the same quad) at the dive's 16 s and 40.8 s cameras, as numpy (no GPU) and, with
  `--render`, from the material itself through the AOV `uf_window_fw` (the kit's `aovs` option).
- `test_two_sets_one_file.py` (no GPU): the city and the standalone hole in one scene, two cities with
  two seeds, disposing one of them, the hole's light restriction (`city_lights`, `set_lights`), a canvas
  sequence into `'//uf_screens'`.
- `test_build_options.py` (no GPU): the build options (`hole`, `seed`, `rain_count`, a shared kit,
  `city=True` on the hole, `emit_building`'s overrides), `dispose`, the plaza's and tickers' canvases,
  `set_lights`, `set_focal`, `update` (a still's controls too); then the family registry with a harness
  ctx: keys through `ctx.key`, `make_cameras` (the dive, the hole's moves, cuts), `animate` on its own
  clock (the focal light on the dive's, the rain along the marked camera, `turn_down`, a flash kept a
  step, a followed object, an unknown control refused), the plaza's keyed step, and the standalone
  hole's eight-move reel and clock.
- `test_city_render.py`: the build checked (counts, buffers, Geometry Nodes after evaluation, the
  keyed dive, the pixel-angle driver, the cloud deck riding the camera, light linking (the
  performer-only lights never reach the set), camera clearances), then stills of the set from the dive,
  the city's views, the hole's moves and a turn-down keyed by `animate`, lit as the WebGPU probe stage
  lit its stills; `--sweep` renders one view per uniform, `--her` (`--vrm`) puts a performer on the
  mark in the haze, idling, and `--compare` writes `compare_<shot>.png`: the probe stage's WebGPU still
  beside the render.
- `test_hole_render.py`: the hole alone, the registry, the screens' and tickers' API, the
  performer-only lights, a keyed camera move, the eight stills; `--compare` pairs `low` with the probe
  stage's standalone-hole still.

Run the Blender ones through the GPU slot from the main checkout:
`HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <test>`.

## Not yet ported

- **Per-material environment strength.** The engine gave each lit material its own `envMapIntensity`
  (facades 0.32, street 0.85, marble 1.0, paving and lamps 0.6); EEVEE has one World, set at the facades'
  0.32 (`env_intensity`). The wet street and the marble reflect less of the night sky where no geometry
  is on screen to reflect; ray-traced reflections of the city itself are unaffected.
- **The engine's SSR.** The puddles' G-buffer reflectivity becomes the Principled IOR under EEVEE's
  screen-traced reflections, which reach the whole frame (the engine's SSR stopped at 140 m, at half
  resolution). Where a wet floor mirrors the sky-glow, its twin keeps the glint at three's F0, but
  EEVEE draws it as a small cluster of bright points where three spread it into a faint haze (three
  added no specular anti-aliasing for normal maps either; its glint was dimmer per pixel).
- **The cloud deck at a grazing distance.** At the dive's end, looking down the avenue at the pillar
  of light, the far cloud sheets read as a dark mottled veil behind the pillar; the WebGPU still shows
  an even bright haze there, and the render with the clouds off matches it. The likely cause is
  texture filtering: three sampled the cloud noise through isotropic mipmaps, which average it to a
  smooth veil at that angle, and EEVEE keeps its detail. Not yet emulated (pre-blurred noise levels
  chosen by the pixel footprint would do it).
- **Skia's canvas.** The canvas art is drawn by the numpy and Pillow canvas (interiors_lib's `Context2D`
  plus the kit's shadows) from the same TTFs: layouts match, but the glyphs' anti-aliasing and the
  neon glow's blur are not Skia's, pixel for pixel.
- **The haze on see-through materials.** `fog_objects` leaves blended and alpha-cut materials (decals,
  hair cards) out of the haze; three fogged them too.
- **Tone mapping.** The port renders AgX (the family's contract); the WebGPU engine used three's ACES Filmic
  (with its 1 / 0.6 exposure lift), so midtones sit a little lower and saturated neon a little paler.
- **The WebGPU post.** Bloom is the compositor's Glare in the render test only; aeropittura is the look
  family's.
- **The engine's own open items** stay open here: the rooms behind the windows have no depth (no
  interior mapping: a window close up is its frame, mullion, curtain and furniture band on one plane),
  and the cloud phase reads as murk with the city glowing through rather than wisps rushing past. The
  shadow-map shader errors do not occur (the city's lights cast no shadows).
