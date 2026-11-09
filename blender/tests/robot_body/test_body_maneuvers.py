"""My embodied robot's moves: VRMRobotBody.vault / jump / climb_ledge / climb_ladder (robot_body.js passes them through
robot_controller.js to the engine's charCtrl; here the controller family's VRMCharacterController plays each one from
where I stand: RobotLegs._start_maneuver), on a course down a hall:

    walk_to(before a low wall, 0.8 m) -> vault() -> walk_to(the ditch's edge) -> jump({'distance': 1.4}) over the ditch
    (0.75 m wide, 0.7 m deep) -> walk_to(before the step, 1.0 m) -> climb_ledge() onto it -> walk_to(the ladder) on its
    top -> climb_ladder({'height': 1.9}) up the tower's ladder and over its top -> look_at the hall

and the refusals, as the JS answers them: vault() with nothing ahead, and a move asked while walking, are False.

Checks (PASS / FAIL):
  - each move started (True), played its maneuver in the controller family (vault; jump; climbLedge; climbLadder with
    the mantle chained over its top) and was keyed; I sense on through each (the readings go on)
  - the refusals answer False and change nothing
  - I end on the tower's top (2.9 m) near the goal
  - no sole point of either foot goes more than 2 cm into the floor, the wall, the step or the tower at any keyed frame
    (rig.feet_world on the keyed records against a BVH of the solids; the bake pushes a climb's foot out of the face it
    climbs), and standing, both feet are within 4 mm of what they stand on
  - the hand-ins: each move shifted at most 4 cm to stand where I stand; my feet step to its stance with no planted sole
    point moving over 2 mm a frame, and where the move takes over the feet move under 15 mm
  - my passes keep the controller family's hands (the knuckles against its own frames), and those hands are on what
    they hold: the vault's on the wall's top, the ladder's on its rungs (within 6 cm, as the controller family's course
    test measures them; its contact IK on my body)
Stills: out/maneuvers_<moment>_f<k>.png; out/maneuvers.json, out/maneuvers.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_body_maneuvers.py [--no-render]
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
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

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
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True


def log(*a):
    print('[maneuvers]', *a, flush=True)


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
    floor_m = textured('floor_wood', 'WoodFloor064_2k', 0.6)
    wall_m = textured('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    block_m = textured('blocks_painted', 'PaintedWood009C_2k', 0.8)
    pit_m = textured('pit_floor', 'PaintedPlaster017_2k', 0.7, tint=(0.45, 0.44, 0.42, 1.0))
    steel_m = textured('ladder_steel', 'PaintedMetal012_1k', 1.0, tint=(0.25, 0.27, 0.3, 1.0))
    solids = []
    # the floor on either side of the ditch (deep boxes: the ditch's walls are their faces), the ditch's floor
    solids += [box('floor_a', -7.0, DITCH[0], -3.0, 3.0, -1.0, 0.0, floor_m),
               box('floor_b', DITCH[1], 6.5, -3.0, 3.0, -1.0, 0.0, floor_m),
               box('ditch_floor', DITCH[0], DITCH[1], -3.0, 3.0, -1.0, DITCH[2], pit_m)]
    solids.append(box('low_wall', WALL[0], WALL[1], -1.6, 1.6, 0.0, WALL[2], block_m, 0.01))
    solids.append(box('step', STEP[0], STEP[1], -1.6, 1.6, 0.0, STEP[2], block_m, 0.01))
    solids.append(box('tower', TOWER[0], TOWER[1], -1.6, 1.6, 0.0, TOWER[2], block_m, 0.01))
    # the hall round it: a back wall and both ends (every camera looks into a room)
    H = 6.5
    room = [box('wall_back', -7.1, 6.6, 3.0, 3.1, -1.0, H, wall_m), box('wall_west', -7.1, -7.0, -3.0, 3.0, -1.0, H, wall_m),
            box('wall_east', 6.5, 6.6, -3.0, 3.0, -1.0, H, wall_m)]
    solids += room
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
    from eidoblend.characters.robot.example import studio_environment
    studio_environment(sc, 0.4, None)
    for name, loc, energy in (('ceiling_w', (-4.0, 0.0, 4.0), 900.0), ('ceiling_m', (0.0, 0.0, 4.0), 900.0),
                              ('ceiling_e', (4.0, 0.0, 4.0), 900.0)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.size = 2.4
        ld.color = (1.0, 0.95, 0.88)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)
    from eidoblend.characters.robot.example import directional
    directional('key', (-3.0, 4.0, -6.0), 0xfff2e4, 1.6)


def solids_bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        b0 = len(verts)
        verts.extend(ev.matrix_world @ v.co for v in me.vertices)
        polys.extend([b0 + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def depth_in(bvh, p):
    """how far p is inside the closed solids (m, 0 outside): the nearest face's normal, then a ray's crossings"""
    q, n, _i, d = bvh.find_nearest(p)
    if q is None or (p - q).dot(n) >= 0:
        return 0.0
    hits, o = 0, p.copy()
    for _ in range(16):
        h = bvh.ray_cast(o, Vector((0.0, 0.0, 1.0)), 50.0)
        if h[0] is None:
            break
        hits += 1
        o = h[0] + Vector((0.0, 0.0, 1e-4))
    return d if hits % 2 == 1 else 0.0


try:
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
        'planner': {'agent_radius': 0.3}}, rig=rig)
    legs = body.controller.char_ctrl
    outcome, marks = {}, {}

    def wait(b, seconds):
        return b.wait(seconds)                          # the body's own script timer

    def until_landed(b):
        return b.until(lambda: not b.is_maneuvering())  # resolves on the first frame the move is over

    def move(b, name, fn):
        n0 = len(b.readings)
        marks[name + '_a'] = b.frame_count
        ok = fn()
        outcome[name] = ok
        return ok, n0

    def script(b):
        # the refusal with nothing ahead: the hall's open floor before the wall is 1.6 m off, past the scan's reach
        outcome['vault_nothing_ahead'] = b.vault()
        outcome['state_after_refusal'] = (b.is_maneuvering(), b.controller.get_state())
        a = yield wait(b, 0.4)
        a = yield b.walk_to(WALL[0] - 0.55, 0.0)
        outcome['walk_wall'] = (a.state, str(a.error) if a.error else None)
        a = yield wait(b, 0.3)
        ok, n0 = move(b, 'vault', b.vault)
        if ok:
            a = yield until_landed(b)
        outcome['vault_senses'] = len(b.readings) - n0
        a = yield b.walk_to(DITCH[0] - 0.35, 0.0)
        outcome['walk_ditch'] = (a.state, str(a.error) if a.error else None)
        a = yield wait(b, 0.3)
        ok, n0 = move(b, 'jump', lambda: b.jump({'distance': 1.4, 'height': 0.45}))
        if ok:
            a = yield until_landed(b)
        outcome['jump_senses'] = len(b.readings) - n0
        # the refusal while walking: a move asked mid-stride
        p_walk = b.walk_to(STEP[0] - 0.5, 0.0)
        a = yield wait(b, 0.6)
        outcome['ledge_while_walking'] = b.climb_ledge()
        a = yield p_walk
        outcome['walk_step'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(H0)
        a = yield wait(b, 0.3)
        ok, n0 = move(b, 'climb_ledge', b.climb_ledge)
        if ok:
            a = yield until_landed(b)
        outcome['climb_ledge_senses'] = len(b.readings) - n0
        a = yield b.walk_to(TOWER[0] - 0.5, 0.0)
        outcome['walk_ladder'] = (a.state, str(a.error) if a.error else None)
        a = yield b.face_direction(H0)
        a = yield wait(b, 0.3)
        ok, n0 = move(b, 'climb_ladder', lambda: b.climb_ladder({'height': TOWER[2] - STEP[2]}))
        if ok:
            a = yield until_landed(b)
        outcome['climb_ladder_senses'] = len(b.readings) - n0
        a = yield b.look_at(-2.0, -1.0, 0.5)
        outcome['look_at'] = a.state
        a = yield wait(b, 1.0)
    body.run(script(body))
    dt = 1.0 / FPS
    t_sim = time.time()
    f_done = None
    for k in range(FPS * 60):
        t = k * dt
        body.update(t, dt)
        if body._script is None and f_done is None:
            f_done = k
        if f_done is not None and k >= f_done + FPS // 2:
            break
    R['run'] = {'frames': body.frame_count, 'seconds': round(time.time() - t_sim, 2), 'outcome': outcome,
                'marks': marks, 'log': [(round(t, 2), e) for t, e in body.log], 'senses': len(body.readings),
                'maneuver_log': legs.maneuver_log,
                'moves_live': [{'name': m['name'], 'played': m['played'], 'frames': len(m['frames']),
                                'start': [round(v, 3) for v in m['start']], 'timing_s': m['report'].get('timing_s')}
                               for m in legs._maneuvers]}
    log('run', R['run'])
    t_b = time.time()
    rep = body.bake(f0=1, face=lambda t: {'happy': 0.2}, action_name='claude|maneuvers')
    R['bake'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('map', 'spans', 'maneuvers')}
    R['bake']['maneuvers'] = [{k: v for k, v in m.items() if not k.startswith('_')} for m in rep['maneuvers']]
    R['bake_s'] = round(time.time() - t_b, 1)
    frames = rep['_frames']
    R['spans'] = [(s['kind'], s['a'], s['b'], s.get('clip')) for s in rep['spans']]
    R['src_track'] = [(fr['f'], fr['src']) for fr in frames]
    sc.frame_start, sc.frame_end = rep['frames']
    log('bake', R['bake_s'], 's;', len(frames), 'frames;', R['bake'].get('maneuvers'))

    # ---- checks
    moves = rep['maneuvers']
    want = {'vault': {'vault'}, 'jump': {'jump'}, 'climb_ledge': {'mount'}, 'climb_ladder': {'ladder', 'mount'}}
    got = {m['name']: set(m['played']) for m in moves}
    R['moves'] = {m['name']: {'played': m['played'], 'film_frames': m['film_frames'], 'shift_m': m['shift_m'],
                              'replayed': m['replayed'], 'frames_live': m['frames_live'],
                              'frames_keyed': m['frames_keyed']} for m in moves}
    started = all(outcome.get(n) is True for n in want)
    played = all(want[n] <= got.get(n, set()) for n in want)
    senses = {n: outcome.get(n + '_senses', 0) for n in want}
    check('moves_play', started and played and all(v > 5 for v in senses.values()),
          f'started {[(n, outcome.get(n)) for n in want]}; played {[(n, sorted(got.get(n, []))) for n in want]} (wanted '
          f'{[(n, sorted(v)) for n, v in want.items()]}); sensor readings through each {senses}')
    check('refusals', outcome.get('vault_nothing_ahead') is False and outcome.get('ledge_while_walking') is False
          and outcome.get('state_after_refusal') == (False, 'idle'),
          f'vault() with nothing ahead {outcome.get("vault_nothing_ahead")}, then {outcome.get("state_after_refusal")}; '
          f'climb_ledge() mid-stride {outcome.get("ledge_while_walking")}; what the legs logged: {legs.maneuver_log}')
    end = frames[-1]['M'].translation
    goal_x = 0.5 * (TOWER[0] + TOWER[1])
    check('ends_on_the_tower', abs(end.z - TOWER[2]) < 0.03 and TOWER[0] + 0.1 < end.x < TOWER[1],
          f'the keyed root ends at ({end.x:.2f}, {end.y:.2f}, {end.z:.3f}) (the tower top {TOWER[2]} m, x {TOWER[0]}..'
          f'{TOWER[1]}, its middle {goal_x})')
    # the feet against the solids, every keyed frame
    bvh = solids_bvh(solids)
    deep = (0.0, None, None)                            # every keyed frame: walking, standing, stepping in, the moves
    stand_gap = (0.0, None)
    for fr in frames:
        F = rig.feet_world(fr)
        for s, P in F.items():
            for p in P[::3]:
                d = depth_in(bvh, Vector(p))
                if d > deep[0]:
                    deep = (d, fr['f'], s, fr['src'][0])
        if fr['src'][0] == 'stand' and fr['src'][2] is None:
            for s, P in F.items():
                low = P[np.argmin(P[:, 2])]
                hit = bvh.ray_cast(Vector((low[0], low[1], low[2] + 0.3)), Vector((0.0, 0.0, -1.0)), 2.0)
                if hit[0] is not None:
                    g = float(low[2]) - hit[0].z
                    if abs(g) > 0.003:
                        R.setdefault('standing_gaps_over_3mm', []).append((fr['f'], s, round(1000 * g, 1), fr['src']))
                    if abs(g) > stand_gap[0]:
                        stand_gap = (abs(g), fr['f'], s, round(1000 * g, 1), fr['src'])
    # the controller family's own frames of each move (shifted as keyed), for the record: how deep its move puts a
    # foot into the face it climbs before my bake pushes the foot out onto it (bake._feet_out_of_solids)
    deep_c = {}
    for m in moves:
        worst = (0.0, None, None)
        for j, fr in enumerate(m['_frames']):
            if j < 8:
                continue                                # the step-in (mine)
            frc = {'N': fr['N'], 'off': fr['off'], 'M': Matrix.Translation(m['_shift']) @ fr['M']}
            for s, P in rig.feet_world(frc).items():
                for p in P[::3]:
                    d = depth_in(bvh, Vector(p))
                    if d > worst[0]:
                        worst = (d, m['film_frames'][0] + j, s)
        deep_c[m['name']] = [round(1000 * worst[0], 1), worst[1], worst[2]]
    R['feet'] = {'deepest_in_mm': [round(1000 * deep[0], 1)] + list(deep[1:]),
                 'standing_off_mm': [round(1000 * stand_gap[0], 1)] + list(stand_gap[1:]),
                 'controller_frames_deepest_in_mm': deep_c,
                 'pushed_out_m': {m['name']: m.get('feet_pushed_out_m') for m in moves}}
    check('feet_on_and_out_of_the_solids', deep[0] < 0.02 and stand_gap[0] < 0.004,
          f'on every keyed frame (walking, standing, stepping in, the moves) no sole point goes deeper than '
          f'{R["feet"]["deepest_in_mm"]} (mm, frame, foot, span) into the floor, the wall, the step or the tower; '
          f'standing, the lowest sole point of each foot is within {R["feet"]["standing_off_mm"]} (mm, frame) of what it '
          f'stands on. (The controller family\'s own move frames put a foot this deep, mm, before my bake pushes it out '
          f'onto the face: {deep_c})')
    # the hand-ins
    FADE = 8                                            # the bake's crossfade (bake_run's fade)
    # each move's hand-in, frame by frame: the root and both soles' centres, mine (keyed) and the controller's (shifted)
    R['hand_in_frames'] = {}
    for m in moves:
        a_ = m['film_frames'][0]
        rows = []
        for j in range(-1, FADE + 3):
            fr = frames[a_ - 1 + j]
            row = {'f': fr['f'], 'root': [round(c, 3) for c in fr['M'].translation],
                   'soles': {s: [round(float(c), 3) for c in P.mean(axis=0)] for s, P in rig.feet_world(fr).items()}}
            if 0 <= j < len(m['_frames']):
                fc = m['_frames'][j]
                frc = {'N': fc['N'], 'off': fc['off'], 'M': Matrix.Translation(m['_shift']) @ fc['M']}
                row['ctrl_root'] = [round(c, 3) for c in frc['M'].translation]
                row['ctrl_soles'] = {s: [round(float(c), 3) for c in P.mean(axis=0)]
                                     for s, P in rig.feet_world(frc).items()}
            rows.append(row)
        R['hand_in_frames'][m['name']] = rows
    def contact(P):
        """the sole points within 3 mm of what is under them"""
        out = np.zeros(len(P), dtype=bool)
        for i_, p in enumerate(P):
            hit = bvh.ray_cast(Vector((p[0], p[1], p[2] + 0.05)), Vector((0.0, 0.0, -1.0)), 0.5)
            out[i_] = hit[0] is not None and p[2] - hit[0].z < 0.003
        return out
    slip, pop = (0.0, None), {}
    for m in moves:
        a_ = m['film_frames'][0]
        prev = None
        for fr in frames[a_ - 2:a_ + FADE]:             # the standing frame before, the step-in, its first own frame
            F = rig.feet_world(fr)
            C = {s: contact(P) for s, P in F.items()}
            if prev is not None:
                for s in F:
                    P, Q = F[s], prev[0][s]
                    if fr['f'] == a_ + FADE:            # the move's own feet after the step-in's
                        pop[m['name'] + '_' + s] = round(1000 * float(np.linalg.norm(P - Q, axis=1).max()), 2)
                        continue
                    both = C[s] & prev[1][s]            # planted in both frames (a stepping foot is lifted)
                    if both.any():
                        dmin = float(np.min(np.linalg.norm(P[both, :2] - Q[both, :2], axis=1)))
                        if dmin > slip[0]:
                            slip = (dmin, fr['f'], m['name'])
            prev = (F, C)
    shifts = {m['name']: m['shift_m'] for m in moves}
    steps = {m['name']: m.get('step_in_m') for m in moves}
    R['hand_in'] = {'shift_m': shifts, 'step_in_m': steps, 'slip_mm': [round(1000 * slip[0], 2), slip[1], slip[2]],
                    'release_mm': pop}
    check('hand_ins', moves and max(shifts.values()) < 0.04 and slip[0] < 0.002 and max(pop.values()) < 15.0,
          f'each move shifted {shifts} m on the ground to stand where I stand; my feet step to its stance {steps} (m); '
          f'a planted sole point moves at most {R["hand_in"]["slip_mm"]} (mm, frame, move) through the step-ins; where '
          f'the move takes over, each foot moves at most {pop} mm (a sole point, that frame)')
    # the hands (each hand's knuckles: the middle finger's proximal joint): the vault's on the wall's top, the ladder's on
    # its rungs, on my keyed frames AND on the controller family's own frames of the same move (shifted as keyed): my
    # passes after its plant (the arms' and hands' DOF, the gaze, the head) must keep what its contact IK did
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
    for m in moves:
        if m['name'] not in ('vault', 'climb_ladder'):
            continue
        fa_, fb_ = m['film_frames']
        mine = frames[fa_ - 1:fb_]
        theirs = [{'N': fr['N'], 'off': fr['off'], 'M': Matrix.Translation(m['_shift']) @ fr['M']} for fr in m['_frames']]
        res = {}
        for lab, seq in (('keyed', mine), ('controller', theirs)):
            ds = []
            for j, fr in enumerate(seq):
                if m['name'] == 'climb_ladder' and mine[j].get('move') != 'ladder':
                    continue
                ps = [rig.bone_world(fr, n)[0] for n in knuck]
                ds.append(min((to_wall_top if m['name'] == 'vault' else to_rung)(p) for p in ps))
            res[lab] = ({'min_m': round(min(ds), 3)} if m['name'] == 'vault' else
                        {'median_m': round(float(np.median(ds)), 3), 'within_6cm': round(float(np.mean(np.array(ds) < 0.06)), 2),
                         'frames': len(ds)}) if ds else None
        hands[m['name']] = res
    R['hands'] = hands
    v_, l_ = hands.get('vault') or {}, hands.get('climb_ladder') or {}
    kept = (v_.get('keyed') and v_.get('controller') and v_['keyed']['min_m'] <= v_['controller']['min_m'] + 0.01
            and l_.get('keyed') and l_.get('controller') and l_['keyed']['median_m'] <= l_['controller']['median_m'] + 0.01)
    on = v_.get('keyed') and v_['keyed']['min_m'] < 0.06 and l_.get('keyed') and l_['keyed']['median_m'] < 0.06
    check('hands_kept_through_my_passes', bool(kept),
          f'my keyed knuckles against the controller family\'s own frames: the vault\'s nearest to the wall\'s top '
          f'{v_}; on the ladder, to the nearest rung {l_}')
    check('hands_on_what_they_hold (the controller family\'s contact IK)', bool(on),
          f'(within 6 cm, as the controller family\'s course test asks) the vault {v_.get("keyed")}, the ladder '
          f'{l_.get("keyed")}')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'maneuvers.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        wide = S.C.camera('wide', 24.0)
        close = S.C.camera('close', 40.0)
        shots = {}
        S.C.aim(wide, (-0.4, -10.5, 3.2), (-0.4, 0.0, 1.1))
        picks = {'start': 1}
        for m in moves:
            fa_, fb_ = m['film_frames']
            mid = [fr['f'] for fr in frames[fa_ - 1:fb_] if fr.get('move') not in (None, 'loco', 'idle')]
            if mid:
                picks[m['name'] + '_a'] = mid[len(mid) // 4]
                picks[m['name'] + '_b'] = mid[len(mid) // 2]
                picks[m['name'] + '_c'] = mid[(3 * len(mid)) // 4]
        for nm, v in deep_c.items():                    # where the controller family's move puts a foot deepest
            if v[1] is not None and v[0] > 20.0:
                picks[nm + '_deepest'] = v[1]
        picks['end'] = frames[-1]['f']
        for name, f in picks.items():
            p = os.path.join(S.OUT, f'maneuvers_wide_{name}_f{f:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, wide, f, p)
            fr = frames[f - 1]
            c = fr['M'].translation + Vector((0.0, 0.0, 0.9))
            S.C.aim(close, c + Vector((0.9, -4.2, 0.6)), c)
            p = os.path.join(S.OUT, f'maneuvers_close_{name}_f{f:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, close, f, p)
        R['renders'] = shots
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('maneuvers.json', R)
log('done', R['ok'], R['seconds'], 's')
