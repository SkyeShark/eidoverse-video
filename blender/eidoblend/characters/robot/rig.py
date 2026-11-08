"""eidoblend.characters.robot.rig: my robot body's runtime on one VRM, the example's whole frame order, keyed.

    from eidoblend.characters import load_vrm, load_clip, Ground
    from eidoblend.characters.robot import RobotRig, perform_robot
    me = load_vrm('claude_robot')
    rig = RobotRig(me)                                   # the DOF records, once, at load (before anything poses the body)
    rep = perform_robot(me, load_clip(me, 'idle'), 1, 240, rig=rig, ground=Ground(fn=lambda x, y: 0 * x),
                        face=lambda t: {'happy': 1.0}, look=lambda t: 0.0)

RobotRig is what eidoverse/examples/claude_robot.js sets up at load: initArmDOF(vrm, joints.hinges) (the elbow's pin, the
shoulder's pitch stages, the wrist's roll and flex stages), initHandDOF (the fingers' pins, the thumb's rotor), initLegDOF
(the hips' pitch and roll stages), initCrown, plus the legs' clearance memo and the head's actuators. Every stage the
solves set and no humanoid bone carries has its VRM node constraint (the add-on's COPY_ROTATION / DAMPED_TRACK) muted
and is keyed instead, as the JS deletes those constraints and sets the stages itself.

rig.frame(...) runs the example's renderFrame on one sampled pose, in its order:

    the clip from the rest pose (restoreArmPose, the clip, keepArmPose)        rig.clip_pose(clip, tc)
    rehomeBody -> applyHardwareDOF(LEG_JOINTS) -> applyLegClearance(dt) -> applyArmDOF(dt) -> applyHandDOF
    [a gaze override: VRMRobotBody's head look, split onto the neck's pan and the head's nod as my stages stack]
    the face's expressions -> applyHeadExpression(dt) -> applyCrown(dt)
    the body set down onto the ground (setDownOnFloor: the lowest foot vertex on it)

and returns one frame record (Blender's axes): N (every humanoid bone's normalized rotation), off (the hips' offset), M
(the armature's world matrix), stages (the hips' pitch / swing), helpers (the shoulders' pitch, rad), wrists (the roll and
flex stages), rotors (the thumbs' rotor stages), petals (the twelve folds, deg). key_robot keys a list of them into ONE
action on the armature (LINEAR, every frame: any frame renders alone), and perform_robot is the example's loop over a
clip. post_pass is the same order for a pose another solver made (round one's walk_path): the arms and hands clamped
where that solver did not, the gaze, the head and the crown.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from .. import robot_dof as dof
from .._math import D2R, R2D, clamp, euler_from_quat, q_from_three, q_to_three, quat_from_euler, v_to_three
from ..ground import SIDES
from ..locomotion import Body
from ..performance import LOOK_RANGE, VISEMES, key_face_track
from ..vrm import joints_record

STAGE_BONES = ('HipPitch', 'HipSwing', 'ShoulderPitch', 'WristRoll', 'WristFlex', 'ThumbRotor')


def look_weights(yaw_deg, pitch_deg=0.0):
    """vrm.lookAt (expression type, as my face is) -> its look expressions: the yaw over the face's horizontal range"""
    w = {'lookLeft': min(1.0, max(0.0, yaw_deg) / LOOK_RANGE['horizontal']),
         'lookRight': min(1.0, max(0.0, -yaw_deg) / LOOK_RANGE['horizontal'])}
    if pitch_deg:
        w['lookUp'] = min(1.0, max(0.0, pitch_deg) / LOOK_RANGE['up'])
        w['lookDown'] = min(1.0, max(0.0, -pitch_deg) / LOOK_RANGE['down'])
    return w


def mouth_capped(w):
    """the five vowel presets kept summing to at most 1 (two shapes past it show the teeth and the tongue together)"""
    vs = [w.get(v, 0.0) for v in VISEMES]
    s = sum(vs)
    if s > 1:
        for v in VISEMES:
            if v in w:
                w[v] /= s
    return w


