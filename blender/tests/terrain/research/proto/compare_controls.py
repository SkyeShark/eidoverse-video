"""The generic realism metrics on two controls: plain fBm (what the WebGPU edition's makeTerrain is) and the Ekigar
port's hero heightfields (blender/tests/terrain_ekigar/out/heroes/cache, read only).
    python compare_controls.py  -> out/controls.json and a printed table"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import terrain_metrics as TM  # noqa: E402
from spl_gather import spectral_noise  # noqa: E402

CACHE = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'terrain_ekigar', 'out', 'heroes', 'cache'))
rows = {}
for beta, name in ((4.0, 'fbm_beta4 (gain 0.5 octaves)'), (3.0, 'fbm_beta3 (rougher)')):
    h = spectral_noise(256, beta, 11) * 1500.0                    # 1.5 km of relief over 20 km, 78 m cells
    rows[name] = TM.metrics(h, 20000.0 / 256)
for hero in ('mountainRange_alpine', 'volcano', 'canyon', 'badlands', 'glacialTrough', 'duneField_star',
             'impactCrater', 'caldera'):
    d = np.load(os.path.join(CACHE, f'hero_{hero}.npz'), allow_pickle=False)
    meta = json.loads(str(d['meta']))
    W, vs, zb = meta['world_size'], meta['vertical_scale'], meta['z_base']
    h = (d['field'][0].astype(np.float64) - zb) * vs * W
    rows['ekigar_' + hero] = TM.metrics(h, W / h.shape[1])
with open(os.path.join(HERE, 'out', 'controls.json'), 'w') as f:
    json.dump(rows, f, indent=1)
keys = ['extent_km', 'pixel_m', 'relief_m', 'slope_p50', 'slope_p90', 'frac_slope_gt40', 'frac_slope_lt5',
        'depression_area_frac', 'depressions_per_100km2']
print('name'.ljust(32) + ''.join(k[:12].rjust(13) for k in keys))
for n, m in rows.items():
    print(n[:31].ljust(32) + ''.join(f'{m[k]:13.3f}' for k in keys))
