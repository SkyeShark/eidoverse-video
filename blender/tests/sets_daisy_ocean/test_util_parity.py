"""ocean/util.py against eidoverse/sets/ocean/util.js itself (run in deno by util_dump.mjs): the rng streams, the shot
maths (clamp01 smooth lerp seg ease), buildMips byte for byte on an odd-sized image, and the asset roots.

    python <worktree>/blender/tests/sets_daisy_ocean/test_util_parity.py        (system Python: no Blender needed)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import numpy as np  # noqa: E402

from eidoblend.sets.daisy.ocean import util as U  # noqa: E402

ck = C.Checks('util')
dst = os.path.join(C.OUT, 'util_js.json')
subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(C.HERE, 'util_dump.mjs'), dst], cwd=C.REPO,
               check=True)
with open(dst) as f:
    js = json.load(f)
worst = 0.0
for seed, vals in js['rng'].items():
    R = U.rng(int(seed))
    worst = max(worst, max(abs(R() - v) for v in vals))
ck.check('rng(seed): the same uint32 stream as util.js (6 seeds x 64 draws)', worst == 0.0, f'max diff {worst:.1e}')
mw = 0.0
for u, a, b, c01, sm, lp, sg, es in js['maths']:
    ours = (U.clamp01(u), U.smooth(u), U.lerp(a, b, u), U.seg(u, a, b), U.ease(u, a, b))
    mw = max(mw, max(abs(x - y) for x, y in zip(ours, (c01, sm, lp, sg, es))))
ck.check('clamp01 / smooth / lerp / seg / ease = util.js (200 cases)', mw < 1e-12, f'max diff {mw:.1e}')
src = np.array(js['src']['data'], np.uint8).reshape(js['src']['h'], js['src']['w'], 4)
ours = U.build_mips(src)
same = len(ours) == len(js['mips']) and all(
    o['width'] == m['w'] and o['height'] == m['h'] and np.array_equal(o['data'].reshape(-1), np.array(m['data'], np.uint8))
    for o, m in zip(ours, js['mips']))
ck.check('build_mips = buildMips byte for byte (37 x 23 down to 1 x 1, clamped odd edges)', same,
         f"{len(ours)} levels vs {len(js['mips'])}")
flat = U.build_mips(src.reshape(-1), js['src']['w'], js['src']['h'])
ck.check('build_mips takes the flat (data, w, h) form too', all(np.array_equal(a['data'], b['data']) for a, b in zip(flat, ours)))
norm = lambda p: os.path.normcase(os.path.normpath(p))  # noqa: E731
roots = js['assets']
ck.check('asset roots = util.js (OCEAN_ASSETS, MODELS, ENGINE_ASSETS)',
         norm(U.OCEAN_ASSETS) == norm(roots['OCEAN_ASSETS']) and norm(U.MODELS) == norm(roots['MODELS'])
         and norm(U.ENGINE_ASSETS) == norm(roots['ENGINE_ASSETS']), f"{U.MODELS}")
ok = ck.summary()
with open(os.path.join(C.OUT, 'test_util_parity.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
sys.exit(0 if ok else 1)
