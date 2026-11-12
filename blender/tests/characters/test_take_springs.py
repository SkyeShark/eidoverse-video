"""The spring chains ride the character controller's take (Locomotion.bake -> Locomotion.bake_springs), as three-vrm's
springs stepped inside vrm.update(dt) every frame the WebGPU engine rendered a controlled VRM:

    test_take_springs.py [--vrm aporia] [--tag NAME] [--no-render]

One take on a floor with a chair (eidoblend.characters.emotes on top of the controller): standing, a walk from
standing, a turn on the spot, a run that stops on its mark, seat_on(chair) with a hold and the stand-up, a lie-down on
the floor (sit_on_ground 'sit_laying_on_ground') and up, standing again.

Prints PASS / FAIL: the take keyed every spring joint over its frames on the springs' own track, nothing NaN, no reset
in a take whose root never jumps (and take_resets finds a jump put into its records); the controller's action keys no
spring bone and the keyed scene plays the spring track (a tail joint's evaluated rotation is its key); the chains swing
with the take (each group's tips move against the hips while the body walks, turns, runs, sits and lies down, and
settle within the last second of standing); lying down, no spring chain goes under the floor (the chains rest on the
take's walkable world), and seated, none goes into the chair (they stay out of the scene's solids). Stills
(render_shots.py): low side strips of the walk's start, the turn, the run's stop, the sit-down and the lie-down.
"""

import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'maneuvers')))
import _mnv_stage as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters import springs as SP  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.characters.controller.film import take_resets  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aporia')
NO_RENDER = '--no-render' in ARGS
R = T.Report(T.arg(ARGS, '--tag', f'take_springs_{VRM}'))
R['vrm'] = VRM
# the out/ folder of this test's own area (the maneuvers stage writes into its folder's otherwise)
T._C.OUT = T.S.OUT
T.OUT = T.S.OUT


def group_of(name):
    n = name.lower()
    if 'tail' in n:
        return 'tails'
    if 'hair' in n:
        return 'hair'
    if 'coat' in n or 'skirt' in n:
        return 'coat'
    return 'other'


def tips_rel(me, chains):
    """each chain's moving points (its joints' children) in the hips' frame, now: {spring: (n, 3)}"""
    arm = me.arm
    hp = arm.matrix_world @ arm.pose.bones[me.humanoid['hips']].matrix
    inv = hp.inverted()
    out = {}
    for s in chains:
        pts = [inv @ (arm.matrix_world @ arm.pose.bones[b].head) for b in s['points']]
        out[s['name']] = np.array([tuple(p) for p in pts])
    return out


