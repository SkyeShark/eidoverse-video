"""eidoblend.characters.controller.plant: the film bake's feet, planted on whatever the controller walked over.

The WebGPU edition grounds the feet every frame with VRMFootControllerIK (foot_ik.py): it follows the animated foot's xy,
so whenever the clip's stride and the body's travel differ (a start, a stop, a turn, a stair the clip was not made for)
the foot slides. A film is built once, so here the controller's run is recorded first (film.py) and the feet are placed
over the whole run, as round one's walk_path places them for one clip (locomotion.py: its passes, generalised to any
blend of clips at any speed):

  THE STANCE    a foot is down where the clips playing (at their weights and their own clip times) have it down: each
                clip's measured stance (clips.analyze), blended; idle and the emotes stand on both feet; a fall, a seat,
                a maneuver leave the feet to the clip
  THE LOCK      through a stance the sole's points in contact in this frame and the last do not slip and the foot does
                not turn on the ground (in a turn on the spot it pivots about its contact: that is a turn). The heading
                it lands with is turned on by the free foot's own turn up to mid-stance (centred: on a curve the hips
                take the turn). On a stair or an edge the landing is moved along the foot (at most 12 cm) to where most
                of the sole is supported
  THE TARGET    tilted onto the ground's plane under the sole, set flat when within 1.5 deg of flat (not into the
                heel-off), inside the ankle's range for my robot body, toes flat on the ground through the toe roll
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
from .._math import D2R, R2D, clamp, ease, hann_smooth, q_from_three, q_to_three, smooth, wrap_pi
from ..ground import SIDES, foot_points
from ..locomotion import CONTACT, FLAT, FWD, LOCK_BAND, NEED, REACH_MARGIN, WIDTH, YAW_CAP, _bump, _intervals

LOCK_ROUNDS = 14                     # round one's 8 rounds converge for one clip at its own pace; a blend of clips at the
#                                      controller's pace corrects more each frame (a stair clip on a stair it was not
#                                      made for): more rounds, each frame's last ones settling the slip
from .pose import dof_pass

CLEARANCE = 0.03
STANCE_DROP_MAX = 0.45               # a stance whose ground lies this far under the body's support steps off an edge
STEP_FIT_MAX = 0.30                  # a landing's fit may move it onto a tread at most this far down (a stair's rise)
TWO_POINT_MAX = 3.0 * D2R            # the most the two-point support turns a planted sole in one round
FIT_RANGE = 0.12                     # the most a landing moves along the foot to find its support (m)
SWEEP_RATE = 1.2                     # the swing's clearance envelope rises toward an obstacle at most this fast (m/s)
LOAD_FRAMES = 4


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
    the bake runs again with those frames lifted ('released' in the report)"""
    late = {s: set(v) for s, v in (released or {}).items()}
    for s in SIDES:
        late.setdefault(s, set())
    frames, rep = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, late)
    for _round in range(3):
        # out of reach, or lifted off by its own toe meeting a riser as it rolls (the trailing foot at a stair's foot):
        # from the first such frame in the stance's second half to its end, the foot is let go (an early toe-off)
        more = {s: set() for s in SIDES}
        f00 = frames[0]['f']
        for s in SIDES:
            for row in rep['stances'][s]:
                a, b = row['frames']
                for f in range(a + (b - a + 1) // 2, b + 1):
                    m = frames[f - f00]['meas'][s]
                    if m['ankle_err'] > 0.003 or m['gap'] > 0.002:
                        more[s].update(range(f, b + 1))
                        break
        if not any(more.values()):
            break
        for s in SIDES:
            late[s] |= more[s]
        log(f'[plant] released at the end of their stances (out of reach): '
            f'{ {s: sorted(v) for s, v in more.items() if v} }')
        frames, rep = _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, late)
    rep['released'] = {s: sorted(v) for s, v in late.items()}
    return frames, rep