class RobotRig:
    """my body's runtime state, one per VRM, made at load (claude_robot.js setup): arms (robot_dof.ArmDOF), hands
    (HandDOF), legs (LegStages), clear (LegClearance), head (HeadState), crown (Crown), body (round one's FK: the set-down)
    and stats (the largest correction per joint, deg: a big entry means the clip asks for a pose my body cannot take)."""

    def __init__(self, h, hinges=None, clearance=True, body=None):
        self.h = h
        rec = joints_record(h)
        self.hinges = hinges if hinges is not None else (rec or {}).get('hinges')
        if not self.hinges:
            print('[robot] no joints file beside the VRM: the elbow keeps ARM\'s constants and the hands go unclamped',
                  flush=True)
        self.arms = dof.init_arm_dof(h, self.hinges, mute=True, wrist=True, mute_wrist=True)
        self.hands = dof.init_hand_dof(h, self.hinges) if self.hinges else None
        self.legs = dof.init_leg_dof(h)
        self.clear = dof.LegClearance(h) if clearance else None
        self.head = dof.init_head_expression()
        self.crown = dof.init_crown(h)
        self.body = body or Body(h, use_dof=False)
        self.stats = {}
        self.hips_bone = h.humanoid['hips']

    # ------------------------------------------------------------------------------------------------------ the clip
    def clip_pose(self, clip, tc):
        """the clip's normalized pose at clip time tc from the rest pose, three's frame, with the arm pass's guard
        (restoreArmPose before, keepArmPose after) -> (pose3, the hips' offset in armature space)"""
        h = self.h
        p3 = {n: Quaternion() for n in h.humanoid}
        dof.restore_arm_pose(self.arms, p3)
        rot, loc = clip.sample(tc)
        for n, b in h.humanoid.items():
            q = rot.get(b)
            if q is not None:
                p3[n] = q_to_three(h.normalized_from_basis(b, q))
        off = h.hips_location_offset(loc.get(self.hips_bone, Vector()))
        dof.keep_arm_pose(self.arms, p3)
        return p3, off

    def reset(self):
        """a cut: the wrists' turn limit and the legs' clearance start fresh (resetArmDOF; the clearance memo)"""
        dof.reset_arm_dof(self.arms)
        if self.clear is not None:
            self.clear.reset()

    # ------------------------------------------------------------------------------------------------------ one frame
    def frame(self, p3, off, dt, weights=None, gaze=None, crown_state=None, head_state=None, state_weight=1.0,
              clearance=True, legs=True):
        """the example's hardware pass, gaze, head and crown on one sampled pose (p3 three's frame, changed in place)
        -> the frame record without M (the caller places the body: place())"""
        h, st = self.h, self.stats
        hips3 = v_to_three(h.rest_head[self.hips_bone] + off)
        dof.rehome_body(p3, st)
        if legs:
            dof.apply_hardware_dof(p3, dof.LEG_JOINTS, self.legs, st)
            if clearance and self.clear is not None:
                dof.apply_leg_clearance(self.clear, p3, hips3, st, dt, None, self.legs)
        dof.apply_arm_dof(self.arms, p3, dt, 8.0, st)
        if self.hands is not None:
            dof.apply_hand_dof(self.hands, p3, st)
        return self._finish(p3, off, dt, weights, gaze, crown_state, head_state, state_weight)

    def stand_raw(self, clip, tc, dt, clearance=True):
        """the frame order's stateless head end on a clip pose, split off for passes that blend two sources before the
        stateful rest runs once (bake): the clip, rehomeBody, applyHardwareDOF (+ the hip stages), applyLegClearance and
        applyArmDOF's own first step, the arms' turn-out (applyArmClearance, 8 deg). finish() is the rest. Together they
        are frame() exactly (applyArmDOF(clearance) is applyArmClearance(clearance) then the solve with none)
        -> {'N' (Blender's axes), 'off', 'stages'}"""
        h, st = self.h, self.stats
        p3, off = self.clip_pose(clip, tc)
        hips3 = v_to_three(h.rest_head[self.hips_bone] + off)
        dof.rehome_body(p3, st)
        dof.apply_hardware_dof(p3, dof.LEG_JOINTS, self.legs, st)
        if clearance and self.clear is not None:
            dof.apply_leg_clearance(self.clear, p3, hips3, st, dt, None, self.legs)
        stages = {s: {k: q_from_three(v) for k, v in o.items()} for s, o in self.legs.out.items() if o}
        dof.apply_arm_clearance(p3, 8.0)
        return {'N': {n: q_from_three(q) for n, q in p3.items()}, 'off': off.copy(), 'stages': stages}

    def finish(self, raw, dt, weights=None, gaze=None, crown_state=None, head_state=None, state_weight=1.0):
        """the frame order's stateful rest, once per film frame: applyArmDOF (no turn-out: stand_raw or the walk did it),
        applyHandDOF, the gaze, applyHeadExpression, applyCrown -> the frame record (its stages: raw['stages'])"""
        return self.post_pass(raw['N'], raw['off'], dt, weights, gaze, crown_state, head_state, state_weight,
                              legs_out=raw.get('stages'))

    def post_pass(self, N, off, dt, weights=None, gaze=None, crown_state=None, head_state=None, state_weight=1.0,
                  legs_out=None, arms=True):
        """the frame order's remainder on a pose another solver made and clamped its own way (N Blender's axes: round
        one's walk_path, which clamps the legs and the arms but not the hands, and keys no wrist or thumb stage): the arms
        re-solved without the turn-out (the pass is a projection there, so the walk's arms stay; it gives the wrist
        stages), the hands, the gaze, the head and the crown. legs_out: the solver's own hip stages (Blender's axes)"""
        p3 = {n: q_to_three(q) for n, q in N.items()}
        if arms:
            dof.apply_arm_dof(self.arms, p3, dt, 0.0, self.stats)
        if self.hands is not None:
            dof.apply_hand_dof(self.hands, p3, self.stats)
        rec = self._finish(p3, off, dt, weights, gaze, crown_state, head_state, state_weight)
        if legs_out is not None:
            rec['stages'] = legs_out
        return rec

    def _finish(self, p3, off, dt, weights, gaze, crown_state, head_state, state_weight):
        w = mouth_capped(dict(weights or {}))
        if gaze is not None:
            self.apply_gaze(p3, gaze[0], gaze[1])
        self.head.apply(p3, w, dt, state=head_state, weight=state_weight)
        look = w.get('lookLeft', 0.0) - w.get('lookRight', 0.0)
        petals = self.crown.apply(w, dof.head_roll_deg(p3), dt, look=look, state=crown_state, weight=state_weight)
        stages = {}
        for side in SIDES:
            o = self.legs.out.get(side) if self.legs is not None else None
            if o:
                stages[side] = {k: q_from_three(v) for k, v in o.items()}
        return {'N': {n: q_from_three(q) for n, q in p3.items()}, 'off': off.copy(), 'stages': stages,
                'helpers': dict(self.arms.helper_phi),
                'wrists': {s: {k: q_from_three(v) for k, v in o.items()} for s, o in self.arms.wrist_out.items()},
                'rotors': {s: q_from_three(q) for s, q in (self.hands.rotor_out.items() if self.hands else ())},
                'petals': list(petals), 'weights': w}

    @staticmethod
    def apply_gaze(p3, yaw, pitch):
        """VRMRobotBody._applyHeadOverride: the head's local turn REPLACED by Euler(pitch, yaw, 0, 'YXZ') (the animation's
        head bobble given up for a steady gaze; yaw + toward the body's left, pitch + looking DOWN, as robot_body.js).
        On my body the neck carries the pan and the head the nod, so the turn is split as the stages stack (rehomeBody's
        split) and clamped at their stops: pan +-60, nod +-30 (the body's own yawLimit / pitchLimit)"""
        q = quat_from_euler(pitch, yaw, 0.0, 'YXZ')
        if 'neck' in p3:
            x, y, z = euler_from_quat(q, 'YXZ')
            pan = clamp(y * R2D, *dof.HEAD_RANGE['pan']) * D2R
            nod = clamp(x * R2D, *dof.HEAD_RANGE['x']) * D2R
            roll = clamp(z * R2D, *dof.HEAD_RANGE['z']) * D2R
            p3['neck'] = Quaternion((0.0, 1.0, 0.0), pan)
            p3['head'] = quat_from_euler(nod, 0.0, roll, 'XZY')
        else:
            p3['head'] = q

    # ------------------------------------------------------------------------------------------------------ placing
    def place(self, rec, M, ground=None):
        """the body at M (a world matrix), set down so the lowest point of either foot touches the ground under it
        (setDownOnFloor / groundVRM: vertically) -> rec with 'M' and 'set_down_m' (the drop, m: + the clip floated)"""
        rec['M'] = M
        rec['set_down_m'] = None
        if ground is not None:
            low = self.lowest(rec, M, ground)
            rec['M'] = Matrix.Translation(Vector((0.0, 0.0, -low))) @ M
            rec['set_down_m'] = low
        return rec

    def rest_feet(self, rec, ground, reach=0.025):
        """a placed standing record's feet brought down onto the ground where they hover within `reach` (m): each such
        foot's ankle lowered by its gap, its turn kept, the leg re-solved (two-bone IK) and clamped as the hardware is,
        the hips' stages solved; a leg too straight to lower its ankle tips its foot toes-down instead. The stock idle on
        my legs holds its unloaded right foot 9-11 mm off the floor with that leg straight (the WebGPU example shows the
        same: its set-down only puts the LOWER foot on the floor); a film's standing body rests both feet.
        In place -> {side: the gap closed, m}"""
        if ground is None or rec.get('M') is None:
            return {}
        b, N = self.body, rec['N']
        ph, Wh = b.hips(rec['M'], rec['off'], N)

        def gaps():
            out = {}
            for s in SIDES:
                fk = b.leg_fk(s, ph, Wh, N)
                P = b.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
                out[s] = float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1])))
            return out
        g_in = gaps()
        closed = {}
        for _round in range(4):                      # the hardware clamp after the IK can tip the sole: settle again
            moved = False
            for s in SIDES:
                fk = b.leg_fk(s, ph, Wh, N)
                P = b.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
                gap = float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1])))
                if (3e-4 if _round else 1e-5) < gap < reach:
                    b.solve_leg(s, ph, Wh, N, fk['p_an'] - Vector((0.0, 0.0, gap)), fk['W_ft'], swivel=1.0)
                    closed[s] = 0.0
                    moved = True
            if not moved:
                break
            self._clamp_legs(rec)
        # a leg already straight cannot lower its ankle: that foot tips toes-down about its ankle's pitch pin until its
        # ball rests on the floor (a free leg's relaxed foot, as a person stands on one leg)
        tipped = False
        for s in SIDES:
            fk = b.leg_fk(s, ph, Wh, N)

            def gap_at(th, fk=fk, s=s):
                R = Quaternion((fk['W_ft'] @ Vector((1.0, 0.0, 0.0))).normalized(), th)
                P = b.sole(s, fk['p_an'], R @ fk['W_ft'], R @ fk['W_to'])
                return float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1])))
            g0 = gap_at(0.0)
            if not 3e-4 < g0 < reach:
                continue
            sgn = 1.0 if gap_at(0.01) < gap_at(-0.01) else -1.0
            lo_, hi_ = 0.0, 20.0 * D2R
            if gap_at(sgn * hi_) > 0:
                continue
            for _ in range(30):
                mid = 0.5 * (lo_ + hi_)
                if gap_at(sgn * mid) > 0:
                    lo_ = mid
                else:
                    hi_ = mid
            R = Quaternion((fk['W_ft'] @ Vector((1.0, 0.0, 0.0))).normalized(), sgn * hi_)
            N[s + 'Foot'] = fk['W_sh'].inverted() @ (R @ fk['W_ft'])
            closed[s] = 0.0
            tipped = True
        if tipped:
            self._clamp_legs(rec)
        g_out = gaps() if closed else g_in
        return {s: g_in[s] - g_out[s] for s in closed}

    def _clamp_legs(self, rec):
        """the legs of a record clamped as the hardware is, the hips' stages solved (rec['stages'])"""
        N = rec['N']
        p3 = {n: q_to_three(q) for n, q in N.items()}
        dof.apply_hardware_dof(p3, dof.LEG_JOINTS, self.legs)
        for n in (n for s in SIDES for n in (s + 'UpperLeg', s + 'LowerLeg', s + 'Foot', s + 'Toes')):
            if n in p3:
                N[n] = q_from_three(p3[n])
        rec['stages'] = {s: {k: q_from_three(v) for k, v in o.items()} for s, o in self.legs.out.items() if o}

    def lowest(self, rec, M, ground):
        """the lowest foot point's height over the ground under it, for the body at M"""
        b, N = self.body, rec['N']
        ph, Wh = b.hips(M, rec['off'], N)
        low = math.inf
        for s in SIDES:
            fk = b.leg_fk(s, ph, Wh, N)
            P = b.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            low = min(low, float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1]))))
        return low

    def feet_world(self, rec):
        """each foot's sole points in the world for a placed record: {side: (n, 3)}"""
        b, N = self.body, rec['N']
        ph, Wh = b.hips(rec['M'], rec['off'], N)
        out = {}
        for s in SIDES:
            fk = b.leg_fk(s, ph, Wh, N)
            out[s] = b.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
        return out

    def bone_world(self, rec, name):
        """a humanoid bone's world head and normalized world turn for a placed record (FK down the humanoid chain)"""
        h, N = self.h, rec['N']
        chain = []
        n = name
        parents = _parents(h)
        while n is not None:
            chain.append(n)
            n = parents.get(n)
        chain.reverse()
        M = rec['M']
        Qr = M.to_quaternion()
        H = self.body.H
        p = M @ (H['hips'] + rec['off'])
        W = Qr @ N['hips']
        for a, b_ in zip(chain[:-1], chain[1:]):
            p = p + W @ (H[b_] - H[a])
            W = W @ N[b_]
        return p, W


