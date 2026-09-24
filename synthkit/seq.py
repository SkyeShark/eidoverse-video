"""Sequencer, mixer and master bus.

    from synthkit import Song, inst
    song = Song(bpm=128, bars=16)
    lead = song.track('lead', inst.pluck, gain_db=-6, pan=0.1, reverb=0.25, delay=0.15)
    lead.note('E5', beat=0, beats=0.5, vel=0.9)
    drums = song.track('kick', inst.kick909, drum=True, sidechain_source=True)
    drums.pattern('x...x...x...x...', bar=0, bars=4)
    stereo = song.render()          # (2, n) float
    stereo = master(stereo, lufs=-14.0)

Times are in beats from the song start (`Song.beat_to_s` handles tempo); a
section with its own tempo is simply another Song rendered and placed with
`place()`. Sidechain: tracks with `duck=True` are gain-ducked by every hit of a
track created with `sidechain_source=True`.
"""
from __future__ import annotations

import re

import numpy as np
from numba import njit

from .dsp import SR, db, midi_hz, pan_stereo

_NOTE = re.compile(r'^([A-Ga-g])([#b]?)(-?\d)$')
_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def nm(n):
    """'C4' -> 60; ints pass through."""
    if isinstance(n, (int, float, np.integer, np.floating)):
        return float(n)
    m = _NOTE.match(n.strip())
    if not m:
        raise ValueError(f'bad note {n!r}')
    return 12 * (int(m.group(3)) + 1) + _PC[m.group(1).upper()] + {'#': 1, 'b': -1, '': 0}[m.group(2)]


CHORD_Q = {
    '': [0, 4, 7], 'm': [0, 3, 7], '7': [0, 4, 7, 10], 'maj7': [0, 4, 7, 11], 'm7': [0, 3, 7, 10],
    'sus2': [0, 2, 7], 'sus4': [0, 5, 7], 'add9': [0, 4, 7, 14], 'madd9': [0, 3, 7, 14], 'dim': [0, 3, 6],
    '6': [0, 4, 7, 9], 'm9': [0, 3, 7, 10, 14], 'maj9': [0, 4, 7, 11, 14], '5': [0, 7],
}


def chord(name, octave=4, inversion=0):
    """'F#m7' -> midi notes rooted in `octave`."""
    m = re.match(r'^([A-G][#b]?)(.*)$', name)
    root = nm(m.group(1) + str(octave))
    notes = [root + i for i in CHORD_Q[m.group(2)]]
    for _ in range(inversion):
        notes = notes[1:] + [notes[0] + 12]
    return notes


class Track:
    def __init__(self, song, name, instrument, gain_db=0.0, pan=0.0, reverb=0.0, delay=0.0, drum=False,
                 duck=False, sidechain_source=False, fx=None, params=None):
        self.song, self.name, self.inst = song, name, instrument
        self.gain = db(gain_db)
        self.pan, self.reverb, self.delay = pan, reverb, delay
        self.drum, self.duck, self.sc = drum, duck, sidechain_source
        self.fx = fx or []            # list of callables (stereo (2,n) -> stereo) applied to this track
        self.params = params or {}
        self.events = []              # (beat, beats, midi_or_None, vel, params)
        self.audio = []               # (seconds, mono or stereo array, gain) pre-rendered clips

    def note(self, pitch, beat, beats, vel=1.0, **params):
        self.events.append((beat, beats, None if pitch is None else nm(pitch), vel, params))
        return self

    def notes(self, pitches, beat, beats_each, vel=1.0, **params):
        for i, p in enumerate(pitches):
            self.note(p, beat + i * beats_each, beats_each, vel, **params)
        return self

    def chord(self, name, beat, beats, octave=4, vel=1.0, inversion=0, **params):
        for p in chord(name, octave, inversion):
            self.note(p, beat, beats, vel, **params)
        return self

    def hit(self, beat, vel=1.0, **params):
        self.events.append((beat, 0.0, None, vel, params))
        return self

    def pattern(self, pat, bar, bars=1, vel=1.0, steps_per_beat=4, beats_per_bar=4, accent=1.15, **params):
        """Drum pattern string, one char per step: x hit, X accent, . rest, o soft."""
        step = 1.0 / steps_per_beat
        L = len(pat)
        for b in range(bars):
            base = (bar + b) * beats_per_bar
            for i, ch in enumerate(pat):
                if ch in 'xXo':
                    v = vel * (accent if ch == 'X' else 0.55 if ch == 'o' else 1.0)
                    self.hit(base + i * step * (beats_per_bar * steps_per_beat / L) / 1.0 if L != beats_per_bar * steps_per_beat else base + i * step, v, **params)
        return self

    def clip(self, seconds, audio, gain_db=0.0):
        """Place a pre-rendered audio clip (mono or (2,n)) at an absolute time."""
        self.audio.append((seconds, audio, db(gain_db)))
        return self

    def render(self, n):
        out = np.zeros((2, n))
        mono = np.zeros(n)
        spb = 60.0 / self.song.bpm
        for (beat, beats, pitch, vel, params) in self.events:
            t0 = self.song.offset + beat * spb
            p = dict(self.params)
            p.update(params)
            if self.drum:
                x = self.inst(vel, **p)
            else:
                x = self.inst(float(midi_hz(pitch)), beats * spb, vel, **p)
            i0 = int(round(t0 * SR))
            if i0 >= n:
                continue
            L = min(len(x), n - i0)
            mono[i0:i0 + L] += x[:L]
        out += pan_stereo(mono, self.pan)
        for (sec, a, g) in self.audio:
            i0 = int(round(sec * SR))
            if a.ndim == 1:
                a = pan_stereo(a, self.pan)
            L = min(a.shape[1], n - i0)
            if L > 0:
                out[:, i0:i0 + L] += a[:, :L] * g
        for f in self.fx:
            out = f(out)
        return out * self.gain

    def hit_times(self):
        spb = 60.0 / self.song.bpm
        return [self.song.offset + b * spb for (b, _, _, _, _) in self.events]


