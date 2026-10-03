"""build_vrma.py — the claudesona's performance clips (VRM Animation, .vrma) for UNKNOWN FORCE.

Run it ONLY through the repository's isolated runner (a bare `blender --factory-startup` run against your real
Blender config deletes your installed extension packages; see docs/blender.md):

    bash run_blender.sh eidoverse/assets/animations/performance_uf_src/build_vrma.py [--clips a,b] [--save-blend]

Adapted from DAISY's builder (eidoverse/assets/animations/performance_src/build_vrma.py): the same IK, hand library,
stance and interpolation, so every clip here crossfades with DAISY's clips too (same foot marks). It imports
eidoverse/assets/vrms/claude_suit_wardrobe.vrm (digi's claudesona with every outfit, the tuta among them, VRM 1.0, a 2.00 m rig; the same
skeleton as claude_suit.vrm), evaluates every clip in CLIPS below, bakes one Blender action per clip, and exports
each with the VRM add-on's `bpy.ops.export_scene.vrma` to eidoverse/assets/animations/<name>.vrma, plus clips.json
next to this script. The build report goes to work/vrma_build_report_uf.txt.

TEMPO: the song is 92.90 BPM. One beat = 0.64584 s (the film's beat grid, rounded to 10 us). Every clip
is sampled at 40 samples per beat (61.9 Hz): the scene runs at fps 40 / fps_base T, and the exporter writes
time = frame * fps_base / fps, so beat k is EXACTLY frame 40k and a loop's last sample sits exactly on its last beat.

CONVENTIONS (read before adding a clip; DAISY's, plus three additions marked NEW)
  * Space = three-vrm's NORMALIZED humanoid frame: x = HER left, y = up, z = toward the audience (a camera at +z).
    Metres of the 2.00 m rig (the film shows it at 0.87). Angles in degrees. Time in BEATS.
  * Euler triples (hips/spine/chest/neck/head) = (x, y, z) applied as turn(y), nod(x), tilt(z):
    +x nods / bends forward, +y turns toward her left, +z tilts the top toward her right shoulder.
  * Shoulders (clavicles) = (elevate, protract) degrees, same meaning on both sides.
  * Arms are IK: 'palm' = the palm-surface point, 'normal' = the way the palm faces, 'fingers' = the way the
    fingers point, 'pole' = the way the ELBOW points, 'hand' = a HANDS shape. By default the targets are in the
    REST frame of the torso (the chest carries them when the spine bends).
  * NEW space='world': the targets are where the hand should be in the world (the floor frame, her feet at rest)
    at that key; the key's own torso pose converts them. For hands that hang by gravity while the chest arches
    (look_up), or a hand offered toward the lens.
  * NEW hang='LR': the layers (breath, nods, rolls) do not swing these arms: they keep their world orientation
    and only travel with the shoulder joint, as arms hanging by gravity do (DAISY's breath swung hanging hands
    ~4 cm forward on every inhale, because the arms ride the arching chest).
  * NEW lock: a key's 'lockL'/'lockR' weight (0..1, interpolated) pins that arm to the clip's world target in
    EVERY frame (IK re-solved per frame, like the legs), so breathing and torso drift cannot slide a hand that
    holds something fixed in the world (fence_hands).
  * Feet are planted by leg IK every frame; every clip shares the STAND stance, so crossfades never slide.
  * Keys are (beat, pose-overrides[, {'hold': True}]). Interpolation: auto-clamped cubic Hermite in rotation-
    vector space relative to STAND. Loops are periodic; one-shots start and end with zero velocity.
  * `lag` delays chains (beats) for overlap; `layers` add procedural motion periodic in the loop length.
  * NEW layers: breath(period, amp, steady_head) — steady_head counters the whole breath in the neck so the face
    holds a camera; nods(at, period, ...) — backbeat nods; shoulder_roll(period, ...) — a slow backward roll.

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
REL = 'eidoverse/assets/animations'
BEAT = 0.64584                            # s: UNKNOWN FORCE's beat (its beat grid: t = 0.12080 + k * BEAT)
BPM = 60.0 / BEAT                          # 92.90
SPB = 40                                   # samples per beat
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
        # the torso chain the arm IK hangs from: hips -> spine -> chest -> shoulders (no upperChest on this rig)
        assert self.parent['spine'] == 'hips' and self.parent['chest'] == 'spine', self.parent
        assert self.parent['leftShoulder'] == 'chest' and self.parent['rightShoulder'] == 'chest', self.parent
        self.order = []
        seen = set()
        while len(self.order) < len(self.hb):
            for h in self.hb:
                if h not in seen and (self.parent[h] is None or self.parent[h] in seen):
                    self.order.append(h)
                    seen.add(h)
        self.bones = [h for h in self.order if not h.endswith('Eye')]
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
    D2a = D1 @ H2
    wrist0 = D2a.inverted() @ Dh
    _, tw = swing_twist(wrist0, c['u2'])
    tw_f = max(-110.0, min(110.0, tw * spec.get('twist_share', 0.85)))
    N2 = H2 @ qaxis(c['u2'], tw_f)
    D2 = D1 @ N2
    Nh = D2.inverted() @ Dh
    sw, tw_w = swing_twist(Nh, c['u2'])
    wrist = math.degrees(sw.angle) if sw.angle <= math.pi else 360 - math.degrees(sw.angle)
    if diag is not None:
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


def torso_fk(rig, hips_pos, hips_rot, rot):
    """World joint positions + rotations of hips -> spine -> chest (normalized frame)."""
    J, R = {'hips': hips_pos}, {'hips': hips_rot}
    for b in ('spine', 'chest'):
        p = rig.parent[b]
        J[b] = J[p] + R[p] @ (rig.head[b] - rig.head[p])
        R[b] = R[p] @ rot[b]
    return J, R


def world_to_torso(rig, spec, J, R):
    """An arm spec in the world (floor frame) -> the same spec in the chest's rest frame, for this torso pose."""
    Ri = R['chest'].inverted()
    out = dict(spec)
    out['palm'] = tuple(rig.head['chest'] + Ri @ (V(spec['palm']) - J['chest']))
    for k in ('normal', 'fingers', 'pole'):
        out[k] = tuple(Ri @ V(spec[k]))
    out.pop('space', None)
    return out


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
    'float':   dict(Index=(7, 12, 6), Middle=(10, 16, 8), Ring=(14, 20, 10), Little=(18, 24, 12), spread=4, thumb=(40, -4, 6, 8)),
    # UNKNOWN FORCE
    # palm down over the room: long, quiet fingers, a little weight in them
    'press':   dict(Index=(5, 7, 3), Middle=(6, 8, 4), Ring=(8, 10, 5), Little=(10, 12, 6), spread=4, thumb=(40, -4, 4, 6)),
    # a calm "no": the palm shown, fingers together-ish, straight
    'stop':    dict(Index=(3, 4, 2), Middle=(3, 4, 2), Ring=(4, 6, 3), Little=(6, 8, 4), spread=4, thumb=(36, -6, 3, 5)),
    # the salute blade: fingers straight and closed, the thumb laid along the index
    'salute':  dict(Index=(1, 2, 1), Middle=(1, 2, 1), Ring=(2, 3, 1), Little=(3, 4, 2), spread=-2, thumb=(50, -2, 2, 4)),
    # hooked into a chain-link mesh: the knuckles at the wire, the two outer joints curled through it
    'hook':    dict(Index=(30, 62, 34), Middle=(32, 66, 36), Ring=(34, 66, 36), Little=(36, 64, 34), spread=1, thumb=(34, 8, 12, 14)),
    # an open palm offered: slightly cupped, the thumb out
    'offer':   dict(Index=(6, 9, 4), Middle=(8, 11, 5), Ring=(10, 13, 6), Little=(13, 16, 8), spread=8, thumb=(26, -10, 3, 5)),
    # the singing hand closing on beat 3: a loose cup, not a fist
    'cup':     dict(Index=(26, 38, 20), Middle=(30, 42, 22), Ring=(34, 44, 22), Little=(38, 46, 22), spread=0, thumb=(36, 10, 12, 12)),
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
    cax = tdir.cross(fing).normalized()
    fax = tdir.cross(V(0, -1, 0)).normalized()
    close, flex, mcp, ip = s['thumb']
    out['leftThumbMetacarpal'] = qaxis(cax, close) @ qaxis(fax, flex)
    out['leftThumbProximal'] = qaxis(fax, mcp)
    out['leftThumbDistal'] = qaxis(fax, ip)
    if side == 'right':
        out = {k.replace('left', 'right'): mirror_q(q) for k, q in out.items()}
    return out


