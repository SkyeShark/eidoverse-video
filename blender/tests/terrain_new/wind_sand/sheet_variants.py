"""A quick sheet of judge_dunes.py variants (system Python: numpy + Pillow): per variant, the main level's hillshade
(north up, lit from 315 degrees) beside its reference's at the same scale, with the judge's failing rows printed.

    python blender/tests/terrain_new/wind_sand/sheet_variants.py --tag v1 [--labels a,b] [--px 360]

Writes out/wind_sand/variants<tag>_sheet.png.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_NEW = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TERRAIN_NEW, 'core'))
sys.path.insert(0, TERRAIN_NEW)
sys.path.insert(0, HERE)
import plain_import  # noqa: E402
plain_import.install()
from judge import refs  # noqa: E402
from sheet_regimes import hillshade, font  # noqa: E402

OUT = os.path.join(TERRAIN_NEW, 'out', 'wind_sand')


def tile(h, cell, px):
    hs = hillshade(h, cell)
    return Image.fromarray((hs[::-1] * 255).astype(np.uint8)).resize((px, px), Image.BILINEAR)


def main():
    a = sys.argv[1:]
    tag = a[a.index('--tag') + 1] if '--tag' in a else ''
    px = int(a[a.index('--px') + 1]) if '--px' in a else 360
    src = os.path.join(OUT, 'variants' + (('_' + tag) if tag else ''))
    labels = a[a.index('--labels') + 1].split(',') if '--labels' in a else \
        sorted(f[:-5] for f in os.listdir(src) if f.endswith('.json'))
    rows = []
    for lb in labels:
        js = json.load(open(os.path.join(src, lb + '.json')))
        z = np.load(os.path.join(src, lb + '.npz'))
        rows.append((lb, js, z))
    txt_w = 430
    W = 2 * (px + 8) + txt_w
    H = len(rows) * (px + 10) + 24
    img = Image.new('RGB', (W, H), (18, 18, 20))
    d = ImageDraw.Draw(img)
    f1, f2 = font(14), font(12)
    d.text((6, 4), f'dunes variants ({src}): generated main level | reference, hillshade lit from 315, north up',
           fill=(220, 220, 220), font=f2)
    y = 24
    for lb, js, z in rows:
        img.paste(tile(z['h'].astype(np.float64), float(z['cell']), px), (0, y))
        v = js.get('verdict')
        if v:
            r = refs.load(v['reference'])
            img.paste(tile(r.h, r.pixel, px), (px + 8, y))
        x = 2 * (px + 8) + 6
        d.text((x, y), lb, fill=(255, 210, 120), font=f1)
        lines = [f"{js['seconds']} s, dunes {js['dune_height_m']:.0f} m (target {js['target']['height_m']:.0f}), "
                 f"spacing target {js['target']['spacing_m']:.0f} m"]
        if v:
            lines.append(f"{'PASS' if v['passed'] else 'FAIL'} vs {v['reference']} at {v['pixel_m']:g} m")
            for row in v['rows']:
                if row.get('passed') is None:
                    continue
                g, rr = row.get('gen'), row.get('ref')
                gs = f'{g:.3g}' if isinstance(g, (int, float)) and g is not None else str(g)
                rs = f'{rr:.3g}' if isinstance(rr, (int, float)) and rr is not None else str(rr)
                lines.append(f"{'  ' if row['passed'] else 'X '}{row['metric'][:24]:24s} {gs:>7s} {rs:>7s} {row['band']}")
        d.text((x, y + 20), '\n'.join(lines), fill=(210, 210, 210), font=f2)
        y += px + 10
    path = os.path.join(OUT, 'variants' + (('_' + tag) if tag else '') + '_sheet.png')
    img.save(path)
    print(path)


if __name__ == '__main__':
    main()
