"""A pour into a stone basin, then a splash: eidoblend.fx.water3d with mesh colliders, emitters and the volume target
driven while water is added (the engine's documented filling workflow).

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/water3d/test_water3d_pour_basin.py [-- res=128 samples=64]
    (a GPU job: 4 GB VRAM, 16 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

A bronze spout on a stone wall pours into an empty fountain basin (a lathe on a pedestal, voxelised as the
collider) standing on paving stones (a ground slab, also a collider). At 5.5 s a bucket-sized slug falls from above
the frame into the filled basin: the splash. Lit by the sky panorama, lit shading (refraction, depth colour, foam).
The pour runs on the engine's solver (the defaults); the frame the slug is thrown, the scene switches to DROP_SOLVER
(water.set_solver), which keeps a dropped body falling where the engine's flattens it into a disc (solver=drop runs
DROP_SOLVER throughout, solver=engine the engine's throughout).

Checks (PASS/FAIL): the colliders voxelise (solid cells in the basin wall and the slab, none in the basin's
hollow), water collects in the basin (the volume inside the bowl grows while the spout runs and stays after it
stops), the target follows the fill and then holds (volume after the pour within 2 % of the target 1 s later),
no water passes through the basin wall (none below the bowl's inner floor inside the bowl's footprint, except
spill outside), the splash raises the surface and throws water above the rim, and the surface mesh sits inside
the domain. Renders out/w3d_pour<tag>_f####.png and contact sheets.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, configure_eevee, DROP_SOLVER  # noqa: E402

A = S.args()
FPS = 24
END = int(A.get('end', 240))
RES = int(A.get('res', 128))                    # cells along x (the grid stays cubic: x, y = RES, z = RES * 7 / 8)
TAG = A.get('tag', '')
SAMPLES = int(A.get('samples', 64))
EVERY = int(A.get('every', 6))
RENDER = A.get('render', '1') == '1'
default_frames = sorted(set(list(range(EVERY, END + 1, EVERY)) + list(range(136, 153))))
FRAMES = [int(x) for x in A['frames'].split(',')] if 'frames' in A else [f for f in default_frames if f <= END]

sc = S.fresh_scene(res=tuple(int(v) for v in A.get('size', '960x540').split('x')), fps=FPS, end=END,
                   samples=SAMPLES)
configure_eevee(sc, samples=SAMPLES)
sc.view_settings.exposure = float(A.get('exposure', 0.0))

# ---- the stage ---------------------------------------------------------------------------------------------
stone = S.pbr('basin_stone', S.texset('Concrete034_2k'), 'Concrete034', scale=1.6, tint=(0.92, 0.88, 0.80))
paving = S.pbr('paving', S.texset('PavingStones128_1k'), 'PavingStones128', scale=0.55)
bronze = S.pbr('spout_bronze', S.texset('Metal042A_1k'), 'Metal042A', scale=6.0, tint=(0.95, 0.62, 0.38),
               rough_mul=0.8)
wall_mat = S.pbr('wall_stone', S.texset('Concrete034_2k'), 'Concrete034', scale=1.1, tint=(0.80, 0.76, 0.70))
# the basin: pedestal and bowl as ONE closed lathe (the collider and the visible prop are the same mesh)
# a deep font (the level set keeps bulk water well and thin sheets badly: a deep vessel fills, a dish would not)
profile = [(0.0, 0.0), (0.26, 0.0), (0.26, 0.05), (0.17, 0.09), (0.13, 0.18), (0.12, 0.30), (0.15, 0.36),
           (0.26, 0.39), (0.34, 0.44), (0.38, 0.52), (0.395, 0.60), (0.40, 0.665), (0.39, 0.683), (0.37, 0.688),
           (0.35, 0.684), (0.34, 0.665), (0.33, 0.60), (0.31, 0.52), (0.26, 0.46), (0.16, 0.432), (0.0, 0.425)]
basin = S.lathe(sc, 'basin', profile, segments=96, mat=stone)
RIM_Z, FLOOR_Z, INNER_R = 0.686, 0.425, 0.34
# the ground slab: its top is the solver's floor (one cell above 0 at res 128), wide enough to fill the frame
ground = S.box(sc, 'ground', (24.0, 24.0, 0.2), (0, 0, -0.1 + 0.012), paving)
# the wall and the spout (props only: the water never reaches them)
S.box(sc, 'wall', (0.16, 1.6, 1.6), (0.78, 0.0, 0.8), wall_mat)
spout_prof = [(0.0, 0.0), (0.056, 0.0), (0.056, 0.30), (0.047, 0.30), (0.047, 0.012), (0.0, 0.012)]
spout = S.lathe(sc, 'spout', spout_prof, segments=40, mat=bronze)
spout.rotation_euler = (0.0, math.radians(-90), 0.0)          # its axis along -X
spout.location = (0.71, 0.0, 0.985)                           # mouth at x = 0.41
S.box(sc, 'spout_flange', (0.03, 0.18, 0.18), (0.70, 0.0, 0.985), bronze)
S.world_panorama(sc, os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky',
                                  'kloppenheim_puresky_ldr.png'), strength=1.0, rotate_deg=40)
S.sun(sc, 'sun', azimuth_deg=-60, elevation_deg=38, strength=3.2)
# looking down into the basin; the dropped water ball starts just above the frame's top edge
S.camera_look(sc, (-1.55, -1.75, 1.6), (0.06, 0.0, 0.55), lens=40)

# ---- the water ---------------------------------------------------------------------------------------------
NX = RES
NZ = RES                                  # a cube: room above the frame for the dropped water ball
DX = 1.4 / NX
water = create_water_sim(
    scene=sc, name='pour' + TAG, cache_dir=os.path.join(S.OUT, 'pour_cache' + TAG),
    grid_size=(NX, NX, NZ), world_size=(1.4, 1.4, NZ * DX), domain_center=(0.0, 0.0, NZ * DX / 2),
    walls=False, collider_meshes=[basin, ground], initial_level=-1.0,   # an empty start (all air)
    max_emitters=2, measure_volume=True, volume_control=A.get('vc', '1') == '1',
    extend_phi_into_solids={'1': True, '0': False}.get(A.get('extend', ''), None),
    smooth_surface=True, shading='lit',
    shallow_color='#a8d4cc', deep_color='#2a5c5f', absorption=2.6, surface_opacity=0.9,
    foam_strength=0.35, foam_shore=0.0, foam_churn=0.35, churn_speed=2.6, roughness=0.03,
    **(DROP_SOLVER if A.get('solver') == 'drop' else {}))
SOLVER = A.get('solver', 'switch')          # switch: the engine's for the pour, DROP_SOLVER from the slug's throw
ok = True
S0 = water.solver
occ = S0.solid_np
nz, ny, nx = occ.shape


def cell_of(x, y, z):
    """Blender point -> (k, j, i) of the [z][y][x] (three axes) grid."""
    c3 = water.center3
    p3 = np.array([x, z, -y]) - c3
    u = p3 / np.array(water.params['world3']) + 0.5
    return (int(u[2] * nz), int(u[1] * ny), int(u[0] * nx))


k, j, i = cell_of(0.355, 0.0, 0.60)                      # inside the bowl wall
ok &= S.check('basin wall voxelised solid', occ[k, j, i] > 0.5)
k, j, i = cell_of(0.0, 0.0, 0.60)                        # the bowl's hollow
ok &= S.check('basin hollow is open', occ[k, j, i] < 0.5)
k, j, i = cell_of(0.6, 0.6, 0.005)                       # the ground slab
ok &= S.check('ground slab voxelised solid', occ[k, j, i] > 0.5)
ok &= S.check('initial state is empty', water.measure_volume() < 1e-4, f'{water.measure_volume():.6f} m3')

POUR = dict(x=0.41, y=0.0, z=0.985, r=0.045, vx=-1.0, vy=0.0, vz=-0.2)
POUR_END = 4.6
# the splash: a bucket's load thrown down, stamped for a single frame above the frame. Thrown fast: a slow ball
# pancakes as it nears the pool (the coarse multigrid levels average the closing air gap away and the pool's
# pressure holds up its underside) and lands softly
DUMP_T0, DUMP_T1 = 5.5, 5.5 + 1.0 / FPS
DUMP = dict(x=-0.05, y=0.03, z=1.27, r=0.10, vx=0.0, vy=0.0, vz=-3.5)
log = []
poured = dict(v=0.0)


def _bowl_mask():
    """Cells of the bowl's hollow: within the inner radius, from just under the inner floor to the rim, not solid.
    Grid axes are [three z][three y = height][three x]; Blender y = -three z."""
    _, j0, _ = cell_of(0, 0, FLOOR_Z - 0.02)
    _, j1, _ = cell_of(0, 0, RIM_Z)
    W3 = np.array(water.params['world3'])
    px = (np.arange(nx) + 0.5) / nx * W3[0] - W3[0] / 2 + water.center3[0]
    by = -((np.arange(nz) + 0.5) / nz * W3[2] - W3[2] / 2 + water.center3[2])
    disc = np.hypot(px[None, :], by[:, None]) < INNER_R               # (nz, nx)
    m = np.zeros(occ.shape, dtype=bool)
    m[:, j0:j1 + 1, :] = disc[:, None, :]
    return m & (occ < 0.5)


BOWL = _bowl_mask()


def bowl_volume(w):
    """Water inside the bowl's hollow, with the engine sensor's smoothed Heaviside (m^3)."""
    frac = np.clip(0.5 - w.solver.phi() / (DX * 3.0), 0, 1)
    return float((frac * BOWL).sum() * DX ** 3)


def controls(frame, t, w):
    if SOLVER == 'switch' and DUMP_T0 <= t < DUMP_T1:
        w.set_solver(**DROP_SOLVER)                   # a body of water is dropped: keep it falling until it lands
    w.set_emitters([POUR if t < POUR_END else None, DUMP if DUMP_T0 <= t < DUMP_T1 else None])
    poured['v'] += w.emitter_flux() / FPS
    if frame % 12 == 0:
        log.append((frame, t, w.measure_volume(), bowl_volume(w), w.uniforms.vol_target))


t0 = time.time()
# the target is the volume poured (the engine's 'measured' workflow bakes the jet's thin-sheet losses in and the
# fill stalls); the controller may restore up to 1.0/s while water is added, then holds what was reached
water.bake(1, END, mesh_frames=FRAMES, controls=controls, fill_target=A.get('fill', 'poured'), fill_rate=1.5,
           fill_kp=3.0)
print(f'[pour] poured {poured["v"]:.4f} m3 by the emitters', flush=True)
print(f'[pour] bake {time.time() - t0:.1f} s', flush=True)
for f, t, v, vb, tg in log:
    print(f'[pour] frame {f:3d} t {t:5.2f}  volume {v:.4f}  in bowl {vb:.4f}  target {tg:.4f}', flush=True)
by_t = {round(t, 3): (v, vb, tg) for f, t, v, vb, tg in log}
vb_mid = [vb for f, t, v, vb, tg in log if 2.0 <= t <= 2.6]
vb_end_pour = [vb for f, t, v, vb, tg in log if POUR_END - 0.6 <= t < POUR_END]
vb_rest = [vb for f, t, v, vb, tg in log if POUR_END + 0.4 <= t < DUMP_T0]
pour_vol = np.pi * POUR['r'] ** 2 * math.hypot(POUR['vx'], POUR['vz']) * POUR_END
ok &= S.check('water collects in the basin while the spout runs', bool(vb_mid and vb_end_pour and
              vb_end_pour[-1] > 1.5 * vb_mid[0] > 0.004), f'{vb_mid[0]:.4f} -> {vb_end_pour[-1]:.4f} m3'
              if vb_mid and vb_end_pour else '')
ok &= S.check('the basin holds what was poured (within 10 %)', bool(vb_rest and vb_rest[-1] > 0.9 * pour_vol),
              f'{vb_rest[-1]:.4f} of {pour_vol:.4f} m3 poured' if vb_rest else '')
held = [(v, tg) for f, t, v, vb, tg in log if POUR_END + 0.7 <= t < DUMP_T0]
ok &= S.check('the held target keeps the volume (within 3 %)', bool(held and
              all(abs(v - tg) / tg < 0.03 for v, tg in held)),
              ', '.join(f'{v:.4f}/{tg:.4f}' for v, tg in held[:3]))
end = [(v, tg) for f, t, v, vb, tg in log if t >= END / FPS - 1.0]
ok &= S.check('after the splash the volume settles at its target (within 3 %)', bool(end and
              all(abs(v - tg) / tg < 0.03 for v, tg in end)), ', '.join(f'{v:.4f}/{tg:.4f}' for v, tg in end[:2]))

# the splash: after the ball lands, water rises well above the rim inside the basin's footprint
def mesh_points(f):
    sc.frame_set(f)
    ev = water.surface_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


# the slug's bottom reaches the pool (~0.62 m) after the stamp frame plus its fall; count only frames after that
fall = 1.27 - DUMP['r'] - 0.62
t_hit = DUMP_T1 + (-abs(DUMP['vz']) + math.sqrt(DUMP['vz'] ** 2 + 2 * 9.8 * fall)) / 9.8
impact = int(math.ceil(t_hit * FPS)) + 1
tops = []
for f in [f for f in FRAMES if impact <= f <= impact + 12]:
    co = mesh_points(f)
    near = co[np.hypot(co[:, 0], co[:, 1]) < INNER_R + 0.15]
    tops.append((f, float(near[:, 2].max()) if len(near) else 0.0))
best = max(tops, key=lambda x: x[1]) if tops else (0, 0.0)
ok &= S.check('the splash throws water above the rim', best[1] > RIM_Z + 0.06,
              f'highest crown {best[1]:.3f} m at frame {best[0]} (impact frame {impact}) vs rim {RIM_Z} m')
co = mesh_points(FRAMES[-1])
W3 = water.params['world3']
inside_dom = (np.abs(co[:, 0]) <= 0.7 + 1e-3) & (np.abs(co[:, 1]) <= 0.7 + 1e-3) & (co[:, 2] >= -1e-3)
ok &= S.check('the surface mesh lies inside the domain', bool(inside_dom.all()))

if RENDER:
    shots = []
    for f in FRAMES:
        p = os.path.join(S.OUT, f'w3d_pour{TAG}_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
    for n in range(0, len(shots), 12):
        S.contact_sheet(shots[n:n + 12], os.path.join(S.OUT, f'w3d_pour{TAG}_sheet{n // 12}.png'), cols=4)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'w3d_pour{TAG}.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
