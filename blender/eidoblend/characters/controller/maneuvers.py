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
'ladder' (hands and feet latching the rungs, or holds on a flat face).

Blender's axes: the travel (fx, fy) = (sin heading, -cos heading); a keypoint is {u, x, y, z} with z the feet's height;
the original's perp (-fz, fx) in three is (fy, -fx) here. The clip's root motion (clips.ControllerClip.root_motion) is the
hips curve in the armature's axes: up is z, the clip's forward is -y.
"""

import math

from mathutils import Vector

SIDES = ('left', 'right')


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


# ================================================================================================ the moves
def start_vault_over(c, scan, ob, fx, fy):
    """_startVaultOver: the vault clip's action window (0.20 .. 0.62) over a root path fitted from its own hips curve"""
    cur = c._center.copy()
    feet = _feet(c)
    land_d = min(ob['landing_d'] + 0.25, c.maneuver_scan_range)
    land_z = ob['landing_y'] if ob['landing_y'] is not None else feet
    duration = max(0.85, min(1.2, land_d / 2.0))
    VC0, VC1 = 0.20, 0.62
    rm = _rm(c, 'vault')
    if rm:
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
    plant_d = ob['start_d'] + min(0.22, (ob['end_d'] - ob['start_d']) * 0.5)
    grab = {'type': 'vaultGeo', 'window': (0.06, 0.85), 'fx': fx, 'fy': fy, 'perp': (fy, -fx), 'top': ob['top_y'],
            'd0': ob['start_d'] - 0.12, 'd1': ob['end_d'] + 0.12, 'ox': cur.x, 'oy': cur.y,
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
    d_end = ob['start_d'] + 0.32
    zs = d_end / z_travel if z_travel > 0.15 else 0.0
    face_max_d = max(0.04, ob['start_d'] - (c.radius + 0.22))
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
            'lip_x': cur.x + fx * ob['start_d'], 'lip_y': cur.y + fy * ob['start_d']}
    return c._start_maneuver({'type': 'mount', 'slot': 'climbLedge', 'slot_fallbacks': [slot, 'jump'], 'path': path,
                              'duration': duration, 'landing_ground_y': top, 'grab': grab,
                              'clip_window': (i_start / N, i_end / N),
                              'visual_sink': {'amount': 0.65, 'u0': 0.55, 'u1': 0.98}})


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
    height, face_start = ob['rise'], ob['start_d']
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


