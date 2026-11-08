"""eidoblend.characters.locomotion: a VRM walking a path over uneven ground with its feet planted (characters.md, "Walking").

    from eidoblend.characters import load_vrm, load_clip, walk_path, Ground
    me = load_vrm('claude_robot')
    walk = load_clip(me, 'walk')
    rep = walk_path(me, walk, [(0, 0), (10, 0)], Ground(obj=terrain), f0=1, face={'happy': 1.0})

The WebGPU edition's controller plays the stock walk on a kinematic body and grounds the feet with foot IK each frame. Played
in place, the stock walk's stance foot slides back under the body: a body moved at any other speed, or a clip phase that
drifts, skates. Here the walk is simulated ONCE, in frame order at the scene fps, and keyed (any frame then renders alone,
no handler):

  THE CLIP       sampled from its fcurves at clip time tc = phase + t * speed / v_clip (three's timeScale), its pose put
                 through the body's DOF pass first when the body has one (the robot: rehome, the arms, the leg clamps)
  THE STANCE     analyze_clip measures, on THIS body, the treadmill (v_native: the flat stance ankle's steady backward
                 speed, 1.40 m/s on my body) and each foot's stance: every sample in which some low point of the sole
                 (within 1 cm of its lowest) moves with the treadmill. That is the heel's edge from the strike as the foot
                 rolls down onto it, the whole sole flat, the ball through the toe roll: so the walk keeps the clip's
                 double support (both feet down while the weight crosses, 12 % of the cycle) and its push-off
  THE SUPPORT    the stock walk has no hips translation, so in place its body neither travels nor bobs: the stance contact
                 moves back under it instead (1.4 to 1.9 m/s through a stance: fastest about the double support, slowest
                 at mid-stance, the inverted pendulum's speed; a 1.50 m stride a cycle on my body, v_clip 1.56 m/s) and
                 rises 35-40 mm at the double support (where a walking pelvis dips). The root follows that support
                 contact: its travel along the path, its sway across it, and its height (THE PELVIS)
  THE PATH       a polyline, every corner rounded by an arc of radius speed / max_turn_rate (shrunk to fit half of each
                 side); the root travels along it by the support's travel (on average `speed`, default v_clip), heading
                 along its tangent. Past the end the line runs on straight for the last step's few cm
  THE FEET       a stance foot is LOCKED: the points of its sole in contact in this frame AND the last do not slide and the
                 foot does not turn on the ground (its roll about the contact, heel to flat to ball, plays as the clip has
                 it). Its heading is set at the landing, turned toward where the body will face at mid-stance, so in a
                 turn the hips take the turn and the foot does not twist. Its sole tilts onto the ground's plane under it
                 and is set down so the lowest sole point touches (no float, no sink); through the flat stance it lies
                 flat (the clip's degree of wobble rocked a rigid sole heel to toe); its turn is planned inside the
                 ankle's range seen from the clip's shin (on a rise the heel lifts a little early instead of the solve's
                 clamp tipping it); through the toe roll the toes lie on the ground; on curved ground it rests on two
                 points rather than rocking from one end to the other. A swing foot follows the clip (the lock's
                 correction easing out over the first half of the swing), over the highest ground its sole sweeps and
                 never closer to it than `clearance` mid-swing: the stock walk's mid-swing toe passes 4 mm over its floor
                 on my legs, and on uneven ground that dragged the foot. Both feet are carried `width` out from the clip's
                 narrow human track (robot_dof's LEG_CLEARANCE width: my feet are wider than a human's)
  THE PELVIS     for a planted leg the root goes where that leg has the clip's own hip-to-ankle length at this phase (its
                 knee is the clip's knee; the bob is the clip's), the two legs shared by their load through a double
                 support, capped so every loaded leg reaches its target (the hips come down to a cap at most 0.4 m/s
                 ahead of it and rise out of it at most 0.5 m/s), then lowered wherever a straight planted leg still
                 comes up short, and solved again. pelvis='lower' is the WebGPU controller's rule instead (the lower
                 foot's ground: made for stairs, it crouches the leg on the higher foot over bumps)
  THE LEGS       two-bone IK per frame: the knee's pin angle from the hip-ankle distance (the knee is a hinge), the thigh
                 turned onto the target by the least rotation, then swivelled so the knee pin lies square to the foot's
                 forward (the ankle has no yaw: the foot's heading is the leg's), the foot's turn the target's; then the
                 DOF clamps again and the hip stages solved
  THE FACE       the expression weights (`face`), the head's expression pose and the crown (robot_dof) in the same pass

walk_path returns a report measured on the RESULT (the feet's points where Blender's skinned mesh puts them:
checks.fk_matches_blender proves the two agree), not on the lock's own targets:
  stances   per planted foot: the slip along the ground a frame of the points in contact (within 2.5 mm) in this frame
            and the last (the least-moving one: a foot rolling about its contact does not slip; a point rising or
            settling inside the contact band is the sole rolling on or off, not sliding), their centroid's slip, the
            foot's turn on the ground a frame, the lowest point's gap over the ground, and any rock (no point staying
            down two frames running)
  swings    per swing: the least clearance, the least in its middle, and every frame it drags (on the ground mid-swing,
            or anywhere in it faster than 1 m/s)
  double_support / airborne   the frames with both feet on the ground / neither
  gait      the planted knee against the clip's own (overall, and frame by frame at the same phase), the root's height
            range and turn rate
  pelvis_lowered_mm, swing_guard   what the last two corrections had to do (frame, mm)
checks.feet holds the report to limits.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import robot_dof as dof
from ._math import D2R, R2D, clamp, ease, hann_smooth, q_from_three, q_to_three, smooth, wrap_pi
from .ground import SIDES, foot_points

FWD = Vector((0.0, -1.0, 0.0))          # a VRM's forward in the armature's axes (it faces -Y)
WIDTH = 0.072                           # robot_dof LEG_CLEARANCE.width
NEED = (0.18, 0.23)                     # ... .need: the clip's ankles already this far apart need no width
LOCK_ROUNDS = 8                         # solve -> measure the planted foot's slip, turn and gap -> move its target, per frame
CLEARANCE = 0.03                        # the swing sole's least height over the ground it sweeps, mid-swing (m)
MAX_TURN_RATE = 1.0                     # rad/s on a path's corners: the arc's radius is speed / this
CONTACT = 0.0025                        # a sole point this close to the ground is touching it (the report's measure)
TREAD_TOL = 0.35                        # a low sole point moving within this fraction of the treadmill's speed is planted
YAW_CAP = 15.0 * D2R                    # the most the lock turns a planted foot's target back
LOCK_BAND = 0.0005                      # the contact's weighting: points this much above the lowest count e^-1 as much
FLAT = 1.5 * D2R                        # a planted sole within this of flat on the ground is set flat (the clip wobbles 1 deg)
LOAD_FRAMES = 4                         # a landing foot takes the pelvis's load over this many frames
REACH_MARGIN = 0.006                    # the cap keeps a loaded leg this much short of straight
PELVIS_ROUNDS = 4                       # solve, lower the hips where a planted foot is still short, solve again


def _m3(q):
    return np.array(q.to_matrix())


class Body:
    """FK for one VRM in the normalized frame (Blender's axes): rest heads, leg vectors, the feet's points, the DOF pass"""

    def __init__(self, h, feet=None, use_dof=None, hinges=None):
        self.h = h
        self.H = {n: h.rest_head[b] for n, b in h.humanoid.items()}
        self.feet = feet or foot_points(h)
        self.robot = ('leftHipPitch' in h.arm.data.bones) if use_dof is None else use_dof
        self.legs = dof.LegStages.from_handle(h) if self.robot else None
        if self.robot:
            from .vrm import joints_record
            rec = joints_record(h)
            self.arms = dof.ArmDOF.from_handle(h, (rec or {}).get('hinges') if hinges is None else hinges)
        else:
            self.arms = None
        self.leg = {}
        for s in SIDES:
            u = self.H[s + 'LowerLeg'] - self.H[s + 'UpperLeg']
            w = self.H[s + 'Foot'] - self.H[s + 'LowerLeg']
            self.leg[s] = {'u': u, 'w': w, 't': self.H[s + 'Toes'] - self.H[s + 'Foot'],
                           'hip': self.H[s + 'UpperLeg'] - self.H['hips'], 'reach': (u + w).length}

    # ---------------------------------------------------------------------------------------------------- the clip
    def clip_pose(self, clip, tc, dt=None):
        """the clip's normalized pose at tc (Blender's axes) after the DOF pass -> (N {name: Quaternion}, hips offset)"""
        h = self.h
        rot, loc = clip.sample(tc)
        N = {}
        for n, b in h.humanoid.items():
            q = rot.get(b)
            N[n] = h.normalized_from_basis(b, q) if q is not None else Quaternion()
        off = h.hips_location_offset(loc.get(h.humanoid['hips'], Vector()))
        if self.robot:
            p3 = {n: q_to_three(q) for n, q in N.items()}
            dof.rehome_body(p3)
            self.arms.apply(p3, dt or 1.0 / 24.0)
            dof.apply_hardware_dof(p3, dof.LEG_JOINTS, None)
            N = {n: q_from_three(q) for n, q in p3.items()}
        return N, off

    # ---------------------------------------------------------------------------------------------------- FK
    def hips(self, M, off, N):
        Qr = M.to_quaternion()
        return M @ (self.H['hips'] + off), Qr @ N['hips']

    def leg_fk(self, side, p_hips, W_hips, N):
        L, s = self.leg[side], side
        W_th = W_hips @ N[s + 'UpperLeg']
        W_sh = W_th @ N[s + 'LowerLeg']
        W_ft = W_sh @ N[s + 'Foot']
        W_to = W_ft @ N[s + 'Toes']
        p_th = p_hips + W_hips @ L['hip']
        p_kn = p_th + W_th @ L['u']
        p_an = p_kn + W_sh @ L['w']
        p_to = p_an + W_ft @ L['t']
        return {'p_th': p_th, 'p_kn': p_kn, 'p_an': p_an, 'p_to': p_to, 'W_th': W_th, 'W_sh': W_sh, 'W_ft': W_ft, 'W_to': W_to}

    def sole(self, side, p_an, W_ft, W_to):
        """the foot's points in the world for an ankle position and foot / toes turns: (n, 3)"""
        F, T = self.feet[side]['Foot'], self.feet[side]['Toes']
        p_to = np.array(p_an + W_ft @ self.leg[side]['t'])
        out = [F @ _m3(W_ft).T + np.array(p_an)]
        if len(T):
            out.append(T @ _m3(W_to).T + p_to)
        return np.concatenate(out, axis=0)

    # ---------------------------------------------------------------------------------------------------- IK
    def knee_for(self, side, d):
        """the knee's pin angle (rad, normalized: + bends the shin back) putting the ankle d from the hip"""
        L = self.leg[side]
        u, w = L['u'], L['w']
        lo, hi = 0.0, 112.0 * D2R

        def f(k):
            return (u + Quaternion((1.0, 0.0, 0.0), k) @ w).length
        if d >= f(lo):
            return lo
        if d <= f(hi):
            return hi
        for _ in range(48):
            mid = 0.5 * (lo + hi)
            if f(mid) > d:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def solve_leg(self, side, p_hips, W_hips, N, T, W_ft_t, swivel=1.0):
        """two-bone IK: N's thigh, shin and foot set so the ankle reaches T and the foot turns to W_ft_t (world)"""
        s, L = side, self.leg[side]
        p_th = p_hips + W_hips @ L['hip']
        k = self.knee_for(side, (T - p_th).length)
        N[s + 'LowerLeg'] = Quaternion((1.0, 0.0, 0.0), k)
        vk = L['u'] + N[s + 'LowerLeg'] @ L['w']
        W_th = W_hips @ N[s + 'UpperLeg']
        a_c = W_th @ vk
        W_th = a_c.rotation_difference(T - p_th) @ W_th
        if swivel > 0:
            n = (T - p_th).normalized()
            X = W_th @ Vector((1.0, 0.0, 0.0))
            F = W_ft_t @ FWD
            Xp = X - n * X.dot(n)
            A, B, C = Xp.dot(F), n.cross(X).dot(F), X.dot(n) * n.dot(F)
            r = math.hypot(A, B)
            if r > 1e-6:
                ph = math.atan2(B, A)
                c = clamp(-C / r, -1.0, 1.0)
                h = math.acos(c)
                cand = [((ph + h + math.pi) % (2 * math.pi)) - math.pi, ((ph - h + math.pi) % (2 * math.pi)) - math.pi]
                sig = min(cand, key=abs)
                W_th = Quaternion(n, swivel * sig) @ W_th
        N[s + 'UpperLeg'] = W_hips.inverted() @ W_th
        W_sh = W_th @ N[s + 'LowerLeg']
        N[s + 'Foot'] = W_sh.inverted() @ W_ft_t

    def project_legs(self, N, stages=True):
        """the leg clamps (and the hip stages) on N, in place; -> the stages' turns (Blender's axes) or {}"""
        if not self.robot:
            return {}
        p3 = {n: q_to_three(N[n]) for s in SIDES for n in (s + 'UpperLeg', s + 'LowerLeg', s + 'Foot', s + 'Toes')}
        dof.apply_hardware_dof(p3, dof.LEG_JOINTS, self.legs if stages else None)
        for n, q in p3.items():
            N[n] = q_from_three(q)
        if not stages:
            return {}
        return {side: {k: q_from_three(v) for k, v in self.legs.out.get(side, {}).items()} for side in SIDES}


