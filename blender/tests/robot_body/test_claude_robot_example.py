"""eidoverse/examples/claude_robot.js in full, in Blender (eidoblend.characters.robot.claude_robot_example): my body playing
the stock idle through every pass of the example's frame order (round one's port ran its face track only: this one adds
applyLegClearance and initHandDOF / applyHandDOF, and keys every stage: the hips' pitch and swing, the shoulders' pitch,
the wrists' roll and flex, the thumbs' rotors, the petals). 8 s at 30 fps, the example's studio and camera move.

Checks (PASS / FAIL lines):
  - every stage bone is keyed and its VRM constraint muted (a live constraint would overwrite the key)
  - the keyed pose evaluates to the rig's own FK: the hands' and the feet's bone heads, at five frames (mm)
  - the set-down: the lowest foot vertex of the EVALUATED (skinned) mesh sits on the floor at five frames (mm)
  - the legs' clearance acted: the ankles stand wider than the clip's own (mm), and no foot slides while planted
  - the hands: every finger pin and the thumb's stages inside their ranges (the joints file's), each frame
Stills: out/robot_example_t<S.SS>.png at the example's face moments (the example's own camera), plus close-ups of the
hands (robot_example_hands_t<S.SS>.png) and the feet (robot_example_feet_t<S.SS>.png); out/robot_example.json.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_claude_robot_example.py [--no-render]
"""

import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import robot_dof as dof  # noqa: E402
from eidoblend.characters.robot import claude_robot_example, stage_constraints  # noqa: E402
from eidoblend.characters.robot.example import camera_at  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True


def log(*a):
    print('[robot_example]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def foot_vertices(h):
    """the example's footVertices: every vertex whose strongest skin weight is a Foot or Toes bone"""
    want = {h.humanoid[s + b] for s in ('left', 'right') for b in ('Foot', 'Toes')}
    out = []
    for o in h.meshes:
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        vs = []
        for v in o.data.vertices:
            if v.groups:
                g = max(v.groups, key=lambda g: g.weight)
                if idx.get(g.group) in want:
                    vs.append(v.index)
        if vs:
            out.append((o, np.array(vs)))
    return out


def lowest_evaluated(sets):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = math.inf
    for o, vs in sets:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)[vs]
        M = np.array(ev.matrix_world)
        z = co @ M[2, :3] + M[2, 3]
        lo = min(lo, float(z.min()))
        ev.to_mesh_clear()
    return lo


