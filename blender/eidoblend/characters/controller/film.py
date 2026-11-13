"""eidoblend.characters.controller.film: directing the controller for a film, and the bake that keys what it did.

    from eidoblend.characters.controller import CollisionWorld, VRMCharacterController, Locomotion
    world = CollisionWorld()                           # the scene's meshes (a skinned VRM never probes itself)
    walk = Locomotion(me, world, start=(0, 0, 0), heading=0.0)   # loads the clips, attaches the gait tree
    walk.wait(0.5)                                     # standing (idle)
    walk.move_to((0, -6))                              # accelerate from standing, walk, slow down and stop on the point
    walk.turn_to(90)                                   # on the spot (turnLeft / turnRight, degrees, 0 faces -Y)
    walk.follow_path([(2, -6), (2, -12)], speed=3.0)   # gait by speed: a run (or gait='walk' / 'run')
    walk.emote('salute', 2.0)                          # a full-body emote (locomotion suspended), then back to idle
    walk.follow(cart, distance=1.8)                    # after a keyed object, stopping short of it wherever it stops
    walk.steer(lambda t, ctrl: (1.0, 0.0) if t < 2 else None)   # a direction each frame from scene logic
    rep = walk.bake(f0=1)                              # run it frame by frame, plant the feet, key the armature, springs

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
  turns       a heading change of more than turn_threshold (60 deg; 25 deg on my robot body, whose hip turns a planted
              leg only so far about its own axis) from standing is a turn on the spot first; turn_to turns on the spot
              (larger than the clip's own turn: split into equal turns); under 20 deg a settling turn
  distance    the controller runs with gait_sync='distance' (distance matching) unless bake(gait_sync='stride')

Every frame is recorded (the root, the blended normalized pose before the foot IK, the clips' weights and times, each
foot's blended stance) and plant.py places the feet over the whole run; feet='foot_ik' keys the WebGPU foot IK's own
per-frame result instead (it slides wherever the stride and the travel differ). The report: plant.py's (stances,
swings, double support, flight) plus 'segments' (the frames each gait led) with checks.feet run on each. Then the VRM's
spring chains are simulated over the keyed take (bake_springs: as the engine's vrm.update stepped them every frame),
resting on the walkable world, out of the scene's solids, reset and settled where the take's root jumps.
"""

import math

import bpy
import numpy as np
from mathutils import Vector

from ..ground import SIDES
from ..locomotion import _path, key_frames
from .controller import VRMCharacterController
from .plant import FLIGHT_SLOTS, STAIR_CLIPS, plant, sub_report

ACCEL = {'walk': 1.8, 'run': 3.5}
DECEL = {'walk': 2.2, 'run': 4.0}
TURN_THRESHOLD = 60.0 * math.pi / 180.0
# my robot body: the hip's yaw ring turns the thigh about its own axis +-40 deg at most, less with the hip abducted
# (robot_dof.LEG_JOINTS), and the foot it stands on as it sets off holds its heading: a walk setting off more than this
# off the body's heading turns on the spot first
TURN_THRESHOLD_ROBOT = 25.0 * math.pi / 180.0
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
            thr = TURN_THRESHOLD_ROBOT if getattr(c.body, 'robot', False) else TURN_THRESHOLD
            if c.speed_actual < 0.3 and abs(_wrap(want - c._heading)) > thr:
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


