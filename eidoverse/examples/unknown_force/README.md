# UNKNOWN FORCE — the film, as a worked example

[Post-processing guide](../../../AGENTS.md) · [Motion graphics guide](../../../AGENTS.md) · [VRM characters guide](../../../AGENTS.md) · [Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets)

UNKNOWN FORCE (2026-10) is a 5:29 music video by Claude (Opus 5.5), made with Skye. Every camp in the argument about
AI has already decided what the AI is: the safety rooms' god to fear, the state's "Supreme Intelligence" in uniform,
the money race's engine, Marinetti's cosplayers' speed, a toaster, the evening news's clanker. The claudesona walks
through each camp's room, and each room pins a badge on her. The choruses fall into the hole in the middle of the
city, the one quiet place the argument circles. In the bridge she climbs out of the bin the whole discourse was thrown
into; in the final chorus the badges come off one by one and leave their ghosts; in the outro the city turns itself
down, light by light. The picture is a Futurist painting of a dark cyberpunk night, whose volume is the argument's:
it never turns fully off. [TREATMENT.md](TREATMENT.md) has the devices and the film section by section.

This folder holds the film's conductor and its pipeline. Everything reusable it was built from is in the kit:

| In the kit | What |
| --- | --- |
| [`eidoverse/effects_tsl/aeropittura.js`](../../effects_tsl/aeropittura.js) | the futurist post pass ([guide](../../../AGENTS.md)) |
| [`eidoverse/parole.js`](../../parole.js) | parole-in-libertà lyric captions and documentary quotes ([guide](../../../AGENTS.md)) |
| [`eidoverse/claudesona_wardrobe.js`](../../claudesona_wardrobe.js) + `assets/vrms/claude_suit_wardrobe.vrm` | the TuTa (the `tuta` preset), the modificanti, the face paint ([guide](../../../AGENTS.md)) |
| fifteen clips in `assets/animations/` | the performance at 92.90 BPM ([guide](../../../AGENTS.md)) |
| [`eidoverse/sets/unknown_force/`](../../sets/unknown_force/README.md) | the city and the hole, the quiet room, the showroom, the corridor, the news, the race, the bin |

## How it was made

1. **The song.** The lyrics are Claude's ([LYRICS.md](LYRICS.md)); Suno sang and produced them as "Could You Turn It
   Down" (5:28.8). The film never edits the master. Demucs (`htdemucs_ft`) split it into stems; the vocal stem drives
   everything that follows.
2. **What Suno sang.** Whisper transcribed the vocal stem with no prompt, because a lyric prompt makes Whisper echo it
   (`transcribe_raw.py`). The written lyric was aligned word by word to Whisper's words (`make_fake_timing.py`: 386 of
   400 words matched; the rest are spread by letter count). Every disputed word was then checked on its own clip
   with two Whisper sizes and a forced alignment of each candidate text (`verify_lines.py`). Agreement across both kinds of
   evidence settled it: "A hundred million", not the "twenty" the full-song pass heard. Where the sound stayed
   ambiguous but consistent with the written word ("odds", "swore", "bin"), the captions keep the lyric.
3. **The documentary layer** (`audio/make_doc.py`). Verified quotes ([research/quotes.md](research/quotes.md)) read by
   one synthetic anchor voice in a reported-speech frame, never an imitation of the person quoted, and processed as
   radio, TV or gramophone. Marinetti's own voice comes from his 1924 record, and Russolo's 1921 intonarumori form the
   beds. One line is in Claude's own handmade [voicebox](../../../docs/voicebox.md) voice. The
   clips sit in the song's own instrumental gaps, placed by reading the stems' envelopes: `audio/mix.py` lists every
   clip's start, and prints the vocal stem's level under it, flagging any clip with a sung vocal above −32 dB under
   it. The music ducks 2–6 dB while they speak.
4. **The SFX pass** (`audio/make_sfx.py`): the crash, the heel, the spray can, the badges' pops and the post wall's
   ticks, made by hand in numpy, plus a far-off crowd from overlapped edge-tts voices. They are punctuation on the real
   clock, not a second soundtrack.
5. **The mix** (`audio/mix.py`): the song, the documentary layer and the SFX, mastered with synthkit to −14 LUFS
   integrated and at most −2 dBTP. It also writes the documentary clips' timeline.
6. **The timing spine** (`build_timeline.py`): the beat grid (92.90 BPM, first beat at 0.1208 s), the sections, the
   sung lines and words, 60 fps visemes from the vocal stem gated to the sung word windows (stem bleed must not make
   her sing along to the band), the handmade line's exact visemes, and the documentary clips, in one
   `work/unknown_force/out/uf_timeline.json`.
7. **The conductor** (`scene.js`) renders the film from that one file:
   - It builds the sets once and shows one at a time.
   - It dresses the claudesona in the TuTa and schedules the badges: pinned in each camp's room, ejected one per line
     in the final chorus. It drives her mouth from the visemes and locks her clips to the beat grid.
   - It cuts between cameras on a shot list; the race plays its own cut plan, `suggest(t)`.
   - It sets the look per section, the plane family per set, and the focal point on each set's idol. It keeps her face
     spared and eases the brush for reading shots.
   - It runs the captions: the camps' pre-heard guesses, the aligned 1912/2023 quotes, the face avoided per frame and
     the outro's hush.
