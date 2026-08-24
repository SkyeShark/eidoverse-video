---
name: eidoverse
description: Produces finished 3D videos with the Eidoverse toolkit - an agent-operated film studio (worlds, VRM characters, robots, weather, physics, cameras, audio, captions) rendered via Deno + WebGPU + three.js on the local GPU. Fire when the user asks to make a video, render a 3D scene, animate a character or robot, or mentions eidoverse. Bootstraps the environment, runs the probe-iterate-render loop, and hands off a playable mp4. Reads AGENTS.md as the full production contract before writing any scene.
---

# Eidoverse - vibe code a finished 3D video

## Outcome

A playable mp4 on disk at the configured resolution: 3D scene + camera work +
audio filling the runtime + a story arc. The session ends with that file
verified frame-by-frame and by waveform, or with a concrete named blocker.
"It rendered without errors" is the floor, never the finish line.

## The contract comes first

Read `AGENTS.md` at the repo root completely before writing a scene. It is
the single agent-facing contract: the API surface, the production rules, and
the anti-patterns paid for across hundreds of sessions. This skill is the
entry ramp; AGENTS.md is the studio. Every rule below exists because skipping
it produced a broken render.

## Bootstrap (once per machine)

```bash
# Deno is PINNED at 2.8.1 - 2.9.x corrupts the TSL effects path into banded
# gradients while every audit passes. Judge a new stack by a rendered FRAME.
curl -fsSL https://deno.land/install.sh | sh -s v2.8.1     # (Windows: see docs/SETUP.md)
python3 eido.py bootstrap    # materialize node_modules from deno.lock
python3 eido.py doctor       # deno / ffmpeg / rapier / backends health check
python3 eido.py render eidoverse/examples/basic_vrm.json   # smoke test
```

Set the encoder for the machine before rendering: `RENDER_CODEC=h264_nvenc`
(NVIDIA), `h264_videotoolbox` (macOS), or `libx264` (portable). ffmpeg
without nvenc fails silently late - doctor reports it up front.

## The loop that ships

1. **Plan 4-6 visual phases before code** - intro, build, climax, resolve.
   Set `duration` from the format (landscape 45-90s) and from the mixed
   audio length, audio first when narration exists.
2. **Write `work/<id>/scene.json` + `scene.js`** - all work lives in
   `work/<id>/`; the `eidoverse/` engine stays untouched.
3. **Probe before committing**: `python3 eido.py render <cfg> --probe` for a
   single frame. For mid-film beats, add a time-offset hook at the top of
   `renderFrame` - `t += Number(Deno.env.get('T_OFFSET') || 0)` - and render
   a short window that ENDS on the beat (creatures, sky, and shadow maps
   need ~1.5s of warm-up; a frame-0 probe of a creature looks catastrophically
   broken and is not).
4. **Look at the frames with your own eyes.** The audit digest measures
   physics; the probe frames show how it looks. Both together are the loop.
5. **Full render, then verify**: ffprobe both streams, extract frames at
   every beat, render the audio waveform, and watch the mp4 when multimodal.
   Fix the specific broken thing and re-render - never the whole piece.

## Hard-won field notes (each one cost a broken render)

- **Camera far plane vs the sky**: `makeSkySystem`'s cloud dome sits at
  ~3200 m. A camera far plane below that clips the entire sky to black while
  the ground renders normally. Set far >= the dome radius (9000 is safe).
- **`merge_av.py` hardcodes nvenc**: on non-NVIDIA machines re-run its
  printed ffmpeg command with your encoder, keeping its tpad/-shortest shape
  intact - never hand-roll clone-padding beyond what it prints.
- **Canvas glyphs**: the Deno canvas shim's fonts lack `▸` and similar
  glyphs (they render as tofu boxes on `makeScreen` panels). Use ASCII.
- **T_OFFSET shifts `renderFrame` time only** - `makeScreen` draw callbacks
  run on real engine time during probes, so typed-screen content verifies
  only in the full render.
- **No ComfyUI is a supported path, not a failure**: narration via
  `uvx --from edge-tts edge-tts --voice <v> --text "..." --write-media out.mp3`
  (zero install), ambience via ffmpeg `anoisesrc` filters, voice mixed
  6-9 dB above beds with `amix=...:normalize=0` and explicit weights.
  Degrade honestly; never fake a tool's output.
- **Captions need no transcriber**: edge-tts narration goes through
  `uv run tts_captions.py narration.json --out-dir work/<id>/audio` — the
  synthesis stream's WordBoundary events emit voice AND word-timed
  `captions.json` in one command, spelling exact by construction. Voice
  from any other TTS: force-align the known script with `align_lyrics.py`.
  Feed either output straight to `makeCaptions({ words, layer, style })`.
  Pass your existing `makeOverlayLayer` handle - a second `makeOverlayLayer`
  call replaces the overlay globals and orphans the first.

## Non-negotiables from the contract (checklist form)

- Audio fills the whole runtime, voice above bed, spread to the end.
- Fetch real assets before building from primitives; read every preview
  image before placing; place with `placeOn`/`placeTouching`/`snapToGround`,
  never raw coordinates.
- NodeMaterials only; no per-frame CPU loops; no top-level imports in scene
  scripts; `renderAsync` every frame, never behind an `else`.
- VRM speech on screen requires driven visemes. Locomotion goes through the
  character controller. One eased camera move per shot.
- End with `work/<id>/<name>_final.mp4` playable on disk, techniques
  appended to `techniques_archive.md`, or a concrete blocker named.