class Song:
    def __init__(self, bpm=128.0, bars=8, beats_per_bar=4, offset=0.0, tail=2.0):
        self.bpm, self.bars, self.bpb, self.offset, self.tail = bpm, bars, beats_per_bar, offset, tail
        self.tracks: list[Track] = []

    @property
    def length_s(self):
        return self.offset + self.bars * self.bpb * 60.0 / self.bpm + self.tail

    def beat_to_s(self, beat):
        return self.offset + beat * 60.0 / self.bpm

    def track(self, name, instrument, **kw):
        t = Track(self, name, instrument, **kw)
        self.tracks.append(t)
        return t

    def render(self, n=None, reverb_size=0.62, reverb_damp=0.45, duck_depth=0.55, duck_release=0.18,
               return_stems=False):
        from pedalboard import Delay, Pedalboard, Reverb
        n = n or int(self.length_s * SR)
        mix = np.zeros((2, n))
        rev_bus = np.zeros((2, n))
        del_bus = np.zeros((2, n))
        stems = {}
        # sidechain envelope from source tracks
        sc_env = np.ones(n)
        for t in self.tracks:
            if t.sc:
                for s in t.hit_times():
                    i0 = int(s * SR)
                    if i0 >= n:
                        continue
                    L = min(int(duck_release * 3 * SR), n - i0)
                    k = np.arange(L) / SR
                    shape = 1 - duck_depth * np.exp(-k / duck_release) * np.clip(k / 0.004 + 0.2, 0, 1)
                    sc_env[i0:i0 + L] = np.minimum(sc_env[i0:i0 + L], shape)
        for t in self.tracks:
            y = t.render(n)
            if t.duck:
                y = y * sc_env
            stems[t.name] = y
            mix += y
            if t.reverb:
                rev_bus += y * t.reverb
            if t.delay:
                del_bus += y * t.delay
        spb = 60.0 / self.bpm
        if np.any(del_bus):
            d = Pedalboard([Delay(delay_seconds=spb * 0.75, feedback=0.35, mix=1.0)])
            mix += d(del_bus.astype(np.float32), SR).astype(np.float64)
        if np.any(rev_bus):
            r = Pedalboard([Reverb(room_size=reverb_size, damping=reverb_damp, wet_level=1.0, dry_level=0.0,
                                   width=1.0)])
            mix += r(rev_bus.astype(np.float32), SR).astype(np.float64)
        return (mix, stems) if return_stems else mix


def place(dst, src, seconds, gain_db=0.0):
    """Add stereo `src` into stereo `dst` at `seconds` (extends nothing; clips at the end)."""
    i0 = int(round(seconds * SR))
    L = min(src.shape[1], dst.shape[1] - i0)
    if L > 0:
        dst[:, i0:i0 + L] += src[:, :L] * db(gain_db)
    return dst


