"""eidoverse/robotics/tests/attachment_frames_test.mjs, ported (no render).

The gripper must seat on the PHYSICAL flanges, measured from the exported triangles independently of the port data:
for the A650 and the S500, the arm moved, turned and scaled (1.7), the gripper attached at the flange, then for three
poses each (and the jaws at both ends of their travel) the two mating faces' centres, normals and the gripper's axis are
compared with the declared port frames. Also: an intentional twist turns about the flange axis without tilting or
moving it; a missing, zero, NaN or parallel authored axis is refused at load (and the refused load leaves nothing in
the file); an invalid attachment (NaN twist, a singular mount matrix) cannot reparent the child.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_attachment_frames.py
"""

import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

from eidoblend.characters.robotics import catalog, make_robot  # noqa: E402

EPS = 2e-5      # the WebGPU test's 2e-6, widened for Blender's float32 transforms on a robot scaled 1.7


def physical_face(robot, part, owner, axis, sign):
    """the outermost planar face of `part` whose normal is +-axis (owner's local Blender axes), from the triangles:
    its bounding-box centre and its mean normal, in the world"""
    bpy.context.view_layer.update()
    inv = owner.matrix_world.inverted()
    faces, extreme = [], -math.inf
    for mesh in robot.part(part):
        m = inv @ mesh.matrix_world
        me = mesh.data
        own = robot.part_faces(mesh)
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        for i, poly in enumerate(me.polygons):
            if own[i] != part:
                continue
            pts = [m @ Vector(co[v]) for v in poly.vertices]
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if n.length_squared < 1e-20:
                continue
            n.normalize()
            if n[axis] * sign < 0.99999:
                continue
            depth = pts[0][axis] * sign
            extreme = max(extreme, depth)
            faces.append((pts, n, depth))
    if not math.isfinite(extreme):
        raise AssertionError('Missing physical face: ' + part)
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    nsum = Vector()
    for pts, n, depth in faces:
        if abs(depth - extreme) < 1e-7:
            for p in pts:
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
            nsum += n
    centre = owner.matrix_world @ ((lo + hi) / 2)
    normal = (owner.matrix_world.to_3x3() @ nsum.normalized()).normalized()
    return centre, normal


