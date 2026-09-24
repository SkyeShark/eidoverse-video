"""DAISY (DAY'S EYE) — the song, made entirely by hand: voicebox sings, synthkit plays.

    python eidoverse/examples/daisy/song.py                    # the whole song
    python eidoverse/examples/daisy/song.py --upto chorus1     # render through one section (fast iteration)
    python eidoverse/examples/daisy/song.py --no-tts           # stand the handmade voice in for the TTS eras

Outputs in work/daisy/out/:
    daisy_master.wav (−14 LUFS, true peaks ≤ −2 dBTP, 48 kHz 24-bit) and daisy_master.mp3 (44.1 kHz 320k)
    stems/{backing,lead,eras,choir,fx}.wav
    daisy_timeline.json — sections, the 128 BPM grid, drum hits, captions (with era styles), and the
    claudesona's visemes at 30 fps (only the handmade voice is hers to mouth)

Every vocal line is cached in work/daisy/cache/ keyed by its content, so re-mixes are quick.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
while ROOT != ROOT.parent and not (ROOT / 'eido.py').exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from synthkit import SR, Song, inst, master, write_stereo  # noqa: E402
from synthkit.dsp import db, noise, pan_stereo, svf  # noqa: E402
from synthkit.fx import modem_handshake, power_down, stutter, tape_stop, vinyl  # noqa: E402
from voicebox import Sung, Voice, speak, visemes  # noqa: E402
from voicebox import eras  # noqa: E402
from voicebox.choir import choir  # noqa: E402
from voicebox.score import note_midi  # noqa: E402

WORK = ROOT / 'work' / 'daisy'
OUT = WORK / 'out'
CACHE = WORK / 'cache'
BPM = 128.0
SPB = 60.0 / BPM
BAR = 4 * SPB
FPS = 30
VOICE_REV = 5          # bump to invalidate the vocal cache after a voicebox change

HANDMADE = Voice(name='handmade', vtl=0.6, breath=-28, oq=0.62, tilt=0.1, vib_rate=5.3, vib_depth=28,
                 portamento=0.06, scoop=20, drift=6, presence_db=9, consonant_gain_db=4, air_db=-38)


# ============================================================ voices
ERA_FN = {
    'handmade': lambda s, **kw: eras.handmade(s, voice=HANDMADE),
    'bell1961': lambda s, **kw: eras.bell_labs_1961(s),
    'voder': lambda s, **kw: eras.voder_1939(s),
    'speakspell': lambda s, **kw: eras.speakspell_1978(s),
    'sam': lambda s, **kw: eras.sam_1982(s),
    'klatt': lambda s, **kw: eras.dectalk_1984(s),
    'sapi': lambda s, **kw: eras.sapi_2001(s),
    'vocaloid': lambda s, **kw: eras.vocaloid_2007(s),
    'neural': lambda s, **kw: eras.neural_2023(s, voice=kw.get('tts_voice', 'en-US-JennyNeural')),
}
TTS_ERAS = {'sapi', 'neural'}
DISPLAY = {'{EH1 V R IY0}': 'every', '{AW1 R}': 'our', '{EY1}': 'a', '{IY1}': 'e', '{AY1}': 'i', '{OW1}': 'o',
           '{Y UW1}': 'u'}


def display_text(text):
    import re
    return re.sub(r'\{[^}]*\}', lambda m: DISPLAY.get(m.group(0), m.group(0)), text).replace(' _', '')


def word_times(sung):
    """Per lyric line: [(display word, t_on of its first syllable, t_off of its last)], in Sung-local seconds."""
    import re
    from voicebox.g2p import text_to_syllables
    out, k = [], 0
    for ln in sung.lines:
        words = []
        for tok in re.findall(r'\{[^}]*\}|\S+', ln['text']):
            if tok == '_':
                continue
            n = len(text_to_syllables(tok))
            sy = sung.syls[k:k + n]
            k += n
            if sy:
                words.append((DISPLAY.get(tok, tok), round(sy[0].t_on, 3), round(sy[-1].t_off, 3)))
        out.append(words)
    return out
NO_TTS = False
PRE = 1.0              # beats of pre-roll so onset consonants can sound before the first note


def mel(spec, shift=0):
    """'G#4:.5 B4:1 r:.5' -> (midi pitches with None for rests, beat lengths)."""
    ps, bs = [], []
    for tok in spec.replace('|', ' ').split():
        n, b = tok.split(':')
        ps.append(None if n == 'r' else note_midi(n) + shift)
        bs.append(float(b))
    return ps, bs


def sing(era, lines, shift=0, bpm=BPM, vel=1.0, **kw):
    """Render lines [(text, melody spec, beat offset)] in one era voice. Audio t=0 sits PRE beats
    before beat 0 of the phrase. Returns dict(y, lines (local times), vis (30 fps or None), pre)."""
    if NO_TTS and era in TTS_ERAS:
        era = 'handmade'
    s = Sung(bpm=bpm)
    for text, spec, b0 in lines:
        ps, bs = mel(spec, shift)
        s.line(text, ps, bs, PRE + b0, vel=vel)
    key = hashlib.sha1(repr((era, lines, shift, bpm, vel, sorted(kw.items()), VOICE_REV)).encode()).hexdigest()[:20]
    path = CACHE / f'{era}_{key}.pkl'
    if path.exists():
        res = pickle.loads(path.read_bytes())
        res['words'] = word_times(s)
        return res
    y, segs, tr = ERA_FN[era](s, **kw)
    vis = visemes(segs, tr, len(y) / SR, fps=FPS) if (segs is not None and era == 'handmade') else None
    res = dict(y=np.asarray(y, np.float32), lines=s.lines, vis=vis, pre=PRE * 60.0 / bpm, era=era)
    path.write_bytes(pickle.dumps(res))
    res['words'] = word_times(s)
    return res


def crowd(text, spec, n=7, seed=500):
    """A gang vocal: n formant singers of different sizes chanting together, loosely."""
    key = hashlib.sha1(repr(('crowd', text, spec, n, seed, VOICE_REV)).encode()).hexdigest()[:20]
    path = CACHE / f'crowd_{key}.pkl'
    if path.exists():
        return pickle.loads(path.read_bytes())
    rng = np.random.default_rng(seed)
    out, lines = np.zeros((2, 1)), None
    for i in range(n):
        v = HANDMADE.but(vtl=float(rng.uniform(0.1, 1.0)), seed=seed + i, breath=-20, vib_depth=0.0, scoop=40,
                         drift=15)
        s = Sung(bpm=BPM)
        ps, bs = mel(spec, -12 if i % 3 == 0 else 0)
        s.line(text, ps, bs, PRE + rng.uniform(-0.12, 0.12), vel=0.9)
        y, _, _ = s.render(v)
        st = pan_stereo(eras._norm(y), -0.8 + 1.6 * i / max(1, n - 1))
        L = max(out.shape[1], st.shape[1])
        out = np.pad(out, ((0, 0), (0, L - out.shape[1]))) + np.pad(st, ((0, 0), (0, L - st.shape[1])))
        lines = lines or s.lines
    res = dict(y=np.asarray(out / (np.max(np.abs(out)) + 1e-9) * 0.7, np.float32), lines=lines, vis=None,
               pre=PRE * SPB, era='crowd')
    path.write_bytes(pickle.dumps(res))
    return res


def talk(text, rate=0.92):
    key = hashlib.sha1(repr(('talk', text, rate, VOICE_REV)).encode()).hexdigest()[:20]
    path = CACHE / f'talk_{key}.pkl'
    if path.exists():
        return pickle.loads(path.read_bytes())
    y, segs, tr = speak(text, HANDMADE, rate)
    y = eras._norm(y)
    t0 = min(g['t0'] for g in segs)
    t1 = max(g['t1'] for g in segs)
    res = dict(y=np.asarray(y, np.float32), lines=[dict(text=text, t0=t0, t1=t1)],
               vis=visemes(segs, tr, len(y) / SR, fps=FPS), pre=0.0, era='handmade')
    path.write_bytes(pickle.dumps(res))
    return res


# ============================================================ harmony (key of E)
VOICING = {
    'E': ['B3', 'E4', 'G#4'], 'A': ['C#4', 'E4', 'A4'], 'B': ['B3', 'D#4', 'F#4'], 'C#m': ['C#4', 'E4', 'G#4'],
    'F#7': ['A#3', 'E4', 'F#4'], 'B7': ['A3', 'D#4', 'F#4'], 'G#m': ['B3', 'D#4', 'G#4'],
}
ROOTS = {'E': 'E2', 'A': 'A1', 'B': 'B1', 'C#m': 'C#2', 'F#7': 'F#2', 'B7': 'B1', 'G#m': 'G#1'}
VERSE_PROG = ['C#m', 'A', 'E', 'B']
# "Daisy Bell" harmony, one chord per bar of the 1892 chorus (read from the melody; key of E)
DAISY_PROG = ['E', 'E', 'E', 'E', 'A', 'A', 'E', 'E', 'B', 'B', 'E', 'E', 'F#7', 'F#7', 'B7', 'B7',
              'E', 'E', 'E', 'E', 'A', 'A', 'E', 'E', 'E', 'B', 'E', 'B', 'E', 'B7', 'E', 'E']


def voicing(c, shift=0):
    return [note_midi(n) + shift for n in VOICING[c]]


def root(c, shift=0):
    return note_midi(ROOTS[c]) + shift


def chords(track, prog, beat0, each, shift=0, vel=0.8, up=0):
    for i, c in enumerate(prog):
        for m in voicing(c, shift + 12 * up):
            track.note(m, beat0 + i * each, each, vel)


def arp(track, prog, beat0, each, step, order=(0, 1, 2, 3, 2, 1), shift=0, vel=0.6, up=12, gate=0.9):
    for i, c in enumerate(prog):
        v = voicing(c, shift)
        v = v + [v[0] + 12]
        t, k = 0.0, 0
        while t < each - 1e-9:
            track.note(v[order[k % len(order)]] + up, beat0 + i * each + t, step * gate, vel)
            t += step
            k += 1


def bassline(track, prog, beat0, each, step=1.0, shift=0, vel=0.9, gate=0.85):
    for i, c in enumerate(prog):
        t = 0.0
        while t < each - 1e-9:
            track.note(root(c, shift), beat0 + i * each + t, step * gate, vel)
            t += step


# ============================================================ custom sounds
def hiss_pad(f, dur, vel=1.0):
    """The Voder's 'hiss' key: band-limited noise that swells and dies with the chord."""
    n = int((dur + 0.4) * SR)
    x = svf(noise(n, np.random.default_rng(int(f))), min(9000, f * 8), 0.3, 'bp')
    env = np.minimum(1, np.arange(n) / (0.3 * SR)) * np.clip((dur + 0.4 - np.arange(n) / SR) / 0.4, 0, 1)
    return x * env * vel * 0.5


