"""eidoblend.characters.robot_dof: my robot body's hardware DOF, ported from eidoverse/claude_robot_dof.js.

Retargeted human clips write full three-axis rotations into every humanoid bone, but my knees and toes are single pins,
my ankles a pitch + roll cardan with no yaw, my hips, shoulders, wrists and thumbs stages. Each frame, after the clip and
before the frame is keyed, this projects every listed bone's NORMALIZED rotation onto the joint's real degrees of freedom
and clamps it to the joint's range. The tables, axes and Euler orders are the WebGPU module's, literally: the maths runs
in three's normalized frame (VRM 1.0: +X my left, +Y up, +Z forward), on a dict

    pose = {'leftUpperLeg': Quaternion(...), ...}        # three's frame; vrm.VRMHandle.read_pose / write_pose convert

so every comment in claude_robot_dof.js about a sign or a range holds here. The JS keeps each actuator's state in a
per-VRM WeakMap; here the state is an object made once at load and passed first. The whole module, name for name:

    LEG_JOINTS, HEAD_RANGE, SPINE_RANGE, ARM, LEG_CLEARANCE, ARM_POSE_BONES, PETAL_A, PETAL_FOLD, STEM_LOCK,
    CROWN_STATES, HEAD_STATES                                  the tables, as the JS exports them
    rehome_body(pose, stats)                                   [rehomeBody]
    apply_hardware_dof(pose, joints, legs, stats)              [applyHardwareDOF] (+ the hip stages when legs is given)
    init_leg_dof(h) -> LegStages                               [initLegDOF]
    apply_leg_clearance(clear, pose, hips_pos, stats, dt, width, legs)  [applyLegClearance]; clear = LegClearance(h)
                                                               (initLegClearance at load; clear.reset() for a cut)
    apply_arm_clearance(pose, deg)                             [applyArmClearance]
    init_arm_dof(h, hinges) -> ArmDOF                          [initArmDOF] (the wrist's stages read here: initWrist)
    apply_arm_dof(arms, pose, dt, clearance, stats)            [applyArmDOF] (the wrist's three stages: wrist_solve)
    wrist_dev_range(flexion_deg)                               [wristDevRange]
    wrist_solve(q, W)                                          [wristSolve]
    keep_arm_pose(arms, pose) / restore_arm_pose(arms, pose)   [keepArmPose / restoreArmPose]
    reset_arm_dof(arms, side)                                  [resetArmDOF]
    init_hand_dof(h, hinges) -> HandDOF                        [initHandDOF]
    apply_hand_dof(hands, pose, stats)                         [applyHandDOF]: the finger pins, the little finger's
                                                               shared limit, the thumb's rotor + CMC pin, MCP and IP
    hand_debug(hands)                                          [handDebug]
    init_head_expression() / apply_head_expression(...)       [applyHeadExpression]
    init_crown() / apply_crown(...)                            [initCrown / applyCrown]

The stages a solve sets but no humanoid bone carries (the hip pitch and swing, the shoulder pitch, the wrist roll and
flex, the thumb rotor, the petals) come back as turns for the keyer (LegStages.out, ArmDOF.helper_phi / wrist_out,
HandDOF.rotor_out, Crown.phi): a turn in the VRM's own frame against the bone's rest, which VRMHandle.basis_from_normalized
writes into the pose bone (eidoblend.characters.robot.rig keys them all). Their VRM node constraints, which the add-on
imports as COPY_ROTATION / DAMPED_TRACK, are muted for the stages the solve owns, as the JS deletes them.
"""

import math

from mathutils import Matrix, Quaternion, Vector

from ._math import (D2R, R2D, angle_about, clamp, euler_from_quat, lerp_table, quat_from_euler, smooth, twist_about,
                    v_to_three, wrap_pi)

SIDES = ('left', 'right')

# ------------------------------------------------------------------------------------------------------------- the legs
# (the measured ranges and the coupled tables: claude_robot_dof.js LEG_JOINTS, with its comments' provenance)
LEG_JOINTS = [
    {'bone': 'UpperLeg', 'type': 'ball', 'range': {'x': (-98, 23), 'z': (-14, 44), 'y': (-40, 40)},
     'coupled': {
         'x': [-98, -95, -90, -85, -80, -77.5, -75, -72.5, -70, -67.5, 0, 5, 10, 15, 20, 23],
         'zmin': [-0.5, -1.5, -3, -5, -7.5, -9.25, -10.75, -12.5, -14, -14, -14, -14, -14, -14, -14, -14],
         'zmax': [21, 21.5, 22.75, 25.5, 28, 29, 29.75, 30.75, 30.75, 44, 44, 40.75, 34.5, 28.5, 23, 19.5],
         'z': [0, 15, 19.5, 23, 30, 37.5, 44],
         'ymin': [-40, -40, -31.75, -21.25, -14, -9.25, -5.5]}},
    {'bone': 'LowerLeg', 'type': 'hinge', 'axis': (1.0, 0.0, 0.0), 'range': (0, 112)},
    {'bone': 'Foot', 'type': 'cardan', 'noTwist': (0.0, 1.0, 0.0), 'range': {'x': (-26.9, 30.9), 'z': (-14.9, 14.9)},
     'coupled': {
         'x': [-26.9, -26.4, -25.9, -22.9, 28.15, 28.4, 28.9, 29.9, 30.4, 30.9],
         'zmin': [-3.75, -6.25, -8.25, -14.9, -14.9, -14.5, -11.5, -7.25, -4.75, -3],
         'zmax': [10.5, 13.25, 14.9, 14.9, 14.9, 14, 12.5, 8.5, 6.5, 4.5]}},
    {'bone': 'Toes', 'type': 'hinge', 'axis': (1.0, 0.0, 0.0), 'range': (-41, 0)},
]
HEAD_RANGE = {'pan': (-60, 60), 'x': (-30, 30), 'z': (-11, 11)}
SPINE_RANGE = {'x': (-25, 25), 'z': (-15, 15), 'y': (-20, 20)}


def _note(stats, k, before, after):
    if stats is not None:
        d = 2.0 * math.acos(min(1.0, abs(before.dot(after)))) * R2D
        stats[k] = max(stats.get(k, 0.0), d)


def _aa(axis, ang):
    """three's Quaternion.setFromAxisAngle: the axis as given (three does not normalise it; the joints file's axes are
    rounded to 6 digits, so a pin's turn is unit to ~1e-6, as in the WebGPU edition)"""
    s = math.sin(0.5 * ang)
    return Quaternion((math.cos(0.5 * ang), axis[0] * s, axis[1] * s, axis[2] * s))


def _unit_vectors(a, b):
    """three's Quaternion.setFromUnitVectors(a, b) (a, b unit), its antiparallel branch included"""
    r = a.dot(b) + 1.0
    if r < 1e-8:
        r = 0.0
        if abs(a.x) > abs(a.z):
            q = Quaternion((r, -a.y, a.x, 0.0))
        else:
            q = Quaternion((r, 0.0, -a.z, a.y))
    else:
        c = a.cross(b)
        q = Quaternion((r, c.x, c.y, c.z))
    return q.normalized()


def _mirror(q, m):
    """the right side in the left's frame and back: the x -> -x mirror conjugates a turn (its axis (x, -y, -z))"""
    return q.copy() if m > 0 else Quaternion((q.w, q.x, -q.y, -q.z))


def _same64(a, b):
    """the JS's 'the same turn' test, |a . b| > 1 - 1e-12, in double precision with both normalised first. mathutils is
    single precision: its own dot of two equal unit quaternions reads 1 +- 1.2e-7, so the JS's literal test would fire for
    any two turns within ~0.06 deg of each other (or never), where the WebGPU edition means a repeated input"""
    na = math.sqrt(a.w * a.w + a.x * a.x + a.y * a.y + a.z * a.z)
    nb = math.sqrt(b.w * b.w + b.x * b.x + b.y * b.y + b.z * b.z)
    return abs(a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z) / (na * nb) > 1 - 1e-12


# double-precision vector maths for the solves whose minimum is flat (the thumb's grid search), as the JS's arrays:
# single-precision noise in a cost of order 1e-7 would otherwise pick a neighbouring grid step
def _d(v):
    return (float(v[0]), float(v[1]), float(v[2]))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _rot(v, k, t):
    """v turned by t about the unit axis k (Rodrigues), as the JS's vrot"""
    c, s = math.cos(t), math.sin(t)
    kv, kd = _cross(k, v), _dot(k, v) * (1 - c)
    return (v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd)


def _qrot(q, v):
    """v turned by the quaternion q (w, x, y, z), in double precision"""
    w, x, y, z = float(q.w), float(q.x), float(q.y), float(q.z)
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx)


def _angle_about64(q, a):
    """angle_about in double precision: the signed twist of q about the unit axis a"""
    p = float(q.x) * a[0] + float(q.y) * a[1] + float(q.z) * a[2]
    tw = (float(q.w), a[0] * p, a[1] * p, a[2] * p)
    n = math.sqrt(sum(c * c for c in tw))
    if n < 1e-9:
        return 0.0
    tw = [c / n for c in tw]
    return wrap_pi(2.0 * math.atan2(tw[1] * a[0] + tw[2] * a[1] + tw[3] * a[2], tw[0]))


