"""eidoblend.characters.controller.maneuvers: the controller's parkour moves (character_controller.js: _startVaultOver,
_startMountOnto, _startGapJump, _startWallScramble, vault, climbLedge, jump, climbLadder, climbWall,
_explicitManeuver and _applyManeuverHandIK), ported line for line onto the maneuver engine in controller.py.

    c.vault()                       # scan along the heading, vault the cover ahead (a landing beyond it)
    c.climb_ledge()                 # mount the block ahead (climbLedge, or climbWallUp over mount_max_rise)
    c.jump(distance=1.4, height=0.45)
    c.climb_ladder(height=2.5)      # the climbLadder loop up the face, chained into the mantle over the top
    c.climb_wall()                  # the wall scramble: climbWallUp looped, then the mantle

and the auto-trigger (controller._maybe_auto_maneuver) starts the same moves from the scan of the path ahead: vault
(cover up to 1.15 m, 1 m deep, a landing beyond), mount (climbLedge to 1.35 m, climbWallUp to 2.3 m), the wall scramble
(to 4.5 m), the gap jump (to 2.2 m). Each move is a keypoint ROOT PATH (the clip's own hips curve where the original
uses it: the vault and the mount fit the clip's root motion to the obstacle) played by _start_maneuver with a window of
its clip, and a GRAB the contact IK reads every frame: 'vaultGeo' (one hand props on the cover top, the feet pushed out
of it), 'climb' (the hands on the lip and the top, the mantling foot onto the top, limbs pushed out of the face),
'ladder' (hands and feet gripping the rungs through the clip's holds, or holds on a flat face).

This edition measures what the original fixed by constants, where those left the body off what it climbs (the
library clips on these bodies): the vault's window on the clip's own take-off and landing (vault_window) and its path
fitted so the tucked feet clear the cover; the mount's end-crouch sink on this body (clip_tuck); the ladder's standoff
from the hips' height (ladder_standoff) and each limb's hold from the clip (limb_grips), latched at full weight; the
prop hand latched at full weight, the spine leaning to it where the arm alone falls short (lean_to_reach); and, last
on every maneuver frame, no foot inside a solid (feet_out_of_solids).

Blender's axes: the travel (fx, fy) = (sin heading, -cos heading); a keypoint is {u, x, y, z} with z the feet's height;
the original's perp (-fz, fx) in three is (fy, -fx) here. The clip's root motion (clips.ControllerClip.root_motion) is the
hips curve in the armature's axes: up is z, the clip's forward is -y.
"""

import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

SIDES = ('left', 'right')
LIMBS = ('leftHand', 'rightHand', 'leftFoot', 'rightFoot')
VAULT_CLEAR = 0.06          # the vault's tucked feet clear the cover's top by this (m)
VAULT_SETTLE = 0.12         # the vault's crouch at the take-off is eased in over this (s)
RUNG_RADIUS = 0.028         # terrain_base's rungs (and the course package's)
GRIP_EASE = 0.08            # a ladder limb's grip eases in and out over this (s)
PALM_THICK = 0.014          # a hand's palm, from the middle knuckle's joint line to the skin a bar rests on (m)
HAND_CLEAR = 0.012          # a reaching hand keeps this off the wall behind a ladder and off its rungs (m)
SOLID_PASSES = 3            # the feet-out-of-solids solve's rounds
SOLID_REACH = 0.24          # the farthest the feet-out-of-solids search looks for a clear place for a foot (m)
SOLID_GRID = 0.01           # its step (m)


def _rm(c, slot):
    """the clip's root motion as the original's {x, y (up), z (forward), N, dur} arrays"""
    r = (getattr(c, '_clip_root_motion', None) or {}).get(slot)
    if r is None:
        return None
    xyz = r['xyz']
    return {'N': r['N'], 'dur': r['dur'], 'up': [float(v) for v in xyz[:, 2]], 'fwd': [float(-v) for v in xyz[:, 1]]}


def _feet(c):
    return c._center.z - c.half_height - c.hip_y


def _dir(c):
    return math.sin(c._heading), -math.cos(c._heading)


def _clip_of(c, slot):
    a = (c._actions or {}).get(slot)
    return a.clip if a is not None else None


def _face(ob):
    """the obstacle's near face from the body (m): measured by the scan's level rays (controller._face_distance) where it
    has them, else the original's first sample over the edge (up to a scan step past the face)"""
    return ob.get('face_d', ob['start_d'])


def _smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


# ================================================================================================ the clips measured
def clip_tuck(cl, t):
    """how far the clip's lowest sole point rides over the root at clip time t on this body with its hips' position
    track stripped (a crouch draws the feet up toward the hips): its analysis' feet less the hips' offset (m)"""
    g = getattr(cl, 'gait', None)
    if g is None:
        return None
    n = len(g.zlow['left'])
    k = min(n - 1, max(0, int(round(t / cl.dt))))
    return float(min(g.zlow['left'][k], g.zlow['right'][k]) - cl.root_curve[k, 2])


def vault_window(cl):
    """the vault clip's action on this body, measured on its own feet (its analysis plays it with its root motion):
    from the take-off (the last sample before the hips' peak with a foot within 3 cm of the clip's floor) to the landing
    (the first after it) -> (c0, c1) fractions of the clip, or None. (The original's fixed window 0.20 .. 0.62 starts
    at the library clip's peak, so the rise it scales is nothing and the root crosses flat.)"""
    g = getattr(cl, 'gait', None)
    if g is None:
        return None
    zl = np.minimum(g.zlow['left'], g.zlow['right'])
    n = len(zl)
    up = cl.root_curve[:n, 2]
    k_peak = int(np.argmax(up))
    on = zl < float(np.percentile(zl, 5)) + 0.03
    before, after = np.flatnonzero(on[:k_peak]), np.flatnonzero(on[k_peak:])
    if not len(before) or not len(after):
        return None
    return int(before[-1]) / (n - 1), (k_peak + int(after[0])) / (n - 1)


def limb_grips(c, cl):
    """a climbing clip's holds on this body: per limb (hands and feet), where it holds: any time but its one reach a
    cycle, the stretch round its fastest climb (in the clip's own root-motion space) where it rises faster than 40 %
    of that (a wobble elsewhere is a hold) -> {limb: bool array over the clip's 60 Hz samples}, cached on the clip"""
    cache = getattr(cl, '_limb_grips', None)
    if cache is not None:
        return cache
    from .pose import Pose
    n = max(8, int(round(cl.duration * 60)))
    ts = np.linspace(0.0, cl.duration, n, endpoint=False)
    Z = {lb: np.zeros(n) for lb in LIMBS}
    for k, t in enumerate(ts):
        N, _h = cl.sample(t, loop=True)
        full = {nm: N.get(nm, Quaternion()) for nm in c.h.humanoid}
        off = Vector([float(np.interp(t, np.arange(cl.n + 1) * cl.dt, cl.root_curve[:, j])) for j in range(3)])
        p = Pose(c.body, Matrix.Identity(4), full, off)
        for lb in LIMBS:
            if lb in c.h.humanoid:
                Z[lb][k] = p.world_pos(lb).z
    out = {}
    dt = cl.duration / n
    rise = cl.root_curve[-1, 2] - cl.root_curve[0, 2]       # one cycle's climb: the loop's seam
    for lb in LIMBS:
        z = Z[lb]
        zz = np.concatenate([z[-2:] - rise, z, z[:2] + rise])
        v = (zz[4:] - zz[:-4]) / (4 * dt)
        fast = v > 0.40 * max(float(v.max()), 0.3)
        k = int(np.argmax(v))
        reach = np.zeros(n, dtype=bool)
        for step in (1, -1):                                  # the contiguous run round the peak (the loop wraps)
            j = k
            for _ in range(n):
                if not fast[j % n]:
                    break
                reach[j % n] = True
                j += step
        out[lb] = ~reach
    cl._limb_grips = out
    return out


LADDER_LEAN_KEEP = 3.0      # the torso's lean toward a vertical ladder that the clip keeps (deg): the shoulders some
#                             25 cm off the rungs, the face 12-15 cm (8 deg hung the face 5-10 cm from them)


