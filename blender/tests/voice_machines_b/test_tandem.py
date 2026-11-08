"""The 1896 tandem (props/tandem.py): build, update against tandem.js (distance, Simpson integral, wheel and crank
angles, the chains' walk and phase), the keyed parts, the spoke smear, the teapot stoker, the VRM rider rig, and probe
renders at true scale.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_tandem.py             # checks
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render             # + stills
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def speed_fn(t):
    return 2.2 * min(1.0, t / 3) + 0.4 * math.sin(t * 1.3)


def _max_angle_deg(a, b):
    """the largest rotation between two bakes' keyed quaternions, over every bone and frame they share"""
    worst = 0.0
    for bone, la in a.items():
        lb = {f: q for f, q, _s in b.get(bone, ())}
        for f, q, _s in la:
            if f in lb:
                worst = max(worst, math.degrees(q.rotation_difference(lb[f]).angle))
    return worst


def options_checks(sc, bike, me, TD):
    """every pose_rider option (tandem.js poseRider's opts, snake_case) moves what it should: each probe poses one
    frame unkeyed (key=False) against the default pose at the same crank angle"""
    th, t = 0.7, 1.0
    sc.frame_set(20)

    def pose(**o):
        rep = TD.pose_rider(me, th, bike=bike, t=t, key=False, **o)
        bpy.context.view_layer.update()
        return rep
    base = pose()
    S_ = 0.87
    d = pose(hip_above_seat=0.05 + (bike.layout['hipTarget'][1] - bike.layout['frontSit'][1]))
    S.check('tandem rider: hip_above_seat raises the hips', abs((d['hips_pos'].y - base['hips_pos'].y) * S_ - 0.05) < 1e-6)
    d = pose(hip_forward=0.04 + (bike.layout['hipTarget'][0] - bike.layout['frontSit'][0]))
    S.check('tandem rider: hip_forward moves the hips forward', abs((d['hips_pos'].z - base['hips_pos'].z) * S_ - 0.04) < 1e-6)
    for opt, val, part in (('sole', 0.04, 'ball'), ('foot_forward', 0.03, 'ball')):
        d = pose(**{opt: val})
        moved = (d['legs']['right'][part] - base['legs']['right'][part]).length * S_
        want = abs(val - (0.0214 if opt == 'sole' else 0.0))
        S.check(f'tandem rider: {opt} moves the ball of the foot {want * 1000:.0f} mm', abs(moved - want) < 1e-5, f'{moved * 1000:.2f} mm')
    d = pose(ankling=0.0)
    S.check('tandem rider: ankling 0 keeps the feet level (pitch 0)', d['legs']['right']['phi'] == 0.0
            and abs(base['legs']['right']['phi'] - TD.ankle_pitch(th)) < 1e-12)
    d = pose(toe_out=0.3)
    S.check('tandem rider: toe_out turns the feet (the ankle moves)',
            (d['legs']['right']['ankle'] - base['legs']['right']['ankle']).length * S_ > 0.005)
    for opt, val in (('grip_along', 0.02), ('grip_palm', 0.05), ('wrist_drop', 0.6)):
        d = pose(**{opt: val})
        moved = (d['arms']['left']['wrist'] - base['arms']['left']['wrist']).length * S_
        S.check(f'tandem rider: {opt} moves the wrist on the grip', moved > 0.004, f'{moved * 1000:.1f} mm')
    for opt, val, at_least in (('lean', 0.7, 0.01), ('sway', 6.0, 0.005)):   # the torso turns about the hip joints
        d = pose(**{opt: val})                                              # (which stay put); the spine counters sway
        moved = (d['arms']['left']['shoulder'] - base['arms']['left']['shoulder']).length * S_
        S.check(f'tandem rider: {opt} moves the torso (the shoulder)', moved > at_least, f'{moved * 1000:.1f} mm')

    def rot(name):
        return me.arm.pose.bones[me.humanoid.get(name, name)].rotation_quaternion.copy()
    pose()
    q_head, q_finger, q_tail = rot('head'), rot('leftIndexProximal'), rot('tail_3')
    for opt, val in (('head_pitch', 0.4), ('head_yaw', 0.5)):
        pose(**{opt: val})
        S.check(f'tandem rider: {opt} turns the head', math.degrees(q_head.rotation_difference(rot('head')).angle) > 10)
    pose(finger_curl=0.0)
    S.check('tandem rider: finger_curl 0 opens the hands (the curl is 1.05 rad at 1)',
            rot('leftIndexProximal').angle < 1e-5 and abs(q_finger.angle - 1.05) < 1e-4, f'{q_finger.angle:.4f} rad')
    pose(tail_lift=0.3)
    S.check('tandem rider: tail_lift lowers the curled tail', math.degrees(q_tail.rotation_difference(rot('tail_3')).angle) > 5)
    # the rig's own options (read on the first call, as rigFor did): a fresh rig with scale 0.9 and the springing tail
    del TD._RIGS[id(me)]
    pose(scale=0.9, tail='spring', settle=False)
    R = TD._RIGS[id(me)]
    S.check("tandem rider: a rig with scale 0.9 and tail='spring' (no curl; settle off)",
            abs(me.arm.scale.x - 0.9) < 1e-6 and R['tail'] == [] and R['settle'] is False, f'{me.arm.scale.x:.6f}')
    rep = TD.bake_rider_springs(me, 20, 23)
    S.check("tandem rider: with tail='spring' the tail stays in the spring solver",
            not rep['dropped'] and any('tail' in b.lower() for b in rep['series']) and rep['settle_steps'] == 0,
            f"{rep['joints']} joints")
    del TD._RIGS[id(me)]
    pose()                                                 # the default rig back: scale 0.87, the curled tail, settle
    S.check('tandem rider: the default rig is back (scale 0.87)', abs(me.arm.scale.x - 0.87) < 1e-6, f'{me.arm.scale.x:.6f}')


