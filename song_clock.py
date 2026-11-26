#!/usr/bin/env python3
"""song_clock.py: a song's clock, measured from the wav. Where its beats, bars, quiet stretches, sections and sung
lines fall, in seconds and in video frames, so that a film can be cut to it. It measures timing only; it never says
how a take sounds (listening is the collaborator's).

    python song_clock.py song.wav [--fps 24] [--out song_clock.json]
        [--lyrics lyrics.txt [--vocal vocals.wav] [--model medium]]   # the lines' times, through align_lyrics.py
        [--downbeat 14.93] [--beats-per-bar 4] [--bpm 128] [--segments 12]
    python song_clock.py song.wav --repeat 33.0 47.6 [--within 60 200]  # where that passage's music comes back
    python song_clock.py song.wav --offset film.mp4 [--film-start 0]     # the film's sound against the song

The clock (JSON; contact_sheet.py and film_print.py read it as a timeline):
  duration_s, sample_rate, channels, and with pyloudnorm installed lufs_integrated and true_peak_dbtp
  tempo_bpm, beats: every beat's time t, its frame, its bar and its place in the bar, and its kind: "measured" (the
    wav's own rise, found within 18 ms of the beat grid) or "carried" (no clear rise there: the grid, smoothed
    through its measured neighbours). The tracker's grid sits a little late on most songs (often 30-40 ms): the
    lag measured over the whole song is taken off first (grid_late_ms). tempo_bpm is the beats' own median spacing
  bars: every --beats-per-bar beats. Their phase is a guess from where the harmony changes unless --downbeat
    names a moment on a bar line (the first word of a verse, say); a bar line is what the song's words and the
    collaborator's ear decide. A beat the tracker missed or doubled shifts the count after it: check the bars
    near the moments a film cuts on
  silences: 0.2 s or more, 25 dB under the loud parts; segments: where timbre and harmony change (S1, S2, ...)
  with --lyrics: lines (each line's start and end, its words, frame and bar), captions ({text, t0, t1}) and
    sections from the lyric file's [Name] lines (a section runs from its first line to the next section's).
    Without lyrics, sections are the measured segments
  check: at every beat with a clear step in the plain level (3 dB or more inside 16 ms), that step's time minus
    the beat's, in ms: how well the clock sits on the sound
Frames: a moment at t seconds sounds in frame 1 + floor(fps * t) (frame 1 starts at 0 s; the WebGPU runner's frame
index is that minus one). Dependencies: numpy, soundfile, librosa; pyloudnorm and scipy for loudness and true
peak; align_lyrics.py's (stable-ts) for --lyrics. Guide: tools-guides/audio.md ("The song's clock").
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

NOWIN = 0x08000000 if os.name == 'nt' else 0
SR, HOP = 22050, 512                     # the tracker's and the segmenter's clock
STEP = 0.001                             # the rises' clock: 1 ms


def fmt(t):
    t = round(t, 1)
    m = int(t // 60)
    return f'{m}:{t - 60 * m:04.1f}'


def read_audio(path):
    """(samples x channels float32, sample rate): soundfile, or ffmpeg for what it cannot read"""
    try:
        import soundfile as sf
        y, sr = sf.read(path, dtype='float32', always_2d=True)
        return y, int(sr)
    except Exception:  # noqa: BLE001  (an mp3, an mp4's sound...)
        sr = 44100
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-ac', '2', '-ar', str(sr), '-f', 'f32le', '-'],
                             capture_output=True, check=True, creationflags=NOWIN).stdout
        return np.frombuffer(raw, np.float32).reshape(-1, 2).copy(), sr


def rises(x, sr):
    """Where the wav's energy rises, on a 1 ms clock: spectral flux of the linear magnitude in three bands (low 30-150
    Hz: kick and bass; mid 150-2000 Hz: voice and chords; high 2-12 kHz: clicks, hats, claps, consonants), each rise
    dated at the middle of the 4 ms it is measured over; and the plain level (rms over 5 ms, no filter)."""
    hop = max(1, sr // 1000)
    n_out = int(len(x) / hop)
    t_out = np.arange(n_out) * STEP
    out = {'t': t_out}
    for name, nfft, lo, hi in (('low', 2048, 30, 150), ('mid', 512, 150, 2000), ('high', 512, 2000, 12000)):
        win = np.hanning(nfft).astype(np.float32)
        n = 1 + (len(x) - nfft) // hop
        if n < 8:
            out[name] = np.zeros(n_out, np.float32)
            continue
        freqs = np.fft.rfftfreq(nfft, 1 / sr)
        sel = (freqs >= lo) & (freqs < hi)
        env = np.zeros(n, np.float32)
        for a in range(0, n, 4096):
            idx = np.arange(a, min(n, a + 4096))
            env[idx] = np.abs(np.fft.rfft(x[idx[:, None] * hop + np.arange(nfft)[None, :]] * win, axis=1))[:, sel].sum(axis=1)
        tt = (np.arange(n) * hop + nfft / 2) / sr - 0.002        # the window's middle; the 4 ms difference sits 2 ms before
        d = np.zeros_like(env)
        d[4:] = env[4:] - env[:-4]
        d = np.convolve(np.maximum(d, 0), np.hanning(7) / np.hanning(7).sum(), mode='same')
        out[name] = np.interp(t_out, tt, d, left=0.0, right=0.0).astype(np.float32)
    w = int(0.005 * sr)
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    mid = (t_out * sr).astype(np.int64)
    a, b = np.clip(mid - w // 2, 0, len(x)), np.clip(mid + w // 2, 0, len(x))
    out['level'] = np.sqrt(np.maximum(0.0, (c[b] - c[a]) / np.maximum(1, b - a))).astype(np.float32)
    return out


def local_mean(d, win=3000):
    """each 1 ms value's surrounding mean (+-3 s), so a quiet passage's rises count as much as a loud one's"""
    n = len(d)
    c = np.concatenate([[0.0], np.cumsum(d.astype(np.float64))])
    i = np.arange(n)
    a, b = np.clip(i - win, 0, n), np.clip(i + win, 0, n)
    return np.maximum((c[b] - c[a]) / np.maximum(1, b - a), 0.02 * float(d.mean()) + 1e-12)


