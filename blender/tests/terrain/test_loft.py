"""Loft: the Blender port against the engine's own loft.js (vertex for vertex), and a probe still.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain/test_loft.py --no-render
    bash run_blender.sh .../test_loft.py
    (the probe still's ground is make_terrain's: its kernels make it a GPU job, 4 GB VRAM, 12 GB RAM cap; on a
    shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Parity: Node runs eidoverse/loft.js (three from node_modules: this checkout's, else the main
checkout's) for the same sweeps; the walls' vertices must agree to float32 precision after the axis
map three (x, y, z) -> Blender (x, -z, y). Probe: out/loft.png (a morphing, twisting horn, a
tapered tentacle and a ribbon road, on a small terrain).
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain import loft  # noqa: E402
from eidoblend.placement import place_on  # noqa: E402


def three_module():
    roots = [F.WORKTREE]
    git = F.WORKTREE / '.git'
    if git.is_file():
        roots.append(Path(git.read_text().split(':', 1)[1].strip()).parents[2])
    for r in roots:
        p = r / 'node_modules' / 'three' / 'build' / 'three.module.js'
        if p.is_file():
            return p
    return None


CASES = [
    dict(path=[[0, 0, 0], [0.3, 1.0, 0.2], [1.0, 1.6, -0.4], [1.8, 1.7, -0.2]], profile=dict(kind='circle', r=0.3, n=32),
         end=dict(kind='star', ro=0.18, ri=0.07, points=16), sections=40, scale='taper', twist=math.pi),
    dict(path=[[0, 0, 0], [1, 0, 0], [2, 0.5, 1], [2, 2, 2]], profile=dict(kind='star', ro=0.4, ri=0.2, points=5),
         end=None, sections=24, scale=1, twist=0),
    dict(path=[[0, 0, 0], [0, 2, 0], [0.01, 4, 0.02]], profile=dict(kind='circle', r=0.2, n=12),
         end=None, sections=8, scale=1.5, twist=0.5),
]


def ring(d):
    return loft.star(d['ro'], d['ri'], d['points']) if d['kind'] == 'star' else loft.circle(d['r'], d['n'])


ok_all = True
node, three = shutil.which('node'), three_module()
if not node or not three:
    print('[loft-test] parity SKIPPED (needs node and node_modules/three)')
else:
    for k, c in enumerate(CASES):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'loft.json'
            r = subprocess.run([node, str(F.HERE / 'loft_dump.mjs'), str(three), str(F.WORKTREE / 'eidoverse' / 'loft.js'),
                                json.dumps(c), str(out)], capture_output=True, text=True)
            if r.returncode or not out.exists():
                print('[loft-test] node failed', r.stdout, r.stderr)
                ok_all = False
                continue
            js = json.loads(out.read_text())
        P = np.asarray(js['position'], dtype=np.float64).reshape(-1, 3)
        cols = len(ring(c['profile']))
        rows = c['sections']
        wall = P[:rows * (cols + 1)].reshape(rows, cols + 1, 3)[:, :cols].reshape(-1, 3)
        o = loft.sweep([(p[0], -p[2], p[1]) for p in c['path']], profile=ring(c['profile']),
                       profile_end=ring(c['end']) if c['end'] else None, sections=rows,
                       scale=(lambda t: 1 - 0.6 * t) if c['scale'] == 'taper' else c['scale'],
                       twist=c['twist'], name='parity_%d' % k)
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        mine = np.stack([co[:, 0], co[:, 2], -co[:, 1]], axis=1)[:rows * cols]
        err = float(np.abs(mine - wall).max())
        good = err < 1e-5
        ok_all = ok_all and good
        print('[loft-test] %s parity case %d: %d x %d wall vertices, max |blender - engine| %.2e m'
              % ('PASS' if good else 'FAIL', k, rows, cols, err))
        bpy.data.objects.remove(o)

if '--no-render' not in F.args():
    F.clean_scene()
    F.render_settings(960, 540, 16)
    F.test_daylight(sun_elevation=35, sun_azimuth=210)
    ground, h = F.ground(size=20, seed=5, clearing_m=7, relief_m=0.6)
    brass = bpy.data.materials.new('brass')
    bs = brass.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (0.75, 0.55, 0.25, 1)
    bs.inputs['Metallic'].default_value = 1.0
    bs.inputs['Roughness'].default_value = 0.28
    horn = loft.sweep([(0, 0, 0.3), (0.25, 0.1, 1.0), (0.9, -0.2, 1.6), (1.7, -0.1, 1.75)],
                      profile=loft.circle(0.32, 48), profile_end=loft.star(0.2, 0.08, 24), sections=64,
                      scale=lambda t: 1 - 0.55 * t, twist=math.pi, material=brass, name='horn')
    horn.location = (-1.8, 0.5, 0)
    flesh = bpy.data.materials.new('flesh')
    fs = flesh.node_tree.nodes['Principled BSDF']
    fs.inputs['Base Color'].default_value = (0.42, 0.08, 0.07, 1)
    fs.inputs['Roughness'].default_value = 0.35
    fs.inputs['Subsurface Weight'].default_value = 0.4
    tent = loft.sweep([(0, 0, 0.12), (0.6, 0.4, 0.5), (0.4, 1.0, 1.1), (0.9, 1.5, 1.4), (1.5, 1.4, 1.2)],
                      profile=loft.ellipse(0.16, 0.12, 24), sections=80, scale=lambda t: (1 - t) ** 0.8 + 0.03,
                      twist=lambda t: 3 * t * t, material=flesh, name='tentacle', cap_end=True)
    tent.location = (1.2, -0.3, 0)
    road = loft.sweep([(-4, -2.5, 0.0), (-1, -3.2, 0.0), (2, -2.6, 0.0), (5, -3.4, 0.0)],
                      profile=[(-0.9, 0.0), (0.9, 0.0)], sections=60, closed=False, name='ribbon')
    road.location.z = 0.01
    for o in (horn, tent):
        place_on(o, ground)
    cam = F.camera('cam_loft', (-1.0, -6.8, 2.3), (0.0, 0.3, 0.9), 35)
    F.render(cam, F.OUT / 'loft.png')
print('[loft-test] %s' % ('PASS' if ok_all else 'FAIL'))
