"""The maneuver, seating and emote tests' stage (tests only): simple geometry built for each move (a floor, a chair with a
backrest, a stool, a cover, a ledge block, a wall, a ladder of rungs against a wall, a gap between two platforms), each
placed anywhere at any heading, dressed in the controller tests' CC0 sets; and the controller tests' instruments
(tests/controller/_ctrl_stage.py: Report, FootMesh, gait_checks, keyed_matches, side shots, save) reused:

    import _mnv_stage as T
    sc = T.S.clean_scene(fps=30)
    T.floor()
    chair = T.chair('chair_a', (1.6, 2.2), heading=math.radians(200))
    R = T.Report('seating_aletheia')
    T.save(R, sc, shots, sheets)      # out/<tag>.blend + out/<tag>_shots.json (render_shots.py renders them)

A heading is the controller's: radians about +Z, 0 faces -Y. A chair at heading th seats its sitter facing th (its
backrest behind her). An obstacle at heading th has its near face toward -forward(th): a body walking along th meets it.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.normpath(os.path.join(HERE, '..', 'controller'))
sys.path.insert(0, CTRL)
import _ctrl_stage as _C  # noqa: E402
from _ctrl_stage import (FootMesh, Report, S, arg, argv, course_materials, fixed_shot, gait_checks,  # noqa: E402,F401
                         light, mesh_feet_check, pbr_material, side_shot)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
_C.OUT = OUT                    # the controller stage's Report.finish and save write into this folder's out/


def save(R, sc, shots, sheets=None, blend=True):
    """the controller tests' save (out/<tag>.blend and out/<tag>_shots.json), into this folder's out/"""
    return _C.save(R, sc, shots, sheets, blend)


def _mats():
    m = course_materials()
    m['chair'] = m['bench']
    return m


def _link(ob, role=None):
    bpy.context.scene.collection.objects.link(ob)
    if role:
        ob['eido_test_role'] = role
    return ob


def box(name, center, size, mat='obstacle', heading=0.0, role=None, parent=None):
    """a box (sx along the heading's right, sy along its forward, sz up) centred at center, turned to heading"""
    from eidoblend.course.builder import box_mesh
    me = box_mesh(name, size)
    me.materials.append(_mats()[mat] if isinstance(mat, str) else mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = Vector(center)
    ob.rotation_euler = (0.0, 0.0, heading)
    if parent is not None:
        ob.parent = parent
    return _link(ob, role)


def floor(size=40.0):
    from eidoblend.course.builder import plane_mesh
    me = plane_mesh('floor', size)
    me.materials.append(_mats()['ground'])
    return _link(bpy.data.objects.new('floor', me), 'floor')


def _fwd(th):
    return Vector((math.sin(th), -math.cos(th), 0.0))


def _right(th):
    return Vector((math.cos(th), math.sin(th), 0.0))


def chair(name, xy, heading, seat_h=0.45, back_h=0.92, width=0.46, depth=0.44, pan=0.04, leg=0.04, back_t=0.04):
    """a chair: a seat pan `seat_h` high (its top), four legs, a backrest to `back_h` behind the sitter, seating her
    facing `heading`. -> the parent empty's mesh children are the chair (seat_on finds its pan and its facing)"""
    root = bpy.data.objects.new(name, None)
    root.location = (xy[0], xy[1], 0.0)
    root.rotation_euler = (0.0, 0.0, heading)
    _link(root, 'chair')
    # local frame: the sitter faces -Y, the backrest at +Y
    box(name + '_pan', (0.0, 0.0, seat_h - pan / 2), (width, depth, pan), 'chair', parent=root)
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = seat_h - pan
            box(f'{name}_leg{sx:+d}{sy:+d}', (sx * (width / 2 - leg / 2), sy * (depth / 2 - leg / 2), h / 2),
                (leg, leg, h), 'chair', parent=root)
    bh = back_h - seat_h
    box(name + '_back', (0.0, depth / 2 - back_t / 2, seat_h + bh / 2), (width, back_t, bh), 'chair', parent=root)
    bpy.context.view_layer.update()
    return root


def stool(name, xy, seat_h=0.62, r=0.18):
    """a backless stool: no facing of its own (seat_on falls back to face= or the camera)"""
    root = bpy.data.objects.new(name, None)
    root.location = (xy[0], xy[1], 0.0)
    _link(root, 'stool')
    box(name + '_top', (0.0, 0.0, seat_h - 0.025), (2 * r, 2 * r, 0.05), 'chair', parent=root)
    box(name + '_post', (0.0, 0.0, (seat_h - 0.05) / 2), (0.06, 0.06, seat_h - 0.05), 'chair', parent=root)
    bpy.context.view_layer.update()
    return root


def obstacle(name, near_xy, heading, height, depth, width=2.4, mat='obstacle'):
    """a block whose near face is at near_xy, square to a walk along `heading`, `height` high and `depth` deep along
    the walk"""
    c = Vector((near_xy[0], near_xy[1], 0.0)) + _fwd(heading) * (depth / 2)
    return box(name, (c.x, c.y, height / 2 - 0.001), (width, depth, height + 0.002), mat, heading, role='obstacle')


def ladder(name, near_xy, heading, height, first_rung=0.25, rung_spacing=0.28, width=0.5, wall_depth=0.5,
           rail=0.035, rung_r=0.028, standoff=0.09):
    """terrain_base's ladder: a wall block `height` high (the flat face is what the controller walks against) with two
    rails and rungs `standoff` (9 cm) out from its face, rungs from first_rung up every rung_spacing while under
    height - 0.05. -> (wall, [rails], [rungs])"""
    from eidoblend.course.builder import rung_mesh
    wall = obstacle(name + '_wall', near_xy, heading, height, wall_depth)
    f, r = _fwd(heading), _right(heading)
    line = Vector((near_xy[0], near_xy[1], 0.0)) - f * standoff
    rails = []
    for s in (-1, 1):
        p = line + r * (s * width / 2)
        rails.append(box(f'{name}_rail{s:+d}', (p.x, p.y, height / 2), (rail, rail, height), 'rail', heading,
                         role='rail'))
    rungs = []
    z = first_rung
    k = 0
    while z < height - 0.05:
        me = rung_mesh(f'{name}_rung{k}', rung_r, width)
        me.materials.append(_mats()['rail'])
        ob = _link(bpy.data.objects.new(f'{name}_rung{k}', me), 'rung')
        # the cylinder runs along its z: turned onto x, then to the ladder's right
        ob.matrix_world = Matrix.Translation((line.x, line.y, z)) @ Matrix.Rotation(heading, 4, 'Z') @ \
            Matrix.Rotation(math.pi / 2, 4, 'Y')
        rungs.append(ob)
        z += rung_spacing
        k += 1
    bpy.context.view_layer.update()
    return wall, rails, rungs


def platform(name, near_xy, heading, height, depth, width=2.4):
    return obstacle(name, near_xy, heading, height, depth, width)


def scene_camera(pos, target, lens=40.0, name='scene_cam'):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(pos)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')
    bpy.context.scene.camera = cam
    return cam


def keyed_matches(R, me, frames, every=None):
    """the controller stage's keyed_matches (the keyed armature's soles against the bake's, within 0.5 mm), safe when
    the two sole sets differ: sole_subset reads the rest mesh through inv(armature) @ mesh world matrices, so rounding
    at another frame can move a vertex across its band or voxel edge (on my robot body the set taken at check time had
    243 points, the plant's 242). Equal sets compare point for point; otherwise the smaller set is matched to its
    nearest points in the larger and the 90th percentile is judged (a keying error moves the whole sole, a swapped voxel
    representative moves one point)"""
    import numpy as np
    from mathutils.kdtree import KDTree
    from eidoblend.characters.controller.plant import sole_subset
    from eidoblend.characters.ground import SIDES, posed_foot_world
    feet = sole_subset(me)
    sc = bpy.context.scene
    f0, f1 = frames[0]['f'], frames[-1]['f']
    byf = {fr['f']: fr for fr in frames if fr.get('meas')}
    worst, n, unequal = 0.0, 0, 0
    for f in range(f0, f1 + 1, every or max(1, (f1 - f0) // 25)):
        if f not in byf:
            continue
        sc.frame_set(f)
        n += 1
        for s in SIDES:
            P = posed_foot_world(me, feet, s)
            Q = byf[f]['meas'][s]['P']
            if P.shape == Q.shape:
                worst = max(worst, float(np.max(np.linalg.norm(P - Q, axis=1))))
                continue
            unequal += 1
            small, big = (P, Q) if len(P) <= len(Q) else (Q, P)
            kd = KDTree(len(big))
            for i, q in enumerate(big):
                kd.insert(Vector(q), i)
            kd.balance()
            d = np.array([kd.find(Vector(p))[2] for p in small])
            worst = max(worst, float(np.percentile(d, 90)))
    R.check(f'the keyed armature matches the bake (soles, {n} frames)', worst < 0.0005,
            f'{worst * 1000:.3f} mm' + (f'; {unequal} foot-frames with unequal sole sets, matched by nearest points'
                                         if unequal else ''))
    return worst


def at_rest(me):
    """the armature at rest, no action playing: what a new controller measures (measure_vrm reads the posed mesh:
    built while the last take played a ground sit, my robot body's second take ran 0.4 m off)"""
    ad = me.arm.animation_data
    if ad is not None:
        ad.action = None
    me.zero_pose()
    bpy.context.view_layer.update()


def bone_world(me, name):
    arm = me.arm
    return arm.matrix_world @ arm.pose.bones[me.humanoid[name]].head


def yaw_of(me):
    """the armature's heading (the controller's convention)"""
    return me.arm.matrix_world.to_euler().z


def ang_deg(a, b):
    d = a - b
    return abs(math.degrees(math.atan2(math.sin(d), math.cos(d))))


def strip(S, sheets, me, recs, label, frames, dist=3.4, lead=0.0, side=1.0, height=0.25, lens=35.0, at=None):
    """one camera (a side shot of the body at the strip's middle frame, or at=(pos, target)) over frames"""
    sc = bpy.context.scene
    r0 = recs[0]['f']
    frames = [f for f in frames if recs[0]['f'] <= f <= recs[-1]['f']]
    if not frames:
        return
    mid = frames[len(frames) // 2]
    sc.frame_set(mid)
    if at is None:
        cam = side_shot(me, recs[mid - r0], 'x', dist=dist, lead=lead, side=side, height=height, lens=lens)
    else:
        cam = {'pos': tuple(at[0]), 'target': tuple(at[1]), 'lens': lens}
    names = []
    for k, f in enumerate(frames):
        nm = f'strip_{label}_{k}'
        S.append(dict(cam, name=nm, frame=f))
        names.append(nm)
    sheets[f'strip_{label}'] = names


# ------------------------------------------------------------------------------------------------ seat instruments
def inside_depth(P, parts, above=None):
    """the deepest of the points P inside any of the parts ([(bvh, lo, hi)]: emotes.verbs._chair_solid's), by the
    nearest face and a parity ray (above: only the points over this height) -> (m, count of points inside)"""
    from eidoblend.characters.emotes.verbs import _inside_bvh
    if above is not None:
        P = P[P[:, 2] > above]
    deep, n = 0.0, 0
    for bvh, lo, hi in parts:
        for p in P[np.all((P >= lo) & (P <= hi), axis=1)]:
            q = Vector(p)
            loc, nrm, _k, d = bvh.find_nearest(q, 0.5)
            if loc is None or (q - loc).dot(nrm) >= 0.0 or not _inside_bvh(bvh, q):
                continue
            n += 1
            deep = max(deep, d)
    return deep, n


def behind_back(P, parts, seat_z, fwd):
    """the points of P over the pan that stand behind a part of the chair over it (outside it, its rear face straight
    ahead along the sitter's facing within 25 cm, under its top: not an arm laid over it): skin come out through the
    back -> count"""
    from eidoblend.characters.emotes.verbs import _inside_bvh
    f3 = Vector((fwd[0], fwd[1], 0.0)).normalized()
    P = P[P[:, 2] > seat_z + 0.005]
    n = 0
    for bvh, lo, hi in parts:
        lo2 = np.minimum(lo, lo - np.array([f3.x, f3.y, 0.0]) * 0.25)
        hi2 = np.maximum(hi, hi - np.array([f3.x, f3.y, 0.0]) * 0.25)
        for p in P[np.all((P >= lo2) & (P <= hi2), axis=1)]:
            if p[2] > hi[2] - 0.05:
                continue
            q = Vector(p)
            hit = bvh.ray_cast(q, f3, 0.25)
            if hit[0] is not None and hit[1].dot(f3) < 0.0 and not _inside_bvh(bvh, q):
                n += 1
    return n


def whole_seat_checks(R, me, tag, cmd, span, sc, step=2):
    """through the WHOLE seat (the walk-in's last steps, the descent, the hold, a seated loop, the stand-up): the seat
    skin over the pan never more than 1 cm under it; nothing of the body inside the chair's back, and nothing of her
    out behind it (a coat may press into it, as cloth would, but not come out of it); the body, its coat left out, not
    inside the pan or the legs (the knee pits over the pan's front edge, a calf by a leg)"""
    from eidoblend.characters.emotes.verbs import _chair_solid, _loose_points, skin_lowest, skin_points
    a, b = span
    parts = _chair_solid(cmd.chair)
    upper = [p for p in parts if p[2][2] > cmd.seat_here + 0.05]
    lower = [p for p in parts if p[2][2] <= cmd.seat_here + 0.05]
    low, back, rest, out = (0.0, None), (0.0, None, 0), (0.0, None, 0), (0, None)
    for f in range(a, b + 1, step):
        sc.frame_set(f)
        u = skin_lowest(me, cmd.pan, cmd.seat_here - 0.25)
        if u is not None and u - cmd.seat_here < low[0]:
            low = (u - cmd.seat_here, f)
        P = skin_points(me, loose=False)
        d, n = inside_depth(P, upper, above=cmd.seat_here + 0.005)
        if d > back[0]:
            back = (d, f, n)
        n = behind_back(_loose_points(me), upper, cmd.seat_here, cmd.fwd) + behind_back(P, upper, cmd.seat_here,
                                                                                      cmd.fwd)
        if n > out[0]:
            out = (n, f)
        d, n = inside_depth(P, lower)
        if d > rest[0]:
            rest = (d, f, n)
    sink = getattr(cmd, 'sink', 0.0) or 0.0
    R.check(f'{tag}: the seat skin stays on the pan through the whole seat, the stand-up included (no more than 1 cm '
            'under it past its sink=)', low[0] > -0.01 - sink, f'lowest {low[0] * 100:+.2f} cm at f{low[1]} (sink '
            f'{sink * 100:.1f} cm)')
    R.check(f'{tag}: nothing of the body (its coat aside; not the spring chains) inside the chair\'s back through the '
            'whole seat (under 5 mm)', back[0] < 0.005, f'deepest {back[0] * 1000:.1f} mm at f{back[1]} '
            f'({back[2]} points)')
    R.check(f'{tag}: nothing of her (body or coat) out behind the chair\'s back through the whole seat', out[0] == 0,
            f'{out[0]} points at f{out[1]}' if out[0] else 'none')
    R.check(f'{tag}: the body (its coat left out) not inside the pan or the legs through the whole seat (under 12 mm '
            'past its sink=: a thigh pressed over the front edge of the pan)', rest[0] < 0.012 + sink,
            f'deepest {rest[0] * 1000:.1f} mm at f{rest[1]} ({rest[2]} points)')


def floor_checks(R, me, tag, span, sc, floor=0.0, step=2, pad=(4, 20)):
    """the ground sit's crossfades: the lowest of the body near the hips (its coat left out: emotes.verbs's ground
    measure) never more than 1 cm under the floor from the sit-down through the rise"""
    from eidoblend.characters.emotes.verbs import _lowest_near, skin_points
    a, b = span
    worst = (1.0, None)
    for f in range(a - pad[0], b + pad[1], step):
        sc.frame_set(f)
        hp = bone_world(me, 'hips')
        z = _lowest_near(skin_points(me, loose=False), (hp.x, hp.y))
        if z is not None and z - floor < worst[0]:
            worst = (z - floor, f)
    R.check(f'{tag}: the body stays out of the floor sitting down and getting up (the lowest of it near the hips, its '
            'coat left out, no more than 1 cm under)', worst[0] > -0.01, f'lowest {worst[0] * 100:+.2f} cm at '
            f'f{worst[1]}')
