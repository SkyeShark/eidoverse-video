"""The photo sheets: each photograph of the real place beside the generated coast from the matching camera (clay and
textured), one row per view, the photo's author and licence under it. System Python (numpy, Pillow):

    python blender/tests/terrain/coast/sheet_photos.py --tag p1 --rock chalk [--title '...']

Reads out/coast/photos/ (the photos, sources.json) and out/coast/views/<tag>_<view>_{clay,tex}.png; writes
out/coast/sheets/<tag>_<rock>_photos.png. A photo is cropped to 16:9 at its own horizontal field of view (the render
matches it), about CROP's centre where the subject is off-centre (the Moher panorama).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUTC = os.path.normpath(os.path.join(HERE, '..', 'out', 'coast'))
PHOTOS = os.path.join(OUTC, 'photos')
VIEWS = os.path.join(OUTC, 'views')
ORDER = {'chalk': ['ss_seaford_head', 'ss_clifftop_east', 'ss_clifftop_west_high', 'ss_beach_birling_gap'],
         'layered': ['moher_clifftop_south', 'moher_stack_obriens', 'moher_from_hags_head', 'moher_from_sea']}
CROP = {'moher_from_sea': (0.36, 0.5)}           # the crop's centre as fractions of the photo (x, y)
TITLES = {
    'ss_seaford_head': 'from Seaford Head, ~70 m up, 91 mm: the sisters 2.5-5 km across the haven',
    'ss_clifftop_east': "on a sister's top, eye level, ~36 mm: along the edge to the east",
    'ss_clifftop_west_high': "at a sister's edge, eye level, 53 mm: west along the coast and down",
    'ss_beach_birling_gap': 'on the beach at Birling Gap, eye level, 42 mm: along the foot of the cliffs',
    'moher_clifftop_south': 'on the cliff top, eye level, 34 mm: south along the coves and headlands',
    'moher_stack_obriens': "~1 km south of O'Brien's Tower, 88 mm: the headland and the sea stack",
    'moher_from_hags_head': "from Hag's Head, eye level, 29 mm: north along 4-5 km of cliffs",
    'moher_from_sea': 'from a boat 700 m out, 1.5 m up, 77 mm panorama (16:9 crop ~43 degrees)',
}
W, H = 640, 360


def font(size):
    for name in ('segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def crop169(im, centre=(0.5, 0.5)):
    w, h = im.size
    if w / h > 16 / 9:
        nw = int(round(h * 16 / 9))
        x0 = int(round(min(max(centre[0] * w - nw / 2, 0), w - nw)))
        return im.crop((x0, 0, x0 + nw, h))
    nh = int(round(w * 9 / 16))
    y0 = int(round(min(max(centre[1] * h - nh / 2, 0), h - nh)))
    return im.crop((0, y0, w, y0 + nh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--rock', default='chalk')
    ap.add_argument('--title', default=None)
    a = ap.parse_args()
    src = json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))
    names = [n for n in ORDER[a['rock'] if isinstance(a, dict) else a.rock]]
    rows = [n for n in names if os.path.exists(os.path.join(VIEWS, f'{a.tag}_{n}_tex.png'))]
    head, foot, gap = 70, 34, 8
    sheet = Image.new('RGB', (3 * W + 4 * gap, head + len(rows) * (H + foot + gap) + gap), (24, 25, 28))
    d = ImageDraw.Draw(sheet)
    f1, f2, f3 = font(26), font(15), font(13)
    place = 'Seven Sisters (chalk)' if a.rock == 'chalk' else 'Cliffs of Moher (layered shale and sandstone)'
    d.text((gap, 10), a.title or f'sea_cliffs {a.rock} ({a.tag}) beside photographs of the {place}', fill=(235, 235, 235),
           font=f1)
    d.text((gap, 44), 'left: the photograph (cropped to 16:9 at its own field of view)   middle: the generated coast '
                      'from the matching camera, grey clay   right: the same, chalk_coast palette; make_sky daylight, '
                      'EEVEE 960x540, 16 samples', fill=(170, 170, 170), font=f3)
    for r, n in enumerate(rows):
        y = head + r * (H + foot + gap)
        s = src[n]
        ph = crop169(Image.open(os.path.join(PHOTOS, s['file'])).convert('RGB'), CROP.get(n, (0.5, 0.5)))
        cells = [ph.resize((W, H), Image.LANCZOS)]
        for kind in ('clay', 'tex'):
            cells.append(Image.open(os.path.join(VIEWS, f'{a.tag}_{n}_{kind}.png')).convert('RGB').resize((W, H),
                                                                                                     Image.LANCZOS))
        for k, im in enumerate(cells):
            sheet.paste(im, (gap + k * (W + gap), y))
        d.text((gap, y + H + 3), f"{n}: {TITLES.get(n, '')}", fill=(225, 225, 225), font=f2)
        d.text((gap, y + H + 19), f"photo: {s['author'][:60]}, {s['licence']}, Wikimedia Commons ({s['commons_title'][5:][:70]})",
               fill=(150, 150, 150), font=f3)
    os.makedirs(os.path.join(OUTC, 'sheets'), exist_ok=True)
    path = os.path.join(OUTC, 'sheets', f'{a.tag}_{a.rock}_photos.png')
    sheet.save(path)
    print(path)


if __name__ == '__main__':
    main()
