"""eidoblend.characters.controller.plant: the film bake's feet, planted on whatever the controller walked over.

The WebGPU edition grounds the feet every frame with VRMFootControllerIK (foot_ik.py): it follows the animated foot's xy,
so whenever the clip's stride and the body's travel differ (a start, a stop, a turn, a stair the clip was not made for)
the foot slides. A film is built once, so here the controller's run is recorded first (film.py) and the feet are placed
over the whole run, as round one's walk_path places them for one clip (locomotion.py: its passes, generalised to any
blend of clips at any speed):

  THE STANCE    a foot is down where the clips playing (at their weights and their own clip times) have it down: each
                clip's measured stance (clips.analyze), blended; idle, the emotes and a seat stand on both feet (a seat's
                pelvis stays where the seat puts it, its feet go onto the floor under it); a fall and a maneuver leave
                the feet to the clip (the maneuver's contact IK places them), and a foot they hand back is planted once
                the blend sets it down (LAND_GAP, LAND_TURN). Neither foot down is a flight only where a
                gait with one leads (FLIGHT_SLOTS); anywhere else the report lists it as airborne. A swing of two frames
                between two stances is the crossfade's noise where the foot lands back where it stood: it stays down;
                one that carries the foot on starts earlier, to last SWING_MIN_FRAMES while the other foot stands
  THE STEPS     a planted foot the body has walked on from is let go (an early toe-off; a stance the walk has already
                ended, held on by a stair clip blending in, as soon as it would pull the hips down: TRAIL_LATE); where
                the other foot is still in its swing then, that swing is brought forward to land by then (its own
                motion relative to the body, played faster: a quicker step, _land_by / _retime), so a walk keeps a
                foot down
  THE LOCK      through a stance the sole's points in contact in this frame and the last do not slip and the foot does
                not turn on the ground (in a turn on the spot it pivots about its contact: that is a turn). The heading
                it lands with is turned on by the free foot's own turn up to mid-stance (centred: on a curve the hips
                take the turn). On a stair or an edge the landing is moved along the foot (at most 12 cm) to where most
                of the sole is supported; a stance whose sole reaches into a riser or a dome's side at any of its
                frames is moved along the travel as little as keeps it out (_tuck_shift). The first stance after a
                seat stands where the seat left the foot
  THE TARGET    tilted onto the ground's plane under the sole, set flat when within 1.5 deg of flat (not into the
                heel-off), inside the ankle's pitch range for my robot body, toes flat on the ground through the toe
                roll. My robot body's ankle rolls at most 14.9 deg, short of a steep cross slope: a planted foot on
                one (ground tilted across it over 8 deg) keeps one roll off the ground for its whole stance, the most
                its solved legs need in its flat part (_stance_rolls), so its sole does not roll on the ground as the
                shin moves over it until the heel-off
  THE HEIGHT    in stance the lowest sole point on the ground. In swing the straight line between the two plants plus
                the clip's own arc over it (in the body's frame), never closer than `clearance` mid-swing to the highest
                ground the sole sweeps (a slope-limited envelope: the foot rises before a riser, not at it)
  THE PELVIS    for each planted leg the root goes where that leg has the clip's own hip-to-ankle length (the stance knee
                is the clip's), the legs shared by their load; capped so every loaded leg reaches; lowered where a
                straight planted leg is still short; in a run's flight carried between the supports. pelvis='controller'
                keeps the controller's own body height (its probes, rate caps and descent drop), capped for reach
  THE LEGS      round one's two-bone IK (Body.solve_leg) with its lock rounds on the result, the robot's joint clamps and
                hip stages after

plant(...) returns the frames round one's key_frames keys, and a report measured on the result (the feet's points where
Blender's skinned mesh puts them) per stance and swing: checks.feet reads it.
"""

import copy
import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from .. import robot_dof as dof
from .._math import (D2R, R2D, clamp, ease, euler_from_quat, hann_smooth, lerp_table, q_from_three, q_to_three, smooth,
                     twist_about, wrap_pi)
from ..ground import SIDES, foot_points
from ..locomotion import CONTACT, FLAT, FWD, LOCK_BAND, NEED, REACH_MARGIN, WIDTH, YAW_CAP, _bump, _intervals

LOCK_ROUNDS = 14                     # round one's 8 rounds converge for one clip at its own pace; a blend of clips at the
#                                      controller's pace corrects more each frame (a stair clip on a stair it was not
#                                      made for): more rounds, each frame's last ones settling the slip
from .pose import Pose, dof_pass

CLEARANCE = 0.03
FLIGHT_SLOTS = ('run', 'stairsRunUp', 'stairsRunDown', 'fallIdle')   # the gaits whose frames may have neither foot down
STAIR_SLOTS = ('stairsDown',)          # a descent's trailing foot leaves before the other lands (it is above the hips)
STANCE_DROP_MAX = 0.45              # a stance whose ground lies this far under the body's support steps off an edge
STEP_FIT_MAX = 0.30                  # a landing's fit may move it onto a tread at most this far down (a stair's rise)
TWO_POINT_MAX = 3.0 * D2R            # the most the two-point support turns a planted sole in one round
FIT_RANGE = 0.12                     # the most a landing moves along the foot to find its support (m)
SURFACE_DROP = 0.05                  # a planted sole's surface lies no further under the ground it landed on (m)
BOOT_FIT = 0.04                      # the most more it moves to take the boot out of a riser (a heel's tuck) (m)
SWEEP_RATE = 1.2                     # the swing's clearance envelope rises toward an obstacle at most this fast (m/s)
STEP_NOISE = 0.08                    # a two-frame swing landing within this of where its foot stood is a blend's noise (m)
SWING_MIN_FRAMES = 4                 # a short swing that carries its foot on is started earlier to last this many frames
LAND_GAP = 0.015                     # a foot handed back from a maneuver or a fall is planted once its sole is this near
LAND_TURN = 3.0 * D2R                # the ground and the blend turns it less than this a frame...
LAND_MAX = 6                         # ...at most this many frames after the hand-over
LOAD_FRAMES = 4
TRAIL_FULL = 0.55                    # a planted foot within this share of its leg's reach from the hip (along the
TRAIL_NONE = 0.85                    # ground) carries its load; past this share none (the body walked on from it)
LOAD_MIN = 0.3                       # under this much carried load the pelvis eases to the controller's own height
TRAIL_BEHIND = 0.12                  # a planted foot this far behind its hip along the travel...
TRAIL_DIP = 0.25                     # ...that the pelvis reaches only this far under the controller's own: left behind
#                                      (0.15 also caught a stair's ordinary dip: a 6-frame hop off the last tread)
TRAIL_LATE = 0.7                     # past this share of its stance a planted foot behind its hip that the walk (or the
TRAIL_GROUND_SHARE = 0.25            # run), still carrying this share of the weight, has already lifted is left behind
TRAIL_DIP_LATE = 0.12                # where the pelvis reaches it only this far under the controller's own
TRAIL_DOUBLE = 3                     # and the other foot has stood this many frames (the weight crosses first)
TRAIL_STAIR_SHARE = 0.15             # the stair clips' share of the blend's weight that holds such a stance on
STAIR_CLIPS = ('stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown')
ROLL_TOL = 0.4 * D2R                 # my robot body: a planted foot its ankle's roll stop holds further than this off its
ROLL_ROUNDS = 2                      # target gets one roll for the stance (_stance_rolls), in these rounds, measured
ROLL_FROM = 0.25                     # over its flat part: from this share of the stance (its landing settled)
ROLL_TO = 0.45                       # to this one (the heel-off: the clip's own foot comes back from there, THE TARGET),
ROLL_SLOPE = 8.0 * D2R               # on ground tilted across the foot more than this (a cross slope); a stance of
ROLL_SHORT = 8                       # fewer frames (a turn's step, a stop's) from ROLL_FROM to its end
ROLL_EASE = 5                        # frames: the swing turns the foot onto its stance's roll over its last ones


KNEE_MAX_HUMAN = 150.0 * D2R          # a human knee folds past round one's 112 deg (my robot's hardware stop): a run's
#                                       back-kick swing needs it


def _knee_for(self, side, d):
    """round one's Body.knee_for with the knee's stop as a field (the robot keeps its hinge's 112 deg)"""
    L = self.leg[side]
    u, w = L['u'], L['w']
    lo, hi = 0.0, self.knee_max

    def f(k):
        return (u + Quaternion((1.0, 0.0, 0.0), k) @ w).length
    if d >= f(lo):
        return lo
    if d <= f(hi):
        return hi
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if f(mid) > d:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def sole_subset(h, band=0.015, voxel=0.006):
    """the sole's points for the plant: the foot's points within `band` of its lowest at rest, thinned to `voxel`"""
    return foot_points(h, band=band, voxel=voxel)


def _ground(world, P, z_from=None):
    """the ground under each point: rays from z_from (default 0.6 m above each point) straight down"""
    zf = P[:, 2] + 0.6 if z_from is None else z_from
    return world.h(P[:, 0], P[:, 1], z_from=zf)


def support_plane(world, P, z_from, band=0.015):
    """the plane a sole would rest on: fitted to the ground under its points that lie within `band` of the highest (a
    sole straddling a stair edge rests on the upper tread, its plane is that tread's, not a slope down the riser)
    -> (normal, heights)"""
    G = world.h(P[:, 0], P[:, 1], z_from=z_from)
    ok = G > -1e8
    if ok.sum() < 3:
        return Vector((0.0, 0.0, 1.0)), G
    top = float(G[ok].max())
    m = ok & (G > top - band)
    xs, ys, zs = P[m, 0], P[m, 1], G[m]
    if m.sum() < 3 or np.ptp(xs) * np.ptp(ys) < 1e-4 and max(np.ptp(xs), np.ptp(ys)) < 0.03:
        return Vector((0.0, 0.0, 1.0)), G
    A = np.stack([xs - xs.mean(), ys - ys.mean(), np.ones_like(xs)], axis=1)
    (a, b, _c), *_ = np.linalg.lstsq(A, zs - zs.mean(), rcond=None)
    n = Vector((-a, -b, 1.0)).normalized()
    return (n if n.z >= 0.5 else Vector((0.0, 0.0, 1.0))), G


