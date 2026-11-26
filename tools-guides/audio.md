# Audio — music, SFX, narration, mix, merge, lipsync

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose music, ambience, voice, physical sound effects or silence for the
piece. Plan sound and image together, including intentional gaps. When voice
needs to be intelligible, listen to its balance against the actual bed; a
fixed gain difference is only a starting point, not a universal mix standard.

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

`claude_suit.vrm`'s mouth (and `claude_suit_wardrobe.vrm`'s) is a special case:
its own shapes slide a flat plate off the face, and a mouth scaled straight by
loudness snaps shut on every consonant. Drive it with `installSuitMouth` and
`makeSuitMouth` from `eidoverse/claudesona_face.js`,
feeding it these same viseme frames with `inputMax: 0.35`; see
[characters.md](characters.md).

### A singing mouth from the vocal stem — `get_viseme_timeline_from_vocal`

When a song's voice is available on its own (a recorded vocal, a demucs stem,
a voicebox render), `lipsync.py` can read a singing mouth from it. The band
method above follows the spectrum, frame by frame. This one follows the
singer:
- **How open** follows the stem's own level, measured four times a frame. A
  held note stays open for as long as it sounds, and a breath between words
  closes the mouth. The mouth opens at once and closes over about 70 ms.
- **Which shape** is the vowel of the word sung then, from the words'
  times. Each word's last vowel is held while the voice goes on.
- **A hiss with no voice under it** (s, sh, a stuttered "s-s-") shows the
  teeth as a narrow `ih`.
- **The lips shut** on the frame before a word that starts with m, b or p.
- **Where the voice sounds and no word was heard** ("ooh", a hum), the shape
  is read off the spectrum: dark vowels round, bright ones wide.

```python
import json
from lipsync import get_viseme_timeline_from_vocal
lines = json.load(open('lyrics_aligned.json'))          # align_lyrics.py output: lines with their "words"
timeline = get_viseme_timeline_from_vocal('vocals.wav', lines, fps=24)
json.dump({'fps': 24, 'frames': timeline}, open('visemes.json', 'w'))
```

The words can be `align_lyrics.py`'s lines, a flat list of
`{word, start, end}`, or `(word, start, end)` tuples. With `None`, every shape
comes from the spectrum. A word's vowels come from a small table of common
words, else from its spelling. Pass `syllables=` your own function for a
language or a lexicon of your own.

The shapes are VRM's: `aa` is the "a" of "father", `ih` the "i" of "see",
`ou` the "u" of "blue", `ee` the "e" of "bed" and "made", and `oh` the "o"
of "go". voicebox's phoneme visemes use the same mapping. The values run 0..1
with their sum at most 1, so drivers take them as they are:
`setValue(k, v)` raw, and `makeSuitMouth({ inputMax: 1 })` for the suit mouth.
`get_mouth_openness()` is scaled for the band method's 0..0.35 and saturates
here.

The stem's own silences close the mouth, so instrumental passages need no
gating. Demucs bleed loud enough to read as voice still opens it; gate those
stretches as above.

On voicebox's own voice, this mouth agrees with voicebox's phoneme mouth
(`voicebox.visemes`, frame-exact) as follows, measured by the
[finishing example](../eidoverse/examples/finishing/README.md):
- the same frames open or shut on 96 % of frames;
- an openness correlation of 0.93;
- the same dominant shape on 90 % of the frames both call open.

## The song's clock — `song_clock.py`

`song_clock.py` measures a song's timing from the wav: where its beats, bars,
quiet stretches, sections and sung lines fall, in seconds and in video frames,
for cutting a film to it. It measures timing only. It never says how a take
sounds, which is the listener's call.

```bash
python song_clock.py song.wav --fps 24 --out work/<id>/song_clock.json [--downbeat 14.93]
python song_clock.py song.wav --lyrics lyrics.txt --vocal vocals.wav      # + the lines, via align_lyrics.py
python song_clock.py song.wav --repeat 33.0 47.6 --within 47.6 140        # where that passage's music returns
python song_clock.py song.wav --offset work/<id>/film.mp4                 # the film's sound against the song
```

**The beats.** librosa's beat tracker gives the grid, which sits a little
late on most songs, often 30–40 ms. The clock measures that lag over the
whole song and takes it off. It then moves each beat onto the wav's own rise
(spectral flux on a 1 ms clock) where one stands within 18 ms. Each beat says
whether it is `measured` or `carried` (no clear rise, so the grid smoothed
through its neighbours). The `check` block reports how far the plain level's
steepest step sits from each beat. On the three songs it was tried on, the
median was 1 to 6 ms.

**The bars** are every `--beats-per-bar` beats. Their phase is a guess from
where the harmony changes, unless `--downbeat` names a moment on a bar line
(the first word of a verse, say). The song's words and the collaborator's ear
decide where a bar line is. A beat the tracker missed or doubled shifts the
count after it, so check the bars near the moments the film cuts on.

**Everything else:**
- `silences`: 0.2 s or more, 25 dB under the loud parts.
- `segments`: where timbre and harmony change.
- With `--lyrics`: `lines` (each line's start, end, words, frame and bar) and
  `captions`. The lyric file holds one sung line per line. A `[Name]` line
  names the section of the lines after it, and those names become the
  clock's `sections`. Without lyrics the sections are the segments.
- With pyloudnorm installed: the integrated loudness and the true peak.

A moment at `t` seconds sounds in frame `1 + floor(fps × t)`, where frame 1
starts at 0 s. The WebGPU runner's frame index is that minus one. The clock's
`sections` and `captions` are the timeline shape `contact_sheet.py` and
`film_print.py` read.

`--repeat A B` finds where the music of a passage comes back. It compares
harmony and timbre beat by beat, so it says where the music repeats, never
what is sung there. `--offset FILM` cross-correlates the film's sound with
the song at five places and prints the lag in ms and frames: 0 when the mux
is right, positive when the film's sound is late. Dependencies: librosa and
soundfile (tier 2), pyloudnorm and scipy for loudness, and stable-ts for
`--lyrics`.

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
- `song_clock.py` measures a song's beats, bars, sections and lines (above);
  its JSON is also a timeline for `contact_sheet.py --lines` and
  `film_print.py --letters`.
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
