"""The Blender port's heights against the WebGPU engine's own terrain.js, number for number.

Runs anywhere numpy does (system Python or Blender's):
    python blender/tests/terrain/test_parity.py
It runs eidoverse/terrain.js under Node (three.js from node_modules: this worktree's, else the
main checkout's), builds the same terrains with eidoblend.terrain._noise, and compares:
  - vertex heights: float32 bit-identical expected;
  - heightAt at scattered points (inside, on and outside the clearing's blend ring): equal to
    ~1e-15 (Math.hypot and C hypot may differ by an ulp);
  - the baked blend weights (R base, G mid, B steep): normals are float32-accumulated in three
    and float64 here, so a few 1e-6 at most;
  - UVs and the triangle split (b-d diagonal).
Exit status 0 = parity, 1 = a mismatch (printed), 2 = Node or three.js not found.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
sys.path.insert(0, str(WORKTREE / 'blender' / 'eidoblend' / 'terrain'))
import _noise  # noqa: E402  (imported as a plain module: no bpy needed)


def _main_checkout():
    git = WORKTREE / '.git'
    if git.is_file():                       # a worktree: "gitdir: <main>/.git/worktrees/<name>"
        line = git.read_text().strip()
        if line.startswith('gitdir:'):
            return Path(line.split(':', 1)[1].strip()).parents[2]
    return WORKTREE


def _three_module():
    for root in (WORKTREE, _main_checkout()):
        p = root / 'node_modules' / 'three' / 'build' / 'three.module.js'
        if p.is_file():
            return p
    return None


CASES = [
    # the guide's own example, a meadow with a clearing, a flat-free one, an odd seed and size
    dict(size=80, segments=160, amplitude=3, seed=7, flatRadius=8, nLayers=3),
    dict(size=120, segments=96, amplitude=2.2, seed=42, flatRadius=10, flatHeight=0.3, nLayers=3),
    dict(size=60, segments=64, amplitude=4, seed=0, nLayers=2, octaves=5, frequency=3.1),
    dict(size=33.3, segments=50, amplitude=1.5, seed=-12345, flatRadius=5, highStart=0.2,
         slopeSteep=[0.1, 0.3], nLayers=3),
]


def run():
    node = shutil.which('node')
    three = _three_module()
    if not node or not three:
        print('[parity] SKIPPED: needs node and node_modules/three (got node=%s, three=%s)' % (node, three))
        return 2
    terrain_js = WORKTREE / 'eidoverse' / 'terrain.js'
    rng = np.random.default_rng(3)
    ok = True
    for case in CASES:
        size = case['size']
        # the clearing's blend ring, where the smoothstep works
        t = rng.uniform(0, 2 * np.pi, 60)
        r = rng.uniform(0, 1.6 * case.get('flatRadius', 1), 60)
        probes = np.concatenate([
            rng.uniform(-size / 2, size / 2, (200, 2)),
            np.stack([np.cos(t) * r, np.sin(t) * r], axis=-1),
            [[0.0, 0.0], [size / 2, size / 2], [-size / 2, size / 3], [1e-9, -1e-9]],
        ]).tolist()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'dump.json'
            r = subprocess.run([node, str(HERE / 'parity_dump.mjs'), str(three), str(terrain_js),
                                json.dumps(case), json.dumps(probes), str(out)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not out.exists():
                print('[parity] node failed:', r.stdout, r.stderr)
                return 1
            js = json.loads(out.read_text())
        f32 = lambda s: np.frombuffer(base64.b64decode(s), dtype=np.float32)
        jpos = f32(js['position']).reshape(-1, 3)
        jcol = f32(js['color']).reshape(-1, 3) if js['color'] else None
        juv = f32(js['uv']).reshape(-1, 2)

        hf = _noise.Heightfield(size=size, amplitude=case['amplitude'], seed=case['seed'],
                                flat_radius=case.get('flatRadius', 0), flat_height=case.get('flatHeight', 0),
                                octaves=case.get('octaves', 4), frequency=case.get('frequency', 2.5),
                                slope_steep=case.get('slopeSteep', (0.25, 0.55)), high_start=case.get('highStart'))
        b = hf.build(case['segments'], n_layers=case['nLayers'])
        px = np.stack([b['X'].ravel(), b['H'].ravel(), b['Z'].ravel()], axis=-1)
        same_xz = np.array_equal(px[:, [0, 2]], jpos[:, [0, 2]])
        h_bits = int(np.count_nonzero(px[:, 1] != jpos[:, 1]))
        h_max = float(np.max(np.abs(px[:, 1].astype(np.float64) - jpos[:, 1])))
        p = np.asarray(probes)
        ha = hf.height_three(p[:, 0], p[:, 1])
        ha_max = float(np.max(np.abs(ha - np.asarray(js['heightAt']))))
        w_max = float(np.max(np.abs(b['weights'] - jcol))) if jcol is not None else 0.0
        uv_max = float(np.max(np.abs(b['uv'] - juv)))
        idx_ok = b['tris'].ravel()[:12].tolist() == js['index']
        line = ('[parity] size %g seg %d seed %s: xz identical %s | heights differing in bits %d (max %.3g m) | '
                'heightAt max %.3g m | weights max %.3g | uv max %.3g | index %s'
                % (size, case['segments'], case['seed'], same_xz, h_bits, h_max, ha_max, w_max, uv_max, idx_ok))
        print(line)
        good = same_xz and h_max <= 1e-6 and ha_max <= 1e-12 and w_max <= 1e-4 and uv_max <= 1e-7 and idx_ok
        ok = ok and good
    print('[parity] PASS' if ok else '[parity] FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(run())