def clip_lean(c, cl):
    """a climbing clip's torso lean on this body: the mean over its cycle of the hips -> shoulders' angle from vertical
    toward the climb (deg; + leans in), cached on the clip. (climbLadder leans 25 deg on Aletheia, 34 on my robot body:
    it climbs a ladder leaning away from the climber)"""
    v = getattr(cl, '_lean_deg', None)
    if v is not None:
        return v
    from .pose import Pose
    out = []
    for k in range(24):
        N, _h = cl.sample(k / 24 * cl.duration, loop=True)
        full = {nm: N.get(nm, Quaternion()) for nm in c.h.humanoid}
        p = Pose(c.body, Matrix.Identity(4), full, Vector())
        if 'leftUpperArm' not in c.h.humanoid or 'rightUpperArm' not in c.h.humanoid:
            return 0.0
        d = 0.5 * (p.world_pos('leftUpperArm') + p.world_pos('rightUpperArm')) - p.world_pos('hips')
        out.append(math.degrees(math.atan2(-d.y, d.z)))          # the armature's forward is -Y
    cl._lean_deg = float(np.mean(out))
    return cl._lean_deg


def _stand_upright(c, m, g, u):
    """a vertical ladder's climb stands the torso up: the spine turned back about the body's width by the clip's mean
    lean less LADDER_LEAN_KEEP (its own sway kept), eased in over the approach and out over the climb's last 8 %, into
    the mantle. (With the clip's lean the shoulders hung 13 cm from the rungs, every grip within reach of the arm solve's
    18 cm guard; a climber on a vertical ladder keeps the torso parallel to it, the shoulders some 30 cm off the rungs)"""
    corr = g.get('upright', 0.0)
    if corr <= 0.0 or 'spine' not in c.h.humanoid:
        return
    u1 = max(1e-3, g.get('u_climb', 0.1))
    k = _smoothstep(u / u1) * (1.0 - _smoothstep((u - 0.92) / 0.08))
    if k <= 1e-4:
        return
    left = Vector((-g['fy'], g['fx'], 0.0))
    c.pose.apply_world_delta('spine', Quaternion(left, -corr * k))


def _grip_at(grips, lb, cl, t):
    g = grips[lb]
    n = len(g)
    return bool(g[int((t % cl.duration) / cl.duration * n) % n])


# ================================================================================================ the moves
def _vault_path(c, cl, win, cur, feet, land_z, land_d, ob, fx, fy, duration):
    """the vault's root path from the clip's own action (vault_window): across, the clip's forward travel scaled to the
    landing; up, the clip's hips curve over the line from the take-off to the landing ground, its rise above the line
    from the crouch at either end scaled so the tucked feet clear the cover's top by VAULT_CLEAR wherever the body is
    over it, the crouch itself kept (the clip's bent legs reach the ground at the take-off, eased in, and at the
    landing) -> (path, the rise's scale)"""
    c0, c1 = win
    k0, k1 = int(round(c0 * cl.n)), int(round(c1 * cl.n))
    R = cl.root_curve
    fwd, up = -R[:, 1], R[:, 2]
    trav = abs(fwd[k1] - fwd[k0]) or 1.0
    g = cl.gait
    need = []
    rows = []
    for k in range(k0, k1 + 1):
        u = (k - k0) / max(1, k1 - k0)
        d = abs(fwd[k] - fwd[k0]) / trav * land_d
        line = feet + (land_z - feet) * u
        b = up[k0] + (up[k1] - up[k0]) * u
        rows.append((u, d, line, b, up[k]))
        if up[k] - b <= 0.05:
            continue
        for s in SIDES:
            # this foot over the cover (its ankle's travel, its length either side): its tucked sole clears the top
            foot_d = d + float(-(g.ankle[s][k][1] - R[k, 1]))
            if _face(ob) - 0.12 <= foot_d <= ob['end_d'] + 0.12:
                zl = float(g.zlow[s][k] - up[k])                     # the tucked sole over the stripped root
                need.append((ob['top_y'] + VAULT_CLEAR - line - b - zl) / (up[k] - b))
    if need:
        ys = min(2.4, max(0.3, max(need)))
    else:
        peak = max(0.001, float(up[k0:k1 + 1].max() - up[k0]))
        ys = max(0.5, (ob['rise'] - 0.22) / peak)
    path = []
    for j, (u, d, line, b, upk) in enumerate(rows):
        if j % 3 and j != len(rows) - 1:
            continue
        settle = _smoothstep(u * duration / VAULT_SETTLE)
        z = line + (upk - b) * ys + b * settle
        path.append({'u': u, 'x': cur.x + fx * d, 'y': cur.y + fy * d, 'z': z, 'ease': 'linear'})
    path[-1]['u'] = 1.0
    return path, ys


def start_vault_over(c, scan, ob, fx, fy):
    """_startVaultOver: the vault clip's action window over a root path fitted from its own hips curve. This edition
    measures the window on the clip (vault_window: its take-off to its landing) and fits the path to the cover
    (_vault_path); without the clip's analysis it plays the original's (window 0.20 .. 0.62, the rise above its start)"""
    cur = c._center.copy()
    feet = _feet(c)
    land_d = min(ob['landing_d'] + 0.25, c.maneuver_scan_range)
    land_z = ob['landing_y'] if ob['landing_y'] is not None else feet
    duration = max(0.85, min(1.2, land_d / 2.0))
    VC0, VC1 = 0.20, 0.62
    rm = _rm(c, 'vault')
    cl = _clip_of(c, 'vault')
    win = vault_window(cl) if cl is not None else None
    if win is not None:
        VC0, VC1 = win
        path, ys = _vault_path(c, cl, win, cur, feet, land_z, land_d, ob, fx, fy, duration)
        c.log(f'[eidoverse-controller] vault: the clip\'s action {VC0:.3f}..{VC1:.3f}, its rise x{ys:.2f}, peak '
              f'{max(p["z"] for p in path) - feet:.2f} m over the take-off')
    elif rm:
        N = rm['N']
        i0, i1 = round(VC0 * N), round(VC1 * N)
        z_travel = abs(rm['fwd'][i1] - rm['fwd'][i0]) or 1.0
        peak = 0.001
        for i in range(i0, i1 + 1):
            peak = max(peak, rm['up'][i] - rm['up'][i0])
        ys = max(0.5, (ob['rise'] - 0.22) / peak)          # the clip's rise scaled so its peak passes the top
        path = []
        for i in range(i0, i1 + 1):
            u = (i - i0) / max(1, i1 - i0)
            d = abs(rm['fwd'][i] - rm['fwd'][i0]) / z_travel * land_d
            z = feet + max(0.0, rm['up'][i] - rm['up'][i0]) * ys + (land_z - feet) * u
            path.append({'u': u, 'x': cur.x + fx * d, 'y': cur.y + fy * d, 'z': z, 'ease': 'linear'})
        path[-1]['u'] = 1.0
        path[-1]['z'] = land_z
    else:
        apex = max(feet, land_z) + max(0.12, ob['rise'] - 0.30)
        ua = max(0.35, min(0.65, (ob['start_d'] + (ob['end_d'] - ob['start_d']) * 0.5) / land_d))
        path = [{'u': 0.0, 'x': cur.x, 'y': cur.y, 'z': feet},
                {'u': ua, 'x': cur.x + fx * land_d * ua, 'y': cur.y + fy * land_d * ua, 'z': apex},
                {'u': 1.0, 'x': cur.x + fx * land_d, 'y': cur.y + fy * land_d, 'z': land_z}]
    plant_d = _face(ob) + min(0.22, (ob['end_d'] - _face(ob)) * 0.5)
    grab = {'type': 'vaultGeo', 'window': (0.06, 0.85), 'fx': fx, 'fy': fy, 'perp': (fy, -fx), 'top': ob['top_y'],
            'd0': _face(ob) - 0.12, 'd1': ob['end_d'] + 0.12, 'ox': cur.x, 'oy': cur.y,
            'px': cur.x + fx * plant_d, 'py': cur.y + fy * plant_d}
    return c._start_maneuver({'type': 'vault', 'slot': 'vault', 'slot_fallbacks': ['jump'], 'path': path,
                              'duration': duration, 'landing_ground_y': land_z, 'grab': grab, 'clip_window': (VC0, VC1)})