def springs_checks(sc, bike, me, TD):
    """tandem.js's springs under a rider: center = the VRM root, the curled tail out of the solver, the settle pre-roll.
    Leaves the engine's own bake (rider frame, settled) over frames 1..72 for the renders."""
    from eidoblend.characters import springs as SP
    F = (1, 48)
    rep = TD.bake_rider_springs(me, *F)
    S.check('tandem: the rider springs bake (the mane and the tie, keyed on <name>|springs, no NaN)',
            rep['joints'] > 0 and rep['nan'] == 0 and rep['keys'] > 0 and SP.spring_track(me) is not None,
            f"{rep['joints']} joints, {rep['springs']} springs, {rep['keys']} keys, swing {rep['swing_deg']}")
    S.check("tandem: the curled tail is out of the spring solver (pose_rider's tail='curl')",
            rep['dropped'] and not any('tail' in b.lower() for b in rep['series']), f"dropped {rep['dropped']}")
    moving = rep['series']
    world = TD.bake_rider_springs(me, *F, center='vrm')['series']
    loc = [fc for fc in S.fcurves_of(bike.group) if fc.data_path == 'location']
    for fc in loc:
        fc.mute = True
    bike.group.location = (0.0, 0.0, 0.0)
    still = TD.bake_rider_springs(me, *F)['series']
    d_still = _max_angle_deg(moving, still)
    d_world = _max_angle_deg(moving, world)
    S.check("tandem: the springs ride in the rider's frame: the bike's travel changes nothing (center = vrm.scene)",
            d_still < 0.05 and d_world > 1.0, f"travel vs standing {d_still:.4f} deg; the file's own centers would "
            f'differ by {d_world:.1f} deg')
    for fc in loc:
        fc.mute = False
    cold = TD.bake_rider_springs(me, *F, settle=False)['series']
    final = TD.bake_rider_springs(me, 1, 72)

    def first_motion(series):
        """the largest turn of any spring joint between consecutive keys over the first four frames"""
        worst = 0.0
        for lst in series.values():
            for (_f0, q0, _s0), (_f1, q1, _s1) in zip(lst[:4], lst[1:5]):
                worst = max(worst, math.degrees(q0.rotation_difference(q1).angle))
        return worst
    m_warm, m_cold = first_motion(final['series']), first_motion(cold)
    S.check('tandem: settle pre-rolls the springs on the first pose (120 steps of 1/60 s): no swing in from rest',
            final['settle_steps'] == 120 and m_warm < m_cold, f'first frames turn {m_warm:.2f} deg settled, {m_cold:.2f} cold')


