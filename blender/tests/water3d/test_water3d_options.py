"""Breadth for eidoblend.fx.water3d: every option and API call the dam break and the pour do not exercise.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_water3d_options.py [-- samples=48]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Numeric (PASS/FAIL), each a small sim:
  - volume_control=False against the engine's own uncontrolled trace (engine_trace_dambreak_novc.json, 3 s)
  - mg_levels=1 (the Jacobi fallback, pressure_iters), reinit_every / reinit_iters, max_trace_cells, max_speed,
    vel_damping, vel_smooth, gravity, fixed_step, max_sub_steps: run, stay finite, and do what they say
  - the debug hooks: __no_clamp, __no_reinit, __no_pressure, __no_multigrid, __debug_phi / __debug_fields (grids
    written as OpenVDB), __bisect (ignored with a note)
  - the API: step() (the engine's 1/30 clamp), warmup(), measure_volume(), reset(), dispose(), uniforms (gravity
    live, look values write through and key), set_spheres/set_emitters slot handling, check_cubic's warning,
    camelCase options, unknown options refused
  - the render-side field ops: surface_bias lowers the surface by the bias, render_blur and smooth_surface change
    the mesh, mesh_adaptivity reduces it, engine_display matches the palette
Renders (out/w3d_opt_*.png): a wading pool (initial_level, max_spheres driven by an animated armature's bones and
an empty through track_spheres, the contact foam ring), the same pool from under the water (inside_domain), and an
emissive goo with sparkle in the engine shading.
"""

import json
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water3d import create_water_sim, configure_eevee, key_look  # noqa: E402
from eidoblend.fx.water3d.solver import check_cubic  # noqa: E402

A = S.args()
SAMPLES = int(A.get('samples', 48))
ok = True
t0 = time.time()
sc = S.fresh_scene(res=(960, 540), fps=30, end=90, samples=SAMPLES)
configure_eevee(sc, samples=SAMPLES)
logs = []


def quiet(*a):
    logs.append(' '.join(str(x) for x in a))


def tank(name, **kw):
    """The engine's watertest tank at 64 x 48 x 64 (Blender (64, 64, 48)) unless kw says otherwise."""
    base = dict(scene=sc, name=name, cache_dir=os.path.join(S.OUT, 'opt_cache'), grid_size=(64, 64, 48),
                world_size=(2.0, 2.0, 1.5), domain_center=(0, 0, 0.75), column_depth=0.62, measure_volume=True,
                log=quiet)
    base.update(kw)
    return create_water_sim(**base)


# ---- volume_control off: the engine's own uncontrolled trace ------------------------------------------------
ref = json.load(open(os.path.join(S.HERE, 'engine_trace_dambreak_novc.json')))['trace']
from eidoblend.fx.water3d import ENGINE_SOLVER as ENGINE, DROP_SOLVER       # noqa: E402  (the presets)
w = tank('novc', volume_control=False, **ENGINE)
mine = [(0.0, w.measure_volume())]
for f in range(1, 91):
    w.solver.step(1 / 30)
    if f % 15 == 0:
        mine.append((w.sim_time, w.measure_volume()))
errs = [abs(m[1] - r[1]) / r[1] for m, r in zip(mine, ref)]
ok &= S.check('volume_control=False matches the engine\'s uncontrolled trace (< 1.5 %)', max(errs) < 0.015,
              f'{len(errs)} samples, max {max(errs) * 100:.2f} %, end {mine[-1][1]:.4f} vs {ref[-1][1]:.4f} m3')
w.dispose()

# ---- solver options: run, finite, and doing what they say ----------------------------------------------------
def run(w, frames, dt=1 / 30):
    for _ in range(frames):
        w.solver.step(dt)
    ph = w.solver.phi()
    return ph, w.measure_volume()


w = tank('jacobi', mg_levels=1, pressure_iters=80)
ph, v = run(w, 30)
ok &= S.check('mg_levels=1 runs the Jacobi fallback', 'jacobi x80' in ' '.join(logs) and np.isfinite(ph).all(),
              f'volume {v:.4f} m3 after 1 s')
w.dispose()
w = tank('reinit', reinit_every=40, reinit_iters=8, reinit_scheme='central')
ph, v = run(w, 30)
ok &= S.check('reinit_scheme=central (the engine\'s kernel) runs at its cadence', bool(np.isfinite(ph).all()),
              f'volume {v:.4f} m3 after 1 s')
