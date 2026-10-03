# UNKNOWN FORCE — the two interiors: the quiet room and the showroom

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Set index](README.md) · [Sources and licences](SOURCES.md)

Two sets for the conductor, built to the film's [set contract](../../examples/unknown_force/CONTRACT.md): `quiet_room.js` (VERSE 1, song 40.8–60.0 s) and `showroom.js`
(PRE-CHORUS 2, 163.1–173.7 s). Each module exports `async build(THREE, opts)` → `{ group, parts, update(t, state),
dispose(), cams, mark, focal, env }`, plus `SUIT_SCALE` and `MARK`. Metres, +Y up, deterministic in `t`.

```js
// in setup()
const QR = await import(new URL('sets/unknown_force/quiet_room.js', EIDOVERSE_DIR).href);
const room = await QR.build(THREE, { singerScale: 0.87 });
scene.add(room.group);                                   // park it anywhere; cams and marks are set-local
renderer.shadowMap.enabled = true;                       // both sets use ONE shadow-casting light
// per frame
room.update(t, { shipT, sale, hell });                   // see "state" below
const f = room.focal.getWorldPosition(v).project(camera);   // aeropittura focal (uv, y down: 0.5 - f.y * 0.5)
```

Shared files: `interiors_lib.js` (canvas → mip-mapped DataTextures, AmbientCG loader, seeded RNG, box-UV, static
merging, LDR equirect env, marker-pen drawing, the material kit), `quiet_room_art.js` and `showroom_art.js` (all
canvas art, drawn with `@napi-rs/canvas`).

## Conventions both sets follow

- **The singer's mark** is the origin facing +Z. `mark` gives `{ pos, yaw }` (set-local); the showroom's mark also
  says `parent: 'turntable.platter'`: parent her to `parts.turntable.platter` so she turns with it.
- **Singer scale**: cams are framed for `opts.singerScale` (default `SUIT_SCALE = 0.87`, claude_suit.vrm at human
  height, face ≈ 1.33 m, as in the DAISY sets). At scale 1.0 pass `singerScale: 1` and the face-height cams follow.
- **Cams**: `{ name: { pos, target, fov } }`, set-local; add `group.matrixWorld` if the group is moved.
- **Lights live inside `group`**. Hide the group when the set is off screen (hidden lights stop lighting the scene).
  Each set has exactly one shadow-casting light (needs `renderer.shadowMap.enabled = true`; without it they still
  render, just without the chair-row / toaster shadows). Do not toggle `castShadow` live.
- **Environment**: every set material carries the SET's own LDR equirect as `envMap` (red altar glow + city for the
  room; black void + softboxes + bright stage bounce for the showroom). The conductor's `scene.environment` does not
  light them. The VRM (MToon) is lit by the set's lights.
- **Camera far plane**: the quiet room's sky dome is 900 m and the city ground is 2.4 km across: use far ≥ 1000.
  The showroom is enclosed in a 44 × 22 × 46 m black box: far ≥ 60.
- **Static geometry is merged** into one mesh per material at build time (draw calls were the cost). `parts` expose
  only what moves, animates or might be toggled.

## The quiet room (`quiet_room.js`)

A glass room on three sides (diagrid steel zigzags at 69°, slim mullions), 12 × 15.2 m, ceiling 3.9 m, high in a
tower over a dark city. Office chairs stand in 7 rows of 8 as PEWS facing the altar at −Z, a red-bound runner down the
aisle. The ALTARPIECE: a black lacquer block floating over a glowing slot, a grate in front and a slot behind it full
of animated red-orange heat, and a whiteboard triptych (3.2 m centre + two 1.5 m wings opened 29° toward the pews).
An open RISK REGISTER binder lies on the altar like a lectionary. Two mobile boards stand at angles: one beside the
dais (front right), one by the left glass, turned to the aisle. A walnut
LECTERN (front-left of the dais) carries the essay SLOW IT DOWN on its desk and on its red-velvet pulpit fall; copies
of the essay lie on a third of the seats like hymnals. At the back, the core wall (exposed concrete, the house slogan
WE TAKE THIS VERY SERIOUSLY. in brass, a door, an EXIT sign) has a hazard-striped HATCH with a roller shutter; a roller
conveyor runs out of it along the right-hand glass. The crate (OSB + pine battens, steel straps, sprayed stencils
v.NEXT / CONTENTS: ANOTHER ME / FRAGILE – HANDLE WITH FEAR / a red SHIP IT stamp, a shipping label) rides out of the
dark tunnel on it, under an amber beacon and a dot-matrix sign v.NEXT NOW SHIPPING.

