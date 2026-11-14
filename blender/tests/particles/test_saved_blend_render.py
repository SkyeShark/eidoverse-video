"""The robot film's saved .blend (test_robot_morph.py's out/<out>/robot_morph.blend) opened in a FRESH Blender process
and rendered: no Python state of the run that built it, only its keys, drivers and graphs. The test that built it
checks the reopened file's point positions in its own process; this renders it, from the same wide camera (the
.blend is saved without cameras), and compares each still with the one the building run rendered.

    out/<out>/saved_blend_wide_f<NNN>.png   stills from the reopened file

Checks: each still matches the building run's still of that frame (mean |diff| under 1 in 8-bit).

    bash run_blender.sh blender/tests/particles/test_saved_blend_render.py [-- out=verify] [frames=58,72,150,214]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

FRAMES = [int(f) for f in S.arg('frames', '58,72,150,214').split(',')]
F_DISSOLVE = 56                         # test_robot_morph.py's: the cloud is exactly the body there


def main():
    blend = os.path.join(S.OUT, 'robot_morph.blend')
    if not os.path.isfile(blend):
        S.check(f'{blend} exists (run test_robot_morph.py with the same out= first)', False)
        sys.exit(1)
    out_dir = S.OUT
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    ob = bpy.data.objects['robot_cloud']
    mod = ob.modifiers['particle_morph']
    ident = mod.node_group.interface.items_tree['Points Only'].identifier
    # the body's centroid at the dissolve (the cloud is the body there), as the building run framed its wide camera
    sc.frame_set(F_DISSOLVE)
    getattr(mod.properties.inputs, ident).value = True
    ob.update_tag()
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    getattr(mod.properties.inputs, ident).value = False
    ob.update_tag()
    bx = float(P.reshape(-1, 3)[:, 0].mean())
    S.camera('wide', (bx - 1.0, -8.2, 1.7), (bx - 0.9, 0.0, 1.0), 32.0, sc).data.dof.use_dof = False
    from PIL import Image
    for f in FRAMES:
        path = os.path.join(out_dir, f'saved_blend_wide_f{f:03d}.png')
        S.render_still(path, f, sc)
        ref = os.path.join(out_dir, f'robot_morph_wide_f{f:03d}.png')
        if os.path.isfile(path) and os.path.isfile(ref):
            a = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
            b = np.asarray(Image.open(ref).convert('RGB')).astype(np.float64)
            d = float(np.abs(a - b).mean()) if a.shape == b.shape else 999.0
            S.check(f'frame {f}: the reopened file renders what the building run rendered', d < 1.0,
                    f'mean |diff| {d:.3f} (8-bit)')
        else:
            S.check(f'frame {f}: rendered (no reference still to compare)', os.path.isfile(path))
    ok = S.summary('saved blend')
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
