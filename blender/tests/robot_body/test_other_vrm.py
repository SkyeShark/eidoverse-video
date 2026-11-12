"""VRMRobotBody on a VRM that is not my robot body: robot_body.js drives ANY VRM through the engine's controller, which
knows nothing of my hardware, so here Aletheia (aletheia.vrm) senses, plans and walks on the controller family's legs
with a plain RobotRig: her clips as the controller plays them, the body's gaze on her head bone exactly as
_applyHeadOverride sets it, and none of my body's passes (joint limits, clearances, head states, crown).

The room (7 x 5 m): a crate across her way and a lamp on a shelf. The scene's direction, awaited action by action:

    scan_area(90 deg, 1.5 s) -> walk_to(the far end) -> face_direction(the lamp 25 deg to her left)
        -> look_at(the lamp, hold) -> wait(1 s) -> perform_action('wave_goodbye', 2 s)

Checks (PASS / FAIL):
  - plain_rig: the rig knows she is not my body (hardware False), no correction was made to any joint (its stats
    empty), and on every frame her keyed arms, hands, fingers, spine and chest are the controller's own pose (within
    0.01 deg): no turn-out, no clamp, no re-homed clavicle
  - arrived: the walk_to resolved and the walk stops within 0.1 m of the goal, round the crate it saw
  - gaze_is_the_js: on every frame her head bone's own turn is _applyHeadOverride's Euler(pitch, yaw, 0, 'YXZ') of the
    body's gaze (re-aimed from where the keyed body stands: bake._aimed_gaze), her neck the controller's; holding the
    lamp her face is off it by no more than the clip's torso and neck turn her head (+2 deg): the JS aims the head bone
    from the body's heading alone
  - feet: the controller family's checks.feet on every gait, both feet on the floor standing (within 3 mm)
  - keyed: the saved action alone puts her head bone where the bake's records do (within 1 mm, evaluated)
  - springs: her spring chains (her hair) baked over the whole keyed take, no NaN (the engine steps them every frame)
  - hands_refused: my hands' work (hands.HandModel) refuses her plainly instead of failing deep inside
Stills: out/other_vrm_<moment>_<k>_f<frame>.png (low side cameras over her walk's start and stop and her turn; her
face on the lamp); out/other_vrm.json, out/other_vrm.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_other_vrm.py --no-render
"""

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
from eidoblend.characters._math import q_from_three, quat_from_euler  # noqa: E402
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody, hands  # noqa: E402
from eidoblend.characters.robot.bake import _aimed_gaze  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
CAST = next((a for a in ARGS if not a.startswith('--')), 'aletheia')
FPS = 24
START, GOAL = (-2.6, -0.2), (2.4, 0.3)
LAMP = (3.2, 1.25, 1.52)
R = S.Report('other_vrm')
R['cast'] = CAST


