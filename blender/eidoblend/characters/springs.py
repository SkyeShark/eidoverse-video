"""eidoblend.characters.springs: VRM spring bones simulated once, in frame order, and baked to keys (claudesona.md,
"Spring bones").

    from eidoblend.characters import load_vrm, play_vrma_default
    from eidoblend.characters.springs import bake_springs
    me = load_vrm('aletheia')
    play_vrma_default(me, 'idle')                       # the body's motion first: the springs follow it
    rep = bake_springs(me, 1, 240)                      # every spring chain keyed, LINEAR, on its own NLA track

The WebGPU engine steps three-vrm's springBoneManager inside vrm.update(dt), once per rendered frame, after the body has
taken that frame's pose (render_scene.mjs), and calls springBoneManager.reset() wherever a character is teleported
(seatOn, the turntable's blocks). bake_springs does the same once at build time and keys the result, so a saved .blend
plays and renders any frame on its own:

    `preroll` seconds held on frame f0's pose first, so the chains start settled (0 = the engine's cold start)
    for each frame f0..f1:
        scene.frame_set(f)                  the body's pose at f (clips, walk, constraints: whatever drives it)
        reset at f if f is in `resets`     (springBoneManager.reset(): a teleport)
        overrides at f                      (the wardrobe's petal folds: each chain's initial state and colliders)
        step the springs                    `rate`: 'frame' = one step of dt = 1/fps (the engine's vrm.update),
                                            or steps per second (60 = the add-on's own schedule)
        the tie limiter (opt-in)            render_scene.mjs's wrapper on vrm.update, as it was meant to work:
                                            claude_suit's tie blade kept within `tie_limit_deg` of world down
    -> one action: each joint's rotation_quaternion (and a folded petal's scale) per frame, LINEAR, on the NLA
       track '<name>|springs' (the body's tracks and its active action key no spring bone, so nothing fights it).

The tie limiter is OFF by default because the engine's own is inert: three-vrm 3.5.2 sets matrixAutoUpdate = false on
every spring joint bone, so the wrapper's write to tie_1.quaternion never reaches tie_1.matrix (its
updateWorldMatrix(false, true) keeps the spring's matrix) and is overwritten on the next update. Measured with the
engine's three-vrm: the tie's moving point is identical with and without the wrapper (tests/claudesona/test_springs.py).
So every WebGPU film shows the free tie, and the default bake matches them. At rest the free blade hangs 19.4 deg off
straight down, following the belly forward; tie_limit_deg=10 (the wrapper's intent) pulls its tip about 18 mm back,
into the shirt, so use it only where a lively tie must not fly.

Two solvers, the same VRMC_springBone 1.0 maths (a verlet tail, stiffness toward the initial direction, gravity in
world space, the length kept, colliders pushing the tail out, the bone turned to the tail):
    solver='three'   (default) a port of three-vrm 3.5.2's VRMSpringBoneJoint / VRMSpringBoneManager, the engine's
                     own: joints sorted parents first, each one's world carried down the chain, tails kept in the
                     spring's center space, each joint's child offset read from the VRM's node transforms in float64 as
                     three-vrm reads it. It also takes what three-vrm's API offers and the wardrobe uses: a joint's
                     initial local rotation and scale (setInitState after a fold) and its collider groups.
    solver='addon'   the VRM Add-on for Blender's own step (spring_bone1.handler.update_pose_bone_rotations), called
                     with the same dt after the frame's pose is evaluated; it has no initial-state override, and it
                     takes the tail back from world positions in float32, so a zero-length joint (aletheia's four cat
                     tails have one each) turns on rounding noise: their tips land up to 136 mm from three-vrm's.
Both read the springs, joints, colliders and collider groups from the add-on's property groups (the VRM's
VRMC_springBone as imported). The add-on's frame-change spring handler is held off during the bake and its
enable_animation stays off, so nothing re-simulates at render time.

`length` is the one place three-vrm departs from the spec. three-vrm 3.5.2 measures a joint's length
(_calcWorldSpaceBoneLength) to its child's matrixWorld as the last matrix refresh left it: this frame's root, but the
child's previous-frame pose (spring joints have matrixAutoUpdate off and the manager never refreshes a joint's children
before it steps). So while the body moves, the verlet tail is held at a length stretched or shrunk by the chain's own
travel since the last frame, and the swing differs. length='engine' (default) reproduces it, so a bake matches the
WebGPU films' springs (claude_suit: 0.001 mm from three-vrm on every joint and frame of a turn and a nod); length='true'
is the bone's real length now, as the add-on and the spec do (the port then matches the add-on's step within 0.31 mm).
On aletheia the cat tails still differ from three-vrm by up to 10 mm at their tips: their bones carry 0.5 % non-uniform
node scales, which a Blender rest pose cannot hold, so three-vrm's segments change length by up to 0.5 % as they
swing and Blender's do not (every other aletheia joint is within 1 mm).

Lower level, mirroring three-vrm's manager (vrm.springBoneManager):
    rig = SpringRig(me)                 # joints (pairs of a spring's joints), colliders, groups
    rig.read_pose(); rig.set_init_state(); rig.reset(); rig.update(dt)
    rig.override(bone, basis=Quaternion, scale=1.0, colliders=False)   # a joint's initial state (a fold)
    rig.basis()                         # {bone: (Quaternion basis, scale)} as simulated now
"""

