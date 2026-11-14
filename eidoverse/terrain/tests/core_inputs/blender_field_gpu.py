"""The Blender edition's own GPU path for world noise, core/world_noise.py field_gpu (its GLSL kernel, KERNEL_FIELD),
on the noise cases core_inputs_expected.py recorded, so fields_noise_test.mjs can put the port's float32 kernel beside
the Blender edition's float32 kernel as well as beside numpy's float64 field() (PORT_PLAN.md 8.2, P2).

    bash <Blender checkout>/run_blender.sh eidoverse/terrain/tests/core_inputs/blender_field_gpu.py [fixtures]

(on a shared machine, behind $EIDO_GPU_WRAP). It writes blender_gpu/<case>.bin (float32, the case's window) and
blender_gpu/manifest.json into the fixture folder (default: the newest tests/out/core_inputs/fixtures_*). field_gpu
evaluates square levels; a window of h x w cells is evaluated on max(h, w) cells and cropped, which changes nothing
(a cell's value depends on the window's origin and cell size, not its extent).

The Blender edition is found at blender/ beside eidoverse/ in this checkout, else at $EIDO_BLENDER_EDITION.
"""
import glob
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    cands = [os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')]
    for root in cands:
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('blender_field_gpu: no Blender edition (blender/eidoblend/terrain) here or at $EIDO_BLENDER_EDITION')


ROOT = blender_edition()
BLENDER_DIR = os.path.join(ROOT, 'blender')
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
sys.path.insert(0, BLENDER_DIR)
import eidoblend  # noqa: E402  (imports nothing)

pkg = types.ModuleType('eidoblend.terrain')
pkg.__path__ = [TERRAIN_DIR]
pkg.__package__ = 'eidoblend.terrain'
sys.modules['eidoblend.terrain'] = pkg
eidoblend.terrain = pkg

import numpy as np  # noqa: E402

from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import world_noise as N  # noqa: E402

args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a != '--']
if args:
    FIX = os.path.abspath(args[0])
else:
    found = sorted(glob.glob(os.path.join(HERE, '..', 'out', 'core_inputs', 'fixtures_*')))
    if not found:
        sys.exit('blender_field_gpu: no fixtures; run core_inputs_expected.py first')
    FIX = os.path.abspath(found[-1])
with open(os.path.join(FIX, 'manifest.json'), encoding='utf-8') as fh:
    M = json.load(fh)
OUT = os.path.join(FIX, 'blender_gpu')
os.makedirs(OUT, exist_ok=True)


def load(a):
    return np.fromfile(os.path.join(FIX, a['file']), dtype={'f32': '<f4', 'f64': '<f8'}[a['dtype']]).reshape(a['shape'])


rows = []
for k, c in enumerate(M['noise']['cases']):
    x0, y0, cell, h, w = M['noise']['windows'][c['window']]
    n = max(h, w)
    lv = L.Level(0, 'main', x0, y0, n * cell, cell, n)
    disp = None
    if c.get('disp'):
        dx, dy = load(c['disp'][0]), load(c['disp'][1])
        px, py = np.zeros((n, n), np.float32), np.zeros((n, n), np.float32)
        px[:h, :w], py[:h, :w] = dx, dy
        disp = (px, py)
    v = N.field_gpu(c['spec'], lv, c['seed'], disp=disp)[:h, :w]
    name = f'case_{k:03d}.bin'
    np.ascontiguousarray(v, dtype='<f4').tofile(os.path.join(OUT, name))
    rows.append({'case': k, 'label': c['label'], 'window': c['window'], 'seed': c['seed'], 'file': name, 'shape': [h, w]})
with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
    json.dump({'blender_commit': M.get('blender_commit'), 'cases': rows}, fh, indent=1)
print(f'[blender_field_gpu] {len(rows)} cases -> {OUT}', flush=True)
