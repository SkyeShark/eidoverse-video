"""eidoblend.characters.controller.mixer: three.js's AnimationMixer, ported for the controller's build-time simulation.

The WebGPU controller owns a THREE.AnimationMixer: every clip is an action playing continuously (most at weight 0), its
weight damped toward a target each frame, its timeScale set for stride sync, its time sometimes set outright (the stair
phase lock), fades scheduled (emotes), and mixer.update(dt) advances them all and writes the blend into the normalized
bones. The port keeps those semantics, so the controller's arithmetic ports line for line:

    mixer = AnimationMixer(h)
    a = mixer.clip_action(controller_clip).set_loop(LOOP_REPEAT)
    a.play(); a.set_effective_weight(0.0)
    a.weight = damp(a.weight, 1.0, 8.0, dt); a.time_scale = 1.2; a.time = 0.4
    mixer.update(dt)                     # advance, then blend -> mixer.pose {humanoid: Quaternion}, mixer.hips (offset)

three's rules, kept: actions blend in the order they were first played; each contributes at its EFFECTIVE weight (weight
x its fade); a property's contributions accumulate as a running slerp (the newcomer mixed in at w / sum), and where the
weights sum under 1 the result is mixed toward the property's original value (the normalized rest: identity) by the
shortfall. A property no playing action binds is left as it was (the controller's own overrides persist). LoopOnce clamps
(clamp_when_finished pauses it on its last frame) or disables at its end; LoopRepeat wraps; LoopPingPong reflects; a
fade-out that reaches 0 disables the action. One three.js quirk is NOT kept: three skips writing a property whose blend
did not change since the last frame, so a frozen pose would keep last frame's IK edits; here every bound property is
written every frame.
"""

import math

from mathutils import Quaternion, Vector

LOOP_ONCE, LOOP_REPEAT, LOOP_PINGPONG = 'once', 'repeat', 'pingpong'


def damp(x, y, lam, dt):
    """THREE.MathUtils.damp: frame-rate independent exponential approach"""
    return x + (y - x) * (1.0 - math.exp(-lam * dt))


def lerp(x, y, t):
    return x + (y - x) * t


def euclidean_modulo(n, m):
    return ((n % m) + m) % m


class AnimationAction:
    def __init__(self, mixer, clip):
        self.mixer, self.clip = mixer, clip
        self.loop = LOOP_REPEAT if getattr(clip, 'loop', True) else LOOP_ONCE
        self.repetitions = math.inf
        self.time = 0.0
        self.time_scale = 1.0
        self.weight = 1.0
        self.enabled = True
        self.paused = False
        self.clamp_when_finished = False
        self._effective_weight = 0.0
        self._fade = None
        self._loop_count = -1
        self.clip_time = 0.0

    # ---------------------------------------------------------------------------------------------- three's API
    def play(self):
        self.mixer._activate(self)
        return self

    def stop(self):
        self.mixer._deactivate(self)
        return self.reset()

    def reset(self):
        self.paused = False
        self.enabled = True
        self.time = 0.0
        self._loop_count = -1
        self.stop_fading()
        return self

    def is_running(self):
        return self.enabled and not self.paused and self.time_scale != 0 and self in self.mixer.active

    def set_loop(self, mode, repetitions=math.inf):
        self.loop, self.repetitions = mode, repetitions
        return self

    def set_effective_weight(self, w):
        self.weight = w
        self._effective_weight = w if self.enabled else 0.0
        return self.stop_fading()

    def get_effective_weight(self):
        return self._effective_weight

    def fade_in(self, duration):
        return self._schedule_fading(duration, 0.0, 1.0)

    def fade_out(self, duration):
        return self._schedule_fading(duration, 1.0, 0.0)

    def stop_fading(self):
        self._fade = None
        return self

    def get_clip(self):
        return self.clip

    def _schedule_fading(self, duration, v0, v1):
        now = self.mixer.time
        self._fade = (now, now + max(duration, 1e-9), v0, v1)
        return self

    # ---------------------------------------------------------------------------------------------- one step
    def _update_weight(self, time):
        w = 0.0
        if self.enabled:
            w = self.weight
            if self._fade is not None:
                t0, t1, v0, v1 = self._fade
                u = min(max((time - t0) / (t1 - t0), 0.0), 1.0)
                val = v0 + (v1 - v0) * u
                w *= val
                if time > t1:
                    self.stop_fading()
                    if val == 0.0:
                        self.enabled = False
        self._effective_weight = w
        return w

    def _update_time(self, delta):
        dur = self.clip.duration
        t = self.time + delta
        if delta == 0:
            if self._loop_count == -1:
                return t
            return dur - t if (self.loop == LOOP_PINGPONG and (self._loop_count & 1) == 1) else t
        if self.loop == LOOP_ONCE:
            if self._loop_count == -1:
                self._loop_count = 0
            if 0.0 <= t < dur:
                self.time = t
            else:
                t = min(max(t, 0.0), dur)
                if self.clamp_when_finished:
                    self.paused = True
                else:
                    self.enabled = False
                self.time = t
            return t
        if self._loop_count == -1:
            self._loop_count = 0
        if dur > 0 and (t >= dur or t < 0):
            loops = math.floor(t / dur)
            t -= dur * loops
            self._loop_count += abs(loops)
            if self.repetitions - self._loop_count <= 0:
                if self.clamp_when_finished:
                    self.paused = True
                else:
                    self.enabled = False
                t = dur if delta > 0 else 0.0
            self.time = t
        else:
            self.time = t
        if self.loop == LOOP_PINGPONG and (self._loop_count & 1) == 1:
            return dur - t
        return t

    def _update(self, time, delta):
        if not self.enabled:
            self._update_weight(time)
            return 0.0
        ts = 0.0 if self.paused else self.time_scale
        self.clip_time = self._update_time(delta * ts)
        return self._update_weight(time)


