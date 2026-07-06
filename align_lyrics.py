"""Align known lyrics to a vocal audio track.

Default method ("chunked"): split the vocal into chunks at silence gaps, run
Whisper TRANSCRIBE (word timestamps) on each chunk, stitch the heard words back
with each chunk's start offset, then sequence-match the heard words against the
KNOWN lyrics so the final per-line timestamps land on the real lyric text.

Why chunked-transcribe instead of one full-track forced align: Whisper operates
on ~30s windows internally, and on a full song the timing drifts and whole lines
get dropped. Chunking the vocal at natural silence gaps keeps each transcribe
pass inside a single clean window, and matching the heard stream back to the
known lyrics self-corrects across chunk seams (a word misheard in one chunk is
recovered by the sequence match). The old single-pass `model.align()` over the
whole track remains available as a fallback (method="align"), and the chunked
path auto-falls-back to it when match coverage is too low to trust.

Usage:
    python3 align_lyrics.py vocals.wav "First line\nSecond line\nThird line" [--model medium] [--output lyrics.json]
    python3 align_lyrics.py vocals.wav "..." --method align        # old single-pass forced align
    python3 align_lyrics.py vocals.wav "..." --chunk-sec 28 --top-db 30

    Or from Python:
        from align_lyrics import align_lyrics
        lines = align_lyrics("vocals.wav", "First line\\nSecond line")
        # Returns: [{"text": "First line", "start": 0.24, "end": 2.1, "words": [...]}, ...]

Outputs per-line AND per-word timestamps as JSON.
"""

import argparse
import json
import re
import sys


_WORD_RE = re.compile(r"[^a-z0-9']+")


def _norm(w: str) -> str:
    """Normalize a word for matching: lowercase, strip punctuation."""
    return _WORD_RE.sub("", w.lower())