def plant(body, world, recs, fps, clearance=CLEARANCE, pelvis='stance', face=None, crown_state=None, head_state=None,
          feet=None, log=print, released=None):
    """recs: film.py's per-frame records -> (frames for key_frames, report). A planted foot that its straight leg still
    cannot reach at the end of its stance (the trailing foot on a stair, the hips already risen) is released there:
    the bake runs again with those frames lifted ('released' in the report); a seat's stance (mostly 'seated' frames:
    film.Sit) is not, its feet stay on the floor through the hold and the rise. On my robot body a stance its ankle's
    roll stop held off the ground is baked again with one roll for the whole stance ('rolls_deg')"""
    late = {s: set(v) for s, v in (released or {}).items()}
    for s in SIDES:
        late.setdefault(s, set())
    retime = {}
    frames, rep = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, late,
                         retime)
    for _round in range(3):
        # out of reach, or lifted off by its own toe meeting a riser as it rolls (the trailing foot at a stair's foot):
        # from the first such frame in the stance's second half to its end, the foot is let go (an early toe-off)
        more = {s: set() for s in SIDES}
        more_rt = {}
        f00 = frames[0]['f']
        for s in SIDES:
            other = 'right' if s == 'left' else 'left'
            for row in rep['stances'][s]:
                a, b = row['frames']
                if 2 * sum(frames[f - f00]['mode'] == 'seated' for f in range(a, b + 1)) > b - a + 1:
                    continue        # a seat's stance (film.Sit): its feet rest on the floor through the hold and the rise
                # left behind (the pelvis no longer comes down to it): let go from there whatever the other foot does,
                # an early toe-off. A walk has a foot down at every frame: where the other foot is still in its swing
                # there, that swing is brought forward to land by then (_land_by: the faster step a body moving on
                # faster than the clip's stride takes)
                gone = next((f for f in range(a, b + 1) if frames[f - f00]['meas'][s].get('behind')), None)
                if gone is not None:
                    more[s].update(range(gone, b + 1))
                    rt = _land_by(frames, recs, other, gone - f00)
                    if rt is not None and retime.get((other, rt[0])) != rt:
                        more_rt[(other, rt[0])] = rt
                    continue
                for f in range(a + (b - a + 1) // 2, b + 1):
                    m = frames[f - f00]['meas'][s]
                    if m['ankle_err'] > 0.003 or m['gap'] > 0.002:
                        # let go from the first frame on with the other foot down: a walk does not lift both feet at
                        # once (until the other lands the pelvis comes down to this one instead). Down stairs the
                        # trailing foot leaves the tread above before the other lands (a lower pelvis cannot reach a
                        # foot above it), and a run may fly
                        start = next((x for x in range(f, b + 1) if frames[x - f00]['meas'][other]['stance'] or
                                      recs[x - f00].get('lead') in FLIGHT_SLOTS + STAIR_SLOTS), None)
                        if start is not None:
                            more[s].update(range(start, b + 1))
                        break
        if not any(more[s] - late[s] for s in SIDES) and not more_rt:
            break
        for s in SIDES:
            late[s] |= more[s]
        retime.update(more_rt)
        log(f'[plant] released at the end of their stances (out of reach): '
            f'{ {s: sorted(v) for s, v in more.items() if v} }' +
            (f'; swings brought forward to land by then: '
             f'{ {k[0]: [recs[i]["f"] for i in v] for k, v in more_rt.items()} }' if more_rt else ''))
        frames, rep = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, late,
                             retime)
    # a planted sole that reaches into a riser or a dome's side at any frame of its stance (the landing's fit sees the
    # heel strike; the toes come down into the step ahead as the foot rolls flat, the heel into the step behind as it
    # comes down a stair): the whole stance moved along the foot, as little as keeps every frame out (_tuck_shift)
    tucks = {}

    def rows_by_start(rep_):
        f0_ = frames[0]['f']
        return {(s, row['frames'][0] - f0_): row for s in SIDES for row in rep_['stances'][s]}

    def worse(new, old):
        """a moved stance that came out worse than it was: it now slips, or its sole reads deeper"""
        return new is None or new['slip_mm_per_frame_max'] > max(1.0, old['slip_mm_per_frame_max']) + 0.5 or \
            new['gap_mm'][0] < old['gap_mm'][0]
    for _round in range(2):
        more_t = {}
        f00 = frames[0]['f']
        before = rows_by_start(rep)
        for s in SIDES:
            for row in rep['stances'][s]:
                if row['gap_mm'][0] >= -TUCK_TOL * 1000:
                    continue
                ia, ib = row['frames'][0] - f00, row['frames'][1] - f00
                d = _tuck_shift(world, frames, s, ia, ib)
                if d is not None:
                    more_t[(s, ia)] = tucks.get((s, ia), Vector((0.0, 0.0))) + d
        if not more_t:
            break
        kept_t = dict(tucks)
        tucks.update(more_t)
        moved = {k[0] + ' f' + str(recs[k[1]]['f']): round(1000 * v.length, 1) for k, v in more_t.items()}
        log(f'[plant] stances moved out of a riser (mm): {moved}')
        frames2, rep2 = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log,
                               late, retime, tucks)
        after = rows_by_start(rep2)
        undo = [k for k in more_t if worse(after.get(k), before[k])]
        if undo:
            # a move out of a riser that costs the stance its hold (a sole on a dome's curve rolling as it leaves) is
            # not kept: that stance stays where it landed
            for k in undo:
                if k in kept_t:
                    tucks[k] = kept_t[k]
                else:
                    tucks.pop(k, None)
            log(f'[plant] moves not kept (the stance held worse): '
                f'{[k[0] + " f" + str(recs[k[1]]["f"]) for k in undo]}')
            frames2, rep2 = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log,
                                   late, retime, tucks)
        frames, rep = frames2, rep2
        if undo and len(undo) == len(more_t):
            break
    # my robot body: a planted foot that its ankle's roll stop held off its target in some frame of its stance (a
    # cross slope steeper than the roll reaches) gets one roll off the ground for the whole stance, the most its solved
    # legs needed (_stance_rolls); a stance that came out turning or slipping more is left as it was
    rolls = {}
    if body.robot:
        for _round in range(ROLL_ROUNDS):
            more_r = _stance_rolls(frames, rep, rolls)
            if not more_r:
                break
            kept_r = dict(rolls)
            rolls.update(more_r)
            log(f'[plant] stances held off their roll by the ankle\'s stop, one roll each (deg): '
                f'{ {k[0] + " f" + str(recs[k[1]]["f"]): round(v * R2D, 1) for k, v in more_r.items()} }')
            before = rows_by_start(rep)
            frames2, rep2 = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log,
                                   late, retime, tucks, rolls)
            after = rows_by_start(rep2)
            undo = [k for k in more_r if after.get(k) is None or
                    after[k]['yaw_deg_per_frame_max'] > before[k]['yaw_deg_per_frame_max'] + 0.1 or
                    after[k]['slip_mm_per_frame_max'] > max(1.0, before[k]['slip_mm_per_frame_max']) + 0.5]
            if undo:
                for k in undo:
                    if k in kept_r:
                        rolls[k] = kept_r[k]
                    else:
                        rolls.pop(k, None)
                log(f'[plant] rolls not kept (the stance held worse): '
                    f'{[k[0] + " f" + str(recs[k[1]]["f"]) for k in undo]}')
                frames2, rep2 = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet,
                                       log, late, retime, tucks, rolls)
            frames, rep = frames2, rep2
            if undo and len(undo) == len(more_r):
                break
    rep['released'] = {s: sorted(v) for s, v in late.items()}
    rep['landed_early'] = {k[0] + f' f{recs[k[1]]["f"]}': [recs[i]['f'] for i in v] for k, v in retime.items()}
    rep['tucks_mm'] = {k[0] + f' f{recs[k[1]]["f"]}': round(1000 * v.length, 1) for k, v in tucks.items()}
    rep['rolls_deg'] = {k[0] + f' f{recs[k[1]]["f"]}': round(v * R2D, 2) for k, v in rolls.items()}
    return frames, rep


def _stance_rolls(frames, rep, rolls):
    """my robot body's planted feet that its ankle's roll stop held off their targets on a cross slope: each stance on
    ground tilted across the foot more than ROLL_SLOPE ('cross_tilt') with a frame of its flat part (ROLL_FROM to
    ROLL_TO of it) whose ankle sits at its roll stop ('roll_stop') and whose solved foot is rolled more than ROLL_TOL
    off its target ('roll_off', after the clamps) gets the roll that frame needed added to the stance's roll, for
    every frame of it. The landing's first frames are not counted: the shin still leans as the swing left it and the
    heel comes down on its edge, settling onto the stance's roll as the foot comes flat (the downhill foot on a 20 deg
    slope: held 13 deg off as it lands, 6 through the stance); nor is the heel-off, where the clip's own foot rolls
    onto its toes, but in a stance of fewer than ROLL_SHORT frames (a turn's step) everything from ROLL_FROM on is.
    On level ground (a turn on the spot, a seat) a foot off its target is the hip's or the ankle's other
    stops, not the roll's: no stance there is rolled -> {(side, the stance's first index): roll}"""
    out = {}
    f00 = frames[0]['f']
    for s in SIDES:
        for row in rep['stances'][s]:
            ia, ib = row['frames'][0] - f00, row['frames'][1] - f00
            if max(abs(frames[i]['meas'][s].get('cross_tilt', 0.0)) for i in range(ia, ib + 1)) < ROLL_SLOPE:
                continue
            k0 = ia + int(ROLL_FROM * (ib - ia + 1))
            k1 = ib if ib - ia + 1 < ROLL_SHORT else max(k0, ia + int(ROLL_TO * (ib - ia + 1)))
            offs = [frames[i]['meas'][s].get('roll_off', 0.0) if frames[i]['meas'][s].get('roll_stop') else 0.0
                    for i in range(k0, k1 + 1)]
            k = max(range(len(offs)), key=lambda j: abs(offs[j]), default=None)
            if k is not None and abs(offs[k]) > ROLL_TOL:
                out[(s, ia)] = rolls.get((s, ia), 0.0) + offs[k]
    return out


def _at_roll_stop(q_foot, side, tol=0.05):
    """whether my robot body's clamped ankle (the foot's turn on its shin, Blender's normalized frame) sits at its roll
    stop: the cardan's roll at the end of its range, coupled to the pitch as robot_dof clamps it"""
    J = dof.LEG_JOINTS[2]
    m = 1 if side == 'left' else -1
    q = q_to_three(q_foot)
    x, _y, z = euler_from_quat(q @ twist_about(q, J['noTwist']).inverted(), 'XZY')
    xd, zd = x * R2D, m * z * R2D
    c = J['coupled']
    lo = max(J['range']['z'][0], lerp_table(c['x'], c['zmin'], xd))
    hi = min(J['range']['z'][1], lerp_table(c['x'], c['zmax'], xd))
    return zd >= hi - tol or zd <= lo + tol


