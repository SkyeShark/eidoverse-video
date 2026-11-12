"""eidoblend.characters.emotes.verbs: scene_placement.js's character verbs (emote, faceCamera, seatOn, sitOnGround,
unseat) for a body the character controller drives, and routed to the stationary ports when nothing drives it.

    from eidoblend.characters.controller import CollisionWorld, Locomotion
    from eidoblend.characters.emotes import seat_on, stand_up, sit_on_ground, face_camera, emote, bake

    walk = Locomotion(me, CollisionWorld(), start=(0, -4, 0), heading=math.pi)
    seat_on(walk, chair)                    # walks up, turns out of the chair, sits into it (stand_to_sit), stays seated
    stand_up(walk)                          # the sit-down reversed (the example's), the walk resumes after it
    seat_on(walk, bench, then='sitting_nervous_arm_rub_chair', hold=4.0)   # a seated loop, then up: sit_to_stand
    sit_on_ground(walk, at=(2, 1), hold=3.0)
    face_camera(walk)                       # turn on the spot toward the scene camera
    emote(walk, 'salute', facing='camera')
    rep = bake(walk)                        # Locomotion.bake, then the seated frames keyed as seated (the audits' exemption)

The engine routes seatOn through the controller when one drives the VRM (globalThis._vrmControllers: "COHESIVE PATH"):
the transition plays on the controller's own mixer (beginSeated), the controller hands the root to the seat helper while
seated, and a per-frame clamp plus a final settle rest the seated body on the seat. Here each verb takes either a
Locomotion (that path: the verbs queue commands, bake() runs them with the rest of the take) or a VRM handle (no
controller: the stationary ports in eidoblend.placement.seating, round one's). What the controller path does:

  seat_on       the seat pan (findSeatSurface) and the chair's facing from its backrest (_detectChairFacing; face= wins,
                then the chair, then the camera); the hips' target over the pan biased toward the backrest
                (_restHipsOnSeat's min(0.12 m, 18 % of the pan's depth)); where to stand so the transition's own hip
                travel ends with the hips on that target (measured on the clip; hip_back= stands the engine's fixed
                distance in front instead); the walk to back_up in front of it (around the chair when it is in the way,
                auto maneuvers off), the turn out of the chair, a step or two back onto the spot; then the sit-down
                (beginSeated's state, entered on the standing pose: _take_stand_pose), the root held, the residual of
                the arrival eased out over the descent's second half (the engine's settle recentres it at the end), the
                underside's settle on the pan eased in over the same half, and from 40 % of the descent the one-sided
                clamp (_clampSeatedButt): the lowest seated skin over the pan never below it. The clamp and the settle
                are measured on the posed skin over the pelvis and thighs at clip times through the descent, over the
                pan's own surface (pan_points), before the take runs, and smoothed into one lift curve.
                then=<seated loop> crossfades into a chair loop (sitting_normal_chair, sitting_nervous_arm_rub_chair)
                with the root carried back by the difference of their hips so the hips stay on the seat, its own settle
                blended in. hold=<s> stands up after it; hold=None stays seated. instant=True (seatOn's instant path):
                no walk and no descent, the take opens (or cuts) seated in the loop, settled on the pan
  stand_up      endSeated: the transition reversed (the example's reverse mode: the same poses backwards, no hip
                mismatch), or a stand-up clip (sit_to_stand: VRMRobotBody.standUp's default): the clip's hips travel
                is taken as root motion (the engine releases the root at 85 % of the clip and the body pops forward;
                here the root follows the hips so the feet stay where they stand); then the standing pose, stopEmote,
                the walk resumes
  sit_on_ground sitOnGround's clip (sitting_on_ground, sit_laying_on_ground) crossfaded in where the body stands (or
                after a walk to at=), facing face=, else the camera (the engine's default); the lowest of the posed skin
                within 0.35 m of the hips (the engine's footprint; its spring chains and a coat left out) rested on the
                floor 5 mm above it, eased in with the crossfade; the boots kept on the floor through it, the crossfade
                and the rise (_boots_over_floor). The library has no stand-to-ground clip: the crossfade IS the
                sit-down (fade=, 1 s)
  face_camera   faceCamera: a turn on the spot toward the camera (+offset rad) at the frame it starts
  emote         emote for a walking body: playEmote (locomotion suspended), facing= 'keep' / 'camera' / a heading in
                degrees / None (the engine's default, three's rotation.y = pi); in at the walk's own fade, out through
                the standing pose, eased; the clip held over the root (align)
  unseat        from here the audits judge the body again, seated or not
  bake          Locomotion.bake with the seats' frames taken from the plant before it runs (_seat_records: the seated
                feet put on the floor here, the knee kept over its seated height, the toes pointing down on a high seat,
                the boots as the armature deforms them moved out of each chair part, smoothed in time; a foot resting
                on the floor held where it rests; a foot moving between two seated poses stepped through the move, one
                foot at a time; on the ground the boots and arms kept out of the floor; my robot body's legs through its
                joint clamps) and handed back after it (_seat_handover: the feet and the pelvis passed between the
                plant's and the seat's over 12 frames; the plant's first stance after a seat stands where the seat left
                the foot), then key_seated: arm['eido_seated'] keyed 1 on the seated frames and 0 elsewhere
                (CONSTANT), so the clipping and hovering audits and the support sensor leave a seated body alone exactly
                while it sits (the engine's _seatedVRMs set), and the engine's deferred facing check 1.5 s into each seat

Headings are Blender's, in radians as eidoblend.placement's (0 faces -Y, the VRM as loaded; pi faces +Y), except
emote's facing in degrees as Locomotion.emote's.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..controller.film import FollowPath, Locomotion, TurnTo, _Cmd, heading_of
from ..controller.film import Emote as _Emote
from .catalog import GROUND_CLIP, SEAT_CLIP, is_sitting

CLAMP_FROM = 0.40           # the clamp runs from this fraction of the descent (the engine's clampFrom)
SETTLE_FROM = 0.50          # the settle and the recentring ease in over the descent from here
UNDER_SAMPLES = 10          # the clamp's underside measured at this many clip times over the descent (at least)
UNDER_FROM = 0.6            # m: the seat measures cast up from this far under the pan (the body posed at floor height)
UP_EASE = 0.60              # the stand-up eases the seat's offsets out over this fraction of it
GROUND_GRID = 0.175         # sitOnGround's up-ray grid: hips +- 2 steps of this, both ways
STAND_POSE = 'idle'         # the pose a ground sit stands back up into


def _log(loco, msg):
    (getattr(loco, 'log', None) or print)(msg)


def _fps():
    sc = bpy.context.scene
    return sc.render.fps / sc.render.fps_base


def _frame(loco):
    """the frame the command now starting will key first (bake(f0=) via this module's bake, else the scene's start)"""
    f0 = getattr(loco, 'f0', None)
    if f0 is None:
        f0 = bpy.context.scene.frame_start
    return f0 + int(round(loco.ctrl.time * _fps()))


def _camera_pos(camera, frame):
    sc = bpy.context.scene
    cam = camera or sc.camera
    if cam is None:
        return None
    cur = sc.frame_current
    sc.frame_set(frame)
    p = cam.matrix_world.translation.copy()
    sc.frame_set(cur)
    return p


def _fwd(th):
    return Vector((math.sin(th), -math.cos(th)))


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def _wrap_pi(a):
    return math.atan2(math.sin(a), math.cos(a))


def is_locomotion(x):
    return isinstance(x, Locomotion)


# ================================================================================================ geometry helpers
def _box_xy(obj):
    """an object tree's visible meshes' world box in x, y: (x0, x1, y0, y1)"""
    from ...placement import _world as W
    W.update()
    dg = W.depsgraph()
    lo, hi = Vector((1e30, 1e30, 1e30)), Vector((-1e30, -1e30, -1e30))
    for o in [obj] + list(obj.children_recursive):
        if o.type != 'MESH' or not W.visible(o):
            continue
        a, b = W.box_of_object(o, dg)
        lo = Vector((min(lo.x, a.x), min(lo.y, a.y), min(lo.z, a.z)))
        hi = Vector((max(hi.x, b.x), max(hi.y, b.y), max(hi.z, b.z)))
    return lo.x, hi.x, lo.y, hi.y


def _seg_hits_box(a, b, box):
    """does the segment a-b pass through the open box (x0, x1, y0, y1)? (Liang-Barsky)"""
    x0, x1, y0, y1 = box
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q <= 0.0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    return t1 - t0 > 1e-6


def route_around(start, goal, box, margin=0.35):
    """waypoints from start to goal (x, y) that keep clear of the box (x0, x1, y0, y1) grown by margin: [goal] when the
    straight line clears it, else the shortest way round by one or two of its corners"""
    x0, x1, y0, y1 = box
    m = margin
    B = (x0 - m, x1 + m, y0 - m, y1 + m)
    if not _seg_hits_box(start, goal, B):
        return [tuple(goal)]
    e = 0.02
    C = [(B[0] - e, B[2] - e), (B[1] + e, B[2] - e), (B[1] + e, B[3] + e), (B[0] - e, B[3] + e)]

    def length(pts):
        return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

    best = None
    for i in range(4):
        cands = [[C[i]], [C[i], C[(i + 1) % 4]], [C[i], C[(i - 1) % 4]]]
        for via in cands:
            pts = [tuple(start)] + via + [tuple(goal)]
            if any(_seg_hits_box(pts[k], pts[k + 1], B) for k in range(len(pts) - 1)):
                continue
            if best is None or length(pts) < length(best):
                best = pts
    return best[1:] if best else [tuple(goal)]


LONG_SIT_KNEE = math.radians(12.0)     # my robot body's ground sit: the knees this little bent...
LONG_SIT_ANKLE = 0.07                  # ...its ankles first put this far over the floor, then each moved so its heel
#                                        rests on it (LONG_SIT_REST over it)
LONG_SIT_REST = 0.002
LONG_SIT_EASE = 0.6                    # its legs taken in over this much of the ground pose's share of a crossfade
BOOT_FLOOR_TOL = 0.002                 # on the ground, a boot this far under the floor is resting on it
BOOT_TURN = math.radians(30.0)         # the most a boot on the ground turns about its width to come out of the floor


def long_sit(body, clip):
    """my robot body sitting on the ground in the library's cross-legged clip: its hips flex 98 deg at most and its
    knees 112, so it cannot fold into that sit (clamped, the shins stood straight down 21 cm through the floor); it
    sits as its joints let it, the legs out in front along the floor (_long_sit_legs)"""
    return body is not None and getattr(body, 'robot', False) and clip == GROUND_CLIP


def _leg_aim(p, body, side, A, hinge):
    """the leg of the Pose p solved to put its ankle at A on the rest legs' own bones (a thigh or a shank need not run
    straight down at rest): the knee a hinge about its X, bent as far as the distance needs (Body.knee_for), the thigh
    turned so the leg so bent points from the hip to A with the thigh's X along `hinge` (made square to the leg)
    -> the knee angle, or None"""
    up_n, lo_n = side + 'UpperLeg', side + 'LowerLeg'
    L = body.leg[side]
    b = A - p.world_pos(up_n)
    if b.length < 1e-6:
        return None
    k = body.knee_for(side, b.length)
    a = L['u'] + Quaternion((1.0, 0.0, 0.0), k) @ L['w']

    def frame(z, x):
        z = z.normalized()
        x = x - z * x.dot(z)
        if x.length < 1e-6:
            return None
        x.normalize()
        return Matrix((x, z.cross(x), z)).transposed()
    F0, F1 = frame(a, Vector((1.0, 0.0, 0.0))), frame(b, hinge)
    if F0 is None or F1 is None:
        return None
    p.set_world_quat(up_n, (F1 @ F0.transposed()).to_quaternion())
    p.N[lo_n] = Quaternion((1.0, 0.0, 0.0), k)
    p.invalidate()
    return k


def _boot_low(p, body, side):
    """the lowest point of the boot (_boot_pts: the skin the foot and toes carry) in the Pose p, or None"""
    P = _boot_pts(p, body, side)
    return None if P is None or not len(P) else float(P[:, 2].min())


def _boots_over_floor(p, body, floor_z, tol=BOOT_FLOOR_TOL, rounds=4):
    """on the ground, each boot of the Pose p kept out of the floor at floor_z: where the boot's lowest point is under
    it, the ankle is raised by as much (the two-bone leg, the foot keeping its world turn) until it rests on it, on my
    robot body through its leg clamps (the plant runs them after). A ground clip crossfaded in from standing swings the
    legs from straight down to along the floor while the hips come down, so the blend of the two can carry a foot
    through the floor; the foot rests on it and slides instead -> the deepest left under the floor (m, >= 0)"""
    from ..controller.pose import leg_clamps
    left = 0.0
    if body.robot:
        # measured on the legs as my hardware holds them: the ankle's stops turn a foot laid along the floor by up to
        # 27 deg from the clip's own
        p.N.update(leg_clamps(body, dict(p.N)))
        p.invalidate()
    for s in ('left', 'right'):
        if s + 'Foot' not in body.h.humanoid:
            continue
        for _ in range(rounds):
            low = _boot_low(p, body, s)
            if low is None or low >= floor_z - tol:
                break
            an = p.world_pos(s + 'Foot').copy()
            _leg_reach(p, s, an + Vector((0.0, 0.0, floor_z - low)))
            if body.robot:
                w_ft = p.world_quat(s + 'Foot').copy()
                p.N.update(leg_clamps(body, dict(p.N)))
                p.invalidate()
                p.set_world_quat(s + 'Foot', w_ft)
                p.N.update(leg_clamps(body, dict(p.N)))
                p.invalidate()
        low = _boot_low(p, body, s)
        if low is not None and low < floor_z - tol:
            # a leg that cannot fold any further (my robot body's knee and ankle stops): the foot turns its toes up off
            # the floor about its own width (lying, a leg laid out along the floor points its toes into it)
            w_ft = p.world_quat(s + 'Foot').copy()
            lat = w_ft @ Vector((1.0, 0.0, 0.0))
            best = (low, None)
            for k in range(1, 11):
                for sg in (1.0, -1.0):
                    p.set_world_quat(s + 'Foot', Quaternion(lat, sg * k * BOOT_TURN / 10) @ w_ft)
                    if body.robot:
                        p.N.update(leg_clamps(body, dict(p.N)))
                        p.invalidate()
                    lw = _boot_low(p, body, s)
                    if lw is not None and lw > best[0] + 1e-4:
                        best = (lw, sg * k * BOOT_TURN / 10)
                if best[0] >= floor_z - tol:
                    break
            p.set_world_quat(s + 'Foot', Quaternion(lat, best[1] or 0.0) @ w_ft)
            if body.robot:
                p.N.update(leg_clamps(body, dict(p.N)))
                p.invalidate()
            low = _boot_low(p, body, s)
        if low is not None:
            left = max(left, floor_z - low)
    return max(0.0, left)


ARM_LIFT_MAX = math.radians(25.0)      # the most an arm laid on the floor turns up at the shoulder to come out of it


def _arms_over_floor(p, body, floor_z, tol=BOOT_FLOOR_TOL, rounds=3):
    """on the ground, each arm of the Pose p (_arm_skin: the upper arm, the forearm, the hand) kept out of the floor at
    floor_z: where its lowest point is under it, the arm turns up at the shoulder (about the level axis square to the
    shoulder-to-that-point line) as little as lifts that point onto the floor. A forearm the clip lays on the floor
    beside the body rests on it; on a body whose arms are longer or thicker than the clip's actor's it would otherwise
    lie in it -> the deepest left under the floor (m, >= 0)"""
    left = 0.0
    for s in ('left', 'right'):
        up_n = s + 'UpperArm'
        if up_n not in body.h.humanoid:
            continue
        sk = _arm_skin(body).get(s)
        for _ in range(rounds):
            P = _skin_pts(p, body, sk)
            if P is None or not len(P):
                break
            k = int(np.argmin(P[:, 2]))
            d = floor_z - float(P[k, 2])
            if d <= tol:
                break
            sh = p.world_pos(up_n)
            v = Vector(P[k]) - sh
            axis = v.cross(Vector((0.0, 0.0, 1.0)))
            if axis.length < 1e-6:
                break
            axis.normalize()
            lo, hi = 0.0, ARM_LIFT_MAX
            for _b in range(20):
                mid = 0.5 * (lo + hi)
                if (Quaternion(axis, mid) @ v).z + sh.z < floor_z:
                    lo = mid
                else:
                    hi = mid
            p.apply_world_delta(up_n, Quaternion(axis, hi))
        P = _skin_pts(p, body, sk)
        if P is not None and len(P):
            left = max(left, floor_z - float(P[:, 2].min()))
    return max(0.0, left)


def _long_sit_legs(h, body, N, off, M, floor_z, w):
    """the legs of a pose taken w of the way to the long sit on the floor at floor_z: each ankle carried from where the
    pose has it to its long-sit place (straight ahead of its hip along the root's heading, the knee bent LONG_SIT_KNEE,
    the heel resting on the floor, the toes up) and the leg solved to it (_leg_aim), the knee's hinge turned from the
    clip's own to across the body (the knee toward forward-and-up: forward standing, up sitting); the foot from the
    clip's turn to at rest on the shank; every boot kept out of the floor on the way (_boots_over_floor). The ankle is
    carried, not the joints turned: a blend of joint turns arcs the ankle through the floor -> a new N"""
    from ..controller.pose import Pose
    if w <= 1e-4:
        return N
    # taken in over the first LONG_SIT_EASE of the ground pose's share (out over its last): the feet slide along the
    # floor while the hips go down (come up)
    w = min(1.0, w / LONG_SIT_EASE)
    p = Pose(body, M, {nm: N.get(nm, Quaternion()).copy() for nm in h.humanoid}, off)
    q = M.to_quaternion()
    fwd = q @ Vector((0.0, -1.0, 0.0))
    fwd.z = 0.0
    if fwd.length < 1e-6:
        return N
    fwd.normalize()
    left = Vector((-fwd.y, fwd.x, 0.0))
    up = Vector((0.0, 0.0, 1.0))
    for s in ('left', 'right'):
        up_n, lo_n, ft_n, to_n = s + 'UpperLeg', s + 'LowerLeg', s + 'Foot', s + 'Toes'
        if any(nm not in h.humanoid for nm in (up_n, lo_n, ft_n)):
            continue
        hip = p.world_pos(up_n).copy()
        A0 = p.world_pos(ft_n).copy()
        w_ft0 = p.world_quat(ft_n).copy()
        x_clip = p.world_quat(up_n) @ Vector((1.0, 0.0, 0.0))
        nt0 = p.N.get(to_n, Quaternion()).copy()
        L = body.leg[s]
        d1 = (L['u'] + Quaternion((1.0, 0.0, 0.0), LONG_SIT_KNEE) @ L['w']).length

        def place(A, ww):
            """the leg to A, the hinge and the foot ww of the way from the clip's to the long sit's"""
            hinge = x_clip.lerp(left, ww)
            _leg_aim(p, body, s, A, hinge if hinge.length > 1e-6 else left)
            w_sh = p.world_quat(lo_n).copy()
            if w_ft0.dot(w_sh) < 0.0:
                w_sh = -w_sh
            p.set_world_quat(ft_n, w_ft0.slerp(w_sh, ww))
            if to_n in p.N:
                p.N[to_n] = nt0.slerp(Quaternion(), ww)
                p.invalidate()
        # the long sit's ankle: d1 from the hip straight ahead, its height found so the heel rests on the floor
        za = floor_z + LONG_SIT_ANKLE
        A1 = None
        for _ in range(4):
            dz = min(za - hip.z, 0.0)
            A1 = hip + fwd * math.sqrt(max(d1 * d1 - dz * dz, 0.0)) + up * dz
            place(A1, 1.0)
            low = _boot_low(p, body, s)
            if low is None or abs(low - (floor_z + LONG_SIT_REST)) < 0.001:
                break
            za += (floor_z + LONG_SIT_REST) - low
        place(A0.lerp(A1, w), w)
    _boots_over_floor(p, body, floor_z)
    out = dict(N)
    for s in ('left', 'right'):
        for nm in (s + 'UpperLeg', s + 'LowerLeg', s + 'Foot', s + 'Toes'):
            if nm in p.N:
                out[nm] = p.N[nm].copy()
    return out


class _Posed:
    """the VRM's armature posed as the controller poses it (a clip at time t, the root matrix M) for measuring, and put
    back as it was on exit (pose, root, action and its slot). body: the controller's Body: on my robot body the legs
    go through its joint clamps first, as the bake's plant will put them (a clamped leg folds or reaches otherwise).
    long_sit: (floor z, 'a' | 'b' | 'all'): my robot body's ground sit (_long_sit_legs) on the ground clip's share of
    the pose (a crossfade's first or second clip, or the whole pose). ground: the floor's z under a ground sit: the
    boots and the arms kept out of it as the bake keeps them (_boots_over_floor, _arms_over_floor)"""

    def __init__(self, h, body=None, long_sit=None, ground=None):
        self.h = h
        self.body = body
        self.long_sit = long_sit
        self.ground = ground

    def __enter__(self):
        arm = self.h.arm
        ad = arm.animation_data
        self.act = ad.action if ad is not None else None
        self.slot = getattr(ad, 'action_slot', None) if ad is not None else None
        self.saved = {pb.name: (pb.rotation_mode, pb.rotation_quaternion.copy(), pb.location.copy())
                      for pb in arm.pose.bones}
        self.mw = arm.matrix_world.copy()
        if ad is not None:
            ad.action = None
        # every bone the clips do not pose at rest: left as the last evaluated frame had them, my robot body's helper
        # bones (the hip swings, the calf cylinders its rig keys) carried a seated frame of the take before into the
        # next take's measures and read the stool's seat 44 cm off
        hum = set(self.h.humanoid.values())
        for pb in arm.pose.bones:
            if pb.name not in hum:
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                pb.location = (0.0, 0.0, 0.0)
        return self

    def pose(self, cclip, t, M):
        N, off = cclip.sample(t, loop=False)
        self.pose_N(N, off, M, ground_w=1.0)

    def pose_N(self, N, off, M, ground_w=None):
        """a normalized pose posed at the root M: on my robot body through its legs' hardware first, the clamps and
        the hip stages (body.project_legs, the HipPitch / HipSwing helper bones keyed as the bake keys them: left at
        rest, the measures missed the hip mechanism going 2 cm into a pan); with long_sit set, its ground sit's legs on
        ground_w of the pose; with ground set, the boots and the arms out of that floor"""
        h = self.h
        arm = h.arm
        stages = {}
        if self.long_sit is not None and ground_w:
            N = _long_sit_legs(h, self.body, N, off, M, self.long_sit[0], ground_w)
        if self.ground is not None and self.body is not None:
            from ..controller.pose import Pose
            p = Pose(self.body, M, {nm: N.get(nm, Quaternion()).copy() for nm in h.humanoid}, off)
            _boots_over_floor(p, self.body, self.ground)
            _arms_over_floor(p, self.body, self.ground)
            N = p.N
        if self.body is not None and getattr(self.body, 'robot', False):
            N = {nm: N.get(nm, Quaternion()) for nm in h.humanoid}
            stages = self.body.project_legs(N, stages=True)
        for nm, b in h.humanoid.items():
            pb = arm.pose.bones[b]
            pb.rotation_mode = 'QUATERNION'
            q = N.get(nm)
            pb.rotation_quaternion = h.basis_from_normalized(b, q) if q is not None else (1.0, 0.0, 0.0, 0.0)
        for side, st in (stages or {}).items():
            for k, bn in (('pitch', side + 'HipPitch'), ('swing', side + 'HipSwing')):
                if k in st and bn in arm.pose.bones:
                    pb = arm.pose.bones[bn]
                    pb.rotation_mode = 'QUATERNION'
                    pb.rotation_quaternion = h.basis_from_normalized(bn, st[k])
        hb = h.humanoid['hips']
        arm.pose.bones[hb].location = h.rest_q[hb].inverted() @ (off if off is not None else Vector())
        arm.matrix_world = M
        bpy.context.view_layer.update()

    def pose_blend(self, ca, ta, cb, tb, e, M, loop_a=True, loop_b=True):
        """two clips crossfaded as the mixer blends them (weights 1 - e and e: each bone's rotation slerped, the hips'
        offsets mixed), posed at the root M (a clip that does not loop holds its last pose)"""
        h = self.h
        Na, oa = ca.sample(ta if loop_a else min(ta, ca.duration), loop=loop_a)
        Nb, ob = cb.sample(tb if loop_b else min(tb, cb.duration), loop=loop_b)
        N = {}
        for nm in h.humanoid:
            qa, qb = Na.get(nm), Nb.get(nm)
            if qa is None and qb is None:
                continue
            qa = qa if qa is not None else Quaternion()
            qb = qb if qb is not None else Quaternion()
            if qa.dot(qb) < 0.0:
                qb = -qb
            N[nm] = qa.slerp(qb, e)
        side = self.long_sit[1] if self.long_sit is not None else None
        gw = e if side == 'b' else (1.0 - e if side == 'a' else (1.0 if side == 'all' else None))
        self.pose_N(N, (oa if oa is not None else Vector()).lerp(ob if ob is not None else Vector(), e), M,
                    ground_w=gw)

    def hips(self):
        arm = self.h.arm
        return arm.matrix_world @ arm.pose.bones[self.h.humanoid['hips']].head

    def bone_z(self, name):
        arm = self.h.arm
        return (arm.matrix_world @ arm.pose.bones[self.h.humanoid[name]].head).z

    def __exit__(self, *exc):
        arm = self.h.arm
        for pb in arm.pose.bones:
            rm, q, loc = self.saved[pb.name]
            pb.rotation_mode = rm
            pb.rotation_quaternion = q
            pb.location = loc
        arm.matrix_world = self.mw
        ad = arm.animation_data
        if ad is not None:
            ad.action = self.act
            if self.act is not None and self.slot is not None:
                try:
                    ad.action_slot = self.slot
                except Exception:  # noqa: BLE001 - a slot of another action: Blender picks one
                    pass
        bpy.context.view_layer.update()
        return False


def _spring_carried(h):
    """the armature's bones a spring chain moves: every joint of every VRMC_springBone spring and the bones under them"""
    joints = set()
    try:
        for s in h.arm.data.vrm_addon_extension.spring_bone1.springs:
            joints.update(j.node.bone_name for j in s.joints if j.node.bone_name)
    except AttributeError:
        return set()
    out = set()
    for b in h.arm.data.bones:
        p = b
        while p is not None and p.name not in joints:
            p = p.parent
        if p is not None:
            out.add(b.name)
    return out


def _loose_layers(h):
    """the meshes that hang loose over the body (a coat, a skirt): those that carry thigh-weighted skin but are not the
    skin that sits tightest round the thigh bones (film._seat_skin's choice). Skinned without cloth, a coat's hem goes
    through whatever she sits on; measured with it, on the ground, Aletheia sat 6 cm over the floor on her coat's hem
    (her crossed legs hovering) -> {mesh}, cached on the handle"""
    cache = getattr(h, '_loose_layers', None)
    if cache is not None:
        return cache
    from ..controller.film import _seat_skin
    tight = {o for o, _k in _seat_skin(h)}
    thighs = {h.humanoid[b] for b in ('leftUpperLeg', 'rightUpperLeg') if b in h.humanoid}
    out = set()
    for o in h.meshes:
        if o in tight:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        if not thighs & set(idx.values()):
            continue
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            if idx.get(best) in thighs:
                out.add(o)
                break
    h._loose_layers = out
    return out


def _support_skin(h):
    """per visible mesh of the VRM, its polygons that can bear the body on the ground: those whose every vertex is
    carried mostly by a bone outside the spring chains, on the meshes that are not loose layers (_loose_layers: a
    coat's hem sinks into the floor where it hangs under the body, hidden by it, as a seat's pan takes it in a chair).
    A spring chain (a tentacle, a tail, hair, a coat's tails) is no support: bake_springs swings it afterwards, under
    gravity, through whatever it was measured against. Lying down ('sit_laying_on_ground'), Aletheia's tails reach
    below her at rest; measured with them she lay propped on two of them, her body about 15 cm over the floor
    -> [(mesh, polygon indices)], cached on the handle"""
    cache = getattr(h, '_support_skin', None)
    if cache is not None:
        return cache
    springy = _spring_carried(h)
    loose = _loose_layers(h)
    out = []
    for o in h.meshes:
        if o in loose:
            continue
        idx = {g.index: g.name for g in o.vertex_groups}
        keep = []
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            keep.append(best is None or idx.get(best) not in springy)
        out.append((o, [p.index for p in o.data.polygons if all(keep[i] for i in p.vertices)]))
    h._support_skin = out
    return out


def _body_lowest(h, pts, z0, reach=1.5):
    """the lowest point of the posed VRM's body over up-rays from z0 at the points (x, y): sitOnGround's measure (the
    butt, folded shins or a lying back, whatever touches down), on the skin that can bear her (_support_skin)"""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o, keep in _support_skin(h):
        if o.hide_render or not keep:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        M = o.matrix_world
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        mp = me.polygons
        polys.extend(tuple(base + i for i in mp[k].vertices) for k in keep if k < len(mp))
        ev.to_mesh_clear()
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(verts, polys)
    low = None
    for x, y in pts:
        loc, _n, _i, _d = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, 1.0)), reach)
        if loc is not None and (low is None or loc.z < low):
            low = loc.z
    return low