def main():
    sc = T.S.clean_scene(fps=30)
    T.floor()
    chair = T.chair('chair_a', (2.6, 3.2), math.radians(-90))
    T.scene_camera((5.0, -1.0, 1.6), (1.0, 3.0, 0.7))
    me = load_vrm(VRM, name=VRM)
    seats = list(chair.children_recursive)
    loco = Locomotion(me, CollisionWorld(exclude=seats), start=(0.0, -3.0, 0.0), heading=math.pi, log=R.log)
    marks = {}

    def mark(name):
        def f(c):
            marks[name] = c.time
        return f
    loco.wait(1.0)
    loco.call(mark('walk'))
    loco.move_to((0.0, 0.5), gait='walk')
    loco.call(mark('turn'))
    loco.turn_by(-90)
    loco.call(mark('run'))
    loco.move_to((-5.0, 0.5), gait='run')
    loco.call(mark('stopped'))
    loco.wait(1.0)
    loco.call(mark('seat'))
    E.seat_on(loco, chair, hold=2.0)
    loco.call(mark('ground'))
    E.sit_on_ground(loco, clip='sit_laying_on_ground', at=(-1.0, 6.0), face=math.radians(-90), hold=2.0)
    loco.call(mark('end'))
    loco.wait(1.5)
    t0 = time.time()
    rep = E.bake(loco, f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    R['timing_s']['springs'] = rep.get('timing_s', {}).get('springs')
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    fps = 30.0
    fr_of = {k: f0 + int(round(t * fps)) for k, t in marks.items()}
    R['marks'] = fr_of
    R['segments'] = [(s['gait'], s['frames']) for s in rep['segments']]
    sp = rep.get('springs')
    rig = SP.SpringRig(me)
    n_joints = len(rig.joints)
    R.check('the take keyed the spring chains', sp is not None and sp['frames'] == [f0, f1] and sp['joints'] == n_joints
            and SP.spring_track(me) is not None,
            f"{sp and sp['joints']} of {n_joints} joints over frames {sp and sp['frames']} (the take {f0}-{f1}), "
            f"{sp and sp['keys']} keys on {sp and sp['track']}, {R['timing_s']['springs']} s")
    if sp is None:
        return
    R.check('no spring joint simulated to NaN', sp['nan'] == 0, f"{sp['nan']}")
    R.check('no reset in a take whose root never jumps', sp['resets'] == [] and take_resets(recs) == [],
            f"{sp['resets']}")
    fake = [dict(r) for r in recs[:40]]
    for r in fake[20:]:
        M = r['M'].copy()
        M.translation = M.translation + Vector((3.0, 0.0, 0.0))
        r['M'] = M
    R.check('take_resets finds a root that jumps 3 m', take_resets(fake) == [fake[20]['f']], f'{take_resets(fake)}')
    # the controller's action keys no spring bone; the keyed scene plays the spring track
    act = me.arm.animation_data.action
    bones = set(SP.spring_bones(me))
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(act, me.arm.animation_data.action_slot)
    on_spring = [fc.data_path for fc in cb.fcurves if any(f'["{b}"]' in fc.data_path for b in bones)]
    R.check("the take's action keys no spring bone", not on_spring, f'{on_spring[:3]}')
    trk = SP.spring_track(me)
    sact = trk.strips[0].action
    scb = anim_utils.action_get_channelbag_for_slot(sact, sact.slots[0])
    tail_j = next((j for j in rig.joints if group_of(j.spring) == 'tails'), rig.joints[0])
    fm = fr_of['run'] + 20
    sc.frame_set(fm)
    q_eval = me.arm.pose.bones[tail_j.bone].rotation_quaternion.copy()
    q_key = [scb.fcurves.find(f'pose.bones["{tail_j.bone}"].rotation_quaternion', index=i).evaluate(fm) for i in range(4)]
    err = max(abs(a - b) for a, b in zip(q_eval, q_key))
    R.check('the keyed scene plays the spring track', err < 1e-4, f'{tail_j.bone} at f{fm}: {err:.2e}')
    own = f"{rep['action']['name']}|springs"
    R.check("the take's springs are kept under the take's name (springs.use_springs puts them back)",
            sact.name == own and SP.use_springs(me, own) is not None and SP.spring_track(me).strips[0].action.name == own,
            f'{sact.name}')
    # the chains swing with the take: their moving points against the hips, frame by frame
    chains = []
    for s in rig.springs:
        if not s['joints']:
            continue
        pts = [j.child for j in rig.joints if j.spring == s['name']]
        chains.append({'name': s['name'], 'group': group_of(s['name']), 'points': pts})
    groups = sorted(set(c['group'] for c in chains))
    rel = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        rel[f] = tips_rel(me, chains)
    speed = {g: np.zeros(f1 - f0 + 1) for g in groups}
    for f in range(f0 + 1, f1 + 1):
        for c in chains:
            v = float(np.max(np.linalg.norm(rel[f][c['name']] - rel[f - 1][c['name']], axis=1))) * fps
            speed[c['group']][f - f0] = max(speed[c['group']][f - f0], v)
    phases = {'walk': (fr_of['walk'] + 3, fr_of['turn']), 'turn': (fr_of['turn'], fr_of['run']),
              'run': (fr_of['run'], fr_of['stopped'] + 10), 'seat': (fr_of['seat'], fr_of['ground']),
              'lie': (fr_of['ground'], fr_of['end'])}
    table = {}
    for g in groups:
        table[g] = {ph: round(float(np.mean(speed[g][a - f0:b - f0])), 3) for ph, (a, b) in phases.items()}
        table[g]['still_last_1s'] = round(float(np.max(speed[g][f1 - f0 - 29:])), 4)
    R['tip_speed_vs_hips_mps'] = table
    R['tip_speed_last_45_frames'] = {g: [round(float(v), 3) for v in speed[g][f1 - f0 - 44:]] for g in groups}
    for g in groups:
        moving = min(table[g][ph] for ph in ('walk', 'turn', 'run'))
        R.check(f'the {g} swing against the hips while she walks, turns and runs', moving > 0.02,
                f"mean tip speed against the hips {', '.join(f'{ph} {table[g][ph]:.3f}' for ph in phases)} m/s")
        # standing, the idle's own sway still moves a long tail a little: settled is a quarter of the walk's swing
        R.check(f'the {g} settle once she stands (the last second)',
                table[g]['still_last_1s'] < min(0.1, 0.25 * table[g]['walk']),
                f"the fastest tip moves {table[g]['still_last_1s']:.4f} m/s against the hips (the walk's mean "
                f"{table[g]['walk']:.3f})")
    # lying down: no spring chain under the floor
    a, b = fr_of['ground'], fr_of['end']
    low = (9.0, None, None)
    for f in range(a, b + 1, 2):
        sc.frame_set(f)
        arm = me.arm
        for c in chains:
            for bn in c['points']:
                z = (arm.matrix_world @ arm.pose.bones[bn].head).z
                if z < low[0]:
                    low = (z, f, c['name'])
    R['lowest_spring_point_lying'] = [round(low[0], 4), low[1], low[2]]
    R.check('lying down, no spring chain goes under the floor', low[0] > -0.01,
            f'the lowest moving point {low[0] * 100:+.1f} cm at f{low[1]} ({low[2][-24:] if low[2] else None})')
    # on the chair: no spring chain's moving point inside it (they stay out of the scene's solids)
    from eidoblend.characters.emotes.verbs import _chair_solid
    seat = rep['seated']['spans']
    if seat:
        parts = _chair_solid(chair)
        deep = (0.0, None, 0)
        for f in range(seat[0][0], seat[0][1] + 1, 2):
            sc.frame_set(f)
            arm = me.arm
            P = np.array([tuple(arm.matrix_world @ arm.pose.bones[bn].head) for c in chains for bn in c['points']])
            d, k = T.inside_depth(P, parts)
            if d > deep[0]:
                deep = (d, f, k)
        R.check('seated, no spring chain goes into the chair (under 1 cm)', deep[0] < 0.01,
                f'deepest {deep[0] * 1000:.1f} mm at f{deep[1]} ({deep[2]} points)')
    # stills: low side strips
    shots, sheets = [], {}
    T.light(sc)

    def strip(label, a, b, step, side=1.0, dist=3.2, height=0.1):
        T.strip(shots, sheets, me, recs, label, list(range(a, b + 1, step)), dist=dist, side=side, height=height)
    strip('walk_start', fr_of['walk'], fr_of['walk'] + 33, 3)
    strip('turn', fr_of['turn'] - 2, fr_of['run'] + 6, 3, side=-1.0)
    strip('run_stop', fr_of['stopped'] - 24, fr_of['stopped'] + 18, 3)
    if seat:
        strip('sit_down', seat[0][0] - 6, seat[0][0] + 42, 4, dist=3.4)
    if len(seat) > 1:
        strip('lie_down', seat[1][0] - 3, seat[1][0] + 45, 4, dist=3.6)
    T.save(R, sc, shots, sheets)
    R['render'] = 'skipped (--no-render)' if NO_RENDER else 'render_shots.py renders out/<tag>_shots.json'


try:
    main()
except Exception as e:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, f'{type(e).__name__}: {e}')
R.finish()
