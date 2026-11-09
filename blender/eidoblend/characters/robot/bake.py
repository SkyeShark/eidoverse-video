"""eidoblend.characters.robot.bake: a run the legs recorded (RobotLegs.record), keyed through my body's passes.

    rep = legs.bake(f0=1, face=lambda t: {'happy': 0.5})       # RobotLegs.bake / EidoverseRobotController.bake call this

The record is one entry per frame the controller stepped: its state (idle, walk, run, emote, seated), the body's place
and facing, the clip an emote or a seat plays, the gaze VRMRobotBody set. It becomes SPANS: standing (one clip: the idle,
an emote, a seated clip) and walking (the frames the body travelled; a standing gap shorter than min_stand frames
between two walks, such as the frame the adapter spends on reaching each waypoint, is walked through). Then, frame by
frame in film order:

  STANDING   the span's clip through the example's frame order at the body's place (eidoblend.characters.robot.rig:
             stand_raw, then finish), set down onto the ground. The idle's clip time runs on with the film, so every idle
             span continues the same breathing; an emote plays from its start and holds its end. A new clip where the
             body stands crossfades in with each foot held where it stands, moved only as the clip moves its own foot
  TURNING    a standing span at another heading than the last (face_direction; an emote aimed by set_emote_facing, and
             back after it): the body steps round on the spot, at most 45 deg a step, the foot on the side it turns
             toward first, each foot lifted and set down where the clip puts it at the step's heading while the other
             stays planted (turn_plan / _turn_frame); a turn longer than its span runs the film on
  WALKING    round one's walk_path (planted feet, the stance's rockers, the swing's clearance, the corner arcs) along the
             route the body travelled, at its speed, then finish() (the hands' pins and the thumb's rotor, which the walk
             does not clamp; the wrists' stages; the gaze; the head and the crown on their actuators' rates)
  STARTING   a walk begins with its left foot at mid-stance (under the hips, as a standing foot is), the whole walk moved
             so that foot lands on the standing left foot; over `fade` frames the pose crossfades from the standing one
             with that foot held where it stands (two-bone IK on the blend) and the right foot lifting into its swing
  STOPPING   a walk followed by standing ends at the mid-stance nearest the place the body stopped (the route is run on
             `extend` m past it so that stance can lie a little beyond, over the goal's own level only: by an edge the
             stop stands back from it); the standing span is placed so its clip's foot on that side lands on the walk's
             planted one, and over `fade` frames the other foot comes down beside it
  MOVES      a maneuver (vault, jump, climb_ledge, climb_ladder: RobotLegs._start_maneuver) is the controller family's
             move played again from where the keyed body stands, my feet stepping to its stance over `fade` frames,
             its planted frames through my passes after
The stateful passes (the wrists' turn limit, the shoulders' pitch rate, the thumbs, the head, the crown) run exactly once
per film frame. A walk's frame count is walk_path's for the route (its average speed is the body's): the film runs on
from where it ends, so later spans may land a frame or two from the frames the live run stepped them on (report['map']).
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from .. import robot_dof as dof
from .._math import ease, q_from_three, q_to_three
from ..ground import SIDES, Ground
from ..locomotion import Body, analyze_clip, walk_path
from ..performance import key_face_track
from ..vrma import load_clip
from .rig import face_track, key_robot

UP = Vector((0.0, 0.0, 1.0))


def _segments(rec, min_stand):
    """the record's frames as spans [{'kind': 'stand' | 'walk' | 'maneuver', 'a', 'b', 'clip'}] (b exclusive; a
    maneuver span is one move, 'clip' its index in the legs' _maneuvers)"""
    kind = [('walk' if r['state'] in ('walk', 'run') else
             (('maneuver', r['maneuver']) if r['state'] == 'maneuver' else 'stand')) for r in rec]
    runs = []
    for i, k in enumerate(kind):
        if runs and runs[-1][0] == k:
            runs[-1][2] = i + 1
        else:
            runs.append([k, i, i + 1])
    # a short standing gap between two walks is walked through
    merged = []
    for j, r in enumerate(runs):
        if (r[0] == 'stand' and 0 < j < len(runs) - 1 and runs[j - 1][0] == 'walk' and runs[j + 1][0] == 'walk'
                and r[2] - r[1] < min_stand and all(rec[i]['state'] == 'idle' for i in range(r[1], r[2]))):
            r = ['walk', r[1], r[2]]
        if merged and merged[-1][0] == r[0]:
            merged[-1][2] = r[2]
        else:
            merged.append(list(r))
    spans = []
    for k, a, b in merged:
        if k == 'walk':
            spans.append({'kind': 'walk', 'a': a, 'b': b, 'clip': None})
            continue
        if isinstance(k, tuple):
            spans.append({'kind': 'maneuver', 'a': a, 'b': b, 'clip': k[1]})
            continue
        # a standing run split by its clip (the idle, an emote, a seated clip)
        cur = None
        for i in range(a, b):
            c = rec[i].get('clip') or None
            if cur is None or cur['clip'] != c or abs(rec[i]['heading'] - rec[cur['a']]['heading']) > 0.02:
                cur = {'kind': 'stand', 'a': i, 'b': i + 1, 'clip': c}
                spans.append(cur)
            else:
                cur['b'] = i + 1
    return spans


EDGE_REACH = 0.4    # how far ahead of my root my standing feet reach (a stop's leading foot and its toes), m
JOIN_DEG = 15.0     # a walk that starts off the live run's line joins it at most this steeply, deg


def _level_run_on(ground, p, d, extend, step=0.05, toe=0.45, rise=0.04, look=1.0):
    """how far (m, up to `extend`) a walk's route may run on past its goal p along d over the goal's own level: it stops
    `toe` short of the first ground more than `rise` above or below it (a drop, a ditch, a step, a wall's foot: walk_path
    plants the leading foot up to a step and a toe ahead of the route's end, and a foot planted over the edge drags its
    pelvis, smoothed over the stances, toward that ground) -> (the run-on, the edge's distance from p (inf: level for
    `look` m on)). Near an edge the walk may so stop up to a step short of its goal: on the safe side"""
    g0 = float(ground.h(np.array([p[0]]), np.array([p[1]]))[0])
    n = int(round(max(extend + toe, look) / step))
    for k in range(1, n + 1):
        s = k * step
        g = float(ground.h(np.array([p[0] + s * d.x]), np.array([p[1] + s * d.y]))[0])
        if abs(g - g0) > rise:
            return max(0.0, min(extend, s - step - toe)), s - step
    return extend, math.inf


