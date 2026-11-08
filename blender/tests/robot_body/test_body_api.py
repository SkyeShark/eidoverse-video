"""The rest of my embodied robot's API, every method exercised: VRMRobotBody (robot_body.js), EidoverseRobotController
(robot_controller.js) and the bake's standing turns, aimed emotes, running and sitting.

A room (7 x 5 m) with a pillar, a stool and, across the east side, a pane the sensors cannot see (hide_render: no ray
hits it) but the legs collide with: the planner routes through it, the legs stall on it, the body replans once and then
gives the walk up, as the JS's collision stall does. The scene's direction, awaited action by action:

    look_at(instant) -> look_forward -> look_at(the lamp, hold) -> face_direction(+90 deg) -> scan_area(2 passes)
    -> run_to(the far corner) -> set_emote_facing(the camera) + perform_action('salute', 2 s) -> walk_to_landmark
    ('stool') -> run_to_landmark('nowhere') [rejected] -> perform_action('no_such_clip') [rejected] -> face_direction
    (away from the stool) -> begin_seated('stand_to_sit') + 3 s -> stand_up('sit_to_stand') -> walk_to(behind the pane)
    [stalls, replans, rejected] -> walk_to + stop() [rejected 'stopped']

Every query is called and checked against the scene (observe, can_see, distance_to, path_to, get_head_direction,
get_head_position, is_blocked, get_landmarks, forget_landmark, get_map, get_current_action, is_moving, is_maneuvering,
vault / jump / climb_ledge / climb_ladder, set_running; the controller's set_walk_speed, set_run_speed, is_busy,
get_state, is_stalled), then the run is baked and checked on the keyed result:
  - the standing turns step round on planted feet (no sole point in contact slides over 2 mm a frame) and end at
    their heading
  - the aimed salute faces the camera within 3 deg, and the body is back on its own heading after it
  - the run (round one's walk_path on the run clip): its report
  - sitting: the hips go down by more than 0.3 m and come back up
The stool is placed under where the seated clip puts my hips (as the WebGPU engine's seatOn places the body on a seat;
seatOn itself is not part of this port): the test says so in its JSON.
Stills: out/body_api_<moment>_f<k>.png; out/body_api.json, out/body_api.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_api.py [--no-render]
"""

import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import Ground, load_vrm  # noqa: E402
from eidoblend.characters.robot import Pending, RobotDebug, RobotRig, VRMRobotBody  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
START = (-2.2, -1.2)
CORNER = (1.9, 1.5)
STOOL = (-1.6, 1.4)
LAMP = (-3.2, 2.2, 1.6)
CAM = (0.6, -3.0, 1.4)
BEHIND_PANE = (3.0, -1.6)
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True


