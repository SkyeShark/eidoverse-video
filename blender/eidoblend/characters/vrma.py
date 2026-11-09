"""eidoblend.characters.vrma: the VRMA clip library (characters.md, "Animation clips").

    from eidoblend.characters import load_vrm, play_vrma_default
    me = load_vrm('claude_robot')
    play_vrma_default(me, 'still_breathe', t=0.0)                       # an NLA strip from second 0, looping
    play_vrma_default(me, 'turn_it_down', t=4.0, loop=False, fade=0.3)  # a one-shot over it, crossfaded, holding its end

A clip goes in once per (character, clip) through the add-on's import_scene.vrma, which retargets it onto that rig (so it is
cached per rig, as three's mixer binds per VRM): the pose is zeroed and the action cleared first (the importer composes onto
the bone's current rotation), the add-on's 'Humanoid' action is renamed '<character>|<slot>' with a fake user and unassigned,
its empty 'Expressions' action and any LookAt empty it made are deleted. The importer keys every frame at the scene's fps
from frame 1, so set the scene fps BEFORE loading clips.

play_vrma(h, clip, t, ...) places a strip: loop=True repeats to `until` (or 600 s), loop=False plays once and holds its last
frame (HOLD_FORWARD); fade crossfades from what plays below (blend_in); time_scale is the strip's scale; phase starts the clip
part-way in. Locomotion slots are refused (walk / run / stairs ...): played in place they walk on a treadmill. Route them
through locomotion.walk_path, which moves the body and plants the feet; force=True overrides for a body that IS on a treadmill.

Clip.sample(tc) reads a clip's pose at clip time tc (s) straight from its fcurves (no depsgraph): {bone: basis Quaternion}
and the hips' basis location; locomotion samples the walk this way.
"""

import os

import bpy
from mathutils import Quaternion, Vector

from .vrm import REPO, glb_json

ANIM_DIR = os.path.join(REPO, 'eidoverse', 'assets', 'animations')
LOCOMOTION_SLOTS = {'walk', 'run', 'fastRun', 'slowRun', 'sneak', 'walkBackward', 'stairsUp', 'stairsDown', 'stairsRunUp',
                    'stairsRunDown'}
_CACHE = {}


def vrma_path(slot):
    if os.path.exists(slot):
        return os.path.abspath(slot)
    p = os.path.join(ANIM_DIR, slot if slot.endswith('.vrma') else slot + '.vrma')
    if not os.path.exists(p):
        raise FileNotFoundError(f'no VRMA clip {slot!r} in {ANIM_DIR}')
    return p


def vrma_duration(path):
    """the clip's length in seconds: its samplers' last input time (three's AnimationClip.duration)"""
    J = glb_json(path)
    mx = 0.0
    for a in J.get('animations', []):
        for s in a['samplers']:
            mx = max(mx, J['accessors'][s['input']]['max'][0])
    return mx


def _channelbag(action):
    from bpy_extras import anim_utils
    slot = action.slots[0] if len(action.slots) else None
    return anim_utils.action_get_channelbag_for_slot(action, slot) if slot else None, slot


class Clip:
    def __init__(self, h, slot, action, path, fps):
        self.h, self.slot, self.action, self.path, self.fps = h, slot, action, path, fps
        self.duration = vrma_duration(path)
        self.first = action.frame_range[0]
        cb, self.action_slot = _channelbag(action)
        self.rot, self.loc = {}, {}
        for fc in (cb.fcurves if cb else []):
            dp = fc.data_path
            if not dp.startswith('pose.bones["'):
                continue
            bone = dp[len('pose.bones["'):dp.index('"]')]
            if dp.endswith('rotation_quaternion'):
                self.rot.setdefault(bone, [None] * 4)[fc.array_index] = fc
            elif dp.endswith('.location'):
                self.loc.setdefault(bone, [None] * 3)[fc.array_index] = fc

    def frame_at(self, tc, loop=True):
        if loop and self.duration > 0:
            tc = tc % self.duration
        else:
            tc = min(max(tc, 0.0), self.duration)
        return self.first + tc * self.fps

    def sample(self, tc, loop=True):
        """-> ({bone: basis Quaternion}, {bone: basis location Vector}) at clip time tc (s)"""
        f = self.frame_at(tc, loop)
        rot = {}
        for b, fcs in self.rot.items():
            q = Quaternion([fc.evaluate(f) if fc else (1.0 if i == 0 else 0.0) for i, fc in enumerate(fcs)])
            rot[b] = q.normalized()
        loc = {b: Vector([fc.evaluate(f) if fc else 0.0 for fc in fcs]) for b, fcs in self.loc.items()}
        return rot, loc


