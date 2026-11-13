"""Boards of this package's matched renders (plain Python, Pillow): per recipe, one row per view - the review's
photograph (cropped to 16:9), the review's render of the old terrain from its camera (textured), and this package's
new render from the matched camera, textured and in grey clay - with the view's caption and camera.

    python review_boards.py [--tag t] [--plan <json>] [recipe ...]

Reads out/layered_rock/review/views_plan.json (or --plan) and renders/<recipe>/; writes
out/layered_rock/review/boards/<recipe>.jpg.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'layered_rock', 'review')
OLD = os.path.join(TN, 'out', 'review', 'renders')
TW, TH = 480, 270


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit(path, label=None):
    if not path or not os.path.exists(path):
        im = Image.new('RGB', (TW, TH), (40, 40, 40))
        ImageDraw.Draw(im).text((16, TH // 2 - 10), label or 'none', fill=(200, 200, 200), font=font(16))
        return im
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
    a = sys.argv[1:]
    tag = ''
    plan_path = os.path.join(OUT, 'views_plan.json')
    for key in ('--tag', '--plan'):
        if key in a:
            v = a[a.index(key) + 1]
            if key == '--tag':
                tag = v
            else:
                plan_path = v
            a = [x for i, x in enumerate(a) if x != key and (i == 0 or a[i - 1] != key)]
    plan = json.load(open(plan_path, encoding='utf-8'))
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    for r in a or list(plan):
        rd = os.path.join(OUT, 'renders', r)
        recp = os.path.join(rd, f'{r}_render.json')
        rec = json.load(open(recp, encoding='utf-8')) if os.path.exists(recp) else {}
        rows = []
        for v in plan[r]['views']:
            tex = os.path.join(rd, tag + v['name'] + '.png')
            clay = os.path.join(rd, tag + v['name'] + '_clay.png')
            if not os.path.exists(tex) and not os.path.exists(clay):
                continue
            row = Image.new('RGB', (4 * TW, TH + 46), (22, 22, 22))
            row.paste(fit(v.get('photo'), 'no photograph at this spot'), (0, 46))
            row.paste(fit(os.path.join(OLD, r, v['name'] + '.png'), 'no review render of this view'), (TW, 46))
            row.paste(fit(tex, 'not rendered'), (2 * TW, 46))
            row.paste(fit(clay, 'not rendered'), (3 * TW, 46))
            d = ImageDraw.Draw(row)
            d.text((6, 2), f"{r} / {v['name']}: {v['caption']}"[:230], fill=(255, 220, 120), font=font(15))
            x = rec.get(tag + v['name'], {}) or rec.get(tag + v['name'] + '_clay', {})
            info = (f"camera {x['camera']}, ground {x.get('ground')}, heading {x.get('heading_deg')}, pitch "
                    f"{x.get('pitch_deg')}, {x.get('lens'):.0f} mm, hero levels {x.get('hero')}, rocks {x.get('rocks')}"
                    if x and 'camera' in x else '')
            d.text((6, 22), 'photograph | the review\'s render of the old terrain | new, textured | new, grey clay    '
                   + info, fill=(200, 200, 200), font=font(13))
            rows.append(row)
        if not rows:
            continue
        sheet = Image.new('RGB', (4 * TW, sum(im.height for im in rows)), (0, 0, 0))
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        p = os.path.join(OUT, 'boards', f'{tag}{r}.jpg')
        sheet.save(p, quality=88)
        print(p, len(rows))


if __name__ == '__main__':
    main()
