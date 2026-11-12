"""eidoblend.characters.controller.pose: one frame's pose as the controller and its foot IK see it.

A WebGPU frame is a scene graph: the VRM's scene node (the root: the feet's world position, the heading about the up
axis) and three-vrm's normalized humanoid nodes under it (rest = identity, world-aligned). The IK reads a bone's world
position and quaternion and writes a world quaternion back through its parent. Here the same frame is a Pose:

    p = Pose(body, M, N, off)        # M: the armature's world matrix; N: {humanoid name: Quaternion} normalized
                                     # (Blender's axes); off: the hips' offset from its rest head (armature space)
    p.world_pos('leftFoot'), p.world_quat('leftFoot')
    p.set_world_quat('leftFoot', q)          # three's bone.quaternion = parent^-1 * q
    p.apply_world_delta('leftUpperLeg', dq)  # bone.quaternion.premultiply(parent^-1 * dq * parent)

FK runs down the humanoid chain from the hips with the rest heads of round one's Body (the normalized frame is
world-aligned at rest, so a child sits at parent + W_parent @ (rest head - parent's rest head)). The chain's parents are
the rig's own (the nearest humanoid ancestor of each bone).

dof_pass(body, N, dt, reach=None) is my robot body's hardware pass on a blended pose (rehome, the arms, the leg clamps:
what round one's Body.clip_pose runs on one clip), the hands a maneuver holds with solved again through it; for any
other VRM it returns N unchanged.
"""

import math

from mathutils import Matrix, Quaternion, Vector

from .. import robot_dof as dof
from .._math import q_from_three, q_to_three


def humanoid_parents(h):
    """{humanoid name: the nearest humanoid ancestor's name (None for the hips)}"""
    by_bone = {b: n for n, b in h.humanoid.items()}
    out = {}
    for n, b in h.humanoid.items():
        p = h.arm.data.bones[b].parent
        while p is not None and p.name not in by_bone:
            p = p.parent
        out[n] = by_bone[p.name] if p is not None else None
    return out


class Pose:
    def __init__(self, body, M, N, off=None, parents=None):
        self.body = body
        self.M = M
        self.N = N
        self.off = Vector(off) if off is not None else Vector()
        self.parents = parents if parents is not None else body.parents
        self._wq, self._wp = {}, {}

    def copy(self):
        return Pose(self.body, self.M.copy(), dict(self.N), self.off.copy(), self.parents)

    def invalidate(self):
        self._wq.clear()
        self._wp.clear()

    @property
    def root_quat(self):
        return self.M.to_quaternion()

    def world_quat(self, name):
        q = self._wq.get(name)
        if q is None:
            p = self.parents.get(name)
            base = self.root_quat if p is None else self.world_quat(p)
            q = base @ self.N.get(name, Quaternion())
            self._wq[name] = q
        return q

    def world_pos(self, name):
        v = self._wp.get(name)
        if v is None:
            H = self.body.H
            p = self.parents.get(name)
            if p is None:
                v = self.M @ (H[name] + self.off)
            else:
                v = self.world_pos(p) + self.world_quat(p) @ (H[name] - H[p])
            self._wp[name] = v
        return v

    def set_world_quat(self, name, q):
        p = self.parents.get(name)
        base = self.root_quat if p is None else self.world_quat(p)
        self.N[name] = (base.inverted() @ q).normalized()
        self.invalidate()

    def apply_world_delta(self, name, dq):
        p = self.parents.get(name)
        base = self.root_quat if p is None else self.world_quat(p)
        local = base.inverted() @ dq @ base
        self.N[name] = (local @ self.N.get(name, Quaternion())).normalized()
        self.invalidate()


REACH_TOL = 0.005           # a held hand within this of where the contact IK put it needs no re-reach (m)
REACH_ROUNDS = 5            # the re-reach's rounds through the arm pass


def dof_pass(body, N, dt, reach=None):
    """my body's hardware pass on a whole pose (in place on a copy) -> (N, the shoulder helpers' angles).
    reach: {'M', 'off', 'hands': {side: weight}}: the hands the maneuvers' contact IK put on a hold this frame (a lip,
    a wall's top, a rung). The pass stiffens the torso (one waist joint: the clip's chest bend is clamped away) and
    clamps the arm, which carried a planted hand up to a metre off the top it pressed: those hands are solved again
    through the hardware (_reach_through)"""
    if not body.robot:
        return N, {}
    p3 = {n: q_to_three(q) for n, q in N.items()}
    dof.rehome_body(p3)
    if reach and reach.get('hands'):
        p3 = _reach_through(body, N, p3, reach, dt)
    else:
        body.arms.apply(p3, dt)
    dof.apply_hardware_dof(p3, dof.LEG_JOINTS, None)
    return {n: q_from_three(q) for n, q in p3.items()}, dict(body.arms.helper_phi)


