"""NuclearExplosionFX.applyTo as volumes in the scene: the effect's life, its motion, its options, the registry hooks.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sdf_volumes/test_nuclear_explosion.py [-- quality=balanced w=480 h=270]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

1. Options: the engine's call shape ({scene, camera, opts} with camelCase keys) and snake_case; an unknown option
   raises; the screen-only options are accepted and said so; disable_for_perf_test builds hidden and bakes nothing.
2. The cloud: two volumes (the base surge and the mushroom) in the effect's world units round `origin`; the surge
   ring is NOT capped (at t = 12 s it holds density beyond the placed example's 6.6-unit cap, out to ~18 units).
3. Life: six stills through the 20 s loop (flash, rise, cap, billow, cooling, dispersal) in EEVEE beside the
   effect's own march: out/nuke_life.png (EEVEE top, march bottom). A town of boxes and a chrome ball stand round
   ground zero; the glow lamps light them.
4. Motion: six consecutive frames at 24 fps from t = 5 s (time_offset), baked with keyed lamps: out/nuke_motion.png.
5. Opacity: key_opacity fades the media (a keyed material socket) and the lamps' energy keys follow.
6. The post registry's hooks: native_build bakes over the scene range and native_undo takes it all back out.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402

from eidoblend.sdf import nuclear_explosion as NX  # noqa: E402

A = V.args()
W, H = int(A.get('w', 480)), int(A.get('h', 270))
QUALITY = A.get('quality', 'balanced')
CACHE = os.path.join(V.OUT, 'cache_nuke')
WORLD = 0.035
LIFE = (0.6, 2.5, 5.0, 8.5, 12.0, 17.0)


def town(sc):
    """Boxes (buildings) and a chrome ball round ground zero, for scale, occlusion and the glow on surfaces."""
    import random
    rng = random.Random(4)
    for k, (x, y, w, d, h) in enumerate([(-14, -16, 3, 3, 6), (-8, -20, 4, 3, 3.5), (9, -18, 3.5, 3.5, 5),
                                         (16, -12, 3, 4, 7), (-20, -6, 4, 4, 4), (3, -26, 5, 3, 2.5)]):
        me = bpy.data.meshes.new(f'bldg{k}')
        v = [(sx * w / 2, sy * d / 2, sz * h) for sx in (-1, 1) for sy in (-1, 1) for sz in (0, 1)]
        me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
        ob = bpy.data.objects.new(f'bldg{k}', me)
        sc.collection.objects.link(ob)
        ob.location = (x, y, 0)
        m = bpy.data.materials.new(f'bldg{k}_mat')
        m.use_nodes = True
        g = 0.35 + 0.15 * rng.random()
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (g, g * 0.97, g * 0.92, 1.0)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.85
        me.materials.append(m)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, location=(6.0, -12.0, 2.0), segments=48, ring_count=24)
    ball = bpy.context.active_object
    ball.name = 'chrome'
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new('chrome_mat')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.1
    ball.data.materials.append(m)


def stage():
    V.stage(W, H, 16, world=WORLD, sun=0.25, floor=True, floor_color=(0.30, 0.28, 0.25), floor_size=400.0,
            sun_rot=(70.0, 0.0, -40.0))
    sc = bpy.context.scene
    sc.render.fps = 24
    town(sc)
    cam = V.camera((0.0, -44.0, 5.5), (0.0, 0.0, 5.5), lens=32)
    cam.data.clip_end = 1000.0
    return sc, cam


# ---- 1. options -------------------------------------------------------------------------------------------------
sc, cam = stage()
try:
    NX.apply_to(sc, cam, {'scael': 1.0}, cache_dir=CACHE)
    V.check('an unknown option raises', False, 'no error')
except KeyError as e:
    V.check('an unknown option raises', 'scael' in str(e), str(e)[:100])
fx = NX.apply_to({'scene': sc, 'camera': cam, 'opts': {'timeOffset': 2.0, 'loopSeconds': 20.0, 'scale': 0.25,
                                                        'maxT': 80, 'surfSteps': 64, 'disableForPerfTest': True}},
                 cache_dir=CACHE, quality='fast')
V.check("the engine's call shape and camelCase options", fx.uniforms['time_offset'] == 2.0
        and fx.uniforms['loop_seconds'] == 20.0 and fx.o['surf_steps'] == 64, repr(fx.uniforms))
V.check('disable_for_perf_test: built hidden, nothing baked', all(o.hide_render for o in fx.objects)
        and not os.path.exists(os.path.join(CACHE, f'{fx.volumes[0].stem}.vdb')), '')
fx.remove()

# ---- 2. the cloud ------------------------------------------------------------------------------------------------
fx = NX.apply_to(sc, cam, {'origin': [0, 0, 0], 'scale': 1.0}, cache_dir=CACHE, quality='fast', lights=0)
V.check('two volumes: the surge and the mushroom', [v.part for v in fx.volumes] == ['surge', 'mushroom'],
        str([(v.part, v.grid_info['dims'], round(v.voxel, 3)) for v in fx.volumes]))
g = fx.volumes[0].sample_grids(12.0)
d = g['density']
v0 = fx.volumes[0]
xs = v0.lo[0] + (np.arange(d.shape[0]) + 0.5) * v0.voxel
ys = v0.lo[1] + (np.arange(d.shape[1]) + 0.5) * v0.voxel
R = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
col = d.max(axis=2)
r_max = float(R[col > 0.05].max()) if (col > 0.05).any() else 0.0
V.check('the surge ring is not capped (the 2 km ring)', r_max > 12.0,
        f'density out to r = {r_max:.1f} units at t = 12 s (the placed example caps it at 6.6 x size)')
fx.remove()

# ---- 3. life -----------------------------------------------------------------------------------------------------
sc, cam = stage()
empty = os.path.join(V.OUT, 'nuke_empty.png')
V.render(empty)
base = V.read_png(empty)
fx = NX.apply_to(sc, cam, {'origin': [0, 0, 0], 'scale': 1.0}, cache_dir=CACHE, quality=QUALITY)
eev, ref = [], []
for i, t in enumerate(LIFE):
    fx.update(t, log=None)
    p = os.path.join(V.OUT, f'nuke_life{i}.png')
    V.check(f'life still t={t} rendered', V.render(p), p)
    V.label(p, f'nuclear_explosion EEVEE t={t:g}s')
    img = V.read_png(p)
    ch = float((np.abs(img - base).max(-1) > 0.03).mean())
    V.check(f'the cloud shows at t={t}', ch > 0.003, f'{ch * 100:.1f}% of the frame changed')
    r = V.reference_over(fx, cam, W, H, WORLD, samples=1, t=t)
    pr = V.save_linear_png(os.path.join(V.OUT, f'nuke_life{i}_ref.png'), r)
    V.label(pr, f'effect march t={t:g}s')
    eev.append(p)
    ref.append(pr)
V.sheet(eev + ref, os.path.join(V.OUT, 'nuke_life.png'), cols=3)
P = [rig.total_power(None) for rig in fx.lights]
V.check('the glow lamps carry light', sum(P) > 0, f'{sum(P):.3g} W at the last still ({len(fx.lights)} rigs)')
fx.remove()

# ---- 4. motion ---------------------------------------------------------------------------------------------------
sc, cam = stage()
sc.frame_start, sc.frame_end = 1, 6
fx = NX.apply_to(sc, cam, {'origin': [0, 0, 0], 'scale': 1.0, 'timeOffset': 5.0}, cache_dir=CACHE, quality=QUALITY,
                 bake='scene')
run = []
for f in range(1, 7):
    sc.frame_set(f)
    p = os.path.join(V.OUT, f'nuke_f{f:02d}.png')
    V.render(p)
    V.label(p, f'frame {f} (t = {5.0 + (f - 1) / 24:.3f} s)')
    run.append(p)
V.sheet(run, os.path.join(V.OUT, 'nuke_motion.png'), cols=3)
imgs = [V.read_png(p) for p in run]
moves = [float(np.abs(imgs[k + 1] - imgs[k]).mean()) for k in range(5)]
V.check('the cloud moves frame to frame', min(moves) > 2e-5, ', '.join(f'{m:.5f}' for m in moves))
vd = fx.volumes[1].object.data
V.check('the volumes play their sequences', vd.is_sequence and vd.frame_duration == 6, f'{vd.frame_duration}')
# ---- 5. opacity --------------------------------------------------------------------------------------------------
fx.key_opacity(1, 0.0)
fx.key_opacity(6, 1.0)
lo = fx.lights[0].lights[0]


def lamp_energy(f):
    """The lamp's energy as the render sees it at frame f (its driver: keyed power x the opacity socket)."""
    sc.frame_set(f)
    return lo.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.energy


