"""The dynamic sphere colliders against the engine itself: the spheretest scene's water, numbers only.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_spheretest_parity.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

engine_trace_spheretest.mjs ran fluid_water.js on the spheretest scene (a 0.26 m ball held over the dam break while it
settles, then lowered into the pool and swept through it, setSpheres once per frame) and wrote its volume sensor's
trace with the volume controller off (engine_trace_spheretest_novc.json) and on (engine_trace_spheretest.json). This
runs the same scene, its camelCase options verbatim, through create_water_sim and the engine's step(1/30), and holds
each trace to the engine's within 1 %, with the defaults and with extend_phi_into_solids=False. The edition's phi
extension into solids is for baked colliders and never enters a sphere, so a spheres-only scene runs the engine's
solver exactly. (When it also entered spheres, the pool lost 5.5 % more water than the engine's by 10 s with the
controller off, 6.3 % at worst.)
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim  # noqa: E402

sc = S.fresh_scene(res=(320, 180), fps=30, end=300, samples=1)
FPS, R = 30, 0.26
ok = True


def run(vc, extend):
    w = create_water_sim(scene=sc, name=f'sph_{vc}_{extend}', cache_dir=os.path.join(S.OUT, 'verify', 'sph_cache'),
                         gridSize=[64, 48, 64], worldSize=[2, 1.5, 2], domainCenter=[0, 0.75, 0], maxSpheres=4,
                         measureVolume=True, columnDepth=0.62, volumeControl=vc, extend_phi_into_solids=extend,
                         log=lambda *a: None)
    out = [(0.0, w.measure_volume())]
    for f in range(10 * FPS):
        t = f / FPS
        y = 1.30 if t < 3 else max(0.30, 1.30 - (t - 3) * 0.42)
        x = 0.0 if t < 5 else np.sin((t - 5) * 1.5) * 0.55
        w.set_spheres([dict(x=x, y=0.0, z=y, r=R)])               # three (x, y, 0) = Blender (x, 0, y)
        w.step(1 / FPS)
        if (f + 1) % 15 == 0:
            out.append((w.sim_time, w.measure_volume()))
    w.dispose()
    return out


for vc, ref_name in ((False, 'engine_trace_spheretest_novc.json'), (True, 'engine_trace_spheretest.json')):
    ref = json.load(open(os.path.join(S.HERE, ref_name)))['trace']
    for extend, label in ((False, 'extend_phi_into_solids=False'), (None, 'the defaults')):
        mine = run(vc, extend)
        errs = [abs(m[1] - r[1]) / r[1] for m, r in zip(mine, ref)]
        worst = int(np.argmax(errs))
        tol = 0.01
        ok &= S.check(f'volume control {"on" if vc else "off"}, {label}: the trace follows the engine\'s '
                      f'(< {tol * 100:.0f} %)', max(errs) < tol,
                      f'{len(errs)} samples, max {max(errs) * 100:.2f} % at t {mine[worst][0]:.1f} s '
                      f'({mine[worst][1]:.4f} vs {ref[worst][1]:.4f} m3); end {mine[-1][1]:.4f} vs {ref[-1][1]:.4f}')
print('ALL PASS' if ok else 'SOME FAIL')