def rehome_body(pose, stats=None):
    """the torso rigid above the waist bellows, the clavicles into the upper arms, the neck/head split into its stages"""
    def note(k, q):
        if stats is not None:
            stats[k] = max(stats.get(k, 0.0), 2.0 * math.acos(min(1.0, abs(q.w))) * R2D)
    spine = pose.get('spine')
    if spine is not None:
        for n in ('chest', 'upperChest'):
            q = pose.get(n)
            if q is None:
                continue
            note('rehome_' + n, q)
            spine = spine @ q
            pose[n] = Quaternion()
        x, y, z = euler_from_quat(spine, 'XZY')
        x = clamp(x * R2D, *SPINE_RANGE['x']) * D2R
        z = clamp(z * R2D, *SPINE_RANGE['z']) * D2R
        y = clamp(y * R2D, *SPINE_RANGE['y']) * D2R
        pose['spine'] = quat_from_euler(x, y, z, 'XZY')
    for side in SIDES:
        sh, ua = pose.get(side + 'Shoulder'), pose.get(side + 'UpperArm')
        if sh is None or ua is None:
            continue
        note('rehome_' + side + 'Shoulder', sh)
        pose[side + 'UpperArm'] = sh @ ua
        pose[side + 'Shoulder'] = Quaternion()
    neck, head = pose.get('neck'), pose.get('head')
    if neck is not None and head is not None:
        x, y, z = euler_from_quat(neck @ head, 'YXZ')
        pan = clamp(y * R2D, *HEAD_RANGE['pan']) * D2R
        nod = clamp(x * R2D, *HEAD_RANGE['x']) * D2R
        roll = clamp(z * R2D, *HEAD_RANGE['z']) * D2R
        pose['neck'] = Quaternion((0.0, 1.0, 0.0), pan)
        pose['head'] = quat_from_euler(nod, 0.0, roll, 'XZY')


def project_joint(q, j, m):
    """one joint's projection (applyHardwareDOF's body), in the left leg's signs (m = +1 left, -1 right) -> Quaternion"""
    def cd(v, r):
        return clamp(v * R2D, r[0], r[1]) * D2R
    if j['type'] == 'hinge':
        ang = angle_about(q, j['axis'])
        return Quaternion(Vector(j['axis']), cd(ang, j['range']))
    if j['type'] == 'cardan':
        tw = twist_about(q, j['noTwist'])
        sw = q @ tw.inverted()
        x, y, z = euler_from_quat(sw, 'XZY')
        x = cd(x, j['range']['x'])
        rz = j['range']['z'] if m > 0 else (-j['range']['z'][1], -j['range']['z'][0])
        z = cd(z, rz)
        c = j.get('coupled')
        if c:
            xd = x * R2D
            zz = min(lerp_table(c['x'], c['zmax'], xd), max(lerp_table(c['x'], c['zmin'], xd), m * z * R2D))
            z = m * zz * D2R
        return quat_from_euler(x, 0.0, z, 'XZY')
    if j['type'] == 'ball':
        x, y, z = euler_from_quat(q, 'XZY')
        r, c = j['range'], j.get('coupled')
        xd = clamp(x * R2D, *r['x'])
        zd = clamp(m * z * R2D, *r['z'])
        yd = clamp(m * y * R2D, *r['y'])
        if c:
            zd = clamp(zd, lerp_table(c['x'], c['zmin'], xd), lerp_table(c['x'], c['zmax'], xd))
            yd = max(yd, lerp_table(c['z'], c['ymin'], zd))
        return quat_from_euler(xd * D2R, m * yd * D2R, m * zd * D2R, 'XZY')
    raise ValueError(j['type'])


def apply_hardware_dof(pose, joints=LEG_JOINTS, legs=None, stats=None):
    """every listed joint projected and clamped, both sides; then the hip's two stages (legs: a LegStages, or None)"""
    for side in SIDES:
        m = 1 if side == 'left' else -1
        for j in joints:
            k = side + j['bone']
            q = pose.get(k)
            if q is None:
                continue
            out = project_joint(q, j, m)
            _note(stats, k, q, out)
            pose[k] = out
        if legs is not None and legs.sides.get(side) is not None and (side + 'UpperLeg') in pose:
            legs.solve(side, pose[side + 'UpperLeg'])


def _vrot(v, k, t):
    c, s = math.cos(t), math.sin(t)
    v, k = Vector(v), Vector(k)
    return v * c + k.cross(v) * s + k * (k.dot(v) * (1.0 - c))


def _mute(h, bone, mute):
    n = 0
    if mute and bone in h.arm.pose.bones:
        for c in h.arm.pose.bones[bone].constraints:
            if not c.mute:
                c.mute = True
                n += 1
    return n


class LegStages:
    """THE HIP'S STAGES (initLegDOF + hipSolve): the ball (HipPitch) turns about the cross axle XP, the roll flange
    (HipSwing) about the roll axle ZR it carries, the yaw ring takes what is left (a turn about the thigh's own axis d0).
    Both stages are solved from the clamped thigh each frame; their VRM node constraints are muted (the file keeps them for
    runtimes without robot_dof). The axes are read at load from the stage bones' glTF node frames (the handle's node_frame),
    in three's normalized frame. After solve(side, q), self.out[side] = {'pitch': Quaternion, 'swing': Quaternion} (three's
    frame, each the stage's turn in the VRM-aligned frame: the handle writes them as normalized-style turns).
    (initLegDOF's guard against a second call or a posed VRM does not apply: these records read the bones' REST frames,
    never the pose, so a second call reads the same.)"""

    def __init__(self, sides):
        self.sides = sides
        self.out = {}

    @classmethod
    def from_handle(cls, h, mute=True):
        sides = {}
        for side in SIDES:
            pb, sb = side + 'HipPitch', side + 'HipSwing'
            bones = h.arm.data.bones
            if pb not in bones or sb not in bones or bones[sb].parent is None or bones[sb].parent.name != pb \
                    or bones[pb].parent is None:
                sides[side] = None
                continue
            Ps, Ws = h.node_frame_three(pb), h.node_frame_three(sb)
            XP = (Ps @ Vector((1, 0, 0))).normalized()
            ZR = (Ps @ Vector((0, 0, 1))).normalized()
            d0 = (Ws @ Vector((0, 1, 0))).normalized()
            muted = _mute(h, pb, mute) + _mute(h, sb, mute)
            aim = None
            up, lo = h.humanoid.get(side + 'UpperLeg'), h.humanoid.get(side + 'LowerLeg')
            if up and lo:
                k = v_to_three(h.rest_head[lo] - h.rest_head[up])
                aim = math.atan2(k.cross(d0).length, k.dot(d0)) * R2D
            sides[side] = {'pitch_bone': pb, 'swing_bone': sb, 'XP': XP, 'ZR': ZR, 'd0': d0, 'A': XP.dot(d0),
                           'B': XP.dot(ZR.cross(d0)), 'muted': muted, 'removed': muted, 'a': 0.0, 'b': 0.0, 'c': 0.0,
                           'aimDeg': aim, 'leanDeg': math.asin(min(1.0, abs(ZR.dot(d0)))) * R2D}
        return cls(sides)

    def solve(self, side, q):
        s = self.sides[side]
        t = q @ s['d0']
        ph = math.atan2(s['B'], s['A'])
        h = math.acos(clamp(s['XP'].dot(t) / math.hypot(s['A'], s['B']), -1.0, 1.0))
        b1, b2 = wrap_pi(ph + h), wrap_pi(ph - h)
        b = b1 if abs(b1) <= abs(b2) else b2

        def off(w):
            k = w.dot(s['XP'])
            return w - s['XP'] * k
        p1, p2 = off(_vrot(s['d0'], s['ZR'], b)), off(t)
        a = math.atan2(p1.cross(p2).dot(s['XP']), p1.dot(p2)) if p1.length > 1e-9 and p2.length > 1e-9 else s['a']
        Ra, Rb = Quaternion(s['XP'], a), Quaternion(s['ZR'], b)
        y = (Ra @ Rb).inverted() @ q
        s['a'], s['b'] = a, b
        s['c'] = wrap_pi(2.0 * math.atan2(y.x * s['d0'].x + y.y * s['d0'].y + y.z * s['d0'].z, y.w))
        self.out[side] = {'pitch': Ra, 'swing': Rb}


# ------------------------------------------------------------------------------------------- the legs' clearance
# THE LEGS' CLEARANCE FROM EACH OTHER (claude_robot_dof.js applyLegClearance, design 2.2, 11-05: its whole comment block
# holds here). Stock clips put both feet on one narrow human track; my feet and shins are wider than a human's, so after
# applyHardwareDOF each ankle moves out on the floor plane by up to `width` and the leg is re-posed to reach it: THE OFFSET
# (held while the foot bears weight, eased while it is up, the pair's shortfall, the slide), LOADED (by height, or at any
# height while it moves with the clip's stance velocity v_st), THE LEG (the knee by the law of cosines, the thigh's least
# turn, the swivel square to the foot's forward with its conditioning guard), THE TABLE (a loaded leg keeps the share of
# the offset the hip's table holds), THE CLAMPS, THE LEVEL (every foot raised by the most-raised loaded foot's rise).
LEG_CLEARANCE = {'width': 0.072, 'need': (0.18, 0.23), 'load': (0.003, 0.006), 'support': (45, 55), 'ease': 0.5,
                 'jump': 0.25, 'hold': 90, 'swivel': (0.02, 0.1), 'level': True,
                 'pair': (0.02, 0.045), 'slide': (0.18, 0.6), 'stance': (0.12, 0.18), 'steady': 2.7, 'track': 0.15,
                 'stale': 0.1, 'cond': (0.3, 0.5), 'window': 1.0 / 30.0, 'condRate': 3}


def _rot_vec(q, v):
    return q @ Vector(v)


