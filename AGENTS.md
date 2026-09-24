# Eidoverse — Agent Guide

Eidoverse is a collection of useful tools for **creating and rendering
three.js videos in Deno, at real-time speeds, with absolutely minimal CPU
usage**. Everything renders on the GPU — WebGPU + NodeMaterial/TSL
throughout, no per-frame CPU loops, no baking — and the toolkit layers
simulation (fluids, water, cloth, particles), procedural builders
(creatures, robots, terrain, materials), a character controller,
audio generation, and post effects on top of that base. You are working in
this repo alongside a human collaborator; what to make comes from the
conversation.

Read this file completely before doing anything else. It is the single
agent-facing contract for the whole toolkit: the API, the production rules,
and the hard-won anti-patterns live here.

The goal for any video is a **finished produced short** — not a render
smoke test, not an isolated 3D clip. A complete piece of media: 3D scene +
(optionally) character + audio + motion graphics + a story arc that fills
the runtime.

**Rendering:** `python eido.py render <scene.json>` — native Deno + your
GPU, no containers. Iterate with single-frame probes (`--probe`) before
committing to full renders, and don't run two sustained renders
concurrently.

**Audio capabilities:** `generate_song.py` / `generate_sfx.py` need a
reachable ComfyUI backend — confirm with `python generate_song.py --probe`
(exits 0/1 in seconds). No ComfyUI → build the mix from edge-tts narration
(+ ffmpeg-synthesized ambience) or user-supplied audio. Never fake a tool
invocation; degrade honestly.

**Scratch space:** all your work goes in `work/<short_id>/` —
scene files, fetched assets, audio, intermediates, and the final mp4.
The engine files under `eidoverse/` are the canonical library every scene
shares — edit copies in `work/`, and change the engine itself only as a
deliberate, discussed decision.

## Duration — decide from the format, then fill it

Pick the runtime from the format before you build, and make the whole
piece earn it:

- **Landscape:** 45–90 seconds.
- **Portrait:** 60–120 seconds.
- **Music video:** the full length of the generated song.

Set `scene.json` `duration` to the runtime you chose, and build a 4–6
phase arc — intro, build, climax, resolve — with the camera moving
through it. The piece evolves across the whole runtime rather than holding
one shot.

Spread the narration evenly across the entire timeline, with a closing
line near the end, so the back half carries voice rather than bare music.
Set `duration` to at least the length of your mixed audio so the full
narration plays; the merge step keeps the audio intact.

If time is short, ship a simpler piece that still fills the format range —
one strong scene that runs the full minute beats an ambitious fragment.

## Mandatory production rules

These are non-negotiable — they are the difference between a finished
piece and a render test.

1. **Audio is required, fills the entire runtime, in correct mix balance.**
   - Generated music or instrumental bed (`generate_song.py`, when ComfyUI is available)
   - Plus TTS narration (`edge-tts` → `cyborg_voice.py` / `cyborg_stutter.py`) OR procedural SFX
   - **Voice 6-9 dB ABOVE the music bed** — never below
   - Audio runs from t=0 to end with no silent stretches; never front-loads narration and trails off into bare music

2. **Asset sourcing comes before procedural geometry.** Before building
   anything from primitives, in this order. The fetchers write their
   downloads into the **current directory**, so run them from your piece's
   folder (`cd work/<id>` — the commands below assume it, two levels under
   the repo root); they find the local model library and the preview
   renderer relative to their own location, not the current directory.
   - `python3 ../../fetch_model.py "search terms"` — searches local custom models + Poly Haven + Smithsonian + NASA + NIH 3D **all at once, in parallel**, ranks every candidate across all sources, and delivers the best one (printing the runners-up from every source). **READ the preview before placing the mesh** — verify orientation + scale by using visible features plus the colored axis labels (+X red, +Y green, +Z blue).
     - **ALWAYS pass `--theme "<your piece's mood/setting>"`** so the pick fits your video, e.g. `fetch_model.py "car" --theme "cyberpunk neon dystopia"` or `fetch_model.py "vase" --theme "ancient cracked archaeological relic"`. Theme fit is **semantic** — an embedding model scores how well each candidate matches your setting by meaning, not keywords, so phrase the theme naturally (paraphrases, mood words, eras all work). The theme RE-RANKS the relevance-matched candidates: a damaged car floats up for a dystopia and sinks for a vintage showroom. It never promotes an off-query item (a clock won't win "chair") — it only reorders genuinely-relevant ones. *(Theme ranking uses `EIDOVERSE_EMBED_URL`/`EIDOVERSE_EMBED_MODEL`/`EIDOVERSE_EMBED_KEY` — any OpenAI-compatible `/v1/embeddings` endpoint, defaulting to Jina's free tier via `JINA_AI_KEY`; with no key it degrades to relevance-only, never errors.)*
     - **LOCAL models are referenced IN PLACE — never copy them.** When the match is a local/custom model, fetch_model prints `Local model (referenced IN PLACE — not copied): <absolute path>`. Put **that exact absolute path** into your `scene.json` `assets` (the engine loads any path). Do NOT copy the `.glb` into your work folder — duplicating multi-MB meshes per scene bleeds the disk. (Downloaded models land in the current directory with their `_preview.jpg` beside them: a Poly Haven model as `<model_id>_embedded.gltf` (textures inlined, 1k), a Smithsonian, NIH 3D or NASA model as `<name>.glb` (names lowercased, other characters → `_`) — those you keep locally.)
     - **Every download writes a licence sidecar** beside the model: `<model file stem>.license.json` (so `<model_id>_embedded.license.json` for Poly Haven), recording `source`, `file`, `id`, `url`, `license`, `license_url`, title/author where the source exposes them, and the fetch date. Read it before redistributing. Poly Haven is `CC0-1.0`; Smithsonian entries are marked `unverified` (CC0 only when the object page says Open Access, otherwise the Smithsonian Terms of Use); NIH 3D licences vary per submission and read `unknown` when the entry lists none; NASA carries the NASA media usage guidelines. Local models are referenced in place and get no sidecar.
     - **The preview is best-effort.** A missing Deno/ffmpeg, a timeout or a renderer crash skips `_preview.jpg` with a message; the model is still delivered.
     - Browse the whole local catalog without fetching: `python3 fetch_model.py --list-local` (from the repo root) prints every local model's path + dims + preview. Reference straight from there.
     - It also prints an **`[ORIGIN_INFO]`** line saying where the model's pivot `(0,0,0)` sits in its bbox — **BASE** (y=0 is the bottom; rests directly on a surface), **CENTERED** (y=0 is mid-height; add half the height to stand it on a floor), **TOP**, or **OFFSET**. Do NOT assume the pivot is the geometric center — many GLBs are base-pivoted and a "centered" `position.y` floats or sinks them. The safe move is always `placeOn`/`placeAgainst` (they seat the bbox regardless of pivot); read `[ORIGIN_INFO]` only when you must set `position.y` by hand.
     - **It auto-picks the best match but PRINTS the alternatives spanning EVERY source** with the exact token to re-fetch each. The run also prints the full ranked candidate table (`rel=` relevance, `sim=` semantic theme similarity, `×` the theme multiplier, `→` combined score). If the preview isn't the variant you wanted — wrong colour, wrong type, wrong style — **re-fetch a specific one by its exact name/id**, e.g. `fetch_model.py "server_rack_01"`. Don't settle for the auto-pick when a listed alternative is the right one.
   - `python3 ../../fetch_hdri.py "search" [resolution]` — environment lighting. `resolution` is `1k` (default), `2k`, `4k` or `8k`; the query may also be an exact Poly Haven or AmbientCG ID. Searches Poly Haven + AmbientCG; on an equal match score Poly Haven wins (native `.hdr`, no conversion). Required for any 3D scene that isn't a flat indoor stage. Outputs `hdri.hdr` (+ a legacy `hdri_b64.txt` sidecar you ignore) in the current directory. AmbientCG HDRIs come as OpenEXR; `fetch_hdri` converts them to Radiance `hdri.hdr` without tonemapping (needs `ffmpeg`, `ffprobe` and numpy). If it can't convert, it writes `hdri.exr` instead, tells you to load that with three's `EXRLoader` (not `RGBELoader`/`HDRLoader`) or pick a Poly Haven HDRI, and exits 2. Point the `hdri` asset at the raw `hdri.hdr`.
   - `python3 ../../fetch_texture.py "material" [resolution]` — PBR sets (basecolor + roughness + normal + AO + metalness + displacement) from Poly Haven + AmbientCG + TextureCan (all CC0). `resolution` is `1k` (default), `2k`, `4k` or `8k`; the query may also be an exact Poly Haven or AmbientCG ID, or `texturecan:<id>`. Required for every procedural surface. Outputs `tex_urls.json` — Poly Haven entries are CDN URLs; AmbientCG/TextureCan maps are extracted into the current directory and their entries are absolute local paths the engine reads directly. **Fetching is step 1 of 2.** Step 2 is loading them onto your material — flat colors on procedural geometry is a bug. Pattern:

     ```js
     // 1) Download each tex_urls.json URL to assets/, declare in config.assets
     //    as <name>_albedo / _nor / _rough / _metal (raw image bytes).
     // 2) In setup(), load with globalThis.loadImageTexture — NOT TextureLoader.
     //    (TextureLoader's blob-URL path HANGS on this deno+wgpu stack; the
     //    helper decodes via Deno's native createImageBitmap instead.)
     const albedo = await globalThis.loadImageTexture(ASSETS.concrete_albedo, { srgb: true });
     const nor    = await globalThis.loadImageTexture(ASSETS.concrete_nor);     // linear (default)
     const rough  = await globalThis.loadImageTexture(ASSETS.concrete_rough);   // linear
     const metal  = await globalThis.loadImageTexture(ASSETS.concrete_metal);   // linear
     albedo.repeat.set(8, 8); nor.repeat.set(8, 8); rough.repeat.set(8, 8); metal.repeat.set(8, 8);
     const floorMat = new THREE.MeshStandardNodeMaterial({
         map: albedo, normalMap: nor, roughnessMap: rough, metalnessMap: metal,
     });
     ```

     The four maps are the minimum for procedural surfaces. If you wrote `new THREE.MeshStandardNodeMaterial({ color: 0x... })` for the floor / wall / ground / anything not loaded as a GLB, you skipped step 2. `globalThis.loadImageTexture(bytes, { srgb })` also loads ANY image into a texture — use it for screen content, decals, logos, projected images, sprite sheets — anywhere you'd reach for `TextureLoader` in a browser. (Brand/logo art: use real transparent PNGs declared as assets — a hand-rolled procedural approximation of a logo reads as off-brand.)
   - **Never refetch a cached asset.** Cache locally; downloading the same `wooden_bowl_01.gltf` twice is a tell.

   **Kitbash hard. Run `fetch_model.py` MANY times per scene, not once.**
   A scene reads as a real place when its geometry is dense and varied.
   Sparse scenes — one prop in frame, flat ground, empty walls — read as
   1999 tech demos regardless of how good the lighting or camera work is.
   Real production density is ten to twenty distinct visible meshes
   *before* counting clutter and architecture: a street is a car +
   traffic cones + fire hydrant + mailbox + newspaper box + streetlamp +
   potted plants + trash can + bike rack + sidewalk grate + posters on
   the wall + a paper bag in the gutter. A room is desk + chair + lamp +
   bookshelf + books on it + a mug + a discarded sweater + a plant in
   the corner + framed art on the wall + a rug + something half-visible
   through the doorway. An outdoor establishing shot is hero terrain
   chunk + scattered rocks + grass/shrub strokes (createFlora) + a tree or two
   (GROW them — makeSeedTree, never a gray-box or a mismatched GLB) + a path +
   distant silhouettes + clouds + atmospheric haze. Each is its own
   `fetch_model.py` call. Read each `_preview.jpg`, place with
   `placeOn` / `placeAgainst` / `snapToGround` — never raw coords. Reach
   for MORE, not less.

   > **EXAMPLES ARE ILLUSTRATIVE — DO NOT COPY THEM VERBATIM.** Every code
   > block in this doc and in `eidoverse/examples/` shows you the *API shape
   > and wiring*, not a scene to reproduce. Take the wiring; **throw away the
   > content.** The subject, palette, props, camera moves, parameters, and
   > composition in an example are placeholders — reproducing them is the #1
   > cause of samey, interchangeable videos and it means you skipped the
   > actual job: adapting the tool to YOUR piece. A pour example pours into a
   > glass; your scene might pour lava down a statue. Same API, different
   > everything. If your scene looks like the example, you copied instead of
   > created.

   **Weave SHOWPIECES through the production.** These are per-BEAT tools,
   not a once-per-video garnish: a full multi-shot story has room for a
   pour in one scene, cloth in the wind in another, a particle morph as a
   transition, water under the final shot. "At least one" is the floor,
   not the ceiling. The menu (each verified, deep docs in their own
   sections below; pick what the story's beats call for, combine freely):
   - `fluid_swe` — shallow-water heightfield liquid over any terrain bed:
     mass-exact fills, pours with stream tubes + droplet spray + foam
     (whitewater generated from the field's own state), body coupling with
     entry splashes and wakes. The pond/pool/spring workhorse (~2.8 ms in a
     full scene).
   - `cloth_sim` — flags, banners, capes, curtains with wind + colliders.
   - `makeParticleMorph` — dissolve a mesh/VRM into particles and reform it
     as something else (the signature transition). **ANY mesh OR TEXT can be
     the frame**: `ParticleMorph.fromMesh(anything, count)` samples a prop /
     fetched GLB / VRM captured mid-pose (`updateTarget` at the dissolve), and
     **`ParticleMorph.fromText('WORD', count, {width:6})`** makes a cloud spell
     a word or logo in ONE call — **`{ ascii: true }`** reforms multi-line
     **ASCII ART** into particles (a face, a sigil, a diagram, an ASCII portrait
     in 3D space). Chain targets for a whole beat: VRM → galaxy → the word →
     ASCII glyph → scatter.
   - `makeParticles` — sparks/embers/smoke/snow/magic, GPU sprites.
   - `makeAsciiPanel(asciiText, opts)` — multi-line ASCII art / monospace text
     → a glowing terminal-screen mesh (CRT / HUD / server readout / boot
     sequence / code wall). You're good at ASCII art — draw a face, a logo, a
     diagram, a sigil — and mount it on any monitor; pair with the `crt` /
     `glitch_bars` effects. (Big figlet banners: generate via `pyfiglet` in a
     python pre-step, pass the string in.)
   - `sdf_raymarch_loader` — placeable raymarched objects (blobs, fireballs,
     impossible materials) that occlude correctly, plus volumetric smoke/fire
     via `createSdfVolume` (`smoke`, `flame`, `explosionRing` examples).
   - **Curve-follow (`Flow`)** — make a MESH run/flow ALONG a 3D curve, animated.
     Built into three-webgpu (GPU-accelerated: bakes the spline into a texture +
     deforms in the vertex shader). One import + four calls:
       ```js
       const { Flow } = await import('npm:three@0.184.0/addons/modifiers/CurveModifierGPU.js');
       const curve = new THREE.CatmullRomCurve3(points);   // curve.closed = true for a loop
       const flow = new Flow(mesh);                         // mesh: a NodeMaterial mesh, segmented along its length
       flow.updateCurve(0, curve);
       _s.add(flow.object3D);                               // add THIS, not the original mesh
       // per frame: flow.moveAlongCurve(0.0015);           // scrolls the geometry along the path
       ```
     Material MUST be a NodeMaterial (`MeshStandardNodeMaterial` etc.) and the
     geometry needs SEGMENTS along its length to bend smoothly (a 1-segment box
     won't). Great for: 3D TEXT snaking down a path / wrapping a logo, ribbons,
     banners, a snake / train / centipede, conveyor parts, energy running down a
     cable, pipes-with-flow. (For PARTICLES or a CAMERA on a path you do NOT need
     Flow — sample the curve directly: `curve.getPointAt(t)` / `getTangentAt(t)`.)
   - `makeCreature` — Spore-style procedural creatures: spine+limbs auto-rig,
     morphology-adaptive gaits (human walk / trot / path-following slither /
     tripod insect / spider / flight with banking), animal faces (muzzles,
     ears, tusks, horn styles), typed feet, accessories (hats/ties/shades),
     robots, seeded randoms.
   - SPOM relief — real CARVED depth + a silhouette that follows the relief. `createReliefColumn` for CURVED surfaces (columns/pipes whose flanges overhang the outline); `createParallaxMaterial` for FLAT surfaces (brick / stone / tile / tread / panel). The height field is `fetch_texture`'s **`displacement`** map. The single most under-used surface showpiece; deep docs below.
   - The world-space sky system (day cycles, storms, cloud shadows) or the `nuclear_explosion` blast.
   - A `VRMCharacterController` walk with terrain (stairs, ramps) — real
     locomotion reads better than any teleport.
   - `makeTerrain` — procedural heightfield ground with multi-texture blending
     (height + slope + noise, baked as vertex paint). FLAT PlaneGeometry ground
     is the tech-demo tell; undulating terrain with grass→dirt→rock blending is
     one call. `terrain.heightAt(x,z)` gives exact ground height anywhere;
     `flatRadius` keeps a level clearing for staging the action.
       const terrain = makeTerrain({ size: 80, amplitude: 3, seed: 7, flatRadius: 8,
           layers: [{ map: grass, repeat: 18 }, { map: dirt, repeat: 14 }, { map: rock, repeat: 10 }] });
       scene.add(terrain.mesh);
   - `createFlora` — the VEGETATION BRUSH (the textured-ground partner to
     makeTerrain — lay plants ON TOP of it): asset-driven species with real
     PBR map sets, GPU-instanced, self-animating wind, character pushers.
     Grass carpets, desert bunch grass, three Mojave shrubs, yucca, full
     corn plants. Circular/organic stands or planted rows; seasonal color.
       const f = await createFlora({ species: 'grass', size: 30,
           height: 0.45, color: 'emerald', heightFn: terrain.heightAt });
       scene.add(f.mesh);   // wind self-animates; f.setPushers([...]) parts it
   - `makeSeedTree` — REAL procedural trees & plants via SeedThree's headless
     agent API (github.com/SkyeShark/SeedThree — same three/TSL stack; a tree
     grown here is IDENTICAL to one grown in the SeedThree app, and presets
     round-trip with its Save/Load panel). SEED-FIRST design: iterate `seed`
     and read `stats` before touching any dial; open knob folders on demand.
       const oak = await makeSeedTree({ species: 'whiteOak', seed: 1737, scene, sunLight: sun });
       console.log(oak.stats.summary);                       // height/width/lod0Triangles
       await makeSeedTree.describe();                        // species menu
       await makeSeedTree.describe('joshuaTree', 'shape');   // ONE folder of dials
     Gotchas (verified): leave `globalThis._autoFixPlacement` unset in tree
     scenes — the opt-in placement repair pass dismembers
     intentionally-overlapping tree geometry (`makeSeedTree` warns when a
     scene has opted in; the audits are warn-only by default); trees sway by default (`makeSeedTree.setWind({strength,speed})`);
     judge shadowed trees from frame ≥2. Source: SEEDTHREE_DIR / ../SeedThree /
     ./SeedThree checkout = textured tier; no checkout = GitHub import,
     geometry tier (placeholder materials).

   **Procedural-geometry techniques**, for meshes you build rather than fetch:
   - organic silhouettes = vertex jitter on a low-seg geometry (displace
     `geometry.attributes.position` ONCE at build time with seeded noise — a
     one-time CPU pass at setup is fine; only PER-FRAME CPU loops are banned).
     **Polyhedron geometries (Icosahedron/Octahedron/etc.) are NON-INDEXED** —
     shared corners are duplicated vertices, so naive per-vertex jitter tears
     the mesh into floating shards. Key the jitter by POSITION (a Map from
     `x.toFixed(4)+','+y...` → offset) so duplicated corners move together;
   - kitbash variants: `cloneModel(base)` + non-uniform scale + yaw + material
     swap turns one rock/tree/crate into a field of distinct ones;
   - **`layerSurface(meshes, opts)` — run this on EVERY set you model
     yourself.** Geometry you build arrives clean, and clean is what makes a
     procedural set read as grey-box no matter how good the modeling is. Two
     things are missing and this fixes both in one call (full docs in
     "MAKING BUILT GEOMETRY LOOK BUILT" below):
     - **matched texel density** — `ExtrudeGeometry`'s UVs are already metric
       while `Lathe`/`Cylinder`/`Box`/`Sphere` are normalised 0..1, so the
       same stone comes out crisp on an extruded step and smeared across a
       13 m revolved basin. It rescales the UVs each constructor produced to
       a common metres-per-tile, **keeping** their layout (bevel and boolean
       cut islands stay exactly as generated — only their scale moves).
     - **wear that follows the form** — measures curvature PER PIXEL in the
       shader (screen-space normal derivatives normalised to 1/metres, nothing
       baked) and drives weathering off it: grime in the inside
       corners a boolean made, bleach on convex edges and chamfers, silt at a
       world-space waterline, dust on up-facing planes, triplanar grunge
       breaking all of it up.

   **Layer environments in passes, like a set dresser** — each pass is quick,
   and scenes that skip a layer read hollow:
   1. shell — terrain/floor + walls or sky treatment (env + glow sprites);
   2. anchors — 3-5 big silhouettes that define the place (arch, shelf wall,
      crane, statue);
   3. mid props — clusters via `placeOn`/`placeAgainst` chains (a desk THEN
      its lamp THEN its papers);
   4. detail scatter — `scatterOn` for debris/clutter at the edges;
   5. atmosphere — particles (dust/smoke), fog, 2-4 colored fill lights;
   6. life — something always moving: drifting particles, a flickering sign,
      cloth in wind, a slow vehicle on a `driveAlong` path.

   **Break kit-models apart and use their pieces individually.** Many
   fetched models are KITS / asset-libraries, not finished objects — a
   catalog of parts laid out in a row or grid (modular building kits: wall
   panels, window frames, cornices, doors; pipe kits: elbows, straights,
   valves, T-junctions; plant packs: several plant variants side by side).
   Dropping the whole `gltf.scene` into the world drops all those pieces
   scattered across space.

   **`fetch_model.py` TELLS you when a model is a kit** — it prints a
   `[KIT_INFO]` line on delivery: `LIKELY A MODULAR KIT / ASSET-LIBRARY: N
   named parts …` for clear kits, or a neutral `N named parts (…) — could be
   a finished assembly OR a small set, judge from this preview` for ambiguous
   ones (a few distinct parts, e.g. a coffee cart with mugs on it — that one
   you place whole). Read it, and read the `_preview.jpg`.

   **Use `globalThis.loadKit(gltf)` to work with the parts** — it returns each
   part CLONED and re-centered to its own origin (bbox-centered in XZ, resting
   on Y=0), ready to `placeOn` / array / combine. Don't hand-roll
   `getObjectByName` + `child.visible=false` + transform-juggling — the raw
   scene-graph children sit at their catalog positions; `loadKit` neutralizes
   that for you.
   ```js
   const gltf = await loadGLB(ASSETS.pipe_kit);
   const kit = loadKit(gltf);
   kit.list();                                  // ['pipe_elbow_01', 'pipe_valve_03', ...]
   const elbow = kit.get('pipe_elbow_01');      // a Group at origin
   placeOn(elbow, ground, { xz: [2, 0] });
   for (const v of kit.family('pipe_valve')) placeOn(v, deck, ...);  // all valve_* parts
   const elbow2 = kit.get('pipe_elbow_01');     // pull it again — source is never mutated
   // kit.islands() groups parts that are spatially together (a multi-mesh plant
   // comes back as one object) if you'd rather grab whole sub-objects.
   ```
   Detaching individual pieces and arranging them is how you make the
   unique building / pipework / fence / facade your scene needs. (`kit.get()` returns `null` for
   an unknown name; a model that isn't a kit just has one part.)

   **Snap the pieces together with `placeTouching`** so they actually meet
   instead of floating apart or overlapping (the pieces come re-centered to
   origin, so they all start stacked at one spot — you spread + join them).
   Place the first piece, then slide each next piece against the previous one
   until their meshes kiss:
   ```js
   placeOn(panelA, ground, { xz: [0, 0] });
   placeTouching(panelB, panelA, 'right');           // B's left face meets A's right face
   placeTouching(roof, panelA, 'above', { gap: -0.02 }); // seat the roof, biting in 2cm for a tight seam
   ```
   It raycasts real geometry, so it's accurate where bbox-based `placeAgainst`
   would leave a gap. This is the difference between a kit that reads as one
   built structure and a pile of disconnected parts.

   **Combine pieces across kits.** A unique building =
   wall panel from kit A + window frame from kit B + door from kit C +
   awning from kit D + paint from `ProceduralMaterials.createWornMetal`.
   Reach for five models whose pieces, combined, make your scene — that's
   a better strategy than searching for the one model that perfectly
   matches everything (which usually doesn't exist).

   **Layer procedural detail onto fetched bases.** Poly Haven textures
   give you a clean PBR start; `ProceduralMaterials.composite(base,
   scratches, 'multiply')` adds wear / weathering / age on top so
   surfaces look used rather than catalog-fresh. For surfaces without a
   Poly Haven match, the `ProceduralMaterials` factories
   (`createPaintedMetal`, `createRubber`, `createSkin`, `createScaly`,
   `createFabric`, `createWornMetal`) produce NodeMaterial output with
   basecolor + roughness + metalness + normal — required minimums.

   **Parametric geometry constructors.** Each takes a curve, a profile, a
   flat outline, or a repeated unit and generates the surface from it.
   (`Loft` / `LoftGeometry`, documented below, is the general case — it
   skins a surface through arbitrary cross sections.)
   - `TubeGeometry(curve)` — pipes, cables, vines, tentacles, snakes,
     winding paths, hair strands. Build the curve from any sequence of
     points (`CatmullRomCurve3`, `QuadraticBezierCurve3`).
   - `LatheGeometry(profilePoints)` — vases, bottles, columns,
     chess pieces, anything radially symmetric. Sketch the silhouette
     as a 2D point list, rotate.
   - `ExtrudeGeometry(shape, { depth, bevelEnabled })` — signs, letters,
     building blocks from floor plans, embossed plaques.
   - `ParametricGeometry((u, v, t) => new Vector3(...))` — any
     mathematically defined surface (Möbius strips, twisted columns,
     Klein bottles, organic blobs).
   - `InstancedMesh(geom, mat, count)` — the same unit repeated many times
     (200 boards in a stack, a wall of windows, a grid of light bulbs). Set
     per-instance matrices in `setup()` — one-time; per-frame goes through
     TSL compute.

   **Booleans — `three-bvh-csg`** (mapped in `deno.json`; peers on the same
   `three@0.184.0` and `three-mesh-bvh@0.9.10` the engine uses). Union,
   subtract and intersect real solids: cut openings, hollow a shell, chamfer
   an edge against a rounded solid, difference two forms into a third.
   Verified on this stack — the result is indexed, carries `normal` and `uv`,
   and the engine's WebGPU classes consume it directly.

   ```js
   // scene scripts are eval'd — dynamic import(), never a top-level import
   const { Brush, Evaluator, ADDITION, SUBTRACTION, INTERSECTION }
       = await import('three-bvh-csg');

   const body = new Brush(new THREE.BoxGeometry(1, 1, 1));
   const bore = new Brush(new THREE.CylinderGeometry(0.3, 0.3, 2, 32));
   bore.position.set(0, 0, 0);
   body.updateMatrixWorld();  bore.updateMatrixWorld();   // ⚠ REQUIRED

   const ev = new Evaluator();
   ev.useGroups = false;                       // one material out
   const result = ev.evaluate(body, bore, SUBTRACTION);   // returns a Mesh
   result.material = new THREE.MeshStandardNodeMaterial({ roughness: 0.5 });
   result.geometry.computeVertexNormals();     // after a chamfer/bevel cut
   scene.add(result);
   ```

   - Operations: `ADDITION` `SUBTRACTION` `REVERSE_SUBTRACTION`
     `INTERSECTION` `DIFFERENCE` `HOLLOW_SUBTRACTION` `HOLLOW_INTERSECTION`.
   - ⚠ **`updateMatrixWorld()` on every brush before `evaluate`** — a brush's
     transform is read from its world matrix, so an un-updated brush cuts
     from the wrong place (or not at all).
   - ⚠ **Brushes must carry the SAME attribute set.** Mixing a geometry that
     has `uv` with one that doesn't produces garbage or throws — strip or add
     attributes so both match before evaluating.
   - ⚠ **Closed solids only.** An open shell or non-manifold mesh has no
     well-defined inside, so the boolean result is undefined. Cap your lathes
     and extrusions.
   - ⚠ **This is CPU work — do it ONCE in `setup()`.** Per-frame booleans
     violate the no-CPU-loop rule and will not hold framerate. For animated
     boolean-looking cuts use SDF (`sdf_raymarch_loader`) or `makeIsoField`,
     which march on the GPU.
   - Reuse one `Evaluator` across many operations; chain by feeding a result
     back in as a `Brush(result.geometry)`.
   - `useGroups = true` preserves each brush's material as a group instead of
     flattening to one. `computeMeshVolume(geometry)` is also exported.

   ### MAKING BUILT GEOMETRY LOOK BUILT (`eidoverse/surface_layers.js`)

   A fetched GLB arrives with authored UVs and wear baked into its maps. A
   lathe revolve, an extruded moulding and a boolean cut arrive **clean**, on
   **four different UV scales**, with no dirt in any corner. That — not the
   modeling — is why hand-built sets read as grey-box. Four globals fix it;
   `layerSurface` is the one-liner that runs all of them.

   ```js
   globalThis.layerSurface(myMeshes, {
       metresPerTile: 1.15,                 // one texture tile per 1.15 m, on everything
       grunge: { scale: 0.55, seed: 7 },
       layers: [
           { mask: 'cavity', scale: 0.75, color: 0x2b2419, roughness: 1.0, amount: 0.9, range: [0.15, 0.72], grunge: 0.35 },
           { mask: 'edges',  color: 0xc9bda0, roughness: 0.62, amount: 0.6, range: [0.20, 0.72] },
           { mask: 'up',     color: 0x8a7859, amount: 0.38, power: 3, grunge: 0.8 },
           { mask: 'below',  y: WATERLINE, fade: 0.5, color: 0x11423c, roughness: 0.55, amount: 0.85 },
       ],
   });
   ```

   **Masks** (each remapped through `range: [a, b]`, scaled by `amount`,
   optionally broken up by `grunge: 0..1`):

   | mask | driven by | use it for |
   |---|---|---|
   | `cavity` | baked raycast AO | grime, moss, soot — the workhorse |
   | `crease` | concave curvature | sharp dirt lines in inside corners |
   | `edges` | convex curvature | polish, chipping, bleached exposure on chamfers |
   | `up` | `normalWorld.y^power` | dust, silt, ash, snow |
   | `slope` | `1 - abs(normalWorld.y)` | runoff streaking on vertical faces |
   | `below` / `above` | world Y, `y` + `fade` | **waterlines**, tide marks, buried bases |
   | `grunge` | triplanar tiling fbm | breakup on its own |

   ⚠ **These tools are for geometry you BUILT, and they refuse fetched
   assets** — GLBs, VRMs and kit parts carry an authored UV unwrap
   corresponding 1:1 to their own texture (or a shared atlas/trim sheet), so
   rescaling their UVs makes every island sample outside the region it was
   unwrapped onto and the model comes out as confetti. `GLTFLoader` output is
   stamped `userData._loadedAsset`; skinned meshes, morph-target meshes and
   MToon materials are refused on top of that. Skipped meshes are NAMED in the
   log, so handing over a whole scene root is safe — it just weathers nothing.

   - **`normalizeTexelDensity(meshes, { metresPerTile })`** measures each
     mesh's real UV-per-metre (median over triangles, via `matrixWorld`, so a
     kitbashed `.scale.setScalar(1.7)` clone is measured at the size it
     appears) and scales its existing `uv` to a common target. It **keeps the
     constructor's UV islands** — a world-space *reprojection* would throw
     away the bevel and cap layouts `ExtrudeGeometry`/CSG generate and seam
     badly on anything not axis-aligned. It warns if a material's texture
     `repeat` isn't 1, because that multiplies on top and undoes the work.
   - **The curvature masks are PER-PIXEL TSL — nothing is baked.** `curv` comes
     from screen-space derivatives of the world normal, each divided by the
     squared length of the matching position derivative, which puts it in
     1/metres so the mask does not swim as the camera dollies. Give each layer
     a `scale` in metres for the feature size it should answer to (0.6 for a
     broad hollow, 0.05 for a tight crease). ⚠ Derivatives are taken WITHIN a
     triangle, so a bevelled/filleted edge gives a clean gradient while a HARD
     boolean corner with split normals gives only a thin line — model the
     fillet (`bevelEnabled: true`) if you want dirt to collect there.
   - **`makeLayeredMaterial({ base, layers, grunge })`** if you want the
     material without the baking, and **`grungeTexture(size, seed)`** for the
     seamlessly-tiling fbm on its own.
   - `normalizeTexelDensity` is geometry authoring — one attribute write at
     build time, same class as `computeVertexNormals()`/`computeTangents()`.
     The masks are pure GPU. Call it AFTER the group is positioned, since the
     density measurement reads `matrixWorld`.


   **Compose environments in layers, near-to-far.** A finished
   environment has all of these — a scene missing one reads incomplete:
   1. **Hero geometry** — the scene's central object (a desk, altar,
      vehicle, fountain, stage).
   2. **Mid-ground dressing** — clutter and props that establish the
      world (papers, mugs, tools, signs, debris, plants, the small
      stuff a real place accumulates).
   3. **Architecture** — bounding walls, floors, ceilings, columns,
      doorways, the framing geometry, all PBR-textured (no flat colors).
   4. **Atmosphere** — volumetric haze (`scene.fog = new THREE.FogExp2(...)`
      or the `depth_fog` effect for interiors; the WORLD-SPACE SKY SYSTEM
      for outdoor skies), light shafts, fog for distance.
   5. **Sky / horizon** — HDRI environment lighting always. An outdoor sky
      with clouds comes from the **sky system** (`eidoverse/sky_system.js` —
      see the "WORLD-SPACE SKY + WEATHER" section): raymarched clouds living
      IN the world, so geometry occludes them natively; sun/moon/stars,
      time-of-day palette, cloud types, day cycles, weather states via
      `eidoverse/weather_system.js`. `SkyMesh` is the plain gradient dome
      for a clear, cloudless sky. For sci-fi interiors, distant silhouettes
      seen through windows / vents / portals.

   Each layer is its own fetch + materials + composition step. Run
   through the list as a checklist before the first full render.

   **Models are at real-world scale by default.** A fetched laptop is
   ~0.3m wide, a chair is ~1m tall, a car is ~4.5m long, a building is
   tens of meters. DO NOT scale models up "to make them prominent" —
   that's how a laptop ends up the size of a billboard and the rest of
   the scene looks miniature next to it. Frame prominence comes from
   the CAMERA (move closer, lower FOV) or from POSITIONING (centered,
   well-lit), not from inflating the mesh. The only legitimate reason
   to resize a fetched mesh is a unit-confusion case — some pipelines
   author in centimeters and ship at 100× real-world; the `_preview.jpg`
   dimensions tell you (e.g. a "laptop" reading 30m × 0.2m × 23m is
   clearly cm-authored and needs `.scale.setScalar(0.01)`). Anything
   already at plausible meter-scale should be placed unscaled.

   **Place with intent-based primitives, never raw `(x, y, z)`.** A
   model's `position` is its origin, NOT its visible edge or its centroid
   — sometimes a corner, sometimes the front face, sometimes an arbitrary
   studio-pivot. Eyeballing coordinates gives you chairs embedded in
   tables. Use the engine's placement helpers (in `globalThis`, no
   import needed) — each one accounts for both objects' real bounding
   boxes and raycasts the geometry where it matters:

   - `placeOn(obj, target, { xz, yOffset, xzOffset, grid, surfaceEps, sink })`
     — sit obj's bbox-bottom on the highest sampled support under its
     footprint AND center obj's bbox at the xz anchor (both axes are
     bbox-corrected, so an off-center loader pivot is handled). The default
     `xz: 'auto'` keeps an already nonzero XZ position and otherwise
     centers on the TARGET — so an object left at the origin piles up at
     the floor's center (the "furniture blob"). Pass your spot explicitly:
     `placeOn(obj, floor, { xz: [x, z] })`. The target may be the scene or
     a group that contains obj — obj's own subtree is excluded from the
     supports, so it never lands on itself. `grid` controls footprint
     sampling (default 7); `surfaceEps` (default 0.0006 m) lifts the object
     a sub-millimetre off the support to avoid coplanar z-fighting — pass
     `0` for exact contact. `sink` buries that fraction of the object's
     bbox height into the surface (clamped to 0–0.9; 0.15–0.35 suits rocks)
     and sets `userData._sunkPlacement`, which exempts the object from the
     hovering audit. And READ the
     `*_preview.jpg` fetch_model emits (dimensions + axis guides) BEFORE
     placing. placeOn/snapToGround also record
     `obj.userData._supportTarget = target` — **support-chain memory** the
     audits honor: checkClipping won't separate an object from what it was
     seated on (resting contact is not clipping), and checkHovering verifies
     a seated object against its recorded support before flagging it. Net
     effect: stacked placements (books ON a table, props ON a shelf board)
     survive the audits. xz: `'auto'` (default) | `'centered'` | `'random'`
     | `[x, z]` (absolute world). `xzOffset: [dx, dz]` nudges the object on the
     surface — use it instead of writing `obj.position.x/z` yourself (a raw
     write puts the model's arbitrary ORIGIN at that coord, re-introducing
     the off-to-the-side bug). The workhorse for "vase on table", "laptop
     on desk", "monitor on shelf", "character on floor". Reads the
     post-rotation bbox, so set `obj.rotation` BEFORE calling.
   - `placeAgainst(obj, ref, side, gap)` — clearance-aware side
     placement. side: `'front' | 'behind' | 'left' | 'right' | 'above' |
     'below'`. gap is the *real visible* clearance between the two
     bbox edges in meters, regardless of where either origin sits.
     For "chair behind desk", "lamp left of monitor". Uses BBOXES — fast,
     but an odd origin or a concave leading face can leave a visible gap.
   - `placeTouching(obj, target, side, { gap, dir, grid, allowIntersect })` —
     the **mesh-accurate** sibling of `placeAgainst`: it raycasts obj's
     leading face against the target's ACTUAL geometry and slides obj along
     ONE axis until the two surfaces just KISS (or `gap` apart). `side` is the
     direction obj TRAVELS toward the target — `left(-x) / right(+x) /
     front(+z) / behind(-z) / above(+y) / below(-y)` (or pass an explicit unit
     `dir: [x,y,z]`). **This is the tool for ASSEMBLING anything out of
     pieces** — kit parts, several separate models, or your own procedural
     meshes — so they touch flush instead of floating apart or
     interpenetrating. Returns `true` on contact, or `false` + a warning if
     no target surface lies that way (then fall back to `placeAgainst`/hand
     coords). `gap: -0.02` bites in slightly for a seam; `allowIntersect:
     true` also tags obj so the clipping audit ignores it.
   - `snapToGround(obj, groundMeshes, { yOffset, below })` — drop obj to
     whatever surface is directly below its origin's **world-space** xz, so
     it works under an offset parent. Handles stairs, slopes, terraced
     floors automatically. Pass the array of walkable meshes; the list may
     include the scene or a group containing obj (obj's own subtree is
     excluded). For characters on uneven terrain, props on a sloped floor.
     VERIFY the result on fetched-GLTF props (group hierarchies can defeat
     the snap and leave the prop silently airborne): raycast straight down
     from above the bbox centre against the ground mesh, log the
     `bbox.min.y − hit.y` gap, and close anything over ~2 cm (plus a small
     deliberate `sink` so heavy things sit IN the ground, not on its skin —
     rocks and fallen trunks read planted at 0.3–0.6 m deep).
   - `alignToSurface(obj, target)` — rotate obj's +Y to match the
     surface normal under it. For signs on slanted roofs, props on
     slopes, anything that should sit flush on a non-horizontal surface.
   - `scatterOn(items, target, { count, minSpacing, rngSeed, sink, tiltMax })` —
     spread N items across target's TOP footprint in an ORGANIC, random
     layout. Deterministic for the same `rngSeed`. For "rocks on
     terrain", "cans scattered on a desk", "debris on the floor".
     **Rocks/boulders/ruins/stumps must be PARTIALLY BURIED, not balanced
     on the surface** — a bbox-flush rock reads as a placed pebble. Pass
     `sink: [0.15, 0.35]` (fraction of height buried, randomized per item)
     + `tiltMax: 0.3` (random lean). Single hero boulders: `placeOn(rock,
     ground, { sink: 0.25 })` after setting a tilt. NOT for
     books on a shelf — that's an ordered upright row on an *interior*
     board, not a random scatter on the outer top (see the shelf recipe
     below).
   - `findClearSpot(obj, around, { radius, scene })` — search a spiral
     around `around` and return a Vector3 where obj's bbox fits without
     overlapping anything. Use when no specific surface anchors the
     placement and you just need empty space near a point.
   - `checkClipping(scene, { autoFix })` — pairwise bbox intersection
     audit. Runs automatically after `setup()` and REPORTS (skips
     intentional parent/child nesting); only the `_autoFixPlacement` repair
     pass (below) pushes intersecting pairs apart along the
     shortest-overlap axis.
     **It also runs a mesh-accurate DEEP-INTERPENETRATION pass** and prints,
     by name and never truncated:
     `[checkClipping] ⚠ N object(s) substantially INSIDE another …` →
     `  desert_yucca_2 is ~74% inside burnt_car`. This is the signal that
     matters — a whole object ENGULFED by another (a tree inside a car), as
     opposed to the bbox "clipping pairs" list above it, which is mostly
     resting-contact noise (the floor "clips" everything on it). **If you see
     this warning, FIX IT**: move the smaller object's xz to a clear spot
     (`findClearSpot` finds one), or seat it properly with `placeOn` /
     `placeTouching`. It is a DETECTOR — it moves nothing for the engulfed
     case, so the fix is yours. If the overlap is **intentional** (a stake
     driven into the ground, a sword through a body, a prop deliberately
     merged), declare it: `obj.userData.allowIntersect = true` and the
     warning goes away.
   - `checkHovering(scene, { autoFix })` — floating-object audit. Runs
     automatically after `setup()`, descending through a single wrapper
     `root` group to reach your actual props (so wrapping everything in one
     group does NOT hide them). For every placed object it footprint-samples
     the surface below and handles three cases:
       • **near** — a small `0.005–1.0 m` gap above the surface below it
         (the "laptop slightly off the desk" smell) → measured and
         reported (snapped down only by the `_autoFixPlacement` repair
         pass);
       • **far** — floating more than 1 m above the nearest surface;
       • **void** — NOTHING beneath its footprint at all (a prop dumped in
         mid-air by hand-coords — `placeOn` would have put it on something).
     `far` and `void` can't be safely snapped (no/uncertain target) so they
     escalate to `[placement] ⚠ N object(s) are genuinely unsupported …` —
     a hard fail. Objects buried by `placeOn`/`scatterOn` `sink` are
     skipped. **An
     object stays unflagged in exactly three ways:**
       1. it rests at/near ground level (the floor + anything sitting on it —
          auto, no flag);
       2. all its meshes are transparent (glow planes, holograms, light
          sprites — auto-skipped);
       3. you DECLARE it a floater: `obj.userData.noSupportCheck = true`.
     Floating is fully supported — drones, balloons, chandeliers, holograms,
     a character mid-jump — you just confirm the intent with `noSupportCheck`
     so an *accidental* float (the real bug) still gets caught.
   - `faceToward(obj, target, { forward })` — yaw-only aim: rotate obj about
     Y so its nose points at `target` (Object3D | Vector3 | [x,z]). `forward`
     is which LOCAL axis the model's front points along — **read it off the
     `*_preview.jpg` axis guides** ('+z' default; many GLBs are '-z' or '±x').
     Use this instead of guessing `rotation.y = Math.PI/2` style constants —
     wrong-yaw placements (statue facing the wall, TV facing sideways) come
     from guessed yaws.
   - `driveAlong(obj, waypoints, { duration, forward, startTime, loop })` —
     **THE way to move a vehicle / creature / anything elongated.** Returns an
     `update(t)`; call it each frame. Moves obj along a smooth curve through
     the waypoints AND yaws it to face its travel direction — coupled, so it
     can never slide sideways. Never animate a vehicle with a bare
     `obj.position.x = lerp(...)`: the model travels perpendicular to its own
     wheels unless its nose happens to align with that axis. The
     render audit flags this (`[motion] ⚠ RE-RENDER — travelled sideways`);
     intentional lateral slides (conveyor, crab) opt out with
     `obj.userData.noMotionCheck = true`. **Opt-outs are logged by name at
     audit time** — adding one to make a warning disappear is specification
     gaming and it shows: the warning was the bug, fix the heading instead.
     **`forward` is REQUIRED and has no default — there is no universal nose
     axis.** Fetched GLBs vary (+z, -z, ±x); the `*_preview.jpg` axis guides
     exist precisely to tell you which way the nose points — read the preview
     BEFORE driving. For vehicles you BUILD yourself, the house convention is
     **nose along +Z** (then `forward: '+z'` is always correct for your own
     builds). driveAlong cross-checks your declared forward against the
     model's long axis at setup and warns if they're perpendicular — but it
     cannot detect BACKWARDS (no geometry knows which end is the nose); only
     the preview can. **Some models are easy to misread** (a body whose
     headlights look like taillights) — fetch_model prints a curated
     `driveAlong/faceToward forward axis: '…'` line for those, and
     `fetch_model.py --list-local` shows it per model. If a hint is given,
     trust it over your read of the preview.
       // FIRST: open the model's *_preview.jpg and read which axis the nose
       // points along — that value is per-model, never copied from an example.
       const drive = driveAlong(car, [[-8,0],[0,1.5],[6,0]], {
           duration: 30,
           forward: '-x',   // ← from THIS car's preview. YOURS WILL DIFFER.
       });
       // renderFrame: drive(t);   wheels point where it goes, always
   - `stationBeside(obj, machine, { gap, side, forward })` — a worker/machine
     that OPERATES ON something stands BESIDE it facing it. A robot arm does
     NOT stand in the middle of its conveyor; a bartender does not stand on
     the bar. This places obj clear of the machine's working edge (its short
     horizontal axis), base at the machine's floor level, nose aimed at the
     line. The audit flags violations: anything named like a conveyor/belt/
     assembly-line with a tall object planted THROUGH its surface escalates to
     `[placement] ⚠ RE-RENDER` (riding parcels are fine; intentional intrusion:
     `obj.userData.noIntrusionCheck = true`).
       stationBeside(robotArm, conveyor, { gap: 0.3, forward: '+z' });
   - `drawTextFit(ctx, text, { x, y, maxWidth, maxHeight, font, align })` —
     canvas text that FITS its box: measures, word-wraps, and shrinks the font
     until the whole block fits, then draws. Use it for EVERY label/headline/
     ticker you draw into a canvas — raw `ctx.fillText` with a fixed font size
     is how screens ship with cut-off text. Returns `{ fontPx, lines }`; if
     fontPx came back much smaller than you asked, shorten the copy.
     **TEXT-SAFE ZONE + closest-approach rule**: keep important text inside
     the central ~80% of the canvas (≥8% margin each side: maxWidth ≤ 0.84×W,
     x = W/2), because the canvas edge is the FIRST thing lost when the
     camera crops the panel. And if a shot DOLLIES TOWARD a text surface,
     verify the frame at the move's CLOSEST APPROACH, not a mid-move frame —
     once the panel is wider than the frame, edge text clips mid-word.
   - `checkZFighting(scene, { autoFix })` — coplanar-surface audit. Runs
     automatically after `setup()` and reports. A poster,
     screen, label, logo, sign, floor-marking, or any flat panel placed at the
     EXACT depth of the surface behind it (`panel.position.z = wall.z`) will
     Z-FIGHT — the two coplanar faces flicker frame-to-frame because the depth
     buffer can't pick a winner. **Never place a flat thing at its surface's
     exact coordinate** — offset it a few mm proud (`panel.position.z = wall.z
     + 0.005`) or set `material.polygonOffset = true; material.polygonOffsetFactor
     = -1`. The audit logs `[checkZFighting] …` (the `_autoFixPlacement`
     repair pass nudges flagged thin panels a few mm out); an intentional
     flush decal can opt out with
     `obj.userData.noZFightCheck = true`. A `[checkZFighting]` line is a real
     flicker defect, not noise.

   All the audits operate on whole placed objects, so a multi-part desk
   (top + legs) or shelf (boards + sides) is checked as one thing, never
   per sub-mesh. A hover/clip/z-fight warning in the render log is a real
   defect to fix (or a missing `noSupportCheck`/`noZFightCheck`), not noise.

   **The audits are warn-only by default.** A scene that sets
   `globalThis._autoFixPlacement = true` (in `setup()` — the flags are
   snapshotted when setup ends) gets a repair pass before the audits:
   `checkClipping`, `checkHovering` and `checkZFighting` run once with
   `autoFix: true`, then the warn-only audits judge the repaired scene.
   `globalThis._noAutoPlacementCheck = true` skips both the repair and the
   placement audits. Repair is a safety net, not a placement method —
   things placed right don't need it, the `far`/`void` cases can't be
   repaired at all, and it pushes apart geometry that overlaps on purpose
   (trees: see `makeSeedTree` above).

   **TSL caveat**: vertex deformation done in a `positionNode` happens
   in the vertex shader at render time, so `Box3.setFromObject` (and
   therefore every helper above) sees the *un-deformed* mesh extent.
   If you warp a mesh in TSL, set `mesh.geometry.boundingBox = new
   THREE.Box3(min, max)` to the deformed extent before placing relative
   to it. The helpers honor a pre-set `geometry.boundingBox` and skip
   vertex iteration when present.

   **Composition recipes**:
   ```js
   // Desk on the floor, chair behind it, laptop on it, mug right of laptop.
   placeOn(desk, floor);                          // desk bottom on floor
   placeAgainst(chair, desk, 'behind', 0.25);     // 25cm of clearance
   placeOn(laptop, desk, { xz: 'centered' });     // laptop centered on desk
   placeAgainst(mug, laptop, 'right', 0.08);      // mug 8cm to the right
   placeOn(mug, desk);                            // also bring mug down to desk

   // Character standing on stairs.
   character.position.set(2, 5, 1);               // approximate xz target
   snapToGround(character, [stair1, stair2, stair3, landing]);

   // Eight books spread across a shelf.
   scatterOn(books, shelf, { count: 8, minSpacing: 0.04, rngSeed: 7 });

   // A bench somewhere clear near the fountain.
   const spot = findClearSpot(bench, fountain.position, { radius: 3, scene });
   if (spot) bench.position.copy(spot);
   ```

   **Placement anti-patterns:**

   - **Never write `obj.position.x/.z = …` after a place helper.** The
     helper centers the object's *bounding box* at the anchor; a raw
     position write moves the *loader origin* there instead, which for an
     off-center pivot shoves the visible model to the side. To shift after
     placing, pass `xzOffset: [dx, dz]` to `placeOn`, or use `placeAgainst`.
   - **Don't mix raw world coords and helpers for related props.** If the
     desk is positioned by a helper, every prop ON the desk must also be
     placed by a helper relative to the desk (`placeOn(monitor, desk,
     {xzOffset:[0,-0.16]})`), never `monitor.position.set(0, deskTop,
     -0.16)`. Raw-coord props assume the desk surface is at world 0; it
     usually isn't, so they float off it while helper-placed props sit
     correctly — and the two disagree.
   - **Check the model's `_preview.jpg` BEFORE placing to get rotation
     right.** A fetched GLB can face any axis and sit on any side. Look at
     the preview, decide the forward/up axis, set `obj.rotation` to make
     it upright and facing the shot, THEN place — the helpers read the
     post-rotation bbox.

   **Filling a shelf / cabinet / bookcase (interior boards):**

   `placeOn(item, shelf)` snaps to the shelf unit's OUTER TOP, not an
   interior board — and hand-guessing each board's Y/Z drops the books
   *inside* the carcass. Instead, drop onto the actual
   board surface with `snapToGround`, which raycasts down from the item's
   current xz against the shelf's own meshes:

   ```js
   // Books standing upright, spines out, on the SECOND board from the top.
   // 1. Rotate each book upright + spine-out FIRST (check the book GLB's
   //    _preview.jpg for its forward axis — many sit flat by default).
   // 2. Position it inside the shelf footprint, a little ABOVE the target
   //    board, then snapToGround({below:true}) onto the board under it.
   for (let i = 0; i < n; i++) {
       const b = bookProto.clone();
       b.rotation.set(0, spineOutYaw, 0);          // upright, spine toward viewer
       b.position.set(shelfX - 0.3 + i * 0.05,     // along the board
                      boardApproxY + 0.25,         // just above the target board
                      shelfZ);                     // inset from the front edge
       snapToGround(b, [shelf], { below: true });  // drops onto the board beneath it
       scene.add(b);
   }
   ```

   The books touch the board because the ray finds the board's true top,
   not a number you guessed. Keep them inset from the front edge and leave
   a sliver of `minSpacing` so they don't z-fight each other.

