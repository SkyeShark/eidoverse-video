"""eidoblend.characters.controller.film: directing the controller for a film, and the bake that keys what it did.

    from eidoblend.characters.controller import CollisionWorld, VRMCharacterController, Locomotion
    world = CollisionWorld()                           # the scene's meshes (a skinned VRM never probes itself)
    walk = Locomotion(me, world, start=(0, 0, 0), heading=0.0)   # loads the clips, attaches the gait tree
    walk.wait(0.5)                                     # standing (idle)
    walk.move_to((0, -6))                              # accelerate from standing, walk, slow down and stop on the point
    walk.turn_to(90)                                   # on the spot (turnLeft / turnRight, degrees, 0 faces -Y)
    walk.follow_path([(2, -6), (2, -12)], speed=3.0)   # gait by speed: a run (or gait='walk' / 'run')
    walk.emote('salute', 2.0)                          # a full-body emote (locomotion suspended), then back to idle
    rep = walk.bake(f0=1)                              # run it frame by frame, plant the feet, key the armature

The commands queue up; bake() runs the controller (controller.py: the WebGPU gait tree, probes, stairs and ramps) one
frame at a time at the scene's fps, steering it the way the WebGPU robot adapter does (robot_controller.js: a unit
direction toward the current waypoint into locomote(), arrival within a radius), with what a film needs on top:

  speed       an acceleration from standing and a deceleration that stops ON the point (v^2 = 2 a d), walk 1.8 / 2.2 and
              run 3.5 / 4.0 m/s^2 by default; the WebGPU input is a unit direction (instant speed)
  gait        'walk' / 'run' set the controller's running flag (the WebGPU family switch, crossfaded); a speed alone
              picks the gait: at or over run_threshold (default halfway between this body's native walk and run speeds)
              it runs. Each gait's speed defaults to its clip's native pace on this body
  paths       corners rounded into arcs of radius speed / max_turn_rate (round one's walk_path does the same), followed
              with a pure-pursuit look-ahead of 0.6 s of travel
  turns       a heading change of more than turn_threshold (60 deg) from standing is a turn on the spot first; turn_to
              turns on the spot (larger than the clip's own turn: split into equal turns); under 20 deg a settling turn
  distance    the controller runs with gait_sync='distance' (distance matching) unless bake(gait_sync='stride')

Every frame is recorded (the root, the blended normalized pose before the foot IK, the clips' weights and times, each
foot's blended stance) and plant.py places the feet over the whole run; feet='foot_ik' keys the WebGPU foot IK's own
per-frame result instead (it slides wherever the stride and the travel differ). The report: plant.py's (stances,
swings, double support, flight) plus 'segments' (the frames each gait led) with checks.feet run on each.
"""

import math

import bpy
import numpy as np
from mathutils import Vector

from ..ground import SIDES
from ..locomotion import _path, key_frames
from .controller import VRMCharacterController
from .plant import FLIGHT_SLOTS, plant, sub_report

ACCEL = {'walk': 1.8, 'run': 3.5}
DECEL = {'walk': 2.2, 'run': 4.0}
TURN_THRESHOLD = 60.0 * math.pi / 180.0
SETTLE_LIMIT = 20.0 * math.pi / 180.0
# the gaits by name: the clip family the controller plays (its running flag) and the pace as a fraction of that family's
# native pace on this body. walk and run are the controller's own; the library has no slowRun / fastRun / walkBackward
# clip (render_scene.mjs names the slots in its treadmill guard), so these are the controller's clips at another pace:
# a jog and a sprint are the run clip with its cadence slowed or quickened (distance matching keeps the stride), a
# backward walk is the walk clip run backward under the travel (the stances replay in reverse: toe strike, heel lift)
GAITS = {'walk': ('walk', 1.0), 'run': ('run', 1.0), 'slowRun': ('run', 0.8), 'fastRun': ('run', 1.25),
         'walkBackward': ('walk', 0.6)}


def heading_of(dx, dy):
    """the heading (rad, the controller's convention: 0 faces -Y, pi faces +Y) of a direction"""
    return math.atan2(dx, -dy)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class _Cmd:
    started = False

    def start(self, loco):
        pass

    def step(self, loco, dt):
        return None


