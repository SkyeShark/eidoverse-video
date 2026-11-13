"""Contact sheet of sweep_box.py's variants (plain Python, numpy + Pillow): per variant its final field's hillshade
(sun north-west at 35 degrees, north up; bare bed tinted blue-grey), a native-resolution crop of its centre, and its
snapshots, with the numbers that matter in the label.

    python look_box.py <box dir> [label ...]      -> <box dir>/sheet.png (or sheet_<first label>.png)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from look_lab import shade  # noqa: E402

PX = 360


def tile(h, sand, cell, label, font, size=PX):
    s = shade(h, cell)
    rgb = np.stack([s, s, s], -1)
    if sand is not None:
        bare = np.asarray(sand)[::-1] < 0.25
        rgb[bare] = rgb[bare] * np.array([0.75, 0.85, 1.0])
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, size, 16), fill=(0, 0, 0))
    d.text((3, 1), label, fill=(255, 220, 120), font=font)
    return im


def main():
    d = sys.argv[1]
    labels = sys.argv[2:] or sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.npz'))
    font = ImageFont.truetype('arial.ttf', 12)
    rows = []
    for label in labels:
        z = np.load(os.path.join(d, label + '.npz'))
        meta = json.load(open(os.path.join(d, label + '.json'), encoding='utf-8'))
        m = meta['measures'][-1]
        cell = float(z['cell'])
        h, sand = z['h'], z['sand']
        n = h.shape[0]
        ims = [tile(h, sand, cell, f'{label}: {m["iters"]} it, {m["seconds"]} s', font)]
        c = n // 2
        k = min(n // 2, 128)
        ims.append(tile(h[c - k:c + k, c - k:c + k], sand[c - k:c + k, c - k:c + k], cell,
                        f'centre {2 * k * cell:.0f} m: dunes {m["dune_height_m"]:.0f} m, cover {m["sand_cover"]:.2f}',
                        font))
        for s, mm in zip(z['snaps'], meta['measures'][:-1]):
            ims.append(tile(s, None, cell, f'{mm["iters"]} it: {mm["dune_height_m"]:.0f} m, sp {mm["spacing_m"]:.0f}',
                            font))
        row = Image.new('RGB', (len(ims) * (PX + 4), PX + 22), (25, 25, 25))
        for i, im in enumerate(ims):
            row.paste(im, (i * (PX + 4), 0))
        dr = ImageDraw.Draw(row)
        dr.text((3, PX + 4), f'spacing {m["spacing_m"]:.0f} m, p99 {m["slope_p99"]:.1f}, p50 {m["slope_p50"]:.1f}, '
                f'<5deg {m.get("frac_lt5", float("nan")):.2f}, '
                f'lee peaks {m["lee_peaks"]} {m["lee_peak_dirs"]}, coherence {m["coherence"]:.2f}, bodies '
                f'{m["bodies"]}; set {json.dumps(meta["variant"].get("set", {}))[:150]}', fill=(220, 220, 220),
                font=font)
        rows.append(row)
    W = max(r.width for r in rows)
    sheet = Image.new('RGB', (W, sum(r.height + 6 for r in rows)), (15, 15, 15))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 6
    p = os.path.join(d, 'sheet.png' if len(sys.argv) <= 2 else f'sheet_{labels[0]}.png')
    sheet.save(p)
    print(p)


if __name__ == '__main__':
    main()
