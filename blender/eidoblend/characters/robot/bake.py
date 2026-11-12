"""eidoblend.characters.robot.bake: the take my legs recorded, baked as the controller family bakes its own takes, then
keyed through my body's passes.

    rep = legs.bake(f0=1, face=lambda t: {'happy': 0.5})       # RobotLegs.bake / EidoverseRobotController.bake call this

The legs' record is the controller's own run (one film.record per frame the body stepped: the root, the blended pose
before the foot IK, each foot's stance from the clips playing, the mode, the move in flight) with the gaze VRMRobotBody
set on each frame. It is baked by the controller family's bake, emotes.bake over the legs' Locomotion: film's plant puts
the feet down over the whole run, through stairs, ramps, moves, turns and emotes, with my body's hardware pass on every
frame (robot_dof: the torso rehomed, the arms and a held hand through my joints, the legs' clamps and the hip stages),
and a seat taken through emotes.SeatOn gets its seated feet and its hand-overs. Then, frame by frame in film order: through
a move, a foot my hardware's leg clamps put back into the face it climbs is pushed out onto it (_feet_out_of_solids);
and my body's remaining passes (RobotRig.post_pass): the arms' pass again for the wrists' stages and the shoulders'
pitch, the hands' pins and the thumb's rotor, the gaze (re-aimed from the keyed head: _aimed_gaze), the face's head
expression and the crown, each stateful pass exactly once per film frame. Every frame of the run is one film frame
(report['map'] is the identity). On any VRM but my body the passes are a plain rig's: the gaze on the head bone, the rest
as baked. Last, the VRM's spring chains (a VRM's hair, a coat's tails: the engine's vrm.update steps them every frame)
are simulated over the keyed take by the controller family's Locomotion.bake_springs; my body has none.
"""

import math
import time

import bpy
from mathutils import Matrix, Vector

from .. import robot_dof as dof
from .._math import q_from_three, q_to_three
from ..ground import SIDES
from ..performance import key_face_track
from .rig import face_track, key_robot

UP = Vector((0.0, 0.0, 1.0))


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
    head and the heading it renders, and the keyed head stands a little off the live one (the plant's pelvis, my torso's
    rehoming). The aim's change from the live head and heading to the keyed ones is added to the live gaze (its
    rate-limited turn kept), clamped at the body's limits. A frame without a look-at target (a scan, the neutral head)
    is the live gaze"""
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


def _fk_feet(rig, rec):
    body = rig.body
    ph, Wh = body.hips(rec['M'], rec['off'], rec['N'])
    return {s: body.leg_fk(s, ph, Wh, rec['N']) for s in SIDES}


def _solve_feet(rig, N, off, M, targets):
    """N's legs solved so each listed foot's ankle and turn are its target ((T, W) world), clamped as the hardware is,
    the hips' stages solved (a plain rig: the legs as the IK solved them)"""
    body = rig.body
    ph, Wh = body.hips(M, off, N)
    for s, (T, W) in targets.items():
        body.solve_leg(s, ph, Wh, N, T, W, swivel=1.0)
    if rig.legs is None:
        return {'N': dict(N), 'off': off, 'M': M, 'stages': {}}
    p3 = {n: q_to_three(q) for n, q in N.items()}
    dof.apply_hardware_dof(p3, dof.LEG_JOINTS, rig.legs)
    stages = {s: {k: q_from_three(v) for k, v in o.items()} for s, o in rig.legs.out.items() if o}
    return {'N': {n: q_from_three(q) for n, q in p3.items()}, 'off': off, 'M': M, 'stages': stages}


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


def _feet_out_of_solids(rig, rec, bvh, tol=0.003, rounds=6, report=None):
    """a move's frame with each foot that is inside a solid pushed out along that face's normal until its deepest sole
    point is on it, the leg re-solved and clamped as my hardware is (the other foot as it is); what the leg cannot reach
    after `rounds - 1` tries moves the whole body out instead -> rec (unchanged when nothing is inside). The controller
    family keeps a move's feet out of what it climbs on its own pose; my hardware's leg clamps, after it, can put one
    back in (a mount's and a ladder's knees and ankles at their stops). report: {'max_in_m', 'body_moved_m'}"""
    out = rec
    for r_ in range(rounds):
        push = {}
        for s, P in rig.feet_world(out).items():
            best = (0.0, None)
            for p in P[::2]:
                d, n = _inside_depth(bvh, Vector(p))
                if d > best[0]:
                    best = (d, n)
            if best[0] > tol:
                push[s] = best[1] * (best[0] + 0.002)
                if report is not None and r_ == 0:
                    report['max_in_m'] = max(report.get('max_in_m', 0.0), best[0])
        if not push:
            return out
        if r_ == rounds - 1:
            # the leg cannot take the foot out by itself (the move holds my hips too close to the face): the whole body
            # moves out along the face by what is left, its hands with it
            v = max(push.values(), key=lambda p_: p_.length)
            if report is not None:
                report['body_moved_m'] = max(report.get('body_moved_m', 0.0), v.length)
            return dict(out, M=Matrix.Translation(v) @ out['M'])
        F = _fk_feet(rig, out)
        targets = {s: ((F[s]['p_an'] + push[s]) if s in push else F[s]['p_an'].copy(), F[s]['W_ft'].copy())
                   for s in SIDES}
        out = dict(out, **_solve_feet(rig, dict(out['N']), out['off'], out['M'], targets))
    return out


