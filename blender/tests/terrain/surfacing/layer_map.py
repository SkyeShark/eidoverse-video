"""Where a palette's layers fall on a built terrain, top-down, before any render (system Python: numpy + Pillow).

    python blender/tests/terrain/surfacing/layer_map.py <cache key | snapshot.npz> [--level main] [--palette auto]
           [--out <png>] [--window x0,y0,side] [--base <metres>]

Reads a cached terrain's level (eidoverse/assets/cache/terrain/<key>/level_<i>.npz: its fields and masks), evaluates
the palette's layer weights with numpy (palettes.evaluate: the scatter's value noise stands in for the shader's
noise, so the breakup's pattern differs but not its statistics), composites them as the material does (a layer covers
what lies below it), and draws each pixel in its layers' debug colours mixed by weight, beside a hillshade. The legend
gives each layer's share of the window. A recipe's palette 'auto' is its RECIPE_PALETTES entry with its RECIPE_LOOKS
(a recipe whose palette comes from strata.palette_for shows the base palette's weights, which are the same).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BLENDER_DIR = HERE.parents[2]
sys.path.insert(0, str(BLENDER_DIR))
from eidoblend.terrain.build import palettes as P  # noqa: E402

CACHE = BLENDER_DIR.parent / 'eidoverse' / 'assets' / 'cache' / 'terrain'
OUT = HERE.parent / 'out' / 'surfacing' / 'layer_maps'
DEBUG_COLOURS = [(0.55, 0.38, 0.25), (0.35, 0.55, 0.2), (0.85, 0.75, 0.45), (0.6, 0.35, 0.6), (0.2, 0.55, 0.85),
                 (0.95, 0.95, 0.95)]


def hillshade(h, cell):
    gy, gx = np.gradient(h, cell)
    az, el = math.radians(315.0), math.radians(40.0)
    lx, ly, lz = math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)
    n = np.sqrt(gx * gx + gy * gy + 1.0)
    return np.clip((-gx * lx - gy * ly + lz) / n, 0, 1)


def composite(pal, masks, x, y, consts):
    cov = [np.clip(P.evaluate(L['weight'], masks, x, y, consts), 0, 1) for L in pal['layers']]
    excl = [None] * len(cov)
    rem = np.ones_like(cov[0])
    for i in range(len(cov) - 1, -1, -1):
        excl[i] = cov[i] * rem
        rem = rem * (1 - cov[i])
    return excl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('key')
    ap.add_argument('--level', default='main')
    ap.add_argument('--palette', default='auto')
    ap.add_argument('--window', default=None, help='x0,y0,side in world metres (default the whole level)')
    ap.add_argument('--base', type=float, default=None,
                    help="the altitude of z = 0 in metres (default the cache's record; a real place's DEM base "
                         "is not recorded there: Lauterbrunnen's is 733)")
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    if a.key.endswith('.npz'):
        # a Terrain.save() snapshot (review_views.py --snap): its levels' fields and masks under L<i>__ prefixes,
        # its record (plan, recipe, base elevation) beside it as .json
        snap = Path(a.key)
        meta = json.loads(snap.with_suffix('.json').read_text())
        meta.setdefault('recipe', meta.get('recipe_name'))
        if isinstance(meta['recipe'], dict):
            meta['recipe'] = meta['recipe'].get('name')
        plan = meta['plan']
        li = next(i for i, L in enumerate(plan) if L['role'] == a.level) if not a.level.isdigit() else int(a.level)
        zz = np.load(snap)
        pre = f'L{li}__'
        z = {k[len(pre):]: zz[k] for k in zz.files if k.startswith(pre)}
        a.key = snap.stem
    else:
        d = CACHE / a.key
        meta = json.loads((d / 'meta.json').read_text())
        plan = meta['plan']
        li = next(i for i, L in enumerate(plan) if L['role'] == a.level) if not a.level.isdigit() else int(a.level)
        zf = np.load(d / f'level_{li}.npz')
        z = {k: zf[k] for k in zf.files}
    L = plan[li]
    masks = {k[3:]: np.asarray(v, np.float64) for k, v in z.items() if k.startswith('m__')}
    h = np.asarray(z['f__h'], np.float64)
    n, cell = h.shape[0], float(L['cell'])
    X = L['x0'] + (np.arange(n) + 0.5) * cell
    Y = L['y0'] + (np.arange(n) + 0.5) * cell
    XX, YY = np.meshgrid(X, Y)
    if a.window:
        wx, wy, ws = (float(v) for v in a.window.split(','))
        i0, j0 = int((wx - L['x0']) / cell), int((wy - L['y0']) / cell)
        k = int(ws / cell)
        sl = (slice(max(j0, 0), min(j0 + k, n)), slice(max(i0, 0), min(i0 + k, n)))
        masks = {nm: v[sl] for nm, v in masks.items()}
        h, XX, YY = h[sl], XX[sl], YY[sl]
    if a.palette == 'auto':
        pal = P.get('auto', recipe=meta['recipe'])
    else:
        pal = P.get(a.palette)
    consts = dict(pal['constants'])
    consts['base_elevation_m'] = float(a.base if a.base is not None else
                                       (meta.get('base_elevation_m') or consts.get('base_elevation_m', 0.0)))
    ex = composite(pal, masks, XX, YY, consts)
    rgb = np.zeros(h.shape + (3,))
    for i, e in enumerate(ex):
        rgb += e[..., None] * np.array(DEBUG_COLOURS[i % len(DEBUG_COLOURS)])
    hs = hillshade(h, cell)[..., None]
    img = np.clip(rgb * (0.45 + 0.75 * hs), 0, 1)[::-1]              # north up
    hsi = np.repeat(hs[::-1], 3, axis=2)
    W = 720
    a_im = Image.fromarray((img * 255).astype(np.uint8)).resize((W, W), Image.BILINEAR)
    b_im = Image.fromarray((hsi * 255).astype(np.uint8)).resize((W, W), Image.BILINEAR)
    sheet = Image.new('RGB', (2 * W, W + 34 + 22 * len(ex)), (18, 18, 18))
    sheet.paste(a_im, (0, 34))
    sheet.paste(b_im, (W, 34))
    dr = ImageDraw.Draw(sheet)
    f = ImageFont.truetype('arial.ttf', 17)
    dr.text((6, 6), f"{meta['recipe']} level {li} ({L['role']}, {cell:g} m), palette {pal['name']}: layers (left), "
                    f"hillshade (right)", fill=(255, 220, 120), font=f)
    for i, (lay, e) in enumerate(zip(pal['layers'], ex)):
        c = tuple(int(255 * v) for v in DEBUG_COLOURS[i % len(DEBUG_COLOURS)])
        y0 = W + 40 + 22 * i
        dr.rectangle([8, y0, 26, y0 + 16], fill=c)
        dr.text((34, y0 - 1), f"{lay['name']}: {100 * float(e.mean()):.1f} % of the window", fill=(230, 230, 230),
                font=f)
    out = Path(a.out) if a.out else OUT / f"{meta['recipe']}_{a.key[:8]}_level{li}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out, ', '.join(f"{lay['name']} {100 * float(e.mean()):.1f}%" for lay, e in zip(pal['layers'], ex)))


if __name__ == '__main__':
    main()