def _surface_under(objs, x, y, z_top):
    """the highest surface of objs' visible meshes under (x, y), cast down from z_top, or None"""
    from ...placement import _world as W
    meshes = [o for ob in objs for o in [ob] + list(ob.children_recursive) if o.type == 'MESH' and W.visible(o)]
    if not meshes:
        return None
    hit = W.Rays(meshes).cast((x, y, z_top), (0, 0, -1), 5.0)
    return hit[0].z if hit else None


def pan_points(chair, seat, n=11, reach=0.32, tol=0.03):
    """points (x, y) on the seat pan itself: a grid of n x n down-rays over +-reach m round the pan's centre, kept where
    the chair's first surface under them is the pan (within tol of its height). The engine's settle and clamp sample a
    world-aligned 0.40 x 0.44 m box round the centre; on a turned chair its corners lie off the pan, where the thighs
    hang lower in the air past its edge (read as sunk into it)"""
    from ...placement import _world as W
    meshes = [o for o in [chair] + list(chair.children_recursive) if o.type == 'MESH' and W.visible(o)]
    if not meshes:
        return []
    rays = W.Rays(meshes)
    out = []
    for i in range(n):
        for j in range(n):
            x = seat['x'] - reach + 2 * reach * i / (n - 1)
            y = seat['y'] - reach + 2 * reach * j / (n - 1)
            h = rays.cast((x, y, seat['z'] + 0.25), (0, 0, -1), 0.6)
            if h and abs(h[0].z - seat['z']) < tol:
                out.append((x, y))
    return out


def seat_skin(h):
    """the skin a seat bears: film's seat skin (the vertices of the tightest mesh carried mostly by the hips or a thigh:
    not hair, a coat's hem or a calf), and on my robot body its hips' mechanism too (the vertices the HipPitch /
    HipSwing stages carry: the keyed hips put it 2 cm into a pan the seat skin alone sat on) -> [(mesh, {index: True})],
    cached on the handle"""
    cache = getattr(h, '_seat_skin_ext', None)
    if cache is not None:
        return cache
    from ..controller.film import _seat_skin
    stage = {b.name for b in h.arm.data.bones if b.name.endswith(('HipPitch', 'HipSwing'))}
    out = []
    for o, keep in _seat_skin(h):
        keep = dict(keep)
        if stage:
            idx = {g.index: g.name for g in o.vertex_groups}
            for v in o.data.vertices:
                best, bw = None, -1.0
                for g in v.groups:
                    if g.weight > bw:
                        bw, best = g.weight, g.group
                if idx.get(best) in stage:
                    keep[v.index] = True
        out.append((o, keep))
    h._seat_skin_ext = out
    return out


def skin_lowest(h, pts, z0, reach=0.6):
    """the lowest point of the posed seat skin (seat_skin: the pelvis and thighs, not hair, a coat's hem or a calf)
    over up-rays from z0 at the points, or None"""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o, keep in seat_skin(h):
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        M = o.matrix_world
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        polys.extend(tuple(base + i for i in p.vertices) for p in me.polygons if all(i in keep for i in p.vertices))
        ev.to_mesh_clear()
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(verts, polys)
    low = None
    for x, y in pts:
        loc, _n, _i, _d = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, 1.0)), reach)
        if loc is not None and (low is None or loc.z < low):
            low = loc.z
    return low


def _support_verts(h):
    """per visible mesh of the VRM, the vertices not carried mostly by a spring chain (_support_skin's, as vertices):
    the posed body a chair's backrest or the floor must not take in -> [(mesh, indices)], cached on the handle"""
    cache = getattr(h, '_support_verts', None)
    if cache is not None:
        return cache
    springy = _spring_carried(h)
    out = []
    for o in h.meshes:
        idx = {g.index: g.name for g in o.vertex_groups}
        keep = []
        for v in o.data.vertices:
            best, bw = None, -1.0
            for g in v.groups:
                if g.weight > bw:
                    bw, best = g.weight, g.group
            if best is None or idx.get(best) not in springy:
                keep.append(v.index)
        out.append((o, np.array(keep, dtype=np.int64)))
    h._support_verts = out
    return out


def skin_points(h, loose=True):
    """the posed VRM's skin that can touch a seat or the floor (every rendered mesh's vertices that no spring chain
    carries: the body, a coat, the face; not tails, tentacles or hair, which bake_springs swings afterwards), in world
    space -> (n, 3). loose=False leaves the loose layers out (_loose_layers: a coat)"""
    return _points_of(h, None if loose else ('skip', _loose_layers(h)))


def _loose_points(h):
    """the posed loose layers' points (a coat: _loose_layers), their spring-carried tails left out -> (n, 3)"""
    loose = _loose_layers(h)
    return _points_of(h, ('only', loose)) if loose else np.zeros((0, 3))


def _points_of(h, sel=None):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o, idx in _support_verts(h):
        if o.hide_render or not len(idx):
            continue
        if sel is not None and ((sel[0] == 'skip' and o in sel[1]) or (sel[0] == 'only' and o not in sel[1])):
            continue
        oe = o.evaluated_get(dg)
        n = len(oe.data.vertices)
        co = np.empty(n * 3)
        oe.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        if int(idx.max()) >= len(co):
            continue
        M = np.array(o.matrix_world)
        out.append(co[idx] @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3))


def _upper_parts(chair, seat_z):
    """the chair's solids that stand over its pan (a backrest, arms), each its own BVH (_chair_solid); a chair modelled
    as one mesh is one part (only the skin over the pan's top is tested against it)"""
    return [s for s in _chair_solid(chair) if s[2][2] > seat_z + 0.05]


BACK_CLEAR = 0.01           # m: the seated skin (a coat included) kept this far in front of a backrest
BACK_CAP = 0.15             # m: at most this far forward (more: the sitter is not where the chair's back can be)


def back_push(P, parts, seat_z, fwd, clear=BACK_CLEAR, cap=BACK_CAP, P_loose=None):
    """how far forward (m, along the sitter's facing fwd) the posed skin must move for none of it over the pan's top to
    be inside the chair's parts over it (its backrest): the farthest exit along fwd of a point of P inside, plus clear;
    0 when none is inside. P_loose (a coat's points: _loose_layers) may press into the back, as cloth would, but not
    come out behind it: each of its points inside keeps `clear` of the back's thickness behind it. The engine biases
    the hips toward the backrest (min(0.12 m, 18 % of the pan's depth)) and never checks it: on a chair whose back
    stands on its pan, the butt and a coat's back went through it and out of its back"""
    f3 = Vector((fwd[0], fwd[1], 0.0))
    if f3.length < 1e-9 or not len(P):
        return 0.0
    f3.normalize()
    best = 0.0
    for pts, through in ((P, False), (P_loose, True)):
        if pts is None or not len(pts):
            continue
        sel = pts[pts[:, 2] > seat_z + 0.005]
        for bvh, lo, hi in parts:
            # skin already out behind the back (outside it, its rear face straight ahead within 25 cm, under its
            # top: not an arm laid over it): the tentacles' base went clean through a 4 cm back, and counting only
            # the points still inside it pushed her 2 cm short. A coat comes back to `clear` inside the back, the body
            # all the way out of its front
            lo2 = np.minimum(lo, lo - np.array([f3.x, f3.y, 0.0]) * 0.25)
            hi2 = np.maximum(hi, hi - np.array([f3.x, f3.y, 0.0]) * 0.25)
            for p in sel[np.all((sel >= lo2) & (sel <= hi2), axis=1)]:
                if p[2] > hi[2] - 0.05:
                    continue
                q = Vector(p)
                hit = bvh.ray_cast(q, f3, 0.25)
                if hit[0] is None or hit[1].dot(f3) >= 0.0 or _inside_bvh(bvh, q):
                    continue
                if through:
                    best = max(best, hit[3] + clear)
                else:
                    out = bvh.ray_cast(hit[0] + f3 * 1e-5, f3, 1.0)
                    best = max(best, hit[3] + (out[3] if out[0] is not None else 0.0) + clear)
            near = sel[np.all((sel >= lo) & (sel <= hi), axis=1)]
            for p in near:
                q = Vector(p)
                loc, nrm, _k, _d = bvh.find_nearest(q, 0.5)
                if loc is None or (q - loc).dot(nrm) >= 0.0 or not _inside_bvh(bvh, q):
                    continue
                if through:
                    hb = bvh.ray_cast(q, -f3, 2.0)          # what is left of the back behind it
                    if hb[0] is not None and hb[3] < clear:
                        best = max(best, clear - hb[3])
                    continue
                hit = bvh.ray_cast(q, f3, 2.0)
                if hit[0] is not None:
                    best = max(best, hit[3] + clear)
    return min(best, cap)


def _lowest_near(P, xy, half=0.35):
    """the lowest of the points P within half m (x and y) of xy: sitOnGround's footprint round the hips"""
    if not len(P):
        return None
    m = (np.abs(P[:, 0] - xy[0]) <= half) & (np.abs(P[:, 1] - xy[1]) <= half)
    return float(P[m, 2].min()) if m.any() else None


def _smooth_lift(dz, clamp, passes=6, first=None, last=None):
    """a lift curve smoothed (three-tap, `passes` times) with the clamp kept under it (lift only); its ends pinned"""
    dz = np.maximum(dz, clamp)
    for _ in range(passes):
        sm = dz.copy()
        sm[1:-1] = 0.25 * dz[:-2] + 0.5 * dz[1:-1] + 0.25 * dz[2:]
        if first is not None:
            sm[0] = first
        if last is not None:
            sm[-1] = last
        dz = np.maximum(sm, clamp)
    return dz


def _ground_lift(c, ca, ta0, cb, tb0, M, floor, span, weight_of, dz_of, long_sit_side=None):
    """a crossfade on the ground (the sit-down onto it, the rise from it): the two clips blended as the mixer blends
    them (weight_of(t): the second's weight at command time t, each clip running on from ta0 / tb0), frame by frame over
    span, the lift dz_of(t) never under the clamp that keeps the lowest of the posed body near the hips (skin_points
    without its loose layers, within sitOnGround's 0.35 m) on the floor; smoothed, lift only -> (times, values,
    the most the clamp lifted over dz_of). Blended halfway, the ground clip's hips are 0.4 m down while its legs are
    half folded: the crossfade alone put the feet and shins 16 cm into the floor. The ends stay sitOnGround's: where
    the settled pose itself has skin under the floor (my robot body's legs cannot fold cross-legged; the engine rests
    the lowest of its grid of up-rays and lets them go under), the clamp hands over to the settle across the
    crossfade instead of holding the body up (21 cm)"""
    dt = 1.0 / _fps()
    nf = int(math.ceil(span / dt)) + 1
    tf = np.arange(nf + 1) * dt
    ease = np.array([dz_of(min(t, span)) for t in tf])
    wt = np.array([weight_of(min(t, span)) for t in tf])
    clamp = np.full(len(tf), -1e9)
    Mt = M.copy()
    with _Posed(c.h, c.body, long_sit=(floor, long_sit_side) if long_sit_side else None, ground=floor) as posed:
        for i, t in enumerate(tf):
            Mt.translation = M.translation.copy()
            posed.pose_blend(ca, ta0 + t, cb, tb0 + t, float(wt[i]), Mt)
            hp = posed.hips()
            low = _lowest_near(skin_points(c.h, loose=False), (hp.x, hp.y))
            if low is not None:
                clamp[i] = floor - low
    ex0, ex1 = max(0.0, clamp[0] - ease[0]), max(0.0, clamp[-1] - ease[-1])
    clamp = clamp - ex0 * (1.0 - wt) - ex1 * wt
    dz = _smooth_lift(ease, clamp, first=float(max(ease[0], clamp[0])), last=float(max(ease[-1], clamp[-1])))
    return tf, dz, float(np.max(clamp - ease))


