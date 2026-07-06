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