def _cross_tilt(fd, W_t):
    """how far the ground a planted foot landed on (its landing surface) tilts across the foot: the surface normal's
    lean toward the foot's side, about its forward (rad); 0 where no surface is known"""
    if 'surface' not in fd:
        return 0.0
    n = fd['surface'][0]
    f = W_t @ FWD
    lat = Vector((-f.y, f.x, 0.0))
    if lat.length < 1e-6:
        return 0.0
    return math.asin(max(-1.0, min(1.0, n.dot(lat.normalized()))))


def _roll_off(W_target, W_foot):
    """how far a solved foot is rolled off its target turn about the target's forward axis (rad, right-handed)"""
    f = (W_target @ FWD).normalized()
    ut, ua = W_target @ Vector((0.0, 0.0, 1.0)), W_foot @ Vector((0.0, 0.0, 1.0))
    ut, ua = ut - f * ut.dot(f), ua - f * ua.dot(f)
    if ut.length < 1e-6 or ua.length < 1e-6:
        return 0.0
    return math.atan2(f.dot(ut.cross(ua)), ut.dot(ua))


TUCK_TOL = 0.0015                     # m: a planted sole point this far under the ground it stands on is in it
TUCK_MAX = 0.06                       # m: the most a stance is moved along its foot out of a riser


