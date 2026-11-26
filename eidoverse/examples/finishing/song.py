#!/usr/bin/env python3
"""The finishing example, step 1: a short song made from scratch, and its singer's mouth read from the vocal stem.

    python eidoverse/examples/finishing/song.py          (from the repository root)

voicebox sings two lines in its handmade voice; synthkit plays drums, bass and a pad under them at 120 BPM; the
master is -14 LUFS. Nothing is downloaded. Written to work/finishing/:
    song.wav        the mix, 48 kHz stereo, 14 s
    vocal.wav       the voice alone: the stem the mouth is read from
    lyrics.txt      the words with a [Section] line, the shape song_clock.py --lyrics reads
    timeline.json   {"sections", "captions", "words"}: when the synth sang each line and word (known, not detected)
    visemes.json    {"fps", "frames"}: lipsync.get_viseme_timeline_from_vocal on vocal.wav with those words, 0..1
Then it sets that mouth beside voicebox's own phoneme mouth for the same voice (voicebox.visemes: the synth knows
every phoneme it sang) and prints how far they agree: the frames both call open or shut, and the dominant shape
where both are open.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lipsync import VISEMES, get_viseme_timeline_from_vocal  # noqa: E402
from synthkit import SR, Song, inst, master, write_stereo  # noqa: E402
from voicebox import Sung, eras, visemes, write_wav  # noqa: E402

BPM, LENGTH = 120.0, 14.0
CHORDS = ['C', 'Am', 'F', 'G', 'C', 'Am', 'G']               # one a bar, seven bars: 14 s at 120 BPM
LINES = [  # words, pitches, beats (one syllable a note), first beat
    ('Run the reel and print it warm', ['E4', 'E4', 'G4', 'A4', 'G4', 'E4', 'D4'], [1, 0.5, 0.5, 1, 1, 0.5, 3.5], 4),
    ('All the frames are made of light', ['C4', 'D4', 'E4', 'G4', 'E4', 'D4', 'C4'], [1, 0.5, 0.5, 1, 1, 0.5, 3.5], 14),
]
ROOTS = {'C': 'C2', 'Am': 'A1', 'F': 'F1', 'G': 'G1'}


def band():
    """drums, bass and a pad, (2, n) at SR"""
    s = Song(bpm=BPM, bars=len(CHORDS), tail=0.0)
    kick = s.track('kick', inst.kick909, drum=True, gain_db=-4, sidechain_source=True)
    snare = s.track('snare', inst.clap, drum=True, gain_db=-9, reverb=0.15)
    hats = s.track('hats', inst.hat, drum=True, gain_db=-17, pan=0.25)
    bass = s.track('bass', inst.sub_bass, gain_db=-8, duck=True)
    pad = s.track('pad', inst.pad, gain_db=-21, reverb=0.35, duck=True)
    for b, ch in enumerate(CHORDS):
        kick.pattern('x...x...x...x...', b)
        if b > 0:
            snare.pattern('....x.......x...', b)
            hats.pattern('..x...x...x...x.', b)
        bass.note(ROOTS[ch], b * 4, 3.5)
        pad.chord(ch, b * 4, 4, octave=3, vel=0.7)
    return s.render(n=int(LENGTH * SR))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=str(ROOT / 'work' / 'finishing'))
    ap.add_argument('--fps', type=int, default=24)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    sung = Sung(bpm=BPM)
    for words, pitches, beats, start in LINES:
        sung.line(words, pitches, beats, start_beat=start)
    y, segs, tracks = eras.handmade(sung, t_end=LENGTH)
    voice = np.zeros(int(LENGTH * SR))
    voice[:min(len(y), len(voice))] = y[:len(voice)]
    write_wav(str(out / 'vocal.wav'), voice, SR)
    mix = band() + np.stack([voice, voice]) * 0.55
    write_stereo(str(out / 'song.wav'), master(mix, lufs=-14.0))

    # the words and lines as the synth sang them
    words, cur = [], None
    for syl in sung.syls:
        if syl.word_start or cur is None:
            cur = {'word': syl.word, 'start': round(syl.t_on, 3), 'end': round(syl.t_off, 3)}
            words.append(cur)
        cur['end'] = round(syl.t_off, 3)
    captions = [{'text': ln['text'], 't0': round(ln['t0'], 3), 't1': round(ln['t1'], 3)} for ln in sung.lines]
    sections = [{'name': 'intro', 't0': 0.0, 't1': captions[0]['t0']},
                {'name': 'verse', 't0': captions[0]['t0'], 't1': captions[-1]['t1']},
                {'name': 'outro', 't0': captions[-1]['t1'], 't1': LENGTH}]
    (out / 'timeline.json').write_text(json.dumps({'sections': sections, 'captions': captions, 'words': words}, indent=1),
                                       encoding='utf-8')
    (out / 'lyrics.txt').write_text('[verse]\n' + '\n'.join(w for w, *_ in LINES) + '\n', encoding='utf-8')

    # the mouth from the stem, and the synth's own mouth to set it beside
    mouth = get_viseme_timeline_from_vocal(str(out / 'vocal.wav'), words, fps=a.fps)
    (out / 'visemes.json').write_text(json.dumps({'fps': a.fps, 'frames': mouth}), encoding='utf-8')
    truth = visemes(segs, tracks, LENGTH, fps=a.fps)
    n = min(len(mouth), len(truth))
    m = np.array([[f[v] for v in VISEMES] for f in mouth[:n]])
    t = np.array([[f[v] for v in VISEMES] for f in truth[:n]])
    om, ot = m.sum(1) > 0.08, t.sum(1) > 0.08
    both = om & ot
    print(f'[song] {out / "song.wav"}: {LENGTH:g} s; {len(words)} words in {len(captions)} lines')
    print(f'[song] the mouth from the stem against the synth\'s phoneme mouth, {n} frames at {a.fps} fps: open or shut '
          f'alike on {100 * (om == ot).mean():.0f} % (open {om.sum()} / {ot.sum()}); openness correlation '
          f'{np.corrcoef(m.sum(1), t.sum(1))[0, 1]:.2f}; the same dominant shape on '
          f'{100 * (m[both].argmax(1) == t[both].argmax(1)).mean():.0f} % of the frames both call open')


if __name__ == '__main__':
    main()
