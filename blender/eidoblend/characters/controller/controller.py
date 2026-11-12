"""eidoblend.characters.controller.controller: VRMCharacterController (character_controller.js), ported.

The WebGPU controller is a per-frame runtime: an upper-body cylinder on a kinematic body slides along walls, the body's
height comes from ground probes under the two feet and ahead of them (stairs and ramps are classified from those probes),
the clips blend by what the terrain and the speed say, and the foot IK plants the feet. Here the same object runs frame
by frame at build time and the bake (film.py) keys what it did:

    from eidoblend.characters.controller import VRMCharacterController, CollisionWorld
    world = CollisionWorld()                                 # every visible mesh that is not a skinned VRM
    ctrl = VRMCharacterController(me, world, start_position=(0, 0, 0), start_heading=math.pi, enable_turning=True)
    ctrl.load_standard_animations()                          # walk, run, idle, stairs x4, fallIdle, the maneuver clips
    ctrl.attach_locomotion(leg_ik=VRMFootControllerIK(...))  # or leg_ik='default': the terrain_base set-up
    ctrl.locomote(1 / 30, (0.0, 1.0))                        # one frame: a direction of travel (world x, y)
    ctrl.pose                                                # the frame's Pose: root matrix + normalized bones

Names are the original's in snake_case (attachLocomotion -> attach_locomotion, feetWorldPosition ->
feet_world_position, the constructor's and attachLocomotion's options too: footStanceX -> foot_stance_x ...), defaults
unchanged unless said here. Blender's axes: three (x, y, z) -> (x, -z, y); a heading is the same angle as three's
rotation.y (about the up axis, 0 faces -Y in Blender: the VRM as imported; math.pi faces +Y, the WebGPU default). The
input of update() is a velocity (m/s), of locomote() a direction: both are world (x, y) here, three's {x, z} being (x, -z).

What the WebGPU world gives that Blender has not, and what stands in:
  Rapier kinematic body + cylinder   self._center (the cylinder's centre); the move-and-slide against walls is
                                     CollisionWorld.move_and_slide (rays from the cylinder's axis), Y = 0 as the original
  castShape ball probes              CollisionWorld.ground_vector (a 1 cm ball emulated with rays, its contact z)
  THREE.AnimationMixer               mixer.AnimationMixer (same weights, fades, loops, blend order)
  the scene graph                    pose.Pose (the root's matrix and the normalized bones)

Additions of this edition, each an option that is off or neutral unless asked (film.py turns them on for a bake):
  gait_sync='stride'      the original: the ground gait's timeScale = speed / native speed. 'distance': the clip's phase
                          from the ground covered (distance matching: walk and run share one phase, aligned on the left
                          strike; the stairs one cycle per two treads, anchored at the first edge, any shape, both ways,
                          on the half nearest the walk's phase where the stair clip takes over the blend; a stair clip
                          not playing held at the shared phase; while stair clips carry weight the phase goes on at the
                          blend's pace, and off a flight the stride grows back over about a step; while a stair clip
                          leads, the walk's phase follows it, so a hand-back keeps the same foot down)
  native_walk_speed / native_run_speed=None   measured on this body (the clip's stride / its duration); the WebGPU
                          numbers (1.5, 3.6) were tuned on Aletheia
  land_on_contact         a body already in the air lands when its feet reach the ground
  ground_past_steep       the support probes under the feet look past a face too steep to stand on to the walkable
                          surface under it (the original finds no ground there: the far side of a dome is a take-off)
  turn_on_spot(angle)     a turn on the spot plays turnLeft / turnRight, the root taking the clip's hips yaw (scaled to
                          the angle asked); the original never plays these clips
  seat_dz                 while seated the root rises or sinks by it (the film's sit(seat=...): seatOn's settle)
  maneuver_planners / maneuvers   the maneuver engine (_start_maneuver, _update_maneuver, _end_maneuver, the path
                          sampling and scans) is here; the moves themselves (vault, climbLedge, jump, climbLadder,
                          climbWall and their contact IK) register into ctrl.maneuvers (maneuvers.py)
  maneuver_feet_out_of_solids (on) / contact_world   the last pass of every maneuver frame: no foot inside a solid
                          of contact_world (default the walking world)
"""

import math

from mathutils import Quaternion, Vector

from ..ground import SIDES
from ..locomotion import Body
from . import clips as C
from . import maneuvers as MV
from .foot_ik import VRMFootControllerIK, CastType
from .mixer import AnimationMixer, LOOP_ONCE, LOOP_REPEAT, damp, euclidean_modulo, lerp
from .pose import Pose, humanoid_parents, root_matrix

D2R = math.pi / 180.0
R2D = 180.0 / math.pi
FOLLOW_UNDER = 0.1          # the walk's and run's weight under which their phase follows a leading stair clip
STAIR_REST_UNDER = 1e-3     # a stair clip's weight under which it is not playing: held at the shared phase
STRIDE_GROWTH = 1.5         # m of stride per m walked: off a flight the stride grows back to the gait's own (about a step)


def _wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _xy(v):
    if v is None:
        return 0.0, 0.0
    if isinstance(v, dict):
        return float(v.get('x', 0.0)), float(v.get('y', 0.0))
    return float(v[0]), float(v[1])


def _sign(x):
    return (x > 0) - (x < 0)


PRESETS = {
    # robot_controller.js (EidoverseRobotController.create, the robot body's walks): the defaults, turning on
    'robot': {'enable_turning': True, 'start_heading': math.pi},
    # terrain_base.js (the WebGPU locomotion bench and examples/obstacle_course.js run on it). Its constructor call also
    # passes requireConfirmedStairClips / confirmedStairHoldFrames, which only attachLocomotion reads: unread there, so
    # unread here too (pass them to attach_locomotion to use them)
    'terrain_base': {
        'foot_stance_x': 0.11,
        'use_contact_support_lift': True, 'contact_support_lift_min': 0.025, 'contact_support_lift_max': 0.18,
        'contact_support_lift_ratio': 0.58, 'contact_support_swing_ratio': 0.32, 'contact_support_max_ramp_angle': 50,
        'use_ik_contact_support_lift': True, 'ik_contact_support_lift_ratio': 0.42, 'ik_contact_support_swing_ratio': 0.18,
        'ik_contact_sole_gap_max': 0.16,
        'allow_raised_support_during_descent': True, 'raised_support_min_lift': 0.045, 'raised_support_ahead_min': 0.035,
        'raised_support_finish_gap': 0.015, 'raised_support_latch_frames': 3, 'raised_support_max_spread': 0.18,
        'use_ik_grounding_grace': True, 'ik_grounding_grace_max_drop': 0.34, 'ik_grounding_grace_max_rise': 0.08,
        'ik_grounding_grace_max_sole_gap': 0.56,
        'prefer_walk_on_untreaded_obstacles': True, 'obstacle_walk_max_rise': 0.18, 'obstacle_walk_max_spread': 0.18,
        'require_confirmed_stair_clips': True, 'confirmed_stair_hold_frames': 12,
        'body_y_rate_up': 1.35, 'body_y_rate_down': 1.25, 'y_average_window_size': 3,
    },
}


def measure_vrm(h, body):
    """the original's constructor measures: the VRM's height and its lowest point (bbox), the hips' rest height over it.
    Measured AT REST (the armature's rest position, whatever its pose, action or NLA plays now), as the engine measures
    a VRM it has just loaded: a controller built while the armature played a ground sit ran its whole take ~0.4 m off."""
    import bpy
    import numpy as np
    arm = h.arm.data
    pose0 = arm.pose_position
    if pose0 != 'REST':
        arm.pose_position = 'REST'
        bpy.context.view_layer.update()
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        inv = h.arm.matrix_world.inverted()
        zmin, zmax = math.inf, -math.inf
        for o in h.meshes:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            n = len(me.vertices)
            if n:
                co = np.empty(n * 3)
                me.vertices.foreach_get('co', co)
                M = np.array(inv @ o.matrix_world)
                z = co.reshape(-1, 3) @ M[2, :3] + M[2, 3]
                zmin, zmax = min(zmin, float(z.min())), max(zmax, float(z.max()))
            ev.to_mesh_clear()
    finally:
        if pose0 != 'REST':
            arm.pose_position = pose0
            bpy.context.view_layer.update()
    return zmax - zmin, zmin, body.H['hips'].z - zmin


def _lower(pose, dz):
    t = pose.M.translation.copy()
    t.z -= dz
    pose.M.translation = t
    pose.invalidate()


