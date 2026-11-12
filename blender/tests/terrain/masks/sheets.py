"""Mask sheets on the real reference DEMs: every mask of the main tile painted over its hillshade, beside a
material-preview composite, for an environment artist to read against the landform.

    python blender/tests/terrain/masks/sheets.py [--only lauterbrunnen,mount_fuji]

Writes into blender/tests/terrain/out/masks/:
    <name>_masks_tile.png      the whole main tile, one panel per mask (north up, the hillshade lit from the NW)
    <name>_masks_detail.png    the same panels on a 2 km-wide crop (Fuji 10 km) at one pixel per cell or finer:
                               where the masks meet the features (benches, gullies, wall feet)
    <name>_mask_stats.json     per mask: min, median, mean, max, the share of cells over 0.5, and the seconds

Overlays: a sequential mask (height, slope, flow, wetness, occlusion) covers the panel through a viridis-like ramp
at 70 %; a presence mask (rock, snow, channels...) paints its colour with opacity = mask, so where it is 0 the bare
hillshade shows; signed curvature is red (convex) / blue (concave) with opacity = |bend|. The composite is a flat
false-colour material driven only by the masks (grass, soil, rock, scree, snow, water by the rules a palette would
use), lit by the hillshade and darkened by the occlusion: a preview of what the surfacing package will build.
"""
import argparse
import json
import math
import os
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import fixtures as F

M = F.M
R = F.R
FONT = 'C:/Windows/Fonts/consola.ttf'
VIRIDIS = np.array([(0.267, 0.005, 0.329), (0.230, 0.322, 0.546), (0.128, 0.567, 0.551), (0.369, 0.789, 0.383),
                    (0.993, 0.906, 0.144)])
# per reference: the crop centre (local metres east, north of the tile centre) and side
DETAIL = {
    'lauterbrunnen': dict(at=(-700.0, -500.0), side=2048.0),
    'grand_canyon_toroweap': dict(at=(250.0, 400.0), side=2048.0),
    'mount_fuji': dict(at=(0.0, 0.0), side=10240.0),
    'badlands_sd': dict(at=(0.0, 0.0), side=768.0),
    'great_sand_dunes': dict(at=(0.0, 0.0), side=1280.0),
}
PALETTES = F.PREVIEW_PALETTES
# (panel title, kind, mask or callable, note)
PANELS = [
    ('hillshade', 'none', None, 'the DEM, lit from the north-west'),
    ('composite', 'composite', None, 'masks as a flat material'),
    ('height_norm', 'seq', 'height_norm', '0-1 over the tile'),
    ('slope', 'seq_deg', 'slope', 'degrees, 0-70 ramp'),
    ('aspect', 'aspect', 'aspect', 'hue = facing (N red, E yellow, S cyan, W blue)'),
    ('curv 2 x cell', 'curv', ('convex', 'concave'), 'red convex, blue concave'),
    ('curv 20 m', 'curv', ('convex_20m', 'concave_20m'), 'red convex, blue concave'),
    ('curv 200 m', 'curv', ('convex_200m', 'concave_200m'), 'scale picks the feature'),
    ('peaks', 'presence', 'peaks', 'high and convex'),
    ('flow', 'seq', 'flow', 'log10 drainage area'),
    ('channels', 'presence', 'channels', 'area over the level threshold'),
    ('wetness', 'seq', 'wetness', 'ln(a / tan slope)'),
    ('occlusion', 'seq', 'occlusion', 'sky view within 500 m'),
    ('rock', 'presence', 'rock', 'slope over 34-46 deg'),
    ('rock_toe', 'presence', 'rock_toe', 'the foot below rock (violet)'),
    ('snow', 'presence', 'snow', 'snowline, aspect, hollows'),
    ('vegetation', 'presence', 'vegetation', 'suitability'),
    ('northness', 'div', 'northness', 'north-facing +1 (red)'),
]
COLOURS = {'peaks': (1.0, 0.15, 0.55), 'channels': (0.05, 0.35, 1.0), 'rock': (1.0, 0.45, 0.05),
           'rock_toe': (0.55, 0.15, 0.95), 'snow': (0.1, 0.95, 1.0), 'vegetation': (0.1, 0.85, 0.15)}
