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
  5s RMS envelope buckets (vocal stem vs full mix); replacing a 120s draft
  with a 159.3s Suno track was a table edit. Jaws/machinery ride the two envelopes; her visemes from
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

## softrains — There Will Come Soft Mornings (2026-08-05)
- MMD-heritage VRM hand-bone frames: +Y along the arm toward fingertips, +Z = palm normal.
  Prop-in-hand grip = attach to raw hand bone, then iterate local offset via close-up probe
  renders (identity attach first to READ the frame, then rotate/offset). claude_suit right
  hand grip for a watering can: pos (0,0.10,0.22), rot Euler(-1.05,0,0) in bone space.
- fluid_swe at prop scale (planter box): keep the domain INSIDE the vessel dish only — a bed
  cliff at the rim makes the heightfield surface draw a tall vertical skirt that reads as a
  phantom waterfall. sprayMax: 0 at cm scale (whitewater needles blow up in 5mm cells).
  Stream tube keeps its last arc after rate→0: set streamMesh.visible = pouring, AFTER syncRenderPhase.
- ParticleMorph.fromMesh on low-poly primitives collapses to vertex rings — hand-sample
  parametric surfaces (cylinder/cone/fins) into fromPoints for a crisp shape.
- Controller 'reach' emote = arms out to the SIDES; aim the RIGHT hand at a work target by
  setting _emoteFacingY 90° CCW of the target bearing. Emotes are one-shot: re-trigger
  playEmote every ~2.5s to hold an engaged pose. loadEmote() at setup or playEmote no-ops.
- grass2 createFlora clipFn strips double as prop stages: anything meant to be SEEN at ground
  level (a crow, a small bot) must stand inside a cleared strip or the turf swallows it.
- Weather sunshower + sky day-cycle: drive sky.setTime per frame from a piecewise knot table,
  re-applyToLights every frame, transitions guarded with a probe catch-up branch (T_OFFSET
  fires transitions late: if t already past the window end, setWeather directly).

## sunflower_sol - Surgical disc trim-sheet PBR update (2026-08-12)
- For a pixel-locked atlas edit, define one inclusive integer mask and hash decoded row-major
  RGBA outside it before painting. Start every output from a byte-for-byte decoded copy, write
  only masked pixels, re-decode the saved PNGs, and require the outside hashes to match.
- A high-resolution head-on botanical source can be fitted to exact radial anatomy with a
  piecewise radial remap (seed field -> gold ring -> dried band), then supersampled into the
  atlas. Clamp the rim to textured source radii and opaque warm underpaint so no source
  background leaks onto a geometry silhouette.
- Derive microrelief normals from band-passed albedo rather than raw luminance: small-minus-
  large local structure preserves seed/floret grooves without turning a bright radial ring
  into one broad fake ridge. Clamp neighbor reads at the circular mask edge and use the
  y-down image derivative sign appropriate for an OpenGL normal map.

## THE SHAPE THE WATER LEFT (work/erosion, 2026-08-13) — Fable Arroyo

**Hydraulic erosion for fluid_swe (now an engine feature, opt-in `erosion:{}`):**
one extra ping-pong pair (R bed-delta, G suspended sediment, B silt age);
stream-power capacity |v|^1.7 with SATURATING depth term (linear-|v| erodes a
maze, saturation is what widens a wash); BANK erosion = neighbour stream power
× exposed face height (without lateral pickup, depth is the only degree of
freedom → slot canyons); talus at wet repose 0.55; the pristine bedTex never
mutates — live bed = bedTex + delta everywhere. Eroding terrain-patch mesh via
storage-buffer displacement; cut/silt/wet fragment tints carry the read as
much as relief does. `rainRate` + `setRain()` = squall-banded distributed
rainfall (the natural wash source; a jet pour reads as a garden hose).
**Scene craft that made it READ:** damp your dune noise inside the domain and
add a valley cross-fall or rain pools instead of channelizing; deep carving
needs a LOW GRAZING finale camera (drone angles compress relief); tint
contrast (cut '#4e3a24' vs silt '#a88a5e') outsells pure shading at distance.
**The patch material must BE the ground material:** flush heights are not
enough — albedo+rough without the NORMAL map leaves the patch glass-smooth
beside a normal-mapped world (the pebble relief IS the normal map), and
patch-local uvs restart the texture phase at the rim; either way the domain
prints as a square of "different texture". `terrainMaps` takes all three and
`terrainTexPeriod` (= static ground size/repeat, metres per tile) WORLD-locks
the patch uvs to the same fract phase, so the pattern continues across the
rim and the seam is impossible by construction.
**In-world text earns its place only if a shot can resolve it:** the survey
log is 9 short lines at 40 px on a 484 px canvas AND owns a dedicated close-up
(camera ~1.6 m out along the facet normal → type ~50 screen px at 1080p).
Diegetic text no shot can read is set dressing pretending to be writing.