def _lowest_y(P, q, y0):
    """the lowest y of a point set (offsets in a bone's normalized frame, three's axes) turned by q, the bone at height y0"""
    if not len(P):
        return math.inf
    r0 = 2 * (q.x * q.y + q.w * q.z)
    r1 = 1 - 2 * (q.x * q.x + q.z * q.z)
    r2 = 2 * (q.y * q.z - q.w * q.x)
    ys = P[:, 0] * r0 + P[:, 1] * r1 + P[:, 2] * r2
    return y0 + float(ys.min())


class LegClearance:
    """initLegClearance's memo (made lazily by the first applyLegClearance in the JS; here at load): each side's foot points
    (every vertex whose dominant skin weight is its Foot or Toes bone, as offsets from that bone at the bind in the
    normalized frame, three's axes, within 50 mm of that set's own lowest), the normalized leg nodes' rest offsets, and
    the per-leg state the pass carries from one clip input to the next."""

    def __init__(self, h, conf=None):
        import numpy as np
        self.C = dict(LEG_CLEARANCE, **(conf or {}))
        H = {n: v_to_three(h.rest_head[b]) for n, b in h.humanoid.items()}
        self.rest = {}
        for s in SIDES:
            self.rest[s] = {'t': H[s + 'UpperLeg'] - H['hips'], 's': H[s + 'LowerLeg'] - H[s + 'UpperLeg'],
                            'f': H[s + 'Foot'] - H[s + 'LowerLeg'],
                            'to': (H[s + 'Toes'] - H[s + 'Foot']) if (s + 'Toes') in H else None}
        self.hips_rest = H['hips']
        pts = {}
        want = {}
        for s in SIDES:
            for b in ('Foot', 'Toes'):
                bn = h.humanoid.get(s + b)
                if bn:
                    want[bn] = (s, b)
        inv = h.arm.matrix_world.inverted()
        for o in h.meshes:
            if not o.vertex_groups:
                continue
            idx = {g.index: g.name for g in o.vertex_groups}
            if not any(n in want for n in idx.values()):
                continue
            M = inv @ o.matrix_world
            for v in o.data.vertices:
                best, bw = None, -1.0
                for g in v.groups:
                    if g.weight > bw:
                        bw, best = g.weight, g.group
                n = idx.get(best)
                if n in want:
                    s, b = want[n]
                    pts.setdefault(s + b, []).append(tuple(v_to_three(M @ v.co - h.rest_head[n])))

        def keep(a):
            if not a:
                return np.zeros((0, 3))
            A = np.array(a, dtype=np.float64)
            return A[A[:, 1] < A[:, 1].min() + 0.05]
        self._pts = {s: (keep(pts.get(s + 'Foot')), keep(pts.get(s + 'Toes'))) for s in SIDES}
        self.reset()

    def reset(self):
        """the per-leg state back to a fresh load's (the foot points kept): for a cut, or a clip that starts where the
        last one did not end (the JS has no such call: a VRM's memo lives as long as the VRM)"""
        self.mem = {'sig': None, 'vst': None, 'stale': 0.0}
        for s in SIDES:
            foot, toes = self._pts[s]
            self.mem[s] = {'foot': foot, 'toes': toes, 'M': {}, 'loaded': False,
                           'h': None, 'next': None, 'last': None, 'st': False, 'hist': [], 'wst': 0.0, 'dmax': 0.0,
                           'wc': 1.0, 'cap': math.inf}
        self.last = {}

    def apply(self, pose, hips_pos, stats=None, dt=None, width=None, legs=None):
        """applyLegClearance(vrm, stats, dt, width): pose (three's frame, in place), hips_pos the normalized hips node's
        position (three's axes: the rest head plus the clip's translation); legs the LegStages (the hips' stages are
        solved by the clamps it calls, as the JS's applyHardwareDOF does after initLegDOF)"""
        C, mem = self.C, self.mem
        width = C['width'] if width is None else width
        if pose.get('hips') is None or not width:
            return
        UL, LL, FT = LEG_JOINTS[0], LEG_JOINTS[1], LEG_JOINTS[2]
        Qh = pose['hips'].copy()
        Qi = Qh.inverted()
        hp = Vector(hips_pos)
        legs_ = {}

        def same(a, b):
            return a is not None and _same64(a, b)
        # 1. the inputs (the clip's, clamped; a bone still holding the pass's output gives back its input)
        for side, m in (('left', 1), ('right', -1)):
            R = self.rest[side]
            kt, ks, kf, ke = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', side + 'Toes'
            if pose.get(kt) is None or pose.get(ks) is None or pose.get(kf) is None:
                return
            Mm = mem[side]['M']

            def inp(k, q):
                o = Mm.get(k)
                return (o['in'] if same(o['out'] if o else None, q) else q).copy()
            qt, qs, qf = inp('t', pose[kt]), inp('s', pose[ks]), inp('f', pose[kf])
            has_to = R['to'] is not None and pose.get(ke) is not None
            qe = pose[ke].copy() if has_to else None
            v = qt @ (qs @ R['f'] + R['s'])
            qF = qt @ qs @ qf
            RF = Qh @ qF
            ankle = Qh @ (R['t'] + v) + hp
            knee = Qh @ (qt @ R['s'] + R['t']) + hp
            ball = (RF @ R['to']) + ankle if has_to else ankle.copy()
            lo = _lowest_y(mem[side]['foot'], RF, ankle.y)
            if has_to:
                lo = min(lo, _lowest_y(mem[side]['toes'], RF @ qe, ball.y))
            legs_[side] = {'m': m, 'kt': kt, 'ks': ks, 'kf': kf, 'has_to': has_to, 'R': R, 'Mm': Mm, 'qt': qt, 'qs': qs,
                           'qf': qf, 'qe': qe, 'qF': qF, 'v': v, 'lo': lo, 'at': [knee, ankle, ball]}
        low = min(legs_['left']['lo'], legs_['right']['lo'])
        # 2. the state, once per new input
        sig = [Qh.x, Qh.y, Qh.z, Qh.w, hp.x, hp.y, hp.z]
        for L in legs_.values():
            for q in (L['qt'], L['qs'], L['qf'], L['qe']):
                if q is not None:
                    sig += [q.x, q.y, q.z, q.w]
        if mem['sig'] is None or len(mem['sig']) != len(sig) or any(x != y for x, y in zip(sig, mem['sig'])):
            mem['sig'] = sig
            dtv = dt if (dt is not None and dt > 0) else 1.0 / 30.0
            lat = Qh @ (legs_['left']['R']['t'] - legs_['right']['R']['t'])
            lh = math.hypot(lat.x, lat.z)
            tgt = (lat.x / lh, lat.z / lh) if lh > 0.25 * lat.length else None
            gap = ((legs_['left']['at'][1].x - legs_['right']['at'][1].x) * tgt[0]
                   + (legs_['left']['at'][1].z - legs_['right']['at'][1].z) * tgt[1]) if tgt else 0.0
            wide = smooth(C['need'][0], C['need'][1], gap) if C.get('need') else 0.0

            def rot(u, a):
                return (u[0] * math.cos(a) - u[1] * math.sin(a), u[0] * math.sin(a) + u[1] * math.cos(a))
            Q = {}
            for side, L in legs_.items():
                S = mem[side]
                up = L['lo'] - low
                tg = (L['m'] * tgt[0], L['m'] * tgt[1]) if tgt else None
                vr = Qh @ L['v']
                hang = math.acos(clamp(-vr.y / vr.length, -1.0, 1.0)) * R2D
                wd = width * (1 - wide * (1 - smooth(C['support'][0], C['support'][1], hang)))
                st = [(p - q).length for p, q in zip(L['at'], S['last'])] if S['last'] else [0.0, 0.0, 0.0]
                moved = math.inf if st[1] > C['jump'] else min(2 * st[0], st[1], st[2])
                k, span = len(S['hist']) - 1, dtv
                while k > 0 and span < 0.9 * (C.get('window') or 0):
                    span += S['hist'][k]['dt']
                    k -= 1
                H0 = S['hist'][k] if k >= 0 and S['hist'] else None
                vel = [(L['at'][i] - H0['at'][i]) / span for i in (1, 2)] if H0 else None
                S['hist'].append({'dt': dtv, 'at': L['at'], 'vel': vel})
                if k > 0:
                    del S['hist'][0:k]
                prev = S['last']
                S['last'] = L['at']
                S['cap'] = S['wc'] + C['condRate'] * dtv if C.get('condRate') else math.inf
                if S['next'] is None:
                    S['next'] = [wd * tg[0], wd * tg[1]] if tg else [width * L['m'], 0.0]
                Q[side] = {'S': S, 'up': up, 'tg': tg, 'hang': hang, 'wd': wd, 'moved': moved, 'vel': vel,
                           'pw': H0['vel'] if H0 else None, 'span': span, 'prev': prev, 'dev': math.inf}
            # (C2) the clip's stance velocity v_st
            if C.get('stance'):
                vw, nw = None, 0
                for q in Q.values():
                    pv = q['pw']
                    if not q['vel'] or not pv or q['hang'] > C['support'][1]:
                        continue
                    ch = [(q['vel'][0] - pv[0]).length, (q['vel'][1] - pv[1]).length]
                    j = 0 if ch[0] <= ch[1] else 1
                    if ch[j] > C['steady'] * q['span']:
                        continue
                    if not (q['up'] <= (C['load'][1] if q['S']['loaded'] else C['load'][0]) or q['S']['st']):
                        continue
                    if mem['vst'] is not None and mem['stale'] < C['stale'] and (q['vel'][j] - mem['vst']).length > C['track']:
                        continue
                    vw = q['vel'][j].copy() if vw is None else vw + q['vel'][j]
                    nw += 1
                if nw:
                    vw = vw / nw
                    if mem['vst'] is None or mem['stale'] >= C['stale']:
                        mem['vst'] = vw
                    else:
                        mem['vst'] = mem['vst'].lerp(vw, 1 - math.pow(0.5, dtv * 30))
                    mem['stale'] = 0.0
                else:
                    mem['stale'] += dtv
            # LOADED: by height, or (C2) at any height while the foot moves with the clip's stance
            for q in Q.values():
                S = q['S']
                if S['loaded']:
                    hgt = q['up'] <= C['load'][1] and q['hang'] <= C['support'][1]
                else:
                    hgt = q['up'] <= C['load'][0] and q['hang'] <= C['support'][0]
                stn = False
                if C.get('stance') and mem['vst'] is not None and q['vel']:
                    q['dev'] = min((q['vel'][0] - mem['vst']).length, (q['vel'][1] - mem['vst']).length)
                    if S['loaded']:
                        stn = q['dev'] <= C['stance'][1] and q['hang'] <= C['support'][1]
                    else:
                        stn = q['dev'] <= C['stance'][0] and q['hang'] <= C['support'][0]
                S['st'] = stn
                S['loaded'] = hgt or stn
                S['wst'] = ((1 - smooth(C['stance'][1], 2 * C['stance'][1], q['dev']))
                            * (1 - smooth(C['support'][0], C['support'][1], q['hang']))) \
                    if C.get('stance') and math.isfinite(q['dev']) else 0.0
            # (C1 b) the pair's slide against itself since the last input, on the floor plane
            rel = 0.0
            if Q['left']['prev'] and Q['right']['prev']:
                rel = min(math.hypot(d.x, d.z) for d in (
                    (legs_['left']['at'][i] - legs_['right']['at'][i]) - (Q['left']['prev'][i] - Q['right']['prev'][i])
                    for i in (1, 2)))
            for side, q in Q.items():
                S, tg, oq = q['S'], q['tg'], Q['right' if side == 'left' else 'left']
                hh, pair, slid = list(S['next']), 0.0, 0.0
                if not S['loaded']:
                    S['dmax'] = 0.0
                elif tg:
                    S['dmax'] = max(S['dmax'] or 0.0, q['wd'] - math.hypot(hh[0], hh[1]))
                if tg and not S['loaded']:
                    if C.get('pair') and oq['S']['loaded'] and oq['tg']:
                        short = min(oq['wd'], max(0.0, oq['wd'] - (oq['S']['next'][0] * oq['tg'][0]
                                                                   + oq['S']['next'][1] * oq['tg'][1])))
                        pair = short * smooth(C['pair'][0], C['pair'][1], short) \
                            * (1 - smooth(C['support'][0], C['support'][1], q['hang']))
                    wd = q['wd'] + pair
                    dx, dz = wd * tg[0] - hh[0], wd * tg[1] - hh[1]
                    n, c = math.hypot(dx, dz), C['ease'] * q['moved']
                    hh = [hh[0] + dx * c / n, hh[1] + dz * c / n] if n > c else [wd * tg[0], wd * tg[1]]
                    a = math.atan2(hh[0] * tg[1] - hh[1] * tg[0], hh[0] * tg[0] + hh[1] * tg[1])
                    lim = C['hold'] * D2R
                    if math.hypot(hh[0], hh[1]) > 1e-9 and abs(a) > lim:
                        hh = list(rot(hh, a - math.copysign(1.0, a) * lim))
                elif tg and C.get('slide') and S['loaded'] and math.isfinite(q['moved']):
                    deficit = max(0.0, q['wd'] - math.hypot(hh[0], hh[1]))
                    if deficit > 0:
                        two = oq['S']['loaded']
                        dv = q['dev'] * dtv if math.isfinite(q['dev']) else (rel if two else 0.0)
                        ns = (min(rel, dv) - C['slide'][0] * dtv) if two else (dv - C['slide'][1] * dtv)
                        slid = smooth(C['pair'][0], C['pair'][1], S['dmax']) * min(deficit, C['ease'] * min(q['moved'], max(0.0, ns)))
                        if slid > 0:
                            hh = [hh[0] + slid * tg[0], hh[1] + slid * tg[1]]
                S['h'] = hh
        # 3. per leg, for a target T = v + s o: the knee for |T|; the thigh's least turn onto T; the swivel about hip -> T
        kx = Vector(LL['axis'])
        ex, ez = Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))

        def solve(L, T, sw):
            a, b = L['R']['s'], L['R']['f']
            P = a.y * b.y + a.z * b.z
            Qq = a.z * b.y - a.y * b.z
            c = (T.length_squared - a.length_squared - b.length_squared - 2 * a.x * b.x) / (2 * math.hypot(P, Qq))
            k = min(LL['range'][1] * D2R, max(LL['range'][0] * D2R, math.atan2(Qq, P) + math.acos(clamp(c, -1.0, 1.0))))
            qs = _aa(kx, k)
            w = (qs @ b) + a
            u = T.normalized()
            q1 = _unit_vectors((L['qt'] @ w).normalized(), u) @ L['qt']
            X1, Fz = q1 @ ex, L['qF'] @ ez
            Cc = X1.dot(u) * Fz.dot(u)
            Ac = X1.dot(Fz) - Cc
            Bc = u.cross(X1).dot(Fz)
            Rr = math.hypot(Ac, Bc)
            psi = 0.0
            if Rr > 1e-9:
                ph, g = math.atan2(Bc, Ac), -Cc / Rr
                if g >= 1:
                    psi = ph
                elif g <= -1:
                    psi = ph + math.pi
                else:
                    p1, p2 = wrap_pi(ph + math.acos(g)), wrap_pi(ph - math.acos(g))
                    psi = p1 if abs(p1) <= abs(p2) else p2
            cnd = Fz.cross(u).length
            wc = min(smooth(C['cond'][0], C['cond'][1], cnd), L.get('cap', math.inf)) if C.get('cond') else 1.0
            psi = wrap_pi(psi) * sw * wc
            return {'qt': _aa(u, psi) @ q1, 'qs': qs, 'wc': wc, 'psi': psi, 'cnd': cnd}

        def in_table(q, m):
            x, y, z = euler_from_quat(q, 'XZY')
            x, z, y = x * R2D, m * z * R2D, m * y * R2D
            r, cp, tol = UL['range'], UL['coupled'], 1e-6
            if x < r['x'][0] - tol or x > r['x'][1] + tol or z < r['z'][0] - tol or z > r['z'][1] + tol \
                    or y < r['y'][0] - tol or y > r['y'][1] + tol:
                return False
            return not cp or (lerp_table(cp['x'], cp['zmin'], x) - tol <= z <= lerp_table(cp['x'], cp['zmax'], x) + tol
                              and y >= lerp_table(cp['z'], cp['ymin'], z) - tol)
        for side, L in legs_.items():
            S = mem[side]
            o = Qi @ Vector((S['h'][0], 0.0, S['h'][1]))
            sw = max(1 - smooth(C['swivel'][0], C['swivel'][1], L['lo'] - low), S['wst'] or 0.0) if C.get('swivel') else 1.0
            L['o'], L['sw'], L['cap'] = o, sw, S['cap']

            def at(sv, L=L, o=o, sw=sw):
                return solve(L, o * sv + L['v'], sw)
            sol = at(1.0)
            L['se'] = 1.0
            if S['loaded'] and not in_table(sol['qt'], L['m']):
                lo_, hi_ = 0.0, 1.0
                for _ in range(16):
                    mid = 0.5 * (lo_ + hi_)
                    if in_table(at(mid)['qt'], L['m']):
                        lo_ = mid
                    else:
                        hi_ = mid
                L['se'] = lo_
                sol = at(lo_)
            pose[L['kt']] = sol['qt']
            pose[L['ks']] = sol['qs']
            L['wc'] = sol['wc']
        # 4. the thighs and the knees clamped as applyHardwareDOF clamps them, the stages solved
        apply_hardware_dof(pose, [UL, LL], legs)

        # 5. each foot: the clip's sole normal in the new shin's frame, then clamped as the cardan is
        def sole(L):
            n = (pose[L['kt']] @ pose[L['ks']]).inverted() @ (L['qF'] @ Vector((0.0, -1.0, 0.0)))
            pose[L['kf']] = quat_from_euler(math.atan2(-n.z, -n.y), 0.0, math.asin(clamp(n.x, -1.0, 1.0)), 'XZY')
        for L in legs_.values():
            sole(L)
        apply_hardware_dof(pose, [FT], legs)
        # 6. THE LEVEL
        if C.get('level') is not False:
            upH = Qi @ Vector((0.0, 1.0, 0.0))

            def low_now(L, side):
                RF = Qh @ pose[L['kt']] @ pose[L['ks']] @ pose[L['kf']]
                ankle = Qh @ (pose[L['kt']] @ (pose[L['ks']] @ L['R']['f'] + L['R']['s']) + L['R']['t']) + hp
                y = _lowest_y(mem[side]['foot'], RF, ankle.y)
                if L['has_to']:
                    y = min(y, _lowest_y(mem[side]['toes'], RF @ L['qe'], ((RF @ L['R']['to']) + ankle).y))
                return y
            Rm, lifted = -math.inf, False
            for side, L in legs_.items():
                L['rise'] = low_now(L, side) - L['lo']
                if mem[side]['loaded']:
                    Rm = max(Rm, L['rise'])
            for side, L in legs_.items():
                L['lift'] = 0.0
                if not math.isfinite(Rm) or (Rm - L['rise']) * L['sw'] <= 1e-4:
                    continue
                T0 = L['o'] * L['se'] + L['v']

                def atL(x, L=L, T0=T0):
                    return solve(L, T0 + upH * x, L['sw'])
                lift = (Rm - L['rise']) * L['sw']
                sol = atL(lift)
                if not in_table(sol['qt'], L['m']):
                    if not in_table(atL(0.0)['qt'], L['m']):
                        continue
                    lo_, hi_ = 0.0, 1.0
                    for _ in range(16):
                        mid = 0.5 * (lo_ + hi_)
                        if in_table(atL(lift * mid)['qt'], L['m']):
                            lo_ = mid
                        else:
                            hi_ = mid
                    lift *= lo_
                    sol = atL(lift)
                pose[L['kt']] = sol['qt']
                pose[L['ks']] = sol['qs']
                L['wc'] = sol['wc']
                L['lift'] = lift
                lifted = True
            if lifted:
                apply_hardware_dof(pose, [UL, LL], legs)
                for L in legs_.values():
                    if L['lift']:
                        sole(L)
                apply_hardware_dof(pose, [FT], legs)
        # 7. the offset carried to the next input; the memo
        for side, L in legs_.items():
            S = mem[side]
            kk = L['se'] if S['loaded'] else 1.0
            S['next'] = [S['h'][0] * kk, S['h'][1] * kk]
            S['wc'] = L['wc']
            L['Mm']['t'] = {'in': L['qt'], 'out': pose[L['kt']].copy()}
            L['Mm']['s'] = {'in': L['qs'], 'out': pose[L['ks']].copy()}
            L['Mm']['f'] = {'in': L['qf'], 'out': pose[L['kf']].copy()}
            if stats is not None:
                k = side + 'LegClearance'
                stats[k] = max(stats.get(k, 0.0), 2 * math.acos(min(1.0, abs(L['qt'].dot(pose[L['kt']])))) * R2D)
        self.last = {side: {'loaded': mem[side]['loaded'], 'offset': list(mem[side]['next']), 'se': L['se'],
                            'lift': L.get('lift', 0.0), 'sw': L['sw']} for side, L in legs_.items()}