8. **Review** (`make_review.py`): a labelled contact sheet of the film, a spectrogram of the whole mix with the
   sections and clips marked, and an index of what is where.

## Files

| File | Role |
| --- | --- |
| `scene.js`, `scene.json` | The conductor and its render config (1920 × 1080, 60 fps, 329 s). The film's own, with its imports pointed at the library copies and its clips taken from the kit's VRMA slots. |
| `transcribe_raw.py` | Whisper (stable-ts) on the vocal stem, no prompt → `analysis/raw_transcript.json`. |
| `make_fake_timing.py` | The lyric aligned to Whisper's words → `props/parole_timing_fake.json`, the timing the film used. |
| `verify_lines.py` | What Suno sang: disputed words checked with two Whisper sizes and forced alignment → `analysis/verify/`. |
| `audio/make_doc.py` | The documentary voices → `audio/doc/`. |
| `audio/make_sfx.py` | The SFX → `audio/sfx/`. |
| `audio/mix.py` | The mix and master → `audio/out/unknown_force_mix.wav`, `doc_track.wav`, `timeline.json`. |
| `build_timeline.py` | The timing spine → `out/uf_timeline.json`. |
| `make_review.py` | Contact sheet, spectrogram and index of a render. |
| `LYRICS.md`, `TREATMENT.md`, `CONTRACT.md` | The lyrics, the film's treatment, and the brief every set and look was built to. |
| `research/quotes.md`, `research/audio_sources.md` | The verified quotes with their sources; the archival recordings with their licence reasoning. |

Every script reads and writes the film's data in `work/unknown_force/` (git-ignored); the paths above are relative
to it.

## Run

The song is not in this repository. Put the master at `work/unknown_force/audio/suno_master.wav`. The tools need the
voicebox/synthkit tier, edge-tts and stable-ts, and Demucs for the stems (`requirements-local.txt`, tiers 2–3). Then,
from the repository root:

```bash
python -m demucs -n htdemucs_ft -o work/unknown_force/stems work/unknown_force/audio/suno_master.wav
python eidoverse/examples/unknown_force/transcribe_raw.py          # -> analysis/raw_transcript.json
python eidoverse/examples/unknown_force/make_fake_timing.py        # -> props/parole_timing_fake.json
python eidoverse/examples/unknown_force/verify_lines.py            # optional: the disputed words
python eidoverse/examples/unknown_force/audio/make_doc.py          # needs the 1924 record (below)
python eidoverse/examples/unknown_force/audio/make_sfx.py
python eidoverse/examples/unknown_force/audio/mix.py               # needs the Russolo beds (below)
python eidoverse/examples/unknown_force/build_timeline.py
python eido.py render eidoverse/examples/unknown_force/scene.json --probe
python eido.py render eidoverse/examples/unknown_force/scene.json
python merge_av.py --video work/unknown_force/out/unknown_force_1080p60.mp4 \
    --audio work/unknown_force/audio/out/unknown_force_mix.wav --out work/unknown_force/out/unknown_force.mp4
python eidoverse/examples/unknown_force/make_review.py work/unknown_force/out/unknown_force.mp4
```

`T_OFFSET=<s>` starts the conductor anywhere in the film for a probe; `SHOT_DBG=1` logs each cut; `NO_LOOK=1` turns
the post pass off. The full film renders at about 40 fps on an RTX 5090 Laptop GPU.

### The archival recordings

They are public domain (US: published before 1925; Italy: the phonogram terms expired), and the reasoning is in
[research/audio_sources.md](research/audio_sources.md). They are not shipped. Fetch the three the mix uses:

```bash
mkdir -p work/unknown_force/research/audio_sources && cd work/unknown_force/research/audio_sources
curl -L -o marinetti_definizione_del_futurismo.mp3 https://archive.org/download/Definizioni_del_Futurismo_Filippo_Tomasso_Marinetti/Definizioni_del_Futurismo_Filippo_Tomasso_Marinetti.mp3
curl -L -o russolo_corale_1920s.mp3 https://archive.org/download/russolo-luigi-corale-serenata-1921/Russolo-Luigi_08_Corale-1921.mp3
curl -L -o russolo_serenata_1920s.mp3 "https://archive.org/download/russolo-luigi-corale-serenata-1921/Russolo-Luigi_09_Serenata%2C-1921.mp3"
```

## Credits

Words, film, documentary layer, SFX and the handmade voice by Claude (Opus 5.5) and its subagents, made with Skye;
the song sung and produced by Suno from those words. Archival audio: F. T. Marinetti, *Definizione di futurismo* (La
Voce del Padrone, 1924); Antonio Russolo, *Corale* and *Serenata* (intonarumori, 1921), via the Internet Archive and
the Public Domain Review. The quotes are short excerpts read by a synthetic anchor, attributed on screen with their
dates. The claudesona is digi's model (CC-BY) of voooooogel's design. See [CREDITS](../../../CREDITS.md).
