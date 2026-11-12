# Creatures (Blender edition: the creature creator is not ported)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md) · [Assets](assets.md)

**Status.** The WebGPU edition's procedural creature builder
(`makeCreature`, `eidoverse/creature_builder.js`) is not ported to the
Blender edition, and it will not be: a new creature creator is being made,
and it comes to this edition in its place. There is no `make_creature` in
`blender/eidoblend/` today.

Until it lands:

- A creature that a library or fetched model already is (a crow, a wren, a
  scanned animal) is fine as what it is. The animated birds and their clips
  are in [assets](assets.md#the-animated-birds--crow--cactus-wren);
  `fetch_model.py` finds others ([assets](assets.md)). Check the licence and
  the clips before you cast one.
- A character with a face, a voice and a body to direct is a VRM
  ([characters](characters.md)): the controller walks it, the claudesona's
  tools give it a mouth, and my robot body moves through its real joints.
- Do not dress another rig up as one of the builder's creatures: a scene
  that needs the builder's own morphologies (a talking octopus, a dragon
  with folding wings, a platypus from mixed parts) waits for the new creator,
  or is made in the WebGPU edition, where `makeCreature` runs as it is.

## Not yet ported

- `makeCreature` and everything it builds: the stances (quad, biped, bird,
  serpent, octopus, insect, spider, snail, fish), the parts that mix across
  them (muzzles and hinged talking jaws, eyes and lids, ears, horns, tusks,
  trunks, beaks, wings, tails, feet), accessories and cyborg parts, the
  procedural skins, the gaits and flight, steering, `say` /
  `setTalkEnvelope`, `makeCreature.human()` / `random(seed)`, and the
  dismember manifest and coverage the destruction family reads. A new
  creature creator replaces it here.
- `makeRealisticCreature` / `makeSpecimen` / `buildRealisticSpec`: they need
  an external sculpting and fur-baking backend that is not in this
  repository. Report that prerequisite missing; never substitute a different
  creature.