class Steer(_Cmd):
    """locomote(dt, input) with the input worked out frame by frame by the scene (the WebGPU scenes' renderFrame): fn(t,
    ctrl) -> a direction of travel (world x, y; its length, at most 1, scales the pace), (0, 0) to stand, or None to
    end. t: seconds since the command started; the frame being simulated is loco.frame. The pace is the gait's (speed=,
    gait= as follow_path), reached with the walk's (or run's) acceleration and left with its deceleration, so a stand,
    a start and the end (stop=True: slowing to a stand along the last direction) read as steps, not pops; a first
    direction far off the body's heading from standing turns on the spot first, as follow_path does"""

    def __init__(self, fn, seconds=None, speed=None, gait=None, stop=True, accel=None, decel=None, turn_first=True):
        self.fn, self.seconds, self.speed, self.gait, self.stop = fn, seconds, speed, gait, stop
        self.accel, self.decel, self.turn_first = accel, decel, turn_first

    def start(self, loco):
        self.t = 0.0
        self.v = loco.ctrl.speed_actual
        self.dir = None
        self.ending = False
        self.sub = None
        self.set_gait(loco, self.gait, self.speed)

    def set_gait(self, loco, gait, v):
        """the clip family and its pace: gait by name, else by speed (run from loco.run_threshold), else a walk"""
        c = loco.ctrl
        if gait is None:
            gait = 'run' if (v is not None and v >= loco.run_threshold) else 'walk'
        if gait not in GAITS:
            raise ValueError(f'steer: gait {gait!r} (one of {sorted(GAITS)})')
        family, frac = GAITS[gait]
        self.gait_name, self.family = gait, family
        self.pace = float(v) if v is not None else loco.native[family] * frac
        c.backward = gait == 'walkBackward'
        c.set_running(family == 'run')
        if family == 'run':
            c._run_speed = self.pace
        else:
            c._flat_speed = self.pace
        self.a_up = self.accel or ACCEL[family]
        self.a_dn = self.decel or DECEL[family]

    def want(self, loco, dt):
        """this frame's (unit direction (x, y) or None to stand, speed m/s), or None to end"""
        d = self.fn(self.t, loco.ctrl)
        if d is None:
            return None
        x, y = float(d[0]), float(d[1])
        ln = math.hypot(x, y)
        if ln < 1e-6:
            return None, 0.0
        return (x / ln, y / ln), min(1.0, ln) * self.pace

    def _end(self, c):
        c.stop_distance = None
        c.backward = False
        return None

    def step(self, loco, dt):
        c = loco.ctrl
        if self.sub is not None:                      # the turn on the spot before the first steps (t runs on)
            inp = self.sub.step(loco, dt)
            if inp is not None:
                self.t += dt
                return inp
            self.sub = None
        w = None
        if not self.ending:
            if self.seconds is not None and self.t >= self.seconds - 1e-9:
                self.ending = True
            else:
                w = self.want(loco, dt)
                if w is None:
                    self.ending = True
        self.t += dt
        if self.ending:
            if not self.stop or self.dir is None or self.v < 0.03:
                return self._end(c)
            w = (None, 0.0)
        u, v_req = w
        if u is not None and v_req > 1e-6:
            if self.dir is None and self.turn_first and c.speed_actual < 0.3:
                want_h = heading_of(*u) + (math.pi if c.backward else 0.0)
                thr = TURN_THRESHOLD_ROBOT if getattr(c.body, 'robot', False) else TURN_THRESHOLD
                if abs(_wrap(want_h - c._heading)) > thr:
                    self.dir = u
                    self.sub = TurnTo(heading=want_h)
                    self.sub.start(loco)
                    inp = self.sub.step(loco, dt)
                    if inp is not None:
                        return inp
                    self.sub = None
            self.dir = u
        if self.dir is None:
            return (0.0, 0.0)
        if c.mode == 'maneuver' or (not c.grounded and c.time > 0):
            self.v = min(self.v, c.speed_actual)       # a landing stops the body: it sets off again from standing
        self.v = max(self.v - self.a_dn * dt, min(v_req, self.v + self.a_up * dt))
        # slowing to a stand: the gait's phase spread over the ground the deceleration covers (distance matching)
        c.stop_distance = (self.v * self.v / (2.0 * self.a_dn)) if v_req < 1e-6 and self.v > 0.03 else None
        base = max(c._smooth_fwd_speed, 1e-3)
        m = max(0.0, min(1.0, self.v / base))
        return (self.dir[0] * m, self.dir[1] * m)


class KeyedPlace:
    """where an object (or one of its bones) is at each frame of the scene, as its keys, constraints and parents put it:
    read through the depsgraph a batch of frames at a time and cached (the follower's own meshes hidden meanwhile, as
    nothing reads them). target: an object or a VRM handle (bone: a bone's name, or a humanoid name on a handle)"""

    BATCH = 30

    def __init__(self, target, bone=None, hide=()):
        self.obj = getattr(target, 'arm', target)
        hum = getattr(target, 'humanoid', None) or {}
        self.bone = hum.get(bone, bone) if bone else None
        if self.bone is not None and (self.obj.type != 'ARMATURE' or self.bone not in self.obj.pose.bones):
            raise ValueError(f'follow: {self.obj.name!r} has no bone {bone!r}')
        self.hide = list(hide)
        self.cache = {}
        last = []
        o = self.obj
        while o is not None:
            ad = o.animation_data
            if ad is not None:
                if ad.action is not None:
                    last.append(ad.action.frame_range[1])
                last += [st.frame_end for tr in ad.nla_tracks for st in tr.strips]
            o = o.parent
        self.end = int(math.ceil(max(last))) if last else None     # the last keyed frame (None: it never moves)

    def at(self, f):
        if f not in self.cache:
            sc = bpy.context.scene
            cur = sc.frame_current
            hidden = [o for o in self.hide if not o.hide_viewport]
            for o in hidden:
                o.hide_viewport = True
            try:
                for k in range(f, f + self.BATCH):
                    sc.frame_set(k)
                    if self.bone is not None:
                        p = (self.obj.matrix_world @ self.obj.pose.bones[self.bone].matrix).translation
                    else:
                        p = self.obj.matrix_world.translation
                    self.cache[k] = Vector((p.x, p.y, p.z))
            finally:
                sc.frame_set(cur)
                for o in hidden:
                    o.hide_viewport = False
        return self.cache[f]


