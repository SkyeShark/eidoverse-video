"""robot_dof against claude_robot_dof.js, frame by frame: my body's rig data (every bone's rest frame, the normalized
humanoid, the foot vertices, the joints file's hinges) and a 30 fps sequence of real clip poses (idle, walk in place,
turnLeft, talk, cheer, sitting_normal_chair, reach, jump, with crossfades between them, sampled from the add-on's own
retarget) go to BOTH editions in the example's frame order:

    restoreArmPose, the clip, keepArmPose, rehomeBody, applyHardwareDOF(LEG_JOINTS), applyLegClearance(dt),
    applyArmDOF(dt) (the wrist's three stages and its turn limit), applyHandDOF, applyHeadExpression, applyCrown

The JS runs under deno on a mock VRM built from the same rig data (three's own maths; the stateful passes keep their
WeakMap memos across the frames). Compared per frame: every humanoid bone's normalized rotation, the hip stages, the
shoulder pitch helpers, the wrist roll and flex stages, the thumb rotors and the 12 petals. Writes out/dof_parity.json.

    bash run_blender.sh blender/tests/robot_body/test_dof_parity.py
"""

import json
import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

from mathutils import Quaternion  # noqa: E402

from eidoblend.characters import load_clip, load_vrm  # noqa: E402
from eidoblend.characters import robot_dof as dof  # noqa: E402
from eidoblend.characters._math import v_to_three  # noqa: E402
from eidoblend.characters.vrm import joints_record  # noqa: E402

FPS = 30
DT = 1.0 / FPS
SEQ = [('idle', 2.0), ('walk', 2.4), ('turnLeft', 1.6), ('talk', 2.0), ('cheer', 2.0), ('sitting_normal_chair', 2.0),
       ('reach', 2.4), ('jump', 1.6), ('idle', 1.0)]
FADE = 0.4
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()


def log(*a):
    print('[dof_parity]', *a, flush=True)


def q4(q):
    return [q.w, q.x, q.y, q.z]


def q4n(q):
    """a clip input normalised in double precision: both editions then read the same unit turn (an f32 quaternion's norm is
    1 +- 1e-7, and claude_robot_dof.js's 'the same turn' test, |a . b| > 1 - 1e-12, fires on that noise for two turns up to
    0.06 deg apart: a property of the input's rounding, not of either edition)"""
    n = math.sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z)
    return [q.w / n, q.x / n, q.y / n, q.z / n]


def qrot(q, v):
    w, x, y, z = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx)


def qmul(a, b):
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def ankle(rig, qs, side):
    """the ankle and the ball (the toes' joint) from the hips, three's axes, double precision: Qh (t + qt (s + qs f))"""
    hd = {n: rig['bones'][b]['p'] for n, b in rig['humanoid'].items()}

    def sub(a, b):
        return [hd[a][i] - hd[b][i] for i in range(3)]
    t, s, f, to = sub(side + 'UpperLeg', 'hips'), sub(side + 'LowerLeg', side + 'UpperLeg'), \
        sub(side + 'Foot', side + 'LowerLeg'), sub(side + 'Toes', side + 'Foot')
    Qh, Qt, Qs, Qf = qs['hips'], qs[side + 'UpperLeg'], qs[side + 'LowerLeg'], qs[side + 'Foot']
    a = qrot(Qs, f)
    a = qrot(Qt, [a[i] + s[i] for i in range(3)])
    a = qrot(Qh, [a[i] + t[i] for i in range(3)])
    b = qrot(qmul(qmul(qmul(Qh, Qt), Qs), Qf), to)
    return a, [a[i] + b[i] for i in range(3)]


def bump(t, t0, t1):
    if t <= t0 or t >= t1:
        return 0.0
    u = (t - t0) / (t1 - t0)
    u = u * u * (3 - 2 * u)
    return math.sin(math.pi * u)


def face(t):
    w = {'happy': bump(t, 0.5, 3.0), 'sad': bump(t, 4.0, 7.0), 'surprised': bump(t, 8.0, 9.5), 'angry': bump(t, 11.0, 13.0),
         'relaxed': bump(t, 14.0, 17.0)}
    yaw = 20.0 * (bump(t, 3.0, 4.0) - bump(t, 9.5, 11.0))
    w['lookLeft'] = min(1.0, max(0.0, yaw) / 28.0)
    w['lookRight'] = min(1.0, max(0.0, -yaw) / 28.0)
    return w


