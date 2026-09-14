# Character damage and dismemberment

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

**`makeDismemberment`** — per-limb health + dismemberment + blood for ANY VRM
humanoid (the shipped cast or an arbitrary rig — bones resolve through
`vrm.humanoid`, and per-mesh reduced skeletons from `combineSkeletons` /
`removeUnnecessaryJoints` are handled).

```js
const dm = await globalThis.makeDismemberment(vrm, { scene, groundY: 0 });
dm.damage('leftArm', 45, { type: 'slash' }); // Fallout rules: part HP, cripple at 0,
                                             // sever on edged overkill / death blow;
                                             // limbs bleed the life pool at 0.45x
dm.sever('head');                            // direct choreography; also 'leftArm',
                                             // 'leftArm:elbow', ':wrist', legs, knees
dm.hitTest(ray);                             // -> {key, part, point, distance} via POSED
                                             // bone capsules (never a bind-pose raycast)
dm.bleed(point, { intensity: 0.6 });         // stab wound without a sever
```
- The sever SPLITS every influenced skinned submesh (sleeves, hair, face —
  material groups and morph targets survive), caps both cross-sections with a
  procedural flesh material whose bone disc sits at the true bone position,
  bakes the severed piece rigid (it tumbles on a built-in integrator, or pass
  `{world, RAPIER}` for a Rapier dynamic body), and starts arterial
  blood: pressure-pulsed spurt on the scene clock, analytically scheduled
  ground stains, and a spreading pool that dries over minutes.
- Everything self-updates via the engine drain; blood runs on the scene clock
  passed to `update(t)`, so offline renders and live hosts behave identically.
- `liquid: 'swe'` swaps the decal pool for a `createWaterSWE` heightfield patch
  fed by the stumps (real flow). At puddle scale under a bright env its fresnel
  reflection washes pale — use it for lake-scale blood, or pair with a dark env;
  the decal pool is the default and reads correctly everywhere.
- Events surface through `opts.onEvent` + `dm.events`; state via `dm.state()`.
  `dispose()` removes every mesh/material the system created.

## Procedural creature cut coverage

`makeCreature` publishes an attachment/cut manifest; read
[creatures.md](creatures.md) before selecting cut sites. A segmented limb or
weighted appendage can be supported while an arbitrary cosmetic shell is not.
Inspect coverage and rejected sites rather than assuming a mesh can be cut
anywhere. `makeSpecimen` has a separate skeleton and is not covered by that
manifest. The renderer injects `dismember.js`, which loads `dismember_core.js`.
