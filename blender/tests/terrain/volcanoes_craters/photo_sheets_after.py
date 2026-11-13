"""Before and after, beside the photographs (system Python): for every view of a recipe the reviewer rendered
(out/review/renders/<recipe>/), its photograph (when the view has one), the reviewer's render (before) and the
re-render after the fixes (render_review_views.py: out/volcanoes_craters/review_views/<tag>/<recipe>/), textured
and, where both exist, grey clay. Writes out/volcanoes_craters/review_views/<tag>/<recipe>_before_after.jpg.

    python blender/tests/terrain/volcanoes_craters/photo_sheets_after.py --tag after impact_crater caldera ...
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BEFORE = os.path.join(TN, 'out', 'review', 'renders')
AFTER = os.path.join(TN, 'out', 'volcanoes_craters', 'review_views')
PLAN = os.path.join(TN, 'out', 'review', 'views_plan.json')
W, H = 640, 360


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tile(path, label):
    img = Image.new('RGB', (W, H + 22), (24, 24, 24))
    if path and os.path.exists(path):
        im = Image.open(path).convert('RGB')
        s = min(W / im.width, H / im.height)
        im = im.resize((max(int(im.width * s), 1), max(int(im.height * s), 1)), Image.LANCZOS)
        img.paste(im, ((W - im.width) // 2, 22 + (H - im.height) // 2))
    else:
        ImageDraw.Draw(img).text((10, 40), 'not rendered', fill=(160, 160, 160), font=font(16))
    ImageDraw.Draw(img).text((6, 3), label, fill=(240, 220, 120), font=font(15))
    return img


def sheet(recipe, tag):
    plan = json.load(open(PLAN, encoding='utf-8'))[recipe]
    rows = []
    for v in plan['views']:
        n = v['name']
        a_rec = os.path.join(AFTER, tag, recipe, 'render.json')
        rec = json.load(open(a_rec, encoding='utf-8')).get(n, {}) if os.path.exists(a_rec) else {}
        build = f", built in {rec['build_s']} s" if rec.get('build_s') is not None else ''
        rows.append([tile(v.get('photo'), f'{n}: photograph'),
                     tile(os.path.join(BEFORE, recipe, n + '.png'), f'{n}: before (the review)'),
                     tile(os.path.join(AFTER, tag, recipe, n + '.png'), f'{n}: after{build}')])
        if os.path.exists(os.path.join(AFTER, tag, recipe, n + '_clay.png')):
            rows.append([tile(None, f'{n}: clay'),
                         tile(os.path.join(BEFORE, recipe, n + '_clay.png'), f'{n}: clay before'),
                         tile(os.path.join(AFTER, tag, recipe, n + '_clay.png'), f'{n}: clay after')])
    out = Image.new('RGB', (3 * W + 16, len(rows) * (H + 26) + 8), (12, 12, 12))
    for r, row in enumerate(rows):
        for c, t in enumerate(row):
            out.paste(t, (4 + c * (W + 4), 4 + r * (H + 26)))
    path = os.path.join(AFTER, tag, f'{recipe}_before_after.jpg')
    out.save(path, quality=90)
    print(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='after')
    ap.add_argument('recipes', nargs='+')
    a = ap.parse_args()
    for r in a.recipes:
        sheet(r, a.tag)


if __name__ == '__main__':
    main()
