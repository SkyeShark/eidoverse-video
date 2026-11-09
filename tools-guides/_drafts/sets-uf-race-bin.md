# UNKNOWN FORCE sets: the race and the bin (Blender edition)

[Props and sets guide](../props-and-sets.md) · [The WebGPU sets](../../eidoverse/sets/unknown_force/README.md) · [RACE.md](../../eidoverse/sets/unknown_force/RACE.md) · [BIN.md](../../eidoverse/sets/unknown_force/BIN.md)

This is the Blender 5.2 EEVEE edition of two sets made for the UNKNOWN FORCE music video: the race (`race.js`), a wet
night highway with two billboards and a 1908 racing car that crashes into a drain, and the bin (`bin.js` with its page
atlas `bin_pages.js`), a canyon of thrown-away paper with a giant trash can. They are free assets for any new piece.
Each is a Python module in `blender/eidoblend/sets/unknown_force/` that builds the whole set in the open scene, keys
its moving parts on your own clock, and hands back its parts, its cameras and its focal points. Everything is built in
code from the same numbers as the WebGPU sets: the race loads no file at all; the bin loads one CC0 model (Poly
Haven's "Metal Trash Can", through the shared library) and the kit's bundled fonts.

| Module | What it builds | WebGPU source |
| --- | --- | --- |
| `race.py` | the elevated wet highway, Sant'Elia towers, two billboards with the machine-god face, Marinetti's 1908 car with two riders, the roadworks, the crash into the drain, the march's shadows, the heel on the manifesto, rain, splash and steam | `sets/unknown_force/race.js` |
| `bin.py` | the paper canyon, the giant stickered trash can, 3,943 sheets, 300 crumpled boulders, the collage underlayer, the typographic fragments and cut shapes, 200 falling sheets, Balla's street lamp | `sets/unknown_force/bin.js` |
| `bin_pages.py` | the 24 invented pages of the bin's atlas (newspapers, forums, sermons, a manifesto, an open letter, a memo, a chat log, a chart, an ad, notes, classifieds, a poster, six Futurist cut papers), and `Canvas2D`, the canvas-2D context the race and the bin draw on | `sets/unknown_force/bin_pages.js` |

Both sets work in Blender's axes: three's set-local `(x, y, z)` is Blender's `(x, -z, y)`, so each set's performer
mark faces −Y (three's +Z). Their tables of numbers (`race.LAYOUT`, the cameras in `race.CAMS`) stay in race.js's own
numbers so they read against RACE.md; every position the modules return is in Blender's axes. Park a set anywhere:
everything reads set-local coordinates, so a moved set renders the same pictures from its own cameras.

## The race

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import race as R

scene = bpy.context.scene
scene.render.fps = 24
race = R.build()                              # or R.build(ctx) in a scene script: its scene, keyed through ctx.key

# twelve seconds on my clock: the gold screen powers on, the car reaches the broken edge at 8 s and goes over,
# the floodlight's march comes up at 9 s, the boot strikes at 11 s
events = dict(bill_a_on=(0.0, 0.8), glance_from=1.0, car_edge=8.0, march_on=(9.0, 9.6), heel_strike=11.0)
frames = (1, 12 * 24)
race.animate(frames, t0=0.0, state_fn=lambda t: R.sequence(t, **events))      # update() KEYED every frame
race.make_cameras([(0.0, 'billA'), (3.0, 'carPass'), (5.0, 'carTrack'), (7.6, 'crashLow'), (9.0, 'shadows'),
                   (10.4, 'heel')], frames, t0=0.0, state_fn=lambda t: R.sequence(t, **events))
print(race.apply_render_settings(scene))      # AgX, ray tracing, bloom, the set's fog, the set's world
```

`R.build(ctx, **opts)` takes race.js's options in snake_case: `reflect` (the wet road's planar mirror), `reflect_scale`,
`sky` (the set's night world), `towers`, `rain`, `rain_count` (5200), `lamp_i` (140, the sodium heads' intensity),
and, for a new piece, `amounts`: the text in the two screens' bands, gold then red (race.js's own `'$100,000,000'`
and `'$20,000,000'` by default), drawn in the same Impact band under the same face.

`make_cameras(cut, ...)` takes the cut as `[(t_start, camera), ...]` on the same clock, or a function `cut(t)`; it
makes one camera per shot, keys it every frame of the shot (the car cameras follow the car), and binds it to a timeline
marker at the cut. Or key it frame by frame:

```python
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
for f in range(1, 1 + 6 * 24):
    t = (f - 1) / 24
    st = R.sequence(t, car_edge=5.5, rain=0.6)                # the car on its own clock; any update() key passes through
    race.update(t, st, frame=f)                               # sets and KEYS the frame
    race.key_camera(cam, 'carTrack' if t < 5.3 else 'crashLow', t, st, frame=f)
race.finish()                                                 # keys LINEAR, visibility switches CONSTANT
```

`update(t, state, frame)` takes race.js's state keys in snake_case (`car_t`, `car_s`, `car_v`, `crash`, `car`,
`headlamps`, `bill_a`, `bill_b`, `billboards`, `gaze`, `march`, `march_t`, `heel`, `rain`, `wet`, `lamps`,
`back_rim`; RACE.md's table says what each drives) and keys every transform, light level and shader uniform it
changes at `frame`, so the saved .blend plays and renders any frame by itself; `frame=None` sets without keying (a
still). `t` is your clock: it runs the rain, the screens' flow and tearing, the engine's shake and, unless `march_t`
is given, the column's lockstep. Built with the harness's ctx, the keys go through `ctx.key` and the runner gives them
their interpolation. The set is also readable as the sets' dict contract: `race['group']`, `race['update']`,
`race['parts']`.

The moving parts have their own time controls (pure Python, the formulas race.js's cut used): `ease_in(t, t0, t1)`
(a screen powering on, the march coming up), `glance(t, t0)` (the irises swinging across), `car_drive(t, t_edge,
speed=22)` (the run to the broken edge, then the 3 s crash: nose in at 0.437, on its back by 0.65, settled by 0.9)
and `heel_stamp(t, t_strike)` (the boot comes down, hovers, strikes the page at `t_strike`, the toe slaps down).
`sequence(t, bill_a_on, bill_b_on, glance_from, car_edge, car_speed, march_on, heel_strike, **keys)` combines them
into one state; every part is optional.

`race.set_active(False, frame)` parks the set outside its section: every mesh hidden and every light at 0, keyed as a
step at `frame`, so the frames before it still show the set and the lights stay off until `set_active(True, frame)`
and the next `update()` bring them back. Park it wherever another set is on screen, because its lights reach anything
in range. `race.dispose()` removes everything it made (objects, data, materials, the images they read, its node
groups, world, collections, the cameras `make_cameras` made and the actions of its keys), as `bin.dispose()` does for
the bin.

The pure half runs anywhere (no Blender): the time controls, `LAYOUT`, `race_state(t, state)` (everything `update`
sets, in race.js's axes), `crash_pose`, `car_path()` (three's CatmullRomCurve3, 390.45 m), `debris_specs`,
`heel_pose`, `cam_at_three`, `lamp_heads()`, `noise_atlas()` and `night_env()` (both bit for bit race.js's), and the
canvases the set paints: `march_canvas()` (the walk cycle), `radiator_number_canvas()` (the 7),
`Race.billboard_canvas(amount)` and `Race.manifesto_canvas()` (callable on `R.Race.__new__(R.Race)` without a
scene).

### Cameras and focal points

`race.cams[name]` holds the static cameras (Blender axes, set-local, three's vertical fov and a roll about the view
axis): `singer` (the performer's mark under the red screen), `billA`, `billB`, `billboards`, `carPass`, `crash`,
`shadows`, `shadowsWide`, `heel`, `heelTop`, and still stand-ins for `carTrack`, `carChase` and `crashLow`.
`race.cam_at(name, t, state)` gives the moving ones (`carChase`, `carTrack`, `carSide`, `carFront`, `carRear`,
`crashLow`) or `None` when the car is hidden or in its crash. `key_camera(cam, name, t, state, frame)` applies either
the way race.js's `applyCam` did (look at the target with +Z up, then roll) and keys the camera, its lens and the LED
cells' pixel angle; asked for a car camera the car cannot give, it says so. `race.focal(name)` is the shot's idol for
the aeropittura pass (set-local); `focal_world(name)` in the world.

### How it is lit

race.js lit almost everything analytically inside its materials, because a three.js light costs every material in
the scene. EEVEE lights hundreds of lights at once, so the street lamps (38 spots, one shared light datablock), the
works' floods and the heel's close key are real lights at the same heads with race.js's colours, intensities (three's
candela I becomes 4πI W), cones and cut-offs; the deck slab's occlusion of the lamps for anything under it, which
race.js computed, is a real shadow now (the heads' shadow maps read at 2 cm, the screens' glows at 5 cm, in a
1.5 GB pool: at EEVEE's 1 mm default the 38 heads overflow the shadow buffer and shadows drop out). What stays
analytic, as in race.js, is what belongs to one material: the march's floodlight and its projected column (towers
only), the ground's sparse sodium pools, the glints in the rain and the splash (Geometry Nodes evaluate the lamp
field per drop), and the extra dose of lamp light race.js gave its hero (below; one shader node group,
`race:field_light`, that `test_race.py` checks against race.js's formulas). The set's procedural night-city
environment and its hemisphere light are the world seen by reflection and ambient rays; camera rays see the set's
night sky.

The wet road reflects through EEVEE's ray tracing and a planar light probe over the deck (`parts['reflector']`),
the Blender form of race.js's ReflectorNode; its normal is tilted toward the viewer by race.js's streak noise, so
every light smears into a vertical streak on wet asphalt and stays sharp in the puddles. The road itself is hidden
from the probe (`hide_probe_plane`): it lies on the mirror's own plane, and left in the probe's capture its
underside covers the whole mirrored set, so every puddle reflects black (race.js's reflector clipped at its plane).
As in race.js, the transparent effects stay out of that mirror too: the lamps' light cones, the car's contact pad,
the rain and the splash; EEVEE's screen tracing never sees blended surfaces. The screens' glow lights light the set
without specular (`specular_factor` 0): in the puddles a screen is its own mirrored picture, never a point light's
disc, as race.js kept it by holding the road's PBR roughness at 1 for real lights.

### Parts

`parts['billboards']['a' | 'b']` (group, screen, material, texture, amount, mode, tint), `car` and `car_rig`
(group, body, wheels with pivot and spin, mats, path, length, crash_pose, CR, beam, shadow), `riders`, `road`,
`reflector`, `lamps` (poles, lenses, cones, heads), `towers`, `works` (drums, steel, lamps, arrow, debris), `march`
(texture, plane, flood), `heel` (root, pivot, page, dur, strike), `water`, `splash`, `rain`, `sky` (the world),
`ground`, `lights` (key, glow_a, glow_b, rim, back_rim, neon_fill, hemi, sodium, works, heel_key, group).
`race.uniforms` (also `race.U`) is race.js's uniforms: one node group of keyed values every material reads
(`race.uniforms.vals`, `race.uniforms.set(name, value)`).

## The bin

```python
from eidoblend.sets.unknown_force import bin as B

b = B.build()                               # sky, lights, atlas_scale=1, sheets=3300, balls=300, falling=200
performer = bpy.data.objects.new('performer', None)
scene.collection.objects.link(performer)
performer.parent = b.parts['mark']          # the mark climbs out of the can (faces -Y)
frames = (1, 20 * 24)
b.animate(frames, t0=0.0, state_fn=lambda t: {'climb': B.ease_in(t, 2.0, 18.0), 'wind': 0.4,
                                               'hush': 1.0 if 12.0 <= t < 15.0 else 0.0})       # KEYED
b.make_cameras([(0.0, 'binWide', {'push': 2.0}), (6.0, 'paperClose'), (10.0, 'climb', {'orbit': 0.3}),
                (15.0, 'topDown')], frames, t0=0.0)
b.apply_render_settings(scene)              # AgX, ray tracing, the set's world and fog (0x070a14, 0.03);
                                            # bloom=True adds a soft one (0.45, radius 0.5, threshold 0.8)
# or by hand: b.update(t, {'climb': c, 'glow': 1, 'wind': 0.4, 'hush': 0}, frame=f)
#             b.key_camera(cam, 'binWide', frame=f, push=2.0, u=0.5)
```

`climb` walks the mark up the paper slope inside the can (0 low inside, about 0.5 head and shoulders over the
rim, 0.95 to 1 on the front lip), `glow` scales the warm light inside the can, `wind` drifts the falling paper (it
holds its last value, as in bin.js), `hush` turns the neon rims, the rim spot and the lamp down to 0.4.
`B.ease_in(t, t0, t1)` ramps any of them between two times. `b.focal_point()` is the lip where the performer rises;
`b.cams` holds `binWide`, `climb`, `paperClose` and `topDown`; `key_camera` and `make_cameras` take a `push`
(metres along the view, eased through the shot) and an `orbit` (radians about the vertical through the target).
`heap_height(x, y, R)` is the heap's height at a Blender ground point (bin.js's `heapHeight(x, -y, R)`);
`b.fill_y(x, y)` the paper fill's inside the can. `parts['page_atlas']` and `parts['page_grid']` are the pages, for a
wardrobe's paper scraps.

The placement of every sheet, boulder, fragment and readable page follows bin.js's mulberry32 stream call for call,
so the canyon is bin.js's canyon sheet for sheet. The sheets are realized meshes carrying their page cell and shade
as point attributes (bin.js instanced them); the falling paper is bin.js's vertex shader in Geometry Nodes on keyed
time and wind, with three's own hash per sheet. The page atlas takes a minute or two to draw at full size and is
cached as a PNG (`cache_dir`, a temp folder by default). The can's glTF import leaves nothing behind: the set keeps
baked copies of its meshes, adopts the materials and maps they use as `bin:...`, and `dispose()` takes them along.

## The page atlas and the canvas

```python
from eidoblend.sets.unknown_force import bin_pages as P

img = P.draw_page_atlas(cols=6, rows=4, cw=682, ch=1024, cache_dir='/tmp/pages')   # PIL RGBA, 4092 x 4096
P.PAGE_KINDS[13]                                                                    # 'chart'
g = P.Canvas2D(512, 512)                    # canvas 2D on Pillow + numpy, supersampled
g.font = '92px "UF Anton"'; g.textAlign = 'center'; g.fillText('NO DUMPING', 256, 165)
rgba = g.to_float()                         # straight alpha, row 0 at the top
```

`Canvas2D` keeps the canvas API's own names (fillStyle, beginPath, arc, quadraticCurveTo, fillText, save / restore,
globalAlpha, the 'lighter' composite, shadowBlur, radial gradients, clip), so drawing code ports line for line. Fonts
are the kit's bundled faces (the 'UF ...' families parole.js registers) and, where a set asks for them, the
Windows faces it names (Impact, Georgia), used when present.

## Costs

Measured on the shared machine (RTX 5090 Laptop GPU), headless, with other jobs on it:

| | race | bin |
| --- | --- | --- |
| build | 6 to 31 s by the machine's load (88,700 triangles, 71 objects) | 16 to 33 s with the page atlas cached, about 40 s drawing it (607,100 triangles) |
| keying | about 236 keys a frame, 0.1 to 1.3 s a frame by the machine's load | per frame: the mark, five lights, the falling paper's time and wind |
| saved .blend | 4 MB with a whole section keyed (every image packed) | about 40 MB (the atlas and the can's 2k maps packed) |
| a still, 960 × 540, 16 samples | 1 to 3 s (the first frames compile the shaders); a Cycles reference at 128 samples about 9 s | about 1 s |

## Checking

`blender/tests/sets_uf_race_bin/` (see each script's docstring for the command):

- `race_parity.py` and `bin_parity.py` run in plain Python against the WebGPU modules built headless in Deno
  (`race_parity_dump.mjs`, `bin_parity_dump.mjs`): the time controls (against race.js's own cut at its event times),
  the car path, the crash, the debris, the boot, everything `update` sets over 33 states, the moving cameras, the
  noise atlas and the environment (bit for bit), the heap's height, and all 3,943 sheets, 300 boulders and 200
  falling sheets (matrix, page, shade).
- `canvas_parity.py` (plain Python, after `atlas_dump.mjs` draws the WebGPU page atlas) compares every canvas the two
  sets paint with the WebGPU edition's own, drawn on napi canvas with the same fonts: both billboards, the march's walk
  cycle, the radiator's 7, the manifesto page, the can's stickers, the cut shapes and the whole 24-page atlas. Two
  font engines never agree pixel for pixel and the pages' body text is laid out word by word, so they compare at the
  scale a sheet is seen at (an 8 px box filter): every canvas is within 0.7 % mean difference there, and
  `out/parity/cmp_<name>.png` puts each pair side by side.
- `test_race.py` and `test_bin.py` build the sets in Blender, compare every race mesh with race.js's (vertex counts and
  positions) and the bin's placed pieces and lights with bin.js's, evaluate the node-built lamp and works field at
  six points against race.js's formulas, key asset states (the car on its run, through the works and over the edge,
  the march, the boot; the bin's climb, hush and wind), jump to each keyed frame to check the scene shows what the
  pure state says, and render stills from the sets' own cameras into `out/<set>_<camera>_<what>.png`, with an
  overview of each set. Then the invariants: the set moved renders the same stills, the saved .blend renders a keyed
  frame on its own, `dispose()` leaves nothing, and an options build renders. `--cycles <tag>` adds a path-traced
  reference of one race still.
- `test_sections.py` keys whole sections on a clock and a cut of its own through a harness-style `ctx.key`, checks the
  cut comes out as cameras bound to timeline markers, `set_active`'s steps, and that `dispose()` leaves no datablock
  of either set behind.

## Where the port differs from the WebGPU sets, on purpose

- **The set, not the video.** race.js's `CUES` and `suggest(t)` were the music video's sung word times and its cut
  on the song clock, and bin.js's `BRIDGE` the song seconds the bin was made for; they are left out. The moving parts
  they timed keep their own controls (`sequence` and its parts, the bin's state keys with `ease_in`), and
  `animate` / `make_cameras` take your clock and your cut.
- **The bin's lid.** bin.js reads the lid's radius from a bounding box its `scale()` has already scaled, then scales
  it again, so its lid sits about 12 m up, out of every shot. The port leans it against the can's front left, as
  BIN.md describes.
- **Stale values.** race.js leaves the boot's pose and the impact points as they were while they do not show; the
  port resets them, so `update` is a pure function of `(t, state)`. The bin's `wind` holds its last value, as in
  bin.js.
- **Hashes in shaders.** TSL's `hash()` (PCG on the seed read as an integer) becomes a White Noise of the seed rounded
  to an integer in the shader graphs (lit windows, the tearing bands, rain-ring cells, the collage tiles): the same
  role, other bits. Rounding matters: the windows' seed comes from a per-face attribute that interpolates to a hair
  off the integer, and hashing the raw float speckled the windows and made them shimmer whenever the camera or the
  set moved (the WebGPU film shows the same speckle in a few windows, where the interpolation crosses an integer).
  The falling paper keeps three's exact hash per sheet. TSL saturates negative seeds to one value, so in the WebGPU
  bin the collage tiles on the negative side all showed one page; here every tile differs.
- **Parking keys steps.** race.js's `setActive` was called every frame by the film's conductor; here `set_active`
  keys its switches once, as steps (the meshes and the light levels hold their state up to the frame and the parked
  state from it), so a single call at a section boundary is enough.
- **The light's dose per material.** race.js dosed its analytic lamp field per material: the car's paint and leather
  took it 1.7 times ("the hero catches more of the row"), its wood and tyres 1.53, its radiator core 1.36, its brass
  0.43 and its steel 0.6 whatever their metalness, the scarves twice and their streaming tails 2.4 times on the face
  and 1.2 through the silk. The real lights give every material its light once, and a metal none as diffuse; the
  rest of each dose comes back as emission from race.js's own field (`Race._dose`: the six nearest lamps and the
  works' floods, the deck's occlusion included, unshadowed as in race.js), so the hero reads as bright as in the
  WebGPU set. Its clearcoat catches every real lamp where race.js drew Blinn glints. The road's PBR roughness, which
  race.js pinned to 1 against three r184's f90 spike, is the physical wet roughness here.
- **Lamp shadows.** race.js's lamps lit through the car, the barriers and the boot; real lights cast shadows, so the
  car, the works and the boot shade the road under them, and race.js's soft contact pad stays as a darkening under
  the car on top of them.
- **LED cells.** The screens' cells fade once smaller than a pixel, as in race.js; `fwidth` becomes the shaded point's
  distance times the camera's pixel angle (keyed per shot), exact for the near-frontal billboard shots.

## Not yet ported

- **The per-material environment strengths.** race.js reflected its night-city environment at a strength per
  material (the car's paint 1.4, the boot 1.8, the road 0.35, the core 0.6); EEVEE has no per-material world strength,
  so here every material sees the one world at 1.
- **`reflect_scale`.** Accepted and kept, with no effect: EEVEE 5.2's planar probe has no resolution of its own; it
  renders at the render's.
- **The can's ambient-occlusion map.** Blender's glTF import keeps the occlusion map outside the shader, so the
  can's 2k AO (which three applied to its hemisphere light only) is not read.
- **MaterialX noise.** The stickers' wear and the street lamp's rust used `mx_noise_float`; Blender's Perlin noise
  stands in for it (another noise, the same role and scale).
- **A turned set's sky.** race.js's 2400 m sky dome was a mesh in the set's group; here the night sky is the world,
  so turning the set about its vertical leaves the sky's faint clouds where they were (its glow and gradient depend
  on height only, and moving the set changes nothing).
- **The painting.** The race's `race_sun` planes and Russolo's chevrons, and the bin's quiet collage planes, are the
  aeropittura pass's (the look family); these modules hand it the focal points (`focal(name)`, `focal_point()`).