def climb_ladder(c, height=None, rate=0.55, first_rung=0.25, rung_spacing=0.28, time_scale=1.0):
    """climbLadder: the climbLadder clip looped at its own pace while the root rises at `rate` until the chest reaches
    the lip, then chained into the mount's mantle; hands and feet latch the rungs (first_rung up, every rung_spacing)"""
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
    face_start = ob['start_d'] if ob else 0.35
    face_d = max(0.06, face_start - (c.radius + 0.34))
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
    grab = {'type': 'ladder', 'window': (u1 * 0.7, 0.98), 'fx': fx, 'fy': fy, 'perp': (fy, -fx),
            'x': cur.x + fx * (face_start - 0.09), 'y': cur.y + fy * (face_start - 0.09),
            'base_rung': feet + first_rung, 'rung_spacing': rung_spacing,
            'max_rung': int(math.floor((height - 0.10) / rung_spacing))}

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
    if u < w0 or u > w1:
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
            if g['top'] - 0.50 < hp.z < g['top'] + 0.01 and along > -0.10:
                # the top plane is a floor for the hands from the grab through the crouch: the pull-up over planted hands
                depth = g['top'] + 0.01 - hp.z
                lat = lat_of(hp, g['lip_x'], g['lip_y'], 0.35)
                at = max(0.10, min(0.45, along))
                tgt = Vector((g['lip_x'] + px * lat + fx * at, g['lip_y'] + py * lat + fy * at, g['top'] + 0.02))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt, 0.7), min(0.98, 0.25 + depth * 4.5))
            elif hp.z < g['top'] - 0.06 and along > -0.02:
                lat = lat_of(hp, g['lip_x'], g['lip_y'], 0.40)                  # deep in the face: pushed out
                tgt = Vector((g['lip_x'] + px * lat - fx * 0.04, g['lip_y'] + py * lat - fy * 0.04, hp.z))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt, 0.7), 0.90)
            elif hp.z >= g['top'] - 0.28 and 0.45 < to_top < 1.10:
                near = _sm(g['top'] - 0.28, g['top'] - 0.10, hp.z)              # the grab: the lip line
                lat = lat_of(hp, g['lip_x'], g['lip_y'], 0.32)
                tgt = Vector((g['lip_x'] + px * lat, g['lip_y'] + py * lat, g['top'] + 0.02))
                c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandClimb', tgt), 0.60 * near)
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
                lat = lat_of(hp, g['px'], g['py'], 0.32)
                tgt = Vector((g['px'] + px * lat, g['py'] + py * lat, g['top'] + 0.02))
                w = 0.85 * _sm(1.20, 0.85, (sh - tgt).length)
                if w > 0.02:
                    c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'HandVault', tgt), w)
        for side in SIDES:
            fp = bone(side + 'Foot')
            if fp is None:
                continue
            along = (fp.x - g['ox']) * fx + (fp.y - g['oy']) * fy
            if g['d0'] - 0.05 < along < g['d1'] + 0.05 and fp.z < g['top'] + 0.04:
                c._solve_leg_ik(side, c._smooth_limb_target(m, side + 'FootVault', Vector((fp.x, fp.y, g['top'] + 0.07))),
                                0.85)
    elif g['type'] == 'ladder':
        w_gate = ramp(w0, w1, 1.0)
        if w_gate <= 0.01:
            return
        spacing = g.get('rung_spacing')
        max_r = g.get('max_rung', 99)

        def along_of(pt):
            return (pt.x - g['x']) * fx + (pt.y - g['y']) * fy
        for side in SIDES:
            hp = bone(side + 'Hand')
            if hp is not None:
                along = along_of(hp)
                near_lo = -0.26 if spacing else -0.42
                w = 0.0
                if along > 0.0:
                    w = min(0.95, 0.65 + along * 2.5)
                elif along > near_lo:
                    w = 0.65 * _sm(near_lo, -0.05, along)
                if w > 0.02:
                    key = side + 'RungK'
                    if spacing:
                        k_pref = round((hp.z + 0.05 - g['base_rung']) / spacing)
                        k = m.get(key)
                        if k is None or (along < -0.10 and k_pref != k) or k_pref - k >= 2:
                            k = k_pref
                        k = max(1, min(max_r, k))
                        m[key] = k
                        hz = g['base_rung'] + k * spacing
                    else:
                        held = m.get(key)
                        if held is None or along < -0.10:
                            held = hp.z + 0.02
                        elif hp.z - held > 0.55:
                            held = hp.z - 0.10
                        m[key] = held
                        hz = held
                    lat = lat_of(hp, g['x'], g['y'], 0.24)
                    tgt = Vector((g['x'] + px * lat - fx * 0.02, g['y'] + py * lat - fy * 0.02, hz))
                    c._solve_arm_ik(side, c._smooth_limb_target(m, side + 'Hand', tgt, 0.55), w * w_gate)
            fp = bone(side + 'Foot')
            if fp is not None:
                along = along_of(fp)
                near_lo = -0.22 if spacing else -0.38
                w = 0.0
                if along > 0.0:
                    w = min(0.95, 0.65 + along * 2.5)
                elif along > near_lo:
                    w = 0.60 * _sm(near_lo, -0.05, along)
                if w > 0.02:
                    key = side + 'FootRungK'
                    if spacing:
                        k_pref = round((fp.z - g['base_rung']) / spacing)
                        k = m.get(key)
                        if k is None or (along < -0.10 and k_pref != k) or k_pref - k >= 2:
                            k = k_pref
                        k = max(0, min(max_r - 3, k))
                        m[key] = k
                        fz = g['base_rung'] + k * spacing
                    else:
                        held = m.get(key)
                        if held is None or along < -0.10:
                            held = fp.z
                        elif fp.z - held > 0.50:
                            held = fp.z - 0.10
                        m[key] = held
                        fz = held
                    lat = lat_of(fp, g['x'], g['y'], 0.15)
                    tgt = Vector((g['x'] + px * lat - fx * 0.02, g['y'] + py * lat - fy * 0.02, fz + 0.03))
                    c._solve_leg_ik(side, c._smooth_limb_target(m, side + 'Foot', tgt, 0.55), w * w_gate)


# the auto-trigger's moves (controller._maybe_auto_maneuver calls them by these names) and the contact IK by grab type
AUTO = {'vault': start_vault_over, 'mount': start_mount_onto, 'wall_scramble': start_wall_scramble,
        'gap_jump': start_gap_jump}
HAND_IK = {'climb': apply_hand_ik, 'vaultGeo': apply_hand_ik, 'ladder': apply_hand_ik}
