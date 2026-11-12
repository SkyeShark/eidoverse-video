# Character damage and dismemberment

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md)

**Not in this edition.** The WebGPU engine's `makeDismemberment` gives
per-limb health, dismemberment and blood for any VRM humanoid: Fallout-style
part HP, cuts at the head, shoulder, elbow, wrist, hip and knee, hit tests
against posed bone capsules, a sever that splits every influenced skinned
submesh and caps both cross-sections, severed pieces that tumble as rigid
bodies, and blood as pressure-pulsed spurts, ground stains and a spreading
pool on the scene clock. Its source is not in this repository, so the Blender
edition has nothing to port it from yet, and there is no `make_dismemberment`
in `blender/eidoblend/`.

Until it is here, keep damage off screen or in the cut, and do not fake a
sever with stand-in geometry on a character.

## Not yet ported

- All of it: `make_dismemberment`, the damage and HP rules, `sever`,
  `hit_test`, `bleed`, the caps and flesh materials, the severed pieces'
  physics, and the blood's spurts, stains and pool.
