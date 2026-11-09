"""VRMCharacterController's options, one behaviour each, measured on the controller's own telemetry (no plant, no
render: the controller frame by frame, as the WebGPU runtime runs it).

    test_controller_options.py [--vrm aletheia]

The lanes (Blender x; every lane runs along +Y from y = -5, the course's start):
    x = 0    terrain_base's course: flat, a 10 cm bump, small stairs up (0.10 / 0.30 x 5), flat, normal stairs down
             (0.18 / 0.28 x 4), flat, large stairs up (0.22 / 0.26 x 3), flat, a 15 deg ramp up and down, flat
    x = 6    a wall across the lane at y = 0 (2 m high), and a second one at 45 deg at x = 9
    x = 12   a 1.5 m platform from y = -6 to y = -1 and its edge
    x = 15.. the maneuver planner's lanes: a 0.55 m wall (vault), a 1.2 m block (climbLedge), a 2.0 m block
             (climbWallUp), a 3.0 m block (wall scramble), a 1.1 m gap between raised slabs (gap jump)
Each check names the option(s) it exercises and prints the numbers it judged.
"""

import math
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CONTROLLER_PRESETS, CollisionWorld, VRMCharacterController  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'aletheia')
R = T.Report(T.arg(ARGS, '--tag', f'options_{VRM}'))
R['vrm'] = VRM
DT = 1.0 / 30.0
ME = None
WORLD = None


def box(name, x0, x1, y0, y1, z0, z1, rot_z=0.0):
    me = bpy.data.meshes.new(name)
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    me.from_pydata(V, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if rot_z:
        c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0.0))
        for v in me.vertices:
            p = v.co - c
            v.co = c + Vector((p.x * math.cos(rot_z) - p.y * math.sin(rot_z), p.x * math.sin(rot_z) + p.y * math.cos(rot_z),
                               p.z))
    return ob


SEG = {}


def build():
    names = ['flat0', 'bump', 'flat1', 'small_up', 'flat2', 'small_down', 'flat3', 'normal_up', 'flat4', 'normal_down',
             'flat5', 'large_up', 'flat6', 'large_down', 'flat7', 'ramp_up', 'flat8', 'ramp_down', 'flat9']
    course = T.course({'type': 'obstacle_course', 'segments': [
        {'kind': 'flat', 'length': 2.0}, {'kind': 'bump', 'height': 0.10, 'depth': 0.30}, {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'up'}, {'kind': 'flat', 'length': 1.2},
        {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'down'}, {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'up'}, {'kind': 'flat', 'length': 1.2},
        {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'down'}, {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 3, 'dir': 'up'}, {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 3, 'dir': 'down'}, {'kind': 'flat', 'length': 1.5},
        {'kind': 'ramp', 'angleDeg': 15, 'horizLen': 2.0, 'dir': 'up'}, {'kind': 'flat', 'length': 1.0},
        {'kind': 'ramp', 'angleDeg': 15, 'horizLen': 2.0, 'dir': 'down'}, {'kind': 'flat', 'length': 3.0}]})
    for i, n in enumerate(names):
        SEG[n] = course.segment(i)
    box('wall', 4.5, 7.5, 0.0, 0.3, 0.0, 2.0)
    box('wall45', 8.0, 10.0, -0.15, 0.15, 0.0, 2.0, rot_z=math.radians(45))
    box('platform', 11.0, 13.0, -6.0, -1.0, 0.0, 1.5)
    box('vault_wall', 14.5, 15.5, 0.0, 0.3, 0.0, 0.55)
    box('ledge_block', 16.5, 17.5, 0.0, 1.5, 0.0, 1.2)
    box('climb_block', 18.5, 19.5, 0.0, 2.5, 0.0, 2.0)
    box('scramble_block', 20.5, 21.5, 0.0, 2.5, 0.0, 3.0)
    box('gap_a', 22.5, 23.5, -6.0, -1.0, 0.0, 0.5)
    box('gap_b', 22.5, 23.5, 0.1, 4.0, 0.0, 0.5)
    # x = -9: a 6 cm block under one foot's probe line only, clear of the centre line the ahead probes follow (the
    # contact support); x = 70: a platform over nothing, beyond the 120 m ground (the IK grounding grace); x = -14:
    # a 45 deg slab at the upper-body cylinder's height (max_slope)
    box('one_foot_block', -9.0 + 0.04, -9.0 + 0.30, -2.0, -1.4, 0.0, 0.06)
    box('void_platform', 69.0, 71.0, -6.0, -1.0, 0.0, 0.5)
    me = bpy.data.meshes.new('slab45')
    me.from_pydata([(-15.5, 0.0, 0.9), (-12.5, 0.0, 0.9), (-12.5, 1.5, 2.4), (-15.5, 1.5, 2.4)], [], [(0, 1, 2, 3)])
    bpy.context.scene.collection.objects.link(bpy.data.objects.new('slab45', me))