# ================================================================================================ the seated feet
KNEE_STEP = math.radians(2.0)
KNEE_MAX = math.radians(70.0)
TIPTOE_MAX = math.radians(35.0)


def _sole(p, body, side):
    """a foot's sole points (body.feet) where the Pose p puts them: (n, 3)"""
    F = body.feet
    p_an = p.world_pos(side + 'Foot')
    W_ft = p.world_quat(side + 'Foot')
    out = [F[side]['Foot'] @ np.array(W_ft.to_matrix()).T + np.array(p_an)]
    if len(F[side]['Toes']) and (side + 'Toes') in body.h.humanoid:
        W_to = p.world_quat(side + 'Toes')
        p_to = p_an + W_ft @ body.leg[side]['t']
        out.append(F[side]['Toes'] @ np.array(W_to.to_matrix()).T + np.array(p_to))
    return np.concatenate(out, axis=0)


KNEE_SIDE = 0.015           # m: how far opening the knee may swing a seated ankle sideways to lower it
KNEE_GIVE = 0.005           # m: how far under the clip's own a seated knee may come as its foot reaches for the floor
#                             (a knee lowered turns the thigh down into the pan: 1.2 cm put the thighs 1.5-1.9 cm into a
#                             0.62 m stool's pad)


def _gap(p, body, side, floor_z):
    return float(_sole(p, body, side)[:, 2].min()) - floor_z


def _foot_to_floor(p, body, side, floor_z, tol=0.002, seated=True, knee_floor=None, sideways=True):
    """a seated foot onto the floor, its world turn kept. Under the floor: lifted straight up (the two-bone leg). Over
    it: while the thigh rests on the seat (seated) and sideways, first the knee opens about its hinge while that swings
    the ankle no more than KNEE_SIDE sideways (a seated shin hangs near vertical, where a turn of the knee moves the
    foot sideways, hardly down); then the ankle reaches straight down, its knee kept over knee_floor (the thigh rests
    on the seat's edge: it does not go through it; a knee already lower is not lifted); what is still short, seated,
    the toes point down to (up to 35 deg): on a high seat the feet hang. -> the sole's gap left (m)"""
    up, lo, ft = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
    if any(n not in body.h.humanoid for n in (up, lo, ft)):
        return None
    g0 = _gap(p, body, side, floor_z)
    if abs(g0) <= tol:
        return g0
    if g0 < 0.0:
        an = p.world_pos(ft).copy()
        _leg_reach(p, side, an + Vector((0.0, 0.0, -g0)))
        return _gap(p, body, side, floor_z)
    if not seated or not sideways:
        _reach_down(p, side, g0, knee_floor)
        g = _gap(p, body, side, floor_z)
        return g if not seated else _tiptoe(p, body, side, floor_z, g, tol)
    a, b, c0 = p.world_pos(up).copy(), p.world_pos(lo).copy(), p.world_pos(ft).copy()
    axis = (b - a).cross(c0 - b)
    if axis.length < 1e-6:
        axis = p.M.to_3x3() @ Vector((1.0, 0.0, 0.0))
    axis.normalize()
    n_lo, n_ft = p.N.get(lo).copy(), p.N.get(ft).copy()
    w_ft = p.world_quat(ft).copy()

    def at(x):
        p.N[lo], p.N[ft] = n_lo.copy(), n_ft.copy()
        p.invalidate()
        if x:
            p.apply_world_delta(lo, Quaternion(axis, x))
            p.set_world_quat(ft, w_ft)
        cc = p.world_pos(ft)
        inner = math.degrees((a - b).angle(cc - b, math.pi))
        return _gap(p, body, side, floor_z), inner, (cc - c0).xy.length

    # 1: the knee opens (the direction that lowers the foot), within the sideways budget, not past straight
    best = (g0, 0.0)
    for sgn in (1.0, -1.0):
        x = 0.0
        while abs(x) < KNEE_MAX:
            x += sgn * KNEE_STEP * 0.5
            g, inner, side_mv = at(x)
            if inner > 178.0 or inner < 30.0 or side_mv > KNEE_SIDE or g > best[0] + 1e-4 and abs(x) > KNEE_STEP:
                break
            if 0.0 <= g < best[0]:
                best = (g, x)
            if g < 0.0:
                break
    g, _i, _s = at(best[1])
    # 2: the ankle reaches down, the knee kept over knee_floor
    if g > tol:
        _reach_down(p, side, g, knee_floor)
        g = _gap(p, body, side, floor_z)
    return _tiptoe(p, body, side, floor_z, g, tol)


def _reach_down(p, side, d, knee_floor):
    """the ankle straight down by d (the two-bone leg, its world turn kept), as far as the knee stays over knee_floor
    (None: all the way; a knee already under it is not lifted)"""
    lo, ft = side + 'LowerLeg', side + 'Foot'
    an = p.world_pos(ft).copy()
    if knee_floor is None:
        _leg_reach(p, side, an - Vector((0.0, 0.0, d)))
        return d
    lim = min(knee_floor, p.world_pos(lo).z)
    N0 = {k: q.copy() for k, q in p.N.items()}
    lo_d, hi_d = 0.0, d
    _leg_reach(p, side, an - Vector((0.0, 0.0, d)))
    if p.world_pos(lo).z >= lim:
        return d
    for _ in range(10):
        mid = 0.5 * (lo_d + hi_d)
        p.N.update({k: q.copy() for k, q in N0.items()})
        p.invalidate()
        _leg_reach(p, side, an - Vector((0.0, 0.0, mid)))
        if p.world_pos(lo).z < lim:
            hi_d = mid
        else:
            lo_d = mid
    p.N.update({k: q.copy() for k, q in N0.items()})
    p.invalidate()
    if lo_d > 1e-4:
        _leg_reach(p, side, an - Vector((0.0, 0.0, lo_d)))
    return lo_d


ANKLE_BAND_MARGIN = 1.0     # deg: my robot body's seated tiptoe keeps its ankle this far inside the full-roll pitch band


def _ankle_band():
    """my robot body's ankle pitch (deg) over which its roll keeps its whole range (robot_dof's coupled table: near the
    pitch stops the roll range narrows to a few degrees, and a foot hanging there rolls from one stop to the other)"""
    from ..robot_dof import LEG_JOINTS
    j = LEG_JOINTS[2]
    c, (z0, z1) = j['coupled'], j['range']['z']
    xs = [x for x, lo, hi in zip(c['x'], c['zmin'], c['zmax']) if lo <= z0 + 1e-6 and hi >= z1 - 1e-6]
    return min(xs) + ANKLE_BAND_MARGIN, max(xs) - ANKLE_BAND_MARGIN


def _ankle_pitch(p, side):
    """the ankle's pitch (deg, robot_dof's cardan x: + toes down) in the Pose p"""
    from .._math import euler_from_quat, q_to_three, twist_about
    from ..robot_dof import LEG_JOINTS
    q = q_to_three(p.N[side + 'Foot'])
    sw = q @ twist_about(q, LEG_JOINTS[2]['noTwist']).inverted()
    return math.degrees(euler_from_quat(sw, 'XZY')[0])


def _tiptoe(p, body, side, floor_z, g, tol=0.002):
    """a seated foot still short of the floor points its toes down to it (up to 35 deg about its lateral axis; on my
    robot body no further than its ankle's full-roll band, _ankle_band): the sole's gap left"""
    if g <= 0.015:
        return g
    ft = side + 'Foot'
    a, b, c0 = (p.world_pos(side + n).copy() for n in ('UpperLeg', 'LowerLeg', 'Foot'))
    lat = (b - a).cross(c0 - b)
    if lat.length < 1e-6:
        lat = p.M.to_3x3() @ Vector((1.0, 0.0, 0.0))
    lat.normalize()
    w_now = p.world_quat(ft).copy()
    band = _ankle_band() if getattr(body, 'robot', False) else None
    best_t = (g, 0.0)
    for k in range(1, 8):
        for s in (1.0, -1.0):
            p.set_world_quat(ft, Quaternion(lat, s * k * TIPTOE_MAX / 7) @ w_now)
            if band is not None and not band[0] <= _ankle_pitch(p, side) <= band[1]:
                continue
            gt = _gap(p, body, side, floor_z)
            if -tol <= gt < best_t[0]:
                best_t = (gt, s * k * TIPTOE_MAX / 7)
    p.set_world_quat(ft, Quaternion(lat, best_t[1]) @ w_now)
    return best_t[0]


HELD_PHASES = ('seated', 'then', 'back')    # the seat's phases where the thigh rests on the pan


def _logged(log, t):
    """a per-frame log's value at time t: the last one logged at or before it (a hold logs nothing new)"""
    if not log:
        return None
    key = round(t, 6)
    if key in log:
        return log[key]
    import bisect
    ks = log.get('__keys__')
    if ks is None or len(ks) != len(log) - 1:
        ks = sorted(k for k in log if k != '__keys__')
        log['__keys__'] = ks
    j = bisect.bisect_right(ks, key) - 1
    return log[ks[j]] if j >= 0 else None


STEP_SPEED = 0.003          # m a frame: a seated foot moving faster than this (a crossfade between two seated poses)...
STEP_MIN = 0.03             # ...over this far in all is lifted through it (a step), not slid
SEAT_DOWN = 0.004           # m: a seated sole this near the floor rests on it (held where it rests, as it rests)
FLAT_REST = 0.6             # a foot rests flat (not on its toes) where its points on the floor span this much of its length
CARRY = 8                   # frames: a held foot lifting off the floor without a step eases back to the clip's place
SWIVEL_MAX = math.radians(25.0)    # my robot body: the most its leg swings round its hip-to-ankle line to hold a foot's turn
SWIVEL_TOL = math.radians(0.1)
SWIVEL_ROUNDS = 6
SWING_KEEP = 0.003                 # m: the swing is kept where the clamped legs leave each foot this near its place
STEP_LIFT = (0.25, 0.06, 0.025)    # the step's lift: this fraction of how far it goes, at most / at least this high
PUSH_ROUNDS = 4             # rounds of the smoothed move of the boots out of a chair's solids


def _seat_records(loco, recs):
    """the frames a seat command held: the plant leaves their feet (mode 'seat': its standing rules would plant them by
    lowering the pelvis into the seat, or lock a ground sit's folded feet as a stance), and on a chair the feet are put
    on the floor here (_foot_to_floor). A seated foot that moves (a crossfade into or out of a seated loop whose feet
    rest elsewhere) is lifted on an arc over the move: a step, not a slide"""
    from ..controller.pose import Pose
    wins = getattr(loco, '_seat_windows', [])
    if not wins:
        return 0
    c = loco.ctrl
    held = []
    for i, r in enumerate(recs):
        w = next((w for w in wins if w[0] - 1e-6 <= r['t'] and (w[1] is None or r['t'] <= w[1] + 1e-6)), None)
        if w is None:
            continue
        # a long crossfade's first frame or two are not yet emoting (the controller's threshold): they are the seat's too
        if r['mode'] == 'seated' or (r['mode'] == 'loco' and r['t'] - w[0] < 0.15):
            held.append((i, w))
    cut = set()
    for i, w in held:
        if getattr(w[3], 'instant', False) and id(w) not in cut:
            cut.add(id(w))
            recs[i]['cut'] = True                     # an instant seat's first frame: the take cuts into the seat
    lift = {}
    chair = [(i, w) for i, w in held if w[2] == 'chair']
    steps = []
    for s in ('left', 'right'):
        xy = {}
        for i, w in chair:
            r = recs[i]
            p = Pose(c.body, r['M'], dict(r['N']), r['off'])
            xy[i] = p.world_pos(s + 'Foot').xy.copy()
        run = []
        idx = [i for i, _w in chair]

        def close(run):
            if len(run) < 2:
                return
            a, b = run[0], run[-1]
            go = (xy[b] - xy[a - 1] if (a - 1) in xy else xy[b] - xy[a]).length
            if go >= STEP_MIN:
                steps.append((go, s, a, b))
        for i in idx:
            moving = (i - 1) in xy and (xy[i] - xy[i - 1]).length > STEP_SPEED
            if moving and run and i - run[-1] <= 3:
                run.extend(range(run[-1] + 1, i + 1))
            elif moving:
                close(run)
                run = [i]
        close(run)
    # one foot steps at a time where the feet bear the body (sitting down, standing up): where both feet's steps
    # overlap there (a clip shuffling both as it stands), the longer step is taken and the other foot stays where it
    # rests (held below). Seated on the pan (HELD_PHASES) the feet carry nothing: both step, each lifted
    on_pan = {i: _logged(getattr(w[3], 'phase_log', {}), recs[i]['t']) in HELD_PHASES for i, w in chair}
    kept = []
    for go, s, a, b in sorted(steps, reverse=True):
        if any(s2 != s and a <= b2 + 2 and a2 <= b + 2 and
               not all(on_pan.get(j, False) for j in range(min(max(a, a2), min(b, b2)), max(max(a, a2), min(b, b2)) + 1))
               for _g, s2, a2, b2 in kept):
            continue
        kept.append((go, s, a, b))
    for go, s, a, b in kept:
        hgt = max(STEP_LIFT[2], min(STEP_LIFT[1], STEP_LIFT[0] * go))
        n = b - a + 2
        for k, j in enumerate(range(a, b + 1)):
            lift[(j, s)] = hgt * math.sin(math.pi * (k + 1) / n)
    solids = {}
    poses, push, held_on, kf = {}, {'left': {}, 'right': {}}, {}, {}
    last_way = {}
    for i, w in chair:
        # pass 1: the feet held against the recentring and on the floor; the least move out of the chair each needs
        r, cmd = recs[i], w[3]
        if id(cmd) not in solids:
            solids[id(cmd)] = _chair_solid(cmd.chair)
        p = Pose(c.body, r['M'], dict(r['N']), r['off'])
        k = _logged(getattr(cmd, 'k_log', {}), r['t'])
        held_on[i] = _logged(getattr(cmd, 'phase_log', {}), r['t']) in HELD_PHASES
        kf[i] = dict(_logged(getattr(cmd, 'kf_log', {}), r['t']) or cmd.knee_floor)
        # the knee no lower than the clip has it in this very frame less the give: one knee height taken from the
        # settled pose let a fidget loop's or a stand-up's knee (the clip has them up to 9 cm higher) be pulled
        # down to it as the foot reached for the floor, turning the thigh 2.8 cm into the pan
        for s in ('left', 'right'):
            if s + 'LowerLeg' in c.body.h.humanoid:
                raw_k = p.world_pos(s + 'LowerLeg').z - KNEE_GIVE
                kf[i][s] = max(kf[i].get(s, raw_k), raw_k)
        shift = cmd.dxy * k if k is not None else Vector((0.0, 0.0))
        for s in ('left', 'right'):
            if shift.length > 0.002:
                an = p.world_pos(s + 'Foot').copy()
                _leg_reach(p, s, Vector((an.x - shift.x, an.y - shift.y, an.z)))
            _foot_to_floor(p, c.body, s, cmd.root0.z + lift.get((i, s), 0.0), seated=held_on[i],
                           knee_floor=kf[i].get(s))
            v = _push_needed(p, c, s, solids[id(cmd)], prefer=last_way.get(s))
            push[s][i] = v
            if v is not None and v.length > 1e-6:
                last_way[s] = v.normalized()
        poses[i] = p
    # the moves out of the chair, smoothed in time (within 4 frames: the way they agree on, as far as the strongest
    # needs; then blurred over 5. A foot decided on alone each frame flickers in and out of a leg, and at a leg's
    # corner the nearest face turns from one side to the other frame by frame), applied, and what they left inside
    # measured again and moved the same way, for up to PUSH_ROUNDS rounds (a residual taken frame by frame shook a
    # hanging foot 1-3 cm a frame)
    for _round in range(PUSH_ROUNDS):
        if not any(v is not None for s in push for v in push[s].values()):
            break
        sm = {'left': {}, 'right': {}}
        for s in ('left', 'right'):
            for i in poses:
                near = [push[s][j] for j in range(i - 4, i + 5) if push[s].get(j) is not None]
                way = sum(near, Vector((0.0, 0.0, 0.0)))
                if not near or way.length < 1e-6:
                    sm[s][i] = max(near, key=lambda v: v.length) if near else None
                    continue
                way.normalize()
                # as far along it as clears each move's own face (|v|^2 / v.way), at most 1.5 x the strongest
                top = max(v.length for v in near)
                need = [v.length_squared / v.dot(way) for v in near if v.dot(way) > 0.2 * v.length]
                sm[s][i] = way * min(max(need, default=0.0), 1.5 * top)
            mx = dict(sm[s])
            for i in poses:
                got = [mx[j] for j in range(i - 2, i + 3) if mx.get(j) is not None]
                sm[s][i] = (sum(got, Vector((0.0, 0.0, 0.0))) / len(got)) if got else None
        for i, w in chair:
            r, cmd, p = recs[i], w[3], poses[i]
            for s in ('left', 'right'):
                v = sm[s].get(i)
                if v is not None and v.length > 1e-4:
                    an = p.world_pos(s + 'Foot').copy()
                    _leg_reach(p, s, an + v)
                    _foot_to_floor(p, c.body, s, cmd.root0.z + lift.get((i, s), 0.0), seated=held_on[i],
                                   knee_floor=kf[i].get(s), sideways=False)
                push[s][i] = _push_needed(p, c, s, solids[id(cmd)],
                                          prefer=v.normalized() if v is not None and v.length > 1e-6 else None)
    # a seated foot resting on the floor stays where it rests: through each run of frames it rests there (no step), it
    # keeps the place and the turn of the run's first frame, whatever the clip's small shuffles, the recentring's
    # remainder or the knee's give would do to it frame by frame; a step (lift) carries it from where it rested to
    # where the clip puts it at the step's end
    step_of = {(j, s): (a, b) for _go, s, a, b in kept for j in range(a, b + 1)}
    for s in ('left', 'right'):
        hold, prev, start, carry, own_prev = None, None, None, None, None
        for i, w in chair:
            p, cmd = poses[i], w[3]
            st = step_of.get((i, s))
            an = p.world_pos(s + 'Foot').copy()
            if st is not None:
                # the clip's own step, set off from where the foot rested (the difference eased out over the step)
                a, b = st
                if i == a:
                    start = Vector((hold[0].x - own_prev.x, hold[0].y - own_prev.y, 0.0)) \
                        if (hold is not None and prev == i - 1 and own_prev is not None) else None
                if start is not None:
                    e = _smooth((i - a + 1) / float(b - a + 1))
                    w_ft = p.world_quat(s + 'Foot').copy()
                    _leg_reach(p, s, an + start * (1.0 - e))
                    p.set_world_quat(s + 'Foot', w_ft)
                hold, carry = None, None
            elif _gap(p, c.body, s, cmd.root0.z) < SEAT_DOWN:
                if hold is not None and prev == i - 1:
                    _leg_reach(p, s, hold[0])
                    p.set_world_quat(s + 'Foot', hold[1])
                else:
                    hold = (an, p.world_quat(s + 'Foot').copy())
                carry = None
            else:
                # off the floor (a foot hanging from a high seat): it goes back to the clip's place over CARRY frames
                if hold is not None and prev == i - 1:
                    carry = (i, Vector((hold[0].x - an.x, hold[0].y - an.y, 0.0)), hold[1])
                if carry is not None and prev == i - 1 and i - carry[0] < CARRY:
                    k = 1.0 - _smooth((i - carry[0] + 1) / float(CARRY))
                    w_ft = p.world_quat(s + 'Foot').copy()
                    q = carry[2] if carry[2].dot(w_ft) >= 0.0 else -carry[2]
                    _leg_reach(p, s, an + carry[1] * k)
                    p.set_world_quat(s + 'Foot', w_ft.slerp(q, k))
                else:
                    carry = None
                hold = None
            prev, own_prev = i, an
    inside = []
    turned = {}                       # my robot body: each foot's (frame index, its turn as keyed, the clip's turn)
    for i, w in chair:
        r, p, cmd = recs[i], poses[i], w[3]
        for s in ('left', 'right'):
            if push[s].get(i) is not None:
                d = _boot_depth(p, c, s, solids[id(cmd)])
                if d > 0.002:
                    inside.append((r['f'], s, round(1000 * d, 1)))
        if c.body.robot:
            # my robot body: the plant runs its joint clamps on these legs. A clamp moves the foot it turns (the knee
            # held to its hinge swings the shin off the solve's plane), so each foot is reached for again where it was
            # placed, on the clamped legs, until the clamps leave it there: what the plant keys is what was placed.
            # The ankle has no twist, so a foot turns with the shin about the leg. One resting flat on the floor keeps
            # the turn it came down with: the leg swings round its hip-to-ankle line (the knee aside, the ankle where
            # it is: _swivel_to) until the shin holds the foot there. Where that would take more than SWIVEL_MAX (the
            # hip's twist), the foot takes the rest of the shin's turn about the middle of the sole it rests on, not
            # about its ankle. The step after a rest carries what the swing held into the clip's turn over the step
            from ..controller.plant import foot_yaw
            from ..controller.pose import leg_clamps
            placed = {s: (p.world_pos(s + 'Foot').copy(), p.world_quat(s + 'Foot').copy()) for s in ('left', 'right')}
            flat = {}
            for s in ('left', 'right'):
                P = _sole(p, c.body, s)
                on = P[:, 2] < cmd.root0.z + SEAT_DOWN
                fw = p.world_quat(s + 'Foot') @ Vector((0.0, -1.0, 0.0))
                fw = np.array((fw.x, fw.y)) / max(1e-6, math.hypot(fw.x, fw.y))
                along = P[:, :2] @ fw
                if int(on.sum()) >= 3 and np.ptp(along[on]) >= FLAT_REST * np.ptp(along):
                    flat[s] = Vector((float(P[on, 0].mean()), float(P[on, 1].mean()), 0.0))
            q0 = Pose(c.body, p.M, leg_clamps(c.body, dict(p.N)), p.off)
            clip_yaw = {s: foot_yaw(q0.world_quat(s + 'Foot')) for s in ('left', 'right')}
            want = {}
            for s in ('left', 'right'):
                last = turned.get(s)
                if last is None or last[0] != i - 1:
                    continue
                if s in flat:
                    want[s] = last[1]                          # resting on: the turn it rests with
                elif step_of.get((i, s)) is not None:
                    a, b = step_of[(i, s)]                     # stepping off a rest: the held turn eased into the clip's
                    if i == a or turned.get(s + '_carry') is not None:
                        off = turned.get(s + '_carry')
                        if off is None:
                            off = _wrap_pi(last[1] - last[2])
                            turned[s + '_carry'] = off
                        want[s] = clip_yaw[s] + off * (1.0 - _smooth((i - a + 1) / float(b - a + 1)))
            N0, base = dict(p.N), dict(placed)
            for swing in (want, {}):
                if swing is not want and not want:
                    break
                p.N = dict(N0)
                p.invalidate()
                placed = dict(base)
                for s, mid in flat.items():
                    pos, quat = placed[s]
                    rest_yaw = swing.get(s, clip_yaw[s])
                    if abs(_wrap_pi(rest_yaw - clip_yaw[s])) > SWIVEL_MAX:
                        rest_yaw = clip_yaw[s] + math.copysign(SWIVEL_MAX, _wrap_pi(rest_yaw - clip_yaw[s]))
                    R = Quaternion((0.0, 0.0, 1.0), _wrap_pi(rest_yaw - foot_yaw(quat)))
                    off = R @ Vector((pos.x - mid.x, pos.y - mid.y, 0.0))
                    placed[s] = (Vector((mid.x + off.x, mid.y + off.y, pos.z)), R @ quat)
                    _leg_reach(p, s, placed[s][0])
                    p.set_world_quat(s + 'Foot', placed[s][1])
                for s in swing:
                    if s not in flat:
                        pos, quat = placed[s]
                        placed[s] = (pos, Quaternion((0.0, 0.0, 1.0), _wrap_pi(swing[s] - foot_yaw(quat))) @ quat)
                        p.set_world_quat(s + 'Foot', placed[s][1])
                for _k in range(4):
                    p.N.update(leg_clamps(c.body, dict(p.N)))
                    p.invalidate()
                    miss = 0.0
                    for s, (pos, quat) in placed.items():
                        miss = max(miss, (p.world_pos(s + 'Foot') - pos).length)
                        _leg_reach(p, s, pos)
                        p.set_world_quat(s + 'Foot', quat)
                        if s in swing:
                            _swivel_to(p, c.body, s, foot_yaw(quat))
                    if miss < 0.001:
                        break
                p.N.update(leg_clamps(c.body, dict(p.N)))
                p.invalidate()
                # the swing kept only where the clamped legs still put the feet where they were placed (the hip's
                # twist stop can take the leg round its own axis instead, the ankle with it)
                if not swing or all((p.world_pos(s + 'Foot') - pos).length < SWING_KEEP for s, (pos, _q) in
                                    placed.items()):
                    break
            if swing is not want:
                want = {}
            for s in ('left', 'right'):
                if s in flat or s in want:
                    turned[s] = (i, foot_yaw(p.world_quat(s + 'Foot')), clip_yaw[s])
                else:
                    turned.pop(s, None)
                if step_of.get((i, s)) is None or s not in want:
                    turned.pop(s + '_carry', None)
        r['N'] = {k_: q.copy() for k_, q in p.N.items()}
        r['N_ik'] = {k_: q.copy() for k_, q in p.N.items()}
    # a ground sit, every frame of the window (the crossfade down, the hold, the rise): my robot body's legs out in
    # front along the floor (long_sit) on the ground clip's share of the frame; on any body the boots and the arms
    # resting on the floor where the pose would carry them under it (_boots_over_floor, _arms_over_floor)
    for w in wins:
        cmd = w[3]
        if w[2] != 'ground':
            continue
        ls = getattr(cmd, 'long_sit', False)
        for r in recs:
            if r['t'] < w[0] - 1e-6 or (w[1] is not None and r['t'] > w[1] + 1e-6):
                continue
            N2 = r['N']
            tot = sum(r['weights'].values())
            gw = r['weights'].get(cmd.clip, 0.0) / tot if tot > 1e-6 else 0.0
            if ls and gw > 1e-3:
                N2 = _long_sit_legs(c.h, c.body, N2, r['off'], r['M'], cmd.floor, gw)
            p = Pose(c.body, r['M'], {k_: q.copy() for k_, q in N2.items()}, r['off'])
            _boots_over_floor(p, c.body, cmd.floor)
            _arms_over_floor(p, c.body, cmd.floor)
            r['N'] = {k_: q.copy() for k_, q in p.N.items()}
            r['N_ik'] = {k_: q.copy() for k_, q in p.N.items()}
            if c.body.robot:
                # my robot body's hardware pass (the plant's) re-poses the arms and clamps the ankles: the limbs are
                # kept out of the floor again on what it leaves
                r['after_hardware'] = (lambda pp, b=c.body, fz=cmd.floor:
                                       (_boots_over_floor(pp, b, fz), _arms_over_floor(pp, b, fz)))
    for i, w in held:
        recs[i]['mode'] = 'seat'
    if inside:
        _log(loco, f'[seatOn] a seated boot still inside its chair after the push ({len(inside)} foot-frames): '
                   f'{inside[:6]} (frame, side, mm)')
    return len(held)


