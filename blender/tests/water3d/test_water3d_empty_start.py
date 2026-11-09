"""A pour that opens on an empty tank: frames with no water at all are meshed (the chorus scene's empty start, baked
from its first frame, and any pour that begins a beat into the shot).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_empty_start.py [-- samples=32]

A small glass tank (0.6 x 0.6 x 0.5 m, the analytic walls, 1.25 cm cells) starts as all air; a spout switches on at
0.5 s and off at 3 s, enough for a pool several cells deep; every frame from 1 is meshed. Checks (PASS/FAIL): the bake
runs through the empty frames, an empty frame's PLY holds no faces and plays as an empty mesh, the first frames after
the spout opens hold water, the volume after the pour holds near what was poured. Renders out/w3d_empty_f####.png (an
empty frame, the stream, the settled pool) and out/w3d_empty_sheet.png.
"""

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
END = int(A.get('end', 108))
SAMPLES = int(A.get('samples', 32))
sc = S.fresh_scene(res=(960, 540), fps=FPS, end=END, samples=SAMPLES)
configure_eevee(sc, samples=SAMPLES)

floor = S.principled('floor', 0x5a5f66, rough=0.7)
glass = S.principled('tank_glass', 0x9fb4c4, rough=0.08, alpha=0.13, blended=True)
S.box(sc, 'ground', (20, 20, 0.02), (0, 0, -0.01), floor)
W, H = 0.6, 0.5
N = 48
DX = W / N
mW = 1.5 * DX                                       # the solver's analytic wall margin (1.5 cells)
ix = W / 2 - mW
for (sx, sy, x, y) in ((0.03, 2 * ix + 0.06, -(ix + 0.015), 0), (0.03, 2 * ix + 0.06, ix + 0.015, 0),
                       (2 * ix + 0.06, 0.03, 0, -(ix + 0.015)), (2 * ix + 0.06, 0.03, 0, ix + 0.015)):
    S.box(sc, 'wall', (sx, sy, H), (x, y, H / 2), glass)
S.world_backdrop(sc, camera_col=0x30343c, ambient_col=0x8899aa, ambient_strength=0.6, glossy=('#9db8c9', 1.0))
S.sun(sc, 'sun', azimuth_deg=-50, elevation_deg=45, strength=3.0)
S.camera_look(sc, (0.95, -1.05, 0.85), (0.0, 0.0, 0.12), lens=32)

water = create_water_sim(scene=sc, name='empty', cache_dir=os.path.join(S.OUT, 'empty_cache'),
                         grid_size=(N, N, int(round(H / DX))), world_size=(W, W, H), domain_center=(0, 0, H / 2),
                         initial_level=-1.0, max_emitters=1, measure_volume=True, smooth_surface=True,
                         foam_strength=0.3, foam_shore=0.0, log=lambda *a: None)
ok = True
ok &= S.check('the tank starts empty', water.measure_volume() < 1e-5, f'{water.measure_volume():.6f} m3')
SPOUT = dict(x=-0.2, y=0.05, z=0.4, r=0.05, vx=0.8, vy=0.0, vz=-0.3)
T_ON, T_OFF = 0.5, 3.0
poured = dict(v=0.0)


def controls(frame, t, w):
    w.set_emitters([SPOUT if T_ON <= t < T_OFF else None])
    poured['v'] += w.emitter_flux() / FPS


t0 = time.time()
err = None
try:
    water.bake(1, END, controls=controls, fill_target='poured', fill_rate=1.5, fill_kp=3.0)
except Exception as e:                                   # noqa: BLE001  (the check reports it)
    import traceback
    traceback.print_exc()
    err = e
ok &= S.check('the bake meshes every frame, the empty ones too', err is None, repr(err) if err else
              f'{END} frames in {time.time() - t0:.1f} s')


def ply_faces(f):
    p = os.path.join(water.cache_dir, f'empty_{f:04d}.ply')
    if not os.path.exists(p):
        return None
    with open(p, 'rb') as fh:
        head = fh.read(2048).split(b'end_header')[0].decode('ascii', 'replace')
    for line in head.splitlines():
        if line.startswith('element face'):
            return int(line.split()[-1])
    return None


def mesh_verts(f):
    sc.frame_set(f)
    ev = water.surface_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    n = len(me.vertices)
    ev.to_mesh_clear()
    return n


if err is None:
    f_on = int(T_ON * FPS) + 1
    empties = [ply_faces(f) for f in range(1, f_on)]
    ok &= S.check('the frames before the spout opens hold an empty surface', all(n == 0 for n in empties),
                  str(empties))
    ok &= S.check('an empty frame plays as an empty mesh', mesh_verts(3) == 0)
    later = [ply_faces(f) for f in range(f_on + 1, f_on + 6)]
    ok &= S.check('water appears once the spout opens', all(n and n > 0 for n in later), str(later))
    v = water.measure_volume()
    ok &= S.check('the tank holds what was poured (within 10 %)', abs(v - poured['v']) < 0.1 * poured['v'],
                  f'{v:.4f} of {poured["v"]:.4f} m3')
    shots = []
    for f in (4, 30, 60, END):
        p = os.path.join(S.OUT, f'w3d_empty_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
    S.contact_sheet(shots, os.path.join(S.OUT, 'w3d_empty_sheet.png'), cols=2)
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
