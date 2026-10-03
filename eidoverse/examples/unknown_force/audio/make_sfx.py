"""UNKNOWN FORCE: the SFX pass, made by hand (numpy) + one edge-tts crowd. Punctuation, not a second soundtrack.

    python eidoverse/examples/unknown_force/audio/make_sfx.py
        -> work/unknown_force/audio/sfx/*.wav (48 kHz mono float) + sfx.json (their lengths)
"""
import asyncio
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
OUT = WORK / 'audio' / 'sfx'
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000
rng = np.random.default_rng(1909)


def bp(y, lo, hi, o=2):
    return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), y)


def lp(y, f, o=2):
    return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), y)


def env(n, a, d):            # attack s, decay tau s
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def norm(y, db=-3):
    return y / (np.max(np.abs(y)) + 1e-9) * 10 ** (db / 20)


def metal_hit(dur=1.2, n=14, lo=180, hi=4200, seed=0):
    r = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for _ in range(n):
        f = r.uniform(lo, hi)
        y += np.sin(2 * np.pi * f * t + r.uniform(0, 6.28)) * np.exp(-t / r.uniform(0.04, 0.5)) * r.uniform(0.2, 1)
    y += bp(r.standard_normal(len(t)), 800, 9000) * np.exp(-t / 0.05) * 2
    y += np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.18) * 1.5
    return norm(y)


def shatter(dur=0.9, grains=420, seed=1):
    r = np.random.default_rng(seed)
    y = np.zeros(int(dur * SR))
    for _ in range(grains):
        i = int(r.beta(1.2, 3.5) * (len(y) - 2000))
        g = bp(r.standard_normal(600), r.uniform(1800, 7000), 11000, 2) * np.exp(-np.arange(600) / r.uniform(40, 160))
        y[i:i + 600] += g * r.uniform(0.1, 1)
    return norm(y)


def whoosh(dur=1.3, seed=2):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = r.standard_normal(n)
    out = np.zeros(n)
    for k, f in enumerate(np.linspace(600, 2200, 12)):
        a, b = int(k / 12 * n), int((k + 1) / 12 * n)
        out[a:b] = bp(x, f * 0.6, f * 1.4)[a:b]
    return norm(out * np.sin(np.linspace(0, np.pi, n)) ** 1.5)


def splash(dur=1.6, seed=3):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = lp(r.standard_normal(n), 900) * np.exp(-t / 0.22) * 2.5           # the slam
    y += bp(r.standard_normal(n), 1500, 8000) * np.exp(-t / 0.5) * 0.7     # the spray
    for _ in range(90):                                                     # bubbles + drips
        i = int(r.uniform(0.1, 1.0) * n)
        f = r.uniform(300, 1400)
        m = int(0.03 * SR)
        if i + m < n:
            y[i:i + m] += np.sin(2 * np.pi * f * (1 + np.linspace(0, 0.6, m)) * np.arange(m) / SR) * np.exp(-np.arange(m) / (0.008 * SR)) * 0.4
    return norm(y)


def heel():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * (70 + 40 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09) * 2.2   # the boot
    y += bp(rng.standard_normal(n), 600, 6000) * np.exp(-t / 0.06)                         # wet slap
    y[int(0.02 * SR):] += splash(0.9 - 0.02, 7)[:n - int(0.02 * SR)] * 0.35
    return norm(y)


def spray(dur=2.9, seed=4):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    hiss = bp(r.standard_normal(n), 2200, 11000, 3)
    gate = np.zeros(n)                     # bursts: one per letter of CLANKER
    for k in range(7):
        a = 0.25 + k * 0.36
        gate += np.exp(-((t - a - 0.12) / 0.11) ** 2)
    rattle = np.zeros(n)                   # the can shaken first
    for k in range(6):
        i = int((0.02 + k * 0.035) * SR)
        rattle[i:i + 400] += bp(r.standard_normal(400), 2500, 7000) * np.exp(-np.arange(400) / 60)
    return norm(hiss * np.clip(gate, 0, 1) * 0.9 + rattle * 0.8)


