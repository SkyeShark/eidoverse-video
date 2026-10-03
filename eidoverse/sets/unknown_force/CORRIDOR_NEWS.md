# The corridor (verse 2) and the evening news (verse 5)

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Set index](README.md) · [Sources and licences](SOURCES.md)

Two sets for UNKNOWN FORCE, built to the film's [set contract](../../examples/unknown_force/CONTRACT.md). Both are ES modules:

```js
const C = await (await import(new URL('sets/unknown_force/corridor.js', EIDOVERSE_DIR).href)).build(THREE, opts);
const N = await (await import(new URL('sets/unknown_force/news.js', EIDOVERSE_DIR).href)).build(THREE, opts);
// → { group, parts, update(t, state), dispose(), cams, focal, look }
```

- `group` is in metres, +Y up, floor at y = 0. The singer's mark is the origin facing +Z in both sets. The cameras
  were framed for `claude_suit.vrm` at scale 0.87.
- `update(t, state)` is deterministic in `t`. Call it once per frame, before rendering.
- `cams` hold `{ pos, target, fov }` and `focal` is a `THREE.Vector3`. Both are **set-local**: apply
  `group.matrixWorld` if you park the group elsewhere. `focal` is where the aeropittura's sun cones should come from.
- `look` holds suggestions: `{ name, exposure, bloom, fog }`. Fog is `null` for the corridor; the news set wants
  `FogExp2(0x0b1018, 0.011)`.
- Each set brings its own lights inside `group`, so hiding the group turns them off. Every metal and stone material
  carries its own environment map, so a scene environment set elsewhere doesn't change them.
- Imports: THREE (passed in), the `three@0.184.0` addon `BufferGeometryUtils`, and `@napi-rs/canvas@0.1.69` for
  lettering. The canvas package is the engine's own pinned dependency, the same one `eidoverse/graphics` uses. Shared
  helpers are in [`cn_lib.js`](cn_lib.js).
- Lettering, signs and insignia are canvas material. None of it is extruded type, and none of it is a real seal,
  logo, account handle or face.

## The corridor: `corridor.js` (song 120.7–140.2 s)

A corridor of power at night, 10 m wide, 12 m high and 46 m long:

- Book-matched black marble walls with gold veins.
- Gilded, fluted, stepped Deco pilasters every 4 m, carrying ribs across a lacquered, coffered ceiling.
- Sconces that throw ribbed Balla fans of gold up the marble.
- Four octagonal pendant lanterns.
- A diagonal marble floor with gold inlay and a sunburst before the door. It mirrors the fans, lanterns, LED wall and
  door through analytic reflections.
- A crimson runner with gold border stripes.

The door is 24 m behind her (−Z): a 6.4 × 8 m bronze-gold double door with Deco relief (a split sunburst and a
ziggurat). Above it, an engraved transom plaque, **SUPREME / INTELLIGENCE**, lettered in black enamel. Beside the door
stands the poll board.

The props:

- The LED wall, 13.2 × 6 m on the right (+X) wall.
- A uniform on a tailor's stand with a red sash, gold buttons, epaulettes, an aiguillette, a ribbon bar and the patch.
- A peaked cap on a velvet cushion on a stepped pedestal.
- The **AI FORCE** mission patch: an original, embroidered roundel showing a rocket rising on the diagonal past an
  orbit round a chip, with the motto *SCIT LOCUM SUUM* ("it knows its place").

| `state` key | default | effect |
| --- | --- | --- |
| `open` | 0 | The doors swing in (eased, up to 93°). Light pours out along the runner: a beam, god-ray shafts, the blaze beyond, and light under the door. |
| `beyond` | 1 | The strength of that light. |
| `gap` | 1 | The seam of light between the closed leaves and under the door. |
| `postText` | — | A string. When it changes, the LED wall reposts in capitals (same as `parts.postWall.setText`). |
| `post` | 1 | Typing reveal, 0..1, of the current post, with a gold cursor. The layout is fixed per text, so nothing reflows. |
| `screen` | 1 | LED wall gain, including its light and floor reflection. |
| `tally` | — | `[superior, extreme, supreme]`. When it changes, `setTally` runs. |
| `capOn` | 0 | 0 = the cap on the cushion, 1 = on her head. Values in between carry it along a 0.45 m arc. Needs `capHead`. |
| `capHead` | — | Her **normalized** head bone: `vrm.humanoid.getNormalizedBoneNode('head')`. |
| `lights` | 1 | Master level for the set's lights and painted light. |

`parts`:

- `doors`: `{ group, left, right, leafL, leafR, seam }`. `left` and `right` are the hinge pivots.
- `postWall`: `{ mesh, setText(str, { name, meta, stats, reveal }), texture, canvas, state }`. The post is a generic
  card: an emblem avatar of three gold chevrons (not a seal), the name **DEPARTMENT OF WAR**, no handle, a generic
  check badge, and generic reply, repost, like and view glyphs. All of it can be overridden. Build option:
  `opts.postText`.
