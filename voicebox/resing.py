"""Make a recorded or text-to-speech voice sing a `Sung` score (Praat PSOLA).

    from voicebox.resing import sing_with_tts
    audio = sing_with_tts(song, engine='edge', voice='en-US-JennyNeural')   # neural voice
    audio = sing_with_tts(song, engine='sapi', voice='Microsoft David Desktop', per_word=True)

For every sung line the speech is synthesised, each word's syllable nuclei are
found from intensity peaks in voiced frames, and a piecewise-linear time map
carries every spoken syllable onto its note (consonants before the beat, vowel
on it). Praat's Manipulation object then applies that map as a DurationTier and
the melody (with vibrato) as a PitchTier, and resynthesises by overlap-add.

Backends: `sapi` needs Windows' System.Speech voices (via PowerShell);
`edge` needs the edge-tts package and network access to Microsoft's read-aloud
service. Report which one actually ran.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile

import numpy as np

from .util import read_wav, write_wav

SR = 48000


# --- TTS backends ---------------------------------------------------------------------------
def tts_sapi(text: str, path: str, voice='Microsoft David Desktop', rate=0):
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SelectVoice('{voice}'); $s.Rate = {int(rate)}; "
        f"$s.SetOutputToWaveFile('{os.path.abspath(path)}'); "
        f"$s.Speak('{text.replace(chr(39), chr(39) * 2)}'); $s.Dispose()"
    )
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps], check=True, capture_output=True)
    return path


def tts_edge(text: str, path: str, voice='en-US-JennyNeural', rate='+0%'):
    """Returns word boundaries [(t0, t1, word)] in seconds; writes an mp3 -> wav at `path`."""
    import edge_tts

    async def run():
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
        audio = bytearray()
        words = []
        async for chunk in comm.stream():
            if chunk['type'] == 'audio':
                audio.extend(chunk['data'])
            elif chunk['type'] == 'WordBoundary':
                t0 = chunk['offset'] / 1e7
                words.append((t0, t0 + chunk['duration'] / 1e7, chunk['text']))
        return bytes(audio), words

    # the service drops requests now and then ("No audio was received"): retry with backoff
    import time
    data, words = b'', []
    for attempt in range(5):
        try:
            data, words = asyncio.run(run())
            if data:
                break
        except Exception as e:                 # NoAudioReceived, websocket resets, timeouts
            if attempt == 4:
                raise
            print(f'[tts_edge] retry {attempt + 1} after {type(e).__name__}', flush=True)
        time.sleep(1.5 * 2 ** attempt)
    mp3 = path + '.mp3'
    with open(mp3, 'wb') as f:
        f.write(data)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', str(SR), path], check=True)
    os.remove(mp3)
    return words


# --- analysis ---------------------------------------------------------------------------------
def syllable_nuclei(snd, t0, t1, n_syl, fmin=75, fmax=600):
    """Times of n_syl syllable nuclei inside [t0, t1] (intensity peaks in voiced frames)."""
    from parselmouth.praat import call
    if n_syl <= 0:
        return []
    a, b = max(0.0, t0), min(snd.duration, t1)
    # Praat's intensity window needs >= 6.4 / fmin seconds; a quick TTS word ("a", "it") can be shorter,
    # so analyse a window centred on the word, but only take peaks that fall inside the word.
    need = 6.4 / fmin + 0.01
    wa, wb = a, b
    if wb - wa < need:
        c = 0.5 * (a + b)
        wa, wb = max(0.0, c - need / 2), min(snd.duration, c + need / 2)
        if wb - wa < need:
            return list(a + (b - a) * (np.arange(n_syl) + 0.5) / n_syl)
    part = snd.extract_part(from_time=wa, to_time=wb, preserve_times=True)
    inten = part.to_intensity(minimum_pitch=fmin, time_step=0.005)
    pitch = part.to_pitch(time_step=0.005, pitch_floor=fmin, pitch_ceiling=fmax)
    ts = inten.xs()
    iv = inten.values[0]
    voiced = np.array([pitch.get_value_at_time(t) or 0.0 for t in ts]) > 0
    inside = (ts >= a) & (ts <= b)
    cand = []
    for i in range(1, len(iv) - 1):
        if iv[i] >= iv[i - 1] and iv[i] >= iv[i + 1] and voiced[i] and inside[i]:
            cand.append((iv[i], ts[i]))
    cand.sort(reverse=True)
    chosen = []
    for val, t in cand:
        if all(abs(t - c) > 0.07 for c in chosen):
            chosen.append(t)
        if len(chosen) == n_syl:
            break
    chosen.sort()
    if len(chosen) < n_syl:
        vt = ts[voiced & inside] if np.any(voiced & inside) else ts[inside]
        a, b = (vt[0], vt[-1]) if len(vt) else (a, b)
        chosen = list(a + (b - a) * (np.arange(n_syl) + 0.5) / n_syl)
    return chosen


def _norm_word(w):
    return re.sub(r"[^a-z']", '', w.lower())


def _align_words(groups, words):
    """One (t0, t1) speech span per score word. When the TTS word list differs from the score
    (contractions, punctuation), split the spoken span by each score word's share of characters."""
    if len(words) == len(groups):
        return words
    t0, t1 = words[0][0], words[-1][1]
    lens = [max(1, len(_norm_word(g[0].word))) for g in groups]
    tot = float(sum(lens))
    out, t = [], t0
    for g, L in zip(groups, lens):
        d = (t1 - t0) * L / tot
        out.append((t, t + d, g[0].word))
        t += d
    return out


