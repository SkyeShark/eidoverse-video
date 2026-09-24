# Voice synthesis: voicebox

[Main instructions](../AGENTS.md)

**`voicebox/`** is a singing and speaking voice built from scratch. It needs no model weights and no network, with two exceptions: the neural era voice, and the optional Whisper checks. Use it to:
- give a character a voice that is its own;
- sing lyrics on exact notes, from a melody you write;
- recreate the machine voices of history, 1939 to now;
- stack a choir that hums or sings;
- get **phoneme-exact visemes** for lipsync.

The synth made every syllable, so the timings are known, not detected.

It is a host-side Python package imported from the repo root. It is not a scene global and never runs inside the render loop. Render WAVs first, then mux them onto the video (`merge_av.py`, see [audio](../AGENTS.md)). All output is 48 kHz (`SR = 48000`); control tracks run at 1 kHz (`voicebox.CR`).

First written for the DAISY music video (2026-09), where every vocal is voicebox. [`eidoverse/examples/daisy/song.py`](../eidoverse/examples/daisy/README.md) is a complete worked example: sections, era layers, a choir, a crowd chant, word timings for captions, and visemes.

## Quick start: sing a line, save it, get the mouth

```python
import sys; sys.path.insert(0, '.')                      # from the repo root
from voicebox import Sung, Voice, visemes, write_wav
from voicebox import eras

s = Sung(bpm=128)
# One syllable per note. Whole words: the G2P syllabifies them for you.
end = s.line("Daisy Daisy give me your answer do",
             ["B4", "G#4", "E4", "B3", "C#4", "D#4", "E4", "C#4", "E4", "B3"],
             [2, 2, 2, 1.333, 0.667, 0.667, 0.667, 1.333, 0.667, 3.333],
             start_beat=1.0)                              # leave >= 1 beat of pre-roll for onset consonants
y, segs, tracks = eras.handmade(s)                        # or s.render(Voice(...))
write_wav('work/demo/daisy.wav', y, 48000)                # atomic write: <name>.part.wav, then rename
mouth = visemes(segs, tracks, len(y) / 48000, fps=30)     # [{aa, ih, ou, ee, oh}] per frame, values 0..1
print(s.lines)                                            # [{text, t0, t1}] for captions
```

What `Sung.line(text, pitches, beats, start_beat, vel=1.0, legato=True, velocities=None)` takes:
- **One syllable per note.** A lone `_` in the text continues the previous syllable onto the next note (a melisma). A `None` pitch is a rest.
- **Pitches** are note names (`'F#3'`, `'Bb4'`) or MIDI numbers. **Beats** are note lengths.
- It raises on any mismatch ("syllables left over", "more notes than syllables"), which is your cue that the G2P counted differently.
- **Check counts first.** `voicebox.text_to_syllables(word)` shows how a word syllabifies. "every" is three syllables and "our" is two.
- **Inline pronunciations** fix a count, or any word the dictionary lacks: `"{EH1 V R IY0} one of us"` sings "ev'ry" as two syllables. `add_word('claudesona', 'K L AO1 D S OW1 N AH0')` registers a word for good.
- The dictionary is CMUdict (`pip install cmudict`) plus the `CUSTOM` table in `voicebox/g2p.py`. A missing word raises `KeyError` naming the fix. **Scan all your lyrics with `lookup()` before a long render.**

## Voices and their controls

`Voice(...)` is a dataclass. `v.but(**changes)` returns a modified copy.

| field | what it does | typical |
|---|---|---|
| `vtl` | vocal-tract size: 0 = adult male (Peterson & Barney 1952 men), 1 = female; >1 is small and bright | 0.0–1.15 |
| `oq`, `tilt`, `breath` | glottal open quotient, spectral tilt, aspiration level (dB) | 0.62, 0.15, −30 |
| `vib_rate`, `vib_depth`, `vib_delay`, `vib_attack` | vibrato Hz, cents, onset delay (s), fade-in (s) | 5.4, 30, 0.28, 0.35 |
| `portamento`, `scoop`, `overshoot`, `drift` | pitch glide (s), note-onset scoop (cents), overshoot (cents), slow wander (cents) | 0.07, 25, 0, 7 |
| `presence_db`, `air_db` | presence shelf at 4.5 kHz; breath "air" band (4–11 kHz) riding the voicing | 7, −60 (handmade: 9, −38) |
| `consonant_gain_db`, `consonant_rate` | consonant loudness and speed | 0–4, 1.0 |
| `f1_tuning` | singers' formant tuning: F1 lifted above F0 on high notes | True |
| `frame_hold_ms`, `bw_scale`, `formant_shift` | stepped control frames (a DECtalk feel), formant bandwidths, global formant scale | 0, 1, 1 |

**Speech** uses `speak(text, voice, rate=1.0)`, which returns `(y, segs, tracks)`: rule-based timing and a falling F0 with accents. The claudesona's handmade voice is `eras.handmade`'s default:

```python
Voice(vtl=0.6, breath=-28, oq=0.62, tilt=0.1, vib_rate=5.3, vib_depth=28, portamento=0.06,
      scoop=20, drift=6, presence_db=9, consonant_gain_db=4, air_db=-38)
```

## Era voices: `voicebox.eras`

Every renderer takes a `Sung` and returns `(y, segs, tracks)` at 48 kHz, peak −3 dBFS, with a 35 Hz sub-sonic blocker. The TTS-based eras return `(y, None, None)`, so they have no visemes. The registry is `eras.ERAS`.

