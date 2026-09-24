"""Era voices: the sound of machine speech through its history.

Each renderer takes a `Sung` score (or pre-rendered formant tracks) and returns
48 kHz mono audio in the character of a historical technology. These are
*evocations built from the published principles* of each system, not
bit-exact emulations of the original hardware or software:

    voder_1939      ten-band filterbank "played" with buzz/hiss sources (Dudley's Voder)
    bell_labs_1961  Kelly–Lochbaum tube model (20 sections, fitted to Peterson & Barney), 10 kHz, onto tape
                    (Bell Labs "Daisy Bell"; lives in voicebox/tube.py)
    speakspell_1978 real LPC-10 analysis/resynthesis at 8 kHz, quantised coefficients, chirp excitation
    sam_1982        phase-reset sine-wave formants, 4-bit output (Software Automatic Mouth)
    dectalk_1984    Klatt cascade synthesis at 10 kHz with stepped parameter frames ("Perfect Paul")
    vocaloid_2007   bright, small vocal tract, tight pitch with stylised vibrato and overshoot
    handmade        the full-quality formant voice

All renderers take the same `Sung` object, so one score can be sung by every era.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit
from scipy.signal import butter, lfilter, resample_poly, sosfilt

from .articulate import CR, Voice, build_tracks, plan_segments, render_syllables, sung_f0
from .engine import synth_core

SR = 48000


# --- generic helpers --------------------------------------------------------------
def _norm(y, peak_db=-3.0):
    # Sub-sonic blocker first: PSOLA resynthesis (sapi/neural) overlap-adds grains with a small
    # non-zero mean, which builds a DC pedestal that switches with each note; SAM's 4-bit sines
    # sit off-centre. Inaudible, but it eats a mix's limiter headroom. 35 Hz clears the lowest
    # sung bass (E2 = 82 Hz) with room to spare.
    y = highpass(y, SR, 35.0, order=4)
    return y / (np.max(np.abs(y)) + 1e-12) * 10 ** (peak_db / 20)


def zoh_upsample(y, sr_in, sr_out=SR):
    """Zero-order-hold resampling: keeps the spectral images old DACs produced."""
    n_out = int(len(y) * sr_out / sr_in)
    idx = np.minimum((np.arange(n_out) * sr_in / sr_out).astype(np.int64), len(y) - 1)
    return y[idx]


def quantize(y, bits):
    q = 2 ** (bits - 1)
    return np.round(np.clip(y, -1, 1) * (q - 1)) / (q - 1)


def band(y, sr, lo, hi, order=4):
    sos = butter(order, [lo / (sr / 2), min(0.999, hi / (sr / 2))], btype='band', output='sos')
    return sosfilt(sos, y)


def lowpass(y, sr, fc, order=4):
    sos = butter(order, min(0.999, fc / (sr / 2)), btype='low', output='sos')
    return sosfilt(sos, y)


def highpass(y, sr, fc, order=2):
    sos = butter(order, fc / (sr / 2), btype='high', output='sos')
    return sosfilt(sos, y)


def tape(y, sr, wow=0.0025, flutter=0.0008, hiss_db=-52, lp=5500, seed=3):
    """Tape playback: wow/flutter as a time-varying delay, hiss, head-bump low-pass."""
    rng = np.random.default_rng(seed)
    n = len(y)
    t = np.arange(n) / sr
    dev = wow * np.sin(2 * np.pi * 0.55 * t + 1.3) + flutter * np.sin(2 * np.pi * 7.1 * t)
    pos = np.arange(n) + np.cumsum(dev)
    pos = np.clip(pos, 0, n - 1)
    y2 = np.interp(pos, np.arange(n), y)
    y2 = lowpass(y2, sr, lp, 2)
    y2 = y2 + rng.standard_normal(n) * 10 ** (hiss_db / 20) * np.max(np.abs(y2))
    return y2


def crackle(n, sr, density=6.0, level=0.25, seed=5):
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    k = rng.poisson(density * n / sr)
    pos = rng.integers(0, n, k)
    out[pos] = rng.uniform(-1, 1, k) * level
    return lowpass(out, sr, 3000, 2)


def small_room(y, sr, mix=0.12, size=0.3):
    from pedalboard import Pedalboard, Reverb
    pb = Pedalboard([Reverb(room_size=size, damping=0.6, wet_level=mix, dry_level=1.0 - mix * 0.5, width=0.0)])
    return pb(y.astype(np.float32)[None, :], sr)[0].astype(np.float64)


# --- the formant voice at an arbitrary sample rate --------------------------------
def _render_at(sung, voice: Voice, sr, t_end=None):
    v = voice.but(sr=sr, presence_db=0.0)
    y, segs, tr = sung.render(v, t_end=t_end)
    return y, segs, tr


def handmade(sung, voice: Voice | None = None, t_end=None):
    voice = voice or Voice(name='handmade', vtl=0.6, breath=-28, oq=0.62, tilt=0.1, vib_rate=5.3,
                           vib_depth=28, portamento=0.06, scoop=20, drift=6, presence_db=9, consonant_gain_db=4,
                           air_db=-38)
    y, segs, tr = sung.render(voice, t_end=t_end)
    return _norm(y), segs, tr


def dectalk_1984(sung, t_end=None):
    """Klatt's DECtalk, 'Perfect Paul': male cascade voice, stepped 6.4 ms frames, 10 kHz."""
    v = Voice(name='dectalk', vtl=0.0, oq=0.5, tilt=0.15, breath=-44, jitter=0.0, shimmer=0.0,
              vib_depth=0.0, portamento=0.02, scoop=0.0, drift=0.0, bw_scale=1.15, f1_tuning=False,
              smooth_ms=16.0, frame_hold_ms=6.4, formant_shift=0.97)
    y, segs, tr = _render_at(sung, v, 10000, t_end)
    y = quantize(_norm(y, -1), 12)
    y = resample_poly(y, 24, 5)            # proper reconstruction filter: DECtalk sounded clean, just synthetic
    y = band(y, SR, 90, 4800, 4)
    return _norm(y), segs, tr


