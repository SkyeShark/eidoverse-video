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

dof_pass(body, N, dt) is my robot body's hardware pass on a blended pose (rehome, the arms, the leg clamps: what round
one's Body.clip_pose runs on one clip); for any other VRM it returns N unchanged.
"""

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


def dof_pass(body, N, dt):
    """my body's hardware pass on a whole pose (in place on a copy) -> (N, the shoulder helpers' angles)"""
    if not body.robot:
        return N, {}
    p3 = {n: q_to_three(q) for n, q in N.items()}
    dof.rehome_body(p3)
    body.arms.apply(p3, dt)
    dof.apply_hardware_dof(p3, dof.LEG_JOINTS, None)
    return {n: q_from_three(q) for n, q in p3.items()}, dict(body.arms.helper_phi)


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
