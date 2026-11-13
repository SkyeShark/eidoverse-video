"""My embodied robot seeing what moves during its run (robot_sensors.js casts against the live scene each sense): a door
that opens, a cart that crosses the room. VRMRobotBody.update(t, dt) sets the scene to the frame for t where the sensed
world has moving objects, and the sensors rebuild their view of it each sense.

A room (8 x 7 m) split by a wall with a 1.4 m doorway, its lintel over it at 2.1-2.6 m (a collider with the walls: my
legs' probes read the floor under it, as I walk beneath it); its sliding door is shut, and slides open behind the wall at
3.0-4.0 s. A cart rolls 2.6 m across my way in the far half at 8.2-9.8 s, past the doorway as I walk up to it, and
stands beside my goal. The scene's direction, awaited action by action:

    scan_area -> walk_to(behind the wall) [no path: the door is shut] -> until 4.3 s -> scan_area (the door open)
    -> walk_to(behind the wall) [through the doorway; the cart crossing ahead]

The door and the cart are not walls the legs walk against (the JS builds its Rapier colliders once, at create): what
keeps me off them is what my sensors see. Checks (PASS / FAIL):
  - the shut door is seen as shut: the first walk_to is rejected ('no path'), the doorway's cells blocked then
  - the open door is seen as open: the doorway's cells free after the second scan, the walk resolves through it
  - the lintel over the doorway is over my head: no move plays, my feet stay on the floor through the doorway
  - every sensor hit on the door and on the cart lies on its surface as the scene has it at that sense's frame (within
    1 cm), where the one snapshot at the first frame would put the cart's hits metres off
  - the cart is seen and avoided: a replan while it is in view, and my keyed root at least 0.35 m from it on every
    frame
  - what it costs: the sensors' rebuild (s), made only at the senses where the door or the cart had moved since the
    last, of the movers' view alone after the first (RobotSensors.refresh(dynamic=, dynamic_only=)); what the cart
    left in the memory at the end (reported)
Stills: out/moving_<moment>_<k>_f<frame>.png (the door and the cart with what I see of them; the walk through the
doorway from a low side camera); out/moving.json, out/moving.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_moving.py --no-render
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
from eidoblend.harness.navigation import STATE_BLOCKED, STATE_FREE  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
R = S.Report('moving')
START, H0 = (0.3, -2.1), math.pi                    # facing +Y, the door ahead
WALL_Y, DOOR_X = 0.5, (-0.7, 0.7)                    # the dividing wall and its doorway
GOAL = (1.3, 3.0)
DOOR_OPEN = (3.0, 4.0)                               # s: the door slides open
CART_T, CART_Y, CART_X = (8.2, 9.8), 2.0, (-0.6, 2.0)   # s: the cart rolls x -0.6 -> 2.0 at y 2.0, then stands
NORTH = 4.0                                          # the far half runs to y 4.0: room past the cart either way


def scene():
    floor_m = S.textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = S.textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    door_m = S.textured('door_wood', 'Wood066_1k', 1.0)
    cart_m = S.textured('cart_metal', 'PaintedMetal012_1k', 1.0, tint=(0.55, 0.2, 0.15, 1.0))
    floor = S.box('floor', -4.0, 4.0, -3.0, NORTH, -0.05, 0.0, floor_m)
    H = 2.6
    walls = [S.box('wall_n', -4.1, 4.1, NORTH, NORTH + 0.1, 0.0, H, wall_m),
             S.box('wall_s', -4.1, 4.1, -3.1, -3.0, 0.0, H, wall_m),
             S.box('wall_w', -4.1, -4.0, -3.0, NORTH, 0.0, H, wall_m),
             S.box('wall_e', 4.0, 4.1, -3.0, NORTH, 0.0, H, wall_m),
             S.box('divider_w', -4.0, DOOR_X[0], WALL_Y - 0.05, WALL_Y + 0.05, 0.0, H, wall_m),
             S.box('divider_e', DOOR_X[1], 4.0, WALL_Y - 0.05, WALL_Y + 0.05, 0.0, H, wall_m),
             # the lintel over the doorway, a collider like the rest of the wall: over my head, it is walked under
             S.box('lintel', DOOR_X[0], DOOR_X[1], WALL_Y - 0.05, WALL_Y + 0.05, 2.1, H, wall_m)]
    # the door: a sliding leaf in the doorway, just on the far side of the wall, sliding east behind it to open
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    w = DOOR_X[1] - DOOR_X[0]
    door = S.box('door', 0.0, w, -0.02, 0.02, 0.0, 2.08, door_m)
    for t, dx in ((0.0, 0.0), (DOOR_OPEN[0], 0.0), (DOOR_OPEN[1], w + 0.05)):
        door.location = (DOOR_X[0] + dx, WALL_Y + 0.08, 0.0)
        door.keyframe_insert('location', frame=1 + int(round(t * FPS)))
    cart = S.box('cart', -0.4, 0.4, -0.3, 0.3, 0.0, 0.9, cart_m, 0.01)
    for t, x in ((0.0, CART_X[0]), (CART_T[0], CART_X[0]), (CART_T[1], CART_X[1])):
        cart.location = (x, CART_Y, 0.0)
        cart.keyframe_insert('location', frame=1 + int(round(t * FPS)))
    return floor, walls, door, cart


def evaluated_bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bvh = BVHTree.FromPolygons([ev.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    return bvh


def main():
    sc = S.C.clean_scene(FPS)
    floor, walls, door, cart = scene()
    from eidoblend.characters.robot.example import directional, studio_environment
    studio_environment(sc, 0.4, None)
    S.area_light(sc, 'ceiling_a', (0.0, -1.5, 2.5), 400.0, 2.0)
    S.area_light(sc, 'ceiling_b', (0.0, 2.2, 2.5), 400.0, 2.0)
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.4)
    sc.frame_start = 1
    sc.frame_set(1)
    me = load_vrm('claude_robot', name='claude', location=(START[0], START[1], 0.0), rotation=math.degrees(H0))
    rig = RobotRig(me)
    body = VRMRobotBody.create(me, sc, {
        'collision_meshes': [floor] + walls,           # the door and the cart are no colliders: what I see of them is all
        'motion': {'start_x': START[0], 'start_y': START[1], 'start_heading': H0, 'walk_speed': 0.9,
                   'agent_radius': 0.3},
        'memory': {'size': 9.0, 'origin_y': 0.5, 'cell_size': 0.1}, 'sensors': {'h_rays': 18, 'v_rays': 14, 'range': 6.0},
        'planner': {'agent_radius': 0.3}}, rig=rig)
    dbg = RobotDebug(body)
    for k in ('rays', 'map', 'path'):
        getattr(dbg, 'show_' + k)(True)
    out, marks = {}, {}
    m = body.memory
    # the cells just behind the leaf's face (the memory marks a wall's cell 0.6 of a cell past where a ray hit it)
    door_cells = [m.world_to_cell(x, WALL_Y + 0.15) for x in np.linspace(DOOR_X[0] + 0.15, DOOR_X[1] - 0.15, 5)]

    def states():
        return [m.get_cell_state(*c) for c in door_cells]

    def script(b):
        a = yield b.scan_area(yaw_range=100, duration=1.5)
        a = yield b.walk_to(*GOAL)
        out['walk_shut'] = (a.state, str(a.error) if a.error else None)
        out['door_cells_shut'] = states()
        a = yield b.until(lambda: b._time_accum >= DOOR_OPEN[1] + 0.3)
        a = yield b.scan_area(yaw_range=100, duration=3.0)
        out['door_cells_open'] = states()
        marks['walk'] = b.frame_count
        a = yield b.walk_to(*GOAL)
        out['walk_open'] = (a.state, str(a.error) if a.error else None)
        a = yield b.wait(0.6)
    body.run(script(body))
    dt = 1.0 / FPS
    refresh = []
    sens = body.sensors
    base_refresh = sens.refresh

    def timed_refresh(*a, **kw):
        t0 = time.time()
        n = base_refresh(*a, **kw)
        refresh.append(time.time() - t0)
        return n
    sens.refresh = timed_refresh
    t0 = time.time()
    for k in range(FPS * 40):
        body.update(k * dt, dt)
        dbg.update()
        if body._script is None:
            break
    sens.refresh = base_refresh
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t0, 1), 'outcome': out, 'marks': marks,
                'log': [(round(t, 2), e) for t, e in body.log], 'movers': [o.name for o in body.movers()],
                'refresh_s': {'n': len(refresh), 'median': round(float(np.median(refresh)), 4) if refresh else None,
                              'max': round(max(refresh), 4) if refresh else None},
                'senses': len(body.readings), 'rebuilds': body.refreshes}
    R.log('run', R['run'])
    rep = body.bake(face=lambda t: {'happy': 0.2}, action_name='claude|moving')
    dbg.build(rep)
    frames = rep['_frames']
    sc.frame_start, sc.frame_end = rep['frames']
    f0 = rep['frames'][0]
    # ---- checks
    shut, opened = out.get('door_cells_shut', []), out.get('door_cells_open', [])
    R.check('the shut door is seen as shut', out.get('walk_shut', ('',))[0] == 'rejected' and
            ('no path' in str(out.get('walk_shut')) or 'unreachable' in str(out.get('walk_shut')))
            and sum(s == STATE_BLOCKED for s in shut) >= 3,
            f'walk_to while it was shut: {out.get("walk_shut")}; the doorway\'s cells then {shut} (2 blocked)')
    thru = [fr['M'].translation for fr in frames if abs(fr['M'].translation.y - WALL_Y) < 0.1]
    R.check('the open door is seen as open', out.get('walk_open', ('',))[0] == 'resolved' and
            sum(s == STATE_FREE for s in opened) >= 4 and thru and all(DOOR_X[0] < p.x < DOOR_X[1] for p in thru),
            f'walk_to after it opened: {out.get("walk_open")}; the doorway\'s cells {opened} (1 free); I cross the wall\'s '
            f'line at x {[round(p.x, 2) for p in thru[:3]]}')
    # the lintel in my legs' colliders: their probes and their scan ahead read the floor under it
    near = [r['feet_world'][2] for r in rep['_records'] if abs(r['feet_world'][1] - WALL_Y) < 1.0]
    R['doorway'] = {'moves': rep['moves'], 'frames_within_1m': len(near),
                    'feet_z_mm': [round(1000 * min(near), 1), round(1000 * max(near), 1)] if near else None}
    R.check('the lintel over the doorway is over my head: no move plays, my feet on the floor through the doorway',
            not rep['moves'] and near and max(abs(z) for z in near) < 0.01, f'{R["doorway"]}')
    # every hit on a mover against its surface at that sense's frame (and the cart's against its first frame's)
    worst, worst_static, n = {'door': 0.0, 'cart': 0.0}, 0.0, {'door': 0, 'cart': 0}
    first_cart = None
    for fc, t, reading in body.readings:
        hits = [h for h in reading['hits'] if h['hit'] and h['object'] is not None and h['object'].name in ('door', 'cart')]
        if not hits:
            continue
        sc.frame_set(1 + int(round(t * FPS)))
        bvhs = {nm: evaluated_bvh(bpy.data.objects[nm]) for nm in ('door', 'cart')}
        for h in hits:
            nm = h['object'].name
            q = bvhs[nm].find_nearest(Vector(h['point']))
            worst[nm] = max(worst[nm], (q[0] - Vector(h['point'])).length if q[0] is not None else 9.0)
            n[nm] += 1
            if nm == 'cart':
                if first_cart is None:
                    sc.frame_set(1)
                    first_cart = evaluated_bvh(cart)
                    sc.frame_set(1 + int(round(t * FPS)))
                q0 = first_cart.find_nearest(Vector(h['point']))
                worst_static = max(worst_static, (q0[0] - Vector(h['point'])).length)
    R['hits_on_movers'] = {'hits': n, 'off_surface_m': {k: round(v, 4) for k, v in worst.items()},
                           'cart_hits_off_its_first_frame_m': round(worst_static, 3)}
    R.check('the hits lie on the movers as the scene has them', n['door'] > 10 and n['cart'] > 10 and
            max(worst.values()) < 0.01 and worst_static > 0.5, f'{R["hits_on_movers"]}')
    cart_seen = [t for _fc, t, rd in body.readings if any(h['hit'] and h['object'] is cart for h in rd['hits'])]
    replans = [(t, e) for t, e in body.log if e.startswith('replan') and cart_seen and min(cart_seen) <= t <= max(cart_seen) + 1]
    dmin = (9.0, None)
    for fr in frames:
        sc.frame_set(fr['f'])
        cp = cart.matrix_world.translation
        p = fr['M'].translation
        dx = max(0.0, abs(p.x - cp.x) - 0.4)
        dy = max(0.0, abs(p.y - cp.y) - 0.3)
        d = math.hypot(dx, dy)
        if d < dmin[0]:
            dmin = (d, fr['f'])
    R['cart'] = {'seen_s': [round(min(cart_seen), 2), round(max(cart_seen), 2)] if cart_seen else None,
                 'replans_while_seen': replans[:6], 'root_to_cart_min_m': [round(dmin[0], 3), dmin[1]]}
    R.check('the cart is seen and avoided', cart_seen and replans and dmin[0] >= 0.35, f'{R["cart"]}')
    # what the cart left in the memory at the end (reported): the cells it stood and rolled over, its last place aside,
    # still blocked, or still holding its top's height (seen while it stood: a ledge to the planner) until the sensors
    # see that floor again (the JS's memory keeps what it saw where it saw it)
    m = body.memory
    left = {'cells': 0, 'blocked': 0, 'ledge': 0, 'unknown': 0}
    for x in np.arange(CART_X[0] - 0.35, CART_X[1] - 0.4, 0.1):
        for y in np.arange(CART_Y - 0.25, CART_Y + 0.3, 0.1):
            c = m.world_to_cell(float(x), float(y))
            s, z = m.get_cell_state(*c), m.get_cell_surface_z(*c)
            left['cells'] += 1
            left['blocked'] += s == STATE_BLOCKED
            left['unknown'] += s == 0
            left['ledge'] += s == STATE_FREE and not math.isnan(z) and z > 0.4
    R['cart_left_in_memory'] = left
    R.log('what the cart left in the memory:', left)
    shots = []
    # the door from my side of the wall, behind me (it slides open over my shoulder); the cart from the far half's
    # north-west corner (its path across the room, the doorway I come through, my goal beside it)
    cams = {'door': (Vector((-1.6, -2.8, 1.5)), Vector((0.2, 0.5, 1.0))),
            'cart': (Vector((-3.6, 3.7, 1.7)), Vector((0.6, 1.6, 0.5)))}
    fa = 1 + int(DOOR_OPEN[0] * FPS)
    for k, f in enumerate(np.linspace(fa - 12, fa + 1.5 * FPS, 6).astype(int)):
        shots.append({'name': f'door_{k}', 'frame': int(f), 'cam': list(cams['door'][0]),
                      'target': list(cams['door'][1]), 'lens': 28.0})
    if cart_seen:
        for k, f in enumerate(np.linspace(1 + int(min(cart_seen) * FPS), 1 + int((max(cart_seen) + 1.0) * FPS),
                                          8).astype(int)):
            shots.append({'name': f'cart_{k}', 'frame': int(min(f, f0 + len(frames) - 1)), 'cam': list(cams['cart'][0]),
                          'target': list(cams['cart'][1]), 'lens': 24.0})
    # the walk through the doorway, a low side camera held over it, the debug overlays left out
    thru_f = [fr['f'] for fr in frames if abs(fr['M'].translation.y - WALL_Y) < 1.3]
    if thru_f:
        a_, b_ = thru_f[0], thru_f[-1]
        hide = [o.name for o in bpy.data.objects if o.name.startswith('robot_debug')]
        shots += [dict(s, hide=hide) for s in S.strip('doorway', S.side_view(S.solids_bvh(walls), frames, f0, a_, b_),
                                                       a_, b_, n=min(18, (b_ - a_) // 3 + 1))]
    S.write_json('moving_shots.json', shots)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'moving.blend'), compress=True)
    if RENDER:
        R['renders'] = S.render_shots(sc, 'moving', shots)


try:
    main()
except Exception:  # noqa: BLE001
    R.finish(traceback.format_exc())
else:
    R.finish()