class VRMCharacterController:
    def __init__(self, h, world, body=None, **opts):
        self.h = h
        self.world = world
        self.body = body or Body(h)
        if not hasattr(self.body, 'parents'):
            self.body.parents = humanoid_parents(h)
        self.opts = opts
        if 'hips' not in h.humanoid:
            raise ValueError('[eidoverse-controller] vrm.humanoid hips bone missing')
        vrm_height, vrm_foot_y, hip_y = measure_vrm(h, self.body)
        upper = vrm_height - hip_y
        half_h = upper / 2.0
        radius = opts.get('cylinder_radius', 0.22)
        center_above_feet = hip_y + half_h
        self.vrm_height, self.vrm_foot_y, self.hip_y = vrm_height, vrm_foot_y, hip_y
        self.half_height, self.radius = half_h, radius
        self.foot_stance_x = opts.get('foot_stance_x', 0.11)
        self.max_turn_rate = opts.get('max_turn_rate', 3.5)
        self.max_fall_speed = opts.get('max_fall_speed', 20.0)
        self.gravity = opts.get('gravity', -9.81)
        start = opts.get('start_position', (0.0, 0.0, 0.0))
        self._center = Vector((start[0], start[1], start[2] + center_above_feet))
        self.skin = opts.get('skin', 0.05)
        self.max_slope = opts.get('max_slope', 60)
        self._velocity_y = 0.0
        self._last_x, self._last_y = start[0], start[1]
        self._turning_enabled = opts.get('enable_turning', False) is True
        self._heading = opts.get('start_heading', math.pi)
        self.grounded = False
        self.ground_y = -math.inf
        self.speed_actual = 0.0
        self.support_frame = None
        self.external_ground_y = None
        self._foot_support_observation = None
        self._use_foot_support_for_root = False
        self._foot_support_root_stable_frames = 4
        self._foot_support_root_max_delta = 0.08
        self._foot_support_stable_frames = 0
        self._last_foot_support_y = None
        self.fall_threshold = opts.get('fall_threshold', 0.4)
        self.max_climb_angle = opts.get('max_climb_angle', 50)
        self.look_ahead = opts.get('look_ahead', 0.35)
        self.small_stair_ascent_early_look_ahead = opts.get('small_stair_ascent_early_look_ahead', 0.76)
        self.small_stair_ascent_early_probe_count = opts.get('small_stair_ascent_early_probe_count', 36)
        self.small_stair_ascent_early_min_positive_edges = opts.get('small_stair_ascent_early_min_positive_edges', 2)
        self.small_stair_ascent_early_max_negative_edges = opts.get('small_stair_ascent_early_max_negative_edges', 0)
        self.small_stair_ascent_early_hold_frames = opts.get('small_stair_ascent_early_hold_frames', 8)
        self._small_stair_ascent_early_frames = 0
        self.small_stair_ascent_early_up = False
        self.small_stair_ascent_early_info = None
        self.body_y_rate_down = opts.get('body_y_rate_down', 1.2)
        self.body_y_rate_up = opts.get('body_y_rate_up', 1.5)
        self.body_y_damp_hz = opts.get('body_y_damp_hz', 60)              # legacy (unused by the original's update)
        self.body_y_damp_hz_up = opts.get('body_y_damp_hz_up', 30)        # legacy
        self.use_contact_support_lift = opts.get('use_contact_support_lift', False)
        self.contact_support_lift_min = opts.get('contact_support_lift_min', 0.025)
        self.contact_support_lift_max = opts.get('contact_support_lift_max', 0.18)
        self.contact_support_lift_ratio = opts.get('contact_support_lift_ratio', 0.55)
        self.contact_support_swing_ratio = opts.get('contact_support_swing_ratio', 0.30)
        self.contact_support_max_ramp_angle = opts.get('contact_support_max_ramp_angle', 12)
        self.use_ik_contact_support_lift = opts.get('use_ik_contact_support_lift', False)
        self.ik_contact_support_lift_ratio = opts.get('ik_contact_support_lift_ratio', 0.42)
        self.ik_contact_support_swing_ratio = opts.get('ik_contact_support_swing_ratio', 0.18)
        self.ik_contact_sole_gap_max = opts.get('ik_contact_sole_gap_max', 0.16)
        self.allow_raised_support_during_descent = opts.get('allow_raised_support_during_descent', False)
        self.raised_support_min_lift = opts.get('raised_support_min_lift', 0.045)
        self.raised_support_ahead_min = opts.get('raised_support_ahead_min', 0.035)
        self.raised_support_finish_gap = opts.get('raised_support_finish_gap', 0.015)
        self.raised_support_latch_frames = opts.get('raised_support_latch_frames', 3)
        self.raised_support_max_spread = opts.get('raised_support_max_spread', 0.18)
        self._raised_support_descent_latch = 0
        self.use_ik_grounding_grace = opts.get('use_ik_grounding_grace', False)
        self.ik_grounding_grace_max_drop = opts.get('ik_grounding_grace_max_drop', 0.34)
        self.ik_grounding_grace_max_rise = opts.get('ik_grounding_grace_max_rise', 0.08)
        self.ik_grounding_grace_max_sole_gap = opts.get('ik_grounding_grace_max_sole_gap', 0.56)
        self.prefer_walk_on_untreaded_obstacles = opts.get('prefer_walk_on_untreaded_obstacles', False)
        self.obstacle_walk_max_rise = opts.get('obstacle_walk_max_rise', 0.18)
        self.obstacle_walk_max_spread = opts.get('obstacle_walk_max_spread', 0.18)
        self.prefer_walk_on_isolated_obstacles = opts.get('prefer_walk_on_isolated_obstacles', True)
        self._isolated_obstacle_sign_hold_frames = opts.get('isolated_obstacle_sign_hold_frames', 14)
        self._isolated_obstacle_context_hold_frames = opts.get('isolated_obstacle_context_hold_frames', 8)
        self._recent_positive_step_frames = 0
        self._recent_negative_step_frames = 0
        self._isolated_obstacle_frames = 0
        self.stair_lift_trigger = opts.get('stair_lift_trigger', 0.05)        # declared, never read by the original
        self.ahead_probe_count = opts.get('ahead_probe_count', 25)
        self.forward_bias = opts.get('forward_bias', 0.5)
        self.body_anticipation_clearance = opts.get('body_anticipation_clearance', 0.05)   # declared, never read
        self.min_stair_speed_scale = opts.get('min_stair_speed_scale', 0.37)             # declared, never read
        # maneuvers (the engine here; the moves register into self.maneuvers)
        self.auto_maneuvers = opts.get('auto_maneuvers', True)
        self.vault_min_rise = opts.get('vault_min_rise', 0.42)
        self.vault_max_rise = opts.get('vault_max_rise', 1.15)
        self.vault_max_depth = opts.get('vault_max_depth', 1.00)
        self.mount_max_rise = opts.get('mount_max_rise', 1.35)
        self.wall_climb_max_rise = opts.get('wall_climb_max_rise', 2.30)
        self.wall_scramble_max_rise = opts.get('wall_scramble_max_rise', 4.5)
        self.jump_auto_gap = opts.get('jump_auto_gap', True)
        self.jump_max_gap = opts.get('jump_max_gap', 2.20)
        self.maneuver_scan_range = opts.get('maneuver_scan_range', 2.6)
        self.maneuver_scan_step = opts.get('maneuver_scan_step', 0.15)
        self.maneuver_clearance = opts.get('maneuver_clearance', 0.16)
        self.maneuver_cooldown = opts.get('maneuver_cooldown', 0.5)
        self.fall_land_min_drop = opts.get('fall_land_min_drop', 0.85)
        self._maneuver = None
        self._maneuver_cooldown_t = 0.0
        self._fading_maneuver_action = None
        self._airborne_from_y = None
        self._airborne_time = 0.0
        self._maneuver_visual_sink = 0.0
        # the auto-trigger's moves by name (maneuvers.py: vault, mount, wall_scramble, gap_jump), extra planners, and the
        # contact IK by grab type ('climb', 'vaultGeo', 'ladder'); replace or extend any of them
        self.maneuvers = dict(MV.AUTO)      # name -> callable(ctrl, scan, obstacle_or_gap, fx, fy[, slot]) -> bool
        self.maneuver_planners = []         # extra auto-trigger planners: callable(ctrl, fx, fy, speed) -> bool
        self.maneuver_hand_ik = dict(MV.HAND_IK)   # grab type -> callable(ctrl, m, u): a maneuver's contact IK
        # this edition's: after the contact IK, no foot inside the world's solids (maneuvers.feet_out_of_solids)
        self.maneuver_feet_out_of_solids = opts.get('maneuver_feet_out_of_solids', True)
        self.contact_world = opts.get('contact_world')    # the solids for that pass (default: the walking world)
        self._body_y_target = start[2] + center_above_feet
        self._y_avg_window = []
        self._y_avg_size = opts.get('y_average_window_size', 4)
        self.walk_speed = opts.get('walk_speed')                 # passed through by the robot adapter, unread
        self.run_speed = opts.get('run_speed')
        # attachLocomotion's state (read by update() before attach in the original as undefined)
        self._stair_spread_threshold = None
        self._stair_discontinuity_threshold = None
        self._max_stair_transitions_in_look_ahead = None
        self._stair_residual_limit = None
        self._min_stair_rise = None
        self._tread_run_memory_frames = None
        self._stair_shape_memory_frames = None
        self._latched_stair_rise = 0.0
        self._latched_stair_shape = None
        self._stair_shape_miss_frames = 999
        self._last_tread_run = None
        self._last_tread_run_age = 999
        self._no_step_evidence_frames = 999
        self._blocked_frames = 0
        self._smooth_speed_scale = None
        self._last_valid_ground_y = None
        self._ground_stale_frames = 0
        self._prior_ik_support_contacts = None
        self._prior_foot_contact_state = None
        self.ahead_probe_spread = 0.0
        self.ahead_step_like = False
        self.ahead_smooth_ramp_like = False
        self.ahead_transition_count = 0
        self.ahead_probe_residual = 0.0
        self.ahead_step_rise_raw = 0.0
        self.ahead_isolated_obstacle = False
        self.ahead_stair_rise = 0.0
        self.ahead_stair_shape = None
        self.ahead_tread_run = None
        self.ahead_lowest_delta = 0.0
        self.ahead_highest_delta = 0.0
        self.climb_angle_deg = 0.0
        self.signed_climb_angle_deg = 0.0
        self.speed_scale = 1.0
        self._climb_blocked = False
        self._feet_world = Vector((start[0], start[1], start[2]))
        # this edition's
        self.gait_sync = opts.get('gait_sync', 'stride')
        self.backward = bool(opts.get('backward', False))   # walk backward: face away from the travel, the clip reversed
        self.land_on_contact = bool(opts.get('land_on_contact', False))   # a fall lands when the feet reach the ground
        self.ground_past_steep = bool(opts.get('ground_past_steep', False))   # a side hit looked past to the ground
        self.mode = 'loco'                  # what the last frame did: loco | emote | seated | turn | maneuver
        self.time = 0.0
        self.pose = Pose(self.body, root_matrix(start[0], start[1], start[2], self._heading), {})
        self.anim_pose = None
        self.scene_heading = self._heading if self._turning_enabled else math.pi
        self._mixer = None
        self._actions = {}
        self._clips = {}
        self._leg_ik = None
        self._turn = None
        self.log = opts.get('log', print)
        self.log(f'[eidoverse-controller] hipY={hip_y:.3f} upperHeight={upper:.3f} halfHeight={half_h:.3f} '
                 f'radius={radius:.3f}')

    # ================================================================================================ physics
    def body_translation(self):
        return self._center.copy()

    @property
    def feet_world_position(self):
        return self._feet_world.copy()

    def _ground_vector(self, x, y, origin_z, past_steep=False):
        """_groundVector: a 1 cm ball dropped from (x, y, origin_z): the contact's z, or None (nothing, or a side hit).
        past_steep (this edition's ground_past_steep, for the two support probes under the feet only): a side hit is
        looked past, down a ray, to the first walkable surface under it (the floor beyond a dome's or a boulder's steep
        far side: a step down, where the original finds no ground and the body takes off). The probes ahead keep the
        original's answer: a ramp box's steep front edge read past would be a step and the ramp a stair"""
        z = self.world.ground_vector(x, y, origin_z, radius=0.01, min_normal=0.5, max_dist=2000.0)
        if z is not None or not past_steep:
            return z
        o = Vector((x, y, origin_z))
        for _ in range(8):
            h = self.world.ray_cast(o, Vector((0.0, 0.0, -1.0)), 2000.0)
            if not h.hit:
                return None
            if h.normal.z >= 0.5:
                return h.point.z
            o = h.point - Vector((0.0, 0.0, 0.002))
        return None

    def update(self, dt, input=None):
        """the original's update(dt, {x, z}): input a velocity (world x, y in m/s)"""
        cur = self._center.copy()
        in_x, in_y = _xy(input)
        flat_len = math.hypot(in_x, in_y)
        if self._turning_enabled and flat_len > 1e-4:
            # this edition's backward walk: the facing turns to the travel's opposite and the travel follows it
            back = -1.0 if self.backward else 1.0
            tgt = math.atan2(back * in_x, -back * in_y)
            d = _wrap(tgt - self._heading)
            step = self.max_turn_rate * dt
            self._heading += max(-step, min(step, d))
            in_x = back * math.sin(self._heading) * flat_len
            in_y = -back * math.cos(self._heading) * flat_len
        fwd_x = in_x / flat_len if flat_len > 1e-6 else 0.0
        fwd_y = in_y / flat_len if flat_len > 1e-6 else 0.0
        probe_z = cur.z + self.half_height + 5.0
        perp_x = math.cos(self._heading) if self._turning_enabled else -1.0
        perp_y = math.sin(self._heading) if self._turning_enabled else 0.0
        left_hit = self._ground_vector(cur.x + perp_x * self.foot_stance_x, cur.y + perp_y * self.foot_stance_x, probe_z,
                                       past_steep=self.ground_past_steep)
        right_hit = self._ground_vector(cur.x - perp_x * self.foot_stance_x, cur.y - perp_y * self.foot_stance_x, probe_z,
                                        past_steep=self.ground_past_steep)
        ahead_hit = None
        ahead_min, ahead_max = math.inf, -math.inf
        probe_ys = []
        if flat_len > 1e-3:
            N = self.ahead_probe_count or 5
            s, hits = 0.0, 0
            for i in range(1, N + 1):
                d = self.look_ahead * i / N
                y = self._ground_vector(cur.x + fwd_x * d, cur.y + fwd_y * d, probe_z)
                probe_ys.append((d, y))
                if y is not None:
                    s += y
                    hits += 1
                    ahead_min, ahead_max = min(ahead_min, y), max(ahead_max, y)
            if hits:
                ahead_hit = s / hits
        self.ahead_probe_spread = (ahead_max - ahead_min) if (ahead_max > -math.inf and ahead_min < math.inf) else 0.0
        transition_ds, transition_dys = [], []
        small_diff_abs_sum = 0.0
        valid_pairs = 0
        last_sign = 0
        sign_changes = 0
        disc = self._stair_discontinuity_threshold if self._stair_discontinuity_threshold is not None else 0.03
        for i in range(1, len(probe_ys)):
            a, b = probe_ys[i - 1][1], probe_ys[i][1]
            if a is None or b is None:
                continue
            dy = b - a
            ady = abs(dy)
            valid_pairs += 1
            if ady > disc:
                transition_ds.append(probe_ys[i - 1][0] + 0.5 * (probe_ys[i][0] - probe_ys[i - 1][0]))
                transition_dys.append(dy)
            else:
                small_diff_abs_sum += ady
            if ady > 0.005:
                sg = _sign(dy)
                if last_sign != 0 and sg != last_sign:
                    sign_changes += 1
                last_sign = sg
        max_transition_abs = max((abs(v) for v in transition_dys), default=0.0)
        max_step_transitions = self._max_stair_transitions_in_look_ahead or 3
        residual_limit = self._stair_residual_limit if self._stair_residual_limit is not None else 0.045
        min_step_rise = self._min_stair_rise if self._min_stair_rise is not None else 0.075
        has_step = (len(transition_ds) > 0 and len(transition_ds) <= max_step_transitions and
                    max_transition_abs >= min_step_rise and small_diff_abs_sum <= residual_limit)
        smooth_ramp_like = (not has_step and valid_pairs > 0 and len(transition_ds) == 0 and
                            self._stair_spread_threshold is not None and
                            self.ahead_probe_spread > self._stair_spread_threshold and sign_changes <= 1)
        # the small-stair early look-ahead
        early_la = self.small_stair_ascent_early_look_ahead if self.small_stair_ascent_early_look_ahead is not None \
            else self.look_ahead
        if flat_len > 1e-3 and early_la > self.look_ahead + 0.05:
            early_n = max(4, self.small_stair_ascent_early_probe_count or 36)
            early = []
            for i in range(1, early_n + 1):
                d = early_la * i / early_n
                early.append((d, self._ground_vector(cur.x + fwd_x * d, cur.y + fwd_y * d, probe_z)))
            pos_ds, neg_ds = [], []
            early_max, early_res = 0.0, 0.0
            for i in range(1, len(early)):
                a, b = early[i - 1][1], early[i][1]
                if a is None or b is None:
                    continue
                dy = b - a
                if abs(dy) > disc:
                    di = early[i - 1][0] + 0.5 * (early[i][0] - early[i - 1][0])
                    (pos_ds if dy > 0 else neg_ds).append(di)
                    early_max = max(early_max, abs(dy))
                else:
                    early_res += abs(dy)
            early_run = None
            if len(pos_ds) >= 2:
                early_run = sum(pos_ds[k] - pos_ds[k - 1] for k in range(1, len(pos_ds))) / (len(pos_ds) - 1)
            looks = (len(pos_ds) >= (self.small_stair_ascent_early_min_positive_edges or 2) and
                     len(neg_ds) <= (self.small_stair_ascent_early_max_negative_edges or 0) and
                     early_max >= min_step_rise and early_max < 0.13 and
                     early_res <= residual_limit * 1.5)
            if looks:
                self._small_stair_ascent_early_frames = self.small_stair_ascent_early_hold_frames or 12
            else:
                self._small_stair_ascent_early_frames = max(0, self._small_stair_ascent_early_frames - 1)
            self.small_stair_ascent_early_up = self._small_stair_ascent_early_frames > 0
            info = {'active': self.small_stair_ascent_early_up, 'detected': looks,
                    'hold_frames': self._small_stair_ascent_early_frames, 'positive_edges': len(pos_ds),
                    'negative_edges': len(neg_ds), 'first_positive_d': pos_ds[0] if pos_ds else None, 'run': early_run,
                    'max_transition_abs': early_max, 'residual': early_res, 'look_ahead': early_la}
        else:
            self._small_stair_ascent_early_frames = max(0, self._small_stair_ascent_early_frames - 1)
            self.small_stair_ascent_early_up = self._small_stair_ascent_early_frames > 0
            info = {'active': self.small_stair_ascent_early_up, 'detected': False,
                    'hold_frames': self._small_stair_ascent_early_frames}
        self.small_stair_ascent_early_info = info
        self.ahead_step_like = has_step
        self.ahead_smooth_ramp_like = smooth_ramp_like
        self.ahead_transition_count = len(transition_ds)
        self.ahead_probe_residual = small_diff_abs_sum
        self.ahead_step_rise_raw = max_transition_abs if has_step else 0.0
        positive_edge = any(dy > disc for dy in transition_dys)
        negative_edge = any(dy < -disc for dy in transition_dys)
        self._recent_positive_step_frames = (self._isolated_obstacle_sign_hold_frames if positive_edge
                                             else max(0, self._recent_positive_step_frames - 1))
        self._recent_negative_step_frames = (self._isolated_obstacle_sign_hold_frames if negative_edge
                                             else max(0, self._recent_negative_step_frames - 1))
        opposed = self._recent_positive_step_frames > 0 and self._recent_negative_step_frames > 0
        isolated_now = (has_step and opposed and max_transition_abs <= self.obstacle_walk_max_rise and
                        self.ahead_probe_spread <= self.obstacle_walk_max_spread)
        self._isolated_obstacle_frames = (self._isolated_obstacle_context_hold_frames if isolated_now
                                          else max(0, self._isolated_obstacle_frames - 1))
        self.ahead_isolated_obstacle = self._isolated_obstacle_frames > 0
        mem = self._stair_shape_memory_frames if self._stair_shape_memory_frames is not None else 20
        if has_step and max_transition_abs > 0:
            self.ahead_stair_rise = max_transition_abs
            self.ahead_stair_shape = 'small' if max_transition_abs < 0.13 else ('normal' if max_transition_abs < 0.20
                                                                                 else 'large')
            self._latched_stair_rise = self.ahead_stair_rise
            self._latched_stair_shape = self.ahead_stair_shape
            self._stair_shape_miss_frames = 0
        elif self._latched_stair_shape and self._stair_shape_miss_frames < mem:
            self._stair_shape_miss_frames += 1
            self.ahead_stair_rise = self._latched_stair_rise
            self.ahead_stair_shape = self._latched_stair_shape
        else:
            self._stair_shape_miss_frames += 1
            self.ahead_stair_rise = 0.0
            self.ahead_stair_shape = None
        run_mem = self._tread_run_memory_frames if self._tread_run_memory_frames is not None else 75
        if has_step and len(transition_ds) >= 2:
            self.ahead_tread_run = sum(transition_ds[k] - transition_ds[k - 1] for k in range(1, len(transition_ds))) \
                / (len(transition_ds) - 1)
            self._last_tread_run = self.ahead_tread_run
            self._last_tread_run_age = 0
            self._no_step_evidence_frames = 0
        elif has_step and len(transition_ds) == 1:
            fallback = {'small': 0.30, 'normal': 0.28, 'large': 0.26}.get(self.ahead_stair_shape)
            if self._last_tread_run and self._last_tread_run_age <= run_mem:
                self.ahead_tread_run = self._last_tread_run
                self._last_tread_run_age = 0
            elif fallback is not None:
                self.ahead_tread_run = fallback
                self._last_tread_run = fallback
                self._last_tread_run_age = 0
            else:
                self.ahead_tread_run = None
            self._no_step_evidence_frames = 0
        else:
            self.ahead_tread_run = None
            self._last_tread_run_age += 1
            self._no_step_evidence_frames = 0 if has_step else self._no_step_evidence_frames + 1
            if self._no_step_evidence_frames > run_mem:
                self._last_tread_run = None
        self._ahead_min_raw = ahead_min if ahead_min < math.inf else None
        self._ahead_max_raw = ahead_max if ahead_max > -math.inf else None
        current_feet_y = cur.z - self.half_height - self.hip_y
        self.ahead_lowest_delta = (self._ahead_min_raw - current_feet_y) if self._ahead_min_raw is not None else 0.0
        self.ahead_highest_delta = (self._ahead_max_raw - current_feet_y) if self._ahead_max_raw is not None else 0.0
        grounded = False
        climb_blocked = False
        if left_hit is not None and right_hit is not None:
            per_foot = min(left_hit, right_hit)
        elif left_hit is not None:
            per_foot = left_hit
        elif right_hit is not None:
            per_foot = right_hit
        else:
            per_foot = None
        is_large_descent = self.ahead_lowest_delta < -0.18
        seam_likely = (has_step or smooth_ramp_like or
                       self.ahead_probe_spread > (self._stair_spread_threshold if self._stair_spread_threshold is not None
                                                  else 0.10) or self.ahead_stair_shape is not None)
        ik_grace = None
        if per_foot is None and seam_likely and self._last_valid_ground_y is not None:
            self._ground_stale_frames += 1
            if self._ground_stale_frames <= (3 if is_large_descent else 2):
                per_foot = self._last_valid_ground_y
        if per_foot is None and self.use_ik_grounding_grace and isinstance(self._prior_ik_support_contacts, list):
            el = [c['hit_y'] for c in self._prior_ik_support_contacts
                  if c and c.get('valid') and c.get('hit_y') is not None and c.get('sole_gap_y') is not None and
                  abs(c['sole_gap_y']) <= self.ik_grounding_grace_max_sole_gap and
                  (current_feet_y - c['hit_y']) <= self.ik_grounding_grace_max_drop and
                  (c['hit_y'] - current_feet_y) <= self.ik_grounding_grace_max_rise]
            if el:
                per_foot = min(el)
                ik_grace = {'y': per_foot, 'contacts': len(el), 'current_feet_y': current_feet_y}
        if per_foot is not None:
            self._last_valid_ground_y = per_foot
            self._ground_stale_frames = 0
        thr = self.fall_threshold
        if self.land_on_contact and not self.grounded and self._velocity_y < 0.0:
            # this edition's: a falling body (already in the air last frame) lands when its feet reach the ground (the
            # original regains the ground fall_threshold above it and floats the rest down at the body-Y rate cap, its
            # feet in the air). A grounded body walking down a slope keeps the original's threshold: read on it, the
            # contact rule made the far side of a 35 cm dome a take-off
            thr = max(0.005, -self._velocity_y * dt)
        if per_foot is not None and (current_feet_y - per_foot) <= thr:
            grounded = True
        climb_deg = 0.0
        target_ground_y = per_foot
        contact_lift, contact_info = 0.0, None
        obs = self._foot_support_observation
        cand_y = obs['y'] if obs and obs.get('y') is not None else None
        cand_delta = (cand_y - per_foot) if (cand_y is not None and per_foot is not None) else None
        cand_stable = bool(obs and obs.get('stable')) and cand_y is not None and cand_delta is not None and \
            abs(cand_delta) <= self._foot_support_root_max_delta
        used_foot_support = False
        if self._use_foot_support_for_root and grounded and cand_stable:
            target_ground_y = cand_y
            used_foot_support = True
        if (self.use_contact_support_lift and grounded and left_hit is not None and right_hit is not None and
                per_foot is not None and not has_step):
            high_y, low_y = max(left_hit, right_hit), min(left_hit, right_hit)
            foot_delta = high_y - low_y
            high_side = 'left' if left_hit >= right_hit else 'right'
            prior_swing = bool(((self._prior_foot_contact_state or {}).get(high_side) or {}).get('in_swing', False))
            local_ramp = math.atan2(foot_delta, max(0.001, self.foot_stance_x * 2)) * R2D
            low_obstacle = (self.contact_support_lift_min <= foot_delta <= self.contact_support_lift_max and
                            (not smooth_ramp_like or local_ramp <= self.contact_support_max_ramp_angle))
            if low_obstacle:
                ratio = self.contact_support_swing_ratio if prior_swing else self.contact_support_lift_ratio
                contact_lift = foot_delta * max(0.0, min(1.0, ratio))
                target_ground_y = max(target_ground_y, low_y + contact_lift)
                contact_info = {'enabled': True, 'high_side': high_side, 'high_y': high_y, 'low_y': low_y,
                                'foot_delta': foot_delta, 'lift': contact_lift, 'ratio': ratio,
                                'high_side_in_swing': prior_swing, 'local_ramp_angle': local_ramp}
        ik_contact_info = None
        if (self.use_ik_contact_support_lift and grounded and per_foot is not None and not has_step and
                isinstance(self._prior_ik_support_contacts, list)):
            for c in self._prior_ik_support_contacts:
                if not c or not c.get('valid'):
                    continue
                dyc = c['hit_y'] - per_foot
                if dyc < self.contact_support_lift_min or dyc > self.contact_support_lift_max:
                    continue
                if abs(c.get('sole_gap_y') if c.get('sole_gap_y') is not None else 999) > self.ik_contact_sole_gap_max:
                    continue
                ratio = self.ik_contact_support_swing_ratio if c.get('in_swing') else self.ik_contact_support_lift_ratio
                lift = dyc * max(0.0, min(1.0, ratio))
                cy = per_foot + lift
                if cy > target_ground_y:
                    target_ground_y = cy
                    ik_contact_info = {'enabled': True, 'side': c['side'], 'hit_y': c['hit_y'], 'delta_y': dyc,
                                       'lift': lift, 'ratio': ratio, 'in_swing': c.get('in_swing'),
                                       'sole_gap_y': c.get('sole_gap_y')}
        if grounded and ahead_hit is not None and ahead_hit > per_foot + 0.01:
            dy = ahead_hit - current_feet_y
            climb_deg = math.atan2(max(0.0, dy), self.look_ahead) * R2D
            if climb_deg > self.max_climb_angle:
                climb_blocked = True
            else:
                ramp = max(0.0, min(1.0, (climb_deg - 5) / 20))
                bias = self.forward_bias * ramp
                target_ground_y = per_foot * (1 - bias) + ahead_hit * bias
        elif grounded and ahead_hit is not None and ahead_hit < per_foot - 0.01:
            dy = per_foot - ahead_hit
            climb_deg = math.atan2(max(0.0, dy), self.look_ahead) * R2D
        target_scale = 1.0
        engage, full, floor = 5, 30, 0.55
        if engage < climb_deg <= 45 and not climb_blocked:
            t = min(1.0, (climb_deg - engage) / (full - engage))
            target_scale = 1.0 * (1 - t) + floor * t
        if self._smooth_speed_scale is None:
            self._smooth_speed_scale = 1.0
        lp_k = min(1.0, dt * 10)
        self._smooth_speed_scale = self._smooth_speed_scale * (1 - lp_k) + target_scale * lp_k
        speed_scale = self._smooth_speed_scale
        self.climb_angle_deg = climb_deg
        is_descent = grounded and ahead_hit is not None and ahead_hit < per_foot - 0.01
        self.signed_climb_angle_deg = 0.0 if climb_blocked else (-climb_deg if is_descent else climb_deg)
        self.speed_scale = speed_scale
        self.grounded = grounded
        self.ground_y = target_ground_y if grounded else -math.inf
        self._climb_blocked = climb_blocked
        support_mode = ('airborne' if not grounded else
                        (('stairDown' if is_descent else 'stairUp') if has_step else
                         (('rampDown' if is_descent else 'rampUp') if smooth_ramp_like else 'flat')))
        self.support_frame = {
            'dt': dt,
            'input': {'x': in_x, 'y': in_y, 'fwd_x': fwd_x, 'fwd_y': fwd_y, 'flat_len': flat_len,
                      'origin_x': cur.x, 'origin_y': cur.y, 'origin_z': cur.z},
            'body': {'current_feet_y': current_feet_y, 'per_foot_ground_y': per_foot, 'target_ground_y': target_ground_y,
                     'used_foot_support_for_root': used_foot_support, 'contact_support': contact_info,
                     'ik_contact_support': ik_contact_info, 'ik_ground_grace': ik_grace, 'support_mode': support_mode,
                     'climb_blocked': climb_blocked},
            'probes': {'left_y': left_hit, 'right_y': right_hit, 'ahead_y': ahead_hit,
                       'raw_ys': [{'d': d, 'y': y} for d, y in probe_ys], 'ahead_min': self._ahead_min_raw,
                       'ahead_max': self._ahead_max_raw, 'spread': self.ahead_probe_spread,
                       'transition_ds': list(transition_ds), 'transition_dys': list(transition_dys),
                       'residual': small_diff_abs_sum, 'step_like': has_step,
                       'isolated_obstacle': self.ahead_isolated_obstacle, 'smooth_ramp_like': smooth_ramp_like,
                       'small_stair_ascent_early': info},
            'terrain': {'mode': support_mode, 'shape': self.ahead_stair_shape, 'rise': self.ahead_stair_rise or 0.0,
                        'run': self.ahead_tread_run, 'signed_angle': self.signed_climb_angle_deg,
                        'highest_delta': self.ahead_highest_delta, 'lowest_delta': self.ahead_lowest_delta,
                        'isolated_obstacle': self.ahead_isolated_obstacle, 'small_stair_ascent_early': info},
            'foot_observation': ({'y': cand_y, 'delta_from_body_support': cand_delta, 'stable': bool(obs.get('stable')),
                                  'stable_frames': obs.get('stable_frames', 0), 'source': obs.get('source')}
                                 if obs else None),
        }
        if grounded:
            wanted = target_ground_y + self.hip_y + self.half_height
            self._y_avg_window.append(wanted)
            if len(self._y_avg_window) > self._y_avg_size:
                self._y_avg_window.pop(0)
            self._body_y_target = sum(self._y_avg_window) / len(self._y_avg_window)
            self._velocity_y = 0.0
            descent_now = self._body_y_target < cur.z
            wants_up = support_mode in ('stairDown', 'rampDown') and self._body_y_target > cur.z
            raised_lift = target_ground_y - current_feet_y
            raised_cand = (self.allow_raised_support_during_descent and wants_up and
                           raised_lift >= self.raised_support_min_lift and
                           self.ahead_highest_delta >= self.raised_support_ahead_min and
                           self.ahead_probe_spread <= self.raised_support_max_spread)
            if raised_cand:
                self._raised_support_descent_latch = max(self._raised_support_descent_latch,
                                                         self.raised_support_latch_frames)
            raised_during = (self.allow_raised_support_during_descent and wants_up and
                             raised_lift >= self.raised_support_finish_gap and
                             (raised_cand or self._raised_support_descent_latch > 0))
            block_up = wants_up and not raised_during
            rate = self.body_y_rate_down if descent_now else self.body_y_rate_up
            max_step = rate * dt
            delta = self._body_y_target - cur.z
            if block_up:
                delta = 0.0
            smoothed = cur.z + _sign(delta) * min(abs(delta), max_step)
            if self._raised_support_descent_latch > 0:
                self._raised_support_descent_latch = (max(0, self._raised_support_descent_latch - 1) if raised_during
                                                      else 0)
            b = self.support_frame['body']
            b['body_y_target'] = self._body_y_target
            b['blocked_upward_descent_snap'] = block_up
            b['raised_support_during_descent'] = ({'lift': raised_lift, 'ahead_highest_delta': self.ahead_highest_delta,
                                                   'latch_frames': self._raised_support_descent_latch}
                                                  if raised_during else None)
            b['smoothed_y'] = smoothed
            if contact_info:
                b['contact_support']['body_y_target_lift'] = contact_lift
        else:
            self._velocity_y = max(self._velocity_y + self.gravity * dt, -self.max_fall_speed)
            smoothed = cur.z + self._velocity_y * dt
            self._y_avg_window.clear()
            self._body_y_target = smoothed
        desired = (in_x * dt * speed_scale, in_y * dt * speed_scale)
        # Rapier's setMaxSlopeClimbAngle(maxSlope): a surface steeper than max_slope stops the cylinder (a wall), a
        # gentler one is walked (the cylinder rides the hips' height over it)
        cx, cy = self.world.move_and_slide(cur, desired, self.radius, self.half_height, skin=self.skin,
                                           max_climb_normal=math.cos(math.radians(self.max_slope)))
        des_len, cor_len = math.hypot(*desired), math.hypot(cx, cy)
        if des_len > 1e-4 and cor_len < 0.4 * des_len:
            self._blocked_frames += 1
        elif cor_len > 0.05:
            self._blocked_frames = 0
        self._center = Vector((cur.x + cx, cur.y + cy, smoothed))
        t2 = self._center
        if dt > 0:
            self.speed_actual = math.hypot(t2.x - self._last_x, t2.y - self._last_y) / dt
        self._last_x, self._last_y = t2.x, t2.y
        self._feet_world = Vector((t2.x, t2.y, t2.z - self.half_height - self.hip_y - self.vrm_foot_y))

    # ================================================================================================ animation set-up
    def load_standard_animations(self, slots=None, turns=True, vrma_library=None):
        """loadStandardAnimations: the controller's own mixer and its actions (walk at weight 1, the rest at 0); every
        clip stripped as the original strips it (clips.py) and measured on this body. turns: also load turnLeft /
        turnRight for turn_on_spot (this edition's). vrma_library (the original's opts.vrmaLibrary): {slot: .vrma path}
        for slots played from elsewhere than the shared library"""
        lib = C.load_standard_animations(self.h, self.body, slots=slots, extra=C.TURN_SLOTS if turns else [],
                                         log=self.log, library=vrma_library)
        mixer = AnimationMixer(self.h)
        self._mixer = mixer
        self._clips = {k: v for k, v in lib.items() if v is not None}
        self._clip_root_motion = {k: v.root_motion for k, v in self._clips.items()}
        actions = {}
        for slot in list(slots or C.STANDARD_SLOTS) + (C.TURN_SLOTS if turns else []):
            clip = lib.get(slot)
            if clip is None:
                actions[slot] = None
                continue
            one = slot in C.ONE_SHOT or slot in C.TURN_SLOTS
            a = mixer.clip_action(clip).set_loop(LOOP_ONCE if one else LOOP_REPEAT)
            if one:
                a.clamp_when_finished = True
            a.play()
            a.set_effective_weight(1.0 if slot == 'walk' else 0.0)
            actions[slot] = a
        self._actions = actions
        return actions

    def load_emote(self, slot, loop=True, vrma_library=None):
        """loadEmote: a non-locomotion clip, every track kept; play it with play_emote (vrma_library: {slot: path})"""
        if self._mixer is None:
            raise RuntimeError('[eidoverse-controller] load_emote: call load_standard_animations() first')
        clip = C.load_emote_clip(self.h, slot, loop=loop is not False, body=self.body,
                                 source=(vrma_library or {}).get(slot))
        if clip is None:
            return None
        a = self._mixer.clip_action(clip).set_loop(LOOP_ONCE if loop is False else LOOP_REPEAT)
        if loop is False:
            a.clamp_when_finished = True
        a.play()
        a.set_effective_weight(0.0)
        if not hasattr(self, '_emote_actions'):
            self._emote_actions = {}
        self._emote_actions[slot] = a
        return a

    def _emote_clip(self, slot, loop=False):
        """the emote's ControllerClip (loaded once if it is not yet)"""
        if slot not in getattr(self, '_emote_actions', {}):
            self.load_emote(slot, loop=loop)
        a = getattr(self, '_emote_actions', {}).get(slot)
        return a.clip if a is not None else None

    def play_emote(self, slot, fade_in=0.2, fade_out=0.2):
        if self._maneuver:
            self.log(f"[eidoverse-controller] play_emote('{slot}') ignored: a {self._maneuver.get('type')} maneuver is "
                     f"in flight")
            return None
        acts = getattr(self, '_emote_actions', {})
        if slot not in acts:
            self.log(f"[eidoverse-controller] play_emote: '{slot}' not loaded: call load_emote('{slot}') first")
            return None
        for k, a in acts.items():
            if k != slot and a.enabled and a.get_effective_weight() > 0.01:
                a.fade_out(fade_out)
        a = acts[slot]
        a.reset()
        a.time_scale = 1.0
        a.set_effective_weight(1.0)
        a.play()
        a.fade_in(fade_in)
        self._active_emote = slot
        return a

    def stop_emote(self, fade_out=0.3):
        for a in getattr(self, '_emote_actions', {}).values():
            if a and a.enabled and a.get_effective_weight() > 0.01:
                a.fade_out(fade_out)
        self._active_emote = None

    def begin_seated(self, slot='stand_to_sit', fade_in=0.25):
        """beginSeated: the seated transition plays on the controller's mixer and the root is the caller's. While seated
        the root holds where the seat began, raised by `seat_dz` (this edition's: the film's Sit sets it so the seated
        underside rests on the seat's pan, seatOn's settle)"""
        self._seated = True
        self._seat_root_z = self.pose.M.translation.z
        self.seat_dz = 0.0
        if slot not in getattr(self, '_emote_actions', {}):
            self.load_emote(slot, loop=False)
        a = self.play_emote(slot, fade_in=fade_in)
        return a.clip.duration if a else None

    def end_seated(self, slot='sit_to_stand', fade_in=0.25, reverse=False, reverse_speed=1.0, release_at=None):
        """endSeated: reverse plays the still-active seated clip backwards; else a stand-up clip; the root returns to the
        controller once the clip has carried the hips back over the feet"""
        if reverse:
            act = getattr(self, '_active_emote', None)
            a = getattr(self, '_emote_actions', {}).get(act) if act else None
            if a is not None:
                dur = a.clip.duration
                a.paused = False
                a.enabled = True
                if a.time <= 0 or a.time > dur:
                    a.time = dur
                a.time_scale = -reverse_speed
                remaining = a.time / reverse_speed
                self._seated_release_in = max(0.3, remaining * (release_at if release_at is not None else 0.92))
                return remaining
        dur = None
        if slot:
            if slot not in getattr(self, '_emote_actions', {}):
                self.load_emote(slot, loop=False)
            a = self.play_emote(slot, fade_in=fade_in)
            dur = a.clip.duration if a else None
            self._seated_release_in = max(0.3, (dur or 1.8) * (release_at if release_at is not None else 0.85))
        else:
            self._seated = False
        return dur

    def load_gesture(self, slot, loop=True, vrma_library=None):
        """loadGesture: an emote masked to the upper body, blended OVER the gait (vrma_library: {slot: path})"""
        if self._mixer is None:
            raise RuntimeError('[eidoverse-controller] load_gesture: call load_standard_animations() first')
        clip = C.load_gesture_clip(self.h, slot, loop=loop is not False, source=(vrma_library or {}).get(slot))
        if clip is None:
            self.log(f"[eidoverse-controller] load_gesture('{slot}'): no upper-body tracks survived the mask")
            return None
        a = self._mixer.clip_action(clip).set_loop(LOOP_ONCE if loop is False else LOOP_REPEAT)
        if loop is False:
            a.clamp_when_finished = True
        a.play()
        a.set_effective_weight(0.0)
        if not hasattr(self, '_gesture_actions'):
            self._gesture_actions = {}
        self._gesture_actions[slot] = a
        return a

    def play_gesture(self, slot, weight=2.5):
        a = getattr(self, '_gesture_actions', {}).get(slot)
        if a is None:
            self.log(f"[eidoverse-controller] play_gesture: '{slot}' not loaded: call load_gesture('{slot}') first")
            return None
        a.reset()
        a.play()
        self._active_gesture = slot
        self._gesture_weight = weight
        return a

    def stop_gesture(self):
        self._active_gesture = None

    def _update_gesture_weights(self, dt, force_off=False):
        for k, a in getattr(self, '_gesture_actions', {}).items():
            if a is None:
                continue
            tgt = getattr(self, '_gesture_weight', 2.5) if (not force_off and getattr(self, '_active_gesture', None) == k) \
                else 0.0
            a.weight = damp(a.weight, tgt, 8, dt)

    @property
    def is_emoting(self):
        thresh = getattr(self, 'emote_suspend_threshold', 0.05)
        for a in getattr(self, '_emote_actions', {}).values():
            if a and a.enabled and a.get_effective_weight() > thresh:
                return True
        return False

    # ================================================================================================ locomotion
    def attach_locomotion(self, mixer=None, actions=None, leg_ik=None, **o):
        """attachLocomotion: the gait tree's parameters (the original's defaults) and the leg IK. leg_ik='default' builds
        the VRMFootControllerIK terrain_base.js builds (RayAndSphere casts, 1.5 cm ball, fixKnee, 12 mm foot offset)"""
        if mixer is not None:
            self._mixer = mixer
        if actions is not None:
            self._actions = actions
        if leg_ik == 'default':
            leg_ik = self.default_leg_ik()
        self._leg_ik = leg_ik
        g = o.get
        self._flat_speed = g('flat_speed', 1.5)
        self._stair_cadence = g('stair_cadence', 2.5)
        self._native_walk_speed = g('native_walk_speed', 1.5)
        self._ascend_threshold = g('ascend_threshold', 0.4)
        self._descend_threshold = g('descend_threshold', -0.4)
        self._stair_leaving_lambda = g('stair_leaving_lambda', 18)
        self._stair_engage_lambda = g('stair_engage_lambda', 12)
        self._tall_riser_threshold = g('tall_riser_threshold', 0.20)
        self._tall_riser_engage_lambda = g('tall_riser_engage_lambda', 16)
        self._stair_up_ahead_threshold = g('stair_up_ahead_threshold', 0.055)
        self._stair_down_ahead_threshold = g('stair_down_ahead_threshold', -0.08)
        self._stair_spread_threshold = g('stair_spread_threshold', 0.10)
        self._stair_spread_history_len = g('stair_spread_history_len', 30)
        self._stair_discontinuity_threshold = g('stair_discontinuity_threshold', 0.03)
        self._max_stair_transitions_in_look_ahead = g('max_stair_transitions_in_look_ahead', 3)
        self._stair_residual_limit = g('stair_residual_limit', 0.045)
        self._min_stair_rise = g('min_stair_rise', 0.075)
        self._tread_run_memory_frames = g('tread_run_memory_frames', 75)
        self._stair_shape_memory_frames = g('stair_shape_memory_frames', 20)
        self._require_confirmed_stair_clips = g('require_confirmed_stair_clips', False)
        self._confirmed_stair_hold_frames = g('confirmed_stair_hold_frames', 12)
        self._confirmed_stair_frames = 0
        self._hip_lean_ascent = g('hip_lean_ascent', 0.30)
        self._hip_lean_descent = g('hip_lean_descent', 0.40)
        self._body_y_drop_ascent = g('body_y_drop_ascent', 0.006)
        self._body_y_drop_descent = g('body_y_drop_descent', 0.018)
        self._body_y_drop_descent_cap = g('body_y_drop_descent_cap', 0.22)
        self._body_y_drop_ascent_cap = g('body_y_drop_ascent_cap', 0.08)
        self._body_y_drop_stair_ramp = g('body_y_drop_stair_ramp', 0.006)
        self._body_y_drop_stair_ramp_cap = g('body_y_drop_stair_ramp_cap', 0.18)
        self._ramp_walk_angle_threshold = g('ramp_walk_angle_threshold', 2.0)
        self._ramp_walk_max_angle = g('ramp_walk_max_angle', 8.0)
        self._ramp_walk_min_probe_spread = g('ramp_walk_min_probe_spread', 0.015)
        self._ramp_walk_max_probe_spread = g('ramp_walk_max_probe_spread', 0.085)
        self._ramp_walk_steep_max_probe_spread = g('ramp_walk_steep_max_probe_spread', 0.17)   # declared, never read
        self._ramp_edge_angle_threshold = g('ramp_edge_angle_threshold', 8.0)
        self._ramp_context_hold_frames = g('ramp_context_hold_frames', 12)
        self._ramp_stair_clear_lambda = g('ramp_stair_clear_lambda', 30)
        self._ramp_body_y_drop_descent = g('ramp_body_y_drop_descent', 0.012)
        self._ramp_body_y_drop_descent_cap = g('ramp_body_y_drop_descent_cap', 0.12)
        self._ramp_foot_clearance_offset = g('ramp_foot_clearance_offset', 0.008)
        self._head_pitch_bonus_max = g('head_pitch_bonus_max', 6)
        self._foot_offset_ascent = g('foot_offset_ascent', 0.9)
        self._foot_offset_descent = g('foot_offset_descent', 0.5)                  # declared, never read
        self._foot_offset_large_descent = g('foot_offset_large_descent', 0.6)      # declared, never read
        self._foot_offset_ascent_small_scale = g('foot_offset_ascent_small_scale', 0.90)
        self._foot_offset_descent_small = g('foot_offset_descent_small', 0.42)
        self._foot_offset_descent_normal = g('foot_offset_descent_normal', 0.25)
        self._foot_offset_descent_large = g('foot_offset_descent_large', 0.20)
        self._large_descent_climb_knee = g('large_descent_climb_knee', 28)        # declared, never read
        self._large_descent_climb_width = g('large_descent_climb_width', 12)      # declared, never read
        self._large_stair_ascent_speed_scale = g('large_stair_ascent_speed_scale', 0.58)
        self._foot_offset_steep_knee = g('foot_offset_steep_knee', 25)            # declared, never read
        self._foot_offset_steep_width = g('foot_offset_steep_width', 10)          # declared, never read
        self._use_foot_support_for_root = g('use_foot_support_for_root', False)
        self._foot_support_root_stable_frames = g('foot_support_root_stable_frames', 4)
        self._foot_support_root_max_delta = g('foot_support_root_max_delta', 0.08)
        self._large_stair_full_toe_reach = g('large_stair_full_toe_reach', False)
        self._opposite_stair_clear_lambda = g('opposite_stair_clear_lambda', 30)
        self.running = g('running', False)
        self._run_speed = g('run_speed', 3.6)
        self._native_run_speed = g('native_run_speed', 3.6)
        self._stair_cadence_run = g('stair_cadence_run', 1.4)
        # this edition: a native speed (or a speed) given as None is measured on this body (the clip's stride / its
        # duration); the WebGPU numbers stay the defaults
        def measured(slot, fallback):
            c = self._clips.get(slot)
            return c.gait.v_native if (c is not None and c.gait is not None and c.gait.v_native > 0.1) else fallback
        if self._native_walk_speed is None or o.get('measure_native'):
            self._native_walk_speed = measured('walk', 1.5)
        if self._native_run_speed is None or o.get('measure_native'):
            self._native_run_speed = measured('run', 3.6)
        if self._flat_speed is None:
            self._flat_speed = self._native_walk_speed
        if self._run_speed is None:
            self._run_speed = self._native_run_speed
        if 'gait_sync' in o:
            self.gait_sync = o['gait_sync']
        self._smooth_fwd_speed = self._flat_speed
        self._smooth_tread_run = 0.28
        self._smooth_hips_lean_deg = 0.0
        self._smooth_head_pitch_deg = 0.0
        self._smooth_body_drop = 0.0
        self._smooth_climb_deg_ik = 0.0
        self._last_body_y = None
        self._spread_history = []
        self._step_evidence_history = []
        self._stair_motion_history = []
        self._last_tread_run = None
        self._last_tread_run_age = 999
        self._no_step_evidence_frames = 999
        self._latched_stair_rise = 0.0
        self._latched_stair_shape = None
        self._stair_shape_miss_frames = 999
        self._head_rest_quat = None
        self._smooth_ramp_context_frames = 0
        self._small_stair_phase_lock = g('small_stair_phase_lock', True)
        self._small_stair_phase_lock_ascent = g('small_stair_phase_lock_ascent', False)
        self._small_stair_phase_lock_descent = g('small_stair_phase_lock_descent', True)
        self._small_stair_ascent_phase_offset = g('small_stair_ascent_phase_offset', 0.0)
        self._small_stair_descent_phase_offset = g('small_stair_descent_phase_offset', 0.0)
        self._small_stair_phase_min_weight = g('small_stair_phase_min_weight', 0.05)
        self._small_stair_ascent_sole_fit = g('small_stair_ascent_sole_fit', True)
        self._small_stair_ascent_guard_rise = g('small_stair_ascent_guard_rise', 0.035)
        self._small_stair_ascent_single_rise_offset_scale = g('small_stair_ascent_single_rise_offset_scale', 0.58)
        self._small_stair_ascent_single_rise_sole_fit_scale = g('small_stair_ascent_single_rise_sole_fit_scale', 0.36)
        self._small_stair_ascent_multi_rise_offset_scale = g('small_stair_ascent_multi_rise_offset_scale', 0.60)
        self._small_stair_ascent_multi_rise_sole_fit_scale = g('small_stair_ascent_multi_rise_sole_fit_scale', 0.46)
        self._small_stair_ascent_early_offset_scale = g('small_stair_ascent_early_offset_scale', 0.42)
        self._small_stair_ascent_exit_clear_lambda = g('small_stair_ascent_exit_clear_lambda', 48)
        self._small_stair_ascent_edge_align = g('small_stair_ascent_edge_align', True)
        self._small_stair_ascent_edge_hold_frames = g('small_stair_ascent_edge_hold_frames', 12)
        self._small_stair_ascent_edge_max_distance = g('small_stair_ascent_edge_max_distance', 0.48)
        self._small_stair_ascent_edge_advance_run_scale = g('small_stair_ascent_edge_advance_run_scale', 0.98)
        self._small_stair_ascent_edge_latch = None
        self._small_stair_ascent_edge_info = None
        self._stair_phase_lock_active = False
        self._stair_phase_lock_dir = None
        self._stair_phase_lock_shape = None
        self._stair_phase_distance = 0.0
        self._stair_phase_cycle = None
        self._stair_phase_lock_info = None
        # this edition's distance matching state
        self._gait_phase = 0.0
        self._distance = 0.0
        self._stair_pace = None
        return self

    def default_leg_ik(self):
        """the leg IK terrain_base.js builds for its controller"""
        return VRMFootControllerIK(self.body, world=self.world, increased_accuracy=True, fix_knee=True,
                                   foot_height_offset=0.012, type=CastType.RAY_AND_SPHERE, sphere_radius=0.015,
                                   max_step_height=0.6, distance_power=1, smoothing_angle=2, global_smoothing_power=0,
                                   mesh_height_offset=self.vrm_foot_y)

    def _update_small_stair_ascent_edge_align_hint(self, active):
        frame = self.support_frame or {}
        inp = frame.get('input') or {}
        probes = frame.get('probes') or {}
        fwd_x, fwd_y = inp.get('fwd_x', 0.0) or 0.0, inp.get('fwd_y', 0.0) or 0.0
        fwd_len = math.hypot(fwd_x, fwd_y)
        transitions = probes.get('transition_ds') or []
        tdys = probes.get('transition_dys') or []
        threshold = self._stair_discontinuity_threshold or 0.03
        max_d = self._small_stair_ascent_edge_max_distance
        hold = self._small_stair_ascent_edge_hold_frames
        run = self.ahead_tread_run if self.ahead_tread_run is not None else (
            self._last_tread_run if self._last_tread_run is not None else self._smooth_tread_run)
        body = self._center

        def make(d, dy, source):
            ox = inp.get('origin_x', body.x)
            oy = inp.get('origin_y', body.y)
            return {'point': (ox + fwd_x * d, oy + fwd_y * d), 'dir': (fwd_x / fwd_len, fwd_y / fwd_len),
                    'run': run, 'age': 0, 'distance': d, 'dy': dy, 'source': source}
        best_d, best_dy = None, None
        if active and fwd_len > 0.5:
            for d, dy in zip(transitions, tdys):
                if dy <= threshold or d < 0 or d > max_d:
                    continue
                if best_d is None or d < best_d:
                    best_d, best_dy = d, dy
        latch = self._small_stair_ascent_edge_latch
        if not active or fwd_len <= 0.5:
            self._small_stair_ascent_edge_latch = None
        elif latch is None and best_d is not None:
            self._small_stair_ascent_edge_latch = make(best_d, best_dy, 'probe-first')
        elif latch is not None:
            latch['age'] += 1
            prog = (body.x - latch['point'][0]) * latch['dir'][0] + (body.y - latch['point'][1]) * latch['dir'][1]
            run_now = latch['run'] if latch['run'] is not None else run
            adv = run_now * self._small_stair_ascent_edge_advance_run_scale if run_now is not None else math.inf
            exp = run_now * 1.35 if run_now is not None else math.inf
            if best_d is not None and prog >= adv:
                self._small_stair_ascent_edge_latch = make(best_d, best_dy, 'probe-advance')
            elif latch['age'] > hold and prog > exp:
                self._small_stair_ascent_edge_latch = None
        elif best_d is not None:
            self._small_stair_ascent_edge_latch = make(best_d, best_dy, 'probe-reacquire')
        latch = self._small_stair_ascent_edge_latch
        if latch is None:
            self._small_stair_ascent_edge_info = {'active': False, 'reason': 'no-positive-edge' if active else 'inactive'}
            return self._small_stair_ascent_edge_info
        prog = (body.x - latch['point'][0]) * latch['dir'][0] + (body.y - latch['point'][1]) * latch['dir'][1]
        self._small_stair_ascent_edge_info = dict(latch, active=True, body_progress=prog)
        return self._small_stair_ascent_edge_info

    def _place_root(self, heading):
        f = self._feet_world
        self.pose.M = root_matrix(f.x, f.y, f.z, heading)
        self.pose.invalidate()
        self.scene_heading = heading

    def _sync_pose(self):
        """the mixer's blend into the frame's Pose (the bones no clip binds keep last frame's value)"""
        self.pose.N.update(self._mixer.pose)
        self.pose.off = self._mixer.hips.copy()
        self.pose.invalidate()

    def locomote(self, dt, input=None):
        """the original's locomote(dt, {z: -1}): one frame (physics, detection, weights, mixer, pose, IK); input a
        direction of travel (world x, y; its length scales the gait's speed)"""
        self.time += dt
        actions = self._actions or {}
        if getattr(self, '_seated_release_in', None) is not None:
            self._seated_release_in -= dt
            if self._seated_release_in <= 0:
                self._seated_release_in = None
                self._seated = False
        walk_a, run_a, idle_a = actions.get('walk'), actions.get('run'), actions.get('idle')
        su_a, sd_a = actions.get('stairsUp'), actions.get('stairsDown')
        sru_a, srd_a = actions.get('stairsRunUp'), actions.get('stairsRunDown')
        fall_a = actions.get('fallIdle')
        ik = self._leg_ik
        mixer = self._mixer
        self.mode = 'loco'
        self.hand_contact = {}              # this frame's hands the contact IK placed: {side: its weight} (the record's)
        # ---- EMOTE SUSPEND
        if self.is_emoting:
            self.mode = 'seated' if getattr(self, '_seated', False) else 'emote'
            for a in actions.values():
                if a is None:
                    continue
                if a is idle_a and not getattr(self, '_active_emote', None) and not getattr(self, '_seated', False):
                    a.weight = damp(a.weight, 1.0, 6, dt)
                    continue
                a.weight = damp(a.weight, 0.0, 12, dt)
            self._update_gesture_weights(dt, True)
            self.update(dt, (0.0, 0.0))
            if mixer:
                mixer.update(dt)
                self._sync_pose()
            if not getattr(self, '_seated', False):
                tgt = (getattr(self, '_emote_facing_y', None) if getattr(self, '_emote_facing_y', None) is not None
                       else math.pi) if getattr(self, '_active_emote', None) else self._heading
                d = _wrap(tgt - self.scene_heading)
                h = tgt if abs(d) < 0.02 else self.scene_heading + d * (1 - math.exp(-12 * dt))
                self._place_root(h)
                self.anim_pose = self.pose.copy()
                if ik and self.grounded:
                    ik.descent_context = False
                    ik.foot_plant_forward_offset = 0.0
                    ik.update(dt, self.pose)
            else:
                if getattr(self, '_seat_root_z', None) is not None:
                    t = self.pose.M.translation.copy()
                    t.z = self._seat_root_z + getattr(self, 'seat_dz', 0.0)
                    self.pose.M.translation = t
                    self.pose.invalidate()
                self.anim_pose = self.pose.copy()
            self.external_ground_y = None
            return
        # ---- this edition's turn on the spot
        if self._turn is not None:
            self._update_turn(dt)
            return
        # ---- MANEUVER IN FLIGHT
        if self._maneuver:
            self.mode = 'maneuver'
            self._update_maneuver(dt)
            return
        if self._maneuver_cooldown_t > 0:
            self._maneuver_cooldown_t -= dt
        if self._fading_maneuver_action is not None:
            fa = self._fading_maneuver_action
            fa.weight = damp(fa.weight, 0.0, 10, dt)
            if fa.weight < 0.01:
                fa.weight = 0.0
                self._fading_maneuver_action = None
        is_running = self.running and run_a is not None
        ground_anim = run_a if is_running else walk_a
        up_anim = sru_a if (is_running and sru_a) else su_a
        down_anim = srd_a if (is_running and srd_a) else sd_a
        # 1. forward speed, shape-synced to the detected tread run
        looks_down = self.ahead_lowest_delta < self._stair_down_ahead_threshold
        looks_up = self.ahead_highest_delta > self._stair_up_ahead_threshold
        if looks_down and not looks_up:
            stairs_dur = (down_anim or up_anim).clip.duration if (down_anim or up_anim) else 1.0
        else:
            stairs_dur = (up_anim or down_anim).clip.duration if (up_anim or down_anim) else 1.0
        run_for_speed = self.ahead_tread_run
        base_speed = self._run_speed if is_running else self._flat_speed
        stair_cad = self._stair_cadence_run if is_running else self._stair_cadence
        target_fwd = base_speed
        confirmed_speed = not self._require_confirmed_stair_clips or self._confirmed_stair_frames > 0
        if confirmed_speed and run_for_speed is not None and self.ahead_probe_spread > self._stair_spread_threshold:
            target_fwd = (2 * run_for_speed * stair_cad) / stairs_dur
            if self.ahead_stair_shape == 'large' and self.ahead_highest_delta > self._stair_up_ahead_threshold:
                target_fwd *= self._large_stair_ascent_speed_scale
        self._smooth_fwd_speed = lerp(self._smooth_fwd_speed, target_fwd, min(1.0, 3 * dt))
        self.target_forward_speed = target_fwd          # telemetry (the original's local targetForwardSpeed)
        ix, iy = _xy(input)
        in_x, in_y = ix * self._smooth_fwd_speed, iy * self._smooth_fwd_speed
        # 2. physics + ground detection (the IK's last contacts first)
        if ik:
            def read(side, limb):
                if limb is None or not limb.can_reach_target:
                    return {'side': side, 'valid': False}
                hit = limb.lowest_hit_point
                actual = limb.low_bone_position
                foot_h = (limb.distance_from_mesh or 0.0) - (ik.m_foot_height_offset or 0.0)
                hit_y = hit.z if hit is not None else None
                gap = actual.z - hit_y - foot_h if hit_y is not None else None
                return {'side': side, 'valid': hit_y is not None and gap is not None, 'hit_y': hit_y, 'sole_gap_y': gap,
                        'in_swing': bool(limb._in_swing) or (limb._synthetic_lift or 0.0) > 0.035,
                        'synthetic_lift': limb._synthetic_lift or 0.0}
            self._prior_ik_support_contacts = [read('left', ik.m_left_leg), read('right', ik.m_right_leg)]
            self._prior_foot_contact_state = {
                s: {'in_swing': bool(l_._in_swing), 'swing_phase': l_._swing_phase, 'synthetic_lift': l_._synthetic_lift}
                for s, l_ in (('left', ik.m_left_leg), ('right', ik.m_right_leg))}
        self.update(dt, (in_x, in_y))
        t2 = self._center
        grounded = self.grounded
        speed = self.speed_actual
        moving = speed > 0.3
        # 2.5 landing recovery + auto-maneuvers
        feet_now = t2.z - self.half_height - self.hip_y
        if not grounded:
            self._airborne_from_y = feet_now if self._airborne_from_y is None else max(self._airborne_from_y, feet_now)
            self._airborne_time += dt
        else:
            if self._airborne_from_y is not None:
                drop = self._airborne_from_y - feet_now
                if drop >= self.fall_land_min_drop and actions.get('fallLand'):
                    self._airborne_from_y = None
                    self._airborne_time = 0.0
                    if self._start_maneuver({'type': 'land', 'slot': 'fallLand', 'duration': None}):
                        return
            self._airborne_from_y = None
            self._airborne_time = 0.0
        if self.auto_maneuvers and grounded and moving and not self.backward and (abs(in_x) > 1e-3 or abs(in_y) > 1e-3):
            if self._turning_enabled:
                fx, fy = math.sin(self._heading), -math.cos(self._heading)
            else:
                ln = math.hypot(in_x, in_y)
                fx, fy = in_x / ln, in_y / ln
            if self._maybe_auto_maneuver(fx, fy, speed):
                return
        # 3. vertical motion
        if self._last_body_y is None:
            self._last_body_y = t2.z
        body_vel_y = (t2.z - self._last_body_y) / dt if dt > 0 else 0.0
        self._last_body_y = t2.z
        ascending = grounded and moving and body_vel_y > self._ascend_threshold
        descending = grounded and moving and body_vel_y < self._descend_threshold
        # 4. stair detection
        climb_blocked = self._climb_blocked
        step_now = bool(self.ahead_step_like)
        steep_ramp_now = bool(self.ahead_smooth_ramp_like)
        tcount = len(((self.support_frame or {}).get('probes') or {}).get('transition_ds') or [])
        multi_edge = step_now and tcount >= 2
        if multi_edge:
            self._confirmed_stair_frames = self._confirmed_stair_hold_frames
        elif self._confirmed_stair_frames > 0 and (step_now or steep_ramp_now):
            self._confirmed_stair_frames = max(0, self._confirmed_stair_frames - 1)
        elif not step_now and not steep_ramp_now:
            self._confirmed_stair_frames = 0
        self._step_evidence_history.append(1 if step_now else 0)
        self._stair_motion_history.append(1 if (step_now or steep_ramp_now) else 0)
        if len(self._step_evidence_history) > self._stair_spread_history_len:
            self._step_evidence_history.pop(0)
        if len(self._stair_motion_history) > self._stair_spread_history_len:
            self._stair_motion_history.pop(0)
        recent_step = any(self._step_evidence_history)
        recent_motion = any(self._stair_motion_history)
        confirmed_clip = not self._require_confirmed_stair_clips or multi_edge or self._confirmed_stair_frames > 0
        stair_ahead = grounded and moving and recent_motion and confirmed_clip and not climb_blocked
        ahead_high, ahead_low = self.ahead_highest_delta, self.ahead_lowest_delta
        stair_up_ahead = stair_ahead and ahead_high > self._stair_up_ahead_threshold
        stair_down_ahead = stair_ahead and ahead_low < self._stair_down_ahead_threshold
        guard = self._small_stair_ascent_guard_rise
        small_no_future = (self.ahead_stair_shape == 'small' and not step_now and ahead_high <= guard and
                           ahead_low >= -guard)
        tall_riser = ahead_high > self._tall_riser_threshold
        abs_climb = abs(self.signed_climb_angle_deg)
        spread = self.ahead_probe_spread
        active_window = self._confirmed_stair_frames > 0
        shallow_ramp = abs_climb <= self._ramp_walk_max_angle and spread <= self._ramp_walk_max_probe_spread
        steep_stair_ctx = (grounded and moving and not step_now and self.ahead_tread_run is None and steep_ramp_now and
                           abs_climb > self._ramp_walk_max_angle and not climb_blocked)
        smooth_ramp_walk = (grounded and moving and not active_window and not step_now and self.ahead_tread_run is None and
                            spread >= self._ramp_walk_min_probe_spread and abs_climb >= self._ramp_walk_angle_threshold and
                            shallow_ramp)
        shallow_single = (grounded and moving and not active_window and step_now and tcount == 1 and
                          self.ahead_step_rise_raw > self._tall_riser_threshold and
                          abs_climb <= self._ramp_edge_angle_threshold)
        recent_ramp = self._smooth_ramp_context_frames > 0
        ramp_ctx = smooth_ramp_walk or shallow_single or (recent_ramp and not steep_stair_ctx and
                                                          (not step_now or shallow_single))
        if smooth_ramp_walk or shallow_single:
            self._smooth_ramp_context_frames = self._ramp_context_hold_frames
        elif steep_stair_ctx or step_now:
            self._smooth_ramp_context_frames = 0
        else:
            self._smooth_ramp_context_frames = max(0, self._smooth_ramp_context_frames - 1)
        untreaded = (self.prefer_walk_on_untreaded_obstacles and grounded and moving and step_now and
                     self.ahead_tread_run is None and spread <= self.obstacle_walk_max_spread and
                     max(abs(ahead_high), abs(ahead_low)) <= self.obstacle_walk_max_rise)
        isolated = self.prefer_walk_on_isolated_obstacles and grounded and moving and bool(self.ahead_isolated_obstacle)
        small_early = (grounded and moving and bool(self.small_stair_ascent_early_up) and not small_no_future and
                       not isolated and not climb_blocked)
        # 5. weight targets
        t_idle = t_walk = t_up = t_down = t_fall = 0.0
        sgn = self.signed_climb_angle_deg
        if not grounded and fall_a:
            t_fall = 1.0
        elif not moving:
            t_idle = 1.0
        elif ramp_ctx:
            t_walk = 1.0
        elif steep_stair_ctx and sgn > 0 and su_a:
            t_up = 1.0
        elif steep_stair_ctx and sgn < 0 and sd_a:
            t_down = 1.0
        elif untreaded or isolated:
            t_walk = 1.0
        elif (small_early or ((ascending and not small_no_future) or stair_up_ahead)) and su_a:
            t_up = 1.0
        elif (descending or stair_down_ahead) and sd_a:
            t_down = 1.0
        else:
            t_walk = 1.0
        entering_idle = not moving
        base_l = 20 if not grounded else (18 if entering_idle else 8)
        eng_l = self._tall_riser_engage_lambda if tall_riser else self._stair_engage_lambda

        def damp_stair(cur, tgt):
            lam = (self._stair_leaving_lambda if (tgt == 0 and cur > 0.01) else
                   (eng_l if (tgt > 0 and cur < 0.5) else base_l))
            return damp(cur, tgt, lam, dt)
        if idle_a:
            idle_a.weight = damp(idle_a.weight, t_idle, base_l, dt)
        if ground_anim:
            ground_anim.weight = damp(ground_anim.weight, t_walk, base_l, dt)
        if up_anim:
            up_anim.weight = damp_stair(up_anim.weight, t_up)
        if down_anim:
            down_anim.weight = damp_stair(down_anim.weight, t_down)
        if fall_a:
            fall_a.weight = damp(fall_a.weight, t_fall, base_l, dt)
        for a in (walk_a, run_a, su_a, sd_a, sru_a, srd_a):
            if a and a is not ground_anim and a is not up_anim and a is not down_anim:
                a.weight = damp(a.weight, 0.0, 10, dt)
        for k, a in actions.items():
            if a and k.startswith('turn'):              # turnLeft / turnRight and their twins
                a.weight = damp(a.weight, 0.0, 10, dt)
        if small_no_future and up_anim:
            up_anim.weight = damp(up_anim.weight, 0.0, self._small_stair_ascent_exit_clear_lambda, dt)
        if ramp_ctx:
            if up_anim:
                up_anim.weight = damp(up_anim.weight, 0.0, self._ramp_stair_clear_lambda, dt)
            if down_anim:
                down_anim.weight = damp(down_anim.weight, 0.0, self._ramp_stair_clear_lambda, dt)
        if not untreaded and not isolated and stair_down_ahead and up_anim:
            up_anim.weight = damp(up_anim.weight, 0.0, self._opposite_stair_clear_lambda, dt)
        if not untreaded and not isolated and stair_up_ahead and down_anim:
            down_anim.weight = damp(down_anim.weight, 0.0, self._opposite_stair_clear_lambda, dt)
        if self.support_frame is not None:
            self.support_frame['animation'] = {
                'target_idle': t_idle, 'target_walk': t_walk, 'target_stairs_up': t_up, 'target_stairs_down': t_down,
                'target_fall': t_fall, 'confirmed_stair_clip': confirmed_clip,
                'confirmed_stair_frames': self._confirmed_stair_frames, 'measured_multi_edge_stair': multi_edge,
                'untreaded_obstacle_walk': untreaded, 'isolated_obstacle_walk': isolated,
                'smooth_ramp_context': ramp_ctx, 'smooth_ramp_walk_now': smooth_ramp_walk,
                'shallow_single_large_edge': shallow_single, 'shallow_continuous_ramp': shallow_ramp,
                'steep_continuous_stair_context': steep_stair_ctx, 'small_stair_early_ascent': small_early,
                'stair_phase_lock': self._stair_phase_lock_info, 'running': is_running,
                'weights': {'idle': idle_a.weight if idle_a else 0.0, 'ground': ground_anim.weight if ground_anim else 0.0,
                            'stairs_up': up_anim.weight if up_anim else 0.0,
                            'stairs_down': down_anim.weight if down_anim else 0.0,
                            'fall_idle': fall_a.weight if fall_a else 0.0}}
        # 6. time scales (stride / cadence sync)
        native = self._native_run_speed if is_running else self._native_walk_speed
        gait_ratio = min(speed / native, 1.4)
        if ground_anim:
            ground_anim.time_scale = gait_ratio
        if self.ahead_tread_run is not None:
            self._smooth_tread_run = lerp(self._smooth_tread_run, self.ahead_tread_run, min(1.0, 12 * dt))
        cycle_d = 2 * self._smooth_tread_run
        for a in (up_anim, down_anim):
            if a:
                k = (speed * a.clip.duration) / cycle_d
                a.time_scale = max(0.2, min(k, 3.0))
        if self.gait_sync == 'distance':
            self._distance_match(dt, speed, (walk_a, run_a), (su_a, sd_a, sru_a, srd_a), is_running)
        # the small-stair phase lock (the original's: descent, small stairs; distance matching does every shape)
        self._stair_phase_lock_info = None
        lock_on = self._small_stair_phase_lock and not isolated and (
            self.ahead_stair_shape == 'small' or (self.gait_sync == 'distance' and self.ahead_stair_shape is not None))
        if lock_on:
            uw = up_anim.weight if up_anim else 0.0
            dw = down_anim.weight if down_anim else 0.0
            direction = 'down' if dw > uw else 'up'
            pa = down_anim if direction == 'down' else up_anim
            pw = dw if direction == 'down' else uw
            run = self.ahead_tread_run if self.ahead_tread_run is not None else (
                self._last_tread_run if self._last_tread_run is not None else self._smooth_tread_run)
            enabled = (self._small_stair_phase_lock_descent if direction == 'down'
                       else self._small_stair_phase_lock_ascent) or self.gait_sync == 'distance'
            can = (enabled and grounded and moving and recent_step and pa is not None and
                   pw > self._small_stair_phase_min_weight and run is not None and run > 0.08)
            if can:
                trans = ((self.support_frame or {}).get('probes') or {}).get('transition_ds') or []
                nearest = min(trans) if trans else None
                reset = (not self._stair_phase_lock_active or self._stair_phase_lock_dir != direction or
                         self._stair_phase_lock_shape != self.ahead_stair_shape)
                cyc = max(0.01, 2 * run)
                off = self._small_stair_descent_phase_offset if direction == 'down' else self._small_stair_ascent_phase_offset
                if reset:
                    self._stair_phase_distance = euclidean_modulo(run - nearest, run) if nearest is not None else 0.0
                    if self.gait_sync == 'distance' and pa.clip.gait is not None:
                        # the edge fixes the stair clip's phase to one tread's run, half its cycle: of the two feet
                        # that can take the next tread, the one the walk has at the same point of its step where the
                        # stair clip takes over the blend (its share past a half), the stair clip going on at the
                        # tread's pace until then and the walk at the blend's (_distance_match). This edition's: the
                        # foot the walk just put down stays down, the trailing one takes the tread
                        gg = ground_anim.clip.gait if ground_anim is not None else None
                        sw = gg.stride if gg is not None and gg.stride > 0.05 else cyc
                        ws, wg = pa.weight, ground_anim.weight if ground_anim is not None else 0.0
                        wi = idle_a.weight if idle_a is not None else 0.0
                        ds_f = max(0.0, speed * dt)
                        k, adv_w = 0, 0.0
                        while k < 12 and ws < 0.5 * (ws + wg + wi):
                            ws, wg, wi = damp_stair(ws, 1.0), damp(wg, 0.0, base_l, dt), damp(wi, 0.0, base_l, dt)
                            k += 1
                            adv_w += ds_f * (wg / sw + ws / cyc) / max(wg + ws, 1e-6)
                        adv_s = k * ds_f / cyc

                        def stair_ph(d):
                            return pa.clip.phase_at_time(euclidean_modulo(d / cyc + off, 1.0) * pa.clip.duration)

                        def walk_gap(d):
                            return abs(euclidean_modulo(stair_ph(d) + adv_s - self._gait_phase - adv_w + 0.5, 1.0) - 0.5)
                        if walk_gap(self._stair_phase_distance + run) < walk_gap(self._stair_phase_distance):
                            self._stair_phase_distance += run
                    self._stair_phase_lock_active = True
                    self._stair_phase_lock_dir = direction
                    self._stair_phase_lock_shape = self.ahead_stair_shape
                else:
                    if self._stair_phase_cycle and abs(cyc - self._stair_phase_cycle) > 1e-9:
                        # a new tread run (the probes' estimate firming up on the flight) keeps the clip's phase
                        # where it is: the distance is carried over to the new cycle
                        self._stair_phase_distance *= cyc / self._stair_phase_cycle
                    self._stair_phase_distance += max(0.0, speed * dt)
                self._stair_phase_cycle = cyc
                dur = pa.clip.duration
                tn = euclidean_modulo(self._stair_phase_distance / cyc + off, 1.0)
                tt = tn * dur
                pre = euclidean_modulo(tt - (pa.time_scale or 1.0) * dt, dur)
                pa.time = pre
                self._stair_phase_lock_info = {'active': True, 'dir': direction, 'shape': self.ahead_stair_shape,
                                               'run': run, 'nearest_edge_d': nearest,
                                               'distance': self._stair_phase_distance, 'target_norm': tn,
                                               'target_time': tt, 'pre_mixer_time': pre, 'weight': pw}
            else:
                self._stair_phase_lock_active = False
                self._stair_phase_lock_dir = None
                self._stair_phase_lock_shape = None
        else:
            self._stair_phase_lock_active = False
            self._stair_phase_lock_dir = None
            self._stair_phase_lock_shape = None
        if self.gait_sync == 'distance':
            self._hold_stair_clips(dt, (su_a, sd_a, sru_a, srd_a))
            self._follow_stair_phase(dt, (walk_a, run_a), (su_a, sd_a, sru_a, srd_a))
        # 6.5 gestures; 7. the mixer
        self._update_gesture_weights(dt)
        if mixer:
            mixer.update(dt)
            self._sync_pose()
        # 8. pose overrides: hip lean + head pitch
        N = self.pose.N
        climb = self.signed_climb_angle_deg
        lean_f = self._hip_lean_ascent if climb >= 0 else self._hip_lean_descent
        walk_w = ground_anim.weight if ground_anim else 0.0
        gate = max(0.0, min(1.0, walk_w))
        target_lean = abs(climb) * lean_f * gate
        k_lean = min(1.0, dt * 6)
        self._smooth_hips_lean_deg = self._smooth_hips_lean_deg * (1 - k_lean) + target_lean * k_lean
        hips_lean = self._smooth_hips_lean_deg
        if 'hips' in N:
            N['hips'] = Quaternion((1.0, 0.0, 0.0), hips_lean * D2R) @ N['hips']
        if 'head' in self.h.humanoid:
            if self._head_rest_quat is None:
                self._head_rest_quat = N.get('head', Quaternion()).copy()
            bonus = 0.0
            if climb > 0:
                bonus = min(self._head_pitch_bonus_max, climb * 0.5) * walk_w
            elif climb < 0:
                bonus = max(-self._head_pitch_bonus_max, climb * 0.5) * walk_w
            target = climb + bonus
            k_h = min(1.0, dt * 6)
            self._smooth_head_pitch_deg = self._smooth_head_pitch_deg * (1 - k_h) + target * k_h
            local = self._smooth_head_pitch_deg - hips_lean * (_sign(self._smooth_head_pitch_deg) or 1)
            N['head'] = self._head_rest_quat @ Quaternion((1.0, 0.0, 0.0), -local * D2R)
        self.hips_lean_deg = hips_lean
        # 9. the VRM at the feet
        self._place_root(self._heading if self._turning_enabled else math.pi)
        if self._maneuver_visual_sink > 0.005 and self._fading_maneuver_action is not None:
            w = self._fading_maneuver_action.get_effective_weight()
            _lower(self.pose, self._maneuver_visual_sink * min(1.0, w))
            if w < 0.02:
                self._maneuver_visual_sink = 0.0
            if self.ground_y is not None and math.isfinite(self.ground_y):
                st = self.__dict__.setdefault('_post_maneuver_ik', {})
                for side in SIDES:
                    hp = self.pose.world_pos(side + 'Hand') if (side + 'Hand') in self.h.humanoid else None
                    if hp is not None and hp.z < self.ground_y + 0.01:
                        self._solve_arm_ik(side, self._smooth_limb_target(st, side + 'HandPost',
                                                                          Vector((hp.x, hp.y, self.ground_y + 0.02))),
                                           0.65)
        # 10. body Y drop on descent
        angle = self.signed_climb_angle_deg
        on_ramp = self.ahead_tread_run is None and self.ahead_probe_spread < 0.10
        if angle < 0 and ramp_ctx:
            drop = min(self._ramp_body_y_drop_descent_cap, abs(angle) * self._ramp_body_y_drop_descent) * walk_w
        elif angle < 0 and on_ramp:
            drop = min(self._body_y_drop_descent_cap, abs(angle) * self._body_y_drop_descent) * walk_w
        elif angle > 0 and on_ramp:
            drop = min(self._body_y_drop_ascent_cap, angle * self._body_y_drop_ascent) * walk_w
        else:
            drop = 0.0
        sdw = down_anim.weight if down_anim else 0.0
        if not ramp_ctx and angle < 0 and sdw > 0.01 and on_ramp:
            drop += min(self._body_y_drop_stair_ramp_cap, abs(angle) * self._body_y_drop_stair_ramp) * sdw
        k_d = min(1.0, dt * 6)
        self._smooth_body_drop = self._smooth_body_drop * (1 - k_d) + drop * k_d
        _lower(self.pose, self._smooth_body_drop)
        self.anim_pose = self.pose.copy()
        # 11. the foot IK's contexts, then the IK
        if ik:
            fwd_moving = speed > 0.3
            uw = up_anim.weight if up_anim else 0.0
            dw = down_anim.weight if down_anim else 0.0
            aw = max(uw, dw)
            small_desc = self.ahead_stair_shape == 'small' and dw > 0.05
            shallow_desc = abs(ahead_low) < 0.13 or small_desc
            rise = max(0.001, self.ahead_stair_rise or self._latched_stair_rise or 0.10)
            multi_small = self.ahead_stair_shape == 'small' and ahead_high > rise * 1.35
            small_cur = self.ahead_stair_shape == 'small' and ahead_high > guard and not small_no_future
            early_only = small_early and not small_cur
            small_off_ctx = small_cur or early_only
            single_scale = (self._small_stair_ascent_multi_rise_offset_scale if multi_small
                            else self._small_stair_ascent_single_rise_offset_scale)
            fit_scale = (self._small_stair_ascent_multi_rise_sole_fit_scale if multi_small
                         else self._small_stair_ascent_single_rise_sole_fit_scale)
            off_scale = self._small_stair_ascent_early_offset_scale if early_only else single_scale
            ik.descent_context = (not isolated) and fwd_moving and ahead_low < -0.05 and shallow_desc
            ik.step_clearance_context = isolated
            ik.flat_walk_context = grounded and fwd_moving and not isolated and ramp_ctx
            ik.stair_ascent_sole_fit_context = (bool(self._small_stair_ascent_sole_fit) and not isolated and grounded and
                                                fwd_moving and small_cur and self.ahead_stair_shape == 'small' and
                                                uw > 0.20 and uw > dw)
            ik.stair_ascent_tread_run = ((self.ahead_tread_run if self.ahead_tread_run is not None
                                          else self._last_tread_run) if ik.stair_ascent_sole_fit_context else None)
            ik.stair_ascent_offset_scale = off_scale if small_off_ctx else 0.0
            ik.stair_ascent_sole_fit_max_scale = fit_scale if ik.stair_ascent_sole_fit_context else 0.0
            edge_ctx = (bool(self._small_stair_ascent_edge_align) and not isolated and grounded and fwd_moving and
                        self.ahead_stair_shape == 'small' and uw > 0.12 and uw > dw and
                        (small_cur or early_only or small_early))
            ea = self._update_small_stair_ascent_edge_align_hint(edge_ctx)
            ik.stair_ascent_edge_align_context = bool(ea.get('active'))
            ik.stair_ascent_edge_point = ea.get('point')
            ik.stair_ascent_move_dir = ea.get('dir')
            ik.stair_ascent_edge_tread_run = ea.get('run') if ea.get('run') is not None else (
                self.ahead_tread_run if self.ahead_tread_run is not None else self._last_tread_run)
            if self.support_frame is not None:
                self.support_frame['stair_ascent_edge_align'] = ea
            ik.ramp_foot_clearance_offset = self._ramp_foot_clearance_offset if (ramp_ctx and sgn < -0.5) else 0.0
            combined = 0.0
            if not isolated and uw > dw and (recent_step or small_early):
                if (self.ahead_stair_shape == 'small' and small_cur) or early_only:
                    combined = self._foot_offset_ascent * self._foot_offset_ascent_small_scale * off_scale * aw
            elif not isolated and dw > 0.05 and recent_step:
                if self.ahead_lowest_delta < -0.05:
                    mag = {'small': self._foot_offset_descent_small, 'normal': self._foot_offset_descent_normal,
                           'large': self._foot_offset_descent_large}.get(self.ahead_stair_shape)
                    if mag is None:
                        mag = max(0.20, min(0.40, 0.43 - 0.9 * abs(self.ahead_lowest_delta)))
                    combined = mag * aw
            ik.foot_plant_forward_offset = combined
            if not hasattr(ik, '_gpt_default_extra_cast_reach_scale'):
                ik._gpt_default_extra_cast_reach_scale = ik.extra_cast_reach_scale if ik.extra_cast_reach_scale is not None \
                    else 0.5
            large_up = (not isolated and uw > 0.05 and recent_step and self.ahead_stair_shape == 'large' and
                        ahead_high > 0.05)
            ik.extra_cast_reach_scale = 1.0 if (self._large_stair_full_toe_reach and large_up) \
                else ik._gpt_default_extra_cast_reach_scale
            ik.increased_accuracy = True
            if grounded:
                ik.update(dt, self.pose)
                fsy, src = None, None
                if ik.can_reach_targets and recent_step:
                    ml = math.hypot(in_x, in_y)
                    if ml > 1e-4:
                        fp = ik.directional_foot_height(Vector((in_x / ml, in_y / ml, 0.0)))
                        fsy, src = fp.z, 'directionalFoot'
                    else:
                        fsy, src = ik.lowest_foot_height, 'lowestFoot'
                if fsy is not None and math.isfinite(fsy):
                    if self._last_foot_support_y is not None and abs(fsy - self._last_foot_support_y) <= 0.04:
                        self._foot_support_stable_frames += 1
                    else:
                        self._foot_support_stable_frames = 1
                    self._last_foot_support_y = fsy
                    self._foot_support_observation = {
                        'y': fsy, 'source': src, 'stable_frames': self._foot_support_stable_frames,
                        'stable': self._foot_support_stable_frames >= self._foot_support_root_stable_frames,
                        'can_reach_targets': bool(ik.can_reach_targets)}
                    self.external_ground_y = fsy
                else:
                    self._foot_support_stable_frames = 0
                    self._last_foot_support_y = None
                    self._foot_support_observation = None
                    self.external_ground_y = None
            else:
                self._foot_support_stable_frames = 0
                self._last_foot_support_y = None
                self._foot_support_observation = None
                self.external_ground_y = None

    # ================================================================================================ distance matching
    def _distance_match(self, dt, speed, ground, stairs, is_running):
        """gait_sync='distance': walk and run share one normalized phase (0 = the left strike), advanced by the ground
        covered over the blended stride (the stair clips' cycle of two treads in the blend while they carry weight);
        each clip's time is set from it (its time_scale only carries the mixer's step).
        A start from standing begins a little before a passing phase (the swing foot beside the planted one, as the idle
        stands); with self.stop_distance set (the film's follower: the ground left to a stop) the phase is spread over
        that distance so the stop lands on the nearest passing phase (distance matching to a stop). Walking backward
        (self.backward) the ground covered counts negative: the clip runs backward through the same stances"""
        sgn = -1.0 if self.backward else 1.0
        ds = max(0.0, speed * dt) * sgn
        self._distance += ds
        act = [(a, a.weight) for a in ground if a is not None and a.clip.gait is not None and a.clip.gait.stride > 0.05]
        wsum = sum(w for _a, w in act)
        a0 = ground[1] if (is_running and ground[1] is not None) else ground[0]
        if wsum > 1e-3:
            stride = sum(a.clip.gait.stride * w for a, w in act) / wsum
        else:
            stride = a0.clip.gait.stride if (a0 is not None and a0.clip.gait is not None) else 1.0
        own = stride
        st_on = sum(a.weight for a in stairs if a is not None and a.clip.gait is not None)
        crossfade = wsum > 1e-3 and st_on > 1e-3
        if crossfade:
            # a crossfade with the stair clips (a cycle of two treads, the walk's stride two to three times as long):
            # the shared phase goes on at the weight-blended pace of every clip playing, so the walk's steps quicken
            # as a flight takes over
            stride = (wsum + st_on) / (wsum / stride + st_on / self._stair_cycle())
        if self._stair_pace is not None and stride > self._stair_pace:
            # off a flight the stride grows back to the walk's (or the run's) over about a step: the first step off
            # the stairs is as quick and short as theirs, so the trailing foot leaves the foot of the flight as the
            # other lands, and the next step is the gait's own
            stride = min(stride, self._stair_pace + STRIDE_GROWTH * abs(ds))
        self._stair_pace = stride if crossfade or (self._stair_pace is not None and stride < own - 1e-6) else None
        dom = max(act, key=lambda x: x[1])[0] if act else None
        lead = dom if dom is not None else a0
        passing = sorted(lead.clip.gait.passing.values()) if (lead is not None and lead.clip.gait is not None and
                                                              getattr(lead.clip.gait, 'passing', None)) else []
        st_w = sum(a.weight for a in stairs if a is not None)
        if wsum < 0.05 and getattr(self, '_ground_wsum_last', 0.0) < 0.05 and st_w < 0.05 and passing:
            self._gait_phase = (passing[0] - 0.08 * sgn) % 1.0      # a start from standing (not off the stairs)
        self._ground_wsum_last = wsum
        d_stop = getattr(self, 'stop_distance', None)
        if d_stop is not None and passing and d_stop < 2.2 * stride and ds != 0:
            want = max(d_stop, 1e-3) / stride
            # the phase still to go to each passing phase, in the travel's sense (backward: the phase decreasing)
            cands = [((sgn * (pp - self._gait_phase)) % 1.0) + k for pp in passing for k in (0, 1, 2)]
            ok = [c for c in cands if c >= 0.5 * want] or [want]
            dphi = min(ok, key=lambda c: abs(c - want))
            step = dphi if abs(ds) >= d_stop else abs(ds) * dphi / max(d_stop, 1e-6)
            self._gait_phase = (self._gait_phase + sgn * step) % 1.0
        elif dom is not None and dom.weight > 0.9 and st_on <= 1e-3 and self._stair_pace is None:
            c = dom.clip
            self._gait_phase = c.phase_at_travel(c.travel_at_phase(self._gait_phase) + ds)
        else:
            self._gait_phase = (self._gait_phase + ds / max(stride, 1e-3)) % 1.0
        for a in ground:
            if a is None or a.clip.gait is None:
                continue
            a.time = a.clip.time_at_phase(self._gait_phase)
            a.time_scale = 0.0

    def _stair_cycle(self):
        """the stair clips' cycle along the ground (m): two treads, the tread lock's on a flight, else the smoothed run"""
        if self._stair_phase_lock_active and self._stair_phase_cycle:
            return self._stair_phase_cycle
        return max(0.01, 2.0 * self._smooth_tread_run)

    def _hold_stair_clips(self, dt, stairs):
        """this edition's (distance matching): a stair clip that is not playing (its weight under STAIR_REST_UNDER) is
        held at the shared phase, so it comes in where the walk is in its cycle, the same foot down and the same foot
        swinging; playing, it keeps its own clock (the tread lock's on a flight). Its time is set before the mixer's
        step, which then carries it onto this frame's phase"""
        for a in stairs:
            if a is None or a.clip.gait is None or a.weight >= STAIR_REST_UNDER:
                continue
            a.time = euclidean_modulo(a.clip.time_at_phase(self._gait_phase) - (a.time_scale or 0.0) * dt,
                                      a.clip.duration)

    def _follow_stair_phase(self, dt, ground, stairs):
        """this edition's (distance matching): the stair clips keep their own clock (the tread-locked phase), the walk
        and the run the shared one. Once a stair clip leads and the walk and the run have faded under FOLLOW_UNDER, the
        shared phase follows it (its time after this frame's mixer step), so a hand-back from the stairs re-enters the
        walk where the stairs are in the cycle, the same foot down (unfollowed, the walk came back off a dome with the
        other foot planted: neither foot down for eight frames). Not before: a walk still carrying weight would jump its
        phase mid-crossfade and flip the blended stance (a stair's first stance tucked 20 mm deeper)"""
        st = [a for a in stairs if a is not None and a.clip.gait is not None and a.weight > 1e-3]
        if not st:
            return
        lead = max(st, key=lambda a: a.weight)
        gw = sum(a.weight for a in ground if a is not None)
        if lead.weight <= gw or gw > FOLLOW_UNDER:
            return
        t_next = (lead.time + (lead.time_scale or 0.0) * dt) % lead.clip.duration
        self._gait_phase = lead.clip.phase_at_time(t_next)
        for a in ground:
            if a is not None and a.clip.gait is not None:
                a.time = a.clip.time_at_phase(self._gait_phase)
                a.time_scale = 0.0

    # ================================================================================================ turn on the spot
    def turn_on_spot(self, angle, clip=None, fade=0.15):
        """this edition's: turn by `angle` rad (+ = left, counter-clockwise from above) on the spot, playing turnLeft /
        turnRight with the root taking the clip's hips yaw scaled to the angle; -> the turn's duration (s) or None"""
        slot = clip or ('turnLeft' if angle > 0 else 'turnRight')
        a = self._actions.get(slot)
        if a is None:
            self.log(f'[eidoverse-controller] turn_on_spot: {slot} not loaded')
            return None
        if a.get_effective_weight() > 0.05:
            # a turn straight after the same turn: three's mixer binds one action per clip, so the clip would jump back
            # to its start; a twin action (a second clip object over the same data) crossfades from the last one
            import copy
            key = slot + '#twin'
            b = self._actions.get(key)
            if b is None:
                b = self._mixer.clip_action(copy.copy(a.clip)).set_loop(LOOP_ONCE)
                b.clamp_when_finished = True
                b.play()
                b.set_effective_weight(0.0)
                self._actions[key] = b
            if b.get_effective_weight() <= a.get_effective_weight():
                a = b
        total = a.clip.total_root_yaw
        if abs(total) < 0.1:
            return None
        scale = angle / total
        a.reset()
        a.set_loop(LOOP_ONCE)
        a.clamp_when_finished = True
        a.time_scale = 1.0
        a.weight = max(a.weight, 0.0)
        a.play()
        self._turn = {'action': a, 'slot': slot, 'scale': scale, 'h0': self._heading, 'angle': angle, 't': 0.0,
                      'dur': a.clip.duration, 'fade': fade}
        return a.clip.duration

    def _update_turn(self, dt):
        T = self._turn
        a = T['action']
        T['t'] += dt
        self.mode = 'turn'
        for b in self._actions.values():
            if b is None:
                continue
            b.weight = damp(b.weight, 1.0 if b is a else 0.0, 14, dt)
        self.update(dt, (0.0, 0.0))
        self._update_gesture_weights(dt, True)
        self._mixer.update(dt)
        self._sync_pose()
        prog = a.clip.root_yaw_progress(min(a.time, a.clip.duration))
        self._heading = T['h0'] + prog * T['scale']
        self._place_root(self._heading)
        self.anim_pose = self.pose.copy()
        if T['t'] >= T['dur']:
            self._heading = T['h0'] + T['angle']
            self._turn = None
            if self._actions.get('idle'):
                self._actions['idle'].weight = max(self._actions['idle'].weight, 0.0)

    @property
    def is_turning(self):
        return self._turn is not None

    # ================================================================================================ maneuver engine
    @property
    def is_maneuvering(self):
        return bool(self._maneuver)

    def set_running(self, v):
        self.running = bool(v)

    # ---- the moves (maneuvers.py): the original's explicit agent-facing API and its planners
    def vault(self):
        """scan along the heading and vault the cover ahead -> started?"""
        return MV.explicit_maneuver(self, 'vault')

    def climb_ledge(self):
        """mount the block ahead (climbLedge; climbWallUp over mount_max_rise) -> started?"""
        return MV.explicit_maneuver(self, 'mount')

    def jump(self, distance=1.4, height=0.45):
        return MV.jump(self, distance=distance, height=height)

    def climb_ladder(self, height=None, rate=0.55, first_rung=0.25, rung_spacing=0.28, time_scale=1.0, standoff=None,
                     rung_radius=None):
        return MV.climb_ladder(self, height=height, rate=rate, first_rung=first_rung, rung_spacing=rung_spacing,
                               time_scale=time_scale, standoff=standoff, rung_radius=rung_radius)

    def climb_wall(self, rate=0.34, time_scale=1.1):
        return MV.climb_wall(self, rate=rate, time_scale=time_scale)

    def _explicit_maneuver(self, kind):
        return MV.explicit_maneuver(self, kind)

    def _start_vault_over(self, scan, ob, fx, fy):
        return MV.start_vault_over(self, scan, ob, fx, fy)

    def _start_mount_onto(self, scan, ob, fx, fy, slot='climbLedge'):
        return MV.start_mount_onto(self, scan, ob, fx, fy, slot)

    def _start_gap_jump(self, scan, gap, fx, fy):
        return MV.start_gap_jump(self, scan, gap, fx, fy)

    def _start_wall_scramble(self, scan, ob, fx, fy, rate=0.34, time_scale=1.1):
        return MV.start_wall_scramble(self, scan, ob, fx, fy, rate=rate, time_scale=time_scale)

    def _apply_world_delta_to_bone_cc(self, name, delta):
        """_applyWorldDeltaToBoneCC: a world-space turn applied to a bone through its parent"""
        self.pose.apply_world_delta(name, delta)

    def _scan_path_ahead(self, fx, fy):
        """dense downward probes along the travel direction (the maneuver planner's view)"""
        cur = self._center
        feet_y = cur.z - self.half_height - self.hip_y
        oz = cur.z + self.half_height + 3.0
        step = self.maneuver_scan_step
        N = max(6, int(math.ceil(self.maneuver_scan_range / step)))
        return {'feet_y': feet_y, 'fx': fx, 'fy': fy, 'x': cur.x, 'y': cur.y,
                'samples': [{'d': i * step, 'y': self._ground_vector(cur.x + fx * i * step, cur.y + fy * i * step, oz)}
                            for i in range(1, N + 1)]}

    def _face_distance(self, scan, start_d, rise):
        """this edition's: an obstacle's near face measured exactly, level rays along the scan from the body's axis at a
        quarter, a half and three quarters of its rise (at most 1.2 m up). The scan's samples step maneuver_scan_step
        (0.15 m), so its start_d lies up to a step past the face; a lip, a rung line or a prop placed from it hung up to
        15 cm off the real one. -> the distance (m), or start_d when no face answers between the last sample before it
        and it"""
        if 'fx' not in scan:
            return start_d
        d = Vector((scan['fx'], scan['fy'], 0.0))
        best = None
        for k in (0.25, 0.5, 0.75):
            z = scan['feet_y'] + min(1.2, max(0.06, k * rise))
            h = self.world.ray_cast(Vector((scan['x'], scan['y'], z)), d, start_d + 0.02)
            if h.hit and abs(h.normal.z) < 0.5 and h.distance > start_d - self.maneuver_scan_step - 0.02:
                best = h.distance if best is None else min(best, h.distance)
        return best if best is not None else start_d

    def _classify_path_ahead(self, scan):
        """at most one OBSTACLE (a single-step vertical jump of 0.40 m or more) and one GAP (a deep void back to level)"""
        feet_y, samples = scan['feet_y'], scan['samples']
        edge_min = 0.40
        obstacle = None
        prev = feet_y
        for i, s in enumerate(samples):
            if s['y'] is None:
                prev = None
                continue
            if prev is not None:
                dy = s['y'] - prev
                if dy >= edge_min and (s['y'] - feet_y) >= self.vault_min_rise:
                    top, end_d, j = s['y'], s['d'], i + 1
                    while j < len(samples):
                        t = samples[j]
                        if t['y'] is None or t['y'] - feet_y < self.vault_min_rise * 0.5:
                            break
                        top, end_d = max(top, t['y']), t['d']
                        j += 1
                    landing = next((t for t in samples[j:] if t['y'] is not None and abs(t['y'] - feet_y) <= 0.35), None)
                    last_d = samples[-1]['d']
                    obstacle = {'start_d': s['d'], 'end_d': end_d, 'depth': end_d - s['d'] + self.maneuver_scan_step,
                                'top_y': top, 'rise': top - feet_y, 'landing_d': landing['d'] if landing else None,
                                'landing_y': landing['y'] if landing else None,
                                'plateau': end_d >= last_d - 1e-6 or landing is None,
                                'face_d': self._face_distance(scan, s['d'], top - feet_y)}
                    break
            prev = s['y']
        gap = None
        if obstacle is None or obstacle['start_d'] > 0.6:
            g_start, deep, rel_prev = None, 0, 0.0
            for s in samples:
                if obstacle and s['d'] >= obstacle['start_d']:
                    break
                rel = None if s['y'] is None else s['y'] - feet_y
                if g_start is None:
                    if rel is not None and rel < -self.fall_threshold:
                        if abs(rel_prev) > 0.12:
                            break
                        g_start, deep = s['d'], 1
                    elif rel is not None and abs(rel) > 0.30:
                        break
                    elif rel is not None:
                        rel_prev = rel
                elif rel is None or rel < -self.fall_threshold:
                    if rel is not None:
                        deep += 1
                elif abs(rel) <= 0.30:
                    width = s['d'] - g_start
                    if deep >= 2 and width >= 0.45:
                        gap = {'start_d': g_start, 'width': width, 'landing_d': s['d'], 'landing_y': s['y']}
                    break
                else:
                    break
        return {'obstacle': obstacle, 'gap': gap, 'feet_y': feet_y}

    def _maybe_auto_maneuver(self, fx, fy, speed):
        """the auto-trigger: obstacles and gaps along the travel direction start a registered maneuver (self.maneuvers:
        'vault', 'mount' (climbLedge / climbWallUp), 'wall_scramble', 'gap_jump'); extra planners run after"""
        if not self.maneuvers and not self.maneuver_planners:
            return False
        hard_guard = self._maneuver_cooldown_t > max(0.0, self.maneuver_cooldown - 0.15)
        gap_cooled = self._maneuver_cooldown_t <= 0
        if hard_guard:
            return False
        if self.ground_y is not None and math.isfinite(self.ground_y):
            feet_now = self._center.z - self.half_height - self.hip_y
            if self.ground_y - feet_now > 0.22:
                return False
        scan = self._scan_path_ahead(fx, fy)
        cl = self._classify_path_ahead(scan)
        ob, gap = cl['obstacle'], cl['gap']
        ob_trig = 0.35 + speed * 0.30
        gap_trig = 0.28 + speed * 0.14
        M = self.maneuvers
        if ob and ob['start_d'] <= ob_trig:
            if (not ob['plateau'] and ob['rise'] <= self.vault_max_rise and ob['depth'] <= self.vault_max_depth and
                    ob['landing_d'] is not None and 'vault' in M):
                return bool(M['vault'](self, scan, ob, fx, fy))
            if ob['rise'] <= self.mount_max_rise and 'mount' in M:
                return bool(M['mount'](self, scan, ob, fx, fy, 'climbLedge'))
            if ob['rise'] <= self.wall_climb_max_rise and 'mount' in M:
                return bool(M['mount'](self, scan, ob, fx, fy, 'climbWallUp'))
            if ob['rise'] <= self.wall_scramble_max_rise and 'wall_scramble' in M:
                return bool(M['wall_scramble'](self, scan, ob, fx, fy))
            return False
        if gap and self.jump_auto_gap and gap_cooled and gap['width'] <= self.jump_max_gap and \
                gap['start_d'] <= gap_trig and 'gap_jump' in M:
            return bool(M['gap_jump'](self, scan, gap, fx, fy))
        for p in self.maneuver_planners:
            if p(self, fx, fy, speed):
                return True
        return False

    def _start_maneuver(self, spec):
        """_startManeuver: a one-shot (or looped) clip over a keypoint root path; the clip's hips position is stripped,
        so the path is the root"""
        slots = [spec['slot']] + list(spec.get('slot_fallbacks') or [])
        action, used = None, None
        for s in slots:
            if self._actions.get(s):
                action, used = self._actions[s], s
                break
        if action is None:
            self.log(f"[eidoverse-controller] maneuver '{spec['type']}' skipped: clip '{spec['slot']}' not loaded")
            return False
        clip_dur = action.clip.duration or 1.0
        if spec.get('duration') == 'clip':
            cl = spec.get('duration_clamp', (0.5, 3.0))
            duration = max(cl[0], min(cl[1], clip_dur))
        else:
            duration = spec.get('duration') or min(1.25, clip_dur)
        action.reset()
        c0, c1 = spec.get('clip_window', (0.0, 1.0))
        action.set_loop(LOOP_REPEAT if spec.get('loop') else LOOP_ONCE, math.inf)
        action.clamp_when_finished = not spec.get('loop')
        action.time_scale = spec.get('time_scale', 1.0) if spec.get('loop') else ((c1 - c0) * clip_dur / duration)
        action.play()
        if c0 > 0:
            action.time = c0 * clip_dur
        self._active_gesture = None
        self._maneuver = dict(spec, slot=used, duration=duration, t=0.0, action=action)
        self._blocked_frames = 0
        self._fading_maneuver_action = None
        self.log(f"[eidoverse-controller] maneuver {spec['type']} ({used}) dur={duration:.2f}s")
        return True

    @staticmethod
    def _sample_maneuver_path(path, u):
        """keypoints {u, x, y, z}: linear across, ease-out rising / ease-in falling (or 'linear') vertically"""
        if u <= path[0]['u']:
            return path[0]
        for i in range(1, len(path)):
            if u <= path[i]['u']:
                a, b = path[i - 1], path[i]
                t = (u - a['u']) / max(1e-6, b['u'] - a['u'])
                ts = t if b.get('ease') == 'linear' else ((1 - (1 - t) * (1 - t)) if b['z'] >= a['z'] else t * t)
                return {'x': a['x'] + (b['x'] - a['x']) * t, 'y': a['y'] + (b['y'] - a['y']) * t,
                        'z': a['z'] + (b['z'] - a['z']) * ts}
        return path[-1]

    def _update_maneuver(self, dt):
        m = self._maneuver
        self.maneuver_type = m['type']          # this frame's maneuver (telemetry; the record reads it)
        m['t'] += dt
        m['_dt'] = dt
        u = min(1.0, m['t'] / m['duration'])
        if m.get('path'):
            p = self._sample_maneuver_path(m['path'], u)
            m['_cur_feet_y'] = p['z']
            self._center = Vector((p['x'], p['y'], p['z'] + self.hip_y + self.half_height))
            t2 = self._center
            if dt > 0:
                self.speed_actual = math.hypot(t2.x - self._last_x, t2.y - self._last_y) / dt
            self._last_x, self._last_y = t2.x, t2.y
            self._feet_world = Vector((t2.x, t2.y, t2.z - self.half_height - self.hip_y - self.vrm_foot_y))
            self.grounded = True
            self._velocity_y = 0.0
            self._airborne_from_y = None
        else:
            self.update(dt, (0.0, 0.0))
        for a in self._actions.values():
            if a is not None:
                a.weight = damp(a.weight, 1.0 if a is m['action'] else 0.0, 14, dt)
        self._update_gesture_weights(dt, True)
        if self._mixer:
            self._mixer.update(dt)
            self._sync_pose()
        self._place_root(self._heading if self._turning_enabled else math.pi)
        vs = m.get('visual_sink')
        if vs:
            k = min(1.0, max(0.0, (u - vs['u0']) / max(1e-6, vs['u1'] - vs['u0'])))
            m['_sink_now'] = vs['amount'] * (k * k * (3 - 2 * k))
            _lower(self.pose, m['_sink_now'])
        self._apply_maneuver_hand_ik(m, u)
        if self.maneuver_feet_out_of_solids and m['type'] != 'land':
            MV.feet_out_of_solids(self, m)          # this edition's: no foot left inside a wall, a cover or a top
        self.anim_pose = self.pose.copy()           # the frame the film keys: the contact IK is part of the maneuver
        self.support_frame = {'dt': dt, 'maneuver': {'type': m['type'], 'slot': m['slot'], 'u': round(u, 3),
                                                     'duration': m['duration']},
                              'body': {'support_mode': 'maneuver:' + m['type']}, 'probes': None,
                              'terrain': {'mode': 'maneuver:' + m['type']}, 'animation': None}
        self.external_ground_y = None
        if u >= 1:
            if m.get('chain'):
                self._maneuver = None
                self._fading_maneuver_action = m['action']
                ok = False
                try:
                    ok = m['chain']()
                except Exception as e:  # noqa: BLE001 - the original logs and ends the maneuver
                    self.log(f'[eidoverse-controller] chained maneuver failed: {e}')
                if not ok:
                    self._maneuver = m
                    self._end_maneuver()
            else:
                self._end_maneuver()

    def _apply_maneuver_hand_ik(self, m, u):
        """a maneuver's contact IK: the handler registered for its grab type (ctrl.maneuver_hand_ik[type])"""
        g = m.get('grab')
        if not g:
            return
        fn = self.maneuver_hand_ik.get(g.get('type'))
        if fn is not None:
            fn(self, m, u)

    def _end_maneuver(self):
        m = self._maneuver
        self._maneuver = None
        self._maneuver_cooldown_t = self.maneuver_cooldown
        self._fading_maneuver_action = m['action']
        self._maneuver_visual_sink = m.get('_sink_now', 0.0)
        if m.get('path') and m.get('landing_ground_y') is not None:
            self._body_y_target = m['landing_ground_y'] + self.hip_y + self.half_height
            self._y_avg_window.clear()
            self._last_valid_ground_y = m['landing_ground_y']
            self._ground_stale_frames = 0
            self._velocity_y = 0.0
            self._last_body_y = None
            self.ground_y = m['landing_ground_y']
            self.grounded = True
        self._airborne_from_y = None
        self._airborne_time = 0.0
        self.log(f"[eidoverse-controller] maneuver {m['type']} complete")

    # ---- the limb IK the maneuvers and the post-maneuver hands use (_solveLimbIK and its helpers)
    def _smooth_limb_target(self, m, key, target, lerp_k=0.4):
        lt = m.setdefault('_limb_targets', {})
        prev = lt.get(key)
        if prev is None:
            lt[key] = Vector(target)
        else:
            lt[key] = prev.lerp(Vector(target), lerp_k)
        return lt[key]

    def _solve_arm_ik(self, side, target, w):
        self._solve_limb_ik(side + 'UpperArm', side + 'LowerArm', side + 'Hand', target, w)
        if w > 0.01:
            hc = self.__dict__.setdefault('hand_contact', {})
            hc[side] = max(hc.get(side, 0.0), min(1.0, w))      # the plant keeps this hand there (my robot body's arms)

    def _solve_leg_ik(self, side, target, w):
        self._solve_limb_ik(side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', target, w)

    def _solve_limb_ik(self, up, mid, end, target, w):
        H = self.h.humanoid
        if w <= 0.01 or any(n not in H for n in (up, mid, end)):
            return
        p = self.pose
        up_q0, mid_q0 = p.N.get(up, Quaternion()).copy(), p.N.get(mid, Quaternion()).copy()
        a, b, c = p.world_pos(up).copy(), p.world_pos(mid).copy(), p.world_pos(end).copy()
        target = Vector(target)
        if (a - target).length < 0.18:
            return
        lu, ll = (a - b).length, (b - c).length
        dist = min(max((a - target).length, abs(lu - ll) + 0.01), lu + ll - 0.005)
        cos_mid = (lu * lu + ll * ll - dist * dist) / (2 * lu * ll)
        desired = math.acos(max(-1.0, min(1.0, cos_mid)))
        vba, vbc = a - b, c - b
        current = vba.angle(vbc, 0.0)
        axis = vbc.cross(vba)
        if axis.length_squared > 1e-8:
            p.apply_world_delta(mid, Quaternion(axis.normalized(), current - desired))
        c2 = p.world_pos(end).copy()
        p.apply_world_delta(up, (c2 - a).normalized().rotation_difference((target - a).normalized()))
        p.N[up] = up_q0.slerp(p.N[up], w)
        p.N[mid] = mid_q0.slerp(p.N[mid], w)
        p.invalidate()
