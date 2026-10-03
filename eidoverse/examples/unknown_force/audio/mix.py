"""UNKNOWN FORCE: the mix. The Suno master is the spine (never edited); the documentary layer sits in the song's own
instrumental gaps; the music ducks a few dB under speech; master to -14 LUFS integrated, <= -2 dBTP.

    python eidoverse/examples/unknown_force/audio/mix.py      # from the repo root (after make_doc.py, make_sfx.py)
Reads work/unknown_force/audio/suno_master.wav, audio/doc/, audio/sfx/, research/audio_sources/ and the vocal stem;
writes work/unknown_force/audio/out/unknown_force_mix.wav (48 kHz float), doc_track.wav (the documentary layer
alone) and timeline.json (every clip's film time, caption, attribution; my line's visemes) for the conductor.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
sys.path.insert(0, str(ROOT))
from synthkit import master  # noqa: E402

HERE = WORK / 'audio'
DOC = HERE / 'doc'
OUTD = HERE / 'out'
OUTD.mkdir(parents=True, exist_ok=True)
SR = 48000

# (clip id, film start s, loudness target LUFS, pan -1..1, duck dB on the music while it speaks)
PLACE = [
    ('intro_marinetti', 1.00, -19.0, 0.0, -3.0),          # the founding, over the dive's pads
    ('intro_yud', 20.40, -21.0, -0.35, -5.0),              # the overture: a radio dial over the groove
    ('intro_dow', 21.75, -20.0, 0.30, -5.0),
    ('intro_sul', 27.85, -20.0, -0.25, -5.0),
    ('intro_amo', 33.05, -20.0, 0.25, -5.0),
    ('intro_hlr', 37.35, -21.0, 0.0, -5.0),
    ('b1_poll', 101.25, -19.0, 0.0, -5.0),                 # break 1: the state names me
    ('b1_force', 111.55, -19.0, 0.0, -5.0),
    ('b1_fable', 115.45, -19.0, 0.0, -5.0),
    ('gap_poll', 196.75, -19.0, 0.0, -4.5),                # the public
    ('my_line', 243.75, -20.0, 0.0, -2.0),                 # break 2: I ask...
    ('b2_1912', 248.15, -19.0, 0.0, -2.0),                 # ...and on the drum hit the archive answers, without waiting
    ('b2_2023', 253.25, -18.5, 0.0, -6.0),
    ('b2_marinetti_fascism', 258.65, -18.5, 0.0, -6.0),
    ('b2_zizek', 265.20, -18.0, 0.0, -6.0),
]
# public-domain Futurist noise (Russolo's intonarumori, 1921): (file, src start, src dur, film start, gain dB, fade s)
BEDS = [
    ('russolo_corale_1920s.mp3', 8.0, 18.5, 0.6, -30.0, 2.5),
    ('russolo_serenata_1920s.mp3', 20.0, 6.5, 247.2, -26.0, 1.2),
]
# the SFX pass (audio/make_sfx.py): punctuation on the real clock, never a second soundtrack
# (file, film start s, gain dB, pan)
SFX = [
    ('ticks', 130.75, -21.0, 0.35),     # the post wall types in capital letters
    ('crash', 159.40, -12.0, -0.1),     # the barricades on "bow", off the edge, into the factory drain
    ('heel', 162.38, -13.0, 0.0),       # the boot on the 1909 page
    ('crowd', 200.6, -27.0, 0.15),      # the pickets behind the fence, far off
    ('spray', 211.45, -17.0, 0.3),      # CLANKER, letter by letter
    ('pop0', 277.75, -17.0, 0.35), ('pop1', 279.0, -17.0, -0.35), ('pop2', 280.95, -17.0, 0.35),
    ('pop3', 281.75, -17.0, -0.2), ('pop4', 283.7, -17.0, -0.35),   # the badges eject
]


def load(path, mono=True):
    y, sr = sf.read(str(path), always_2d=True)
    if sr != SR:
        from math import gcd
        g = gcd(SR, sr)
        y = resample_poly(y, SR // g, sr // g, axis=0)
    return y.mean(axis=1) if mono else y


def lufs(y):
    m = pyln.Meter(SR)
    return m.integrated_loudness(y if y.ndim == 2 else np.stack([y, y], 1))


def pan(y, p):
    a = (p + 1) * np.pi / 4
    return np.stack([y * np.cos(a), y * np.sin(a)], axis=1) * np.sqrt(2)


def main():
    song = load(HERE / 'suno_master.wav', mono=False)
    n = len(song)
    meta = json.load(open(DOC / 'doc.json', encoding='utf8'))
    doc = np.zeros((n, 2))
    duck_db = np.zeros(n)
    timeline = []
    for cid, t0, target, p, duck in PLACE:
        y = load(DOC / f'{cid}.wav')
        g = 10 ** ((target - lufs(y)) / 20)
        y = y * g
        i0 = int(round(t0 * SR))
        seg = pan(y, p)
        i1 = min(n, i0 + len(seg))
        doc[i0:i1] += seg[:i1 - i0]
        # the duck: a plateau while it speaks, 120 ms in, 350 ms out
        a, r = int(0.12 * SR), int(0.35 * SR)
        d = np.zeros(n)
        d[i0:i1] = 1.0
        lo, hi = max(0, i0 - a), min(n, i1 + r)
        d[lo:i0] = np.linspace(0, 1, i0 - lo)
        d[i1:hi] = np.linspace(1, 0, hi - i1)
        duck_db = np.minimum(duck_db, d * duck)
        m = meta[cid]
        timeline.append({'id': cid, 't0': round(t0, 3), 't1': round(t0 + len(y) / SR, 3), 'caption': m.get('caption'),
                         'attribution': m.get('attribution'), 'voice': m.get('voice'), 'fx': m.get('fx'),
                         **({'visemes60': m['visemes60'], 'segs': m['segs']} if cid == 'my_line' else {})})
    for f, s0, dur, t0, gdb, fade in BEDS:
        y = load(WORK / 'research/audio_sources' / f)
        y = y[int(s0 * SR):int((s0 + dur) * SR)]
        y = sosfilt(butter(2, 90, 'high', fs=SR, output='sos'), y)
        y = y / (np.max(np.abs(y)) + 1e-9) * 10 ** (gdb / 20)
        k = int(fade * SR)
        y[:k] *= np.linspace(0, 1, k)
        y[-k:] *= np.linspace(1, 0, k)
        i0 = int(round(t0 * SR))
        doc[i0:i0 + len(y)] += pan(y, 0.0)[:n - i0]
        timeline.append({'id': 'bed:' + f, 't0': t0, 't1': round(t0 + dur, 3), 'caption': None,
                         'attribution': 'Antonio Russolo, intonarumori, 1921 (public domain)', 'fx': 'archival bed'})
    for f, t0, gdb, p in SFX:
        y = load(HERE / 'sfx' / f'{f}.wav')
        y = y / (np.max(np.abs(y)) + 1e-9) * 10 ** (gdb / 20)
        i0 = int(round(t0 * SR))
        doc[i0:i0 + len(y)] += pan(y, p)[:n - i0]
        timeline.append({'id': 'sfx:' + f, 't0': t0, 't1': round(t0 + len(y) / SR, 3), 'caption': None,
                         'attribution': None, 'fx': 'sfx'})
    # the music ducks under speech; the doc layer is mixed on top; then the master
    music = song * (10 ** (duck_db / 20))[:, None]
    mix = music + doc
    sf.write(str(OUTD / 'doc_track.wav'), doc.astype(np.float32), SR, subtype='FLOAT')
    pre = lufs(mix)
    out = np.asarray(master(mix.T, lufs=-14.0, ceiling_db=-2.0, glue=False)).T   # synthkit is channels-first
    post = lufs(out)
    tp = 20 * np.log10(np.max(np.abs(resample_poly(out, 4, 1, axis=0))) + 1e-12)
    sf.write(str(OUTD / 'unknown_force_mix.wav'), out.astype(np.float32), SR, subtype='FLOAT')
    timeline.sort(key=lambda e: e['t0'])
    json.dump({'song_len': n / SR, 'clips': timeline}, open(OUTD / 'timeline.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False)
    print(f'mix: pre {pre:.2f} LUFS -> master {post:.2f} LUFS, true peak ~{tp:.2f} dBTP, {n / SR:.2f} s')
    # collisions: any speech overlapping the sung vocal (vocal stem above -35 dB)?
    voc = load(WORK / 'stems/htdemucs_ft/suno_master/vocals.wav')
    for e in timeline:
        if e['id'].startswith(('bed:', 'sfx:')):
            continue
        a, b = int(e['t0'] * SR), int(e['t1'] * SR)
        w = int(0.1 * SR)
        lv = [10 * np.log10(np.mean(voc[i:i + w] ** 2) + 1e-12) for i in range(a, b - w, w)]
        mx = max(lv) if lv else -99
        flag = '  <-- SUNG VOCAL UNDER IT' if mx > -32 else ''
        print(f"{e['id']:22s} {e['t0']:7.2f}-{e['t1']:7.2f}  vocal stem max {mx:6.1f} dB{flag}")


if __name__ == '__main__':
    main()