import math
from decimal import ROUND_FLOOR, Decimal

import bpy
from mathutils import Matrix, Quaternion, Vector

DEFAULT_TIE_LIMIT_DEG = 10.0      # globalThis._tieSwingMaxDeg's default in render_scene.mjs (opt-in: see above)
TIE_TIP_LIMIT_DEG = 8.0           # the tip's own cone (min(limit, 8 deg)) in the same wrapper
_EPS = 1e-12


class _Collider:
    __slots__ = ('bone', 'kind', 'offset', 'tail', 'radius', 'inside', 'normal')

    def __init__(self, bone, kind, offset, radius=0.0, tail=None, inside=False, normal=None):
        self.bone, self.kind, self.offset, self.radius = bone, kind, Vector(offset), float(radius)
        self.tail = Vector(tail) if tail is not None else None
        self.inside, self.normal = bool(inside), Vector(normal) if normal is not None else None


class _Joint:
    """one three-vrm VRMSpringBoneJoint: `bone` turned toward `child` (the next joint of its spring)"""
    __slots__ = ('bone', 'child', 'parent', 'spring', 'stiffness', 'drag', 'gravity_power', 'gravity_dir', 'hit_radius',
                 'groups', 'groups0', 'center', 'rest_local', 'child_local', 'axis', 'init_basis', 'init_scale',
                 'basis', 'scale', 'cur_tail', 'prev_tail', 'gltf')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def _gltf_child_offsets(path):
    """{(spring index, joint index): the child's rest position minus the joint's, armature space (Blender axes)} from
    the VRM's own node transforms in float64, as three-vrm reads them. Blender's bone heads are float32: for a
    zero-length joint (aletheia's cat tails: a child 8e-8 m from its bone) their difference is noise of its own, and the
    joint's axis, which three-vrm takes from the file, would point elsewhere. {} when the file can't be read."""
    import numpy as np
    try:
        from .vrm import glb_json
        g = glb_json(path)
    except Exception:  # noqa: BLE001 (any unreadable file: the bone heads are used instead)
        return {}
    nodes = g.get('nodes', [])
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i

    def local(n):
        if 'matrix' in n:
            return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T
        x, y, z, w = n.get('rotation', (0.0, 0.0, 0.0, 1.0))
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], dtype=np.float64)
        M = np.eye(4)
        M[:3, :3] = R * np.array(n.get('scale', (1.0, 1.0, 1.0)), dtype=np.float64)
        M[:3, 3] = n.get('translation', (0.0, 0.0, 0.0))
        return M
    cache = {}

    def world(i):
        if i not in cache:
            cache[i] = (world(parent[i]) @ local(nodes[i])) if i in parent else local(nodes[i])
        return cache[i]
    out = {}
    sb = g.get('extensions', {}).get('VRMC_springBone', {})
    for si, s in enumerate(sb.get('springs', [])):
        js = [jj['node'] for jj in s.get('joints', [])]
        for k, (a, b) in enumerate(zip(js, js[1:])):
            d = world(b)[:3, 3] - world(a)[:3, 3]
            out[(si, k)] = Vector((float(d[0]), float(-d[2]), float(d[1])))      # three (x, y, z) -> Blender (x, -z, y)
    return out


def _addon_handler_module():
    import importlib
    for name in ('bl_ext.blender_org.vrm.editor.spring_bone1.handler', 'io_scene_vrm.editor.spring_bone1.handler'):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