def apply_leg_clearance(clear, pose, hips_pos, stats=None, dt=None, width=None, legs=None):
    """applyLegClearance(vrm, stats, dt, width): clear is a LegClearance(h) made at load"""
    return clear.apply(pose, hips_pos, stats, dt, width, legs)


# ------------------------------------------------------------------------------------------------------------- the arms
def _b2t(v):
    return Vector((v[0], v[2], -v[1]))


def _make_arm():
    S, E, W = Vector((165.0, -28.0, 1337.0)), Vector((199.0, -46.5, 1069.0)), Vector((234.5, -50.0, 811.0))
    Ub, FAb = (E - S).normalized(), (W - E).normalized()
    RYb = Vector((1, 0, 0)).cross(Ub).normalized()
    XEb = Ub.cross(Vector((0, 1, 0))).normalized()
    U, RY, X = _b2t(Ub), _b2t(RYb).normalized(), Vector((1, 0, 0))
    nRY = -RY
    k, t = U.cross(X).normalized(), math.acos(min(1.0, U.dot(X)))
    return {
        'U': U, 'RY': RY, 'nRY': nRY,
        'XF': _vrot(_b2t(-XEb), k, t), 'FA': _vrot(_b2t(FAb), k, t),
        'rollT': math.atan2(U.cross(X).dot(nRY), U.dot(X)),
        'pitch': (-150, 60), 'roll': (-0.5, 110), 'twist': (-90, 90), 'flex': (0, 135), 'wristRoll': (-90, 90),
        'wristFlex': (-70, 70), 'wristDev': (-12, 12),
        'wristCoupled': [
            {'flexion': -70, 'dev_min': -3, 'dev_max': 12}, {'flexion': -68, 'dev_min': -5, 'dev_max': 12},
            {'flexion': -66, 'dev_min': -5, 'dev_max': 12}, {'flexion': -65, 'dev_min': -7, 'dev_max': 12},
            {'flexion': -64, 'dev_min': -7, 'dev_max': 12}, {'flexion': -62, 'dev_min': -9, 'dev_max': 12},
            {'flexion': -61, 'dev_min': -12, 'dev_max': 12}, {'flexion': -60, 'dev_min': -12, 'dev_max': 12},
        ],
        'wristLimit': {'turn': 25, 'jump': 90},
        'pitchRate': 360,
        'hang': {'rollMin': 0, 'twistMin': -52, 'flex': (12, 20), 'roll': (20, 30)},
    }