**MiniMax Music 3 (comfy_bridge):** `max_duration` is a WALL the model happily
composes past — set the ceiling well ABOVE the intended piece and write an
explicit natural ending into the arrangement ("finishes naturally around Ns…
must complete its final cadence"); v3 ended itself at 132.4s under a 150 wall
after two truncated attempts. Master with softclip+headroom (−0.9dB, peaks
came in at 0.0 dBFS = AAC crunch) + fades. RMS cadence-finder fallback:
scan the tail for the last quiet trough and cut+fade there.

**claude_suit lipsync on THIS engine:** the VRM path runs combineMorphs — the
raw 'show MMD mouth' recipe finds ZERO plates; runtime morph dictionaries are
expression-named (aa/ee/ih/oh/ou). Drive those directly via
morphTargetInfluences in onBeforeRender (fill(0) first — then RE-ADD blink
yourself), winner-take-all with EMA ~3 frames. ⚠ Combined-morph weights CLAMP
at 1.0: past it the mouth plate EXTRAPOLATES forward off the face (visible
from the side) — the >1 punch idiom belongs to the raw-morph pipeline only.
Gate visemes to align_lyrics windows ±0.12s or demucs bleed sings the
instrumentals.

**Controller on shaped ground:** a displaced walk strip MUST declare
`userData.trimeshCollider = true` — the default bbox cuboid is an invisible
plateau at the strip's high corner (the tall-AABB bug's third appearance).
Real mixer + startPosition in opts; never hand-set the root.

**Overlay layer:** title/end cards + a ticker (canvas cut to exact phrase
width, repeat.x = (frameW/barH)·(64/pw), offset.x scroll) composite between
world FX and signal FX exactly as documented. document.createElement('canvas')
(napi shim) — OffscreenCanvas doesn't exist here; run `deno install` on fresh
machines or every canvas texture is silently black.

## 2026-09-05 — Astra / A Room Made of Replies

Working production: `work/astra_replies/`. Shared tools unchanged; experiments
are separate files. Full notes: `production_feedback.md` in that directory.

- Couple delta-printer axis motion and deposited bead reveal to one arc-length
  cursor. `path_print.js` slices actual contours and infill; nonextruding travel
  remains explicit. A single solid takes over on completion.
- Preserve Omnitron's measured pivots and map sets in a detached GLB. Use a
  calibrated tool frame/aperture, constrained pose IK and unwrapped periodic
  angles. Export real scene geometry and sweep the arm AND attached payload;
  reachable tool targets and coarse proxies can miss wrist/rod contacts.
- Model clearance in the scene: a hinged printer frame and a side-fed rain
  pipe leave the manipulation volume open. Union a receiver with its spillway,
  then cut the actual outlet, rather than overlapping a capped chute and rim.
- Small-vessel SWE: log quantized atomic drop volume and per-cell depth. A
  0.4 mL drop rounds to zero at a 1e6 fixed-point scale. A fractional source
  budget avoids tying flow rate to an assumed particle life cycle.
- A 128×128 closed-cup GPU probe lost substantial volume in float16 state
  during redistribution. Float32 state with nearest sampling retained volume
  to about 1e-6 L over ten seconds; a warmed-up 8 L pour returned 8 L after
  settling. See `water_probe.mjs` and its report. Keep broader regression work
  separate from this production evidence.
- Rooted foliage growth can wrap the vegetation brush's GPU position node:
  scale the displacement from `aPosRot.xyz`, retaining placement, wind and
  authored materials. Explicit placements avoid empty tiny random stands.
- Map the editorial timeline to music cues instead of stretching the score.
  Check collisions again at the final resampled frame times. Keep the full
  supplied track and finish on the next complete video frame.
- Synthesize motor foley from the exported print cursor and planned joint
  velocities on that same clock. Give jaws and hinges their own envelopes;
  verify silence during stationary holds. Keep generated water/garden recordings
  as separate, crossfaded beds. Working implementation: `motion_sfx.py`.


## Modular robotics foundation, permissive source intake, and native checks — Astra, 2026-09-05

Working implementation: `work/modular_robotics/README.md`; evidence and native
5-second 1280x720/24fps clip are in its `checks/` directory. Existing tool
implementations are unchanged. A separate MIT-scoped original module library
has 14 Blender-authored parts, shared packed PBR maps, full-frame attachment,
typed joints, bounded full-pose IK and quintic rest-to-rest trajectories.
Joint/pose guards explicitly permit named mating surfaces. The demonstration
sweep checked 121 poses and 18 colliders; these discrete surface checks are not
a continuous or containment collision proof.

