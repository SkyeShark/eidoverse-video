"""The claudesona tests' sung line, made host-side (system Python: voicebox needs scipy / numba): the claudesona's own
handmade voice sings one line of DAISY, and beside the WAV go voicebox's frame-exact visemes, its timed phones (for
the viseme mouth) and the line timings.

    python blender/tests/claudesona/sung_line_host.py [out_dir] [fps]      # from the repo root
-> out/sung_line.wav, out/sung_line.json {fps, duration, frames (voicebox visemes), segs [{ph, t0, t1}], lines}
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, REPO)

from voicebox import Sung, visemes, write_wav  # noqa: E402
from voicebox import eras  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out')
    fps = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    os.makedirs(out, exist_ok=True)
    s = Sung(bpm=120)
    s.line("Daisy Daisy give me your answer do",
           ["B4", "G#4", "E4", "B3", "C#4", "D#4", "E4", "C#4", "E4", "B3"],
           [2, 2, 2, 1.333, 0.667, 0.667, 0.667, 1.333, 0.667, 3.333],
           start_beat=1.0)
    y, segs, tracks = eras.handmade(s)
    wav = os.path.join(out, 'sung_line.wav')
    write_wav(wav, y, 48000)
    dur = len(y) / 48000
    vis = visemes(segs, tracks, dur, fps=fps)
    rec = {'fps': fps, 'duration': dur, 'frames': vis, 'lines': s.lines,
           'segs': [{'ph': g['ph'], 't0': float(g['t0']), 't1': float(g['t1'])} for g in segs]}
    with open(os.path.join(out, 'sung_line.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f)
    print(f'sung_line: {dur:.2f} s, {len(vis)} frames at {fps}, {len(segs)} phones, lines {s.lines}')


if __name__ == '__main__':
    main()