def rig_data(h):
    bones = {}
    for b in h.arm.data.bones:
        bones[b.name] = {'parent': b.parent.name if b.parent else None, 'q': q4(h.node_frame_three(b.name)),
                         'p': list(v_to_three(b.head_local))}
    inv = {v: k for k, v in h.humanoid.items()}
    norm_parent = {}
    for n, bn in h.humanoid.items():
        p = h.arm.data.bones[bn].parent
        while p is not None and p.name not in inv:
            p = p.parent
        norm_parent[n] = inv[p.name] if p is not None else None
    want = {h.humanoid[s + b]: s + b for s in ('left', 'right') for b in ('Foot', 'Toes')}
    feet = {bn: [] for bn in want}
    m_inv = h.arm.matrix_world.inverted()
    for o in h.meshes:
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        if not any(n in want for n in idx.values()):
            continue
        M = m_inv @ o.matrix_world
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            n = idx.get(best)
            if n in want:
                feet[n].append(list(v_to_three(M @ v.co)))
    return {'bones': bones, 'humanoid': h.humanoid, 'norm_parent': norm_parent, 'feet': feet}


def sequence(h):
    clips = {n: load_clip(h, n) for n, _d in SEQ}
    frames = []
    for i, (name, dur) in enumerate(SEQ):
        c = clips[name]
        n = int(round(dur * FPS))
        for k in range(n):
            tc = k * DT
            q, hp = S.raw_pose(h, c, tc)
            if i > 0 and k < int(FADE * FPS):
                pn, pd = SEQ[i - 1]
                q0, hp0 = S.raw_pose(h, clips[pn], pd + k * DT)
                u = (k + 1) / (FADE * FPS)
                u = u * u * (3 - 2 * u)
                q = {b: q0[b].slerp(q[b], u) for b in q}
                hp = hp0.lerp(hp, u)
            frames.append({'q': {b: q4n(v) for b, v in q.items()}, 'hp': list(hp), 'clip': name})
    for j, fr in enumerate(frames):
        fr['w'] = face(j * DT)
    return frames


def run_python(h, hinges, frames):
    legs = dof.init_leg_dof(h)
    arms = dof.init_arm_dof(h, hinges, mute_wrist=True)
    hands = dof.init_hand_dof(h, hinges)
    clear = dof.LegClearance(h)
    head, crown = dof.init_head_expression(), dof.init_crown(h)
    out = []
    stats = {}
    t = time.time()
    for fr in frames:
        p3 = {}
        dof.restore_arm_pose(arms, p3)
        p3 = {n: Quaternion(v) for n, v in fr['q'].items()}
        dof.keep_arm_pose(arms, p3)
        dof.rehome_body(p3, stats)
        dof.apply_hardware_dof(p3, dof.LEG_JOINTS, legs, stats)
        dof.apply_leg_clearance(clear, p3, fr['hp'], stats, DT, None, legs)
        dof.apply_arm_dof(arms, p3, DT, 8.0, stats)
        dof.apply_hand_dof(hands, p3, stats)
        w = fr['w']
        dof.apply_head_expression(head, p3, w, DT)
        petals = dof.apply_crown(crown, w, dof.head_roll_deg(p3), DT, look=w['lookLeft'] - w['lookRight'])
        st = {}
        for side in dof.SIDES:
            o = legs.out.get(side) or {}
            for k, v in o.items():
                st[side + 'Hip' + k.capitalize()] = q4(v)
            if side in arms.helper_phi:
                st[side + 'ShoulderPhi'] = arms.helper_phi[side]
            for k, v in (arms.wrist_out.get(side) or {}).items():
                st[side + 'Wrist' + k.capitalize()] = q4(v)
            if side in hands.rotor_out:
                st[side + 'ThumbRotor'] = q4(hands.rotor_out[side])
        dbg = {}
        for side in dof.SIDES:
            W, T, L, M = arms.wrist.get(side), hands.side[side], legs.sides.get(side), clear.mem[side]
            dbg[side] = {'wrist': [W['a'], W['b'], W['c'], *W['asked']] if W else None, 'thumb': [T['alpha'], T['beta']],
                         'hip': [L['a'], L['b'], L['c']] if L else None, 'loaded': M['loaded'], 'st': M['st'],
                         'next': list(M['next']) if M['next'] else None, 'wst': M['wst']}
        dbg['vst'] = list(clear.mem['vst']) if clear.mem['vst'] is not None else None
        out.append({'q': {n: q4(v) for n, v in p3.items()}, 'stages': st, 'petals': petals, 'dbg': dbg,
                    'clear': {s: dict(v) for s, v in clear.last.items()}})
    return out, round(time.time() - t, 2), stats


