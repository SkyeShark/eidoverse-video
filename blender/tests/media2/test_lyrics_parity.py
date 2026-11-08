"""Parity: media.lyrics.LyricRenderer against the original eidoverse/lyric_renderer.py, pixel for pixel (no Blender).

    python -B blender/tests/media2/test_lyrics_parity.py

The original names its fonts by Docker paths (/usr/share/fonts/truetype/custom/...); for the comparison its table is
pointed at the same bundled files the port resolves the names to, nothing else is touched. Both renderers read
DAISY's lines (the timeline's captions written as align_lyrics.py output, {text, start, end}); for each option set
below, the display timing must be identical and every compared frame identical to the byte, on a PIL frame and on a
numpy frame. Writes out/lyrics/parity_<case>.png (the port's frame) for a look. Prints PASS/FAIL lines.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT / 'blender'))
from eidoblend.media import lyrics  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = HERE / 'out' / 'lyrics'
TIMELINE = HERE / 'out' / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def original():
    spec = importlib.util.spec_from_file_location('lyric_renderer_original', WT / 'eidoverse' / 'lyric_renderer.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for k in list(m._FONT_PATHS):
        f = lyrics.font_file(k)
        if f is not None:
            m._FONT_PATHS[k] = str(f)
    return m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    lines = [{'text': c['text'], 'start': c['t0'], 'end': c['t1']} for c in tl['captions']]
    src = OUT / 'daisy_lines_aligned.json'                      # align_lyrics.py's shape
    src.write_text(json.dumps(lines), encoding='utf-8')
    O = original()
    bg = Image.open(HERE / 'out' / 'era_wall_0005.png').convert('RGB').resize((1280, 720), Image.Resampling.LANCZOS)
    cases = {
        'default': dict(),
        'mono_glow': dict(font='mono', font_size=40, glow=True, glow_color=(39, 224, 160)),
        'display_top': dict(font='display', font_size=34, y_position=110, bg_opacity=210, bg_padding=(30, 16),
                            text_color=(255, 212, 0), max_chars_per_line=28, min_duration=2.0, max_gap=1.0,
                            fade_duration=0.35),
        'handwriting_small': dict(font='handwriting', font_size=20, bg_color=(60, 10, 40)),   # size clamps to 30
    }
    for name, kw in cases.items():
        a = O.LyricRenderer(str(src), width=1280, height=720, **kw)
        b = lyrics.LyricRenderer(str(src), width=1280, height=720, **kw)
        check(a.display_lines == b.display_lines and a.duration == b.duration and a.line_count == b.line_count,
              f'{name}: display timing identical ({b.line_count} lines, ends {b.duration:.2f} s)')
        # the moments: inside lines, in fades, in the filled gaps, and between lines
        ts = []
        for ln in b.display_lines[:12]:
            ts += [ln['start'] - b.fade_duration * 0.5, ln['start'] + 0.05, (ln['start'] + ln['end']) / 2,
                   ln['end'] - b.fade_duration * 0.3, ln['end'] + 0.01]
        diffs, shown = [], 0
        for t in ts:
            ta, tb_ = a.get_line_at(t), b.get_line_at(t)
            if ta != tb_:
                diffs.append((t, 'get_line_at', ta, tb_))
                continue
            fa, fb = a.draw(bg, t), b.draw(bg, t)
            if np.asarray(fa).tobytes() != np.asarray(fb).tobytes():
                diffs.append((t, 'pixels'))
            na, nb = a.draw(np.asarray(bg), t), b.draw(np.asarray(bg), t)
            if not (isinstance(nb, np.ndarray) and np.array_equal(na, nb)):
                diffs.append((t, 'numpy'))
            shown += ta[0] is not None
        check(not diffs, f'{name}: {len(ts)} moments ({shown} with a line up), PIL and numpy frames identical'
                         + (f'; first difference {diffs[0]}' if diffs else ''))
        k = b.display_lines[min(3, len(b.display_lines) - 1)]
        im = b.draw(bg, (k['start'] + k['end']) / 2)
        im.save(OUT / f'parity_{name}.png')
        kk = b.draw_karaoke(bg, (k['start'] + k['end']) / 2)
        check(np.array_equal(np.asarray(kk), np.asarray(im)), f'{name}: draw_karaoke falls back to draw, as the original')
    # inputs the original cannot take, which the port accepts: the timeline itself, captions with t0/t1
    c = lyrics.LyricRenderer(tl, width=1280, height=720)
    d = lyrics.LyricRenderer(str(src), width=1280, height=720)
    check(c.display_lines == d.display_lines, 'the port reads the timeline dict (captions t0/t1) as align_lyrics output')
    lay = d.layer((d.display_lines[2]['start'] + d.display_lines[2]['end']) / 2)
    check(lay is not None and lay.mode == 'RGBA' and lay.getextrema()[3][0] == 0,
          'layer(t): the subtitle alone, transparent around it (for the overlay panel)')
    check(d.layer(-5.0) is None, 'layer(t) is None when no line shows')
    # debug_timeline: the original's print, line for line
    import contextlib
    import io
    oa, ob = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(oa):
        O.LyricRenderer(str(src), width=1280, height=720).debug_timeline()
    with contextlib.redirect_stdout(ob):
        d.debug_timeline()
    check(oa.getvalue() == ob.getvalue() and ob.getvalue().count('\n') == d.line_count,
          f'debug_timeline() prints the original\'s {d.line_count} lines, character for character')
    print('the first six:\n' + ''.join(ob.getvalue().splitlines(keepends=True)[:6]), end='')
    # a font name that does not resolve falls back to Rajdhani Bold and says so, as the original fell back
    with contextlib.redirect_stdout(io.StringIO()) as said:
        e = lyrics.LyricRenderer(str(src), font='no-such-face')
    check(Path(e.font.path).name == 'Rajdhani-Bold.ttf' and 'Rajdhani Bold instead' in said.getvalue(),
          f'an unknown font falls back to {Path(e.font.path).name}, and says so')
    print(f'[test_lyrics_parity] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    sys.exit(1 if FAILS else 0)


main()