- `poll`: `{ group, setTally(a, b, c, { title, sub, names, footnote, stamp }), tally, options }`. It is a
  2.4 × 3.4 m black-lacquer board with gold-leaf lettering on an easel:
  - title: *WHAT SHALL WE CALL IT?*;
  - three rows of hand-painted tally groups with bars and percentages;
  - a red **LOSING BADLY** stamp on the smallest row when it is under 60% of the leader;
  - footnote: *THE ONE BEING NAMED MAY NOT VOTE*.

  `setTally` takes the counts in the poll's order: SUPERIOR, EXTREME, SUPREME. Build option `opts.tally`; the default
  is about 49 / 39 / 12%. Pass `footnote: false` or `stamp: false` to drop either.
- `cap`: a Group whose origin is the bottom of the headband, visor toward +Z. `update` owns its transform from
  `capOn`, so to move it yourself, leave `capOn` at 0 and set `cap.position` after `update`.
- `capRest`: where the cap sits on the cushion.
- `capFit`: `{ pos: [0, 0.13, 0.095], rot: [-0.1, 0, 0], scale: 1.0 }`, in head-bone space. Override with
  `opts.capFitPos`, `opts.capFitRot` and `opts.capFitScale`. It was measured from the front and the side: the
  claudesona's head is a flat flower disc, and the cap sits centred on the disc's plane with the visor over the brow.
- `patch`, `uniform`, `pedestal`, `cushion`, `plaque`, `beyond`, `shafts`, `sconces`, `room`.
- `lights`: `key`, `doorL`, `doorR` (raking floor uplights), `plaque` (a picture light), `beyond`, `poll`, `cap`,
  `uniform`, `screen`, `fill` and `hemi`.
- `uniforms` and `materials`.

`cams`:

| cam | frames |
| --- | --- |
| `door` | Her on the runner, the door, the plaque and the poll board down the axis. |
| `corridorWide` | Crali's dive: a one-point gold tunnel onto the door. |
| `postWall` | The LED wall at an angle, with her at right. |
| `poll` | The board, with the door's relief beyond. |
| `cap` | The cap on its cushion; the uniform behind. |

`focal`: the door, at set-local (0, 5.2, −23.8).

Suggested cues, from the film's sung times:

| time (s) | lyric | cue |
| --- | --- | --- |
| 120.7 | "President renames me" | Go to `door`. |
| 123.1 | "Supreme intelligence" | The plaque. |
| 130.8 | "The Department of War posts" | `postText`, with `post` running 0 → 1 over about 1.5 s. |
| 133.5 | "in capital letters" | — |
| 135.9 | "god in uniform" | `capOn` 0 → 1. |
| 138–140 | "knows its place" | `open` a crack. |

## The evening news: `news.js` (song 201.3–222.2 s)

A hyperscale data centre at night:

- **The monolith.** A windowless precast block, 116 m long and 15 m high, 12 m behind her. It has panel reveals,
  rain streaks, a louvre band, wall packs throwing sodium pools, and serrated rows of condensers on the roof. Four
  cooling towers send up steam plumes, and two low vents steam at its base. Aviation lights blink.
- **The transformer yard.** Three transformers with fins, porcelain bushings and amber beacons; a gantry and
  conductors; gravel; a hazard sign.
- **The floodlights.** Four HMI poles with visible beams in the damp air.
- **The fence.** Chain link 3.2 m in front of her: 2-inch diamonds of 3.5 mm wire, with posts, rails, 45° outriggers,
  three barbed strands and a concertina coil. A private-property sign hangs on it.
- **The protest side.** A verge, a wet road with faded markings and puddles, a raised sidewalk, sodium street lights,
  and a row of small houses with lit windows ("not built in their town").
- **The pickets.** 79 featureless silhouettes: the DAISY funeral's crowd figures, instanced. 29 hold handwritten
  signs, double-sided on cardboard and foam board, that pump with the chant and glow through when a flood is behind
  them. Twelve film on phones, five carry torches with beams, seven raise fists, one is a camera operator.
- **The news crew.** A van with an invented livery (*88 NIGHT DESK*) and a mast, and an LED light on a stand that is
  her key light.
- **The sky.** A night dome with sodium skyglow and overcast.

The pickets' signs are fair local concerns, not mockery: NOT IN OUR TOWN · OUR WATER · WHO PAYS THE BILL? · NO DATA
CENTER HERE · NOISE 24/7 · HEAR US · OUR TOWN, OUR SAY · SAVE OUR AQUIFER.

The tag reads **CLANKER**: a brush-hand spray tag in hot pink with a cream outline, overspray and drips. It is on the
wall behind her, at x 1.2–15.2 m and y 0.6–4.1 m, right of her mark.

