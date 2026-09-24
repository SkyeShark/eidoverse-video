"""Instruments: each is a function (freq_hz, dur_s, vel, **params) -> mono float array.

Melodic instruments render one note including its release tail; drums take
(vel, **params). Sound-design notes live next to each recipe.
"""
from __future__ import annotations

import math

import numpy as np

from .dsp import (SR, adsr, exp_decay, noise, pulse, saw, sine, supersaw, svf, tri)


def _n(dur, tail=0.0):
    return max(1, int((dur + tail) * SR))


# --- melodic --------------------------------------------------------------------------
def chip_pulse(f, dur, vel=1.0, duty=0.25, vib=0.0, arp=None, release=0.03, bits=4):
    """NES/C64 pulse channel: fixed duty, 4-bit volume steps, optional chip arpeggio
    (a list of semitone offsets cycled at 50 Hz, the classic 'chord in one voice')."""
    n = _n(dur, release)
    t = np.arange(n) / SR
    fr = np.full(n, f)
    if arp:
        step = (t * 50).astype(int) % len(arp)
        fr = f * 2 ** (np.array(arp)[step] / 12.0)
    if vib:
        fr = fr * 2 ** (vib / 1200 * np.sin(2 * np.pi * 6 * t) * np.clip((t - 0.15) / 0.2, 0, 1))
    x = pulse(fr, n, duty)
    env = adsr(n, 0.002, 0.08, 0.7, release, gate=dur)
    q = 2 ** bits - 1
    env = np.round(env * q) / q
    return x * env * vel * 0.5


def chip_tri(f, dur, vel=1.0, release=0.01):
    """NES triangle: 4-bit stepped triangle, no volume control (the classic chip bass)."""
    n = _n(dur, release)
    ph = np.cumsum(np.full(n, f) / SR) % 1.0
    x = 1 - 4 * np.abs(ph - 0.5)
    x = np.round(x * 7.5) / 7.5
    env = np.ones(n)
    env[int(dur * SR):] = 0
    return x * env * vel * 0.55


def pluck(f, dur, vel=1.0, bright=0.6, release=0.15, detune=0.12):
    """Supersaw pluck: fast filter envelope, short decay."""
    n = _n(dur, release)
    x = supersaw(f, n, 5, detune)
    fenv = 300 + (2500 + 9000 * bright) * exp_decay(n, 0.09)
    y = svf(x, fenv, 0.25, 'lp')
    env = adsr(n, 0.002, 0.25, 0.25, release, gate=dur)
    return y * env * vel * 0.5


def pad(f, dur, vel=1.0, attack=0.25, release=0.6, cutoff=3800, detune=0.3):
    n = _n(dur, release)
    x = supersaw(f, n, 7, detune)
    y = svf(x, cutoff, 0.1, 'lp')
    env = adsr(n, attack, 0.3, 0.85, release, gate=dur)
    return y * env * vel * 0.35


def lead_saw(f, dur, vel=1.0, release=0.08, cutoff=5500, glide_from=None, vib=18):
    n = _n(dur, release)
    t = np.arange(n) / SR
    fr = np.full(n, f)
    if glide_from:
        g = np.clip(t / 0.06, 0, 1)
        fr = glide_from * (f / glide_from) ** g
    fr = fr * 2 ** (vib / 1200 * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.2) / 0.3, 0, 1))
    x = 0.6 * saw(fr, n) + 0.4 * saw(fr * 1.004, n, 0.3)
    y = svf(x, cutoff, 0.2, 'lp')
    return y * adsr(n, 0.004, 0.2, 0.8, release, gate=dur) * vel * 0.4


def sub_bass(f, dur, vel=1.0, release=0.06, drive=1.6):
    n = _n(dur, release)
    x = sine(f, n) + 0.25 * sine(2 * f, n)
    x = np.tanh(drive * x) / np.tanh(drive)
    return x * adsr(n, 0.004, 0.1, 0.9, release, gate=dur) * vel * 0.6