FOLLOW_GAIN = 0.8           # 1/s: how quickly a follower that has dropped back makes up the distance
FOLLOW_LEAD = 0.4           # s: a moving target is steered for where it will be this much later


class Follow(Steer):
    """keep `distance` from a moving object (a character's armature, a vehicle, an empty, one of its bones), reading
    where its keys put it at each frame (KeyedPlace): walk or run toward where it is going, at its speed plus what
    makes up the distance, and stop `distance` short of it with follow_path's own deceleration (v^2 = 2ad, the gait's
    phase spread over the ground left) wherever it stops. gait None: a walk, a run while the speed needed is at or over
    loco.run_threshold (back to a walk under 0.8 of it); speed: the most the follower goes (default: the run's pace).
    seconds None: until the target's last key has passed and the follower stands at its distance"""

    def __init__(self, target, distance=1.0, speed=None, gait=None, seconds=None, bone=None, arrive=0.08,
                 lead=FOLLOW_LEAD, accel=None, decel=None, turn_first=True):
        super().__init__(None, seconds=seconds, speed=None, gait=gait, stop=True, accel=accel, decel=decel,
                         turn_first=turn_first)
        self.target, self.distance, self.cap, self.bone = target, float(distance), speed, bone
        self.arrive, self.lead = arrive, lead
        self.fixed = gait

    def start(self, loco):
        super().start(loco)
        self.place = KeyedPlace(self.target, self.bone, hide=getattr(loco.h, 'meshes', ()))
        if self.place.obj == loco.h.arm:
            raise ValueError('follow: a body cannot follow itself')
        sc = bpy.context.scene
        self.fps = sc.render.fps / sc.render.fps_base
        if self.cap is None:
            self.cap = loco.native['run'] if self.fixed is None else self.pace
        if self.fixed is None:
            self._family(loco, 'walk')

    def _family(self, loco, family):
        """the automatic gait: the walk paced up to the run threshold, the run up to the cap"""
        if family == 'walk':
            self.set_gait(loco, 'walk', min(self.cap, loco.run_threshold))
        else:
            self.set_gait(loco, 'run', max(self.cap, loco.run_threshold))

    def want(self, loco, dt):
        c = loco.ctrl
        f = loco.frame
        P, P1 = self.place.at(f), self.place.at(f + 1)
        V = (P1 - P).xy * self.fps
        me = c.feet_world_position.xy
        to_t = P.xy - me
        dist = to_t.length
        remain = dist - self.distance
        moving = V.length > 0.05
        self.stop_at = None
        keys_over = self.place.end is None or f >= self.place.end
        if self.seconds is None and keys_over and remain <= self.arrive and self.v < 0.03:
            return None                               # the target's keys are over and she stands at her distance
        if (remain <= self.arrive and not moving) or dist < 1e-6:
            return None, 0.0                          # close enough to a target that stands: stand (or slow to it)
        aim = P.xy + V * self.lead - me
        u = aim / aim.length if aim.length > 1e-6 else to_t / dist
        away = max(0.0, V.dot(to_t / dist))           # how fast the target draws away from her
        need = away + FOLLOW_GAIN * max(0.0, remain)
        v_stop = away + math.sqrt(2.0 * self.a_dn * max(0.0, remain - 0.5 * self.arrive))
        if self.fixed is None:
            if self.family == 'walk' and need >= loco.run_threshold:
                self._family(loco, 'run')
            elif self.family == 'run' and need < 0.8 * loco.run_threshold:
                self._family(loco, 'walk')
        if not moving and v_stop < 1.5 * self.pace:
            self.stop_at = max(remain, 1e-3)          # arriving where a stopped target stands (follow_path's stop)
        v_req = 0.0 if (remain <= 0.0 and away < 0.05) else max(0.0, min(self.cap, need, v_stop, self.pace))
        return (u.x, u.y), v_req

    def step(self, loco, dt):
        inp = super().step(loco, dt)
        if inp is not None and getattr(self, 'stop_at', None) is not None and not self.ending:
            loco.ctrl.stop_distance = self.stop_at    # the gait's phase spread over the ground left to the distance
        return inp


