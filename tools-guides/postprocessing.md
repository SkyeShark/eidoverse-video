# Post-processing effects

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

### TSL postprocessing — `CustomEffectsDeno`

The effect registry provides reusable GPU shaders for stylized looks. Use it
when an existing effect fits, or build a custom TSL effect when exploring a
new one. Large per-pixel effects belong on the GPU. Canvas/Satori remain useful
for authored text, display content and graphic elements; see
[motion graphics](motion-graphics.md).

```js
globalThis._fx = globalThis.CustomEffectsDeno.applyTo({
    scene, camera,
    effects: 'depth_fog,glitch_bars',   // comma-separated — chain 1-4 freely
    opts: { glitch_bars: { barFreq: 22, shift: 0.03, opacity: 0.85 } },
});
// per frame — update the effect's uniforms, THEN render. _fx.update(t) does
// NOT render (it only pushes uniforms into the auto-enhance pipeline); the
// scene render still has to happen, every frame, or the video freezes:
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);
```

**Timed glitch (a burst on a beat) — pulse the effect's live uniform, don't
swap canvases.** Every effect returns `uniforms`; drive them per frame:
```js
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'glitch_bars' });
// in renderFrame(t): ramp intensity on the beat
const u = globalThis._fx.uniforms;
if (u?.opacity) u.opacity.value = beatEnv(t);   // 0 most of the time, 1 on the hit
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);   // ALWAYS render after — update() doesn't
```

The default auto-enhance path supplies N8AO ambient occlusion, SSR, UnrealBloom and FXAA; a scene can opt out when it owns its compositor (below). Moving sky/cloud reflections on metals come from the sky system's `sky.enableReflections(camera)` ([sky-weather.md](sky-weather.md)).

The complete current catalog has 31 effects. Discover it programmatically
with `CustomEffectsDeno.list()` or inspect the sources under `effects_tsl/`.
Choose effects for the piece, including none when the image needs no added
treatment. The families below help compare the available looks.

For one effect, `_fx.uniforms` is that effect's uniform object. For a chain,
it is keyed by effect name, such as `_fx.uniforms.glitch_bars`. The available
fields differ by effect; inspect the selected entry before animating it.

Library (31 effects) — the families:
- **3D/volumetric** (scene passes): `nuclear_explosion` (skies and rain are
  NOT effects — use the world-space sky + weather systems)
- **Glitch/retro**: `glitch_bars`, `vhs_tape`, `crt`, `rgb_shift`, `chromatic_aberration_alpha`, `jitter`, `after_image`
- **Colour grade**: `full_toon`, `sepia`, `bleach_bypass`, `old_bw_film`, `bw_halftone`
- **Line/edge**: `cross_hatch`, `neon_edges`, `blueprint`, `dithering`, `retro_wireframe`
- **Atmospheric / light**: `depth_fog`, `godrays`, `lensflare`, `anamorphic_flare`, `underwater`, `rain_on_camera` (lens droplets — world rain is the weather system's job)
- **Distort**: `melt`, `wavy`, `kaleidoscope`
- **Blur/focus**: `focus_blur` (DoF), `radial_blur`, `box_blur`, `hash_blur`

## Renderer integration

The renderer injects each `effects_tsl/*.js` implementation before
`custom_effects_deno.js`. Use the registry instead of eval-loading effect files
again. The native auto-enhance path adds AO, reflections, bloom and antialiasing.
If a scene owns a complete custom compositor, set `_noAutoEnhance = true` in
`setup()` and verify the final render path; updating effect uniforms alone does
not produce frames. See [scene-format.md](scene-format.md) and
[stack-notes.md](stack-notes.md) for render hooks and depth/transparent surfaces.