# ============================================================================ poses
AXIAL = ('spine', 'chest', 'neck', 'head')

# DAISY's stance, unchanged: every UNKNOWN FORCE clip shares these foot marks (and so do DAISY's clips)
STAND = {
    'hips': {'pos': (-0.012, -0.006, 0.0), 'rot': (0, 2, -2.0)},
    'spine': (0, -1, 1.2), 'chest': (-2, -1.5, 1.3), 'neck': (3, 0, 0), 'head': (-3, 1, -1.5),
    'shoulderL': (-2, 3), 'shoulderR': (-2, 3),
    'armL': {'palm': (0.236, 0.690, 0.082), 'normal': (-0.84, 0.05, -0.48), 'fingers': (0.07, -1, 0.16),
             'pole': (0.35, 0, -1), 'hand': 'relaxed'},
    'armR': {'palm': (-0.234, 0.694, 0.076), 'normal': (0.84, 0.05, -0.50), 'fingers': (-0.07, -1, 0.14),
             'pole': (-0.35, 0, -1), 'hand': 'relaxed'},
    'feet': {'L': {'pos': (0.118, -0.022), 'yaw': 8.0}, 'R': {'pos': (-0.112, -0.046), 'yaw': -6.0}},
    'lockL': 0.0, 'lockR': 0.0,
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
    """Pose spec -> per-bone N (upper body + fingers) + hips transform + feet (legs solve per frame)."""
    rot = {}
    for b in AXIAL:
        rot[b] = euler(pose.get(b, (0, 0, 0)))
    hp = pose['hips']
    hips_pos, hips_rot = rig.head['hips'] + V(hp['pos']), euler(hp['rot'])
    J, R = torso_fk(rig, hips_pos, hips_rot, rot)
    for s, side, sg in (('L', 'left', 1), ('R', 'right', -1)):
        el, pr = pose.get('shoulder' + s, (0, 0))
        nsh = qaxis(Z, sg * el) @ qaxis(Y, -sg * pr)
        rot[f'{side}Shoulder'] = nsh
        spec = pose['arm' + s]
        if spec.get('space') == 'world':
            spec = world_to_torso(rig, spec, J, R)
        rot.update(solve_arm(rig, 'arm' + s, spec, nsh, diag))
        rot.update(hand_rots(rig, side, spec.get('hand', 'relaxed')))
    return dict(rot=rot, hips_pos=hips_pos, hips_rot=hips_rot, feet=pose['feet'],
                lock=(pose.get('lockL', 0.0), pose.get('lockR', 0.0)))


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


def clip(name, beats, loop, section, keys, lag=None, layers=(), base=STAND, notes='', lock=None, hang='', extra=None):
    lag = lag or {}
    if loop and name.endswith('_hold') and lag:
        # a _hold loop must START on the exact numbers its one-shot ended on: lagged bones read the loop's tail at
        # frame 0, so the tail holds a flat copy of the first key for the longest lag
        k0 = sorted(keys, key=lambda k: k[0])[0]
        keys = list(keys) + [(beats - max(lag.values()) - 0.05, k0[1], {'hold': True})]
    CLIPS[name] = dict(name=name, beats=beats, loop=loop, section=section, keys=keys, lag=lag,
                       layers=list(layers), base=base, notes=notes, lock=lock or {}, hang=hang, extra=extra or {})


def breath(period, amp=1.0, steady_head=False):
    """Inhale lifts the chest (extension) and the shoulders; the neck counters. One-sided (sin^2): zero AND
    zero-velocity at beat 0, so a loop starts exactly on its key pose. steady_head: the neck counters the whole
    inhale, so the face does not move at all (a gaze that holds the lens)."""
    def f(t):
        s = math.sin(math.pi * t / period) ** 2
        neck = (3.6 if steady_head else 2.0) * amp * s
        return {'chest': (-2.6 * amp * s, 0, 0), 'spine': (-1.0 * amp * s, 0, 0), 'neck': (neck, 0, 0),
                'leftShoulder': ('elev', 1.8 * amp * s), 'rightShoulder': ('elev', 1.8 * amp * s)}
    return f


def _bump(u, a, b):
    """0..1 pulse peaking at u = 0: rises over a beats before, falls over b after; C1 everywhere."""
    if -a < u <= 0:
        return math.cos(0.5 * math.pi * u / a) ** 2
    if 0 < u < b:
        return math.cos(0.5 * math.pi * u / b) ** 2
    return 0.0


def nods(at, every, head=4.0, neck=2.0, chest=0.8, dip=0.0, rise=0.32, fall=0.85):
    """Head nods landing ON beats at + k*every (the head is lowest on the beat), with an optional knee dip."""
    def f(t):
        u = (t - at + every / 2) % every - every / 2
        s = _bump(u, rise, fall)
        out = {'head': (head * s, 0, 0), 'neck': (neck * s, 0, 0), 'chest': (chest * s, 0, 0)}
        if dip:
            out['hips_pos'] = (0.0, -dip * s, 0.0)
        return out
    return f


def shoulder_roll(period, elev=3.5, prot=4.5, twist=2.0, phase=-0.5 * math.pi):
    """A slow backward roll (up, back, down, forward), the right shoulder half a cycle behind the left; the chest
    turns a little toward the shoulder that is going back."""
    def f(t):
        a = 2 * math.pi * t / period + phase
        return {'leftShoulder': ('roll', elev * math.sin(a), prot * math.cos(a)),
                'rightShoulder': ('roll', elev * math.sin(a + math.pi), prot * math.cos(a + math.pi)),
                'chest': (0, -twist * math.cos(a), 0)}
    return f


def arm(palm, normal, fingers, pole, hand=None, **kw):
    """An IK arm key: palm-surface point, palm facing, finger direction, elbow direction, hand shape."""
    d = {'palm': palm, 'normal': normal, 'fingers': fingers, 'pole': pole}
    if hand:
        d['hand'] = hand
    d.update(kw)
    return d


LAG_ARMS = {'LowerArm': 0.06, 'Hand': 0.12, 'fingers': 0.16, 'neck': 0.05, 'head': 0.1}


# ---------------------------------------------------------------- 1. turn_it_down (+ turn_it_down_hold)
# THE gesture of "could you turn it down?": the right hand comes up (the elbow leads, the forearm turning the
# palm down) to the bottom of the chest, IN FRONT of the drooping petals (their tips: z 0.23 at y 1.11-1.15),
# hangs a moment, then presses slowly down through something dense to the belt, the body sinking with it a
# centimetre; the head tilts toward the hand and leans down to watch it; the hand lets go, low and relaxed.
TID_TOP = dict(
    armR=arm((-0.080, 1.140, 0.385), (0.02, -1, 0.06), (0.30, -0.04, 0.95), (-0.80, -0.55, -0.25), 'press'),
    shoulderR=(0, 7), chest=(-3.5, -4, 1.3), spine=(0, -2, 1.2), neck=(3, -1, 1), head=(-2, -5, 6))
TID_LOW = dict(
    armR=arm((-0.125, 0.880, 0.300), (0.06, -1, 0.10), (0.26, -0.10, 0.96), (-0.60, -0.30, -0.70), 'press'),
    shoulderR=(-3, 5), chest=(0, -3, 1.3), spine=(1.5, -1.5, 1.2), neck=(5, -1, 1), head=(3, -4, 6.5),
    hips={'pos': (-0.012, -0.018, -0.004), 'rot': (0, 2, -2.0)})
TID_END = dict(
    armR=arm((-0.205, 0.790, 0.165), (0.80, -0.38, -0.46), (0.10, -0.80, 0.58), (-0.40, -0.10, -1.0), 'relaxed'),
    shoulderR=(-2, 4), chest=(-2, -2, 1.3), spine=(0.5, -1, 1.2), neck=(4, 0, 0.5), head=(0, -3, 4.5),
    hips={'pos': (-0.012, -0.010, -0.002), 'rot': (0, 2, -2.0)})
clip('turn_it_down', 4, False, 'every "could you turn it down?" (99.0, 109.2, 292.9, 303.2 s): the signature gesture',
     keys=[(0, {}),
           (0.55, dict(shoulderR=(-1, 5), chest=(-3, -2, 1.3), head=(-3, -2, 2),
                       armR=arm((-0.215, 0.930, 0.265), (0.55, -0.62, -0.56), (0.05, -0.20, 0.98), (-0.60, -0.70, -0.45), 'relaxed'))),
           (1.15, TID_TOP),
           (1.45, dict(TID_TOP, armR=arm((-0.080, 1.132, 0.383), (0.02, -1, 0.06), (0.30, -0.05, 0.95), (-0.80, -0.55, -0.25), 'press')), {'hold': True}),
           (3.05, TID_LOW),
           (4, TID_END)],
     lag={'LowerArm': 0.05, 'Hand': 0.12, 'fingers': 0.2, 'neck': 0.08, 'head': 0.16})
clip('turn_it_down_hold', 8, True, 'hold after turn_it_down (starts on its last frame): the room is quieter',
     keys=[(0, TID_END), (4, dict(TID_END, head=(1, -1.5, 2.5), neck=(4.5, 0, 0.5)))],
     lag={'neck': 0.15, 'head': 0.3}, layers=[breath(8, 1.0)], hang='LR')


# ---------------------------------------------------------------- 2. not_that (+ mirror)
# A calm "no": the right hand rises (elbow first) to shoulder height, the palm shown to the camera, fingers up,
# in front of the side petals; the head turns a little away (to her left) and lifts a hair; then the hand drops.
NOT_TOP = dict(
    armR=arm((-0.330, 1.290, 0.340), (-0.08, -0.36, 0.93), (0.10, 0.92, 0.38), (-0.45, -1, 0.10), 'stop'),
    shoulderR=(3, 5), chest=(-3, 4, 1.0), spine=(0, 1, 1.2), neck=(2, 4, 0), head=(-4, 8, -3))
clip('not_that', 2, False, 'pre-heard captions struck through; the final chorus "Not your god, not your engine..."',
     keys=[(0, {}),
           (0.45, dict(shoulderR=(0, 4), chest=(-2.5, 2, 1.2), head=(-3, 3, -2),
                       armR=arm((-0.300, 0.935, 0.200), (0.95, 0.15, -0.10), (0.10, -0.38, 0.92), (-0.70, -1, -0.25), 'soft'))),
           (0.68, dict(shoulderR=(2, 5), chest=(-3, 3.5, 1.1), head=(-4, 6.5, -2.8), neck=(2, 3, 0),
                       armR=arm((-0.322, 1.165, 0.318), (0.62, -0.45, 0.64), (0.06, 0.55, 0.83), (-0.50, -1, 0.0), 'soft'))),
           (0.95, NOT_TOP),
           (1.2, dict(NOT_TOP, head=(-4, 9, -3.5)), {'hold': True}),
           (2, {})],
     lag={'LowerArm': 0.04, 'Hand': 0.09, 'fingers': 0.12, 'neck': 0.05, 'head': 0.1})


# ---------------------------------------------------------------- 3. dark_groove
# The chorus groove at 93 BPM, low and slow: knees soft (the hips 3 cm down), the weight crosses to her left on
# beat 1, to her right on beat 3 (every two beats, the free heel peeling a little); the shoulders roll slowly
# backward, one after the other; the head nods on the backbeat (2 and 4) with a small knee dip; the arms hang
# loose and swing late. Small numbers on purpose: hypnotic, not bouncy.
def _groove(side, k=1.0):
    sg = 1 if side == 'L' else -1
    return {
        'hips': {'pos': (-0.004 + sg * 0.036 * k, -0.030, 0.004), 'rot': (2, sg * 3.0, sg * 2.8)},
        'spine': (1, sg * -1, sg * -4.0), 'chest': (-1, sg * 2.5, sg * -2.0), 'neck': (3, 0, sg * -0.5),
        'head': (-2, sg * 2.5, sg * -1.5),
        'armL': arm((0.246 + sg * 0.016, 0.700, 0.078 + sg * 0.012), (-0.84, 0.05, -0.48), (0.07 + sg * 0.08, -1, 0.16), (0.35, 0, -1)),
        'armR': arm((-0.244 + sg * 0.016, 0.704, 0.072 - sg * 0.012), (0.84, 0.05, -0.50), (-0.07 + sg * 0.08, -1, 0.14), (-0.35, 0, -1)),
        'feet': {'L': {'pos': (0.118, -0.022), 'yaw': 8.0, 'lift': 0.0 if sg > 0 else 3.5 * k},
                 'R': {'pos': (-0.112, -0.046), 'yaw': -6.0, 'lift': 3.5 * k if sg > 0 else 0.0}},
    }


clip('dark_groove', 8, True, 'the choruses in the hole (79.3, 174.9, 272.3 s): the darkwave groove',
     keys=[(0, _groove('L')), (2, _groove('R')), (4, _groove('L', 1.1)), (6, _groove('R', 1.1))],
     lag={'UpperArm': 0.14, 'LowerArm': 0.24, 'Hand': 0.34, 'fingers': 0.4, 'neck': 0.12, 'head': 0.22},
     layers=[nods(1.0, 2.0, head=4.0, neck=2.0, chest=0.8, dip=0.006), shoulder_roll(4.0, elev=5.0, prot=6.0, twist=3.0),
             breath(8, 0.6)], hang='LR')


# ---------------------------------------------------------------- 4. still_breathe
# The hush: almost nothing. One breath per bar, the head drifts a degree or two over two bars.
clip('still_breathe', 8, True, 'the hush: break 2 near-silence, the outro, anywhere the city goes quiet',
     keys=[(0, {}), (4, {'head': (-2, 2.5, -2.5), 'neck': (3, 0.5, 0), 'chest': (-2.3, -1, 1.4)})],
     lag={'neck': 0.12, 'head': 0.25}, layers=[breath(4, 0.85)], hang='LR',
     notes='same stance as every clip; use it as the neutral between gestures')


# ---------------------------------------------------------------- 5. look_up (+ look_up_hold)
# In the hole: the gaze lifts ~50 deg to the ring of billboards on the rim. The head leads, the neck and then
# the chest follow (the cervical spine does most of it), the pelvis tips back a hair to balance; the arms keep
# hanging by gravity (world-space hands, so the arching chest does not swing them forward).
UP_ARMS = dict(armL=arm((0.236, 0.700, 0.050), (-0.84, 0.05, -0.50), (0.06, -1, 0.10), (0.35, 0, -1), 'relaxed', space='world'),
               armR=arm((-0.234, 0.704, 0.044), (0.84, 0.05, -0.52), (-0.06, -1, 0.08), (-0.35, 0, -1), 'relaxed', space='world'))
LOOKUP = dict(UP_ARMS, hips={'pos': (-0.012, -0.010, 0.010), 'rot': (-2, 2, -2.0)},
              spine=(-4, -1, 1.0), chest=(-8, -1, 1.0), neck=(-13, 0, 0), head=(-23, 1, -1.5),
              shoulderL=(-1, -2), shoulderR=(-1, -2))
clip('look_up', 4, False, 'the hole: looking up at the ring of billboards on the rim (~50 deg up); the outro "she looks up"',
     keys=[(0, {}),
           (0.6, dict(UP_ARMS, neck=(4, 0, 0), head=(0, 1, -1.5), chest=(-2.5, -1, 1.3))),
           (2.9, dict(LOOKUP, neck=(-14, 0, 0), head=(-24.5, 1.5, -2), chest=(-8.5, -1, 1.0))),
           (4, LOOKUP)],
     lag={'chest': 0.12, 'spine': 0.18, 'neck': 0.06, 'head': 0.0, 'LowerArm': 0.1, 'Hand': 0.2, 'fingers': 0.25})


def _ring(az, el=0.0):
    """The look-up pose turned az deg around the ring (+ = toward her left), elevation nudged by el deg."""
    return dict(LOOKUP, hips={'pos': (-0.012, -0.010, 0.010), 'rot': (-2, 2 + 0.10 * az, -2.0)},
                spine=(-4, -1 + 0.12 * az, 1.0), chest=(-8 - 0.3 * el, -1 + 0.20 * az, 1.0),
                neck=(-13 - 0.4 * el, 0.22 * az, 0), head=(-23 - 0.3 * el, 1 + 0.36 * az, -1.5 - 0.05 * az))


clip('look_up_hold', 8, True, 'hold after look_up (starts on its last frame): the gaze travels round the ring',
     keys=[(0, LOOKUP), (2, _ring(34, 1)), (4, _ring(2, -1)), (6, _ring(-30, 1.5))],
     lag={'chest': 0.12, 'spine': 0.2, 'neck': 0.08, 'head': 0.0}, layers=[breath(8, 0.9)], hang='LR')


# ---------------------------------------------------------------- 6. salute_abort
# The gold corridor, the cap just placed on her: the right hand flattens into the salute blade and starts up,
# elbow out, toward the brim... and stops at the chest (in front of the petals), palm down, the blade pointing
# up to the brow it will not reach. It hangs there a beat; the head tilts, a thought; the fingers lose their
# line; the hand lowers back to her side, unhurried. Ends exactly on STAND.
SAL_HALF = dict(
    armR=arm((-0.140, 1.200, 0.310), (0.25, -0.55, -0.80), (0.45, 0.75, 0.48), (-1.0, -0.45, -0.05), 'salute'),
    shoulderR=(4, 5), chest=(-4, -2, 1.3), spine=(-0.5, -1, 1.2), neck=(1, 0, 0), head=(-5, 0, -0.5))
clip('salute_abort', 6, False, 'verse 2, the gold corridor: the cap is placed, the salute starts and is not finished',
     keys=[(0, {}),
           (0.5, dict(shoulderR=(-1, 3), chest=(-3.5, -1.5, 1.3), head=(-4, 0.5, -1),
                      armR=arm((-0.250, 0.740, 0.110), (0.72, 0.0, -0.69), (-0.05, -1, 0.20), (-0.55, 0, -1), 'flat'))),
           (1.05, dict(shoulderR=(2, 4), chest=(-4, -2, 1.3), head=(-5, 0, -0.5),
                       armR=arm((-0.235, 0.990, 0.255), (0.30, -0.90, -0.30), (0.45, -0.22, 0.87), (-1.0, -0.6, -0.1), 'salute'))),
           (1.55, SAL_HALF),
           (2.6, dict(SAL_HALF, head=(-3, 2, 3.5), neck=(2, 1, 1)), {'hold': True}),
           (3.1, dict(SAL_HALF, head=(-2, 3, 4.5), neck=(2.5, 1, 1.5), chest=(-3, -2, 1.3),
                      armR=arm((-0.145, 1.180, 0.305), (0.22, -0.60, -0.77), (0.45, 0.68, 0.58), (-1.0, -0.5, -0.05), 'press'))),
           (4.6, dict(shoulderR=(-1, 4), chest=(-2.5, -1.5, 1.3), head=(-2, 2, 2), neck=(3, 0.5, 0.5),
                      armR=arm((-0.235, 0.860, 0.190), (0.72, -0.30, -0.62), (0.12, -0.78, 0.62), (-0.55, -0.2, -1), 'relaxed'))),
           (6, {})],
     lag={'LowerArm': 0.06, 'Hand': 0.13, 'fingers': 0.2, 'neck': 0.1, 'head': 0.2})


# ---------------------------------------------------------------- 7. fence_hands (+ fence_hands_hold)
# The evening news: she stands on the other side of the fence. No step: both hands come up IN FRONT of the
# petals and hook into a chain-link mesh at shoulder height, 0.30 m (film) in front of her chest; the head goes
# slightly down. The fence plane is z = FENCE_Z (rig metres; film z = 0.87 * FENCE_Z). The palms sit 2 cm behind
# the wire plane, the curled fingers go through it. From the contact on, both hands are LOCKED to these world
# points every frame, so the breathing body moves around fixed hands.
CHEST_FRONT = 0.083                       # the tuta's chest surface (rig z, measured from the mesh)
FENCE_Z = round(CHEST_FRONT + 0.30 / 0.87, 3)          # 0.428
FENCE_L = arm((0.235, 1.240, FENCE_Z - 0.020), (-0.06, -0.40, 0.91), (-0.14, 0.89, 0.43), (0.40, -1, -0.15), 'hook', space='world')
FENCE_R = arm((-0.240, 1.235, FENCE_Z - 0.020), (0.06, -0.40, 0.91), (0.14, 0.89, 0.43), (-0.40, -1, -0.15), 'hook', space='world')
FENCE = dict(armL=FENCE_L, armR=FENCE_R, lockL=1.0, lockR=1.0,
             hips={'pos': (-0.010, -0.010, -0.012), 'rot': (1, 2, -1.5)},
             spine=(1, -1, 1.0), chest=(1, -1, 1.0), neck=(4, 0, 0), head=(2.5, 1, 1.5),
             shoulderL=(1, 8), shoulderR=(1, 8))
FENCE_INFO = {'fence': {
    'plane_z_rig': FENCE_Z, 'plane_z_film': round(FENCE_Z * 0.87, 4),
    'palm_L_film': [round(v * 0.87, 4) for v in FENCE_L['palm']], 'palm_R_film': [round(v * 0.87, 4) for v in FENCE_R['palm']],
    'note': 'film metres at scale 0.87, her origin = the floor between her feet, facing +z; palms 2 cm (rig) behind '
            'the wire plane, curled fingers through it; the hands at the top of the chest, just under the shoulder line '
            '(her face hangs between the shoulders: any higher and the hooked fingers cover her mouth from the front)'}}
clip('fence_hands', 3, False, 'verse 5, the evening news: her hands on the data-centre fence (fence plane in the README)',
     keys=[(0, {}),
           (0.45, dict(shoulderL=(-1, 4), shoulderR=(-1, 4), chest=(-3, -1, 1.3), head=(-3, 1, -1),
                       armL=arm((0.255, 0.860, 0.200), (-0.70, 0.30, 0.65), (0.05, -0.2, 0.98), (0.55, -0.6, -0.6), 'soft'),
                       armR=arm((-0.255, 0.865, 0.195), (0.70, 0.30, 0.65), (-0.05, -0.2, 0.98), (-0.55, -0.6, -0.6), 'soft'))),
           (1.25, dict(shoulderL=(1, 7), shoulderR=(1, 7), chest=(-1, -1, 1.2), head=(0, 1, 0), neck=(4, 0, 0),
                       armL=arm((0.245, 1.090, 0.370), (-0.05, -0.90, 0.42), (-0.06, 0.40, 0.91), (0.45, -1, -0.25), 'soft', space='world'),
                       armR=arm((-0.250, 1.085, 0.365), (0.05, -0.90, 0.42), (0.06, 0.40, 0.91), (-0.45, -1, -0.25), 'soft', space='world'))),
           (1.95, dict(FENCE, lockL=0.6, lockR=0.6, head=(1, 1, 1), neck=(3, 0, 0),
                       armL=dict(FENCE_L, hand='float'), armR=dict(FENCE_R, hand='float'))),
           (3, FENCE)],
     lag={'LowerArm': 0.05, 'Hand': 0.1, 'fingers': 0.22, 'neck': 0.1, 'head': 0.2},
     lock={'L': FENCE_L, 'R': FENCE_R}, extra=FENCE_INFO)
clip('fence_hands_hold', 8, True, 'hold after fence_hands (starts on its last frame): hands hooked, she breathes',
     keys=[(0, FENCE), (4, dict(FENCE, head=(4, -2, 2.5), neck=(4.5, -0.5, 0.5), hips={'pos': (-0.006, -0.011, -0.014), 'rot': (1, 1, -1.0)}))],
     lag={'neck': 0.15, 'head': 0.3}, layers=[breath(8, 1.3)], lock={'L': FENCE_L, 'R': FENCE_R}, extra=FENCE_INFO)


# ---------------------------------------------------------------- 8. ask_me (+ ask_me_hold)
# "Ask me something. Then wait." in my own voice: a small open palm offered toward the camera at belly height
# (the forearm forward, the elbow by her side), then nothing moves but the breath; the face holds the lens
# (head square to a camera at +z, no tilt, no turn; the breath is countered in the neck).
ASK = dict(armR=arm((-0.120, 0.985, 0.305), (0.10, 0.80, 0.59), (0.22, -0.12, 0.97), (-0.45, -1, -0.35), 'offer', space='world'),
           shoulderR=(-2, 5), chest=(-2, 0, 0.5), spine=(0, 0, 0.6), neck=(3, 0, 0), head=(-1, 0, 0),
           hips={'pos': (-0.012, -0.006, 0.0), 'rot': (0, 1, -2.0)})
clip('ask_me', 4, False, 'break 2 (~269-272 s): "Ask me something. Then wait." in my homemade voice; the quietest picture',
     keys=[(0, {}),
           (0.5, dict(chest=(-3, -0.5, 0.8), neck=(3, 0, 0), head=(-1.5, 0.5, -0.5),
                      armR=arm((-0.215, 0.835, 0.190), (0.70, 0.30, -0.60), (0.08, -0.45, 0.88), (-0.45, -0.6, -0.7), 'relaxed', space='world'))),
           (1.5, dict(ASK, armR=arm((-0.122, 0.992, 0.310), (0.10, 0.80, 0.59), (0.22, -0.10, 0.97), (-0.45, -1, -0.35), 'offer', space='world'))),
           (2.2, ASK, {'hold': True}),
           (4, ASK)],
     lag={'LowerArm': 0.06, 'Hand': 0.14, 'fingers': 0.22, 'neck': 0.06, 'head': 0.1})
clip('ask_me_hold', 8, True, 'hold after ask_me (starts on its last frame): stillness, the breath, the gaze on the lens',
     keys=[(0, ASK), (4, ASK)], layers=[breath(8, 0.9, steady_head=True)], hang='LR')


# ---------------------------------------------------------------- 9. sing_low (+ mirror)
# A verse gesture, small: the right hand at belly height turns palm UP and open on beat 1, slowly turns over and
# closes into a loose cup by beat 3, opens and turns up again for the next bar. The left arm hangs. The head
# moves a degree with the phrase.
def _sing(turn, close, y, z, head):
    up = Vector((0.12, 0.95, 0.28)).normalized()
    over = Vector((0.80, -0.10, -0.59)).normalized()
    n = (up * (1 - turn) + over * turn).normalized()
    f = Vector((0.40 - 0.10 * turn, -0.06 - 0.18 * turn, 0.91)).normalized()
    return dict(armR=arm((-0.140 + 0.025 * turn, y - 0.015, z - 0.030), tuple(n), tuple(f), (-0.40, -1, -0.45),
                         'offer' if close < 0.5 else 'cup'),
                head=head, chest=(-2, -2.5 + 1.0 * turn, 1.3), neck=(3, -0.5, 0))


clip('sing_low', 4, True, 'the verses: a sung line, the hand opening on beat 1 and closing on beat 3',
     keys=[(0, _sing(0.0, 0, 0.975, 0.270, (-3.5, -1.5, -2.5))),
           (1, _sing(0.30, 0, 0.968, 0.262, (-3, -1, -2))),
           (2, _sing(1.0, 1, 0.950, 0.240, (-1.5, 0, -1.5))),
           (3, _sing(0.55, 0, 0.962, 0.255, (-2.5, -1, -2)))],
     lag={'LowerArm': 0.08, 'Hand': 0.16, 'fingers': 0.24, 'neck': 0.1, 'head': 0.2}, layers=[breath(4, 0.5)], hang='L')


# ---------------------------------------------------------------- mirrors: the same performance with the other hand
# Mirrored at the POSE level: arms and shoulders swap sides with x negated, the torso's and hips' turn/tilt flip,
# locks swap, the peeling heel swaps, but the FEET KEEP THE STANCE (crossfades never slide).
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
        elif k in ('lockL', 'lockR'):
            out['lockR' if k == 'lockL' else 'lockL'] = v
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
                       lock={('R' if s == 'L' else 'L'): mirror_pose({'armL': v})['armR'] for s, v in c['lock'].items()},
                       hang=''.join('R' if s == 'L' else 'L' for s in c['hang']),
                       section=f"mirror of {src}: the other hand, toward her other side (same stance)", notes='', extra={})