class Emote(_Cmd):
    """playEmote for `seconds` (default: the clip once), then stopEmote. facing: where the body turns while it plays
    (the WebGPU controller's _emoteFacingY): 'keep' (default) the current heading, a heading in degrees, or None for
    the WebGPU default (three's rotation.y = pi: Blender +Y). stop=False: no stopEmote, as a scene that plays an emote
    and never stops it (the course example's finale salute): after its seconds the clip holds its last pose (a clip
    played once stays clamped there) and the body keeps the emote's facing; the commands after it run with the emote
    still on (a wait holds the pose; locomotion stays suspended while it plays, the engine's)"""

    def __init__(self, slot, seconds=None, fade_in=0.2, fade_out=0.3, loop=False, facing='keep', stop=True):
        self.slot, self.seconds, self.fade_in, self.fade_out, self.loop, self.facing = \
            slot, seconds, fade_in, fade_out, loop, facing
        self.stop = stop

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
                if not self.stop:
                    return None                     # the pose held on: the next command takes the frame
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


def planted_legs(body, world, M, N, off):
    """the seated legs as the film bake leaves them: each foot set down on the ground under it (its lowest sole point
    on it, as plant.py stands a seat's feet), the leg solved to it as the plant solves a planted leg (Body.solve_leg,
    the knee swung to the foot) with the pelvis where the seat put it -> N with the legs changed (a copy)"""
    N = dict(N)
    ph, Wh = body.hips(M, off if off is not None else Vector(), N)
    for s in SIDES:
        fk = body.leg_fk(s, ph, Wh, N)
        P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
        G = world.h(P[:, 0], P[:, 1], z_from=P[:, 2] + 0.6)
        ok = G > -1e8
        if not ok.any():
            continue
        dz = float(np.min(P[ok, 2] - G[ok]))
        body.solve_leg(s, ph, Wh, N, fk['p_an'] - Vector((0.0, 0.0, dz)), fk['W_ft'], swivel=1.0)
    return N


def seat_gap(h, body, cclip, M, seat, world=None, t=None):
    """how far the seated clip's underside rides over a seat's pan (m; negative: sunk into it): the clip's end pose
    (the held seat; t: the clip at that time instead) put on the armature at the root M, its underside under the pelvis
    (seat_underside) less the pan's height (eidoblend.placement.seating's findSeatSurface). world: the walkable world,
    where the bake will set the feet down (planted_legs: a foot pushed up onto the floor raises its knee and turns the
    thigh under the pelvis into the pan; one let down lowers it). The armature is put back as it was. -> (gap, the
    pan's height)"""
    from ...placement import seating as SE
    arm = h.arm
    ad = arm.animation_data
    act = ad.action if ad is not None else None
    saved = {pb.name: (pb.rotation_mode, pb.rotation_quaternion.copy(), pb.location.copy()) for pb in arm.pose.bones}
    mw = arm.matrix_world.copy()
    try:
        if ad is not None:
            ad.action = None
        N, off = cclip.sample(cclip.duration if t is None else t, loop=False)
        if world is not None:
            N = planted_legs(body, world, M, N, off)
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


def stand_clip_travel(cc):
    """a stand-up clip (sit_to_stand: its root under the seated hips, its hips stepping forward over the feet) played
    with its hips' xy held over its first frame's: its hips' travel taken out of it, once per clip (cc._travel, (n + 1,
    2) in the clip's axes; cc.root_curve keeps the hips' curve as the clip has it) -> the travel, which the caller
    takes as root motion (stand_shift). The seated root holds still, so the travel played in the clip carried the hips
    forward off the root and, once the controller had the root back, slid them back onto it"""
    if not hasattr(cc, '_travel'):
        cc._travel = cc.P[:, :2] - cc.P[0, :2]
        cc.P[:, :2] = cc.P[0, :2]
        cc.root_curve = cc.root_curve.copy()
    return cc._travel


