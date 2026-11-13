"""tests/harness/test_robot_sensors.py: RobotSensors' view of a scene where some things move (harness/navigation.py):
one BVH over everything (refresh()), or split by refresh(dynamic=movers) into the still part, built once, and the
movers' own BVH, which refresh(dynamic=movers, dynamic_only=True) rebuilds alone at each sense (Blender, no render).

The set: 400 crates on a 40k-vertex ground, a wall across it with a doorway, and five movers: a door sliding across the
doorway (keyed), a cart rolling along the wall (keyed) with a crate parented on it, a panel whose shape key folds it
(keyed), a crate turning in place (a driver), and a trolley that is a collection instance on a keyed Empty.

    the split view        at 6 frames, the senses of the split view (refresh(dynamic=movers) once, then dynamic_only=True
                          each frame) match a full rebuild's ray for ray (the same object at the same distance, 1e-5 m,
                          or a miss in both), and every ray that meets a mover meets it where the frame has it
    the nearer hit        a ray along the wall's face meets the cart (the moving view) in front of the wall (the still
                          view) behind it, and the wall once the cart has rolled past
    the still part kept   dynamic_only keeps the still part as built: a crate moved by hand is seen where it was until a
                          refresh that rebuilds the still part
    no split yet          dynamic_only on sensors never split builds both parts
    exclude               exclude(cart) keeps the split and drops the cart and the crate on it from the view
    the cost              2,000 crates beside a 250k-vertex ground: a full rebuild, and the movers' alone (under a tenth
                          of it)

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/harness/test_robot_sensors.py
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.dont_write_bytecode = True

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from eidoblend.harness.navigation import RobotSensors  # noqa: E402

FAIL = []


def check(ok, what):
    print(f"[sensors] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


# ------------------------------------------------------------------------------------------------- the set ---

def box_mesh(name, sx, sy, sz):
    me = bpy.data.meshes.new(name)
    v = [(x * sx / 2, y * sy / 2, z * sz) for x in (-1, 1) for y in (-1, 1) for z in (0, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    return me


def ground_mesh(name, n, size):
    """an n x n grid of quads with a gentle roll, triangles at one edge (a mixed polygon mesh)"""
    me = bpy.data.meshes.new(name)
    t = np.linspace(-size / 2, size / 2, n)
    x, y = np.meshgrid(t, t)
    z = 0.03 * np.sin(x * 0.7) * np.cos(y * 0.5)
    v = np.stack([x.ravel(), y.ravel(), z.ravel()], 1).tolist()
    f = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 2) for i in range(n - 1)]
    j = n - 2
    for i in range(n - 1):                                    # the last row as triangles
        f += [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1), (j * n + i, (j + 1) * n + i + 1, (j + 1) * n + i)]
    me.from_pydata(v, [], f)
    return me


def obj(name, me, loc=(0, 0, 0), col=None):
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def key_loc(ob, keys):
    for f, loc in keys:
        ob.location = loc
        ob.keyframe_insert('location', frame=f)


def build(n_crates, ground_n, size):
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 48
    rng = np.random.default_rng(7)
    obj('ground', ground_mesh('ground', ground_n, size))
    for k in range(n_crates):                                 # crates all round a clear 16 x 16 m middle
        while True:
            x, y = rng.uniform(-size / 2 + 1, size / 2 - 1, 2)
            if abs(y) > 8.0 or abs(x) > 8.0:
                break
        obj(f'crate{k}', box_mesh(f'crate{k}', 0.5, 0.5, 0.6), (x, y, 0.0))
    obj('wall_left', box_mesh('wall_left', 6.4, 0.2, 2.4), (-3.8, 0.0, 0.0))
    obj('wall_right', box_mesh('wall_right', 6.4, 0.2, 2.4), (3.8, 0.0, 0.0))
    movers = []
    door = obj('door', box_mesh('door', 1.2, 0.1, 2.2), (0.0, 0.15, 0.0))
    key_loc(door, [(1, (0.0, 0.15, 0.0)), (20, (0.0, 0.15, 0.0)), (40, (1.3, 0.15, 0.0))])
    cart = obj('cart', box_mesh('cart', 1.0, 0.7, 0.8), (-5.0, -1.2, 0.0))
    key_loc(cart, [(1, (-5.0, -1.2, 0.0)), (48, (5.0, -1.2, 0.0))])
    load = obj('cart_load', box_mesh('cart_load', 0.5, 0.5, 0.5), (0.0, 0.0, 0.8))
    load.parent = cart
    panel = obj('panel', box_mesh('panel', 1.5, 0.05, 1.5), (-2.5, -2.4, 0.0))
    panel.shape_key_add(name='Basis')
    fold = panel.shape_key_add(name='fold')
    for i, v in enumerate(fold.data):
        if v.co.z > 0.5:
            v.co.y -= 1.0
            v.co.z -= 0.6
    for f, val in ((1, 0.0), (48, 1.0)):
        fold.value = val
        fold.keyframe_insert('value', frame=f)
    turner = obj('turner', box_mesh('turner', 1.4, 0.3, 1.0), (2.6, -2.5, 0.0))
    d = turner.driver_add('rotation_euler', 2).driver
    d.expression = 'frame * 0.06'
    lib = bpy.data.collections.new('trolley_parts')              # instanced only: not in the scene itself
    obj('trolley_box', box_mesh('trolley_box', 0.8, 0.6, 1.1), (0.0, 0.0, 0.0), col=lib)
    trolley = bpy.data.objects.new('trolley', None)
    trolley.instance_type = 'COLLECTION'
    trolley.instance_collection = lib
    sc.collection.objects.link(trolley)
    key_loc(trolley, [(1, (4.5, 2.0, 0.0)), (48, (-4.5, 2.0, 0.0))])
    movers = [door, cart, panel, turner, trolley]
    sc.frame_set(1)
    return sc, movers


# ---------------------------------------------------------------------------------------------- the senses ---

SENSES =[((0.0, -6.0, 1.5), math.pi, 0.2), ((3.0, -4.5, 1.5), math.pi + 0.5, 0.35),
          ((-3.0, 4.5, 1.5), 0.0, 0.25), ((0.0, -3.0, 1.2), math.pi, 0.05)]


def rays(s):
    out = []
    for origin, heading, pitch in SENSES:
        out += [(Vector(origin), h['dir']) for h in s.sense(origin, heading, pitch)['hits']]
    return out


def same_hits(a, b, ray_list, dist):
    """(rays compared, the rays that differ: hit or miss, object, distance > 1e-5 m)"""
    bad = []
    for o, d in ray_list:
        ha, hb = a(o, d, dist), b(o, d, dist)
        if (ha[0] is None) != (hb[0] is None):
            bad.append(('hit/miss', ha[2], hb[2]))
        elif ha[0] is not None and (ha[2] != hb[2] or abs(ha[3] - hb[3]) > 1e-5):
            bad.append((ha[2].name, hb[2].name, round(ha[3] - hb[3], 7)))
    return len(ray_list), bad


def on_its_surface(sc, s, origin_heading_pitch, mover_names):
    """every hit the sensors report on a mover lies on that mover's surface as the scene has it now (mm)"""
    dg = bpy.context.evaluated_depsgraph_get()
    trees = {}
    for inst in dg.object_instances:
        if inst.object.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent else inst.object.original
        if src.name in mover_names or inst.object.original.name in mover_names:
            me = inst.object.data
            mw = inst.matrix_world
            v = [mw @ x.co for x in me.vertices]
            trees.setdefault(src.name, []).append(BVHTree.FromPolygons(v, [list(p.vertices) for p in me.polygons]))
    worst, n = 0.0, 0
    for origin, heading, pitch in origin_heading_pitch:
        for h in s.sense(origin, heading, pitch)['hits']:
            if h['hit'] and h['object'].name in trees:
                gap = min(t.find_nearest(h['point'])[3] for t in trees[h['object'].name])
                worst, n = max(worst, gap), n + 1
    return n, worst


