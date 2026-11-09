# The gold corridor and the evening news (Blender edition)

[Props and sets guide](../props-and-sets.md) · [The WebGPU sets](../../eidoverse/sets/unknown_force/README.md) · [CORRIDOR_NEWS.md](../../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md)

This is the Blender 5.2 EEVEE edition of two sets made for the UNKNOWN FORCE music video and free for any piece: the
corridor of power (`corridor.js`) and the evening news at a data centre (`news.js`), with the helpers they share
(`cn_lib.js`). They are Python modules in `blender/eidoblend/sets/unknown_force/` that build the whole set in the open
scene from the same numbers as the WebGPU sets and hand back its parts, its five cameras, its focal point and the
look it was lit for. Its moving parts (the doors, the LED wall's posts, the poll board, the cap, the spray tag, the
chanting pickets, the steam, the chyron) are keyed on whatever clock you give them. Nothing is loaded but the kit's
own fonts, the DAISY crowd figures (`funeral_crowd.glb`) and the CC0 texture sets the WebGPU sets used, through the
shared library.

| Module | What it builds | WebGPU source |
| --- | --- | --- |
| `corridor.py` | black marble and gold, the Deco pilasters and ribs, the sconces' Balla fans, the lanterns, the mirror floor with its sunburst, the red runner, the bronze door under an engraved plaque, the LED wall that posts in capitals, the poll board, the uniform, the cap on its cushion, the AI FORCE patch | `sets/unknown_force/corridor.js` |
| `news.py` | the data-centre monolith with a tag sprayed on it, the transformer yard, the floods and their beams, the chain-link fence, the wet road and the town, 79 pickets with their signs, phones and torches, the news van and its light, the night sky, the chyron | `sets/unknown_force/news.js` |
| `cn_lib.py` | a canvas-2D drawing like the WebGPU's (@napi-rs/canvas, Skia), relief and mask textures, three's geometry generators, a node-math writer for the materials and Geometry Nodes, lights, world, cameras, and the set base both sets build on | `sets/unknown_force/cn_lib.js` |

Both sets are built in three's metres and converted once, three `(x, y, z)` to Blender `(x, -z, y)`: the floor is
z = 0 and the mark is the origin, facing −Y (three's +Z). What the sets hand back is in Blender's axes (`cams`,
`focal`, every part); the module tables (`CAMS`, `FOCAL`, `CORRIDOR`, `NEWS`) and the sets' `cams_three` /
`focal_three` keep the WebGPU's own numbers so they read against CORRIDOR_NEWS.md. The cameras were framed for a
figure of about 1.6 m standing on the mark.

The result of `build()` is an object with the parts as attributes, and it reads as a dict too, as the sets' contract
asks: `C['parts']` is `C.parts`, `C['update']` is `C.update`, `C.keys()` lists `group`, `parts`, `update`, `dispose`,
`cams`, `focal`, `look` and the rest.

## The corridor

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import corridor as COR

scene = bpy.context.scene
C = COR.build(scene, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM',    # the post on the LED wall
                      'tally': [49, 39, 12],                                # the poll board's counts
                      'plaque': ('SUPREME', 'INTELLIGENCE')})               # the two lines over the door
C.apply_look(scene)                          # AgX at the set's exposure (see Units), shadows on, no screen-traced mirrors
# C.apply_look(scene, view_look=cn_lib.ACES_LIKE_LOOK)   # the WebGPU frames' tone instead (see Units and exposure)
C.camera('door', scene)                      # the five cameras: door, corridorWide, postWall, poll, cap
C.parts['postWall'].set_text('A NEW POST', name='MINISTRY OF ANYTHING', meta='just now')
C.parts['poll'].set_tally(512000, 418000, 141000, stamp='LOSING BADLY')
C.update(0.0, {'open': 0.4, 'post': 0.5})    # a still: sets everything, keys nothing
```

Its moving parts on your own clock, keyed into the .blend:

```python
from eidoblend.characters import vrm as V
her = V.load_vrm('claude_suit'); her.arm.scale = (0.87,) * 3            # the scale capFit was measured for
head = (her.arm, her.humanoid['head'])                                  # the cap lands on her normalized head bone
scene.render.fps = 24
C.animate(lambda t: {'postText': 'A NEW POST, IN CAPITAL LETTERS',
                     'post': (t - 1.0) / 0.5,             # typed over 0.5 s from 1 s, a gold cursor running ahead
                     'capOn': (t - 2.0) / 1.1,            # the cap carried from its cushion to her head
                     'capHead': head,
                     'open': 0.3 * (t - 4.0) / 2.0},      # the doors cracked over 2 s from 4 s
          frames=(1, 168))                   # update() KEYED on every frame; t = seconds from the first frame (or t0=)
