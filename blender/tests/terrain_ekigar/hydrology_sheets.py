"""Top-down sheets of the hydrology masks (no GPU), one PNG per terrain in out/hydrology/: a hillshade with the lakes
in blue and the channels drawn on it, then flow accumulation, channels, lake depth, wetness, moisture, deposition,
horizon occlusion and vegetation. North is up.

    python blender/tests/terrain_ekigar/hydrology_sheets.py [resolution]
"""
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

import _ekigar_load

ek = _ekigar_load.load()
OUT = os.path.join(_ekigar_load.OUT, 'hydrology')
os.makedirs(OUT, exist_ok=True)
RES = int(sys.argv[1]) if len(sys.argv) > 1 else 512
CELL = 320

SCENES = [
    ('mountainRange_eroded_phacelle', ('chain', [('mountainRange', {'style': 'eroded', 'frequency': 3}),
                                                 ('phacelle', {'strength': 0.25})]), 3000, {}),
    ('island_sea', ('op', 'island', {}), 3000, {'sea_level': 0.05}),
    ('canyon', ('op', 'canyon', {}), 2000, {}),
    ('volcano', ('op', 'volcano', {}), 3000, {}),
    ('badlands', ('op', 'badlands', {}), 1500, {}),
    ('glacialTrough_open_edges', ('op', 'glacialTrough', {}), 3000, {'open': True}),
]


def hillshade(hf):
    n = hf.normals()
    light = np.array([-0.55, 0.45, 0.70])
    light /= np.linalg.norm(light)
    return np.clip(0.12 + 0.88 * np.clip(np.tensordot(light, n, axes=1), 0, 1), 0, 1)


def tile(rgb, label):
    im = Image.fromarray((np.clip(rgb[::-1], 0, 1) * 255).astype(np.uint8)).resize((CELL, CELL), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, CELL, 13], fill=(0, 0, 0))
    d.text((3, 1), label, fill=(255, 230, 160))
    return im


def grey(a):
    return np.repeat(np.clip(a, 0, 1)[..., None], 3, axis=2)


for name, how, world, kw in SCENES:
    t0 = time.time()
    if how[0] == 'chain':
        g, ids = ek.chain_graph(how[1])
        t = ids[-1]
    else:
        g, t, _fx = ek.operator_example(how[1], how[2])
    tile_ = (0.0, 0.0) if kw.get('open') else (1.0, 1.0)
    hf = ek.generate(g, target=t, resolution=RES, world_size=world, tile=tile_)
    t_gen = time.time() - t0
    t1 = time.time()
    H = hf.hydrology(**{k: v for k, v in kw.items() if k != 'open'})
    t_hy = time.time() - t1
    shade = hillshade(hf)
    base = grey(shade)
    lake = H['lake'][..., None]
    base = base * (1 - lake) + lake * np.array([0.12, 0.28, 0.55])
    ch = H['channels'][..., None]
    base = base * (1 - ch) + ch * np.array([0.10, 0.55, 0.95])
    depth = H['lakeDepth_m']
    tiles = [tile(base, f'{name}: lakes + channels'),
             tile(grey(H['accumulation']), 'accumulation (log)'),
             tile(grey(H['channels']), 'channels'),
             tile(grey(depth / max(float(depth.max()), 1e-6)), f'lake depth (max {depth.max():.1f} m)'),
             tile(grey(H['wetness']), 'wetness (TWI)'),
             tile(grey(H['moisture']), 'moisture'),
             tile(grey(H['deposition']), 'deposition'),
             tile(grey(H['occlusion']), 'occlusion (horizon)'),
             tile(grey(H['vegetation']), 'vegetation')]
    cols = 5
    rows = -(-len(tiles) // cols)
    sheet = Image.new('RGB', (cols * CELL, rows * CELL), (11, 15, 20))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * CELL, (i // cols) * CELL))
    sheet.save(os.path.join(OUT, f'{name}.png'))
    st = ek.stats_of(hf, sea_level=kw.get('sea_level'))
    print(f'{name}: {RES}^2 gen {t_gen:.1f}s hydrology {t_hy:.1f}s, {H["info"]["basins"]} basins, outlet '
          f'{H["info"]["outlet"]}, water {st["waterFraction"]:.1%}, channels {float((H["channels"] > 0.5).mean()):.2%}',
          flush=True)
