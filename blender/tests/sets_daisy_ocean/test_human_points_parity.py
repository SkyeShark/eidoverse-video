"""The human of light's 5200 points against apparitions.js itself: human_points_dump.mjs runs the untouched module in
deno with three's GLTFLoader on ocean_human.glb; the port reads the same GLB's triangles as three does (glb_triangles)
and draws the same rng(13) samples and rng(17) twinkles; build_apparitions must put exactly those points on the
points mesh (holder-local, Blender axes).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_human_points_parity.py
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.sets.daisy.ocean import apparitions as A  # noqa: E402
from eidoblend.sets.daisy.ocean.util import MODELS, rng  # noqa: E402

ck = C.Checks('human')
work = os.path.join(C.OUT, 'human_only')
os.makedirs(work, exist_ok=True)
shutil.copyfile(os.path.join(MODELS, 'ocean_human.glb'), os.path.join(work, 'x_human.glb'))   # no robot.glb beside it
tb = os.path.dirname(C.THREE_BUILD).replace('\\', '/')
imap = os.path.join(work, 'import_map.json')
with open(imap, 'w') as f:
    json.dump({'imports': {'three': f'file:///{tb}/build/three.webgpu.js', 'three/webgpu': f'file:///{tb}/build/three.webgpu.js',
                           'three/tsl': f'file:///{tb}/build/three.tsl.js', 'three/addons/': f'file:///{tb}/examples/jsm/'}}, f)
dst = os.path.join(work, 'human_points_js.json')
subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={imap}',
                os.path.join(C.HERE, 'human_points_dump.mjs'), C.THREE_BUILD, work.replace('\\', '/') + '/x_', dst],
               cwd=C.REPO, check=True)
with open(dst) as f:
    js = json.load(f)
jc = np.array(js['center'], np.float64)
jr = np.array(js['rnd'], np.float64)

# ---- the sampling itself (numpy, three's axes)
g3 = A.glb_triangles(os.path.join(MODELS, 'ocean_human.glb'))
ck.check('glb_triangles reads the human as three does', g3 is not None and len(g3[0]) == 58000, f'{len(g3[0]) if g3 else 0} triangles')
pts3 = A.sample_surface(g3[0], 5200, 13)
pts3[:, 1] -= g3[1]
d = np.linalg.norm(pts3 - jc, axis=1)
ck.check('the 5200 points = apparitions.js sampleSurface (same triangles, same rng(13) draws)',
         len(pts3) == len(jc) and d.max() < 1e-5, f'max {d.max() * 1000:.4f} mm, all {len(jc)} points')
R = rng(17)
ours_r = np.array([[R(), R(), R(), R()] for _ in range(len(jc))])
ck.check('their twinkle draws = rng(17)', np.abs(ours_r - jr).max() < 1e-6, f'max {np.abs(ours_r - jr).max():.1e}')

# ---- on the built points mesh (holder-local, Blender axes)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
app = A.build_apparitions(base=(0.0, 0.0, 0.0), yaw=0.0)
me = app.human['points'].data
cen = np.zeros(len(me.vertices) * 3, np.float32)
me.attributes['center'].data.foreach_get('vector', cen)
cen = cen.reshape(-1, 3)[::4]
b3 = np.stack([cen[:, 0], cen[:, 2], -cen[:, 1]], 1)                  # Blender -> three
d = np.linalg.norm(b3 - jc, axis=1)
ck.check('build_apparitions puts the WebGPU edition\'s points on its mesh (holder-local)', d.max() < 1e-4,
         f'max {d.max() * 1000:.4f} mm (float32 attribute)')
ok = ck.summary()
with open(os.path.join(C.OUT, 'test_human_points_parity.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