ARM = _make_arm()
ARM_POSE_BONES = [s + b for b in ('Shoulder', 'UpperArm', 'LowerArm', 'Hand') for s in SIDES]


def apply_arm_clearance(pose, deg=8.0):
    """THE HANDS' CLEARANCE FROM THE THIGHS: each hanging upper arm turned out about the body's front axis by up to deg"""
    z = Vector((0.0, 0.0, 1.0))
    for side, sg in (('left', 1), ('right', -1)):
        ua = pose.get(side + 'UpperArm')
        if ua is None:
            continue
        d = ua @ Vector((sg, 0.0, 0.0))
        w = smooth(0.5, 0.95, -d.y)
        if w > 0:
            pose[side + 'UpperArm'] = Quaternion(z, sg * deg * D2R * w) @ ua


def wrist_dev_range(b_deg):
    """the coupled wrist clamp: deviation's range (lo, hi) deg at flexion b_deg, linear in flexion between
    ARM['wristCoupled']'s rows, the box's own limits (ARM['wristDev']) outside them"""
    R, box = ARM['wristCoupled'], ARM['wristDev']
    if not R or b_deg < R[0]['flexion'] or b_deg > R[-1]['flexion']:
        return box
    i = 1
    while i < len(R) - 1 and b_deg > R[i]['flexion']:
        i += 1
    r0, r1 = R[i - 1], R[i]
    t = (b_deg - r0['flexion']) / ((r1['flexion'] - r0['flexion']) or 1)
    return (max(box[0], r0['dev_min'] + t * (r1['dev_min'] - r0['dev_min'])),
            min(box[1], r0['dev_max'] + t * (r1['dev_max'] - r0['dev_max'])))


def _qang(p, q):
    return 2.0 * math.acos(min(1.0, abs(p.dot(q))))


def wrist_solve(q, W):
    """the hand's turn q against the forearm (the left's frame, three's axes) split in the mechanism's order and clamped at
    the stops: in the stages' basis q is Euler 'XYZ' (roll a, flexion b, deviation c), the natural branch, each clamped
    (the deviation in the coupled range at the clamped flexion); the hand turns toward that as fast as ARM['wristLimit']
    allows. -> (the recomposed q, the solution {a, b, c, asked[, limited]}); W keeps a, b, c (rad) and its memo"""
    qb = W['Bi'] @ q @ W['B']
    M, L = W.get('memo'), ARM['wristLimit']
    if M is not None and _same64(qb, M['out']):
        W['a'], W['b'], W['c'], W['asked'] = M['a'], M['b'], M['c'], M['asked']
        return W['B'] @ M['out'] @ W['Bi'], M

    def lim(x, r):
        return min(r[1] * D2R, max(r[0] * D2R, x))
    a0, b0, c0 = euler_from_quat(qb, 'XYZ')
    sA, sD = W.get('sgnA', 1), W.get('sgnD', 1)
    a, b = lim(a0, ARM['wristRoll']), lim(b0, ARM['wristFlex'])
    dl = wrist_dev_range(sA * b * R2D)
    c = lim(c0, dl if sD > 0 else (-dl[1], -dl[0]))
    s = {'a': a, 'b': b, 'c': c, 'asked': [a0, b0, c0]}
    qo = quat_from_euler(a, b, c, 'XYZ')
    if M is not None and L and _qang(qb, M['in']) <= L['jump'] * D2R:
        allow = _qang(qb, M['in']) + L['turn'] * D2R
        if _qang(qo, M['out']) > allow:
            def at(u):
                bu = M['b'] + u * (b - M['b'])
                du = wrist_dev_range(sA * bu * R2D)
                return (M['a'] + u * (a - M['a']), bu, lim(M['c'] + u * (c - M['c']), du if sD > 0 else (-du[1], -du[0])))
            lo, hi = 0.0, 1.0
            for _ in range(30):
                mm = 0.5 * (lo + hi)
                if _qang(quat_from_euler(*at(mm), 'XYZ'), M['out']) <= allow:
                    lo = mm
                else:
                    hi = mm
            v = at(lo)
            s = {'a': v[0], 'b': v[1], 'c': v[2], 'asked': [a0, b0, c0], 'limited': True}
            qo = quat_from_euler(v[0], v[1], v[2], 'XYZ')
    W['a'], W['b'], W['c'], W['asked'] = s['a'], s['b'], s['c'], s['asked']
    W['memo'] = {'in': qb.copy(), 'out': qo.copy(), 'a': s['a'], 'b': s['b'], 'c': s['c'], 'asked': s['asked']}
    return W['B'] @ qo @ W['Bi'], s


