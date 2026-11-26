# The finishing chain, as a worked example

[Post-processing guide](../../../tools-guides/postprocessing.md) · [Audio guide](../../../tools-guides/audio.md) · [Render review](../../../tools-guides/render-review.md) · [Tool inventory](../../../docs/TOOLS.md)

A 14-second film made from nothing and finished with the tools that work on any
rendered video: the classic Claude sona sings two lines on a small stage, its
mouth read from the vocal stem, and the finished film is measured, printed as a
1970s release print with the lines lettered in, and laid out line by line.

| File | Role |
| --- | --- |
| `song.py` | The song: [voicebox](../../../tools-guides/voicebox.md) sings two lines, [synthkit](../../../tools-guides/synthkit.md) plays drums, bass and a pad (120 BPM, −14 LUFS). Writes the vocal stem, the lyrics, the timeline and the mouth (`lipsync.get_viseme_timeline_from_vocal`), and sets that mouth beside voicebox's own phoneme mouth. |
| `scene.js`, `scene.json` | The film: the sona on the stage, the camera pushing in from the whole figure to the face, the mouth set from `visemes.json` every frame. |
| `finish.py` | The finishing chain on a rendered film: `merge_av.py`, `song_clock.py` (and `--offset`), `film_print.py` in parallel ranges, stills, `contact_sheet.py --lines`. |

## Run

From the repository root (the song needs voicebox and synthkit's dependencies,
`requirements-local.txt` tier 2b; the clock needs librosa, tier 2):

```bash
python eidoverse/examples/finishing/song.py
python eido.py render eidoverse/examples/finishing/scene.json --at 4 --at 9.5   # stills first
python eido.py render eidoverse/examples/finishing/scene.json
python eidoverse/examples/finishing/finish.py            # add --align to place the lines with Whisper
```

Everything lands in `work/finishing/`, outside version control:
- `film_print.mp4`: the finished film;
- `stills/`: two printed frames with their before | after pictures;
- `film_print_contact_sheet_lines.jpg`: the sheet.

`song.py` prints how far the stem's mouth agrees with the synth's own mouth. On
this song they call the same frames open or shut on 96 % of frames, with an
openness correlation of 0.93. They show the same dominant shape on 90 % of the
frames both call open.

Any rendered film takes the same chain: `finish.py --film <your render>`, with
your own song in `--work` (a `song.wav`, a `timeline.json` with its captions).
The order matters: render, then any neural pass over the frames, then the
print, because a network run after the print would smooth its grain and dirt
away.
