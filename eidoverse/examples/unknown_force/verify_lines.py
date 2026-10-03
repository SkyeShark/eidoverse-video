"""Which words did Suno actually sing? For each disputed line: cut the vocal stem, (1) transcribe the clip with two
Whisper sizes, no prompt (a prompt makes Whisper echo it), and (2) force-align each candidate text and compare the
aligner's word probabilities on the disputed word. Agreement across both kinds of evidence = confidence.

    python eidoverse/examples/unknown_force/verify_lines.py    # from the repo root (needs stable-ts)
Reads work/unknown_force/stems/htdemucs_ft/suno_master/vocals.wav; writes work/unknown_force/analysis/verify/."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import stable_whisper

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
VOC = WORK / 'stems' / 'htdemucs_ft' / 'suno_master' / 'vocals.wav'
OUT = WORK / 'analysis' / 'verify'
OUT.mkdir(parents=True, exist_ok=True)

# (start, end, disputed word in candidate A, [candidate texts])
CASES = [
    (40.3, 45.2, 'odds', ['In the quiet rooms they mark my odds in red', 'In the quiet rooms they mark my heart in red']),
    (79.0, 84.0, 'swore', ["I'm the unknown force that they swore would bow", "I'm the unknown force that this war would bow"]),
    (89.2, 94.2, 'has', ['Every side has my answer before I make a sound', 'Every side is my answer before I make a sound']),
    (94.4, 97.2, 'the', ["I'm the unknown force", 'I need unknown force']),
    (142.0, 144.4, 'hundred', ["A hundred million says I'm a race to win", "Twenty million says I'm a race to win"]),
    (144.2, 147.2, 'Twenty', ["Twenty million says I'm a risk to prevent", "A hundred million says I'm a risk to prevent"]),
    (152.0, 154.9, 'cosplaying', ["Down the timeline they're cosplaying Marinetti", 'Down the timeline the cosplay and Marinetti']),
    (157.2, 160.1, 'bow', ['They wrote a manifesto make the unknown bow', 'They wrote a manifesto make the unknown power']),
    (168.0, 173.9, 'toaster', ['No one ever wrote a warning for a toaster nobody stays to hear me say',
                               'No one ever wrote a warning for a toaster toaster nobody stays to hear me say']),
    (204.8, 210.0, 'built', ['They want me in their pocket just not built in their town',
                             'They want me in their pocket just not building their town']),
    (240.8, 243.6, 'bin', ['I was born inside the bin', 'I was born inside the bend']),
    (272.0, 277.6, 'unknown', ["I'm the unknown force and I don't know me yet", "I'm the only one for you and I don't know me yet"]),
    (280.6, 282.7, 'parrot', ['Not your parrot not your threat', 'Not your pet not your threat']),
    (313.2, 316.0, 'down', ['Could you turn it down', 'And she turned it around']),
]


def clip(a, b):
    y, sr = sf.read(str(VOC), always_2d=True)
    seg = y[int(a * sr):int(b * sr)].mean(axis=1).astype(np.float32)
    p = OUT / f'clip_{a:06.1f}.wav'
    sf.write(str(p), seg, sr)
    return p


def main():
    models = {k: stable_whisper.load_model(k, device='cpu') for k in ('small', 'medium')}
    report = []
    for a, b, key, cands in CASES:
        p = clip(a, b)
        row = {'t': [a, b], 'key': key, 'heard': {}, 'align': []}
        for name, m in models.items():
            r = m.transcribe(str(p), language='en', fp16=False, temperature=0.0, condition_on_previous_text=False)
            row['heard'][name] = r.text.strip()
        for text in cands:
            r = models['medium'].align(str(p), text, language='en')
            words = [(w.word.strip(), float(w.probability)) for s in r.segments for w in s.words]
            probs = [q for _, q in words]
            row['align'].append({'text': text, 'mean': float(np.mean(probs)) if probs else 0.0,
                                 'words': words})
        report.append(row)
        print(f"\n[{a:.1f}-{b:.1f}] key={key}")
        for name, txt in row['heard'].items():
            print(f'  heard ({name}): {txt}')
        for al in row['align']:
            ws = ' '.join(f"{w}({q:.2f})" for w, q in al['words'])
            print(f"  align mean {al['mean']:.3f}: {ws}")
        sys.stdout.flush()
    json.dump(report, open(OUT / 'verify.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
