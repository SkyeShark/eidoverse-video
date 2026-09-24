"""build_vrma.py — the claudesona's hand-authored performance clips (VRM Animation, .vrma), made for the DAISY
(DAY'S EYE) music video. Any VRM 1.0 humanoid plays them (three-vrm retargets normalized bone rotations).
Guide: AGENTS.md ("Performance clips").

Run it ONLY through the repository's isolated runner (a bare `blender --factory-startup` run against your real
Blender config deletes your installed extension packages; see docs/blender.md):

    bash run_blender.sh eidoverse/assets/animations/performance_src/build_vrma.py [--clips a,b] [--save-blend] [--report]

It imports eidoverse/assets/vrms/claude_suit_wardrobe.vrm (digi's claudesona, VRM 1.0, a 2.00 m rig), evaluates every clip
in CLIPS below at 64 fps, bakes the result into one Blender action per clip, and exports each with the VRM add-on's
`bpy.ops.export_scene.vrma` to eidoverse/assets/animations/<name>.vrma, plus clips.json next to this script.

WHY 64 fps: at 128 BPM one beat is 0.46875 s = exactly 30 frames at 64 fps, so every loop ends exactly on a beat
boundary (its last sample equals its first) and every key time in beats lands on a whole frame.

CONVENTIONS (read before adding a clip)
  * Space = three-vrm's NORMALIZED humanoid frame, the same one `vrm.humanoid.getNormalizedBoneNode(...)` uses:
    x = HER left, y = up, z = forward (toward the audience / a camera at +z). Metres of the 2.00 m rig
    (the film shows it at scale 0.87). Angles in degrees. Time in BEATS (128 BPM).
  * A bone's rotation N is its rotation relative to its parent, measured against the rest T-pose with
    world-aligned axes. Converting to Blender is exact: q_basis = Rrest^-1 · N · Rrest (see `basis`).
  * Euler triples (hips/spine/chest/neck/head) = (x, y, z) applied as turn(y), then nod(x), then tilt(z):
    +x nods / bends forward, +y turns toward her left, +z tilts the top toward her right shoulder.
  * Shoulders (clavicles) = (elevate, protract) degrees, same meaning on both sides.
  * Arms are IK: 'palm' = where the palm surface should be (a point in the REST frame of the torso: the chest
    carries it when the spine bends), 'normal' = the way the palm faces, 'fingers' = the way the fingers point,
    'pole' = the way the ELBOW points. Absolute coordinates on both sides (x = her left). 'hand' = a HANDS shape.
  * Feet are planted by leg IK every frame; every clip shares the STAND stance, so crossfades between any two
    clips never slide the feet. 'hips' = {'pos': offset from rest, 'rot': euler}.
  * Keys are (beat, pose-overrides[, options]). Overrides merge one level deep onto the clip's base pose.
    Interpolation is an auto-clamped cubic Hermite in rotation-vector space (relative to STAND) — flat at
    extremes, flowing through breakdowns. Loops are periodic (the key at beat 0 is also the key at `beats`).
    One-shots start and end with zero velocity.
  * `lag` delays chains (in beats) for overlap/follow-through: the hand trails the forearm, the head trails
    the chest. `layers` add procedural motion (breathing, sway) that is periodic in the loop length.

Everything is deterministic: same script, same bytes.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
VRM = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe.vrm')
OUT = os.path.join(REPO, 'eidoverse', 'assets', 'animations')
BPM = 128.0
BEAT = 60.0 / BPM
FPS = 64            # 30 frames per beat
REPORT = []


# ============================================================================ math (normalized frame)
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def V(*a):
    return Vector(a[0] if len(a) == 1 else a)


def qaxis(axis, deg):
    return Quaternion(V(axis).normalized(), math.radians(deg))


def euler(e):
    """(x, y, z) degrees -> turn(y) · nod(x) · tilt(z)."""
    x, y, z = (tuple(e) + (0, 0, 0))[:3]
    return qaxis(Y, y) @ qaxis(X, x) @ qaxis(Z, z)


def frame(a, b):
    """Orthonormal frame, columns (a, b', a x b') with b' = b made perpendicular to a."""
    a = V(a).normalized()
    b = V(b) - a * a.dot(V(b))
    b.normalize()
    return Matrix((a, b, a.cross(b))).transposed()


def rot_frames(a0, b0, a1, b1):
    """The rotation taking direction a0 -> a1 while taking b0 -> b1 (as nearly as orthogonality allows)."""
    return (frame(a1, b1) @ frame(a0, b0).transposed()).to_quaternion()


def swing_twist(q, axis):
    """q = swing @ twist, twist about `axis`. Returns (swing, twist_deg)."""
    axis = V(axis).normalized()
    v = Vector((q.x, q.y, q.z))
    p = axis * v.dot(axis)
    tw = Quaternion((q.w, p.x, p.y, p.z))
    if tw.magnitude < 1e-9:
        return q.copy(), 0.0
    tw.normalize()
    ang = 2 * math.degrees(math.atan2(Vector((tw.x, tw.y, tw.z)).dot(axis), tw.w))
    if ang > 180:
        ang -= 360
    if ang < -180:
        ang += 360
    return q @ tw.inverted(), ang


def signed_angle(a, b, axis):
    return math.degrees(math.atan2(a.cross(b).dot(V(axis).normalized()), a.dot(b)))


def qlog(q):
    q = q.normalized()
    if q.w < 0:
        q = Quaternion((-q.w, -q.x, -q.y, -q.z))
    return Vector(q.to_exponential_map())


def qexp(v):
    return Quaternion(Vector(v))


