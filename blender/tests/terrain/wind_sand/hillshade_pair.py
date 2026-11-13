"""The review's top-down pair for the dunes (plain Python, numpy + Pillow): the Namib reference beside a generated
main level at the same 8 km extent, north up, the review's own shading (out/review/scripts/hillshade.py: sun from the
north-west at 40 degrees), each 480 px as in out/review/hillshade/pairs_3.jpg; plus a native-resolution 4 km crop of
the generated field's centre, where the review read "polygonal plates" and "a pockmarked sheet".

    python hillshade_pair.py <field.npz> <out.png> [label]
        <field.npz>: a judge field (h, cell; row 0 south) or a dune_lab.py dump (its level at 8 km)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'out', 'review', 'scripts'))
import plain_import  # noqa: E402
plain_import.install()

from judge import refs  # noqa: E402
from hillshade import shade  # noqa: E402  (the review's own shading)

PX = 480


def load(path, extent):
    z = np.load(path)
    if 'h' in z.files:
        return np.asarray(z['h'], np.float64), float(z['cell'])
    for k in range(16):
        if f'win_{k}' in z.files and abs(float(z[f'win_{k}'][2]) * float(z[f'win_{k}'][3]) - extent) < 1.0:
            return np.asarray(z[f'h_{k}'], np.float64), float(z[f'win_{k}'][2])
    raise SystemExit(f'{path}: no level at {extent:g} m')


def tile(h, cell, label, font, size=PX):
    im = Image.fromarray((shade(h, cell)[::-1] * 255).astype(np.uint8)).convert('RGB').resize((size, size),
                                                                                             Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, size, 22), fill=(0, 0, 0))
    d.text((4, 2), label, fill=(255, 220, 120), font=font)
    return im


def main():
    path, out = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(path))[0]
    font = ImageFont.truetype('arial.ttf', 16)
    R = refs.load('namib_star_dunes')
    h, cell = load(path, R.extent)
    n = h.shape[0]
    k = int(round(2000.0 / cell))
    c = n // 2
    ims = [tile(np.asarray(R.h, np.float64), float(R.pixel), f'namib_star_dunes (real, 8 km, {R.pixel:g} m px)', font),
           tile(h, cell, f'{label} (8 km, {cell:.1f} m cells)', font),
           tile(h[c - k:c + k, c - k:c + k], cell, f'{label}: centre 4 km at native cells', font)]
    sheet = Image.new('RGB', (3 * PX + 20, PX), (0, 0, 0))
    for i, im in enumerate(ims):
        sheet.paste(im, (i * (PX + 10), 0))
    sheet.save(out, quality=90)
    print(out)


if __name__ == '__main__':
    main()