w.dispose()
# Godunov redistancing (DROP_SOLVER): after 3 s of the dam break, |grad phi| is ~1 in the band 2-4 cells from the
# surface (a distance field), where the engine's settings (the defaults) leave the clamped, advected profile
grads = {}
for nm, kw in (('godunov', DROP_SOLVER), ('engine', ENGINE)):
    w = tank('rd_' + nm, **kw)
    ph, v = run(w, 90)
    g = np.stack(np.gradient(ph.astype(np.float64), w.solver.DX), axis=0)
    gm = np.sqrt((g ** 2).sum(axis=0))
    band = (np.abs(ph) > 2 * w.solver.DX) & (np.abs(ph) < 4 * w.solver.DX)
    grads[nm] = float(np.median(np.abs(gm[band] - 1.0)))
    w.dispose()
ok &= S.check('godunov redistancing keeps phi a distance field (median ||grad phi| - 1| in the 2-4 cell band)',
              grads['godunov'] < 0.15 and grads['godunov'] < grads['engine'],
              f'godunov {grads["godunov"]:.3f}, engine settings {grads["engine"]:.3f}')
w = tank('switch')
run(w, 5)
w.set_solver(**DROP_SOLVER)
ph, v = run(w, 5)
switched = (w.params['reinit_every'], w.params['reinit_scheme'], w.params['extrapolation'])
w.set_solver(**ENGINE)
ph2, v2 = run(w, 5)
ok &= S.check('set_solver switches between the engine\'s solver and DROP_SOLVER mid-run',
              switched == (1, 'godunov', 'bfs') and w.params['extrapolation'] == 'phi'
              and bool(np.isfinite(ph).all() and np.isfinite(ph2).all()), f'{switched}, volume {v2:.4f} m3')
try:
    w.set_solver(extrapolation='nearest')
    ok &= S.check('set_solver refuses an unknown extrapolation', False)
except ValueError:
    ok &= S.check('set_solver refuses an unknown extrapolation', True)
w.dispose()
w = tank('fast', max_speed=1.0, max_trace_cells=1.0, vel_damping=2.0, vel_smooth=0.5)
run(w, 30)
vel = w.solver.velocity()
ok &= S.check('max_speed caps the projected speed', float(np.linalg.norm(vel, axis=-1).max()) <= 1.0 + 0.02,
              f'max |v| {np.linalg.norm(vel, axis=-1).max():.3f} m/s')
w.dispose()
w = tank('lowg', gravity=1.0, fixed_step=1 / 60, max_sub_steps=4)
n = w.step(1 / 30)
ok &= S.check('fixed_step 1/60: one 1/30 s frame runs two substeps', n == 2, f'{n} substeps')
n = w.step(0.5)
ok &= S.check('step() clamps delta to 1/30 s as the engine (max_sub_steps 4)', n == 2, f'{n} substeps for 0.5 s')
w.dispose()

# ---- debug hooks --------------------------------------------------------------------------------------------
for hook in ('__noClamp', '__noReinit', '__noPressure', '__noMultigrid'):
    w = tank('dbg' + hook.strip('_'), **{hook: True})
    ph, v = run(w, 15)
    ok &= S.check(f'{hook} runs', bool(np.isfinite(ph).all()), f'volume {v:.4f} m3 after 0.5 s')
    w.dispose()
w = tank('dbggrids', __debugPhi=True)
ok &= S.check('__debugPhi turns on write_grids', w.params['write_grids'] is True)
w.solver.step(1 / 30)
w.capture(1)
gp = os.path.join(S.OUT, 'opt_cache', 'dbggrids_grids_0001.vdb')
import openvdb as vdb  # noqa: E402
names = sorted(g.name for g in vdb.readAll(gp)[0]) if os.path.exists(gp) else []
ok &= S.check('the grids file holds phi, velocity, pressure, divergence',
              names == ['divergence', 'phi', 'pressure', 'velocity'], str(names))
w.dispose()
logs.clear()
w = tank('bisect', __bisect=1)
ok &= S.check('__bisect is noted and ignored', any('__bisect' in s for s in logs))
w.dispose()

