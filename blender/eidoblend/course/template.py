"""eidoblend.course.template: the locomotion scene template (eidoverse/terrain_base.js's setup / renderFrame /
cleanup) for the Blender harness, and the course example (eidoverse/examples/obstacle_course.js) on top of it.

A scene script (eido_blender.py runs it) sets a TERRAIN_CONFIG and hands its hooks to the template, as the engine's
scenes set globalThis.TERRAIN_CONFIG and eval'd terrain_base.js:

    from eidoblend.course import template, PRESETS
    TERRAIN_CONFIG = PRESETS['stairs_small']
    CAMERA_MODE = 'three_quarter'                       # 'side' (the default) | 'three_quarter' | 'hands_closeup'
    def setup(ctx):
        template.setup(ctx, TERRAIN_CONFIG, character='claude_robot', camera_mode=CAMERA_MODE)
    render_frame = template.render_frame
    cleanup = template.cleanup

    def setup(ctx):                                     # the course example, its whole run
        template.setup(ctx, example='obstacle_course')

setup builds the course and the stage (builder.py, stage.py), loads the VRM at the controller's start (Blender
(0, -5, 0), facing +Y) and walks it along the course: the engine's renderFrame called charCtrl.locomote(dt, {z: -1})
every frame (the controller and its foot IK in a Rapier world). Here the same controller (the Blender port,
eidoblend.characters.controller: VRMCharacterController with terrain_base's options and its foot IK, in a
CollisionWorld over the course's colliders: the ladder's rails and rungs are visual, as the engine's were) walks it
once, frame by frame, and the bake keys it (driver='controller', the default: its gait tree takes the steps, ramps
and bumps itself). driver='walk_path' walks round one's walk_path instead (planted feet over the course's own height
function, pelvis='lower' when the course has steps: faster to build, no step adaptation), and
driver(course, handle, scene) -> a report replaces the walk with anything else. A plain walk stops 0.6 m before the
first wall, gap or ladder (those are maneuvers).

example='obstacle_course' runs the course example: its course and bench, its character (aporia, the example's asset),
its follow camera, and with the controller its whole renderFrame direction (direct_example(), the controller's
maneuvers: two vaults, the mount and drop, the run zone and the gap jump, the wall climb and drop, the sit stop on
the bench, the cheer gesture while walking, the ladder, the finale salute toward the camera). direct=False walks
the example's course like a preset instead.

terrain_base gave its controller requireConfirmedStairClips / confirmedStairHoldFrames in the constructor, which does
not read them (only attachLocomotion does): the engine's walks ran without them. The template applies them to
attachLocomotion (TERRAIN_BASE_LOCOMOTION), as the scene meant: without them the controller port's bake sinks the
body at the expanded course's dome. locomotion_opts={} reproduces the engine literally.

variant='stairs_handcloseup' (presets.SCENES) runs one of the engine's variant scenes: its config, camera mode,
character, recolour, telemetry, baked expression and foot IK switch; the clouds scenes' post effect is not ported
(named in the entry, logged here).

Camera modes (the template's, in Blender's axes; b = the body centre, terrain_base's t2 = charCtrl.bodyTranslation:
the controller's capsule centre, hip height plus half the upper body; with walk_path the hips lifted by that half):
    side            at (5, b.y, b.z + 0.2), looking at (b.x, b.y, b.z - 0.5)
    three_quarter   35 degrees from the side toward her front: (b.x + 5 cos 35, b.y + 5 sin 35, b.z + 1), looking at
                    (b.x, b.y, b.z - 0.5)
    hands_closeup   0.8 m to the left hand's side, 5 cm above it, looking at it (falls back to side without hands)
    follow          the course example's: radius 5.2 m (3.4 while maneuvering or at the sit stop), swinging to 46
                    degrees from 2.2 m before the ladder, both damped (THREE.MathUtils.damp), at
                    b.z + 0.45 + 0.07 R, looking 0.3 m below b

Telemetry (LOCOMOTION_TELEMETRY's port): telemetry={'enabled': True, 'sample_every': 1, 'max_frames': None,
'output_path': ..., 'summary_path': ..., 'include_frames': True} (camelCase keys too). With the controller driving,
every field of the engine's _locRecordTelemetry, read off the controller port and its foot IK after each simulated
frame (engine_telemetry): body (centre, feet, speedActual / Input / Scale, grounded, groundY, externalGroundY,
supportMode and the support records, bodyYTarget, bodyVelY, bodyJerkY), support (the climb angles, climbBlocked, the
ahead* probe fields, stairShape, stairRise, footObservation, animation, stairAscentEdgeAlign), actions (idle, walk,
run, stairsUp, stairsDown, fallIdle: weight, timeScale, time) and ik (its contexts and per limb: actual, toe, target,
hit, canReachTarget, inSwing, swingPhase, syntheticLift, animatorWeight, footHeight, targetError(XZ), hitGapY,
soleGapY, toeGroundAngleDeg, the stair-ascent nudges and statuses, the foot-plant offsets, actual / target / hit
speeds). Positions are Blender axes (z up). On top, the port's own measurement: each sole's lowest point on the keyed
mesh and its gap over the course surface (feet: {side: {actual, soleGapY}}). The summary is _locSummarizeTelemetry's
(max / avg of bodyJerkY, speedError, and per side TargetError, TargetErrorXZ, SoleGapY, TargetSpeed, HitSpeed from
the IK, overall and per terrain segment, else per stairShape) plus each side's MeshSoleGapY. With walk_path only the
body and the mesh soles are recorded.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

from .builder import add_bench, build_course
from .presets import EXAMPLES, SCENES
from .stage import course_stage, look_at

CAMERA_MODES = ('side', 'three_quarter', 'hands_closeup', 'follow')
DRIVERS = ('controller', 'walk_path')
ACTIONS = {'idle': 'idle', 'walk': 'walk', 'run': 'run', 'stairsUp': 'stairsUp', 'stairsDown': 'stairsDown',
           'fallIdle': 'fallIdle'}
SIT_PHASES = ('route', 'settle', 'sit')         # the example's sitPhase while it is set (the camera pushes in)
_DEFAULT = object()
_STATE = {}
# the options terrain_base.js gave its VRMCharacterController (snake_case: the port's names; equal to the controller
# port's PRESETS['terrain_base'] less the two flags below)
TERRAIN_BASE_CONTROLLER = {
    'foot_stance_x': 0.11, 'use_contact_support_lift': True, 'contact_support_lift_min': 0.025,
    'contact_support_lift_max': 0.18, 'contact_support_lift_ratio': 0.58, 'contact_support_swing_ratio': 0.32,
    'contact_support_max_ramp_angle': 50, 'use_ik_contact_support_lift': True, 'ik_contact_support_lift_ratio': 0.42,
    'ik_contact_support_swing_ratio': 0.18, 'ik_contact_sole_gap_max': 0.16,
    'allow_raised_support_during_descent': True, 'raised_support_min_lift': 0.045, 'raised_support_ahead_min': 0.035,
    'raised_support_finish_gap': 0.015, 'raised_support_latch_frames': 3, 'raised_support_max_spread': 0.18,
    'use_ik_grounding_grace': True, 'ik_grounding_grace_max_drop': 0.34, 'ik_grounding_grace_max_rise': 0.08,
    'ik_grounding_grace_max_sole_gap': 0.56, 'prefer_walk_on_untreaded_obstacles': True,
    'obstacle_walk_max_rise': 0.18, 'obstacle_walk_max_spread': 0.18, 'body_y_rate_up': 1.35,
    'body_y_rate_down': 1.25, 'y_average_window_size': 3}
# terrain_base passed these two to the controller's CONSTRUCTOR, which never reads them (only attachLocomotion does), so
# the engine's own walks ran without them. The template applies them where they take effect, as the scene meant them:
# without them the controller port's bake sinks the body at the expanded course's dome (keyed hips 0.5 m low, soles 0.3
# to 0.6 m under the surface over frames 200 to 230, measured); with them every sole sample of that walk stays within
# 1 cm. locomotion_opts={} gives the engine's literal behaviour.
TERRAIN_BASE_LOCOMOTION = {'require_confirmed_stair_clips': True, 'confirmed_stair_hold_frames': 12}


def _linear_keys(idb, frame=None):
    """Python keyframe_insert ignores the default-interpolation preference: make the object's keys LINEAR
    (Blender 5's layered actions: through the slot's channelbag). frame: only the key just inserted there (keys go in
    in frame order, so it is each curve's last: one key per curve, not the whole film again on every frame)"""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        cb = None
    for fc in (cb.fcurves if cb is not None else []):
        kps = fc.keyframe_points
        if frame is not None and len(kps) and abs(kps[-1].co.x - frame) < 1e-6:
            kps[-1].interpolation = 'LINEAR'
            continue
        for kp in kps:
            kp.interpolation = 'LINEAR'


def _snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def _num(v, digits=5):
    """_locNum: a finite number rounded, else None"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, digits) if math.isfinite(f) else None


def _vec(v):
    if v is None:
        return None
    return [_num(v[0]), _num(v[1]), _num(v[2])]


def _plain(o):
    """a support-frame record made JSON-safe (Vectors to lists, infinities to None)"""
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, Vector):
        return _vec(o)
    if o is None or isinstance(o, (bool, str)):
        return o
    if isinstance(o, (int, float, np.floating, np.integer)):
        return _num(o)
    return str(o)


def damp(x, y, lam, dt):
    """THREE.MathUtils.damp: a frame-rate independent lerp toward y"""
    return x + (y - x) * (1 - math.exp(-lam * dt))


def camera_pose(mode, body, hand=None, follow=None):
    """the template's camera for a mode -> (position, target), Blender axes; follow = {'R': .., 'A': ..} (radians)"""
    bx, by, bz = body
    if mode == 'hands_closeup' and hand is not None:
        lx, ly, lz = hand
        return (lx - 0.8, ly, lz + 0.05), (lx, ly, lz)
    if mode == 'three_quarter':
        R, a = 5.0, math.radians(35)
        return (bx + R * math.cos(a), by + R * math.sin(a), bz + 1.0), (bx, by, bz - 0.5)
    if mode == 'follow' and follow is not None:
        R, A = follow['R'], follow['A']
        return (bx + R * math.cos(A), by - R * math.sin(A), bz + 0.45 + R * 0.07), (bx, by, bz - 0.30)
    return (5.0, by, bz + 0.2), (bx, by, bz - 0.5)


def _limb(ik, limb, prev, dt, pose):
    """_locLimbTelemetry for one leg of the controller port's foot IK (Blender axes: z up). pose: a copy of the IK's
    pose (its world cache filled here would otherwise outlive the frame in the IK's own)"""
    if limb is None:
        return None
    actual = pose.world_pos(limb.low).copy()
    target = limb.target_position.copy() if limb.target_position is not None else None
    hit = limb.lowest_hit_point.copy() if limb.lowest_hit_point is not None else None
    valid = bool(limb.can_reach_target) and target is not None and hit is not None
    foot_h = (limb.distance_from_mesh or 0.0) - (ik.m_foot_height_offset or 0.0)
    terr = (actual - target).length if valid else None
    terr_xy = math.hypot(actual.x - target.x, actual.y - target.y) if valid else None
    hit_gap = actual.z - hit.z if valid else None
    sole_gap = actual.z - hit.z - foot_h if valid else None

    def speed(key, now):
        p = (prev or {}).get(key)
        return (now - p).length / dt if (valid and p is not None and dt > 0) else None
    toe = pose.world_pos(limb.extra).copy() if limb.extra else None
    toe_ang = (math.degrees(math.atan2(toe.z - actual.z, math.hypot(toe.x - actual.x, toe.y - actual.y)))
               if toe is not None else None)
    rec = {
        'actual': _vec(actual), 'toe': _vec(toe), 'target': _vec(target), 'hit': _vec(hit),
        'canReachTarget': bool(limb.can_reach_target), 'inSwing': bool(getattr(limb, '_in_swing', False)),
        'swingPhase': _num(getattr(limb, '_swing_phase', None)),
        'syntheticLift': _num(getattr(limb, '_synthetic_lift', None)),
        'animatorWeight': _num(getattr(limb, '_animator_weight', None)), 'footHeight': _num(foot_h),
        'targetError': _num(terr), 'targetErrorXZ': _num(terr_xy), 'hitGapY': _num(hit_gap),
        'soleGapY': _num(sole_gap), 'toeGroundAngleDeg': _num(toe_ang),
        'stairAscentSoleFitNudge': _num(getattr(limb, '_stair_ascent_sole_fit_nudge', None)),
        'stairAscentSoleFitStatus': getattr(limb, '_stair_ascent_sole_fit_status', None),
        'stairAscentEdgeAlignNudge': _num(getattr(limb, '_stair_ascent_edge_align_nudge', None)),
        'stairAscentEdgeAlignStatus': getattr(limb, '_stair_ascent_edge_align_status', None),
        'stairAscentEdgeProgressBefore': _num(getattr(limb, '_stair_ascent_edge_progress_before', None)),
        'stairAscentEdgeProgressAfter': _num(getattr(limb, '_stair_ascent_edge_progress_after', None)),
        'stairAscentEdgeMinProgress': _num(getattr(limb, '_stair_ascent_edge_min_progress', None)),
        'stairAscentEdgeRegroundStatus': getattr(limb, '_stair_ascent_edge_reground_status', None),
        'stairAscentEdgeSurfaceYBefore': _num(getattr(limb, '_stair_ascent_edge_surface_y_before', None)),
        'stairAscentEdgeSurfaceYAfter': _num(getattr(limb, '_stair_ascent_edge_surface_y_after', None)),
        'footPlantForwardOffsetDistance': _num(getattr(limb, '_foot_plant_forward_offset_distance', None)),
        'footPlantForwardOffsetScalar': _num(getattr(limb, '_foot_plant_forward_offset_scalar', None)),
        'actualSpeed': _num(speed('actual', actual)),
        'targetSpeed': _num(speed('target', target) if target is not None else None),
        'hitSpeed': _num(speed('hit', hit) if hit is not None else None),
    }
    now = {'actual': actual, 'target': target, 'hit': hit} if valid else None
    return rec, now


def engine_telemetry(c, dt, prev_feet=None):
    """terrain_base's _locRecordTelemetry fields read off the controller port (and its foot IK) right after a
    locomote(): -> (record, the limbs' positions for the next frame's speeds). Blender axes."""
    sf = c.support_frame or {}
    sb = sf.get('body') or {}
    centre = c.body_translation() if callable(getattr(c, 'body_translation', None)) else c.body_translation
    body = {
        'center': _vec(centre), 'feet': _vec(c.feet_world_position), 'speedActual': _num(c.speed_actual),
        'speedInput': _num(getattr(c, '_smooth_fwd_speed', None)), 'speedScale': _num(c.speed_scale),
        'grounded': bool(c.grounded), 'groundY': _num(c.ground_y), 'externalGroundY': _num(c.external_ground_y),
        'supportMode': sb.get('support_mode'),
        'usedFootSupportForRoot': bool(sb.get('used_foot_support_for_root')),
        'blockedUpwardDescentSnap': bool(sb.get('blocked_upward_descent_snap')),
        'raisedSupportDuringDescent': _plain(sb.get('raised_support_during_descent')),
        'ikGroundGrace': _plain(sb.get('ik_ground_grace')), 'bodyYTarget': _num(sb.get('body_y_target')),
        'contactSupport': _plain(sb.get('contact_support')), 'ikContactSupport': _plain(sb.get('ik_contact_support'))}
    support = {
        'climbAngleDeg': _num(c.climb_angle_deg), 'signedClimbAngleDeg': _num(c.signed_climb_angle_deg),
        'climbBlocked': bool(getattr(c, '_climb_blocked', False)),
        'aheadHighestDelta': _num(c.ahead_highest_delta), 'aheadLowestDelta': _num(c.ahead_lowest_delta),
        'aheadProbeSpread': _num(c.ahead_probe_spread), 'aheadTreadRun': _num(c.ahead_tread_run),
        'aheadStepLike': bool(c.ahead_step_like), 'aheadIsolatedObstacle': bool(c.ahead_isolated_obstacle),
        'aheadSmoothRampLike': bool(c.ahead_smooth_ramp_like),
        'aheadTransitionCount': getattr(c, 'ahead_transition_count', None),
        'aheadProbeResidual': _num(c.ahead_probe_residual), 'aheadStepRiseRaw': _num(c.ahead_step_rise_raw),
        'stairShape': c.ahead_stair_shape, 'stairRise': _num(c.ahead_stair_rise),
        'footObservation': _plain(sf.get('foot_observation')), 'animation': _plain(sf.get('animation')),
        'stairAscentEdgeAlign': _plain(sf.get('stair_ascent_edge_align'))}
    acts = getattr(c, '_actions', None) or {}
    actions = {}
    for k, slot in ACTIONS.items():
        a = acts.get(slot)
        actions[k] = None if a is None else {'weight': _num(a.weight), 'timeScale': _num(a.time_scale),
                                             'time': _num(a.time)}
    ik = getattr(c, '_leg_ik', None)
    ik_rec, now = None, {}
    if ik is not None:
        ik_rec = {
            'descentContext': bool(ik.descent_context), 'flatWalkContext': bool(ik.flat_walk_context),
            'stepClearanceContext': bool(ik.step_clearance_context),
            'stairAscentSoleFitContext': bool(ik.stair_ascent_sole_fit_context),
            'stairAscentTreadRun': _num(ik.stair_ascent_tread_run),
            'stairAscentOffsetScale': _num(ik.stair_ascent_offset_scale),
            'stairAscentSoleFitMaxScale': _num(ik.stair_ascent_sole_fit_max_scale),
            'stairAscentEdgeAlignContext': bool(ik.stair_ascent_edge_align_context),
            'stairAscentEdgePoint': _plain(ik.stair_ascent_edge_point),
            'stairAscentMoveDir': _plain(ik.stair_ascent_move_dir),
            'stairAscentEdgeTreadRun': _num(ik.stair_ascent_edge_tread_run),
            'footPlantForwardOffset': _num(ik.foot_plant_forward_offset),
            'rampFootClearanceOffset': _num(ik.ramp_foot_clearance_offset),
            'extraCastReachScale': _num(ik.extra_cast_reach_scale), 'canReachTargets': bool(ik.can_reach_targets)}
        pose = ik.pose.copy()               # read-only: never touch the IK's own pose or its world cache
        for side, limb in (('left', ik.m_left_leg), ('right', ik.m_right_leg)):
            r = _limb(ik, limb, (prev_feet or {}).get(side), dt, pose)
            ik_rec[side], now[side] = (r[0], r[1]) if r is not None else (None, None)
    return {'body': body, 'support': support, 'actions': actions, 'ik': ik_rec, 'mode': c.mode}, now


class CourseScene:
    """The template's state: the course, the stage, the character and its walk, the camera and the telemetry."""

    def __init__(self, scene, config=None, character=_DEFAULT, camera_mode=None, clip='walk', speed=None,
                 walk_to=None, duration=None, telemetry=None, driver='controller', pelvis=None, example=None,
                 materials=None, variant=None, direct=True, locomotion_opts=None, log=print):
        self.scene = scene
        self.example = EXAMPLES.get(example) if isinstance(example, str) else example
        if isinstance(variant, str):
            if variant not in SCENES:
                raise ValueError('variant %r: one of %s' % (variant, ', '.join(sorted(SCENES))))
            variant = SCENES[variant]
        self.variant = variant or {}
        v = self.variant
        ex = self.example or {}
        self.config = config if config is not None else (v.get('config') or ex.get('config'))
        # the example's CAMERA_MODE global is the template's; its own renderFrame replaced that camera with the follow
        self.camera_mode = camera_mode or v.get('camera_mode') or ex.get('render_camera') or ex.get('camera_mode') \
            or 'side'
        if self.camera_mode not in CAMERA_MODES:
            raise ValueError('camera_mode %r: one of %s' % (self.camera_mode, ', '.join(CAMERA_MODES)))
        if not callable(driver) and driver not in DRIVERS:
            raise ValueError('driver %r: one of %s, or a callable' % (driver, ', '.join(DRIVERS)))
        self.character = (v.get('character', ex.get('character', 'claude_robot')) if character is _DEFAULT
                          else character)
        self.clip_name, self.speed = clip, speed
        self.walk_to, self.duration = walk_to, duration if duration is not None else v.get('duration')
        self.driver, self.pelvis = driver, pelvis
        self.direct = bool(direct) and bool(self.example)
        self.locomotion_opts = dict(locomotion_opts if locomotion_opts is not None else TERRAIN_BASE_LOCOMOTION)
        self.materials = materials if materials is not None else v.get('materials')
        tel = telemetry if telemetry is not None else (v.get('telemetry') or {})
        self.telemetry_cfg = {_snake(k): x for k, x in tel.items()}      # LOCOMOTION_TELEMETRY's camelCase too
        self.log = log
        if v.get('post'):
            self.log('[course] variant post effect %r is not ported (the POC scenes\' effects library; not in '
                     'eidoverse/effects_tsl nor eidoblend.look.post): rendered without it' % v['post'])
        self.frames = []
        self._prev = {}
        self._follow = None
        self._log_sec = -1
        self.h = None
        self.report = None
        self.records = {}
        self.engine = {}               # frame -> engine_telemetry record (the controller drove)
        self.flags = {}                # frame -> {'mode', 'phase', 'maneuver'}
        self._phase = None
        self._centre_lift = 0.0

    # ------------------------------------------------------------------------------------------- setup ---
    def setup(self, frame_start=1):
        self.course = build_course(self.config, materials=self.materials, scene=self.scene)
        if self.example and self.example.get('bench'):
            add_bench(self.course, self.example['bench'])
        self.stage = course_stage(self.scene, self.course)
        self.frame_start = frame_start
        if self.character:
            self._load_character()
            self.report = self._walk()
        return self

    def _load_character(self):
        from ..characters import load_vrm
        from ..characters.ground import foot_points
        self.h = load_vrm(self.character, location=self.course.start, rotation=180.0, scene=self.scene)
        bpy.context.view_layer.update()
        zs = [(o.matrix_world @ Vector(c)).z for o in self.scene.objects
              if o.type == 'MESH' and o.parent is self.h.arm for c in o.bound_box]
        hb = self.h.humanoid
        self.hips = hb.get('hips')
        self.left_hand = hb.get('leftHand')
        if zs:                                     # the template's log line
            self.log('%s VRM height=%.3f footY=%.3f' % (self.course.tag, max(zs) - min(zs), min(zs)))
            if self.hips:                          # the capsule centre sits half the upper body over the hips
                hz = (self.h.arm.matrix_world @ self.h.arm.pose.bones[self.hips].head).z
                self._centre_lift = max(0.0, (max(zs) - hz) / 2.0)
        self.feet = foot_points(self.h)
        expr = self.variant.get('expressions') or {}
        if expr:                                   # the clouds scenes baked these into the face for the whole run
            from ..characters import key_expression
            have = getattr(self.h, 'expr', {}) or {}
            for name, w in expr.items():
                if name in have:
                    key_expression(self.h, name, [(self.frame_start, float(w))])
                else:
                    self.log('[course] %s has no expression %r: left out' % (self.character, name))

    def _stop_y(self):
        """how far a walk can go: the course end plus 2 m, or the face of the first segment a walk cannot take
        (a wall, a ladder, a gap: the controller's maneuvers), less 0.6 m"""
        stop = self.course.end_y + 2.0
        for s in self.course.segments:
            if s['kind'] in ('wall', 'ladder', 'gap'):
                stop = min(stop, s['y0'] - 0.6)
                break
        return stop

    def _walk(self):
        if callable(self.driver):
            return self.driver(self.course, self.h, self)
        if self.driver == 'controller':
            return self._walk_controller()
        from ..characters import load_clip, walk_path
        clip = load_clip(self.h, self.clip_name)
        has_steps = any(p.role == 'step' for p in self.course.plan.pieces)
        pelvis = self.pelvis or ('lower' if has_steps else 'stance')
        y0 = self.course.start[1]
        y1 = self.walk_to if self.walk_to is not None else self._stop_y()
        if self.duration is not None:
            v = self.speed or 1.6           # a little over the stock walk's own pace (1.56 m/s on my body): no early stop
            y1 = min(y1, y0 + v * self.duration)
        self.walk_span = (y0, y1)
        rep = walk_path(self.h, clip, [(0.0, y0), (0.0, y1)], self.course.ground(), f0=self.frame_start,
                        speed=self.speed, pelvis=pelvis, log=self.log)
        return rep

    def colliders(self):
        """the course pieces the engine gave Rapier colliders (every solid, the ground, the bench); the ladder's
        rails and rungs were visual"""
        out = [o for o in self.course.objects if o.type == 'MESH' and o.get('eido_collider')]
        if self.course.bench is not None:
            out.append(self.course.bench)
        return out

    def _hook(self, ctrl):
        """snapshot the engine's telemetry fields and the frame's flags after every simulated frame
        (Locomotion.simulate calls locomote once per keyed frame)"""
        self._snaps, self._ik_prev = [], {}
        orig = ctrl.locomote

        def locomote(dt, inp=None):
            out = orig(dt, inp)
            rec, now = engine_telemetry(ctrl, dt, self._ik_prev)
            self._ik_prev = now
            self._snaps.append((rec, {'mode': ctrl.mode, 'phase': self._phase,
                                      'maneuver': (ctrl._maneuver or {}).get('type') if ctrl.mode == 'maneuver'
                                      else None}))
            return out
        ctrl.locomote = locomote

    def _walk_controller(self):
        """terrain_base's renderFrame: the controller (the Blender port) walking forward, +Y, over the course's own
        colliders, simulated frame by frame and keyed; with an example, its whole direction. The noik variant
        (foot_ik False) bakes the raw animation."""
        from ..characters.controller import CollisionWorld, Locomotion
        world = CollisionWorld(self.colliders())
        foot_ik = self.variant.get('foot_ik', True)
        # the maneuvers' feet stay out of every solid, the ladder's rails and rungs too (which the walk does not stand
        # on: they are visual, as the engine's were): the controller's contact_world
        opts = dict(TERRAIN_BASE_CONTROLLER, contact_world=CollisionWorld())
        self.loco = Locomotion(self.h, world, start=self.course.start, heading=math.pi,
                               leg_ik='default' if foot_ik else None, controller_opts=opts,
                               locomotion_opts=dict(self.locomotion_opts), log=self.log)
        self._hook(self.loco.ctrl)
        y0 = self.course.start[1]
        max_s = 600.0
        if self.direct:
            self.direct_example(self.loco)
            self.walk_span = (y0, self.course.end_y)
            if self.duration is not None:
                max_s = float(self.duration)
        else:
            y1 = self.walk_to if self.walk_to is not None else self._stop_y()
            if self.duration is not None:
                v = self.speed or self.loco.native['walk']
                y1 = min(y1, y0 + v * self.duration)
            self.walk_span = (y0, y1)
            self.loco.move_to((0.0, y1), speed=self.speed)
        rep = self.loco.bake(f0=self.frame_start, feet='plant' if foot_ik else 'foot_ik', max_seconds=max_s)
        recs = rep.get('_records', [])
        self.records = {r['f']: r for r in recs}
        if len(self._snaps) != len(recs):
            self.log('[course] telemetry: %d snapshots for %d frames: the engine fields are left out'
                     % (len(self._snaps), len(recs)))
        else:
            for r, (eng, fl) in zip(recs, self._snaps):
                self.engine[r['f']] = eng
                self.flags[r['f']] = fl
        return rep

    def direct_example(self, loco):
        """examples/obstacle_course.js's renderFrame direction as the controller port's film commands (the example
        steered the controller frame by frame; these steer it the same way, with a walk's acceleration and its stops'
        deceleration). From the start: walk over the bump, the 8 degree ramps and the small stairs, the low cover's
        vault and the 1.15 m wall's mount and drop (the controller's own auto maneuvers, which the example left on);
        the run zone (segments 15 to 23: stairs up, the gap jump, stairs down, the chest-high vault); the 2.2 m
        wall's climb and drop; the sit stop (auto maneuvers off from 1.2 m before segment 26, the example's three
        waypoints around the bench, a square-up to the course heading, stand_to_sit back onto the pan, the hold, the
        clip reversed at 1.25x, stopEmote); the cheer gesture over segment 27; the ladder (an explicit 2.5 m climb
        0.55 m from its face; the port's auto trigger reads the ladder block as a wall to scramble, so it is off for
        the approach); the finale: the top platform's middle, and after 0.7 s a salute toward the follow camera."""
        ex, course = self.example, self.course
        seg = course.segment
        z = ex['zones']
        run0, run1 = seg(z['run'][0])['y0'], seg(z['run'][1])['y1']
        sit = seg(z['sit'])
        by = course.bench.location.y if course.bench is not None else (sit['y0'] + sit['y1']) / 2
        ges, lad, top = seg(z['gesture']), seg(z['ladder']), seg(z['finale'])
        st, g, ld, fin = ex['sit_timing'], ex['gesture'], ex['ladder'], ex['finale']
        cam = ex.get('camera', {})

        def phase(p):
            def f(_ctl):
                self._phase = p
            return f

        def auto(on):
            def f(ctl):
                ctl.auto_maneuvers = on
            return f
        loco.follow_path([(0.0, run0)], gait='walk', stop=False)
        loco.follow_path([(0.0, run1)], gait='run', stop=False)
        loco.follow_path([(0.0, sit['y0'] - 1.2)], gait='walk', stop=False)
        loco.call(auto(False))
        loco.follow_path([(0.0, by - 1.6)], gait='walk', stop=False)
        loco.call(phase('route'))
        # the waypoints: three (x, benchZ + dz) -> Blender (x, by - dz)
        loco.follow_path([(x, by - dz) for x, dz in ex['sit_route']], gait='walk')
        loco.call(phase('settle'))
        loco.turn_to(180.0)       # square up to the course heading (three's pi: Blender +Y), damped at 8 / s as the
        loco.call(phase('sit'))   # example's settle (its 0.45 s is what that damping takes over a few degrees)
        loco.sit(hold=st['hold'], down=st['sit_down'], up=st['stand_up'], reverse=True,
                 reverse_speed=st['reverse_speed'], seat=course.bench)     # seatOn's settle: the seat on the pan
        loco.call(phase(None))
        loco.call(auto(True))
        loco.follow_path([(0.0, ges['y0'])], gait='walk', stop=False)
        loco.gesture(g['name'], weight=g['weight'])
        loco.follow_path([(0.0, ges['y1'] - g['stop_before_end'])], gait='walk', stop=False)
        loco.stop_gesture()
        loco.call(auto(False))
        loco.move_to((0.0, lad['y0'] - ld['trigger']), gait='walk')
        loco.climb_ladder(height=ld['height'])
        loco.call(auto(True))
        loco.move_to((0.0, (top['y0'] + top['y1']) / 2), gait='walk')
        loco.call(phase('finale'))
        loco.wait(fin['delay'])
        # face the follow camera where it orbits by then (swung to the ladder angle): its offset from the body is
        # (R cos A, -R sin A); the controller's heading is atan2(dx, -dy), 0 facing -Y
        A = math.radians(cam.get('ladder_angle_deg', 46.0))
        loco.emote(fin['emote'], fade_in=fin['fade_in'], facing=math.degrees(math.atan2(math.cos(A), math.sin(A))))
        loco.wait(fin.get('hold', 1.0))

    # ------------------------------------------------------------------------------------------- frames ---
    def body(self, i=None):
        """terrain_base's t2 on frame i: the controller's capsule centre when it drove, else the hips lifted by half
        the upper body (where that centre sits)"""
        if i is not None and i in self.engine and self.engine[i]['body']['center'] is not None:
            return Vector(self.engine[i]['body']['center'])
        if self.h is None:
            return Vector((0.0, -5.0, 0.9))
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.hips].head + Vector((0.0, 0.0, self._centre_lift))

    def hips_world(self):
        if self.h is None or not self.hips:
            return None
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.hips].head

    def hand(self):
        if self.h is None or not self.left_hand:
            return None
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.left_hand].head

    def follow_close(self, i):
        """the example's camera pushes in while she maneuvers or while the sit stop runs"""
        fl = self.flags.get(i) or {}
        return fl.get('mode') == 'maneuver' or fl.get('phase') in SIT_PHASES

    def frame(self, ctx, t, i):
        """render_frame: the camera for this frame (keyed), then the telemetry record"""
        dt = 1.0 / (self.scene.render.fps / self.scene.render.fps_base)
        b = self.body(i)
        follow = None
        if self.camera_mode == 'follow':
            cam = (self.example or {}).get('camera', {})
            lad = None
            zones = (self.example or {}).get('zones', {})
            if 'ladder' in zones:
                lad = self.course.segment(zones['ladder'])
            want_r = cam.get('radius_close', 3.4) if self.follow_close(i) else cam.get('radius', 5.2)
            want_a = math.radians(cam.get('ladder_angle_deg', 46.0)) if (
                lad and b.y >= lad['y0'] - cam.get('ladder_lead', 2.2)) else 0.0
            if self._follow is None:
                self._follow = {'R': cam.get('radius', 5.2), 'A': 0.0}
            else:
                self._follow['R'] = damp(self._follow['R'], want_r, cam.get('radius_damp', 2.5), dt)
                self._follow['A'] = damp(self._follow['A'], want_a, cam.get('angle_damp', 1.8), dt)
            follow = self._follow
        hand = self.hand() if self.camera_mode == 'hands_closeup' else None
        pos, tgt = camera_pose(self.camera_mode, tuple(b), tuple(hand) if hand is not None else None, follow)
        cam = self.stage.camera
        look_at(cam, pos, tgt)
        if ctx is not None and hasattr(ctx, 'key_transform'):
            ctx.key_transform(cam)
        else:
            for path in ('location', 'rotation_euler'):
                cam.keyframe_insert(path, frame=i)
            _linear_keys(cam, frame=i)
        self._record(t, i, dt, b)
        sec = int(math.floor(t))
        if sec != self._log_sec:
            self._log_sec = sec
            seg = self.course.segment_at(b.y)
            cr = self.records.get(i)
            eng = self.engine.get(i)
            extra = ''
            if cr is not None:                     # the template's per-second line: speed, input, tread, climb, weights
                tr = cr.get('tread_run')
                up = ((eng or {}).get('actions') or {}).get('stairsUp') or {}
                down = ((eng or {}).get('actions') or {}).get('stairsDown') or {}
                extra = ' speed=%.2f fwdIn=%s treadRaw=%s spread=%.3f climb=%.0f deg upW=%.2f downW=%.2f upScale=%s' % (
                    cr.get('speed') or 0.0, '%.3f' % cr['smooth_speed'] if cr.get('smooth_speed') is not None else '?',
                    '%.3f' % tr if tr is not None else 'null', cr.get('spread') or 0.0, cr.get('climb_deg') or 0.0,
                    up.get('weight') or 0.0, down.get('weight') or 0.0,
                    '%.2f' % up['timeScale'] if up.get('timeScale') is not None else '?')
                fl = self.flags.get(i) or {}
                if self.direct:                    # the example's own per-second course line
                    extra += ' run=%s maneuver=%s sit=%s emoting=%s seated=%s grounded=%s' % (
                        bool(cr.get('running')), fl.get('maneuver') or '-', fl.get('phase') or '-',
                        cr.get('mode') == 'emote', cr.get('mode') == 'seated', bool(cr.get('grounded')))
            self.log('%s t=%ds body=(%.2f,%.2f,%.2f) segment=%s%s' % (self.course.tag, sec, b.x, b.y, b.z,
                                                                      seg['label'] if seg else '-', extra))

    def _record(self, t, i, dt, b):
        cfg = self.telemetry_cfg
        if not cfg.get('enabled'):
            return
        every = max(1, int(cfg.get('sample_every') or 1))
        if (i - self.frame_start) % every:
            return
        if cfg.get('max_frames') is not None and len(self.frames) >= cfg['max_frames']:
            return
        prev = self._prev
        vz = (b.z - prev['z']) / dt if 'z' in prev else None
        jerk = (vz - prev['vz']) / dt if (vz is not None and prev.get('vz') is not None) else None
        speed = (math.hypot(b.x - prev['x'], b.y - prev['y']) / dt) if 'x' in prev else None
        feet = {}
        if self.h is not None:
            from ..characters.ground import posed_foot_world
            for side in ('left', 'right'):
                P = posed_foot_world(self.h, self.feet, side)
                if not len(P):
                    continue
                k = int(np.argmin(P[:, 2]))
                low = P[k]
                g = float(self.course.height_at(low[0], low[1]))
                feet[side] = {'actual': [round(float(c), 5) for c in low], 'soleGapY': round(float(low[2] - g), 5)}
        grounded = any(abs(f['soleGapY']) < 0.02 for f in feet.values()) if feet else None
        seg = self.course.segment_at(b.y)
        rec = {
            'frame': i, 't': round(t, 5), 'terrain': seg,
            'body': {'center': [round(b.x, 5), round(b.y, 5), round(b.z, 5)], 'speedActual': speed,
                     'speedInput': self.speed, 'grounded': grounded, 'bodyVelY': _num(vz), 'bodyJerkY': _num(jerk)},
            'feet': feet}
        hw = self.hips_world()
        if hw is not None:
            rec['body']['hips'] = [round(hw.x, 5), round(hw.y, 5), round(hw.z, 5)]
        eng = self.engine.get(i)
        if eng is not None:                       # the controller's own state on this frame: the engine's fields
            rec['body'].update({k: v for k, v in eng['body'].items() if k != 'center'})
            rec['body']['hipsSpeed'] = _num(speed)
            rec['support'] = eng['support']
            rec['actions'] = eng['actions']
            rec['ik'] = eng['ik']
            rec['mode'] = eng['mode']
            fl = self.flags.get(i) or {}
            if fl.get('maneuver'):
                rec['maneuver'] = fl['maneuver']
            if fl.get('phase'):
                rec['phase'] = fl['phase']
        self.frames.append(rec)
        prev.update({'x': b.x, 'y': b.y, 'z': b.z})
        if vz is not None:
            prev['vz'] = vz

    # ------------------------------------------------------------------------------------------ cleanup ---
    def summary(self):
        """_locSummarizeTelemetry over the recorded frames (plus each side's MeshSoleGapY: the keyed soles over the
        course surface)"""
        out = {'frameCount': len(self.frames), 'metrics': {}, 'byTerrain': {}}

        def upd(bucket, name, v):
            if v is None or not math.isfinite(v):
                return
            c = bucket.setdefault(name, {'max': 0.0, 'sum': 0.0, 'count': 0})
            c['max'] = max(c['max'], abs(v))
            c['sum'] += abs(v)
            c['count'] += 1
            c['avg'] = c['sum'] / c['count']

        for f in self.frames:
            key = ((f['terrain'] or {}).get('label') or (f.get('support') or {}).get('stairShape')
                   or 'unclassified')
            bt = out['byTerrain'].setdefault(key, {'frameCount': 0, 'metrics': {}})
            bt['frameCount'] += 1
            for bucket in (out['metrics'], bt['metrics']):
                upd(bucket, 'bodyJerkY', f['body']['bodyJerkY'])
                upd(bucket, 'speedError', (f['body'].get('speedInput') or 0.0) - (f['body'].get('speedActual') or 0.0))
                for side in ('left', 'right'):
                    foot = (f.get('ik') or {}).get(side) or {}
                    for name, key2 in (('TargetError', 'targetError'), ('TargetErrorXZ', 'targetErrorXZ'),
                                       ('SoleGapY', 'soleGapY'), ('TargetSpeed', 'targetSpeed'),
                                       ('HitSpeed', 'hitSpeed')):
                        upd(bucket, side + name, foot.get(key2))
                    if side in f['feet']:
                        upd(bucket, side + 'MeshSoleGapY', f['feet'][side]['soleGapY'])
        return out

    def cleanup(self):
        cfg = self.telemetry_cfg
        if not cfg.get('enabled'):
            return None
        out = cfg.get('output_path') or os.path.join(bpy.path.abspath('//') or '.', 'locomotion_telemetry.json')
        summ = cfg.get('summary_path') or out.replace('.json', '_summary.json')
        s = self.summary()
        import datetime
        payload = {'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'),
                   'terrainSegments': self.course.segments, 'summary': s,
                   'frames': self.frames if cfg.get('include_frames', True) else None}
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w') as fh:
            json.dump(payload, fh, indent=1, default=float)
        with open(summ, 'w') as fh:
            json.dump(s, fh, indent=1, default=float)
        self.log('[locomotion-telemetry] wrote %d frames to %s' % (len(self.frames), out))
        return out


# --------------------------------------------------------------------------------------- the harness hooks ---

def setup(ctx, config=None, **kw):
    """the scene script's setup(ctx): the course, the stage, the character and its keyed walk"""
    cs = CourseScene(ctx.scene, config, log=getattr(ctx, 'log', print), **kw)
    cs.setup(frame_start=ctx.frame_start)
    _STATE['scene'] = cs
    return cs


def render_frame(ctx, t, i):
    cs = _STATE.get('scene')
    if cs is not None:
        cs.frame(ctx, t, i)


def cleanup(ctx):
    cs = _STATE.get('scene')
    if cs is not None:
        cs.cleanup()
