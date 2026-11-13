"""Top-down: the reference, the field the independent review judged and the field now, per recipe (system Python):
each a hillshade of the same crop round the landform at the main level's cells, north up, lakes blue.

    python blender/tests/terrain/volcanoes_craters/hillshade_review_now.py stratovolcano=<npz> caldera=<npz> ...

The reviewed fields are the integration's judge runs (out/integration/sheets/judge/<recipe>/<recipe>_seed1.npz); a
'now' field is any field in the judge's format (h, cell, row 0 south; water), as gen.py or judge/blender_job.py save
them. Writes out/volcanoes_craters/hillshade_review_now.png."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vc  # noqa: E402  (its sheet helpers: shade, crop, CROP, REF_OF)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TN = os.path.normpath(os.path.join(HERE, '..'))
REVIEWED = os.path.join(TN, 'out', 'integration', 'sheets', 'judge')
W = 560


def tile(img, label):
    out = Image.new('RGB', (W, W + 24), (24, 24, 24))
    out.paste(img.resize((W, W), Image.LANCZOS), (0, 24))
    ImageDraw.Draw(out).text((6, 4), label, fill=(240, 220, 120), font=vc.font(15))
    return out


def field_crop(path, ref):
    d = np.load(path)
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    water = np.asarray(d['water']) if 'water' in d.files else None
    half, _c = vc.CROP.get(ref.name, (0.15 * ref.extent, (0.0, 0.0)))
    a = vc.crop(h, cell, half, (0.0, 0.0), h.shape[0] * cell)
    w = vc.crop(water, cell, half, (0.0, 0.0), h.shape[0] * cell) if water is not None else None
    return vc.shade(a, cell, None, w), cell


def main():
    rows = []
    for pair in sys.argv[1:]:
        recipe, now = pair.split('=', 1)
        ref = vc.refs.load(vc.REF_OF[recipe])
        half, c = vc.CROP.get(ref.name, (0.15 * ref.extent, (0.0, 0.0)))
        r = vc.shade(vc.crop(ref.h, ref.pixel, half, c, ref.extent), ref.pixel)
        b, cb = field_crop(os.path.join(REVIEWED, recipe, f'{recipe}_seed1.npz'), ref)
        f, cf = field_crop(now, ref)
        rows.append([tile(r, f'{recipe}: {ref.title}, {2 * half / 1000:g} km'),
                     tile(b, f'reviewed (integration), {cb:.3g} m cells'),
                     tile(f, f'now ({os.path.basename(now)}), {cf:.3g} m cells')])
    out = Image.new('RGB', (3 * W + 16, len(rows) * (W + 28) + 4), (10, 10, 10))
    for i, row in enumerate(rows):
        for j, t in enumerate(row):
            out.paste(t, (4 + j * (W + 4), 4 + i * (W + 28)))
    path = os.path.normpath(os.path.join(vc.OUT, '..', 'hillshade_review_now.png'))
    out.save(path)
    print(path)


if __name__ == '__main__':
    main()