# ---- the API --------------------------------------------------------------------------------------------------
w = tank('api', warmup_seconds=0.5)
v0 = w.measure_volume()
w.warmup()
ok &= S.check('warmup() runs warmup_seconds', abs(w.sim_time - 0.5) < 1 / 120 + 1e-6, f'sim time {w.sim_time:.4f} s')
run(w, 10)
w.uniforms.gravity = 0.0
ok &= S.check('uniforms write through to the solver (gravity)', w.solver.U['gravity'] == 0.0)
w.uniforms.shallow_color = '#ff0000'
node = w.material.node_tree.nodes['w3d.shallow_color']
ok &= S.check('look uniforms write through to the material', node.outputs[0].default_value[0] > 0.9)
key_look(w.material, 'absorption', 10, 4.0)
ad = w.material.node_tree.animation_data
ok &= S.check('key_look keys a look value', ad is not None and ad.action is not None)
w.reset()
ok &= S.check('reset() returns to the initial state', abs(w.measure_volume() - v0) < 1e-5 and w.sim_time == 0.0,
              f'{w.measure_volume():.5f} vs {v0:.5f} m3')
w.set_spheres([dict(x=0, y=0, z=0.3, r=0.2), None, dict(x=0, y=0, z=0.3, r=0)])
ok &= S.check('set_spheres without slots is a no-op', w.solver.NSPH == 0)
w.dispose()
ok &= S.check('dispose() frees the textures', w.solver.velA is None)
w = tank('target', volume_target=0.9)
ok &= S.check('an explicit volume_target is the controller\'s target', w.solver.U['vol_target'] == 0.9 and
              w.solver.target_valid, f'{w.solver.U["vol_target"]}')
w.dispose()
logs.clear()
check_cubic((64, 64, 64), (2.0, 1.5, 2.0), log=quiet)
ok &= S.check('non-cubic cells warn with the right grid', any('[64, 48, 64]' in s for s in logs), logs[-1][:90])
try:
    tank('bad', no_such_option=1)
    ok &= S.check('unknown options are refused', False)
except TypeError:
    ok &= S.check('unknown options are refused', True)

# ---- render-side field ops ----------------------------------------------------------------------------------
w = tank('field', initial_level=0.5)
run(w, 6)


def surface_top(w, **o):
    """The median height of the pool's TOP (the mesh also holds the body's floor-side face) and the face count."""
    for k, v in o.items():
        w.params[k] = v
    verts, tris, quads, attrs = w.surface_arrays()
    mid = (np.abs(verts[:, 0]) < 0.5) & (np.abs(verts[:, 1]) < 0.5) & (verts[:, 2] > 0.3)
    return float(np.median(verts[mid, 2])), len(tris) + len(quads)


z0, n0 = surface_top(w, surface_bias=0.0, render_blur=0, smooth_surface=False, mesh_adaptivity=0.0)
zb, _ = surface_top(w, surface_bias=0.02)
# the phi = -bias contour sits bias / |grad phi| lower; the engine's solver keeps no distance field near the surface
# (|grad phi| about 0.65 in this still pool), DROP_SOLVER's redistancing does (about 24 mm)
ok &= S.check('surface_bias lowers the drawn surface by about the bias (between 1 and 2 times it)',
              0.02 <= (z0 - zb) <= 0.04, f'{(z0 - zb) * 1000:.1f} mm for a 20 mm bias')
_, ns = surface_top(w, surface_bias=0.0, smooth_surface=True)
_, na = surface_top(w, smooth_surface=False, mesh_adaptivity=0.6)
w.dispose()
# render_blur low-passes phi: a flat pool is a linear field it leaves alone, so it is tried on the dam break's
# column, whose edges and corners it rounds (the meshed body loses that much volume)


def mesh_volume(v, t, q):
    tri = np.concatenate([t, q[:, [0, 1, 2]], q[:, [0, 2, 3]]]) if len(q) else t
    a, b, c = v[tri[:, 0]].astype(np.float64), v[tri[:, 1]].astype(np.float64), v[tri[:, 2]].astype(np.float64)
    return abs(float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum()) / 6.0)


w = tank('blur')
run(w, 1)
w.params.update(surface_bias=0.0, smooth_surface=False, mesh_adaptivity=0.0, render_blur=0)
vp, tp, qp, _ = w.surface_arrays()
w.params['render_blur'] = 2
vb, tb, qb, _ = w.surface_arrays()
w.dispose()
volp, volb = mesh_volume(vp, tp, qp), mesh_volume(vb, tb, qb)
ok &= S.check('render_blur / smooth_surface / mesh_adaptivity change the mesh',
              volb < volp - 1e-4 and ns > n0 and na < n0,
              f'column {volp * 1000:.1f} -> {volb * 1000:.1f} l with its edges rounded by blur 2; faces plain {n0}, '
              f'smooth {ns}, adaptive {na}')
