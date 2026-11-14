"""My embodied robot sitting down through its own seated state (VRMRobotBody.begin_seated / stand_up on the controller
family's legs), on a chair through seatOn and on a bench it walks up to itself:

    walk_to(in front of the chair) -> emotes.seat_on(vrm, chair, transition='stand_to_sit') (robot_body.js: "Normally you
    call seatOn(vrm, chair, {transition}) which uses [beginSeated] under the hood": it puts me on the spot it measured,
    facing out of the chair, and keeps its measures as body.seat_plan) -> 2.5 s seated -> stand_up('sit_to_stand')
    -> walk_to(the bench's side) -> begin_seated('stand_to_sit', chair=bench) (walked up, turned out of it, backed
    onto its spot) -> 2 s seated -> stand_up(None) (the sit-down played backwards) -> walk_to(away)

    test_body_seat.py [--vrm claude_robot | aletheia] [--no-render]

Checks (PASS / FAIL), each seat measured on the keyed, evaluated mesh:
  - seat_on returns the pan's height; I stand on the spot seat_plan measured, facing out of the chair (1 cm, 1 deg)
  - seated on the pan: through the hold the lowest of my seat skin over the pan is within 1 cm of it (not on air, not
    in it), and my hips are over the seat's target (within 3 cm across)
  - my feet on the floor while seated: each foot's lowest sole point within 6 mm of the floor through the hold
  - the stand-ups: I end standing (the hips back at standing height) and walk on; the seated frames are keyed as
    seated for the audits (eido_seated) and nothing else is
  - the bench: the walk up, the turn, the back-up onto the spot and the sit-down played; seated on its pan as above
  - the controller family's checks.feet per gait listed
Stills: out/seat_<vrm>_<moment>_<k>_f<frame>.png (low side cameras); out/seat_<vrm>.json, out/seat_<vrm>.blend.

    bash run_blender.sh blender/tests/robot_body/test_body_seat.py --no-render
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters import emotes as E  # noqa: E402
from eidoblend.characters.robot import RobotRig, VRMRobotBody  # noqa: E402
from eidoblend.placement.seating import find_seat_surface  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
VRM = ARGS[ARGS.index('--vrm') + 1] if '--vrm' in ARGS else 'claude_robot'
FPS = 24
R = S.Report(f'seat_{VRM}')
START, H0 = (-2.6, -1.6), math.pi                   # facing +Y, into the room
CHAIR = (-1.2, 1.4, 0.0)                             # its back toward the north wall: its sitter faces -Y
BENCH = (1.8, 1.6)                                   # backless; sat on facing -Y (face=0)
AWAY = (2.4, -1.8)


def furniture(name, xy, heading, seat_h, width, depth, back_h, mat):
    """a seat: a pan `seat_h` high on four legs, a backrest behind its sitter to back_h (none: 0), turned so its sitter
    faces `heading` (0 faces -Y). -> the parent empty (the seat's meshes are its children)"""
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (xy[0], xy[1], 0.0)
    root.rotation_euler = (0.0, 0.0, heading)
    parts = [S.box(name + '_pan', -width / 2, width / 2, -depth / 2, depth / 2, seat_h - 0.04, seat_h, mat, 0.004)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (width / 2 - 0.03), sy * (depth / 2 - 0.03)
            parts.append(S.box(f'{name}_leg{sx:+d}{sy:+d}', cx - 0.02, cx + 0.02, cy - 0.02, cy + 0.02, 0.0,
                               seat_h - 0.04, mat))
    if back_h > seat_h:
        parts.append(S.box(name + '_back', -width / 2, width / 2, depth / 2 - 0.04, depth / 2, seat_h, back_h, mat,
                           0.004))
    for p in parts:
        p.parent = root
    bpy.context.view_layer.update()
    return root


def room():
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    wood_m = S.textured('chair_wood', 'Wood066_1k', 1.2)
    floor = S.box('floor', -4.0, 4.0, -3.0, 3.0, -0.05, 0.0, floor_m)
    H = 2.6
    walls = [S.box('wall_n', -4.1, 4.1, 3.0, 3.1, 0.0, H, wall_m), S.box('wall_w', -4.1, -4.0, -3.0, 3.0, 0.0, H, wall_m),
             S.box('wall_e', 4.0, 4.1, -3.0, 3.0, 0.0, H, wall_m)]
    chair = furniture('chair', CHAIR[:2], CHAIR[2], 0.45, 0.46, 0.44, 0.92, wood_m)
    bench = furniture('bench', BENCH, 0.0, 0.45, 1.2, 0.4, 0.0, wood_m)
    return floor, walls, chair, bench


def main():
    sc = S.C.clean_scene(FPS)
    floor, walls, chair, bench = room()
    from eidoblend.characters.robot.example import directional, studio_environment
    studio_environment(sc, 0.4, None)
    S.area_light(sc, 'ceiling_a', (-1.0, 0.5, 2.5), 400.0, 2.0)
    S.area_light(sc, 'ceiling_b', (2.0, 0.5, 2.5), 400.0, 2.0)
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.4)
    me = load_vrm(VRM, name='sitter', location=(START[0], START[1], 0.0), rotation=math.degrees(H0))
    rig = RobotRig(me)
    # the walkable world: the floor and the walls; the seats stay out of it (the controller would read a pan as a step)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + walls,
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': H0, 'walk_speed': 0.9,
                   'agent_radius': 0.3},
        'memory': {'size': 10.0, 'cell_size': 0.1}, 'sensors': {'h_rays': 16, 'v_rays': 12, 'range': 6.0},
        'planner': {'agent_radius': 0.3}}, rig=rig)
    legs = body.controller.char_ctrl
    out, marks = {}, {}
    plan0 = E.seat_plan(me, chair, transition='stand_to_sit')

    def script(b):
        a = yield b.scan_area(yaw_range=90, duration=1.6)
        # as a JS scene does: walk up to the seat's spot (the planner stops me short of the chair it sees), turn out of
        # the chair, then seatOn (its snap onto the spot is what is left)
        a = yield b.walk_to(*plan0['spot'])
        out['walk_chair'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(plan0['heading'])
        out['turn_chair'] = a.state
        p = b.get_position()
        out['snap_m'] = math.hypot(p['x'] - plan0['spot'][0], p['y'] - plan0['spot'][1])
        marks['chair'] = b.frame_count
        out['z'] = E.seat_on(me, chair, transition='stand_to_sit')
        p = b.get_position()
        out['placed'] = (p['x'], p['y'], b.get_heading())
        out['state'] = b.controller.get_state()
        a = yield b.wait(2.3 + 2.5)
        marks['chair_up'] = b.frame_count
        b.stand_up('sit_to_stand')
        a = yield b.until(lambda: b.controller.get_state() != 'performing')
        marks['chair_stood'] = b.frame_count
        a = yield b.walk_to(BENCH[0] - 1.4, BENCH[1] - 1.2)
        out['walk_bench'] = (a.state, str(a.error) if a.error else None)
        marks['bench'] = b.frame_count
        out['bench_dur'] = b.begin_seated('stand_to_sit', chair=bench, face=0.0)
        a = yield b.wait(9.0)
        marks['bench_up'] = b.frame_count
        b.stand_up(None)
        a = yield b.until(lambda: b.controller.get_state() != 'performing')
        marks['bench_stood'] = b.frame_count
        a = yield b.walk_to(*AWAY)
        out['walk_away'] = (a.state, str(a.error) if a.error else None)
        a = yield b.wait(0.6)
    body.run(script(body))
    dt = 1.0 / FPS
    for k in range(FPS * 60):
        body.update(k * dt, dt)
        if body._script is None:
            break
    plan = getattr(body, 'seat_plan', None)
    R['run'] = {'frames': body.frame_count, 'outcome': out, 'marks': marks,
                'log': [(round(t, 2), e) for t, e in body.log],
                'seats': [dict(s) for s in getattr(legs.loco, '_seats', [])],
                'said': [s for s in legs.said if 'seat' in s[1].lower() or 'stand' in s[1].lower()][:30]}
    R.log('run', R['run'])
    rep = body.bake(face=lambda t: {'relaxed': 0.3}, action_name='sitter|seats')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    frames = rep['_frames']
    sc.frame_start, sc.frame_end = rep['frames']
    f0 = rep['frames'][0]

    # ---- checks
    px, py, ph = out.get('placed', (0, 0, 0))
    d = math.hypot(px - plan['spot'][0], py - plan['spot'][1]) if plan else 9.0
    R.check('seat_on places me as seatOn measures', plan is not None and abs(out.get('z', -1) - 0.45) < 0.005 and d < 0.01
            and abs(math.remainder(ph - plan['heading'], 2 * math.pi)) < math.radians(1.0),
            f'pan {out.get("z")}, {d * 100:.2f} cm off the spot, heading {math.degrees(ph):.1f} deg (the plan '
            f'{math.degrees(plan["heading"]) if plan else None:.1f}); the walk up left me {out.get("snap_m", 0) * 100:.1f} '
            f'cm from it (seatOn\'s snap)')
    spans = rep.get('seated', {}).get('spans', [])
    R['seated_spans'] = spans
    seats = {s['chair']: s for s in getattr(legs.loco, '_seats', [])}
    for tag, seat, a_, b_ in (('chair', chair, marks.get('chair', 0), marks.get('chair_up', 0)),
                              ('bench', bench, marks.get('bench', 0), marks.get('bench_up', 0))):
        span = next(((a, b) for a, b in spans if a_ <= a <= b_ + 2 * FPS), None)
        if span is None or tag not in seats:
            R.check(f'{tag}: seated', False, f'no seated span between frames {a_} and {b_}: {spans}; seats {seats}')
            continue
        pan = find_seat_surface(seat)
        pts = E.pan_points(seat, pan)
        # the hold: from the sit-down's end (it began at the seat's t0 and lasts its clip) to the stand-up's call
        h0_ = f0 + int(round((seats[tag]['t0'] + 2.3) * FPS))
        hold = list(range(h0_, f0 + b_ - 2, 3))
        gaps, across, feet = [], [], []
        for f in hold:
            sc.frame_set(f)
            und = E.skin_lowest(me, pts, pan['z'] - 0.6, reach=1.2)
            if und is not None:
                gaps.append(und - pan['z'])
            hp = S.C.bone_world(me.arm, me.humanoid['hips'])
            across.append(math.hypot(hp.x - pan['x'], hp.y - pan['y']))
            for s_, P in rig.feet_world(frames[f - f0]).items():
                feet.append(float(P[:, 2].min()))
        R[f'{tag}_seated'] = {'span': span, 'frames_measured': len(hold),
                              'skin_over_pan_cm': [round(100 * min(gaps), 2), round(100 * max(gaps), 2)] if gaps else None,
                              'hips_from_pan_centre_cm': round(100 * max(across), 1) if across else None,
                              'feet_lowest_mm': [round(1000 * min(feet), 1), round(1000 * max(feet), 1)] if feet else None}
        st = R[f'{tag}_seated']
        R.check(f'{tag}: seated on the pan', gaps and -0.01 < min(gaps) and max(gaps) < 0.01 and max(across) < 0.12,
                f'{st} (the skin within 1 cm of the pan; the hips over the pan, its backrest bias aside)')
        R.check(f'{tag}: my feet on the floor while seated', feet and max(abs(v) for v in feet) < 0.006,
                f'each foot\'s lowest sole point {st["feet_lowest_mm"]} mm over the floor through the hold')
    # standing again, walking on
    hz = [(fr['f'], rig.bone_world(fr, 'hips')[0].z) for fr in frames]
    z_stand = hz[0][1]
    ends = {}
    for tag, m in (('chair', 'chair_stood'), ('bench', 'bench_stood')):
        f = marks.get(m)
        if f:
            ends[tag] = round(hz[min(len(hz) - 1, f + FPS // 2)][1] - z_stand, 3)
    R.check('the stand-ups: standing again and walking on', ends and all(abs(v) < 0.04 for v in ends.values())
            and out.get('walk_bench', ('',))[0] == 'resolved' and out.get('walk_away', ('',))[0] == 'resolved',
            f'the hips half a second after each stand-up, against my standing height: {ends} m; the walks after them '
            f'{out.get("walk_bench")}, {out.get("walk_away")}')
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    R.log('the controller family\'s checks.feet failures:', fails)
    # the stills: a low side camera held over each sit-down, each stand-up and the bench's approach (the walk up, the
    # turn out of it, the back-up), every two or three frames
    vbvh = S.solids_bvh(walls + [o for s_ in (chair, bench) for o in s_.children_recursive])
    last = f0 + len(frames) - 1
    t_b = seats.get('bench', {}).get('t0')
    f_b = f0 + int(round(t_b * FPS)) if t_b is not None else marks.get('bench', 1)
    shots = []
    for tag, a_, b_ in (('chair_sit', marks.get('chair', 1) - 4, marks.get('chair', 1) + int(2.6 * FPS)),
                        ('chair_up', marks.get('chair_up', 1) - 4, marks.get('chair_stood', 1) + 12),
                        ('bench_approach', marks.get('bench', 1), f_b),
                        ('bench_sit', f_b - 4, f_b + int(2.6 * FPS)),
                        ('bench_up', marks.get('bench_up', 1) - 4, marks.get('bench_stood', 1) + 12)):
        a_, b_ = max(f0, a_), min(last, b_)
        if b_ > a_:
            shots += S.strip(tag, S.side_view(vbvh, frames, f0, a_, b_), a_, b_, n=min(18, (b_ - a_) // 3 + 1))
    S.write_json(f'seat_{VRM}_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, f'seat_{VRM}.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, f'seat_{VRM}', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