def _place(x, y, z, heading):
    return Matrix.Translation(Vector((x, y, z))) @ Quaternion((0.0, 0.0, 1.0), heading).to_matrix().to_4x4()


def _aim(target, head, heading):
    """robot_body.js's _updateHeadTargetFromLookAt, unclamped: the (yaw, pitch) that faces `target` from `head` for a
    body facing `heading` (yaw + toward the body's left, pitch + looking down)"""
    d = Vector(target) - Vector(head)
    f = Vector((math.sin(heading), -math.cos(heading)))
    lz = d.x * f.x + d.y * f.y
    lx = d.x * -f.y + d.y * f.x
    return math.atan2(lx, lz), -math.atan2(d.z, math.hypot(lx, lz))


def _aimed_gaze(rig, raw, r):
    """the gaze a frame recorded live, re-aimed for the keyed body: the JS aims the head at a look-at target from the
    head and the heading it renders, and the keyed body can stand a little off the live run (a walk's stop on a
    mid-stance at the goal where the live run stopped within arrive_radius; a stand placed on the walk's planted foot).
    The aim's change from the live head and heading to the keyed ones is added to the live gaze (its rate-limited turn
    kept), clamped at the body's limits. A frame without a look-at target (a scan, the neutral head) is the live gaze"""
    g, lk = r.get('gaze'), r.get('look')
    if g is None or lk is None or raw.get('M') is None:
        return g
    target, head0, h0, ylim, plim = lk
    head1, _W = rig.bone_world(raw, 'head')
    q = raw['M'].to_quaternion()
    y0, p0 = _aim(target, head0, h0)
    y1, p1 = _aim(target, head1, 2.0 * math.atan2(q.z, q.w))
    yaw = g[0] + math.remainder(y1 - y0, 2 * math.pi)
    pitch = g[1] + (p1 - p0)
    return (max(-ylim, min(ylim, yaw)), max(-plim, min(plim, pitch)))


def _sole_xy(rig, rec, side):
    P = rig.feet_world(rec)[side]
    return P, Vector((float(P[:, 0].mean()), float(P[:, 1].mean()), 0.0))


def _fk_feet(rig, rec):
    body = rig.body
    ph, Wh = body.hips(rec['M'], rec['off'], rec['N'])
    return {s: body.leg_fk(s, ph, Wh, rec['N']) for s in SIDES}


def _solve_feet(rig, N, off, M, targets, ground, keep_up=None):
    """N's legs solved so each listed foot's ankle and turn are its target ((T, W) world), clamped as the hardware is,
    the hips' stages solved; `keep_up`: a side whose foot is lifted back over its ground if the solve sank it"""
    body = rig.body
    ph, Wh = body.hips(M, off, N)
    for s, (T, W) in targets.items():
        body.solve_leg(s, ph, Wh, N, T, W, swivel=1.0)
    if rig.legs is not None:
        p3 = {n: q_to_three(q) for n, q in N.items()}
        dof.apply_hardware_dof(p3, dof.LEG_JOINTS, rig.legs)
        stages = {s: {k: q_from_three(v) for k, v in o.items()} for s, o in rig.legs.out.items() if o}
        rec = {'N': {n: q_from_three(q) for n, q in p3.items()}, 'off': off, 'M': M, 'stages': stages}
    else:                                            # a plain rig (any VRM but my body): the legs as the IK solved them
        rec = {'N': dict(N), 'off': off, 'M': M, 'stages': {}}
    if keep_up is not None:
        P = rig.feet_world(rec)[keep_up]
        gap = float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1])))
        if gap < 0:
            T, W = targets[keep_up]
            return _solve_feet(rig, dict(rec['N']), off, M, {keep_up: (T + UP * (-gap), W)}, ground)
    return rec


def _blend(rig, A, B, u, pin, pin_from, ground, lift=0.05):
    """a pose between two placed records A -> B at u: every rotation slerped, the root and the hips' offset lerped; then
    the feet: pin a side ('left' / 'right': its ankle and foot held as `pin_from` (A or B) has them, the other eased
    from A's to B's and lifted by up to `lift` m on the way, never below its ground), 'both' (both held as A has them:
    a standing body changing clips) or None (both eased, no lift: a standing body turning round)"""
    N = {}
    for n, qb in B['N'].items():
        qa = A['N'].get(n, qb)
        if qa.dot(qb) < 0:
            qa = -qa
        N[n] = qa.slerp(qb, u)
    off = A['off'].lerp(B['off'], u)
    la, ra, _s = A['M'].decompose()
    lb, rb, _s = B['M'].decompose()
    if ra.dot(rb) < 0:
        ra = -ra
    M = Matrix.Translation(la.lerp(lb, u)) @ ra.slerp(rb, u).to_matrix().to_4x4()
    FA, FB = _fk_feet(rig, A), _fk_feet(rig, B)
    targets = {}
    for s in SIDES:
        fa, fb = FA[s], FB[s]
        if pin == 'both' or s == pin:
            src = fa if (pin == 'both' or pin_from is A) else fb
            targets[s] = (src['p_an'].copy(), src['W_ft'].copy())
            continue
        wa, wb = fa['W_ft'], fb['W_ft']
        if wa.dot(wb) < 0:
            wa = -wa
        T = fa['p_an'].lerp(fb['p_an'], ease(u))
        if pin is not None:
            T = T + UP * (lift * math.sin(math.pi * u))
        targets[s] = (T, wa.slerp(wb, ease(u)))
    other = None if pin in (None, 'both') else ('right' if pin == 'left' else 'left')
    return _solve_feet(rig, N, off, M, targets, ground, keep_up=other)


