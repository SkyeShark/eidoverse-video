"""The fluvial package's look sheet (PORT_PLAN.md 5.3 "look", 8.1 "Looking"): per recipe, the reference place's own
renders (the Blender edition's reference/renders: the real DEM, top hillshade and 45-degree aerial), the Blender
floor run's terrain and the port's terrain of the same recipe and seed rendered from the same cameras by the port's
renderer (tests/judge/views.mjs), and the place's photographs (CC0 / public domain, with their sources.json) under
them. It lays pictures out and computes nothing.

    python eidoverse/terrain/tests/fluvial/sheet.py --recipe fluvial_range --reference san_gabriel_mountains \
        --renders <views out> --blender-label <label> --port-label <label> --photos <photos dir> --out <png>

Needs Pillow (any Python that has it: a picture layout, no numbers).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

W = 640


def fit(path, w=W):
    im = Image.open(path).convert('RGB')
    h = int(round(im.height * w / im.width))
    return im.resize((w, h), Image.LANCZOS)


def label(im, text):
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('arial.ttf', 18)
    except OSError:
        f = ImageFont.load_default()
    d.rectangle([0, 0, im.width, 26], fill=(0, 0, 0))
    d.text((8, 4), text, fill=(255, 255, 255), font=f)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--reference', required=True)
    ap.add_argument('--reference-renders', required=True, help="the Blender edition's reference/renders")
    ap.add_argument('--renders', required=True, help="views.mjs's output folder")
    ap.add_argument('--blender-label', required=True)
    ap.add_argument('--port-label', required=True)
    ap.add_argument('--photos', default=None)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = []
    for kind, name in (('top', 'top_hillshade'), ('aerial', 'aerial_45deg')):
        cells = []
        for title, path in ((f'{a.reference}: the real DEM ({kind})', f'{a.reference_renders}/{a.reference}_{name}.png'),
                            (f'{a.recipe}: Blender ({kind})', f'{a.renders}/{a.blender_label}_{name}.png'),
                            (f'{a.recipe}: the port ({kind})', f'{a.renders}/{a.port_label}_{name}.png')):
            if os.path.exists(path):
                cells.append(label(fit(path), title))
        if cells:
            rows.append(cells)
    if a.photos and os.path.isdir(a.photos):
        src = {}
        sj = os.path.join(a.photos, 'sources.json')
        if os.path.exists(sj):
            with open(sj) as fh:
                src = json.load(fh)
        photos = sorted(p for p in os.listdir(a.photos) if p.lower().endswith(('.jpg', '.jpeg', '.png')))[:3]
        if photos:
            rows.append([label(fit(os.path.join(a.photos, p)), f'photograph: {p}') for p in photos])
    height = sum(max(c.height for c in r) for r in rows)
    sheet = Image.new('RGB', (3 * W, height), (30, 30, 30))
    y = 0
    for r in rows:
        for i, c in enumerate(r):
            sheet.paste(c, (i * W, y))
        y += max(c.height for c in r)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f'[sheet] {a.out}: {len(rows)} rows')


if __name__ == '__main__':
    main()