class Wait(_Cmd):
    def __init__(self, seconds):
        self.left = float(seconds)

    def step(self, loco, dt):
        if self.left <= 1e-9:
            return None
        self.left -= dt
        return (0.0, 0.0)


class Call(_Cmd):
    def __init__(self, fn):
        self.fn = fn

    def start(self, loco):
        self.fn(loco.ctrl)


class SetRunning(_Cmd):
    def __init__(self, v):
        self.v = v

    def start(self, loco):
        loco.ctrl.set_running(self.v)


class TurnTo(_Cmd):
    """turn on the spot to a heading (rad) or by an angle (rad)"""

    def __init__(self, heading=None, by=None):
        self.heading, self.by = heading, by

    def start(self, loco):
        c = loco.ctrl
        if self.by is not None:
            ang = self.by
        else:
            ang = _wrap(self.heading - c._heading)
        self.left = ang
        self.parts = []
        if abs(ang) < SETTLE_LIMIT:
            self.settle = c._heading + ang
            return
        self.settle = None
        clip = c._actions.get('turnLeft' if ang > 0 else 'turnRight')
        total = abs(clip.clip.total_root_yaw) if clip is not None else math.pi / 2
        k = max(1, int(math.ceil(abs(ang) / (total * 1.1))))
        self.parts = [ang / k] * k

    def step(self, loco, dt):
        c = loco.ctrl
        if self.settle is not None:
            d = _wrap(self.settle - c._heading)
            if abs(d) < 0.003:
                c._heading = self.settle
                return None
            c._heading += d * (1 - math.exp(-8 * dt))
            return (0.0, 0.0)
        if c.is_turning:
            return (0.0, 0.0)
        if self.parts:
            c.turn_on_spot(self.parts.pop(0))
            return (0.0, 0.0)
        return None


