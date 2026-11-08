# UNKNOWN FORCE: the gold corridor and the evening news (Blender edition)

[Props and sets guide](../props-and-sets.md) · [The WebGPU sets](../../eidoverse/sets/unknown_force/README.md) · [CORRIDOR_NEWS.md](../../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md) · [The film's conductor](../../eidoverse/examples/unknown_force/scene.js)

This is the Blender 5.2 EEVEE edition of two sets of the UNKNOWN FORCE music video: the corridor of power (verse 2,
`corridor.js`) and the evening news at the data centre (verse 5, `news.js`), with the helpers they share
(`cn_lib.js`). They are Python modules in `blender/eidoblend/sets/unknown_force/` that build the whole set in the open
scene from the same numbers as the WebGPU sets, key it on the song clock, and hand back the parts, the cameras, the
focal point and the look the film used. Nothing is loaded but the kit's own fonts, the DAISY crowd figures
(`funeral_crowd.glb`) and the CC0 texture sets the WebGPU sets used, through the shared library.

| Module | What it builds | WebGPU source |
| --- | --- | --- |
| `corridor.py` | black marble and gold, the Deco pilasters and ribs, the sconces' Balla fans, the lanterns, the mirror floor with its sunburst, the red runner, the bronze door under SUPREME / INTELLIGENCE, the LED wall that posts in capitals, the poll board, the uniform, the cap on its cushion, the AI FORCE patch | `sets/unknown_force/corridor.js` |
| `news.py` | the data-centre monolith with CLANKER sprayed on it, the transformer yard, the floods and their beams, the chain-link fence, the wet road and the town, 79 pickets with their signs, phones and torches, the news van and its light, the night sky, the chyron | `sets/unknown_force/news.js` |
| `cn_lib.py` | a canvas-2D drawing like the WebGPU's (@napi-rs/canvas, Skia), relief and mask textures, three's geometry generators, a node-math writer for the materials and Geometry Nodes, lights, world, cameras, and the set base both sets build on | `sets/unknown_force/cn_lib.js` |

Both sets are built in three's metres and converted once, three `(x, y, z)` to Blender `(x, -z, y)`: the floor is
z = 0 and the singer's mark is the origin, facing −Y (three's +Z). What the sets hand back is in Blender's axes
(`cams`, `focal`, every part); the module tables (`CAMS`, `FOCAL`, `CORRIDOR`, `NEWS`, the film's shots) and the
sets' `cams_three` / `focal_three` keep the WebGPU's own numbers so they read against CORRIDOR_NEWS.md.

## The corridor

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import corridor as COR

scene = bpy.context.scene
C = COR.build(scene, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})   # opts: postText, tally, capFitPos/Rot/Scale
C.apply_look(scene)                          # AgX at the set's exposure (see Units), shadows on, no screen-traced mirrors
C.camera('door', scene)                      # the film's five cameras: door, corridorWide, postWall, poll, cap
C.parts['postWall'].set_text('THE DEPARTMENT OF WAR POSTS IN CAPITAL LETTERS')
C.parts['poll'].set_tally(512000, 418000, 141000, stamp='LOSING BADLY')
C.update(0.0, {'open': 0.4, 'post': 0.5})    # a still: sets everything, keys nothing
```

On the song clock, as the film drove it:

```python
from eidoblend.characters import vrm as V
her = V.load_vrm('claude_suit'); her.arm.scale = (0.87,) * 3            # the scale the cameras were framed for
head = (her.arm, her.humanoid['head'])                                  # the cap lands on her normalized head bone
scene.render.fps = 24
frames = (1, int((141.6 - 101.2) * 24))                                 # the corridor's span in the film
C.animate(lambda t: COR.film_state(t, cap_head=head), frames=frames, t0=101.2)   # update() KEYED every frame
C.make_cameras(frames=frames, t0=101.2)      # the film's eight shots with their pushes and orbits, cut by markers
C.apply_post(scene, frames=frames)           # the film's look: bloom and the aeropittura 'argue', its focal keyed per frame
```

`update(t, state, ctx=None, frame=None)` takes CORRIDOR_NEWS.md's state keys. With `frame` (or the harness's `ctx`)
it keys every value it sets, so the saved .blend plays and renders any frame by itself; without, it sets a still.

| `state` key | default | effect |
| --- | --- | --- |
| `open` | 0 | The doors swing in (eased, up to 93°); light pours out along the runner: the beam, the god-ray shafts, the blaze beyond, the light under the door. |
| `beyond` | 1 | The strength of that light. |
| `gap` | 1 | The seam of light between the closed leaves and under the door. |
| `postText` | — | A string. When it changes, the LED wall reposts in capitals (keyed CONSTANT). |
| `post` | 1 | Typing reveal 0..1 with a gold cursor; the layout is fixed per text, so nothing reflows. |
| `screen` | 1 | LED wall gain, its light and its reflection in the floor included. |
| `tally` | — | `[superior, extreme, supreme]`: a recount (keyed CONSTANT). |
| `capOn` | 0 | 0 the cap on its cushion, 1 on her head, carried along a 0.45 m arc in between. Needs `capHead`. |
| `capHead` | — | Her head: an `(armature, bone name)` pair (its normalized frame, as three-vrm's), a Matrix, or an object. |
| `lights` | 1 | Master level of the set's lights and painted light. |
| `camera`, `pix` | — | The render camera (or its pixel footprint): the LED wall's moiré guard reads it. |

`parts`: `doors` (`group`, `left`, `right` the hinge pivots, `leafL`, `leafR`, `seam`), `postWall` (`mesh`,
`set_text(str, name=, meta=, stats=, reveal=)`, `texture`, `canvas`, `state`, `variants`), `poll` (`group`,
`set_tally(a, b, c, title=, sub=, names=, footnote=, stamp=)`, `tally`, `options`; `footnote=False` or
`stamp=False` drop either), `cap` (origin the bottom of the headband, visor toward three's +Z), `capRest`, `capFit`
(`pos`, `rot`, `scale` in head-bone space; `opts` `capFitPos` / `capFitRot` / `capFitScale`), `patch`, `uniform`,
`pedestal`, `cushion`, `plaque`, `beyond`, `shafts`, `sconces`, `room`, `marble`, `env` (the room's light as an
equirect), `lights` (`key`, `doorL`, `doorR`, `plaque`, `beyond`, `poll`, `cap`, `uniform`, `screen`, `fill`, and
`hemi`, the world's hemisphere term), `uniforms` (the root Empty, whose custom properties every material reads
through drivers) and `materials`.

`cams` hold `{pos, target, fov}` set-local in Blender's axes (the sets' contract; `cams_three` keeps the WebGPU
numbers), `focal` is the door, Blender (0, 23.8, 5.2) = three (0, 5.2, −23.8) (`focal_three`, `focal_world()`), and
`look` is `{name: 'argue', exposure: 1.0, bloom: {strength 0.55, radius 0.5, threshold 0.7}, fog: None}`.

### The film's use of it

`COR.FILM_SHOTS` is the film's cut on this set (eidoverse/examples/unknown_force/scene.js): poll (push 0.5, a
reading shot), door, cap (orbit 0.1), corridorWide, door, corridorWide, postWall (orbit −0.08, reading), door,
101.2 to 141.6 s. `film_state(t, cap_head)` is the conductor's own state: the post typed over 130.8–132.3 s, the cap
carried over 135.9–137.0 s, the doors at 0.06 of their swing over 138–140 s, the tally 49 / 39 / 12, and the lights
dipped to 0.15 for the blackout at 115.45–116.6 s. `film_cut(t)` gives the shot (`cam`, `move`, `u`, and `singer`:
the film hid her from the cap and poll shots), `C.film_pose(name, u, move)` the camera with its move, and
`C.key_camera(cam, name, u, move, frame)` keys a Blender camera on it. `COR.CUES` is CORRIDOR_NEWS.md's cue sheet and
`cue_state` is `film_state`.

## The evening news

```python
from eidoblend.sets.unknown_force import news as NEWS
from eidoblend.media import overlay

