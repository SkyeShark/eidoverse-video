"""The engine's spheretest scene in Blender: a dynamic sphere collider driven per frame (the path a VRM's bones use).
A ball hangs over the dam-break tank while the pool settles, then descends into it and sweeps through it; the water
must part around it, not pass through it.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_spheretest.py [-- samples=32 shading=engine]

The engine's scene (E:/eidoverse-video-desktop-work-folder/spheretest/scene.js), option for option: gridSize
[64, 48, 64] over [2, 1.5, 2] m, domainCenter [0, 0.75, 0], maxSpheres 4, the 0.62-deep dam-break column, the ball
r 0.26 at y 1.30 for 3 s, then down at 0.42 m/s to 0.30, sweeping x = 0.55 sin(1.5 (t - 5)) from 5 s; 9 s at 30 fps.
The ball is an animated object fed to the solver by bake(track_spheres=...).

Checks (PASS/FAIL): no water inside the ball (no surface vertex deeper than a cell inside the sphere at any rendered
frame); the free surface meets the submerged ball (a waterline ring of vertices on it); the water closes in where the
sweeping ball was a second before; the volume stays within 3 % of its target. Renders out/w3d_sphere<tag>_f####.png
and a sheet (the engine's _sheet.png frames). render=0 runs the checks only.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, ENGINE_SOLVER  # noqa: E402

A = S.args()
FPS = 30
END = int(A.get('end', 270))
TAG = A.get('tag', '')
SHADING = A.get('shading', 'lit')
FRAMES = [int(x) for x in A.get('frames', '60,105,135,165,210,255').split(',')]
sc = S.fresh_scene(res=(960, 540), fps=FPS, end=END, samples=int(A.get('samples', 32)))
sc.view_settings.exposure = float(A.get('exposure', 0.2))

# ---- the stage: the engine's tank (dark floor, 13 % glass walls), camera and lights ----------------------------
W, H, D = 2.0, 1.5, 2.0
wallT, mW = 0.06, (1.5 / 64) * 2.0
S.box(sc, 'ground', (30, 30, 0.02), (0, 0, -0.01), S.principled('floor', 0x232830, rough=0.85))
glass = S.principled('tank_glass', 0x9fb4c4, rough=0.08, alpha=0.13, blended=True)
ix, iz = W / 2 - mW, D / 2 - mW
S.box(sc, 'wall_nx', (wallT, D + 2 * wallT, H), (-(ix + wallT / 2), 0, H / 2), glass)
S.box(sc, 'wall_px', (wallT, D + 2 * wallT, H), ((ix + wallT / 2), 0, H / 2), glass)
S.box(sc, 'wall_nz', (W + 2 * wallT, wallT, H), (0, (iz + wallT / 2), H / 2), glass)
S.box(sc, 'wall_pz', (W + 2 * wallT, wallT, H), (0, -(iz + wallT / 2), H / 2), glass)
S.camera_three(sc, (2.35, 2.95, 2.55), (0, 0.22, 0), 46)
S.sun_three(sc, 'key', (2.2, 4.5, 2.6), 0xffffff, 1.6 * 2.2)
S.world_backdrop(sc, camera_col=0x10141a, ambient_col=0x8899aa, ambient_strength=0.55, glossy=('#9db8c9', 1.0),
                 match_display=True)

# ---- the ball: the engine's per-frame path, keyed (LINEAR) so the .blend plays it ------------------------------
R = 0.26
import bmesh  # noqa: E402
me = bpy.data.meshes.new('ball')
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=R)
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
me.materials.append(S.principled('ball_m', 0xff8a4c, rough=0.35))
ball = bpy.data.objects.new('ball', me)
sc.collection.objects.link(ball)


def ball_at(t):
    """renderFrame's path in three axes (x, y up, z) -> Blender (x, -z, y)."""
    y = 1.30 if t < 3 else max(0.30, 1.30 - (t - 3) * 0.42)
    x = 0.0 if t < 5 else math.sin((t - 5) * 1.5) * 0.55
    return (x, 0.0, y)