def load_clip(h, slot, scene=None):
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    key = (h.arm.name, slot, fps)
    try:
        hit = key in _CACHE and _CACHE[key].action.name in bpy.data.actions
    except ReferenceError:      # the action was removed (a file reloaded)
        _CACHE.pop(key, None); hit = False
    if hit:
        return _CACHE[key]
    path = vrma_path(slot)
    arm = h.arm
    ad = arm.animation_data or arm.animation_data_create()
    keep_action, keep_slot = ad.action, getattr(ad, 'action_slot', None)
    ad.action = None
    h.zero_pose()
    bpy.context.view_layer.update()
    acts0, objs0 = set(bpy.data.actions), set(bpy.data.objects)
    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = arm
    res = bpy.ops.import_scene.vrma(filepath=path, armature_object_name=arm.name)
    if 'FINISHED' not in res:
        raise RuntimeError(f'load_clip: the add-on refused {path}: {res}')
    new = [a for a in bpy.data.actions if a not in acts0]
    hum = next((a for a in new if a.name.startswith('Humanoid')), None)
    if hum is None:
        raise RuntimeError(f'load_clip: {path} made no Humanoid action ({[a.name for a in new]})')
    name = f'{h.name}|{os.path.splitext(os.path.basename(path))[0]}'
    old = bpy.data.actions.get(name)
    if old is not None and old is not hum:
        bpy.data.actions.remove(old)
    hum.name = name
    hum.use_fake_user = True
    for a in new:
        if a is not hum and a.name.startswith('Expressions'):
            if a.users:
                for idb in (arm.data,):
                    if idb.animation_data and idb.animation_data.action is a:
                        idb.animation_data.action = None
            bpy.data.actions.remove(a)
    for o in [o for o in bpy.data.objects if o not in objs0]:
        bpy.data.objects.remove(o, do_unlink=True)
    ad.action = keep_action
    if keep_action is not None and keep_slot is not None and hasattr(ad, 'action_slot'):
        ad.action_slot = keep_slot
    h.zero_pose()
    bpy.context.view_layer.objects.active = prev
    clip = Clip(h, slot, hum, path, fps)
    _CACHE[key] = clip
    return clip


def play_vrma(h, clip, t=0.0, loop=True, until=None, fade=0.0, time_scale=1.0, phase=0.0, scene=None, frame_start=1):
    """place `clip` as an NLA strip from second t (scene time, frame = frame_start + t * fps) -> the strip"""
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    arm = h.arm
    ad = arm.animation_data or arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = f'{clip.slot}@{t:g}'
    f0 = frame_start + t * fps
    strip = track.strips.new(track.name, int(round(f0)), clip.action)
    if hasattr(strip, 'action_slot') and clip.action_slot is not None:
        strip.action_slot = clip.action_slot
    a0 = clip.first + (phase % clip.duration if loop and clip.duration else phase) * fps
    strip.action_frame_start = a0
    strip.action_frame_end = a0 + clip.duration * fps if clip.duration > 0 else a0 + 1
    strip.scale = 1.0 / time_scale if time_scale else 1.0
    if loop:
        end_t = until if until is not None else 600.0
        span = max(1e-3, (end_t - t) * fps)
        strip.repeat = max(1.0, span / ((strip.action_frame_end - strip.action_frame_start) * strip.scale))
        strip.extrapolation = 'HOLD_FORWARD'
    else:
        strip.repeat = 1.0
        strip.extrapolation = 'HOLD_FORWARD'
    strip.blend_type = 'REPLACE'
    strip.use_auto_blend = False
    if fade > 0:
        strip.blend_in = fade * fps
    return strip


def play_vrma_default(h, slot, t=0.0, force=False, **kw):
    if slot in LOCOMOTION_SLOTS and not force:
        raise ValueError(f'play_vrma_default: "{slot}" is a LOCOMOTION clip: played in place it walks on a treadmill. '
                         'Route it through locomotion.walk_path (it moves the body and plants the feet), or pass force=True '
                         'for a body that really is on a treadmill or carried.')
    return play_vrma(h, load_clip(h, slot), t=t, **kw)
