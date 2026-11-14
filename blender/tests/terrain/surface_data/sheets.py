"""Map sheets of the surface data (SURFACING_DESIGN.md 5.4, package 1, item 1): each map beside the hillshade at the
main level and one hero level, for the cases _cases.SHEET_CASES. Plain Python (numpy, Pillow); reads the snapshot
and the bake bake_cases.py cached:

    python blender/tests/terrain/surface_data/sheets.py --case toroweap [--case canyon ...] [--all] [--hero K]

Writes out/surface_data/sheets/<case>.png (and <case>_<level>_<map>.png at full size with --full). Panels are north
up. Signed maps (crest, crease, crest_fine) are drawn blue (-) to red (+) over a light hillshade; 0-1 maps in a
sequential ramp over it; src_strata as the debris' source height above the ground's own bed (src_strata - strata,
red where a talus carries rock from higher beds); n20 as the azimuth of the 20 m normal (hue) by its dip (strength);
'relief' is D's normal with the sub-cell gradient added (s = 0.5), hillshaded; down_colour is P's colour.
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import _cases as C  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

PANEL = 380
PANELS = ('hillshade', 'relief', 'crest', 'crest_fine', 'crease', 'cavity', 'settle', 'valley', 'fresh', 'spi',
          'grain', 'src_offset', 'streak', 'snowpack', 'n20', 'flow', 'wetness', 'channels', 'down_colour',
          'down_share', 'far_colour')
SIGNED = ('crest', 'crest_fine', 'crease')


def hillshade(h, cell, az=315.0, alt=45.0):
    gy, gx = np.gradient(np.asarray(h, np.float64), cell)
    return _shade(-gx, -gy, np.ones_like(gx), az, alt)


def _shade(nx, ny, nz, az=315.0, alt=45.0):
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    a, e = math.radians(az), math.radians(alt)
    s = (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))
    return np.clip((nx * s[0] + ny * s[1] + nz * s[2]) / L, 0.0, 1.0)


def _ramp(t, stops):
    t = np.clip(t, 0.0, 1.0)
    xs = np.array([s[0] for s in stops])
    out = np.zeros(t.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(t, xs, [s[1][c] for s in stops])
    return out


SEQ = [(0.0, (0.05, 0.05, 0.2)), (0.25, (0.2, 0.25, 0.6)), (0.5, (0.2, 0.6, 0.55)), (0.75, (0.85, 0.8, 0.25)),
       (1.0, (1.0, 1.0, 0.85))]
DIV = [(0.0, (0.1, 0.25, 0.85)), (0.5, (0.95, 0.95, 0.95)), (1.0, (0.85, 0.15, 0.1))]


def colourise(name, a, hs):
    """(H, W, 3) 0..1: the map coloured, over a light hillshade."""
    base = (0.55 + 0.45 * hs)[..., None]
    if name in ('hillshade', 'relief'):
        return np.repeat(np.asarray(a, np.float64)[..., None], 3, 2)
    if name in ('down_colour', 'far_colour'):
        c = np.clip(np.asarray(a, np.float64), 0, 1)
        return np.clip(c ** (1 / 2.2) * base * 1.1, 0, 1)
    if name == 'n20':
        x, y = a
        dip = np.clip(np.hypot(x, y) / 0.7, 0, 1)
        hue = (np.degrees(np.arctan2(x, y)) % 360.0) / 360.0
        rgb = _hsv(hue, dip, np.ones_like(dip))
        return rgb * base
    a = np.asarray(a, np.float64)
    if name in SIGNED:
        return _ramp(0.5 + 0.5 * a, DIV) * base
    if name == 'src_offset':
        return _ramp(0.5 + 0.5 * np.tanh(a / 60.0), DIV) * base
    if name == 'snowpack':
        return _ramp(np.sqrt(np.clip(a / 4.0, 0, 1)), SEQ) * base
    return _ramp(a, SEQ) * base


def _hsv(h, s, v):
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    i = i.astype(int) % 6
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1)


def _fit(a, n):
    """Box-average or nearest-resize a (m, m[, 3]) array to (n, n)."""
    m = a.shape[0]
    if m == n:
        return a
    if m % n == 0:
        f = m // n
        sh = (n, f, n, f) + a.shape[2:]
        return a.reshape(sh).mean(axis=(1, 3))
    idx = (np.arange(n) * m / n).astype(int)
    return a[idx][:, idx]


def level_panels(name, sd_maps, h, cell, hero_window=None):
    """{panel: (H, W, 3) 0..1 north up} for one level."""
    hs = hillshade(h, cell)
    n = h.shape[0]
    out = {'hillshade': hs}
    m = sd_maps
    if 'normal_x' in m:
        nx, ny = np.asarray(m['normal_x'], np.float64), np.asarray(m['normal_y'], np.float64)
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 1e-6, 1))
        gx = np.asarray(m.get('detail_gx', 0 * nx), np.float64)
        gy = np.asarray(m.get('detail_gy', 0 * nx), np.float64)
        hx, hy = -nx / nz, -ny / nz
        out['relief'] = _shade(-(hx + 0.5 * gx), -(hy + 0.5 * gy), np.ones_like(hx))
    for k in PANELS:
        if k in out:
            continue
        if k == 'n20':
            if 'n20_x' in m:
                out[k] = (np.asarray(m['n20_x']), np.asarray(m['n20_y']))
            continue
        if k == 'src_offset':
            if 'src_dz' in m and 'strata' in m:
                out[k] = (h + np.asarray(m['src_dz'], np.float64)) - np.asarray(m['strata'], np.float64)
            continue
        if k in m:
            out[k] = m[k]
    res = {}
    for k, v in out.items():
        hsk = hs if k != 'relief' else hs
        if isinstance(v, tuple):
            arr = colourise(k, tuple(_fit(np.asarray(c, np.float64), n) for c in v), hsk)
        else:
            v = np.asarray(v, np.float64)
            if v.shape[0] != n:
                v = _fit(v, n) if v.ndim == 2 or v.shape[0] > n else v
            arr = colourise(k, v, hsk)
        res[k] = np.ascontiguousarray(arr[::-1])                     # north up
    return res


def sheet(name, hero=None, full=False):
    t = C.terrain(name)
    sd, _key = load_sd(name, t)
    roles = [lv.role for lv in t.levels]
    main = roles.index('main')
    heroes = [i for i, r in enumerate(roles) if r == 'hero']
    hi = hero if hero is not None else (heroes[min(1, len(heroes) - 1)] if heroes else None)
    rows = []
    for i in [main] + ([hi] if hi is not None else []):
        lv = t.levels[i]
        h = np.asarray(t.fields(i)['h'], np.float64)
        m = sd.maps(i)
        if 'strata' not in m:
            m['strata'] = h
        rows.append((i, lv, level_panels(name, m, h, lv.cell)))
    names = [k for k in PANELS if any(k in r[2] for r in rows)]
    cols = 7
    nrow_per = int(math.ceil(len(names) / cols))
    lab = 22
    W = cols * PANEL
    Ht = len(rows) * (nrow_per * (PANEL + lab) + 34)
    img = Image.new('RGB', (W, Ht), (24, 24, 24))
    d = ImageDraw.Draw(img)
    y = 0
    for i, lv, panels in rows:
        d.text((8, y + 8), f'{C.CASES[name]["title"]}: level {i} {lv.role}, {lv.side:g} m @ {lv.cell:g} m '
                           f'(x0 {lv.x0:g}, y0 {lv.y0:g}), north up', fill=(235, 235, 235))
        y += 34
        for k, nm in enumerate(names):
            r, c = divmod(k, cols)
            x0, y0 = c * PANEL, y + r * (PANEL + lab)
            if nm in panels:
                a = np.clip(panels[nm], 0, 1)
                tile = Image.fromarray((a * 255 + 0.5).astype(np.uint8)).resize((PANEL, PANEL), Image.LANCZOS)
                img.paste(tile, (x0, y0 + lab))
                if full:
                    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(
                        os.path.join(C.OUT, 'sheets', f'{name}_L{i}_{nm}.png'))
            d.text((x0 + 6, y0 + 4), nm, fill=(235, 235, 120))
        y += nrow_per * (PANEL + lab)
    os.makedirs(os.path.join(C.OUT, 'sheets'), exist_ok=True)
    p = os.path.join(C.OUT, 'sheets', f'{name}.png')
    img.save(p)
    stats = {}
    for i, lv, _p in rows:
        m = sd.maps(i)
        stats[f'L{i}'] = {k: [round(float(np.percentile(np.asarray(m[k], np.float64), q)), 4) for q in (1, 50, 99)]
                          for k in sorted(m) if k in PANELS or k in ('src_dz', 'detail_gx', 'normal_x')
                          if np.asarray(m[k]).ndim == 2}
    with open(os.path.join(C.OUT, 'sheets', f'{name}_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=1)
    print(f'[sheets] {name}: {p}')
    return p


CROP_PANELS = ('hillshade', 'relief', 'crease', 'cavity', 'crest_fine', 'crest', 'settle', 'grain', 'fresh',
               'flow', 'channels', 'snowpack')


def crop(name, level, cx, cy, size_m, zoom=2):
    """A crop sheet at full texel resolution (the detail maps at their own texel, the cell maps at theirs, both
    shown at `zoom` x on the detail grid): out/surface_data/sheets/<name>_crop_L<level>.png."""
    from eidoblend.terrain import surface as S
    t = C.terrain(name)
    sd, _key = load_sd(name, t)
    i = int(level)
    lv = t.levels[i]
    m = sd.maps(i)
    h = np.asarray(t.fields(i)['h'], np.float64)
    fD = sd.factors[i]
    nD = lv.n * fD

    def window(a):
        k = a.shape[0] // lv.n
        tex = lv.side / a.shape[0]
        i0 = int(round((cx - size_m / 2 - lv.x0) / tex))
        j0 = int(round((cy - size_m / 2 - lv.y0) / tex))
        s = int(round(size_m / tex))
        i0, j0 = max(0, min(i0, a.shape[0] - s)), max(0, min(j0, a.shape[0] - s))
        w = a[j0:j0 + s, i0:i0 + s]
        if k < fD:
            w = np.repeat(np.repeat(w, fD // k, 0), fD // k, 1)
        return w
    hD = h if fD == 1 else np.repeat(np.repeat(h, 2, 0), 2, 1)
    hs = hillshade(window(hD), lv.cell / fD)
    panels = {'hillshade': hs}
    if 'normal_x' in m:
        nx, ny = window(np.asarray(m['normal_x'], np.float64)), window(np.asarray(m['normal_y'], np.float64))
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 1e-6, 1))
        gx, gy = window(np.asarray(m['detail_gx'], np.float64)), window(np.asarray(m['detail_gy'], np.float64))
        panels['relief'] = _shade(-(-nx / nz + 0.5 * gx), -(-ny / nz + 0.5 * gy), np.ones_like(nx))
        panels['field normal'] = _shade(nx, ny, nz)
    for k in CROP_PANELS:
        if k in m and k not in panels:
            panels[k] = colourise(k, window(np.asarray(m[k], np.float64)), hs)
    order = ['hillshade', 'field normal', 'relief'] + [k for k in CROP_PANELS if k in panels and k not in
                                                        ('hillshade', 'relief')]
    tiles = []
    for k in order:
        a = panels[k]
        a = np.repeat(a[..., None], 3, 2) if a.ndim == 2 else a
        a = np.clip(a[::-1], 0, 1)
        im = Image.fromarray((a * 255 + 0.5).astype(np.uint8))
        im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
        tiles.append((k, im))
    cols = 4
    pw = tiles[0][1].width
    lab = 22
    rows = int(math.ceil(len(tiles) / cols))
    img = Image.new('RGB', (cols * pw, rows * (pw + lab) + 30), (24, 24, 24))
    d = ImageDraw.Draw(img)
    d.text((8, 8), f'{C.CASES[name]["title"]}: level {i} ({lv.cell:g} m cells, detail texel {lv.cell / fD:g} m), '
                   f'{size_m:g} m around ({cx:g}, {cy:g}), north up, {zoom}x', fill=(235, 235, 235))
    for k, (nm, im) in enumerate(tiles):
        r, c = divmod(k, cols)
        img.paste(im, (c * pw, 30 + r * (pw + lab) + lab))
        d.text((c * pw + 6, 30 + r * (pw + lab) + 4), nm, fill=(235, 235, 120))
    os.makedirs(os.path.join(C.OUT, 'sheets'), exist_ok=True)
    p = os.path.join(C.OUT, 'sheets', f'{name}_crop_L{i}.png')
    img.save(p)
    print(f'[sheets] {name} crop: {p}')
    return p


def load_sd(name, t):
    from eidoblend.terrain import surface as S
    folder = os.path.join(C.OUT, 'cache', name)
    metas = sorted(glob.glob(os.path.join(folder, 'surface_*.json')), key=os.path.getmtime)
    metas = [p for p in metas if '_pal' not in os.path.basename(p)]
    if not metas:
        raise FileNotFoundError(f'no bake of {name!r} in {folder}: run bake_cases.py --case {name}')
    key = os.path.basename(metas[-1])[len('surface_'):-len('.json')]
    baked, info = S.load_cached(folder, key, len(t.levels))
    pal = None                                            # the newest palette bake of it, when there is one
    pals = sorted(glob.glob(os.path.join(folder, f'surface_{key}_pal*_L0.npz')), key=os.path.getmtime)
    if pals:
        tag = os.path.basename(pals[-1])[len(f'surface_{key}_'):-len('_L0.npz')]
        pal = []
        for i in range(len(t.levels)):
            with np.load(os.path.join(folder, f'surface_{key}_{tag}_L{i}.npz')) as z:
                pal.append({k: np.asarray(z[k], np.float32) for k in z.files})
    return S.SurfaceData(t, baked, info, info.get('options') or {}, key, colour=pal, cache_dir=folder), key


def main():
    a = plain_import.script_args()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)]
    if '--all' in a:
        names = list(C.SHEET_CASES)
    hero = int(a[a.index('--hero') + 1]) if '--hero' in a else None
    if '--crop' in a:
        k = a.index('--crop')
        lvl, cx, cy, size = a[k + 1:k + 5]
        for nm in names:
            crop(nm, int(lvl), float(cx), float(cy), float(size))
        return 0
    for nm in names:
        sheet(nm, hero, full='--full' in a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
