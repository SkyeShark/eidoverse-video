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
   anything from primitives, in this order:
   - `python3 fetch_model.py "search terms"` — searches local custom models + Poly Haven + Smithsonian + NASA + NIH 3D **all at once, in parallel**, ranks every candidate across all sources, and delivers the best one (printing the runners-up from every source). **READ the preview before placing the mesh** — verify orientation + scale by using visible features plus the colored axis labels (+X red, +Y green, +Z blue).
     - **ALWAYS pass `--theme "<the brief's mood/setting>"`** so the pick fits your video, e.g. `fetch_model.py "car" --theme "cyberpunk neon dystopia"` or `fetch_model.py "vase" --theme "ancient cracked archaeological relic"`. Theme fit is **semantic** — an embedding model scores how well each candidate matches your setting by meaning, not keywords, so phrase the theme naturally (paraphrases, mood words, eras all work). The theme RE-RANKS the relevance-matched candidates: a damaged car floats up for a dystopia and sinks for a vintage showroom. It never promotes an off-query item (a clock won't win "chair") — it only reorders genuinely-relevant ones. *(Theme ranking uses `EIDOVERSE_EMBED_URL`/`EIDOVERSE_EMBED_MODEL`/`EIDOVERSE_EMBED_KEY` — any OpenAI-compatible `/v1/embeddings` endpoint, defaulting to Jina's free tier via `JINA_AI_KEY`; with no key it degrades to relevance-only, never errors.)*
     - **LOCAL models are referenced IN PLACE — never copy them.** When the match is a local/custom model, fetch_model prints `Local model (referenced IN PLACE — not copied): <absolute path>`. Put **that exact absolute path** into your `scene.json` `assets` (the engine loads any path). Do NOT copy the `.glb` into your work folder — duplicating multi-MB meshes per scene bleeds the disk. (Downloaded models from Poly Haven/NASA/etc. still land in cwd as `model_embedded.gltf` — those you keep locally.)
     - Browse the whole local catalog without fetching: `python3 fetch_model.py --list-local` prints every local model's path + dims + preview. Reference straight from there.
     - It also prints an **`[ORIGIN_INFO]`** line saying where the model's pivot `(0,0,0)` sits in its bbox — **BASE** (y=0 is the bottom; rests directly on a surface), **CENTERED** (y=0 is mid-height; add half the height to stand it on a floor), **TOP**, or **OFFSET**. Do NOT assume the pivot is the geometric center — many GLBs are base-pivoted and a "centered" `position.y` floats or sinks them. The safe move is always `placeOn`/`placeAgainst` (they seat the bbox regardless of pivot); read `[ORIGIN_INFO]` only when you must set `position.y` by hand.
     - **It auto-picks the best match but PRINTS the alternatives spanning EVERY source** with the exact token to re-fetch each. The run also prints the full ranked candidate table (`rel=` relevance, `sim=` semantic theme similarity, `×` the theme multiplier, `→` combined score). If the preview isn't the variant you wanted — wrong colour, wrong type, wrong style — **re-fetch a specific one by its exact name/id**, e.g. `fetch_model.py "server_rack_01"`. Don't settle for the auto-pick when a listed alternative is the right one.
   - `python3 fetch_hdri.py "search"` — environment lighting. Searches Poly Haven + AmbientCG. Required for any 3D scene that isn't a flat indoor stage. Outputs `hdri.hdr` (+ a legacy `hdri_b64.txt` sidecar you ignore). Point the `hdri` asset at the raw `hdri.hdr`.
   - `python3 fetch_texture.py "material"` — PBR sets (basecolor + roughness + normal + AO + metalness + displacement) from Poly Haven + AmbientCG + TextureCan (all CC0). Required for every procedural surface. Outputs `tex_urls.json` — Poly Haven entries are CDN URLs, AmbientCG/TextureCan entries are absolute local paths the engine reads directly. **Fetching is step 1 of 2.** Step 2 is loading them onto your material — flat colors on procedural geometry is a bug. Pattern:

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
   chunk + scattered rocks + grass clusters (makeGrass) + a tree or two
   (GROW them — makeSeedTree, never a gray-box or a mismatched GLB) + a path +
   distant silhouettes + clouds + atmospheric haze. Each is its own
   `fetch_model.py` call. Read each `_preview.jpg`, place with
   `placeOn` / `placeAgainst` / `snapToGround` — never raw coords. Reach
   for MORE, not less.

   > **EXAMPLES ARE ILLUSTRATIVE — DO NOT COPY THEM VERBATIM.** Every code
   > block in this doc and in `eidoverse/examples/` shows you the *API shape
   > and wiring*, not a scene to reproduce. Take the wiring; **throw away the
   > content.** The brief, palette, props, camera moves, parameters, and
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
   - `fluid_3d` — 3D MLS-MPM particle fluid (FLIP-style): pours that fill a
     glass, fountains, rain collecting, a creature of water. Emitters +
     box/cylinder domains + colliders. The single most under-used flagship
     in the toolkit. **The DOMAIN IS the container**: size its walls/floor
     to the visible vessel's interior (a domain bigger than the prop = fluid
     sloshing around an invisible box in mid-air); only the ROOF should be
     generous — it's invisible pour/splash headroom. **RENDER IT AS WATER** — a translucent/refractive surface
     material, not bare FLYING SPHERES (the spheres are the debug view, not the
     showpiece). Creative seeds, go past "pour into a glass": liquid that flows
     UP, mercury / lava / molten gold / ink suspended in zero-g, a body or a
     logo DISSOLVING into running liquid, a creature that moves made of water,
     a flood swallowing the set.
   - `water_compute` — rippling interactive water surface (`disturb()` drops
     ripples anywhere). Pours and streams come from `fluid_3d` emitters.
   - `cloth_sim` — flags, banners, capes, curtains with wind + colliders.
   - `makeParticleMorph` — dissolve a mesh/VRM into particles and reform it
     as something else (the signature transition). **ANY mesh OR TEXT can be
     the frame**: `ParticleMorph.fromMesh(anything, count)` samples a prop /
     fetched GLB / VRM captured mid-pose (`updateTarget` at the dissolve), and
     **`ParticleMorph.fromText('WORD', count, {width:6})`** makes a cloud spell
     a word or logo in ONE call — **`{ ascii: true }`** reforms multi-line
     **ASCII ART** into particles (a face, a sigil, a diagram, an ASCII portrait
     in 3D space). Chain targets for a whole beat: VRM → galaxy → the word →
     ASCII glyph → scatter. (You can even aim a `fluid_3d` pour at a `fromText`
     point set so a liquid WRITES the word.)
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
   - `makeGrass` — a field of real tapered grass blades with GPU WIND sway and a
     height-gradient color, in one call (the textured-ground partner to
     makeTerrain — lay grass ON TOP of it). Wind animates itself on the GPU (no
     per-frame CPU); width/depth, density, blade height, base→tip color, and wind
     amplitude/speed are all adjustable. Pass `heightFn: terrain.heightAt` to drape
     it over uneven terrain, or `clipFn` to carve a path through it.
       globalThis.makeGrass({ scene, width: 40, depth: 30, center: [0, -10],
           bladeHeight: 0.55, spacing: 0.18, perCell: 5, wind: 0.24,
           color: 0x35540f, colorTip: 0xaecb5a /* base→tip */ });
       // wind animates itself every frame — you call nothing.
   - `makeSeedTree` — REAL procedural trees & plants via SeedThree's headless
     agent API (github.com/SkyeShark/SeedThree — same three/TSL stack; a tree
     grown here is IDENTICAL to one grown in the SeedThree app, and presets
     round-trip with its Save/Load panel). SEED-FIRST design: iterate `seed`
     and read `stats` before touching any dial; open knob folders on demand.
       const oak = await makeSeedTree({ species: 'whiteOak', seed: 1737, scene, sunLight: sun });
       console.log(oak.stats.summary);                       // height/width/lod0Triangles
       await makeSeedTree.describe();                        // species menu
       await makeSeedTree.describe('joshuaTree', 'shape');   // ONE folder of dials
     Gotchas (verified): set `globalThis._noAutoFixPlacement = true` in setup()
     — the placement auto-fix dismembers intentionally-overlapping tree
     geometry; trees sway by default (`makeSeedTree.setWind({strength,speed})`);
     judge shadowed trees from frame ≥2. Source: SEEDTHREE_DIR / ../SeedThree /
     ./SeedThree checkout = textured tier; no checkout = GitHub import,
     geometry tier (placeholder materials).

   **Build LOWPOLY hero geometry when fetched models don't fit the art
   direction** — stylized reads better than a mismatched photoreal GLB:
   - low-segment primitives (`CylinderGeometry(r, r, h, 6)`, `IcosahedronGeometry(r, 0)`),
     `flatShading: true`, a restrained 4-6 color palette shared across meshes;
   - organic silhouettes = vertex jitter on a low-seg geometry (displace
     `geometry.attributes.position` ONCE at build time with seeded noise — a
     one-time CPU pass at setup is fine; only PER-FRAME CPU loops are banned).
     **Polyhedron geometries (Icosahedron/Octahedron/etc.) are NON-INDEXED** —
     shared corners are duplicated vertices, so naive per-vertex jitter tears
     the mesh into floating shards. Key the jitter by POSITION (a Map from
     `x.toFixed(4)+','+y...` → offset) so duplicated corners move together;
   - kitbash variants: `cloneModel(base)` + non-uniform scale + yaw + palette
     swap turns one rock/tree/crate into a field of distinct ones;
   - tile box architecture with `uvByWorld` so textures keep uniform density.

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
   Detaching individual pieces and arranging them is how you make the brief's
   unique building / pipework / fence / facade. (`kit.get()` returns `null` for
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
   matches the brief (which usually doesn't exist).

   **Layer procedural detail onto fetched bases.** Poly Haven textures
   give you a clean PBR start; `ProceduralMaterials.composite(base,
   scratches, 'multiply')` adds wear / weathering / age on top so
   surfaces look used rather than catalog-fresh. For surfaces without a
   Poly Haven match, the `ProceduralMaterials` factories
   (`createPaintedMetal`, `createRubber`, `createSkin`, `createScaly`,
   `createFabric`, `createWornMetal`) produce NodeMaterial output with
   basecolor + roughness + metalness + normal — required minimums.

   **Build complex geometry from primitives + math when no GLB fits.**
   `BufferGeometry` + your math = anything. Beyond the procedural
   toolkits (makeCreature, ProceduralMaterials, SDF, water, cloth), the
   stock three.js geometry constructors are your structural toolkit:
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
   - `BoxGeometry` / `CylinderGeometry` / `SphereGeometry` ARRAYS — when
     you need 200 identical boards in a stack, 60 stacked crates, a
     wall of windows, an instanced grid of light bulbs. Use
     `InstancedMesh(geom, mat, count)` and set per-instance matrices in
     `setup()` (one-time, in `setup()` — not per-frame; per-frame goes
     through TSL compute).

   With procedural materials applied, these read as rocks, statues, sci-
   fi machinery, organic structures, ancient ruins — whatever the brief
   needs. Geometry primitives + procedural materials + clever placement
   produces a unique-feeling scene out of zero downloaded assets.

   **Compose environments in layers, near-to-far.** A finished
   environment has all of these — a scene missing one reads incomplete:
   1. **Hero geometry** — the brief's central object (a desk, altar,
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

   - `placeOn(obj, target, { xz, yOffset, xzOffset })` — sit obj's
     bbox-bottom on target's top surface AND center obj's bbox at the xz
     anchor (both axes are bbox-corrected, so an off-center loader pivot
     no longer lands the model sideways). ⚠ The default `xz: 'centered'`
     means the TARGET'S center — `obj.position.set(...)` before a bare
     `placeOn(obj, floor)` is silently DISCARDED and every prop piles up
     at the floor's center (the "furniture blob"). Pass your spot
     explicitly: `placeOn(obj, floor, { xz: [x, z] })`. And READ the
     `*_preview.jpg` fetch_model emits (dimensions + axis guides) BEFORE
     placing. placeOn/snapToGround also record
     `obj.userData._supportTarget = target` — **support-chain memory** the
     audits honor: checkClipping won't separate an object from what it was
     seated on (resting contact is not clipping), and checkHovering verifies
     a seated object against its recorded support before flagging it. Net
     effect: stacked placements (books ON a table, props ON a shelf board)
     survive the audits. xz: `'centered'` (default) | `'random'` | `[x, z]`
     (absolute world). `xzOffset: [dx, dz]` nudges the object on the
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
   - `snapToGround(obj, groundMeshes, { yOffset })` — drop obj to
     whatever surface is directly below its current xz. Handles stairs,
     slopes, terraced floors automatically. Pass the array of walkable
     meshes. For characters on uneven terrain, props on a sloped floor.
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
     audit. Runs automatically after `setup()` and **auto-fixes by default**
     (pushes intersecting pairs apart along the shortest-overlap axis;
     skips intentional parent/child nesting). Set
     `globalThis._noAutoFixPlacement = true` to revert to warn-only.
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
         (the "laptop slightly off the desk" smell) → **AUTO-SNAPPED down**
         by default (disable with `_noAutoFixPlacement = true`);
       • **far** — floating more than 1 m above the nearest surface;
       • **void** — NOTHING beneath its footprint at all (a prop dumped in
         mid-air by hand-coords — `placeOn` would have put it on something).
     `far` and `void` can't be safely snapped (no/uncertain target) so they
     escalate to `[placement] ⚠ RE-RENDER REQUIRED` — a hard fail. **An
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
     wheels unless its nose happens to align with that axis (the sideways-
     vehicle bug — a 75-second video of a vehicle drifting broadside). The
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
     automatically after `setup()` and **auto-fixes by default**. A poster,
     screen, label, logo, sign, floor-marking, or any flat panel placed at the
     EXACT depth of the surface behind it (`panel.position.z = wall.z`) will
     Z-FIGHT — the two coplanar faces flicker frame-to-frame because the depth
     buffer can't pick a winner. **Never place a flat thing at its surface's
     exact coordinate** — offset it a few mm proud (`panel.position.z = wall.z
     + 0.005`) or set `material.polygonOffset = true; material.polygonOffsetFactor
     = -1`. The audit nudges flagged thin panels ~3 mm out automatically and logs
     `[checkZFighting] …`; an intentional flush decal can opt out with
     `obj.userData.noZFightCheck = true`. A `[checkZFighting]` line is a real
     flicker defect, not noise.

   All the audits operate on whole placed objects, so a multi-part desk
   (top + legs) or shelf (boards + sides) is checked as one thing, never
   per sub-mesh. A hover/clip/z-fight warning in the render log is a real
   defect to fix (or a missing `noSupportCheck`/`noZFightCheck`), not noise.

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

   **Placement anti-patterns (these are real failures that have shipped):**

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
   *inside* the carcass (a shipped bug). Instead, drop onto the actual
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

3. **Expand the brief into a fully realized piece.** The brief is the
   seed — a concept, a mood, a few anchor elements. Your job is to
   imagine the rest into existence: the world it lives in, the
   composition and depth of every frame, the rhythm, the things the
   brief doesn't mention but that the piece needs to feel real and
   complete. A brief that names three things doesn't mean a video of
   three things floating in black; it means three things ANCHORED in
   the world you build around them. Take creative authorship. The brief
   trusts you to do the expansion work.

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

(If the ffmpeg has no nvenc, set `RENDER_CODEC=libx264`.)

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
texture sets, VRMs, audio. Declare only what your scene uses. The brief
decides what belongs there; there is no required set.

**Asset injection is RAW BYTES.** Point each asset at the REAL file —
`hdri.hdr`, `model_embedded.gltf`, `character.vrm`, `image.png` — NOT a
`*_b64.txt` sidecar. The engine reads the file and puts a `Uint8Array`
straight on `globalThis.ASSETS[key]` (no base64 round-trip).
`globalThis.b64toArrayBuffer(ASSETS.key)` still works — it passes that
`Uint8Array` through to an `ArrayBuffer` — so
`loader.parse(globalThis.b64toArrayBuffer(ASSETS.x))` is the universal
pattern for GLB / VRM / HDR. (The `fetch_*` scripts still emit a
`*_b64.txt` sidecar for legacy reasons; ignore it and point at the raw
file. Pointing the `hdri` asset at `hdri_b64.txt` and then parsing it
yields "no header found" — you'd be handing the loader base64 text, not
the HDR bytes.)

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

    // Build the world the brief asks for here — HDRI sky + lighting,
    // terrain or interior, props, characters (or none of those, if the
    // brief is abstract / pure motion graphics / data viz / something
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

### Reusable patterns (mix and match per the brief)

**HDRI for lighting** — provides ambient + IBL reflections. HDRI is
INVISIBLE: only set the environment, NOT `scene.background`.
HDRIs are designed to be a global light source, not a backdrop —
using one as the visible sky gives a flat 360 photo behind everything.

```js
// HDRLoader (RGBELoader is deprecated in three 0.184). The `hdri` asset
// points at the RAW hdri.hdr (see "Asset injection is RAW BYTES" above).
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
backdrop / gradient / shader dome that fits the brief — never leave
`scene.background` as a flat dark color and call it done.

**Motivated lights on top of HDRI** — HDRI alone is flat ambient. Add
key/rim/fill that match the brief's mood. One `DirectionalLight` with
`castShadow: true` per scene MAX.

```js
const key = new THREE.DirectionalLight(0xfff8ee, 2.5);
key.position.set(3, 8, 6); scene.add(key);
```

**Procedural surfaces** — PBR sets from `fetch_texture.py`, never
flat-color `MeshStandardNodeMaterial({ color: ... })`. See the "Asset
sourcing" section above for the four-map material recipe.

**VRM character** — ONLY when the brief calls for a character on
screen. Many briefs don't. The `loader.register(VRMLoaderPlugin)` line
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
- `claude.vrm` — a legacy lightweight Claude stand-in; prefer `claude_suit.vrm`

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
name-drop "Claude" unless the brief specifically asks for it.

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
- Genre palette — DO NOT default to synthwave / cyberpunk. The full menu:
  jazz, swing, lounge, ragtime, country, folk, bluegrass, classical, orchestral,
  baroque, opera, ambient, dark ambient, drone, trance, happy hardcore, EBM,
  industrial, martial industrial, new wave, dark wave, ska, pop punk, reggae,
  bossa nova, trip-hop, downtempo, chiptune, vaporwave, slushwave, neoclassical
  darkwave, folkwave, jazzwave, ostalgie, cabaret, cyber cabaret, military
  march, circus, digitized opera, gospel, blues, funk, soul, R&B, hip-hop,
  trap, house, techno, breakbeat, drum and bass, dubstep, psytrance, minimal
  techno. If you catch yourself typing "synthwave" or "cyberpunk", stop and
  pick something else.

**Lyrics rules:**
- Lyrics field is SINGABLE WORDS ONLY. No timestamps. No `[verse]` / `[chorus]` / `[bridge]` labels. No descriptive markers. ACE renders lyrics verbatim — labels become sung words.
- If the brief calls for instrumental, leave the lyrics field empty.

**Output:** writes `song.mp3` in CWD. Poll loop waits up to 5 minutes — that's enough for typical generations. If ACE legitimately doesn't finish, FIX THE BRIEF (shorter duration, simpler tags) before falling back to a synth bed.

### Sound effects — `generate_sfx.py` (Stable Audio via ComfyUI)

Real SFX for your beats — wind beds, footsteps, impacts, mechanical
whirs, water, crowd murmur — instead of shipping a video whose only
audio is music + voice. Fast (~12–30s per clip on a local GPU).

```bash
python3 generate_sfx.py "<prompt>" <seconds> <category> <out.mp3> [seed]
# category: SFX (ambiences/loops: wind, rain, footsteps, room tone)
#           One-shot (single events: a thud, a door, a whoosh, an impact)
#           Music | Instrument (usually use generate_song.py instead)
python3 generate_sfx.py "steady wind through dry grass, open field, no music" 24 SFX wind.mp3
python3 generate_sfx.py "single soft body landing thud on stone, one-shot" 3 One-shot land.mp3
```

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
python3 merge_av.py --video scene_video_only.mp4 --audio mixed_audio.wav --out scene_final.mp4
```

It trims the video to the audio with `-shortest` and **refuses to
clone-pad a short render into a frozen-frame video.** If it prints
`REFUSING TO MERGE — video is shorter than audio`, your render is too
short: re-render with `duration` ≥ the audio length (a second longer is
ideal). **NEVER hand-roll `tpad=stop_mode=clone`** — cloning the last
frame to backfill the audio is exactly how frozen-frame videos ship.
(Know the audio length before you render and set `duration` from it.)

### Lipsync — any scene with a VRM + audible vocals

```bash
python3 -m demucs --two-stems=vocals music.wav      # → vocals.wav + no_vocals.wav
python3 align_lyrics.py vocals.wav --out lyrics_aligned.json
python3 cyborg_voice.py vocals.wav cyborg_vocals.wav   # NOT cyborg_stutter
python3 lipsync.py cyborg_vocals.wav --out visemes.json
```

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
The visible cat-smile is PAINTED on the face; the animatable mouth is a hidden
black cavity revealed by the `show MMD mouth` shapekey. The expressionManager
path above barely moves it (the expression binds under-drive the reveal) —
voice over that mouth reads frozen. The render-verified recipe:

1. Select the 3 face plates once at setup and write **raw
   `morphTargetInfluences` inside `mesh.onBeforeRender`** (survives the
   engine's VRM passes), `fill(0)` FIRST — leftover expression weights
   otherwise hold the mouth shut. (`fill(0)` also kills auto-blink;
   re-apply `Blink` yourself if you want it.)
   ```js
   const plates = [];
   vrm.scene.traverse(o => { if (o.morphTargetDictionary && ('show MMD mouth' in o.morphTargetDictionary)) plates.push(o); });
   for (const p of plates) p.onBeforeRender = () => {
       const inf = p.morphTargetInfluences, d = p.morphTargetDictionary;
       inf.fill(0);
       for (const [nm, w] of Object.entries(globalThis._suitMouth || {})) if (nm in d) inf[d[nm]] = w;
   };
   ```
2. Per frame set `globalThis._suitMouth` to a viseme pose. This table is
   contact-sheet tested — **weights above 1 are intentional** (morph deltas
   scale linearly past 1; these stacks are verified tear-free):
   ```js
   const S = 'show MMD mouth';
   const SUIT_VISEMES = {
       aa: { [S]: 1.6, 'あ': 2.0, JawOpen: 1.5, A: 0.5 },   // big open — the workhorse
       oh: { [S]: 1.2, LipFunnel: 1.0, 'お': 0.8 },          // rounded drop
       ou: { [S]: 0.8, LipPucker: 1.2 },                     // tight pucker
       ee: { [S]: 1.0, 'え': 1.5 },                          // wide + shallow
       ih: { [S]: 0.9, 'い': 1.2 },                          // flat slit
       rest: {},                                             // painted smile returns
   };
   ```
3. Simplest talking (one openness signal — `lipsync.py get_mouth_openness`
   or an RMS envelope): scale the whole `aa` pose by openness 0..1 —
   verified to ramp smoothly. For full visemes: **WINNER-TAKE-ALL, never
   additive.** `lipsync.py` emits all five channels at once — summing the
   poses renders untested morph combinations that read as glitches.
   EMA-smooth the channels (~3 frames), pick the dominant one, render ONLY
   its pose scaled by `min(1, value/0.35)`; below ~0.03 raw → rest.
4. Traps (all render-verified): `vis_aa/ih/ou/ee/oh` and the plain vowel
   shapes do NOTHING without the reveal; `MouthClosed` does NOT hide the
   cavity (rest = reveal at 0); never drive `hide mouth` (it restyles the
   painted line — an aesthetic change, not lipsync); `O`/`お` solo are
   empty exports. Expression accents that DO work as raw morphs: `Smile`,
   `MouthSmileLeft/Right`, `MouthFrown`, `Blink`, `EyeClosedLeft/Right`,
   `EyeWide`, `Blush`/`照れ`.

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

Music-video full protocol:
1. `generate_song.py` with a vocal tag + singable lyrics
2. demucs split → `vocals.wav` + `no_vocals.wav`
3. `align_lyrics.py vocals.wav` → `lyrics_aligned.json`
4. `cyborg_voice.py vocals.wav` (NOT stutter — stutter breaks sustained notes)
5. `lipsync.py cyborg_vocals.wav` → `visemes.json`
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
- Manual lights ON TOP of HDRI for specific motivated sources — a key light from the direction the brief implies, a rim/back light to separate the subject from the background, accent point lights for diegetic sources (neon signs, screens, candles, sun through a window).
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
  await body.walkTo(2.5, -3);                            // plans a path, turns + walks it, arrives → idle
  // in renderFrame(t): body.update(t, dt);  read body.getPosition() / getHeadPosition()
  ```
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
  pre-played action stays at weight 1 and blends over every clip it plays
  (the recurring "legs drag around, no walk animation" bug).
- Do **NOT** call `mixer.update(dt)` / `vrm.update(dt)` yourself (it does).
- Do **NOT** write `vrm.scene.position` / `.rotation.y` per frame — read
  position via `getPosition()`; face the camera only when stationary via the
  controller's `heading`. Manual transforms each frame = foot-slide / drag.

## Movement vocabulary — run, vault, climb, jump, ladders, gestures, sitting

The controller's full vocabulary, available through all three entry points
(`VRMRobotBody` / `EidoverseRobotController` / `VRMCharacterController` expose
the same calls). Everything below is animation-driven with automatic contact
IK — hands plant on vaulted objects, grab ledge lips, and find ladder rungs on
their own. Never hand-IK limbs or hand-animate any of these moves.

- **Running.** Per-waypoint: `setWaypoints([{ x, z, action: 'run' }, …])` —
  they run to that waypoint and drop back to a walk for waypoints without it.
  Direct: `setRunning(true/false)`. Stride syncs to actual speed; stairs
  switch to run-stair clips automatically.

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
  Set `autoManeuvers = false` while deliberately approaching furniture or
  scenery the character should NOT parkour over (a bench they'll sit on is
  not an obstacle), and re-enable after. Check `isManeuvering()` before
  issuing new orders mid-flight.

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
  walking:
  ```js
  await ctrl.loadGesture('cheer');           // once, at setup
  ctrl.playGesture('cheer', { weight: 2.5 }); // ≈70% gesture on the upper body
  ctrl.stopGesture();
  ```
  Weight is a mixer blend: `2.5 ≈ 70%`, `4 ≈ 80%`. Gestures end automatically
  when a maneuver starts (the whole body belongs to the vault/climb). A FULL
  emote (`playEmote`) still suspends locomotion entirely — gestures are the
  move-and-emote path.

- **Aiming a standing emote.** Full emotes (salute / bow / dance / talk while
  stopped) face `Math.PI` by default. To aim one at the camera or another
  character, set the facing yaw before playing (on `EidoverseRobotController` /
  `VRMRobotBody` the emote API lives on `.charCtrl`; on a bare
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

7. **Loading Walk Backwards by default.** Backwards walking is a narrative
   choice, not a default. Load the normal walk for forward locomotion.

## What's on `globalThis` when your script runs

### Engine
- `WIDTH`, `HEIGHT`, `FPS`, `DURATION`, `TOTAL_FRAMES`
- `canvas`, `GPU_ADAPTER`, `GPU_DEVICE`
- `ASSETS[key]` — raw `Uint8Array` bytes keyed by your `assets` map
- `b64toArrayBuffer(x)` → ArrayBuffer (passes Uint8Array through; decodes legacy base64 strings)

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
`eidoverse/assets/animations/` (slot name = filename stem):
- **Locomotion** (driven by `VRMCharacterController` — NOT playable via `playVRMADefault`): `walk`, `run`, `fastRun`, `slowRun`, `sneak`, `walkBackward`, `stairsUp`, `stairsDown`, `stairsRunUp`, `stairsRunDown` (plus controller-internal: `turnLeft`, `turnRight`, `jump`, `vault`, `climb*`, `fallLand`)
- **Stationary** (`idle`, `fallIdle`) and **Expressive** (a STATIONARY VRM only — see below): `sit`, `talk`, `cheer`, `reach`, `raise`, `fist`, `salute`, `crazy`, `dance`

Helpers: `playVRMADefault(vrm, slot, { loopOnce, fadeIn, fadeOut })` sets up `globalThis._mixer`. The engine auto-updates `_mixer` each frame if set.

> **`playVRMADefault` REFUSES locomotion slots.** Calling `playVRMADefault(vrm, 'walk')` (or run/sneak/stairs…) **throws** — playing a locomotion clip in place is the "walking in place" treadmill bug (legs cycle, body never moves). Locomotion is owned by `VRMCharacterController` (`body.walkTo(x,z)` / waypoints), which moves the body AND grounds the feet with IK. `playVRMADefault` only plays stationary/expressive clips. The one exception — a VRM genuinely on a treadmill or carried by a vehicle — passes `{ force: true }` (or `globalThis._allowManualLocomotion = true`).

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

**Multiple characters — just animate each; the engine drives them all.** Load each VRM, then call `playVRMADefault` / `seatOn` / `sitOnGround` / the controller per VRM. The render loop updates EVERY loaded VRM's mixer **and** `vrm.update()` every frame (one mixer per VRM — replaying a clip on a VRM replaces its previous mixer, so idle+sit can't both play). Do **NOT** hand-roll mixer management for multi-VRM scenes — capturing mixers into your own vars, nulling `globalThis._mixer` between loads, or updating `_mixer1`/`_mixer2` in `renderFrame`. That old workaround leaves the 2nd character standing in its chair or sunk through the seat (only one VRM got driven). Each `seatOn`/`playVRMADefault` call is self-sufficient.

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
unless the brief explicitly wants a "robot POV / diagnostics" look.

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

Do NOT hand-build CanvasTexture screens in scenes anymore — this helper IS
that pattern, done right. Full-frame HUDs / lower thirds still go through
`makeOverlayLayer` (screen-locked); screen-space glitch/CRT looks are still
`CustomEffectsDeno`'s job, never faked inside `draw()`.

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

Always-on baseline (no opt-in): GTAO + SSR + UnrealBloom + FXAA. Moving sky/cloud reflections on metals come from the sky system's `sky.enableReflections(camera)` (see "WORLD-SPACE SKY + WEATHER").

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

**Robot scene direction — hero-reel lessons (hard-won, follow these):**
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

**`makeGrass`** — a field of real tapered grass blades with GPU wind sway, NEVER
a flat green PlaneGeometry (the outdoor tech-demo tell). 5-vertex tapered blades
on a jittered tuft grid (continuous coverage, no isolated-blade "chunks"); vertex
colour is a base→tip height gradient; wind is a sine sway + scrolling gust field,
all on the GPU via `positionNode` (no per-frame CPU). Wind animates itself.
```js
globalThis.makeGrass({ scene, width: 40, depth: 30, center: [0, -10] });   // simplest
// lusher, breezier, sun-kissed:
globalThis.makeGrass({ scene, width: 60, depth: 40, bladeHeight: 0.7,
    spacing: 0.16, perCell: 5, wind: 0.28, windSpeed: 2.0,
    color: 0x2f5212, colorTip: 0xb6d45a });
```
- Tune to the brief: `width`/`depth` (metres; `size` = square), `center [x,z]`,
  `spacing` (smaller = denser → heavier), `perCell` (blades/tuft), `bladeHeight`,
  `bladeWidth`, `color`+`colorTip` (base→tip — dry/autumn/alien grass), `wind`
  (amplitude; **0 = dead-still**), `windSpeed`, `lean`.
- `heightFn: (x,z) => y` drapes it over uneven ground — pass `terrain.heightAt`
  (from `makeTerrain`) so each blade sits on the surface. `clipFn: (x,z) => bool`
  skips blades (carve a path, keep a clearing, avoid a building footprint —
  but DON'T clip holes around props standing in the field; grass hugging a
  rock or a log reads natural, a bare ring around it reads wrong).
- Rim fade — the field's edge thins out and tints so it blends away instead of
  ending in a hard line: `fade` (default on when the scene has fog; `false`
  disables), `fadeStart`/`fadeEnd` (fractions of the half-extent, 0.62/0.98),
  `fadeColor` (default = fog colour). Against a BRIGHT sky/fog, pass a dark
  earth tone instead (e.g. `fadeColor: 0x6e5f3e`) — tinting rim blades toward a
  bright horizon paints the very line you're hiding. And size the field so its
  edge dies INSIDE the fog's heavy band; extend the underlying terrain far
  past the grass so the ground, not the void, carries the distance.
- `backlight` (default 0.22, `0` disables) — a height²-scaled emissive on each
  blade that reads as low sun glowing through the tips; lovely at golden hour,
  turn it off for overcast/night.
- You call nothing per frame — wind self-updates. Returns `{ mesh, material,
  update, uniforms: { wind }, bladeCount }`. Lay grass ON TOP of a textured
  ground/terrain; the blades are the detail, the ground carries the far distance.
- Density costs: ~40×30m at spacing 0.17 / perCell 5 ≈ 250K blades — fine. Keep
  the field to roughly what the camera sees rather than carpeting a whole world
  off-screen.

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
head — which looks exactly like a catastrophic skinning/engine bug and
has sent real builds on false bug hunts. Shadow maps and pipelines also
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

The material is a real **lit `MeshStandardNodeMaterial`** — the relief is lit, self-shadowed (a second march toward `lightDir`), and its **shading normal is derived from the height field by default** (`heightNormal:true`), so it shades like geometry with NO normal map needed. It also sets `maskShadowNode` so cast shadows follow the carved outline; `createReliefColumn` additionally enables the relief self-shadow mode so recesses shadow themselves. `computeTangents()` is mandatory (POM marches in tangent space) — as a safety net, the helper audits the scene at first render: a POM mesh with no tangents gets them auto-computed (the warning names the mesh), and when they can't be computed (merged non-indexed geometry) the relief shading normal is disabled instead of miscompiling into an invisible mesh (`THREE.Node: Recursion detected` on a POM surface means exactly this). It also warns on `curvedSilhouette` without `inflate` and other footguns — read the warnings; they name the exact fix. (`selfLit`/`lambert` remain legacy unlit escape hatches; never `MeshBasicNodeMaterial` — it renders all-black under the march.)

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
  section) — states from drizzle to darkstorm with world-anchored rain,
  wet surfaces + puddles, from-the-clouds lightning, and smooth
  agent-directable transitions. Add `rain_on_camera` (LENS rain —
  screen-locked refracting droplets + wet blur) on top only when the
  shot wants a lens inside the storm.
- **Water / pours / splashes** → the fluid tools (`water_compute`,
  `fluid_3d`) — including novel uses: rain sheeting down a
  window, a character wading, ink blooming, a zero-g blob.

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
- `sky.enableReflections(camera)` — per-pixel MOVING cloud reflections on
  metals (SSR composes on top; geometry occludes sky reflections).
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
weather.setWeather('storm', 1);            // clear|drizzle|sunshower|overcast|rain|storm|hurricane|noreaster|darkstorm
sun.intensity *= weather.sunDim();
// per frame: weather.update(t, camera)  — REQUIRED (rain, lightning, greying)
```

- `weather.transitionTo(name, k, durationSeconds)` — SMOOTH weather change:
  everything (cloud coverage, rain, wind, lightning odds, greying, wetness)
  eases across the window. Duration is yours to direct: `90` = a storm
  rolling in over a minute and a half; default 45. One call, no other steps.
- Weather couples the sky automatically: coverage presets, sun dimming,
  wind-driven cloud + rain drift, from-the-clouds lightning with distant
  sheet flashes on harsh states, world-tiled rain curtains under dense
  cells. Mark materials `userData.noWet` to skip wetness; sky-element
  materials should set `userData.keepEnv` so reflection-hook env
  suppression leaves their env-IBL alone.
- Scene lights should re-apply per frame during transitions/cycles:
  `sky.applyToLights(...)` then `sun.intensity *= weather.sunDim()`.

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

**Water comes from the fluid tools — `water_compute`, `fluid_3d`.**
A real water surface ripples, a real pour streams and
splashes, a real splash throws droplets with the sim's dynamics — reach
for these for any pool, lake, rain-on-glass, pour, or splash. A displaced
mesh driven by a sine/noise function reads as plastic; let the sim carry
the motion.

**`water_compute`** — interactive height-field water surface (compute shaders).
```js
// NOTE: scene scripts are eval'd, NOT loaded as modules — use DYNAMIC
// import() inside setup(), never a top-level `import` statement.
const { createWaterCompute } = await import(globalThis.EIDOVERSE_DIR + 'water_compute.js');
const water = await createWaterCompute(renderer, { width: 128, bounds: 20, color: 0x2266aa });
scene.add(water.mesh);
// per frame: water.step()
// drop a ripple — coords are PLANE-LOCAL (the surface is built around its
// own origin; ±bounds/2). If you moved water.mesh, pass offsets relative
// to the mesh, NOT world coords — world coords silently miss the grid:
//   water.disturb(localX, localZ, radius, amplitude)
```
Real-time wave sim (verified). Use for puddles, lakes, pools, fountain
basins, rain-impacted surfaces. Key options: `circular: true` masks the
surface to a disc (for round containers — cups, bowls, barrels);
`maxHeight` clamps wave height so sustained disturbance can't run away
into a spike; `displaceScale` tunes visible wave amplitude.

**Pours / streams** — use `fluid_3d` (the MLS-MPM particle liquid): aim an
emitter where the stream starts, give the container a collider, render the
particles as water. Pour-into-container pattern = a `fluid_3d` pour filling
a collider cup, optionally paired with a `water_compute({ circular: true })`
surface whose `mesh.position.y` you raise over the fill duration so the
stream lands on a rippling, rising level. Same primitives compose into
fountains, rain into a barrel, a waterfall pool — point them where the
brief needs.

**`WaterMesh` + `SkyMesh`** — passive ocean / large-scale water with
FFT-style waves. Better than `water_compute` when you need horizon-
filling water you don't push around interactively.
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
NOT 3D liquid (use water_compute / WaterMesh for that).
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
`globalThis._overlayScene` / `_overlayCamera`; the engine does the rest.

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

### Particle textures
`eidoverse/assets/particle_textures/` has 80+ pre-made textures (circles, glow, smoke, fire, sparks, magic, muzzle flashes, energy, stars, dirt, scorch, light, traces, symbols). NEVER ship untextured 2D particles — those render as squares. Load via config.assets, e.g. `config.assets: { "spark": "eidoverse/assets/particle_textures/spark_05.png" }` → `await globalThis.loadImageTexture(ASSETS.spark)`, then feed the texture to `makeParticles` / a sprite material.

### Video on 3D screens
```bash
python3 video_to_sprite.mjs <clip>.mp4 --out sprite.png   # (deno tool; see file header)
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

### 3D fluid — pours, sprays, splashes (`fluid_3d.js`)
MLS-MPM particle fluid with emitters + sphere colliders + a raymarched water surface. Getting it to read as *water* (not specks, blobs, flat sheets, or invisible) is mostly these levers:
- **`surfaceMesh` boxMin/boxMax ARE the world placement.** They position the [0,1]³ domain in world space inside the shader — never ALSO scale/move the returned mesh (the raymarch then samples density at a ghost location and the water is invisible). Set the world box via the options and leave the mesh untransformed. (The returned proxy self-exempts from the placement audits — it legitimately overlaps the vessel and the fluid; if anything ever relocates it, the pool vanishes and the stream cuts off at a floating box edge.)
- **Emitter spawn density ∝ rate / (velocity × area).** A slow dense spawn (`velocity: [0,-0.5,0]`, high rate, wide radius) piles particles up AT the nozzle and the raymarch renders a fat levitating water mushroom there. Give pours a strong exit velocity (≥1.5 domain-units/s), a modest rate, and a tight radius so the stream leaves the spawn region before density accumulates.
- **Substep the sim**: call `fluid.step(dt/N)` N times (≈3) per frame. One `step(1/60)` per frame is unstable — the water flickers and gets flung onto the domain walls.
- **Lower the gravity** (e.g. `gravity:[0,-22,0]`, far below the strong default) so the pour stays a dense, connected 3D body. High gravity thins the falling stream below the surface threshold, so only pooled water shows.
- **Small, dense domain + TIGHT framing.** A big domain dilutes per-cell density below the iso threshold → invisible water. The fluid is a closed box, so water always clamps onto its walls as flat sheets — do NOT enlarge the domain to hide them (that dilutes the water); instead frame tight on the subject so the walls/floor are off-frame, and occlude the back with a backdrop.
- **Scale the surface `steps` to the box size** — too few raymarch steps over a large box undersamples into cubic / aliased blobs (more steps is cheap here).
- **Make it interact with a character**: update sphere `setColliders([...])` every frame from the VRM's bone world positions (head/chest/hips/arms, mapped into the [0,1] domain) so the water sheets off the moving body.
- **Surface depth + shading**: the raymarched surface must write per-fragment hit depth or it sorts behind opaque geometry and reads as flat sheets stuck to the box planes. And water reflecting a dim environment renders dark — give it a bright reflection source or it blends into the background.

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

Run these against your `scene.js` before the first full render. Each
catches a failure mode that has eaten thousands of frames in past
sessions. Fix any matches and re-scan.

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

# 5. Walk Backwards is a narrative choice. If the brief doesn't call for
#    backward motion, swap to the forward walk + waypoints.
grep -nE "Walk.?Backward" "$SC"

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

# 7. PLACEMENT LOG — clipping + near-surface hovering are AUTO-FIXED by
#    default (the engine pushes overlapping models apart and snaps
#    near-surface floaters down, once, post-setup). You'll see
#    "[placement] ⚠ RE-RENDER REQUIRED — N object(s) floating with no/far
#    support" ONLY for props dumped in mid-air with nothing beneath →
#    HARD FAIL: place them with placeOn / placeAgainst / snapToGround.
#    A deliberate flyer → mark obj.userData.noSupportCheck = true.
#    Don't lean on auto-fix as a crutch — place things right.

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

Codified from real shipped failures. Most have deep-dive sections above;
this is the checklist form.

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
- **Genre: don't default to synthwave/cyberpunk.** Match the brief; use the
  whole menu; surprise yourself.
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
- **Re-reading these docs beats re-discovering the bug.** Every rule here
  was paid for in broken renders.

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




