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
seek(seconds) poses everything at a playback time (duration maps it onto the physical program); key(frame, rate) keys
that pose and writes the stock's field for the frame; play(start, speed) seeks and keys every frame of the range (what
the WebGPU play() did on the engine clock); stop() removes the job's keys and holds the stock as it is; dispose()
removes everything the job made. Spindle rotation and chip flight run on the physical clock even in a time lapse.

THE SHUTTER. A time-lapse frame is seconds of program after the one before it, so keys at whole frames alone would
make motion blur sample the straight line between two poses that far apart: the gantry ghosting across centimetres,
the chuck swinging through an index. key() therefore brackets each frame's exposure with sub-frame keys
(shutter_offsets: 31/64 of a frame each side for the CENTER shutter, 31/32 after START or before END), posing the
machine at the physical times a real camera's exposure would see: the frame's moment plus offset / fps seconds,
times rate capped at 1 (rate: program seconds per film second around the frame; 0 holds the pose; below 1, slow
motion, the exposure shortens with it). Any shutter up to 31/32 of a frame then blurs only real motion. The spindle
and the chips hold their frame's state through the bracket: 18,000 rpm turns 6 times in a 1/48 s exposure, more than
any motion-blur step count resolves, and the chips' pool renumbers its instances as chips are born and die, so their
motion vectors would join unrelated chips. The stock shows its frame's file through the whole bracket (stock.py).

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
SHUTTER_SPAN = 31 / 64                          # f +- 31/64 is exact in float32 below frame 131,072: keys land as asked


def shutter_offsets(scene=None):
    """(before, after): the sub-frame offsets of the keys that bracket each keyed frame's exposure, for the scene's
    motion-blur shutter position: CENTER (-31/64, +31/64), START (0, +31/32), END (-31/32, 0). Any shutter up to 31/32
    of a frame then samples only the bracket."""
    import bpy
    pos = getattr((scene or bpy.context.scene).render, 'motion_blur_position', 'CENTER')
    if pos == 'START':
        return 0.0, 2 * SHUTTER_SPAN
    if pos == 'END':
        return -2 * SHUTTER_SPAN, 0.0
    return -SHUTTER_SPAN, SHUTTER_SPAN