def vocaloid_2007(sung, t_end=None, vtl=1.15):
    """Bright, small vocal tract; exact pitch with stylised vibrato, overshoot and quick portamento."""
    v = Voice(name='vocaloid', vtl=vtl, oq=0.55, tilt=0.08, breath=-26, jitter=0.0015, shimmer=0.012,
              vib_rate=6.1, vib_depth=45, vib_delay=0.16, vib_attack=0.2, portamento=0.045, overshoot=35,
              scoop=35, drift=2.5, presence_db=10, consonant_rate=0.85, smooth_ms=18.0, consonant_gain_db=3)
    y, segs, tr = sung.render(v, t_end=t_end)
    y = small_room(y, SR, mix=0.1, size=0.2)
    return _norm(y), segs, tr


# --- LPC-10 (Speak & Spell) ------------------------------------------------------------
def _levinson(r, p):
    a = np.zeros(p + 1)
    a[0] = 1.0
    e = r[0] + 1e-9
    ks = np.zeros(p)
    for i in range(1, p + 1):
        acc = r[i] + np.dot(a[1:i], r[i - 1:0:-1])
        k = -acc / e
        a_new = a.copy()
        a_new[1:i] = a[1:i] + k * a[i - 1:0:-1]
        a_new[i] = k
        a = a_new
        ks[i - 1] = k
        e *= (1 - k * k)
        if e <= 0:
            break
    return a, ks, e


def _step_up(ks):
    a = np.array([1.0])
    for k in ks:
        a = np.concatenate([a, [0.0]]) + k * np.concatenate([a, [0.0]])[::-1]
    return a


# bit allocation of the TMS5100's reflection coefficients (K1..K10)
_KBITS = [5, 5, 4, 4, 4, 4, 4, 3, 3, 3]


