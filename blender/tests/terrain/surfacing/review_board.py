"""Before and after boards for the surfacing package (system Python: Pillow): per recipe, one row per matched view of
the review - the reviewer's photograph (cropped to 16:9 around its centre, or a blank when the view has none), the
reviewer's textured render (out/review/renders/<recipe>/<view>.png: the palettes before this round), the same camera
with the current palettes (out/surfacing/review/<recipe>/<view>[_<tag>].png, review_views.py), and the grey clay the
reviewer rendered there when there is one - captioned with the view, its camera and the render seconds.

    python blender/tests/terrain/surfacing/review_board.py <recipe> [<recipe> ...] [--tag v2] [--views a,b]

Writes out/surfacing/review/boards/<recipe>[_<tag>].jpg.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
REVIEW = os.path.join(TN, 'out', 'review')
MINE = os.path.join(TN, 'out', 'surfacing', 'review')
TW, TH = 640, 360


def fit(path, label=None):
    if not path or not os.path.exists(path):
        im = Image.new('RGB', (TW, TH), (40, 40, 40))
        ImageDraw.Draw(im).text((20, TH // 2 - 10), label or 'none', fill=(200, 200, 200),
                                font=ImageFont.truetype('arial.ttf', 20))
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


def main(argv):
    tag = argv[argv.index('--tag') + 1] if '--tag' in argv else ''
    only = set((argv[argv.index('--views') + 1] if '--views' in argv else '').split(',')) - {''}
    recipes = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in
                                                                           ('--tag', '--views'))]
    plan = json.load(open(os.path.join(REVIEW, 'views_plan.json'), encoding='utf-8'))
    font = ImageFont.truetype('arial.ttf', 17)
    small = ImageFont.truetype('arial.ttf', 15)
    t = f'_{tag}' if tag else ''
    os.makedirs(os.path.join(MINE, 'boards'), exist_ok=True)
    for r in recipes:
        recp = os.path.join(MINE, r, f'{r}{t}_record.json')
        rec = json.load(open(recp, encoding='utf-8')) if os.path.exists(recp) else {}
        rows = []
        for v in plan[r]['views']:
            if only and v['name'] not in only:
                continue
            after = os.path.join(MINE, r, v['name'] + t + '.png')
            if not os.path.exists(after):
                continue
            before = os.path.join(REVIEW, 'renders', r, v['name'] + '.png')
            clay = os.path.join(REVIEW, 'renders', r, v['name'] + '_clay.png')
            cols = [fit(v.get('photo'), 'no photograph at this spot'), fit(before, 'not rendered by the review'),
                    fit(after)]
            if os.path.exists(clay):
                cols.append(fit(clay))
            row = Image.new('RGB', (len(cols) * TW, TH + 48), (22, 22, 22))
            for k, im in enumerate(cols):
                row.paste(im, (k * TW, 48))
            d = ImageDraw.Draw(row)
            d.text((6, 2), f"{r} / {v['name']}: {v['caption']}"[:230], fill=(255, 220, 120), font=font)
            x = rec.get(v['name'] + t, {})
            sub = 'photograph | the review\'s render (palettes before) | this round\'s palettes' + \
                  (' | grey clay' if len(cols) > 3 else '')
            if x and 'camera' in x:
                sub += (f"    camera {x['camera']}, heading {x.get('heading_deg')}, pitch {x.get('pitch_deg')}, "
                        f"{x.get('lens'):.0f} mm, rocks {x.get('rocks')}, material {x.get('nodes')} nodes, render "
                        f"{x.get('second_render_s')} s/frame")
            d.text((6, 24), sub, fill=(200, 200, 200), font=small)
            rows.append(row)
        if not rows:
            print(f'{r}: nothing rendered yet')
            continue
        width = max(im.width for im in rows)
        sheet = Image.new('RGB', (width, sum(im.height for im in rows)), (0, 0, 0))
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        p = os.path.join(MINE, 'boards', f'{r}{t}.jpg')
        sheet.save(p, quality=88)
        print(p, len(rows))


if __name__ == '__main__':
    main(sys.argv[1:])