def _step_in(rig, A, B, j, n, ground, lift=0.035, state=None):
    """frame j of n of a hand-over from my standing record A to another solver's standing start B (a move's first
    frames) whose feet stand elsewhere: the pose crossfades A -> B over the n frames, and the feet STEP from A's places
    to B's, one at a time (the one with farther to go first, the other planted), each lifted up to `lift` on its way;
    a foot within 1 cm of its place stays put. state: {} on the first call (the order is chosen there)"""
    u = (j + 1) / (n + 1)
    N = {}
    for nm, qb in B['N'].items():
        qa = A['N'].get(nm, qb)
        if qa.dot(qb) < 0:
            qa = -qa
        N[nm] = qa.slerp(qb, u)
    off = A['off'].lerp(B['off'], u)
    la, ra, _s = A['M'].decompose()
    lb, rb, _s = B['M'].decompose()
    if ra.dot(rb) < 0:
        ra = -ra
    M = Matrix.Translation(la.lerp(lb, u)) @ ra.slerp(rb, u).to_matrix().to_4x4()
    FA, FB = _fk_feet(rig, A), _fk_feet(rig, B)
    if state is not None and 'order' not in state:
        far = {s: (FB[s]['p_an'] - FA[s]['p_an']).length for s in SIDES}
        state['order'] = [s for s in sorted(SIDES, key=lambda s_: -far[s_]) if far[s] > 0.01]
        state['far'] = far
    order = state['order'] if state is not None else list(SIDES)
    half = max(1, n // max(1, len(order))) if order else n
    targets = {}
    moving = None
    for s in SIDES:
        fa, fb = FA[s], FB[s]
        wa, wb = fa['W_ft'], fb['W_ft']
        if wa.dot(wb) < 0:
            wa = -wa
        if s not in order:
            targets[s] = (fa['p_an'].copy(), fa['W_ft'].copy())
            continue
        k0 = order.index(s) * half
        v = min(1.0, max(0.0, (j + 1 - k0) / float(half)))
        T = fa['p_an'].lerp(fb['p_an'], ease(v)) + UP * (lift * math.sin(math.pi * v))
        if 0.0 < v < 1.0:
            moving = s
        targets[s] = (T, wa.slerp(wb, ease(v)))
    return _solve_feet(rig, N, off, M, targets, ground, keep_up=moving)


def _inside_depth(bvh, p):
    """how far p is inside the closed solids of bvh (m, 0 outside) and the face's outward normal there: the nearest
    face's side, then an upward ray's crossings to tell a point inside from one beside a concave corner"""
    q, n, _i, d = bvh.find_nearest(p)
    if q is None or (p - q).dot(n) >= 0:
        return 0.0, None
    hits, o = 0, p.copy()
    for _ in range(16):
        h = bvh.ray_cast(o, UP, 50.0)
        if h[0] is None:
            break
        hits += 1
        o = h[0] + UP * 1e-4
    return (d, n) if hits % 2 == 1 else (0.0, None)


def _feet_out_of_solids(rig, rec, bvh, ground, tol=0.003, rounds=6, report=None):
    """a move's frame with each foot that is inside a solid (a climb's foot in the face it climbs) pushed out along that
    face's normal until its deepest sole point is on it, the leg re-solved and clamped (the other foot as it is); what
    the leg cannot reach after `rounds - 1` tries moves the whole body out instead -> rec (unchanged when nothing is
    inside). report: {'max_in_m': the deepest before the push, 'body_moved_m': the largest body move}"""
    out = rec
    for _r in range(rounds):
        soles = rig.feet_world(out)
        push = {}
        for s, P in soles.items():
            best = (0.0, None)
            for p in P[::2]:
                d, n = _inside_depth(bvh, Vector(p))
                if d > best[0]:
                    best = (d, n)
            if best[0] > tol:
                push[s] = best[1] * (best[0] + 0.002)
                if report is not None and _r == 0:
                    report['max_in_m'] = max(report.get('max_in_m', 0.0), best[0])
        if not push:
            return out
        if _r == rounds - 1:
            # the leg cannot take the foot out by itself (the move holds my hips too close to the face): the whole body
            # moves out along the face by what is left, its hands with it
            v = max(push.values(), key=lambda p_: p_.length)
            if report is not None:
                report['body_moved_m'] = max(report.get('body_moved_m', 0.0), v.length)
            out = dict(out, M=Matrix.Translation(v) @ out['M'])
            return out
        F = _fk_feet(rig, out)
        targets = {s: ((F[s]['p_an'] + push[s]) if s in push else F[s]['p_an'].copy(), F[s]['W_ft'].copy())
                   for s in SIDES}
        out = dict(out, **_solve_feet(rig, dict(out['N']), out['off'], out['M'], targets, ground))
    return out


def _settle(rig, A, B, v, ground):
    """B's pose with both feet eased from where A has them to B's own (v 0 -> 1): after a standing hand-over"""
    FA, FB = _fk_feet(rig, A), _fk_feet(rig, B)
    targets = {}
    for s in SIDES:
        wa, wb = FA[s]['W_ft'], FB[s]['W_ft']
        if wa.dot(wb) < 0:
            wa = -wa
        targets[s] = (FA[s]['p_an'].lerp(FB[s]['p_an'], ease(v)), wa.slerp(wb, ease(v)))
    return _solve_feet(rig, dict(B['N']), B['off'], B['M'], targets, ground)


LIFT = 0.025        # a standing clip's foot whose lowest point is this far over the ground is stepping, not planted (a
                    # relaxed foot hovers up to 11 mm in the stock idle on my legs: RobotRig.rest_feet's reach)


def _hold_follow(rig, held, raw, u, ground, state, settle=False):
    """a new standing clip where the body stands: the pose crossfades from `held` (the last frame before) to the clip's
    (u 0 -> 1), and each foot is PLANTED where it stands while the clip's own foot is down (its own slide on the floor is
    not passed on), and carried as the clip carries it while the clip lifts it (over LIFT), landing where that motion
    takes it: a planted foot stays put through a wave or a salute, and a clip that steps or sits on the ground moves
    its feet as it does. state: per side {'anchor': (p, W) where the foot is held, 'ref': (p, W) the clip's foot when
    the hold began}, made on the first call"""
    FR = _fk_feet(rig, raw)
    if not state:
        FH = _fk_feet(rig, held)
        for s in SIDES:
            state[s] = {'anchor': (FH[s]['p_an'].copy(), FH[s]['W_ft'].copy()),
                        'ref': (FR[s]['p_an'].copy(), FR[s]['W_ft'].copy()), 'up': False}
    soles = rig.feet_world(raw)
    targets = {}
    for s in SIDES:
        st = state[s]
        P = soles[s]
        up = float(np.min(P[:, 2] - ground.h(P[:, 0], P[:, 1]))) > LIFT
        dp = FR[s]['p_an'] - st['ref'][0]
        dW = FR[s]['W_ft'] @ st['ref'][1].inverted()
        p_t, W_t = st['anchor'][0] + dp, dW @ st['anchor'][1]
        if not up:
            if st['up']:
                st['anchor'] = (p_t.copy(), W_t.copy())        # it landed where the clip's step took it
            p_t, W_t = st['anchor']
            st['ref'] = (FR[s]['p_an'].copy(), FR[s]['W_ft'].copy())   # the clip's own slide while down: not passed on
        st['up'] = up
        targets[s] = (p_t.copy(), W_t.copy())
    N = {}
    for n, qb in raw['N'].items():
        qa = held['N'].get(n, qb)
        if qa.dot(qb) < 0:
            qa = -qa
        N[n] = qa.slerp(qb, u)
    la, ra, _s = held['M'].decompose()
    lb, rb, _s = raw['M'].decompose()
    if ra.dot(rb) < 0:
        ra = -ra
    M = Matrix.Translation(la.lerp(lb, u)) @ ra.slerp(rb, u).to_matrix().to_4x4()
    out = _solve_feet(rig, N, held['off'].lerp(raw['off'], u), M, targets, ground)
    if settle:
        # the hardware clamp after the solve can tip a planted sole a few mm off the floor: settled back down (a
        # stepping foot is over LIFT, past rest_feet's reach, and left alone)
        rig.rest_feet(out, ground)
    return out


TURN_STEP = math.radians(45.0)     # a standing turn steps at most this far at a time
TURN_PHASE_S = 0.25                # each foot's step of it, s
TURN_LIFT = 0.04                   # a stepping foot's lift, m


def turn_plan(h0, h1, fps):
    """a standing turn from heading h0 to h1 (rad): steps of at most TURN_STEP, each the leading foot then the
    trailing one -> {'theta', 'steps', 'n_phase', 'frames', 'lead'}"""
    th = math.remainder(h1 - h0, 2 * math.pi)
    steps = max(1, int(math.ceil(abs(th) / TURN_STEP - 1e-9)))
    n_phase = max(4, int(round(TURN_PHASE_S * fps)))
    return {'h0': h0, 'theta': th, 'steps': steps, 'n_phase': n_phase, 'frames': 2 * steps * n_phase,
            'lead': 'left' if th > 0 else 'right'}


def _turn_frame(rig, raw, xyz, plan, k, planted, ground):
    """frame k of a standing turn on the spot (the body's own feet stepping it round, never sliding): the root turns
    about its place; in each step the leading foot (the side turned toward) lifts and sets down where the clip puts it at
    the step's heading while the other stays planted, then the trailing foot follows. `planted` {side: (p_an, W_ft)} is
    the feet's places at the phase's start, updated in place at each phase's end -> the placed record"""
    n = plan['n_phase']
    p, kk = divmod(k, n)
    j, sub = divmod(p, 2)
    u = (kk + 1) / n
    th, st = plan['theta'], plan['steps']
    hA = plan['h0'] + th * j / st
    hB = plan['h0'] + th * (j + 1) / st
    hh = hA + (hB - hA) * (0.5 * sub + 0.5 * ease(u))
    x, y, z = xyz
    rec = rig.place({'N': dict(raw['N']), 'off': raw['off'].copy(), 'stages': raw.get('stages')},
                    _place(x, y, z, hh), ground)
    end = rig.place({'N': dict(raw['N']), 'off': raw['off'].copy(), 'stages': raw.get('stages')},
                    _place(x, y, z, hB), ground)
    rig.rest_feet(end, ground)                       # where each foot lands: on the floor
    FB = _fk_feet(rig, end)
    lead = plan['lead']
    moving = lead if sub == 0 else ('right' if lead == 'left' else 'left')
    targets = {}
    for s in SIDES:
        p0, W0 = planted[s]
        if s != moving:
            targets[s] = (p0.copy(), W0.copy())
            continue
        W1 = FB[s]['W_ft']
        if W0.dot(W1) < 0:
            W1 = -W1
        e = ease(u)
        targets[s] = (p0.lerp(FB[s]['p_an'], e) + UP * (TURN_LIFT * math.sin(math.pi * u)), W0.slerp(W1, e))
    out = _solve_feet(rig, rec['N'], rec['off'], rec['M'], targets, ground,
                      keep_up=moving if 0.0 < u < 1.0 else None)
    if kk == n - 1:
        planted[moving] = (FB[moving]['p_an'].copy(), FB[moving]['W_ft'].copy())
    return out


def controller_run(legs, pts, speed, heading0, z0, log=print):
    """a run along pts (the route the body ran, from where it stood) through the controller family's
    VRMCharacterController (eidoblend.characters.controller: the WebGPU engine's gait tree with the run clip's flight,
    its acceleration from standing and its stop on the point, its planted feet), on the same collision meshes ->
    (frames {'N', 'off', 'M', 'stages', ...} in Blender's axes, its report). Round one's walk_path is a planted-feet WALK
    and cannot play the run clip (it finds no stance in it: 9 % of the cycle on my body)"""
    from ..controller import CollisionWorld as ControllerWorld, Locomotion
    objs = [bpy.data.objects[n] for n in (legs.world.names if legs.world is not None else []) if n in bpy.data.objects]
    world = ControllerWorld(objs) if objs else ControllerWorld()
    loco = Locomotion(legs.h, world, start=(pts[0][0], pts[0][1], z0), heading=heading0, log=lambda *a: None)
    loco.follow_path([tuple(p) for p in pts[1:]], gait='run', speed=speed)
    crep = loco.bake(f0=1, key=False)
    frames = [{'N': fr['N'], 'off': fr['off'], 'M': fr['M'], 'stages': fr.get('stages') or {}} for fr in crep['_frames']]
    rep = {'gait': 'run (the controller family)', 'speed': speed, 'native_run_mps': round(loco.native['run'], 3),
           'worst': crep.get('worst', {}), 'flight_frames': len(crep.get('flight', [])),
           'segments': [{k: v for k, v in s.items() if k in ('gait', 'frames', 'checks_feet', 'waived')}
                        for s in crep.get('segments', [])], 'path_m': float(sum(
                            math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:])))}
    log(f'[robot bake] a run of {rep["path_m"]:.2f} m through the controller family: {len(frames)} frames, '
        f'{rep["flight_frames"]} in flight')
    return frames, rep


