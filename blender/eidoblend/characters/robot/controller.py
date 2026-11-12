"""eidoblend.characters.robot.controller: EidoverseRobotController (eidoverse/robot_controller.js) and the legs it drives.

    from eidoblend.characters.robot import EidoverseRobotController
    ctl = EidoverseRobotController.create(me, rig=rig, opts={'start_position': (0, 0, 0), 'start_heading': 0.0,
                                                             'walk_speed': 1.0, 'collision_meshes': [floor, walls]})
    ctl.set_waypoints([(2.0, -1.0), (4.0, 0.5)])
    for f in range(1, 241):
        ctl.update((f - 1) / fps, 1 / fps)       # VRMRobotBody calls this; a scene that walks waypoints alone may too
    rep = ctl.bake(f0=1)                          # the run keyed: one action, every frame renders alone

robot_controller.js adapts the engine's physics character controller (character_controller.js's VRMCharacterController:
the gait tree, the ground and stair probes, the foot IK, the moves) to the waypoint contract VRMRobotBody was written
against: each frame the current waypoint becomes a unit direction for charCtrl.locomote, arrival within arrive_radius
moves to the next one, a collision stall (six frames of move-and-slide cancelling the step) latches the input to zero,
emotes and seated clips suspend the walk. That logic is ported line for line (update, set_waypoints, force_action,
is_stalled, begin_seated, end_seated, the accessors).

THE LEGS (RobotLegs, the charCtrl) are the controller family's VRMCharacterController (eidoblend.characters.controller),
set up as its Locomotion sets one up for a film (the robot preset, the stock clips, the gait tree at this body's measured
paces, distance matching), on the colliders the JS gives Rapier (CollisionWorld), and stepped frame by frame while the
body senses and decides. Each frame they run the command in hand, the controller family's own: a route (film.FollowPath:
from standing a turn on the spot first where the way is more than 25 deg off my heading, then it accelerates, follows the
route with its corners rounded at the controller's max_turn_rate, 3.5 rad/s, and slows down to stop on the goal), an
emote (emotes.EmoteCmd), a turn on the spot (film.TurnTo), a seat (emotes.SeatOn and StandUp); and they record the frame
(film.record). Whatever the engine's controller does on its own while it walks or runs happens here on its own: stairs
and ramps, low cover vaulted, a ledge climbed, a gap jumped, a big drop landed (fallLand). A move called while walking or
running starts out of the stride; upper-body gestures play over the gait. bake() bakes the take as the controller family
bakes its own (emotes.bake: the plant, the seats' feet) and runs my body's passes over it (eidoblend.characters.robot.bake).
legs_class: any object with this contract may stand in. The JS's VRMUtils merge (fewer skinned draws in three) does not
apply in Blender, and Rapier's world is a BVH over the same colliders.
"""

import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import robot_dof as dof
from .._math import q_from_three, q_to_three, wrap_pi
from ..controller.film import DECEL, Call, FollowPath, Locomotion, TurnTo, Wait, record
from ..controller.pose import Pose
from ..controller.world import CollisionWorld as _ControllerWorld

FWD = Vector((0.0, -1.0, 0.0))            # a VRM faces -Y: heading 0 (the same number as three's rotation.y)


def heading_vector(h):
    """the facing for a heading (rad about +Z, 0 = -Y, counter-clockwise): three's (sin h, 0, cos h) in Blender's axes"""
    return Vector((math.sin(h), -math.cos(h)))


def heading_of(dx, dy):
    """the heading that faces (dx, dy)"""
    return math.atan2(dx, -dy)


# ------------------------------------------------------------------------------------------------------------ the world
MIN_HALF = 0.05          # robot_controller.js: a flat mesh's box gets this half-thickness, its top kept at the mesh's top
SLAB = 60.0              # robot_controller.js: no collider at all -> a flat ground slab, 120 m square, at ground_z