class FollowPath(_Cmd):
    """walk / run along a polyline (world x, y) and stop on its last point (stop=False: carry on into the next command)"""

    def __init__(self, points, speed=None, gait=None, stop=True, arrive=0.03, accel=None, decel=None, look=0.6,
                 turn_first=True):
        self.points = [tuple(map(float, p[:2])) for p in points]
        self.speed, self.gait, self.stop, self.arrive = speed, gait, stop, arrive
        self.accel, self.decel, self.look, self.turn_first = accel, decel, look, turn_first

    def start(self, loco):
        c = loco.ctrl
        pos = c.feet_world_position
        pts = [(pos.x, pos.y)] + self.points
        gait = self.gait
        v = self.speed
        if gait is None:
            gait = 'run' if (v is not None and v >= loco.run_threshold) else 'walk'
        if gait not in GAITS:
            raise ValueError(f'follow_path: gait {gait!r} (one of {sorted(GAITS)}; no sneak clip exists in the library)')
        family, frac = GAITS[gait]
        if v is None:
            v = loco.native[family] * frac
        self.gait_name, self.family, self.v = gait, family, float(v)
        self.backward = gait == 'walkBackward'
        c.backward = self.backward
        c.set_running(family == 'run')
        if family == 'run':
            c._run_speed = self.v
        else:
            c._flat_speed = self.v
        self.a_up = self.accel or ACCEL[family]
        self.a_dn = self.decel or DECEL[family]
        self.at, self.total = _path(pts, max(0.3, self.v / max(c.max_turn_rate, 0.5)))
        self.s = 0.0
        self.v_des = c.speed_actual
        self.turned = False
        self.d0 = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]

    def _project(self, pos):
        best, bs = 1e9, self.s
        for k in range(-5, 41):
            s = self.s + k * 0.02
            if s < 0:
                continue
            p, _h = self.at(min(s, self.total + 0.5))
            d = (p.x - pos.x) ** 2 + (p.y - pos.y) ** 2
            if d < best:
                best, bs = d, s
        self.s = max(self.s, bs)

    def _done(self, c):
        c.stop_distance = None
        c.backward = False
        return None

    def step(self, loco, dt):
        c = loco.ctrl
        if self.turn_first and not self.turned:
            self.turned = True
            want = heading_of(*self.d0) + (math.pi if self.backward else 0.0)
            if c.speed_actual < 0.3 and abs(_wrap(want - c._heading)) > TURN_THRESHOLD:
                self.sub = TurnTo(heading=want)
                self.sub.start(loco)
        if getattr(self, 'sub', None) is not None:
            inp = self.sub.step(loco, dt)
            if inp is not None:
                return inp
            self.sub = None
        pos = c.feet_world_position
        self._project(pos)
        remain = max(0.0, self.total - self.s)
        end, _h = self.at(self.total)
        dist_end = math.hypot(end.x - pos.x, end.y - pos.y)
        if self.stop:
            remain = min(remain, dist_end) if remain < 0.5 else remain
            if remain <= self.arrive or (dist_end <= self.arrive):
                return self._done(c)
            v_stop = math.sqrt(2.0 * self.a_dn * max(0.0, remain - self.arrive * 0.5))
        else:
            if remain <= 0.05:
                return self._done(c)
            v_stop = 1e9
        if c.mode == 'maneuver' or (not c.grounded and c.time > 0):
            self.v_des = min(self.v_des, c.speed_actual)     # a landing (fallLand) stops the body: walk off again
        self.v_des = min(self.v, self.v_des + self.a_up * dt, v_stop)
        if self.stop and self.v_des < 0.04 and remain < 0.2:
            return self._done(c)
        # the stop: the controller spreads the gait's phase over the ground left (distance matching to a stop), and a
        # run slowing under the run threshold finishes as a walk
        c.stop_distance = remain if (self.stop and v_stop < self.v * 1.5) else None
        if self.family == 'run' and c.running and self.stop and v_stop < loco.run_threshold * 0.85:
            c.set_running(False)
            c._flat_speed = loco.native['walk']
        L = max(0.25, self.look * max(self.v_des, 0.4))
        tgt, _h = self.at(min(self.s + L, self.total + (0.0 if self.stop else L)))
        dx, dy = tgt.x - pos.x, tgt.y - pos.y
        dl = math.hypot(dx, dy)
        if dl < 1e-6:
            return None
        base = max(c._smooth_fwd_speed, 1e-3)
        m = max(0.0, min(1.0, self.v_des / base))
        return (dx / dl * m, dy / dl * m)


class Emote(_Cmd):
    """playEmote for `seconds` (default: the clip once), then stopEmote. facing: where the body turns while it plays
    (the WebGPU controller's _emoteFacingY): 'keep' (default) the current heading, a heading in degrees, or None for
    the WebGPU default (three's rotation.y = pi: Blender +Y)"""

    def __init__(self, slot, seconds=None, fade_in=0.2, fade_out=0.3, loop=False, facing='keep'):
        self.slot, self.seconds, self.fade_in, self.fade_out, self.loop, self.facing = \
            slot, seconds, fade_in, fade_out, loop, facing

    def start(self, loco):
        c = loco.ctrl
        if self.slot not in getattr(c, '_emote_actions', {}):
            c.load_emote(self.slot, loop=self.loop)
        if self.facing == 'keep':
            c._emote_facing_y = c._heading
        elif self.facing is None:
            c._emote_facing_y = None
        else:
            c._emote_facing_y = self.facing * math.pi / 180.0
        a = c.play_emote(self.slot, fade_in=self.fade_in)
        dur = a.clip.duration if a else 0.0
        self.left = self.seconds if self.seconds is not None else dur
        self.phase = 'play'

    def step(self, loco, dt):
        c = loco.ctrl
        if self.phase == 'play':
            self.left -= dt
            if self.left <= 0:
                c.stop_emote(fade_out=self.fade_out)
                self.phase = 'out'
                self.left = self.fade_out + 0.1
            return (0.0, 0.0)
        self.left -= dt
        return (0.0, 0.0) if self.left > 0 else None


class Gesture(_Cmd):
    def __init__(self, slot, on=True, weight=2.5, loop=True):
        self.slot, self.on, self.weight, self.loop = slot, on, weight, loop

    def start(self, loco):
        c = loco.ctrl
        if not self.on:
            c.stop_gesture()
            return
        if self.slot not in getattr(c, '_gesture_actions', {}):
            c.load_gesture(self.slot, loop=self.loop)
        c.play_gesture(self.slot, weight=self.weight)