def stand_shift(cc, R, t, fade, span, cross, resid, extra0=None):
    """the seated root's shift (x, y) at time t of a stand-up clip played through stand_clip_travel: the crossfade's
    carry (cross: the seated pose's hips less the clip's first pose's, by the crossfade's weight, so the hips stay where
    the seated pose has them), the clip's hips' travel to t (R: the seated root's rotation), and what is left over
    against the standing spot (resid) eased out over the span's second half; extra0: the seat's own shift before the
    stand-up (emotes.StandUp's seated loop). film.Sit's forward stand-up and emotes.StandUp's stand-up clip ->
    Vector (x, y)"""
    w = min(1.0, t / max(fade, 1e-6))
    tc = min(t, cc.duration)
    kt = np.linspace(0.0, cc.duration, len(cc._travel))
    trw = R @ Vector((float(np.interp(tc, kt, cc._travel[:, 0])), float(np.interp(tc, kt, cc._travel[:, 1])), 0.0))
    e = min(1.0, max(0.0, (min(1.0, t / max(span, 1e-6)) - 0.5) / 0.5))
    out = cross * w + Vector((trw.x, trw.y)) - resid * (e * e * (3.0 - 2.0 * e))
    return out if extra0 is None else extra0 + out


SIT_CLAMP_FROM = 0.4        # from this share of the seated clip on, no seated skin goes into the pan (seatOn's clamp)


