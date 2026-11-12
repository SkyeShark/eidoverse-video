"""The regimes sheet (system Python: numpy + Pillow): one row per dune kind, a hillshade per snapshot from
run_regimes.py, the wind regime drawn as arrows, and the measures that tell the families apart printed under each.

    python blender/tests/terrain/wind_sand/sheet_regimes.py [--tag name] [--px 300]

Writes out/wind_sand/regimes<tag>_sheet.png. Hillshades are lit from the north-west (315 degrees), north up.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'wind_sand'))
KINDS = ('barchan', 'transverse', 'linear', 'star')


def hillshade(h, cell, az=315.0, alt=40.0, z=1.0):
    gy, gx = np.gradient(np.asarray(h, np.float64) * z, cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, -gy)                       # compass the slope faces
    a, e = math.radians(az), math.radians(alt)
    sh = np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(sh, 0, 1)


def font(size):
    for f in ('consola.ttf', 'DejaVuSansMono.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def arrows(draw, x, y, r, winds):
    tot = sum(w for _, w in winds)
    draw.ellipse([x - r, y - r, x + r, y + r], outline=(90, 90, 90))
    for d, w in winds:
        a = math.radians(d)
        # the wind comes FROM d: draw an arrow from the rim at d toward the centre and past it
        sx, sy = x + r * math.sin(a), y - r * math.cos(a)
        ex, ey = x - 0.6 * r * math.sin(a), y + 0.6 * r * math.cos(a)
        width = max(1, int(round(4 * w / tot * len(winds))))
        draw.line([sx, sy, ex, ey], fill=(200, 60, 40), width=width)
        ha = math.atan2(ey - sy, ex - sx)
        for s in (-0.5, 0.5):
            draw.line([ex, ey, ex - 8 * math.cos(ha + s), ey - 8 * math.sin(ha + s)], fill=(200, 60, 40), width=width)


def main():
    a = sys.argv[1:]
    tag = a[a.index('--tag') + 1] if '--tag' in a else ''
    px = int(a[a.index('--px') + 1]) if '--px' in a else 300
    src = os.path.join(OUT, 'regimes' + (('_' + tag) if tag else ''))
    rows = []
    for k in KINDS:
        p = os.path.join(src, f'{k}.npz')
        if os.path.exists(p):
            rows.append((k, np.load(p), json.load(open(os.path.join(src, f'{k}.json')))))
    if not rows:
        raise SystemExit(f'no runs in {src}')
    ncol = max(len(r[1]['iters']) for r in rows)
    lab_w, txt_h, pad = 170, 64, 6
    W = lab_w + ncol * (px + pad)
    H = len(rows) * (px + txt_h + pad) + 30
    img = Image.new('RGB', (W, H), (18, 18, 20))
    d = ImageDraw.Draw(img)
    f1, f2 = font(15), font(12)
    d.text((8, 6), f'wind regimes on a periodic box ({src}); hillshade lit from 315 deg, north up; arrows: winds '
                   f'(from the rim)', fill=(220, 220, 220), font=f2)
    y = 30
    for kind, z, js in rows:
        cell = float(z['cell'])
        winds = js['params']['winds']
        d.text((8, y + 4), kind, fill=(255, 210, 120), font=f1)
        d.text((8, y + 24), f"sand {js['params']['sand_m']:g} m\nspacing {js['params']['spacing_m']:g} m\n"
                            f"{js['n']} x {cell:g} m", fill=(200, 200, 200), font=f2)
        arrows(d, 80, y + 130, 40, winds)
        for c in range(len(z['iters'])):
            hs = hillshade(z['h'][c], cell)
            im = Image.fromarray((hs[::-1] * 255).astype(np.uint8)).resize((px, px), Image.BILINEAR)
            x = lab_w + c * (px + pad)
            img.paste(im, (x, y))
            m = js['measures'][c]
            t = (f"{m['iters']} it  relief {m['relief_m']:.1f} m  p99 {m['slope_p99']:.1f}\n"
                 f"lee peaks {m['lee_peaks']} {[int(v) for v in m['lee_peak_dirs']]}\n"
                 f"grad {m['gradient_dir_deg']:.0f} coh {m['coherence']:.2f} cover {m.get('sand_cover', 0):.2f}\n"
                 f"lee {m.get('lee_lee_share', 0):.2f} stoss {m.get('lee_stoss_share', 0):.2f} sp {m['spacing_m']:.0f}")
            d.text((x + 2, y + px + 2), t, fill=(210, 210, 210), font=f2)
        y += px + txt_h + pad
    path = os.path.join(OUT, 'regimes' + (('_' + tag) if tag else '') + '_sheet.png')
    img.save(path)
    print(path)


if __name__ == '__main__':
    main()
