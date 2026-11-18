"""Hillshades of the main level, the port's save beside the Blender floor run's save of the same recipe and seed (the
fluvial package's looking aid, PORT_PLAN.md 8.1 "Looking"): one row per seed, north up, the same light (from the
north-west, 45 degrees up) and vertical exaggeration on both, so drainage density, valley spacing, ridge texture
and the floors read side by side. A picture of each save's own heights; it judges nothing.

    python eidoverse/terrain/tests/fluvial/hillshade_sheet.py --recipe fluvial_range --seeds 1,2 \
        --port <saves dir> --blender <parity key dir> --out <png>

Needs numpy and Pillow (a picture, made in any Python that has them).
"""
import argparse
import json
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def main_h(npz_path):
    base = npz_path[:-4]
    with open(base + '.json') as fh:
        info = json.load(fh)
    main = next(lv for lv in info['plan'] if lv['role'] == 'main')
    with zipfile.ZipFile(npz_path) as z:
        name = f"L{main['index']}__f__h.npy"
        with z.open(name) as fh:
            a = np.lib.format.read_array(fh)
    return a.astype(np.float64), float(main['cell'])


def hillshade(h, cell, z=2.0, az=315.0, alt=45.0):
    gy, gx = np.gradient(h * z, cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, e = np.radians(az), np.radians(alt)
    s = np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(s, 0, 1)[::-1]                       # row 0 is south: north up


def tile(h, cell, title, w=512):
    im = Image.fromarray((hillshade(h, cell) * 255).astype(np.uint8), 'L').convert('RGB')
    im = im.resize((w, w), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('arial.ttf', 16)
    except OSError:
        f = ImageFont.load_default()
    d.rectangle([0, 0, w, 22], fill=(0, 0, 0))
    d.text((6, 3), title, fill=(255, 255, 255), font=f)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--seeds', default='1,2')
    ap.add_argument('--port', required=True, help="the port's saves: <dir>/<recipe>_s<seed>.npz")
    ap.add_argument('--blender', required=True, help='the parity key folder: <dir>/<recipe>_s<seed>_draft/base/terrain.npz')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = []
    for s in a.seeds.split(','):
        bp = f'{a.blender}/{a.recipe}_s{s}_draft/base/terrain.npz'
        pp = f'{a.port}/{a.recipe}_s{s}.npz'
        if not (os.path.exists(bp) and os.path.exists(pp)):
            continue
        hb, cb = main_h(bp)
        hp, cp = main_h(pp)
        rows.append([tile(hb, cb, f'{a.recipe} seed {s}: Blender (relief {np.ptp(hb):.0f} m)'),
                     tile(hp, cp, f'{a.recipe} seed {s}: the port (relief {np.ptp(hp):.0f} m)')])
    if not rows:
        print('[hillshade] no pairs of saves')
        return
    sheet = Image.new('RGB', (1024, 512 * len(rows)), (0, 0, 0))
    for r, (b, p) in enumerate(rows):
        sheet.paste(b, (0, 512 * r))
        sheet.paste(p, (512, 512 * r))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f'[hillshade] {a.out}: {len(rows)} seeds')


if __name__ == '__main__':
    main()