def _runs(recs, f0, key):
    """consecutive frames with the same key(r) (None: not counted) -> [(value, first film frame, last film frame)]"""
    out = []
    for i, r in enumerate(recs):
        v = key(r)
        if v is not None and out and out[-1][0] == v and out[-1][2] == f0 + i - 1:
            out[-1][2] = f0 + i
        elif v is not None:
            out.append([v, f0 + i, f0 + i])
    return [tuple(x) for x in out]


def bake_run(legs, f0=None, face=None, crown_state=None, head_state=None, action_name=None, key=True, springs=True,
             log=print):
    """the legs' take baked and keyed (the module's doc) -> report: 'frames' [f0, f1], the controller family's bake
    report (the plant's measures: 'worst', 'flight', 'airborne', 'double_support', 'segments' with each gait's
    checks.feet, ...), 'moves' (the maneuvers played: [(type, first, last frame)]), 'turns' (the turns on the spot),
    'emotes', 'seats' (emotes.SeatOn's seats), 'map', 'action', 'face', 'seated', 'springs' (the VRM's spring chains
    baked over the keyed take: Locomotion.bake_springs' report, None on a VRM with none; springs=False leaves them
    out, a dict passes bake_springs' options), '_frames' (the keyed records), '_records' (the controller's),
    '_planted' (the controller family's baked frames, before my passes)"""
    from ..emotes import verbs as EV
    rig, h, loco = legs.rig, legs.h, legs.loco
    if not legs.record:
        return {'frames': 0}
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    dt = 1.0 / fps
    f0 = sc.frame_start if f0 is None else int(f0)
    t0 = time.time()
    rep = EV.bake(loco, f0=f0, key=False)
    t1 = time.time()
    frames, recs = rep['_frames'], rep['_records']
    rig.reset()                                           # the film's first frame: the wrists' memory starts fresh
    bvh = getattr(legs.world, 'tree', None)
    guard = {}
    out = []
    for i, (r, fr) in enumerate(zip(recs, frames)):
        raw = {'N': fr['N'], 'off': fr['off'], 'M': fr['M'], 'stages': fr.get('stages') or {}}
        if r['mode'] == 'maneuver' and bvh is not None:
            raw = _feet_out_of_solids(rig, dict(raw, N=dict(raw['N'])), bvh, report=guard)
        o = rig.post_pass(raw['N'], raw['off'], dt, face(i * dt) if face else None, _aimed_gaze(rig, raw, r),
                          crown_state, head_state, legs_out=raw['stages'])
        o.update(f=fr['f'], M=raw['M'], mode=r['mode'], lead=r.get('lead'), move=r.get('maneuver'), cmd=r.get('cmd'))
        out.append(o)
    t2 = time.time()
    res = {k: v for k, v in rep.items() if not k.startswith('_') and k not in ('action', 'frames_baked')}
    res['frames'] = [f0, f0 + len(out) - 1]
    res['map'] = list(range(len(out)))
    res['moves'] = _runs(recs, f0, lambda r: r.get('maneuver') if r['mode'] == 'maneuver' else None)
    n = len(recs)
    res['turns'] = [(a, b, round(math.degrees(math.remainder(recs[min(n - 1, b - f0 + 1)]['heading']
                                                             - recs[max(0, a - f0 - 1)]['heading'], 2 * math.pi)), 1))
                    for _v, a, b in _runs(recs, f0, lambda r: 'turn' if r['mode'] == 'turn' else None)]
    res['emotes'] = _runs(recs, f0, lambda r: r.get('lead') if r['mode'] == 'emote' and r.get('lead') not in
                          (None, 'idle') and not str(r.get('lead')).startswith('idle') else None)
    res['seats'] = [dict(s) for s in getattr(loco, '_seats', [])]
    res['moves_feet_out_m'] = {k: round(v, 4) for k, v in guard.items()}
    res['timing_s'] = dict(rep.get('timing_s') or {}, controller_bake=round(t1 - t0, 2), passes=round(t2 - t1, 2))
    if key:
        res['action'] = key_robot(h, out, action_name or f'{h.name}|robot_run')
        res['face'] = key_face_track(h, face_track(out)) if face else {}
        if getattr(loco, '_seat_windows', None):
            res['seated'] = EV.key_seated(loco, {'_records': recs})
        if springs:
            # the VRM's spring chains over the keyed take, as the engine's vrm.update steps them (a VRM's hair, a coat's
            # tails; my body has none)
            t3 = time.time()
            res['springs'] = loco.bake_springs({'_records': recs, 'action': res['action']},
                                               **(springs if isinstance(springs, dict) else {}))
            res['timing_s']['springs'] = round(time.time() - t3, 2)
    res['_frames'] = out
    res['_records'] = recs
    res['_planted'] = frames
    log(f'[robot bake] {len(out)} frames ({res["frames"][0]}-{res["frames"][1]}): {len(res["moves"])} moves, '
        f'{len(res["turns"])} turns on the spot, {len(res["seats"])} seats; the controller family\'s bake '
        f'{t1 - t0:.1f} s, my passes {t2 - t1:.1f} s')
    return res
