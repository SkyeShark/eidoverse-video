"""Top-down sheets of every gallery scene's masks (no GPU): a hillshade, the height, then each named output of the
operator and the masks.js set (slope, profile curvature, concave, converge). One PNG per scene in out/masks/, and
out/masks/_overview_<k>.png hillshade contact sheets of all of them.

    python blender/tests/terrain_ekigar/mask_sheets.py [resolution] [op,op,...]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import _ekigar_load

ek = _ekigar_load.load()
OUT = os.path.join(_ekigar_load.OUT, 'masks')
os.makedirs(OUT, exist_ok=True)
RES = int(sys.argv[1]) if len(sys.argv) > 1 else 192
ONLY = sys.argv[2].split(',') if len(sys.argv) > 2 else None
CELL = 192


def hillshade(hf):
    n = hf.normals()
    light = np.array([-0.55, 0.45, 0.70])
    light /= np.linalg.norm(light)
    lam = np.clip(np.tensordot(light, n, axes=1), 0, 1)
    return np.clip(0.12 + 0.88 * lam, 0, 1)


def to_img(a, label, cmap=None):
    a = np.asarray(a, dtype=np.float64)[::-1]              # north up
    if cmap == 'div':
        t = np.clip(a, 0, 1)[..., None]
        rgb = (1 - t) * np.array([0.25, 0.45, 0.85]) + t * np.array([0.88, 0.42, 0.28])
    else:
        rgb = np.repeat(np.clip(a, 0, 1)[..., None], 3, axis=2)
    im = Image.fromarray((rgb * 255).astype(np.uint8)).resize((CELL, CELL), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, CELL, 13], fill=(0, 0, 0))
    d.text((3, 1), label, fill=(255, 230, 160))
    return im


def sheet(name, hf):
    h = hf.height
    lo, hi = float(h.min()), float(h.max())
    tiles = [to_img(hillshade(hf), f'{name} shade'), to_img((h - lo) / max(hi - lo, 1e-9), f'height {lo:.2f}..{hi:.2f}')]
    for k in sorted(hf.outs):
        tiles.append(to_img(hf.outs[k], f'out: {k}'))
    m = hf.masks()
    tiles.append(to_img(m['slope'], 'slope'))
    tiles.append(to_img(m['curvProfile'], 'curvProfile', 'div'))
    tiles.append(to_img(m['concave'], 'concave'))
    tiles.append(to_img(m['converge'], 'converge'))
    cols = 6
    rows = -(-len(tiles) // cols)
    out = Image.new('RGB', (cols * CELL, rows * CELL), (11, 15, 20))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * CELL, (i // cols) * CELL))
    out.save(os.path.join(OUT, f'{name}.png'))
    return tiles[0]


scenes = [('reference', *ek.fixture_graph()[:2])]
for op in ek.gallery_ids():
    g, t, fx = ek.operator_example(op)
    scenes.append((op, g, t))
thumbs = []
for name, g, t in scenes:
    if ONLY and name not in ONLY:
        continue
    hf = ek.generate(g, target=t, resolution=RES, world_size=100)
    thumbs.append(sheet(name, hf))
    print('sheet', name, flush=True)
per = 30
for k in range(0, len(thumbs), per):
    chunk = thumbs[k:k + per]
    cols = 6
    rows = -(-len(chunk) // cols)
    ov = Image.new('RGB', (cols * CELL, rows * CELL), (11, 15, 20))
    for i, t in enumerate(chunk):
        ov.paste(t, ((i % cols) * CELL, (i // cols) * CELL))
    ov.save(os.path.join(OUT, f'_overview_{k // per}.png'))
print(f'{len(thumbs)} sheets in {OUT}')
