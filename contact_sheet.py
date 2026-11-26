"""A shareable, high-resolution contact sheet of a video: for collaborators and models without video input.

    python contact_sheet.py work/<id>/film.mp4 [--every 5] [--cols 6] [--tile 640] [--parts 1]
        [--timeline timeline.json] [--names '{"verse1": "verse 1 · the machines"}'] [--title T] [--synopsis S]
        [--out work/<id>/film_contact_sheet]
    python contact_sheet.py work/<id>/film.mp4 --lines --timeline timeline.json [--per-row 6] [--tile 320]
        [--song song.wav | --song none] [--beats song_clock.json] [--gap 3] [--png] [--parts 1] [--title T]

Takes one frame every --every seconds (from the middle of each interval). With --timeline it also takes one just
inside each section start, and labels every tile with its timestamp, section and the line being sung or spoken
then, so the story reads without sound. Timelines: {"sections": [{name, t0, t1}], "captions": [{text, t0, t1}]}
(either key optional; the shape voicebox/song timelines and song_clock.py use), or align_lyrics.py's list of
{text, start, end}. --names maps section keys to readable labels (inline JSON or a .json path). Writes <out>.jpg
with everything and, with --parts N, <out>_part1..N.jpg holding the same frames split for per-image size limits.
Tiles keep the video's aspect.

--lines lays the piece out line by line instead: a row for every caption and one for each stretch without words
longer than --gap seconds (labelled with its section, else intro / break / outro). Each row shows its time and
section, the words, --per-row frames spread over its seconds and, under them, the sound's mel spectrogram over the
same seconds (40 Hz - 11 kHz, dB on one scale for the whole piece, so rows compare), with the beats (--beats: a
JSON list of seconds, or song_clock.py's clock) as ticks and the frames' moments marked. The sound is the video's
own unless --song names another (--song none leaves the strips out). Default <out>: <video>_contact_sheet_lines.
Guide: AGENTS.md ("Contact sheets").
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
FONT_WORDS = ROOT / 'eidoverse' / 'assets' / 'fonts' / 'Anton-Regular.ttf'
NOWIN = 0x08000000 if os.name == 'nt' else 0       # no console window for the ffmpeg children on Windows


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


# ---------------------------------------------------------------------------------- the line-by-line sheet (--lines)
L_BG, L_INK, L_DIM, L_ACCENT = (14, 11, 9), (240, 226, 196), (150, 136, 112), (255, 150, 40)
INFERNO = [(0, 0, 4), (40, 11, 84), (101, 21, 110), (159, 42, 99), (212, 72, 66), (245, 125, 21), (250, 193, 39),
           (252, 255, 164)]


def fmt_tenths(t):
    t = round(t, 1)                                       # (rounded first: 119.98 s would print as "1:60.0")
    m = int(t // 60)
    return f'{m}:{t - 60 * m:04.1f}'


def load_beats(path):
    """beat times in seconds: a JSON list of seconds, or a dict whose "beats" are seconds or {t, ...} (song_clock.py)"""
    import numpy as np
    if not path:
        return np.zeros(0, np.float32)
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(d, dict):
        d = d.get('beats', [])
    return np.array(sorted(float(b['t'] if isinstance(b, dict) else b) for b in d), np.float32)


def colormap(v):
    """v in 0..1 -> RGB uint8, inferno-like"""
    import numpy as np
    a = np.array(INFERNO, np.float32)
    x = np.clip(v, 0.0, 1.0) * (len(a) - 1)
    i = np.minimum(x.astype(np.int32), len(a) - 2)
    f = (x - i)[..., None]
    return (a[i] * (1.0 - f) + a[i + 1] * f).astype(np.uint8)


def spectrogram(src, sr=22050, hop=230, n_fft=2048, bands=96):
    """a sound (any file ffmpeg reads: a wav, or a video's own track) -> ((bands x columns) in 0..1, columns a second),
    low frequencies at the bottom: mel bands 40 Hz - 11 kHz in dB, 64 dB under the piece's loudest at 0, on a curve
    that keeps the bed dark (every row is on this one scale). (None, rate) when there is no sound."""
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(src), '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, creationflags=NOWIN).stdout
    y = np.frombuffer(raw, np.float32)
    if len(y) < 2 * n_fft:
        return None, sr / hop
    n = 1 + (len(y) - n_fft) // hop
    win = np.hanning(n_fft).astype(np.float32)
    mag = np.empty((n, n_fft // 2 + 1), np.float32)
    for s in range(0, n, 2048):                           # (in blocks: a whole song at once is gigabytes)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(s, min(n, s + 2048))[:, None]
        mag[s:s + len(idx)] = np.abs(np.fft.rfft(y[idx] * win, axis=1))
    mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)  # noqa: E731
    imel = lambda m: 700.0 * (10 ** (m / 2595.0) - 1.0)  # noqa: E731
    edges = imel(np.linspace(mel(40.0), mel(11000.0), bands + 2))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    fb = np.zeros((bands, len(freqs)), np.float32)
    for b in range(bands):
        lo, c, hi = edges[b], edges[b + 1], edges[b + 2]
        fb[b] = np.clip(np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)), 0.0, None)
    db = 20.0 * np.log10(mag @ fb.T + 1e-6)
    top = np.percentile(db, 99.7)
    v = np.clip((db - (top - 64.0)) / 64.0, 0.0, 1.0) ** 1.8
    return v.T[::-1], sr / hop


def video_frames(path, wanted, tw, th):
    """{frame number (1-based): tw x th image} for the frames in `wanted`, by one decode of the video"""
    want = set(wanted)
    last = max(want) if want else 0
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'scale={tw}:{th}:flags=area', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, creationflags=NOWIN)
    got, f, size = {}, 0, tw * th * 3
    while f < last:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        f += 1
        if f in want:
            got[f] = Image.frombytes('RGB', (tw, th), b)
    p.kill()
    p.wait()
    return got


def line_rows(captions, sections, names, end, gap):
    """[(t0, t1, words or None, section label)]: every caption, and every stretch without words longer than gap s"""
    def section_at(t):
        for s in sections:
            if s['t0'] <= t < s['t1']:
                return names.get(s['name'], s['name'])
        return ''
    caps = sorted((float(c['t0']), float(c['t1']), c['text'].replace('\\N', ' ').replace('\n', ' ').strip())
                  for c in captions if float(c['t1']) > float(c['t0']))
    rows, prev = [], 0.0
    for t0, t1, text in caps:
        if t0 - prev > gap:
            rows.append((prev, t0, None, section_at((prev + t0) / 2) or ('intro' if not rows else 'break')))
        rows.append((t0, t1, text, section_at(t0)))
        prev = max(prev, t1)
    if end - prev > gap:
        rows.append((prev, end, None, section_at((prev + end) / 2) or 'outro'))
    return rows


def lines_sheet(a):
    """the --lines sheet: a row per line, its frames, the sound's spectrogram under them"""
    video = Path(a.video)
    out = a.out or str(video.with_name(video.stem + '_contact_sheet_lines'))
    sections, captions = load_timeline(a.timeline)
    if not captions:
        raise SystemExit('contact_sheet.py --lines needs a --timeline with captions (the lines and their times)')
    names = load_json_arg(a.names)
    probe = json.loads(subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height,avg_frame_rate,nb_frames:format=duration', '-of', 'json', str(video)],
        capture_output=True, text=True, check=True, creationflags=NOWIN).stdout)
    st = probe['streams'][0]
    num, den = (int(x) for x in st['avg_frame_rate'].split('/'))
    fps = num / den if den else 24.0
    n_frames = int(st.get('nb_frames') or 0) or int(round(float(probe['format']['duration']) * fps))
    end = n_frames / fps
    rows = line_rows(captions, sections, names, end, a.gap)
    tw = a.tile or 320
    th = round(tw * st['height'] / st['width'] / 2) * 2
    k = max(1, a.per_row)
    W = k * tw
    s = tw / 320.0
    head_h, gap_h = int(64 * s), int(14 * s)
    picks = [[min(n_frames, max(1, int(round((t0 + (t1 - t0) * (j + 0.5) / k) * fps)) + 1)) for j in range(k)]
             for t0, t1, _w, _s in rows]
    frames = video_frames(video, [f for fs in picks for f in fs], tw, th)
    spec, cps = (None, 0.0) if (a.song or '').lower() == 'none' else spectrogram(a.song or video)
    spec_h = int(110 * s) if spec is not None else 0
    beats = load_beats(a.beats)

    def font(path, size, bold=False):
        f = ImageFont.truetype(str(path), max(8, int(size)))
        if bold:
            try:
                f.set_variation_by_name('Bold')              # (Exo2 is a variable font)
            except (OSError, ValueError):
                pass
        return f
    f_time, f_sec = font(FONT, 22 * s, bold=True), font(FONT, 20 * s)
    f_title, f_sub = font(FONT_WORDS, 96 * s), font(FONT, 26 * s)
    sizes = {}

    def words_font(d, text, width):
        size = int(40 * s)
        while size > 12 and d.textlength(text, font=sizes.setdefault(size, font(FONT_WORDS, size))) > width:
            size -= 2
        return sizes.setdefault(size, font(FONT_WORDS, size))

    title = a.title or video.stem
    what = 'lines, frames and the sound, line by line' if spec is not None else 'lines and frames, line by line'

    def compose(items, path, subtitle):
        measure = ImageDraw.Draw(Image.new('RGB', (8, 8)))
        syn = wrap(measure, a.synopsis, f_sub, W - int(80 * s)) if a.synopsis else []
        title_h = int(170 * s) + int(34 * s) * len(syn)
        row_h = head_h + th + spec_h + gap_h
        sheet = Image.new('RGB', (W, title_h + row_h * len(items) + int(40 * s)), L_BG)
        d = ImageDraw.Draw(sheet)
        d.text((int(40 * s), int(16 * s)), title, font=f_title, fill=L_ACCENT)
        d.text((int(44 * s), int(132 * s)), subtitle, font=f_sub, fill=L_DIM)
        for i, ln in enumerate(syn):
            d.text((int(44 * s), int(166 * s) + i * int(34 * s)), ln, font=f_sub, fill=L_INK)
        for r, ((t0, t1, text, sec), fs) in enumerate(items):
            y0 = title_h + r * row_h
            d.text((int(40 * s), y0 + int(6 * s)), f'{fmt_tenths(t0)} – {fmt_tenths(t1)}', font=f_time, fill=L_INK)
            d.text((int(40 * s), y0 + int(34 * s)), sec, font=f_sec, fill=L_DIM)
            shown = '(no words)' if text is None else text.upper()
            fw = words_font(d, shown, W - int(290 * s))
            d.text((int(270 * s), y0 + int(8 * s)), shown, font=fw, fill=L_DIM if text is None else L_INK)
            for j, f in enumerate(fs):
                if f in frames:
                    sheet.paste(frames[f], (j * tw, y0 + head_h))
            if spec is None:
                continue
            sy = y0 + head_h + th
            c0 = int(t0 * cps)
            c1 = min(spec.shape[1], max(c0 + 2, int(t1 * cps)))
            if c1 - c0 >= 2:                                 # the row's seconds, on the whole piece's scale
                strip = Image.fromarray(colormap(spec[:, c0:c1])).resize((W, spec_h), Image.BILINEAR)
                sheet.paste(strip, (0, sy))
            for b in beats[(beats >= t0) & (beats <= t1)]:   # the beats
                x = int((b - t0) / (t1 - t0) * (W - 1))
                d.line([(x, sy), (x, sy + int(10 * s))], fill=(255, 255, 255), width=1)
            for f in fs:                                      # the frames' moments
                x = int(((f - 1) / fps - t0) / (t1 - t0) * (W - 1))
                m = int(6 * s)
                d.polygon([(x - m, sy + spec_h), (x + m, sy + spec_h), (x, sy + spec_h - int(10 * s))], fill=L_ACCENT)
        sheet.save(path, quality=90, optimize=True)
        print(f'{path}: {sheet.size[0]}x{sheet.size[1]}, {os.path.getsize(path) / 2 ** 20:.1f} MiB, {len(items)} rows')
        if a.png:
            png = os.path.splitext(path)[0] + '.png'
            sheet.save(png, compress_level=6)
            print(f'{png}: {os.path.getsize(png) / 2 ** 20:.1f} MiB')

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    info = f'{what}  ·  {fmt_tenths(end)}  ·  {n_frames} frames at {fps:g} fps'
    items = list(zip(rows, picks))
    compose(items, out + '.jpg', info)
    if a.parts > 1:
        per = (len(items) + a.parts - 1) // a.parts
        for p in range(a.parts):
            chunk = items[p * per:(p + 1) * per]
            if chunk:
                compose(chunk, f'{out}_part{p + 1}.jpg', f'part {p + 1} of {a.parts}: {fmt_tenths(chunk[0][0][0])}–'
                        f'{fmt_tenths(chunk[-1][0][1])}  ·  ' + info)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('video')
    ap.add_argument('--timeline', default=None)
    ap.add_argument('--names', default=None, help='section key -> label: inline JSON or a .json path')
    ap.add_argument('--every', type=float, default=5.0)
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('--tile', type=int, default=None, help='tile width in px (default 640; --lines: 320)')
    ap.add_argument('--parts', type=int, default=1)
    ap.add_argument('--title', default=None, help='default: the video file name')
    ap.add_argument('--synopsis', default='')
    ap.add_argument('--out', default=None, help='default: <video>_contact_sheet next to the video')
    ap.add_argument('--lines', action='store_true', help='a row per line sung or spoken (needs --timeline)')
    ap.add_argument('--per-row', type=int, default=6, help='--lines: frames in each row')
    ap.add_argument('--song', default=None,
                    help="--lines: the sound for the spectrogram (default: the video's own; 'none': no strips)")
    ap.add_argument('--beats', default=None, help='--lines: beat times (a JSON list of seconds, or song_clock.py output)')
    ap.add_argument('--gap', type=float, default=3.0, help='--lines: a stretch without words this long gets a row')
    ap.add_argument('--png', action='store_true', help='--lines: also write a lossless PNG')
    a = ap.parse_args()
    if a.lines:
        return lines_sheet(a)

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

    W = a.tile or 640
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