def start_mount_onto(c, scan, ob, fx, fy, slot='climbLedge'):
    """_startMountOnto: the climbLedge clip's root motion fitted to the wall (a shorter wall joins the clip late: its
    tail is the mantle over the lip), the end crouch sunk visually and faded after"""
    cur = c._center.copy()
    feet = _feet(c)
    top = ob['top_y']
    rise = top - feet
    rm = _rm(c, 'climbLedge')
    if not rm:
        c.log('[eidoverse-controller] mount: climbLedge root motion unavailable')
        return False
    N = rm['N']
    up, fwd = rm['up'], rm['fwd']
    z_sgn = math.copysign(1.0, fwd[N] - fwd[0]) if fwd[N] != fwd[0] else 1.0
    y_max = max(up)
    i_end = N
    for i in range(N + 1):
        if up[i] >= y_max - 0.03:
            i_end = i
            break
    i_end = min(N, i_end + 2)
    i_start = 0
    for i in range(i_end - 1, -1, -1):
        if up[i_end] - up[i] >= rise:
            i_start = i
            break
    clip_rise = up[i_end] - up[i_start]
    ys = rise / clip_rise if clip_rise > 0.2 else 1.0
    z_travel = (fwd[i_end] - fwd[i_start]) * z_sgn
    d_end = _face(ob) + 0.32
    zs = d_end / z_travel if z_travel > 0.15 else 0.0
    face_max_d = max(0.04, _face(ob) - (c.radius + 0.22))
    path = []
    for i in range(i_start, i_end + 1):
        u = (i - i_start) / max(1, i_end - i_start)
        d = (fwd[i] - fwd[i_start]) * z_sgn * zs if zs > 0 else d_end * u
        d = max(d, face_max_d * min(1.0, u / 0.12))
        z = feet + (up[i] - up[i_start]) * ys
        if z < top - 0.30:
            d = min(d, face_max_d)
        path.append({'u': u, 'x': cur.x + fx * d, 'y': cur.y + fy * d, 'z': z, 'ease': 'linear'})
    path[-1]['u'] = 1.0
    duration = max(1.0, min(3.8, (i_end - i_start) / N * rm['dur']))
    grab = {'type': 'climb', 'window': (0.0, 1.0), 'fx': fx, 'fy': fy, 'perp': (fy, -fx), 'top': top,
            'lip_x': cur.x + fx * _face(ob), 'lip_y': cur.y + fy * _face(ob)}
    # the end crouch's sink: the original's 0.65 m was probed on its rig; here it is how far the clip's end crouch
    # draws THIS body's feet over its root (clip_tuck), so the crouched feet rest on the top
    cl = _clip_of(c, 'climbLedge')
    tuck = clip_tuck(cl, i_end / N * cl.duration) if cl is not None else None
    sink = max(0.0, tuck) if tuck is not None else 0.65
    return c._start_maneuver({'type': 'mount', 'slot': 'climbLedge', 'slot_fallbacks': [slot, 'jump'], 'path': path,
                              'duration': duration, 'landing_ground_y': top, 'grab': grab,
                              'clip_window': (i_start / N, i_end / N),
                              'visual_sink': {'amount': sink, 'u0': 0.55, 'u1': 0.98}})


def start_gap_jump(c, scan, gap, fx, fy):
    """_startGapJump: a ballistic three-keypoint path over the gap, the jump clip's take-off to landing"""
    cur = c._center.copy()
    feet = _feet(c)
    land_d = min(gap['landing_d'] + 0.22, c.maneuver_scan_range)
    land_z = gap['landing_y'] if gap['landing_y'] is not None else feet
    apex = max(feet, land_z) + 0.32 + gap['width'] * 0.10
    ua = max(0.40, min(0.60, (gap['start_d'] + gap['width'] * 0.5) / land_d))
    duration = max(0.70, min(1.25, land_d / 2.6))
    path = [{'u': 0.0, 'x': cur.x, 'y': cur.y, 'z': feet},
            {'u': ua, 'x': cur.x + fx * land_d * ua, 'y': cur.y + fy * land_d * ua, 'z': apex},
            {'u': 1.0, 'x': cur.x + fx * land_d, 'y': cur.y + fy * land_d, 'z': land_z}]
    return c._start_maneuver({'type': 'jump', 'slot': 'jump', 'path': path, 'duration': duration,
                              'landing_ground_y': land_z, 'clip_window': (0.15, 0.80)})


def start_wall_scramble(c, scan, ob, fx, fy, rate=0.34, time_scale=1.1):
    """_startWallScramble: climbWallUp looped while the root rises at `rate`, palms and toes on the face, chained into
    the mantle at the top (shorter than 1.35 + 5 cm of climbing: just the mount)"""
    cur = c._center.copy()
    feet = _feet(c)
    height, face_start = ob['rise'], _face(ob)
    face_d = max(0.06, face_start - (c.radius + 0.20))
    top = ob['top_y']
    climb_h = max(0.0, height - min(height, 1.35))
    if climb_h < 0.05:
        return start_mount_onto(c, scan, ob, fx, fy, 'climbLedge')
    t_app, t_climb = 0.35, climb_h / rate
    total = t_app + t_climb
    u1 = t_app / total
    path = [{'u': 0.0, 'x': cur.x, 'y': cur.y, 'z': feet},
            {'u': u1, 'x': cur.x + fx * face_d, 'y': cur.y + fy * face_d, 'z': feet},
            {'u': 1.0, 'x': cur.x + fx * face_d, 'y': cur.y + fy * face_d, 'z': feet + climb_h, 'ease': 'linear'}]
    grab = {'type': 'ladder', 'window': (u1 * 0.7, 0.98), 'fx': fx, 'fy': fy, 'perp': (fy, -fx),
            'x': cur.x + fx * face_start, 'y': cur.y + fy * face_start}

    def chain():
        f_now = _feet(c)
        return start_mount_onto(c, None, {'top_y': top, 'rise': top - f_now, 'start_d': face_start - face_d,
                                          'end_d': face_start - face_d + 0.5}, fx, fy, 'climbLedge')
    return c._start_maneuver({'type': 'wallScramble', 'slot': 'climbWallUp', 'slot_fallbacks': ['climbLadder', 'climbLedge'],
                              'path': path, 'duration': total, 'landing_ground_y': top, 'loop': True,
                              'time_scale': time_scale, 'grab': grab, 'chain': chain})


# ================================================================================================ explicit
def explicit_maneuver(c, kind):
    """_explicitManeuver: scan along the heading and do `kind` ('vault' | 'mount') on the obstacle ahead"""
    if c._maneuver:
        return False
    fx, fy = _dir(c)
    scan = c._scan_path_ahead(fx, fy)
    ob = c._classify_path_ahead(scan)['obstacle']
    if not ob:
        c.log(f'[eidoverse-controller] {kind}: no obstacle ahead along the heading')
        return False
    if kind == 'vault':
        if ob['landing_d'] is None:
            c.log('[eidoverse-controller] vault: no landing beyond the obstacle: use climb_ledge()')
            return False
        return start_vault_over(c, scan, ob, fx, fy)
    slot = 'climbWallUp' if ob['rise'] > c.mount_max_rise else 'climbLedge'
    return start_mount_onto(c, scan, ob, fx, fy, slot)


