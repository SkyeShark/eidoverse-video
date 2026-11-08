"""The robotics kit's first probe: the A650 arm with the parallel gripper attached at its TC70 flange, recoloured, the arm
posed (robotics.md's own example) and the jaws opened, on the studio floor. Checks the mount: the two mating frames meet
(their origins' distance, mm) with opposed normals (deg off 180) and matching tangents after the twist; the joint states;
the recolour (materials rebuilt); renders two stills:

    out/robotics_arm_rest.png      every joint at rest, the jaws closed
    out/robotics_arm_posed.png     joints [0, 0.5, 0.4, 0, -0.9, 0], jaw gap 0.03 m, primary #d9e0df, accent #398b91
    out/robotics_arm.json

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/characters/test_robotics_arm.py [--no-render]
"""

import json
import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters.robotics import make_robot  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()


def log(*a):
    print('[robotics_arm]', *a, flush=True)


def mount_report(a, b):
    """the two port frames in the world: origin distance (mm), normals' angle (deg, 180 = opposed)"""
    bpy.context.view_layer.update()
    A = a['owner'].matrix_world @ a['matrix']
    B = b['owner'].matrix_world @ b['matrix']
    za, zb = A.to_3x3().col[2].normalized(), B.to_3x3().col[2].normalized()
    xa, xb = A.to_3x3().col[0].normalized(), B.to_3x3().col[0].normalized()
    return {'origin_mm': round(1000 * (A.translation - B.translation).length, 4),
            'normals_deg': round(math.degrees(math.acos(max(-1, min(1, za.dot(zb))))), 4),
            'tangents_deg': round(math.degrees(math.acos(max(-1, min(1, xa.dot(xb))))), 4)}


try:
    sc = S.clean_scene(24)
    S.probe_render(sc)
    S.studio_world(sc, 0.8, background=0x121214)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0, angle_deg=3.0)
    S.floor_disc()
    arm = make_robot('arm', color='#d9e0df', accent='#398b91')
    claw = make_robot('gripper')
    R['arm'] = arm.stats()
    R['gripper'] = claw.stats()
    R['recoloured_materials'] = [arm.recoloured, claw.recoloured]
    arm.attach(claw, port='a650_j6/output', child_port='parallel_gripper/input')
    R['mount_rest'] = mount_report(arm.port('a650_j6/output'), claw.port('parallel_gripper/input'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'robotics_arm.blend'), compress=True)
    cam = S.camera('cam', 50.0)
    S.aim(cam, (1.25, -1.75, 0.95), (0.18, 0.0, 0.42))
    rs = {}
    if RENDER:
        p = os.path.join(S.OUT, 'robotics_arm_rest.png')
        rs[os.path.basename(p)] = S.still(sc, cam, 1, p)
    arm.joints([0, 0.5, 0.4, 0, -0.9, 0])
    claw.jaw_gap(0.03)
    R['mount_posed'] = mount_report(arm.port('a650_j6/output'), claw.port('parallel_gripper/input'))
    R['state'] = {'arm': arm.state, 'gripper': claw.state}
    tcp = claw.roots['parallel_gripper'].matrix_world @ Vector(claw.specs['parallel_gripper'].get('tcp', (0, 0, 0)))
    R['gripper_tcp_world'] = [round(c, 4) for c in tcp]
    log(R['mount_rest'], R['mount_posed'], R['recoloured_materials'], R['state'])
    if RENDER:
        p = os.path.join(S.OUT, 'robotics_arm_posed.png')
        rs[os.path.basename(p)] = S.still(sc, cam, 1, p)
    R['renders'] = rs
    R['ok'] = True
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
with open(os.path.join(S.OUT, 'robotics_arm.json'), 'w', encoding='utf-8') as f:
    json.dump(R, f, indent=1, default=str)
log('done', R['ok'], R['seconds'], 's')
