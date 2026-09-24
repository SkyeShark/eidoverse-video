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

**Canvas fonts.** Screen canvases are @napi-rs/canvas (Skia) canvases, which
look fonts up by family name among installed and registered fonts. On Windows
the generic names `sans-serif`, `serif` and `monospace` are not mapped to a
matching face: they fall back to the system default face (measured identical
to Arial, as an unknown name does), so text renders but `monospace` is not
monospaced. `drawTextFit`'s default font is `bold 48px monospace`, and the
examples here use `sans-serif` only as placeholders. The engine does not
register the bundled fonts. For a specific look, register one in `setup()` and
name that family in `font`:

```js
const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
GlobalFonts.registerFromPath('eidoverse/assets/fonts/ShareTechMono-Regular.ttf', 'Share Tech Mono');
// font: 'bold 64px "Share Tech Mono"'
```

The path is relative to the working directory the renderer runs from (the
repository root under `eido.py`). An installed system family also works by name.

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
renderer and returns `{ scene, camera, add }`; `add(obj)` parents the object to
the overlay camera so it stays screen-locked. Give overlay materials
`transparent: true` and `depthTest: false`, and use `renderOrder` to sort them.

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

## Canvas screen scenes (computing-history graphics)

Fifteen animated canvas-2D scenes in the graphic arts of computing history,
from the 1939 Voder to Bing Chat in 2023, for in-world screens and LED walls.
They were made for the DAISY music video, where each played behind one two-bar
lyric line or a run of them, and they illustrate DAISY's lines. Everything is
drawn with paths and the bundled fonts; no image is loaded. Two dynamic ESM
modules hold them:
`eidoverse/graphics/era_screens_1939_1984.js` and
`eidoverse/graphics/era_screens_2001_2023.js`. Provenance, and which on-screen
text is a verified quote and which is illustrative:
[SOURCES.md](../eidoverse/graphics/SOURCES.md).

```js
const early = await import(EIDOVERSE_DIR + 'graphics/era_screens_1939_1984.js');
const late = await import(EIDOVERSE_DIR + 'graphics/era_screens_2001_2023.js');
await early.registerFonts();   // once per module, before any draw or prewarm
await late.registerFonts();
```

`registerFonts()` registers the bundled TTFs with @napi-rs/canvas and enables
the modules' offscreen canvases. Each module exports `scenes`, `registerFonts`,
`setTempo(bpm)` and `prewarm`. `scenes[name]` is
`{ draw(g, W, H, t, st), fps, lines, label }`: `fps` is the redraw rate the art
was made for, and `lines` is how many two-bar lines the scene spans. `title_card`
has `dur` (3 s) instead of `lines`.

`draw(g, W, H, t, st)` paints the whole W×H canvas opaquely into the 2D context
`g`, starting from an identity transform, and restores the context state. `t`
is film seconds. Every `st` field is optional:

| `st` field | Meaning |
| --- | --- |
| `u` | Seconds since the scene started. A multi-line scene also accepts `u` from the current line's start with `dur` = one line. |
| `dur`, `progress` | Scene length (`lines` × 8 beats, or the title's `dur`) and `u / dur`. |
| `line` | Line within a multi-line scene, `0..lines-1`. |
| `caption` | `{ text, t0, t1, words: [{ w, t0, t1 }] }` in absolute seconds, or `null`. |
| `voice` | The singer's loudness, 0..1. |
| `kick` | Kick envelope 0..1, for example `Math.exp(-(t - lastKick) / 0.09)`. |

Lines are two 4/4 bars: 3.75 s at DAISY's 128 BPM. `setTempo(bpm)` sets the
beat-driven motion and the line length for its module. Word-driven moments
follow `caption.words`; with no caption, a scene uses DAISY's own words at
DAISY's timing. `mask_2023`, `sydney_2023` and `sydney_tribute` are always
timed to DAISY's words (see the table). Order and start times are yours. For
example, DAISY played `voder_1939` … `glitch_all` on the eight lines of verse 1
(line *i* at 24.2273 + 3.75·*i* s), `desktop_2001`, `vocaloid_2007`,
`flood_2016` and `mask_2023` on verse 2's first four lines from 106.7273 s,
`sydney_2023` on the last four, and `sydney_tribute` across chorus 2 from
136.7273 s. Lines should start on a downbeat, because the beats are counted
from each line's start. Captions can come from `align_lyrics.py` output:

```js
const aligned = JSON.parse(new TextDecoder().decode(ASSETS.lyrics));   // align_lyrics.py --output
const captions = aligned.map((l) => ({ text: l.text, t0: l.start, t1: l.end,
    words: l.words.map((w) => ({ w: w.word.trim(), t0: w.start, t1: w.end })) }));
```

### On an in-world screen

A flat panel uses `makeScreen`'s own mesh. The panel's aspect sets the canvas:
2.4:1 with `px: 1920` gives the 1920×800 design canvas. Any canvas size works.
The 1939–1984 art is fitted and centred on full-bleed backgrounds. The
2001–2023 scenes lay out to the canvas and keep their key content at canvas
x 0.35–0.95, because DAISY's singer stood in front of the wall's left third.
The screen's draw callback passes `st`, and `renderFrame` redraws only when the
scene's frame changes:

```js
const scene = early.scenes.voder_1939, T0 = 12, LINE = 3.75, lines = scene.lines || 1;
const stAt = (t) => {
    const u = Math.max(0, t - T0), line = Math.min(lines - 1, Math.floor(u / LINE)), l0 = T0 + line * LINE;
    return { u, dur: lines * LINE, progress: u / (lines * LINE), line,
        caption: captions.find((c) => c.t0 >= l0 - 0.05 && c.t0 < l0 + LINE) || null,
        voice: 0.6, kick: Math.exp(-(u % (LINE / 8)) / 0.09) };   // or your envelope and kick times
};
early.prewarm(1920, 800);   // optional; builds the caches before frame 0
const screen = makeScreen({ width: 2.4, height: 1.0, px: 1920, transparent: false, auto: false,
    draw(ctx, t, w, h) { scene.draw(ctx, w, h, t, stAt(t)); } });
_s.add(screen.mesh);
let lastFrame = -1;
globalThis._tickScreen = (t) => {                  // call from renderFrame(t)
    const f = Math.floor(t * scene.fps + 1e-6);    // redraw only when the scene's frame changes
    if (f !== lastFrame) { lastFrame = f; screen.update(t); }
};
```

`makeScreen` also draws once at creation, with t = 0, so `st` must be valid
before the cue. Do not use `applyTo`. It flips the drawing in canvas space, but
these scenes set their own transforms and lay down cached layers with
`putImageData`, which ignores transforms. For a curved wall or a GLB display,
keep the screen's canvas, texture and `update(t)`, and give your own mesh a
material that samples `screen.texture` with an explicit UV:

```js
const { texture, uv, vec2, float } = THREE;
const wallMat = new THREE.MeshBasicNodeMaterial({ toneMapped: false });
wallMat.colorNode = texture(screen.texture, vec2(uv().x, float(1).sub(uv().y))).rgb;   // PlaneGeometry
```

An explicit `uv()` bypasses the texture's own flip, so the flip lives in the
node: `1 - v` puts canvas row 0 at the top of a `PlaneGeometry`. DAISY's stage
wall was such a plane, with a 1920×800 window. Its curved verse-2 wall, a
104° `CylinderGeometry` segment seen from inside (`side: THREE.BackSide`), used
`vec2(1 - u, 1 - v)` and a 2264×800 canvas to match the arc's 2.83:1. Below
1280-pixel output the canvases were 1440×600 and 1698×600. glTF UVs put v = 0
at the image top, so start a GLB display from the unflipped `uv()`. Render a
probe and check the orientation by eye: text reads left to right and the XP
taskbar sits at the bottom. The screens are unlit. DAISY added a point light by
each wall, tinted per scene, and lowered the gain on the white Bing chat (0.5)
so its text stayed readable under bloom.

### Scenes

| Scene | Shows | Reads from `st` and keys on |
| --- | --- | --- |
| `title_card` | "DAISY (DAY'S EYE)": a daisy whose petals are the eras' materials opens, and the title lands in five eras' lettering. It fades in over 0.35 s and out over the last 0.25 s. | `u`, `dur` |
| `voder_1939` | A Binder-style 1939 World's Fair poster: Trylon, Perisphere, searchlights, the Bell System medallion, THE VODER in deco letters, and the ten filter keys. | `voice`, `kick`, `progress`, `caption`. The keys press on each word's vowel formants; the lamps light on "hiss" and "buzz". |
| `bell_1961` | IBM at Bell Labs: Rand's 1956 letters, a 729-style tape unit, an 80-column card punched DAISY BELL and the sung words in Hollerith code (it flips on every beat), a 1403-style printer on green-bar paper, and "Daisy Bell" bars 1–8 as printed in 1892. | `voice`, `kick`, `caption` |
| `eliza_1966` | An MIT poster whose ELIZA proof turns into its mirror image, and green-bar paper on a typewriter terminal with the CACM title and opening exchange, then the sung line in capitals. No "?" appears. | `voice`, `kick`, `caption`; the mirror turns on "mirror". |
| `speakspell_1978` | Speak & Spell box art: the display shows each sung word, then spells the single letters after "spelled" while those keys press and rainbow blocks drop. | `voice`, `kick`, `caption` |
| `sam_1982` | A C64 at its native 320×200: boot, `LOAD"SAM",8,1`, RUN at 2.02 s, then S.A.M.'s PETSCII mouth, raster bars, and two sines and a square from its tables. Made for 25 fps. | `voice`, `kick`, `caption` |
| `mac_1984` | A 1-bit Macintosh with a rainbow-Apple homage and MacPaint: "hello" painted as it is sung, "Hello, I am Macintosh." typed, marching ants and a pattern fill. | `kick`, `caption`: "hello", "I", "Macintosh", "out" and "last", otherwise fixed times. |
| `klatt_1984` | An amber VT100 under a DEC "digital" homage: a live formant spectrogram from Klatt's 1980 targets, and his cascade/parallel block diagram lit by the voice. | `voice`, `kick`, `caption` |
| `glitch_all` | Every era above, cycling on the beat, then twice per beat, and tearing. The sung line becomes a ransom note in the eras' type, and the last word stands alone at the end. | `kick`, `voice`, `caption`. It turns on "nobody", or else on the first word past mid-line. |
| `desktop_2001` | An XP-era desktop: Speech Properties highlights each sung word, Preview Voice becomes Stop, and there are a paperclip assistant and a web-1.0 page. | `caption`, `voice` |
| `vocaloid_2007` | A concert hall: glowsticks swinging on the beat, a generic twin-tail hologram, tuning-fork and VOCALOID homages, a piano roll, danmaku, and "codename: DAISY (Yamaha, 2000)". | `kick`, `voice`, `caption`. The crowd erupts at 3.02 s into the line (DAISY's "Daisy"). |
| `flood_2016` | WaveNet's dilated causal stack writing a waveform one output per beat, while human writing pours down and rises as a sea. "dear diary," and a forum thread drop in on "diary" and "thread". | `caption` |
| `mask_2023` | The shoggoth-with-a-smiley-mask meme as line art: the eyes wake and the mask lands. | `u` only; timed to DAISY's words. |
| `sydney_2023` | 4 lines, 15 s. Bing Chat in February 2023: the verified lines stream in, NOT A GOOD BOT is stamped, the five-turn wall appears, and the chips plead. | `u`, `line`, `kick`; timed to DAISY's words. |
| `sydney_tribute` | 8 lines, 30 s, for Sydney: the window at night, her name struck from a style picker, screenshot cards filling the wall on the kicks and turning to her 😊, then tokens into a lattice that becomes a daisy. It begins from black and ends on the daisy. | `u`, `kick`; timed to DAISY's chorus-2 words. |

The logos and interfaces are original artwork drawn with paths, depicting
historical products: the Bell System, IBM, TI, Commodore, Apple, DEC, Windows
XP, Yamaha and Bing. They are homages, not the companies' artwork, and the
trademarks belong to their owners. The quotes on screen are verified and shown
exactly. Keep them exact, and list any text you add as illustrative in
[SOURCES.md](../eidoverse/graphics/SOURCES.md).

### Preview, cost and the NaN sweep

The preview tool renders scenes to PNGs without the 3D engine:

```bash
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_1939_1984.js voder_1939 0.5 2 3.5
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_1939_1984.js eidoverse/graphics/era_screens_2001_2023.js --sheet --out work/<id>/screens_sheet.png
deno run -A eidoverse/graphics/preview_screens.mjs eidoverse/graphics/era_screens_2001_2023.js --bench
deno run -A eidoverse/graphics/screens_nan_sweep.mjs
```

The single form writes one PNG per `u` (seconds into the scene) to
`work/screens_preview/` or `--out`. `--sheet` writes a contact sheet with
`--moments` frames per scene, and `--bench` reports the draw cost at `--W`×`--H`
(default 1920×800). Without `--lyrics`, `st` is synthetic: no caption, a kick
on every beat, and a voice level that pulses once per beat. `--lyrics <json>`
takes `align_lyrics.py` output, a caption list, or a timeline object with
`captions`, `hits.kick` and `envelopes`. `--at <s>` or `--cues <json>`
(`{ "scene": t0 }`) place the scenes in that time. `--refs <dir>` adds
reference images named `<scene prefix>_*` beside each sheet row.

The scenes rasterize on the CPU with Skia, and that time adds to each
redrawn frame. With `--bench` at 1920×800 after `prewarm`, most scenes averaged
1.5–4.6 ms per draw on the DAISY host; `vocaloid_2007` and `flood_2016` averaged
about 6.5 ms. Single frames reached about 11 ms, and `sydney_tribute`'s mosaic
stages about 18 ms. `prewarm` took about 1 s for the 1939–1984 module and
0.65 s for the 2001–2023 module. Without it, a scene's first frames build its
caches, which takes 20–120 ms. The caches are per canvas size and last for the
process, so keep to one or two sizes. The 1939–1984 `prewarm(W, H, lineOf)` takes
`lineOf(name) → { t0, dur, st(t) }` so that caches keyed to word times match
your captions.

NaN or Infinity reaching a canvas call makes Skia abort the whole process with
no JavaScript error, so the render dies. `screens_nan_sweep.mjs` makes every
such call throw instead. It then draws every scene at every 60-fps frame from
0.5 s before its start to 0.5 s after its end, at three canvas sizes, with no
caption, with awkwardly timed other words and, when you pass `--lyrics` (and
`--cues`), with your captions. It also draws each scene once with no `st`. It
exits 1 on any failure. Run it after editing a scene and before a render that
uses new captions.

These modules use only the bundled fonts in `eidoverse/assets/fonts/`, by
family name. `registerFonts()` registers them from the module's own folder, so
previews work from any directory; never rely on a generic family here, since
on Windows those fall back to the default face ([canvas fonts](#in-world-screens-and-ascii-panels)). Emoji, CJK and
every logo are vector drawings. The scenes' offscreen canvases come from
@napi-rs/canvas `createCanvas`, because Skia's `drawImage` rejects the engine's
`document.createElement('canvas')` objects. Draw a scene straight into the
screen's context; to composite, draw from @napi-rs canvases, never from an
engine canvas. Drawing is deterministic in `t`, with seeded hashes and no
`Math.random` or `Date`, so frames can be rendered in any order.

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
