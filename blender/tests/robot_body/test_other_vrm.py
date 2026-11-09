"""VRMRobotBody on a VRM that is not my robot body: robot_body.js drives ANY VRM (the engine's controller under it knows
nothing of my hardware), so here Aletheia (aletheia.vrm) senses, plans and walks with a plain RobotRig: her clips as
they are, the body's gaze on her head bone exactly as _applyHeadOverride sets it, her feet set down, and none of my
body's passes (joint limits, leg and arm clearances, head states, crown).

The room (7 x 5 m): a crate across her way and a lamp on a shelf. The scene's direction, awaited action by action:

    scan_area(90 deg, 1.5 s) -> walk_to(the far end) -> face_direction(the lamp 25 deg to her left)
        -> look_at(the lamp, hold) -> wait(1 s) -> perform_action('wave_goodbye', 2 s)

Checks (PASS / FAIL):
  - plain_rig: the rig knows she is not my body (hardware False), no correction was made to any joint (its stats empty),
    and on every standing frame after a hand-over her keyed arms, hands, fingers, spine, neck and hips are the clip's own
    pose (within 0.01 deg): no turn-out, no clamp, no re-homed clavicle
  - arrived: the walk_to resolved and the keyed body ends within 0.5 m of the goal, round the crate it saw
  - gaze_is_the_js: on every frame her head bone's own turn is _applyHeadOverride's Euler(pitch, yaw, 0, 'YXZ') of the
    body's gaze (re-aimed from where the keyed body stands: bake._aimed_gaze), her neck the clip's; holding the lamp her
    face is off it by no more than the clip's torso and neck turn her head (+2 deg): the JS aims the head bone from the
    body's heading alone
  - feet: the walks' planted feet (walk_path's report: slip <= 1 mm a frame, no swing touching) and both feet on the floor
    on the standing frames after each hand-over (within 3 mm: an emote may roll a planted foot a little onto its edge)
  - keyed: the saved action alone puts her head bone where the bake's records do (within 1 mm, evaluated)
  - hands_refused: my hands' work (hands.HandModel) refuses her plainly instead of failing deep inside
Stills: out/other_vrm_<moment>_f<k>.png; out/other_vrm.json, out/other_vrm.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_other_vrm.py [--no-render]
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
from eidoblend.characters._math import q_from_three  # noqa: E402
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody, hands  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402
from eidoblend.characters.vrma import load_clip  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
CAST = next((a for a in ARGS if not a.startswith('--')), 'aletheia')
FPS = 24
START, GOAL = (-2.6, -0.2), (2.4, 0.3)
LAMP = (3.2, 1.25, 1.52)
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'cast': CAST}
T0 = time.time()
OK = True


def log(*a):
    print('[other_vrm]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def material(name, tex, scale=1.0, tint=None, colour=(0.5, 0.5, 0.5, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ts = S.C.texture_set(tex) if tex else None
    if not ts:
        bsdf.inputs['Base Color'].default_value = colour
        return mat
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    for role, sock in (('color', 'Base Color'), ('rough', 'Roughness'), ('normal', None)):
        if not ts.get(role):
            continue
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(ts[role], check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if role == 'color' else 'Non-Color'
        n.projection, n.projection_blend = 'BOX', 0.2
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        if role == 'color' and tint:
            mx = nt.nodes.new('ShaderNodeMix')
            mx.data_type, mx.blend_type = 'RGBA', 'MULTIPLY'
            mx.inputs['Factor'].default_value = 1.0
            nt.links.new(n.outputs['Color'], mx.inputs['A'])
            mx.inputs['B'].default_value = tint
            nt.links.new(mx.outputs['Result'], bsdf.inputs['Base Color'])
        elif sock:
            nt.links.new(n.outputs['Color'], bsdf.inputs[sock])
        else:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(n.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
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
    me.materials.append(mat)
    return ob


try:
    sc = S.C.clean_scene(FPS)
    floor_m = material('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = material('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    crate_m = material('crate_card', 'Cardboard002_1k', 1.5)
    shelf_m = material('shelf_metal', 'PaintedMetal012_1k', 1.0, tint=(0.42, 0.45, 0.5, 1.0))
    floor = box('floor', -3.5, 3.5, -2.5, 2.5, -0.05, 0.0, floor_m)
    H = 2.6
    obs = [box('wall_s', -3.6, 3.6, -2.6, -2.5, 0.0, H, wall_m), box('wall_n', -3.6, 3.6, 2.5, 2.6, 0.0, H, wall_m),
           box('wall_w', -3.6, -3.5, -2.5, 2.5, 0.0, H, wall_m), box('wall_e', 3.5, 3.6, -2.5, 2.5, 0.0, H, wall_m),
           box('crate', -0.45, 0.35, -0.9, 0.7, 0.0, 0.85, crate_m, 0.01),
           box('shelf', 2.9, 3.45, 0.8, 1.7, 0.0, 1.4, shelf_m, 0.006)]
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
    for name, loc, energy in (('ceiling_w', (-1.8, 0.0, 2.45), 260.0), ('ceiling_e', (1.8, 0.4, 2.45), 260.0)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy, ld.size, ld.color = energy, 1.2, (1.0, 0.93, 0.85)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)
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
    outcome = {}
    marks = {}

    def script(b):
        a = yield b.scan_area(yaw_range=90, duration=1.5)
        outcome['scan'] = a.state
        a = yield b.walk_to(*GOAL)
        outcome['walk_to'] = (a.state, str(a.error) if a.error else None)
        p_ = b.get_position()                         # she turns (on her feet, in the bake) to have the lamp 25 deg left
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
    log('run', R['run'])
    rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * np.asarray(x)), face=lambda t: {'happy': 0.3},
                    action_name=f'{CAST}|other_vrm')
    sc.frame_start, sc.frame_end = rep['frames']
    objs = dbg.build(rep)
    frames = rep['_frames']
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'walks')}

    # ---- plain_rig: her clips as they are
    clip = load_clip(me, 'idle')
    kept = ('hips', 'spine', 'chest', 'upperChest', 'neck', 'leftShoulder', 'rightShoulder', 'leftUpperArm',
            'rightUpperArm', 'leftLowerArm', 'rightLowerArm', 'leftHand', 'rightHand', 'leftIndexProximal',
            'rightThumbProximal', 'leftLittleDistal')
    kept = [n for n in kept if n in me.humanoid]
    worst, judged = (0.0, None, None), 0
    per_bone = {}
    for fr in frames:
        if fr['src'] != ('stand', 'idle', None):
            continue
        tc = (fr['f'] - rep['frames'][0]) * dt + dt         # the bake's idle clock: the film's time plus one step
        p3, _off = rig.clip_pose(clip, tc)                  # (as the bake sums it: at a loop's seam the last bit counts)
        judged += 1
        for n in kept:
            a = math.degrees(fr['N'][n].rotation_difference(q_from_three(p3[n])).angle)
            per_bone[n] = max(per_bone.get(n, 0.0), round(a, 5))
            if a > worst[0]:
                worst = (a, fr['f'], n)
    R['plain_rig'] = {'hardware': rig.hardware, 'stats': rig.stats, 'standing_frames_judged': judged,
                      'worst_deg': [round(worst[0], 5), worst[1], worst[2]], 'per_bone_deg': per_bone,
                      'src_around_worst': [(fr['f'], fr['src']) for fr in frames
                                           if worst[1] and abs(fr['f'] - worst[1]) <= 3]}
    check('plain_rig', rig.hardware is False and not rig.stats and judged > 20 and worst[0] < 0.01,
          f'hardware {rig.hardware}, joint corrections {rig.stats or "none"}; on {judged} standing frames her keyed '
          f'{", ".join(kept[:6])} ... are the idle\'s own within {worst[0]:.5f} deg (worst at frame {worst[1]}, {worst[2]})')

    # ---- arrived
    walk_frames = [fr for fr in frames if fr['src'][0] == 'walk']
    last = (walk_frames[-1] if walk_frames else frames[-1])['M'].translation
    end = frames[-1]['M'].translation
    dgoal = math.hypot(end.x - GOAL[0], end.y - GOAL[1])
    crate_min = math.inf
    for fr in walk_frames:
        p = fr['M'].translation
        dx = max(-0.45 - p.x, 0.0, p.x - 0.35)
        dy = max(-0.9 - p.y, 0.0, p.y - 0.7)
        crate_min = min(crate_min, math.hypot(dx, dy))
    R['arrived'] = {'from_goal_m': round(dgoal, 3), 'root_to_crate_min_m': round(crate_min, 3)}
    check('arrived', outcome.get('walk_to', ('',))[0] == 'resolved' and dgoal < 0.5 and crate_min > 0.25,
          f'walk_to {outcome.get("walk_to")}; the keyed body ends {dgoal:.3f} m from the goal, its root at least '
          f'{crate_min:.3f} m from the crate it walked round')

    # ---- the gaze: robot_body.js's _applyHeadOverride on her head bone, every frame, and on the lamp while it holds
    from eidoblend.characters._math import quat_from_euler
    lamp_p = Vector(LAMP)
    legs_rec = body.controller.char_ctrl.record
    f_map = rep['map']
    film_of = {}
    for j, i in enumerate(f_map):
        film_of.setdefault(i, rep['frames'][0] + j)
    from eidoblend.characters.robot.bake import _aimed_gaze
    head_err = (0.0, None)
    for j, fr in enumerate(frames):
        g = _aimed_gaze(rig, fr, legs_rec[f_map[j]])        # the live gaze, re-aimed from where the keyed body stands
        if g is None:
            continue
        want = q_from_three(quat_from_euler(g[1], g[0], 0.0, 'YXZ'))
        a = math.degrees(fr['N']['head'].rotation_difference(want).angle)
        if a > head_err[0]:
            head_err = (a, fr['f'])
    fa = film_of.get(marks.get('look_from', 0) + 2)
    fb = film_of.get(marks.get('look_to', 0) - 1)
    offs, chain, neck_off, aim_err, live_err = [], [], 0.0, [], []
    for fr in frames:
        if fa is None or fb is None or not (fa <= fr['f'] <= fb):
            continue
        p, W = rig.bone_world(fr, 'head')
        fwd = W @ Vector((0.0, -1.0, 0.0))
        offs.append((round(math.degrees(fwd.angle(lamp_p - p)), 2), fr['f']))
        # the part of that the clip's own torso and neck make (the JS aims the head from the body's heading alone)
        _pn, Wn = rig.bone_world(fr, 'neck')
        Mq = fr['M'].to_quaternion()
        chain.append(round(math.degrees((Mq.inverted() @ Wn).angle), 2))
        hk = 2.0 * math.atan2(Mq.z, Mq.w)
        fv = Vector((math.sin(hk), -math.cos(hk)))
        d_ = lamp_p - p
        lz_, lx_ = d_.x * fv.x + d_.y * fv.y, d_.x * (-fv.y) + d_.y * fv.x
        g = _aimed_gaze(rig, fr, legs_rec[f_map[fr['f'] - rep['frames'][0]]]) or (0.0, 0.0)
        g_live = legs_rec[f_map[fr['f'] - rep['frames'][0]]].get('gaze') or (0.0, 0.0)
        live_err.append(round(math.degrees(math.atan2(lx_, lz_) - g_live[0]), 2))
        aim_err.append((round(math.degrees(math.atan2(lx_, lz_) - g[0]), 2),
                        round(math.degrees(-math.atan2(d_.z, math.hypot(lx_, lz_)) - g[1]), 2), fr['f']))
        tc = (fr['f'] - rep['frames'][0]) * dt + dt
        if fr['src'] == ('stand', 'idle', None):
            p3, _o = rig.clip_pose(clip, tc)
            neck_off = max(neck_off, math.degrees(fr['N']['neck'].rotation_difference(q_from_three(p3['neck'])).angle))
    R['gaze'] = {'head_local_vs_js_deg': [round(head_err[0], 5), head_err[1]], 'frames': [fa, fb],
                 'facing_off_lamp_deg': offs, 'torso_and_neck_turn_deg': chain, 'neck_vs_clip_deg': round(neck_off, 5),
                 'keyed_aim_less_applied_gaze_deg': aim_err, 'keyed_aim_less_live_gaze_yaw_deg': live_err}
    check('gaze_is_the_js', head_err[0] < 0.01 and bool(offs) and neck_off < 0.01 and max(offs)[0] <= max(chain) + 2.0,
          f'on every frame her head bone\'s own turn is _applyHeadOverride\'s Euler(pitch, yaw, 0, YXZ) of the body\'s '
          f'gaze (re-aimed from where the keyed body stands: the live run aimed it {min(live_err)}-{max(live_err)} deg '
          f'off for this body) within {head_err[0]:.5f} deg; her neck stays the clip\'s within {neck_off:.5f} deg; '
          f'holding the lamp (frames {fa}-{fb}) her face is {min(offs)[0]}-{max(offs)[0]} deg off it, no more than the '
          f'clip\'s torso and neck turn her head ({min(chain)}-{max(chain)} deg: the JS aims the head bone from the '
          f'body\'s heading alone)')

    # ---- feet
    wr = rep['walks']
    worst_walk = max((w['worst'].get('slip_mm_per_frame_max', 0.0) for w in wr), default=0.0)
    touches = sum(w['worst'].get('swing_touch_frames', 0) for w in wr)
    stand_gap, gap_at = 0.0, None
    for fr in frames:
        if fr['src'][0] != 'stand' or fr['src'][2] is not None:
            continue
        for s, P in rig.feet_world(fr).items():
            g_ = float(P[:, 2].min())
            if abs(g_) > stand_gap:
                stand_gap, gap_at = abs(g_), (fr['f'], s, round(1000 * g_, 2), fr['src'])
    R['feet'] = {'walk_slip_mm': worst_walk, 'swing_touch_frames': touches, 'standing_gap_mm': round(1000 * stand_gap, 2),
                 'standing_gap_at': gap_at}
    check('feet', worst_walk <= 1.0 and touches == 0 and stand_gap < 0.003,
          f'{len(wr)} walk(s): planted slip at most {worst_walk} mm a frame, {touches} swing frames touching; standing, '
          f'each foot\'s lowest sole point within {1000 * stand_gap:.2f} mm of the floor')

    # ---- keyed: the action alone puts the head where the records do
    hb = me.humanoid['head']
    err = (0.0, None)
    for f in (1, frames[len(frames) // 3]['f'], frames[2 * len(frames) // 3]['f'], frames[-1]['f']):
        sc.frame_set(f)
        got = me.arm.matrix_world @ me.arm.pose.bones[hb].head
        want, _W = rig.bone_world(frames[f - rep['frames'][0]], 'head')
        e = (got - want).length
        if e > err[0]:
            err = (e, f)
    R['keyed_head_err_mm'] = [round(1000 * err[0], 3), err[1]]
    check('keyed', err[0] < 0.001, f'the evaluated head bone is within {1000 * err[0]:.3f} mm of the bake\'s record '
                                   f'(worst frame {err[1]})')

    # ---- my hands' work refuses her plainly
    try:
        hands.HandModel(rig, 'right')
        refused = None
    except ValueError as e:
        refused = str(e)
    check('hands_refused', refused is not None, f'HandModel on {CAST}: {refused}')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'other_vrm.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        shots = {}
        cam = S.C.camera('cam', 30.0)
        wf = [fr['f'] for fr in walk_frames]
        picks = {'walk': (wf[0] + wf[-1]) // 2 if wf else 1, 'look': fb or frames[-1]['f'],
                 'wave': frames[-1]['f'] - FPS}
        # the overview with what she sees and knows (the rays, the map, the path); the shots of her without the rays
        S.C.aim(cam, (0.0, -2.0, 9.0), (0.0, 0.0, 0.0))
        p = os.path.join(S.OUT, f'other_vrm_overview_walk_f{picks["walk"]:03d}.png')
        shots[os.path.basename(p)] = S.C.still(sc, cam, picks['walk'], p)
        dbg.show_rays(False)
        wide = S.C.camera('wide', 26.0)                     # lens mm
        vbvh = S.solids_bvh([o for o in obs if o.name != 'lamp'])
        for name in ('walk', 'wave'):
            f = picks[name]
            fr = frames[f - rep['frames'][0]]
            pp = fr['M'].translation
            hd = fr['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))
            side = Vector((-hd.y, hd.x, 0.0))
            tgt = pp + Vector((0.0, 0.0, 0.8))
            cpos = S.best_view(vbvh, tgt, [pp + s_ * side * 2.2 + hd * 1.0 + Vector((0, 0, 1.4)) for s_ in (1, -1)])
            S.C.aim(wide, cpos, tgt)
            p = os.path.join(S.OUT, f'other_vrm_{name}_f{f:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, wide, f, p)
        # her face turned to the lamp: from beside the shelf, south of the lamp (she faces east-north-east at the goal,
        # the lamp 25 deg to her left), her face and the lamp in one frame
        f = picks['look']
        fr = frames[f - rep['frames'][0]]
        ph, _W = rig.bone_world(fr, 'head')
        mid = ph.lerp(lamp_p, 0.5)
        face_cam = S.C.camera('face', 22.0)
        S.C.aim(face_cam, Vector((LAMP[0] + 0.15, GOAL[1] - 0.45, 1.65)), mid)
        p = os.path.join(S.OUT, f'other_vrm_head_on_lamp_f{f:03d}.png')
        shots[os.path.basename(p)] = S.C.still(sc, face_cam, f, p)
        R['renders'] = shots
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('other_vrm.json', R)
log('done', R['ok'], R['seconds'], 's')