| renderer | how it's made | needs |
|---|---|---|
| `voder_1939` | ten band-pass filters played like the Bell Labs Voder: buzz/hiss sources, pedal pitch, over a 1939 PA | — |
| `bell_labs_1961` | a **Kelly–Lochbaum tube model** (`voicebox/tube.py`): 20 sections at 20 kHz, area functions fitted to Peterson & Barney (worst 0.64%), a nasal side branch, then 10 kHz, 12-bit, onto tape. The method behind the 1961 "Daisy Bell". | — |
| `speakspell_1978` | LPC-10 at 8 kHz, 25 ms frames, TMS5100 bit allocation, a chirp excitation, 8-step interpolation | — |
| `sam_1982` | S.A.M. style: two sine formants plus a square, reset each glottal pulse, 4-bit output | — |
| `dectalk_1984` | a Klatt cascade voice at 10 kHz with 6.4 ms stepped frames. A generic Klatt voice: **never imitate Stephen Hawking's specific voice**, whose keeper asked that it not be reused. | — |
| `sapi_2001` | a Windows desktop voice speaks each word, then Praat PSOLA re-sings it onto the notes | **Windows only** (`powershell.exe` System.Speech) |
| `vocaloid_2007` | a small bright tract, exact pitch, stylized vibrato, overshoot | — |
| `neural_2023` | a Microsoft neural voice via `edge-tts`, re-sung with PSOLA (`voice='en-US-AriaNeural'` etc.) | **network** + `edge-tts` |
| `handmade` | the full-quality formant voice | — |

**Report which backend actually ran** (AGENTS rule). The TTS eras depend on the machine and the network. `tts_edge` retries dropped requests with backoff, but a failure still raises.

## Choir, crowd, tube

- **`voicebox.choir.choir(chords, vowel='AA', per_note=3, vtl_range=(0.25, 0.95), detune_cents=9, timing_ms=30, …)`** returns stereo `(2, n)`.
  - `chords = [(t0, t1, [pitches…])]`, and every chord needs the same number of tones: singer k takes tone k, which is simple voice leading.
  - Each singer gets its own tract size, detune, timing drift and pan.
  - `vowel='NM'` **hums**: lips closed, sound through the nose.
- **A gang chant:** render one line with several `HANDMADE.but(vtl=…, seed=…)` voices, each with a little timing slop, and pan them apart. See `crowd()` in `eidoverse/examples/daisy/song.py`.
- **`voicebox.tube`** holds the physical vocal tract:
  - `tube_formants(areas, length_cm)` gives a tube's resonances (chain-matrix method);
  - `fit_area(targets_hz)` fits an area function to target formants;
  - `vowel_areas()` holds the cached vowel shapes;
  - `render_tube(sung)` renders without the era chain (as does `bell_labs_1961_clean`).
  - Use them for creature voices, or to animate a throat.

## Lipsync from voicebox

`visemes(segs, tracks, duration, fps=30, gain=1.0)` reads the phoneme timeline, so it's exact to the frame:
- openness follows the synthesized voicing;
- the mouth closes on rests and on bilabials (M, B, P and the hummed `NM`);
- the dominant vowel shape wins.

**Values run 0..1.** `lipsync.py`'s audio-derived visemes cap at 0.35 and existing drivers divide by 0.35; don't do that here.

For `claude.vrm` (the expression path), set `vrm.expressionManager.setValue(k, w[k])` for `aa ih ou ee oh` each frame. A VRM registered through `playVRMADefault` is updated by the engine **after** your render, so read the viseme at `t + 1/FPS`. Gate the mouth to your own vocal lines; visemes from a ghost or double track belong to whoever sings them. For the claudesona (`claude_suit.vrm`, `claude_suit_wardrobe.vrm`) use `makeSuitMouth({ inputMax: 1 })` from `eidoverse/claudesona_face.js`: its mouth is a threshold reveal that a loudness-scaled pose makes flicker. See [characters](../AGENTS.md).

## Measuring without ears

We can't listen, so we measure. `voicebox.util` has:
- `spectrogram_png(y, sr, path, title, fmax)`: look at every render;
- `transcribe(path, model='small')`: Whisper as an intelligibility meter, needs `openai-whisper`;
- `word_error_rate(ref, hyp)`.

Lessons that cost something:
- **Never give Whisper the lyrics as `initial_prompt`.** It echoes them back, which is invalid evidence.
- **Transcribe one lyric line at a time.** Whole sections and sustained notes make Whisper loop ("A A A A…").
- **The mix masks far more than the voice alone.** On DAISY one line scored WER 0.08 on the vocals alone and 0.69 in the mix. Compare the two before blaming the voice.
- **Rhythm is the biggest lever.** At 128 BPM, sixteenth-note syllables crush consonants, and every "I was a" became "I wanna". Keep eighth notes as the fastest, and **≤14 syllables per two bars**. Doing that took the handmade voice's WER from 0.65 to 0.46 on DAISY's verse, together with stronger Z/ZH frication.
- **Layers of other voices smear consonants.** Band-limit harmony and polyphony layers to 250–3000 Hz so they add body. Duck the backing's 0.5–6 kHz band while anyone sings (DAISY's `vocal_pocket()`).
- **The formant voice loses definition above about C#5.** Male-configured era voices fail at high pitch, so sing them an octave down.

## Known limits
- Consonant clusters are simplified. TH/F and V confusions persist at speed.
- `sapi_2001` needs a Windows host. `neural_2023` needs the network.
- Praat's overlap-add allocates at most 3× the input length, so `resing` pads the source internally. Words shorter than Praat's 71 ms intensity window are handled by a widened analysis window.

**Dependencies** (see `requirements-local.txt`, "voice & music synthesis"): numpy, scipy, numba, soundfile, cmudict, pedalboard. `resing` / `neural_2023` also need praat-parselmouth and edge-tts. The Whisper checks need openai-whisper.
