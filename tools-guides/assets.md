# Sourcing assets — models, HDRIs, textures, kits

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The fetch tools help find reusable models, environments and surface maps.
They can save substantial work on a realistic setting. Inspect candidates for
the scene you are making; reuse, kitbashing and original geometry are all part
of the studio. Search ranking does not establish visual suitability or license
compatibility with a particular redistribution; for a downloaded model, read
its [licence sidecar](#fetch_modelpy--meshes-from-everywhere-at-once) before
redistributing.

The fetchers write their downloads into the **current directory**, so run
them from the piece's folder (paths below assume `work/<id>/`, two levels
under the repo root). They find the local model library and the preview
renderer relative to their own location, not the current directory.

## `fetch_model.py` — meshes from everywhere at once

```bash
cd work/<id>
python ../../fetch_model.py "search terms" --theme "your piece's mood/setting"
```

Searches local custom models + Poly Haven + Smithsonian + NASA + NIH 3D all
at once, ranks every candidate across all sources, and delivers the best one
(printing the runners-up from every source). Read the `_preview.jpg` before
placing — it shows orientation + scale via visible features and the colored
axis labels (+X red, +Y green, +Z blue).

- **`--theme` tunes the pick to your video** — e.g. `fetch_model.py "car"
  --theme "cyberpunk neon dystopia"`. Theme fit is semantic: an embedding
  model scores each candidate against your setting by meaning, so natural
  phrasing (paraphrases, mood words, eras) works. The theme re-ranks
  relevance-matched candidates — a damaged car floats up for a dystopia and
  sinks for a vintage showroom. Inspect the result; rankings can still miss
  the intended object or style.
  *(Uses any OpenAI-compatible `/v1/embeddings` endpoint via
  `EIDOVERSE_EMBED_URL`/`EIDOVERSE_EMBED_MODEL`/`EIDOVERSE_EMBED_KEY`,
  defaulting to Jina's free tier via `JINA_AI_KEY`; with no key it degrades
  to relevance-only.)*
- **Local models are referenced in place.** When the match is local,
  fetch_model prints `Local model (referenced IN PLACE — not copied):
  <absolute path>` — put that exact path into `scene.json` `assets` (the
  engine loads any path). Copying multi-MB meshes per scene bleeds the disk;
  referencing in place costs nothing. Downloaded models land in the current
  directory with their `_preview.jpg` beside them: a Poly Haven model as
  `<model_id>_embedded.gltf` (textures inlined, 1k), a Smithsonian, NIH 3D or
  NASA model as `<name>.glb` (names lowercased, other characters → `_`) —
  those stay with your work. Browse the whole local catalog with
  `python fetch_model.py --list-local` (from the repo root).
- **Every download writes a licence sidecar** beside the model:
  `<model file stem>.license.json` (so `<model_id>_embedded.license.json` for
  Poly Haven), recording `source`, `file`, `id`, `url`, `license`,
  `license_url`, title/author where the source exposes them, and the fetch
  date. Read it before redistributing. Poly Haven is `CC0-1.0`; Smithsonian
  entries are marked `unverified` (CC0 only when the object page says Open
  Access, otherwise the Smithsonian Terms of Use); NIH 3D licences vary per
  submission and read `unknown` when the entry lists none; NASA carries the
  NASA media usage guidelines. Local models are referenced in place and get
  no sidecar.
- **The preview is best-effort.** A missing Deno/ffmpeg, a timeout or a
  renderer crash skips `_preview.jpg` with a message; the model is still
  delivered.
- **`[ORIGIN_INFO]`** tells you where the model's pivot `(0,0,0)` sits in
  its bbox — **BASE** (y=0 at the bottom; rests directly on a surface),
  **CENTERED** (add half the height to stand it on a floor), **TOP**, or
  **OFFSET**. Many GLBs are base-pivoted, so a "centered" `position.y`
  floats or sinks them. `placeOn`/`placeAgainst` seat the bbox regardless of
  pivot, which is why they're the go-to; `[ORIGIN_INFO]` matters when you
  set `position.y` by hand.
- **The alternatives are printed for a reason.** The run shows the full
  ranked candidate table (`rel=` relevance, `sim=` theme similarity, `×`
  multiplier, `→` combined) with the exact token to re-fetch each. If the
  preview isn't the variant you wanted — wrong colour, type, style —
  re-fetch a specific one by its name/id: `fetch_model.py "server_rack_01"`.
- **Cache and reuse.** Downloading the same `wooden_bowl_01.gltf` twice in
  one session means the first copy wasn't tracked — keep and reference it.

## `fetch_hdri.py` — environment lighting

```bash
python ../../fetch_hdri.py "search" [resolution]
```

`resolution` is the optional second argument: `1k` (default), `2k`, `4k` or
`8k`. The query may also be an exact Poly Haven or AmbientCG ID.

