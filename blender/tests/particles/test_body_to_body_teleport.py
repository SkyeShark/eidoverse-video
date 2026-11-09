"""A teleport between two moving bodies, both live targets: my robot body walks (live pose), dissolves head first in
its own colours, flies across with a vortex and lands (in the order it left) on Aletheia while she dances, so the
reform lands on the pose she has on each frame and the cloud keeps dancing with her until she is shown and it fades.

    out/<out>/teleport_f<NNN>.png   stills: walking, dissolving, in flight, formed on her, her body shown

Checks (PASS/FAIL): the cloud is the robot's live surface at the dissolve; once formed it is HER live surface at two
different frames (it moves with her dance); its colours are hers there.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/particles/test_body_to_body_teleport.py \
        [-- out=verify] [no-render]
"""

import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters import Ground, load_clip, load_vrm, play_vrma_default, walk_path  # noqa: E402
from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx import particle_targets as PT  # noqa: E402

RENDER = 'no-render' not in S.argv()
N = int(S.arg('count', 50000))
F_DISSOLVE, F_FORMED, F_SHOW, F_END = 36, 84, 100, 120


def log(*a):
    print('[teleport]', *a, flush=True)


def cloud(m, frame):
    sc = bpy.context.scene
    sc.frame_set(frame)
    m.uniforms.points_only.value = True
    bpy.context.view_layer.update()
    ev = m.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
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


def main():
    t0 = time.time()
    sc = S.clean_scene(24, 1, F_END)
    S.probe_render(sc, (960, 540), 16)
    S.world(sc, (0.012, 0.013, 0.02), 1.0)
    S.sun('key', (-2.0, -3.0, 3.2), (1.0, 0.96, 0.9), 3.2)
    S.sun('rim', (2.5, 3.0, 1.5), (0.75, 0.85, 1.0), 2.0)
    S.floor(40.0, (0.035, 0.036, 0.04), 0.5)
    robot = load_vrm('claude_robot_2k', name='robot', location=(-3.4, 0.0, 0.0), rotation=0.0)
    walk = load_clip(robot, 'walk')
    # 3.4 m at the clip's 1.56 m/s: still walking at the dissolve (frame 36), as in the robot film
    walk_path(robot, walk, [(-3.4, 0.0), (0.0, 0.0)], Ground(fn=lambda x, y: 0.0 * x), f0=1, log=log)
    her = load_vrm('aletheia', name='aletheia', location=(2.0, 0.0, 0.0), rotation=0.0)
    play_vrma_default(her, 'dance')
    sc.frame_set(F_DISSOLVE)
    a = PT.from_object(robot, N, live=True, seed=21)
    b = PT.from_object(her, N, live=True, seed=22)
    log('robot', a, 'her', b)
    m = PM.make_particle_morph(count=N, targets=[a, b], blending='normal', size=0.02, center=(0.4, 0.0, 1.0),
                               curl={'scale': 1.5, 'strength': 0.5}, name='teleport_cloud', seed=23)
    m.key_hold(0, 1)
    m.key_fade(F_DISSOLVE - 10, F_DISSOLVE, 0.0, 1.0)
    m.key_morph(0, 1, F_DISSOLVE, F_FORMED, ease='in_out_sine', turb=0.6, turb_auto=True, vortex=3.0)
    m.set_stagger(0.3, 'down')                 # head first off the robot (measured on the robot's points)
    m.key_fade(F_SHOW, F_SHOW + 12, 1.0, 0.0)
    PM.key_visibility(robot, 1, True)
    PM.key_visibility(robot, F_DISSOLVE, False)
    PM.key_visibility(her, 1, False)
    PM.key_visibility(her, F_SHOW, True)
    # ---- checks
    P, _C = cloud(m, F_DISSOLVE)
    err = float(np.abs(P - a.live.points(F_DISSOLVE)).max())
    S.check('the dissolve frame: the cloud is the robot\'s live surface', err < 1e-3, f'{err:.2e} m')
    for f in (F_FORMED + 2, F_SHOW - 2):
        P, C = cloud(m, f)
        err = float(np.abs(P - b.live.points(f)).max())
        S.check(f'frame {f}: formed on HER live surface (her pose at that frame)', err < 1e-3, f'{err:.2e} m')
    P1 = b.live.points(F_FORMED + 2)
    P2 = b.live.points(F_SHOW - 2)
    S.check('she danced between those frames (the cloud moved with her)', float(np.abs(P2 - P1).max()) > 0.05,
            f'{float(np.abs(P2 - P1).max()):.3f} m')
    S.check('the formed cloud wears her colours', np.abs(C - b.colors).max() < 1e-4, str(C.mean(0).round(3)))
    if RENDER:
        S.camera('cam', (0.0, -9.0, 1.5), (0.2, 0.0, 1.0), 32.0)
        for f in (24, 46, 62, F_FORMED + 4, F_SHOW + 6):
            S.render_still(os.path.join(S.OUT, f'teleport_f{f:03d}.png'), f)
    log(f'done in {time.time() - t0:.1f} s')
    ok = S.summary('teleport')
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
