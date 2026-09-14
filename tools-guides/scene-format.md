# Scene format — config, script shape, engine globals

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

## Invoking the renderer

Everything renders natively (deno 2.8.1 or 2.9.5 + ffmpeg + your GPU; setup in
[setup guide](../docs/SETUP.md)):

```bash
python eido.py render work/<your_scene>.json            # full render
python eido.py render work/<your_scene>.json --probe    # single frame, framing checks
# or raw, from the repo root:
deno run --allow-all --unstable-webgpu eidoverse/render_scene.mjs work/<your_scene>.json
```

If the ffmpeg has no nvenc, set `RENDER_CODEC=libx264`. All paths in scene
configs and tool calls are relative to the repo root — the engine always
runs with that as its cwd. `python eido.py doctor` diagnoses
deno/ffmpeg/deps; `python eido.py bootstrap` fetches them the first time.

## scene.json

```json
{
    "width": 1280, "height": 720, "fps": 30, "duration": 60,
    "script": "work/<id>/scene.js",
    "outputVideo": "work/<id>/scene_video_only.mp4",
    "assets": {
        "hdri": "work/<id>/hdri.hdr"
    }
}
```

`assets` is whatever your scene actually needs — HDRIs, GLBs, PBR texture
sets, VRMs, audio. Declare only what the scene uses; there is no required
set.

**Asset injection is raw bytes.** Point each asset at the real file —
`hdri.hdr`, `model_embedded.gltf`, `character.vrm`, `image.png` — not a
`*_b64.txt` sidecar. The engine reads the file and puts a `Uint8Array`
straight on `globalThis.ASSETS[key]`. `globalThis.b64toArrayBuffer(ASSETS.key)`
passes that through to an `ArrayBuffer`. GLTFLoader parses asynchronously
with callbacks or `parseAsync(buffer, '')`; HDRLoader's `parse(buffer)` is
synchronous. See the examples below and in [assets](assets.md). Handing a
loader base64 text instead of HDR bytes yields "no header found".

## Minimum scene script

```js
globalThis.setup = async function () {
    // Renderer — adapter + device props keep the frames from rendering black
    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: true,
        adapter: GPU_ADAPTER, device: GPU_DEVICE,
    });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    await renderer.init();

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.1, 200);

    // Build the world your piece needs here — HDRI sky + lighting, terrain
    // or interior, props, characters (or none of those, if the piece is
    // abstract / pure motion graphics / something else entirely).

    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
};

globalThis.renderFrame = async function (t) {
    // If you applied CustomEffectsDeno: _fx.update(t) only pushes effect
    // uniforms — it does not render. The scene render still happens every
    // frame, after it (an if/else here that skips renderAsync when _fx
    // exists produces a frozen video; the harness renders and warns as a
    // safety net, but write it straight).
    if (globalThis._fx?.update) await globalThis._fx.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
```

Use the declared assets in real setup/helper code. The runner records accesses
to `ASSETS` through a Proxy; writing an asset name in a comment does not load
or use it. The current static name scan does not enforce missing references.
Neither a name match nor an asset read proves the asset is visible in a frame.

The frame callback receives `renderFrame(t, frameIndex)`, with time in seconds.
The second argument is an integer frame index, not delta time. For the fixed
render rate, use `dt = 1 / FPS` when a system requires a time step. An optional
`globalThis.cleanup` hook releases scene-owned resources after the frame loop;
follow each system's update and disposal instructions.

Scene scripts are eval'd, not loaded as modules — top-level `import` throws;
all imports go inside `setup()` via `await import(...)`.

## HDRI lighting (the reusable pattern)

HDRI provides ambient lighting and IBL reflections. This example sets the
environment only. You can also use an environment as a visible background;
choose the world-space sky when the piece needs spatial clouds, atmosphere
and time-of-day motion rather than a distant panoramic image.

```js
const { HDRLoader } = await import('npm:three@0.184.0/addons/loaders/HDRLoader.js');
const hdr = new HDRLoader().parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.hdri));
// 1) CPU row-flip — DataTexture.flipY is ignored on WebGPU; without this
//    the equirect is upside-down and the key light comes from the ground.
const rowLen = hdr.width * 4, Ctor = hdr.data.constructor;
const flipped = new Ctor(hdr.data.length);
for (let y = 0; y < hdr.height; y++)
    flipped.set(hdr.data.subarray(y * rowLen, (y + 1) * rowLen), (hdr.height - 1 - y) * rowLen);
const hdriTex = new THREE.DataTexture(
    flipped, hdr.width, hdr.height,
    THREE.RGBAFormat, hdr.type || THREE.HalfFloatType,
);
hdriTex.mapping = THREE.EquirectangularReflectionMapping;
hdriTex.minFilter = THREE.LinearFilter;
hdriTex.needsUpdate = true;
// 2) pmremTexture rather than plain scene.environment — the raw equirect
//    gives checkerboard mip artifacts on opaque PBR and near-black metals.
scene.environmentNode = THREE.pmremTexture(hdriTex);   // lighting only
// The engine also provides a dim fallback environment when none is supplied.
// Choose an environment or light rig that produces the intended material response.
```

**Visible sky / horizon:** the [world-space sky system](sky-weather.md)
provides sky, clouds, sun/moon and stars. An interior can use an enclosure
with windows onto that world. A studio or abstract piece can use a solid
background, gradient or shader dome. Choose what supports the composition.

## What's on `globalThis` when your script runs

**Engine:** `WIDTH`, `HEIGHT`, `FPS`, `DURATION`, `TOTAL_FRAMES`, `canvas`,
`GPU_ADAPTER`, `GPU_DEVICE`, `ASSETS[key]` (raw `Uint8Array` per your assets
map), `b64toArrayBuffer(x)`, `EIDOVERSE_DIR`.

**Three.js:** `THREE` — three@0.184.0 (WebGPU build + TSL), plus
`RaymarchingBox`, `SkyMesh` TSL utilities. You build renderer / scene /
camera yourself and assign `_r` / `_s` / `_c`. Per frame the render is
`await _r.renderAsync(_s, _c)` — the async variant, every frame.

**GLB / VRM loading:** `GLTFLoader` (auto-wires `VRMLoaderPlugin` +
`DRACOLoader`, and auto-converts GLB textures to DataTextures — Deno's
WebGPU bindings lack `copyExternalImageToTexture`), `VRMLoaderPlugin`,
`MToonNodeMaterial`, `VRMUtils`, `VRMAnimationLoaderPlugin`,
`createVRMAnimationClip`, `__DRACO_LOADER__`. After GLTFLoader parses a
VRM, `globalThis._vrm` is auto-captured.

**Loading mode matters:** use the pattern in each system's guide.

| Availability | Systems |
| --- | --- |
| Injected globals | Placement, character controllers, navigation, modular robotics/FabSim, creatures, Clippy, books, screens, particles/morphs, terrain, flora, SeedThree, procedural materials/layers, lofts, SDF/iso fields, low-level sky/weather and the effects registry |
| Dynamic ESM import inside `setup()` | `fluid_swe`, `fluid_sim`, `fluid_water`, `fluid_grid`, `cloth_sim`, `text_3d`, `cloud_spatial` and individual addons |
| Explicitly loaded facade | `sky_worlds.js`, which installs `makeSky` and composes the world package |

The prefix `make` alone does not establish that a function is already loaded.
Use the [tool inventory](../docs/TOOLS.md) to find its guide. `loadImageTexture`
and `loadCanvasImage` are also supplied by the renderer for native image loading.
Absolute local asset filenames are accepted; reference reusable assets in place.