SEAT_BONES = ('hips', 'leftUpperLeg', 'rightUpperLeg')


def _seat_skin(h):
    """the meshes that are the skin over the pelvis and thighs: of the meshes carrying thigh-weighted vertices, the one
    whose vertices sit tightest round the thigh bones at rest (and any within 1.3 x of it). A coat or a skirt skinned to
    the thighs hangs looser, and in a seat its skinned hem goes through the pan: it is not what rests on it ->
    [(mesh, {vertex index: True})], cached on the handle"""
    cache = getattr(h, '_seat_skin', None)
    if cache is not None:
        return cache
    want = {h.humanoid[b] for b in SEAT_BONES if b in h.humanoid}
    thighs = {}
    for s in ('left', 'right'):
        b = h.humanoid.get(s + 'UpperLeg')
        if b:
            bone = h.arm.data.bones[b]
            thighs[b] = (bone.head_local.copy(), (bone.tail_local - bone.head_local).normalized())
    cand = []
    for o in h.meshes:
        idx = {g.index: g.name for g in o.vertex_groups}
        if not any(nm in want for nm in idx.values()):
            continue
        M = h.arm.matrix_world.inverted() @ o.matrix_world
        keep, dist = {}, []
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            nm = idx.get(best)
            if nm in want:
                keep[v.index] = True
                if nm in thighs:
                    a, u = thighs[nm]
                    p = M @ v.co - a
                    dist.append((p - u * p.dot(u)).length)
        if keep and dist:
            cand.append((float(np.median(dist)), o, keep))
    if not cand:
        h._seat_skin = []
        return []
    tight = min(c[0] for c in cand)
    h._seat_skin = [(o, keep) for d, o, keep in cand if d <= 1.3 * tight]
    return h._seat_skin


def seat_underside(h, xy, z0, half=0.15, n=7):
    """the seated body's underside under the pelvis: the lowest point, over a grid of up-rays (half m either way of xy,
    n x n, from z0), of the posed skin over the pelvis and thighs (_seat_skin: the vertices whose strongest weight is the
    hips' or a thigh's, on the skin's mesh: hair, tentacles, a coat's hem or a calf over the pan are not what rests on
    it) -> z or None"""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o, keep in _seat_skin(h):
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        M = o.matrix_world
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        for p in me.polygons:
            if all(i in keep for i in p.vertices):
                polys.append(tuple(base + i for i in p.vertices))
        ev.to_mesh_clear()
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(verts, polys)
    low = None
    for i in range(n):
        for j in range(n):
            x = xy[0] - half + 2 * half * i / (n - 1)
            y = xy[1] - half + 2 * half * j / (n - 1)
            loc, _n, _k, _d = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, 1.0)), 1.5)
            if loc is not None and (low is None or loc.z < low):
                low = loc.z
    return low


def seat_gap(h, body, cclip, M, seat):
    """how far the seated clip's underside rides over a seat's pan (m; negative: sunk into it): the clip's end pose
    (the held seat) put on the armature at the root M, its underside under the pelvis (seat_underside) less the pan's
    height (eidoblend.placement.seating's findSeatSurface). The armature is put back as it was. -> (gap, the pan's
    height)"""
    from ...placement import seating as SE
    arm = h.arm
    ad = arm.animation_data
    act = ad.action if ad is not None else None
    saved = {pb.name: (pb.rotation_mode, pb.rotation_quaternion.copy(), pb.location.copy()) for pb in arm.pose.bones}
    mw = arm.matrix_world.copy()
    try:
        if ad is not None:
            ad.action = None
        N, off = cclip.sample(cclip.duration, loop=False)
        for nm, b in h.humanoid.items():
            pb = arm.pose.bones[b]
            pb.rotation_mode = 'QUATERNION'
            q = N.get(nm)
            pb.rotation_quaternion = h.basis_from_normalized(b, q) if q is not None else (1.0, 0.0, 0.0, 0.0)
        hb = h.humanoid['hips']
        arm.pose.bones[hb].location = h.rest_q[hb].inverted() @ (off if off is not None else Vector())
        arm.matrix_world = M
        bpy.context.view_layer.update()
        pan = SE.find_seat_surface(seat)
        hp = arm.matrix_world @ arm.pose.bones[hb].head
        lowest = seat_underside(h, (hp.x, hp.y), pan['z'] - 0.35)
    finally:
        for pb in arm.pose.bones:
            rm, q, loc = saved[pb.name]
            pb.rotation_mode = rm
            pb.rotation_quaternion = q
            pb.location = loc
        arm.matrix_world = mw
        if ad is not None:
            ad.action = act
        bpy.context.view_layer.update()
    if lowest is None:
        return None, pan['z']
    return lowest - pan['z'], pan['z']