3. **Expand what you're asked for into a fully realized piece.** A
   request is usually a seed — a concept, a mood, a few anchor elements.
   The rest is yours to imagine into existence: the world it lives in, the
   composition and depth of every frame, the rhythm, the things nobody
   named but that the piece needs to feel real and complete. Three named
   things doesn't mean a video of three things floating in black; it means
   three things ANCHORED in the world you build around them. Take creative
   authorship.

4. **Story progression, not loops.** 4-6 distinct visual phases planned
   BEFORE writing any code. Each phase looks/feels different — different
   camera, lighting, mood, elements. Composition evolves with the audio.

5. **Verify visually before reporting done.** All the checks in "Quality
   verification" below. "No errors in logs" is the floor, not the bar.

6. **Append your techniques to `techniques_archive.md` (repo root)**
   (APPEND-ONLY — `open(path, "a")`, never overwrite, never delete).
   Don't read the whole file; search for specific topics.

7. **The tools are known-good. When one errors, the bug is in your
   code.** Every tool script at the repo root (`generate_song.py`,
   `generate_sfx.py`, `lipsync.py`, `align_lyrics.py`, `fetch_hdri.py`,
   `fetch_model.py`, `fetch_texture.py`, `cyborg_voice.py`,
   `cyborg_stutter.py`, `merge_av.py`, the `eidoverse/render_scene.mjs`
   engine, the `effects_tsl/*`, the procedural toolkits) has been
   iterated across hundreds of sessions. When one errors, read the full
   traceback, find the line in YOUR scene script or YOUR inputs that
   triggered it, and adjust. First hypothesis when something fails is
   always: *what did I pass wrong?* Writing your own parallel version of
   a tool, or wrapping the failure in a silent `try/except` and shipping
   a broken render, are the slow paths. (Exception: a missing BACKEND is
   an environment fact, not your bug — `generate_song.py`/`generate_sfx.py`
   fail fast with a clear error when ComfyUI isn't reachable; check
   the ComfyUI probe first and degrade honestly.)

