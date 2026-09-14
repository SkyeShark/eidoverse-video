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