def main():
    sc = S.C.clean_scene(FPS)
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    crate_m = S.textured('crate_card', 'Cardboard002_1k', 1.5)
    shelf_m = S.textured('shelf_metal', 'PaintedMetal012_1k', 1.0, tint=(0.42, 0.45, 0.5, 1.0))
    floor = S.box('floor', -3.5, 3.5, -2.5, 2.5, -0.05, 0.0, floor_m)
    H = 2.6
    obs = [S.box('wall_s', -3.6, 3.6, -2.6, -2.5, 0.0, H, wall_m), S.box('wall_n', -3.6, 3.6, 2.5, 2.6, 0.0, H, wall_m),
           S.box('wall_w', -3.6, -3.5, -2.5, 2.5, 0.0, H, wall_m), S.box('wall_e', 3.5, 3.6, -2.5, 2.5, 0.0, H, wall_m),
           S.box('crate', -0.45, 0.35, -0.9, 0.7, 0.0, 0.85, crate_m, 0.01),
           S.box('shelf', 2.9, 3.45, 0.8, 1.7, 0.0, 1.4, shelf_m, 0.006)]
    lamp_m = bpy.data.materials.new('lamp_glow')
    lamp_m.use_nodes = True
    b_ = lamp_m.node_tree.nodes['Principled BSDF']
    b_.inputs['Base Color'].default_value = (1.0, 0.8, 0.5, 1.0)
    b_.inputs['Emission Color'].default_value = (1.0, 0.75, 0.45, 1.0)
    b_.inputs['Emission Strength'].default_value = 6.0
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=LAMP)
    lamp = bpy.context.object
    lamp.name = 'lamp'
    lamp.data.materials.append(lamp_m)
    obs.append(lamp)
    from eidoblend.characters.robot.example import studio_environment
    studio_environment(sc, 0.35, None)
    S.area_light(sc, 'ceiling_w', (-1.8, 0.0, 2.45), 260.0, 1.2, (1.0, 0.93, 0.85))
    S.area_light(sc, 'ceiling_e', (1.8, 0.4, 2.45), 260.0, 1.2, (1.0, 0.93, 0.85))
    ld = bpy.data.lights.new('lamp_light', 'POINT')
    ld.energy, ld.color, ld.shadow_soft_size = 40.0, (1.0, 0.75, 0.45), 0.12
    ob = bpy.data.objects.new('lamp_light', ld)
    ob.location = LAMP
    sc.collection.objects.link(ob)

    h0 = heading_of(GOAL[0] - START[0], GOAL[1] - START[1])
    me = load_vrm(CAST, name=CAST, location=(START[0], START[1], 0.0), rotation=math.degrees(h0))
    rig = RobotRig(me)
    R['hardware'] = rig.hardware
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + obs,
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': h0, 'walk_speed': 1.0, 'agent_radius': 0.3},
        'memory': {'size': 9.0, 'cell_size': 0.1},
        'sensors': {'h_rays': 16, 'v_rays': 12, 'range': 6.0},
        'planner': {'agent_radius': 0.3}}, rig=rig)
    dbg = RobotDebug(body)
    for k in ('rays', 'map', 'path'):
        getattr(dbg, 'show_' + k)(True)
    outcome, marks = {}, {}

    def script(b):
        a = yield b.scan_area(yaw_range=90, duration=1.5)
        outcome['scan'] = a.state
        a = yield b.walk_to(*GOAL)
        outcome['walk_to'] = (a.state, str(a.error) if a.error else None)
        marks['arrived'] = b.frame_count
        p_ = b.get_position()                         # she turns on the spot to have the lamp 25 deg to her left
        a = yield b.face_direction(heading_of(LAMP[0] - p_['x'], LAMP[1] - p_['y']) - math.radians(25.0))
        outcome['face_direction'] = a.state
        a = yield b.look_at(*LAMP, hold=True)
        outcome['look_at'] = a.state
        marks['look_from'] = b.frame_count
        a = yield b.wait(1.0)
        marks['look_to'] = b.frame_count
        a = yield b.perform_action('wave_goodbye', 2.0)
        outcome['wave'] = a.state
    body.run(script(body))
    dt = 1.0 / FPS
    f_done = None
    for k in range(FPS * 30):
        body.update(k * dt, dt)
        dbg.update()
        if body._script is None and f_done is None:
            f_done = k
        if f_done is not None and k >= f_done + FPS // 2:
            break
    R['run'] = {'frames': body.frame_count, 'outcome': outcome, 'marks': marks,
                'log': [(round(t, 2), e) for t, e in body.log]}
    R.log('run', R['run'])
    rep = body.bake(face=lambda t: {'happy': 0.3}, action_name=f'{CAST}|other_vrm')
    sc.frame_start, sc.frame_end = rep['frames']
    dbg.build(rep)
    frames, recs = rep['_frames'], rep['_records']
    f0 = rep['frames'][0]
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}

    # ---- plain_rig: her pose is the controller's own (my passes touch only her head bone's gaze)
    kept = ('spine', 'chest', 'upperChest', 'leftShoulder', 'rightShoulder', 'leftUpperArm', 'rightUpperArm',
            'leftLowerArm', 'rightLowerArm', 'leftHand', 'rightHand', 'leftIndexProximal', 'rightThumbProximal',
            'leftLittleDistal')
    kept = [n for n in kept if n in me.humanoid]
    worst = (0.0, None, None)
    for fr, r in zip(frames, recs):
        for n in kept:
            a = math.degrees(fr['N'][n].rotation_difference(r['N'][n]).angle) if n in r['N'] else 0.0
            if a > worst[0]:
                worst = (a, fr['f'], n)
    R['plain_rig'] = {'hardware': rig.hardware, 'stats': rig.stats, 'frames': len(frames),
                      'worst_deg': [round(worst[0], 5), worst[1], worst[2]]}
    R.check('plain_rig', rig.hardware is False and not rig.stats and worst[0] < 0.01,
            f'hardware {rig.hardware}, joint corrections {rig.stats or "none"}; on all {len(frames)} frames her keyed '
            f'{", ".join(kept[:6])} ... are the controller\'s own pose within {worst[0]:.5f} deg (worst at frame '
            f'{worst[1]}, {worst[2]})')

    # ---- arrived, round the crate
    stop = recs[marks['arrived'] - 1]['feet_world']
    dgoal = math.hypot(stop[0] - GOAL[0], stop[1] - GOAL[1])
    crate_min = math.inf
    for fr in frames:
        p = fr['M'].translation
        dx = max(-0.45 - p.x, 0.0, p.x - 0.35)
        dy = max(-0.9 - p.y, 0.0, p.y - 0.7)
        crate_min = min(crate_min, math.hypot(dx, dy))
    R['arrived'] = {'from_goal_m': round(dgoal, 3), 'root_to_crate_min_m': round(crate_min, 3)}
    R.check('arrived', outcome.get('walk_to', ('',))[0] == 'resolved' and dgoal < 0.1 and crate_min > 0.25,
            f'walk_to {outcome.get("walk_to")}; the walk stops {dgoal:.3f} m from the goal, the root at least '
            f'{crate_min:.3f} m from the crate it walked round')

    # ---- the gaze: robot_body.js's _applyHeadOverride on her head bone, every frame, and on the lamp while it holds
    lamp_p = Vector(LAMP)
    head_err, neck_off = (0.0, None), 0.0
    for fr, r in zip(frames, recs):
        # (a bone no clip binds stays at rest in the controller's pose: identity)
        neck_off = max(neck_off, math.degrees(fr['N'].get('neck', Quaternion()).rotation_difference(
            r['N'].get('neck', Quaternion())).angle))
        g = _aimed_gaze(rig, fr, r)                       # the live gaze, re-aimed from where the keyed body stands
        if g is None:
            continue
        want = q_from_three(quat_from_euler(g[1], g[0], 0.0, 'YXZ'))
        a = math.degrees(fr['N']['head'].rotation_difference(want).angle)
        if a > head_err[0]:
            head_err = (a, fr['f'])
    fa, fb = f0 + marks.get('look_from', 0) + 1, f0 + marks.get('look_to', 0) - 2
    offs, chain = [], []
    for fr in frames[fa - f0:fb - f0 + 1]:
        p, W = rig.bone_world(fr, 'head')
        offs.append((round(math.degrees((W @ Vector((0.0, -1.0, 0.0))).angle(lamp_p - p)), 2), fr['f']))
        _pn, Wn = rig.bone_world(fr, 'neck')
        chain.append(round(math.degrees((fr['M'].to_quaternion().inverted() @ Wn).angle), 2))
    R['gaze'] = {'head_local_vs_js_deg': [round(head_err[0], 5), head_err[1]], 'frames': [fa, fb],
                 'facing_off_lamp_deg': offs, 'torso_and_neck_turn_deg': chain, 'neck_vs_controller_deg': round(neck_off, 5)}
    R.check('gaze_is_the_js', head_err[0] < 0.01 and bool(offs) and neck_off < 0.01 and max(offs)[0] <= max(chain) + 2.0,
            f'on every frame her head bone\'s own turn is _applyHeadOverride\'s Euler(pitch, yaw, 0, YXZ) of the body\'s '
            f'gaze within {head_err[0]:.5f} deg; her neck stays the controller\'s within {neck_off:.5f} deg; holding the '
            f'lamp (frames {fa}-{fb}) her face is {min(offs)[0] if offs else None}-{max(offs)[0] if offs else None} deg '
            f'off it, no more than the clip\'s torso and neck turn her head ({min(chain) if chain else None}-'
            f'{max(chain) if chain else None} deg)')

    # ---- feet
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    stand_gap, gap_at = 0.0, None
    for fr, r in zip(frames, recs):
        if not (r['mode'] == 'loco' and r.get('lead') == 'idle' and r['speed'] < 0.02):
            continue
        for s, P in rig.feet_world(fr).items():
            g_ = float(P[:, 2].min())
            if abs(g_) > stand_gap:
                stand_gap, gap_at = abs(g_), (fr['f'], s, round(1000 * g_, 2))
    R['feet'] = {'standing_gap_mm': round(1000 * stand_gap, 2), 'standing_gap_at': gap_at}
    R.check('feet', not fails and stand_gap < 0.003,
            f'the controller family\'s checks.feet: {len(rep["segments"]) - len(fails)} of {len(rep["segments"])} gaits '
            f'pass {[(f[0], f[1], f[2][:1]) for f in fails]}; standing, each foot\'s lowest sole point within '
            f'{1000 * stand_gap:.2f} mm of the floor')

    # ---- keyed: the action alone puts the head where the records do
    hb = me.humanoid['head']
    err = (0.0, None)
    for f in (f0, frames[len(frames) // 3]['f'], frames[2 * len(frames) // 3]['f'], frames[-1]['f']):
        sc.frame_set(f)
        got = me.arm.matrix_world @ me.arm.pose.bones[hb].head
        want, _W = rig.bone_world(frames[f - f0], 'head')
        e = (got - want).length
        if e > err[0]:
            err = (e, f)
    R['keyed_head_err_mm'] = [round(1000 * err[0], 3), err[1]]
    R.check('keyed', err[0] < 0.001, f'the evaluated head bone is within {1000 * err[0]:.3f} mm of the bake\'s record '
                                     f'(worst frame {err[1]})')

    # ---- her spring chains (her hair) baked over the keyed take, as the engine's vrm.update steps them
    sp = rep.get('springs') or {}
    R['springs'] = {k: sp.get(k) for k in ('springs', 'joints', 'frames', 'keys', 'nan', 'max_tail_speed_mps', 'track')}
    R.check('springs', sp.get('springs', 0) > 0 and sp.get('nan') == 0 and sp.get('frames') == list(rep['frames']),
            f'{R["springs"]} (the controller family\'s bake_springs over the take my bake keyed)')

    # ---- my hands' work refuses her plainly
    try:
        hands.HandModel(rig, 'right')
        refused = None
    except ValueError as e:
        refused = str(e)
    R.check('hands_refused', refused is not None, f'HandModel on {CAST}: {refused}')

    # ---- the stills: a low side camera held over her walk's start, its stop and her turn on the spot, every two
    # frames (the debug overlays left out); her face on the lamp
    vbvh = S.solids_bvh([o for o in obs if o.name != 'lamp'])
    walk = [f0 + i for i, r in enumerate(recs) if r['mode'] == 'loco' and r.get('lead') == 'walk']
    shots, last = [], f0 + len(frames) - 1
    spans = [('walk_start', walk[0] - 6, walk[0] + 30), ('walk_stop', walk[-1] - 24, walk[-1] + 12)] if walk else []
    spans += [(f'turn{k + 1}', a - 3, b + 3) for k, (a, b, _d) in enumerate(rep['turns'][:2])]
    hide = [o.name for o in bpy.data.objects if o.name.startswith('robot_debug')]
    for name, a_, b_ in spans:
        a_, b_ = max(f0, a_), min(last, b_)
        shots += [dict(s, hide=hide) for s in S.strip(name, S.side_view(vbvh, frames, f0, a_, b_), a_, b_,
                                                       n=min(18, (b_ - a_) // 2 + 1))]
    if offs:
        ph, _W = rig.bone_world(frames[fb - f0], 'head')
        shots.append({'name': 'head_on_lamp', 'frame': int(fb), 'cam': [LAMP[0] + 0.15, GOAL[1] - 0.45, 1.65],
                      'target': list(ph.lerp(lamp_p, 0.5)), 'lens': 22.0})
    S.write_json('other_vrm_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'other_vrm.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'other_vrm', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
