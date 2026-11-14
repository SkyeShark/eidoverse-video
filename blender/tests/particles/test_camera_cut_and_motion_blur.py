"""Two things a film asks of both particle systems that their own tests do not show: billboards that follow a
marker-bound camera cut, and motion blur.

  cut     a morph cloud (the word CUT spiralling into a galaxy) and a sparks emitter, both left to face the ACTIVE camera
          (camera=None), under two cameras bound to timeline markers: a front camera, then a side camera 90 degrees
          round from frame 20. After the cut every quad must face the side camera, or the cloud would show edge-on
          slivers. Stills: out/<out>/cut_front_f010.png, cut_side_f030.png.
  blur    an additive spinning galaxy cloud, a normal-blended one, the normal one realized (realize=True) and the
          sparks preset, rendered at one frame with EEVEE motion blur off, on with one time step and on with 8.
          EEVEE's one-step blur is a post-process on the velocity buffer: dithered (normal) surfaces write velocity,
          BLENDED (additive) ones do not, so additive particles blur only when the time steps accumulate. Stills:
          out/<out>/blur_{off,on_steps1,on_steps8}_f026.png.
  blurcontrol  the control: a cube moved by object keys blurs (the render setup works).

    bash run_blender.sh blender/tests/particles/test_camera_cut_and_motion_blur.py \
        [-- out=verify] [parts=cut,blur,blurcontrol] [no-render]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
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

from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx import particle_targets as PT  # noqa: E402
from eidoblend.fx import particles as PA  # noqa: E402

RENDER = 'no-render' not in S.argv()
PARTS = S.arg('parts', 'cut,blur,blurcontrol').split(',')
RES = (960, 540)


def log(*a):
    print('[cut+blur]', *a, flush=True)


def instances(ob, frame):
    """(centres (n, 3), rotations (n, 3, 3)) of the quads a graph instanced on `ob` at frame."""
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    C, R = [], []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob:
            M = inst.matrix_world
            C.append(tuple(M.translation))
            R.append(np.array(M.to_3x3().normalized()))
    return np.array(C), np.array(R)


def facing(R, cam):
    """The worst |cos| between a quad's normal (its local Z) and the camera's view axis."""
    view = np.array(cam.matrix_world.to_3x3())[:, 2]
    return float(np.abs(R[:, :, 2] @ view).min()) if len(R) else 0.0


def part_cut():
    sc = S.clean_scene(24, 1, 48)
    S.probe_render(sc, RES, 16)
    S.world(sc, (0.004, 0.005, 0.009))
    S.floor(30.0, (0.03, 0.03, 0.035), 0.6)
    N = 20000
    word = PT.target('text:CUT', N, width=2.6, at=(0, 0, 1.4))
    gal = PT.shapes.galaxy(N, radius=1.6, center=(0, 0, 1.4), normal=(0, -0.5, 1), colors=('#fff2d6', '#ff9ad0',
                                                                                            '#5a7dff'), seed=2)
    m = PM.make_particle_morph(count=N, targets=[word.tinted(0x66ccff), gal], size=0.03, center=(0, 0, 1.4),
                               name='cut_cloud')
    m.key_hold(0, 1)
    m.key_morph(0, 1, 6, 30, vortex=4.0)
    sp = PA.make_particles('sparks', origin=(1.9, 0.0, 0.4), map='spark_05', seed=3, name='cut_sparks')
    front = S.camera('front', (0.0, -7.0, 1.5), (0.0, 0.0, 1.3), 35.0)
    side = S.camera('side', (7.0, 0.0, 1.5), (0.0, 0.0, 1.3), 35.0)
    for f, cam in ((1, front), (20, side)):
        mk = sc.timeline_markers.new(f'cam_{cam.name}', frame=f)
        mk.camera = cam
    sc.camera = front
    sc.frame_set(10)
    ok_a = sc.camera == front
    _C, R = instances(m.object, 10)
    _Cs, Rs = instances(sp.object, 10)
    S.check('before the cut (frame 10): the front camera is active, every quad faces it (cloud and sparks)',
            ok_a and facing(R, front) > 0.999 and facing(Rs, front) > 0.999,
            f'worst cos {facing(R, front):.5f} / {facing(Rs, front):.5f}')
    sc.frame_set(30)
    ok_b = sc.camera == side
    _C, R = instances(m.object, 30)
    _Cs, Rs = instances(sp.object, 30)
    S.check('after the marker cut (frame 30): the side camera is active, every quad faces IT (no edge-on slivers)',
            ok_b and facing(R, side) > 0.999 and facing(Rs, side) > 0.999,
            f'active {sc.camera.name}; worst cos {facing(R, side):.5f} / {facing(Rs, side):.5f}; to the front camera '
            f'{facing(R, front):.3f}')
    if RENDER:
        S.render_still(os.path.join(S.OUT, 'cut_front_f010.png'), 10)
        S.render_still(os.path.join(S.OUT, 'cut_side_f030.png'), 30)


def region_change(a, b, x0, x1):
    """Mean |a - b| (8-bit) over columns x0..x1 where either image has content (the systems' light)."""
    A, B = a[:, x0:x1].astype(np.float64), b[:, x0:x1].astype(np.float64)
    mask = (A.max(2) > 30) | (B.max(2) > 30)
    return float(np.abs(A - B)[mask].mean()) if mask.any() else 0.0, int(mask.sum())


BLUR_SYSTEMS = (('the additive cloud (instances)', 'additive', False), ('the normal cloud (instances)', 'normal', False),
                ('the normal cloud (realized)', 'normal', True), ('the sparks (additive instances)', None, None))


def part_blur():
    """Four systems side by side, one frame rendered with motion blur off, on with one time step (EEVEE's velocity
    post-blur) and on with 8 time steps (accumulated): an additive spinning galaxy cloud (BLENDED: no velocity
    written), a normal one (DITHERED: velocity written), the normal one realized, and the sparks preset (additive)."""
    sc = S.clean_scene(24, 1, 48)
    S.probe_render(sc, RES, 16)
    S.world(sc, (0.004, 0.005, 0.009))
    N = 9000
    xs = (-3.3, -1.1, 1.1, 3.3)
    for i, ((nm, blending, realize), x) in enumerate(zip(BLUR_SYSTEMS, xs)):
        if blending is None:
            PA.make_particles('sparks', origin=(x, 0.0, 0.7), map='spark_05', seed=3, name='blur_sparks')
            continue
        g = PT.shapes.galaxy(N, radius=0.85, center=(x, 0, 1.3), normal=(0, -1, 0.35),
                             colors=('#fff2d6', '#ff9ad0', '#5a7dff'), seed=7)
        m = PM.make_particle_morph(count=N, targets=[g, g], size=0.03, center=(x, 0, 1.3), realize=realize,
                                   blending=blending, name=f'spin_{i}', seed=8 + i)
        # a fast turn: two revolutions a second about the cloud's vertical axis
        m.key_hold(0, 1)
        m.uniforms.spin.value = 0.0
        m.uniforms.spin.key(1)
        m.uniforms.spin.value = 8 * math.pi
        m.uniforms.spin.key(49)
    S.camera('cam', (0.0, -8.6, 1.3), (0.0, 0.0, 1.2), 35.0)
    sc.render.use_motion_blur = False
    if not RENDER:
        return
    from PIL import Image
    shots = {}
    for tag, on, steps in (('off', False, 1), ('on_steps1', True, 1), ('on_steps8', True, 8)):
        sc.render.use_motion_blur = on
        sc.render.motion_blur_shutter = 0.5
        sc.eevee.motion_blur_steps = steps
        p = os.path.join(S.OUT, f'blur_{tag}_f026.png')
        S.render_still(p, 26)
        shots[tag] = np.asarray(Image.open(p).convert('RGB')) if os.path.isfile(p) else None
    if any(v is None for v in shots.values()):
        S.check('motion blur stills rendered', False)
        return
    W = shots['off'].shape[1]
    q = W // 4
    res = {}
    for i, (nm, _b, _r) in enumerate(BLUR_SYSTEMS):
        for tag in ('on_steps1', 'on_steps8'):
            res[(i, tag)] = region_change(shots['off'], shots[tag], i * q, (i + 1) * q)[0]
        print(f'[blur] {nm}: mean |on - off| steps 1 {res[(i, "on_steps1")]:.1f}, steps 8 {res[(i, "on_steps8")]:.1f}',
              flush=True)
    S.check('motion blur, one step: the normal (dithered) clouds blur, instanced and realized (they write velocity)',
            res[(1, 'on_steps1')] > 6.0 and res[(2, 'on_steps1')] > 6.0,
            f'{res[(1, "on_steps1")]:.1f} / {res[(2, "on_steps1")]:.1f}')
    S.check('motion blur, one step: additive (BLENDED) particles write no velocity and do not blur',
            res[(0, 'on_steps1')] < 1.0 and res[(3, 'on_steps1')] < 1.0,
            f'{res[(0, "on_steps1")]:.1f} / {res[(3, "on_steps1")]:.1f}')
    S.check('motion blur, 8 time steps: every system blurs, additive ones too (the steps accumulate)',
            all(res[(i, 'on_steps8')] > 6.0 for i in range(3)) and res[(3, 'on_steps8')] > 3.0,
            ', '.join(f'{res[(i, "on_steps8")]:.1f}' for i in range(4)))


def part_blurcontrol():
    """The control for part_blur: a cube moved by plain object keys, the case EEVEE's motion blur is made for. If it
    does not blur either, the render setup is at fault, not the particles."""
    sc = S.clean_scene(24, 1, 48)
    S.probe_render(sc, RES, 16)
    S.world(sc, (0.004, 0.005, 0.009))
    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(-2.0, 0.0, 1.2))
    cube = bpy.context.object
    m = bpy.data.materials.new('white')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em, out = nt.nodes.new('ShaderNodeEmission'), nt.nodes.new('ShaderNodeOutputMaterial')
    em.inputs['Strength'].default_value = 2.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    cube.data.materials.append(m)
    cube.location.x = -3.0
    cube.keyframe_insert('location', index=0, frame=1)
    cube.location.x = 3.0
    cube.keyframe_insert('location', index=0, frame=49)
    S.camera('cam', (0.0, -8.6, 1.3), (0.0, 0.0, 1.2), 35.0)
    print('[blur control] render.use_motion_blur', sc.render.use_motion_blur, 'shutter',
          getattr(sc.render, 'motion_blur_shutter', None), 'eevee steps', getattr(sc.eevee, 'motion_blur_steps', None),
          'engine', sc.render.engine, flush=True)
    if RENDER:
        p_off = os.path.join(S.OUT, 'blur_control_off_f026.png')
        p_on = os.path.join(S.OUT, 'blur_control_on_f026.png')
        sc.render.use_motion_blur = False
        S.render_still(p_off, 26)
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = 0.5
        S.render_still(p_on, 26)
        from PIL import Image
        a, b = np.asarray(Image.open(p_off).convert('RGB')), np.asarray(Image.open(p_on).convert('RGB'))
        d, npx = region_change(a, b, 0, a.shape[1])
        lit_off, lit_on = int((a.max(2) > 30).sum()), int((b.max(2) > 30).sum())
        S.check('control: a keyed moving cube blurs with motion blur on (render setup works)', d > 6.0 and lit_on >
                lit_off, f'mean |on - off| {d:.1f} over {npx} px; lit px {lit_off} -> {lit_on}')


def main():
    t0 = time.time()
    for p in PARTS:
        log('part', p)
        globals()['part_' + p]()
    log(f'done in {time.time() - t0:.1f} s')
    ok = S.summary('cut+blur')
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
