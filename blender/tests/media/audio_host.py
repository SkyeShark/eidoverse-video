"""Host-side half of the audio probe (system Python: voicebox needs scipy and numba, which Blender's Python lacks).

    python blender/tests/media/audio_host.py [out_dir]

Sings one line with voicebox's handmade voice and writes, into out_dir (default blender/tests/media/out/audio_work):
    daisy.wav               48 kHz, the voice
    daisy_visemes.json      {fps: 24, frames: [{aa, ih, ou, ee, oh}], lines: Sung.lines}  (phoneme-exact, 0..1)
    audio_spectrogram.png   voicebox.util.spectrogram_png of the line (also copied to out/)
"""
import json
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKTREE))
from voicebox import Sung, visemes, write_wav  # noqa: E402
from voicebox import eras  # noqa: E402
from voicebox.util import spectrogram_png  # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else WORKTREE / 'blender' / 'tests' / 'media' / 'out' / 'audio_work'
out.mkdir(parents=True, exist_ok=True)
s = Sung(bpm=128)
s.line("Daisy Daisy give me your answer do",
       ["B4", "G#4", "E4", "B3", "C#4", "D#4", "E4", "C#4", "E4", "B3"],
       [2, 2, 2, 1.333, 0.667, 0.667, 0.667, 1.333, 0.667, 3.333], start_beat=1.0)
y, segs, tracks = eras.handmade(s)
write_wav(str(out / 'daisy.wav'), y, 48000)
dur = len(y) / 48000
vis = visemes(segs, tracks, dur, fps=24)
(out / 'daisy_visemes.json').write_text(json.dumps({'fps': 24, 'duration': dur, 'frames': vis, 'lines': s.lines}))
spectrogram_png(y, 48000, str(out / 'audio_spectrogram.png'), title='voicebox handmade: "Daisy Daisy give me your answer do"')
shutil.copy(out / 'audio_spectrogram.png', out.parent / 'audio_spectrogram.png')
peak = max(range(len(vis)), key=lambda i: vis[i]['aa'] + vis[i]['oh'])
print(json.dumps({'wav': str(out / 'daisy.wav'), 'duration': round(dur, 3), 'viseme_frames': len(vis),
                  'lines': s.lines, 'widest_frame': peak, 'widest': vis[peak]}))
