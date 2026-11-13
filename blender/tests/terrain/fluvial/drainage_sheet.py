"""The drainage hierarchy of generated fields beside their reference (plain Python: numpy + Pillow), for the reviewer's
"no hierarchy, a crumpled sheet" defect: each field's hillshade at the reference pixel with its channel network by
drainage area (0.1, 1 and 10 km2, thin to thick) drawn on it, and the numbers that tell a hierarchy from corduroy.

    python blender/tests/terrain/fluvial/drainage_sheet.py <out.png> ref:san_gabriel_mountains gen=<tag.npz> ...

Numbers per field (D8 drainage area on the depression-filled surface):
  density_<a>      channel length per km2 for the channels draining at least a km2 (a = 0.1, 1, 10)
  depth_trunk      the median valley depth along the channels draining 10 km2 or more: the highest ground within
                   1 km of the channel cell minus its height
  depth_small      the same along the channels draining 0.1-1 km2, within 300 m
  trunk_ratio      depth_trunk / depth_small: a range of a few deep trunk canyons with long main ridges between them
                   has trunks far deeper than its small valleys; corduroy (every ridge cut alike) has a ratio near 1
  relief_cv_2km    the coefficient of variation of the local relief in 2 km windows: even dissection is uniform
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from eidoblend.terrain.core import grid as Gd  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

TILE = 640
COLOURS = {0.1: (120, 190, 255), 1.0: (40, 120, 255), 10.0: (10, 40, 200)}


def load(spec, pixel=None):
    """(label, h float64 row 0 south, cell) for 'ref:<name>' or '<label>=<path.npz>' (gen.py's main level, box-averaged
    to `pixel` when given)."""
    if spec.startswith('ref:'):
        from judge import refs
        r = refs.load(spec[4:])
        return spec[4:], np.asarray(r.h, np.float64), float(r.pixel)
    label, path = spec.split('=', 1)
    d = np.load(path)
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    if pixel and pixel > cell * 1.0001:
        h = Gd.resample_box(h, cell, pixel)
        cell = pixel
    return label, h, cell


def drainage(h, cell):
    filled, _ = HY.fill_depressions(h)
    recv, wgt, term = HY.route(filled, method='d8')
    A = HY.accumulate(recv, wgt, term).reshape(h.shape) * cell * cell
    return A, recv[0].reshape(h.shape)


def max_filter(a, r_cells):
    """The maximum over a square window of half-width r_cells (separable running maximum)."""
    r = max(int(r_cells), 1)
    out = np.asarray(a, np.float64)
    for ax in (0, 1):
        p = np.pad(out, [(r, r) if k == ax else (0, 0) for k in range(2)], mode='edge')
        m = p[tuple(slice(0, out.shape[k]) if k != ax else slice(0, out.shape[ax]) for k in range(2))].copy()
        for s in range(1, 2 * r + 1):
            sl = tuple(slice(s, s + out.shape[ax]) if k == ax else slice(None) for k in range(2))
            m = np.maximum(m, p[sl])
        out = m
    return out


def numbers(h, cell, A):
    km2 = 1e6
    area_km2 = h.size * cell * cell / km2
    out = {}
    for a in (0.1, 1.0, 10.0):
        out[f'density_{a:g}'] = round(float(np.sum(A >= a * km2) * cell / 1000.0 / area_km2), 3)
    trunk = A >= 10 * km2
    small = (A >= 0.1 * km2) & (A < 1.0 * km2)
    m1 = max_filter(h, 1000.0 / cell)
    m3 = max_filter(h, 300.0 / cell)
    out['depth_trunk'] = round(float(np.median((m1 - h)[trunk])), 1) if trunk.any() else None
    out['depth_small'] = round(float(np.median((m3 - h)[small])), 1) if small.any() else None
    if out['depth_trunk'] and out['depth_small']:
        out['trunk_ratio'] = round(out['depth_trunk'] / out['depth_small'], 2)
    k = max(int(round(2000.0 / cell)), 2)
    n0, n1 = (h.shape[0] // k) * k, (h.shape[1] // k) * k
    b = h[:n0, :n1].reshape(n0 // k, k, n1 // k, k)
    rel = (b.max(axis=(1, 3)) - b.min(axis=(1, 3))).ravel()
    out['relief_cv_2km'] = round(float(np.std(rel) / max(np.mean(rel), 1e-9)), 3)
    out['relief_2km_p10_p50_p90'] = [round(float(v), 0) for v in np.percentile(rel, [10, 50, 90])]
    return out


def picture(h, cell, A):
    hs = IO.hillshade(h, cell)
    img = np.repeat(IO.to_u8(hs)[..., None], 3, axis=2).astype(np.float64)
    for a, col in COLOURS.items():
        m = A >= a * 1e6
        if a >= 10:
            m = m | np.roll(m, 1, 0) | np.roll(m, 1, 1)
        img[m] = 0.25 * img[m] + 0.75 * np.asarray(col, np.float64)
    im = Image.fromarray(np.ascontiguousarray(img[::-1].astype(np.uint8)))      # north up
    return im.resize((TILE, TILE), Image.LANCZOS)


def main():
    out = sys.argv[1]
    specs = sys.argv[2:]
    pixel = None
    for s in specs:
        if s.startswith('ref:'):
            from judge import refs
            pixel = float(refs.load(s[4:]).pixel)
    tiles = []
    rec = {}
    for s in specs:
        label, h, cell = load(s, pixel)
        A, _ = drainage(h, cell)
        num = numbers(h, cell, A)
        rec[label] = num
        print(label, json.dumps(num), flush=True)
        tiles.append((label, picture(h, cell, A), num))
    try:
        font = ImageFont.truetype('arial.ttf', 15)
    except OSError:
        font = ImageFont.load_default()
    W = len(tiles) * (TILE + 8) + 8
    img = Image.new('RGB', (W, TILE + 120), (22, 22, 22))
    d = ImageDraw.Draw(img)
    for i, (label, t, num) in enumerate(tiles):
        x = 8 + i * (TILE + 8)
        d.text((x, 4), label, fill=(255, 220, 120), font=font)
        img.paste(t, (x, 26))
        lines = [f"channels per km2: {num['density_0.1']} (0.1 km2), {num['density_1']} (1), {num['density_10']} (10)",
                 f"valley depth: trunks (>=10 km2, 1 km) {num['depth_trunk']} m, small (0.1-1 km2, 300 m) "
                 f"{num['depth_small']} m, ratio {num.get('trunk_ratio')}",
                 f"2 km relief p10/p50/p90 {num['relief_2km_p10_p50_p90']}, cv {num['relief_cv_2km']}"]
        for k, ln in enumerate(lines):
            d.text((x, TILE + 32 + 20 * k), ln, fill=(220, 220, 220), font=font)
    img.save(out)
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=1)
    print(out)


if __name__ == '__main__':
    main()
