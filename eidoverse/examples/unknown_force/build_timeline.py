"""UNKNOWN FORCE: the film's one timing spine -> out/uf_timeline.json (loaded by scene.js as an asset).

Beats (analysis/beatgrid.json), sections (TREATMENT.md), sung lines + words (props/parole_timing_fake.json: LYRICS.md
aligned to Whisper's words on the vocal stem), visemes at 60 fps from the vocal stem GATED to the sung word windows
(stem bleed must not make her sing along to the band), my own line's exact voicebox visemes, and the documentary clips
(audio/out/timeline.json).   python eidoverse/examples/unknown_force/build_timeline.py   (from the repo root)
Reads and writes the film's data in work/unknown_force/ (analysis/, props/, audio/out/, stems/, out/).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
sys.path.insert(0, str(ROOT))
GRID = {'T': 0.64584, 'bpm': 92.902, 't0': 0.120803}   # the master's measured beat grid, if analysis/ has none
FPS = 60

SECTIONS = [  # name, t0, t1, set, look   (sung times; TREATMENT.md)
    ('intro_dive', 0.0, 20.0, 'dive', 'hush'),
    ('intro_groove', 20.0, 40.8, 'dive', 'argue'),
    ('verse1', 40.8, 61.5, 'quiet_room', 'argue'),
    ('pre1', 61.5, 79.0, 'quiet_room', 'argue'),
    ('chorus1', 79.0, 101.0, 'hole', 'storm'),
    ('break1', 101.0, 120.6, 'hole', 'argue'),
    ('verse2', 120.6, 141.6, 'corridor', 'argue'),
    ('verse3', 141.6, 152.15, 'race', 'argue'),
    ('verse4', 152.15, 163.0, 'race', 'storm'),
    ('pre2', 163.0, 174.6, 'showroom', 'argue'),
    ('chorus2', 174.6, 196.3, 'hole', 'storm'),
    ('gap', 196.3, 201.2, 'news', 'argue'),
    ('verse5', 201.2, 222.6, 'news', 'argue'),
    ('bridge', 222.6, 243.5, 'bin', 'argue'),
    ('break2', 243.5, 272.0, 'collage', 'storm'),
    ('final', 272.0, 294.8, 'hole', 'storm'),
    ('outro', 294.8, 328.84, 'hole', 'hush'),
]


def main():
    from lipsync import get_viseme_timeline
    gp = WORK / 'analysis' / 'beatgrid.json'
    grid = json.load(open(gp)) if gp.exists() else GRID
    lyr = json.load(open(WORK / 'props' / 'parole_timing_fake.json', encoding='utf8'))['lines']
    doc = json.load(open(WORK / 'audio' / 'out' / 'timeline.json', encoding='utf8'))
    song_len = doc['song_len']
    # visemes from the vocal stem, 60 fps; lipsync.py caps at 0.35 -> rescale to 0..1
    raw = get_viseme_timeline(str(WORK / 'stems/htdemucs_ft/suno_master/vocals.wav'), fps=FPS)
    nfr = int(np.ceil(song_len * FPS)) + 1
    keys = ['aa', 'ih', 'ou', 'ee', 'oh']
    vis = np.zeros((nfr, 5))
    for i, f in enumerate(raw[:nfr]):
        w = f.get('visemes', f) if isinstance(f, dict) else {}
        for k, key in enumerate(keys):
            vis[i, k] = min(1.0, float(w.get(key, 0.0)) / 0.35)
    # gate: open only inside sung words (+-0.12 s)
    gate = np.zeros(nfr, bool)
    for ln in lyr:
        for w in ln['words']:
            a, b = int((w['s'] - 0.12) * FPS), int((w['e'] + 0.12) * FPS)
            gate[max(0, a):min(nfr, b)] = True
    vis[~gate] = 0.0
    # my line: exact voicebox visemes (60 fps) laid over its time
    for c in doc['clips']:
        if c['id'] == 'my_line':
            i0 = int(round(c['t0'] * FPS))
            for j, f in enumerate(c['visemes60']):
                if i0 + j < nfr:
                    vis[i0 + j] = [f.get(k, 0.0) for k in keys]
    beats = [grid['t0'] + k * grid['T'] for k in range(int((song_len - grid['t0']) / grid['T']) + 1)]
    out = {
        'song_len': song_len, 'fps': FPS, 'bpm': grid['bpm'], 'beat': grid['T'], 'beat_t0': grid['t0'],
        'beats': [round(b, 4) for b in beats],
        'sections': [{'name': n, 't0': a, 't1': b, 'set': s, 'look': l} for n, a, b, s, l in SECTIONS],
        'lines': lyr,
        'doc': [{k: v for k, v in c.items() if k not in ('visemes60', 'segs')} for c in doc['clips']],
        'visemes_keys': keys,
        'visemes': [[round(float(x), 3) for x in row] for row in vis],
    }
    (WORK / 'out').mkdir(parents=True, exist_ok=True)
    json.dump(out, open(WORK / 'out' / 'uf_timeline.json', 'w', encoding='utf8'), ensure_ascii=False)
    print(f"timeline: {len(out['beats'])} beats, {len(out['sections'])} sections, {len(lyr)} lines, "
          f"{len(out['doc'])} doc clips, {nfr} viseme frames (gated open {gate.mean() * 100:.0f}% of frames)")


if __name__ == '__main__':
    main()
