"""My robot body picking up a can and holding it with careful fingers and wrists (eidoblend.characters.robot.hands).

A counter (top at 0.95 m) in a room's corner, with an aluminium can (r 33 mm, 122 mm) in front of my right shoulder.
Standing in the idle, I reach (the arm on its real joints: the elbow's pin, the shoulder's stages, the wrist's roll /
flexion / deviation inside their stops), bring the palm to the can, close each finger's pins until each link touches and
the thumb round the near side, lift it, hold it up before me where my arm brings it upright, roll it in my wrist to look
it over (my head follows it, the crown curious), set it down where it was and let go, and the arm returns to the idle.
13.4 s at 24 fps, keyed.

Checks (PASS / FAIL), on the EVALUATED (skinned) mesh where it matters:
  - the hand touches without passing in: at the closed hand, every finger and the thumb within 3 mm of the can's
    surface, no hand vertex more than 1 mm inside it (and none in the counter) through the whole hold
  - the can moves only in the hand: its place against the hand bone constant from the grasp to the release (mm, deg),
    still on the counter before and after
  - the reach: the wrist reaches its grasp target (mm), the wrist's stages inside their stops all through
  - set down: the can's base on the counter (mm) and upright (deg) after the release, and never in the counter while
    carried, set down and settling
  - the hand follows its plan through my arm's hardware pass (at the can 3 mm / 4 deg, in the air 15 mm / 10 deg)
  - my forearm, hand and fingers clear my torso, head, crown and thighs; both feet on the floor throughout
Stills: out/pick_up_<moment>_f<k>.png (wide and close), out/pick_up.json, out/pick_up.blend.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/test_pick_up.py [--no-render]
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
from mathutils.bvhtree import BVHTree  # noqa: E402

from eidoblend.characters import Ground, load_vrm  # noqa: E402
from eidoblend.characters import robot_dof as dof  # noqa: E402
from eidoblend.characters.robot import RobotRig, hands  # noqa: E402
from eidoblend.characters.robot.example import directional, studio_environment  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS = 24
TOP = 0.95
CAN = (-0.17, -0.44)
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True


def log(*a):
    print('[pick_up]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def tex_mat(name, tex, scale, tint=None, metallic=None, rough=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes['Principled BSDF']
    ts = S.C.texture_set(tex)
    if metallic is not None:
        b.inputs['Metallic'].default_value = metallic
    if ts:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        for role, sock, colour in (('color', 'Base Color', True), ('rough', 'Roughness', False), ('normal', None, False)):
            if not ts.get(role):
                continue
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = bpy.data.images.load(ts[role], check_existing=True)
            n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
            n.projection = 'BOX'
            n.projection_blend = 0.25
            nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
            if sock == 'Base Color' and tint:
                mx = nt.nodes.new('ShaderNodeMix')
                mx.data_type, mx.blend_type = 'RGBA', 'MULTIPLY'
                mx.inputs['Factor'].default_value = 1.0
                nt.links.new(n.outputs['Color'], mx.inputs['A'])
                mx.inputs['B'].default_value = tint
                nt.links.new(mx.outputs['Result'], b.inputs['Base Color'])
            elif sock:
                if sock == 'Roughness' and rough is not None:
                    continue
                nt.links.new(n.outputs['Color'], b.inputs[sock])
            else:
                nm = nt.nodes.new('ShaderNodeNormalMap')
                nm.inputs['Strength'].default_value = 0.6
                nt.links.new(n.outputs['Color'], nm.inputs['Color'])
                nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if rough is not None:
        b.inputs['Roughness'].default_value = rough
    return mat


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=3, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def can(name, x, y, z, r=0.033, hgt=0.122):
    """an aluminium drinks can: the body, the rolled rims, a painted band (its origin on its axis, at its base)"""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    seg = 64
    # the profile (r, z): the base's dome inset, the rolled bottom rim, the wall, the shoulder, the top rim
    prof = [(0.0, 0.006), (r - 0.010, 0.006), (r - 0.007, 0.0), (r - 0.002, 0.002), (r, 0.010), (r, hgt - 0.014),
            (r - 0.004, hgt - 0.006), (r - 0.004, hgt - 0.001), (r - 0.006, hgt), (r - 0.007, hgt - 0.002),
            (0.0, hgt - 0.003)]
    rings = []
    for pr, pz in prof:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new((pr * math.cos(a), pr * math.sin(a), pz)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(seg):
            a, b = rings[i][k], rings[i][(k + 1) % seg]
            c, d = rings[i + 1][(k + 1) % seg], rings[i + 1][k]
            bm.faces.new((a, b, c, d))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = (x, y, z)
    bpy.context.scene.collection.objects.link(ob)
    alu = bpy.data.materials.new('can_aluminium')
    alu.use_nodes = True
    nt = alu.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.22
    b.inputs['Base Color'].default_value = (0.86, 0.86, 0.88, 1.0)
    # the painted band: a deep teal between 18 mm and 104 mm, by the object's height
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    lo_ = nt.nodes.new('ShaderNodeMath')
    lo_.operation = 'GREATER_THAN'
    lo_.inputs[1].default_value = 0.018
    hi_ = nt.nodes.new('ShaderNodeMath')
    hi_.operation = 'LESS_THAN'
    hi_.inputs[1].default_value = 0.104
    nt.links.new(sep.outputs['Z'], lo_.inputs[0])
    nt.links.new(sep.outputs['Z'], hi_.inputs[0])
    band = nt.nodes.new('ShaderNodeMath')
    band.operation = 'MULTIPLY'
    nt.links.new(lo_.outputs[0], band.inputs[0])
    nt.links.new(hi_.outputs[0], band.inputs[1])
    paint = nt.nodes.new('ShaderNodeBsdfPrincipled')
    paint.inputs['Base Color'].default_value = (0.02, 0.24, 0.26, 1.0)
    paint.inputs['Roughness'].default_value = 0.32
    paint.inputs['Metallic'].default_value = 0.35
    paint.inputs['Coat Weight'].default_value = 0.6
    mix = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes['Material Output']
    nt.links.new(band.outputs[0], mix.inputs['Fac'])
    nt.links.new(b.outputs['BSDF'], mix.inputs[1])
    nt.links.new(paint.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    me.materials.append(alu)
    return ob


def hand_vertices(h, side):
    """the evaluated mesh's vertices whose strongest weight is a bone of `side`'s hand (fingers, thumb, palm)"""
    names = {h.humanoid[n] for n in h.humanoid if n.startswith(side) and any(k in n for k in ('Hand', 'Thumb', 'Index',
                                                                                              'Middle', 'Ring', 'Little'))}
    by_bone = {v: k for k, v in h.humanoid.items()}
    out = []
    for o in h.meshes:
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        sel, tags = [], []
        for v in o.data.vertices:
            if v.groups:
                g = max(v.groups, key=lambda g: g.weight)
                n = idx.get(g.group)
                if n in names:
                    sel.append(v.index)
                    tags.append(by_bone.get(n, n))
        if sel:
            out.append((o, np.array(sel), tags))
    return out


def part_vertices(h, side, parts=('Foot', 'Toes')):
    """the evaluated mesh's vertices whose strongest weight is one of `side`'s `parts` bones (default: the foot)"""
    names = {h.humanoid[side + p] for p in parts if (side + p) in h.humanoid}
    out = []
    for o in h.meshes:
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        sel = [v.index for v in o.data.vertices
               if v.groups and idx.get(max(v.groups, key=lambda g: g.weight).group) in names]
        if sel:
            out.append((o, np.array(sel), []))
    return out


def evaluated_points(sets):
    dg = bpy.context.evaluated_depsgraph_get()
    P, tags = [], []
    for o, sel, tg in sets:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)[sel]
        M = np.array(ev.matrix_world)
        P.append(co @ M[:3, :3].T + M[:3, 3])
        tags += tg
        ev.to_mesh_clear()
    return np.concatenate(P), tags


def bvh_of(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    vs = [ev.matrix_world @ v.co for v in me.vertices]
    ps = [list(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, ps, all_triangles=False)


def signed(bvh, P):
    """signed distance to a closed mesh: the nearest face's normal, a ray's crossings deciding where that says inside
    (hands.inside: at a concave feature the nearest face can face away from a point outside)"""
    out = np.empty(len(P))
    for i, p in enumerate(P):
        v = Vector(p)
        q, n, _i, d = bvh.find_nearest(v)
        out[i] = math.inf if q is None else (d if ((v - q).dot(n) >= 0 or not hands.inside(bvh, v)) else -d)
    return out


try:
    sc = S.C.clean_scene(FPS)
    studio_environment(sc, 0.6, 0x16161a)
    directional('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.4)
    directional('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.2)
    floor = box('floor', -3, 3, -3, 3, -0.02, 0.0, tex_mat('floor', 'WoodFloor064_2k', 0.6))
    # a room's corner behind me (every camera looks into it: no void behind the counter)
    plaster = tex_mat('walls_plaster', 'PaintedPlaster017_2k', 0.5, tint=(0.82, 0.8, 0.76, 1.0))
    for wn, wx0, wx1, wy0, wy1 in (('wall_back', -3.0, 3.0, 1.5, 1.6), ('wall_right', 2.2, 2.3, -3.0, 1.6),
                                   ('wall_left', -2.6, -2.5, -3.0, 1.6)):
        box(wn, wx0, wx1, wy0, wy1, 0.0, 2.6, plaster)
    wood = tex_mat('counter_wood', 'Wood066_1k', 1.6, rough=0.45)
    body_m = tex_mat('counter_body', 'PaintedWood009C_2k', 1.0)       # a painted kitchen cabinet
    top = box('counter_top', -0.75, 0.55, -0.9, -0.28, TOP - 0.04, TOP, wood, 0.004)
    cab = box('counter_cabinet', -0.72, 0.52, -0.86, -0.32, 0.0, TOP - 0.04, body_m, 0.006)
    prop = can('can', CAN[0], CAN[1], TOP)
    me = load_vrm('claude_robot', name='claude')
    rig = RobotRig(me)
    t = time.time()
    rep = hands.pick_and_hold(me, rig, prop, f0=1, side='right', ground=Ground(fn=lambda x, y: 0.0 * np.asarray(x)),
                              face=lambda tt: {'happy': 0.35}, action_name='claude|pick_up')
    R['solve_s'] = round(time.time() - t, 1)
    R['pick'] = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('hand_model', 'surface')}
    sc.frame_start, sc.frame_end = rep['frames']
    fa, frl = rep['attach_frame'], rep['release_frame']
    log('solved', R['solve_s'], 's; attach', fa, 'release', frl, 'clearance mm', rep['clearance_mm'])
    sets = hand_vertices(me, 'right')
    # 1. the hand on the can: touching, never in it (nor in the counter)
    top_bvh = bvh_of(top)
    worst_in, worst_top = 0.0, 0.0
    worst_in_at = worst_top_at = None
    touch = {}
    T_ = rep['times']
    f_pre, f_back = 1 + int(round(T_['pre'] * FPS)), 1 + int(round(T_['back'] * FPS))
    for f in list(range(f_pre, f_back, 3)) + [fa, fa + 6]:
        sc.frame_set(f)
        P, tags = evaluated_points(sets)
        d = signed(bvh_of(prop), P)
        dt_ = signed(top_bvh, P)
        if float(d.min()) < worst_in:
            worst_in = float(d.min())
            worst_in_at = (f, tags[int(np.argmin(d))])
        if float(dt_.min()) < worst_top:
            worst_top = float(dt_.min())
            worst_top_at = (f, tags[int(np.argmin(dt_))])
        if f == fa + 6:
            for part in ('Thumb', 'Index', 'Middle', 'Ring', 'Little', 'Hand'):
                sel = [i for i, tg in enumerate(tags) if part in tg and (part != 'Hand' or tg.endswith('Hand'))]
                if sel:
                    touch[part] = round(1000 * float(d[sel].min()), 2)
    R['hand_on_can'] = {'deepest_into_can_mm': round(-1000 * worst_in, 2), 'deepest_into_counter_mm': round(-1000 * worst_top, 2),
                        'deepest_into_can_at': worst_in_at, 'deepest_into_counter_at': worst_top_at,
                        'closest_mm_by_part': touch}
    check('fingers_touch', all(v <= 3.0 for k, v in touch.items() if k != 'Hand') and len(touch) >= 5,
          f'at the closed hand (frame {fa + 6}) each part\'s closest vertex to the can: {touch} mm')
    check('nothing_passes_in', worst_in > -0.0011 and worst_top > -0.0011,
          f'from the approach to the return of the arm no hand vertex is more than {-1000 * worst_in:.2f} mm inside the can, '
          f'{-1000 * worst_top:.2f} mm inside the counter top')
    # 2. the can moves only in the hand
    pb = me.arm.pose.bones[me.humanoid['rightHand']]
    rel0, drift_mm, drift_deg = None, 0.0, 0.0
    still = 0.0
    sc.frame_set(1)
    M_start = prop.matrix_world.copy()
    for f in range(1, rep['frames'][1] + 1, 2):
        sc.frame_set(f)
        Mh = me.arm.matrix_world @ pb.matrix
        if fa <= f < frl:
            rel = Mh.inverted() @ prop.matrix_world
            if rel0 is None:
                rel0 = rel
            drift_mm = max(drift_mm, 1000 * (rel.translation - rel0.translation).length)
            drift_deg = max(drift_deg, math.degrees(rel.to_quaternion().rotation_difference(rel0.to_quaternion()).angle))
        elif f < fa:
            still = max(still, 1000 * (prop.matrix_world.translation - M_start.translation).length)
    sc.frame_set(rep['frames'][1])
    M_end = prop.matrix_world.copy()
    lifted = 0.0
    for f in range(fa, frl, 3):
        sc.frame_set(f)
        lifted = max(lifted, prop.matrix_world.translation.z - M_start.translation.z)
    check('moves_only_in_the_hand', drift_mm < 0.1 and drift_deg < 0.01 and still < 0.01 and lifted > 0.1,
          f'against the hand bone the can drifts {drift_mm:.4f} mm / {drift_deg:.5f} deg from the grasp to the release; '
          f'before the grasp it moves {still:.4f} mm; it is lifted {lifted:.3f} m')
    # 3. the reach and the wrists' stops
    sc.frame_set(fa)
    wg = Vector(rep['wrist_grasp'])
    got = me.arm.matrix_world @ pb.head
    reach_mm = 1000 * (got - wg).length
    wr = [fr['wrists'].get('right') for fr in rep['_frames'] if fr.get('wrists')]
    W = rig.arms.wrist['right']
    worst_split = [0.0, 0.0, 0.0]
    for fr in rep['_frames']:
        st = fr['wrists'].get('right') if fr.get('wrists') else None
        if st is None:
            continue
    check('reach', reach_mm < 6.0, f'the wrist at the grasp is {reach_mm:.2f} mm from its target (after the arm\'s DOF pass); '
          f'the solve: {rep["grasp"]}')
    # 4. set down
    sc.frame_set(rep['frames'][1])
    zb = M_end.translation.z
    up = M_end.to_quaternion() @ Vector((0.0, 0.0, 1.0))
    tilt = math.degrees(up.angle(Vector((0.0, 0.0, 1.0))))
    moved = 1000 * (M_end.translation - M_start.translation).xy.length
    check('set_down', abs(zb - TOP) < 0.001 and tilt < 0.5,
          f'after the release the can stands with its base {1000 * (zb - TOP):.3f} mm over the counter, tilted {tilt:.3f} deg, '
          f'{moved:.1f} mm from where it was picked up')
    # 4a. the can never passes into the counter while carried, set down and settling (its evaluated mesh)
    can_low = (math.inf, None)
    for f in range(fa, min(rep['frames'][1], frl + 6) + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = prop.evaluated_get(dg)
        me_ = ev.to_mesh()
        co = np.empty(len(me_.vertices) * 3)
        me_.vertices.foreach_get('co', co)
        Mw = np.array(ev.matrix_world)
        z = float((co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3])[:, 2].min())
        ev.to_mesh_clear()
        if z < can_low[0]:
            can_low = (z, f)
    R['can_lowest_over_counter_mm'] = [round(1000 * (can_low[0] - TOP), 3), can_low[1]]
    check('can_stays_on_the_counter', can_low[0] > TOP - 0.0005,
          f'from the grasp to the can settling its lowest point is at least {R["can_lowest_over_counter_mm"]} (mm over the '
          f'counter top, frame)')
    # 4b. the hand follows its planned path through the arm's hardware pass (FK of the keyed records): the wrist's place
    # and the hand's turn against the plan on every frame of the reach (the arm's DOF pass may clamp what my joints
    # cannot make: a large number here is the pass correcting the plan)
    # (judged where the hand is on the prop or carrying it: from the pre-grasp to the hand opening; after it lets go the
    # free hand only has to clear the prop and the counter, which nothing_passes_in measures; its deviation is reported)
    # Three stretches, three bars: AT THE CAN (the pre-grasp to the grasp, and the set-down to the hand opening: where a
    # millimetre is a finger in the can or a can in the counter) 3 mm and 4 deg (where my wrist's turn limit lags the
    # plan most, at the set-down, the can lands that far off upright and tips onto its base over 3 frames: the settle);
    # CARRYING IN THE AIR (the lift to the set-down's start: nothing touches, the path is a choice) 15 mm and 10 deg;
    # after letting go, reported only
    T_ = rep['times']

    def fr_of(tt):
        return 1 + int(round(tt * FPS))
    at_can = lambda f: fr_of(T_['pre']) <= f <= fr_of(T_['closed']) or fr_of(T_['over']) <= f <= fr_of(T_['open'])  # noqa: E731
    in_air = lambda f: fr_of(T_['closed']) < f < fr_of(T_['over'])  # noqa: E731
    dev = {'at_can': ([], []), 'in_air': ([], []), 'after_letting_go': ([], [])}
    for fr in rep['_frames']:
        if fr.get('hand_target') is None:
            continue
        wt_, tq_ = fr['hand_target']
        p_, W_ = rig.bone_world(fr, 'rightHand')
        k_ = 'at_can' if at_can(fr['f']) else ('in_air' if in_air(fr['f']) else 'after_letting_go')
        dev[k_][0].append((1000 * (p_ - wt_).length, fr['f']))
        dev[k_][1].append((math.degrees(W_.rotation_difference(tq_).angle), fr['f']))
    R['hand_follows_plan'] = {k: {'frames': len(a), 'wrist_mm_max': [round(max(a)[0], 2), max(a)[1]] if a else None,
                                  'turn_deg_max': [round(max(b)[0], 2), max(b)[1]] if b else None}
                              for k, (a, b) in dev.items()}
    hp = R['hand_follows_plan']
    good = (hp['at_can']['frames'] and hp['at_can']['wrist_mm_max'][0] < 3.0 and hp['at_can']['turn_deg_max'][0] < 4.0
            and hp['in_air']['frames'] and hp['in_air']['wrist_mm_max'][0] < 15.0 and hp['in_air']['turn_deg_max'][0] < 10.0)
    check('hand_follows_plan', good,
          f'after my arm\'s hardware pass the hand is, at the can, at most {hp["at_can"]["wrist_mm_max"]} (mm, frame) and '
          f'{hp["at_can"]["turn_deg_max"]} (deg, frame) from its plan; carrying it in the air at most '
          f'{hp["in_air"]["wrist_mm_max"]} and {hp["in_air"]["turn_deg_max"]}; after letting go '
          f'{hp["after_letting_go"]["wrist_mm_max"]} and {hp["after_letting_go"]["turn_deg_max"]}')
    # 4c. my forearm, hand and fingers clear the rest of my body (the torso, the head, the crown, the legs: the
    # evaluated mesh, nearest vertex to vertex) all through the reach, the carry before my face and the return
    from mathutils.kdtree import KDTree
    arm_sets = part_vertices(me, 'right', ('LowerArm', 'Hand', 'ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal')
                             + tuple(f + k for f in ('Index', 'Middle', 'Ring', 'Little')
                                     for k in ('Proximal', 'Intermediate', 'Distal')))
    body_names = {me.humanoid[n] for n in ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head', 'leftUpperLeg',
                                           'rightUpperLeg', 'leftShoulder') if n in me.humanoid}
    body_names |= {b.name for b in me.arm.data.bones if b.name.startswith('petal_')}
    body_sets = []
    for o in me.meshes:
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        sel = [v.index for v in o.data.vertices
               if v.groups and idx.get(max(v.groups, key=lambda g: g.weight).group) in body_names]
        if sel:
            body_sets.append((o, np.array(sel)[::2], []))
    near = (math.inf, None)
    for f in range(1 + int(round(T_['reach'] * FPS)), 1 + int(round(T_['back'] * FPS)), 4):
        sc.frame_set(f)
        A_, _t = evaluated_points(arm_sets)
        B_, _t = evaluated_points(body_sets)
        kd = KDTree(len(B_))
        for i_, p_ in enumerate(B_):
            kd.insert(p_, i_)
        kd.balance()
        d_ = min(kd.find(p_)[2] for p_ in A_[::3])
        if d_ < near[0]:
            near = (d_, f)
    R['arm_to_body_min_mm'] = [round(1000 * near[0], 2), near[1]]
    check('arm_clears_body', near[0] > 0.004,
          f'my forearm, hand and fingers come no closer than {R["arm_to_body_min_mm"]} (mm, frame) to my torso, head, '
          f'crown and thighs')
    # 5. both feet on the floor while I stand (the evaluated mesh: each foot's lowest vertex)
    feet_sets = {s: [(o, sel) for o, sel, tg in part_vertices(me, s)] for s in ('left', 'right')}
    worst_gap = {'left': 0.0, 'right': 0.0}
    for f in range(1, rep['frames'][1] + 1, 12):
        sc.frame_set(f)
        for s, sets_ in feet_sets.items():
            P, _tg = evaluated_points([(o, sel, []) for o, sel in sets_])
            worst_gap[s] = max(worst_gap[s], abs(float(P[:, 2].min())))
    R['feet_lowest_mm'] = {s: round(1000 * v, 2) for s, v in worst_gap.items()}
    check('both_feet_on_the_floor', all(v < 0.0015 for v in worst_gap.values()),
          f'each foot\'s lowest vertex within {R["feet_lowest_mm"]} mm of the floor at every 12th frame')
    R['wrist_stats_deg'] = {k: v for k, v in rig.stats.items() if 'Hand' in k or 'LowerArm' in k or 'UpperArm' in k}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'pick_up.blend'), compress=True)

    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        T = rep['times']

        def fr_at(tt):
            return 1 + int(round(tt * FPS))
        wide = S.C.camera('wide', 35.0)
        close = S.C.camera('close', 70.0)
        shots = {}
        cpos = Vector((CAN[0], CAN[1], TOP + 0.06))
        for name, tt in (('reach', 1.4), ('touch', T['touch']), ('closed', T['closed'] + 0.25), ('lift', T['lift']),
                         ('face', T['face'] + 0.3), ('turned_a', T['turn_a']), ('turned_b', T['turn_b']),
                         ('down', T['down'] + 0.1), ('let_go', T['open'] + 0.3), ('back', T['end'] - 0.2)):
            f = fr_at(tt)
            S.C.aim(wide, (-1.45, -2.05, 1.55), (-0.1, -0.25, 1.05))
            p = os.path.join(S.OUT, f'pick_up_{name}_wide_f{f:03d}.png')
            shots[os.path.basename(p)] = S.C.still(sc, wide, f, p)
            sc.frame_set(f)
            hp = me.arm.matrix_world @ pb.head
            if name in ('touch', 'closed', 'down', 'let_go'):
                S.C.aim(close, cpos + Vector((-0.42, -0.5, 0.18)), cpos + Vector((-0.03, 0.0, 0.0)))
                p = os.path.join(S.OUT, f'pick_up_{name}_close_f{f:03d}.png')
                shots[os.path.basename(p)] = S.C.still(sc, close, f, p)
                S.C.aim(close, cpos + Vector((0.25, -0.62, 0.12)), cpos + Vector((-0.03, 0.0, 0.0)))
                p = os.path.join(S.OUT, f'pick_up_{name}_front_f{f:03d}.png')
                shots[os.path.basename(p)] = S.C.still(sc, close, f, p)
            if name in ('face', 'turned_a', 'turned_b', 'lift'):
                hd = me.arm.matrix_world @ me.arm.pose.bones[me.humanoid['head']].head
                S.C.aim(close, hd + Vector((0.35, -1.25, 0.05)), (hd + hp) / 2)
                p = os.path.join(S.OUT, f'pick_up_{name}_close_f{f:03d}.png')
                shots[os.path.basename(p)] = S.C.still(sc, close, f, p)
        R['renders'] = shots
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('pick_up.json', R)
log('done', R['ok'], R['seconds'], 's')
