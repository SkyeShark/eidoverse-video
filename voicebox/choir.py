"""A choir of formant voices: chord progressions voiced across many singers.

    from voicebox.choir import choir
    stereo = choir([(0.0, 4.0, ['E3','B3','G#4']), (4.0, 8.0, ['C#3','C#4','E4'])],
                   vowel='NM', per_note=3)          # humming
    stereo = choir(chords, vowel='AA', per_note=4)  # 'aah'

Each chord tone gets `per_note` singers. Every singer has their own vocal-tract
scale, seed (so jitter/vibrato/drift differ), a few cents of detune, tens of
milliseconds of timing drift and a stereo position — the small disagreements
that make a group of voices sound like a group. Returns (2, n) at 48 kHz.
"""
from __future__ import annotations

import numpy as np

from .articulate import Syl, Voice, render_syllables
from .score import note_midi

SR = 48000


def choir(chords, vowel='AA', per_note=3, vtl_range=(0.25, 0.95), detune_cents=9.0, timing_ms=30.0,
          breath=-24.0, vib_depth=22.0, vel=0.8, onset=(), coda=(), t_end=None, seed=100, width=0.9,
          base_voice: Voice | None = None):
    """chords: [(t0, t1, [pitches...])] — pitches as note names or midi. All chords must have
    the same number of tones (voice k sings tone k of every chord: simple voice leading)."""
    rng = np.random.default_rng(seed)
    k_tones = len(chords[0][2])
    t_end = t_end or (max(c[1] for c in chords) + 1.5)
    n = int(t_end * SR)
    out = np.zeros((2, n))
    base = base_voice or Voice(breath=breath, oq=0.66, tilt=0.18, vib_depth=vib_depth, vib_delay=0.4,
                               vib_attack=0.6, portamento=0.12, scoop=0.0, drift=9.0, presence_db=4.0,
                               air_db=-36.0, consonant_gain_db=0.0)
    singers = []
    for k in range(k_tones):
        for j in range(per_note):
            singers.append((k, j))
    for idx, (k, j) in enumerate(singers):
        vtl = rng.uniform(*vtl_range)
        det = rng.uniform(-detune_cents, detune_cents)
        dt = rng.uniform(-timing_ms, timing_ms) / 1000.0
        v = base.but(vtl=vtl, seed=int(seed + idx * 7), vib_rate=float(rng.uniform(4.8, 5.9)))
        syls, notes = [], []
        for ci, (t0, t1, tones) in enumerate(chords):
            m = note_midi(tones[k]) + det / 100.0
            a = max(0.02, t0 + dt + (0.08 if ci == 0 else 0.0))
            b = t1 + dt
            syls.append(Syl(onset=list(onset) if ci == 0 else [], vowel=vowel,
                            coda=list(coda) if ci == len(chords) - 1 else [], t_on=a, t_off=b, vel=vel,
                            index=ci))
            notes.append((a, b, m))
        y, _, _ = render_syllables(syls, notes, v, t_end=t_end)
        y = y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)))
        pan = (idx / max(1, len(singers) - 1) * 2 - 1) * width
        pan += rng.uniform(-0.1, 0.1)
        th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        out[0] += y * np.cos(th)
        out[1] += y * np.sin(th)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.7