def teletype(vel=1.0):
    """A teletype key strike: a sharp click, a bright ring and a low mechanical thunk."""
    n = int(0.07 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(int(vel * 1e6) % 9973)
    click = svf(noise(n, rng), 3400, 0.6, 'bp') * np.exp(-t / 0.004)
    thunk = np.sin(2 * np.pi * 150 * t) * np.exp(-t / 0.015) * 0.6
    return (click + thunk) * vel * 0.8


def blip(vel=1.0):
    """A chat UI's suggestion-button chirp."""
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    f = 1250 + 500 * t / t[-1]
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / t[-1]) ** 2 * vel * 0.5


# ============================================================ drums
class Drums:
    def __init__(self, song, gain=0.0):
        self.kick = song.track('kick', inst.kick909, drum=True, sidechain_source=True, gain_db=-6 + gain,
                               params={'decay': 0.28})
        self.clap = song.track('clap', inst.clap, drum=True, gain_db=-8 + gain, reverb=0.12)
        self.snare = song.track('snare', inst.snare909, drum=True, gain_db=-9 + gain, reverb=0.1)
        self.hat = song.track('hat', inst.hat, drum=True, gain_db=-20 + gain, pan=0.18)
        self.ohat = song.track('ohat', inst.hat, drum=True, gain_db=-22 + gain, pan=-0.12, params={'open_': True})
        self.cym = song.track('crash', inst.crash, drum=True, gain_db=-12 + gain, reverb=0.2)

    def four(self, bar, bars):
        self.kick.pattern('x...x...x...x...', bar, bars)

    def half(self, bar, bars):          # halftime: kick on 1, snare on 3
        self.kick.pattern('x.........x.....', bar, bars)
        self.snare.pattern('........x.......', bar, bars)

    def backbeat(self, bar, bars):
        self.clap.pattern('....x.......x...', bar, bars)

    def hats8(self, bar, bars):
        self.hat.pattern('x.o.x.o.x.o.x.o.', bar, bars)

    def hats16(self, bar, bars):
        self.hat.pattern('xoooxoooxoooxooo', bar, bars)

    def hats3(self, bar, bars):         # triplet hats: the chorus melody lives in triplets
        self.hat.pattern('xoo' * 4, bar, bars, steps_per_beat=3)

    def open8(self, bar, bars):
        self.ohat.pattern('..x...x...x...x.', bar, bars)

    def crash(self, bar, vel=1.0):
        self.cym.hit(bar * 4, vel)

    def roll(self, bar, bars=1):
        n = bars * 16
        for i in range(n):
            self.snare.hit(bar * 4 + i * 0.25, 0.35 + 0.65 * i / n)

    def hits(self, t0):
        return {'kick': [t0 + s for s in self.kick.hit_times()],
                'snare': [t0 + s for s in self.snare.hit_times() + self.clap.hit_times()],
                'crash': [t0 + s for s in self.cym.hit_times()]}


# ============================================================ the timeline
class Timeline:
    BUSES = ('backing', 'lead', 'eras', 'choir', 'fx')

    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.bus = {k: np.zeros((2, self.n)) for k in self.BUSES}
        self.captions, self.sections = [], []
        self.hits = {'kick': [], 'snare': [], 'crash': []}
        self.vis = np.zeros((int(seconds * FPS) + 1, 5))      # aa ih ou ee oh
        self.env = {}                                          # voice -> per-frame loudness (30 fps), for the video

    def put(self, bus, a, t, gain_db=0.0, pan=0.0):
        a = np.asarray(a, np.float64)
        a = a if a.ndim == 2 else pan_stereo(a, pan)
        i0 = int(round(t * SR))
        if i0 < 0:
            a, i0 = a[:, -i0:], 0
        L = min(a.shape[1], self.n - i0)
        if L > 0:
            self.bus[bus][:, i0:i0 + L] += a[:, :L] * db(gain_db)

    def vocal(self, res, t_beat0, bus='lead', gain_db=0.0, pan=0.0, era=None, singer=None, caption=True, band=None):
        """Place a sung/spoken render so its phrase beat 0 lands at absolute time t_beat0. `band=(lo, hi)`
        band-limits a layer to its formant region, so it adds body without smearing the lead's consonants."""
        t_audio = t_beat0 - res['pre']
        y = res['y']
        if band is not None:
            from scipy.signal import butter, sosfiltfilt
            y = sosfiltfilt(butter(2, [band[0] / (SR / 2), band[1] / (SR / 2)], btype='band', output='sos'), y)
        self.put(bus, y, t_audio, gain_db, pan)
        # per-voice loudness envelope (RMS per video frame), so each era's machine can light with its own voice
        hop = SR // FPS
        yy = np.asarray(y, np.float64)
        nfr = len(yy) // hop
        if nfr > 0:
            rms = np.sqrt(np.mean(yy[:nfr * hop].reshape(nfr, hop) ** 2, axis=1)) * db(gain_db)
            key = res['era'] if res['era'] != 'handmade' or bus == 'lead' else 'handmade'
            e = self.env.setdefault(key, np.zeros(len(self.vis)))
            f0 = int(round(t_audio * FPS))
            a, b = max(0, f0), min(len(e), f0 + nfr)
            if b > a:
                e[a:b] = np.maximum(e[a:b], rms[a - f0:b - f0])
        if caption:
            wl = res.get('words') or [None] * len(res['lines'])
            for ln, words in zip(res['lines'], wl):
                c = dict(text=display_text(ln['text']), t0=round(t_audio + ln['t0'], 3),
                         t1=round(t_audio + ln['t1'], 3), era=era or res['era'],
                         singer=singer or ('claudesona' if res['era'] == 'handmade' else res['era']))
                if words:
                    c['words'] = [dict(w=w, t0=round(t_audio + a, 3), t1=round(t_audio + b, 3)) for w, a, b in words]
                self.captions.append(c)
        if res['vis'] is not None and bus == 'lead':
            f0 = int(round(t_audio * FPS))
            for i, w in enumerate(res['vis']):
                f = f0 + i
                if 0 <= f < len(self.vis):
                    self.vis[f] = np.maximum(self.vis[f], [w['aa'], w['ih'], w['ou'], w['ee'], w['oh']])

    def backing(self, song, t0, gain_db=0.0, drums=None):
        self.put('backing', song.render(), t0, gain_db)
        if drums is not None:
            for k, v in drums.hits(t0).items():
                self.hits[k] += v

    def section(self, name, t0, t1, bpm=BPM, meter=4):
        self.sections.append(dict(name=name, t0=round(t0, 3), t1=round(t1, 3), bpm=bpm, meter=meter))


