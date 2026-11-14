"""My robot body navigating a room to a goal with its own sensors (VRMRobotBody + EidoverseRobotController + RobotDebug),
walking on the controller family's legs.

The room (8 x 6 m, walls 2.6 m): a partition across it with a 1.3 m doorway, a table, a crate standing just behind the
doorway (out of sight until the body is at the door), a shelf with a lamp. I start in the far corner facing the goal
and know nothing but the floor under my feet. The scene's direction is the JS's, awaited action by action:

    scan_area(100 deg, 2 s) -> walk_to(goal) -> look_at(the lamp) -> perform_action('wave_goodbye', 2 s)

Everything I learn comes through the sensor cone on my head (RobotSensors): the scan maps the partition and its doorway,
the plan goes through the doorway, the crate behind it is seen from the door and the route is replanned round it.
Checks (PASS / FAIL):
  - arrived: the walk_to resolved, and the keyed body stands within 0.1 m of the goal (the walk stops on it)
  - replanned on what it saw: at least one replan after the walk began (the crate)
  - the memory is the room: the blocked cells lie on the real geometry (within 0.15 m of a surface), none in the open
  - clearance: the keyed root keeps 0.3 m from every wall and obstacle; no hand or foot bone inside one
  - the walk: the controller family's checks.feet on every gait it played, and on the keyed result the least-moving
    sole point in contact moves at most 2 mm a frame anywhere in the film; the corners turn at most the controller's
    max_turn_rate (3.5 rad/s)
  - the gaze: the head's pan follows the scan (both ways past 35 deg) and settles on the lamp (the keyed head's facing
    within 10 deg of it before the wave)
  - the senses come from my head as the take has it (across within 1 cm; up by the plant's pelvis, set after the run)
Stills: out/nav_room_<moment>_<k>_f<frame>.png (the map, the route and the rays over the room from above; the body
walking; the start and the stop, low); out/nav_room.json, out/nav_room.blend.

    bash run_blender.sh blender/tests/robot_body/test_navigate_room.py --no-render
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
from mathutils.bvhtree import BVHTree  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402
from eidoblend.harness.navigation import STATE_BLOCKED  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
START, GOAL = (-3.0, -2.0), (2.7, 2.1)
LAMP = (3.55, 1.0, 1.95)
R = S.Report('nav_room')


def room():
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    wood_m = S.textured('table_wood', 'Wood066_1k', 1.2)
    crate_m = S.textured('crate_card', 'Cardboard002_1k', 1.5)
    metal_m = S.textured('shelf_metal', 'PaintedMetal012_1k', 1.0, tint=(0.42, 0.45, 0.5, 1.0))   # a grey steel shelf
    obs = []
    floor = S.box('floor', -4.0, 4.0, -3.0, 3.0, -0.05, 0.0, floor_m)
    H = 2.6
    obs += [S.box('wall_s', -4.1, 4.1, -3.1, -3.0, 0.0, H, wall_m), S.box('wall_n', -4.1, 4.1, 3.0, 3.1, 0.0, H, wall_m),
            S.box('wall_w', -4.1, -4.0, -3.0, 3.0, 0.0, H, wall_m), S.box('wall_e', 4.0, 4.1, -3.0, 3.0, 0.0, H, wall_m)]
    # the partition with its doorway (y 0.6 .. 1.9)
    obs += [S.box('partition_a', 0.45, 0.55, -3.0, 0.6, 0.0, H, wall_m),
            S.box('partition_b', 0.45, 0.55, 1.9, 3.0, 0.0, H, wall_m)]
    # the table (a top on four legs), the crate behind the doorway, a crate in the west half, the shelf with its lamp
    tb = [S.box('table_top', -2.1, -0.9, 0.45, 1.15, 0.72, 0.76, wood_m, 0.004)]
    for lx, ly in ((-2.05, 0.5), (-0.95, 0.5), (-2.05, 1.1), (-0.95, 1.1)):
        tb.append(S.box('table_leg', lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, 0.0, 0.72, wood_m))
    obs += tb
    obs.append(S.box('crate_behind_door', 1.6, 2.2, 0.95, 1.55, 0.0, 0.62, crate_m, 0.01))
    obs.append(S.box('crate_west', -1.9, -1.3, -1.9, -1.3, 0.0, 0.55, crate_m, 0.01))
    obs.append(S.box('shelf', 3.4, 3.95, 0.3, 1.7, 0.0, 1.8, metal_m, 0.006))
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
    obs.append(lamp)
    return floor, obs


def lights(sc):
    from eidoblend.characters.robot.example import studio_environment
    studio_environment(sc, 0.35, None)
    for name, loc, energy in (('ceiling_w', (-2.0, 0.0, 2.45), 260.0), ('ceiling_e', (2.4, 0.5, 2.45), 260.0),
                              ('ceiling_door', (0.5, 1.25, 2.45), 120.0)):
        S.area_light(sc, name, loc, energy, 1.2, (1.0, 0.93, 0.85))
    ld = bpy.data.lights.new('lamp_light', 'POINT')
    ld.energy = 40.0
    ld.color = (1.0, 0.75, 0.45)
    ld.shadow_soft_size = 0.12
    ob = bpy.data.objects.new('lamp_light', ld)
    ob.location = LAMP
    sc.collection.objects.link(ob)


def blocked_on_geometry(memory, obs):
    """the blocked cells' distance to the real geometry (a BVH over the obstacles), m"""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        b0 = len(verts)
        verts.extend(ev.matrix_world @ v.co for v in me.vertices)
        polys.extend([b0 + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    d = []
    for cx, cy, s in memory.get_known_cells():
        if s != STATE_BLOCKED:
            continue
        x, y = memory.cell_to_world(cx, cy)
        z = memory.get_cell_blocking_z(cx, cy)
        z = 1.0 if math.isnan(z) else z
        hit = bvh.find_nearest(Vector((x, y, z)))
        d.append(math.inf if hit[0] is None else (hit[0] - Vector((x, y, z))).xy.length)
    return bvh, np.array(d)


def main():
    sc = S.C.clean_scene(FPS)
    floor, obs = room()
    lights(sc)
    h0 = heading_of(GOAL[0] - START[0], GOAL[1] - START[1])
    me = load_vrm('claude_robot', name='claude', location=(START[0], START[1], 0.0), rotation=math.degrees(h0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + obs,          # the walkable world: the floor walked on, every solid walked round
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': h0, 'walk_speed': 0.9, 'agent_radius': 0.35},
        'memory': {'size': 12.0, 'cell_size': 0.1},
        'sensors': {'h_rays': 16, 'v_rays': 14, 'range': 6.0},
        'planner': {'agent_radius': 0.35}}, rig=rig)
    dbg = RobotDebug(body)
    for k in ('rays', 'map', 'path', 'landmarks'):
        getattr(dbg, 'show_' + k)(True)
    body.tag_landmark('door', 0.5, 1.25)
    outcome, marks = {}, {}

    def script(b):
        a = yield b.scan_area(yaw_range=100, duration=2.0)
        outcome['scan'] = a.state
        marks['walk'] = b.frame_count
        a = yield b.walk_to(*GOAL)
        outcome['walk_to'] = (a.state, str(a.error) if a.error else None)
        marks['arrived'] = b.frame_count
        b.tag_landmark('goal', *GOAL)
        a = yield b.look_at(*LAMP)
        outcome['look_at'] = a.state
        marks['wave'] = b.frame_count
        a = yield b.perform_action('wave_goodbye', 2.0)
        outcome['wave'] = a.state
    body.run(script(body))
    dt = 1.0 / FPS
    t_sim = time.time()
    f_done = None
    for k in range(FPS * 40):
        body.update(k * dt, dt)
        dbg.update()
        if body._script is None and f_done is None:
            f_done = k
        if f_done is not None and k >= f_done + FPS // 2:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t_sim, 2), 'outcome': outcome,
                'marks': marks, 'log': [(round(t, 2), e) for t, e in body.log], 'senses': len(body.readings),
                'explored_m2': round(body.memory.get_explored_area(), 2)}
    R.log('run', R['run'])
    t_b = time.time()
    rep = body.bake(face=lambda t: {'happy': 0.25}, action_name='claude|nav_room')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'stances', 'swings')}
    R['bake_s'] = round(time.time() - t_b, 1)
    sc.frame_start, sc.frame_end = rep['frames']
    objs = dbg.build(rep)
    R['debug_objects'] = {k: (o.name if o else None) for k, o in objs.items()}
    frames, recs = rep['_frames'], rep['_records']
    f0 = rep['frames'][0]

    # ---- checks
    stop = recs[marks['arrived'] - 1]['feet_world'] if marks.get('arrived') else recs[-1]['feet_world']
    dgoal = math.hypot(stop[0] - GOAL[0], stop[1] - GOAL[1])
    R.check('arrived', outcome.get('walk_to', ('',))[0] == 'resolved' and dgoal < 0.1,
            f'walk_to {outcome.get("walk_to")}; the walk stops {dgoal:.3f} m from the goal')
    walk_t = next((t for t, e in body.log if e.startswith('walk_to')), 0.0)
    replans = [(t, e) for t, e in body.log if e.startswith('replan') and t > walk_t]
    R.check('replanned_on_sight', len(replans) >= 1, f'{len(replans)} replans after the walk began: {replans[:4]}')
    bvh, dblk = blocked_on_geometry(body.memory, obs)
    good = float(np.mean(dblk <= 0.15)) if len(dblk) else 0.0
    R['memory'] = {'blocked_cells': int(len(dblk)), 'on_geometry_frac': round(good, 4),
                   'off_by_m_p95': round(float(np.percentile(dblk, 95)), 3) if len(dblk) else None,
                   'explored_m2': round(body.memory.get_explored_area(), 2)}
    R.check('memory_is_the_room', len(dblk) > 50 and good >= 0.97,
            f'{len(dblk)} blocked cells, {100 * good:.1f}% within 0.15 m of a real surface (95th pct '
            f'{R["memory"]["off_by_m_p95"]} m); explored {R["memory"]["explored_m2"]} m2')
    # clearance on the keyed result
    walls = [o for o in obs if o.name != 'lamp']
    _bvh_w, _d = blocked_on_geometry(body.memory, walls)
    root_min, root_at = math.inf, None
    limb = (math.inf, None, None)                         # (the signed distance, frame, bone): - inside a solid
    for fr in frames:
        p = fr['M'].translation
        for z in (0.3, 0.8, 1.3):
            hit = _bvh_w.find_nearest(Vector((p.x, p.y, z)))
            if hit[0] is not None and (hit[0] - Vector((p.x, p.y, z))).xy.length < root_min:
                root_min = (hit[0] - Vector((p.x, p.y, z))).xy.length
                root_at = (fr['f'], fr['mode'], round(p.x, 3), round(p.y, 3), [round(c, 3) for c in hit[0]])
        for n in ('leftHand', 'rightHand', 'leftFoot', 'rightFoot', 'leftLowerArm', 'rightLowerArm'):
            q, _W = rig.bone_world(fr, n)
            depth = S.depth_in(_bvh_w, q)
            d = -depth if depth > 0 else (_bvh_w.find_nearest(q)[0] - q).length
            if d < limb[0]:
                limb = (d, fr['f'], n)
    R['clearance_m'] = {'root_min': round(root_min, 3), 'limbs_min': [round(limb[0], 3), limb[1], limb[2]],
                        'root_min_at': root_at}
    R['plans'] = [(f, None if p is None else [(round(q['x'], 2), round(q['y'], 2)) for q in p]) for f, p in body.paths]
    R.check('clearance', root_min >= 0.3 and limb[0] > 0.0,
            f'the keyed root keeps {root_min:.3f} m from walls and obstacles; hands, forearms and feet at least '
            f'{R["clearance_m"]["limbs_min"]} (m, frame, bone)')
    # the walk: the controller family's checks.feet, the slip on the keyed result, the corners' rate
    slip = {}
    for s in ('left', 'right'):
        prev = None
        for fr in frames:
            P = rig.feet_world(fr)[s]
            low = P[:, 2] < 0.0025
            if prev is not None and low.any() and prev[1].any():
                both = low & prev[1]
                if both.any():
                    d = float(np.min(np.linalg.norm(P[both, :2] - prev[0][both, :2], axis=1)))
                    if d > slip.get(s, (0, 0))[0]:
                        slip[s] = (d, fr['f'], fr['mode'], fr['lead'])
            prev = (P, low)
    R['planted_slip_mm'] = {s: [round(1000 * v[0], 3)] + list(v[1:]) for s, v in slip.items()}
    hd = [r['heading'] for r in recs]
    rate = max((abs(math.remainder(hd[i + 1] - hd[i], 2 * math.pi)) * FPS for i in range(len(hd) - 1)
                if recs[i]['mode'] == 'loco' and recs[i + 1]['mode'] == 'loco'), default=0.0)
    fails = S.plant_failures(rep)
    R['controller_checks_feet'] = fails
    R.check('feet_hold', not fails and all(v[0] < 0.002 for v in slip.values()) and rate <= 3.5 * 1.02,
            f'the controller family\'s checks.feet: {len(rep["segments"]) - len(fails)} of {len(rep["segments"])} '
            f'gaits pass {[(f[0], f[1], f[2][:1]) for f in fails]}; on the keyed result the least-moving sole point in '
            f'contact two frames running moves at most {R["planted_slip_mm"]} (mm, frame, mode, gait); the heading '
            f'turns at most {rate:.2f} rad/s walking')
    # the gaze: the neck's pan through the scan and onto the lamp
    from eidoblend.characters._math import euler_from_quat, q_to_three
    pans = [math.degrees(euler_from_quat(q_to_three(fr['N']['neck']), 'YXZ')[1]) for fr in frames]
    R['neck_pan_deg'] = [round(min(pans), 1), round(max(pans), 1)]
    lamp_v = Vector(LAMP)
    on_lamp = []
    for fr in frames[marks['arrived'] - 1:marks['wave'] - 1]:
        p_, W_ = rig.bone_world(fr, 'head')
        on_lamp.append((round(math.degrees((W_ @ Vector((0.0, -1.0, 0.0))).angle(lamp_v - p_)), 2), fr['f']))
    R['head_on_lamp_deg'] = min(on_lamp) if on_lamp else None
    R.check('gaze_follows', min(pans) < -35 and max(pans) > 35 and bool(on_lamp) and min(on_lamp)[0] < 10.0,
            f'the neck pans {R["neck_pan_deg"]} deg through the film; between the walk and the wave my head comes to '
            f'{R["head_on_lamp_deg"]} (deg, frame) of the lamp')
    sh = S.sense_heads(body, rep)
    up_less_pelvis = max(abs(u - dz) for _a, u, dz, _f in sh)
    R['sense_head'] = {'senses': len(sh), 'across_max_m': round(sh[-1][0], 4),
                       'up_max_m': round(max(abs(u) for _a, u, _dz, _f in sh), 4),
                       'up_less_the_plant_pelvis_max_m': round(up_less_pelvis, 4)}
    R.check('senses from my head where the take has it', sh[-1][0] < 0.01 and up_less_pelvis < 0.01, f'{R["sense_head"]}')
    # the stills
    vbvh = S.solids_bvh(obs)
    shots = []
    walk_f = [f0 + i for i, r in enumerate(recs) if r['mode'] == 'loco' and r.get('lead') == 'walk']
    for name, f in (('scan', f0 + FPS), ('door', next((f0 + i for i, r in enumerate(recs) if r['feet_world'][0] > 0.2),
                                                       None)), ('arrive', marks.get('arrived')),
                    ('wave', f0 + len(frames) - FPS)):
        if f is not None:
            shots.append({'name': f'overview_{name}', 'frame': int(f), 'cam': [0.0, -2.6, 10.5], 'target': [0.0, 0.15, 0.0],
                          'lens': 30.0})
    # a low side camera held over the walk's start, its stop on the goal, and each turn on the spot, every two frames,
    # the debug overlays left out of them
    last = f0 + len(frames) - 1
    spans = []
    if walk_f:
        spans += [('feet_start', walk_f[0] - 6, walk_f[0] + 30), ('feet_stop', walk_f[-1] - 24, walk_f[-1] + 12)]
    spans += [(f'turn{k + 1}', a - 3, b + 3) for k, (a, b, _d) in enumerate(rep['turns'][:3])]
    hide = [n for n in R['debug_objects'].values() if n]
    for name, fa, fb in spans:
        fa, fb = max(f0, fa), min(last, fb)
        shots += [dict(s, hide=hide) for s in S.strip(name, S.side_view(vbvh, frames, f0, fa, fb), fa, fb,
                                                       n=min(18, (fb - fa) // 2 + 1))]
    S.write_json('nav_room_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'nav_room.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'nav_room', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
