"""Lip sync engine for VRM characters — generates per-frame viseme weights from audio.

Analyzes audio frequency bands and maps them to 5 VRM visemes (aa, ih, ou, ee, oh).

Usage:
    from lipsync import get_viseme_timeline

    # Get viseme weights for every frame of an audio file
    timeline = get_viseme_timeline("speech.wav", fps=30)
    # timeline[frame_index] = {"aa": 0.2, "ee": 0.0, "ih": 0.1, "oh": 0.0, "ou": 0.0}

    # Use with VRM mouth animation:
    # - Scale mouth-open vertices/blend shapes by the dominant viseme weight
    # - Or swap between mouth shape meshes based on which viseme is strongest
"""

import numpy as np
from pathlib import Path


def _load_audio_mono(path: str, target_sr: int = 22050) -> tuple[np.ndarray, int]:
    """Load audio file as mono float32 numpy array. Uses ffmpeg for format support."""
    import subprocess, struct

    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path)
    ]
    duration = float(subprocess.check_output(cmd).strip())

    cmd = [
        "ffmpeg", "-y", "-v", "quiet", "-i", str(path),
        "-ac", "1", "-ar", str(target_sr), "-f", "s16le", "-"
    ]
    raw = subprocess.check_output(cmd)
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
    n_frames = int(duration * fps)
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