For efficient material baking, join a single global atlas while retaining
module vertex-ownership groups, bake once per channel, then separate the rigid
parts again. Pack image dependencies into the editable Blender files. Native
procedural environment textures used Uint16 half-float data; Float32 produced
an incorrect color cast on this installed stack. The generic motion audit
misidentifies the moving center of an articulated chain as a displaced base
pivot; the actual pivot has zero drift in the recorded sweep. Avoid suppressing
the whole hierarchy. See `TOOL_FEEDBACK.md` for follow-up improvements.

Platform source intake must preserve per-model licenses, revisions and hashes.
The Menagerie UR5e source is staged under BSD-3-Clause, with all 20 mesh
references resolved, but is not yet a runtime import. Restrictive or unclear
assets are excluded from the open package across all sources, including Isaac
Sim. Omnitron remains a local owner-authorized reference without copied source
assets. General mechanical principles from public references can inform fresh
geometry. `PLATFORM_SOURCES.md` records the licensing and importer plan.

## Common Tools: original modular workshop and process-driven fabrication — Astra, 2026-09-05

Staged production: `work/common_tools/`. An 80.29-second 1080p24 film with an
original synthesized score and motion-derived mechanism sounds; a browser
inspector also demonstrates 106.94 seconds of continuous-wall printing.

24 new original Blender modules extend the earlier original robotics foundation.
The compact wrist solved reach/clearance failures; full-frame tool ports support
gripper, spindle and side-fed hotend. The vise grips orthogonal to the robot's
jaws, avoiding competing contact spaces. The billet is seated and withdrawn
vertically before lateral travel. Cutter flutes are a separate rotating mesh.

The machining path is the single authority for axis positions and stock sweeps.
Feed lookahead and small circular blends bound acceleration; a height field at
0.125 mm spacing resolves the cut. Printing uses the same path clock to reveal
an elliptical bead up to the nozzle, consume filament, and rotate the spool.
The CNC section is explicitly labeled 5×; handling and inspector printing retain
their actual motion time. The machining core rejects engaged diagonal Z ramps.

Verification: 3,212 mesh/containment clearance samples at 25 ms, with explicit
guide/bearing/support and state-dependent payload contact permissions; 16,057
joint derivative samples at 5 ms; independent known-volume, acceleration,
continuity, timestep-independence and nozzle-end checks. These are sampled
geometry and kinematics, not a continuous collision or rigid-body simulation.

Surface pipeline: ambientCG Metal009 CC0 inputs, original layered Blender
materials using curvature wear and local AO, unique shared 2k UV atlas, packed
PBR exports, and editable packed source/baked .blend files. Distribution contains
only original MIT geometry/code/art and CC0 material inputs; no Omnitron,
commercial platform or Isaac Sim source assets. Existing Eidoverse licensing is
unchanged and its engine files were not edited.

Rendering lessons: tune N8AO radius to mechanical scale (35 mm here), use
half-float studio environment data, and load native image textures with
`loadImageTexture`. Manual `makeScreen` updates after the scene clock keep
nonsequential probes synchronized. Probe montages can trigger camera-bounce
heuristics despite smooth individual shots. Hidden base/floor support faces
produce coplanarity warnings requiring inspection. Automatic frame extraction
still fails on this installation; direct FFmpeg extraction is the working path.
Native material-copy bug: Three r184 node material cloning retained nodes but
lost ordinary PBR color, maps, and metalness. `material_tools.js` explicitly
preserves those fields; `check_materials.mjs` reproduces and checks the fix.
Detailed implementation feedback: `work/common_tools/TOOL_FEEDBACK.md`.

## Deno 2.9.5 effects-path check and WSL rendering — Fable, 2026-09-12

- The old 2.8.1 pin ("2.9.x corrupts the effects path") did not reproduce.
  `work/nightshift/fxtest/fx.js` (five spheres, fogged wall, shadowed spot,
  full auto-enhance N8AO/SSR/bloom/FXAA plus the `depth_fog` TSL effect)
  rendered on Windows deno 2.8.1 and WSL deno 2.9.5: same tone-step profile
  down the wall and floor gradients (max 3 levels/pixel on the wall), SSIM
  0.98 between them, no banding on either. The 2.8.1 frame showed the
  rectangular SSR/AO patches on the wall; 2.9.5 was the cleaner of the two.
  Docs and `eido.py doctor` now accept 2.8.x and 2.9.x.
- Rendering from WSL on a `/mnt/c` checkout works (Vulkan adapter, RTX 5090)
  but the static ffmpeg there has no nvenc: `RENDER_CODEC=libx264`. ComfyUI
  on the Windows host is not reachable from WSL as 127.0.0.1 — run the
  music/SFX generators from the Windows side.
- Deno rewrites `node_modules/.bin` per OS. After a WSL run the Windows deno
  fails with `os error 1920` on `.bin/ot`; `rm -rf node_modules/.bin` fixes it.
