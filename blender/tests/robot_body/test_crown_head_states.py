"""Every crown and head state of my body: claude_robot_dof.js's presets CROWN_STATES (neutral, happy, angry, sad, relaxed,
surprised, thinking, listening, curious, resting) and HEAD_STATES (happy, angry, sad, relaxed, surprised, curious,
thinking), as applyCrown / applyHeadExpression take them by `state` (robot_dof.apply_crown / apply_head_expression;
RobotRig.frame's crown_state / head_state).

Standing in the idle with a neutral face, I go through the ten crown states one after another, 1.5 s each, the head's
state with it where HEAD_STATES has one, every frame through the example's frame order (the actuators at their rates:
the crown's lead screws 240 deg/s, the neck 120 deg/s), keyed on one timeline. Checks (PASS / FAIL):
  - at the end of each state every petal's fold is the state's (its rank's value inside the petal's built stops, the
    stem interlock where the head rolls toward a stem), within 0.01 deg
  - the head's actuators hold the state's pitch / roll / pan (0 where HEAD_STATES has none), within 0.01 deg
  - the keyed petals in Blender match the records (each petal bone's turn about its own X against the fold, 0.01 deg)
  - nothing moves faster than its actuator: no petal turns more than 240 deg/s, the head's state no more than 120 deg/s
Stills: out/crown_head_<state>_f<k>.png (my head, front three-quarter); out/crown_head_states.json, .blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_crown_head_states.py [--no-render]
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
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.characters import Ground, load_clip, load_vrm  # noqa: E402
from eidoblend.characters import robot_dof as dof  # noqa: E402
from eidoblend.characters._math import q_to_three  # noqa: E402
from eidoblend.characters.robot import RobotRig, key_robot  # noqa: E402
from eidoblend.characters.robot.example import directional, studio_environment  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
HOLD = 36                                          # frames per state (1.5 s)
STATES = list(dof.CROWN_STATES)
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'states': STATES}
T0 = time.time()
OK = True


def log(*a):
    print('[crown_head]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def expected_folds(state, head_roll):
    """CROWN_STATES[state] per petal (its rank), inside PETAL_FOLD's stops, with SPEC's stem interlock"""
    out = []
    for i in range(12):
        r = i if i < 6 else 11 - i
        lo0, hi = dof.PETAL_FOLD[i]
        toward = head_roll if dof.PETAL_A[i] > 0 else -head_roll
        lo = max(lo0, dof.STEM_LOCK['fold']) if (r == 5 and toward >= dof.STEM_LOCK['roll'] - 1e-6) else lo0
        out.append(min(hi, max(lo, dof.CROWN_STATES[state][r])))
    return out


try:
    sc = S.C.clean_scene(FPS)
    studio_environment(sc, 0.8, 0x121214)
    directional('key', (-2.0, 3.0, 3.0), 0xfff4e8, 2.2)
    directional('rim', (2.5, 2.5, -3.0), 0xdfe8ff, 1.2)
    S.C.floor_disc()
    me = load_vrm('claude_robot', name='claude')
    rig = RobotRig(me)
    idle = load_clip(me, 'idle')
    ground = Ground(fn=lambda x, y: 0.0 * np.asarray(x))
    dt = 1.0 / FPS
    frames, ends = [], {}
    head_track = []
    f = 1
    for k, st in enumerate(STATES):
        hs = st if st in dof.HEAD_STATES else None
        for j in range(HOLD):
            p3, off = rig.clip_pose(idle, (f - 1) * dt + dt)
            rec = rig.frame(p3, off, dt, {}, None, st, hs, state_weight=1.0)
            rig.place(rec, Matrix.Identity(4), ground)
            rig.rest_feet(rec, ground)
            rec['f'] = f
            frames.append(rec)
            head_track.append((f, dict(rig.head.st)))
            f += 1
        ends[st] = f - 1
    act = key_robot(me, frames, 'claude|crown_head_states')
    sc.frame_start, sc.frame_end = 1, frames[-1]['f']

    # 1. the petals at each state's end against the table
    worst, per = 0.0, {}
    for st in STATES:
        fr = frames[ends[st] - 1]
        roll = dof.head_roll_deg({n: q_to_three(q) for n, q in fr['N'].items()})
        want = expected_folds(st, roll)
        d = max(abs(a - b) for a, b in zip(fr['petals'], want))
        per[st] = {'folds': [round(v, 2) for v in fr['petals']], 'max_off_deg': round(d, 4), 'head_roll_deg': round(roll, 2)}
        worst = max(worst, d)
    R['crown'] = per
    check('crown_states', worst < 0.01, f'every petal at its state\'s fold (inside its stops, the stem interlock) within '
          f'{worst:.4f} deg at the end of each of {len(STATES)} states')
    # 2. the head's actuators at the state's pose
    hw = 0.0
    hd = {}
    for st in STATES:
        want = dof.HEAD_STATES.get(st, {'pitch': 0.0, 'roll': 0.0, 'pan': 0.0})
        got = dict(head_track[ends[st] - 1][1])
        d = max(abs(got[c] - want[c]) for c in want)
        hd[st] = {'got': {c: round(v, 3) for c, v in got.items()}, 'want': want}
        hw = max(hw, d)
    R['head'] = hd
    check('head_states', hw < 0.01, f'the head\'s pitch / roll / pan at each state\'s within {hw:.4f} deg ('
          f'{len(dof.HEAD_STATES)} head states, neutral elsewhere)')
    # 3. the keyed petals in Blender against the records
    arm = me.arm
    pet = [f'petal_{i:02d}' for i in range(12)]
    kw = 0.0
    for st in STATES:
        fk = ends[st]
        sc.frame_set(fk)
        fr = frames[fk - 1]
        for i, nm in enumerate(pet):
            pb = arm.pose.bones.get(nm)
            if pb is None:
                continue
            q = pb.rotation_quaternion if pb.rotation_mode == 'QUATERNION' else pb.matrix_basis.to_quaternion()
            ang = math.degrees(2.0 * math.atan2(q.x, q.w))
            kw = max(kw, abs(ang - (fr['petals'][i] - dof.PETAL_REST)))
    check('petals_keyed', kw < 0.01, f'each petal bone\'s keyed turn about its X is its fold less the rest '
          f'({dof.PETAL_REST}) within {kw:.4f} deg at every state\'s end')
    # 4. the actuators' rates
    pr = max(abs(b['petals'][i] - a['petals'][i]) for a, b in zip(frames[:-1], frames[1:]) for i in range(12)) * FPS
    hr = max(abs(b[1][c] - a[1][c]) for a, b in zip(head_track[:-1], head_track[1:]) for c in a[1]) * FPS
    R['rates_deg_s'] = {'petals': round(pr, 2), 'head': round(hr, 2)}
    check('actuator_rates', pr <= 240.0 + 1e-6 and hr <= 120.0 + 1e-6,
          f'the fastest petal {pr:.1f} deg/s (its lead screw 240), the head\'s state {hr:.1f} deg/s (the neck 120)')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'crown_head_states.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        cam = S.C.camera('head', 85.0)
        shots = {}
        for st in STATES:
            fk = ends[st]
            sc.frame_set(fk)
            hd_ = arm.matrix_world @ arm.pose.bones[me.humanoid['head']].head
            tgt = hd_ + Vector((0.0, 0.0, 0.14))
            S.C.aim(cam, tgt + Vector((0.75, -1.45, 0.12)), tgt)
            p = os.path.join(S.OUT, f'crown_head_{st}_f{fk:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, cam, fk, p)
        R['renders'] = shots
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('crown_head_states.json', R)
log('done', R['ok'], R['seconds'], 's')
