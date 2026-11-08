"""eidoblend.course.template: the locomotion scene template (eidoverse/terrain_base.js's setup / renderFrame /
cleanup) for the Blender harness.

A scene script (eido_blender.py runs it) sets a TERRAIN_CONFIG and hands its hooks to the template, as the engine's
scenes set globalThis.TERRAIN_CONFIG and eval'd terrain_base.js:

    from eidoblend.course import template, PRESETS
    TERRAIN_CONFIG = PRESETS['stairs_small']
    CAMERA_MODE = 'three_quarter'                       # 'side' (the default) | 'three_quarter' | 'hands_closeup'
    def setup(ctx):
        template.setup(ctx, TERRAIN_CONFIG, character='claude_robot', camera_mode=CAMERA_MODE)
    render_frame = template.render_frame
    cleanup = template.cleanup

setup builds the course and the stage (builder.py, stage.py), loads the VRM at the controller's start (Blender
(0, -5, 0), facing +Y) and walks it along the course: the engine's renderFrame called charCtrl.locomote(dt, {z: -1})
every frame (the controller and its foot IK in a Rapier world). Here the same controller (the Blender port,
eidoblend.characters.controller: VRMCharacterController with the terrain_base foot IK, in a CollisionWorld over the
course's meshes) walks it once, frame by frame, and the bake keys it (driver='controller', the default: its gait tree
takes the steps, ramps and bumps itself). driver='walk_path' walks round one's walk_path instead (planted feet over
the course's own height function, pelvis='lower' when the course has steps: faster to build, no step adaptation), and
driver(course, handle, scene) -> a report replaces the walk with anything else. The walk stops 0.6 m before the first
wall, gap or ladder: those are maneuvers, the course example's direction. render_frame keys the camera for the frame
(the template's modes) and records the telemetry; cleanup writes it.

variant='stairs_handcloseup' (presets.SCENES) runs one of the engine's variant scenes: its config, camera mode,
character, recolour, telemetry and baked expression; the post effects it also set belong to other ports (named in the
entry, logged here).

Camera modes (the template's, in Blender's axes; b = the body centre, the hips):
    side            at (5, b.y, b.z + 0.2), looking at (b.x, b.y, b.z - 0.5)
    three_quarter   35 degrees from the side toward her front: (b.x + 5 cos 35, b.y + 5 sin 35, b.z + 1), looking at
                    (b.x, b.y, b.z - 0.5)
    hands_closeup   0.8 m to the left hand's side, 5 cm above it, looking at it (falls back to side without hands)
    follow          the course example's: radius 5.2 m (3.4 while maneuvering), swinging to 46 degrees from 2.2 m
                    before the ladder, both damped (THREE.MathUtils.damp), at b.z + 0.45 + 0.07 R, looking 0.3 m below b

Telemetry (LOCOMOTION_TELEMETRY's port): telemetry={'enabled': True, 'sample_every': 1, 'max_frames': None,
'output_path': ..., 'summary_path': ..., 'include_frames': True}. Per frame: the course segment under the body, the
body centre, the feet (each foot's lowest sole point), the actual and input speed, grounded, each sole's gap over
the course surface, the body's vertical velocity and jerk; with the controller driving, its own state too (speed
input and scale, grounded, support mode, signed climb angle, climb blocked, tread run, and the six actions' weights
idle / walk / run / stairsUp / stairsDown / fallIdle); the summary is _locSummarizeTelemetry's (max / avg of
bodyJerkY, speedError and each side's soleGapY, overall and per terrain segment). The engine's per-limb IK internals
(stair-ascent nudges, IK targets, toe angles) stay inside the controller port's foot IK.
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
_DEFAULT = object()
_STATE = {}
# the options terrain_base.js gave its VRMCharacterController (snake_case: the port's names); the two stair-clip
# confirmations are attachLocomotion's in the port
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
TERRAIN_BASE_LOCOMOTION = {'require_confirmed_stair_clips': True, 'confirmed_stair_hold_frames': 12}


def _linear_keys(idb):
    """Python keyframe_insert ignores the default-interpolation preference: make the object's keys LINEAR
    (Blender 5's layered actions: through the slot's channelbag)"""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        cb = None
    for fc in (cb.fcurves if cb is not None else []):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def _snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


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


class CourseScene:
    """The template's state: the course, the stage, the character and its walk, the camera and the telemetry."""

    def __init__(self, scene, config=None, character=_DEFAULT, camera_mode=None, clip='walk', speed=None,
                 walk_to=None, duration=None, telemetry=None, driver='controller', pelvis=None, example=None,
                 materials=None, variant=None, log=print):
        self.scene = scene
        self.example = EXAMPLES.get(example) if isinstance(example, str) else example
        if isinstance(variant, str):
            if variant not in SCENES:
                raise ValueError('variant %r: one of %s' % (variant, ', '.join(sorted(SCENES))))
            variant = SCENES[variant]
        self.variant = variant or {}
        v = self.variant
        self.config = config if config is not None else (
            v.get('config') or (self.example['config'] if self.example else None))
        self.camera_mode = camera_mode or v.get('camera_mode') or (
            self.example.get('camera_mode') if self.example else None) or 'side'
        if self.camera_mode not in CAMERA_MODES:
            raise ValueError('camera_mode %r: one of %s' % (self.camera_mode, ', '.join(CAMERA_MODES)))
        if not callable(driver) and driver not in DRIVERS:
            raise ValueError('driver %r: one of %s, or a callable' % (driver, ', '.join(DRIVERS)))
        self.character = v.get('character', 'claude_robot') if character is _DEFAULT else character
        self.clip_name, self.speed = clip, speed
        self.walk_to, self.duration = walk_to, duration if duration is not None else v.get('duration')
        self.driver, self.pelvis = driver, pelvis
        self.materials = materials if materials is not None else v.get('materials')
        tel = telemetry if telemetry is not None else (v.get('telemetry') or {})
        self.telemetry_cfg = {_snake(k): x for k, x in tel.items()}      # LOCOMOTION_TELEMETRY's camelCase too
        self.log = log
        if v.get('post'):
            self.log('[course] variant post effect %r: the sky / fx ports render it, not the template'
                     % v['post'])
        self.frames = []
        self._prev = {}
        self._follow = None
        self._log_sec = -1
        self.h = None
        self.report = None
        self.records = {}

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
        if zs:                                     # the template's log line
            self.log('%s VRM height=%.3f footY=%.3f' % (self.course.tag, max(zs) - min(zs), min(zs)))
        self.feet = foot_points(self.h)
        hb = self.h.humanoid
        self.hips = hb.get('hips')
        self.left_hand = hb.get('leftHand')
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

    def _walk_controller(self):
        """terrain_base's renderFrame: the controller (the Blender port) walking forward, +Y, over the course's own
        meshes, simulated frame by frame and keyed. The noik variant (foot_ik False) bakes the raw animation."""
        from ..characters.controller import CollisionWorld, Locomotion
        meshes = [o for o in self.course.objects if o.type == 'MESH']
        if self.course.bench is not None:
            meshes.append(self.course.bench)
        world = CollisionWorld(meshes)
        foot_ik = self.variant.get('foot_ik', True)
        self.loco = Locomotion(self.h, world, start=self.course.start, heading=math.pi,
                               leg_ik='default' if foot_ik else None, controller_opts=dict(TERRAIN_BASE_CONTROLLER),
                               locomotion_opts=dict(TERRAIN_BASE_LOCOMOTION), log=self.log)
        y0 = self.course.start[1]
        y1 = self.walk_to if self.walk_to is not None else self._stop_y()
        if self.duration is not None:
            v = self.speed or self.loco.native['walk']
            y1 = min(y1, y0 + v * self.duration)
        self.walk_span = (y0, y1)
        self.loco.move_to((0.0, y1), speed=self.speed)
        rep = self.loco.bake(f0=self.frame_start, feet='plant' if foot_ik else 'foot_ik')
        self.records = {r['f']: r for r in rep.get('_records', [])}
        return rep

    # ------------------------------------------------------------------------------------------- frames ---
    def body(self):
        if self.h is None:
            return Vector((0.0, -5.0, 0.9))
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.hips].head

    def hand(self):
        if self.h is None or not self.left_hand:
            return None
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.left_hand].head

    def frame(self, ctx, t, i):
        """render_frame: the camera for this frame (keyed), then the telemetry record"""
        dt = 1.0 / (self.scene.render.fps / self.scene.render.fps_base)
        b = self.body()
        follow = None
        if self.camera_mode == 'follow':
            cam = (self.example or {}).get('camera', {})
            lad = None
            zones = (self.example or {}).get('zones', {})
            if 'ladder' in zones:
                lad = self.course.segment(zones['ladder'])
            want_r = cam.get('radius', 5.2)
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
            _linear_keys(cam)
        self._record(t, i, dt, b)
        sec = int(math.floor(t))
        if sec != self._log_sec:
            self._log_sec = sec
            seg = self.course.segment_at(b.y)
            cr = self.records.get(i)
            extra = ''
            if cr is not None:                     # the template's per-second line: speed, input, tread, climb, weights
                w = cr.get('weights') or {}
                tr = cr.get('tread_run')
                extra = ' speed=%.2f fwdIn=%s treadRaw=%s climb=%.0f deg upW=%.2f downW=%.2f' % (
                    cr.get('speed') or 0.0, '%.3f' % cr['smooth_speed'] if cr.get('smooth_speed') is not None else '?',
                    '%.3f' % tr if tr is not None else 'null', cr.get('climb_deg') or 0.0, w.get('stairsUp', 0.0),
                    w.get('stairsDown', 0.0))
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
                     'speedInput': self.speed, 'grounded': grounded, 'bodyVelY': vz, 'bodyJerkY': jerk},
            'feet': feet}
        cr = self.records.get(i)
        if cr is not None:                        # the controller's own state on this frame (the engine's fields)
            def num(v):
                return None if v is None else round(float(v), 5)
            rec['body'].update({'speedInput': num(cr.get('smooth_speed')), 'speedScale': num(cr.get('speed_scale')),
                                'speedActual': num(cr.get('speed')), 'hipsSpeed': speed,
                                'grounded': bool(cr.get('grounded')), 'supportMode': cr.get('support_mode')})
            rec['support'] = {'signedClimbAngleDeg': num(cr.get('climb_deg')),
                              'climbBlocked': bool(cr.get('climb_blocked')), 'aheadTreadRun': num(cr.get('tread_run'))}
            w = cr.get('weights') or {}
            rec['actions'] = {k: ({'weight': w[slot]} if slot in w else None) for k, slot in ACTIONS.items()}
            rec['mode'] = cr.get('mode')
        self.frames.append(rec)
        prev.update({'x': b.x, 'y': b.y, 'z': b.z})
        if vz is not None:
            prev['vz'] = vz

    # ------------------------------------------------------------------------------------------ cleanup ---
    def summary(self):
        """_locSummarizeTelemetry over the recorded frames"""
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
            key = (f['terrain'] or {}).get('label') or 'unclassified'
            bt = out['byTerrain'].setdefault(key, {'frameCount': 0, 'metrics': {}})
            bt['frameCount'] += 1
            for bucket in (out['metrics'], bt['metrics']):
                upd(bucket, 'bodyJerkY', f['body']['bodyJerkY'])
                si, sa = f['body']['speedInput'], f['body']['speedActual']
                if sa is not None:
                    upd(bucket, 'speedError', (si or 0.0) - sa)
                for side in ('left', 'right'):
                    if side in f['feet']:
                        upd(bucket, side + 'SoleGapY', f['feet'][side]['soleGapY'])
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