def jump(c, distance=1.4, height=0.45):
    """jump({distance, height}): a blind leap forward along the heading, the landing probed"""
    if c._maneuver:
        return False
    fx, fy = _dir(c)
    cur = c._center.copy()
    feet = _feet(c)
    land = c._ground_vector(cur.x + fx * distance, cur.y + fy * distance, cur.z + c.half_height + 3.0)
    land_z = land if (land is not None and abs(land - feet) < 1.5) else feet
    path = [{'u': 0.0, 'x': cur.x, 'y': cur.y, 'z': feet},
            {'u': 0.5, 'x': cur.x + fx * distance * 0.5, 'y': cur.y + fy * distance * 0.5,
             'z': max(feet, land_z) + height},
            {'u': 1.0, 'x': cur.x + fx * distance, 'y': cur.y + fy * distance, 'z': land_z}]
    return c._start_maneuver({'type': 'jump', 'slot': 'jump', 'path': path,
                              'duration': max(0.65, min(1.30, distance / 2.4)), 'landing_ground_y': land_z,
                              'clip_window': (0.15, 0.80)})


def ladder_standoff(c):
    """how far the hips hang behind the rungs' line on a vertical ladder: a third of the hips' standing height
    (0.30 m on a 0.9 m hip), so the hands grip with bent elbows and the balls of the feet reach the rungs. (The
    original's body centre 0.34 m + the cylinder's radius off the face hangs the library clip's feet 0.3-0.6 m behind
    the rungs: its clip climbs a leaning ladder, hands half a metre ahead of the hips and feet under them.)"""
    return min(0.42, max(0.24, 0.33 * c.body.H['hips'].z))


def climb_ladder(c, height=None, rate=0.55, first_rung=0.25, rung_spacing=0.28, time_scale=1.0, standoff=None,
                 rung_radius=None):
    """climbLadder: the climbLadder clip looped at its own pace while the root rises at `rate` until the chest reaches
    the lip, then chained into the mount's mantle; hands and feet grip the rungs (first_rung up, every rung_spacing,
    their line 0.09 m out from the face) through their holds. standoff: the hips behind the rungs' line (m; default
    ladder_standoff); rung_radius: the rungs' (m; default terrain_base's RUNG_RADIUS): the palms close over them and the
    balls of the feet stand on them"""
    if c._maneuver:
        return False
    fx, fy = _dir(c)
    scan = c._scan_path_ahead(fx, fy)
    ob = c._classify_path_ahead(scan)['obstacle']
    cur = c._center.copy()
    feet = _feet(c)
    height = height if height is not None else (ob['rise'] if ob else None)
    if height is None or not math.isfinite(height) or height <= 0.2:
        c.log('[eidoverse-controller] climbLadder: no height (pass height= or face a wall)')
        return False
    face_start = _face(ob) if ob else 0.35
    standoff = ladder_standoff(c) if standoff is None else standoff
    face_d = max(0.06, face_start - 0.09 - standoff)
    top = feet + height
    climb_h = max(0.0, height - min(height, 1.35))
    if climb_h < 0.05:
        return start_mount_onto(c, None, {'top_y': top, 'rise': height, 'start_d': face_start,
                                          'end_d': face_start + 0.5}, fx, fy, 'climbLedge')
    t_app, t_climb = 0.35, climb_h / rate
    total = t_app + t_climb
    u1 = t_app / total
    path = [{'u': 0.0, 'x': cur.x, 'y': cur.y, 'z': feet},
            {'u': u1, 'x': cur.x + fx * face_d, 'y': cur.y + fy * face_d, 'z': feet},
            {'u': 1.0, 'x': cur.x + fx * face_d, 'y': cur.y + fy * face_d, 'z': feet + climb_h, 'ease': 'linear'}]
    # the top rung: terrain_base builds rungs from first_rung while under height - 0.05 (the original's
    # (height - 0.10) / spacing counts one past it, a hold in the air)
    grab = {'type': 'ladder', 'window': (u1 * 0.7, 0.98), 'fx': fx, 'fy': fy, 'perp': (fy, -fx),
            'x': cur.x + fx * (face_start - 0.09), 'y': cur.y + fy * (face_start - 0.09),
            'base_rung': feet + first_rung, 'rung_spacing': rung_spacing,
            'max_rung': int(math.floor((height - 0.05 - first_rung) / rung_spacing - 1e-9)),
            'face_x': cur.x + fx * face_start, 'face_y': cur.y + fy * face_start,
            'rung_radius': RUNG_RADIUS if rung_radius is None else rung_radius, 'u_climb': u1}
    cl = _clip_of(c, 'climbLadder')
    if cl is not None:
        grab['upright'] = math.radians(max(0.0, clip_lean(c, cl) - LADDER_LEAN_KEEP))

    def chain():
        f_now = _feet(c)
        return start_mount_onto(c, None, {'top_y': top, 'rise': top - f_now, 'start_d': face_start - face_d,
                                          'end_d': face_start - face_d + 0.5}, fx, fy, 'climbLedge')
    return c._start_maneuver({'type': 'ladder', 'slot': 'climbLadder', 'slot_fallbacks': ['climbWallUp', 'climbLedge'],
                              'path': path, 'duration': total, 'landing_ground_y': top, 'loop': True,
                              'time_scale': time_scale, 'grab': grab, 'chain': chain})


def climb_wall(c, rate=0.34, time_scale=1.1):
    """climbWall: the wall scramble up the wall ahead"""
    if c._maneuver:
        return False
    fx, fy = _dir(c)
    scan = c._scan_path_ahead(fx, fy)
    ob = c._classify_path_ahead(scan)['obstacle']
    if not ob:
        c.log('[eidoverse-controller] climbWall: no wall ahead')
        return False
    return start_wall_scramble(c, scan, ob, fx, fy, rate=rate, time_scale=time_scale)


# ================================================================================================ the contact IK
def _sm(a, b, v):
    return min(1.0, max(0.0, (v - a) / (b - a)))


