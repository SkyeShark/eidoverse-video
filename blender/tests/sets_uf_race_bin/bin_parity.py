"""bin_parity.py: the Blender bin's pure half (eidoblend/sets/unknown_force/bin.py: heap_height, the placement of every
sheet, boulder and falling sheet on bin.js's mulberry32 stream, the mark's climb, the lights' hush) against bin.js
(bin_parity_dump.mjs writes out/parity/bin.json first).

    cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/bin_parity_dump.mjs <metal_trash_can_embedded.gltf>
    python blender/tests/sets_uf_race_bin/bin_parity.py

Runs in plain Python (no Blender). Prints PASS / FAIL per check; exit 1 on any FAIL.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sets.unknown_force import bin as B  # noqa: E402
from eidoblend.sets.unknown_force import bin_pages as PAGES  # noqa: E402

J = json.load(open(os.path.join(HERE, 'out', 'parity', 'bin.json')))
fails = []


def check(name, ok, info=''):
    print(('PASS' if ok else 'FAIL'), name, info, flush=True)
    if not ok:
        fails.append(name)


R = J['R']
err = max(max(abs(B.heap_height_three(x, z, R) - h), abs(B.heap_height_three(x, z) - h0)) for x, z, h, h0 in J['heap'])
check('heap_height on a 21 x 21 grid (the can R and the default)', err < 1e-12, f'max err {err:.2e}')
check('heap_height(x, y) is heapHeight(x, -y)', abs(B.heap_height(3.0, -7.0, R) - B.heap_height_three(3.0, 7.0, R)) < 1e-15)
cams3 = B.cams_three(R, J['yFill'])
ok = all(cams3[k]['pos'] == list(v['pos']) or np.allclose(cams3[k]['pos'], v['pos']) for k, v in J['cams'].items())
check('cams (with the can radius)', ok and len(cams3) == len(J['cams']))
pl = B.placement(R, cams3, 3300, 300, 200, PAGES.PAGE_KINDS.index('cut'), 24)


def compare(name, items, rec):
    n = rec['n']
    if len(items) != n:
        check(f'{name}: count', False, f'{len(items)} vs {n}')
        return
    m = np.array(rec['m'], float).reshape(n, 4, 4).transpose(0, 2, 1)       # three's column-major -> rows
    mine = np.array([it[0] for it in items])
    em = float(np.max(np.abs(mine - m)))
    ec = max(abs(it[1] - c) for it, c in zip(items, rec['cell']))
    es = max(abs(it[2] - s) for it, s in zip(items, rec['shade']))
    check(f'{name}: {n} instances (matrix, cell, shade)', em < 2e-5 and ec == 0 and es < 2e-6,
          f'matrix {em:.1e}, cell {ec}, shade {es:.1e}')


I = J['instances']
compare('paper:flat', pl['sheets'][0], I['paper:flat'])
compare('paper:curled', pl['sheets'][1], I['paper:curled'])
compare('paper:folded', pl['sheets'][2], I['paper:folded'])
compare('paper:inside', pl['inner'], I['paper:inside'])
compare('paper:crumpled', pl['balls'], I['paper:crumpled'])
fc = [c for c, _ in pl['falling']]
fs = [s for _, s in pl['falling']]
check('bin:falling: 200 cells and shades', fc == [int(c) for c in I['bin:falling']['cell']]
      and max(abs(a - b) for a, b in zip(fs, I['bin:falling']['shade'])) < 2e-6)
# the mark's climb (bin.js's three axes): fill_y on the path from Z_IN to Z_OUT
y_fill, Z_IN, Z_OUT = B.H - 1.95, -0.45, R - 0.42
worst = 0.0
for c, pos in J['mark']:
    z = B.lerp(Z_IN, Z_OUT, B.smooth(0, 1, c))
    y = y_fill + (B.H + 0.06 - y_fill) * B.smooth(Z_IN, Z_OUT, z) ** 1.25 + 0.05 * math.sin(0 * 3.1 + z * 2.3) + 0.03
    worst = max(worst, abs(z - pos[2]), abs(y - pos[1]), abs(pos[0]))
check('mark on the climb (6 values)', worst < 1e-6, f'max err {worst:.2e}')
check('focal on the lip', np.allclose(J['focal'], [0, B.H + 0.9, R - 0.2], atol=1e-6))
check('pcg_hash (TSL hash) for small ids', abs(B.pcg_hash([0.11])[0] - B.pcg_hash([0.0])[0]) < 1e-12
      and 0 <= B.pcg_hash([7.0])[0] < 1)
print('bin_parity:', 'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}')
sys.exit(1 if fails else 0)