_PARENTS = {}


def _parents(h):
    k = h.arm.name
    if k not in _PARENTS:
        by_bone = {b: n for n, b in h.humanoid.items()}
        out = {}
        for n, b in h.humanoid.items():
            p = h.arm.data.bones[b].parent
            while p is not None and p.name not in by_bone:
                p = p.parent
            out[n] = by_bone[p.name] if p is not None else None
        _PARENTS[k] = out
    return _PARENTS[k]


# ---------------------------------------------------------------------------------------------------------- the keyer
def key_robot(h, frames, name, object_transform=True):
    """one action on the armature (LINEAR, every frame): the object's place (M), every humanoid bone (N), the hips'
    offset, the hips' pitch and swing stages, the shoulders' pitch helpers, the wrists' roll and flex stages, the thumbs'
    rotors and the twelve petals. Frames: dicts with 'f' and a rig record's fields -> {name, fcurves, frames}"""
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

    def put_q(bn, f, q):
        if bn in arm.pose.bones:
            bq = h.basis_from_normalized(bn, q)
            for i in range(4):
                put(f'pose.bones["{bn}"].rotation_quaternion', i, f, bq[i], bn)
    hb = h.humanoid['hips']
    prev = {}
    for fr in frames:
        f = fr['f']
        if object_transform and fr.get('M') is not None:
            loc, rot, _sc = fr['M'].decompose()
            if 'rot' in prev and prev['rot'].dot(rot) < 0:
                rot.negate()                                   # the shortest way round between keys
            prev['rot'] = rot
            for i in range(3):
                put('location', i, f, loc[i], 'Object Transforms')
            for i in range(4):
                put('rotation_quaternion', i, f, rot[i], 'Object Transforms')
        for n, q in fr['N'].items():
            b = h.humanoid.get(n)
            if b is None:
                continue
            bq = h.basis_from_normalized(b, q)
            pq = prev.get(b)
            if pq is not None and pq.dot(bq) < 0:
                bq.negate()
            prev[b] = bq
            for i in range(4):
                put(f'pose.bones["{b}"].rotation_quaternion', i, f, bq[i], b)
        lb = h.rest_q[hb].inverted() @ fr['off']
        for i in range(3):
            put(f'pose.bones["{hb}"].location', i, f, lb[i], hb)
        for side, st in (fr.get('stages') or {}).items():
            for k, bn in (('pitch', side + 'HipPitch'), ('swing', side + 'HipSwing')):
                if k in st:
                    put_q(bn, f, st[k])
        for side, phi in (fr.get('helpers') or {}).items():
            put_q(side + 'ShoulderPitch', f, Quaternion((1.0, 0.0, 0.0), phi))
        for side, st in (fr.get('wrists') or {}).items():
            put_q(side + 'WristRoll', f, st['roll'])
            put_q(side + 'WristFlex', f, st['flex'])
        for side, q in (fr.get('rotors') or {}).items():
            put_q(side + 'ThumbRotor', f, q)
        if fr.get('petals') is not None:
            for i_, phi in enumerate(fr['petals']):
                bn = f'petal_{i_:02d}'
                if bn in arm.pose.bones:
                    bq = Quaternion((1.0, 0.0, 0.0), (phi - dof.PETAL_REST) * D2R)
                    for i in range(4):
                        put(f'pose.bones["{bn}"].rotation_quaternion', i, f, bq[i], bn)
    for (path, idx, group), kv in series.items():
        fc = cb.fcurves.new(path, index=idx, group_name=group)
        fc.keyframe_points.add(len(kv))
        fc.keyframe_points.foreach_set('co', [c for f, v in kv for c in (f, v)])
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()
    for p in arm.pose.bones:
        p.rotation_mode = 'QUATERNION'
    return {'name': act.name, 'fcurves': len(series), 'frames': len(frames)}


