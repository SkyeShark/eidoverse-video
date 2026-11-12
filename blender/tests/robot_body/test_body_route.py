"""My embodied robot walking and running its planned route on the full character controller (VRMRobotBody over the
controller family's VRMCharacterController, the engine's), down a hall it has never seen and into a room:

    play_gesture('cheer') -> walk_to(the room): a flight of stairs up and down, a low wall across the hall, a ditch
    across it (the planner may cross what the controller steps, vaults or jumps: planner max_step_height 1.15 m)
        stop_gesture() on the stairs' top
        vault() called 0.9 m before the wall, mid-stride: a move out of the walk
        the ditch: jumped by the controller on its own (its gap jump en route)
    run_to(a point behind a pillar in the room): the run's corners at the controller's turn rate -> look_at(the lamp)

    test_body_route.py [--vrm claude_robot | aletheia] [--no-render]

--vrm aletheia runs the same course on a VRM that is not my body (the JS drives any VRM through the engine's
controller). Checks (PASS / FAIL):
  - the walk arrives in the room, the run ends by its goal, the look resolves
  - stairs: the stair clips lead on the flights (stairsUp, stairsDown) and the probes read them (stairUp, stairDown)
  - the moves: the vault called mid-walk starts (True) and plays; the ditch's gap jump plays with no call; both in
    the bake's moves, the walk going on to its goal after each
  - the gesture: its weight is over 0.5 on the walk's frames before the stop, the legs walking under it
  - the run: the run clip leads the frames round the pillar; the heading turns at most the controller's
    max_turn_rate (3.5 rad/s) in any frame of the route, and the corner round the pillar is taken running
  - controller_opts reach the controller
  - feet: on every keyed frame no sole point goes more than 2 cm into the floor, the stairs, the wall or the ditch;
    the controller family's checks.feet per gait listed (its known residuals are its own)
  - sensing: each sense's origin, the head the live run sensed from, is my keyed head at that frame across (1 cm) and
    up by the plant's pelvis (the film's planted legs set it after the run); every sense cast again from my keyed head
    makes the same world: a memory within 5 % of its known cells of the live one, the route through it within 0.3 m
Stills: out/route_<vrm>_<moment>_f<k>.png (low side cameras); out/route_<vrm>.json, out/route_<vrm>.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_route.py --no-render
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_route.py
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotRig, VRMRobotBody  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
VRM = ARGS[ARGS.index('--vrm') + 1] if '--vrm' in ARGS else 'claude_robot'
FPS = 24
R = S.Report(f'route_{VRM}')
START, H0 = (-7.0, 0.0), math.pi / 2                 # facing +X, down the hall
UP_X, RUN, RISE, NSTEP = -5.0, 0.3, 0.15, 4          # the stairs up from x -5.0, a 0.6 m top, down after it
TOP0, TOP1 = UP_X + NSTEP * RUN, UP_X + NSTEP * RUN + 0.6
WALL = (0.6, 0.85, 0.8)                              # x0, x1, its top: low cover across the hall
DITCH = (3.0, 3.75, -0.7)                            # x0, x1, its floor
GOAL = (6.6, 0.0)                                    # in the room
PILLAR = (8.6, 9.2, 0.2, 0.8)
RUN_GOAL = (10.6, 1.4)
LAMP = (11.6, 2.6, 1.6)
HALL_Y = 2.0                                         # the hall 4 m wide: the stairs, the wall, the ditch span it


def hall():
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    block_m = S.textured('blocks_painted', 'PaintedWood009C_2k', 0.8)
    pit_m = S.textured('pit_floor', 'PaintedPlaster017_2k', 0.7, tint=(0.45, 0.44, 0.42, 1.0))
    solids = [S.box('floor_a', -8.5, DITCH[0], -4.0, 4.0, -1.0, 0.0, floor_m),
              S.box('floor_b', DITCH[1], 13.0, -4.0, 4.0, -1.0, 0.0, floor_m),
              S.box('ditch_floor', DITCH[0], DITCH[1], -4.0, 4.0, -1.0, DITCH[2], pit_m)]
    solids += [S.stairs('stairs_up', UP_X, RUN, RISE, NSTEP, -HALL_Y, HALL_Y, block_m),
               S.box('stairs_top', TOP0 - 0.01, TOP1, -HALL_Y, HALL_Y, 0.0, NSTEP * RISE, block_m),
               S.stairs('stairs_down', TOP1, RUN, RISE, NSTEP, -HALL_Y, HALL_Y, block_m, down=True)]
    solids.append(S.box('low_wall', WALL[0], WALL[1], -HALL_Y, HALL_Y, 0.0, WALL[2], block_m, 0.01))
    # the hall's walls to the room (x 5.5), then the room (y -4 .. 4) with a pillar
    H = 3.0
    solids += [S.box('hall_n', -8.5, 5.5, HALL_Y, HALL_Y + 0.1, -1.0, H, wall_m),
               S.box('hall_s', -8.5, 5.5, -HALL_Y - 0.1, -HALL_Y, -1.0, H, wall_m),
               S.box('hall_end', -8.6, -8.5, -HALL_Y, HALL_Y, -1.0, H, wall_m),
               S.box('room_n', 5.5, 13.0, 4.0, 4.1, -1.0, H, wall_m), S.box('room_s', 5.5, 13.0, -4.1, -4.0, -1.0, H, wall_m),
               S.box('room_e', 13.0, 13.1, -4.0, 4.0, -1.0, H, wall_m),
               S.box('room_w_n', 5.5, 5.6, HALL_Y, 4.0, -1.0, H, wall_m),
               S.box('room_w_s', 5.5, 5.6, -4.0, -HALL_Y, -1.0, H, wall_m),
               S.box('pillar', PILLAR[0], PILLAR[1], PILLAR[2], PILLAR[3], 0.0, H, wall_m)]
    lamp_m = bpy.data.materials.new('lamp_glow')
    lamp_m.use_nodes = True
    b = lamp_m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (1.0, 0.8, 0.5, 1.0)
    b.inputs['Emission Color'].default_value = (1.0, 0.75, 0.45, 1.0)
    b.inputs['Emission Strength'].default_value = 6.0
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=LAMP)
    lamp = bpy.context.object
    lamp.name = 'lamp'
    lamp.data.materials.append(lamp_m)
    return solids


def lights(sc):
    from eidoblend.characters.robot.example import directional, studio_environment
    studio_environment(sc, 0.4, None)
    for k, x in enumerate((-6.0, -2.0, 2.0, 6.0, 10.0)):
        S.area_light(sc, f'ceiling_{k}', (x, 0.0, 2.9), 500.0, 2.0)
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.6)


def main():
    sc = S.C.clean_scene(FPS)
    solids = hall()
    lights(sc)
    me = load_vrm(VRM, name='walker', location=(START[0], START[1], 0.0), rotation=math.degrees(H0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': solids,
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': H0, 'walk_speed': 0.9,
                   'run_speed': 2.6, 'agent_radius': 0.3},
        'memory': {'size': 24.0, 'origin_x': 2.5, 'cell_size': 0.1},
        'sensors': {'h_rays': 16, 'v_rays': 14, 'range': 6.0},
        'planner': {'agent_radius': 0.3, 'max_step_height': 1.15},
        'controller_opts': {'vault_max_rise': 1.1}}, rig=rig)
    legs = body.controller.char_ctrl
    out, marks = {}, {}

    def script(b):
        a = yield b.scan_area(yaw_range=60, duration=1.2)
        b.play_gesture('cheer')
        marks['walk'] = b.frame_count
        walk = b.walk_to(*GOAL)
        a = yield b.until(lambda: b.get_position()['x'] > TOP0 + 0.2 or walk.done)
        b.stop_gesture()
        marks['gesture_off'] = b.frame_count
        a = yield b.until(lambda: b.get_position()['x'] > WALL[0] - 0.9 or walk.done)
        marks['vault_call'] = b.frame_count
        out['vault_mid_walk'] = (b.vault(), b.controller.get_state())
        a = yield walk
        out['walk'] = (a.state, str(a.error) if a.error else None)
        marks['run'] = b.frame_count
        a = yield b.run_to(*RUN_GOAL)
        out['run'] = (a.state, str(a.error) if a.error else None)
        a = yield b.look_at(*LAMP)
        out['look'] = a.state
        a = yield b.wait(0.8)
    body.run(script(body))
    dt = 1.0 / FPS
    import time
    t0 = time.time()
    for k in range(FPS * 70):
        body.update(k * dt, dt)
        if body._script is None:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t0, 1), 'outcome': out, 'marks': marks,
                'log': [(round(t, 2), e) for t, e in body.log], 'maneuver_log': legs.maneuver_log,
                'controller_said': [s for s in legs.said if 'maneuver' in s[1] or 'vault' in s[1]][:20]}
    R.log('run', R['run'])
    t0 = time.time()
    rep = body.bake(face=lambda t: {'happy': 0.25}, action_name='walker|route')
    R['bake_s'] = round(time.time() - t0, 1)
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    frames, recs = rep['_frames'], rep['_records']
    sc.frame_start, sc.frame_end = rep['frames']
    f0 = rep['frames'][0]

    # ---- checks
    end = recs[-1]['feet_world']
    R.check('arrives', out.get('walk', ('',))[0] == 'resolved' and out.get('run', ('',))[0] == 'resolved'
            and math.hypot(end[0] - RUN_GOAL[0], end[1] - RUN_GOAL[1]) < 0.35 and out.get('look') == 'resolved',
            f'walk {out.get("walk")}, run {out.get("run")}, look {out.get("look")}; the body ends '
            f'{math.hypot(end[0] - RUN_GOAL[0], end[1] - RUN_GOAL[1]):.2f} m from the run\'s goal')
    leads = {}
    for r in recs:
        leads[r.get('lead')] = leads.get(r.get('lead'), 0) + 1
    modes = sorted(set(r.get('support_mode') or '-' for r in recs))
    R['leads'], R['support_modes'] = leads, modes
    R.check('the stairs walked on the stair clips', leads.get('stairsUp', 0) > 5 and leads.get('stairsDown', 0) > 5
            and {'stairUp', 'stairDown'} <= set(modes),
            f'frames led by stairsUp {leads.get("stairsUp", 0)}, stairsDown {leads.get("stairsDown", 0)}; probes {modes}')
    moves = rep['moves']
    called = out.get('vault_mid_walk', (None,))[0]
    vault_frames = [m for m in moves if m[0] == 'vault']
    jump_frames = [m for m in moves if m[0] in ('jump', 'gap_jump')]
    walk_after = vault_frames and any(r['mode'] == 'loco' and r.get('lead') == 'walk' for r in recs[vault_frames[0][2] - f0:])
    R.check('the moves: a vault out of the walk, the ditch jumped on its own', called is True and vault_frames and
            jump_frames and walk_after and out.get('walk', ('',))[0] == 'resolved',
            f'vault() mid-walk -> {out.get("vault_mid_walk")}; moves played {moves}; the walk on to its goal after them')
    gw = []
    a_, b_ = marks.get('walk', 0), marks.get('gesture_off', 0)
    for r in recs[a_ + FPS:b_ - 2]:
        gw.append((r.get('weights') or {}).get('cheer', 0.0))
    walking = sum(1 for r in recs[a_ + FPS:b_ - 2] if r['mode'] == 'loco' and r.get('lead') in ('walk', 'stairsUp'))
    R['gesture'] = {'frames': len(gw), 'weight_min': round(min(gw), 3) if gw else None, 'walking_frames': walking}
    R.check('the gesture over the walk', gw and min(gw) > 0.5 and walking > 0.8 * len(gw),
            f'the cheer\'s weight over {len(gw)} walking frames: at least {R["gesture"]["weight_min"]}; '
            f'{walking} of them walking or climbing')
    # the run: the run clip at the corner, the heading's rate
    rf = [r for r in recs[marks.get('run', 0):] if r['mode'] == 'loco']
    hd = [r['heading'] for r in recs]
    rate = [abs(math.remainder(hd[i + 1] - hd[i], 2 * math.pi)) * FPS for i in range(len(hd) - 1)
            if recs[i]['mode'] == 'loco' and recs[i + 1]['mode'] == 'loco']
    corner = [r for r in rf if math.hypot(r['feet_world'][0] - 0.5 * (PILLAR[0] + PILLAR[1]),
                                          r['feet_world'][1] - 0.5 * (PILLAR[2] + PILLAR[3])) < 1.6]
    run_lead = sum(1 for r in corner if r.get('lead') == 'run')
    turn_running = max((abs(math.remainder(corner[i + 1]['heading'] - corner[i]['heading'], 2 * math.pi)) * FPS
                        for i in range(len(corner) - 1) if corner[i].get('lead') == 'run'), default=0.0)
    R['run_turns'] = {'max_rate_rad_s': round(max(rate), 3) if rate else None, 'corner_frames': len(corner),
                      'run_led': run_lead, 'turning_while_running_rad_s': round(turn_running, 3)}
    R.check('the run turns at the controller\'s rate', rate and max(rate) <= 3.5 * 1.02 and corner and
            run_lead > 0.6 * len(corner) and turn_running > 0.5,
            f'{R["run_turns"]} (the controller\'s max_turn_rate 3.5 rad/s)')
    R.check('controller_opts reach the controller', abs(legs.ctrl.vault_max_rise - 1.1) < 1e-9,
            f'vault_max_rise {legs.ctrl.vault_max_rise}')
    bvh = S.solids_bvh(solids)
    deep = S.feet_in_solids(rig, frames, bvh)
    R['feet_in_solids'] = [round(1000 * deep[0], 1)] + list(deep[1:])
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    R.check('feet out of the solids', deep[0] < 0.02,
            f'the deepest sole point {R["feet_in_solids"]} (mm, frame, foot, mode); the controller family\'s checks.feet '
            f'fail on {len(fails)} of {len(rep["segments"])} gait segments: {[(f[0], f[1], f[2][:1]) for f in fails][:6]}')
    sh = S.sense_heads(body, rep)
    up_less_pelvis = max(abs(u - dz) for _a, u, dz, _f in sh)
    R['sense_head'] = {'senses': len(sh), 'across_max_m': round(sh[-1][0], 4), 'across_at': sh[-1][3],
                       'up_max_m': round(max(abs(u) for _a, u, _dz, _f in sh), 4),
                       'up_less_the_plant_pelvis_max_m': round(up_less_pelvis, 4)}
    R['head_live_vs_keyed_m'] = S.live_heads(rig, legs.ctrl.body, recs, frames)
    R.check('senses from my head where the take has it', sh and sh[-1][0] < 0.01 and up_less_pelvis < 0.01,
            f'{R["sense_head"]}: across within 1 cm, and up by the plant\'s pelvis (the film\'s planted legs set it '
            f'after the run); every frame\'s live head against the keyed one (median, 95th pct, max m: the '
            f'controller\'s pose before / after its foot IK, my torso rehomed): {R["head_live_vs_keyed_m"]}')
    # what the plant's pelvis (set after the run) does to what I know: every sense cast again from my keyed head
    rs_ = S.resense_keyed(body, rep, START, GOAL)
    R['resensed_from_keyed_head'] = rs_
    R.check('the world sensed from my keyed head is the one I sensed', rs_['differ_frac'] < 0.05
            and rs_['route_apart_m'] is not None and rs_['route_apart_m'] < 0.3,
            f'{rs_} (the senses cast again from my keyed head into a fresh memory, against the live senses the same way: '
            f'the cells they disagree on, the routes from the start to the room through each)')
    if '--dump' in ARGS:
        S.dump(R, recs, frames, [tuple(int(v) for v in s.split('-')) for s in ARGS[ARGS.index('--dump') + 1].split(',')])
    shots = shot_list(frames, recs, marks, moves, f0, bvh)
    S.write_json(f'route_{VRM}_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'route_{VRM}.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, f'route_{VRM}', shots)


def shot_list(frames, recs, marks, moves, f0, bvh):
    """a low side camera held over each moment (_stage.side_view), its frames every two or three: the flight up and
    the flight down (the stair clips' frames), the vault and the jump (the move and the steps either side), the run
    round the pillar -> [{'name', 'frame', 'cam', 'target', 'lens'}]"""
    spans = {}
    for g, nm in (('stairsUp', 'stairs_up'), ('stairsDown', 'stairs_down')):
        # the flight: the longest run of frames the stair clip leads (a stray frame elsewhere is not the flight)
        runs = []
        for i, r in enumerate(recs):
            if r.get('lead') == g:
                if runs and runs[-1][1] >= f0 + i - 3:
                    runs[-1][1] = f0 + i
                else:
                    runs.append([f0 + i, f0 + i])
        if runs:
            a, b = max(runs, key=lambda ab: ab[1] - ab[0])
            spans[nm] = (a - 6, b + 6)
    for m, a, b in moves:
        spans.setdefault(m, (a - 10, b + 10))
    pil = Vector((0.5 * (PILLAR[0] + PILLAR[1]), 0.5 * (PILLAR[2] + PILLAR[3]), 0.0))
    near = [f0 + i for i, r in enumerate(recs) if f0 + i > marks.get('run', 0)
            and (Vector(r['feet_world']) - pil).xy.length < 1.6]
    if near:
        spans['run_corner'] = (near[0] - 4, near[-1] + 4)
    out, last = [], f0 + len(frames) - 1
    for name, (a, b) in sorted(spans.items(), key=lambda kv: kv[1][0]):
        a, b = max(f0, a), min(last, b)
        out += S.strip(name, S.side_view(bvh, frames, f0, a, b), a, b, n=min(18, (b - a) // 2 + 1))
    return out


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