def ctrl(x=0.0, y=-5.0, z=0.0, heading=math.pi, attach=None, **opts):
    o = dict(start_position=(x, y, z), start_heading=heading, log=lambda *a: None)
    o.update(opts)
    c = VRMCharacterController(ME, WORLD, **o)
    c.load_standard_animations()
    c.attach_locomotion(leg_ik='default', **(attach or {}))
    return c


def drive(c, frames, direction=(0.0, 1.0), stop_y=None, each=None):
    out = []
    for k in range(frames):
        d = direction(c, k) if callable(direction) else direction
        if stop_y is not None and c.feet_world_position.y >= stop_y:
            d = (0.0, 0.0)
        c.locomote(DT, d)
        sf = c.support_frame or {}
        rec = {'k': k, 'p': c.feet_world_position.copy(), 'c': c.body_translation().copy(), 'heading': c._heading,
               'scene_heading': c.scene_heading, 'grounded': c.grounded, 'speed': c.speed_actual,
               'mode': (sf.get('body') or {}).get('support_mode'), 'body': dict(sf.get('body') or {}),
               'anim': dict(sf.get('animation') or {}), 'probes': dict(sf.get('probes') or {}),
               'w': {k_: (a.weight if a else 0.0) for k_, a in c._actions.items()}, 'climb': c.signed_climb_angle_deg,
               'scale': c.speed_scale, 'lean': getattr(c, 'hips_lean_deg', 0.0), 'drop': c._smooth_body_drop,
               'fpo': c._leg_ik.foot_plant_forward_offset if c._leg_ik else None,
               'reach': c._leg_ik.extra_cast_reach_scale if c._leg_ik else None,
               'target': getattr(c, 'target_forward_speed', None), 'smooth': c._smooth_fwd_speed,
               'blocked': c._climb_blocked, 'early': c.small_stair_ascent_early_up, 'vy': c._velocity_y,
               'tread_run': c.ahead_tread_run, 'ground_y': c.ground_y}
        out.append(rec)
        if each:
            each(c, rec)
    return out


