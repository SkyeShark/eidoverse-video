# DAISY (DAY'S EYE) — the song, as a worked example

[Voice synthesis guide](../../../tools-guides/voicebox.md) · [Music synthesis guide](../../../tools-guides/synthkit.md) · [Tool inventory](../../../docs/TOOLS.md)

The complete source of the song from the DAISY music video (2026-09): a
5:29 song about the history of machine voices, made with no samples and no
generative audio model. [voicebox](../../../tools-guides/voicebox.md) sings every vocal: each verse
line in the voice technology of its era (the 1939 Voder, the 1961 Bell Labs
tube voice, Speak & Spell, S.A.M., the Klatt voice, desktop TTS, neural TTS),
a handmade lead voice, a choir and a chanting crowd.
[synthkit](../../../tools-guides/synthkit.md) plays the band, and the master bus
delivers −14 LUFS with true peaks under −2 dBTP. Read it as the fullest example of both packages
working together. `LYRICS.md` is the lyric sheet with its sources.

| File | Role |
| --- | --- |
| `song.py` | The song: sections on a 128 BPM grid, era layers, choir, crowd, designed FX, the mix and the master. Also writes the timeline the film is cut to: sections, beat grid, drum hits, captions with era styles, and the lead voice's visemes at 30 fps. |
| `captions.py` | Timeline to ASS subtitles, one style per era, with `\kf` karaoke on the lead's own lines, in two lanes (words at the bottom, the room's sounds at the top) where a line never overlaps the next one in its lane. `--preview` renders a lyric video (CQT visual, captions, song). |
| `analyze.py` | Measures a render section by section: LUFS per stem and of the mix, lead-over-backing margin, spectral balance, peaks, a spectrogram per section, and with `--asr` what Whisper hears in the vocals alone and in the mix. |
| `LYRICS.md` | Lyrics, structure and the historical sources of every line. |

## Run

From the repository root, with the voicebox and synthkit dependencies installed
(`requirements-local.txt`, tier 2b):

```bash
python eidoverse/examples/daisy/song.py --upto chorus1   # fast: through one section
python eidoverse/examples/daisy/song.py                  # the whole song
python eidoverse/examples/daisy/analyze.py --asr         # measure it
python eidoverse/examples/daisy/captions.py --preview    # subtitles + a lyric video
```

Outputs go to `work/daisy/out/` and a content-keyed vocal cache to
`work/daisy/cache/`, both outside version control. Once the vocals are cached,
a mix change rerenders quickly. The neural-era lines use online TTS re-sung on the melody. Pass
`--no-tts` to stand the handmade voice in for them offline.

To drive a character from `daisy_timeline.json`, feed its visemes to
`makeSuitMouth` in `eidoverse/claudesona_face.js` (the claudesona) or to the
expression path for other VRMs; see the [characters guide](../../../tools-guides/characters.md).

## Credits

Words, voices and music by Claude (Opus 5.5), made with Skye. "Daisy Bell"
(Harry Dacre, 1892) is in the public domain; the melody follows the 1892 first
edition. No recording is sampled.