def _wrist_record(h, side, mute):
    """initWrist: the roll stage (WristRoll, on the forearm) and the drum (WristFlex, on the roll stage): their axes in the
    left's frame (the right's mirrored), EL the roll stage's Y, EA the drum's X squared to EL, ED = EL x EA the deviation
    pin; their constraints muted when `mute` (then the keyer must key them: wrist_out)"""
    rn, fn = side + 'WristRoll', side + 'WristFlex'
    bones = h.arm.data.bones
    if rn not in bones or fn not in bones or bones[fn].parent is None or bones[fn].parent.name != rn \
            or bones[rn].parent is None:
        return None
    muted = _mute(h, rn, mute) + _mute(h, fn, mute)
    m = 1 if side == 'left' else -1

    def mir(u):
        return Vector((u.x, u.y, u.z)) if m > 0 else Vector((u.x, -u.y, -u.z))
    Pd, Wd = h.node_frame_three(rn), h.node_frame_three(fn)
    EL = mir(Pd @ Vector((0.0, 1.0, 0.0))).normalized()
    ea = mir(Wd @ Vector((1.0, 0.0, 0.0)))
    k = ea.dot(EL)
    EA = (ea - EL * k).normalized()
    ED = EL.cross(EA)
    B = Matrix((EL, EA, ED)).transposed().to_quaternion()
    rest_deg = None
    hb = h.humanoid.get(side + 'Hand')
    if hb:
        hd = Wd.inverted() @ h.node_frame_three(hb)
        rest_deg = 2 * math.atan2(math.sqrt(hd.x ** 2 + hd.y ** 2 + hd.z ** 2), abs(hd.w)) * R2D
    return {'roll': rn, 'flex': fn, 'muted': muted, 'removed': muted, 'EL': EL, 'EA': EA, 'ED': ED, 'B': B,
            'Bi': B.inverted(), 'squareDeg': math.asin(min(1.0, abs(k))) * R2D, 'restDeg': rest_deg,
            'a': 0.0, 'b': 0.0, 'c': 0.0, 'asked': [0.0, 0.0, 0.0], 'memo': None}


class ArmDOF:
    """initArmDOF + applyArmDOF: per side the shoulder's pitch stage state (phi, rate-limited), the wrist's three stages
    (wristSolve, its turn limit's memo) and the elbow's record from the joints file's hinges.leftLowerArm (axis XF, hardware
    range, flexion at rest, forearm axis). apply() leaves self.helper_phi[side] (rad, the ShoulderPitch helper's turn about
    X) and self.wrist_out[side] = {'roll', 'flex'} (three-frame turns of the WristRoll / WristFlex stages) for the keyer.
    from_handle mutes the shoulder helpers' constraints; the wrist stages' only with mute_wrist=True (a caller that keys
    wrist_out); otherwise the add-on's own COPY_ROTATION constraints turn them from the solved hand."""

    def __init__(self, hinges=None, helpers=None, wrist=None):
        el = (hinges or {}).get('leftLowerArm')
        if hinges and not el:
            print("[robot_dof] init_arm_dof: hinges without a leftLowerArm record: the elbow keeps ARM's constants "
                  "(its clamp [0, 135] from the rest, FA the upper arm's turn only)", flush=True)
        if el:
            self.elbow = {'record': True, 'XF': Vector(el['axis']).normalized(),
                          'FA': Vector(el.get('forearm_axis') or ARM['FA']).normalized(), 'rest': el['flex_at_rest'],
                          'flex': (el['deg'][0] - el['flex_at_rest'], el['deg'][1] - el['flex_at_rest'])}
        else:
            self.elbow = {'record': False, 'XF': ARM['XF'], 'FA': ARM['FA'], 'rest': 0.0, 'flex': ARM['flex']}
        self.phi = {'left': 0.0, 'right': 0.0}
        self.helpers = helpers or {}
        self.helper_phi = {}
        self.wrist = wrist or {}
        self.wrist_out = {}
        self.kept = None
        WL, WR = self.wrist.get('left'), self.wrist.get('right')
        if WL:
            WL['sgnA'], WL['sgnD'] = 1, 1
        if WR:
            WR['sgnA'] = -1 if WL and WL['EA'].dot(WR['EA']) < 0 else 1
            WR['sgnD'] = -1 if WL and WL['ED'].dot(WR['ED']) < 0 else 1

    @classmethod
    def from_handle(cls, h, hinges=None, mute=True, wrist=True, mute_wrist=False):
        helpers = {}
        for side in SIDES:
            n = side + 'ShoulderPitch'
            if n in h.arm.data.bones:
                helpers[side] = n
                _mute(h, n, mute)
        wr = {s: _wrist_record(h, s, mute_wrist) for s in SIDES} if wrist else {}
        return cls(hinges, helpers, {s: w for s, w in wr.items() if w})

    def apply(self, pose, dt=1.0 / 24.0, clearance=8.0, stats=None):
        A, el = ARM, self.elbow
        if clearance:
            apply_arm_clearance(pose, clearance)

        def roll_for(phi, d):
            d0 = Vector((d[0], d[1] * math.cos(-phi) - d[2] * math.sin(-phi), d[1] * math.sin(-phi) + d[2] * math.cos(-phi)))
            k = d0.dot(A['RY'])
            p = (d0 - A['RY'] * k).normalized()
            return math.atan2(A['U'].cross(p).dot(A['nRY']), A['U'].dot(p))

        for side in SIDES:
            m = 1 if side == 'left' else -1
            W = self.wrist.get(side)
            ua, la, hand = pose.get(side + 'UpperArm'), pose.get(side + 'LowerArm'), pose.get(side + 'Hand')
            if ua is None or la is None:
                continue
            # 1. the elbow: its flexion only, clamped at the hardware stops; the forearm's twist goes to the hand (about
            # the roll stage's own axis EL where the VRM has the wrist's stages, else the elbow's FA)
            FAx = W['EL'] if W else el['FA']
            q = _mirror(la, m)
            flex = clamp(angle_about(q, el['XF']) * R2D, el['flex'][0], el['flex'][1]) * D2R
            qa = Quaternion(el['XF'], flex)
            pron = angle_about(qa.inverted() @ q, FAx)
            pose[side + 'LowerArm'] = _mirror(qa, m)
            _note(stats, side + 'LowerArm', q, qa)
            if hand is not None:
                q = _mirror(hand, m)
                hb = q.copy()
                q = Quaternion(FAx, pron) @ q
                if W:
                    q, _s = wrist_solve(q, W)
                else:
                    roll = angle_about(q, el['FA'])
                    q = q @ Quaternion(el['FA'], -roll) @ Quaternion(el['FA'], clamp(roll * R2D, *A['wristRoll']) * D2R)
                pose[side + 'Hand'] = _mirror(q, m)
                _note(stats, side + 'Hand', hb, q)
                if W:
                    self.wrist_out[side] = {'roll': _mirror(Quaternion(W['EL'], W['a']), m),
                                            'flex': _mirror(Quaternion(W['EA'], W['b']), m)}
            # 2. the shoulder: the pitch that turns the axle square to the arm, the roll, the twist at the ring
            q = _mirror(ua, m)
            qb = q.copy()
            d = q @ Vector((1.0, 0.0, 0.0))
            fd = flex * R2D + el['rest']
            rmin = (A['hang']['rollMin'] + (A['roll'][0] - A['hang']['rollMin']) * smooth(A['hang']['flex'][0], A['hang']['flex'][1], fd)) * D2R
            rmax, plo, phi_hi = A['roll'][1] * D2R, A['pitch'][0] * D2R, A['pitch'][1] * D2R
            base = math.atan2(d[2], d[1]) - math.atan2(A['RY'][2], A['RY'][1])
            best = None
            for c in (wrap_pi(base + math.pi / 2), wrap_pi(base - math.pi / 2)):
                p = min(phi_hi, max(plo, c))
                rr = roll_for(p, d)
                cost = abs(p - c) + max(0.0, rmin - rr, rr - rmax) + 1e-3 * abs(wrap_pi(p - self.phi[side]))
                if best is None or cost < best[1]:
                    best = (p, cost)
            target = self.phi[side] if abs(d[0]) > math.cos(10 * D2R) else best[0]
            step = A['pitchRate'] * D2R * (dt or 1.0 / 30.0)
            phi = min(phi_hi, max(plo, self.phi[side] + min(step, max(-step, wrap_pi(target - self.phi[side])))))
            self.phi[side] = phi
            rho = min(rmax, max(rmin, roll_for(phi, d)))
            swing = Quaternion((1.0, 0.0, 0.0), phi) @ Quaternion(A['nRY'], rho - A['rollT'])
            clear = max(smooth(A['hang']['flex'][0], A['hang']['flex'][1], fd), smooth(A['hang']['roll'][0], A['hang']['roll'][1], rho * R2D))
            tmin = A['hang']['twistMin'] + (A['twist'][0] - A['hang']['twistMin']) * clear
            tau = clamp(angle_about(swing.inverted() @ q, (1.0, 0.0, 0.0)) * R2D, tmin, A['twist'][1]) * D2R
            q = swing @ Quaternion((1.0, 0.0, 0.0), tau)
            pose[side + 'UpperArm'] = _mirror(q, m)
            _note(stats, side + 'UpperArm', qb, q)
            # 3. the pitch helper: phi about the torso's X (the mirror leaves a turn about X as it is)
            self.helper_phi[side] = phi


def keep_arm_pose(arms, pose):
    """keepArmPose(vrm): right after the clip is sampled, keep its pose of the bones the arm pass reads (ARM_POSE_BONES).
    (three's mixer skips a held key, so the JS frame loop needs it; Blender's sampled clip writes every track every frame,
    so in this edition the pair changes a pose only where the clip has no track for one of those bones, exactly as there)"""
    arms.kept = {n: pose[n].copy() for n in ARM_POSE_BONES if pose.get(n) is not None}


def restore_arm_pose(arms, pose):
    """restoreArmPose(vrm): first in the next frame, put the kept clip pose back (a bone the clip leaves holds the clip's
    value, not the pass's)"""
    for n, q in (arms.kept or {}).items():
        pose[n] = q.copy()