S.key_path(ball, [(f, ball_at((f - 1) / FPS)) for f in range(1, END + 1)])

# ---- the water: the scene's options ------------------------------------------------------------------------
kw = ENGINE_SOLVER if A.get('solver') == 'engine' else {}
water = create_water_sim(scene=sc, name='sphere' + TAG, cache_dir=os.path.join(S.OUT, 'sphere_cache' + TAG),
                         gridSize=[64, 48, 64], worldSize=[W, H, D], domainCenter=[0, H / 2, 0], maxSpheres=4,
                         measureVolume=True, columnDepth=0.62, smooth_surface=True, shading=SHADING,
                         thickness_mode='view' if SHADING == 'engine' else 'normal', **kw)
ok = True
vols = []
behind = {}


def phi_at(w, p):
    """phi (m) at a Blender point, nearest cell."""
    ph = w.solver.phi()
    nz, ny, nx = ph.shape
    u = (np.array([p[0], p[2], -p[1]]) - w.center3) / np.array(w.params['world3']) + 0.5
    return float(ph[min(int(u[2] * nz), nz - 1), min(int(u[1] * ny), ny - 1), min(int(u[0] * nx), nx - 1)])


def controls(frame, t, w):
    if frame % 15 == 0:
        vols.append((t, w.measure_volume(), w.uniforms.vol_target))
    if frame == 211:
        # the state after frame 210: where the ball's centre was a second earlier, water has closed in again
        behind['old'] = phi_at(w, ball_at(180 / FPS))
        behind['now'] = ball_at(209 / FPS)


t0 = time.time()
water.bake(1, END, mesh_frames=FRAMES, track_spheres=[(ball, R)], controls=controls)
print(f'[sphere] bake {time.time() - t0:.1f} s', flush=True)


def mesh_points(f):
    sc.frame_set(f)
    ev = water.surface_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    co = np.zeros(len(m.vertices) * 3)
    m.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


DX = water.solver.DX
inside = []
for f in FRAMES:
    co = mesh_points(f)
    c = np.array(ball_at((f - 1) / FPS))
    d = np.linalg.norm(co - c, axis=1)
    inside.append((f, int((d < R - DX).sum())))
ok &= S.check('no water inside the ball', all(n == 0 for f, n in inside),
              ', '.join(f'f{f}: {n}' for f, n in inside))
# the submerged ball: the free surface meets it (vertices within 1.5 cells of the sphere, the waterline ring)
f_sub = 165
co = mesh_points(f_sub)
c = np.array(ball_at((f_sub - 1) / FPS))
ring = int((np.abs(np.linalg.norm(co - c, axis=1) - R) < 1.5 * DX).sum())
ok &= S.check('the water meets the submerged ball (a waterline ring on it)', ring > 50, f'{ring} vertices at f{f_sub}')
ok &= S.check('the water closes in behind the sweeping ball', behind.get('old', 1.0) < 0.0,
              f'phi {behind.get("old", float("nan")):.3f} m where the centre was a second before')
late = [(t, v, tg) for t, v, tg in vols if t > 3.0]
ok &= S.check('volume held within 3 % of its target while the ball moves', bool(late) and
              all(abs(v - tg) / tg < 0.03 for t, v, tg in late), f'{min(v / tg for t, v, tg in late):.3f} .. '
              f'{max(v / tg for t, v, tg in late):.3f} of target' if late else '')
shots = []
for f in (FRAMES if A.get('render', '1') == '1' else []):
    p = os.path.join(S.OUT, f'w3d_sphere{TAG}_f{f:04d}.png')
    ok &= S.render(sc, f, p)
    shots.append(p)
S.contact_sheet(shots, os.path.join(S.OUT, f'w3d_sphere{TAG}_sheet.png'), cols=3)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'w3d_sphere{TAG}.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