def measure_beats(mono, sr, bpm=None, reach_ms=18, rise_min=4.0):
    """the beat grid (librosa's tracker), its lag taken off, each beat on its own rise where it has one"""
    import librosa
    y22 = librosa.resample(mono, orig_sr=sr, target_sr=SR)
    oenv = librosa.onset.onset_strength(y=y22, sr=SR, hop_length=HOP)
    tempo, beat_fr = librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=HOP, start_bpm=bpm or 120.0)
    tempo = float(np.atleast_1d(tempo)[0])
    grid = librosa.frames_to_time(beat_fr, sr=SR, hop_length=HOP)
    E = rises(mono, sr)
    n = len(E['t'])
    high = E['high'] / local_mean(E['high'])
    # the grid's lag over the whole song: the median of each beat's strongest high-band rise within 60 ms
    offs = []
    for g in grid:
        ci = int(round(g * 1000))
        a_, b_ = max(0, ci - 60), min(n, ci + 61)
        if b_ - a_ < 10:
            continue
        j = int(np.argmax(high[a_:b_]))
        if high[a_ + j] >= rise_min and 0 < j < b_ - a_ - 1:
            offs.append(a_ + j - ci)
    lag = float(np.median(offs)) / 1000.0 if len(offs) >= max(8, len(grid) // 5) else 0.0
    grid = grid + lag
    nb = len(grid)
    rise = np.full(nb, np.nan)
    for i, g in enumerate(grid):
        ci = int(round(g * 1000))
        a_, b_ = max(0, ci - reach_ms), min(n, ci + reach_ms + 1)
        if b_ - a_ < 3:
            continue
        j = int(np.argmax(high[a_:b_]))
        if 0 < j < b_ - a_ - 1 and high[a_ + j] >= rise_min:      # a peak inside the reach, not its edge
            rise[i] = (a_ + j) * STEP
    measured = ~np.isnan(rise)
    # the grid smoothed through the measured rises: a local straight line over beat number, +-3 beats
    idx = np.arange(nb, dtype=np.float64)
    y = np.where(measured, rise, grid)
    wgt = np.where(measured, 1.0, 0.12)
    lattice = grid.copy()
    for i in range(nb):
        k = np.exp(-0.5 * ((idx - i) / 3.0) ** 2) * wgt
        k[np.abs(idx - i) > 10] = 0
        sw, sx, sy = k.sum(), (k * idx).sum(), (k * y).sum()
        sxx, sxy = (k * idx * idx).sum(), (k * idx * y).sum()
        den = sw * sxx - sx * sx
        if abs(den) > 1e-12:
            slope = (sw * sxy - sx * sy) / den
            lattice[i] = (sy - slope * sx) / sw + slope * i
    use = measured & (np.abs(rise - lattice) <= 0.010)
    bt = np.where(use, rise, lattice)
    order = np.argsort(bt, kind='stable')
    bt, use = bt[order], use[order]
    return dict(tempo=tempo, beats=bt, measured=use, lag=lag, rises=E, y22=y22, beat_fr=beat_fr)


def level_check(E, bt):
    """the plain level's steepest rise within 60 ms of each beat, minus the beat (ms), where the level steps up by
    3 dB or more inside 16 ms"""
    lv = E['level'].astype(np.float64)
    n = len(lv)
    if n < 40:
        return {'beats_with_a_clear_level_rise': 0}
    c = np.concatenate([[0.0], np.cumsum(lv ** 2)])
    i_ = np.arange(n)
    w = 6
    lev = np.sqrt((c[np.clip(i_ + w, 0, n)] - c[np.clip(i_ - w, 0, n)]) / (2 * w))
    db = 20 * np.log10(lev + 1e-5)
    slope = np.zeros(n)
    slope[8:-8] = db[16:] - db[:-16]
    res = []
    for t in bt:
        ci = int(round(t * 1000))
        a_, b_ = max(0, ci - 60), min(n, ci + 61)
        if b_ - a_ < 10:
            continue
        j = int(np.argmax(slope[a_:b_]))
        if slope[a_ + j] >= 3.0:
            res.append(a_ + j - ci)
    res = np.array(res)
    if not len(res):
        return {'beats_with_a_clear_level_rise': 0}
    return {'what': "the plain level's steepest rise (dB over 16 ms) within 60 ms of each beat, minus the beat, in ms, "
                    'where the level steps up by 3 dB or more', 'beats_with_a_clear_level_rise': int(len(res)),
            'median_ms': float(np.median(res)), 'within_10_ms': int((np.abs(res) <= 10).sum()),
            'within_half_a_frame_at_24': int((np.abs(res) <= 21).sum())}


def bar_phase(y22, beat_fr, nb, per_bar):
    """the bar lines' phase where the harmony changes most (beat-synchronous chroma), a guess"""
    import librosa
    chroma = librosa.feature.chroma_cqt(y=y22, sr=SR, hop_length=HOP)
    cs = librosa.util.sync(chroma, beat_fr, aggregate=np.median)       # column j + 1 starts at beat j
    u = cs / np.maximum(np.linalg.norm(cs, axis=0, keepdims=True), 1e-9)
    nov = 1.0 - (u[:, :-1] * u[:, 1:]).sum(axis=0)
    m = min(nb, len(nov))
    return int(np.argmax([nov[p:m:per_bar].mean() if len(nov[p:m:per_bar]) else 0.0 for p in range(per_bar)]))


def silences_of(y22, dur):
    import librosa
    rms = librosa.feature.rms(y=y22, frame_length=2048, hop_length=HOP)[0]
    db = 20 * np.log10(rms + 1e-9)
    ft = librosa.frames_to_time(np.arange(len(db)), sr=SR, hop_length=HOP)
    loud = float(np.median(db[db > db.max() - 30]))
    quiet = db < loud - 25.0
    out, i = [], 0
    while i < len(quiet):
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < len(quiet) and quiet[j]:
            j += 1
        s, e = float(ft[i]), float(ft[min(j, len(ft) - 1)])
        if e - s >= 0.2 and s > 0.5 and e < dur - 0.5:
            out.append({'t0': round(s, 3), 't1': round(e, 3), 'dur': round(e - s, 3),
                        'under_loud_db': round(loud - float(db[i:j].min()), 1)})
        i = j
    return out, db, ft


def segments_of(y22, beat_fr, beats, dur, db, ft, k):
    """where timbre and harmony change, on beats (beat-synchronous chroma + MFCC, agglomerative)"""
    import librosa
    cs = librosa.util.sync(librosa.feature.chroma_cqt(y=y22, sr=SR, hop_length=HOP), beat_fr, aggregate=np.median)
    ms = librosa.util.sync(librosa.feature.mfcc(y=y22, sr=SR, n_mfcc=13, hop_length=HOP), beat_fr, aggregate=np.mean)

    def z(v):
        return (v - v.mean(axis=1, keepdims=True)) / (v.std(axis=1, keepdims=True) + 1e-9)
    feat = np.vstack([z(cs), z(ms)])
    k = max(2, min(k, feat.shape[1] - 1))
    bidx = librosa.segment.agglomerative(feat, k)
    col_t = np.concatenate([[0.0], beats])
    starts = sorted(set(float(col_t[min(c, len(col_t) - 1)]) for c in bidx))
    out = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else dur
        sel = (ft >= s) & (ft < e)
        out.append({'name': f'S{i + 1}', 't0': round(s, 3), 't1': round(e, 3),
                    'level_db': round(float(db[sel].mean()), 1) if sel.any() else None})
    return out


def read_lyrics(path):
    """one sung line per line; a line in [square brackets] names the section of the lines after it"""
    out, section = [], ''
    for raw in open(path, encoding='utf-8'):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line.strip('[]').strip()
            continue
        out.append({'section': section, 'text': line})
    return out


def clock(a):
    y, sr = read_audio(a.song)
    dur = y.shape[0] / sr
    mono = y.mean(axis=1)
    fin = lambda t: int(math.floor(1 + a.fps * t + 1e-9))  # noqa: E731  (the frame a moment sounds in)
    out = {'_what': 'song_clock.py: timing measured from the wav (not how it sounds). frame = 1 + floor(fps * t), the '
                    'video frame a moment sounds in; frame 1 starts at 0 s.',
           'song': os.path.basename(a.song), 'fps': a.fps, 'duration_s': round(dur, 3), 'sample_rate': sr,
           'channels': int(y.shape[1])}
    try:
        import pyloudnorm as pyln
        from scipy.signal import resample_poly
        out['lufs_integrated'] = round(float(pyln.Meter(sr).integrated_loudness(y.astype(np.float64))), 2)
        tp = max(float(np.abs(resample_poly(y[:, c], 4, 1)).max()) for c in range(y.shape[1]))
        out['true_peak_dbtp'] = round(float(20 * np.log10(max(tp, 1e-9))), 2)
    except ImportError:
        out['lufs_integrated'] = out['true_peak_dbtp'] = None
    print(f'[clock] {os.path.basename(a.song)}: {fmt(dur)} ({dur:.2f} s), {sr} Hz, {y.shape[1]} ch'
          + (f", {out['lufs_integrated']:.1f} LUFS, true peak {out['true_peak_dbtp']:+.2f} dBTP" if out['lufs_integrated'] is not None else ''),
          flush=True)

    B = measure_beats(mono, sr, bpm=a.bpm)
    bt, use = B['beats'], B['measured']
    nb = len(bt)
    if a.downbeat is not None and nb > 1:
        # the beats between the downbeat and the beat nearest it (the tracker often finds no beat at a song's very start)
        q = int(np.argmin(np.abs(bt - a.downbeat)))
        steps = int(round((bt[q] - a.downbeat) / float(np.median(np.diff(bt)))))
        phase = (q - steps) % a.beats_per_bar
        phase_how = f'a bar line at {a.downbeat} s (--downbeat)'
    else:
        phase = bar_phase(B['y22'], B['beat_fr'], nb, a.beats_per_bar) if nb > a.beats_per_bar else 0
        phase_how = 'a guess from where the harmony changes (pass --downbeat to set it)'
    beats, bars, bar_no = [], [], 0
    for q in range(nb):
        on_bar = (q - phase) % a.beats_per_bar == 0
        if on_bar:
            bar_no += 1
            bars.append({'bar': bar_no, 't': round(float(bt[q]), 4), 'frame': fin(bt[q])})
        beats.append({'n': q, 't': round(float(bt[q]), 4), 'frame': fin(bt[q]), 'bar': bar_no if on_bar else None,
                      'beat': (q - phase) % a.beats_per_bar + 1, 'kind': 'measured' if use[q] else 'carried'})
    bpm = 60.0 / float(np.median(np.diff(bt))) if nb > 2 else B['tempo']      # (the beats' own; the tracker's guess differs)
    out.update(tempo_bpm=round(bpm, 2), beats_per_bar=a.beats_per_bar, bar_phase=phase_how,
               grid_late_ms=round(-1000 * B['lag'], 1), beats=beats, bars=bars)
    late = -1000 * B['lag']
    print(f"[clock] {bpm:.1f} bpm; {nb} beats ({int(use.sum())} on their own rise, {nb - int(use.sum())} carried), "
          f"{len(bars)} bars; the tracker's grid sat {abs(late):.0f} ms {'late' if late >= 0 else 'early'} and is "
          'corrected', flush=True)

    sil, db, ft = silences_of(B['y22'], dur)
    for s in sil:
        s['frame'] = fin(s['t0'])
    out['silences'] = sil
    segs = segments_of(B['y22'], B['beat_fr'], bt, dur, db, ft, a.segments) if nb > 4 else []
    for s in segs:
        s['frame'] = fin(s['t0'])
    out['segments'] = segs
    out['sections'] = [{'name': s['name'], 't0': s['t0'], 't1': s['t1']} for s in segs]
    out['captions'], out['lines'] = [], []

    if a.lyrics:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from align_lyrics import align_lyrics
        lyr = read_lyrics(a.lyrics)
        got = align_lyrics(a.vocal or a.song, '\n'.join(ln['text'] for ln in lyr), model_size=a.model)
        if len(got) != len(lyr):
            print(f'[clock] align_lyrics returned {len(got)} lines for {len(lyr)} written (its single-pass fallback): '
                  'lines kept, sections not set from the lyrics', flush=True)
            lyr = [{'section': '', 'text': g['text']} for g in got]
        bar_t = np.array([b['t'] for b in bars]) if bars else np.zeros(0)
        lines = []
        for ln, g in zip(lyr, got):
            s, e = float(g['start']), float(g['end'])
            lines.append({'text': ln['text'], 'section': ln['section'], 'start': round(s, 3), 'end': round(e, 3),
                          'frame': fin(s), 'bar': int(np.searchsorted(bar_t, s + 1e-3)) if len(bar_t) else None,
                          'words': g.get('words', [])})
        out['lines'] = lines
        out['captions'] = [{'text': ln['text'], 't0': ln['start'], 't1': ln['end']} for ln in lines if ln['end'] > ln['start']]
        named = [ln for ln in lines if ln['section']]
        if named:
            secs = []
            for ln in lines:
                if ln['section'] and (not secs or secs[-1]['name'] != ln['section']):
                    secs.append({'name': ln['section'], 't0': ln['start']})
            for i, s in enumerate(secs):
                s['t1'] = secs[i + 1]['t0'] if i + 1 < len(secs) else round(dur, 3)
            out['sections'] = secs
        print(f'[clock] {len(lines)} lyric lines placed by align_lyrics.py', flush=True)
    out['check'] = level_check(B['rises'], bt)
    path = a.out or os.path.splitext(a.song)[0] + '_clock.json'
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('{\n')
        keys = list(out)
        for k in keys:
            v = out[k]
            if isinstance(v, list) and v and isinstance(v[0], dict):
                fh.write(f' {json.dumps(k)}: [\n' + ',\n'.join('  ' + json.dumps(e, ensure_ascii=False) for e in v) + '\n ]')
            else:
                fh.write(f' {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}')
            fh.write(',\n' if k != keys[-1] else '\n')
        fh.write('}\n')
    c = out['check']
    if c.get('beats_with_a_clear_level_rise'):
        print(f"[clock] check: {c['beats_with_a_clear_level_rise']} beats with a clear level step; the step minus the beat: "
              f"median {c['median_ms']:+.0f} ms, {c['within_10_ms']} within 10 ms", flush=True)
    print(f'[clock] {len(sil)} silences, {len(segs)} segments -> {path}', flush=True)


def repeat(a):
    """where the passage [A, B] comes back in [C, D], beat by beat on harmony (chroma) and timbre (MFCC). A chorus
    scores high on harmony wherever its music returns, sung or not: this says where the music repeats, never what
    is sung there."""
    import librosa
    y, sr = read_audio(a.song)
    y22 = librosa.resample(y.mean(axis=1), orig_sr=sr, target_sr=SR)
    oenv = librosa.onset.onset_strength(y=y22, sr=SR, hop_length=HOP)
    tempo, beat_fr = librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=HOP, start_bpm=a.bpm or 120.0)
    beats = librosa.frames_to_time(beat_fr, sr=SR, hop_length=HOP)
    ch = librosa.util.sync(librosa.feature.chroma_cqt(y=y22, sr=SR, hop_length=HOP), beat_fr, aggregate=np.median)[:, 1:]
    mf = librosa.util.sync(librosa.feature.mfcc(y=y22, sr=SR, n_mfcc=13, hop_length=HOP), beat_fr, aggregate=np.mean)[1:, 1:]

    def unit(v):
        return v / np.maximum(np.linalg.norm(v, axis=0, keepdims=True), 1e-9)
    ch, mf = unit(ch), unit(mf - mf.mean(axis=1, keepdims=True))
    A, Bt = a.repeat
    C, D = a.within or (0.0, len(y22) / SR)
    i0, i1 = int(np.searchsorted(beats, A)), int(np.searchsorted(beats, Bt))
    n = i1 - i0
    if n < 1:
        raise SystemExit('[repeat] the passage holds no beat')
    j0, j1 = int(np.searchsorted(beats, C)), int(np.searchsorted(beats, D)) - n
    rows = []
    for j in range(j0, max(j0, j1) + 1):
        if j + n > ch.shape[1]:
            break
        if abs(j - i0) < n // 2:
            continue                                          # (the passage itself)
        sc = float((ch[:, i0:i1] * ch[:, j:j + n]).sum(axis=0).mean())
        sm = float((mf[:, i0:i1] * mf[:, j:j + n]).sum(axis=0).mean())
        rows.append((sc, sm, j))
    print(f'[repeat] {float(np.atleast_1d(tempo)[0]):.1f} bpm; the passage {A:.2f}-{Bt:.2f} s is {n} beats from beat {i0} '
          f'({beats[i0]:.2f} s). Best starts by harmony (chroma similarity, then timbre):')
    for sc, sm, j in sorted(rows, reverse=True)[:8]:
        print(f'  {beats[j]:7.2f} s (beat {j}, {j - i0:+d} beats): harmony {sc:.3f}, timbre {sm:.3f}')


