"""The judge's views as the independent review saw them beside the same views now (system Python): per recipe, the
reviewer's renders (out/integration/sheets/judge/<recipe>/<recipe>_seed1_<view>.png) in the left column and this
package's re-run of the judge's Blender job (out/volcanoes_craters/judge_views/<tag>_<recipe>/<tag>_<recipe>_s1_<view>.png)
in the right, for the top hillshade, the 45-degree aerial, the 1.7 m eye, the hero eye and the textured aerial and
eye. Writes out/volcanoes_craters/judge_views/<recipe>_review_vs_now.jpg.

    python blender/tests/terrain/volcanoes_craters/judge_views_sheet.py --tag p2 stratovolcano caldera ...
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
REVIEW = os.path.join(TN, 'out', 'integration', 'sheets', 'judge')
NOW = os.path.join(TN, 'out', 'volcanoes_craters', 'judge_views')
VIEWS = ('tex_aerial', 'tex_eye', 'hero_eye', 'eye_1p7m', 'aerial_45deg', 'top_hillshade')
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
    rows = []
    for v in VIEWS:
        rows.append([tile(os.path.join(REVIEW, recipe, f'{recipe}_seed1_{v}.png'), f'{v}: the review'),
                     tile(os.path.join(NOW, f'{tag}_{recipe}', f'{tag}_{recipe}_s1_{v}.png'), f'{v}: now ({tag})')])
    out = Image.new('RGB', (2 * W + 12, len(rows) * (H + 26) + 8), (12, 12, 12))
    for r, row in enumerate(rows):
        for c, t in enumerate(row):
            out.paste(t, (4 + c * (W + 4), 4 + r * (H + 26)))
    path = os.path.join(NOW, f'{recipe}_review_vs_now.jpg')
    out.save(path, quality=88)
    print(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='p2')
    ap.add_argument('recipes', nargs='+')
    a = ap.parse_args()
    for r in a.recipes:
        sheet(r, a.tag)


if __name__ == '__main__':
    main()
