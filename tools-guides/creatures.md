# Creatures — make_creature (Blender edition: not yet ported)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md)

**Status.** The universal procedural creature builder has not been ported to
the Blender edition yet: there is no `make_creature` in
`blender/eidoblend/characters/` today. Do not stand a stock model or another
rig in for it; a scene that needs a creature waits for the port, or is made in
the WebGPU edition. This page keeps the builder's vocabulary (the port's
specification, from `eidoverse/creature_builder.js`, 2,856 lines) and the plan
the port follows, so nothing is silently dropped.

## What the port must carry over

One spine + parts + gait system parameterized into any morphology (Spore-style),
auto-rigged (a real skeleton, analytic weights), gaits that carry body
language: human pelvis / weight-shift / heel-toe roll with settle-on-stop, quad
strike bob + head nod, arthropod skitter.

- **Stances:** `quad` (+ `legPairs` 2–4), `biped` (arms, optional hands),
  `bird` (horizontal body, hooked two-mandible beak, two-segment folding wings,
  walk head-bob), `serpent` (ground-fixed path following: the S-curves stay
  planted while the body slides through them; tongue flicks), `octopus`
  (mantle + 8 wave-animated tentacles), `insect` (tripod gait, compound eyes,
  antennae, buzzing translucent wings; `wings: 4` = dragonfly), `spider`
  (alternating-tetrapod gait, fanned legs, abdomen bulb, 8-eye cluster,
  chelicerae), `snail` (slug glide, eye stalks, spiral shell; `shell: true` on
  any creature), `fish` (tail-amplified swim wave, fins, banks into turns,
  hovers at `swimDepth`).
- **Flight** (`fly(alt)` / `land()`): fast downstroke, lagging hand segment,
  pitch into climbs, banking. Quads pick a 4-beat lateral walk at low speed and
  a diagonal trot above ~0.75 m/s (`gait` overrides; phases blend).
- **Faces and feet:** a lofted `muzzle` with the hinged talking jaw;
  iris / pupil eyes with hooded lids (`eyeColor`, `pupil: 'slit'`), `ears`
  (`point` / `flop` / `round`, flick-animated), `fangs`, `tusks`, `horns` +
  `hornStyle` (`spike` / `ram` / `antler` / `moose` / `narwhal`); `feet`
  (`shoe` / `paw` / `hoof` / `webbed` / `lizard` / `talon`), ankles planted at
  foot height.
- **Everything mixes** (parts gated by options, not stance): beak + webbed +
  `tailStyle: 'paddle'` = platypus; `trunk` + `tusks` + big round ears =
  elephant; `neck: 1.3` + `legLength: 1.15` = giraffe; wings on anything =
  dragons. More: `wingType` (`bat` / `butterfly`), `nose: 'star'`, `buckTeeth`,
  `beakWidth`, `spikes`, `armor`, `gills`, `claws`, `antennae`, `squid`,
  `build: 'feminine'` + `hair: 'long'`, `tailCarry`, `whiskers`, `tailRadius`,
  `finScale`, `eyelids`.
- **Accessories:** `hat` (`cap` / `top` / `beanie` / `cowboy` / `officer`),
  `helmet` (`space` / `hardhat`), `glasses`, `sunglasses`, `mask`, `tie`.
  **Cyborgs:** `robot: true` (panel plating, LED iris eyes, joint caps),
  `robotParts`. **Humans:** `makeCreature.human()` (sculpted skull head, jaw,
  brows, hair, shoulders, shirt treatment); `makeCreature.random(seed)`.
- **Skins:** procedural TSL patterns (`pattern`, colours) over the bind pose,
  clothing bands (`outfit: { shirt, pants, shoes }`), or image maps (tube UVs
  u-around / v-along); add-on parts are named meshes (`parts('shell')`).
- **Talking:** every jawed head is hinged: `say(text | {duration, energy})`,
  `talking`, `setTalkEnvelope((t) => amp01)` for an audio envelope
  (`lipsync.py get_mouth_openness`), `hasJaw`.
- **Steering:** `walkTo` / `setHeading` / `speed`; the gait owns heading.
- **Dismemberment manifest:** `dismemberManifest` and `dismemberCoverage`
  (weighted and rigid cut keys, deterministic across seeds), the destruction
  family's interface.

## The plan (how it ports, as the rest of this family does)

- `make_creature(**opts)` builds the same geometry from the same maths with
  numpy (`from_pydata`, vertex groups with the analytic weights) and one
  armature whose bones take three's rest frames turned into Blender's axes
  (three `(x, y, z)` → Blender `(x, −z, y)`).
- The TSL patterns become shader node groups on a rest-position attribute
  (`Object.add_rest_position_attribute`), materials Principled under EEVEE.
- The gait, flight, steering and the talking jaw are simulated once, in frame
  order, at the scene's fps, and keyed (the family's rule: no handler at render
  time); feet plant on the ground the way `walk_path` plants mine.
- The dismember manifest is emitted unchanged, for the destruction family.

## Not yet ported

- `make_creature` and everything above: stances, parts, accessories, skins,
  gaits, flight, steering, talking, the dismember manifest and coverage.
- `make_realistic_creature` / `makeSpecimen` / `buildRealisticSpec`: they need
  `work/creaturelab/` (`sculpt_creature.py`, `fur_bake.py` and its cache), which
  exists in neither checkout. Report that prerequisite missing; never substitute
  a different creature.
- The Bestiary (Claude's creatures) lives on another fork, not on this branch.
