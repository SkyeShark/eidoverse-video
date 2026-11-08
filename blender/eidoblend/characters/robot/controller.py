"""eidoblend.characters.robot.controller: EidoverseRobotController (eidoverse/robot_controller.js) and the legs it drives.

    from eidoblend.characters.robot import EidoverseRobotController
    ctl = EidoverseRobotController.create(me, rig=rig, opts={'start_position': (0, 0, 0), 'start_heading': 0.0,
                                                             'walk_speed': 1.0, 'collision_meshes': [floor, walls]})
    ctl.set_waypoints([(2.0, -1.0), (4.0, 0.5)])
    for f in range(1, 241):
        ctl.update((f - 1) / fps, 1 / fps)       # VRMRobotBody calls this; a scene that walks waypoints alone may too
    rep = ctl.bake(f0=1)                          # the run keyed: one action, every frame renders alone

The WebGPU adapter presents the waypoint contract VRMRobotBody was written against (set_waypoints, update(t, dt),
get_state / get_heading / get_position, heading, walk_speed / run_speed, force_action, is_stalled, begin_seated /
end_seated, on_pre_vrm_update) over the engine's physics character controller: each frame the current waypoint becomes
a unit direction for charCtrl.locomote (which turns the facing toward it at maxTurnRate and walks forward along the
facing at the tread-synced speed), arrival within arrive_radius moves to the next waypoint, a collision stall (six frames
of move-and-slide cancelling the step) latches the input to zero, and emotes / seated clips suspend the walk. That logic
is ported line for line (update, set_waypoints, force_action, is_stalled, begin_seated, end_seated, the accessors).

THE LEGS. The engine's charCtrl (VRMCharacterController: Rapier, the gait tree, foot IK) runs live in the browser. In a
film the run is solved at build time and keyed, so the legs here, RobotLegs, are two passes:
  1. live, frame by frame, while VRMRobotBody senses, plans and decides: a kinematic body. The adapter hands it the
     waypoints; it walks them along a route it can actually walk: each corner rounded by an arc of radius speed /
     max_turn_rate whose middle passes THROUGH the planned corner (the corner is pushed out along its bisector first, so
     the arc keeps the planner's clearance instead of cutting inside it), a start that turns from the current facing on
     the same radius. It moves at the gait's speed, stops where its cylinder (agent_radius) would meet a collision mesh
     (the stall the adapter latches on), records each frame (state, place, facing, the clip, the gaze the body set).
  2. bake(): the record keyed through my body's passes. Each standing span plays the idle (or the emote, or the seated
     clip) through the example's frame order (eidoblend.characters.robot.rig); each walking span is round one's walk_path
     along the route it travelled (planted feet, the swing's clearance, the corners' arcs), then the hands, the wrists'
     stages, the gaze, the head and the crown (rig.post_pass); a walk starts at its stance foot's mid-stance and stops at
     the nearest one, and the hand-over between standing and walking crossfades with that foot held where it stands.
legs_class: any object with this contract may stand in (the controller family's VRMCharacterController port, when it has
locomote and bake). The JS's VRMUtils merge (fewer skinned draws in three) and the Rapier world do not apply in Blender.
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .._math import D2R, wrap_pi
from ..ground import Ground

FWD = Vector((0.0, -1.0, 0.0))            # a VRM faces -Y: heading 0 (the same number as three's rotation.y)


def heading_vector(h):
    """the facing for a heading (rad about +Z, 0 = -Y, counter-clockwise): three's (sin h, 0, cos h) in Blender's axes"""
    return Vector((math.sin(h), -math.cos(h)))


def heading_of(dx, dy):
    """the heading that faces (dx, dy)"""
    return math.atan2(dx, -dy)


# ------------------------------------------------------------------------------------------------------------ routes
def build_route(p0, h0, points, radius, ds=0.02):
    """a route the legs can walk from p0 (facing h0) through `points`: a start arc of `radius` from the facing toward the
    first point, then each corner rounded by an arc of `radius` that passes through the corner (the corner pushed out
    along its bisector by r (sec(phi / 2) - 1), capped at r) -> {'P': (n, 2), 'H': (n,) headings, 'S': (n,) arc length,
    'total'}"""
    P = [np.array(p0[:2], dtype=float)]
    for q in points:
        q = np.array(q[:2], dtype=float)
        if np.linalg.norm(q - P[-1]) > 1e-4:
            P.append(q)
    out_p, out_h = [P[0].copy()], [h0]
    if len(P) < 2:
        return _route(out_p, out_h)
    r = max(1e-3, float(radius))
    # the start: an arc tangent to the facing, turning toward the first point until the tangent meets it
    f0 = np.array([math.sin(h0), -math.cos(h0)])
    d = P[1] - P[0]
    turn = math.atan2(f0[0] * d[1] - f0[1] * d[0], float(f0 @ d))
    cur, hc = P[0].copy(), h0
    if abs(turn) > 2 * D2R:
        s = 1.0 if turn > 0 else -1.0                        # + turns left (counter-clockwise)
        n = np.array([-f0[1], f0[0]]) * s
        c = P[0] + n * r
        dist = np.linalg.norm(P[1] - c)
        if dist > r * 1.02:
            # the tangent point T on the circle whose tangent (in the turning sense) points at P1
            ang_c = math.atan2(P[1][1] - c[1], P[1][0] - c[0])
            beta = math.acos(min(1.0, r / dist))
            tang = ang_c - s * beta
            a0 = math.atan2(P[0][1] - c[1], P[0][0] - c[0])
            sweep = wrap_pi(tang - a0)
            if s > 0 and sweep < 0:
                sweep += 2 * math.pi
            if s < 0 and sweep > 0:
                sweep -= 2 * math.pi
            m = max(1, int(abs(sweep) * r / ds))
            for k in range(1, m + 1):
                a = a0 + sweep * k / m
                out_p.append(c + r * np.array([math.cos(a), math.sin(a)]))
                out_h.append(h0 + sweep * k / m)
            cur, hc = out_p[-1].copy(), out_h[-1]
    pts = [cur] + P[1:]
    if len(pts) >= 3:
        # the corners pushed out so their arcs pass through them
        Q = [pts[0]]
        for j in range(1, len(pts) - 1):
            a, b, cpt = pts[j - 1], pts[j], pts[j + 1]
            u, v = b - a, cpt - b
            lu, lv = np.linalg.norm(u), np.linalg.norm(v)
            if lu < 1e-6 or lv < 1e-6:
                Q.append(b)
                continue
            u, v = u / lu, v / lv
            phi = math.atan2(u[0] * v[1] - u[1] * v[0], float(u @ v))
            if abs(phi) < 1e-3:
                Q.append(b)
                continue
            bis_in = v - u
            bis_in /= max(1e-9, np.linalg.norm(bis_in))
            delta = min(r, r * (1.0 / math.cos(abs(phi) / 2) - 1.0))
            Q.append(b - bis_in * delta)
        Q.append(pts[-1])
        pts = Q
    # straight runs and fillets, sampled
    for j in range(len(pts) - 1):
        a, b = pts[j], pts[j + 1]
        u = b - a
        L = float(np.linalg.norm(u))
        if L < 1e-6:
            continue
        u /= L
        t_in = 0.0
        if j > 0:
            t_in = _trim(pts[j - 1], a, b, r)
        t_out = _trim(a, b, pts[j + 2], r) if j + 2 < len(pts) else 0.0
        hseg = heading_of(u[0], u[1])
        s0, s1 = t_in, L - t_out
        m = max(1, int((s1 - s0) / ds))
        for k in range(0, m + 1):
            p = a + u * (s0 + (s1 - s0) * k / m)
            if np.linalg.norm(p - out_p[-1]) > 1e-6:
                out_p.append(p)
                out_h.append(_unwrap(out_h[-1], hseg))
        if j + 2 < len(pts):
            c_ = pts[j + 2]
            v = c_ - b
            v /= max(1e-9, np.linalg.norm(v))
            phi = math.atan2(u[0] * v[1] - u[1] * v[0], float(u @ v))
            t = _trim(a, b, c_, r)
            rr = t / math.tan(abs(phi) / 2) if abs(phi) > 1e-3 else 0.0
            if rr > 1e-4:
                start = b - u * t
                s_ = 1.0 if phi > 0 else -1.0
                nrm = np.array([-u[1], u[0]]) * s_
                cc = start + nrm * rr
                a0 = math.atan2(start[1] - cc[1], start[0] - cc[0])
                m = max(1, int(abs(phi) * rr / ds))
                for k in range(1, m + 1):
                    ang = a0 + phi * k / m
                    p = cc + rr * np.array([math.cos(ang), math.sin(ang)])
                    out_p.append(p)
                    out_h.append(_unwrap(out_h[-1], hseg + phi * k / m))
    return _route(out_p, out_h)


def _trim(a, b, c, r):
    """how far before corner b the arc of radius r starts (shrunk to half of each side)"""
    u, v = b - a, c - b
    lu, lv = float(np.linalg.norm(u)), float(np.linalg.norm(v))
    if lu < 1e-6 or lv < 1e-6:
        return 0.0
    u, v = u / lu, v / lv
    phi = abs(math.atan2(u[0] * v[1] - u[1] * v[0], float(u @ v)))
    if phi < 1e-3:
        return 0.0
    return min(r * math.tan(phi / 2), 0.5 * lu, 0.5 * lv)


def _unwrap(prev, h):
    return prev + wrap_pi(h - prev)


def _route(P, H):
    P = np.array(P, dtype=float).reshape(-1, 2)
    H = np.array(H, dtype=float)
    S = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]) if len(P) > 1 else np.zeros(1)
    return {'P': P, 'H': H, 'S': S, 'total': float(S[-1])}


def route_at(route, s):
    """(x, y, heading) at arc length s along a route"""
    S, P, H = route['S'], route['P'], route['H']
    if len(S) == 1 or s <= 0:
        return float(P[0][0]), float(P[0][1]), float(H[0])
    if s >= S[-1]:
        return float(P[-1][0]), float(P[-1][1]), float(H[-1])
    k = int(np.searchsorted(S, s, side='right')) - 1
    u = (s - S[k]) / max(1e-12, S[k + 1] - S[k])
    p = P[k] + (P[k + 1] - P[k]) * u
    return float(p[0]), float(p[1]), float(H[k] + (H[k + 1] - H[k]) * u)


# ------------------------------------------------------------------------------------------------------------ the world
MIN_HALF = 0.05          # robot_controller.js: a flat mesh's box gets this half-thickness, its top kept at the mesh's top


class CollisionWorld:
    """the meshes the body walks on and against (robot_controller.js: opts.collisionMeshes), built as the adapter builds
    its Rapier colliders, then one BVH over them in world space:

      - a mesh flagged ob['trimesh_collider'] (the JS's userData.trimeshCollider: terrain, ramps, any shaped ground), or
        every mesh when trimesh_colliders=True: its own triangles (its mesh children's too, as three's traverse)
      - any other mesh: the axis-aligned box round it and its mesh children (three's Box3.setFromObject), a flat one
        (a floor plane) given a MIN_HALF half-thickness downward so its top stays the visible surface. A box turns a
        slope into a block at its highest point, as in the WebGPU edition: flag shaped ground trimesh
      - a mesh flagged ob['no_walkable'] (the JS's userData.noWalkable: vegetation, effects): never a collider
      - nothing at all: a flat ground at ground_z (the JS's 120 m slab at groundY)

    -> .bvh (None for the flat fallback), .names, .kinds {name: 'trimesh' | 'aabb'}"""

    def __init__(self, meshes, ground_z=0.0, trimesh_colliders=False):
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys = [], []
        self.names, self.kinds = [], {}
        for ob in meshes:
            if ob.type != 'MESH' or ob.get('no_walkable'):
                continue
            parts = [ob] + [c for c in ob.children_recursive if c.type == 'MESH' and not c.get('no_walkable')]
            if ob.get('trimesh_collider') or trimesh_colliders:
                for o in parts:
                    ev = o.evaluated_get(dg)
                    me = ev.to_mesh()
                    base = len(verts)
                    mw = ev.matrix_world
                    verts.extend(mw @ v.co for v in me.vertices)
                    polys.extend([base + i for i in p.vertices] for p in me.polygons)
                    ev.to_mesh_clear()
                self.kinds[ob.name] = 'trimesh'
            else:
                P = [o.evaluated_get(dg).matrix_world @ Vector(c) for o in parts for c in o.evaluated_get(dg).bound_box]
                lo = Vector((min(p.x for p in P), min(p.y for p in P), min(p.z for p in P)))
                hi = Vector((max(p.x for p in P), max(p.y for p in P), max(p.z for p in P)))
                s = hi - lo
                if (s.x < 1e-4 and s.z < 1e-4) or (s.y < 1e-4 and s.z < 1e-4) or (s.x < 1e-4 and s.y < 1e-4):
                    continue                                              # a point or a line: no collider
                hz = max(s.z / 2, MIN_HALF)
                hx, hy = max(s.x / 2, MIN_HALF), max(s.y / 2, MIN_HALF)
                cx, cy, cz = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z - hz
                base = len(verts)
                verts.extend(Vector((cx + sx * hx, cy + sy * hy, cz + sz * hz))
                             for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1))
                polys.extend([[base + i for i in f] for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6),
                                                                  (0, 2, 6, 4), (1, 5, 7, 3))])
                self.kinds[ob.name] = 'aabb'
            self.names.append(ob.name)
        self.bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False) if polys else None
        self.ground_z = ground_z
        if self.bvh is None:
            print(f'[robot] no collision meshes: a flat ground at z={ground_z}', flush=True)

    def ground(self, x, y, z_from):
        """the walkable surface under (x, y) from z_from down (the controller's ground probe), or ground_z"""
        if self.bvh is None:
            return self.ground_z
        hit = self.bvh.ray_cast(Vector((x, y, z_from)), Vector((0.0, 0.0, -1.0)), 10.0)
        if hit[0] is None or hit[1].z < 0.5:
            return self.ground_z
        return hit[0].z

    def blocked(self, x0, y0, x1, y1, z, radius, heights=(0.25, 0.7, 1.2, 1.6)):
        """does the body's cylinder (radius) moving from (x0, y0) to (x1, y1), standing at z, meet a wall: rays along the
        step at each height from the cylinder's front and both sides, and a ring round the new place"""
        if self.bvh is None:
            return False
        d = Vector((x1 - x0, y1 - y0, 0.0))
        L = d.length
        dirs = []
        if L > 1e-9:
            d /= L
            side = Vector((-d.y, d.x, 0.0))
            for hz in heights:
                for off in (0.0, 0.7, -0.7):
                    o = Vector((x0, y0, z + hz)) + side * radius * off
                    hit = self.bvh.ray_cast(o, d, L + radius * math.sqrt(1 - off * off))
                    if hit[0] is not None and abs(hit[1].z) < 0.6:
                        return True
        for hz in heights:
            o = Vector((x1, y1, z + hz))
            for k in range(8):
                a = k * math.pi / 4
                dirs = Vector((math.cos(a), math.sin(a), 0.0))
                hit = self.bvh.ray_cast(o, dirs, radius)
                if hit[0] is not None and abs(hit[1].z) < 0.6:
                    return True
        return False

    def as_ground(self):
        """a round-one Ground over the same meshes (the walk's feet read it)"""
        w = self

        def fn(xs, ys):
            xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
            out = np.empty(xs.shape)
            for i, (x, y) in enumerate(zip(xs.ravel(), ys.ravel())):
                out.flat[i] = w.ground(float(x), float(y), 3.0)
            return out
        return Ground(fn=fn)


# ------------------------------------------------------------------------------------------------------------ the legs
# a route starting this far off the facing begins with a turn on the spot (a walk that starts on an arc from standing
# turns its first planted foot on the ground: 5 deg a frame on a 45 deg start)
START_TURN = math.radians(25.0)
# rad/s while walking. The engine controller turns at 3.5 (VRMCharacterController's maxTurnRate) and its foot IK slides
# through the tight arcs that makes (0.26 m at 0.9 m/s); the film's planted feet (walk_path, verified on arcs of
# speed / 1.0) miss their targets by 6 cm on 0.26 m, and at speed / 1.5 a planted foot turns 2 deg a frame on the
# ground in a 90 deg corner. So the legs walk arcs of speed / 1.0, and make the big turns (over START_TURN) on the
# spot: max_turn_rate=3.5 is the engine's exactly
MAX_TURN_RATE = 1.0


class RobotLegs:
    """the charCtrl the adapter drives (VRMCharacterController's contract as robot_controller.js uses it), solved at
    build time and keyed by bake(). Live state: feet_world_position, _heading, running, _blocked_frames, is_maneuvering,
    _seated; the record: one dict per locomote() call (see the module doc).

    Turning: while walking the facing turns at max_turn_rate (MAX_TURN_RATE: 1.0 rad/s, the engine's 3.5 on request), so
    a route's corners are arcs of radius speed / max_turn_rate. A route that starts more than START_TURN (25 deg) off the
    facing, and an emote aimed
    away from it (set_emote_facing), begin with a turn on the spot instead (the record stands at the new heading for the
    turn's frames; the bake steps it round on my feet: bake.turn_plan), as a body turns to face its way before walking
    off; the engine's walk does the same by turning while its speed builds from standing."""

    def __init__(self, h, rig=None, world=None, start_position=(0.0, 0.0, 0.0), start_heading=0.0, walk_speed=1.0,
                 run_speed=3.6, max_turn_rate=MAX_TURN_RATE, agent_radius=0.3, idle='idle', walk='walk', run='run'):
        from .rig import RobotRig
        self.h = h
        self.rig = rig or RobotRig(h)
        self.world = world
        self.pos = Vector((start_position[0], start_position[1], start_position[2] if len(start_position) > 2 else 0.0))
        if world is not None:
            self.pos.z = world.ground(self.pos.x, self.pos.y, self.pos.z + 1.0)
        self._heading = float(start_heading)
        self._flat_speed = float(walk_speed)
        self._run_speed = float(run_speed)
        self.max_turn_rate = float(max_turn_rate)
        self.agent_radius = float(agent_radius)
        self.running = False
        self._blocked_frames = 0
        self._seated = False
        self.slots = {'idle': idle, 'walk': walk, 'run': run}
        self.route = None
        self.route_s = 0.0
        self._emote = None
        self._emote_actions = {}
        self._emote_facing = None            # the engine controller's _emoteFacingY: a standing emote's world heading
        self._pre_turn = None                # a turn on the spot in progress: {'heading', 'left' (frames)}
        self.record = []
        self._gaze = None
        self.t = 0.0
        sc = bpy.context.scene
        self.fps = sc.render.fps / sc.render.fps_base

    # the contract
    @property
    def feet_world_position(self):
        return self.pos.copy()

    @property
    def is_maneuvering(self):
        return False

    @property
    def is_emoting(self):
        return self._emote is not None

    def speed(self):
        return self._run_speed if self.running else self._flat_speed

    def turn_on_spot(self, heading):
        """turn to `heading` (rad) where the body stands: the facing is the new one from now, and the next frames stand
        while the bake steps the body round -> the turn's frames (0: already facing it)"""
        from .bake import turn_plan
        n = turn_plan(self._heading, heading, self.fps)['frames'] if abs(wrap_pi(heading - self._heading)) > 0.02 else 0
        if n:
            self._heading = self._heading + wrap_pi(heading - self._heading)
            self._pre_turn = {'heading': self._heading, 'left': n}
        return n

    def set_route(self, waypoints):
        """the polyline the adapter is following (its remaining waypoints), as a route from here and this facing; a
        route starting more than START_TURN off the facing begins with a turn on the spot (a replan while one is under
        way keeps it, unless the new route starts off that turn's heading too)"""
        if not waypoints:
            self.route = None
            return
        pts = [(w['x'], w['y']) for w in waypoints]
        first = next((p for p in pts if math.hypot(p[0] - self.pos.x, p[1] - self.pos.y) > 0.05), None)
        if first is not None and not self._seated and self._emote is None:
            d = heading_of(first[0] - self.pos.x, first[1] - self.pos.y)
            if abs(wrap_pi(d - self._heading)) > START_TURN:
                self.turn_on_spot(d)
        r = self.speed() / max(1e-3, self.max_turn_rate)
        self.route = build_route((self.pos.x, self.pos.y), self._heading, pts, r)
        self.route_s = 0.0

    def locomote(self, dt, inp):
        """one frame: the input a unit direction on the ground plane ({'x', 'y'}; zero stands). With a route, a non-zero
        input walks the route; without one it steers the facing toward the input at max_turn_rate and walks forward (the
        engine controller's turning model). A step the collision world blocks is not taken (_blocked_frames counts). A
        turn on the spot in progress stands its frames out first"""
        self.t += dt
        x, y = (inp.get('x', 0.0), inp.get('y', 0.0)) if isinstance(inp, dict) else (inp[0], inp[1])
        turning = self._pre_turn is not None and self._pre_turn['left'] > 0
        if turning:
            self._pre_turn['left'] -= 1
            if self._pre_turn['left'] <= 0:
                self._pre_turn = None
        moving = math.hypot(x, y) > 1e-4 and not self._seated and self._emote is None and not turning
        state = 'seated' if self._seated else ('emote' if self._emote is not None else 'idle')
        if state == 'emote' and self.t - dt < self._emote['t0']:
            state = 'idle'                                   # an aimed emote's turn before it plays
        step = 0.0
        if moving:
            v = self.speed()
            if self.route is not None and self.route_s < self.route['total'] - 1e-6:
                s1 = min(self.route['total'], self.route_s + v * dt)
                nx, ny, nh = route_at(self.route, s1)
            else:
                tgt = heading_of(x, y)
                dh = wrap_pi(tgt - self._heading)
                mx = self.max_turn_rate * dt
                nh = self._heading + max(-mx, min(mx, dh))
                f = heading_vector(nh)
                nx, ny = self.pos.x + f.x * v * dt, self.pos.y + f.y * v * dt
                s1 = None
            if self.world is not None and self.world.blocked(self.pos.x, self.pos.y, nx, ny, self.pos.z, self.agent_radius):
                self._blocked_frames += 1
                state = 'idle' if self._blocked_frames >= 6 else ('run' if self.running else 'walk')
                moving = state != 'idle'
            else:
                step = math.hypot(nx - self.pos.x, ny - self.pos.y)
                self.pos.x, self.pos.y, self._heading = nx, ny, nh
                if s1 is not None:
                    self.route_s = s1
                if self.world is not None:
                    self.pos.z = self.world.ground(nx, ny, self.pos.z + 0.6)
                if step > 0.05 * v * dt:
                    self._blocked_frames = 0
                state = 'run' if self.running else 'walk'
        rec = {'t': self.t - dt, 'state': state, 'x': self.pos.x, 'y': self.pos.y, 'z': self.pos.z,
               'heading': self._heading, 'step': step, 'speed': self.speed(), 'clip': None, 'gaze': None,
               'goal': (tuple(self.route['P'][-1]) if self.route is not None else None)}
        if self._emote is not None and self._emote.get('facing') is not None and not self._seated:
            rec['heading'] = self._emote['facing']          # the emote aimed (set_emote_facing); the walk's own after
        if state == 'emote':
            rec['clip'] = self._emote['slot']
            rec['clip_t'] = self.t - dt - self._emote['t0']
            rec['loop'] = self._emote['loop']
        elif state == 'seated':
            rec['clip'] = self._emote['slot'] if self._emote else self._seat_slot
            rec['clip_t'] = self.t - dt - self._seat_t0
            rec['loop'] = False
        self.record.append(rec)
        return rec

    def set_gaze(self, yaw, pitch):
        """the body's head override for the frame just stepped (VRMRobotBody._applyHeadOverride)"""
        if self.record:
            self.record[-1]['gaze'] = (yaw, pitch)

    def load_emote(self, slot, loop=False):
        from ..vrma import load_clip
        if slot not in self._emote_actions:
            self._emote_actions[slot] = load_clip(self.h, slot)
        return self._emote_actions[slot]

    def play_emote(self, slot, loop=False, aim=True):
        """a standing clip from now (aim: at _emote_facing when it is set; the seated clips are not aimed). An aimed
        emote first turns on the spot to its facing and plays after the turn: -> the emote, with 'lead_s' (the turn)"""
        if slot not in self._emote_actions:
            self.load_emote(slot)
        facing = self._emote_facing if aim else None
        lead = 0.0
        if facing is not None:
            from .bake import turn_plan
            facing = self._heading + wrap_pi(facing - self._heading)
            if abs(facing - self._heading) > 0.02:
                lead = turn_plan(self._heading, facing, self.fps)['frames'] / self.fps
            else:
                facing = None
        self._emote = {'slot': slot, 't0': self.t + lead, 'loop': loop, 'facing': facing, 'lead_s': lead}
        return self._emote

    def stop_emote(self):
        """the emote ends; an aimed one turns back on the spot to the body's own heading"""
        em, self._emote = self._emote, None
        if em is not None and em.get('facing') is not None:
            from .bake import turn_plan
            self._pre_turn = {'heading': self._heading, 'left': turn_plan(em['facing'], self._heading, self.fps)['frames']}

    def begin_seated(self, slot='stand_to_sit', opts=None):
        self._seated = True
        self._seat_slot = slot
        self._seat_t0 = self.t
        self.load_emote(slot)
        self._emote = None
        return self._emote_actions[slot].duration

    def end_seated(self, slot='sit_to_stand', opts=None):
        self._seated = False
        if slot:
            self.play_emote(slot, aim=False)
        return None

    def vault(self):
        return False

    def jump(self, opts=None):
        return False

    def climb_ledge(self):
        return False

    def climb_ladder(self, opts=None):
        return False

    # ------------------------------------------------------------------------------------------------------ the bake
    def bake(self, f0=1, ground=None, face=None, crown_state=None, head_state=None, fade=8, action_name=None,
             key=True, log=print):
        """the record keyed through my body's passes (see the module doc) -> report"""
        from . import bake as B
        return B.bake_run(self, f0=f0, ground=ground, face=face, crown_state=crown_state, head_state=head_state, fade=fade,
                          action_name=action_name, key=key, log=log)


# ------------------------------------------------------------------------------------------------------------ the adapter
class EidoverseRobotController:
    """robot_controller.js's EidoverseRobotController: VRMRobotBody's controller contract over the legs"""

    @classmethod
    def create(cls, h, overrides=None, opts=None, rig=None, legs_class=None):
        """create(vrm, mixer, overrides, opts): opts start_position (x, y[, z]), start_heading (rad, 0 faces -Y),
        walk_speed, run_speed, max_turn_rate, arrive_radius, agent_radius, collision_meshes (the walkable world: every
        surface walked on and every solid walked round; none: a flat ground at ground_z, as the JS), trimesh_colliders
        (every collision mesh as its triangles instead of its box: CollisionWorld), ground_z. overrides: {'idle': slot,
        'walk': slot, 'run': slot} (the clips' slots; the JS's standardAnimationOverrides). The JS's VRMUtils merge
        (fewer skinned draws for three's renderer) does not apply in Blender"""
        opts = dict(opts or {})
        overrides = dict(overrides or {})
        mine = {o.name for o in h.objects} | {h.arm.name}
        meshes = [o for o in (opts.get('collision_meshes') or []) if o.name not in mine]
        if not meshes:
            print('[eidoverse-robot] no collision_meshes provided: using a flat ground plane at z='
                  f'{opts.get("ground_z", 0.0)}', flush=True)
        world = CollisionWorld(meshes, opts.get('ground_z', 0.0), opts.get('trimesh_colliders', False))
        Legs = legs_class or RobotLegs
        legs = Legs(h, rig=rig, world=world, start_position=opts.get('start_position', (0.0, 0.0, 0.0)),
                    start_heading=opts.get('start_heading', 0.0), walk_speed=opts.get('walk_speed', 1.5),
                    run_speed=opts.get('run_speed', 3.6), max_turn_rate=opts.get('max_turn_rate') or MAX_TURN_RATE,
                    agent_radius=opts.get('agent_radius', 0.3), idle=overrides.get('idle', 'idle'),
                    walk=overrides.get('walk', 'walk'), run=overrides.get('run', 'run'))
        return cls(h, legs, opts)

    def __init__(self, h, char_ctrl, opts=None):
        opts = opts or {}
        self.vrm = h
        self.char_ctrl = char_ctrl
        self.waypoints = []
        self.waypoint_index = 0
        self.state = 'idle'                  # 'idle' | 'walking' | 'running' | 'performing' | 'seated'
        self.walk_speed = opts.get('walk_speed', 1.5)
        self.run_speed = opts.get('run_speed', 3.6)
        self.arrive_radius = opts.get('arrive_radius', 0.28)
        self.actions = {}                    # VRMRobotBody reads this; emotes go through force_action
        self.current_action = None
        self.on_pre_vrm_update = None        # VRMRobotBody sets this for its head look
        self._emote_until = 0.0
        self._t = 0.0
        self._emotes_loaded = {}

    # the VRMRobotBody contract's accessors
    @property
    def heading(self):
        return self.char_ctrl._heading

    @heading.setter
    def heading(self, h):
        self.char_ctrl._heading = h

    def get_heading(self):
        return self.char_ctrl._heading

    def get_position(self):
        f = self.char_ctrl.feet_world_position
        return {'x': f.x, 'y': f.y, 'z': f.z}

    def get_state(self):
        return self.state

    def get_current_action(self):
        return self.current_action

    def is_busy(self):
        return self.state != 'idle' or self.waypoint_index < len(self.waypoints)

    def set_walk_speed(self, v):
        self.walk_speed = v
        self.char_ctrl._flat_speed = v

    def set_run_speed(self, v):
        self.run_speed = v
        self.char_ctrl._run_speed = v

    def set_running(self, v):
        self.char_ctrl.running = bool(v)

    @property
    def is_maneuvering(self):
        return bool(getattr(self.char_ctrl, 'is_maneuvering', False))

    # parkour passthroughs (the legs have no maneuvers yet: False, as the JS answers for a controller without them)
    def vault(self):
        return getattr(self.char_ctrl, 'vault', lambda: False)()

    def jump(self, opts=None):
        return getattr(self.char_ctrl, 'jump', lambda o=None: False)(opts)

    def climb_ledge(self):
        return getattr(self.char_ctrl, 'climb_ledge', lambda: False)()

    def climb_ladder(self, opts=None):
        return getattr(self.char_ctrl, 'climb_ladder', lambda o=None: False)(opts)

    def set_waypoints(self, waypoints):
        """keeps each waypoint's `action` ('run' runs to it); clears the stall latch so a fresh path resumes"""
        self.waypoints = [({'x': w[0], 'y': w[1]} if isinstance(w, (list, tuple)) else
                           {'x': w['x'], 'y': w['y'], 'action': w.get('action')}) for w in (waypoints or [])]
        self.waypoint_index = 0
        self.char_ctrl._blocked_frames = 0
        if self.state != 'performing':
            self.state = 'walking' if self.waypoints else 'idle'
        if self.waypoints and any(w.get('action') == 'run' for w in self.waypoints):
            self.char_ctrl.running = self.waypoints[0].get('action') == 'run'
        if hasattr(self.char_ctrl, 'set_route'):
            self.char_ctrl.set_route(self.waypoints)

    def force_action(self, name, duration=None):
        """a stationary expressive clip through the legs' emote system: 'performing' at once (a caller polling the
        state right after must not see the old one), the clip loaded and played for `duration` (1.5 s by default);
        False (and the state restored) when it cannot be loaded"""
        prev = self.state
        self.current_action = name
        self.state = 'performing'
        self._emote_until = math.inf
        try:
            if not self._emotes_loaded.get(name):
                self.char_ctrl.load_emote(name)
                self._emotes_loaded[name] = True
            if self.current_action != name or self.state != 'performing':
                return False
            em = self.char_ctrl.play_emote(name)
            # the JS plays `duration` from the call (the engine pivots to an aimed facing during the fade-in); the legs
            # here turn on the spot first, so the emote's own time starts after that turn
            lead = em.get('lead_s', 0.0) if isinstance(em, dict) else 0.0
            self._emote_until = self._t + (1.5 if duration is None else duration) + lead
            return True
        except Exception as e:  # noqa: BLE001 (the JS: an unknown emote degrades to a no-op)
            print(f'[eidoverse-robot] force_action({name}) failed: {e}', flush=True)
            if self.current_action == name and self.state == 'performing':
                self.current_action = None
                self.state = (('walking' if self.waypoint_index < len(self.waypoints) else 'idle')
                              if prev == 'performing' else prev)
            return False

    def is_stalled(self):
        return (not self.is_maneuvering and self.char_ctrl._blocked_frames >= 6
                and self.waypoint_index < len(self.waypoints) and self.state not in ('performing', 'seated'))

    def begin_seated(self, slot='stand_to_sit', opts=None):
        try:
            self.state = 'seated'
            self.current_action = slot
            return self.char_ctrl.begin_seated(slot, opts or {})
        except Exception as e:  # noqa: BLE001
            print(f'[eidoverse-robot] begin_seated({slot}) failed: {e}', flush=True)
            return None

    def end_seated(self, slot='sit_to_stand', opts=None):
        opts = opts or {}
        try:
            if slot:
                self.current_action = slot
                self.state = 'performing'
                self._emote_until = self._t + opts.get('duration', 1.8)
            else:
                self.state = 'walking' if self.waypoint_index < len(self.waypoints) else 'idle'
            return self.char_ctrl.end_seated(slot, opts)
        except Exception as e:  # noqa: BLE001
            print(f'[eidoverse-robot] end_seated failed: {e}', flush=True)

    def update(self, t, dt):
        self._t = t
        if self.state in ('performing', 'seated'):
            if self.state == 'performing' and t >= self._emote_until:
                self.current_action = None
                self.state = 'walking' if self.waypoint_index < len(self.waypoints) else 'idle'
                if hasattr(self.char_ctrl, 'stop_emote'):
                    self.char_ctrl.stop_emote()
            self.char_ctrl.locomote(dt, {'x': 0.0, 'y': 0.0})
            if self.on_pre_vrm_update:
                self.on_pre_vrm_update(dt)
            return
        dx_, dy_ = 0.0, 0.0
        if self.waypoint_index < len(self.waypoints):
            pos = self.char_ctrl.feet_world_position
            wp = self.waypoints[self.waypoint_index]
            dx, dy = wp['x'] - pos.x, wp['y'] - pos.y
            dist = math.hypot(dx, dy)
            running = wp.get('action') == 'run'
            self.char_ctrl.running = running
            if dist <= self.arrive_radius:
                self.waypoint_index += 1
                if self.waypoint_index >= len(self.waypoints):
                    self.state = 'idle'
            else:
                dx_, dy_ = dx / dist, dy / dist
                self.state = 'running' if running else 'walking'
        else:
            self.state = 'idle'
            self.char_ctrl.running = False
        if not self.is_maneuvering and self.char_ctrl._blocked_frames >= 6:
            dx_, dy_ = 0.0, 0.0
            self.state = 'idle'
        self.char_ctrl.locomote(dt, {'x': dx_, 'y': dy_})
        if self.on_pre_vrm_update:
            self.on_pre_vrm_update(dt)

    def bake(self, **kw):
        """the run keyed (RobotLegs.bake)"""
        return self.char_ctrl.bake(**kw)
