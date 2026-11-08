"""Freestanding rotary carving on the G430 XYZ + A assembly: the port of eidoverse/robotics/rotary.js (rotaryCarve).

    from eidoblend.characters.robotics import make_robot
    from eidoblend.fabrication.rotary import rotary_carve, sample_rotary
    machine = make_robot('cnc_rotary', primary='#b9c7c8', accent='#235b68')
    job = rotary_carve(machine, sample_rotary, material='wood', duration=28, cache_dir='//rotary_cache')
    job.seek(14)                       # the machine, the A axis, the spindle, the carved stock, the chips at 14 s
    job.play()                         # keyed at every frame of the scene's range (t = seconds since frame_start)
    job.state['stock_position'], job.state['physical_time'], job.done

rotary_carve validates the whole job before touching the scene (the machine, its installed cutter, the fixture's
datums, the toolpath's axis and end stock, every move's XYZ travel, retracts before every index), then sets the
fixture for the blank (jaws, tailstock, quill), and builds:
    job.mesh       the stock frame: an empty on the chuck, on the A axis at the blank's centre. It turns with the
                   chuck because it is parented to it (the WebGPU poseCallbacks follower).
    job.stock      the carved stock (stock.py): its surface object, its field, its VDB file sequence
    job.removal    the chip events (removal.py), sampled once
    job.debris     the fabrication family's cutting_debris on those events (chips; wood fines too), on the bed
    job.program, job.path, job.settings, job.duration (playback seconds), job.physical_duration
seek(seconds) poses everything at a playback time (duration maps it onto the physical program); key(frame) keys that
pose and writes the stock's field for the frame; play(start, speed) seeks and keys every frame of the range (what the
WebGPU play() did on the engine clock); stop() removes the job's keys and holds the stock as it is; dispose() removes
everything the job made. Spindle rotation and chip flight run on the physical clock even in a time lapse.

Options (the WebGPU names in snake_case): every rotary_program / rotary_mesh_program option, the blank (stock_length,
stock_width, stock_height, quill), tool (must be the installed cutter's kind), duration, resolution (the stock field,
default (256, 96, 96)), color, engagement_resolution (the chip sampling, default (96, 28, 28)), max_particles,
seed, dust, on_done(job), auto_play; Blender's own: cache_dir (the stock's VDB files; '//rotary_stock_cache' beside
the .blend by default), collection. The WebGPU renderer option has no counterpart: nothing renders at build time.
"""

from __future__ import annotations

import math

import numpy as np

from .._axes import Rec
from .path import TAU, rotary_program, sample_rotary
from .removal import rotary_removal
from .setup import rotary_fixture_setup
from .stock import create_rotary_stock

JOINTS_MOVED = ('gantry_x', 'gantry_y', 'gantry_z', 'rotary_output', 'rotary_chuck', 'spindle_rotor')
SETUP_KEYS = ('stock_length', 'stock_width', 'stock_height', 'quill')


def _opt(options, key, default=None):
    v = options.get(key)
    return default if v is None else v


def _machine_controls(machine):
    """The kit's G430 controls (robot.machine, move_tool ...): the fabrication family installs them on a kit that
    lacks them."""
    if getattr(machine, 'machine', None) is None or not callable(getattr(machine, 'move_tool', None)):
        from ..machine import g430
        g430(machine)
    return machine


def _flute(cutter):
    v = cutter.get('flute_length', cutter.get('fluteLength'))
    return v if v is not None else (.018 if cutter.get('kind') == 'flat' else .017)


