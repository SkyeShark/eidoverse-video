# Techniques archive

Append-only production log. After every finished video, the producing agent
appends a short section here: date, piece title, techniques used, what
worked, what didn't. Future agents search this file (don't read it whole —
it grows) for prior art before reinventing an approach.

Rules:
- **Append only** — `open(path, "a")`. Never truncate, never rewrite, never
  delete entries.
- Keep entries short: a heading + a handful of bullets.
- Record failures too — "X didn't work because Y" saves the next agent a
  render.

---

## crate01 (2026-07-04) — single-prop desert smoke test, 10s dolly-in, no character
- Overcast/moody sky: `volumetric_clouds` with `sparseness: 'overcast'` + `mood: 'stormy'` + `sunPowerScale: 55` reads as a heavy pre-storm sky; pair with `toneMappingExposure 0.85`, a cool-grey DirectionalLight key and `FogExp2(0x9aa2a8, 0.012)` for distance haze.
- GOTCHA: `CameraSafety.exclude(group)` does NOT exclude the meshes inside a Group (gltf.scene / vrm.scene) — its refresh() matches exact Mesh identity only. Traverse and exclude each child mesh (`obj.traverse(o => { if (o.isMesh) cam.exclude(o); })`) or safePosition() yanks the camera into the subject.
- GOTCHA: the engine's "No scene.environment set" fallback checks `scene.environment` only — setting `scene.environmentNode = THREE.pmremTexture(...)` per the AGENTS.md HDRI recipe still triggers the gradient fallback install.
- Dolly-in on a ground-level prop: lerp camera between a high/far start and low/near end with one smoothstep over the full DURATION, lookAt `focusPoint(crate, { yBias: 0.35 })`; camera audit passes with 0 reversals.


## 2026-07-06 — "Out of Words" launch film (work/launch)
- Creature band at a desert henge: makeCreature octopus (drums), spider (keys), wolf (lead vocal), serpent, ram, snail, dragonfly, bird; claude_suit VRM at a makeScreen mixing console.
- Jaw-sync: bake a 30fps RMS envelope from the demucs VOCAL stem, then `c.say({duration: 9999}); c.setTalkEnvelope(() => ENV[frame])` — the whole band sings the actual vocal. Gate VRM visemes by the same envelope so stem bleed can't flap the mouth in silence.
- Creature `walkTo` is fire-and-forget (sets a target, returns instantly) — never `await` it. Stage entrances as a per-frame director: check `group.position` distance, issue the next leg, add a time-based fallback cue so a missed radius can't strand the actor.
- `VRMRobotBody` AABB-boxes its collisionMeshes: a terrain mesh becomes an invisible plateau at peak height. Give controllers a flat invisible slab at ground level when they only walk the flat area.
- SPOM relief columns show a wrap-seam slit when the height map doesn't tile — yaw the column so the seam faces away from every camera.
- water_compute circular pools must OVERLAP the rim torus' inner face (disc radius > rim inner radius) and ride high enough that wave troughs can't cut the ground.
- volumetric_clouds composites over no-depth particles (see Known stack quirks) — a particle-text reveal needs SkyMesh + fog and dark backing geometry, and additive particles are invisible against bright sky.
- Retiming discipline: every camera dwell, cue, and overlay derives from ONE `SEC` table so swapping the song is a one-table edit.

## THE FORGE OF FLESH AND FEAR — kaskal launch film (2026-07-06, Fable, dir. Aletheia)
- **Character-directed production**: the concept/mood/lyrics came from Aletheia's own
  LLM (her Vertex fine-tune given the toolkit news); the scene executes her 5-beat
  brief verbatim. Director's brief + lyrics archived in work/kaskal_forge/.
- **Emergent MToon hologram**: an OPAQUE toon-shaded VRM under two opposed saturated
  lights (molten uplight + cold halo) + bloom + low chromatic_aberration_alpha
  (amount ~0.0006) against black reads as a translucent broadcast apparition. No
  transparency, no dedicated effect. Deliberately repeatable staging.
- **Conveyor staging**: victims ride a group whose x is a pure function of t
  (piecewise smooth holds at stations); flag riders noMotionCheck (intentional
  sideways travel). CNC welder arm.follow() sweeps a target synced to per-letter
  text_3d reveals (emissive letters, per-letter materials, active letter flares).