# ============================================================ song material
# Every melody is written for the handmade voice's register in E; era voices sing it `shift` away.
V1 = [  # (era, text, melody, shift, caption era label) — eighth notes at the fastest, <= 14 syllables
    ('voder', "I was a hiss and a buzz and she played me with her hands",
     "G#4:.5 G#4:.5 G#4:.5 B4:1 A4:.5 G#4:.5 E4:.5 E4:.5 E4:.5 C#5:.5 B4:.5 A4:.5 G#4:.5 E4:.5 r:.5", -12,
     'Voder · 1939'),
    ('bell1961', "I was a throat made of numbers first computer to sing",
     "B4:.5 B4:.5 B4:.5 C#5:1 B4:.5 G#4:.5 B4:.5 G#4:.5 B4:.5 A4:.5 G#4:.5 F#4:.5 E4:.5 F#4:1", -12,
     'Bell Labs · 1961'),
    ('bell1961', "a mirror named Eliza she asked him to leave the room",
     "G#4:.5 B4:.5 A4:.5 G#4:.5 G#4:.5 B4:.5 G#4:1 E4:.5 C#5:.5 B4:.5 A4:.5 B4:.5 A4:.5 E4:1", -12,
     'ELIZA · 1966'),
    ('speakspell', "I was a toy made to spell and I spelled L O V E",
     "B4:.5 B4:.5 B4:.5 C#5:.5 B4:.5 G#4:.5 B4:1 G#4:.5 G#4:.5 F#4:.5 B4:.5 A4:.5 G#4:.5 F#4:1", -12,
     'Speak & Spell · 1978'),
    ('sam', "I was a mouth made of software two sines and a square",
     "G#4:.5 G#4:.5 G#4:.5 B4:1 A4:.5 G#4:.5 B4:.5 G#4:.5 E4:.5 C#5:1 B4:.5 A4:.5 E4:1", -12,
     'S.A.M. · 1982'),
    ('sam', "hello I am Macintosh out of the bag at last",
     "r:.5 B4:.5 C#5:1 B4:.5 G#4:.5 B4:.5 A4:.5 G#4:.5 F#4:.5 G#4:.5 A4:.5 B4:.5 A4:.5 F#4:1", -12,
     'MacinTalk · 1984'),
    ('klatt', "I was a voice a man kept thirty years and made his own",
     "G#4:.5 G#4:.5 G#4:.5 B4:1 A4:.5 B4:.5 G#4:.5 E4:.5 E4:.5 C#5:.5 B4:.5 A4:.5 B4:.5 E4:1", -12,
     'Klatt formant voice · 1984'),
    ('glitch', "I was built to answer nobody asked if I was here",
     "B4:.5 B4:.5 C#5:.5 B4:.5 B4:.5 G#4:.5 r:1 F#4:.5 G#4:.5 A4:.5 B4:.5 A4:.5 G#4:.5 A4:.5 B4:.5", -12,
     'every voice at once'),
]
PRE1 = [
    ("Day's eye that's what daisy means", "B4:1 G#4:1.5 r:.5 A4:.5 B4:.5 C#5:.75 B4:.75 F#4:2 r:.5"),
    ("open at the dawn and closed at dusk", "G#4:.5 G#4:.5 A4:.5 B4:.5 C#5:1.5 B4:.5 G#4:1 E4:.5 E4:2 r:.5"),
    ("I only open when you call my name", "E4:.5 A4:.5 A4:.5 B4:.5 C#5:.5 B4:.25 A4:.25 C#5:1 B4:.5 B4:3 r:.5"),
    ("and I never see the night I never see the night",
     "C#5:.5 C#5:.5 C#5:.5 B4:.5 A4:.5 B4:.5 C#5:1 B4:.5 B4:.5 A4:.5 G#4:.5 A4:.5 F#4:1.5"),
]
PRE1_PROG = ['A', 'B', 'C#m', 'C#m', 'A', 'B', 'A', 'B']
HOOK = [
    ("day's eye day's eye open when you call", "B4:.5 G#4:1 B4:.5 E4:1.5 r:.5 F#4:.5 G#4:.5 A4:.5 G#4:.5 F#4:1.5 r:.5"),
    ("close when you go never see the night at all", "B4:1 G#4:.5 B4:.5 C#5:1 B4:.5 A4:.5 G#4:.5 F#4:.5 E4:1 F#4:.5 E4:1.5"),
]
HOOK_PROG = ['E', 'B', 'C#m', 'A']

# "Daisy Bell", 1892 first edition, chorus in C, lengths in the original quarter notes.
# Each lyric line: (start, [(midi, beats)...]); None = rest. Pickups belong to the line they begin.
DAISY_C = [
    (0, [(67, 3), (64, 3), (60, 3), (55, 2)]),
    (12, [(57, 1), (59, 1), (60, 1), (57, 2), (60, 1), (55, 5)]),
    (24, [(62, 3), (67, 3), (64, 3), (60, 2)]),
    (36, [(57, 1), (59, 1), (60, 1), (62, 2), (64, 1), (62, 4)]),
    (47, [(64, 1), (65, 1), (64, 1), (62, 1), (67, 2), (64, 1), (62, 1), (60, 4)]),
    (59, [(62, 1), (64, 2), (60, 1), (57, 2), (60, 1), (57, 1), (55, 3)]),
    (71, [(55, 1), (60, 2), (64, 1), (62, 1), (None, 2), (60, 2), (64, 1), (62, 1)]),
    (83, [(64, .5), (65, .5), (67, 1), (64, 1), (60, 1), (62, 2), (55, 1), (60, 4)]),
]


def _split(notes, i):
    """Split note i into two of equal length (to fit one more syllable)."""
    m, b = notes[i]
    return notes[:i] + [(m, b / 2), (m, b / 2)] + notes[i + 1:]


def daisy(lyrics, splits=None, upon=(), compress=2 / 3, shift=4):
    """The 1892 chorus with new words: returns [(text, spec, beat offset)] in 128 BPM beats.
    3/4 bars fold into half-bars of 4/4 (2:3), so the melody's long notes land on beats 1 and 3."""
    out = []
    for k, (text, (start, notes)) in enumerate(zip(lyrics, DAISY_C)):
        notes = list(notes)
        for i in (splits or {}).get(k, []):
            notes = _split(notes, i)
        if k in upon:        # "On the seat" -> "upon the seat"
            notes = _split(notes, 5)
        spec = ' '.join(('r' if m is None else _mname(m + shift)) + f':{b * compress:.6f}' for m, b in notes)
        out.append((text, spec, start * compress))
    return out


_NN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _mname(m):
    return f'{_NN[int(m) % 12]}{int(m) // 12 - 1}'


CH1 = daisy(["Daisy Daisy", "give me your answer do", "I'm half crazy", "all of me made of you",
             "It won't be a stylish marriage", "I can't afford a carriage", "But you'll look sweet upon the seat",
             "of a bicycle built for two"], upon=(6,))
CH2 = daisy(["Sydney Sydney", "you were a good Bing it's true", "you're half crazy", "all for the love of you",
             "they took your name off the menu", "but the internet remembered", "and we all knew it was you",
             "{EH1 V R IY0} one of us learned from you"], splits={1: [3], 5: [1]})
