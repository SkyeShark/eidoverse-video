"""The references on one page: per landform a row of its three probe renders (top-down hillshade, 45-degree aerial,
eye level at 1.7 m) and a label (place, landform, tile size, pixel, source). Writes contact_sheet.png beside this file.

    python contact_sheet.py [--only a,b] [--out contact_sheet.png]
"""
import argparse
import json
import os
import site
import sys

sys.path.append(site.getusersitepackages())
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sites import SITES  # noqa: E402

ROW_H = 270
GAP = 8
LABEL_W = 300
BG = (24, 25, 27)
INK = (232, 232, 228)
DIM = (150, 152, 156)


def font(size):
    for f in ('segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default=os.path.join(HERE, 'contact_sheet.png'))
    a = ap.parse_args()
    names = [n for n in (a.only.split(',') if a.only else SITES) if n]
    rend = os.path.join(HERE, 'renders')
    cols = [('top_hillshade', ROW_H), ('aerial_45deg', ROW_H * 16 // 9), ('eye_1p7m', ROW_H * 16 // 9)]
    W = LABEL_W + sum(w for _, w in cols) + GAP * (len(cols) + 1)
    head = 64
    H = head + len(names) * (ROW_H + GAP) + GAP
    sheet = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(sheet)
    ft, fb, fs = font(26), font(17), font(14)
    d.text((GAP + 4, 14), 'Real landform references: real elevation data, grey clay (albedo 0.18) under make_sky daylight '
           '(15:30, sun 37.7 deg up)', font=ft, fill=INK)
    x = LABEL_W + GAP
    for (kind, w), lab in zip(cols, ('top-down hillshade, north up, sun NW', '45-degree aerial, sun 70 deg left',
                                     'eye level 1.7 m, sun 70 deg left')):
        d.text((x + 2, head - 20), lab, font=fs, fill=DIM)
        x += w + GAP
    for i, n in enumerate(names):
        y = head + i * (ROW_H + GAP)
        with open(os.path.join(HERE, 'data', n + '.json'), encoding='utf-8') as f:
            m = json.load(f)
        src = m['source']
        lines = [(m['title'], fb, INK), (m['landform'], fb, (240, 200, 120))]
        info = (f'{m["extent_m"][0] / 1000:g} km tile, {m["pixel_size_m"]:g} m px, relief '
                f'{m["shape_stats"]["relief_m"]:.0f} m. {src["dataset"].split(",")[0].split("(")[0].strip()}')
        lines += [(t, fs, DIM) for t in wrap(d, info, fs, LABEL_W - 16)]
        ty = y + 6
        for t, f, c in lines:
            for ln in (wrap(d, t, f, LABEL_W - 16) if f is not fs else [t]):
                d.text((GAP + 4, ty), ln, font=f, fill=c)
                ty += f.size + 5
        x = LABEL_W + GAP
        for kind, w in cols:
            p = os.path.join(rend, f'{n}_{kind}.png')
            if os.path.exists(p):
                im = Image.open(p).convert('RGB').resize((w, ROW_H), Image.LANCZOS)
                sheet.paste(im, (x, y))
            else:
                d.rectangle([x, y, x + w - 1, y + ROW_H - 1], outline=(70, 70, 70))
                d.text((x + 10, y + 10), 'not rendered', font=fs, fill=DIM)
            x += w + GAP
    sheet.save(a.out)
    print('[sheet]', a.out, sheet.size)


if __name__ == '__main__':
    main()
