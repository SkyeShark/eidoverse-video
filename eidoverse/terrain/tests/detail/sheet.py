"""A row of pictures with a title, for the detail package's view sheets (tests/detail/views.mjs). Pictures only: no
number is computed here, so it runs in any Python with Pillow (the system's, whose user site holds it; Blender's
bundled Python has none).

    python eidoverse/terrain/tests/detail/sheet.py --out <png> [--title T] <png> [<png> ...]

A missing picture is drawn as a grey panel saying so. Each panel is scaled to 640 pixels wide.
"""
import argparse
import os
import site
import sys

sys.dont_write_bytecode = True
sys.path.append(site.getusersitepackages())                  # Pillow, where it lives in the user's site
from PIL import Image, ImageDraw  # noqa: E402

W = 640


def panel(path):
    if path and os.path.exists(path):
        im = Image.open(path).convert('RGB')
        return im.resize((W, round(im.height * W / im.width)))
    im = Image.new('RGB', (W, 360), (90, 90, 90))
    ImageDraw.Draw(im).text((12, 12), f'not rendered: {os.path.basename(path or "")}', fill=(230, 230, 230))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('pictures', nargs='+')
    a = ap.parse_args()
    ims = [panel(p) for p in a.pictures]
    h = max(im.height for im in ims)
    top = 28 if a.title else 0
    sheet = Image.new('RGB', (W * len(ims) + 8 * (len(ims) - 1), h + top + 22), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    if a.title:
        d.text((8, 8), a.title, fill=(235, 235, 235))
    for k, (im, p) in enumerate(zip(ims, a.pictures)):
        x = k * (W + 8)
        sheet.paste(im, (x, top))
        d.text((x + 6, top + h + 5), os.path.basename(p), fill=(200, 200, 200))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    sheet.save(a.out)
    print(f'[sheet] {a.out}')


if __name__ == '__main__':
    main()