class CollisionWorld(_ControllerWorld):
    """the colliders robot_controller.js gives Rapier from opts.collisionMeshes, as the controller family's walkable world
    (its probes, its move-and-slide, the maneuvers' scans and the plant all read it):

      - a mesh flagged ob['trimesh_collider'] (the JS's userData.trimeshCollider: terrain, ramps, stairs, any shaped
        ground), or every mesh when trimesh_colliders=True: its own triangles (its mesh children's too, as three's
        traverse)
      - any other mesh: the axis-aligned box round it and its mesh children (three's Box3.setFromObject), a flat one
        (a floor plane) given a MIN_HALF half-thickness downward so its top stays the visible surface. A box turns a
        slope or a flight of stairs into a block at its highest point, as in the WebGPU edition: flag shaped ground
      - a mesh flagged ob['no_walkable'] (the JS's userData.noWalkable: vegetation, effects, a ladder's rungs): never a
        collider
      - nothing at all: a flat slab at ground_z (the JS's 120 m slab at groundY)

    -> the controller family's CollisionWorld (ray_cast, ground_vector, move_and_slide, h, ...) over those colliders,
    with .names (the meshes made colliders) and .kinds {name: 'trimesh' | 'aabb'}"""

    def __init__(self, meshes, ground_z=0.0, trimesh_colliders=False):
        self.ground_z = float(ground_z)
        self.trimesh_colliders = bool(trimesh_colliders)
        self.names, self.kinds = [], {}
        super().__init__(objects=list(meshes or []))

    def refresh(self):
        """the colliders built again from the meshes' evaluated geometry (call after the scene changes)"""
        dg = bpy.context.evaluated_depsgraph_get()
        verts, polys, owner = [], [], []
        self.names, self.kinds, self.objects = [], {}, []
        for ob in self._explicit or []:
            if ob is None or ob.type != 'MESH' or ob.get('no_walkable'):
                continue
            parts = [ob] + [c for c in ob.children_recursive if c.type == 'MESH' and not c.get('no_walkable')]
            if ob.get('trimesh_collider') or self.trimesh_colliders:
                for o in parts:
                    ev = o.evaluated_get(dg)
                    me = ev.to_mesh()
                    base = len(verts)
                    mw = ev.matrix_world
                    verts.extend(mw @ v.co for v in me.vertices)
                    for p in me.polygons:
                        polys.append(tuple(base + i for i in p.vertices))
                        owner.append(o)
                    ev.to_mesh_clear()
                self.kinds[ob.name] = 'trimesh'
            else:
                P = [o.evaluated_get(dg).matrix_world @ Vector(c) for o in parts for c in o.evaluated_get(dg).bound_box]
                lo = Vector((min(p.x for p in P), min(p.y for p in P), min(p.z for p in P)))
                hi = Vector((max(p.x for p in P), max(p.y for p in P), max(p.z for p in P)))
                s = hi - lo
                if (s.x < 1e-4 and s.z < 1e-4) or (s.y < 1e-4 and s.z < 1e-4) or (s.x < 1e-4 and s.y < 1e-4):
                    continue                                              # a point or a line: no collider
                self._box(verts, polys, owner, ob, (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z,
                          max(s.x / 2, MIN_HALF), max(s.y / 2, MIN_HALF), max(s.z / 2, MIN_HALF))
                self.kinds[ob.name] = 'aabb'
            self.names.append(ob.name)
            self.objects.append(ob)
        if not polys:
            print(f'[eidoverse-robot] no collision meshes: a flat ground slab at z={self.ground_z}', flush=True)
            self._box(verts, polys, owner, None, 0.0, 0.0, self.ground_z, SLAB, SLAB, MIN_HALF)
        self.tree = BVHTree.FromPolygons(verts, polys)
        self._poly_obj = owner
        self.top = max(v.z for v in verts)
        self.casts = 0
        return self

    @staticmethod
    def _box(verts, polys, owner, ob, cx, cy, top, hx, hy, hz):
        """a box (half sizes hx, hy, hz) whose top face is at `top` over (cx, cy)"""
        cz = top - hz
        base = len(verts)
        verts.extend(Vector((cx + sx * hx, cy + sy * hy, cz + sz * hz)) for sx in (-1, 1) for sy in (-1, 1)
                     for sz in (-1, 1))
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            polys.append(tuple(base + i for i in f))
            owner.append(ob)


# ------------------------------------------------------------------------------------------------------------ the legs
class _Take(Locomotion):
    """the legs' Locomotion: set up as the controller family sets one up for a film, and its take is the frames the legs
    recorded live, so its bake (and emotes.bake, which bakes the seats with it) bakes what the body did"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.live = []

    def simulate(self, f0=1, max_seconds=600.0, fps=None):
        for i, r in enumerate(self.live):
            r['f'] = f0 + i
        self.records = list(self.live)
        return self.records


class RobotLegs:
    """the charCtrl the adapter drives: the controller family's VRMCharacterController (self.ctrl, of self.loco: the
    Locomotion that set it up), stepped frame by frame (locomote), every frame recorded (self.record: film.record's
    fields plus the gaze VRMRobotBody set and the command in hand). See the module doc.

    Turning: a route's corners are the controller's (max_turn_rate, 3.5 rad/s, the engine's), its start from standing
    more than 25 deg off my heading a turn on the spot on the turn clips (film.FollowPath's rule for my robot body: the
    hip's yaw ring turns a planted leg only so far about its own axis; 60 deg on any other VRM). An emote aimed by
    set_emote_facing pivots during its fade-in, as the engine's does, where the pivot is under PIVOT_MAX; past it the
    planted feet cannot follow a root that pivots so far (the plant keeps them where they stand), so the body turns on
    the spot to the aim first, plays the emote, and turns back to its own heading after it."""

    def __init__(self, h, rig=None, world=None, start_position=(0.0, 0.0, 0.0), start_heading=0.0, walk_speed=None,
                 run_speed=None, max_turn_rate=None, controller_opts=None, vrma_library=None):
        from .rig import RobotRig
        self.h = h
        self.rig = rig or RobotRig(h)
        self.world = world if world is not None else CollisionWorld([])
        self.said = []                       # what the controller logged: (its time, the line)
        co = {}
        if max_turn_rate is not None:
            co['max_turn_rate'] = float(max_turn_rate)
        co.update(controller_opts or {})
        p = tuple(start_position) + (0.0,) * (3 - len(tuple(start_position)))
        self.loco = _Take(h, self.world, start=p, heading=float(start_heading), controller_opts=co, log=self._said)
        self.ctrl = c = self.loco.ctrl
        if vrma_library:
            # the JS's standardAnimationOverrides: these slots played from other files; the gait tree measured again
            c.load_standard_animations(vrma_library=dict(vrma_library))
            c.attach_locomotion(leg_ik='default', flat_speed=None, run_speed=None, native_walk_speed=None,
                                native_run_speed=None, gait_sync='distance')
            self.loco.native = {'walk': c._native_walk_speed, 'run': c._native_run_speed}
            self.loco.run_threshold = 0.5 * (self.loco.native['walk'] + self.loco.native['run'])
        self.walk_speed = float(walk_speed) if walk_speed is not None else self.loco.native['walk']
        self.run_speed = float(run_speed) if run_speed is not None else self.loco.native['run']
        self._run = False
        self._cmd = None                     # the command in hand: {'kind', 'cmd', ...}
        self._next_route = None              # a route handed over while a turn clip plays: taken when it ends
        self._emote_facing = None            # the engine controller's _emoteFacingY: a standing emote's world heading
        self._seat = None                    # the seat in hand: 'seat' (emotes.SeatOn) | 'plain' (beginSeated alone)
        self.maneuver_log = []               # the moves the controller did not start: (time, name, what it said)
        self._auto_held = None               # the legs' auto_maneuvers setting while a route holds it (_moves_en_route)
        self.record = self.loco.live
        self._gaze = None
        self.pos = self.ctrl.feet_world_position
        self._placed = (self.pos.copy(), c._heading)
        sc = bpy.context.scene
        self.fps = sc.render.fps / sc.render.fps_base

    def _said(self, *a):
        self.said.append((round(getattr(getattr(self, 'ctrl', None), 'time', 0.0), 4), ' '.join(str(x) for x in a)))

    # ------------------------------------------------------------------------------------------------- the contract
    @property
    def feet_world_position(self):
        self._sync_place()
        return self.ctrl.feet_world_position

    @property
    def _heading(self):
        return self.ctrl._heading

    @_heading.setter
    def _heading(self, h):
        self._sync_place()
        self.place(heading=h)

    @property
    def _blocked_frames(self):
        return self.ctrl._blocked_frames

    @_blocked_frames.setter
    def _blocked_frames(self, v):
        self.ctrl._blocked_frames = v

    @property
    def _flat_speed(self):
        return self.walk_speed

    @_flat_speed.setter
    def _flat_speed(self, v):
        self.walk_speed = float(v)

    @property
    def _run_speed(self):
        return self.run_speed

    @_run_speed.setter
    def _run_speed(self, v):
        self.run_speed = float(v)

    @property
    def running(self):
        return self._run

    @running.setter
    def running(self, v):
        """the gait of the routes from now; a route in hand changes gait from where the body is"""
        v = bool(v)
        if v != self._run:
            self._run = v
            k = self._cmd
            if k is not None and k['kind'] == 'route' and not k.get('stopping'):
                self._start_route(k['points'])

    @property
    def is_maneuvering(self):
        return self.ctrl.is_maneuvering

    @property
    def is_turning(self):
        """a turn on the spot in hand (face_direction, a route's start, an aimed emote's turn in or out)"""
        k = self._cmd
        if self.ctrl.is_turning or (k is not None and k['kind'] == 'turn'):
            return True
        return k is not None and (isinstance(k['cmd'], TurnTo) or getattr(k['cmd'], 'sub', None) is not None)

    @property
    def is_emoting(self):
        return self.ctrl.is_emoting

    @property
    def travelling(self):
        """a route in hand (it ends stopped on its goal), or one waiting for a turn clip to end"""
        return self._next_route is not None or (self._cmd is not None and self._cmd['kind'] == 'route')

    @property
    def performing(self):
        """an emote, or a stand-up, still in its playing time (the adapter's 'performing'): its turn in, its seconds"""
        k = self._cmd
        if k is None or k['kind'] not in ('emote', 'stand'):
            return False
        if k['kind'] == 'stand':
            return True
        return k['phase'] in ('in', 'play')

    @property
    def _seated(self):
        return self._seat is not None

    def head_world(self):
        """my head bone's world place in the frame last stepped, where VRMRobotBody senses from (the JS's
        headBone.getWorldPosition: the head the body renders): the controller's pose (its gait's bob, its height on a
        stair, a move's place) with my torso as my hardware holds it (robot_dof.rehome_body: my single waist joint does
        not take a clip's chest bend, which carried the clip's head up to half a metre off mine in a vault)"""
        if 'head' not in self.h.humanoid:
            return None
        p = self.ctrl.pose
        if not self.rig.hardware:
            return p.world_pos('head').copy()
        p3 = {n: q_to_three(q) for n, q in p.N.items()}
        dof.rehome_body(p3)
        return Pose(p.body, p.M, {n: q_from_three(q) for n, q in p3.items()}, p.off).world_pos('head').copy()

    def place(self, x=None, y=None, heading=None):
        """the body moved where it stands (seatOn's snap: the engine sets the VRM's position and the capsule's,
        rb.setTranslation): the controller's place (its feet, capsule and root, standing still there); a heading alone
        is robot_controller.js's heading setter (charCtrl._heading), the root turned with it"""
        c = self.ctrl
        if x is not None or y is not None:
            p = c.feet_world_position
            c.place((p.x if x is None else float(x), p.y if y is None else float(y), p.z), heading)
        elif heading is not None:
            c._heading = float(heading)
            c._place_root(c._heading)
        self.pos = c.feet_world_position
        self._placed = (self.pos.copy(), c._heading)

    def _sync_place(self):
        """an outside move of `pos` (seatOn's snap writes legs.pos.x / .y) carried to the controller"""
        p0, _h0 = self._placed
        if (self.pos.xy - p0.xy).length > 1e-6:
            self.place(self.pos.x, self.pos.y)

    # ------------------------------------------------------------------------------------------------- the frame
    def locomote(self, dt, inp):
        """one frame: the input a unit direction on the ground plane ({'x', 'y'} or (x, y); zero stands). The command in
        hand steps and gives the controller its input (a route walks while the input is not zero: the adapter's zero
        is an arrival or a collision stall, and stops it); with no command a non-zero input steers the facing toward it
        at max_turn_rate and walks forward (the engine controller's own turning). Then the controller runs one frame
        (VRMCharacterController.locomote) and the frame is recorded -> the record"""
        self._sync_place()
        c = self.ctrl
        x, y = (inp.get('x', 0.0), inp.get('y', 0.0)) if isinstance(inp, dict) else (inp[0], inp[1])
        go = math.hypot(x, y) > 1e-6
        if not go and not c.is_maneuvering and self.travelling:
            self._next_route = None                        # stopped by the adapter: a collision stall, a stop
            if self._cmd is not None and self._cmd['kind'] == 'route':
                self._drop()
        if self._next_route is not None and not c.is_turning:
            pts, self._next_route = self._next_route, None
            self._start_route(pts)
        k = self._cmd
        if k is None or k['kind'] != 'route':
            self._auto_back()                              # before another command starts (a seat turns them off)
        step = (0.0, 0.0)
        if k is not None:
            step = self._step(k, dt)
        elif go and self._seat is None:
            step = (x, y)
        self._moves_en_route(self._cmd, step)
        t = c.time
        c.locomote(dt, step)
        rec = record(c, len(self.record) + 1, t)
        rec['cmd'] = k['kind'] if k is not None else None
        rec['gaze'] = None
        self.record.append(rec)
        self.pos = c.feet_world_position
        self._placed = (self.pos.copy(), c._heading)
        return rec

    def _moves_en_route(self, k, step):
        """the moves the controller starts on its own (auto_maneuvers) are for what lies ON the route: cover, a ledge, a
        gap between me and the goal. The JS's adapter stops pushing the controller within arrive_radius of the last
        waypoint, so a wall just past the goal never draws a move there; my legs slow down to stop on the goal under
        their own input, so while a route is in hand the controller's own scan of the path ahead (the one it triggers
        from) is read here once the goal is within its reach, and the moves are held while the nearest thing they would
        start for lies past the goal. The setting the legs were given comes back when the route ends (_auto_back)"""
        c = self.ctrl
        cmd = k['cmd'] if (k is not None and k['kind'] == 'route') else None
        if not isinstance(cmd, FollowPath) or not hasattr(cmd, 'total'):
            if cmd is None:
                self._auto_back()
            return
        if self._auto_held is None:
            self._auto_held = c.auto_maneuvers
        on = self._auto_held
        remain = max(0.0, cmd.total - cmd.s)
        if on and remain < c.maneuver_scan_range and getattr(cmd, 'sub', None) is None:
            if c._turning_enabled:
                fx, fy = math.sin(c._heading), -math.cos(c._heading)
            else:
                ln = math.hypot(step[0], step[1])
                fx, fy = (step[0] / ln, step[1] / ln) if ln > 1e-6 else (math.sin(c._heading), -math.cos(c._heading))
            cl = c._classify_path_ahead(c._scan_path_ahead(fx, fy))
            near = [d for d in ((cl['obstacle'] or {}).get('face_d', (cl['obstacle'] or {}).get('start_d')),
                                (cl['gap'] or {}).get('start_d')) if d is not None]
            on = not near or min(near) < remain
        c.auto_maneuvers = on

    def _auto_back(self):
        """the legs' own auto_maneuvers setting, held while a route was in hand, given back"""
        if self._auto_held is not None:
            self.ctrl.auto_maneuvers, self._auto_held = self._auto_held, None

    def _hand(self, kind, *cmds, **extra):
        """a command in hand: the first of `cmds` runs, the rest follow it in order"""
        self._cmd = dict(extra, kind=kind, cmd=cmds[0], parts=list(cmds[1:]))
        return self._cmd

    def _step(self, k, dt):
        """the command in hand stepped -> its input for the controller this frame. A part that ends hands over to the
        next in the same frame (as Locomotion.simulate runs its queue); the last one ending drops the command (a seat
        stays: seated until the stand-up)"""
        while True:
            cmd = k['cmd']
            if not cmd.started:
                cmd.start(self.loco)
                cmd.started = True
            inp = cmd.step(self.loco, dt)
            if k['kind'] == 'emote':
                k['phase'] = self._emote_phase(k)
            if inp is not None:
                return inp
            if not k['parts']:
                break
            k['cmd'] = k['parts'].pop(0)
        if k['kind'] == 'emote':
            k['phase'] = 'done'
        self._cmd = None
        return (0.0, 0.0)

    def _drop(self):
        """the command in hand given up (another one takes the body): an emote stopped (its clip faded out)"""
        k, self._cmd = self._cmd, None
        if k is None:
            return
        if k['kind'] == 'emote' and self.ctrl.is_emoting:
            self.ctrl.stop_emote(fade_out=0.3)

    def set_gaze(self, yaw, pitch, look=None):
        """the body's head override for the frame just stepped (VRMRobotBody._applyHeadOverride); look: (the look-at
        target, the head's place and the heading its aim was taken from, the yaw and pitch limits) while one is held,
        for the bake to re-aim the head from the keyed body (bake._aimed_gaze)"""
        if self.record:
            self.record[-1]['gaze'] = (yaw, pitch)
            if look is not None:
                self.record[-1]['look'] = look

    # ------------------------------------------------------------------------------------------------- routes
    def set_route(self, waypoints):
        """the polyline the adapter is following (its remaining waypoints), walked or run from where the body is
        (film.FollowPath at walk_speed or run_speed, stopping on the last point); none stops the body: a walk or a run
        in hand slows down to a stop straight ahead (film.FollowPath's own deceleration, as a body stops when told to)"""
        if not waypoints:
            self._next_route = None
            k, c = self._cmd, self.ctrl
            if k is not None and k['kind'] == 'route':
                v = c.speed_actual
                if v > 0.3 and not c.is_maneuvering and not k.get('stopping'):
                    gait = 'run' if c.running else 'walk'
                    d = v * v / (2.0 * DECEL[gait]) + 0.05
                    f, p = heading_vector(c._heading), c.feet_world_position
                    pt = (p.x + f.x * d, p.y + f.y * d)
                    self._hand('route', FollowPath([pt], speed=v, gait=gait, turn_first=False), points=[pt],
                               stopping=True)
                elif not k.get('stopping'):
                    self._drop()
            return
        pts = [(float(w['x']), float(w['y'])) for w in waypoints]
        if self._seat is not None:
            return
        if self.ctrl.is_turning:
            self._next_route = pts                         # a turn clip plays: the new route from where it ends
            return
        self._start_route(pts)

    def _start_route(self, pts):
        if self._cmd is not None and self._cmd['kind'] != 'route':
            self._drop()
        gait, v = ('run', self.run_speed) if self._run else ('walk', self.walk_speed)
        self._hand('route', FollowPath(pts, speed=v, gait=gait), points=list(pts))

    def turn_to(self, heading):
        """a turn on the spot to `heading` (rad; film.TurnTo: the turn clips, split into equal turns past one clip's
        turn; under 20 deg the facing eases round) -> started? An emote going out finishes first (the turn takes the
        place of its turn back from an aim), and a walk slowing to a stop; not while seated or while an emote plays"""
        k = self._cmd
        if self._seat is not None or self.performing or (k is not None and k['kind'] in ('stand', 'seat')):
            return False
        self._next_route = None
        if k is not None and (k['kind'] == 'emote' or k.get('stopping')):
            k['parts'] = [TurnTo(heading=float(heading))]
            k['kind'] = 'turn'
            return True
        self._drop()
        self._hand('turn', TurnTo(heading=float(heading)))
        return True

    # ------------------------------------------------------------------------------------------------- emotes
    def load_emote(self, slot, loop=False):
        acts = getattr(self.ctrl, '_emote_actions', {})
        if slot not in acts:
            self.ctrl.load_emote(slot, loop=loop)
        a = getattr(self.ctrl, '_emote_actions', {}).get(slot)
        if a is None:
            raise FileNotFoundError(f'no {slot!r} clip in the library')
        return a

    def play_emote(self, slot, seconds=None, aim=True):
        """a standing clip from now for `seconds` (emotes.EmoteCmd: in at the walk's own fade, out through the standing
        pose), aimed at _emote_facing (set_emote_facing) when it is set: within PIVOT_MAX of my heading the emote's root
        pivots there during its fade-in (the engine's), else a turn on the spot to it first and back to my heading after
        -> the command"""
        from ..emotes.verbs import EmoteCmd
        if self._seat is not None or (self._cmd is not None and self._cmd['kind'] in ('stand', 'seat')):
            raise RuntimeError('seated: an emote plays standing (stand_up first)')
        self.load_emote(slot)
        self._drop()
        self._next_route = None
        h0 = self.ctrl._heading
        d = wrap_pi(self._emote_facing - h0) if (aim and self._emote_facing is not None) else 0.0
        if abs(d) <= PIVOT_MAX:
            em = EmoteCmd(slot, seconds, facing=math.degrees(h0 + d) if d else 'keep')
            return self._hand('emote', em, slot=slot, emote=em, phase='in')
        em = EmoteCmd(slot, seconds, facing='keep')
        return self._hand('emote', TurnTo(heading=h0 + d), em, TurnTo(heading=h0), slot=slot, emote=em, phase='in')

    @staticmethod
    def _emote_phase(k):
        em = k['emote']
        if not em.started:
            return 'in'                                    # turning to the aim first
        return 'play' if getattr(em, 'phase', 'in') in ('in', 'play') else 'out'

    def stop_emote(self):
        """the emote ends now (it goes out through the standing pose, then turns back from an aim)"""
        k = self._cmd
        if k is not None and k['kind'] == 'emote' and k['emote'].started and k['emote'].phase in ('in', 'play'):
            k['emote'].left = 0.0
            k['cmd'] = k['emote']

    # ------------------------------------------------------------------------------------------------- seats
    def begin_seated(self, slot='stand_to_sit', opts=None):
        """beginSeated: the seated state. With a seat (opts['seat']: emotes.seat_plan's measures, which seat_on keeps on
        the body, or opts['chair']: a chair to walk to) the controller family's sit-down (emotes.SeatOn: from where the
        body stands, or walked up to the chair, turned out of it and backed onto its spot; the hips settled on the pan,
        the feet on the floor) and seated until stand_up. Without one the JS's: the seated clip plays where the body
        stands and the root holds (the caller owns the seat) -> the clip's duration"""
        from ..emotes.verbs import SeatOn
        o = dict(opts or {})
        self._sync_place()                                 # seatOn's snap onto its spot, made just before
        self._drop()
        self._next_route = None
        plan, chair = o.get('seat'), o.get('chair')
        a = self.load_emote(slot)
        fade = o.get('fadeIn', o.get('fade', 0.25))
        if plan is not None or chair is not None:
            ch = chair if chair is not None else plan['chair']
            face = plan['heading'] if plan is not None else o.get('face')
            self._hand('seat', SeatOn(ch, transition=slot, face=face, hold=None, fade=fade, sink=o.get('sink', 0.0),
                                      back_up=0.0 if plan is not None else o.get('back_up', 0.35),
                                      hip_back=o.get('hip_back'), camera=o.get('camera'), speed=self.walk_speed))
            self._seat = 'seat'
            return a.clip.duration
        self._seat = 'plain'
        return self.ctrl.begin_seated(slot, fade_in=fade)

    def end_seated(self, slot='sit_to_stand', opts=None):
        """endSeated: a seat taken through emotes.SeatOn stands up through its StandUp (slot: the stand-up clip; None
        reverses the sit-down); a plain seat plays the stand-up clip where it sits (the controller hands the root back
        once the clip has carried the hips over the feet), then stopEmote -> the stand-up's length (s), or None"""
        from ..emotes.verbs import StandUp
        o = dict(opts or {})
        fade = o.get('fadeIn', o.get('fade', 0.25))
        if self._seat is None:
            return None
        if self._seat == 'seat':
            self._seat = None
            up = StandUp(reverse=None if slot is None else False, clip=slot or 'sit_to_stand', fade=fade)
            k = self._cmd
            if k is not None and k['kind'] == 'seat':
                k['parts'].append(up)                      # still sitting down: up once it is seated
                k['kind'] = 'stand'
            else:
                self._hand('stand', up)
            return None
        self._seat = None
        rem = self.ctrl.end_seated(slot, fade_in=fade, reverse=slot is None) or 1.8
        self._hand('stand', Wait(rem), Call(lambda c: c.stop_emote(fade_out=0.3)), Wait(0.4))
        return rem

    # ------------------------------------------------------------------------------------------------- gestures
    def load_gesture(self, slot, loop=True):
        return self.ctrl.load_gesture(slot, loop=loop)

    def play_gesture(self, slot, weight=2.5, loop=True):
        """playGesture: `slot` masked to the upper body, blended over whatever the legs do (walk, run, stairs, standing)
        until stop_gesture; the controller fades it out through turns on the spot, moves and emotes"""
        if slot not in getattr(self.ctrl, '_gesture_actions', {}):
            if self.ctrl.load_gesture(slot, loop=loop) is None:
                return None
        return self.ctrl.play_gesture(slot, weight=weight)

    def stop_gesture(self):
        self.ctrl.stop_gesture()

    # ------------------------------------------------------------------------------------------------- the moves
    # robot_controller.js passes vault / jump / climbLedge / climbLadder through to the engine's charCtrl: here the
    # controller family's, from wherever the body is: standing, walking or running (a move out of the stride), facing
    # its heading, its scan of the colliders ahead deciding whether the move fits (False when it does not)
    def vault(self):
        """vault the cover ahead along the heading (a wall 0.42 to 1.15 m high, with ground to land on beyond)"""
        return self._move('vault')

    def jump(self, opts=None):
        """jump({distance, height}): a leap forward along the heading (1.4 m and 0.45 m by default), the landing probed"""
        o = dict(opts or {})
        return self._move('jump', distance=o.get('distance', 1.4), height=o.get('height', 0.45))

    def climb_ledge(self):
        """mount the block ahead (climbLedge; climbWallUp over 1.35 m)"""
        return self._move('climb_ledge')

    def climb_ladder(self, opts=None):
        """climbLadder({height, rate, firstRung, rungSpacing, timeScale}): up the ladder on the face ahead, the rung loop
        chained into the mantle over its top (height: the ladder's, else the face's the scan measures). This edition
        also takes rungRadius (my palms close over rungs that thick) and standoff"""
        o = dict(opts or {})
        kw = {k: o[j] for j, k in (('height', 'height'), ('rate', 'rate'), ('firstRung', 'first_rung'),
                                   ('first_rung', 'first_rung'), ('rungSpacing', 'rung_spacing'),
                                   ('rung_spacing', 'rung_spacing'), ('timeScale', 'time_scale'),
                                   ('time_scale', 'time_scale'), ('rungRadius', 'rung_radius'),
                                   ('rung_radius', 'rung_radius'), ('standoff', 'standoff')) if j in o}
        return self._move('climb_ladder', **kw)

    def _move(self, name, **kw):
        """the controller's own move now -> started? A seated, emoting or turning body answers False (its clips own the
        frame); a move in flight too, as the engine's"""
        c = self.ctrl
        why = None
        if self._seat is not None:
            why = 'seated'
        elif c.is_emoting or (self._cmd is not None and self._cmd['kind'] in ('emote', 'stand')):
            why = 'an emote plays'
        elif self.is_turning:
            why = 'turning on the spot'
        if why is not None:
            self.maneuver_log.append((round(c.time, 3), name, [why]))
            return False
        n0 = len(self.said)
        ok = bool(getattr(c, name)(**kw))
        if not ok:
            self.maneuver_log.append((round(c.time, 3), name, [s for _t, s in self.said[n0:]][-3:]))
        return ok

    # ------------------------------------------------------------------------------------------------------ the bake
    def bake(self, f0=None, face=None, crown_state=None, head_state=None, action_name=None, key=True, springs=True,
             log=print):
        """the take baked (eidoblend.characters.robot.bake) -> report"""
        from . import bake as B
        return B.bake_run(self, f0=f0, face=face, crown_state=crown_state, head_state=head_state,
                          action_name=action_name, key=key, springs=springs, log=log)


# an aimed emote pivots during its fade-in up to this far off my heading; further, I turn on the spot first. Measured on
# my body through the plant, pivoting right after a walk's stop with the walk's last stance planted: 10 and 15 deg hold
# both feet both ways; 20 deg to the left turns the planted left foot 4.3 deg in a frame, 60 deg slides it 26 mm in a
# frame and 75 deg 178 mm (my hip's yaw ring cannot twist a planted leg that far)
PIVOT_MAX = math.radians(15.0)


# ------------------------------------------------------------------------------------------------------------ the adapter
class EidoverseRobotController:
    """robot_controller.js's EidoverseRobotController: VRMRobotBody's controller contract over the legs"""

    @classmethod
    def create(cls, h, overrides=None, opts=None, rig=None, legs_class=None):
        """create(vrm, mixer, overrides, opts): opts start_position (x, y[, z]), start_heading (rad, 0 faces -Y),
        walk_speed, run_speed (the routes' paces; default this body's measured native ones), max_turn_rate (default the
        controller's 3.5 rad/s), arrive_radius, collision_meshes (the walkable world: every surface walked on and every
        solid walked round; none: a flat ground at ground_z, as the JS), trimesh_colliders (every collision mesh as its
        triangles instead of its box: CollisionWorld), ground_z, controller_opts (the JS's opts.controllerOpts: any
        VRMCharacterController option, e.g. {'auto_maneuvers': False, 'vault_max_rise': 1.0}). overrides: the JS's
        {'standard_animation_overrides': {'vrma_library': {slot: .vrma path}}} (the stock slots played from other
        files). The JS's VRMUtils merge (fewer skinned draws for three's renderer) does not apply in Blender"""
        opts = dict(opts or {})
        overrides = dict(overrides or {})
        mine = {o.name for o in h.objects} | {h.arm.name}
        meshes = [o for o in (opts.get('collision_meshes') or []) if o.name not in mine]
        if not meshes:
            print('[eidoverse-robot] no collision_meshes provided: using a flat ground plane at z='
                  f'{opts.get("ground_z", 0.0)}', flush=True)
        world = CollisionWorld(meshes, opts.get('ground_z', 0.0), opts.get('trimesh_colliders', False))
        lib = (overrides.get('standard_animation_overrides') or {}).get('vrma_library')
        Legs = legs_class or RobotLegs
        legs = Legs(h, rig=rig, world=world, start_position=opts.get('start_position', (0.0, 0.0, 0.0)),
                    start_heading=opts.get('start_heading', 0.0), walk_speed=opts.get('walk_speed'),
                    run_speed=opts.get('run_speed'), max_turn_rate=opts.get('max_turn_rate'),
                    controller_opts=opts.get('controller_opts'), vrma_library=lib)
        return cls(h, legs, opts)

    def __init__(self, h, char_ctrl, opts=None):
        opts = opts or {}
        self.vrm = h
        self.char_ctrl = char_ctrl
        self.waypoints = []
        self.waypoint_index = 0
        self.state = 'idle'                  # 'idle' | 'walking' | 'running' | 'performing' | 'seated'
        self.walk_speed = getattr(char_ctrl, 'walk_speed', None) or opts.get('walk_speed', 1.5)
        self.run_speed = getattr(char_ctrl, 'run_speed', None) or opts.get('run_speed', 3.6)
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

    def is_turning(self):
        """this edition's: a turn on the spot in hand (face_direction, a route's or an aimed emote's)"""
        return bool(getattr(self.char_ctrl, 'is_turning', False))

    # parkour passthroughs (scripted moments; a legs object without a move answers False, as the JS's ?? false)
    def vault(self):
        return getattr(self.char_ctrl, 'vault', lambda: False)()

    def jump(self, opts=None):
        return getattr(self.char_ctrl, 'jump', lambda o=None: False)(opts)

    def climb_ledge(self):
        return getattr(self.char_ctrl, 'climb_ledge', lambda: False)()

    def climb_ladder(self, opts=None):
        return getattr(self.char_ctrl, 'climb_ladder', lambda o=None: False)(opts)

    # this edition's: playGesture on the inner controller, and a turn on the spot (face_direction)
    def play_gesture(self, slot, weight=2.5, loop=True):
        return getattr(self.char_ctrl, 'play_gesture', lambda *a, **k: None)(slot, weight=weight, loop=loop)

    def stop_gesture(self):
        return getattr(self.char_ctrl, 'stop_gesture', lambda: None)()

    def turn_to(self, heading):
        """turn on the spot to `heading` (rad) -> started?; a legs object without turn_to snaps it (the JS's
        faceDirection)"""
        self.set_waypoints([])
        if hasattr(self.char_ctrl, 'turn_to'):
            return self.char_ctrl.turn_to(heading)
        self.char_ctrl._heading = heading
        return True

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
        elif self.waypoints:
            self.char_ctrl.running = False
        if hasattr(self.char_ctrl, 'set_route') and self.state != 'performing':
            self.char_ctrl.set_route(self.waypoints)

    def force_action(self, name, duration=None):
        """a stationary expressive clip through the legs' emote system: 'performing' at once (a caller polling the
        state right after must not see the old one), the clip loaded and played for `duration` (1.5 s by default);
        False (and the state restored) when it cannot be loaded. The JS counts `duration` from the call (the engine
        pivots to an aimed facing during the fade-in); an emote aimed further than the legs pivot turns on the spot
        first, and its `duration` starts when it plays"""
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
            self.char_ctrl.play_emote(name, 1.5 if duration is None else duration)
            self._emote_until = self._t + (1.5 if duration is None else duration)
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
            if slot or getattr(self.char_ctrl, 'performing', None) is not None:
                self.current_action = slot
                self.state = 'performing'
                self._emote_until = self._t + opts.get('duration', 1.8)
            else:
                self.state = 'walking' if self.waypoint_index < len(self.waypoints) else 'idle'
            return self.char_ctrl.end_seated(slot, opts)
        except Exception as e:  # noqa: BLE001
            print(f'[eidoverse-robot] end_seated failed: {e}', flush=True)

    def _performing(self, t):
        """the performing window: the legs' own emote or stand-up while they say it plays, else the JS's timer"""
        p = getattr(self.char_ctrl, 'performing', None)
        return bool(p) if p is not None else t < self._emote_until

    def update(self, t, dt):
        self._t = t
        legs = self.char_ctrl
        if self.state in ('performing', 'seated'):
            if self.state == 'performing' and not self._performing(t):
                self.current_action = None
                self.state = 'walking' if self.waypoint_index < len(self.waypoints) else 'idle'
                if hasattr(legs, 'set_route') and self.waypoint_index < len(self.waypoints):
                    legs.set_route(self.waypoints[self.waypoint_index:])     # the walk resumes from where it was
                elif hasattr(legs, 'stop_emote') and getattr(legs, 'performing', None) is None:
                    legs.stop_emote()
            if self.state in ('performing', 'seated'):
                legs.locomote(dt, {'x': 0.0, 'y': 0.0})
                if self.on_pre_vrm_update:
                    self.on_pre_vrm_update(dt)
                return
        dx_, dy_ = 0.0, 0.0
        if self.waypoint_index < len(self.waypoints):
            pos = legs.feet_world_position
            wp = self.waypoints[self.waypoint_index]
            dx, dy = wp['x'] - pos.x, wp['y'] - pos.y
            dist = math.hypot(dx, dy)
            running = wp.get('action') == 'run'
            legs.running = running
            if dist <= self.arrive_radius:
                self.waypoint_index += 1
                if self.waypoint_index >= len(self.waypoints):
                    self.state = 'idle'
            else:
                dx_, dy_ = dx / dist, dy / dist
                self.state = 'running' if running else 'walking'
        else:
            self.state = 'idle'
        stalled = not self.is_maneuvering and legs._blocked_frames >= 6
        if stalled:
            dx_, dy_ = 0.0, 0.0
            self.state = 'idle'
        elif getattr(legs, 'travelling', False):
            # this edition's: the legs slow down to stop ON the goal (film.FollowPath): the walk goes on until they
            # have, and a waypoint the route's rounded corner passed farther than arrive_radius from is passed
            if self.state == 'idle':
                self.state = 'running' if legs.running else 'walking'
            if dx_ == 0.0 and dy_ == 0.0:
                f = heading_vector(legs._heading)
                dx_, dy_ = f.x, f.y
        elif self.waypoints and hasattr(legs, 'travelling') and self.state in ('walking', 'running'):
            # the route is over (stopped on its goal): every waypoint is behind
            self.waypoint_index = len(self.waypoints)
            self.state = 'idle'
            dx_, dy_ = 0.0, 0.0
        legs.locomote(dt, {'x': dx_, 'y': dy_})
        if self.on_pre_vrm_update:
            self.on_pre_vrm_update(dt)

    def bake(self, **kw):
        """the run keyed (RobotLegs.bake)"""
        return self.char_ctrl.bake(**kw)