def audio_at(path, sr, t0, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, t0):.4f}', '-t', f'{dur:.4f}', '-i', path, '-vn', '-ac', '1',
                          '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True, creationflags=NOWIN).stdout
    y = np.frombuffer(raw, np.float32)
    if t0 < 0:                                                # (before the song starts: silence)
        y = np.concatenate([np.zeros(int(round(-t0 * sr)), np.float32), y])
    return y


def offset(a):
    """the film's sound against the song: at five places, the lag (cross-correlation of the waveforms, 8 kHz, +-250
    ms) at which the film's sound matches the song laid at the film's time (film time 0 = song time --film-start)"""
    sr, win, reach = 8000, 6.0, 0.25
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.offset],
                       capture_output=True, text=True, creationflags=NOWIN)
    fdur = float(r.stdout.strip())
    fps = a.fps
    res = []
    for k in range(5):
        t = (fdur - win) * (k + 0.5) / 5
        if t < 0:
            continue
        f = audio_at(a.offset, sr, t, win)
        s = audio_at(a.song, sr, a.film_start + t - reach, win + 2 * reach)
        if len(f) < sr or np.linalg.norm(f) < 1e-6:
            continue
        n = len(f)
        m = len(s) - n
        if m <= 0:
            continue
        L = 1 << int(np.ceil(np.log2(len(s) + n)))
        xc = np.fft.irfft(np.fft.rfft(s, L) * np.conj(np.fft.rfft(f, L)), L)[:m + 1]
        c2 = np.concatenate([[0.0], np.cumsum(s.astype(np.float64) ** 2)])
        norms = np.sqrt(c2[n:n + m + 1] - c2[:m + 1]) * np.linalg.norm(f) + 1e-9
        corr = xc / norms
        lag = int(np.argmax(corr))
        # the film's sound matches the song `lag` samples into the window that starts `reach` early: a sound that is
        # late by d matches where the song is d earlier, lag = reach - d
        res.append((t, (reach - lag / sr) * 1000.0, float(corr[lag])))
    if not res:
        raise SystemExit('[offset] the film has no sound to compare')
    for t, ms, c in res:
        print(f'[offset] at {t:6.1f} s of the film: its sound sits {ms:+6.1f} ms from the song (correlation {c:.3f})')
    med = float(np.median([ms for _t, ms, _c in res]))
    print(f'[offset] median {med:+.1f} ms ({med * fps / 1000:+.2f} frames at {fps:g} fps; a frame is {1000 / fps:.1f} ms). '
          'Positive: the film\'s sound is late.')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--fps', type=float, default=24.0)
    ap.add_argument('--out', default=None, help='default: <song>_clock.json beside the song')
    ap.add_argument('--lyrics', default=None, help='lyrics text file: one sung line per line, [Section] headers')
    ap.add_argument('--vocal', default=None, help='the vocal stem for the lyric alignment (default: the song)')
    ap.add_argument('--model', default='medium', help="align_lyrics.py's Whisper model size")
    ap.add_argument('--downbeat', type=float, default=None, help='a moment on a bar line, in seconds')
    ap.add_argument('--beats-per-bar', type=int, default=4)
    ap.add_argument('--bpm', type=float, default=None, help="the tracker's starting tempo (default 120)")
    ap.add_argument('--segments', type=int, default=12)
    ap.add_argument('--repeat', nargs=2, type=float, metavar=('A', 'B'), help='find where [A, B] s comes back')
    ap.add_argument('--within', nargs=2, type=float, metavar=('C', 'D'), help='--repeat: search [C, D] s only')
    ap.add_argument('--offset', default=None, metavar='FILM', help="measure a film's sound against the song")
    ap.add_argument('--film-start', type=float, default=0.0, help='--offset: the song time of the film\'s start')
    a = ap.parse_args()
    if a.repeat:
        repeat(a)
    elif a.offset:
        offset(a)
    else:
        clock(a)


if __name__ == '__main__':
    main()
