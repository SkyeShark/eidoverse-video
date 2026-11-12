"""My embodied robot's moves: VRMRobotBody.vault / jump / climb_ledge / climb_ladder (robot_body.js passes them through
robot_controller.js to the engine's charCtrl; here the controller family's VRMCharacterController, my legs, plays each
from wherever I am: standing, or out of a walk), on a course down a hall:

    walk_to(before a low wall, 0.8 m) -> vault() from standing -> walk_to(past the ditch) with jump() called 0.45 m
    before its edge, mid-stride (0.75 m wide, 0.7 m deep) -> walk_to(before the step, 1.0 m) -> climb_ledge() onto it
    -> walk_to(the ladder) on its top -> climb_ladder({'height': 1.9}) up the tower's ladder and over its top
    -> look_at the hall

and the refusals, as the JS answers them: vault() with nothing ahead, and a move asked while an emote plays, are False.

Checks (PASS / FAIL):
  - each move started (True) and played its maneuver in the controller family (vault; jump; mount; ladder with the
    mount chained over its top); the jump out of the walk, the walk going on to its goal after it; I sense on through
    each (the readings go on)
  - the refusals answer False and change nothing
  - I end on the tower's top (2.9 m)
  - no sole point of either foot goes more than 2 cm into the floor, the wall, the step or the tower at any keyed frame,
    and standing, both feet are within 4 mm of what they stand on
  - my passes keep the controller family's hands (my keyed knuckles against its baked frames), and those hands are on
    what they hold: the vault's on the wall's top, the ladder's on its rungs (within 6 cm, as the controller family's
    course test measures them; its contact IK on my body)
  - the controller family's checks.feet on every gait, listed
Stills: out/maneuvers_<move>_<k>_f<frame>.png (low side cameras); out/maneuvers.json, out/maneuvers.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_maneuvers.py --no-render
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

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotRig, VRMRobotBody  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
START = (-6.45, 0.0)                              # the wall 2.85 m ahead: past the moves' scan (2.6 m)
H0 = math.pi / 2                                   # facing +X, down the hall
WALL = (-3.6, -3.35, 0.8)                          # x0, x1, its top
DITCH = (-1.2, -0.45, -0.7)                        # x0, x1, its floor
STEP = (1.2, 3.4, 1.0)
TOWER = (3.4, 4.6, 2.9)
LADDER_Y = 0.25                                    # the rails at +-0.25 m
RUNG0, RUNG_DY = 0.25, 0.28                        # the first rung over the step's top, the spacing
R = S.Report('maneuvers')


def bar(name, p0, p1, radius, mat):
    """a round bar from p0 to p1 (a ladder's rail or rung)"""
    d = Vector(p1) - Vector(p0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=d.length,
                                        location=(Vector(p0) + Vector(p1)) / 2)
    ob = bpy.context.object
    ob.name = name
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized())
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def hall():
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    block_m = S.textured('blocks_painted', 'PaintedWood009C_2k', 0.8)
    pit_m = S.textured('pit_floor', 'PaintedPlaster017_2k', 0.7, tint=(0.45, 0.44, 0.42, 1.0))
    steel_m = S.textured('ladder_steel', 'PaintedMetal012_1k', 1.0, tint=(0.25, 0.27, 0.3, 1.0))
    solids = []
    # the floor on either side of the ditch (deep boxes: the ditch's walls are their faces), the ditch's floor
    solids += [S.box('floor_a', -7.0, DITCH[0], -3.0, 3.0, -1.0, 0.0, floor_m),
               S.box('floor_b', DITCH[1], 6.5, -3.0, 3.0, -1.0, 0.0, floor_m),
               S.box('ditch_floor', DITCH[0], DITCH[1], -3.0, 3.0, -1.0, DITCH[2], pit_m)]
    solids.append(S.box('low_wall', WALL[0], WALL[1], -1.6, 1.6, 0.0, WALL[2], block_m, 0.01))
    solids.append(S.box('step', STEP[0], STEP[1], -1.6, 1.6, 0.0, STEP[2], block_m, 0.01))
    solids.append(S.box('tower', TOWER[0], TOWER[1], -1.6, 1.6, 0.0, TOWER[2], block_m, 0.01))
    # the hall round it: a back wall and both ends (every camera looks into a room)
    H = 6.5
    solids += [S.box('wall_back', -7.1, 6.6, 3.0, 3.1, -1.0, H, wall_m),
               S.box('wall_west', -7.1, -7.0, -3.0, 3.0, -1.0, H, wall_m),
               S.box('wall_east', 6.5, 6.6, -3.0, 3.0, -1.0, H, wall_m)]
    # the ladder on the tower's face over the step (visual: "the rungs are visual, the flat face is the collider", as
    # the WebGPU terrain_base builds its ladders)
    fx = TOWER[0] - 0.09
    rungs = []
    fixtures = [bar('ladder_rail_l', (fx, -LADDER_Y, STEP[2]), (fx, -LADDER_Y, TOWER[2] + 0.9), 0.022, steel_m),
                bar('ladder_rail_r', (fx, LADDER_Y, STEP[2]), (fx, LADDER_Y, TOWER[2] + 0.9), 0.022, steel_m)]
    z = STEP[2] + RUNG0
    k = 0
    while z < TOWER[2] - 0.05:
        rungs.append(bar(f'ladder_rung_{k:02d}', (fx, -LADDER_Y, z), (fx, LADDER_Y, z), 0.016, steel_m))
        z += RUNG_DY
        k += 1
    fixtures += rungs
    for o in fixtures:                               # standoffs back to the face
        o['no_walkable'] = True
    return solids, fixtures, rungs


