"""examples/obstacle_course.js, the controller's full vocabulary on one course, directed as the WebGPU example directs it:

    test_controller_maneuvers.py [--vrm aporia] [--tag NAME] [--dump f0-f1,...]

The example's character (obstacle_course.json: aporia.vrm), its course (TERRAIN_CONFIG: eidoblend.course.EXAMPLES
['obstacle_course']), the controller terrain_base's (CONTROLLER_PRESETS['terrain_base']), and its renderFrame script
as film commands:
    walk: the bump, 8 deg ramps, small stairs up and down, the low cover VAULT (auto), the 1.15 m wall MOUNT (auto),
          across its top and off its far edge (a fall, fallLand)
    run (segments 15 to 23): stairs up, the 1.1 m GAP JUMP (auto), stairs down, the chest-high cover VAULT (auto)
    walk: the 2.2 m wall CLIMB (auto: climbWallUp), its top and the drop (fallLand)
    the sit stop: auto maneuvers off near the bench, routed around it (the example's three waypoints), squared up to
          the course heading, seated on the bench through eidoblend.characters.emotes.seat_on (stand_to_sit, the seat
          settled on the pan as its seatOn does, the take baked by emotes.bake), held, stood (the clip reversed at
          1.25x), stopEmote
    a cheer gesture while walking (segment 27), stopped before the ladder
    the LADDER (explicit climbLadder, 2.5 m: the rung loop chained into the mantle over the top)
    the finale: walk to the platform's middle, salute toward the camera
and its camera: the full-side follow camera (5.2 m off, 3.4 m while maneuvering or sitting, eased at 2.5 / s), swung to
a rear three-quarter 46 deg for the ladder and the finale (eased at 1.8 / s), keyed on every frame of the saved film.

Prints PASS / FAIL: every maneuver the example plays (vault x2, mount x2, the gap jump, the ladder and its mantle,
fallLand); each vault rises over its cover and plants its prop hand's palm on the top, no point of a hand in the
cover, the hold taken and let go without a pop; the hands on the lip during each
mount, its crouched feet resting on the top; the hands and the balls of the feet on the rungs through the ladder; no
foot inside a solid in any maneuver (the visible foot mesh measured, FootMesh); checks.feet on the walking, running and
seated stretches; the seated feet on the floor and the seat's underside on the bench; the gesture; the salute; the
finale on the top platform; the keyed armature against the bake. Stills (render_shots.py): the example's camera at
the middle of each stretch and through each maneuver, and close-ups of the contacts.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import emotes as E  # noqa: E402
from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402
from eidoblend.course import EXAMPLES, add_bench  # noqa: E402

ARGS = T.argv()
EX = EXAMPLES['obstacle_course']
VRM = T.arg(ARGS, '--vrm', EX.get('character', 'aporia'))     # the example's own character (obstacle_course.json)
R = T.Report(T.arg(ARGS, '--tag', f'maneuvers_{VRM}'))
R['vrm'] = VRM
_cam = EX.get('camera') or {}                                    # the example's follow camera
CAM_R, CAM_R_NEAR, CAM_SWING_DEG = (_cam.get('radius', 5.2), _cam.get('radius_close', 3.4),
                                    _cam.get('ladder_angle_deg', 46.0))


def main():
    sc = T.S.clean_scene(fps=30)
    course = T.course(EX['config'], name='example')
    bench = add_bench(course, EX['bench'], material=T.course_materials()['bench'])
    seg = course.segment
    me = load_vrm(VRM, name=VRM)
    # terrain_base: "Rungs are visual; the flat face is the collider": the ladder's rails and rungs are not walked on
    fixtures = [o for o in course.objects if o.get('eido_course_role') in ('rail', 'rung')]
    world = CollisionWorld(exclude=fixtures)
    R['fixtures_excluded'] = len(fixtures)
    # the maneuvers' feet stay out of every solid, the rungs and rails too (contact_world)
    loco = Locomotion(me, world, start=course.start, heading=math.pi, preset='terrain_base', log=R.log,
                      controller_opts={'contact_world': CollisionWorld()})
    c = loco.ctrl
    z = EX['zones']
    run0, run1 = seg(z['run'][0])['y0'], seg(z['run'][1])['y1']
    by = (bench.location.y if bench is not None else (seg(z['sit'])['y0'] + seg(z['sit'])['y1']) / 2)
    sit_seg = seg(z['sit'])
    ges, lad, top = seg(z['gesture']), seg(z['ladder']), seg(z['finale'])
    R['zones'] = {'run': (run0, run1), 'bench_y': by, 'ladder_y0': lad['y0'], 'top': (top['y0'], top['y1'])}

    def auto(on):
        def f(ctl):
            ctl.auto_maneuvers = on
        return f
    loco.wait(0.6)
    loco.follow_path([(0.0, run0)], gait='walk', stop=False)
    loco.follow_path([(0.0, run1)], gait='run', stop=False)
    loco.follow_path([(0.0, sit_seg['y0'] - 1.2)], gait='walk', stop=False)
    loco.call(auto(False))                                       # the example: no maneuver near the bench
    route = [(x, by - z_) for x, z_ in EX['sit_route']]          # three (x, bz + dz) -> Blender (x, by - dz)
    loco.follow_path(route, gait='walk')
    loco.turn_to(180.0)                                          # square up to the course heading (three's pi)
    st = EX['sit_timing']
    # the example's seatOn(vrm, bench, {transition: 'stand_to_sit', faceY: Math.PI}) through the controller, its hold,
    # endSeated({reverse: true, reverseSpeed: 1.25}): eidoblend.characters.emotes' cohesive path
    E.seat_on(loco, bench, face=math.pi, hold=st['hold'], stand={'reverse': True, 'reverse_speed': st['reverse_speed']})
    seat_cmd = loco._queue[-1]
    loco.call(auto(True))
    loco.follow_path([(0.0, ges['y0'])], gait='walk', stop=False)
    loco.gesture(EX['gesture']['name'], weight=EX['gesture']['weight'])
    loco.follow_path([(0.0, ges['y1'] - EX['gesture']['stop_before_end'])], gait='walk', stop=False)
    loco.stop_gesture()
    # the example calls climbLadder 0.55 m from the face, but its auto-trigger (0.35 + 0.3 x speed ahead) reads the
    # 2.5 m ladder block as a wall to scramble before that: the trigger is off for the approach so the ladder plays
    loco.call(auto(False))
    loco.move_to((0.0, lad['y0'] - EX['ladder']['trigger']), gait='walk')
    loco.climb_ladder(height=EX['ladder']['height'])
    loco.call(auto(True))
    loco.move_to((0.0, (top['y0'] + top['y1']) / 2), gait='walk')
    loco.wait(EX['finale']['delay'])
    # the example salutes toward its camera, which has swung to its rear three-quarter (46 deg) by the finale: the
    # heading toward (cos 46, -sin 46) is 90 - 46 deg. It never stops the salute: the last pose holds, facing the camera
    loco.emote(EX['finale']['emote'], fade_in=EX['finale']['fade_in'], facing=90.0 - CAM_SWING_DEG, stop=False)
    loco.wait(EX['finale'].get('hold', 1.0))
    t0 = time.time()
    rep = E.bake(loco, f0=1)                                     # Locomotion.bake with the seat's frames handed over
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = segs
    man = {}
    for r in recs:
        if r['mode'] == 'maneuver' and r['maneuver']:
            man.setdefault(r['maneuver'], []).append(r['f'])
    runs = {}
    for k, fs in man.items():
        runs[k] = [[fs[0], fs[0]]]
        for f in fs[1:]:
            if f == runs[k][-1][1] + 1:
                runs[k][-1][1] = f
            else:
                runs[k].append([f, f])
    R['maneuvers'] = runs
    R.log(f'maneuvers: {runs}')
    want = {'vault': 2, 'mount': 2, 'jump': 1, 'ladder': 1, 'land': 1}
    for k, n in want.items():
        got = len(runs.get(k, []))
        R.check(f'the example\'s {k} maneuver plays ({n} or more)', got >= n, f'{got}: {runs.get(k)}')
    R.check('the ladder chains into the mantle (a mount right after the ladder)', bool(runs.get('ladder')) and any(
        a == runs['ladder'][-1][1] + 1 for a, _b in runs.get('mount', [])), f'ladder {runs.get("ladder")}, mount '
        f'{runs.get("mount")}')
    # the contact IK, judged on what the camera sees: the bones where Blender's keyed pose puts them, the visible feet
    # (FootMesh: the skinned foot vertices against every solid, rungs included)
    fm = T.FootMesh(me)
    hand = {s: me.humanoid[s + 'Hand'] for s in ('left', 'right')}
    hips = me.humanoid['hips']

    def bone_at(f, b):
        sc.frame_set(f)
        return me.arm.matrix_world @ me.arm.pose.bones[b].head

    def hand_points(f, s):
        """a hand's wrist, middle knuckle, middle fingertip and the palm's skin under its knuckles (the controller's
        maneuvers._grip_point with no bar) as the keyed pose has them at frame f"""
        sc.frame_set(f)
        hb = me.humanoid[s + 'Hand']
        M = me.arm.matrix_world @ me.arm.pose.bones[hb].matrix
        W = M.to_quaternion() @ me.rest_q[hb].inverted()
        pos = {n: me.arm.matrix_world @ me.arm.pose.bones[me.humanoid[s + n]].head
               for n in ('MiddleProximal', 'MiddleIntermediate', 'MiddleDistal')}
        wr, kn = M.translation.copy(), pos['MiddleProximal']
        d = pos['MiddleDistal'] - pos['MiddleIntermediate']
        tip = pos['MiddleDistal'] + d * 0.8
        return wr, kn, tip, wr * 0.25 + kn * 0.75 + (W @ Vector((0.0, 0.0, -1.0))) * 0.014

    def box(o):
        V = [o.matrix_world @ v.co for v in o.data.vertices]
        return (min(v.x for v in V), max(v.x for v in V), min(v.y for v in V), max(v.y for v in V), max(v.z for v in V))
    walls = [box(o) for o in course.objects if o.type == 'MESH' and o.get('eido_course_role') in ('wall', 'ladder')]

    def crossed(a, b):
        """the wall box the body crosses in frames a..b (the one its feet's y span overlaps most)"""
        ys = [recs[f - f0]['feet_world'][1] for f in range(a, b + 1)]
        lo, hi = min(ys) - 0.3, max(ys) + 0.3
        cand = [w for w in walls if w[3] > lo and w[2] < hi]
        return max(cand, key=lambda w: min(w[3], hi) - max(w[2], lo)) if cand else None
    R['vault_detail'], R['mount_detail'] = [], []
    for j, (a, b) in enumerate(runs.get('vault', [])):
        w = crossed(a, b)
        if w is None:
            R.check(f'vault {j + 1}: a cover crossed', False, f'frames {a}-{b}')
            continue
        tz = w[4]
        hz = max(bone_at(f, hips).z for f in range(a, b + 1))
        R.check(f'vault {j + 1} (frames {a}-{b}) rises over its cover: the hips {hz - tz:.2f} m over its {tz:.2f} m top',
                hz - tz > 0.25, f'peak hips {hz:.2f} m')
        best, deep, prop = 9.9, (0.0, None, None), None
        for f in range(a, b + 1):
            for s in hand:
                wr, kn, tip, pp = hand_points(f, s)
                if w[0] - 0.02 <= pp.x <= w[1] + 0.02 and w[2] - 0.02 <= pp.y <= w[3] + 0.02 and abs(pp.z - tz) < best:
                    best, prop = abs(pp.z - tz), s
                for nm, q in (('wrist', wr), ('knuckle', kn), ('fingertip', tip)):
                    d = min(tz - q.z, q.x - w[0], w[1] - q.x, q.y - w[2], w[3] - q.y)    # inside the cover: its nearest face
                    if d > deep[0]:
                        deep = (d, f, f'{s} {nm}')
        # the prop hand taken hold and let go of without a pop: its wrist's change of velocity a frame (the second
        # difference of its place: a planted hand stands still while the body moves on over it, and a swing changes
        # its velocity smoothly), the move and the frames after it (a hold taken at full weight at once jumped the hand
        # 32 cm onto the top, and one ending in one frame left the clip's flung-up hand 58 cm away); the free arm is the
        # clip's own
        pw = {f: bone_at(f, hand[prop or 'right']) for f in range(a, b + 7)}
        jump = max(((pw[f + 1] - 2 * pw[f] + pw[f - 1]).length, f, prop or 'right') for f in range(a + 1, b + 6))
        R['vault_detail'].append({'frames': [a, b], 'top': round(tz, 3), 'hips_over_top': round(hz - tz, 3),
                                  'prop_palm_off_top_m': round(best, 3),
                                  'hand_into_top_m': [round(deep[0], 3), deep[1], deep[2]],
                                  'wrist_velocity_change_max_m': [round(jump[0], 3), jump[1], jump[2]]})
        R.check(f'vault {j + 1}: the prop hand takes hold of the cover and lets go of it without a pop (its wrist\'s '
                f'velocity changes under 25 cm a frame, a frame: a hold taken at once changed it 32 cm, one let go in a '
                f'frame 86 cm; the palm landing on the top stops it about 23)', jump[0] < 0.25,
                f'{jump[0] * 100:.1f} cm ({jump[2]} at f{jump[1]})')
        R.check(f'vault {j + 1}: the prop hand plants its palm on the cover\'s top (the skin under its knuckles within '
                f'1.5 cm of it) and no point of the hand goes into it (wrist, knuckle, fingertip: under 1 cm)',
                best < 0.015 and deep[0] < 0.01, f'the palm {best * 100:.1f} cm off the top at its nearest; the deepest '
                f'point of a hand under it {deep[0] * 100:.1f} cm ({deep[2]} at f{deep[1]})')
    for j, (a, b) in enumerate(runs.get('mount', [])):
        w = crossed(a, b)
        if w is None:
            R.check(f'mount {j + 1}: a wall climbed', False, f'frames {a}-{b}')
            continue
        tz = w[4]
        best = min(abs(bone_at(f, bn).z - (tz + 0.025)) for f in range(a, b + 1, 2) for bn in hand.values())
        m_end = fm.at(b)
        low = min(v['zmin'] for v in m_end.values())
        R['mount_detail'].append({'frames': [a, b], 'top': round(tz, 3), 'hand_off_top_m': round(best, 3),
                                  'feet_low_over_top_m_at_end': round(low - tz, 3)})
        R.check(f'mount {j + 1} (frames {a}-{b}): a hand on the lip / the top (within 6 cm)', best < 0.06,
                f'{best * 100:.1f} cm')
        R.check(f'mount {j + 1}: the crouched feet rest on the top at its end (the lower foot 0-3 cm over it)',
                -0.006 <= low - tz <= 0.03, f'{(low - tz) * 100:+.1f} cm')
    # no foot inside a solid through any maneuver (and the settle after it)
    pen = {}
    for k, rs in runs.items():
        worst = (0.0, None)
        for a, b in rs:
            for f in list(range(a, b + 1, 2)) + list(range(b + 1, min(f1, b + 8) + 1, 2)):
                m = fm.at(f)
                for s, v in m.items():
                    if v['pen_mm'] > worst[0]:
                        worst = (v['pen_mm'], [f, s])
        pen[k] = worst
        R.check(f'{k}: no foot inside a solid (the visible foot mesh, every 2nd frame)', worst[0] <= 10.0,
                f'deepest {worst[0]} mm at {worst[1]}')
    R['maneuver_foot_penetration_mm'] = pen
    # the ladder: hands and the balls of the feet on the rungs (a rung is a bar along X)
    rungs = [o.matrix_world.translation.copy() for o in course.objects if o.get('eido_course_role') == 'rung']
    hd, fd = [], []
    for a, b in runs.get('ladder', []):
        for f in range(a + int(0.2 * (b - a)), a + int(0.95 * (b - a)) + 1, 2):
            hs = [bone_at(f, bn) for bn in hand.values()]
            hd.append(min((math.hypot(p.y - q.y, p.z - q.z) for p in hs for q in rungs if abs(p.x - q.x) < 0.3),
                          default=9.9))
            m = fm.at(f)
            best = 9.9
            for v in m.values():
                P = v['P']
                for q in rungs:
                    sel = np.abs(P[:, 0] - q.x) < 0.25
                    if sel.any():
                        d = np.hypot(P[sel, 1] - q.y, P[sel, 2] - q.z) - 0.028
                        best = min(best, float(np.abs(d).min()))
            fd.append(best)
    R['ladder_hand_to_rung_m'] = [round(d, 3) for d in hd]
    R['ladder_foot_to_rung_m'] = [round(d, 3) for d in fd]
    R.check('the hands grip the rungs through the climb (a wrist within 6 cm of a rung\'s line in 85 % of the frames)',
            bool(hd) and float(np.mean(np.array(hd) < 0.06)) >= 0.85,
            f'{sum(1 for d in hd if d < 0.06)} of {len(hd)}; median {np.median(hd) if hd else 9.9:.3f} m')
    R.check('the feet stand on the rungs through the climb (a boot within 1.5 cm of a rung in 75 % of the frames)',
            bool(fd) and float(np.mean(np.array(fd) < 0.015)) >= 0.75,
            f'{sum(1 for d in fd if d < 0.015)} of {len(fd)}; median {np.median(fd) if fd else 9.9:.3f} m')
    # the walking, running and seated stretches
    T.gait_checks(R, rep)
    seated = [r for r in recs if r['mode'] in ('seated', 'seat')]     # 'seat': the frames emotes.bake hands over
    spans = (rep.get('seated') or {}).get('spans') or []
    R['seated_spans'] = spans
    R.check('the sit stop: seated on the bench', len(seated) > 30 and len(spans) == 1,
            f'{len(seated)} seated frames, spans {spans}')
    if seated:
        fa, fb = seated[0]['f'], seated[-1]['f']
        # the hold itself: from the sit-down's end to the stand-up (seat_on's seated frames also carry its descent,
        # whose last step lifts a boot, and its stand-up: their middle third began in the descent)
        h0 = fa + int(round(getattr(seat_cmd, 'span', 0.0) * 30)) + 6
        h1 = min(fb, h0 + int(round(st['hold'] * 30)) - 12)
        hold = range(h0, h1 + 1, 6) if h1 > h0 else range(fa + (fb - fa) // 3, fb - (fb - fa) // 3 + 1, 6)
        floor = seated[0]['feet_world'][2]
        lows = [min(v['zmin'] for v in fm.at(f).values()) - floor for f in hold]
        R.check('the seated feet stand on the floor (the visible boots within -6 / +10 mm of it through the hold)',
                all(-0.006 <= z <= 0.010 for z in lows), f'{[round(z * 1000, 1) for z in lows]} mm')
        from eidoblend.characters.emotes.verbs import skin_lowest
        sc.frame_set((fa + fb) // 2)
        und = skin_lowest(me, seat_cmd.pan, seat_cmd.seat_here - 0.25)
        gap = (und - seat_cmd.seat_here) if und is not None else 9.9
        R.check('the seat rests on the bench (the seated skin within 1.5 cm of its top, seatOn\'s settle)',
                abs(gap) < 0.015, f'{gap * 100:+.1f} cm')
    gw = max((r['weights'].get('cheer', 0.0) for r in recs), default=0.0)
    R.check('the cheer gesture over the walk', gw > 1.0, f'weight up to {gw:.2f}')
    em = [r for r in recs if r['mode'] == 'emote' and r['weights'].get('salute', 0) > 0.5]
    R.check('the finale salute', len(em) > 10, f'{len(em)} frames')
    if em:
        aim = math.radians(90.0 - CAM_SWING_DEG)
        held = [r for r in recs if r['f'] >= em[0]['f'] + 15]
        dev = max(abs(math.degrees(math.remainder(r['heading'] - aim, 2 * math.pi))) for r in held)
        R.check('the salute holds to the end, facing the camera (no stopEmote: the last pose kept, no turn back)',
                recs[-1]['weights'].get('salute', 0.0) > 0.9 and dev < 2.0,
                f'from 0.5 s into it to the last frame {held[-1]["f"]}: the heading at most {dev:.2f} deg off the aim; '
                f'the salute\'s weight at the end {recs[-1]["weights"].get("salute", 0.0):.2f}')
    end = recs[-1]['feet_world']
    R.check('the finale stands on the ladder\'s top platform', top['y0'] < end[1] < top['y1'] and
            abs(end[2] - top['floor0']) < 0.08, f'feet at {tuple(round(v, 2) for v in end)}, the platform at '
            f'{top["floor0"]:.2f} m from y {top["y0"]:.2f} to {top["y1"]:.2f}')
    R['worst'] = rep['worst']
    if T.arg(ARGS, '--dump'):
        T.dump_frames(R, rep, [tuple(int(v) for v in rg.split('-')) for rg in T.arg(ARGS, '--dump').split(',')])
    T.keyed_matches(R, me, frames)
    cam = follow_camera(sc, loco.ctrl, recs, lad['y0'])
    shots(sc, me, recs, segs, runs, cam)


def follow_camera(sc, c, recs, ladder_y0):
    """the example's camera, keyed on every frame: beside the body (+X, the course runs along +Y) 5.2 m off, 3.4 m while
    a maneuver plays or the body sits (eased at 2.5 / s), swung 46 deg to a rear three-quarter from 2.2 m before the
    ladder (eased at 1.8 / s); 0.45 + 0.07 x the distance over the body's centre, looking 0.30 m under it; 45 deg
    vertical field (terrain_base's camera: 24.4 mm on a 36 mm sensor at 16:9) -> {frame: (pos, target)}"""
    cd = bpy.data.cameras.new('example_cam')
    cd.lens, cd.clip_start, cd.clip_end = 24.4, 0.1, 200.0
    cam = bpy.data.objects.new('example_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.rotation_mode = 'QUATERNION'
    lift = c.hip_y + c.half_height + c.vrm_foot_y
    dt = 1.0 / 30.0
    Rr, A = CAM_R, 0.0
    out = {}
    for i, r in enumerate(recs):
        bx, by, bz = r['feet_world'][0], r['feet_world'][1], r['feet_world'][2] + lift
        near = r['mode'] in ('maneuver', 'seated', 'seat') or r.get('cmd') == 'Sit'
        want_r = CAM_R_NEAR if near else CAM_R
        want_a = math.radians(CAM_SWING_DEG) if by >= ladder_y0 - 2.2 else 0.0
        if i:
            Rr += (want_r - Rr) * (1 - math.exp(-2.5 * dt))
            A += (want_a - A) * (1 - math.exp(-1.8 * dt))
        pos = Vector((bx + Rr * math.cos(A), by - Rr * math.sin(A), bz + 0.45 + 0.07 * Rr))
        tgt = Vector((bx, by, bz - 0.30))
        cam.location = pos
        cam.rotation_quaternion = (tgt - pos).to_track_quat('-Z', 'Y')
        cam.keyframe_insert('location', frame=r['f'])
        cam.keyframe_insert('rotation_quaternion', frame=r['f'])
        out[r['f']] = (tuple(pos), tuple(tgt))
    return out


def shots(sc, me, recs, segs, runs, cam):
    """the example's camera at the middle of each stretch, eight frames through each maneuver (the strips), close-ups
    of the contacts (the vault's prop hand, the mount's end crouch, the feet on the rungs, the seated feet)"""
    T.light(sc)
    S, sheets = [], {'sheet': []}
    r0 = recs[0]['f']

    def at(f, name):
        pos, tgt = cam[f]
        return {'name': name, 'frame': f, 'pos': pos, 'target': tgt, 'lens': 24.4}
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 8:
            continue
        f = (a + b) // 2
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        S.append(at(f, name))
        sheets['sheet'].append(name)
    for k, rs in runs.items():
        for j, (a, b) in enumerate(rs[:2]):
            a2, b2 = max(r0, a - 6), min(recs[-1]['f'], b + 10)
            fs = [int(a2 + (b2 - a2) * i / 7) for i in range(8)]
            names = []
            for i, f in enumerate(fs):
                nm = f'strip_{k}{j}_{i}'
                S.append(at(f, nm))
                names.append(nm)
            sheets[f'strip_{k}{j}'] = names
    # close-ups: a fixed camera 1.6 m to the side of the contact, level with it
    hand = me.humanoid['rightHand']

    def close(f, name, z_off=0.0, side=1.6, lens=50.0, back=0.0):
        sc.frame_set(f)
        p = recs[f - r0]['feet_world']
        tgt = Vector((p[0], p[1] + back, p[2] + z_off))
        return {'name': name, 'frame': f, 'pos': (tgt.x + side, tgt.y - 0.25, tgt.z + 0.15), 'target': tuple(tgt),
                'lens': lens}
    for j, (a, b) in enumerate(runs.get('vault', [])[:2]):
        names = []
        for i, f in enumerate(range(a, b + 1, max(1, (b - a) // 5))):
            nm = f'close_vault{j}_{i}'
            S.append(close(f, nm, z_off=0.7, side=2.2, lens=35.0))
            names.append(nm)
        sheets[f'close_vault{j}'] = names
        # the prop hand from its plant on the top to its letting go, every second frame
        names = []
        for i, f in enumerate(range(a + (b - a) // 2 - 4, a + (b - a) // 2 + 10, 2)):
            nm = f'close_vault{j}_hand_{i}'
            S.append(close(f, nm, z_off=0.75, side=1.4, lens=50.0))
            names.append(nm)
        sheets[f'close_vault{j}_hand'] = names
    # the finale from the example's own camera: the salute to the film's end (held, facing the camera)
    em = [r['f'] for r in recs if r['mode'] == 'emote' and r['weights'].get('salute', 0) > 0.5]
    if em:
        names = []
        for i, f in enumerate(range(em[0] - 6, recs[-1]['f'] + 1, 6)):
            nm = f'finale_{i}'
            S.append(at(f, nm))
            names.append(nm)
        sheets['finale'] = names
    for j, (a, b) in enumerate(runs.get('mount', [])[:2]):
        names = []
        for i, f in enumerate(range(a + (b - a) // 2, b + 9, max(1, (b - a) // 8))):
            nm = f'close_mount{j}_{i}'
            S.append(close(min(f, recs[-1]['f']), nm, z_off=0.3, side=1.8, lens=40.0))
            names.append(nm)
        sheets[f'close_mount{j}'] = names
    for a, b in runs.get('ladder', [])[:1]:
        names = []
        for i, f in enumerate(range(a + (b - a) // 4, b, max(1, (b - a) // 8))):
            nm = f'close_ladder_{i}'
            sc.frame_set(f)
            p = recs[f - r0]['feet_world']
            S.append({'name': nm, 'frame': f, 'pos': (p[0] + 1.5, p[1] - 0.9, p[2] + 0.9),
                      'target': (p[0], p[1] + 0.35, p[2] + 0.7), 'lens': 35.0})
            names.append(nm)
        sheets['close_ladder'] = names
    seated = [r['f'] for r in recs if r['mode'] in ('seated', 'seat')]
    if seated:
        names = []
        for i, f in enumerate(range(seated[0], seated[-1] + 1, max(1, (seated[-1] - seated[0]) // 5))):
            nm = f'close_sit_{i}'
            S.append(close(f, nm, z_off=0.35, side=1.7, lens=40.0))
            names.append(nm)
        sheets['close_sit'] = names
    T.save(R, sc, S, sheets)

try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