def _yaw(q):
    f = q @ FWD
    return math.atan2(f.y, f.x)


def analyze_clip(body, clip, rate=120):
    """the clip's treadmill on this body: per side, per sample (rate per second over one loop): the sole's points, their
    lowest height, the ankle and its velocity, the stance and the swing's phase;
    -> {'v_native', 'floor', 'period', 'side': {side: {'stance', 'core', 'u', ...}}, ...}"""
    n = max(8, int(round(clip.duration * rate)))
    dtc = clip.duration / n
    M = Matrix.Identity(4)
    S = {s: {'z': [], 'P': [], 'an': []} for s in SIDES}
    hipz = []
    for i in range(n):
        N, off = body.clip_pose(clip, i * dtc, dt=dtc)
        ph, Wh = body.hips(M, off, N)
        hipz.append(ph.z)
        for s in SIDES:
            fk = body.leg_fk(s, ph, Wh, N)
            P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            S[s]['z'].append(float(P[:, 2].min()))
            S[s]['P'].append(P)
            S[s]['an'].append(np.array(fk['p_an']))
    # THE TREADMILL'S SPEED is the stance ankle's: a human clip on my legs does not keep its stance sole at one height
    # (it rises and falls 3-4 cm through the stance), and its lowest region jumps heel / toe, so neither the sole's
    # height nor its lowest point gives the speed. The ankle does: it moves back steadily at the treadmill's speed
    # through the flat stance (measured 1.40 m/s on my body: the lead's 1.44), and forward fast in the swing
    out = {'n': n, 'dtc': dtc, 'period': clip.duration, 'side': {}}
    vs = []
    for s in SIDES:
        A_ = np.array(S[s]['an'])
        vel = (np.roll(A_, -1, axis=0) - np.roll(A_, 1, axis=0)) / (2 * dtc)
        out['side'][s] = {'z': np.array(S[s]['z']), 'P': np.array(S[s]['P']), 'vel': vel, 'an': A_}
        back = vel[:, 1]
        vs.append(back[back > 0.3])
    v_all = np.sort(np.concatenate(vs))
    v_native = float(np.median(v_all[len(v_all) // 4: max(len(v_all) // 4 + 1, 3 * len(v_all) // 4)])) if len(v_all) else 0.0
    floor = []
    for s in SIDES:
        d = out['side'][s]
        core = _clean_mask(np.abs(d['vel'][:, 1] - v_native) < 0.3 * v_native, max(2, int(round(0.06 / dtc))))
        # THE ROCKERS. The ankle's steady speed marks only the flat stance: through the heel strike the foot rolls down
        # about its heel and through the push-off it rolls up about its ball, and the ankle moves differently. The
        # contact point does not: some low point of the sole (within 1 cm of its lowest) moves with the treadmill
        # through both. The stance grows from the flat core while that holds (on my body: one sample before the core
        # at the strike, five after it at the toe-off: the walk's double support)
        P = d['P']
        V = (np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)) / (2 * dtc)
        rel = P[:, :, 2] - P[:, :, 2].min(axis=1, keepdims=True)
        err = np.hypot(V[:, :, 0], V[:, :, 1] - v_native) / max(v_native, 1e-6)
        err[rel > 0.01] = np.inf
        match = err.min(axis=1) < TREAD_TOL
        st = core.copy()
        for _ in range(n):
            grow = match & ~st & (np.roll(st, 1) | np.roll(st, -1))
            if not grow.any():
                break
            st |= grow
        d['core'], d['stance'], d['u'], d['p'] = core, st, _swing_phase(st), _swing_phase(~st)
        w = np.exp(-rel / LOCK_BAND)
        d['vc'] = (V * w[:, :, None]).sum(1) / w.sum(1)[:, None]      # the contact's own velocity (its lowest points')
        # the floor is where the stance sole comes LOWEST (mid-stance, the leg under the hip)
        floor.append(np.percentile(d['z'][core], 10) if core.any() else d['z'].min())
    # THE SUPPORT. The stock walk has no hips translation, so in place its body neither travels nor bobs: the stance
    # contact moves back under it instead, at 1.4 to 1.9 m/s through the stance (fastest about the double support, slowest
    # at mid-stance: the inverted pendulum's speed), 1.57 m/s on average on my body, and rises 35-40 mm at the double
    # support (where a walking pelvis dips). Moved at the ankle's 1.40 m/s on a constant height, a planted foot ended its
    # stance 9 cm closer to the hips than the clip has it and its knee folded 20 deg past the clip's. So the root follows
    # the support contact (the stance feet's, shared by their load through the double support): its travel along the
    # path, its sway across it, its height over the ground. Lightly smoothed (the contact's weighting is noisy sample to
    # sample); the sway's mean is taken out so the root stays on the path
    load = {s: _periodic_hann(out['side'][s]['stance'].astype(float), 4) for s in SIDES}
    den = load['left'] + load['right'] + 1e-9
    vsup = sum(load[s][:, None] * out['side'][s]['vc'] for s in SIDES) / den[:, None]
    zsup = sum(load[s] * out['side'][s]['z'] for s in SIDES) / den
    vf = _periodic_hann(vsup[:, 1], 6)
    vl = _periodic_hann(-vsup[:, 0], 6)
    vl = vl - vl.mean()
    out['support'] = {'fwd': np.concatenate([[0.0], np.cumsum(vf) * dtc]), 'lat': np.concatenate([[0.0], np.cumsum(vl) * dtc]),
                      'z': _periodic_hann(zsup, 4)}
    out['v_clip'] = float(vf.mean())
    out['stride'] = float(out['support']['fwd'][-1])
    out['v_native'] = v_native
    out['floor'] = float(np.mean(floor))
    out['hips_z'] = np.array(hipz)
    sep = np.abs(out['side']['left']['an'][:, 0] - out['side']['right']['an'][:, 0])
    out['ankle_sep'] = sep
    both = out['side']['left']['stance'] & out['side']['right']['stance']
    out['double_support'] = float(both.mean())
    out['stance_fraction'] = {s: float(out['side'][s]['stance'].mean()) for s in SIDES}
    return out


def _periodic_hann(x, r):
    """a Hann-window moving average of a periodic array, radius r samples"""
    if r <= 0:
        return np.asarray(x, dtype=np.float64).copy()
    w = np.array([0.5 - 0.5 * math.cos(2.0 * math.pi * (k + r + 1) / (2 * r + 2)) for k in range(-r, r + 1)])
    w /= w.sum()
    x = np.asarray(x, dtype=np.float64)
    return sum(wk * np.roll(x, -k) for wk, k in zip(w, range(-r, r + 1)))


def _support_at(an, tc):
    """the support's travel (forward, sideways: m since the clip's start, unrolled over loops) and height at clip time tc"""
    sup, n, period = an['support'], an['n'], an['period']
    loops = math.floor(tc / period)
    x = (tc - loops * period) / an['dtc']
    k = min(int(x), n - 1)
    u = x - k
    fwd = loops * sup['fwd'][-1] + sup['fwd'][k] + (sup['fwd'][k + 1] - sup['fwd'][k]) * u
    lat = loops * sup['lat'][-1] + sup['lat'][k] + (sup['lat'][k + 1] - sup['lat'][k]) * u
    z = sup['z'][k] + (sup['z'][(k + 1) % n] - sup['z'][k]) * u
    return fwd, lat, z


def _clean_mask(m, min_run):
    """drop runs (True or False) shorter than min_run samples, periodic"""
    m = m.copy()
    n = len(m)
    for _ in range(2):
        for val in (True, False):
            runs = []
            start = None
            for k in range(2 * n):
                v = m[k % n]
                if v == val and start is None:
                    start = k
                if v != val and start is not None:
                    runs.append((start, k))
                    start = None
            for a, b in runs:
                if b - a < min_run and a < n:
                    for k in range(a, b):
                        m[k % n] = not val
    return m


def _swing_phase(st):
    """per sample, how far through its swing the foot is (0 at the lift, 1 at the landing; 0 in a stance), periodic
    (given ~stance: how far through its stance)"""
    n = len(st)
    u = np.zeros(n)
    if st.all() or not st.any():
        return u
    k0 = int(np.argmax(st))
    runs, cur = [], None
    for j in range(1, n + 1):
        k = (k0 + j) % n
        if not st[k]:
            if cur is None:
                cur = [k, 0]
            cur[1] += 1
        elif cur is not None:
            runs.append(cur)
            cur = None
    for start, ln in runs:
        for j in range(ln):
            u[(start + j) % n] = (j + 0.5) / ln
    return u


def _bump(u):
    """the swing's clearance profile: 0 at the lift and at the landing, 1 through the middle"""
    return smooth(0.0, 0.3, u) * (1.0 - smooth(0.75, 1.0, u))


def _path(points, radius, ds=0.005):
    """the path's centre line, every corner rounded by an arc of `radius` (shrunk to fit half of each side) ->
    (at(s) -> (point Vector, heading rad), length); past its end the line runs on straight (the last frame's step may
    overshoot it by a few cm, and a root clamped there would drag the planted foot)"""
    Q = []
    for p in points:
        v = np.array([float(p[0]), float(p[1])])
        if not Q or np.linalg.norm(v - Q[-1]) > 1e-6:
            Q.append(v)
    if len(Q) < 2:
        raise ValueError('walk_path needs a path of two or more distinct points')
    lens = [float(np.linalg.norm(Q[i + 1] - Q[i])) for i in range(len(Q) - 1)]
    dirs = [(Q[i + 1] - Q[i]) / lens[i] for i in range(len(Q) - 1)]
    trim, corners = [0.0] * len(Q), {}
    for j in range(1, len(Q) - 1):
        d0, d1 = dirs[j - 1], dirs[j]
        phi = math.atan2(d0[0] * d1[1] - d0[1] * d1[0], float(d0 @ d1))
        if abs(phi) < 1e-4:
            continue
        t = min(radius * math.tan(abs(phi) / 2), 0.5 * lens[j - 1], 0.5 * lens[j])
        trim[j] = t
        corners[j] = (phi, t / math.tan(abs(phi) / 2))
    P, H = [], []
    for i in range(len(Q) - 1):
        d = dirs[i]
        h = math.atan2(d[1], d[0])
        a, b = Q[i] + d * trim[i], Q[i + 1] - d * trim[i + 1]
        m = max(1, int(math.ceil(float(np.linalg.norm(b - a)) / ds)))
        for k in range(m):
            P.append(a + (b - a) * (k / m))
            H.append(h)
        if i + 1 in corners:
            phi, r = corners[i + 1]
            c = b + np.array([-d[1], d[0]]) * (r if phi > 0 else -r)
            v0 = b - c
            m = max(1, int(math.ceil(r * abs(phi) / ds)))
            for k in range(m):
                a_ = phi * k / m
                ca, sa = math.cos(a_), math.sin(a_)
                P.append(c + np.array([ca * v0[0] - sa * v0[1], sa * v0[0] + ca * v0[1]]))
                H.append(h + a_)
    P.append(Q[-1])
    H.append(math.atan2(dirs[-1][1], dirs[-1][0]))
    P, H = np.array(P), np.unwrap(np.array(H))
    S = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    total = float(S[-1])

    def at(s):
        if s > total:
            h = float(H[-1])
            return Vector((float(P[-1][0]) + math.cos(h) * (s - total), float(P[-1][1]) + math.sin(h) * (s - total), 0.0)), h
        s = max(s, 0.0)
        k = min(max(int(np.searchsorted(S, s, side='right')) - 1, 0), len(S) - 2)
        u = (s - S[k]) / (S[k + 1] - S[k]) if S[k + 1] > S[k] else 0.0
        p = P[k] + (P[k + 1] - P[k]) * u
        return Vector((float(p[0]), float(p[1]), 0.0)), float(H[k] + (H[k + 1] - H[k]) * u)
    return at, total


def _intervals(flags):
    """runs of True in a list -> [(first, last)]"""
    iv, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            iv.append((start, i - 1))
            start = None
    if start is not None:
        iv.append((start, len(flags) - 1))
    return iv


def walk_path(h, clip, path, ground, f0=1, speed=None, phase=0.0, width=WIDTH, face=None, crown_state=None, head_state=None,
              body=None, ease_frames=4, key=True, action_name=None, preroll=1.0, clearance=CLEARANCE,
              max_turn_rate=MAX_TURN_RATE, pelvis='stance', log=print):
    """walk `h` along `path` (world (x, y) points) over `ground` from frame f0 at `speed` m/s on average (default: the
    clip's own stride speed on this body, v_clip); key one action -> a report (see the module's doc)"""
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt = 1.0 / fps
    body = body or Body(h)
    an = analyze_clip(body, clip)
    v_native, v_clip = an['v_native'], an['v_clip']
    speed = speed or v_clip
    ts = speed / v_clip
    at, total = _path(path, speed / max_turn_rate)
    # the frames: the clip runs at timeScale ts; the root covers the path by the support's travel
    fw0, lt0, _z = _support_at(an, phase)
    travel = []
    while True:
        tc = phase + len(travel) * dt * ts
        fw, lt, zs = _support_at(an, tc)
        travel.append((tc, fw - fw0, lt - lt0, zs))
        if fw - fw0 >= total or len(travel) > 100000:
            break
    nfr = len(travel)
    F = list(range(f0, f0 + nfr))
    log(f'[walk] the clip on this body: stride {an["stride"]:.3f} m a cycle ({v_clip:.3f} m/s; the stance ankle '
        f'{v_native:.3f}), stance {an["stance_fraction"]["left"]:.2f} / {an["stance_fraction"]["right"]:.2f} of the cycle, '
        f'double support {an["double_support"]:.2f}; support height {an["support"]["z"].min() * 1000:.1f}-'
        f'{an["support"]["z"].max() * 1000:.1f} mm, sway {np.ptp(an["support"]["lat"]) * 1000:.1f} mm; '
        f'speed {speed:.3f}, timeScale {ts:.3f}, {total:.2f} m in {nfr} frames')

    def clip_k(tc):
        return int(round((tc % clip.duration) / an['dtc'])) % an['n']

    # ---- pass A: the free walk (root at the support's height over z 0): the clip's pose, the feet where it has them
    A = []
    for i, f in enumerate(F):
        t = i * dt
        tc, fw, lt, zs = travel[i]
        p, psi = at(fw)
        Qr = Quaternion((0.0, 0.0, 1.0), psi + math.pi / 2)
        p = p + Qr @ Vector((lt, 0.0, 0.0))
        M = Matrix.Translation(p) @ Qr.to_matrix().to_4x4()
        N, off = body.clip_pose(clip, tc, dt=dt * ts)
        ph, Wh = body.hips(M, off, N)
        rec = {'f': f, 't': t, 'tc': tc, 'M': M, 'Qr': Qr, 'psi': psi, 'N': N, 'off': off, 'ph0': ph, 'feet': {}, 'zsup': zs,
               'helpers': dict(body.arms.helper_phi) if body.arms else {}}
        k = clip_k(tc)
        w_eff = width * (1.0 - smooth(NEED[0], NEED[1], float(an['ankle_sep'][k])))
        for s in SIDES:
            fk = body.leg_fk(s, ph, Wh, N)
            lat = Qr @ Vector((w_eff if s == 'left' else -w_eff, 0.0, 0.0))
            p_an = fk['p_an'] + lat
            P = body.sole(s, p_an, fk['W_ft'], fk['W_to'])
            rec['feet'][s] = {'p_an': p_an, 'W_ft': fk['W_ft'], 'W_to': fk['W_to'], 'W_sh': fk['W_sh'],
                              'zlow': float(P[:, 2].min()), 'P': P,
                              'stance': bool(an['side'][s]['stance'][k]), 'u': float(an['side'][s]['u'][k]),
                              'p': float(an['side'][s]['p'][k]),
                              'Ntoes': N[s + 'Toes'], 'dclip': (fk['p_an'] - fk['p_th']).length}
        A.append(rec)

    # ---- pass B: THE LOCK on the free walk. Through a stance the points of the sole in contact in this frame and the
    # last (the heel at the strike, the whole sole flat, the ball at the heel-off) must not slip and the foot must not
    # turn on the ground: frame by frame the free foot's slip of those points and its change of heading are taken back
    # (a correction: the ankle's offset delta and a turn theta about +Z through the ankle). A roll about the contact is no
    # slip, so it plays as the clip has it. Each stance's heading is set at its landing: the free foot's, turned on by
    # the root's turn from the landing to mid-stance (on a straight path, none). Through a swing the correction eases over
    # the first half to the next landing's (no offset, that heading)
    intervals = {}

    def rz(th, v):
        c, s_ = math.cos(th), math.sin(th)
        return Vector((c * v[0] - s_ * v[1], s_ * v[0] + c * v[1]))
    for s in SIDES:
        iv = _intervals([r['feet'][s]['stance'] for r in A])
        intervals[s] = iv
        th0 = {a: wrap_pi(A[(a + b) // 2]['psi'] - A[a]['psi']) for a, b in iv}
        delta, theta = Vector((0.0, 0.0)), 0.0
        lift = None
        for i, r in enumerate(A):
            fd = r['feet'][s]
            if fd['stance']:
                if i in th0:
                    delta, theta = Vector((0.0, 0.0)), th0[i]
                else:
                    fp = A[i - 1]['feet'][s]
                    z, zp = fd['P'][:, 2], fp['P'][:, 2]
                    both = (z - z.min()) + (zp - zp.min())
                    w = np.exp(-both / LOCK_BAND)
                    ci = Vector((fd['P'][:, :2] * w[:, None]).sum(0) / w.sum())
                    cp = Vector((fp['P'][:, :2] * w[:, None]).sum(0) / w.sum())
                    ai, ap = fd['p_an'].xy, fp['p_an'].xy
                    th_new = theta - wrap_pi(_yaw(fd['W_ft']) - _yaw(fp['W_ft']))
                    held = ap + delta + rz(theta, cp - ap)
                    delta = held - ai - rz(th_new, ci - ai)
                    theta = th_new
                lift = None
                fd['lock'] = True
            else:
                if lift is None:
                    nxt = min([a for a, b in iv if a > i], default=None)
                    span = max(1, int(0.5 * ((nxt if nxt is not None else len(A)) - i)))
                    lift = (i, delta.copy(), theta, th0[nxt] if nxt is not None else 0.0, span)
                b0, d0, t0, t1, span = lift
                u = ease((i - b0 + 1) / float(span))
                delta, theta = d0 * (1.0 - u), t0 + wrap_pi(t1 - t0) * u
                fd['lock'] = None
            fd['delta'], fd['theta'] = delta.copy(), theta

    # ---- pass C: each foot's target turn (heading lock, the ground's tilt in stance) and its xy
    def tilt_w(s, i):
        """1 through a stance, eased over ease_frames outside it"""
        best = 0.0
        for a, b in intervals[s]:
            if a <= i <= b:
                return 1.0
            dd = (a - i) if i < a else (i - b)
            best = max(best, 1.0 - dd / float(ease_frames + 1))
        return max(0.0, best)

    for s in SIDES:
        for i, r in enumerate(A):
            fd = r['feet'][s]
            xy = fd['p_an'].xy + fd['delta']
            W = Quaternion((0.0, 0.0, 1.0), fd['theta']) @ fd['W_ft']
            fd['xy'] = xy
            fd['wt'] = tilt_w(s, i)
            # FLAT ON THE GROUND: through its flat stance the clip's sole wobbles about a degree, which rocks a rigid sole
            # from heel to toe and back (no point stays down two frames running); within FLAT of flat a planted sole is
            # set flat (the heel strike keeps its pitch, less FLAT). Not into the heel-off (from 45 to 60 % of the
            # stance it fades out): there the ankle is near its dorsiflexion stop, and the clip's first degree or two of
            # heel rise, flattened back, pushed it past the stop
            up = W @ Vector((0.0, 0.0, 1.0))
            ang = up.angle(Vector((0.0, 0.0, 1.0)), 0.0)
            fl = fd['wt'] * (1.0 - smooth(0.45, 0.6, fd['p'])) if fd['lock'] is not None else fd['wt']
            if ang > 1e-7 and fl > 0.0:
                W = Quaternion(up.cross(Vector((0.0, 0.0, 1.0))).normalized(), min(ang, FLAT) * fl) @ W
            Wt = W @ fd['Ntoes']
            P = body.sole(s, Vector((xy.x, xy.y, 0.0)), W, Wt)
            nrm, _z = ground.plane(P[:, 0], P[:, 1])
            tilt = Vector((0.0, 0.0, 1.0)).rotation_difference(nrm)
            tq = Quaternion().slerp(tilt, fd['wt'])
            fd['W_t'] = tq @ W
            # THE ANKLE'S RANGE: seen from the clip's own shin at this phase (turned with the heading lock), the planned
            # turn is projected onto the ankle's cardan (its pitch and roll stops, coupled). On a rise under a late stance
            # the flat sole needs more dorsiflexion than the ankle has: planned inside the range, the heel lifts a little
            # early, as it must, and the heights below are set for that foot rather than the solve's clamp tipping it after
            if body.robot and fd['lock'] is not None:
                Wsh = Quaternion((0.0, 0.0, 1.0), fd['theta']) @ fd['W_sh']
                q3 = dof.project_joint(q_to_three(Wsh.inverted() @ fd['W_t']), dof.LEG_JOINTS[2], 1 if s == 'left' else -1)
                fd['W_t'] = Wsh @ q_from_three(q3)
            # THE TOES stay flat on the ground while the heel rises (the toe roll turns the foot about them): in a stance
            # with the sole pitched toe-down, the toes' pin is set so they lie on the ground's plane (the hinge's range
            # clamps it in the DOF pass). The clip's own toe bend misses that by a degree or two a frame, which slid them
            fwd = W @ FWD
            Nt = fd['Ntoes']
            if fd['lock'] is not None and fwd.z < 0.0:
                flat = tq @ Quaternion((0.0, 0.0, 1.0), math.atan2(fwd.y, fwd.x) - math.atan2(FWD.y, FWD.x))
                Nt = fd['W_t'].inverted() @ flat
            fd['Ntoes_t'] = Nt
            fd['W_toes_t'] = fd['W_t'] @ Nt
            fd['gnd'] = float(np.mean(_z))
            fd['P_plan'] = body.sole(s, Vector((xy.x, xy.y, 0.0)), fd['W_t'], fd['W_toes_t'])

    # ---- pass D: each ankle's height. In stance the lowest sole point on the ground. In swing the clip's lift over its
    # support (eased in from the ground near the stances) but never less than the clearance profile, over the highest of:
    # the ground under each sole point now and half a frame either way (the ground the sole sweeps between keys), and the
    # ground blended from the lift's to the landing's
    floor = an['floor']
    for s in SIDES:
        iv = intervals[s]
        for i, r in enumerate(A):
            fd = r['feet'][s]
            P = fd['P_plan']
            G = ground.h(P[:, 0], P[:, 1])
            if fd['lock'] is not None:
                fd['g_ref'], fd['lift'], fd['lift_min'] = fd['gnd'], 0.0, 0.0
                fd['z_an'] = float(np.max(G - P[:, 2]))
            else:
                prev = max([b for a, b in iv if b < i], default=None)
                nxt = min([a for a, b in iv if a > i], default=None)
                if prev is not None and nxt is not None:
                    u = ease((i - prev) / float(nxt - prev))
                    g_lerp = (1 - u) * A[prev]['feet'][s]['gnd'] + u * A[nxt]['feet'][s]['gnd']
                else:
                    g_lerp = A[prev]['feet'][s]['gnd'] if prev is not None else (A[nxt]['feet'][s]['gnd'] if nxt is not None else fd['gnd'])
                for nb in (i - 1, i + 1):
                    if 0 <= nb < len(A):
                        Q = 0.5 * (P[:, :2] + A[nb]['feet'][s]['P_plan'][:, :2])
                        G = np.maximum(G, ground.h(Q[:, 0], Q[:, 1]))
                G = np.maximum(G, g_lerp)
                fd['lift_min'] = clearance * _bump(fd['u'])
                fd['lift'] = max(max(0.0, fd['zlow'] - r['zsup']) * (1.0 - fd['wt']), fd['lift_min'])
                fd['g_ref'] = g_lerp
                fd['z_an'] = float(np.max(G - P[:, 2])) + fd['lift']
            fd['T'] = Vector((fd['xy'].x, fd['xy'].y, fd['z_an']))

    # ---- pass E: the root's height. Each leg has, in the clip, a hip-to-ankle length at this phase (its knee's bend);
    # for a planted leg the root goes where that leg has the clip's length to its target (so the stance knee is the
    # clip's, and the walk's bob is the clip's: the pelvis dips through the double support). Through a double support the
    # two legs' heights are shared by their load (each foot's stance, smoothed over LOAD_FRAMES either side: on a step up
    # the leading knee takes the step as it lands and straightens as the pelvis rises over it). Capped so every loaded
    # leg reaches its target. pelvis='lower' is the WebGPU controller's rule instead: the lower foot's ground less the
    # clip's support height (made for stairs; on bumps it crouches the leg on the higher foot)
    def leg_z(r, s, L):
        """the root's height at which leg s is L from its target"""
        fd = r['feet'][s]
        p_th = r['ph0'] + (r['Qr'] @ r['N']['hips']) @ body.leg[s]['hip']
        dxy = math.hypot(fd['T'].x - p_th.x, fd['T'].y - p_th.y)
        return fd['T'].z - p_th.z + (math.sqrt(L * L - dxy * dxy) if dxy < L else 0.0)
    if pelvis == 'lower':
        g = hann_smooth([min(r['feet']['left']['g_ref'], r['feet']['right']['g_ref']) for r in A], 2)
        z_nom = [gg - r['zsup'] for gg, r in zip(g, A)]
    else:
        load = {s: hann_smooth([1.0 if r['feet'][s]['lock'] is not None else 0.0 for r in A], LOAD_FRAMES) for s in SIDES}
        z_nom = []
        for i, r in enumerate(A):
            w = {s: max(load[s][i], 1e-6) for s in SIDES}
            z_nom.append(sum(w[s] * leg_z(r, s, r['feet'][s]['dclip']) for s in SIDES) / sum(w.values()))
    cap = []
    for i, r in enumerate(A):
        c = 1e9
        for s in SIDES:
            if r['feet'][s]['wt'] > 0.0:
                c = min(c, leg_z(r, s, body.leg[s]['reach'] - REACH_MARGIN))
        cap.append(c)
    # the hips come down to a cap at most 0.4 m/s ahead of it (a step off a kerb drops the body about 0.5 m/s; at a
    # walk's own 0.26 the crouch before a step down lasted six frames) and rise out of it at most 0.5 m/s (a push up onto
    # a step). The bob is already in z_nom, so the smoothing after is light
    down, up = 0.4 / fps, 0.5 / fps

    def shape(z_nom, hard):
        """the root's height: z_nom wherever it is under the hard limits (the reach caps, and the lowerings below), else
        the limits' slope-limited lower envelope H (at most the limit at every frame, its slopes bounded, so clipping to
        it leaves no notch); the kinks where the two meet rounded over a frame, under H"""
        n = len(hard)
        H = [min(hard[min(n - 1, max(0, i + k))] + (k * down if k > 0 else -k * up) for k in range(-10, 11))
             for i in range(n)]
        return [min(a, b) for a, b in zip(hann_smooth([min(a, b) for a, b in zip(z_nom, H)], 1), H)]
    hard = list(cap)
    zr = shape(z_nom, hard)

    # ---- pass F: the final solve per frame (solve), then the pelvis lowered wherever a planted foot is still short
    weights = dict(face or {})

    def solve(zr):
        """THE LOCK AGAIN, on the result: the joints' clamps (the ankle's cardan has no yaw and its pitch / roll stop; the
        hip's coupled table) and the ground's tilt turn the foot a little off its target, and that turn moves the contact
        points. So each frame is solved, and a planted foot measured against itself the frame before: its points in contact
        in BOTH frames (the persistent contact: a point that has just come down may still be moving, a point that was down
        must not) give its slip, its forward its turn on the ground; the target is moved back by the slip and turned back
        about the contact by the turn, and re-solved (LOCK_ROUNDS). The lowest sole point is set on the ground the same way
        (a clamped tilt then rests on its lowest corner: the hardware's limit, not a sink). A swing foot under its clearance
        profile is lifted to it. The running corrections carry to the next frame and ease out after the lift"""
        head = dof.HeadState()
        crown = dof.Crown()
        if body.robot and preroll > 0:
            # the face's state settled before the first frame (the head's and the crown's actuators start where it is)
            p3 = {n_: q_to_three(q) for n_, q in A[0]['N'].items()}
            for _k in range(int(preroll * fps)):
                q3 = dict(p3)
                head.apply(q3, weights, dt, state=head_state)
                crown.apply(weights, dof.head_roll_deg(q3), dt, state=crown_state)
        frames = []
        run = {s: Vector((0.0, 0.0)) for s in SIDES}
        run_yaw = {s: 0.0 for s in SIDES}
        prev = {s: None for s in SIDES}
        lift = {s: None for s in SIDES}
        guard = {s: [] for s in SIDES}
        for i, r in enumerate(A):
            frames.append(_solve_frame(i, r, zr[i], run, run_yaw, prev, lift, guard, head, crown))
        return frames, guard

    def _solve_frame(i, r, z, run, run_yaw, prev, lift, guard, head, crown):
        M = Matrix.Translation(Vector((0.0, 0.0, z))) @ r['M']
        N = dict(r['N'])
        for s in SIDES:
            N[s + 'Toes'] = r['feet'][s]['Ntoes_t']
        ph, Wh = body.hips(M, r['off'], N)
        T, Wt, st_now, yaw_acc, lifted = {}, {}, {}, {}, {}
        for s in SIDES:
            fd = r['feet'][s]
            st_now[s] = fd['lock'] is not None
            if not st_now[s]:
                if lift[s] is None:
                    nxt = min([a for a, b in intervals[s] if a > i], default=len(A))
                    lift[s] = (i, run[s].copy(), run_yaw[s], max(1, int(0.5 * (nxt - i))))
                b0, r0, y0, span = lift[s]
                k = 1.0 - ease((i - b0 + 1) / float(span))
                run[s], run_yaw[s] = r0 * k, y0 * k
            else:
                lift[s] = None
            T[s] = fd['T'] + Vector((run[s].x, run[s].y, 0.0))
            Wt[s] = Quaternion((0.0, 0.0, 1.0), run_yaw[s]) @ fd['W_t']
            yaw_acc[s], lifted[s] = run_yaw[s], 0.0
        for _it in range(LOCK_ROUNDS + 1):
            for s in SIDES:
                body.solve_leg(s, ph, Wh, N, T[s], Wt[s], swivel=r['feet'][s]['wt'])
            stages = body.project_legs(N, stages=True)
            if _it == LOCK_ROUNDS:
                break
            for s in SIDES:
                fd = r['feet'][s]
                fk = body.leg_fk(s, ph, Wh, N)
                P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
                gap = P[:, 2] - ground.h(P[:, 0], P[:, 1])
                pv = prev[s]
                if st_now[s] and pv is not None and pv['stance']:
                    # TWO-POINT SUPPORT: a rigid sole on curved ground rolls its contact from one end to the other (the
                    # heel rocker lands the forefoot on a rise and lifts the heel). When the points down last frame have
                    # lifted while another point is now the lowest, the foot turns about that point until the old contact
                    # is down again: it rests on both, as a rigid foot would (in the early rounds: the last ones settle
                    # the slip and the height on what it turned)
                    old = pv['gaps'] < 0.0005
                    k1 = int(np.argmin(gap))
                    if _it < LOCK_ROUNDS - 3 and old.any() and not old[k1] and float(gap[old].min() - gap[k1]) > 0.0003:
                        co = P[old].mean(0)
                        v = Vector((co[0] - P[k1][0], co[1] - P[k1][1], 0.0))
                        if v.length > 0.02:
                            R = Quaternion(Vector((0.0, 0.0, 1.0)).cross(v).normalized(),
                                           math.atan2(float(gap[old].min() - gap[k1]), v.length))
                            pk = Vector(P[k1])
                            Wt[s] = R @ Wt[s]
                            T[s] = pk + R @ (T[s] - pk)
                    both = gap + pv['gaps']
                    w = np.exp(-(both - both.min()) / LOCK_BAND)
                    c_now = (P[:, :2] * w[:, None]).sum(0) / w.sum()
                    d = ((P[:, :2] - pv['P'][:, :2]) * w[:, None]).sum(0) / w.sum()
                    T[s] = T[s] - Vector((d[0], d[1], 0.0))
                    dy = wrap_pi(_yaw(fk['W_ft']) - pv['yaw'])
                    dy = clamp(dy, yaw_acc[s] - YAW_CAP, yaw_acc[s] + YAW_CAP)
                    if abs(dy) > 1e-9:
                        R = Quaternion((0.0, 0.0, 1.0), -dy)
                        Wt[s] = R @ Wt[s]
                        a_ = R @ Vector((T[s].x - c_now[0], T[s].y - c_now[1], 0.0))
                        T[s].x, T[s].y = c_now[0] + a_.x, c_now[1] + a_.y
                        yaw_acc[s] -= dy
                if st_now[s]:
                    T[s].z -= float(gap.min()) * fd['wt']
                elif gap.min() < fd['lift_min'] - 0.001:
                    dz = fd['lift_min'] - 0.001 - float(gap.min())
                    T[s].z += dz
                    lifted[s] += dz
        for s in SIDES:
            if st_now[s]:
                run[s] = Vector((T[s].x - r['feet'][s]['T'].x, T[s].y - r['feet'][s]['T'].y))
                run_yaw[s] = yaw_acc[s]
            if lifted[s] > 0:
                guard[s].append([r['f'], round(lifted[s] * 1000, 2)])
        p3 = {n_: q_to_three(q) for n_, q in N.items()}
        petals = None
        if body.robot:
            head.apply(p3, weights, dt, state=head_state)
            petals = crown.apply(weights, dof.head_roll_deg(p3), dt, state=crown_state)
        N = {n_: q_from_three(q) for n_, q in p3.items()}
        meas = {}
        for s in SIDES:
            fk = body.leg_fk(s, ph, Wh, N)
            P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            gap = P[:, 2] - ground.h(P[:, 0], P[:, 1])
            meas[s] = {'gap': float(gap.min()), 'P': P, 'gaps': gap, 'ankle_err': (fk['p_an'] - T[s]).length,
                       'ankle_err_xy': (fk['p_an'] - T[s]).xy.length,
                       'stance': st_now[s], 'yaw': _yaw(fk['W_ft']), 'lift_min': r['feet'][s]['lift_min']}
            prev[s] = meas[s]
        return {'f': r['f'], 'M': M, 'N': N, 'off': r['off'], 'stages': stages, 'helpers': r['helpers'],
                'petals': petals, 'meas': meas, 'psi': r['psi'], 'tc': r['tc']}

    frames, guard = solve(zr)
    # where a planted leg is straight and still short (its foot floats, or the ankle misses the lock's target: the push-off
    # leg reaching back for its toe; a hip lowered 1 mm reaches about 2 mm further back), the hips come down by the
    # shortfall (at most 3 cm a round), spread like the cap, and the walk is solved again
    lowered = []
    for _round in range(PELVIS_ROUNDS):
        short = []
        for fr in frames:
            d = 0.0
            for s in SIDES:
                m = fr['meas'][s]
                if m['stance'] and fr['N'][s + 'LowerLeg'].to_axis_angle()[1] < 3.0 * D2R:
                    d = max(d, m['gap'], 0.5 * m['ankle_err_xy'])
            short.append(min(d, 0.03))
        if max(short) < 0.0005:
            break
        lowered.append([F[int(np.argmax(short))], round(1000 * max(short), 2), sum(1 for d in short if d >= 0.0005)])
        hard = [min(hh, z - d - 0.001) if d >= 0.0005 else hh for hh, z, d in zip(hard, zr, short)]
        zr = shape(z_nom, hard)
        frames, guard = solve(zr)

    rep = _report(body, clip, an, frames, intervals, F, fps, zr, clearance)
    rep['pelvis_lowered_mm'] = lowered
    rep.update({'v_native': v_native, 'v_clip': v_clip, 'stride_m': an['stride'], 'speed': speed, 'time_scale': ts,
                'floor_m': floor, 'path_m': total,
                'clip_stance_fraction': an['stance_fraction'], 'clip_double_support': an['double_support'],
                'swing_guard': {s: guard[s] for s in SIDES}})
    if key:
        rep['action'] = key_frames(h, body, frames, action_name or f'{h.name}|walk_path')
    rep['_frames'] = frames
    rep['_root'] = {'z': zr, 'z_nom': z_nom, 'cap': cap, 'tc': [r['tc'] for r in A]}
    return rep


def _report(body, clip, an, frames, intervals, F, fps, zr, clearance):
    """the walk measured on its result (see the module's doc)"""
    rep = {'frames': [F[0], F[-1]], 'stances': {}, 'swings': {}}
    for s in SIDES:
        rows = []
        for a, b in intervals[s]:
            slips, cents, yaws, rocks = [], [], [], []
            for i in range(a + 1, b + 1):
                m1, m0 = frames[i]['meas'][s], frames[i - 1]['meas'][s]
                c = (m1['gaps'] < CONTACT) & (m0['gaps'] < CONTACT)
                if not c.any():
                    # no point stayed down: the sole rocked from one end to the other. How far the old contact rose,
                    # and the slip of the point nearest the ground through both frames
                    k = int(np.argmin(m1['gaps'] + m0['gaps']))
                    rocks.append([F[i], round(1000 * float(m1['gaps'][m0['gaps'] < CONTACT].min(initial=1.0)), 2)])
                    c = np.zeros(len(m1['gaps']), dtype=bool)
                    c[k] = True
                # slip is motion ALONG the ground: a point within the contact band moving up or down is the sole
                # rolling on or off its contact, not sliding
                mv = np.linalg.norm(m1['P'][c, :2] - m0['P'][c, :2], axis=1)
                slips.append(float(mv.min()))
                cents.append(float(np.linalg.norm((m1['P'][c, :2] - m0['P'][c, :2]).mean(0))))
                yaws.append(abs(wrap_pi(m1['yaw'] - m0['yaw'])) * R2D)
            gaps = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)]
            rows.append({'frames': [F[a], F[b]], 'slip_mm_per_frame_max': round(1000 * max(slips, default=0.0), 2),
                         'centroid_mm_per_frame_max': round(1000 * max(cents, default=0.0), 2),
                         'drift_mm': round(1000 * sum(slips), 2),
                         'yaw_deg_per_frame_max': round(max(yaws, default=0.0), 3),
                         'gap_mm': [round(min(gaps) * 1000, 2), round(max(gaps) * 1000, 2)], 'rocks': rocks})
        rep['stances'][s] = rows
        sw = []
        for a, b in _intervals([not fr['meas'][s]['stance'] for fr in frames]):
            gaps = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)]
            mid = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)
                   if clearance > 0 and frames[i]['meas'][s]['lift_min'] >= 0.5 * clearance]
            # a drag: the swinging sole on the ground mid-swing, or anywhere in the swing moving faster than a toe leaving
            # the ground at the lift (0.5 m/s) or a heel arriving at the strike does (the verifier's drags: 4.7-5.3 m/s)
            touch = []
            for i in range(max(a, 1), b + 1):
                m1, m0 = frames[i]['meas'][s], frames[i - 1]['meas'][s]
                if m1['gap'] < CONTACT:
                    k = int(np.argmin(m1['gaps']))
                    v = float(np.linalg.norm(m1['P'][k] - m0['P'][k])) * fps
                    if v > 1.0 or (clearance > 0 and m1['lift_min'] >= 0.5 * clearance):
                        touch.append([F[i], round(v, 2)])
            sw.append({'frames': [F[a], F[b]], 'clearance_mm': round(min(gaps) * 1000, 2),
                       'mid_clearance_mm': round(min(mid) * 1000, 2) if mid else None, 'touch_frames': touch})
        rep['swings'][s] = sw
    down = [{s: fr['meas'][s]['gap'] < CONTACT for s in SIDES} for fr in frames]
    rep['double_support'] = [F[i] for i, d in enumerate(down) if all(d.values())]
    rep['airborne'] = [F[i] for i, d in enumerate(down) if not any(d.values())]
    allrows = [row for s in SIDES for row in rep['stances'][s]]
    allsw = [row for s in SIDES for row in rep['swings'][s]]
    rep['worst'] = {'slip_mm_per_frame_max': max((r_['slip_mm_per_frame_max'] for r_ in allrows), default=0.0),
                    'centroid_mm_per_frame_max': max((r_['centroid_mm_per_frame_max'] for r_ in allrows), default=0.0),
                    'drift_mm': max((r_['drift_mm'] for r_ in allrows), default=0.0),
                    'yaw_deg_per_frame_max': max((r_['yaw_deg_per_frame_max'] for r_ in allrows), default=0.0),
                    'gap_min_mm': min((r_['gap_mm'][0] for r_ in allrows), default=0.0),
                    'gap_max_mm': max((r_['gap_mm'][1] for r_ in allrows), default=0.0),
                    'ankle_err_mm': round(1000 * max(fr['meas'][s]['ankle_err'] for fr in frames for s in SIDES), 2),
                    'swing_clearance_min_mm': min((r_['clearance_mm'] for r_ in allsw), default=None),
                    'swing_mid_clearance_min_mm': min((r_['mid_clearance_mm'] for r_ in allsw if r_['mid_clearance_mm'] is not None),
                                                      default=None),
                    'swing_touch_frames': sum(len(r_['touch_frames']) for r_ in allsw),
                    'rocks': sum(len(r_['rocks']) for r_ in allrows),
                    'rock_mm_max': max((x[1] for r_ in allrows for x in r_['rocks']), default=0.0)}
    rep['swing_gap_min_mm'] = rep['worst']['swing_clearance_min_mm']
    # the gait's shape against the clip's over the same phases: the knee of a foot on the ground (the pin angle)
    kn = []
    for fr in frames:
        for s in SIDES:
            if fr['meas'][s]['stance']:
                kn.append(fr['N'][s + 'LowerLeg'].to_axis_angle()[1] * R2D)
    clip_kn = []
    for s in SIDES:
        d = an['side'][s]
        for k in range(an['n']):
            if d['stance'][k]:
                N_, _o = body.clip_pose(clip, k * an['dtc'])
                clip_kn.append(N_[s + 'LowerLeg'].to_axis_angle()[1] * R2D)
    # and frame by frame against the clip's own knee at the same phase (on uneven ground a step up or down is taken in
    # the knees: the leading knee as it lands on a rise, the stance knee as the hips come down ahead of a drop)
    exc = []
    for fr in frames:
        N_, _o = body.clip_pose(clip, fr['tc'])
        for s in SIDES:
            if fr['meas'][s]['stance']:
                exc.append((fr['N'][s + 'LowerLeg'].to_axis_angle()[1] - N_[s + 'LowerLeg'].to_axis_angle()[1]) * R2D)
    psi = np.unwrap([fr['psi'] for fr in frames])
    rep['gait'] = {'planted_knee_deg': [round(min(kn), 1), round(float(np.median(kn)), 1), round(max(kn), 1)] if kn else None,
                   'clip_planted_knee_deg': [round(min(clip_kn), 1), round(float(np.median(clip_kn)), 1),
                                             round(max(clip_kn), 1)] if clip_kn else None,
                   'planted_knee_minus_clip_deg': [round(float(np.median(exc)), 1), round(float(np.percentile(exc, 90)), 1),
                                                   round(max(exc), 1)] if exc else None,
                   'planted_knee_over_clip_by_15deg_frames': sum(1 for x in exc if x > 15.0),
                   'root_z_m': [round(min(zr), 4), round(max(zr), 4)],
                   'root_turn_deg_per_frame_max': round(float(np.max(np.abs(np.diff(psi)))) * R2D, 2) if len(psi) > 1 else 0.0}
    return rep