N = NEWS.build(scene)                        # opts: world, fog (FogExp2 in the materials), shadows, crowd
N.apply_look(scene)
cam = N.camera('crowd', scene)
ov = overlay.make_overlay_layer(scene, camera=cam)
N.parts['chyron'].place(ov, fov=N.cams['crowd']['fov'], aspect=16 / 9)   # the lower third, display space
frames = (1, int((222.6 - 196.3) * 24))
N.animate(NEWS.film_state, frames=frames, t0=196.3)       # spray, chant, the pulse on the signs, KEYED
N.make_cameras(frames=frames, t0=196.3)                   # wide (push 3), crowd, pov, wall (push 0.6), fence, fence
```

| `state` key | default | effect |
| --- | --- | --- |
| `spray` | 1 | 0..1 paints CLANKER on: letter by letter, each with its own sweep, then the outline, then the drips running. |
| `chant` | 1 | Amplitude of the signs' and fists' pumping and the heads' nods (0.95 Hz). |
| `pulse` | 0 | A 0..1 kick envelope added to the pump, to put the signs on the beat. |
| `floods` | 1 | The floodlights: lamps, beams, painted light and the fence's shadow. |
| `lights` | 1 | Master level. |
| `camera`, `pix` | — | Only for the chain link's moiré guard: the steam and the hand lights face the scene's active camera by themselves (Geometry Nodes). |

`parts`: `ground`, `fence`, `poles`, `beams`, `monolith`, `yard`, `street`, `van`, `sky` (hide it under the engine's
sky), `steam` (110 puffs), `signs`, `handlights`, `torchBeams`, `crowd` (its `people` property: the 79 pickets as
JSON; `parts['people']` the list), `rig` (the crowd figure's shoulder, hand and neck), `signAtlas`, `graffiti`
(`texture`, `rect`, `uniform`), `chyron` (`mesh`, `set_text(headline=, sub=, ticker=, tag=, channel=, time=)`,
`place(overlay, fov, aspect, bottom)`, `update(t)`, `state`), `lights` (`floods[4]`, `street[3]`, `news` her key,
`graffiti`, `hemi`), `flood_receivers`, `uniforms`, `materials`. `focal` is the flood behind her, Blender
(−3.9, 6.5, 7.4) = three (−3.9, 7.4, −6.5); `look.fog` is FogExp2(0x0b1018, 0.011), carried by the materials (the
sky takes none).

The pickets are the WebGPU's: the same rng, so the same 79 people stand in the same places with the same roles, signs
and arms (29 signs, 12 phones, 5 torches, 7 fists, the camera operator). Their arms, heads, signs and torch beams pump
in Geometry Nodes, the WebGPU vertex stage written out (the test checks it against news.js's formula to 1e-6 m); the
steam puffs and the hand lights are points placed by Geometry Nodes from the keyed `t` and instanced as quads facing
the active camera (the WebGPU placed 110 matrices on the CPU per frame).

### How it is lit

As in the WebGPU set: the floods are painted analytically onto the ground, the pickets, their signs, the fence and the
steam, with the chain link's diamond shadow and the posts' long shadows across the verge, and those surfaces leave the
real flood lamps out. Here that is light linking: the four flood spots' receiver collection excludes them
(`parts['flood_receivers']`). The real floods (850 cd against the 4200 painted) light her, the building, the van and
the posts. The wet ground mirrors every lamp as a vertical streak toward the camera, painted in its material; the
signs glow through when a flood is behind them.

### The film's use of it

`NEWS.FILM_SHOTS`: wide (push 3.0), crowd, pov, wall (push 0.6, reading), fence, fence (push 0.4), 196.3 to 222.6 s.
`film_state(t)` sprays the tag over 211.5–214.2 s and pumps the signs with `0.5 + 0.5 sin 3t`; `film_singer_mark(t)`
moves her to the fence (z 3.2 − 0.372, her hands on the chain link) from 215.4 s; `film_cut(t)['singer']` is False
on the wall shot. The chyron is the cue sheet's "crowd with the chyron in" (`film_state(t)['chyron']`).

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
  why the poll's LOSING BADLY stamp is distressed on its lower right only, in the film and here);
- `fit_text(g, text, x, y, max_w, max_h, family, ...)` is the JS export; `register_font(path, name)` is
  `GlobalFonts.registerFromPath`.

Against the WebGPU canvases (`test_parity.py`), every texture both sets draw matches to within 1/255 on average
(the sign atlas 1.6/255), and the text advances to within 0.005 %.

**Textures.** A canvas becomes a packed image (`L.canvas_tex`, `L.data_tex`, rows as three's DataTexture);
`height_field`, `box_blur`, `normal_tex` and `pack_tex` make the relief maps (engraving, the door's Deco relief, the
patch's satin stitches) exactly as the JS does. A texture the WebGPU edition redrew while the film ran (a new post, a
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

**The set base.** `update`, `animate(state, frames, t0)`, `camera(name)`, `film_pose`, `key_camera`,
`make_cameras`, `apply_look`, `apply_post`, `focal_world`, `set_u`, `dispose`.

## How the WebGPU pieces became Blender data

| WebGPU | Blender |
| --- | --- |
| TSL node materials | node trees written by `NB` (the same math, in three's axes) |
| `uniform()` values | custom properties on the set's root Empty, read by drivers; `update` keys them |
| a live update without keys | `update(t, st)` tags the root, so the drivers (materials, Geometry Nodes) follow at once |
| canvas DataTextures redrawn over the film | packed images, one per variant (`ImageVariants`), the shown one keyed CONSTANT |
| the post's typing (redraw per character) | one full post, a typing-order map and a cursor lookup row: the shader shows the first `post_n` |
| `texture().grad()` across uv jumps | the jumps moved onto mesh edges (`slice_tris`) |
| `positionNode` (pickets, signs, torch beams) | Geometry Nodes on the per-person copies, reading the keyed `t` |
| CPU-placed billboards (steam, hand lights) | points placed by Geometry Nodes, instanced as quads facing the active camera |
| `lightsNode` leaving the floods out | light linking: the floods' receiver collection excludes the painted surfaces |
| per-material `envMap` / `envMapIntensity` | each material's own image-based light (`NB.ibl`): the set's environment prefiltered for roughness (`prefilter_env`, the GGX lobe of α = r²), three's DFG approximation, the diffuse from the rough level, at the material's intensity, added as emission; the world carries only the hemisphere term, so her VRM, which three lit by the set's lamps alone, takes none either (`opts ibl='world'`: the environment as the world for everything, at 0.75 / 0.7) |
| three's HemisphereLight | the world's colour, sky above and ground below, at its irradiance |
| `BackSide` | the box or sphere wound the other way |
| additive / transparent `MeshBasicNodeMaterial` | emission over Transparent BSDF (Add Shader) / mixed by alpha, blended |
| three's SpotLight / PointLight | spot / point lights (see Units), a custom cut-off so EEVEE's light threshold keeps them |

## Units and exposure

The sets light in three's numbers converted the house way (`look/lighting.py`): a lamp's candela becomes
`cd × 4π / 683` W. Everything that is light without a lamp (emissive paint, unlit glass and screens, the
environment, the hemisphere term, the fog) takes the same factor, `cn_lib.SPEC = 1 / 683`, so lamps and painted
light keep the WebGPU's ratios; `apply_look` sets the view exposure that shows the set as three's renderer did at the
look's exposure, `log2(683 × exposure)` = 9.42 stops. A character dropped into the set takes its light from the set's
lamps and needs nothing; an emissive part of hers would need the same 1/683. Note for the film's conductor: the race
and the interiors of round two light `cd × 4π` W (683 × these), so a cut between them changes the view exposure too.

## Checking

```bash
# the WebGPU originals, headless in Deno (canvases, poses, placements, update()):
cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_corridor_news/cn_parity_dump.mjs
# the Blender sets against them, and each set's own checks (no renders):
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_parity.py
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_corridor.py
cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_news.py
# the film's cameras with the claudesona, the states, the cue sheets, the film's shots, the look on:
cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_uf_corridor_news/render_shots.py both
```

`render_shots.py` writes `out/shots/<set>/` and a contact sheet per set; `--dry` runs everything but the renders.

## Performance

Builds, measured headless on the shared machine (busy with other jobs): the corridor 12 to 19 s, the news 17 to 29 s
(the WebGPU builds took 1.8 and 3.5 s). Most of it is Python drawing the canvases (the patch, the post, the poll, the
graffiti, the sign atlas) and writing the node trees; the environments' prefiltered levels take about a second each.
The corridor holds 42 meshes and about 36k triangles (the marble and the floor are cut along their slab edges), the
news 60 meshes; the pickets, signs and torch beams are Geometry Nodes on per-person copies.

## Not yet ported

- Two terms of three's image-based light: the sheen layer's (`IBLSheenBRDF`, the carpet, the velvet and the wool's
  sheen in the environment) and the multi-scattering energy compensation; the image-based light is also not
  occluded (as in three without its AO pass).
- Ambient-occlusion maps (`aoNode`): three darkens only the indirect light with them; Principled has no such input,
  so EEVEE's own occlusion stands in.
- `polygonOffset` and `depthWrite: false` as material flags: the coplanar pieces sit a few millimetres apart instead,
  and EEVEE's blended surfaces do not write depth.
- The canvas's glyph ligatures (HarfBuzz's 'liga'): none of the sets' strings has one; a string with "fi" would differ.
- The conductor's per-shot look (the reading shots' brush, the spared face, the per-set plane family): the film's,
  not the sets' (`look/post/aeropittura.py` has `ease_reading` and `set_spare`); `apply_post` applies the set's look
  with its focal.