class Sit(_Cmd):
    """beginSeated / endSeated as the WebGPU course example drives them: the seated clip plays from where the body
    stands (the root holds; the clip's own hip travel carries the hips back onto the seat), `down` seconds to sit (default:
    the clip), `hold` seated, then endSeated (reverse=True plays the seated clip backwards at reverse_speed, else
    stand_clip forward), `up` seconds to stand (default: the clip's remaining time), stopEmote, and the walk resumes.
    seat: the seat object (the example's seatOn): the clip's held seat is measured on the posed mesh with the feet set
    down where the bake plants them (seat_gap) and the root rises or sinks by that gap so the underside rests on the
    pan, eased in over the descent's second half and out over the first 60 % of the stand-up; and from SIT_CLAMP_FROM
    of the clip on, sitting down and (reversed) standing up, the root is never lower than keeps the underside on the pan
    at the clip's time (the clamp: the clip's hips reach the seat's height before its end). The feet stand on the floor
    under the seated body (the plant). A stand-up clip (reverse=False) takes its hips' travel as root motion
    (stand_clip_travel, stand_shift: the hips stay on the seat through the crossfade, then step forward with the clip
    and end over the spot the sit began from) and the root is handed back at its end, so `up` is at least its length.
    The body keeps the seat's heading when the controller has the root back (an earlier emote's facing is not taken)"""

    def __init__(self, hold=2.2, clip='stand_to_sit', stand_clip='sit_to_stand', reverse=True, reverse_speed=1.25,
                 down=None, up=None, fade_in=0.25, fade_out=0.3, seat=None):
        self.hold, self.clip, self.stand_clip, self.reverse, self.reverse_speed = hold, clip, stand_clip, reverse, \
            reverse_speed
        self.down, self.up, self.fade_in, self.fade_out, self.seat = down, up, fade_in, fade_out, seat
        self.settle = 0.0
        self.clamp_t = self.clamp_v = None
        self.up_cc = None

    def start(self, loco):
        c = loco.ctrl
        c._emote_facing_y = c.scene_heading
        dur = c.begin_seated(self.clip, fade_in=self.fade_in)
        self.phase, self.left = 'down', (self.down if self.down is not None else (dur or 0.0))
        self.span = self.left
        if self.seat is not None:
            # measured on the legs the bake will plant (seat_gap's world=): settled, the feet go down onto the floor
            # (or up onto it) and the thighs turn with them, so the settle is measured again where it put the root
            cc, M = c._emote_clip(self.clip), c.pose.M.copy()
            gap, pan_z = seat_gap(c.h, c.body, cc, M, self.seat, world=loco.world)
            self.settle = -gap if gap is not None else 0.0
            for _ in range(2):
                if gap is None:
                    break
                Ms = M.copy()
                Ms.translation.z += self.settle
                g2, _z = seat_gap(c.h, c.body, cc, Ms, self.seat, world=loco.world)
                if g2 is None or abs(g2) < 0.002:
                    break
                self.settle -= g2
            self.gap = gap
            if gap is not None:
                # the clamp's lift at each clip time from SIT_CLAMP_FROM on (every frame), measured where the root
                # stands and once more where that lift puts it (the planted legs change with the height)
                fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
                ts = np.linspace(SIT_CLAMP_FROM * cc.duration, cc.duration,
                                 max(8, int(math.ceil((1.0 - SIT_CLAMP_FROM) * cc.duration * fps)) + 1))
                lift = []
                for t in ts:
                    g, _z = seat_gap(c.h, c.body, cc, M, self.seat, world=loco.world, t=float(t))
                    v = -g if g is not None else -1e9
                    if g is not None and abs(g) > 0.01:
                        Ms = M.copy()
                        Ms.translation.z += v
                        g2, _z = seat_gap(c.h, c.body, cc, Ms, self.seat, world=loco.world, t=float(t))
                        v = v - g2 if g2 is not None else v
                    lift.append(v)
                self.clamp_t, self.clamp_v = [float(t) for t in ts], lift
            loco.log(f'[film] sit: the held seat\'s underside {"(not over the pan)" if gap is None else f"{gap * 100:+.1f} cm"}'
                     f' over the pan at {pan_z:.3f} m: the root {"holds" if gap is None else f"moves {self.settle * 100:+.1f} cm"}'
                     + (f'; the clamp lifts it up to {max(self.clamp_v) * 100:+.1f} cm from {SIT_CLAMP_FROM:.0%} of the clip'
                        if self.clamp_v else ''))

    def _clamp(self, c, dt):
        """the lift the clamp needs in this frame: the seated clip's time after this frame's mixer step, read off the
        clamp curve (None before SIT_CLAMP_FROM, while the clip is not this seat's, or with no seat)"""
        if not self.clamp_t or (self.phase == 'up' and not self.reverse) or self.phase == 'out':
            return None
        a = getattr(c, '_emote_actions', {}).get(self.clip)
        if a is None:
            return None
        tau = min(max(a.time + dt * (0.0 if a.paused else a.time_scale), 0.0), a.clip.duration)
        if tau < self.clamp_t[0]:
            return None
        v = float(np.interp(tau, self.clamp_t, self.clamp_v))
        return v if v > -1e8 else None

    def _seat_dz(self, c=None, dt=0.0):
        frac = 1.0 - max(0.0, self.left) / max(1e-6, self.span)
        if self.phase == 'down':
            k = min(1.0, max(0.0, (frac - 0.5) / 0.5))
        elif self.phase == 'hold':
            k = 1.0
        elif self.phase == 'up':
            k = 1.0 - min(1.0, frac / 0.6)
        else:
            k = 0.0
        dz = self.settle * k * k * (3.0 - 2.0 * k)
        lift = self._clamp(c, dt) if c is not None else None
        return dz if lift is None else max(dz, lift)

    def _begin_stand_clip(self, c):
        """endSeated with the stand-up clip, its hips' travel as root motion: the clip crossfaded in over the held
        sit-down's last pose, the root carried by the two poses' hips (cross) and then by the clip's travel, what is
        left against the spot the sit began from eased out (resid); the root stays the seat's until the clip ends
        -> the clip's length (s)"""
        if self.stand_clip not in getattr(c, '_emote_actions', {}):
            c.load_emote(self.stand_clip, loop=False)
        cc = c._emote_actions[self.stand_clip].clip
        travel = stand_clip_travel(cc)
        M = c.pose.M.copy()
        R = M.to_3x3()
        d = R @ (Vector(c._emote_clip(self.clip).root_curve[-1]) - Vector(cc.root_curve[0]))
        trend = R @ Vector((travel[-1][0], travel[-1][1], 0.0))
        self.up_cc, self.up_R, self.up_t = cc, R, 0.0
        self.root0 = M.translation.copy()
        self.cross = Vector((d.x, d.y))
        self.resid = self.cross + Vector((trend.x, trend.y))
        c.play_emote(self.stand_clip, fade_in=self.fade_in, fade_out=self.fade_in)    # symmetric: the carry's weight
        c._seated_release_in = None
        return cc.duration

    def _carry(self, c, dt):
        """this frame's root on the stand-up clip's travel (the clip's time after this frame's mixer update); at the
        clip's end the root goes back to the controller, over the spot the sit began from"""
        cc = self.up_cc
        self.up_t += dt
        s = stand_shift(cc, self.up_R, self.up_t, self.fade_in, cc.duration, self.cross, self.resid)
        t = c.pose.M.translation.copy()
        t.x, t.y = self.root0.x + s.x, self.root0.y + s.y
        c.pose.M.translation = t
        c.pose.invalidate()
        if self.up_t >= cc.duration - 1e-6:
            c._seated = False
            self.up_cc = None

    def step(self, loco, dt):
        c = loco.ctrl
        self.left -= dt
        if self.left > 0:
            if self.up_cc is not None:
                self._carry(c, dt)
            c.seat_dz = self._seat_dz(c, dt)
            return (0.0, 0.0)
        if self.phase == 'down':
            self.phase, self.left = 'hold', self.hold
        elif self.phase == 'hold':
            if self.reverse:
                rem = c.end_seated(None, reverse=True, reverse_speed=self.reverse_speed)
                self.phase, self.left = 'up', (self.up if self.up is not None else (rem or 0.0) + 0.1)
            else:
                rem = self._begin_stand_clip(c)
                self.phase, self.left = 'up', max(self.up if self.up is not None else 0.0, rem) + 0.1
                self._carry(c, dt)
        elif self.phase == 'up':
            c.stop_emote(fade_out=self.fade_out)
            self.phase, self.left = 'out', self.fade_out + 0.1
        else:
            c.seat_dz = 0.0
            return None
        self.span = max(self.left, 1e-6)
        c.seat_dz = self._seat_dz(c, dt)
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

    def steer(self, fn, seconds=None, speed=None, gait=None, stop=True, **kw):
        """steer the controller frame by frame from scene logic (locomote(dt, input) as a WebGPU scene's renderFrame
        does): fn(t, ctrl) -> a direction of travel (world x, y; length at most 1 scales the pace), (0, 0) to stand,
        None to end; t is the command's seconds, self.frame the frame being simulated (Steer)"""
        self._queue.append(Steer(fn, seconds=seconds, speed=speed, gait=gait, stop=stop, **kw))
        return self

    def follow(self, target, distance=1.0, speed=None, gait=None, seconds=None, bone=None, **kw):
        """keep `distance` from a keyed object (a character's armature or a bone of it, a vehicle, an empty): walk or
        run after it and stop short of it wherever it stops; seconds None: until its keys are over and she stands at
        her distance (Follow)"""
        self._queue.append(Follow(target, distance=distance, speed=speed, gait=gait, seconds=seconds, bone=bone, **kw))
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
            self.frame = f                      # the frame being simulated (a steer function's, a follow's)
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
             head_state=None, action_name=None, max_seconds=600.0, check=True, springs=True):
        """simulate, plant the feet, key the armature, then the spring chains over the keyed take (bake_springs below;
        springs=False leaves them out, a dict passes characters.springs.bake_springs' options) -> the report (plant.py's,
        plus 'segments', 'action', 'springs', timings)"""
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
        if key and springs:
            t3 = time.time()
            rep['springs'] = self.bake_springs(rep, **(springs if isinstance(springs, dict) else {}))
            rep['timing_s']['springs'] = round(time.time() - t3, 2)
        return rep

    def bake_springs(self, rep, **opts):
        """the VRM's spring chains (hair, tails, tentacles, a coat's tails) simulated over the keyed take, frame by
        frame after the body's pose, as the engine's vrm.update(dt) stepped them every rendered frame, and keyed on
        their own NLA track (characters.springs.bake_springs: the solver, the preroll that starts them settled on the
        take's first pose, the keys). Called by bake() once the take is keyed; call it yourself after keying a take with
        bake(key=False). The chains rest on the walkable world (ground=, default the take's CollisionWorld: a tail
        lying on the floor stays on it) and stay out of every solid in the scene that stands still (solids=, default
        every visible mesh no armature deforms and nothing keys, seats included: a tail hanging behind a chair drapes
        over its pan rather than through its back; a cart the body follows moves, and one place of it would be a
        phantom to the others). They are reset (springBoneManager.reset) wherever the take's root jumps (take_resets: a
        teleport, an instant seat) and at opts['resets'] frames, and settled there on the new pose for the preroll's
        time (a cut opens on them hanging); a body with no spring chain (my robot body) is left alone -> bake_springs'
        report, or None"""
        from .. import springs as SP
        from .world import CollisionWorld
        recs = rep.get('_records') or []
        if not recs or not SP.spring_bones(self.h):
            return None
        resets = set(int(f) for f in opts.pop('resets', ()))
        resets |= set(take_resets(recs))
        resets |= set(getattr(self, '_spring_resets', ()))
        if opts.get('solver', 'three') == 'three':
            opts.setdefault('ground', self.world)
            if 'solids' not in opts:
                sc = getattr(self.world, 'scene', None) or bpy.context.scene
                try:
                    opts['solids'] = CollisionWorld(scene=sc, exclude=[o for o in sc.objects if _moves(o)])
                except ValueError:                   # no mesh in the scene but the body's own
                    opts['solids'] = None
        opts.setdefault('reset_preroll', opts.get('preroll', 1.0))
        if isinstance(rep.get('action'), dict) and rep['action'].get('name'):
            # each take's springs kept under its own name (springs.use_springs puts a take's back with its action)
            opts.setdefault('action_name', f"{rep['action']['name']}|springs")
        opts.setdefault('log', self.log)
        return SP.bake_springs(self.h, recs[0]['f'], recs[-1]['f'], resets=sorted(resets), **opts)