def rotary_carve(machine, source=sample_rotary, **options):
    """rotaryCarve (see the module docstring): validate, set up the fixture, and return the RotaryJob at time 0."""
    import bpy
    from mathutils import Matrix, Vector
    roots = getattr(machine, 'roots', {}) or {}
    if 'rotary_chuck' not in roots or 'rotary_output' not in roots:
        raise ValueError('Load cnc_rotary for rotary carving')
    _machine_controls(machine)
    cutter = (machine.machine or {}).get('cutter') or {}
    if cutter.get('kind') not in ('flat', 'ball'):
        raise ValueError('Rotary carving requires a fitted flat or ball-nose cutter')
    if not getattr(machine, 'has_rotary_setup', 'rotary_tailstock' in roots and 'rotary_jaw_0' in roots):
        raise ValueError('Load the adjustable rotary fixture')
    setup = rotary_fixture_setup(**{k: options[k] for k in SETUP_KEYS if options.get(k) is not None})
    if options.get('tool') is not None and options['tool'] != cutter['kind']:
        raise ValueError('Requested tool must match the installed cutter')
    program = rotary_program(source, **dict(options, tool=cutter['kind'], flute_length=_flute(cutter)))
    s, path = program.settings, program.path
    duration = _opt(options, 'duration', path.duration)
    if not (isinstance(duration, (int, float)) and math.isfinite(duration) and duration > 0):
        raise ValueError('Invalid job duration')
    if (abs(s['axis_x'] - setup['axis_x']) > 1e-9 or s['axis_height'] != setup['axis_height']
            or s['start'] < setup['start'] - 1e-9 or s['end'] > setup['end'] + 1e-9):
        raise ValueError('Toolpath must retain the calibrated rotary axis and sacrificial end stock')
    if abs(s['radius'] - cutter['radius']) > 1e-9:
        raise ValueError('Cutter radius must match the installed tool')
    m = machine.machine
    rest, bed = m['rest_tip'], m['bed_top']
    pos = np.array([mv['position'] for mv in program.moves], dtype=float)
    q = np.stack([pos[:, 0] + s['axis_x'] - rest[0], pos[:, 1] - rest[1], pos[:, 2] + s['axis_height'] + bed - rest[2]], 1)
    for k in range(3):
        lo, hi = m['axis_limits'][k]
        if (q[:, k] < lo - 1e-7).any() or (q[:, k] > hi + 1e-7).any():
            raise ValueError('Rotary toolpath exceeds ' + 'XYZ'[k] + ' travel')
    clear = math.hypot(s['stock_width'] / 2, s['stock_height'] / 2) + .002
    for mv in program.moves:
        if mv['type'] == 'index' and mv['position'][2] < clear:
            raise ValueError('Retract clear of the rotating stock before indexing')
    # everything else that can refuse the job, before the scene changes: an invalid job leaves nothing behind
    from .stock import _abspath, check_resolution
    resolution = check_resolution(tuple(_opt(options, 'resolution', (256, 96, 96))))
    cache_dir = _abspath(options.get('cache_dir') or '//rotary_stock_cache')
    max_particles = _opt(options, 'max_particles', 1200)
    if not (isinstance(max_particles, int) and not isinstance(max_particles, bool) and 0 <= max_particles <= 50000):
        raise ValueError('maxParticles must be 0..50000')
    removal = rotary_removal(path, s, tuple(_opt(options, 'engagement_resolution', (96, 28, 28))))
    # ---- valid: change the scene
    if callable(getattr(machine, 'rotary_setup', None)):
        machine.rotary_setup(setup['stock_length'], setup['stock_width'], setup['stock_height'], setup['quill'])
    else:
        machine.set_joints(setup['joints'])
    stop = getattr(machine, 'stop', None)
    if callable(stop):
        stop()
    base, chuck = machine.roots['gantry_base'], machine.roots['rotary_chuck']
    collection = options.get('collection') or (base.users_collection[0] if base.users_collection
                                               else bpy.context.scene.collection)
    bpy.context.view_layer.update()
    frame = bpy.data.objects.new('Rotary stock frame', None)
    collection.objects.link(frame)
    frame.empty_display_type = 'ARROWS'
    frame.empty_display_size = .02
    on_axis = base.matrix_world @ Vector((s['axis_x'], 0.0, bed + s['axis_height']))
    frame.parent = chuck
    frame.matrix_parent_inverse.identity()
    frame.matrix_basis = Matrix.Translation(chuck.matrix_world.inverted() @ on_axis)
    stock = create_rotary_stock(path, s, parent=frame, resolution=resolution, color=options.get('color'),
                                cache_dir=cache_dir, collection=collection)
    from ..cutting import cutting_debris, stock_profile
    debris = cutting_debris(removal, stock_profile(s['material']),
                            {'width': s['stock_length'], 'depth': s['stock_width'],
                             'height': s['axis_height'] + s['stock_height'], 'radius': s['radius']},
                            max_particles=max_particles, seed=_opt(options, 'seed', 7319),
                            dust=_opt(options, 'dust', True), parent=base, collection=collection)
    debris.group.location = (0.0, 0.0, bed)
    job = RotaryJob(machine, program, removal, stock, debris, frame, duration, options.get('on_done'))
    job.seek(0)
    if options.get('auto_play'):
        job.play()
    return job