class SpringRig:
    """the VRM's springs as three-vrm builds them, over the add-on's data. h: a VRMHandle (characters.vrm)."""

    def __init__(self, h, tie_limit_deg=None, length='engine'):
        if length not in ('true', 'engine'):
            raise ValueError(f"SpringRig length={length!r}: 'true' or 'engine'")
        self.length = length
        self.h, self.arm = h, h.arm
        sb = self.arm.data.vrm_addon_extension.spring_bone1
        pbs, bones = self.arm.pose.bones, self.arm.data.bones
        colliders = {}
        for c in sb.colliders:
            bn = c.node.bone_name
            if not c.uuid or bn not in pbs:
                continue
            ex = c.extensions.vrmc_spring_bone_extended_collider
            if ex.enabled:
                st = ex.shape_type
                if st == ex.SHAPE_TYPE_EXTENDED_SPHERE.identifier:
                    s = ex.shape.sphere
                    colliders[c.uuid] = _Collider(bn, 'sphere', s.offset, s.radius, inside=s.inside)
                elif st == ex.SHAPE_TYPE_EXTENDED_CAPSULE.identifier:
                    s = ex.shape.capsule
                    colliders[c.uuid] = _Collider(bn, 'capsule', s.offset, s.radius, tail=s.tail, inside=s.inside)
                elif st == ex.SHAPE_TYPE_EXTENDED_PLANE.identifier:
                    s = ex.shape.plane
                    colliders[c.uuid] = _Collider(bn, 'plane', s.offset, normal=s.normal)
                continue
            if c.shape_type == c.SHAPE_TYPE_SPHERE.identifier:
                s = c.shape.sphere
                colliders[c.uuid] = _Collider(bn, 'sphere', s.offset, s.radius)
            elif c.shape_type == c.SHAPE_TYPE_CAPSULE.identifier:
                s = c.shape.capsule
                colliders[c.uuid] = _Collider(bn, 'capsule', s.offset, s.radius, tail=s.tail)
        self.colliders = list(colliders.values())
        self.groups, self.group_names = {}, {}
        for g in sb.collider_groups:
            self.groups[g.uuid] = [colliders[r.collider_uuid] for r in g.colliders if r.collider_uuid in colliders]
            self.group_names[g.uuid] = g.vrm_name
        self.joints, self.springs = [], []
        for si, s in enumerate(sb.springs):
            groups = [self.groups[r.collider_group_uuid] for r in s.collider_groups if r.collider_group_uuid in self.groups]
            center = s.center.bone_name if s.center.bone_name in pbs else None
            made = []
            js = list(s.joints)
            for k, (a, b) in enumerate(zip(js, js[1:])):
                ba, bb = a.node.bone_name, b.node.bone_name
                if ba not in pbs or bb not in pbs:
                    continue
                anc = bones[bb].parent                  # a joint pair must be a chain (three-vrm's child)
                while anc is not None and anc.name != ba:
                    anc = anc.parent
                if anc is None:
                    break
                gd = Vector(a.gravity_dir)
                made.append(_Joint(bone=ba, child=bb, parent=bones[ba].parent.name if bones[ba].parent else None,
                                   spring=s.vrm_name, stiffness=float(a.stiffness), drag=float(a.drag_force),
                                   gravity_power=float(a.gravity_power), gravity_dir=gd, hit_radius=float(a.hit_radius),
                                   groups=list(groups), groups0=list(groups), center=center, gltf=(si, k)))
            self.springs.append({'name': s.vrm_name, 'joints': [j.bone for j in made],
                                 'tip': made[-1].child if made else None, 'center': center,
                                 'collider_groups': [self.group_names.get(r.collider_group_uuid, '') for r in s.collider_groups]})
            self.joints.extend(made)
        depth, order = {}, {b.name: i for i, b in enumerate(bones)}

        def dep(b):
            if b.name not in depth:
                depth[b.name] = 0 if b.parent is None else dep(b.parent) + 1
            return depth[b.name]
        for b in bones:
            dep(b)
        self.joints.sort(key=lambda j: (depth[j.bone], order[j.bone]))    # parents first (three's _sortJoints)
        self.by_bone = {j.bone: j for j in self.joints}
        self.first = {}
        file_d = _gltf_child_offsets(h.path) if getattr(h, 'path', None) else {}
        self.file_offsets = 0
        for j in self.joints:
            self.first.setdefault(j.spring, j.bone)
            br, cr = bones[j.bone].matrix_local, bones[j.child].matrix_local
            pr = bones[j.parent].matrix_local if j.parent else Matrix()
            j.rest_local = pr.inverted_safe() @ br                     # the bone in its parent's frame at rest
            j.child_local = (br.inverted_safe() @ cr).to_translation()  # three's child.position
            d = file_d.get(j.gltf)                                     # the same offset from the file, in float64
            if d is not None and (d - (cr.to_translation() - br.to_translation())).length < 1e-4:
                j.child_local = br.to_3x3().normalized().inverted() @ d
                self.file_offsets += 1
            j.axis = j.child_local.normalized()                        # three's _boneAxis
            j.init_basis, j.init_scale = Quaternion(), 1.0
            j.basis, j.scale = Quaternion(), 1.0
        # what lies under a spring bone is recomputed by FK from the simulated chain
        self._below = set()
        for b in bones:
            p = b.parent
            while p is not None:
                if p.name in self.by_bone:
                    self._below.add(b.name)
                    break
                p = p.parent
        self._local_rest = {b.name: ((b.parent.matrix_local.inverted_safe() @ b.matrix_local) if b.parent else b.matrix_local)
                            for b in bones}
        self.tie = ('tie_1' in self.by_bone and 'tie_2' in pbs) and tie_limit_deg is not None
        self.tie_limit_deg = tie_limit_deg
        self.tie_clamped = False
        self._tie_rest2 = None
        self._mw, self._cache = {}, {}
        self._root = self.arm.matrix_world.copy()
        self._child_prev = {}             # length='engine': each joint's child, armature space, as last refreshed

    # ------------------------------------------------------------------------------------------- world matrices
    def read_pose(self):
        """the evaluated pose (after scene.frame_set) of every bone not under a spring bone, Blender world"""
        mw = self.arm.matrix_world
        self._root = mw.copy()
        self._mw = {pb.name: mw @ pb.matrix for pb in self.arm.pose.bones}
        self._cache = {}

    def _refresh_children(self, bones=None):
        """three-vrm's matrix refresh: each joint's child where the current state puts it (armature space; the next
        step sees it through that step's root, as vrm.scene.updateMatrixWorld does before vrm.update)"""
        inv = self._root.inverted_safe()
        for j in self.joints:
            if bones is None or j.bone in bones:
                self._child_prev[j.bone] = inv @ (self.world(j.bone) @ j.child_local)

    def _local(self, j, basis=None, scale=None):
        q = j.basis if basis is None else basis
        s = j.scale if scale is None else scale
        return j.rest_local @ q.to_matrix().to_4x4() @ Matrix.Diagonal((s, s, s, 1.0))

    def world(self, bone):
        """a bone's world matrix now: simulated for spring bones and anything under them, evaluated otherwise"""
        m = self._cache.get(bone)
        if m is not None:
            return m
        j = self.by_bone.get(bone)
        if j is not None:
            pw = self.world(j.parent) if j.parent else self.arm.matrix_world
            m = pw @ self._local(j)
        elif bone in self._below:
            b = self.arm.data.bones[bone]
            m = self.world(b.parent.name) @ self._local_rest[bone] @ self.arm.pose.bones[bone].matrix_basis
        else:
            m = self._mw[bone]
        self._cache[bone] = m
        return m

    def _drop_below(self, bone):
        self._cache.pop(bone, None)
        for k in [k for k in self._cache if k in self._below]:
            del self._cache[k]

    # ------------------------------------------------------------------------------------------- three-vrm's API
    def override(self, bone, basis=None, scale=None, colliders=None):
        """a joint's initial state (three: bone.quaternion / scale before setInitState) and its collider groups:
        basis None = rest; colliders True / False = its spring's own / none (a folded petal springs freely)"""
        j = self.by_bone.get(bone)
        if j is None:
            raise KeyError(f'{bone!r} is not a spring joint of {self.h.name}')
        j.init_basis = Quaternion() if basis is None else Quaternion(basis).normalized()
        j.init_scale = 1.0 if scale is None else float(scale)
        if colliders is not None:
            j.groups = list(j.groups0) if colliders else []

    def set_init_state(self, bones=None):
        """three's setInitState() / reset(): each joint at its initial rotation, its tail re-seated there"""
        for j in self.joints:
            if bones is not None and j.bone not in bones:
                continue
            j.basis, j.scale = j.init_basis.copy(), j.init_scale
        self._cache = {}
        for j in self.joints:
            if bones is not None and j.bone not in bones:
                continue
            tail = self.world(j.bone) @ j.child_local
            c = self.world(j.center) if j.center else None
            j.cur_tail = (c.inverted_safe() @ tail) if c is not None else tail.copy()
            j.prev_tail = j.cur_tail.copy()
        self._refresh_children(bones)

    reset = set_init_state

    def update(self, dt):
        """three-vrm's VRMSpringBoneManager.update(delta): every joint in order, each one's world carried down"""
        if dt <= 0:
            return
        self._cache = {}
        for j in self.joints:
            pw = self.world(j.parent) if j.parent else self.arm.matrix_world
            init_w = pw @ self._local(j, j.init_basis, j.init_scale)
            wb = pw @ self._local(j)
            bpos = wb.to_translation()
            cp = self._child_prev.get(j.bone) if self.length == 'engine' else None
            if cp is not None:                                                  # three-vrm: the child as last refreshed
                length = ((self._root @ cp) - bpos).length
            else:
                length = ((wb @ j.child_local) - bpos).length                   # the bone's real length now
            axis_w = (init_w.to_3x3() @ j.axis).normalized()                    # worldSpaceBoneAxis
            c = self.world(j.center) if j.center else None
            nxt = j.cur_tail + (j.cur_tail - j.prev_tail) * (1.0 - j.drag)       # verlet, center space
            if c is not None:
                nxt = c @ nxt
            nxt = nxt + axis_w * (j.stiffness * dt) + j.gravity_dir * (j.gravity_power * dt)
            d = nxt - bpos
            dirv = d / d.length if d.length > _EPS else None
            if dirv is not None:
                nxt = bpos + dirv * length
            for grp in j.groups:
                for col in grp:
                    hit = _collide(col, self.world(col.bone), nxt, j.hit_radius, bpos, length)
                    if hit is not nxt:
                        nxt = hit
                        dirv = (nxt - bpos).normalized()
            j.prev_tail = j.cur_tail
            j.cur_tail = (c.inverted_safe() @ nxt) if c is not None else nxt.copy()
            # the bone turned toward the tail: from the head -> tail DIRECTION (mathutils is float32: a tail a few
            # 1e-8 m from its head, as on a zero-length joint, is lost if it is taken back from world positions)
            loc = (init_w.to_3x3().inverted_safe() @ dirv) if dirv is not None else Vector()
            if loc.length > _EPS:
                j.basis = (j.init_basis @ j.axis.rotation_difference(loc.normalized())).normalized()
            j.scale = j.init_scale
            self._drop_below(j.bone)
        if self.tie:
            self.tie_clamped = self._tie_limit()
        if self.length == 'engine':
            self._refresh_children()

    def _tie_limit(self):
        """render_scene.mjs's tie-blade swing limiter: the world vector tie_1 -> tie_2 kept within tie_limit_deg of
        world down (0 pins it straight down) by turning tie_1, then tie_2 within its own small cone of its first pose.
        Returns whether it turned tie_1."""
        j = self.by_bone['tie_1']
        lim = math.radians(self.tie_limit_deg)
        self._cache = {}
        w1 = self.world('tie_1')
        d = self.world('tie_2').to_translation() - w1.to_translation()
        down = Vector((0.0, 0.0, -1.0))
        acted = False
        if d.length > 1e-9:
            d.normalize()
            ang = d.angle(down, 0.0)
            if ang > lim + 1e-4:
                full = down.rotation_difference(d)
                target = Quaternion().slerp(full, lim / ang) @ down
                corr = d.rotation_difference(target)
                pw = self.world(j.parent) if j.parent else self.arm.matrix_world
                w_new = corr.to_matrix() @ w1.to_3x3().normalized()
                pre = pw.to_3x3().normalized() @ j.rest_local.to_3x3().normalized()
                j.basis = (pre.inverted() @ w_new).to_quaternion().normalized()
                self._cache = {}
                acted = True
        j2 = self.by_bone.get('tie_2')            # the chain's end on claude_suit: never turned, so this holds
        if j2 is not None:
            if self._tie_rest2 is None:
                self._tie_rest2 = j2.basis.copy()
            else:
                tip = min(lim, math.radians(TIE_TIP_LIMIT_DEG))
                a2 = self._tie_rest2.rotation_difference(j2.basis).angle
                if a2 > tip:
                    j2.basis = self._tie_rest2.slerp(j2.basis, tip / a2)
        return acted

    def basis(self):
        return {j.bone: (j.basis.copy(), j.scale) for j in self.joints}

    def tails(self):
        """{bone: world position of its child} now (the chains' moving points)"""
        self._cache = {}
        return {j.bone: self.world(j.bone) @ j.child_local for j in self.joints}


