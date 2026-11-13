"""Radial profiles through the highest dunes, 1:1, beside the Namib reference's (plain Python, numpy + Pillow): for the
reference and each sweep_box field, the three highest separated summits, profiles every 45 degrees out to 1.5 km, all
on one scale (2 m per pixel both ways). Reads the dune's silhouette: a concave apron flaring from a sharp summit (the
Namib) or planar faces to the floor (a pyramid).

    python profiles_box.py <box dir> label [label ...]      -> <box dir>/profiles_<first label>.png
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'reference'))
import landform_refs as R  # noqa: E402

COLS = [(200, 0, 0), (0, 120, 0), (0, 0, 200)]


def peaks(h, k=3, sep_cells=60):
    hh = h.copy()
    out = []
    for _ in range(k):
        i = int(np.argmax(hh))
        j, c = np.unravel_index(i, hh.shape)
        out.append((j, c))
        hh[max(0, j - sep_cells):j + sep_cells, max(0, c - sep_cells):c + sep_cells] = -1e9
    return out


def panel(h, cell, title, font, W=700, H=300, mpp=4.0):
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    base = float(np.percentile(h, 2))
    n0, n1 = h.shape
    for (j, i), c in zip(peaks(h, sep_cells=int(600 / cell)), COLS):
        for ang in range(0, 180, 45):
            a = math.radians(ang)
            ts = np.arange(-1300.0, 1300.0, cell)
            ii = i + ts / cell * math.cos(a)
            jj = j + ts / cell * math.sin(a)
            ok = (ii >= 0) & (jj >= 0) & (ii < n1 - 1) & (jj < n0 - 1)
            v = h[np.clip(jj.astype(int), 0, n0 - 1), np.clip(ii.astype(int), 0, n1 - 1)]
            pts = [(W / 2 + t / mpp, H - 10 - (y - base) / mpp) for t, y, o in zip(ts, v, ok) if o]
            if len(pts) > 2:
                d.line(pts, fill=c, width=1)
    d.text((5, 3), title, fill=(0, 0, 0), font=font)
    return im


def main():
    d = sys.argv[1]
    labels = sys.argv[2:]
    font = ImageFont.truetype('arial.ttf', 13)
    hr, meta = R.load('namib_star_dunes')
    ims = [panel(np.asarray(hr, np.float64)[::-1], float(meta['pixel_size_m']), 'namib_star_dunes (real, 10 m px of '
                 '30 m data), 1:1, +-1.3 km', font)]
    for lb in labels:
        z = np.load(os.path.join(d, lb + '.npz'))
        ims.append(panel(np.asarray(z['h'], np.float64), float(z['cell']), f'{lb}, 1:1, +-1.3 km', font))
    sheet = Image.new('RGB', (ims[0].width, sum(im.height for im in ims)), 'white')
    y = 0
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height
    p = os.path.join(d, f'profiles_{labels[0]}.png')
    sheet.save(p)
    print(p)


if __name__ == '__main__':
    main()