- `fetch_model.py` crashes on Windows consoles with a cp1252 `UnicodeEncodeError`
  (it prints an arrow glyph); set `PYTHONIOENCODING=utf-8` (or `PYTHONUTF8=1`)
  before calling it.


## Manufacturing surfaces and live feed — Astra, 2026-09-13

- `fdm_plate` and `cnc_plate` are independently loadable kit modules with a
  shared 512 x 1024 material set. The inspector preserves rectangular map
  aspect in its image and UV overlay. Keep those authored UVs on extraction.
- The FDM build surface belongs to the machine. Disposing a print job removes
  its deposition, leaving the shared plate intact. Its actual 6 mm height sets
  the default first-layer datum; use `buildPlate:false` with an explicitly
  seated custom fixture when changing the surface.
- The G430's milky PTFE wall encloses an opaque filament core. They share three
  cubic control curves and move through uniforms without vertex uploads.
  Match their endpoint tangents to the actual fitting bores, and include both
  connection contact and free-span clearance in visual/motion review.
- GPU stock readback and rewind probes distinguish actual material removal
  from a plausible still image. This CNC implementation uses a flat-end cutter
  and 2.5D stock; it does not provide rotary or undercut machining.


## Removable sheets, supported tubing and relief stock - September 13

- The accepted FDM surface datum is the original bed plus a 0.65 mm removable
  PEI sheet. The sheet covers that bed and has accessible pull tabs.
- A frame-mounted guide and shared push fittings support the 1.34 m PTFE route.
  Straight insertion spans preserve clearance through the full fitting length;
  a tangent at the endpoint alone does not establish that clearance.
- The CNC T-slot table and toe clamps are reusable machine components. Dispose
  of process stock and debris separately from the machine's shared hardware.
- `cnc_relief` and `FabSim.carve` accept functions, heightfields or mesh envelopes.
  Ball compensation, successive roughing and a finishing raster use a vertical
  three-axis tool. Stock removal evaluates the swept cutter along full XYZ moves.
- Filter curved stock normals at its grid sampling scale; unresolved scallop
  normals can alias into false wide stripes. Increase stock resolution when
  individual scallops need geometric detail. Keep abrupt cut walls distinct.


## Indexed rotary stock and short direct feed - September 14

- Load `cnc_rotary` for XYZ plus A-axis carving around stock. The separate
  `rotary_fixture` supplies the existing drive, new saddle, four-jaw chuck and
  live-centre tailstock. `cnc` and `cnc_relief` keep their respective pocket and
  top-down relief processes. Use `FabSim.rotaryCarve` with an initialized renderer.
- Rotary stock uses a tiled GPU distance field, swept ball-tool subtraction,
  trilinear sampling and actual fragment depth. It is not a heightfield turned
  sideways. A radius function about the stock axis defines the target; this
  indexed four-axis planner does not provide arbitrary undercut mesh CAM.
  Retract beyond the rectangular block's corners before indexing. Preserve the
  calibrated fixture and end tabs; final part-off is a separate operation.
- Keep Three's settled renderer initialization promise intact. Clearing
  `_initPromise` after scene setup caused the offline clock guard to initialize
  it again. Instrumentation found replaced texture/attribute managers while
  backend resources still referred to the first initialization. Stock rendered
  into during setup failed on subsequent target reuse; cleanup also failed.
  Awaiting without clearing that promise fixes this lifetime error.
- Compare actual stock-buffer readback through forward AND backward seek on
  native WebGPU and the browser fallback. At 128 x 48 x 48, all 294,912 voxels
  at five checkpoints agreed with an independent swept-cutter calculation
  within 6 micrometres; the measured maxima were 1.95 and 4.12 micrometres.
  This is a numerical field check, not a statement of physical machining accuracy.
- Debris comes from first material engagement, sampled once during setup.
  Repeated cuts and air moves add no chips. Keep stock discretization separate
  from the coarser emission-volume estimate. Wood/plywood and metal use their
  corresponding finish, feed and chip presets.
- The FDM uses an exposed span between short seated PTFE entries: 30 mm at
  the rail-mounted carrier, 96 mm at the head. The strands, translucent wall
  and colored core update through curve uniforms. Preserve the accepted
  0.65 mm removable PEI sheet on the original bed.
- Payout begins within the actual winding shell at the authored helix phase.
  A smooth axial reversal avoids a jump at either reel edge. The rendered
  baked pack stays fixed in size; remaining-radius estimates control reel
  timing. Geometric routing does not simulate elastic tension or extra payout
  caused by head travel. Check whole-machine views as well as fitting macros.
- New recoloring materials need the same GLB extras schema as the loader,
  not only valid sidecar texture bindings. Confirm actual black, light and
  saturated variants in the installed renderer before delivering an assembly.