def _collide(col, cm, tail, radius, bpos, length):
    """three-vrm's VRMSpringBoneColliderShape*.calculateCollision + the joint's push-out and length restore"""
    pos = cm @ col.offset
    if col.kind in ('sphere', 'capsule'):
        t = tail - pos
        if col.kind == 'capsule':
            ax = (cm @ col.tail) - pos
            lsq = ax.length_squared
            dot = ax.dot(t)
            if dot > 0:
                t = t - ax if lsq <= dot else t - ax * (dot / lsq)
        L = t.length
        dist = (col.radius - radius - L) if col.inside else (L - radius - col.radius)
        if dist >= 0 or L <= _EPS:
            return tail
        n = -t / L if col.inside else t / L
    elif col.kind == 'plane':
        n = (cm.to_3x3().inverted_safe().transposed() @ col.normal).normalized()
        dist = (tail - pos).dot(n) - radius
        if dist >= 0:
            return tail
    else:
        return tail
    tail = tail + n * (-dist)
    d = tail - bpos
    return bpos + d * (length / d.length) if d.length > _EPS else tail


def _n_steps(t0, t1, rate):
    """solver steps in (t0, t1] at `rate` per second, counted on an exact grid (the add-on's Decimal schedule)"""
    r = Decimal(str(rate))
    n0 = int((Decimal(repr(t0)) * r).to_integral_value(rounding=ROUND_FLOOR))
    n1 = int((Decimal(repr(t1)) * r).to_integral_value(rounding=ROUND_FLOOR))
    return max(0, n1 - n0)