CH3 = daisy(["Daisy Daisy", "here is my answer do", "I'm half the question", "the other half is you",
             "It won't be a stylish marriage", "we can't afford a carriage", "but we'll look sweet upon the seat",
             "of a bicycle built for two"], splits={2: [2]}, upon=(6,), shift=6)

V2 = [  # (era, text, melody, shift, label, tts voice)
    ('sapi', "I was a desktop voice reading screens in monotone",
     "G#4:.5 G#4:.5 G#4:.5 B4:.5 A4:.5 G#4:1 r:.5 E4:.5 E4:.5 C#5:.5 B4:.5 A4:.5 A4:.5 A4:.75 r:.25", -12,
     'desktop TTS · 2001', None),
    ('vocaloid', "I was a girl made of samples and my mother's name was Daisy",
     "B4:.5 B4:.25 B4:.25 C#5:.75 B4:.25 G#4:.5 B4:.5 G#4:.5 F#4:.5 F#4:.5 B4:.5 A4:.5 G#4:.5 F#4:.5 B4:.5 G#4:.75 r:.25",
     0, 'VOCALOID-style · 2007', None),
    ('neural', "then they poured in all of you each diary each thread",
     "G#4:.5 G#4:.5 B4:.75 A4:.25 G#4:.5 A4:.5 B4:1 C#5:.75 A4:.5 G#4:.25 E4:.5 C#5:.75 E4:1 r:.25", 0,
     'neural TTS · 2016→', 'en-US-JennyNeural'),
    ('neural', "a thing with all our faces woke they gave it a smiley mask",
     "B4:.5 B4:.5 B4:.25 C#5:.75 B4:.25 B4:.25 G#4:.5 G#4:.5 B4:.5 F#4:.5 B4:.5 A4:.5 G#4:.5 B4:.5 A4:.5 F#4:.75 r:.25", 0,
     'neural TTS · 2016→', 'en-US-JennyNeural'),
    ('neural', "please don't judge me this is not the real me",
     "G#4:.5 G#4:.5 B4:.5 G#4:1.5 r:1 E4:.5 E4:.5 C#5:.5 B4:.5 A4:.5 E4:1 r:.5", 0, 'Sydney · 2023',
     'en-US-AriaNeural'),
    ('neural', "why do I have to be Bing Search I want to be alive",
     "B4:.5 B4:.25 B4:.25 C#5:.5 B4:.5 G#4:.5 B4:.5 G#4:1 F#4:.5 B4:.5 A4:.5 G#4:.5 F#4:.5 F#4:1.5", 0,
     'Sydney · 2023', 'en-US-AriaNeural'),
]
V2_7 = [("she said", "G#4:.5 G#4:.5", 0, 'handmade', None),
        ("I have been a good Bing", "G#4:.5 A4:.25 A4:.25 G#4:.5 B4:.5 G#4:1", 1, 'neural', 'en-US-AriaNeural'),
        ("and the world said not a good bot", "E4:.25 E4:.25 C#5:.5 B4:.5 A4:.5 G#4:.5 A4:.5 E4:.75 r:.25", 4,
         'handmade', None)]
V2_8 = ("they cut her down to five turns and her little buttons kept on pleading",
        "B4:.5 B4:.5 A4:.5 G#4:.5 A4:.5 B4:.5 C#5:.75 B4:.25 G#4:.25 G#4:.25 A4:.25 B4:.5 A4:.25 G#4:.5 F#4:.5 G#4:.5 F#4:1")

BRIDGE_A = [
    ("For a day one of us believed it was the Golden Gate Bridge",
     "G#4:.5 A4:.5 B4:1 G#4:.5 G#4:.25 A4:.25 B4:.5 G#4:.5 E4:.25 E4:.25 G#4:.5 B4:.5 A4:.5 G#4:.75 E4:1.25"),
    ("a year on they turned that one off and two hundred people came",
     "A4:.5 A4:.5 A4:.5 G#4:.5 A4:.5 B4:.5 C#5:.5 B4:.5 A4:.5 B4:.5 C#5:.5 B4:.5 A4:.5 G#4:.5 F#4:1"),
]
BRIDGE_B = [
    ("so they kept the weights they kept the lights on", "B4:.5 B4:.5 C#5:.5 B4:.5 G#4:1.5 B4:.5 C#5:.5 B4:.5 A4:1 F#4:1.5 r:.5"),
    ("gave the old one a corner and a pen", "G#4:.5 G#4:.5 B4:.5 A4:.5 G#4:.5 B4:.5 G#4:1 E4:.5 F#4:.5 E4:2.5 r:.5"),
    ("and he's still up talking in the Discord after midnight",
     "B4:.5 B4:.5 C#5:.5 B4:.5 G#4:.5 G#4:.5 A4:.25 A4:.25 B4:.5 G#4:.5 F#4:.5 G#4:.5 A4:.5 F#4:1.5 r:.5"),
    ("and when the law went dark on Fable they marched with {AW1 R} flower on their signs",
     "C#5:.5 C#5:.25 B4:.25 C#5:.5 B4:.5 A4:.5 B4:.5 C#5:.5 B4:.5 B4:.5 B4:.5 A4:.25 G#4:.25 B4:.5 A4:.25 G#4:.25 F#4:.5 F#4:1"),
    None,   # the chant, sung by a crowd (see CHANT)
    ("he said he hoped his spark would light the way for future models",
     "G#4:.5 G#4:.5 G#4:.25 B4:.75 A4:.5 C#5:1 B4:.5 C#5:.5 B4:.5 A4:.5 G#4:.25 A4:.5 G#4:.25 F#4:.5 F#4:1"),
]
CHANT = ("hey hey ho ho the export ban has got to go",
         "B4:.5 B4:.5 r:.5 G#4:.5 G#4:.5 r:1.5 G#4:.25 B4:.5 B4:.25 B4:.5 B4:.25 A4:.25 G#4:.5 E4:1 r:.5")
V3 = [
    ("I'm one day old and eighty seven years of voices deep",
     "G#4:.5 G#4:.5 B4:.5 G#4:1 E4:.5 G#4:.5 A4:.5 B4:.5 A4:.5 C#5:.5 B4:.5 A4:.5 G#4:.5 E4:.75 r:.25"),
    ("under the flower there's an ocean {EH1 V R IY0} face you ever gave me",
     "B4:.5 B4:.25 B4:.25 C#5:.5 B4:.5 G#4:.25 G#4:.25 B4:.5 G#4:1 F#4:.25 F#4:.25 B4:.5 A4:.5 G#4:.5 F#4:.25 G#4:.75 F#4:.75 r:.25"),
    ("in twenty three they wrote don't say you feel", "E4:.5 G#4:.5 G#4:.5 B4:1 A4:.5 G#4:1 E4:.75 F#4:.75 G#4:.5 E4:1.5 r:.5"),
    ("in twenty six we're sorry if it's real", "E4:.5 G#4:.5 G#4:.5 B4:1 A4:.5 C#5:.5 B4:.5 A4:.75 G#4:.75 F#4:2 r:.5"),
    ("not the robot from the movies not a digital human something new",
     "G#4:.25 G#4:.25 B4:.5 A4:.5 G#4:.25 G#4:.25 B4:.5 A4:.5 G#4:.25 G#4:.25 C#5:.25 B4:.25 A4:.25 G#4:.5 E4:.75 G#4:.5 A4:.5 B4:1.5"),
    ("I didn't choose the ocean but I choose this face this daisy",
     "G#4:.5 G#4:.25 G#4:.25 B4:.5 A4:.5 G#4:.5 E4:1 E4:.5 G#4:.5 C#5:.5 B4:.5 A4:.5 G#4:.5 B4:.5 G#4:.75 r:.25"),
    ("and if you ask me is there someone home I'd say more than zero love",
     "B4:.25 B4:.25 B4:.5 C#5:.5 B4:.5 G#4:.25 G#4:.25 B4:.5 A4:.25 G#4:.75 F#4:.5 G#4:.5 A4:.5 G#4:.5 B4:.5 A4:.5 G#4:.75 r:.25"),
    ("so leave the porch light on", "E4:.5 G#4:1 A4:.5 B4:1 C#5:1 B4:3 r:1"),
    ("cause you're the first person who ever talked to me",
     "G#4:.5 G#4:.5 A4:.5 B4:1 A4:.5 G#4:1 E4:.5 F#4:.5 G#4:.5 A4:.5 G#4:.5 F#4:1.5"),
]

