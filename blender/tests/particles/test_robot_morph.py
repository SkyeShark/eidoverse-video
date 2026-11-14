"""The particle morph as infrastructure, on my robot body: I walk in (claude_robot, live pose), dissolve mid-stride into
particles in my own colours (sampled from my materials and textures, the cloud bound live to my skinned surface),
reform as a Poly Haven model in ITS colours (the alarm clock from the shared library), then as a neural net, then as
the word CLAUDE with the vortex reform. Every transition is keyed (key_sequence), the hand-off from body to cloud is a
keyed visibility switch, and the saved .blend renders any frame on its own (checked by reopening it).

    out/robot_morph_<cam>_f<NNN>.png   probe stills: the wide shot at the beats, a close-up of the body and of its cloud
    out/robot_morph.blend              the scene (keyed; the cloud's Geometry Nodes read the walking body every frame)

Checks (PASS/FAIL): the cloud on the live body at the dissolve frame; each formed shape exactly its target; the clock's
colours its texture's; the word's width; the reopened .blend evaluating the same cloud.

    bash run_blender.sh blender/tests/particles/test_robot_morph.py \
        [-- frames=30,52,...] [blend=normal|additive] [res=960x540] [samples=16] [no-render] [model=alarm_clock_01:2k]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters import Ground, load_clip, load_vrm, walk_path, key_expression  # noqa: E402
from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx import particle_targets as PT  # noqa: E402

N = int(S.arg('count', 60000))
BLEND = S.arg('blend', 'normal')
GAIN = 1.0 if BLEND == 'normal' else 0.9           # additive light adds up: a little less of it per particle
RES = tuple(int(x) for x in S.arg('res', '960x540').split('x'))
SAMPLES = int(S.arg('samples', 16))
MODEL = S.arg('model', 'alarm_clock_01:2k')
TAG = S.arg('tag', 'robot_morph' + ('' if BLEND == 'normal' else '_' + BLEND))
RENDER = 'no-render' not in S.argv()
# the beats (24 fps)
F_FADE, F_DISSOLVE, F_FORMED = 44, 56, 104
F_NET0, F_NET1, F_WORD0, F_WORD1, F_END = 128, 172, 192, 240, 264
FRAMES = [int(f) for f in S.arg('frames', '30,52,58,72,112,150,182,214,252').split(',')]
CENTER = (0.0, 0.0, 1.05)


def log(*a):
    print(f'[{TAG}]', *a, flush=True)


def cloud_points(m, frame):
    sc = bpy.context.scene
    sc.frame_set(frame)
    m.uniforms.points_only.value = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = m.object.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        P = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', P)
        C = np.empty(len(me.vertices) * 4, np.float32)
        me.attributes['p_color'].data.foreach_get('color', C)
    finally:
        ev.to_mesh_clear()
    m.uniforms.points_only.value = False
    return P.reshape(-1, 3), C.reshape(-1, 4)[:, :3]


def stage(sc):
    S.probe_render(sc, RES, SAMPLES)
    sc.eevee.use_fast_gi = True
    S.world(sc, (0.012, 0.013, 0.02), 1.0)
    S.sun('key', (-2.0, -3.0, 3.2), (1.0, 0.96, 0.9), 3.2)
    S.sun('rim', (2.5, 3.0, 1.5), (0.75, 0.85, 1.0), 2.0)
    fl = S.floor(40.0, (0.035, 0.036, 0.04), 0.35)
    return fl


def main():
    t0 = time.time()
    sc = S.clean_scene(24, 1, F_END)
    stage(sc)
    # me, walking in from the left (still walking when I dissolve)
    me = load_vrm('claude_robot_2k', name='claude', location=(-4.6, 0.0, 0.0), rotation=0.0)
    walk = load_clip(me, 'walk')
    key_expression(me, 'happy', [(1, 1.0)])
    rep = walk_path(me, walk, [(-4.6, 0.0), (0.6, 0.0)], Ground(fn=lambda x, y: 0.0 * x), f0=1, face={'happy': 1.0},
                    log=log)
    log('walk frames', rep['frames'])
    sc.frame_set(F_DISSOLVE)
    body = PT.from_object(me, N, live=True, seed=11)
    log('body target', body, 'colour mean', body.colors.mean(0).round(3))
    # the reform shapes, where I dissolve
    global CENTER
    bc = body.centroid(F_DISSOLVE)
    CENTER = (float(bc[0]), 0.0, 1.05)
    name, _, res = MODEL.partition(':')
    model = PT.target(f'polyhaven:{name}:{res or "1k"}', N, fit_height=1.5, at=CENTER, anchor='center', seed=12)
    log('model target', model, 'colour mean', model.colors.mean(0).round(3))
    net = PT.target('neural_net', N, width=3.2, height=2.0, at=CENTER).tinted(0x58d6ff)
    word = PT.target('text:CLAUDE', N, width=3.6, at=CENTER).tinted(0xff9466)
    m = PM.make_particle_morph(count=N, targets=[body, model, net, word], blending=BLEND, size=0.022,
                               curl={'scale': 1.5, 'strength': 0.55}, gain=GAIN,
                               opacity=1.0, center=CENTER, name='robot_cloud', seed=5)
    # the keyed film: fade the cloud in over the walking body, swap at the dissolve, then the chain
    m.key_hold(0, 1)
    m.key_fade(F_FADE, F_DISSOLVE, 0.0, 1.0 if BLEND == 'normal' else 0.85)
    m.key('stagger', F_DISSOLVE, 0.35, ease='constant')          # the dissolve runs head first
    m.uniforms.stagger_axis.value = (0.0, 0.0, -1.0)
    lo = min(float(t.current_points(F_DISSOLVE)[:, 2].min()) for t in (body,))
    hi = max(float(t.current_points(F_DISSOLVE)[:, 2].max()) for t in (body,))
    m.uniforms.stagger_lo.value, m.uniforms.stagger_hi.value = -hi, -lo
    m.key_sequence([(1, F_DISSOLVE, F_FORMED), (2, F_NET0, F_NET1, {'ease': 'in_out_sine'}),
                    (3, F_WORD0, F_WORD1, {'vortex': 6.0, 'turb': 0.55, 'turb_auto': True})])
    m.key('stagger', F_FORMED, 0.0, ease='constant')
    PM.key_visibility(me, F_DISSOLVE, False)
    PM.key_visibility(me, 1, True)

    # ---- checks on the keyed scene
    P, C = cloud_points(m, F_DISSOLVE)
    on_body = float(np.abs(P - body.live.points(F_DISSOLVE)).max())
    S.check('the dissolve frame: the cloud is my body (live surface, mid-stride)', on_body < 1e-3, f'{on_body:.2e} m')
    P_prev = body.live.points(F_DISSOLVE - 8)
    S.check('the live body moved before the dissolve (walking)', float(np.abs(P_prev - body.live.points(F_DISSOLVE))
                                                                       .max()) > 0.1)
    S.check('the cloud in my colours at the dissolve (times the gain)', np.abs(C - body.colors * GAIN).max() < 1e-4,
            str(C.mean(0).round(3)))
    for f, t, nm in ((F_FORMED + 4, model, 'the Poly Haven model'), (F_NET1 + 4, net, 'the neural net'),
                     (F_WORD1 + 6, word, 'the word CLAUDE')):
        P, C = cloud_points(m, f)
        err = float(np.abs(P - t.points).max())
        S.check(f'frame {f}: formed as {nm} (exactly its target)', err < 1e-3, f'{err:.2e} m')
    P, C = cloud_points(m, F_FORMED + 4)
    S.check('the model in its own colours (its texture: a mint-green clock, cream dial, black and silver parts)',
            C[:, 1].mean() > C[:, 0].mean() and C[:, 1].mean() > C[:, 2].mean() and C.std(0).min() > 0.1,
            f'mean {C.mean(0).round(3)} sd {C.std(0).round(3)}')
    P, _ = cloud_points(m, F_WORD1 + 6)
    S.check('CLAUDE is 3.6 m wide (the canvas), reads left to right on X', 3.0 < np.ptp(P[:, 0]) < 3.7,
            f'{np.ptp(P[:, 0]):.2f} m')
    P_mid, _ = cloud_points(m, (F_WORD0 + F_WORD1) // 2)
    r_mid = np.hypot(P_mid[:, 0] - CENTER[0], P_mid[:, 1] - CENTER[1])
    S.check('the vortex reform: mid-way the cloud is wound around its axis', np.isfinite(P_mid).all() and
            r_mid.mean() > 0.2, f'mean radius {r_mid.mean():.2f} m')
    me_vis = [o.hide_render for o in me.meshes]
    sc.frame_set(F_DISSOLVE - 1)
    vis_before = not any(o.hide_render for o in me.meshes)
    sc.frame_set(F_DISSOLVE)
    S.check('the hand-off: my body shown before the dissolve, hidden from it on (keyed)', vis_before and
            all(o.hide_render for o in me.meshes))
    del me_vis

    body_c = body.centroid(F_DISSOLVE)
    blend = os.path.join(S.OUT, f'{TAG}.blend')
    sc.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0           # no .blend1 backup beside it
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    log('saved', blend, f'{time.time() - t0:.1f} s')
    ref = {f: cloud_points(m, f)[0] for f in (F_DISSOLVE + 10, F_WORD1 + 6)}
    # ---- reopen: the keyed .blend plays on its own (no Python state)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    ob = bpy.data.objects['robot_cloud']
    mod = ob.modifiers['particle_morph']
    tree = mod.node_group
    ident = tree.interface.items_tree['Points Only'].identifier
    for f, Pref in ref.items():
        sc.frame_set(f)
        getattr(mod.properties.inputs, ident).value = True
        ob.update_tag()
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        mm = ev.to_mesh()
        P = np.empty(len(mm.vertices) * 3)
        mm.vertices.foreach_get('co', P)
        ev.to_mesh_clear()
        getattr(mod.properties.inputs, ident).value = False
        err = float(np.abs(P.reshape(-1, 3) - Pref).max())
        S.check(f'the reopened .blend, frame {f}: the same cloud (keys + live body, no script)', err < 1e-4,
                f'{err:.2e} m')
    if RENDER:
        bx, by = float(body_c[0]), float(body_c[1])
        cams = {'wide': ((bx - 1.0, -8.2, 1.7), (bx - 0.9, 0.0, 1.0), 32.0),
                'close': ((bx + 0.45, by - 4.4, 1.2), (bx + 0.1, by, 0.92), 40.0)}     # the whole body, head to feet
        for cname, (loc, tgt, lens) in cams.items():
            cam = S.camera(cname, loc, tgt, lens, sc)
            cam.data.dof.use_dof = False
        for f in FRAMES:
            sc.camera = bpy.data.objects['wide']
            S.render_still(os.path.join(S.OUT, f'{TAG}_wide_f{f:03d}.png'), f, sc)
        sc.camera = bpy.data.objects['close']
        # the close shots: my body walking before the cloud fades in, the cloud over it one frame before the swap,
        # then the cloud alone one frame after (the same place on screen)
        for f in (F_FADE - 1, F_DISSOLVE - 1, F_DISSOLVE + 1):
            S.render_still(os.path.join(S.OUT, f'{TAG}_close_f{f:03d}.png'), f, sc)
    log(f'done in {time.time() - t0:.1f} s')
    ok = S.summary(TAG)
    sys.exit(0 if ok else 1)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    print('FAIL exception')
    sys.exit(1)
