"""seatOn for a VRM my robot body drives (robot_body.js: "Normally you call seatOn(vrm, chair, {transition}) which uses
[beginSeated] under the hood"; the engine finds the body in globalThis._vrmControllers): eidoblend.characters.emotes'
seat_on on a VRMRobotBody's VRM, through its own seated state.

    test_robot_seat.py [--tag NAME]

A floor and a chair; my robot body (claude_robot) stands a metre from it and its script, frame-stepped as the JS awaits
it: wait 0.5 s -> seat_on(vrm, chair, transition='stand_to_sit') -> wait 3 s -> stand_up('sit_to_stand') -> wait 2.5 s.

Prints PASS / FAIL: seat_on returns the pan's height; the body is placed at the spot seat_plan measured, facing out of
the chair (the engine moves the VRM there and syncs its capsule); its controller enters the seated state; the plan
(body.seat_plan) is kept for the bake: its lift curve starts at 0 and ends on the settle, never under the clamp; the
audits' exemption is set; the stationary path is not taken (no clip strips added on the armature). Then the run is baked
by the body's own bake (eidoblend.characters.robot) and the seated hips are measured over the seat: the bake places a
seated clip with its feet on the floor (it does not read body.seat_plan yet: a hook in robot/bake.py), so how far the
seated skin sits from the pan is reported, not judged. Stills: a strip of the sit.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _mnv_stage as T  # noqa: E402

import numpy as np  # noqa: E402

from eidoblend.characters import Ground, load_vrm  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402
from eidoblend.characters.robot import RobotRig, VRMRobotBody  # noqa: E402

ARGS = T.argv()
R = T.Report(T.arg(ARGS, '--tag', 'robot_seat_claude_robot'))
FPS = 30
CHAIR_XY, CHAIR_H = (0.0, 1.2), math.radians(180)       # the chair seats its sitter facing +Y (heading pi)


def main():
    sc = T.S.clean_scene(fps=FPS)
    floor = T.floor()
    chair = T.chair('chair', CHAIR_XY, CHAIR_H)
    T.scene_camera((2.6, 3.4, 1.5), (0.0, 1.4, 0.6))
    # she stands a metre in front of the chair's front, facing it (the scene walked her there)
    start = (0.0, 2.6)
    h0 = 0.0                                             # facing -Y: toward the chair
    me = load_vrm('claude_robot', name='claude', location=(start[0], start[1], 0.0), rotation=math.degrees(h0))
    body = VRMRobotBody.create(me, sc, {'collision_meshes': [floor],
                                        'motion': {'start_x': start[0], 'start_y': start[1], 'start_heading': h0,
                                                   'walk_speed': 0.9, 'agent_radius': 0.35}}, rig=RobotRig(me))
    nla0 = len(me.arm.animation_data.nla_tracks) if me.arm.animation_data else 0
    out = {}

    def script(b):
        yield b.wait(0.5)
        out['z'] = E.seat_on(me, chair, transition='stand_to_sit')
        out['t_seat'] = b._time_accum
        p = b.get_position()
        out['placed'] = (p['x'], p['y'], b.get_heading())
        out['seated_state'] = b.controller.get_state()
        out['seated_flag'] = bool(b.controller.char_ctrl._seated)
        yield b.wait(3.0)
        b.stand_up('sit_to_stand')
        yield b.wait(2.5)
    body.run(script(body))
    dt = 1.0 / FPS
    for k in range(FPS * 12):
        body.update(k * dt, dt)
        if body._script is None:
            break
    plan = getattr(body, 'seat_plan', None)
    R.check('seat_on returns the pan\'s height (0.45 m)', abs(out.get('z', -1) - 0.45) < 0.005, f"{out.get('z')}")
    R.check('the plan is kept on the body for its bake (body.seat_plan)', plan is not None,
            '' if plan is None else f"spot ({plan['spot'][0]:.3f}, {plan['spot'][1]:.3f}), heading "
                                    f"{math.degrees(plan['heading']):.1f} deg, settle {plan['settle'] * 100:+.1f} cm, "
                                    f"the back took the target {plan['push'] * 100:.1f} cm forward")
    if plan is None:
        return
    px, py, ph = out['placed']
    d = math.hypot(px - plan['spot'][0], py - plan['spot'][1])
    R.check('the body is placed at the measured spot, facing out of the chair (within 1 cm, 1 deg)',
            d < 0.01 and T.ang_deg(ph, plan['heading']) < 1.0 and T.ang_deg(ph, E.verbs._wrap_pi(CHAIR_H)) < 2.0,
            f'{d * 100:.2f} cm off, {T.ang_deg(ph, plan["heading"]):.2f} deg; the chair faces '
            f'{math.degrees(CHAIR_H):.0f} deg')
    R.check('its controller enters the seated state (beginSeated)', out.get('seated_flag') is True,
            f"seated {out.get('seated_flag')}, state '{out.get('seated_state')}'")
    lv = np.asarray(plan['lift_v'])
    R.check('the plan\'s lift starts at 0, ends on the settle and is smooth (no step over 1 cm a frame)',
            abs(lv[0]) < 1e-6 and abs(lv[-1] - plan['settle']) < 1e-6 and float(np.abs(np.diff(lv)).max()) < 0.01,
            f'{len(lv)} frames, the largest step {float(np.abs(np.diff(lv)).max()) * 1000:.1f} mm')
    R.check('the audits\' exemption is set (eido_seated)', bool(me.arm.get('eido_seated')), f"{me.arm.get('eido_seated')}")
    nla1 = len(me.arm.animation_data.nla_tracks) if me.arm.animation_data else 0
    R.check('the stationary path is not taken (no clip strips added on the armature)', nla1 == nla0,
            f'{nla0} -> {nla1} tracks')
    # the body's own bake
    t0 = time.time()
    rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * np.asarray(x)), action_name='claude|robot_seat')
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    f0, f1 = rep['frames']
    sc.frame_start, sc.frame_end = f0, f1
    fs = int(round((out['t_seat'] + 2.21 + 0.6) * FPS)) + 1        # seated, the sit-down done
    sc.frame_set(fs)
    hp = T.bone_world(me, 'hips')
    dxy = math.hypot(hp.x - plan['target'].x, hp.y - plan['target'].y)
    und = E.skin_lowest(me, E.pan_points(chair, plan['seat']), plan['seat']['z'] - 0.6, reach=1.2)
    gap = None if und is None else (und - plan['seat']['z']) * 100
    R['seated_after_bake'] = {'frame': fs, 'hips_to_target_cm': round(dxy * 100, 1),
                              'seat_skin_to_pan_cm': None if gap is None else round(gap, 1)}
    R.log(f"after the body's own bake (reported, not judged: robot/bake.py does not read body.seat_plan yet, and places "
          f'a seated clip where the feet stood before the seat): the seated hips {dxy * 100:.1f} cm from the target at '
          f'f{fs}, the seat skin {gap if gap is None else round(gap, 1)} cm from the pan')
    T.light(sc)
    S, sheets = [], {}
    names = []
    for k, f in enumerate(np.linspace(f0, f1, 8).astype(int)):
        nm = f'strip_robot_seat_{k}'
        S.append(T.fixed_shot(nm, int(f), (2.4, 1.0, 0.9), (0.0, 1.5, 0.6), lens=30))
        names.append(nm)
    sheets['strip_robot_seat'] = names
    for s in S:
        s['action'] = 'claude|robot_seat'
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
