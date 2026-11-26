"""Lip sync engine for VRM characters — generates per-frame viseme weights from audio.

Two methods, both giving one {aa, ih, ou, ee, oh} dict per video frame
(ceil(duration × fps) frames). numpy only, plus ffmpeg/ffprobe on PATH, so
Blender's own Python can run it too.

get_viseme_timeline(audio, fps) — frequency bands mapped to the 5 VRM visemes.
    Values 0..0.35 (drivers use inputMax 0.35). Works on any voice audio.

get_viseme_timeline_from_vocal(stem, words, fps) — a singing mouth from a
    vocal stem (a voice alone: a separated or recorded vocal track). Values
    0..1 (drivers use inputMax 1, as for voicebox visemes):
    - how open: the stem's own level, measured 4 times a frame, so a held
      note stays open and a breath between words closes the mouth;
    - which shape: the vowel of the word being sung then (words from
      align_lyrics.py), its last vowel carried while the voice goes on;
    - a hiss with no voice under it (s, sh, a stuttered "s-s-") shows the
      teeth as a narrow 'ih';
    - the lips shut on the frame before a word that starts with m, b or p;
    - where the voice sounds and no word was heard, the shape is read off
      the spectrum (dark vowels round, bright ones wide).

Usage:
    from lipsync import get_viseme_timeline

    # Get viseme weights for every frame of an audio file
    timeline = get_viseme_timeline("speech.wav", fps=30)
    # timeline[frame_index] = {"aa": 0.2, "ee": 0.0, "ih": 0.1, "oh": 0.0, "ou": 0.0}

    from lipsync import get_viseme_timeline_from_vocal
    import json
    lines = json.load(open("lyrics_aligned.json"))        # align_lyrics.py output
    timeline = get_viseme_timeline_from_vocal("vocals.wav", lines, fps=24)

    # Use with VRM mouth animation:
    # - Scale mouth-open vertices/blend shapes by the dominant viseme weight
    # - Or swap between mouth shape meshes based on which viseme is strongest
"""

import numpy as np
from pathlib import Path


def _load_audio_mono(path: str, target_sr: int = 22050) -> tuple[np.ndarray, int]:
    """Load audio file as mono float32 numpy array. Uses ffmpeg for format support."""
    import subprocess, struct

    # Every standard handle is given: a process started without a console
    # (Blender launched windowless by a runner) has none to hand down, and
    # Windows then refuses the child ("WinError 6: the handle is invalid").
    handles = dict(stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path)
    ]
    duration = float(subprocess.check_output(cmd, **handles).strip())

    cmd = [
        "ffmpeg", "-y", "-v", "quiet", "-i", str(path),
        "-ac", "1", "-ar", str(target_sr), "-f", "s16le", "-"
    ]
    raw = subprocess.check_output(cmd, **handles)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, target_sr


def _get_frequency_bands(fft_magnitudes: np.ndarray, sr: int, fft_size: int) -> dict:
    """Extract energy in 5 frequency bands from FFT magnitudes."""
    bin_width = sr / fft_size
    n_bins = len(fft_magnitudes)

    def energy(min_hz, max_hz):
        min_bin = int(min_hz / bin_width)
        max_bin = min(int(np.ceil(max_hz / bin_width)), n_bins - 1)
        if max_bin < min_bin:
            return 0.0
        # Convert to dB scale and normalize to 0-1 range to match
        # Web Audio API's getByteFrequencyData behavior.
        # Web Audio maps dB to 0-255 with minDecibels=-100, maxDecibels=-30.
        raw = float(np.mean(fft_magnitudes[min_bin:max_bin + 1]))
        if raw < 1e-10:
            return 0.0
        db = 20 * np.log10(raw + 1e-10)
        # Map from dB range [-100, -30] to [0, 1] (same as Web Audio default)
        normalized = (db + 100) / 70
        return float(np.clip(normalized, 0.0, 1.0))

    return {
        "sub": energy(20, 100),
        "low": energy(100, 400),
        "mid": energy(400, 2000),
        "high": energy(2000, 4000),
        "veryHigh": energy(4000, 8000),
    }


