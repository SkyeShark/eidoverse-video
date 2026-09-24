"""Core DSP for synthkit: band-limited oscillators, envelopes and a state-variable filter.

Everything renders at SR = 48 kHz into float64 numpy arrays. Frequency inputs
may be scalars or per-sample arrays (for glides, vibrato and FM).
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

SR = 48000


def as_freq(f, n):
    f = np.asarray(f, dtype=np.float64)
    return np.full(n, float(f)) if f.ndim == 0 else f[:n]


@njit(cache=True, fastmath=True)
def _polyblep(t, dt):
    if t < dt:
        t = t / dt
        return t + t - t * t - 1.0
    elif t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


@njit(cache=True, fastmath=True)
def _saw(freq, sr, phase0):
    n = freq.shape[0]
    out = np.empty(n)
    ph = phase0
    for i in range(n):
        dt = freq[i] / sr
        out[i] = 2.0 * ph - 1.0 - _polyblep(ph, dt)
        ph += dt
        if ph >= 1.0:
            ph -= 1.0
    return out


@njit(cache=True, fastmath=True)
def _pulse(freq, duty, sr, phase0):
    n = freq.shape[0]
    out = np.empty(n)
    ph = phase0
    for i in range(n):
        dt = freq[i] / sr
        d = duty[i]
        v = 1.0 if ph < d else -1.0
        v += _polyblep(ph, dt)
        t2 = ph - d
        if t2 < 0.0:
            t2 += 1.0
        v -= _polyblep(t2, dt)
        out[i] = v
        ph += dt
        if ph >= 1.0:
            ph -= 1.0
    return out


@njit(cache=True, fastmath=True)
def _tri(freq, sr, phase0):
    n = freq.shape[0]
    out = np.empty(n)
    ph = phase0
    for i in range(n):
        out[i] = 4.0 * abs(ph - 0.5) - 1.0
        ph += freq[i] / sr
        if ph >= 1.0:
            ph -= 1.0
    return out


def saw(f, n, phase=0.0):
    return _saw(as_freq(f, n), float(SR), float(phase))


def pulse(f, n, duty=0.5, phase=0.0):
    d = np.asarray(duty, dtype=np.float64)
    d = np.full(n, float(d)) if d.ndim == 0 else d[:n]
    return _pulse(as_freq(f, n), d, float(SR), float(phase))


def tri(f, n, phase=0.0):
    return _tri(as_freq(f, n), float(SR), float(phase))


def sine(f, n, phase=0.0):
    fr = as_freq(f, n)
    return np.sin(2 * np.pi * (np.cumsum(fr) / SR + phase))


def supersaw(f, n, voices=7, detune=0.22, rng=None):
    """Roland JP-8000-style: detuned saws (spread in cents scaled by `detune`) with random phases."""
    rng = rng or np.random.default_rng(1)
    fr = as_freq(f, n)
    offs = np.array([-1.0, -0.7, -0.35, 0.0, 0.35, 0.7, 1.0])[:voices] if voices <= 7 else np.linspace(-1, 1, voices)
    out = np.zeros(n)
    for o in offs:
        cents = o * detune * 60.0
        out += saw(fr * 2 ** (cents / 1200.0), n, rng.uniform())
    return out / math.sqrt(len(offs))


def noise(n, rng=None):
    rng = rng or np.random.default_rng(2)
    return rng.uniform(-1, 1, n)


def adsr(n, a=0.005, d=0.1, s=0.7, r=0.1, gate=None):
    """ADSR envelope of n samples; the note is held for `gate` seconds (default: until release starts)."""
    gate = (n / SR - r) if gate is None else gate
    t = np.arange(n) / SR
    env = np.empty(n)
    a = max(a, 1e-4)
    d = max(d, 1e-4)
    att = t < a
    env[att] = t[att] / a
    dec = (t >= a) & (t < a + d)
    env[dec] = 1.0 - (1.0 - s) * (t[dec] - a) / d
    sus = (t >= a + d) & (t < gate)
    env[sus] = s
    # level at gate time
    g_level = (gate / a) if gate < a else (1.0 - (1.0 - s) * (gate - a) / d if gate < a + d else s)
    rel = t >= gate
    env[rel] = g_level * np.exp(-(t[rel] - gate) / max(r / 5.0, 1e-4))
    return env


def exp_decay(n, tau):
    return np.exp(-np.arange(n) / (SR * max(tau, 1e-5)))


@njit(cache=True, fastmath=True)
def _svf(x, cutoff, res, mode, sr):
    """Chamberlin/Simper state-variable filter (TPT form), per-sample cutoff. mode: 0 lp, 1 bp, 2 hp."""
    n = x.shape[0]
    y = np.empty(n)
    ic1 = 0.0
    ic2 = 0.0
    k = 2.0 - 2.0 * res
    for i in range(n):
        fc = cutoff[i]
        if fc < 10.0:
            fc = 10.0
        if fc > 0.49 * sr:
            fc = 0.49 * sr
        g = math.tan(math.pi * fc / sr)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if mode == 0:
            y[i] = v2
        elif mode == 1:
            y[i] = v1
        else:
            y[i] = x[i] - k * v1 - v2
    return y


def svf(x, cutoff, res=0.2, mode='lp'):
    c = np.asarray(cutoff, dtype=np.float64)
    c = np.full(len(x), float(c)) if c.ndim == 0 else c[:len(x)]
    return _svf(np.asarray(x, dtype=np.float64), c, float(min(0.98, max(0.0, res))),
                {'lp': 0, 'bp': 1, 'hp': 2}[mode], float(SR))


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def pan_stereo(x, pan=0.0):
    """Constant-power pan, pan in [-1, 1]. Returns (2, n)."""
    th = (pan + 1) * np.pi / 4
    return np.vstack([x * np.cos(th), x * np.sin(th)])


def db(x):
    return 10 ** (x / 20.0)
