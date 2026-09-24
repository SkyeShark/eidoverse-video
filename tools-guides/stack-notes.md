# Stack notes — native WebGPU/TSL behavior and observed issues

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

These notes combine the pinned stack's integration requirements with issues
observed in earlier renders. Treat a workaround as a diagnosis to verify in
the current scene, rather than assuming every dark frame has the same cause.

- **A WebGPU adapter can be software.** Use `python eido.py doctor --gpu-only`
  in the shell that will render. The runner reports the adapter and verifies
  WebGPU compute/readback. Use hardware when GPU access is available;
  environments without it can use software WebGPU, with a clear CPU warning.
  WSL 2 with a GPU needs [backend selection](../docs/SETUP.md#gpu-setup-for-wsl-2).
  `nvidia-smi`, WebGPURenderer class selection and `powerPreference` alone
  do not prove hardware rendering. Video encoding is chosen separately:
  `RENDER_CODEC` if set, else `h264_nvenc` when ffmpeg lists it and a
  one-frame test encode succeeds on a hardware adapter, else `libx264`.
- **Materials are the NodeMaterial family** — `MeshStandardNodeMaterial` /
  `MeshPhysicalNodeMaterial` / `MeshBasicNodeMaterial`. Non-Node variants
  work via auto-wrap but accumulate WebGL idioms; the Node forms compose
  with TSL effects directly.
- **MeshBasic vs MeshStandard:** `MeshBasicNodeMaterial` is unlit — the
  surface renders `color * map` and ignores every light. It's the right
  choice for things that are themselves emissive (HUD panels, displays,
  glow strips, neon, screens). A creature on `MeshBasicNodeMaterial` with a
  dark color renders as a black silhouette no matter how the scene is lit —
  physical objects lit by the scene want `MeshStandardNodeMaterial` /
  `MeshPhysicalNodeMaterial`.
- **The pipeline is GPU-resident.** Per-frame CPU loops mutating instance
  matrices or vertex positions are the WebGL pattern; here that work lives
  in TSL compute or `positionNode` (one-time CPU passes in `setup()` are
  fine). Small joint/control loops and canvas UI updates are supported;
  reserve bulk simulation and large per-pixel effects for GPU work.
  `rtt(node, w, h)` from `'three/tsl'` renders a TSL texture on the GPU.
- **`VolumeNodeMaterial` doesn't compile under Naga.** Distance fog comes
  from `scene.fog = new THREE.FogExp2(...)`; custom volumes go through
  `RaymarchingBox` or the SDF loader ([sdf-volumes.md](sdf-volumes.md)).
- **Texture orientation depends on the path.** Native image/canvas helpers,
  raw HDR data and render-target textures are not interchangeable. Follow
  the HDR row-flip recipe in [scene-format](scene-format.md) for that loader.
  If sampling a render target on a mesh appears inverted, inspect its UVs
  and apply the needed orientation there; do not flip every asset globally.
- **VRMs load through `globalThis.GLTFLoader` only.** Importing
  `@pixiv/three-vrm` directly gives MToon a ShaderMaterial fallback under
  WebGPURenderer — a black scenePass.
- **Environment lighting:** follow the HDR/PMREM path in
  [scene-format](scene-format.md), or use the sky's environment bake.
  The engine supplies a dim fallback when an environment is absent.
  Inspect reflection setup, exposure and material conversion if a metal
  looks black. Preserve authored metalness rather than making all metals
  diffuse as a workaround.

- **Glass / water / transparency: alpha opacity carries the see-through.**
  ```js
  new THREE.MeshPhysicalNodeMaterial({
      color: 0xcfe6ff, roughness: 0.05, metalness: 0,
      transparent: true, opacity: 0.3,      // ← the see-through
      transmission: 0.9, thickness: 0.5, ior: 1.4,
  });
  ```
  `transmission` + `ior` add refraction flavor on top, but `transmission:
  1.0` with no opacity renders opaque/dark here (the backdrop sample comes
  back black). For a hero refraction beat, hand-roll screen-space
  refraction; for ordinary glass/water/ice/windows, alpha + transmission is
  the pattern.
- **Encoder bitrate:** the frame→nvenc pipe defaults to 8000k average /
  10000k peak. If high-frequency content (fluid, noise, dense particles,
  fast whole-frame motion) macroblocks into "pixel boxes", raise
  `RENDER_BITRATE` or switch to `RENDER_CQ=19` (a quality-mode starting point). A delivery
  file-size ceiling is respected the other way: higher `-cq`, lower
  resolution, or a shorter clip.
- **Depth-keyed screen effects composite over no-depth particles.** Effects
  that read scene depth (`depth_fog`, `godrays`, …) blend using the depth
  behind a particle quad — additive sprites, particle-morph clouds, and
  `fromText` particle words get fog/rays drawn through them. A particle
  showpiece that must read against the sky wants geometry behind it
  (occlusion works fine — stones in front of a particle word clip it
  correctly). The world-space sky system doesn't have this problem — its
  cloud dome draws in the scene pass behind the particles. Additive
  particles also can't show against a bright sky (add-to-white is
  invisible) — glowing particle work reads against dark backgrounds.
- **Transparent materials write into the auto-enhance G-buffer.** The scene
  pass renders color + encoded normals + metalrough as MRT; the extra
  attachments follow each material's blend state. A custom transparent
  billboard that lets the default normal write through smears quad-face
  normals over the GTAO reads, and AO stamps dark rectangles behind it.
  `makeParticles` opts its quads out already; for your own transparent
  effect quads copy its pattern —
  `mat.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) })` (alpha-0
  writes preserve what's underneath). Real transparent surfaces (water,
  glass) keep writing their true normals — SSR needs them.

## Encoding and delivery copies

If a render already contains macroblocking, encoding that MP4 at a higher
bitrate cannot recover the lost detail. Re-render with improved encoder
settings, or encode again from a higher-quality master if one exists.

For a delivery copy from such a master, examples are:

```bash
ffmpeg -i master.mp4 -c:v h264_nvenc -preset p5 -rc vbr -cq 19 -b:v 12M -maxrate 24M -bufsize 24M -c:a copy delivery.mp4
ffmpeg -i master.mp4 -c:v libx264 -crf 20 -preset slow -pix_fmt yuv420p -c:a copy delivery_cpu.mp4
```

Lower CQ/CRF generally means higher quality and a larger file. These values
are starting points, not a guarantee for every resolution or motion pattern.
Review busy areas and gradients in the encoded copy, and retain the master.

