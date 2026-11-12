"""Frames and film seconds, and the timing files the media tools read. No bpy needed.

The film convention (the toolkit's Blender films): frame 1 is 0 s. A scene may move that with a custom property
``scene['eido_frame0']``; chunked renders change ``scene.frame_start``, so time is never measured from it.

    tb = Timebase.of(bpy.context.scene)      # or Timebase(fps=24)
    t = tb.t(frame)                          # film seconds at a frame
    f = tb.frame(t)                          # the (fractional) frame at film seconds t
    lines = load_lines('work/x/lyrics_aligned.json')   # [{text, start, end, words: [{w, s, e}]}]
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Timebase:
    fps: float = 24.0
    frame0: int = 1

    @classmethod
    def of(cls, scene):
        r = scene.render
        return cls(fps=r.fps / r.fps_base, frame0=int(scene.get('eido_frame0', 1)))

    def t(self, frame):
        """Film seconds at a (possibly fractional) frame."""
        return (frame - self.frame0) / self.fps

    def frame(self, t):
        """The fractional frame at film seconds t."""
        return self.frame0 + t * self.fps

    def frame_round(self, t):
        return int(round(self.frame(t)))

    def frames(self, t0, t1):
        """Every whole frame whose time lies in [t0, t1]."""
        return range(int(math.ceil(self.frame(t0) - 1e-9)), int(math.floor(self.frame(t1) + 1e-9)) + 1)


def _num(d, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return float(d[k])
    return None


def load_lines(src):
    """Lyric or narration lines in one shape, from any of the timing files the toolkit writes:

    - align_lyrics.py output: [{text, start, end, words: [{word, start, end}]}]
    - captions: [{text, t0, t1, words: [{w, t0, t1}]}]
    - voicebox Sung.lines: [{text, t0, t1}]
    - parole timing: [{text, start, end, words: [{w, s, e}]}] or {lines: [...]}
    - a timeline object {captions: [...]} (preview_screens.mjs's --lyrics form)

    Returns [{text, start, end, words: [{w, s, e}], **other keys kept}] sorted by start.
    """
    if isinstance(src, (str, Path)):
        src = json.loads(Path(src).read_text(encoding='utf-8'))
    if isinstance(src, dict):
        src = src.get('lines') or src.get('captions') or []
    out = []
    for raw in src:
        start = _num(raw, 'start', 't0')
        end = _num(raw, 'end', 't1')
        if start is None:
            continue
        words = []
        for w in raw.get('words') or []:
            ws = _num(w, 's', 'start', 't0')
            we = _num(w, 'e', 'end', 't1')
            text = str(w.get('w', w.get('word', ''))).strip()
            if ws is not None and text:
                words.append({'w': text, 's': ws, 'e': we if we is not None else ws})
        line = {k: v for k, v in raw.items() if k not in ('start', 'end', 't0', 't1', 'words')}
        line.update(text=str(raw.get('text', '')).strip(), start=start,
                    end=end if end is not None else (words[-1]['e'] if words else start), words=words)
        out.append(line)
    out.sort(key=lambda l: l['start'])
    return out


def text_at(lines, t, pre=0.0, post=0.0):
    """The line on screen at t (start - pre <= t < end + post), or None."""
    for l in lines:
        if l['start'] - pre <= t < l['end'] + post:
            return l
    return None