def reset_arm_dof(arms, side=None):
    """resetArmDOF(vrm[, side]): the next apply solves that body's wrists (or the one hand) as a fresh load does (the turn
    limit's memo cleared): for a cut or a seek. The shoulder's pitch stage and the kept clip pose are left as they are"""
    for s in ([side] if side else SIDES):
        W = arms.wrist.get(s)
        if W:
            W['memo'] = None


# ------------------------------------------------------------------------------------------------------------- the hands
FINGER_PINS = [f + s for f in ('Index', 'Middle', 'Ring', 'Little') for s in ('Proximal', 'Intermediate', 'Distal')] \
    + ['ThumbProximal', 'ThumbDistal']


def _vunit(v):
    return Vector(v).normalized()


class HandDOF:
    """initHandDOF + applyHandDOF: every finger joint and the thumb's MCP and IP are single pins (the twist about the pin,
    clamped from its flexion at rest); the little finger's MCP + PIP share one 93 deg limit; the thumb's metacarpal sits
    on the ROTOR (opposition about the rest axis Yr, 0..60) carrying the CMC PIN square to it (flexion, 0..87, its coupled
    limit against the stator's lip), solved from the clip's thumb direction (the analytic pair, else the nearest reachable
    pair on a 5 deg grid refined by halving steps); the thumb's MCP and IP then by DIRECTION. After apply(),
    self.rotor_out[side] is the ThumbRotor stage's turn (three's frame) for the keyer; self.side[side]['dbg'] the solve's
    last numbers (handDebug)."""

    def __init__(self, hinges, side, ok):
        self.hinges, self.side, self.ok = hinges, side, ok
        self.rotor_out = {}

    @classmethod
    def from_handle(cls, h, hinges, mute=True):
        meta, rot = hinges.get('leftThumbMetacarpal'), hinges.get('leftThumbRotor')
        side = {}
        for s in SIDES:
            m = 1 if s == 'left' else -1
            helper = s + 'ThumbRotor' if (s + 'ThumbRotor') in h.arm.data.bones else None
            muted = _mute(h, helper, mute) if helper else 0

            def head(n):
                b = h.humanoid.get(s + n)
                return v_to_three(h.rest_head[b]) if b else None
            a, b, c = head('ThumbMetacarpal'), head('ThumbProximal'), head('ThumbDistal')
            m0 = Vector(rot['axis']) if rot else Vector((1.0, 0.0, 0.0))
            if a is not None and b is not None:
                m0 = _vunit((m * (b.x - a.x), b.y - a.y, b.z - a.z))
            s0 = m0
            if b is not None and c is not None:
                s0 = _vunit((m * (c.x - b.x), c.y - b.y, c.z - b.z))
            side[s] = {'helper': helper, 'removed': muted, 'm0': m0, 's0': s0, 'alpha': 0.0, 'beta': 0.0, 'dbg': None}
        return cls(hinges, side, bool(meta and rot))

    def apply(self, pose, stats=None):
        T = self.hinges

        def rng(j):
            return ((j['deg'][0] - j['flex_at_rest']) * D2R, (j['deg'][1] - j['flex_at_rest']) * D2R)
        for side in SIDES:
            m, s = (1 if side == 'left' else -1), self.side[side]
            # 1. the pins: the twist about each pin only, clamped (the thumb's MCP and IP after its metacarpal: 2b)
            turned = {}
            for b in FINGER_PINS:
                if self.ok and b.startswith('Thumb'):
                    continue
                j, k = T.get('left' + b), side + b
                if not j or pose.get(k) is None:
                    continue
                q = _mirror(pose[k], m)
                g = clamp(angle_about(q, j['axis']), *rng(j))
                turned[b] = {'j': j, 'k': k, 'before': q.copy(), 'g': g}
                q = _aa(j['axis'], g)
                pose[k] = _mirror(q, m)
                _note(stats, k, turned[b]['before'], q)
            # the little finger's MCP and PIP share one limit: any excess comes off both pins equally
            lp, li = turned.get('LittleProximal'), turned.get('LittleIntermediate')
            if lp and li:
                over = (lp['g'] * R2D + lp['j']['flex_at_rest']) + (li['g'] * R2D + li['j']['flex_at_rest']) - 93
                if over > 0:
                    def room(t):
                        return max(0.0, t['g'] - rng(t['j'])[0])
                    tot = over * D2R
                    d1 = min(0.5 * tot, room(lp))
                    d2 = min(tot - d1, room(li))
                    d1 = min(tot - d2, room(lp))
                    lp['g'] -= d1
                    li['g'] -= d2
                    for t in (lp, li):
                        q = _aa(t['j']['axis'], t['g'])
                        pose[t['k']] = _mirror(q, m)
                        _note(stats, t['k'], t['before'], q)
            # 2. the thumb's metacarpal: rotor alpha about Yr, then the CMC pin beta about P0 (square to Yr)
            kmc = side + 'ThumbMetacarpal'
            if not self.ok or pose.get(kmc) is None:
                continue
            # (in double precision, as the JS's arrays: the grid search's cost is flat to 1e-7 near its minimum)
            Yr, m0 = _unit(T['leftThumbRotor']['axis']), _d(s['m0'])
            P0 = _unit(_cross(_cross(Yr, T['leftThumbMetacarpal']['axis']), Yr))
            q = _mirror(pose[kmc], m)
            before, qm_clip = q.copy(), q.copy()
            d = _qrot(q, m0)
            A, Bs = _dot(Yr, m0), _dot(Yr, _cross(P0, m0))
            Rn, ph = math.hypot(A, Bs), math.atan2(Bs, A)
            bR, aR = rng(T['leftThumbMetacarpal']), rng(T['leftThumbRotor'])
            c = math.acos(clamp(_dot(Yr, d) / max(Rn, 1e-9), -1.0, 1.0))
            beta = None
            for cand in (wrap_pi(ph + c), wrap_pi(ph - c)):
                bb = clamp(cand, *bR)
                cost = abs(bb - cand) + 1e-3 * abs(bb - s['beta'])
                if beta is None or cost < beta[1]:
                    beta = (bb, cost)
            beta = beta[0]
            mb = _rot(m0, P0, beta)

            def off(w_):
                k_ = _dot(w_, Yr)
                return (w_[0] - k_ * Yr[0], w_[1] - k_ * Yr[1], w_[2] - k_ * Yr[2])
            p1, p2 = off(mb), off(d)
            n1, n2 = math.sqrt(_dot(p1, p1)), math.sqrt(_dot(p2, p2))
            a_dir = math.atan2(_dot(_cross(p1, p2), Yr), _dot(p1, p2)) if n1 > 1e-6 and n2 > 1e-6 else 0.0
            a_tw = _angle_about64(q, Yr)
            w = smooth(4 * D2R, 12 * D2R, math.asin(min(1.0, min(n1, n2))))
            alpha = clamp(a_tw + w * wrap_pi(a_dir - a_tw), *aR)

            def dir_of(a, b):
                return _rot(_rot(m0, P0, b), Yr, a)

            def miss(a, b):
                return 1 - _dot(dir_of(a, b), d)

            def b_max(a):
                o = a * R2D + T['leftThumbRotor']['flex_at_rest']
                lim = 87 if o <= 40 else (87 - 0.1 * (o - 40) if o <= 50 else 86 - 0.7 * (o - 50))
                return min(bR[1], (lim - T['leftThumbMetacarpal']['flex_at_rest']) * D2R)
            if miss(alpha, beta) > 1e-6 or beta > b_max(alpha):
                def cost(a, b):
                    return miss(a, b) + (1 - w) * 0.05 * (a - a_tw) ** 2 + 0.002 * (abs(a - s['alpha']) + abs(b - s['beta']))
                b0 = min(beta, b_max(alpha))
                best = (alpha, b0, cost(alpha, b0))
                a = aR[0]
                while a <= aR[1] + 1e-9:
                    bb = bR[0]
                    while bb <= b_max(a) + 1e-9:
                        e = cost(a, bb)
                        if e < best[2]:
                            best = (a, bb, e)
                        bb += 5 * D2R
                    a += 5 * D2R
                step = 2.5 * D2R
                while step > 0.02 * D2R:
                    moved = True
                    while moved:
                        moved = False
                        for da, db in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
                            a = clamp(best[0] + da, *aR)
                            bb = clamp(best[1] + db, bR[0], b_max(a))
                            e = cost(a, bb)
                            if e < best[2] - 1e-12:
                                best = (a, bb, e)
                                moved = True
                    step /= 2
                alpha, beta = best[0], best[1]
            s['alpha'], s['beta'] = alpha, beta
            s['dbg'] = {'alpha': alpha * R2D, 'beta': beta * R2D, 'aDir': a_dir * R2D, 'aTw': a_tw * R2D, 'w': w,
                        'd': tuple(d)}
            qr = Quaternion(Vector(Yr), alpha)
            q = qr @ Quaternion(Vector(P0), beta)
            pose[kmc] = _mirror(q, m)
            _note(stats, kmc, before, q)
            # 2b. the thumb's MCP and IP pins by DIRECTION: each flexed so its segment points nearest the clip's segment
            our, clip_chain = q.copy(), qm_clip
            for b in ('ThumbProximal', 'ThumbDistal'):
                j, k = T.get('left' + b), side + b
                if not j or pose.get(k) is None:
                    continue
                q = _mirror(pose[k], m)
                before2 = q.copy()
                clip_chain = clip_chain @ q
                u = our.inverted() @ (clip_chain @ s['s0'])
                ax = _vunit(j['axis'])

                def off2(w_, ax=ax):
                    return w_ - ax * w_.dot(ax)
                p1, p2 = off2(s['s0']), off2(u)
                g = math.atan2(p1.cross(p2).dot(ax), p1.dot(p2)) if p1.length > 1e-6 and p2.length > 1e-6 \
                    else angle_about(q, j['axis'])
                q = Quaternion(ax, clamp(g, *rng(j)))
                our = our @ q
                pose[k] = _mirror(q, m)
                _note(stats, k, before2, q)
            # 3. the rotor helper: alpha about Yr (its turn in the VRM's frame; the keyer writes it against the rest)
            if s['helper']:
                self.rotor_out[side] = _mirror(qr, m)


