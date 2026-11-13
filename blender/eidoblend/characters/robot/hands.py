"""eidoblend.characters.robot.hands: my hands' work: reaching with the arm's real joints, grasping with the fingers' and the
thumb's real pins until each link touches, holding (the prop rides the hand), setting down and letting go.

    from eidoblend.characters.robot import hands
    rep = hands.pick_and_hold(me, rig, can, f0=1, side='right', ground=floor, look_at_it=True)   # keyed, any frame alone

The pieces, usable on their own:
    hm = hands.HandModel(rig, 'right')            # the hand's chains, its pins in this side's frame, its links' surfaces
    hands.reach(rig, rec, 'right', wrist, turn, swivel)   # two-bone IK onto the elbow's pin (rec['N'] in place)
    curls = hands.close_on(hm, rec, hands.Surface(obj), gap=0.001)          # each link closes until it touches
    hands.set_curls(hm, rec, curls)                # the fingers' and the thumb's pins (and the thumb's rotor) posed

THE ARM. The target is the wrist (the hand bone's head) and the hand's turn in the world. The elbow is a pin (the joints
file's leftLowerArm hinge, mirrored for the right): its flexion is the one that puts the wrist at the target's distance
from the shoulder; the upper arm takes the least turn onto the target and then swivels about the shoulder-wrist line; the
swivel is chosen (in 5 deg steps round a pole below and outside the shoulder) so the hand's turn against the forearm
lies inside the wrist's stops (roll +-90, flexion +-70, deviation in the coupled +-12: robot_dof.wrist_solve's split) with
the most margin. robot_dof's arm pass (the shoulder's pitch / roll / twist, the elbow's clamp, the wrist's three stages)
then runs on the result as on any pose: the reach is checked against what it leaves (the wrist's place, mm).

THE FINGERS. Each finger's three pins close in turn, proximal first, each until a link at or beyond it would come closer
than `gap` to the prop's surface (its signed distance from a BVH of the prop: no link passes into it), inside the pin's
range; a finger that meets nothing closes to its range. The thumb: its rotor turns it into opposition (alpha), then its
CMC pin, its MCP and its IP close the same way. robot_dof's hand pass then clamps them as it clamps any clip.

THE PROP rides the hand by a Child Of constraint on the hand's bone, its influence keyed on at the frame the hand closes
and off at the frame it lets go (the prop's own transform keyed to where the hand left it): it moves only in the hand
that moves it. A held prop's motion is never its own keys. Let go within a few degrees of upright, it tips onto its
base over three frames (keyed).

THE PATH (pick_and_hold) is planned for my hardware, not for a free arm:
  - every planned frame's elbow swivel is chosen by what THIS frame's arm pass makes of it (reach_through_hardware:
    the shoulder's stops, its pitch stage's actuator rate from where it is, the wrist's stops and turn limit);
  - carrying, the hand and the prop are one rigid pair that may turn about the prop's upright axis: each carried key
    takes the turn my wrist reaches best, and moves onto the pose my hardware actually makes (achieved);
  - looking it over is a roll of the forearm, as far as my wrist reaches it;
  - setting down goes to contact: the prop, riding the hand as the hardware will put it, never passes into the surface;
  - the free hand (to the pre-grasp, and home after rising past the prop) moves in its joints between key poses my
    hardware makes, the way a clip moves an arm.

THE GAZE (pick_and_hold): my head turns to the prop at the body's head actuator's rate, eased, from the clip's own head
(its roll carried: RobotRig.apply_gaze) and back onto it, a beat ahead of the hand and ahead of it to where the prop is
set down; my face's eyes (face_look, look_expression_weights: the VRM's look-at offset and ranges) take what my neck's
stops and the head's speed leave.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

from .. import robot_dof as dof
from .._math import D2R, R2D, clamp, ease, euler_from_quat, q_from_three, q_to_three, v_from_three

FINGERS = ('Index', 'Middle', 'Ring', 'Little')
LINKS = ('Proximal', 'Intermediate', 'Distal')
THUMB = ('ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal')


def _mirror_q3(q, m):
    return q.copy() if m > 0 else Quaternion((q.w, q.x, -q.y, -q.z))


def pin_turn(axis3, ang, side):
    """a pin's turn by `ang` about its joints-file axis (three's frame, the LEFT hand's), as this side's normalized turn in
    Blender's axes (the right mirrors: a turn's axis (x, -y, -z))"""
    q = Quaternion(Vector(axis3).normalized(), ang)
    return q_from_three(_mirror_q3(q, 1 if side == 'left' else -1))


class Surface:
    """a prop's surface for contact: its evaluated mesh in world space as a BVH, signed distance by the nearest face's
    normal (outside +)"""

    def __init__(self, obj, matrix=None):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        M = matrix if matrix is not None else ev.matrix_world
        self.verts = [M @ v.co for v in me.vertices]
        self.polys = [list(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        self.bvh = BVHTree.FromPolygons(self.verts, self.polys, all_triangles=False)

    def sdf(self, P):
        """signed distances of world points (n, 3) -> (n,). The nearest face's normal gives the sign, except where it
        says inside: there a ray's crossings decide (at a concave feature, a can's recessed lid, the nearest face can
        face away from a point that is outside)"""
        out = np.empty(len(P))
        for i, p in enumerate(P):
            v = Vector(p)
            q, n, _i, d = self.bvh.find_nearest(v)
            if q is None:
                out[i] = math.inf
                continue
            out[i] = d if ((v - q).dot(n) >= 0 or not inside(self.bvh, v)) else -d
        return out


_RAY = Vector((0.1234, 0.4567, 0.8811)).normalized()


def inside(bvh, p, direction=_RAY, far=50.0):
    """is p inside a closed mesh: an odd number of crossings along a ray"""
    o, n = Vector(p), 0
    for _ in range(64):
        hit = bvh.ray_cast(o, direction, far)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + direction * 1e-5
    return n % 2 == 1


class HandModel:
    """one hand of my body: its finger chains (humanoid names), each link's surface points (the vertices whose strongest
    skin weight is that link, as offsets from its rest head in the normalized frame, thinned), its pins (the joints file's
    axes and ranges, normalized: from the flexion at rest), the thumb's rotor and CMC axes, and the palm's contact patch"""

    def __init__(self, rig, side, step=3):
        h = rig.h
        if not getattr(rig, 'hardware', True) or not rig.hinges or 'leftThumbRotor' not in rig.hinges:
            raise ValueError(f'[hands] {h.name}: my hands\' work needs my body\'s pins (the joints file beside '
                             'claude_robot.vrm: the fingers\', the thumb\'s rotor and CMC, the wrist\'s stages); this VRM '
                             'has none (a plain RobotRig)')
        self.rig, self.side, self.h = rig, side, h
        self.m = 1 if side == 'left' else -1
        T = rig.hinges or {}
        self.T = T
        self.H = rig.body.H
        want = {}
        for f in FINGERS:
            for k in LINKS:
                want[h.humanoid.get(side + f + k)] = side + f + k
        for k in THUMB:
            want[h.humanoid.get(side + k)] = side + k
        want[h.humanoid.get(side + 'Hand')] = side + 'Hand'
        pts = {}
        inv = h.arm.matrix_world.inverted()
        for o in h.meshes:
            if not o.vertex_groups:
                continue
            idx = {g.index: g.name for g in o.vertex_groups}
            if not any(n in want for n in idx.values()):
                continue
            Mo = inv @ o.matrix_world
            for v in o.data.vertices:
                if not v.groups:
                    continue
                g = max(v.groups, key=lambda g: g.weight)
                n = want.get(idx.get(g.group))
                if n:
                    pts.setdefault(n, []).append(tuple(Mo @ v.co))
        self.pts = {}
        for n, P in pts.items():
            A = np.array(P, dtype=np.float64)
            head = np.array(self.H[n])
            self.pts[n] = (A - head)[::step] if n != side + 'Hand' else (A - head)
        # the palm's contact point: on the hand link's inner face (the side the fingers close toward), under the
        # middle of the palm (halfway from the wrist to the middle finger's knuckle): the hand link's points within
        # 12 mm of that line along the palm's normal, the innermost of them
        A = self.pts[side + 'Hand']
        self.palm_normal_rest = self._curl_dir()
        nrm = np.array(self.palm_normal_rest)
        pk = 0.5 * (np.array(self.H[side + 'MiddleProximal']) - np.array(self.H[side + 'Hand']))
        rel = A - pk
        perp = rel - np.outer(rel @ nrm, nrm)
        near = np.linalg.norm(perp, axis=1) < 0.012
        depth = float((rel[near] @ nrm).max()) if near.any() else 0.0
        self.palm_centre = Vector(pk + nrm * depth)
        self.pts[side + 'Hand'] = A[::step]
        self.pins = {}
        for f in FINGERS:
            for k in LINKS:
                j = T.get('left' + f + k)
                if j:
                    self.pins[f + k] = {'axis': j['axis'], 'range': ((j['deg'][0] - j['flex_at_rest']) * D2R,
                                                                       (j['deg'][1] - j['flex_at_rest']) * D2R)}
        for k in ('ThumbProximal', 'ThumbDistal', 'ThumbMetacarpal', 'ThumbRotor'):
            j = T.get('left' + k)
            if j:
                self.pins[k] = {'axis': j['axis'], 'range': ((j['deg'][0] - j['flex_at_rest']) * D2R,
                                                               (j['deg'][1] - j['flex_at_rest']) * D2R)}
        Yr = Vector(T['leftThumbRotor']['axis']).normalized()
        P0 = Yr.cross(Vector(T['leftThumbMetacarpal']['axis'])).cross(Yr).normalized()
        self.Yr, self.P0 = Yr, P0

    def _curl_dir(self):
        """the direction the fingers close toward at rest (the palm's normal), Blender's normalized axes: the middle
        finger's tip turned a little about its proximal pin, minus where it was"""
        side = self.side
        tip = Vector(self.H[side + 'MiddleDistal']) - Vector(self.H[side + 'MiddleProximal'])
        j = self.T.get('leftMiddleProximal')
        q = pin_turn(j['axis'], 0.3, side)
        d = (q @ tip) - tip
        return Vector(d).normalized()

    # ---- the pose of one hand's links, from the hand's world head and turn
    def chain_world(self, N, p_hand, W_hand):
        """{link: (head, turn)} world, for the fingers and the thumb from the hand's world place"""
        out = {}
        side, H = self.side, self.H
        for f in FINGERS + ('Thumb',):
            names = [side + f + k for k in (LINKS if f != 'Thumb' else ('Metacarpal', 'Proximal', 'Distal'))]
            p, W, prev = p_hand, W_hand, side + 'Hand'
            for n in names:
                if n not in N:
                    break
                p = p + W @ (Vector(H[n]) - Vector(H[prev]))
                W = W @ N[n]
                out[n] = (p, W)
                prev = n
        return out

    def link_points(self, name, p, W):
        P = self.pts.get(name)
        if P is None or not len(P):
            return np.zeros((0, 3))
        R = np.array(W.to_matrix())
        return P @ R.T + np.array(p)


# ---------------------------------------------------------------------------------------------------------------- the arm
def _wrist_margin(rig, side, q_rel_bl):
    """the hand's turn against the forearm (Blender's normalized axes) split as the wrist's stages split it -> (the least
    margin to a stop, rad: negative past it, (a, b, c))"""
    W = rig.arms.wrist.get(side)
    m = 1 if side == 'left' else -1
    q3 = _mirror_q3(q_to_three(q_rel_bl), m)
    if W is None:
        return 1.0, (0.0, 0.0, 0.0)
    qb = W['Bi'] @ q3 @ W['B']
    a, b, c = euler_from_quat(qb, 'XYZ')
    A = dof.ARM
    lo, hi = dof.wrist_dev_range(W.get('sgnA', 1) * b * R2D)
    if W.get('sgnD', 1) < 0:
        lo, hi = -hi, -lo
    mg = min(A['wristRoll'][1] * D2R - abs(a), A['wristFlex'][1] * D2R - abs(b), hi * D2R - c, c - lo * D2R)
    return mg, (a, b, c)


def elbow_axis(rig, side):
    """the elbow's pin in Blender's normalized axes for this side, and its range (rad, normalized: from the rest)"""
    el = rig.arms.elbow
    XF = Vector(el['XF'])
    if side == 'right':
        XF = Vector((XF.x, -XF.y, -XF.z))
    return v_from_three(XF).normalized(), (el['flex'][0] * D2R, el['flex'][1] * D2R)


def reach(rig, rec, side, wrist, turn, swivel=None, pole=None, step_deg=5.0, hint=None):
    """two-bone IK of `side`'s arm on the record (N in place): the hand's head to `wrist` (world), the hand turned to
    `turn` (world, normalized sense); the elbow's swivel about the shoulder-wrist line chosen for the wrist's margin (or
    given, rad from the pole) -> {'swivel', 'margin', 'wrist_split', 'flex', 'reach_short'}"""
    h, N = rig.h, rec['N']
    H = rig.body.H
    ua, la, hd, sh = side + 'UpperArm', side + 'LowerArm', side + 'Hand', side + 'Shoulder'
    N[sh] = Quaternion()
    p_s, W_s = rig.bone_world(rec, sh)
    S = p_s + W_s @ (Vector(H[ua]) - Vector(H[sh]))
    u = Vector(H[la]) - Vector(H[ua])
    w = Vector(H[hd]) - Vector(H[la])
    XF, (flo, fhi) = elbow_axis(rig, side)
    D = wrist - S
    dist = D.length

    def span(k):
        return (u + Quaternion(XF, k) @ w).length
    lo, hi = max(flo, 0.0), fhi
    short = 0.0
    if dist >= span(lo):
        k = lo
        short = dist - span(lo)
    elif dist <= span(hi):
        k = hi
    else:
        a_, b_ = lo, hi
        for _ in range(50):
            mid = 0.5 * (a_ + b_)
            if span(mid) > dist:
                a_ = mid
            else:
                b_ = mid
        k = 0.5 * (a_ + b_)
    qe = Quaternion(XF, k)
    vc = u + qe @ w
    n = D.normalized()
    W0 = vc.rotation_difference(D)               # the least turn from rest putting the chain on the line
    e0 = W0 @ u                                  # the elbow, before the swivel
    if pole is None:                             # below the shoulder and a little out from the body
        out = W_s @ Vector((1.0 if side == 'left' else -1.0, 0.0, 0.0))
        pole = Vector((0.0, 0.0, -1.0)) + Vector((out.x, out.y, 0.0)) * 0.4
    pp = (pole - n * pole.dot(n))
    ep = (e0 - n * e0.dot(n))
    base = math.atan2(ep.cross(pp).dot(n), ep.dot(pp)) if pp.length > 1e-6 and ep.length > 1e-6 else 0.0

    def solve(psi):
        W_ua = Quaternion(n, base + psi) @ W0
        W_la = W_ua @ qe
        return W_ua, W_la, W_la.inverted() @ turn
    if swivel is None:
        best = None
        for kk in range(-int(80 / step_deg), int(80 / step_deg) + 1):
            psi = kk * step_deg * D2R
            _ua, _la, rel = solve(psi)
            mg, abc = _wrist_margin(rig, side, rel)
            cost = -min(mg, 0.35) + 0.15 * abs(psi)          # margin first (to 20 deg), then the pole
            if hint is not None:
                cost += 0.6 * abs(psi - hint)                # and no flip from the last frame's
            if best is None or cost < best[0]:
                best = (cost, psi, mg, abc)
        swivel = best[1]
    W_ua, W_la, rel = solve(swivel)
    mg, abc = _wrist_margin(rig, side, rel)
    N[ua] = W_s.inverted() @ W_ua
    N[la] = qe
    N[hd] = rel
    return {'swivel': swivel, 'margin_deg': mg * R2D, 'wrist_split_deg': [x * R2D for x in abc], 'flex_deg': k * R2D,
            'reach_short_m': short, '_base': base, '_n': n, '_W0': W0, '_u': u}


def swivel_of(rig, rec, side):
    """the swivel (rad, reach's measure) of the record's own arm: the elbow's place round the shoulder-wrist line"""
    p_w, W_h = rig.bone_world(rec, side + 'Hand')
    p_e, _W = rig.bone_world(rec, side + 'LowerArm')
    probe = {'N': dict(rec['N']), 'off': rec['off'], 'M': rec['M']}
    r = reach(rig, probe, side, p_w, W_h, swivel=0.0)
    n, W0, u = r['_n'], r['_W0'], r['_u']
    p_s, W_s = rig.bone_world(rec, side + 'UpperArm')
    e_act = p_e - p_s
    e0 = W0 @ u
    a = e0 - n * e0.dot(n)
    b = e_act - n * e_act.dot(n)
    if a.length < 1e-6 or b.length < 1e-6:
        return 0.0
    return math.atan2(a.cross(b).dot(n), a.dot(b)) - r['_base']


def wrist_error(rig, rec, side, wrist, turn):
    """where the hand is after the pose (FK) against the target: (mm, deg)"""
    p, W = rig.bone_world(rec, side + 'Hand')
    return (p - wrist).length * 1000, math.degrees(W.rotation_difference(turn).angle)


# ---------------------------------------------------------------------------------------------------------------- fingers
def set_curls(hm, N, curls, dof_state=False):
    """the fingers' pins and the thumb's stages from curls {'Index': (gP, gI, gD), ..., 'Thumb': (alpha, beta, gMCP,
    gIP)} (rad, normalized: from the flexion at rest) into N (Blender's axes). dof_state: also tell robot_dof's hand
    pass that this is the thumb's last solution: it solves the rotor and the CMC from the metacarpal's DIRECTION, which
    two (alpha, beta) pairs give (different twists about it); of those it keeps the one nearest its last, so a commanded
    thumb passes through it unchanged"""
    side = hm.side
    if dof_state and 'Thumb' in curls and hm.rig.hands is not None:
        st = hm.rig.hands.side[side]
        st['alpha'], st['beta'] = curls['Thumb'][0], curls['Thumb'][1]
    for f in FINGERS:
        if f not in curls:
            continue
        for k, g in zip(LINKS, curls[f]):
            pin = hm.pins.get(f + k)
            if pin:
                N[side + f + k] = pin_turn(pin['axis'], g, side)
    if 'Thumb' in curls:
        al, be, g1, g2 = curls['Thumb']
        q3 = Quaternion(hm.Yr, al) @ Quaternion(hm.P0, be)
        N[side + 'ThumbMetacarpal'] = q_from_three(_mirror_q3(q3, hm.m))
        for k, g in (('ThumbProximal', g1), ('ThumbDistal', g2)):
            pin = hm.pins.get(k)
            if pin:
                N[side + k] = pin_turn(pin['axis'], g, side)


def close_on(hm, rec, surf, gap=0.001, open_curls=None, step=1.0, support_z=None, alphas=range(60, -1, -5), pre=None):
    """each finger's pins closed in turn (proximal first) until a link at or past the pin would come within `gap` of
    the prop's surface (a pin whose open angle already presses in opens until it clears); the thumb turned into the
    most opposition (alpha, its rotor) that clears the prop open, then its CMC, MCP and IP closed the same way. A thumb
    that closes that way without touching (a square-sided prop: the pre-shaped thumb presses into the side at every
    higher opposition, and from the one that clears it curls past the prop into the palm) is searched again opened
    flat (its CMC, MCP and IP at their open stops): the most opposition that clears flat and closes onto the prop;
    `pre` (a dict) then gets that open thumb as 'Thumb', for the hand's approach and release. No link goes below
    support_z (the surface the prop stands on) -> (curls, the least clearance per finger, m)"""
    side = hm.side
    N = dict(rec['N'])
    p_hand, W_hand = hm.rig.bone_world(rec, side + 'Hand')
    curls = {f: list((open_curls or {}).get(f, (0.0, 0.0, 0.0))) for f in FINGERS}
    th = list((open_curls or {}).get('Thumb', (0.0, 0.0, 0.0, 0.0)))
    clear = {}

    def links_of(f):
        return [side + f + k for k in LINKS] if f != 'Thumb' else [side + k for k in THUMB]

    def dist(f, from_j):
        set_curls(hm, N, {**{g: tuple(curls[g]) for g in FINGERS}, 'Thumb': tuple(th)})
        if f == 'Thumb':
            N.update(hand_preview(hm, N, th))         # the thumb as robot_dof's hand pass leaves it
        W = hm.chain_world(N, p_hand, W_hand)
        names = links_of(f)[from_j:]
        P = np.concatenate([hm.link_points(n, *W[n]) for n in names if n in W] or [np.zeros((0, 3))])
        if not len(P):
            return math.inf
        d = float(surf.sdf(P).min())
        if support_z is not None:
            d = min(d, float(P[:, 2].min()) - support_z - 0.002)
        return d

    def close_pin(get, put, f, from_j, rng):
        """close one pin from its current angle while the links from it stay clear; open it first if they do not"""
        g = max(get(), rng[0])
        put(g)
        if dist(f, from_j) <= gap:
            a_, b_ = rng[0], g
            put(a_)
            if dist(f, from_j) <= gap:
                return
            for _ in range(14):
                mid = 0.5 * (a_ + b_)
                put(mid)
                if dist(f, from_j) <= gap:
                    b_ = mid
                else:
                    a_ = mid
            put(a_)
            return
        while g < rng[1]:
            g2 = min(rng[1], g + step * D2R)
            put(g2)
            if dist(f, from_j) <= gap:
                a_, b_ = g, g2
                for _ in range(12):
                    mid = 0.5 * (a_ + b_)
                    put(mid)
                    if dist(f, from_j) <= gap:
                        b_ = mid
                    else:
                        a_ = mid
                put(a_)
                return
            g = g2
    for f in FINGERS:
        for j, k in enumerate(LINKS):
            pin = hm.pins.get(f + k)
            if not pin:
                continue

            def get(f=f, j=j):
                return curls[f][j]

            def put(v, f=f, j=j):
                curls[f][j] = v
            close_pin(get, put, f, j, pin['range'])
        clear[f] = dist(f, 0)
    # the thumb: the most opposition that clears, then its pins
    rot = hm.pins.get('ThumbRotor')
    th_open = list(th)

    def close_thumb():
        for idx, k in ((1, 'ThumbMetacarpal'), (2, 'ThumbProximal'), (3, 'ThumbDistal')):
            pin = hm.pins.get(k)
            if not pin:
                continue
            rng = pin['range']
            if idx == 1:      # the CMC's coupled stop against the stator's lip (robot_dof's b_max at this alpha)
                o = th[0] * R2D + hm.T['leftThumbRotor']['flex_at_rest']
                lim = 87 if o <= 40 else (87 - 0.1 * (o - 40) if o <= 50 else 86 - 0.7 * (o - 50))
                rng = (rng[0], min(rng[1], (lim - hm.T['leftThumbMetacarpal']['flex_at_rest']) * D2R))

            def get(idx=idx):
                return th[idx]

            def put(v, idx=idx):
                th[idx] = v
            close_pin(get, put, 'Thumb', idx - 1, rng)
        return dist('Thumb', 0)
    if rot:
        for a_d in alphas:
            th[0] = clamp(a_d * D2R, *rot['range'])
            if dist('Thumb', 0) > gap + 0.002:
                break
    c_th = close_thumb()
    if rot and c_th > gap + 0.0005:
        # it closed without touching: the most opposition at which the thumb opened flat clears, closing onto the prop
        best_t = (c_th, list(th), th_open)
        for a_d in alphas:
            flat = [clamp(a_d * D2R, *rot['range'])] + [hm.pins[k]['range'][0] if k in hm.pins else 0.0
                                                          for k in ('ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal')]
            th[:] = flat
            c_open = dist('Thumb', 0)
            if c_open <= gap + 0.0003:                  # opened flat it still presses in at this opposition
                if pre is not None:
                    pre.setdefault('trace', []).append((a_d, round(1000 * c_open, 1), None))
                continue
            c2 = close_thumb()
            if pre is not None:
                pre.setdefault('trace', []).append((a_d, round(1000 * c_open, 1), round(1000 * c2, 1)))
            if c2 < best_t[0] - 1e-6:
                best_t = (c2, list(th), flat)
            if c2 <= gap + 0.0005:
                break
        th[:] = best_t[1]
        if pre is not None and best_t[2] is not th_open:
            pre['Thumb'] = tuple(best_t[2])
    clear['Thumb'] = dist('Thumb', 0)
    out = {f: tuple(curls[f]) for f in FINGERS}
    out['Thumb'] = tuple(th)
    return out, clear


def hand_preview(hm, N, thumb=None):
    """the thumb as robot_dof's hand pass leaves it (its state untouched; told the commanded alpha / beta are its last,
    as set_curls(dof_state=True) tells it in the frames) -> {thumb link: Quaternion}"""
    rig, side = hm.rig, hm.side
    H = rig.hands
    if H is None:
        return {}
    st = H.side[side]
    keep = (st['alpha'], st['beta'], st.get('dbg'), dict(H.rotor_out))
    if thumb is not None:
        st['alpha'], st['beta'] = thumb[0], thumb[1]
    p3 = {n: q_to_three(q) for n, q in N.items()}
    dof.apply_hand_dof(H, p3)
    st['alpha'], st['beta'], st['dbg'] = keep[0], keep[1], keep[2]
    H.rotor_out.clear()
    H.rotor_out.update(keep[3])
    return {side + k: q_from_three(p3[side + k]) for k in THUMB if (side + k) in p3}


def lerp_curls(a, b, u):
    return {k: tuple(x + (y - x) * u for x, y in zip(a[k], b[k])) for k in b}


def hand_frame(hm):
    """the rest hand's own frame from its geometry (Blender's normalized axes): fingers (wrist -> the middle finger's
    knuckle), knuckles (index -> little, square to the fingers), palm (the side the fingers close toward)"""
    side, H = hm.side, hm.H
    d = (Vector(H[side + 'MiddleProximal']) - Vector(H[side + 'Hand'])).normalized()
    k = Vector(H[side + 'LittleProximal']) - Vector(H[side + 'IndexProximal'])
    k = (k - d * k.dot(d)).normalized()
    n = d.cross(k)
    if n.dot(hm.palm_normal_rest) < 0:
        n = -n
    return d, k, n


def grasp_turn(hm, approach, tilt=0.0, up=Vector((0.0, 0.0, 1.0))):
    """the hand's world turn for a side grasp of an upright prop: the palm toward `approach` (horizontal, from the hand
    to the prop's axis), the knuckles' line pointing down (the index on top) tilted by `tilt` rad about the approach,
    the fingers wrapping round the far side: the rest hand's own frame (hand_frame) carried onto that"""
    d, k, n = hand_frame(hm)
    hand = 1.0 if d.cross(k).dot(n) > 0 else -1.0
    n2 = Vector((approach.x, approach.y, 0.0)).normalized()
    k2 = Quaternion(n2, tilt) @ (-up)
    d2 = k2.cross(n2) * hand
    R = Matrix((d2, k2, n2)).transposed() @ Matrix((d, k, n)).transposed().inverted()
    return R.to_quaternion()


def hand_lowest(hm, turn, curls):
    """the lowest point of the hand and every link of its fingers (posed by curls: the pre-shaped hand) under the wrist,
    for the hand turned by `turn` (m): the grip must sit high enough that none of it meets the surface under the prop"""
    N = {}
    set_curls(hm, N, curls)
    W = hm.chain_world(N, Vector((0.0, 0.0, 0.0)), turn)
    P = [hm.link_points(hm.side + 'Hand', Vector((0.0, 0.0, 0.0)), turn)]
    P += [hm.link_points(n, *W[n]) for n in W]
    return float(np.concatenate(P)[:, 2].min())


def arm_preview(rig, N, side, dt=None):
    """the pose the arm's DOF pass leaves (robot_dof.apply_arm_dof, no turn-out), its state untouched. dt None: a
    fresh pass (no turn limit, the shoulder's pitch free to go anywhere: the reach checked against the joints' stops);
    dt a frame step: THIS frame's pass from the arm's current state (the shoulder's pitch stage turning at most its
    actuator's rate from where it is, the wrist's turn limit from its last solution)"""
    A = rig.arms
    keep = (dict(A.phi), dict(A.helper_phi), dict(A.wrist_out), A.kept,
            {s: dict(w) for s, w in A.wrist.items()})
    p3 = {n: q_to_three(q) for n, q in N.items()}
    if dt is None:
        for w in A.wrist.values():
            w['memo'] = None
    dof.apply_arm_dof(A, p3, 1.0 if dt is None else dt, 0.0)
    A.phi, A.helper_phi, A.wrist_out, A.kept, ws = keep[0], keep[1], keep[2], keep[3], keep[4]
    for s, w in ws.items():
        A.wrist[s].clear()
        A.wrist[s].update(w)
    out = dict(N)
    for n in (side + 'UpperArm', side + 'LowerArm', side + 'Hand', side + 'Shoulder'):
        out[n] = q_from_three(p3[n])
    return out


def reach_through_hardware(rig, rec, side, wrist, turn, swivel, dt, last=None, span_deg=45.0, step_deg=5.0, turn_w=2.0):
    """reach() whose elbow swivel is chosen by what the arm's hardware pass will make of it THIS frame (arm_preview with
    dt: the shoulder's stops, its pitch stage's actuator rate from where it stands, the wrist's stops and turn limit):
    swivels round the planned one, each solved, passed through the hardware and measured against the target (the wrist's
    place, mm, and the hand's turn, a degree weighing turn_w mm), the least miss kept, then the nearest to the last
    frame's (no flip). rec['N'] in place -> reach()'s report with 'miss_mm' and 'miss_deg' (what the pass will leave)"""
    best = None
    n = int(span_deg / step_deg)
    for k in range(-n, n + 1):
        psi = swivel + k * step_deg * D2R
        probe = {'N': dict(rec['N']), 'off': rec['off'], 'M': rec['M']}
        r = reach(rig, probe, side, wrist, turn, swivel=psi)
        Np = arm_preview(rig, probe['N'], side, dt)
        p, W = rig.bone_world({'N': Np, 'off': rec['off'], 'M': rec['M']}, side + 'Hand')
        miss_mm = 1000 * (p - wrist).length
        miss_deg = math.degrees(W.rotation_difference(turn).angle)
        cost = miss_mm + turn_w * miss_deg + 0.2 * abs(k) * step_deg + (0.6 * abs(math.degrees(psi - last))
                                                                        if last is not None else 0.0)
        if best is None or cost < best[0]:
            best = (cost, psi, probe['N'], dict(r, miss_mm=miss_mm, miss_deg=miss_deg))
    rec['N'].update(best[2])
    return best[3]


AT_PROP_TURN_W = 8.0      # mm a degree of the hand's turn weighs in the elbow's swivel while the hand is at the prop


def _rot_z(q, ang):
    return Quaternion((0.0, 0.0, 1.0), ang) @ q


FLAT_SNAP_DEG = 5.0      # a face whose normal is this far off the approach is a flat side met at an angle (a round
#                          prop's facets: 2.8 deg on a 64-sided can), and the approach squares to it


def _face_on(surf, axis, z, a, far):
    """the prop's surface met from outside along the horizontal approach `a` (toward its axis) at height z -> (the
    point, its outward horizontal normal) or None"""
    o = Vector((axis.x, axis.y, z)) - a * far
    hit = surf.bvh.ray_cast(o, a, 2.0 * far)
    if hit[0] is None:
        return None
    n = Vector((hit[1].x, hit[1].y, 0.0))
    if n.length < 1e-6:
        return None
    n.normalize()
    if n.dot(a) > 0:                     # the face's outward side is the one the hand comes from
        n = -n
    return hit[0], n


def pick_and_hold(h, rig, obj, f0=1, side='right', clip=None, ground=None, at=(0.0, 0.0), heading=0.0, fps=None,
                  look_at_it=True, set_down_offset=(0.0, 0.0), gap=0.0006, palm_gap=0.003, face=None, timing=None,
                  action_name=None, rest_feet=True, look_over_deg=(40.0, -35.0), head_rate=math.pi / 2,
                  head_accel=2.0 * math.pi, gaze_lead=0.1, look_eyes=True, eye_rate=5.0, log=print):
    """my body standing at `at` facing `heading` (rad, 0 faces -Y) reaches for `obj` (an upright prop on a surface in
    front of it, its origin on its axis), closes its hand on it, lifts it, brings it before its face, turns it in the
    wrist to look it over, sets it down (moved by set_down_offset, m) and lets go, all keyed from f0 -> report.
    rest_feet: both feet on the floor through the idle (RobotRig.rest_feet); look_at_it: my head looks at the prop from
    the reach until my arm is home: where it stands, then where my hand carries it gaze_lead (s) ahead, then, once it is
    looked over, where it will be set down (the eyes lead the hand), and back onto the clip's own head after. The head
    turns at most head_rate (rad/s: VRMRobotBody's 90 deg/s), speeding up and slowing down at head_accel (rad/s2).
    look_eyes: my face's eyes (its look expressions, the VRM's lookAt ranges) take what the head's stops and speed
    leave, at most eye_rate (rad/s)"""
    from ..ground import Ground
    from ..vrma import load_clip
    from .rig import face_track, key_robot
    from ..performance import key_face_track
    sc = bpy.context.scene
    fps = fps or sc.render.fps / sc.render.fps_base
    dt = 1.0 / fps
    ground = ground or Ground(fn=lambda x, y: 0.0 * np.asarray(x))
    T = {'reach': 0.5, 'up_in': 1.1, 'arc_in': 1.7, 'pre': 2.3, 'touch': 2.8, 'closed': 3.3, 'lift': 4.3, 'face': 5.5,
         'turn_a': 6.3, 'turn_b': 7.3, 'face2': 7.9, 'over': 9.1, 'down': 9.7, 'open': 10.2, 'clear': 10.6,
         'arc_out': 11.3, 'up_out': 11.9, 'back': 12.6, 'end': 13.4}
    T.update(timing or {})
    nfr = int(round(T['end'] * fps)) + 1
    idle = clip or load_clip(h, 'idle')
    hm = HandModel(rig, side)
    # the prop: its axis, radius, height (an upright prop: its bounding box in its own frame)
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
    hi = Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
    axis = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0.0))
    radius = 0.25 * ((hi.x - lo.x) + (hi.y - lo.y))
    height = hi.z - lo.z
    M_obj0 = obj.matrix_world.copy()
    root = Matrix.Translation(Vector((at[0], at[1], 0.0))) @ Quaternion((0.0, 0.0, 1.0), heading).to_matrix().to_4x4()
    Qr = root.to_quaternion()
    m = 1 if side == 'left' else -1
    # the frames: the idle through the stand passes, the arm and hand overridden
    rig.clear.reset() if rig.clear is not None else None
    surf = Surface(obj)
    raw0 = rig.place(rig.stand_raw(idle, dt, dt), root, ground)
    # the pre-shaped hand: each finger loosely curled (20, 20, 11 deg: they close in the plane square to the knuckles,
    # so they keep to their knuckles' height), the thumb part-way into opposition
    open_c = {f: (0.35, 0.35, 0.2) for f in FINGERS}
    open_c['Thumb'] = (35.0 * D2R, 0.15, 0.05, 0.05)
    # letting go, the hand opens back to the same pre-shape and backs off the way it came in: that shape cleared the
    # prop and the surface on the way in (straighter fingers reach lower: the little finger's tip would touch the surface)
    release_c = dict(open_c)
    # THE GRASP, planned: round the prop's side facing this hand (the azimuth), the knuckles' line tilted off upright (a
    # diagonal power grasp), the grip as low as the open hand clears the surface under the prop; each candidate's arm
    # solved and scored by the wrist's margin inside its stops, then by how little it turns from the plain grasp
    left_dir = Qr @ Vector((1.0, 0.0, 0.0))
    a0 = left_dir if side == 'right' else -left_dir
    support_z = lo.z
    best = None
    tried = []
    far = 3.0 * radius + 0.1
    for phi_d in range(-60, 41, 10):
        a = Quaternion((0.0, 0.0, 1.0), -m * phi_d * D2R) @ a0
        # a FLAT side (a carton, a box) met at an angle: the palm squared to it (the approach along the face's inward
        # normal), else a palm square to the azimuth meets the face on its edge and presses one side of the hand in. A
        # round prop's facets (a few degrees) leave the azimuth as it is
        side_hit = _face_on(surf, axis, lo.z + 0.5 * height, a, far)
        flat = side_hit is not None and math.degrees(side_hit[1].angle(-a)) > FLAT_SNAP_DEG
        if flat:
            a = -side_hit[1]
        for tau_d in range(-40, 41, 10):
            turn_c = grasp_turn(hm, a, tau_d * D2R)
            palm_off_c = turn_c @ hm.palm_centre
            low = hand_lowest(hm, turn_c, open_c)
            need = support_z + 0.008 - low + palm_off_c.z
            zg = min(hi.z - 0.035, max(lo.z + 0.5 * height, need))
            contact_c = axis + Vector((0.0, 0.0, zg)) - a * (radius + palm_gap)
            if flat:
                face_g = _face_on(surf, axis, zg, a, far)    # the palm on the face itself (not the bounding radius)
                if face_g is not None:
                    contact_c = face_g[0] - a * palm_gap
            wrist_c = contact_c - palm_off_c
            rec_c = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
            r = reach(rig, rec_c, side, wrist_c, turn_c)
            tried.append((phi_d, tau_d, round(r['margin_deg'], 1), round(1000 * (need - lo.z)), round(1000 * (zg - lo.z)),
                          round(1000 * r['reach_short_m'], 1)))
            if r['reach_short_m'] > 0.002 or zg < need - 1e-6:
                continue
            cost = -min(r['margin_deg'], 15.0) + 0.05 * abs(tau_d) + 0.04 * abs(phi_d)
            if best is None or cost < best[0]:
                best = (cost, phi_d, tau_d, a, turn_c, zg, wrist_c, r)
    tried.sort(key=lambda r: -r[2])
    log('[hands] grasp candidates by wrist margin (azimuth, tilt, margin deg, grip needed mm, grip mm, short mm): '
        + str(tried[:12]))
    if best is None:
        raise RuntimeError('[hands] no grasp of the prop is in reach from here')
    _c, phi_d, tau_d, approach, turn, grip_z, wrist_grasp, rep_g = best
    rep_g = dict(rep_g, azimuth_deg=phi_d, tilt_deg=tau_d)
    # the hand closed where the arm's own pass leaves it (its stops: the wrist's split clamped, if it must be)
    rec_g = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
    reach(rig, rec_g, side, wrist_grasp, turn)
    rec_g['N'] = arm_preview(rig, rec_g['N'], side)
    set_curls(hm, rec_g['N'], open_c)
    # the palm never presses in: the whole palm link (not only its centre) measured against the prop's surface there,
    # and the grasp backed off along the approach by what it lacks of palm_gap (a flat face meets the palm's rim too)
    for _k in range(3):
        p_h, W_h = rig.bone_world(rec_g, side + 'Hand')
        palm_min = float(surf.sdf(hm.link_points(side + 'Hand', p_h, W_h)).min())
        if palm_min >= palm_gap - 0.0003:
            break
        wrist_grasp = wrist_grasp - approach * (palm_gap - palm_min)
        rec_g = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
        reach(rig, rec_g, side, wrist_grasp, turn)
        rec_g['N'] = arm_preview(rig, rec_g['N'], side)
        set_curls(hm, rec_g['N'], open_c)
    wrist_pre = wrist_grasp - approach * 0.07
    pre = {}
    closed, clear = close_on(hm, rec_g, surf, gap=gap, open_curls=open_c, support_z=support_z, pre=pre)
    if 'Thumb' in pre:
        # the pre-shaped thumb pressed into this prop: the hand comes in and lets go with the thumb opened flat at the
        # opposition it closes from (it clears the prop there), not the pre-shape's
        open_c = dict(open_c, Thumb=pre['Thumb'])
        release_c = dict(release_c, Thumb=pre['Thumb'])
        log(f'[hands] the thumb comes in opened flat at {math.degrees(pre["Thumb"][0]):.0f} deg of opposition (the '
            f'pre-shape pressed into the prop)')
    if pre.get('trace'):
        log('[hands] the thumb searched opened flat (opposition deg, open clearance mm, closed clearance mm): '
            + str(pre['trace']))
    log(f'[hands] grasp: azimuth {phi_d} deg, knuckles tilted {tau_d} deg, grip {1000 * (grip_z - lo.z):.0f} mm up; '
        f'elbow swivel {math.degrees(rep_g["swivel"]):.0f} deg, wrist margin {rep_g["margin_deg"]:.1f} deg (split '
        f'{[round(x, 1) for x in rep_g["wrist_split_deg"]]}), elbow {rep_g["flex_deg"]:.0f} deg; clearances (mm) '
        + ', '.join(f'{k} {v * 1000:.1f}' for k, v in clear.items()))
    # the hand's path: keys (time, wrist, turn) in the world; between them eased
    face_pt = None
    p_head, _W = rig.bone_world(raw0, 'head')
    fwd = Qr @ Vector((0.0, -1.0, 0.0))
    face_pt = p_head + fwd * 0.34 + Vector((0.0, 0.0, -0.08))
    # the prop carried: the hand and the prop one rigid pair, which may turn about the prop's own upright axis on the way
    # (alpha: the prop stays upright and is set down where it was, its label turned). Each carried key takes the alpha
    # my arm reaches best through its hardware (the shoulder's and the wrist's stops: a wrist that keeps the grasp's own
    # world turn at the face would need a roll past its 90 deg stop)
    grip_vec = (axis + Vector((0.0, 0.0, grip_z))) - wrist_grasp

    def carried(centre, a, q=None):
        Rz = Quaternion((0.0, 0.0, 1.0), a)
        return centre - Rz @ grip_vec, Rz @ (q if q is not None else turn)

    def key_eval(w_k, q_k):
        rec_k = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
        r_k = reach_through_hardware(rig, rec_k, side, w_k, q_k, 0.0, None, span_deg=80.0, step_deg=10.0)
        return r_k['miss_mm'] + 2.0 * r_k['miss_deg'], r_k['margin_deg']

    def key_miss(w_k, q_k):
        return key_eval(w_k, q_k)[0]

    def best_alpha(centre, prefer=0.0):
        """the turn about the prop's axis (10 deg steps) my arm makes best for a carried key (a fresh hardware pass: the
        frame's own pass also carries the wrist's turn limit and the shoulder's pitch rate, so a finer search on the
        fresh pass does not make the frames closer)"""
        best_a = None
        for a_d in range(-120, 121, 10):
            a = a_d * D2R
            cost = key_miss(*carried(centre, a)) + 0.08 * abs(a_d - prefer * R2D)
            if best_a is None or cost < best_a[0]:
                best_a = (cost, a)
        return best_a[1]
    def achieved(w_k, q_k):
        """where my hardware actually puts the hand for this key (the best swivel, then the arm's pass): the key moved
        onto it, so the carried path runs between poses my arm makes (a prop held before my face from this grasp tips a
        little where my wrist meets its stops)"""
        rec_k = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
        reach_through_hardware(rig, rec_k, side, w_k, q_k, 0.0, None, span_deg=80.0, step_deg=10.0)
        Np = arm_preview(rig, rec_k['N'], side)
        return rig.bone_world({'N': Np, 'off': raw0['off'], 'M': raw0['M']}, side + 'Hand')
    lift_c = wrist_grasp + Vector((0.0, 0.0, 0.16)) - approach * 0.02 + grip_vec
    a_lift = best_alpha(lift_c, 0.0)
    # HOLDING IT UP TO LOOK AT IT: the place before my face my arm actually brings it to, upright. Candidates from
    # centred before my face out toward the holding shoulder and down to the chin: the first my hardware makes within
    # 2.5 cm and 8 deg (a place it cannot make, it would leave lower or turned: a held can that sinks to the chest)
    p_shoulder, _W = rig.bone_world(raw0, side + 'UpperArm')
    look_at_pt = None
    for dz in (0.04, -0.04, -0.12, -0.20):              # the head bone is my neck's top: +4 cm is eye height
        for lat in (0.0, 0.35, 0.7, 1.0):
            for reach_d in (0.34, 0.42):
                c_xy = p_head.lerp(p_shoulder, lat) + fwd * reach_d
                cand = Vector((c_xy.x, c_xy.y, p_head.z + dz))
                a_c = best_alpha(cand, a_lift)
                w_c, q_c = carried(cand, a_c)
                p_c, W_c = achieved(w_c, q_c)
                miss_m, miss_deg = (p_c - w_c).length, math.degrees(W_c.rotation_difference(q_c).angle)
                if miss_m < 0.025 and miss_deg < 8.0:
                    look_at_pt = (cand, a_c, (p_c, W_c), {'lateral': lat, 'below_head_m': -dz, 'forward_m': reach_d,
                                                         'miss_mm': round(1000 * miss_m, 1),
                                                         'miss_deg': round(miss_deg, 1)})
                    break
            if look_at_pt:
                break
        if look_at_pt:
            break
    if look_at_pt is None:                              # nothing within reach: the plan's centred place, as made
        a_c = best_alpha(face_pt, a_lift)
        look_at_pt = (face_pt, a_c, achieved(*carried(face_pt, a_c)), {'lateral': 0.0, 'unreached': True})
    face_pt, a_face, (at_face, turn_face), look_where = look_at_pt
    log(f'[hands] held up to look at: {look_where}')
    down_c = wrist_grasp + Vector((set_down_offset[0], set_down_offset[1], 0.0)) + grip_vec
    a_down = best_alpha(down_c, a_face)
    lift, turn_lift = achieved(*carried(lift_c, a_lift))
    # looking it over: the hand turns the can one way and the other about the FOREARM's line (my wrist's roll stage, +-90:
    # the turn a forearm makes, pronation and supination), not about an axis of the room the wrist cannot follow
    rec_f = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
    reach_through_hardware(rig, rec_f, side, at_face, turn_face, 0.0, None, span_deg=80.0, step_deg=10.0)
    p_el, _W = rig.bone_world(rec_f, side + 'LowerArm')
    p_wr, _W = rig.bone_world(rec_f, side + 'Hand')
    fore = (p_wr - p_el).normalized()

    face_miss = key_miss(at_face, turn_face)

    def look_turn(want_deg):
        """the largest roll toward want_deg (in 5 deg steps) my wrist makes from the face pose about as well as the face
        pose itself, keeping 8 deg from its stops: a turn at a stop is clamped, and the wrist's turn limit then lags the
        plan"""
        sgn = 1.0 if want_deg >= 0 else -1.0
        for a_d in range(int(abs(want_deg)), 4, -5):
            q_k = Quaternion(fore, sgn * a_d * D2R) @ turn_face
            m_k, _margin = key_eval(at_face, q_k)
            if m_k < face_miss + 3.0:
                return q_k, sgn * a_d
        return turn_face, 0.0
    turn_t1, look_a = look_turn(look_over_deg[0])
    turn_t2, look_b = look_turn(look_over_deg[1])
    down, turn_down = carried(down_c, a_down)
    over = down + Vector((0.0, 0.0, 0.10))
    approach_out = Quaternion((0.0, 0.0, 1.0), a_down) @ approach
    log(f'[hands] carried: the prop turned about its own axis {math.degrees(a_lift):.0f} deg at the lift, '
        f'{math.degrees(a_face):.0f} deg before the face, {math.degrees(a_down):.0f} deg when set down; looked over '
        f'with forearm rolls of {look_a:.0f} and {look_b:.0f} deg')
    # the path in and out: from the idle's own hand up over the surface's edge and down to the pre-grasp, and after
    # letting go up off the prop and back to the idle's hand (a straight line from the hip would cut the counter)
    raw_a = rig.place(rig.stand_raw(idle, T['reach'] + dt, dt), root, ground)
    raw_b = rig.place(rig.stand_raw(idle, T['back'] + dt, dt), root, ground)
    rig.clear.reset() if rig.clear is not None else None
    p_a, q_a = rig.bone_world(raw_a, side + 'Hand')
    p_b, q_b = rig.bone_world(raw_b, side + 'Hand')
    sw_a, sw_b = swivel_of(rig, raw_a, side), swivel_of(rig, raw_b, side)
    # the hand stays clear of the surface the prop stands on: from the idle's hand it rises forward, over the surface's
    # height (12 cm over it, a third of the way toward the pre-grasp: a hand raised straight up beside the hip lifts
    # the elbow out like a wing), crosses over the edge, comes down onto the pre-grasp from above; it lets go, backs
    # off the prop, rises past its top, and comes home high beside the hip (25 cm over the surface: a lower way home
    # in the joints swings the fingers down through the prop and the surface)
    p_sh, _W = rig.bone_world(raw0, side + 'UpperArm')
    hi_z = support_z + 0.12
    up_in = p_a.lerp(wrist_pre, 0.33)
    up_in.z = max(hi_z, p_a.z)
    up_out = Vector((p_b.x, p_b.y, max(support_z + 0.25, p_b.z)))
    arc_in = Vector((0.5 * (wrist_pre.x + p_sh.x), 0.5 * (wrist_pre.y + p_sh.y), max(hi_z, wrist_pre.z + 0.08)))
    # letting go: the open hand backs off the prop and a little up (its lowest finger clears the surface), then rises
    # straight up past the prop's top before it swings home (a swing toward the shoulder from beside the prop would
    # sweep the open fingers through it)
    clear_p = down - approach_out * 0.08 + Vector((0.0, 0.0, 0.04))
    arc_out = clear_p + Vector((0.0, 0.0, max(0.16, (lo.z + height + 0.06) - clear_p.z)))
    q_up_in = q_a.slerp(turn if q_a.dot(turn) >= 0 else -turn, 0.5)
    q_up_out = q_b.slerp(turn_down if q_b.dot(turn_down) >= 0 else -turn_down, 0.5)
    keys = [(T['reach'], p_a, q_a), (T['up_in'], up_in, q_up_in), (T['arc_in'], arc_in, turn), (T['pre'], wrist_pre, turn),
            (T['touch'], wrist_grasp, turn), (T['closed'], wrist_grasp, turn), (T['lift'], lift, turn_lift),
            (T['face'], at_face, turn_face), (T['turn_a'], at_face, turn_t1), (T['turn_b'], at_face, turn_t2),
            (T['face2'], at_face, turn_face), (T['over'], over, turn_down), (T['down'], down, turn_down),
            (T['open'], down, turn_down), (T['clear'], clear_p, turn_down), (T['arc_out'], arc_out, turn_down),
            (T['up_out'], up_out, q_up_out), (T['back'], p_b, q_b)]
    # each key's elbow swivel: the grasp's planned one wherever the hand is at the prop, the idle's own at the ends,
    # else the best for the wrist near the last key's (no flip), so the elbow moves as smoothly as the hand
    sw_g = rep_g['swivel']
    swk = []
    for kt, kp, kq in keys:
        if kt == T['reach']:
            swk.append(sw_a)
        elif kt == T['back']:
            swk.append(sw_b)
        elif kt in (T['pre'], T['touch'], T['closed']):
            swk.append(sw_g)
        else:
            rec_k = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
            swk.append(reach(rig, rec_k, side, kp, kq, hint=swk[-1] if swk else sw_g)['swivel'])
    keys = [(kt, kp, kq, sk) for (kt, kp, kq), sk in zip(keys, swk)]
    # THE FREE HAND (to the pre-grasp, and back from the clear): there no prop needs a straight path, and a wrist path
    # through the room crosses where my shoulder's pitch stage must swap its solution (its actuator then lags behind the
    # plan by up to 16 cm). So the arm moves in its own joints there: each key's pose solved once as my hardware makes it
    # (reach_through_hardware, then the arm's pass), the frames between them eased bone by bone, the way a clip moves
    # an arm; the stretch near the prop (the pre-grasp to the grasp, the carry, the set-down, backing off) follows the
    # planned wrist path, which my arm makes there to within millimetres
    ARM4 = (side + 'Shoulder', side + 'UpperArm', side + 'LowerArm', side + 'Hand')
    free_keys = (T['up_in'], T['arc_in'], T['pre'], T['arc_out'], T['up_out'])
    key_pose = {}
    for kt, kp, kq, sk in keys:
        if kt in free_keys:
            rec_k = {'N': dict(raw0['N']), 'off': raw0['off'], 'M': raw0['M']}
            reach_through_hardware(rig, rec_k, side, kp, kq, sk, None, span_deg=60.0, step_deg=5.0)
            Np = arm_preview(rig, rec_k['N'], side)
            key_pose[kt] = {n: Np[n].copy() for n in ARM4}

    def free_pose(t, N_now):
        """the arm's four bones at t in a free stretch (None outside one): eased between the stretch's key poses, the
        clip's own arm at the stretch's open end"""
        for seq in ((T['reach'], T['up_in'], T['arc_in'], T['pre']), (T['arc_out'], T['up_out'], T['back'])):
            if seq[0] <= t < seq[-1]:
                for ta, tb in zip(seq[:-1], seq[1:]):
                    if ta <= t < tb:
                        u = ease((t - ta) / max(1e-6, tb - ta))
                        Pa = key_pose.get(ta) or {n: N_now[n] for n in ARM4}
                        Pb = key_pose.get(tb) or {n: N_now[n] for n in ARM4}
                        out = {}
                        for n in ARM4:
                            qa, qb = Pa[n], Pb[n]
                            if qa.dot(qb) < 0:
                                qa = -qa
                            out[n] = qa.slerp(qb, u)
                        return out
        return None

    def path(t):
        if t <= keys[0][0]:
            return keys[0][1], keys[0][2], keys[0][3]
        for (ta, pa, qa, sa), (tb, pb, qb, sb) in zip(keys[:-1], keys[1:]):
            if t <= tb:
                u = ease((t - ta) / max(1e-6, tb - ta))
                if qa.dot(qb) < 0:
                    qa = -qa
                return pa.lerp(pb, u), qa.slerp(qb, u), sa + (sb - sa) * u
        return keys[-1][1], keys[-1][2], keys[-1][3]
    prop_down = down + (turn_down @ turn.inverted()) @ grip_vec   # the prop's grip point where it is set down
    gz = None                                           # the head's gaze (yaw, pitch, roll) as it turns; None: the clip's
    gv = 0.0                                            # the head's turning speed (rad/s)
    t_where = T['face2'] + 0.25                         # from here my eyes go ahead of the hand to where it sets it down
    look_off, look_ranges = face_look(h) if look_eyes else (None, None)
    eye, eye_w = (0.0, 0.0), {}                         # my eyes' (yaw, pitch down) rad, and their look weights
    tgt = None
    frames = []
    swivels, misses = [], []
    last_sw, rec_prev = None, None
    att_f = rel_f = None
    grasp_hand = None                                   # the hand's (place, turn) on the frame it closed on the prop
    prop_pts = np.array(surf.verts[::max(1, len(surf.verts) // 2000)], dtype=np.float64)   # the prop where it stands
    for i in range(nfr):
        t = i * dt
        f = f0 + i
        raw = rig.place(rig.stand_raw(idle, t + dt, dt), root, ground)
        if rest_feet:
            rig.rest_feet(raw, ground)                  # both feet on the floor (the idle's own floats its right)
        N_idle = dict(raw['N'])
        rec = {'N': dict(N_idle), 'off': raw['off'], 'M': raw['M'], 'stages': raw['stages']}
        planned = False
        if T['reach'] < t < T['back']:
            wt, tq, sw = path(t)
            fp = free_pose(t, N_idle)
            if fp is not None:
                rec['N'].update(fp)                     # the free hand: in the arm's own joints
                last_sw = None
            else:
                if last_sw is None:
                    last_sw = swivel_of(rig, rec_prev, side) if rec_prev is not None else sw
                base_N = dict(rec['N'])
                # at the prop (the pre-grasp to the grasp, the set-down to the hand opening) the hand's turn is the
                # prop's: a degree off there weighs AT_PROP_TURN_W mm, so the elbow swings round to keep it rather than
                # hold its place while the wrist meets a stop (the left hand setting the can down: 4.4 deg off at 2 mm a
                # degree)
                at_prop = T['pre'] <= t <= T['closed'] or T['over'] <= t <= T['open']
                r = reach_through_hardware(rig, rec, side, wt, tq, sw, dt, last=last_sw, span_deg=90.0,
                                           turn_w=AT_PROP_TURN_W if at_prop else 2.0)
                if grasp_hand is not None and T['over'] <= t < T['open']:
                    # SETTING DOWN to contact: the prop rides the hand as my hardware will put it this frame; where
                    # its lowest point would pass into the surface, the hand stops that much higher
                    for _it in range(3):
                        Np = arm_preview(rig, rec['N'], side, dt)
                        p_h, W_h = rig.bone_world({'N': Np, 'off': rec['off'], 'M': rec['M']}, side + 'Hand')
                        R_ = np.array((W_h @ grasp_hand[1].inverted()).to_matrix())
                        low_z = float(((prop_pts - np.array(grasp_hand[0])) @ R_.T + np.array(p_h))[:, 2].min())
                        if low_z >= support_z - 1e-4:
                            break
                        wt = wt + Vector((0.0, 0.0, support_z - low_z))
                        rec['N'] = dict(base_N)
                        r = reach_through_hardware(rig, rec, side, wt, tq, sw, dt, last=last_sw, span_deg=90.0)
                last_sw = r['swivel']
                swivels.append(r['swivel'])
                misses.append((r['miss_mm'], r['miss_deg'], f))
                planned = True
        # the fingers: from the idle's own to open on the way, closing from touch to closed, held, opening from down
        # to open, then back to the idle's (rotation by rotation, the thumb's stages with them)
        if T['reach'] <= t < T['touch']:
            u = ease((t - T['reach']) / (T['arc_in'] - T['reach'])) if t < T['arc_in'] else 1.0
            _hand_toward(hm, rec['N'], N_idle, open_c, u)
        elif T['touch'] <= t < T['down']:
            u = ease((t - T['touch']) / (T['closed'] - T['touch']))
            set_curls(hm, rec['N'], lerp_curls(open_c, closed, u), dof_state=True)
        elif T['down'] <= t < T['clear']:
            # letting go: the fingers open wide (the far side's fingers must clear the prop as the hand backs off)
            u = ease((t - T['down']) / (T['open'] - T['down']))
            set_curls(hm, rec['N'], lerp_curls(closed, release_c, u), dof_state=True)
        elif T['clear'] <= t < T['back']:
            v = ease((t - T['clear']) / (T['back'] - T['clear']))
            _hand_toward(hm, rec['N'], N_idle, release_c, 1.0 - v)
        # the gaze: on the prop while the hand works (where it stands; where the hand carries it, a beat ahead; where
        # it goes once looked over, and where it was set down), else the clip's own head. The head turns from the
        # clip's head (its roll with it) and back onto it at most head_rate (VRMRobotBody's head actuator), speeding up
        # and slowing down at head_accel, so it never jumps a frame
        own = _clip_gaze(rec['N'])
        tgt_g = own
        if look_at_it and T['reach'] <= t < T['back']:
            if t < T['closed']:
                tgt = axis + Vector((0.0, 0.0, grip_z))
            elif t < t_where:                           # the prop where the hand carries it (rigid with the hand)
                pw, pq, _s = path(min(t + gaze_lead, t_where))
                tgt = pw + (pq @ turn.inverted()) @ grip_vec
            else:                                       # where it goes, and where it was set down
                tgt = prop_down
            tgt_g = _gaze_to(rig, rec, tgt, heading) + (0.0,)
        cur = own if gz is None else gz
        d = [b_ - a_ for a_, b_ in zip(cur, tgt_g)]
        dist = math.sqrt(sum(x * x for x in d))
        gv = clamp(min(head_rate, math.sqrt(2.0 * head_accel * dist)), gv - head_accel * dt, gv + head_accel * dt)
        stp = min(dist, gv * dt)
        gz = tuple(a_ + x * stp / dist for a_, x in zip(cur, d)) if dist > 1e-9 else tuple(tgt_g)
        if tgt_g is own and dist < 0.25 * D2R:
            gz, gv = None, 0.0                          # back on the clip's own head (its bobble with it)
        gaze = gz
        w = dict(face(t)) if face else {}
        w.update(eye_w)                                 # the look the crown leans into: last frame's (the JS's applyCrown
        #                                                 reads what vrm.update's look-at set the frame before)
        crown_state = 'curious' if T['lift'] <= t < T['over'] else None
        out = rig.finish(rec, dt, w, gaze, crown_state, None, state_weight=0.8)
        out['M'] = rec['M']
        out['f'] = f
        out['t'] = t
        # MY EYES (the face's look expressions) take what my head's stops and its speed leave: from my face's look
        # origin as the head now is, they hold the target while the head turns and look the rest of the way down where
        # my neck's nod stops at 30 deg (the counter's top is 45-50 deg under my eyes), at most eye_rate
        if look_ranges is not None:
            e_t = (0.0, 0.0)
            if look_at_it and T['reach'] <= t < T['back']:
                ya, pa = _eye_angles(rig, out, tgt, look_off)
                e_t = (clamp(ya, -look_ranges['horizontal'] * D2R, look_ranges['horizontal'] * D2R),
                       clamp(pa, -look_ranges['up'] * D2R, look_ranges['down'] * D2R))
            de = (e_t[0] - eye[0], e_t[1] - eye[1])
            dl = math.hypot(*de)
            s_e = min(1.0, eye_rate * dt / dl) if dl > 1e-9 else 0.0
            eye = (eye[0] + de[0] * s_e, eye[1] + de[1] * s_e)
            eye_w = look_expression_weights(eye[0] * R2D, eye[1] * R2D, look_ranges)
            out['weights'].update(eye_w)
            out['eye_deg'] = (eye[0] * R2D, eye[1] * R2D)
        if planned:
            out['hand_target'] = (wt.copy(), tq.copy())     # the planned wrist and hand turn (the checks' reference)
        frames.append(out)
        rec_prev = {'N': dict(out['N']), 'off': out['off'], 'M': out['M']}
        if att_f is None and t >= T['closed']:
            att_f = f
            grasp_hand = rig.bone_world(out, side + 'Hand')
        if rel_f is None and t >= T['open'] - 0.2:
            rel_f = f
    act = key_robot(h, frames, action_name or f'{h.name}|pick_and_hold')
    fr_face = key_face_track(h, face_track(frames)) if (face or look_ranges is not None) else {}
    # the prop rides the hand from the frame it closes to the frame it lets go
    sc.frame_set(att_f)
    pb = h.arm.pose.bones[h.humanoid[side + 'Hand']]
    con = obj.constraints.new('CHILD_OF')
    con.name = 'held_in_' + side + '_hand'
    con.target = h.arm
    con.subtarget = pb.name
    Mh = h.arm.matrix_world @ pb.matrix
    con.inverse_matrix = Mh.inverted()
    _key_influence(con, [(f0, 0.0), (att_f, 1.0), (rel_f, 0.0)])
    sc.frame_set(rel_f - 1)
    Mh2 = h.arm.matrix_world @ pb.matrix
    M_rel = Mh2 @ Mh.inverted() @ M_obj0
    # let go, it settles onto the surface under it: a prop the hand set down within a few degrees and millimetres of
    # standing tips upright onto its base over the next frames (its base's centre kept where it was, on the surface)
    bb = [Vector(c) for c in obj.bound_box]
    c_loc = Vector(((min(c.x for c in bb) + max(c.x for c in bb)) / 2, (min(c.y for c in bb) + max(c.y for c in bb)) / 2,
                    min(c.z for c in bb)))
    loc_r, rot_r, sca_r = M_rel.decompose()
    up = rot_r @ Vector((0.0, 0.0, 1.0))
    tilt = math.degrees(up.angle(Vector((0.0, 0.0, 1.0))))
    b = M_rel @ c_loc
    low = min((M_rel @ Vector(c)).z for c in obj.bound_box)
    settle = support_z - low
    keys_obj = [(f0, M_obj0, 'CONSTANT'), (rel_f, M_rel, 'LINEAR')]
    settled = None
    if tilt < 8.0 and abs(settle) < 0.01:
        rot_s = up.rotation_difference(Vector((0.0, 0.0, 1.0))) @ rot_r
        R3 = rot_s.to_matrix().to_4x4()
        S4 = Matrix.Diagonal((sca_r[0], sca_r[1], sca_r[2], 1.0))
        p = Vector((b.x, b.y, support_z)) - (R3 @ S4 @ c_loc.to_4d()).to_3d()
        settled = Matrix.Translation(p) @ R3 @ S4
        keys_obj.append((rel_f + 3, settled, 'CONSTANT'))
    obj.rotation_mode = 'QUATERNION'
    _key_object(obj, keys_obj)
    return {'frames': [f0, f0 + nfr - 1], 'times': T, 'attach_frame': att_f, 'release_frame': rel_f, 'grasp': rep_g,
            'settle_mm': round(1000 * settle, 3), 'settle_tilt_deg': round(tilt, 3), 'settled': settled is not None,
            'held_up_at': look_where,
            'hardware_miss': {'wrist_mm_max': round(max(m[0] for m in misses), 2) if misses else None,
                              'turn_deg_max': round(max(m[1] for m in misses), 2) if misses else None,
                              'at_frame': max(misses)[2] if misses else None},
            'clearance_mm': {k: round(v * 1000, 2) for k, v in clear.items()},
            'curls_deg': {k: [round(x * R2D, 1) for x in v] for k, v in closed.items()}, 'action': act, 'face': fr_face,
            'prop': {'axis': list(axis), 'radius': radius, 'height': height}, 'wrist_grasp': list(wrist_grasp),
            'turn': list(turn), 'hand_model': hm, '_frames': frames, 'surface': surf}


def _hand_toward(hm, N, N_idle, curls, u):
    """the hand's fingers and thumb turned from the idle's own pose toward `curls`, by u (each link slerped)"""
    tgt = dict(N_idle)
    set_curls(hm, tgt, curls)
    side = hm.side
    for f in FINGERS + ('Thumb',):
        names = [side + f + k for k in LINKS] if f != 'Thumb' else [side + k for k in THUMB]
        for n in names:
            if n in tgt and n in N_idle:
                qa, qb = N_idle[n], tgt[n]
                if qa.dot(qb) < 0:
                    qa = -qa
                N[n] = qa.slerp(qb, u)


def _clip_gaze(N):
    """the clip's own head as a gaze (yaw, pitch, roll): the neck's and the head's turns composed and read in
    RobotRig.apply_gaze's YXZ Euler (its inverse; rehomeBody already split them so), so a gaze that starts from the
    clip's head or ends on it does not jump"""
    q = q_to_three(N['neck']) @ q_to_three(N['head']) if 'neck' in N else q_to_three(N['head'])
    x, y, z = euler_from_quat(q, 'YXZ')
    return y, x, z


def face_look(h):
    """my face's look origin from the head bone (VRMC_vrm.lookAt offsetFromHeadBone, Blender's axes) and its look
    expressions' ranges (deg: horizontal, down, up), or (None, None) for a VRM whose look-at turns eye bones"""
    from ..vrm import glb_json
    try:
        la = glb_json(h.path).get('extensions', {}).get('VRMC_vrm', {}).get('lookAt') or {}
    except Exception:  # noqa: BLE001
        la = {}
    if la.get('type') != 'expression':
        return None, None

    def rng(k, d):
        return float((la.get(k) or {}).get('inputMaxValue', d))
    return (v_from_three(Vector(la.get('offsetFromHeadBone', (0.0, 0.06, 0.0)))),
            {'horizontal': rng('rangeMapHorizontalOuter', 90.0), 'down': rng('rangeMapVerticalDown', 90.0),
             'up': rng('rangeMapVerticalUp', 90.0)})


def look_expression_weights(yaw_deg, down_deg, ranges):
    """the face's look expressions for an eye turn (yaw + toward my left, pitch + down, deg) over its ranges"""
    return {'lookLeft': clamp(yaw_deg / ranges['horizontal'], 0.0, 1.0),
            'lookRight': clamp(-yaw_deg / ranges['horizontal'], 0.0, 1.0),
            'lookDown': clamp(down_deg / ranges['down'], 0.0, 1.0),
            'lookUp': clamp(-down_deg / ranges['up'], 0.0, 1.0)}


def look_expression_angles(w, ranges):
    """look_expression_weights' inverse: (yaw, pitch down) deg from the weights"""
    return ((w.get('lookLeft', 0.0) - w.get('lookRight', 0.0)) * ranges['horizontal'],
            w.get('lookDown', 0.0) * ranges['down'] - w.get('lookUp', 0.0) * ranges['up'])


def eye_ray(rig, rec, look_off, yaw_deg=0.0, down_deg=0.0):
    """(origin, direction) of my gaze in the world: from the face's look origin, the head as it is in rec, the eyes
    turned (yaw + toward my left, pitch + down, deg) in the head's frame (it faces -Y at rest, +Z up)"""
    p, W = rig.bone_world(rec, 'head')
    y, d = yaw_deg * D2R, down_deg * D2R
    return p + W @ look_off, W @ Vector((math.sin(y) * math.cos(d), -math.cos(y) * math.cos(d), -math.sin(d)))


def _eye_angles(rig, rec, target, look_off):
    """the (yaw, pitch down) rad of a world point from my face's look origin, in my head's frame as it is in rec"""
    p, W = rig.bone_world(rec, 'head')
    d = W.inverted() @ (target - (p + W @ look_off))
    return math.atan2(d.x, -d.y), math.atan2(-d.z, math.hypot(d.x, d.y))


def _gaze_to(rig, rec, target, heading):
    """the head's (yaw, pitch) toward a world point from where the head is (VRMRobotBody's look_at maths)"""
    p, _W = rig.bone_world(rec, 'head')
    d = target - p
    f = Vector((math.sin(heading), -math.cos(heading)))
    left = Vector((-f.y, f.x))
    lz = d.x * f.x + d.y * f.y
    lx = d.x * left.x + d.y * left.y
    yaw = clamp(math.atan2(lx, lz), -math.pi / 3, math.pi / 3)
    pitch = clamp(-math.atan2(d.z, math.hypot(lx, lz)), -math.pi / 6, math.pi / 6)
    return yaw, pitch


def _key_influence(con, keys):
    for f, v in keys:
        con.influence = v
        con.keyframe_insert('influence', frame=f)
    ad = con.id_data.animation_data
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in cb.fcurves:
        if fc.data_path.endswith('influence'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def _key_object(obj, keys):
    """the object's own transform keyed: [(frame, matrix, interpolation from that key on)]"""
    prev = None
    for f, M, _i in keys:
        loc, rot, _s = M.decompose()
        if prev is not None and prev.dot(rot) < 0:
            rot.negate()                                 # the short way round between keys
        prev = rot
        obj.location = loc
        obj.rotation_quaternion = rot
        obj.keyframe_insert('location', frame=f)
        obj.keyframe_insert('rotation_quaternion', frame=f)
    ad = obj.animation_data
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    how = {f: i for f, _M, i in keys}
    for fc in cb.fcurves:
        if fc.data_path in ('location', 'rotation_quaternion'):
            for kp in fc.keyframe_points:
                kp.interpolation = how.get(int(round(kp.co[0])), 'CONSTANT')
