"""eidoblend.characters.controller.foot_ik: VRMFootControllerIK, raycast foot planting (foot_ik.js), ported line for line.

Per frame, after the mixer has posed the body: the ground is sampled under each animated foot with a low cast and a toe
cast, the support surface is chosen (the higher hit places the foot), the foot is conformed to the surface normal,
smoothed against last frame and the leg solved with the cosine-rule two-bone IK (a knee plane from the leg itself:
fixKnee). It reads and writes a Pose (pose.py: the WebGPU edition's scene graph) and casts against a CollisionWorld
(world.py: the Rapier world):

    from eidoblend.characters.controller import VRMFootControllerIK, CastType
    ik = VRMFootControllerIK(body, world=world, type=CastType.RAY_AND_SPHERE, sphere_radius=0.015,
                             max_step_height=0.6, foot_height_offset=0.012, mesh_height_offset=foot_z)
    ik.update(dt, pose)                    # pose: the frame's Pose, edited in place
    ik.lowest_foot_height, ik.can_reach_targets, ik.directional_foot_height(move_dir)

The options are the WebGPU edition's in snake_case (MaxStepHeight -> max_step_height, FootHeightOffset ->
foot_height_offset, DistancePower -> distance_power, SmoothingAngle -> smoothing_angle, GlobalSmoothingPower ->
global_smoothing_power), with the same defaults. Its per-frame contexts are set by the controller (locomote): descent_context,
flat_walk_context, step_clearance_context, foot_plant_forward_offset, stair_ascent_* and ramp_foot_clearance_offset.

three.js is Y-up and this is Z-up: every 'y' of the original (heights, upY, normal.y) is z here; the character's forward
(three's +Z through the root's turn) is the root's -Y. One constant of the original assumes 60 fps (the descent
baseline's drift, 0.5 * 0.0167 m a call): kept, as is the rest.

This is the WebGPU behaviour, frame by frame: it follows the animated foot's xy, so a stride that does not match the
body's travel slides. The film bake (plant.py) plants the feet instead; this IK still runs inside the controller for its
ground observations (the contacts the controller's support options read) and as feet='foot_ik'.
"""

import math

from mathutils import Quaternion, Vector

MAX_DISTANCE_POWER = 2
MAX_SMOOTHING_ANGLE = 3
SMOOTHING_POWER = 1
MAX_STEP_HEIGHT = 2
HEIGHT_OFFSET = 0.5
RAD2DEG = 180.0 / math.pi
DEG2RAD = math.pi / 180.0
NORMAL_UP_THRESHOLD = 0.7          # NormalUpThreshold: a surface below this normal z is no ground (a riser, a wall)
UP = Vector((0.0, 0.0, 1.0))


class CastType:
    RAY = 0
    SPHERE = 1
    RAY_AND_SPHERE = 2


class RotationType:
    """the original's enum; only RAW_TARGET is used by its solve (the others are declared and never read)"""
    RAW_TARGET = 0
    ADD_TARGET = 1
    DIRECTION = 2
    ANIMATOR = 3


def _angle_to(a, b):
    """three's Quaternion.angleTo"""
    d = abs(a.dot(b))
    return 2.0 * math.acos(min(1.0, d))


def _apply_axis_angle(v, axis, ang):
    return Quaternion(Vector(axis).normalized(), ang) @ Vector(v)


class Limb:
    """per-leg state: bone names, lengths, the cosine rule's constants, this frame's target and last frame's state"""

    def __init__(self, ik, up, middle, low, extra=None):
        self.ik = ik
        self.up, self.middle, self.low, self.extra = up, middle, low, extra
        p = ik.pose
        a, b, c = p.world_pos(up), p.world_pos(middle), p.world_pos(low)
        self.upper_length = (a - b).length
        self.lower_length = (b - c).length
        self.extra_length = (c - p.world_pos(extra)).length if extra else 0.0
        self.length = self.upper_length + self.lower_length + self.extra_length
        self.upper_length_squared = self.upper_length ** 2
        self.lower_length_squared = self.lower_length ** 2
        self.cosine_rule_numerator_part = self.upper_length_squared + self.lower_length_squared
        self.cosine_rule_denominator = 2.0 * self.upper_length * self.lower_length
        self.distance_from_mesh = 0.0
        self.target_position = Vector()
        self.target_rotation = Quaternion()
        self.last_low_bone_position = c.copy()
        self.last_low_bone_rotation = p.world_quat(low).copy()
        self.last_middle_bone_rotation = p.world_quat(middle).copy()
        self.last_up_bone_rotation = p.world_quat(up).copy()
        self._rotation_history_seeded = False
        self.last_low_bone_animation_position = c.copy()
        self.last_low_bone_animation_rotation = p.world_quat(low).copy()
        self.can_reach_target = False
        self.lowest_hit_point = Vector()
        self._animator_weight = 0.0
        self._min_up_y = math.inf
        self._in_swing = False
        self._swing_phase = 0.0
        self._synthetic_lift = 0.0
        self._last_step_clearance_hit_y = None
        self._step_clearance_drop_phase = 1.0

    @property
    def low_bone_position(self):
        return self.ik.pose.world_pos(self.low).copy()

    @property
    def low_bone_rotation(self):
        return self.ik.pose.world_quat(self.low).copy()

    @low_bone_rotation.setter
    def low_bone_rotation(self, q):
        self.ik.pose.set_world_quat(self.low, q)

    def middle_bone_angle(self, d):
        c = (self.cosine_rule_numerator_part - d * d) / self.cosine_rule_denominator
        return math.acos(max(-1.0, min(1.0, c))) * RAD2DEG

    def lower_bone_angle(self, d):
        c = (d * d + self.lower_length_squared - self.upper_length_squared) / (2.0 * d * self.lower_length)
        return math.acos(max(-1.0, min(1.0, c))) * RAD2DEG

    def upper_bone_angle(self, d):
        c = (d * d + self.upper_length_squared - self.lower_length_squared) / (2.0 * d * self.upper_length)
        return math.acos(max(-1.0, min(1.0, c))) * RAD2DEG