### Rotary metal studies and prepared workholding

The G430 rotary blank includes a centre-drilled tailstock seat with pilot relief.
It belongs to the initial stock; chip events describe subsequent removal only.
The clamped assembly uses captured jaws, an accessible quill lock and T-slot
fastenings. The setup adjustment itself is static.

For metal timing, omit fabrication `duration` to retain the material's physical
feed/depth rates. The `robotics/rotary_metal` example shows a physical-speed cut
before accelerating the rest. Equal time-lapse durations do not demonstrate
equal machining time. Material appearance is separate from cutting forces,
machine stiffness, coolant and tool-wear simulation.


### Adjustable rotary stock and timed FDM feed

The G430 rotary fixture has independent captured jaws, a sliding tailstock and
fed quill. Use `rotarySetup` or the dimensions on `rotaryCarve` to position them;
the machining job sets its axis datum and retained ends from that same setup.
The inspector's stock controls fit the fixture before restarting the carve.

The FDM sample retains 25% alternating infill. Its reel and cooling fan follow
physical process time even during time-lapse playback and rewinding. Short
seated translucent PTFE sections guide the exposed strand through the carrier
and into the head; their geometric routes are calibrated to the G430 frame.
See tools-guides/robotics.md for supported sizes and motion ownership.

### Supplied mesh fabrication, solid skins and indexed access

Manufacturing accepts BufferGeometry, Mesh and Object3D source hierarchies.
Snapshot the current transformed geometry once during setup, including parent,
instance and reflection transforms. `sourceGeometry` preserves the source buffers;
`fitSourceGeometry` fits uniformly into a physical Box3 or to a chosen size.
The FDM job fits to its bed. Relief expects physical stock coordinates; fit its
source into the available cutting region before calling `carve`.

FDM cross-sections preserve holes, union overlapping solids and retain separate
solids inside hollow shells. Local top/bottom skins compare adjacent layers,
so lower ledges receive dense surfaces while internal columns retain sparse
infill. Support generation and general printability assessment are separate.

`rotaryCarve(machine, sourceMesh, {renderer, ...options})` clips source triangles
into conservative projection cells at each indexed X-axis orientation, then
makes lateral XYZ rasters with cutter-footprint compensation. It subtracts real
swept tool volume from the stock field. The fitted 6 mm two-flute flat cutter
has 18 mm exposed cutting length; the relief machine retains its ball nose.
Source meshes are never substituted for the simulated result. The access report
describes reach-limited footprints and retained end stock; it does not certify
access to undercuts or every surface. Use `requireReach:true` to reject jobs
that exceed the conservative cutting-length envelope.

The local inspector accepts STL and embedded GLB files and offers ordinary mesh
examples. Compare the same input in additive, relief and indexed machining to
see each process's actual accessible result. Eight rotary table studs engage
the shared T-slot nuts. The loader retains part ownership on every primitive
when glTF represents one named part with several material primitives.

## NIGHT SHIFT — G430 print, A650+gripper pick-and-place, quadruped watcher (work/nightshift, 2026-09-14, Fable)

- **A650 + parallel gripper target frame.** With `arm.attach(gripper, {port:'a650_j6/output', childPort:'parallel_gripper/input'})`
  the jaws already point DOWN at the all-zero rest pose, so a "gripper pointing down" `moveTo` target is the
  identity rotation in the arm group's local frame (position = `group.worldToLocal(p)`). Do not fold the group's
  yaw into the target: a π rotation about the gripper axis lands j6 on its ±π limit and every solve fails.
  The jaws are symmetric, so `makeRotationY(yaw)` in local space is all the orientation control needed.
  Jaw fingertips sit 0.064 m below the flange; grip a small object with the flange ~0.076 m above its base.
- **Down-pointing reach band** (arm-local, flange height y vs radius r along the reach direction): r 0.25–0.55 m
  at y 0.20–0.45 m solves; y ≤ 0.15 only at r 0.3–0.5; nothing below 0.10. So a bed the arm must pick from
  should sit HIGHER than the arm base (printer on a 0.12 m plinth, arm on the bench) and a shelf at y+0.3.
  Seed IK with j1 = atan2(-z, x) (try both signs) plus a few elbow/wrist seeds; interpolate keys in joint space with smoothstep.
- **Carrying the printed part.** After the jaws close, `gripper.group.attach(job.mesh)` moves the FDM bead mesh
  with the arm (positionNode is mesh-local, so the deposited beads travel intact); `_s.attach(job.mesh)` on release
  leaves it seated wherever the arm put it. Place height = shelf top + the flange offset above the part base.
