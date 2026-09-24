"""A shareable, high-resolution contact sheet of a video: for collaborators and models without video input.

    python contact_sheet.py work/<id>/film.mp4 [--every 5] [--cols 6] [--tile 640] [--parts 1]
        [--timeline timeline.json] [--names '{"verse1": "verse 1 · the machines"}'] [--title T] [--synopsis S]
        [--out work/<id>/film_contact_sheet]

Takes one frame every --every seconds (from the middle of each interval). With --timeline it also takes one just
inside each section start, and labels every tile with its timestamp, section and the line being sung or spoken
then, so the story reads without sound. Timelines: {"sections": [{name, t0, t1}], "captions": [{text, t0, t1}]}
(either key optional; the shape voicebox/song timelines use), or align_lyrics.py's list of {text, start, end}.
--names maps section keys to readable labels (inline JSON or a .json path). Writes <out>.jpg with everything and,
with --parts N, <out>_part1..N.jpg holding the same frames split for per-image size limits. Tiles keep the video's
aspect. Guide: AGENTS.md ("Contact sheets").
"""
import argparse
import json
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = ROOT / 'eidoverse' / 'assets' / 'fonts' / 'Exo2.ttf'


def mmss(t):
    return f'{int(t // 60)}:{int(t % 60):02d}'


def load_json_arg(s):
    if not s:
        return {}
    p = Path(s)
    return json.loads(p.read_text(encoding='utf-8')) if p.suffix == '.json' and p.exists() else json.loads(s)


def load_timeline(path):
    if not path:
        return [], []
    tl = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(tl, list):                                  # align_lyrics.py output
        return [], [{'text': c['text'], 't0': c['start'], 't1': c['end']} for c in tl]
    return tl.get('sections', []), tl.get('captions', [])


def wrap(draw, text, font, width):
    lines, cur = [], ''
    for word in text.split():
        nxt = f'{cur} {word}'.strip()
        if cur and draw.textlength(nxt, font=font) > width:
            lines.append(cur)
            cur = word
        else:
            cur = nxt
    return lines + ([cur] if cur else [])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('video')
    ap.add_argument('--timeline', default=None)
    ap.add_argument('--names', default=None, help='section key -> label: inline JSON or a .json path')
    ap.add_argument('--every', type=float, default=5.0)
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('--tile', type=int, default=640, help='tile width in px')
    ap.add_argument('--parts', type=int, default=1)
    ap.add_argument('--title', default=None, help='default: the video file name')
    ap.add_argument('--synopsis', default='')
    ap.add_argument('--out', default=None, help='default: <video>_contact_sheet next to the video')
    a = ap.parse_args()

    video = Path(a.video)
    out = a.out or str(video.with_name(video.stem + '_contact_sheet'))
    title = a.title or video.stem
    sections, captions = load_timeline(a.timeline)
    names = load_json_arg(a.names)
    probe = json.loads(subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration',
         '-of', 'json', str(video)], capture_output=True, text=True, check=True).stdout)
    dur = float(probe['format']['duration'])
    vw, vh = probe['streams'][0]['width'], probe['streams'][0]['height']

    times = {round(k * a.every + a.every / 2, 2) for k in range(max(1, int(dur // a.every)))}
    for s in sections:
        times.add(round(min(dur - 0.5, s['t0'] + 1.2), 2))
    kept = []
    for t in sorted(t for t in times if 0 <= t < dur - 0.2):
        if kept and t - kept[-1] < a.every * 0.45:           # a section-start extra crowding a regular sample
            continue
        kept.append(t)
    times = kept

    def section(t):
        for s in sections:
            if s['t0'] <= t < s['t1']:
                return names.get(s['name'], s['name'])
        return names.get(sections[-1]['name'], sections[-1]['name']) if sections else ''

    def line(t):
        cs = [c for c in captions if c['t0'] - 0.3 <= t <= c['t1'] + 0.6]
        if not cs:
            return ''
        c = min(cs, key=lambda c: abs((c['t0'] + c['t1']) / 2 - t))
        return c['text'].replace('\\N', ' ').replace('\n', ' ')

    W = a.tile
    H = round(W * vh / vw / 2) * 2
    LAB = int(W * (0.13 if captions else 0.075))
    f_big = ImageFont.truetype(str(FONT), int(W * 0.036))
    f_small = ImageFont.truetype(str(FONT), int(W * 0.03))
    f_title = ImageFont.truetype(str(FONT), int(W * 0.07))
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            p = os.path.join(td, f'f{i:04d}.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1',
                            '-vf', f'scale={W}:{H}:flags=lanczos', p], check=True)
            tiles.append((t, Image.open(p).convert('RGB')))

    def compose(items, path, subtitle):
        cols = min(a.cols, len(items))
        rows = (len(items) + cols - 1) // cols
        pad = int(W * 0.012)
        sw = cols * (W + pad) + pad
        measure = ImageDraw.Draw(Image.new('RGB', (8, 8)))
        syn = wrap(measure, a.synopsis, f_small, sw - pad * 4) if a.synopsis else []
        lh = int(W * 0.042)
        head = int(W * 0.11) + lh * (len(syn) + 1) + pad * 2
        S = Image.new('RGB', (sw, head + rows * (H + LAB + pad) + pad), (14, 15, 20))
        d = ImageDraw.Draw(S)
        d.text((pad * 2, pad * 2), title, font=f_title, fill=(244, 238, 226))
        y = pad * 2 + int(W * 0.1)
        for ln in syn:
            d.text((pad * 2, y), ln, font=f_small, fill=(200, 204, 214))
            y += lh
        d.text((pad * 2, y), subtitle, font=f_small, fill=(224, 134, 95))
        for k, (t, im) in enumerate(items):
            x = pad + (k % cols) * (W + pad)
            y = head + (k // cols) * (H + LAB + pad)
            S.paste(im, (x, y))
            sec = section(t)
            d.text((x + 6, y + H + 4), f'{mmss(t)}  ·  {sec}' if sec else mmss(t), font=f_big, fill=(244, 238, 226))
            ly = line(t)
            if ly:
                ln = textwrap.shorten(ly, width=int(W / (W * 0.03) * 1.9), placeholder='…')
                d.text((x + 6, y + H + 4 + int(W * 0.05)), f'“{ln}”', font=f_small, fill=(170, 176, 190))
        S.save(path, quality=90, optimize=True)
        print(f'{path}: {S.size[0]}x{S.size[1]}, {os.path.getsize(path) / 2 ** 20:.1f} MiB, {len(items)} frames')

    info = f'{mmss(dur)} · one frame every {a.every:g} s' + (' (+ each section start)' if sections else '')
    if sections or captions:
        info += ' · timestamp' + (' · section' if sections else '') + (' · the line sung or spoken then' if captions else '')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    compose(tiles, out + '.jpg', info)
    if a.parts > 1:
        per = (len(tiles) + a.parts - 1) // a.parts
        for k in range(a.parts):
            chunk = tiles[k * per:(k + 1) * per]
            if chunk:
                compose(chunk, f'{out}_part{k + 1}.jpg',
                        f'part {k + 1} of {a.parts}: {mmss(chunk[0][0])}–{mmss(chunk[-1][0])} · ' + info)


if __name__ == '__main__':
    main()
