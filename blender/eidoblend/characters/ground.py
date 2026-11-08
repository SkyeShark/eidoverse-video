"""eidoblend.characters.ground: the feet's contact points and the ground a body stands on (avatar_ground's port).

    from eidoblend.characters.ground import foot_points, Ground, ground_vrm
    feet = foot_points(me)             # {side: {'Foot': (n, 3) offsets, 'Toes': ...}}: the sole's candidates
    g = Ground(fn=lambda x, y: 0.02 * np.sin(x))    # or Ground(obj=terrain_mesh): rays straight down
    ground_vrm(me, g, frame)           # set the body down (vertically) so the lowest foot vertex touches the ground

THE FEET (as the WebGPU edition's groundVRM reads them): every vertex whose strongest skin weight is a Foot or Toes bone,
within `band` m of the set's lowest at the bind, thinned on a `voxel` grid. Each point is stored as an offset from its
bone's rest head in the armature's axes: the normalized frame is world-aligned at rest, so a point rides its bone as
p = head + W @ offset, with W the bone's normalized world turn. (The robot's feet are rigid parts, so the dominant-bone
rule is exact for them; a skinned human sole is approximated as rigid on its dominant bone.)

THE GROUND is a height function z = g(x, y) (numpy, vectorised) or a mesh read by downward rays (a BVHTree in world space,
rebuilt when asked). Ground.normal(x, y) is the surface normal from the heights around the point; Ground.plane(xs, ys)
fits a plane to the heights under a footprint (the sole's own tilt).
"""

import math

import numpy as np
from mathutils import Vector

SIDES = ('left', 'right')


def foot_points(h, band=0.05, voxel=0.004, meshes=None):
    out = {s: {'Foot': [], 'Toes': []} for s in SIDES}
    want = {}
    for s in SIDES:
        for b in ('Foot', 'Toes'):
            bn = h.humanoid.get(s + b)
            if bn:
                want[bn] = (s, b)
    inv = h.arm.matrix_world.inverted()
    for o in (meshes or h.meshes):
        if not o.vertex_groups:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        if not any(n in want for n in idx.values()):
            continue
        M = inv @ o.matrix_world
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            n = idx.get(best)
            if n in want:
                s, b = want[n]
                out[s][b].append(tuple(M @ v.co))
    res = {}
    for s in SIDES:
        allz = [p[2] for b in ('Foot', 'Toes') for p in out[s][b]]
        if not allz:
            res[s] = None
            continue
        zmin = min(allz)
        res[s] = {}
        for b in ('Foot', 'Toes'):
            P = np.array([p for p in out[s][b] if p[2] <= zmin + band], dtype=np.float64).reshape(-1, 3)
            if len(P) and voxel:
                key = np.floor(P / voxel).astype(np.int64)
                _u, first = np.unique(key, axis=0, return_index=True)
                P = P[np.sort(first)]
            head = np.array(h.rest_head[h.humanoid[s + b]])
            res[s][b] = P - head
        res[s]['zmin_rest'] = zmin
    return res


class Ground:
    def __init__(self, fn=None, obj=None, max_up=50.0):
        if fn is None and obj is None:
            raise ValueError('Ground needs fn (z = fn(x, y)) or obj (a mesh)')
        self.fn, self.obj, self.max_up = fn, obj, max_up
        self._bvh = None

    def bvh(self):
        if self._bvh is None:
            import bpy
            from mathutils.bvhtree import BVHTree
            dg = bpy.context.evaluated_depsgraph_get()
            ev = self.obj.evaluated_get(dg)
            me = ev.to_mesh()
            M = self.obj.matrix_world
            verts = [M @ v.co for v in me.vertices]
            polys = [tuple(p.vertices) for p in me.polygons]
            self._bvh = BVHTree.FromPolygons(verts, polys)
            ev.to_mesh_clear()
        return self._bvh

    def h(self, xs, ys):
        xs, ys = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
        if self.fn is not None:
            return np.asarray(self.fn(xs, ys), dtype=np.float64) + 0.0 * xs
        t = self.bvh()
        out = np.empty(xs.shape)
        down = Vector((0.0, 0.0, -1.0))
        for i, (x, y) in enumerate(zip(xs.ravel(), ys.ravel())):
            hit = t.ray_cast(Vector((x, y, self.max_up)), down)
            out.flat[i] = hit[0].z if hit[0] is not None else -1e9
        return out

    def normal(self, x, y, r=0.05):
        hx = self.h([x + r, x - r], [y, y])
        hy = self.h([x, x], [y + r, y - r])
        n = Vector((-(hx[0] - hx[1]) / (2 * r), -(hy[0] - hy[1]) / (2 * r), 1.0))
        return n.normalized()

    def plane(self, xs, ys):
        """a least-squares plane z = a x + b y + c under the points -> (normal Vector, heights)"""
        xs, ys = np.asarray(xs), np.asarray(ys)
        zs = self.h(xs, ys)
        A = np.stack([xs - xs.mean(), ys - ys.mean(), np.ones_like(xs)], axis=1)
        (a, b, _c), *_ = np.linalg.lstsq(A, zs - zs.mean(), rcond=None)
        return Vector((-a, -b, 1.0)).normalized(), zs


def posed_foot_world(h, feet, side):
    """the side's foot points in the world from the CURRENT evaluated pose (pose_bone.matrix): (n, 3)"""
    arm = h.arm
    out = []
    for b in ('Foot', 'Toes'):
        P = feet[side][b]
        if not len(P):
            continue
        bn = h.humanoid[side + b]
        pb = arm.pose.bones[bn]
        rest = arm.data.bones[bn].matrix_local
        M = np.array(arm.matrix_world @ pb.matrix @ rest.inverted())
        head = np.array(h.rest_head[bn])
        Q = P + head
        out.append(Q @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(out, axis=0) if out else np.zeros((0, 3))


def ground_vrm(h, ground, feet=None):
    """groundVRM: lower (or raise) the armature so the lowest foot point of either foot touches the ground under it;
    reads the current evaluated pose -> the vertical shift applied (m)"""
    import bpy
    feet = feet or foot_points(h)
    bpy.context.view_layer.update()
    gap = math.inf
    for s in SIDES:
        if feet.get(s) is None:
            continue
        P = posed_foot_world(h, feet, s)
        if len(P):
            gap = min(gap, float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1]))))
    if math.isfinite(gap):
        h.arm.location.z -= gap
        bpy.context.view_layer.update()
        return -gap
    return 0.0