def apply_hand_ik(c, m, u):
    """_applyManeuverHandIK: the clip drives the limbs; the solve pulls contact points onto the geometry at partial
    weight (the lip and the top for a climb, the prop hand and the feet's clearance for a vault, the rungs or the face's
    holds for a ladder or a scramble)"""
    g = m.get('grab')
    if not g:
        return
    H = c.h.humanoid
    p = c.pose

    def bone(name):
        return p.world_pos(name).copy() if name in H else None
    w0, w1 = g['window']
    if g['type'] == 'ladder':
        _stand_upright(c, m, g, u)
    if u < w0 or u > w1:
        if g['type'] == 'ladder':
            # before the grips (the approach) and after them: the clip's reaching hands kept off the wall and the rungs
            f3 = Vector((g['fx'], g['fy'], 0.0))
            for side in SIDES:
                if side + 'Hand' in H:
                    _hand_off_ladder(c, m, g, side, f3, g.get('rung_radius', RUNG_RADIUS), g.get('rung_spacing'), 1.0)
        return

    def ramp(a, b, max_w):
        if u < a or u > b:
            return 0.0
        q = (u - a) / max(1e-6, b - a)
        return min(max_w, math.sin(math.pi * q) * max_w * 1.6)
    px, py = g['perp']

    def lat_of(pt, cx, cy, clamp):
        raw = (pt.x - cx) * px + (pt.y - cy) * py
        return max(-clamp, min(clamp, raw))
    fx, fy = g['fx'], g['fy']
    if g['type'] == 'climb':
        feet_now = m.get('_cur_feet_y', _feet(c))
        to_top = g['top'] - feet_now
        for side in SIDES:
            hp = bone(side + 'Hand')
            if hp is None:
                continue
            along = (hp.x - g['lip_x']) * fx + (hp.y - g['lip_y']) * fy
            key = side + 'HandTop'
            if g['top'] - 0.50 < hp.z < g['top'] + 0.01 and along > -0.10:
                # the top plane is a floor for the hands from the grab through the crouch: the pull-up over planted hands.
                # This edition latches the palm where it first lands (the original re-reads the animated hand's along
                # and lateral every frame, so a planted hand slides over the top)
                depth = g['top'] + 0.01 - hp.z
                if m.get(key) is None:
                    m[key] = (lat_of(hp, g['lip_x'], g['lip_y'], 0.35), max(0.10, min(0.45, along)))
                lat, at = m[key]
                tgt = Vector((g['lip_x'] + px * lat + fx * at, g['lip_y'] + py * lat + fy * at, g['top'] + 0.02))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt, 0.7), min(0.98, 0.25 + depth * 4.5))
                continue
            if hp.z > g['top'] + 0.06:
                m[key] = None                                                   # lifted off the top: a new plant next
            if hp.z < g['top'] - 0.06 and along > -0.02:
                lat = lat_of(hp, g['lip_x'], g['lip_y'], 0.40)                  # deep in the face: pushed out
                tgt = Vector((g['lip_x'] + px * lat - fx * 0.04, g['lip_y'] + py * lat - fy * 0.04, hp.z))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt, 0.7), 0.90)
            elif hp.z >= g['top'] - 0.28 and 0.45 < to_top < 1.25:
                # the grab: the lip line, at full weight as the hand nears it (the original's 60 % from a body hanging
                # within 1.10 m of the top leaves a 1.15 m wall's hands short of its lip)
                near = _sm(g['top'] - 0.28, g['top'] - 0.10, hp.z)
                lat = lat_of(hp, g['lip_x'], g['lip_y'], 0.32)
                tgt = Vector((g['lip_x'] + px * lat, g['lip_y'] + py * lat, g['top'] + 0.02))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt), near)
        for side in SIDES:
            fp = bone(side + 'Foot')
            if fp is None:
                continue
            along_f = (fp.x - g['lip_x']) * fx + (fp.y - g['lip_y']) * fy
            if to_top <= 0.55 and g['top'] - 0.45 < fp.z < g['top'] + 0.02 and along_f > -0.35:
                depth = g['top'] + 0.02 - fp.z                                   # the mantle: the foot onto the top
                lat = lat_of(fp, g['lip_x'], g['lip_y'], 0.30)
                at = max(0.15, along_f)
                tgt = Vector((g['lip_x'] + px * lat + fx * at, g['lip_y'] + py * lat + fy * at, g['top'] + 0.02))
                c._solve_leg_ik(side, c._smooth_limb_target(m, side + 'FootClimb', tgt, 0.7), min(0.97, depth * 7.0))
            elif fp.z < g['top'] - 0.05 and along_f > 0.0:
                lat = lat_of(fp, g['lip_x'], g['lip_y'], 0.30)                  # inside the face: pushed out
                tgt = Vector((g['lip_x'] + px * lat - fx * 0.06, g['lip_y'] + py * lat - fy * 0.06, fp.z))
                c._solve_leg_ik(side, c._smooth_limb_target(m, side + 'FootClimb', tgt, 0.7),
                                min(0.95, 0.60 + min(0.35, along_f) * 1.5))
    elif g['type'] == 'vaultGeo':
        if 0.12 < u < 0.68:
            if not m.get('_prop_side'):
                best, bd = None, math.inf
                for side in SIDES:
                    hp = bone(side + 'Hand')
                    if hp is None:
                        continue
                    d = math.hypot(hp.x - g['px'], hp.y - g['py'])
                    if d < bd:
                        best, bd = side, d
                m['_prop_side'] = best
            side = m['_prop_side']
            hp = bone(side + 'Hand') if side else None
            if hp is not None:
                sh = bone(side + 'UpperArm') or hp
                # the film's prop: the contact point latched where the hand first reaches for it (the original takes
                # the animated hand's lateral every frame, so a planted hand slides along the top), at full weight
                # within reach (the original's 85 % leaves the palm off the cover)
                if m.get('_prop_lat') is None:
                    m['_prop_lat'] = lat_of(hp, g['px'], g['py'], 0.32)
                lat = m['_prop_lat']
                tgt = Vector((g['px'] + px * lat, g['py'] + py * lat, g['top'] + 0.02))
                w = _sm(1.25, 1.0, (sh - tgt).length)
                if w > 0.02:
                    st = c._smooth_limb_target(m, side + 'HandVault', tgt, 0.6)
                    c._solve_arm_ik(side, st, w)
                    lean_to_reach(c, side, st, w)
        for side in SIDES:
            fp = bone(side + 'Foot')
            if fp is None:
                continue
            along = (fp.x - g['ox']) * fx + (fp.y - g['oy']) * fy
            if g['d0'] - 0.05 < along < g['d1'] + 0.05 and fp.z < g['top'] + 0.04:
                c._solve_leg_ik(side, c._smooth_limb_target(m, side + 'FootVault', Vector((fp.x, fp.y, g['top'] + 0.07))),
                                0.85)
    elif g['type'] == 'ladder':
        # the film edition's climb-face contact: each limb GRIPS through its clip's hold (limb_grips: any time but its
        # reach) and is latched there at full weight, eased in and out over GRIP_EASE; through its reach the clip owns
        # it. A hold is the rung nearest where the limb arrives (a real ladder: rung_spacing) or, on a flat face (the
        # scramble), the height it arrives at; its lateral is latched with it. The hand's wrist rests on the rung's
        # line (2 cm toward the climber, as the original), the ball of the foot on the rung's top (a scramble's toe on
        # the face). The original pulls at 60-95 % only while a limb nears the rungs' plane, which the library clip's
        # feet never do (they climb a leaning ladder): its feet hung behind the rungs
        # full through the climb, eased in over its first 12 % and out over its last 4 % (the original's sine ramp lets
        # go of the rungs through the climb's last fifth, before the mantle's hands take the lip)
        w_gate = max(0.0, min(1.0, (u - w0) / 0.12, (w1 - u) / 0.04))
        spacing = g.get('rung_spacing')
        max_r = g.get('max_rung', 99)
        cl = m['action'].clip
        grips = limb_grips(c, cl)
        t_clip = m['action'].time
        step = m.get('_dt', 1.0 / 30.0) / GRIP_EASE
        gws = m.setdefault('_gw', {})
        f3 = Vector((fx, fy, 0.0))
        rr = g.get('rung_radius', RUNG_RADIUS)
        for lb in LIMBS:
            if lb not in H:
                continue
            side = 'left' if lb.startswith('left') else 'right'
            hand = lb.endswith('Hand')
            pt = bone(lb)
            gripping = _grip_at(grips, lb, cl, t_clip) and w_gate > 0.01
            gw = min(1.0, gws.get(lb, 0.0) + step) if gripping else max(0.0, gws.get(lb, 0.0) - step)
            gws[lb] = gw
            key = lb + 'Hold'
            hold = m.get(key)
            if hand and gw * w_gate < 0.99:
                # its reach (and the ease into and out of a hold, the grips' gate at the climb's start): what the
                # hold does not place is kept off the wall and the rungs (the clip's hands reach into the wall)
                _hand_off_ladder(c, m, g, side, f3, rr, spacing, 1.0 - gw * w_gate)
            if gripping and (hold is None or not hold.get('on')):
                lat = lat_of(pt, g['x'], g['y'], 0.24 if hand else 0.15)
                if hand:
                    z_ref = _grip_point(c, side, rr).z if spacing else pt.z + 0.05
                else:
                    P = _foot_world(c, side, c.body.feet)
                    z_ref = float(P[:, 2].min())
                if spacing:
                    k = int(round((z_ref - g['base_rung']) / spacing))
                    k = max(1, min(max_r, k)) if hand else max(0, min(max_r - 3, k))
                    if hand:
                        k = _hand_rung(c, m, g, side, grips[lb], cl, t_clip, k, max_r)
                    hz = g['base_rung'] + k * spacing
                else:
                    k, hz = None, (pt.z + 0.02 if hand else z_ref)
                hold = {'on': True, 'k': k, 'z': hz, 'lat': lat}
                m[key] = hold
            elif not gripping and hold is not None and hold.get('on'):
                hold['on'] = False
            if hold is None or gw <= 0.01:
                continue
            base = Vector((g['x'] + px * hold['lat'], g['y'] + py * hold['lat'], 0.0))
            if hand:
                w = gw * w_gate
                if spacing:
                    # a rung: the hand closes over it as the clip's holds do (palm down on the bar, the fingers curled
                    # over its far side): the bar's axis under the palm (_grip_point), not the wrist on the axis (the
                    # original's contact point ran the rung through the palm)
                    axis = base.copy()
                    axis.z = hold['z']
                    wr = c.pose.world_pos(side + 'Hand').copy()
                    tgt = wr + (axis - _grip_point(c, side, rr))
                    c._solve_arm_ik(side, _off_guard(c, side, c._smooth_limb_target(m, key, tgt, 0.6)), w)
                    if w > 0.95:                     # the forearm turned the hand: once more, the rest of the way
                        miss = axis - _grip_point(c, side, rr)
                        if miss.length > 0.004:
                            c._solve_arm_ik(side, _off_guard(c, side, c.pose.world_pos(side + 'Hand') + miss), 1.0)
                else:
                    tgt = base - f3 * 0.02           # a flat face (the scramble): the palm against it
                    tgt.z = hold['z']
                    c._solve_arm_ik(side, c._smooth_limb_target(m, key, tgt, 0.6), w)
                continue
            # a foot: where its ankle goes for the ball (a rung) or the toe (a face) to touch the hold
            for _it in range(2):
                an = c.pose.world_pos(side + 'Foot').copy()
                P = _foot_world(c, side, c.body.feet)
                rel = P - np.array(an)
                along_f = rel @ np.array(f3)
                if spacing:
                    front = along_f > along_f.min() + 0.70 * (along_f.max() - along_f.min())
                    q = P[front]
                    ball = q[q[:, 2] <= q[:, 2].min() + 0.01].mean(axis=0)
                    want = base + f3 * 0.01
                    want.z = hold['z'] + rr + 0.004
                    tgt = an + (want - Vector(ball))
                else:
                    toe = P[int(np.argmax(along_f))]
                    face = Vector((g['x'], g['y'], 0.0))
                    d_face = (face - Vector(toe)).dot(f3) - 0.01
                    tgt = an + f3 * d_face
                    tgt.z = hold['z'] + (an.z - float(P[:, 2].min()))
                c._solve_leg_ik(side, c._smooth_limb_target(m, key, tgt, 0.6) if _it == 0 else tgt, gw * w_gate)