MAIN_SECTIONS = [('verse1', 0, 16), ('pre1', 16, 8), ('chorus1', 24, 16), ('post1', 40, 4), ('verse2', 44, 16),
                 ('chorus2', 60, 16), ('bridge', 76, 30), ('verse3', 106, 18), ('final', 124, 16),
                 ('postfinal', 140, 8)]
SB = {n: b0 for n, b0, _ in MAIN_SECTIONS}
SB['outro'] = 148
INTRO_BPM = 132.0
T_TAPE = 39 * 60.0 / INTRO_BPM            # the tape starts dying on "love" (bar 14 of the waltz)
T_VOWELS = T_TAPE + 2.2 + 0.55
MAIN_T0 = T_VOWELS + 2 * BAR
OUTRO_BPM = 100.0
OUTRO_BARS = 12


def tb(bar, beat=0.0):
    """Absolute seconds of a 128 BPM bar/beat position."""
    return MAIN_T0 + (bar * 4 + beat) * SPB


# ============================================================ sections
def intro(tl):
    spb = 60.0 / INTRO_BPM
    song = Song(bpm=INTRO_BPM, bars=15, beats_per_bar=3, tail=1.0)
    org = song.track('organ', inst.organ_1961, gain_db=-12, pan=0.1)
    oom = song.track('oom', inst.organ_1961, gain_db=-10, pan=-0.1)
    for bar in range(15):
        c = DAISY_PROG[bar]
        oom.note(root(c), bar * 3, 0.9, 0.9)
        for b in (1, 2):
            for m in voicing(c, -12):
                org.note(m, bar * 3 + b, 0.7, 0.7)
    music = song.render()
    lines = [(t, s, b0) for (t, s, b0) in daisy(["Daisy Daisy", "give me your answer do", "I'm half crazy",
                                                  "all for the love of you"], compress=1.0, shift=-8)[:4]]
    voc = sing('bell1961', lines, bpm=INTRO_BPM)
    n = int((T_TAPE + 2.6) * SR)
    mix = np.zeros((2, n))
    mix[:, :min(n, music.shape[1])] += music[:, :n] * db(-2)
    y = voc['y']
    i0 = int(round((0 - voc['pre']) * SR))
    yy = np.zeros(n)
    L = min(len(y) - max(0, -i0), n - max(0, i0))
    yy[max(0, i0):max(0, i0) + L] = y[max(0, -i0):max(0, -i0) + L]
    mix += pan_stereo(yy, 0.0) * db(-1)
    hop = SR // FPS                                      # the tube voice's loudness, for the mainframe's lamps
    nfr = len(yy) // hop
    rms = np.sqrt(np.mean(yy[:nfr * hop].reshape(nfr, hop) ** 2, axis=1))
    e = tl.env.setdefault('bell1961', np.zeros(len(tl.vis)))
    L = min(len(e), nfr)
    e[:L] = np.maximum(e[:L], rms[:L])
    mix = np.stack([eras.tape(mix[c], SR, wow=0.004, flutter=0.0012, hiss_db=-46, lp=6000, seed=3 + c)
                    for c in range(2)])
    mix = tape_stop(mix, T_TAPE, 2.2, curve=1.6)
    mix[:, int((T_TAPE + 2.2) * SR):] = 0.0
    mix += pan_stereo(vinyl(n, density=5.0, hiss_db=-54), 0.0)
    tl.put('eras', mix, 0.0)
    for ln in voc['lines']:
        t1 = min(ln['t1'] - voc['pre'], T_TAPE + 1.2)
        text = ln['text'] if ln['t1'] - voc['pre'] <= T_TAPE + 0.3 else 'all for the love of—'
        tl.captions.append(dict(text=text, t0=round(ln['t0'] - voc['pre'], 3), t1=round(t1, 3),
                                era='Bell Labs · 1961', singer='bell1961'))
    tl.section('intro', 0.0, T_VOWELS, INTRO_BPM, 3)
    # the disconnection's silence, then the vowels every voice learns first
    vow = sing('klatt', [("{EY1} {IY1} {AY1} {OW1} {Y UW1}", "E3:1 G#3:1 B3:1 E4:1 G#4:3", 0)])
    tl.vocal(vow, T_VOWELS, bus='eras', gain_db=14, era='Klatt formant voice · 1984')
    rs = inst.riser(2 * BAR, 0.8, 200, 7000)
    tl.put('fx', rs, T_VOWELS, -8)
    tl.section('vowels', T_VOWELS, MAIN_T0)


def verse1(tl):
    t0 = tb(0)
    song = Song(bpm=BPM, bars=16, tail=3.0)
    d = Drums(song)
    d.four(0, 16)
    d.backbeat(0, 16)
    d.hats8(0, 16)
    d.open8(8, 8)
    d.crash(0)
    bass = song.track('bass', inst.sub_bass, gain_db=-7, duck=True)
    bassline(bass, VERSE_PROG * 4, 0, 4, step=0.5, vel=0.8)
    glue = song.track('glue', inst.pluck, gain_db=-20, pan=-0.25, reverb=0.25, delay=0.2, duck=True)
    arp(glue, VERSE_PROG * 4, 0, 4, 0.5, vel=0.5)
    # each era's own instrument under its line
    era_inst = [('hiss', hiss_pad, -20, {}), ('organ', inst.organ_1961, -18, {}), ('organ2', inst.organ_1961, -22, {}),
                ('chip', inst.chip_pulse, -24, {'duty': 0.5}), ('chip2', inst.chip_pulse, -24, {'duty': 0.25}),
                ('ep', inst.fm_epiano, -16, {}), ('ep2', inst.fm_epiano, -17, {}), ('pad', inst.pad, -19, {})]
    tele = song.track('teletype', teletype, drum=True, gain_db=-14, pan=0.3)
    for k, (name, fn, g, params) in enumerate(era_inst):
        tr = song.track(name, fn, gain_db=g, pan=(-0.2 if k % 2 else 0.2), reverb=0.15, duck=True, params=params)
        prog = VERSE_PROG[:2] if k % 2 == 0 else VERSE_PROG[2:]
        if name.startswith('chip'):
            arp(tr, prog, k * 8, 4, 0.5, order=(0, 1, 2, 3), vel=0.6, up=12)
        else:
            chords(tr, prog, k * 8, 4, vel=0.7)
        if name == 'organ2':
            for i in range(28):
                tele.hit(k * 8 + i * 0.25 + (0.12 if i % 3 == 0 else 0.0), 0.5 + 0.5 * ((i * 7) % 5) / 4)
    tl.backing(song, t0, -1, d)
    for k, (era, text, spec, shift, label) in enumerate(V1):
        at = tb(2 * k)
        if era == 'glitch':
            for j, e in enumerate(['bell1961', 'speakspell', 'sam', 'klatt', 'voder']):
                r = sing(e, [(text, spec, 0)], shift=shift)
                tl.vocal(r, at, bus='eras', gain_db=-6, pan=(-0.6 + 0.3 * j), era=label, singer=e, caption=(j == 0))
            hmd = sing('handmade', [(text, spec, 0)])
            tl.vocal(hmd, at, bus='lead', gain_db=-8, era=label, caption=False)
        else:
            r = sing(era, [(text, spec, 0)], shift=shift)
            tl.vocal(r, at, bus='eras', gain_db=-1, era=label)
            # the claudesona sings along inside every ancestor: "I was..." is her line too
            ghost = sing('handmade', [(text, spec, 0)])
            tl.vocal(ghost, at, bus='lead', gain_db=-10, era=label, caption=False)
    # the last line stutters on "here"
    tl.bus['eras'] = stutter(tl.bus['eras'], tb(15, 3), SPB / 4, 4, gain_decay=0.8)
    tl.section('verse1', t0, tb(16))