def mirror_q(q):
    return Quaternion((q.w, q.x, -q.y, -q.z))


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ============================================================================ rig
class Rig:
    """Rest data of the imported claudesona, in the normalized frame."""

    def __init__(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
        bpy.ops.import_scene.vrm(filepath=VRM)
        self.arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        ext = self.arm.data.vrm_addon_extension.vrm1
        # the exporter's rest reference = the armature rest pose (digi's T-pose), the same pose three-vrm normalizes
        ext.humanoid.pose = 'restPositionPose'
        self.hb = {}
        for name, h in ext.humanoid.human_bones.human_bone_name_to_human_bone().items():
            bn = h.node.bone_name
            if bn and bn in self.arm.data.bones:
                self.hb[name.value] = bn
        self.human = {v: k for k, v in self.hb.items()}
        self.head, self.rr, self.parent = {}, {}, {}
        for h, bn in self.hb.items():
            b = self.arm.data.bones[bn]
            self.head[h] = Vector((b.head_local.x, b.head_local.z, -b.head_local.y))
            self.rr[h] = b.matrix_local.to_quaternion()
            p = b.parent
            while p is not None and p.name not in self.human:
                p = p.parent
            self.parent[h] = self.human[p.name] if p is not None else None
        self.order = []                                   # parents before children
        seen = set()
        while len(self.order) < len(self.hb):
            for h in self.hb:
                if h not in seen and (self.parent[h] is None or self.parent[h] in seen):
                    self.order.append(h)
                    seen.add(h)
        self.bones = [h for h in self.order if not h.endswith('Eye')]
        # limb chains
        self.chain = {}
        for s, side in (('L', 'left'), ('R', 'right')):
            a, e, w = self.head[f'{side}UpperArm'], self.head[f'{side}LowerArm'], self.head[f'{side}Hand']
            u1, u2 = (e - a).normalized(), (w - e).normalized()
            h = u1.cross(Z).normalized()                 # elbow flexion swings the forearm toward +z
            mid = self.head[f'{side}MiddleProximal']
            fing = (mid - w).normalized()
            palm_n = V(0, -1, 0)                          # T-pose palms face down
            off = (mid - w) * 0.55 + palm_n * 0.016       # palm-surface point, from the wrist
            self.chain['arm' + s] = dict(root=a, L1=(e - a).length, L2=(w - e).length, u1=u1, u2=u2, h=h,
                                         fing=fing, palm=palm_n, off=off, side=side)
            a, k, f = self.head[f'{side}UpperLeg'], self.head[f'{side}LowerLeg'], self.head[f'{side}Foot']
            u1, u2 = (k - a).normalized(), (f - k).normalized()
            h = u1.cross(-Z).normalized()                 # knee flexion swings the shin toward -z
            self.chain['leg' + s] = dict(root=a, L1=(k - a).length, L2=(f - k).length, u1=u1, u2=u2, h=h, side=side)

    def basis(self, h, n):
        """Normalized-frame rotation N of humanoid bone h -> Blender pose-bone rotation_quaternion."""
        nb = Quaternion((n.w, n.x, -n.z, n.y))           # three axes (x, y, z) -> Blender (x, -z, y)
        r = self.rr[h]
        return r.inverted() @ nb @ r

    def hips_location(self, pos):
        """Absolute hips joint position (normalized frame) -> Blender pose-bone location."""
        b = self.arm.data.bones[self.hb['hips']]
        want = Vector((pos.x, -pos.z, pos.y))
        return self.rr['hips'].inverted() @ (want - b.head_local)


# ============================================================================ IK
def two_bone(A, T, c, pole):
    """World deltas for a 2-bone chain rooted at A reaching T. Returns (D1, N2_hinge, flexion_deg, reach)."""
    L1, L2 = c['L1'], c['L2']
    d = T - A
    dist = d.length
    reach = dist / (L1 + L2)
    dc = min(max(dist, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.99995)
    dh = d / dist
    ca = (L1 * L1 + dc * dc - L2 * L2) / (2 * L1 * dc)
    a = math.acos(max(-1.0, min(1.0, ca)))
    pp = V(pole) - dh * V(pole).dot(dh)
    pp.normalize()
    B = A + (dh * math.cos(a) + pp * math.sin(a)) * L1
    w1 = (B - A).normalized()
    w2 = (A + dh * dc - B).normalized()
    n = w1.cross(w2)
    n = n.normalized() if n.length > 1e-6 else pp.cross(dh).normalized()
    D1 = rot_frames(c['u1'], c['h'], w1, n)
    th = signed_angle(w1, w2, n)
    th0 = signed_angle(c['u1'], c['u2'], c['h'])
    return D1, qaxis(c['h'], th - th0), th, reach


def solve_arm(rig, key, spec, n_shoulder, diag):
    """IK in the torso's rest frame (the chest carries the result). Returns {bone: N}."""
    c = rig.chain[key]
    side = c['side']
    sh = rig.head[f'{side}Shoulder']
    A = sh + n_shoulder @ (c['root'] - sh)
    Dh = rot_frames(c['fing'], c['palm'], V(spec['fingers']).normalized(), V(spec['normal']).normalized())
    W = V(spec['palm']) - Dh @ c['off']
    D1, H2, flex, reach = two_bone(A, W, c, V(spec['pole']))
    # twist split: the forearm takes the twist about its own axis (pronation/supination), the wrist the swing
    D2a = D1 @ H2
    wrist0 = D2a.inverted() @ Dh
    _, tw = swing_twist(wrist0, c['u2'])
    tw_f = max(-110.0, min(110.0, tw * spec.get('twist_share', 0.85)))
    N2 = H2 @ qaxis(c['u2'], tw_f)
    D2 = D1 @ N2
    Nh = D2.inverted() @ Dh
    sw, tw_w = swing_twist(Nh, c['u2'])
    wrist = math.degrees(sw.angle) if sw.angle <= math.pi else 360 - math.degrees(sw.angle)
    diag.append(f"{key}: elbow {flex:5.1f}  forearm-twist {tw_f:6.1f}  wrist-swing {wrist:5.1f}  wrist-twist {tw_w:6.1f}  reach {reach:.2f}")
    if flex < 2 or flex > 150 or wrist > 65 or abs(tw_w) > 35 or reach > 1.0:
        diag.append(f"   ^^^ {key} out of comfortable range")
    return {f'{side}UpperArm': n_shoulder.inverted() @ D1, f'{side}LowerArm': N2, f'{side}Hand': Nh}


def solve_leg(rig, key, hips_pos, d_hips, foot):
    c = rig.chain[key]
    side = c['side']
    ank0, toe0 = rig.head[f'{side}Foot'], rig.head[f'{side}Toes']
    qy = qaxis(Y, foot.get('yaw', 0.0))
    lift = foot.get('lift', 0.0)
    fx, fz = foot['pos']
    ank_flat = Vector((fx, ank0.y, fz))
    ball = ank_flat + qy @ (toe0 - ank0)
    d_foot = qy @ qaxis(X, lift)
    T = ball + d_foot @ (ank0 - toe0)
    A = hips_pos + d_hips @ (c['root'] - rig.head['hips'])
    knee_dir = qaxis(Y, 0.5 * (foot.get('yaw', 0.0) + math.degrees(2 * math.atan2(d_hips.y, d_hips.w)))) @ Z
    D1, H2, flex, reach = two_bone(A, T, c, knee_dir)
    D2 = D1 @ H2
    return ({f'{side}UpperLeg': d_hips.inverted() @ D1, f'{side}LowerLeg': H2,
             f'{side}Foot': D2.inverted() @ d_foot, f'{side}Toes': qaxis(X, -lift)}, reach, flex)


# ============================================================================ hands
FINGERS = ('Index', 'Middle', 'Ring', 'Little')
# per finger (proximal, intermediate, distal) curl, then spread (deg);
# thumb = (close, flex, mcp, ip): close lays the thumb along the index (digi's rest thumb points into the palm),
# flex swings it into the palm at the base, mcp/ip curl its two joints.
HANDS = {
    'relaxed': dict(Index=(10, 16, 8), Middle=(14, 22, 10), Ring=(18, 26, 12), Little=(22, 28, 14), spread=3, thumb=(44, -2, 8, 12)),
    'soft':    dict(Index=(5, 8, 4), Middle=(8, 12, 6), Ring=(12, 16, 8), Little=(16, 20, 10), spread=7, thumb=(38, -6, 6, 8)),
    'open':    dict(Index=(2, 4, 2), Middle=(3, 5, 2), Ring=(5, 7, 3), Little=(7, 9, 4), spread=11, thumb=(28, -8, 2, 4)),
    'flat':    dict(Index=(3, 4, 2), Middle=(4, 5, 2), Ring=(5, 6, 3), Little=(6, 7, 3), spread=5, thumb=(44, -2, 4, 6)),
    'grip':    dict(Index=(38, 48, 28), Middle=(44, 54, 30), Ring=(50, 56, 30), Little=(54, 56, 30), spread=0, thumb=(30, 18, 18, 16)),
    'clasp':   dict(Index=(30, 38, 22), Middle=(36, 42, 24), Ring=(40, 46, 24), Little=(44, 48, 24), spread=0, thumb=(40, 8, 14, 12)),
    'wave':    dict(Index=(2, 3, 2), Middle=(2, 3, 2), Ring=(3, 5, 2), Little=(5, 7, 3), spread=5, thumb=(40, -6, 4, 6)),
    'hold':    dict(Index=(22, 30, 18), Middle=(26, 34, 18), Ring=(30, 36, 18), Little=(34, 38, 20), spread=0, thumb=(30, 12, 12, 10)),
    'float':   dict(Index=(7, 12, 6), Middle=(10, 16, 8), Ring=(14, 20, 10), Little=(18, 24, 12), spread=4, thumb=(40, -4, 6, 8)),
}
SPREAD_W = dict(Index=-1.0, Middle=-0.2, Ring=0.5, Little=1.0)


def hand_rots(rig, side, shape):
    """Finger rotations for one hand (defined on the left, mirrored for the right)."""
    s = HANDS[shape] if isinstance(shape, str) else shape
    out = {}
    for f in FINGERS:
        c1, c2, c3 = s[f]
        sp = s.get('spread', 0.0) * SPREAD_W[f]
        segs = (('Proximal', qaxis(Y, sp) @ qaxis(-Z, c1)), ('Intermediate', qaxis(-Z, c2)), ('Distal', qaxis(-Z, c3)))
        for seg, q in segs:
            out[f'left{f}{seg}'] = q
    t0, t2 = rig.head['leftThumbMetacarpal'], rig.head['leftThumbDistal']
    tdir = (t2 - t0).normalized()
    fing = rig.chain['armL']['fing']
    cax = tdir.cross(fing).normalized()               # + closes the thumb toward the index finger
    fax = tdir.cross(V(0, -1, 0)).normalized()        # + curls it into the palm
    close, flex, mcp, ip = s['thumb']
    out['leftThumbMetacarpal'] = qaxis(cax, close) @ qaxis(fax, flex)
    out['leftThumbProximal'] = qaxis(fax, mcp)
    out['leftThumbDistal'] = qaxis(fax, ip)
    if side == 'right':
        out = {k.replace('left', 'right'): mirror_q(q) for k, q in out.items()}
    return out


# ============================================================================ poses
AXIAL = ('spine', 'chest', 'neck', 'head')

STAND = {
    'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2.0)},
    'spine': (0, -1, 1.2), 'chest': (-2, -1.5, 1.3), 'neck': (3, 0, 0), 'head': (-3, 1, -1.5),
    'shoulderL': (-2, 3), 'shoulderR': (-2, 3),
    'armL': {'palm': (0.236, 0.690, 0.082), 'normal': (-0.84, 0.05, -0.48), 'fingers': (0.07, -1, 0.16),
             'pole': (0.35, 0, -1), 'hand': 'relaxed'},
    'armR': {'palm': (-0.234, 0.694, 0.076), 'normal': (0.84, 0.05, -0.50), 'fingers': (-0.07, -1, 0.14),
             'pole': (-0.35, 0, -1), 'hand': 'relaxed'},
    'feet': {'L': {'pos': (0.118, -0.022), 'yaw': 8.0}, 'R': {'pos': (-0.112, -0.046), 'yaw': -6.0}},
}


def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            m = dict(out[k])
            for kk, vv in v.items():
                m[kk] = (dict(m[kk], **vv) if isinstance(vv, dict) and isinstance(m.get(kk), dict) else vv)
            out[k] = m
        else:
            out[k] = v
    return out


def resolve(rig, pose, diag):
    """Pose spec -> dict of per-bone N (upper body + fingers) + hips transform + feet (legs solve per frame)."""
    rot = {}
    for b in AXIAL:
        rot[b] = euler(pose.get(b, (0, 0, 0)))
    for s, side, sg in (('L', 'left', 1), ('R', 'right', -1)):
        el, pr = pose.get('shoulder' + s, (0, 0))
        nsh = qaxis(Z, sg * el) @ qaxis(Y, -sg * pr)
        rot[f'{side}Shoulder'] = nsh
        spec = pose['arm' + s]
        rot.update(solve_arm(rig, 'arm' + s, spec, nsh, diag))
        rot.update(hand_rots(rig, side, spec.get('hand', 'relaxed')))
    hp = pose['hips']
    return dict(rot=rot, hips_pos=rig.head['hips'] + V(hp['pos']), hips_rot=euler(hp['rot']), feet=pose['feet'])


# ============================================================================ interpolation
class Channel:
    """Auto-clamped cubic Hermite over (beat, vector) keys; periodic for loops, flat-ended for one-shots."""

    def __init__(self, times, values, period=None, holds=()):
        self.t = list(times)
        self.v = [Vector(v) for v in values]
        self.P = period
        self.holds = set(holds)
        n = len(self.t)
        self.m = []
        for k in range(n):
            if k in self.holds or (self.P is None and (k == 0 or k == n - 1)) or n == 1:
                self.m.append(Vector([0.0] * len(self.v[k])))
                continue
            tp, vp = self._nb(k, -1)
            tn, vn = self._nb(k, +1)
            d0 = (self.v[k] - vp) / (self.t[k] - tp)
            d1 = (vn - self.v[k]) / (tn - self.t[k])
            m = Vector([0.0] * len(self.v[k]))
            for i in range(len(m)):
                if d0[i] * d1[i] <= 0:
                    m[i] = 0.0
                else:
                    mi = (vn[i] - vp[i]) / (tn - tp)
                    lim = 3.0 * min(abs(d0[i]), abs(d1[i]))
                    m[i] = max(-lim, min(lim, mi))
            self.m.append(m)

    def _nb(self, k, step):
        n = len(self.t)
        j = k + step
        if 0 <= j < n:
            return self.t[j], self.v[j]
        return (self.t[j % n] + (self.P if step > 0 else -self.P)), self.v[j % n]

    def __call__(self, t):
        n = len(self.t)
        if n == 1:
            return self.v[0].copy()
        if self.P is not None:
            t = (t - self.t[0]) % self.P + self.t[0]
        else:
            t = max(self.t[0], min(self.t[-1], t))
        k = n - 1
        for i in range(n - 1):
            if t < self.t[i + 1]:
                k = i
                break
        if k == n - 1:
            if self.P is None:
                return self.v[-1].copy()
            t0, v0, m0 = self.t[k], self.v[k], self.m[k]
            t1, v1, m1 = self.t[0] + self.P, self.v[0], self.m[0]
        else:
            t0, v0, m0 = self.t[k], self.v[k], self.m[k]
            t1, v1, m1 = self.t[k + 1], self.v[k + 1], self.m[k + 1]
        h = t1 - t0
        s = (t - t0) / h
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        return v0 * h00 + m0 * (h10 * h) + v1 * h01 + m1 * (h11 * h)


# ============================================================================ clips
CLIPS = {}


def clip(name, beats, loop, section, keys, lag=None, layers=(), base=STAND, notes='', holds=()):
    lag = lag or {}
    if loop and name.endswith('_hold') and lag:
        # a _hold loop must START on the exact numbers its one-shot ended on: lagged bones read the loop's tail at
        # frame 0, so the tail holds a flat copy of the first key for the longest lag
        k0 = sorted(keys, key=lambda k: k[0])[0]
        keys = list(keys) + [(beats - max(lag.values()) - 0.05, k0[1], {'hold': True})]
    CLIPS[name] = dict(name=name, beats=beats, loop=loop, section=section, keys=keys, lag=lag,
                       layers=list(layers), base=base, notes=notes, holds=holds)


LAG_ARMS = {'LowerArm': 0.06, 'Hand': 0.12, 'fingers': 0.16, 'neck': 0.04, 'head': 0.08}


def breath(period, amp=1.0):
    """Inhale lifts the chest (extension), rises the shoulders; the neck counters so the head stays level.
    One-sided (sin^2): zero AND zero-velocity at beat 0, so a loop starts exactly on its key pose at rest —
    a one-shot that ends still hands over to its _hold loop with no kick (measured: frame diffs stay smooth)."""
    def f(t):
        s = math.sin(math.pi * t / period) ** 2
        return {'chest': (-2.6 * amp * s, 0, 0), 'spine': (-1.0 * amp * s, 0, 0), 'neck': (2.0 * amp * s, 0, 0),
                'leftShoulder': ('elev', 1.8 * amp * s), 'rightShoulder': ('elev', 1.8 * amp * s)}
    return f


def arm(palm, normal, fingers, pole, hand=None, **kw):
    """An IK arm key: palm-surface point, palm facing, finger direction, elbow direction, hand shape."""
    d = {'palm': palm, 'normal': normal, 'fingers': fingers, 'pole': pole}
    if hand:
        d['hand'] = hand
    d.update(kw)
    return d


# ---------------------------------------------------------------- the neutral: stand and breathe
clip('stand_breathe', 8, True, 'anywhere she simply stands and sings (the DAISY idle; same stance as every clip)',
     keys=[(0, {}), (4, {'head': (-2, 2, -2.5), 'chest': (-2.5, -1, 1.5)})],
     lag={'neck': 0.1, 'head': 0.2}, layers=[breath(8, 1.2)],
     notes='use instead of the engine idle between DAISY clips: same foot marks, so crossfades never slide')


# ---------------------------------------------------------------- 1. sing_gesture_a: presenting to her right
# (the machines stand beside her). Beat 1 = the presentation, beat 3 = the hand drawn back in to the belly,
# beat 4 = the little roll that carries it out again. Head looks out with the hand, then back to the audience.
GA_LEFT = arm((0.240, 0.72, 0.10), (-0.84, 0.1, -0.45), (0.08, -1, 0.22), (0.35, 0, -1), 'relaxed')
clip('sing_gesture_a', 4, True, 'verse 1 / verse 2: the machine lines (she shows the machine that is singing)',
     keys=[
         (0.0, {'armR': arm((-0.56, 1.075, 0.36), (-0.1, 0.9, 0.4), (-0.65, 0.08, 0.75), (-0.3, -1, -0.3), 'soft'),
                'armL': GA_LEFT, 'chest': (-2, -7, 1), 'neck': (3, -3, 0), 'head': (-3, -12, -2),
                'hips': {'pos': (-0.020, -0.007, 0.0), 'rot': (0, 0, -2.5)}}),
         (0.6, {'armR': arm((-0.575, 1.05, 0.33), (-0.1, 0.9, 0.4), (-0.68, 0.04, 0.72), (-0.3, -1, -0.3), 'open'),
                'armL': GA_LEFT, 'chest': (-2.5, -7.5, 1), 'neck': (3, -3, 0), 'head': (-3.5, -13, -2),
                'hips': {'pos': (-0.021, -0.007, 0.0), 'rot': (0, 0, -2.5)}}),
         (1.6, {'armR': arm((-0.47, 0.95, 0.35), (0.2, 0.9, 0.3), (-0.45, -0.05, 0.88), (-0.35, -1, -0.3), 'soft'),
                'armL': arm((0.238, 0.725, 0.105), (-0.84, 0.1, -0.45), (0.08, -1, 0.24), (0.35, 0, -1), 'relaxed'),
                'chest': (-2.5, -4, 1.2), 'neck': (3, -2, 0), 'head': (-4, -6, -1.5),
                'hips': {'pos': (-0.016, -0.007, 0.0), 'rot': (0, 1, -2.2)}}),
         (2.4, {'armR': arm((-0.22, 0.95, 0.30), (0.55, 0.75, 0.3), (0.45, 0.05, 0.9), (-0.6, -1, -0.2), 'soft'),
                'armL': arm((0.236, 0.73, 0.11), (-0.84, 0.1, -0.45), (0.08, -1, 0.25), (0.35, 0, -1), 'relaxed'),
                'chest': (-2.5, -1.5, 1.5), 'neck': (3, 0, 0), 'head': (-4, -1, -1),
                'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2.0)}}),
         (3.3, {'armR': arm((-0.36, 1.02, 0.37), (0.1, 0.95, 0.2), (-0.3, 0.08, 0.95), (-0.45, -1, -0.3), 'soft'),
                'armL': arm((0.239, 0.722, 0.102), (-0.84, 0.1, -0.45), (0.08, -1, 0.23), (0.35, 0, -1), 'relaxed'),
                'chest': (-2, -4.5, 1.2), 'neck': (3, -2, 0), 'head': (-3, -7, -1.5),
                'hips': {'pos': (-0.017, -0.007, 0.0), 'rot': (0, 0.5, -2.3)}}),
     ], lag=LAG_ARMS, layers=[breath(4, 0.6)])


# ---------------------------------------------------------------- 2. sing_gesture_b: palm up, the other hand on the chest
# The left hand rests over her heart, in FRONT of the drooping lower petals (petal 5_L runs z 0.10 -> 0.23 there).
# The right palm offers upward: it lifts into the downbeat (beat 1), settles, lifts smaller into beat 3.
GB_HEART = arm((0.088, 1.172, 0.236), (0.0, 0.05, -1.0), (-0.66, 0.74, 0.06), (1.0, -0.8, -0.2), 'flat')
clip('sing_gesture_b', 4, True, 'pre-chorus / verse 3: sung to the audience ("I only open when you call my name")',
     keys=[
         (0.0, {'armL': GB_HEART, 'armR': arm((-0.28, 1.13, 0.43), (0.12, 0.95, 0.28), (-0.25, 0.12, 0.96), (-0.4, -1, -0.2), 'open'),
                'chest': (1.5, -3, 1), 'neck': (4, -1, 0), 'head': (1, -3, -2), 'hips': {'pos': (-0.012, -0.007, 0.005), 'rot': (0, 1, -2)}}),
         (1.0, {'armL': GB_HEART, 'armR': arm((-0.25, 1.05, 0.40), (0.08, 0.96, 0.25), (-0.22, 0.05, 0.97), (-0.4, -1, -0.2), 'soft'),
                'chest': (-2, -2, 1.3), 'neck': (3, 0, 0), 'head': (-3, -1, -2), 'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2)}}),
         (2.0, {'armL': GB_HEART, 'armR': arm((-0.30, 1.10, 0.42), (0.15, 0.95, 0.25), (-0.3, 0.1, 0.95), (-0.4, -1, -0.2), 'open'),
                'chest': (0.5, -4, 1), 'neck': (3.5, -1, 0), 'head': (-0.5, -5, -2.5), 'hips': {'pos': (-0.013, -0.007, 0.004), 'rot': (0, 1, -2)}}),
         (3.0, {'armL': GB_HEART, 'armR': arm((-0.26, 1.04, 0.39), (0.08, 0.96, 0.25), (-0.22, 0.05, 0.97), (-0.4, -1, -0.2), 'soft'),
                'chest': (-2, -2, 1.3), 'neck': (3, 0, 0), 'head': (-3, -2, -2), 'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2)}}),
     ], lag=LAG_ARMS, layers=[breath(4, 0.6)])


# ---------------------------------------------------------------- 3. chorus_sway: weight side to side, arms loose
# Weight on her left on beats 1 and 5, on her right on 3 and 7 (two sways a bar); the hips dip as they cross,
# the free heel peels, the arms swing a little past the body like hung pendulums (they lag), the head rides last.
def _sway(side, depth, arms_fwd, head_turn):
    sg = 1 if side == 'L' else -1
    return {
        'hips': {'pos': (-0.004 + sg * 0.050, -0.016, 0.0), 'rot': (0, sg * 3, sg * 3.0)},
        'spine': (0, sg * -1, sg * -5.5), 'chest': (-2, sg * 4, sg * -3.5), 'neck': (3, 0, sg * -1.0),
        'head': (-3, sg * head_turn, sg * -2.5),
        'shoulderL': (-2 + (1.5 if sg < 0 else -0.5), 3), 'shoulderR': (-2 + (1.5 if sg > 0 else -0.5), 3),
        'armL': arm((0.236 + sg * 0.05, 0.694, 0.082 + arms_fwd * sg), (-0.84, 0.05, -0.48), (0.07 + sg * 0.16, -1, 0.16), (0.35, 0, -1)),
        'armR': arm((-0.234 + sg * 0.05, 0.698, 0.076 - arms_fwd * sg), (0.84, 0.05, -0.50), (-0.07 + sg * 0.16, -1, 0.14), (-0.35, 0, -1)),
        'feet': {'L': {'pos': (0.118, -0.022), 'yaw': 8.0, 'lift': 0.0 if sg > 0 else depth},
                 'R': {'pos': (-0.112, -0.046), 'yaw': -6.0, 'lift': depth if sg > 0 else 0.0}},
    }


def _cross(y=-0.022, turn=0.0):
    return {'hips': {'pos': (-0.004, y, 0.0), 'rot': (0, turn, 0)}, 'spine': (0, 0, 0), 'chest': (-2, 0, 0),
            'head': (-3, 0, 0), 'neck': (3, 0, 0)}


clip('chorus_sway', 8, True, 'chorus 1 / chorus 2 / final chorus (the singalong sway; also the vigil)',
     keys=[(0, _sway('L', 7, 0.02, 4)), (1, _cross()), (2, _sway('R', 7, 0.02, -4)), (3, _cross()),
           (4, _sway('L', 9, 0.035, 6)), (5, _cross(-0.024)), (6, _sway('R', 9, 0.035, -6)), (7, _cross(-0.024))],
     lag={'UpperArm': 0.10, 'LowerArm': 0.18, 'Hand': 0.26, 'fingers': 0.3, 'neck': 0.12, 'head': 0.24},
     layers=[breath(8, 0.8)])


# ---------------------------------------------------------------- 4. sing_open_arms: arms wide on a long note
# One slow breath over two bars: the arms float up and open on the inhale (beats 1-4), settle on 5-8;
# the palms turn up as they rise. Never symmetric: the left leads, the right answers half a beat later.
def _open(lift, spread, tilt, hips_x, head):
    return {
        'hips': {'pos': (hips_x, -0.006, 0.004), 'rot': (0, 1, -2.0 + 1.5 * (hips_x + 0.012) / 0.015)},
        'spine': (-1, 0, 1.0), 'chest': (-4 - 2 * lift, 0, 1.0), 'neck': (2, 0, 0), 'head': head,
        'shoulderL': (1 + 4 * lift, -2), 'shoulderR': (1 + 4 * lift, -2),
        'armL': arm((0.63 + 0.02 * spread, 1.10 + 0.06 * lift, 0.28), (0.05, 0.72 + 0.1 * tilt, 0.66), (0.74, -0.08, 0.66),
                    (0.2, -1, -0.5), 'open'),
        'armR': arm((-0.64 - 0.02 * spread, 1.09 + 0.05 * lift, 0.30), (-0.05, 0.7 + 0.1 * tilt, 0.68), (-0.72, -0.1, 0.68),
                    (-0.2, -1, -0.5), 'soft'),
    }


clip('sing_open_arms', 8, True, 'long notes: "Daisy, Daisy", the choir, "ERUPT into polyphony", the final chorus',
     keys=[(0, _open(0.0, 0.0, 0.0, -0.012, (-6, 0, -1))),
           (2, _open(0.55, 0.6, 0.6, -0.004, (-8, 2, -3))),
           (4, _open(1.0, 1.0, 1.0, 0.002, (-9, 1, -4))),
           (6, _open(0.45, 0.4, 0.4, -0.006, (-7, -2, 0)))],
     lag={'rightUpperArm': 0.5, 'rightLowerArm': 0.62, 'rightHand': 0.75, 'LowerArm': 0.12, 'Hand': 0.25,
          'fingers': 0.35, 'neck': 0.1, 'head': 0.2},
     layers=[breath(8, 0.6)])


# ---------------------------------------------------------------- 5. hand_to_heart (+ hand_to_heart_hold)
# The right hand crosses to her heart and rests there, palm flat, OVER the lower petals (never under them);
# a breath in first, then the head softens down and to the side on the exhale.
HEART = {
    'armR': arm((0.072, 1.172, 0.236), (0.05, 0.05, -1.0), (0.64, 0.76, -0.05), (-0.55, -1, 0.05), 'flat'),
    'chest': (0, -3, 1.3), 'spine': (1, -1, 1.2), 'neck': (5, -1, 0), 'head': (4, -4, 4),
    'shoulderR': (-3, 6), 'shoulderL': (-3, 3), 'hips': {'pos': (-0.012, -0.007, 0.0), 'rot': (0, 2, -2.0)},
}
clip('hand_to_heart', 5, False, 'verse 3 ("I choose this face, this daisy"), chorus 2 (for Sydney), the funeral',
     keys=[(0, {}),
           (0.8, {'chest': (-3.5, -1, 1.3), 'shoulderR': (0, 1), 'neck': (2, 0, 0), 'head': (-4, 1, -1.5),
                  'armR': arm((-0.20, 0.80, 0.15), (0.6, 0.2, -0.6), (-0.1, -0.8, 0.5), (-0.4, -0.3, -1), 'relaxed')}),
           (1.8, {'chest': (-3, -2, 1.3), 'neck': (2, 0, 0), 'head': (-3, -1, -1),
                  'armR': arm((-0.045, 1.06, 0.30), (0.1, -0.55, -0.83), (0.72, 0.38, 0.58), (-0.55, -1, 0.0), 'soft')}),
           (2.6, dict(HEART, head=(0, -2, 1), neck=(4, -1, 0), chest=(-2.5, -3, 1.3),
                      armR=arm((0.073, 1.175, 0.230), (0.05, 0.05, -1.0), (0.64, 0.76, -0.05), (-0.55, -1, 0.05), 'flat'))),
           (5, HEART)],
     lag=LAG_ARMS)
clip('hand_to_heart_hold', 8, True, 'hold after hand_to_heart (starts on its last frame)',
     keys=[(0, HEART), (4, dict(HEART, head=(5, -6, 2.5), chest=(0.5, -3.5, 1.5)))],
     lag={'neck': 0.15, 'head': 0.3}, layers=[breath(8, 1.3)])


# ---------------------------------------------------------------- 6. look_up_sky (+ look_up_sky_hold)
# A small dip first (the thought), then the face lifts ~32 deg and the chest opens; the arms float off
# the body with the palms turning forward — wonder, not alarm.
SKY = {
    'hips': {'pos': (-0.010, -0.008, 0.012), 'rot': (-2, 2, -1.5)},
    'spine': (-3, -1, 1.0), 'chest': (-8, -1, 1.0), 'neck': (-10, 0, 0), 'head': (-22, 2, -3),
    'shoulderL': (1, -5), 'shoulderR': (1, -5),
    'armL': arm((0.315, 0.79, 0.18), (-0.55, 0.25, 0.8), (0.25, -1, 0.2), (0.4, 0, -1), 'float'),
    'armR': arm((-0.305, 0.80, 0.17), (0.55, 0.25, 0.8), (-0.25, -1, 0.2), (-0.4, 0, -1), 'float'),
}
clip('look_up_sky', 6, False, 'the sky arc: pre-chorus dawn, the lanterns for Sydney, "the porch light turns on"',
     keys=[(0, {}),
           (1.0, {'neck': (5, 0, 0), 'head': (2, 2, -1), 'chest': (-1, -1, 1.3)}),
           (3.4, dict(SKY, head=(-25, 3, -3.5), neck=(-11, 0, 0), chest=(-9, -1, 1.0))),
           (6, SKY)],
     lag={'LowerArm': 0.1, 'Hand': 0.2, 'fingers': 0.25, 'neck': 0.12, 'head': 0.25, 'chest': 0.05})
clip('look_up_sky_hold', 8, True, 'hold after look_up_sky (starts on its last frame)',
     keys=[(0, SKY), (3, dict(SKY, head=(-23, 7, -1.5))), (6, dict(SKY, head=(-21, -3, -4)))],
     lag={'neck': 0.15, 'head': 0.3}, layers=[breath(8, 1.0)])


# ---------------------------------------------------------------- 7. phone_raise (+ phone_raise_hold)
# The right hand lifts a phone light high: elbow leads, the arm passes IN FRONT of the side petals, and the hand
# ends beside the top of the flower (13 cm outside the petal ring, 20 cm in front of it), palm to the stage.
PHONE = {
    'shoulderR': (12, 8), 'chest': (-4, -3, 2.5), 'spine': (-1, -1, 2.0), 'neck': (1, -2, 0), 'head': (-8, -6, 1),
    'armR': arm((-0.53, 1.73, 0.29), (0.42, 0.1, 0.9), (-0.12, 1, 0.1), (-1, -0.5, -0.1), 'hold'),
    'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2.0)},
}
clip('phone_raise', 4, False, 'the bridge: the power fails and the phone lights come on one by one (the vigil)',
     keys=[(0, {}),
           (0.9, {'shoulderR': (2, 6), 'chest': (-3, -2, 1.5),
                  'armR': arm((-0.29, 0.98, 0.25), (0.6, 0.1, 0.8), (0.0, 0.2, 1), (-0.8, -1, -0.3), 'relaxed')}),
           (1.9, {'shoulderR': (8, 8), 'chest': (-4, -3, 2.0), 'head': (-5, -4, 0),
                  'armR': arm((-0.42, 1.40, 0.40), (0.4, 0.05, 0.92), (-0.1, 0.9, 0.35), (-1, -0.6, -0.1), 'hold')}),
           (3.1, dict(PHONE, armR=arm((-0.535, 1.745, 0.295), (0.42, 0.1, 0.9), (-0.14, 1, 0.1), (-1, -0.5, -0.1), 'hold'))),
           (4, PHONE)],
     lag=LAG_ARMS)
clip('phone_raise_hold', 8, True, 'hold after phone_raise: a slow vigil sway (starts on its last frame)',
     keys=[(0, PHONE),
           (2, dict(PHONE, hips={'pos': (0.010, -0.010, 0.0), 'rot': (0, 3, 1.0)}, spine=(-1, -2, -1.0), head=(-8, -3, -1),
                    armR=arm((-0.50, 1.755, 0.30), (0.4, 0.1, 0.91), (0.04, 1, 0.12), (-1, -0.5, -0.1), 'hold'))),
           (6, dict(PHONE, hips={'pos': (-0.030, -0.013, 0.0), 'rot': (0, 1, -3.5)}, spine=(-1, 0, 4.0), head=(-8, -9, 3),
                    armR=arm((-0.56, 1.70, 0.28), (0.44, 0.1, 0.89), (-0.24, 1, 0.1), (-1, -0.5, -0.1), 'hold')))],
     lag={'UpperArm': 0.15, 'LowerArm': 0.25, 'Hand': 0.35, 'neck': 0.15, 'head': 0.3})


# ---------------------------------------------------------------- 8. head_bow (+ head_bow_hold)
# Mourning: the hands meet low first (right over left), then the head goes down slowly, shoulders soften.
BOW_HANDS = {
    'armL': arm((0.035, 0.875, 0.125), (-0.25, 0.1, -0.96), (-0.72, -0.55, 0.25), (0.5, 0, -1), 'clasp'),
    'armR': arm((-0.015, 0.885, 0.155), (0.22, 0.1, -0.97), (0.74, -0.52, 0.25), (-0.5, 0, -1), 'clasp'),
}
MOURN = dict(BOW_HANDS, chest=(5, -1, 1.0), spine=(2, -1, 1.2), neck=(12, 0, 0), head=(22, 0, 1),
             shoulderL=(-4, 6), shoulderR=(-4, 6), hips={'pos': (-0.010, -0.009, 0.0), 'rot': (1, 2, -1.5)})
clip('head_bow', 6, False, 'the funeral ("two hundred people came"), "they turned that one off"',
     keys=[(0, {}),
           (2.6, dict(BOW_HANDS, chest=(0, -1, 1.2), neck=(5, 0, 0), head=(3, 0, 0), shoulderL=(-3, 5), shoulderR=(-3, 5))),
           (4.4, dict(MOURN, neck=(11, 0, 0), head=(20, 0, 1))),
           (6, MOURN)],
     lag={'LowerArm': 0.1, 'Hand': 0.2, 'fingers': 0.3, 'neck': 0.2, 'head': 0.4})
clip('head_bow_hold', 8, True, 'hold after head_bow (starts on its last frame)',
     keys=[(0, MOURN), (4, dict(MOURN, head=(24, 1, 2), neck=(13, 0, 0)))],
     lag={'neck': 0.2, 'head': 0.4}, layers=[breath(8, 1.4)])


# ---------------------------------------------------------------- 9. bow_thanks: a gracious bow and back up
# Prep (chest lifts, right hand to the belly, left arm sweeps open), fold ~37 deg from the hips with the hips
# going BACK over the heels, hold a beat, rise; ends exactly on STAND so any clip can follow.
BOW_ARMS = {
    'armR': arm((-0.005, 1.00, 0.115), (0.1, 0.0, -1.0), (0.95, 0.25, 0.0), (-0.6, -1, 0.1), 'flat'),
    'armL': arm((0.50, 0.93, 0.26), (0.05, 0.45, 0.9), (0.72, -0.35, 0.6), (0.3, -1, -0.5), 'soft'),
}
clip('bow_thanks', 7, False, 'the end card: thanks to the audience',
     keys=[(0, {}),
           (1.2, dict(BOW_ARMS, chest=(-4, 0, 1.2), neck=(2, 0, 0), head=(-4, 0, 0))),
           (3.0, dict(BOW_ARMS, hips={'pos': (-0.010, -0.014, -0.055), 'rot': (24, 1, -1.5)}, spine=(7, 0, 0.5),
                      chest=(6, 0, 0.5), neck=(5, 0, 0), head=(9, 0, 0))),
           (4.0, dict(BOW_ARMS, hips={'pos': (-0.010, -0.015, -0.058), 'rot': (25, 1, -1.5)}, spine=(7.5, 0, 0.5),
                      chest=(6.5, 0, 0.5), neck=(5, 0, 0), head=(10, 0, 0)), {'hold': True}),
           (5.6, dict(BOW_ARMS, hips={'pos': (-0.011, -0.008, -0.012), 'rot': (5, 2, -2)}, spine=(0, -1, 1),
                      chest=(-3, -1, 1.2), neck=(3, 0, 0), head=(-4, 1, -1))),
           (7, {})],
     lag={'LowerArm': 0.1, 'Hand': 0.2, 'fingers': 0.25, 'neck': 0.1, 'head': 0.2})


# ---------------------------------------------------------------- 10. wave_goodbye
# The right hand up beside the flower (outside the petal ring, in front of it), palm to the audience; two waves
# a bar, the hand whipping a little behind the forearm. A friendly head tilt, a small answering sway.
def _wave(out, y, head_z, hips_x):
    return {
        'shoulderR': (8, 6), 'chest': (-3, -4, 1.0 - out), 'head': (-3, -6, head_z), 'neck': (3, -2, 0),
        'hips': {'pos': (hips_x, -0.006, 0.0), 'rot': (0, 1, -2.0)},
        'armR': arm((-0.475 - 0.095 * out, y - 0.02 * out, 0.26), (0.05, 0.05, 1.0), (-0.52 * out + 0.36 * (1 - out), 0.92, 0.05),
                    (-0.6, -0.8, -0.1), 'wave'),
    }


clip('wave_goodbye', 4, True, 'the outro: "close when you go" (goodbye to the viewer, to the day)',
     keys=[(0, _wave(1, 1.60, -4, -0.014)), (1, _wave(0, 1.63, -5, -0.010)),
           (2, _wave(1, 1.61, -4, -0.014)), (3, _wave(0, 1.635, -5.5, -0.009))],
     lag={'Hand': 0.12, 'fingers': 0.2, 'neck': 0.1, 'head': 0.2}, layers=[breath(4, 0.4)])


# ---------------------------------------------------------------- mirrors: the same performance with the other hand
# Mirrored at the POSE level (not the baked curves): arms and shoulders swap sides with x negated, the torso's and
# hips' turn/tilt flip, the peeling heel swaps — but the FEET KEEP THE STANCE, so a mirror crossfades with every
# other clip without sliding. hand_to_heart / sing_gesture_b stay one-sided: the heart is on her left.
def mirror_pose(p):
    out = {}
    for k, v in p.items():
        if k in AXIAL:
            out[k] = (v[0], -v[1], -v[2])
        elif k == 'hips':
            h = dict(v)
            if 'pos' in h:
                h['pos'] = (-h['pos'][0], h['pos'][1], h['pos'][2])
            if 'rot' in h:
                h['rot'] = (h['rot'][0], -h['rot'][1], -h['rot'][2])
            out[k] = h
        elif k in ('armL', 'armR'):
            m = dict(v)
            for kk in ('palm', 'normal', 'fingers', 'pole'):
                if kk in m:
                    m[kk] = (-m[kk][0], m[kk][1], m[kk][2])
            out['armR' if k == 'armL' else 'armL'] = m
        elif k in ('shoulderL', 'shoulderR'):
            out['shoulderR' if k == 'shoulderL' else 'shoulderL'] = v
        elif k == 'feet':
            out[k] = {'L': dict(STAND['feet']['L'], lift=v.get('R', {}).get('lift', 0.0)),
                      'R': dict(STAND['feet']['R'], lift=v.get('L', {}).get('lift', 0.0))}
        else:
            out[k] = v
    return out


def mirror_clip(src, name):
    c = CLIPS[src]
    swap = lambda k: k.replace('left', '\0').replace('right', 'left').replace('\0', 'right')
    CLIPS[name] = dict(c, name=name, base=mirror_pose(c['base']),
                       keys=[(k[0], mirror_pose(k[1])) + tuple(k[2:]) for k in c['keys']],
                       lag={swap(k): v for k, v in c['lag'].items()},
                       section=f"mirror of {src}: the other hand, toward her other side (same stance)", notes='')


mirror_clip('sing_gesture_a', 'sing_gesture_a_mirror')
mirror_clip('phone_raise', 'phone_raise_mirror')
mirror_clip('phone_raise_hold', 'phone_raise_mirror_hold')
mirror_clip('wave_goodbye', 'wave_goodbye_mirror')


# ---------------------------------------------------------------- test rig for hand shapes (build with --clips zz_handtest)
def _thumbs(t):
    return dict(HANDS['relaxed'], thumb=t)


_SHOW = {'armL': {'palm': (0.16, 1.16, 0.34), 'normal': (0, 0.1, 1), 'fingers': (0.1, 1, 0.1), 'pole': (0.6, -1, -0.2)}}
clip('zz_handtest', 8, False, 'test', notes='hand shapes',
     keys=[(0, merge(_SHOW, {'armL': {'hand': _thumbs((38, 0, 10, 14))}, 'armR': {'hand': _thumbs((38, 0, 10, 14))}}), {'hold': True}),
           (1.9, merge(_SHOW, {'armL': {'hand': _thumbs((38, 0, 10, 14))}, 'armR': {'hand': _thumbs((38, 0, 10, 14))}}), {'hold': True}),
           (2, merge(_SHOW, {'armL': {'hand': _thumbs((50, -6, 6, 10))}, 'armR': {'hand': _thumbs((50, -6, 6, 10))}}), {'hold': True}),
           (3.9, merge(_SHOW, {'armL': {'hand': _thumbs((50, -6, 6, 10))}, 'armR': {'hand': _thumbs((50, -6, 6, 10))}}), {'hold': True}),
           (4, merge(_SHOW, {'armL': {'hand': _thumbs((28, 8, 16, 20))}, 'armR': {'hand': _thumbs((28, 8, 16, 20))}}), {'hold': True}),
           (5.9, merge(_SHOW, {'armL': {'hand': _thumbs((28, 8, 16, 20))}, 'armR': {'hand': _thumbs((28, 8, 16, 20))}}), {'hold': True}),
           (6, merge(_SHOW, {'armL': {'hand': 'open'}, 'armR': {'hand': 'soft'}}), {'hold': True}),
           (8, merge(_SHOW, {'armL': {'hand': 'open'}, 'armR': {'hand': 'soft'}}), {'hold': True})])


# ============================================================================ sampling + baking
def lagged(t, lag, clipd):
    if clipd['loop']:
        return (t - lag) % clipd['beats']
    # one-shots: the lag fades out over the last beat, so every bone lands on the final key on the final frame
    # (the clamped hold is exactly the final pose, and its _hold loop starts on the same numbers)
    B = float(clipd['beats'])
    return max(0.0, min(B, t - lag * smooth(B - t)))


def bone_lag(h, lag):
    for key, v in lag.items():
        if key == 'fingers':
            if any(f in h for f in FINGERS + ('Thumb',)):
                return v
        elif h.endswith(key) or h == key:
            return v
    return 0.0


def build_channels(rig, c):
    base_pose = c['base']
    ref = resolve(rig, base_pose, [])
    keys = sorted(c['keys'], key=lambda k: k[0])
    poses, diag = [], []
    for k in keys:
        d = [f"  key @ beat {k[0]}"]
        poses.append(resolve(rig, merge(base_pose, k[1]), d))
        diag += d
    REPORT.append(f"[{c['name']}] {c['beats']} beats {'loop' if c['loop'] else 'one-shot'}")
    REPORT.extend(diag)
    times = [k[0] for k in keys]
    P = float(c['beats']) if c['loop'] else None
    holds = [i for i, k in enumerate(keys) if len(k) > 2 and k[2].get('hold')]
    ch = {}
    for h in ref['rot']:
        vals = [qlog(ref['rot'][h].inverted() @ p['rot'][h]) for p in poses]
        ch[h] = Channel(times, vals, P, holds)
    ch['_hips_pos'] = Channel(times, [p['hips_pos'] for p in poses], P, holds)
    ch['_hips_rot'] = Channel(times, [qlog(p['hips_rot']) for p in poses], P, holds)
    for s in ('L', 'R'):
        ch['_lift' + s] = Channel(times, [Vector((p['feet'][s].get('lift', 0.0), 0.0)) for p in poses], P, holds)
    return ref, ch, poses


def sample(rig, c, ref, ch, poses, t):
    rot = {}
    for h in ref['rot']:
        tt = lagged(t, bone_lag(h, c['lag']), c)
        rot[h] = ref['rot'][h] @ qexp(ch[h](tt))
    hips_pos = ch['_hips_pos'](lagged(t, 0, c))
    hips_rot = qexp(ch['_hips_rot'](lagged(t, 0, c)))
    extra_hips = Vector((0, 0, 0))
    for layer in c['layers']:
        for b, e in layer(t).items():
            if b == 'hips_pos':
                extra_hips += V(e)
            elif b == 'hips_rot':
                hips_rot = hips_rot @ euler(e)
            elif isinstance(e, tuple) and len(e) == 2 and e[0] == 'elev':
                sg = 1 if b.startswith('left') else -1
                rot[b] = rot[b] @ qaxis(Z, sg * e[1])
            else:
                rot[b] = rot[b] @ euler(e)
    hips_pos = hips_pos + extra_hips
    feet = poses[0]['feet']
    worst = 0.0
    for s in ('L', 'R'):
        foot = dict(feet[s], lift=ch['_lift' + s](lagged(t, 0, c))[0])
        r, reach, _ = solve_leg(rig, 'leg' + s, hips_pos, hips_rot, foot)
        rot.update(r)
        worst = max(worst, reach)
    rot['hips'] = hips_rot
    return rot, hips_pos, worst


def bake(rig, c):
    ref, ch, poses = build_channels(rig, c)
    nf = int(round(c['beats'] * BEAT * FPS))
    act = bpy.data.actions.new(c['name'])
    arm = rig.arm
    arm.animation_data_create()
    arm.animation_data.action = act
    series = {h: [] for h in rig.bones}
    hips_loc = []
    worst = 0.0
    for f in range(nf + 1):
        t = f / (BEAT * FPS)
        rot, hp, reach = sample(rig, c, ref, ch, poses, t)
        worst = max(worst, reach)
        for h in rig.bones:
            q = rig.basis(h, rot.get(h, Quaternion()))
            if series[h] and series[h][-1].dot(q) < 0:
                q = -q
            series[h].append(q)
        hips_loc.append(rig.hips_location(hp))
    if worst > 0.999:
        REPORT.append(f"  !!! leg reach {worst:.3f}: a foot would lift off its mark")
    REPORT.append(f"  leg reach max {worst:.3f}")
    for h in rig.bones:
        pb = arm.pose.bones[rig.hb[h]]
        pb.rotation_mode = 'QUATERNION'
        path = pb.path_from_id('rotation_quaternion')
        for i in range(4):
            fc = act.fcurve_ensure_for_datablock(arm, path, index=i)
            co = []
            for f, q in enumerate(series[h]):
                co += [float(f), q[i]]
            fc.keyframe_points.add(nf + 1)
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [1] * (nf + 1))   # LINEAR (the exporter samples whole frames)
            fc.update()
    path = arm.pose.bones[rig.hb['hips']].path_from_id('location')
    for i in range(3):
        fc = act.fcurve_ensure_for_datablock(arm, path, index=i)
        co = []
        for f, loc in enumerate(hips_loc):
            co += [float(f), loc[i]]
        fc.keyframe_points.add(nf + 1)
        fc.keyframe_points.foreach_set('co', co)
        fc.keyframe_points.foreach_set('interpolation', [1] * (nf + 1))
        fc.update()
    return act, nf


def export(rig, c, act, nf):
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    sc.frame_start, sc.frame_end = 0, nf
    for pb in rig.arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
        pb.scale = Vector((1, 1, 1))
    rig.arm.animation_data.action = act
    bpy.context.view_layer.objects.active = rig.arm
    rig.arm.select_set(True)
    path = os.path.join(OUT, c['name'] + '.vrma')
    res = bpy.ops.export_scene.vrma(filepath=path, armature_object_name=rig.arm.name)
    if res != {'FINISHED'}:
        raise RuntimeError(f"export of {c['name']} failed: {res}")
    return path


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    want = None
    if '--clips' in argv:
        want = argv[argv.index('--clips') + 1].split(',')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(REPO, 'work'), exist_ok=True)
    rig = Rig()
    man_path = os.path.join(HERE, 'clips.json')
    manifest = json.load(open(man_path, encoding='utf-8')) if os.path.exists(man_path) else {}
    for name, c in CLIPS.items():
        if (want and name not in want) or (not want and name.startswith('zz_')):
            continue
        act, nf = bake(rig, c)
        path = export(rig, c, act, nf)
        if name.startswith('zz_'):
            continue
        manifest[name] = dict(file=f'eidoverse/assets/animations/{name}.vrma', beats=c['beats'], seconds=c['beats'] * BEAT,
                              loop=c['loop'], section=c['section'], notes=c['notes'], frames_64fps=nf + 1)
        print(f'[build_vrma] {name}: {nf + 1} samples, {c["beats"]} beats = {c["beats"] * BEAT:.4f} s -> {path}')
    manifest = dict(sorted(manifest.items()))
    with open(man_path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(REPO, 'work', 'vrma_build_report.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(REPORT) + '\n')
    for line in REPORT:
        print('[report] ' + line)
    if '--save-blend' in argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(REPO, 'work', 'claudesona_performance.blend'))


main()