@njit(cache=True)
def _lookahead_gain(peak, ceiling, L, rel):
    """Gain curve that keeps |x| <= ceiling: sliding minimum of the needed gain over a look-ahead
    window of L samples (monotonic deque), a length-L moving average so the gain ramps down
    *before* each peak arrives, and an exponential release back up."""
    n = peak.shape[0]
    need = np.empty(n)
    for i in range(n):
        need[i] = 1.0 if peak[i] <= ceiling else ceiling / peak[i]
    # sliding minimum over [i, i+L)
    mn = np.empty(n)
    dq = np.empty(n + 1, dtype=np.int64)
    head = 0
    tail = 0
    j = 0
    for i in range(n):
        while j < n and j < i + L:
            while tail > head and need[dq[tail - 1]] >= need[j]:
                tail -= 1
            dq[tail] = j
            tail += 1
            j += 1
        while dq[head] < i:
            head += 1
        mn[i] = need[dq[head]]
    # moving average of length L over the past: reaches mn's value by the time the peak arrives
    ma = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += mn[i]
        if i >= L:
            acc -= mn[i - L]
        ma[i] = acc / min(i + 1, L)
    g = np.empty(n)
    prev = 1.0
    for i in range(n):
        target = ma[i] if ma[i] < mn[i] else mn[i]
        if target < prev:
            prev = target
        else:
            prev = rel * prev + (1.0 - rel) * target
        g[i] = prev
    return g


def true_peak_limit(x, ceiling_db=-1.0, lookahead_ms=1.5, release_ms=60.0, os_factor=4):
    """Look-ahead limiter on the oversampled signal (true-peak aware). x: (2, n)."""
    from scipy.signal import resample_poly
    up = resample_poly(x, os_factor, 1, axis=1)
    sr = SR * os_factor
    L = max(1, int(lookahead_ms * 1e-3 * sr))
    peak = np.max(np.abs(up), axis=0)
    ceil = 10 ** (ceiling_db / 20)
    rel = float(np.exp(-1.0 / (release_ms * 1e-3 * sr)))
    g = _lookahead_gain(peak, ceil, L, rel)
    # the gain was computed against the future: delay the signal by L so peaks meet their gain
    upd = np.concatenate([np.zeros((up.shape[0], L)), up[:, :-L]], axis=1) if L > 0 else up
    gd = np.concatenate([np.ones(L), g[:-L]]) if L > 0 else g
    # align: sample i of the delayed signal carries peak i-L, whose gain decision is g[i-L] ... use shifted min
    y = upd * gd
    y = resample_poly(y, 1, os_factor, axis=1)
    y = y[:, L // os_factor:]
    y = np.concatenate([y, np.zeros((y.shape[0], x.shape[1] - y.shape[1]))], axis=1) if y.shape[1] < x.shape[1] else y[:, :x.shape[1]]
    return y


def master(stereo, lufs=-14.0, ceiling_db=-1.0, glue=True):
    """Glue compression, loudness to `lufs` (ITU-R BS.1770 via pyloudnorm) and a look-ahead
    true-peak limiter so peaks stay under `ceiling_db`."""
    import pyloudnorm as pyln
    from pedalboard import Compressor, Pedalboard
    from scipy.signal import resample_poly
    from scipy.signal import butter, sosfilt
    x = stereo.astype(np.float64)
    # sub-sonic cleanup (20 Hz, 2nd order): DC and rumble are inaudible but they cost headroom
    x = sosfilt(butter(2, 20.0 / (SR / 2), btype='high', output='sos'), x, axis=1)
    if glue:
        x = Pedalboard([Compressor(threshold_db=-16, ratio=2.0, attack_ms=20, release_ms=150)])(
            x.astype(np.float32), SR).astype(np.float64)
    meter = pyln.Meter(SR)
    for _ in range(4):
        loud = meter.integrated_loudness(x.T)
        x = x * db(lufs - loud)
        x = true_peak_limit(x, ceiling_db - 0.2)
    peak = np.max(np.abs(resample_poly(x, 4, 1, axis=1)))
    if peak > db(ceiling_db):
        x = x * db(ceiling_db) / peak
    return x


def write_stereo(path, stereo, subtype='PCM_24'):
    """Atomic write (render to <stem>.part<suffix>, then rename): a half-written WAV has
    unfinished header sizes, which Windows players reject as an unsupported format."""
    import os
    from pathlib import Path
    import soundfile as sf
    path = Path(path)
    tmp = path.with_name(path.stem + '.part' + path.suffix)
    sf.write(str(tmp), stereo.T, SR, subtype=subtype)
    os.replace(tmp, path)
