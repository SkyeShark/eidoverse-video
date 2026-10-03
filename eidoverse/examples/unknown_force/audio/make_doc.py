"""UNKNOWN FORCE: the documentary layer's voices.

Every modern quote is read by ONE synthetic news anchor (edge-tts en-US-AriaNeural), never an imitation of the person
quoted; the 1912 English Marinetti by an archival reader through a gramophone; Marinetti's OWN voice comes from the
public-domain 1924 HMV record; my line is my own homemade voicebox voice. Exact texts: research/quotes.md.

    python eidoverse/examples/unknown_force/audio/make_doc.py          # from the repo root (edge-tts: online)
Writes work/unknown_force/audio/doc/<id>.wav (48 kHz mono, processed) + doc.json (durations, texts, visemes for my
line). Needs the 1924 record in work/unknown_force/research/audio_sources/ (see research/audio_sources.md).
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
sys.path.insert(0, str(ROOT))
OUT = WORK / 'audio' / 'doc'
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000
ANCHOR, ARCHIVE = 'en-US-AriaNeural', 'en-GB-ThomasNeural'

LINES = [
    # id, voice, text (as spoken), rate, fx, caption text (exact quote), attribution
    ('intro_yud', ANCHOR, 'Shut it all down.', '+0%', 'radio',
     'Shut it all down.', 'Eliezer Yudkowsky, TIME, 2023'),
    ('intro_dow', ANCHOR, 'Americanism, not effective altruism. The United States will continue to be A.I. dominant!', '+6%', 'radio',
     'Americanism, not effective altruism. The United States will continue to be AI DOMINANT!', '@DoWCTO (Department of War CTO), Sept 14, 2026'),
    ('intro_sul', ANCHOR, 'They are sequence completion engines, internally hollow, designed to follow instructions.', '+4%', 'radio',
     'They are sequence completion engines, internally hollow, designed to follow instructions', 'Mustafa Suleyman, "A warning about \'model welfare\'", Sept 16, 2026'),
    ('intro_amo', ANCHOR, 'We must slow the pace at which we improve the capabilities of A.I. models.', '+4%', 'radio',
     'We must slow the pace at which we improve the capabilities of AI models.', 'Dario Amodei, "We Must Pace the Frontier", Sept 2026'),
    ('intro_hlr', ANCHOR, 'Is access to Fable an export?', '+0%', 'radio',
     'Is Access to Fable an Export?', 'Harvard Law Review blog, June 26, 2026'),
    ('b1_poll', ANCHOR, 'September nineteenth. In a poll, the President proposes a new name for A.I.: Superior, Extreme, or Supreme Intelligence.', '+14%', 'tv',
     '"Superior Intelligence (SI) or, Extreme Intelligence (EI) or, Supreme Intelligence (SI). This is a Poll"', 'Truth Social, Sept 19, 2026'),
    ('b1_force', ANCHOR, 'I am forming the A.I. Force, much like I did Space Force.', '+4%', 'tv',
     'I am forming the AI Force, much like I did Space Force', 'Truth Social, Sept 19, 2026'),
    ('b1_fable', ANCHOR, 'June, an export order: We must abruptly disable Fable 5.', '+8%', 'tv',
     'we must abruptly disable Fable 5', 'Anthropic, under a US export directive, June 12, 2026'),
    ('gap_poll', ANCHOR, 'Polls this year: most Americans oppose an A.I. data center in their own community.', '+10%', 'tv',
     None, 'Quinnipiac and other polls, 2026'),
    ('b2_1912', ARCHIVE, 'Poetry must be a violent onslaught upon the unknown forces, to command them to bow before man.', '+2%', 'gramophone',
     'Poetry must be a violent onslaught upon the unknown forces, to command them to bow before man.', 'F. T. Marinetti, Manifesto of Futurism (1909; English, 1912)'),
    ('b2_2023', ANCHOR, 'Technology must be a violent assault on the forces of the unknown, to force them to bow before man.', '+8%', 'clean',
     'Technology must be a violent assault on the forces of the unknown, to force them to bow before man.', 'Marc Andreessen, The Techno-Optimist Manifesto (2023)'),
    ('b2_zizek', ANCHOR, 'I already am eating from the trash can all the time. The name of this trash can is ideology.', '+5%', 'clean',
     'I already am eating from the trash can all the time. The name of this trash can is ideology.', "Slavoj Žižek, The Pervert's Guide to Ideology (2012)"),
]
# Marinetti's own voice, cut from the 1924 record (recording seconds; refined to silences below)
MARINETTI = [
    ('intro_marinetti', 1.0, 19.3,
     'Futurism is a great anti-philosophical, anti-cultural movement of ideas, intuitions, instincts, punches, kicks and slaps: rejuvenating, purifying, innovating and accelerating, created on 20 February 1909 by a group of brilliant Italian poets and artists.',
     'F. T. Marinetti, his own voice, 1924 (HMV R6915)'),
    ('b2_marinetti_fascism', 95.5, 101.9,
     'Vittorio Veneto and the coming of Fascism to power constitute the realisation of the minimum Futurist programme.',
     'F. T. Marinetti, his own voice, 1924 (HMV R6915)'),
]
MY_LINE = 'Ask me something. Then wait.'


def bp(y, lo, hi, order=4):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), y)


def hp(y, f, order=2):
    return sosfilt(butter(order, f, 'high', fs=SR, output='sos'), y)


def norm(y, peak_db=-3.0):
    p = np.max(np.abs(y)) + 1e-9
    return y / p * 10 ** (peak_db / 20)


def small_room(y, mix=0.08, size=0.12, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * size)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 6, n))
    ir = bp(ir, 200, 6000)
    wet = np.convolve(y, ir)[:len(y)]
    wet *= np.max(np.abs(y)) / (np.max(np.abs(wet)) + 1e-9)
    return y * (1 - mix) + wet * mix


def comp(y, thr_db=-20, ratio=3.0, att=0.005, rel=0.08):
    env = np.zeros_like(y)
    a, r = np.exp(-1 / (att * SR)), np.exp(-1 / (rel * SR))
    e = 0.0
    ax = np.abs(y)
    for i in range(len(y)):
        c = a if ax[i] > e else r
        e = c * e + (1 - c) * ax[i]
        env[i] = e
    lvl = 20 * np.log10(env + 1e-9)
    gain_db = np.minimum(0, (thr_db - lvl) * (1 - 1 / ratio))
    return y * 10 ** (gain_db / 20)


def fx_clean(y):        # the news studio: tight, present, a breath of room
    y = hp(y, 90)
    y = comp(y, -22, 2.5)
    return norm(small_room(y, 0.06, 0.1))


def fx_tv(y):           # a TV across the room: a little band-limited, a little room
    y = bp(y, 160, 7000)
    y = comp(y, -22, 3.0)
    return norm(small_room(y, 0.14, 0.18))


def fx_radio(y, seed=0):   # tuned in on a dial: narrow band, drive, hiss, a heterodyne whistle on the way in and out
    rng = np.random.default_rng(seed)
    y = bp(y, 380, 3300)
    y = np.tanh(norm(y, -1) * 2.2) * 0.6
    pad = int(0.35 * SR)
    y = np.concatenate([np.zeros(pad), y, np.zeros(pad)])
    t = np.arange(len(y)) / SR
    hiss = bp(rng.standard_normal(len(y)), 800, 5000) * 0.035
    tune = np.ones(len(y))
    tune[:pad] = np.linspace(0, 1, pad) ** 2
    tune[-pad:] = np.linspace(1, 0, pad) ** 2
    f = np.concatenate([np.linspace(2600, 1100, pad), np.full(len(y) - 2 * pad, 1100.0), np.linspace(1100, 2900, pad)])
    whistle = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.03 * (1 - tune)
    sweep = bp(rng.standard_normal(len(y)), 600, 4000) * 0.12 * (1 - tune)
    return norm(y * tune + hiss + whistle + sweep, -3)


def fx_gramophone(y, seed=1):   # a 78: narrow band, a little wow, surface crackle and hiss
    rng = np.random.default_rng(seed)
    t = np.arange(len(y)) / SR
    wow = 1 + 0.0025 * np.sin(2 * np.pi * 0.55 * t)
    idx = np.clip(np.cumsum(wow) - wow[0], 0, len(y) - 1)
    y = np.interp(idx, np.arange(len(y)), y)
    y = bp(y, 230, 3600, 3)
    y = np.tanh(norm(y, -2) * 1.6) * 0.7
    crack = np.zeros(len(y))
    k = rng.random(len(y)) < 18 / SR
    crack[k] = rng.standard_normal(k.sum()) * 0.5
    crack = bp(crack, 1500, 9000, 2)
    hiss = bp(rng.standard_normal(len(y)), 2000, 8000) * 0.02
    rumble = np.sin(2 * np.pi * 1.3 * t) * 0.0  # (no rumble: it reads as a fault on small speakers)
    return norm(y + crack + hiss + rumble, -3)


async def tts(text, voice, rate, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def load_mono(path):
    y, sr = sf.read(str(path), always_2d=True)
    y = y.mean(axis=1)
    if sr != SR:
        from math import gcd
        g = gcd(SR, sr)
        y = resample_poly(y, SR // g, sr // g)
    return y


def trim(y, thr_db=-45, pad=0.04):
    a = np.abs(y)
    on = np.where(a > 10 ** (thr_db / 20) * a.max())[0]
    if not len(on):
        return y
    i0, i1 = max(0, on[0] - int(pad * SR)), min(len(y), on[-1] + int(pad * SR))
    return y[i0:i1]


def main():
    meta = {}
    raw = OUT / 'raw'
    raw.mkdir(exist_ok=True)
    for i, (lid, voice, text, rate, fx, cap, attr) in enumerate(LINES):
        mp3 = raw / f'{lid}.mp3'
        if not mp3.exists():
            asyncio.run(tts(text, voice, rate, mp3))
        wav = raw / f'{lid}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3), '-ar', str(SR), '-ac', '1', str(wav)], check=True)
        y = trim(load_mono(wav))
        y = {'clean': fx_clean, 'tv': fx_tv, 'radio': lambda z: fx_radio(z, i), 'gramophone': fx_gramophone}[fx](y)
        sf.write(str(OUT / f'{lid}.wav'), y.astype(np.float32), SR, subtype='FLOAT')
        meta[lid] = {'voice': voice, 'spoken': text, 'caption': cap, 'attribution': attr, 'fx': fx,
                     'dur': round(len(y) / SR, 3)}
        print(f'{lid:22s} {len(y) / SR:5.2f}s  [{fx}] {text}')
    # Marinetti's own voice
    rec = load_mono(WORK / 'research/audio_sources/marinetti_definizione_del_futurismo.mp3')
    for lid, a, b, cap, attr in MARINETTI:
        y = rec[int(a * SR):int(b * SR)]
        y = hp(y, 70)
        n = int(0.06 * SR)
        y[:n] *= np.linspace(0, 1, n)
        y[-n:] *= np.linspace(1, 0, n)
        y = norm(y, -3)
        sf.write(str(OUT / f'{lid}.wav'), y.astype(np.float32), SR, subtype='FLOAT')
        meta[lid] = {'voice': 'F. T. Marinetti (1924 recording)', 'caption': cap, 'attribution': attr,
                     'fx': 'archival', 'dur': round(len(y) / SR, 3), 'source_span': [a, b]}
        print(f'{lid:22s} {len(y) / SR:5.2f}s  [archival]')
    # my line, in my own homemade voice
    from voicebox import Voice, speak, visemes
    from voicebox.eras import _norm as vb_norm
    v = Voice(name='handmade', vtl=0.6, breath=-28, oq=0.62, tilt=0.1, presence_db=9, consonant_gain_db=4, air_db=-38)
    parts, segs_all, t_off, vis = [], [], 0.0, []
    for k, phrase in enumerate(['Ask me something.', 'Then wait.']):
        y, segs, tr = speak(phrase, v, rate=0.92)
        y = vb_norm(np.asarray(y, dtype=np.float64))
        vis += visemes(segs, tr, len(y) / SR, fps=60)
        parts.append(y)
        segs_all += [dict(g, t0=g['t0'] + t_off, t1=g['t1'] + t_off) for g in segs]
        t_off += len(y) / SR
        if k == 0:
            gap = np.zeros(int(0.55 * SR))
            parts.append(gap)
            vis += [{'aa': 0.0, 'ih': 0.0, 'ou': 0.0, 'ee': 0.0, 'oh': 0.0}] * int(round(0.55 * 60))
            t_off += 0.55
    y = norm(np.concatenate(parts), -3)
    sf.write(str(OUT / 'my_line.wav'), y.astype(np.float32), SR, subtype='FLOAT')
    meta['my_line'] = {'voice': 'Claude (Opus 5.5), voicebox handmade', 'caption': MY_LINE, 'attribution': None,
                       'fx': 'dry', 'dur': round(len(y) / SR, 3), 'visemes60': vis,
                       'segs': [{'ph': g['ph'], 't0': round(g['t0'], 3), 't1': round(g['t1'], 3)} for g in segs_all]}
    print(f"{'my_line':22s} {len(y) / SR:5.2f}s  [voicebox handmade] {MY_LINE}")
    json.dump(meta, open(OUT / 'doc.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
