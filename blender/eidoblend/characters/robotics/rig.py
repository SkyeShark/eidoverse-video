"""eidoblend.characters.robotics.rig: a robot's joints as sliders that drive its modules (the inspector's joint panel).

The WebGPU inspector gives every revolute and prismatic joint with limits a range input that calls setJoints, and the
rotary fixture's output and chuck one shared "A axis / chuck" input. In Blender the same panel is a set of custom
properties on the robot's empty, each with its limits as the slider's range, and a SIMPLE-EXPRESSION driver on the
module it moves (no Python driver, so they evaluate with auto-run off):

    revolute    the module's quaternion = rest (three's split of the rest matrix) * turn(axis, q) [* X half-turn
                for a mirrored module, Blender's own split], so each component is A cos(q/2) + B sin(q/2)
    prismatic   the module's location = rest location + rest rotation * axis * q

    joints = rig_joints(robot, values=None)
                                        {joint name: custom property name}; robot.group['joint:<name>'] = value. The
                                        sliders start at `values` (default robot.state, the joints set_joints moved)
    measure_joints(robot)               each slider's value read off its module's CURRENT transform (its turn about
                                        the axis from rest, or its travel along it), clamped to the limits: rigging
                                        with these keeps the visible pose, keyed or sampled, as the inspector's
                                        sliders move one joint from the pose on screen
    set_slider(robot, joint, value)     the same from a script, with the depsgraph tagged (a Python write to a custom
                                        property alone does not re-evaluate its drivers)
    unrig_joints(robot)                 removes the drivers and the properties

The sliders are keyable like any property, so a hand-made animation of the joint values plays from the file. A robot
with sliders is in "manual" mode, as the inspector is after a slider moves: its play() keys transforms the drivers
would override, so unrig first to key a sample.
"""

from __future__ import annotations

import bpy
from mathutils import Quaternion, Vector

PREFIX = 'joint:'


def _qmul(a, b):
    return Quaternion((a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
                       a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
                       a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
                       a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0]))


def _num(x):
    """a literal Blender's simple-expression evaluator reads (no exponent notation)"""
    s = f'{x:.12f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _driver(ob, path, index, prop, holder, expr):
    fc = ob.driver_add(path, index)
    d = fc.driver
    d.type = 'SCRIPTED'
    v = d.variables.new()
    v.name = 'q'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = holder
    v.targets[0].data_path = f'["{prop}"]'
    d.expression = expr
    if not d.is_simple_expression:
        raise RuntimeError(f'driver {ob.name}.{path}[{index}] is not a simple expression: {expr}')
    return fc


def joint_names(robot):
    """the inspector's joint list: revolute / prismatic with limits, and the rotary fixture's A axis"""
    out = []
    for n, s in robot.specs.items():
        a_axis = bool(robot.report.get('rotary_fixture')) and n == 'rotary_output'
        if not a_axis and (s.get('joint_type') not in ('revolute', 'prismatic') or not s.get('limits')):
            continue
        out.append(n)
    return out


def _limits(robot, n):
    import math
    a_axis = bool(robot.report.get('rotary_fixture')) and n == 'rotary_output'
    return (-math.pi, math.pi) if a_axis else tuple(robot.specs[n]['limits'])


def measure_joints(robot):
    """{joint: value} for every slider joint, read off the module's current local transform against its rest: the
    signed turn about the joint axis (three's split of the matrices, as set_joints composes them) or the travel along
    it, clamped to the slider's range. A pose set_joints made reads back exactly; a GLB clip's node rotation reads as
    its component about the axis."""
    import math
    from .kit import decompose_three
    out = {}
    for n in joint_names(robot):
        o, s = robot.roots[n], robot.specs[n]
        loc0, rot0, _s0 = decompose_three(robot.rest[o.name])
        loc, rot, _s = decompose_three(o.matrix_basis)
        axis = Vector(s.get('axis') or (0, 0, 1)).normalized()
        if s.get('joint_type') == 'prismatic':
            v = (rot0.inverted() @ (loc - loc0)).dot(axis)
        else:
            rel = rot0.inverted() @ rot
            v = 2.0 * math.atan2(Vector((rel.x, rel.y, rel.z)).dot(axis), rel.w)
            v = math.atan2(math.sin(v), math.cos(v))
        lo, hi = _limits(robot, n)
        out[n] = max(lo, min(hi, v))
    return out


def rig_joints(robot, values=None):
    from .kit import decompose_three
    import math
    g = robot.group
    made = {}
    for n in joint_names(robot):
        s = robot.specs[n]
        a_axis = bool(robot.report.get('rotary_fixture')) and n == 'rotary_output'
        lo, hi = _limits(robot, n)
        prop = PREFIX + ('A axis / chuck' if a_axis else n)
        start = robot.state.get(n, 0.0) if values is None or n not in values else values[n]
        g[prop] = float(max(lo, min(hi, start)))
        ui = g.id_properties_ui(prop)
        ui.update(min=lo, max=hi, soft_min=lo, soft_max=hi, step=0.01 if s.get('joint_type') == 'prismatic' else 1,
                  description=f"{n} ({s.get('joint_type')}, {'m' if s.get('joint_type') == 'prismatic' else 'rad'})")
        targets = [n] + (['rotary_chuck'] if a_axis and 'rotary_chuck' in robot.roots else [])
        for t in targets:
            o = robot.roots[t]
            st = robot.specs[t]
            rest = robot.rest[o.name]
            loc, q3, sc = decompose_three(rest)
            axis = Vector(st.get('axis') or (0, 0, 1)).normalized()
            o.matrix_basis = rest
            o.rotation_mode = 'QUATERNION'
            if st.get('joint_type') == 'prismatic':
                d = q3 @ axis
                for i in range(3):
                    _driver(o, 'location', i, prop, g, f'{_num(loc[i])} + {_num(d[i])} * q')
            else:
                tail = Quaternion((0.0, 1.0, 0.0, 0.0)) if rest.to_3x3().determinant() < 0 else Quaternion()
                A = _qmul(_qmul(q3, Quaternion()), tail)
                B = _qmul(_qmul(q3, Quaternion((0.0, axis.x, axis.y, axis.z))), tail)
                for i in range(4):
                    _driver(o, 'rotation_quaternion', i, prop, g,
                            f'{_num(A[i])} * cos(q / 2) + {_num(B[i])} * sin(q / 2)')
        made[n] = prop
    robot.joint_sliders = made
    g.update_tag()                         # new drivers are evaluated once their property is tagged: pose them now
    bpy.context.view_layer.update()
    return made


def set_slider(robot, joint, value):
    """move one slider from a script (the UI tags the update itself; a Python write to a custom property does not)"""
    robot.group[robot.joint_sliders[joint]] = float(value)
    robot.group.update_tag()
    bpy.context.view_layer.update()


def unrig_joints(robot):
    for n, prop in (getattr(robot, 'joint_sliders', None) or {}).items():
        targets = [n] + (['rotary_chuck'] if prop.endswith('A axis / chuck') and 'rotary_chuck' in robot.roots else [])
        for t in targets:
            o = robot.roots[t]
            for path in ('location', 'rotation_quaternion'):
                try:
                    o.driver_remove(path)
                except TypeError:
                    pass
        if prop in robot.group.keys():
            del robot.group[prop]
    robot.joint_sliders = {}
    bpy.context.view_layer.update()
