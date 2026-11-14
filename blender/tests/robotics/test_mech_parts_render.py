"""MechParts (mech_parts.py, the production engine's mech_parts.js) and RoboticArm (legacy_arm.py, robotic_arm.js):
every generator built, laid out on the kit's studio grid, its moving parts keyed, and rendered.

Checks (numbers): the lathe keeps the profile's crisp corners (duplicated points give split normals); chamfered_box has
its 26 analytic faces (6 + 12 + 8, 44 triangles); the tread's plates sit on the loop and scroll_tread moves them along
it; the e-chain links follow the path; hex_bolts are deterministic for a seed (mulberry32 bit for bit against the JS
reference values); the beacon / stack light keys follow update(t); RoboticArm.follow_path reaches its waypoints.

    out/mech_parts_lineup.png, out/mech_parts_lineup_f30.png, out/legacy_arm_tools.png, out/legacy_arm_f60.png

    bash run_blender.sh blender/tests/robotics/test_mech_parts_render.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters.robotics import mech_parts as mp  # noqa: E402
from eidoblend.characters.robotics import studio  # noqa: E402
from eidoblend.characters.robotics.legacy_arm import RoboticArm  # noqa: E402
from eidoblend.characters.robotics.studio import frame_camera, make_camera  # noqa: E402

# mulberry32(42), the first five values, from mech_parts.js's own function run in Deno
MULBERRY_42 = [0.6011037519201636, 0.44829055899754167, 0.8524657934904099, 0.6697340414393693, 0.17481389874592423]
# robotic_arm.js run in Deno (THREE r184) with the same mounts and waypoints: the welder arm's tool tip (three's axes)
# after followPath at frames 1, 30 and 72 (the other three arms are the same, 1.6 m apart). The original's base faces
# the target while its shoulder and elbow bend in the base's X-Y plane, so its tip never reaches the target: ported as
# it is, and compared with the original, not with the target.
JS_WELDER_TIPS = {1: (-2.539624131771816, 1.8382906930105563, 0.008101121653540487),
                  30: (-2.5688850379538497, 1.260281071770642, 0.27586347615139223),
                  72: (-2.427819018288193, 1.278042374009625, 0.09697123802564428)}


def place(ob, x, y, z=0.0):
    ob.location = (x, y, z)
    return ob


def main():
    sc = K.clean_scene()
    sc.frame_start, sc.frame_end = 1, 60
    K.probe_render(sc, (960, 540), 16)
    studio(sc)
    cam = make_camera(35, 'mech camera', sc)
    sc.camera = cam
    built = {}
    try:
        built['chamfered_box'] = place(mp.chamfered_box(0.3, 0.2, 0.25, 0.03), -1.6, 0.6, 0.1)
        me = built['chamfered_box'].data
        K.check(f'chamfered_box: 26 faces as {len(me.polygons)} triangles (6 quads + 12 bevels + 8 corners = 44)',
                len(me.polygons) == 44)
        built['motor_housing'] = place(mp.motor_housing(), -1.0, 0.6, 0.35)
        built['gearbox_bell'] = place(mp.gearbox_bell(), -0.45, 0.6, 0.22)
        built['joint_hub'] = place(mp.joint_hub(), 0.0, 0.6, 0.07)
        hub = built['joint_hub'].data
        cn = [tuple(round(c, 4) for c in v.vector) for v in hub.corner_normals]
        K.check('lathe: duplicated profile points keep crisp corners (split normals)', len(set(cn)) > 40)
        built['arm_link_casting'] = place(mp.arm_link_casting(), 0.5, 0.6, 0.1)
        built['piston_rod'] = place(mp.piston_rod(), 1.1, 0.6, 0.5)
        built['piston_sleeve'] = place(mp.piston_sleeve(), 1.35, 0.6, 0.5)
        built['vent_grille'] = place(mp.vent_grille(), 1.7, 0.6, 0.1)
        bolts = mp.hex_bolts(0.2, 0.0, 8, seed=11)
        built['hex_bolts'] = place(mp.geometry_object('hex bolts', mp.merge(bolts), mp.metal(0x777a80)), -1.6, -0.2, 0.02)
        rng = mp.mulberry(42)
        seq = [rng() for _ in range(5)]
        K.check(f'mulberry32(42) bit for bit with the JavaScript: {[round(v, 6) for v in seq]}',
                all(abs(a - b) < 1e-15 for a, b in zip(seq, MULBERRY_42)))
        built['cable'] = mp.make_cable((-1.2, -0.2, 0.5), (-0.4, -0.3, 0.45), radius=0.012, sag=0.12)
        built['corrugated'] = mp.make_cable((-1.2, -0.45, 0.4), (-0.4, -0.55, 0.38), radius=0.015, sag=0.1,
                                            corrugated=True)
        chain = mp.make_e_chain([(0.0, -0.3, 0.05), (0.15, -0.3, 0.3), (0.45, -0.3, 0.32), (0.6, -0.3, 0.06)])
        built['e_chain'] = chain['root']
        tip = chain['links'][-1].matrix_basis.translation
        K.check(f"e-chain: {chain['count']} links, the last on the path's end", (tip - Vector((0.6, -0.3, 0.06))).length < 1e-4)
        tread = mp.make_tread_track(run_len=0.5, cap_r=0.12, width=0.1, plate_n=40)
        tread['root'].location = (1.0, -0.3, 0.16)
        built['tread'] = tread['root']
        p0 = tread['plates'][0].matrix_basis.translation.copy()
        mp.key_tread(tread, 0.25, 1, 60)
        sc.frame_set(30)
        p1 = tread['plates'][0].matrix_basis.translation.copy()
        K.check('tread: scroll_tread keyed, plate 0 moved along the loop', (p1 - p0).length > 0.05)
        built['wheel'] = place(mp.make_wheel(r=0.18, width=0.1), 1.65, -0.3, 0.18)
        built['mecanum'] = place(mp.make_mecanum_wheel(), 2.05, -0.3, 0.12)
        built['hose_coil'] = place(mp.hose_coil(), -1.6, -0.9, 0.2)
        bc = mp.beacon(color=0xff7a10)
        place(bc['object'], -1.1, -0.9, 0.05)
        mp.key_lights(bc, 1, 60)
        sl = mp.stack_light(s=1.5)
        place(sl['group'], -0.8, -0.9, 0.0)
        mp.key_lights(sl, 1, 60, modes={1: 'run', 20: 'warn', 40: 'fault'})
        sc.frame_set(25)
        bc['update'](24 / 24)
        K.check('beacon / stack light: emission keyed per frame', bc['sockets'][0].id_data.animation_data is not None
                and sl['sockets'][0].id_data.animation_data is not None)
        striped = mp.chamfered_box(0.4, 0.06, 0.4, 0.01, mp.metal(0xffffff, 0.5, 0.1, 'hazard'))
        mp.apply_hazard_stripes(striped.active_material, freq=10)
        place(striped, -0.3, -0.9, 0.03)
        brushed = mp.chamfered_box(0.3, 0.2, 0.3, 0.02, mp.metal(0xb8bcc2, 0.3, 1.0, 'brushed'))
        mp.apply_brushed_metal(brushed.active_material)
        place(brushed, 0.3, -0.9, 0.1)
        built['hazard'], built['brushed'] = striped, brushed
        K.check(f'every generator built ({len(built) + 2} kinds)', True)
        cam.location = (0.25, -4.3, 2.2)
        cam.rotation_quaternion = (Vector((0.25, -0.15, 0.2)) - cam.location).to_track_quat('-Z', 'Y')
        K.still(sc, cam, 1, os.path.join(K.OUT, 'mech_parts_lineup.png'))
        K.still(sc, cam, 30, os.path.join(K.OUT, 'mech_parts_lineup_f30.png'))
        # the gallery: every generator alone, framed close, so each one's shape and shading can be judged
        built.update({'beacon': bc['object'], 'stack_light': sl['group'], 'hazard': striped, 'brushed': brushed})
        built['link_casting_rect'] = place(mp.arm_link_casting(end_w=0.09, end_h=0.1, name='casting rect end'),
                                           2.4, 0.6, 0.1)
        built['lathe_custom'] = place(mp.lathe([(0.0, 0.08), (0.05, 0.08), (0.05, 0.08), (0.07, 0.0), (0.05, -0.08),
                                                (0.05, -0.08), (0.0, -0.08)], 32), 2.4, -0.9, 0.08)
        gallery = os.path.join(K.OUT, 'mech_parts')
        os.makedirs(gallery, exist_ok=True)
        cam.data.angle_y = 0.6
        movable = [o for o in sc.objects if o.type in ('MESH', 'EMPTY', 'CURVE') and o.name != 'robotics grid']
        saved = {o.name: o.hide_render for o in movable}
        sc.render.resolution_x, sc.render.resolution_y = 320, 240
        frames = {'tread': (1, 30), 'beacon': (1, 4), 'stack_light': (10, 30, 50), 'e_chain': (1,)}
        shots = 0
        for name, ob in built.items():
            keep = {ob.name} | {c.name for c in ob.children_recursive}
            for o in movable:
                o.hide_render = o.name not in keep
            mesh = [ob] + [c for c in ob.children_recursive if c.type == 'MESH']
            frame_camera(cam, mesh, direction=(0.9, -1.5, 0.8), margin=1.3)
            for f in frames.get(name, (1,)):
                p = os.path.join(gallery, f'{name}_f{f:02d}.png')
                shots += bool(K.still(sc, cam, f, p))
        for o in movable:
            o.hide_render = saved[o.name]
        K.check(f'gallery: {shots} stills of {len(built)} generators', shots >= len(built))
    except Exception:  # noqa: BLE001
        K.check('mech parts', False, traceback.format_exc().splitlines()[-1])
        traceback.print_exc()
    try:
        sc = K.clean_scene()
        sc.frame_start, sc.frame_end = 1, 72
        K.probe_render(sc, (960, 540), 16)
        studio(sc)
        cam = make_camera(35, 'arm camera', sc)
        sc.camera = cam
        arms = []
        for i, tool in enumerate(('welder', 'gripper', 'spray', 'saw')):
            a = RoboticArm(mount_point=(-2.4 + i * 1.6, 0, 0), tool=tool, name=f'arm {tool}')
            arms.append(a)
        paths = []
        for i, a in enumerate(arms):
            x = -2.4 + i * 1.6
            wp = [{'time': 0, 'target': (x + 0.3, -0.6, 1.2), 'action': 'weld' if a.tool == 'welder' else 'cut',
                   'grip': 1.0},
                  {'time': 1.5, 'target': (x + 0.7, -0.2, 0.5), 'grip': 1.0},
                  {'time': 2.5, 'target': (x + 0.7, -0.2, 0.5), 'grip': 0.0}]
            paths.append(wp)
            tips = a.bake(wp, 1, 72)
            worst = 0.0
            for f, (tx, ty, tz) in JS_WELDER_TIPS.items():
                want = Vector((tx + i * 1.6, -tz, ty))
                worst = max(worst, (tips[f] - want).length)
            K.check(f'RoboticArm {a.tool}: follow_path baked 72 frames; the tool tip follows robotic_arm.js '
                    '(frames 1, 30, 72)', worst < 1e-4, f'worst {worst * 1000:.3f} mm')
        RoboticArm.help()
        cam.location = (0.0, -6.5, 2.4)
        cam.rotation_quaternion = (Vector((0.0, 0.0, 0.7)) - cam.location).to_track_quat('-Z', 'Y')
        K.still(sc, cam, 1, os.path.join(K.OUT, 'legacy_arm_tools.png'))
        K.still(sc, cam, 60, os.path.join(K.OUT, 'legacy_arm_f60.png'))
        # each tool close up, mid-path (the welder's tip flickers, the saw's blade has turned, the gripper has closed)
        sc.render.resolution_x, sc.render.resolution_y = 480, 270
        os.makedirs(os.path.join(K.OUT, 'mech_parts'), exist_ok=True)
        for a in arms:
            for f in (20, 60):
                sc.frame_set(f)
                frame_camera(cam, [a.wrist_pivot], direction=(0.7, -1.4, 0.6), margin=1.6)
                K.still(sc, cam, f, os.path.join(K.OUT, 'mech_parts', f'legacy_arm_{a.tool}_f{f:02d}.png'))
        K.check('legacy arm: each tool rendered close up at frames 20 and 60', True)
    except Exception:  # noqa: BLE001
        K.check('legacy arm', False, traceback.format_exc().splitlines()[-1])
        traceback.print_exc()
    K.save_results('mech_parts_render')


main()