try:
    sc = S.C.clean_scene(30)
    t = time.time()
    ex = claude_robot_example(sc)
    h, rig, rep = ex['h'], ex['rig'], ex['rep']
    R['build_s'] = round(time.time() - t, 1)
    R['action'] = rep['action']
    R['set_down_mm'] = rep['set_down_mm']
    R['stats_max_deg'] = rep['stats']
    frames = rep['_frames']
    byf = {fr['f']: fr for fr in frames}
    log('built', R['build_s'], 's', rep['action'], 'set-down', rep['set_down_mm'])

    # 1. the stages keyed, their constraints muted
    sc_ = stage_constraints(h)
    act = h.arm.animation_data.action
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, h.arm.animation_data.action_slot)
    keyed = {fc.data_path.split('"')[1] for fc in cb.fcurves if fc.data_path.startswith('pose.bones')}
    stage_ok = {bn: (bn in keyed, all(m for _t, m in cs)) for bn, cs in sc_.items()}
    petals_keyed = sum(1 for i in range(12) if f'petal_{i:02d}' in keyed)
    R['stage_bones'] = {bn: {'keyed': k, 'constraints_muted': m, 'constraints': [c for c, _m in sc_[bn]]}
                        for bn, (k, m) in stage_ok.items()}
    check('stages_keyed_and_muted', all(k and m for k, m in stage_ok.values()) and len(stage_ok) == 12 and petals_keyed == 12,
          f'{sum(k for k, _ in stage_ok.values())}/{len(stage_ok)} stage bones keyed, '
          f'{sum(m for _, m in stage_ok.values())} with every constraint muted; {petals_keyed}/12 petals keyed')

    # 2. the keyed pose evaluates to the rig's FK (hands, feet), and the stages to the solve's turns
    worst, worst_stage = 0.0, 0.0
    probe_f = [1, 45, 117, 160, 230]
    for f in probe_f:
        sc.frame_set(f)
        for n in ('leftHand', 'rightHand', 'leftFoot', 'rightFoot', 'head', 'leftThumbDistal', 'rightIndexDistal'):
            p, _W = rig.bone_world(byf[f], n)
            pb = h.arm.pose.bones[h.humanoid[n]]
            q = h.arm.matrix_world @ pb.head
            worst = max(worst, (p - q).length)
        for side in ('left', 'right'):
            for k, bn in (('roll', side + 'WristRoll'), ('flex', side + 'WristFlex')):
                want = byf[f]['wrists'][side][k]
                pb = h.arm.pose.bones[bn]
                got = h.basis_from_normalized(bn, want)
                worst_stage = max(worst_stage, math.degrees(got.rotation_difference(pb.rotation_quaternion).angle))
    check('fk_matches_blender', worst < 5e-4, f'bone heads within {worst * 1000:.3f} mm of the rig\'s FK at frames {probe_f}; '
          f'wrist stage keys within {worst_stage:.4f} deg')
    R['fk_worst_mm'] = round(worst * 1000, 4)

    # 3. the set-down, on the skinned mesh
    sets = foot_vertices(h)
    lows = {}
    for f in probe_f:
        sc.frame_set(f)
        lows[f] = round(1000 * lowest_evaluated(sets), 3)
    R['evaluated_lowest_foot_mm'] = lows
    check('set_down_on_floor', all(abs(v) < 1.0 for v in lows.values()),
          f'the lowest foot vertex of the evaluated mesh at {lows} mm (frames: mm over the floor)')

    # 4. the legs' clearance: the ankles' spacing against the clip's own, and the planted feet's slide
    from eidoblend.characters.robot.rig import RobotRig  # noqa: F401
    sep, sep_clip = [], []
    idle = rig.body
    from eidoblend.characters import load_clip
    clip = load_clip(h, 'idle')
    for fr in frames[::5]:
        pl, _ = rig.bone_world(fr, 'leftFoot')
        pr, _ = rig.bone_world(fr, 'rightFoot')
        sep.append((pl - pr).length)
    # the clip's own ankles (the hardware clamps only, no clearance), from a fresh rig on the same frames
    from eidoblend.characters.robot import rig as rigmod
    plain = rigmod.RobotRig(h, clearance=False, body=rig.body)
    for fr in frames[::5]:
        p3, off = plain.clip_pose(clip, (fr['f'] - 1) / 30.0 + 1 / 30.0)
        rec = plain.frame(p3, off, 1 / 30.0)
        rec['M'] = fr['M']
        pl, _ = plain.bone_world(rec, 'leftFoot')
        pr, _ = plain.bone_world(rec, 'rightFoot')
        sep_clip.append((pl - pr).length)
    R['ankle_spacing_mm'] = {'with_clearance': [round(1000 * min(sep), 1), round(1000 * max(sep), 1)],
                             'clip_only': [round(1000 * min(sep_clip), 1), round(1000 * max(sep_clip), 1)]}
    check('leg_clearance_widens', np.median(sep) - np.median(sep_clip) > 0.03,
          f'ankles {R["ankle_spacing_mm"]["with_clearance"]} mm apart against the clip\'s {R["ankle_spacing_mm"]["clip_only"]}')
    slide = {}
    for s in ('left', 'right'):
        prev = None
        for fr in frames:
            P = rig.feet_world(fr)[s]
            low = P[:, 2] < P[:, 2].min() + 0.0025
            if prev is not None and low.any() and prev[1].any():
                both = low & prev[1]
                if both.any():
                    d = float(np.min(np.linalg.norm(P[both, :2] - prev[0][both, :2], axis=1)))
                    slide[s] = max(slide.get(s, 0.0), d)
            prev = (P, low)
    R['planted_slide_mm_per_frame'] = {s: round(1000 * v, 3) for s, v in slide.items()}
    check('planted_feet_hold', all(v < 0.004 for v in slide.values()),
          f'the least-moving sole point in contact two frames running moves at most {R["planted_slide_mm_per_frame"]} mm a frame '
          f'(the stock idle sways its hips; the example sets the body down vertically only)')

    # 5. the hands inside their pins' ranges
    T = rig.hinges
    out_of = []
    for fr in frames:
        for side in ('left', 'right'):
            m = 1 if side == 'left' else -1
            for b in dof.FINGER_PINS:
                j = T.get('left' + b)
                q = fr['N'].get(side + b)
                if not j or q is None:
                    continue
                from eidoblend.characters._math import angle_about, q_to_three
                q3 = q_to_three(q)
                q3 = q3 if m > 0 else type(q3)((q3.w, q3.x, -q3.y, -q3.z))
                g = math.degrees(angle_about(q3, j['axis'])) + j['flex_at_rest']
                if g < j['deg'][0] - 0.01 or g > j['deg'][1] + 0.01:
                    out_of.append((fr['f'], side + b, round(g, 2), j['deg']))
    check('finger_pins_in_range', not out_of, f'{len(out_of)} finger pin readings outside the joints file\'s ranges '
          f'{out_of[:4]}; thumb solve last: {dof.hand_debug(rig.hands)}')

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'robot_example.blend'), compress=True)
    if RENDER:
        cam = ex['camera']
        rs = {}
        for tt in (0.5, 2.1, 3.85, 5.25, 6.8, 7.6):
            f = 1 + round(tt * 30)
            p = os.path.join(S.OUT, f'robot_example_t{tt:.2f}.png')
            rs[os.path.basename(p)] = S.C.still(sc, cam, f, p)
        close = S.C.camera('close', 85.0)
        for tt in (0.5, 4.0):
            f = 1 + round(tt * 30)
            sc.frame_set(f)
            hl = h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['rightHand']].head
            S.C.aim(close, hl + Vector((0.5, -0.85, 0.06)), hl + Vector((0.0, 0.0, -0.08)))
            p = os.path.join(S.OUT, f'robot_example_hands_t{tt:.2f}.png')
            rs[os.path.basename(p)] = S.C.still(sc, close, f, p)
            fl = (h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['leftFoot']].head
                  + h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['rightFoot']].head) / 2
            S.C.aim(close, fl + Vector((0.35, -1.9, 0.45)), fl + Vector((0.0, 0.0, -0.03)))
            p = os.path.join(S.OUT, f'robot_example_feet_t{tt:.2f}.png')
            rs[os.path.basename(p)] = S.C.still(sc, close, f, p)
        R['renders'] = rs
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('robot_example.json', R)
log('done', R['ok'], R['seconds'], 's')
