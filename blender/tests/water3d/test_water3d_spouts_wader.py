"""The chorus scene's water in Blender: an empty stone basin filled on camera by spouts, a wader walking through it
as sphere colliders, the luminous jade palette.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/water3d/test_water3d_spouts_wader.py [-- samples=48]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The chorus scene (work/chorus/scene.js) at a fifth of its scale: the basin is a
revolved bowl voxelised as the only collider (walls off), the sim starts EMPTY (initialLevel below the floor) and the
spouts fill it (one emitter per mouth, falling at 5 m/s with a slight inward lean, as its setEmitters); his body is a
set of spheres set every frame (bake(track_spheres=...)); and its water options carry over: velSmooth 0 ("water, not
goo"), maxSpeed 15, foamShore 0, smoothSurface, the jade palette (deep #04262a, shallow #2ba393, sky #e8a077,
absorption 2.45, opacity 0.62, emissive #1ee0c2 0.5 falloff 3.8, foam #cdf3ea 0.8 width 0.085, sparkle 0.65 / 38 /
1.0, keyLightDir toward the low red sun). The volume target follows the water poured (fill_target='poured'), the
Blender edition of the volumeTarget the scene had to set by hand.

Checks (PASS/FAIL): the basin wall voxelises solid and its hollow open; the basin fills while the spouts run (the
volume in the bowl grows to most of what was poured); no water inside the wader's spheres; the surface stays inside
the domain. Renders out/w3d_spouts<tag>_f####.png (filling, the wader in the pool, the end) and a sheet.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, configure_eevee  # noqa: E402

A = S.args()
FPS = 24
END = int(A.get('end', 192))
TAG = A.get('tag', '')
SAMPLES = int(A.get('samples', 48))
FRAMES = [int(x) for x in A.get('frames', '48,96,144,192').split(',')]
sc = S.fresh_scene(res=(960, 540), fps=FPS, end=END, samples=SAMPLES)
configure_eevee(sc, samples=SAMPLES)
sc.view_settings.exposure = float(A.get('exposure', 0.4))

# ---- the stage: a dusk basin -------------------------------------------------------------------------------
stone = S.pbr('basin_stone', S.texset('Concrete034_2k'), 'Concrete034', scale=0.9, tint=(0.55, 0.50, 0.46))
ground_m = S.pbr('ground', S.texset('PavingStones128_1k'), 'PavingStones128', scale=0.4,
                 tint=(0.45, 0.42, 0.40))
# the bowl: inner radius 0.95 m at the rim, floor 0.12 m above the ground, rim at 0.62 m (a closed lathe: the
# collider and the visible prop are one mesh)
prof = [(0.0, 0.0), (1.12, 0.0), (1.12, 0.60), (1.10, 0.64), (1.02, 0.66), (0.97, 0.64), (0.95, 0.58),
        (0.90, 0.30), (0.78, 0.17), (0.50, 0.125), (0.0, 0.12)]
basin = S.lathe(sc, 'basin', prof, segments=128, mat=stone)
RIM_Z, FLOOR_Z, INNER_R = 0.62, 0.12, 0.92
S.box(sc, 'ground', (30, 30, 0.2), (0, 0, -0.1), ground_m)
# three spout heads on posts round the rim (props; the water leaves their mouths)
bronze = S.pbr('spout_bronze', S.texset('Metal042A_1k'), 'Metal042A', scale=6.0, tint=(0.75, 0.52, 0.34))
spouts = []
for k in range(3):
    a = math.radians(90 + 120 * k)
    px, py = 1.05 * math.cos(a), 1.05 * math.sin(a)
    S.box(sc, f'post{k}', (0.12, 0.12, 1.0), (1.22 * math.cos(a), 1.22 * math.sin(a), 0.5), stone)
    S.box(sc, f'spout{k}', (0.26, 0.09, 0.09), (1.08 * math.cos(a), 1.08 * math.sin(a), 0.95), bronze).rotation_euler \
        = (0, 0, a)
    spouts.append((0.92 * math.cos(a), 0.92 * math.sin(a), 0.95))
# a low red sun and a dusk sky (the chorus' red giant at azimuth 182, elevation 10)
S.world_backdrop(sc, None, None, 0, sky_grad=('#1b2238', '#c8643a', 0.35))
S.sun(sc, 'sun', azimuth_deg=182 - 90, elevation_deg=10, strength=2.6, col=(1.0, 0.55, 0.32), angle_deg=1.5)
S.sun(sc, 'fill', azimuth_deg=-60, elevation_deg=40, strength=0.25, col=(0.55, 0.65, 1.0))
S.camera_look(sc, (-2.6, -2.9, 1.9), (0.0, 0.0, 0.35), lens=32)

# ---- the wader: hips and two feet, walking across the pool once it holds water -------------------------------
spheres = []
mat_body = S.principled('wader', 0x6b5b4c, rough=0.6)
import bmesh  # noqa: E402


def ball(name, r):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat_body)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


T_IN = 4.0                                 # he steps in at 4 s and crosses by 8 s
parts = [('hips', 0.16, 0.0, 0.62), ('foot_l', 0.09, 0.11, 0.26), ('foot_r', 0.09, -0.11, 0.26)]   # feet clear the floor
for nm, r, side, z in parts:
    ob = ball(nm, r)
    keys = []
    for f in range(1, END + 1):
        t = (f - 1) / FPS
        u = min(max((t - T_IN) / 4.0, 0.0), 1.0)
        x = -0.7 + 1.4 * u                                        # across the bowl, inside its wall
        stride = 0.0 if nm == 'hips' else math.sin(t * 5.0 + (0 if side > 0 else math.pi)) * 0.12 * (0 < u < 1)
        keys.append((f, (x + stride, side - 0.15, z + (0.06 * abs(stride) if nm != 'hips' else 0.0))))
    S.key_path(ob, keys)
    spheres.append((ob, r))

# ---- the water: the chorus options at this scale -----------------------------------------------------------
N = int(A.get('res', 112))
DX = 2.4 / N
NZ = int(round(1.2 / DX))
water = create_water_sim(
    scene=sc, name='spouts' + TAG, cache_dir=os.path.join(S.OUT, 'spouts_cache' + TAG),
    grid_size=(N, N, NZ), world_size=(2.4, 2.4, NZ * DX), domain_center=(0.0, 0.0, NZ * DX / 2),
    walls=False, collider_meshes=[basin], initial_level=-0.5, volume_control=True, measure_volume=True,
    max_spheres=8, max_emitters=len(spouts), vel_smooth=0.0, max_speed=15.0, gravity=9.81,
    smooth_surface=True, foam_shore=0.0, shading='lit',
    deep_color='#04262a', shallow_color='#2ba393', sky_color='#e8a077', absorption=2.45, surface_opacity=0.62,
    emissive_color='#1ee0c2', emissive_strength=0.5, emissive_falloff=3.8,
    foam_color='#cdf3ea', foam_strength=0.8, foam_width=0.085,
    sparkle_strength=0.65, sparkle_scale=38.0, sparkle_speed=1.0,
    key_light_dir=(-0.97, 0.17, -0.03))
ok = True
occ = water.solver.solid_np
nz, ny, nx = occ.shape


def cell_of(x, y, z):
    p3 = np.array([x, z, -y]) - water.center3
    u = p3 / np.array(water.params['world3']) + 0.5
    return (int(u[2] * nz), int(u[1] * ny), int(u[0] * nx))


ok &= S.check('basin wall voxelised solid', occ[cell_of(1.03, 0.0, 0.40)] > 0.5)
ok &= S.check('basin hollow is open', occ[cell_of(0.0, 0.0, 0.40)] < 0.5)
POUR_END = 6.5
poured = dict(v=0.0)
log = []
W3 = np.array(water.params['world3'])
px = (np.arange(nx) + 0.5) / nx * W3[0] - W3[0] / 2 + water.center3[0]
by = -((np.arange(nz) + 0.5) / nz * W3[2] - W3[2] / 2 + water.center3[2])
BOWL = np.zeros(occ.shape, dtype=bool)
_, j0, _ = cell_of(0, 0, FLOOR_Z - 0.03)
_, j1, _ = cell_of(0, 0, RIM_Z + 0.02)
BOWL[:, j0:j1 + 1, :] = (np.hypot(px[None, :], by[:, None]) < INNER_R + 0.03)[:, None, :]
BOWL &= occ < 0.5


def controls(frame, t, w):
    on = t < POUR_END
    w.set_emitters([dict(x=x, y=y, z=z, r=0.055, vx=-x * 0.8, vy=-y * 0.8, vz=-5.0 * 0.5) if on else None
                    for x, y, z in spouts])
    poured['v'] += w.emitter_flux() / FPS
    if frame % 24 == 0:
        frac = np.clip(0.5 - w.solver.phi() / (DX * 3.0), 0, 1)
        log.append((t, float((frac * BOWL).sum() * DX ** 3), poured['v']))


t0 = time.time()
water.bake(1, END, mesh_frames=FRAMES, controls=controls, track_spheres=spheres, fill_target='poured',
           fill_rate=1.5, fill_kp=3.0)
print(f'[spouts] bake {time.time() - t0:.1f} s, poured {poured["v"]:.4f} m3', flush=True)
for t, vb, pv in log:
    print(f'[spouts] t {t:5.2f}  in bowl {vb:.4f}  poured {pv:.4f}', flush=True)
mid = [vb for t, vb, pv in log if 2.5 <= t < 3.5]
fin = [(vb, pv) for t, vb, pv in log if t >= POUR_END + 0.5]
ok &= S.check('the basin fills while the spouts run', bool(mid and fin and fin[-1][0] > 1.5 * mid[0] > 0.0),
              f'{mid[0]:.4f} -> {fin[-1][0]:.4f} m3' if mid and fin else '')
ok &= S.check('the bowl holds most of what was poured (> 85 %)', bool(fin) and fin[-1][0] > 0.85 * fin[-1][1],
              f'{fin[-1][0]:.4f} of {fin[-1][1]:.4f} m3' if fin else '')
bad = []
for f in FRAMES:
    sc.frame_set(f)
    ev = water.surface_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    for ob, r in spheres:
        c = np.array(ob.matrix_world.translation)
        n_in = int((np.linalg.norm(co - c, axis=1) < r - DX).sum())
        if n_in:
            bad.append(f'f{f} {ob.name}: {n_in}')
    if not ((np.abs(co[:, :2]) <= 1.2 + 1e-3).all() and (co[:, 2] >= -1e-3).all()):
        bad.append(f'f{f}: outside the domain')
ok &= S.check('no water inside the wader; the surface stays in the domain', not bad, '; '.join(bad[:4]))
shots = []
for f in (FRAMES if A.get('render', '1') == '1' else []):
    p = os.path.join(S.OUT, f'w3d_spouts{TAG}_f{f:04d}.png')
    ok &= S.render(sc, f, p)
    shots.append(p)
S.contact_sheet(shots, os.path.join(S.OUT, f'w3d_spouts{TAG}_sheet.png'), cols=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'w3d_spouts{TAG}.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
