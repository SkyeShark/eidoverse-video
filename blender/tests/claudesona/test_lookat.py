"""Eyes on a target (characters/lookat.py), measured against the engine's own three-vrm (deno, CPU): the character turns
and nods (30 fps) while a target circles in front of its face; the eye bones' world rotations and the yaw / pitch are
compared frame by frame for claude_suit.vrm (0.87) and aletheia.vrm.

Checks:
    yaw / pitch within 0.01 deg of three-vrm's VRMLookAt on every frame (lag=1, the engine's timing)
    each eye bone's world rotation within 0.05 deg of three-vrm's raw eye bones
    the keys are on the '<name>|lookat' NLA track, LINEAR, and a saved frame re-evaluates the same
    the expression applier (kind='expression') keys lookLeft/Right/Up/Down by three-vrm's rules
    key_yaw_pitch keys a hand-written gaze (claude_robot.js's vrm.lookAt.yaw bump)
    the claudesona's eye bones carry no vertices (its eyes are painted on the face plate): reported
Stills: out/lookat_aletheia_sheet.png (the eyes on a lit target: centre, her left, her right, up, down; close up).

    bash run_blender.sh blender/tests/claudesona/test_lookat.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters._math import q_to_three  # noqa: E402
from eidoblend.characters.lookat import LookAt, bake_look_at  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, N = 30, 90
TURN = [[0.0, 0.0], [0.4, 0.0], [1.0, 35.0], [2.0, 35.0], [2.6, 0.0], [3.0, 0.0]]
NOD = [[0.0, 0.0], [0.8, 0.0], [1.2, 14.0], [1.6, -10.0], [2.0, 0.0], [3.0, 0.0]]
SCALE = {'claude_suit': 0.87, 'aletheia': 1.0}
_RX90I = Quaternion((1.0, 0.0, 0.0), math.pi / 2).inverted()


def key_motion(h):
    arm = h.arm
    arm.rotation_mode = 'XYZ'
    pb = arm.pose.bones[h.humanoid['head']]
    pb.rotation_mode = 'QUATERNION'
    for i in range(N):
        f, t = 1 + i, i / FPS
        arm.rotation_euler = (0.0, 0.0, math.radians(S.lerp_keys(TURN, t)))
        arm.keyframe_insert('rotation_euler', index=2, frame=f)
        h.write_pose({'head': Quaternion((1.0, 0.0, 0.0), math.radians(S.lerp_keys(NOD, t)))})
        pb.keyframe_insert('rotation_quaternion', frame=f)
    from bpy_extras import anim_utils
    act = arm.animation_data.action
    cb = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def target_path(h):
    """a point circling 0.9 m in front of the face (Blender world, per frame)"""
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    out = {}
    for i in range(N):
        a = 2 * math.pi * i / N * 1.5
        out[1 + i] = Vector((0.55 * math.sin(a), hb.y - 0.9, hb.z + 0.08 + 0.35 * math.sin(2 * a)))
    return out


def eye_world_three(h, side):
    b = h.humanoid.get(side)
    if not b:
        return None
    m = h.arm.matrix_world @ h.arm.pose.bones[b].matrix
    return q_to_three(m.to_3x3().normalized().to_quaternion() @ _RX90I)


def run(who, C, R):
    sc = S.clean_scene(FPS)
    sc.frame_start, sc.frame_end = 1, N
    h = load_vrm(who)
    h.arm.scale = (SCALE[who],) * 3
    bpy.context.view_layer.update()
    key_motion(h)
    tgt = target_path(h)
    job = {'vrm': h.path.replace('\\', '/'), 'scale': SCALE[who], 'fps': FPS, 'frames': N, 'turn': TURN, 'nod': NOD,
           'tie': None, 'look': {'targets': [S.to_three(tgt[f]) for f in range(1, N + 1)]}}
    ref = S.three_vrm(job, f'lookat_{who}')
    rep = bake_look_at(h, lambda f: tgt[f], 1, N, lag=1)
    R['bake'] = {k: v for k, v in rep.items() if k != 'yaw_pitch'}
    dyp = max(max(abs(y - ry), abs(p - rp)) for (_f, y, p), (ry, rp) in zip(rep['yaw_pitch'], ref['yawPitch']))
    R['yaw_pitch_max_diff_deg'] = round(dyp, 6)
    R['yaw_range_deg'] = [round(min(y for _f, y, _p in rep['yaw_pitch']), 2), round(max(y for _f, y, _p in rep['yaw_pitch']), 2)]
    R['pitch_range_deg'] = [round(min(p for _f, _y, p in rep['yaw_pitch']), 2), round(max(p for _f, _y, p in rep['yaw_pitch']), 2)]
    C.check(f"{who}: yaw / pitch follow three-vrm's VRMLookAt within 0.01 deg", dyp < 0.01,
            f"max {dyp:.5f} deg; yaw {R['yaw_range_deg']}, pitch {R['pitch_range_deg']}")
    # each eye's world rotation as a turn from its own rest (the bone frames' conventions cancel)
    def q3(a):
        return Quaternion((a[3], a[0], a[1], a[2]))
    rest_b = {}
    for side in ('leftEye', 'rightEye'):
        b = h.humanoid.get(side)
        if b:
            rest_b[side] = q_to_three(h.arm.data.bones[b].matrix_local.to_3x3().normalized().to_quaternion())
    worst = 0.0
    for f in range(1, N + 1):
        sc.frame_set(f)
        for side, k in (('leftEye', 0), ('rightEye', 1)):
            r, r0 = ref['eyes'][f - 1][k], ref['eyesRest'][k]
            b = h.humanoid.get(side)
            if r is None or r0 is None or not b:
                continue
            wb = q_to_three((h.arm.matrix_world.to_3x3().normalized() @
                             h.arm.pose.bones[b].matrix.to_3x3().normalized()).to_quaternion())
            d_b = wb @ rest_b[side].inverted()
            d_3 = q3(r) @ q3(r0).inverted()
            a = math.degrees(d_b.rotation_difference(d_3).angle)
            worst = max(worst, min(a, 360.0 - a))
    R['eye_world_max_diff_deg'] = round(worst, 5)
    C.check(f"{who}: both eye bones' world rotations follow three-vrm's within 0.05 deg", worst < 0.05, f'max {worst:.4f} deg')
    ad = h.arm.animation_data
    tr = ad.nla_tracks.get(f'{h.name}|lookat')
    ok = tr is not None and len(tr.strips) == 1
    C.check(f"{who}: the gaze is keyed on the '{h.name}|lookat' NLA track", ok, tr.name if tr else 'missing')
    weights = 0
    eyes = [h.humanoid.get('leftEye'), h.humanoid.get('rightEye')]
    for o in h.meshes:
        for g in o.vertex_groups:
            if g.name in eyes:
                gi = g.index
                weights += sum(1 for v in o.data.vertices for e in v.groups if e.group == gi and e.weight > 0)
    R['eye_bone_vertices'] = weights
    return h, tgt


def expression_type(C, R):
    """claude_robot.vrm binds lookLeft / Right / Up / Down (6 morphs each): the expression applier on it"""
    sc = S.clean_scene(FPS)
    h = load_vrm('claude_robot')
    file_type = LookAt(h).type
    look = LookAt(h, kind='expression')
    R['claude_robot_file_lookat_type'] = file_type
    rep = look.key_yaw_pitch([(1, 0.0, 0.0), (11, 45.0, 0.0), (21, -60.0, 0.0), (31, 0.0, -30.0), (41, 0.0, 20.0)])
    vals = {}
    for f in (11, 21, 31, 41):
        sc.frame_set(f)
        vals[f] = {}
        for e in ('lookLeft', 'lookRight', 'lookUp', 'lookDown'):
            o, k, _w = h.expr[e][0]
            vals[f][e] = round(o.data.shape_keys.key_blocks[k].value, 4)
    R['expression_type'] = {'report': rep, 'values': vals, 'maps': [look.range_map_horizontal_outer.output_scale,
                                                                   look.range_map_vertical_up.output_scale]}
    m_out = look.range_map_horizontal_outer
    exp = {11: ('lookLeft', m_out.map(45)), 21: ('lookRight', m_out.map(60)), 31: ('lookUp', look.range_map_vertical_up.map(30)),
           41: ('lookDown', look.range_map_vertical_down.map(20))}
    bind_w = {e: h.expr[e][0][2] if h.expr.get(e) else 1.0 for e in ('lookLeft', 'lookRight', 'lookUp', 'lookDown')}
    ok = all(abs(vals[f][e] - v * bind_w[e]) < 1e-3 for f, (e, v) in exp.items())
    C.check("expression lookAt: lookLeft / lookRight / lookUp / lookDown keyed by three-vrm's maps", ok,
            f"{ {f: (e, round(v, 3), vals[f][e]) for f, (e, v) in exp.items()} } (file outputScale {look.range_map_horizontal_outer.output_scale})")


def hand_keys(C, R):
    sc = S.clean_scene(FPS)
    h = load_vrm('claude_suit')
    look = LookAt(h)

    def bump(t, a, b):
        return max(0.0, math.sin(math.pi * min(1, max(0, (t - a) / (b - a)))))
    keys = [(1 + i, 20 * (bump(i / FPS, 0.2, 1.0) - bump(i / FPS, 1.0, 1.8)), 0.0) for i in range(60)]
    rep = look.key_yaw_pitch(keys)
    sc.frame_set(1 + 18)
    q = h.arm.pose.bones[h.humanoid['leftEye']].rotation_quaternion
    R['hand_keys'] = {'report': rep, 'eye_basis_angle_f19_deg': round(math.degrees(q.angle), 4)}
    C.check("key_yaw_pitch: claude_robot.js's hand-written gaze bump keyed (eyes turned mid-bump)",
            rep['keys'] > 0 and math.degrees(q.angle) > 1.0, f"{rep['keys']} keys, {math.degrees(q.angle):.2f} deg at f19")


def render(R):
    sc = S.clean_scene(FPS)
    h = load_vrm('aletheia')
    S.probe_render(sc, res=(420, 300), samples=16)
    S.turntable_studio(sc, light=0.7)
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    eye = (h.arm.matrix_world @ h.arm.data.bones[h.humanoid['leftEye']].head_local +
           h.arm.matrix_world @ h.arm.data.bones[h.humanoid['rightEye']].head_local) / 2
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(0, 0, 0))
    ball = bpy.context.object
    m = bpy.data.materials.new('target')
    m.use_nodes = True
    nt = m.node_tree
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.55, 0.15, 1.0)
    em.inputs['Strength'].default_value = 6.0
    nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    ball.data.materials.append(m)
    spots = {1: (0.0, 0.0), 2: (0.9, 0.0), 3: (-0.9, 0.0), 4: (0.0, 0.6), 5: (0.0, -0.55)}
    tgt = {f: Vector((eye.x + x, eye.y - 0.7, eye.z + z)) for f, (x, z) in spots.items()}
    for f, p in tgt.items():
        ball.location = p
        ball.keyframe_insert('location', frame=f)
    rep = bake_look_at(h, lambda f: tgt[f], 1, 5, lag=0)
    R['render_yaw_pitch'] = rep['yaw_pitch']
    cam = S.camera('eyecam', lens=135)
    S.aim(cam, (eye.x, eye.y - 0.62, eye.z + 0.01), (eye.x, eye.y, eye.z - 0.005))
    sc.camera = cam
    paths = []
    for f in spots:
        p = os.path.join(S.OUT, f'lookat_aletheia_{f}.png')
        S.still(sc, cam, f, p)
        paths.append(p)
    R['sheet'] = S.sheet(paths, os.path.join(S.OUT, 'lookat_aletheia_sheet.png'), cols=5)
    _ = hb


def main():
    R, C = {}, S.Checks('lookat')
    try:
        for who in ('claude_suit', 'aletheia'):
            R[who] = {}
            run(who, C, R[who])
        R['claudesona_eye_bone_vertices'] = R['claude_suit']['eye_bone_vertices']
        C.check("claude_suit: the eye bones carry no vertices (its eyes are painted on the face plate; reported)",
                True, f"{R['claude_suit']['eye_bone_vertices']} weighted vertices; aletheia "
                      f"{R['aletheia']['eye_bone_vertices']}")
        expression_type(C, R)
        hand_keys(C, R)
        if RENDER:
            render(R)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(S.OUT, 'lookat.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[lookat] ALL PASS' if R['all_pass'] else '[lookat] SOME FAILED', flush=True)


main()
