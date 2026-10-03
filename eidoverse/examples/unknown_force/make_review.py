"""Review sheets for other agents and Claudes: SEE the whole film and HEAR the whole mix.

    python eidoverse/examples/unknown_force/make_review.py <video.mp4> [--every 4] [--cols 8] [--out work/unknown_force/out/review]
Writes <out>_contact.png (one frame every N s, labelled with time + section + the sung line), <out>_spectrogram.png
(the whole mix, log-frequency, sections and documentary clips marked) and <out>_index.md (what is where).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'eido.py').exists())
WORK = ROOT / 'work' / 'unknown_force'            # the film's data and outputs (git-ignored)
sys.path.insert(0, str(ROOT))


def font(px, bold=False):
    for f in (['consolab.ttf', 'arialbd.ttf'] if bold else ['consola.ttf', 'arial.ttf']):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            pass
    return ImageFont.load_default()


def section_at(TL, t):
    for s in TL['sections']:
        if s['t0'] <= t < s['t1']:
            return s['name']
    return TL['sections'][-1]['name']


def line_at(TL, t):
    for ln in TL['lines']:
        if ln['start'] - 0.3 <= t <= ln['end'] + 0.3:
            return ln['text']
    for c in TL['doc']:
        if c['t0'] <= t <= c['t1'] and c.get('caption'):
            return '[doc] ' + c['caption'][:70]
    return ''


def contact(video, TL, every, cols, out):
    dur = TL['song_len']
    times = list(np.arange(every / 2, dur, every))
    tmp = out.parent / (out.name + '_frames')
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = []
    W, H = 384, 216
    for i, t in enumerate(times):
        f = tmp / f'f{i:03d}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1',
                        '-vf', f'scale={W}:{H}', str(f)], check=True)
        im = Image.open(f).convert('RGB')
        lab = Image.new('RGB', (W, H + 40), (12, 12, 16))
        lab.paste(im, (0, 0))
        d = ImageDraw.Draw(lab)
        d.text((6, H + 3), f'{int(t // 60)}:{t % 60:05.2f}  {section_at(TL, t)}', fill=(255, 210, 90), font=font(15, True))
        d.text((6, H + 21), line_at(TL, t)[:52], fill=(200, 200, 210), font=font(13))
        tiles.append(lab)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * W, rows * (H + 40) + 50), (6, 6, 9))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), f'UNKNOWN FORCE — contact sheet, one frame every {every:g} s ({len(tiles)} frames, {dur:.1f} s)',
           fill=(255, 255, 255), font=font(22, True))
    for i, tl in enumerate(tiles):
        sheet.paste(tl, ((i % cols) * W, 50 + (i // cols) * (H + 40)))
    sheet.save(f'{out}_contact.png')
    return len(tiles)


def spectrogram(TL, out):
    import soundfile as sf
    from scipy.signal import stft
    y, sr = sf.read(str(WORK / 'audio/out/unknown_force_mix.wav'), always_2d=True)
    y = y.mean(axis=1)
    f, t, Z = stft(y, fs=sr, nperseg=4096, noverlap=4096 - 1024)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    # log-frequency rows 40 Hz .. 16 kHz
    W, Hh = 4000, 700
    fr = np.geomspace(40, 16000, Hh)
    idx = np.clip(np.searchsorted(f, fr), 0, len(f) - 1)
    S = S[idx]
    cols = np.linspace(0, S.shape[1] - 1, W).astype(int)
    S = S[:, cols]
    S = np.clip((S - (S.max() - 90)) / 90, 0, 1)[::-1]
    # magma-ish ramp
    r = np.clip(1.6 * S - 0.1, 0, 1); g = np.clip(1.8 * S - 0.75, 0, 1); b = np.clip(0.7 * S + 0.35 * np.sin(S * 3.1), 0, 1)
    img = (np.stack([r, g, b], -1) * 255).astype(np.uint8)
    top, bot = 60, 150
    im = Image.new('RGB', (W, Hh + top + bot), (6, 6, 9))
    im.paste(Image.fromarray(img), (0, top))
    d = ImageDraw.Draw(im)
    dur = len(y) / sr
    X = lambda tt: int(tt / dur * W)
    d.text((10, 10), 'UNKNOWN FORCE — the whole mix (log frequency 40 Hz–16 kHz; -14 LUFS master). Sections on top, '
           'documentary clips below.', fill=(255, 255, 255), font=font(22, True))
    for hz in (100, 1000, 10000):
        yy = top + Hh - int(np.searchsorted(fr, hz) / Hh * Hh)
        d.line([(0, yy), (14, yy)], fill=(255, 80, 80)); d.text((18, yy - 8), f'{hz if hz < 1000 else str(hz // 1000) + "k"}', fill=(255, 120, 120), font=font(13))
    for s in TL['sections']:
        d.line([(X(s['t0']), top), (X(s['t0']), top + Hh)], fill=(90, 200, 255))
        d.text((X(s['t0']) + 3, top + 2), s['name'], fill=(140, 220, 255), font=font(14, True))
    for i, c in enumerate(TL['doc']):
        y0 = top + Hh + 8 + (i % 6) * 22
        d.rectangle([X(c['t0']), y0, max(X(c['t0']) + 2, X(c['t1'])), y0 + 16], fill=(255, 170, 60) if 'marinetti' in c['id'] else (200, 120, 255) if c['id'] == 'my_line' else (90, 160, 120))
        d.text((X(c['t0']) + 3, y0), c['id'], fill=(10, 10, 10), font=font(12, True))
    for m in range(0, int(dur) + 1, 30):
        d.text((X(m) + 2, top + Hh - 18), f'{m // 60}:{m % 60:02d}', fill=(230, 230, 230), font=font(13))
    im.save(f'{out}_spectrogram.png')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--every', type=float, default=4.0)
    ap.add_argument('--cols', type=int, default=8)
    ap.add_argument('--out', default=str(WORK / 'out' / 'review'))
    a = ap.parse_args()
    TL = json.load(open(WORK / 'out' / 'uf_timeline.json', encoding='utf8'))
    out = Path(a.out)
    n = contact(Path(a.video), TL, a.every, a.cols, out)
    spectrogram(TL, out)
    with open(f'{out}_index.md', 'w', encoding='utf8') as fh:
        fh.write('# UNKNOWN FORCE — review index\n\n| section | from | to | set | look |\n|---|---|---|---|---|\n')
        for s in TL['sections']:
            fh.write(f"| {s['name']} | {s['t0']:.1f} | {s['t1']:.1f} | {s['set']} | {s['look']} |\n")
        fh.write('\n## Documentary clips (exact quotes; generic anchor voice; Marinetti = his own 1924 voice)\n\n')
        for c in TL['doc']:
            fh.write(f"- {c['t0']:.2f}–{c['t1']:.2f} `{c['id']}`: {c.get('caption') or ''} — {c.get('attribution') or ''}\n")
    print(f'contact: {n} frames -> {out}_contact.png; spectrogram -> {out}_spectrogram.png; index -> {out}_index.md')


if __name__ == '__main__':
    main()