def main():
    global ME, WORLD
    T.S.clean_scene(fps=30)
    build()
    ME = load_vrm(VRM, name=VRM)
    WORLD = CollisionWorld()
    # ---- enable_turning (off: the original's default), max_turn_rate
    c = ctrl()
    rr = drive(c, 30, (1.0, 1.0))
    sh = {round(r['scene_heading'], 4) for r in rr}
    d = rr[-1]['p'] - rr[0]['p']
    R.check('enable_turning=False: the body travels the input\'s direction, its facing stays at pi',
            sh == {round(math.pi, 4)} and abs(math.atan2(d.y, d.x) - math.pi / 4) < 0.05,
            f'facing {sh}, travel {math.degrees(math.atan2(d.y, d.x)):.1f} deg')
    c = ctrl(enable_turning=True, max_turn_rate=2.0)
    rr = drive(c, 30, (1.0, 0.0))
    steps = [abs(((b['heading'] - a['heading']) + math.pi) % (2 * math.pi) - math.pi) for a, b in zip(rr, rr[1:])]
    R.check('enable_turning=True, max_turn_rate=2: the facing turns toward the input at 2 rad/s at most',
            max(steps) <= 2.0 * DT + 1e-6 and abs(rr[-1]['heading'] - (-math.pi / 2) % (2 * math.pi) + 2 * math.pi) < 3.2,
            f'largest turn a frame {math.degrees(max(steps)):.2f} deg (cap {math.degrees(2 * DT):.2f})')
    # ---- cylinder_radius, skin: into the wall and along the 45 deg wall
    for rad in (0.22, 0.35):
        c = ctrl(x=6.0, y=-2.0, cylinder_radius=rad, auto_maneuvers=False)    # the wall, not the planner
        rr = drive(c, 75, (0.0, 1.0))
        gap = 0.0 - rr[-1]['c'].y
        R.check(f'cylinder_radius={rad}, skin=0.05: walking into a wall stops the body radius + skin short of it',
                abs(gap - (rad + 0.05)) < 0.03, f'stopped {gap:.3f} m short')
    c = ctrl(x=9.0, y=-2.0, auto_maneuvers=False)
    rr = drive(c, 80, (0.0, 1.0))
    R.check('the cylinder slides along a 45 deg wall (move and slide)', abs(rr[-1]['c'].x - rr[0]['c'].x) > 0.3,
            f'slid {rr[-1]["c"].x - rr[0]["c"].x:+.2f} m across while pushing ahead')
    # ---- max_slope (Rapier's setMaxSlopeClimbAngle): it judges what the upper-body cylinder touches, never the ground
    # under it (the body's height is the probes'), so it is measured on the cylinder's move and slide against a 45 deg
    # slab at hip height: climbable at 60 (the default: no wall), a wall at 30
    c = ctrl(x=-14.0, y=-1.0)
    centre = c.body_translation()
    for ms, wall in ((60, False), (30, True)):
        dx, dy = WORLD.move_and_slide(centre, (0.0, 1.2), c.radius, c.half_height, skin=c.skin,
                                      max_climb_normal=math.cos(math.radians(ms)))
        R.check(f'max_slope={ms}: a 45 deg slab touching the cylinder is {"a wall" if wall else "climbable (no wall)"}',
                (dy < 1.0) == wall, f'the cylinder moves {dy:.2f} of 1.20 m (centre at {centre.z:.2f} m)')
    # ---- gravity, max_fall_speed, fall_threshold: off the 1.5 m platform (its edge 1.5 m ahead)
    c = ctrl(x=12.0, y=-2.5, z=1.5, gravity=-9.81, max_fall_speed=3.0)
    rr = drive(c, 75, (0.0, 1.0))
    vys = [r['vy'] for r in rr]
    R.check('gravity / max_fall_speed=3: the fall accelerates at g and caps at 3 m/s', min(vys) >= -3.0 - 1e-9 and
            any(abs(v + 3.0) < 1e-6 for v in vys), f'fall speeds down to {min(vys):.2f} m/s')
    for ft, gr in ((0.4, False), (2.0, True)):
        c = ctrl(x=12.0, y=-2.5, z=1.5, fall_threshold=ft)
        rr = drive(c, 75, (0.0, 1.0))
        air = sum(1 for r in rr if not r['grounded'])
        R.check(f'fall_threshold={ft}: the 1.5 m edge is {"a step down (no airborne frame)" if gr else "a fall"}',
                (air == 0) == gr and rr[-1]['p'].y > -0.5, f'{air} airborne frames, reached y = {rr[-1]["p"].y:.2f}')
    c = ctrl(x=12.0, y=-2.5, z=1.5, land_on_contact=True)
    rr = drive(c, 75, (0.0, 1.0))
    land = next((r for r in rr[1:] if r['grounded'] and not rr[r['k'] - 1]['grounded']), None)
    R.check('land_on_contact (this edition): the fall lands when the feet reach the ground', land is not None and
            abs(land['p'].z - 0.0) < 0.12, f'feet at {land["p"].z if land else None} on the landing frame')
    # ---- max_climb_angle: the 2 m wall ahead blocks the climb
    for mca in (50, 89):
        c = ctrl(x=6.0, y=-1.0, max_climb_angle=mca, auto_maneuvers=False)
        rr = drive(c, 20, (0.0, 1.0))
        R.check(f'max_climb_angle={mca}: a 2 m wall ahead {"blocks" if mca < 80 else "does not block"} the climb',
                any(r['blocked'] for r in rr) == (mca < 80), f'blocked frames {sum(1 for r in rr if r["blocked"])}')
    # ---- look_ahead, ahead_probe_count
    c = ctrl(look_ahead=0.5, ahead_probe_count=10)
    rr = drive(c, 5, (0.0, 1.0))
    ys = rr[-1]['probes'].get('raw_ys') or []
    R.check('look_ahead=0.5, ahead_probe_count=10: ten probes out to 0.5 m', len(ys) == 10 and abs(ys[-1]['d'] - 0.5) < 1e-9,
            f'{len(ys)} probes, last at {ys[-1]["d"] if ys else None} m')
    # ---- the default course run: stairs, ramps, bump; the gait tree's options read on it
    base = drive(ctrl(), 1100, (0.0, 1.0), stop_y=SEG['flat9']['y0'] + 1.5)
    modes = sorted(set(r['mode'] or '-' for r in base))
    R['course_modes'] = modes
    past_bump = SEG['bump']['y1'] + 0.3
    ear = [r for r in base if r['early'] and r['p'].y > past_bump]
    k_up = next((r['k'] for r in base if r['mode'] == 'stairUp' and r['p'].y > past_bump), None)
    R.check('small_stair_ascent_early_*: the early look-ahead (0.76 m, 36 probes) sees the small stairs before the '
            '0.35 m probes do', bool(ear) and k_up is not None and ear[0]['k'] < k_up,
            f'early from frame {ear[0]["k"] if ear else None} (y {ear[0]["p"].y if ear else 0:.2f}), stairUp from {k_up}')
    vz = [abs(b['c'].z - a['c'].z) / DT for a, b in zip(base, base[1:]) if a['grounded'] and b['grounded']]
    R.check('body_y_rate_up / body_y_rate_down cap the body\'s climb and descent (1.5 / 1.2 m/s)', max(vz) <= 1.5 + 1e-6,
            f'fastest {max(vz):.3f} m/s')
    lean = max(abs(r['lean']) for r in base)
    R.check('hip_lean_ascent / hip_lean_descent lean the hips on the ramps and stairs', lean > 1.0, f'up to {lean:.2f} deg')
    drops = max(r['drop'] for r in base)
    R.check('body_y_drop_* / ramp_body_y_drop_*: the body lowers on descents', drops > 0.005, f'up to {drops * 1000:.1f} mm')
    fpo = [r['fpo'] for r in base if r['fpo']]
    R.check('foot_offset_ascent / foot_offset_descent_*: the IK\'s forward plant offset engages on the small stairs',
            len(fpo) > 5, f'{len(fpo)} frames, up to {max(fpo, default=0):.3f}')
    big = [r for r in base if r['mode'] == 'stairUp' and r['probes'].get('step_like') and r['target'] is not None]
    R['large_stairs_target'] = [round(r['target'], 3) for r in big[-5:]]
    up_w = max(r['w'].get('stairsUp', 0) for r in base)
    dn_w = max(r['w'].get('stairsDown', 0) for r in base)
    R.check('the stair clips engage (stair_engage_lambda, stair_up/down_ahead_threshold)', up_w > 0.9 and dn_w > 0.9,
            f'stairsUp {up_w:.2f}, stairsDown {dn_w:.2f}')
    # the bump: its up edge alone looks like a stair for the 6 frames before its down edge enters the 0.35 m window
    # (stairsUp engages that long); once both are in, isolated_obstacle hands it back to the walk. Without the option
    # the stair clip leads over the bump
    def over_bump(rr):
        b = [r for r in rr if SEG['bump']['y0'] - 0.6 < r['p'].y < SEG['bump']['y1'] + 0.6]
        return sum(1 for r in b if r['w'].get('stairsUp', 0) > 0.5), sum(1 for r in b if r['anim'].get('isolated_obstacle_walk'))
    n_on, iso_on = over_bump(base)
    no_iso = drive(ctrl(prefer_walk_on_isolated_obstacles=False), 160, (0.0, 1.0), stop_y=SEG['bump']['y1'] + 1.0)
    n_off, iso_off = over_bump(no_iso)
    R.check('prefer_walk_on_isolated_obstacles (default on): the bump is handed back to the walk once both its edges '
            'are seen', iso_on > 0 and iso_off == 0 and n_on < n_off,
            f'stair-clip-led frames over the bump: {n_on} with the option ({iso_on} isolated), {n_off} without')
    # preferWalkOnUntreadedObstacles needs a step with no tread run, but since the tread run falls back to the stair
    # shape's (0.30 / 0.28 / 0.26 m) a step always has one: the gate cannot open, in the original as here
    unt = drive(ctrl(prefer_walk_on_isolated_obstacles=False, prefer_walk_on_untreaded_obstacles=True), 160, (0.0, 1.0),
                stop_y=SEG['bump']['y1'] + 1.0)
    steps_without_run = sum(1 for r in unt if r['probes'].get('step_like') and r['tread_run'] is None)
    R.check('prefer_walk_on_untreaded_obstacles: ported as the original, where a step always has a tread run (its '
            'shape\'s fallback), so the gate never opens', steps_without_run == 0 and
            not any(r['anim'].get('untreaded_obstacle_walk') for r in unt),
            f'step frames without a tread run: {steps_without_run}')
    # ---- the speeds and the gait sync
    for sync in ('stride', 'distance'):
        c = ctrl(attach={'gait_sync': sync, 'flat_speed': 1.2})
        rr = drive(c, 60, (0.0, 1.0))
        a = c._actions['walk']
        R.check(f'flat_speed=1.2, gait_sync={sync!r}: the walk settles at 1.2 m/s; '
                f'{"timeScale = speed / nativeWalkSpeed" if sync == "stride" else "the phase from the ground covered"}',
                abs(rr[-1]['speed'] - 1.2) < 0.05 and ((abs(a.time_scale - min(rr[-1]['speed'] / 1.5, 1.4)) < 1e-6)
                                                      if sync == 'stride' else a.time_scale == 0.0),
                f'speed {rr[-1]["speed"]:.3f}, walk timeScale {a.time_scale:.3f}')
    c = ctrl(x=-6.0, attach={'running': True, 'run_speed': 3.0})        # a clear lane: nothing ahead for 60 m
    rr = drive(c, 75, (0.0, 1.0))
    R.check('running=True, run_speed=3: the run clip leads at 3 m/s', rr[-1]['w']['run'] > 0.9 and
            abs(rr[-1]['speed'] - 3.0) < 0.1, f'run weight {rr[-1]["w"]["run"]:.2f}, speed {rr[-1]["speed"]:.2f}')
    c = ctrl(attach={'require_confirmed_stair_clips': True})
    rr = drive(c, 320, (0.0, 1.0), stop_y=SEG['small_up']['y1'] + 0.5)
    conf = [r['anim'].get('confirmed_stair_frames', 0) for r in rr]
    R.check('require_confirmed_stair_clips: the stair clips wait for a multi-edge confirmation', max(conf) > 0,
            f'confirmed frames up to {max(conf)}')
    c = ctrl(attach={'large_stair_full_toe_reach': True})
    rr = drive(c, 1000, (0.0, 1.0), stop_y=SEG['large_up']['y1'] + 0.5)
    R.check('large_stair_full_toe_reach: the toe cast reaches the whole foot on large stairs up',
            any(r['reach'] == 1.0 for r in rr), f'frames at full reach {sum(1 for r in rr if r["reach"] == 1.0)}')
    big = [r for r in rr if r['target'] is not None and r['probes'].get('step_like') and
           SEG['large_up']['y0'] - 0.5 < r['p'].y < SEG['large_up']['y1']]
    R['large_stair_targets'] = [round(r['target'], 3) for r in big[:8]]
    lock = drive(ctrl(attach={'gait_sync': 'stride'}), 500, (0.0, 1.0), stop_y=SEG['small_down']['y1'] + 0.5)
    R.check('small_stair_phase_lock (descent, stride sync): the stair clip\'s time is locked to the treads',
            any((r['anim'].get('stair_phase_lock') or {}).get('active') for r in lock),
            f'locked frames {sum(1 for r in lock if (r["anim"].get("stair_phase_lock") or {}).get("active"))}')
    fs = drive(ctrl(attach={'use_foot_support_for_root': True}), 320, (0.0, 1.0), stop_y=SEG['small_up']['y1'] + 0.5)
    R.check('use_foot_support_for_root: a stable IK foot observation sets the body\'s ground',
            any(r['body'].get('used_foot_support_for_root') for r in fs),
            f'frames {sum(1 for r in fs if r["body"].get("used_foot_support_for_root"))}')
    # ---- terrain_base's preset: the IK contact lifts, raised support, grounding grace
    tb = drive(ctrl(**CONTROLLER_PRESETS['terrain_base']), 1100, (0.0, 1.0), stop_y=SEG['flat9']['y0'] + 1.5)
    for key, label in (('ik_contact_support', 'use_ik_contact_support_lift'),
                       ('raised_support_during_descent', 'allow_raised_support_during_descent')):
        n = sum(1 for r in tb if r['body'].get(key))
        R.check(f'{label} (terrain_base preset) acts on the course', n > 0, f'{n} frames')
    R['terrain_base_modes'] = sorted(set(r['mode'] or '-' for r in tb))
    # the contact support lift reads the two FOOT probes (either side of the body): the course is level across, so it
    # acts where one foot's line crosses a block the other's does not (x = -9: 6 cm under one foot's line)
    for on in (False, True):
        c = ctrl(x=-9.0, y=-3.5, use_contact_support_lift=on, contact_support_lift_ratio=0.58)
        rr = drive(c, 60, (0.0, 1.0), stop_y=-1.0)
        cs = [r['body'].get('contact_support') for r in rr if r['body'].get('contact_support')]
        gy = max(r['ground_y'] for r in rr if r['grounded'])
        if on:
            ok = bool(cs) and abs(gy - 0.06 * 0.58) < 0.004
            R.check('use_contact_support_lift: one foot over a 6 cm block lifts the body\'s ground by ratio x the '
                    'difference (0.58 x 6 cm)', ok, f'{len(cs)} frames, ground up to {gy * 1000:.1f} mm')
        else:
            R.check('use_contact_support_lift off: the body follows the lower foot (the floor)', not cs and abs(gy) < 1e-3,
                    f'ground up to {gy * 1000:.1f} mm')
    # ---- use_ik_grounding_grace: off a platform over NOTHING (no probe hit at all) the IK's last valid contacts hold
    # the body grounded a few frames longer; over a floor the probes always hit, so it never applies there
    def void_run(grace):
        c = ctrl(x=70.0, y=-2.5, z=0.5, use_ik_grounding_grace=grace)
        rr = drive(c, 75, (0.0, 1.0))
        return next((r['k'] for r in rr if not r['grounded']), None)
    g0, g1 = void_run(False), void_run(True)
    R.check('use_ik_grounding_grace: walking off into a void, the IK\'s last contacts hold the ground longer',
            g0 is not None and (g1 is None or g1 > g0), f'airborne from frame {g0} without, {g1} with')
    # ---- y_average_window_size: the body target is the mean of the last N wanted heights
    c = ctrl(y_average_window_size=1)
    drive(c, 200, (0.0, 1.0), stop_y=SEG['small_up']['y1'])
    R.check('y_average_window_size=1: the body target is this frame\'s wanted height alone', len(c._y_avg_window) == 1,
            f'window {len(c._y_avg_window)}')
    # ---- the world's Ground interface (round one's walk_path and checks read it), add(), refresh()
    y_mid = SEG['ramp_up']['y0'] + 1.0
    n = WORLD.normal(0.0, y_mid)
    nrm, zs = WORLD.plane([-0.3, 0.3, -0.3, 0.3], [y_mid - 0.3, y_mid - 0.3, y_mid + 0.3, y_mid + 0.3])
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, n.z))))
    tilt_p = math.degrees(math.acos(max(-1.0, min(1.0, nrm.z))))
    R.check('CollisionWorld.normal / plane read the 15 deg ramp', abs(tilt - 15.0) < 0.5 and abs(tilt_p - 15.0) < 0.5,
            f'normal {tilt:.2f} deg, fitted plane {tilt_p:.2f} deg')
    extra = box('added_block', 30.0, 31.0, 0.0, 1.0, 0.0, 0.33)
    h0 = float(WORLD.h([30.5], [0.5])[0])
    WORLD.add(extra)
    h1 = float(WORLD.h([30.5], [0.5])[0])
    R.check('CollisionWorld.add puts a new mesh in the casts (refresh)', abs(h1 - 0.33) < 1e-4,
            f'height there {h0:.3f} before, {h1:.3f} after')
    # ---- set_running, an extra planner, a clip from elsewhere (vrma_library)
    c = ctrl(x=-6.0)
    c.set_running(True)
    rr = drive(c, 60, (0.0, 1.0))
    R.check('set_running(True): the run clip takes over', rr[-1]['w']['run'] > 0.9, f'run weight {rr[-1]["w"]["run"]:.2f}')
    asked = []

    def planner(ctl, fx, fy, speed):
        asked.append(round(speed, 2))
        return False
    c = ctrl(x=-6.0, enable_turning=True)
    c.maneuver_planners.append(planner)
    drive(c, 30, (0.0, 1.0))
    R.check('maneuver_planners: an extra planner is consulted while the body moves', len(asked) > 10,
            f'consulted {len(asked)} times, last at {asked[-1] if asked else None} m/s')
    from eidoblend.characters.vrma import vrma_path
    c = VRMCharacterController(ME, WORLD, start_position=(-6.0, -5.0, 0.0), log=lambda *a: None)
    c.load_standard_animations(vrma_library={'idle': vrma_path('still_breathe')})
    src = c._actions['idle'].clip.clip.path
    R.check('vrma_library: a slot played from another clip (idle <- still_breathe)', src.endswith('still_breathe.vrma'),
            f'idle plays {os.path.basename(src)}')
    # ---- the explicit moves from standing, facing the obstacle (vault, climbLedge, jump, climbLadder, climbWall)
    def explicit(name, x, y, z=0.0, frames=240, **kw):
        c = ctrl(x=x, y=y, z=z, enable_turning=True)
        ok = getattr(c, name)(**kw)
        types, peak = [], -9.0
        for k in range(frames):
            c.locomote(DT, (0.0, 0.0))
            if c.is_maneuvering:
                types.append(c._maneuver['type'])
            peak = max(peak, c.feet_world_position.z)
            if not c.is_maneuvering and k > 5 and not types[-1:] == []:
                if c._fading_maneuver_action is None:
                    break
        seen = []
        for t in types:
            if not seen or seen[-1] != t:
                seen.append(t)
        return ok, seen, c.feet_world_position.copy(), peak
    for name, x, y, kw, want, check in (
            # the vault's root rises over the 0.55 m cover (the clip's own hips curve fitted to it: 0.27 m on Aletheia)
            ('vault', 15.0, -0.7, {}, ['vault'], lambda p, pk: p.y > 0.4 and abs(p.z) < 0.05 and pk > 0.15),
            ('climb_ledge', 17.0, -0.6, {}, ['mount'], lambda p, pk: abs(p.z - 1.2) < 0.06),
            ('jump', -6.0, -2.0, {'distance': 1.4, 'height': 0.45}, ['jump'],
             lambda p, pk: abs(p.y - (-2.0 + 1.4)) < 0.1 and pk > 0.3),
            ('climb_ladder', 19.0, -0.7, {'height': 2.0}, ['ladder', 'mount'], lambda p, pk: abs(p.z - 2.0) < 0.08),
            ('climb_wall', 21.0, -0.6, {}, ['wallScramble', 'mount'], lambda p, pk: abs(p.z - 3.0) < 0.08)):
        ok, seen, p, pk = explicit(name, x, y, **kw)
        R.check(f'{name}(): {" then ".join(want)}, ending where the move leads', ok and seen == want and check(p, pk),
                f'started {ok}, played {seen}, feet at ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}), peak {pk:.2f} m')
    # ---- the maneuver planner (the engine: scan, classify, choose; moves registered as stubs)
    picks = {}

    def stub(name):
        def f(ctl, scan, ob, fx, fy, *rest):
            picks.setdefault(name, []).append((round(ob.get('rise', ob.get('width', 0.0)), 2), rest))
            return False
        return f
    for lane, x, z in (('vault 0.55', 15.0, 0.0), ('ledge 1.2', 17.0, 0.0), ('climb 2.0', 19.0, 0.0),
                       ('scramble 3.0', 21.0, 0.0), ('gap 1.1', 23.0, 0.5)):
        c = ctrl(x=x, y=-3.0, z=z, enable_turning=True)
        c.maneuvers = {'vault': stub('vault'), 'mount': stub('mount'), 'wall_scramble': stub('wall_scramble'),
                       'gap_jump': stub('gap_jump')}
        drive(c, 60, (0.0, 1.0))
    R['planner_picks'] = {k: [list(map(str, v_)) for v_ in vs[:2]] for k, vs in picks.items()}
    R.check('the planner picks vault for 0.55 m cover (vault_min_rise 0.42 .. vault_max_rise 1.15, depth <= 1.0)',
            any(abs(p[0] - 0.55) < 0.05 for p in picks.get('vault', [])), f'{picks.get("vault", [])[:2]}')
    R.check('the planner picks mount (climbLedge) for a 1.2 m block, mount (climbWallUp) for 2.0 m',
            any(p[1] == ('climbLedge',) for p in picks.get('mount', [])) and
            any(p[1] == ('climbWallUp',) for p in picks.get('mount', [])), f'{picks.get("mount", [])[:4]}')
    R.check('the planner picks the wall scramble for 3.0 m (wall_scramble_max_rise 4.5)', bool(picks.get('wall_scramble')),
            f'{picks.get("wall_scramble", [])[:2]}')
    R.check('the planner picks the gap jump for a 1.1 m gap (jump_max_gap 2.2)', bool(picks.get('gap_jump')),
            f'{picks.get("gap_jump", [])[:2]}')


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
