# Creatures — makeCreature

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The universal procedural creature builder (Spore-style): one
spine+parts+gait system parameterized into any morphology. Auto-rigged
(real Skeleton, analytic weights); gaits carry body language — human
pelvis/weight-shift/heel-toe roll with settle-on-stop, quad strike bob +
head nod, arthropod skitter.

**Stances:** `'quad'` (+ `legPairs` 2–4), `'biped'` (arms, optional hands),
`'bird'` (horizontal body, hooked two-mandible beak, two-segment folding
wings, walk head-bob), `'serpent'` (ground-fixed path following — the
S-curves stay planted in the world while the body slides through them;
tongue flicks, rests in its curve), `'octopus'` (mantle + 8 wave-animated
tentacles), `'insect'` (tripod gait, compound eyes, antennae, buzzing
translucent wings — `wings: 4` = dragonfly), `'spider'`
(alternating-tetrapod gait, fanned splay legs, abdomen bulb, 8-eye cluster,
chelicerae), `'snail'` (slug glide, eye stalks, spiral shell — `shell:
true` mounts one on any creature), `'fish'` (tail-amplified swim wave,
caudal/dorsal/pectoral fins, banks into turns, hovers at `swimDepth`).

**Flight** (`c.fly(alt)` / `c.land()`): fast downstroke + lagging hand
segment, pitch into climbs, banking into turns. Quads auto-pick a 4-beat
lateral walk at low speed / diagonal trot above ~0.75 m/s (`gait`
overrides; phases blend on transition).

**Animal faces** on tube heads: quads default a lofted `muzzle` (the mouth
is the hinged talking jaw); iris/pupil eyes with hooded lids (`eyeColor`,
`pupil: 'slit'`), `ears: 'point'|'flop'|'round'` (flick-animated), `fangs`,
curling `tusks`, `horns` + `hornStyle: 'spike'|'ram'|'antler'|'moose'|
'narwhal'`. **Feet:** `feet: 'shoe'|'paw'|'hoof'|'webbed'|'lizard'|'talon'`
— ankles plant at foot height so soles rest on the ground.

**Everything mixes — parts are gated by options, not stance.** Beak on a
quad + webbed + `tailStyle: 'paddle'` = platypus; `trunk` + `tusks` +
`ears: 'round'` + `earScale: 2` = elephant; `neck: 1.3` + `legLength: 1.15`
= giraffe; wings on anything = dragons. More organs: `wingType:
'bat'|'butterfly'` (butterflies fold upright at rest), `nose: 'star'`,
`buckTeeth`, `beakWidth` (duck ≈1.6), `spikes`, `armor`, `gills`, `claws`,
`antennae` (metal + glowing when robot), `squid: true`, `build:
'feminine'` + `hair: 'long'`, `tailCarry` (raised cat curl), `whiskers`,
`tailRadius`, `finScale` (sharks), `eyelids: 0..1` (droopiness — they
still blink).

**Accessories** on any creature: `hat: 'cap'|'top'|'beanie'|'cowboy'|
'officer'`, `helmet: 'space'|'hardhat'`, `glasses`, `sunglasses: true`,
`mask: 'smile'|'frown'`, `tie` (bipeds). **Cyborgs:** `robot: true` =
metallic panel plating, LED iris eyes, joint caps; `robotParts: ['arms',
'legs', 'head', 'tail', 'neck', 'body', 'tentacles']` robots individual
elements. **Humans:** `makeCreature.human()` = sculpted skull head (jaw,
brows, hair), raised shoulder points, relaxed elbows, sleeve/collar shirt
treatment.

**Skins:** procedural TSL patterns (`pattern`, colors), clothing color
bands (`outfit: { shirt, pants, shoes }`), or image textures (`map` /
`normalMap` / `roughnessMap` — tube UVs run u-around / v-along; set
`texture.repeat`). Add-on parts are named meshes — `c.parts('shell')`
returns them for material swaps. Weld balls cover tube junctions; inspect
tail/neck/hip joins through the poses and proportions you actually use.

```js
const wolf = globalThis.makeCreature({ stance: 'quad', ears: 'point', fangs: 1,
    muzzle: 1.1, feet: 'paw', color: 0x6f7378, speed: 0.5, seed: 9 });
scene.add(wolf.group);                                 // self-animating
wolf.walkTo(4, 2);  wolf.speed = 0.8;  wolf.setHeading(a);   // steering
const person = globalThis.makeCreature(makeCreature.human({ shirt: 0x3a6ea8,
    hat: 'cap', sunglasses: true, tie: 0x2a2a30 }));
const ram = globalThis.makeCreature({ stance: 'quad', horns: 2, hornStyle: 'ram', feet: 'hoof' });
const spider = globalThis.makeCreature({ stance: 'spider', color: 0x3a2c22 });
const dfly = globalThis.makeCreature({ stance: 'insect', wings: 4 });
const bot = globalThis.makeCreature(makeCreature.human({ robot: true, hair: 'none', outfit: null }));
const wild = globalThis.makeCreature(makeCreature.random(42));
```