def _foot_rel(rig, rec, side):
    """a foot's sole centre against the record's root, in the root's own frame (x across, y the armature's: -y forward)"""
    _P, c = _sole_xy(rig, rec, side)
    loc, rot, _s = rec['M'].decompose()
    return rot.inverted() @ Vector((c.x - loc.x, c.y - loc.y, 0.0))


def _mid_stance(an, side):
    """the clip time of `side`'s mid-stance (its stance phase nearest 0.5)"""
    d = an['side'][side]
    st, p = d['stance'], d['p']
    cand = np.where(st, np.abs(p - 0.5), np.inf)
    return float(np.argmin(cand)) * an['dtc']


def _stance_score(an, tc):
    """per side, how near mid-stance the clip is at clip time tc (0 at mid-stance, inf in swing)"""
    k = int(round((tc % an['period']) / an['dtc'])) % an['n']
    return {s: (abs(float(an['side'][s]['p'][k]) - 0.5) if an['side'][s]['stance'][k] else math.inf) for s in SIDES}


def bake_run(legs, f0=1, ground=None, face=None, crown_state=None, head_state=None, fade=8, action_name=None, key=True,
             log=print, min_stand=12, extend=0.4, rest_feet=True, keep_feet_out=True):
    """the legs' record keyed (the module's doc) -> report. keep_feet_out: through a move, a foot the move puts inside a
    collision mesh is pushed out onto its face (_feet_out_of_solids)"""
    rig, h = legs.rig, legs.h
    rec = legs.record
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    dt = 1.0 / fps
    if not rec:
        return {'frames': 0}
    fixed_ground, grounds = ground, {}

    def ground_at(z):
        """the ground a span's feet read: the caller's, else the collision meshes probed from that level plus a step
        (a foot by a tall solid reads the floor it stands on, never the solid's top)"""
        if fixed_ground is not None:
            return fixed_ground
        if legs.world is None:
            return Ground(fn=lambda x, y: 0.0 * np.asarray(x))
        k_ = round(float(z), 2)
        if k_ not in grounds:
            grounds[k_] = legs.world.as_ground(z_from=k_ + 0.45)
        return grounds[k_]
    ground = ground_at(rec[0]['z'])
    spans = _segments(rec, min_stand)
    clips, ans = {}, {}
    walk_body = getattr(legs, '_walk_body', None) or Body(h)
    legs._walk_body = walk_body

    def clip(slot):
        if slot not in clips:
            clips[slot] = legs._emote_actions.get(slot) or load_clip(h, slot)
        return clips[slot]

    def analysis(slot):
        if slot not in ans:
            ans[slot] = analyze_clip(walk_body, clip(slot))
        return ans[slot]

    out = []                          # the film's records, in order
    sim_of = []                       # the record index each film frame stands for
    reports = []
    turns = []                        # the standing turns: their first film frame, angle, steps, frames
    moves = []                        # the maneuvers: their film frames, the hand-in's shift
    prev_last = None                  # the last placed raw record (for a hand-over)
    prev_kind = None
    prev_move = False                 # the span before was a move (its own standing hands over)
    stop_side = None
    probes = {}

    def walk_rel(slot, side, speed):
        """where a walk's foot is at its mid-stance against the root (a short walk_path, once per clip and side)"""
        k = (slot, side, round(speed, 2))
        if k not in probes:
            an_ = analysis(slot)
            w = walk_path(h, clip(slot), [(0.0, 0.0), (0.0, -0.15)], ground, f0=1, speed=speed, phase=_mid_stance(an_, side),
                          face=None, body=walk_body, key=False, preroll=0.0, log=lambda *a: None)['_frames'][0]
            probes[k] = _foot_rel(rig, {'N': w['N'], 'off': w['off'], 'M': w['M']}, side)
        return probes[k]

    def stand_rel(slot, tc):
        """where a standing clip's feet are against its root (its first frame from a fresh clearance)"""
        if rig.clear is not None:
            rig.clear.reset()
        pr = rig.place(rig.stand_raw(clip(slot), tc, dt), _place(0.0, 0.0, 0.0, 0.0), ground)
        if rig.clear is not None:
            rig.clear.reset()
        return {s: _foot_rel(rig, pr, s) for s in SIDES}

    for si, sp in enumerate(spans):
        nxt = spans[si + 1] if si + 1 < len(spans) else None
        ground = ground_at(rec[sp['a']]['z'])            # the level this span starts on
        if sp['kind'] == 'maneuver':
            # A MOVE (RobotLegs._start_maneuver): the controller family's planted frames, my body's DOF pass already
            # run on them (its plant). The keyed body stands where its walk's planted feet stopped it, which can be a
            # part of a stride from where the live run stood, so the move is played again from where I stand (its
            # scan of the cover, the lip, the ladder fitted to where I really am; the film runs on by any frames it
            # differs). Over `fade` frames the pose crossfades from my standing one with both my feet held; where the
            # crossfade lets them go, the move's own feet must be mine: the controller's standing feet sit a few cm
            # off its start point, so the move is played once more from a start moved by that offset, and the small
            # rest is a shift of the whole move on the ground (least squares over both feet). The move's own standing
            # after its landing hands over to the next span as any standing does
            mv = legs._maneuvers[sp['clip']]
            mf, mr, played, replayed = mv['frames'], mv['records'], mv['played'], None
            ks = [rec[i]['maneuver_k'] for i in range(sp['a'], sp['b'])]

            def feet_offset(frames_, k_):
                """my standing feet less the move's at its frame k_ (the ground plane)"""
                fk = frames_[min(k_, len(frames_) - 1)]
                fk = {'N': fk['N'], 'off': fk['off'], 'M': fk['M']}
                d = Vector((0.0, 0.0, 0.0))
                for sd in SIDES:
                    d += _sole_xy(rig, prev_last, sd)[1] - _sole_xy(rig, fk, sd)[1]
                d /= 2.0
                d.z = 0.0
                return d
            if prev_last is not None:
                lp, rp, _s = prev_last['M'].decompose()
                h_here = 2.0 * math.atan2(rp.z, rp.w)
                x0, y0, z0, h0 = mv['start']
                moved = math.hypot(lp.x - x0, lp.y - y0)
                same = moved <= 0.01 and abs(math.remainder(h_here - h0, 2 * math.pi)) <= math.radians(0.5)
                off_ = feet_offset(mf, ks[min(fade, len(ks) - 1)]) if same else None
                if not same or off_.length >= 0.01:
                    start = (Vector((x0, y0, z0)) + off_) if same else Vector((lp.x, lp.y, z0))
                    replayed = {'from_live_m': round(moved, 3), 'played': None}
                    for rnd in range(2):
                        sim = legs.simulate_maneuver(mv['name'], mv['kw'], tuple(start), h_here)
                        if not sim['played']:
                            replayed['refused_round_%d' % rnd] = sim['said'][-3:]
                            break
                        mf, mr, played = sim['frames'], sim['records'], sim['played']
                        ks = list(range(len(mf)))
                        replayed['played'] = played
                        off_ = feet_offset(mf, fade)
                        replayed['round_%d_offset_m' % rnd] = round(off_.length, 4)
                        if off_.length < 0.01:
                            break
                        start = start + off_
                    if replayed['played'] is None:
                        log(f'[robot bake] {mv["name"]}: the move does not fit where the keyed body stands '
                            f'({moved:.2f} m from the live run): its live frames, shifted')
            delta = feet_offset(mf, ks[min(fade, len(ks) - 1)]) if prev_last is not None else Vector((0.0, 0.0, 0.0))
            f_in = f0 + len(out)
            n_sim = sp['b'] - sp['a']
            step_state, guard = {}, {}
            bvh_w = legs.world.bvh if legs.world is not None else None
            k_landed = max((k for k in ks if mr[k].get('mode') == 'maneuver'), default=None)
            for j, k in enumerate(ks):
                fr = mf[k]
                raw = {'N': fr['N'], 'off': fr['off'], 'M': Matrix.Translation(delta) @ fr['M'],
                       'stages': fr.get('stages') or {}}
                if prev_last is not None and j < fade:
                    # the feet step from where I stand to where the move stands (its idle's stance is its own)
                    raw = _step_in(rig, prev_last, raw, j, fade, ground, state=step_state)
                elif bvh_w is not None and keep_feet_out:
                    # a climb's foot never goes into the face it climbs: pushed out onto it, the leg re-solved
                    raw = _feet_out_of_solids(rig, raw, bvh_w, ground, report=guard)
                if rest_feet and k_landed is not None and k > k_landed:
                    # landed and standing on the level it landed on: both feet down (its plant's clearance)
                    rig.rest_feet(raw, ground_at(mr[k]['feet_world'][2]))
                i = min(sp['b'] - 1, sp['a'] + int(round(j * n_sim / max(1, len(ks)))))
                t_film = len(out) * dt
                out.append(rig.finish(raw, dt, face(t_film) if face else None, _aimed_gaze(rig, raw, rec[i]),
                                      crown_state, head_state))
                out[-1]['M'] = raw['M']
                out[-1]['src'] = ('maneuver', mv['name'], 'in' if (prev_last is not None and j < fade) else None)
                out[-1]['move'] = mr[k].get('maneuver') or mr[k].get('mode')
                sim_of.append(i)
                prev_raw = raw
            moves.append({'name': mv['name'], 'played': played, 'film_frames': [f_in, f0 + len(out) - 1],
                          'shift_m': round(delta.length, 4), 'replayed': replayed, 'controller': mv['report'],
                          'step_in_m': {s: round(v, 3) for s, v in step_state.get('far', {}).items()},
                          'feet_pushed_out_m': round(guard.get('max_in_m', 0.0), 3),
                          'body_moved_out_m': round(guard.get('body_moved_m', 0.0), 3),
                          'frames_live': n_sim, 'frames_keyed': len(ks),
                          '_frames': [mf[k] for k in ks], '_shift': delta.copy()})
            prev_last, prev_kind, prev_move = prev_raw, 'stand', True
            continue
        if sp['kind'] == 'stand':
            slot = sp['clip'] or legs.slots['idle']
            c = clip(slot)
            r0 = rec[sp['a']]
            heading = r0['heading']
            x, y, z = r0['x'], r0['y'], r0['z']
            mode = None
            tc_first = (len(out) * dt + dt) if not sp['clip'] else 0.0
            if prev_last is not None:
                lp, rp, _s = prev_last['M'].decompose()
                prev_heading = 2 * math.atan2(rp.z, rp.w)
                rel = stand_rel(slot, tc_first)
                if prev_kind == 'walk':
                    # this clip's foot on the walk's stance side lands on the walk's planted foot
                    heading, mode = prev_heading, 'stop'
                    want = _sole_xy(rig, prev_last, stop_side)[1]
                    have = Quaternion((0.0, 0.0, 1.0), heading) @ rel[stop_side]
                    x, y, z = want.x - have.x, want.y - have.y, lp.z
                elif abs(math.remainder(heading - prev_heading, 2 * math.pi)) < 0.02:
                    # a new clip where the body stands: its feet as near the old ones as they go (least squares)
                    heading, mode = prev_heading, 'both'
                    Rz = Quaternion((0.0, 0.0, 1.0), heading)
                    acc = Vector((0.0, 0.0, 0.0))
                    for sd in SIDES:
                        acc += _sole_xy(rig, prev_last, sd)[1] - Rz @ rel[sd]
                    x, y, z = acc.x / 2, acc.y / 2, lp.z
                else:
                    # face_direction, or an emote aimed elsewhere (set_emote_facing): the body steps round on the spot
                    x, y, z, mode = lp.x, lp.y, lp.z, 'turn'
            if rig.clear is not None:
                rig.clear.reset()
            held, plan, planted, hold_state = prev_last, None, None, {}
            after_move = prev_move                    # holding a move's own landing stance: its soles settled
            n_frames = sp['b'] - sp['a']
            if mode == 'stop':
                n_frames = max(n_frames, fade)        # the other foot comes all the way down first (the film runs on):
                #                                       what follows (a move's step-in, a turn, a clip) starts from both
                #                                       feet down
            if mode == 'turn':
                plan = turn_plan(prev_heading, heading, fps)
                FP = _fk_feet(rig, prev_last)
                planted = {s: (FP[s]['p_an'].copy(), FP[s]['W_ft'].copy()) for s in SIDES}
                # a foot still in the air (a stop cut short by the turn) is the first to step: it lands at the turn's
                # first heading instead of being held where it hangs
                gaps = {}
                for s_, P_ in rig.feet_world(prev_last).items():
                    gaps[s_] = float(np.min(P_[:, 2] - ground.h(P_[:, 0], P_[:, 1])))
                up = max(SIDES, key=lambda s_: gaps[s_])
                if gaps[up] > 0.003:
                    plan['lead'] = up
                n_frames = max(n_frames, plan['frames'])            # a turn longer than its span runs the film on
                turns.append({'frame': f0 + len(out), 'deg': round(math.degrees(plan['theta']), 1),
                              'steps': plan['steps'], 'frames': plan['frames']})
            for k in range(n_frames):
                i = min(sp['a'] + k, sp['b'] - 1)
                r = rec[i]
                t_film = len(out) * dt
                if sp['clip']:
                    tc = min(r.get('clip_t', 0.0), c.duration) if not r.get('loop') else r.get('clip_t', 0.0)
                else:
                    tc = t_film + dt                         # the idle runs on with the film
                raw_c = rig.stand_raw(c, tc, dt)
                raw = rig.place(dict(raw_c), _place(x, y, z, heading), ground)
                if rest_feet and mode in (None, 'stop'):
                    rig.rest_feet(raw, ground)                # both feet on the floor (the idle's own floats one)
                tag = None
                if mode == 'stop' and k < fade:
                    # the walk's planted foot held, the other set down beside it: landed on the blend's last frame
                    raw = _blend(rig, prev_last, raw, (k + 1) / fade, stop_side, prev_last, ground)
                    tag = 'stop'
                    if k == fade - 1:
                        if rest_feet:
                            rig.rest_feet(raw, ground)        # landed: the clamp's tip of the sole settled
                        held = raw                            # stopped: the feet stay where the stop set them
                        hold_state = {}
                elif mode == 'turn' and k < plan['frames']:
                    raw = _turn_frame(rig, raw_c, (x, y, z), plan, k, planted, ground)
                    tag = 'turn'
                    if k == plan['frames'] - 1:
                        # turned: from here the clip plays with each foot where the turn set it down
                        held = raw
                        hold_state = {}
                elif mode in ('both', 'turn', 'stop'):
                    # both feet stay where they stand (moved only as the clip steps its own: _hold_follow), the legs
                    # taking the clip's hips onto them, as the engine's foot IK holds a standing body's feet through an
                    # emote; the pose crossfades in
                    u = min(1.0, (k + 1) / (fade + 1)) if mode == 'both' else 1.0
                    raw = _hold_follow(rig, held, raw, u, ground, hold_state, settle=after_move)
                    tag = 'hold' if mode == 'both' and k < fade else None
                out.append(rig.finish(raw, dt, face(t_film) if face else None, _aimed_gaze(rig, raw, r), crown_state,
                                      head_state))
                out[-1]['M'] = raw['M']
                out[-1]['src'] = ('stand', slot, tag)
                sim_of.append(i)
                prev_raw = raw
            prev_last, prev_kind, prev_move = prev_raw, 'stand', after_move
            continue
        # ---- a walk
        r0 = rec[sp['a']]
        slot = legs.slots['run'] if r0['state'] == 'run' else legs.slots['walk']
        c = clip(slot)
        an = analysis(slot)
        speed = max(0.2, r0['speed'])
        start = rec[sp['a'] - 1] if sp['a'] > 0 else r0
        pts = [(start['x'], start['y'])]
        starting = prev_kind == 'stand' and prev_last is not None
        is_run = r0['state'] == 'run'
        side0 = 'left'
        if starting:
            l0, _r, _s = prev_last['M'].decompose()
            pts = [(l0.x, l0.y)]
            # the walk starts at the mid-stance of the foot whose standing place is nearest its walking one (a run
            # starts from standing, both feet down: its left foot lands on the standing left one)
            if not is_run:
                side0 = min(SIDES, key=lambda sd: (_foot_rel(rig, prev_last, sd) - walk_rel(slot, sd, speed)).length)
        # the route from where the standing body is (the stand's placement can sit off the run's line: a few cm, or a
        # few dm after stepped turns and an aimed emote): it joins the run's line ahead, at least 35 cm and far enough
        # that the course correction is at most JOIN_DEG (a kink near the start would turn a planted foot on the
        # ground, and a sharp one breaks walk_path's planted feet), so it never doubles back
        d0 = (math.sin(r0['heading']), -math.cos(r0['heading']))
        ahead = not starting
        join = 0.35
        if starting:
            live = [(rec[i]['x'], rec[i]['y']) for i in range(sp['a'], sp['b'])]
            lat = min((math.hypot(q[0] - pts[0][0], q[1] - pts[0][1]) for q in live[:40]), default=0.0)
            run_len = sum(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) for a_, b_ in zip(live[:-1], live[1:]))
            join = max(0.35, min(lat / math.tan(math.radians(JOIN_DEG)), 0.6 * run_len))
        for i in range(sp['a'], sp['b']):
            q = (rec[i]['x'], rec[i]['y'])
            if not ahead:
                if (q[0] - pts[0][0]) * d0[0] + (q[1] - pts[0][1]) * d0[1] < join:
                    continue
                ahead = True
            if math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) > 0.02:
                pts.append(q)
        stopping = nxt is not None
        last = rec[sp['b'] - 1]
        target = Vector((last['x'], last['y'], 0.0))
        if stopping and last.get('goal') is not None:
            g = Vector((last['goal'][0], last['goal'][1], 0.0))
            if (g - target).length < 0.6:
                target = g                                    # the walk stops at the goal, not at the arrival radius
                if (g.xy - Vector(pts[-1])).length > 0.02:
                    pts.append((g.x, g.y))
        if len(pts) < 2:
            pts.append((pts[0][0] + 0.05 * math.sin(r0['heading']), pts[0][1] - 0.05 * math.cos(r0['heading'])))
        run_failed = None
        if is_run:
            h_start = rec[sp['a'] - 1]['heading'] if sp['a'] > 0 else r0['heading']
            try:
                wf, wrep = controller_run(legs, pts, speed, h_start, r0['z'], log=log)
            except Exception as e:  # noqa: BLE001 (the controller family is its own package: say so, walk instead)
                run_failed = f'{type(e).__name__}: {e}'
                log(f'[robot bake] THE RUN COULD NOT BE BAKED through the controller family ({run_failed}): this span '
                    f'is WALKED at the run\'s speed instead')
                is_run = False
                c, an = clip(legs.slots['walk']), analysis(legs.slots['walk'])
        edge = None                                       # (the goal, the way on, how far its level runs on)
        if not is_run:
            if stopping and extend > 0:
                d_ = Vector(pts[-1]) - Vector(pts[-2])
                d_ = (d_.normalized() if d_.length > 1e-6
                      else Vector((math.sin(last['heading']), -math.cos(last['heading']))))
                ext, s_edge = _level_run_on(ground, pts[-1], d_, extend)
                edge = (Vector((pts[-1][0], pts[-1][1], 0.0)), Vector((d_.x, d_.y, 0.0)), s_edge)
                if ext > 0.02:
                    pts.append((pts[-1][0] + ext * d_.x, pts[-1][1] + ext * d_.y))
            phase = (_mid_stance(an, side0) if starting
                     else (len(out) * dt * speed / max(1e-6, an['v_clip'])) % an['period'])
            wrep = walk_path(h, c, pts, ground, f0=1, speed=speed, phase=phase, face=None, body=walk_body, key=False,
                             preroll=0.0, log=log)
            wrep['route_in'] = {'pts': [(round(p[0], 4), round(p[1], 4)) for p in pts], 'speed': speed,
                                'phase': round(phase, 5), 'clip': c.name if hasattr(c, 'name') else str(slot)}
            if (wrep.get('worst') or {}).get('ankle_err_mm', 0.0) > 20.0:
                log(f'[robot bake] WALK FAILED its planted feet (an ankle {wrep["worst"]["ankle_err_mm"]} mm off its '
                    f'target): walk_path input {wrep["route_in"]}')
            wf = wrep['_frames']
        # the start: the whole walk moved so its planted foot lands on the standing one
        if starting:
            have = _sole_xy(rig, {'N': wf[0]['N'], 'off': wf[0]['off'], 'M': wf[0]['M']}, side0)[1]
            want = _sole_xy(rig, prev_last, side0)[1]
            delta = want - have
            delta.z = 0.0
            for fr in wf:
                fr['M'] = Matrix.Translation(delta) @ fr['M']
            wrep['start'] = {'side': side0, 'shift_m': round(delta.length, 3)}
        # the stop: a mid-stance near the goal whose standing hand-over moves the hips least (a run slows to a stand on
        # the point itself: both its feet end down, the standing clip's left foot lands on its left)
        if stopping and is_run:
            stop_side = 'left'
        elif stopping:
            nslot = nxt['clip'] or legs.slots['idle']
            nrel = stand_rel(nslot, 0.0 if nxt['clip'] else (len(out) + len(wf)) * dt)
            best = None
            for j, fr in enumerate(wf):
                sc_ = _stance_score(an, fr['tc'])
                if edge is not None and math.isfinite(edge[2]):
                    # by an edge (a drop, a step up, a wall's foot) the stop stands back from it: my standing feet
                    # reach EDGE_REACH ahead of my root
                    lc = fr['M'].translation
                    if (Vector((lc.x, lc.y, 0.0)) - edge[0]).dot(edge[1]) > edge[2] - EDGE_REACH:
                        continue
                for sd in SIDES:
                    if sc_[sd] > 0.06:
                        continue
                    loc = fr['M'].translation
                    d = (Vector((loc.x, loc.y, 0.0)) - target).length
                    glide = (nrel[sd] - _foot_rel(rig, {'N': fr['N'], 'off': fr['off'], 'M': fr['M']}, sd)).length
                    cost = d + glide
                    if best is None or cost < best[0]:
                        best = (cost, j, sd, d, glide)
            if best is not None:
                wf = wf[:best[1] + 1]
                stop_side = best[2]
                wrep['stop'] = {'frame': best[1], 'side': best[2], 'from_goal_m': round(best[3], 3),
                                'hips_glide_m': round(best[4], 3)}
            else:
                stop_side = side0
        if run_failed:
            wrep['run_failed'] = run_failed
        reports.append({k: v for k, v in wrep.items() if not k.startswith('_')})
        n_sim = sp['b'] - sp['a']
        for k, fr in enumerate(wf):
            raw = {'N': fr['N'], 'off': fr['off'], 'M': fr['M'], 'stages': fr['stages']}
            if starting and k < fade:
                raw = _blend(rig, prev_last, raw, (k + 1) / (fade + 1), side0, raw, ground)
            i = min(sp['b'] - 1, sp['a'] + int(round(k * n_sim / max(1, len(wf)))))
            t_film = len(out) * dt
            out.append(rig.finish(raw, dt, face(t_film) if face else None, _aimed_gaze(rig, raw, rec[i]), crown_state,
                                  head_state))
            out[-1]['M'] = raw['M']
            out[-1]['src'] = ('walk', slot, 'start' if (starting and k < fade) else None)
            sim_of.append(i)
            prev_raw = raw
        prev_last, prev_kind, prev_move = prev_raw, 'walk', False
    for j, r in enumerate(out):
        r['f'] = f0 + j
    rep = {'frames': [f0, f0 + len(out) - 1], 'spans': [{k: v for k, v in s.items()} for s in spans], 'walks': reports,
           'turns': turns, 'maneuvers': moves, 'map': sim_of}
    if key:
        rep['action'] = key_robot(h, out, action_name or f'{h.name}|robot_run')
        rep['face'] = key_face_track(h, face_track(out)) if face else {}
    rep['_frames'] = out
    log(f'[robot bake] {len(spans)} spans ({sum(1 for s in spans if s["kind"] == "walk")} walks) -> {len(out)} frames '
        f'(the run recorded {len(rec)})')
    return rep
