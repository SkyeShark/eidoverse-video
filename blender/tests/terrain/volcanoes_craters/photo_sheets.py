"""The photo-matched compare sheets: per place, one row per photograph - the photograph, the real DEM re-shot from
the same camera (real_place), and the generated recipe from the matching camera (render_photo_views.py) - with the
photo's title, author and licence, the camera (recorded or estimated) and the lens under each row.

    python blender/tests/terrain/volcanoes_craters/photo_sheets.py [--place mount_fuji] [--tex]

Writes out/volcanoes_craters/photo_views/<place>_photo_sheet.png (and _tex with --tex: the textured renders).
"""
import argparse
import json
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.normpath(os.path.join(TN, 'out', 'volcanoes_craters', 'photo_views'))
PHOTOS = os.path.normpath(os.path.join(TN, 'out', 'volcanoes_craters', 'photos'))
PLACES = ('mount_fuji', 'crater_lake', 'meteor_crater', 'sp_crater')
TITLE = {'mount_fuji': 'stratovolcano vs Mount Fuji', 'crater_lake': 'caldera vs Crater Lake',
         'meteor_crater': 'impact_crater vs Meteor Crater', 'sp_crater': 'cinder_cones vs SP Crater'}


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit(im, w, h):
    im = im.convert('RGB')
    s = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def views_of(place):
    out = {}
    d = os.path.join(OUT, place)
    for fn in os.listdir(d) if os.path.isdir(d) else []:
        if fn.startswith('views_') and fn.endswith('.json'):
            with open(os.path.join(d, fn), encoding='utf-8') as f:
                out.update(json.load(f).get('views', {}))
    return out


def sheet(place, tex=False):
    with open(os.path.join(PHOTOS, place, 'sources.json'), encoding='utf-8') as f:
        photos = json.load(f)['photos']
    views = views_of(place)
    W, H = 600, 400
    rows = []
    for p in photos:
        stem = os.path.splitext(p['file'])[0]
        sfx = '_tex' if tex else ''
        cells = [('photograph', os.path.join(PHOTOS, place, p['file'])),
                 ('real DEM, same camera (real_place, clay)', os.path.join(OUT, place, f'{stem}_real{sfx}.png')),
                 (f'generated ({TITLE[place].split(" vs ")[0]}), matching camera',
                  os.path.join(OUT, place, f'{stem}_gen{sfx}.png'))]
        if not any(os.path.exists(c[1]) for c in cells[1:]):
            continue
        v = views.get(f'{stem}_gen{sfx}.png') or views.get(f'{stem}_real{sfx}.png') or {}
        cam = ('camera estimated from the image' if p.get('camera_estimated') else 'camera from the file') + \
            (f", {v['camera_rel'][0] / 1000:.1f} km east, {v['camera_rel'][1] / 1000:.1f} km north of the "
             f"landform, heading {v['heading_deg']:.0f}, pitch {v['pitch_deg']:.1f}, {v['lens_mm']:.0f} mm"
             if v else '')
        for which in ('real', 'gen'):
            mv = (views.get(f'{stem}_{which}{sfx}.png') or {}).get('camera_moved')
            if mv:
                cam += (f"; {'real' if which == 'real' else 'generated'} camera moved {mv['bearing_deg']:+.1f} deg "
                        f"round the landform, distance x {mv['distance_factor']:.2f}, for an open view")
        lines = [f"{p['title'][5:]} - {p['author']} - {p['licence']} ({p.get('licence_url') or ''})",
                 f"{p['note']}; {cam}"]
        rows.append((cells, lines))
    if not rows:
        print(f'{place}: no renders yet')
        return None
    f, fs = font(15), font(13)
    head = 40
    img = Image.new('RGB', (3 * (W + 10) + 10, head + len(rows) * (H + 74) + 10), (22, 22, 22))
    dr = ImageDraw.Draw(img)
    dr.text((10, 10), f'{TITLE[place]}: photographs beside the real DEM and the recipe from the same camera '
                      f'({"textured" if tex else "grey clay"}, make_sky daylight)', fill=(255, 255, 255),
            font=font(18))
    y = head
    for cells, lines in rows:
        for k, (label, path) in enumerate(cells):
            x = 10 + k * (W + 10)
            dr.text((x, y), label, fill=(230, 230, 230), font=fs)
            if os.path.exists(path):
                im = fit(Image.open(path), W, H)
                img.paste(im, (x + (W - im.width) // 2, y + 18))
            else:
                dr.text((x + 10, y + 40), 'not rendered', fill=(200, 80, 80), font=f)
        wrapped = [w for ln in lines for w in textwrap.wrap(ln, 225)][:3]
        for i, ln in enumerate(wrapped):
            dr.text((10, y + 18 + H + 6 + 17 * i), ln, fill=(190, 190, 190), font=fs)
        y += H + 74
    path = os.path.join(OUT, f'{place}_photo_sheet{"_tex" if tex else ""}.png')
    img.save(path)
    print(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--place')
    ap.add_argument('--tex', action='store_true')
    a = ap.parse_args()
    for place in ([a.place] if a.place else PLACES):
        sheet(place, a.tex)


if __name__ == '__main__':
    main()
