"""The review's three dune views before and after (plain Python, Pillow): per view one row of the photograph the
review set beside it, the review's own render of 11-12 (out/review/renders/dunes/), and this package's re-render of
the same view (review_dunes.py: textured, and grey clay when there is one).

    python before_after.py <review dir>      e.g. ../out/wind_sand/review_v3 -> <review dir>/before_after.jpg
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BEFORE = os.path.join(TN, 'out', 'review', 'renders', 'dunes')
TW, TH = 480, 270


def fit(path):
    if not path or not os.path.exists(path):
        return Image.new('RGB', (TW, TH), (40, 40, 40))
    im = Image.open(path).convert('RGB')
    w, h = im.size
    if w / h > TW / TH:
        nw = int(h * TW / TH)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * TH / TW)
        top = max(0, min(h - nh, int(0.45 * (h - nh))))
        im = im.crop((0, top, w, top + nh))
    return im.resize((TW, TH), Image.LANCZOS)


def main():
    d = sys.argv[1]
    rec = json.load(open(os.path.join(d, 'views.json'), encoding='utf-8'))
    font = ImageFont.truetype('arial.ttf', 15)
    rows = []
    for v in rec['views']:
        name = v['name']
        cells = [(v.get('photo'), 'photograph'), (os.path.join(BEFORE, name + '.png'), 'review 11-12 (before)'),
                 (os.path.join(d, name + '.png'), 'now, textured'), (os.path.join(d, name + '_clay.png'), 'now, clay')]
        row = Image.new('RGB', (4 * TW, TH + 24), (22, 22, 22))
        dr = ImageDraw.Draw(row)
        dr.text((6, 3), f'dunes / {name}: {v["caption"]}'[:200], fill=(255, 220, 120), font=font)
        for i, (p, label) in enumerate(cells):
            row.paste(fit(p), (i * TW, 24))
            dr.rectangle((i * TW, TH + 4, i * TW + 190, TH + 22), fill=(0, 0, 0))
            dr.text((i * TW + 4, TH + 5), label, fill=(230, 230, 230), font=font)
        rows.append(row)
    sheet = Image.new('RGB', (4 * TW, sum(r.height for r in rows)), (0, 0, 0))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    out = os.path.join(d, 'before_after.jpg')
    sheet.save(out, quality=90)
    print(out)


if __name__ == '__main__':
    main()
