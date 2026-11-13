"""Top-down before and after (system Python): per recipe, the reference's hillshade round the landform beside the
same crop of an earlier run's main level and of the new run's, at the main level's cells, north up, lakes blue.

    python blender/tests/terrain/volcanoes_craters/hillshade_before_after.py --before stratovolcano=r14 ... \\
           --after r21 [--out <png>]

Writes out/volcanoes_craters/hillshade_before_after_<after>.png."""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vc  # noqa: E402  (its sheet helpers: shade, crop, CROP, REF_OF)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

W = 600


def tile(img, label):
    out = Image.new('RGB', (W, W + 24), (24, 24, 24))
    out.paste(img.resize((W, W), Image.LANCZOS), (0, 24))
    ImageDraw.Draw(out).text((6, 4), label, fill=(240, 220, 120), font=vc.font(15))
    return out


def gen_crop(tag, ref):
    d = np.load(os.path.join(vc.OUT, tag + '.npz'))
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    water = np.asarray(d['water']) if 'water' in d.files else None
    half, _c = vc.CROP.get(ref.name, (0.15 * ref.extent, (0.0, 0.0)))
    a = vc.crop(h, cell, half, (0.0, 0.0), h.shape[0] * cell)
    w = vc.crop(water, cell, half, (0.0, 0.0), h.shape[0] * cell) if water is not None else None
    return vc.shade(a, cell, None, w), cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', nargs='+', required=True, help='recipe=tag pairs')
    ap.add_argument('--after', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    rows = []
    for pair in a.before:
        recipe, before = pair.split('=')
        ref = vc.refs.load(vc.REF_OF[recipe])
        half, c = vc.CROP.get(ref.name, (0.15 * ref.extent, (0.0, 0.0)))
        r = vc.shade(vc.crop(ref.h, ref.pixel, half, c, ref.extent), ref.pixel)
        b, cb = gen_crop(f'{before}_{recipe}_s1', ref)
        f, cf = gen_crop(f'{a.after}_{recipe}_s1', ref)
        rows.append([tile(r, f'{recipe}: {ref.title}, {2 * half / 1000:g} km'),
                     tile(b, f'before ({before}), {cb:.3g} m cells'), tile(f, f'after ({a.after}), {cf:.3g} m cells')])
    out = Image.new('RGB', (3 * W + 16, len(rows) * (W + 28) + 4), (10, 10, 10))
    for i, row in enumerate(rows):
        for j, t in enumerate(row):
            out.paste(t, (4 + j * (W + 4), 4 + i * (W + 28)))
    path = a.out or os.path.join(vc.OUT, '..', f'hillshade_before_after_{a.after}.png')
    out.save(os.path.normpath(path))
    print(os.path.normpath(path))


if __name__ == '__main__':
    main()
