"""Sheets of dune_lab.py's dumps (plain Python, numpy + Pillow): per variant, every level's hillshade (sun from the
north-west, 35 degrees, north up) with its sand cover tinted, crops at native resolution around the focus, and a
profile through the focus along the steepest-descent line of each level, to read crest sharpness, slip faces,
interdune floors and the small dunes level by level.

    python look_lab.py <lab dir> [label ...]      -> <lab dir>/<label>_levels.png, <label>_profiles.png
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PX = 420


def shade(h, cell, az=315.0, alt=35.0, z=1.5):
    """Hillshade of h (row 0 south) shown north up."""
    gy, gx = np.gradient(np.asarray(h, np.float64) * z, cell)   # row 0 south: gy is d/dnorth
    sl = np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, -gy)                    # the compass direction the slope faces (downhill)
    a, b = math.radians(az), math.radians(alt)
    s = np.clip(np.sin(b) * np.cos(sl) + np.cos(b) * np.sin(sl) * np.cos(a - asp), 0, 1)
    return s[::-1]


def tile(h, sand, cell, label, font, size=PX):
    s = shade(h, cell)
    rgb = np.stack([s, s, s], -1)
    if sand is not None:
        bare = (np.asarray(sand)[::-1] < 0.25)
        rgb[bare] = rgb[bare] * np.array([0.75, 0.85, 1.0])      # bare bed: blue-grey
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, size, 18), fill=(0, 0, 0))
    d.text((3, 2), label, fill=(255, 220, 120), font=font)
    return im


def crop_at(a, win, x, y, half_cells):
    x0, y0, cell, n = win
    i = int((x - x0) / cell)
    j = int((y - y0) / cell)
    n = int(n)
    i0, j0 = max(0, i - half_cells), max(0, j - half_cells)
    i1, j1 = min(n, i0 + 2 * half_cells), min(n, j0 + 2 * half_cells)
    i0, j0 = max(0, i1 - 2 * half_cells), max(0, j1 - 2 * half_cells)
    return a[j0:j1, i0:i1]


def gauss(a, sigma_cells):
    """A separable Gaussian (mirrored edges), float64."""
    a = np.asarray(a, np.float64)
    r = max(1, int(math.ceil(3.0 * sigma_cells)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / float(sigma_cells)) ** 2)
    k /= k.sum()
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(a, pad, mode='symmetric')
        n = a.shape[axis]
        a = sum(w * np.take(p, np.arange(i, i + n), axis=axis) for i, w in enumerate(k))
    return a


def flank_relief(h, win, fx, fy, radius_m=200.0, form_m=15.0):
    """The secondary relief on the dune flanks around the focus: within radius_m, on the cells sloping 8-28 degrees
    (flanks: not the floor, not the slip faces), the standard deviation of h minus its Gaussian of form_m metres (the
    small dunes and ridges left once the big dune's form is taken out), metres; and the share of those cells."""
    x0, y0, cell, n = win
    hc = crop_at(h, win, fx, fy, int(min(n // 2, radius_m / cell + 3 * form_m / cell)))
    hp = hc - gauss(hc, form_m / cell)
    gy, gx = np.gradient(hc, cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    jj, ii = np.mgrid[0:hc.shape[0], 0:hc.shape[1]]
    c = (np.array(hc.shape) - 1) / 2.0
    near = np.hypot(ii - c[1], jj - c[0]) * cell <= radius_m
    m = near & (s >= 8.0) & (s <= 28.0)
    return (float(np.std(hp[m])) if m.sum() > 50 else float('nan')), float(m.mean())


def main():
    d = sys.argv[1]
    labels = sys.argv[2:] or sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.npz'))
    font = ImageFont.truetype('arial.ttf', 13)
    for label in labels:
        z = np.load(os.path.join(d, label + '.npz'))
        fx, fy = z['focus']
        n_lv = len([k for k in z.files if k.startswith('h_')])
        for i in range(n_lv):
            win = z[f'win_{i}']
            if win[2] <= 4.0:
                rel, share = flank_relief(z[f'h_{i}'], win, fx, fy)
                print(f'{label} L{i} ({win[2]:.2f} m cells): flank relief {rel:.2f} m (std after removing a 15 m '
                      f'Gaussian, 8-28 degree cells within 200 m of the focus: {100 * share:.0f} % of them)')
        tiles = []
        for i in range(n_lv):
            h = z[f'h_{i}']
            sand = z[f'sand_{i}'] if f'sand_{i}' in z.files else None
            win = z[f'win_{i}']
            cell = float(win[2])
            tiles.append(tile(h, sand, cell, f'L{i} {win[3] * cell / 1000:.1f} km @ {cell:.2f} m', font))
            # native-resolution crop around the focus (256 cells)
            hc = crop_at(h, win, fx, fy, 128)
            sc = crop_at(sand, win, fx, fy, 128) if sand is not None else None
            tiles.append(tile(hc, sc, cell, f'L{i} crop {256 * cell:.0f} m around the focus', font))
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * (PX + 6), rows * (PX + 6)), (25, 25, 25))
        for k, im in enumerate(tiles):
            sheet.paste(im, ((k % cols) * (PX + 6), (k // cols) * (PX + 6)))
        p = os.path.join(d, f'{label}_levels.png')
        sheet.save(p)
        print(p)
        # profiles through the focus, west-east and south-north, every level that holds it
        W, H = 1400, 700
        im = Image.new('RGB', (W, H), (250, 250, 250))
        dr = ImageDraw.Draw(im)
        cols_rgb = [(0, 0, 0), (120, 120, 120), (200, 0, 0), (0, 120, 0), (0, 0, 200), (180, 0, 180), (0, 160, 160)]
        half = 300.0
        for axis, top in ((0, 0), (1, H // 2)):
            prof = []
            for i in range(n_lv):
                win = z[f'win_{i}']
                x0, y0, cell, n = win
                h = z[f'h_{i}']
                ts = np.arange(-half, half, min(cell, 1.0))
                xs = fx + (ts if axis == 0 else 0 * ts)
                ys = fy + (ts if axis == 1 else 0 * ts)
                ii = (xs - x0) / cell - 0.5
                jj = (ys - y0) / cell - 0.5
                ok = (ii >= 0) & (jj >= 0) & (ii < n - 1) & (jj < n - 1)
                if ok.mean() < 0.99:
                    continue
                i0, j0 = np.floor(ii).astype(int), np.floor(jj).astype(int)
                ti, tj = ii - i0, jj - j0
                v = (h[j0, i0] * (1 - ti) * (1 - tj) + h[j0, i0 + 1] * ti * (1 - tj) + h[j0 + 1, i0] * (1 - ti) * tj
                     + h[j0 + 1, i0 + 1] * ti * tj)
                prof.append((i, ts, v, cell))
            if not prof:
                continue
            lo = min(float(p[2].min()) for p in prof)
            hi = max(float(p[2].max()) for p in prof)
            span = max(hi - lo, 1.0)
            # equal scales: metres per pixel the same on both axes where it fits
            mpp = max(2 * half / (W - 40), span / (H // 2 - 40))
            for i, ts, v, cell in prof:
                pts = [(20 + (t + half) / mpp, top + H // 2 - 20 - (y - lo) / mpp) for t, y in zip(ts, v)]
                dr.line(pts, fill=cols_rgb[i % len(cols_rgb)], width=1)
            dr.text((25, top + 4), f"{'west-east' if axis == 0 else 'south-north'} through the focus, +-{half:.0f} m, "
                    f"1:1; colours = levels {[p[0] for p in prof]} (finest last)", fill=(0, 0, 0), font=font)
        p = os.path.join(d, f'{label}_profiles.png')
        im.save(p)
        print(p)


if __name__ == '__main__':
    main()
