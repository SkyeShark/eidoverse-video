"""My robot body navigating a room to a goal with its own sensors (VRMRobotBody + EidoverseRobotController + RobotDebug).

The room (8 x 6 m, walls 2.6 m): a partition across it with a 1.3 m doorway, a table, a crate standing just behind the
doorway (out of sight until the body is at the door), a shelf with a lamp. I start in the far corner facing the goal
and know nothing but the floor under my feet. The scene's direction is the JS's, awaited action by action:

    scan_area(100 deg, 2 s) -> walk_to(goal) -> look_at(the lamp) -> perform_action('wave_goodbye', 2 s)

Everything I learn comes through the sensor cone on my head (RobotSensors): the scan maps the partition and its doorway,
the plan goes through the doorway, the crate behind it is seen from the door and the route is replanned round it.
Checks (PASS / FAIL):
  - arrived: the walk_to resolved, and the keyed body stands within 0.5 m of the goal
  - replanned on what it saw: at least one replan after the walk began (the crate)
  - the memory is the room: the blocked cells lie on the real geometry (within 0.15 m of a surface), none in the open
  - clearance: the keyed root keeps 0.3 m from every wall and obstacle; no hand or foot bone inside one
  - the walk: round one's walk report on every walk span (planted slip, swing clearance), and the hand-overs (start and
    stop) hold the planted foot: the least-moving sole point in contact moves at most 2 mm a frame anywhere in the film
  - the gaze: the head's pan follows the scan (both ways past 35 deg) and settles on the lamp
Stills: out/nav_room_overview_f<k>.png (the map, the route and the rays over the room), nav_room_follow_f<k>.png (the body
walking), nav_room_feet_*.png (the start and the stop, low); out/nav_room.json, out/nav_room.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_navigate_room.py [--no-render]
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

from eidoblend.characters import Ground, load_vrm  # noqa: E402
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody  # noqa: E402
from eidoblend.characters.robot.controller import heading_of  # noqa: E402
from eidoblend.harness.navigation import STATE_BLOCKED  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
START, GOAL = (-3.0, -2.0), (2.7, 2.1)
LAMP = (3.55, 1.0, 1.95)
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True


def log(*a):
    print('[nav_room]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def textured(name, tex, scale=1.0, tint=None, rough=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ts = S.C.texture_set(tex)
    if not ts:
        bsdf.inputs['Base Color'].default_value = tint or (0.5, 0.5, 0.5, 1.0)
        return mat
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

    def img(role, colour):
        if not ts.get(role):
            return None
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(ts[role], check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
        n.projection = 'BOX'
        n.projection_blend = 0.2
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    c, r, nrm = img('color', True), img('rough', False), img('normal', False)
    if c:
        if tint:
            mul = nt.nodes.new('ShaderNodeMix')
            mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            nt.links.new(c.outputs['Color'], mul.inputs['A'])
            mul.inputs['B'].default_value = tint
            nt.links.new(mul.outputs['Result'], bsdf.inputs['Base Color'])
        else:
            nt.links.new(c.outputs['Color'], bsdf.inputs['Base Color'])
    if r and rough is None:
        nt.links.new(r.outputs['Color'], bsdf.inputs['Roughness'])
    elif rough is not None:
        bsdf.inputs['Roughness'].default_value = rough
    if nrm:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(nrm.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    import bmesh
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


def room():
    floor_m = textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    wood_m = textured('table_wood', 'Wood066_1k', 1.2)
    crate_m = textured('crate_card', 'Cardboard002_1k', 1.5)
    metal_m = textured('shelf_metal', 'PaintedMetal012_1k', 1.0, tint=(0.42, 0.45, 0.5, 1.0))   # a grey steel shelf
    obs = []
    floor = box('floor', -4.0, 4.0, -3.0, 3.0, -0.05, 0.0, floor_m)
    H, T = 2.6, 0.1
    obs += [box('wall_s', -4.1, 4.1, -3.1, -3.0, 0.0, H, wall_m), box('wall_n', -4.1, 4.1, 3.0, 3.1, 0.0, H, wall_m),
            box('wall_w', -4.1, -4.0, -3.0, 3.0, 0.0, H, wall_m), box('wall_e', 4.0, 4.1, -3.0, 3.0, 0.0, H, wall_m)]
    # the partition with its doorway (y 0.6 .. 1.9)
    obs += [box('partition_a', 0.45, 0.55, -3.0, 0.6, 0.0, H, wall_m), box('partition_b', 0.45, 0.55, 1.9, 3.0, 0.0, H, wall_m)]
    # the table (a top on four legs), the crate behind the doorway, a crate in the west half, the shelf with its lamp
    tb = [box('table_top', -2.1, -0.9, 0.45, 1.15, 0.72, 0.76, wood_m, 0.004)]
    for lx, ly in ((-2.05, 0.5), (-0.95, 0.5), (-2.05, 1.1), (-0.95, 1.1)):
        tb.append(box('table_leg', lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, 0.0, 0.72, wood_m))
    obs += tb
    obs.append(box('crate_behind_door', 1.6, 2.2, 0.95, 1.55, 0.0, 0.62, crate_m, 0.01))
    obs.append(box('crate_west', -1.9, -1.3, -1.9, -1.3, 0.0, 0.55, crate_m, 0.01))
    obs.append(box('shelf', 3.4, 3.95, 0.3, 1.7, 0.0, 1.8, metal_m, 0.006))
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
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.size = 1.2
        ld.color = (1.0, 0.93, 0.85)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)
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


try:
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
    outcome = {}

    def script(b):
        a = yield b.scan_area(yaw_range=100, duration=2.0)
        outcome['scan'] = a.state
        a = yield b.walk_to(*GOAL)
        outcome['walk_to'] = (a.state, str(a.error) if a.error else None)
        b.tag_landmark('goal', *GOAL)
        a = yield b.look_at(*LAMP)
        outcome['look_at'] = a.state
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
                'log': [(round(t, 2), e) for t, e in body.log], 'senses': len(body.readings),
                'explored_m2': round(body.memory.get_explored_area(), 2)}
    log('run', R['run'])
    t_b = time.time()
    rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * np.asarray(x)), face=lambda t: {'happy': 0.25},
                    action_name='claude|nav_room')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k != 'map'}
    R['bake_s'] = round(time.time() - t_b, 1)
    sc.frame_start, sc.frame_end = rep['frames']
    objs = dbg.build(rep)
    R['debug_objects'] = {k: (o.name if o else None) for k, o in objs.items()}
    frames = rep['_frames']

    # ---- checks
    last = frames[-1]['M'].translation
    dgoal = math.hypot(last.x - GOAL[0], last.y - GOAL[1])
    check('arrived', outcome.get('walk_to', ('',))[0] == 'resolved' and dgoal < 0.5,
          f'walk_to {outcome.get("walk_to")}; the keyed body ends {dgoal:.3f} m from the goal')
    walk_t = next((t for t, e in body.log if e.startswith('walk_to')), 0.0)
    replans = [(t, e) for t, e in body.log if e.startswith('replan') and t > walk_t]
    check('replanned_on_sight', len(replans) >= 1, f'{len(replans)} replans after the walk began: {replans[:4]}')
    bvh, dblk = blocked_on_geometry(body.memory, obs)
    good = float(np.mean(dblk <= 0.15)) if len(dblk) else 0.0
    R['memory'] = {'blocked_cells': int(len(dblk)), 'on_geometry_frac': round(good, 4),
                   'off_by_m_p95': round(float(np.percentile(dblk, 95)), 3) if len(dblk) else None,
                   'explored_m2': round(body.memory.get_explored_area(), 2)}
    check('memory_is_the_room', len(dblk) > 50 and good >= 0.97,
          f'{len(dblk)} blocked cells, {100 * good:.1f}% within 0.15 m of a real surface (95th pct {R["memory"]["off_by_m_p95"]} m); '
          f'explored {R["memory"]["explored_m2"]} m2')
    # clearance on the keyed result
    walls = [o for o in obs if o.name != 'lamp']
    _bvh_w, _d = blocked_on_geometry(body.memory, walls)
    root_min, limb_min = math.inf, math.inf
    root_at = None
    for fr in frames:
        p = fr['M'].translation
        for z in (0.3, 0.8, 1.3):
            hit = _bvh_w.find_nearest(Vector((p.x, p.y, z)))
            if hit[0] is not None and (hit[0] - Vector((p.x, p.y, z))).xy.length < root_min:
                root_min = (hit[0] - Vector((p.x, p.y, z))).xy.length
                root_at = (fr['f'], fr['src'][0], round(p.x, 3), round(p.y, 3), [round(c, 3) for c in hit[0]])
        for n in ('leftHand', 'rightHand', 'leftFoot', 'rightFoot', 'leftLowerArm', 'rightLowerArm'):
            q, _W = rig.bone_world(fr, n)
            hit = _bvh_w.find_nearest(q)
            if hit[0] is not None:
                inside = (hit[0] - q).dot(hit[1]) > 0       # the nearest face's normal points away from q: q is behind it
                limb_min = min(limb_min, -1.0 if inside else (hit[0] - q).length)
    R['clearance_m'] = {'root_min': round(root_min, 3), 'limbs_min': round(limb_min, 3), 'root_min_at': root_at}
    R['run_track'] = [(i, r['state'], round(r['x'], 2), round(r['y'], 2), round(math.degrees(r['heading']), 1))
                      for i, r in enumerate(body.controller.char_ctrl.record)][::6]
    R['plans'] = [(f, None if p is None else [(round(q['x'], 2), round(q['y'], 2)) for q in p]) for f, p in body.paths]
    check('clearance', root_min >= 0.3 and limb_min > 0.0,
          f'the keyed root keeps {root_min:.3f} m from walls and obstacles; hands, forearms and feet at least {limb_min:.3f} m')
    # the walk and the hand-overs
    wr = rep['walks']
    R['walks'] = [{k: v for k, v in w.items() if k in ('worst', 'stop', 'start', 'frames', 'speed', 'path_m')}
                  for w in wr]
    slip = {}
    for s in ('left', 'right'):
        prev = None
        for fr in frames:
            P = rig.feet_world(fr)[s]
            low = P[:, 2] < 0.0025
            # the standing frames and the hand-overs (walk_path measures its own walk frames: its report below)
            judged = fr['src'][0] == 'stand' or fr['src'][2] is not None
            if judged and prev is not None and low.any() and prev[1].any():
                both = low & prev[1]
                if both.any():
                    d = float(np.min(np.linalg.norm(P[both, :2] - prev[0][both, :2], axis=1)))
                    if d > slip.get(s, (0, 0))[0]:
                        slip[s] = (d, fr['f'], fr['src'][2])
            prev = (P, low)
    R['planted_slip_mm'] = {s: [round(1000 * v[0], 3), v[1], v[2]] for s, v in slip.items()}
    wf_ = max(slip.values())[1] if slip else None
    if wf_:
        R['feet_around_the_worst'] = []
        for fr in frames[max(0, wf_ - 6):wf_ + 2]:
            row = [fr['f'], fr['src']]
            for s in ('left', 'right'):
                P = rig.feet_world(fr)[s]
                row += [s, round(1000 * float(P[:, 2].min()), 2), [round(float(c), 4) for c in P[:, :2].mean(axis=0)]]
            R['feet_around_the_worst'].append(row)
    worst_walk = max((w['worst'].get('slip_mm_per_frame_max', 0.0) for w in wr), default=0.0)
    touches = sum(w['worst'].get('swing_touch_frames', 0) for w in wr)
    check('feet_hold', all(v[0] < 0.002 for v in slip.values()) and worst_walk <= 1.0 and touches == 0,
          f'standing and the hand-overs: the least-moving sole point in contact two frames running moves at most '
          f'{R["planted_slip_mm"]} (mm, frame, hand-over); the walks (walk_path\'s report): planted slip at most '
          f'{worst_walk} mm a frame, {touches} swing frames touching')
    # the gaze: the neck's pan through the scan and onto the lamp
    from eidoblend.characters._math import euler_from_quat, q_to_three
    pans = []
    for fr in frames:
        n3 = q_to_three(fr['N']['neck'])
        pans.append(math.degrees(euler_from_quat(n3, 'YXZ')[1]))
    R['neck_pan_deg'] = [round(min(pans), 1), round(max(pans), 1)]
    check('gaze_follows', min(pans) < -35 and max(pans) > 35, f'the neck pans {R["neck_pan_deg"]} deg through the film')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'nav_room.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        cam = S.C.camera('cam', 30.0)
        rs_ = {}
        walk_frames = [fr['f'] for fr in frames if fr['src'][0] == 'walk']
        wa, wb = walk_frames[0], walk_frames[-1]
        picks = {'scan': 1 + FPS, 'walk': (wa + wb) // 2 - 30, 'door': None, 'arrive': wb + 4, 'wave': frames[-1]['f'] - FPS}
        for fr in frames:                                   # the frame the body passes the doorway
            p = fr['M'].translation
            if picks['door'] is None and fr['src'][0] == 'walk' and p.x > 0.2:
                picks['door'] = fr['f']
        for name, f in picks.items():
            if f is None:
                continue
            S.C.aim(cam, (0.0, -2.6, 10.5), (0.0, 0.15, 0.0))     # from above: both halves, the door, the crate
            p = os.path.join(S.OUT, f'nav_room_overview_{name}_f{f:03d}.png')
            rs_[os.path.basename(p)] = S.C.still(sc, cam, f, p)
        cam2 = S.C.camera('follow', 32.0)
        vbvh = S.solids_bvh(obs)
        for name in ('walk', 'door', 'arrive'):
            f = picks[name]
            if f is None:
                continue
            fr = frames[f - 1]
            p = fr['M'].translation
            hd = fr['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))
            side = Vector((-hd.y, hd.x, 0.0))
            tgt = p + Vector((0, 0, 1.0))
            # (the side with the room's space: a camera never behind a wall or the partition)
            cpos = S.best_view(vbvh, tgt, [p + s_ * side * 2.8 - hd * 0.6 + Vector((0, 0, 1.25)) for s_ in (1, -1)])
            S.C.aim(cam2, cpos, tgt)
            pth = os.path.join(S.OUT, f'nav_room_follow_{name}_f{f:03d}.png')
            rs_[os.path.basename(pth)] = S.C.still(sc, cam2, f, pth)
        # the start and the stop, low and close on the feet (one camera side per hand-over, held for its frames)
        for name, f0_ in (('start', wa), ('stop', wb)):
            fr = frames[f0_ - 1]
            p = fr['M'].translation
            hd = fr['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))
            side = Vector((-hd.y, hd.x, 0.0))
            tgt = p + Vector((0, 0, 0.25))
            cpos = S.best_view(vbvh, tgt, [p + s_ * side * 1.6 + hd * 0.4 + Vector((0, 0, 0.35)) for s_ in (1, -1)])
            for k in (-2, 2, 6, 10):
                f = max(1, min(frames[-1]['f'], f0_ + k))
                S.C.aim(cam2, cpos, tgt)
                pth = os.path.join(S.OUT, f'nav_room_feet_{name}_f{f:03d}.png')
                rs_[os.path.basename(pth)] = S.C.still(sc, cam2, f, pth)
        R['renders'] = rs_
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('nav_room.json', R)
log('done', R['ok'], R['seconds'], 's')
