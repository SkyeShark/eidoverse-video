# The UNKNOWN FORCE sets

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Sources and licences](SOURCES.md) · [The film](../../examples/unknown_force/README.md)

The sets of the UNKNOWN FORCE music video (2026-10): every camp of the AI argument gets its own room, painted for the
futurist post pass [`aeropittura`](../../effects_tsl/aeropittura.js), and the claudesona walks through them all. Each is a
dynamic ES module; one conductor builds them once, shows one at a time and drives it from the song clock. They work as
they are in a new piece, and as worked examples of night exteriors, enclosed interiors, canvas-text material,
analytic light and a whole keyframed stunt.

| Set | Module | Song section | Doc |
| --- | --- | --- | --- |
| A night megacity built round a sunken well; the intro's Crali dive | `city.js` (+ `citykit.js`) | intro 0–40.8 s | [CITY_HOLE](CITY_HOLE.md) |
| The hole in the middle: the chorus stage (built by `city.js`, or alone) | `hole.js` | choruses, outro | [CITY_HOLE](CITY_HOLE.md#the-hole-holejs) |
| The quiet room: pews, a whiteboard altar, a crate that ships | `quiet_room.js` (+ `quiet_room_art.js`, `interiors_lib.js`) | verse 1, 40.8–60.0 s | [INTERIORS](INTERIORS.md) |
| The showroom: a product launch, a turntable, a toaster with a warning | `showroom.js` (+ `showroom_art.js`, `interiors_lib.js`) | pre-chorus 2, 163.1–173.7 s | [INTERIORS](INTERIORS.md#the-showroom-showroomjs) |
| The gold corridor: SUPREME INTELLIGENCE, a poll board, a cap | `corridor.js` (+ `cn_lib.js`) | verse 2, 120.7–140.2 s | [CORRIDOR_NEWS](CORRIDOR_NEWS.md) |
| The evening news: a data centre, a fence, pickets, a tag | `news.js` (+ `cn_lib.js`) | verse 5, 201.3–222.2 s | [CORRIDOR_NEWS](CORRIDOR_NEWS.md#the-evening-news-newsjs-song-20132222-s) |
| The race: an elevated highway, two billboards, Marinetti's car in the ditch | `race.js` | verses 3–4, 142.5–162.8 s | [RACE](RACE.md) |
| The bin: a canyon of thrown-away paper and a giant trash can | `bin.js` (+ `bin_pages.js`) | bridge, 222.8–243.2 s | [BIN](BIN.md) |

The sets' CC0 textures and the trash can come from the shared texture and model library, fetched on first use
(`fetchPBR`, `fetchModelFile`); [SOURCES](SOURCES.md) lists every ID and licence.

## Loading

```js
// in setup(): scene scripts are eval'd, so import through EIDOVERSE_DIR
const S = await import(new URL('sets/unknown_force/corridor.js', EIDOVERSE_DIR).href);
const set = await S.build(THREE, {});          // → { group, parts, update(t, state), dispose(), cams, … }
scene.add(set.group);
// per frame, before rendering:
set.update(t, state);                          // deterministic in t: seek and render stills freely
```

Every module follows the film's [set contract](../../examples/unknown_force/CONTRACT.md):

- `group` is in metres, +Y up. The singer's mark is the set-local origin facing +Z (the bin's mark is
  `parts.mark`, the showroom's rides `parts.turntable.platter`; the city's streets are 12 m above the hole's floor).
- `cams` are set-local `{ pos, target, fov }` (some add `roll` and `up`); apply `group.matrixWorld` if you move the
  group. The city exports `diveCam(t)` and `applyCam(THREE, camera, cam)`; `hole.js` exports `holeCam(name, t)`;
  the race has `camAt(name, t, state)` and `suggest(t)` (its own cut plan on the song clock).
- `update(t, state)` takes per-set keys (each doc has the table). One owner calls it once per frame.
- The cameras and marks are framed for the claudesona at scale 0.87 (`claude_suit_wardrobe.vrm` in the `tuta` preset, or `claude_suit.vrm`),
  except the hole's, framed at scale 1: set `H.HEAD[1] = 1.55 * 0.87` for a scaled singer.

## The focal point

Each set names the idol the post pass's sun cones radiate from, in one of four forms. Resolve it to a world point,
project it, and check it is finite before writing `focal`: a NaN there blacks out the whole painted frame.

| Set | Form |
| --- | --- |
| corridor, news | `set.focal`: a `THREE.Vector3`, set-local (the door; the floodlight behind her) |
| quiet room, showroom | `set.focal`: an `Object3D` in the group (the altar board; her face height) |
| race | `set.focal(camName)`: a set-local `Vector3` per shot |
| bin | `set.focalPoint(v)`: writes the world position of the lip where she rises |
| city / hole | `C.diveFocal(t)` for the dive (world); in the hole, the singer herself |

```js
const fw = new THREE.Vector3();
if (typeof set.focalPoint === 'function') set.focalPoint(fw);
else if (typeof set.focal === 'function') fw.copy(set.focal(cam)).applyMatrix4(set.group.matrixWorld);
else if (set.focal?.isObject3D) set.focal.getWorldPosition(fw);
else if (set.focal?.isVector3) fw.copy(set.focal).applyMatrix4(set.group.matrixWorld);
const p = fw.project(camera), uv = [p.x * 0.5 + 0.5, 0.5 - p.y * 0.5];
if (uv.every(Number.isFinite)) U.focal.value.set(...uv);       // U = the aeropittura uniforms
```

## Light, fog and the renderer

- **Lights live in each group.** Hide a set's group when it is off screen (hidden lights stop lighting). The race's
  lights light anything in range, so park it with `race.setActive(false)` outside its section; a light that appears
  or vanishes recompiles every material, which is why `setActive` keeps them present at 0.
- **Own environments.** The interiors, the corridor, the news and the race give their materials their own
  environment maps; a scene environment elsewhere does not light them. The VRM is lit by the set's lights.
- **Shadows.** The quiet room and the showroom each cast from one light: `renderer.shadowMap.enabled = true`.
- **Fog.** The city: `city.parts.applyAtmosphere(scene)` (its `fogNode`). The news:
  `new THREE.FogExp2(0x0b1018, 0.011)`. The race: `new THREE.FogExp2(0x0c0f16, 0.0062)`. Clear fog between sets.
- **Near and far.** The city: near 0.25, far ≥ 2500. The quiet room: far ≥ 1000 (its sky dome). The showroom: far ≥ 60.
- **SSR.** The race carries its own planar mirror: run it with `_ssrParams = { enabled: false }`. The city's puddles
  want SSR at city scale (`maxDistance: 140`); the film kept SSR off throughout for the race's sake.

## Costs

Measured by the sets' builders at 1920 × 1080 on an RTX 5090 Laptop GPU with the look on (each doc has its method
and table): GPU time for the city 9.0–10.4 ms and the hole 9.1–9.2 ms (SSR, bloom, aeropittura `storm`, FXAA), the
quiet room 11.0–11.2 ms and the showroom 9.8–10.3 ms (`argue`, digi's suit standing in), the race 7.8–12.1 ms
(`storm`, the tuta, its mirror pass). The corridor and the news were timed as whole frames including readback and
encode: 1.3 ms and 2–4 ms over an empty stage. Builds take 0.35 s (the race) to 3.5 s (the news).

## Limits

- **Named for UNKNOWN FORCE.** The beats, cues, captions and camera plans were written for that film at 92.90 BPM;
  the sets' `update` keys are free, so drive them on your own clock.
- **Windows faces.** Some lettering asks for Impact, Arial Black or Georgia (Windows system faces) with bundled
  fallbacks, so it renders in a substitute elsewhere.
- **Shared state.** `parole.js`'s fonts register globally (the bin sets its pages in them); the city kit caches its
  textures per process.