def check_physical_ports(arm, gripper, spec, tag):
    a, b = arm.port(spec['port']), gripper.port('parallel_gripper/input')
    face_a = physical_face(arm, spec['part'], a['owner'], spec['axis'], spec['sign'])
    face_b = physical_face(gripper, 'TC robot side', b['owner'], 2, 1)     # three's local +Y is Blender's +Z
    worst = 0.0
    ok = True
    for port, face in ((a, face_a), (b, face_b)):
        m = port['owner'].matrix_world @ port['matrix']
        d = (m.translation - face[0]).length
        z = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
        worst = max(worst, d, abs(z.dot(face[1]) - 1))
        ok &= d < EPS and abs(z.dot(face[1]) - 1) < EPS
    touch = (face_a[0] - face_b[0]).length
    oppose = face_a[1].dot(face_b[1])
    along = (b['owner'].matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized().dot(face_a[1])
    ok &= touch < EPS and abs(oppose + 1) < EPS and abs(along - 1) < EPS
    K.check(f'{tag}: port centres on the geometry, directions match, flanges touch and oppose, gripper on the axis',
            ok, f'worst port {worst:.1e}, touch {touch * 1000:.4f} mm, normals {oppose:.7f}, axis {along:.7f}')


SPECS = (
    {'id': 'arm', 'port': 'a650_j6/output', 'part': 'A650 TC70 output flange common flange', 'axis': 0, 'sign': 1,
     'method': 'joints', 'poses': [[0, 0, 0, 0, 0, 0], [.2, .4, -.6, .25, .6, -.2], [-.4, .6, .3, -.2, .7, .5]]},
    {'id': 'scara', 'port': 's500_tool/output', 'part': 'S500 tool mounting flange common flange', 'axis': 2, 'sign': -1,
     'method': 'scara_joints', 'poses': [[0, 0, 0, 0], [.2, .8, .04, -.4], [-.4, .5, .08, .6]]},
)


def main():
    for spec in SPECS:
        K.clean_scene()
        arm = make_robot(spec['id'], textures=False)
        gripper = make_robot('gripper', textures=False)
        arm.group.location = (0.4, 0.8, 1.2)
        arm.group.rotation_euler = Euler((0.1, 0.65, -0.15), 'XYZ')
        arm.group.scale = (1.7, 1.7, 1.7)
        bpy.context.view_layer.update()
        arm.attach(gripper, port=spec['port'], child_port='parallel_gripper/input')
        for i, pose in enumerate(spec['poses']):
            getattr(arm, spec['method'])(pose)
            gripper.jaw_gap(0.044 if i % 2 else 0.0)
            check_physical_ports(arm, gripper, spec, f"{spec['id']} pose {i}")
        arm.dispose()
        K.check(f"{spec['id']}: dispose takes the attached gripper with it", gripper.disposed)

    K.clean_scene()
    arm = make_robot('arm', textures=False)
    gripper = make_robot('gripper', textures=False)
    arm.joints([.2, .4, -.6, .25, .6, -.2])
    arm.attach(gripper, port='a650_j6/output', child_port='parallel_gripper/input', twist=math.pi / 2)
    bpy.context.view_layer.update()
    a, b = arm.port('a650_j6/output'), gripper.port('parallel_gripper/input')
    ma = a['owner'].matrix_world @ a['matrix']
    mb = b['owner'].matrix_world @ b['matrix']
    d = (mb.to_3x3() @ Vector((1, 0, 0))).normalized().dot((ma.to_3x3() @ Vector((0, 1, 0))).normalized())
    K.check('twist pi/2: quarter-turn clocking about the flange axis', abs(d - 1) < 1e-6, f'{d:.8f}')
    check_physical_ports(arm, gripper, {'port': 'a650_j6/output', 'part': 'A650 TC70 output flange common flange',
                                        'axis': 0, 'sign': 1}, 'twist pi/2')
    arm.dispose()

    K.clean_scene()
    frame = catalog()['port_frames']['a650_j6']['output']
    normal, tangent = frame['normal'], frame.get('tangent')
    n0 = len(bpy.data.objects)
    try:
        for bad in (None, [0, 0, 0], [math.nan, 0, 0]):
            frame['normal'] = bad
            try:
                make_robot('arm', textures=False)
                K.check(f'normal {bad} refused', False)
            except ValueError as e:
                K.check(f'normal {bad} refused: {e}', 'Invalid mount a650_j6/output' in str(e))
        frame['normal'], frame['tangent'] = normal, normal
        try:
            make_robot('arm', textures=False)
            K.check('a tangent parallel to the normal refused', False)
        except ValueError as e:
            K.check(f'a tangent parallel to the normal refused: {e}', 'tangent must not be parallel' in str(e))
    finally:
        frame['normal'], frame['tangent'] = normal, tangent
    K.check('the refused loads left nothing in the file', len(bpy.data.objects) == n0,
            f'{len(bpy.data.objects) - n0} objects left')

    arm = make_robot('arm', textures=False)
    gripper = make_robot('gripper', textures=False)
    parent = gripper.group.parent
    try:
        arm.attach(gripper, port='a650_j6/output', child_port='parallel_gripper/input', twist=math.nan)
        K.check('a NaN twist is refused', False)
    except ValueError as e:
        K.check(f'a NaN twist is refused: {e}', 'finite radians' in str(e))
    gripper.port('parallel_gripper/input')['matrix'] = Matrix.Diagonal((0, 0, 0, 1))
    try:
        arm.attach(gripper, port='a650_j6/output', child_port='parallel_gripper/input')
        K.check('a singular mount matrix is refused', False)
    except ValueError as e:
        K.check(f'a singular mount matrix is refused: {e}', 'Invalid mount matrix' in str(e))
    K.check('an invalid attachment changed no hierarchy', gripper.group.parent == parent and not arm.connections)
    K.save_results('attachment_frames')


main()