class VRMFootControllerIK:
    def __init__(self, body, pose=None, world=None, **opts):
        from .pose import Pose
        self.opts = opts
        self.body = body
        self.outside_update = opts.get('outside_update', False)
        self.increased_accuracy = opts.get('increased_accuracy', True)
        self.fix_knee = opts.get('fix_knee', True)
        self.foot_constraint = opts.get('foot_constraint', False)
        self.m_max_step_height = opts.get('max_step_height', 0.6)
        self.m_foot_height_offset = opts.get('foot_height_offset', 0.0)
        self.left_enabled = opts.get('left_enabled', True)
        self.right_enabled = opts.get('right_enabled', True)
        self.m_distance_power = opts.get('distance_power', 1)
        self.m_smoothing_angle = opts.get('smoothing_angle', 2)
        self.m_global_smoothing_power = opts.get('global_smoothing_power', 0)
        self.type = opts.get('type', CastType.RAY)
        self.sphere_radius = opts.get('sphere_radius', 0.03)
        self.rotation_type = opts.get('rotation_type', RotationType.RAW_TARGET)
        # the swing arc (a minimum sinusoidal lift through a swing on a flat walk)
        self.swing_arc_height = opts.get('swing_arc_height', 0.20)
        self.swing_duration = opts.get('swing_duration', 0.40)
        self.swing_detect_threshold = opts.get('swing_detect_threshold', 0.005)
        self.step_clearance_arc_height = opts.get('step_clearance_arc_height', 0.12)
        self.step_clearance_drop_min = opts.get('step_clearance_drop_min', 0.035)
        self.step_clearance_drop_max = opts.get('step_clearance_drop_max', 0.24)
        self.step_clearance_drop_lift = opts.get('step_clearance_drop_lift', 0.07)
        self.step_clearance_drop_duration = opts.get('step_clearance_drop_duration', 0.22)
        self.step_clearance_context = False
        self.flat_walk_context = False
        self.descent_context = False
        self.ramp_foot_clearance_offset = 0.0
        self._debug_swing = opts.get('debug_swing', False)
        self._debug_ik = opts.get('debug_ik', False)
        self.foot_plant_forward_offset = opts.get('foot_plant_forward_offset', 0.0)
        self.stair_ascent_sole_fit_context = False
        self.stair_ascent_tread_run = None
        self.stair_ascent_heel_probe_scale = opts.get('stair_ascent_heel_probe_scale', 0.90)
        self.stair_ascent_toe_probe_scale = opts.get('stair_ascent_toe_probe_scale', 0.95)
        self.stair_ascent_sole_fit_tolerance = opts.get('stair_ascent_sole_fit_tolerance', 0.025)
        self.stair_ascent_sole_fit_up_y_max = opts.get('stair_ascent_sole_fit_up_y_max', 0.14)
        self.stair_ascent_sole_fit_step = opts.get('stair_ascent_sole_fit_step', 0.012)
        self.stair_ascent_sole_fit_max = opts.get('stair_ascent_sole_fit_max', 0.14)
        self.stair_ascent_sole_fit_tread_run_scale = opts.get('stair_ascent_sole_fit_tread_run_scale', 0.45)
        self.stair_ascent_sole_fit_extra_scale = opts.get('stair_ascent_sole_fit_extra_scale', 1.05)
        self.stair_ascent_sole_fit_max_scale = 1.0
        self.stair_ascent_offset_scale = 1.0
        self.stair_ascent_toe_guard_rise = opts.get('stair_ascent_toe_guard_rise', 0.085)
        self.stair_ascent_edge_align_context = False
        self.stair_ascent_edge_point = None
        self.stair_ascent_move_dir = None
        self.stair_ascent_edge_tread_run = None
        self.stair_ascent_edge_run_margin_scale = opts.get('stair_ascent_edge_run_margin_scale', 0.18)
        self.stair_ascent_edge_foot_margin_scale = opts.get('stair_ascent_edge_foot_margin_scale', 0.42)
        self.stair_ascent_edge_max_run_scale = opts.get('stair_ascent_edge_max_run_scale', 0.38)
        self.stair_ascent_edge_max_foot_scale = opts.get('stair_ascent_edge_max_foot_scale', 0.90)
        self.stair_ascent_edge_toe_reserve_run_scale = opts.get('stair_ascent_edge_toe_reserve_run_scale', 0.42)
        self.stair_ascent_edge_toe_reserve_foot_scale = opts.get('stair_ascent_edge_toe_reserve_foot_scale', 0.72)
        self.stair_ascent_edge_max_progress_run_scale = opts.get('stair_ascent_edge_max_progress_run_scale', 0.62)
        self.stair_ascent_edge_max_progress_foot_reserve_scale = opts.get('stair_ascent_edge_max_progress_foot_reserve_scale', 0.65)
        self.stair_ascent_edge_back_max_run_scale = opts.get('stair_ascent_edge_back_max_run_scale', 0.42)
        self.stair_ascent_edge_back_max_foot_scale = opts.get('stair_ascent_edge_back_max_foot_scale', 0.90)
        self.stair_ascent_edge_tolerance = opts.get('stair_ascent_edge_tolerance', 0.008)
        self.stair_ascent_edge_up_y_max = opts.get('stair_ascent_edge_up_y_max', 0.14)
        self.extra_cast_reach_scale = opts.get('extra_cast_reach_scale', 0.5)
        self.increased_accuracy_default = self.increased_accuracy
        self.m_incline = 0.85
        self.m_incline_radian = math.acos(self.m_incline)
        self.m_minimal_smooth_distance = 0.005
        self.m_mesh_height_offset = 0.0
        self.m_is_initialized = False
        self.world = world
        self.casts = 0
        # the bind pose: the WebGPU edition measures its legs on the VRM as loaded (rest, root at the origin)
        from mathutils import Matrix
        self.pose = pose if pose is not None else Pose(body, Matrix.Identity(4), {})
        self.initiation()

    # ------------------------------------------------------------------------------------------------ setup
    def initiation(self):
        if self.m_is_initialized:
            return
        H = self.body.h.humanoid
        need = ['leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot']
        if any(n not in H for n in need):
            raise ValueError('[foot-ik] the humanoid has no legs')
        have_toes = 'leftToes' in H and 'rightToes' in H
        p = self.pose
        if have_toes:
            self.m_left_leg = Limb(self, 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'leftToes')
            self.m_right_leg = Limb(self, 'rightUpperLeg', 'rightLowerLeg', 'rightFoot', 'rightToes')
            left_ht = (p.world_pos('leftFoot') - p.world_pos('leftLowerLeg')).length
            right_ht = (p.world_pos('rightFoot') - p.world_pos('rightLowerLeg')).length
            if left_ht <= self.sphere_radius or right_ht <= self.sphere_radius:
                use_r = right_ht / 3 if left_ht > right_ht else left_ht / 3
                self.sphere_radius = max(0.01, use_r)
        else:
            self.m_left_leg = Limb(self, 'leftUpperLeg', 'leftLowerLeg', 'leftFoot')
            self.m_right_leg = Limb(self, 'rightUpperLeg', 'rightLowerLeg', 'rightFoot')
        self.m_mesh_height_offset = self.opts.get('mesh_height_offset', 0.0)
        root_z = p.M.translation.z
        self.m_left_leg.distance_from_mesh = (p.world_pos('leftFoot').z - root_z) - self.m_mesh_height_offset
        self.m_right_leg.distance_from_mesh = (p.world_pos('rightFoot').z - root_z) - self.m_mesh_height_offset
        self.m_is_initialized = True

    @property
    def legs(self):
        return (self.m_left_leg, self.m_right_leg)

    @property
    def max_step_height(self):
        return self.m_max_step_height

    @max_step_height.setter
    def max_step_height(self, v):
        self.m_max_step_height = max(0.0, min(MAX_STEP_HEIGHT, v))

    @property
    def lowest_foot_height(self):
        a, b = self.m_left_leg.lowest_hit_point.z, self.m_right_leg.lowest_hit_point.z
        return a if a < b else b

    @property
    def highest_foot_height(self):
        a, b = self.m_left_leg.lowest_hit_point.z, self.m_right_leg.lowest_hit_point.z
        return a if a > b else b

    @property
    def lowest_foot_position(self):
        L, R = self.m_left_leg, self.m_right_leg
        return (L if L.lowest_hit_point.z < R.lowest_hit_point.z else R).lowest_hit_point.copy()

    def directional_foot_height(self, move_direction):
        root = self.pose.M.translation
        d = Vector(move_direction)
        left = (self.m_left_leg.low_bone_position - root).dot(d)
        right = (self.m_right_leg.low_bone_position - root).dot(d)
        return (self.m_left_leg if left > right else self.m_right_leg).lowest_hit_point.copy()

    @property
    def can_reach_targets(self):
        return self.m_left_leg.can_reach_target and self.m_right_leg.can_reach_target

    # ------------------------------------------------------------------------------------------------ per frame
    def _update_swing_phase(self, dt):
        enabled = bool(self.flat_walk_context) or bool(self.step_clearance_context)
        l_y = self.m_left_leg.low_bone_position.z
        r_y = self.m_right_leg.low_bone_position.z
        thr = self.swing_detect_threshold
        swing_dur = max(0.05, self.swing_duration)
        peak = self.step_clearance_arc_height if self.step_clearance_context else self.swing_arc_height
        k = min(1.0, dt * 20.0)
        for leg in self.legs:
            this_y = l_y if leg is self.m_left_leg else r_y
            other_y = r_y if leg is self.m_left_leg else l_y
            swinging = enabled and (this_y > other_y + thr)
            if swinging:
                leg._in_swing = True
                leg._swing_phase = min(1.0, leg._swing_phase + dt / swing_dur)
            else:
                leg._in_swing = False
                leg._swing_phase = 0.0
            target = peak * math.sin(leg._swing_phase * math.pi) if leg._in_swing else 0.0
            leg._synthetic_lift = (leg._synthetic_lift or 0.0) * (1.0 - k) + target * k
        if self._debug_swing:                                 # the original's debugSwing line, every 5th frame
            self._swing_dbg_count = getattr(self, '_swing_dbg_count', 0) + 1
            if self._swing_dbg_count % 5 == 0:
                L, R = self.m_left_leg, self.m_right_leg
                print(f'[swing] gate={enabled} L.fkY={l_y:.3f} R.fkY={r_y:.3f} dLR={l_y - r_y:.4f} | L: swing={L._in_swing} '
                      f'phase={L._swing_phase:.2f} lift={L._synthetic_lift:.3f} | R: swing={R._in_swing} '
                      f'phase={R._swing_phase:.2f} lift={R._synthetic_lift:.3f}')

    def foot_ik(self, dt):
        self.pose.invalidate()
        self._update_swing_phase(dt)
        for leg in self.legs:
            if leg._rotation_history_seeded:
                continue
            leg.last_up_bone_rotation = self.pose.world_quat(leg.up).copy()
            leg.last_middle_bone_rotation = self.pose.world_quat(leg.middle).copy()
            leg.last_low_bone_rotation = self.pose.world_quat(leg.low).copy()
            leg._rotation_history_seeded = True
        if self.left_enabled:
            self.set_position_rotation_from_ray_cast(self.m_left_leg)
            self.smoothing(self.m_left_leg, dt)
            self.foots_placement(self.m_left_leg)
        if self.right_enabled:
            self.set_position_rotation_from_ray_cast(self.m_right_leg)
            self.smoothing(self.m_right_leg, dt)
            self.foots_placement(self.m_right_leg)
        self.global_smoothing(self.m_left_leg)
        self.global_smoothing(self.m_right_leg)
        self.saving_position_rotation(self.m_left_leg)
        self.saving_position_rotation(self.m_right_leg)

    def update(self, dt, pose=None):
        """call once per frame after the mixer (pose: the frame's Pose, else the last one given)"""
        if pose is not None:
            self.pose = pose
        if not self.m_is_initialized:
            return
        self.foot_ik(dt)

    # ------------------------------------------------------------------------------------------------ casts
    def raycast_down(self, origin, dist):
        if self.world is None:
            return {'hit': False}
        self.casts += 1
        h = self.world.raycast_down(Vector(origin), dist)
        if not h.hit:
            return {'hit': False}
        return {'hit': True, 'point': Vector((origin[0], origin[1], origin[2] - h.distance)), 'normal': h.normal.copy(),
                'distance': h.distance}

    def sphere_cast_down(self, origin, radius, dist):
        if self.world is None:
            return {'hit': False}
        self.casts += 1
        h = self.world.sphere_cast_down(Vector(origin), radius, dist, min_normal=NORMAL_UP_THRESHOLD)
        if not h.hit:
            return {'hit': False}
        return {'hit': True, 'point': h.point.copy(), 'normal': h.normal.copy(), 'distance': h.distance}

    def cast(self, origin, dist):
        if self.type == CastType.RAY:
            return self.raycast_down(origin, dist)
        if self.type == CastType.SPHERE:
            return self.sphere_cast_down(origin, self.sphere_radius, dist)
        r = self.raycast_down(origin, dist)
        if r['hit'] and r['normal'].z > NORMAL_UP_THRESHOLD:
            return r
        return self.sphere_cast_down(origin, self.sphere_radius, dist)

    # ------------------------------------------------------------------------------------------------ targets
    def _root(self):
        M = self.pose.M
        return M.translation.copy(), M.to_quaternion()

    def set_position_rotation_from_ray_cast(self, limb):
        root_pos, _rq = self._root()
        low_pos = limb.low_bone_position
        current_height = low_pos.z - root_pos.z
        limb._animator_weight = current_height - limb.distance_from_mesh - self.m_mesh_height_offset
        fox = foy = 0.0
        limb._stair_ascent_sole_fit_nudge = 0.0
        limb._stair_ascent_sole_fit_status = None
        limb._stair_ascent_edge_align_nudge = 0.0
        limb._stair_ascent_edge_align_status = None
        limb._foot_plant_forward_offset_scalar = 0.0
        limb._foot_plant_forward_offset_distance = 0.0
        if abs(self.foot_plant_forward_offset) > 0.001 and limb.extra and limb.extra_length > 0.01:
            ex = self.pose.world_pos(limb.extra)
            dx, dy = ex.x - low_pos.x, ex.y - low_pos.y
            ln = math.hypot(dx, dy)
            if ln > 0.001:
                mag = limb.extra_length * self.foot_plant_forward_offset
                limb._foot_plant_forward_offset_scalar = self.foot_plant_forward_offset
                limb._foot_plant_forward_offset_distance = mag
                fox, foy = dx / ln * mag, dy / ln * mag
        origin = Vector((low_pos.x + fox, low_pos.y + foy, low_pos.z + (self.m_max_step_height - current_height)))
        low_result = self.cast(origin, self.m_max_step_height * 2)
        dbg = self._debug_ik and limb is self.m_left_leg

        def fmt(v):
            return f'({v.x:.2f},{v.y:.2f},{v.z:.2f})' if v is not None else 'null'
        if dbg:                                               # the original's debugIK cast lines (the left leg)
            print(f'[foot-ik-raycast] foot={fmt(low_pos)} originZ={origin.z:.2f} lowHit='
                  f'{fmt(low_result["point"]) if low_result["hit"] else "MISS"} normal={fmt(low_result.get("normal"))}')
        if self.increased_accuracy and limb.extra:
            ex = self.pose.world_pos(limb.extra)
            reach = self.extra_cast_reach_scale
            sample = low_pos + (ex - low_pos) * reach
            extra_height = sample.z - root_pos.z
            extra_origin = Vector((sample.x + fox, sample.y + foy, sample.z + (self.m_max_step_height - extra_height)))
            extra_result = self.cast(extra_origin, self.m_max_step_height * 2)
            if dbg:
                print(f'[foot-ik-raycast]   toe={fmt(ex)} toeHit={fmt(extra_result["point"]) if extra_result["hit"] else "MISS"}')
            if low_result['hit'] and extra_result['hit']:
                if low_result['point'].z - root_pos.z > extra_result['point'].z - root_pos.z:
                    self.set_foot_from_low(limb, low_result, extra_result)
                    limb.lowest_hit_point = extra_result['point'].copy()
                else:
                    self.set_foot_from_extra(limb, extra_result, low_result)
                    limb.lowest_hit_point = low_result['point'].copy()
            elif low_result['hit']:
                self.set_foot_from_low(limb, low_result, None)
                limb.lowest_hit_point = low_result['point'].copy()
            elif extra_result['hit']:
                self.set_foot_from_extra(limb, extra_result, None)
                limb.lowest_hit_point = extra_result['point'].copy()
            else:
                limb.can_reach_target = False
        else:
            if low_result['hit']:
                self.set_foot_from_low(limb, low_result, None)
                limb.lowest_hit_point = low_result['point'].copy()
            else:
                limb.can_reach_target = False

    def _up_y(self, limb):
        root_pos, _rq = self._root()
        up_y = (limb.low_bone_position.z - root_pos.z) - limb.distance_from_mesh - self.m_mesh_height_offset
        raw = up_y
        if self.descent_context:
            if up_y < limb._min_up_y:
                limb._min_up_y = up_y
            else:
                limb._min_up_y += 0.5 * 0.0167
            up_y = max(0.0, up_y - limb._min_up_y)
        else:
            limb._min_up_y = math.inf
        up_y = max(up_y, limb._synthetic_lift)
        if self._debug_ik:                                    # the original's debugIK line
            side = 'L' if limb is self.m_left_leg else 'R'
            print(f'[upY-{side}] raw={raw:.3f} minBase={limb._min_up_y:.3f} synth={limb._synthetic_lift:.3f} '
                  f'effective={up_y:.3f}')
        return up_y

    def set_foot_from_low(self, limb, low_result, extra_result):
        normal = low_result['normal'].copy()
        if extra_result:
            normal = (normal + extra_result['normal']) * 0.5
        if self.foot_constraint:
            normal = self.constrainted_normal(normal)
        up_y = self._up_y(limb)
        foot_h = limb.distance_from_mesh - self.m_foot_height_offset + (self.ramp_foot_clearance_offset or 0.0)
        limb.target_position = low_result['point'] + normal * foot_h + UP * up_y
        sy = self._apply_stair_ascent_edge_align(limb, low_result['point'].z, up_y)
        self._apply_stair_ascent_sole_fit(limb, sy, up_y)
        limb.target_rotation = self._quat_from_up_to_normal(UP, normal) @ limb.low_bone_rotation
        reach = limb.upper_length + limb.lower_length + self.m_max_step_height
        limb.can_reach_target = (self.pose.world_pos(limb.up) - limb.target_position).length <= reach

    def set_foot_from_extra(self, limb, extra_result, low_result):
        normal = extra_result['normal'].copy()
        if low_result:
            normal = (normal + low_result['normal']) * 0.5
        if self.foot_constraint:
            normal = self.constrainted_normal(normal)
        from_up = self._quat_from_up_to_normal(UP, normal)
        ex = self.pose.world_pos(limb.extra).copy()
        low_pos = limb.low_bone_position
        reach_scale = max(0.0, min(1.0, self.extra_cast_reach_scale if self.extra_cast_reach_scale is not None else 1.0))
        foot_dir = (ex - low_pos) * reach_scale
        _rp, rq = self._root()
        fwd = foot_dir.dot(rq @ Vector((0.0, -1.0, 0.0)))
        right = foot_dir.dot(rq @ Vector((1.0, 0.0, 0.0)))
        foot_dir_rot = rq @ Vector((right, -fwd, 0.0))
        on_ground = from_up @ foot_dir_rot
        up_y = self._up_y(limb)
        foot_h = limb.distance_from_mesh - self.m_foot_height_offset + (self.ramp_foot_clearance_offset or 0.0)
        limb.target_position = extra_result['point'] - on_ground + normal * foot_h + UP * up_y
        sy = self._apply_stair_ascent_edge_align(limb, extra_result['point'].z, up_y)
        self._apply_stair_ascent_sole_fit(limb, sy, up_y)
        limb.target_rotation = from_up @ limb.low_bone_rotation
        reach = limb.upper_length + limb.lower_length + self.m_max_step_height
        limb.can_reach_target = (self.pose.world_pos(limb.up) - limb.target_position).length <= reach

    @staticmethod
    def _quat_from_up_to_normal(up, normal):
        return Vector(up).rotation_difference(Vector(normal).normalized())

    def _reground_stair_ascent_edge_target(self, limb, surface_y):
        limb._stair_ascent_edge_surface_y_before = surface_y
        limb._stair_ascent_edge_surface_y_after = surface_y
        limb._stair_ascent_edge_reground_status = 'skipped'
        if surface_y is None or not math.isfinite(surface_y):
            return surface_y
        offset = limb.target_position.z - surface_y
        root_z = self.pose.M.translation.z
        origin = Vector((limb.target_position.x, limb.target_position.y,
                         max(limb.target_position.z, surface_y, root_z) + self.m_max_step_height))
        hit = self.cast(origin, self.m_max_step_height * 2.5)
        if not hit['hit'] or hit['normal'].z <= NORMAL_UP_THRESHOLD:
            limb._stair_ascent_edge_reground_status = 'miss'
            return surface_y
        limb.target_position.z = hit['point'].z + offset
        limb._stair_ascent_edge_surface_y_after = hit['point'].z
        limb._stair_ascent_edge_reground_status = 'hit'
        return hit['point'].z

    def _apply_stair_ascent_edge_align(self, limb, surface_y, up_y):
        limb._stair_ascent_edge_align_nudge = 0.0
        limb._stair_ascent_edge_align_status = None
        limb._stair_ascent_edge_progress_before = None
        limb._stair_ascent_edge_progress_after = None
        limb._stair_ascent_edge_min_progress = None
        if not self.stair_ascent_edge_align_context or not limb.extra or limb.extra_length <= 0.01:
            return surface_y
        if surface_y is None or up_y is None:
            return surface_y
        elevated = up_y > self.stair_ascent_edge_up_y_max
        edge, move = self.stair_ascent_edge_point, self.stair_ascent_move_dir
        if edge is None or move is None:
            return surface_y
        ln = math.hypot(move[0], move[1])
        if ln <= 0.001:
            return surface_y
        dx, dy = move[0] / ln, move[1] / ln
        progress = (limb.target_position.x - edge[0]) * dx + (limb.target_position.y - edge[1]) * dy
        run = self.stair_ascent_edge_tread_run if self.stair_ascent_edge_tread_run is not None else self.stair_ascent_tread_run
        run_margin = run * self.stair_ascent_edge_run_margin_scale if run is not None else math.inf
        foot_margin = limb.extra_length * self.stair_ascent_edge_foot_margin_scale
        min_progress = max(0.015, min(run_margin, foot_margin))
        limb._stair_ascent_edge_progress_before = progress
        limb._stair_ascent_edge_min_progress = min_progress
        tol = self.stair_ascent_edge_tolerance
        if run is not None:
            max_by_run = run * self.stair_ascent_edge_max_progress_run_scale
            max_by_reserve = run - limb.extra_length * self.stair_ascent_edge_max_progress_foot_reserve_scale
            max_progress = max(min_progress, min(max_by_run, max_by_reserve))
            if progress > max_progress + tol:
                back = min(progress - max_progress, run * self.stair_ascent_edge_back_max_run_scale,
                           limb.extra_length * self.stair_ascent_edge_back_max_foot_scale, 0.16)
                if back > tol * 0.25:
                    limb.target_position.x -= dx * back
                    limb.target_position.y -= dy * back
                    limb._stair_ascent_edge_align_nudge = -back
                    limb._stair_ascent_edge_progress_after = progress - back
                    limb._stair_ascent_edge_align_status = ('overreach-capped' if back + 1e-6 < progress - max_progress
                                                            else ('overreach-elevated' if elevated else 'overreach'))
                    return self._reground_stair_ascent_edge_target(limb, surface_y)
        if elevated:
            limb._stair_ascent_edge_align_status = 'elevated-ok'
            limb._stair_ascent_edge_progress_after = progress
            return surface_y
        if progress >= min_progress - tol:
            limb._stair_ascent_edge_align_status = 'already-forward'
            limb._stair_ascent_edge_progress_after = progress
            return surface_y
        run_cap = run * self.stair_ascent_edge_max_run_scale if run is not None else math.inf
        foot_cap = limb.extra_length * self.stair_ascent_edge_max_foot_scale
        max_nudge = max(0.0, min(run_cap, foot_cap, 0.16))
        if run is not None:
            toe_reserve = min(run * self.stair_ascent_edge_toe_reserve_run_scale,
                              limb.extra_length * self.stair_ascent_edge_toe_reserve_foot_scale)
            max_progress = max(min_progress, run - toe_reserve)
            max_nudge = min(max_nudge, max(0.0, max_progress - progress))
        needed = max(0.0, min_progress - progress)
        nudge = min(needed, max_nudge)
        if nudge <= tol * 0.25:
            limb._stair_ascent_edge_align_status = 'toe-reserve' if max_nudge <= 0 else 'no-nudge'
            limb._stair_ascent_edge_progress_after = progress
            return surface_y
        limb.target_position.x += dx * nudge
        limb.target_position.y += dy * nudge
        limb._stair_ascent_edge_align_nudge = nudge
        limb._stair_ascent_edge_progress_after = progress + nudge
        limb._stair_ascent_edge_align_status = 'capped' if nudge + 1e-6 < needed else 'aligned'
        return self._reground_stair_ascent_edge_target(limb, surface_y)

    def _apply_stair_ascent_sole_fit(self, limb, surface_y, up_y):
        limb._stair_ascent_sole_fit_nudge = 0.0
        limb._stair_ascent_sole_fit_status = None
        if not self.stair_ascent_sole_fit_context or not limb.extra or limb.extra_length <= 0.01:
            return
        if surface_y is None or up_y is None:
            return
        if up_y > self.stair_ascent_sole_fit_up_y_max:
            limb._stair_ascent_sole_fit_status = 'swing'
            return
        low_pos = limb.low_bone_position
        ex = self.pose.world_pos(limb.extra)
        d = Vector((ex.x - low_pos.x, ex.y - low_pos.y, 0.0))
        ln = d.length
        if ln <= 0.001:
            return
        d /= ln
        heel_back = limb.extra_length * self.stair_ascent_heel_probe_scale
        toe_ahead = limb.extra_length * self.stair_ascent_toe_probe_scale
        tol = self.stair_ascent_sole_fit_tolerance
        toe_guard = self.stair_ascent_toe_guard_rise
        step = max(0.001, self.stair_ascent_sole_fit_step)
        run_cap = max(0.0, self.stair_ascent_tread_run * self.stair_ascent_sole_fit_tread_run_scale) \
            if self.stair_ascent_tread_run is not None else 0.0
        foot_cap = limb.extra_length * self.stair_ascent_sole_fit_extra_scale
        max_nudge = max(0.0, min(self.stair_ascent_sole_fit_max, max(run_cap, foot_cap)) *
                        max(0.0, min(1.0, self.stair_ascent_sole_fit_max_scale)))
        total, status = 0.0, 'start'
        while total + 1e-6 < max_nudge:
            heel = self.cast(Vector((limb.target_position.x - d.x * heel_back, limb.target_position.y - d.y * heel_back,
                                     surface_y + self.m_max_step_height)), self.m_max_step_height * 2)
            if heel['hit'] and heel['normal'].z > NORMAL_UP_THRESHOLD and heel['point'].z >= surface_y - tol:
                status = 'supported' if total > 0 else 'already-supported'
                break
            toe = self.cast(Vector((limb.target_position.x + d.x * toe_ahead, limb.target_position.y + d.y * toe_ahead,
                                    surface_y + self.m_max_step_height)), self.m_max_step_height * 2)
            if toe['hit'] and toe['normal'].z > NORMAL_UP_THRESHOLD and toe['point'].z > surface_y + toe_guard:
                status = 'toe-guard' if total > 0 else 'toe-guard-start'
                break
            nudge = min(step, max_nudge - total)
            limb.target_position += d * nudge
            total += nudge
            status = 'max'
        limb._stair_ascent_sole_fit_nudge = total
        limb._stair_ascent_sole_fit_status = status

    # ------------------------------------------------------------------------------------------------ smoothing
    def smoothing(self, limb, dt):
        self._apply_step_clearance_drop(limb, dt)
        if limb.can_reach_target and self.m_distance_power > 0:
            anim_d = (limb.last_low_bone_animation_position - limb.low_bone_position).length
            move_d = (limb.last_low_bone_position - limb.target_position).length
            anim_d = max(anim_d, self.m_minimal_smooth_distance)
            factor = (anim_d * (MAX_DISTANCE_POWER - self.m_distance_power)) / move_d if move_d > 1e-6 else 1.0
            u = max(0.0, min(1.0, factor))
            limb.target_position = limb.last_low_bone_position.lerp(limb.target_position, u)
        if limb.can_reach_target and self.m_smoothing_angle > 0:
            anim_a = _angle_to(limb.last_low_bone_animation_rotation, limb.low_bone_rotation) * RAD2DEG
            target_a = _angle_to(limb.last_low_bone_rotation, limb.target_rotation) * RAD2DEG
            t = max(0.0, min(1.0, (anim_a + (MAX_SMOOTHING_ANGLE - self.m_smoothing_angle)) / target_a)) \
                if target_a > 1e-6 else 1.0
            limb.target_rotation = limb.last_low_bone_rotation.slerp(limb.target_rotation, t)
        limb.last_low_bone_animation_position = limb.low_bone_position
        limb.last_low_bone_animation_rotation = limb.low_bone_rotation

    def _apply_step_clearance_drop(self, limb, dt):
        hit_y = limb.lowest_hit_point.z if limb.lowest_hit_point is not None else None
        if not self.step_clearance_context or hit_y is None:
            limb._last_step_clearance_hit_y = None
            limb._step_clearance_drop_phase = 1.0
            return
        prev = limb._last_step_clearance_hit_y
        drop = prev - hit_y if prev is not None else 0.0
        if self.step_clearance_drop_min <= drop <= self.step_clearance_drop_max:
            limb._step_clearance_drop_phase = 0.0
        if limb._step_clearance_drop_phase < 1.0:
            dur = max(0.05, self.step_clearance_drop_duration)
            nxt = min(1.0, limb._step_clearance_drop_phase + dt / dur)
            lift = self.step_clearance_drop_lift * math.sin(nxt * math.pi)
            if lift > 0:
                limb.target_position = limb.target_position + UP * lift
                limb._synthetic_lift = max(limb._synthetic_lift or 0.0, lift)
                limb._in_swing = True
                limb._swing_phase = max(limb._swing_phase or 0.0, nxt)
            limb._step_clearance_drop_phase = nxt
        limb._last_step_clearance_hit_y = hit_y

    def global_smoothing(self, limb):
        if self.m_global_smoothing_power <= 0:
            return
        f = 1.0 - self.m_global_smoothing_power
        p = self.pose
        self._set_world_quat(limb.up, limb.last_up_bone_rotation.slerp(p.world_quat(limb.up), f))
        self._set_world_quat(limb.middle, limb.last_middle_bone_rotation.slerp(p.world_quat(limb.middle), f))
        limb.low_bone_rotation = limb.last_low_bone_rotation.slerp(p.world_quat(limb.low), f)

    def _set_world_quat(self, name, q):
        self.pose.set_world_quat(name, q)

    def saving_position_rotation(self, limb):
        p = self.pose
        limb.last_up_bone_rotation = p.world_quat(limb.up).copy()
        limb.last_middle_bone_rotation = p.world_quat(limb.middle).copy()
        limb.last_low_bone_rotation = p.world_quat(limb.low).copy()
        limb.last_low_bone_position = p.world_pos(limb.low).copy()

    def constrainted_normal(self, normal):
        if normal.z < self.m_incline:
            axis = UP.cross(normal)
            if axis.length_squared < 1e-6:
                return UP.copy()
            return Quaternion(axis.normalized(), self.m_incline_radian) @ UP
        return normal

    # ------------------------------------------------------------------------------------------------ the solve
    def foots_placement(self, limb):
        if not limb.can_reach_target:
            return
        p = self.pose
        _rp, rq = self._root()
        up_pos = p.world_pos(limb.up).copy()
        mid_pos = p.world_pos(limb.middle).copy()
        low_pos = limb.low_bone_position
        target_distance = min((limb.target_position - up_pos).length, limb.upper_length + limb.lower_length - 0.001)
        fwd = rq @ Vector((0.0, -1.0, 0.0))                         # three's root +Z: the character's forward
        if not self.fix_knee:
            third = (mid_pos + low_pos) * 0.5 + fwd * 0.05
        else:
            tv = (mid_pos - up_pos).normalized()
            char_right = rq @ Vector((1.0, 0.0, 0.0))
            ang = tv.angle(char_right, 0.0) * RAD2DEG
            cross = _apply_axis_angle(fwd, UP, -ang * DEG2RAD).normalized()
            rotated = _apply_axis_angle(tv, cross, math.pi / 2)
            third = mid_pos + rotated * limb.length
        target_angle = limb.middle_bone_angle(target_distance)
        source_angle = (low_pos - mid_pos).angle(up_pos - mid_pos, 0.0) * RAD2DEG
        axis = (low_pos - third).cross(up_pos - third)
        if axis.length > 1e-12:
            axis.normalize()
            p.apply_world_delta(limb.middle, Quaternion(axis, (source_angle - target_angle) * DEG2RAD))
        low_after = limb.low_bone_position
        a, b = (low_after - up_pos), (limb.target_position - up_pos)
        if a.length > 1e-9 and b.length > 1e-9:
            p.apply_world_delta(limb.up, a.normalized().rotation_difference(b.normalized()))
        limb.low_bone_rotation = limb.target_rotation

    def _apply_world_delta_to_bone(self, name, delta):
        self.pose.apply_world_delta(name, delta)