def _boot_skin(c):
    """the boots as the armature deforms them, for the chair push: per side, the vertices whose strongest weight is
    that side's foot or toes (the boot the audits see), thinned to 5 mm at rest, with their weights over the humanoid
    bones (a weight on any other bone counted on its nearest humanoid parent). The rigid foot points the maneuvers use
    missed the boot's ankle, which the shin's weights carry: a chair leg stood 14 mm into it where they read clear
    -> {side: (V rest points in the armature's space (n, 3), {humanoid name: weights (n,)}) or None}, cached"""
    return _limb_skin(c, ('Foot', 'Toes'), '_boot_skin')


ARM_PARTS = ('UpperArm', 'LowerArm', 'Hand')


def _arm_skin(c):
    """the arms as the armature deforms them (the vertices whose strongest weight is the upper arm, the forearm, the
    hand or a finger: _limb_skin), for keeping a forearm laid on the floor out of it, cached"""
    return _limb_skin(c, ARM_PARTS, '_arm_skin', descendants=True)


def _limb_skin(c, parts, attr, descendants=False):
    """per side, the skin a limb carries: the vertices whose strongest weight is that side's humanoid bones `parts`
    (descendants: and every bone under them, a hand's fingers), thinned to 5 mm at rest, with their weights over the
    humanoid bones (a weight on any other bone counted on its nearest humanoid parent), cached on c as `attr`"""
    cache = getattr(c, attr, None)
    if cache is not None:
        return cache
    h = c.h
    hum_of = {b: nm for nm, b in h.humanoid.items()}
    bones = h.arm.data.bones

    def humanoid_of(bname):
        b = bones.get(bname) if bname else None
        while b is not None and b.name not in hum_of:
            b = b.parent
        return hum_of[b.name] if b is not None else None
    inv = h.arm.matrix_world.inverted()
    out = {}
    for s in ('left', 'right'):
        want = {h.humanoid.get(s + part) for part in parts} - {None}
        if descendants:
            for b in list(want):
                if b in bones:
                    want |= {d.name for d in bones[b].children_recursive}
        V, WL = [], []
        for o in h.meshes:
            if not o.vertex_groups:
                continue
            idx = {g.index: g.name for g in o.vertex_groups}
            if not want & set(idx.values()):
                continue
            to_h = {gi: humanoid_of(nm) for gi, nm in idx.items()}
            M = inv @ o.matrix_world
            for v in o.data.vertices:
                best, bw = None, -1.0
                for g in v.groups:
                    if g.weight > bw:
                        bw, best = g.weight, g.group
                if idx.get(best) not in want:
                    continue
                ws = {}
                for g in v.groups:
                    hn = to_h.get(g.group)
                    if hn is not None and g.weight > 0.0:
                        ws[hn] = ws.get(hn, 0.0) + g.weight
                tot = sum(ws.values())
                if tot > 0.0:
                    V.append(tuple(M @ v.co))
                    WL.append({k: w / tot for k, w in ws.items()})
        if not V:
            out[s] = None
            continue
        V = np.array(V, dtype=np.float64)
        _u, first = np.unique(np.floor(V / 0.005).astype(np.int64), axis=0, return_index=True)
        first = np.sort(first)
        V, WL = V[first], [WL[i] for i in first]
        names = sorted({k for d in WL for k in d})
        out[s] = (V, {nm: np.array([d.get(nm, 0.0) for d in WL]) for nm in names})
    setattr(c, attr, out)
    return out


def _boot_pts(p, c, side):
    """the boot's points (_boot_skin) where the Pose p deforms them (linear blend skinning, as the armature does): (n, 3)
    world, or None"""
    return _skin_pts(p, c, _boot_skin(c).get(side))


def _skin_pts(p, c, sk):
    """a limb's skin (_limb_skin's (V, weights)) where the Pose p deforms it: (n, 3) world, or None"""
    if sk is None:
        return None
    V, W = sk
    P = np.zeros_like(V)
    for nm, w in W.items():
        R = np.array(p.world_quat(nm).to_matrix())
        head = np.array(c.h.rest_head[c.h.humanoid[nm]])
        P += w[:, None] * ((V - head) @ R.T + np.array(p.world_pos(nm)))
    return P


def _boot_depth(p, c, side, solid):
    """how deep (m) the boot's deepest point is inside the chair's parts (0: clear)"""
    P = _boot_pts(p, c, side)
    deep = 0.0
    for bvh, lo, hi in (solid or ()):
        for i in np.flatnonzero(np.all((P >= lo) & (P <= hi), axis=1)) if P is not None else ():
            q = Vector(P[i])
            loc, nrm, _k, d = bvh.find_nearest(q, 0.3)
            if loc is not None and (q - loc).dot(nrm) < 0.0 and _inside_bvh(bvh, q):
                deep = max(deep, d)
    return deep


PUSH_DIRS = [Vector((math.cos(2 * math.pi * k / 16), math.sin(2 * math.pi * k / 16), 0.0)) for k in range(16)] + \
    [Vector((0.0, 0.0, -1.0))]


def _clear_along(bvh, Q, inside_idx, d, clear):
    """the least distance t >= 0 that moves every point of Q along d clear of the part (each point's span inside it
    along the ray, entry to exit, grown by clear, is forbidden; a point already inside forbids up to its exit)"""
    spans = []
    for i, q in enumerate(Q):
        qv = Vector(q)
        h1 = bvh.ray_cast(qv, d, 1.0)
        if h1[0] is None:
            continue
        if i in inside_idx:
            spans.append((-1e9, h1[3] + clear))
            continue
        h2 = bvh.ray_cast(h1[0] + d * 1e-5, d, 1.0)
        spans.append((h1[3] - clear, h1[3] + (h2[3] if h2[0] is not None else 0.0) + clear))
    t = 0.0
    moved = True
    while moved:
        moved = False
        for a, b in spans:
            if a < t < b:
                t, moved = b, True
    return t


def _push_needed(p, c, side, solid, clear=0.012, prefer=None):
    """the least move that takes this foot's boot out of the chair, `clear` beyond, or None when it is clear: for each
    part with boot points inside (behind its nearest face and inside by a parity ray), the shortest translation over
    16 horizontal ways and straight down that leaves every point of the boot outside it, those that would pass into it
    included (a boot round a 4 cm chair leg must step off it whole: moved toward the nearest face of its deepest
    point, it went 2-3 cm and stayed on the leg). prefer: the way chosen on the neighbouring frame, kept unless another
    is clearly shorter (a foot pushed left on one frame and right on the next shakes)"""
    if not solid:
        return None
    P = _boot_pts(p, c, side)
    if P is None:
        return None
    total = None
    for bvh, lo, hi in solid:
        near = np.flatnonzero(np.all((P >= lo) & (P <= hi), axis=1))
        ins = []
        for i in near:
            q = Vector(P[i])
            loc, nrm, _k, d = bvh.find_nearest(q, 0.3)
            # inside: behind the nearest face AND an odd count of crossings up, part by part
            if loc is None or (q - loc).dot(nrm) >= 0.0 or not _inside_bvh(bvh, q):
                continue
            if d > 1e-4:
                ins.append(i)
        if not ins:
            continue
        # the boot's points within reach of the part, thinned to 1.5 cm for the search (each inside point kept)
        m = (P[:, 2] >= lo[2] - 0.01) & (P[:, 2] <= hi[2] + 0.01) & \
            np.all(np.abs(P[:, :2] - (lo[:2] + hi[:2]) / 2) <= (hi[:2] - lo[:2]) / 2 + 0.30, axis=1)
        cand = np.flatnonzero(m)
        _u, first = np.unique(np.floor(P[cand] / 0.015).astype(np.int64), axis=0, return_index=True)
        keep = sorted(set(cand[first].tolist()) | set(ins))
        Q = P[keep]
        ins_q = {keep.index(i) for i in ins}
        best = None
        for d in PUSH_DIRS:
            t = _clear_along(bvh, Q, ins_q, d, clear)
            cost = t * (1.0 + 0.6 * (1.0 - d.dot(prefer))) if prefer is not None else t
            if best is None or cost < best[0]:
                best = (cost, d * t)
        v = best[1]
        total = v if total is None or v.length > total.length else total
    return total


_RAY_UP = Vector((0.0123, 0.0217, 1.0)).normalized()


def _chair_solid(chair):
    """the chair's visible meshes, each its own world-space BVH with its box: [(bvh, lo, hi)], as the audits test a
    boot against each object. One BVH over all of them read a point deep in a leg as outside: the leg's top and the
    pan's underside are coplanar, so the parity ray up counts the two as one crossing and then the pan's top"""
    from ...placement import _world as W
    meshes = [o for o in [chair] + list(chair.children_recursive) if o.type == 'MESH' and W.visible(o)]
    W.update()
    dg = W.depsgraph()
    out = []
    for o in meshes:
        bvh = W.world_bvh([o], dg)
        if bvh is not None:
            co = W.world_verts(o, dg)
            out.append((bvh, co.min(axis=0) - 0.01, co.max(axis=0) + 0.01))
    return out


def _inside_bvh(bvh, p):
    n, org = 0, Vector(p)
    for _ in range(16):
        hit = bvh.ray_cast(org, _RAY_UP, 50.0)
        if hit[0] is None:
            break
        n += 1
        org = hit[0] + _RAY_UP * 1e-5
    return n % 2 == 1


def _leg_reach(p, side, target):
    """a two-bone leg solve on the Pose p, full weight, the foot keeping its world turn (the recentring moves the hips,
    not the planted feet)"""
    up, mid, end = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
    w_ft = p.world_quat(end).copy()
    a, b, e = p.world_pos(up).copy(), p.world_pos(mid).copy(), p.world_pos(end).copy()
    lu, ll = (a - b).length, (b - e).length
    dist = min(max((a - target).length, abs(lu - ll) + 0.02), lu + ll - 0.005)
    desired = math.acos(max(-1.0, min(1.0, (lu * lu + ll * ll - dist * dist) / (2 * lu * ll))))
    vba, vbc = a - b, e - b
    axis = vbc.cross(vba)
    if axis.length_squared > 1e-10:
        p.apply_world_delta(mid, Quaternion(axis.normalized(), vba.angle(vbc, 0.0) - desired))
    e2 = p.world_pos(end).copy()
    if (e2 - a).length > 1e-6 and (target - a).length > 1e-6:
        p.apply_world_delta(up, (e2 - a).normalized().rotation_difference((target - a).normalized()))
    p.set_world_quat(end, w_ft)


def _swivel_to(p, body, side, yaw):
    """my robot body's leg swung round the line from its hip to its ankle (the knee goes aside, the ankle stays where it
    is) until, through its joint clamps, its foot faces `yaw` (rad): the ankle has no twist, so the shin's turn is the
    foot's. At most SWIVEL_MAX; the secant on the clamped foot's turn, SWIVEL_ROUNDS at most -> the turn left over"""
    from ..controller.plant import foot_yaw
    from ..controller.pose import Pose, leg_clamps
    up, ft = side + 'UpperLeg', side + 'Foot'
    w_ft = p.world_quat(ft).copy()

    def miss():
        q = Pose(body, p.M, leg_clamps(body, dict(p.N)), p.off)
        return _wrap_pi(yaw - foot_yaw(q.world_quat(ft)))
    axis = p.world_pos(ft) - p.world_pos(up)
    e0 = miss()
    if axis.length < 1e-6 or abs(e0) < SWIVEL_TOL:
        return e0
    axis.normalize()
    phi0, phi, now = 0.0, max(-SWIVEL_MAX, min(SWIVEL_MAX, e0)), 0.0
    e = e0
    for _ in range(SWIVEL_ROUNDS):
        p.apply_world_delta(up, Quaternion(axis, phi - now))
        now = phi
        p.set_world_quat(ft, w_ft)
        e1 = miss()
        if abs(e1) < SWIVEL_TOL or abs(e1 - e0) < 1e-9:
            e = e1
            break
        phi0, phi, e0 = phi, phi - e1 * (phi - phi0) / (e1 - e0), e1
        phi = max(-SWIVEL_MAX, min(SWIVEL_MAX, phi))
        e = e1
    return e


def _open_window(loco, kind, cmd):
    loco.__dict__.setdefault('_seat_windows', []).append([loco.ctrl.time, None, kind, cmd])


def _close_window(loco):
    for w in reversed(getattr(loco, '_seat_windows', [])):
        if w[1] is None:
            w[1] = loco.ctrl.time
            return


