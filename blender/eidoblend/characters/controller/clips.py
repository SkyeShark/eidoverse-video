"""eidoblend.characters.controller.clips: the controller's clip library and what it measures in each clip on this body.

The WebGPU controller loads its clips once (loadStandardAnimations: walk, run, idle, the four stair clips, fallIdle and
the maneuver one-shots) from the VRMA library and strips what would fight its own authority: every clip's hips POSITION
track (the root is the controller's; the curve is kept first as the clip's root motion, extractRootMotion), every clip's
head and neck ROTATION (the controller pitches the head from the climb), and for the maneuver clips the hips' YAW (their
trajectory owns the heading: stripHipsYaw, a swing-twist split). Here the same clips come in through round one's
load_clip (the VRM add-on's own retarget onto this rig), are stripped the same way, and are cached as NORMALIZED rotations
(three-vrm's frame in Blender's axes: rest = identity) at 120 samples a second:

    lib = load_standard_animations(h, body)          # {slot: ControllerClip or None}; turnLeft / turnRight too
    c = lib['walk']
    N, hips = c.sample(t)                             # {humanoid name: Quaternion}, the hips offset (None: stripped)
    c.gait                                            # GaitAnalysis: the clip measured on THIS body (below)
    c.root_motion                                     # the stripped hips curve, 48 + 1 samples (extractRootMotion)

Emotes keep every track (loadEmote); gestures keep only the upper body's rotations (loadGesture's mask):
load_emote_clip(h, slot), load_gesture_clip(h, slot).

GaitAnalysis (analyze): every clip is measured once on the body it plays on. The clip is played in its own space WITH
its root motion (and, for a turn, with its hips' yaw); each ankle and each sole point is followed 120 times a second.
  THE TREADMILL  the velocity the ground has under a planted foot in that space: backward at the walk's pace for an
                 in-place clip (walk, run), zero for a clip that carries its root (stairsDown), backward but not down for
                 stairsUp (in place across, root motion up). It is the median velocity of the 40 % of ankle samples that
                 move most backward (a stance is the slowest, most backward part of any foot's cycle)
  THE STANCE     a foot is planted where its ankle moves with the treadmill within 28 % of the gait's swing speed (the
                 90th percentile of every ankle's speed over the treadmill), grown through the heel strike and the toe
                 roll while some low point of its sole (within 1 cm of its lowest) still moves with it, runs shorter than
                 50 ms dropped. A walk-like gait (walk, stairsUp, stairsDown) has no flight: where neither foot is down,
                 the foot that was down last stays down. A turn (the library's shuffle the feet 1-4 cm off the floor,
                 the planted ankle circling its ball at 0.2-0.3 m/s) steps a foot where it rides 6 mm or more over the
                 other while it moves, or where its ankle sweeps faster than 0.55 m/s; elsewhere the foot is planted
                 and pivots, and where neither would be, the lower one stays down. A stationary clip (idle, an emote)
                 plants both feet throughout
  THE SUPPORT    the root's velocity over the ground (forward, to its left, up) = its own root motion less the planted
                 contact's velocity, shared by the feet's load; through a run's flight the planted pace carries on
    stance / p / u          per foot and sample: planted?, how far through its stance, how far through its swing
    stride, v_native        forward travel a cycle (m) and its mean pace (m/s) ON THIS BODY: the distance matching's cycle
    travel                  forward travel since the cycle's start, n + 1 samples (distance matching inverts it)
    lat                     the sideways sway of the root over its support through the cycle (mean 0)
    phase0                  where the left foot strikes (0..1 of the cycle): the gait clips' sync marker
    rise_per_cycle          the root motion's climb a cycle (the stair clips: two treads)
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..ground import SIDES
from ..vrma import load_clip, vrma_path
from .pose import leg_clamps

RATE = 120.0                        # cache / analysis samples a second
# loadStandardAnimations' SLOTS and ONE_SHOT, and its STRIP_HIPS_ROT (the maneuver clips' baked root yaw)
STANDARD_SLOTS = ['walk', 'run', 'idle', 'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown', 'fallIdle',
                  'jump', 'vault', 'climbLedge', 'climbWallUp', 'fallLand', 'climbLadder']
ONE_SHOT = {'jump', 'vault', 'climbLedge', 'climbWallUp', 'fallLand'}
STRIP_HIPS_ROT = {'vault', 'jump', 'climbLadder', 'climbLedge', 'climbWallUp'}
# the library's turns (render_scene.mjs VRMA_SLOTS lists them as controller-internal; the WebGPU controller never plays
# them): this edition's turn on the spot plays them with their hips' yaw moved to the root
TURN_SLOTS = ['turnLeft', 'turnRight']
GAIT_SLOTS = {'walk', 'run', 'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown'}
WALK_LIKE = {'walk', 'stairsUp', 'stairsDown'}
UPPER_BODY = ['spine', 'chest', 'upperChest', 'neck', 'head', 'leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand',
              'rightShoulder', 'rightUpperArm', 'rightLowerArm', 'rightHand']
FINGER_WORDS = ('Thumb', 'Index', 'Middle', 'Ring', 'Little')
TOL = 0.28                          # a planted ankle moves with the treadmill within this fraction of the swing speed
LIFT_SPEED = 0.35                   # a planted ankle (flat stance) / contact point (rockers) rises or sinks slower (m/s)
# a turn on the spot's step (analyze): the library's turns shuffle, lifting a stepping foot only 1-4 cm while the
# planted foot's ankle circles its ball at 0.2-0.3 m/s, so neither a height band nor a speed limit alone tells them apart
TURN_LIFT, TURN_LIFT_END = 0.006, 0.003     # a step rides this much higher than the other foot (m), until under the end
TURN_MOVING = 0.15                          # ... while its ankle moves (m/s)
TURN_SWEEP, TURN_SWEEP_END = 0.55, 0.35     # or its ankle sweeps faster than a pivot carries it (m/s), until under the end


def twist_z(q):
    """the twist of q about +Z (Blender's up: three's +Y), and its angle"""
    n = math.hypot(q.w, q.z)
    if n < 1e-8:
        return Quaternion(), 0.0
    tw = Quaternion((q.w / n, 0.0, 0.0, q.z / n))
    return tw, 2.0 * math.atan2(q.z / n, q.w / n)


def strip_hips_yaw(q):
    """stripHipsYaw: swing = q * twist^-1 (the authored pitch and roll kept, the yaw about the up axis gone)"""
    tw, _a = twist_z(q)
    return (q @ tw.inverted()).normalized()


class ControllerClip:
    """one clip as the controller plays it: stripped, cached as normalized rotations, measured on the body"""

    def __init__(self, h, slot, clip, strip_hips_position=True, strip_head=True, strip_hips_rot=False,
                 turn_root_yaw=False, mask=None, loop=True):
        self.h, self.slot, self.clip = h, slot, clip
        self.duration = float(clip.duration)
        self.loop = loop
        self.n = max(2, int(math.ceil(self.duration * RATE)))
        self.dt = self.duration / self.n
        names = [n for n in h.humanoid]
        bound = [n for n in names if h.humanoid[n] in clip.rot]
        if strip_head:
            bound = [n for n in bound if n not in ('head', 'neck')]
        if mask is not None:
            bound = [n for n in bound if n in mask]
        self.bones = bound
        hb = h.humanoid['hips']
        Q = np.zeros((self.n + 1, len(bound), 4))
        P = np.zeros((self.n + 1, 3))
        raw_hips_yaw = np.zeros(self.n + 1)
        for k in range(self.n + 1):
            rot, loc = clip.sample(min(k * self.dt, self.duration), loop=False)
            for j, nm in enumerate(bound):
                b = h.humanoid[nm]
                q = h.normalized_from_basis(b, rot[b])
                Q[k, j] = (q.w, q.x, q.y, q.z)
            if hb in loc:
                P[k] = tuple(h.hips_location_offset(loc[hb]))
            if 'hips' in bound:
                qh = Quaternion(Q[k, bound.index('hips')])
                raw_hips_yaw[k] = twist_z(qh)[1]
        self.has_hips_position = hb in clip.loc and mask is None
        # ROOT MOTION (extractRootMotion): the hips curve before the strip, 48 + 1 samples of the clip's duration
        self.root_curve = P.copy()
        N48 = 48
        idx = np.linspace(0, self.n, N48 + 1)
        self.root_motion = {'N': N48, 'dur': self.duration,
                            'xyz': np.stack([np.interp(idx, np.arange(self.n + 1), P[:, c]) for c in range(3)], axis=1)}
        self.strip_hips_position = strip_hips_position or not self.has_hips_position
        if self.strip_hips_position:
            P[:] = 0.0
        self.hips_yaw = np.unwrap(raw_hips_yaw)
        self.turn_root_yaw = turn_root_yaw
        if 'hips' in bound and (strip_hips_rot or turn_root_yaw):
            j = bound.index('hips')
            for k in range(self.n + 1):
                q = Quaternion(Q[k, j])
                if strip_hips_rot:
                    q = strip_hips_yaw(q)
                else:
                    q = (Quaternion((0.0, 0.0, 1.0), -(self.hips_yaw[k] - self.hips_yaw[0])) @ q).normalized()
                Q[k, j] = (q.w, q.x, q.y, q.z)
        # hemisphere-continuous so neighbours interpolate the short way
        for k in range(1, self.n + 1):
            flip = np.einsum('ij,ij->i', Q[k], Q[k - 1]) < 0.0
            Q[k, flip] *= -1.0
        self.Q, self.P = Q, P
        self.gait = None
        self.mask = mask

    def get_clip(self):
        return self

    # ---------------------------------------------------------------------------------------------- sampling
    def _index(self, t, loop):
        if loop and self.duration > 0:
            t = t % self.duration
        t = min(max(t, 0.0), self.duration)
        x = t / self.dt
        k = min(int(x), self.n - 1)
        return k, x - k

    def sample(self, t, loop=None):
        """-> ({humanoid name: Quaternion (normalized, Blender's axes)}, hips offset Vector or None (stripped))"""
        k, u = self._index(t, self.loop if loop is None else loop)
        a, b = self.Q[k], self.Q[k + 1]
        q = a * (1.0 - u) + b * u
        q /= np.linalg.norm(q, axis=1)[:, None]
        N = {nm: Quaternion(q[j]) for j, nm in enumerate(self.bones)}
        hips = None if self.strip_hips_position else Vector(self.P[k] * (1.0 - u) + self.P[k + 1] * u)
        return N, hips

    def root_yaw_progress(self, t):
        """for a turn: the hips' yaw turned since the clip's start (rad), the root takes it"""
        k, u = self._index(t, False)
        return float((self.hips_yaw[k] * (1.0 - u) + self.hips_yaw[k + 1] * u) - self.hips_yaw[0])

    @property
    def total_root_yaw(self):
        return float(self.hips_yaw[-1] - self.hips_yaw[0])

    def stance_at(self, t, side, loop=None):
        """the measured stance (0..1, interpolated between samples) of a foot at clip time t; 1 for an unmeasured clip"""
        g = self.gait
        if g is None:
            return 1.0
        loop = self.loop if loop is None else loop
        if loop and self.duration > 0:
            t = t % self.duration
        x = min(max(t, 0.0), self.duration) / g.dt
        k = int(x)
        u = x - k
        st = g.stance[side]
        if g.cyclic:
            return float(st[k % g.n]) * (1.0 - u) + float(st[(k + 1) % g.n]) * u
        k = min(k, g.n - 1)
        return float(st[k]) * (1.0 - u) + float(st[min(k + 1, g.n - 1)]) * u

    # ---------------------------------------------------------------------------------------------- distance matching
    def phase_at_time(self, t):
        """the normalized gait phase (0..1, 0 = the left strike) at clip time t"""
        g0 = self.gait.phase0 if self.gait is not None else 0.0
        return ((t / self.duration) - g0) % 1.0

    def time_at_phase(self, ph):
        g0 = self.gait.phase0 if self.gait is not None else 0.0
        return ((ph + g0) % 1.0) * self.duration

    def travel_at_phase(self, ph):
        """forward travel since the left strike at normalized phase ph (m, 0..stride)"""
        g = self.gait
        x = ((ph + g.phase0) % 1.0) * g.n
        k = min(int(x), g.n - 1)
        u = x - k
        k0 = int(round(g.phase0 * g.n)) % g.n
        tr = g.travel[k] + (g.travel[k + 1] - g.travel[k]) * u
        tr0 = g.travel[k0]
        return (tr - tr0) % g.stride if g.stride > 1e-6 else 0.0

    def phase_at_travel(self, d):
        """distance matching: the normalized phase at which the cycle has travelled d (m, any value: taken modulo the
        stride) since the left strike"""
        g = self.gait
        if g is None or g.stride <= 1e-6:
            return 0.0
        k0 = g.phase0 * g.n
        tr0 = float(np.interp(k0, np.arange(g.n + 1), g.travel))
        target = (tr0 + (d % g.stride)) % g.stride
        x = float(np.interp(target, g.travel, np.arange(g.n + 1)))
        return ((x / g.n) - g.phase0) % 1.0

    def lat_at_phase(self, ph):
        g = self.gait
        x = ((ph + g.phase0) % 1.0) * g.n
        return float(np.interp(x, np.arange(g.n + 1), np.concatenate([g.lat_pos, g.lat_pos[:1]])))


# -------------------------------------------------------------------------------------------------- the analysis
def _periodic_hann(x, r):
    if r <= 0:
        return np.asarray(x, dtype=np.float64).copy()
    w = np.array([0.5 - 0.5 * math.cos(2.0 * math.pi * (k + r + 1) / (2 * r + 2)) for k in range(-r, r + 1)])
    w /= w.sum()
    x = np.asarray(x, dtype=np.float64)
    return sum(wk * np.roll(x, -k, axis=0) for wk, k in zip(w, range(-r, r + 1)))


def _hysteresis(start, keep):
    """each run of `start` grown both ways through the neighbouring samples where `keep` holds"""
    out = start.copy()
    n = len(out)
    for k in range(1, n):
        if out[k - 1] and keep[k]:
            out[k] = True
    for k in range(n - 2, -1, -1):
        if out[k + 1] and keep[k]:
            out[k] = True
    return out


def _clean_runs(m, min_run, periodic):
    """drop runs (True or False) shorter than min_run samples"""
    m = m.copy()
    n = len(m)
    for _ in range(2):
        for val in (True, False):
            seq = range(2 * n) if periodic else range(n)
            runs, start = [], None
            for kk in seq:
                v = m[kk % n]
                if v == val and start is None:
                    start = kk
                if v != val and start is not None:
                    runs.append((start, kk))
                    start = None
            if start is not None and not periodic:
                runs.append((start, n))
            for a, b in runs:
                if b - a < min_run and a < n and not (not periodic and (a == 0 or b == n)):
                    for kk in range(a, b):
                        m[kk % n] = not val
    return m


def _phases(st, periodic):
    """per sample: how far through its swing (u, 0 at the lift, 1 at the landing) / its stance (p) the foot is"""
    n = len(st)
    u, p = np.zeros(n), np.zeros(n)
    for arr, val in ((u, False), (p, True)):
        if periodic and (st.all() or not st.any()):
            if bool(st[0]) == val:
                arr[:] = np.arange(n) / n
            continue
        k0 = int(np.argmax(st != val)) if periodic else 0
        cur = None
        runs = []
        rng = [(k0 + j) % n for j in range(n)] if periodic else range(n)
        for k in rng:
            if bool(st[k]) == val:
                if cur is None:
                    cur = [k, 0]
                cur[1] += 1
            elif cur is not None:
                runs.append(cur)
                cur = None
        if cur is not None:
            runs.append(cur)
        for start, ln in runs:
            for j in range(ln):
                arr[(start + j) % n] = (j + 0.5) / ln
    return u, p


def _no_flight(st, periodic):
    """a walk has no flight: where neither foot is down, the foot that was down last stays down (its toe-off later)"""
    L, R = st['left'].copy(), st['right'].copy()
    n = len(L)
    for _ in range(2):
        for k in (range(n) if periodic else range(1, n)):
            if not L[k] and not R[k]:
                kp = (k - 1) % n
                if L[kp] and not R[kp]:
                    L[k] = True
                elif R[kp] and not L[kp]:
                    R[k] = True
    return {'left': L, 'right': R}


class GaitAnalysis:
    """what analyze measured on one clip (the module's doc)"""

    def __repr__(self):
        return (f'GaitAnalysis({self.slot}: stride {self.stride:.3f} m, {self.v_native:.3f} m/s, stance '
                f'{self.stance_fraction["left"]:.2f}/{self.stance_fraction["right"]:.2f}, double {self.double_support:.2f}, '
                f'flight {self.flight:.2f}, phase0 {self.phase0:.3f})')


def analyze(body, cclip, cyclic=None, tol=TOL):
    """measure a ControllerClip on `body` (round one's locomotion.Body): the module's doc. cyclic: a looping gait
    (default: a gait slot)"""
    cyclic = (cclip.slot in GAIT_SLOTS) if cyclic is None else cyclic
    turn = cclip.slot in TURN_SLOTS
    n = cclip.n if cyclic else cclip.n + 1
    dt = cclip.dt
    M = Matrix.Identity(4)
    S = {s: {'P': [], 'an': []} for s in SIDES}
    off_all = []
    for k in range(n):
        t = k * dt
        N, _h = cclip.sample(t, loop=cyclic)
        full = {nm: N.get(nm, Quaternion()) for nm in body.h.humanoid}
        # the analysis plays the clip WITH its root motion (the stance is stationary in a root-motion clip's space)
        off = Vector([float(np.interp(min(t, cclip.duration), np.arange(cclip.n + 1) * dt, cclip.root_curve[:, c]))
                      for c in range(3)])
        if cclip.turn_root_yaw:
            full['hips'] = Quaternion((0.0, 0.0, 1.0), cclip.root_yaw_progress(t)) @ full['hips']
        full = leg_clamps(body, full)                    # my body's legs as they will play (the joint clamps)
        off_all.append(off)
        ph, Wh = body.hips(M, off, full)
        for s in SIDES:
            fk = body.leg_fk(s, ph, Wh, full)
            S[s]['P'].append(body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to']))
            S[s]['an'].append(np.array(fk['p_an']))
    OFF = np.array([tuple(o) for o in off_all])
    disp = (cclip.root_curve[-1] - cclip.root_curve[0]) if cyclic else np.zeros(3)
    g = GaitAnalysis()
    g.slot, g.n, g.dt, g.duration, g.cyclic = cclip.slot, n, dt, cclip.duration, cyclic

    def vel(X):
        if cyclic:
            XX = np.concatenate([X[-1:] - disp, X, X[:1] + disp], axis=0)
            return (XX[2:] - XX[:-2]) / (2 * dt)
        return np.gradient(X, dt, axis=0)
    A = {s: np.array(S[s]['an']) for s in SIDES}
    Va = {s: vel(A[s]) for s in SIDES}
    P = {s: np.array(S[s]['P']) for s in SIDES}
    VP = {s: vel(P[s]) for s in SIDES}
    Z = {s: P[s][:, :, 2].min(axis=1) for s in SIDES}
    rel = {s: P[s][:, :, 2] - Z[s][:, None] for s in SIDES}
    min_run = max(2, int(round(0.05 / dt)))
    # THE TREADMILL
    if cyclic:
        allh = np.concatenate([Va[s][:, :2] for s in SIDES])
        vf = -allh[:, 1]                                             # forward is -Y in the armature's axes
        slow = vf <= np.percentile(vf, 40)
        T = np.array([*np.median(allh[slow], axis=0), 0.0])
    else:
        T = np.zeros(3)
    allv = np.concatenate([Va[s] for s in SIDES])
    Sv = float(np.percentile(np.linalg.norm(allv - T, axis=1), 90)) if cyclic else 1.0
    g.T, g.swing_speed = Vector(T), Sv
    # THE STANCE
    g.stance, g.core = {}, {}
    for s in SIDES:
        if not cyclic and not turn:
            st = np.ones(n, dtype=bool)                              # a stationary clip: both feet stand
            core = st.copy()
        elif turn:
            # a turn steps round on its feet: a foot steps where it rides higher than the other while it moves, or
            # where its ankle sweeps faster than a pivot carries it; anywhere else it is planted and pivots on it
            other = 'right' if s == 'left' else 'left'
            hi = Z[s] - Z[other]
            va = np.linalg.norm(Va[s][:, :2], axis=1)
            step = _hysteresis((hi > TURN_LIFT) & (va > TURN_MOVING), hi > TURN_LIFT_END) | \
                _hysteresis(va > TURN_SWEEP, va > TURN_SWEEP_END)
            core = ~step
            st = _clean_runs(core, min_run, False)
        else:
            z = Z[s]
            band = z <= z.min() + max(0.05, 0.6 * (z.max() - z.min()))
            if abs(disp[1]) > 0.02 or abs(disp[2]) > 0.02:
                band = np.ones(n, dtype=bool)                        # root motion moves the stance height: no band
            # a planted foot moves with the treadmill across and does not rise or sink: in the clip's root-motion space
            # its ankle's height holds through the flat stance, its contact point's through the rockers (a lifting
            # foot keeps a lowest point of its own, so the vertical speed, not that point's height, ends the stance)
            lift = max(LIFT_SPEED, 0.15 * Sv)                        # a run's stance bobs faster than a walk's
            core = (np.linalg.norm(Va[s][:, :2] - T[:2], axis=1) < tol * Sv) & (np.abs(Va[s][:, 2]) < lift) & band
            core = _clean_runs(core, min_run, True)
            err = np.linalg.norm(VP[s][:, :, :2] - T[None, None, :2], axis=2)
            err[rel[s] > 0.01] = np.inf
            err[np.abs(VP[s][:, :, 2]) > lift] = np.inf
            match = (err.min(axis=1) < tol * Sv) & band
            st = core.copy()
            for _ in range(n):
                grow = match & ~st & (np.roll(st, 1) | np.roll(st, -1))
                if not grow.any():
                    break
                st |= grow
            st = _clean_runs(st, min_run, True)
        g.core[s], g.stance[s] = core, st
    if cyclic and cclip.slot in WALK_LIKE:
        g.stance = _no_flight(g.stance, True)
    if turn:
        # a turn on the spot has no flight: where both feet would be stepping, the lower one stays down
        both = ~g.stance['left'] & ~g.stance['right']
        low_l = Z['left'] <= Z['right']
        g.stance['left'] = g.stance['left'] | (both & low_l)
        g.stance['right'] = g.stance['right'] | (both & ~low_l)
    g.u, g.p = {}, {}
    for s in SIDES:
        g.u[s], g.p[s] = _phases(g.stance[s], cyclic)
    # THE SUPPORT: the root's velocity over the ground = its own root motion - the planted contact's velocity (the low
    # sole point that moves most nearly with the treadmill: the heel at the strike, the ball at the push-off)
    doff = vel(OFF)
    vc = {}
    for s in SIDES:
        err = np.linalg.norm(VP[s] - T[None, None, :], axis=2)
        err[rel[s] > 0.01] = np.inf
        kbest = np.argmin(err, axis=1)
        vc[s] = VP[s][np.arange(n), kbest]
    if cyclic:
        load = {s: _periodic_hann(g.stance[s].astype(float), max(1, int(round(0.035 / dt)))) for s in SIDES}
    else:
        load = {s: g.stance[s].astype(float) for s in SIDES}
    den = load['left'] + load['right']
    vsup = (load['left'][:, None] * vc['left'] + load['right'][:, None] * vc['right']) / np.maximum(den, 1e-9)[:, None]
    zsup = (load['left'] * Z['left'] + load['right'] * Z['right']) / np.maximum(den, 1e-9) - OFF[:, 2]
    planted = den > 0.15
    if planted.any() and not planted.all():
        vsup[~planted] = vsup[planted].mean(axis=0)                  # a flight: the planted pace carries on
        idx = np.arange(n)
        zsup[~planted] = np.interp(idx[~planted], idx[planted], zsup[planted], period=n if cyclic else None)
    rootv = doff - vsup
    fwd, lat, rise = -rootv[:, 1], rootv[:, 0], rootv[:, 2]
    if cyclic:
        r = max(1, int(round(0.05 / dt)))
        fwd = _periodic_hann(fwd, r)
        lat = _periodic_hann(lat, r)
        lat = lat - lat.mean()
    g.fwd, g.lat, g.rise, g.zsup = fwd, lat, rise, zsup
    g.stride = float(fwd.mean() * cclip.duration) if cyclic else 0.0
    g.v_native = float(fwd.mean()) if cyclic else 0.0
    g.g = fwd / max(abs(float(fwd.mean())), 1e-6) if cyclic else np.ones(n)
    g.rise_per_cycle = float(disp[2]) if cyclic else 0.0
    # distance matching's tables: forward travel since the cycle's start (monotone: a clip that steps back for a
    # moment holds), the sideways sway (position, mean 0)
    step = np.maximum(fwd, 0.0) * dt
    if cyclic and step.sum() > 1e-6:
        step *= max(g.stride, 1e-6) / step.sum()
    g.travel = np.concatenate([[0.0], np.cumsum(step)])
    lp = np.concatenate([[0.0], np.cumsum(lat * dt)])[:-1]
    g.lat_pos = lp - lp.mean()
    st_l = g.stance['left']
    if cyclic and st_l.any() and not st_l.all():
        k = int(np.flatnonzero(st_l & ~np.roll(st_l, 1))[0])
        g.phase0 = k / n
    else:
        g.phase0 = 0.0
    # the passing phases: where each foot is mid-swing, beside the planted one (a start begins there, a stop ends there)
    g.passing = {}
    for s in SIDES:
        sw = ~g.stance[s]
        if cyclic and sw.any() and not sw.all():
            ks = np.flatnonzero(sw)
            k = int(ks[np.argmin(np.abs(g.u[s][ks] - 0.5))])
            g.passing[s] = ((k / n) - g.phase0) % 1.0
    both = g.stance['left'] & g.stance['right']
    g.double_support = float(both.mean())
    g.flight = float((~g.stance['left'] & ~g.stance['right']).mean())
    g.stance_fraction = {s: float(g.stance[s].mean()) for s in SIDES}
    g.lift = {s: Z[s] - OFF[:, 2] - zsup for s in SIDES}
    g.ankle = A
    g.zlow = Z
    return g


# -------------------------------------------------------------------------------------------------- the library
def load_controller_clip(h, slot, body=None, analyze_on=True, source=None, **kw):
    """one slot through round one's load_clip, stripped as the controller strips it -> ControllerClip (None if the
    library has no such clip). source: a .vrma path played as this slot (the original's vrmaLibrary override)"""
    try:
        vrma_path(source or slot)
    except FileNotFoundError:
        return None
    clip = load_clip(h, source or slot)
    if slot in TURN_SLOTS:
        kw.setdefault('turn_root_yaw', True)
    kw.setdefault('strip_hips_rot', slot in STRIP_HIPS_ROT)
    kw.setdefault('loop', slot not in ONE_SHOT and slot not in TURN_SLOTS)
    cc = ControllerClip(h, slot, clip, **kw)
    if analyze_on and body is not None and kw.get('mask') is None:
        cc.gait = analyze(body, cc)
    return cc


_LIBRARY = {}          # (rig, slot, source) -> ControllerClip: measured on its body once (a clip is stateless)


def _alive(c):
    """a cached clip whose Blender action still exists (a cleaned scene invalidates it)"""
    try:
        return c is None or c.clip.action.name in bpy.data.actions
    except ReferenceError:
        return False


def load_standard_animations(h, body, slots=None, extra=TURN_SLOTS, log=None, library=None):
    """loadStandardAnimations: every standard slot (and the turns) -> {slot: ControllerClip or None}. library (the
    original's vrmaLibrary option): {slot: a .vrma path} played instead of the shared library's clip for those slots"""
    out = {}
    for slot in list(slots or STANDARD_SLOTS) + list(extra or []):
        src = (library or {}).get(slot)
        key = (h.arm.as_pointer(), h.arm.name, slot, src)
        if key in _LIBRARY and _alive(_LIBRARY[key]):
            c = _LIBRARY[key]
        else:
            c = _LIBRARY[key] = load_controller_clip(h, slot, body, source=src)
        out[slot] = c
        if log and c is not None and c.gait is not None and c.gait.cyclic:
            g = c.gait
            log(f'[controller] {slot}: {c.duration:.3f} s, stride {g.stride:.3f} m ({g.v_native:.3f} m/s on this body), '
                f'stance {g.stance_fraction["left"]:.2f}/{g.stance_fraction["right"]:.2f}, double {g.double_support:.2f}, '
                f'flight {g.flight:.2f}, treadmill {tuple(round(c_, 2) for c_ in g.T)}, rise {g.rise_per_cycle:.3f} m')
    return out


def load_emote_clip(h, slot, loop=True, body=None, source=None):
    """loadEmote's clip: every track kept (an emote's authored head and hips motion come through); source: a .vrma
    path played as this slot"""
    try:
        vrma_path(source or slot)
    except FileNotFoundError:
        return None
    cc = ControllerClip(h, slot, load_clip(h, source or slot), strip_hips_position=False, strip_head=False, loop=loop)
    if body is not None:
        cc.gait = analyze(body, cc, cyclic=False)
    return cc


def upper_body_mask(h):
    """loadGesture's mask: the upper body's humanoid bones (and every finger the rig has)"""
    keep = set(n for n in UPPER_BODY if n in h.humanoid)
    keep |= set(n for n in h.humanoid if any(w in n for w in FINGER_WORDS))
    return keep


def load_gesture_clip(h, slot, loop=True, source=None):
    """loadGesture's clip: the upper body's rotations only (None when nothing survives the mask)"""
    try:
        vrma_path(source or slot)
    except FileNotFoundError:
        return None
    cc = ControllerClip(h, slot, load_clip(h, source or slot), strip_hips_position=True, strip_head=False,
                        mask=upper_body_mask(h), loop=loop)
    return cc if cc.bones else None
