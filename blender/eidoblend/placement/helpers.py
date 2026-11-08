"""Intent-based placement helpers, ported from eidoverse/scene_placement.js to Blender.

Same intent and the same defaults as the engine's code (where its comments disagree with its code,
the code wins), in Blender axes: Z up, and the sides
    front = -Y   behind = +Y   left = -X   right = +X   above = +Z   below = -Z
(three's +Z front is Blender's -Y, which is also the glTF importer's front).
A model's location is its origin, which can sit anywhere; these helpers seat its visible geometry.
Set the rotation first: they read the rotated bounds.
"""
import math
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import _world as W

_UP = Vector((0.0, 0.0, 1.0))
_DOWN = Vector((0.0, 0.0, -1.0))
SIDE_DIR = {'left': (-1, 0, 0), 'right': (1, 0, 0), 'behind': (0, 1, 0), 'front': (0, -1, 0),
            'below': (0, 0, -1), 'above': (0, 0, 1)}
# yaw about Z that turns each local forward axis toward a horizontal direction (dx, dy)
_YAW = {'-y': lambda dx, dy: math.atan2(dx, -dy), '+y': lambda dx, dy: math.atan2(-dx, dy),
        '+x': lambda dx, dy: math.atan2(dy, dx), '-x': lambda dx, dy: math.atan2(-dy, -dx)}


def _log(tag, msg):
    print('[%s] %s' % (tag, msg))


def support_under_footprint(obj, rays, cx, cy, start_z, grid=9, box=None):
    """Highest downward hit over an n x n grid spanning obj's footprint centred at (cx, cy).
    Returns (z, hits) or None (the engine's supportYUnderFootprint)."""
    b = box or W.tight_box(obj)
    hx = (b[1].x - b[0].x) / 2
    hy = (b[1].y - b[0].y) / 2
    n = max(1, int(grid))
    best, count = None, 0
    for i in range(n):
        for j in range(n):
            fx = cx if n == 1 else cx - hx + (2 * hx) * (i / (n - 1))
            fy = cy if n == 1 else cy - hy + (2 * hy) * (j / (n - 1))
            h = rays.cast((fx, fy, start_z), _DOWN)
            if h:
                count += 1
                if best is None or h[0].z > best:
                    best = h[0].z
    return None if best is None else (best, count)


def place_on(obj, target, xy='auto', z_offset=0.0, xy_offset=None, grid=7, surface_eps=0.0006,
             sink=None, seed=1):
    """Seat obj's bounds bottom on the highest support under its footprint on `target`.

    xy: 'auto' (default: keep an already-placed spot, i.e. a non-zero location XY, measured at the
        bounds centre; else centre on the target), 'centered', 'random' (seeded by `seed`), or (x, y).
    xy_offset: (dx, dy) added after the anchor. z_offset: extra lift. surface_eps (0.6 mm): sit a
    hair proud so a flat base never lands coplanar with the floor (z-fighting); 0 for exact contact.
    sink: bury that fraction of obj's height (clamped 0..0.9; rocks 0.15-0.35); marks
    obj['_sunk_placement'] so the hovering audit leaves it buried.
    Records what obj sits on (obj['_support_targets']). Returns True, or False when nothing is under
    the footprint. `target` may be an object, a list, a collection, or a group containing obj (obj's
    own subtree is never its own support).
    """
    W.update()
    dg = W.depsgraph()
    t_objs = W.collect(target, exclude=[obj])
    if not t_objs:
        _log('place_on', 'target has no surfaces besides obj itself')
        return False
    t_box = _union_boxes(t_objs, dg)
    o_box = W.tight_box(obj, dg=dg)
    if isinstance(xy, (tuple, list, Vector)):
        x, y = float(xy[0]), float(xy[1])
    elif xy == 'random':
        r = random.Random(seed)
        x = t_box[0].x + r.random() * (t_box[1].x - t_box[0].x)
        y = t_box[0].y + r.random() * (t_box[1].y - t_box[0].y)
    elif xy == 'auto' and (abs(obj.location.x) > 1e-6 or abs(obj.location.y) > 1e-6):
        c = W.box_center(o_box)
        x, y = c.x, c.y
    else:
        c = W.box_center(t_box)
        x, y = c.x, c.y
    if xy_offset is not None:
        x += xy_offset[0]
        y += xy_offset[1]
    rays = W.Rays(t_objs, dg)
    sup = support_under_footprint(obj, rays, x, y, t_box[1].z + 100, grid, box=o_box)
    if not sup:
        _log('place_on', 'no surface under footprint at %.3f, %.3f' % (x, y))
        return False
    c = W.box_center(o_box)
    dz = sup[0] + z_offset + surface_eps - o_box[0].z
    if sink:
        h = o_box[1].z - o_box[0].z
        dz -= min(0.9, max(0.0, sink)) * h
        obj['_sunk_placement'] = True
    W.move_world(obj, (x - c.x, y - c.y, dz))
    W.record_support(obj, target)
    return True


