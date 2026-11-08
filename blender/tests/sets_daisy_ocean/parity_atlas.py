"""The face atlas against the WebGPU edition's own (faces_atlas.js drawn with @napi-rs/canvas in deno: atlas_dump.mjs):
the same 64 people stroke for stroke (the same rng(11) draws), the line art's coverage, the halo and the fill.
System Python (numpy, Pillow):

    cd <worktree> && python blender/tests/sets_daisy_ocean/parity_atlas.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from eidoblend.sets.daisy.ocean.faces_atlas import draw_face_atlas  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
raw = os.path.join(OUT, 'atlas_js.rgba')
if not os.path.exists(raw):
    subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'atlas_dump.mjs'), raw], cwd=REPO, check=True)
js = np.fromfile(raw, np.uint8).reshape(2048, 2048, 4)
t0 = time.time()
py = draw_face_atlas(n=8, cell=256, seed=11)
print(f'[atlas] drawn in {time.time() - t0:.1f}s')
rows = []


def check(name, ok, detail=''):
    rows.append(ok)
    print(f'[atlas] {"PASS" if ok else "FAIL"} {name} {detail}')


a, b = js.astype(np.float32), py.astype(np.float32)
for ch, nm, tol in ((0, 'line art (R)', 6.0), (1, 'halo (G)', 6.0), (2, 'fill (B)', 2.0)):
    d = np.abs(a[..., ch] - b[..., ch]).mean()
    check(f'{nm}: mean |difference| < {tol} / 255', d < tol, f'{d:.2f}')
la, lb = a[..., 0] > 128, b[..., 0] > 128
iou = (la & lb).sum() / max(1, (la | lb).sum())
check('line pixels overlap (IoU > 0.75)', iou > 0.75, f'IoU {iou:.3f}')
per_cell = []
for k in range(64):
    oy, ox = (k // 8) * 256, (k % 8) * 256
    ca, cb = la[oy:oy + 256, ox:ox + 256], lb[oy:oy + 256, ox:ox + 256]
    per_cell.append((ca & cb).sum() / max(1, (ca | cb).sum()))
check('every face is the same person (each cell IoU > 0.6)', min(per_cell) > 0.6,
      f'worst cell {int(np.argmin(per_cell))}: {min(per_cell):.3f}, median {np.median(per_cell):.3f}')
# a side-by-side of four cells (JS left, Blender right) at 2x
crop = lambda x: Image.fromarray(np.ascontiguousarray(x[::-1][:512, :512, 0]))   # noqa: E731
side = Image.new('L', (1024, 512))
side.paste(crop(js), (0, 0))
side.paste(crop(py), (512, 0))
side.save(os.path.join(OUT, 'atlas_js_left_blender_right.png'))
print(f'[atlas] {sum(rows)}/{len(rows)} checks pass')