C.apply_post(scene)                          # the suggested look: bloom and the aeropittura 'argue' round the door
```

`update(t, state, ctx=None, frame=None)` takes CORRIDOR_NEWS.md's state keys. With `frame` (or the harness's `ctx`)
it keys every value it sets, so the saved .blend plays and renders any frame by itself; without, it sets a still.
`t` is the set's own clock: the lanterns' slow breath reads it.

| `state` key | default | effect |
| --- | --- | --- |
| `open` | 0 | The doors swing in (eased, up to 93°); light pours out along the runner: the beam, the god-ray shafts, the blaze beyond, the light under the door. |
| `beyond` | 1 | The strength of that light. |
| `gap` | 1 | The seam of light between the closed leaves and under the door. |
| `postText` | — | A string. When it changes, the LED wall reposts in capitals (keyed CONSTANT). |
| `post` | 1 | Typing reveal 0..1 with a gold cursor; the layout is fixed per text, so nothing reflows. |
| `screen` | 1 | LED wall gain, its light and its reflection in the floor included. |
| `tally` | — | `[superior, extreme, supreme]`: a recount (keyed CONSTANT). |
| `capOn` | 0 | 0 the cap on its cushion, 1 on the head, carried along a 0.45 m arc in between. Needs `capHead`. |
| `capHead` | — | The head: an `(armature, bone name)` pair (its normalized frame, as three-vrm's), a Matrix, or an object. |
| `lights` | 1 | Master level of the set's lights and painted light. |
| `camera`, `pix` | — | The render camera (or its pixel footprint): the LED wall's moiré guard reads it. |

Build options: `postText`, `tally`, `capFitPos`, `capFitRot`, `capFitScale` (the JS's), and the Blender edition's
`plaque` (the two engraved lines), `world` (True: the set's environment and hemisphere light become the scene's
world), `shadows` (True) and `ibl` (`'material'`: each material lit by its own environment, as three's per-material
`envMap`; `'world'`: the environment as the world for everything).

`parts`: `doors` (`group`, `left`, `right` the hinge pivots, `leafL`, `leafR`, `seam`), `postWall` (`mesh`,
`set_text(str, name=, meta=, stats=, reveal=)`, `texture`, `canvas`, `state`, `variants`), `poll` (`group`,
`set_tally(a, b, c, title=, sub=, names=, footnote=, stamp=)`, `tally`, `options`; `footnote=False` or
`stamp=False` drop either, and the stamp only lands on a row under 60 % of the leader), `cap` (origin the bottom of
the headband, visor toward three's +Z), `capRest`, `capFit` (`pos`, `rot`, `scale` in head-bone space; `opts`
`capFitPos` / `capFitRot` / `capFitScale`), `patch`, `uniform`, `pedestal`, `cushion`, `plaque`, `beyond`, `shafts`,
`sconces`, `room`, `marble`, `env` (the room's light as an equirect), `lights` (`key`, `doorL`, `doorR`, `plaque`,
`beyond`, `poll`, `cap`, `uniform`, `screen`, `fill`, and `hemi`, the world's hemisphere term), `uniforms` (the root
Empty, whose custom properties every material reads through drivers) and `materials`.

`cams` hold `{pos, target, fov}` set-local in Blender's axes (the sets' contract; `cams_three` keeps the WebGPU
numbers), `focal` is the door, Blender (0, 23.8, 5.2) = three (0, 5.2, −23.8) (`focal_three`, `focal_world()`), and
`look` is `{name: 'argue', exposure: 1.0, bloom: {strength 0.55, radius 0.5, threshold 0.7}, fog: None}`.

## The evening news

```python
import math
from eidoblend.sets.unknown_force import news as NEWS
from eidoblend.media import overlay