def run(render=False, rider=True):
    sc = S.fresh_scene(frames=(1, 72))
    from eidoblend.props import tandem as TD
    bike = TD.build()
    P = bike.parts
    S.check('tandem: parts', all(P[k] is not None for k in TD.PART_NODES) and P['timing_chain'] and P['drive_chain'])
    S.check('tandem: gear 9 / 24 from the extras', abs(bike.gear - 0.375) < 1e-12)
    S.check('tandem: spoke smear on (no motion blur in this scene)', bike.group['spoke_smear'] == 1.0)

    J = json.loads((S.OUT / 'parity_js.json').read_text())
    worst = max(abs(TD.integrate(speed_fn, t) - v) for t, v in J['tandem_integrate'])
    S.check('tandem: Simpson integral of the speed equals tandem.js', worst < 1e-12, f'{worst:.1e}')
    worst = 0.0
    for t, st, dist, wa, ca in J['tandem_update']:
        s = bike.update(t, {k: v for k, v in st.items()}, key=False)
        worst = max(worst, abs(s['distance'] - dist), abs(s['wheel_angle'] - wa), abs(s['crank_angle'] - ca))
    S.check('tandem: update distance / wheel / crank angles equal tandem.js', worst < 1e-12, f'{worst:.1e}')
    worst = 0.0
    for key, rows in J['tandem_belts'].items():
        belt = bike.chains[key]
        for crank, i, ph, s0, x, y in rows:
            worst = max(worst, abs(belt.phase(crank) - ph))
            px, py = belt.point(s0)
            worst = max(worst, abs(px - x), abs(py - y))
    S.check('tandem: belt walk and phase equal tandem.js (CPU)', worst < 1e-12, f'{worst:.1e}')
    worst = max(max(abs(TD.ankle_pitch(th) - a), abs(TD.ankle_pitch(th, 0.5) - b)) for th, a, b in J['ankle'])
    S.check('tandem: anklePitch equals tandem.js', worst < 1e-15, f'{worst:.1e}')

    # ride: speed as a function of t, keyed every frame
    for f in range(1, 73):
        t = bike.time_at(f)
        st = bike.update(t, {'speed': speed_fn, 'steer': 0.05 * math.sin(t)})
        bike.group.location.x = st['distance']
        bike.keyer.key(bike.group, 'location', frame=f)
    f = 50
    t50 = bike.time_at(f)
    sc.frame_set(f)
    d = TD.integrate(speed_fn, t50)
    S.check('tandem: the rear wheel angle is keyed', abs(P['rear_wheel'].rotation_euler[1] - d / bike.layout['R']) < 1e-4)
    S.check('tandem: the root travels the distance', abs(bike.group.location.x - d) < 1e-4, f'{d:.3f} m')
    sw = max(-0.7, min(0.7, speed_fn(t50) / bike.layout['R'] * 0.5 / 24))
    S.check('tandem: the spoke sweep follows the speed and shutter', abs(bike.group['sweep'] - sw) < 1e-6, f'{sw:.4f} rad')
    # the GN chain against the CPU walk: every link's position in the bike frame
    dg = bpy.context.evaluated_depsgraph_get()
    for key in ('timing', 'drive'):
        ob = P[f'{key}_chain']
        belt = bike.chains[key]
        inv = ob.matrix_world.inverted()
        got = [inv @ inst.matrix_world.translation for inst in dg.object_instances
               if inst.is_instance and inst.parent and inst.parent.original == ob]
        crank = d / bike.layout['R'] * bike.gear                 # the crank at frame 50 (keyed)
        ph = belt.phase(crank)
        want = [belt.point(((i * belt.pp + ph) % belt.L + belt.L) % belt.L) for i in range(int(belt.N))]
        err = 0.0
        for g in got:
            gx, gy = g.x, g.z
            err = max(err, min(math.hypot(gx - wx, gy - wy) for wx, wy in want))
        S.check(f'tandem: the {key} chain has its {int(belt.N)} links on the belt (GN = CPU walk)',
                len(got) == int(belt.N) and err < 1e-4, f'{len(got)} links, max {err * 1000:.3f} mm')
    # state.shutter and state.steer (unkeyed probe; the frame's keys come back on the next frame_set)
    R_ = bike.layout['R']
    bike.update(1.0, {'speed': 2.0, 'shutter': 1 / 48, 'steer': 0.2}, key=False)
    S.check('tandem: shutter sets the spoke sweep (speed / R x shutter, clamped 0.7)',
            abs(bike.group['sweep'] - 2.0 / R_ / 48) < 1e-9, f"{bike.group['sweep']:.5f} rad")
    q = P['steering'].rotation_quaternion
    ax = Vector((bike.layout['axis'][0], bike.layout['axis'][1], 0.0)).normalized()
    S.check('tandem: steer turns the fork about the head-tube axis',
            abs(q.angle - 0.2) < 1e-6 and (q.axis - TD.v3(ax.x, ax.y, ax.z)).length < 1e-5, f'{q.angle:.4f} rad')
    sc.frame_set(f)
    lows = []                       # the lowest real vertex of each part (a rotated bound box overstates a wheel)
    for o in [bike.group] + list(bike.group.children_recursive):
        if o.type == 'MESH' and o.visible_get() and len(o.data.vertices):
            ev = o.evaluated_get(dg)
            mw = ev.matrix_world
            lows.append((min((mw @ v.co).z for v in ev.data.vertices), o.name))
    lows.sort()
    S.check('tandem: wheels rest on the ground (tyres squashed 2.4 mm)', abs(lows[0][0]) < 0.005,
            f'lowest {lows[0][0] * 1000:.1f} mm ({lows[0][1]}), next {lows[1][0] * 1000:.1f} mm ({lows[1][1]})')

    # the teapot stoker
    body = TD.teapot_geometry(1, 20, True, False, True, True, False)
    lid = TD.teapot_geometry(1, 20, False, True, False, True, False)
    S.check('tandem: teapot triangles as three (body 19120, lid 6320 at 20 segments)',
            len(body.tris) == 19120 and len(lid.tris) == 6320, f'{len(body.tris)}, {len(lid.tris)}')
    pot = TD.build_teapot_rider().mount(bike)
    for f in range(1, 73):
        pot.update(bike.time_at(f), TD.integrate(speed_fn, bike.time_at(f)) / bike.layout['R'] * bike.gear, frame=f)
    zb = [v.co.z for v in pot.parts['body'].data.vertices]
    zl = [v.co.z + pot.parts['lid_pivot'].location.z for v in pot.parts['lid'].data.vertices]
    S.check('tandem: teapot 0.35 m tall (Newell proportions, its own frame)',
            abs(max(zb + zl) - min(zb + zl) - 0.35) < 0.002 and abs(min(zb)) < 1e-6, f'{max(zb + zl) - min(zb + zl):.4f} m')
    seat = P['rear_seat'].matrix_world.translation
    lo, hi = S.bounds([pot.parts['body']])
    S.check('tandem: the teapot sits on the rear saddle', abs(lo.z - seat.z) < 0.03, f'base {lo.z:.3f} m, saddle {seat.z:.3f} m')
    S.dispose_leaves_nothing('tandem teapot', lambda: TD.build_teapot_rider(height=0.2, segments=8, color=0xb03a2e,
                                                                           pitch=0.0, roll=0.0, name='teapot_2'))

    # opts.glb as bytes (the engine's Uint8Array, e.g. ASSETS.tandem): built, its maps packed, nothing left on disk
    def check_bytes_build(b2):
        maps = {n.image for o in b2.group.children_recursive if o.type == 'MESH' for s in o.material_slots if s.material
                and s.material.node_tree for n in s.material.node_tree.nodes if getattr(n, 'image', None)}
        S.check('tandem: build(glb=<bytes>) builds the same bike, its maps packed in the blend',
                all(b2.parts[k] is not None for k in TD.PART_NODES) and maps and all(m.packed_file for m in maps)
                and b2.group.get('eido_src_asset') == 'bytes', f'{len(maps)} maps')
        S.check('tandem: build(spoke_smear=False) switches the smear off', b2.group['spoke_smear'] == 0.0)
        b2.dispose()
    S.dispose_leaves_nothing('tandem', lambda: TD.build(glb=Path(TD.TANDEM_GLB).read_bytes(), name='tandem_bytes',
                                                        spoke_smear=False), check_bytes_build)
    sc.render.use_motion_blur = True                       # the harness default: EEVEE blurs the keyed wheels itself
    b3 = TD.build(name='tandem_mb')
    S.check('tandem: with EEVEE motion blur on, build() leaves the smear off (no double blur)', b3.group['spoke_smear'] == 0.0)
    b3.dispose()
    sc.render.use_motion_blur = False

    me = None
    if rider:
        from eidoblend.characters import load_vrm
        me = load_vrm('claude_suit')
        worst_leg = worst_arm = 0.0
        for f in range(1, 73, 1):
            sc.frame_set(f)
            t = bike.time_at(f)
            rep = TD.pose_rider(me, bike.state['crank_angle'] if False else
                                TD.integrate(speed_fn, t) / bike.layout['R'] * bike.gear, bike=bike, t=t, frame=f)
            worst_leg = max(worst_leg, max(abs(rep['legs'][s]['reach_err']) for s in rep['legs']))
            worst_arm = max(worst_arm, max(abs(rep['arms'][s]['reach_err']) for s in rep['arms']))
        S.check('tandem: the rider reaches the pedals (two-bone IK, every frame)', worst_leg < 0.005, f'{worst_leg * 1000:.1f} mm')
        S.check('tandem: the rider reaches the grips', worst_arm < 0.03, f'{worst_arm * 1000:.1f} mm')
        sc.frame_set(30)
        bpy.context.view_layer.update()
        foot = me.arm.matrix_world @ me.arm.pose.bones[me.humanoid['rightToes']].head
        ped = P['front_pedal_r'].matrix_world.translation
        want = (bike.layout['pedalTop'] + 0.0214)              # pedal top + the suit's sole under the toe joint
        S.check('tandem: the keyed pose puts the right toe joint a sole above its pedal', abs((foot - ped).length - want) < 0.008,
                f'{(foot - ped).length * 1000:.1f} mm (want {want * 1000:.1f})')
        options_checks(sc, bike, me, TD)
        springs_checks(sc, bike, me, TD)

    if render:
        S.floor(sc, size=30, color=(0.30, 0.29, 0.27))
        S.studio(sc, (2.0, 0.0, 0.7), dist=4.0, key=200, scale=1.4)     # the floor mid-grey: the enamel reads oxblood
        cam = S.camera(sc, (1.9, -4.6, 1.1), (1.2, 0.0, 0.75), lens=35)
        cam.parent = None
        sc.frame_set(50)
        bx = bike.group.location.x
        S.look_from(cam, (bx + 0.1, -4.4, 1.05), (bx + 0.05, 0.0, 0.72), lens=32)
        S.render(S.OUT / 'tandem_side_riders_f050.png', frame=50)
        S.look_from(cam, (bx - 0.25, -1.35, 0.55), (bx - 0.1, 0.0, 0.32), lens=35)
        S.render(S.OUT / 'tandem_chain_cranks_f050.png', frame=50)
        S.look_from(cam, (bx - 0.2, -1.1, 1.25), (bx - 0.55, 0.0, 0.95), lens=40)
        S.render(S.OUT / 'tandem_teapot_stoker_f050.png', frame=50)
        if me is not None:
            S.look_from(cam, (bx + 1.7, -1.6, 1.35), (bx + 0.3, 0.0, 1.0), lens=40)
            S.render(S.OUT / 'tandem_rider_three_quarter_f050.png', frame=50)
            S.look_from(cam, (bx + 0.75, -0.75, 1.05), (bx + 0.6, 0.05, 0.92), lens=45)
            S.render(S.OUT / 'tandem_rider_hands_grips_f050.png', frame=50)
    return S.summary('tandem')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv, rider='--no-rider' not in sys.argv) else 0)
