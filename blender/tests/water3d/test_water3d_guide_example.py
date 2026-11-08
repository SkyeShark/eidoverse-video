"""free-surface-water.md's own example, as written for the engine, run in Blender (numbers only, no render):

    const water = await createWaterSim(_r, { gridSize: [64, 48, 64], worldSize: [2, 1.5, 2],
      domainCenter: [0, 0.75, 0], initialLevel: 0.4, maxSpheres: 8, maxEmitters: 1 });
    await water.warmup(0.5);
    // in renderFrame: update collider/emitter controls, then await water.step(dt)

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_guide_example.py

The same options in camelCase, verbatim (create_water_sim reads the engine's camelCase names in the engine's
three.js axes), the engine's per-frame step(dt) with a sphere pushed down into the pool and an emitter pouring, both
moved every frame as a scene's renderFrame would.

Checks (PASS/FAIL): the still pool starts 0.4 m deep and settles level near it (a still start dips about 1 cm while
the pressure builds, in the engine too); a sphere lowered into it raises the water by its submerged volume; the
emitter adds water; without fill_target the controller holds the INITIAL volume through and after the pour (the
engine's default); camelCase and snake_case names give the same solver.
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim  # noqa: E402

ok = True
logs = []
sc = bpy.context.scene
water = create_water_sim(scene=sc, name='guide', cache_dir=os.path.join(S.OUT, 'guide_cache'),
                         gridSize=[64, 48, 64], worldSize=[2, 1.5, 2], domainCenter=[0, 0.75, 0],     # the engine's, verbatim
                         initialLevel=0.4, maxSpheres=8, maxEmitters=1, log=lambda *a: logs.append(a))
S0 = water.solver
DX = S0.DX


def level():
    """The mean surface height (Blender z) over interior columns away from the centre, from phi."""
    ph = S0.phi()
    nz, ny, nx = ph.shape
    hs = []
    for k in range(8, nz - 8, 4):
        for i in range(8, nx - 8, 4):
            if abs(i - nx / 2) < 12 and abs(k - nz / 2) < 12:
                continue
            c = ph[k, :, i]
            js = np.where((c[:-1] < 0) & (c[1:] >= 0))[0]
            if len(js):
                j = js[-1]
                hs.append((j + 0.5 + c[j] / (c[j] - c[j + 1])) * DX)
    return float(np.mean(hs)) if hs else float('nan')


v0 = water.measure_volume()
z0 = level()
ok &= S.check('the still pool starts 0.4 m deep', abs(z0 - 0.4) < 0.01, f'{z0:.4f} m')
water.warmup(0.5)
ok &= S.check('warmup(0.5) advances half a second', abs(water.sim_time - 0.5) < 1e-6, f'{water.sim_time:.3f} s')
for f in range(45):                                         # the scene's opening frames: the start transient settles
    water.step(1 / 30)
z1, v1 = level(), water.measure_volume()
# a still start dips about 1 cm while the pressure builds from zero (the engine does the same), then the volume
# controller brings it back
ok &= S.check('the pool settles level near 0.4 m', abs(z1 - 0.4) < 0.015, f'{z1:.4f} m at {water.sim_time:.1f} s')
# a sphere of r 0.25 lowered until its centre sits on the waterline (half submerged), held for a second
R = 0.25
for f in range(60):
    zc = 1.0 - min(f / 30, 1.0) * 0.6                          # 1.0 -> 0.4 over a second, then held
    water.set_spheres([dict(x=0.0, y=0.0, z=zc, r=R)])
    water.step(1 / 30)
z2, v2 = level(), water.measure_volume()
interior = (2.0 - 2 * 2.0 * 1.5 / 64) ** 2
# half a sphere's volume over the tank floor, plus whatever the controller added or the solver lost meanwhile
want = (2 / 3 * math.pi * R ** 3 + (v2 - v1)) / interior
ok &= S.check('the half-submerged sphere raises the pool by its displaced volume', abs((z2 - z1) - want) < 0.35 * want,
              f'rise {(z2 - z1) * 1000:.1f} mm vs {want * 1000:.1f} mm')
water.set_spheres([])
# an emitter pouring for a second (the controller keeps its initial target: the engine's default)
v_before = water.measure_volume()
for f in range(30):
    water.set_emitters([dict(x=0.5, y=0.0, z=1.0, r=0.06, vx=0.0, vy=0.0, vz=-1.5)])
    water.step(1 / 30)
flux = water.emitter_flux()
v_after = water.measure_volume()
ok &= S.check('the emitter adds water while it runs', v_after > v_before + 0.3 * flux * 1.0,
              f'+{(v_after - v_before) * 1000:.1f} l in 1 s at a nominal {flux * 1000:.1f} l/s')
water.set_emitters([None])
for f in range(90):
    water.step(1 / 30)
v_end = water.measure_volume()
ok &= S.check('without fill_target the controller holds its initial target through and after a pour (the engine)',
              abs(v_end - v0) / v0 < 0.03, f'{v_after:.4f} after the pour -> {v_end:.4f} m3, target {v0:.4f}')
snake = create_water_sim(scene=sc, name='guide2', cache_dir=os.path.join(S.OUT, 'guide_cache'),
                         grid_size=(64, 64, 48), world_size=(2, 2, 1.5), domain_center=(0, 0, 0.75),
                         initial_level=0.4, max_spheres=8, max_emitters=1, log=lambda *a: None)
ok &= S.check('camelCase and snake_case options build the same solver',
              snake.solver.N == S0.N and snake.solver.NSPH == S0.NSPH == 8 and snake.solver.NEMI == S0.NEMI == 1
              and abs(snake.measure_volume() - v0) < 1e-6)
water.dispose()
snake.dispose()
print('ALL PASS' if ok else 'SOME FAIL')