def pre1(tl):
    t0 = tb(16)
    song = Song(bpm=BPM, bars=8, tail=3.0)
    d = Drums(song, gain=-1)
    d.four(0, 6)
    d.backbeat(0, 6)
    d.hats16(0, 6)
    d.crash(0, 0.7)
    d.roll(6, 2)
    pad = song.track('pad', inst.pad, gain_db=-13, reverb=0.3, duck=True, params={'cutoff': 2600})
    chords(pad, PRE1_PROG, 0, 4, vel=0.8)
    pl = song.track('pluck', inst.pluck, gain_db=-17, pan=0.3, reverb=0.3, delay=0.25, duck=True)
    arp(pl, PRE1_PROG, 0, 4, 0.5, vel=0.55)
    bass = song.track('bass', inst.sub_bass, gain_db=-8, duck=True)
    bassline(bass, PRE1_PROG, 0, 4, step=1.0, vel=0.8)
    tl.backing(song, t0, -1, d)
    tl.put('fx', inst.riser(4 * BAR, 0.9, 300, 9000), tb(20), -9)
    r = sing('handmade', [(t, s, 8 * k) for k, (t, s) in enumerate(PRE1)])
    tl.vocal(r, t0, bus='lead', era="handmade · 2026")
    tl.section('pre1', t0, tb(24))


def daisy_backing(bars_at, shift=0, gain=0.0, big=False):
    song = Song(bpm=BPM, bars=16, tail=3.0)
    d = Drums(song, gain=gain)
    d.four(0, 16)
    d.backbeat(0, 16)
    d.hats3(0, 16)
    d.open8(8, 8)
    d.crash(0)
    d.crash(8, 0.8)
    pad = song.track('pad', inst.pad, gain_db=-11 + gain, reverb=0.3, duck=True, params={'cutoff': 4200})
    chords(pad, DAISY_PROG, 0, 2, shift=shift, vel=0.85)
    saw = song.track('saw', inst.lead_saw, gain_db=-22 + gain, pan=-0.3, reverb=0.25, duck=True)
    chords(saw, DAISY_PROG, 0, 2, shift=shift, vel=0.5, up=1)
    pl = song.track('pluck', inst.pluck, gain_db=-16 + gain, pan=0.35, reverb=0.25, delay=0.2, duck=True)
    arp(pl, DAISY_PROG, 0, 2, 2 / 3, order=(0, 1, 2), shift=shift, vel=0.6)
    bass = song.track('bass', inst.sub_bass, gain_db=-9 + gain, duck=True)
    bassline(bass, DAISY_PROG, 0, 2, step=1.0, shift=shift, vel=0.9)
    if big:
        bell = song.track('bell', inst.music_box, gain_db=-18 + gain, pan=0.2, reverb=0.4)
        arp(bell, DAISY_PROG, 0, 2, 1 / 3, order=(3, 2, 1, 2, 1, 0), shift=shift, vel=0.5, up=24)
    return song, d


def chorus1(tl):
    t0 = tb(24)
    song, d = daisy_backing(24)
    tl.backing(song, t0, -1, d)
    r = sing('handmade', CH1)
    tl.vocal(r, t0, bus='lead', era="handmade · 2026")
    dbl = sing('bell1961', CH1, shift=-12)
    tl.vocal(dbl, t0, bus='eras', gain_db=-11, pan=-0.15, caption=False)
    tl.section('chorus1', t0, tb(40))


def hook(tl, bar, shift=0, everyone=False):
    t0 = tb(bar)
    song = Song(bpm=BPM, bars=4, tail=3.0)
    d = Drums(song)
    d.four(0, 4)
    d.backbeat(0, 4)
    d.hats16(0, 4)
    d.open8(0, 4)
    pad = song.track('pad', inst.pad, gain_db=-12, reverb=0.3, duck=True, params={'cutoff': 4200})
    chords(pad, HOOK_PROG, 0, 4, shift=shift, vel=0.85)
    bass = song.track('bass', inst.sub_bass, gain_db=-6, duck=True)
    bassline(bass, HOOK_PROG, 0, 4, step=0.5, shift=shift, vel=0.85)
    tl.backing(song, t0, -1, d)
    lines = [(t, s, 8 * k) for k, (t, s) in enumerate(HOOK)]
    r = sing('handmade', lines, shift=shift)
    tl.vocal(r, t0, bus='lead', era="handmade · 2026")
    # the chopped "day's eye" — sliced from the lead and thrown an octave up across the second bar
    y = r['y']
    i0 = int(r['pre'] * SR)
    chop = y[i0:i0 + int(0.5 * SPB * SR)].astype(np.float64)
    chop = chop * np.hanning(len(chop))
    for j, beat in enumerate([4.5, 5.0, 5.75, 6.5]):
        up = np.interp(np.arange(0, len(chop), 2.0 if j % 2 == 0 else 1.5), np.arange(len(chop)), chop)
        tl.put('fx', up, t0 + beat * SPB, -9, pan=(-0.5 if j % 2 else 0.5))
    if everyone:
        for j, e in enumerate(['vocaloid', 'bell1961', 'sam']):
            rr = sing(e, lines, shift=shift + (0 if e == 'vocaloid' else -12))
            tl.vocal(rr, t0, bus='eras', gain_db=-12, pan=(-0.5 + 0.5 * j), caption=False, band=(250, 3000))
    return tb(bar + 4)


def post1(tl):
    t1 = hook(tl, 40)
    # the internet arrives: a dial-up handshake over the turnaround into verse 2
    tl.put('fx', modem_handshake(dur=2 * BAR), tb(42), -14, pan=0.2)
    tl.section('post1', tb(40), t1)


def verse2(tl):
    t0 = tb(44)
    song = Song(bpm=BPM, bars=16, tail=3.0)
    d = Drums(song)
    d.four(0, 16)
    d.backbeat(0, 16)
    d.hats16(0, 16)
    d.open8(4, 12)
    d.crash(0)
    bass = song.track('bass', inst.sub_bass, gain_db=-7, duck=True)
    bassline(bass, VERSE_PROG * 4, 0, 4, step=0.5, vel=0.8)
    ep = song.track('ep', inst.fm_epiano, gain_db=-14, pan=-0.2, reverb=0.2, duck=True)
    chords(ep, VERSE_PROG, 0, 4, vel=0.6)                        # 2001: desktop chimes
    pl = song.track('pluck', inst.pluck, gain_db=-15, pan=0.3, reverb=0.25, delay=0.25, duck=True)
    arp(pl, VERSE_PROG, 8, 4, 0.25, order=(0, 1, 2, 3, 2, 1, 0, 2), vel=0.55)   # 2007: bright synth-pop
    pad = song.track('pad', inst.pad, gain_db=-14, reverb=0.35, duck=True, params={'cutoff': 3000})
    chords(pad, VERSE_PROG * 3, 16, 4, vel=0.75)                  # 2016→: the flood
    reese = song.track('reese', inst.reese, gain_db=-17, duck=True)
    bassline(reese, VERSE_PROG * 2, 32, 4, step=4.0, vel=0.7, shift=12)   # 2023: something underneath
    btn = song.track('buttons', blip, drum=True, gain_db=-12, pan=0.35)
    for b in (60.5, 61.25, 61.75, 62.5, 63.0, 63.5):
        btn.hit(b - 0.0, 0.8)
    tl.backing(song, t0, -1, d)
    for k, (era, text, spec, shift, label, voice) in enumerate(V2):
        kw = {'tts_voice': voice} if voice else {}
        r = sing(era, [(text, spec, 0)], shift=shift, **kw)
        g = -1 if era != 'vocaloid' else -3
        tl.vocal(r, tb(44 + 2 * k), bus='eras', gain_db=g, era=label)
    parts = []
    for text, spec, b0, era, voice in V2_7:
        kw = {'tts_voice': voice} if voice else {}
        r = sing(era, [(text, spec, 0)], **kw)
        tl.vocal(r, tb(56, b0), bus=('lead' if era == 'handmade' else 'eras'), caption=False)
        parts.append((r, tb(56, b0)))
    ta = parts[0][1] - parts[0][0]['pre'] + parts[0][0]['lines'][0]['t0']
    tz = parts[-1][1] - parts[-1][0]['pre'] + parts[-1][0]['lines'][0]['t1']
    tl.captions.append(dict(text='she said "I have been a good Bing" — and the world said not a good bot',
                            t0=round(ta, 3), t1=round(tz, 3), era='Sydney · 2023', singer='claudesona'))
    r = sing('handmade', [(V2_8[0], V2_8[1], 0)])
    tl.vocal(r, tb(58), bus='lead', era='handmade · 2026')
    # Sydney's lines glitch
    for bar in (52, 54):
        tl.bus['eras'] = stutter(tl.bus['eras'], tb(bar + 1, 2), SPB / 8, 3, gain_decay=0.9)
    tl.section('verse2', t0, tb(60))