def log(*a):
    print('[body_api]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def mat(name, tex, scale=1.0, tint=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    ts = S.C.texture_set(tex)
    if not ts:
        b.inputs['Base Color'].default_value = tint or (0.5, 0.5, 0.5, 1.0)
        return m
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    for role, colour in (('color', True), ('rough', False), ('normal', False)):
        if not ts.get(role):
            continue
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(ts[role], check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
        n.projection = 'BOX'
        n.projection_blend = 0.2
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        if role == 'color':
            if tint:
                mx = nt.nodes.new('ShaderNodeMix')
                mx.data_type, mx.blend_type = 'RGBA', 'MULTIPLY'
                mx.inputs['Factor'].default_value = 1.0
                nt.links.new(n.outputs['Color'], mx.inputs['A'])
                mx.inputs['B'].default_value = tint
                nt.links.new(mx.outputs['Result'], b.inputs['Base Color'])
            else:
                nt.links.new(n.outputs['Color'], b.inputs['Base Color'])
        elif role == 'rough':
            nt.links.new(n.outputs['Color'], b.inputs['Roughness'])
        else:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(n.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m


def box(name, x0, x1, y0, y1, z0, z1, m, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(m)
    return ob


def feet_slide(rig, frames, sel):
    """over the frames `sel` picks: per side, the largest move of the least-moving sole point in contact (2.5 mm) two
    frames running, mm"""
    out = {}
    for s in ('left', 'right'):
        prev = None
        worst = (0.0, None)
        for fr in frames:
            P = rig.feet_world(fr)[s]
            low = P[:, 2] < 0.0025
            if sel(fr) and prev is not None and prev[1].any() and low.any():
                both = low & prev[1]
                if both.any():
                    d = float(np.min(np.linalg.norm(P[both, :2] - prev[0][both, :2], axis=1)))
                    if d > worst[0]:
                        worst = (d, fr['f'])
            prev = (P, low)
        out[s] = (round(1000 * worst[0], 3), worst[1])
    return out


def heading_of_rec(fr):
    q = fr['M'].to_quaternion()
    return 2 * math.atan2(q.z, q.w)


try:
    sc = S.C.clean_scene(FPS)
    floor_m = mat('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = mat('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    floor = box('floor', -3.5, 3.5, -2.5, 2.5, -0.05, 0.0, floor_m)
    H = 2.6
    walls = [box('wall_s', -3.6, 3.6, -2.6, -2.5, 0.0, H, wall_m), box('wall_n', -3.6, 3.6, 2.5, 2.6, 0.0, H, wall_m),
             box('wall_w', -3.6, -3.5, -2.5, 2.5, 0.0, H, wall_m), box('wall_e', 3.5, 3.6, -2.5, 2.5, 0.0, H, wall_m)]
    pillar = box('pillar', -0.25, 0.25, -0.25, 0.25, 0.0, H, wall_m, 0.01)
    # the pane: in the legs' world, not in the sensors' (hide_render: RobotSensors skips it)
    pane = box('pane_unseen', 2.3, 2.34, -2.5, -0.6, 0.0, 2.0, wall_m)
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
    for name, loc, energy in (('ceiling_w', (-1.8, 0.0, 2.45), 240.0), ('ceiling_e', (1.8, 0.0, 2.45), 240.0)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy, ld.size, ld.color = energy, 1.2, (1.0, 0.93, 0.85)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)

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
    api['vault'], api['jump'], api['climb_ledge'], api['climb_ladder'] = (body.vault(), body.jump({'distance': 1.0}),
                                                                          body.climb_ledge(), body.climb_ladder())
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
    check('queries_at_rest',
          abs(p0['x'] - START[0]) < 1e-6 and abs(api['get_heading_deg'] - math.degrees(h0)) < 0.01 and hp.z > 1.4
          and abs(hd.length - 1) < 1e-6 and api['vault'] is False and api['jump'] is False and not api['is_moving_0']
          and api['get_landmarks'] == ['stool'] and api['get_map_is_memory'] and api['get_state_0'] == 'idle',
          f'{api}')

    outcome, marks = {}, {}

    def wait(b, seconds):
        p = Pending('waiting')
        p.until = b._time_accum + seconds
        waits.append(p)
        return p
    waits = []

    def script(b):
        r = b.look_at(LAMP[0], LAMP[1], LAMP[2], instant=True)
        outcome['look_at_instant'] = (r.state, round(math.degrees(b._head_yaw_current), 1))
        b.look_forward()
        a = yield wait(b, 0.8)
        a = yield b.look_at(*LAMP, hold=True)
        outcome['look_at_hold'] = (a.state, b._look_at_world_target is not None)
        a = yield wait(b, 0.6)
        b.look_forward()
        marks['face_a'] = b.frame_count
        a = yield b.face_direction(b.get_heading() + math.pi / 2)
        outcome['face_direction'] = (a.state, round(math.degrees(b.get_heading()), 1))
        a = yield wait(b, 1.2)
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
        a = yield wait(b, 1.0)
        a = yield b.walk_to_landmark('stool')
        outcome['walk_to_landmark'] = (a.state, str(a.error) if a.error else None)
        a = yield b.run_to_landmark('nowhere')
        outcome['run_to_landmark_unknown'] = (a.state, str(a.error))
        a = yield b.perform_action('no_such_clip')
        outcome['perform_unknown'] = (a.state, str(a.error))
        marks['sit_turn'] = b.frame_count
        a = yield b.face_direction(0.0)                  # facing -Y: the stool goes behind, where the clip sits me
        a = yield wait(b, 1.2)
        marks['sit_a'] = b.frame_count
        outcome['begin_seated'] = b.begin_seated('stand_to_sit')
        outcome['state_seated'] = (b.controller.get_state(), b.get_current_action())
        a = yield wait(b, 3.0)
        marks['stand_a'] = b.frame_count
        b.stand_up('sit_to_stand')
        a = yield wait(b, 2.4)
        marks['stand_b'] = b.frame_count
        # the stall: the planner routes through the pane it never saw; the legs meet it
        marks['stall_a'] = b.frame_count
        a = yield b.walk_to(*BEHIND_PANE)
        outcome['walk_to_stall'] = (a.state, str(a.error) if a.error else None, b.is_blocked())
        marks['stall_b'] = b.frame_count
        a = yield wait(b, 0.6)
        w = b.walk_to(0.9, -1.4)
        outcome['moving_after_walk_to'] = (b.is_moving(), b.get_current_action())
        a = yield wait(b, 0.8)
        b.stop()
        outcome['stop'] = (w.state, str(w.error), b.controller.get_state())
        a = yield wait(b, 1.0)

    body.run(script(body))
    dt = 1.0 / FPS
    t_sim = time.time()
    f_done = None
    for k in range(FPS * 90):
        t = k * dt
        for p in list(waits):
            if t >= p.until:
                waits.remove(p)
                p.resolve()
        body.update(t, dt)
        dbg.update()
        if body._script is None and f_done is None:
            f_done = k
        if f_done is not None:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t_sim, 2),
                'outcome': outcome, 'marks': marks, 'log': [(round(t, 2), e) for t, e in body.log]}
    log('run', R['run'])
    # ---- the queries after the run
    pos = body.get_position()
    obs = body.observe()
    api['observe_hits'] = (obs['hit_count'], obs['count']) if obs else None
    hp = body.get_head_position()
    fw = body.get_head_direction()
    api['can_see_ahead'] = body.can_see(*(hp + fw * 1.5))
    api['can_see_behind'] = body.can_see(*(hp - fw * 1.5))
    api['can_see_through_pillar'] = None
    pth = body.path_to(*CORNER)
    api['path_to_corner'] = None if pth is None else len(pth)
    api['path_to_outside'] = body.path_to(9.0, 9.0)
    check('queries_after', api['can_see_ahead'] is True and api['can_see_behind'] is False
          and api['path_to_corner'] and api['path_to_outside'] is None and api['observe_hits'] is not None,
          f'observe {api["observe_hits"]}, can_see ahead {api["can_see_ahead"]} / behind {api["can_see_behind"]}, '
          f'path_to the corner {api["path_to_corner"]} waypoints, outside the map {api["path_to_outside"]}')
    check('actions_resolve_as_the_js',
          outcome.get('look_at_instant', ('',))[0] == 'resolved' and outcome.get('look_at_hold') == ('resolved', True)
          and outcome.get('face_direction', ('',))[0] == 'resolved' and outcome.get('scan_area') == 'resolved'
          and outcome.get('run_to', ('',))[0] == 'resolved' and outcome.get('salute') == 'resolved'
          and outcome.get('walk_to_landmark', ('',))[0] == 'resolved'
          and outcome.get('run_to_landmark_unknown', ('',))[0] == 'rejected'
          and 'unknown landmark: nowhere' in outcome.get('run_to_landmark_unknown', ('', ''))[1]
          and outcome.get('perform_unknown', ('',))[0] == 'rejected'
          and 'unknown clip' in outcome.get('perform_unknown', ('', ''))[1]
          and outcome.get('state_seated', ('',))[0] == 'seated',
          f'{outcome}')
    st = outcome.get('walk_to_stall', ('', ''))
    check('collision_stall_rejects', st[0] == 'rejected' and 'blocked: collision stall' in (st[1] or ''),
          f'walk_to behind the pane the sensors cannot see: {st}; the log: '
          f'{[e for t, e in body.log if "stall" in e or "replan" in e][-4:]}')
    sp = outcome.get('stop', ('', ''))
    check('stop_rejects_stopped', sp[0] == 'rejected' and 'stopped' in sp[1] and sp[2] == 'idle', f'{sp}')

    # ---- the bake
    t_b = time.time()
    rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * np.asarray(x)), face=lambda t: {'relaxed': 0.3},
                    action_name='claude|body_api')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'walks')}
    R['bake_walks'] = [{k: v for k, v in w.items() if k in ('worst', 'stop', 'start', 'speed', 'path_m', 'stances')}
                       for w in rep['walks']]
    R['bake_s'] = round(time.time() - t_b, 1)
    sc.frame_start, sc.frame_end = rep['frames']
    frames = rep['_frames']
    film_of = {}
    for j, i in enumerate(rep['map']):
        film_of.setdefault(i, rep['frames'][0] + j)

    def film(run_frame):
        i = run_frame - 1
        while i not in film_of and i > 0:
            i -= 1
        return film_of.get(i, 1)
    # the standing turns: planted feet, and the heading reached
    turn_frames = {fr['f'] for fr in frames if fr['src'][2] == 'turn'}
    slide = feet_slide(rig, frames, lambda fr: fr['f'] in turn_frames)
    ends = []
    for tn in rep['turns']:
        f_end = tn['frame'] + tn['frames'] - 1
        ends.append((tn['frame'], tn['deg'], round(math.degrees(heading_of_rec(frames[f_end - 1])), 1)))
    R['turns'] = {'slide_mm': slide, 'turns': rep['turns'], 'end_headings': ends}
    worst_f = max(slide.values())[1]
    if worst_f:
        diag = []
        for fr in frames[max(0, worst_f - 7):worst_f + 3]:
            row = [fr['f'], fr['src'][2]]
            for s in ('left', 'right'):
                P = rig.feet_world(fr)[s]
                row += [s, round(1000 * float(P[:, 2].min()), 1), [round(float(c), 4) for c in P[:, :2].mean(axis=0)]]
            diag.append(row)
        R['turns']['around_the_worst'] = diag
    check('turns_step_on_planted_feet', len(rep['turns']) >= 3 and all(v[0] <= 2.0 for v in slide.values()),
          f'{len(rep["turns"])} standing turns ({rep["turns"]}); the least-moving sole point in contact moves at most '
          f'{slide} (mm, film frame) a frame through them')
    # the aimed salute
    fa, fb = film(marks['salute_a']), film(marks['salute_b'])
    salute = [fr for fr in frames if fr['src'][1] == 'salute']
    if salute:
        mid = salute[len(salute) // 2]
        err = math.degrees(math.remainder(heading_of_rec(mid) - math.radians(outcome['salute_facing_deg']), 2 * math.pi))
        after = frames[min(len(frames) - 1, salute[-1]['f'] + 30)]
        R['salute'] = {'frames': [salute[0]['f'], salute[-1]['f']], 'mid_heading_err_deg': round(err, 2),
                       'heading_after_deg': round(math.degrees(heading_of_rec(after)), 1)}
        check('aimed_emote', abs(err) < 3.0, f'{R["salute"]} (aimed at {outcome["salute_facing_deg"]} deg)')
    else:
        check('aimed_emote', False, 'no salute frames in the bake')
    # the run
    runs = [w for w in rep['walks'] if abs(w.get('speed', 0) - 2.6) < 0.05]
    R['run_walk'] = [{k: v for k, v in w.items() if k in ('worst', 'speed', 'path_m', 'frames', 'gait', 'run_failed',
                                                           'flight_frames', 'segments')} for w in runs]
    check('run_bakes', len(runs) >= 1 and all(not w.get('run_failed') and 'controller' in w.get('gait', '')
                                              and w.get('flight_frames', 0) > 0
                                              and w['worst'].get('slip_mm_per_frame_max', 9) <= 1.0
                                              and w['worst'].get('swing_touch_frames', 0) == 0 for w in runs),
          f'run spans {len(runs)} (the controller family\'s run: {[w.get("gait") for w in runs]}, frames in flight '
          f'{[w.get("flight_frames") for w in runs]}, failures {[w.get("run_failed") for w in runs]}); worst '
          f'{[w["worst"] for w in runs]}')
    # the walks (walk_path's report, measured on its result): planted feet, no swing touching
    walks = [w for w in rep['walks'] if abs(w.get('speed', 0) - 2.6) >= 0.05]
    worst_w = max((w['worst'].get('slip_mm_per_frame_max', 0.0) for w in walks), default=0.0)
    yaw_w = max((w['worst'].get('yaw_deg_per_frame_max', 0.0) for w in walks), default=0.0)
    touch_w = sum(w['worst'].get('swing_touch_frames', 0) for w in walks)
    check('walks_hold', walks and worst_w <= 1.0 and yaw_w <= 0.5 and touch_w == 0,
          f'{len(walks)} walks: planted slip at most {worst_w} mm a frame, turn on the ground at most {yaw_w} deg a frame, '
          f'{touch_w} swing frames touching')
    # sitting: the hips go down and back up; the stool goes under them (seatOn's job in the WebGPU engine)
    seated = [fr for fr in frames if fr['src'][1] in ('stand_to_sit',)]
    hz = []
    for fr in frames:
        p, _W = rig.bone_world(fr, 'hips')
        hz.append((fr['f'], p))
    z_stand = hz[0][1].z
    if seated:
        f_low = min(seated, key=lambda fr: rig.bone_world(fr, 'hips')[0].z)
        p_low, _W = rig.bone_world(f_low, 'hips')
        R['sit'] = {'frames': [seated[0]['f'], seated[-1]['f']], 'hips_drop_m': round(z_stand - p_low.z, 3),
                    'hips_at': [round(c, 3) for c in p_low]}
        check('sits_and_stands', z_stand - p_low.z > 0.3 and hz[-1][1].z > z_stand - 0.05, f'{R["sit"]}; hips at the end '
              f'{hz[-1][1].z:.3f} m against {z_stand:.3f} m standing')
        seat_top = p_low.z - 0.09
        fwd = f_low['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))
        c = p_low - fwd * 0.02
        stool_m = mat('stool_wood', 'Wood066_1k', 1.4)
        box('stool_seat', c.x - 0.2, c.x + 0.2, c.y - 0.2, c.y + 0.2, seat_top - 0.04, seat_top, stool_m, 0.006)
        for dx in (-0.17, 0.17):
            for dy in (-0.17, 0.17):
                box('stool_leg', c.x + dx - 0.02, c.x + dx + 0.02, c.y + dy - 0.02, c.y + dy + 0.02, 0.0, seat_top - 0.04,
                    stool_m)
        R['stool'] = {'placed_under_the_hips': True, 'top_m': round(seat_top, 3), 'centre': [round(c.x, 3), round(c.y, 3)]}
    else:
        check('sits_and_stands', False, 'no stand_to_sit frames in the bake')
    objs = dbg.build(rep)
    R['debug_objects'] = {k: (o.name if o else None) for k, o in objs.items()}
    R['api'] = {k: (v if not isinstance(v, Vector) else list(v)) for k, v in api.items()}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'body_api.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        cam = S.C.camera('cam', 35.0)
        shots = {}

        vbvh = S.solids_bvh(walls + [pillar])           # (every camera kept in front of the walls: S.best_view)

        def shoot(name, f, wants, aim):
            S.C.aim(cam, S.best_view(vbvh, aim, wants), aim)
            p = os.path.join(S.OUT, f'body_api_{name}_f{f:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, cam, f, p)
        # the first turn, low on the feet, from one camera: before, two mid-steps, after
        if rep['turns']:
            tn = rep['turns'][0]
            p0 = frames[tn['frame'] - 1]['M'].translation
            aim0 = p0 + Vector((0, 0, 0.2))
            cpos = S.best_view(vbvh, aim0, [p0 + Vector((sx * 1.1, sy * 1.3, 0.55)) for sx in (1, -1) for sy in (-1, 1)])
            for k in (0, tn['frames'] // 4, tn['frames'] // 2, 3 * tn['frames'] // 4, tn['frames']):
                shoot('turn_feet', tn['frame'] + k, [cpos], aim0)
        # the run, from the side
        rf = [fr['f'] for fr in frames if fr['src'][0] == 'walk' and fr['src'][1] == 'run']
        for f in (rf[len(rf) // 3], rf[2 * len(rf) // 3]) if rf else ():
            M_ = frames[f - 1]['M']
            p = M_.translation
            side = M_.to_quaternion() @ Vector((1.0, 0.0, 0.0))
            shoot('run', f, [p + s_ * side * 3.0 + Vector((0, 0, 1.0)) for s_ in (1, -1)], p + Vector((0, 0, 0.85)))
        # the salute, from the camera it is aimed at (brought inside the room on that line)
        if salute:
            f = salute[len(salute) // 2]['f']
            shoot('salute', f, [Vector(CAM)], salute[len(salute) // 2]['M'].translation + Vector((0, 0, 1.1)))
        # sitting on the stool, from the side
        if seated:
            f = f_low['f']
            p = f_low['M'].translation
            side = f_low['M'].to_quaternion() @ Vector((1.0, 0.0, 0.0))
            shoot('seated', f, [p + s_ * side * 2.4 + Vector((0, 0, 0.9)) for s_ in (1, -1)], p + Vector((0, 0, 0.6)))
        R['renders'] = shots
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('body_api.json', R)
log('done', R['ok'], R['seconds'], 's')