class Sit(_Cmd):
    """beginSeated / endSeated as the WebGPU course example drives them: the seated clip plays from where the body
    stands (the root holds; the clip's own hip travel carries the hips back onto the seat), `down` seconds to sit (default:
    the clip), `hold` seated, then endSeated (reverse=True plays the seated clip backwards at reverse_speed, else
    stand_clip forward), `up` seconds to stand (default: the clip's remaining time), stopEmote, and the walk resumes.
    seat: the seat object (the example's seatOn): the clip's held seat is measured on the posed mesh (seat_gap) and the
    root rises or sinks by that gap so the underside rests on the pan, eased in over the descent's second half and out
    over the first 60 % of the stand-up. The feet stand on the floor under the seated body (the plant)"""

    def __init__(self, hold=2.2, clip='stand_to_sit', stand_clip='sit_to_stand', reverse=True, reverse_speed=1.25,
                 down=None, up=None, fade_in=0.25, fade_out=0.3, seat=None):
        self.hold, self.clip, self.stand_clip, self.reverse, self.reverse_speed = hold, clip, stand_clip, reverse, \
            reverse_speed
        self.down, self.up, self.fade_in, self.fade_out, self.seat = down, up, fade_in, fade_out, seat
        self.settle = 0.0

    def start(self, loco):
        c = loco.ctrl
        dur = c.begin_seated(self.clip, fade_in=self.fade_in)
        self.phase, self.left = 'down', (self.down if self.down is not None else (dur or 0.0))
        self.span = self.left
        if self.seat is not None:
            gap, pan_z = seat_gap(c.h, c.body, c._emote_clip(self.clip), c.pose.M.copy(), self.seat)
            self.settle = -gap if gap is not None else 0.0
            self.gap = gap
            loco.log(f'[film] sit: the held seat\'s underside {"(not over the pan)" if gap is None else f"{gap * 100:+.1f} cm"}'
                     f' over the pan at {pan_z:.3f} m: the root {"holds" if gap is None else f"moves {self.settle * 100:+.1f} cm"}')

    def _seat_dz(self):
        frac = 1.0 - max(0.0, self.left) / max(1e-6, self.span)
        if self.phase == 'down':
            k = min(1.0, max(0.0, (frac - 0.5) / 0.5))
        elif self.phase == 'hold':
            k = 1.0
        elif self.phase == 'up':
            k = 1.0 - min(1.0, frac / 0.6)
        else:
            k = 0.0
        return self.settle * k * k * (3.0 - 2.0 * k)

    def step(self, loco, dt):
        c = loco.ctrl
        self.left -= dt
        if self.left > 0:
            c.seat_dz = self._seat_dz()
            return (0.0, 0.0)
        if self.phase == 'down':
            self.phase, self.left = 'hold', self.hold
        elif self.phase == 'hold':
            rem = c.end_seated(None if self.reverse else self.stand_clip, reverse=self.reverse,
                               reverse_speed=self.reverse_speed)
            self.phase, self.left = 'up', (self.up if self.up is not None else (rem or 0.0) + 0.1)
        elif self.phase == 'up':
            c.stop_emote(fade_out=self.fade_out)
            self.phase, self.left = 'out', self.fade_out + 0.1
        else:
            c.seat_dz = 0.0
            return None
        self.span = max(self.left, 1e-6)
        c.seat_dz = self._seat_dz()
        return (0.0, 0.0)