def pop(seed=5):
    r = np.random.default_rng(seed)
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    fm = np.sin(2 * np.pi * (900 + 600 * np.sin(2 * np.pi * 63 * t)) * t) * np.exp(-t / 0.05)
    crack = bp(r.standard_normal(n), 3000, 12000) * np.exp(-t / 0.015) * 1.4
    embers = np.zeros(n)
    for _ in range(14):
        i = int(r.uniform(0.04, 0.45) * SR)
        embers[i:i + 120] += r.standard_normal(120) * np.exp(-np.arange(120) / 25) * 0.4
    return norm(fm * 0.6 + crack + bp(embers, 2000, 10000))


def ticks(dur=1.6, rate=13, seed=6):
    r = np.random.default_rng(seed)
    y = np.zeros(int(dur * SR))
    for k in range(int(dur * rate)):
        i = int((k / rate + r.uniform(0, 0.012)) * SR)
        g = bp(r.standard_normal(500), 1800, 6500) * np.exp(-np.arange(500) / 50)
        y[i:i + 500] += g * r.uniform(0.6, 1)
    return norm(y)


async def _tts(text, voice, rate, pitch, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(path))


def crowd(dur=21.0):
    """A low murmur of pickets: several voices, pitch-shifted, overlapping, far off behind the fence."""
    lines = ['Not in our town.', 'Who pays the bill?', 'Our water, our power.', 'No data center here.',
             'They never asked us.', 'Not in our town!', 'Shut it down!', 'Who decided this?']
    voices = ['en-US-GuyNeural', 'en-US-JennyNeural', 'en-US-EricNeural', 'en-US-MichelleNeural', 'en-US-RogerNeural',
              'en-US-AriaNeural', 'en-US-SteffanNeural', 'en-US-EmmaNeural']
    raw = OUT / 'raw'
    raw.mkdir(exist_ok=True)
    clips = []
    for i, (ln, v) in enumerate(zip(lines, voices)):
        mp3 = raw / f'crowd{i}.mp3'
        if not mp3.exists():
            asyncio.run(_tts(ln, v, f'{(i % 3) * 6 - 6:+d}%', f'{(i % 4) * 4 - 6:+d}Hz', mp3))
        wav = raw / f'crowd{i}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3), '-ar', str(SR), '-ac', '1', str(wav)], check=True)
        y, _ = sf.read(str(wav))
        clips.append(y)
    n = int(dur * SR)
    out = np.zeros(n)
    r = np.random.default_rng(8)
    for k in range(70):
        c = clips[k % len(clips)]
        i = int(r.uniform(0, max(1, n - len(c))))
        out[i:i + len(c)] += c * r.uniform(0.3, 1.0)
    out = bp(out, 180, 3200)                    # far, through the fence, across the road
    rv = np.convolve(out, bp(r.standard_normal(int(0.6 * SR)), 300, 4000) * np.exp(-np.linspace(0, 7, int(0.6 * SR))))[:n]
    out = out * 0.5 + rv / (np.max(np.abs(rv)) + 1e-9) * np.max(np.abs(out)) * 0.5
    fade = int(1.5 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return norm(out)


def main():
    S = {}
    def save(name, y):
        sf.write(str(OUT / f'{name}.wav'), y.astype(np.float32), SR, subtype='FLOAT')
        S[name] = round(len(y) / SR, 3)
    crash = np.zeros(int(3.2 * SR))
    a = metal_hit(1.4, seed=11); crash[:len(a)] += a                          # the barricade drum, on "bow"
    b = shatter(); crash[int(0.05 * SR):int(0.05 * SR) + len(b)] += b * 0.8
    w = whoosh(1.3); crash[int(0.25 * SR):int(0.25 * SR) + len(w)] += w * 0.5  # off the edge
    m = metal_hit(1.6, n=18, lo=90, hi=2600, seed=12); i = int(1.45 * SR); crash[i:i + len(m)] += m * 0.9   # into the drain
    s = splash(1.6); crash[i:i + len(s)] += s * 0.9
    save('crash', norm(crash))
    save('heel', heel())
    save('spray', spray())
    for k in range(5):
        save(f'pop{k}', pop(20 + k))
    save('ticks', ticks())
    save('crowd', crowd())
    json.dump(S, open(OUT / 'sfx.json', 'w'), indent=1)
    print(S)


if __name__ == '__main__':
    main()
