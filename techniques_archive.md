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