# --- the re-singing core ------------------------------------------------------------------------
def resing_line(audio_path, words, syls, notes, t_line0, vib_rate=5.3, vib_depth=25.0, fmin=75, fmax=600,
                lead=0.05):
    """Return (audio, start_time) for one line: `words` [(t0,t1,text)] in the speech, `syls` the score
    syllables of the line (in order), `notes` [(t_on, t_off, midi)] of the line."""
    import parselmouth
    from parselmouth.praat import call
    snd = parselmouth.Sound(audio_path)
    # group score syllables by word, in order
    groups = []
    for s in syls:
        if s.word_start or not groups:
            groups.append([s])
        else:
            groups[-1].append(s)
    words = _align_words(groups, words)
    src, tgt = [], []
    pitch_pts = []   # (src_time, hz)
    for grp, (w0, w1, wtext) in zip(groups, words):
        nuc = syllable_nuclei(snd, w0, w1, len(grp), fmin, fmax)
        bounds = [w0] + [0.5 * (nuc[i] + nuc[i + 1]) for i in range(len(nuc) - 1)] + [w1]
        for j, s in enumerate(grp):
            t_on = s.t_on - t_line0
            t_off = s.t_off - t_line0
            src += [bounds[j], nuc[j]]
            tgt += [max(0.0, t_on - lead), t_on + 0.04]
            if j == len(grp) - 1:
                src.append(bounds[j + 1])
                tgt.append(t_off)
    # make the maps strictly increasing
    pairs = sorted(zip(src, tgt))
    S, T = [pairs[0][0]], [pairs[0][1]]
    for a, b in pairs[1:]:
        if a > S[-1] + 1e-3 and b > T[-1] + 1e-3:
            S.append(a)
            T.append(b)
    dur = snd.duration
    if S[0] > 1e-3:                       # before the first anchor: original speed, clamped at 0
        S.insert(0, 0.0)
        T.insert(0, max(0.0, T[0] - S[1]))
    if S[-1] < dur - 1e-3:                # after the last anchor: original speed
        T.append(T[-1] + (dur - S[-1]))
        S.append(dur)
    # Praat's overlap-add allocates at most 3x the input's length of output samples: pad the
    # source with silence so long sung notes fit, and map the padding onto a few milliseconds.
    need = (T[-1] - T[0]) / 2.8
    if need > dur:
        pad = need - dur + 0.1
        arr = np.concatenate([snd.values[0], np.zeros(int(pad * snd.sampling_frequency))])
        snd = parselmouth.Sound(arr, sampling_frequency=snd.sampling_frequency)
        S.append(snd.duration)
        T.append(T[-1] + 0.01)
        dur = snd.duration
    t_start = T[0]
    manip = call(snd, 'To Manipulation', 0.01, fmin, fmax)
    dt = call('Create DurationTier', 'dt', 0, dur)
    eps = 1e-4
    for i in range(len(S) - 1):
        a, b = S[i], S[i + 1]
        f = max(0.05, (T[i + 1] - T[i]) / max(1e-4, b - a))
        call(dt, 'Add point', a + eps, f)
        call(dt, 'Add point', b - eps, f)
    call([manip, dt], 'Replace duration tier')
    # pitch: inverse-map target times to source times and write the melody there
    pt = call('Create PitchTier', 'pt', 0, dur)
    tt = np.arange(0, T[-1], 0.01)
    st = np.interp(tt, T, S)
    mids = np.full(len(tt), np.nan)
    for (a, b, m) in notes:
        a -= t_line0
        b -= t_line0
        sel = (tt >= a - lead) & (tt < b)
        mids[sel] = m
    # hold pitch through gaps, glide between notes
    good = ~np.isnan(mids)
    if not np.any(good):
        return None, t_line0
    mids = np.interp(np.arange(len(tt)), np.nonzero(good)[0], mids[good])
    from scipy.ndimage import gaussian_filter1d
    mids = gaussian_filter1d(mids, 3.0)
    vib = np.zeros(len(tt))
    for (a, b, m) in notes:
        a -= t_line0
        b -= t_line0
        sel = (tt >= a) & (tt < b)
        e = np.clip((tt[sel] - a - 0.25) / 0.3, 0, 1)
        vib[sel] = vib_depth * e * np.sin(2 * np.pi * vib_rate * tt[sel])
    hz = 440.0 * 2 ** ((mids + vib / 100.0 - 69) / 12)
    for s_t, f in zip(st, hz):
        call(pt, 'Add point', float(s_t), float(f))
    call([pt, manip], 'Replace pitch tier')
    out = call(manip, 'Get resynthesis (overlap-add)')
    y = out.values[0]
    y = y[: int(round((T[-1] - T[0]) * out.sampling_frequency))]
    sr = int(out.sampling_frequency)
    if sr != SR:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, SR)
        y = resample_poly(y, SR // g, sr // g)
    return y, t_line0 + t_start


def sing_with_tts(song, engine='edge', voice=None, per_word=False, rate=None, tmpdir=None,
                  vib_rate=5.3, vib_depth=25.0):
    """Sing every line of a `Sung` score with a TTS voice. Returns 48 kHz mono audio."""
    tmpdir = tmpdir or tempfile.mkdtemp(prefix='resing_')
    t_end = max(s.t_off for s in song.syls) + 0.5
    out = np.zeros(int(t_end * SR) + SR)
    # split the syllables/notes by line using the stored line windows
    for li, ln in enumerate(song.lines):
        syls = [s for s in song.syls if ln['t0'] - 1e-6 <= s.t_on < ln['t1'] - 1e-6]
        notes = [n for n in song.notes if ln['t0'] - 1e-6 <= n[0] < ln['t1'] - 1e-6]
        if not syls:
            continue
        wordlist = []
        for s in syls:
            if s.word_start:
                wordlist.append(s.word)
        path = os.path.join(tmpdir, f'line{li}.wav')
        if engine == 'edge':
            words = tts_edge(' '.join(wordlist), path, voice or 'en-US-JennyNeural', rate=rate or '+0%')
            fmin, fmax = 90, 500
        elif engine == 'sapi':
            if per_word:
                # one word at a time, like concatenative-era singing memes
                pieces, words, t = [], [], 0.0
                for wi, w in enumerate(wordlist):
                    wp = os.path.join(tmpdir, f'line{li}_w{wi}.wav')
                    tts_sapi(w, wp, voice or 'Microsoft David Desktop', rate=rate or 0)
                    y, sr = read_wav(wp)
                    if sr != SR:
                        from scipy.signal import resample_poly
                        from math import gcd
                        g = gcd(sr, SR)
                        y = resample_poly(y, SR // g, sr // g)
                    nz = np.nonzero(np.abs(y) > 0.01 * np.max(np.abs(y)))[0]
                    y = y[max(0, nz[0] - 200): nz[-1] + 200] if len(nz) else y
                    words.append((t, t + len(y) / SR, w))
                    pieces.append(y)
                    pieces.append(np.zeros(int(0.08 * SR)))
                    t += len(y) / SR + 0.08
                write_wav(path, np.concatenate(pieces), SR)
            else:
                tts_sapi(' '.join(wordlist), path, voice or 'Microsoft David Desktop', rate=rate or 0)
                words = None
            fmin, fmax = 70, 400
        else:
            raise ValueError(engine)
        if words is None:
            raise NotImplementedError('sentence-level SAPI needs word timings; use per_word=True')
        y, t0 = resing_line(path, words, syls, notes, t_line0=syls[0].t_on - 0.2, vib_rate=vib_rate,
                            vib_depth=vib_depth, fmin=fmin, fmax=fmax)
        if y is None:
            continue
        i0 = int(round(t0 * SR))
        if i0 < 0:
            y = y[-i0:]
            i0 = 0
        L = min(len(y), len(out) - i0)
        fade = np.ones(L)
        k = min(int(0.02 * SR), L // 2)
        fade[:k] = np.linspace(0, 1, k)
        fade[-k:] = np.linspace(1, 0, k)
        out[i0:i0 + L] += y[:L] * fade
    return out / (np.max(np.abs(out)) + 1e-9) * 10 ** (-3 / 20)