# ================================================================================================ the commands
class _Composite(_Cmd):
    """runs sub-commands in order inside one queue entry (the approach of a seat); no frame is spent between them"""

    def _run_subs(self, loco, dt):
        while self.subs:
            sub = self.subs[0]
            if not sub.started:
                sub.start(loco)
                sub.started = True
            inp = sub.step(loco, dt)
            if inp is not None:
                return inp
            self.subs.pop(0)
        return None


class FaceCamera(TurnTo):
    """faceCamera for a walking body: a turn on the spot toward the camera (the scene's or camera=) where it stands at
    the frame the command starts, plus offset (rad)"""

    def __init__(self, camera=None, offset=0.0):
        super().__init__()
        self.camera, self.offset = camera, offset

    def start(self, loco):
        c = loco.ctrl
        p = _camera_pos(self.camera, _frame(loco))
        if p is None:
            _log(loco, '[faceCamera] need a camera (scene.camera or camera=)')
            self.heading = c._heading
        else:
            f = c.feet_world_position
            self.heading = heading_of(p.x - f.x, p.y - f.y) + self.offset
        super().start(loco)


BACK_MIN = 0.5              # s: an emote eases back to the standing pose over at least this
SCOOT_T = 0.5               # s: a sitter shifts forward on the seat over this before a stand-up that would lean back
BACK_ROOM = 0.30            # m: the room behind the spot at foot height a backing step needs (less: in from the side)


class EmoteCmd(_Emote):
    """emote for a walking body: playEmote (locomotion suspended) for `seconds` (default the clip once), stopEmote;
    facing 'keep', 'camera' (toward the camera at the frame it starts, + offset rad), a heading in degrees or None (the
    engine's default). This edition's: the emote comes in and goes out through the standing pose (_hold_stand_pose: no
    rest-pose shortfall), and align=True holds the clip over the root (its hips' offset at its first frame taken off:
    the library's cheer stands 25 cm behind its origin, which slid the whole body back as it came in)"""

    def __init__(self, slot, seconds=None, facing='keep', camera=None, offset=0.0, align=True, **kw):
        self.want_camera = facing == 'camera'
        super().__init__(slot, seconds, facing='keep' if self.want_camera else facing, **kw)
        self.camera, self.offset, self.align = camera, offset, align

    def start(self, loco):
        c = loco.ctrl
        if is_sitting(self.slot):
            _log(loco, f"[emote] '{self.slot}' is a sitting clip: seat_on / sit_on_ground place the body for it")
        if self.want_camera:
            p = _camera_pos(self.camera, _frame(loco))
            if p is not None:
                f = c.feet_world_position
                self.facing = math.degrees(heading_of(p.x - f.x, p.y - f.y) + self.offset)
        acts = c.__dict__.setdefault('_emote_actions', {})
        if self.slot not in acts:
            c.load_emote(self.slot, loop=self.loop)
        a = acts.get(self.slot)
        if a is None:
            _log(loco, f"[emote] no '{self.slot}' clip in the library")
            self.phase, self.left, self.stand = 'out', 0.0, None
            return
        cc = a.clip
        if self.align and not getattr(cc, '_aligned', False):
            cc.P[:, :2] -= cc.P[0, :2].copy()
            cc._aligned = True
        if self.facing == 'keep':
            c._emote_facing_y = c._heading
        elif self.facing is None:
            c._emote_facing_y = None
        else:
            c._emote_facing_y = self.facing * math.pi / 180.0
        # playEmote, its weight driven in step with the walk's fade (the controller damps the walk's clips out at
        # lambda 12 while an emote plays): the two sum to one, no rest pose fills a shortfall and nothing snaps
        for k, b in acts.items():
            if k != self.slot and b is not None and b.enabled and b.get_effective_weight() > 0.01:
                b.fade_out(self.fade_in)
        a.reset()
        a.time_scale = 1.0
        a.play()
        a.set_effective_weight(0.0)
        c._active_emote = self.slot
        self.act = a
        self.stand = _stand_pose_clip(c)
        self.left = self.seconds if self.seconds is not None else a.clip.duration
        self.phase = 'in'

    def step(self, loco, dt):
        c = loco.ctrl
        if self.phase == 'in':
            walk = sum(b.weight for b in (c._actions or {}).values() if b is not None)
            others = sum(b.get_effective_weight() for k, b in getattr(c, '_emote_actions', {}).items()
                         if b is not None and b is not self.act and b.enabled)
            w = min(1.0, max(0.0, 1.0 - walk * math.exp(-12.0 * dt) - others))
            self.act.set_effective_weight(w)
            if w >= 0.995:
                self.act.set_effective_weight(1.0)
                self.phase = 'play'
        self.left -= dt
        if self.phase in ('in', 'play'):
            if self.left <= 0:
                if self.stand is not None:            # back through the standing pose (eased by hand), then stopEmote
                    _start_clip(c, self.stand, loop=True)
                    self.phase, self.t_back = 'back', 0.0
                else:
                    c.stop_emote(fade_out=self.fade_out)
                    self.phase, self.left = 'out', self.fade_out + 0.1
                    return (0.0, 0.0)
            else:
                return (0.0, 0.0)
        if self.phase == 'back':
            # a linear crossfade starts and stops at full speed: a clip that ends far from standing jerks at both ends
            self.t_back += dt
            e = _smooth(self.t_back / max(self.fade_out, BACK_MIN))
            _drive_cross(c, self.slot, self.stand, e)
            if e >= 1.0:
                c.stop_emote(fade_out=0.5)
                self.phase, self.left = 'out', 0.6
            return (0.0, 0.0)
        return (0.0, 0.0) if self.left > 0 else None


class Unseat(_Cmd):
    """unseat: from this frame the audits judge the body again (key_seated stops the seated mark here)"""

    def start(self, loco):
        loco.__dict__.setdefault('_unseat_times', []).append(loco.ctrl.time)


class SeatOn(_Composite):
    """seatOn routed through the controller (the module's doc)"""

    def __init__(self, chair, transition='stand_to_sit', face=None, sink=0.0, hip_back=None, hold=None, fade=0.25,
                 transition_dur=None, gait='walk', speed=None, camera=None, then=None, then_fade=0.5, via=None,
                 stand=None, back_up=0.35, instant=False):
        self.chair, self.transition, self.face, self.sink, self.hip_back = chair, transition, face, sink, hip_back
        self.hold, self.fade, self.transition_dur, self.gait, self.speed = hold, fade, transition_dur, gait, speed
        self.camera, self.then, self.then_fade, self.via, self.stand_opts = camera, then, then_fade, via, stand or {}
        self.back_up, self.instant = back_up, instant
        if instant and not then:
            self.then = SEAT_CLIP                     # seatOn's instant path holds a chair pose: the default seated loop

    # ---- the approach
    def start(self, loco):
        from ...placement import seating as SE
        c = loco.ctrl
        self.seat = seat = SE.find_seat_surface(self.chair)
        self.facing = facing = SE.chair_facing(self.chair, seat)
        SE._warn_bad_seat(self.chair, seat, facing)
        if self.face is not None:
            th = self.face
        elif facing is not None:
            th = facing
        else:
            p = _camera_pos(self.camera, _frame(loco))
            th = heading_of(p.x - seat['x'], p.y - seat['y']) if p is not None else c._heading
        self.th = th
        fwd = _fwd(th)
        tx, ty = seat['x'], seat['y']
        if facing is not None and 'pan_dx' in seat:
            back = -_fwd(facing)
            depth = abs(back.x) * seat['pan_dx'] + abs(back.y) * seat['pan_dy']
            shift = min(0.12, depth * 0.18)
            tx, ty = tx + back.x * shift, ty + back.y * shift
        self.target = Vector((tx, ty))
        self.fwd = fwd
        feet = c.feet_world_position
        if self.hip_back is not None:
            spot = (seat['x'] + fwd.x * self.hip_back, seat['y'] + fwd.y * self.hip_back)
        else:
            spot = loco.seat_spot((tx, ty), math.degrees(th), clip=self.transition)
        if self.instant:
            # no walk to it: the floor is the one under the spot
            z = c._ground_vector(spot[0], spot[1], max(feet.z, seat['z']) + 1.0)
            feet = Vector((feet.x, feet.y, z if z is not None else feet.z))
        # the backrest: the transition's last pose, settled on the pan where the walk will put her, measured against
        # the chair's parts over the pan; where the skin (a coat included) is inside its back, the target moves
        # forward until it clears it, before the walk (so the spot is right). A sitter turned away from the chair's
        # facing (face= on purpose) is left where the target puts her
        self.pan = pan_points(self.chair, seat) or [(seat['x'], seat['y'])]
        here = _surface_under([self.chair], tx, ty, seat['z'] + 0.5)
        self.parts_up = _upper_parts(self.chair, here if here is not None else seat['z'])
        self.back_ok = facing is not None and abs(_wrap_pi(th - facing)) < math.pi / 2
        self.push = 0.0
        if self.parts_up and self.back_ok:
            from ..controller.pose import root_matrix
            push = self._back_push(c, self.transition, root_matrix(spot[0], spot[1], feet.z, th),
                                   here if here is not None else seat['z'])
            if push > 0.0:
                self.push = push
                self.target = self.target + fwd * push
                tx, ty = self.target.x, self.target.y
                if self.hip_back is None:
                    spot = loco.seat_spot((tx, ty), math.degrees(th), clip=self.transition)
                _log(loco, f"[seatOn] '{self.chair.name}': the seated skin stood {push * 100 - BACK_CLEAR * 100:.1f} "
                           f'cm inside its back: the hips\' target moved {push * 100:.1f} cm forward')
        self.spot = spot
        self.subs = []
        self.auto_was = c.auto_maneuvers
        if self.instant:
            z = c._ground_vector(spot[0], spot[1], max(feet.z, seat['z']) + 1.0)
            self.spot_z = z if z is not None else feet.z
            c.auto_maneuvers = False
            self.phase = 'instant'
            _log(loco, f"[seatOn] '{self.chair.name}': the pan at {seat['z']:.3f} m; the take opens seated in "
                       f"'{self.then}' facing {math.degrees(th):.1f} deg, put on ({spot[0]:.3f}, {spot[1]:.3f}) for the "
                       f'hips to rest on ({tx:.3f}, {ty:.3f})')
            return
        bk = max(0.0, self.back_up)
        # the walk to a point back_up in front of the spot, the turn out of the chair there, and a step or two back onto
        # the spot (walkBackward): a sitter backs up to the seat, and the feet the sit starts on are freshly planted
        # (a turn's stance carries its lock to the first seat frame, where the plant hands the feet over). A backing step
        # plants the trailing foot about 0.25 m behind the root: a chair leaves that room under its pan, a bench boxed to
        # the floor does not (the example's: its face 19 cm behind the spot, the backing steps planted a boot 6 cm inside
        # it). With too little room behind the spot at foot height she comes in from the side, past the seat's end, as
        # the example's route does, and settles round to face out
        self.room = self._room_behind(feet.z, spot, fwd)
        side_in = self.room < BACK_ROOM and self.via is None
        if side_in:
            bk = 0.0
        pre = (spot[0] + fwd.x * bk, spot[1] + fwd.y * bk)
        if math.dist((feet.x, feet.y), pre) > 0.04:
            if self.via is not None:
                route = [tuple(p) for p in self.via] + [pre]
            elif side_in:
                route = self._side_route(feet, spot, fwd)
            else:
                front = (spot[0] + fwd.x * (bk + 0.6), spot[1] + fwd.y * (bk + 0.6))
                box = _box_xy(self.chair)
                direct = not _seg_hits_box((feet.x, feet.y), pre, (box[0] - 0.25, box[1] + 0.25, box[2] - 0.25,
                                                                    box[3] + 0.25))
                ahead = (feet.x - spot[0]) * fwd.x + (feet.y - spot[1]) * fwd.y > bk + 0.3
                route = [pre] if (direct and ahead) else route_around((feet.x, feet.y), front, box) + [pre]
            self.subs.append(FollowPath(route, speed=self.speed, gait=self.gait, arrive=0.012))
        self.subs.append(TurnTo(heading=th))
        if bk > 0.04:
            self.subs.append(FollowPath([spot], gait='walkBackward', arrive=0.012, turn_first=False))
            self.subs.append(TurnTo(heading=th))         # backing up along a line a little off squares it again
        c.auto_maneuvers = False
        self.phase = 'approach'
        parts = {o for o in [self.chair] + list(self.chair.children_recursive)}
        if parts & set(getattr(c.world, 'objects', ())):
            _log(loco, f"[seatOn] ⚠ '{self.chair.name}' is in the walking world: the controller's probes read its pan "
                       'as a step to climb, and the plant reads it as the ground over a foot under it. Keep seats out '
                       'of it, as the course keeps its rungs: CollisionWorld(exclude=[...the seat\'s meshes])')
        _log(loco, f"[seatOn] '{self.chair.name}': the pan at {seat['z']:.3f} m, facing "
                   f"{'(none: the camera / face=)' if facing is None else f'{math.degrees(facing):.1f} deg'}, she "
                   f"sits facing {math.degrees(th):.1f} deg; stands at ({spot[0]:.3f}, {spot[1]:.3f}) for the hips to "
                   f"end on ({tx:.3f}, {ty:.3f})")

    def _room_behind(self, floor_z, spot, fwd):
        """how far behind the spot (along -fwd) the seat's solids begin at foot height (rays at 4, 10 and 16 cm over
        the floor, on the spot's line and 10 cm to each side): the room a backing step has (m; 9: none in 1 m)"""
        from ...placement import _world as W
        meshes = [o for o in [self.chair] + list(self.chair.children_recursive) if o.type == 'MESH' and W.visible(o)]
        if not meshes:
            return 9.0
        rays = W.Rays(meshes)
        b = Vector((-fwd.x, -fwd.y, 0.0))
        s = Vector((fwd.y, -fwd.x, 0.0))
        best = 9.0
        for hz in (0.04, 0.10, 0.16):
            for k in (-0.1, 0.0, 0.1):
                o = Vector((spot[0], spot[1], floor_z + hz)) + s * k
                hit = rays.cast(o, b, 1.0)
                if hit:
                    best = min(best, hit[3])
        return best

    def _side_route(self, feet, spot, fwd):
        """the way in from the side: round the seat to a point past its end on her side, level with the seat's middle,
        then on to the spot (the example's route round its bench: the last leg runs out of the seat's end, away from
        it, so the feet never step back into it)"""
        x0, x1, y0, y1 = _box_xy(self.chair)
        side = Vector((fwd.y, -fwd.x))
        sp = Vector(spot)
        corners = [Vector((x, y)) for x in (x0, x1) for y in (y0, y1)]
        sgn = 1.0 if (Vector((feet.x, feet.y)) - sp).dot(side) >= 0.0 else -1.0
        out = max((cn - sp).dot(side * sgn) for cn in corners) + 0.33
        back = max(0.0, min(0.41, max((sp - cn).dot(Vector(fwd)) for cn in corners) - 0.05))
        p = sp + side * (sgn * out) - Vector(fwd) * back
        route = route_around((feet.x, feet.y), (p.x, p.y), (x0, x1, y0, y1)) if math.dist((feet.x, feet.y), p) > 0.05 \
            else []
        return route + [tuple(spot)]

    # ---- the sit-down
    def _underside(self, c, cc, t, M, posed):
        """the seat skin's lowest over the pan with the clip at t posed at the root M. The measures pose the body at the
        floor's height, before any lift: on a high seat the seated skin then lies up to 25 cm under the pan, and up-rays
        cast from 25 cm under it (the engine's window, for the lifted body) started inside it on a 0.62 m stool and
        read it 0.9 cm high. The seat skin is the pelvis and thighs only (no foot to catch): cast from 0.6 m under"""
        posed.pose(cc, t, M)
        return skin_lowest(c.h, self.pan, self.seat_here - UNDER_FROM, reach=2 * UNDER_FROM)

    def _back_push(self, c, slot_or_clip, M, seat_z, times=None, sink=None, poser=None):
        """how far forward the posed skin must move to clear the chair's back (back_push): the clip (a slot or a
        ControllerClip) at `times` (default its last pose), or poser(posed, t, M) for each time (a crossfade), each
        settled on the pan first (its seat skin's lowest over the pan put at the seat's height less sink)"""
        cc = c._emote_clip(slot_or_clip) if isinstance(slot_or_clip, str) else slot_or_clip
        if cc is None:
            return 0.0
        sink = self.sink if sink is None else sink
        times = [cc.duration] if times is None else times
        pan = getattr(self, 'pan', None) or [(self.seat['x'], self.seat['y'])]
        if poser is None:
            def poser(posed, t, Mt):
                posed.pose(cc, float(t), Mt)
        push = 0.0
        with _Posed(c.h, c.body) as posed:
            for t in times:
                Mt = M(t) if callable(M) else M
                poser(posed, t, Mt)
                zl = skin_lowest(c.h, pan, seat_z - UNDER_FROM, reach=2 * UNDER_FROM)
                Mz = Mt.copy()
                if zl is not None:
                    Mz.translation = Vector((Mt.translation.x, Mt.translation.y,
                                             Mt.translation.z + (seat_z - sink) - zl))
                    poser(posed, t, Mz)
                push = max(push, back_push(skin_points(c.h, loose=False), self.parts_up, seat_z, self.fwd,
                                           P_loose=_loose_points(c.h)))
        return push

    def _begin(self, loco):
        c = loco.ctrl
        M = c.pose.M.copy()
        self.root0 = M.translation.copy()
        # beginSeated(transition, fadeIn), crossfaded from the standing pose taken at once (_take_stand_pose)
        cc = c._emote_clip(self.transition)
        _take_stand_pose(c)
        c.play_emote(self.transition, fade_in=self.fade, fade_out=self.fade)
        self.clip_dur = cc.duration if cc is not None else 0.0
        self.span = self.transition_dur or self.clip_dur
        self.cc = cc
        self.off_end = c.body.H['hips'] + Vector(cc.root_curve[-1])
        hips_end = M @ self.off_end
        self.dxy = Vector((self.target.x - hips_end.x, self.target.y - hips_end.y))
        if self.dxy.length > 0.2:
            _log(loco, f'[seatOn] the body stands {self.dxy.length:.2f} m off its spot (blocked on the way?): '
                       'the recentring is held to 0.2 m')
            self.dxy *= 0.2 / self.dxy.length
        here = _surface_under([self.chair], self.target.x, self.target.y, self.seat['z'] + 0.5)
        if here is None:
            _log(loco, "[seatOn] settle: no chair surface beneath the hips' target: resting at the pan's height")
        self.seat_here = here if here is not None else self.seat['z']
        self.target_z = self.seat_here - self.sink
        self.pan = pan_points(self.chair, self.seat)
        if not self.pan:
            self.pan = [(self.seat['x'], self.seat['y'])]
        Mf = M.copy()
        Mf.translation = Vector((self.root0.x + self.dxy.x, self.root0.y + self.dxy.y, self.root0.z))
        if self.parts_up and self.back_ok:
            # the backrest again where she really stands (the arrival is a centimetre or two off the spot, and turned
            # by the walk's last step): what is left inside goes into the recentring, the feet held
            res = self._back_push(c, cc, Mf, self.seat_here)
            if res > 0.002:
                f2 = Vector((self.fwd.x, self.fwd.y))
                self.target = self.target + f2 * res
                self.dxy = self.dxy + f2 * res
                if self.dxy.length > 0.25:
                    self.dxy *= 0.25 / self.dxy.length
                Mf.translation = Vector((self.root0.x + self.dxy.x, self.root0.y + self.dxy.y, self.root0.z))
                self.push += res
                _log(loco, f'[seatOn] the back measured again where she stands: {res * 100:.1f} cm more forward')
        self.Mf = Mf
        # every frame from 40 % in (ten samples let the skin dip 1.9 cm into a stool's pad between two of them)
        ts = np.linspace(CLAMP_FROM * self.clip_dur, self.clip_dur,
                         max(UNDER_SAMPLES, int(math.ceil((1.0 - CLAMP_FROM) * self.clip_dur * _fps())) + 1))
        zl = []
        with _Posed(c.h, c.body) as posed:
            for t in ts:
                zl.append(self._underside(c, cc, float(t), Mf, posed))
            knees = {s: posed.bone_z(s + 'LowerLeg') for s in ('left', 'right') if s + 'LowerLeg' in c.h.humanoid}
        self.ts = [float(t) for t, z in zip(ts, zl) if z is not None]
        self.zl = [float(z) for z in zl if z is not None]
        if self.zl and zl[-1] is not None:
            self.settle = self.target_z - zl[-1]
        else:
            self.settle = 0.0
            _log(loco, '[seatOn] could not cast up through the seated skin over the pan: the root holds its height; '
                       'verify she sits flush')
        self.dz_t, self.dz_v = self._dz_curve()
        # the knees of the settled pose (its thighs on the pan): a foot reaching for the floor keeps its knee over this
        self.knee_floor = {s: z + self.settle - KNEE_GIVE for s, z in knees.items()}
        self.kf_tr = dict(self.knee_floor)                  # the sit-down's (and the reverse's)
        self.cur_kf = dict(self.knee_floor)
        self.t = 0.0
        self.phase = 'down'
        loco.__dict__.setdefault('_seats', []).append({'chair': self.chair.name, 't0': c.time, 'heading': self.th,
                                                       'facing': self.facing, 'kind': 'chair'})
        loco._seat = {'kind': 'chair', 'cmd': self}
        _open_window(loco, 'chair', self)
        self.extra = Vector((0.0, 0.0))
        arr = math.hypot(self.root0.x - self.spot[0], self.root0.y - self.spot[1])
        if not self.instant:
            _log(loco, f'[seatOn] sits down over {self.span:.2f} s ({self.transition}), standing {arr * 100:.1f} cm '
                       f'off its spot: the hips recentred by {self.dxy.length * 100:.1f} cm (the feet held), the '
                       f'underside settled {self.settle * 100:+.1f} cm onto the pan at {self.seat_here:.3f} m; the '
                       f'clamp watches {len(self.zl)} samples from {CLAMP_FROM:.0%} in')

    def _dz_curve(self):
        """the descent's lift, frame by frame: the settle eased in over its second half, never under the clamp (the
        lowest skin over the pan on the pan, from 40 % in); smoothed so the switch between them is no kink, the clamp
        kept (lift only)"""
        dt = 1.0 / _fps()
        n = int(math.ceil(self.span / dt)) + 1
        tf = np.arange(n + 1) * dt
        k = np.array([_smooth((min(1.0, t / max(self.span, 1e-6)) - SETTLE_FROM) / (1.0 - SETTLE_FROM)) for t in tf])
        ease = self.settle * k
        clamp = np.full(len(tf), -1e9)
        for i, t in enumerate(tf):
            if t / max(self.span, 1e-6) >= CLAMP_FROM:
                zl = self._zlow(min(t, self.clip_dur))
                if zl is not None:
                    clamp[i] = self.target_z - zl
        dz = np.maximum(ease, clamp)
        for _ in range(6):
            sm = dz.copy()
            sm[1:-1] = 0.25 * dz[:-2] + 0.5 * dz[1:-1] + 0.25 * dz[2:]
            sm[-1] = self.settle
            dz = np.maximum(sm, clamp)
        dz[0] = 0.0
        return tf, dz

    def root(self, c, xy_k, dz, phase=None):
        """the seated root: the standing root moved by the recentring (xy_k of it) and the extra shift (a seated loop's
        or a stand-up's), its height by dz over where the seat began. Logged by frame for the feet: the recentring they
        hold against, and the phase (the thigh rests on the pan in the held ones)"""
        t = c.pose.M.translation.copy()
        t.x = self.root0.x + self.dxy.x * xy_k + self.extra.x
        t.y = self.root0.y + self.dxy.y * xy_k + self.extra.y
        c.pose.M.translation = t
        c.pose.invalidate()
        c.seat_dz = dz
        self.cur_dz, self.cur_xy_k = dz, xy_k
        key = round(c.time, 6)
        self.__dict__.setdefault('k_log', {})[key] = xy_k
        self.__dict__.setdefault('phase_log', {})[key] = phase or self.phase
        self.__dict__.setdefault('kf_log', {})[key] = dict(getattr(self, 'cur_kf', {}) or {})

    def _zlow(self, t):
        if not self.ts:
            return None
        if t <= self.ts[0]:
            return None
        return float(np.interp(t, self.ts, self.zl))

    # ---- the seated loop (then=)
    def _begin_then(self, loco):
        c = loco.ctrl
        if self.then not in getattr(c, '_emote_actions', {}):
            c.load_emote(self.then, loop=True)
        lc = c._emote_clip(self.then, loop=True)
        off_loop = c.body.H['hips'] + Vector(lc.root_curve[0])
        R = self.Mf.to_3x3()
        d = R @ (self.off_end - off_loop)
        self.then_shift = Vector((d.x, d.y))
        Ml = self.Mf.copy()
        Ml.translation = Vector((self.Mf.translation.x + d.x, self.Mf.translation.y + d.y, self.root0.z))
        self.push_then = 0.0
        if self.parts_up and self.back_ok:
            # the loop leans and fidgets in its own way (the fidget loop sits 4 cm further back than the sit-down's
            # last pose): sampled over its length, the hips carried forward as far as its back needs
            res = self._back_push(c, lc, Ml, self.seat_here,
                                  times=[float(x) for x in np.linspace(0.0, lc.duration,
                                                                       max(16, int(lc.duration * _fps() / 2)),
                                                                       endpoint=False)])
            if res > 0.002:
                self.push_then = res
                f2 = Vector((self.fwd.x, self.fwd.y))
                self.then_shift = self.then_shift + f2 * res
                Ml.translation = Vector((Ml.translation.x + f2.x * res, Ml.translation.y + f2.y * res, self.root0.z))
                _log(loco, f"[seatOn] then '{self.then}': its back measured over the loop: {res * 100:.1f} cm forward")
        with _Posed(c.h, c.body) as posed:
            z = self._underside(c, lc, 0.0, Ml, posed)
            knees = {s: posed.bone_z(s + 'LowerLeg') for s in ('left', 'right') if s + 'LowerLeg' in c.h.humanoid}
        self.settle_then = (self.target_z - z) if z is not None else self.settle
        self.kf_then = {s: kz + self.settle_then - KNEE_GIVE for s, kz in knees.items()}
        c.play_emote(self.then, fade_in=self.then_fade, fade_out=self.then_fade)
        self.t = 0.0
        self.phase = 'then'
        loco._seat.update({'then': self.then, 'then_clip': lc})
        _log(loco, f"[seatOn] then '{self.then}': the root carried {d.length * 100:.1f} cm so the hips stay on the "
                   f'seat, its underside settled {self.settle_then * 100:+.1f} cm')

    def _begin_instant(self, loco):
        """seatOn's instant path (the engine snaps a VRM into the chair pose): the body put on the spot facing out of
        the chair (controller.place), the seat measured as a sit-down measures it (_begin: the root, the recentring,
        the settle) and the seated loop as a loop after it (_begin_then: the root carried so its hips rest on the seat,
        its own settle), then the loop held at full weight at once, its settle applied, no descent. stand_up and the
        walk after it work from here as from any seat; the springs start over on the seated pose"""
        c = loco.ctrl
        c.place((self.spot[0], self.spot[1], self.spot_z), self.th)
        if c.time > 1e-9 and getattr(loco, 'frame', None) is not None:
            loco.__dict__.setdefault('_spring_resets', []).append(loco.frame)
        self._begin(loco)
        self._begin_then(loco)
        acts = getattr(c, '_emote_actions', {})
        for k, a in acts.items():
            if a is not None and k != self.then:
                a.stop()
                a.set_effective_weight(0.0)           # a stopped action keeps its last weight otherwise: still 'emoting'
        acts[self.then].set_effective_weight(1.0)
        for a in (c._actions or {}).values():
            if a is not None:
                a.weight = 0.0
        self.extra = self.then_shift.copy()
        self.cur_kf = dict(self.kf_then)
        self.root(c, 1.0, self.settle_then, phase='seated')
        self.phase, self.t = 'seated', 0.0

    def step(self, loco, dt):
        c = loco.ctrl
        if self.phase == 'instant':
            self._begin_instant(loco)
        if self.phase == 'approach':
            inp = self._run_subs(loco, dt)
            if inp is not None:
                return inp
            self._begin(loco)
        if self.phase == 'down':
            self.t += dt
            u = min(1.0, self.t / max(self.span, 1e-6))
            k = _smooth((u - SETTLE_FROM) / (1.0 - SETTLE_FROM))
            dz = float(np.interp(self.t, self.dz_t, self.dz_v))      # the settle, lifted by the clamp where it must
            self.root(c, k, dz)
            if u < 1.0:
                return (0.0, 0.0)
            self.root(c, 1.0, self.settle, phase='seated')
            if not self.then:
                self.phase, self.t = 'seated', 0.0
                return (0.0, 0.0)
            # the seated loop starts in this frame's mixer update: its first step is this frame's too
            self._begin_then(loco)
        if self.phase == 'then':
            self.t += dt
            w = min(1.0, self.t / max(self.then_fade, 1e-6))
            self.extra = self.then_shift * w
            self.cur_kf = {s: self.kf_tr[s] * (1.0 - w) + self.kf_then.get(s, self.kf_tr[s]) * w for s in self.kf_tr}
            self.root(c, 1.0, self.settle * (1.0 - w) + self.settle_then * w, phase='then' if w < 1.0 else 'seated')
            if w >= 1.0:
                self.phase, self.t = 'seated', 0.0
            return (0.0, 0.0)
        if self.phase == 'seated':
            if self.hold is None:
                c.auto_maneuvers = self.auto_was
                return None
            self.t += dt
            if self.t < self.hold:
                return (0.0, 0.0)
            self.stand = StandUp(**self.stand_opts)
            self.stand.start(loco)
            self.stand.started = True
            self.phase = 'standing'
        if self.phase == 'standing':
            inp = self.stand.step(loco, dt)
            if inp is None:
                c.auto_maneuvers = self.auto_was
                return None
            return inp
        return None