def _union_boxes(objs, dg):
    mn = Vector((1e30, 1e30, 1e30))
    mx = Vector((-1e30, -1e30, -1e30))
    for o in objs:
        a, b = W.box_of_object(o, dg)
        mn = Vector((min(mn.x, a.x), min(mn.y, a.y), min(mn.z, a.z)))
        mx = Vector((max(mx.x, b.x), max(mx.y, b.y), max(mx.z, b.z)))
    return mn, mx


def place_against(obj, ref, side, gap=0.3):
    """Sit obj's bounds flush against ref's side with `gap` metres of clearance between the bounds.
    side: front (-Y) / behind (+Y) / left (-X) / right (+X) / above (+Z) / below (-Z). Bounds based:
    an offset origin is handled, a concave leading face can still leave a visible gap."""
    W.update()
    r, o = W.tight_box(ref), W.tight_box(obj)
    rc, oc = W.box_center(r), W.box_center(o)
    h = W.box_size(o) * 0.5
    t = oc.copy()
    if side == 'behind':
        t.x, t.y = rc.x, r[1].y + gap + h.y
    elif side == 'front':
        t.x, t.y = rc.x, r[0].y - gap - h.y
    elif side == 'left':
        t.x, t.y = r[0].x - gap - h.x, rc.y
    elif side == 'right':
        t.x, t.y = r[1].x + gap + h.x, rc.y
    elif side == 'above':
        t.x, t.y, t.z = rc.x, rc.y, r[1].z + gap + h.z
    elif side == 'below':
        t.x, t.y, t.z = rc.x, rc.y, r[0].z - gap - h.z
    else:
        _log('place_against', 'unknown side "%s": use front/behind/left/right/above/below' % side)
        return
    W.move_world(obj, t - oc)