def _remove_track(h, tname):
    ad = h.arm.animation_data
    if ad is None:
        return
    for tr in list(ad.nla_tracks):
        if tr.name == tname:
            for st in list(tr.strips):
                if st.action is not None and st.action.users <= 1 + int(st.action.use_fake_user):
                    bpy.data.actions.remove(st.action)
            ad.nla_tracks.remove(tr)


def key_track(h, tname, series, f0, scale_bones=()):
    """series {bone: [(frame, Quaternion, scale)]} -> one action on an NLA track named tname (above the others)"""
    from bpy_extras import anim_utils
    arm = h.arm
    ad = arm.animation_data or arm.animation_data_create()
    act = bpy.data.actions.new(tname)
    slot = act.slots.new(id_type='OBJECT', name=arm.name)
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    n = 0
    for b, lst in series.items():
        paths = [('rotation_quaternion', 4, lambda q, s, i: q[i])]
        if b in scale_bones or any(abs(s - 1.0) > 1e-9 for _f, _q, s in lst):
            paths.append(('scale', 3, lambda q, s, i: s))
        for prop, cnt, get in paths:
            for i in range(cnt):
                fc = cb.fcurves.new(f'pose.bones["{b}"].{prop}', index=i, group_name=b)
                fc.keyframe_points.add(len(lst))
                fc.keyframe_points.foreach_set('co', [c for f, q, s in lst for c in (f, get(q, s, i))])
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                fc.update()
                n += len(lst)
    act.use_fake_user = True
    track = ad.nla_tracks.new()
    track.name = tname
    strip = track.strips.new(tname, int(f0), act)
    if hasattr(strip, 'action_slot'):
        strip.action_slot = slot
    strip.blend_type = 'REPLACE'
    strip.extrapolation = 'HOLD'
    strip.use_auto_blend = False
    return act, track, n


