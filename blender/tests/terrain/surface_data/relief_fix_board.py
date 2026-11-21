"""The relief fix's boards (the 11-20 review: the sub-cell relief's washboard on the cones, the snowfield and the dune
flanks): per view, the photograph | the render before | the render after, and under them the places the review named,
enlarged, before beside after, with the judge's repetition and high-pass energy of each crop (system Python: numpy,
Pillow):

    python blender/tests/terrain/surface_data/relief_fix_board.py [--before final] [--after pkg1fix]

The renders are review_views.py's (out/surfacing/review/<recipe>/<view>_<tag>.png), the photographs the judge's
(surfacing_judge/photos.json through views.json). Writes out/surface_data/fix/<recipe>_<view>.jpg and
out/surface_data/fix/measures.json.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
REVIEW = os.path.join(TN, 'out', 'surfacing', 'review')
OUT = os.path.join(TN, 'out', 'surface_data', 'fix')

# the views the review named and its crops (render pixels x0, y0, x1, y1), with what it saw there
CASES = [
    ('stratovolcano', 'aerial_nne', [(183, 237, 423, 372), (400, 100, 880, 370)],
     'an even washboard of waves about 60 m apart over the snowfield and the bare ash band'),
    ('stratovolcano', 'low_oblique', [(409, 399, 649, 534), (200, 240, 700, 420)],
     'the washboard on the forest zone and the ash band at a grazing angle'),
    ('stratovolcano', 'walk_upper_flank', [(536, 132, 776, 267), (77, 338, 317, 473)],
     'rows of lens-shaped dark patches through the snow near the walker'),
    ('cinder_cones', 'aerial_south', [(148, 355, 388, 490), (380, 380, 700, 540)],
     'an even corrugation of stripes about 16 m apart on the cone flank'),
    ('cinder_cones', 'low_oblique', [(0, 264, 240, 399), (300, 250, 700, 400)],
     'the same washboard on every cone'),
    ('cinder_cones', 'ground_se', [(94, 38, 334, 173), (280, 230, 800, 330)],
     'the cones from the plateau: fine ripples on the flanks'),
    ('dunes', 'aerial', [(0, 330, 480, 540), (300, 150, 780, 400)],
     'short dark down-slope dashes over the dune flanks'),
    ('dunes', 'low_oblique', [(300, 250, 780, 500), (0, 300, 480, 540)],
     'the dashes at a low angle'),
    ('mesas_buttes', 'low_oblique', [(0, 300, 480, 540), (480, 300, 960, 540)],
     'a patch of regular corrugation on a small dune slope on the floor'),
    ('mesas_buttes', 'aerial', [(300, 200, 780, 470), (0, 270, 480, 540)], 'the floor from above'),
    ('canyon', 'aerial_down_canyon', [(240, 200, 720, 470), (0, 270, 480, 540)],
     'the look the review kept'),
    ('canyon', 'overlook_down', [(240, 200, 720, 470), (480, 270, 960, 540)], 'the look the review kept'),
    ('canyon', 'low_oblique', [(240, 200, 720, 470), (0, 270, 480, 540)], 'the look the review kept'),
    ('canyon', 'brink_down', [(240, 200, 720, 470), (480, 270, 960, 540)], 'the look the review kept'),
]


def _font(size):
    from PIL import ImageFont
    for name in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _photo(recipe, view):
    try:
        from surfacing_judge import views as V
        return V.photo_path(V.view(recipe, view))
    except Exception:                                     # noqa: BLE001 - a board without its photograph
        return None


def main():
    from PIL import Image, ImageDraw
    from surfacing_judge import measures as JM
    a = sys.argv[1:]
    before = a[a.index('--before') + 1] if '--before' in a else 'final'
    after = a[a.index('--after') + 1] if '--after' in a else 'pkg1fix'
    os.makedirs(OUT, exist_ok=True)
    f12, f14 = _font(12), _font(14)
    report = {}
    for recipe, view, crops, said in CASES:
        pb = os.path.join(REVIEW, recipe, f'{view}_{before}.png')
        pa = os.path.join(REVIEW, recipe, f'{view}_{after}.png')
        if not (os.path.exists(pb) and os.path.exists(pa)):
            continue
        ib, ia = Image.open(pb).convert('RGB'), Image.open(pa).convert('RGB')
        ph = _photo(recipe, view)
        tw, th = 480, 270
        tiles = [Image.open(ph).convert('RGB').resize((tw, th)) if ph else Image.new('RGB', (tw, th), (35, 35, 35)),
                 ib.resize((tw, th)), ia.resize((tw, th))]
        rows = [(tiles, ['photograph' if ph else 'no photograph at this spot', f'before: {before}',
                         f'after: {after}'])]
        meas = []
        for (x0, y0, x1, y1) in crops:
            cw, ch = x1 - x0, y1 - y0
            s = min(720 / cw, 405 / ch)
            size = (int(cw * s), int(ch * s))
            cb, ca = ib.crop((x0, y0, x1, y1)).resize(size), ia.crop((x0, y0, x1, y1)).resize(size)
            mb = JM.repetition(JM.luma(np.asarray(ib, np.float64)), (x0, y0, x1, y1))
            ma = JM.repetition(JM.luma(np.asarray(ia, np.float64)), (x0, y0, x1, y1))
            meas.append(dict(box=[x0, y0, x1, y1], before=dict(peak=mb.get('peak'), energy=mb.get('energy')),
                             after=dict(peak=ma.get('peak'), energy=ma.get('energy'))))
            lab = (f'{s:.1f}x, render pixels {x0}-{x1}, {y0}-{y1}: repetition {mb.get("peak") or 0:.2f} -> '
                   f'{ma.get("peak") or 0:.2f}, energy {mb.get("energy") or 0:.1f} -> {ma.get("energy") or 0:.1f}')
            rows.append(([cb, ca], [f'before, {lab}', 'after']))
        report[f'{recipe}/{view}'] = dict(review=said, crops=meas)
        W = 3 * tw
        H = 24 + sum(max(t.size[1] for t in r[0]) + 18 for r in rows)
        board = Image.new('RGB', (max(W, 1440), H), (20, 20, 20))
        d = ImageDraw.Draw(board)
        d.text((6, 4), f'{recipe} / {view}: the review saw {said}', fill=(240, 210, 120), font=f14)
        y = 24
        for imgs, labels in rows:
            x = 0
            for im, lb in zip(imgs, labels):
                d.text((x + 4, y), lb, fill=(220, 220, 220), font=f12)
                board.paste(im, (x, y + 16))
                x += im.size[0]
            y += max(t.size[1] for t in imgs) + 18
        board.save(os.path.join(OUT, f'{recipe}_{view}.jpg'), quality=90)
        print(f'[relief_fix_board] {recipe}/{view}: ' + '; '.join(
            f'repetition {m["before"]["peak"] or 0:.2f} -> {m["after"]["peak"] or 0:.2f}' for m in meas))
    with open(os.path.join(OUT, 'measures.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