class SitOnGround(_Composite):
    """sitOnGround for a walking body (the module's doc)"""

    def __init__(self, clip=GROUND_CLIP, at=None, face=None, camera=None, fade=1.0, hold=None, sink=0.005,
                 hip_height=0.08, gait='walk', speed=None, stand=None):
        self.clip, self.at, self.face, self.camera, self.fade, self.hold = clip, at, face, camera, fade, hold
        self.sink, self.hip_height, self.gait, self.speed, self.stand_opts = sink, hip_height, gait, speed, stand or {}

    def start(self, loco):
        c = loco.ctrl
        self.subs = []
        feet = c.feet_world_position
        at = (feet.x, feet.y) if self.at is None else tuple(self.at[:2])
        self.xy = at
        if math.dist((feet.x, feet.y), at) > 0.04:
            self.subs.append(FollowPath([at], speed=self.speed, gait=self.gait))
        if self.face is not None:
            th = self.face
        else:
            fr = _frame(loco)
            p = _camera_pos(self.camera, fr)
            th = heading_of(p.x - at[0], p.y - at[1]) if p is not None else None
        self.th = th
        if th is not None:
            self.subs.append(TurnTo(heading=th))
        self.phase = 'approach'

    def _begin(self, loco):
        c = loco.ctrl
        M = c.pose.M.copy()
        self.root0 = M.translation.copy()
        floor = c._ground_vector(self.root0.x, self.root0.y, self.root0.z + 1.0)
        self.floor = floor if floor is not None else self.root0.z
        # beginSeated(clip): the standing pose taken at once, the ground clip crossfaded in from it by hand (eased:
        # the library has no stand-to-ground clip, the crossfade is the sit-down)
        self.stand = _take_stand_pose(c)
        if _start_clip(c, self.clip, loop=True) is None:
            fb = SEAT_CLIP
            if self.clip != fb and _start_clip(c, fb, loop=True) is not None:
                _log(loco, f"[sitOnGround] ⚠ no '{self.clip}' clip in the library: falling back to the CHAIR clip "
                           f"'{fb}', which reads wrong on the floor (the legs dangle or clip)")
                self.clip = fb
            else:
                _log(loco, f"[sitOnGround] ⚠ no '{self.clip}' or chair-sit clip in the library: seating without a "
                           'pose')
                self.clip = self.stand
        cc = c._emote_clip(self.clip, loop=True)
        low = None
        # my robot body cannot fold cross-legged: it sits with its legs out in front (long_sit), measured so
        self.long_sit = long_sit(c.body, self.clip)
        if self.long_sit:
            _log(loco, f"[sitOnGround] my robot body cannot fold into '{self.clip}' (hips flex 98 deg, knees 112): "
                       'it sits with its legs out in front along the floor')
        with _Posed(c.h, c.body, long_sit=(self.floor, 'all') if self.long_sit else None, ground=self.floor) as posed:
            posed.pose(cc, min(0.5, cc.duration), M)
            hp = posed.hips()
            pts = [(hp.x + i * GROUND_GRID, hp.y + j * GROUND_GRID) for i in range(-2, 3) for j in range(-2, 3)]
            # the lowest of the skin itself within the grid's reach (the crossfade's clamp measures the same skin): the
            # engine's grid of up-rays passes between a hip's frame or a forearm laid on the floor and reads the body
            # higher than it is; the grid stays the measure where no skin is found
            low = _lowest_near(skin_points(c.h, loose=False), (hp.x, hp.y), half=2 * GROUND_GRID)
            if low is None:
                low = _body_lowest(c.h, pts, self.floor - 0.6, 1.5)
            hz = hp.z
        if low is not None:
            self.settle = (self.floor - low) + self.sink
        else:
            self.settle = (self.floor + self.hip_height) - hz
            _log(loco, '[sitOnGround] could not cast the seated mesh: the hip_height fallback; verify she rests on the '
                       'floor')
        # the crossfade is the sit-down: the body kept out of the floor through it (_ground_lift), measured on the
        # blended poses before the take
        a_st = getattr(c, '_emote_actions', {}).get(self.stand)
        sc_ = a_st.clip if a_st is not None else cc
        fade = max(self.fade, 1e-6)
        self.lz_t, self.lz_v, lifted = _ground_lift(
            c, sc_, a_st.time if a_st is not None else 0.0, cc, 0.0, M, self.floor, self.fade,
            lambda t: _smooth(t / fade), lambda t: self.settle * _smooth(t / fade),
            long_sit_side='b' if self.long_sit else None)
        if lifted > 0.005:
            _log(loco, f'[sitOnGround] the crossfade held out of the floor: lifted up to {lifted * 100:.1f} cm over '
                       'the eased settle')
        self.t = 0.0
        self.phase = 'down'
        loco.__dict__.setdefault('_seats', []).append({'chair': None, 't0': c.time, 'heading': c.scene_heading,
                                                       'facing': None, 'kind': 'ground'})
        loco._seat = {'kind': 'ground', 'cmd': self, 'fade': self.fade, 'clip': self.clip}
        _open_window(loco, 'ground', self)
        _log(loco, f"[sitOnGround] '{self.clip}' over {self.fade:.2f} s at ({self.root0.x:.2f}, {self.root0.y:.2f}): "
                   f'the lowest underside rested on the floor at {self.floor:.3f} m ({self.settle * 100:+.1f} cm)')

    def root(self, c, dz):
        c.seat_dz = dz
        self.cur_dz = dz

    def step(self, loco, dt):
        c = loco.ctrl
        if self.phase == 'approach':
            inp = self._run_subs(loco, dt)
            if inp is not None:
                return inp
            self._begin(loco)
        if self.phase == 'down':
            self.t += dt
            e = _smooth(self.t / max(self.fade, 1e-6))
            _drive_cross(c, self.stand, self.clip, e)
            self.root(c, float(np.interp(self.t, self.lz_t, self.lz_v)))
            if e >= 1.0:
                self.phase, self.t = 'seated', 0.0
            return (0.0, 0.0)
        if self.phase == 'seated':
            if self.hold is None:
                return None
            self.t += dt
            if self.t < self.hold:
                return (0.0, 0.0)
            self.stand = StandUp(**self.stand_opts)
            self.stand.start(loco)
            self.stand.started = True
            self.phase = 'standing'
        if self.phase == 'standing':
            return self.stand.step(loco, dt)
        return None


def _hips_at(cc, t, loop=True):
    """a clip's hips track (its offset from the root, armature axes) at clip time t"""
    if loop and cc.duration > 0:
        t = t % cc.duration
    t = min(max(t, 0.0), cc.duration)
    x = t / cc.dt
    k = min(int(x), cc.n - 1)
    u = x - k
    return Vector(cc.root_curve[k] * (1.0 - u) + cc.root_curve[k + 1] * u)


def _stand_pose_clip(c):
    """the idle as an emote, its hips' position stripped as the locomotion idle's is: the walk's own standing pose,
    held by the emote layer (a seat takes over from it and gives the body back through it)"""
    acts = c.__dict__.setdefault('_emote_actions', {})
    if STAND_POSE + '#stand' not in acts:
        a = c.load_emote(STAND_POSE, loop=True)
        if a is None:
            return None
        cc = a.clip
        cc.P[:] = 0.0
        cc.slot = STAND_POSE + '#stand'
        acts.pop(STAND_POSE, None)
        acts[STAND_POSE + '#stand'] = a
    return STAND_POSE + '#stand'


def _take_stand_pose(c):
    """the controller's seated state (beginSeated's: the root the seat's, held where it stands) entered on the standing
    pose (_hold_stand_pose). -> the stand pose's slot"""
    c._seated = True
    c._seat_root_z = c.pose.M.translation.z
    c.seat_dz = 0.0
    c._seated_release_in = None
    return _hold_stand_pose(c)


def _hold_stand_pose(c):
    """the emote layer takes the body on the standing pose, at full weight at once. The controller fades the walk's
    clips out in about a quarter second while an emote fades in, and the mixer fills the weights' shortfall with the
    rest pose (the T-pose: arms rising for a few frames, longer the longer the emote's fade); the same pose taken at
    once leaves no shortfall, and the emote crossfades from it with weights that sum to one. -> its slot"""
    slot = _stand_pose_clip(c)
    if slot is None:
        return None
    for k, a in getattr(c, '_emote_actions', {}).items():
        if k != slot and a is not None and a.enabled and a.get_effective_weight() > 0.01:
            a.fade_out(0.2)
    a = c._emote_actions[slot]
    a.reset()
    a.time_scale = 1.0
    a.play()
    a.set_effective_weight(1.0)
    c._active_emote = slot
    return slot


def _drive_cross(c, slot_from, slot_to, e):
    """two emotes crossfaded by hand: weights 1 - e and e (no scheduled fade), the second the active one"""
    acts = getattr(c, '_emote_actions', {})
    for slot, w in ((slot_from, 1.0 - e), (slot_to, e)):
        a = acts.get(slot)
        if a is not None:
            a.enabled = True
            a.set_effective_weight(w)
    c._active_emote = slot_to if e >= 0.5 else slot_from


def _start_clip(c, slot, loop):
    """an emote ready to crossfade in: loaded (once), from its start, playing at weight 0"""
    acts = c.__dict__.setdefault('_emote_actions', {})
    if slot not in acts:
        c.load_emote(slot, loop=loop)
    a = acts.get(slot)
    if a is None:
        return None
    a.reset()
    a.time_scale = 1.0
    a.play()
    a.set_effective_weight(0.0)
    return a


