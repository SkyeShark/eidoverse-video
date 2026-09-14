# Motion graphics, screens, subtitles and 3D text

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose the anchor before making a graphic: an in-world screen uses
`makeScreen`; a broadcast title, lower third or subtitle uses the separate
scene returned by `makeOverlayLayer`. Both are available as renderer globals.

## In-world screens and ASCII panels

```js
const ui = makeScreen({
  width: 0.64, height: 0.36, px: 768,
  draw(ctx, t, w, h) {
    ctx.fillStyle = '#071b22'; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#c6f4ef';
    drawTextFit(ctx, 'SYSTEM READY', {
      x: w / 2, y: h / 2, maxWidth: w * 0.8, maxHeight: h * 0.5,
      font: 'bold 64px sans-serif', align: 'center'
    });
  }
});
ui.applyTo(displayMesh); // the actual GLB display surface
```

`applyTo` also accepts a model and searches for a screen/display/monitor/LCD
mesh. Pass the exact mesh when the model has several. It handles the glTF UV
orientation; inspect unusual assets before using its `flip`/`mirrorX` options.
One screen instance drives one surface. After `applyTo`, do not also add
`ui.mesh`; for a new standalone screen, add that mesh instead.

`makeScreen` returns `mesh`, `material`, `texture`, `canvas`, `ctx` and
`update(t)`. It auto-updates in the engine; use `auto:false` for manual control
or `fps` to limit redraw frequency. Default displays are unlit with exact UI
colors. Use `lit:true` when the surface should respond to scene lighting.
Maintain canvas/mesh aspect ratio and central text margins; review the camera's
closest approach so labels remain readable. Do not copy pixels to flip text.

`makeAsciiPanel(asciiText, options)` uses the same screen system for multiline
terminal art. Use supported fonts; the effect registry provides reusable
CRT/glitch styling, while the screen draw callback can author its own content.

## Frame overlays

```js
const hud = makeOverlayLayer({fov: _c.fov});
const caption = makeScreen({
  width: 0.9, height: 0.14, px: 1024, transparent: true,
  draw(ctx, t, w, h) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#ffffff';
    drawTextFit(ctx, subtitleAt(t), {
      x: w / 2, y: h / 2, maxWidth: w * 0.84, maxHeight: h * 0.8,
      font: '48px sans-serif', align: 'center'
    });
  }
});
hud.add(caption.mesh);
caption.mesh.position.set(0, -0.32, -1);
```

Supply `subtitleAt(t)` from actual narration/lyric timings. `makeOverlayLayer`
owns an independent overlay scene/camera; do not parent the graphic to the
moving world camera. At z=-1 its half-height is `tan(fov/2)`, with half-width
multiplied by output aspect ratio. Keep graphics within that frustum and text
safe areas. Aspect and positions in this snippet are illustrative.
The helper installs `globalThis._overlayScene` and `_overlayCamera` for the
renderer; scene code normally interacts with the returned overlay group.

World effects composite before the overlay; signal effects can composite
after it. `nuclear_explosion`, `godrays` and `underwater` stay under it;
`depth_fog` and `retro_wireframe` default under; other effects default over.
For switchable effects set `opts[effect].layer` to `under` or `over` through
`CustomEffectsDeno.applyTo`. Read [postprocessing.md](postprocessing.md).
Avoid coplanar overlay elements and keep the central frame available for the
subject. Adjust tint/glitch uniforms on beats; preserve text legibility.

## Video displayed inside the scene

```bash
node eidoverse/video_to_sprite.mjs work/<id>/clip.mp4 --fps 12 --width 256 --height 144 --max-frames 120 --output work/<id>/screen_clip
```

Declare the resulting JPEG atlas and `_info.json` as assets, then:

```js
const info = JSON.parse(new TextDecoder().decode(ASSETS.video_info));
const texture = await loadImageTexture(ASSETS.video_atlas, {srgb: true});
const screen = makeVideoScreen({texture, info, width: 1.6});
_s.add(screen.mesh);
```

`makeVideoScreen` handles the frame UV offsets automatically. The converter
requires Node and FFmpeg and only includes the selected frames; choose atlas
resolution/length deliberately. Use a second screen instance for a second
surface instead of sharing mutable texture offsets accidentally.

## Satori layouts

For a complex static layout, dynamically import `rasterizeUI` from
`EIDOVERSE_DIR + 'render_common.mjs'`. Its signature is
`await rasterizeUI(jsxTree, width, height, fonts)` and its result is top-down
RGBA bytes. Supply a JSX-like Satori tree and real font buffers. Defaults
refer to Linux DejaVu paths, so supply fonts explicitly on other systems.
Place the pixels into a canvas once, then present it through the same screen
or overlay system; do not invert rows or build a second per-frame compositor.

`eidoverse/satori_ui.mjs` is a standalone older demonstration with hard-coded
Linux font paths and its own renderer. It is not a `satori_ui.render()` library
or a scene global. `render_common.mjs` also exports the CPU `alphaComposite`
utility; the normal scene path composites overlays on the GPU.

`eidoverse/lyric_renderer.py` is the older Python `LyricRenderer` frame-overlay
utility. For the native film path, use aligned timestamps with the overlay
above. [audio.md](audio.md) covers alignment, narration and final mixing.

## Extruded type

```js
const {createText3D} = await import(EIDOVERSE_DIR + 'text_3d.js');
const title = await createText3D('EIDO', {
  fontPath: 'eidoverse/assets/fonts/Audiowide-Regular.ttf',
  size: 0.4, depth: 0.04, curveSegments: 6,
  bevelEnabled: true, bevelSize: 0.004, bevelThickness: 0.004,
  material: new THREE.MeshStandardNodeMaterial({color: '#b6d8d5', roughness: 0.4})
});
_s.add(title);
```

Choose a real font path with the required glyphs. Do not assume container font
paths exist on the native machine; bundled display fonts are under
`eidoverse/assets/fonts/`. Use extruded text when its thickness and
lighting matter; use the screen/overlay paths for flat UI. `ParticleMorph.fromText`
is documented in [particles-fx.md](particles-fx.md) for point-cloud lettering.

## Native canvas images and optional Python overlays

`await loadCanvasImage(ASSETS.image)` decodes an image for the native canvas
context's `drawImage` method. Use it for collages, screen artwork or images
alongside typography; it supplies a canvas-compatible image rather than a
Three.js texture. Load it once during setup, then draw it in a screen callback.

```js
const illustration = await loadCanvasImage(ASSETS.illustration);
const panel = makeScreen({ width: 1.2, height: 0.8, px: 1024,
  draw(ctx, t, w, h) { ctx.drawImage(illustration, 0, 0, w, h); }
});
scene.add(panel.mesh);
```

The older `LyricRenderer` is a separate Pillow utility for offline frames,
not part of the native render loop. It takes `align_lyrics.py` JSON:

```python
from eidoverse.lyric_renderer import LyricRenderer
captions = LyricRenderer('work/<id>/lyrics_aligned.json', width=1280, height=720,
                        font='eidoverse/assets/fonts/Audiowide-Regular.ttf',
                        font_size=42, min_duration=1.2, max_gap=0.6,
                        fade_duration=0.2)
frame = captions.draw(frame, t)  # frame is a Pillow image; t is seconds
```

Install Pillow and NumPy, and supply an existing font path; its named/default fonts refer
to the old Linux container. No standalone CLI is implemented. Keep source
frames if using it, and inspect the composite's timing, alpha and color.
For native in-scene captions the overlay approach above shares the renderer's
compositing and avoids a separate frame-processing pass.