class AnimationMixer:
    """the blend of every playing action into the humanoid's normalized pose"""

    def __init__(self, h=None, names=None):
        self.time = 0.0
        self.time_scale = 1.0
        self.actions = {}                 # clip -> action (clipAction caches one per clip)
        self.active = []                  # in activation order
        self.pose = {}                    # {humanoid name: Quaternion}: the last blend (the scene graph's values)
        self.hips = Vector()              # the hips' offset (the position track's blend)
        self.names = list(names) if names is not None else (list(h.humanoid) if h is not None else [])
        self.weights = {}                 # {slot: effective weight} after the last update
        self.clip_times = {}              # {slot: clip time} after the last update

    def clip_action(self, clip):
        a = self.actions.get(id(clip))
        if a is None:
            a = AnimationAction(self, clip)
            self.actions[id(clip)] = a
        return a

    def _activate(self, a):
        if a not in self.active:
            self.active.append(a)

    def _deactivate(self, a):
        if a in self.active:
            self.active.remove(a)

    def stop_all_action(self):
        for a in list(self.active):
            a.stop()

    def update(self, dt):
        dt *= self.time_scale
        self.time += dt
        acc, cum = {}, {}
        hips_acc, hips_cum, hips_bound = None, 0.0, False
        bound = set()
        self.weights, self.clip_times = {}, {}
        for a in list(self.active):
            w = a._update(self.time, dt)
            c = a.clip
            bound.update(c.bones)
            if not c.strip_hips_position:
                hips_bound = True
            self.weights[c.slot] = w
            self.clip_times[c.slot] = a.clip_time
            if w <= 0.0:
                continue
            N, hp = c.sample(a.clip_time, loop=a.loop != LOOP_ONCE)
            for nm, q in N.items():
                cw = cum.get(nm, 0.0)
                if cw == 0.0:
                    acc[nm], cum[nm] = q.copy(), w
                else:
                    cw += w
                    acc[nm] = acc[nm].slerp(q, w / cw)
                    cum[nm] = cw
            if hp is not None:
                if hips_cum == 0.0:
                    hips_acc, hips_cum = hp.copy(), w
                else:
                    hips_cum += w
                    hips_acc = hips_acc.lerp(hp, w / hips_cum)
        for nm in bound:
            cw = cum.get(nm, 0.0)
            if cw == 0.0:
                self.pose[nm] = Quaternion()
            elif cw < 1.0:
                self.pose[nm] = acc[nm].slerp(Quaternion(), 1.0 - cw)
            else:
                self.pose[nm] = acc[nm]
        if hips_bound:
            if hips_cum == 0.0:
                self.hips = Vector()
            elif hips_cum < 1.0:
                self.hips = hips_acc.lerp(Vector(), 1.0 - hips_cum)
            else:
                self.hips = hips_acc
        return self
