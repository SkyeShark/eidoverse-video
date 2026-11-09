"""Water dropped onto water: a 0.12 m ball of water thrown down at 2 m/s into a still pool 0.4 m deep (the watertest's
2 x 2 x 1.5 m tank), with the engine's solver (the defaults) and with DROP_SOLVER, at 64 and 128 cells across.
Numbers only (no render), so it runs directly:

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_drop_ball.py [-- res=64,128]

Per run, along the ball's axis: the height above the pool at which its underside leaves free fall (trails the free-fall
path by more than a cell), the frame it meets the pool against the frame a free fall would (60 fps), and the crater
(the lowest the pool surface at the impact point drops in the 0.3 s after the landing).

Checks (PASS/FAIL): with DROP_SOLVER the underside keeps free fall closer to the pool than with the engine's solver and
lands no later; every run keeps the poured volume within 8 % (the default controller is still restoring the splash's
loss at the end).
"""

import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, DROP_SOLVER, ENGINE_SOLVER  # noqa: E402

A = S.args()
RES = [int(r) for r in A.get('res', '64,128').split(',')]
FPS = 60
R, V0, Z0, LEVEL = 0.12, 2.0, 1.1, 0.4                 # ball radius, throw speed, centre height, pool depth (m)
G = 9.8
sc = bpy.context.scene
sc.render.fps = FPS
ok = True
results = {}


def column(w):
    """phi along the vertical through the domain centre (Blender z up, from the floor), and the cell heights."""
    ph = w.solver.phi()                                  # [z3][y3 up][x3]
    nz, ny, nx = ph.shape
    col = 0.5 * (ph[nz // 2, :, nx // 2] + ph[nz // 2 - 1, :, nx // 2 - 1])
    zs = (np.arange(ny) + 0.5) / ny * 1.5
    return col, zs


def crossing(col, zs, j):
    """The height where phi crosses zero between cells j and j + 1."""
    a, b = col[j], col[j + 1]
    return zs[j] + (zs[j + 1] - zs[j]) * (a / (a - b)) if a != b else zs[j]


for n in RES:
    for tag, preset in (('engine', ENGINE_SOLVER), ('drop', DROP_SOLVER)):
        logs = []
        w = create_water_sim(scene=sc, name=f'drop_{tag}_{n}', cache_dir=os.path.join(S.OUT, 'drop_cache'),
                             grid_size=(n, n, n * 3 // 4), world_size=(2.0, 2.0, 1.5), domain_center=(0, 0, 0.75),
                             initial_level=LEVEL, max_emitters=1, measure_volume=True,
                             log=lambda *a: logs.append(a), **preset)
        dx = w.solver.DX
        rec = []

        def controls(frame, t, ww):
            ww.set_emitters([dict(x=0, y=0, z=Z0, r=R, vx=0, vy=0, vz=-V0)] if frame == 1 else [None])
            if frame > 1:
                col, zs = column(ww)
                water = col < 0
                # the pool: water contiguous from the floor; the ball: the lowest water above the first air gap
                j = 0
                while j < len(col) - 1 and water[j + 1]:
                    j += 1
                pool_top = crossing(col, zs, j)
                k = j + 1
                while k < len(col) - 1 and not water[k + 1]:
                    k += 1
                under = crossing(col, zs, k) if k < len(col) - 1 else None
                rec.append((t, pool_top, under))

        w.bake(1, int(0.75 * FPS), controls=controls, mesh_frames=[], fill_target='poured', log=lambda *a: None)
        # the stamp is on the first frame's substeps; free fall from there (the bottom of the ball)
        t0 = 1.0 / FPS
        ff = lambda t: (Z0 - R) - V0 * (t - t0) - 0.5 * G * (t - t0) ** 2           # noqa: E731
        t_ff_land = t0 + (-V0 + np.sqrt(V0 * V0 + 2 * G * (Z0 - R - LEVEL))) / G
        leave = land = None
        for t, pool_top, under in rec:
            if under is None:
                if land is None:
                    land = t
                continue
            if leave is None and under - ff(t) > dx:
                leave = (t, ff(t) - LEVEL)
        after = [p for t, p, u in rec if land is not None and land <= t <= land + 0.3]
        crater = LEVEL - min(after) if after else 0.0
        vol = w.measure_volume()
        target = w.uniforms.vol_target
        results[(n, tag)] = dict(leave=leave[1] if leave else 0.0, late=(land - t_ff_land) * FPS if land else None,
                                 crater=crater, vol=vol / target)
        r = results[(n, tag)]
        print(f'[drop] {n:3d} {tag:6s}: leaves free fall {r["leave"] * 100:5.1f} cm above the pool; lands '
              + (f'{r["late"]:+.1f} frames' if r['late'] is not None else 'never') + f' against a free fall; '
              f'crater {crater * 100:.1f} cm; volume {r["vol"] * 100:.1f} % of its target', flush=True)
        # the default controller (0.35/s) is still restoring the splash's loss 0.4 s after the landing
        ok &= S.check(f'{n} {tag}: the volume holds within 8 % of the poured target', abs(r['vol'] - 1) < 0.08,
                      f'{r["vol"] * 100:.1f} %')
        w.dispose()
    e, d = results[(n, 'engine')], results[(n, 'drop')]
    ok &= S.check(f'{n}: DROP_SOLVER keeps free fall closer to the pool and lands no later than the engine\'s solver',
                  d['leave'] < e['leave'] and d['late'] is not None and (e['late'] is None or d['late'] <= e['late']),
                  f'leaves {d["leave"] * 100:.1f} vs {e["leave"] * 100:.1f} cm; lands {d["late"]:+.1f} vs '
                  + (f'{e["late"]:+.1f}' if e['late'] is not None else 'never') + ' frames against a free fall')
print('ALL PASS' if ok else 'SOME FAIL')