def _map_visemes(bands: dict) -> dict:
    """Map frequency bands to viseme weights (aa, ee, ih, oh, ou)."""
    total = sum(bands.values())
    if total < 0.08:
        return {"aa": 0, "ee": 0, "ih": 0, "oh": 0, "ou": 0}

    # Coefficients from the vtuber lip sync engine
    raw = {
        "aa": (bands["low"] * 0.5 + bands["mid"] * 0.5) * 0.7,
        "ee": (bands["mid"] * 0.5 + bands["high"] * 0.5) * 0.5,
        "ih": (bands["high"] * 0.6 + bands["veryHigh"] * 0.4) * 0.5,
        "oh": (bands["low"] * 0.6 + bands["sub"] * 0.4) * 0.6,
        "ou": (bands["sub"] * 0.5 + bands["low"] * 0.5) * 0.5,
    }

    # Pick dominant viseme, suppress others
    max_key = max(raw, key=raw.get)
    cap = 0.35

    return {
        k: min(cap, v * (1.0 if k == max_key else 0.3))
        for k, v in raw.items()
    }


def get_viseme_timeline(audio_path: str, fps: int = 30, fft_size: int = 1024) -> list[dict]:
    """Analyze an audio file and return viseme weights for each video frame.

    Args:
        audio_path: Path to audio file (wav, mp3, etc.)
        fps: Video frame rate
        fft_size: FFT window size (1024 matches the vtuber engine)

    Returns:
        List of dicts, one per frame: {"aa": float, "ee": float, "ih": float, "oh": float, "ou": float}
        Values range 0.0-0.35. The dominant viseme is strongest, others are suppressed.
    """
    samples, sr = _load_audio_mono(audio_path)
    duration = len(samples) / sr
    # ceil, like render_scene.mjs (totalFrames = Math.ceil(duration * fps)):
    # int() dropped the partial last frame, so timeline[frame] ran out one
    # frame early. The epsilon keeps an exact multiple (2.0 s @ 30) at 60.
    n_frames = int(np.ceil(duration * fps - 1e-6))
    hop = fft_size // 2  # 50% overlap

    # Smoothing (matches vtuber engine's smoothingTimeConstant = 0.3)
    smooth = 0.3
    prev_mags = np.zeros(fft_size // 2 + 1)

    timeline = []
    for frame_idx in range(n_frames):
        t = frame_idx / fps
        center_sample = int(t * sr)
        start = max(0, center_sample - fft_size // 2)
        end = start + fft_size

        if end > len(samples):
            chunk = np.pad(samples[start:], (0, end - len(samples)))
        else:
            chunk = samples[start:end]

        # Apply Hann window and FFT
        window = np.hanning(len(chunk))
        fft = np.fft.rfft(chunk * window)
        magnitudes = np.abs(fft) / fft_size

        # Exponential smoothing
        magnitudes = smooth * prev_mags + (1 - smooth) * magnitudes
        prev_mags = magnitudes.copy()

        bands = _get_frequency_bands(magnitudes, sr, fft_size)
        visemes = _map_visemes(bands)
        timeline.append(visemes)

    return timeline


def get_mouth_openness(visemes: dict) -> float:
    """Simple helper: convert viseme weights to a single mouth-open value (0-1).

    Useful when you just need "how open is the mouth" without full viseme shapes.
    aa/oh = wide open, ee/ih = slightly open, ou = pursed.
    """
    return min(1.0, (
        visemes["aa"] * 2.5 +
        visemes["oh"] * 2.0 +
        visemes["ee"] * 1.5 +
        visemes["ih"] * 1.5 +
        visemes["ou"] * 1.0
    ))


# --------------------------------------------------------------------------- #
# The vocal-stem method: a singing mouth from the voice alone.
# --------------------------------------------------------------------------- #
VISEMES = ("aa", "ih", "ou", "ee", "oh")

# The shapes are VRM's: aa = the "a" of "father", ih = the "i" of "see", ou =
# the "u" of "blue", ee = the "e" of "bed" and "made", oh = the "o" of "go"
# (voicebox's phoneme visemes use the same mapping).
# Words whose spelling misleads the vowel rules below. Each syllable is
# (mouth shape, how open 0..1, onset): onset "m" = the word starts with the
# lips shut (m, b, p), "w" = rounded lips first, "" = neither.
WORD_SHAPES = {
    "a": [("aa", 0.4, "")], "an": [("aa", 0.45, "")], "the": [("aa", 0.35, "")], "of": [("aa", 0.45, "")],
    "and": [("aa", 0.5, "")], "to": [("ou", 0.6, "")], "in": [("ih", 0.45, "")], "it": [("ih", 0.5, "")],
    "it's": [("ih", 0.5, "")], "is": [("ih", 0.5, "")], "this": [("ih", 0.7, "")], "that": [("aa", 0.7, "")],
    "that's": [("aa", 0.8, "")], "them": [("ee", 0.6, "")], "then": [("ee", 0.6, "")], "when": [("ee", 0.6, "w")],
    "by": [("aa", 0.75, "m")], "be": [("ih", 0.7, "m")], "me": [("ih", 0.8, "m")], "my": [("aa", 0.8, "m")],
    "we": [("ih", 0.75, "w")], "you": [("ou", 0.8, "")], "your": [("oh", 0.7, "")], "who": [("ou", 0.85, "")],
    "do": [("ou", 0.9, "")], "does": [("aa", 0.7, "")], "done": [("aa", 0.8, "")], "they": [("ee", 0.75, "")],
    "i": [("aa", 0.8, "")], "i'll": [("aa", 0.8, "")], "i'm": [("aa", 0.8, "")], "oh": [("oh", 1.0, "")],
    "all": [("oh", 0.9, "")], "are": [("aa", 0.8, "")], "were": [("ou", 0.6, "w")], "was": [("aa", 0.6, "w")],
    "what": [("aa", 0.7, "w")], "have": [("aa", 0.75, "")], "give": [("ih", 0.7, "")], "live": [("ih", 0.7, "")],
    "love": [("aa", 0.8, "")], "come": [("aa", 0.8, "")], "some": [("aa", 0.75, "")], "one": [("aa", 0.85, "w")],
    "once": [("aa", 0.8, "w")], "none": [("aa", 0.8, "")], "gone": [("oh", 0.8, "")], "said": [("ee", 0.65, "")],
    "says": [("ee", 0.65, "")], "say": [("ee", 0.75, "")], "eye": [("aa", 0.85, "")], "eyes": [("aa", 0.85, "")],
    "heart": [("aa", 0.85, "")], "our": [("aa", 0.8, "")], "hour": [("aa", 0.8, "")], "now": [("aa", 0.85, "")],
    "how": [("aa", 0.85, "")], "down": [("aa", 0.85, "")], "more": [("oh", 1.0, "m")], "four": [("oh", 0.9, "")],
    "door": [("oh", 0.9, "")], "floor": [("oh", 0.9, "")], "two": [("ou", 0.85, "")], "three": [("ih", 0.85, "")],
    "five": [("aa", 0.9, "")], "six": [("ih", 0.7, "")], "seven": [("ee", 0.75, ""), ("aa", 0.4, "")],
    "eight": [("ee", 0.85, "")], "nine": [("aa", 0.85, "")], "ten": [("ee", 0.7, "")],
    "hundred": [("aa", 0.75, ""), ("aa", 0.4, "")], "thousand": [("aa", 0.85, ""), ("aa", 0.4, "")],
    "million": [("ih", 0.7, "m"), ("aa", 0.4, "")], "another": [("aa", 0.55, ""), ("aa", 0.9, ""), ("ou", 0.5, "")],
    "body": [("aa", 0.8, "m"), ("ih", 0.5, "")], "every": [("ee", 0.75, ""), ("ih", 0.5, "")],
    "only": [("oh", 0.85, ""), ("ih", 0.5, "")], "quiet": [("aa", 0.8, "w"), ("aa", 0.45, "")],
    "word": [("ou", 0.6, "w")], "words": [("ou", 0.6, "w")], "work": [("ou", 0.6, "w")],
    "world": [("ou", 0.6, "w")], "well": [("ee", 0.7, "w")], "please": [("ih", 0.85, "m")],
    "people": [("ih", 0.8, "m"), ("aa", 0.4, "m")], "today": [("aa", 0.45, ""), ("ee", 0.9, "")],
    "water": [("oh", 0.8, "w"), ("ou", 0.4, "")], "here": [("ih", 0.75, "")], "there": [("ee", 0.75, "")],
    "where": [("ee", 0.75, "w")], "why": [("aa", 0.8, "w")], "up": [("aa", 0.6, "")],
}
_VOWEL_LETTERS = "aeiouy"
# the spelling's vowel groups, longest first, and the VRM shape each is sung with
_VOWEL_GROUPS = [("igh", "aa"), ("oo", "ou"), ("ou", "aa"), ("ow", "aa"), ("ew", "ou"), ("ue", "ou"), ("oa", "oh"),
                 ("oe", "oh"), ("au", "oh"), ("aw", "oh"), ("ai", "ee"), ("ay", "ee"), ("ei", "ee"), ("ey", "ee"),
                 ("ee", "ih"), ("ea", "ih"), ("ie", "ih"), ("oi", "oh"), ("oy", "oh"), ("a", "aa"), ("e", "ee"),
                 ("i", "ih"), ("o", "oh"), ("u", "aa"), ("y", "ih")]
# a vowel lengthened by a silent final e: made, time, home, tune, these
_LONG = {"a": "ee", "i": "aa", "o": "oh", "u": "ou", "e": "ih", "y": "aa"}


def _norm_word(word: str) -> str:
    import re
    return re.sub(r"[^a-z'\-]", "", word.lower().replace("’", "'"))


def word_syllables(word: str) -> list[tuple]:
    """[(shape, how open, onset)] for a sung word: WORD_SHAPES, else its spelling's vowel groups.

    The first syllable carries the word and the others are lighter; a silent
    final e lengthens the vowel before it (made, time, home; frames, times).
    """
    import re
    w = _norm_word(word)
    for k in (w, w[:-2] if w.endswith("'s") else w):
        if k in WORD_SHAPES:
            return list(WORD_SHAPES[k])
    s = re.sub(r"[^a-z]", "", w)
    if len(s) > 4 and s.endswith("es") and s[-3] not in _VOWEL_LETTERS:
        s = s[:-1]                                       # frames -> frame: the e is still silent
    elif len(s) > 4 and s.endswith("ed") and s[-3] not in _VOWEL_LETTERS + "td":
        s = s[:-2]                                       # walked, jumped: the -ed is no syllable
    long_ = len(s) > 2 and s.endswith("e") and s[-2] not in _VOWEL_LETTERS and any(c in _VOWEL_LETTERS for c in s[:-1])
    if long_:
        s = s[:-1]
    out, i, onset, letter = [], 0, "", ""
    while i < len(s):
        c = s[i]
        if c not in _VOWEL_LETTERS or (c == "y" and i == 0):
            # m, b and p shut the lips, w rounds them; a cluster after one (bl, pr) keeps it
            keep = onset if onset in ("m", "w") and i and s[i - 1] not in _VOWEL_LETTERS else ""
            onset = {"m": "m", "b": "m", "p": "m", "w": "w"}.get(c, keep)
            i += 1
            continue
        for g, shape in _VOWEL_GROUPS:
            if s.startswith(g, i):
                if g == "y" and i == len(s) - 1 and not out:
                    shape = "aa"                         # my, fly, why: a lone final y is the "ai" of "eye"
                elif g == "a" and (s.startswith(("lk", "ll"), i + 1) or (i and s[i - 1] == "w" and s.startswith("r", i + 1))):
                    shape = "oh"                         # walk, call, warm: the "aw" of "law"
                out.append([shape, 0.75, onset])
                letter = g if len(g) == 1 else ""
                i += len(g)
                onset = ""
                break
    if not out:
        out = [["ih", 0.4, onset]]
    if long_ and letter in _LONG:
        out[-1][0] = _LONG[letter]
    for k in range(1, len(out)):
        out[k][1] = 0.5
    return [tuple(x) for x in out]


def _word_list(words) -> list[tuple]:
    """align_lyrics.py's lines ({text, start, end, words: [...]}), a flat list of word
    dicts ({word|w|text, start|s|t0, end|e|t1}) or (word, start, end) tuples
    -> [(word, start, end)] sorted by start"""
    out = []
    for item in words or []:
        if isinstance(item, dict) and isinstance(item.get("words"), list):
            out += _word_list(item["words"])
            continue
        if isinstance(item, dict):
            w = item.get("word", item.get("w", item.get("text", "")))
            s = item.get("start", item.get("s", item.get("t0")))
            e = item.get("end", item.get("e", item.get("t1")))
        else:
            w, s, e = item
        if s is None or e is None or not str(w).strip():
            continue
        out.append((str(w).strip(), float(s), float(max(e, s))))
    return sorted(out, key=lambda x: x[1])


def _band_levels_db(samples: np.ndarray, sr: int, rate: float, bands) -> np.ndarray:
    """(bands x n) level in dB of each (lo, hi) Hz band, `rate` values a second:
    value i measures the 1/rate s from i/rate (a Hann window twice that long,
    centred on it). Relative levels only: the absolute scale is arbitrary."""
    n = int(len(samples) / sr * rate)
    hop = sr / rate
    win = max(16, int(round(2 * hop)))
    nfft = 1 << (win - 1).bit_length()
    w = np.hanning(win).astype(np.float32)
    pad = win
    y = np.pad(samples.astype(np.float32), (pad, pad))
    starts = ((np.arange(n) + 0.5) * hop).astype(np.int64) - win // 2 + pad
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    sel = [(freqs >= lo) & (freqs < hi) for lo, hi in bands]
    out = np.zeros((len(bands), n), np.float64)
    for a in range(0, n, 2048):                        # in blocks: a whole song at once is gigabytes
        idx = starts[a:a + 2048, None] + np.arange(win)[None, :]
        power = np.abs(np.fft.rfft(y[idx] * w, n=nfft, axis=1)) ** 2
        for k, s in enumerate(sel):
            out[k, a:a + len(idx)] = power[:, s].sum(axis=1)
    return 10.0 * np.log10(out + 1e-12)


def get_viseme_timeline_from_vocal(stem: str, words=None, fps: int = 30, sub: int = 4,
                                   syllables=None, sample_rate: int = 44100) -> list[dict]:
    """A singing mouth from a vocal stem: per-frame viseme weights, 0..1.

    Args:
        stem: the voice alone (a separated or recorded vocal; any format ffmpeg reads).
            A full mix would open the mouth on the drums: use the band method or a stem.
        words: the sung words with their times: align_lyrics.py's lines (their
            "words"), a flat list of {word, start, end}, or (word, start, end) tuples.
            None: every shape comes from the spectrum.
        fps: video frame rate
        sub: measurements per frame (the mouth's own clock is fps * sub a second)
        syllables: optional function word -> [(shape, how open 0..1, onset "m"|"w"|"")],
            in place of word_syllables (e.g. one built on a pronouncing dictionary)
        sample_rate: the stem is decoded at this rate (the hiss band reaches 11 kHz)

    Returns:
        ceil(duration × fps) dicts {"aa", "ih", "ou", "ee", "oh"}; their sum is at most 1.
        Drivers take these values as they are (inputMax 1, as for voicebox visemes).
        get_mouth_openness() is scaled for the 0..0.35 band method, so it saturates here.
    """
    samples, sr = _load_audio_mono(stem, target_sr=sample_rate)
    n_frames = int(np.ceil(len(samples) / sr * fps - 1e-6))
    rate = fps * sub
    voiced, hiss, low, mid = _band_levels_db(samples, sr, rate,
                                             ((120, 3200), (5000, 11000), (200, 900), (900, 2600)))
    n = len(voiced)
    if n == 0:
        return [dict.fromkeys(VISEMES, 0.0) for _ in range(n_frames)]
    # HOW OPEN: shut 30 dB under the loudest notes, wide open at the top; at once
    # on the way up, fully shut in about 70 ms on the way down
    top = np.percentile(voiced, 97)
    raw = np.clip((voiced - (top - 30.0)) / 31.0, 0.0, 1.0) ** 0.8
    fall = 14.4 / rate
    opened = np.empty(n)
    prev = 0.0
    for i in range(n):
        prev = raw[i] if raw[i] >= prev else max(raw[i], prev - fall)
        opened[i] = prev
    sounding = raw > 0.08
    hissing = (hiss > np.percentile(hiss, 90) - 6.0) & (raw < 0.25)
    # WHICH SHAPE: the vowel of the word being sung, its last vowel held on
    shape = np.full(n, -1, dtype=np.int64)
    amp = np.ones(n)
    shut = np.zeros(n, dtype=bool)
    syl_of = syllables or word_syllables
    ws = _word_list(words)
    for k, (w, s, e) in enumerate(ws):
        syl = syl_of(w) or [("aa", 0.7, "")]
        a = int(s * rate)
        e_ = max(a + 1, int(e * rate))
        nxt = ws[k + 1][1] if k + 1 < len(ws) else e + 2.0
        b = max(e_, int(min(nxt, e + 2.5) * rate))            # held for as long as the voice goes on
        for j, (sh, o, _onset) in enumerate(syl):
            s0 = max(0, a + (e_ - a) * j // len(syl))
            s1 = min(n, a + (e_ - a) * (j + 1) // len(syl) if j + 1 < len(syl) else b)
            if s1 > s0:
                shape[s0:s1] = VISEMES.index(sh)
                amp[s0:s1] = 0.55 + 0.45 * o
        if syl[0][2] == "m":                                    # the lips together on the frame before
            shut[max(0, a - sub + 1):max(0, min(n, a + 1))] = True
    # ... and where the voice sounds with no word: dark vowels round, bright ones wide
    free = (shape < 0) & sounding
    bright = (mid - low)[free]
    shape[free] = np.select([bright < -14, bright < -8, bright < -2],
                            [VISEMES.index("ou"), VISEMES.index("oh"), VISEMES.index("aa")], VISEMES.index("ee"))
    W = np.zeros((len(VISEMES), n))
    on = (shape >= 0) & ~hissing & ~shut
    W[shape[on], np.nonzero(on)[0]] = (opened * amp)[on]
    W[VISEMES.index("ih"), hissing & ~shut] = 0.3               # the teeth on a hiss
    # a vowel does not jump: each shape eased over 3 measurements; a frame is the mean of its own
    ker = np.array([0.25, 0.5, 0.25])
    W = np.stack([np.convolve(r, ker, mode="same") for r in W])
    frames = n // sub
    Wf = W[:, :frames * sub].reshape(len(VISEMES), frames, sub).mean(axis=2)
    tot = Wf.sum(axis=0)
    Wf = np.where(tot > 1.0, Wf / np.maximum(tot, 1e-6), Wf)
    out = [{v: round(float(Wf[k, f]), 4) for k, v in enumerate(VISEMES)} for f in range(min(frames, n_frames))]
    out += [dict.fromkeys(VISEMES, 0.0) for _ in range(n_frames - len(out))]
    return out
