"""rig.drive_module: one module of a robot driven by a simple expression of a property and the frame (the robotics
guide's recipe, on the G430 CNC), no render:

    bash run_blender.sh blender/tests/robotics/test_rig_drive_module.py

Checked: the gantry's X carriage follows its property along its axis; its lead screw turns 785.398 rad per metre of it
(an 8 mm lead); the spindle turns at 16,000 rpm with the frame at 24 fps; every driver is a simple expression (no
Python, so a saved file plays with scripts off); unrig_joints removes the drivers of the joints robot.joint_sliders
lists and their property, the modules back at rest.
"""

import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters.robotics import make_robot  # noqa: E402
from eidoblend.characters.robotics.kit import decompose_three  # noqa: E402
from eidoblend.characters.robotics.rig import drive_module, set_slider, unrig_joints  # noqa: E402

TAU = 2 * math.pi


def turn(robot, name):
    """a module's turn about its joint axis from rest as the scene shows it, -pi .. pi"""
    o = robot.roots[name]
    _l0, r0, _s0 = decompose_three(robot.rest[o.name])
    _l, r, _s = decompose_three(o.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_basis)
    rel = r0.inverted() @ r
    a = 2.0 * math.atan2(Vector((rel.x, rel.y, rel.z)).dot(Vector(robot.specs[name].get('axis') or (0, 0, 1))
                                                              .normalized()), rel.w)
    return (a + math.pi) % TAU - math.pi


sc = K.clean_scene(24)
cnc = make_robot('cnc')
x0 = cnc.roots['gantry_x'].matrix_world.translation.copy()
cnc.group['joint:gantry_x'] = 0.0                                       # the property first (keyable)
drive_module(cnc, 'gantry_x', 'joint:gantry_x')                         # the module follows it
drive_module(cnc, 'gantry_x_screw', 'joint:gantry_x', 'q * 785.398')    # its lead screw turning with it
drive_module(cnc, 'spindle_rotor', None, '(frame - 1) * 69.81')         # 16,000 rpm at 24 fps, no property
cnc.joint_sliders = {'gantry_x': 'joint:gantry_x', 'gantry_x_screw': None, 'spindle_rotor': None}
set_slider(cnc, 'gantry_x', 0.0501)
sc.frame_set(3)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
moved = (cnc.roots['gantry_x'].evaluated_get(dg).matrix_world.translation - x0).length
screw = turn(cnc, 'gantry_x_screw')
want_screw = (0.0501 * 785.398 + math.pi) % TAU - math.pi
spin = turn(cnc, 'spindle_rotor')
want_spin = (2 * 69.81 + math.pi) % TAU - math.pi
K.check(f'the X carriage follows its property ({moved * 1000:.3f} mm for 50.1 mm)', abs(moved - 0.0501) < 1e-6)
K.check(f'its lead screw turns with it, 785.398 rad a metre ({math.degrees(screw):.3f} vs '
        f'{math.degrees(want_screw):.3f} deg)', abs(screw - want_screw) < 1e-4)
K.check(f'the spindle turns with the frame, 69.81 rad a frame ({math.degrees(spin):.3f} vs {math.degrees(want_spin):.3f} '
        'deg at frame 3)', abs(spin - want_spin) < 1e-4)
drivers = [fc.driver for o in cnc.roots.values() if o.animation_data for fc in o.animation_data.drivers]
K.check(f'every driver is a simple expression ({len(drivers)} drivers)',
        len(drivers) == 11 and all(d.is_simple_expression and d.is_valid for d in drivers))
unrig_joints(cnc)
sc.frame_set(1)
bpy.context.view_layer.update()
left = sum(len(o.animation_data.drivers) for o in cnc.roots.values() if o.animation_data)
K.check(f'unrig_joints removes the listed joints\' drivers and their property ({left} drivers, properties '
        f"{[k for k in cnc.group.keys() if k.startswith('joint:')]})",
        left == 0 and not [k for k in cnc.group.keys() if k.startswith('joint:')])
K.save_results('rig_drive_module')