def place_touching(obj, target, side=None, dir=None, gap=0.0, grid=8, allow_intersect=False):
    """Slide obj along one axis until its leading face meets target's real geometry (rays fanned over
    the inner 80% of the leading bounds face; the nearest hit wins), stopping `gap` short (negative
    bites in). side: the way obj TRAVELS (left/right/front/behind/above/below) or dir=(x, y, z).
    Returns True on contact, False (obj unmoved) when nothing lies that way."""
    d = Vector(dir if dir is not None else SIDE_DIR.get(side, (0, 0, 0)))
    if d.length == 0:
        _log('place_touching', 'need a side (left/right/front/behind/above/below) or dir')
        return False
    d.normalize()
    W.update()
    dg = W.depsgraph()
    t_objs = W.collect(target, exclude=[obj])
    if not t_objs:
        _log('place_touching', 'target has no raycastable geometry')
        return False
    rays = W.Rays(t_objs, dg)
    b = W.tight_box(obj, dg=dg)
    ax = 0 if abs(d.x) > 0.5 else (2 if abs(d.z) > 0.5 else 1)
    lead = b[1][ax] if d[ax] > 0 else b[0][ax]
    span = [a for a in range(3) if a != ax]
    n = max(2, int(grid))
    best = None
    for i in range(n):
        for j in range(n):
            fi = 0.1 + 0.8 * (i / (n - 1))
            fj = 0.1 + 0.8 * (j / (n - 1))
            p = Vector((0.0, 0.0, 0.0))
            p[ax] = lead
            p[span[0]] = b[0][span[0]] + fi * (b[1][span[0]] - b[0][span[0]])
            p[span[1]] = b[0][span[1]] + fj * (b[1][span[1]] - b[0][span[1]])
            h = rays.cast(p, d)
            if h and (best is None or h[3] < best):
                best = h[3]
    if best is None:
        _log('place_touching', "no target surface in the '%s' direction: obj not moved (check the "
             "direction or starting positions, or use place_against)" % (side or 'dir'))
        return False
    W.move_world(obj, d * (best - gap))
    if allow_intersect:
        obj['allow_intersect'] = True
    return True


def surface_point(obj, direction, exclude=()):
    """The point on obj's surface facing `direction` (world), with its outward normal:
    {'point', 'normal', 'distance' (from the bounds centre)} or None."""
    W.update()
    dg = W.depsgraph()
    ms = W.collect(obj, exclude)
    if not ms:
        return None
    b = W.tight_box(obj, exclude, dg)
    c = W.box_center(b)
    R = W.box_size(b).length * 0.75 + 1e-3
    d = Vector(direction).normalized()
    h = W.Rays(ms, dg).cast(c + d * R, -d, 2 * R)
    if not h:
        return None
    n = h[1].copy()
    if n.dot(d) < 0:
        n.negate()
    return {'point': h[0], 'normal': n.normalized(), 'distance': (h[0] - c).length}


def mount_on(part, mount, dir=None, standoff=0.0, face_axis=None, exclude=()):
    """Seat `part` on a bearing point of `mount`'s surface: offset outward along the surface normal,
    touching only there. dir: world direction from the mount's centre toward the mounting side
    (default: toward the part). face_axis: the part's LOCAL axis to turn INTO the mount (omit to
    keep its rotation). Returns {'point', 'normal'} or None."""
    W.update()
    mb = W.tight_box(mount)
    mc = W.box_center(mb)
    d = Vector(dir) if dir is not None else part.matrix_world.translation - mc
    if d.length < 1e-4:
        d = Vector((0, -1, 0))
    sp = surface_point(mount, d, exclude)
    if not sp:
        _log('mount_on', "no surface found on '%s' toward %s: a different dir will find one"
             % (mount.name, tuple(round(v, 2) for v in d.normalized())))
        return None
    if face_axis is not None:
        target = -sp['normal']
        cur = part.matrix_world.to_quaternion() @ Vector(face_axis).normalized()
        q = cur.rotation_difference(target)
        mw = part.matrix_world.copy()
        loc = mw.translation.copy()
        rot = (q @ mw.to_quaternion()).to_matrix().to_4x4()
        sc = Matrix.Diagonal(mw.to_scale().to_4d())
        part.matrix_world = Matrix.Translation(loc) @ rot @ sc
        W.update()
    pb = W.tight_box(part)
    pc = W.box_center(pb)
    inward = -sp['normal']
    depth = 0.0
    dg = W.depsgraph()
    for m in W.collect(part):
        co = W.world_verts(m, dg, cap=4000)
        if len(co):
            depth = max(depth, float(((co - list(pc)) @ list(inward)).max()))
    target_c = sp['point'] + sp['normal'] * (standoff + depth)
    W.move_world(part, target_c - pc)
    _log('mount_on', "seated '%s' on '%s' at %s, bearing normal %s, standoff %gm"
         % (part.name, mount.name, tuple(round(v, 2) for v in sp['point']),
            tuple(round(v, 2) for v in sp['normal']), standoff))
    return {'point': sp['point'], 'normal': sp['normal']}