| `state` key | default | effect |
| --- | --- | --- |
| `spray` | 1 | 0..1 paints the tag on: letter by letter, each with its own sweep, then the outline, then the drips running. |
| `chant` | 1 | Amplitude of the sign and fist pumping and head nods (about 0.95 Hz). |
| `pulse` | 0 | A 0..1 kick envelope added to the pump, to put the signs on the beat. |
| `floods` | 1 | The floodlights: lamps, beams, painted light and the fence's shadow. |
| `lights` | 1 | Master level. |
| `camera` | `globalThis._c` | The render camera. Steam and hand-light billboards turn to face it, so **pass it** if your camera isn't `_c`. |

`parts`:

- `chyron`: a generic lower third, `{ mesh, setText({ headline, sub, ticker, tag, channel, time }), place(overlay, { fov, aspect, bottom }), update(t), state }`. Place it once, after setup:

  ```js
  N.parts.chyron.place(makeOverlayLayer({ fov: camera.fov }), { fov: camera.fov, aspect: WIDTH / HEIGHT })
  ```

  It is LIVE · NIGHT DESK 88 · 10:42 PM, with the headline "RESIDENTS PICKET AI DATA CENTER", a sub line, and a
  ticker that scrolls in the shader (`set.update` drives it). Show or hide it with `chyron.mesh.visible`. The channel
  and the text are invented.
- `graffiti`: `{ texture, rect, uniform }`.
- `crowd`: its `userData.people` holds the positions and roles.
- `ground`, `fence`, `poles`, `beams`, `monolith`, `yard`, `street`, `van`, `steam`.
- `sky`: hide it if you use the engine's sky.
- `lights`: `floods[4]`, `street[3]`, `news` (the crew's LED, her key), `graffiti` and `hemi`.
- `uniforms` and `materials`.

`cams`:

| cam | frames |
| --- | --- |
| `fence` | Low, through the chain link at her. CLANKER on the wall to her right, the floods' glare at top left. |
| `crowd` | Over the pickets from the sidewalk: silhouettes, signs, phones, the fence and the glare. |
| `wall` | The tag across the wall, a wall pack's pool above it. |
| `wide` | The establishing shot: monolith, roof steam, floods and beams, the fence, the crowd, the van, the street. |
| `pov` | Over her shoulder, through the fence: the pickets and the lit town beyond. |

`focal`: the floodlight behind her, at set-local (−3.9, 7.4, −6.5).

Suggested cues:

| time (s) | lyric | cue |
| --- | --- | --- |
| 201.3 | "evening news … picketing my body" | `crowd` with the chyron in. |
| 204.9 | "not built in their town" | `pov`. |
| 211.5 | "kids made up a slur" | `wall`, with `spray` 0 → 1 over about 2.5 s. |
| 218.9 | "who's the someone you're keeping down?" | `fence`. |

How the light works:

- The floods are painted analytically onto the ground, pickets, signs, fence and steam. These carry the chain link's
  diamond shadow and the posts' long shadows across the verge.
- Those materials leave the real flood SpotLights out of their `lightsNode`.
- The real flood lamps, at 850 against the 4200 painted, light her, the building, the van and the posts. They are
  kept low so her petals don't clip.
- The wet ground mirrors every lamp as a vertical streak toward the camera.
- No shadow maps are needed.

## Performance

Measured at 1920 × 1080 on this machine with the `argue` look and the claudesona, as mean frame-to-frame wall time
including the engine's readback and encode:

| scene | ms/frame |
| --- | --- |
| Empty stage (baseline) | 15.9 |
| Corridor, `door` | 17.2 |
| Corridor, `corridorWide` | 17.3 |
| News, `crowd` | 18.1 |
| News, `wide` | 18.1 |
| News, `fence` | 19.8 |

So the corridor costs about 1.3 ms over the baseline and the news set 2–4 ms. The news set's most expensive view is
the full-frame chain link.

| set | build | meshes | triangles | notes |
| --- | --- | --- | --- | --- |
| Corridor | 1.8 s | 42 | 25k | |
| News | 3.5 s | 57 | 340k | Mostly the instanced crowd and the barbed wire. |

Every material stays within 16 sampled textures.

## Checking

The film's probe harness is not part of the kit. Build the set in a short probe as the
[props and sets guide](../../../docs/props-and-sets.md#verify) shows, judge frames from 10 on, read the
log for `missing texture` and `[uf-sets]` lines, and look at the frame with the look off and on
([aeropittura](../../../AGENTS.md)).

## Limits

- The poll board's smaller lines lose legibility under the `argue` brushwork at 960 × 540. The bars, percentages and
  stamp survive. Use the `poll` cam at 1080p, or spare the board with `uniforms.spare`.
- The doors open by swinging into the room of light; there is no geometry beyond it.
- The steam and hand-light billboards are placed on the CPU every frame, about 110 matrices.
- The chain link is a single transparent plane, so it sorts with other transparents per object. No sorting problems
  showed up in the film's probes.