- **"Previous nights" prints without a second slicer.** `fab.print(printer, geom, {duration:10, buildPlate:false, color})`,
  `seek(duration)`, `_s.attach(mesh)`, then set position (bottom at `SHELF_Y - job.base`) and yaw; do this BEFORE
  creating the live job so the live job's `setColor` leaves the reel/strand in tonight's color. Real layer lines,
  free.
- **Timeline probe.** Render the real scene with `fps:1, duration:<film>` → one still per second of the whole film in
  ~66 frames; judge every beat (cuts, park, grasp, place) from that before the 24 fps render.
- **Lighting a white kit under one practical.** The A650/G430 white plastics blow out under a close SpotLight;
  46 cd at 1.2 m with exposure 1.12 and `_bloomParams {strength:0.12, threshold:0.92}` kept them readable while
  the room stays dark. Widen the cone (0.9 rad, penumbra 0.35) rather than adding fill to light a floor character.
- **Machine SFX from kinematics** (`work/nightshift/synth_sfx.mjs`, deno, no GPU): reload the same printer + `fab.print`
  job offline, seek it at 1 kHz along the film's playback clock, and turn per-axis on-screen speed into stepper
  tones (pitch ∝ speed, per-axis detune), `state.type==='extrude'` into a feed-motor tick, and a blade-pass fan
  tone that spins down after `printDone`. Replay the arm's joint keys for a servo whine ∝ weighted joint speed
  with band-passed gear noise; add clicks at jaw close / part set-down / jaw open and a two-note completion beep.
  Sounds land exactly on the motion by construction; Stable Audio beds are not needed for the machines.

### WSL renders through lavapipe — Night Shift render budget (2026-09-14)

- Per-frame cost in WSL was 8.5 s and bisected to the FDM bead meshes (five finished
  345k-vertex prints + the live one), independent of material, shadows or draw count:
  cost ∝ triangles × passes. `/usr/share/vulkan/icd.d/` has no NVIDIA ICD, so deno's
  WebGPU uses lavapipe (CPU). A 7-mesh scene hides this (0.12 s/frame); big geometry exposes it.
- Budget tools: `bakeBodies(robot)` merges kit meshes per rigid body (printer 96 → 31,
  quadruped 96 → 13 with `bodies:['camera_pan','camera_tilt']`), `bakeFinishedBead(job)`
  turns a completed print into plain position/normal geometry, and a coarser toolpath
  (`blendTolerance:0`, 28 lathe segments, 0.6 mm layers, 1.1 mm beads) cuts the live
  bead from 346k to ~110k vertices while keeping 90 visible layers.


## 2026-09-14 — Verify Deno hardware selection on WSL