mirror_clip('not_that', 'not_that_mirror')
mirror_clip('sing_low', 'sing_low_mirror')


# ---------------------------------------------------------------- test rig for the new hand shapes (--clips zz_hands)
_SHOW = {'armL': {'palm': (0.16, 1.16, 0.34), 'normal': (0, 0.1, 1), 'fingers': (0.1, 1, 0.1), 'pole': (0.6, -1, -0.2)},
         'armR': {'palm': (-0.16, 1.16, 0.34), 'normal': (0, 0.1, 1), 'fingers': (-0.1, 1, 0.1), 'pole': (-0.6, -1, -0.2)}}
_HK = []
for _i, (_l, _r) in enumerate((('hook', 'salute'), ('offer', 'cup'), ('press', 'stop'))):
    _p = merge(_SHOW, {'armL': {'hand': _l}, 'armR': {'hand': _r}})
    _HK += [(_i * 2, _p, {'hold': True}), (_i * 2 + 1.9, _p, {'hold': True})]
clip('zz_hands', 6, False, 'test', notes='hand shapes: hook|salute, offer|cup, press|stop', keys=_HK)


# ============================================================================ sampling + baking
def lagged(t, lag, clipd):
    if clipd['loop']:
        return (t - lag) % clipd['beats']
    # one-shots: the lag fades out over the last beat, so every bone lands on the final key on the final frame
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
    REPORT.append(f"[{c['name']}] {c['beats']} beats {'loop' if c['loop'] else 'one-shot'} = {c['beats'] * BEAT:.5f} s")
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
    ch['_lock'] = Channel(times, [Vector(p['lock']) for p in poses], P, holds)
    return ref, ch, poses