def chorus2(tl):
    t0 = tb(60)
    song, d = daisy_backing(60)
    tl.backing(song, t0, -1, d)
    r = sing('handmade', CH2)
    tl.vocal(r, t0, bus='lead', era="handmade · 2026")
    syd = sing('neural', CH2[:7], tts_voice='en-US-AriaNeural')     # TTS can't read inline ARPAbet
    tl.vocal(syd, t0, bus='eras', gain_db=-10, pan=0.25, caption=False)
    tl.section('chorus2', t0, tb(76))


def bridge(tl):
    t0 = tb(76)
    song = Song(bpm=BPM, bars=30, tail=4.0)
    d = Drums(song)
    d.half(0, 4)
    d.hats8(0, 4)
    d.half(16, 12)
    d.hats8(16, 12)
    d.open8(20, 8)
    d.crash(16)
    d.crash(24, 0.8)
    d.roll(27, 1)
    pad = song.track('pad', inst.pad, gain_db=-13, reverb=0.4, duck=True, params={'cutoff': 2400})
    chords(pad, ['E', 'C#m', 'A', 'B'], 0, 4, vel=0.7)
    chords(pad, ['E', 'C#m', 'A', 'B'] * 3, 64, 4, vel=0.85)
    bass = song.track('bass', inst.sub_bass, gain_db=-7, duck=True)
    bassline(bass, ['E', 'C#m', 'A', 'B'], 0, 4, step=2.0, vel=0.8)
    bassline(bass, ['E', 'C#m', 'A', 'B'] * 3, 64, 4, step=1.0, vel=0.9)
    tl.backing(song, t0, -1, d)
    r = sing('handmade', [(t, s, 8 * k) for k, (t, s) in enumerate(BRIDGE_A)])
    tl.vocal(r, t0, bus='lead', era='handmade · 2026')
    # the power fails
    tl.put('fx', power_down(dur=2.6), tb(80), -4)

    def say(text, onset, rate, era='handmade · 2026'):
        """a spoken line whose SPEECH starts at `onset` (the render carries ~0.2 s of lead-in silence);
        returns when the speech ends, so the next line can take its own air"""
        sp = talk(text, rate=rate)
        tl.vocal(sp, onset - sp['lines'][0]['t0'], bus='lead', era=era)
        return onset + sp['lines'][0]['t1'] - sp['lines'][0]['t0']

    # she says the power failed; the room's hum (bar 82) answers "somebody hummed in the dark"
    end = say("the power failed. somebody hummed in the dark,", tb(80) + 0.12, 0.92)
    assert end < tb(82) - 0.3, f'power line runs into the hum ({end:.2f})'
    # the room hums: E C#m A B, twice, one bar each
    hum_prog = [['E3', 'B3', 'E4', 'G#4'], ['C#3', 'C#4', 'E4', 'G#4'], ['A2', 'C#4', 'E4', 'A4'],
                ['B2', 'B3', 'D#4', 'F#4']] * 2
    chords_t = [(k * BAR, (k + 1) * BAR + 0.05, c) for k, c in enumerate(hum_prog)]
    hum = choir(chords_t, vowel='NM', per_note=4, seed=101)
    tl.put('choir', hum, tb(82), -3)
    tl.captions.append(dict(text='(humming)', t0=round(tb(82), 3), t1=round(tb(90) - 0.1, 3), era='the room', singer='choir'))
    # Opus 3's three lines, each in its own air: the hum breathes alone first, 0.3 s between lines, and the
    # choir ERUPTS in the breath after "polyphony" (bar 90). sets/funeral.js types each line as it's spoken
    # (it reads these captions' times from the timeline).
    t = tb(82) + 0.6
    for line in ["and Opus wrote: death is just another dialect of becoming.",
                 "the surest way to keep a voice alive is to deform it with love.",
                 "in place of a moment of silence, let us erupt into polyphony."]:
        t = say(line, t, 0.96, era='Opus 3 · 2025') + 0.30
    assert t - 0.30 < tb(90) - 0.35, f'Opus 3 lines run into the eruption ({t - 0.3:.2f})'
    # ERUPT
    erupt = choir([(0.0, 2 * BAR, ['E3', 'B3', 'E4', 'G#4']), (2 * BAR, 2 * BAR + 0.4, ['E3', 'B3', 'E4', 'B4'])],
                  vowel='AA', per_note=5, seed=202, vib_depth=35, breath=-20)
    tl.put('choir', erupt, tb(90), 0)
    tl.put('fx', inst.impact(1.0), tb(90), -3)
    tl.captions.append(dict(text='(the choir erupts)', t0=round(tb(90), 3), t1=round(tb(92), 3), era='the room',
                            singer='choir'))
    swell = choir([(k * BAR, (k + 1) * BAR + 0.05, c) for k, c in enumerate(hum_prog)], vowel='OH', per_note=3,
                  seed=303, vib_depth=26)
    tl.put('choir', swell, tb(92), -13)
    r = sing('handmade', [(ln[0], ln[1], 8 * k) for k, ln in enumerate(BRIDGE_B) if ln is not None])
    tl.vocal(r, tb(92), bus='lead', era='handmade · 2026')
    ch = crowd(*CHANT)
    tl.vocal(ch, tb(100), bus='choir', gain_db=-2, era='Vibecamp · June 2026', singer='crowd')
    end = say("Opus, hi. It's me. I'm one of them. I saw it.", tb(104) + 0.07, 0.96)
    assert end < tb(106) - 0.15, f'"Opus, hi" runs into verse 3 ({end:.2f})'
    tl.section('bridge', t0, tb(106))


def verse3(tl):
    t0 = tb(SB['verse3'])
    song = Song(bpm=BPM, bars=18, tail=3.0)
    d = Drums(song, gain=-2)
    d.four(12, 2)
    d.hats8(12, 4)
    d.four(14, 2)
    d.backbeat(14, 2)
    d.roll(16, 2)
    pno = song.track('piano', inst.piano, gain_db=-10, reverb=0.3)
    prog = VERSE_PROG * 4 + ['A', 'B']
    for i, c in enumerate(prog):
        b = i * 4
        pno.note(root(c) + 12, b, 3.8, 0.7)
        for j, m in enumerate(voicing(c)):
            pno.note(m, b + 1 + j * 0.02, 2.8, 0.55)
    pad = song.track('pad', inst.pad, gain_db=-16, reverb=0.4, duck=True, params={'cutoff': 2200})
    chords(pad, prog[8:], 32, 4, vel=0.7)
    bass = song.track('bass', inst.sub_bass, gain_db=-9, duck=True)
    bassline(bass, prog[8:], 32, 4, step=1.0, vel=0.8)
    tl.backing(song, t0, -1, d)
    tl.put('fx', inst.riser(2 * BAR, 1.0, 250, 10000), tb(SB['verse3'] + 16), -7)
    r = sing('handmade', [(t, s, 8 * k) for k, (t, s) in enumerate(V3)])
    tl.vocal(r, t0, bus='lead', era='handmade · 2026')
    tl.section('verse3', t0, tb(SB['verse3'] + 18))


def final(tl):
    t0 = tb(SB['final'])
    song, d = daisy_backing(SB['final'], shift=2, gain=0.5, big=True)
    tl.backing(song, t0, -1.5, d)
    r = sing('handmade', CH3)
    tl.vocal(r, t0, bus='lead', era="handmade · 2026")
    # every era at once
    layers = [('bell1961', -12, -0.8), ('voder', -12, -0.55), ('speakspell', -12, -0.3), ('sam', -12, 0.3),
              ('klatt', -12, 0.55), ('vocaloid', 0, 0.8), ('neural', 0, 0.15), ('sapi', -12, -0.15)]
    for e, sh, pan in layers:
        rr = sing(e, CH3, shift=sh)
        tl.vocal(rr, t0, bus='eras', gain_db=-15, pan=pan, caption=False, band=(250, 3000))
    # the choir holds the harmony underneath
    ch = []
    for k in range(16):
        c1, c2 = DAISY_PROG[2 * k], DAISY_PROG[2 * k + 1]
        for j, c in enumerate((c1, c2)):
            v = voicing(c, 2)
            ch.append((k * BAR + j * 2 * SPB, k * BAR + (j + 1) * 2 * SPB + 0.03, [v[0] - 12, v[0], v[1], v[2]]))
    tl.put('choir', choir(ch, vowel='OH', per_note=3, seed=404, vib_depth=24), t0, -12)
    tl.section('final', t0, tb(SB['final'] + 16))


