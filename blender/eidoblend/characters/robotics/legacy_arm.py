"""eidoblend.characters.robotics.legacy_arm: RoboticArm (the production engine's robotic_arm.js), in Blender.

The older, primitive industrial arm: a turntable base, a 2-link shoulder / elbow, a wrist and one of four tools, with
smoothed 2-link IK. For new work the modular kit's A650 (make_robot('arm'), six real joints, damped least-squares IK,
the parallel gripper on its TC70 flange) supersedes it; the primitive arm is ported for the films and scenes written
against it, with its tools, which the kit does not have (welder torch, spray nozzle, saw blade).

    arm = RoboticArm(mount_point=(2, -5, 0), tool='welder', color=0xdddd00)       # Blender axes for every point
    arm.reach_to(target, dt)          smoothed IK toward a world point (Vector / tuple); updates arm.tool_tip
    arm.follow_path(waypoints, t, dt) waypoints [{'time', 'target', 'grip'?, 'action'?}]: smoothstep between them,
                                      grip interpolated, 'weld' / 'cut' actions as the original
    arm.set_grip(0..1)                the gripper's fingers (0 closed, 1 open)
    arm.rest(dt)                      back toward the folded neutral pose
    arm.tool_tip                      the tool tip in the world (a Vector)
    arm.bake(waypoints, frame_start, frame_end, fps=None) -> {frame: tool tip}
                                      follow_path frame by frame (its smoothing is stateful, so in order), keyed: the
                                      pivots' rotations, the fingers, the blade's spin, the welder tip's flicker
    RoboticArm.help()                 the API reference

The welder's flicker used Math.random(); here a seeded mulberry32 stream (seed=7) keeps renders repeatable.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from . import mech_parts as mp

_C4 = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))       # three -> Blender
_C4I = _C4.inverted()


def _clamp(v, a, b):
    return max(a, min(b, v))


class RoboticArm:
    def __init__(self, mount_point=None, upper_length=0.7, lower_length=0.6, base_radius=0.2, arm_thickness=0.08,
                 color=0xdddd00, joint_color=0x555555, tool='welder', smooth_speed=3.0, name='robotic arm', seed=7):
        self.upper_len, self.lower_len = upper_length, lower_length
        self.total_reach = upper_length + lower_length
        self.angles = {'base': 0.0, 'shoulder': 0.0, 'elbow': 0.0, 'wrist': 0.0}
        self.smooth_speed = smooth_speed
        self.rng = mp.mulberry(seed)
        self.tool = tool
        t = arm_thickness
        arm_mat = mp.metal(color, 0.25, 0.7, name + ' arm')
        joint_mat = mp.metal(joint_color, 0.2, 0.8, name + ' joint')
        dark = mp.metal(0x333333, 0.15, 0.8, name + ' dark')
        self.group = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(self.group)
        if mount_point is not None:
            self.group.location = Vector(mount_point)
        self._local = {}

        def node(nm, parent, pos=(0, 0, 0), geo=None, mat=None):
            ob = (mp.geometry_object(f'{name} {nm}', geo, mat) if geo is not None
                  else bpy.data.objects.new(f'{name} {nm}', None))
            if geo is None:
                bpy.context.scene.collection.objects.link(ob)
            ob.parent = parent
            ob.rotation_mode = 'XYZ'
            self._local[ob.name] = Matrix.Translation(pos)
            ob.matrix_basis = _C4 @ self._local[ob.name] @ _C4I
            return ob
        node('pedestal', self.group, (0, 0.075, 0), mp.cylinder_geometry(base_radius * 1.3, base_radius * 1.5, 0.15, 16),
             dark)
        self.base_pivot = node('base pivot', self.group, (0, 0.15, 0))
        g = mp.cylinder_geometry(base_radius, base_radius, 0.25, 16)
        node('base body', self.base_pivot, (0, 0.125, 0), g, arm_mat)
        self.shoulder_pivot = node('shoulder pivot', self.base_pivot, (0, 0.25, 0))
        node('shoulder joint', self.shoulder_pivot, (0, 0, 0), mp.sphere_geometry(t * 1.5, 12, 12), joint_mat)
        g = mp.box_geometry(t, upper_length, t)
        g.translate(0, upper_length / 2, 0)
        node('upper arm', self.shoulder_pivot, (0, 0, 0), g, arm_mat)
        node('hydraulic', self.shoulder_pivot, (t * 0.8, upper_length * 0.4, 0),
             mp.cylinder_geometry(t * 0.4, t * 0.4, upper_length * 0.6), dark)
        self.elbow_pivot = node('elbow pivot', self.shoulder_pivot, (0, upper_length, 0))
        node('elbow joint', self.elbow_pivot, (0, 0, 0), mp.sphere_geometry(t * 1.3, 12, 12), joint_mat)
        g = mp.box_geometry(t * 0.85, lower_length, t * 0.85)
        g.translate(0, lower_length / 2, 0)
        node('lower arm', self.elbow_pivot, (0, 0, 0), g, arm_mat)
        self.wrist_pivot = node('wrist pivot', self.elbow_pivot, (0, lower_length, 0))
        node('wrist joint', self.wrist_pivot, (0, 0, 0), mp.sphere_geometry(t, 10, 10), joint_mat)
        self.tool_group = node('tool', self.wrist_pivot)
        self.finger_l = self.finger_r = self.blade = self.welder_tip = None
        self.blade_angle = 0.0
        self._build_tool(tool, t, dark, arm_mat, node, name)
        self.tool_tip = Vector()
        self._pivots = (self.base_pivot, self.shoulder_pivot, self.elbow_pivot, self.wrist_pivot)

    def _build_tool(self, kind, t, dark, arm_mat, node, name):
        tg = self.tool_group
        if kind == 'gripper':
            node('gripper mount', tg, (0, 0.04, 0), mp.cylinder_geometry(t * 0.8, t * 0.8, 0.08, 8), dark)
            self.finger_l = node('finger left', tg, (-t * 0.6, 0.14, 0), mp.box_geometry(0.015, 0.12, 0.04), dark)
            self.finger_r = node('finger right', tg, (t * 0.6, 0.14, 0), mp.box_geometry(0.015, 0.12, 0.04), dark)
            self.grip_open = t * 0.6
        elif kind == 'spray':
            node('spray nozzle', tg, (0, 0.1, 0), mp.cylinder_geometry(0, 0.03, 0.12, 8), dark)
            node('spray hose', tg, (0.03, 0.05, 0), mp.cylinder_geometry(0.012, 0.012, 0.15),
                 mp.metal(0x880000, 0.6, 0.0, name + ' hose'))
        elif kind == 'saw':
            self.blade = node('saw blade', tg, (0, 0.08, 0), mp.cylinder_geometry(0.12, 0.12, 0.005, 32),
                              mp.metal(0xcccccc, 0.0, 1.0, name + ' blade'))
            self._set_local(self.blade, Matrix.Translation((0, 0.08, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        else:
            node('welder torch', tg, (0, 0.1, 0), mp.cylinder_geometry(0.02, 0.015, 0.12, 8), dark)
            mat = mp._emissive(name + ' welder tip', 0x00aaff, 0x00aaff, 2.0)
            self.welder_tip = node('welder tip', tg, (0, 0.16, 0), mp.sphere_geometry(0.01, 8, 8), mat)
            self.tip_strength = mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']

    def _set_local(self, ob, m):
        self._local[ob.name] = m
        ob.matrix_basis = _C4 @ m @ _C4I

    def _pivot(self, ob, axis, angle):
        """a pivot's rotation about three's local axis (its position kept)"""
        base = Matrix.Translation(self._local[ob.name].to_translation())
        self._set_local(ob, base @ Matrix.Rotation(angle, 4, axis))

    def reach_to(self, target, dt=1 / 24):
        bpy.context.view_layer.update()
        local_b = self.group.matrix_world.inverted() @ Vector(target)
        lt = _C4I @ local_b                                       # into three's axes
        target_base = math.atan2(lt.x, lt.z)
        dy = lt.y - 0.4
        dxz = math.hypot(lt.x, lt.z)
        dist = math.hypot(dy, dxz)
        dist = min(dist, self.total_reach * 0.98)
        dist = max(dist, abs(self.upper_len - self.lower_len) + 0.01)
        cos_e = _clamp((self.upper_len ** 2 + self.lower_len ** 2 - dist * dist) / (2 * self.upper_len * self.lower_len),
                       -1, 1)
        elbow = math.pi - math.acos(cos_e)
        cos_a = _clamp((dist * dist + self.upper_len ** 2 - self.lower_len ** 2) / (2 * dist * self.upper_len), -1, 1)
        shoulder = math.atan2(dy, dxz) + math.acos(cos_a)
        k = min(1.0, self.smooth_speed * dt)
        a = self.angles
        a['base'] += (target_base - a['base']) * k
        a['shoulder'] += (shoulder - a['shoulder']) * k
        a['elbow'] += (elbow - a['elbow']) * k
        self._pivot(self.base_pivot, 'Y', a['base'])
        self._pivot(self.shoulder_pivot, 'Z', a['shoulder'])
        self._pivot(self.elbow_pivot, 'Z', -a['elbow'])
        a['wrist'] = -(a['shoulder'] - a['elbow']) * 0.3
        self._pivot(self.wrist_pivot, 'Z', a['wrist'])
        bpy.context.view_layer.update()
        self.tool_tip = self.wrist_pivot.matrix_world.translation.copy() + Vector((0, 0, 0.15))
        if self.blade is not None:
            self.blade_angle += 15 * dt
            self._spin_blade()
        if self.welder_tip is not None:
            self.tip_strength.default_value = 1.5 + self.rng() * 1.5
        return self.tool_tip

    def _spin_blade(self):
        self._set_local(self.blade, Matrix.Translation((0, 0.08, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X')
                        @ Matrix.Rotation(self.blade_angle, 4, 'Z'))

    def set_grip(self, amount):
        if self.finger_l is None:
            return
        off = self.grip_open * _clamp(amount, 0, 1)
        self._set_local(self.finger_l, Matrix.Translation((-off, 0.14, 0)))
        self._set_local(self.finger_r, Matrix.Translation((off, 0.14, 0)))

    def follow_path(self, waypoints, t, dt=1 / 24):
        if not waypoints:
            return None
        first, last = waypoints[0], waypoints[-1]
        if t <= first['time']:
            target, action = first['target'], first.get('action')
        elif t >= last['time']:
            target, action = last['target'], last.get('action')
        else:
            a, b = first, waypoints[1]
            for i in range(len(waypoints) - 1):
                if waypoints[i]['time'] <= t < waypoints[i + 1]['time']:
                    a, b = waypoints[i], waypoints[i + 1]
                    break
            al = (t - a['time']) / (b['time'] - a['time'])
            al = al * al * (3 - 2 * al)
            target = [a['target'][k] + (b['target'][k] - a['target'][k]) * al for k in range(3)]
            action = a.get('action')
            if a.get('grip') is not None and b.get('grip') is not None:
                self.set_grip(a['grip'] + (b['grip'] - a['grip']) * al)
            elif a.get('grip') is not None:
                self.set_grip(a['grip'])
        self.reach_to(Vector(target), dt)
        if action == 'weld' and self.welder_tip is not None:
            self.tip_strength.default_value = 3 + self.rng() * 4
        if action == 'cut' and self.blade is not None:
            self.blade_angle += 30 * dt
            self._spin_blade()
        return self.tool_tip

    def rest(self, dt=1 / 24):
        bpy.context.view_layer.update()
        return self.reach_to(self.group.matrix_world @ (_C4 @ Vector((0, 0.8, 0.2))), dt)

    def bake(self, waypoints, frame_start, frame_end, fps=None):
        from bpy_extras import anim_utils
        fps = fps or bpy.context.scene.render.fps
        dt = 1 / fps
        moving = list(self._pivots) + [o for o in (self.finger_l, self.finger_r, self.blade) if o is not None]
        tips = {}
        for f in range(frame_start, frame_end + 1):
            tips[f] = self.follow_path(waypoints, (f - frame_start) / fps, dt).copy()
            for ob in moving:
                ob.keyframe_insert('location', frame=f)
                ob.keyframe_insert('rotation_euler', frame=f)
            if self.welder_tip is not None:
                self.tip_strength.keyframe_insert('default_value', frame=f)
        for idb in moving + ([self.tip_strength.id_data] if self.welder_tip is not None else []):
            ad = idb.animation_data
            if ad and ad.action:
                cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
                for fc in cb.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
        return tips

    @staticmethod
    def help():
        msg = '\n'.join([
            '---------- RoboticArm (eidoblend.characters.robotics.legacy_arm) ----------',
            'A jointed industrial arm with smoothed 2-link IK (shoulder + elbow), a turntable base and a wrist.',
            'For new work the modular kit supersedes it: make_robot("arm") + make_robot("gripper").',
            '  arm = RoboticArm(mount_point=(x, y, z), tool="welder", color=0xdddd00)   # welder | gripper | spray | saw',
            '  arm.reach_to(target, dt)        smoothed IK toward a world point; arm.tool_tip follows',
            '  arm.follow_path(waypoints, t, dt)   [{"time": 0, "target": (x, y, z), "action": "weld"},',
            '                                       {"time": 5, "target": (...), "grip": 0.0}]',
            '  arm.set_grip(0..1), arm.rest(dt), arm.bake(waypoints, frame_start, frame_end)',
            'Gotchas: the IK is 2-link, an unreachable target clamps to 98% of the reach; tool_tip is updated by',
            'reach_to; bake follow_path in frame order (the smoothing carries state from frame to frame).',
        ])
        print(msg)
        return msg
