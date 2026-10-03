"""Raw Whisper transcription of the vocal stem (no lyric prompt: a prompt makes Whisper echo it).

    python eidoverse/examples/unknown_force/transcribe_raw.py [vocals.wav] [model]     # from the repo root
Defaults: work/unknown_force/stems/htdemucs_ft/suno_master/vocals.wav, the medium model (stable-ts, CPU).
Writes work/unknown_force/analysis/raw_transcript.json (segments with word times) and prints the lines.
"""
import json, sys
from pathlib import Path
import stable_whisper
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
src = sys.argv[1] if len(sys.argv) > 1 else str(WORK / 'stems' / 'htdemucs_ft' / 'suno_master' / 'vocals.wav')
m = stable_whisper.load_model(sys.argv[2] if len(sys.argv) > 2 else 'medium', device='cpu')
r = m.transcribe(src, language='en', word_timestamps=True, vad=True, fp16=False,
                 condition_on_previous_text=False, temperature=0.0)
segs = [{'start': s.start, 'end': s.end, 'text': s.text.strip(),
         'words': [{'w': w.word.strip(), 's': w.start, 'e': w.end} for w in s.words]} for s in r.segments]
(WORK / 'analysis').mkdir(parents=True, exist_ok=True)
json.dump(segs, open(WORK / 'analysis' / 'raw_transcript.json', 'w'), indent=1)
for s in segs:
    print(f"{s['start']:7.2f}-{s['end']:7.2f}  {s['text']}")
