"""eidoblend.harness.context: `ctx`, what a scene script's hooks receive.

    def setup(ctx): ...                 build the scene (required)
    def render_frame(ctx, t, i): ...    optional; runs ONCE PER FRAME AT BUILD TIME, the scene already at that frame,
                                        and keys what it changes (ctx.key / ctx.key_transform), so the saved .blend
                                        plays and scrubs on its own and any frame renders the same, jumped to or not.
                                        A change it does not key keeps its LAST value for the whole film: the build
                                        finds those (eidoblend.harness.keying) and names them in the digest.
    def cleanup(ctx): ...               optional; after the build is saved

ctx holds
    scene                 the bpy scene being built (bpy.context.scene)
    width height fps duration total_frames frame_start frame_end
    assets                {key: absolute path} from the config's "assets"; reads are recorded (a declared asset never
                          read is a finding)
    repo eidoverse_dir scene_dir out_dir   paths
    mode                  'film' | 'probe' | 'capture' | 'bench' | 'build' (setup should not depend on it)
    frame_at(t)  time_at(frame)
    key(target, data_path, index=-1, frame=None, interpolation='LINEAR')
                                                     insert a key at the current frame (given its interpolation
                                                     once render_frame has run over the film; 'CONSTANT' for a step)
    key_transform(ob, frame=None)                    location + rotation (its rotation mode's channels) + scale
    cut(t_or_frame, camera)                          a timeline marker that switches to this camera (a shot cut)
    flag(ob, name, value=True)                       an audit flag on an object ('no_motion_check', 'allow_intersect' ...)
    record(check, outcome, message, ...)             your own finding in the audit ledger (PASS | WARN | SKIPPED)
    log(*msg)
The script's module namespace also has WIDTH, HEIGHT, FPS, DURATION, TOTAL_FRAMES, FRAME_START, FRAME_END, ASSETS,
EIDOVERSE_DIR and REPO, as the WebGPU edition's globals; scene-wide audit flags are module-level names there
(e.g. `_no_motion_check = True`).
"""

from __future__ import annotations

import os

from .. import common
from . import config as cfgmod, keying, ledger as L


class AssetMap(dict):
    """A dict of declared assets that remembers which keys the script read."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.reads = set()

    def __getitem__(self, k):
        self.reads.add(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        if k in self:
            self.reads.add(k)
        return super().get(k, default)


class Ctx:
    def __init__(self, scene, cfg, assets: AssetMap, led: L.Ledger, mode: str):
        self.scene = scene
        self.cfg = cfg
        self.width, self.height = cfg['width'], cfg['height']
        self.fps, self.duration = cfg['fps'], cfg['duration']
        self.frame_start = cfg['frame_start']
        self.total_frames = cfgmod.total_frames(cfg)
        self.frame_end = self.frame_start + self.total_frames - 1
        self.assets = assets
        self.repo = common.REPO
        self.eidoverse_dir = common.EIDOVERSE_DIR
        self.scene_dir = os.path.dirname(cfg['_scene_json'])
        self.out_dir = os.path.dirname(cfg['_output'])
        self.mode = mode
        self._led = led
        self.keyed = 0
        self.key_log = keying.KeyLog()

    # time
    def frame_at(self, t: float) -> int:
        return common.frame_at(t, self.fps, self.frame_start)

    def time_at(self, frame: int) -> float:
        return common.time_at(frame, self.fps, self.frame_start)

    # keys
    def key(self, target, data_path: str, index: int = -1, frame=None, interpolation: str = 'LINEAR'):
        """Key target.data_path at `frame` (default: the current frame). Once render_frame has run over the film,
        the runner gives every key made here its interpolation (keying.make_linear): LINEAR by default, so
        sub-frame motion blur interpolates straight between the frames render_frame set; 'CONSTANT' holds the value
        to the next key (a step: a light switched at a cut); 'BEZIER' eases. (Python's keyframe_insert always makes
        BEZIER keys in Blender 5.2, whatever the preference says, hence the pass afterwards.)"""
        f = self.scene.frame_current if frame is None else frame
        ok = target.keyframe_insert(data_path, index=index, frame=f)
        if ok:
            self.keyed += 1
            self.key_log.add(target, data_path, index, f, interpolation)
        return ok

    def key_transform(self, ob, frame=None, interpolation='LINEAR'):
        self.key(ob, 'location', frame=frame, interpolation=interpolation)
        mode = ob.rotation_mode
        self.key(ob, 'rotation_quaternion' if mode == 'QUATERNION' else
                 'rotation_axis_angle' if mode == 'AXIS_ANGLE' else 'rotation_euler', frame=frame,
                 interpolation=interpolation)
        self.key(ob, 'scale', frame=frame, interpolation=interpolation)

    def cut(self, when, camera, name=None):
        """A shot cut: a timeline marker bound to `camera` at frame `when` (an int) or at `when` seconds (a float)."""
        f = when if isinstance(when, int) else self.frame_at(float(when))
        m = self.scene.timeline_markers.new(name or f'cut_{camera.name}_{f}', frame=f)
        m.camera = camera
        if self.scene.camera is None or f <= self.frame_start:
            self.scene.camera = camera
        return m

    # audits
    def flag(self, ob, name: str, value=True):
        c = L.canonical_flag(name, L.OBJECT_FLAG_ALIASES)
        if c not in L.OBJECT_FLAGS and c != 'assembly':
            raise ValueError(f"unknown audit flag {name!r}; flags: {', '.join(L.OBJECT_FLAGS)}, assembly")
        ob[c] = value
        return ob

    def record(self, check: str, outcome: str, message: str, **kw):
        return self._led.record(check=f'scene.{check}', outcome=outcome, message=message, **kw)

    def log(self, *msg):
        common.log('scene', *msg)