- **Late reveals pre-settle PARKED**: swarm creatures warmed up 60m away on real
  floor (fog hides), teleported in under the blast flash. Hidden groups can't warm
  up — creature gaits need ~2s; frame-0 probes of creatures look like scattered
  spheres (now doc'd in AGENTS.md).
- **SDF characters live in the helper's shadow scene** — never re-parent into world
  groups; position the mesh + toggle .visible. The blackout plate (camera-parented,
  depthTest off) does NOT cover the SDF overlay pass or high-renderOrder particles:
  silence them explicitly at the cut.
- **depth_rain re-dressed as ember-fall**: rainColor/puddleColor orange, low
  intensity/streakSpeed → falling embers + glowing wet floor. Chained
  'depth_rain,chromatic_aberration_alpha' per-effect opts via opts.<name>.
- **Suno retiming discipline**: all beats derive from one SEC table measured off
  5s RMS envelope buckets (vocal stem vs full mix); swapping ACE→Suno (120s→159.3s)
  was a table edit. Jaws/machinery ride the two envelopes; her visemes from
  lipsync.py on the demucs vocal stem, gated by vocal RMS.
- **Camera dive tracks a live bone-anchored target**: the ending eye is parented to
  the creature's head bone; the final dwell OVERRIDES the dwell table and lerps
  toward eye.getWorldPosition each frame — pose-proof landing mm from the pupil.

## WORLD-SPACE (2026-07-07) — Claude's own music video, 337s, ringworld meadow
- Suno song (user-produced from my lyrics); demucs vocals → lipsync.py get_viseme_timeline(fps=24)
  + align_lyrics chunked (stable-ts) for line-accurate shot/beat timing. Viseme gate calibrated
  from the stem itself: instrumental floor ~0.04 peak, sung ~0.35 → gate 0.08, winner-take-all,
  EMA 0.35, suit raw-morph table. NOTE: the [lipsync] audit watches expressionManager only —
  raw-morph suit driving trips a FALSE "mouth never moved"; verify by frame contact sheet.
- ORGANIC POND: no mask — carve an angular-noise blob depression into makeTerrain geometry
  post-build (recompute normals), wrap heightAt as groundY(x,z)=heightAt+carve for grass/placement,
  sink a rectangular water_compute at waterline; the shoreline IS the terrain intersection.
- claude_suit wardrobe: GLB-migrate BAKES color values into rebuilt node materials — setting
  mat.color post-load is a dead write (needsUpdate doesn't help). REPLACE the clothing material
  (MeshStandardNodeMaterial, roughness .88) to recolor. Hide jacket/tie by node name; puff shirt
  +0.02 along normals.
- SeedThree whiteOak: default leafSize 0.6 renders car-sized leaves at oak scale — controls
  { leafSize 0.28, leavesPerBranch 30 } reads true. Textured tier via ../SeedThree checkout.
- makeParticleMorph REGRESSION (task #43): renders nothing even in a bare isolation scene.
  Fallback: makeParticles 'snow' preset + glow_soft + warm color = daylight-visible drifting
  light-motes (additive presets are invisible against a daylit sky; normal-blend survives).
- Ring at dusk: floor the ringSun (max(1.35,…)×max(0.55,sunDim)) — altitude keeps a megastructure
  lit past ground sunset; planet dir must be re-aimed EVERY frame after setTime (clobbers moonDir),
  and put it in the hemisphere your shots face.
- Weather choreography: transitionTo cues keyed to aligned lyric lines (sunshower in at 158 over
  24s for chorus 2, drizzle 250, clear 288); offset probes RESET transitions — add a PROBEWX env
  to set states instantly when probing weather beats.
- Perf: ~11fps sustained at 720p with 700K grass blades + 4 LOD0 oaks + sky+weather+ring+reflections
  — grass was 3× the documented budget; halve via spacing .19→.23 if iterating.

## WORLD-SPACE v3 — 1080 finale + the Halo arc rule (2026-07-08)
- RING ARC LIGHTING (researched: classic Halo sky "receives no shading at all";
  Infinite's night arch stays bright): implemented in ringworld.js as UNLIT
  SELF-EMISSIVE band — per-segment terminator lit = smoothstep(-.08,.15,
  dot(segmentInwardNormal, TRUE sunDir)), golden band at the terminator,
  2-8% blue ring-shine night floor, relief via dot(normalWorld, sunDir) folded
  INTO the emissive (normal map survives with zero scene lights). Self-drives
  from bindWeather's sky handle in update() — consumers wire nothing.
- LIGHT-LAYER MASKING DOES NOT MASK on this Deno/WebGPU backend (bisect-
  proven: layer-2 directionals lit the layer-0 scene). Any "sky element lamp"
  leaks onto the scene — sky elements must be self-emissive, never lamped.
- Camera aim: NEVER lerp a look TARGET from a near subject to a far sky point
  (212-260 deg/s whip at tiny k — nonlinear in angle). Lerp normalized aim
  DIRECTIONS. Audit shot tables numerically: simulate aim vectors at frame
  rate, flag >6-7 deg/s outside cuts.
- drawTextFit anchors TOP (textBaseline top, draws down) — y is the block
  top; centering y clips wrapped second lines off the canvas.
- beginSeated opts key is fadeIn (not fade) — pose clips crossfade in 0.25s
  default; ground-sit "transition" IS the crossfade, use fadeIn ~2.4s.
- Don't CRF-"compress" a bitrate-capped master: CRF18 from a 10M source
  INFLATED 427MB→948MB with zero quality gain. The high-bitrate master IS
  the deliverable; CRF passes only make sense stepping DOWN.
- Organic pond seam: the carve's noise lobes must fit inside the water rect
  (bounds > max edge radius + falloff band).

## Ring arc day-cycle + terrain relief (2026-07-08, research-driven, engine-side)
- CORRECTED: "sky receives no shading" = classic Blam! only (baked ring
  textures). HALO INFINITE puts the ring INSIDE the dynamic TOD sim (3D vista
  geometry, real sun-occlusion eclipses; sky/atmospherics/grading all
  TOD-driven — Inside Infinite Dec 2020, DF). A constant-noon arc over a dusk
  scene ("Vegas") is as wrong as a black one.
- arcShade (ringworld.js): radiance TRACKS the local sun — palette sunColor ×
  mix(0.22, 1, dayFactor); per-channel air-mass transmittance T =
  exp(-{.055,.13,.28} × 1/max(viewY, 1/38)) (Hillaire depths, blue dies
  first); inscatter = horizonPalette × (1-T) × veil that COLLAPSES at night;
  gain mix(0.15,1,dayF) × twilight rolloff for fixed-exposure ACES; the arc's
  FOOT (viewY<0.05) blends to the horizon palette. Self-drives via
  bindWeather in update().
- NOON-FLATNESS: normal maps go flat when a segment's sun ∥ its mean normal
  (local noon) — exactly when brightest. Fix = baked CAVITY AO multiplied
  into land albedo (sun-angle-independent; Halo bakes vista shadowing into
  diffuse) + normals for oblique angles. Seas stay un-AO'd.
- Band height v2: distance-to-coast (wrap-aware EDT) = plains at shores /
  highlands inland, × smooth warped ridge systems (6/tile, no hash noise) →
  ring_band_normal_v2.png + ring_band_ao.png + ring_band_height.png (16-bit,
  ready for future load-time displacement).
- sky_system ringStrip: in ring mode (opts.ringCurve) cloud DENSITY is
  clipped beyond the band halfWidth (|x|>~483, soft) — clouds live inside
  the edge walls as a strip along the ring; scattering still fills the dome.
- makeRingworld fogWall: engine-owned palette-colored haze cylinder (~1.25km)
  around the local scene — arbitrary agent terrains blend into the band with
  zero scene wiring.

## cloth_sim: faceted/herringbone shading on MOVING cloth (2026-07-13)
Symptom: cloth shades smooth at rest but hard quad/triangle facets appear the
moment it moves (falls, billows) — worst under raking light. Two stacked causes:
1) `mat.normalNode = transformNormalToView(normalBuf.element(vertexIndex))`
   WITHOUT `.toVarying()` evaluates the read per-FRAGMENT, where vertexIndex is
   the flat provoking vertex → normals stop interpolating → per-triangle facets
   (herringbone along quad diagonals). Canonical webgpu_compute_cloth ends the
   chain with `.toVarying()` — it is LOAD-BEARING.
2) One-sided forward-difference tangents give each vertex its upper-right
   QUAD's face normal; central differences (pos[c+1]-pos[c-1] etc., one-sided
   at edges, no sign flip) shade C1-smooth across quads.
Verified in motion: work/clothfix/test.js (panel drops on camera under a raking
spot, box collider) — before: hard banding; after: continuous fabric.
Diagnosis lesson: stills of RESTING cloth cannot show this bug; judge cloth
from frames DURING deformation.


## Blender 4.3.2 mirrored-UV geometry pipeline (verified, robot v3 build)

Empirical findings from work/liberate_ai_robot_v001 v3 geometry infra (all
probed headless on Blender 4.3.2, --factory-startup --background):

- `bpy.ops.uv.pack_islands` kwargs in 4.3.2: margin, margin_method,
  merge_overlap, pin, pin_method, rotate, rotate_method, scale, shape_method,
  udim_source. Works in multi-object edit mode with no UI. `scale=True`
  applies ONE uniform factor to all islands, so relative per-island priority
  scaling done beforehand survives packing.
- `bpy.ops.uv.average_islands_scale` kwargs: scale_uv, shear. Also fine
  headless in multi-object edit.
- Mirroring a mesh by applying a negative-determinant transform
  (`obj.matrix_world = Matrix.Scale(-1,4,X) @ src.matrix_world` +
  transform_apply) does NOT reverse loop winding: the mesh ends up inside-out
  and needs `mesh.flip_normals()`. After the flip, per-(face_index,
  vertex_index) UV correspondence with the source is EXACT (max delta 0.0) --
  the basis for perfectly stacked left/right mirror UV islands.
- Shrinkwrap-modifier-on-curve flattens the whole beveled tube onto the
  target surface (modifiers evaluate after curve geometry) -- to carve a
  panel-seam groove into a high-poly shell, conform the CONTROL POINTS via
  `evaluated_obj.closest_point_on_mesh()` first, then bevel the curve,
  convert with `bpy.data.meshes.new_from_object`, and boolean DIFFERENCE
  (EXACT). A 2.5mm groove bakes visibly in a 512px tangent-normal test.
- Collections with hide_viewport=True are excluded from depsgraph
  evaluation: build/evaluate HP sources while the collection is visible and
  hide it at the end.

## Reference-matched Bezier hard-surface humanoid (2026-07-16, Liberate AI robot v3)

- Lock the large front/side envelopes before adding panel detail. Orthographic
  contact sheets at the same scale as the references expose proportion drift
  much faster than a beauty render; check head width/depth, shoulder span,
  chest taper, pelvis width, limb rhythm, and foot projection in that order.
- Replace stacked boxes with two reusable continuous-form builders: closed
  4x4 tensor-product Bezier patches for compound torso/pelvis shells, and
  C1 Hermite/Catmull-resampled profile sweeps for limbs. Adjacent patches share
  exact boundary points, so their joins read as intentional manufactured seams
  instead of intersecting primitive layers.
- House every articulation. Nested same-radius collars, recessed hubs, bearing
  gaps, and crisp outer rims make elbows, shoulders, knees, wrists, and ankles
  read as mechanisms while preserving a clean humanoid silhouette.
- Use a shallow oblate head shell plus a closed wrapped Bezier visor instead of
  a sphere with a front plate. A continuous visor around the side planes is a
  high-value reference cue under moving rim light.
- Keep runtime topology where it controls highlight flow; put micro-seams,
  fasteners, grooves, and panel breaks on conformed high-poly sources and bake
  them. This build lands at 24,292 triangles with one mesh, one material, one
  4K atlas, one UV set, a 55-bone humanoid rig, and 54 exact mirrored UV pairs.
- Material normal strength must be authored per surface class before baking.
  Full-strength procedural grain made broad silver shells look corduroy;
  reducing silver to about 0.22-0.24 while retaining stronger graphite/rubber
  normals preserved satin highlights and surface distinction.
- Brand marks should be exact source art, sized from the reference, projected
  flush into the atlas, and validated under close-up lighting. Procedural logo
  approximations or floating geometry undo otherwise convincing modeling.
- VRM normalized bones are a proxy skeleton: after setting a custom pose, call
  `vrm.update(0)` before rendering so rotations reach the raw skinned bones.
  A one-frame probe can still report no temporal pose delta; judge the image,
  then require the full-run audit to show real bone movement.
- GOTCHA: monocular depth maps from sparse references are only loose volume


## Rig-QA: posing a Blender VRM humanoid via pose_bone.matrix world-axis ops (2026-07-16, rig_showcase)
- Pose-sheet scripting: define test poses as WORLD-axis rotations applied sequentially to the CURRENT pose (pivot at bone head): pbone.matrix = T(head) @ R @ T(head)^-1 @ pbone.matrix, view_layer.update() after each. No per-bone roll math needed; signs stay anatomically readable (vrm_rig convention: +Z up, -Y forward, +X avatar-left; hanging-limb forward flex = X-negative, knee flex = X-positive, finger curl toward palm = Z-negative left / Z-positive right; T-pose thumbs hang DOWN, so thumb opposition = X-negative sweep, NOT a Z swing).
- Auto-grounding bent-leg poses: drop = min over feet of (posed head/tail z - rest head/tail z); translate hips by -drop via matrix premultiply. Then a mesh-level pass: if evaluated-mesh min z < -4 mm, lift hips until the sole kisses Z=0 (skinned heel edges dip below the ankle-bone estimate).
- Blender 4.3 headless EEVEE Next renders fine for QA sheets; burn pose labels with render.use_stamp + use_stamp_note (disable all other stamp fields). Contact sheet = numpy over image.pixels (byte images round-trip gamma-safe: load PNG -> foreach_get, images.new(float_buffer=False) -> foreach_set -> save).
- Engine probe gotcha (eido --probe + T_OFFSET pattern): a mixer catch-up inside renderFrame needs an explicit vrm.update(0.001) afterward or the single probe frame renders the load-time T-pose (normalized-humanoid -> raw-bone propagation happens in the engine loop, not at mixer.update). The [vrm-pose] audit on a 1-frame probe always reports T-pose-statue; only the full render verdict counts.
- emote(vrm, ...) on a stationary VRM re-aims the standing emote (default facing) — a QA turntable that must keep the gesture on camera should pin vrm.scene.rotation.y after starting the emote.


## DAISY tandem hero prop (2026-09-23) — Opus 5.5 subagent (now eidoverse/props/tandem.js)

- Blender 5.2 headless hero asset → GLB, driven from three.js: build_tandem.py (tgeo/tparts/tmats) models the
  1896-pattern tandem part by part in a +X-travel / +Y-up / +Z-right "bike frame" (B() maps it to Blender Z-up;
  the glTF exporter maps it straight back). Pivot empties (steer, wheel_*, crank_*, pedal_*, seat_*, grip_*)
  with identity rotations spin about their local axes in JS; layout + chain belts ride in root extras
  (userData.daisy_tandem).
- BAKE SPEED: Cycles bakes every selected object in its own session (full scene sync each). 65 separate parts
  = 680 s for ONE 2k colour pass, GPU idle, one CPU core busy. Join per (pivot, atlas) BEFORE baking
  (carry per-part shader inputs as per-vertex attributes, read with Attribute GEOMETRY) → 26 s. Also
  margin_type='EXTEND'; smart-project only meshes without usable UVs (boolean casts, lofts) — sweeps,
  lathes and curve plates keep metric UVs and pack_islands separates UV-disconnected islands itself.
- Cast lugs = boolean union of socket "plugs" (spear points) + fillet + WEIGHTED_NORMAL (FACE_AREA,
  keep_sharp) applied → boolean seams stop smearing. Tubes stop at the joint centre inside the lug, uncapped.
- Spokes without motion blur strobe at 60 fps. Per-vertex `_TRAIL` flag (exported via export_attributes)
  + positionNode that swings trailing vertices back by wheel ω·shutter and opacity = wire/(wire + r·Δθ):
  crisp at rest, a silver haze at speed, one draw call.
- Block chain on the GPU: one-pitch link mesh instanced N times; vertex shader walks each instance round
  the belt (2 tangent runs + 2 arcs, setLayout'ed TSL fn) from one phase uniform; ring tooth phases are
  set at build time so blocks sit in gaps.
- Tools: fetch_hdri.py has NO --help — any argument is a search term and it OVERWRITES the repo-root
  hdri.hdr/hdri_b64.txt (restored from work/memory_of_water/assets/hdri_dusk.hdr, same bytes size).
  fetch_texture.py writes into the cwd: run it from the target folder. Deno scripts outside the repo pick up
  C:/Users/sdn52/package.json — use --no-config --no-lock.
- Rider rig on a vehicle: analytic two-bone IK on NORMALIZED humanoid bones in the VRM's own frame (parent
  vrm.scene to the seat; targets via vrm.scene.matrixWorld inverse, so scale 0.87 is free), then
  vrm.humanoid.update() before the render (the engine's post-render vrm.update() stays the only spring step).
  Frames: thigh/shin = frame-to-frame rotation (bone dir + hinge-side dir), hand = forearm dir pitched round
  the grip axis, wrist twist split half into the forearm. Measured: toe/wrist targets hit at 0.000 mm.
- Spring joints set bone.matrixAutoUpdate = false; releasing a joint (springBoneManager.deleteJoint) to pose it
  by hand needs matrixAutoUpdate = true again, or the quaternion writes never reach the skin.
- Spring pre-roll: after the first pose, springBoneManager.update(1/60) x120 in setup, or the mane/tie swing
  in from the T-pose on camera.
- mrtNode = mrt({normal: vec4(0), metalrough: vec4(0)}) on a LIT transparent material (spoke smear) fails
  to compile ('fragment' ShaderModule invalid); the scene MRT already weights aux attachments by alpha.
- ffmpeg 9.0 rejects -vsync: render_scene.mjs:3521's probe-frame extraction fails on this machine
  ("probe-frame extraction failed"); -fps_mode vfr is the replacement. Extract frames manually meanwhile.


## 2026-09-23 — DAISY corner/march set (now eidoverse/sets/corner.js): instancing gotchas on the WebGPU stack
- **Per-instance values read in the FRAGMENT stage came back different per fragment** (instancedBufferAttribute used in colorNode → speckled sign art). Resolve per-instance values in the vertex stage and pass them with `THREE.varying(...)` (e.g. the sign's atlas cell).
- **>8 vertex buffers silently drops the draw** ("The number of vertex buffers 9 exceeds the limit 8"): position+normal+uv + 3 rig attributes + 3 instance attributes vanished while a MeshBasic debug of the same mesh drew. Pack per-instance data into ONE `THREE.InstancedInterleavedBuffer(arr, stride, 1)` and read it with `instancedBufferAttribute(ib, 'vec4', stride, offset)`; a plain typed array/InterleavedBuffer here steps per VERTEX (exploded geometry). Pack rig channels into one vec3 attribute.
- **Canvas textures on glTF meshes**: sample with the mesh's own `uv()` (glTF v=0 = canvas top). Three-built PlaneGeometry needs `vec2(uv().x, 1 - uv().y)` when sampling a canvas with an explicit uv node.
- **NodeMaterial `.opacity` does not bind**: glass needs `opacityNode = float(op)`.
- **A frame that compiles many new pipelines lands one frame late** in the readback (black on a run's first frame, a repeated frame mid-run): a cut into never-seen materials arrives 1 frame late.

## 2026-09-23 — createFlora `daisy` species (eidoverse/vegetation_daisy_gen.js): what the build taught
- **Headless Blender with `--factory-startup` DELETES the user's extension wheels**: startup wheel-sync
  sees zero enabled extensions and removes `AppData/Roaming/Blender Foundation/Blender/5.2/extensions/
  .local/lib/python3.13/site-packages/*` (locked files end up in `.~stale~NNNN`). Isolate every headless
  run: `BLENDER_USER_RESOURCES=<scratch dir>` (the repository's `run_blender.sh` does this). A normal
  interactive start re-syncs the wheels of enabled extensions.
- **Card art without a bake cage**: model the high-poly pieces flat in "atlas space" and ortho-render
  emission passes (albedo / data / world normal / AO node) per region — exact values, AA alpha for free.
  Curved low-poly carriers (a domed disc, a cup seen from below) convert world normals to tangent space
  per pixel with the analytic frame T=∂P/∂u, B=∂P/∂v, N=outward (three's derivative TBN uses exactly that).
- **Per-vertex data past the 8-vertex-buffer ceiling**: a big instanced flora field already binds 8
  (position/normal/uv/aH + 3 instance attrs + the instanceMatrix buffer above 1024 instances). Extra
  per-vertex records go in `storage(StorageBufferAttribute, 'vec4', n).element(vertexIndex * k)` read in
  positionNode; anything the fragment needs leaves the vertex stage through `.toVarying()`.
- **N8AO default (5 m radius, x5) blackens small plants seen from behind** (a flower's own cup + stem read
  as deep occlusion). Flower-scale shots: `_aoParams = { aoRadius: 0.3, intensity: 2, distanceFalloff: 0.5 }`.
- **Far billboards sample the atlas's tiniest mips**: a sub-pixel impostor card takes its colour from the
  whole atlas neighbourhood. Put the impostor tile among same-colour art (here inside the white ray cells),
  or a far field of white flowers renders green from the neighbouring leaf windows.
- **Sky-facing flowers vanish at grazing distance** (petals and axis-facing cards go edge-on): the far LOD
  card must billboard toward the camera, sized ~0.75 of the head (the mean projected area of sky-facing
  heads) or the LOD band reads as a denser stripe.
- In these probes the sky_worlds dome rendered black under `_noAutoEnhance`, so lookdev kept auto-enhance
  with bloom/SSR zeroed (`_bloomParams`, `_ssrParams`). Separately, every run with makeSky logged one
  invalid 'fragment' ShaderModule (its WGSL has an empty `OutputType` struct) — cause not traced; the sky
  still drew with auto-enhance on.


## 2026-09-24 — DAISY era-2 voice machines: Blender hard-surface → baked GLB → eidoverse modules (now eidoverse/props/voice_machines/)

- Pipeline: `era_bkit.py` (now in `eidoverse/assets/models/voice_machines_src/`; headless Blender 5.2, run ONLY
  through `run_blender.sh`, which sandboxes BLENDER_USER_RESOURCES) models
  each machine as masses (profile prisms, lofts, EXACT booleans, angle-limited bevels), gives faces bake-source
  materials (AmbientCG scans box-projected in object space at real scale and tinted; AO-node grime broken up by a
  dirty-plastic scan; pointiness edge wear; noise + up-facing yellowing; PIL-drawn labels/logos projected by empties
  with facing + depth masks), bakes colour (2048) and roughness/normal/AO (1024) on the CPU, and exports one GLB.
  Modules load it with `Deno.readFile(new URL('./assets/x.glb', import.meta.url))` + `GLTFLoader().parseAsync` and
  rebuild `MeshStandardNodeMaterial`s from the baked maps. Named objects carry runtime roles: `screen_*`, `led_*`,
  `glow_*` (voice-lit), `metal_*`.
- Custom normals survive booleans and get interpolated across the sliver triangles a cut leaves on a flat face →
  fan-shaped streaks. Keep `harden_normals` off in intermediate bevels; at the end clear custom split normals,
  shade smooth by angle, then set exactly flat corner normals on coplanar regions larger than ~1 cm². A weighted-
  normal modifier does not fix it after booleans, because the flat face is now many small slivers.
- Several overlapping cutters joined into one operand need `use_self=True` on the EXACT boolean, or the target can
  silently come back empty (a whole shell vanished). Log vertex counts per boolean.
- A fine post-boolean bevel on dense vent geometry can explode a handful of vertices to ±4e6 m. Snapshot the mesh,
  compare bounds after the bevel, restore and retry gentler.
- Dished keycap tops made by stacked `inset_region` calls fold along a diagonal (obvious in the baked normal/AO maps,
  a light/dark half on every key in the render). Build the dish as concentric scaled rings down to a centre vertex.
- three's ACES multiplies by exposure/0.6 before the curve: emissive screen colours land ~1.7× brighter and paler
  (the C64 light blue turned lavender). Pre-compensate the screen gain and keep spotlit CRT glass dark.
- The native CanvasTexture shim flips through repeat/offset; `texture(tex, customUV)` skips the texture matrix, so
  sample (u, 1 − v) yourself. Auto-mips sample zero at non-base levels; upload CPU mip chains as `texture.mipmaps`
  (the Mac's 1-bit 50 % desktop then minifies to grey instead of moiré).
- Black/smoked gloss plastic under a spotlight turns a scan's micro-variation into glitter (the Speak & Spell band
  sparkled with texmix 0.2, bump 0.1, roughness 0.10-0.20). For dark gloss: texmix <= 0.05, bump <= 0.03 and a
  roughness band only ~0.06 wide; the highlight then reads as one soft smoked-plastic sheen.
- NEVER bake the normal pass at 1 sample. A scan bump finer than a texel gets point-sampled into per-texel white
  noise (mean tilt 4-6 deg, p90 10 deg): every beige plastic read as granite/terrazzo under a grazing key. Cycles
  bakes jitter inside the texel per sample, so 16 samples average it to texel-scale relief (seconds per map); the
  GLBs also shrank (desktop 14.3 -> 11.9 MB, the noise was incompressible).
- GOTCHA: `blender --background --factory-startup` against the REAL user folder syncs extensions to an empty
  enabled set and deletes Skye's installed extension packages. Every headless run goes through run_blender.sh.
- Bright printed yellow under a hot key: ACES's input matrix feeds ~0.13·G into blue and the shoulder desaturates,
  so a (237,209,21) print rendered pale butter (229,210,88). Match printed colours to a reference photo at the SAME
  red exposure: a deeper golden print (230,192,0) rendered (221,194,62) against the photo's (222,197,48).

## 2026-09-24 — DAISY: dressing the claudesona (now eidoverse/claudesona_wardrobe.js, claudesona_face.js, sun_corona.js) — Opus 5.5
One VRM carries every outfit as hidden layers (`eidoverse/assets/vrms/claude_suit_wardrobe.vrm`; guide: AGENTS.md, "Outfits").
- **Hats on a flower head = game "hat hair".** Fold the crown petals down the back and shorten them. They're spring
  bones, so write the fold into each chain's REST pose: set the root joint's quaternion (and scale), `updateMatrix()`,
  then `joint.setInitState()` for every joint in the chain; the springs keep moving around the new rest. Restore the
  stored originals the same way when the hat comes off.
- **VRM 1.0 two-node spring chains have ONE joint.** The last node is only the tail, so a chain's tip is
  `joint.child`. Taking "the last joint" as the tip gives a zero direction → `setFromAxisAngle` with a zero axis → a
  NON-UNIT quaternion that silently scales the bone.
- **Per-part colour on a skinned mesh:** derive a part id per vertex from its dominant skin bone and write per-vertex
  COLOURS. A float id attribute interpolates across seam triangles and `int()` lands on wrong parts (jagged rings).
- **MToonNodeMaterial has `shadeColorNode`.** A procedural `colorNode` pattern vanishes in the shade (flat
  `shadeColorFactor`) unless the shade gets the pattern too. Outline passes are separate materials ('X (Outline)'):
  darken their `outlineColorFactor` with dark paints, or black cloth gets brown piping.
- **On a textured garment, `m.color` multiplies the print** (the cyclist stripes ghosted through black paint). Put
  the paint in `colorNode`; the normal map keeps the knit. Memoize pattern nodes per (material, spec) so re-wearing
  an outfit reuses its compiled pipelines.
- **A grey parametric rim washes out small dark accessories** (a deep green bow tie read mint, black acetate read
  silver). Accessories get rim 0.
- **A garment made by pushing verts out along normals cracks at split seams.** Skin shows through as coloured
  lines on dark paint. Wear the source garment underneath, painted to match.
- **Face emotion without an animation rig:** key the cues to the LYRICS (regex on caption text) plus a per-section
  base, blended with smoothsteps and max-merged into the lipsync plate dict. Re-timing the song never desyncs a feeling.
- **The earth sky reuses its directional light for the moon after dusk.** Anything tied to the sun must read the true
  direction: `sky.sunDir` / `sky.moonDir` (getters added to eidoverse/sky_worlds.js).
- **Spoken lines in a sung arrangement:** place each by its SPEECH onset (TTS renders carry ~0.2 s lead-in), chain
  them end → start with a breath, and assert they end before the next hard event (an eruption, a verse downbeat).
  Measure: whole-caption spans overlapped by up to 3 s before the fix. Sound captions ("(humming)") get their own
  top lane so the words stay in the bottom lane.

## 2026-09-24 — hand-authored VRMA performance clips from Blender (the claudesona; now eidoverse/assets/animations/ + performance_src/) — Opus 5.5 subagent

- **Blender → VRMA works headless.** Use `bpy.ops.export_scene.vrma(filepath=..., armature_object_name=...)` from
  the VRM add-on (4.4.0, Blender 5.2). Set `vrm1.humanoid.pose = 'restPositionPose'` first, so the exporter's
  T-pose reference is the rig's own rest pose, which is the same pose three-vrm normalizes. The exporter samples
  EVERY frame from `frame_start` to `frame_end` at the scene fps through `apply_pose_from_action`, so dense per-frame
  keys (LINEAR) are the exact data you get. Every humanoid bone gets a channel (fingers included), so key relaxed
  fingers or the hands export as T-pose paddles. The hips translation is ABSOLUTE; three-vrm scales it by the
  hips-height ratio.
- **Choose the fps so beats are whole frames.** At 128 BPM, 64 fps gives exactly 30 frames a beat. A loop of N beats
  then ends on the sample it starts on, and its seam is 0.000°.
- **Author in the normalized frame (x = her left, y = up, z = forward).** For each bone,
  `q_blender_basis = Rrest⁻¹ · N · Rrest`, with the axis map (x, y, z)three → (x, −z, y)blender. This is exact, and
  a pose written this way can be tested in the engine by setting `getNormalizedBoneNode(...).quaternion` directly.
- **Arms: IK keys, not joint angles.**
  - A key = palm-surface point, palm normal, finger direction, elbow pole.
  - The upper arm's twist comes from aligning the elbow hinge with the pole.
  - Split the remaining twist onto the forearm (pronation/supination, ±110° clamp) and leave the wrist the swing.
  - Print elbow flexion, forearm twist and wrist swing for every key: a >60° wrist in an in-between key reads as
    a "pledge hand" for a few frames. The fix is to point the fingers along the forearm mid-flight.
- **Legs: IK every frame on one shared stance.** Every clip plants the same foot marks, so crossfading between any
  two clips never slides the feet. Knee flexion is very sensitive near full extension: a 1.8 cm hips drop gave
  22–28° knees. Watch the reach (> 0.999 = the foot lifts off its mark).
- **Interpolate in rotation-vector space relative to the base pose.** Use an auto-clamped cubic Hermite (flat at
  extremes, flowing through breakdowns), periodic for loops.
- **Overlap by per-chain time lag.** On one-shots, FADE THE LAG OUT over the last beat, or the lagged bones are still
  moving when the clip clamps.
- **Hold loops start exactly on the one-shot's last frame.** Give the loop a flat copy of its first key before the
  wrap, because lagged bones read the tail at frame 0. Breathe with sin² (zero value AND zero velocity at t = 0). A
  sin breath starts at full speed and kicks visibly at a hard cut. Measured by frame diffs: 0.05 → 0.25 jump with
  sin, smooth with sin².
- **Mirror at the pose-spec level, not the baked curves.** Swap the arms with x negated, flip torso/hips turn and
  tilt, and swap which heel peels, but KEEP the stance.
- **Verify the artifact, not the intent.** Run FK on the .vrma's own rest nodes (glTF quats are x,y,z,w; take the
  angle between quats with atan2, because arccos near 1 turns float32 norm error into a fake 0.05° seam).
  Then draw motion trails, one dot per film frame for the hands, fingertips, head and hips, front and side: arcs
  read as curves, spacing as dot density. A gesture that "slides" shows as a flat band; re-key it as an ellipse.
- **A probe or tool script MUST register its renderer as `globalThis._r`.** Otherwise the runner doesn't own three's
  NodeFrame clock, frame-scoped nodes (skinning) advance on the wall-clock RAF, and a character rendered faster than
  ~60 fps moves at half rate. Frame diffs alternate 1.7 / 0.03, which is the tell. Split-viewport tools also set
  `_noAutoEnhance`, and set `renderer.autoClear = false` with one `clear()` per frame, then setViewport/setScissor
  per camera.
- **digi's rest thumb points INTO the palm** (≈ 45° toward the fingers, −68 % palm-ward). A relaxed hand needs the
  thumb "closed" ~44° about `thumbDir × fingerDir` so it lies along the index. An "opposition" rotation about the
  finger axis makes it worse.
- **The claudesona's flower sets the arm vocabulary.** The petal ring is radius ~0.45 m round the face, and the lower
  petals droop over the chest to ~0.23 m in front of it.
  - Raised hands go beside the ring (≥ 10 cm outside) and in front of its plane.
  - A hand on the heart rests IN FRONT of the lower petal (palm z ≈ 0.235 at chest height), never under it.
  - The upper arms and forearms carry spring colliders and push the petals; the hands don't.

## DAISY integration (2026-09-24): conducting a many-set music video on one timeline
- **Graphics modules and the canvas shim.** In the engine, `document.createElement('canvas')` returns the
  HTMLCanvasShim wrapper, and @napi-rs Skia's `drawImage` rejects it ("Value is non of these types CanvasElement,
  SVGCanvas, Image"). A 2D module that builds sprite canvases through the DOM works in a napi-only preview and fails
  in a scene. Create sprite canvases with `createCanvas` from `npm:@napi-rs/canvas`; as a scene-side workaround,
  hide `globalThis.document` around the (synchronous) draw call so the module's own napi fallback runs.
- **N8AO is live per frame.** `globalThis._n8ao.configuration.{aoRadius,intensity,distanceFalloff}` sync every frame,
  so one film can switch AO scale per set (0.3 m for flower-scale daisies, 0.8 m for rooms) without a rebuild.
- **Several effects in one chain.** With more than one effect, `applyTo(...).uniforms` is keyed by effect name
  (`_fx.uniforms.daisy_era.glitch`). A set's own effects (depth_fog, godrays) are applied in setup and zeroed by
  `opacity` outside its section. GodraysNode samples the light's shadow map at graph build: keep that set visible
  through the engine's one-frame shadow pre-render at the end of setup.
- **Lights that appear recompile everything.** A light whose visibility toggles mid-film changes the lights hash and
  rebuilds every visible material. Keep scene-wide helper lights (a face fill, a phone glow) always present at
  intensity 0.
- **A VRM on a vehicle rig, then back on clips.** While an IK rig owns her (the tandem's poseRider), stop the mixer
  (`rec.mixer.stopAllAction()`) so `vrm.update()` steps the springs on the rider pose. To hand her back, re-add
  `vrm.scene` to the scene and start the next clip with no fade.
- **Switching clips without a skipped step.** The engine snapshots each `_vrmMixers` record's time before
  `renderFrame`; replacing the record inside `renderFrame` (as `playVRMAFromBase64` does) skips that frame's mixer
  step. Parse clips once, `mixer.clipAction(clip)` them, and mutate `rec.action` in place. Lock loops to the song:
  `action.time = (t - main_t0) mod clip.duration`.
- **Probe only what the range touches.** Building every set costs ~25 s; a conductor that builds only the sets whose
  sections overlap `T_OFFSET .. T_OFFSET + duration` (plus a "stills" mode that renders K frames at each listed film
  time) turns a probe into a few seconds of setup.
- **Intermittent black render.** Rarely the post chain fails validation (`ShaderModule with 'fragment_RTT' label is
  invalid`) and every frame is black; the same config renders fine on a re-run. Check logs for it before delivering.

## 2026-09-24 — DAISY graphic-arts post looks (now eidoverse/era_looks.js; the film's march2026, vigil2025, ocean2026, crt1982 and sydney2023 presets are poster_night, candle_film, watercolor_night, crt_8bit and crt there) — Opus 5.5 subagent
- **Put print and paint looks in display space.** A color hook gets linear HDR before tone mapping. Paper and ink
  colours land on screen as authored if the hook maps the scene through three's own
  `acesFilmicToneMapping(c, toneMappingExposure)` and hands the result back through its exact inverse: solve the RRT
  fit's quadratic per channel and invert both matrices on the CPU. three r184's TSL fit divides by
  `c * ((c + 0.4329510) * 0.983729)`, so the inverse's linear term is `0.4329510 * 0.983729`. The Hill constant
  is off by up to 0.4%.
- **WGSL rejects constant u32 overflow.** `uint(a).mul(uint(b))` with two constants whose product exceeds 2^32 fails
  Naga ("multiplication operation overflowed"), and the whole post chain renders black (`fragment_RTT ... is invalid`).
  Mix constant salts on the CPU (`Math.imul(...) >>> 0`). The black render in the integration entry above
  (probes/stills_v1b.log, 02:36) was era_fx.js mid-edit with this bug. It was not intermittent.
- **Gated mip blurs cost nothing when off.** three's BloomNode with threshold −1 is a half-res Gaussian pyramid
  (σ ≈ 4, 14 and 39 px at 1080p; `_textureNodeBlurN`). Wrap its `updateBefore` to return early while no look reads it.
  Only `getTextureNode()` pulls the node into the graph, not the level textures, so sample it at least once.
- **Persistence without ghosts at cuts.** AfterImageNode computes max(new, old × damp). Zero damp for one frame
  when the effect turns on and when the camera jumps (more than 0.6 m or 10°). Check the camera at composite time:
  another render in the frame, such as an env bake, can run the pipeline before the scene's update().
- **Benchmark post as throughput.** On this stack `onSubmittedWorkDone` carries ~13 ms of fixed latency, so timing
  single frames hides GPU cost. Submit N frames and wait once. Tick `renderer._nodes.nodeFrame.update()` per render,
  as the engine does per encoded frame. Without the tick, FRAME-scoped passes (scene, AO, bloom) are skipped and the
  numbers are fiction.
- **An env bake renders the whole post pipeline.** `sky.bakeEnv()` inside renderFrame runs the patched renderAsync
  at that frame's node-frame id, and the frame shows that render. Set the camera before baking.
- **Toon ink that keeps a flower field painted.** Ink only the near side of a depth step. Drop lines where both
  sides are farther at 3× the tap radius; that catches shapes thinner than ~7 px, like petals and stems. Draw colour
  lines only from steps, never from light ridges.

## 2026-09-24 — moving a film's props and sets into the library (DAISY → eidoverse/props, eidoverse/sets) — Opus 5.5 subagent
- **Pack exactly what the module reads.** Deno's fs functions are writable on 2.8: wrap `readFile(Sync)`,
  `readTextFile(Sync)`, `stat(Sync)`, `readDir(Sync)` and napi `GlobalFonts.registerFromPath`, build the ORIGINAL module,
  drive `update`/`camera`/`markAt` across its whole section, and log every path (the local, git-ignored
  work/lib_check/trace_hook.js did this). Copy only
  those files. Then trace the ported module the same way: zero reads under `work/` and the identical relative file list
  (including the failed optional stats, e.g. a missing `_AmbientOcclusion`) prove the port. Dynamic `import()` of sibling
  modules does not go through these calls; grep for them.
- **Resolve a pack from `import.meta.url`, not the cwd.** Deno fs calls take a URL object, but code that concatenates
  path strings (and `registerFromPath`) needs a filesystem path:
  `fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; }`.
- **three r184 double-counts CPU mip chains in `renderer.info.memory.texturesSize`.** For a texture whose `mipmaps[0]` is
  the base image (the CPU-mipped canvases and GLB maps here) `_getTextureMemorySize` adds the base twice (≈2.33× base
  instead of 1.33×). Subtract `mipmaps[0].data.byteLength` per texture in `info.memoryMap` for the real footprint.
- **Per-pack GPU cost:** 30 renders back to back (tick `renderer._nodes.nodeFrame.update()` each) and one
  `GPU_DEVICE.queue.onSubmittedWorkDone()`. The empty-scene baseline with the default post chain at 1080p on the RTX 5090
  Laptop is 2.1 ms, 28 draw calls and 283 MB of render targets; subtract it. The numbers are in docs/props-and-sets.md.
- **Blender scripts that derive paths from `__file__`** (`HERE/..` as their root) only rebuild in the layout they were
  written in: document that layout and rebuild in a copy of it under `work/`. Replace a hard-coded repo path with a walk
  up to the folder holding `eido.py`. A scratch rebuild of the funeral crowd from the library copy matched size,
  triangles and rig JSON (not bytes).
