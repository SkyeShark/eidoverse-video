Vendored from npm `n8ao-webgpu@0.1.0` (github.com/marioandf/n8ao-webgpu, CC0-1.0),
a three.js WebGPU port of N8AO by N8python — endorsed by the original author.
Bare `three` / `three/tsl` / `three/webgpu` import specifiers are pinned to
`npm:three@0.184.0` so Deno cannot resolve a second three instance (the
package's peer range is ^0.182.0).

N8AO 2.0's neural denoise is ported in from npm `n8ao@2.0.1`
(github.com/N8python/n8ao, CC0-1.0):
- `NeuralDenoiseModel.json`: upstream's `src/NeuralDenoiseModel.json`, verbatim.
- `NeuralDenoise.js`: upstream's `src/NeuralDenoise.js` (the GLSL generator) and
  the `NEURAL_DENOISE` block of `src/PoissionBlur.js`, as TSL: the same layout
  checks, folded normalisation, layers and online-softmax attention.
- `N8AONode.js`: the neural material as denoise pass two, the `neuralDenoise`
  setter and the fallback guard with upstream's warning.
- `math.js`: the `neuralDenoise` default and the `Neural-Low` /
  `Neural-Medium` / `Neural-High` quality modes.
Checked on the GPU against a plain-JS transcription of upstream's math (random
tap tokens, real tap geometry through the local frame, the global-only path):
largest difference 1.1e-7.

One change from upstream: with `neuralDenoise` on, the AO pass hands the
denoise passes the G-buffer's shading normals (`normalNode`, the scene pass's
MRT normal) where upstream stores the depth-derived ones. On game-resolution
meshes the depth normals are flat per facet, and the model kept the AO's
facet-to-facet steps as creases: bands on every round shell. The AO itself
still samples its hemisphere about the depth normals.
