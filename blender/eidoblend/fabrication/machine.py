"""eidoblend.fabrication.machine: the G430 gantry controls a fabrication job drives (motion.js's G430 part, MIT).

    from eidoblend.characters.robotics import make_robot
    from eidoblend.fabrication import g430
    printer = make_robot('fdm')
    m = g430(printer)                   # also sets printer.machine / axes / move_tool / tool_tip / cooling_fan
    m.bed_top, m.axis_limits, m.bed_bounds, m.tool, m.cutter, m.rest_tip
    printer.axes((x, y, z))             # machine XYZ travel (metres); the lead screws turn 8 mm per revolution
    printer.move_tool((x, y, height))   # the process tip in the bed frame: Blender (x, y) on the bed, height above it
    printer.tool_tip()                  # the same frame back; tool_tip(world=True) a world point
    printer.cooling_fan(seconds, rpm=4800)

The machine itself is the robotics kit's (eidoblend.characters.robotics). When the kit already provides these controls
(robot.machine with move_tool), g430 uses them as they are; otherwise it installs them from the same metadata the
WebGPU motion.js reads: the inspector assembly's bed_top_z_m, z_limits_m, tool and cutter, gantry_base's
bed_bounds_xy, the gantry joints' limits, and the tool's rest position in gantry_base's frame.
Bed frame: gantry_base's axes (Blender's, Z up), origin on the bed top. three's moveTool([x, h, z]) is
move_tool((x, -z, h)) here.
"""

from __future__ import annotations

import math

from mathutils import Matrix, Quaternion, Vector

from ._axes import Rec

TAU = math.pi * 2


def _get(o, k, default=None):
    if o is None:
        return default
    if isinstance(o, dict):
        return o.get(k, default)
    return getattr(o, k, default)


def world_matrix(ob):
    """An object's world matrix from its parent chain's local transforms (valid between depsgraph updates, which a
    per-frame keying pass would otherwise need after every joint change)."""
    m = ob.matrix_basis.copy()
    while ob.parent is not None:
        m = ob.matrix_parent_inverse @ m
        ob = ob.parent
        m = ob.matrix_basis @ m
    return m


class G430(Rec):
    pass


def _cutter(c):
    if c is None:
        return None
    return Rec(kind=_get(c, 'kind', 'flat'), radius=_get(c, 'radius', .003),
               flute_length=_get(c, 'fluteLength', _get(c, 'flute_length', .018)))


def rest_matrix(robot, name):
    """A kit joint's rest matrix_basis (the kit keys its rest poses by object name; older kits by module name)."""
    o = robot.roots[name]
    m = robot.rest.get(o.name)
    return (m if m is not None else robot.rest[name]).copy()