from eidoblend.fx.water3d.material import display_matched  # noqa: E402
from eidoblend.fx._util import color  # noqa: E402
m = display_matched(sc, color('#2f8f9d'))
ok &= S.check('engine_display matches the palette under AgX (differs from the raw colour)',
              not np.allclose(m, color('#2f8f9d'), atol=1e-3), f'{tuple(round(x, 4) for x in m)}')
# the refraction thickness: the baked exit path linked as a slab (default), a sphere, or left to EEVEE ('none')
th = {}
for mode in ('slab', 'sphere', 'none'):
    w = tank('rt_' + mode, refraction_thickness=mode)
    out_n = [n for n in w.material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    th[mode] = (out_n.inputs['Thickness'].is_linked, w.material.thickness_mode)
    w.dispose()
ok &= S.check('refraction_thickness links the baked path as a slab / sphere, or leaves it to EEVEE',
              th['slab'] == (True, 'SLAB') and th['sphere'] == (True, 'SPHERE') and not th['none'][0], str(th))
picks = {}
for mode in ('lace', 'dither'):
    w = tank('fp_' + mode, foam_pick=mode, foam_scale=60.0)
    kinds = {n.bl_idname for n in w.material.node_tree.nodes}
    picks[mode] = ('ShaderNodeTexNoise' in kinds, 'ShaderNodeTexWhiteNoise' in kinds,
                   'w3d.foam_scale' in w.material.node_tree.nodes)
    w.dispose()
ok &= S.check('foam_pick: lace picks by a 3D noise at foam_scale, dither by a white-noise hash',
              picks['lace'] == (True, False, True) and picks['dither'][1] and not picks['dither'][0], str(picks))
w = tank('attrs', initial_level=0.5)
run(w, 3)
vt, _, _, at = w.surface_arrays()
top = (np.abs(vt[:, 2] - 0.5) < 0.03) & (np.abs(vt[:, 0]) < 0.8) & (np.abs(vt[:, 1]) < 0.8)
depth = 0.5 - 1.5 / 64 * 1.5                                    # to the analytic floor (its 1.5-cell margin)
ok &= S.check('exit/bed: a still pool\'s top looks down to its floor (bed) about its depth',
              bool(top.sum() > 100) and float(at['bed'][top].mean()) > 0.99 and
              abs(float(np.median(at['exit'][top])) - depth) < 0.04,
              f'{int(top.sum())} top vertices, bed {at["bed"][top].mean():.2f}, median exit '
              f'{np.median(at["exit"][top]):.3f} m vs {depth:.3f}')
w.dispose()

# ---- renders: the wading pool, from above and from under the water, and an emissive goo ----------------------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc.frame_start, sc.frame_end = 1, 60
tiles = S.pbr('pool_tiles', S.texset('Terrazzo005_1k'), 'Terrazzo005', scale=1.2)
# the pool basin the analytic walls stand for, as the visible stage: 4 x 4 m, floor at 0
S.box(sc, 'pool_floor', (4.4, 4.4, 0.2), (0, 0, -0.1), tiles)
for (sx, sy, x, y) in ((0.2, 4.4, 2.1, 0), (0.2, 4.4, -2.1, 0), (4.4, 0.2, 0, 2.1), (4.4, 0.2, 0, -2.1)):
    S.box(sc, 'pool_wall', (sx, sy, 0.9), (x, y, 0.45), tiles)
S.world_panorama(sc, os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky',
                                  'kloppenheim_puresky_ldr.png'), strength=1.0, rotate_deg=90)
S.sun(sc, 'sun', -40, 42, 3.0)
# a wader: an armature whose 'hips' bone walks across, and an empty for a hand trailing in the water
arm_d = bpy.data.armatures.new('wader')
arm = bpy.data.objects.new('wader', arm_d)
sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_d.edit_bones.new('hips')
eb.head, eb.tail = (0, 0, 0.0), (0, 0, 0.3)
bpy.ops.object.mode_set(mode='OBJECT')
for f, x in ((1, -1.3), (60, 1.3)):
    arm.location = (x, -0.2, 0.42)
    arm.keyframe_insert('location', frame=f)
hand = bpy.data.objects.new('hand', None)
sc.collection.objects.link(hand)
for f, x in ((1, -1.0), (60, 1.5)):
    hand.location = (x, 0.35, 0.55)
    hand.keyframe_insert('location', frame=f)