def qdiff(a, b):
    """the angle between two orientations (deg), in double precision: mathutils is single precision, so its own dot of two
    equal unit quaternions can read 1 - 1.2e-7 (a 0.056 deg floor); here the relative turn's vector part is measured"""
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    a, b = [x / na for x in a], [x / nb for x in b]
    if a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3] < 0:
        b = [-x for x in b]
    # conj(a) * b: its vector part's length is sin(angle / 2)
    w = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    x = a[0] * b[1] - a[1] * b[0] - a[2] * b[3] + a[3] * b[2]
    y = a[0] * b[2] + a[1] * b[3] - a[2] * b[0] - a[3] * b[1]
    z = a[0] * b[3] - a[1] * b[2] + a[2] * b[1] - a[3] * b[0]
    return 2.0 * math.degrees(math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))


GROUPS = {
    'legs': [s + b for s in ('left', 'right') for b in ('UpperLeg', 'LowerLeg', 'Foot', 'Toes')],
    'torso_head': ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head'],
    'arms': [s + b for s in ('left', 'right') for b in ('Shoulder', 'UpperArm', 'LowerArm')],
    'hands': ['leftHand', 'rightHand'],
    'fingers': [s + f for s in ('left', 'right') for f in dof.FINGER_PINS],
    'thumb_metacarpals': ['leftThumbMetacarpal', 'rightThumbMetacarpal'],
}