# ---------------------------------------------------------------------------------------------------- checks ---

def main():
    sc, movers = build(400, 200, 40.0)
    names = {'door', 'cart', 'cart_load', 'panel', 'turner', 'trolley'}
    full = RobotSensors(sc, range=12.0)

    # the split view against a full rebuild, frame by frame
    split = RobotSensors(sc, range=12.0)
    sc.frame_set(1)
    n_split = split.refresh(dynamic=movers)
    check(split.dynamic == frozenset(names) and split._bvh_dyn is not None,
          f'refresh(dynamic=movers) splits the view: {n_split} meshes, the moving part {sorted(split.dynamic or ())}')
    diffs, total, gaps = [], 0, []
    for f in (1, 9, 18, 27, 36, 48):
        sc.frame_set(f)
        full.refresh()
        split.refresh(dynamic=movers, dynamic_only=True)
        n, bad = same_hits(full._cast, split._cast, rays(full), 12.0)
        total += n
        if bad:
            diffs.append((f, bad[:3]))
        gaps.append(on_its_surface(sc, split, SENSES, names))
    check(not diffs, f'the split view (the movers rebuilt alone each frame) matches a full rebuild ray for ray: '
          f'{total} rays at 6 frames, differing {diffs}')
    n_mov = sum(n for n, _w in gaps)
    check(n_mov > 50 and max(w for _n, w in gaps) < 1e-4,
          f'every hit on a mover lies on its surface as the frame has it: {n_mov} hits, the worst '
          f'{max(w for _n, w in gaps) * 1000:.3f} mm off')

    # the nearer hit across the two views: along the wall's face, the cart in front of the wall, then the wall
    sc.frame_set(24)                                          # the cart at x ~ -0.1, in front of the doorway's left jamb
    split.refresh(dynamic=movers, dynamic_only=True)
    cart = bpy.data.objects['cart']
    o = Vector((cart.location.x, -6.0, 0.4))
    h = split.cast_one(o, (0.0, 1.0, 0.0), 12.0)
    sc.frame_set(48)
    split.refresh(dynamic=movers, dynamic_only=True)
    o2 = Vector((-5.0, -6.0, 0.4))                            # where the cart started; it has rolled to x = 5
    h2 = split.cast_one(o2, (0.0, 1.0, 0.0), 12.0)
    check(h['hit'] and h['object'].name == 'cart' and abs(h['distance'] - (6.0 - 1.2 - 0.35)) < 1e-4
          and h2['hit'] and h2['object'].name == 'wall_left' and abs(h2['distance'] - 5.9) < 1e-4,
          f"the nearer hit wins: at f24 the cart at {h['distance']:.3f} m ({h['object'] and h['object'].name}), at "
          f"f48 the wall behind at {h2['distance']:.3f} m ({h2['object'] and h2['object'].name})")

    # dynamic_only keeps the still part as built
    crate = bpy.data.objects['crate0']
    was = crate.location.copy()
    crate.location = (0.0, -5.0, 0.0)                         # moved by hand onto the line of sight
    bpy.context.view_layer.update()
    split.refresh(dynamic=movers, dynamic_only=True)
    a = split.cast_one((0.0, -8.0, 0.3), (0.0, 1.0, 0.0), 12.0)
    split.refresh(dynamic=movers)
    b = split.cast_one((0.0, -8.0, 0.3), (0.0, 1.0, 0.0), 12.0)
    check((a['object'] is None or a['object'].name != 'crate0') and b['object'] is not None
          and b['object'].name == 'crate0' and abs(b['distance'] - 2.75) < 1e-4,
          f"dynamic_only keeps the still part as it was built (a crate moved by hand is not seen there: "
          f"{a['object'] and a['object'].name}); refresh(dynamic=movers) rebuilds it (crate0 at {b['distance']:.3f} m)")
    crate.location = was
    bpy.context.view_layer.update()
    split.refresh(dynamic=movers)

    # dynamic_only on sensors never split builds both parts
    fresh = RobotSensors(sc, range=12.0)
    fresh.refresh(dynamic=movers, dynamic_only=True)
    full.refresh()
    n, bad = same_hits(full._cast, fresh._cast, rays(full), 12.0)
    check(fresh.dynamic == frozenset(names) and fresh._bvh is not None and not bad,
          f'dynamic_only with no split yet builds both parts: {n} rays as a full rebuild sees them, differing {bad[:3]}')

    # exclude keeps the split and drops the object and what it carries
    sc.frame_set(24)
    split.refresh(dynamic=movers, dynamic_only=True)
    split.exclude(cart)
    h3 = split.cast_one(o, (0.0, 1.0, 0.0), 12.0)
    h4 = split.cast_one((cart.location.x, -6.0, 1.05), (0.0, 1.0, 0.0), 12.0)
    gone = ('cart', 'cart_load')
    check(split.dynamic is not None and 'cart' not in split.dynamic and 'cart_load' not in split.dynamic
          and h3['object'] is not None and h3['object'].name not in gone
          and (h4['object'] is None or h4['object'].name not in gone),
          f"exclude(cart) keeps the split ({sorted(split.dynamic or ())}) and the cart and its load leave the view: "
          f"the ray that met the cart now meets {h3['object'] and h3['object'].name}")

    # the cost
    sc, movers = build(2000, 500, 60.0)
    big = RobotSensors(sc, range=12.0)
    t_full = []
    for _ in range(3):
        t = time.perf_counter()
        n_full = big.refresh()
        t_full.append(time.perf_counter() - t)
    big.refresh(dynamic=movers)
    t_dyn = []
    for f in (5, 9, 13):
        sc.frame_set(f)
        t = time.perf_counter()
        big.refresh(dynamic=movers, dynamic_only=True)
        t_dyn.append(time.perf_counter() - t)
    tf, td = min(t_full) * 1e3, min(t_dyn) * 1e3
    check(td < 0.1 * tf, f'the cost, {n_full} meshes (2,000 crates, a 250k-vertex ground): the movers rebuilt alone '
          f'take under a tenth of a full rebuild ({td:.1f} ms against {tf:.0f} ms)')
    print(f'[sensors] {"FAIL" if FAIL else "PASS"}: {len(FAIL)} failed', flush=True)
    return len(FAIL)


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(1)
