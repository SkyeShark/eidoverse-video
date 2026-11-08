"""eidoblend.characters.robotics.motion: motion.js, the kit's deterministic controls and motion samples, in Blender.

Every Robot (kit.py) carries these, as installMotion gives them in the WebGPU edition. Values are metres and radians in
the robot's own frame (the 'robot|<id>' empty's local axes, Blender's Z up):

    robot.clips                     the sample names this robot has ('walk', 'run-circle', 'run-figure_eight',
                                    'run-straight', 'grasp', 'drive', 'drive-circle', 'stock-setup', 'flight', 'fold',
                                    'rotors', 'joints', 'filament-feed')
    robot.sample(clip, seconds)     the pose at that time, deterministic and seekable (it resets first)
    robot.play(clip, speed, start, frame_start, frame_end)
                                    the WebGPU play() registers the engine clock; here the clip is SAMPLED AT EVERY
                                    FRAME of the scene's range and keyed (LINEAR, one action with a slot per moving
                                    object, Geometry Nodes inputs the sample changes included: the live filament's
                                    strand), so the saved .blend plays and renders any frame on its own:
                                    t = max(0, (seconds since frame_start - start) * speed)
    robot.stop()                    removes those keys (the pose stays where the last sample left it)
    robot.grasp(0..1) / grasp_reference()       every hand's reviewed grasp; the grasped cylinder under each hand
    robot.jaw_gap(0..0.044)         both parallel jaws and the opposed lead screw
    robot.spin_rotors(angle) / fold(0..1)      propellers with their directions; park, unlock, fold the booms
    robot.track_travel({track root: metres})   belts (rigid shoes split from the batched mesh) and wheels
    robot.cooling_fan(seconds, rpm=4800)       the extruder fan
    robot.rotary_setup(stock_length, stock_width, stock_height, quill) / rotary_stock_setup
    A650:  robot.ik (SerialArm), robot.joints(q6), robot.move_to(target 4x4, seed)
    S500:  robot.scara (the solver), robot.scara_joints(q4), robot.move_scara(position, yaw, tcp, seed)
    G430:  robot.machine {bed_top, axis_limits, bed_bounds, tool, cutter, rest_tip, to_axes}, robot.axes(xyz),
           robot.move_tool((x, y, height above the bed)), robot.tool_tip(world=False)
    robot.running (the humanoid / quadruped gait controller, running.py), robot.walk_clips (the GLB's own animations)

Axes: motion.js converts every authored number into three's +Y up through its C matrix and axis(); here the authored
numbers ARE Blender's, so a three offset (x, y, z) in the sources is (x, -z, y) below, and a turn about three's local Y
(up) is a turn about Blender's local Z.
"""

from __future__ import annotations

import math
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import io as kio
from . import solvers
from .running import RunningController

TAU = math.pi * 2


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (10 + x * (-15 + 6 * x))


def _suffix(n):
    return n.split(' / ')[-1]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _emod(a, n):
    return ((a % n) + n) % n


def track_frame(s, p):
    """motion.js trackFrame: the shoe frame at arc length s round the track's stadium path (authoring axes: x along the
    belt, z up, y the axle); p = {half_wheelbase_m, radius_m, height_m, length_m}"""
    h, r, z = p['half_wheelbase_m'], p['radius_m'], p['height_m']
    s = _emod(s, p['length_m'])
    if s < 2 * h:
        x, y, tx, tz, nx, nz = -h + s, z + r, 1.0, 0.0, 0.0, 1.0
    else:
        s -= 2 * h
        if s < math.pi * r:
            a = math.pi / 2 - s / r
            x, y = h + r * math.cos(a), z + r * math.sin(a)
            tx, tz, nx, nz = math.sin(a), -math.cos(a), math.cos(a), math.sin(a)
        else:
            s -= math.pi * r
            if s < 2 * h:
                x, y, tx, tz, nx, nz = h - s, z - r, -1.0, 0.0, 0.0, -1.0
            else:
                a = -math.pi / 2 - (s - 2 * h) / r
                x, y = -h + r * math.cos(a), z + r * math.sin(a)
                tx, tz, nx, nz = math.sin(a), -math.cos(a), math.cos(a), math.sin(a)
    return Matrix(((tx, 0, nx, x), (0, 1, 0, 0), (tz, 0, nz, y), (0, 0, 0, 1)))


def _three_split(m):
    from .kit import decompose_three
    return decompose_three(m)


