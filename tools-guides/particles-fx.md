# Particles — makeParticles, makeParticleMorph

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

## `makeParticles` — sparks, smoke, dust, snow, magic

Camera-facing textured sprites whose motion runs on the GPU (TSL
`positionNode`); billboarding auto-updates, and you call nothing per frame.
The texture is what sells it — there's an ~80-texture library at
`eidoverse/assets/particle_textures/` (`spark_*`, `smoke_*`, `flame_*`,
`magic_*`, `star_*`, `muzzle_*`, `glow_*`, `dirt_*`, scorch, energy,
traces, symbols…) — add the one you want to scene.json `assets` and load
it. Untextured 2D particles render as squares. Use a shaped alpha texture
for soft smoke or sparks; geometric particles are also available as a style.

```js
const tex = await globalThis.loadImageTexture(globalThis.ASSETS.spark, { srgb: true });
globalThis.makeParticles({ scene, camera, preset: 'sparks', map: tex, origin: [0, 1, 0] });
```

- Presets: `sparks`, `embers`, `smoke`, `dust`, `snow`, `magic`, `stars`,
  `muzzle`, `fire` — each sets count/size/lifetime/gravity/blending/color;
  override any (`count`, `size`, `color`, `origin`, `gravity`, `speed`,
  `lifetime`, `area`, `grow`, `opacity`). `area` accepts a number or
  `[x, y, z]` extents.
- Returns `{ mesh, material, update, uniforms }`; pulse
  `uniforms.opacity.value` for a burst.
- Glowing presets (sparks/fire/magic) use additive blending automatically;
  smoke/dust/snow blend normally. Additive particles can't show against a
  bright sky (add-to-white is invisible) — stage glowing particle work
  against dark backgrounds, and see [stack-notes.md](stack-notes.md) for how
  depth-keyed screen effects composite over particle quads.

## `makeParticleMorph` — dissolve and reform anything

A GPU particle cloud that morphs between point-set targets: dissolve a
mesh/VRM into volumetric particles and reform it as another shape —
teleports, summons, shape-forms, a body→diagram→body sequence. Position is
`mix(targetA, targetB)` + curl turbulence, all on the GPU, billboarded like
`makeParticles`.

```js
const m = globalThis.makeParticleMorph({
  scene, camera, count: 60000, map: glowTex,
  targets: [ ParticleMorph.fromMesh(vrm.scene, 60000),       // sample a mesh/VRM surface (skinned-aware, current pose)
             ParticleMorph.neuralNet({ count: 60000 }) ],    // or .neuronGraph / .fromPoints / .fromText
  color: 0x55e0ff, color2: 0xc060ff, size: 0.014,
  blending: 'additive', curl: { scale: 1.5, strength: 0.55 },
});
// per frame, from your timeline:
m.morph(0, 1, t01 /*0..1*/, turbulence);   // morph A→B
m.uniforms.opacity.value = fade;            // fade the cloud in/out
m.uniforms.vortex.value = 5;                // optional spiral/vortex reassembly
m.updateTarget(0, ParticleMorph.fromMesh(vrm.scene, m.count));  // recapture a LIVE pose at the dissolve instant
```

- **Target generators:** `ParticleMorph.fromMesh(obj, count)`
  (surface-sample any mesh/VRM in its current pose),
  `ParticleMorph.fromText('WORD', count, { width, ascii, fontSize, depth })`
  (rasterized text or multi-line ASCII art → 3D point cloud — a cloud can
  spell a word or logo in one call, and `{ ascii: true }` reforms ASCII art:
  a face, a sigil, a diagram), `ParticleMorph.neuralNet({ layers, … })`,
  `ParticleMorph.neuronGraph(...)`, `ParticleMorph.fromPoints(arr, count)`.
- All targets resample to `count`; share centroids if a jump between A and
  B isn't wanted. A soft `glow_*` texture as `map` reads best.
- `size` defaults to 0.014 (tuned for close-ups) — at a pulled-back camera
  (5 m+) pass `size: 0.03–0.05` or the cloud reads dim.
- To match a moving/posed VRM at the handoff: play the animation live, then
  `updateTarget(0, fromMesh(vrm.scene, count))` at the dissolve frame and
  freeze the pose — dissolve, reform, and snap-back all line up.
- Chain targets for a whole beat: VRM → galaxy → the word → ASCII glyph →
  scatter.


### Particle textures

Declare a texture in `config.assets`, for example
`"spark": "eidoverse/assets/particle_textures/spark_05.png"`, then load it with
`await loadImageTexture(ASSETS.spark)` and pass it to `makeParticles` or a sprite
material. Reuse textures across emitters when their sampler settings agree.
Use the library's alpha shapes for soft edges, or leave particles geometric
when that is the intended image.

