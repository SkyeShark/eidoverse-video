"""Audio I/O and small analysis helpers (spectrogram images, ASR intelligibility)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import soundfile as sf


def write_wav(path, y, sr, subtype='PCM_24'):
    """Atomic: renders to <stem>.part<suffix>, then renames, so a player that opens the file
    mid-write never sees a header whose sizes aren't final yet (Windows reports that as an
    unsupported format)."""
    y = np.asarray(y, dtype=np.float64)
    path = Path(path)
    tmp = path.with_name(path.stem + '.part' + path.suffix)
    sf.write(str(tmp), y, int(sr), subtype=subtype)
    os.replace(tmp, path)


def read_wav(path, mono=True):
    y, sr = sf.read(str(path), always_2d=False)
    if mono and y.ndim == 2:
        y = y.mean(axis=1)
    return y, sr


def spectrogram_png(y, sr, path, title='', fmax=10000, n_fft=2048, hop=256, width=1600, height=600,
                    marks=None):
    """Save a log-magnitude spectrogram as a PNG (for reading formants and consonants by eye)."""
    from scipy.signal import stft
    from PIL import Image, ImageDraw
    f, t, Z = stft(y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    S = S[f <= fmax]
    S = np.clip((S - (S.max() - 80)) / 80, 0, 1)
    img = (255 * (1 - S[::-1])).astype(np.uint8)
    im = Image.fromarray(img).resize((width, height), Image.BILINEAR).convert('RGB')
    d = ImageDraw.Draw(im)
    for khz in range(1, int(fmax / 1000) + 1):
        yy = height - int(khz * 1000 / fmax * height)
        d.line([(0, yy), (12, yy)], fill=(200, 0, 0))
        d.text((14, yy - 6), f'{khz}k', fill=(200, 0, 0))
    if marks:
        dur = len(y) / sr
        for (tm, label) in marks:
            x = int(tm / dur * width)
            d.line([(x, 0), (x, height)], fill=(0, 120, 255))
            d.text((x + 2, 2), label, fill=(0, 90, 200))
    if title:
        d.text((40, 4), title, fill=(0, 0, 0))
    im.save(path)
    return path


_WHISPER = {}


def transcribe(path, model='small', language='en', initial_prompt=None):
    """Whisper transcription — used as an intelligibility meter for synthesized voices."""
    import whisper
    if model not in _WHISPER:
        _WHISPER[model] = whisper.load_model(model)
    r = _WHISPER[model].transcribe(str(path), language=language, fp16=False, temperature=0.0,
                                   condition_on_previous_text=False, initial_prompt=initial_prompt)
    return r['text'].strip()


def word_error_rate(ref: str, hyp: str) -> float:
    import re
    norm = lambda s: re.sub(r"[^a-z' ]", ' ', s.lower()).split()
    r, h = norm(ref), norm(hyp)
    d = np.zeros((len(r) + 1, len(h) + 1), dtype=int)
    d[:, 0] = np.arange(len(r) + 1)
    d[0, :] = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r), len(h)] / max(1, len(r))