HAND_OVER_SHOULDER = 0.10  # a ladder hold's rung stays at least this far over the shoulder to the hold's end (m)
HAND_FROM_SHOULDER = 0.21  # ... and at least this far from it (the arm solve leaves a target within 18 cm alone)


def _hand_rung(c, m, g, side, grip, cl, t_clip, k_clip, max_r):
    """the rung a hand takes hold of on a vertical ladder: within the arm's reach of the shoulder now, and still
    HAND_OVER_SHOULDER over it and HAND_FROM_SHOULDER from it when the hold ends (the body climbs on through the hold);
    of those the nearest to the clip's own (k_clip). (The library clip holds a leaning ladder's rungs at shoulder
    height: on a vertical one its shoulder came within 13 cm of the rung, an arm folded shut, and the solve gave up and
    left the hand in the wall.) None fits: the nearest to the hold's end height that the arm reaches"""
    sp, base = g['rung_spacing'], g['base_rung']
    sh = c.pose.world_pos(side + 'UpperArm')
    reach = 0.94 * ((sh - c.pose.world_pos(side + 'LowerArm')).length +
                    (c.pose.world_pos(side + 'LowerArm') - c.pose.world_pos(side + 'Hand')).length)
    f3 = Vector((g['fx'], g['fy'], 0.0))
    hd = abs((sh - Vector((g['x'], g['y'], 0.0))).dot(f3))       # the shoulder's distance from the rungs' line
    n = len(grip)
    j0 = int((t_clip % cl.duration) / cl.duration * n)
    left = 0
    while left < n and grip[(j0 + left) % n]:
        left += 1
    hold_s = left / n * cl.duration / max(1e-6, m.get('time_scale', 1.0))
    u_now = min(1.0, m['t'] / m['duration'])
    u_end = min(1.0, (m['t'] + hold_s) / m['duration'])
    a, b = c._sample_maneuver_path(m['path'], u_now), c._sample_maneuver_path(m['path'], u_end)
    rise = b['z'] - a['z']
    hd_end = max(0.0, hd - ((b['x'] - a['x']) * f3.x + (b['y'] - a['y']) * f3.y))   # it may still approach the rungs
    low = sh.z + rise + math.sqrt(max(HAND_OVER_SHOULDER ** 2, HAND_FROM_SHOULDER ** 2 - hd_end * hd_end))
    ok = [k for k in range(1, max_r + 1)
          if base + k * sp >= low and math.hypot(hd, base + k * sp - sh.z) <= reach]
    if ok:
        return min(ok, key=lambda k: abs(k - k_clip))
    within = [k for k in range(1, max_r + 1) if math.hypot(hd, base + k * sp - sh.z) <= reach] or [k_clip]
    return min(within, key=lambda k: abs(base + k * sp - low))


def _hand_points(c, side):
    """a hand's wrist, middle knuckle and middle fingertip where the controller's pose puts them (the wrist alone on a
    VRM without finger bones)"""
    p = c.pose
    H = c.h.humanoid
    out = [p.world_pos(side + 'Hand').copy()]
    kn, mid, tip = side + 'MiddleProximal', side + 'MiddleIntermediate', side + 'MiddleDistal'
    if kn in H:
        out.append(p.world_pos(kn).copy())
    if tip in H and mid in H:
        a, b = p.world_pos(mid), p.world_pos(tip)
        d = b - a
        out.append(b + (d.normalized() * 0.8 * d.length if d.length > 1e-6 else Vector()))
    return out


def _grip_point(c, side, rr):
    """where a bar of radius rr lies in a hand closed over it from above, as the ladder clip's holds close it (palm down
    on the bar, the fingers curled over its far side): under the palm, a quarter of the way from the middle knuckle to
    the wrist, the bar's radius and the palm's thickness below the joint line. Without finger bones: the wrist"""
    p = c.pose
    kn = side + 'MiddleProximal'
    wr = p.world_pos(side + 'Hand').copy()
    if kn not in c.h.humanoid:
        return wr
    palm = p.world_quat(side + 'Hand') @ Vector((0.0, 0.0, -1.0))     # the rest pose's palms face down (-Z)
    return wr * 0.25 + p.world_pos(kn) * 0.75 + palm * (rr + PALM_THICK)


def _hand_off_ladder(c, m, g, side, f3, rr, spacing, w):
    """a hand between its holds (the clip owns its reach) kept off what it climbs: on a ladder none of its points (the
    wrist, the middle knuckle, the fingertip) past the front of the rungs less HAND_CLEAR (a climber's hand comes back
    off a rung and goes up in front of the rungs to the next; the 6 cm behind them is no room for a hand), on a flat
    face none nearer it than HAND_CLEAR. (The library clip reaches for a leaning ladder's next rung half a metre ahead:
    on a vertical ladder its hand went 15-33 cm into the wall.) The arm moves straight back as far as the deepest point
    needs, at weight w, the push let go over a few frames once clear (no pop)"""
    if spacing:
        face = Vector((g['x'], g['y'], 0.0)) - f3 * rr                # the rungs' front
    else:
        face = Vector((g['face_x'], g['face_y'], 0.0)) if 'face_x' in g else Vector((g['x'], g['y'], 0.0))

    def need_now():
        return max(0.0, max((q - face).dot(f3) + HAND_CLEAR for q in _hand_points(c, side)))
    if w > 0.01:
        _pitch_hand_up(c, m, side, f3, need_now, w)
    need = need_now()
    pushes = m.setdefault('_hand_push', {})
    push = max(need, pushes.get(side, 0.0) * 0.55)
    pushes[side] = push if push > 0.001 else 0.0
    if pushes[side] <= 0.0 or w <= 0.01:
        return
    c._solve_arm_ik(side, _off_guard(c, side, c.pose.world_pos(side + 'Hand') - f3 * pushes[side]), min(1.0, w))


ARM_GUARD = 0.19            # the arm solve leaves alone a target within 18 cm of the shoulder: kept this far out