NAMES = list(M.DEFAULT_NAMES) + ['convex_200m', 'concave_200m']


def ramp(v, stops=VIRIDIS):
    v = np.clip(np.asarray(v, np.float64), 0.0, 1.0) * (len(stops) - 1)
    i = np.minimum(np.floor(v).astype(int), len(stops) - 2)
    t = (v - i)[..., None]
    return stops[i] * (1 - t) + stops[i + 1] * t


def hsv_hue(hue, sat, val):
    h6 = (np.asarray(hue) % 1.0) * 6.0
    c = val * sat
    x = c * (1 - np.abs(h6 % 2 - 1))
    z = np.zeros_like(c)
    sel = [(c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)]
    k = np.minimum(h6.astype(int), 5)
    rgb = np.zeros(hue.shape + (3,))
    for i, (r, g, b) in enumerate(sel):
        m = k == i
        rgb[m] = np.stack([r[m], g[m], b[m]], -1)
    return rgb + (val - c)[..., None]


def composite(m, hs, palette):
    P = PALETTES[palette]
    get = lambda k: np.asarray(m[k], np.float64) if k in m else np.zeros_like(hs)   # noqa: E731
    col = np.broadcast_to(np.array(P['soil']), hs.shape + (3,)).copy()
    wet = get('wetness')
    col *= (1.0 - 0.25 * wet)[..., None]
    for key, layer in (('vegetation', 'veg'), ('rock_toe', 'scree'), ('rock', 'rock'), ('channels', 'water'),
                       ('snow', 'snow')):
        w = get(key)
        if key == 'vegetation':
            w = np.clip(w * P['veg_k'] * 1.2, 0, 1)
        if key == 'channels':
            w = w * 0.8
        col = col * (1 - w[..., None]) + np.array(P[layer]) * w[..., None]
    water = (get('water') > 0)[..., None] if 'water' in m else np.zeros(hs.shape + (1,), bool)
    col = np.where(water, np.array(P['water']), col)
    light = (0.55 + 0.75 * hs) * (0.7 + 0.3 * get('occlusion') if 'occlusion' in m else 1.0)
    return np.clip(col * light[..., None], 0, 1) ** (1 / 1.25)


def panel_rgb(kind, key, m, hs, palette):
    grey = np.repeat((0.15 + 0.8 * hs)[..., None], 3, -1)
    if kind == 'none':
        return grey, ''
    if kind == 'composite':
        return composite(m, hs, palette), ''
    if kind == 'curv':
        cv, cc = (np.asarray(m[k], np.float64) if k in m else np.zeros_like(hs) for k in key)
        out = grey * (1 - 0.85 * cv[..., None]) + np.array([1.0, 0.2, 0.1]) * 0.85 * cv[..., None]
        out = out * (1 - 0.85 * cc[..., None]) + np.array([0.1, 0.4, 1.0]) * 0.85 * cc[..., None]
        return out, f'convex>0.5 {np.mean(cv > 0.5):.0%}  concave>0.5 {np.mean(cc > 0.5):.0%}'
    if key not in m:
        return grey * 0.6, 'skipped: ' + m.skipped.get(key, 'not made')
    v = np.asarray(m[key], np.float64)
    if kind == 'seq':
        return grey * 0.3 + ramp(v) * 0.7, f'mean {v.mean():.2f}  p5 {np.percentile(v, 5):.2f}  p95 {np.percentile(v, 95):.2f}'
    if kind == 'seq_deg':
        return grey * 0.3 + ramp(v / 70.0) * 0.7, f'p50 {np.median(v):.1f}  p99 {np.percentile(v, 99):.1f} deg'
    if kind == 'aspect':
        fade = M.smoothstep(1.0, 3.0, m['slope']).astype(np.float64)
        col = hsv_hue(v / 360.0 + 0.0, np.full_like(v, 0.85), np.full_like(v, 1.0))
        a = 0.75 * fade[..., None]
        return grey * (1 - a) + col * a, ''
    if kind == 'div':
        pos, neg = np.clip(v, 0, 1)[..., None], np.clip(-v, 0, 1)[..., None]
        out = grey * (1 - 0.7 * pos) + np.array([1.0, 0.25, 0.1]) * 0.7 * pos
        return out * (1 - 0.7 * neg) + np.array([0.1, 0.4, 1.0]) * 0.7 * neg, ''
    c = np.array(COLOURS.get(key, (1.0, 0.5, 0.0)))
    a = 0.85 * np.clip(v, 0, 1)[..., None]
    return grey * (1 - a) + c * a, f'mean {v.mean():.3f}  >0.5 {np.mean(v > 0.5):.1%}'


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def to_img(rgb, px):
    a = (np.clip(rgb, 0, 1) ** (1 / 1.0) * 255).astype(np.uint8)
    im = Image.fromarray(a)
    return im.resize((px, px), Image.LANCZOS if a.shape[0] > px else Image.NEAREST)