def lights(sc):
    from eidoblend.characters.robot.example import directional, studio_environment
    studio_environment(sc, 0.4, None)
    for name, loc in (('ceiling_w', (-4.0, 0.0, 4.0)), ('ceiling_m', (0.0, 0.0, 4.0)), ('ceiling_e', (4.0, 0.0, 4.0))):
        S.area_light(sc, name, loc, 900.0, 2.4)
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.6)


def main():
    sc = S.C.clean_scene(FPS)
    solids, fixtures, rungs = hall()
    lights(sc)
    me = load_vrm('claude_robot', name='claude', location=(START[0], START[1], 0.0), rotation=math.degrees(H0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': solids,                  # the walkable world: floors, the wall, the step, the tower
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': H0, 'walk_speed': 0.9,
                   'agent_radius': 0.3},
        'memory': {'size': 16.0, 'cell_size': 0.1},
        'sensors': {'h_rays': 16, 'v_rays': 12, 'range': 6.0},
        'planner': {'agent_radius': 0.3, 'max_step_height': 1.15}}, rig=rig)
    legs = body.controller.char_ctrl
    outcome, marks = {}, {}

    def landed(b):
        return b.until(lambda: not b.is_maneuvering())

    def move(b, name, fn):
        marks[name] = b.frame_count
        ok = fn()
        outcome[name] = ok
        return ok, len(b.readings)

    def script(b):
        # the refusal with nothing ahead: the hall's open floor before the wall is past the scan's reach
        outcome['vault_nothing_ahead'] = b.vault()
        outcome['state_after_refusal'] = (b.is_maneuvering(), b.controller.get_state())
        a = yield b.wait(0.4)
        a = yield b.walk_to(WALL[0] - 0.55, 0.0)
        outcome['walk_wall'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(H0)
        ok, n0 = move(b, 'vault', b.vault)
        if ok:
            a = yield landed(b)
        outcome['vault_senses'] = len(b.readings) - n0
        # the jump out of a walk: walking past the ditch, the jump called 0.45 m before its edge
        walk = b.walk_to(DITCH[1] + 0.9, 0.0)
        a = yield b.until(lambda: b.get_position()['x'] > DITCH[0] - 0.45 or walk.done)
        ok, n0 = move(b, 'jump', lambda: b.jump({'distance': 1.4, 'height': 0.45}))
        outcome['jump_state'] = b.controller.get_state()
        if ok:
            a = yield landed(b)
        outcome['jump_senses'] = len(b.readings) - n0
        a = yield walk
        outcome['walk_ditch'] = (a.state, str(a.error) if a.error else None)
        # the refusal during an emote
        em = b.perform_action('wave_goodbye', 1.2)
        a = yield b.wait(0.3)
        outcome['vault_in_emote'] = b.vault()
        a = yield em
        a = yield b.walk_to(STEP[0] - 0.5, 0.0)
        outcome['walk_step'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(H0)
        ok, n0 = move(b, 'climb_ledge', b.climb_ledge)
        if ok:
            a = yield landed(b)
        outcome['climb_ledge_senses'] = len(b.readings) - n0
        a = yield b.walk_to(TOWER[0] - 0.5, 0.0)
        outcome['walk_ladder'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(H0)
        ok, n0 = move(b, 'climb_ladder', lambda: b.climb_ladder({'height': TOWER[2] - STEP[2], 'rungRadius': 0.016}))
        if ok:
            a = yield landed(b)
        outcome['climb_ladder_senses'] = len(b.readings) - n0
        a = yield b.look_at(-2.0, -1.0, 0.5)
        outcome['look_at'] = a.state
        a = yield b.wait(1.0)
    body.run(script(body))
    dt = 1.0 / FPS
    t_sim = time.time()
    for k in range(FPS * 70):
        body.update(k * dt, dt)
        if body._script is None:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t_sim, 2), 'outcome': outcome,
                'marks': marks, 'log': [(round(t, 2), e) for t, e in body.log], 'senses': len(body.readings),
                'maneuver_log': legs.maneuver_log}
    R.log('run', R['run'])
    t_b = time.time()
    rep = body.bake(face=lambda t: {'happy': 0.2}, action_name='claude|maneuvers')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    R['bake_s'] = round(time.time() - t_b, 1)
    frames, recs, planted = rep['_frames'], rep['_records'], rep['_planted']
    sc.frame_start, sc.frame_end = rep['frames']
    f0 = rep['frames'][0]

    # ---- checks
    moves = rep['moves']
    played = [m[0] for m in moves]
    want = {'vault': 'vault', 'jump': 'jump', 'climb_ledge': 'mount', 'climb_ladder': 'ladder'}
    started = all(outcome.get(n) is True for n in want)
    has = (all(v in played for v in want.values()) and 'ladder' in played
           and 'mount' in played[played.index('ladder'):])
    senses = {n: outcome.get(n + '_senses', 0) for n in want}
    R.check('moves_play', started and has and all(v > 5 for v in senses.values())
            and outcome.get('jump_state') == 'walking' and outcome.get('walk_ditch', ('',))[0] == 'resolved',
            f'started {[(n, outcome.get(n)) for n in want]}; played {moves}; the jump called mid-walk (the state '
            f'{outcome.get("jump_state")}), the walk on to its goal: {outcome.get("walk_ditch")}; sensor readings through '
            f'each {senses}')
    R.check('refusals', outcome.get('vault_nothing_ahead') is False and outcome.get('vault_in_emote') is False
            and outcome.get('state_after_refusal') == (False, 'idle'),
            f'vault() with nothing ahead {outcome.get("vault_nothing_ahead")}, then {outcome.get("state_after_refusal")}; '
            f'vault() while waving {outcome.get("vault_in_emote")}; what the legs logged: {legs.maneuver_log}')
    end = frames[-1]['M'].translation
    R.check('ends_on_the_tower', abs(end.z - TOWER[2]) < 0.03 and TOWER[0] + 0.1 < end.x < TOWER[1],
            f'the keyed root ends at ({end.x:.2f}, {end.y:.2f}, {end.z:.3f}) (the tower top {TOWER[2]} m, x {TOWER[0]}..'
            f'{TOWER[1]})')
    bvh = S.solids_bvh(solids)
    deep = S.feet_in_solids(rig, frames, bvh)
    stand_gap = (0.0, None)
    for fr, r in zip(frames, recs):
        if not (r['mode'] == 'loco' and r.get('lead') == 'idle' and r['speed'] < 0.02):
            continue
        for s, P in rig.feet_world(fr).items():
            low = P[np.argmin(P[:, 2])]
            hit = bvh.ray_cast(Vector((low[0], low[1], low[2] + 0.3)), Vector((0.0, 0.0, -1.0)), 2.0)
            if hit[0] is not None and abs(float(low[2]) - hit[0].z) > stand_gap[0]:
                stand_gap = (abs(float(low[2]) - hit[0].z), fr['f'], s)
    R['feet'] = {'deepest_in_mm': [round(1000 * deep[0], 1)] + list(deep[1:]),
                 'standing_off_mm': [round(1000 * stand_gap[0], 1)] + list(stand_gap[1:]),
                 'pushed_out_of_a_climbed_face_m': rep.get('moves_feet_out_m')}
    R.check('feet_on_and_out_of_the_solids', deep[0] < 0.02 and stand_gap[0] < 0.004,
            f'on every keyed frame no sole point goes deeper than {R["feet"]["deepest_in_mm"]} (mm, frame, foot, mode) '
            f'into the floor, the wall, the step or the tower; standing, the lowest sole point of each foot is within '
            f'{R["feet"]["standing_off_mm"]} (mm, frame, foot) of what it stands on (through the moves my clamped legs '
            f'put a foot into a face this deep, pushed out onto it by the bake: {R["feet"]["pushed_out_of_a_climbed_face_m"]})')
    # the hands (each hand's knuckles: the middle finger's proximal joint) on my keyed frames and on the controller
    # family's baked frames of the same moves: my passes after its plant must keep what its contact IK did
    knuck = ('leftMiddleProximal', 'rightMiddleProximal')
    fxr = TOWER[0] - 0.09
    rung_z = [r.matrix_world.translation.z for r in rungs]

    def to_wall_top(p):
        dx = max(0.0, WALL[0] - p.x, p.x - WALL[1])
        dy = max(0.0, -1.6 - p.y, p.y - 1.6)
        return math.sqrt(dx * dx + dy * dy + (p.z - WALL[2]) ** 2)

    def to_rung(p):
        dy = max(0.0, abs(p.y) - LADDER_Y)
        return min(math.sqrt((p.x - fxr) ** 2 + (p.z - z) ** 2 + dy * dy) for z in rung_z)
    hands = {}
    for kind, fn in (('vault', to_wall_top), ('ladder', to_rung)):
        span = next(((a, b) for v, a, b in moves if v == kind), None)
        if span is None:
            continue
        res = {}
        for lab, seq in (('keyed', frames), ('controller', planted)):
            ds = [min(fn(rig.bone_world(seq[f - f0], n)[0]) for n in knuck) for f in range(span[0], span[1] + 1)]
            res[lab] = ({'min_m': round(min(ds), 3)} if kind == 'vault' else
                        {'median_m': round(float(np.median(ds)), 3), 'within_6cm': round(float(np.mean(np.array(ds) < 0.06)), 2),
                         'frames': len(ds)})
        hands[kind] = res
    R['hands'] = hands
    v_, l_ = hands.get('vault') or {}, hands.get('ladder') or {}
    kept = (v_ and l_ and v_['keyed']['min_m'] <= v_['controller']['min_m'] + 0.01
            and l_['keyed']['median_m'] <= l_['controller']['median_m'] + 0.01)
    on = v_ and l_ and v_['keyed']['min_m'] < 0.06 and l_['keyed']['median_m'] < 0.06
    R.check('hands_kept_through_my_passes', bool(kept), f'my keyed knuckles against the controller family\'s frames: the '
            f'vault\'s nearest to the wall\'s top {v_}; on the ladder, to the nearest rung {l_}')
    R.check('hands_on_what_they_hold (the controller family\'s contact IK)', bool(on),
            f'(within 6 cm, as the controller family\'s course test asks) the vault {v_.get("keyed")}, the ladder '
            f'{l_.get("keyed")}')
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    R.log('the controller family\'s checks.feet failures:', fails)
    # the stills: a low side camera held over each move and the steps either side of it (_stage.side_view: on the side
    # with room, so the ladder is seen from the step's side, where the tower does not hide it), every two frames
    vbvh = S.solids_bvh(solids)
    shots, last, seen = [], f0 + len(frames) - 1, {}
    for v, a, b in moves:
        a_, b_ = max(f0, a - 8), min(last, b + 8)
        seen[v] = seen.get(v, -1) + 1
        nm = v if not seen[v] else f'{v}{seen[v] + 1}'
        shots += S.strip(nm, S.side_view(vbvh, frames, f0, a_, b_), a_, b_, n=min(20, (b_ - a_) // 2 + 1))
    S.write_json('maneuvers_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'maneuvers.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'maneuvers', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