# --------------------------------------------------------------------------- #
# Fallback: original single-pass forced alignment over the whole track.
# --------------------------------------------------------------------------- #
def _forced_align(model, audio_path: str, lyrics: str, language: str) -> list[dict]:
    result = model.align(audio_path, lyrics, language=language)
    lines = []
    for segment in result.segments:
        lines.append({
            "text": segment.text.strip(),
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "words": [
                {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                for w in segment.words
            ],
        })
    return lines


# --------------------------------------------------------------------------- #
# Chunking: cut the vocal at silence gaps, group into ~chunk_target_sec pieces.
# --------------------------------------------------------------------------- #
def _chunk_intervals(y, sr, top_db: float, chunk_target_sec: float):
    """Return a list of (start_sample, end_sample) chunks cut at silence gaps.

    librosa.effects.split gives non-silent intervals; we accrete them into
    groups up to ~chunk_target_sec, always cutting in a silence so no word is
    sliced. Any single non-silent run longer than 1.5x the target (e.g. a long
    sustained passage with no gap) is force-split so a chunk never blows past
    Whisper's clean window.
    """
    import librosa

    intervals = librosa.effects.split(y, top_db=top_db)
    if len(intervals) == 0:
        return [(0, len(y))]

    target = int(chunk_target_sec * sr)
    hard_max = int(1.5 * target)
    pad = int(0.15 * sr)

    chunks = []
    cur_start = None
    cur_end = None
    for (s, e) in intervals:
        # Force-split an over-long single run.
        if e - s > hard_max:
            if cur_start is not None:
                chunks.append((cur_start, cur_end))
                cur_start = None
            p = s
            while p < e:
                chunks.append((p, min(p + target, e)))
                p += target
            continue
        if cur_start is None:
            cur_start, cur_end = s, e
        elif e - cur_start <= target:
            cur_end = e
        else:
            chunks.append((cur_start, cur_end))
            cur_start, cur_end = s, e
    if cur_start is not None:
        chunks.append((cur_start, cur_end))

    # Pad each chunk slightly so transcription has lead-in/out context.
    padded = []
    for (s, e) in chunks:
        padded.append((max(0, s - pad), min(len(y), e + pad)))
    return padded


def _transcribe_chunks(model, y, sr, chunks, language):
    """Transcribe each chunk, offset word timestamps back to global time.

    Returns a flat list of heard words: {"word", "start", "end"} in global
    seconds, sorted by start.
    """
    heard = []
    for (cs, ce) in chunks:
        seg = y[cs:ce]
        if len(seg) < int(0.1 * sr):
            continue
        offset = cs / sr
        result = model.transcribe(
            seg,
            language=language,
            word_timestamps=True,
            verbose=None,
        )
        # stable_whisper result.segments[*].words[*].(word,start,end)
        segments = getattr(result, "segments", None)
        if segments is None and isinstance(result, dict):
            segments = result.get("segments", [])
        for s in segments or []:
            words = getattr(s, "words", None)
            if words is None and isinstance(s, dict):
                words = s.get("words", [])
            for w in words or []:
                wt = getattr(w, "word", None)
                ws = getattr(w, "start", None)
                we = getattr(w, "end", None)
                if wt is None and isinstance(w, dict):
                    wt, ws, we = w.get("word"), w.get("start"), w.get("end")
                if wt is None or ws is None or we is None:
                    continue
                heard.append({
                    "word": wt.strip(),
                    "start": float(ws) + offset,
                    "end": float(we) + offset,
                })
    heard.sort(key=lambda x: x["start"])
    return heard


# --------------------------------------------------------------------------- #
# Match: align the heard word stream to the KNOWN lyrics (difflib / DTW-style).
# --------------------------------------------------------------------------- #
def _match_lyrics_to_heard(lyric_lines, heard):
    """Sequence-match known lyric words to heard words; build per-line timing.

    Uses difflib.SequenceMatcher over normalized word tokens. Matched ("equal")
    blocks pin known-word timestamps to the heard timestamps; unmatched known
    words are interpolated between their nearest matched neighbours. Then words
    are rolled up into the original lyric lines.

    Returns (lines, coverage) where coverage is the fraction of known words that
    got a real (matched) timestamp.
    """
    from difflib import SequenceMatcher

    # Flatten known lyrics to words, remembering which line each belongs to.
    known_words = []          # normalized token
    known_disp = []           # display token (original)
    known_line_of = []        # line index per word
    for li, line in enumerate(lyric_lines):
        for tok in line.split():
            n = _norm(tok)
            if not n:
                continue
            known_words.append(n)
            known_disp.append(tok)
            known_line_of.append(li)

    heard_norm = [_norm(h["word"]) for h in heard]

    # word-level timestamps for known words; None until assigned.
    n_known = len(known_words)
    w_start = [None] * n_known
    w_end = [None] * n_known
    matched = [False] * n_known

    if n_known and heard:
        sm = SequenceMatcher(a=known_words, b=heard_norm, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    w_start[i1 + k] = heard[j1 + k]["start"]
                    w_end[i1 + k] = heard[j1 + k]["end"]
                    matched[i1 + k] = True

    coverage = (sum(matched) / n_known) if n_known else 0.0

    # Interpolate timestamps for unmatched known words between matched anchors.
    def _interp():
        # forward-fill anchors
        last_idx = None
        for i in range(n_known):
            if matched[i]:
                if last_idx is not None and i - last_idx > 1:
                    # distribute between last_idx and i
                    t0 = w_end[last_idx]
                    t1 = w_start[i]
                    gap = i - last_idx
                    for k in range(1, gap):
                        frac = k / gap
                        w_start[last_idx + k] = t0 + (t1 - t0) * frac
                        w_end[last_idx + k] = t0 + (t1 - t0) * ((k + 0.8) / gap)
                last_idx = i
        # leading unmatched (before first anchor)
        first = next((i for i in range(n_known) if matched[i]), None)
        if first is not None and first > 0:
            t1 = w_start[first]
            for k in range(first):
                frac = (k + 1) / (first + 1)
                w_start[k] = max(0.0, t1 - (first - k) * 0.3)
                w_end[k] = w_start[k] + 0.25
        # trailing unmatched (after last anchor)
        last = next((i for i in range(n_known - 1, -1, -1) if matched[i]), None)
        if last is not None and last < n_known - 1:
            t0 = w_end[last]
            for k in range(last + 1, n_known):
                w_start[k] = t0 + (k - last) * 0.3
                w_end[k] = w_start[k] + 0.25

    _interp()

    # Roll up words into lines.
    lines = []
    for li, line in enumerate(lyric_lines):
        idxs = [i for i in range(n_known) if known_line_of[i] == li]
        words_out = []
        for i in idxs:
            s = w_start[i] if w_start[i] is not None else 0.0
            e = w_end[i] if w_end[i] is not None else s + 0.25
            words_out.append({
                "word": known_disp[i],
                "start": round(float(s), 3),
                "end": round(float(e), 3),
            })
        if words_out:
            l_start = min(w["start"] for w in words_out)
            l_end = max(w["end"] for w in words_out)
        else:
            # Empty/blank lyric line — give it zero-length placeholder timing
            # anchored to the previous line's end (or 0).
            l_start = lines[-1]["end"] if lines else 0.0
            l_end = l_start
        lines.append({
            "text": line.strip(),
            "start": round(float(l_start), 3),
            "end": round(float(l_end), 3),
            "words": words_out,
        })

    # Enforce monotonic non-overlapping line starts (interp can produce ties).
    for i in range(1, len(lines)):
        if lines[i]["start"] < lines[i - 1]["start"]:
            lines[i]["start"] = lines[i - 1]["start"]
            if lines[i]["end"] < lines[i]["start"]:
                lines[i]["end"] = lines[i]["start"]

    return lines, coverage


# --------------------------------------------------------------------------- #
# Public entry point.
# --------------------------------------------------------------------------- #
def align_lyrics(
    audio_path: str,
    lyrics: str,
    model_size: str = "medium",
    language: str = "en",
    method: str = "chunked",
    chunk_target_sec: float = 28.0,
    top_db: float = 30.0,
    min_coverage: float = 0.5,
) -> list[dict]:
    """Align known lyrics to a vocal audio track.

    Args:
        audio_path: Path to isolated vocal WAV file
        lyrics: Full lyrics text (newline-separated lines)
        model_size: Whisper model size — "medium" is the default (good balance of
            accuracy and speed on GPU); use "base" to save ~1.4 GB if you need
            fast CPU-only alignment, or "large-v3" for critical music videos
            where word-level timing must be perfect
        language: Language code
        method: "chunked" (silence-split transcribe + sequence-match to known
            lyrics — robust on full songs) or "align" (legacy single-pass forced
            alignment over the whole track)
        chunk_target_sec: Target seconds per chunk for the chunked method
        top_db: Silence threshold (dB below peak) for the chunk splitter; higher
            = treats quieter passages as non-silent (fewer, longer chunks)
        min_coverage: If the chunked match assigns real timestamps to fewer than
            this fraction of the known words, fall back to single-pass align()

    Returns:
        List of line dicts: {text, start, end, words: [{word, start, end}, ...]}
    """
    import stable_whisper

    model = stable_whisper.load_model(model_size)

    lyric_lines = [ln for ln in lyrics.split("\n")]
    # Drop trailing blank lines but keep internal ones (verse spacing).
    while lyric_lines and not lyric_lines[-1].strip():
        lyric_lines.pop()

    if method == "align":
        return _forced_align(model, audio_path, lyrics, language)

    # Chunked transcribe + match.
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        chunks = _chunk_intervals(y, sr, top_db=top_db, chunk_target_sec=chunk_target_sec)
        heard = _transcribe_chunks(model, y, sr, chunks, language)
        lines, coverage = _match_lyrics_to_heard(lyric_lines, heard)
        sys.stderr.write(
            f"[align_lyrics] chunked: {len(chunks)} chunks, {len(heard)} heard words, "
            f"coverage={coverage:.2f}\n"
        )
        if coverage < min_coverage:
            sys.stderr.write(
                f"[align_lyrics] coverage {coverage:.2f} < {min_coverage}; "
                f"falling back to single-pass forced align\n"
            )
            return _forced_align(model, audio_path, lyrics, language)
        return lines
    except Exception as e:
        sys.stderr.write(
            f"[align_lyrics] chunked method failed ({e!r}); "
            f"falling back to single-pass forced align\n"
        )
        return _forced_align(model, audio_path, lyrics, language)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Align lyrics to vocal audio")
    parser.add_argument("audio", help="Path to vocal WAV file")
    parser.add_argument("lyrics", help="Lyrics text (newlines between lines, or use \\n)")
    parser.add_argument("--model", default="medium", help="Whisper model size (base/medium/large-v3)")
    parser.add_argument("--output", default="lyrics_aligned.json", help="Output JSON path")
    parser.add_argument("--language", default="en")
    parser.add_argument("--method", default="chunked", choices=["chunked", "align"],
                        help="chunked = silence-split transcribe + match (robust on full songs); "
                             "align = legacy single-pass forced alignment")
    parser.add_argument("--chunk-sec", type=float, default=28.0,
                        help="Target seconds per chunk (chunked method)")
    parser.add_argument("--top-db", type=float, default=30.0,
                        help="Silence threshold in dB below peak for the chunk splitter")
    args = parser.parse_args()

    # Handle escaped newlines from command line
    lyrics_text = args.lyrics.replace("\\n", "\n")

    lines = align_lyrics(
        args.audio,
        lyrics_text,
        model_size=args.model,
        language=args.language,
        method=args.method,
        chunk_target_sec=args.chunk_sec,
        top_db=args.top_db,
    )

    with open(args.output, "w") as f:
        json.dump(lines, f, indent=2)

    print(f"Aligned {len(lines)} lines → {args.output}")
    for line in lines:
        print(f"  [{line['start']:.1f}s - {line['end']:.1f}s] {line['text']}")