def _arm_state(arms):
    """the arm pass's state between frames (each shoulder's rate-limited pitch stage, each wrist's turn-limit memo and
    its last solution, the helpers' outputs): to try a pose through the pass and put the state back"""
    keys = ('memo', 'a', 'b', 'c', 'asked')
    return (dict(arms.phi), {s: {k: W.get(k) for k in keys} for s, W in arms.wrist.items()}, dict(arms.helper_phi),
            dict(arms.wrist_out))


def _set_arm_state(arms, st):
    phi, wr, hp, wo = st
    arms.phi = dict(phi)
    for s, d in wr.items():
        arms.wrist[s].update(d)
    arms.helper_phi, arms.wrist_out = dict(hp), dict(wo)


def _arm_to(p, side, target, w_hand=None):
    """the two-bone arm solve on the Pose p at full weight (no guard), the hand keeping the world turn w_hand"""
    up, mid, end = side + 'UpperArm', side + 'LowerArm', side + 'Hand'
    a, b, e = p.world_pos(up).copy(), p.world_pos(mid).copy(), p.world_pos(end).copy()
    lu, ll = (a - b).length, (b - e).length
    dist = min(max((a - target).length, abs(lu - ll) + 0.02), lu + ll - 0.003)
    desired = math.acos(max(-1.0, min(1.0, (lu * lu + ll * ll - dist * dist) / (2 * lu * ll))))
    vba, vbc = a - b, e - b
    axis = vbc.cross(vba)
    if axis.length_squared > 1e-10:
        p.apply_world_delta(mid, Quaternion(axis.normalized(), vba.angle(vbc, 0.0) - desired))
    e2 = p.world_pos(end).copy()
    if (e2 - a).length > 1e-6 and (target - a).length > 1e-6:
        p.apply_world_delta(up, (e2 - a).normalized().rotation_difference((target - a).normalized()))
    if w_hand is not None:
        p.set_world_quat(end, w_hand)
    p.invalidate()


def _reach_through(body, N_ik, p3, reach, dt):
    """the held hands through my hardware: the arm pass on the rehomed pose as it is; where a held hand lands off the
    place the contact IK gave it (weighted by the hold: at 0 the pass's own hand, at 1 the IK's), the arm is solved
    again toward it from the rehomed shoulder, the hand keeping the IK's world turn, and run through the pass, the aim
    moved by what the pass still takes off each round (its joint clamps and its pitch stage's rate). The arm state the
    pass carries between frames is put back before each try; the best try's pose and state are kept -> three-frame pose"""
    M, off = reach['M'], reach['off']
    sides = [s for s, w in reach['hands'].items() if w > 0.01 and (s + 'Hand') in N_ik]
    P_ik = Pose(body, M, dict(N_ik), off)
    want = {s: P_ik.world_pos(s + 'Hand').copy() for s in sides}
    turn = {s: P_ik.world_quat(s + 'Hand').copy() for s in sides}
    st0 = _arm_state(body.arms)

    def run(p3_in):
        _set_arm_state(body.arms, st0)
        out = dict(p3_in)
        body.arms.apply(out, dt)
        P = Pose(body, M, {n: q_from_three(q) for n, q in out.items()}, off)
        return out, {s: P.world_pos(s + 'Hand').copy() for s in sides}, _arm_state(body.arms)
    out, got, st = run(p3)
    goal = {s: got[s] + (want[s] - got[s]) * min(1.0, reach['hands'][s]) for s in sides}
    err = max(((goal[s] - got[s]).length for s in sides), default=0.0)
    best = (err, out, st)
    if err > REACH_TOL:
        base = {n: q_from_three(q) for n, q in p3.items()}
        aim = {s: goal[s].copy() for s in sides}
        for _round in range(REACH_ROUNDS):
            P = Pose(body, M, dict(base), off)
            for s in sides:
                _arm_to(P, s, aim[s], turn[s])
            out, got, st = run({n: q_to_three(q) for n, q in P.N.items()})
            miss = {s: goal[s] - got[s] for s in sides}
            err = max(v.length for v in miss.values())
            if err < best[0]:
                best = (err, out, st)
            if err <= REACH_TOL:
                break
            for s in sides:
                aim[s] = aim[s] + miss[s]
    _set_arm_state(body.arms, best[2])
    return best[1]


def leg_clamps(body, N):
    """the leg joints' clamps alone (the analysis' view of a clip on my legs)"""
    if not body.robot:
        return N
    p3 = {n: q_to_three(N[n]) for s in ('left', 'right') for n in (s + 'UpperLeg', s + 'LowerLeg', s + 'Foot', s + 'Toes')
          if n in N}
    dof.apply_hardware_dof(p3, dof.LEG_JOINTS, None)
    out = dict(N)
    out.update({n: q_from_three(q) for n, q in p3.items()})
    return out


def root_matrix(x, y, z, heading):
    """the armature's world matrix for a feet position and a heading (rad about +Z; 0 faces -Y)"""
    return Matrix.Translation(Vector((x, y, z))) @ Quaternion((0.0, 0.0, 1.0), heading).to_matrix().to_4x4()