def _tuck_shift(world, frames, s, ia, ib):
    """the least move of stance [ia, ib] of foot s along the body's travel (square to a stair's edges; 5 mm steps, at
    most TUCK_MAX, back or forth) that keeps every frame's sole points (as solved) out of the ground they are over (a
    riser's step, a dome's side) and keeps as much of the sole on what it stands on (at least 80 % of it) -> Vector
    (xy) or None"""
    psi = frames[(ia + ib) // 2]['psi']
    f = np.array([math.sin(psi), -math.cos(psi)])
    Ps = [frames[i]['meas'][s]['P'] for i in range(ia, ib + 1)]
    mid = Ps[len(Ps) // 2]

    def on(G):
        """the share of the sole standing on the ground under it (within 1 cm over it, not in it)"""
        gap = mid[:, 2] - G
        return float(np.mean((G > -1e8) & (gap < 0.01) & (gap >= -TUCK_TOL)))
    on0 = on(world.h(mid[:, 0], mid[:, 1], z_from=mid[:, 2] + 0.6))

    def deepest(d):
        lo = 1.0
        for P in Ps:
            Q = P[:, :2] + f * d
            G = world.h(Q[:, 0], Q[:, 1], z_from=P[:, 2] + 0.6)
            ok = G > -1e8
            if ok.any():
                lo = min(lo, float(np.min(P[ok, 2] - G[ok])))
        return lo

    def supported(d):
        Q = mid[:, :2] + f * d
        return on(world.h(Q[:, 0], Q[:, 1], z_from=mid[:, 2] + 0.6)) >= 0.8 * on0
    if deepest(0.0) >= -TUCK_TOL:
        return None
    for k in range(1, int(TUCK_MAX / 0.005) + 1):
        for d in (-0.005 * k, 0.005 * k):
            if deepest(d) >= -TUCK_TOL and supported(d):
                return Vector((f[0] * d, f[1] * d))
    return None


SWING_MIN = 5                         # a swing brought forward keeps at least this many frames...
SWING_SHORT = 0.5                     # ...and this share of its own


def _land_by(frames, recs, o, g):
    """the swing of foot o going on over frame index g (where the other foot is let go) brought forward to land there:
    (a, L, g, E): the swing's first frame, its own landing, g, and the end of the stance it lands into (indices). None
    where o is down at g, a flight gait leads (a run flies), the swing leads into a seat, a maneuver or a fall, or it
    would keep under SWING_SHORT of its frames"""
    n = len(frames)
    m = frames[g]['meas'][o]
    if m['stance'] or m['free'] or recs[g].get('lead') in FLIGHT_SLOTS:
        return None
    a = g
    while a > 0 and not frames[a - 1]['meas'][o]['stance'] and not frames[a - 1]['meas'][o]['free']:
        a -= 1
    L = g
    while L < n and not frames[L]['meas'][o]['stance']:
        if frames[L]['meas'][o]['free']:
            return None
        L += 1
    if L >= n or a == 0:
        return None
    E = L
    while E + 1 < n and frames[E + 1]['meas'][o]['stance']:
        E += 1
    if g - a < max(SWING_MIN, SWING_SHORT * (L - a)):
        return None
    return (a, L, g, E)


def _retime(pb, world, A, recs, s, a, L, g, E, released):
    """foot s's swing [a, L) brought forward to land at g and its stance [L, E] stretched over [g, E]: each frame takes
    the foot's place and turn relative to the root from the clip warped in time (piecewise linear: a -> a, g -> L,
    E -> E), so the swing is the clip's own played faster and lands where the clip lands it relative to the body, the
    stance rolls over the frames it gained"""
    rel = []
    for i in range(a, E + 1):
        r, fd = A[i], A[i]['feet'][s]
        Mi, Qi = r['M'].inverted(), r['Qr'].inverted()
        rel.append({'p_an': Mi @ fd['p_an'], 'p_th': Mi @ fd['p_th'], 'w_off': Qi @ fd['w_off'],
                    'W_ft': Qi @ fd['W_ft'], 'W_to': Qi @ fd['W_to'], 'W_sh': Qi @ fd['W_sh'], 'Ntoes': fd['Ntoes']})

    def at(tau):
        k = min(max(tau - a, 0.0), float(E - a))
        i0 = int(math.floor(k))
        i1 = min(i0 + 1, E - a)
        u = k - i0
        x, y = rel[i0], rel[i1]
        out = {key: x[key].lerp(y[key], u) for key in ('p_an', 'p_th', 'w_off')}
        for key in ('W_ft', 'W_to', 'W_sh', 'Ntoes'):
            q1 = y[key] if x[key].dot(y[key]) >= 0.0 else -y[key]
            out[key] = x[key].slerp(q1, u)
        return out
    for j in range(a, E + 1):
        if j <= g:
            tau = a + (j - a) * (L - a) / float(g - a)
        else:
            tau = L + (j - g) * (E - L) / float(E - g)
        v = at(tau)
        r = A[j]
        M, Q = r['M'], r['Qr']
        fd = r['feet'][s]
        fd['p_an'], fd['p_th'], fd['w_off'] = M @ v['p_an'], M @ v['p_th'], Q @ v['w_off']
        fd['W_ft'], fd['W_to'], fd['W_sh'], fd['Ntoes'] = Q @ v['W_ft'], Q @ v['W_to'], Q @ v['W_sh'], v['Ntoes']
        fd['P'] = pb.sole(s, fd['p_an'], fd['W_ft'], fd['W_to'])
        fd['zlow'] = float(fd['P'][:, 2].min())
        fd['dclip'] = (fd['p_an'] - fd['p_th']).length
        rr = recs[j]
        planted = j >= g and rr['grounded'] and feet_down_mode(rr) and rr['f'] not in released.get(s, ())
        if planted and float(np.max(_ground(world, fd['P']))) < M.translation.z - STANCE_DROP_MAX:
            planted = False
        fd['stance'] = planted


def _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, released,
           retime=None, tucks=None, rolls=None):
    import types
    dt = 1.0 / fps
    pb = copy.copy(body)
    pb.feet = feet or sole_subset(body.h)
    pb.knee_max = 112.0 * D2R if body.robot else KNEE_MAX_HUMAN
    pb.knee_for = types.MethodType(_knee_for, pb)
    n = len(recs)
    # ---- 0/1: the robot's DOF pass on each blended pose, the free FK
    A = []
    for i, r in enumerate(recs):
        N = {nm: r['N'].get(nm, Quaternion()).copy() for nm in body.h.humanoid}
        helpers = {}
        if body.robot:
            # a maneuver's held hands (the record's hand_contact: the contact IK's weight on each) go back where its
            # IK put them, through the hardware, and out of the vault cover one is held over (the record's hand_cover)
            hc = {s: w for s, w in (r.get('hand_contact') or {}).items() if w > 0.01}
            N, helpers = dof_pass(body, N, dt, reach={'M': r['M'], 'off': r['off'], 'hands': hc,
                                                     'covers': r.get('hand_cover') or {}} if hc else None)
        if r.get('after_hardware') is not None:
            # what the frame's maker asks of the pose as the hardware leaves it (a ground sit: the limbs resting on
            # the floor rather than in it)
            pp = Pose(body, r['M'], N, r['off'])
            r['after_hardware'](pp)
            N = pp.N
        M = r['M']
        Qr = M.to_quaternion()
        ph, Wh = pb.hips(M, r['off'], N)
        rec = {'f': r['f'], 'M': M, 'Qr': Qr, 'psi': r['heading'], 'N': N, 'off': r['off'], 'ph0': ph, 'helpers': helpers,
               'mode': r['mode'], 'maneuver': r.get('maneuver'), 'feet': {}, 'z0': M.translation.z,
               'grounded': r['grounded'], 'lead': r.get('lead'), 'backward': bool(r.get('backward')),
               'ground_stance': r.get('ground_stance') or {s: 1.0 for s in SIDES},
               'ground_share': r.get('ground_share', 0.0), 'stair_share': r.get('stair_share', 0.0)}
        fks = {s: pb.leg_fk(s, ph, Wh, N) for s in SIDES}
        # my robot's feet are wider than a human's (robot_dof LEG_CLEARANCE.width): carried out from the clip's narrow
        # track where its ankles come closer than 18-23 cm, as round one's walk_path does
        w_eff = 0.0
        if body.robot:
            sep = abs((Qr.inverted() @ (fks['left']['p_an'] - fks['right']['p_an'])).x)
            w_eff = WIDTH * (1.0 - smooth(NEED[0], NEED[1], sep))
        for s in SIDES:
            fk = fks[s]
            w_off = Vector((0.0, 0.0, 0.0))
            if w_eff > 0:
                fk = dict(fk)
                w_off = Qr @ Vector((w_eff if s == 'left' else -w_eff, 0.0, 0.0))
                fk['p_an'] = fk['p_an'] + w_off
            P = pb.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            st = r['stance'][s]
            planted = (st >= 0.5) and r['grounded'] and feet_down_mode(r) and r['f'] not in released.get(s, ())
            if planted and float(np.max(_ground(world, P))) < M.translation.z - STANCE_DROP_MAX:
                planted = False         # the clip plants it past an edge: nothing to stand on near the body's support
            # a fall (the controller airborne) and a maneuver leave the feet to the clip (a landing, fallLand, stands
            # on the ground it landed on); a seat plants them on the floor under the seated body
            free = not feet_down_mode(r) or not r['grounded']
            rec['feet'][s] = {'p_an': fk['p_an'], 'p_th': fk['p_th'], 'W_ft': fk['W_ft'], 'W_to': fk['W_to'],
                              'W_sh': fk['W_sh'], 'P': P, 'zlow': float(P[:, 2].min()), 'stance': planted, 'free': free,
                              'Ntoes': N[s + 'Toes'] if (s + 'Toes') in N else Quaternion(),
                              'dclip': (fk['p_an'] - fk['p_th']).length, 'p': 0.0, 'u': 0.0, 'w_off': w_off}
        A.append(rec)
    for (s, _a), (a, L, g, E) in sorted((retime or {}).items(), key=lambda kv: kv[1][0]):
        _retime(pb, world, A, recs, s, a, L, g, E, released)
    # a foot handed back from the clip (a maneuver's or a fall's frames just before) is planted once the blend has set
    # it down: its sole within LAND_GAP of the ground and turning under LAND_TURN a frame, at most LAND_MAX frames on,
    # while the other foot stands and its own stance goes on. Until then it ends its swing (a vault's landing foot is
    # still turning as the move fades out: it is planted flat, not mid-roll). Where the blend never sets it down in
    # that time it is planted at the hand-over (a running jump's landing: the stance is short, and the run lifts that
    # foot again)
    for s in SIDES:
        o = 'right' if s == 'left' else 'left'
        for i in range(1, n):
            if not (A[i - 1]['feet'][s]['free'] and A[i]['feet'][s]['stance']) or A[i - 1]['mode'] == 'seat':
                continue                                  # (a seat hands its feet back its own way: _seat_handover)
            j, down = i, False
            while j < min(n - 1, i + LAND_MAX):
                fj, fn = A[j]['feet'][s], A[j + 1]['feet'][s]
                if not fj['stance'] or not fn['stance'] or not A[j]['feet'][o]['stance'] or A[j]['feet'][o]['free']:
                    break
                G = _ground(world, fj['P'])
                ok = G > -1e8
                gap = float(np.min(fj['P'][ok, 2] - G[ok])) if ok.any() else 0.0
                turn = (fj['W_ft'] @ Vector((0.0, 0.0, 1.0))).angle(fn['W_ft'] @ Vector((0.0, 0.0, 1.0)), 0.0)
                if gap <= LAND_GAP and turn <= LAND_TURN:
                    down = True
                    break
                j += 1
            if down:
                for k in range(i, j):
                    A[k]['feet'][s]['stance'] = False
    # stance runs of one frame (and swings of one frame) are blend noise: dropped. A swing of two frames between two
    # stances is too where the foot lands back where it stood (a crossfade's stance weights dipping under a half): no
    # foot lifts, travels and lands in 0.07 s; it stays down. One that carries the foot on (a stair clip coming in
    # with that foot's next stance a step ahead of where it stands) is a step: it starts earlier, to last
    # SWING_MIN_FRAMES, while the other foot stands
    for s in SIDES:
        o = 'right' if s == 'left' else 'left'
        fl = [r['feet'][s]['stance'] for r in A]
        fo = [r['feet'][o]['stance'] for r in A]
        for _ in range(2):
            for i in range(1, n - 1):
                if fl[i] != fl[i - 1] and fl[i] != fl[i + 1]:
                    fl[i] = fl[i - 1]
        for i in range(1, n - 2):
            if fl[i - 1] and not fl[i] and not fl[i + 1] and fl[i + 2] and \
                    not any(A[k]['feet'][s]['free'] for k in (i, i + 1)) and \
                    not any(recs[k]['f'] in released.get(s, ()) for k in (i, i + 1)):
                a0 = i - 1
                while a0 > 0 and fl[a0 - 1]:
                    a0 -= 1
                if (A[i + 2]['feet'][s]['p_an'].xy - A[a0]['feet'][s]['p_an'].xy).length < STEP_NOISE:
                    fl[i] = fl[i + 1] = True
                    continue
                for k in range(i - 1, i + 1 - SWING_MIN_FRAMES, -1):
                    if k <= a0 + 1 or not fo[k]:
                        break
                    fl[k] = False
        for r, v in zip(A, fl):
            r['feet'][s]['stance'] = v
    intervals = {s: _intervals([r['feet'][s]['stance'] for r in A]) for s in SIDES}
    swings = {s: _intervals([(not r['feet'][s]['stance']) and not r['feet'][s]['free'] for r in A]) for s in SIDES}
    for s in SIDES:
        for a, b in intervals[s]:
            for i in range(a, b + 1):
                A[i]['feet'][s]['p'] = (i - a + 0.5) / (b - a + 1)
        for a, b in swings[s]:
            for i in range(a, b + 1):
                A[i]['feet'][s]['u'] = (i - a + 0.5) / (b - a + 1)

    def rz(th, v):
        c, s_ = math.cos(th), math.sin(th)
        return Vector((c * v[0] - s_ * v[1], s_ * v[0] + c * v[1]))

    # ---- 2: THE LOCK (round one's pass B) with the landing's support fit
    for s in SIDES:
        iv = intervals[s]
        yaw_free = [foot_yaw(r['feet'][s]['W_ft'], r['feet'][s]['W_to']) for r in A]
        th0, fit = {}, {}
        for a, b in iv:
            if a > 0 and A[a - 1]['mode'] == 'seat' and A[a - 1]['feet'][s]['free']:
                # the first stance after a seat stands where the seat left the foot (its place and heading): the
                # stand-up's feet stay put, no hand-over step or slide back to where the standing pose has them
                fp = A[a - 1]['feet'][s]
                fit[a] = (fp['p_an'] - fp['w_off']).xy - A[a]['feet'][s]['p_an'].xy
                th0[a] = wrap_pi(yaw_free[a - 1] - yaw_free[a])
                continue
            th0[a] = wrap_pi(yaw_free[(a + b) // 2] - yaw_free[a]) if A[a]['mode'] != 'turn' else 0.0
            fit[a] = _support_fit(world, A[a]['feet'][s], th0[a], boot=(pb, s)) if A[a]['mode'] == 'loco' else \
                Vector((0.0, 0.0))
            fit[a] = fit[a] + (tucks or {}).get((s, a), Vector((0.0, 0.0)))
        delta, theta = Vector((0.0, 0.0)), 0.0
        lift = None
        for i, r in enumerate(A):
            fd = r['feet'][s]
            if fd['free']:
                delta, theta, lift = Vector((0.0, 0.0)), 0.0, None
                fd['lock'] = None
            elif fd['stance']:
                if i in th0:
                    delta, theta = fit[i].copy(), th0[i]
                else:
                    fp = A[i - 1]['feet'][s]
                    z, zp = fd['P'][:, 2], fp['P'][:, 2]
                    both = (z - z.min()) + (zp - zp.min())
                    w = np.exp(-both / LOCK_BAND)
                    ci = Vector((fd['P'][:, :2] * w[:, None]).sum(0) / w.sum())
                    cp = Vector((fp['P'][:, :2] * w[:, None]).sum(0) / w.sum())
                    ai, ap = fd['p_an'].xy, fp['p_an'].xy
                    pivot = r['mode'] == 'turn'
                    th_new = theta if pivot else theta - wrap_pi(yaw_free[i] - yaw_free[i - 1])
                    held = ap + delta + rz(theta, cp - ap)
                    delta = held - ai - rz(th_new, ci - ai)
                    theta = th_new
                lift = None
                fd['lock'] = True
            else:
                if lift is None:
                    nxt = min([a for a, b in iv if a > i], default=None)
                    free_at = _free_ahead(A, s, i, nxt if nxt is not None else n)
                    if free_at is not None:
                        # a fall, a seat or a maneuver comes before the next stance: there is no landing to aim at;
                        # the swing hands its foot to the clip by the free frame (the offset decays to none there)
                        nxt, span = None, max(1, free_at - i)
                    else:
                        span = max(1, int(0.5 * ((nxt if nxt is not None else n) - i)))
                    lift = (i, delta.copy(), theta, fit[nxt] if nxt is not None else Vector((0.0, 0.0)),
                            th0[nxt] if nxt is not None else 0.0, span)
                b0, d0, t0, d1, t1, span = lift
                u = ease((i - b0 + 1) / float(span))
                delta, theta = d0 * (1.0 - u) + d1 * u, t0 + wrap_pi(t1 - t0) * u
                fd['lock'] = None
            fd['delta'], fd['theta'] = delta.copy(), theta

    for s in SIDES:                     # how many frames each foot has stood so far (the early toe-off's double support)
        run = 0
        for r in A:
            run = run + 1 if r['feet'][s]['lock'] is not None else 0
            r['feet'][s]['locked_for'] = run

    # ---- 3: each foot's target turn and xy (round one's pass C)
    def tilt_w(s, i):
        best = 0.0
        for a, b in intervals[s]:
            if a <= i <= b:
                return 1.0
            dd = (a - i) if i < a else (i - b)
            best = max(best, 1.0 - dd / 5.0)
        return max(0.0, best)

    # my robot body: each stance's roll (_stance_rolls) on its frames, and eased in and out over ROLL_EASE frames of the
    # swings either side (the foot turns onto it in the air, not on the ground)
    roll_of, roll_w = {}, {}
    for (s, a), v in (rolls or {}).items():
        b = next((b_ for a_, b_ in intervals[s] if a_ == a), a)
        for i in range(max(0, a - ROLL_EASE), min(n - 1, b + ROLL_EASE) + 1):
            w = 1.0 if a <= i <= b else ease(1.0 - (a - i if i < a else i - b) / float(ROLL_EASE + 1))
            if w > roll_w.get((s, i), 0.0) and not A[i]['feet'][s]['free'] and \
                    (a <= i <= b or A[i]['feet'][s]['lock'] is None):
                roll_of[(s, i)], roll_w[(s, i)] = v * w, w
    for s in SIDES:
        for i, r in enumerate(A):
            fd = r['feet'][s]
            xy = fd['p_an'].xy + fd['delta']
            W = Quaternion((0.0, 0.0, 1.0), fd['theta']) @ fd['W_ft']
            fd['xy'] = xy
            fd['wt'] = 0.0 if fd['free'] else tilt_w(s, i)
            up = W @ Vector((0.0, 0.0, 1.0))
            ang = up.angle(Vector((0.0, 0.0, 1.0)), 0.0)
            fl = fd['wt'] * (1.0 - smooth(0.45, 0.6, fd['p'])) if fd['lock'] is not None else fd['wt']
            if ang > 1e-7 and fl > 0.0:
                W = Quaternion(up.cross(Vector((0.0, 0.0, 1.0))).normalized(), min(ang, FLAT) * fl) @ W
            Wt = W @ fd['Ntoes']
            P = pb.sole(s, Vector((xy.x, xy.y, fd['p_an'].z)), W, Wt)
            nrm, _z = support_plane(world, P, fd['p_an'].z + 0.6)
            tilt = Vector((0.0, 0.0, 1.0)).rotation_difference(nrm)
            tq = Quaternion().slerp(tilt, fd['wt'])
            fd['W_t'] = tq @ W
            if body.robot and fd['lock'] is not None:
                # inside my ankle's pitch range as the clip's shin would leave it (a heel strike, a heel-off, a steep
                # ramp). Its roll is not that clamp's: measured against the clip's shin it followed the shin's lean
                # frame by frame and rolled a planted sole on a cross slope; it is the stance's own (_stance_rolls)
                Wsh = Quaternion((0.0, 0.0, 1.0), fd['theta']) @ fd['W_sh']
                q3 = dof.project_joint(q_to_three(Wsh.inverted() @ fd['W_t']), dof.LEG_JOINTS[2], 1 if s == 'left' else -1)
                D = (Wsh @ q_from_three(q3)) @ fd['W_t'].inverted()
                f_ax = (fd['W_t'] @ FWD).normalized()
                D = D @ twist_about(D, f_ax).inverted()
                fd['W_t'] = D @ Quaternion(f_ax, roll_of.get((s, i), 0.0)) @ fd['W_t']
            elif (s, i) in roll_of:
                fd['W_t'] = Quaternion((fd['W_t'] @ FWD).normalized(), roll_of[(s, i)]) @ fd['W_t']
            fwd = W @ FWD
            Nt = fd['Ntoes']
            if fd['lock'] is not None and fwd.z < 0.0:
                flat = tq @ Quaternion((0.0, 0.0, 1.0), foot_yaw(W, W @ Nt) - math.atan2(FWD.y, FWD.x))
                Nt = fd['W_t'].inverted() @ flat
            fd['Ntoes_t'] = Nt
            fd['W_toes_t'] = fd['W_t'] @ Nt
            fd['P_plan'] = pb.sole(s, Vector((xy.x, xy.y, 0.0)), fd['W_t'], fd['W_toes_t'])

    # ---- 4: the heights. Stance: the lowest sole point on the ground. Swing: the line between the plants plus the
    # clip's arc over it (in the body's frame), at least `clearance` over the swept ground's envelope mid-swing
    for s in SIDES:
        for i, r in enumerate(A):
            fd = r['feet'][s]
            P = fd['P_plan']
            G = _ground(world, P, z_from=fd['p_an'].z + 0.6)
            G = np.where(G < -1e8, P[:, 2] * 0 + r['z0'], G)
            fd['G'] = G
            fd['z_stance'] = float(np.max(G - P[:, 2]))
            fd['low_off'] = float(P[:, 2].min())
        # a planted foot keeps the surface it landed on: a heel that creeps over a higher edge mid-stance (a blend
        # turning the planted sole) does not lift the foot onto that edge. That surface is the landing's own plane: a
        # tread's level, or a slope's incline (a level there would sink a foot planted on a 45 deg ramp into it)
        for a, b in intervals[s]:
            Ga = A[a]['feet'][s]['G']
            plane = landing_surface(A[a]['feet'][s]['P_plan'], Ga)
            # nowhere under the ground the landing stood on, less SURFACE_DROP: a plane fitted where a floor meets a
            # dome's foot runs steeply down past the footprint, and a rolling sole reaches out over it
            lo = float(np.min(Ga[Ga > -1e8])) - SURFACE_DROP if (Ga > -1e8).any() else -np.inf
            for i in range(a, b + 1):
                fd = A[i]['feet'][s]
                fd['surface'] = plane
                fd['surface_lo'] = lo
                lim = np.maximum(plane_z(plane, fd['P_plan']) + 0.01, lo)
                if np.any(fd['G'] > lim):
                    fd['G'] = np.minimum(fd['G'], lim)
                    fd['z_stance'] = float(np.max(fd['G'] - fd['P_plan'][:, 2]))
        for a, b in swings[s]:
            pa = a - 1 if a > 0 and A[a - 1]['feet'][s]['lock'] else None
            pz = b + 1 if b + 1 < n and A[b + 1]['feet'][s]['lock'] else None
            # the sweep: the ground under the sole now and half a frame either way, then the envelope
            Gs = []
            for i in range(a, b + 1):
                fd = A[i]['feet'][s]
                P = fd['P_plan']
                g = fd['G']
                for nb in (i - 1, i + 1):
                    if 0 <= nb < n:
                        Q = 0.5 * (P[:, :2] + A[nb]['feet'][s]['P_plan'][:, :2])
                        gq = world.h(Q[:, 0], Q[:, 1], z_from=fd['p_an'].z + 0.6)
                        g = np.maximum(g, np.where(gq < -1e8, g, gq))
                Gs.append(float(np.max(g)))
            Gs = np.array(Gs)
            m = len(Gs)
            env = np.array([max(Gs[j] - abs(j - k) * dt * SWEEP_RATE for j in range(m)) for k in range(m)])
            rel0 = (A[pa]['feet'][s]['p_an'].z - A[pa]['z0']) if pa is not None else None
            rel1 = (A[pz]['feet'][s]['p_an'].z - A[pz]['z0']) if pz is not None else None
            for k, i in enumerate(range(a, b + 1)):
                fd = A[i]['feet'][s]
                u = (i - (a - 1)) / float((b + 1) - (a - 1))
                if pa is not None and pz is not None:
                    base = (1 - ease(u)) * A[pa]['feet'][s]['z_stance'] + ease(u) * A[pz]['feet'][s]['z_stance']
                    line = (1 - ease(u)) * rel0 + ease(u) * rel1
                elif pa is not None:
                    base, line = A[pa]['feet'][s]['z_stance'], rel0
                elif pz is not None:
                    base, line = A[pz]['feet'][s]['z_stance'], rel1
                else:
                    base, line = fd['z_stance'], fd['p_an'].z - A[i]['z0']
                arc = max(0.0, (fd['p_an'].z - A[i]['z0']) - line)
                fd['lift_min'] = clearance * _bump(u) if r_has_ground(A[i]) else 0.0
                if r_has_ground(A[i]) and i > 0:
                    # a swinging foot travelling over the ground faster than 0.8 m/s is off it (a toe-off, a backward
                    # walk's lift): never left within the contact band to drag across the surface
                    v = (fd['xy'] - A[i - 1]['feet'][s]['xy']).length / dt
                    if v > 0.8:
                        fd['lift_min'] = max(fd['lift_min'], CONTACT + 0.0015)
                z_min = env[k] + fd['lift_min'] - fd['low_off']
                fd['z_an'] = max(base + arc, z_min)
                fd['z_base'] = base
        for i, r in enumerate(A):
            fd = r['feet'][s]
            if fd['lock'] is not None:
                fd['z_an'] = fd['z_stance']
                fd['lift_min'] = 0.0
            elif fd['free']:
                fd['z_an'] = fd['p_an'].z
                fd['lift_min'] = 0.0
            fd['T'] = Vector((fd['xy'].x, fd['xy'].y, fd['z_an']))

    # ---- 5: the pelvis
    def leg_dxy(r, s):
        """how far leg s's target lies from its hip, along the ground"""
        fd = r['feet'][s]
        p_th = r['ph0'] + (r['Qr'] @ r['N']['hips']) @ body.leg[s]['hip']
        return math.hypot(fd['T'].x - p_th.x, fd['T'].y - p_th.y)

    def leg_dz(r, s, L):
        """the root's rise (from where the controller put it) at which leg s is L from its target"""
        fd = r['feet'][s]
        p_th = r['ph0'] + (r['Qr'] @ r['N']['hips']) @ body.leg[s]['hip']
        dxy = math.hypot(fd['T'].x - p_th.x, fd['T'].y - p_th.y)
        return fd['T'].z - p_th.z + (math.sqrt(L * L - dxy * dxy) if dxy < L else 0.0)

    def left_behind(r, s):
        """a planted foot the body has walked on from: farther from its hip along the ground than TRAIL_NONE of the
        leg's reach, or behind the hip and reachable only with the pelvis more than TRAIL_DIP under the controller's
        own (a stair clip's long stance kept it planted while the body climbed on: the trailing foot on the floor 0.6 m
        behind a body 28 cm up the 22 cm stairs). It carries no load: it neither pulls the pelvis down nor caps it; out
        of reach, the release rounds let it go (an early toe-off)"""
        dxy = leg_dxy(r, s)
        R_ = body.leg[s]['reach']
        if dxy > TRAIL_NONE * R_:
            return True
        fd = r['feet'][s]
        fwd = Vector((math.sin(r['psi']), -math.cos(r['psi'])))
        p_th = r['ph0'] + (r['Qr'] @ r['N']['hips']) @ body.leg[s]['hip']
        behind = (fd['T'].xy - p_th.xy).dot(fwd) < -TRAIL_BEHIND
        if not behind:
            return False
        dip = -leg_dz(r, s, R_ - REACH_MARGIN)
        # a stance the walk (or the run) has already ended, held on only by a stair clip blending in (a step up onto a
        # low block: the stair clip's long stance keeps the walk's trailing foot down after the walk lifted it): a
        # trailing foot late in it toes off as the walk lifts it rather than pull the hips down. Only in a forward walk
        # the walk still carries (TRAIL_GROUND_SHARE: on a 45 deg ramp the stair clip leads and its long trailing
        # stance is the climb's own), with a stair clip in the blend
        # (TRAIL_STAIR_SHARE: at a stop the idle coming in holds both feet down, and the trailing one stays), once the
        # other foot has stood TRAIL_DOUBLE frames (the weight crosses first)
        o = 'right' if s == 'left' else 'left'
        late = (r['mode'] == 'loco' and not r['backward'] and r['ground_share'] >= TRAIL_GROUND_SHARE and
                r['stair_share'] >= TRAIL_STAIR_SHARE and r['ground_stance'][s] < 0.5 and fd['p'] >= TRAIL_LATE and
                r['feet'][o].get('locked_for', 0) >= TRAIL_DOUBLE)
        return dip > TRAIL_DIP or (late and dip > TRAIL_DIP_LATE)

    def carried(r, s):
        """the share of the body's load leg s's planted foot can carry by where it stands: all of it within TRAIL_FULL
        of the leg's reach from its hip along the ground, none past TRAIL_NONE or left behind (a double support hands
        the load to the leading leg as the body moves on; the trailing foot toes off)"""
        if left_behind(r, s):
            return 0.0
        R_ = body.leg[s]['reach']
        return 1.0 - smooth(TRAIL_FULL * R_, TRAIL_NONE * R_, leg_dxy(r, s))
    for r in A:
        for s in SIDES:
            r['feet'][s]['behind'] = r['feet'][s]['lock'] is not None and left_behind(r, s)
    load = {s: hann_smooth([1.0 if r['feet'][s]['lock'] is not None else 0.0 for r in A], LOAD_FRAMES) for s in SIDES}
    # the shortest each leg can be: hip to ankle with the knee at its stop (the floor under the pelvis='controller'
    # root: a body lower than that cannot fold the planted leg any more, its sole would go into the ground)
    fold = {s: (body.leg[s]['u'] + Quaternion((1.0, 0.0, 0.0), pb.knee_max) @ body.leg[s]['w']).length for s in SIDES}
    dz_nom, has = [], []
    for i, r in enumerate(A):
        w = {s: load[s][i] for s in SIDES if not r['feet'][s]['free']}
        own = pelvis == 'controller' or not ground_mode(r) or not r['grounded']   # the root as the controller has it
        if own or not w or sum(w.values()) < 1e-3:
            dz = 0.0
            if pelvis == 'controller' and ground_mode(r) and r['grounded']:
                lows = [leg_dz(r, s, fold[s] + REACH_MARGIN) for s in SIDES if r['feet'][s]['lock'] is not None]
                dz = max([0.0] + lows)
            dz_nom.append(dz if own else None)
            has.append(own)
            continue
        # each planted leg weighs by its load and by where its foot stands (carried): a stair clip's bent stance knee
        # on a foot the body had walked 0.5-0.8 m on from dragged the pelvis 35-70 cm down (the stress course: she
        # knelt and fell into the splits between the stairs and the ramp); no leg carrying the body (a lone stance foot
        # left behind): the controller's own height
        ws = {s: max(v, 1e-6) * max(0.02, carried(r, s)) for s, v in w.items()}
        tot = sum(ws.values())
        nom = sum(ws[s] * leg_dz(r, s, r['feet'][s]['dclip']) for s in ws) / tot
        dz_nom.append(nom * min(1.0, tot / LOAD_MIN))
        has.append(True)
    idx = np.arange(n)
    ok = np.array(has)
    if ok.any() and not ok.all():
        vals = np.array([d if d is not None else 0.0 for d in dz_nom])
        vals[~ok] = np.interp(idx[~ok], idx[ok], vals[ok])               # a flight: carried between the supports
        dz_nom = list(vals)
    elif not ok.any():
        dz_nom = [0.0] * n
    cap = []
    for i, r in enumerate(A):
        c = 1e9
        for s in SIDES:
            fd = r['feet'][s]
            # a foot left behind is not reached for, planted or just let go (its swing starts back there)
            if fd['wt'] > 0.0 and not fd['free'] and not left_behind(r, s):
                c = min(c, leg_dz(r, s, body.leg[s]['reach'] - REACH_MARGIN))
        cap.append(c)
    down, upr = 0.4 / fps, 0.5 / fps
    # a frame whose feet are both the clip's (a maneuver, a fall) keeps the controller's root exactly: its contacts
    # (hands on a lip, feet on rungs or out of a wall) were solved against it, and the smoothing and the rate envelope
    # below would carry a neighbour's offset in (a mount's last crouch sunk into the top it ends on)
    own_root = [all(r['feet'][s]['free'] for s in SIDES) for r in A]

    def shape(z_nom, hard):
        H = [min(hard[min(n - 1, max(0, i + k))] + (k * down if k > 0 else -k * upr) for k in range(-10, 11))
             for i in range(n)]
        out = [min(a, b) for a, b in zip(hann_smooth([min(a, b) for a, b in zip(z_nom, H)], 1), H)]
        return [0.0 if k else v for k, v in zip(own_root, out)]
    hard = list(cap)
    dzr = shape(dz_nom, hard)

    # ---- 6: the solve, the lock on the result, the pelvis lowered where a planted leg is short
    weights = dict(face or {})

    def solve(dzr):
        head, crown = dof.HeadState(), dof.Crown()
        frames = []
        run = {s: Vector((0.0, 0.0)) for s in SIDES}
        run_yaw = {s: 0.0 for s in SIDES}
        prev = {s: None for s in SIDES}
        lift = {s: None for s in SIDES}
        for i, r in enumerate(A):
            frames.append(_solve_frame(pb, world, A, intervals, i, r, dzr[i], run, run_yaw, prev, lift, head, crown,
                                       weights, dt, crown_state, head_state))
        return frames

    frames = solve(dzr)
    lowered = []
    for _round in range(4):
        short = []
        for i, fr in enumerate(frames):
            d = 0.0
            for s in SIDES:
                m = fr['meas'][s]
                if m['stance'] and fr['N'][s + 'LowerLeg'].to_axis_angle()[1] < 3.0 * D2R and \
                        not left_behind(A[i], s):
                    d = max(d, m['gap'], 0.5 * m['ankle_err_xy'])
            short.append(min(d, 0.03))
        if max(short) < 0.0005:
            break
        lowered.append([A[int(np.argmax(short))]['f'], round(1000 * max(short), 2), sum(1 for d in short if d >= 0.0005)])
        hard = [min(hh, z - d - 0.001) if d >= 0.0005 else hh for hh, z, d in zip(hard, dzr, short)]
        dzr = shape(dz_nom, hard)
        frames = solve(dzr)
    rep = report(frames, intervals, A, fps, clearance)
    rep['pelvis_lowered_mm'] = lowered
    rep['_root'] = {'dz': dzr, 'dz_nom': dz_nom, 'cap': cap}
    return frames, rep


def landing_surface(P, G, resid=0.012, jump=0.012):
    """the surface a sole lands on: (normal, a point, kind). 'plane': the ground under all its points lies on one plane
    within `resid` (a tread, a ramp). 'smooth': no plane, but no jump either between sole points within 2.5 cm of each
    other (a dome, a boulder: the foot rests on the curve itself, nothing clamps it). 'level': an edge under the sole
    (a stair's nose): the highest level under it, the upper tread"""
    ok = G > -1e8
    if ok.sum() >= 3:
        xs, ys, zs = P[ok, 0], P[ok, 1], G[ok]
        A = np.stack([xs - xs.mean(), ys - ys.mean(), np.ones_like(xs)], axis=1)
        (a, b, c0), *_ = np.linalg.lstsq(A, zs - zs.mean(), rcond=None)
        fit = a * (xs - xs.mean()) + b * (ys - ys.mean()) + c0 + zs.mean()
        n = Vector((-a, -b, 1.0)).normalized()
        c = Vector((float(xs.mean()), float(ys.mean()), float(c0 + zs.mean())))
        if n.z > 0.5:
            if float(np.max(np.abs(fit - zs))) < resid:
                return n, c, 'plane'
            Q = np.stack([xs, ys], axis=1)
            near = ((Q[:, None, :] - Q[None, :, :]) ** 2).sum(-1) < 0.025 ** 2
            if float(np.abs(zs[:, None] - zs[None, :])[near].max()) < jump:
                return n, c, 'smooth'
    top = float(np.max(G[ok])) if ok.any() else 0.0
    return Vector((0.0, 0.0, 1.0)), Vector((0.0, 0.0, top)), 'level'


def plane_z(plane, P):
    """the landed-on surface's heights under points (n, 3): a plane's or a level's; a smooth curve sets no limit"""
    n, c, kind = plane
    if kind == 'smooth':
        return np.full(len(P), np.inf)
    return c.z - (n.x * (P[:, 0] - c.x) + n.y * (P[:, 1] - c.y)) / n.z


def _free_ahead(A, s, i, end):
    """the first frame in [i, end) whose foot s is left to the clip (a fall, a seat, a maneuver), or None"""
    for j in range(i, min(end, len(A))):
        if A[j]['feet'][s]['free']:
            return j
    return None


def foot_yaw(W_ft, W_to=None):
    """a foot's heading on the ground at any pitch: its forward's horizontal part weighted by itself plus its up's
    horizontal part weighted by the forward's drop. A foot pitched by p (no roll) has forward.xy = cos p h and up.xy =
    sin p h, so the sum is exactly h: steady on the heel, flat and on the toes alike (the forward's own heading is
    undefined when the foot stands steeply on its toes; switching to another bone's jumps)"""
    f = W_ft @ FWD
    u = W_ft @ Vector((0.0, 0.0, 1.0))
    hf = math.hypot(f.x, f.y)
    return math.atan2(f.y * hf - u.y * f.z, f.x * hf - u.x * f.z)


def ground_yaw(W_ft, W_to, nrm):
    """a foot's heading on the ground it stands on: foot_yaw in the frame that lays that ground (normal nrm) flat. On a
    cross slope a rolled foot's pitch (a heel strike, a heel-off) reads as a turn in the world's frame (up's sideways
    lean times the forward's drop), so a lock holding that heading turns the planted foot a degree or two a frame"""
    if nrm.z > 0.9999:
        return foot_yaw(W_ft, W_to)
    q = Vector((0.0, 0.0, 1.0)).rotation_difference(nrm).inverted()
    return foot_yaw(q @ W_ft, q @ W_to)


def _surface_normal(fd, stance):
    return fd['surface'][0] if stance and 'surface' in fd else Vector((0.0, 0.0, 1.0))


def ground_mode(r):
    """a frame whose body stands on its feet (the pelvis follows the planted legs): locomotion, an emote, a turn on the
    spot, a landing (fallLand)"""
    return r['mode'] in ('loco', 'emote', 'turn') or (r['mode'] == 'maneuver' and r.get('maneuver') == 'land')


def feet_down_mode(r):
    """a frame whose feet stand on the ground: the standing modes and a seat (its pelvis is the seat's, its feet on
    the floor under it)"""
    return ground_mode(r) or r['mode'] == 'seated'


def r_has_ground(r):
    return r['grounded'] and feet_down_mode(r)


def _boot_inside(world, pb, s, fd, th0, shift, top):
    """does the whole boot of a landing (its foot turned by th0 about the ankle and moved by shift, resting on `top`)
    reach into a solid (a stair's riser behind or ahead of it)?"""
    from .maneuvers import _inside
    F = getattr(pb, '_feet_full', None)
    if F is None:
        from ..ground import foot_points
        F = pb._feet_full = foot_points(pb.h, band=0.30, voxel=0.012)
    if F.get(s) is None:
        return False
    W = Quaternion((0.0, 0.0, 1.0), th0) @ fd['W_ft']
    Wt = W @ fd['Ntoes']
    an = fd['p_an'] + Vector((shift.x, shift.y, 0.0))
    P = [F[s]['Foot'] @ np.array(W.to_matrix()).T + np.array(an)]
    if len(F[s]['Toes']):
        P.append(F[s]['Toes'] @ np.array(Wt.to_matrix()).T + np.array(an + W @ pb.leg[s]['t']))
    P = np.concatenate(P)
    P[:, 2] += top - float(P[:, 2].min())                     # the boot standing on its support
    G = world.h(P[:, 0], P[:, 1], z_from=P[:, 2] + 0.6)
    for i in np.flatnonzero((G > -1e8) & (G - P[:, 2] > 0.003)):
        if _inside(world, P[i]):
            return True
    return False


def _support_fit(world, fd, th0, boot=None):
    """a landing moved along the foot (at most FIT_RANGE) to where most of its sole is supported: the shift (xy). With
    boot=(plant body, side) the whole boot must also stay out of every solid there (a descent's heel against the riser
    behind it): the nearest shift that keeps it out and most of the support is taken"""
    sh = _support_shift(world, fd, th0)
    if boot is None:
        return sh
    pb, s = boot
    P = fd['P']
    G0 = world.h(P[:, 0], P[:, 1], z_from=fd['p_an'].z + 0.6)
    if not (G0 > -1e8).any():
        return sh
    if landing_surface(P, G0)[2] == 'smooth' or landing_surface(P, G0)[0].z < 0.995:
        return sh                         # a slope or a curve: the boot is not standing on a level (a tread) there
    W = Quaternion((0.0, 0.0, 1.0), th0) @ fd['W_ft']
    f = W @ FWD
    f = Vector((f.x, f.y))
    if f.length < 1e-6:
        return sh
    f.normalize()
    d0 = sh.dot(f)

    def support(here):
        Q = P[:, :2] + np.array(here)
        G = world.h(Q[:, 0], Q[:, 1], z_from=fd['p_an'].z + 0.6)
        ok = G > -1e8
        if not ok.any():
            return None, 0.0
        top = float(G[ok].max())
        if top < float(G0[G0 > -1e8].max()) - STEP_FIT_MAX:
            return None, 0.0
        return top, float(np.mean(G[ok] > top - 0.01)) * ok.mean()
    top0, frac0 = support(sh)
    if top0 is None or not _boot_inside(world, pb, s, fd, th0, sh, top0):
        return sh
    # the boot reaches into a riser: the nearest shift (at most BOOT_FIT more, a heel's or a toe's tuck) that keeps it
    # out and keeps the support; none (a tread shorter than the boot): the support's own landing
    for k in range(1, int(BOOT_FIT / 0.01) + 1):
        for d in (d0 + k * 0.01, d0 - k * 0.01):
            if abs(d) > FIT_RANGE + 1e-9:
                continue
            here = f * d
            top, frac = support(here)
            if top is None or frac < max(0.6, 0.9 * frac0):
                continue
            if not _boot_inside(world, pb, s, fd, th0, here, top):
                return here
    return sh


def _support_shift(world, fd, th0):
    """a landing moved along the foot (at most FIT_RANGE) to where most of its sole is supported: the shift (xy)"""
    P = fd['P']
    W = Quaternion((0.0, 0.0, 1.0), th0) @ fd['W_ft']
    f = W @ FWD
    f = Vector((f.x, f.y))
    if f.length < 1e-6:
        return Vector((0.0, 0.0))
    f.normalize()
    an = fd['p_an']
    Pc = P[:, :2] - np.array(an.xy)
    Pr = np.stack([math.cos(th0) * Pc[:, 0] - math.sin(th0) * Pc[:, 1],
                   math.sin(th0) * Pc[:, 0] + math.cos(th0) * Pc[:, 1]], axis=1) + np.array(an.xy)
    zf = an.z + 0.6

    def ground(d):
        Q = Pr + np.array([f.x * d, f.y * d])
        G = world.h(Q[:, 0], Q[:, 1], z_from=zf)
        return G[G > -1e8]
    G0 = ground(0.0)
    if len(G0) == 0:
        return Vector((0.0, 0.0))
    top0 = float(G0.max())

    def frac(d):
        """the share of the sole on the surface a shift d stands on; a surface more than a stair's rise (0.30 m) under
        the landing's own is no support for it (a shift wholly past an edge onto the ground below)"""
        G = G0 if d == 0.0 else ground(d)
        if not len(G):
            return 0.0
        top = float(G.max())
        if top < top0 - STEP_FIT_MAX:
            return 0.0
        return float(np.mean(G > top - 0.01))
    base = frac(0.0)
    if base >= 0.85:
        return Vector((0.0, 0.0))
    best, bd = base, 0.0
    for k in range(1, int(FIT_RANGE / 0.01) + 1):
        for d in (k * 0.01, -k * 0.01):
            fr = frac(d)
            if fr > best + 0.05:
                best, bd = fr, d
    return Vector((f.x * bd, f.y * bd))


def _solve_frame(pb, world, A, intervals, i, r, dz, run, run_yaw, prev, lift, head, crown, weights, dt, crown_state,
                 head_state):
    body = pb
    M = Matrix.Translation(Vector((0.0, 0.0, dz))) @ r['M']
    N = dict(r['N'])
    for s in SIDES:
        if not r['feet'][s]['free'] and (s + 'Toes') in N:
            N[s + 'Toes'] = r['feet'][s]['Ntoes_t']
    ph, Wh = body.hips(M, r['off'], N)
    T, Wt, st_now, yaw_acc, free = {}, {}, {}, {}, {}
    n = len(A)
    for s in SIDES:
        fd = r['feet'][s]
        st_now[s] = fd['lock'] is not None
        free[s] = fd['free']
        if not st_now[s]:
            if lift[s] is None:
                nxt = min([a for a, b in intervals[s] if a > i], default=n)
                free_at = _free_ahead(A, s, i, nxt)
                span = max(1, free_at - i) if free_at is not None else max(1, int(0.5 * (nxt - i)))
                lift[s] = (i, run[s].copy(), run_yaw[s], span)
            b0, r0, y0, span = lift[s]
            k = 1.0 - ease((i - b0 + 1) / float(span))
            run[s], run_yaw[s] = r0 * k, y0 * k
        else:
            lift[s] = None
        T[s] = fd['T'] + Vector((run[s].x, run[s].y, 0.0))
        Wt[s] = Quaternion((0.0, 0.0, 1.0), run_yaw[s]) @ fd['W_t']
        yaw_acc[s] = run_yaw[s]
    stages = {}
    for _it in range(LOCK_ROUNDS + 1):
        for s in SIDES:
            if not free[s]:
                body.solve_leg(s, ph, Wh, N, T[s], Wt[s], swivel=r['feet'][s]['wt'])
        stages = body.project_legs(N, stages=True)
        if _it == LOCK_ROUNDS:
            break
        for s in SIDES:
            if free[s]:
                continue
            fd = r['feet'][s]
            fk = body.leg_fk(s, ph, Wh, N)
            P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            G = _ground(world, P)
            if st_now[s] and 'surface' in fd:
                # the surface it landed on, not an edge it crept over
                G = np.minimum(G, np.maximum(plane_z(fd['surface'], P) + 0.01, fd.get('surface_lo', -np.inf)))
            gap = P[:, 2] - G
            pv = prev[s]
            if st_now[s] and pv is not None and pv['stance']:
                old = pv['gaps'] < 0.0005
                k1 = int(np.argmin(gap))
                if _it < LOCK_ROUNDS - 3 and old.any() and not old[k1] and float(gap[old].min() - gap[k1]) > 0.0003:
                    co = P[old].mean(0)
                    v = Vector((co[0] - P[k1][0], co[1] - P[k1][1], 0.0))
                    if v.length > 0.02:
                        # a rigid sole rolling on curved ground turns a degree or two a frame; more is the clip's own
                        # roll (a blend turning the foot), which the next rounds settle: capped
                        R = Quaternion(Vector((0.0, 0.0, 1.0)).cross(v).normalized(),
                                       min(TWO_POINT_MAX, math.atan2(float(gap[old].min() - gap[k1]), v.length)))
                        pk = Vector(P[k1])
                        Wt[s] = R @ Wt[s]
                        T[s] = pk + R @ (T[s] - pk)
                both = gap + pv['gaps']
                w = np.exp(-(both - both.min()) / LOCK_BAND)
                c_now = (P[:, :2] * w[:, None]).sum(0) / w.sum()
                d = ((P[:, :2] - pv['P'][:, :2]) * w[:, None]).sum(0) / w.sum()
                if _it >= LOCK_ROUNDS - 2:
                    # the last rounds pin the contact point that moved least (a rigid sole in contact turns about a
                    # point that stays: the heel's edge at the strike, the ball at the push-off)
                    c = (gap < CONTACT) & (pv['gaps'] < CONTACT)
                    if c.any():
                        mv = P[c, :2] - pv['P'][c, :2]
                        d = mv[int(np.argmin(np.linalg.norm(mv, axis=1)))]
                T[s] = T[s] - Vector((d[0], d[1], 0.0))
                if r['mode'] != 'turn':
                    nrm = _surface_normal(fd, st_now[s])
                    dy = wrap_pi(ground_yaw(fk['W_ft'], fk['W_to'], nrm) - pv['yaw'])
                    dy = clamp(dy, yaw_acc[s] - YAW_CAP, yaw_acc[s] + YAW_CAP)
                    if abs(dy) > 1e-9:
                        R = Quaternion(nrm, -dy)
                        Wt[s] = R @ Wt[s]
                        a_ = R @ Vector((T[s].x - c_now[0], T[s].y - c_now[1], 0.0))
                        T[s].x, T[s].y = c_now[0] + a_.x, c_now[1] + a_.y
                        yaw_acc[s] -= dy
            if st_now[s]:
                T[s].z -= float(gap.min()) * fd['wt']
            elif r_has_ground(r) and gap.min() < fd['lift_min'] - 0.001:
                T[s].z += fd['lift_min'] - 0.001 - float(gap.min())
    for s in SIDES:
        if st_now[s]:
            run[s] = Vector((T[s].x - r['feet'][s]['T'].x, T[s].y - r['feet'][s]['T'].y))
            run_yaw[s] = yaw_acc[s]
    petals = None
    if body.robot:
        p3 = {n_: q_to_three(q) for n_, q in N.items()}
        head.apply(p3, weights, dt, state=head_state)
        petals = crown.apply(weights, dof.head_roll_deg(p3), dt, state=crown_state)
        N = {n_: q_from_three(q) for n_, q in p3.items()}
    meas = {}
    for s in SIDES:
        fk = body.leg_fk(s, ph, Wh, N)
        P = body.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
        gap = P[:, 2] - _ground(world, P)
        meas[s] = {'gap': float(gap.min()), 'P': P, 'gaps': gap, 'ankle_err': (fk['p_an'] - T[s]).length,
                   'T': T[s].copy(), 'ankle': fk['p_an'].copy(),
                   'ankle_err_xy': (fk['p_an'] - T[s]).xy.length, 'stance': st_now[s], 'free': free[s],
                   'behind': bool(r['feet'][s].get('behind')),
                   'yaw': ground_yaw(fk['W_ft'], fk['W_to'], _surface_normal(r['feet'][s], st_now[s])),
                   'lift_min': r['feet'][s]['lift_min'], 'mode': r['mode'],
                   'roll_off': _roll_off(Wt[s], fk['W_ft']) if body.robot and st_now[s] else 0.0,
                   'roll_stop': _at_roll_stop(N[s + 'Foot'], s) if body.robot and st_now[s] else False,
                   'cross_tilt': _cross_tilt(r['feet'][s], Wt[s]) if st_now[s] else 0.0}
        prev[s] = meas[s]
    return {'f': r['f'], 'M': M, 'N': N, 'off': r['off'], 'stages': stages, 'helpers': r['helpers'], 'petals': petals,
            'meas': meas, 'psi': r['psi'], 'mode': r['mode']}


def report(frames, intervals, A, fps, clearance):
    """measured on the result (round one's report, any gait): per stance its slip a frame (the least-moving of the points
    in contact in this frame and the last), drift, turn, gap and rocks; per swing its clearance and drags; the frames
    with both feet down and with neither (a run's flight is its own, under 'flight')"""
    F = [fr['f'] for fr in frames]
    rep = {'frames': [F[0], F[-1]], 'stances': {}, 'swings': {}}
    for s in SIDES:
        rows = []
        for a, b in intervals[s]:
            slips, cents, yaws, rocks = [], [], [], []
            pivot = []
            for i in range(a + 1, b + 1):
                m1, m0 = frames[i]['meas'][s], frames[i - 1]['meas'][s]
                c = (m1['gaps'] < CONTACT) & (m0['gaps'] < CONTACT)
                if not c.any():
                    k = int(np.argmin(m1['gaps'] + m0['gaps']))
                    rocks.append([F[i], round(1000 * float(m1['gaps'][m0['gaps'] < CONTACT].min(initial=1.0)), 2)])
                    c = np.zeros(len(m1['gaps']), dtype=bool)
                    c[k] = True
                mv = np.linalg.norm(m1['P'][c, :2] - m0['P'][c, :2], axis=1)
                slips.append(float(mv.min()))
                cents.append(float(np.linalg.norm((m1['P'][c, :2] - m0['P'][c, :2]).mean(0))))
                y = abs(wrap_pi(m1['yaw'] - m0['yaw'])) * R2D
                (pivot if frames[i]['mode'] == 'turn' else yaws).append(y)
            gaps = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)]
            modes = sorted(set(frames[i]['mode'] for i in range(a, b + 1)))
            rows.append({'frames': [F[a], F[b]], 'modes': modes,
                         'slip_mm_per_frame_max': round(1000 * max(slips, default=0.0), 2),
                         'centroid_mm_per_frame_max': round(1000 * max(cents, default=0.0), 2),
                         'drift_mm': round(1000 * sum(slips), 2),
                         'yaw_deg_per_frame_max': round(max(yaws, default=0.0), 3),
                         'pivot_deg_per_frame_max': round(max(pivot, default=0.0), 3),
                         'gap_mm': [round(min(gaps) * 1000, 2), round(max(gaps) * 1000, 2)], 'rocks': rocks})
        rep['stances'][s] = rows
        sw = []
        for a, b in _intervals([not fr['meas'][s]['stance'] and not fr['meas'][s]['free'] for fr in frames]):
            gaps = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)]
            mid = [frames[i]['meas'][s]['gap'] for i in range(a, b + 1)
                   if clearance > 0 and frames[i]['meas'][s]['lift_min'] >= 0.5 * clearance]
            touch = []
            for i in range(max(a, 1), b + 1):
                m1, m0 = frames[i]['meas'][s], frames[i - 1]['meas'][s]
                if m1['gap'] < CONTACT:
                    k = int(np.argmin(m1['gaps']))
                    v = float(np.linalg.norm(m1['P'][k] - m0['P'][k])) * fps
                    if v > 1.0 or (clearance > 0 and m1['lift_min'] >= 0.5 * clearance):
                        touch.append([F[i], round(v, 2)])
            sw.append({'frames': [F[a], F[b]], 'clearance_mm': round(min(gaps) * 1000, 2),
                       'mid_clearance_mm': round(min(mid) * 1000, 2) if mid else None, 'touch_frames': touch})
        rep['swings'][s] = sw
    down = [{s: fr['meas'][s]['gap'] < CONTACT for s in SIDES} for fr in frames]
    grounded_modes = [r_has_ground(A[i]) for i in range(len(frames))]
    rep['double_support'] = [F[i] for i, d in enumerate(down) if all(d.values())]
    none = [i for i, d in enumerate(down) if not any(d.values()) and grounded_modes[i]]
    # a flight is planned only where a gait with one leads (a run, a fall); anywhere else neither foot down is airborne
    # (a turn on the spot, an emote, a walk have no flight: a frame with both feet in the air there is a defect)
    planned_flight = [i for i in none if not any(A[i]['feet'][s]['stance'] for s in SIDES)
                      and A[i].get('lead') in FLIGHT_SLOTS]
    rep['flight'] = [F[i] for i in planned_flight]
    rep['airborne'] = [F[i] for i in none if i not in planned_flight]
    allrows = [row for s in SIDES for row in rep['stances'][s]]
    allsw = [row for s in SIDES for row in rep['swings'][s]]
    rep['worst'] = {'slip_mm_per_frame_max': max((r_['slip_mm_per_frame_max'] for r_ in allrows), default=0.0),
                    'centroid_mm_per_frame_max': max((r_['centroid_mm_per_frame_max'] for r_ in allrows), default=0.0),
                    'drift_mm': max((r_['drift_mm'] for r_ in allrows), default=0.0),
                    'yaw_deg_per_frame_max': max((r_['yaw_deg_per_frame_max'] for r_ in allrows), default=0.0),
                    'gap_min_mm': min((r_['gap_mm'][0] for r_ in allrows), default=0.0),
                    'gap_max_mm': max((r_['gap_mm'][1] for r_ in allrows), default=0.0),
                    'ankle_err_mm': round(1000 * max((fr['meas'][s]['ankle_err'] for fr in frames for s in SIDES
                                                      if fr['meas'][s]['stance']), default=0.0), 2),
                    'swing_ankle_err_mm': round(1000 * max((fr['meas'][s]['ankle_err'] for fr in frames for s in SIDES
                                                            if not fr['meas'][s]['stance'] and not fr['meas'][s]['free']),
                                                           default=0.0), 2),
                    'swing_clearance_min_mm': min((r_['clearance_mm'] for r_ in allsw), default=None),
                    'swing_mid_clearance_min_mm': min((r_['mid_clearance_mm'] for r_ in allsw
                                                       if r_['mid_clearance_mm'] is not None), default=None),
                    'swing_touch_frames': sum(len(r_['touch_frames']) for r_ in allsw),
                    'rocks': sum(len(r_['rocks']) for r_ in allrows),
                    'rock_mm_max': max((x[1] for r_ in allrows for x in r_['rocks']), default=0.0)}
    # the IK's miss of a PLANTED foot's target (the contact); a swing foot's target is the clip's arc lifted over the
    # ground, and a leg at full reach (or a knee at its stop) misses it in the air: reported apart, not a contact
    rep['ankle_err_mm'] = [[F[i], round(1000 * max((fr['meas'][s]['ankle_err'] for s in SIDES
                                                    if fr['meas'][s]['stance']), default=0.0), 2)]
                           for i, fr in enumerate(frames)]
    rep['swing_ankle_err_mm'] = [[F[i], round(1000 * max((fr['meas'][s]['ankle_err'] for s in SIDES
                                                          if not fr['meas'][s]['stance'] and not fr['meas'][s]['free']),
                                                         default=0.0), 2)] for i, fr in enumerate(frames)]
    return rep