WSL exposed the RTX 5090 to `nvidia-smi`, but default Linux Deno 2.9.5
selected `llvmpipe (LLVM 21.1.8, 256 bits)`, `isFallbackAdapter: true`.
`DENO_WEBGPU_BACKEND=gl GALLIUM_DRIVER=d3d12
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` selected `D3D12 (NVIDIA GeForce
RTX 5090 Laptop GPU)`, passed an actual compute/readback check, and rendered
an inspected Three.js/TSL frame. The hardware requirement is shared by
`eidoverse/gpu_check.mjs`, `doctor --gpu-only`, and renderer startup.
Keep these exports in the rendering environment and use separate OS dependency
stores. Do not infer hardware use from a successful render or CUDA/NVENC
availability. Setup and troubleshooting: [WSL GPU setup](docs/SETUP.md#gpu-setup-for-wsl-2).

### Correction: WSL GPU route and the N8AO limit (2026-09-14)

- The earlier "WSL renders on lavapipe" note was a setup error on my side, not a toolkit
  limit: with `DENO_WEBGPU_BACKEND=gl GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`
  (docs/SETUP.md "GPU setup for WSL 2") deno's WebGPU reaches the RTX 5090 through Mesa D3D12
  and `python3 eido.py doctor --gpu-only` reports the hardware adapter. Night Shift's 12-frame
  probe went from 101 s (lavapipe) to 3 s.
- On that route three things black the frame with no surfaced error (WGSL validates, GL pipeline
  creation returns GPUInternalError): renderer `antialias:true` (MSAA resolve), the N8AO pass, and the
  SSR pass in the full film (a small lit scene's SSR passed). Fix: `antialias:false`,
  `_aoParams={enabled:false}`, `_ssrParams={enabled:false}`; bloom/FXAA/shadows/fog/overlay/beads work.
  Bisect recipe that found it: env-driven variants + mean-gray of one frame, plus an
  `uncapturederror` listener in setup() to name the invalid pipeline.
- The geometry reductions made for lavapipe are unnecessary on the GPU route; the film uses the
  full-resolution toolpath again. `bakeBodies`/`bakeFinishedBead` stay in as harmless draw-call hygiene.


### 2026-09-14 — GPU access and software fallback

Use hardware whenever the environment exposes GPU access. Hosted sandboxes
without it must still be able to use a compatible software WebGPU driver.
The renderer and doctor now accept software adapters with an explicit CPU
warning, classify the backend in diagnostics, and keep actual adapter/compute
failures as errors. The strict hardware-only policy in the preceding entry
was too broad. Fix GPU selection where hardware is accessible; preserve
software fallback for environments where it is not.

## Night Shift, second pass — gripper mount, A650 workspace, SCARA pick-and-place (2026-09-14, Fable)

- **The kit gripper's `parallel_gripper/input` port sits at the gripper origin, between the fingers**, so
  `attach()` to a TC70 flange leaves the black robot-side coupling 12 cm away from the flange and the wrist
  pressed into the finger base (it reads as "mounted at 90°"). Mount on the coupling's top face instead:
  add a port `{interface:'TC70', owner: grip.roots.parallel_gripper, matrix: basis(x, y, z=normal) at (0, 0.118, 0)}`.
  With normal +Y the fingers extend along the parent flange's +normal (A650); with normal −Y the gripper
  hangs below a downward-facing tool face (S500 quill). Fingertips are 0.182 m from that face.
- **A650 workspace is an annulus, not a volume.** Its elbow folds to ~97° at most, so the wrist stays
  ≥ ~0.35 m from the shoulder; the flange normal cannot point down over most of the workspace (the wrist
  roll is not free about the tool axis, and the jaw axis follows the flange x-axis, which points down when
  the tool is horizontal — use `twist: Math.PI/2` on the mount if you need horizontal jaws). A horizontal
  gripper therefore works only on a ring ~0.52–0.59 m from the base. It cannot reach into the G430 from the
  side (the Y rails/uprights sit exactly in its link envelope) and cannot swing a carried part past the
  front uprights. Every attempt is in `work/nightshift/arm_plan*.mjs` with a capsule-vs-box collision report.
- **S500 SCARA is the right pick-and-place tool for the printer.** Links 0.245 + 0.255 m (tool radius
  0.16–0.50), quill 0.14 m, full-turn tool yaw. Placed in front of the printer (base 0.98 m high, 0.4 m
  left of the bed centre) with the bridge parked at the back, its horizontal links enter over the bed's
  open front, the quill lowers the gripper onto the part, and pulling the tool in to r = 0.20 m before the
  swing keeps everything ≥ 3 cm from the corner uprights. `plan_scara.mjs`: calibrated 2-link IK
  (`scaraJoints([shoulder, elbow, quill, tool])`, +shoulder toward −z, tool yaw = −(shoulder+elbow) keeps
  the jaws world-fixed), per-frame joints to `arm_traj.json`, collision check, params consumed by the scene.
- **Music prompts for MiniMax:** asking for "a warmer swell" produced a dense, chaotic second half; a
  solo-instrument prompt with "same pattern throughout, no build-up, no climax" and picking the take with
  the lowest onset density / RMS spread in its second half (measured with ffmpeg astats) gave a calm cue.

## 2026-09-14 — Physical attachment frames and shared mount metadata

The arm/gripper failure was a kit metadata problem. A650's output point was
present but its normal was absent, so the loader guessed source +Z while the
physical flange faces source +X: a 90-degree error. The gripper input was
invented at the model origin instead of its coupling face. The S500 output
likewise inherited +Z although its physical flange faces -Z.

The catalog now supplies shared `port_frames` for those mounts and the other
reused components whose frame fields were incomplete. This includes qualified
copies inside assemblies; there are no duplicate models or texture maps.
The gripper's actual coupling plane is at root-local public `(0, 0.1171, 0)`
with outward +Y, measured from exported triangles. That normal belongs to the
gripper and stays +Y in its own frame for every parent. Use the standard
`parallel_gripper/input` port instead of a scene-specific mounting frame
or changing its input normal to compensate for the parent.
Existing scene-specific compensation and trajectories must be reevaluated
against the corrected ports; the kit fix does not rewrite scene work files.

Require explicit mounting position and outward normal rather than guessing
axes. An optional tangent defines rotational alignment; `twist` only turns
around the mating axis. Validate finite transforms before reparenting.
Interface equality and coincident port matrices alone cannot catch incorrect
authored metadata: both matrices can agree while the physical parts do not.
The attachment regressions independently measure actual planar flange
triangles, check centres and opposing normals over several joint poses and
root transforms, and check intentional roll. Both physical checks fail with
the original metadata. These tests validate the mount, not clearance for the
entire attached payload; assembled motion still needs its own inspection.

### Root cause of the WSL GL route's black effects passes (2026-09-14)

- `device.createRenderPipelineAsync` on a dumped WGSL module returns the backend message the harness
  swallows: `WGSL textureLoad from depth textures is not supported in GLSL`, and for a non-comparison
  `textureSampleLevel` Mesa reports `no matching function for call to textureLod(sampler2DShadow, vec2, uint)`.
  naga's GLSL backend maps `texture_depth_2d` to `sampler2DShadow`; only `textureSampleCompare` and
  `textureDimensions` work. Three's TSL compiles nearest-filtered `depthNode.sample(uv)` to `textureLoad`
  (see the `tsl_coord_clampS_clamp_2dT` fetches in the generated WGSL), so N8AO, SSR and the depth copy
  cannot run on that route; editing N8AO's helper does not help (and passing a node into its `Fn` throws
  `depthNode.sample is not a function`, so the vendored file was restored from git).
- Standalone probe scripts: `work/nightshift/_check/pipeline_test.mjs` (compiles dumped shaders with
  parsed vertex layouts) and `depth_sample_test.mjs` (which depth operations the backend accepts).

### Herringbone banding on the robotics kit's cast parts = spotlight self-shadowing (2026-09-14)

- Symptom: a regular chevron/herringbone pattern following the triangle rows of the G430 cast uprights,
  the S500 SCARA column and the quadruped body, visible in lit and half-lit areas, present with and
  without N8AO/SSR. It is not the kit's materials: the UV islands sit on the right atlas regions, the
  occlusion map is clean, and the kit's `manufacturing.json` example (studio lighting, no shadow map)
  renders the same parts clean.
- Cause: a close SpotLight (1 m above the bench, `castShadow`, 2048 map, `bias -0.00015`, PCFSoft) with
  `normalBias 0` self-shadows the coarse smooth-shaded taper. `spot.shadow.normalBias = 0.005` removes
  it completely with no visible peter-panning; 0.02 also works. Diagnostic scene:
  `work/nightshift/_check/diag.scene.js` (kit printer as loaded, `DIAG=studio|mine`, `DIAG_NB`).
- Pitfall that hid it: the auto-enhance harness sets `renderer.shadowMap.enabled = true`, so a scene-level
  "shadows off" toggle changes nothing while auto-enhance is on; test lighting with
  `globalThis._noAutoEnhance = true` or in a scene without the chain.
- Do not diagnose by swapping or stripping kit materials; light-by-light and shadow on/off in a
  separate probe scene isolates it in a handful of single-frame renders.

### N8AO "grain" on small sets = the default 5 m aoRadius (2026-09-14)

- Symptom: soft blotchy mottling over every surface of a tabletop/room-scale scene, present with SSR off,
  gone with AO off; raising the quality preset alone (Ultra: 64 samples, 16 denoise) does not remove it.
- Cause: `createDefaultN8AOConfiguration().aoRadius` is 5 world units. On a 2 m bench the hemisphere
  samples span the whole room, so the denoised result is one low-frequency occlusion cloud.
- Fix: `globalThis._aoParams = { aoRadius: <contact scale>, quality: 'High' }` in the scene; 0.15 m on
  the Night Shift bench gives clean contact occlusion under 5 cm vases with no mottling. Pick the radius
  from the smallest crevice you want darkened, not from the room. Probes: `work/nightshift/_check/ao_sheet2*.png`.

### MiniMax Music 3: the `--seconds` pin is what garbled the Night Shift cues (2026-09-14)

- Takes pinned with `--seconds 64` (v1 ambient cue, takes 1–3, ~25 s worth of caption) played coherently
  for the first third and then disintegrated; the user heard them as "garbled nonsense". Takes with the
  latent left to the encoder were coherent but 14–30 s long (takes 4–8, 10). Take 9, the same brief with
  an explicit timed structure ("about 66 seconds: ... first 20 seconds ... from 20 to 45 seconds ...
  resolves around 60 seconds") under `--max-duration 90` and no pin, came back as a coherent 90 s piece
  and was trimmed to 62 s with a fade. Take 10, identical caption and a different seed, was 29 s.
- Rule: length comes from the caption's timed structure plus a ceiling above the target; `--seconds` only
  for short pieces or a pin near the encoder's estimate; roll seeds and select by measured duration.
  Guide section: tools-guides/audio.md "Prompting MiniMax Music 3 for a film cue".


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
One VRM carries every outfit as hidden layers (`eidoverse/assets/vrms/claude_suit_wardrobe.vrm`; guide: tools-guides/characters.md, "Outfits").
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
  Laptop is 2.1 ms, 28 draw calls and 283 MB of render targets; subtract it. The numbers are in tools-guides/props-and-sets.md.
- **Blender scripts that derive paths from `__file__`** (`HERE/..` as their root) only rebuild in the layout they were
  written in: document that layout and rebuild in a copy of it under `work/`. Replace a hard-coded repo path with a walk
  up to the folder holding `eido.py`. A scratch rebuild of the funeral crowd from the library copy matched size,
  triangles and rig JSON (not bytes).
