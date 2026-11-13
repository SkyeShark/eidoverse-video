"""eidoblend.characters.controller.world: the walkable world the controller and the foot IK probe.

The WebGPU controller lives in a Rapier world built from the scene's collision meshes: its ground probes are shape
casts of a 1 cm ball straight down (castShape + witness1), the foot IK's are rays (castRayAndGetNormal) and 1.5 cm
ball casts, and its upper-body cylinder slides along walls (Rapier's character controller). Here the world is one
BVH tree over the meshes, in world space, and the same three queries run against it:

    from eidoblend.characters.controller import CollisionWorld
    world = CollisionWorld([floor, stairs, ramp])        # the meshes walked on and against (default: every visible mesh
                                                          # that is not skinned to an armature: a VRM never probes itself)
    hit = world.raycast_down(Vector((x, y, z)), 2.0)      # Hit: .hit .point .normal .distance .object
    hit = world.sphere_cast_down(Vector((x, y, z)), 0.015, 2.0)   # the first contact of a falling ball
    z = world.ground_vector(x, y, z_from)                 # the controller's probe: a surface z, or None
    under, below = world.underside(x, y, z)               # a surface seen from under it: its underside, what lies below
    world.inside_solid(Vector((x, y, z)))                 # a point inside a solid (by its faces' winding)
    world.h(xs, ys)                                       # heights under points (numpy): a Ground for round one's walk_path

A ball cast is emulated with rays (Blender has no shape sweep): rays at the centre and on two rings (r / 2 and r, eight
each); the ball touches first where z + sqrt(r^2 - d^2) is highest (d: the ray's offset from the centre). Its contact
normal is the hit face's normal for a contact under the centre, else the direction from the contact to the ball's centre
at contact (an edge: horizontal at the rim). A hit whose normal's z is under the caller's limit is no ground (a riser, a
wall), as the WebGPU edition's -normal2.y test rejects it.

Blender's axes throughout: Z is up, metres. The tree is built from the evaluated meshes (modifiers applied) when the world
is made; refresh() rebuilds it after the scene changes.
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DOWN = Vector((0.0, 0.0, -1.0))
UP = Vector((0.0, 0.0, 1.0))


class Hit:
    """a cast's result, as the WebGPU edition's {hit, point, normal, distance}"""
    __slots__ = ('hit', 'point', 'normal', 'distance', 'object')

    def __init__(self, hit=False, point=None, normal=None, distance=None, obj=None):
        self.hit, self.point, self.normal, self.distance, self.object = hit, point, normal, distance, obj

    def __bool__(self):
        return bool(self.hit)

    def __repr__(self):
        if not self.hit:
            return 'Hit(miss)'
        return f'Hit({tuple(round(c, 4) for c in self.point)}, n={tuple(round(c, 3) for c in self.normal)}, d={self.distance:.4f})'


MISS = Hit(False)


def _is_skinned(ob):
    return any(m.type == 'ARMATURE' for m in ob.modifiers) or (ob.parent is not None and ob.parent.type == 'ARMATURE')


class CollisionWorld:
    """the walkable world: a BVH over `objects` (meshes) in world space"""

    def __init__(self, objects=None, exclude=(), scene=None):
        self.scene = scene or bpy.context.scene
        self.exclude = set(exclude)
        self._explicit = list(objects) if objects is not None else None
        self.objects = []
        self.tree = None
        self._poly_obj = None
        self.casts = 0
        self.refresh()

    # ------------------------------------------------------------------------------------------------ the tree
    def _pick(self):
        if self._explicit is not None:
            return [o for o in self._explicit if o is not None and o.type == 'MESH' and o not in self.exclude]
        out = []
        for o in self.scene.objects:
            if o.type != 'MESH' or o in self.exclude or o.hide_render or o.hide_get():
                continue
            if _is_skinned(o):
                continue
            out.append(o)
        return out

    def refresh(self):
        """rebuild the tree from the objects' evaluated meshes (call after the scene changes)"""
        self.objects = self._pick()
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys, owner = [], [], []
        for o in self.objects:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            M = o.matrix_world
            base = len(verts)
            verts.extend(M @ v.co for v in me.vertices)
            for p in me.polygons:
                polys.append(tuple(base + i for i in p.vertices))
                owner.append(o)
            ev.to_mesh_clear()
        if not polys:
            raise ValueError('CollisionWorld: no mesh to walk on (pass objects=[...])')
        self.tree = BVHTree.FromPolygons(verts, polys)
        self._poly_obj = owner
        self.top = max(v.z for v in verts)          # the highest point of the world (a ray from over it starts outside)
        self.casts = 0
        return self

    def add(self, *objects):
        self._explicit = (self._explicit if self._explicit is not None else self._pick()) + list(objects)
        return self.refresh()

    # ------------------------------------------------------------------------------------------------ rays
    def ray_cast(self, origin, direction, max_dist=1e4):
        """the first hit along a ray -> Hit (normal: the face's, facing the ray's origin)"""
        self.casts += 1
        d = Vector(direction).normalized()
        loc, nrm, idx, dist = self.tree.ray_cast(Vector(origin), d, max_dist)
        if loc is None:
            return MISS
        n = Vector(nrm)
        if n.dot(d) > 0.0:
            n = -n
        return Hit(True, Vector(loc), n, dist, self._poly_obj[idx] if idx is not None else None)

    def raycast_down(self, origin, dist):
        """castRayAndGetNormal straight down (foot_ik.js raycastDown)"""
        return self.ray_cast(origin, DOWN, dist)

    def underside(self, x, y, z, step=0.002, faces=8):
        """a surface met at height z over (x, y), seen from under it, straight down: from just under it through the
        faces that face down (the bottom of the solid it tops, by its faces' winding; a sheet is its own underside) to
        the first face that faces up -> (the underside's z, that face's z or None where nothing lies under it). Faces
        that lie on one another count together (a block standing on the floor: its bottom on the floor's top, a ray
        meets either first): a bottom with a top on it has that top under it, no room between. The space between the
        two is open air: where its middle lies inside a solid (inside_solid), the face met is inside that solid (the
        ground plane's face inside a block sunk 2 mm into it, as the course builder stands its blocks) and the ray goes
        on through it to the solid's bottom"""
        under = z
        o = Vector((x, y, z - step))
        for _ in range(faces):
            self.casts += 1
            loc, nrm, _i, _d = self.tree.ray_cast(o, DOWN, 1e4)
            if loc is None:
                return under, None
            here = [n.z for _l, n, _k, _dd in self.tree.find_nearest_range(loc, 1e-4)] + [nrm.z]
            bottom = any(nz < -0.5 for nz in here)
            if bottom:
                under = loc.z
            if (not bottom or any(nz > 0.5 for nz in here)) and (
                    under - loc.z < step or not self.inside_solid(Vector((x, y, 0.5 * (under + loc.z))))):
                return under, loc.z
            o = Vector((x, y, loc.z - step))
        return under, None

    def inside_solid(self, p, rays=4, crossings=64):
        """whether p lies inside a solid, by its faces' winding: along each of `rays` level rays from p (turned off the
        axes, clear of a box's edges) the faces it leaves through (met from their back) less the faces it enters
        through (met from their front) count the solids p lies inside; faces lying on one another count together (two
        blocks built against each other: the ladder block and the platform behind it). Inside where most rays count
        one or more. A doorway's jambs, a room's walls seen from inside it and open space count none. A ray that meets
        more than `crossings` faces counts as inside (the surface over p is then kept as the ground, as the original
        reads it)"""
        votes = 0
        for k in range(rays):
            a = 0.37 + 2.0 * math.pi * k / rays
            d = Vector((math.cos(a), math.sin(a), 0.0))
            o, depth = Vector(p), 0
            for _ in range(crossings):
                self.casts += 1
                loc, nrm, idx, _dist = self.tree.ray_cast(o, d, 1e4)
                if loc is None:
                    break
                faces = {i: n for _c, n, i, _dd in self.tree.find_nearest_range(loc, 1e-4)}
                faces[idx] = nrm
                for n in faces.values():
                    s = n.dot(d)
                    if abs(s) > 1e-3:
                        depth += 1 if s > 0.0 else -1
                o = loc + d * 1e-4
            else:
                depth = 1
            votes += depth > 0
        return 2 * votes > rays

    def sphere_cast_down(self, origin, radius, dist, min_normal=0.0):
        """a ball of `radius` dropped from `origin` (its centre) for at most `dist`: the contact point on the surface it
        touches first (Rapier's witness1), its contact normal and the distance the centre fell + radius (foot_ik.js
        sphereCastDown's time_of_impact + radius). A contact whose normal z is under min_normal is no hit (the caller's
        upward test: the controller's 0.5, the foot IK's NormalUpThreshold 0.7)."""
        o = Vector(origin)
        best, best_c = None, -math.inf
        rings = [(0.0, 1)] + [(radius * 0.5, 8), (radius * 0.999, 8)]
        for rr, n in rings:
            for k in range(n):
                a = 2.0 * math.pi * k / n
                off = Vector((rr * math.cos(a), rr * math.sin(a), 0.0))
                h = self.ray_cast(o + off, DOWN, dist + radius)
                if not h.hit:
                    continue
                c = h.point.z + math.sqrt(max(0.0, radius * radius - rr * rr))   # the centre's height at this contact
                if c > best_c + 1e-9:
                    best_c, best = c, (h, rr, off)
        if best is None:
            return MISS
        h, rr, off = best
        nf = h.normal
        if nf.z < 1e-3:
            return MISS

        def zplane(x, y):                     # the winning face's plane, as a height over (x, y)
            return h.point.z - (nf.x * (x - h.point.x) + nf.y * (y - h.point.y)) / nf.z

        def on_face(q):
            return q.hit and q.normal.dot(nf) > 0.999 and abs(q.point.z - zplane(q.point.x, q.point.y)) < 1e-4
        if rr < 1e-9 or on_face(self.ray_cast(o, DOWN, dist + radius)):
            # the face runs under the centre: the ball rests on its plane (centre r along the normal from it)
            best_c = zplane(o.x, o.y) + radius / nf.z
            point, n = Vector((o.x, o.y, best_c)) - nf * radius, nf.copy()
        else:
            # a face the centre's ray misses: the ball rests on its EDGE between the centre and the ring ray. Bisect
            # for the edge (the nearest offset still on the face) and sit the ball on it, as Rapier's swept ball does
            # (its witness the edge point, its normal from the edge to the centre)
            u = off / rr
            lo, hi = 0.0, rr
            for _ in range(8):
                mid = 0.5 * (lo + hi)
                if on_face(self.ray_cast(o + u * mid, DOWN, dist + radius)):
                    hi = mid
                else:
                    lo = mid
            point = Vector((o.x + u.x * hi, o.y + u.y * hi, zplane(o.x + u.x * hi, o.y + u.y * hi)))
            best_c = max(best_c, point.z + math.sqrt(max(0.0, radius * radius - hi * hi)))
            n = (Vector((o.x, o.y, best_c)) - point).normalized()
        fall = o.z - best_c
        if fall < -1e-6 or fall > dist:
            return MISS
        if n.z < min_normal:
            return MISS
        return Hit(True, point, n, fall + radius, h.object)

    def ground_vector(self, x, y, origin_z, radius=0.01, min_normal=0.5, max_dist=2000.0):
        """the controller's _groundVector: a small ball cast down from (x, y, origin_z) -> the contact's z, or None
        (nothing below, or a side hit: a contact normal under min_normal)"""
        h = self.sphere_cast_down(Vector((x, y, origin_z)), radius, max_dist, min_normal=min_normal)
        return h.point.z if h.hit else None

    # ------------------------------------------------------------------------------------------------ a Ground
    def h(self, xs, ys, z_from=None, max_up=50.0):
        """heights under points (numpy, vectorised over the inputs): the first surface below z_from (a scalar or an
        array like xs; default max_up). Points over nothing read -1e9. Round one's Ground interface, so walk_path and
        the checks read this world as they read a height function."""
        xs, ys = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
        zf = np.broadcast_to(np.asarray(max_up if z_from is None else z_from, dtype=np.float64), xs.shape)
        out = np.empty(xs.shape)
        for i, (x, y, z0) in enumerate(zip(xs.ravel(), ys.ravel(), zf.ravel())):
            hit = self.ray_cast(Vector((x, y, z0)), DOWN)
            out.flat[i] = hit.point.z if hit.hit else -1e9
        return out

    def normal(self, x, y, r=0.05, z_from=None):
        hx = self.h([x + r, x - r], [y, y], z_from)
        hy = self.h([x, x], [y + r, y - r], z_from)
        return Vector((-(hx[0] - hx[1]) / (2 * r), -(hy[0] - hy[1]) / (2 * r), 1.0)).normalized()

    def plane(self, xs, ys, z_from=None):
        """a least-squares plane under the points -> (normal Vector, heights) (ground.Ground.plane)"""
        xs, ys = np.asarray(xs), np.asarray(ys)
        zs = self.h(xs, ys, z_from)
        A = np.stack([xs - xs.mean(), ys - ys.mean(), np.ones_like(xs)], axis=1)
        (a, b, _c), *_ = np.linalg.lstsq(A, zs - zs.mean(), rcond=None)
        return Vector((-a, -b, 1.0)).normalized(), zs

    # ------------------------------------------------------------------------------------------------ walls
    def move_and_slide(self, centre, delta, radius, half_height, skin=0.05, heights=(-0.9, -0.45, 0.0, 0.45, 0.9),
                       max_climb_normal=0.5, iterations=3):
        """the upper-body cylinder's horizontal move against walls (Rapier's computeColliderMovement with Y = 0):
        `centre` the cylinder's centre, `delta` the wanted (dx, dy). Rays from the cylinder's axis at `heights` (fractions
        of its half height) in the move's direction and either side of it find a wall within radius + skin + the move;
        the move's part into the wall is taken out (a slide along it). A surface whose normal z is over
        max_climb_normal is ground, not a wall. -> the corrected (dx, dy)"""
        c = Vector(centre)
        d = Vector((delta[0], delta[1], 0.0))
        for _ in range(iterations):
            L = d.length
            if L < 1e-9:
                break
            u = d / L
            side = Vector((-u.y, u.x, 0.0))
            worst = None
            for fz in heights:
                o = c + Vector((0.0, 0.0, fz * half_height))
                for dirv in (u, (u + side * 0.7).normalized(), (u - side * 0.7).normalized()):
                    reach = radius + skin + L * max(0.0, dirv.dot(u))
                    h = self.ray_cast(o, dirv, reach)
                    if not h.hit or abs(h.normal.z) > max_climb_normal:
                        continue
                    n = Vector((h.normal.x, h.normal.y, 0.0))
                    if n.length < 1e-6:
                        continue
                    n.normalize()
                    # how far the cylinder may still go toward this wall along u
                    clearance = (h.point - o).dot(-n) - radius - skin
                    into = d.dot(-n)
                    if into > clearance and (worst is None or into - clearance > worst[0]):
                        worst = (into - clearance, n)
            if worst is None:
                break
            excess, n = worst
            d = d + n * excess
        return d.x, d.y