def sub_report(rep, f0, f1):
    """the report cut to the frames [f0, f1] (a gait's segment): the stances and swings that touch it (one that crosses
    into the next gait is judged in both: the hand-overs are where defects hide), the frame lists cut"""
    out = {'frames': [f0, f1], 'stances': {}, 'swings': {}}
    for s in SIDES:
        out['stances'][s] = [r for r in rep['stances'][s] if r['frames'][1] >= f0 and r['frames'][0] <= f1]
        out['swings'][s] = [r for r in rep['swings'][s] if r['frames'][1] >= f0 and r['frames'][0] <= f1]
    for k in ('double_support', 'airborne', 'flight'):
        out[k] = [f for f in rep[k] if f0 <= f <= f1]
    allrows = [row for s in SIDES for row in out['stances'][s]]
    allsw = [row for s in SIDES for row in out['swings'][s]]
    w = rep['worst']
    out['worst'] = dict(w)
    out['worst'].update({
        'slip_mm_per_frame_max': max((r_['slip_mm_per_frame_max'] for r_ in allrows), default=0.0),
        'drift_mm': max((r_['drift_mm'] for r_ in allrows), default=0.0),
        'yaw_deg_per_frame_max': max((r_['yaw_deg_per_frame_max'] for r_ in allrows), default=0.0),
        'swing_touch_frames': sum(len(r_['touch_frames']) for r_ in allsw),
        'rocks': sum(len(r_['rocks']) for r_ in allrows),
        'ankle_err_mm': max((e for f, e in rep.get('ankle_err_mm', []) if f0 <= f <= f1), default=0.0)})
    return out