def reese(f, dur, vel=1.0, release=0.08, cutoff=900):
    n = _n(dur, release)
    x = saw(f, n) + saw(f * 1.012, n, 0.5)
    y = svf(x, cutoff, 0.3, 'lp')
    return np.tanh(1.5 * y) * adsr(n, 0.01, 0.1, 0.9, release, gate=dur) * vel * 0.35


def fm_epiano(f, dur, vel=1.0, release=0.4):
    """DX7 'E.PIANO 1'-flavoured 2x2-operator FM: a 1:1 pair for the body and a 14:1
    pair for the tine 'clank', both with velocity-scaled modulation index."""
    n = _n(dur, release)
    t = np.arange(n) / SR
    env_c = adsr(n, 0.001, 1.8, 0.0, release, gate=dur) * (0.6 + 0.4 * vel)
    idx1 = (1.2 + 1.6 * vel) * exp_decay(n, 0.9)
    body = np.sin(2 * np.pi * f * t + idx1 * np.sin(2 * np.pi * f * t))
    idx2 = (2.5 * vel) * exp_decay(n, 0.05)
    tine = np.sin(2 * np.pi * f * t + idx2 * np.sin(2 * np.pi * 14 * f * t)) * exp_decay(n, 0.35)
    return (0.75 * body + 0.35 * tine) * env_c * vel * 0.45


def organ_1961(f, dur, vel=1.0, release=0.05):
    """The Music-N computer 'organ' of Bell Labs demos: a few pure sine partials, flat, no vibrato."""
    n = _n(dur, release)
    x = sine(f, n) + 0.5 * sine(2 * f, n) + 0.25 * sine(3 * f, n) + 0.12 * sine(4 * f, n)
    return x * adsr(n, 0.02, 0.05, 0.9, release, gate=dur) * vel * 0.3


def music_box(f, dur, vel=1.0):
    """Tuned steel comb: inharmonic sine partials with fast-decaying highs."""
    n = _n(dur, 2.5)
    parts = [(1.0, 1.0, 1.6), (2.76, 0.35, 0.5), (5.40, 0.18, 0.25), (8.93, 0.08, 0.12)]
    x = np.zeros(n)
    for ratio, amp, tau in parts:
        x += amp * sine(f * ratio, n) * exp_decay(n, tau)
    click = noise(int(0.004 * SR)) * 0.1
    x[:len(click)] += click
    return x * vel * 0.4


def piano(f, dur, vel=1.0, release=0.3):
    """Additive piano sketch: stretched partials (inharmonicity), per-partial decay, hammer thump."""
    n = _n(dur, release + 0.5)
    B = 0.0004
    x = np.zeros(n)
    for k in range(1, 12):
        fk = k * f * math.sqrt(1 + B * k * k)
        if fk > 16000:
            break
        amp = (1.0 / k) * (0.6 + 0.4 * vel) ** (k * 0.5)
        tau = 2.2 / (1 + 0.35 * k) * (220.0 / max(80.0, f)) ** 0.3
        x += amp * sine(fk, n, np.random.default_rng(k).uniform()) * exp_decay(n, tau)
    x[:int(0.01 * SR)] += noise(int(0.01 * SR)) * 0.05 * vel
    damp = np.ones(n)
    g = int(dur * SR)
    if g < n:
        damp[g:] = np.exp(-np.arange(n - g) / (SR * release / 4))
    return x * damp * vel * 0.35


# --- drums ---------------------------------------------------------------------------------
def kick909(vel=1.0, tune=1.0, decay=0.35, click=0.6):
    n = _n(decay * 2.2)
    t = np.arange(n) / SR
    f = (48 + 180 * np.exp(-t / 0.035)) * tune
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    cl = svf(noise(n), 3200, 0.1, 'bp') * np.exp(-t / 0.004) * click
    return np.tanh(1.8 * (body + cl)) * vel * 0.9


def kick808(vel=1.0, tune=1.0, decay=0.9):
    n = _n(decay * 2)
    t = np.arange(n) / SR
    f = (45 + 55 * np.exp(-t / 0.02)) * tune
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    return np.tanh(1.3 * body) * vel * 0.95


