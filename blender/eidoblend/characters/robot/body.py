"""eidoblend.characters.robot.body: VRMRobotBody (eidoverse/robot_body.js), the embodied robot over a VRM, in Blender.

    from eidoblend.characters.robot import VRMRobotBody
    body = VRMRobotBody.create(me, scene, {'motion': {'start_x': 0.0, 'start_y': 0.0, 'start_heading': 0.0,
                                                      'walk_speed': 1.0}})
    def script(body):                                 # the scene's direction, as the JS awaits the body's actions
        yield body.scan_area(yaw_range=90, duration=2.0)
        yield body.walk_to(4.0, -2.0)
        yield body.perform_action('wave_goodbye', 2.0)
    body.run(script(body))                            # each yield waits for that action's outcome
    for f in range(1, 361):
        body.update((f - 1) / fps, 1 / fps)           # senses, remembers, replans, drives the legs (the frame loop)
    rep = body.bake(f0=1)                             # the whole run keyed through my body's passes

The body never sees the scene's meshes or colliders: its sensor cone (eidoblend.harness.navigation.RobotSensors, cast
from its head along the head's own direction) is its only contact with the geometry; what it sees goes into an occupancy
grid and landmarks (RobotMemory); A* (RobotPlanner) plans over that memory; the legs follow the plan
(EidoverseRobotController over RobotLegs). The head pans and nods on its own (the depth camera's mount), at headRate,
inside yawLimit / pitchLimit (which are my neck's pan and nod stops), and its gaze replaces the clip's head each frame
(the JS's _applyHeadOverride, recorded for the bake).

Actions return a Pending (the JS returns a Promise): .state 'pending' / 'resolved' / 'rejected', .error, .kind,
.then(on_ok, on_err). They resolve as frames advance in update(); body.run(generator) sequences them the way an async
scene awaits them. Everything is the JS's, name for name in snake_case (walkTo -> walk_to, scanArea -> scan_area ...).
Axes: Blender's ground plane is XY, heights are Z; a heading is radians about +Z with 0 facing -Y (where a VRM faces:
the same number as three's rotation.y), counter-clockwise; the JS's (x, z) arguments are (x, y) here.
"""

import math

from mathutils import Vector

from ...harness.navigation import RobotMemory, RobotPlanner, RobotSensors
from .controller import EidoverseRobotController, heading_vector

_VRM_CONTROLLERS = {}        # the JS's globalThis._vrmControllers: armature name -> body (seat_on and the emotes find it)


class Pending:
    """a Promise's stand-in: resolved or rejected by the body as the frames run"""

    def __init__(self, kind):
        self.kind, self.state, self.error, self.value = kind, 'pending', None, None
        self._cbs = []

    def resolve(self, value=None):
        if self.state == 'pending':
            self.state, self.value = 'resolved', value
            for ok, _err in self._cbs:
                ok and ok(value)

    def reject(self, error):
        if self.state == 'pending':
            self.state, self.error = 'rejected', error
            for _ok, err in self._cbs:
                err and err(error)

    def then(self, on_ok=None, on_err=None):
        if self.state == 'resolved':
            on_ok and on_ok(self.value)
        elif self.state == 'rejected':
            on_err and on_err(self.error)
        else:
            self._cbs.append((on_ok, on_err))
        return self

    @property
    def done(self):
        return self.state != 'pending'

    def __repr__(self):
        return f'<Pending {self.kind} {self.state}{" " + str(self.error) if self.error else ""}>'


def resolved(kind='done'):
    p = Pending(kind)
    p.resolve()
    return p


def rejected(error, kind='failed'):
    p = Pending(kind)
    p.reject(error)
    return p


