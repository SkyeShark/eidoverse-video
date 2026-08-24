# /// script
# dependencies = ["edge-tts"]
# ///
"""Synthesize narration with edge-tts and emit word-timed caption JSON from the same stream.

Usage: uv run tts_captions.py narration.json --out-dir work/<id>/audio
       narration.json: [{"text": "...", "at": 1.0, "voice": "en-US-ChristopherNeural"}, ...]
"""

import argparse
import asyncio
import json
import pathlib

import edge_tts

DEFAULT_VOICE = "en-US-ChristopherNeural"
TRAILING_PUNCTUATION = '.,!?;:)…”’"'


def restore_punctuation(text: str, words: list[dict]) -> list[dict]:
    cursor = 0
    for w in words:
        i = text.find(w["text"], cursor)
        if i == -1:
            continue
        j = i + len(w["text"])
        while j < len(text) and text[j] in TRAILING_PUNCTUATION:
            j += 1
        w["text"] = text[i:j]
        cursor = j
    return words


async def synthesize_line(line: dict, mp3_path: pathlib.Path) -> list[dict]:
    tts = edge_tts.Communicate(
        line["text"],
        line.get("voice", DEFAULT_VOICE),
        boundary="WordBoundary",
    )
    at_ms = round(float(line.get("at", 0)) * 1000)
    words = []
    with open(mp3_path, "wb") as f:
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = at_ms + chunk["offset"] // 10_000
                words.append({
                    "text": chunk["text"],
                    "startMs": start,
                    "endMs": start + chunk["duration"] // 10_000,
                })
    return restore_punctuation(line["text"], words)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("narration", help="JSON list of {text, at, voice?}")
    parser.add_argument("--out-dir", default=".", help="Output directory")
    args = parser.parse_args()

    lines = json.loads(pathlib.Path(args.narration).read_text())
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_words = []
    for i, line in enumerate(lines, 1):
        mp3_path = out_dir / f"line_{i:02d}.mp3"
        all_words.extend(await synthesize_line(line, mp3_path))
        print(f"line_{i:02d}.mp3  at={line.get('at', 0)}s  {line['text'][:50]}")

    captions_path = out_dir / "captions.json"
    captions_path.write_text(json.dumps(all_words, indent=1))
    print(f"{captions_path}  ({len(all_words)} words)")


if __name__ == "__main__":
    asyncio.run(main())
