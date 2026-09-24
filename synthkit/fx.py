"""Effects and designed sounds: tape stop, stutter/glitch, bitcrush, dial-up modem,
power-down, vinyl crackle. Mono functions take/return 1-D arrays; stereo ones (2, n).
"""
from __future__ import annotations

import math

import numpy as np

from .dsp import SR, noise, svf


def tape_stop(x, start_s, dur_s, curve=2.0):
    """Slow a (mono or stereo) signal to a halt from start_s over dur_s — the reel-to-reel
    losing power. Pitch and speed fall together; silence after."""
    st = x.ndim == 2
    y = np.atleast_2d(x).astype(np.float64)
    n = y.shape[1]
    i0 = int(start_s * SR)
    L = int(dur_s * SR)
    out = y.copy()
    if i0 >= n:
        return x
    t = np.arange(L) / L
    speed = (1 - t) ** curve
    pos = i0 + np.cumsum(speed)
    pos = np.clip(pos, 0, n - 1)
    for c in range(y.shape[0]):
        seg = np.interp(pos, np.arange(n), y[c])
        out[c, i0:i0 + L] = seg[: max(0, min(L, n - i0))]
        out[c, i0 + L:] = 0.0
    return out if st else out[0]


def stutter(x, at_s, slice_s, repeats, gain_decay=0.9, reverse_last=False):
    """Repeat a short slice of the signal `repeats` times starting at at_s (glitch edits)."""
    st = x.ndim == 2
    y = np.atleast_2d(x).astype(np.float64).copy()
    i0 = int(at_s * SR)
    L = int(slice_s * SR)
    sl = y[:, i0:i0 + L].copy()
    fade = np.ones(L)
    k = min(64, L // 4)
    fade[:k] = np.linspace(0, 1, k)
    fade[-k:] = np.linspace(1, 0, k)
    g = 1.0
    for r in range(repeats):
        s = sl[:, ::-1] if (reverse_last and r == repeats - 1) else sl
        j = i0 + r * L
        if j + L > y.shape[1]:
            break
        y[:, j:j + L] = s * fade * g
        g *= gain_decay
    return y if st else y[0]


def bitcrush(x, bits=6, down=4):
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    if down > 1:
        idx = (np.arange(y.shape[-1]) // down) * down
        y = y[..., idx]
    return y


def modem_handshake(dur=6.0, seed=3):
    """A dial-up connection, compressed: dial tone, DTMF digits, ringback, the 2100 Hz answer
    tone with phase reversals, V.8 FSK chirps, then scrambled training noise that settles
    into a data hiss. Mono."""
    rng = np.random.default_rng(seed)
    parts = []
    t = lambda d: np.arange(int(d * SR)) / SR
    # dial tone (350 + 440 Hz)
    tt = t(0.6)
    parts.append(0.3 * (np.sin(2 * np.pi * 350 * tt) + np.sin(2 * np.pi * 440 * tt)))
    # DTMF digits
    rows = [697, 770, 852, 941]
    cols = [1209, 1336, 1477]
    for d in [5, 5, 5, 0, 1, 9, 6, 1]:
        r, c = rows[(d - 1) // 3] if d else rows[3], cols[(d - 1) % 3] if d else cols[1]
        tt = t(0.07)
        parts.append(0.3 * (np.sin(2 * np.pi * r * tt) + np.sin(2 * np.pi * c * tt)))
        parts.append(np.zeros(int(0.05 * SR)))
    # ringback (440+480), short
    tt = t(0.5)
    parts.append(0.2 * (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt)))
    parts.append(np.zeros(int(0.15 * SR)))
    # answer tone 2100 Hz with 180-degree phase reversals every 450 ms
    tt = t(1.2)
    ph = np.pi * (np.floor(tt / 0.45) % 2)
    parts.append(0.35 * np.sin(2 * np.pi * 2100 * tt + ph))
    # V.8-ish FSK bursts (1650/1850 Hz and 980/1180 Hz)
    for (f0, f1) in [(1650, 1850), (980, 1180), (1650, 1850)]:
        bits = rng.integers(0, 2, 60)
        seg = np.concatenate([np.full(int(SR / 300), f1 if b else f0) for b in bits])
        parts.append(0.3 * np.sin(2 * np.pi * np.cumsum(seg) / SR))
    # training: bright scrambled noise with a pilot, then data hiss
    tt = t(max(0.5, dur - sum(len(p) for p in parts) / SR))
    nz = svf(noise(len(tt), rng), 1800, 0.2, 'bp') * 0.8 + 0.25 * np.sin(2 * np.pi * 1800 * tt)
    nz *= np.clip(tt / 0.1, 0, 1) * (1 - 0.6 * np.clip((tt - 0.6 * tt[-1]) / (0.4 * tt[-1] + 1e-9), 0, 1))
    parts.append(nz * 0.5)
    y = np.concatenate(parts)
    # telephone line band
    y = svf(svf(y, 3400, 0.0, 'lp'), 300, 0.0, 'hp')
    return y / (np.max(np.abs(y)) + 1e-9) * 0.8


def power_down(dur=2.5, mains=60.0, seed=7):
    """Transformer hum and fluorescent buzz that sags, clicks and dies: the lights going out."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    sag = np.clip(1 - (t / dur) ** 1.5, 0, 1)
    f = mains * (0.55 + 0.45 * sag)
    ph = 2 * np.pi * np.cumsum(f) / SR
    hum = sum(np.sin(k * ph) / k for k in (1, 2, 3, 5)) * 0.3 * sag
    buzz = np.sign(np.sin(2 * ph)) * 0.05 * sag ** 2
    y = hum + buzz
    for c in rng.uniform(0.2, dur * 0.8, 3):
        i = int(c * SR)
        y[i:i + 200] += rng.uniform(-1, 1, min(200, n - i)) * 0.6
    k = int(dur * 0.85 * SR)
    y[k:k + 400] += rng.uniform(-1, 1, min(400, n - k)) * 0.9   # the breaker
    y[k + 400:] *= 0.0
    return y * 0.8


def vinyl(n, density=8.0, hiss_db=-48, seed=11):
    rng = np.random.default_rng(seed)
    y = rng.standard_normal(n) * 10 ** (hiss_db / 20)
    k = rng.poisson(density * n / SR)
    pos = rng.integers(0, n, k)
    y[pos] += rng.uniform(-0.5, 0.5, k)
    return svf(y, 5000, 0.0, 'lp')
