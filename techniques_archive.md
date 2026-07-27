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