def snap_to_ground(obj, ground, z_offset=0.0, below=False, grid=None, surface_eps=0.0006):
    """Drop obj onto whatever surface of `ground` lies under its origin's WORLD XY (works under an
    offset parent). below=True casts from obj's current bottom instead of the sky: it lands on the
    nearest surface BENEATH where you put it (an interior shelf board). grid: footprint samples
    (default 5, or 9 when below). Records the support. Returns True/False."""
    W.update()
    dg = W.depsgraph()
    t_objs = W.collect(ground, exclude=[obj])
    if not t_objs:
        _log('snap_to_ground', 'no ground geometry provided')
        return False
    o_box = W.tight_box(obj, dg=dg)
    p = obj.matrix_world.translation
    start = o_box[0].z + 0.01 if below else max(o_box[1].z, p.z) + 100
    g = grid if grid is not None else (9 if below else 5)
    sup = support_under_footprint(obj, W.Rays(t_objs, dg), p.x, p.y, start, g, box=o_box)
    if not sup:
        _log('snap_to_ground', 'no ground under footprint at %.3f, %.3f%s'
             % (p.x, p.y, ' (below mode: is the item above a board?)' if below else ''))
        return False
    W.move_world(obj, (0, 0, sup[0] + z_offset + surface_eps - o_box[0].z))
    W.record_support(obj, ground)
    return True


def align_to_surface(obj, target, keep_yaw=True):
    """Turn obj's +Z to the normal of target's surface under its origin (signs on a slanted roof,
    props on a slope). keep_yaw (default) keeps its heading; the engine's alignToSurface replaced
    the whole rotation (keep_yaw=False)."""
    W.update()
    dg = W.depsgraph()
    t_objs = W.collect(target)
    tb = _union_boxes(t_objs, dg) if t_objs else None
    if not tb:
        _log('align_to_surface', 'no target geometry')
        return False
    p = obj.matrix_world.translation
    h = W.Rays(t_objs, dg).cast((p.x, p.y, tb[1].z + 100), _DOWN)
    if not h:
        _log('align_to_surface', 'no hit under the object')
        return False
    q = _UP.rotation_difference(h[1])
    if keep_yaw:
        yaw = obj.matrix_world.to_euler('XYZ').z
        q = q @ Quaternion((0, 0, 1), yaw)
    mw = obj.matrix_world.copy()
    sc = Matrix.Diagonal(mw.to_scale().to_4d())
    obj.matrix_world = Matrix.Translation(mw.translation) @ q.to_matrix().to_4x4() @ sc
    W.update()
    return True


def _lcg(seed):
    """The engine's scatterOn LCG: (imul(rng, 1103515245) + 12345) & 0x7fffffff, from (seed|0)||1."""
    s = int(seed) & 0xFFFFFFFF
    if s >= 0x80000000:
        s -= 0x100000000
    s = s or 1

    def rnd():
        nonlocal s
        s = ((s * 1103515245) + 12345) & 0x7FFFFFFF
        return s / 0x7FFFFFFF
    return rnd