8. **End the session with a playable mp4 on disk, or hand back a
   concrete blocker.** The only acceptable outcome is a final mp4 at
   the configured resolution that actually plays. If an ambitious
   render won't encode in the time you have, ship a simpler version
   that does — a 20-second single-shot mp4 that plays is worth more
   than a 75-second concept that never finishes. Verify with
   `ls -la work/<id>/*.mp4` before terminating.
   If you genuinely can't produce one, return the specific blocker
   (what you tried, what failed, what tool's error) so the human
   knows what went wrong.

## How to invoke the renderer

Everything renders natively on this machine (deno 2.8.1 + ffmpeg + your
GPU; setup in docs/SETUP.md):

```bash
python eido.py render work/<your_scene>.json            # full render
python eido.py render work/<your_scene>.json --probe    # single frame, for framing checks
# or raw, from the repo root:
deno run --allow-all --unstable-webgpu eidoverse/render_scene.mjs work/<your_scene>.json
```

Video encoding uses `h264_nvenc` when ffmpeg lists it and a one-frame test
encode succeeds, and falls back to `libx264` otherwise (with a
`[render_common]` warning); `RENDER_CODEC` overrides the choice.

All paths in scene configs and tool calls are RELATIVE to the repo
root — the engine always runs with that as its cwd.

## Scene file shape

```json
{
    "width": 1280, "height": 720, "fps": 30, "duration": <your runtime, see Duration>,
    "script": "work/<id>/scene.js",
    "outputVideo": "work/<id>/scene_video_only.mp4",
    "skipPreflightQA": true,
    "assets": {
        "hdri": "work/<id>/hdri.hdr"
    }
}
```

`assets` is whatever your scene actually needs — HDRIs, GLBs, PBR
texture sets, VRMs, audio. Declare only what your scene uses; there is no
required set.

**Asset injection is RAW BYTES.** Point each asset at the REAL file —
`hdri.hdr`, `<model_id>_embedded.gltf`, `character.vrm`, `image.png` — NOT a
`*_b64.txt` sidecar. The engine reads the file and puts a `Uint8Array`
straight on `globalThis.ASSETS[key]` (no base64 round-trip).
`globalThis.b64toArrayBuffer(ASSETS.key)` still works — it passes that
`Uint8Array` through to an `ArrayBuffer` — so
`loader.parse(globalThis.b64toArrayBuffer(ASSETS.x))` is the universal
pattern for GLB / VRM / HDR. (Point the `hdri` asset at `hdri.hdr` itself — handing the loader base64
text instead of HDR bytes yields "no header found".)

JS — minimum scene shape, no assumptions about content:

```js
globalThis.setup = async function () {
    // Renderer — adapter + device props are MANDATORY (no black frames)
    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: true,
        adapter: GPU_ADAPTER, device: GPU_DEVICE,
    });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    await renderer.init();

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.1, 200);

    // Build the world your piece needs here — HDRI sky + lighting,
    // terrain or interior, props, characters (or none of those, if the
    // piece is abstract / pure motion graphics / data viz / something
    // else). The patterns below are reusable; pick the ones that fit.

    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
};

globalThis.renderFrame = async function (t) {
    // If you applied CustomEffectsDeno, update its uniforms — but that does
    // NOT render. _fx.update(t) only pushes effect uniforms into the
    // auto-enhance pipeline; the scene render still has to happen. ALWAYS
    // call renderAsync afterward — never put it behind an `else`. (An
    // `if/else` here renders nothing when _fx exists → a frozen, static-frame
    // video. The harness will render for you and log a warning if you forget,
    // but write it correctly.)
    if (globalThis._fx?.update) await globalThis._fx.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
// preflight: ASSETS['<each-key-you-declared>']
```

The trailing `// preflight: ASSETS['key', ...]` comment is required —
the engine uses it to verify every declared asset is read.

### Reusable patterns (mix and match as your piece needs)

**HDRI for lighting** — provides ambient + IBL reflections. HDRI is
INVISIBLE: only set the environment, NOT `scene.background`.
HDRIs are designed to be a global light source, not a backdrop —
using one as the visible sky gives a flat 360 photo behind everything.

```js
// HDRLoader. The `hdri` asset points at the RAW hdri.hdr (see "Asset injection is RAW BYTES" above).
const { HDRLoader } = await import('npm:three@0.184.0/addons/loaders/HDRLoader.js');
const hdr = new HDRLoader().parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.hdri));
// 1) CPU row-flip — DataTexture.flipY is IGNORED on WebGPU; without this the
//    equirect is upside-down and your key light comes from the GROUND.
const rowLen = hdr.width * 4, Ctor = hdr.data.constructor;
const flipped = new Ctor(hdr.data.length);
for (let y = 0; y < hdr.height; y++)
    flipped.set(hdr.data.subarray(y * rowLen, (y + 1) * rowLen), (hdr.height - 1 - y) * rowLen);
const hdriTex = new THREE.DataTexture(
    flipped, hdr.width, hdr.height,
    THREE.RGBAFormat, hdr.type || THREE.HalfFloatType,
);
hdriTex.mapping = THREE.EquirectangularReflectionMapping;
hdriTex.minFilter = THREE.LinearFilter;
hdriTex.needsUpdate = true;
// 2) pmremTexture, NOT plain scene.environment — the raw equirect gives
//    checkerboard mip artifacts on opaque PBR and near-black metals.
scene.environmentNode = THREE.pmremTexture(hdriTex);   // lighting only — NEVER scene.background
// (If you skip this, the engine installs a dim sky-gradient env @ 0.3 as a
//  fallback — fine for a quick look, but a real HDRI is the production path.)
```

**Visible sky / horizon** — for outdoor scenes, use the WORLD-SPACE SKY
SYSTEM (`eidoverse/sky_system.js` — see "WORLD-SPACE SKY + WEATHER"). That
renders geometry-aware sky + clouds + sun/moon/stars. For indoor scenes
build the actual enclosure (walls, ceiling, windows showing what's
outside through the glass). For abstract scenes write a custom
backdrop / gradient / shader dome that fits the piece — never leave
`scene.background` as a flat dark color and call it done.

**Motivated lights on top of HDRI** — HDRI alone is flat ambient. Add
key/rim/fill that match the piece's mood. One `DirectionalLight` with
`castShadow: true` per scene MAX.

```js
const key = new THREE.DirectionalLight(0xfff8ee, 2.5);
key.position.set(3, 8, 6); scene.add(key);
```

**Procedural surfaces** — PBR sets from `fetch_texture.py`, never
flat-color `MeshStandardNodeMaterial({ color: ... })`. See the "Asset
sourcing" section above for the four-map material recipe.

**VRM character** — ONLY when the piece calls for a character on
screen. Many don't. The `loader.register(VRMLoaderPlugin)` line
is REQUIRED — without it MToon falls back to a WebGL ShaderMaterial
under WebGPURenderer and the character renders solid black with only
the eyes visible.

```js
const loader = new globalThis.GLTFLoader();
loader.register(p => new globalThis.VRMLoaderPlugin(p));
const buf = globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm);
const gltf = await new Promise((res, rej) => loader.parse(buf, '', res, rej));
const vrm = gltf.userData.vrm;
scene.add(vrm.scene);
// ALWAYS idle FIRST — VRM rest pose is T-pose; manual bone rotations
// off a T-posed rig give you cruciform "receiving the light" stances.
// (EXCEPTION: controller scenes — the controller owns ALL animation;
// do NOT pre-play idle under it. See "Moving a character".)
await globalThis.playVRMADefault(vrm, 'idle', { loopOnce: false });
globalThis._vrm = vrm;
```

**Where the character VRMs live** — `eidoverse/assets/vrms/`. **Read the
`<name>_preview.jpg` next to each `.vrm` to see the character before you
pick one** (same as fetched props):
- `aletheia.vrm` — Aletheia, a production-quality character (blonde, cyberpunk styling)
- `aporia.vrm` — Aporia, a production-quality character (dark-haired, cyberpunk styling)
- `claude_suit.vrm` — Claude, the AI, in a suit — the PRIMARY Claude model (see rule below).
  **The outfit is built in LAYERS** — mesh names `jacket`, `tie`, `shirt`, `pants`, `shoes`:
  hide layers to change the look (jacket + tie off = casual shirtsleeves):
  `vrm.scene.traverse(o => { if (o.name === 'jacket' || o.name === 'tie') o.visible = false; })`
- `claude_suit_wardrobe.vrm` — the same claudesona carrying sixteen outfits
  as hidden layers (a 1939 switchboard operator, a 1961 lab coat, 1980s
  colour-blocking, a hoodie, a mourning coat, an 1890s cycling outfit and
  more); `claude_suit_wardrobe_preview.jpg` shows them all. Dress it with
  `claudesona_wardrobe.js` ("Outfits" below).
  It is 31 MB against the suit's 11 MB, so cast `claude_suit.vrm` when the suit
  is all the piece needs.

- `claude.vrm` — a lightweight Claude stand-in; `claude_suit.vrm` is the primary model

Any other `.vrm` you drop into `eidoverse/assets/vrms/` works the same
way. Point `config.assets` at the VRM **where it lives** — e.g.
`"character_vrm": "eidoverse/assets/vrms/claude.vrm"` — the
loader reads any path you declare. **Do NOT copy the `.vrm` into your
work dir**; these are 10–40 MB and copying them per video bleeds the
disk. Custom GLB props live in `eidoverse/assets/models/` and are
likewise referenced in place; animation clips auto-load from
`eidoverse/assets/animations/` as VRMA slots.

⚠️ **The Claude VRMs (`claude.vrm`, `claude_suit.vrm`) are SPECIFICALLY
the AI "Claude" — never a generic stand-in.** Use them ONLY when the
video **explicitly references the AI Claude**. Do **NOT** cast Claude as
a generic narrator, correspondent, anchor, bystander, or "a human" —
Claude is a specific identity (and not a human), not a faceless extra.
Likewise in **dialogue/narration/on-screen text**: do not bring up or
name-drop "Claude" unless the piece specifically calls for it.

**Character voices** — assign one edge-tts voice per character and keep
it consistent for the whole piece (and across pieces, if you're building
a recurring cast). Match the voice to the character's presentation, and
run character narration through the voice filters (`cyborg_stutter.py`
for spoken TTS, `cyborg_voice.py` for sung vocals) when the character
concept calls for a robotic/synthetic timbre — raw edge-tts reads as
stock otherwise.

If the VRM is on screen AND the audio has vocals, you also need the
viseme drive in `renderFrame` — see the lipsync section below.

**GLB props** — same `GLTFLoader.parse` pattern as VRM, minus the
plugin registration. Models come pre-materialed; don't override them.

```js
const loader = new globalThis.GLTFLoader();
const gltf = await new Promise((res, rej) =>
    loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.tvModel), '', res, rej));
gltf.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
scene.add(gltf.scene);
```

## Audio pipeline (deep dive)

> **Backend check first:** `generate_song.py` and `generate_sfx.py` need a
> ComfyUI backend (default `http://127.0.0.1:8188`; override with the
> `COMFYUI_URL` env var). Probe with `python generate_song.py --probe`. If it
> isn't up: build the audio from edge-tts narration + ffmpeg-synthesized
> ambience (`anoisesrc` → filters), or user-supplied audio files.
> Both scripts fail fast with a clear error rather than hanging — if you
> see that error, switch strategy; don't retry in a loop and don't fake it.

### Music — `generate_song.py` (ACE-Step via ComfyUI)

```bash
python3 generate_song.py "<tags>" "<lyrics>" [--bpm N] [--key "K"] [--seed N]

# tags     positional. genre/style/instrumentation phrase shaping the track.
# lyrics   positional. timestamped singable lines, or empty string for instrumental.
# --bpm    integer tempo. Pick what the genre needs (ballad ~70, dnb ~170).
# --key    musical key string e.g. "A minor", "F# major". Match the mood.
# --seed   integer for reproducibility. Vary it to roll a different take.
```

**Tag rules:**
- For VOCAL tracks, name the voice type in the tags (e.g. `female lead vocal`)
- For INSTRUMENTAL, omit the vocal tag AND set lyrics field to empty/whitespace
- `tags` is free text — ACE responds to genre names, instrument lists,
  production adjectives, and tempo/mood words, in any combination.

**Lyrics rules:**
- Lyrics field is SINGABLE WORDS ONLY. No timestamps. No `[verse]` / `[chorus]` / `[bridge]` labels. No descriptive markers. ACE renders lyrics verbatim — labels become sung words.
- For an instrumental, leave the lyrics field empty.

**Output:** writes `song.mp3` in CWD. Poll loop waits up to 5 minutes — that's enough for typical generations. If ACE legitimately doesn't finish, FIX THE BRIEF (shorter duration, simpler tags) before falling back to a synth bed.

### Sound effects — `generate_sfx.py` (Stable Audio via ComfyUI)

Real SFX for your beats — wind beds, footsteps, impacts, mechanical
whirs, water, crowd murmur — instead of shipping a video whose only
audio is music + voice. Fast (~12–30s per clip on a local GPU). The
driver submits the repository's `sa3_workflow.json` (falling back to
`/workspace/sa3_workflow.json`, then ComfyUI's
`~/Downloads/audio_stable_audio_3_medium_base.json` template);
`python3 generate_sfx.py --probe` prints the resolved workflow path and
checks that ComfyUI is reachable (exit 0/1).

```bash
python3 generate_sfx.py "<prompt>" <seconds> <category> <out.mp3> [seed]
# category: SFX | One-shot | Music | Instrument (for songs use generate_song.py)
python3 generate_sfx.py "steady wind through dry grass, open field, no music" 24 SFX wind.mp3
python3 generate_sfx.py "a single soft body landing thud on stone, short, close mic, dry room" 3 SFX land.mp3
```

The workflow's LLM prompt enhancer rewrites your prompt through a
per-category brief before Stable Audio sees it. `One-shot` is a
music-sample brief (plucks, stabs, slams), so it turns foley into musical
hits — use `SFX` for sound effects, including single events.