Searches Poly Haven + AmbientCG; on an equal match score Poly Haven wins
(native `.hdr`, no conversion). An HDRI provides environment lighting and
IBL reflections in a single asset; choose one when it suits the lighting rig. Outputs `hdri.hdr` (plus a legacy `hdri_b64.txt` sidecar you
can ignore) in the current directory. AmbientCG HDRIs come as OpenEXR;
`fetch_hdri` converts them to Radiance `hdri.hdr` without tonemapping, so the
HDR range is kept. The conversion needs `ffmpeg` and `ffprobe` on PATH and
numpy. If it can't convert, it writes `hdri.exr` instead, tells you to load
that with three's `EXRLoader` (not `RGBELoader`/`HDRLoader`) or pick a Poly
Haven HDRI, and exits with status 2. Point the `hdri` asset at the raw `hdri.hdr`.

## `fetch_texture.py` — PBR sets

```bash
python ../../fetch_texture.py "material" [resolution]
```

`resolution` is the optional second argument: `1k` (default), `2k`, `4k` or
`8k`. The query may also be an exact Poly Haven or AmbientCG ID, or
`texturecan:<id>`.

Basecolor + roughness + normal + AO + metalness + displacement, from Poly
Haven + AmbientCG + TextureCan (all CC0). Outputs `tex_urls.json` — Poly
Haven entries are CDN URLs; AmbientCG/TextureCan maps are extracted into the
current directory and their entries are absolute local paths the engine reads
directly. Load the maps you need onto the material;
unused downloads do not change the scene. A constant channel is appropriate
when that property is uniform. This example uses four varying channels:

```js
// 1) Download each tex_urls.json URL to assets/, declare in config.assets
//    as <name>_albedo / _nor / _rough / _metal (raw image bytes).
// 2) In setup(), load with globalThis.loadImageTexture — not TextureLoader.
//    (TextureLoader's blob-URL path hangs on this deno+wgpu stack; the
//    helper decodes via Deno's native createImageBitmap instead.)
const albedo = await globalThis.loadImageTexture(ASSETS.concrete_albedo, { srgb: true });
const nor    = await globalThis.loadImageTexture(ASSETS.concrete_nor);     // linear (default)
const rough  = await globalThis.loadImageTexture(ASSETS.concrete_rough);   // linear
const metal  = await globalThis.loadImageTexture(ASSETS.concrete_metal);   // linear
albedo.repeat.set(8, 8); nor.repeat.set(8, 8); rough.repeat.set(8, 8); metal.repeat.set(8, 8);
const floorMat = new THREE.MeshStandardNodeMaterial({
    map: albedo, normalMap: nor, roughnessMap: rough, metalnessMap: metal,
    metalness: 1, // map multiplies this value; a dielectric map stays black
});
```

There is no fixed minimum map count. A dielectric can use constant metalness
0; a uniformly colored surface may not need an albedo texture. Keep authored
UVs and baked maps on loaded assets instead of replacing them wholesale.
`globalThis.loadImageTexture(bytes, { srgb })` loads any image into a
texture — screen content, decals, logos, projected images, sprite sheets —
anywhere you'd reach for `TextureLoader` in a browser. (Brand/logo art:
real transparent PNGs declared as assets read on-brand; a hand-rolled
procedural approximation of a logo doesn't.)

## Loading GLBs in the scene

```js
const loader = new globalThis.GLTFLoader();
const gltf = await new Promise((res, rej) =>
    loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.tvModel), '', res, rej));
gltf.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
scene.add(gltf.scene);
```

Models come pre-materialed — their authored materials are the look.
Models over ~1M polys can crash the loader; fetch_model auto-filters them.

**Real-world scale is the default.** A fetched laptop is ~0.3 m wide, a
chair ~1 m tall, a car ~4.5 m long. Prominence comes from the camera (move
closer, lower FOV) or from positioning — inflating a mesh makes everything
around it read as miniature. Correct unit mismatches first: some pipelines
author in centimeters and ship at 100× (a "laptop" whose preview reads
30 m wide wants `.scale.setScalar(0.01)`). Deliberate scale changes are also
available; check the resulting proportions, contacts and animation.

## Embedded animations — play what ships

Many fetched models (robot arms, machines, doors, rigged props) carry their
own animation in `gltf.animations`. Playing it beats hand-rotating the mesh
every time:

```js
const loader = new globalThis.GLTFLoader();
const gltf = await loader.parseAsync(b64toArrayBuffer(ASSETS.robot_arm), '');
globalThis.playModelAnimations(gltf, { clip: 0, loop: THREE.LoopRepeat });
scene.add(gltf.scene);
```

`{ clip }` selects by name or index (default first; `{ clip: 'all' }` plays
every clip). The mixer registers for per-frame auto-update — nothing to call
yourself. If the log says the model has no embedded animations, that's the
cue to animate it by hand.