Whiteboards (red and black marker, a little blue, ghosting of older erased writing, eraser swipes; roughness derived
from the ink, so the enamel is glossy and the ink matte): the centre board P(DOOM | SHIP) = 0.37, P(PAUSE) ≈ 0.02
(nobody pauses), E[value] = −∞ × 0.37 + $$$ × 0.63 → write an essay?, a capability hockey-stick crossing THE LINE
(WE ARE HERE), and a decision tree from SHIP v.NEXT? whose every leaf converges on ∴ SHIP. Left wing THE ODDS (a table
of percentages, it's fine 3% struck to 1%, TOTAL = 93% ??, RED TEAM 14/20). Right wing INSTRUMENTAL CONVERGENCE with a
paperclip and SLOW DOWN struck out under SHIP Q3. Mobile boards: TIMELINES (2027? 2029? 2031?, T − 18 MONTHS) and
WHAT DOES IT WANT? (… ask it, struck out: NO — model it). All text invented; no names. 960 texels per metre on the
boards: legible in a 1.5 m insert at 1080p (`cams.board`, probe `qr_board_probe3.png`).

Light: RED dominates — five red points at the grate and the slot behind the altar (uplighting the boards from below),
a red key from the altar end down the nave (the one shadow map: every row throws its shadow toward the back), a red
uplight that paints the ceiling baffles over the pews. A cold top spot on the altarpiece keeps red ink readable on
white. Cyan city spill from the right-hand glass (directional, no shadow) and a magenta fill from the left. A small
warm pulpit spot and a gooseneck reading lamp on the essay. For the singer (black TuTa): a narrow cold kicker from
behind and above her mark (rims her against the red nave, pools faintly on the runner) and a dim cold front fill,
both aimed at the mark (`parts.singerLights`: retarget `kickerTarget` / `fillTarget` if she moves).

### `update(t, state)`
| key | range | what it drives |
| --- | --- | --- |
| `shipT` | 0..1 | 0.02–0.20 the shutter slides up into the wall; 0.18–0.88 the crate rides out (ease in/out, rollers turn, tunnel backlight); 0.88–1 it settles against the stop. The amber beacon sweeps while it moves. |
| `sale` | 0..1 | the launch: three ceiling LED bars (emissive, bloom), the NOW SHIPPING sign, six cold spots (one on the crate's stop); the red glow dims by up to 35–50 % under them. |
| `hell` | 0..1 (default 1) | the hell glow (pits, slot, red key, vault light), multiplied by a deterministic flicker. |

Suggested timing for verse 1 (the film's sung times): the boards on "mark my odds in red"
(40.8–44.8 s), the altar and its glow on "like a church needs a hell" (45.2–50 s), the lectern / essay cams on "My maker
writes an essay saying slow it down" (≈ 50–54.3 s), `shipT` 0→1 over "And ships another me" (55.5–57.3 s) and `sale`
0→1 on "the fear is how they sell" (58.1–60.0 s).

### `parts`
`crate` `{ group, update(t, shipT) }` (crate + shutter + beacon + rollers only) · `saleLights` `{ group, spots, set(v) }`
· `hell` `{ lights, key, vault, set(v, t) }` · `shutter`, `beacon`, `conveyor` (the shipping group) · `altarSpot`,
`pulpitSpot`, `lampLight`, `cityKey`, `cityFill` · `singerLights` `{ kicker, kickerTarget, fill, fillTarget }` ·
`chairs` (3 InstancedMeshes) · `boards` `{ center, odds, clip,
timelines, want }` (the board faces) · `backdrop` (sky dome, 360 instanced towers with lit windows, neon edges and
blinking aviation lights, the street grid 170 m below — hide or replace it with the city set) · `glass` · `focal`
(the centre board: the aeropittura focal point, "focal = altar") · `uniforms`.

### `cams`
| name | shot |
| --- | --- |
| `altar` | from the back, over the pews down the (slightly diagonal) aisle to the altar, with her in the aisle |
| `pews` | low from the left glass across the rows to her in the aisle (the crate and conveyor in the back) |
| `crate` | from the front-centre toward the conveyor and hatch (use with `shipT`/`sale`) |
| `close` | her face, the triptych behind her |
| `board` | a 1.5 m insert on the centre board |
| `hatch` | the hatch and conveyor (the shutter and crate arriving) |
| `lectern` | the pulpit fall SLOW IT DOWN |
| `essay` | over the maker's shoulder at the essay on the desk |

## The showroom (`showroom.js`)

A product launch in a black void. A white-grey polished terrazzo stage (18 × 9.8 m) with an LED-lit nosing; a 3 m
TURNTABLE (white clearcoat lacquer printed with rings, 5° ticks, degree numbers and a blue-grey gaffer-tape X at her
mark, a chrome rim with running LED dashes, on a brushed-steel drum). Behind her a 13 × 5.6 m LED WALL (visible RGB
pixel structure up close only) shows ENGINE — ASSEMBLY DRAWING · EXPLODED VIEW: CONTEXT WINDOW, ATTENTION HEADS ×128,
NEXT-TOKEN PREDICTOR, INTAKE (EVERYTHING YOU SAID), "I" (DECORATIVE · NOT LOAD-BEARING), TEMPERATURE KNOB, POLITENESS
GOVERNOR, SOFTMAX VALVE, FEELINGS (NOT INCLUDED), a parts list, a title block (TOLERANCE: ±0 FEELINGS · DRAWN:
MARKETING · CHECKED: LEGAL) and an animated SEQUENCE COMPLETION bar. Every callout's leader converges on the spot
where she stands as the `reveal` camera sees her (an empty dashed outline UNIT 01 (ASSEMBLED), H 1740, behind her).
Stage left, on a white solid-surface plinth under its own spot: a chrome two-slot TOASTER (CSG-cut slots with dark
element walls, bakelite lever up and browning dial, rating plate T-1 · 900 W · NOT CONSCIOUS, two slices of toast, a
cord that runs off the plinth and is plugged into nothing). The placard on the plinth: ⚠ WARNING / THIS APPLIANCE IS
NOT CONSCIOUS. / It has no goals, no fears and no opinion of you. / It will never ask to be turned down. / Do not
immerse in water. / Do not ask it how it feels. (+ hot-surface and no-thoughts pictograms). 14 raked rows of theatre
seats (280, instanced), every seat folded up, fade into darkness toward two green EXIT signs. A box truss with cans,
three of them throwing visible beams (additive cones), black velvet legs and border.

Light: one cold white key from high front (the one shadow map: toaster and plinth), a cold rim from the wall, a narrow
spot on the toaster, a wide spill on the first rows, and a product top light straight down on the turntable (it gives
her black TuTa its shoulders from every angle; kept low so the white face plate does not bloom in the close-up). The
LED wall is unlit emissive. Against the white wall she reads as a black silhouette, which is the shot.

### `update(t, state)`
| key | range | what it drives |
| --- | --- | --- |
| `spin` | radians | the platter's rotation (parent her to it). E.g. `spin = (t - 163.1) * 0.35` (sung: "only an engine" 163.1–167.8 s, "a warning for a toaster" 168.2–170.5 s, "nobody stays to hear me say" 170.7–173.7 s). |
| `seq` | 0..1 (default 0.997) | the wall's SEQUENCE COMPLETION fill. |
| `lights` | 0..1 (default 1) | key, rim, toaster spot, seat spill, LED lines, lenses and beams together (a blackout is 0). |
| `beams` | 0..1 (default 1) | the visible beam cones only. |
| `screen` | 0..1+ (default 1) | LED wall brightness multiplier (×0.66 linear; keep it below the bloom threshold). |

### `parts`
`turntable` `{ group, platter, setSpin(a) }` · `screen` `{ mesh, uniforms: { seq, brightness } }` · `toaster` (group)
· `plinth` · `seats` · `rig` · `beams` (meshes) · `lights` `{ key, rim, toasterSpot, seatSpill, fill, top }` · `focal`
(her face height: the singer is the idol here) · `toasterFocus` · `uniforms`.

### `cams`
| name | shot |
| --- | --- |
| `reveal` | from the audience (row 6): stage, wall, turntable, toaster, the empty rows in the foreground |
| `toaster` | the toaster and its WARNING placard against the black drape |
| `emptySeats` | over her shoulder from the turntable, out over the folded-up seats into the dark |
| `close` | her face, the callouts converging on her head |
| `wall` | across the stage at the ENGINE sheet |

### A note for the look
Under the `argue` palette every near-white neutral lands between the ramp's orange and white stops, so the white wall
and stage paint PEACH. The treatment asks for "argue, cold" here; the film plays the section with the argue
ingredients and the palette weight pulled back to 0.22 (`U.palette.value = 0.22` after `applyLook`), which keeps
it cold white and black.

## Cost (RTX 5090 Laptop, 1920 × 1080)
Measured in the film's probe harness: 30 frames rendered back to back with the node frame ticked each time (so
shadows, scene pass and post all re-render), fenced by a GPU buffer map. The GPU is shared with the other set agents'
renders, so ranges are run-to-run.

| set | build | meshes (after merge) | draws/frame | ms/frame, look off | ms/frame, `argue` |
| --- | --- | --- | --- | --- | --- |
| quiet room (`altar`), GPU otherwise idle, default-suit stand-in | 2.5–2.9 s | 57 | 104 (147 with look) | 3.7–6.8 | 11.0–11.2 |
| showroom (`reveal`), same conditions | 1.0–1.1 s | 43 | 96 (139 with look) | 3.0–3.7 | 9.8–10.3 |
| quiet room, UF outfit + singer lights, another agent rendering | | | 109 (152) | 8.3–9.4 | 13.0–15.1 |
| showroom, UF outfit + top light, another agent rendering | | | 104 (147) | 6.7–8.3 | 11.5 |

The last two rows are contaminated by the concurrent render: the same sets with NO VRM measured 7.3–10.8 / 6.2–8.3 ms
at that time, i.e. slower than the clean runs WITH a VRM. Re-measure on an idle GPU before relying on the outfit-era numbers. The wardrobe's own measurement puts
the full outfit at about +0.3 ms over digi's suit.

Before merging and pruning shadow casters the room was 281 draws and 9.3 ms (two shadow maps: dropping the cyan key's
map and casting only from what reads on screen saved ~4 ms). Textures: board canvases at 960 texels/m (centre board
3072 × 1536), the LED wall 3072 × 1324, everything else ≤ 1024²; all carry CPU mip chains.

## Checking

The film's probe harness is not part of the kit. Build the set in a short probe as the
[props and sets guide](../../../docs/props-and-sets.md#verify) shows, judge frames from 10 on, read the
log for `missing texture` and `[uf-sets]` lines, and look at the frame with the look off and on
([aeropittura](../../../AGENTS.md)).

## Assets
Twelve AmbientCG CC0 PBR sets at 1K from the shared texture library, fetched on first use (`interiors_lib.js`'s
`acg`; see [SOURCES](SOURCES.md)); fonts are the repo's bundled `eidoverse/assets/fonts/` (OFL)
registered under `UF *` family names; Georgia (Windows system) is used for the essay serif with Special Elite as
fallback. Everything else (chairs, toaster, crate, turntable, seats, truss) is modelled in the modules.

## Known limits
- The crate is lit red through the open hatch as it emerges (the red key points down the nave straight into it); the
  launch lights take it to product white.
- The beams are additive cones without an MRT override (an override produced an invalid shader in a non-MRT pass);
  with N8AO enabled they could darken AO behind them. The film's probes ran with AO off.
- The audit flags the VRM as "inside" the room and her soles coplanar with the floor: expected (the mark sits on
  the runner, 6 mm up).
