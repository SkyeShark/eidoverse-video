#!/usr/bin/env python3
"""Cyborg voice filter + AI-glitch stutter (e.g. "I am g-g-g-going to the store").

Builds on cyborg_voice.py: applies the same echo + pitched-undertone tone
filter, then randomly inserts repeated short slices at the start of some
words so the resulting speech sounds like a stuttering AI. Use this on
SPOKEN audio (TTS narration, dialogue) — NOT on sung vocals, where the
stutters mangle the melody.

Algorithm:
1. Apply cyborg tone filter (echo + pitched undertone) via cyborg_voice
2. Detect word-start positions in the result with librosa onset detection
3. For a random subset (~stutter_rate of them), copy a 50-90ms slice from
   immediately after the onset and paste it 2-4 times back-to-back at the
   onset position, creating the "g-g-g-going" effect
4. Write the result to output_path

Usage:
    python3 cyborg_stutter.py input.wav output.wav

    from cyborg_stutter import cyborg_filter
    cyborg_filter("tts.wav", "stuttered.wav", stutter_rate=0.3)

The stutter logic uses NUMPY arrays directly (read with scipy.io.wavfile)
so there's no extra subprocess after the initial ffmpeg tone pass.
"""
import os
import random
import subprocess
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

from cyborg_voice import cyborg_tone


def _detect_word_onsets(audio: np.ndarray, sr: int) -> list:
    """Return sample indices where words probably begin.

    Uses librosa onset detection if available; falls back to a simple
    energy-rise heuristic so the script still runs without librosa.
    """
    try:
        import librosa
        # backtrack=True snaps each onset back to the nearest local energy
        # minimum, which lines up well with the actual word START rather
        # than the peak — important for stuttering, which needs to splice
        # in BEFORE the word's first phoneme.
        onset_frames = librosa.onset.onset_detect(
            y=audio.astype(np.float32),
            sr=sr,
            backtrack=True,
            units="samples",
        )
        return list(onset_frames)
    except ImportError:
        pass

    # Fallback: short-time RMS, find positions where RMS jumps from low → high
    win = max(1, sr // 100)  # 10ms window
    if len(audio) < win * 2:
        return []
    rms = np.sqrt(np.convolve(audio.astype(np.float32) ** 2, np.ones(win) / win, mode="same"))
    threshold = rms.max() * 0.18
    onsets = []
    in_silence = True
    for i in range(0, len(rms), win):
        if in_silence and rms[i] > threshold:
            onsets.append(i)
            in_silence = False
        elif not in_silence and rms[i] < threshold * 0.5:
            in_silence = True
    return onsets


def _apply_stutter(
    audio: np.ndarray,
    sr: int,
    stutter_rate: float = 0.07,
    repeats_range: tuple = (2, 3),
    slice_ms_range: tuple = (45, 90),
    min_word_gap: int = 12,
    seed: int | None = None,
) -> np.ndarray:
    """Insert g-g-g-going style stutters at random word onsets.

    stutter_rate    — fraction of detected word onsets to stutter (0..1).
                       Default 0.07 = roughly 1 stutter per 14 onsets.
    repeats_range   — (min, max) extra repetitions of the slice.
    slice_ms_range  — (min, max) length of the slice copied per stutter.
    min_word_gap    — minimum number of OTHER onsets between any two
                       stuttered onsets. Default 12 keeps stutters sparse
                       so they read as occasional AI glitches, not a
                       speech impediment.
    seed            — RNG seed for reproducible stutters (None = random).
    """
    rng = random.Random(seed)
    onsets = _detect_word_onsets(audio, sr)
    if not onsets:
        return audio

    # Walk the onsets in random order and accept each one only if it is at
    # least `min_word_gap` ONSETS away from every already-accepted onset.
    # Indices into the onset list, NOT samples — that's what makes it a
    # word-distance gap rather than a time gap.
    target_count = max(1, int(len(onsets) * stutter_rate))
    candidate_indices = list(range(len(onsets)))
    rng.shuffle(candidate_indices)
    chosen_indices: list[int] = []
    for idx in candidate_indices:
        if all(abs(idx - c) >= min_word_gap for c in chosen_indices):
            chosen_indices.append(idx)
        if len(chosen_indices) >= target_count:
            break
    chosen_indices.sort()
    chosen = [onsets[i] for i in chosen_indices]

    out = audio.copy()
    # Insert from the END so earlier offsets don't shift
    for onset in reversed(chosen):
        slice_ms = rng.randint(*slice_ms_range)
        slice_len = int(sr * slice_ms / 1000)
        if onset + slice_len >= len(out):
            continue
        repeats = rng.randint(*repeats_range)
        slice_data = out[onset:onset + slice_len].copy()
        # Slight fade so each repeat doesn't click into the next
        fade_len = max(1, slice_len // 10)
        fade_out = np.linspace(1.0, 0.7, fade_len)
        slice_data[-fade_len:] = (slice_data[-fade_len:] * fade_out).astype(slice_data.dtype)
        # Build the stutter block: repeats copies of the slice, then the rest
        stutter_block = np.tile(slice_data, repeats)
        out = np.concatenate([out[:onset], stutter_block, out[onset:]])
    return out


def cyborg_filter(
    input_path: str,
    output_path: str,
    stutter_rate: float = 0.07,
    sample_rate: int = 44100,
    seed: int | None = None,
) -> None:
    """Run the cyborg tone filter then add AI-glitch stutters."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tone_path = tmp.name
    try:
        cyborg_tone(input_path, tone_path, sample_rate=sample_rate, mono=True)
        sr, audio = wavfile.read(tone_path)
        if audio.ndim > 1:
            audio = audio[:, 0]
        stuttered = _apply_stutter(audio, sr, stutter_rate=stutter_rate, seed=seed)
        wavfile.write(output_path, sr, stuttered.astype(audio.dtype))
    finally:
        try:
            os.remove(tone_path)
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 cyborg_stutter.py input.wav output.wav [stutter_rate]")
        sys.exit(1)
    rate = float(sys.argv[3]) if len(sys.argv) > 3 else 0.18
    cyborg_filter(sys.argv[1], sys.argv[2], stutter_rate=rate)
    print(f"Wrote: {sys.argv[2]}")