**Dismemberment topology is authored, not guessed.** Every returned creature
has `c.dismemberManifest`, ready for the generic shared-Skeleton adapter:

```js
const c = makeCreature({ stance: 'octopus', seed: 9 });
scene.add(c.group);
const dm = await makeDismemberment(null, {
    scene,
    manifest: c.dismemberManifest,
});
dm.sever('tentacle:3:mid');
```

Part/cut keys are deterministic across seeds and cosmetic variants. Weighted
heads, three-site arms/legs, tube tails, ordinary/back tentacles, and explicitly
pre-segmented rigid fan/paddle tails, wings, pectoral/caudal fins, and dorsal
fins are covered for biped, quad, bird, serpent, octopus, insect, spider, and
fish rigs. Feather wings retain an outer Group, so `wing:0:<side>:tip` can be
cut before `wing:0:<side>:base`; other wing styles and fins expose whole-root
base cuts only. Distal cuts consume only their descendants, so a later proximal
cut and an opposite-side sibling remain independently legal.

Read `c.dismemberCoverage.weightedCutKeys`, `.rigidCutKeys`, and `.unsupported`
for the exact receipt. Opaque geometry is never inferred into a cut: arbitrary
unsegmented meshes, the core/unskinned torso, and cosmetic shells, hats, horns,
claws, armor, and spikes have no independent authored cut. An ordinary
accessory beneath a severed weighted Bone may ride that detached piece, but
that is not an accessory cut site and this manifest does not generalize opaque
triangle soup.

`makeRealisticCreature()` calls `makeCreature()` and returns this same rig and
manifest, though its Deno sculpt-render replacement is not exercised by the
headless procedural fleet. `makeSpecimen()` has an independent anatomy and
skeleton; it does not inherit this manifest and remains a separate integration.

**Talking** — every jawed head is hinged (skull chin, animal lower jaw,
beak mandible; serpents/fish have no jaw): `c.say('Some words')` (duration
from word count) or `c.say({ duration: 4, energy: 0.9 })` flaps procedural
syllables and reveals a dark mouth interior; `c.talking = true/false` for
continuous. **`c.setTalkEnvelope((t) => amp01)` maps a real audio amplitude
envelope onto the jaw** — pair with `lipsync.py`'s `get_mouth_openness` for
TTS-synced creature speech. `say()` animates the jaw; it does not synthesize
audio. Add the matching voice through [audio](audio.md). `c.hasJaw` says
whether this head articulates.

**Steering:** `walkTo` / `setHeading` / `speed` own the movement — the gait
owns heading, so writing `group.rotation.y` does nothing. Route paths
around other actors; nobody avoids anybody on their own.

**Initial-state review:** earlier creature studies showed settling and
first-frame pose/shadow issues. Inspect both the opening and later motion in
a short render. If a scene needs pre-roll, advance all relevant update owners
consistently before recording; changing `t` only inside `renderFrame` does not
advance the engine's already-run automatic creature updates. A later clean
frame does not excuse a broken opening in the final piece.

Earlier mixed creature/robot scenes also showed render-order problems. Treat
creation-order changes as a diagnostic experiment, not a requirement proved
for the new modular robotics kit. Inspect the actual result after changes.

## Optional realistic body pipelines

The renderer also injects two async constructors:

```js
const creature = await makeRealisticCreature({
  stance: 'quad', bodyLength: 1.35, legLength: 1.05,
  neck: 0.42, tail: 0.85, seed: 7, speed: 0.6
});
scene.add(creature.group);
creature.walkTo(4, 2);
```

`makeRealisticCreature` retains the `makeCreature` rig and control vocabulary,
replacing its body with a cached realist asset. `makeSpecimen` constructs a
different anatomy skeleton and gait; it shares options, not the original rig.
Both return a self-animated creature group with navigation controls.

These are **optional local pipelines**: cache misses call
`work/creaturelab/sculpt_creature.py`, and specimen fur can call
`work/creaturelab/fur_bake.py`. Those are ignored working-project dependencies,
not bundled public modules. Check the required scripts/cache before choosing
these constructors; the injected function alone does not make a clean checkout
capable of building a new realist asset. Report missing prerequisites instead
of silently substituting a different creature. The ordinary `makeCreature`
path does not require that backend.

`buildRealisticSpec(creature, opts)` is a low-level converter in
`creature_realist.js`: it turns an existing procedural creature's anatomy into
the sculpt specification used by that optional backend. It does not create or
render a creature on its own. Use `makeRealisticCreature` for the full path.