e_1, e_3, e_6 = lamp_energy(1), lamp_energy(3), lamp_energy(6)
sock = fx.opacity_socket
sc.frame_set(3)
V.check('key_opacity fades the media and the lamps', abs(e_1) < 1e-6 and e_6 > 0 and 0.0 < e_3 < e_6
        and 0.0 < sock.default_value < 1.0,
        f'lamp energy {e_1:.3g} at frame 1, {e_3:.3g} at frame 3, {e_6:.3g} at frame 6; opacity '
        f'{sock.default_value:.2f} at frame 3')
# the socket keyed some other way (the post registry's FX.key): the lamps follow by their drivers
sock.default_value = 0.25
sock.keyframe_insert('default_value', frame=6)
e_6b = lamp_energy(6)
V.check('a key set on the opacity socket directly fades the lamps too', abs(e_6b - 0.25 * e_6) < 1e-3 * max(1.0, e_6),
        f'{e_6b:.4g} W at opacity 0.25 vs {e_6:.4g} W at 1.0')
fx.remove()

# ---- 6. registry hooks -------------------------------------------------------------------------------------------
sc.frame_start, sc.frame_end = 1, 2
n_before = len(bpy.data.objects)
ob, unif = NX.native_build(sc, {'scale': 0.5, 'quality': 'fast'})
made = len(bpy.data.objects) - n_before
V.check('native_build bakes the scene range', ob is not None and made >= 2 and 'opacity' in unif,
        f'{made} objects made, uniforms {list(unif)}')
NX.native_undo(sc)
V.check('native_undo takes it back out', len(bpy.data.objects) == n_before, f'{len(bpy.data.objects)} vs {n_before}')
V.summary()