def cut_offset(scene=None):
    """Where to key a camera cut (CONSTANT) before a frame: midway between the brackets of that frame and the one
    before it, so no shutter sees both shots (-1/2 for CENTER)."""
    lo, hi = shutter_offsets(scene)
    return lo - (1.0 - (hi - lo)) / 2


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
        object.__setattr__(self, '_physical', None)

    __slots__ = ('_on_done', '_called', '_keyed', '_physical')

    # ---------------------------------------------------------------------------------------------- the pose ---
    def _pose(self, physical_time):
        """The machine alone at a physical time (clamped to the program): the cutter tip and the A axis. The stock,
        the spindle and the chips are left as they are. Returns (sample, tip over the bed)."""
        s, path = self.settings, self.path
        state = path.sample(min(max(float(physical_time), 0.0), path.duration))
        p = (state['position'][0] + s['axis_x'], state['position'][1], state['position'][2] + s['axis_height'])
        self.machine.move_tool(p)
        self.machine.set_joints({'rotary_output': state['angle'], 'rotary_chuck': state['angle']})
        return state, p

    def seek(self, seconds):
        """Pose the job at a playback time (clamped to 0..duration): the cutter tip and A axis from the program, the
        stock field to that moment, the chips' clock and the spindle on the physical clock. Returns the state."""
        if not (isinstance(seconds, (int, float)) and math.isfinite(seconds)):
            raise ValueError('Job time must be finite')
        from ..machine import spin
        s, path, machine = self.settings, self.path, self.machine
        t = min(max(float(seconds), 0.0), self.duration)
        state, p = self._pose(t / self.duration * path.duration)
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

    def _key_channels(self, frame):
        for target, path, n in self._channels():
            if path == 'rotation_quaternion':
                q = target.rotation_quaternion
                prev = self._keyed.get((target.name, path))
                if prev is not None and q.dot(prev) < 0:
                    target.rotation_quaternion = -q
                self._keyed[(target.name, path)] = target.rotation_quaternion.copy()
            target.keyframe_insert(path, frame=frame)
            _linear_at(target, path, frame)

    def key(self, frame=None, rate=1.0, scene=None):
        """Key the current pose (the last seek) at `frame` (the scene's current frame by default), LINEAR, with the
        frame's exposure bracketed (the module docstring, THE SHUTTER): the machine at the physical moments the
        shutter would see, the spindle and the chips held; then write the stock's field for the frame.
        rate: program seconds per film second around this frame (clock_rate() measures it from a playback clock);
        capped at 1, so a time lapse exposes like a real-time camera; 0 for a held frame."""
        import bpy
        if not (isinstance(rate, (int, float)) and math.isfinite(rate) and rate >= 0):
            raise ValueError('Key rate must be a finite number >= 0')
        sc = scene or bpy.context.scene
        frame = sc.frame_current if frame is None else int(frame)
        fps = sc.render.fps / sc.render.fps_base
        r = min(1.0, float(rate))
        t0 = self.state['physical_time']
        lo, hi = shutter_offsets(sc)
        for df in sorted({lo, 0.0, hi}):
            self._pose(t0 + df / fps * r)
            self._key_channels(frame + df)
        self._pose(t0)
        self.stock.write_frame(frame)
        return self

    def clock_rate(self, clock, t, dt=1e-3):
        """Program seconds per film second at film time t of a playback clock (film seconds -> job seconds, as given
        to seek): the rate key() takes, the faster of the two sides, so a clock that starts or stops at this frame
        still exposes its moving side (the held side clamps to the program's ends). Holds measure 0; a jump in the
        clock measures more than 1, which key() caps."""
        def physical(x):
            return min(max(float(clock(x)), 0.0), self.duration) / self.duration * self.physical_duration
        p = physical(t)
        return max(0.0, (physical(t + dt) - p) / dt, (p - physical(t - dt)) / dt)

    def play(self, start=0.0, speed=1.0, frame_start=None, frame_end=None, scene=None, frames=None):
        """The WebGPU play(): every frame of the range (or the given frames) seeks t = (seconds since frame_start -
        start) * speed and keys it, its shutter bracketed at that clock's rate. Returns the job."""
        import bpy
        sc = scene or bpy.context.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        self.stop()

        def clock(x):
            return max(0.0, (x - start) * speed)

        for f in (range(fs, fe + 1) if frames is None else sorted(int(v) for v in frames)):
            t = (f - fs) / fps
            self.seek(clock(t))
            self.key(f, rate=self.clock_rate(clock, t), scene=sc)
        return self

    def key_events(self, frame_start=None, scene=None, stock=(0.0, 0.0)):
        """Key the job at its program's events instead of every frame (eidoblend.fabrication.physical): the gantry
        and the A axis as the machine's joint sliders with Bezier keys exact between events (an index's smoothstep
        included), the screws, the spindle and the chips' clock as drivers (the spindle and the chips hold their
        frame's state through the shutter, as key() holds them). A job made without a duration plays at its own
        physical speed, however long. The carved stock is a file per frame, so it is written for the playback
        seconds `stock` (start, end) only (write_stock; the default: the first frame). -> self"""
        from .. import physical
        import bpy
        sc = scene or bpy.context.scene
        physical.key_job(self, frame_start, sc)
        self.write_stock(stock[0], stock[1], scene=sc)
        return self

    def write_stock(self, start, end, scene=None):
        """The carved stock's files for the frames of playback seconds start .. end, on the frames key_events keyed
        (from the scene's start without it): each frame's field, one VDB file a frame. The stock then plays that
        stretch alone and holds its nearer end on every frame around it (stock.show_frames). Returns the frames
        written."""
        import bpy
        sc = scene or bpy.context.scene
        fps = sc.render.fps / sc.render.fps_base
        f0 = (self._physical or {}).get('frame_start', sc.frame_start)
        a = max(0.0, min(float(start), float(end), self.duration))
        b = min(self.duration, max(float(start), float(end)))
        frames = list(range(int(math.floor(f0 + a * fps + 1e-6)), int(math.floor(f0 + b * fps + 1e-6)) + 1))
        keep = self.time
        for f in frames:
            self.seek((f - f0) / fps)
            self.stock.write_frame(f)
        self.seek(keep)
        if frames:
            self.stock.show_frames(frames[0], frames[-1])
        return frames

    def stop(self):
        """Remove the job's keys (what play(), key() and key_events() made); the machine and the stock stay as they
        are."""
        from .. import physical
        from .._keys import clear
        physical.unrig(self)
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
    """Blender's keyframe_insert ignores the default interpolation: set the keys just made at `frame` (a sub-frame
    too) LINEAR."""
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
            if abs(kp.co.x - frame) < 1e-4:
                kp.interpolation = 'LINEAR'
                break
            if kp.co.x < frame:
                break