class StandUp(_Cmd):
    """endSeated for a seat made by seat_on / sit_on_ground (the module's doc)"""

    def __init__(self, reverse=None, clip='sit_to_stand', reverse_speed=1.25, fade=0.25, fade_out=0.5,
                 ground_fade=None):
        self.reverse, self.clip, self.reverse_speed, self.fade, self.fade_out = reverse, clip, reverse_speed, fade, \
            fade_out
        self.ground_fade = ground_fade

    def start(self, loco):
        c = loco.ctrl
        self._loco = loco
        st = getattr(loco, '_seat', None)
        self.st = st
        if not st or not getattr(c, '_seated', False):
            _log(loco, '[standUp] the body is not seated (seat_on / sit_on_ground first)')
            self.phase = 'done'
            return
        seat = st['cmd']
        self.seat = seat
        self.t = 0.0
        # once the controller has the root back, an emote it plays turns the body to _emote_facing_y (the engine's
        # default: three's rotation.y = pi): the stand-up keeps the seat's heading
        c._emote_facing_y = c.scene_heading
        self.stand = _stand_pose_clip(c)
        if st['kind'] == 'ground':
            # the ground clip crossfaded back to the standing pose by hand, eased, the settle eased out with it
            self.span = self.ground_fade or st.get('fade') or 1.0
            self.ground = st.get('clip')
            _start_clip(c, self.stand, loop=True)
            self.dz0 = seat.cur_dz
            self.phase = 'rise_ground'
            # out of the floor through the rise as through the sit-down (_ground_lift)
            acts = getattr(c, '_emote_actions', {})
            ga, sa = acts.get(self.ground), acts.get(self.stand)
            if ga is not None and sa is not None:
                M0 = c.pose.M.copy()
                M0.translation = seat.root0.copy()
                span = max(self.span, 1e-6)
                self.lz_t, self.lz_v, lifted = _ground_lift(
                    c, ga.clip, ga.time, sa.clip, 0.0, M0, seat.floor, self.span, lambda t: _smooth(t / span),
                    lambda t: self.dz0 * (1.0 - _smooth(t / span)),
                    long_sit_side='a' if getattr(seat, 'long_sit', False) else None)
                if lifted > 0.005:
                    _log(loco, f'[standUp] the rise from the ground held out of the floor: lifted up to '
                               f'{lifted * 100:.1f} cm over the eased settle')
            return
        rev = self.reverse if self.reverse is not None else not st.get('then')
        self.rev = rev
        self.dz0, self.k0, self.extra0 = seat.cur_dz, seat.cur_xy_k, seat.extra.copy()
        if rev and st.get('then'):
            # back to the sit-down's last pose first (the reverse plays the sit-down backwards), the root carried by
            # the difference of the two poses' hips (the loop's where it is now) so the hips stay on the seat
            lc = st['then_clip']
            la = getattr(c, '_emote_actions', {}).get(st['then'])
            off_loop = _hips_at(lc, la.time if la is not None else 0.0)
            d = seat.Mf.to_3x3() @ (off_loop - Vector(seat.cc.root_curve[-1]))
            self.back_shift = Vector((d.x, d.y))
            a = c.play_emote(seat.transition, fade_in=self.fade, fade_out=self.fade)
            if a is not None:
                a.time = a.clip.duration
            self.phase = 'back'
            return
        self._begin_up(loco)

    def _begin_up(self, loco):
        c = loco.ctrl
        seat = self.seat
        self.t = 0.0
        self.dz0, self.k0, self.extra0 = seat.cur_dz, seat.cur_xy_k, seat.extra.copy()
        if self.rev:
            a_tr = getattr(c, '_emote_actions', {}).get(seat.transition)
            rem = c.end_seated(None, reverse=True, reverse_speed=self.reverse_speed)
            self.span = rem or 0.0
            self.phase = 'up'
            if a_tr is not None and self.span > 0.0:
                t0, rs, span = a_tr.time, self.reverse_speed, self.span
                r0, dxy, k0, ex0 = seat.root0, seat.dxy, self.k0, self.extra0

                def xy_rev(t):
                    ks = _smooth(1.0 - min(1.0, t / max(UP_EASE * span, 1e-6)))
                    return (r0.x + dxy.x * k0 * ks + ex0.x * ks, r0.y + dxy.y * k0 * ks + ex0.y * ks)
                self.lz_t, self.lz_v = self._lift_curve(c, seat.cc, lambda t: max(0.0, t0 - t * rs), xy_rev,
                                                        lambda t: self.dz0, release=0.88)
            _log(loco, f'[standUp] the sit-down reversed at {self.reverse_speed:g}x ({self.span:.2f} s)')
            return
        # a stand-up clip, its hips' travel taken as root motion
        acts = getattr(c, '_emote_actions', {})
        if self.clip not in acts:
            c.load_emote(self.clip, loop=False)
        a = acts.get(self.clip)
        if a is None:
            _log(loco, f"[standUp] no '{self.clip}' clip: the sit-down reversed instead")
            self.rev = True
            return self._begin_up(loco)
        cc = a.clip
        if not hasattr(cc, '_travel'):
            cc._travel = cc.P[:, :2] - cc.P[0, :2]
            cc.P[:, :2] = cc.P[0, :2]
            cc.root_curve = cc.root_curve.copy()
        st = self.st
        if st.get('then'):
            la = acts.get(st['then'])
            off_cur = c.body.H['hips'] + _hips_at(st['then_clip'], la.time if la is not None else 0.0)
        else:
            off_cur = c.body.H['hips'] + Vector(seat.cc.root_curve[-1])
        off_s0 = c.body.H['hips'] + Vector(cc.root_curve[0])
        R = seat.Mf.to_3x3()
        d = R @ (off_cur - off_s0)
        self.cross = Vector((d.x, d.y))
        self.R = R
        self.cc = cc
        # the stand-up clip's own seat (its first pose's underside on the pan, where the crossfade puts its root): a
        # seated loop sitting higher or lower than it would otherwise drop or lift the hips through the crossfade
        Ms = seat.Mf.copy()
        rx = seat.root0.x + seat.dxy.x * self.k0 + self.extra0.x + self.cross.x
        ry = seat.root0.y + seat.dxy.y * self.k0 + self.extra0.y + self.cross.y
        Ms.translation = Vector((rx, ry, seat.root0.z))
        if seat.parts_up and seat.back_ok:
            # its first poses against the chair's back (the seated loop's hips are where it starts): forward as far
            # as they need, over the crossfade
            Mb = Ms.copy()
            res = 0.0
            for tb in np.linspace(0.0, 0.4 * cc.duration, 5):
                tr0 = np.array([np.interp(tb, np.linspace(0.0, cc.duration, len(cc._travel)), cc._travel[:, j])
                                for j in range(2)])
                trw0 = R @ Vector((tr0[0], tr0[1], 0.0))
                Mb.translation = Vector((rx + trw0.x, ry + trw0.y, seat.root0.z))
                res = max(res, seat._back_push(c, cc, Mb, seat.seat_here, times=[float(tb)]))
            if res > 0.002:
                self.cross = self.cross + Vector((seat.fwd.x, seat.fwd.y)) * res
                rx, ry = rx + seat.fwd.x * res, ry + seat.fwd.y * res
                Ms.translation = Vector((rx, ry, seat.root0.z))
                _log(loco, f"[standUp] '{self.clip}': its first poses against the chair's back: {res * 100:.1f} cm "
                           'forward')
        with _Posed(c.h, c.body) as posed:
            z = seat._underside(c, cc, 0.0, Ms, posed)
        self.settle_s0 = (seat.target_z - z) if z is not None else self.dz0
        self.span = cc.duration
        # what is left over at the end (the clip's stance against the standing spot) eases out over its last half
        trend = R @ Vector((cc._travel[-1][0], cc._travel[-1][1], 0.0))
        self.resid = self.extra0 + self.cross + Vector((trend.x, trend.y)) + seat.dxy * self.k0
        r0, dxy, k0 = seat.root0, seat.dxy, self.k0

        def xy_clip(t):
            b = self._clip_base(t)
            return (r0.x + dxy.x * k0 + b.x, r0.y + dxy.y * k0 + b.y)
        if st.get('then'):
            la = acts.get(st['then'])
            frm = (st['then_clip'], la.time if la is not None else 0.0, True)
        else:
            frm = (seat.cc, seat.cc.duration, False)
        if seat.parts_up and seat.back_ok:
            # the crossfade's frames against the back, blended as the mixer blends them: both poses are clear of it
            # (the seated loop measured over all of its length, the stand-up's first poses above), so this only
            # reports what a blend of the two still puts inside
            bc, bt0, bloop = frm
            fps = _fps()

            def M_at(t):
                Mt = seat.Mf.copy()
                x, y = xy_clip(t)
                Mt.translation = Vector((x, y, seat.root0.z))
                return Mt

            def blended(posed, t, Mt):
                posed.pose_blend(bc, bt0 + t, cc, t, t / max(self.fade, 1e-6), Mt, loop_a=bloop, loop_b=False)
            res = seat._back_push(c, cc, M_at, seat.seat_here, poser=blended,
                                  times=[k / fps for k in range(int(self.fade * fps) + 1)])
            if res > BACK_CLEAR + 0.002 and not getattr(self, '_scooted', False):
                # a blend of two poses that each clear the back can still lean into it (the fidget loop into
                # sit_to_stand: the tentacles' base 1.7 cm into it): she shifts forward on the seat first, as one does
                # before getting up, and the stand-up starts from there
                self._scooted = True
                self.scoot_from = seat.extra.copy()
                self.scoot = Vector((seat.fwd.x, seat.fwd.y)) * res
                self.phase, self.t = 'scoot', 0.0
                _log(loco, f"[standUp] '{self.clip}': its crossfade from the seated pose leans "
                           f'{(res - BACK_CLEAR) * 100:.1f} cm into the back of the chair: she shifts {res * 100:.1f} '
                           f'cm forward on the seat over {SCOOT_T:g} s first')
                return
            if res > BACK_CLEAR + 0.002:
                _log(loco, f"[standUp] '{self.clip}': its crossfade from the seated pose still leans "
                           f'{(res - BACK_CLEAR) * 100:.1f} cm into the back of the chair')
        # endSeated(slot) is playEmote(slot) plus a release of the root at 85 % of the clip; the root stays this
        # command's until the clip is done, and the crossfade is symmetric
        c.play_emote(self.clip, fade_in=self.fade, fade_out=self.fade)
        c._seated_release_in = None
        self.act = a
        self.phase = 'up_clip'
        self.lz_t, self.lz_v = self._lift_curve(
            c, cc, lambda t: min(t, cc.duration), xy_clip,
            lambda t: self.dz0 * (1.0 - min(1.0, t / max(self.fade, 1e-6))) +
            self.settle_s0 * min(1.0, t / max(self.fade, 1e-6)), release=0.9, blend_from=frm)
        _log(loco, f"[standUp] '{self.clip}' ({self.span:.2f} s), its hips' travel "
                   f'{float(np.hypot(*cc._travel[-1])) * 100:.1f} cm taken as root motion')

    def _clip_base(self, t):
        """a stand-up clip's shift of the seated root at stand-up time t: the crossfade's carry (the hips kept where the
        seated pose has them), the clip's hips travel as root motion, the residual eased out over its last half"""
        cc = self.cc
        w = min(1.0, t / max(self.fade, 1e-6))
        tc = min(t, cc.duration)
        kt = np.linspace(0.0, cc.duration, len(cc._travel))
        trw = self.R @ Vector((float(np.interp(tc, kt, cc._travel[:, 0])), float(np.interp(tc, kt, cc._travel[:, 1])),
                               0.0))
        u = min(1.0, t / max(self.span, 1e-6))
        return self.extra0 + self.cross * w + Vector((trw.x, trw.y)) - self.resid * _smooth((u - 0.5) / 0.5)

    def _lift_curve(self, c, cc, clip_t, xy_of, dz_base, release=0.9, blend_from=None):
        """the stand-up's lift (the seat's dz) frame by frame over its span: dz_base(t) (the seat's lift) let go as the
        clip's own hips rise from seated to standing (their progress), all of it by `release` of the span, and never
        under the clamp (_clampSeatedButt's: the seat skin over the pan kept on the pan, measured on the posed skin
        every frame while it is over the pan); smoothed, lift only -> (times, values). Let go over a fixed 60 % of
        the span whatever the clip did, a stand-up clip that leans forward before it rises sank the seated body up to
        12 cm through a 0.56 m seat, and the reversed sit-down 4 cm through a 0.45 m one"""
        seat = self.seat
        dt = 1.0 / _fps()
        nf = int(math.ceil(self.span / dt)) + 1
        tf = np.arange(nf + 1) * dt
        kt = np.arange(len(cc.root_curve)) * cc.dt
        hz = cc.root_curve[:, 2]
        z0 = float(np.interp(clip_t(0.0), kt, hz))
        rise = float(np.interp(clip_t(self.span), kt, hz)) - z0
        ease = np.zeros(len(tf))
        for i, t in enumerate(tf):
            u = min(1.0, t / max(self.span, 1e-6))
            p = (float(np.interp(clip_t(t), kt, hz)) - z0) / rise if abs(rise) > 0.05 else u
            # all of it gone by the time the hips are 60 % up (the clamp keeps the butt on the pan while it is
            # there): the feet, reaching for the floor from a high seat, come down as she rises, not after
            p = max(_smooth(min(1.0, max(0.0, p)) / 0.6), _smooth((u - (release - 0.2)) / 0.2))
            ease[i] = dz_base(t) * (1.0 - p)
        clamp = np.full(len(tf), -1e9)
        M = seat.Mf.copy()
        gone = 0
        with _Posed(c.h, c.body) as posed:
            for i, t in enumerate(tf):
                x, y = xy_of(t)
                M.translation = Vector((x, y, seat.root0.z))
                if blend_from is not None and t < self.fade:
                    # the crossfade from the seated pose (blend_from: (clip, its time now, loops)): measured as blended
                    bc, bt0, bloop = blend_from
                    posed.pose_blend(bc, bt0 + t, cc, clip_t(t), t / max(self.fade, 1e-6), M, loop_a=bloop,
                                     loop_b=False)
                    z = skin_lowest(c.h, seat.pan, seat.seat_here - UNDER_FROM, reach=2 * UNDER_FROM)
                else:
                    z = seat._underside(c, cc, clip_t(t), M, posed)
                if z is not None:
                    clamp[i] = seat.target_z - z
                gone = gone + 1 if (z is None or clamp[i] < -0.25) else 0
                if gone >= 4 and t > 0.5 * self.span:
                    break                                  # off the pan: nothing left to clamp
        dz = _smooth_lift(ease, clamp, first=float(max(ease[0], clamp[0])), last=0.0)
        lifted = float(np.max(clamp - ease))
        if lifted > 0.005:
            _log(getattr(self, '_loco', None), f'[standUp] the clamp holds the seated skin on the pan: up to '
                                              f'{lifted * 100:.1f} cm over the eased lift')
        return tf, dz

    def step(self, loco, dt):
        c = loco.ctrl
        seat = getattr(self, 'seat', None)
        if self.phase == 'done':
            return None
        self.t += dt
        if self.phase == 'rise_ground':
            e = _smooth(self.t / max(self.span, 1e-6))
            _drive_cross(c, self.ground, self.stand, e)
            seat.root(c, float(np.interp(self.t, self.lz_t, self.lz_v)) if hasattr(self, 'lz_t') else
                      self.dz0 * (1.0 - e))
            if e >= 1.0:
                c.end_seated(None)                   # the root back to the controller, standing where she sat
                c.seat_dz = 0.0
                self._release(loco)
            return (0.0, 0.0)
        if self.phase == 'to_stand':
            if self.t >= self.fade:
                self._release(loco)
            return (0.0, 0.0)
        if self.phase == 'back':
            w = min(1.0, self.t / max(self.fade, 1e-6))
            seat.extra = self.extra0 + self.back_shift * w
            seat.cur_kf = {s: seat.kf_then.get(s, seat.kf_tr[s]) * (1.0 - w) + seat.kf_tr[s] * w for s in seat.kf_tr}
            seat.root(c, self.k0, self.dz0 * (1.0 - w) + seat.settle * w, phase='back')
            if w < 1.0:
                return (0.0, 0.0)
            # the stand-up starts in this frame's mixer update: its first step is this frame's too
            self._begin_up(loco)
            self.t += dt
        if self.phase == 'up':
            k = 1.0 - min(1.0, self.t / max(UP_EASE * self.span, 1e-6))
            ks = k * k * (3.0 - 2.0 * k)
            if getattr(c, '_seated', False):
                seat.extra = self.extra0 * ks
                dz = float(np.interp(self.t, self.lz_t, self.lz_v)) if hasattr(self, 'lz_t') else self.dz0 * ks
                seat.root(c, self.k0 * ks, dz, phase='up')
            if self.t >= self.span:
                c.seat_dz = 0.0
                self._to_stand(loco)
            return (0.0, 0.0)
        if self.phase == 'scoot':
            e = _smooth(self.t / SCOOT_T)
            seat.extra = self.scoot_from + self.scoot * e
            seat.root(c, self.k0, seat.cur_dz, phase='seated')
            if e < 1.0:
                return (0.0, 0.0)
            self._begin_up(loco)                      # from where she now sits; its first step is this frame's
            self.t += dt
        if self.phase == 'up_clip':
            # the crossfade: the root carried by the hips' mismatch so the hips stay on the seat; then the clip's own
            # hips travel moves the root (the clip plays with its hips held over its first frame's)
            # (the clip time this frame's mixer update puts it at is self.t: it started at 0 on the first step)
            seat.extra = self._clip_base(self.t)
            seat.root(c, self.k0, float(np.interp(self.t, self.lz_t, self.lz_v)), phase='up')
            if self.t >= self.span:
                c._seated = False                    # the root back to the controller, where the clip stood her up
                c.seat_dz = 0.0
                self._to_stand(loco)
            return (0.0, 0.0)
        if self.phase == 'out':
            if self.t < self.fade_out + 0.1:
                return (0.0, 0.0)
            return None
        return None

    def _to_stand(self, loco):
        """the stand-up's last pose crossfaded into the standing pose (symmetric, no shortfall), then released"""
        c = loco.ctrl
        if self.stand is not None:
            c.play_emote(self.stand, fade_in=self.fade, fade_out=self.fade)
        self.phase, self.t = 'to_stand', 0.0

    def _release(self, loco):
        """stopEmote from the standing pose: the walk's idle damps back in under it (the same pose), the emote fading
        over fade_out (0.5 s: the idle's damping outpaces it, so the weights never fall short of one)"""
        loco.ctrl.stop_emote(fade_out=self.fade_out)
        self._finish(loco)
        self.phase, self.t = 'out', 0.0

    def _finish(self, loco):
        loco._seat = None
        _close_window(loco)


# ================================================================================================ my robot body
def robot_body_of(h):
    """the VRMRobotBody that drives this VRM (robot.body's registry: the engine's globalThis._vrmControllers), or None"""
    try:
        from ..robot.body import _VRM_CONTROLLERS
    except ImportError:
        return None
    arm = getattr(h, 'arm', h)
    return _VRM_CONTROLLERS.get(getattr(arm, 'name', None))