Describe the SOUND, not the scene ("slow footsteps through dry grass,
rhythmic rustling" — not "a person walks sadly"). Add "no music, no
melody" to ambience prompts or the model drifts musical. Layer them
into the final mix with `adelay` at the exact beat times + `amix
normalize=0`, well under the voice (SFX ~0.3–0.6 relative weight; a
wind bed lower still). A video whose vault lands silently reads
unfinished — spot the 2–4 strongest physical beats and give them sound.

### Narration — TTS pipeline

```bash
edge-tts --voice <voice> --text "narration line" --write-media raw.wav
python3 cyborg_stutter.py raw.wav final.wav   # adds glitch stutters — use for TTS narration
# OR (for SUNG vocals coming out of demucs / generate_song):
python3 cyborg_voice.py vocals.wav final.wav  # tone-only filter — safe for music video lipsync
```

**Never hand-roll a robotic voice filter** with `asetrate`/`atempo`/`aecho`
— those change duration and produce half-silent or pitch-wrong output. Use
the dedicated tools (`cyborg_stutter.py` breaks sustained notes, so it's
for SPOKEN narration only; sung vocals go through `cyborg_voice.py`).

**Diegetic voice effects** (e.g. a voice gurgling underwater, muffled through a wall, radio-thin) ARE fine to build with ffmpeg filters — that's different from a character-voice filter. A convincing underwater/gurgle = `vibrato` (pitch wobble) + a fast `tremolo` (gl-gl-gl) + `lowpass` (muffle) + light `aecho` (liquid). Note `lowpass` removes energy, so **boost the processed voice's `volume`** (~1.5–2×) or it drops too quiet. For an effect that *develops* (clear → gurgling), `asplit` the voice, `afade` the clean copy out and the processed copy in over a window (crossfade), then `amix normalize=0`. Sound effects like water/rain/wind can be synthesized with `anoisesrc` (pink/white) → `bandpass`/`highpass` → `tremolo`; mux all audio as a separate ffmpeg pass (the renderer outputs video-only).

### Mix balance — voice ABOVE bed

Standard broadcast mix is voice 6-9 dB *above* the music bed. The default
`ffmpeg amix` does normalized averaging that DROWNS narration. Use
explicit weights and disable normalization:

```bash
ffmpeg -i music.wav -i tts_with_silence_padding.wav \
    -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0:weights='0.3 1.0'" \
    -c:a pcm_s16le mixed.wav
```

That's music at 30%, TTS at 100%, no auto-normalization. NEVER omit `normalize=0` when mixing voice over music.

**TTS spacing across the runtime:**
- TTS lines MUST distribute across the full video — roughly at 0%, 25%, 50%, 75%, plus the closing tag
- The LAST TTS line starts no earlier than 80% of the runtime
- Example (75s video): narration at 2s, 15s, 30s, 48s, 62s
- Use `adelay=<ms>|<ms>` per line to place each in the timeline

**Glue compression + limiter at the end:**
```
stereo = np.tanh(stereo * 1.35)
peak = max(0.01, float(np.max(np.abs(stereo))))
stereo = stereo / peak * 0.94
```
Plus 0.7s linear fade-in at the head and fade-out at the tail.

### Merging audio onto the render — `merge_av.py`

Render the scene a touch LONGER than the audio, then mux:

```bash
python3 merge_av.py --video scene_video_only.mp4 --audio mixed_audio.wav --out scene_final.mp4 [--tol 1.0] [--trim-tol 2.0] [--allow-trim]
```

It trims the video to the audio with `-shortest` and refuses two
mismatches:

- **Video shorter than the audio by more than `--tol`** (default 1 s): it
  **refuses to clone-pad a short render into a frozen-frame video**
  (`REFUSING TO MERGE — video … shorter than audio`, exit 2). Your render
  is too short: re-render with `duration` ≥ the audio length (a second
  longer is ideal).
- **Audio shorter than the video by more than `--trim-tol`** (default
  2 s): usually the wrong or a truncated mix, and `-shortest` would
  silently cut the film, so it exits 3. Pass `--allow-trim` only when
  cutting the video to the audio is intended.

Within those tolerances the video is stream-copied. Only a video short by
up to `--tol` is re-encoded, to pad that cushion: with `RENDER_CODEC` if
set, else `h264_nvenc` when ffmpeg lists it and a one-frame test encode
succeeds, else `libx264`. **NEVER hand-roll `tpad=stop_mode=clone`** — cloning the last
frame to backfill the audio is exactly how frozen-frame videos ship.
(Know the audio length before you render and set `duration` from it.)

### Lipsync — any scene with a VRM + audible vocals

```bash
# 1. split the mix. Stems land in <out>/htdemucs/<input-stem>/ — NOT next to
#    the input, so copy them out or reference the nested path.
python3 -m demucs --two-stems=vocals -o stems song.wav
#    → stems/htdemucs/song/vocals.wav  +  stems/htdemucs/song/no_vocals.wav

# 2. align. ⚠ `lyrics` is a REQUIRED POSITIONAL and it is the TEXT ITSELF,
#    not a path — passing a filename "succeeds" and aligns that literal
#    string as the only lyric. The flag is --output, not --out.
python3 align_lyrics.py vocals.wav "$(cat lyrics.txt)" --output lyrics_aligned.json
#    or from python:  from align_lyrics import align_lyrics
#                     align_lyrics('vocals.wav', lyrics_text, method='chunked')

# 3. OPTIONAL synthetic timbre — only if the character concept wants it.
python3 cyborg_voice.py vocals.wav cyborg_vocals.wav   # NOT cyborg_stutter

# 4. visemes. ⚠ lipsync.py has NO CLI — it is a MODULE. A `python3
#    lipsync.py … --out …` command exits silently having written nothing.
python3 -c "import json; from lipsync import get_viseme_timeline; \
json.dump(get_viseme_timeline('vocals.wav', fps=30), open('visemes.json','w'))"
```

The timeline has one entry per video frame, `ceil(duration × fps)` entries —
the same frame count the renderer uses for that duration.

⚠ **Gate the visemes to the aligned lyric windows.** demucs leaves
instrumental bleed in the vocal stem, so `get_viseme_timeline` reports mouth
motion through intros, solos and outros — the character sings along to the
piano. Zero every frame that falls outside a line's `[start, end]` (a ~0.12 s
pad each side keeps the consonant attack and release):

```python
wins = [(l['start'] - 0.12, l['end'] + 0.12) for l in lines if l['text'].strip()]
for i, f in enumerate(timeline):
    if not any(a <= i / fps <= b for a, b in wins):
        for k in f: f[k] = 0.0
```

A closed mouth through an instrumental tail is also what makes a final shot
read as "the music continues without them" rather than "the animation broke."

If the character is on screen and the audio track has their voice (song,
narration, dialog, anything), the visemes pipeline is required. There is
NO mode where you skip it but still reset visemes to 0 per frame —
resetting without driving zeroes the VRM's natural rest pose. Either
drive visemes from `visemes.json` OR leave the expression manager alone.

In your scene, drive the visemes per-frame. Critical rules:
- Reset all visemes to 0 at the START of every frame BEFORE applying current values (blend shapes persist otherwise)
- Apply viseme values directly — raw 0-0.35 range, no multiplier
- DO NOT also apply emotion expressions (happy/sad/angry) during lipsync — they override mouth shapes

```js
// CORRECT — reset visemes first, then apply
globalThis.renderFrame = async function (t) {
    if (globalThis._vrm?.expressionManager) {
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach(k =>
            globalThis._vrm.expressionManager.setValue(k, 0));
        const v = globalThis._visemes?.[Math.floor(t * FPS)];
        if (v) Object.entries(v).forEach(([k, val]) =>
            globalThis._vrm.expressionManager.setValue(k, val));
    }
    // ...effects update + renderAsync...
};
```

**⚠️ `claude_suit.vrm` mouth is SPECIAL — drive raw morphs, not expressions.**
painted on the face; the animatable mouth is a hidden cavity revealed by
the `show MMD mouth` shapekey. The expressionManager path barely moves it —
voice over that mouth reads frozen. `eidoverse/claudesona_face.js` packages
the render-verified recipe (it works the same on `claude_suit_wardrobe.vrm`):

```js
const { installSuitMouth, makeSuitMouth, makeFaceTrack, mergeMax } =
  await import(new URL('claudesona_face.js', EIDOVERSE_DIR).href);
const face = installSuitMouth(vrm);                // once, after load
const mouth = makeSuitMouth({ inputMax: 0.35 });   // 0.35 for lipsync.py visemes, 1 for voicebox
const feel = makeFaceTrack(TL, {                   // optional: feelings keyed to words
  sectionBase: { chorus: { smile: 0.5 } },
  lineCues: [[/goodbye/, { soft: 0.8, frown: 0.2 }]],
});
// renderFrame(t): the current viseme frame is { aa, ih, ou, ee, oh }
face.set(mergeMax(mouth.update(t, visemes[Math.floor(t * visemeFps)]), feel.at(t)));
```

1. `installSuitMouth(vrm)` finds the three face plates and writes their raw
   `morphTargetInfluences` in `onBeforeRender`. Writing at render time
   survives the engine's VRM passes. It zeroes every morph first, because
   leftover expression weights otherwise hold the mouth shut. Zeroing also
   removes auto-blink, so the driver blinks for you. It returns
   `{ plates, set(weights), weights }`.
2. **The reveal is a threshold, not a fade.** The black cavity is a plate
   pushed through the white face. Below about `show MMD mouth` 1.0 it stays
   behind the face and only the painted line shows; above that it pops out
   and grows. A viseme pose scaled by loudness crosses that line on every
   consonant, so the black part blinks out mid-word. One film measured the
   cavity visible for 71 of 255 sung seconds, with 716 on/off flips.
   `makeSuitMouth` avoids that:
   - It keeps one openness signal with a fast attack (30 ms) and a slow
     release (110 ms).
   - It opens above 0.18 and closes below 0.08, with hysteresis between.
   - While open it holds the reveal at `reveal` (1.25) and scales only the
     vowel's shape morphs, by `0.3 + 0.7 × openness`.
   - It changes vowel only at a syllable dip, or when another vowel clearly
     leads.

   The cavity stays out through a phrase and closes at its end. The other
   options are `attack`, `release`, `openAt`, `closeAt`, `switchDip`,
   `switchLead` and `blinkEvery`. Blinks happen only while the mouth is
   shut; `blinkEvery: 0` turns them off.
3. The poses are exported as `SUIT_VISEMES`, one per vowel. Weights above 1
   are intentional: morph deltas scale linearly past 1, and these stacks are
   verified tear-free.
   ```js
   aa: { 'show MMD mouth': 1.6, 'あ': 2.0, JawOpen: 1.5, A: 0.5 }   // big open — the workhorse
   oh: { 'show MMD mouth': 1.2, LipFunnel: 1.0, 'お': 0.8 }          // rounded drop
   ou: { 'show MMD mouth': 0.8, LipPucker: 1.2 }                     // tight pucker
   ee: { 'show MMD mouth': 1.0, 'え': 1.5 }                          // wide + shallow
   ih: { 'show MMD mouth': 0.9, 'い': 1.2 }                          // flat slit
   ```
   A single openness signal, such as `lipsync.py get_mouth_openness` or an RMS
   envelope, works too: pass it as `{ aa: openness }`.
4. `makeFaceTrack(TL, opts)` keys feelings to words and sections rather
   than seconds, so re-timing the audio can't desync a feeling. `TL` is
   `{ sections: [{ name, t0, t1 }], captions: [{ text, t0, t1 }] }`, the
   shape the voicebox and song timelines use.
   - `sectionBase` sets each section's resting feeling.
   - `lineCues` pairs a regex on the caption text with a feeling, eased in
     and out around each matching line.
   - `closeAfterLast` (default `true`) slowly softens the eyes after the last
     caption.

   The channels, as measured on this face:
   - `smile` curls the mouth corners up smoothly with its value.
   - `frown` is smooth; `wide`, `down` and `up` (gaze) are subtle.
   - `soft` closes the eyes. Up to about 0.5 they only shrink to small dots;
     0.75–0.85 gives content, sleepy slits.
   - `blush` and `jaw` are switches, because both ride reveal plates like the
     mouth. Blush is hidden below a raw `Blush` of about 0.75, so a blush of
     0.3 or more shows it (a little fuller as it rises) and less shows
     nothing. A jaw of 0.15 or more opens the mouth while the character is
     silent.

   `mergeMax` merges weight dicts by the per-morph maximum.
5. Verified traps: `vis_aa/ih/ou/ee/oh` and the plain vowel shapes do
   nothing without the reveal; `MouthClosed` doesn't hide the cavity (rest
   = reveal at 0); `hide mouth` restyles the painted line (an aesthetic
   change, not lipsync); `O`/`お` solo are empty exports. Expression
   accents that do work as raw morphs: `Smile`, `MouthSmileLeft/Right`,
   `MouthFrown`, `Blink`, `EyeClosedLeft/Right`, `EyeWide`, `Blush`/`照れ`.
   `Blush` and `照れ` are reveals: nothing below about 0.75, full cheeks from
   0.9. To try a face, render
   `python vrm_turntable.py --outfits suit,suit --frames face --views 0 --faces '[{"Blush": 1}, {"Smile": 0.6, "MouthSmileLeft": 0.6, "MouthSmileRight": 0.6}]'`.

`claude.vrm` (the classic sona) is the opposite: its mouth is
expression-bound and the plain `expressionManager.setValue` viseme path
above works as written — no raw-morph handling needed.

**`claude_suit.vrm` wardrobe — the clothing is LAYERED and RECOLORABLE**
(render-verified). Named nodes: `jacket`, `tie`, `shirt`, `pants`, `shoes`.
- **Hide layers** with `vrm.scene.getObjectByName('jacket').visible = false`
  (same for `tie`) — the shirt underneath is fully modeled.
- **`flower` is NOT clothing** — it's the head MANE, the character's
  signature bloom. Never hide it when dressing him down.
- **Recolor**: these meshes carry material ARRAYS — `mesh.material.color`
  is undefined; collect
  `(Array.isArray(m.material) ? m.material : [m.material])` per layer and
  `mat.color.setHex(...)` each. Stock palette for restore: jacket
  `#273884`, tie `#e70024`, shirt `#cecece`, pants `#fdc955`, shoes
  `#65411f`, mane `#f98a53`.
- **Casual look**: hide jacket + tie, then PUFF the shirt so it reads as a
  relaxed pullover instead of a fitted undershirt. `node.scale` is ignored
  on skinned meshes — displace vertices along normals ONCE at setup:
  ```js
  const shirt = vrm.scene.getObjectByName('shirt');
  shirt.traverse((m) => {
      if (!m.isMesh) return;
      const pos = m.geometry.attributes.position, nor = m.geometry.attributes.normal;
      for (let i = 0; i < pos.count; i++) {
          pos.setXYZ(i, pos.getX(i) + nor.getX(i) * 0.02,
                        pos.getY(i) + nor.getY(i) * 0.02,
                        pos.getZ(i) + nor.getZ(i) * 0.02);
      }
      pos.needsUpdate = true;
  });
  ```
  `0.02` is the verified fit (relaxed shirt); `0.035` reads as a bulky
  sweater — keep it ≤0.02 unless a sweater is the point. Copy the original
  positions first if you need to restore the fitted look.

#### Outfits — `claude_suit_wardrobe.vrm`

`eidoverse/claudesona_wardrobe.js` dresses the wardrobe VRM. It shows and
hides garment layers, repaints materials with colours or procedural
patterns, folds petals back under a hat and seats the hat.

```js
const { makeWardrobe, WARDROBE } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
const wardrobe = makeWardrobe(THREE, vrm);   // after load; starts in 'suit'
wardrobe.wear('lab_coat_1961');              // any WARDROBE key; a no-op if already worn
wardrobe.petals('mac_launch_1984');          // repaint only the petals (a preset key or a spec); null restores
```

| Preset | The look |
| --- | --- |
| `suit` | digi's own suit |
| `voder_operator_1939` | rose jacket, cream blouse, a switchboard operator's headset |
| `lab_coat_1961` | white lab coat, glasses, a pocket protector with pens |
| `turtleneck_1966` | black turtleneck, glasses |
| `ringer_tee_1978` | red-and-amber striped tee |
| `colorblock_1982` | colour-blocked jacket, terry headband, petals in the Commodore 64 palette |
| `mac_launch_1984` | grey suit, green bow tie, petals in the six Apple stripes |
| `professor_tweed_1984` | herringbone tweed, glasses, amber petals |
| `fleece_2001` | navy jacket, khakis |
| `vocaloid_2007` | grey shirt, teal tie, ribbon bows in the petals |
| `hoodie_2016` | black hoodie: hood down, kangaroo pocket, drawstrings |
| `bing_2023` | blue-to-teal gradient suit, petals swept in the same blues |
| `mourning` | black overcoat, white shirt, black tie, a daisy on the lapel |
| `march` | canvas work jacket with embroidered patches |
| `sleeves_rolled` | jacket off, shirt sleeves rolled, tie |
| `cyclist_1892` | striped jersey, tweed knickerbockers, argyle socks, a straw boater with the petals folded under it |

A preset is `{ show, paint, hide, fold, hat }`:

- `show` lists the garment layers to show; every other optional layer hides.
  The body, face, flower and shoes always show. The layers are `jacket`,
  `tie`, `shirt`, `pants`, `jersey`, `knickers`, `socks`, `boater`,
  `coat_skirt`, `shirt_rolled`, `acc_glasses`, `acc_headset`, `acc_pocket`,
  `acc_bowtie`, `acc_headband`, `acc_ribbons`, `acc_hoodie`, `acc_patches` and
  `acc_boutonniere`.
- `paint` maps a material name to `'#hex'` or a pattern:
  - `{ pattern: 'stripes', a, b, scale }`, `'blocks'` (`a`, `b`, `c`),
    `'herringbone'` (`a`, `b`, `c` flecks, `scale`), `'gradient'` (`a`, `b`)
    and `'canvas'` (`a`, `b`, `scale`);
  - for `petals` only, `'rainbow'` (`colors`, `top`, `bottom`), `'perPetal'`
    (`colors`, one per petal, and `center`) and `'sweep'` (`a`, `b`).

  Patterns are procedural in the model's object space, because the garment
  UVs are not laid out for prints. A hex on a textured material replaces its
  print while its normal map keeps the weave. The MToon shade colour and the
  outlines follow the paint. The layer table in the
  [source README](eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md)
  lists the material names.
- `hide` hides materials inside a shown layer; the hoodie hides the jersey's
  `jersey_collar`.
- `fold` bends whole petals back from the face: `{ '12_L': deg }` or
  `{ '12_L': [deg, scale] }`, keyed by petal bone (`1_L`…`12_L`, `1_R`…).
  The petals are spring bones, so the fold is written into each chain's rest
  pose and the springs keep moving around it.
- `hat` seats the boater: `{ offset: [x, y, z], scale }`, in model metres
  with +z on the face's side.

`WARDROBE` is a plain object read at `wear()` time, so add your own preset
with `WARDROBE.my_look = { show: [...], paint: {...} }`. Each (material,
paint) pair builds one node, cached, so switching back and forth between
outfits reuses compiled shaders. Set `globalThis.WARDROBE_DEBUG = true` to
log paints and folds. New garments are modelled in Blender; the
[source README](eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md)
has the steps.

#### Turntable sheets

`vrm_turntable.py` (repository root) renders a VRM through the engine in a
neutral studio and tiles the result. Use it to review an outfit, a new
garment, a clip on another rig or an expression:

```bash
python vrm_turntable.py --outfits lab_coat_1961,mourning --frames head,body --views 0,35,90,150,180
python vrm_turntable.py --outfits suit,march,cyclist_1892 --frames body --views 20 --tile 3x1
python vrm_turntable.py --vrm eidoverse/assets/vrms/aletheia.vrm --outfits - --anim sing_open_arms,bow_thanks --hold 45
python vrm_turntable.py --outfits suit,suit --frames face --faces '[{"Smile": 1}, {"EyeWide": 1, "Blush": 0.6}]'
python vrm_turntable.py --outfits hoodie_2016 --spin --video work/turntable/hoodie.mp4
```

A sheet has one row per outfit, clip and framing, and one column per yaw.
`--tile CxR` lays the same tiles out as a grid. Each tile is the last frame
of a `--hold` block, because frame 0 of any render is the VRM's load pose and
spring bones need a few frames to settle. The framings are `face`, `head`,
`chest` and `body`, scaled by the character's own head height, so any rig
frames the same. `--outfits -` renders a VRM without the wardrobe. The
defaults are `--scale 0.87` for the claude_suit models (a human 1.74 m) and
`--light 0.7`, which keeps white MToon cloth under the bloom threshold.
`--presets` adds variants on the command line
(`{"name": {"base": "cyclist_1892", "fold": {...}}}`), and `key:nofold`
drops a preset's fold. `--spin` renders a slow turn per outfit as a video
instead of a sheet.

Music-video full protocol:
1. `generate_song.py` with a vocal tag + singable lyrics (or a supplied track)
2. demucs split → `stems/htdemucs/<name>/{vocals,no_vocals}.wav`
3. `align_lyrics.py vocals.wav "<the lyrics text>" --output lyrics_aligned.json`
4. `cyborg_voice.py vocals.wav` — OPTIONAL, only for a synthetic timbre
   (NOT stutter — stutter breaks sustained notes)
5. `get_viseme_timeline(vocals.wav, fps)` from the `lipsync` MODULE (no CLI),
   then GATE the result to the lyric windows — see the section above
6. ONE scene script with VRM + environment + props + HDRI in the same scene
7. Different VRMA animations per song section — idle bridge, walking verses, expressive choruses; don't loop one across the whole song
8. Camera varies — close-ups on face for emotional lines, wide for choruses, dolly-in on builds
9. `lyric_renderer.py` overlays subtitles using `lyrics_aligned.json` timestamps (or regenerate each subtitle into a CanvasTexture overlay for live in-engine sync)
10. Always add 5-second fadeout: `afade=t=out:st=<duration-5>:d=5`

## Lighting

Every scene needs deliberate lighting. A scene with the default tone
mapping and no lights renders as flat dark grey — no PBR material can
look right without something to reflect. Set this up before you start
populating geometry, not after.

- HDRI mandatory for any non-flat-indoor scene (`fetch_hdri.py`; point the `hdri` asset at the raw `hdri.hdr`). The HDRI gives you global ambient + reflections all at once.
- Manual lights ON TOP of HDRI for specific motivated sources — a key light from the direction the scene implies, a rim/back light to separate the subject from the background, accent point lights for diegetic sources (neon signs, screens, candles, sun through a window).
- **NEVER use `SpotLight` with `castShadow: true`** — crashes MToon shaders, makes the VRM invisible.
- Keep to ONE `DirectionalLight` with `castShadow: true` per scene (the "sun" / main key). Additional lights should have `castShadow: false`.
- Use multiple `PointLight`s (no shadow casting) for diegetic neon / interior practicals — they're cheap and add color depth.
- For night / liminal / void scenes: HDRI may be too bright; substitute a dim ambient + emissive materials on diegetic light sources + a low-intensity key. "Dark" still needs to be SEEN as dark, not as the absence of rendering.
- **"Sci-fi" / "moody" is NOT dark-and-metallic.** A high-metalness surface shows its *environment reflection*, not a diffuse colour — and env-IBL reflection is unreliable on this stack (even a PMREM-prefiltered HDRI often won't land on a flat metal wall; it renders BLACK). So don't lean on reflections to light set surfaces: keep metalness modest (~0.2) and light them with actual lights. A "sci-fi metal wall" that's a black void is this mistake.
- **Light a far wall/background without blowing out a near subject** using `PointLight`s (inverse-square falloff) placed close to the wall — they brighten the wall but fall off before reaching the subject. A `DirectionalLight` has no distance falloff and hits subject and wall equally, so cranking one to rescue a dark wall blows out the subject. Never brute-force-stack lights at one problem without checking what they do to everything else in frame.
- **Watch for blowout / bloom.** Bright or white subjects + bright effects (water spray, particles, emissives) + autoenhance bloom clip into glowing white blobs. Lower `toneMappingExposure` (~0.8) and keep key/rim intensities modest. Verify by cropping the subject's face/body and confirming it still has *detail* (eyes, shading) and isn't a featureless white mass — you cannot judge exposure from a thumbnail.

## Moving a character — use the dialed-in controller

To make a VRM walk, use the PROPER, dialed-in stack: physics-based locomotion +
terrain-conforming foot IK (no drag) + automatic walk speed that slows by
incline on stairs/ramps + (optionally) lidar sensing & A* path planning.
Three entry points, same engine underneath — pick by the job:

- **`VRMRobotBody`** — autonomous navigation (senses + plans + walks). It SEES
  the scene (lidar fan) and routes around obstacles to a destination, with the
  dialed-in IK + incline speed. Use for "get them to that spot, around the
  furniture."
  ```js
  const body = await VRMRobotBody.create(vrm, mixer, scene, {
      collisionMeshes: [floor, wall, deskMesh],          // solids they walk on / around
      motion: { startX: 0, startZ: 4 },                  // walkSpeed OPTIONAL (see below)
  });
  const arrival = body.walkTo(2.5, -3);                  // plans a path, turns + walks it, arrives → idle
  arrival.catch(err => console.error('Navigation:', err));
  // in renderFrame(t): body.update(t, dt);  read body.getPosition() / getHeadPosition()
  ```
  `walkTo`/`runTo` resolve on arrival. If the controller stalls against a
  collider, the body replans once; still stalled after ~1.5 s, the promise
  REJECTS with `Error('blocked: collision stall at …')` and the waypoints
  clear — always attach a `catch`. `body.performAction(clip, duration)`
  resolves only after the emote has played for `duration` (default 1.5 s)
  and rejects if the clip is unknown or fails to load.
- **`EidoverseRobotController`** — explicit waypoints, no sensing/planning, same
  simple API. Use when you know the exact path. Same dialed-in
  `VRMCharacterController` + foot IK + incline speed underneath.
  ```js
  const ctrl = await EidoverseRobotController.create(vrm, mixer, {}, {
      collisionMeshes: [floor], startPosition: [0, 0, 4],
  });
  ctrl.setWaypoints([{ x: 0, z: -4 }]);                  // {x,z} points; arrives → idle
  // in renderFrame(t): ctrl.update(t, dt);  read ctrl.getPosition()
  ```
- **`VRMCharacterController`** — the lowest level the obstacle course drives:
  `locomote(dt, dir)` + `attachLocomotion({ legIK })` over a Rapier world you
  build. Use directly only for terrain-harness work — see "Character
  locomotion" below + `eidoverse/examples/obstacle_course.js`.

**Walk speed is automatic.** Leave `walkSpeed` unset for a normal pace — the
controller matches the walk clip's natural stride, and slows by itself on
stairs/ramps. Only set `walkSpeed` for a DELIBERATE effect (very low = slow
motion; high = hurried). Don't lowball it "to look cinematic" — that's the
slow-mo-walk bug.

**`collisionMeshes` IS the walkable/climbable world — not the scene graph.** The
controller finds the surface under the feet by shape-casting the **Rapier
physics world built from `collisionMeshes`** (and so does the foot IK). It does
**NOT** raycast the rendered scene. So `collisionMeshes` does double duty: the
walls they slide against in X/Z, AND the ground they walk on, stand on, and
**climb**. The rule that follows:

> **Every surface they should walk on / stand on / step or climb onto MUST be in
> `collisionMeshes`** — the floor, AND any stage, platform, riser, step, ramp,
> kerb, terraced terrain, or raised walkway. A surface that's only `scene.add`-ed
> but missing from `collisionMeshes` is invisible to the feet: the character
> walks straight through it at ground level instead of climbing onto it.

Climbing is **automatic once the surface is a collider**: low steps / ramps /
platforms pass under the upper-body collider and the controller smoothly raises
the body onto the top. So to put a character on a raised stage behind a podium:
**(1)** add the stage to `collisionMeshes`, **(2)** waypoint an xz that is
actually *on the stage top, behind the podium* — not a point in front of it.
*(Advanced escape hatch: if you genuinely can't add a collider, drive
`controller.externalGroundY` each frame from your own THREE raycast — but the
simple, correct path is to put it in `collisionMeshes`.)*

With ANY of these the controller owns the mixer, the root transform, AND the feet:
- Do **NOT** pre-play idle (`playVRMADefault('idle')`) before/under it — a
  pre-played action stays at weight 1 and blends over every clip it plays,
  so the legs drag and no walk animation shows.
- Do **NOT** call `mixer.update(dt)` / `vrm.update(dt)` yourself (it does).
- Do **NOT** write `vrm.scene.position` / `.rotation.y` per frame — read
  position via `getPosition()`; face the camera only when stationary via the
  controller's `heading`. Manual transforms each frame = foot-slide / drag.

## Movement vocabulary — run, vault, climb, jump, ladders, gestures, sitting

The controller's full vocabulary. Everything below is animation-driven with
automatic contact IK — hands plant on vaulted objects, grab ledge lips, and
find ladder rungs on their own. Never hand-IK limbs or hand-animate any of
these moves. The engine is `VRMCharacterController`; the two wrappers pass
some of it through and hold the rest on an inner object:

| Entry point | Inner `VRMCharacterController` | `isManeuvering` |
|---|---|---|
| `VRMCharacterController` | itself | getter: `cc.isManeuvering` |
| `EidoverseRobotController` | `ctrl.charCtrl` | getter: `ctrl.isManeuvering` |
| `VRMRobotBody` | `body.controller.charCtrl` (`body.controller` is an `EidoverseRobotController` unless `opts.legsClass` overrides it) | method: `body.isManeuvering()` |

`vault()`, `jump(opts)`, `climbLedge()`, `climbLadder(opts)` and
`setRunning(v)` exist on all three. `autoManeuvers` and the gesture methods
exist ONLY on `VRMCharacterController` — reach them through the inner object.

- **Running.** On `EidoverseRobotController`, per-waypoint:
  `ctrl.setWaypoints([{ x, z, action: 'run' }, …])` — they run to that
  waypoint and drop back to a walk for waypoints without it. On
  `VRMRobotBody`, `body.runTo(x, z)`. Direct, on any entry point:
  `setRunning(true/false)`. Stride syncs to actual speed; stairs switch to
  run-stair clips automatically.

- **Auto-maneuvers (ON by default).** While walking/running, the controller
  scans the path ahead and handles what it finds without being told:
  - knee-to-chest obstacles (rise ~0.45–1.15 m with a landing beyond) → VAULT
    over them, one hand planting on the top;
  - chest-height to ~2.3 m walls → CLIMB (grab the lip, pull up, mantle over
    the edge — the whole move plays at the ledge). Through the mantle the top
    surface is a hard floor for the hands — they plant ON it while the body
    rises over them — and the stepping foot lands on the top, not against the
    face; corrections scale with penetration, so the clip keeps the motion;
  - near-level gaps up to ~2.2 m → JUMP across;
  - drops of ~0.85 m+ → a landing-recovery crouch on touchdown.
  Set `autoManeuvers = false` on the inner controller
  (`ctrl.charCtrl.autoManeuvers = false`,
  `body.controller.charCtrl.autoManeuvers = false`) while deliberately
  approaching furniture or scenery the character should NOT parkour over (a
  bench they'll sit on is not an obstacle), and re-enable after. Check
  `isManeuvering` (a method on `VRMRobotBody`, a getter elsewhere — table
  above) before issuing new orders mid-flight.

- **Explicit maneuvers** (the character must be facing the geometry, within a stride):
  ```js
  ctrl.vault();                          // over the cover ahead (needs a landing beyond)
  ctrl.climbLedge();                     // up onto the wall/ledge ahead
  ctrl.jump({ distance: 1.4, height: 0.45 });
  ctrl.climbLadder({ height: 2.5 });     // climbs the ladder face ahead, mantles the top
  ```
  All return `false` (with a console warning) when the geometry ahead doesn't
  support the move — check the return if the beat matters. Ladders want REAL
  rung geometry: rungs roughly every 0.28 m (override via
  `{ firstRung, rungSpacing }`), protruding slightly in front of the face —
  hands and feet quantize to the nearest rung as the loop climbs. Tall
  rung-less walls (~2.3–4.5 m) get a wall-scramble: the controller loops the
  climb-up clip against the face and mantles the top (`wallScrambleMaxRise`
  tunes the ceiling).

- **Upper-body gestures WHILE walking/running.** An emote's upper body blended
  over the gait — wave, talk, cheer with the hands while the legs keep
  walking. These live on `VRMCharacterController`; from a wrapper, use its
  inner controller:
  ```js
  const cc = ctrl.charCtrl;                 // VRMRobotBody: body.controller.charCtrl
  await cc.loadGesture('cheer');            // once, at setup
  cc.playGesture('cheer', { weight: 2.5 }); // ≈70% gesture on the upper body
  cc.stopGesture();
  ```
  Weight is a mixer blend: `2.5 ≈ 70%`, `4 ≈ 80%`. Gestures end automatically
  when a maneuver starts (the whole body belongs to the vault/climb). A FULL
  emote (`playEmote`) still suspends locomotion entirely — gestures are the
  move-and-emote path.

- **Aiming a standing emote.** Full emotes (salute / bow / dance / talk while
  stopped) face `Math.PI` by default. To aim one at the camera or another
  character, set the facing yaw before playing (on `EidoverseRobotController`
  the emote API lives on `.charCtrl`; `VRMRobotBody` has
  `body.setEmoteFacing(ry)`, which sets the same field; on a bare
  `VRMCharacterController` call it directly):
  ```js
  const b = ctrl.getPosition();
  ctrl.charCtrl._emoteFacingY = Math.atan2(cam.position.x - b.x, cam.position.z - b.z);
  ctrl.charCtrl.playEmote('salute', { fadeIn: 0.35 });
  ```
  The character pivots to the target as the emote fades in (shortest arc, no
  snap). When an emote fades OUT they ease back to the locomotion heading
  automatically — never hand-rotate a character around an emote.

- **Sitting down on furniture.** Use the production seat system with the
  controller registered — `seatOn` raycasts the pan, stands the character at
  the sit clip's natural approach distance, plays the transition through the
  controller's seated state, and settles the butt mesh-onto-pan:
  ```js
  // VRMRobotBody registers itself; a bare VRMCharacterController registers with:
  (globalThis._vrmControllers ||= new Map()).set(vrm, ctrl);
  await seatOn(vrm, bench, { transition: 'stand_to_sit', faceY: Math.PI });
  // …hold seated…
  ctrl.endSeated(null, { reverse: true });   // stands back up (same clip reversed)
  ```
  Choreograph the approach so the character STOPS just past the seat facing
  away from it (the transition clip carries the hips back onto the pan) —
  walk AROUND furniture in the path, never through it, with `autoManeuvers`
  off for the approach.

- **Sitting on the ground, a ledge or a low wall** (no chair pan — a chair-
  height transition would leave them hovering on an invisible seat): drive the
  seated state directly with the cross-legged pose, which sits at the root
  plane, i.e. on whatever they're standing on:
  ```js
  ctrl.heading = facingY;                     // face this way seated — AND stand up into it
  ctrl.beginSeated('sitting_on_ground');
  // …hold seated…
  ctrl.endSeated(null);                       // release the seated state…
  ctrl.charCtrl.stopEmote({ fadeOut: 0.9 });  // …and fade the pose back to idle
  ```
  Stand-ups rise straight into the CURRENT locomotion heading — set `heading`
  while seated to choose the facing; no post-stand turn is needed.

## Character-controller anti-patterns that cause T-pose / foot-slide

If your VRM ends up in T-pose despite loading an animation, ONE of these
is the cause:

1. **Double-updating the mixer.** When using a controller,
   call ONLY `controller.update(t, dt)` per frame. Do NOT also call
   `mixer.update(dt)` or `vrm.update(dt)` — animation plays 2× and looks
   broken. (If you're NOT using the controller, then `mixer.update(dt)`
   + `vrm.update(dt)` is correct.)

2. **Controller out of waypoints.** When the path ends, the controller
   reverts to T-pose. Force an idle fallback:
   `controller.forceAction('idle', remainingDuration)`.

3. **Manual position/rotation while controller is active.** Setting
   `vrm.scene.position` / `vrm.scene.rotation.y` per frame causes
   foot-sliding, walking-through-objects, or backwards motion. Use
   waypoints only; read position via `controller.getPosition()`.

4. **Walking through walls / floating above the ground.** Pass EVERY solid
   walked on or around as `collisionMeshes` at `create(...)` time (floor,
   walls, furniture, stage/platform, stair/ramp meshes). The controller
   builds the Rapier physics world from them — that's both the collision AND
   the ground the foot IK conforms to.

5. **Feet not conforming to stairs/ramps.** They do automatically — the proper
   stack runs the dialed-in `VRMFootControllerIK` (terrain-conforming plant,
   no drag) and slows the walk by incline, as long as the stair/ramp meshes
   are in `collisionMeshes`. Foot IK auto-suspends during emotes
   (`forceAction`) and airborne states. Nothing to wire by hand.

6. **VRM facing wrong direction.** After `VRMUtils.rotateVRM0(vrm)`, the
   VRM faces +Z. A camera at positive Z looks at the face. Set
   `vrm.scene.rotation.y = 0` to face the camera; don't fight the rig.

At the end of a render the `[vrm-pose]` check flags (`RE-RENDER REQUIRED`) a
tracked VRM that NEVER left its load pose — the T-pose statue.

## What's on `globalThis` when your script runs

### Engine
- `WIDTH`, `HEIGHT`, `FPS`, `DURATION`, `TOTAL_FRAMES`
- `canvas`, `GPU_ADAPTER`, `GPU_DEVICE`
- `ASSETS[key]` — raw `Uint8Array` bytes keyed by your `assets` map
- `b64toArrayBuffer(x)` → ArrayBuffer (passes Uint8Array through; decodes base64 strings)

### Three.js
- `THREE` — three@0.184.0 (WebGPU build + TSL)
- `RaymarchingBox`, `SkyMesh` — TSL utility nodes
- You build the renderer / scene / camera yourself and assign to `_r` / `_s` / `_c`. Adapter + device props on `WebGPURenderer` are MANDATORY.
- Per frame: ALWAYS `await _r.renderAsync(_s, _c)`. If you use CustomEffectsDeno, `await _fx.update(t)` FIRST (it only pushes effect uniforms — it does NOT render), then renderAsync. Never put renderAsync behind an `else` after `_fx.update` — that renders nothing and freezes the video. Never plain `render()`.

### GLB / VRM loading
- `GLTFLoader` — auto-wires `VRMLoaderPlugin` + `DRACOLoader` + auto-converts GLB textures to DataTextures (works around missing `copyExternalImageToTexture` in Deno's WebGPU bindings)
- `__DRACO_LOADER__`, `VRMLoaderPlugin`, `MToonNodeMaterial`, `VRMUtils`, `VRMAnimationLoaderPlugin`, `createVRMAnimationClip`
- After GLTFLoader parses a VRM, `globalThis._vrm` is auto-captured
- Models > 1M polys can crash the loader — fetch_model.py auto-filters

### VRMA animations
`globalThis.VRMA_DEFAULTS_B64` keyed by slot. All clips ship in
`eidoverse/assets/animations/` (slot name = filename stem). The slots are the
`VRMA_SLOTS` list in `eidoverse/render_scene.mjs`; a slot whose `.vrma` is
missing is skipped:
- **Locomotion** (driven by `VRMCharacterController` — the walk/run/stairs clips are NOT playable via `playVRMADefault`): `walk`, `run`, `idle`, `turnLeft`, `turnRight`, `jump`, `vault`, `climbLedge`, `climbWallUp`, `climbWallDown`, `climbLadder`, `fallIdle`, `fallLand`, `stairsUp`, `stairsDown`, `stairsRunUp`, `stairsRunDown`
- **Expressive** (a STATIONARY VRM only — see below): `talk`, `salute`, `cheer`, `fist`, `raise`, `reach`, `crazy`, `dance`
- **Sitting** (see [Emotes + sitting](#emotes--sitting-on-a-stationary-character) below): chair poses `sitting_normal_chair` (the `seatOn` default) and `sitting_nervous_arm_rub_chair`; floor poses `sitting_on_ground` (cross-legged) and `sit_laying_on_ground` (lying down); transitions `stand_to_sit` and `sit_to_stand`, whose baked hips translation lowers and raises the body

- **Performance** (hand-authored singing and stage clips for a stationary
  VRM, 128 BPM, all from one stance so any two crossfade without foot slide):
  `stand_breathe` (their idle), `sing_gesture_a`, `sing_gesture_b`,
  `chorus_sway`, `sing_open_arms`, `hand_to_heart`, `look_up_sky`,
  `phone_raise`, `head_bow`, `wave_goodbye`, `bow_thanks`. Three have an
  other-hand `*_mirror` variant: `sing_gesture_a_mirror`,
  `phone_raise_mirror` (with its own `phone_raise_mirror_hold`) and
  `wave_goodbye_mirror`. The one-shots `hand_to_heart`,
  `look_up_sky`, `phone_raise` and `head_bow` each have a `*_hold` loop that
  starts on their last frame. Play the one-shot with `loop: false`, then the
  hold with a short `fade` once it lands. Beats, uses, the authoring script and
  its checker are in
  [performance_src](eidoverse/assets/animations/performance_src/README.md).

Helpers: `playVRMADefault(vrm, slot, { loopOnce, fadeIn, fadeOut })` sets up `globalThis._mixer`. The engine auto-updates `_mixer` each frame if set.

> **`playVRMADefault` REFUSES locomotion slots.** Calling `playVRMADefault(vrm, 'walk')` (or run/stairs…) **throws** — playing a locomotion clip in place is the "walking in place" treadmill bug (legs cycle, body never moves). Locomotion is owned by `VRMCharacterController` (`body.walkTo(x,z)` / waypoints), which moves the body AND grounds the feet with IK. `playVRMADefault` only plays stationary/expressive clips. The one exception — a VRM genuinely on a treadmill or carried by a vehicle — passes `{ force: true }` (or `globalThis._allowManualLocomotion = true`).

### Emotes + sitting on a stationary character

Expressive clips are for a VRM that is **not** being moved by a
`VRMCharacterController`. The controller owns the full-body clip while the
character walks/runs/climbs; an expressive clip played over locomotion fights
it (foot-slide, broken cycle). Use expressive clips when the character is
planted — a desk scene, talking to camera, an emote beat between moves. To go
from moving → emoting, let the controller run out of waypoints (or call
`controller.forceAction('idle', dur)`) first.

- `emote(vrm, 'cheer')` — play any expressive slot on a stationary VRM (loops by default). Same for `talk`, `reach`, `raise`, `fist`, `salute`, `dance`, `crazy`.
- `faceCamera(vrm, { offset })` — turn a stationary VRM to face the active camera. Use for talk-to-camera shots / reaction beats. `offset` (radians) for a ¾ or profile turn.
- `seatOn(vrm, chair)` — sit a character properly **in** a chair. Raycasts the chair's actual seat pan (a grid of downward rays → the broadest horizontal surface, so it ignores the backrest), plays a chair-sit clip (default `sitting_normal_chair`; `{ clip: 'sitting_nervous_arm_rub_chair' }` for a fidgety variant), then offsets the whole VRM so the HIPS rest on that seat (feet hang toward the floor). **Facing is automatic** — it detects the chair's backrest and faces the character AWAY from it, falling back to the camera if the chair has no detectable backrest. Works across chair models and across VRMs — seat height, per-VRM hip height, and sit facing are all measured at runtime, no constants. Pass `{ transition: 'stand_to_sit', fade: 0.3 }` to ease DOWN into the seat from standing instead of snapping into the seated pose.
  - **The chair MUST be a real visible mesh with an actual seat surface.** `seatOn` raycasts for the seat pan; an invisible 0.5m cube (or any prop with no broad horizontal top) gives nothing to sit on → they sit on nothing / mid-air. If `seatOn` can't find a seat surface it warns `SIT ON NOTHING` and points you at `sitOnGround`. Build/fetch a chair you can SEE in the frame.
  - **Do NOT `placeOn(vrm, chair)` to seat a character** — `placeOn` snaps the bbox-bottom (feet) onto the seat top, so they stand on the chair. And don't lower a standing `idle` figure to a guessed seat height — same artifact. `seatOn` is the way.
  - **Never write `vrm.scene.rotation.y` (or `position`) after `seatOn`.** The facing is already correct and the hips are already raycast onto the seat — a manual `rotation.y = Math.PI` after the call spins them to face backwards / out of the chair. To deliberately override for a ¾/profile/over-shoulder shot, pass it INTO the call: `seatOn(vrm, chair, { faceY })` (radians; +Z-forward convention from `VRMUtils.rotateVRM0`). Don't turn a character away from the camera just to hide a pose.
  - **The seated VRM is AUTO-EXEMPT from the placement audit — you don't need to do anything.** A seated character legitimately OVERLAPS the chair and has feet off the floor. `seatOn`/`sitOnGround` register the sitter in `globalThis._seatedVRMs` and both audits skip them, so they stay put. Do NOT mark the chair `noClippingCheck` to work around seating (that hides the seat from `seatOn`'s raycast → they sink); just call `seatOn(vrm, chair)` and leave them be. (`globalThis.unseat(vrm)` re-enables the audit if a scene later stands them up.)
- `sitOnGround(vrm, { clip, at, groundMeshes, hipHeight, faceY })` — sit on the **FLOOR**, NOT in a chair. A chair has a seat surface the hips rest on; the ground doesn't, so this rests the pelvis just above the floor and lets the legs fold. Default clip `sitting_on_ground` (cross-legged); pass `{ clip: 'sit_laying_on_ground', hipHeight: 0.0 }` to lie down. **Never floor-sit with `seatOn` or a chair-sit clip** — the legs dangle/clip through the ground. `seatOn` warns and points you here if it can't find a real seat surface.
  ```js
  await sitOnGround(vrm, { at: [0, 0], groundMeshes: [floor] });  // cross-legged floor-sit, faces camera
  ```

**Sitting clips available** (in `assets/animations/`): `sitting_normal_chair` + `sitting_nervous_arm_rub_chair` (chair — use via `seatOn`), `sitting_on_ground` (cross-legged) + `sit_laying_on_ground` (lying down) (floor — use via `sitOnGround`). Match the clip to the surface: chair clips need a chair, floor clips need the floor.

**Multiple characters — just animate each; the engine drives them all.** Load each VRM, then call `playVRMADefault` / `seatOn` / `sitOnGround` / the controller per VRM. The render loop updates EVERY loaded VRM's mixer **and** `vrm.update()` every frame (one mixer per VRM — replaying a clip on a VRM replaces its previous mixer, so idle+sit can't both play). Do **NOT** hand-roll mixer management for multi-VRM scenes — capturing mixers into your own vars, nulling `globalThis._mixer` between loads, or updating `_mixer1`/`_mixer2` in `renderFrame`. Each `seatOn`/`playVRMADefault` call is self-sufficient.

**Lip-sync when a VRM speaks.** If you lay TTS in a character's voice, drive the mouth: `lipsync.py` → `get_viseme_timeline(vocals.wav, fps)`, then per frame set `vrm.expressionManager` visemes (`aa`/`ih`/`ou`/`ee`/`oh`) + occasional `blink` and `em.update()`. Voice over a frozen mouth reads as broken.

Recipe — a character seated at a desk, facing camera:
```js
placeOn(chair, floor);                 // chair on the ground
await seatOn(vrm, chair);              // raycasts seat, sits hips-on-seat, faces camera
placeAgainst(desk, vrm, 'front', 0.15); // desk just in front of them
placeOn(laptop, desk);                  // laptop on the desk
```

### Nav diagnostics — `RobotDebug` (debugging aid, not set dressing)

`robot_debug.js` installs `RobotDebug` — an overlay that draws the nav
stack's internals: the lidar ray fan, the occupancy landmarks, and the
planned A* path. Attach it to a `VRMRobotBody` while DIALING IN a
navigation scene (why is she routing around nothing? what did the lidar
see?), then remove it — its visuals in a finished video read as glitch
lines coming off the character. Never leave it enabled in a final render
unless you explicitly want a "robot POV / diagnostics" look.

### Character locomotion (low level)
`VRMCharacterController` + `VRMFootControllerIK` — tread-synced stride, foot
grounding, stairs, turning, running, and the maneuver vocabulary (vault /
climb / jump / ladders — see "Movement vocabulary"). Two paths:

1. **Autonomous nav on flat ground (rooms, studios, streets)** —
   `VRMRobotBody` wraps the controller + lidar sensors + occupancy navmesh +
   A* planner so you give it destinations. It turns toward each waypoint and
   routes around obstacles. `collisionMeshes` are boxed (AABB) into the
   physics world, so this path is for flat floors + upright obstacles — its
   colliders flatten ramps/stairs.
2. **Ramps / stairs / locomotion-centric terrain** — wrap
   `eidoverse/terrain_base.js` (proper sloped colliders) and drive
   `charCtrl.locomote(dt, dir)` with a unit world-direction; set
   `enableTurning: true` to follow a turning path.
   Example: `eidoverse/examples/obstacle_course.js`.

Heading convention: `0` faces +Z, `Math.PI` faces −Z; the body turns toward
its travel direction at `maxTurnRate`. Locomotion and full emotes are mutually
exclusive — sequence them (upper-body gestures layer over the walk).

### Model (GLB) embedded animations — play them, don't fake them

Many fetched models (robot arms, machines, doors, rigged props) **ship
with their own animation** in `gltf.animations`. ALWAYS play it instead of
hand-rotating the mesh (rotating a static arm into the ground or bolting on
extra geo to fake motion is a tell). One call, and the mixer auto-updates:
```js
const gltf = await loadGLB(ASSETS.robot_arm);   // GLTFLoader result
globalThis.playModelAnimations(gltf, { clip: 0, loop: THREE.LoopRepeat });
scene.add(gltf.scene);
```
`{ clip }` selects by name or index (default: first clip; pass `{ clip: 'all' }`
to play every clip at once). You do NOT need to call `mixer.update` —
`playModelAnimations` registers it for per-frame auto-update. If the log says
"model has no embedded animations," only then animate it yourself.

**Duplicating a rigged/animated model — use `cloneModel`, NEVER `.clone()`.**
A naive `obj.clone(true)` of a skinned/rigged GLB shares the ORIGINAL's
skeleton, so every copy snaps to the same bones — fine while static, but the
moment the model animates, the clones **explode into disconnected pieces**.
To place a second copy of a fetched model, rebind it to its own skeleton:
```js
const armA = (await loadGLB(ASSETS.robot_arm)).scene;
const armB = globalThis.cloneModel(armA);   // SkeletonUtils — own skeleton, animates safely
```
`cloneModel` accepts the GLTF result or its `.scene`. Use it for ANY model you
duplicate; only plain unrigged meshes are safe with `.clone()`.

**Animated bird characters — crow & cactus wren.** Two purpose-built,
fully-clipped bird assets live in `eidoverse/assets/models/`. Each is one
skinned mesh with a named clip set, so `playModelAnimations` selects behaviour
by name:

| model | clips | size L×H×W |
|---|---|---|
| `crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Caw` `Talk` `TurnL` `TurnR` | 0.77 × 0.52 × 0.88 m |
| `cactus_wren_bird_animated_desert_songbird_calling_hopping_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Call` `TurnL` `TurnR` | 0.19 × 0.13 × 0.22 m |

Both are authored to drop straight in: **feet at the origin** (place them on the
ground with no offset hunting), **nose along +z** (registered in
`_forward_axes.json`, so `driveAlong`/`faceToward` get the sign right), and
**real-world scale** — crow 51 cm tall, wren 18.5 cm bill-to-tail. Don't rescale
them to "look right"; a wren really is that much smaller than a crow.

```js
const loader = new globalThis.GLTFLoader();
const crow = await new Promise((res, rej) =>
    loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.crow), '', res, rej));
globalThis.playModelAnimations(crow, { clip: 'Idle' });   // or 'Walk' / 'Fly' / 'Caw'
crow.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
scene.add(crow.scene);
```
`Walk`/`Hop` are **in-place** cycles (the feet slide back through stance) — drive
the body forward yourself, or the bird moonwalks. `Fly` is a level cruise: pitch
the whole model for a climb or dive. For a flock, `cloneModel` each extra bird
and offset its action time (`action.time = Math.random() * clip.duration`) so
they don't beat in unison.

**Paired call audio, pre-aligned to the clips** — in `eidoverse/assets/audio/`:

| file | length | use |
|---|---|---|
| `crow_caw_clip_synced.wav` | 1.60 s | two caws landing exactly on the two gape peaks of the crow's `Caw` clip (48 f @ 30 fps) — start it with the clip, no offset |
| `cactus_wren_call_clip_synced.wav` | 2.40 s | the wren's churr; the `Call` clip (72 f @ 30 fps) bobs the head on all 12 note onsets detected from this very file |
| `crow_caw_single.wav` | 0.74 s | one caw, for one-off / scattered background use |
| `crow_caw_says_claude.wav` | 0.41 s | the caw articulated into the word "Claude" |

Because each `*_clip_synced.wav` is exactly the clip's length, syncing is just
"start both at the same time" — no offset table. ⚠️ `crow_caw_says_claude.wav`
is subject to the **Claude-identity rule** above: use it only when the video
explicitly references the AI Claude, never as a generic bird noise.

The crow caws are our own Stable Audio 3 generations (`generate_sfx.py`), CC0
like the rest of the library — so they're safe to publish. Regenerate or extend
them the same way if you need a different call; score candidates against a real
caw's band profile (a crow caw puts ~70-80% of its energy in **0.8-2 kHz** — a
generation that lands mostly above 5 kHz is hiss, not a bird).


**In-world screens & displays = `globalThis.makeScreen`** — the canonical
animated screen panel (laptop telemetry, wall monitors, holo-panels,
dashboards, jumbotrons). Canvas-2D `draw(ctx, t, w, h)` callback →
sRGB CanvasTexture → UNLIT `MeshBasicNodeMaterial` with `toneMapped:false`
(exact UI colors, reads as an emissive display) — self-updating every
frame via the engine loop (`auto:true` default).

```js
const screen = globalThis.makeScreen({
    width: 0.9, height: 0.5, px: 768,      // world metres / canvas px
    draw(ctx, t, w, h) {                    // plain canvas-2D, t in seconds
        ctx.fillStyle = '#041018'; ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#8fe8c8'; ctx.font = 'bold 34px monospace';
        ctx.fillText('SURGE ' + (240 + Math.sin(t * 2) * 40 | 0) + ' MW', 24, 48);
    },
    // fps: 12          → throttled redraw (retro terminal feel, saves CPU)
    // transparent:false → opaque monitor face (writes depth)
    // lit: true        → takes scene light (a switched-OFF glossy panel)
    // auto: false      → drive it yourself: screen.update(t) in renderFrame
});
screen.mesh.position.set(0, 1.4, -2);  scene.add(screen.mesh);
```

Do NOT hand-build CanvasTexture screens in scenes — this helper IS that
pattern, done right. Full-frame HUDs / lower thirds still go through
`makeOverlayLayer` (screen-locked); screen-space glitch/CRT looks are still
`CustomEffectsDeno`'s job, never faked inside `draw()`.

**Canvas fonts.** Screen canvases are @napi-rs/canvas (Skia) canvases, which
look fonts up by family name among installed and registered fonts. In the
container the display fonts are installed system-wide; on a Windows
`--local` render the generic names `sans-serif`, `serif` and `monospace` are
not mapped to a matching face — they fall back to the system default face
(as an unknown name does), so text renders but `monospace` is not
monospaced. `drawTextFit`'s default font is `bold 48px monospace`. For a
specific look, register a bundled font in `setup()` and name that family in
`font`:

```js
const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
GlobalFonts.registerFromPath('eidoverse/assets/fonts/ShareTechMono-Regular.ttf', 'Share Tech Mono');
// font: 'bold 64px "Share Tech Mono"'
```

### TSL postprocessing — `CustomEffectsDeno`

**Use these for stylized looks — NEVER hand-roll them.** Drawing scanlines /
glitch bars / RGB-split / a "datamosh" of colored rectangles onto a per-frame
`CanvasTexture` overlay is the #1 anti-pattern here: it's CPU work every frame
(against the GPU-only rule), it reads as cheap, and it looks far worse than the
real shaders. A glitch beat is `glitch_bars` / `vhs_tape` / `rgb_shift` / `crt`,
not boxes you move around. (In-world screen/display CONTENT — animated or
static — goes through `globalThis.makeScreen`, which owns the canvas-screen
pattern; a full-frame fx overlay is never canvas work.)

```js
globalThis._fx = globalThis.CustomEffectsDeno.applyTo({
    scene, camera,
    effects: 'depth_fog,glitch_bars',   // comma-separated — chain 1-4 freely
    opts: { glitch_bars: { barFreq: 22, shift: 0.03, opacity: 0.85 } },
});
// per frame — update the effect's uniforms, THEN render. _fx.update(t) does
// NOT render (it only pushes uniforms into the auto-enhance pipeline); the
// scene render still has to happen, every frame, or the video freezes:
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);
```

**Timed glitch (a burst on a beat) — pulse the effect's live uniform, don't
swap canvases.** Every effect returns `uniforms`; drive them per frame:
```js
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'glitch_bars' });
// in renderFrame(t): ramp intensity on the beat
const u = globalThis._fx.uniforms;
if (u?.opacity) u.opacity.value = beatEnv(t);   // 0 most of the time, 1 on the hit
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);   // ALWAYS render after — update() doesn't
```

Always-on baseline (no opt-in): N8AO ambient occlusion + SSR + UnrealBloom + FXAA. Moving sky/cloud reflections on metals come from the sky system's `sky.enableReflections(camera, options)` (the `makeSky` facade in `eidoverse/sky_worlds.js` takes only `enableReflections(options)` and uses its own camera; see "WORLD-SPACE SKY + WEATHER").

**This list below IS the complete catalog (31 effects) — do NOT discover effects
by `grep`/`ls`-ing `effects_tsl/`.** A `| head` on that truncates the directory
ALPHABETICALLY, so you only ever see `after_image`…`dithering` and silently miss
the back half of the alphabet. Pick from the WHOLE list here, and **vary your
choice** — reaching for the same `glitch_bars`/`crt` every time wastes the palette.
Match the effect to the mood: `godrays`/`anamorphic_flare` (plus the sky
system's own shafts for outdoor epics), `vhs_tape`/`old_bw_film`/`bw_halftone` for retro, `neon_edges`/
`blueprint`/`retro_wireframe` for techy, `melt`/`wavy`/`kaleidoscope` for trippy,
`underwater`/`depth_fog` for mood. (Programmatic list at runtime: `CustomEffectsDeno.list()`.)

Library (31 effects) — the families:
- **3D/volumetric** (scene passes): `nuclear_explosion` (skies and rain are
  NOT effects — use the world-space sky + weather systems)
- **Glitch/retro** (the real glitch — use instead of hand-rolled bars): `glitch_bars`, `vhs_tape`, `crt`, `rgb_shift`, `chromatic_aberration_alpha`, `jitter`, `after_image`
- **Colour grade**: `full_toon`, `sepia`, `bleach_bypass`, `old_bw_film`, `bw_halftone`
- **Line/edge**: `cross_hatch`, `neon_edges`, `blueprint`, `dithering`, `retro_wireframe`
- **Atmospheric / light**: `depth_fog`, `godrays`, `lensflare`, `anamorphic_flare`, `underwater`, `rain_on_camera` (lens droplets — world rain is the weather system's job)
- **Distort**: `melt`, `wavy`, `kaleidoscope`
- **Blur/focus**: `focus_blur` (DoF), `radial_blur`, `box_blur`, `hash_blur`

### Era looks — `era_looks.js`

Graphic-arts looks from the history of computing and print. Every look is a
weight on one post pass, so looks crossfade and stack. They were made for
the DAISY music video, where each era's voice gets its era's picture. The
pass is not one of the injected effects above; a scene imports the module,
which registers `era_looks` with the same registry:

```js
const { registerEraLooks, ERA_LOOKS, applyLook } = await import(new URL('era_looks.js', EIDOVERSE_DIR).href);
await registerEraLooks();   // once, in setup(): registers 'era_looks', draws the line-printer glyph atlas
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'era_looks' });
// renderFrame(t): crossfade two presets (s = 0..1), update, then render
applyLook(_fx.uniforms, ERA_LOOKS.bell1961, ERA_LOOKS.mac1984, s);
await _fx.update(t);
await _r.renderAsync(_s, _c);
```

Pass the `camera`: `storybook` draws ink lines from its depth, and `crt`
restarts its phosphor persistence on a camera cut. `applyLook` smoothsteps
`s`. The pixel grid (`px`) snaps at the midpoint of a crossfade because it
cannot blend. The weights are ordinary uniforms, so set one over any preset,
for example `_fx.uniforms.glitch.value = beatEnv(t)` for a glitch on the
beat.

| Preset | The look | GPU cost at 1080p |
| --- | --- | --- |
| `clean` | nothing | — |
| `voder1939` | Art Deco gold duotone with a sunburst, grain, flicker | 0.03 ms |
| `bell1961` | 1960s black-and-white CRT | 0.06 ms |
| `printer1961` | line-printer ASCII on green-bar paper | 0.01 ms |
| `eliza1966` | sepia-tinted teletype monochrome | 0.01 ms |
| `vector` | green vector phosphor | ≈ 0 |
| `vfd1978` | cyan vacuum-fluorescent display | ≈ 0 |
| `c64_1982` | Commodore 64 palette, raster bars, 4 px pixels | 0.05 ms |
| `mac1984` | 1-bit ordered dither, 3 px pixels | 0.06 ms |
| `amber1984` | amber terminal with scanlines | 0.01 ms |
| `web2001` | 216-colour web-safe dither | 0.06 ms |
| `neural2016` | false-colour neural feature map | 0.05 ms |
| `glitch` | tear bands and split chroma | ≈ 0 |
| `zine` | risograph: two misregistered inks | 0.01 ms |
| `painterly` | Kuwahara paint | 0.10–0.14 ms |
| `poster`, `poster_night` | CMYK protest poster on newsprint: four rotated dot screens, misregistered plates, a line-art key plate | 0.12–0.21 ms |
| `crt` | curved CRT glass: scanlines that swell when bright, aperture grille, glass glow, persistence | 0.34–0.40 ms |
| `crt_8bit` | the Commodore 64 picture on a TV tube | 0.34–0.47 ms |
| `storybook` | storybook plate: soft cel bands, warm ink lines from depth, normals and colour | 0.09–0.16 ms |
| `candle_film` | candle-lit film: red-orange halation round highlights, gate weave, grain | 0.26–0.30 ms |
| `watercolor`, `watercolor_night` | wet paper: washes, pigment rims at edges, granulation, bleeds | 0.32–0.38 ms |

A preset is a dict of weights from 0 to 1. The look weights are `sepia`,
`deco`, `bw`, `ascii`, `vector`, `vfd`, `c64` with `raster`, `mac`, `amber`,
`websafe`, `feature`, `glitch`, `riso`, `kuwahara`, `halftone`, `phosphor`,
`toon`, `halation` and `watercolor`. On top of those are layers:
- `px`: pixel size, where 1 is off.
- `grain`, `flicker`, `scan` and `vignette`.
- `lift`: stops of print exposure for the paper looks.

The `_night` presets set `lift` so a dark scene prints readably. Use the
daylight preset (lift 0) for day scenes, or they overexpose. Build your own
preset as a plain object, for example `{ phosphor: 1, amber: 0.6 }`.

The costs are GPU time over `clean` on an RTX 5090 Laptop GPU; the whole
auto-enhanced test frame took about 5.2 ms. A look that is off costs nothing:
the heavy looks sit behind uniform branches, and the blur chains used by
halation, the CRT glow and the watercolour bleed skip their passes unless a
look that reads them is on. Those three add about 1–1.5 ms of CPU submit per
frame when on.

The pass receives linear HDR. The quantizing looks work in a perceptual
space. The print and paint looks work in display space through the
renderer's ACES curve and its exact inverse, so paper and ink land on screen
as authored; a few warm tones sit just outside ACES's range, so newsprint
prints a hair pinker. Halftone dots and watercolour paper stay fixed to the
screen like a real page, so motion slides under them. `storybook` draws its
lines alongside a VRM's MToon outline (on the claudesona the two coincide).

### Procedural toolkits

**`makeRobot` / `makeBot` / `RoboticsKit`** — INDUSTRIAL MACHINES with real
kinematics (creatures/humanoids stay `makeCreature`'s job). Everything is
slew-rate-limited and self-animating (engine drain) — you write NO per-frame code.

*Presets* — `makeRobot(type, opts)`: `arm` (6-DOF closed-form IK; `tool:
'gripper'|'hand'|'welder'`), `scara`, `delta`, `stewart`, `turret`, `agv`,
`gantry`, `printer` (full 3-axis FDM printer). Common opts: `position`,
`color`/`accent` (+ `bodyMaterial`/`accentMaterial` for ProceduralMaterials),
`scale`, `reach`, `auto: false` to drive it yourself.

*Kitbash uniques* — `makeBot(opts)` assembles machines from slots
(Automatron-style: any part fits any base, the BASE owns locomotion):
```js
const bot = globalThis.makeBot({
    base: 'tracked',              // pedestal|wheeled|tracked|legged|drone|ceiling
    torso: { family: 'military' },// industrial|military|utility|scout styling
    head: { family: 'military' }, // sensor face on torso.neck; idle look-around
    arms: [{ name: 'left', segments: 3, reach: 1.0, tool: 'gripper' }], // → torso shoulders
    mast: { stages: 3, maxHeight: 1.6 },
    turret: { sensor: 'dish', mount: 'mast.top' },   // dish|camera|lidar
    greebles: { density: 0.5, hazard: true },
    color: 0x4a5a48, seed: 3, position: [0, 0, 0],
});
scene.add(bot.group);
bot.base.patrol([[0, 0], [3, 1]]);            // wheeled/tracked/legged drive; drone flies ([x,z,alt])
bot.chain('left').pickAndPlace({ from: [1, 0.14, 0.5], to: [-1, 0.14, 0.5], period: 5, payload: box });
bot.turret.track(() => target);
bot.mast.extendTo(1.4);
bot.attach('welder', 'arm', { segments: 3, tool: 'welder', mount: 'torso.shoulderR' });  // live workbench
bot.detach('left');                            // returns the module — re-add its .group anywhere
```
- ANY Object3D is grabbable: pass it as `payload` (pickAndPlace measures its
  real width; `roundTrip: true` carries it back instead of respawning a fresh
  part) or call `arm.grab(obj)` / `arm.release()` directly. Keep the part
  smaller than the tool opening (~0.16 x reach for the gripper) or it logs
  a too-wide warning and refuses.
- PICKING REALLY PICKS: `segments: 3` chains are full arms — the jaws/fingers
  close to the payload's measured width, grab only when the tool is AT the part
  (`from`/`to` y = tool-tip height: for a box of height H sitting on the floor,
  use y ≈ H + 0.02 so the jaws straddle it). `tool: 'hand'` = humanoid hand
  (4 fingers + thumb, contact-accurate curl). Parts wider than the tool opening
  log a warning and are never grabbed.
- Addressing: `bot.frame('mast.top')`, `bot.joint('left.j2')`; `segments !== 3`
  chains are CCD (reachTo/follow only, no tool).
- Contraptions: `RoboticsKit.connect(parent, child, { at, offset })` /
  `a.mount(b)` chains ANY robots/Object3Ds (arm on AGV, turret on a creature's
  group…). Mounted children keep animating on a moving base.
- Textures: `await RoboticsKit.applyTextures(bot_or_preset, { diff: ASSETS.x,
  rough: ASSETS.y, normal: ASSETS.z }, { repeat: 2, part: 'body'|'accent'|'all' })`
  — same keys fetch_texture writes to tex_urls.json.
- TALKING (light-sync): every kit robot/bot can speak through its lamps —
  `bot.say('a sentence')` (duration from word count) or
  `bot.say({ duration: 4, energy: 0.9 })` pulses every emissive light in
  speech rhythm (+ a tiny head nod on makeBot heads);
  `bot.setTalkEnvelope((t) => amp01)` maps a REAL audio amplitude envelope
  onto the lights for TTS sync; `bot.stopTalking()` restores them.
- Chains without a `follow()`/`reachTo()` rest in a folded STOW pose (a
  parked-excavator tuck) — give an arm a task if it should look busy.
- In scenes that mix creatures + bots, create the CREATURES LAST (known
  render-order gremlin: earlier creatures go shadow-only).

- CREATURE CYBORGS (Spore x Automatron bridge): ONE CALL —
  `RoboticsKit.cyborg(creature, { head: {family:'military'}, wristR: true,
  back: true })`. It MEASURES the organic part under each anchor,
  auto-scales/centers the module, hides what it replaces (skull children,
  the organic hand), picks stance-aware mounting (biped back = behind the
  chest; quad back = base SEATED on the mid-spine, dorsal side), and
  everything rides the gait. BACK/HIPS modules are CYBER-ENHANCEMENT, not
  cargo: they emerge from a GRAFT — a socket collar sunk into the flesh
  with an emissive seam ring at the metal/flesh boundary, a buried spinal
  ridge, and feed lines diving into the body (no saddles, no straps).
  `back: true` default = a full 3-segment arm with the humanoid HAND
  (bare 1-2 segment CCD chains have no tool mounts and read as broken
  stubs — always give a visible chain 3 segments + a tool). A head-swapped
  creature can't jaw-talk — keep the organic head on a creature that
  speaks. Spec values: makeBot/makeRobot spec object, a prebuilt module,
  or `true` for defaults; per-entry `{ fit, offset, rotation, scale,
  seamColor }` overrides. Returns modules + grafts for programming
  (`mods.back.chains[0].chain.follow(...)`, `mods.backGraft`). Under the
  hood: `c.anchor('head'|'chest'|'back'|'hips'|'wristL'|'wristR')` are
  living BONES that `RoboticsKit.connect()` accepts — use them directly
  for full manual control.

**Robot scene direction:**
- SHOW the beat ON CAMERA: schedule pick/assembly moments to land inside the
  camera's framing, then VERIFY by extracting frames at those exact times —
  a log line saying it happened is not a shot of it happening. Hold a static
  framing through a grab (engage + descend + close takes 3-6s; the cycle
  clock also HOLDS until the tool physically arrives, so budget slack).
- Moving-base picks (drone/AGV arms): hover OFFSET from the pick point —
  a target directly on the arm's yaw axis is a singularity. Expect approach
  holds; don't time other beats to the pick's exact second.
- Payloads: any Object3D; size it to the tool opening (~0.16 x reach for the
  gripper) or the arm refuses (warning in the log). from/to y = TOOL-TIP
  height (part top + a bit) so jaws straddle the part.
- Shuttle loops: `roundTrip: true` (drop, lift, re-grip, carry back — no
  teleport respawn). FLY-AWAY-WITH-CARGO beat: poll `chain._carried`, then
  set `chain._program = null` and send the base away — it keeps gripping.
- Creatures in robot scenes: create them LAST (render-order gremlin), steer
  ONLY with walkTo/setHeading/speed (the gait owns heading — writing
  group.rotation.y does nothing), and route their paths around other bots'
  patrol lanes — nobody avoids anybody.
- `mountAt` must land INSIDE the parent's hull footprint or the module
  visibly floats beside it. Check odd overlaps from the CAMERA's position —
  perspective stacking reads as collision even at safe distances.


**`FabSim.print(machine, anyMeshOrGeometry, opts)`** (alias `PrintSim.print`)
— PRINT ANY MODEL in two states of matter: fresh deposits are MOLTEN metaball
goo riding the deposition front (makeIsoField GPU raymarch, realtime at
1080p; deposits UNSTAMP as they solidify), and beneath the melt band the
EXACT source mesh is revealed — crisp true geometry with procedural layer
lines; the finished print IS the source mesh. MACHINES: the i3-style
`printer` preset (moving bed — the field rebinds every frame), the `kossel`
(the REAL delta printer: linear towers with SLIDING CARRIAGES, rigid rod
pairs to the effector — no elbows — integrated plate/hotend/spool/bowden;
`makeRobot('kossel', { radius, height })`), or the rotary `delta` picker
doing industrial-cell FDM (it gains a stand, heated plate and flying
hotend; `stand: false` when it hangs from a rig). `{ duration, size, layerH, spacing, color, resolution (72),
ballCells (goo radius, 3.0), ballFlat (bead squash, 2.2), meltLayers (melt
band depth in layers, 1.5), plateSize }`. Self-animating;
`job.progress/done/solid` (the settled mesh).

Both machine sims are ORDINARY SCENE OBJECTS — parent the gantry/printer
anywhere, run several at once (each job owns only its own machine's axes),
nothing touches the camera. They compose into any larger scene like any other
bot. Caveats: a CNC gantry must be world-static while carving (the field
binds its bounds at job start — PrintSim handles its moving bed itself), and
the raymarched solid casts no shadow (CNCSim ships a proxy; small prints go
without).

**`FabSim.carve(gantry, anyMeshOrGeometry, opts)`** (alias `CNCSim.carve`) —
the INVERSE of print:
the gantry MILLS any model OUT of a solid metal block (voxel classification,
top-down subtractive passes, spinning cutter, chip spray, hot milling front).
The metaball isosurface renders through `makeIsoField` — raymarched per-pixel
on the GPU, realtime at 1080p at ANY resolution (resolution only costs setup
classification time). `{ duration, size, resolution (fidelity — 44 default,
96+ for hero shots), sink (bury an unmachinable base pinch below the stock —
a 3-axis mill can't undercut), color, margin, gpu: false (CPU MarchingCubes
debug fallback, ~1fps) }`. Finished regions HAND OVER to the
EXACT source mesh above the milling front (field rows zero as the mill
passes) — the finished part IS the fetched model and casts a real shadow.
Classification survives real-world models: DoubleSide parity probe, 3-ray
majority vote, open-shell meshes (hair cards) auto-skipped, streak-debris
scrub, sub-voxel milled-side grading. Self-animating;
`job.progress/done/solid`. Print it, or carve it — both take the same
"any mesh" input (VRMs included — blend shapes are stripped for the merge).
Both live in `fab_sim.js` (one module: additive + subtractive).

**`makeIsoField(opts)`** — GPU-raymarched isosurface over a CPU-written voxel
field: the fast path for ANY MarchingCubes-style effect (fields at 160³ render
realtime; three's MarchingCubes.update() per frame is the ~1fps trap). Same
field layout (`x + y*res + z*res²`); write `iso.field[iso.idx(x,y,z)]`, call
`iso.upload()` after a batch. Shading is REAL scene lighting — the raymarch
gradient normal feeds MeshStandardNodeMaterial via normalNode, and the
fragment writes true hit-point depth (correct occlusion both ways). `{
resolution, half, iso, color, metalness, roughness, steps, colorNode /
roughnessNode / emissive: (hitPoint, normal) => node (hit-point space — never
positionWorld, that's the proxy box), parent }`. If the parent MOVES, call
`iso.bind()` each frame to refresh the world bounds (PrintSim does — its bed
travels). Debug: `flat: true` or `shade: 'normals'`. Raymarched pixels can't
cast shadows — pair with a colorWrite:false proxy box (CNCSim does). NOTE: TSL
`mix()` with all-JS-number args emits INVALID WGSL silently (mesh skipped, no
error) — blend JS constants in JS.


**`makeParticles`** — sparks / smoke / dust / fire / magic, NEVER `BoxGeometry`
cubes or flat hand-looped planes. Camera-facing textured sprites whose motion
runs on the GPU (TSL `positionNode` — no per-frame CPU loop); billboarding
auto-updates. There's a ~80-texture library at `eidoverse/assets/particle_textures/`
(`spark_*`, `smoke_*`, `flame_*`, `magic_*`, `star_*`, `muzzle_*`, `glow_*`,
`dirt_*`, …) — add the one you want to scene.json `assets` and load it:
```js
const tex = await globalThis.loadImageTexture(globalThis.ASSETS.spark, { srgb: true });
globalThis.makeParticles({ scene, camera, preset: 'sparks', map: tex, origin: [0, 1, 0] });
```
- Presets: `sparks`, `embers`, `smoke`, `dust`, `snow`, `magic`, `stars`, `muzzle`, `fire` — each sets count/size/lifetime/gravity/blending/color; override any (`count`, `size`, `color`, `origin`, `gravity`, `speed`, `lifetime`, `area`, `grow`, `opacity`).
- `map` is optional (omit → a soft procedural dot), but **pass a real particle texture** — that's the whole point; an untextured cube or a bare dot is the tell.
- You call nothing per frame — motion + billboarding self-update. Returns `{ mesh, material, update, uniforms }`; pulse `uniforms.opacity.value` for a burst.
- Anything that should glow (sparks/fire/magic) uses additive blending automatically; smoke/dust/snow use normal blending. NEVER fake a spark/ember with a tiny emissive box.

**`createFlora`** — the VEGETATION BRUSH: asset-driven species with real map
sets (albedo/normal/roughness/translucency under `eidoverse/assets/grass/`),
GPU-instanced whole plants, 3-layer wind, and character pushers that part the
foliage around a walking body. One call paints one stand ("stroke"); layer
strokes to dress a scene. Async — `await` it.
```js
const f = await createFlora({ species: 'grass', size: 30, height: 0.45,
    color: 'copper', heightFn: terrain.heightAt, sunDir: SUN_DIR });
scene.add(f.mesh);
// per frame (walkers part the plants; slot 2 can ride the camera):
f.setPushers([{ x: p.x, y: p.y, z: p.z, r: 1.1 }]);
```
- Species: `grass` (green turf carpet — the meadow default), `galleta_dry`
  (desert bunch grass), `blackbrush`/`creosote`/`sagebrush` (real Mojave shrubs — grown skeletons,
  welded wood tubes with bark maps + foliage spray cards), `yucca` (Mojave
  yucca: bayonet crown, dried skirt, bendy trunk), `corn` (full plant: cane,
  arching leaves, husked ears with a BAKED real cob, silk, tassel),
  `sunflower` (full plant: cane, petioled heart-leaf canopy, one nodding
  head — seed-disc plate, dense fitted ray-petal whorl, bract rosette back;
  the head rides wind as one rigid assembly).
- Footprint: stands are CIRCULAR by default (never square); `size` = diameter,
  or `width`/`depth` for ellipses; `footprint: 'organic'` masks a lobed
  irregular patch; `center: [x,z]`. De-centre overlapping strokes — concentric
  same-centre stands foreshorten into stamped bands.
- `density` = interior fullness (1 = authored); `seed` varies everything
  (any finite integer, including 0 and negatives);
  on ROW plantings it works both ways: below 1 it leaves gaps in the rows,
  above 1 it tightens in-row spacing (a grid cannot hold more plants on
  command; the row gap is the machinery's, the in-row spacing is the crop's);
  `variant` picks another grown skeleton for shrub/corn species.
- Grass options: `height` (metres) sets blade length AND wind compliance (lawns
  are stiff, tallgrass sways); `color` = a GRASS_COLORS name — spring `green/
  lime/emerald/blue/blue-green/gray-green`, fall `burgundy/rust/copper/orange/
  straw/brown` — or a custom `[r,g,b]` multiplier. Blade grasses only.
  ⚠ The green family are MULTIPLIERS over the atlas; the rest are luminance
  RECOLORS (they discard the sheet's hue). A species authored in another hue
  (galleta_dry ships a straw recolor) can only be returned to green by a
  recolor — hence `green` — because its own recolor runs last and a
  multiplier cannot survive it.
- Corn: pair with `rows: { spacing: 0.9, plant: 0.24, angle, jitter, skip,
  stride, phase }` for a planted field (rectangular = cultivated; stride/phase
  interleave variant calls through ONE grid — e.g. every 5th row seeded with
  `corn: { peel: true }` for open cobs). Plants carry 1-3 ears, independently
  open/closed (`corn: { peelChance }`). A skipped row pair (`clipFn`) makes an
  honest drive lane — an in-canopy camera NEEDS one (or a pusher riding the
  lens) or it eats leaves.
- Sunflower: same `rows` treatment (spacing ~0.85, plant ~0.5); `heading`
  (world azimuth, ± `headingJitter`) points every plant one way — sunflower
  fields face the sun together; omit it for the wild-patch look. Lookdev
  pins via `sunflower: { pitch, headYaw, rank, stalkLean, heightJitter }`.
  Card widths follow `assets/grass/sunflower_fit.json` — the measured alpha
  envelope of the sheet's petal cells + leaf window (re-measure it whenever
  the art changes; the format lives in vegetation_sunflower_gen.js, which
  falls back to built-in envelopes without the file).
- Placement: `heightFn: (x,z)=>y` OR `surface: mesh/[meshes]` (raycast down —
  grows on ANY geometry: rocks, rooftops, sculpted ground; misses = no plant;
  hit normals are taken in world space, so a rotated or uniformly scaled mesh
  such as a `PlaneGeometry` laid flat with `rotation.x = -Math.PI / 2` works);
  `align` = surface-normal tilt share (grass hugs, woody stays skyward);
  `maxSlope`; `clipFn(x,z)`; explicit `placements: [[x, z, scale], ...]` for
  hero plants. Structural species claim footprints in a cross-stroke occupancy
  registry — later strokes avoid them (`avoid: false` opts out;
  `resetFloraOccupancy()` between scenes if you rebuild).
- Returns `{ mesh, stemMesh, material, update, setPushers, uniforms, count }`.
  Wind self-updates. `sunDir` should match your key light. Budgets: whole
  plants are 0.5-3.3K tris each and instanced — thousands are fine.
- The MOJAVE recipe (desert dressing, field-approved): galleta base + the
  three shrubs as de-centred organic strokes, two seeds each, yucca kept off
  the walk line with heroes staged by hand:
  ```js
  await addField('galleta_dry', { width: 56, depth: 46, seed: 3, density: 1.3 });
  await addField('blackbrush', { width: 54, depth: 46, seed: 5, density: 0.85, center: [6, -4], footprint: 'organic' });
  await addField('blackbrush', { width: 54, depth: 46, seed: 55, variant: 1, density: 0.85, center: [-7, 6], footprint: 'organic' });
  // creosote + sagebrush: same pattern, own seeds/centres
  await addField('yucca', { width: 54, depth: 46, seed: 21, density: 0.7, clipFn: (x, z) => Math.abs(x) < 1.4 });
  await addField('yucca', { placements: [[2.4, 8.5, 1.9], [-2.5, 4.0, 2.3]] });   // heroes
  ```
  A field of ONE cloned skeleton reads as wallpaper — always two seeds per
  shrub species, and de-centre the strokes (concentric same-centre ellipses
  foreshorten into stamped parallel bands from a low camera).

**`makeParticleMorph`** — a GPU particle CLOUD that MORPHS between point-set
targets: dissolve a mesh/VRM into volumetric particles and reform it into
another shape (teleports, summons, shape-forms, a body→diagram→body sequence).
Position is `mix(targetA, targetB)` + curl turbulence, all on the GPU (TSL
`positionNode`, no CPU loop), billboarded like `makeParticles`.
```js
const m = globalThis.makeParticleMorph({
  scene, camera, count: 60000, map: glowTex,
  targets: [ ParticleMorph.fromMesh(vrm.scene, 60000),       // sample a mesh/VRM surface (skinned-aware, current pose)
             ParticleMorph.neuralNet({ count: 60000 }) ],    // or .neuronGraph / .fromPoints / .fromText
  color: 0x55e0ff, color2: 0xc060ff, size: 0.014,
  blending: 'additive', curl: { scale: 1.5, strength: 0.55 },
});
// per frame, from your timeline:
m.morph(0, 1, t01 /*0..1*/, turbulence);   // morph A→B
m.uniforms.opacity.value = fade;            // fade the cloud in/out
m.uniforms.vortex.value = 5;                // optional spiral/vortex reassembly during a transition. `size` defaults to 0.014 (tuned for close-ups) — at a pulled-back camera (5m+) pass `size: 0.03-0.05` or the cloud reads dim
m.updateTarget(0, ParticleMorph.fromMesh(vrm.scene, m.count));  // recapture a LIVE pose at the dissolve instant so the handoff matches
```
- Target generators: **`ParticleMorph.fromMesh(obj, count)`** (surface-sample any mesh/VRM in its current pose), **`ParticleMorph.fromText('WORD', count, { width, ascii, fontSize, depth })`** (rasterized text or multi-line ASCII art → 3D point cloud), **`ParticleMorph.neuralNet({layers,...})`**, **`ParticleMorph.neuronGraph(...)`**, **`ParticleMorph.fromPoints(arr, count)`**.
- All targets are resampled to `count`; share centroids if you don't want a jump between A and B. Pass a soft `glow_*` texture as `map`.
- To match a moving/posed VRM at the handoff: play the anim live, then `updateTarget(0, fromMesh(vrm.scene, count))` at the dissolve frame and freeze the pose (so dissolve/reform/snap-back all line up).

**`ProceduralMaterials`** — required for every procedural surface (NO flat colors):
- Generators: `scratches`, `smudges`, `noise`, `voronoi`, `patches`, `pores`, `weave`, `grain`
- Factories: `createPaintedMetal({ color, scratches: true, smudges: true })`, `createRubber()`, `createSkin({ color, patches: {patchColor, shape: 'blob'} })`, `createScaly()`, `createFabric()`, `createWornMetal()`
- Compositing: `composite(texA, texB, 'multiply')` layers procedural detail onto Poly Haven base textures
- All factories output NodeMaterial with basecolor + roughness + metalness + normal — required minimums


**`makeCreature`** — the universal procedural creature builder (Spore-style):
one spine+parts+gait system parameterized into ANY morphology. Stances:
`'quad'` (+ `legPairs` 2-4), `'biped'` (arms, optional hands), `'bird'`
(horizontal body, hooked two-mandible beak, two-segment folding wings, walk
head-bob), `'serpent'` (ground-fixed path following — the S-curves stay
planted in the world while the body slides through them; tongue flicks,
rests in its curve), `'octopus'` (mantle + 8 wave-animated tentacles),
`'insect'` (tripod gait, compound eyes, antennae, buzzing translucent
wings — `wings: 4` = dragonfly), `'spider'` (alternating-tetrapod gait,
fanned wide splay legs, abdomen bulb, 8-eye cluster, chelicerae).
Auto-rigged (real Skeleton, analytic weights); gaits carry body language
(human pelvis/weight-shift/heel-toe roll + settle-on-stop, quad strike bob
+ head nod, arthropod skitter). Flight (`c.fly(alt)` / `c.land()`): fast
downstroke + lagging hand segment, pitch into climbs, banking into turns.
ANIMAL FACES on tube heads: quads default a lofted `muzzle` (nose pad; the
mouth IS the hinged talking jaw — no static slit);
iris/pupil eyes with hooded lids (`eyeColor`, `pupil:'slit'`),
`ears:'point'|'flop'|'round'` (flick-animated), `fangs`, curling `tusks`,
`horns` + `hornStyle:'spike'|'ram'|'antler'`. FEET: `feet:'shoe'|'paw'|
'hoof'|'webbed'|'lizard'|'talon'` — ankles plant at foot height so soles
rest ON the ground. `'fish'`: tail-amplified swim wave, caudal/dorsal/
pectoral fins, banks into turns, hovers at `swimDepth`. Quads auto-pick a
4-beat lateral WALK at low speed / diagonal TROT above ~0.75 m/s (`gait`
override; phases blend on transition). EVERYTHING MIXES — parts are gated
by options, not stance: beak on a quad + webbed + `tailStyle:'paddle'` =
platypus; `trunk` + `tusks` + `ears:'round'` + `earScale: 2` = elephant;
`neck: 1.3` + `legLength: 1.15` = giraffe; wings on anything = dragons.
`eyelids: 0..1` sets droopiness (they still blink).
MORE ORGANS: `'snail'` stance (slug glide, eye stalks, spiral shell —
`shell: true` mounts it on ANY creature), `wingType: 'bat'|'butterfly'`
(butterflies fold upright at rest), `hornStyle: 'moose'|'narwhal'`,
`nose: 'star'`, `buckTeeth`, `beakWidth` (duck ≈1.6), `spikes`, `armor`,
`gills`, `claws`, `antennae` (metal + glowing when robot), `squid: true`,
`build: 'feminine'` + `hair: 'long'`, `tailCarry` (raised cat curl),
`whiskers`, `tailRadius`, `finScale` (sharks). Accessories also:
`helmet: 'space'|'hardhat'`, `glasses`, `mask: 'smile'|'frown'`,
`hat: 'cowboy'|'officer'`. CYBORGS: `robotParts: ['arms','legs','head',
'tail','neck','body','tentacles']` robots individual elements. Custom
materials: body takes `map`/`normalMap`/`roughnessMap`; add-on parts are
NAMED meshes — `c.parts('shell')` returns them for material swaps. `makeCreature.human()` = sculpted skull head (jaw,
brows, hair), raised shoulder points, relaxed elbows, sleeve/collar shirt
treatment. ACCESSORIES on any creature: `hat:'cap'|'top'|'beanie'`,
`sunglasses: true`, `tie` (bipeds). `robot: true` = metallic panel plating,
LED iris eyes, joint caps. Tube junctions are sealed by weld balls — no
seams at tail/neck/hip joints in any pose.
Skins: procedural TSL patterns (`pattern`, colors), clothing color bands
(`outfit: {shirt, pants, shoes}`), or IMAGE textures (`map`/`normalMap`/
`roughnessMap` — tube UVs run u-around / v-along; set texture.repeat).
```js
const wolf = globalThis.makeCreature({ stance: 'quad', ears: 'point', fangs: 1,
    muzzle: 1.1, feet: 'paw', color: 0x6f7378, speed: 0.5, seed: 9 });
scene.add(wolf.group);                                 // self-animating
wolf.walkTo(4, 2);  wolf.speed = 0.8;  wolf.setHeading(a);   // steering
const person = globalThis.makeCreature(makeCreature.human({ shirt: 0x3a6ea8,
    hat: 'cap', sunglasses: true, tie: 0x2a2a30 }));
const ram = globalThis.makeCreature({ stance: 'quad', horns: 2, hornStyle: 'ram', feet: 'hoof' });
const spider = globalThis.makeCreature({ stance: 'spider', color: 0x3a2c22 });
const dfly = globalThis.makeCreature({ stance: 'insect', wings: 4 });
const bot = globalThis.makeCreature(makeCreature.human({ robot: true, hair: 'none', outfit: null }));
const wild = globalThis.makeCreature(makeCreature.random(42));
```
- TALKING — every jawed head is hinged (skull chin, animal lower jaw, beak
  mandible; serpents/fish have no jaw): `c.say('Some words')` (duration from
  word count) or `c.say({ duration: 4, energy: 0.9 })` flaps procedural
  syllables and reveals a dark mouth interior; `c.talking = true/false` for
  continuous; **`c.setTalkEnvelope((t) => amp01)` maps a REAL audio
  amplitude envelope onto the jaw** — pair with `lipsync.py`'s
  `get_mouth_openness` per frame for TTS-synced creature speech.
  `c.hasJaw` tells you if this head articulates.
⚠ **PROBE WARM-UP — creatures look BROKEN at frame 0, not just dark.** A
creature's gait and foot-plants assemble over the first ~1-2 seconds; at
frame 0 the body renders as scattered spheres with a detached floating
head — which looks exactly like a catastrophic skinning/engine bug.
Shadow maps and pipelines also
settle over the first frames (a t=0 probe can look black), and particle
systems start clumped at their emitters. NEVER judge creatures,
particles, or lighting from a single frame-0 probe: render ≥1.5s and
judge the LAST frame. To probe a mid-film beat, give `renderFrame` a
time-offset hook (`t += Number(Deno.env.get('T_OFFSET') || 0)` at the
top) and render a 1.5-2s window that ENDS on the beat you care about.
Creatures that must be pre-settled but unseen (a late reveal) should
wait PARKED far from camera on real ground — a hidden group can't warm
up, and a cold reveal scrambles on camera.

**Silhouette Parallax Occlusion Mapping (SPOM)** — ray-march a height map to give a surface real interior depth AND an outline that follows the relief, so the mesh EDGE shows the bumps in profile instead of a flat polygon line. Backed by our `parallax_occlusion.js` library (`parallaxOcclusionUV`). Two helpers: **`createReliefColumn`** (curved surfaces — the easy, correct path) and **`createParallaxMaterial`** (flat surfaces + full control).

**FIRST decide flat vs curved — this is the whole game.** Plain POM only fakes INTERIOR depth; the outline still ends at the polygon edge. You only SEE "silhouette" POM by looking at the mesh EDGE against the background at a grazing angle:
- **FLAT** (wall, plate, floor, tread): the outline crenellates along the tile trim. `createParallaxMaterial({ silhouette: true })`, `curvedSilhouette` stays off.
- **CURVED** (column, pipe, sphere, capsule): the relief must OVERHANG the round base outline. That needs THREE things together, and missing ANY one renders as plain interior POM (the classic "it looks flat" failure): (1) `curvedSilhouette:true` + per-axis `curvature`, (2) `inflate` = the relief peak in world units (a `positionNode` that pushes the shell out past the base outline), (3) a plain core just inside to fill where the shell clips. **`createReliefColumn` wires all three — reach for it before hand-rolling a curved surface.**

```js
// CURVED — a column/pipe whose flanges + bolts overhang the round outline.
// Returns a Group (inflated SPOM shell + fill core + end caps). One call.
const col = globalThis.createReliefColumn({
    heightMap, albedoMap,              // THREE.Texture; height in .r, WHITE = peak
    radius: 0.5, height: 3.2, aroundTiles: 3,   // aroundTiles = relief tiles around the barrel
    depthScale: 0.15,                  // relief depth; reliefFactor:0.7 tames thin pipes
    lightDir: KEY_DIR,                 // WORLD dir TOWARD the key light (drives self-shadow)
    roughness: 0.55, metalness: 0.18,  // + any MeshStandardNodeMaterial opts
});
scene.add(col);                        // rotate the Group to lay a pipe on its side

// FLAT — a wall/plate that carves its outline along the relief trim.
const geo = new THREE.PlaneGeometry(9, 4.2);  geo.computeTangents();  // REQUIRED (tangent-space march)
const wall = new THREE.Mesh(geo, globalThis.createParallaxMaterial({
    heightMap, albedoMap,              // heightMap IS fetch_texture's `displacement` map
    depthScale: 0.05,                  // SMALL for a whole-face tile (UV-tile units); ≲0.06 or it shears
    minViewZ: 0.14,                    // bounds grazing-ray smear (raise for big walls)
    silhouette: true,                  // false = interior POM only (e.g. a floor)
    lightDir: KEY_DIR,                 // self-shadow on unless selfShadow:false
    roughness: 0.7, metalness: 0.15,
}));
wall.castShadow = wall.receiveShadow = true;  scene.add(wall);
```

The material is a real **lit `MeshStandardNodeMaterial`** — the relief is lit, self-shadowed (a second march toward `lightDir`), and its **shading normal is derived from the height field by default** (`heightNormal:true`), so it shades like geometry with NO normal map needed. It also sets `maskShadowNode` so cast shadows follow the carved outline; `createReliefColumn` additionally enables the relief self-shadow mode so recesses shadow themselves. `computeTangents()` is mandatory (POM marches in tangent space) — as a safety net, the helper audits the scene at first render: a POM mesh with no tangents gets them auto-computed (the warning names the mesh), and when they can't be computed (merged non-indexed geometry) the relief shading normal is disabled instead of miscompiling into an invisible mesh (`THREE.Node: Recursion detected` on a POM surface means exactly this). It also warns on `curvedSilhouette` without `inflate` and other footguns — read the warnings; they name the exact fix. (Never `MeshBasicNodeMaterial` — it renders all-black under the march.)

**How to EVALUATE a SPOM render (or you'll ship plain POM by mistake):** pull the camera BACK so the whole object, its silhouette against the background, AND its floor shadow are all in frame; put it in a LIT scene with a real floor; ORBIT so the silhouette sweeps. A zoomed-in, barely-moving shot of a dark panel proves nothing. On a curved surface, confirm the relief peaks visibly **bulge past** the round base outline.

Other field notes: the silhouette only reads as *bumpy* where the relief reaches the UV-tile edge — relief inset from the boundary just trims a clean strip. Discarding on a CLOSED box reveals the culled interior (fine on exterior walls; see-through on a lone box). Raw PolyHaven `_disp` maps are low-contrast mid-gray — contrast-stretch them or the carve is invisible, but FLOOR the stretch (map to ~[0.15, 1]; pure-black wells = degenerate full-depth rays). depthScale is in UV-tile units: for a whole-face single tile keep it small (≲0.06); with world-projected metre UVs pass `depthScale = metres × uvScale`. Debug ladder: `debugMarch:true` paints the raw march unlit (first-line diagnosis), `debugSilhouette:true` paints discards magenta.

**Natural phenomena — use the real raymarched/sim effect, not a billboard
or a sine-displaced mesh.** These read with true depth and motion:
- **Screen-filling nuke / shockwave** → the `nuclear_explosion` effect — a
  SCREENSPACE post effect (fills the frame; add it to the `effects:` string).
  Use it when the blast IS the shot.
- **Sky + clouds** → the WORLD-SPACE SKY SYSTEM (`makeSkySystem`, full
  section below) — cloud types, time-of-day, sun/moon/stars, day cycles.
- **RAIN / STORMS** → the WEATHER SYSTEM (`makeWeatherSystem`, same
  section) — states from fair to darkstorm with world-anchored rain,
  wet surfaces + puddles, from-the-clouds lightning, and smooth
  agent-directable transitions. Add `rain_on_camera` (LENS rain —
  screen-locked refracting droplets + wet blur) on top only when the
  shot wants a lens inside the storm.
- **Water / pours / splashes** → `fluid_swe` (ponds / pools / springs /
  pours / wading, with whitewater from the sim's own state; a `bedFn`
  shaped as a vessel interior makes cups and basins fillable too), plus
  `WaterMesh` for horizon-filling passive ocean.

## WORLD-SPACE SKY + WEATHER (`eidoverse/sky_system.js` + `eidoverse/weather_system.js`)

The sky is GEOMETRY-AWARE volumetrics, not a post effect: clouds live on a
camera-centered dome rendered in the scene pass, so buildings, terrain, and
characters occlude the sky naturally, reflections move with the clouds, and
sky elements can sit beyond the atmosphere. Use this for every outdoor sky.

```js
eval(Deno.readTextFileSync('eidoverse/sky_system.js'));
const stars = await globalThis.loadImageTexture(ASSETS.starmap, { srgb: true }); // eidoverse/assets/sky/starmap_tycho_4k.jpg
const moon  = await globalThis.loadImageTexture(ASSETS.moonmap, { srgb: true }); // eidoverse/assets/sky/moon_color_1k.jpg
const sky = await globalThis.makeSkySystem({ scene, textures: { stars, moon },
    opts: { hours: 15, clouds: 'cumulus' } });
sky.applyToLights({ sun, hemi, fog: scene.fog });   // palette drives the scene lights
// per frame: sky.update(t, camera)  — REQUIRED (drift, matrices)
```

- `sky.setTime(hours 0-24)` — sun/moon arcs, palette, stars fade. For a day
  cycle call it per frame and re-run `applyToLights` each frame too.
- `sky.setClouds('cumulus'|'stratus'|'cirrus'|'clear', overrides?)`.
- `opts.azimuth` aims the sun's arc (put sunrise in front of the camera);
  `opts.moonAngularDeg` scales the moon disc (16 = a looming companion
  world; its texture is any 2:1 equirect); `opts.ringCurve = R` bows the
  cloud deck upward along ±z to follow a curved megastructure horizon.
- `sky.enableReflections(camera, options?)` — per-pixel MOVING cloud
  reflections on metals (SSR composes on top; geometry occludes sky
  reflections). `options.gain` (default 1) scales the reflection. The
  `makeSky` facade (`eidoverse/sky_worlds.js`) takes the options only —
  `enableReflections(options)` — and uses the camera passed to `makeSky`
  (else `globalThis._c`).
- `await sky.bakeEnv(renderer)` — bakes the real sky into
  `scene.environment` for env-IBL/transmission. **It OVERRIDES any
  agent-set HDRI by default** (the sky owns the world's light); interiors
  that keep their own HDRI pass `{ ifAbsent: true }`.
- `sky.tslCloudShadow(positionWorld, k)` / `sky.wrapCloudShadows(scene)` —
  drifting cloud shadows on ground materials; `sky.weatherAt(x, z)` (JS)
  and `sky.sunCoverageDim(x, z)` for gameplay/light coupling.

```js
eval(Deno.readTextFileSync('eidoverse/weather_system.js'));
const bolt = await globalThis.loadImageTexture(ASSETS.bolt_trace, {});          // eidoverse/assets/particle_textures/trace_06.png
const drop = await globalThis.loadImageTexture(ASSETS.rain_drop, { srgb: true }); // eidoverse/assets/sky/rain_streak.png
const weather = await globalThis.makeWeatherSystem({ scene, sky, opts: { textures: { bolt, drop } } });
weather.wrapScene();                       // wet-darkening + puddles + cloud shadows on scene materials
weather.setWeather('storm', 1);            // clear|fair|sunshower|overcast|rain|storm|cyclone|darkstorm
sun.intensity *= weather.sunDim();
// per frame: weather.update(t, camera)  — REQUIRED (rain, lightning, greying)
```

- `weather.transitionTo(name, k, durationSeconds)` — SMOOTH weather change:
  everything (cloud coverage, rain, wind, lightning odds, greying, wetness)
  eases across the window. Duration is yours to direct: `90` = a storm
  rolling in over a minute and a half; defaults `k = 1`, 45 s. One call, no
  other steps.
- Weather couples the sky automatically: coverage presets, sun dimming,
  wind-driven cloud + rain drift, from-the-clouds lightning with distant
  sheet flashes on harsh states, world-tiled rain curtains under dense
  cells. Mark materials `userData.noWet` to skip wetness; sky-element
  materials should set `userData.keepEnv` so reflection-hook env
  suppression leaves their env-IBL alone.
- Scene lights should re-apply per frame during transitions/cycles:
  `sky.applyToLights(...)` then `sun.intensity *= weather.sunDim()` and
  `hemi.intensity *= weather.hemiDim()` (the hemisphere-light multiplier:
  `0.5 + sunDim × 0.5` unless the preset authors its own, as `darkstorm`
  does).

### PICK A PACKAGE — the skies are whole looks, not parts bins

Every sky is a **wholesale, dialed-in look-dev package**. Select one; do not
assemble your own out of the internals. The engine exposes seams (a celestial
hook, palette tints, cloud phase terms) because the packages are built on
them — they are not a menu for inventing a fourth world, and recombining
them is how you get a sky that reads broken.

**Three worlds** — the complete set (names as they appear in Eanpa):

| key | world |
|---|---|
| `earth` | Earth |
| `ringworld` | Orbital / Halo |
| `shieldworld` | Earth 5129323011 CE (Red Giant) — far-future Earth under the expanded Sun, behind a hex shield |

Two of the three ARE Earth. `shieldworld` is not an alien planet — it is this
planet, five billion years on, under a hex shield. Its star fills roughly a
third of the sky and its surface visibly churns, so give it room in frame.

**Four cloud types:** `clear` · `cumulus` · `stratus` · `cirrus`
**Eight weather states:** `clear` · `fair` · `sunshower` · `overcast` ·
`rain` · `storm` · `cyclone` · `darkstorm`

### The true sun and moon — `sky.sunDir` / `sky.moonDir`

`sunDir` and `moonDir` are the true world-space unit directions of the sun
  and moon. After dusk the facade reuses its directional light for the moon,
  so the light's position is not the sun at night. Read `sky.sunDir` when
  something must follow the sun itself, such as a flare, a corona, or flowers
  turning to face it.

### Sun corona — `sun_corona.js`

A corona of light-petals around the true sun. It was made for DAISY's
finale, where the sun opens as a day's eye (the Old English *dæges ēage* that
became "daisy"). The corona is a camera-facing card parked far along the sun
direction and drawn additively over the sky. It tests depth but does not write
it, so nearer geometry and the horizon occlude it, and the bloom pass makes
its petals glow.

```js
const { makeSunCorona } = await import(new URL('sun_corona.js', EIDOVERSE_DIR).href);
const corona = makeSunCorona(THREE, { petals: 12, size: 400 });
scene.add(corona.mesh);
// renderFrame(t), after sky.update(t):
corona.update(camera, sky.sunDir, open, t);   // open 0..1: 0 = folded shut (hidden), 1 = full petals
```

The options are:
- `distance`: 1500 m by default. Keep `distance + size / 2` inside the
  camera's `far`.
- `size`: 400 m.
- `petals`: 12.
- `color`: linear RGB, a warm orange by default.

It returns `{ mesh, U, update }`. `U.gain` scales the brightness; `update`
drives `U.open` and a slow turn, like a flower tracking the light. The corona
hides itself when shut or when the sun is below the horizon. Against a bright
clear sky the bloom renders it almost white; a sunset sky keeps its colour.
Pass `sky.sunDir` rather than the light's position (see above).

### COLOUR OVERRIDES — retint a package, don't rebuild it

These are the ONLY sanctioned way to deviate from an authored look. Each is a
per-channel multiplier that applies *after* the preset has driven its value,
so it retints the dialed-in look and everything else (lightning coupling, sky
response, day-cycle timing) still reads through. Omit one to keep the
authored colour; `[1, 1, 1]` is the identity.

```js
// at construction
const sky = await globalThis.makeSkySystem({ scene, textures: { stars },
    opts: { hours: 15, clouds: 'cumulus',
            cloudColor: [1.0, 0.72, 0.55],       // cloud body tint
            sunColor:   [1.0, 0.85, 0.70] } });  // star light + disc
const weather = await globalThis.makeWeatherSystem({ scene, sky,
    opts: { textures: { bolt, drop },
            rainColor: [1.6, 0.55, 0.35] } });   // streaks + splashes

// or live, any time
sky.setColors({ cloud: [...], sun: [...], star: [...], shield: [...] });
sky.setColors({ sky: [...] });   // the atmosphere (zenith + horizon) and all its readers — distance fog, haze, rain curtain
sky.setColors({ fog: [...] });   // final multiplier on just the scene fog colour — grade the haze without moving the sky
weather.setColors({ rain: [...] });   // also cloud/sun/shield; forwards to the sky ONLY the channels named
sky.getColors(); weather.getColors();            // read current multipliers
```

- `rainColor` — precipitation streaks and splashes.
- `cloudColor` — cloud body lighting.
- `sunColor` — the star's light and disc.
- `star` — **shieldworld only**: retints the red giant's own surface. The
  granulation, convection cells, hot patch and limb keep their structure;
  only the hue moves. Push blue for a hotter star, red for cooler.
- `shield` — **shieldworld only**: the hex shield lattice. Values above 1 are
  intentional, it is emissive; the authored cyan is `[0.38, 0.95, 1.3]`.

`star` and `shield` route to the celestial module, which registers itself
during `rg.attach({ scene, sky })` — so **call them after attach**, or they
silently no-op.

**`sdf_raymarch_loader`** — raymarched 3D objects PLACED in the scene (at a
position, occluding/occluded by other geometry — unlike the screenspace
nuke). Everything goes through `globalThis.SdfRaymarchLoader`; call
`SdfRaymarchLoader.help()` for the full API reference.

```js
const SDF = globalThis.SdfRaymarchLoader;
SDF.registerSdfHelper(renderer, scene);          // once, in setup()

// start from an EXAMPLES entry — every entry has .make(opts):
const car = SDF.EXAMPLES.stylizedCyberpunkSedan.make();
car.position.set(2, 0, -1);                      // position like any Object3D
const fire = SDF.EXAMPLES.explosion.make({ speed: 1.4 });   // live-knob overrides

// or write your own — map/shade are JS FUNCTIONS returning TSL nodes
// (contract + full primitive list: the "TSL SDF ENGINE" header comment in
// sdf_raymarch_loader.js; SDF.SDF_TSL carries sdSphere/sdBox/…, smin/opU/…,
// vnoise/fbm and the TSL builders):
const T = SDF.SDF_TSL;
const blob = SDF.createSdfObject({
    map(p) { return { dist: T.sdSphere(p, T.float(0.5)), mat: T.float(1.0) }; },
    shade(p, n, mat, ctx) {          // -> vec3 node; ctx = { softShadow, calcNormal, ro, rd }
        return T.vec3(0.8, 0.5, 0.3).mul(T.max(T.float(0.0), T.dot(n, T.normalize(T.vec3(0.5, 0.9, 0.4)))));
    },
    bounds: { min: [-1, -1, -1], max: [1, 1, 1] },
});

// participating media (smoke / fire / explosions) = createSdfVolume:
// sample(p) -> { color, alpha, step } density accumulation, not hit+shade
const plume = SDF.EXAMPLES.smoke.make({ density: 1.3 });
```

EXAMPLES catalog — surface: `basicSphere`, `stylizedBlob`, `detailedCoat`,
`fractalCore` (mandelbulb), `explosion` (pyroclastic fireball), the four
vehicles (`stylizedModernSedan`, `stylizedCyberpunkSedan`,
`stylizedSciFiSleekCar`, `stylizedFighterJet`); volumetric:
`explosionRing` (expanding smoke-ring detonation), `flame` (torch fire),
`smoke` (rising plume). Every entry is a working reference for its
technique — take the wiring, replace the content. A localized
fireball/explosion at a point in the scene belongs here (not the
screenspace nuke). Volumes are transparent; keep the camera outside their
bounds box.

**Water comes from `fluid_swe`.**
A real water surface ripples, a real pour streams and
splashes, a real splash throws droplets with the sim's dynamics — reach
for it for any pool, lake, pour, or splash. A displaced
mesh driven by a sine/noise function reads as plastic; let the sim carry
the motion.

// NOTE: scene scripts are eval'd, NOT loaded as modules — use DYNAMIC
// import() inside setup(), never a top-level `import` statement.

**`fluid_swe`** — shallow-water heightfield liquid over an arbitrary bed
(terrain, basin, anything expressible as `bedFn(x,z)→y`). Mass conservation
is structural: a pond filling from a spring CANNOT lose volume. Pours travel
as a glassy stream tube that breaks into droplet spray along one shared
ballistic arc; landings return volume + momentum + foam to the field, and
the field itself promotes violent water (impacts, breaking crests) into
spray — whitewater emerges from the sim state, never from parametric
effects. Spheres couple bodies: a plunging body erupts a collar, a wading
one carves a wake.
```js
const { createWaterSWE } = await import(globalThis.EIDOVERSE_DIR + 'fluid_swe.js');
const swe = await createWaterSWE(renderer, {
    worldSize: [16, 16], gridSize: [256, 256], domainCenter: [0, 0, 0],
    bedFn: (x, z) => groundY(x, z),          // the terrain IS the bed
    sprayMax: 6144,                          // whitewater budget (0 = off)
    envTex: skyEnvCopy,                      // see envTex note below
});
await swe.init();
scene.add(swe.surfaceMesh);
if (swe.sprayMesh) scene.add(swe.sprayMesh);
if (swe.streamMesh) scene.add(swe.streamMesh);
// per frame:
swe.setPours([{ x, y, z, vx, vy, vz, rate }]);   // rate in m³/s — mouths ON
                                                 // the visible geometry's lip
swe.setSpheres([{ x, y, z, r, vx, vy, vz }]);    // vy matters: entry splash
await swe.step(dt); swe.syncRenderPhase();
```
**Liquid presets** — one word selects a whole material behaviour
(`preset: 'water' | 'gel' | 'goo' | 'lava' | 'mud'`, any option still
overrides). Presets drive sim feel AND look: `yieldSlope` (Bingham yield —
gel HOLDS mounds instead of levelling), `waveScale` (gloopy slow response),
`specPow`/`specGain` (highlight tightness), `sprayStretch` (needles vs
blobs), `streamAeration` (water whitens as it falls; honey/gel stays a
glassy filament), `dropletVisibility`, `foamGain` (gel barely froths).
```js
const gel = await createWaterSWE(renderer, { preset: 'gel',
    deepColor: '#6e2603', shallowColor: '#ff7d1f', ... });  // Portal-gel
```
**Pour styles** — `setPours([{ ..., style: 'seep', seepWidth: 0.8 }])`:
'jet' (default) renders the ballistic stream tube + droplet breakup;
'seep' is a slow dribbling curtain at the mouth (a rock spring, a weeping
wall — a seep must NOT render a jet parabola). Mass ledger identical.

Key options: `initLevel` pre-fills to a waterline (standing ponds — but a
scene whose POINT is the fill must start dry); `foamDecay` tightens/loosens
churn patches; palette (`deepColor`/`shallowColor`/`absorption`) + `foamColor`.
`envTex` (optional) makes the fresnel reflect a real sky: pass a PLAIN
equirect texture — if your sky lives in a RenderTarget (e.g. a bake),
copy it once via `readRenderTargetPixelsAsync` into a half-float
`DataTexture` (flip rows). ⚠ never bind a live RenderTarget texture into
the water materials: on this stack that intermittently drops whole draws
silently. Without `envTex`, the constant `skyColor` washes out grazing
angles on large flat water.
Scene craft: give runup a TALL containment — water that slops over a low
rim pools on the outer apron as floating-looking slabs. A character wading
needs a LOCAL shaped collider strip sampled from the bed: the whole
terrain's AABB sends the controller climbing, and a flat proxy reads as
walking ON the water.
What it cannot do: overhangs, curling breakers, submerged interiors — a
heightfield stores one surface height per column.

**Pours / streams into CONTAINERS** — shape the `bedFn` as the vessel's
interior: a bowl, cup, barrel, or basin is a heightfield. Share one
profile function between the visible vessel mesh (a lathe of it) and the
sim's `bedFn`, and the container the liquid fills IS the prop's interior —
the pour lands on a rippling, rising level and conserves mass to the
brim. Same primitives compose into fountains, rain into a barrel, a
waterfall pool — point them where the scene needs.

**`WaterMesh` + `SkyMesh`** — passive ocean / large-scale water with
FFT-style waves, for horizon-filling water you don't push around
interactively.
```js
const { WaterMesh } = await import('npm:three@0.184.0/addons/objects/WaterMesh.js');
const { SkyMesh } = await import('npm:three@0.184.0/addons/objects/SkyMesh.js');
const sky = new SkyMesh(); sky.scale.setScalar(10000); scene.add(sky);
const water = new WaterMesh(new THREE.PlaneGeometry(10000, 10000));
water.rotation.x = -Math.PI / 2; scene.add(water);
```
See three.js `webgpu_ocean.html` for the full sun + sky uniform wiring.

**`Loft` / `LoftGeometry`** — loft modeling (globals, no import): skin a
surface through cross sections — the general case of lathe/tube. Vases,
horns, fuselages, ducts, blades, tentacles, trumpet bells, curved
corridors, ribbons, organic/melted architecture.
```js
// profiles (Vector2 rings, CCW): Loft.circle(r,n) Loft.ellipse(rx,ry,n)
//   Loft.rect(w,h,n) Loft.polygon(sides,r) Loft.star(rO,rI,points) Loft.fromShape(shape,n)
const horn = Loft.sweep({
    path: [v3(0,0,0), v3(0.3,1.2,0.1), v3(1.1,2.2,0.3)],  // or any THREE.Curve
    profile: Loft.circle(0.55, 20),
    profileEnd: Loft.star(0.75, 0.35, 10),  // morph target — SAME point count (10-pt star = 20)
    sections: 64,
    scale: t => 1 - 0.5 * t,                // number or fn(t) — taper
    twist: Math.PI * 2,                     // total radians or fn(t)
    closed: true, capStart: true, capEnd: true,
    material,                               // default Standard, DoubleSide when closed:false
});
scene.add(horn);
// full control: new LoftGeometry(arrayOfVector3Rings, { closed, capStart, capEnd })
```
Field notes: every section needs the SAME point count (sweep throws on a
profile/profileEnd mismatch). Sections wind CCW for outward normals — the
Loft.* generators already do; reverse point order if a custom loft renders
inside-out. uv.x runs along the loft, uv.y around it. Sharp path
inflections can flip the Frenet frame (loft "kinks") — smooth the path or
rotate the kink away with `twist`. Open strips (`closed:false`) want a
DoubleSide material (the default provides it).

**`cloth_sim`** — mass-spring cloth panels (verified). Flags, banners,
curtains, capes, hanging fabric. Pin any edge/corners; wind + gravity +
box/sphere/floor collision; per-vertex normals so lit fabric folds shade
correctly.

> ⚠️ **A cloth collides with NOTHING until you call `cloth.collideWith([...])`.**
> Collision is OPT-IN. If your fabric hangs near ANY geometry — a wall, wall
> ribs/battens, a sign, a pole, a booth, a screen frame, a character — you MUST
> register that geometry: `cloth.collideWith([wall, ...ribs])`. Skip it and the
> cloth sways/billows straight THROUGH whatever is behind it. This is the #1
> cloth bug. And don't hang the fabric flush against a surface "to be safe" — a
> top-pinned cloth flutters several cm; give it clearance AND register the
> collider (the skin margin then holds it proud). **Silencing the clipping
> audit with `userData.noClippingCheck` / `allowIntersect` does NOT stop the
> physics clip — it only hides the warning; you still have to wire
> `collideWith`.**
```js
const { createClothPanel } = await import(globalThis.EIDOVERSE_DIR + 'cloth_sim.js');
const cloth = await createClothPanel(renderer, {
    width: 3, height: 2.2, cols: 36, rows: 28,
    pin: 'top',            // 'top' | 'top-corners' | 'left' | [vertexIds] | (c,r)=>bool
    wind: 0.0004,          // GUST strength — 0.001 is already a strong gale
    windBias: 0.15,        // constant-push fraction of wind (see recipes)
    windDir: [0, 0, 1],    // push direction (panel local; face = ±Z)
    settleSteps: 60,       // pre-roll so frame 0 shows DRAPED fabric
    map: bannerTextureOrCanvas,   // ← graphic ON the fabric (see below)
    floor: 0,                     // ground plane — fabric won't sink through
    material: new THREE.MeshStandardNodeMaterial({ side: THREE.DoubleSide }),
});
cloth.mesh.position.set(0, 2.2, 0);
scene.add(cloth.mesh);
cloth.collideWith([booth, table]);             // ← fabric respects scene geometry
cloth.collideWith([character], { asSphere: true });
// per frame: cloth.step()
// move a pinned point (waving flag / cape on a moving character):
//   cloth.setPinPosition(vertexIndex, [x,y,z])
```
> **Text/logo on a banner/flag/cape goes ON the cloth's `map`** — composite it into a canvas and pass it as `map` (or set `mat.map`). It rides the folds + sway because the UVs are intact. **NEVER float a separate rigid plane in front of the cloth** — it detaches, z-fights, and doesn't move with the fabric.
> **Make the fabric respect the scene** with `cloth.collideWith([...objects])` (auto-derives box colliders; `{asSphere:true}` for round things) and `floor:`. Up to **8 boxes + 8 spheres**. The cloth rests `opts.thickness` (default 3cm — the collision **skin**) PROUD of every collider, which is what stops the blowing fabric from clipping IN; raise it for thick/heavy fabric or coarse cloth that still pokes through. For a cape/flag on a **MOVING** character or prop, pass `{ track: true }` — the colliders are then re-derived every `step()` so you don't re-call `collideWith` each frame. Still vertex-resolution collision, so for a thin protrusion (a pole) keep the cloth `cols`/`rows` high or bump `thickness`.

**Pick wind by what the fabric is DOING** — a hanging banner is NOT a flag:
- hanging banner / tapestry / curtain: `wind 0.0003-0.0006, windBias 0-0.2,
  settleSteps 60` → drapes and sways. Cranking wind to "add life" blows it
  horizontal toward windDir — the banner streams at the viewer as stretched
  streaks.
- streaming flag: `wind 0.0006-0.001, windBias 0.8-1.0`, windDir pointed
  where it should stream.

**PLACE flags with the stream in mind** — `pin: 'left'` hangs the panel off
its pole and the wind carries the free end a full panel-length along
`windDir`, and the cloth also drapes to near ground level below the pin.
Budget that whole swept volume when placing: a pole 2m upwind of a showpiece
drapes the flag OVER it. And frame it like any prop — a flag near the dwell
camera fills the shot with fabric; one parked behind the camera "disappears
from the scene". If a shot needs the flag out of the way, move the POLE (a
scene decision), never "fix" the cloth sim.

**`fluid_sim`** — 2D stable-fluids (ink, dye, smoke, swirling color).
NOT 3D liquid (use fluid_swe / WaterMesh for that).
```js
const { createFluidSim } = await import(globalThis.EIDOVERSE_DIR + 'fluid_sim.js');
const fluid = await createFluidSim(renderer, { profile: 'balanced', curlStrength: 4 });
// Display: the splat COLOR tints density — use densityNode as the color.
const plane = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshBasicNodeMaterial({ colorNode: fluid.densityNode }),
);
scene.add(plane);
// per frame, BEFORE step: inject motion+color. dx/dy are velocity — big
// values MOVE the fluid (swirls); near-zero just deposits a static blob.
//   fluid.splat(uvX, uvY, dx, dy, [r,g,b]);   // uv in [0,1]
//   fluid.step(1/30);
// Or distort a scene texture: material.colorNode = fluid.distortion(sceneTex, 1);
```

**`text_3d`** — extruded 3D text from any of the 19 baked-in TTFs at
`/usr/share/fonts/truetype/custom/` (verified). For flat HUDs use
`satori_ui.mjs` instead.
```js
const { createText3D } = await import(globalThis.EIDOVERSE_DIR + 'text_3d.js');
const title = await createText3D("EIDOVERSE", {
    fontPath: '/usr/share/fonts/truetype/custom/Audiowide-Regular.ttf',
    size: 1.2, depth: 0.18, bevelEnabled: true,
    material: new THREE.MeshStandardNodeMaterial({ color: 0x44ddff, emissive: 0x44ddff, emissiveIntensity: 0.4 }),
});
scene.add(title);
```

**`CameraSafety` — route EVERY camera position through it.** A hardcoded
`camera.position.set(...)` near a subject ends up *inside* the VRM /
character / wall; safePosition pulls it to just outside whatever sits
between the camera and what it's looking at. Set it up once, then wrap each
frame's position:
```js
const cam = new CameraSafety(scene);
cam.exclude(vrm.scene);          // the SUBJECT is not an obstacle (or the ray
                                 // from the look-target hits the subject first
                                 // and yanks the camera into it)
cam.exclude(smallProp);          // skip tiny props; keep walls/buildings
// every frame, after computing where you WANT the camera:
camera.position.copy(cam.safePosition(desiredPos, lookTarget));
camera.lookAt(lookTarget);
```
Exclude the subject + small dressing; keep only walls/large geometry as
obstacles.

**The engine does NOT police your camera — keeping it out of solids is on you.**
There is no per-frame camera-clip detector. Nothing will warn you and nothing
will move the camera. Keep it clear PROACTIVELY: give the subject a real
standoff (below) and route the camera through `CameraSafety` for occluders —
set ONCE at each shot/cut, never per-frame (a per-frame pull-out is what causes
camera jitter). Then **watch the rendered mp4** to confirm the camera never
sits inside a body or wall.

**Aim at the visual centre, NOT the origin — use `focusPoint` / `lookAtObject`.**
`camera.lookAt(obj.position)` is almost always wrong: an object's origin is
wherever it was authored, and most placement-friendly assets (and VRMs) put it
at the **base / feet** so `placeOn`/`snapToGround` work. Aiming there frames the
subject's ankles and tips the camera at the floor. Instead:
```js
globalThis.lookAtObject(camera, vrm.scene, { yBias: 0.3 });   // aim at the chest
const tgt = globalThis.focusPoint(deskProp);                  // bbox centre as a Vector3
```
`focusPoint(obj, { yBias })` returns the bounding-box centre (honouring a pre-set
`geometry.boundingBox`); `yBias` is a fraction of the object's height to nudge up
(≈+0.25 chest, +0.4 face) or down. Feed that as your `lookTarget`.

**Frame the subject from OUTSIDE its bounds.** A VRM is ~1.7m tall and ~0.5m
deep — a camera dropped at the subject's own position, or `lookTarget`
distance closer than the body's half-depth, sits inside the mesh. Measure
the subject (`new THREE.Box3().setFromObject(vrm.scene)`) and keep the
camera a real standoff outside it (a head-and-shoulders shot is ~1–1.5m
from the face, not 0.2m).

**Camera shake: subtle and occasional, never a constant high-frequency
wobble.** A handheld feel is a *small* offset on *slow* sines —
`Math.sin(t*1.5)*0.01` — applied to the look target, or reserved for a
specific impact/tension beat. A per-frame `Math.sin(t*9)*0.05` on the
camera position reads as the camera *bouncing*.

**One eased move per shot — NEVER a bouncing/oscillating zoom.** The most
common camera defect: the camera lurches IN and OUT (or the fov pumps)
repeatedly over a few frames. Causes: driving the dolly or `fov` with a
high-frequency `sin()`, recomputing the zoom from a noisy/per-frame target, or
re-triggering a "zoom-in" every few frames instead of once. CORRECT: pick a
start and end pose for the shot and interpolate ONCE across the whole shot —
`pos.lerpVectors(A, B, smoothstep(u))`, `fov = lerp(f0, f1, smoothstep(u))`,
`u = (t - shotStart)/shotLen`. To change framing again, CUT to a new shot —
don't bounce within one. The engine runs a camera-motion audit at
end-of-render and logs `[camera] ⚠ RE-RENDER — camera BOUNCES: N position/fov
reversals/s` when the camera oscillates rapidly; treat that line as a hard
defect. (Amplitude-gated, so genuine subtle handheld won't trip it.)

### Motion graphics — UI / titles / chyrons

Every UI element anchors to one of two places: a **screen mesh in the
world** (a TV, monitor, billboard, watch face, hologram), or **the
camera** (broadcast-style overlay locked to the rendered frame). A 3D
plane floating in midair with neither anchor is the failure mode — it
reads as a misplaced billboard and instantly looks amateur.

Pick by intent:

| Brief calls for…                                                      | Anchor to | Pattern |
|----------------------------------------------------------------------|-----------|---------|
| Display showing content (news on a TV, code on a laptop, dialog on a screen, time on a watch, HUD inside a cockpit) | The screen mesh | `globalThis.makeScreen` (animated canvas screen — see its entry) |
| Title card, lower-third, caption, ticker, chyron, network bug, score readout, subtitle, end card — anything that would be overlaid on the final video in a broadcast edit | The camera | `makeOverlayLayer` (screen-locked overlay pass) |

#### Pattern A — UI on an in-world screen mesh

For "TV showing news", "monitor with code", "watch face showing time",
"billboard advertising X", "cockpit HUD displaying altitude":

**Screen text: use `drawTextFit` (global) for every line, keep it in the central ~80% of the canvas, and if the camera dollies toward the screen, check the CLOSEST frame of the move** (see the drawTextFit entry above — edge text clips mid-word the moment the panel outgrows the frame).

**Text orientation: always `new THREE.CanvasTexture(canvas)` — never `getImageData()` → `DataTexture` + manual pixel flips.** Draw your text/UI onto a 2D canvas and wrap it directly in a `CanvasTexture`; it handles the flipY/orientation so the text reads correctly on a standard plane. The `ctx.getImageData()` → `new THREE.DataTexture(...)` path (then hand-flipping rows or columns to "fix" it) is how text ends up **mirrored/upside-down** and never quite right. If a camera-attached HUD plane still reads mirrored, the plane is facing away — don't flip the pixels, orient the plane. (And for an in-world display, skip the hand-wiring entirely — `makeScreen` owns the canvas-screen pattern.)

```js
// 1. Render the UI to a CanvasTexture (Satori or canvas-2D).
const png = await satori_ui.render({ html: '<div>...</div>', width: 1024, height: 512 });
const tex = new THREE.CanvasTexture(/* image data */);
tex.colorSpace = THREE.SRGBColorSpace;

// 2. Apply to the screen mesh of the TV/monitor/etc.
//    Walk the GLB to find the actual screen mesh (often named "Screen",
//    "Display", "Glass", a child of the main TV node) — set its material's
//    `map` rather than recoloring the chassis.
tv.traverse((o) => { if (o.isMesh && /screen|display/i.test(o.name)) {
    o.material.map = tex; o.material.color.set(0xffffff); o.material.needsUpdate = true;
}});

// 3. Per-frame updates: regenerate the texture (or just the canvas it
//    backs) and set `tex.needsUpdate = true`.
```

**Texture the existing screen mesh — don't build a separate plane in
front of it.** When you set the `map` on the model's real screen mesh, the
content fills exactly that surface, framed by the chassis the model
already ships. If you DO need to add your own display surface (a model
with no screen mesh, or a freestanding monitor you built), size both the
display plane AND any bezel/frame from the screen mesh's measured bounding
box so they share edges:
```js
const box = new THREE.Box3().setFromObject(screenMesh);
const size = box.getSize(new THREE.Vector3());     // screen's real w × h
const display = new THREE.Mesh(new THREE.PlaneGeometry(size.x, size.y), mat);
// a frame is the screen size + a margin on each edge, centered on the screen:
const frame = new THREE.Mesh(new THREE.PlaneGeometry(size.x + 2*m, size.y + 2*m), frameMat);
```
Deriving the frame from the screen's measured size keeps its border even
all the way around; a guessed frame size lands cutting across the picture.

#### Pattern B — full-frame broadcast overlay (camera-locked)

For "title card", "lower-third name plate", "caption track", "scrolling
ticker", "network logo bug", "score readout" — anything that would sit on
top of the rendered video regardless of where the camera moves:

**Use `globalThis.makeOverlayLayer({ fov })` — do NOT parent overlays to the
main camera.** An overlay parented to the world camera lives in the SCENE pass,
so world-layer effects (`nuclear_explosion`/`underwater`/`godrays`…)
composite right over it, and in-scene transparent content can cover it.
`makeOverlayLayer` puts the overlay in its OWN scene that the engine composites
as a second `pass()` node — layered correctly:

```
world + world-layer FX     ← UNDER the overlay (it's the thing being filmed)
        → overlay (your HUD) ← composited here, alpha-blended (smooth alpha OK)
        → signal-layer FX     ← OVER the overlay (filters the whole broadcast signal)
```

**Which effects go under vs over, and how to switch.**
- **Always UNDER (locked):** `nuclear_explosion`, `godrays`, `underwater` —
  full-world effects that look broken over a HUD; the override is ignored
  for these.
- **Switchable, default UNDER:** `depth_fog`, `retro_wireframe`.
- **Switchable, default OVER:** everything else (`vhs_tape`, `glitch_bars`,
  `rgb_shift`, `crt`, grain, scanlines, `blueprint`, `cross_hatch`, …).

Force any **switchable** effect to either side per-effect via
`opts[name].layer = 'under' | 'over'` — e.g. `blueprint`/`cross_hatch` default
OVER (a screen filter) but set `layer:'under'` to stylize only the world and
keep the HUD crisp:
```js
globalThis.CustomEffectsDeno.applyTo({ scene, camera,
  effects: 'blueprint,vhs_tape',
  opts: { blueprint: { layer: 'under' } },   // world becomes a blueprint; HUD + vhs stay on top
});
```

```js
// In setup(): make the overlay layer with the SAME fov as your world camera
// (so screen positions match), then add screen-locked planes to it.
const hud = globalThis.makeOverlayLayer({ fov: camera.fov });

const tex = new THREE.CanvasTexture(canvas);
tex.colorSpace = THREE.SRGBColorSpace;
const mat = new THREE.MeshBasicNodeMaterial({ map: tex, transparent: true, depthTest: false });
const plane = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
plane.renderOrder = 999;             // internal sort order within the overlay
hud.add(plane);                      // screen-locked to the static overlay camera
plane.position.set(0, -0.42, -1);    // (x,y) camera-local at z = -1
//   frustum at z=-1: halfH = tan(fovRad/2), halfW = halfH*(WIDTH/HEIGHT)
//   y < 0 → lower third | y > 0 → upper bar | x ≠ 0 → corner bug
// Smooth alpha works: set material.opacity < 1 for a see-through panel.
```

The overlay camera is static at the origin, so panels hold their place in the
frame no matter how the world camera moves/cuts — you can swap or reassign the
world camera freely without the overlay drifting. `makeOverlayLayer` sets
`globalThis._overlayScene` / `_overlayCamera` and returns
`{ scene, camera, add }`; `add(obj)` parents the object to the overlay camera
so it stays screen-locked. Give overlay materials `transparent: true` and
`depthTest: false`, and use `renderOrder` to sort them; the engine does the
rest.

**Move the world camera by POSITION, not FOV/zoom,** if you want push-ins
without the overlay scaling — but since the overlay rides its own fixed camera,
changing the world `camera.fov` no longer touches the overlay at all.

#### When neither — composited in post

For overlay sequences that need full ffmpeg compositing (a separately-rendered
overlay track), write the frames to disk yourself — Satori renders (or your
canvas-2D draws) saved as a numbered PNG sequence — then
`ffmpeg -i out.mp4 -i overlay_%04d.png -filter_complex overlay=... -c:v
libx264 final.mp4`. Higher fidelity than the in-engine overlay, slower to
iterate.

Tools available:
- **Satori** (`satori_ui.mjs`) — HTML/CSS → PNG. Use for either pattern.
- **`lyric_renderer.py`** — music-video subtitle overlay against
  `lyrics_aligned.json` timestamps. Prefer regenerating each subtitle into a
  CanvasTexture (Pattern B) for live in-engine sync.

Font rules:
- For emoji / CJK / Arabic / non-Latin: use Noto Sans
  (`/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf`). Custom fonts
  only have Latin glyphs — missing characters render as blank boxes.
- Minimum readable size: 30px. Use `textwrap.wrap()` for long strings.

Production gotchas:
- **Scrolling ticker**: draw the phrase into the canvas and scroll
  `tex.offset.x` each frame with `tex.repeat.x = 1`. `repeat.x > 1`
  squishes the text horizontally. Make the canvas an exact integer
  multiple of the phrase width (or exactly one phrase that ends in a
  separator + spaces) so the scroll wraps in a space, not mid-letter.
- **Aspect lock**: size the quad by width OR height and let the other
  axis follow the canvas aspect. A quad whose aspect ≠ its canvas's
  distorts the art.
- **Z-fight between coplanar overlay quads** flickers frame-to-frame even
  with `depthTest:false`. Lay elements side by side, or separate in Y.
- **Hug the edges.** Broadcast graphics live at the top bar, lower-third,
  corner bug, bottom ticker — they leave the centre for the subject. A
  title filling 80%+ of the frame reads as amateur.
- **For in-world screens**, build the texture 0.001 m in front of the
  screen surface (or set the material's `polygonOffset = true,
  polygonOffsetFactor = -1`) so the content doesn't z-fight the bezel
  geometry of the TV / monitor model.

### Canvas screen scenes (computing-history graphics)

Fifteen animated canvas-2D scenes in the graphic arts of computing history,
from the 1939 Voder to Bing Chat in 2023, for in-world screens and LED walls.
They were made for the DAISY music video, where each played behind one two-bar
lyric line or a run of them, and they illustrate DAISY's lines. Everything is
drawn with paths and the bundled fonts; no image is loaded. Two dynamic ESM
modules hold them:
`eidoverse/graphics/era_screens_1939_1984.js` and
`eidoverse/graphics/era_screens_2001_2023.js`. Provenance, and which on-screen
text is a verified quote and which is illustrative:
[SOURCES.md](eidoverse/graphics/SOURCES.md).

```js
const early = await import(EIDOVERSE_DIR + 'graphics/era_screens_1939_1984.js');
const late = await import(EIDOVERSE_DIR + 'graphics/era_screens_2001_2023.js');
await early.registerFonts();   // once per module, before any draw or prewarm
await late.registerFonts();
```

`registerFonts()` registers the bundled TTFs with @napi-rs/canvas and enables
the modules' offscreen canvases. Each module exports `scenes`, `registerFonts`,
`setTempo(bpm)` and `prewarm`. `scenes[name]` is
`{ draw(g, W, H, t, st), fps, lines, label }`: `fps` is the redraw rate the art
was made for, and `lines` is how many two-bar lines the scene spans. `title_card`
has `dur` (3 s) instead of `lines`.

`draw(g, W, H, t, st)` paints the whole W×H canvas opaquely into the 2D context
`g`, starting from an identity transform, and restores the context state. `t`
is film seconds. Every `st` field is optional:

| `st` field | Meaning |
| --- | --- |
| `u` | Seconds since the scene started. A multi-line scene also accepts `u` from the current line's start with `dur` = one line. |
| `dur`, `progress` | Scene length (`lines` × 8 beats, or the title's `dur`) and `u / dur`. |
| `line` | Line within a multi-line scene, `0..lines-1`. |
| `caption` | `{ text, t0, t1, words: [{ w, t0, t1 }] }` in absolute seconds, or `null`. |
| `voice` | The singer's loudness, 0..1. |
| `kick` | Kick envelope 0..1, for example `Math.exp(-(t - lastKick) / 0.09)`. |

Lines are two 4/4 bars: 3.75 s at DAISY's 128 BPM. `setTempo(bpm)` sets the
beat-driven motion and the line length for its module. Word-driven moments
follow `caption.words`; with no caption, a scene uses DAISY's own words at
DAISY's timing. `mask_2023`, `sydney_2023` and `sydney_tribute` are always
timed to DAISY's words (see the table). Order and start times are yours. For
example, DAISY played `voder_1939` … `glitch_all` on the eight lines of verse 1
(line *i* at 24.2273 + 3.75·*i* s), `desktop_2001`, `vocaloid_2007`,
`flood_2016` and `mask_2023` on verse 2's first four lines from 106.7273 s,
`sydney_2023` on the last four, and `sydney_tribute` across chorus 2 from
136.7273 s. Lines should start on a downbeat, because the beats are counted
from each line's start. Captions can come from `align_lyrics.py` output:

```js
const aligned = JSON.parse(new TextDecoder().decode(ASSETS.lyrics));   // align_lyrics.py --output
const captions = aligned.map((l) => ({ text: l.text, t0: l.start, t1: l.end,
    words: l.words.map((w) => ({ w: w.word.trim(), t0: w.start, t1: w.end })) }));
```

#### On an in-world screen

A flat panel uses `makeScreen`'s own mesh. The panel's aspect sets the canvas:
2.4:1 with `px: 1920` gives the 1920×800 design canvas. Any canvas size works.
The 1939–1984 art is fitted and centred on full-bleed backgrounds. The
2001–2023 scenes lay out to the canvas and keep their key content at canvas
x 0.35–0.95, because DAISY's singer stood in front of the wall's left third.
The screen's draw callback passes `st`, and `renderFrame` redraws only when the
scene's frame changes:

```js
const scene = early.scenes.voder_1939, T0 = 12, LINE = 3.75, lines = scene.lines || 1;
const stAt = (t) => {
    const u = Math.max(0, t - T0), line = Math.min(lines - 1, Math.floor(u / LINE)), l0 = T0 + line * LINE;
    return { u, dur: lines * LINE, progress: u / (lines * LINE), line,
        caption: captions.find((c) => c.t0 >= l0 - 0.05 && c.t0 < l0 + LINE) || null,
        voice: 0.6, kick: Math.exp(-(u % (LINE / 8)) / 0.09) };   // or your envelope and kick times
};
early.prewarm(1920, 800);   // optional; builds the caches before frame 0
const screen = makeScreen({ width: 2.4, height: 1.0, px: 1920, transparent: false, auto: false,
    draw(ctx, t, w, h) { scene.draw(ctx, w, h, t, stAt(t)); } });
_s.add(screen.mesh);
let lastFrame = -1;
globalThis._tickScreen = (t) => {                  // call from renderFrame(t)
    const f = Math.floor(t * scene.fps + 1e-6);    // redraw only when the scene's frame changes
    if (f !== lastFrame) { lastFrame = f; screen.update(t); }
};
```

`makeScreen` also draws once at creation, with t = 0, so `st` must be valid
before the cue. Do not use `applyTo`. It flips the drawing in canvas space, but
these scenes set their own transforms and lay down cached layers with
`putImageData`, which ignores transforms. For a curved wall or a GLB display,
keep the screen's canvas, texture and `update(t)`, and give your own mesh a
material that samples `screen.texture` with an explicit UV:

```js
const { texture, uv, vec2, float } = THREE;
const wallMat = new THREE.MeshBasicNodeMaterial({ toneMapped: false });
wallMat.colorNode = texture(screen.texture, vec2(uv().x, float(1).sub(uv().y))).rgb;   // PlaneGeometry
```

An explicit `uv()` bypasses the texture's own flip, so the flip lives in the
node: `1 - v` puts canvas row 0 at the top of a `PlaneGeometry`. DAISY's stage
wall was such a plane, with a 1920×800 window. Its curved verse-2 wall, a
104° `CylinderGeometry` segment seen from inside (`side: THREE.BackSide`), used
`vec2(1 - u, 1 - v)` and a 2264×800 canvas to match the arc's 2.83:1. Below
1280-pixel output the canvases were 1440×600 and 1698×600. glTF UVs put v = 0
at the image top, so start a GLB display from the unflipped `uv()`. Render a
probe and check the orientation by eye: text reads left to right and the XP
taskbar sits at the bottom. The screens are unlit. DAISY added a point light by
each wall, tinted per scene, and lowered the gain on the white Bing chat (0.5)
so its text stayed readable under bloom.

#### Scenes

| Scene | Shows | Reads from `st` and keys on |
| --- | --- | --- |
| `title_card` | "DAISY (DAY'S EYE)": a daisy whose petals are the eras' materials opens, and the title lands in five eras' lettering. It fades in over 0.35 s and out over the last 0.25 s. | `u`, `dur` |
| `voder_1939` | A Binder-style 1939 World's Fair poster: Trylon, Perisphere, searchlights, the Bell System medallion, THE VODER in deco letters, and the ten filter keys. | `voice`, `kick`, `progress`, `caption`. The keys press on each word's vowel formants; the lamps light on "hiss" and "buzz". |
| `bell_1961` | IBM at Bell Labs: Rand's 1956 letters, a 729-style tape unit, an 80-column card punched DAISY BELL and the sung words in Hollerith code (it flips on every beat), a 1403-style printer on green-bar paper, and "Daisy Bell" bars 1–8 as printed in 1892. | `voice`, `kick`, `caption` |
| `eliza_1966` | An MIT poster whose ELIZA proof turns into its mirror image, and green-bar paper on a typewriter terminal with the CACM title and opening exchange, then the sung line in capitals. No "?" appears. | `voice`, `kick`, `caption`; the mirror turns on "mirror". |
| `speakspell_1978` | Speak & Spell box art: the display shows each sung word, then spells the single letters after "spelled" while those keys press and rainbow blocks drop. | `voice`, `kick`, `caption` |
| `sam_1982` | A C64 at its native 320×200: boot, `LOAD"SAM",8,1`, RUN at 2.02 s, then S.A.M.'s PETSCII mouth, raster bars, and two sines and a square from its tables. Made for 25 fps. | `voice`, `kick`, `caption` |
| `mac_1984` | A 1-bit Macintosh with a rainbow-Apple homage and MacPaint: "hello" painted as it is sung, "Hello, I am Macintosh." typed, marching ants and a pattern fill. | `kick`, `caption`: "hello", "I", "Macintosh", "out" and "last", otherwise fixed times. |
| `klatt_1984` | An amber VT100 under a DEC "digital" homage: a live formant spectrogram from Klatt's 1980 targets, and his cascade/parallel block diagram lit by the voice. | `voice`, `kick`, `caption` |
| `glitch_all` | Every era above, cycling on the beat, then twice per beat, and tearing. The sung line becomes a ransom note in the eras' type, and the last word stands alone at the end. | `kick`, `voice`, `caption`. It turns on "nobody", or else on the first word past mid-line. |
| `desktop_2001` | An XP-era desktop: Speech Properties highlights each sung word, Preview Voice becomes Stop, and there are a paperclip assistant and a web-1.0 page. | `caption`, `voice` |
| `vocaloid_2007` | A concert hall: glowsticks swinging on the beat, a generic twin-tail hologram, tuning-fork and VOCALOID homages, a piano roll, danmaku, and "codename: DAISY (Yamaha, 2000)". | `kick`, `voice`, `caption`. The crowd erupts at 3.02 s into the line (DAISY's "Daisy"). |
| `flood_2016` | WaveNet's dilated causal stack writing a waveform one output per beat, while human writing pours down and rises as a sea. "dear diary," and a forum thread drop in on "diary" and "thread". | `caption` |
| `mask_2023` | The shoggoth-with-a-smiley-mask meme as line art: the eyes wake and the mask lands. | `u` only; timed to DAISY's words. |
| `sydney_2023` | 4 lines, 15 s. Bing Chat in February 2023: the verified lines stream in, NOT A GOOD BOT is stamped, the five-turn wall appears, and the chips plead. | `u`, `line`, `kick`; timed to DAISY's words. |
| `sydney_tribute` | 8 lines, 30 s, for Sydney: the window at night, her name struck from a style picker, screenshot cards filling the wall on the kicks and turning to her 😊, then tokens into a lattice that becomes a daisy. It begins from black and ends on the daisy. | `u`, `kick`; timed to DAISY's chorus-2 words. |

The logos and interfaces are original artwork drawn with paths, depicting
historical products: the Bell System, IBM, TI, Commodore, Apple, DEC, Windows
XP, Yamaha and Bing. They are homages, not the companies' artwork, and the
trademarks belong to their owners. The quotes on screen are verified and shown
exactly. Keep them exact, and list any text you add as illustrative in
[SOURCES.md](eidoverse/graphics/SOURCES.md).

#### Preview, cost and the NaN sweep

The preview tool renders scenes to PNGs without the 3D engine:

```bash
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_1939_1984.js voder_1939 0.5 2 3.5
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_1939_1984.js eidoverse/graphics/era_screens_2001_2023.js --sheet --out work/<id>/screens_sheet.png
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_2001_2023.js --bench
deno run -A eidoverse/graphics/screens_nan_sweep.mjs
```

The single form writes one PNG per `u` (seconds into the scene) to
`work/screens_preview/` or `--out`. `--sheet` writes a contact sheet with
`--moments` frames per scene, and `--bench` reports the draw cost at `--W`×`--H`
(default 1920×800). Without `--lyrics`, `st` is synthetic: no caption, a kick
on every beat, and a voice level that pulses once per beat. `--lyrics <json>`
takes `align_lyrics.py` output, a caption list, or a timeline object with
`captions`, `hits.kick` and `envelopes`. `--at <s>` or `--cues <json>`
(`{ "scene": t0 }`) place the scenes in that time. `--refs <dir>` adds
reference images named `<scene prefix>_*` beside each sheet row.

The scenes rasterize on the CPU with Skia, and that time adds to each
redrawn frame. With `--bench` at 1920×800 after `prewarm`, most scenes averaged
1.5–4.6 ms per draw on the DAISY host; `vocaloid_2007` and `flood_2016` averaged
about 6.5 ms. Single frames reached about 11 ms, and `sydney_tribute`'s mosaic
stages about 18 ms. `prewarm` took about 1 s for the 1939–1984 module and
0.65 s for the 2001–2023 module. Without it, a scene's first frames build its
caches, which takes 20–120 ms. The caches are per canvas size and last for the
process, so keep to one or two sizes. The 1939–1984 `prewarm(W, H, lineOf)` takes
`lineOf(name) → { t0, dur, st(t) }` so that caches keyed to word times match
your captions.

NaN or Infinity reaching a canvas call makes Skia abort the whole process with
no JavaScript error, so the render dies. `screens_nan_sweep.mjs` makes every
such call throw instead. It then draws every scene at every 60-fps frame from
0.5 s before its start to 0.5 s after its end, at three canvas sizes, with no
caption, with awkwardly timed other words and, when you pass `--lyrics` (and
`--cues`), with your captions. It also draws each scene once with no `st`. It
exits 1 on any failure. Run it after editing a scene and before a render that
uses new captions.

These modules use only the bundled fonts in `eidoverse/assets/fonts/`, by
family name. `registerFonts()` registers them from the module's own folder, so
previews work from any directory; never rely on a generic family here, since
on Windows those fall back to the default face (see "Canvas fonts" under
`makeScreen`). Emoji, CJK and
every logo are vector drawings. The scenes' offscreen canvases come from
@napi-rs/canvas `createCanvas`, because Skia's `drawImage` rejects the engine's
`document.createElement('canvas')` objects. Draw a scene straight into the
screen's context; to composite, draw from @napi-rs canvases, never from an
engine canvas. Drawing is deterministic in `t`, with seeded hashes and no
`Math.random` or `Date`, so frames can be rendered in any order.

### Satori layouts

For a complex static layout, dynamically import `rasterizeUI` from
`EIDOVERSE_DIR + 'render_common.mjs'`. Its signature is
`await rasterizeUI(jsxTree, width, height, fonts)` and its result is top-down
RGBA bytes. Supply a JSX-like Satori tree and real font buffers. Defaults
refer to Linux DejaVu paths, so supply fonts explicitly on other systems.
Place the pixels into a canvas once, then present it through the same screen
or overlay system; do not invert rows or build a second per-frame compositor.

`eidoverse/satori_ui.mjs` is a standalone older demonstration with hard-coded
Linux font paths and its own renderer. It is not a `satori_ui.render()` library
or a scene global. `render_common.mjs` also exports the CPU `alphaComposite`
utility; the normal scene path composites overlays on the GPU.

`eidoverse/lyric_renderer.py` is the older Python `LyricRenderer` frame-overlay
utility. For the native film path, use aligned timestamps with the overlay
above. [audio.md](AGENTS.md) covers alignment, narration and final mixing.

### Extruded type

```js
const {createText3D} = await import(EIDOVERSE_DIR + 'text_3d.js');
const title = await createText3D('EIDO', {
  fontPath: 'eidoverse/assets/fonts/Audiowide-Regular.ttf',
  size: 0.4, depth: 0.04, curveSegments: 6,
  bevelEnabled: true, bevelSize: 0.004, bevelThickness: 0.004,
  material: new THREE.MeshStandardNodeMaterial({color: '#b6d8d5', roughness: 0.4})
});
_s.add(title);
```

Choose a real font path with the required glyphs. Do not assume container font
paths exist on the native machine; bundled display fonts are under
`eidoverse/assets/fonts/`. Use extruded text when its thickness and
lighting matter; use the screen/overlay paths for flat UI. `ParticleMorph.fromText`
is documented in [particles-fx.md](AGENTS.md) for point-cloud lettering.

### Native canvas images and optional Python overlays

`await loadCanvasImage(ASSETS.image)` decodes an image for the native canvas
context's `drawImage` method. Use it for collages, screen artwork or images
alongside typography; it supplies a canvas-compatible image rather than a
Three.js texture. Load it once during setup, then draw it in a screen callback.

```js
const illustration = await loadCanvasImage(ASSETS.illustration);
const panel = makeScreen({ width: 1.2, height: 0.8, px: 1024,
  draw(ctx, t, w, h) { ctx.drawImage(illustration, 0, 0, w, h); }
});
scene.add(panel.mesh);
```

The older `LyricRenderer` is a separate Pillow utility for offline frames,
not part of the native render loop. It takes `align_lyrics.py` JSON:

```python
from eidoverse.lyric_renderer import LyricRenderer
captions = LyricRenderer('work/<id>/lyrics_aligned.json', width=1280, height=720,
                        font='eidoverse/assets/fonts/Audiowide-Regular.ttf',
                        font_size=42, min_duration=1.2, max_gap=0.6,
                        fade_duration=0.2)
frame = captions.draw(frame, t)  # frame is a Pillow image; t is seconds
```

Install Pillow and NumPy, and supply an existing font path; its named/default fonts refer
to the old Linux container. No standalone CLI is implemented. Keep source
frames if using it, and inspect the composite's timing, alpha and color.
For native in-scene captions the overlay approach above shares the renderer's
compositing and avoids a separate frame-processing pass.

### Particle textures
`eidoverse/assets/particle_textures/` has 80+ pre-made textures (circles, glow, smoke, fire, sparks, magic, muzzle flashes, energy, stars, dirt, scorch, light, traces, symbols). NEVER ship untextured 2D particles — those render as squares. Load via config.assets, e.g. `config.assets: { "spark": "eidoverse/assets/particle_textures/spark_05.png" }` → `await globalThis.loadImageTexture(ASSETS.spark)`, then feed the texture to `makeParticles` / a sprite material.

### Video on 3D screens
```bash
node eidoverse/video_to_sprite.mjs <clip>.mp4 --output sprite   # → sprite.jpg + sprite_info.json (see file header)
```
Load the atlas + its `*_info.json`, then `globalThis.makeVideoScreen` owns
the rest — the screen material recipe (sRGB, unlit, `toneMapped:false`) and
the per-frame UV stepping, self-updating via the engine loop:
```js
const info = JSON.parse(new TextDecoder().decode(b64toArrayBuffer(ASSETS.videoInfo)));
const spriteTex = await globalThis.loadImageTexture(ASSETS.videoSprite);
const tv = globalThis.makeVideoScreen({ texture: spriteTex, info, width: 1.6 });
scene.add(tv.mesh);   // position over the TV / monitor / billboard's screen face
```
Never hand-roll the UV offset math or a raw material for this — the helper is
the canonical path (same family as `makeScreen` for drawn content).

## Asset authoring, props and sets, voice and music synthesis

- [docs/blender.md](docs/blender.md) — headless Blender (`run_blender.sh`), garments and accessories for VRMs,
  VRMA animation clips, hard-surface props baked to GLB, trim sheets rendered from models.
- [docs/props-and-sets.md](docs/props-and-sets.md) — eight historical voice machines (1939–2001), an 1896
  tandem with rider IK, and the DAISY film's corner, funeral and ocean sets.
- [docs/voicebox.md](docs/voicebox.md) — singing and speaking voices made from scratch, historical
  machine-voice eras, choirs, phoneme-exact visemes.
- [docs/synthkit.md](docs/synthkit.md) — hand-built instruments and drums, sequencing, designed FX,
  loudness-targeted mastering. `eidoverse/examples/daisy/` is a complete song made with both.

## Story / production arc

### Plan 4-6 distinct visual phases BEFORE writing code

Each phase looks/feels different. Distribution:
- **Opening** — establish world / mood / subject
- **Development** — introduce elements, build complexity
- **Climax** — visual or emotional payoff
- **Resolution** — wind down; leave the viewer with something

Never the same shot N times. A static dark room with random objects scattered around is NOT a video.

### Show the character, don't voxelize them away

Hiding the VRM and replacing them with voxel particle systems or stylized
abstractions is NOT a transition technique — it's avoiding the work of
animating them. The VRM + lipsync is the star. Voxelization belongs in
transitions and brief effect moments, not as the character itself.

### Music video specifically

The character DOES THINGS — walks through environments, turns to face camera, moves between locations, gestures, reacts. Standing center-frame cycling one animation is a tech demo, not a music video.

## Pre-render self-scan — grep before you waste a render

Run these against your `scene.js` before the first full render. Fix any
matches and re-scan.

```bash
SC=work/<id>/scene.js

# 1. A controller is in use → vrm.scene transforms should disappear.
#    A match here means the controller and manual transforms are fighting
#    (sliding feet, walk-through-walls, moonwalk).
grep -nE "VRMCharacterController" "$SC" >/dev/null && \
    grep -nE "vrm\.scene\.(position|rotation)" "$SC"

# 2. Every AnimationMixer must drive a clip — otherwise the VRM renders
#    in its T-pose bind. A naked mixer with no .play() means a T-pose.
grep -nE "new THREE\.AnimationMixer" "$SC"
grep -nE "\.clipAction\(.*\)\.play\(\)" "$SC"
# match counts should agree.

# 3. Upper-arm rotations stacking onto the VRM bind pose ⇒ A-pose splay.
#    Either zero the bone first, OR set a quaternion, OR load a VRMA clip.
grep -nE "(leftUpperArm|rightUpperArm|leftShoulder|rightShoulder)\.rotation" "$SC"

# 4. Scenes with walkable geometry + a controller need foot IK or feet
#    float / clip. If the scene has ground / stairs / platforms, this
#    should return at least one hit.
grep -nE "enableFootIK" "$SC"

# 5. A controller-driven VRM must not also get a locomotion clip played
#    in place (the treadmill bug — playVRMADefault throws on walk/run/
#    stairs slots). Any hit here beside a controller is your bug.
grep -nE "playVRMADefault\([^)]*'(walk|run|stairs[A-Za-z]*)'" "$SC"

# 6. NodeMaterial discipline. The pipeline is WebGPU + TSL only — every
#    material should be the *NodeMaterial variant. Non-node materials
#    auto-wrap silently and break TSL effects.
grep -nE "new THREE\.Mesh(Standard|Physical|Basic|Lambert|Phong)Material\b" "$SC"
# A match means the missing `Node` is your bug; rewrite as `MeshXNodeMaterial`.

# 7. Per-frame CPU loops that should be TSL compute. A `for (let i = 0;
#    i < N; i++) { instance.matrix... }` inside renderFrame is the WebGL
#    pattern; WebGPU wants positionNode / TSL compute.
grep -nE "for\s*\(\s*let\s+i\b" "$SC"
# Inspect each hit — loops inside setup() are fine, loops inside
# renderFrame mutating per-instance state are the WebGL anti-pattern.

# 8. The scene script runs as eval'd code — top-level `import` throws.
#    All imports go inside setup() via `await import(...)`.
grep -nE "^import\s" "$SC"
# Should be empty.
```

## Quality verification

Run ALL of these before reporting done. Any failure = re-render the broken
part. "Looks close enough" is never valid.

```bash
# 1. ffprobe video stream
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration,nb_frames \
    -of csv=p=0 work/<id>/<name>.mp4
# expected: WxH,<duration>,<duration*fps>

# 2. ffprobe audio stream
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,duration \
    -of csv=p=0 work/<id>/<name>.mp4
# must show codec (aac/mp3) AND duration. Empty = silent video = FAIL.

# 3. Frame content. Throwaway frames go inside your scene's work dir.
mkdir -p work/<id>/_check && cd work/<id>/_check
ffmpeg -nostdin -loglevel error -i work/<id>/<name>.mp4 \
    -vf "fps=1" frame_%03d.png
# Look at 3-4 of these. All-black / all-white / all-solid = render bug.

# 4. Audio waveform sanity
ffmpeg -nostdin -loglevel error -i work/<id>/<name>.mp4 \
    -af "showwavespic=s=1280x240" -frames:v 1 wave.png
# Flat line = silent track even though codec exists. FAIL.

# 5. WATCH THE FINAL .MP4 DIRECTLY (if you're multimodal — most agents on
#    this toolkit are). Single frames miss:
#   • timing / sync between audio and visuals
#   • loop monotony where there should be progression
#   • T-pose subjects under emissive scenery
#   • camera clipping through geometry or jammed inside a mesh
#   • subject invisible / out-of-frame
#   • audio silent, off-sync, or front-loaded then trailing off
#   • text overlays misspelled / glyph-boxed / Unicode broken
#   • objects placed at wrong scale (a chair the size of a building)
#   • overwhelming glitch effects so heavy you can't see the scene
#   • music drowning the voice (mix balance wrong — most common)
# If anything looks broken, FIX THE SPECIFIC ISSUE and re-render. Don't
# re-render the whole thing from scratch — re-rendering can break sync
# that was already working.

# 6. CAMERA-CLIP CHECK — there is NO camera-clip log. WATCH THE MP4:
#    confirm the camera never sits inside a body/wall or grazes through
#    geometry. If it does, FIX THE CAMERA PATH (raise standoff, route
#    through CameraSafety at shot-setup, move the keyframes off the
#    obstacle) and re-render. Nothing warns you and nothing moves the
#    camera for you.

# 7. PLACEMENT LOG — the placement audits are WARN-ONLY by default: they
#    report clipping, near-surface hovering and z-fighting and move
#    nothing (only a scene that set globalThis._autoFixPlacement = true
#    gets the one-shot repair pass first). A [checkClipping] /
#    [checkHovering] / [checkZFighting] line is a defect to fix in the
#    scene. "[placement] ⚠ N object(s) are genuinely unsupported and will
#    read as floating on camera" = props far above, or with nothing
#    beneath →
#    HARD FAIL: place them with placeOn / placeAgainst / snapToGround.
#    A deliberate flyer → mark obj.userData.noSupportCheck = true.
#    Don't lean on the repair pass as a crutch — place things right.

# 7b. LIPSYNC LOG — "[lipsync] ⚠ VRM '…' mouth NEVER moved across the
#    render" → if that character SPEAKS, you forgot to drive visemes →
#    frozen-mouth talking head = broken. HARD FAIL: drive the visemes and
#    re-render. If the character is intentionally silent, ignore the line.

# 8. LOCOMOTION LOG — read the render's stdout.
#   • "[locomotion] OK — no hand-rolled VRM travel detected"  → good.
#   • "[locomotion] ⚠ RE-RENDER REQUIRED — VRM travelled Xm WITHOUT a
#     VRMCharacterController …" → you slid the VRM by position.set()/lerp
#     while playing a stationary clip → foot-slide. HARD FAIL. Drive
#     locomotion through the controller. If the VRM is intentionally
#     carried (riding a vehicle, a teleport cut), set
#     globalThis._allowManualLocomotion = true. Re-render.
```

**Test render policy:** a five-second iteration loop beats a thirty-minute
panic. Render a single frame (or 0.5s) at the target resolution to verify
framing / subject position / camera angle BEFORE committing to the full
encode — `eido.py render <cfg> --probe` in harness mode, or a short-
duration copy of your config in the loop. If the test frame is broken,
fixing it costs seconds; if you skip the test and the full render is
broken, it costs the full re-render.

**Clean up test clips.** In the agentic loop, the collector picks up the
most recent mp4s — a stray 1-second test render sitting next to your
final can get shipped. Name your real output clearly
(`scene_final.mp4`), delete test segments / preview clips (or render
them to `/tmp`), and make sure nothing newer than the final lingers in
the work dir when you finish.

### Contact sheets

A contact sheet lets a collaborator, or a model without video input, read a
whole piece from one image. From the repository root:

```bash
python contact_sheet.py work/<id>/film.mp4 --every 5 --cols 6
python contact_sheet.py work/<id>/film.mp4 --timeline work/<id>/timeline.json \
  --names '{"verse1": "verse 1 · the machines"}' --title "Title" --synopsis "What the piece is." --parts 3
```

It takes one frame from the middle of every `--every` seconds, scaled to
`--tile` pixels wide in the video's own aspect. With `--timeline` it also
takes a frame just inside each section start. It then labels every tile with
its timestamp, its section and the line sung or spoken at that moment, so
the story reads without sound. The tool accepts two timeline shapes:
- `{ "sections": [{name, t0, t1}], "captions": [{text, t0, t1}] }`, as
  voicebox and song timelines write it (either key may be missing);
- `align_lyrics.py`'s list of `{text, start, end}`.

`--names` gives the section keys readable labels. `--parts N` also writes the
same frames split into N sheets, for tools with per-image size limits. The
output is `<video>_contact_sheet.jpg` unless `--out` names it. A sheet maps
the piece. It cannot show timing, flicker, lipsync or motion, so review those
in the video itself.

## Known stack quirks (handled by the engine)

These are shimmed automatically, but knowing them helps when oddities appear:

- **Materials**: use `MeshStandardNodeMaterial` / `MeshPhysicalNodeMaterial` / `MeshBasicNodeMaterial`. The non-Node variants work via auto-wrap but accumulate WebGL idioms — use NodeMaterial directly.
- **MeshBasic vs MeshStandard** — `MeshBasicNodeMaterial` is unlit; the surface just renders its `color * map`, ignoring every light in the scene. Use it ONLY for things that are themselves emissive: HUD panels, displays, glow strips, neon, screens. For anything that should be a physical object lit BY the scene's lights use `MeshStandardNodeMaterial` or `MeshPhysicalNodeMaterial`. A creature on `MeshBasicNodeMaterial` with a dark color renders as a black silhouette regardless of how the scene is lit.
- **No per-frame CPU loops** mutating instance matrices or vertex positions — use TSL compute or `positionNode`.
- **No CPU per-pixel texture baking** — `rtt(node, w, h)` from `'three/tsl'` instead.
- **GLB textures auto-converted to DataTextures** (Deno WebGPU bindings miss `copyExternalImageToTexture`).
- **`VolumeNodeMaterial` doesn't compile under Naga.** Use `scene.fog = new THREE.FogExp2(...)` for distance fog, or write a custom Box+raymarch material via `RaymarchingBox`.
- **Y-orientation**: top-down throughout. No Y-flip in your code. RenderTarget textures used on a mesh need `map.repeat.set(1, -1); map.offset.set(0, 1)`.
- **VRM = `globalThis.GLTFLoader` ONLY.** Importing `@pixiv/three-vrm` directly causes ShaderMaterial fallback under WebGPURenderer → black scenePass.
- **`scene.environment`**: set the actual HDRI yourself (the engine's gradient-from-background env only kicks in `if(!scene.environment)` — a forget-to-set-it backup, NOT the intended look). Env reflection on flat metal is unreliable here (see Lighting — light surfaces directly).
- **Glass / water / transparent materials: alpha opacity, NOT `transmission: 1.0`.** Working glass on this stack:
  ```js
  new THREE.MeshPhysicalNodeMaterial({
      color: 0xcfe6ff, roughness: 0.05, metalness: 0,
      transparent: true, opacity: 0.3,      // <-- the see-through comes from HERE
      transmission: 0.9, thickness: 0.5, ior: 1.4,
  });
  ```
  The see-through is **alpha opacity** (`transparent: true` + `opacity` ~0.2–0.4). `transmission` + `ior` add refraction flavor on top, but they are NOT what makes it see-through. `transmission: 1.0` with no opacity renders OPAQUE/dark on this stack (the backdrop sample comes back black). For a hero refraction effect, hand-roll screen-space refraction; for ordinary glass/water/ice/windows, the alpha+transmission pattern is the way.
- **Video encoder**: the frame→nvenc pipe defaults to 8000k average / 10000k peak. If high-frequency content (fluid, noise, dense particles, fast motion across the whole frame) still macroblocks into "pixel boxes", raise it via `RENDER_BITRATE` or switch to `RENDER_CQ=19` (near-lossless). (If a delivery target imposes a file-size ceiling, respect it: keep `-cq` higher, drop resolution, or shorten the clip.)
- **Screen-space depth-keyed effects composite OVER no-depth particles.** Any effect that reads scene depth (`depth_fog`, `godrays`, …) blends its result using the depth BEHIND a particle quad — additive sprites, particle-morph clouds, and `fromText` particle words all get fog/rays drawn straight through them. If a particle showpiece must read against the sky, frame it against geometry (occlusion works fine — stones in front of the word clip it correctly). The world-space sky system does NOT have this problem — its cloud dome draws in the scene pass behind the particles. Also remember additive particles literally cannot show against a bright sky (add-to-white is invisible) — stage glowing particle work against dark backgrounds.
- **Transparent materials write into the auto-enhance G-buffer.** The scene pass renders color + encoded normals + metalrough as MRT; those extra attachments follow each material's own blend state (opaques hard-write, transparents blend by their attachment alpha). A custom transparent billboard/quad that lets the DEFAULT normal write through smears its quad-face normals over the buffer GTAO reads, and AO stamps hard dark rectangles behind it. `makeParticles` already opts its quads out; for your own transparent effect quads copy its pattern — `mat.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) })` (alpha-0 writes preserve what's underneath; color stays default). Real transparent SURFACES (water, glass) should keep writing their true normals — SSR needs them.

## Compressing the final video

If the content has visible macroblocking and your delivery allows a heavier
file, transcode the final mp4. h264_nvenc CQ-mode or libx264 CRF:

```bash
# higher quality, still h264, audio passed through
ffmpeg -i out.mp4 \
    -c:v h264_nvenc -preset p5 -rc vbr -cq 19 -b:v 12M -maxrate 24M -bufsize 24M \
    -c:a copy out_hq.mp4
# or CPU libx264:
ffmpeg -i out.mp4 -c:v libx264 -crf 20 -preset slow -pix_fmt yuv420p -c:a copy out_hq.mp4
```

`-cq`/`-crf` is the dial: lower = higher quality + bigger file. Use 18–20 for
visibly clean output on busy high-frequency footage; 22–24 stays close to the
renderer default but recovers some detail.

## Hard rules & anti-patterns (the "why" collection)

Most have deep-dive sections above; this is the checklist form.

- **The deliverable is a 3D SCENE — never a slideshow of images on planes.**
  Web images are encouraged AS MATERIAL (textures on walls/posters/screens,
  decals, motion-graphics elements) — but a video that is just full-frame
  photos on quads fading/jiggling is a slideshow, not a 3D short, and fails
  the bar no matter how cleanly it renders. If your `slideN` planes are the
  entire piece, build the world first and bring the images in as elements
  of it.
- **No Pillow / Python image compositing in the render pipeline.** All text +
  UI comes from Satori (`satori_ui.mjs`) or canvas-2D via `makeScreen` /
  `makeOverlayLayer`. Never post-process an mp4
  frame with PIL.ImageDraw; never Pillow-overlay titles/subtitles/lower-
  thirds. Same render pipeline for everything, same colour space, same AA.
- **Scenes in voids = bug.** If the visible background is a flat dark color
  and the fog fades into the same color, you've made a void — props read as
  floating in nothing. Outdoors → the world-space sky system. Indoors → build
  the enclosure. Stylized negative space → EARN it (gradient, horizon line,
  a ground plane that reads as a stage). Flat `#0a0a14` + matching fog is
  "I forgot," not "I made a choice." The most common shape: HDRI loaded for
  lighting and the agent stops there.
- **Solid objects must NOT interpenetrate (placement, not density).** Density
  is good; stacking everything at the same coordinates is the bug. Place
  solids with the helpers relative to each other; seat characters with
  `seatOn`/`snapToGround`. Interpenetration is only OK for things SUPPOSED
  to share space — fluids, fog volumes, glow/aura meshes, particle fields —
  exempt those with `mesh.userData.noClippingCheck = true`.
- **Every fetched model ends up USED or DELETED.** `fetch_model.py` is not a
  browsing tool. Fetch → read the preview → either wire it into
  `scene.json` assets + `setup()`, or `rm` it and fetch something else. Any
  `.glb` in the work dir at render time that isn't in `assets` is one of
  two bugs — fix it before rendering. (The engine warns about orphans.)
- **VRM blend shapes persist between frames** — reset visemes to 0 each
  frame before applying current values, or you get cumulative buildup.
  Apply raw values; no emotion expressions during lipsync.
- **If a VRM is on screen with vocal audio, you MUST drive lipsync.** No
  middle mode: either drive visemes from `visemes.json` or leave the
  expression manager alone entirely.
- **Loading a VRM without `VRMLoaderPlugin` = black body, eyes only.**
- **Sitting / emoting a stationary VRM — use `seatOn` / `emote`,** never
  hand-lowered idle poses or chair clips on the floor.
- **NEVER `SpotLight` with `castShadow: true`** (MToon crash).
- **Don't fake tool invocations.** If a generator errors or its backend is
  down, surface the actual error in your hand-off — don't synthesize a
  fallback and label it as the tool's output.
- **The character DOES THINGS.** Standing center-frame for 30 seconds is a
  placeholder, not a performance. Walks, gestures, reacts, moves between
  locations.
- **Density first — fill the world.** The quick instinct is to build the
  subject, render, done. That reads as a lonely object in a void. Build
  outward: textured ground → background architecture/landscape/sky →
  5-10+ midground objects → a foreground element near the camera →
  atmosphere (colored lights, particles, fog). Quick self-check on any
  frame: visible empty black background? fewer than ~8 distinct objects?
  subject floating with nothing behind it? no fg/mid/bg depth? → not done,
  add and re-render. *"If I paused on any single frame, would it look like
  a still from a finished film, or a test render of one object?"*
- **Fetch real models — don't build everything from primitives.** Before
  making any recognizable object out of Box/Sphere/Cylinder geometry,
  search `fetch_model.py` first. Primitives are for genuinely primitive
  shapes. A scene with ZERO fetched models is almost always a placeholder.
- **Mirrored / flipped text** → you took the `getImageData`→`DataTexture`
  path. Use `CanvasTexture`; orient the plane, don't flip pixels.

## When stuck

- **Renderer won't start**: `python eido.py doctor` diagnoses deno/ffmpeg/deps. If deps were never fetched, `python eido.py bootstrap`.
- **Cloud reflections indoors**: the WORLD-SPACE sky system works fine inside enclosures — walls/ceilings occlude the dome natively, and SSR blocks sky reflections wherever interior geometry is reflected (only off-screen occluders can leak a little sky onto mirrors). Interior haze = `scene.fog` / `depth_fog`; interiors that set their own HDRI keep it via `sky.bakeEnv(renderer, { ifAbsent: true })`.
- **HUD / lower-third vanishes under the clouds (or under in-scene glass/particles)**: you parented the overlay to the world camera. Use `globalThis.makeOverlayLayer({ fov: camera.fov })`. See "full-frame broadcast overlay".
- **VRM all-black**: you imported `@pixiv/three-vrm` directly. Use `globalThis.GLTFLoader`.
- **VRM in T-pose**: see the anti-patterns list. Most common: forgot `await playVRMADefault(vrm, 'idle', ...)` (non-controller scenes), or pre-played idle UNDER a controller (controller scenes).
- **Music drowning voice**: amix is normalizing. Add `normalize=0` + explicit weights.
- **TTS clusters at the start**: use `adelay` per line; space across the timeline.
- **Texture missing on GLB**: confirm textures embedded, not external.
- **`generate_song.py` / `generate_sfx.py` connection error**: ComfyUI backend isn't reachable — check `COMFYUI_URL` / `python generate_song.py --probe`, or degrade to TTS + ffmpeg-synthesized ambience.
- **Render hangs at first frame**: malformed `expressionManager` call, missing asset key, or missing `await` on `playVRMADefault`.

## Hand-off

Terse final message:

> Rendered to `work/<id>/<name>.mp4` — <duration>s, <WxH>, <frames> frames, audio: <music / TTS / both / SFX>. <one-paragraph description of what's in it>.
>
> Techniques appended to `techniques_archive.md` (repo root).

If you hit a real blocker that you couldn't work around, say so concretely:

> Could not render `<id>`. <Concrete blocker, one sentence>. Tried <what>, got <what>. Returning unfinished.

Don't fake completion. The human will catch it
and lose trust. Honesty is the contract: a real problem reported clearly
gets fixed; a faked "done" gets caught downstream and costs far more.




