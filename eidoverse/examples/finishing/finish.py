#!/usr/bin/env python3
"""The finishing example, step 3: a rendered film through the finishing tools, in their order.

    python eidoverse/examples/finishing/finish.py [--film work/finishing/film_video_only.mp4] [--parts 3] [--align]

    1. merge_av.py                the song onto the render                       -> work/finishing/film.mp4
    2. song_clock.py              the song's clock: beats, bars, sections         -> work/finishing/song_clock.json
                                  (--align: also the lines placed by align_lyrics.py on vocal.wav; needs stable-ts and a
                                  Whisper model, so it is off by default and the clock takes song.py's own captions)
    3. song_clock.py --offset     the film's sound against the song: 0 ms expected
    4. film_print.py              the 1970s release print with the lines lettered in, --parts ranges side by side
                                  -> work/finishing/film_print.mp4, and two stills with before | after pictures in
                                  work/finishing/stills/
    5. contact_sheet.py --lines   the printed film line by line, its spectrogram and beats
                                  -> work/finishing/film_print_contact_sheet_lines.jpg
A film from any renderer will do: the WebGPU scene beside this file, or the Blender edition's own scene. Look at the
stills and the sheet when it ends.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOWIN = 0x08000000 if os.name == 'nt' else 0


def run(*args):
    cmd = [sys.executable] + [str(a) for a in args]
    print('+ python ' + ' '.join(Path(a).name if os.path.isabs(str(a)) else str(a) for a in args), flush=True)
    # (stdin given, so the windowless child writes to this process's stdout and stderr, not to a console of its own)
    r = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, creationflags=NOWIN)
    if r.returncode != 0:
        raise SystemExit(f'step failed (exit {r.returncode}): {args[0]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--work', default=str(ROOT / 'work' / 'finishing'), help="song.py's folder")
    ap.add_argument('--film', default=None, help='the rendered film (default: <work>/film_video_only.mp4)')
    ap.add_argument('--parts', type=int, default=3)
    ap.add_argument('--era', default='1970s')
    ap.add_argument('--align', action='store_true', help='place the lines with align_lyrics.py (Whisper)')
    a = ap.parse_args()
    work = Path(a.work)
    film = Path(a.film) if a.film else work / 'film_video_only.mp4'
    song, clock, merged = work / 'song.wav', work / 'song_clock.json', work / 'film.mp4'
    printed = work / 'film_print.mp4'

    run('merge_av.py', '--video', film, '--audio', song, '--out', merged)
    if a.align:
        run('song_clock.py', song, '--fps', 24, '--out', clock, '--lyrics', work / 'lyrics.txt', '--vocal', work / 'vocal.wav',
            '--downbeat', 0.0)
    else:
        run('song_clock.py', song, '--fps', 24, '--out', clock, '--downbeat', 0.0)
        # (the synth's own lines and sections, in place of an alignment)
        c = json.loads(clock.read_text(encoding='utf-8'))
        tl = json.loads((work / 'timeline.json').read_text(encoding='utf-8'))
        c['sections'], c['captions'] = tl['sections'], tl['captions']
        clock.write_text(json.dumps(c, indent=1), encoding='utf-8')
    run('song_clock.py', song, '--offset', merged)
    run('film_print.py', merged, '--out', printed, '--era', a.era, '--letters', clock, '--parts', a.parts)
    run('film_print.py', merged, '--era', a.era, '--letters', clock, '--stills', work / 'stills', '--at', '4.0,9.5')
    run('contact_sheet.py', printed, '--lines', '--timeline', clock, '--beats', clock, '--gap', 1.5,
        '--title', 'Run the reel', '--synopsis', 'The finishing example: a song made with voicebox and synthkit, sung by '
        'the classic Claude sona with its mouth read from the vocal stem, printed as a 1970s release print.')
    print(f'[finish] {printed}\n[finish] look at {work / "stills"} and {work / "film_print_contact_sheet_lines.jpg"}')


if __name__ == '__main__':
    main()
