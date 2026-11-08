# Audio — music, SFX, narration, mix, merge, lipsync

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose music, ambience, voice, physical sound effects or silence for the
piece. Plan sound and image together, including intentional gaps. When voice
needs to be intelligible, listen to its balance against the actual bed; a
fixed gain difference is only a starting point, not a universal mix standard.
Real recorded foley (CC0, e.g. freesound) comes before generated effects:
the episode mixes are built from recorded clips.

## In the Blender edition

Every audio tool here carries over unchanged. They are host-side Python run
in the system Python: `generate_song.py`, `generate_sfx.py`, `merge_av.py`,
`align_lyrics.py`, `lipsync.py`, `cyborg_voice.py`, `cyborg_stutter.py`,
`bake_weather_audio.py`, `eidoverse/comfy_bridge.py`, and the
[voicebox](voicebox.md) and [synthkit](synthkit.md) packages. Blender 5.2's
own Python has numpy but no scipy, numba, soundfile, whisper or demucs, so
these never run inside Blender. They write WAV and JSON, and
`eidoblend.media.audio` places them on the film's frames:

| Job | Blender edition |
| --- | --- |
| Put a sound on the timeline | `audio.add_sound(scene, path, t=…)`, a sound strip. A sequencer holding only sound strips leaves the 3D render in place (measured 11-07). |
| A mix's event list (foley hits, page turns) | `audio.place_events(scene, [{t, clip, gain, pan}])` |
| Beats and cues | `audio.add_markers(scene, times, prefix='kick')` |
| Sound in the render | `audio.mux_settings(scene)` before a video render: H.264 with AAC 320k, 48 kHz, in one pass. Or stay video-only and use `merge_av.py`. |
| A mixdown of the strips | `audio.mixdown(scene, 'work/<id>/mix.wav')` (WAV, FLAC, MP3, AAC by extension) |
| A mouth that sings | `audio.prepare_visemes` + `audio.key_expressions` ([lipsync](#lipsync--a-character-visibly-speaking-or-singing)) |
| Subtitles on the frame | `eidoblend.media.lyrics.LyricRenderer` (`lyric_renderer.py`, ported) or DAISY's ASS route ([below](#karaoke-captions-on-a-blender-film--the-ass-route)) |
| Weather sound | `eidoblend.media.weather_audio` records over Blender frames, `bake_weather_audio.py` bakes ([below](#supporting-services-and-timing-utilities)) |

Time follows the film convention: frame 1 is 0 s (`eidoblend.media.timebase`).
A film that starts partway into a song sets `scene['eido_frame0'] = 1 −
round(t_start × fps)`: frame 1 is then `t_start` in the song's time, and the
song's excerpt for a video-only render starts at `t_start` too, not one frame
earlier.

**`audio.mixdown` runs in a child Blender.** Blender 5.2 runs
`bpy.ops.sound.mixdown` as a window-manager job on its own thread. The
operator returns FINISHED before the file exists: measured 11-07, it took
8 ms, and 15 s of 48 kHz stereo was on disk 0.4 s later. Without an event
loop (a background run, or a script that keeps the UI busy) the job is never
ended, so only a session's first mixdown writes anything; every later one in
the same session wrote no file at all. So `mixdown` saves a copy of the
.blend, runs one mixdown in a child Blender (the same binary, with
`--factory-startup` when this session had it), waits until the file is
complete and returns. Measured: WAV S24, FLAC, MP3 and WAV S16 in a row from
one session, each 15.00 s, 1 to 2 s apiece. A script that calls
`bpy.ops.sound.mixdown` itself must wait for the file and must not expect a
second one.

### Every tool, run on this branch

Measured 11-07 on the Blender branch, unchanged, with Blender-edition
outputs (`blender/tests/media2/tools_host.py`, then
`test_tools_film.py` in Blender):

| Tool | What ran | Into the Blender film |
| --- | --- | --- |
| [synthkit](synthkit.md) | its guide's quick start: an 8-bar loop at 128 BPM, mastered, 17.0 s, 32 kick times (9.8 s to render) | a sound strip; the kick times as 32 markers |
| [voicebox](voicebox.md) | its guide's quick start: "Daisy Daisy give me your answer do", handmade, 7.64 s, 184 viseme frames at 24 fps | as round one's probe: keyed onto claude.vrm |
| `eidoverse/examples/daisy/` | `song.py --upto chorus2 --no-tts` (168.7 s, −14.0 LUFS, peak −2.2 dBFS), `captions.py` (43 captions to ASS; `--preview`, the CQT lyric video), `analyze.py` (LUFS per stem and section; `--asr` below) | the era screens' timeline and captions; the song under the EEVEE film; its ASS burned onto it |
| `lipsync.py` | `get_viseme_timeline` on DAISY's lead stem, chorus 1 (69–84 s): 450 frames at 30 fps in 0.1 s, values capped at 0.35. Mouth openness correlates 0.60 with the song's own phoneme-exact visemes (a 1/6 s smoothing) | keyed onto claude.vrm with `divide=0.35`, gated to `align_lyrics.py`'s lines: 362 frames per expression, read back exactly, open at 70.46 s, shut between lines |
| `align_lyrics.py` | the same excerpt and its four lines, Whisper medium (the default), chunked, on the CPU: 14 s, coverage 0.94, line starts within 0.48 s of the song's own (mean 0.29). Whisper small heard less (coverage 0.56) and placed "Daisy Daisy" 3.1 s late | the visemes' windows |
| `cyborg_voice.py` | the sung excerpt, 15.00 → 15.06 s | a sound strip |
| `cyborg_stutter.py` | a line voicebox speaks, 4.26 → 4.76 s with stutters | a sound strip, panned |
| `merge_av.py` | muxed the 7.5 s EEVEE era film with the song; refused (exit 2) the same film against 10 s of sound | `era_film_av.mp4` |
| `contact_sheet.py` | a labelled sheet of the EEVEE film with DAISY's sections and captions | `era_film_contact_sheet.jpg` |
| `generate_song.py --probe` | exit 0: MiniMax Music 3 nodes and models found at 127.0.0.1:8188. Nothing was generated | (a generated song is a sound strip like any other) |
| `generate_sfx.py --probe` | exit 0: ComfyUI reachable, `sa3_workflow.json` resolved. Nothing was generated | (recorded foley comes first) |

The strips in the song's time (frame 1 = 69 s) went into a one-pass render
(H.264 + 48 kHz stereo AAC, 2.0 s) and a mixdown. On Windows, a pipe's
console encoding is cp1252, and `align_lyrics.py`'s last print (a "→") then
raises after the JSON is written, with exit 1. Run it with
`PYTHONIOENCODING=utf-8` (or `python -X utf8`) when its output is piped.

The options those runs leave at their defaults, each run on this branch
(`tools_host.py --only options`, CPU only, 11-07):

| Tool and options | Result |
| --- | --- |
| `merge_av.py`, 7.5 s film, 4 s of sound | refused, exit 3 (`--trim-tol` 2.0); `--allow-trim` cut the film to 4.00 s; `--trim-tol 4` let the 3.5 s overrun through, 4.00 s |
| `merge_av.py`, 7.5 s film, 8 s of sound | the pad path (gap 0.5 s within `--tol` 1.0), re-encoded with `RENDER_CODEC=libx264`, 8.00 s; `--tol 0.25` refused it, exit 2 |
| `contact_sheet.py --parts 2 --names '{"verse1": "verse 1 · the machines"}' --synopsis …` | the full sheet plus `_part1` (4 frames) and `_part2` (3 frames); the section labels and the synopsis read as given |
| `align_lyrics.py --method align` (medium) | 2 lines for the 4 given: it merges a line pair into one ("Daisy Daisy give me your answer do", 69.00 s), starts within 0.36 s; 20 s on the CPU |
| `align_lyrics.py --chunk-sec 8 --top-db 24` (medium) | all 4 lines, starts within 0.19 s of the song's own; 28 s |
| DAISY `captions.py --preview` | the 168.7 s CQT lyric video (1920×1080, libx264), era captions burned in; 23 s |
| DAISY `analyze.py --asr --sections chorus1` | Whisper small per caption line, in the mix and in the vocals alone: mean word error rate 0.69 in the mix over chorus 1's 8 lines ("all of me made of you" heard exactly, "I can't afford a carriage" not at all) |

Whisper there is an intelligibility meter for synthesized voices, so the
numbers say how a listener might mishear the handmade lead, not that a tool
failed.

## Synthesized voices and music (no models)

When a piece wants its OWN voice or music, made by hand rather than generated: [voicebox](voicebox.md) sings and speaks from scratch (formant synthesis, historical machine voices from the 1939 Voder to neural TTS, choirs, a physical vocal-tract model), and [synthkit](synthkit.md) builds the music (instruments, drums, sequencer, sidechain, a −14 LUFS / −2 dBTP master). [`eidoverse/examples/daisy/`](../eidoverse/examples/daisy/README.md) is a full song made with both.

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
`max_duration`, `seconds`, `out`, `timeout_s` (default 900, the CLI's
`--timeout`) and sampler settings as keyword arguments.

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
The driver submits the repository's `sa3_workflow.json` (it falls back to
`/workspace/sa3_workflow.json`, then ComfyUI's
`~/Downloads/audio_stable_audio_3_medium_base.json` template).
`python generate_sfx.py --probe` prints the resolved workflow path and checks
that ComfyUI is reachable (exit 0/1).

```bash
python generate_sfx.py "<prompt>" <seconds> <category> <out.mp3> [seed] [--raw] [--neg "<text>"]
# category: SFX | One-shot | Music | Instrument
python generate_sfx.py "steady wind through dry grass, open field, no music" 24 SFX wind.mp3
python generate_sfx.py "TrackType: SFX. A single soft body landing thud on stone, short, close mic, dry room" 3 SFX land.mp3 --raw
```

By default the workflow's LLM prompt enhancer rewrites your prompt through a
per-category brief before Stable Audio sees it. `One-shot` is a music-sample
brief (plucks, stabs, slams), so it turns foley into musical hits — use `SFX`
for sound effects, including single events. `--raw` bypasses the enhancer and
sends the prompt verbatim; structure a raw foley prompt as
`TrackType: SFX.` + source + action/duration + mic/room/processing.
`--neg "<text>"` sets the negative prompt (empty by default). The flags may go
anywhere on the command line.

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
python cyborg_stutter.py raw.wav final.wav   # glitch stutters — for spoken TTS
# for SUNG vocals (separated from a song with demucs):
python cyborg_voice.py vocals.wav final.wav  # tone-only filter — safe for lipsync
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
`anoisesrc` (pink/white) → `bandpass`/`highpass` → `tremolo`. Mux the audio
in a separate ffmpeg pass, or let the Blender render carry its sound strips
([In the Blender edition](#in-the-blender-edition)).

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

## Sound in a Blender film

```python
from eidoblend.media import audio
audio.add_sound(scene, 'work/<id>/mix.wav', t=0.0, volume=1.0)
audio.place_events(scene, book.page_turn_events())          # e.g. a book's turns (books.md)
audio.add_markers(scene, [l['start'] for l in lines], prefix='line')
audio.mux_settings(scene)                                    # then render to video: picture and sound in one file
```

The lead's films keep the mix outside Blender (`mix_ep3.py`: clips placed by
frame, LUFS and true peak measured) and render chunks video-only; the cut
concatenates and muxes once. Both routes work; a one-pass render suits a short
piece or a probe. `make_edit_scene` in [motion graphics](motion-graphics.md)
carries the sound when graphics go over the film. Measured 11-07: a one-pass
render of a sung line wrote H.264 plus a 48 kHz stereo AAC stream, and the
strip's mixdown came back at 48 kHz stereo.

## Merging onto the render — `merge_av.py`

Render the scene a touch longer than the audio, then mux:

```bash
python merge_av.py --video scene_video_only.mp4 --audio mixed_audio.wav --out scene_final.mp4 [--tol 1.0] [--trim-tol 2.0] [--allow-trim]
```

It trims the video to the audio with `-shortest` and refuses two mismatches:

- **Video shorter than the audio by more than `--tol`** (default 1 s): it
  will not clone-pad a short render (`REFUSING TO MERGE — video … shorter
  than audio`, exit 2). Re-render longer.
- **Audio shorter than the video by more than `--trim-tol`** (default 2 s):
  usually the wrong or a truncated mix, and `-shortest` would silently cut
  the film, so it exits 3. Pass `--allow-trim` when cutting the video to the
  audio is intended.

Within those tolerances the video is stream-copied. Only a video short by up
to `--tol` is re-encoded, to pad that cushion: with `RENDER_CODEC` if set,
else `h264_nvenc` when ffmpeg lists it and a one-frame test encode succeeds,
else `libx264`. Measure the audio first and give the video enough duration,
allowing for rounding. If you want a held final image, author that hold in the scene
instead of relying on an accidental frozen tail.

## Lipsync — a character visibly speaking or singing

A voice made with [voicebox](voicebox.md) needs none of the steps below: `voicebox.visemes()` reads the synth's own phoneme timeline, frame-exact, with values 0..1 (not the 0.35 cap of `lipsync.py`, so drivers must not divide by 0.35).

```bash
# 1. split the mix. Stems land in <out>/htdemucs/<input-stem>/ — nested,
#    not next to the input — so reference the nested path.
python -m demucs --two-stems=vocals -o stems song.wav
#    → stems/htdemucs/song/vocals.wav  +  stems/htdemucs/song/no_vocals.wav

# 2. align. `lyrics` is a required positional and it is the TEXT ITSELF,
#    not a path — a filename "succeeds" and aligns that literal string as
#    the only lyric. The flag is --output.
python align_lyrics.py vocals.wav "$(cat lyrics.txt)" --output lyrics_aligned.json
#    or from python:  from align_lyrics import align_lyrics
#                     align_lyrics('vocals.wav', lyrics_text, method='chunked')

# 3. optional synthetic timbre — when the character concept wants it:
python cyborg_voice.py vocals.wav cyborg_vocals.wav   # (voice, not stutter)

# 4. visemes. lipsync.py is a MODULE with no CLI — a `python lipsync.py`
#    command exits silently having written nothing. Call it from python:
python -c "import json; from lipsync import get_viseme_timeline; \
json.dump(get_viseme_timeline('vocals.wav', fps=30), open('visemes.json','w'))"
```

The timeline has one entry per video frame, `ceil(duration × fps)` entries —
the same frame count the renderer uses for that duration.

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

**Keying the visemes in Blender.** The WebGPU engine set the expressions in
every `renderFrame`; Blender keys them once at build time, so any frame
renders in any order:

```python
from eidoblend.media import audio, timebase
vis = audio.load_visemes(json.load(open('visemes.json')), fps=30)   # a bare list needs its fps
lines = timebase.load_lines('lyrics_aligned.json')
keys = audio.prepare_visemes(vis, scene, start_t=0.0, divide=0.35,    # lipsync.py caps at 0.35
                             windows=audio.viseme_windows(lines), pad=0.12)
audio.key_expressions(armature, keys)
```

- `divide=0.35` for `lipsync.py`'s audio-derived values (the lead's unboxing
  face did the same); voicebox's are 0..1 already, so `divide=1`.
- `windows` gates the mouth to the sung lines, which is the gating above.
- Each frame's shapes are scaled to sum to at most 1, and every frame of the
  range is keyed (zeros included), so nothing persists between lines.
- `key_expressions` keys the shape keys through the VRM add-on's binds (VRM 1.0
  presets, or a VRM 0.x model's `a i u e o` groups) and the add-on's expression
  previews, with LINEAR interpolation.
- Emotion expressions (happy/sad/angry) override mouth shapes, so they sit
  out during lipsync.

`claude_suit.vrm`'s mouth (and `claude_suit_wardrobe.vrm`'s) is a special case:
its own shapes slide a flat plate off the face, and a mouth scaled straight by
loudness snaps shut on every consonant. Its suit-mouth driver is
`eidoblend.characters.claudesona.face`: `install_suit_mouth(me)` once, then
`make_suit_mouth(input_max=0.35)` for `lipsync.py`'s frames (1.0 for
voicebox's), keyed with `face.bake(...)`; see [claudesona.md](claudesona.md).

## Example workflow: a character performance music video

1. Generate or choose a song and measure its duration.
2. Separate vocals with demucs if needed; align the actual lyric text.
3. Apply any desired voice treatment, then generate visemes from the matching
   vocal timing and gate them to the sung windows.
4. Build a scene and choreograph performance, camera and environment around
   the song's structure. Key the visemes onto the singer in the build script.
5. Add readable captions if they serve the piece: subtitle strips or the
   overlay layer in [motion-graphics.md](motion-graphics.md).
6. Review image, sound and synchronization together, including the ending.

Instrumental films and other forms can use a different workflow. A singer,
captions, a fixed shot count and a fadeout are not prerequisites for a video.

## Supporting services and timing utilities

- `align_lyrics.py` creates word/lyric timing from vocal audio for captions.
  Use `lipsync.py`'s imported functions for mouth animation; it is not a
  standalone viseme JSON CLI. Keep speech and matching timings together.
- `bake_weather_audio.py` turns the weather system's event timeline into a
  WAV, unchanged. In Blender the timeline comes from
  `eidoblend.media.weather_audio`, a decision-for-decision port of
  `weather_audio.js`: it steps the film's frames and records the rain and wind
  envelopes and one thunder event per new strike (distance, the 343 m/s delay,
  pan from the camera's own axes, the compressed inverse-distance gain).

  ```python
  from eidoblend.media import weather_audio
  rec = weather_audio.WeatherAudioRecorder().record_scene(scene)   # reads 'eido_weather' each frame
  rec.write('work/<id>/wx_audio.json')
  # python bake_weather_audio.py work/<id>/wx_audio.json --out wx.wav --duration <d>
  ```

  By default it reads the weather from custom properties keyed on an object
  named `eido_weather` (`rainK`, `denseA`, `windK` or `wind_len`, `strike_id`,
  `strike_x/y/z`, `strike_flash`, `strike_local`, Blender metres); pass
  `read=` to read them elsewhere. That object is a proposal to the sky-weather
  family's port. `blender/tests/media/test_weather_audio_parity.py` feeds a
  synthetic storm to both recorders: the timelines match exactly (11-07), and
  the baker renders the port's.
- `eidoverse/comfy_bridge.py` is an optional TCP bridge for a container client
  that needs to reach a host ComfyUI. Native rendering can use the backend
  directly. The bridge listens on all interfaces by default; starting it is a
  separate networking operation, not a prerequisite for reading these guides.
- `eidoverse/lyric_renderer.py`'s `LyricRenderer` (minimum display time, gap
  filling, fades, wrapping, a backing pill, glow) is ported as
  `eidoblend.media.lyrics.LyricRenderer`. It gives byte-identical frames to the
  original, and its fonts resolve to the bundled files. It draws onto frames,
  `burn`s over a rendered sequence, or becomes an overlay panel
  (`make_lyric_layer`); see [motion-graphics.md](motion-graphics.md#lyric-subtitles--lyricrenderer).

## Karaoke captions on a Blender film — the ASS route

DAISY's `captions.py` writes ASS subtitles: one style per era, `\kf` karaoke
on the lead's own lines, two lanes. They burn onto the EEVEE film at the cut
with ffmpeg's `ass` filter and the bundled fonts. Shift them into the film's
time first:

```bash
python eidoverse/examples/daisy/captions.py                      # work/daisy/out/daisy.ass
ffmpeg -itsoffset -24.25 -i work/daisy/out/daisy.ass -c copy work/<id>/film.ass     # film frame 1 = 24.25 s
ffmpeg -i work/<id>/film.mp4 -i work/<id>/song_excerpt.wav \
    -vf "ass=work/<id>/film.ass:fontsdir=eidoverse/assets/fonts" -map 0:v -map 1:a \
    -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -shortest work/<id>/film_captions.mp4
```

Run it from the repository root: the filter's paths are relative, because a
Windows drive colon breaks its argument parsing. Measured 11-07
(`test_tools_film.py --only captions`): verse 1's era lines appeared on the
EEVEE wall at 25.75 s and 29.75 s of the song, each in its era's style ("Bell
Labs · 1961" in the corner, the line in typewriter type).

## Not yet ported

- The weather object `eido_weather` is a proposed contract; the sky-weather
  family's port decides where rain, wind and strikes are exposed.
- No generation was run on this branch: `generate_song.py` and
  `generate_sfx.py` answered their probes. A real generation loads weights
  onto the shared GPU and wants the collaborator's yes. Their output is an
  MP3 that `audio.add_sound` places like any other.

External music/SFX availability depends on the selected ComfyUI workflow and
installed models. A connectivity probe does not prove all generators work.
Use the selected tool's real error output to diagnose failures. A supplied
recording or another agreed sound-making method can keep the piece moving.