def _off_guard(c, side, tgt):
    """a hand target moved out from the shoulder to ARM_GUARD where it lies nearer (the controller's arm solve skips a
    target within 18 cm of the shoulder, leaving the clip's hand where it was: in a wall, on the ladder)"""
    sh = c.pose.world_pos(side + 'UpperArm')
    d = tgt - sh
    if d.length >= ARM_GUARD:
        return tgt
    if d.length < 1e-6:
        d = Vector((0.0, 0.0, 1.0))
    return sh + d.normalized() * ARM_GUARD


def _pitch_hand_up(c, m, side, f3, need_fn, w, max_deg=80):
    """a reaching hand whose fingers point into the wall (the leaning ladder's clip reaches forward): turned at the
    wrist about the body's width, fingers up, as little as clears them (5 deg steps to max_deg, the least need if none
    does), times the weight w; the turn let go over a few frames (no snap): a climber's open hand goes up the ladder
    fingers first"""
    p = c.pose
    nm = side + 'Hand'
    axis = Vector((-f3.y, f3.x, 0.0))
    q0 = p.N[nm].copy()
    best = (need_fn(), 0.0)
    if best[0] > 0.0:
        for deg in range(5, max_deg + 1, 5):
            p.N[nm] = q0.copy()
            p.invalidate()
            p.apply_world_delta(nm, Quaternion(axis, -math.radians(deg)))
            n = need_fn()
            if n < best[0] - 1e-4:
                best = (n, math.radians(deg))
            if n <= 0.0:
                break
        p.N[nm] = q0
        p.invalidate()
    pitches = m.setdefault('_hand_pitch', {})
    ang = max(best[1], pitches.get(side, 0.0) * 0.6)
    pitches[side] = ang if ang > math.radians(0.5) else 0.0
    if pitches[side] > 0.0:
        p.apply_world_delta(nm, Quaternion(axis, -pitches[side] * min(1.0, w)))


def lean_to_reach(c, side, tgt, w, max_deg=28.0):
    """this edition's: a contact the arm cannot reach from where the clip holds the shoulder (a vault over low cover,
    the body high enough for its tucked legs to clear it) bends the spine toward it: the least turn of the spine (up to
    max_deg, times the contact's weight) that brings the shoulder within the arm's reach, then the arm solved again"""
    p = c.pose
    H = c.h.humanoid
    if 'spine' not in H or w <= 0.05:
        return 0.0
    up, lo_, hand = side + 'UpperArm', side + 'LowerArm', side + 'Hand'
    if (p.world_pos(hand) - tgt).length < 0.012:
        return 0.0
    reach = (p.world_pos(up) - p.world_pos(lo_)).length + (p.world_pos(lo_) - p.world_pos(hand)).length - 0.01
    piv = p.world_pos('spine').copy()
    a = p.world_pos(up) - piv
    if (piv + a - tgt).length <= reach:
        return 0.0
    ax = a.cross(tgt - piv)
    if ax.length < 1e-8:
        return 0.0
    ax.normalize()
    lo, hi = 0.0, math.radians(max_deg) * min(1.0, w)
    if (piv + Quaternion(ax, hi) @ a - tgt).length > reach:
        lo = hi                                              # the most it may lean still falls short: lean it all
    for _ in range(14):
        if lo >= hi:
            break
        mid = 0.5 * (lo + hi)
        if (piv + Quaternion(ax, mid) @ a - tgt).length > reach:
            lo = mid
        else:
            hi = mid
    ang = hi if lo < hi else lo
    p.apply_world_delta('spine', Quaternion(ax, ang))
    c._solve_arm_ik(side, tgt, w)
    return ang


def _foot_world(c, side, F):
    """a foot's points (a foot_points set) where the controller's pose puts them: (n, 3)"""
    p = c.pose
    p_an = p.world_pos(side + 'Foot')
    W_ft = p.world_quat(side + 'Foot')
    out = [F[side]['Foot'] @ np.array(W_ft.to_matrix()).T + np.array(p_an)]
    if len(F[side]['Toes']) and (side + 'Toes') in c.h.humanoid:
        W_to = p.world_quat(side + 'Toes')
        p_to = p_an + W_ft @ c.body.leg[side]['t']
        out.append(F[side]['Toes'] @ np.array(W_to.to_matrix()).T + np.array(p_to))
    return np.concatenate(out, axis=0)


_UP_TILT = Vector((0.0123, 0.0217, 1.0)).normalized()


def _inside(world, p):
    """p inside a closed solid of the world: an odd count of crossings on a slightly tilted ray up (an open ground
    plane counts once from under it)"""
    n, org = 0, Vector(p)
    for _ in range(16):
        h = world.ray_cast(org, _UP_TILT, 50.0)
        if not h.hit:
            break
        n += 1
        org = h.point + _UP_TILT * 1e-5
    return n % 2 == 1


def _over(world, P):
    """where the solids test's downward rays start: over everything in the world. (Started 3 m over a foot point, a ray
    begins inside a wall taller than that, meets the wall's underside instead of its top, and a boot kicked into the
    face of a 3.2 m wall read as outside it)"""
    top = getattr(world, 'top', None)
    return top + 1.0 if top is not None else P[:, 2] + 50.0


def _foot_depth(c, side, pts, world, f3):
    """how far a foot's deepest point inside a solid lies behind the face the travel meets (0: none inside)"""
    P = _foot_world(c, side, pts)
    G = world.h(P[:, 0], P[:, 1], z_from=_over(world, P))
    worst = 0.0
    for i in np.flatnonzero((G > -1e8) & (G - P[:, 2] > 0.002)):
        if _inside(world, P[i]):
            hb = world.ray_cast(Vector(P[i]), -f3, 1.0)
            worst = max(worst, hb.distance if hb.hit else 1.0)
    return worst


def _pitch_foot_out(c, side, pts, world, f3, max_deg=70):
    """a foot pointing into a face (a mantle's high step, its toes in the wall): turned at the ankle about its own
    lateral axis, toes up or down, as little as clears it (10 deg steps to max_deg; the least depth if none clears),
    so its sole comes against the face as a climber's does -> the turn (rad)"""
    p = c.pose
    nm = side + 'Foot'
    base = _foot_depth(c, side, pts, world, f3)
    if base <= 0.0:
        return 0.0
    ax = (p.world_quat(nm) @ Vector((1.0, 0.0, 0.0))).normalized()
    q0 = p.N[nm].copy()
    best = (base, 0.0)
    for deg in range(10, max_deg + 1, 10):
        for sgn in (1.0, -1.0):
            p.N[nm] = q0.copy()
            p.invalidate()
            p.apply_world_delta(nm, Quaternion(ax, sgn * math.radians(deg)))
            d = _foot_depth(c, side, pts, world, f3)
            if d < best[0] - 1e-4:
                best = (d, sgn * math.radians(deg))
        if best[0] <= 0.0:
            break
    p.N[nm] = q0
    p.invalidate()
    if best[1]:
        p.apply_world_delta(nm, Quaternion(ax, best[1]))
    return best[1]


def _leg_to(c, side, target, keep_turn=False):
    """the two-bone leg solve (the controller's _solve_limb_ik at full weight) without its 18 cm guard: a foot folded
    up against the hip must still come out of a face. keep_turn: the foot keeps its world turn (the move is the boot's
    own translation, as the solids search tested it)"""
    p = c.pose
    up, mid, end = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
    w_ft = p.world_quat(end).copy() if keep_turn else None
    a, b, e = p.world_pos(up).copy(), p.world_pos(mid).copy(), p.world_pos(end).copy()
    lu, ll = (a - b).length, (b - e).length
    dist = min(max((a - target).length, abs(lu - ll) + 0.02), lu + ll - 0.005)
    desired = math.acos(max(-1.0, min(1.0, (lu * lu + ll * ll - dist * dist) / (2 * lu * ll))))
    vba, vbc = a - b, e - b
    axis = vbc.cross(vba)
    if axis.length_squared > 1e-8:
        p.apply_world_delta(mid, Quaternion(axis.normalized(), vba.angle(vbc, 0.0) - desired))
    e2 = p.world_pos(end).copy()
    if (e2 - a).length > 1e-6 and (target - a).length > 1e-6:
        p.apply_world_delta(up, (e2 - a).normalized().rotation_difference((target - a).normalized()))
    if w_ft is not None:
        p.set_world_quat(end, w_ft)
    p.invalidate()