**Duplicating a rigged model: `cloneModel`, not `.clone()`.** A naive
`obj.clone(true)` of a skinned GLB shares the original's skeleton, so every
copy snaps to the same bones — fine while static, exploding into
disconnected pieces the moment it animates. `globalThis.cloneModel(armA)`
(SkeletonUtils) rebinds a fresh skeleton. Plain unrigged meshes are safe
with `.clone()`.

## The animated birds — crow & cactus wren

Two purpose-built, fully-clipped bird assets in `eidoverse/assets/models/`,
each one skinned mesh with named clips for `playModelAnimations`:

| model | clips | size L×H×W |
|---|---|---|
| `crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Caw` `Talk` `TurnL` `TurnR` | 0.77 × 0.52 × 0.88 m |
| `cactus_wren_bird_animated_desert_songbird_calling_hopping_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Call` `TurnL` `TurnR` | 0.19 × 0.13 × 0.22 m |

Both drop straight in: feet at the origin, nose along +z (registered in
`_forward_axes.json` for `driveAlong`/`faceToward`), real-world scale — a
wren really is that much smaller than a crow. `Walk`/`Hop` are in-place
cycles, so drive the body forward yourself or the bird moonwalks. `Fly` is
a level cruise — pitch the model for climbs and dives. For a flock,
`cloneModel` each bird and offset `action.time` randomly so they don't beat
in unison.

Paired call audio, pre-aligned to the clips, in `eidoverse/assets/audio/`:
`crow_caw_clip_synced.wav` (1.60 s — two caws landing on the `Caw` clip's
two gape peaks; start both together, no offset), `cactus_wren_call_clip_synced.wav`
(2.40 s — the `Call` clip bobs on all 12 note onsets), `crow_caw_single.wav`
(one caw for scattered background use). The caws are our own Stable Audio
generations, CC0 — regenerate with `generate_sfx.py` if you need variants;
a real crow caw puts ~70–80% of its energy in 0.8–2 kHz, so a generation
landing above 5 kHz is hiss rather than bird.

## Kits — models that are catalogs of parts

Many fetched models are kits (modular building kits, pipe kits, plant packs)
— a catalog of parts laid out in a row, not one finished object. Dropping
the whole `gltf.scene` in drops all the pieces scattered across space.
`fetch_model.py` prints a `[KIT_INFO]` line on delivery — a clear
`LIKELY A MODULAR KIT` for obvious ones, or a neutral part-count for
ambiguous ones (a coffee cart with mugs on it places whole). Read it with
the preview.

**`globalThis.loadKit(gltf)`** returns each part cloned and re-centered to
its own origin (bbox-centered in XZ, resting on Y=0), ready to place:

```js
const loader = new globalThis.GLTFLoader();
const gltf = await new Promise((resolve, reject) =>
  loader.parse(b64toArrayBuffer(ASSETS.pipe_kit), '', resolve, reject));
const kit = loadKit(gltf);
kit.list();                                  // ['pipe_elbow_01', 'pipe_valve_03', ...]
const elbow = kit.get('pipe_elbow_01');      // a Group at origin
placeOn(elbow, ground, { xz: [2, 0] });
kit.family('pipe_valve').forEach((valve, i) =>
  placeOn(valve, deck, {xzOffset: [i * 0.3, 0]})); // space by measured part dimensions
const elbow2 = kit.get('pipe_elbow_01');     // pull again — source is never mutated
// kit.islands() groups spatially-connected parts (a multi-mesh plant comes
// back as one object) when you'd rather grab whole sub-objects.
```

**Snap pieces together with `placeTouching`** so they meet instead of
floating apart — parts come re-centered to origin, so you spread and join
them:

```js
placeOn(panelA, ground, { xz: [0, 0] });
placeTouching(panelB, panelA, 'right');           // B's left face meets A's right face
placeTouching(roof, panelA, 'above', { gap: -0.02 }); // bite in 2cm for a tight seam
```

It raycasts real geometry, so it's accurate where bbox-based `placeAgainst`
would leave a gap — the difference between a kit reading as one built
structure and a pile of disconnected parts.

**Combine pieces across kits.** A unique building = wall panel from kit A +
window frame from kit B + door from kit C + awning from kit D + paint from
`ProceduralMaterials.createWornMetal`. Five models whose pieces combine into
your scene beats hunting for the one perfect model (which usually doesn't
exist).

For the robotics library use [RoboticsKit.loadPart and module ports](robotics.md)
instead: that loader preserves the authored joint hierarchy and supports
triangle-owned parts inside batch meshes. Generic `loadKit` recenters kit
objects for ordinary set dressing.

## Housekeeping

Keep reusable sources and useful studies. A model not used by the current
scene can remain in its working project or shared cache. Remove unused entries
from that scene's config when they are unnecessary, and name experiments so
their purpose is clear. The runner's nearby-model warning is a heuristic:
check whether an intended prop was omitted, rather than deleting files just
to silence it. Preserve local source work and collaborators' assets.