def seat_plan(h, chair, transition='stand_to_sit', face=None, camera=None, hip_back=None, sink=0.0, floor_z=None,
              fps=None):
    """seatOn's measures for a body that stands to sit into `chair` with `transition`, on the VRM handle h: the pan
    (find_seat_surface), the chair's facing (_detectChairFacing) and hers (face=, else the chair's, else the camera's),
    the hips' target (the backrest bias, then forward as far as the chair's back needs: back_push), where to stand for
    the clip's own hip travel to end the hips on it (or hip_back m in front, the engine's), the settle of its last
    pose onto the pan, and the descent's lift frame by frame (the settle eased in over its second half, never under the
    clamp from 40 % in) -> {'seat', 'facing', 'heading', 'target', 'spot', 'settle', 'lift_t', 'lift_v', 'push',
    'floor_z', 'transition', 'chair'}: what a body that no Locomotion drives needs to sit as the controller path sits
    (my robot body's bake rests its seat on the pan with it)"""
    from ...placement import seating as SE
    from ..controller import clips as C
    from ..controller.pose import root_matrix
    fps = fps or _fps()
    seat = SE.find_seat_surface(chair)
    facing = SE.chair_facing(chair, seat)
    if face is not None:
        th = face
    elif facing is not None:
        th = facing
    else:
        cam = camera or bpy.context.scene.camera
        p = cam.matrix_world.translation if cam is not None else None
        th = heading_of(p.x - seat['x'], p.y - seat['y']) if p is not None else 0.0
    fwd = _fwd(th)
    tx, ty = seat['x'], seat['y']
    if facing is not None and 'pan_dx' in seat:
        back = -_fwd(facing)
        depth = abs(back.x) * seat['pan_dx'] + abs(back.y) * seat['pan_dy']
        shift = min(0.12, depth * 0.18)
        tx, ty = tx + back.x * shift, ty + back.y * shift
    cc = C.load_emote_clip(h, transition, loop=False)
    if cc is None:
        raise ValueError(f"seat_plan: no '{transition}' clip in the library")
    off = Vector(h.rest_head[h.humanoid['hips']]) + Vector(cc.root_curve[-1])

    def spot_for(x, y):
        if hip_back is not None:
            return (seat['x'] + fwd.x * hip_back, seat['y'] + fwd.y * hip_back)
        d = Quaternion((0.0, 0.0, 1.0), th) @ Vector((off.x, off.y, 0.0))
        return (x - d.x, y - d.y)
    here = _surface_under([chair], tx, ty, seat['z'] + 0.5)
    seat_here = here if here is not None else seat['z']
    target_z = seat_here - sink
    pan = pan_points(chair, seat) or [(seat['x'], seat['y'])]
    if floor_z is None:
        from ...placement import _world as W
        mine = set([chair] + list(chair.children_recursive))
        others = [o for o in bpy.context.scene.objects if o.type == 'MESH' and W.visible(o) and o not in mine and
                  not any(m.type == 'ARMATURE' for m in o.modifiers)]
        sp = spot_for(tx, ty)
        hit = W.Rays(others).cast((sp[0], sp[1], seat['z'] + 1.0), (0, 0, -1), 50.0) if others else None
        floor_z = hit[0].z if hit else 0.0
    parts = _upper_parts(chair, seat_here)
    push = 0.0
    body = None
    if 'leftHipPitch' in h.arm.data.bones:                 # my robot body: its legs' hardware posed as its bake poses it
        from ..locomotion import Body
        body = Body(h)
    with _Posed(h, body) as posed:
        def settled_at(t, xy):
            M = root_matrix(xy[0], xy[1], floor_z, th)
            posed.pose(cc, t, M)
            zl = skin_lowest(h, pan, seat_here - UNDER_FROM, reach=2 * UNDER_FROM)
            return M, (target_z - zl) if zl is not None else None
        if parts and facing is not None and abs(_wrap_pi(th - facing)) < math.pi / 2:
            M, s0 = settled_at(cc.duration, spot_for(tx, ty))
            if s0 is not None:
                M.translation = Vector((M.translation.x, M.translation.y, floor_z + s0))
                posed.pose(cc, cc.duration, M)
                push = back_push(skin_points(h, loose=False), parts, seat_here, fwd, P_loose=_loose_points(h))
                tx, ty = tx + fwd.x * push, ty + fwd.y * push
        spot = spot_for(tx, ty)
        ts = np.linspace(CLAMP_FROM * cc.duration, cc.duration,
                         max(UNDER_SAMPLES, int(math.ceil((1.0 - CLAMP_FROM) * cc.duration * fps)) + 1))
        zl = [settled_at(float(t), spot)[1] for t in ts]
    settle = zl[-1] if zl and zl[-1] is not None else 0.0
    tf = np.arange(int(math.ceil(cc.duration * fps)) + 2) / fps
    ease = np.array([settle * _smooth((min(1.0, t / cc.duration) - SETTLE_FROM) / (1.0 - SETTLE_FROM)) for t in tf])
    vals = [(float(t), s) for t, s in zip(ts, zl) if s is not None]
    clamp = np.array([float(np.interp(min(t, cc.duration), [v[0] for v in vals], [v[1] for v in vals]))
                      if vals and t / cc.duration >= CLAMP_FROM else -1e9 for t in tf])
    lift = _smooth_lift(ease, clamp, first=0.0, last=settle)
    return {'seat': seat, 'facing': facing, 'heading': th, 'target': Vector((tx, ty)), 'spot': spot,
            'settle': settle, 'lift_t': tf, 'lift_v': lift, 'push': push, 'floor_z': floor_z,
            'transition': transition, 'chair': chair}


def _seat_robot_body(h, body, chair, transition, face, camera, hip_back, sink, fade):
    """seatOn's cohesive path for my robot body (robot_body.js: "seatOn(vrm, chair, {transition}) uses beginSeated
    under the hood"): the body put where the transition's hip travel ends the hips on the seat, facing out of the chair
    (the engine moves the VRM there and syncs its capsule), its controller's seated state begun, the plan kept on the
    body (body.seat_plan) for its bake to rest the seat on the pan"""
    plan = seat_plan(h, chair, transition=transition, face=face, camera=camera, hip_back=hip_back,
                     sink=0.0 if sink is None else sink)
    legs = body.controller.char_ctrl
    legs.pos.x, legs.pos.y = plan['spot']
    legs._heading = plan['heading']
    body.seat_plan = plan
    dur = body.begin_seated(transition, fadeIn=fade)
    from ...placement.seating import _mark_seated
    _mark_seated(h, chair)
    _log(None, f"[seatOn] '{chair.name}' through my robot body's seated state: standing at ({plan['spot'][0]:.3f}, "
               f"{plan['spot'][1]:.3f}) facing {math.degrees(plan['heading']):.1f} deg, the pan at "
               f"{plan['seat']['z']:.3f} m, settle {plan['settle'] * 100:+.1f} cm over the clip's {dur} s: its bake "
               "rests the seat on the pan with body.seat_plan (lift_t, lift_v)")
    return plan['seat']['z']


def _driven_warning(h, verb, instead):
    body = robot_body_of(h)
    if body is not None:
        _log(None, f"[{verb}] ⚠ a VRMRobotBody drives this VRM: the engine's {verb} is for a VRM nothing moves (its "
                   f"controller owns the body); {instead}")
    return body


# ================================================================================================ the verbs
def emote(target, slot, seconds=None, facing='keep', camera=None, offset=0.0, t=0.0, **kw):
    """emote: an expressive clip (talk, salute, cheer, fist, raise, reach, crazy, dance, any slot). A Locomotion: the
    controller's playEmote for `seconds` (default the clip once), facing 'keep' / 'camera' / degrees / None (fade_in,
    fade_out, loop as Locomotion.emote). A VRM handle: eidoblend.placement's stationary emote from t, looping"""
    if is_locomotion(target):
        target._queue.append(EmoteCmd(slot, seconds, facing=facing, camera=camera, offset=offset, **kw))
        return target
    _driven_warning(target, 'emote', 'play it through the body: body.perform_action(slot, seconds)')
    from ...placement import seating as SE
    return SE.emote(target, slot, t=t, **kw)


def face_camera(target, camera=None, offset=0.0, frame=None):
    """faceCamera: a Locomotion turns on the spot toward the camera (+offset rad); a VRM handle turns at once
    (eidoblend.placement's, keyed at frame= when given)"""
    if is_locomotion(target):
        target._queue.append(FaceCamera(camera, offset))
        return target
    _driven_warning(target, 'faceCamera', 'turn the body: body.face_direction(heading) or body.set_emote_facing')
    from ...placement import seating as SE
    return SE.face_camera(target, camera=camera, offset=offset, frame=frame)


def seat_on(target, chair, clip=None, face=None, sink=None, transition=None, fade=0.25, transition_dur=None,
            hip_back=None, camera=None, t=0.0, then=None, hold=None, gait='walk', speed=None, via=None, stand=None,
            then_fade=0.5, back_up=0.35, instant=False):
    """seatOn. A Locomotion: the controller path (the module's doc): transition (default 'stand_to_sit'), then= (or
    clip=) the seated loop after it, hold= seconds before standing up (None: stays seated until stand_up), stand= the
    stand-up's options, gait / speed / via= the walk to the chair, back_up= the last steps backward onto the spot (m;
    0: none); instant=True: the engine's instant path, no walk and no descent: the body put where the transition would
    have seated it, in the seated loop (then= or clip=, default 'sitting_normal_chair') at once, settled on the pan (a
    shot that opens seated; stand_up and walks follow as from any seat). A VRM my robot body drives (robot.body's
    registry), with a transition: the engine's cohesive path through its seated state (_seat_robot_body: placed at
    the measured spot, begin_seated, body.seat_plan for its bake). Any other VRM handle: eidoblend.placement's seat_on
    (the instant sit in `clip`, default 'sitting_normal_chair', or the transition from t). Returns the Locomotion, or
    the seat's height"""
    if is_locomotion(target):
        target._queue.append(SeatOn(chair, transition=transition or 'stand_to_sit', face=face,
                                    sink=0.0 if sink is None else sink, hip_back=hip_back, hold=hold, fade=fade,
                                    transition_dur=transition_dur, gait=gait, speed=speed, camera=camera,
                                    then=then or clip, then_fade=then_fade, via=via, stand=stand, back_up=back_up,
                                    instant=instant))
        return target
    body = robot_body_of(target)
    if body is not None:
        if transition:
            return _seat_robot_body(target, body, chair, transition, face, camera, hip_back, sink, fade)
        _driven_warning(target, 'seatOn', "pass transition='stand_to_sit': the cohesive path sits it through its "
                                          'seated state')
    from ...placement import seating as SE
    return SE.seat_on(target, chair, clip=clip or SEAT_CLIP, face=face, sink=sink, transition=transition, t=t,
                      fade=fade, transition_dur=transition_dur, hip_back=0.46 if hip_back is None else hip_back,
                      then=then, camera=camera)


def sit_on_ground(target, clip=GROUND_CLIP, at=None, face=None, sink=0.005, hip_height=0.08, camera=None, fade=1.0,
                  hold=None, gait='walk', speed=None, stand=None, ground=None, z=0.0, t=0.0):
    """sitOnGround. A Locomotion: the controller path (the module's doc). A VRM handle: eidoblend.placement's
    sit_on_ground (ground=, z=, t= are its)"""
    if is_locomotion(target):
        target._queue.append(SitOnGround(clip=clip, at=at, face=face, camera=camera, fade=fade, hold=hold, sink=sink,
                                         hip_height=hip_height, gait=gait, speed=speed, stand=stand))
        return target
    _driven_warning(target, 'sitOnGround', 'stop the body first; a seat for it goes through seat_on(transition=...)')
    from ...placement import seating as SE
    return SE.sit_on_ground(target, at=at, clip=clip, ground=ground, z=z, sink=sink, hip_height=hip_height, face=face,
                            t=t, camera=camera)


def stand_up(loco, reverse=None, clip='sit_to_stand', reverse_speed=1.25, fade=0.25, fade_out=0.5, ground_fade=None):
    """endSeated / VRMRobotBody.standUp for a body seat_on or sit_on_ground seated: reverse=None reverses the sit-down
    when it is the pose held, else plays `clip` (the seated loop's pair); a ground sit crossfades back up over its
    own fade (ground_fade=)"""
    loco._queue.append(StandUp(reverse=reverse, clip=clip, reverse_speed=reverse_speed, fade=fade, fade_out=fade_out,
                               ground_fade=ground_fade))
    return loco


def unseat(target):
    """unseat: the audits judge the body again (a Locomotion: from this point of the take; a VRM handle: now)"""
    if is_locomotion(target):
        target._queue.append(Unseat())
        return target
    from ...placement import seating as SE
    return SE.unseat(target)


# ================================================================================================ after the bake
def seated_spans(loco, rep):
    """the frames the body sat, as [(f0, f1), ...]: runs of the controller's seated frames, an unseat inside a run
    ending it there"""
    recs = rep['_records']
    runs, cur = [], None
    for r in recs:
        if r['mode'] in ('seated', 'seat'):
            if cur is not None and r['f'] - cur[1] <= 3:      # a long crossfade's first frame or two read as standing
                cur[1], cur[3] = r['f'], r['t']
            else:
                if cur is not None:
                    runs.append(cur)
                cur = [r['f'], r['f'], r['t'], r['t']]
    if cur is not None:
        runs.append(cur)
    cuts = sorted(getattr(loco, '_unseat_times', []))
    out = []
    for a, b, t0, t1 in runs:
        u = next((c for c in cuts if t0 - 1e-6 <= c <= t1 + 1e-6), None)
        if u is not None:
            b = next((r['f'] for r in recs if a <= r['f'] <= b and r['t'] >= u - 1e-6), b + 1) - 1
        if b >= a:
            out.append((a, b))
    return out


def key_seated(loco, rep, prop='eido_seated'):
    """after loco.bake(): the armature's `prop` keyed 1 over the seated frames and 0 elsewhere (CONSTANT), into the
    take's action; the engine's deferred facing check 1.5 s into each chair seat. -> {'spans', 'facing'}"""
    from bpy_extras import anim_utils
    arm = loco.h.arm
    recs = rep['_records']
    if not recs:
        return {'spans': [], 'facing': []}
    spans = seated_spans(loco, rep)
    arm[prop] = 0
    keys = [(recs[0]['f'], 0)]
    for a, b in spans:
        keys += [(a, 1), (b + 1, 0)]
    for f, v in keys:
        arm[prop] = v
        arm.keyframe_insert(f'["{prop}"]', frame=f)
    ad = arm.animation_data
    if ad is not None and ad.action is not None:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in (cb.fcurves if cb else []):
            if fc.data_path == f'["{prop}"]':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    out = []
    for s in getattr(loco, '_seats', []):
        if s['facing'] is None:
            continue
        t_check = s['t0'] + 1.5
        r = min(recs, key=lambda q: abs(q['t'] - t_check))
        if r['mode'] not in ('seated', 'seat'):
            continue
        d = r['heading'] - s['facing']
        deg = abs(math.degrees(math.atan2(math.sin(d), math.cos(d))))
        out.append({'chair': s['chair'], 'frame': r['f'], 'deg': round(deg, 1)})
        if deg > 110:
            _log(loco, f"[seatOn] ⚠ RE-RENDER REQUIRED: the sitter faces the BACKREST of '{s['chair']}' ({deg:.0f} deg "
                       'off its natural facing): pass face= to seat_on')
        elif deg > 55:
            _log(loco, f"[seatOn] the sitter is {deg:.0f} deg off '{s['chair']}''s natural facing: verify; pass face= "
                       'if deliberate')
    _log(loco, f'[key_seated] {prop} keyed over {spans}')
    return {'spans': spans, 'facing': out}


HANDOVER = 12               # frames over which the feet and the pelvis pass between the plant and a seat


def _seat_handover(loco, rep):
    """where a seat's frames meet the plant's (its first frame after a planted stance, its last before one): over
    HANDOVER frames inside the seat, each foot moves between where the plant planted it and where the seat puts it (a
    step, lifted, when that is over 3 cm: a sitter shuffles her feet into place) and the pelvis between the plant's
    height and the seat's; the legs solved to it (the plant drops a stance's hold at once where its feet are handed
    over, a jump of up to the stance's whole correction). The frames' measures are taken again where they changed"""
    from ..controller.pose import Pose
    body = loco.ctrl.body
    frames, recs = rep['_frames'], rep['_records']
    n = len(frames)
    seat = [fr.get('mode') == 'seat' for fr in frames]
    runs, a = [], None
    for i, s_ in enumerate(seat + [False]):
        if s_ and a is None:
            a = i
        elif not s_ and a is not None:
            runs.append((a, i - 1))
            a = None
    touched = {}

    def goes(js, anchor):
        # how far each foot goes over the hand-over (the farthest of its frames from the plant's foot): one decision per
        # hand-over, step or slide (decided per frame, a foot near 3 cm lifted on one frame and not the next: a pop)
        q = Pose(body, frames[anchor]['M'], dict(frames[anchor]['N']), frames[anchor]['off'])
        out = {}
        for s in ('left', 'right'):
            nm = s + 'Foot'
            if nm in body.h.humanoid:
                hold = q.world_pos(nm)
                out[s] = max((Pose(body, frames[j]['M'], dict(frames[j]['N']), frames[j]['off']).world_pos(nm)
                              - hold).xy.length for j in js)
        return out

    def blend(j, anchor, v, go_run):
        fr, fa = frames[j], frames[anchor]
        if j not in touched:                                # the feet as the plant measured them, to carry its points
            q0 = Pose(body, fr['M'].copy(), dict(fr['N']), fr['off'])
            touched[j] = {s: (q0.world_pos(s + 'Foot').copy(), q0.world_quat(s + 'Foot').copy())
                          for s in ('left', 'right') if s + 'Foot' in body.h.humanoid}
        dz_a = fa['M'].translation.z - recs[anchor]['M'].translation.z      # the plant's pelvis offset there
        M = fr['M'].copy()
        t = M.translation.copy()
        t.z += dz_a * (1.0 - v)
        M.translation = t
        p = Pose(body, M, dict(fr['N']), fr['off'])
        q = Pose(body, fa['M'], dict(fa['N']), fa['off'])
        for s in ('left', 'right'):
            nm = s + 'Foot'
            if nm not in body.h.humanoid:
                continue
            an_free, an_hold = p.world_pos(nm).copy(), q.world_pos(nm).copy()
            go = go_run[s]
            e = _smooth(v)
            tgt = an_hold.lerp(an_free, e)
            if go > STEP_MIN:
                # a step: it lifts, goes, and comes straight down onto its place (over its last 15 %)
                ex = _smooth(min(1.0, v / 0.85))
                tgt.x, tgt.y = an_hold.x + (an_free.x - an_hold.x) * ex, an_hold.y + (an_free.y - an_hold.y) * ex
                tgt.z += max(STEP_LIFT[2], min(STEP_LIFT[1], STEP_LIFT[0] * go)) * math.sin(math.pi * v)
            w_q = q.world_quat(nm).slerp(p.world_quat(nm), e)
            _leg_reach(p, s, tgt)
            p.set_world_quat(nm, w_q)
        fr['M'], fr['N'] = M, dict(p.N)

    for a, b in runs:
        # v reaches 1 on the hand-over's last frame: the next frame is the seat's (or the plant's) own. Where the take
        # cuts into the seat (an instant seat put the body there) nothing is handed over
        if a > 0 and not seat[a - 1] and not recs[a].get('cut'):
            js = range(a, min(b + 1, a + HANDOVER))
            g = goes(js, a - 1)
            for k, j in enumerate(js):
                blend(j, a - 1, (k + 1) / HANDOVER, g)
        if b < n - 1 and not seat[b + 1]:
            js = range(b, max(a - 1, b - HANDOVER), -1)
            g = goes(js, b + 1)
            for k, j in enumerate(js):
                blend(j, b + 1, k / HANDOVER, g)
    for j, old in touched.items():
        # the plant's measured sole points carried with their foot (its point set is the plant's own)
        fr = frames[j]
        q1 = Pose(body, fr['M'], dict(fr['N']), fr['off'])
        for s, (p0, w0) in old.items():
            p1, w1 = q1.world_pos(s + 'Foot'), q1.world_quat(s + 'Foot')
            Rm = np.array((w1 @ w0.inverted()).to_matrix())
            m = fr['meas'][s]
            m['P'] = (m['P'] - np.array(p0)) @ Rm.T + np.array(p1)
            m['ankle'] = p1.copy()
    return len(touched)


def bake(loco, f0=1, key=True, action_name=None, springs=True, **kw):
    """Locomotion.bake(f0, **kw) with the seats' frames handed over between the run and the plant (_seat_records: the
    seat's feet, the plant leaving them and the seated root) and back after it (_seat_handover: the feet and pelvis
    passed between the plant's and the seat's), keyed as Locomotion.bake keys; the frames the verbs see (a camera's
    place when a command starts); then key_seated, and the spring chains over the keyed take (Locomotion.bake_springs;
    springs=False leaves them out, a dict passes bake_springs' options) -> the report, with 'seated' ({'spans',
    'facing'}), 'seat_frames', 'handover_frames' and 'springs'"""
    import time
    import types
    from ..locomotion import key_frames
    loco.f0 = f0
    base = type(loco).simulate
    handed = []

    def simulate(self, *a, **k):
        recs = base(self, *a, **k)
        handed.append(_seat_records(self, recs))
        return recs
    loco.simulate = types.MethodType(simulate, loco)
    try:
        rep = loco.bake(f0=f0, key=False, **kw)
    finally:
        del loco.simulate
    rep['seat_frames'] = sum(handed)
    rep['handover_frames'] = _seat_handover(loco, rep) if kw.get('feet', 'plant') == 'plant' else 0
    if key:
        rep['action'] = key_frames(loco.h, loco.ctrl.body, rep['_frames'], action_name or f'{loco.h.name}|controller')
        rep['seated'] = key_seated(loco, rep)
        if springs:
            t0 = time.time()
            rep['springs'] = loco.bake_springs(rep, **(springs if isinstance(springs, dict) else {}))
            rep.setdefault('timing_s', {})['springs'] = round(time.time() - t0, 2)
    return rep