def scatter_on(items, target, count=None, min_spacing=0.1, rng_seed=1, max_attempts=30, sink=0.0,
               tilt_max=0.0):
    """Spread items over target's top footprint, deterministic per rng_seed (the engine's LCG, and
    its sample order mapped through the axes, so a seed lays out the same as in WebGPU).
    sink: fraction or (min, max) of each item's height to bury; tilt_max: radians of random lean.
    Returns the items placed."""
    rnd = _lcg(rng_seed)
    W.update()
    dg = W.depsgraph()
    t_objs = W.collect(target, exclude=list(items))
    tb = _union_boxes(t_objs, dg)
    placed = []
    n = len(items) if count is None else min(count, len(items))
    for i in range(n):
        it = items[i]
        if tilt_max > 0:
            it.rotation_euler.x += (rnd() * 2 - 1) * tilt_max
            it.rotation_euler.y -= (rnd() * 2 - 1) * tilt_max     # three's z-lean is Blender's -y
            W.update()
        s = sink[0] + rnd() * (sink[1] - sink[0]) if isinstance(sink, (tuple, list)) else sink
        ok = False
        for _ in range(max_attempts):
            x = tb[0].x + rnd() * (tb[1].x - tb[0].x)
            y = tb[1].y - rnd() * (tb[1].y - tb[0].y)               # three z runs along Blender -y
            if not place_on(it, target, xy=(x, y), sink=s):
                continue
            p = it.matrix_world.translation
            if any((p - q.matrix_world.translation).length < min_spacing for q in placed):
                continue
            placed.append(it)
            ok = True
            break
        if not ok:
            _log('scatter_on', "couldn't fit item %d after %d attempts" % (i, max_attempts))
    return placed


def find_clear_spot(obj, around, radius=2.0, samples=16, scene=None, exclude=None, z=None):
    """Spiral-search a spot near `around` where obj's bounds overlap nothing else. Returns a world
    Vector (the bounds' bottom centre goes there) or None; then place_on(obj, ground,
    xy=(spot.x, spot.y)) seats it.

    The ground is not an obstacle: terrain (trimesh_collider, as make_terrain sets) and anything
    whose top is at or below the spot's bottom (a floor) are skipped. The engine's findClearSpot
    counted the terrain's whole box, so on hilly ground it found nothing."""
    W.update()
    dg = W.depsgraph()
    scene = scene or bpy.context.scene
    excl = list(exclude) if exclude is not None else [obj]
    if obj not in excl:
        excl.append(obj)
    b = W.tight_box(obj, dg=dg)
    size = W.box_size(b)
    a = Vector(around)
    zc = a.z if z is None else z
    others = [W.box_of_object(m, dg) for m in W.collect(scene, excl) if not W.flag(m, 'trimesh_collider')]
    others = [ob for ob in others if ob[1].z > zc + 1e-3]
    for i in range(samples):
        ang = i / samples * math.pi * 2
        r = radius * (0.3 + 0.7 * (i / samples))
        c = Vector((a.x + math.cos(ang) * r, a.y - math.sin(ang) * r, zc))
        tb = (c - Vector((size.x / 2, size.y / 2, 0)), c + Vector((size.x / 2, size.y / 2, size.z)))
        if not any(W.boxes_intersect(tb, ob) for ob in others):
            return c
    return None


def place_inside(obj, container, aim_z=None, match_yaw=True, xy_offset=None):
    """Rest obj on an interior surface of a container (a shelf board): centre it in the container's
    footprint at height aim_z (between the board you want and the one above), then
    snap_to_ground(below=True). match_yaw copies the container's heading. Returns the snap result."""
    if match_yaw:
        obj.rotation_euler.z = container.matrix_world.to_euler('XYZ').z
    W.update()
    cb = W.tight_box(container)
    cc = W.box_center(cb)
    z = (cb[0].z + cb[1].z) / 2 if aim_z is None else aim_z
    ob = W.tight_box(obj)
    oc = W.box_center(ob)
    W.move_world(obj, (cc.x - oc.x + (xy_offset[0] if xy_offset else 0),
                       cc.y - oc.y + (xy_offset[1] if xy_offset else 0), z - ob[0].z))
    ok = snap_to_ground(obj, container, below=True)
    if not ok:
        _log('place_inside', 'no interior surface beneath aim_z %.3f: check the preview for board heights' % z)
    return ok


