"""The rest of my embodied robot's API, every method exercised: VRMRobotBody (robot_body.js), EidoverseRobotController
(robot_controller.js) on the controller family's legs: turns on the spot, an aimed emote, a run, a seat.

A room (7 x 5 m) with a pillar and, across its east end from wall to wall, a pane the sensors cannot see (hide_render:
no ray hits it) but the legs collide with, too tall for the controller to climb: the planner routes through it, the
legs stall on it (the controller's move-and-slide finds no way along it), the body replans once and then gives the walk
up, as the JS's collision stall does. The run to the far corner ends 0.4 m short of the pane: a wall past the goal
draws no move from the controller (its moves are for what lies on the route). The scene's direction, awaited action by
action:

    look_at(instant) -> look_forward -> look_at(the lamp, hold) -> face_direction(+90 deg) -> scan_area(2 passes)
    -> run_to(the far corner) -> set_emote_facing(the camera) + perform_action('salute', 2 s) -> walk_to_landmark
    ('stool') -> run_to_landmark('nowhere') [rejected] -> perform_action('no_such_clip') [rejected] -> face_direction
    (away from the stool) -> begin_seated('stand_to_sit') + 3 s -> stand_up('sit_to_stand') -> walk_to(behind the pane)
    [stalls, replans, rejected] -> walk_to + stop() [rejected 'stopped']

Every query is called and checked against the scene (observe, can_see, distance_to, path_to, get_head_direction,
get_head_position, is_blocked, get_landmarks, forget_landmark, get_map, get_current_action, is_moving, is_maneuvering,
set_running; the controller's set_walk_speed, set_run_speed, is_busy, get_state, is_stalled), then the run is baked
(the controller family's bake, my passes after it) and checked on the keyed result:
  - face_direction turns on the spot on the controller's turn clips and resolves facing its heading (within 2 deg),
    no planted sole point sliding over 2 mm a frame through the turns
  - the aimed salute faces the camera within 3 deg (more than 15 deg off my heading: I turn to it first, then salute)
  - the run: the run clip leads it, the controller family's checks.feet on its frames (a run's flight is its own)
  - no move plays: nothing here lies on a route (the run's goal is 0.4 m short of the pane it faces)
  - sitting (the JS's plain beginSeated: the seated clip where I stand, the root held; emotes.SeatOn's plain seat): the
    hips go down by more than 0.3 m and come back up; my feet on the floor through the hold (within 6 mm) and a foot on
    it at every frame from my hips leaving the seat (2 cm over their seated height) to the walk on; the stand-up clip
    carries my hips forward, never back (its hips' travel as root
    motion), and I stand up over the spot I sat down from (within 3 cm); a stool is put where the seated clip puts my
    hips (the scene's seat: test_body_seat.py sits through seatOn) and the test says so in its JSON
Stills: out/body_api_<moment>_<k>_f<frame>.png (low side cameras over the turns, the run, the sit and the stand; the
salute from its camera); out/body_api.json, out/body_api.blend.

    bash run_blender.sh blender/tests/robot_body/test_body_api.py --no-render
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
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
START = (-2.2, -1.2)
CORNER = (1.9, 1.5)
STOOL = (-1.6, 1.4)
LAMP = (-3.2, 2.2, 1.6)
CAM = (0.6, -2.3, 1.4)
BEHIND_PANE = (3.0, -1.6)
R = S.Report('body_api')


def heading_of_rec(fr):
    q = fr['M'].to_quaternion()
    return 2 * math.atan2(q.z, q.w)


def main():
    sc = S.C.clean_scene(FPS)
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    floor = S.box('floor', -3.5, 3.5, -2.5, 2.5, -0.05, 0.0, floor_m)
    H = 2.6
    walls = [S.box('wall_s', -3.6, 3.6, -2.6, -2.5, 0.0, H, wall_m), S.box('wall_n', -3.6, 3.6, 2.5, 2.6, 0.0, H, wall_m),
             S.box('wall_w', -3.6, -3.5, -2.5, 2.5, 0.0, H, wall_m), S.box('wall_e', 3.5, 3.6, -2.5, 2.5, 0.0, H, wall_m)]
    pillar = S.box('pillar', -0.25, 0.25, -0.25, 0.25, 0.0, H, wall_m, 0.01)
    # the pane: in the legs' world, not in the sensors' (hide_render: RobotSensors skips it); wall to wall (no sliding
    # round it) and taller than anything the controller climbs (its wall scramble goes up 4.5 m at most): a walk into it
    # stalls, as the test means it to
    pane = S.box('pane_unseen', 2.3, 2.34, -2.5, 2.5, 0.0, 5.0, wall_m)
    pane.hide_render = True
    lamp_m = bpy.data.materials.new('lamp_glow')
    lamp_m.use_nodes = True
    lb = lamp_m.node_tree.nodes['Principled BSDF']
    lb.inputs['Emission Color'].default_value = (1.0, 0.75, 0.45, 1.0)
    lb.inputs['Emission Strength'].default_value = 6.0
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=LAMP)
    lamp = bpy.context.object
    lamp.name = 'lamp'
    lamp.data.materials.append(lamp_m)
    from eidoblend.characters.robot.example import studio_environment
    studio_environment(sc, 0.35, None)
    S.area_light(sc, 'ceiling_w', (-1.8, 0.0, 2.45), 240.0, 1.2, (1.0, 0.93, 0.85))
    S.area_light(sc, 'ceiling_e', (1.8, 0.0, 2.45), 240.0, 1.2, (1.0, 0.93, 0.85))

    h0 = heading_of(CORNER[0] - START[0], CORNER[1] - START[1])
    me = load_vrm('claude_robot', name='claude', location=(START[0], START[1], 0.0), rotation=math.degrees(h0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + walls + [pillar, pane],
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': h0, 'walk_speed': 0.9, 'run_speed': 2.6,
                   'agent_radius': 0.35},
        'memory': {'size': 9.0, 'cell_size': 0.1},
        'sensors': {'h_rays': 16, 'v_rays': 12, 'range': 6.0}}, rig=rig)
    ctl = body.controller
    dbg = RobotDebug(body)
    dbg.show_path(True)
    api = {}

    # ---- the queries before anything moves
    api['collision_kinds'] = dict(ctl.char_ctrl.world.kinds)
    p0 = body.get_position()
    api['get_position'] = (round(p0['x'], 3), round(p0['y'], 3), round(p0['z'], 3))
    api['get_heading_deg'] = round(math.degrees(body.get_heading()), 2)
    hp = body.get_head_position()
    hd = body.get_head_direction()
    api['get_head_position'] = [round(c, 3) for c in hp]
    api['get_head_direction'] = [round(c, 3) for c in hd]
    api['distance_to'] = round(body.distance_to(*CORNER), 3)
    api['is_moving_0'] = body.is_moving()
    api['is_blocked_0'] = body.is_blocked()
    api['get_current_action_0'] = body.get_current_action()
    # (the moves, vault / jump / climb_ledge / climb_ladder, play on their course: test_body_maneuvers.py)
    api['is_maneuvering'] = body.is_maneuvering()
    body.set_running(False)
    ctl.set_walk_speed(0.9)
    ctl.set_run_speed(2.6)
    api['is_busy_0'] = ctl.is_busy()
    api['get_state_0'] = ctl.get_state()
    body.tag_landmark('stool', STOOL[0] + 0.1, STOOL[1] - 0.55)
    body.tag_landmark('scratch', 0.0, 0.0)
    body.forget_landmark('scratch')
    api['get_landmarks'] = [lm['name'] for lm in body.get_landmarks()]
    api['get_map_is_memory'] = body.get_map() is body.memory
    R.check('queries_at_rest',
            abs(p0['x'] - START[0]) < 1e-6 and abs(api['get_heading_deg'] - math.degrees(h0)) < 0.01 and hp.z > 1.4
            and abs(hd.length - 1) < 1e-6 and api['is_maneuvering'] is False and not api['is_moving_0']
            and api['get_landmarks'] == ['stool'] and api['get_map_is_memory'] and api['get_state_0'] == 'idle',
            f'{api}')

    outcome, marks = {}, {}

    def script(b):
        r = b.look_at(LAMP[0], LAMP[1], LAMP[2], instant=True)
        outcome['look_at_instant'] = (r.state, round(math.degrees(b._head_yaw_current), 1))
        b.look_forward()
        a = yield b.wait(0.8)
        a = yield b.look_at(*LAMP, hold=True)
        outcome['look_at_hold'] = (a.state, b._look_at_world_target is not None)
        a = yield b.wait(0.6)
        b.look_forward()
        marks['face_a'] = b.frame_count
        want = b.get_heading() + math.pi / 2
        a = yield b.face_direction(want)
        outcome['face_direction'] = (a.state, round(math.degrees(math.remainder(b.get_heading() - want, 2 * math.pi)), 2))
        a = yield b.wait(1.2)
        a = yield b.scan_area(yaw_range=80, duration=2.4, passes=2, center_yaw=0.2)
        outcome['scan_area'] = a.state
        marks['run_a'] = b.frame_count
        a = yield b.run_to(*CORNER)
        outcome['run_to'] = (a.state, str(a.error) if a.error else None)
        marks['run_b'] = b.frame_count
        cam_heading = heading_of(CAM[0] - b.get_position()['x'], CAM[1] - b.get_position()['y'])
        b.set_emote_facing(cam_heading)
        marks['salute_a'] = b.frame_count
        a = yield b.perform_action('salute', 2.0)
        outcome['salute'] = a.state
        marks['salute_b'] = b.frame_count
        outcome['salute_facing_deg'] = round(math.degrees(cam_heading), 1)
        b.set_emote_facing(None)
        a = yield b.wait(1.0)
        a = yield b.walk_to_landmark('stool')
        outcome['walk_to_landmark'] = (a.state, str(a.error) if a.error else None)
        a = yield b.run_to_landmark('nowhere')
        outcome['run_to_landmark_unknown'] = (a.state, str(a.error))
        a = yield b.perform_action('no_such_clip')
        outcome['perform_unknown'] = (a.state, str(a.error))
        marks['sit_turn'] = b.frame_count
        a = yield b.face_direction(0.0)                  # facing -Y: the stool goes behind, where the clip sits me
        outcome['face_direction_2'] = (a.state, round(math.degrees(b.get_heading()), 2))
        a = yield b.wait(0.6)
        marks['sit_a'] = b.frame_count
        outcome['begin_seated'] = b.begin_seated('stand_to_sit')
        outcome['state_seated'] = (b.controller.get_state(), b.get_current_action())
        a = yield b.wait(3.0)
        marks['stand_a'] = b.frame_count
        b.stand_up('sit_to_stand')
        a = yield b.until(lambda: b.controller.get_state() != 'performing')
        marks['stand_b'] = b.frame_count
        # the stall: the planner routes through the pane it never saw; the legs meet it
        marks['stall_a'] = b.frame_count
        a = yield b.walk_to(*BEHIND_PANE)
        outcome['walk_to_stall'] = (a.state, str(a.error) if a.error else None, b.is_blocked())
        marks['stall_b'] = b.frame_count
        a = yield b.wait(0.6)
        w = b.walk_to(0.9, -1.4)
        outcome['moving_after_walk_to'] = (b.is_moving(), b.get_current_action())
        a = yield b.wait(0.8)
        b.stop()
        outcome['stop'] = (w.state, str(w.error), b.controller.get_state())
        a = yield b.wait(1.0)

    body.run(script(body))
    dt = 1.0 / FPS
    t_sim = time.time()
    for k in range(FPS * 90):
        body.update(k * dt, dt)
        dbg.update()
        if body._script is None:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t_sim, 2),
                'outcome': outcome, 'marks': marks, 'log': [(round(t, 2), e) for t, e in body.log]}
    R.log('run', R['run'])
    # ---- the queries after the run
    obs = body.observe()
    api['observe_hits'] = (obs['hit_count'], obs['count']) if obs else None
    hp = body.get_head_position()
    fw = body.get_head_direction()
    api['can_see_ahead'] = body.can_see(*(hp + fw * 0.6))
    api['can_see_behind'] = body.can_see(*(hp - fw * 0.6))
    pth = body.path_to(*CORNER)
    api['path_to_corner'] = None if pth is None else len(pth)
    api['path_to_outside'] = body.path_to(9.0, 9.0)
    R.check('queries_after', api['can_see_ahead'] is True and api['can_see_behind'] is False
            and api['path_to_corner'] and api['path_to_outside'] is None and api['observe_hits'] is not None,
            f'observe {api["observe_hits"]}, can_see ahead {api["can_see_ahead"]} / behind {api["can_see_behind"]}, '
            f'path_to the corner {api["path_to_corner"]} waypoints, outside the map {api["path_to_outside"]}')
    R.check('actions_resolve_as_the_js',
            outcome.get('look_at_instant', ('',))[0] == 'resolved' and outcome.get('look_at_hold') == ('resolved', True)
            and outcome.get('face_direction', ('',))[0] == 'resolved' and abs(outcome['face_direction'][1]) < 2.0
            and outcome.get('scan_area') == 'resolved'
            and outcome.get('run_to', ('',))[0] == 'resolved' and outcome.get('salute') == 'resolved'
            and outcome.get('walk_to_landmark', ('',))[0] == 'resolved'
            and outcome.get('run_to_landmark_unknown', ('',))[0] == 'rejected'
            and 'unknown landmark: nowhere' in outcome.get('run_to_landmark_unknown', ('', ''))[1]
            and outcome.get('perform_unknown', ('',))[0] == 'rejected'
            and 'unknown clip' in outcome.get('perform_unknown', ('', ''))[1]
            and outcome.get('state_seated', ('',))[0] == 'seated',
            f'{outcome}')
    st = outcome.get('walk_to_stall', ('', ''))
    R.check('collision_stall_rejects', st[0] == 'rejected' and 'blocked: collision stall' in (st[1] or ''),
            f'walk_to behind the pane the sensors cannot see: {st}; the log: '
            f'{[e for t, e in body.log if "stall" in e or "replan" in e][-4:]}')
    sp = outcome.get('stop', ('', ''))
    R.check('stop_rejects_stopped', sp[0] == 'rejected' and 'stopped' in sp[1] and sp[2] == 'idle', f'{sp}')

    # ---- the bake
    t_b = time.time()
    rep = body.bake(face=lambda t: {'relaxed': 0.3}, action_name='claude|body_api')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    R['bake_s'] = round(time.time() - t_b, 1)
    sc.frame_start, sc.frame_end = rep['frames']
    frames = rep['_frames']
    f0 = rep['frames'][0]
    # the turns on the spot: the turn clips, planted feet, the heading reached
    turn_frames = {fr['f'] for fr in frames if fr['mode'] == 'turn'}
    slide = S.feet_slide(rig, frames, lambda fr: fr['f'] in turn_frames)
    R['turns'] = {'slide_mm': slide, 'turns': rep['turns']}
    R.check('turns_step_on_planted_feet', len(rep['turns']) >= 3 and all(v[0] <= 2.0 for v in slide.values()),
            f'{len(rep["turns"])} turns on the spot (first, last frame, deg): {rep["turns"]}; the least-moving sole point '
            f'in contact moves at most {slide} (mm, film frame) a frame through them')
    # the aimed salute
    salute = [fr for fr in frames if fr['mode'] == 'emote' and fr['lead'] == 'salute']
    if salute:
        mid = salute[len(salute) // 2]
        err = math.degrees(math.remainder(heading_of_rec(mid) - math.radians(outcome['salute_facing_deg']), 2 * math.pi))
        R['salute'] = {'frames': [salute[0]['f'], salute[-1]['f']], 'mid_heading_err_deg': round(err, 2),
                       'turned_first': any(a <= salute[0]['f'] <= b + 3 for a, b, _d in rep['turns'])}
        R.check('aimed_emote', abs(err) < 3.0, f'{R["salute"]} (aimed at {outcome["salute_facing_deg"]} deg)')
    else:
        R.check('aimed_emote', False, 'no salute frames in the bake')
    # the run: the run clip leads it; the controller family's checks.feet on it
    segs = rep['segments']
    runs = [s for s in segs if s['gait'] == 'run']
    R['run_segments'] = [(s['frames'], s['checks_feet']['ok'], s['checks_feet']['failures'][:2], s.get('waived'))
                         for s in runs]
    R.check('the run', runs and sum(s['frames'][1] - s['frames'][0] + 1 for s in runs) > FPS
            and all(s['checks_feet']['ok'] for s in runs), f'{R["run_segments"]}')
    # the controller's own moves are for what lies on a route: nothing here is (the corner's goal is 0.4 m short of the
    # pane, the walks end in the open), so none plays
    R.check('no move for a wall past the goal', not rep['moves'],
            f'moves played {rep["moves"]} (the run ends {abs(2.3 - CORNER[0]):.1f} m short of the pane it faces)')
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    R.log('the controller family\'s checks.feet failures:', fails)
    # sitting: the hips go down and back up; a stool goes under them (the scene's seat). The plain seat is emotes.SeatOn's
    # (chair=None): its frames are the seat window's ('seat' once the bake hands them over)
    seated = [fr for fr in frames if fr['mode'] in ('seat', 'seated')]
    hz = [(fr['f'], rig.bone_world(fr, 'hips')[0]) for fr in frames]
    z_stand = hz[0][1].z
    if seated:
        f_low = min(seated, key=lambda fr: rig.bone_world(fr, 'hips')[0].z)
        p_low, _W = rig.bone_world(f_low, 'hips')
        by_f = {fr['f']: fr for fr in frames}
        low = {fr['f']: {s: float(P[:, 2].min()) for s, P in rig.feet_world(fr).items()} for fr in frames}
        hold = [f for f in range(marks['sit_a'] + int(2.4 * FPS), marks['stand_a']) if f in by_f]
        feet = [v for f in hold for v in low[f].values()]
        # the rise: from my hips leaving the seat (2 cm over their seated height as the stand-up starts; the stand-up
        # clip shuffles both feet while they are still on it) to the walk on
        z_seat = rig.bone_world(by_f[marks['stand_a']], 'hips')[0].z if marks['stand_a'] in by_f else 9.9
        up_f = next((f for f in range(marks['stand_a'], marks['stand_b'] + 1)
                     if f in by_f and rig.bone_world(by_f[f], 'hips')[0].z > z_seat + 0.02), marks['stand_b'])
        rise = [f for f in range(up_f, marks['stand_b'] + FPS // 2) if f in by_f]
        neither = [f for f in rise if min(low[f].values()) > 0.006]
        R['sit'] = {'frames': [seated[0]['f'], seated[-1]['f']], 'hips_drop_m': round(z_stand - p_low.z, 3),
                    'hips_at': [round(c, 3) for c in p_low],
                    'feet_lowest_mm_held': [round(1000 * min(feet), 1), round(1000 * max(feet), 1)] if feet else None,
                    'frames_neither_foot_down_rising': len(neither)}
        R.check('sits_and_stands', z_stand - p_low.z > 0.3 and hz[-1][1].z > z_stand - 0.05, f'{R["sit"]}; hips at the '
                f'end {hz[-1][1].z:.3f} m against {z_stand:.3f} m standing')
        R.check('the plain seat: my feet on the floor while seated (each foot\'s lowest sole point within 6 mm)',
                feet and max(abs(v) for v in feet) < 0.006, f'{R["sit"]["feet_lowest_mm_held"]} mm over {len(hold)} '
                f'frames of the hold')
        R.check('the plain seat: a foot on the floor at every frame from my hips leaving the seat to the walk on',
                rise and not neither, f'{len(neither)} of {len(rise)} frames (from f{up_f}) with neither foot within 6 mm '
                f'of the floor: {neither[:8]}')
        # the stand-up clip's hips' travel taken as root motion: forward with the clip, never back, over the spot
        up = [f for f in range(marks['stand_a'], marks['stand_b'] + 1) if f in by_f]
        hxy = {f: rig.bone_world(by_f[f], 'hips')[0].xy.copy() for f in up}
        h_sit = heading_of_rec(by_f[marks['sit_a']]) if marks['sit_a'] in by_f else 0.0
        fwd = Vector((math.sin(h_sit), -math.cos(h_sit)))
        steps = [hxy[f] - hxy[f - 1] for f in up[1:]]
        big = max((d.length for d in steps), default=9.9)
        back = max((-d.dot(fwd) for d in steps), default=9.9)
        p0 = rig.bone_world(by_f[marks['sit_a']], 'hips')[0].xy if marks['sit_a'] in by_f else None
        end = (hxy[up[-1]] - p0).length if p0 is not None and up else 9.9
        R['stand'] = {'step_max_cm': round(big * 100, 2), 'back_max_cm': round(back * 100, 2),
                      'end_from_sit_spot_cm': round(end * 100, 2)}
        R.check('the plain seat: the stand-up clip carries my hips forward, never back (at most 2.5 cm a frame, none '
                'over 0.5 cm back)', big < 0.025 and back < 0.005, f'{R["stand"]}')
        R.check('the plain seat: I stand up over the spot I sat down from (the hips within 3 cm)', end < 0.03,
                f'{R["stand"]}')
        seat_top = p_low.z - 0.09
        fwd = f_low['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))
        c = p_low - fwd * 0.02
        stool_m = S.textured('stool_wood', 'Wood066_1k', 1.4)
        S.box('stool_seat', c.x - 0.2, c.x + 0.2, c.y - 0.2, c.y + 0.2, seat_top - 0.04, seat_top, stool_m, 0.006)
        for dx in (-0.17, 0.17):
            for dy in (-0.17, 0.17):
                S.box('stool_leg', c.x + dx - 0.02, c.x + dx + 0.02, c.y + dy - 0.02, c.y + dy + 0.02, 0.0,
                      seat_top - 0.04, stool_m)
        R['stool'] = {'placed_under_the_hips': True, 'top_m': round(seat_top, 3), 'centre': [round(c.x, 3), round(c.y, 3)]}
    else:
        R.check('sits_and_stands', False, 'no seated frames in the bake')
    objs = dbg.build(rep)
    R['debug_objects'] = {k: (o.name if o else None) for k, o in objs.items()}
    R['api'] = {k: (v if not isinstance(v, Vector) else list(v)) for k, v in api.items()}
    # the stills: a low side camera held over each turn on the spot, the run, the sit-down and the stand-up, every two
    # or three frames (the path overlay left out); the salute from the camera it is aimed at
    vbvh = S.solids_bvh(walls + [pillar])
    hide = [n for n in R['debug_objects'].values() if n]
    shots, last = [], f0 + len(frames) - 1
    spans = [(f'turn{k + 1}', a - 3, b + 3) for k, (a, b, _d) in enumerate(rep['turns'][:4])]
    rf = [fr['f'] for fr in frames if fr['lead'] == 'run']
    if rf:
        spans.append(('run', rf[0] - 6, rf[-1] + 10))
    if seated:
        spans += [('sit', seated[0]['f'] - 6, seated[0]['f'] + int(2.4 * FPS)),
                  ('stand', marks.get('stand_a', seated[-1]['f']) - 4, marks.get('stand_b', seated[-1]['f']) + 24)]
    for name, a_, b_ in spans:
        a_, b_ = max(f0, a_), min(last, b_)
        shots += [dict(s, hide=hide) for s in S.strip(name, S.side_view(vbvh, frames, f0, a_, b_), a_, b_,
                                                       n=min(18, (b_ - a_) // 2 + 1))]
    if salute:
        aim = salute[len(salute) // 2]['M'].translation + Vector((0, 0, 1.0))
        for k, f in enumerate((salute[0]['f'] - 20, salute[0]['f'], salute[len(salute) // 2]['f'], salute[-1]['f'] + 20)):
            shots.append({'name': f'salute_{k}', 'frame': int(f), 'cam': list(CAM), 'target': list(aim), 'lens': 35.0,
                          'hide': hide})
    S.write_json('body_api_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'body_api.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'body_api', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