class VRMRobotBody:
    """robot_body.js's VRMRobotBody. Build it with create(); call update(t, dt) once a frame; bake() at the end."""

    @classmethod
    def create(cls, h, scene=None, opts=None, rig=None):
        """create(vrm, mixer, scene, opts). opts (the JS's, snake_case): sensors (RobotSensors: h_fov, v_fov, range,
        h_rays, v_rays), memory (RobotMemory: size, cell_size, origin_x, origin_y, bayesian), motion (agent_radius,
        agent_height, walk_speed, run_speed, start_x, start_y, start_heading, max_turn_rate, collision_meshes, ground_z),
        planner (RobotPlanner: optimistic, unknown_penalty, clearance_margin, ...), head_rate, yaw_limit, pitch_limit,
        sense_period, character_controller_overrides ({'idle' | 'walk' | 'run': slot}), legs_class"""
        import bpy
        scene = scene or bpy.context.scene
        opts = dict(opts or {})
        motion = dict(opts.get('motion') or {})
        z0 = h.arm.matrix_world.translation.z
        copts = {'start_position': (motion.get('start_x', 0.0), motion.get('start_y', 0.0), z0),
                 'start_heading': motion.get('start_heading', math.pi),
                 'collision_meshes': opts.get('collision_meshes') or motion.get('collision_meshes') or [],
                 'trimesh_colliders': opts.get('trimesh_colliders', motion.get('trimesh_colliders', False)),
                 'ground_z': motion.get('ground_z', 0.0), 'max_turn_rate': motion.get('max_turn_rate'),
                 'agent_radius': 0.85 * motion.get('agent_radius', 0.35)}
        for k in ('walk_speed', 'run_speed'):
            if k in motion:
                copts[k] = motion[k]
        Ctl = opts.get('controller_class') or EidoverseRobotController
        controller = Ctl.create(h, opts.get('character_controller_overrides') or {}, copts, rig=rig,
                                legs_class=opts.get('legs_class'))
        so = dict(opts.get('sensors') or {})
        excl = list(so.pop('exclude_objects', [])) + [h.arm] + list(h.objects)
        sensors = RobotSensors(scene, exclude_objects=excl, **so)
        memory = RobotMemory(**dict(opts.get('memory') or {}))
        po = {'agent_radius': motion.get('agent_radius', 0.35), 'agent_height': motion.get('agent_height', 1.7)}
        po.update(opts.get('planner') or {})
        planner = RobotPlanner(**po)
        body = cls(h, scene, controller, sensors, memory, planner, opts)
        _VRM_CONTROLLERS[h.arm.name] = body
        return body

    def __init__(self, h, scene, controller, sensors, memory, planner, opts=None):
        opts = opts or {}
        motion = opts.get('motion') or {}
        self.vrm, self.scene, self.controller = h, scene, controller
        self.sensors, self.memory, self.planner = sensors, memory, planner
        self.agent_radius = motion.get('agent_radius', 0.35)
        self.agent_height = motion.get('agent_height', 1.7)
        self.head_rate = opts.get('head_rate', math.pi / 2)              # 90 deg/s
        self.yaw_limit = opts.get('yaw_limit', math.pi / 3)              # 60 deg: my neck's pan stop
        self.pitch_limit = opts.get('pitch_limit', math.pi / 6)          # 30 deg: my head's nod stop
        self.sense_period = opts.get('sense_period', 2)
        self._sense_phase = 0
        hb = h.humanoid.get('head')
        self.head_bone = hb
        self._head_rest = (h.rest_head[hb].copy() if hb else None)
        self._head_yaw_target = self._head_pitch_target = 0.0
        self._head_yaw_current = self._head_pitch_current = 0.0
        self._look_at_world_target = None
        self._aim_basis = None         # (the head's place, the heading) the last look-at aim was taken from
        self._pending_action = None
        self._current_path = None
        self._current_goal = None
        self._last_replan_time = -math.inf
        self._replan_cooldown = 0.4
        self._blocked_since = -1.0
        self._blocked_timeout = 1.5
        self._stall_since = -1.0
        self._stall_replanned = False
        self._scan = None
        self.last_reading = None
        self.frame_count = 0
        self._time_accum = 0.0
        self._stuck_check = None
        self._script = None
        self._waiting = None
        self._timers = []              # wait() / until(): (t, predicate, Pending)
        self.log = []                  # (t, event) for a scene's report: plans, replans, resolutions, rejections
        self.readings = []             # (frame_count, t, reading): every sense, for RobotDebug and the checks
        self.paths = []                # (frame_count, path or None): every plan and replan
        self.controller.on_pre_vrm_update = self._apply_head_override

    # ------------------------------------------------------------------------------------------------- public info
    def get_position(self):
        return self.controller.get_position()

    def get_heading(self):
        return self.controller.get_heading()

    def get_current_action(self):
        if self._pending_action:
            return self._pending_action.kind
        return self.controller.get_current_action()

    def is_moving(self):
        s = self.controller.get_state()
        return s not in ('idle', 'performing')

    def is_blocked(self):
        return self._blocked_since > 0 and (self._time_accum - self._blocked_since) > self._blocked_timeout

    def get_map(self):
        return self.memory

    def get_landmarks(self):
        return self.memory.list_landmarks()

    def tag_landmark(self, name, x, y, **opts):
        self.memory.tag_landmark(name, x, y, type=opts.get('type', 'point'), last_seen=opts.get('last_seen', self._time_accum),
                                 metadata=opts.get('metadata'))

    def forget_landmark(self, name):
        self.memory.forget_landmark(name)

    def get_head_direction(self):
        """the head's world forward: the body's heading plus the head's pan, its nod (+ looking down)"""
        hh = self.controller.heading + self._head_yaw_current
        p = self._head_pitch_current
        return Vector((math.sin(hh) * math.cos(p), -math.cos(hh) * math.cos(p), -math.sin(p)))

    def get_head_position(self):
        """the head bone's world position (its rest place carried by the body's place and heading; the clip's bob of a
        couple of cm is not in it); without a head bone, agent_height over the feet"""
        pos = self.get_position()
        if self._head_rest is None:
            return Vector((pos['x'], pos['y'], pos['z'] + self.agent_height))
        hd = self._head_rest
        f = heading_vector(self.controller.heading)
        # the rest head in the armature's frame (the VRM faces -Y): x across, -y forward
        fwd, side = -hd.y, hd.x
        return Vector((pos['x'] + f.x * fwd - f.y * side, pos['y'] + f.y * fwd + f.x * side, pos['z'] + hd.z))

    # ------------------------------------------------------------------------------------------------- actions
    def walk_to(self, x, y):
        return self._begin_go_to_action(x, y, 'walk')

    def run_to(self, x, y):
        return self._begin_go_to_action(x, y, 'run')

    def walk_to_landmark(self, name):
        lm = self.memory.get_landmark(name)
        if not lm:
            return rejected(ValueError(f'unknown landmark: {name}'), 'walking')
        return self.walk_to(lm['x'], lm['y'])

    def run_to_landmark(self, name):
        lm = self.memory.get_landmark(name)
        if not lm:
            return rejected(ValueError(f'unknown landmark: {name}'), 'running')
        return self.run_to(lm['x'], lm['y'])

    def _begin_go_to_action(self, x, y, mode):
        self._cancel_pending_action('superseded')
        pos = self.get_position()
        path = self.planner.find_path(self.memory, pos['x'], pos['y'], x, y)
        self.paths.append((self.frame_count, path))
        if not path:
            self.log.append((self._time_accum, f'no path from ({pos["x"]:.2f},{pos["y"]:.2f}) to ({x:.2f},{y:.2f})'))
            return rejected(RuntimeError(f'no path from ({pos["x"]:.2f},{pos["y"]:.2f}) to ({x:.2f},{y:.2f})'), mode)
        wps = [{'x': p['x'], 'y': p['y'], 'action': mode} for p in path[1:]]
        if not wps:
            return resolved(mode)
        self.controller.set_waypoints(wps)
        self._current_path = path
        self._current_goal = {'x': x, 'y': y, 'mode': mode}
        self._blocked_since = -1.0
        self._stall_since = -1.0
        self._stall_replanned = False
        p = Pending('running' if mode == 'run' else 'walking')
        p.mode = mode
        self._pending_action = p
        self.log.append((self._time_accum, f'{mode}_to ({x:.2f},{y:.2f}): {len(path)} waypoints'))
        return p

    def look_at(self, x, y, z, hold=False, instant=False):
        """turn the head to face a world point; resolves within ~3 deg (0.05 rad). hold keeps tracking it after"""
        self._look_at_world_target = Vector((x, y, z))
        if instant:
            self._update_head_target_from_look_at()
            self._head_yaw_current = self._head_yaw_target
            self._head_pitch_current = self._head_pitch_target
            return resolved('lookingAt')
        self._cancel_pending_action('superseded')
        p = Pending('lookingAt')
        p.hold = bool(hold)
        self._pending_action = p
        return p

    def look_forward(self):
        self._look_at_world_target = None
        self._head_yaw_target = 0.0
        self._head_pitch_target = 0.0

    def face_direction(self, heading):
        """the whole body to a heading (rad, 0 faces -Y). The JS snaps the controller's heading (its own note: the
        standing turn would need the waypoint state machine); so does this, and the bake turns the standing body round
        over its crossfade (a turn in place on the turn clips is not built)"""
        self._cancel_pending_action('superseded')
        d = (heading - self.controller.heading + math.pi) % (2 * math.pi) - math.pi
        if abs(d) < 0.05:
            return resolved('turning')
        self.controller.heading = heading
        return resolved('turning')

    def scan_area(self, yaw_range=90.0, duration=1.5, center_yaw=0.0, passes=1, pitch_range=0.0):
        """a smooth head sweep over yaw_range deg about the body's forward (center_yaw rad off it), `passes` times,
        without turning the body (the walk stops while it scans)"""
        self._cancel_pending_action('superseded')
        self._scan = {'start_time': self._time_accum, 'duration': duration, 'yaw_half': math.radians(yaw_range) / 2,
                      'center_yaw': center_yaw, 'passes': passes}
        self.controller.set_waypoints([])
        self._look_at_world_target = None
        p = Pending('scanning')
        p._scan_done = False
        self._pending_action = p
        return p

    def perform_action(self, clip_name, duration=None):
        """a canned clip on the controller (force_action): a VRMA slot of the clip library"""
        self._cancel_pending_action('superseded')
        from ..vrma import vrma_path
        try:
            vrma_path(clip_name)
        except FileNotFoundError:
            return rejected(ValueError(f'unknown clip: {clip_name}'), 'performing')
        p = Pending('performing')
        self._pending_action = p
        ok = self.controller.force_action(clip_name, duration)
        if ok is False and self._pending_action is p:
            self._pending_action = None
            p.reject(RuntimeError(f'clip failed to play: {clip_name}'))
        return p

    # parkour, passed through to the legs as the JS passes it to the engine's charCtrl: the move ahead along the heading,
    # played by the controller family's VRMCharacterController from where I stand (RobotLegs._start_maneuver) -> True
    # when it started (False: nothing it fits ahead, or moving: a move starts from standing here). It lasts while
    # is_maneuvering(); the body senses on from where the move carries it
    def vault(self):
        return self.controller.vault()

    def jump(self, opts=None):
        """opts: {'distance': m, 'height': m} (1.4 and 0.45 by default)"""
        return self.controller.jump(opts)

    def climb_ledge(self):
        return self.controller.climb_ledge()

    def climb_ladder(self, opts=None):
        """opts: {'height', 'rate', 'firstRung', 'rungSpacing', 'timeScale'} (snake_case keys too)"""
        return self.controller.climb_ladder(opts)

    def set_running(self, v):
        self.controller.set_running(v)

    def is_maneuvering(self):
        return bool(self.controller.is_maneuvering)

    def begin_seated(self, slot='stand_to_sit', **opts):
        """the SEATED state: the seated clip plays (and holds) where the body stands; the caller owns the root's place
        (the JS's seatOn raycasts the seat: not ported here)"""
        return self.controller.begin_seated(slot, opts)

    def stand_up(self, slot='sit_to_stand', **opts):
        return self.controller.end_seated(slot, opts)

    def set_emote_facing(self, ry):
        """aim STANDING emotes (perform_action) at a fixed world heading (rad, 0 faces -Y), as the JS sets the engine
        controller's _emoteFacingY: the body steps round to it as the emote starts and back to its own heading after.
        None restores the default (the body's heading). Locomotion and the seated facing are not affected"""
        legs = self.controller.char_ctrl
        legs._emote_facing = ry

    def stop(self):
        self._cancel_pending_action('stopped')
        self.controller.set_waypoints([])
        self._scan = None
        self._current_path = None
        self._current_goal = None

    def _cancel_pending_action(self, reason):
        if not self._pending_action:
            return
        a = self._pending_action
        self._pending_action = None
        a.reject(RuntimeError(f'action {a.kind} {reason}'))

    # ------------------------------------------------------------------------------------------------- sensing
    def observe(self):
        return self.last_reading

    def can_see(self, x, y, z):
        """is a world point inside the sensor cone and not occluded"""
        hp = self.get_head_position()
        d = Vector((x, y, z)) - hp
        dist = d.length
        if dist > self.sensors.range:
            return False
        d.normalize()
        half = max(self.sensors.h_fov, self.sensors.v_fov) / 2
        if self.get_head_direction().dot(d) < math.cos(half):
            return False
        r = self.sensors.cast_one(hp, d, dist)
        return not r or not r['hit'] or r['distance'] >= dist - 0.05

    def distance_to(self, x, y):
        p = self.get_position()
        return math.hypot(x - p['x'], y - p['y'])

    def path_to(self, x, y):
        p = self.get_position()
        return self.planner.find_path(self.memory, p['x'], p['y'], x, y)

    # ------------------------------------------------------------------------------------------------- the frame
    def run(self, script):
        """drive a generator of actions (yield an action: the script resumes with it once it resolves or rejects; its
        outcome is the yield's value). The JS scene's `await body.walkTo(...)`, frame-stepped"""
        self._script = script
        self._step_script(None)

    def wait(self, seconds):
        """a Pending that resolves `seconds` on (a JS scene's `await sleep(ms)`): `yield body.wait(0.5)` in a script"""
        p = Pending('waiting')
        self._timers.append((self._time_accum + seconds, None, p))
        return p

    def until(self, predicate):
        """a Pending that resolves on the first update where predicate() is true: `yield body.until(lambda: not
        body.is_maneuvering())` waits out a move"""
        p = Pending('waiting')
        self._timers.append((None, predicate, p))
        return p

    def _resolve_timers(self, t):
        keep = []
        for until_t, pred, p in self._timers:
            if p.done:
                continue
            if (until_t is not None and t >= until_t - 1e-9) or (pred is not None and pred()):
                p.resolve()
            else:
                keep.append((until_t, pred, p))
        self._timers = keep

    def _step_script(self, last):
        if self._script is None:
            return
        try:
            nxt = self._script.send(last) if last is not None else next(self._script)
        except StopIteration:
            self._script = None
            self._waiting = None
            return
        self._waiting = nxt

    def _poll_script(self):
        for _ in range(32):                          # actions that resolve at once chain within the frame
            if self._script is None or self._waiting is None or not self._waiting.done:
                return
            w = self._waiting
            self._waiting = None
            self._step_script(w)

    def update(self, t, dt):
        self._time_accum = t
        self.frame_count += 1
        if self._timers:
            self._resolve_timers(t)
        if self._scan:
            self._update_scan()
        if self._look_at_world_target is not None:
            self._update_head_target_from_look_at()
        elif not self._scan:
            self._head_yaw_target = 0.0
            self._head_pitch_target = 0.0
        mx = self.head_rate * dt
        self._head_yaw_current += max(-mx, min(mx, self._head_yaw_target - self._head_yaw_current))
        self._head_pitch_current += max(-mx, min(mx, self._head_pitch_target - self._head_pitch_current))
        self._head_yaw_current = max(-self.yaw_limit, min(self.yaw_limit, self._head_yaw_current))
        self._head_pitch_current = max(-self.pitch_limit, min(self.pitch_limit, self._head_pitch_current))
        pos = self.get_position()
        should = (self._sense_phase % self.sense_period) == 0
        self._sense_phase += 1
        if should:
            hp = self.get_head_position()
            reading = self.sensors.sense(hp, self.controller.heading + self._head_yaw_current, self._head_pitch_current)
            self.last_reading = reading
            self.readings.append((self.frame_count, t, reading))
            self.memory.apply_sensor_reading(reading, floor_z=pos['z'], agent_height=self.agent_height)
        self.memory.mark_standing_footprint(pos['x'], pos['y'], self.agent_radius * 1.2, pos['z'])
        if self._current_path and self._current_goal and (t - self._last_replan_time) > self._replan_cooldown:
            if self.planner.is_path_blocked(self.memory, self._remaining_path(pos)):
                self._replan(t, 'the route ahead is blocked in the memory')
        self._check_stuck(t, dt)
        self.controller.update(t, dt)
        self._resolve_pending_action()
        self._poll_script()

    def _update_scan(self):
        s = self._scan
        u = min((self._time_accum - s['start_time']) / s['duration'], 1.0)
        phase = u * s['passes']
        tri = 1 - 2 * abs((phase * 2) % 2 - 1)
        self._head_yaw_target = s['center_yaw'] + tri * s['yaw_half']
        self._head_pitch_target = 0.0
        if u >= 1:
            self._scan = None
            self._head_yaw_target = 0.0
            if self._pending_action and self._pending_action.kind == 'scanning':
                self._pending_action._scan_done = True

    def _update_head_target_from_look_at(self):
        hp = self.get_head_position()
        d = self._look_at_world_target - hp
        hh = self.controller.heading
        f = heading_vector(hh)                 # the body's forward on the ground
        left = Vector((-f.y, f.x))             # (the VRM's own +X after the heading: its left)
        lz = d.x * f.x + d.y * f.y             # along the body's forward
        lx = d.x * left.x + d.y * left.y       # toward its left
        yaw = math.atan2(lx, lz)
        pitch = -math.atan2(d.z, math.hypot(lx, lz))     # below the head looks down: + (as the JS)
        self._head_yaw_target = max(-self.yaw_limit, min(self.yaw_limit, yaw))
        self._head_pitch_target = max(-self.pitch_limit, min(self.pitch_limit, pitch))
        self._aim_basis = (hp.copy(), hh)

    def _apply_head_override(self, dt):
        """the head's turn REPLACED by (yaw, pitch) each frame: recorded on the legs' frame for the bake (rig.apply_gaze
        splits it onto my neck's pan and my head's nod). With a look-at target the frame also records the target and the
        head's place and heading the aim was taken from: the keyed body can stand a little off the live one (a walk's
        stop lands on a mid-stance at the goal, the live run stops within arrive_radius), and the bake re-aims the head
        from where the keyed body really is (bake._aimed_gaze), as the JS aims it from the head it renders"""
        if self.head_bone is None:
            return
        legs = self.controller.char_ctrl
        if hasattr(legs, 'set_gaze'):
            look = None
            if self._look_at_world_target is not None and self._aim_basis is not None:
                look = (self._look_at_world_target.copy(), self._aim_basis[0], self._aim_basis[1], self.yaw_limit,
                        self.pitch_limit)
            try:
                legs.set_gaze(self._head_yaw_current, self._head_pitch_current, look=look)
            except TypeError:                         # a legs_class whose set_gaze takes the gaze alone
                legs.set_gaze(self._head_yaw_current, self._head_pitch_current)

    def _remaining_path(self, pos):
        if not self._current_path:
            return []
        best_i, best_d = 0, math.inf
        for i, p in enumerate(self._current_path):
            d = (p['x'] - pos['x']) ** 2 + (p['y'] - pos['y']) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return self._current_path[best_i:]

    def _replan(self, t, why='replan'):
        if not self._current_goal:
            return
        pos = self.get_position()
        g = self._current_goal
        new = self.planner.find_path(self.memory, pos['x'], pos['y'], g['x'], g['y'])
        self._last_replan_time = t
        self.paths.append((self.frame_count, new))
        if not new:
            self.log.append((t, f'replan ({why}): goal unreachable'))
            if self._pending_action:
                self._pending_action.reject(RuntimeError('replan: goal unreachable'))
                self._pending_action = None
            self.controller.set_waypoints([])
            self._current_path = None
            self._current_goal = None
            return
        self.log.append((t, f'replan ({why}): {len(new)} waypoints'))
        self._current_path = new
        self.controller.set_waypoints([{'x': p['x'], 'y': p['y'], 'action': g['mode']} for p in new[1:]])
        self._blocked_since = -1.0

    def _check_stuck(self, t, dt):
        if self._stuck_check is None:
            self._stuck_check = {'last_pos': self.get_position(), 'last_time': t}
            return
        pa = self._pending_action
        if pa and pa.kind in ('walking', 'running') and self.controller.is_stalled():
            if self._stall_since < 0:
                self._stall_since = t
            if not self._stall_replanned and (t - self._last_replan_time) > self._replan_cooldown:
                self._stall_replanned = True
                self._replan(t, 'a collision stall')
            elif t - self._stall_since >= self._blocked_timeout:
                p, g = self.get_position(), self._current_goal
                self._pending_action = None
                self.controller.set_waypoints([])
                self._current_path = None
                self._current_goal = None
                self._stall_since = -1.0
                self._stall_replanned = False
                msg = (f'blocked: collision stall at ({p["x"]:.2f},{p["y"]:.2f})'
                       + (f' short of ({g["x"]:.2f},{g["y"]:.2f})' if g else '')
                       + f' for {self._blocked_timeout}s after replanning')
                self.log.append((t, msg))
                pa.reject(RuntimeError(msg))
            return
        pos = self.get_position()
        lp = self._stuck_check['last_pos']
        moved = math.hypot(pos['x'] - lp['x'], pos['y'] - lp['y'])
        dt_ = t - self._stuck_check['last_time']
        if dt_ < 0.5:
            return
        speed = moved / dt_
        expected = (self.controller.run_speed if self._current_goal and self._current_goal['mode'] == 'run'
                    else self.controller.walk_speed) * 0.3
        st = self.controller.get_state()
        moving = st in ('walking', 'running')
        if moving and speed < expected:
            if self._blocked_since < 0:
                self._blocked_since = t
            if (t - self._last_replan_time) > self._replan_cooldown:
                self._replan(t, 'no progress')
        else:
            self._blocked_since = -1.0
            if moving:
                self._stall_since = -1.0
                self._stall_replanned = False
        self._stuck_check = {'last_pos': pos, 'last_time': t}

    def _resolve_pending_action(self):
        a = self._pending_action
        if not a:
            return
        cs = self.controller.get_state()
        if a.kind in ('walking', 'running'):
            if cs == 'idle' and self.controller.waypoint_index >= len(self.controller.waypoints):
                self._pending_action = None
                self._current_path = None
                self._current_goal = None
                self.log.append((self._time_accum, f'arrived ({a.kind})'))
                a.resolve()
        elif a.kind == 'lookingAt':
            if (abs(self._head_yaw_target - self._head_yaw_current) < 0.05
                    and abs(self._head_pitch_target - self._head_pitch_current) < 0.05):
                self._pending_action = None
                a.resolve()
                if not getattr(a, 'hold', False):
                    self._look_at_world_target = None
        elif a.kind == 'scanning':
            if getattr(a, '_scan_done', False) and abs(self._head_yaw_current) < 0.05:
                self._pending_action = None
                a.resolve()
        elif a.kind == 'performing':
            if cs != 'performing':
                self._pending_action = None
                a.resolve()

    # ------------------------------------------------------------------------------------------------- the film
    def bake(self, **kw):
        """the whole run keyed (RobotLegs.bake: walk_path for the walks, the example's frame order for the rest)"""
        return self.controller.bake(**kw)
