# Audio — music, SFX, narration, mix, merge, lipsync

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose music, ambience, voice, physical sound effects or silence for the
piece. Plan sound and image together, including intentional gaps. When voice
needs to be intelligible, listen to its balance against the actual bed; a
fixed gain difference is only a starting point, not a universal mix standard.

## Recommended music — MiniMax Music 3

Use `generate_song.py` for generated music, including instrumental
scores and songs with vocals. It submits a local ComfyUI workflow; no cloud
music account or API key is needed. The backend defaults to
`http://127.0.0.1:8188`; set `COMFYUI_URL` to its actual address if different.

**Check the backend and model selections first:**

```bash
python generate_song.py --probe
```

The probe exits 0 when the required node classes and configured model names
are available, or 1 with the missing dependencies/connection error. It does
not load weights, use the GPU or queue a song. Run a short generation to check
inference on the installed hardware. `generate_sfx.py --probe` separately
checks ComfyUI connectivity; it does not validate the Stable Audio workflow.

Install these files in ComfyUI's model folders, using the
[official ComfyUI MiniMax Music 3 model package](https://huggingface.co/Comfy-Org/MiniMax-Music-3):

| Folder under `ComfyUI/models/` | File used by this driver |
| --- | --- |
| `diffusion_models/` | `minimax_music3_dit_fp16.safetensors` |
| `text_encoders/` | `minimax_music3_text_encoder_pruned_int8_convrot.safetensors` |
| `vae/` | `minimax_music3_dav.safetensors` |

ComfyUI must provide `MiniMaxMusic3TextEncode` and
`EmptyMiniMaxMusic3LatentAudio`, alongside its loader, sampler, audio decode
and MP3 save nodes. The probe lists missing classes or model selections.
The graph is embedded in the driver; a separate custom-node music API is
not required. Match the filenames above or deliberately update the driver's
model constants to the compatible files you installed.

```bash
# Instrumental: omit lyrics. The output directory is created if needed.
python generate_song.py "Instrumental chamber-electronic score, warm marimba and soft synths, 96 BPM in D major; a quiet opening, rhythmic middle and a gentle resolution around 70 seconds" --max-duration 100 --seed 42 --out work/<id>/music.mp3

# Vocal song: caption first, then the actual words to sing.
python generate_song.py "Warm folk duet, acoustic guitar, 80 BPM, intimate and hopeful" "We leave a light beside the door, a little brighter than before" --max-duration 60 --seed 43 --out work/<id>/song.mp3
```

Put genre, instruments, vocal character, tempo, key and structure in the
free-text caption. Omit lyrics (or pass an empty string) for an instrumental.
Optional `--bpm` and `--key` append those requests to the caption; they are
musical guidance, not guarantees of the generated tempo or key.

For a short instrumental with explicit tempo, key and duration:

```bash
python generate_song.py "Instrumental marimba and soft synths, a playful phrase with a gentle resolution" --bpm 96 --key "D major" --seconds 24 --max-duration 30 --seed 42 --out work/<id>/music.mp3
```

For Python use, import `generate_song` from `generate_song.py`. Pass the
caption as `tags`, optional `lyrics`, `bpm`, `key` and `seed`, and choose
`max_duration`, `seconds`, `out` and sampler settings as keyword arguments.

`--max-duration` defaults to 120 seconds and caps the encoder's generated
conditioning. By default that conditioning's length determines the audio
latent; `--seconds` explicitly sets the latent duration instead. The
[ComfyUI nodes](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_music.py)
accept durations from 0.04 to 360 seconds. A ceiling or fixed latent length
does not guarantee a resolved musical ending. Describe the intended ending,
allow room for its decay, and inspect the actual duration and cadence before
timing a film. A short test can use `--seconds 24 --max-duration 30`.

### Prompting MiniMax Music 3 for a film cue

The text encoder plans the piece and its length from the caption; the audio
latent is then generated to that plan. Garbled output comes from a mismatch
between the two, not from the sampler settings (Night Shift, 2026-09-14,
ten takes measured):

- **Do not pin `--seconds` beyond what the caption plans.** A caption the
  encoder reads as a 20–30 s idea, pinned to `--seconds 64`, gives 64 s of
  audio whose second half disintegrates into dense, incoherent playing.
  Reserve `--seconds` for short pieces (roughly 30 s or less) or for a pin
  close to the encoder's own estimate.
- **Ask for length in the caption, with a timed structure.** "about 66
  seconds: a very quiet, sparse opening for the first 20 seconds; a slightly
  fuller but still calm middle from 20 to 45 seconds with the same gentle
  two-chord pattern; then it thins out and resolves on a soft sustained chord
  around 60 seconds, decaying into silence" produced a coherent 90 s take
  under `--max-duration 90`. The same brief without the timings came back as
  14–30 s pieces.
- **Set `--max-duration` above the target** (90 for a 66 s cue) and trim the
  result with a fade. The ceiling is not a target; the encoder can stop well
  short of it or run to it.
- **Planned length varies by seed.** Identical captions returned 28 s and
  90 s on different seeds. Generate several seeds, keep a log per take (the
  driver prints seed, ceiling and latent), and pick by measured duration.
- **For a calm cue, say so in structural terms.** "same pattern throughout,
  no build-up, no climax", a single named instrument and a stated final
  cadence hold; "a warmer swell" or "grows" turns the second half dense and
  chaotic. Negative lists ("no drums, no synths") are cheap and did no harm.
- **Measure before listening at length.** `ffprobe` for duration, then
  `ffmpeg -af astats` per second for RMS spread and onset density in the
  second half; the calmest take has the lowest spread and density there.

Generation defaults are `--steps 24`, `--cfg 1`, `--cfg-scale 1.5` and
`--top-k 50`. `--cfg` controls diffusion guidance; `--cfg-scale` and
`--top-k` control the text encoder's acoustic generation. Change `--seed`
for another take. Output is a 320 kbps MP3 at `--out` (default `song.mp3` in
the current directory); use distinct filenames to preserve earlier takes.
The queue/generation wait defaults to 900 seconds (`--timeout` overrides it).
A timeout leaves the ComfyUI job alone: inspect its printed prompt ID and
queue/history before submitting another job.

When a backend is unavailable, report that limitation and choose a supplied
recording, synthesized sound, TTS or another method with your collaborator.
Describe the sound by how it was actually made.

## Sound effects — `generate_sfx.py` (Stable Audio via ComfyUI)

Generate wind beds, footsteps, impacts, mechanical whirs, water and crowd
sounds. Generation time depends on the installed model, GPU and clip length.

```bash
python3 generate_sfx.py "<prompt>" <seconds> <category> <out.mp3> [seed]
# category: SFX (ambiences/loops: wind, rain, footsteps, room tone)
#           One-shot (single events: a thud, a door, a whoosh, an impact)
#           Music | Instrument (prefer generate_song.py for songs/scores)
python3 generate_sfx.py "steady wind through dry grass, open field, no music" 24 SFX wind.mp3
python3 generate_sfx.py "single soft body landing thud on stone, one-shot" 3 One-shot land.mp3
```

Describe the sound, not the scene ("slow footsteps through dry grass,
rhythmic rustling" rather than "a person walks sadly"). Adding "no music, no
melody" to ambience prompts keeps the model from drifting musical. Layer
clips into the final mix with `adelay` at the exact beat times + `amix
normalize=0`. Choose gains by listening: a quiet wind bed and a foreground
impact usually need different levels. Sound on a landing or machine movement
can communicate weight and timing; silence can also be deliberate.

## Narration — TTS

```bash
edge-tts --voice <voice> --text "narration line" --write-media raw.wav
python3 cyborg_stutter.py raw.wav final.wav   # glitch stutters — for spoken TTS
# for SUNG vocals (separated from a song with demucs):
python3 cyborg_voice.py vocals.wav final.wav  # tone-only filter — safe for lipsync
```

The two filters divide the work: `cyborg_stutter.py` breaks sustained notes,
so it suits spoken narration; sung vocals keep their sustains through
`cyborg_voice.py`. These provide existing recipes for preserving useful
timing. You can design other filters; inspect duration, pitch, tails and
alignment after processing, especially with `asetrate`, `atempo` or `aecho`.

A consistent voice helps establish a recurring character. Use voice filters
when the character or scene calls for that timbre; unfiltered speech is also
a valid choice. A deliberate voice change can be part of the performance.

**Diegetic voice effects** (gurgling underwater, muffled through a wall,
radio-thin) are a different thing from character-voice filters, and ffmpeg
is the right tool for them: a convincing underwater gurgle = `vibrato`
(pitch wobble) + fast `tremolo` (gl-gl-gl) + `lowpass` (muffle) + light
`aecho` (liquid). `lowpass` removes energy, so boost the processed voice
(~1.5–2×). For an effect that develops (clear → gurgling), `asplit` the
voice, `afade` the clean copy out and the processed copy in (crossfade),
then `amix normalize=0`. Water/rain/wind can be synthesized with
`anoisesrc` (pink/white) → `bandpass`/`highpass` → `tremolo`. Mux all audio
as a separate ffmpeg pass — the renderer outputs video-only.

## Mix balance — voice above bed

Explicit input weights and disabled normalization make gains easier to
control. This example starts with music below speech:

```bash
ffmpeg -i music.wav -i tts_with_silence_padding.wav \
    -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0:weights='0.3 1.0'" \
    -c:a pcm_s16le mixed.wav
```

These are relative gains applied to the existing input levels. `normalize=0`
does not guarantee intelligibility or prevent clipping. Listen, adjust gains
and inspect peaks; ducking or EQ may help when spectra overlap.

**Timing:** `adelay=<ms>|<ms>` places a stereo line at a chosen moment. A
narrated piece might spread lines across its arc; an opening monologue followed
by music can be equally intentional. Time the scene from the recording you use.

**Dynamics and endings:** compression, limiting, fades and hard cuts are
available choices. For a five-second fade, use
`afade=t=out:st=<duration-5>:d=5` when the duration is at least five seconds.
Listen to whether the fade preserves the musical cadence. Peak normalization
and a `tanh` waveshaper are different operations from a loudness-aware mix;
neither is a required finishing step.

## Merging onto the render — `merge_av.py`

Render the scene a touch longer than the audio, then mux:

```bash
python3 merge_av.py --video scene_video_only.mp4 --audio mixed_audio.wav --out scene_final.mp4
```

It trims the video to the audio with `-shortest`, and it refuses to
clone-pad a short render (`REFUSING TO MERGE — video is shorter than
audio`). Measure the audio first and give the video enough duration, allowing
for rounding. If you want a held final image, author that hold in the scene
instead of relying on an accidental frozen tail.

## Lipsync — a character visibly speaking or singing

```bash
# 1. split the mix. Stems land in <out>/htdemucs/<input-stem>/ — nested,
#    not next to the input — so reference the nested path.
python3 -m demucs --two-stems=vocals -o stems song.wav
#    → stems/htdemucs/song/vocals.wav  +  stems/htdemucs/song/no_vocals.wav

# 2. align. `lyrics` is a required positional and it is the TEXT ITSELF,
#    not a path — a filename "succeeds" and aligns that literal string as
#    the only lyric. The flag is --output.
python3 align_lyrics.py vocals.wav "$(cat lyrics.txt)" --output lyrics_aligned.json
#    or from python:  from align_lyrics import align_lyrics
#                     align_lyrics('vocals.wav', lyrics_text, method='chunked')

# 3. optional synthetic timbre — when the character concept wants it:
python3 cyborg_voice.py vocals.wav cyborg_vocals.wav   # (voice, not stutter)

# 4. visemes. lipsync.py is a MODULE with no CLI — a `python3 lipsync.py`
#    command exits silently having written nothing. Call it from python:
python3 -c "import json; from lipsync import get_viseme_timeline; \
json.dump(get_viseme_timeline('vocals.wav', fps=30), open('visemes.json','w'))"
```

**Gate the visemes to the aligned lyric windows.** demucs leaves
instrumental bleed in the vocal stem, so `get_viseme_timeline` reports mouth
motion through intros, solos and outros — the character sings along to the
piano. Zero every frame outside a line's `[start, end]` (a ~0.12 s pad each
side keeps the consonant attack and release):

```python
wins = [(l['start'] - 0.12, l['end'] + 0.12) for l in lines if l['text'].strip()]
for i, f in enumerate(timeline):
    if not any(a <= i / fps <= b for a, b in wins):
        for k in f: f[k] = 0.0
```

A closed mouth through an instrumental tail is also what makes a final shot
read as "the music continues without them" rather than "the animation
broke."

Use the viseme pipeline when the visible character is producing the voice.
Off-screen narration or music does not imply mouth movement for everyone in
frame. When a character is silent, preserve their intended expression/rest
pose; do not add a reset loop that erases it without supplying new animation.

**Driving visemes per frame:**
- Reset all visemes to 0 at the start of every frame before applying current
  values — blend shapes persist otherwise and build up cumulatively.
- Apply values directly — raw 0–0.35 range, no multiplier.
- Emotion expressions (happy/sad/angry) override mouth shapes, so they sit
  out during lipsync.

```js
globalThis.renderFrame = async function (t) {
    if (globalThis._vrm?.expressionManager) {
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach(k =>
            globalThis._vrm.expressionManager.setValue(k, 0));
        const v = globalThis._visemes?.[Math.floor(t * FPS)];
        if (v) Object.entries(v).forEach(([k, val]) =>
            globalThis._vrm.expressionManager.setValue(k, val));
    }
    // ...effects update + renderAsync...
};
```

`claude_suit.vrm`'s mouth is a special case (raw morphs, not expressions) —
its render-verified recipe lives in [characters.md](characters.md).

## Example workflow: a character performance music video

1. Generate or choose a song and measure its duration.
2. Separate vocals with demucs if needed; align the actual lyric text.
3. Apply any desired voice treatment, then generate visemes from the matching
   vocal timing and gate them to the sung windows.
4. Build a scene and choreograph performance, camera and environment around
   the song's structure. Use the movement controller for grounded VRM travel.
5. Add readable captions if they serve the piece, using the native overlay
   workflow in [motion-graphics.md](motion-graphics.md).
6. Review image, sound and synchronization together, including the ending.

Instrumental films and other forms can use a different workflow. A singer,
captions, a fixed shot count and a fadeout are not prerequisites for a video.

## Supporting services and timing utilities

- `align_lyrics.py` creates word/lyric timing from vocal audio for captions.
  Use `lipsync.py`'s imported functions for mouth animation; it is not a
  standalone viseme JSON CLI. Keep speech and matching timings together.
- `bake_weather_audio.py` turns the weather system's event timeline into a
  WAV; its recording and bake workflow is in [sky-weather.md](sky-weather.md).
- `eidoverse/comfy_bridge.py` is an optional TCP bridge for a container client
  that needs to reach a host ComfyUI. Native rendering can use the backend
  directly. The bridge listens on all interfaces by default; starting it is a
  separate networking operation, not a prerequisite for reading these guides.
- `eidoverse/lyric_renderer.py` exposes the older `LyricRenderer` Python
  frame-compositing utility. Current scene subtitles use the engine overlay
  path in [motion-graphics.md](motion-graphics.md); do not import the Python
  renderer into a scene or assume it is part of the native frame loop.

External music/SFX availability depends on the selected ComfyUI workflow and
installed models. A connectivity probe does not prove all generators work.
Use the selected tool's real error output to diagnose failures. A supplied
recording or another agreed sound-making method can keep the piece moving.