class Maneuver(_Cmd):
    """an explicit move (the controller's vault / climb_ledge / jump / climb_ladder / climb_wall) from where the body
    stands, facing its heading; the command lasts while the move (and anything it chains) is in flight"""

    def __init__(self, name, **kw):
        self.name, self.kw = name, kw

    def start(self, loco):
        c = loco.ctrl
        self.ok = bool(getattr(c, self.name)(**self.kw))
        if not self.ok:
            loco.log(f'[film] {self.name}: the controller could not start it here')

    def step(self, loco, dt):
        c = loco.ctrl
        if self.ok and c.is_maneuvering:
            return (0.0, 0.0)
        return None


class Locomotion:
    """a VRMCharacterController set up for a film (the module's doc): the clips loaded, the gait tree attached with the
    WebGPU defaults except the speeds (this body's native paces) and the sync (distance matching), and a queue of
    commands that bake() runs and keys"""

    def __init__(self, h, world, start=(0.0, 0.0, 0.0), heading=math.pi, ctrl=None, leg_ik='default',
                 gait_sync='distance', preset='robot', controller_opts=None, locomotion_opts=None, log=print):
        self.h, self.world, self.log = h, world, log
        if ctrl is None:
            from .controller import PRESETS
            co = dict(PRESETS[preset]) if preset else {}
            co.update(start_position=tuple(start), start_heading=heading, enable_turning=True, land_on_contact=True,
                      ground_past_steep=True, log=log)
            co.update(controller_opts or {})
            ctrl = VRMCharacterController(h, world, **co)
            ctrl.load_standard_animations()
            lo = dict(flat_speed=None, run_speed=None, native_walk_speed=None, native_run_speed=None,
                      gait_sync=gait_sync)
            lo.update(locomotion_opts or {})
            ctrl.attach_locomotion(leg_ik=leg_ik, **lo)
        self.ctrl = ctrl
        self.native = {'walk': ctrl._native_walk_speed, 'run': ctrl._native_run_speed}
        self.run_threshold = 0.5 * (self.native['walk'] + self.native['run'])
        self._queue = []
        self.records = []

    # ---- the commands
    def wait(self, seconds):
        self._queue.append(Wait(seconds))
        return self

    def move_to(self, point, speed=None, gait=None, stop=True, **kw):
        self._queue.append(FollowPath([point], speed=speed, gait=gait, stop=stop, **kw))
        return self

    def follow_path(self, points, speed=None, gait=None, stop=True, **kw):
        self._queue.append(FollowPath(points, speed=speed, gait=gait, stop=stop, **kw))
        return self

    def run_to(self, point, speed=None, **kw):
        return self.move_to(point, speed=speed, gait='run', **kw)

    def turn_to(self, heading_deg):
        self._queue.append(TurnTo(heading=heading_deg * math.pi / 180.0))
        return self

    def turn_by(self, deg):
        self._queue.append(TurnTo(by=deg * math.pi / 180.0))
        return self

    def face(self, point):
        """turn on the spot toward a world point (x, y)"""
        self._queue.append(_FaceCmd(point))
        return self

    def emote(self, slot, seconds=None, **kw):
        self._queue.append(Emote(slot, seconds, **kw))
        return self

    def gesture(self, slot, weight=2.5, loop=True):
        """playGesture: the upper body plays `slot` over whatever the legs do until stop_gesture()"""
        self._queue.append(Gesture(slot, True, weight, loop))
        return self

    def vault(self):
        """vault the cover ahead (the auto-trigger does this on its own while a path crosses low cover)"""
        self._queue.append(Maneuver('vault'))
        return self

    def climb_ledge(self):
        self._queue.append(Maneuver('climb_ledge'))
        return self

    def jump(self, distance=1.4, height=0.45):
        self._queue.append(Maneuver('jump', distance=distance, height=height))
        return self

    def climb_ladder(self, height=None, **kw):
        """climb the ladder the body faces (height: the ladder's, else the scanned face's)"""
        self._queue.append(Maneuver('climb_ladder', height=height, **kw))
        return self

    def climb_wall(self, **kw):
        self._queue.append(Maneuver('climb_wall', **kw))
        return self

    def sit(self, hold=2.2, seat=None, **kw):
        """sit down where the body stands (Sit: beginSeated, hold, endSeated, stopEmote); seat: the seat object, so the
        seated underside rests on its pan (seatOn's settle)"""
        self._queue.append(Sit(hold=hold, seat=seat, **kw))
        return self

    def seat_spot(self, seat_xy, heading_deg, clip='stand_to_sit'):
        """where to stand, facing heading_deg, so that `clip`'s own hip travel ends with the hips over seat_xy"""
        c = self.ctrl
        cc = c._emote_clip(clip)
        off = c.body.H['hips'] + Vector(cc.root_curve[-1])        # the hips over the root at the clip's end
        h = heading_deg * math.pi / 180.0
        dx = math.cos(h) * off[0] - math.sin(h) * off[1]
        dy = math.sin(h) * off[0] + math.cos(h) * off[1]
        return (seat_xy[0] - dx, seat_xy[1] - dy)

    def stop_gesture(self):
        self._queue.append(Gesture(None, False))
        return self

    def set_running(self, v):
        self._queue.append(SetRunning(v))
        return self

    def call(self, fn):
        self._queue.append(Call(fn))
        return self

    # ---- the bake
    def simulate(self, f0=1, max_seconds=600.0, fps=None):
        """run the queue frame by frame; -> the records"""
        sc = bpy.context.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        dt = 1.0 / fps
        c = self.ctrl
        recs = []
        f, t = f0, 0.0
        guard = int(max_seconds * fps)
        while self._queue and len(recs) < guard:
            cmd = self._queue[0]
            if not cmd.started:
                cmd.start(self)
                cmd.started = True
            inp = cmd.step(self, dt)
            if inp is None:
                if self._queue and self._queue[0] is cmd:
                    self._queue.pop(0)
                continue
            c.locomote(dt, inp)
            recs.append(record(c, f, t))
            recs[-1]['cmd'] = type(cmd).__name__
            recs[-1]['gait'] = getattr(cmd, 'gait_name', None)
            f += 1
            t += dt
        self.records += recs
        return recs

    def bake(self, f0=1, key=True, feet='plant', pelvis='stance', clearance=0.03, face=None, crown_state=None,
             head_state=None, action_name=None, max_seconds=600.0, check=True):
        """simulate, plant the feet, key the armature -> the report (plant.py's, plus 'segments', 'action', timings)"""
        import time
        sc = bpy.context.scene
        fps = sc.render.fps / sc.render.fps_base
        t0 = time.time()
        recs = self.simulate(f0=f0, max_seconds=max_seconds)
        t1 = time.time()
        body = self.ctrl.body
        if feet == 'plant':
            frames, rep = plant(body, self.world, recs, fps, clearance=clearance, pelvis=pelvis, face=face,
                                crown_state=crown_state, head_state=head_state, log=self.log)
        elif feet == 'foot_ik':
            frames = [{'f': r['f'], 'M': r['M_ik'], 'N': r['N_ik'], 'off': r['off'], 'stages': {}, 'helpers': {},
                       'petals': None, 'meas': None, 'psi': r['heading'], 'mode': r['mode']} for r in recs]
            rep = {}
        else:
            raise ValueError(f'bake: feet={feet!r} (plant | foot_ik)')
        t2 = time.time()
        rep['segments'] = segments(recs)
        if check and feet == 'plant':
            for seg in rep['segments']:
                ok, bad = check_segment(rep, seg)
                seg['checks_feet'] = {'ok': ok, 'failures': bad}
        if key:
            rep['action'] = key_frames(self.h, body, frames, action_name or f'{self.h.name}|controller')
        self.h.arm['eido_controller'] = True         # the audits' motion.locomotion: this rig's travel is driven
        rep['timing_s'] = {'simulate': round(t1 - t0, 2), 'plant': round(t2 - t1, 2), 'key': round(time.time() - t2, 2)}
        rep['frames_baked'] = [recs[0]['f'], recs[-1]['f']] if recs else None
        rep['_frames'] = frames
        rep['_records'] = recs
        return rep