def sheet(name, m, h_south, cell, title, crop=None, px=420, cols=6, palette='alpine'):
    """One PNG: the panels of PANELS over the hillshade, north up. crop: (j0, j1, i0, i1) in south-up cells."""
    hs = R.hillshade(np.flipud(h_south), cell)                 # north up for display
    mm = {k: np.flipud(v) for k, v in m.items()}

    class _MM(dict):
        skipped = m.skipped
    mm = _MM(mm)
    if crop is not None:
        j0, j1, i0, i1 = crop
        ny = h_south.shape[0]
        r0, r1 = ny - j1, ny - j0                             # south-up rows -> north-up rows
        hs = hs[r0:r1, i0:i1]
        mm = _MM({k: v[r0:r1, i0:i1] for k, v in mm.items()})
    rows = math.ceil(len(PANELS) / cols)
    head, lab = 64, 46
    W, H = cols * px + (cols + 1) * 6, head + rows * (px + lab + 6)
    img = Image.new('RGB', (W, H), (14, 15, 18))
    d = ImageDraw.Draw(img)
    d.text((10, 8), title[0], font=font(24), fill=(240, 220, 150))
    d.text((10, 38), title[1], font=font(16), fill=(190, 195, 205))
    f1, f2 = font(17), font(13)
    for k, (ptitle, kind, key, note) in enumerate(PANELS):
        r, c = divmod(k, cols)
        x, y = 6 + c * (px + 6), head + r * (px + lab + 6)
        rgb, stat = panel_rgb(kind, key, mm, hs, palette)
        img.paste(to_img(rgb, px), (x, y + lab))
        d.text((x + 2, y + 2), ptitle, font=f1, fill=(240, 220, 150))
        d.text((x + 2, y + 24), (stat + ('  |  ' if stat else '') + note)[:62], font=f2, fill=(185, 190, 200))
    return img


def stats(m):
    out = {}
    for k, v in m.items():
        v = np.asarray(v, np.float64)
        out[k] = dict(min=round(float(v.min()), 4), median=round(float(np.median(v)), 4),
                      mean=round(float(v.mean()), 4), max=round(float(v.max()), 4),
                      over_half=round(float(np.mean(v > 0.5)), 4))
    return out


