"""The fire preset's flame tongues, two ways side by side: as the engine's code draws them (rotate 0.35: each tongue
starts at a random angle over the whole circle, phase x 2 pi, then turns slowly) and with rotate=0 (every tongue
upright, as the preset's own comment says tongue textures must stay). Same emitter, sprite and seed.

    out/<out>/fire_tongues_engine_vs_upright_f048.png   left: the engine's rotate 0.35; right: rotate=0

Checks: with rotate=0 every quad's up axis is the camera's up (upright tongues); with the engine's rotate the quads
point every way.

    bash run_blender.sh blender/tests/particles/test_fire_tongue_rotation.py [-- out=verify] [no-render]
    (a GPU job: 4 GB VRAM, 6 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx import particles as PA  # noqa: E402

RENDER = 'no-render' not in S.argv()


def quad_ups(ob, frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return np.array([np.array(i.matrix_world.to_3x3().normalized())[:, 1] for i in dg.object_instances
                     if i.is_instance and i.parent is not None and i.parent.original == ob])


def main():
    sc = S.clean_scene(24, 1, 96)
    S.probe_render(sc, (960, 540), 16)
    S.world(sc, (0.004, 0.005, 0.009))
    eng = PA.make_particles('fire', origin=(-0.55, 0.0, 0.05), map='flame_05', seed=3, name='fire_engine_rotate')
    upr = PA.make_particles('fire', origin=(0.55, 0.0, 0.05), map='flame_05', seed=3, rotate=0,
                            name='fire_upright')
    cam = S.camera('cam', (0.0, -2.9, 0.55), (0.0, 0.0, 0.40), 35.0)
    q_up, q_eng = quad_ups(upr.object, 48), quad_ups(eng.object, 48)     # (these update the scene: the camera too)
    up = np.array(cam.matrix_world.to_3x3())[:, 1]
    u_up, u_eng = q_up @ up, q_eng @ up
    S.check('rotate=0: every tongue upright (the quad up = the camera up)', u_up.min() > 0.999, f'min {u_up.min():.4f}')
    S.check("the engine's rotate 0.35: tongues at every angle (some point down)", (u_eng < -0.5).mean() > 0.2,
            f'{100 * (u_eng < -0.5).mean():.0f} % point down')
    if RENDER:
        S.render_still(os.path.join(S.OUT, 'fire_tongues_engine_vs_upright_f048.png'), 48)
    ok = S.summary('fire tongues')
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