def snare909(vel=1.0, tone=0.5, snappy=0.8):
    n = _n(0.4)
    t = np.arange(n) / SR
    body = (np.sin(2 * np.pi * 185 * t) + 0.6 * np.sin(2 * np.pi * 330 * t)) * np.exp(-t / 0.07) * tone
    nz = svf(noise(n), 6500, 0.1, 'lp')
    nz = svf(nz, 900, 0.0, 'hp') * np.exp(-t / 0.12) * snappy
    return np.tanh(1.4 * (body + nz)) * vel * 0.7


def clap(vel=1.0):
    """808-style clap: three quick noise bursts then a longer tail, band-passed ~1.1 kHz."""
    n = _n(0.45)
    t = np.arange(n) / SR
    env = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.023)):
        i = int(off * SR)
        env[i:] += np.exp(-(t[:n - i]) / 0.006) * (0.9 - 0.15 * k)
    i = int(0.03 * SR)
    env[i:] += 0.7 * np.exp(-t[:n - i] / 0.13)
    x = svf(noise(n, np.random.default_rng(9)), 1150, 0.35, 'bp') * env
    return x * vel * 1.6


_HAT_RATIOS = [2.0, 3.0, 4.16, 5.43, 6.79, 8.21]


def hat(vel=1.0, open_=False, decay=None):
    """808 metal: six square oscillators at inharmonic ratios, band-passed high."""
    dec = decay or (0.32 if open_ else 0.045)
    n = _n(dec * 4)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for r in _HAT_RATIOS:
        x += np.sign(np.sin(2 * np.pi * 150 * r * t + r))
    x = svf(x, 8500, 0.3, 'bp')
    x = svf(x, 6500, 0.0, 'hp')
    return x * np.exp(-t / dec) * vel * 0.25


def crash(vel=1.0):
    n = _n(2.5)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for r in _HAT_RATIOS:
        x += np.sign(np.sin(2 * np.pi * 180 * r * t + 2 * r))
    x = 0.6 * svf(x, 7000, 0.2, 'bp') + 0.5 * svf(noise(n), 9000, 0.1, 'bp')
    return x * np.exp(-t / 0.7) * vel * 0.3


def chip_noise(vel=1.0, kind='snare'):
    """NES noise channel: LFSR noise (long or short mode) with stepped volume decay."""
    dur = {'kick': 0.09, 'snare': 0.16, 'hat': 0.04}[kind]
    n = _n(dur)
    rate = {'kick': 2000, 'snare': 9000, 'hat': 22000}[kind]
    reg = 1
    per = SR / rate
    out = np.empty(n)
    acc = 0.0
    bit = 1.0
    for i in range(n):
        acc += 1.0
        if acc >= per:
            acc -= per
            fb = (reg & 1) ^ ((reg >> (6 if kind == 'hat' else 1)) & 1)
            reg = (reg >> 1) | (fb << 14)
            bit = 1.0 if reg & 1 else -1.0
        out[i] = bit
    env = np.exp(-np.arange(n) / (SR * dur / 3))
    env = np.round(env * 15) / 15
    if kind == 'kick':
        tt = np.arange(n) / SR
        out = 0.4 * out + np.sign(np.sin(2 * np.pi * np.cumsum(120 * np.exp(-tt / 0.03) + 40) / SR))
    return out * env * vel * 0.35


def riser(dur, vel=1.0, f0=300, f1=9000):
    n = _n(dur)
    t = np.arange(n) / SR
    fc = f0 * (f1 / f0) ** (t / dur)
    x = svf(noise(n), fc, 0.5, 'bp')
    return x * (t / dur) ** 2 * vel * 0.6


def impact(vel=1.0):
    n = _n(3.0)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 60 * np.exp(-t / 0.1)) / SR) * np.exp(-t / 1.2)
    nz = svf(noise(n), 2000, 0.1, 'lp') * np.exp(-t / 0.5)
    return np.tanh(boom + 0.4 * nz) * vel * 0.8
