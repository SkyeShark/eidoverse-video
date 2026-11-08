"""The engine's watertest, in Blender: a dam break in a glass tank (column against the -x wall collapses, surges
across the floor, runs up the far wall, settles), with eidoblend.fx.water3d.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_dam_break.py [-- frames=12,24,...]
    (more: smooth=0 for the trilinear contour, samples=64, tag=_x)

Checks (PASS/FAIL): the sensor's initial volume and the whole 6 s volume trace against the engine's own run of
fluid_water.js (engine_trace_dambreak.json, made by engine_trace.mjs), the settled pool's height and the baked
thickness on its top surface. Renders out/w3d_dambreak<tag>_f####.png at the engine scene's camera.
Reference look: E:/eidoverse-video-desktop-work-folder/watertest/water.mp4 (_sheet_final2.png).
"""

import json
import os
import time

import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, ENGINE_SOLVER  # noqa: E402

A = S.args()
FPS = 30
END = int(A.get('end', 180))
FRAMES = [int(x) for x in A.get('frames', '12,24,36,48,72,96,132,180').split(',')]
TAG = A.get('tag', '')
SMOOTH = A.get('smooth', '1') == '1'
SHADING = A.get('shading', 'lit')            # lit (the film material) | engine (the WebGPU unlit look)
sc = S.fresh_scene(res=tuple(int(v) for v in A.get('res', '960x540').split('x')), fps=FPS, end=END,
                   samples=int(A.get('samples', 16)))
sc.view_settings.exposure = float(A.get('exposure', 0.2))

# ---- the engine's watertest stage: dark floor, 13 % glass walls hugging the solver's interior -----------------
W, H, D = 2.0, 1.5, 2.0
wallT = 0.06
mW = (1.5 / 64) * W
floor = S.principled('floor', 0x232830, rough=0.85)
glass = S.principled('tank_glass', 0x9fb4c4, rough=0.08, alpha=0.13, blended=True)
S.box(sc, 'ground', (30, 30, 0.02), (0, 0, -0.01), floor)
ix, iz = W / 2 - mW, D / 2 - mW
S.box(sc, 'wall_nx', (wallT, D + 2 * wallT, H), (-(ix + wallT / 2), 0, H / 2), glass)
S.box(sc, 'wall_px', (wallT, D + 2 * wallT, H), ((ix + wallT / 2), 0, H / 2), glass)
S.box(sc, 'wall_nz', (W + 2 * wallT, wallT, H), (0, (iz + wallT / 2), H / 2), glass)
S.box(sc, 'wall_pz', (W + 2 * wallT, wallT, H), (0, -(iz + wallT / 2), H / 2), glass)
S.camera_three(sc, (2.35, 2.95, 2.55), (0, 0.22, 0), 46)
S.sun_three(sc, 'key', (2.2, 4.5, 2.6), 0xffffff, 1.6 * 2.2)
# reflections see the engine's skyColor (its shader mixed it in by fresnel); the backdrop shows as its canvas did
S.world_backdrop(sc, camera_col=0x10141a, ambient_col=0x8899aa, ambient_strength=0.55, glossy=('#9db8c9', 1.0),
                 match_display=True)

# ---- the water: the watertest's options --------------------------------------------------------------------
# the engine's solver exactly (ENGINE_SOLVER), so the volume trace can be held to the engine's run; solver=edition runs
# this edition's defaults instead (redistancing and breadth-first extrapolation: the trace differs by up to 5 % through
# the collapse, a looser check)
GODUNOV = A.get('solver') == 'edition'
water = create_water_sim(scene=sc, name='dambreak' + TAG, cache_dir=os.path.join(S.OUT, 'dambreak_cache' + TAG),
                         grid_size=(64, 64, 48), world_size=(W, D, H), domain_center=(0, 0, H / 2),
                         columnDepth=0.62, measureVolume=True, smooth_surface=SMOOTH, shading=SHADING,
                         thickness_mode='view' if SHADING == 'engine' else 'normal',
                         **({} if GODUNOV else ENGINE_SOLVER))
ok = True
ref = json.load(open(os.path.join(S.HERE, 'engine_trace_dambreak.json')))['trace']
v0 = water.measure_volume()
ok &= S.check('initial volume = engine', abs(v0 - ref[0][1]) < 1e-4, f'{v0:.5f} vs {ref[0][1]:.5f} m3')
trace = [(0.0, v0)]




def controls(frame, t, w):
    # runs BEFORE the frame's step: at frame 16 the state is the engine's after 15 frames (sim t = 0.5 s)
    if frame > 1 and (frame - 1) % 15 == 0:
        trace.append((w.sim_time, w.measure_volume()))


t0 = time.time()
water.bake(1, END, mesh_frames=FRAMES, controls=controls)
trace.append((water.sim_time, water.measure_volume()))
# the engine's trace samples after frames 15, 30, ... (sim time 0.5, 1.0, ...); controls runs BEFORE the step, so
# the reading at frame f + 1's controls is the state after frame f: compare by sim time
tr = {round(t, 2): v for t, v in trace}
errs = []
for t, v in ref[1:]:
    mine = tr.get(round(t, 2))
    if mine is not None:
        errs.append(abs(mine - v) / v)
TOL = 0.06 if GODUNOV else 0.01
ok &= S.check(f'volume trace vs engine (max rel diff < {TOL * 100:.0f} %)', len(errs) >= 8 and max(errs) < TOL,
              f'{len(errs)} samples, max {max(errs) * 100:.2f} %' if errs else 'no samples')

# ---- the settled pool: height and thickness on the top surface ---------------------------------------------
last = max(f for f in FRAMES if f <= END)
sc.frame_set(last)
ev = water.surface_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
me = ev.to_mesh()
n = len(me.vertices)
co = np.zeros(n * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
th = np.zeros(n)
me.attributes['thick'].data.foreach_get('value', th)
inner = (np.abs(co[:, 0]) < 0.7) & (np.abs(co[:, 1]) < 0.7)
top = inner & (co[:, 2] > np.percentile(co[inner, 2], 60))
vol_end = water.measure_volume()
interior = (W - 2 * mW) * (D - 2 * mW)
h_expect = mW * H / W * 1.0 + vol_end / interior          # floor margin (1.5/64 of the 1.5 m height) + depth
zt = float(np.median(co[top, 2]))
ok &= S.check('settled pool top height', abs(zt - h_expect) < 0.04, f'{zt:.3f} m vs {h_expect:.3f} m expected')
tt = float(np.median(th[top]))
if SHADING == 'engine':
    # view-ray thickness: the camera looks down at about 35 degrees, so the ray runs depth / sin(35) long
    cam = sc.camera.matrix_world.translation
    vd = np.array(cam) - co[top]
    sin_el = np.median(vd[:, 2] / np.linalg.norm(vd, axis=1))
    want = (h_expect - mW * H / W) / sin_el
    ok &= S.check('top-surface view-ray thickness ~ depth / sin(elevation)', abs(tt - want) < 0.1,
                  f'{tt:.3f} m vs {want:.3f} m')
else:
    ok &= S.check('top-surface thickness ~ pool depth', abs(tt - (h_expect - mW * H / W)) < 0.08,
                  f'{tt:.3f} m')
ev.to_mesh_clear()

shots = []
for f in FRAMES:
    if f <= END:
        p = os.path.join(S.OUT, f'w3d_dambreak{TAG}_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
S.contact_sheet(shots, os.path.join(S.OUT, f'w3d_dambreak{TAG}_sheet.png'), cols=4)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'w3d_dambreak{TAG}.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