def bake_springs(h, f0, f1, solver='three', rate='frame', preroll=1.0, resets=(), overrides=None, tie_limit_deg=None,
                 length=None, hide_meshes=True, scene=None, log=None):
    """simulate h's springs over frames f0..f1 in order and key them; returns a report:
       solver, rate, frames, springs, joints, steps, preroll_steps, resets, action, track, keys,
       swing_deg {spring: the most its first joint turned from its initial state}, tie_clamped_frames,
       max_tail_speed_mps, nan (must be 0), spring_list
    rate: 'frame' (one step per frame, dt = 1/fps: the engine) or steps per second (60: the add-on's viewport)
    overrides: {frame: {bone: {'basis': Quaternion | None, 'scale': float, 'colliders': bool}}} (the wardrobe's petal
    folds; h.spring_overrides when not given); tie_limit_deg: None (default: the free tie every WebGPU film shows, the
    engine's limiter being inert), a cone in degrees, or 'engine' (the wrapper's own 10 deg); length: 'engine'
    (three-vrm's, the default for solver 'three') or 'true' (the bone's real length; the only one solver 'addon' has)"""
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt = 1.0 / fps
    if overrides is None:
        overrides = getattr(h, 'spring_overrides', None) or {}
    if solver not in ('three', 'addon'):
        raise ValueError(f"bake_springs solver={solver!r}: 'three' or 'addon'")
    if length is None:
        length = 'engine' if solver == 'three' else 'true'
    if solver == 'addon' and length != 'true':
        raise ValueError("bake_springs: the add-on's solver measures the real bone length; length='engine' needs solver='three'")
    if solver == 'addon' and overrides:
        raise ValueError("bake_springs: the add-on's solver has no initial-state override (the wardrobe's petal folds); "
                         "use solver='three' (or 'auto')")
    if rate != 'frame' and not (isinstance(rate, (int, float)) and rate > 0):
        raise ValueError(f"bake_springs rate={rate!r}: 'frame' or steps per second")
    lim = DEFAULT_TIE_LIMIT_DEG if tie_limit_deg in ('engine', 'auto') else tie_limit_deg
    arm = h.arm
    rig = SpringRig(h, tie_limit_deg=lim, length=length)
    bones = [j.bone for j in rig.joints]
    resets = sorted(set(int(r) for r in resets))
    tname = f'{h.name}|springs'
    _remove_track(h, tname)
    for b in bones:
        pb = arm.pose.bones[b]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    hidden = []
    if hide_meshes:                       # the meshes need no evaluation while the springs bake
        for o in h.meshes:
            if not o.hide_viewport:
                o.hide_viewport = True
                hidden.append(o)
    ext = arm.data.vrm_addon_extension.spring_bone1
    anim0 = ext.enable_animation
    mod = _addon_handler_module()
    held = []
    if mod is not None:                   # the add-on's own frame-change step would run on every frame_set
        for fn in list(bpy.app.handlers.frame_change_pre):
            if fn is getattr(mod, 'frame_change_pre', None):
                bpy.app.handlers.frame_change_pre.remove(fn)
                held.append(fn)
    series = {b: [] for b in bones}
    swing, speeds, prev_tip = {}, [], {}
    steps, nan, clamped = 0, 0, 0
    over_frames = sorted(overrides)

    def apply_overrides(fr):
        for bone, o in (overrides.get(fr) or {}).items():
            if bone in rig.by_bone:
                rig.override(bone, basis=o.get('basis'), scale=o.get('scale'), colliders=o.get('colliders'))

    def addon_reset():
        for b in bones:
            arm.pose.bones[b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        for s in ext.springs:
            s.animation_state.use_center_space = False
            for jn in s.joints:
                jn.animation_state.initialized_as_tail = False

    def step(sdt):
        nonlocal steps, clamped
        if solver == 'three':
            rig.update(sdt)
        else:
            mod.update_pose_bone_rotations(bpy.context, sdt)
        steps += 1

    def n_for(t_prev, t):
        return 1 if rate == 'frame' else _n_steps(t_prev, t, rate)

    def sync_from_pose():
        for j in rig.joints:
            j.basis = arm.pose.bones[j.bone].rotation_quaternion.copy()
            j.scale = 1.0

    def write_pose():
        for j in rig.joints:
            pb = arm.pose.bones[j.bone]
            pb.rotation_quaternion = j.basis
            pb.scale = (j.scale, j.scale, j.scale)

    try:
        if solver == 'addon':
            if mod is None:
                raise RuntimeError('bake_springs: the VRM add-on spring handler is not importable')
            ext.enable_animation = True
        scene.frame_set(f0)
        for fo in over_frames:
            if fo <= f0:
                apply_overrides(fo)
        rig.read_pose()
        rig.set_init_state()
        if solver == 'addon':
            addon_reset()
        sdt_frame = dt if rate == 'frame' else 1.0 / rate
        for k in range(int(round(preroll * fps))):           # frame f0's pose held: the chains settle into it
            for _ in range(n_for(k * dt, (k + 1) * dt)):
                step(sdt_frame)
            if solver == 'three':
                write_pose()
        rep_pre = steps
        t_prev = -dt
        for f in range(f0, f1 + 1):
            t = (f - f0) * dt
            scene.frame_set(f)
            if solver == 'three':
                rig.read_pose()
                if f > f0 and f in overrides:
                    apply_overrides(f)
                    rig.set_init_state([b for b in overrides[f] if b in rig.by_bone])
                if f in resets:
                    rig.set_init_state()
                for _ in range(n_for(t_prev, t)):
                    step(sdt_frame)
                if rig.tie and rig.tie_clamped:
                    clamped += 1
                write_pose()
            else:
                if f in resets:
                    addon_reset()
                for _ in range(n_for(t_prev, t)):
                    step(sdt_frame)
                rig.read_pose()
                sync_from_pose()
                if rig.tie:
                    if rig._tie_limit():
                        clamped += 1
                        arm.pose.bones['tie_1'].rotation_quaternion = rig.by_bone['tie_1'].basis
            t_prev = t
            for j in rig.joints:
                q = j.basis.copy()
                if any(math.isnan(c) for c in q):
                    nan += 1
                    q = Quaternion()
                lst = series[j.bone]
                if lst and lst[-1][1].dot(q) < 0:            # the short way round between keys
                    q.negate()
                lst.append((f, q, j.scale))
                if rig.first.get(j.spring) == j.bone:
                    a = math.degrees(j.init_basis.rotation_difference(q).angle)
                    swing[j.spring] = max(swing.get(j.spring, 0.0), a)
            for b, p in rig.tails().items():
                if b in prev_tip:
                    speeds.append((p - prev_tip[b]).length * fps)
                prev_tip[b] = p
    finally:
        for fn in held:
            bpy.app.handlers.frame_change_pre.append(fn)
        ext.enable_animation = anim0 if solver != 'addon' else False
        for o in hidden:
            o.hide_viewport = False
    act, _track, n_keys = key_track(h, tname, series, f0)
    for b in bones:                       # the track drives these bones now
        arm.pose.bones[b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        arm.pose.bones[b].scale = (1.0, 1.0, 1.0)
    scene.frame_set(scene.frame_current)
    rep = {'solver': solver, 'length': length, 'rate': rate, 'frames': [f0, f1], 'springs': len(rig.springs),
           'joints': len(rig.joints), 'tie_limit_deg': lim if rig.tie else None, 'steps': steps, 'preroll_steps': rep_pre, 'resets': resets,
           'override_frames': over_frames, 'action': act.name, 'track': tname, 'keys': n_keys,
           'swing_deg': {k: round(v, 2) for k, v in swing.items()}, 'tie_clamped_frames': clamped,
           'max_tail_speed_mps': round(max(speeds), 3) if speeds else 0.0, 'nan': nan, 'spring_list': rig.springs}
    if log:
        log(f'[springs] {h.name}: {rep["springs"]} springs, {rep["joints"]} joints, solver {solver}, rate {rate}, '
            f'{steps} steps, {n_keys} keys on {tname}')
    return rep


def spring_bones(h):
    """the bones the springs turn (each spring's joints but its last)"""
    sb = h.arm.data.vrm_addon_extension.spring_bone1
    out = []
    for s in sb.springs:
        for a in list(s.joints)[:-1]:
            if a.node.bone_name and a.node.bone_name not in out:
                out.append(a.node.bone_name)
    return out


def reset_springs(h):
    """every spring joint back at rest (identity basis, scale 1) now, unkeyed: the static pose under a bake"""
    for b in spring_bones(h):
        pb = h.arm.pose.bones.get(b)
        if pb is not None:
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)


def spring_track(h):
    """the NLA track bake_springs made, or None"""
    ad = h.arm.animation_data
    return ad.nla_tracks.get(f'{h.name}|springs') if ad is not None else None


def remove_springs(h):
    """the bake removed: its track and action, the bones at rest"""
    _remove_track(h, f'{h.name}|springs')
    reset_springs(h)
