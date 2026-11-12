"""A quick eye-level silhouette preview of a heightfield in numpy (no Blender, no GPU slot): a column ray-marcher
(the 'voxel space' method: each screen column marches out from the eye and draws every height span that rises above
what it has drawn), lit by the slope toward a sun 70 degrees left of the view, with aerial perspective. It is for
judging silhouettes and wall angles between proper renders (render_karst.py, the reference rig), not a substitute.

    python preview_eye.py <fields.npz> <eye.json> <out.png> [--key h_main --cell 8]
"""
import argparse
import json
import math

import numpy as np
from PIL import Image


def render(h, cell, eye, w=960, hgt=540, lens_mm=35.0, far=9000.0, eye_h=1.7, step0=1.0, sun_left_deg=70.0):
    """h: north-up metres (row 0 north), the tile centred on 0; eye: dict(x, y, look_x, look_y, look_dz)."""
    n = h.shape[0]
    half = n * cell / 2

    def sample(x, y):
        c = np.clip((x + half) / cell - 0.5, 0, n - 1.001)
        r = np.clip((half - y) / cell - 0.5, 0, n - 1.001)
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        fc, fr = c - c0, r - r0
        return ((h[r0, c0] * (1 - fc) + h[r0, c0 + 1] * fc) * (1 - fr)
                + (h[r0 + 1, c0] * (1 - fc) + h[r0 + 1, c0 + 1] * fc) * fr)
    ex, ey = eye['x'], eye['y']
    ez = float(sample(np.array([ex]), np.array([ey]))[0]) + eye_h
    hd = math.atan2(eye['look_y'] - ey, eye['look_x'] - ex)
    tz = float(sample(np.array([eye['look_x']]), np.array([eye['look_y']]))[0]) + eye.get('look_dz', 0.0)
    dist_t = math.hypot(eye['look_x'] - ex, eye['look_y'] - ey)
    pitch = math.atan2(tz - ez, dist_t)
    f = (w / 2) / math.tan(math.atan(18.0 / lens_mm))           # 36 mm sensor width
    cols = (np.arange(w) - w / 2 + 0.5) / f
    ang = hd - np.arctan(cols)
    sun = hd + math.radians(sun_left_deg)
    lx, ly, lz = math.cos(sun) * math.cos(0.66), math.sin(sun) * math.cos(0.66), math.sin(0.66)
    img = np.zeros((hgt, w, 3))
    sky_top, sky_hor = np.array([0.45, 0.62, 0.85]), np.array([0.80, 0.86, 0.93])
    yy = (np.arange(hgt)[:, None] / hgt)
    img[:] = sky_top * (1 - yy[..., None] ** 0.6) + sky_hor * (yy[..., None] ** 0.6)
    ybuf = np.full(w, hgt, float)                              # lowest drawn row per column (draw front to back)
    d = step0
    gx = np.cos(ang) / np.cos(np.arctan(cols))
    gy = np.sin(ang) / np.cos(np.arctan(cols))
    while d < far:
        x = ex + gx * d
        y = ey + gy * d
        z = sample(x, y)
        e = 1.0
        zx = (sample(x + e, y) - sample(x - e, y)) / (2 * e)
        zy = (sample(x, y + e) - sample(x, y - e)) / (2 * e)
        nl = np.sqrt(zx * zx + zy * zy + 1.0)
        shade = np.clip((-zx * lx - zy * ly + lz) / nl, 0.0, 1.0) * 0.75 + 0.22
        row = hgt / 2 - (np.arctan2(z - ez, d) - pitch) * f
        row = np.clip(row, 0, hgt)
        fog = 1.0 - math.exp(-d / 7000.0)
        col = np.array([0.55, 0.56, 0.58])[None, :] * shade[:, None]
        col = col * (1 - fog) + sky_hor[None, :] * fog
        draw = row < ybuf
        for i in np.nonzero(draw)[0]:
            img[int(row[i]):int(ybuf[i]), i] = col[i]
        ybuf = np.minimum(ybuf, row)
        d += max(step0, d * 0.004)
    return (np.clip(img, 0, 1) ** (1 / 1.1) * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('eye')
    ap.add_argument('out')
    ap.add_argument('--key', default='h_main')
    ap.add_argument('--cell', type=float, default=8.0)
    a = ap.parse_args()
    h = np.load(a.npz)[a.key].astype(np.float64)
    with open(a.eye) as f:
        eye = json.load(f)['eye']
    Image.fromarray(render(h, a.cell, eye)).save(a.out)


if __name__ == '__main__':
    main()