def init_hand_dof(h, hinges, mute=True):
    """initHandDOF(vrm, hinges): the joints file's hinges, the thumb rotors found and their constraints muted -> HandDOF"""
    return HandDOF.from_handle(h, hinges, mute)


def apply_hand_dof(hands, pose, stats=None):
    """applyHandDOF(vrm, stats): each frame after apply_arm_dof"""
    if hands is None:
        return
    return hands.apply(pose, stats)


def hand_debug(hands):
    """handDebug(vrm): the thumb solve's last numbers per side (deg): alpha, beta, aDir, aTw, w, d"""
    return None if hands is None else {s: hands.side[s]['dbg'] for s in SIDES}


# ------------------------------------------------------------------------------------------------- the head and the crown
PETAL_A = [18.4, 49.4, 79.8, 107.4, 128.2, 148.5, -148.5, -128.2, -107.4, -79.8, -49.4, -18.4]
PETAL_REST = 35.0
PETAL_FOLD = [(-6, 100), (-6, 100), (-6, 100), (-6, 100), (10, 100), (30, 100),
              (30, 100), (10, 100), (-6, 100), (-6, 100), (-6, 100), (-6, 100)]
STEM_LOCK = {'roll': 4, 'fold': 70}
CROWN_STATES = {
    'neutral': [35, 35, 35, 35, 35, 35],
    'happy': [2, 8, 16, 26, 36, 44],
    'angry': [-6, 20, 60, 74, 82, 88],
    'sad': [70, 76, 82, 88, 92, 94],
    'relaxed': [55, 58, 60, 62, 64, 66],
    'surprised': [-4, -4, -2, 0, 10, 30],
    'thinking': [0, 0, 0, 0, 10, 30],
    'listening': [28, 28, 28, 28, 28, 30],
    'curious': [-6, 30, 30, 30, 58, 58],
    'resting': [97, 97, 97, 97, 97, 97],
}
CROWN_EMOTIONS = ('happy', 'angry', 'sad', 'relaxed', 'surprised')
HEAD_STATES = {
    'happy': {'pitch': -6, 'roll': 5, 'pan': 0},
    'angry': {'pitch': 8, 'roll': 0, 'pan': 0},
    'sad': {'pitch': 12, 'roll': -3, 'pan': 0},
    'relaxed': {'pitch': 3, 'roll': 3, 'pan': 0},
    'surprised': {'pitch': -8, 'roll': 0, 'pan': 0},
    'curious': {'pitch': -2, 'roll': 9, 'pan': 0},
    'thinking': {'pitch': -6, 'roll': 4, 'pan': 10},
}


def _emotion_weights(weights):
    ws = [float(weights.get(e, 0.0)) for e in CROWN_EMOTIONS]
    s = sum(ws)
    k = 1.0 / s if s > 1 else 1.0
    return ws, k


class HeadState:
    """applyHeadExpression: each emotion's small head pose on top of the animation, moved at the neck actuators' 120 deg/s,
    the sum kept inside the head's built stops (pan / nod / roll split as the stages stack)."""

    def __init__(self):
        self.st = {'pitch': 0.0, 'roll': 0.0, 'pan': 0.0}

    def apply(self, pose, weights, dt, state=None, weight=1.0):
        head, neck = pose.get('head'), pose.get('neck')
        if head is None:
            return
        ws, k = _emotion_weights(weights)
        want = {'pitch': 0.0, 'roll': 0.0, 'pan': 0.0}
        for j, e in enumerate(CROWN_EMOTIONS):
            for c in want:
                want[c] += k * ws[j] * HEAD_STATES[e][c]
        if state and state in HEAD_STATES:
            for c in want:
                want[c] += weight * (HEAD_STATES[state][c] - want[c])
        step = 120.0 * dt
        for c in want:
            self.st[c] += max(-step, min(step, want[c] - self.st[c]))
        q = Quaternion((1.0, 0.0, 0.0), self.st['pitch'] * D2R) @ Quaternion((0.0, 0.0, 1.0), -self.st['roll'] * D2R)
        head = q @ head
        if neck is not None and self.st['pan']:
            neck = Quaternion((0.0, 1.0, 0.0), self.st['pan'] * D2R) @ neck
        nq = neck if neck is not None else Quaternion()
        x, y, z = euler_from_quat(nq @ head, 'YXZ')

        def cl(v, rr):
            return min(rr[1] * D2R, max(rr[0] * D2R, v))
        pan, nod, rl = cl(y, HEAD_RANGE['pan']), cl(x, HEAD_RANGE['x']), cl(z, HEAD_RANGE['z'])
        if pan != y or nod != x or rl != z:
            if neck is not None:
                neck = Quaternion((0.0, 1.0, 0.0), pan)
            head = quat_from_euler(nod, 0.0 if neck is not None else pan, rl, 'YXZ')
        pose['head'] = head
        if neck is not None:
            pose['neck'] = neck


class Crown:
    """applyCrown: each petal's fold phi (deg; 0 radial in the face plane, + folding back, rest 35) blended from the face's
    expression weights, a CROWN_STATES state on top, the look's bias, the built stops (PETAL_FOLD), SPEC's stem interlock
    and the 240 deg/s lead-screw rate. self.phi[i] after apply(); petal_NN's turn is (phi - 35) about its own X.
    (initCrown's petal search: from_handle(h) counts the petal bones the VRM has, `found`.)"""

    def __init__(self, found=12):
        self.phi = [PETAL_REST] * 12
        self.found = found

    @classmethod
    def from_handle(cls, h):
        return cls(sum(1 for i in range(12) if f'petal_{i:02d}' in h.arm.data.bones))

    def apply(self, weights, head_roll_deg, dt, look=0.0, state=None, weight=1.0):
        ws, k = _emotion_weights(weights)
        for i in range(12):
            r = i if i < 6 else 11 - i
            phi = CROWN_STATES['neutral'][r]
            for j, e in enumerate(CROWN_EMOTIONS):
                phi += k * ws[j] * (CROWN_STATES[e][r] - CROWN_STATES['neutral'][r])
            if state and state in CROWN_STATES:
                phi += weight * (CROWN_STATES[state][r] - phi)
            if look:
                phi -= 15.0 * abs(look) * max(0.0, math.cos((PETAL_A[i] - math.copysign(90.0, look)) * D2R))
            lo0, hi = PETAL_FOLD[i]
            toward = head_roll_deg if PETAL_A[i] > 0 else -head_roll_deg
            lo = max(lo0, STEM_LOCK['fold']) if (r == 5 and toward >= STEM_LOCK['roll'] - 1e-6) else lo0
            phi = min(hi, max(lo, phi))
            step = 240.0 * dt
            p = self.phi[i] + max(-step, min(step, phi - self.phi[i]))
            self.phi[i] = min(hi, max(lo0, p))
        return list(self.phi)


def head_roll_deg(pose):
    """the head's roll (deg, + lowering the robot's left side, SPEC's sign), as applyCrown reads it"""
    h = pose.get('head')
    return 0.0 if h is None else -2.0 * math.atan2(h.z, h.w) * R2D


# ------------------------------------------------------------------------------------------- the WebGPU names, one to one
def init_leg_dof(h, mute=True):
    """initLegDOF(vrm): the hip stages' axes from the handle, their VRM constraints muted -> LegStages"""
    return LegStages.from_handle(h, mute)


def init_arm_dof(h, hinges=None, mute=True, wrist=True, mute_wrist=False):
    """initArmDOF(vrm, hinges): the elbow record, the shoulder pitch helpers (constraints muted) and the wrist's stages
    (initWrist; their constraints muted only with mute_wrist, for a caller that keys ArmDOF.wrist_out) -> ArmDOF"""
    return ArmDOF.from_handle(h, hinges, mute, wrist, mute_wrist)


def apply_arm_dof(arms, pose, dt=1.0 / 24.0, clearance=8.0, stats=None):
    """applyArmDOF(vrm, stats, dt, clearance): arms is init_arm_dof's ArmDOF"""
    return arms.apply(pose, dt, clearance, stats)


def init_head_expression():
    """the head actuators' state applyHeadExpression keeps on the vrm -> HeadState"""
    return HeadState()


def apply_head_expression(head, pose, weights, dt, state=None, weight=1.0):
    """applyHeadExpression(vrm, dt, {state, weight}): head is a HeadState; weights the face's {expression: weight}"""
    return head.apply(pose, weights, dt, state, weight)


def init_crown(h=None):
    """initCrown(vrm) -> Crown (with h: its `found` counts the petal bones, as the JS's st.found)"""
    return Crown.from_handle(h) if h is not None else Crown()


def apply_crown(crown, weights, head_roll, dt, look=0.0, state=None, weight=1.0):
    """applyCrown(vrm, dt, {look, state, weight}): crown is init_crown's Crown; head_roll in deg (head_roll_deg(pose));
    -> the 12 petals' folds (deg)"""
    return crown.apply(weights, head_roll, dt, look, state, weight)