def g430(robot):
    """The G430 controls for a loaded fdm / cnc / cnc_relief / gantry robot (see the module notes)."""
    if getattr(robot, '_fabrication_g430', None) is not None:
        return robot._fabrication_g430
    existing = getattr(robot, 'machine', None)
    if existing is not None and callable(getattr(robot, 'move_tool', None)):
        if _get(existing, 'tool') is None:
            raise ValueError('Fabrication needs the assembled G430 FDM or CNC machine')
        m = G430(bed_top=_get(existing, 'bed_top'), axis_limits=_get(existing, 'axis_limits'),
                 bed_bounds=_get(existing, 'bed_bounds'), tool=_get(existing, 'tool'),
                 cutter=_cutter(_get(existing, 'cutter')), rest_tip=_get(existing, 'rest_tip'),
                 to_axes=_get(existing, 'to_axes'), provided_by='robotics kit')
        robot._fabrication_g430 = m
        return m
    roots, specs, report = robot.roots, robot.specs, robot.report
    if 'gantry_x' not in roots:
        raise ValueError('Fabrication needs the assembled G430 FDM or CNC machine')
    a = ((report.get('inspector') or {}).get('assemblies') or {}).get(robot.entry.get('assembly'), {})
    tool = {'spindle': 'spindle_fixed', 'extruder': 'extruder_fixed'}.get(a.get('tool'))
    cutter = _cutter(a.get('cutter') or ({'kind': 'flat', 'radius': .003, 'fluteLength': .018}
                                         if a.get('tool') == 'spindle' else None))
    m = G430(bed_top=a.get('bed_top_z_m', .056),
             axis_limits=[list(specs['gantry_x']['limits']), list(specs['gantry_y']['limits']),
                          list(a.get('z_limits_m') or specs['gantry_z']['limits'])],
             bed_bounds=list((specs.get('gantry_base') or {}).get('bed_bounds_xy') or [-.225, .225, -.274, .246]),
             tool=tool, cutter=cutter, provided_by='fabrication.machine')
    base = roots['gantry_base']
    screws = {n: (0 if '_x_' in n else 1 if '_y_' in n else 2) for n in roots
              if n.startswith('gantry_') and 'screw' in n}

    def axes(q):
        if len(q) != 3:
            raise ValueError('XYZ requires 3 coordinates')
        for i, v in enumerate(q):
            lim = m.axis_limits[i]
            if not math.isfinite(v) or v < lim[0] - 1e-7 or v > lim[1] + 1e-7:
                raise ValueError('G430 travel exceeded on ' + 'XYZ'[i])
        values = {'gantry_x': q[0], 'gantry_y': q[1], 'gantry_z': q[2]}
        for n, i in screws.items():
            values[n] = q[i] / .008 * TAU
        robot.set_joints(values)
        robot.state.update(values)
        fil = getattr(robot, 'filament', None)          # the WebGPU pose callbacks: the feed follows the head
        if fil is not None and callable(getattr(fil, 'update', None)):
            fil.update()
        return robot

    robot.axes = axes
    if tool:
        # the tip's rest position in gantry_base's frame, from the rest pose (independent of where the robot stands)
        rest = (_rest_world(robot, base).inverted() @ _rest_world(robot, roots[tool])).to_translation()
        m.rest_tip = tuple(rest)

        def to_axes(p):
            return [p[0] - rest.x, p[1] - rest.y, p[2] + m.bed_top - rest.z]
        m.to_axes = to_axes

        def move_tool(p):
            return axes(to_axes(p))

        def tool_tip(world=False):
            w = world_matrix(roots[tool]).to_translation()
            if world:
                return w
            return (world_matrix(base).inverted() @ w) - Vector((0, 0, m.bed_top))
        robot.move_tool = move_tool
        robot.tool_tip = tool_tip
    fans = [n for n in roots if n.split(' / ')[-1] == 'extruder_fan']

    def cooling_fan(seconds, rpm=4800):
        if not (math.isfinite(seconds) and seconds >= 0 and math.isfinite(rpm) and rpm >= 0):
            raise ValueError('Cooling fan time and rpm must be finite and nonnegative')
        for n in fans:
            angle = (seconds * rpm / 60 * TAU) % TAU
            spin(robot, n, angle)
            robot.state[n] = angle
        return robot

    robot.cooling_fan = cooling_fan
    robot.machine = m
    robot._fabrication_g430 = m
    return m


def _rest_of(robot, ob):
    m = robot.rest.get(ob.name)
    if m is None:
        n = next((n for n, o in robot.roots.items() if o == ob), None)
        m = robot.rest.get(n) if n is not None else None
    return (m if m is not None else ob.matrix_basis).copy()


def _rest_world(robot, ob):
    """ob's world matrix with every kit joint at rest."""
    m = _rest_of(robot, ob)
    while ob.parent is not None:
        m = ob.matrix_parent_inverse @ m
        ob = ob.parent
        m = _rest_of(robot, ob) @ m
    return m


def spin(robot, name, angle):
    """Turn a kit joint about its axis from the rest (a rotor's rpm keyframes), position and scale kept."""
    o = robot.roots[name]
    axis = Vector(robot.specs[name].get('axis') or (0, 0, 1)).normalized()
    loc, rot, sc = rest_matrix(robot, name).decompose()
    o.matrix_basis = Matrix.LocRotScale(loc, rot @ Quaternion(axis, angle), sc)