class _FaceCmd(TurnTo):
    def __init__(self, point):
        super().__init__()
        self.point = point

    def start(self, loco):
        p = loco.ctrl.feet_world_position
        self.heading = heading_of(self.point[0] - p.x, self.point[1] - p.y)
        super().start(loco)


def record(c, f, t):
    """one frame of the controller, for the plant: the root and the blended pose BEFORE the foot IK, each foot's stance
    blended from the clips playing (at their effective weights and their own clip times), the IK's own result"""
    p = c.anim_pose if c.anim_pose is not None else c.pose
    mx = c._mixer
    st = {s: 0.0 for s in SIDES}
    wsum = 0.0
    lead, lead_w = None, 0.0
    gest = set(getattr(c, '_gesture_actions', {}).keys())
    for a in mx.active:
        w = a.get_effective_weight()
        if w <= 1e-4 or a.clip.slot in gest:
            continue
        wsum += w
        loop = a.loop != 'once'
        for s in SIDES:
            st[s] += w * a.clip.stance_at(a.clip_time, s, loop=loop)
        if w > lead_w:
            lead, lead_w = a.clip.slot, w
    if wsum > 1e-6:
        st = {s: v / wsum for s, v in st.items()}
    else:
        st = {s: 1.0 for s in SIDES}
    sf = c.support_frame or {}
    return {'f': f, 't': t, 'M': p.M.copy(), 'N': {k: q.copy() for k, q in p.N.items()}, 'off': p.off.copy(),
            'heading': c.scene_heading, 'mode': c.mode, 'grounded': bool(c.grounded), 'speed': c.speed_actual,
            'maneuver': getattr(c, 'maneuver_type', None) if c.mode == 'maneuver' else None,
            'stance': st, 'lead': lead, 'running': bool(getattr(c, 'running', False)),
            'weights': {a.clip.slot: round(a.get_effective_weight(), 4) for a in mx.active
                        if a.get_effective_weight() > 1e-4},
            'support_mode': (sf.get('body') or {}).get('support_mode'),
            'terrain': {k: v for k, v in (sf.get('terrain') or {}).items() if k != 'small_stair_ascent_early'},
            'climb_deg': c.signed_climb_angle_deg, 'speed_scale': c.speed_scale, 'climb_blocked': bool(c._climb_blocked),
            'target_speed': getattr(c, 'target_forward_speed', None), 'smooth_speed': getattr(c, '_smooth_fwd_speed', None),
            'tread_run': c.ahead_tread_run, 'spread': c.ahead_probe_spread, 'stair_shape': c.ahead_stair_shape,
            'backward': bool(c.backward), 'feet_world': tuple(c.feet_world_position),
            'hand_contact': dict(getattr(c, 'hand_contact', None) or {}),
            'M_ik': c.pose.M.copy(), 'N_ik': {k: q.copy() for k, q in c.pose.N.items()}}


def segments(recs):
    """the frames each gait led: runs of the same leading clip (by weight) and mode, idle and turns included"""
    out = []
    cur = None
    for r in recs:
        lab = r['lead'] if r['mode'] == 'loco' else r['mode'] + (':' + r['lead'] if r['lead'] else '')
        if cur is None or cur['gait'] != lab:
            cur = {'gait': lab, 'frames': [r['f'], r['f']]}
            out.append(cur)
        else:
            cur['frames'][1] = r['f']
    return out


FLIGHT_GAITS = FLIGHT_SLOTS


def check_segment(rep, seg):
    """checks.feet on one gait's frames. A run's flight and its lack of double support are what a run is: for the run
    family those two walk rules' failures are left out (and listed under 'waived')"""
    from .. import checks
    sub = sub_report(rep, seg['frames'][0], seg['frames'][1])
    ok, bad = checks.feet(sub)
    g = seg['gait'].split(':')[-1]
    if g in FLIGHT_GAITS:
        walk_rules = ('no frame has both feet on the ground', 'have neither foot on the ground')
        seg['waived'] = [b for b in bad if any(w in b for w in walk_rules)]
        bad = [b for b in bad if not any(w in b for w in walk_rules)]
    return (not bad), bad