class RotaryJob(Rec):
    """What rotary_carve returns (see the module docstring); a dict that reads its keys as attributes too."""

    def __init__(self, machine, program, removal, stock, debris, frame, duration, on_done=None):
        super().__init__(machine=machine, program=program, path=program.path, stock=stock, mesh=frame,
                         removal=removal, debris=debris, settings=program.settings, duration=float(duration),
                         physical_duration=program.path.duration, time=0.0, state=None, done=False)
        object.__setattr__(self, '_on_done', on_done)
        object.__setattr__(self, '_called', False)
        object.__setattr__(self, '_keyed', {})

    __slots__ = ('_on_done', '_called', '_keyed')

    # ---------------------------------------------------------------------------------------------- the pose ---
    def seek(self, seconds):
        """Pose the job at a playback time (clamped to 0..duration): the cutter tip and A axis from the program, the
        stock field to that moment, the chips' clock and the spindle on the physical clock. Returns the state."""
        if not (isinstance(seconds, (int, float)) and math.isfinite(seconds)):
            raise ValueError('Job time must be finite')
        from ..machine import spin
        s, path, machine = self.settings, self.path, self.machine
        t = min(max(float(seconds), 0.0), self.duration)
        state = path.sample(t / self.duration * path.duration)
        p = (state['position'][0] + s['axis_x'], state['position'][1], state['position'][2] + s['axis_height'])
        machine.move_tool(p)
        machine.set_joints({'rotary_output': state['angle'], 'rotary_chuck': state['angle']})
        self.stock.update(state)
        self.debris.set_time(state['time'])
        spin(machine, 'spindle_rotor', math.fmod(state['time'] * s['rpm'] / 60 * TAU, TAU))
        self['state'] = Rec(state, position=p, stock_position=state['position'], physical_time=state['time'],
                            playback_time=t)
        self['time'] = t
        self['done'] = t >= self.duration
        if not self.done:
            object.__setattr__(self, '_called', False)
        if self.done and not self._called:
            object.__setattr__(self, '_called', True)
            if self._on_done:
                self._on_done(self)
        return self.state

    # ---------------------------------------------------------------------------------------------- the keys ---
    def _moving(self):
        roots = self.machine.roots
        names = [n for n in JOINTS_MOVED if n in roots]
        names += sorted(n for n in roots if n.startswith('gantry_') and 'screw' in n)
        return [roots[n] for n in names]

    def _channels(self):
        out = []
        for ob in self._moving():
            rot = 'rotation_quaternion' if ob.rotation_mode == 'QUATERNION' else 'rotation_euler'
            out.append((ob, 'location', 3))
            out.append((ob, rot, 4 if rot == 'rotation_quaternion' else 3))
        from .._nodes import modifier_input
        for pool in self.debris.pools:
            out.append((modifier_input(pool.modifier, 'Time'), 'value', 1))
        return out

    def key(self, frame=None):
        """Key the current pose at `frame` (the scene's current frame by default): the moving joints, the chips'
        clock, LINEAR; and write the stock's field for that frame."""
        import bpy
        frame = bpy.context.scene.frame_current if frame is None else int(frame)
        for target, path, n in self._channels():
            if path == 'rotation_quaternion':
                q = target.rotation_quaternion
                prev = self._keyed.get((target.name, path))
                if prev is not None and q.dot(prev) < 0:
                    target.rotation_quaternion = -q
                self._keyed[(target.name, path)] = target.rotation_quaternion.copy()
            target.keyframe_insert(path, frame=frame)
            _linear_at(target, path, frame)
        self.stock.write_frame(frame)
        return self

    def play(self, start=0.0, speed=1.0, frame_start=None, frame_end=None, scene=None, frames=None):
        """The WebGPU play(): every frame of the range (or the given frames) seeks t = (seconds since frame_start -
        start) * speed and keys it. Returns the job."""
        import bpy
        sc = scene or bpy.context.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        self.stop()
        for f in (range(fs, fe + 1) if frames is None else sorted(int(v) for v in frames)):
            self.seek(max(0.0, ((f - fs) / fps - start) * speed))
            self.key(f)
        return self

    def stop(self):
        """Remove the job's keys (what play() and key() made); the machine and the stock stay as they are."""
        from .._keys import clear
        for target, path, _n in self._channels():
            idb = getattr(target, 'id_data', None) or target
            try:
                full = target.path_from_id(path)
            except (ValueError, TypeError, AttributeError):
                full = path
            clear(idb, (full,))
        self._keyed.clear()
        if self.stock.frames_written:
            self.stock.hold()
        return self

    def dispose(self, files=False):
        """Remove everything the job made (its keys, chips, stock objects and frame; the cache files with files=True)."""
        import bpy
        self.stop()
        self.debris.dispose()
        self.stock.dispose(files=files)
        if self.mesh is not None and self.mesh.name in bpy.data.objects:
            bpy.data.objects.remove(self.mesh, do_unlink=True)
        self['mesh'] = None


def _linear_at(target, path, frame):
    """Blender's keyframe_insert ignores the default interpolation: set the keys just made at `frame` LINEAR."""
    idb = getattr(target, 'id_data', None) or target
    try:
        full = target.path_from_id(path)
    except (ValueError, TypeError, AttributeError):
        full = path
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if cb is None:
        return
    for fc in cb.fcurves:
        if fc.data_path != full:
            continue
        pts = fc.keyframe_points
        for i in range(len(pts) - 1, -1, -1):
            kp = pts[i]
            if abs(kp.co.x - frame) < 1e-6:
                kp.interpolation = 'LINEAR'
                break
            if kp.co.x < frame:
                break