ball_m = S.principled('wader_m', 0xd0a080, rough=0.5)
import bmesh  # noqa: E402


def sphere_obj(name, r, parent=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    bm.to_mesh(me)
    bm.free()
    for p_ in me.polygons:
        p_.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    me.materials.append(ball_m)
    if parent is not None:
        ob.parent = parent
    return ob


sphere_obj('wader_body', 0.32, arm)
sphere_obj('hand_ball', 0.09, hand)
pool = create_water_sim(scene=sc, name='wade', cache_dir=os.path.join(S.OUT, 'opt_cache'),
                        grid_size=(96, 96, 24), world_size=(4.0, 4.0, 1.0), domain_center=(0, 0, 0.5),
                        initial_level=0.42, max_spheres=4, measure_volume=True, smooth_surface=True,
                        foam_strength=0.9, foam_shore=0.0, foam_width=0.06, shallow_color='#7fc7c8',
                        deep_color='#1d5866', absorption=1.8)
pool.bake(1, 60, mesh_frames=[30, 60], track_spheres=[(arm, 0.32, 'hips'), (hand, 0.09)])
ok &= S.check('track_spheres fills the sphere slots (bone and object)',
              int((pool.solver.spheres[:, 3] > 0).sum()) == 2, str(pool.solver.spheres[:2]))
S.camera_look(sc, (-2.6, -3.4, 2.4), (0.0, 0.0, 0.3), lens=30)
ok &= S.render(sc, 30, os.path.join(S.OUT, 'w3d_opt_wade_f0030.png'))
ok &= S.render(sc, 60, os.path.join(S.OUT, 'w3d_opt_wade_f0060.png'))
# under the water: inside_domain shows the surface's back faces and absorbs along the view inside the water
pool.set_inside_domain(True)
ok &= S.check('set_inside_domain draws back faces and links the under-water absorption',
              not pool.material.use_backface_culling and
              [n for n in pool.material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'][0].inputs['Volume'].is_linked)
S.camera_look(sc, (-1.6, -1.7, 0.22), (0.4, 0.4, 0.5), lens=24)
ok &= S.render(sc, 60, os.path.join(S.OUT, 'w3d_opt_underwater_f0060.png'))
# an emissive goo, the engine shading (the engine's 'luminous liquid' palette)
for ob in [o for o in sc.objects if o.name.startswith(('wade', 'wader', 'hand', 'pool_wall'))]:
    bpy.data.objects.remove(ob, do_unlink=True)
for (sx, sy, x, y) in ((0.2, 4.4, 2.1, 0), (0.2, 4.4, -2.1, 0), (4.4, 0.2, 0, 2.1), (4.4, 0.2, 0, -2.1)):
    S.box(sc, 'goo_wall', (sx, sy, 2.0), (x, y, 1.0), tiles)        # the surge runs up higher than the column
# the engine drew to an sRGB canvas with no tone mapping: an emissive above 1 clips to its hue there, where AgX
# bleaches it, so the engine-shading goo is built and viewed as that canvas (its palette display-matched to Standard)
sc.view_settings.view_transform = 'Standard'
goo = create_water_sim(scene=sc, name='goo', cache_dir=os.path.join(S.OUT, 'opt_cache'),
                       grid_size=(64, 64, 48), world_size=(4.0, 4.0, 3.0), domain_center=(0, 0, 1.5),
                       column_width=0.42, column_height=0.6, column_depth=0.5, shading='engine',
                       thickness_mode='view', emissive_strength=1.4, emissive_color='#2ffbe0', emissive_falloff=5.0,
                       sparkle_strength=0.6, deep_color='#0b3a2c', shallow_color='#3fe0a0', smooth_surface=True)
S.camera_look(sc, (-2.0, -2.8, 6.0), (0.3, 0.3, 0.2), lens=24)     # steep, over the 2 m walls into the tank
goo.bake(1, 45, mesh_frames=[45])
ok &= S.render(sc, 45, os.path.join(S.OUT, 'w3d_opt_goo_f0045.png'))
S.contact_sheet([os.path.join(S.OUT, p) for p in ('w3d_opt_wade_f0030.png', 'w3d_opt_wade_f0060.png',
                                                    'w3d_opt_underwater_f0060.png', 'w3d_opt_goo_f0045.png')],
                os.path.join(S.OUT, 'w3d_opt_sheet.png'), cols=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'w3d_options.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