N = NEWS.build(scene, {'tag': 'CLANKER',                                  # the word sprayed on the wall
                       'signs': ['NOT IN / OUR TOWN', None, 'WHO PAYS / THE BILL?']})   # None keeps a sign's own
N.apply_look(scene)
cam = N.camera('crowd', scene)               # the five cameras: fence, crowd, wall, wide, pov
ov = overlay.make_overlay_layer(scene, camera=cam)
N.parts['chyron'].place(ov, fov=N.cams['crowd']['fov'], aspect=16 / 9)   # the lower third, display space
N.parts['chyron'].set_text(headline='RESIDENTS PICKET AI DATA CENTER', ticker='YOUR TICKER  ·  ')
N.animate(lambda t: {'spray': t / 2.5,                                    # the tag sprayed on over 2.5 s
                     'pulse': 0.5 + 0.5 * math.sin(t * 3.0)},             # the signs pumped on a beat
          frames=(1, 120))
```

| `state` key | default | effect |
| --- | --- | --- |
| `spray` | 1 | 0..1 paints the tag on: letter by letter, each with its own sweep, then the outline, then the drips running. |
| `chant` | 1 | Amplitude of the signs' and fists' pumping and the heads' nods (0.95 Hz). |
| `pulse` | 0 | A 0..1 kick envelope added to the pump, to put the signs on a beat. |
| `floods` | 1 | The floodlights: lamps, beams, painted light and the fence's shadow. |
| `lights` | 1 | Master level. |
| `camera`, `pix` | — | Only for the chain link's moiré guard: the steam and the hand lights face the scene's active camera by themselves (Geometry Nodes). |

`t` is the set's own clock: the chant, the steam rising, the aviation lights blinking (0.8 s of every 1.6) and the
chyron's ticker read it.

Build options: news.js reads none; the Blender edition's are `tag` (the word sprayed, `'CLANKER'`; a longer word is
drawn smaller so it stays on the wall), `signs` (up to eight messages for the pickets' signs, each a list of lines or
`'LINE / LINE'`; each sign keeps its board, pen and doodle), `world`, `fog` (True: the materials carry the look's
FogExp2), `shadows` (True: the real lamps cast EEVEE shadows, which the WebGPU lamps did not), `chainShadow` (False:
the whole fence, its chain link and its posts, rails, outriggers, wire and signs, casts none of them, so the crew's
LED behind the fence keys the mark clean and neither the diamonds nor the bars of the steel land on the wall and the
tag; the painted floods carry the fence's shadow either way), `signNormals` (`'rest'`, the default: the painted floods
light the raised signs as news.js did, see How it is lit; `'posed'`: by the boards' true normals), `crowd` (True: the
79 pickets) and `ibl`.

`parts`: `ground`, `fence`, `poles`, `beams`, `monolith`, `yard`, `street`, `van`, `sky` (hide it under a sky of your
own), `steam` (110 puffs), `signs`, `handlights`, `torchBeams`, `crowd` (its `people` property: the 79 pickets as
JSON; `parts['people']` the list), `rig` (the crowd figure's shoulder, hand and neck), `signAtlas`, `graffiti`
(`texture`, `rect`, `uniform`), `chyron` (`mesh`, `set_text(headline=, sub=, ticker=, tag=, channel=, time=)`,
`place(overlay, fov, aspect, bottom)`, `update(t)`, `state`), `lights` (`floods[4]`, `street[3]`, `news` the crew's
LED, the key on the mark, `graffiti`, `hemi`), `flood_receivers`, `uniforms`, `materials`. `focal` is the flood
behind the mark, Blender (−3.9, 6.5, 7.4) = three (−3.9, 7.4, −6.5); `look.fog` is FogExp2(0x0b1018, 0.011), carried
by the materials (the sky takes none).

The pickets are the WebGPU's: the same rng, so the same 79 people stand in the same places with the same roles, signs
and arms (29 signs, 12 phones, 5 torches, 7 fists, the camera operator). Their arms, heads, signs and torch beams pump
in Geometry Nodes, the WebGPU vertex stage written out (the test checks it against news.js's formula to 1e-6 m); the
steam puffs and the hand lights are points placed by Geometry Nodes from the keyed `t` and instanced as quads facing
the active camera (the WebGPU placed 110 matrices on the CPU per frame).

### How it is lit

As in the WebGPU set: the floods are painted analytically onto the ground, the pickets, their signs, the fence and the
steam, with the chain link's diamond shadow and the posts' long shadows across the verge, and those surfaces leave the
real flood lamps out. Here that is light linking: the four flood spots' receiver collection excludes them
(`parts['flood_receivers']`). The real floods (850 cd against the 4200 painted) light a figure on the mark, the
building, the van and the posts. The wet ground mirrors every lamp as a vertical streak toward the camera, painted in
its material; the signs glow through when a flood is behind them.

The signs keep one quirk of the WebGPU edition, because its frames were lit by it: news.js raised each board with a
`positionNode` and TSL does not turn normals with one, so its painted floods saw the boards' hanging-pose normals.
The face the crowd sees therefore took the floods head-on (the signs blaze white over the pickets in the `crowd` and
`wide` shots) and the face toward her glowed through (grey ink on lit paper in `pov`). The signs carry those normals
as an attribute (`n0`) and their material reads it; `signNormals='posed'` lights them by their true normals instead
(her side front-lit in its colours, the crowd side a dimmer glow). The pickets' own painted floods use their posed
normals (their dark coats show the difference on raised arms only).

## cn_lib: what both sets stand on

**The canvas.** `cn_lib.create_canvas(w, h).get_context('2d')` takes the canvas-2D calls the sets make, in snake_case
(`fill_rect`, `begin_path`, `arc`, `bezier_curve_to`, `fill_text`, `stroke_text`, `create_radial_gradient`,
`draw_image`, `global_composite_operation`, `shadow_blur` ...). It is built to draw what @napi-rs/canvas drew:

- shapes are filled by a scanline fill with canvas's nonzero rule (even-odd on request), 4 × 4 samples per pixel at
  the sample centres, so a 14 px rect covers exactly 14 pixels and a ring cut by an opposite winding is a ring;
  strokes are outlined (quads, miter joins with the limit 10, round and bevel joins, butt, square and round caps);
- text is laid out as Skia lays it: each glyph's unhinted advance from the face's `hmtx`, the face's GPOS pair
  kerning ('kern' feature, PairPos formats 1 and 2, legacy 'kern' as a fallback), drawn 4 × 4 and box-filtered;
  'bold' on a face with no bold of its own (Exo 2 is one variable face) is Skia's fake bold, the face's own advances
  with its outline grown by size / 64; glyph coverage goes through Skia's mask gamma (light text a little heavier,
  dark a little lighter); a shadow is (shadow alpha × paint alpha)², and a `destination-out` erases only inside
  the canvas rectangle carried through the current transform, both as @napi-rs/canvas 0.1.69 draws them (that is
  why the poll's LOSING BADLY stamp is distressed on its lower right only, in the WebGPU set and here);
- `fit_text(g, text, x, y, max_w, max_h, family, ...)` is the JS export; `register_font(path, name)` is
  `GlobalFonts.registerFromPath`.

Against the WebGPU canvases (`test_parity.py`), every texture both sets draw matches to within 1/255 on average
(the sign atlas 1.6/255), and the text advances to within 0.005 %.

**Textures.** A canvas becomes a packed image (`L.canvas_tex`, `L.data_tex`, rows as three's DataTexture);
`height_field`, `box_blur`, `normal_tex` and `pack_tex` make the relief maps (engraving, the door's Deco relief, the
patch's satin stitches) exactly as the JS does. A texture the WebGPU edition redrew while it ran (a new post, a
recount, a new chyron) is an `ImageVariants`: every variant is packed, and a keyed property picks the one shown.

**Geometry.** three r184's Box, Cylinder, Cone, Sphere, Lathe, Torus, Circle, Plane and Tube generators, CatmullRom
and quadratic Bézier curves, `extrude_polygon`, `prep`, `box_uv` (metre UVs) and `bucket` (merge many pieces into one
mesh) in three's axes; meshes convert when they are made, with three's normals as custom normals. `slice_tris` cuts
triangles where a texture uv jumps (the marble's book-matched slabs, the floor's diagonal tiles), because EEVEE picks
mip levels from screen derivatives and a jump inside a triangle draws a seam; the WebGPU sampled those with explicit
gradients.

**Node math.** `NB` writes the TSL materials' math as shader (or Geometry Nodes) nodes line for line: arithmetic on
`X` values folds constants, `nb.P()` / `nb.cam_local()` read positions in three's axes, `nb.U(name)` is a set uniform
(a Value node driven by the root's custom property), `nb.mx_noise` / `nb.mx_fbm` are three's MaterialX noises.
`L.mat(name).standard(...)` / `.unlit(...)` finish a material (Principled or emission, additive or blended, with the
set's fog), and `L.pbr_mat(S, tile=, tint=, recolor=, macro=, rough=, metal=, nrm=, post=, physical=, sheen=,
clearcoat=, side=, ...)` is the JS `pbrMat`. `GN(L, ob, name)` writes a Geometry Nodes modifier the same way.

**The set base.** `update`, `animate(state, frames, t0=)`, `camera(name)`, `apply_look`, `apply_post(frames=)` (its
focal keyed through the scene's camera on every frame, so it follows cuts made with camera markers), `focal_world`,
`set_u`, `dispose`, and the dict reading of the contract.

## How the WebGPU pieces became Blender data

| WebGPU | Blender |
| --- | --- |
| TSL node materials | node trees written by `NB` (the same math, in three's axes) |
| `uniform()` values | custom properties on the set's root Empty, read by drivers; `update` keys them |
| a live update without keys | `update(t, st)` tags the root, so the drivers (materials, Geometry Nodes) follow at once |
| canvas DataTextures redrawn while running | packed images, one per variant (`ImageVariants`), the shown one keyed CONSTANT |
| the post's typing (redraw per character) | one full post, a typing-order map and a cursor lookup row: the shader shows the first `post_n` |
| `texture().grad()` across uv jumps | the jumps moved onto mesh edges (`slice_tris`) |
| `positionNode` (pickets, signs, torch beams) | Geometry Nodes on the per-person copies, reading the keyed `t` |
| CPU-placed billboards (steam, hand lights) | points placed by Geometry Nodes, instanced as quads facing the active camera |
| `lightsNode` leaving the floods out | light linking: the floods' receiver collection excludes the painted surfaces |
| per-material `envMap` / `envMapIntensity` | each material's own image-based light (`NB.ibl`), three r184's indirect terms: the set's environment prefiltered for roughness (`prefilter_env`, the GGX lobe of α = r²) x the single scattering, plus the multiple scattering x the irradiance (dielectric and metal mixed by metalness), the diffuse from the rough level less the dielectric's scattering, the clearcoat's layer, the sheen's layer (`IBLSheenBRDF`) with its energy compensation; at the material's intensity, added as emission. The world carries only the hemisphere term (`opts ibl='world'`: the environment as the world for everything, at 0.75 / 0.7) |
| `aoNode` (`pbrMat`'s `ao` / `aoAmt`, the sets' AO maps) | the AO map occludes that image-based light as three's did (the diffuse, coat and sheen by it, the specular by its specular occlusion); the lamps are untouched, as there |
| `positionNode` moving vertices, the normals left behind | the posed mesh shades with its true normals; where the WebGPU frames showed the stale ones (the signs' painted floods) the rest-pose normal rides along as an attribute (`n0`) |
| three's HemisphereLight | the world's colour, sky above and ground below, at its irradiance |
| `BackSide` | the box or sphere wound the other way |
| additive / transparent `MeshBasicNodeMaterial` | emission over Transparent BSDF (Add Shader) / mixed by alpha, blended |
| `depthWrite: false` (the shafts, the seam, the beams, the steam, the hand lights, the torch beams) | Transparency Overlap on (`Mat.unlit(depth_write=False)`, the default for additive): every layer of the object blends, as three drew a cloud of puffs or a double-sided cone in one call. Off (depth written), EEVEE keeps only the object's front-most layer: the steam vanished behind its own front puffs |
| three's SpotLight / PointLight | spot / point lights (see Units), a custom cut-off so EEVEE's light threshold keeps them |
| `userData.assembly`, `userData.noSupportCheck` | the same names as custom properties on the objects |
| TSL's `uv()`, a vec2 | the UV Map node, a 3-vector with z = 0: a radius from the quad's centre is built from its x and y (`nb.vec2(u.x - 0.5, u.y - 0.5)`). `(uv - 0.5) * 2` would carry z = −1 into `dot(d, d)`: every steam puff and hand light came out transparent until that was found |

## Units and exposure

three r155+ shades a punctual light of I candela as irradiance I / d² with no 683 lm/W factor, so the sets' levels
carry over as radiometric numbers: a spot or point lamp is `cd × 4π` W (`cn_lib.cd_watts`), and everything that is
light without a lamp (emissive paint, unlit glass and screens, the environment, the hemisphere term, the fog) is
three's number as it is (`cn_lib.SPEC = 1`). `apply_look` sets the view exposure that shows the set as three's
renderer did at the look's exposure: `log2(exposure)`, 0 stops at 1.0. This is the convention of the other round-two
sets (the race, the interiors, the funeral), so cuts between them keep one exposure, and a VRM dropped in (the VRM
add-on's MToon emits its lit colour) renders as it does there. The glTF importer's `/ 683`
(`look/lighting.candela_to_watts`) is photometric: lamps and paint at `/ 683` need a +9.42-stop view exposure, and
that exposure blows a VRM's MToon out to white.

The tone curve is the one difference left in every frame. The WebGPU probes used three's `ACESFilmicToneMapping`
(which also scales by exposure / 0.6); plain AgX lifts the deep darks to about twice their level there and holds the
highlights lower, so under it the marble's veins, the pickets' coats and the patch read lighter, and the lit signs,
the LED wall and the open door's blaze duller, than in the WebGPU frames. Measured in Blender 5.2, sRGB 8-bit for a
scene-linear grey of:

| linear | 0.01 | 0.05 | 0.18 | 0.5 | 1 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| three's ACES Filmic | 8 | 50 | 127 | 197 | 226 | 251 |
| AgX, look None (the pipeline's) | 18 | 58 | 118 | 170 | 197 | 237 |
| AgX, `AgX - Medium High Contrast` (`cn_lib.ACES_LIKE_LOOK`) | 10 | 49 | 118 | 178 | 208 | 248 |
| AgX, `AgX - Punchy` | 3 | 35 | 88 | 144 | 177 | 228 |

`apply_look(scene, view_look=cn_lib.ACES_LIKE_LOOK)` sets that look (it is the scene's, so it holds for every set in
the scene); without `view_look` the scene keeps its own. The WebGPU probes also lit materials that have no envMap of
their own (the runner, the signs) by the probe harness's fallback sky at 0.3, which the sets themselves never had.

## Checking

```bash
# the WebGPU originals, headless in Deno (canvases, poses, placements, update()):
cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_corridor_news/cn_parity_dump.mjs
# the Blender sets against them, and each set's own checks (no renders):
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_cn_lib.py
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_parity.py
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_corridor.py
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_news.py
# test stills from the sets' cameras: every camera, the states and options, the look on (both sets in one run):
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/render_shots.py both --her
# the news set's billboards alone on black (the steam, the hand lights): that they draw at all
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/render_steam_alone.py
# a saved .blend plays on its own: each set animated, saved, and the same frames rendered again from the file in a
# fresh Blender that imports nothing of eidoblend (bake, then replay; corridor, then news)
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/verify_keyed_replay.py bake corridor
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/verify_keyed_replay.py replay corridor
# close-ups the set cameras never frame (the patch, the uniform, the cap, the pedestal, the van, a fence sign, the
# yard), her on the news mark, and one camera per set under plain AgX and the ACES-like look against the WebGPU frame
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/verify_probes.py both
```

The tests also check that every mesh carries the uv maps and attributes its materials read
(`_fixture.material_attr_misses`): a material that names a uv layer its mesh lacks samples one texel, and the
surface turns one flat colour (the corridor's pedestal once did, its marble reading the walls' book-matched uv).

`render_shots.py` writes `out/shots/<set>/` and a contact sheet per set; every still carries the look's bloom (as the
WebGPU probes' 'off' frames did) and one per set the aeropittura too; `--her` stands the claudesona on the mark for
the cap shots alone (the cap carried to her head, its fit from the front and the side), `--dry` runs everything but
the renders. Give the news set a 12 GB cap: its shaders (the ground's painted floods and streaks are some 1,200
nodes, the signs 700, each picket variant 440) ran the driver's compiler out of memory under 4 GB.

## Performance

Builds, measured headless on the shared machine (busy with other jobs): the corridor 17 to 53 s, the news 25 to 76 s
(the WebGPU builds took 1.8 and 3.5 s). Most of it is Python drawing the canvases (the patch, the post, the poll, the
graffiti, the sign atlas) and writing the node trees; the environments' prefiltered levels take about a second each.
The corridor holds 42 meshes and about 36k triangles (the marble and the floor are cut along their slab edges), the
news 60 meshes; the pickets, signs and torch beams are Geometry Nodes on per-person copies.

Renders at 960 × 540 and 16 samples: each set's first frame takes 7 to 17 s (EEVEE compiling its shaders), every
other still 0.4 to 2.2 s, the look on 1.5 to 24 s (its first frame compiles the aeropittura's compositor graph).
Both sets in one run (two builds, 24 stills and the chyron overlay) take 2 to 3.5 minutes and peak at 5.4 GB of RAM.

## Limits

- The poll board's smaller lines lose legibility under the `argue` brushwork at 960 × 540 (the bars, percentages and
  stamp survive). Use the `poll` camera at 1080p, or spare the board: `apply_post` returns the aeropittura's handle,
  and `look.post.aeropittura.set_spare(e.uniforms['aeropittura'], x, y, r)` keeps a disc of the frame readable (uv,
  y down; r in frame heights), the WebGPU's `uniforms.spare`.
- The doors open by swinging into the room of light; there is no geometry beyond it.
- The chain link is one blended plane per fence, so EEVEE sorts it with other blended surfaces per object; the
  stills showed no sorting problem.

## Left out on purpose

CORRIDOR_NEWS.md's suggested cues (the song's seconds and lines for each set) and the music video's own cut of these
sets recreate that video, so they are not part of the asset; `animate()` keys any state on your own clock, and the
sets' cameras are there to cut between.

## Not yet ported

- `polygonOffset` as a material flag: EEVEE has no per-material depth bias, so the coplanar pieces sit a few
  millimetres apart instead. (`depthWrite: false` is ported: `pbr_mat(depth_write=False)` and `Mat.unlit` turn on
  Transparency Overlap.)
- Two small terms of three r184's image-based light: it reads its DFG from a table where `NB.dfg` uses Karis's fit
  (within a few %), and a clearcoat dims the layer under it by its Fresnel (`1 - clearcoat x Fcc`); here the coat's
  reflection is added on top.
- The image-based light has no occlusion beyond an AO map (as in three without its AO pass); EEVEE's own horizon
  scan occludes only the world's hemisphere term.
- The look's FogExp2 lives in the sets' materials, so a character dropped in is not fogged (three's scene fog fogged
  her too): 0.3 % at 5 m, 5 % at 20 m, 22 % at 45 m (the `wide` camera).
- `pbr_mat`'s side defaults to `'double'` where three's `pbrMat` defaulted to FrontSide: closed meshes look the
  same; an open one (the towers' stacks, the uniform's collar) keeps its inside. Pass `side='front'` for three's.
- The canvas's glyph ligatures (HarfBuzz's 'liga'): none of the sets' strings has one; a string with "fi" would differ.