def key_frames(h, body, frames, name):
    """one action: the armature object's location / rotation and every pose bone the pass set (LINEAR, every frame)"""
    from bpy_extras import anim_utils
    arm = h.arm
    ad = arm.animation_data or arm.animation_data_create()
    act = bpy.data.actions.new(name)
    slot = act.slots.new(id_type='OBJECT', name=arm.name)
    ad.action = act
    ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    arm.rotation_mode = 'QUATERNION'
    series = {}

    def put(path, idx, f, v, group):
        series.setdefault((path, idx, group), []).append((f, v))
    hb = h.humanoid['hips']
    for fr in frames:
        f = fr['f']
        loc, rot, _sc = fr['M'].decompose()
        for i in range(3):
            put('location', i, f, loc[i], 'Object Transforms')
        for i in range(4):
            put('rotation_quaternion', i, f, rot[i], 'Object Transforms')
        for n, q in fr['N'].items():
            b = h.humanoid[n]
            bq = h.basis_from_normalized(b, q)
            for i in range(4):
                put(f'pose.bones["{b}"].rotation_quaternion', i, f, bq[i], b)
        lb = h.rest_q[hb].inverted() @ fr['off']
        for i in range(3):
            put(f'pose.bones["{hb}"].location', i, f, lb[i], hb)
        for side, st in (fr['stages'] or {}).items():
            for k, bn in (('pitch', side + 'HipPitch'), ('swing', side + 'HipSwing')):
                if k in st and bn in arm.pose.bones:
                    bq = h.basis_from_normalized(bn, st[k])
                    for i in range(4):
                        put(f'pose.bones["{bn}"].rotation_quaternion', i, f, bq[i], bn)
        for side, phi in (fr['helpers'] or {}).items():
            bn = side + 'ShoulderPitch'
            if bn in arm.pose.bones:
                bq = h.basis_from_normalized(bn, Quaternion((1.0, 0.0, 0.0), phi))
                for i in range(4):
                    put(f'pose.bones["{bn}"].rotation_quaternion', i, f, bq[i], bn)
        if fr['petals'] is not None:
            for i_, phi in enumerate(fr['petals']):
                bn = f'petal_{i_:02d}'
                if bn in arm.pose.bones:
                    bq = Quaternion((1.0, 0.0, 0.0), (phi - dof.PETAL_REST) * D2R)
                    for i in range(4):
                        put(f'pose.bones["{bn}"].rotation_quaternion', i, f, bq[i], bn)
    for (path, idx, group), kv in series.items():
        fc = cb.fcurves.new(path, index=idx, group_name=group)
        fc.keyframe_points.add(len(kv))
        flat = [c for f, v in kv for c in (f, v)]
        fc.keyframe_points.foreach_set('co', flat)
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()
    for p in arm.pose.bones:
        p.rotation_mode = 'QUATERNION'
    return {'name': act.name, 'fcurves': len(series), 'frames': len(frames)}
