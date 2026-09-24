"""Syllables + timing + pitch -> control tracks for the formant engine.

The unit of performance is a *syllable event*: onset consonants, a vowel
nucleus and coda consonants, plus the moment the vowel should start (`t_on`,
the beat — sung consonants are placed *before* the beat so the vowel lands on
it), the end of the syllable (`t_off`) and a loudness. Pitch arrives separately
as note segments, so one syllable can carry a melisma.

Coarticulation is modelled the classic way: every phoneme contributes target
values over its span (stops and nasals contribute their formant *loci*), and
the target tracks are smoothed with a place-appropriate time constant, which
produces anticipatory and carry-over transitions between neighbours.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .engine import synth_core
from .phonemes import (CONSONANTS, DIPHTHONGS, LOCI, VOWELS, vowel_formants, velar_locus)

CR = 1000  # control rate (Hz)


@dataclass
class Voice:
    """A voice: vocal-tract, source and singing-style settings."""
    name: str = 'voice'
    sr: int = 48000
    vtl: float = 0.5              # vocal-tract scale: 0 = adult male averages, 1 = adult female, >1 smaller/brighter
    oq: float = 0.62              # glottal open quotient (lower = pressed/buzzier, higher = softer/breathier)
    tilt: float = 0.15            # source low-pass (0 bright ... 0.9 dark)
    breath: float = -30.0         # aspiration during vowels, dB re voicing
    jitter: float = 0.004         # per-cycle F0 randomness (fraction)
    shimmer: float = 0.03         # per-cycle amplitude randomness (fraction)
    vib_rate: float = 5.4         # Hz
    vib_depth: float = 30.0       # cents (peak)
    vib_delay: float = 0.28       # s after the vowel starts
    vib_attack: float = 0.35      # s to reach full depth
    portamento: float = 0.07      # s glide between notes
    overshoot: float = 0.0        # cents of overshoot when arriving on a new pitch
    scoop: float = 25.0           # cents below target at a phrase's first vowel, released over 80 ms
    drift: float = 7.0            # cents of slow random pitch wander
    bw_scale: float = 1.0         # formant bandwidth multiplier
    formant_shift: float = 1.0    # extra multiplier on all formant frequencies
    consonant_rate: float = 1.0   # consonant duration multiplier
    consonant_gain_db: float = 0.0  # extra level on bursts and frication (sung consonants need more)
    f1_tuning: bool = True        # raise F1 to sit above F0 on high notes (what sopranos do)
    smooth_ms: float = 24.0       # coarticulation smoothing for formants
    amp_smooth_ms: float = 3.0    # smoothing for amplitude tracks
    frame_hold_ms: float = 0.0    # >0: hold every control parameter for this long (DECtalk-style steps)
    level_db: float = -3.0        # output peak level
    presence_db: float = 7.0      # high shelf above ~4.5 kHz: the air the resonator cascade rolls off
    air_db: float = -60.0         # breath turbulence above ~4 kHz riding the voicing, dB re peak voice (-60 = off)
    seed: int = 7

    def but(self, **kw):
        return replace(self, **kw)


@dataclass
class Syl:
    onset: list
    vowel: str
    coda: list
    t_on: float
    t_off: float
    vel: float = 1.0
    stress: int = 1
    text: str = ''
    word: str = ''
    word_start: bool = True
    word_end: bool = True
    index: int = 0


def db(x):
    return 10.0 ** (x / 20.0)


def _cons_formants(c, vtl, next_f, prev_f, role='onset'):
    """Formant targets (F1..F3) for consonant c, male base scaled by vtl.

    Context (velar loci, /h/ colouring) comes from the vowel the consonant belongs to:
    the following vowel for onsets, the preceding vowel for codas.
    """
    spec = CONSONANTS[c]
    if role == 'coda':
        next_f, prev_f = prev_f, next_f
    s1, s2, s3 = 1 + 0.10 * vtl, 1 + 0.17 * vtl, 1 + 0.17 * vtl
    if spec.kind in ('stop', 'affricate') or (spec.kind == 'nasal' and spec.formants is None):
        if spec.place == 'velar':
            ref = next_f if next_f is not None else prev_f
            f2, f3 = velar_locus(ref[1] / s2 if ref is not None else 1700.0)
        else:
            f2, f3 = LOCI[spec.place]
        return (250 * s1, f2 * s2, f3 * s3)
    if spec.kind == 'aspirate':
        ref = next_f if next_f is not None else prev_f
        return ref[:3] if ref is not None else (500 * s1, 1500 * s2, 2500 * s3)
    if spec.place == 'velar' and spec.kind == 'nasal':
        ref = next_f if next_f is not None else prev_f
        f2, f3 = velar_locus(ref[1] / s2 if ref is not None else 1700.0)
        return (spec.formants[0] * s1, f2 * s2, f3 * s3)
    f1, f2, f3 = spec.formants
    return (f1 * s1, f2 * s2, f3 * s3)


def plan_segments(syls: list[Syl], voice: Voice):
    """Place every phoneme of every syllable in time. Returns segment dicts in phoneme order.

    Sung consonants live *between* vowels: a syllable's coda and the next syllable's
    onset form one ordered cluster that ends exactly when the next vowel starts
    (the beat). When the cluster would eat the vowel, every consonant in it is
    shortened proportionally, leaving at least 40% of the gap to the vowel. A
    syllable followed by a rest keeps its coda at the end of its own note, and a
    syllable after a rest has its onset placed just before its beat.
    """
    segs = []
    vtl = voice.vtl
    n = len(syls)
    rate = voice.consonant_rate
    odur = [[CONSONANTS[c].dur * rate for c in s.onset] for s in syls]
    cdur = [[CONSONANTS[c].dur * rate * 0.9 for c in s.coda] for s in syls]
    vf = [_vowel_mid_formants(s.vowel, vtl) for s in syls]

    def attached(k):
        """Does syllable k+1 follow syllable k without a rest?"""
        if k + 1 >= n:
            return False
        gap = syls[k + 1].t_on - syls[k].t_off
        return gap <= max(0.05, sum(odur[k + 1]) + 0.02)

    v_start = [s.t_on for s in syls]
    v_end = [s.t_off for s in syls]
    placed_onset = [False] * n
    for k, s in enumerate(syls):
        prev_f = vf[k - 1] if k > 0 else None
        next_f = vf[k + 1] if k + 1 < n else None
        # onset after a rest (or the first syllable)
        if not placed_onset[k] and s.onset:
            d = list(odur[k])
            floor = (syls[k - 1].t_off if k > 0 else -1e9)
            room = s.t_on - max(floor, s.t_on - 0.5)
            if sum(d) > room:
                d = [x * room / sum(d) for x in d]
            t = s.t_on - sum(d)
            for c, x in zip(s.onset, d):
                segs.append(dict(ph=c, t0=t, t1=t + x, syl=k, role='onset', next_f=vf[k], prev_f=prev_f, vel=s.vel))
                t += x
        if attached(k):
            nxt = syls[k + 1]
            clus = [(c, x, 'coda', k) for c, x in zip(s.coda, cdur[k])] + \
                   [(c, x, 'onset', k + 1) for c, x in zip(nxt.onset, odur[k + 1])]
            D = sum(x for _, x, _, _ in clus)
            window = nxt.t_on - s.t_on
            maxD = 0.6 * window
            sc = min(1.0, maxD / D) if D > 0 else 1.0
            t = nxt.t_on - D * sc
            v_end[k] = t
            for c, x, role, kk in clus:
                x *= sc
                if role == 'coda':
                    segs.append(dict(ph=c, t0=t, t1=t + x, syl=kk, role='coda', next_f=vf[k + 1], prev_f=vf[k], vel=s.vel))
                else:
                    segs.append(dict(ph=c, t0=t, t1=t + x, syl=kk, role='onset', next_f=vf[k + 1], prev_f=vf[k], vel=nxt.vel))
                t += x
            placed_onset[k + 1] = True
        else:
            d = list(cdur[k])
            span = s.t_off - s.t_on
            if sum(d) > 0.6 * span:
                d = [x * 0.6 * span / sum(d) for x in d]
            t = s.t_off - sum(d)
            v_end[k] = t
            for c, x in zip(s.coda, d):
                segs.append(dict(ph=c, t0=t, t1=t + x, syl=k, role='coda', next_f=next_f, prev_f=vf[k], vel=s.vel))
                t += x
        segs.append(dict(ph=s.vowel, t0=v_start[k], t1=max(v_start[k] + 0.01, v_end[k]), syl=k, role='vowel',
                         vel=s.vel, stress=s.stress))
    segs.sort(key=lambda g: (g['t0'], 0 if g['role'] == 'coda' else 1))
    for i in range(len(segs) - 1):
        if segs[i]['t1'] > segs[i + 1]['t0']:
            segs[i]['t1'] = max(segs[i]['t0'] + 0.003, segs[i + 1]['t0'])
    return segs


def _vowel_mid_formants(v, vtl):
    if v in DIPHTHONGS:
        a, b, _ = DIPHTHONGS[v]
        fa, fb = vowel_formants(a, vtl), vowel_formants(b, vtl)
        return tuple(0.5 * (x + y) for x, y in zip(fa, fb))
    return vowel_formants(v, vtl)


def build_tracks(segs, voice: Voice, t_end: float, f0_hz: np.ndarray):
    """Target tracks at CR, smoothed. Returns a dict of arrays for synth_core."""
    n = int(math.ceil(t_end * CR)) + 2
    vtl = voice.vtl
    neutral = vowel_formants('AX', vtl)
    F = np.tile(np.array(neutral, dtype=np.float64)[:, None], (1, n))
    B = np.tile(np.array([80, 100, 160, 250, 350, 900], dtype=np.float64)[:, None], (1, n)) * voice.bw_scale
    av = np.zeros(n)
    ah = np.zeros(n)
    af = np.zeros(n)
    fnp = np.full(n, 270.0)
    fnz = np.full(n, 270.0)
    fr_f = np.tile(np.array([2500.0, 4500.0, 7000.0])[:, None], (1, n))
    fr_b = np.tile(np.array([1000.0, 1500.0, 2500.0])[:, None], (1, n))
    fr_g = np.zeros((3, n))
    bursts = []   # (i0, i1, level, spectrum) added after smoothing
    breath = db(voice.breath)
    fs = 1 + 0.12 * vtl   # frication centre scaling
    cg = voice.consonant_gain_db

    def idx(t):
        return int(round(t * CR))

    def set_spec(i0, i1, spec, level_db):
        for k in range(3):
            if k < len(spec):
                c, bw, g = spec[k]
                fr_f[k, i0:i1] = c * fs
                fr_b[k, i0:i1] = bw
                fr_g[k, i0:i1] = db(g)
            else:
                fr_g[k, i0:i1] = 0.0
        af[i0:i1] = db(level_db + cg)

    last_vowel_f = None
    for g in segs:
        i0, i1 = max(0, idx(g['t0'])), min(n, idx(g['t1']))
        if i1 <= i0:
            continue
        ph = g['ph']
        vel = g.get('vel', 1.0)
        if ph in VOWELS:
            if ph in DIPHTHONGS:
                a, b, frac = DIPHTHONGS[ph]
                fa, fb = np.array(vowel_formants(a, vtl)), np.array(vowel_formants(b, vtl))
                L = i1 - i0
                x = np.linspace(0, 1, L)
                w = np.clip((x - frac) / max(1e-3, 1 - frac), 0, 1)
                w = 0.5 - 0.5 * np.cos(np.pi * w)
                F[:, i0:i1] = fa[:, None] * (1 - w) + fb[:, None] * w
                last_vowel_f = tuple(fb)
            else:
                ff = np.array(vowel_formants(ph, vtl))
                F[:, i0:i1] = ff[:, None]
                last_vowel_f = tuple(ff)
            av[i0:i1] = vel
            ah[i0:i1] = breath * vel
            if ph == 'NM':                      # humming: lips closed, sound through the nose
                fnp[i0:i1] = 260.0
                fnz[i0:i1] = 950.0 * (1 + 0.12 * vtl)
                B[0:3, i0:i1] *= 1.6
                av[i0:i1] = vel * db(-3.0)
                ah[i0:i1] = 0.0
            continue
        spec = CONSONANTS[ph]
        f3 = _cons_formants(ph, vtl, g.get('next_f'), g.get('prev_f'), g.get('role', 'onset'))
        F[0, i0:i1], F[1, i0:i1], F[2, i0:i1] = f3
        if spec.kind == 'stop':
            dur = i1 - i0
            vot = spec.vot * voice.consonant_rate if g['role'] == 'onset' else 0.0
            n_vot = min(int(vot * CR), int(dur * 0.6))
            n_cl = max(1, dur - n_vot)
            ir = i0 + n_cl                     # release
            av[i0:ir] = db(spec.av_level) * vel if spec.voiced else 0.0
            if spec.voiced:
                F[0, i0:ir] = 200 * (1 + 0.1 * vtl)
            lvl = spec.burst_level - (3.0 if g['role'] == 'coda' else 0.0)
            bspec = spec.burst
            if spec.place == 'velar':
                c2 = f3[1] / fs
                bspec = [(c2, 500.0, 0.0), (f3[2] / fs, 900.0, -6.0)]
            bursts.append((ir, min(n, ir + 7), lvl, bspec))
            if n_vot > 0:
                ah[ir:i1] = db(-17.0) * vel
                # during aspiration formants head to the vowel: leave F at locus, smoothing moves them
            if spec.voiced:
                av[ir:i1] = vel * 0.8
        elif spec.kind == 'affricate':
            dur = i1 - i0
            n_cl = int(dur * 0.3)
            ir = i0 + n_cl
            av[i0:ir] = db(spec.av_level) * vel if spec.voiced else 0.0
            bursts.append((ir, min(n, ir + 5), spec.burst_level, spec.burst))
            set_spec(ir, i1, spec.fric, spec.fric_level)
            af[ir:i1] *= vel
            av[ir:i1] = db(spec.av_level) * vel if spec.voiced else 0.0
        elif spec.kind == 'fricative':
            set_spec(i0, i1, spec.fric, spec.fric_level)
            af[i0:i1] *= vel
            av[i0:i1] = db(spec.av_level) * vel if spec.voiced else 0.0
        elif spec.kind == 'aspirate':
            ah[i0:i1] = db(-5.0) * vel
            av[i0:i1] = 0.0
        elif spec.kind == 'nasal':
            av[i0:i1] = db(spec.av_level) * vel
            fnp[i0:i1] = spec.nasal[0]
            fnz[i0:i1] = spec.nasal[1] * (1 + 0.12 * vtl)
            B[0:3, i0:i1] *= 1.6
        else:  # liquid / glide
            av[i0:i1] = db(spec.av_level) * vel
            ah[i0:i1] = breath * vel * 0.5

    # --- smoothing (coarticulation) ---------------------------------------
    sig = voice.smooth_ms / 2.0 * CR / 1000.0
    sig_a = voice.amp_smooth_ms * CR / 1000.0
    if voice.frame_hold_ms <= 0:
        F = np.exp(gaussian_filter1d(np.log(F), sig, axis=1, mode='nearest'))
        B = gaussian_filter1d(B, sig * 0.5, axis=1, mode='nearest')
        av = gaussian_filter1d(av, sig_a, mode='nearest')
        ah = gaussian_filter1d(ah, sig_a, mode='nearest')
        af = gaussian_filter1d(af, sig_a * 2.5, mode='nearest')
        fnp = gaussian_filter1d(fnp, sig * 0.4, mode='nearest')
        fnz = gaussian_filter1d(fnz, sig * 0.4, mode='nearest')
        fr_f = gaussian_filter1d(fr_f, sig_a, axis=1, mode='nearest')
        fr_g = gaussian_filter1d(fr_g, sig_a, axis=1, mode='nearest')
    # bursts: short sharp noise events on their own spectrum
    for (i0, i1, lvl, spec) in bursts:
        if i1 <= i0:
            continue
        for k in range(3):
            if k < len(spec):
                c, bw, g = spec[k]
                fr_f[k, i0:i1] = c * fs
                fr_b[k, i0:i1] = bw
                fr_g[k, i0:i1] = db(g)
            else:
                fr_g[k, i0:i1] = 0.0
        env = np.exp(-np.arange(i1 - i0) / 2.5)
        af[i0:i1] = np.maximum(af[i0:i1], db(lvl + cg) * env)

    # --- singing: F1 tracks above F0 on high notes -------------------------
    f0 = f0_hz[:n] if len(f0_hz) >= n else np.pad(f0_hz, (0, n - len(f0_hz)), mode='edge')
    if voice.f1_tuning:
        lift = np.maximum(F[0], np.minimum(f0 * 1.08, 1100.0))
        F[0] = np.where(av > 0.05, lift, F[0])
    F = F * voice.formant_shift

    if voice.frame_hold_ms > 0:
        h = max(1, int(voice.frame_hold_ms * CR / 1000.0))
        def hold(a):
            a = np.array(a, copy=True)
            if a.ndim == 1:
                for s in range(0, a.shape[0], h):
                    a[s:s + h] = a[s]
            else:
                for s in range(0, a.shape[1], h):
                    a[:, s:s + h] = a[:, s:s + 1]
            return a
        F, B, av, ah, af, fnp, fnz, fr_f, fr_b, fr_g = map(hold, (F, B, av, ah, af, fnp, fnz, fr_f, fr_b, fr_g))
    return dict(F=F, B=B, av=av, ah=ah, af=af, fnp=fnp, fnz=fnz, fr_f=fr_f, fr_b=fr_b, fr_g=fr_g, f0=f0)


def midi_to_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def sung_f0(notes, voice: Voice, t_end: float, rng=None):
    """F0 track (Hz) at CR from note segments [(t_on, t_off, midi)], with portamento,
    vibrato, overshoot, scoop and drift."""
    rng = rng or np.random.default_rng(voice.seed)
    n = int(math.ceil(t_end * CR)) + 2
    t = np.arange(n) / CR
    notes = sorted(notes, key=lambda x: x[0])
    midi = np.full(n, float(notes[0][2]) if notes else 60.0)
    # piecewise constant with raised-cosine glides centred on each boundary
    cur = float(notes[0][2])
    midi[:] = cur
    for k, (a, b, m) in enumerate(notes):
        i0 = int(a * CR)
        midi[i0:] = m
    # glides
    out = midi.copy()
    P = max(1, int(voice.portamento * CR))
    for k in range(1, len(notes)):
        a_prev, b_prev, m_prev = notes[k - 1]
        a, b, m = notes[k]
        if a - b_prev > 0.15 or m == m_prev:
            continue
        c = int(a * CR)
        s0, s1 = max(0, c - P // 2), min(n, c + P // 2)
        if s1 <= s0:
            continue
        x = np.linspace(0, 1, s1 - s0)
        w = 0.5 - 0.5 * np.cos(np.pi * x)
        out[s0:s1] = m_prev + (m - m_prev) * w
        if voice.overshoot > 0 and abs(m - m_prev) >= 1:
            L = int(0.25 * CR)
            e = np.exp(-np.arange(L) / (0.07 * CR)) * np.sin(np.arange(L) / (0.07 * CR) * 1.6)
            seg = out[s1:s1 + L]
            out[s1:s1 + len(seg)] += np.sign(m - m_prev) * voice.overshoot / 100.0 * e[:len(seg)]
    cents = np.zeros(n)
    # vibrato: continuous oscillator, per-note onset envelope
    rate = voice.vib_rate * (1 + 0.04 * np.sin(2 * np.pi * 0.37 * t + rng.uniform(0, 6)))
    ph = np.cumsum(2 * np.pi * rate / CR)
    env = np.zeros(n)
    for (a, b, m) in notes:
        i0, i1 = int(a * CR), int(b * CR)
        tt = t[i0:i1] - a
        e = np.clip((tt - voice.vib_delay) / max(1e-3, voice.vib_attack), 0, 1)
        env[i0:i1] = np.maximum(env[i0:i1], e * e * (3 - 2 * e))
    cents += voice.vib_depth * env * np.sin(ph)
    # scoop at phrase starts
    if voice.scoop > 0:
        for k, (a, b, m) in enumerate(notes):
            if k == 0 or a - notes[k - 1][1] > 0.15:
                i0 = int(a * CR)
                L = min(int(0.12 * CR), n - i0)
                cents[i0:i0 + L] -= voice.scoop * np.exp(-np.arange(L) / (0.04 * CR))
    # drift: smooth random wander
    if voice.drift > 0:
        w = rng.standard_normal(n // 50 + 4)
        wd = np.interp(np.arange(n) / 50.0, np.arange(len(w)), w)
        wd = gaussian_filter1d(wd, 60)
        wd = wd / (np.std(wd) + 1e-9)
        cents += voice.drift * wd
    return midi_to_hz(out + cents / 100.0)


def render_syllables(syls: list[Syl], notes, voice: Voice, t_end: float | None = None, f0_hz=None):
    """Synthesize. `notes` = [(t_on, t_off, midi)] for the F0 line (or pass f0_hz directly)."""
    if t_end is None:
        t_end = max(s.t_off for s in syls) + 0.3
    if f0_hz is None:
        f0_hz = sung_f0(notes, voice, t_end)
    segs = plan_segments(syls, voice)
    tr = build_tracks(segs, voice, t_end, f0_hz)
    n_out = int(t_end * voice.sr)
    tilt = np.full_like(tr['av'], voice.tilt)
    oq = np.full_like(tr['av'], voice.oq)
    y = synth_core(float(voice.sr), float(CR), n_out, tr['f0'], tr['av'], tr['ah'], tr['af'], oq, tilt,
                   tr['F'], tr['B'], tr['fnp'], tr['fnz'], tr['fr_f'], tr['fr_b'], tr['fr_g'],
                   float(voice.jitter), float(voice.shimmer), int(voice.seed), 8)
    if voice.presence_db:
        y = high_shelf(y, voice.sr, 4500.0, voice.presence_db)
    if voice.air_db > -59 and voice.sr >= 20000:
        # glottal turbulence: real voices keep energy at 5-10 kHz that a resonator cascade cannot reach
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(voice.seed + 17)
        nz = rng.standard_normal(len(y))
        nz = sosfilt(butter(4, [4000.0 / (voice.sr / 2), min(0.95, 11000.0 / (voice.sr / 2))], btype='band',
                            output='sos'), nz)
        env = np.interp(np.arange(len(y)) / voice.sr, np.arange(len(tr['av'])) / CR, tr['av'] + 0.3 * tr['ah'] / max(1e-6, db(voice.breath)) * db(voice.breath))
        nz = nz / (np.sqrt(np.mean(nz ** 2)) + 1e-12)
        y = y + nz * env * np.sqrt(np.mean(y ** 2)) * db(voice.air_db + 20.0)
    peak = np.max(np.abs(y)) + 1e-12
    y = y / peak * db(voice.level_db)
    return y, segs, tr


def high_shelf(y, sr, fc, gain_db, q=0.7):
    """RBJ high-shelf biquad."""
    from scipy.signal import lfilter
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * fc / sr
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    b0 = A * ((A + 1) + (A - 1) * cw + 2 * math.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cw)
    b2 = A * ((A + 1) + (A - 1) * cw - 2 * math.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * cw + 2 * math.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * cw)
    a2 = (A + 1) - (A - 1) * cw - 2 * math.sqrt(A) * alpha
    return lfilter([b0 / a0, b1 / a0, b2 / a0], [1, a1 / a0, a2 / a0], y)
