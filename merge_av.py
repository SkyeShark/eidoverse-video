"""Safely mux a rendered video with its mixed audio.

WHY THIS EXISTS — the freeze bug:
    The old documented merge used
        -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=300[v]" -shortest
    which CLONES the last video frame for up to 300s to backfill the audio
    length. So any time the video came in short — a render that died partway,
    or the wrong file fed in (a 1-frame test_frame) — the last frame got
    stretched into a multi-second-to-45s FROZEN video. It then passed the
    duration/stream QA (duration matched, both streams present) and shipped.
    We kept putting out 45-second frozen-frame videos.

THE RULE:
    Render slightly LONGER than the audio, then trim to the audio with
    -shortest. Never clone-pad a real gap. If the video is materially shorter
    than the audio, the render is broken — re-render at the right duration.
    This tool enforces that: it refuses to pad more than --tol seconds (a
    rounding cushion so the narration's last word isn't clipped) and exits
    non-zero with a clear message telling you to re-render.

Usage:
    python merge_av.py --video scene_video_only.mp4 --audio mixed_audio.wav \
        --out scene_final.mp4 [--tol 1.0]
"""
import argparse
import subprocess
import sys


def _duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float((out.stdout or "").strip())
    except ValueError:
        raise SystemExit(f"merge_av: could not read duration of {path}: {out.stderr.strip()[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tol", type=float, default=1.0,
                    help="max seconds the video may be padded to reach the audio "
                         "(rounding cushion only — NOT a backfill for a short render)")
    args = ap.parse_args()

    v = _duration(args.video)
    a = _duration(args.audio)
    gap = a - v
    print(f"merge_av: video={v:.2f}s  audio={a:.2f}s  gap={gap:+.2f}s")

    if gap > args.tol:
        # The video is meaningfully shorter than the audio. Padding here would
        # freeze the last frame for `gap` seconds — the exact bug. Refuse.
        sys.stderr.write(
            f"\nmerge_av: REFUSING TO MERGE — video ({v:.2f}s) is {gap:.2f}s "
            f"shorter than audio ({a:.2f}s).\n"
            f"Clone-padding that gap would produce a FROZEN-FRAME video.\n"
            f"Your render is too short: re-render the scene with duration >= "
            f"{a:.1f}s (render a bit LONGER than the audio; -shortest trims the "
            f"tail). Do NOT pad to hide a short render.\n"
        )
        return 2

    # Safe to merge. If the video is longer, -shortest trims it to the audio.
    # If it's shorter by <= tol, pad only that tiny cushion so the last word of
    # narration isn't clipped, then -shortest trims to the audio.
    # STREAM-COPY the video whenever possible: muxing audio needs no video
    # re-encode, and h264_nvenc at its default rate control was silently
    # squashing 8Mbps masters down to ~2Mbps in the mux step. Only the
    # tpad path (filtering = must re-encode) transcodes, at high bitrate.
    if gap > 0:
        vfilter = ["-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={args.tol}[v]",
                   "-map", "[v]", "-map", "1:a"]
        vcodec = ["-c:v", "h264_nvenc", "-b:v", "8000k", "-maxrate", "10000k", "-bufsize", "16000k"]
    else:
        vfilter = ["-map", "0:v", "-map", "1:a"]
        vcodec = ["-c:v", "copy"]

    cmd = ["ffmpeg", "-y", "-i", args.video, "-i", args.audio,
           *vfilter, *vcodec, "-c:a", "aac", "-shortest", args.out]
    print("merge_av:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        return r.returncode

    final = _duration(args.out)
    print(f"merge_av: wrote {args.out} ({final:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