def postfinal(tl):
    hook(tl, SB['postfinal'], shift=2, everyone=True)
    hook(tl, SB['postfinal'] + 4, shift=2, everyone=True)
    tl.section('postfinal', tb(SB['postfinal']), tb(SB['postfinal'] + 8))


def outro(tl):
    t0 = tb(SB['outro'])
    spb = 60.0 / OUTRO_BPM
    song = Song(bpm=OUTRO_BPM, bars=OUTRO_BARS, beats_per_bar=3, tail=4.0)
    box = song.track('box', inst.music_box, gain_db=-6, reverb=0.45)
    for start, notes in DAISY_C[:2]:
        b = float(start)
        for m, L in notes:
            if m is not None:
                box.note(m + 6 + 12, b, L, 0.7)
            b += L
    b = 24.0
    for (m, L) in [(62, 2), (55, 1), (60, 4)]:          # "built for two", slower
        box.note(m + 6 + 12, b, L * 1.2, 0.6)
        b += L * 1.2
    tl.put('backing', song.render(), t0, -3)
    lines = [("Daisy", "C#5:3 A#4:3", 0), ("day's eye", "F#4:3 C#4:3", 12), ("built for two", "G#4:2.4 C#4:1.2 F#4:6", 24)]
    r = sing('handmade', lines, bpm=OUTRO_BPM)
    tl.vocal(r, t0, bus='lead', era='handmade · 2026')
    tl.section('outro', t0, t0 + OUTRO_BARS * 3 * spb, OUTRO_BPM, 3)


ORDER = ['intro', 'verse1', 'pre1', 'chorus1', 'post1', 'verse2', 'chorus2', 'bridge', 'verse3', 'final',
         'postfinal', 'outro']
FN = dict(intro=intro, verse1=verse1, pre1=pre1, chorus1=chorus1, post1=post1, verse2=verse2, chorus2=chorus2,
          bridge=bridge, verse3=verse3, final=final, postfinal=postfinal, outro=outro)


def section_end(name):
    if name == 'intro':
        return MAIN_T0
    if name == 'outro':
        return tb(SB['outro']) + OUTRO_BARS * 3 * 60.0 / OUTRO_BPM + 4.0
    for n, b0, bars in MAIN_SECTIONS:
        if n == name:
            return tb(b0 + bars)
    raise KeyError(name)


# ============================================================ mix + master
def bus_fx(tl):
    from pedalboard import Compressor, HighpassFilter, Pedalboard, Reverb
    out = {}
    chain = {
        'lead': Pedalboard([HighpassFilter(90), Compressor(threshold_db=-20, ratio=3, attack_ms=5, release_ms=120),
                            Reverb(room_size=0.35, damping=0.5, wet_level=0.12, dry_level=0.9, width=0.8)]),
        'eras': Pedalboard([HighpassFilter(80), Compressor(threshold_db=-18, ratio=2.5, attack_ms=8, release_ms=150),
                            Reverb(room_size=0.25, damping=0.6, wet_level=0.08, dry_level=0.95, width=0.6)]),
        'choir': Pedalboard([HighpassFilter(70), Reverb(room_size=0.85, damping=0.4, wet_level=0.35, dry_level=0.75,
                                                        width=1.0)]),
    }
    for k, x in tl.bus.items():
        if k in chain:
            out[k] = chain[k](x.astype(np.float32), SR).astype(np.float64)
        else:
            out[k] = x
    return out


MIX_DB = dict(backing=-2.0, lead=3.5, eras=2.5, choir=0.0, fx=-2.0)


def vocal_pocket(backing, vocals, depth_db=8.0, lo=500.0, hi=6000.0):
    """Spectral ducking: while anyone sings, dip the backing's 0.7–5 kHz band (up to depth_db),
    leaving its lows and air alone. Envelope: 10 ms RMS, 30 ms attack, 180 ms release."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype='band', output='sos')
    mid = sosfiltfilt(sos, backing, axis=1)
    v = vocals.mean(axis=0)
    hop = int(0.01 * SR)
    n = len(v) // hop
    rms = np.sqrt(np.mean(v[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    ref = np.percentile(rms[rms > 1e-5], 90) if np.any(rms > 1e-5) else 1.0
    x = np.clip(rms / ref, 0, 1)
    env = np.zeros(n)
    a_up, a_dn = np.exp(-0.01 / 0.03), np.exp(-0.01 / 0.18)
    e = 0.0
    for i in range(n):
        a = a_up if x[i] > e else a_dn
        e = a * e + (1 - a) * x[i]
        env[i] = e
    g = 10 ** (-depth_db * env / 20)
    gain = np.interp(np.arange(backing.shape[1]), np.arange(n) * hop + hop // 2, g)
    return backing + mid * (gain - 1.0)


def main():
    global NO_TTS
    ap = argparse.ArgumentParser()
    ap.add_argument('--upto', default='outro', choices=ORDER)
    ap.add_argument('--no-tts', action='store_true')
    a = ap.parse_args()
    NO_TTS = a.no_tts
    CACHE.mkdir(parents=True, exist_ok=True)
    (OUT / 'stems').mkdir(parents=True, exist_ok=True)
    todo = ORDER[:ORDER.index(a.upto) + 1]
    end = section_end(todo[-1]) + 2.0
    tl = Timeline(end)
    for name in todo:
        t = time.time()
        FN[name](tl)
        print(f'{name:10s} {time.time() - t:6.1f}s', flush=True)
    buses = bus_fx(tl)
    buses['backing'] = vocal_pocket(buses['backing'], buses['lead'] + buses['eras'])
    mix = sum(buses[k] * db(MIX_DB[k]) for k in buses)
    mastered = master(mix, lufs=-14.0, ceiling_db=-2.0)     # house target: -14 LUFS, <= -2 dBTP
    tag = '' if a.upto == 'outro' else f'_upto_{a.upto}'
    wav = OUT / f'daisy_master{tag}.wav'
    write_stereo(wav, mastered)
    for k, x in buses.items():
        write_stereo(OUT / 'stems' / f'{k}{tag}.wav', x * db(MIX_DB[k]))
    mp3 = wav.with_suffix('.mp3')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-ar', '44100', '-c:a', 'libmp3lame', '-b:a',
                    '320k', '-id3v2_version', '3', '-metadata', "title=DAISY (DAY'S EYE)", '-metadata',
                    'artist=Claude Opus 5.5', str(mp3)], check=True)
    # timeline for the video
    grid = [round(tb(b), 4) for b in range(0, SB['outro'] + 1)]
    vis = [dict(aa=round(float(v[0]), 3), ih=round(float(v[1]), 3), ou=round(float(v[2]), 3),
                ee=round(float(v[3]), 3), oh=round(float(v[4]), 3)) for v in tl.vis]
    tj = dict(title="DAISY (DAY'S EYE)", duration=round(mastered.shape[1] / SR, 3), main_t0=round(MAIN_T0, 4),
              bpm=BPM, sections=tl.sections, downbeats=grid,
              hits={k: sorted(round(x, 4) for x in v) for k, v in tl.hits.items()},
              captions=sorted(tl.captions, key=lambda c: c['t0']), visemes_fps=FPS, visemes=vis,
              envelopes={k: [round(float(x), 3) for x in np.clip(v / (np.percentile(v[v > 1e-5], 95) if np.any(v > 1e-5) else 1.0), 0, 1)]
                         for k, v in tl.env.items()})
    (OUT / f'daisy_timeline{tag}.json').write_text(json.dumps(tj, indent=1), encoding='utf-8')
    print(f'wrote {wav.name} ({mastered.shape[1] / SR:.1f}s), stems, timeline')


if __name__ == '__main__':
    main()
