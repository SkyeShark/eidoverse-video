#!/usr/bin/env python3
"""Apply the cyborg voice filter to an audio file.

Mixes the original (with echo) and a pitch-shifted copy back together,
producing a doubled / metallic / "AI speaking through static" tone. Use
this on any voice track — TTS narration, character dialogue, sung vocals.
Tone-only, no stutter, so it's safe for music_video sung vocals (use
cyborg_stutter.py for spoken TTS where AI-glitch stutters add character).

Filter chain:
    [0:a]aecho=0.8:0.88:60:0.4[echo];
    [0:a]rubberband=pitch=0.75[pitched];
    [echo][pitched]amix=inputs=2:weights=1 0.5

Usage:
    python3 cyborg_voice.py input.wav output.wav

    from cyborg_voice import cyborg_tone
    cyborg_tone("vocals.wav", "cyborg_vocals.wav")
"""
import subprocess
import sys


CYBORG_FILTER = (
    "[0:a]aecho=0.8:0.88:60:0.4[echo];"
    "[0:a]rubberband=pitch=0.75[pitched];"
    "[echo][pitched]amix=inputs=2:weights=1 0.5"
)


def cyborg_tone(input_path: str, output_path: str, sample_rate: int = 44100, mono: bool = True) -> None:
    """Apply just the cyborg tone filter (echo + pitched undertone). No stutter."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", CYBORG_FILTER,
        "-ar", str(sample_rate),
        "-ac", "1" if mono else "2",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"cyborg_tone: ffmpeg failed (exit {proc.returncode})\n"
            f"stderr (last 800 chars):\n{proc.stderr[-800:]}"
        )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 cyborg_voice.py input.wav output.wav")
        sys.exit(1)
    cyborg_tone(sys.argv[1], sys.argv[2])
    print(f"Wrote: {sys.argv[2]}")