def _moves(o):
    """does the object move over a take: keys (an action or NLA strips), a driver or a constraint on it or on any of its
    parents"""
    while o is not None:
        ad = o.animation_data
        if ad is not None and (ad.action is not None or len(ad.nla_tracks) or len(ad.drivers)):
            return True
        if len(o.constraints):
            return True
        o = o.parent
    return False


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
    gst = {s: 0.0 for s in SIDES}                     # the walk's and the run's own stance (the ground gait's)
    wsum, gsum, ssum = 0.0, 0.0, 0.0
    lead, lead_w = None, 0.0
    gest = set(getattr(c, '_gesture_actions', {}).keys())
    for a in mx.active:
        w = a.get_effective_weight()
        if w <= 1e-4 or a.clip.slot in gest:
            continue
        wsum += w
        loop = a.loop != 'once'
        ground = a.clip.slot in ('walk', 'run')
        gsum += w if ground else 0.0
        ssum += w if a.clip.slot in STAIR_CLIPS else 0.0
        for s in SIDES:
            v = a.clip.stance_at(a.clip_time, s, loop=loop)
            st[s] += w * v
            if ground:
                gst[s] += w * v
        if w > lead_w:
            lead, lead_w = a.clip.slot, w
    if wsum > 1e-6:
        st = {s: v / wsum for s, v in st.items()}
    else:
        st = {s: 1.0 for s in SIDES}
    gst = {s: (v / gsum if gsum > 1e-6 else 1.0) for s, v in gst.items()}
    sf = c.support_frame or {}
    return {'f': f, 't': t, 'M': p.M.copy(), 'N': {k: q.copy() for k, q in p.N.items()}, 'off': p.off.copy(),
            'heading': c.scene_heading, 'mode': c.mode, 'grounded': bool(c.grounded), 'speed': c.speed_actual,
            'maneuver': getattr(c, 'maneuver_type', None) if c.mode == 'maneuver' else None,
            'stance': st, 'lead': lead, 'running': bool(getattr(c, 'running', False)),
            'ground_stance': gst, 'ground_share': (gsum / wsum) if wsum > 1e-6 else 0.0,
            'stair_share': (ssum / wsum) if wsum > 1e-6 else 0.0,
            'weights': {a.clip.slot: round(a.get_effective_weight(), 4) for a in mx.active
                        if a.get_effective_weight() > 1e-4},
            'support_mode': (sf.get('body') or {}).get('support_mode'),
            'terrain': {k: v for k, v in (sf.get('terrain') or {}).items() if k != 'small_stair_ascent_early'},
            'climb_deg': c.signed_climb_angle_deg, 'speed_scale': c.speed_scale, 'climb_blocked': bool(c._climb_blocked),
            'target_speed': getattr(c, 'target_forward_speed', None), 'smooth_speed': getattr(c, '_smooth_fwd_speed', None),
            'tread_run': c.ahead_tread_run, 'spread': c.ahead_probe_spread, 'stair_shape': c.ahead_stair_shape,
            'backward': bool(c.backward), 'feet_world': tuple(c.feet_world_position),
            'hand_contact': dict(getattr(c, 'hand_contact', None) or {}),
            'hand_cover': dict(getattr(c, 'hand_cover', None) or {}),
            'M_ik': c.pose.M.copy(), 'N_ik': {k: q.copy() for k, q in c.pose.N.items()}}


TELEPORT_SPEED = 25.0       # m/s: a root moving faster than this between two frames jumped (the fastest fall is 20)
TELEPORT_TURN = math.pi / 2  # rad: a root turning more than this in one frame jumped (an emote's facing turns 60 at most)


def take_resets(recs):
    """the frames where the take's root jumps (moved faster than TELEPORT_SPEED or turned more than TELEPORT_TURN in
    one frame: a teleport, an instant seat): the spring chains are reset there (springBoneManager.reset(), which the
    engine calls wherever it teleports a VRM, so the tails are not dragged through the body)"""
    out = []
    for a, b in zip(recs, recs[1:]):
        dt = max(1e-6, b['t'] - a['t'])
        d = (b['M'].translation - a['M'].translation).length
        turn = abs(_wrap(b['heading'] - a['heading']))
        if d > TELEPORT_SPEED * dt or turn > TELEPORT_TURN:
            out.append(b['f'])
    return out


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