def run(name, log=print):
    t0 = time.time()
    fl, lv, meta = F.reference_stack(name, log=log)
    P = F.params_for(name)
    stack = M.compute_stack(fl, lv, names=NAMES, params=P, strict=False)
    m = stack[1]
    h, cell = fl[1]['h'], lv[1].cell
    os.makedirs(F.OUT, exist_ok=True)
    pal = F.PREVIEW_PALETTE_OF.get(name, 'alpine')
    secs = ', '.join(f'{k} {v:.2f}' for k, v in m.seconds.items())
    t1 = (f'{meta["title"]}: the main tile\'s masks ({meta["landform"]})',
          f'{h.shape[1] * cell / 1000:g} km at {cell:g} m  |  relief {h.max() - h.min():.0f} m  |  '
          f'stacked on the {lv[0].cell:g} m context, border pinned  |  {secs} s')
    sheet(name, m, h, cell, t1, palette=pal).save(os.path.join(F.OUT, f'{name}_masks_tile.png'))
    det = DETAIL.get(name, dict(at=(0.0, 0.0), side=2048.0))
    half = int(round(det['side'] / cell / 2))
    ci = int(round((det['at'][0] - lv[1].x0) / cell))
    cj = int(round((det['at'][1] - lv[1].y0) / cell))
    ci = min(max(ci, half), h.shape[1] - half)
    cj = min(max(cj, half), h.shape[0] - half)
    crop = (cj - half, cj + half, ci - half, ci + half)
    t2 = (f'{meta["title"]}: detail, {2 * half * cell / 1000:g} km wide at ({det["at"][0]:g}, {det["at"][1]:g}) m',
          f'{2 * half} x {2 * half} cells of {cell:g} m drawn at {420 / (2 * half):.2f} px per cell  |  north up')
    sheet(name, m, h, cell, t2, crop=crop, palette=pal).save(os.path.join(F.OUT, f'{name}_masks_detail.png'))
    st = dict(reference=name, cell_m=cell, params=P.to_dict(), skipped=m.skipped,
              seconds={k: round(v, 3) for k, v in m.seconds.items()},
              context_seconds={k: round(v, 3) for k, v in stack[0].seconds.items()},
              norms=vars(m.norms), masks=stats(m))
    with open(os.path.join(F.OUT, f'{name}_mask_stats.json'), 'w') as f:
        json.dump(st, f, indent=1)
    log(f'[sheets] {name}: {time.time() - t0:.1f}s')
    return st


def aerial_sheet(names=None, w=640):
    """out/masks/masks_aerials.png: per reference, the clay reference's 45-degree aerial (reference/renders) beside
    the same view rendered with the masks as point attributes driving the preview material (render_masks.py)."""
    names = names or F.SHEET_REFS
    rows = []
    for name in names:
        ref = os.path.join(F.TN, 'reference', 'renders', f'{name}_aerial_45deg.png')
        got = os.path.join(F.OUT, 'renders', f'{name}_masks_aerial_45deg.png')
        if os.path.exists(ref) and os.path.exists(got):
            rows.append((name, Image.open(ref).convert('RGB'), Image.open(got).convert('RGB')))
    if not rows:
        return None
    hgt = int(w * 540 / 960)
    lab = 30
    img = Image.new('RGB', (2 * w + 18, 50 + len(rows) * (hgt + lab + 6)), (14, 15, 18))
    d = ImageDraw.Draw(img)
    d.text((10, 8), 'Masks as a material: the clay reference (left) and the same view with eido_* point attributes '
                    'driving the preview material (right)', font=font(18), fill=(240, 220, 150))
    for k, (name, a, b) in enumerate(rows):
        y = 50 + k * (hgt + lab + 6)
        d.text((8, y + 4), f'{name}: clay (reference rig)', font=font(15), fill=(190, 195, 205))
        d.text((w + 14, y + 4), f'{name}: masks (palette {F.PREVIEW_PALETTE_OF.get(name)})', font=font(15),
               fill=(190, 195, 205))
        img.paste(a.resize((w, hgt), Image.LANCZOS), (6, y + lab))
        img.paste(b.resize((w, hgt), Image.LANCZOS), (w + 12, y + lab))
    path = os.path.join(F.OUT, 'masks_aerials.png')
    img.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--aerials', action='store_true', help='only the aerial compare sheet (after render_masks.py)')
    a = ap.parse_args()
    if a.aerials:
        print(aerial_sheet())
        return
    for name in (a.only.split(',') if a.only else F.SHEET_REFS):
        run(name)


if __name__ == '__main__':
    main()
