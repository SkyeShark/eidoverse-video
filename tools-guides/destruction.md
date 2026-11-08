# Character damage and dismemberment

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The engine's `makeDismemberment` gives per-limb health, dismemberment and
blood for any VRM humanoid. It applies Fallout-style part HP, cuts at the
head, shoulder, elbow, wrist, hip and knee, and hit-tests against posed bone
capsules. The sever splits every influenced skinned submesh and caps both
cross-sections with a flesh material. The severed piece tumbles as a rigid
body, and the blood is pressure-pulsed spurts, scheduled ground stains and
a spreading pool, all on the scene clock.

**It is not in this repository yet.** `dismember.js`, `dismember_core.js`
and `dismember_core_test.mjs` exist only as untracked files in the main
checkout, with no history on any branch. Porting them would publish them,
so the Blender edition waits on that decision. The decision belongs to the
lead and Skye, and it includes the open provenance of Sol's flesh, stain
and pool materials.

## The Blender edition's shape, for when it goes ahead

- **The pure-math core** ports to numpy almost line for line:
  - which bones leave with the limb, and each vertex's severed weight;
  - the continuous cut field and the marching-triangles split with
    attribute interpolation;
  - the cap "medallion" from the crossing-point cloud, cap weight transfer
    and renormalisation;
  - pose bake, rod physics at 1/120 s, and the gore limits.

  Vertex groups are the skin weights. The core's tests become Python unit
  tests that need no Blender.
- **The cut** is made on the rest-pose mesh, with the plane mapped through
  the bone's rest frame. The body keeps its Armature modifier with
  renormalised groups. The severed piece is the posed, evaluated mesh baked
  into a new object.
- **Physics.** The rod pieces and the verlet ragdoll are baked to
  keyframes. Bullet rigid bodies are Blender's native counterpart of the
  optional Rapier path.
- **Blood.** Spurts and stains become Scene-Time Geometry Nodes, as
  [particles](particles-fx.md) are. The pool becomes time-driven shader
  nodes. `liquid: 'swe'` goes through `eidoblend.fx.swe.create_water_swe`
  ([liquids](liquids.md)), which is ported.

## Procedural creature cut coverage

`makeCreature` publishes an attachment and cut manifest; read
[creatures.md](creatures.md) before selecting cut sites. A segmented limb
or weighted appendage can be supported, while an arbitrary cosmetic shell
cannot. Inspect coverage and rejected sites rather than assuming a mesh can
be cut anywhere. `makeSpecimen` has a separate skeleton and is not covered
by that manifest.

## Not yet ported

- All of it: `make_dismemberment`, damage and HP rules, `sever`,
  `hit_test`, `bleed`, caps and flesh materials, severed-piece physics, and
  blood spurts, stains and pool. It is blocked on the decision above.
