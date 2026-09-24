"""Score helpers: lyric lines on notes, rule-based speech timing, and visemes.

A sung line is written as text plus parallel lists of pitches and beat lengths.
Every syllable takes one note; a lone `_` in the text continues the previous
syllable onto the next note (a melisma); a pitch of None is a rest.

    notes = line("Dai sy _ Dai sy", ["G4","E4","D4","C4","G3"], [3,2,1,3,3], start_beat=0)
"""
from __future__ import annotations

import re

import numpy as np

from .articulate import CR, Syl, Voice, midi_to_hz, render_syllables
from .g2p import text_to_syllables
from .phonemes import VISEME_OF_CONSONANT, VISEME_OF_VOWEL, VOWELS

_NOTE = re.compile(r'^([A-Ga-g])([#b]?)(-?\d)$')
_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def note_midi(n):
    """'C4' -> 60, 'F#3' -> 54, 'Bb4' -> 70; numbers pass through."""
    if n is None or isinstance(n, (int, float)):
        return n
    m = _NOTE.match(n.strip())
    if not m:
        raise ValueError(f'bad note {n!r}')
    pc = _PC[m.group(1).upper()] + {'#': 1, 'b': -1, '': 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc


class Sung:
    """Accumulates sung lines -> syllables + note segments for one voice layer."""

    def __init__(self, bpm: float, release: float = 0.03):
        self.bpm = bpm
        self.spb = 60.0 / bpm
        self.release = release
        self.syls: list[Syl] = []
        self.notes: list[tuple] = []    # (t_on, t_off, midi)
        self.lines: list[dict] = []     # for subtitles: text, t0, t1

    def line(self, text, pitches, beats, start_beat, vel=1.0, legato=True, velocities=None):
        toks = re.findall(r'\{[^}]*\}|\S+', text)     # keep inline {ARPA BET} groups whole
        pitches = [note_midi(p) for p in pitches]
        assert len(pitches) == len(beats), f'{len(pitches)} pitches vs {len(beats)} beats in {text!r}'
        # expand tokens into syllables (multi-syllable words consume several notes)
        units = []
        for tok in toks:
            if tok == '_':
                units.append('_')
            else:
                for s in text_to_syllables(tok):
                    units.append(s)
        b = start_beat
        ui = 0
        cur = None
        first_t = None
        for i, (p, nb) in enumerate(zip(pitches, beats)):
            t_on, t_off = b * self.spb, (b + nb) * self.spb
            b += nb
            if p is None:
                cur = None
                continue
            if first_t is None:
                first_t = t_on
            u = units[ui] if ui < len(units) else None
            ui += 1
            v = vel if velocities is None else velocities[i]
            if u == '_' and cur is not None:
                cur.t_off = t_off - (0 if legato else self.release)
                self.notes.append((t_on, t_off, p))
                continue
            if u is None or u == '_':
                raise ValueError(f'more notes than syllables in {text!r}')
            s = Syl(onset=list(u['onset']), vowel=u['vowel'], coda=list(u['coda']), t_on=t_on,
                    t_off=t_off - (0 if legato else self.release), vel=v, stress=u['stress'],
                    word=u['word'], word_start=u['word_start'], word_end=u['word_end'],
                    index=len(self.syls))
            self.syls.append(s)
            self.notes.append((t_on, t_off, p))
            cur = s
        if ui < len(units):
            raise ValueError(f'{len(units) - ui} syllables left over in {text!r}')
        self.lines.append(dict(text=text.replace(' _', '').strip(), t0=first_t, t1=b * self.spb))
        return b

    def render(self, voice: Voice, t_end=None):
        return render_syllables(self.syls, self.notes, voice, t_end=t_end)


def speak_syllables(text: str, rate: float = 1.0, t0: float = 0.2):
    """Rule-based speech timing: stressed vowels long, unstressed short, phrase-final lengthening."""
    syls = text_to_syllables(text)
    out = []
    t = t0
    for k, s in enumerate(syls):
        stressed = s['stress'] == 1
        v = 0.15 if stressed else 0.075
        if s['vowel'] in ('AY', 'EY', 'OW', 'AW', 'OY'):
            v *= 1.25
        if s['word_end']:
            v *= 1.15
        if k == len(syls) - 1:
            v *= 1.6
        from .phonemes import CONSONANTS
        on = sum(CONSONANTS[c].dur for c in s['onset']) / rate
        co = sum(CONSONANTS[c].dur for c in s['coda']) * 0.9 / rate
        if k == len(syls) - 1:
            co *= 1.7   # phrase-final consonants ring out instead of being clipped
        t_on = t + on
        t_off = t_on + v / rate + co
        out.append(Syl(onset=list(s['onset']), vowel=s['vowel'], coda=list(s['coda']), t_on=t_on, t_off=t_off,
                       stress=s['stress'], word=s['word'], word_start=s['word_start'], word_end=s['word_end'], index=k))
        t = t_off
    return out


def speech_f0(syls, t_end, f_hi=135.0, f_lo=95.0, accent=0.12):
    """Declining F0 with a rise-fall accent on stressed syllables."""
    n = int(np.ceil(t_end * CR)) + 2
    t = np.arange(n) / CR
    T = max(s.t_off for s in syls)
    base = f_hi + (f_lo - f_hi) * np.clip(t / T, 0, 1)
    acc = np.zeros(n)
    for s in syls:
        if s.stress == 1:
            c = 0.5 * (s.t_on + s.t_off)
            w = (s.t_off - s.t_on) * 0.6
            acc += accent * np.exp(-0.5 * ((t - c) / max(0.02, w)) ** 2)
    return base * (1 + acc)


def speak(text, voice: Voice, rate=1.0, f_hi=None, f_lo=None):
    syls = speak_syllables(text, rate)
    t_end = syls[-1].t_off + 0.4
    lo = 95.0 + 90.0 * voice.vtl if f_lo is None else f_lo
    hi = lo * 1.4 if f_hi is None else f_hi
    f0 = speech_f0(syls, t_end, hi, lo)
    v = voice.but(vib_depth=0.0, scoop=0.0, f1_tuning=False)
    return render_syllables(syls, [], v, t_end=t_end, f0_hz=f0)


def visemes(segs, tracks, duration: float, fps: int = 30, gain: float = 1.0):
    """Per-frame VRM mouth weights {aa, ih, ou, ee, oh} straight from the phoneme timeline.

    Openness follows the synthesized voicing amplitude, so the mouth closes on
    rests and for bilabial closures, and the dominant vowel shape wins.
    """
    av = tracks['av']
    out = []
    nfr = int(np.ceil(duration * fps))
    j = 0
    segs = sorted(segs, key=lambda g: g['t0'])
    peak = max(1e-6, float(np.percentile(av[av > 0.01], 90)) if np.any(av > 0.01) else 1.0)
    for f in range(nfr):
        t = f / fps
        while j < len(segs) - 1 and segs[j]['t1'] <= t:
            j += 1
        w = {'aa': 0.0, 'ih': 0.0, 'ou': 0.0, 'ee': 0.0, 'oh': 0.0}
        g = segs[j] if segs and segs[j]['t0'] <= t < segs[j]['t1'] else None
        i = min(len(av) - 1, int(t * CR))
        amp = min(1.0, av[i] / peak) * gain
        if g is not None:
            ph = g['ph']
            if ph in VOWELS:
                vis = VISEME_OF_VOWEL.get(ph, 'aa')
                if vis != 'closed':
                    w[vis] = amp
            else:
                shape, open_ = VISEME_OF_CONSONANT.get(ph, (None, 0.3))
                if shape and shape != 'closed':
                    w[shape] = open_ * max(amp, 0.5)
        out.append(w)
    return out
