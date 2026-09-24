# Music synthesis: synthkit

[Main instructions](../AGENTS.md)

**`synthkit/`** is music built by hand, from oscillators up, with no samples and no model. It covers:
- band-limited synths, chip voices, FM electric piano, a 1961 organ, a music box and a piano;
- 808/909 drums;
- a beat sequencer with sidechain ducking and delay/reverb sends;
- designed effects: tape stop, stutter, bitcrush, a dial-up modem, a power-down, vinyl;
- a **loudness-targeted master bus** with its own look-ahead true-peak limiter.

Use it when a piece wants its own music, made the way the piece means. For generated songs, use `generate_song.py` ([audio](../AGENTS.md#audio-pipeline-deep-dive)).

It is a host-side Python package imported from the repo root, like [voicebox](voicebox.md), and works at 48 kHz. [`eidoverse/examples/daisy/song.py`](../eidoverse/examples/daisy/README.md) is the full worked example: a 5:29 song with a 3/4 intro, a 128 BPM body, sections, era instruments, sidechain, choirs and mastering.

## Quick start

```python
import sys; sys.path.insert(0, '.')
from synthkit import Song, inst, master, write_stereo

song = Song(bpm=128, bars=8, tail=2.0)
kick = song.track('kick', inst.kick909, drum=True, sidechain_source=True, gain_db=-6)
kick.pattern('x...x...x...x...', bar=0, bars=8)                  # one char per 16th: x hit, X accent, o soft, . rest
hat = song.track('hat', inst.hat, drum=True, gain_db=-20, pan=0.2)
hat.pattern('xoo' * 4, bar=0, bars=8, steps_per_beat=3)          # triplet hats
pad = song.track('pad', inst.pad, gain_db=-12, reverb=0.3, duck=True, params={'cutoff': 3000})
for i, c in enumerate(['C#m', 'A', 'E', 'B'] * 2):
    pad.chord(c, beat=i * 4, beats=4, octave=4)
bass = song.track('bass', inst.sub_bass, gain_db=-9, duck=True)
bass.notes(['C#2', 'A1', 'E2', 'B1'] * 2, beat=0, beats_each=4)
mix = song.render()                                              # (2, n) float, sends included
write_stereo('work/demo/loop.wav', master(mix, lufs=-14.0, ceiling_db=-2.0))
```

- **`Song(bpm, bars, beats_per_bar=4, offset=0, tail=2)`**:
  - `.track(name, instrument, gain_db, pan, reverb, delay, drum, duck, sidechain_source, fx, params)` adds a track.
  - `.render(return_stems=False)` → `mix` or `(mix, stems)`. The stems are pre-send.
  - `.beat_to_s(beat)` converts beats to seconds.
  - A section with its own tempo or metre (a waltz intro) is simply another `Song`, placed with `place(dst, src, seconds)`.
- **`Track`**:
  - `.note(pitch, beat, beats, vel)`, `.notes(...)` and `.chord(name, beat, beats, octave, inversion)` for pitched parts;
  - `.hit(beat, vel)` and `.pattern(pat, bar, bars, steps_per_beat)` for drums;
  - `.clip(seconds, audio)` places a pre-rendered clip (a vocal, a riser);
  - `.hit_times()` returns seconds, for video beat-sync.
  - Instrument kwargs go per note (`note(..., cutoff=900)`) or per track (`params={}`).
- **Sidechain:** tracks with `duck=True` are gain-ducked by every hit of the `sidechain_source` track.
- **Chords:** `chord('F#m7', 3)` → MIDI list. Qualities: `'' m 7 maj7 m7 sus2 sus4 add9 madd9 dim 6 m9 maj9 5`. `nm('C#4')` → 61.

## Instruments: `synthkit.inst`

Melodic ones are called as `(f, dur, vel, **params)`, drums as `(vel, **params)`:

| family | instruments |
|---|---|
| synth | `pad` (supersaw pad; `attack`, `release`, `cutoff`, `detune`), `lead_saw`, `pluck`, `sub_bass` (`drive`), `reese` |
| keys | `fm_epiano` (DX7-style), `piano`, `organ_1961`, `music_box` |
| chip | `chip_pulse` (`duty`, `vib`, `arp`, 4-bit volume), `chip_tri`, `chip_noise(kind=)` |
| drums | `kick909` (`tune`, `decay`, `click`), `kick808`, `snare909`, `clap`, `hat(open_=)`, `crash`, `impact` |
| risers | `riser(dur, vel, f0, f1)` |

The oscillators in `synthkit.dsp` (`saw`, `pulse`, `tri`, `supersaw`) are polyBLEP band-limited, with numba kernels. `svf(x, cutoff, res, mode)` is a TPT state-variable filter; `adsr`, `noise` and `pan_stereo` round out the kit.

## Effects: `synthkit.fx`

- `tape_stop(x, start_s, dur_s)`: the reel losing power, pitch and speed falling together.
- `stutter(x, at_s, slice_s, repeats)`: glitch repeats.
- `bitcrush(x, bits, down)`.
- `modem_handshake(dur)`: dial tone, DTMF, the 2100 Hz answer tone with phase reversals, V.8 FSK, training hiss.
- `power_down(dur)`: mains hum and buzz sagging to a breaker click.
- `vinyl(n)`.

## Mastering

`master(stereo, lufs=-14.0, ceiling_db=-1.0, glue=True)`:
1. a 20 Hz sub-sonic high-pass;
2. gentle glue compression;
3. loudness to target (ITU-R BS.1770, pyloudnorm);
4. `true_peak_limit`: 4× oversampled look-ahead. It replaced pedalboard's `Limiter`, which adds its own makeup gain and silently lands a few LU hot.

**The house delivery target is −14 LUFS and ≤ −2 dBTP, so pass `ceiling_db=-2.0`.** `write_stereo(path, x)` writes 24-bit WAV atomically, via a `.part` rename. A half-written WAV has unfinished header sizes, which Windows players report as an "unsupported format".

Deliver a compatible mp3 with ffmpeg: `-ar 44100 -c:a libmp3lame -b:a 320k -id3v2_version 3`. All formats tested, WAV 16/24/float, mp3 and AAC, play in both the Windows 11 Media Player engine and legacy WMP.

**Measure the mix; don't guess it.** `eidoverse/examples/daisy/analyze.py` reports, per section:
- the LUFS of each stem;
- the vocal-over-backing margin (aim for about +5 to +8 LU in a vocal pop mix);
- the spectral balance (sub/low/mid/presence/air);
- optionally, a per-line Whisper check in the mix.

**Dependencies:** numpy, scipy, numba, soundfile, pedalboard (sends, glue), pyloudnorm (master).