def sample(rig, c, ref, ch, poses, t):
    rot = {}
    for h in ref['rot']:
        tt = lagged(t, bone_lag(h, c['lag']), c)
        rot[h] = ref['rot'][h] @ qexp(ch[h](tt))
    hips_pos = ch['_hips_pos'](lagged(t, 0, c))
    hips_rot = qexp(ch['_hips_rot'](lagged(t, 0, c)))
    pre = {b: rot[b].copy() for b in ('spine', 'chest', 'leftShoulder', 'rightShoulder')}
    pre_hips = hips_rot.copy()
    extra_hips = Vector((0, 0, 0))
    for layer in c['layers']:
        for b, e in layer(t).items():
            if b == 'hips_pos':
                extra_hips += V(e)
            elif b == 'hips_rot':
                hips_rot = hips_rot @ euler(e)
            elif isinstance(e, tuple) and len(e) >= 2 and e[0] == 'elev':
                sg = 1 if b.startswith('left') else -1
                rot[b] = rot[b] @ qaxis(Z, sg * e[1])
            elif isinstance(e, tuple) and len(e) == 3 and e[0] == 'roll':
                sg = 1 if b.startswith('left') else -1
                rot[b] = rot[b] @ (qaxis(Z, sg * e[1]) @ qaxis(Y, -sg * e[2]))
            else:
                rot[b] = rot[b] @ euler(e)
    hips_pos = hips_pos + extra_hips
    # hanging arms: undo what the layers did to the chain above the upper arm (world orientation kept)
    for s, side in (('L', 'left'), ('R', 'right')):
        if s in c['hang']:
            A0 = pre_hips @ pre['spine'] @ pre['chest'] @ pre[f'{side}Shoulder']
            A1 = hips_rot @ rot['spine'] @ rot['chest'] @ rot[f'{side}Shoulder']
            rot[f'{side}UpperArm'] = A1.inverted() @ A0 @ rot[f'{side}UpperArm']
    # world-locked arms: re-solve the IK in this frame's torso, blend by the lock weight
    lock = ch['_lock'](lagged(t, 0, c))
    if c['lock']:
        J, R = torso_fk(rig, hips_pos, hips_rot, rot)
        for i, (s, side) in enumerate((('L', 'left'), ('R', 'right'))):
            w = max(0.0, min(1.0, lock[i]))
            if w <= 1e-4 or s not in c['lock']:
                continue
            spec = world_to_torso(rig, c['lock'][s], J, R)
            sol = solve_arm(rig, 'arm' + s, spec, rot[f'{side}Shoulder'], None)
            for b, q in sol.items():
                rot[b] = q if w >= 0.9999 else rot[b].slerp(q, w)
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
    nf = int(round(c['beats'] * SPB))
    act = bpy.data.actions.new(c['name'])
    arm_ = rig.arm
    arm_.animation_data_create()
    arm_.animation_data.action = act
    series = {h: [] for h in rig.bones}
    hips_loc = []
    worst = 0.0
    for f in range(nf + 1):
        t = f / SPB
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
        pb = arm_.pose.bones[rig.hb[h]]
        pb.rotation_mode = 'QUATERNION'
        path = pb.path_from_id('rotation_quaternion')
        for i in range(4):
            fc = act.fcurve_ensure_for_datablock(arm_, path, index=i)
            co = []
            for f, q in enumerate(series[h]):
                co += [float(f), q[i]]
            fc.keyframe_points.add(nf + 1)
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [1] * (nf + 1))   # LINEAR (the exporter samples whole frames)
            fc.update()
    path = arm_.pose.bones[rig.hb['hips']].path_from_id('location')
    for i in range(3):
        fc = act.fcurve_ensure_for_datablock(arm_, path, index=i)
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
    sc.render.fps, sc.render.fps_base = SPB, BEAT     # frame -> seconds = frame * BEAT / SPB: beat k = frame SPB*k
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
    rig = Rig()
    man_path = os.path.join(HERE, 'clips.json')
    manifest = json.load(open(man_path, encoding='utf-8')) if os.path.exists(man_path) else {}
    os.makedirs(os.path.join(REPO, 'work'), exist_ok=True)
    rep_path = os.path.join(REPO, 'work', 'vrma_build_report_uf.txt')
    old = {}
    if want and os.path.exists(rep_path):              # partial build: keep the other clips' report sections
        cur = None
        for line in open(rep_path, encoding='utf-8').read().splitlines():
            if line.startswith('[') and '] ' in line:
                cur = line[1:line.index(']')]
            if cur:
                old.setdefault(cur, []).append(line)
    for name, c in CLIPS.items():
        if (want and name not in want) or (not want and name.startswith('zz_')):
            continue
        act, nf = bake(rig, c)
        path = export(rig, c, act, nf)
        if name.startswith('zz_'):
            continue
        manifest[name] = dict(file=f'{REL}/{name}.vrma', beats=c['beats'], seconds=round(c['beats'] * BEAT, 5),
                              loop=c['loop'], section=c['section'], notes=c['notes'], samples=nf + 1,
                              bpm=round(BPM, 3), **c.get('extra', {}))
        print(f'[build_vrma] {name}: {nf + 1} samples, {c["beats"]} beats = {c["beats"] * BEAT:.5f} s -> {path}')
    manifest = dict(sorted(manifest.items()))
    with open(man_path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2)
    built = set()
    lines = []
    cur = None
    for line in REPORT:
        if line.startswith('[') and '] ' in line:
            cur = line[1:line.index(']')]
            built.add(cur)
        lines.append(line)
    for name, ls in old.items():
        if name not in built and name in CLIPS:
            lines += ls
    with open(rep_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    for line in REPORT:
        print('[report] ' + line)
    if '--save-blend' in argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(REPO, 'work', 'claudesona_uf_performance.blend'))


main()