def face_toward(obj, target, forward='-y'):
    """Yaw obj about Z so its `forward` local axis ('-y' default, '+y', '+x', '-x') points at target
    (an object, or a world point (x, y) / (x, y, z)). Pitch and roll are kept."""
    if forward not in _YAW:
        raise ValueError("forward must be '-y', '+y', '+x' or '-x' (the model's nose axis)")
    if isinstance(target, bpy.types.Object):
        tp = target.matrix_world.translation.copy()
    else:
        t = list(target)
        tp = Vector((t[0], t[1], t[2] if len(t) > 2 else obj.matrix_world.translation.z))
    if obj.parent:
        tp = (obj.parent.matrix_world @ obj.matrix_parent_inverse).inverted() @ tp
    d = tp - obj.location
    if d.x * d.x + d.y * d.y < 1e-10:
        return obj
    obj.rotation_euler.z = _YAW[forward](d.x, d.y)
    W.update()
    return obj


def station_beside(obj, machine, gap=0.2, side=None, face=True, forward='-y'):
    """A worker or machine that operates on something stands BESIDE it, facing it: obj goes clear of
    the machine's working edge (its short horizontal axis), base at the machine's floor level, nose
    aimed at the closest point of the line."""
    W.update()
    mb, ob = W.tight_box(machine), W.tight_box(obj)
    ms = W.box_size(mb)
    ax = 0 if ms.x <= ms.y else 1
    mc = W.box_center(mb)
    half = ms[ax] / 2
    o_half = W.box_size(ob)[ax] / 2
    oc = W.box_center(ob)
    sd = side if side is not None else (1 if oc[ax] >= mc[ax] else -1)
    t = oc.copy()
    t[ax] = mc[ax] + sd * (half + o_half + gap)
    la = 1 - ax
    t[la] = min(mb[1][la], max(mb[0][la], oc[la]))
    delta = t - oc
    delta.z = mb[0].z - ob[0].z
    W.move_world(obj, delta)
    if face:
        aim = obj.matrix_world.translation.copy()
        aim[ax] = mc[ax]
        face_toward(obj, aim, forward)
    return obj


def hinge(obj, edge='back'):
    """Make a part swing about one EDGE of its bounds (a lid, a door, a flap): an Empty at that
    edge's midpoint becomes obj's parent, obj's world transform kept. Rotate the returned pivot.
    edge: back (+Y), front (-Y), left (-X), right (+X), top (+Z), bottom (-Z).
    A lid hinged at the back opens with a NEGATIVE X rotation (front edge up); a front hinge with a
    positive one; a door on its left/right edge turns about Z."""
    W.update()
    b = W.tight_box(obj)
    p = W.box_center(b)
    if edge == 'back':
        p.y = b[1].y
    elif edge == 'front':
        p.y = b[0].y
    elif edge == 'left':
        p.x = b[0].x
    elif edge == 'right':
        p.x = b[1].x
    elif edge == 'top':
        p.z = b[1].z
    elif edge == 'bottom':
        p.z = b[0].z
    else:
        _log('hinge', 'unknown edge "%s": use back/front/left/right/top/bottom' % edge)
    piv = bpy.data.objects.new((obj.name or 'part') + '_hinge', None)
    piv.empty_display_type = 'ARROWS'
    piv.empty_display_size = 0.1
    for c in (obj.users_collection or [bpy.context.scene.collection]):
        c.objects.link(piv)
    if obj.parent:
        piv.parent = obj.parent
        piv.matrix_parent_inverse = obj.parent.matrix_world.inverted()
    piv.matrix_world = Matrix.Translation(p)
    W.update()
    mw = obj.matrix_world.copy()
    obj.parent = piv
    obj.matrix_parent_inverse = piv.matrix_world.inverted()
    obj.matrix_world = mw
    # the pivot is now the placed object: it carries what the part was seated on
    for k in ('_support_targets', '_support_target', '_sunk_placement', 'assembly'):
        if k in obj:
            piv[k] = obj[k]
    W.update()
    return piv