try:
    sc = S.C.clean_scene(FPS)
    h = load_vrm('claude_robot', name='claude')
    rec = joints_record(h)
    hinges = rec['hinges']
    rig = rig_data(h)
    frames = sequence(h)
    R['frames'] = len(frames)
    log('frames', len(frames), 'foot vertices', {k: len(v) for k, v in rig['feet'].items()})
    py, py_s, stats = run_python(h, hinges, frames)
    R['python_s'] = py_s
    R['python_stats_max_deg'] = {k: round(v, 2) for k, v in sorted(stats.items())}
    inp = S.write_json('dof_parity_in.json', {'rig': rig, 'hinges': hinges, 'frames': frames, 'dt': DT})
    outp = os.path.join(S.OUT, 'dof_parity_js.json')
    t = time.time()
    js_log = S.run_deno(os.path.join(S.HERE, 'dof_parity.mjs'), S.THREE_JS, os.path.join(S.REPO, 'eidoverse', 'claude_robot_dof.js'),
                        inp, outp)
    R['js_s'] = round(time.time() - t, 1)
    R['js_log'] = js_log.strip().splitlines()[-8:]
    with open(outp, encoding='utf-8') as f:
        js = json.load(f)
    worst, over = {}, {}
    TOL = 1e-3
    TOL_MM = 0.05
    for i, (a, b) in enumerate(zip(py, js['frames'])):
        for s in ('left', 'right'):
            pa, pb = ankle(rig, a['q'], s), ankle(rig, b['q'], s)
            for g, u, v in (('ankle_mm', pa[0], pb[0]), ('ball_mm', pa[1], pb[1])):
                d = 1000 * math.dist(u, v)
                if d > worst.get(g, (0, None, None))[0]:
                    worst[g] = (d, i, s)
                if d > TOL_MM:
                    over.setdefault(g, set()).add(i)
        for g, names in GROUPS.items():
            for n in names:
                if n in a['q'] and n in b['q']:
                    d = qdiff(a['q'][n], b['q'][n])
                    if n.endswith('LowerLeg') and min(qdiff([1, 0, 0, 0], a['q'][n]), qdiff([1, 0, 0, 0], b['q'][n])) < 5.0:
                        # a near-straight knee turns a hair of reach into degrees (|T| changes by L1 L2 k dk / |T|: at
                        # 1 deg of knee, 0.1 mm of reach is 1 deg): judged by the ankle's place (ankle_mm), not its angle
                        continue
                    if d > worst.get(g, (0, None, None))[0]:
                        worst[g] = (d, i, n)
                    if d > TOL:
                        over.setdefault(g, set()).add(i)
        for k, v in a['stages'].items():
            if k not in b['stages']:
                worst.setdefault('missing_' + k, (1e9, i, k))
                continue
            d = abs(v - b['stages'][k]) * 180 / math.pi if isinstance(v, float) else qdiff(v, b['stages'][k])
            g = 'stage_' + k[len('left'):] if k.startswith('left') else 'stage_' + k[len('right'):]
            if d > worst.get(g, (0, None, None))[0]:
                worst[g] = (d, i, k)
            if d > TOL:
                over.setdefault(g, set()).add(i)
        dp = max(abs(x - y) for x, y in zip(a['petals'], b['petals']))
        if dp > worst.get('petals', (0, None, None))[0]:
            worst['petals'] = (dp, i, 'phi')
        if dp > TOL:
            over.setdefault('petals', set()).add(i)
    # the passes' own state, side by side: where the legs' clearance first decides differently (loaded, stance), how far
    # its offsets and v_st part, where the wrist's and the thumb's solved angles part
    div = {}
    for i, (a, b) in enumerate(zip(py, js['frames'])):
        for s in ('left', 'right'):
            pa, pb = a['dbg'][s], b['dbg'][s]
            for k in ('loaded', 'st'):
                if pa[k] != pb[k]:
                    div.setdefault(f'{s}_{k}_first', [i, a['clip'] if 'clip' in a else frames[i]['clip'], pa[k], pb[k]])
                    div[f'{s}_{k}_frames'] = div.get(f'{s}_{k}_frames', 0) + 1
            if pa['next'] and pb['next']:
                d = 1000 * math.hypot(pa['next'][0] - pb['next'][0], pa['next'][1] - pb['next'][1])
                if d > div.get(f'{s}_offset_mm', [0])[0]:
                    div[f'{s}_offset_mm'] = [round(d, 4), i, frames[i]['clip']]
            for k, n in (('wrist', 3), ('thumb', 2), ('hip', 3)):
                if pa[k] and pb[k]:
                    d = max(abs(x - y) for x, y in zip(pa[k][:n], pb[k][:n])) * 180 / math.pi
                    if d > div.get(f'{s}_{k}_deg', [0])[0]:
                        div[f'{s}_{k}_deg'] = [round(d, 5), i, frames[i]['clip']]
                    if d > TOL and f'{s}_{k}_first' not in div:
                        div[f'{s}_{k}_first'] = [i, frames[i]['clip'], [round(x * 180 / math.pi, 4) for x in pa[k]],
                                                 [round(x * 180 / math.pi, 4) for x in pb[k]]]
        va, vb = a['dbg']['vst'], b['dbg']['vst']
        if va and vb:
            d = math.dist(va, vb)
            if d > div.get('vst_mps', [0])[0]:
                div['vst_mps'] = [round(d, 6), i]
        elif (va is None) != (vb is None):
            div.setdefault('vst_presence_first', i)
    R['divergence'] = div
    R['worst_deg'] = {g: [round(v[0], 6), v[1], v[2]] for g, v in sorted(worst.items())}
    R['frames_over_tol'] = {g: len(v) for g, v in over.items()}
    R['first_over'] = {g: min(v) for g, v in over.items()}
    R['tolerance_deg'] = TOL
    R['js_counts'] = js.get('counts')
    # the legs' clearance did act: offsets held on loaded feet, eased on swinging ones
    R['clearance_offsets_mm'] = {s: [round(1000 * min(math.hypot(*f['clear'][s]['offset']) for f in py), 1),
                                     round(1000 * max(math.hypot(*f['clear'][s]['offset']) for f in py), 1)] for s in ('left', 'right')}
    ok = True
    for g in list(GROUPS) + ['stage_HipPitch', 'stage_HipSwing', 'stage_ShoulderPhi', 'stage_WristRoll', 'stage_WristFlex',
                             'stage_ThumbRotor', 'petals', 'ankle_mm', 'ball_mm']:
        w = worst.get(g)
        good = w is not None and w[0] <= (TOL_MM if g.endswith('_mm') else TOL)
        ok &= good
        unit, tol = ('mm', TOL_MM) if g.endswith('_mm') else ('deg', TOL)
        print(f'{"PASS" if good else "FAIL"} parity {g}: worst {w[0] if w else None} {unit} (frame {w[1] if w else None}, '
              f'{w[2] if w else None}); frames over {tol}: {len(over.get(g, ()))}', flush=True)
    R['ok'] = ok
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('dof_parity.json', R)
log('done', R['ok'], R['seconds'], 's')