def _chirp(n=48, sr=8000):
    t = np.arange(n) / sr
    f = 2600 * np.exp(-t / 0.0025) + 450
    ph = 2 * np.pi * np.cumsum(f) / sr
    return np.sin(ph) * np.exp(-t / 0.0022)


def speakspell_1978(sung, t_end=None):
    """Texas Instruments Speak & Spell style: LPC-10 at 8 kHz with 25 ms frames,
    coarsely quantised reflection coefficients and energy, and a chirp-shaped
    voiced excitation, played through a small speaker."""
    base = Voice(name='ss_base', vtl=0.05, oq=0.55, tilt=0.12, breath=-40, jitter=0.0, shimmer=0.0,
                 vib_depth=0.0, scoop=0.0, drift=0.0, portamento=0.03, f1_tuning=False)
    y, segs, tr = _render_at(sung, base, 8000, t_end)
    y = _norm(y, -1)
    sr = 8000
    fl = 200                       # 25 ms
    p = 10
    nfr = len(y) // fl
    win = np.hamming(fl * 2)
    ypad = np.concatenate([np.zeros(fl // 2), y, np.zeros(fl * 2)])
    f0 = tr['f0']
    av = tr['av']
    chirp = _chirp()
    rng = np.random.default_rng(11)
    # pass 1: analyse every frame -> quantised reflection coefficients, energy, pitch, voicing
    frames = []
    for i in range(nfr):
        seg = ypad[i * fl: i * fl + fl * 2] * win
        r = np.correlate(seg, seg, 'full')[len(seg) - 1: len(seg) + p]
        ci = min(len(av) - 1, int((i + 0.5) * fl / sr * CR))
        if r[0] < 1e-8:
            frames.append((np.zeros(p), 0.0, 100.0, False))
            continue
        a, ks, err = _levinson(r, p)
        kq = []
        for k, bits in zip(ks, _KBITS):
            k = float(np.clip(k, -0.995, 0.995))
            levels = 2 ** bits
            u = (np.arcsin(k) / (np.pi / 2) + 1) / 2
            u = np.round(u * (levels - 1)) / (levels - 1)
            kq.append(np.sin((u * 2 - 1) * np.pi / 2) * 0.998)
        gain = math.sqrt(max(err, 1e-12) / fl)
        lg = np.clip(np.round((20 * np.log10(gain + 1e-9) + 60) / 4), 0, 15)
        frames.append((np.array(kq), 10 ** ((lg * 4 - 60) / 20), float(np.round(sr / max(50.0, f0[ci]))), av[ci] > 0.25))
    # pass 2: synthesise with the chip's 8 interpolation steps per frame (lattice-equivalent direct form)
    sub = fl // 8
    out = np.zeros(nfr * fl + fl)
    zi = np.zeros(p)
    phase_pos = 0.0
    for i in range(nfr):
        k0, g0, per0, v0 = frames[i]
        k1, g1, per1, v1 = frames[i + 1] if i + 1 < nfr else frames[i]
        for j in range(8):
            w = j / 8.0
            kk = k0 * (1 - w) + k1 * w if v0 == v1 else k0
            gg = g0 * (1 - w) + g1 * w
            per = per0 if v0 else per1
            aq = _step_up(kk)
            exc = np.zeros(sub)
            if v0:
                while phase_pos < sub:
                    s0 = int(phase_pos)
                    L = min(len(chirp), sub - s0)
                    exc[s0:s0 + L] += chirp[:L]
                    phase_pos += per
                phase_pos -= sub
                exc *= 3.2
            else:
                exc = np.sign(rng.standard_normal(sub)) * 0.5
                phase_pos = 0.0
            yy, zi = lfilter([gg], aq, exc, zi=zi)
            out[i * fl + j * sub: i * fl + (j + 1) * sub] = yy
    out = np.clip(_norm(out, -1), -1, 1)
    out = quantize(out, 8)
    out = zoh_upsample(out, sr)
    out = band(out, SR, 280, 5200, 2)               # tiny speaker, no reconstruction filter to speak of
    return _norm(out), segs, tr


# --- SAM (1982) ------------------------------------------------------------------------
@njit(cache=True)
def _sam_core(sr, cr, n_out, f0, av, F1, F2, F3, nz):
    out = np.zeros(n_out)
    ph1 = 0.0
    ph2 = 0.0
    ph3 = 0.0
    tpos = 0.0
    period = sr / 110.0
    for n in range(n_out):
        i = int(n * cr / sr)
        if i >= f0.shape[0]:
            i = f0.shape[0] - 1
        f = f0[i]
        a = av[i]
        tpos += 1.0
        if tpos >= period:
            tpos -= period
            period = sr / max(40.0, f)
            ph1 = 0.0
            ph2 = 0.0
            ph3 = 0.0
        # formant oscillators restart at every glottal pulse and are silenced for the last part of the period
        gate = 1.0 if tpos < 0.72 * period else 0.0
        ph1 += 2 * math.pi * F1[i] / sr
        ph2 += 2 * math.pi * F2[i] / sr
        ph3 += 2 * math.pi * F3[i] / sr
        s3 = 1.0 if math.sin(ph3) >= 0 else -1.0
        v = (math.sin(ph1) * 1.0 + math.sin(ph2) * 0.55 + s3 * 0.22) * gate * a
        out[n] = v / 1.8 + nz[n]
    return out


def sam_1982(sung, t_end=None):
    """Software Automatic Mouth style: three formant oscillators (two sines and a square)
    reset at each glottal pulse, noise-table consonants, 4-bit output at ~22 kHz."""
    base = Voice(name='sam_base', vtl=0.1, oq=0.5, tilt=0.1, breath=-60, jitter=0.0, shimmer=0.0,
                 vib_depth=0.0, scoop=0.0, drift=0.0, portamento=0.02, f1_tuning=False, frame_hold_ms=8)
    sr = 22050
    v = base.but(sr=sr, presence_db=0.0)
    segs = plan_segments(sung.syls, v)
    t_end = t_end or (max(s.t_off for s in sung.syls) + 0.3)
    f0 = sung_f0(sung.notes, v, t_end)
    tr = build_tracks(segs, v, t_end, f0)
    n_out = int(t_end * sr)
    # consonant noise: the formant engine with voicing and aspiration off, frication only
    zero = np.zeros_like(tr['av'])
    nz = synth_core(float(sr), float(CR), n_out, tr['f0'], zero, zero, tr['af'], np.full_like(zero, 0.5),
                    np.full_like(zero, 0.1), tr['F'], tr['B'], tr['fnp'], tr['fnp'], tr['fr_f'], tr['fr_b'],
                    tr['fr_g'], 0.0, 0.0, 99, 8)
    nz = nz / (np.max(np.abs(nz)) + 1e-9) * 0.35
    y = _sam_core(float(sr), float(CR), n_out, tr['f0'], np.minimum(1.0, tr['av'] * 1.2), tr['F'][0], tr['F'][1],
                  tr['F'][2], nz)
    y = quantize(_norm(y, -0.5), 4)
    y = zoh_upsample(y, sr)
    y = lowpass(y, SR, 9000, 2)
    return _norm(y), segs, tr


# --- the Voder (1939) ------------------------------------------------------------------------
_VODER_BANDS = [(0, 225), (225, 450), (450, 700), (700, 1000), (1000, 1400), (1400, 2000),
                (2000, 2700), (2700, 3800), (3800, 5400), (5400, 7500)]


def _tract_gain(F, B, f):
    """Magnitude of a cascade of resonators (unity DC gain each) at frequency f."""
    g = np.ones(F.shape[1])
    for k in range(F.shape[0]):
        Fk, Bk = F[k], B[k]
        num = Fk ** 2 + (Bk / 2) ** 2
        den = np.sqrt(((Fk - f) ** 2 + (Bk / 2) ** 2) * ((Fk + f) ** 2 + (Bk / 2) ** 2))
        g *= num / den
    return g


def voder_1939(sung, t_end=None, seed=4):
    """Homer Dudley's Voder: an operator plays ten band-pass filters with a buzz (wrist bar)
    and a hiss key, and bends the pitch with a foot pedal. Heard over a 1939 PA system."""
    v = Voice(name='voder', vtl=0.2, portamento=0.12, vib_depth=0.0, scoop=60.0, drift=40.0, f1_tuning=False,
              smooth_ms=40.0)
    segs = plan_segments(sung.syls, v)
    t_end = t_end or (max(s.t_off for s in sung.syls) + 0.3)
    f0 = sung_f0(sung.notes, v, t_end, rng=np.random.default_rng(seed))
    tr = build_tracks(segs, v, t_end, f0)
    n = int(t_end * SR)
    tt = np.arange(n) / SR
    ctl_t = np.arange(tr['av'].shape[0]) / CR
    f0s = np.interp(tt, ctl_t, tr['f0'])
    # relaxation-oscillator buzz (a sawtooth) and hiss
    ph = np.cumsum(f0s / SR) % 1.0
    buzz = 2 * ph - 1
    rng = np.random.default_rng(seed)
    hiss = rng.standard_normal(n) * 0.5
    avs = np.interp(tt, ctl_t, np.clip(tr['av'] * 1.0 + tr['ah'] * 2, 0, 1.2))
    afs = np.interp(tt, ctl_t, np.clip(tr['af'] * 3, 0, 1.0))
    out = np.zeros(n)
    for (lo, hi) in _VODER_BANDS:
        fc = math.sqrt(max(lo, 60) * hi)
        gctl = _tract_gain(tr['F'][:5], tr['B'][:5] * 1.6, fc)
        gctl = np.clip(gctl, 0, 30) ** 0.6       # the operator's keys: coarse, compressed
        g = np.interp(tt, ctl_t, gctl)
        # fricatives: open the upper keys
        fr_g = np.interp(tt, ctl_t, np.clip(np.max(tr['fr_g'], axis=0) * (fc / 4000.0), 0, 1.5))
        bsrc = band(buzz, SR, max(40, lo), hi, 2) * g * avs + band(hiss, SR, max(40, lo), hi, 2) * fr_g * afs * 2.0
        out += bsrc
    out = band(out, SR, 180, 3600, 3)          # 1939 PA / broadcast bandwidth
    out = tape(out, SR, wow=0.004, flutter=0.0015, hiss_db=-40, lp=3400, seed=seed)
    out += crackle(n, SR, density=4.0, level=0.15, seed=seed) * np.max(np.abs(out))
    out = small_room(out, SR, mix=0.25, size=0.6)   # the Hall of Science
    return _norm(out), segs, tr


def sapi_2001(sung, t_end=None, voice='Microsoft David Desktop'):
    """Early-2000s desktop TTS, singing one word at a time (the concatenative era's
    'text-to-speech sings' sound): Windows SAPI voice, re-pitched and re-timed with PSOLA."""
    from .resing import sing_with_tts
    y = sing_with_tts(sung, engine='sapi', voice=voice, per_word=True, vib_depth=0.0)
    return _norm(y), None, None


def neural_2023(sung, t_end=None, voice='en-US-JennyNeural', vib_depth=30.0):
    """A neural TTS voice (Microsoft's, via edge-tts) singing through PSOLA re-pitching."""
    from .resing import sing_with_tts
    y = sing_with_tts(sung, engine='edge', voice=voice, vib_depth=vib_depth)
    return _norm(y), None, None


from .tube import bell_labs_1961  # noqa: E402  (the 1961 voice: a physical vocal-tract model)

ERAS = {
    'voder_1939': voder_1939, 'bell_labs_1961': bell_labs_1961, 'speakspell_1978': speakspell_1978,
    'sam_1982': sam_1982, 'dectalk_1984': dectalk_1984, 'sapi_2001': sapi_2001, 'vocaloid_2007': vocaloid_2007,
    'neural_2023': neural_2023, 'handmade': handmade,
}