def face_track(frames):
    """the frames' expression weights as key_face_track's {expression: [(frame, weight)]} (an expression first named
    late starts from 0 on the first frame)"""
    track, f0 = {}, frames[0]['f'] if frames else 0
    for fr in frames:
        for k, v in (fr.get('weights') or {}).items():
            if k not in track and fr['f'] > f0:
                track[k] = [(f0, 0.0)]
            track.setdefault(k, []).append((fr['f'], v))
    return track


def stage_constraints(h):
    """the stage bones' VRM node constraints and whether each is muted: {bone: [(type, muted)]} (a check: every stage
    the solve keys must have its constraint muted, or the constraint overwrites the key at evaluation)"""
    out = {}
    for side in SIDES:
        for k in STAGE_BONES:
            bn = side + k
            pb = h.arm.pose.bones.get(bn)
            if pb is not None:
                out[bn] = [(c.type, c.mute) for c in pb.constraints]
    return out


# ------------------------------------------------------------------------------------------------- the example's loop
def perform_robot(h, clip, f0, f1, rig=None, ground=None, at=(0.0, 0.0), heading=0.0, face=None, look=None, gaze=None,
                  phase=None, time_scale=1.0, crown_state=None, head_state=None, loop=True, clearance=True,
                  action_name=None, preroll=1.0, key=True, rest_feet=False):
    """eidoverse/examples/claude_robot.js renderFrame over frames f0..f1, in frame order, keyed into one action:

        face(t) -> {expression: weight}     (the mouth's five vowels kept summing to at most 1)
        look(t) -> the eyes' yaw, deg       (+ my left; lookLeft / lookRight at |yaw| / 28; the crown leans into it)
        gaze(t) -> (yaw, pitch) rad or None (VRMRobotBody's head look; None: the clip's head)
        ground  a Ground: the body set down every frame (None: the clip's height)
        rest_feet  both feet rested on the ground too (RobotRig.rest_feet; off: the WebGPU example's own set-down, which
                   leaves the stock idle's relaxed right foot 9-11 mm up)
        phase   the clip time at f0 (None: one frame step, as three's mixer.update(dt) runs before the first render)

    -> {'frames', 'action', 'face', 'set_down_mm', 'stats', '_frames'} (the records, for checks and further passes)"""
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt = 1.0 / fps
    rig = rig or RobotRig(h)
    phase = dt * time_scale if phase is None else phase
    Qr = Quaternion((0.0, 0.0, 1.0), heading * D2R)
    M0 = Matrix.Translation(Vector((at[0], at[1], 0.0))) @ Qr.to_matrix().to_4x4()
    if preroll > 0:
        # the face's state settled before the first frame: the head's and the crown's actuators start where it is
        w0 = mouth_capped(dict(face(0.0))) if face else {}
        if look is not None:
            w0.update(look_weights(look(0.0)))
        p3, _o = rig.clip_pose(clip, phase)
        for _k in range(int(preroll * fps)):
            q3 = {n: q.copy() for n, q in p3.items()}
            rig.head.apply(q3, w0, dt, state=head_state)
            rig.crown.apply(w0, dof.head_roll_deg(q3), dt, look=w0.get('lookLeft', 0.0) - w0.get('lookRight', 0.0),
                            state=crown_state)
    frames = []
    for f in range(f0, f1 + 1):
        t = (f - f0) * dt
        tc = phase + t * time_scale
        if not loop:
            tc = min(tc, clip.duration)
        p3, off = rig.clip_pose(clip, tc)
        w = dict(face(t)) if face else {}
        if look is not None:
            w.update(look_weights(look(t)))
        rec = rig.frame(p3, off, dt * time_scale, w, gaze(t) if gaze else None, crown_state, head_state,
                        clearance=clearance)
        rec['f'] = f
        rig.place(rec, M0, ground)
        if rest_feet and ground is not None:
            rig.rest_feet(rec, ground)
        frames.append(rec)
    rep = {'frames': [f0, f1], 'stats': {k: round(v, 2) for k, v in sorted(rig.stats.items())}}
    if key:
        rep['action'] = key_robot(h, frames, action_name or f'{h.name}|robot|{clip.slot}')
        rep['face'] = key_face_track(h, face_track(frames))
    if ground is not None:
        d = [fr['set_down_m'] for fr in frames]
        rep['set_down_mm'] = [round(-1000 * max(d), 1), round(-1000 * min(d), 1)]
    rep['_frames'] = frames
    return rep