def _plant(body, world, recs, fps, clearance, pelvis, face, crown_state, head_state, feet, log, released):
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
            N, helpers = dof_pass(body, N, dt)
        M = r['M']
        Qr = M.to_quaternion()
        ph, Wh = pb.hips(M, r['off'], N)
        rec = {'f': r['f'], 'M': M, 'Qr': Qr, 'psi': r['heading'], 'N': N, 'off': r['off'], 'ph0': ph, 'helpers': helpers,
               'mode': r['mode'], 'maneuver': r.get('maneuver'), 'feet': {}, 'z0': M.translation.z,
               'grounded': r['grounded']}
        fks = {s: pb.leg_fk(s, ph, Wh, N) for s in SIDES}
        # my robot's feet are wider than a human's (robot_dof LEG_CLEARANCE.width): carried out from the clip's narrow
        # track where its ankles come closer than 18-23 cm, as round one's walk_path does
        w_eff = 0.0
        if body.robot:
            sep = abs((Qr.inverted() @ (fks['left']['p_an'] - fks['right']['p_an'])).x)
            w_eff = WIDTH * (1.0 - smooth(NEED[0], NEED[1], sep))
        for s in SIDES:
            fk = fks[s]
            if w_eff > 0:
                fk = dict(fk)
                fk['p_an'] = fk['p_an'] + Qr @ Vector((w_eff if s == 'left' else -w_eff, 0.0, 0.0))
            P = pb.sole(s, fk['p_an'], fk['W_ft'], fk['W_to'])
            st = r['stance'][s]
            planted = (st >= 0.5) and r['grounded'] and ground_mode(r) and r['f'] not in released.get(s, ())
            if planted and float(np.max(_ground(world, P))) < M.translation.z - STANCE_DROP_MAX:
                planted = False         # the clip plants it past an edge: nothing to stand on near the body's support
            # a fall (the controller airborne), a seat and a maneuver leave the feet to the clip (a landing, fallLand,
            # stands on the ground it landed on)
            free = not ground_mode(r) or not r['grounded']
            rec['feet'][s] = {'p_an': fk['p_an'], 'p_th': fk['p_th'], 'W_ft': fk['W_ft'], 'W_to': fk['W_to'],
                              'W_sh': fk['W_sh'], 'P': P, 'zlow': float(P[:, 2].min()), 'stance': planted, 'free': free,
                              'Ntoes': N[s + 'Toes'] if (s + 'Toes') in N else Quaternion(),
                              'dclip': (fk['p_an'] - fk['p_th']).length, 'p': 0.0, 'u': 0.0}
        A.append(rec)
    # stance runs of one frame (and swings of one frame) are blend noise: dropped
    for s in SIDES:
        fl = [r['feet'][s]['stance'] for r in A]
        for _ in range(2):
            for i in range(1, n - 1):
                if fl[i] != fl[i - 1] and fl[i] != fl[i + 1]:
                    fl[i] = fl[i - 1]
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
            th0[a] = wrap_pi(yaw_free[(a + b) // 2] - yaw_free[a]) if A[a]['mode'] != 'turn' else 0.0
            fit[a] = _support_fit(world, A[a]['feet'][s], th0[a]) if A[a]['mode'] == 'loco' else Vector((0.0, 0.0))
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

    # ---- 3: each foot's target turn and xy (round one's pass C)
    def tilt_w(s, i):
        best = 0.0
        for a, b in intervals[s]:
            if a <= i <= b:
                return 1.0
            dd = (a - i) if i < a else (i - b)
            best = max(best, 1.0 - dd / 5.0)
        return max(0.0, best)

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
                Wsh = Quaternion((0.0, 0.0, 1.0), fd['theta']) @ fd['W_sh']
                q3 = dof.project_joint(q_to_three(Wsh.inverted() @ fd['W_t']), dof.LEG_JOINTS[2], 1 if s == 'left' else -1)
                fd['W_t'] = Wsh @ q_from_three(q3)
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
        # turning the planted sole) does not lift the foot onto that edge
        for a, b in intervals[s]:
            top = float(np.max(A[a]['feet'][s]['G']))
            for i in range(a, b + 1):
                fd = A[i]['feet'][s]
                fd['surface_top'] = top + 0.01
                if float(np.max(fd['G'])) > top + 0.01:
                    fd['G'] = np.minimum(fd['G'], top + 0.01)
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
    def leg_dz(r, s, L):
        """the root's rise (from where the controller put it) at which leg s is L from its target"""
        fd = r['feet'][s]
        p_th = r['ph0'] + (r['Qr'] @ r['N']['hips']) @ body.leg[s]['hip']
        dxy = math.hypot(fd['T'].x - p_th.x, fd['T'].y - p_th.y)
        return fd['T'].z - p_th.z + (math.sqrt(L * L - dxy * dxy) if dxy < L else 0.0)
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
        ws = {s: max(v, 1e-6) for s, v in w.items()}
        dz_nom.append(sum(ws[s] * leg_dz(r, s, r['feet'][s]['dclip']) for s in ws) / sum(ws.values()))
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
            if fd['wt'] > 0.0 and not fd['free']:
                c = min(c, leg_dz(r, s, body.leg[s]['reach'] - REACH_MARGIN))
        cap.append(c)
    down, upr = 0.4 / fps, 0.5 / fps

    def shape(z_nom, hard):
        H = [min(hard[min(n - 1, max(0, i + k))] + (k * down if k > 0 else -k * upr) for k in range(-10, 11))
             for i in range(n)]
        return [min(a, b) for a, b in zip(hann_smooth([min(a, b) for a, b in zip(z_nom, H)], 1), H)]
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
        for fr in frames:
            d = 0.0
            for s in SIDES:
                m = fr['meas'][s]
                if m['stance'] and fr['N'][s + 'LowerLeg'].to_axis_angle()[1] < 3.0 * D2R:
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


def ground_mode(r):
    """a frame whose feet stand on the ground: locomotion, an emote, a turn on the spot, a landing (fallLand)"""
    return r['mode'] in ('loco', 'emote', 'turn') or (r['mode'] == 'maneuver' and r.get('maneuver') == 'land')


def r_has_ground(r):
    return r['grounded'] and ground_mode(r)


def _support_fit(world, fd, th0):
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
            if st_now[s] and 'surface_top' in fd:
                G = np.minimum(G, fd['surface_top'])          # the surface it landed on, not an edge its heel crept over
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
                    dy = wrap_pi(foot_yaw(fk['W_ft'], fk['W_to']) - pv['yaw'])
                    dy = clamp(dy, yaw_acc[s] - YAW_CAP, yaw_acc[s] + YAW_CAP)
                    if abs(dy) > 1e-9:
                        R = Quaternion((0.0, 0.0, 1.0), -dy)
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
                   'yaw': foot_yaw(fk['W_ft'], fk['W_to']), 'lift_min': r['feet'][s]['lift_min'], 'mode': r['mode']}
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
    planned_flight = [i for i in none if not any(A[i]['feet'][s]['stance'] for s in SIDES)]
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