class _WalkClip:
    """one glTF animation of the GLB, evaluated as three's AnimationMixer does (LoopRepeat, linear / slerp)"""

    def __init__(self, robot, anim):
        self.name = anim.get('name', '')
        self.channels = []
        dur = 0.0
        for ch in anim['channels']:
            node = ch['target'].get('node')
            obj = robot.node_obj.get(node)
            if obj is None:
                continue
            smp = anim['samplers'][ch['sampler']]
            if smp.get('interpolation', 'LINEAR') not in ('LINEAR', 'STEP'):
                raise ValueError(f"walk clip {self.name}: {smp['interpolation']} keys are not supported")
            times = [t[0] for t in kio.glb_accessor(robot.gltf_path, smp['input'])]
            vals = kio.glb_accessor(robot.gltf_path, smp['output'])
            path = ch['target']['path']
            if path == 'translation':
                vals = [Vector((v[0], -v[2], v[1])) for v in vals]
            elif path == 'rotation':
                vals = [Quaternion((v[3], v[0], -v[2], v[1])) for v in vals]
            elif path == 'scale':
                vals = [Vector((v[0], v[2], v[1])) for v in vals]
            else:
                continue
            self.channels.append((obj, path, times, vals, smp.get('interpolation', 'LINEAR')))
            dur = max(dur, times[-1])
        self.duration = dur

    def apply(self, time):
        t = time - self.duration * math.floor(time / self.duration) if self.duration > 0 else 0.0
        for obj, path, times, vals, interp in self.channels:
            if t <= times[0]:
                v = vals[0]
            elif t >= times[-1]:
                v = vals[-1]
            else:
                lo, hi = 0, len(times) - 1
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if times[mid] <= t:
                        lo = mid
                    else:
                        hi = mid
                w = (t - times[lo]) / (times[hi] - times[lo])
                if interp == 'STEP':
                    v = vals[lo]
                elif path == 'rotation':
                    v = vals[lo].slerp(vals[hi], w)
                else:
                    v = vals[lo].lerp(vals[hi], w)
            loc, rot, sc = _three_split(obj.matrix_basis)
            if path == 'translation':
                loc = v
            elif path == 'rotation':
                rot = v
            else:
                sc = v
            obj.matrix_basis = Matrix.LocRotScale(loc, rot, sc)