def _inside_mask(world, P, idx, top):
    """which of the points P[idx] lie inside a closed solid of the world: under a surface (a ray down from over it all)
    and inside by the parity ray -> bool array over P"""
    out = np.zeros(len(P), dtype=bool)
    if not len(idx):
        return out
    G = world.h(P[idx, 0], P[idx, 1], z_from=top)
    for k in np.flatnonzero((G > -1e8) & (G - P[idx, 2] > 0.002)):
        out[idx[k]] = _inside(world, P[idx[k]])
    return out


def _clear_move(world, P, ins, f3, first=(), prefer=None):
    """the least move of a whole foot in the travel's plane (back off the face or toward it, up or down, out to
    SOLID_REACH) that leaves every one of its points outside the solids, those the move would carry into one included.
    A boot wedged between a ladder's rung and the wall behind it comes out of neither by a move straight back or straight
    up (back takes it out of the wall into the rung, up out of the rung into the wall): the search finds the rung's top
    or the space before it. `first`: moves tried before the search (taken if clear); the search runs on a 3 cm grid
    over the foot's points thinned to 2 cm (each inside point kept), then 1 cm round the best, each candidate checked on
    every point. prefer: the move chosen on the last frame, kept unless another is clearly shorter (a foot set on a rung
    one frame and before it the next shakes) -> Vector or None"""
    top = (world.top + 1.0) if getattr(world, 'top', None) is not None else float(P[:, 2].max()) + 50.0
    near = np.empty(len(P))
    for i, p in enumerate(P):
        hit = world.tree.find_nearest(Vector(p), SOLID_REACH + 0.05)
        near[i] = hit[3] if hit[0] is not None else 9.0
    near[ins] = 0.0

    def clear(v, idx_all):
        idx = idx_all[near[idx_all] <= v.length + 0.004]
        return not _inside_mask(world, P + np.array(v), idx, top).any()
    every = np.arange(len(P))
    for v in first:
        if clear(v, every):
            return v
    _u, keep = np.unique(np.floor(P / 0.02).astype(np.int64), axis=0, return_index=True)
    thin = np.union1d(keep, np.asarray(ins, dtype=np.int64))

    def cost(v):
        L = v.length
        if prefer is None or prefer.length < 1e-6 or L < 1e-9:
            return L
        return L * (1.0 + 0.6 * (1.0 - v.normalized().dot(prefer.normalized())))

    def grid(step, lo, hi, c0=Vector()):
        out = []
        for i in range(lo, hi + 1):            # i > 0: back off the face (-f3); i < 0: toward it
            for j in range(lo, hi + 1):        # j > 0: up; j < 0: down
                v = c0 + Vector((-f3.x * i * step, -f3.y * i * step, j * step))
                if v.length > 1e-9 and v.length <= SOLID_REACH + 1e-9:
                    out.append(v)
        return sorted(out, key=cost)
    best = None
    for v in grid(0.03, -2, int(round(SOLID_REACH / 0.03))):
        if clear(v, thin) and clear(v, every):
            best = v
            break
    if best is None:
        return None
    for v in grid(SOLID_GRID, -2, 2, best):
        if cost(v) < cost(best) - 1e-9 and clear(v, every):
            return v
    return best


def _contact_feet(c):
    """the feet's points for the solids test: the whole foot every 12 mm plus the sole's own dense points"""
    pts = getattr(c, '_solid_feet', None)
    if pts is None:
        from ..ground import foot_points
        whole = foot_points(c.h, band=0.30, voxel=0.012)
        pts = {}
        for s in SIDES:
            if whole.get(s) is None:
                pts[s] = None
                continue
            pts[s] = {b: np.concatenate([whole[s][b], c.body.feet[s][b]]) for b in ('Foot', 'Toes')}
        c._solid_feet = pts
    return pts


def feet_out_of_solids(c, m):
    """this edition's last word on a maneuver frame's feet: no part of a foot inside a solid. The clip owns the legs and
    the contact IK pulls them at partial weight, so a kick into a wall face, a toe into the cover a vault crosses, a
    crouch sunk into the top a mount ends on, a boot through a rung all happen; here each foot with points inside a
    solid (the whole foot every 12 mm and its sole; under a surface, confirmed by a parity ray) moves out. Into a face,
    the foot first turns its sole against it at the ankle (a mantle's high step points its toes into the wall); then
    the whole boot takes the least move in the travel's plane that leaves it clear (_clear_move: back off the face or
    up out of the solid, or both, as a boot wedged between a ladder's rung and the wall needs), the same way as on the
    last frame unless another is clearly shorter, and a full-weight two-bone solve moves the leg there with the foot's
    world turn kept (_leg_to: no 18 cm guard, a foot folded to the hip still comes out). Where nothing within
    SOLID_REACH is clear, the shorter of straight up and straight back. SOLID_PASSES rounds. The solids are
    c.contact_world's (default the walking world: pass one with the ladder's rungs in it)"""
    pts = _contact_feet(c)
    world = getattr(c, 'contact_world', None) or c.world
    g = m.get('grab') or {}
    if 'fx' in g:
        f3 = Vector((g['fx'], g['fy'], 0.0))
    else:
        f3 = Vector((math.sin(c._heading), -math.cos(c._heading), 0.0))
    moved = 0.0
    left = {}
    prev = m.setdefault('_solid_move', {})
    for side in SIDES:
        if pts.get(side) is None:
            continue
        took = None
        for rnd in range(SOLID_PASSES + 1):
            P = _foot_world(c, side, pts)
            top = _over(world, P)
            ins = np.flatnonzero(_inside_mask(world, P, np.arange(len(P)), top))
            if not len(ins):
                left.pop(side, None)
                break
            up_need = back_need = 0.0
            for i in ins:
                p = Vector(P[i])
                hu = world.ray_cast(p, Vector((0.0, 0.0, 1.0)), 3.0)
                hb = world.ray_cast(p, -f3, 1.0)
                up_need = max(up_need, hu.distance if hu.hit else math.inf)
                back_need = max(back_need, hb.distance if hb.hit else math.inf)
            left[side] = round(1000 * min(up_need, back_need), 1)
            if rnd == SOLID_PASSES:
                break
            if rnd == 0 and back_need < up_need:
                # into a face: first the foot turns its sole against it (toes up or down at the ankle)
                if _pitch_foot_out(c, side, pts, world, f3):
                    moved = max(moved, 0.001)
                    continue
            axis = None
            if math.isfinite(min(up_need, back_need)):
                axis = Vector((0.0, 0.0, up_need + 0.004)) if up_need <= back_need else -f3 * (back_need + 0.004)
            v = _clear_move(world, P, ins, f3, first=[axis] if axis is not None else [], prefer=prev.get(side))
            if v is None:
                if axis is None:
                    break
                v = axis
            an = c.pose.world_pos(side + 'Foot').copy()
            _leg_to(c, side, an + v, keep_turn=True)
            took = v if took is None else took + v
            moved = max(moved, v.length)
        if took is not None:
            prev[side] = took
    m['_solids_moved'] = moved
    if left:
        m.setdefault('_solids_left', []).append((round(m.get('t', 0.0), 3), dict(left)))
        c.log(f"[eidoverse-controller] {m['type']} t={m.get('t', 0.0):.3f}: a foot still inside a solid after "
              f"{SOLID_PASSES} rounds: {left} mm")
    return moved


# the auto-trigger's moves (controller._maybe_auto_maneuver calls them by these names) and the contact IK by grab type
AUTO = {'vault': start_vault_over, 'mount': start_mount_onto, 'wall_scramble': start_wall_scramble,
        'gap_jump': start_gap_jump}
HAND_IK = {'climb': apply_hand_ik, 'vaultGeo': apply_hand_ik, 'ladder': apply_hand_ik}
