"""The karst photo sheet: each Li River photograph beside the generated tower_karst from the matching camera
(textured and grey clay), one row per view, the photo's author and licence under it. System Python (Pillow):

    python blender/tests/terrain/karst/sheet_photo_views.py --tag v1

Reads out/integration/photos/guilin_karst/ (the photos, sources.json) and out/karst/views/<tag>_<view>_{tex,clay}.png
(render_photo_views.py); writes out/karst/sheets/<tag>_guilin_photos.png. A photo is cropped to 16:9 about its
centre.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUTK = os.path.join(TN, 'out', 'karst')
PHOTOS = os.path.join(TN, 'out', 'integration', 'photos', 'guilin_karst')
VIEWS = [('riverbank', 'guilin_karst_01.jpg', 'on the river bank at 1.7 m looking along the river between towers, '
                                              '28 mm'),
         ('plain_fields', 'guilin_karst_04.jpg', 'on the plain 0.5-0.9 km from a group of towers, 1.7 m, 30 mm'),
         ('aerial', 'guilin_karst_03.jpg', 'a low oblique over the river and towers, 400 m over the tallest '
                                           'tower, 35 mm (photo: the Li from its bank)')]
W, H = 640, 360


def font(size):
    for name in ('segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def crop169(im):
    w, h = im.size
    if w / h > 16 / 9:
        nw = int(round(h * 16 / 9))
        return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = int(round(w * 9 / 16))
    return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='v1')
    a = ap.parse_args()
    src = {p['file']: p for p in json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))['photos']}
    rows = []
    f1, f2 = font(18), font(14)
    for name, photo, cap in VIEWS:
        tex = os.path.join(OUTK, 'views', f"{a.tag}_{name}_tex.png")
        clay = os.path.join(OUTK, 'views', f"{a.tag}_{name}_clay.png")
        if not os.path.exists(tex):
            continue
        row = Image.new('RGB', (3 * W + 20, H + 50), (24, 24, 28))
        row.paste(crop169(Image.open(os.path.join(PHOTOS, photo)).convert('RGB')).resize((W, H)), (0, 0))
        row.paste(Image.open(tex).convert('RGB').resize((W, H)), (W + 10, 0))
        if os.path.exists(clay):
            row.paste(Image.open(clay).convert('RGB').resize((W, H)), (2 * W + 20, 0))
        d = ImageDraw.Draw(row)
        p = src.get(photo, {})
        d.text((6, H + 4), f'{name}: {cap}', fill=(240, 220, 150), font=f1)
        d.text((6, H + 27), f"photo: {p.get('author', '?')}, {p.get('licence', '?')}, Wikimedia Commons "
                            f"({p.get('title', photo)})  |  tower_karst textured  |  grey clay", fill=(190, 190, 190),
               font=f2)
        rows.append(row)
    if not rows:
        raise SystemExit('no views rendered for tag ' + a.tag)
    head = Image.new('RGB', (rows[0].width, 60), (24, 24, 28))
    d = ImageDraw.Draw(head)
    d.text((8, 6), f'tower_karst ({a.tag}) beside photographs of the Li River at Yangshuo', fill=(255, 255, 255),
           font=font(26))
    d.text((8, 38), 'left: the photograph (16:9 crop)   middle: the generated karst from the matching camera, its '
                    'palette, rocks   right: the same, grey clay; make_sky daylight, EEVEE 960x540, 16 samples',
           fill=(200, 200, 200), font=f2)
    sheet = Image.new('RGB', (rows[0].width, 60 + sum(r.height for r in rows)), (24, 24, 28))
    sheet.paste(head, (0, 0))
    y = 60
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    os.makedirs(os.path.join(OUTK, 'sheets'), exist_ok=True)
    path = os.path.join(OUTK, 'sheets', f'{a.tag}_guilin_photos.png')
    sheet.save(path)
    print(path)


if __name__ == '__main__':
    main()