class MotionMixin:
    """motion.js installMotion's controls, as methods of kit.Robot"""

    # ------------------------------------------------------------------------------------------------ install
    def install_motion(self):
        roots, specs, report = self.roots, self.specs, self.report
        names = list(roots)
        self.has_rotary_setup = 'rotary_tailstock' in roots and 'rotary_jaw_0' in roots
        self.rotary_stock_setup = None
        self._fans = [n for n in names if _suffix(n) == 'extruder_fan']
        interaction = kio.json_file('metadata/interaction.json')
        if report.get('novel'):
            for n, rows in report['novel']['nominal_matrices'].items():
                o = roots.get(n)
                if o is not None:
                    self.rest[o.name] = Matrix(rows)
            self.default_joints = {n: d['angle'] for n, d in report['novel']['drives'].items() if n in roots}
            self.reset()
            self.set_joints(self.default_joints)
        self._grasp = interaction['mobile']['hand']['grasp']
        self._grasp_prefixes = [n[:-len('hand_base')] for n in names if _suffix(n) == 'hand_base']
        self._install_tracks()
        self.ik = solvers.SerialArm(report) if 'a650_j6' in roots else None
        self.scara = solvers.scara if 's500_shoulder' in roots else None
        self.machine = None
        if 'gantry_x' in roots:
            a = ((report.get('inspector') or {}).get('assemblies') or {}).get(self.entry.get('assembly')) or {}
            tool = 'spindle_fixed' if a.get('tool') == 'spindle' else 'extruder_fixed' if a.get('tool') == 'extruder' else None
            cutter = a.get('cutter')
            if cutter is None and a.get('tool') == 'spindle':
                cutter = {'kind': 'flat', 'radius': 0.003, 'fluteLength': 0.018}
            self.machine = {
                'bed_top': a.get('bed_top_z_m') if a.get('bed_top_z_m') is not None else 0.056,
                'axis_limits': [list(specs['gantry_x']['limits']), list(specs['gantry_y']['limits']),
                                list(a.get('z_limits_m') or specs['gantry_z']['limits'])],
                'bed_bounds': list((specs.get('gantry_base') or {}).get('bed_bounds_xy') or [-0.225, 0.225, -0.274, 0.246]),
                'tool': tool, 'cutter': cutter, 'tool_tip_rest_z_m': a.get('tool_tip_rest_z_m')}
            if tool:
                bpy.context.view_layer.update()
                base = roots['gantry_base']
                rest = base.matrix_world.inverted() @ roots[tool].matrix_world.translation
                self.machine['rest_tip'] = list(rest)
                bed = self.machine['bed_top']
                self.machine['to_axes'] = lambda p, rest=rest, bed=bed: [p[0] - rest.x, p[1] - rest.y, p[2] + bed - rest.z]
        gait = self.entry.get('family') in ('humanoid', 'quadruped')
        self.running, self.walk_clips = None, []
        if gait:
            data = kio.json_file(f"metadata/{self.entry['family']}_running.json")
            nodes = {self.node_name[o.name]: o for o in self.objects}
            self.running = RunningController(nodes, self.entry['family'] == 'quadruped', data)
            self.walk_clips = [_WalkClip(self, a) for a in self.gltf.get('animations', [])]
        clips = ['walk', 'run-circle', 'run-figure_eight', 'run-straight'] if gait else []
        if self._grasp_prefixes:
            clips.append('grasp')
        if self.track_bindings is not None:
            clips += ['drive', 'drive-circle']
        if self.has_rotary_setup:
            clips.append('stock-setup')
        if any(n.endswith('airframe') for n in names):
            clips += ['flight', 'fold', 'rotors']
        clips.append('joints')
        if 'filament_reel' in roots and not self.machine:
            clips.insert(0, 'filament-feed')
        self.clips = clips
        self._played = None

    # ------------------------------------------------------------------------------------------------ helpers
    def _turn(self, name, axis, angle):
        """rest rotation * the turn, position and scale as they are (spinRotors / coolingFan / the wheels)"""
        o = self.roots[name]
        loc, _r, sc = _three_split(o.matrix_basis)
        _l, rq, _s = _three_split(self.rest[o.name])
        o.matrix_basis = Matrix.LocRotScale(loc, rq @ Quaternion(Vector(axis).normalized(), angle), sc)

    def _require(self, ok, what):
        if not ok:
            raise AttributeError(f'{self.id} has no {what}')

    # ------------------------------------------------------------------------------------------------ controls
    def cooling_fan(self, seconds, rpm=4800):
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (seconds, rpm)) or seconds < 0 or rpm < 0:
            raise ValueError('Cooling fan time and rpm must be finite and nonnegative')
        for n in self._fans:
            angle = math.fmod(seconds * rpm / 60 * TAU, TAU)
            self._turn(n, self.specs[n]['axis'], angle)
            self.state[n] = angle
        return self

    def rotary_setup(self, stock_length=0.140, stock_width=0.036, stock_height=0.036, quill=0.0):
        self._require(self.has_rotary_setup, 'adjustable rotary fixture')
        setup = solvers.rotary_fixture_setup(stock_length, stock_width, stock_height, quill)
        self.set_joints(setup['joints'])
        self.rotary_stock_setup = setup
        return setup

    def grasp(self, phase):
        if not isinstance(phase, (int, float)) or not math.isfinite(phase) or phase < 0 or phase > 1:
            raise ValueError('Grasp phase must be 0..1')
        q = {}
        for p in self._grasp_prefixes:
            for n, v in solvers.grasp_values(self._grasp, phase).items():
                if p + n in self.roots:
                    q[p + n] = v
        self.set_joints(q)
        return self

    def grasp_reference(self):
        """the cylinder the reviewed grasp closes on, under each hand (interaction.json mobile.hand.grasp.object)"""
        import bmesh
        out = []
        s = self._grasp['object']
        for p in self._grasp_prefixes:
            me = bpy.data.meshes.new('Grasp reference')
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=s['radius_m'], radius2=s['radius_m'],
                                  depth=s['length_m'])
            for f in bm.faces:
                f.smooth = len(f.verts) == 4
            bm.to_mesh(me)
            bm.free()
            mat = bpy.data.materials.get('robot grasp reference') or bpy.data.materials.new('robot grasp reference')
            mat.use_nodes = True
            b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            b.inputs['Base Color'].default_value = (0.0368, 0.2051, 0.2346, 1.0)      # 0x367d85, linear
            b.inputs['Roughness'].default_value = 0.5
            b.inputs['Metallic'].default_value = 0.1
            me.materials.append(mat)
            ob = bpy.data.objects.new('Grasp reference', me)
            self.collection.objects.link(ob)
            ob.parent = self.roots[p + 'hand_base']
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.matrix_basis = Matrix.LocRotScale(Vector(s['center_m']),
                                                 Vector((0, 0, 1)).rotation_difference(Vector(s['axis']).normalized()),
                                                 Vector((1, 1, 1)))
            ob['grasp_reference'] = True
            out.append(ob)
        self.grasp_references.extend(out)
        self.extra_objects.extend(out)
        return out

    def jaw_gap(self, gap):
        if not isinstance(gap, (int, float)) or not math.isfinite(gap) or gap < 0 or gap > 0.044:
            raise ValueError('Jaw gap must be 0..0.044 m')
        q = {}
        for n in self.roots:
            if _suffix(n) in ('jaw_left', 'jaw_right'):
                q[n] = gap / 2
            elif _suffix(n) == 'pg_drive_screw':
                q[n] = -gap / 2 / 0.004 * TAU
        self.set_joints(q)
        return self

    def spin_rotors(self, angle):
        if not isinstance(angle, (int, float)) or not math.isfinite(angle):
            raise ValueError('Rotor angle must be finite')
        q = {}
        for n in self.roots:
            if re.search(r'air_rotor_[0-3]$', n):
                boom = n.replace('rotor', 'boom', 1)
                if abs(self.state.get(boom, 0.0)) > 1e-7 and angle != 0:
                    raise ValueError('Deploy booms before spinning rotors')
                q[n] = angle * (1, -1, -1, 1)[int(n[-1])]
        for n, v in q.items():
            self._turn(n, self.specs[n]['axis'], v)
        return self

    def fold(self, phase):
        if not isinstance(phase, (int, float)) or not math.isfinite(phase) or phase < 0 or phase > 1:
            raise ValueError('Fold phase must be 0..1')
        self.spin_rotors(0)
        q = {}
        for n in self.roots:
            if re.search(r'air_boom_[0-3]$', n):
                q[n] = max(0.0, (phase - 0.15) / 0.85) * 0.95
            if re.search(r'air_lock_[0-3]$', n):
                q[n] = min(phase / 0.15, 1.0) * 0.04
        self.set_joints(q)
        return self

    # ------------------------------------------------------------------------------------------------ tracks
    def _install_tracks(self):
        from ._mesh import submesh
        specs = (self.report.get('mobile') or {}).get('tracks')
        self.track_bindings = None
        self._track_specs = specs
        if not specs:
            return
        bindings = []
        bpy.context.view_layer.update()
        originals = [o for o in self.objects if o.type == 'MESH']
        for n, s in specs.items():
            root = self.roots.get(n)
            if root is None:
                continue
            shoes = {t['part']: t for t in s['shoes']}
            for mesh in originals:
                faces = self.part_for_face.get(mesh.name)
                if not faces or not any(p in shoes for p in faces):
                    continue
                keep, parts = [], {}
                for fi, p in enumerate(faces):
                    (parts.setdefault(p, []) if p in shoes else keep).append(fi)
                local_from_root = mesh.matrix_world.inverted() @ root.matrix_world
                root_from_local = local_from_root.inverted()
                old = mesh.data
                mesh.data = submesh(old, keep, old.name + '|frame')
                self.part_for_face[mesh.name] = [p for p in faces if p not in shoes]
                for p, idx in parts.items():
                    ob = bpy.data.objects.new(p, submesh(old, idx, p))
                    self.collection.objects.link(ob)
                    ob.parent = mesh
                    ob.matrix_parent_inverse = Matrix.Identity(4)
                    for k in ('eidoverseRobotics', '_loadedAsset', 'assembly', 'eidoverseAssembly', 'batch'):
                        if mesh.get(k) is not None:
                            ob[k] = mesh[k]
                    ob['part_id'] = p
                    ob['track_shoe'] = n
                    ob.rotation_mode = 'QUATERNION'
                    self.part_ids[ob.name] = [p]
                    self.part_for_face[ob.name] = [p] * len(idx)
                    self.extra_objects.append(ob)
                    spec = shoes[p]
                    bindings.append({'n': n, 'ob': ob, 'spec': spec, 'path': s['path'], 'left': local_from_root,
                                     'right': Matrix(spec['rest_frame']).inverted() @ root_from_local})
                if old.users == 0:
                    bpy.data.meshes.remove(old)
        self.track_bindings = bindings
        self.track_travel({})

    def track_travel(self, values=None):
        """belt travel in metres per track root ({'track_left': 0.3, ...}): every rigid shoe round its stadium path,
        every wheel and roller rolled by travel / its rolling radius -> {'distances', 'wheels'}"""
        self._require(self.track_bindings is not None, 'tracks')
        values = values or {}
        specs = self._track_specs
        for n, v in values.items():
            if n not in specs or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError('Invalid track travel ' + n)
        for b in self.track_bindings:
            b['ob'].matrix_basis = b['left'] @ track_frame(b['spec']['distance_m'] + values.get(b['n'], 0.0),
                                                           b['path']) @ b['right']
        wheels = {}
        for n, s in specs.items():
            d = values.get(n, 0.0)
            for w in list(s.get('wheel_roots', [])) + list(s.get('roller_roots', [])):
                if w in self.roots:
                    sp = self.specs[w]
                    a = d / (sp.get('rolling_radius_m') if sp.get('rolling_radius_m') is not None else 0.058)
                    self._turn(w, sp['axis'], a)
                    wheels[w] = a
        return {'distances': dict(values), 'wheels': wheels}

    # ------------------------------------------------------------------------------------------------ arms
    def joints(self, q):
        """the A650's six joints"""
        self._require(self.ik is not None, 'A650 arm')
        return self.set_joints({f'a650_j{i + 1}': v for i, v in enumerate(q)})

    def move_to(self, target, seed=None):
        """the A650's TCP to a 4x4 target in the robot's frame (the GLB root's), bounded damped least squares"""
        self._require(self.ik is not None, 'A650 arm')
        rows = [[float(v) for v in r] for r in target]
        q = self.ik.inverse(rows, seed)
        if not q:
            raise ValueError('A650 target is unreachable within joint limits')
        return self.joints(q)

    def scara_joints(self, q):
        self._require(self.scara is not None, 'S500 SCARA')
        return self.set_joints({n: q[i] for i, n in enumerate(('s500_shoulder', 's500_elbow', 's500_quill', 's500_tool'))})

    def move_scara(self, position, yaw=0.0, tcp=(0.0, 0.0, 0.0), seed=None):
        """the S500's tool (plus a tool-frame tcp offset) to (x, y, z) in the robot's frame at yaw"""
        self._require(self.scara is not None, 'S500 SCARA')
        x, y, z = position
        sols = self.scara.inverse(x, y, z, yaw, tcp, seed)
        if not sols:
            raise ValueError('S500 target is unreachable')
        return self.scara_joints(sols[0])

    # ------------------------------------------------------------------------------------------------ G430
    def axes(self, q):
        """the G430's machine XYZ travel (metres), the lead screws turned with it"""
        self._require(self.machine is not None, 'G430 gantry')
        if len(q) != 3:
            raise ValueError('XYZ requires 3 coordinates')
        lim = self.machine['axis_limits']
        for i, v in enumerate(q):
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v < lim[i][0] - 1e-7 or v > lim[i][1] + 1e-7:
                raise ValueError('G430 travel exceeded on ' + 'XYZ'[i])
        values = {'gantry_x': q[0], 'gantry_y': q[1], 'gantry_z': q[2]}
        for n in self.specs:
            if n.startswith('gantry_') and 'screw' in n:
                i = 0 if '_x_' in n else 1 if '_y_' in n else 2
                values[n] = q[i] / 0.008 * TAU
        self.set_joints(values)
        return self

    def move_tool(self, p):
        """the process head's tip to (x, y, height above the bed) in the gantry base's frame"""
        self._require(self.machine is not None and self.machine.get('tool'), 'G430 process head')
        return self.axes(self.machine['to_axes'](p))

    def tool_tip(self, world=False):
        """the tool tip: (x, y, height above the bed) in the gantry base's frame, or a world Vector"""
        self._require(self.machine is not None and self.machine.get('tool'), 'G430 process head')
        bpy.context.view_layer.update()
        p = self.roots[self.machine['tool']].matrix_world.translation.copy()
        if world:
            return p
        return self.roots['gantry_base'].matrix_world.inverted() @ p - Vector((0, 0, self.machine['bed_top']))

    # ------------------------------------------------------------------------------------------------ samples
    def sample(self, clip, time):
        """the motion sample `clip` at `time` seconds: deterministic, seekable, reset first"""
        if not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
            raise ValueError('Animation time must be nonnegative seconds')
        self.reset()
        roots, specs, report = self.roots, self.specs, self.report
        names = list(roots)
        t = math.fmod(time, 12) / 12
        s = math.sin(t * TAU)
        curl = 0.5 - 0.5 * math.cos(t * TAU)
        if clip == 'stock-setup':
            if not self.has_rotary_setup:
                raise ValueError('No adjustable rotary fixture')
            self.rotary_setup(stock_length=0.130 + 0.050 * s, stock_width=0.034 + 0.016 * math.cos(t * TAU),
                              stock_height=0.034 - 0.016 * math.cos(t * TAU), quill=0.004 * s)
            self.set_joints({'rotary_output': time * 0.25})
            return self
        if clip == 'walk':
            if not self.walk_clips:
                raise ValueError('No walk clip for ' + self.id)
            for w in self.walk_clips:
                w.apply(time)
            return self
        if clip.startswith('run-'):
            if self.running is None:
                raise ValueError('No gait for ' + self.id)
            c = clip[4:]
            if c not in self.running.data['clips']:
                raise ValueError('Unknown gait ' + clip)
            self.running.apply(c, math.fmod(time, self.running.duration(c)))
            return self
        if clip not in self.clips:
            raise ValueError('Unknown sample ' + clip + ' for ' + self.id)
        if clip == 'filament-feed':
            if self.filament is None:
                raise ValueError('filament-feed drives the live filament, which the fabrication port (filament.js '
                                 'installFilament) installs: none is installed on ' + self.id)
            self.filament.seek(time * 0.025)
            return self
        if clip == 'grasp':
            return self.grasp(min(time / 3, 1.0))
        if clip == 'fold':
            return self.fold(curl)
        if clip == 'rotors':
            return self.spin_rotors(time * TAU * 1.2)
        if clip == 'flight':
            envelope = _smooth((t - 0.30) / 0.08) * (1 - _smooth((t - 0.74) / 0.08))
            height = 0.22 * _smooth((t - 0.12) / 0.17) * (1 - _smooth((t - 0.78) / 0.18))
            x = 0.11 * math.sin(TAU * (t - 0.30) / 0.44) * envelope
            for n in names:
                if _suffix(n) == 'airframe':
                    o = roots[n]
                    loc, rot, sc = _three_split(o.matrix_basis)
                    o.matrix_basis = Matrix.LocRotScale(loc + Vector((x, 0.0, height)), rot, sc)
            return self.spin_rotors(time * TAU * 1.6416667)
        if clip.startswith('drive'):
            tracks = report['mobile']['tracks']
            q = {}
            for left in [n for n in tracks if n.endswith('left')]:
                right = left[:-4] + 'right'
                novel = report.get('novel') or {}
                parent = novel.get('body_root') if novel.get('body_root') is not None else \
                    ((report.get('roots') or {}).get(left) or {}).get('parent')
                base = roots.get(parent)
                if right not in tracks or base is None:
                    continue
                gauge = (self.rest[roots[left].name].translation - self.rest[roots[right].name].translation).length
                if clip == 'drive-circle':
                    yaw = time * TAU / 20
                else:
                    yaw = 0.55 * _smooth((t - 0.22) / 0.14) * (1 - _smooth((t - 0.66) / 0.14))
                a = 0.26 * _smooth(t / 0.18) * (1 - _smooth((t - 0.82) / 0.18))
                b = 0.14 * _smooth((t - 0.40) / 0.10) * (1 - _smooth((t - 0.54) / 0.10))
                distance = 1.35 * yaw if clip == 'drive-circle' else a + b
                q[left] = distance + gauge * yaw / 2
                q[right] = distance - gauge * yaw / 2
                if clip == 'drive-circle':
                    off = Vector((1.35 * math.sin(yaw), 1.35 * (1 - math.cos(yaw)), 0.0))
                else:
                    off = Vector((a + b * math.cos(yaw), b * math.sin(yaw), 0.0))
                loc, rot, sc = _three_split(base.matrix_basis)
                base.matrix_basis = Matrix.LocRotScale(loc + off, rot @ Quaternion((0, 0, 1), yaw), sc)
            self.track_travel(q)
            return self
        q = {}
        if self.entry.get('family') == 'humanoid_modules':
            table = {'leg_hip': -0.4 * curl, 'leg_knee': 0.8 * curl, 'leg_ankle': -0.4 * curl,
                     'pelvis_left_yaw': 0.15 * s, 'pelvis_right_yaw': -0.15 * s,
                     'pelvis_left_roll': 0.1 * s, 'pelvis_right_roll': -0.1 * s}
            for n in names:
                v = table.get(_suffix(n))
                if v is not None:
                    q[n] = v
        cfg = (report.get('mobile') or {}).get('configuration_limits') or {}
        for n in names:
            sid = _suffix(n)
            limit = cfg.get(n) if cfg.get(n) is not None else specs[n].get('limits')
            drone = n.startswith('drone_')
            arm = {'m360_yaw': 0.25 * s, 'm360_shoulder_pitch': -0.22 + 0.15 * s, 'm360_upper_roll': 0.15 * s,
                   'm360_elbow_pitch': 0.2 * s if drone else 0.65 + 0.25 * s, 'm360_forearm_roll': 0.18 * s,
                   'm360_wrist_pitch': -0.3 + 0.15 * s if drone else -0.2 + 0.1 * math.cos(t * TAU),
                   'm360_wrist_roll': 0.4 * s}
            v = arm.get(sid)
            if v is None:
                v = {'camera_pan': 0.65 * s, 'camera_tilt': 0.18 * s, 'display_pan': 0.5 * s, 'display_tilt': 0.16 * s,
                     'antenna_hinge': 0.4 * curl, 'linear_carriage': 0.08 * s,
                     'linear_screw': -0.08 * s / 0.007384615 * TAU, 'rotary_output': 0.5 * s}.get(sid)
            if v is not None:
                q[n] = _clamp(v, limit[0], limit[1]) if limit else v
        if self.ik is not None:
            self.joints(solvers.articulated_demo(t))
        if self.scara is not None:
            self.scara_joints(self.scara.demo(t))
        if self.machine is not None:
            tool = self.machine.get('tool') or ''
            xyz = solvers.gantry_demo(t, 'extruder' if tool.startswith('extruder') else 'spindle',
                                      self.machine.get('tool_tip_rest_z_m'))
            self.axes([_clamp(v, *self.machine['axis_limits'][i]) for i, v in enumerate(xyz)])
        if report.get('novel'):
            for n, d in report['novel']['drives'].items():
                if n in roots:
                    q[n] = _clamp(d['angle'] + (0.08 * s if ('m360_yaw' in n or 'elbow_pitch' in n) else 0.0),
                                  d['limits'][0] + 0.005, d['limits'][1] - 0.005)
        self.set_joints(q)
        self.grasp(curl)
        self.jaw_gap(0.044 * curl)
        return self

    # ------------------------------------------------------------------------------------------------ keys
    def motion_objects(self):
        """the objects a sample can move: the robot's own nodes and its track shoes (never an attached robot)"""
        return [o for o in self.objects if o.name in bpy.data.objects] + \
            [o for o in self.extra_objects if o.name in bpy.data.objects and o.get('track_shoe')]

    def _modifier_slots(self):
        """every numeric input of a Geometry Nodes modifier on this robot's objects and the parts registered at load
        (the fabrication port's live filament and PTFE tubes are curves driven by such inputs): (object, slot, path)"""
        out = []
        objs = [o for o in self.objects + self.extra_objects if o.name in bpy.data.objects]
        for o in objs:
            for mod in o.modifiers:
                if mod.type != 'NODES' or mod.node_group is None:
                    continue
                inputs = getattr(getattr(mod, 'properties', None), 'inputs', None)
                if inputs is None:
                    continue
                for item in mod.node_group.interface.items_tree:
                    if getattr(item, 'in_out', None) != 'INPUT':
                        continue
                    s = getattr(inputs, item.identifier, None)
                    if s is None or not hasattr(s, 'value'):
                        continue
                    v = s.value
                    if not (isinstance(v, (int, float)) or (hasattr(v, '__len__') and all(
                            isinstance(x, (int, float)) for x in v))):
                        continue
                    out.append((o, s, s.path_from_id('value')))
        return out

    def play(self, clip=None, speed=1.0, start=0.0, frame_start=None, frame_end=None, scene=None):
        """key `clip` at every frame of the range: t = max(0, (seconds since the scene's first frame - start) * speed).
        One action holds the robot's moving objects (a slot each), LINEAR keys; objects the clip never moves are left
        unkeyed at the pose the sample gives them. Geometry Nodes inputs the clip changes on the robot's objects and
        registered parts (the live filament's strand for 'filament-feed') are keyed in the same action, so the saved
        file plays everything the sample moves. Returns {'clip', 'action', 'objects', 'frames', 'inputs'}."""
        from bpy_extras import anim_utils
        clip = clip or self.clips[0]
        scene = scene or bpy.context.scene
        fps = scene.render.fps / scene.render.fps_base
        f0 = scene.frame_start if frame_start is None else int(frame_start)
        f1 = scene.frame_end if frame_end is None else int(frame_end)
        self.stop()
        objs = self.motion_objects()
        for o in objs:
            o.rotation_mode = 'QUATERNION'
        slots = self._modifier_slots()
        series = {o.name: [] for o in objs}
        inputs = [[] for _ in slots]

        def read(v):
            return tuple(float(x) for x in v) if hasattr(v, '__len__') else (float(v),)
        for f in range(f0, f1 + 1):
            t = (f - scene.frame_start) / fps
            self.sample(clip, max(0.0, (t - start) * speed))
            for o in objs:
                series[o.name].append((o.location.copy(), o.rotation_quaternion.copy(), o.scale.copy()))
            for i, (_o, s, _p) in enumerate(slots):
                inputs[i].append(read(s.value))
        moving = []
        for o in objs:
            sr = series[o.name]
            a = sr[0]
            if any((b[0] - a[0]).length > 1e-7 or (b[2] - a[2]).length > 1e-7
                   or min(max(abs(x - y) for x, y in zip(b[1], a[1])), max(abs(x + y) for x, y in zip(b[1], a[1]))) > 1e-6
                   for b in sr[1:]):
                moving.append(o)
        changing = [i for i, vals in enumerate(inputs)
                    if any(max(abs(x - y) for x, y in zip(v, vals[0])) > 1e-9 for v in vals[1:])]
        act = bpy.data.actions.new(f'{self.group.name}|{clip}')
        frames = list(range(f0, f1 + 1))
        bags = {}

        def bag(o):
            if o.name not in bags:
                ad = o.animation_data or o.animation_data_create()
                slot = act.slots.new(id_type='OBJECT', name=o.name)
                ad.action = act
                ad.action_slot = slot
                bags[o.name] = anim_utils.action_ensure_channelbag_for_slot(act, slot)
            return bags[o.name]

        def curve(cb, path, idx, group, vals):
            fc = cb.fcurves.new(path, index=idx, group_name=group)
            fc.keyframe_points.add(len(frames))
            fc.keyframe_points.foreach_set('co', [c for f, v in zip(frames, vals) for c in (f, v)])
            fc.keyframe_points.foreach_set('interpolation', [1] * len(frames))       # LINEAR
            fc.update()
        for o in moving:
            sr = series[o.name]
            for i in range(1, len(sr)):                          # quaternion sign continuity
                if sr[i][1].dot(sr[i - 1][1]) < 0:
                    sr[i] = (sr[i][0], -sr[i][1], sr[i][2])
            o.rotation_quaternion = sr[-1][1]                    # the unkeyed components agree with the keyed sign
            cb = bag(o)
            for path, k, n in (('location', 0, 3), ('rotation_quaternion', 1, 4), ('scale', 2, 3)):
                for idx in range(n):
                    vals = [v[k][idx] for v in sr]
                    if max(vals) - min(vals) <= 1e-9:        # a channel the clip never changes keeps its value unkeyed
                        continue
                    curve(cb, path, idx, o.name, vals)
        keyed_inputs = []
        for i in changing:
            o, s, path = slots[i]
            vals = inputs[i]
            cb = bag(o)
            vector = hasattr(s.value, '__len__')
            for idx in range(len(vals[0])):
                comp = [v[idx] for v in vals]
                if max(comp) - min(comp) <= 1e-12:
                    continue
                if vector:
                    curve(cb, path, idx, o.name, comp)
                else:
                    curve(cb, path, 0, o.name, comp)
            keyed_inputs.append(f'{o.name}:{path}')
        names = [o.name for o in moving] + [n for n in bags if n not in {o.name for o in moving}]
        self._played = {'clip': clip, 'action': act, 'objects': names, 'frames': (f0, f1),
                        'speed': speed, 'start': start, 'inputs': keyed_inputs}
        return dict(self._played, objects=list(self._played['objects']), inputs=list(keyed_inputs))

    def stop(self):
        """remove the keys play() made (the WebGPU stop() unregisters the engine clock)"""
        p = getattr(self, '_played', None)
        if not p:
            return self
        act = p['action']
        for name in p['objects']:
            o = bpy.data.objects.get(name)
            if o is not None and o.animation_data is not None and o.animation_data.action == act:
                o.animation_data.action = None
        if act.name in bpy.data.actions and act.users == 0:
            bpy.data.actions.remove(act)
        self._played = None
        return self
