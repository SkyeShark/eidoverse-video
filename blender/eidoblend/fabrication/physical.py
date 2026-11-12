"""eidoblend.fabrication.physical: a fabrication job keyed at its program's events instead of at every frame, so it
plays at its own physical speed however long it is (the WebGPU inspector's process timing 'physical').

A time lapse keys every frame (Job.key, RotaryJob.play). At the program's own speed the relief carve runs 7.8 hours,
675,637 frames at 24 fps. Between two events of a program, though, every axis moves as a polynomial of degree three
or less in time: a feed accelerates at a constant rate (a quadratic), cruises (a line) and brakes (a quadratic); an
index turn eases by a smoothstep (a cubic). A Bezier key at each event, its handles a third of the way to its
neighbours along the exact velocity there (_keys.write_hermite), reproduces that motion exactly between the keys, at
every frame and sub-frame. So the keys count the program's events, not its frames:

    the axes      the machine's joint sliders (eidoblend.characters.robotics.rig: custom properties on the robot's
                  empty that move the modules through SIMPLE-EXPRESSION drivers): gantry X / Y / Z and the rotary
                  A axis, keyed at the events
    followers     the lead screws turn with their axis' slider, the spindle and the cooling fans at their rpm with
                  the frame (drivers; nothing keyed). On the rotary machine the spindle and the chips hold their
                  frame's state through the shutter, as RotaryJob.key keys them
    the process   the job's Progress (its distance along the path, which the bead's or the stock's nodes read) keyed at
                  the same events; the chips' clock (physical time) keyed at the two ends
    the filament  (a print) the reel, the live strand and the feed tubes, keyed LINEAR at the events at most one every
                  FILAMENT_FRAMES frames (the strand and tubes are shaped in Python; they bend slowly)
    the stock     (the rotary machine) one VDB file per frame of a window (RotaryJob.write_stock): its field is
                  written per frame, about 0.1 s and 0.6 to 1.7 MB at the default 256 x 96 x 96, so a whole
                  38-minute carve would be 54,781 files, about 73 GB

    events(path)                          the program's event times (seconds of physical time, sorted)
    event_count(job)                      how many there are (the inspector's MAX_PROGRAM_EVENTS counts these)
    event_frames(job, times, f0, fps)     their frames and which of them stay (keys store float32 frames: events
                                          closer than that merge, the last one always kept)
    key_job(job, frame_start, scene)      Job.key_events / RotaryJob.key_events
    unrig(job)                            what key_job made, removed (Job.stop / RotaryJob.stop call it)

Saved, the .blend plays the job on its own: every driver is a simple expression and evaluates without Python.
"""

from __future__ import annotations

import math

import numpy as np

from . import _keys
from ._nodes import modifier_input

TAU = math.pi * 2
LAST_FRAME = 1_048_574          # Blender's last frame (Scene.frame_end's hard maximum)
FILAMENT_FRAMES = 4             # a print's filament keys: at most one every this many frames
AXES = ('gantry_x', 'gantry_y', 'gantry_z')
SLIDER = 'joint:'               # the kit's slider prefix (rig.PREFIX)


def events(path):
    """The program's event times in seconds of physical time, sorted and unique: each move's start, the ends of its
    acceleration and cruise, its end (an index turn: its start and end); a print's retraction and prime dwells."""
    t = []
    for g in path.segments:
        t0 = float(g['t0'])
        t.append(t0)
        if 'ta' in g and g.get('type') != 'index':
            t += [t0 + g['ta'], t0 + g['ta'] + g['tc']]
        t.append(float(g['t1']))
    for s in getattr(path, 'spans', None) or ():
        t += [s.t0, s.t1]
    return np.unique(np.clip(np.asarray(t, dtype=np.float64), 0.0, path.duration))


def frames_per_second_of_program(job, fps):
    """Frames per physical second: fps at the job's own speed, fewer in a time lapse."""
    return fps * job.duration / job.physical_duration


def event_frames(job, times, frame_start, fps):
    """(frames, keep): each event's frame (float64) and the mask of the events keyed. Keys store their frames as
    float32, so two events closer than that step (1/16 frame near frame 675,000) share a key; the last event is
    always kept, so the job ends where it ends."""
    f = frame_start + np.asarray(times, dtype=np.float64) * frames_per_second_of_program(job, fps)
    f32 = f.astype(np.float32)
    keep = np.zeros(len(f), dtype=bool)
    last, kept = -np.inf, -1
    for i, x in enumerate(f32):
        if x > last:
            keep[i], last, kept = True, x, i
    if len(f) and not keep[-1]:
        keep[kept], keep[-1] = False, True
    return f, keep


def event_count(job):
    """How many events key_job keys (the inspector's limit counts these)."""
    return int(len(events(job.path)))


# ------------------------------------------------------------------------------------------------- the rig ---

def _num(x):
    from ..characters.robotics.rig import _num as num
    return num(x)


def _axis_relations(robot, to_axes, p0):
    """{joint: (axis index, scale, offset)} for every joint the kit's axes() moves, measured from the kit itself: the
    joint's value is offset + scale * q[axis] for the machine travel q (the gantry joints with scale 1, the lead screws
    with their turns per metre). p0 is a tool position inside the travel."""
    q0 = list(to_axes(p0))
    lim = robot.machine['axis_limits'] if isinstance(robot.machine, dict) else robot.machine.axis_limits
    robot.axes(q0)
    base = dict(robot.state)
    out = {}
    for i in range(3):
        d = 1e-3 if q0[i] + 1e-3 <= lim[i][1] else -1e-3
        q = list(q0)
        q[i] += d
        robot.axes(q)
        for n, v in robot.state.items():
            if n in base and isinstance(v, (int, float)) and abs(v - base[n]) > 1e-12:
                k = (v - base[n]) / d
                if n in out and out[n][0] != i:
                    raise RuntimeError(f'{n} moves with more than one machine axis: no single slider drives it')
                out[n] = (i, k, base[n] - k * q0[i])
    robot.axes(q0)
    return out


def _rig(job, robot, rel, f0, k, rotors, hold, a_axis_range=None):
    """The physical rig: sliders for the axes (and the A axis), followers driven from them or from the frame.
    Returns {'sliders': {joint: property}, 'driven': [(object, data path)]}."""
    from ..characters.robotics import rig as R
    g = robot.group
    sliders, made = {}, {}
    for n in AXES:
        if n not in rel:
            continue
        prop = SLIDER + n
        lo, hi = robot.specs[n].get('limits') or (-1e9, 1e9)
        g[prop] = float(robot.state.get(n, 0.0))
        g.id_properties_ui(prop).update(min=lo, max=hi, soft_min=lo, soft_max=hi, step=0.01,
                                        description=f'{n} (prismatic, m), keyed at the program events')
        R.drive_module(robot, n, prop)
        sliders[n] = prop
        made[n] = prop
    for n, (i, s, off) in rel.items():
        if n in sliders:
            continue
        axis = AXES[i]
        _ai, sa, oa = rel[axis]
        # follower = off + s q_i, the slider holds oa + sa q_i: follower = off + (s / sa) (slider - oa)
        R.drive_module(robot, n, sliders[axis], f'{_num(off)} + {_num(s / sa)} * (q - {_num(oa)})')
        made[n] = None
    if a_axis_range is not None and 'rotary_output' in robot.roots:
        prop = SLIDER + 'A axis / chuck'
        lo, hi = a_axis_range
        g[prop] = float(robot.state.get('rotary_output', 0.0))
        g.id_properties_ui(prop).update(min=lo - 1.0, max=hi + 1.0, soft_min=lo - 1.0, soft_max=hi + 1.0, step=1,
                                        description='the A axis and the chuck (rad), keyed at the program events')
        for t in ['rotary_output'] + (['rotary_chuck'] if 'rotary_chuck' in robot.roots else []):
            R.drive_module(robot, t, prop)
        made['rotary_output'] = prop
    frame = f'floor(frame + {_num(hold)})' if hold is not None else 'frame'
    for n, rpm in rotors.items():
        R.drive_module(robot, n, None, f'({frame} - {_num(f0)}) * {_num(rpm / 60 * TAU / k)}')
        made[n] = None
    robot.joint_sliders = made
    return {'sliders': made}


def _hermite(target, path, frames, values, slopes):
    _keys.write_hermite(target, path, frames, values, slopes)


def _slider_keys(robot, rel, frames, k, q, dq):
    """the axis sliders keyed: values at the events (the joint's value), slopes per frame"""
    keyed = []
    for i, n in enumerate(AXES):
        if n not in rel:
            continue
        _ai, s, off = rel[n]
        path = f'["{SLIDER}{n}"]'
        _hermite(robot.group, path, frames, off + s * q[:, i], s * dq[:, i] / k)
        keyed.append(path)
    return keyed


def _jacobian(to_axes, p):
    a = np.asarray(to_axes(p), dtype=np.float64)
    J = np.zeros((3, 3))
    for j in range(3):
        e = list(p)
        e[j] += 1e-3
        J[:, j] = (np.asarray(to_axes(e), dtype=np.float64) - a) / 1e-3
    return J


def _to_axes(robot):
    m = robot.machine
    return m['to_axes'] if isinstance(m, dict) else m.to_axes


# ------------------------------------------------------------------------------------------------ keying ---

def key_job(job, frame_start=None, scene=None):
    """Key `job` (a fabrication Job or a RotaryJob) at its program's events from frame_start (the scene's start by
    default), playback time mapped onto the program as job.seek maps it. Removes what an earlier keying made.
    Returns the job, with job.event_keys = {'events', 'keys', 'frames': (first, last)}."""
    import bpy
    sc = scene or bpy.context.scene
    f0 = sc.frame_start if frame_start is None else int(frame_start)
    fps = sc.render.fps / sc.render.fps_base
    job.stop()
    robot = job.machine
    rotary = hasattr(job, 'stock') and 'rotary_chuck' in robot.roots
    path = job.path
    times = events(path)
    frames, keep = event_frames(job, times, f0, fps)
    if frames[-1] > LAST_FRAME:
        raise ValueError(f'the job ends at frame {frames[-1]:,.0f}, past Blender\'s last frame {LAST_FRAME:,}: '
                         f'key it at {math.floor((LAST_FRAME - f0) / (frames[-1] - f0) * fps)} fps or fewer')
    times, frames = times[keep], frames[keep]
    k = frames_per_second_of_program(job, fps)
    to_axes = _to_axes(robot)
    states = [path.sample(float(t)) for t in times]
    if rotary:
        s = job.settings
        off = np.array([s['axis_x'], 0.0, s['axis_height']])
        pos = np.array([st['position'] for st in states], dtype=np.float64) + off
        vel = np.zeros_like(pos)
        for i, st in enumerate(states):
            g = path.segments[st['index']]
            if g['type'] != 'index':
                vel[i] = np.asarray(g['d']) * st['speed']
        angles = np.array([st['angle'] for st in states], dtype=np.float64)
    else:
        pos = np.array([st.position for st in states], dtype=np.float64)
        vel = np.array([st.velocity for st in states], dtype=np.float64)
    q = np.array([to_axes(p) for p in pos], dtype=np.float64)
    dq = vel @ _jacobian(to_axes, pos[0]).T
    rel = _axis_relations(robot, to_axes, tuple(pos[0]))
    if rotary:
        from .rotary.carve import shutter_offsets
        lo, _hi = shutter_offsets(sc)
        hold = 1e-4 - lo
        rotors = {'spindle_rotor': job.settings['rpm']} if 'spindle_rotor' in robot.roots else {}
        rig = _rig(job, robot, rel, f0, k, rotors, hold, (float(angles.min()), float(angles.max())))
    else:
        rotors = {'spindle_rotor': job.options.get('rpm', 1800)} if 'spindle_rotor' in robot.roots else {}
        if 'filament_length' in (job.state or {}):
            for n in robot.roots:
                if n.split(' / ')[-1] == 'extruder_fan':
                    rotors[n] = job.options.get('fan_rpm', 4800)
        rig = _rig(job, robot, rel, f0, k, rotors, None)
    span = (float(frames[0]), float(frames[-1]))
    keyed = [(robot.group, tuple(_slider_keys(robot, rel, frames, k, q, dq)), span)]
    n_keys = len(frames) * len(keyed[0][1])
    if rotary:
        path_a = f'["{SLIDER}A axis / chuck"]'
        _hermite(robot.group, path_a, frames, angles, np.zeros(len(frames)))     # an index eases: zero slope ends
        keyed[0] = (robot.group, keyed[0][1] + (path_a,), span)
        n_keys += len(frames)
        driven = _hold_chips(job, f0, k, hold)
    else:
        slot = modifier_input(job.mesh.modifiers['fabrication'], 'Progress')
        dist = np.array([st.distance for st in states], dtype=np.float64)
        speed = np.array([st.speed for st in states], dtype=np.float64)
        _hermite(slot, 'value', frames, dist, speed / k)
        keyed.append((slot.id_data, (slot.path_from_id('value'),), span))
        n_keys += len(frames)
        if job.effects is not None:
            for p in job.effects.pools:
                s = modifier_input(p.modifier, 'Time')
                _keys.write(s, 'value', [frames[0], frames[-1]], [times[0], times[-1]])
                keyed.append((s.id_data, (s.path_from_id('value'),), span))
                n_keys += 2
        driven = []
        if 'filament_length' in (job.state or {}):
            n_keys += _key_filament(job, times, frames, keyed, span)
    rig['driven'] = driven
    rig['keyed'] = keyed
    rig['frame_start'] = f0
    _store(job, rig)
    bpy.context.view_layer.update()
    job.event_keys = {'events': int(len(frames)), 'keys': int(n_keys), 'frames': span}
    return job


def _hold_chips(job, f0, k, hold):
    """the rotary chips' clock as a driver: their frame's physical time, held through the shutter"""
    out = []
    end = job.physical_duration
    for p in job.debris.pools:
        s = modifier_input(p.modifier, 'Time')
        ob = s.id_data
        dp = s.path_from_id('value')
        fc = ob.driver_add(dp)
        d = fc.driver
        d.type = 'SCRIPTED'
        for v in list(d.variables):
            d.variables.remove(v)
        d.expression = f'min({_num(end)}, max(0, (floor(frame + {_num(hold)}) - {_num(f0)}) / {_num(k)}))'
        if not d.is_simple_expression:
            raise RuntimeError('the chips\' clock driver is not a simple expression: ' + d.expression)
        out.append((ob, dp))
    return out


def _key_filament(job, times, frames, keyed, span):
    """a print's reel, live strand and feed tubes: posed by job.seek at the events, at most one every FILAMENT_FRAMES
    frames (the first and last always), keyed LINEAR; a channel that never changes is set, not keyed"""
    robot = job.machine
    pick, last = [], -np.inf
    for i, f in enumerate(frames):
        if f - last >= FILAMENT_FRAMES or i == len(frames) - 1:
            pick.append(i)
            last = f
    slots = None
    reel = robot.roots.get('filament_reel')
    rows, rot = [], []
    for i in pick:
        job.seek(float(times[i]) * job.duration / job.physical_duration)
        fil = robot.filament
        if slots is None:
            slots = [modifier_input(c.modifier, n) for c in fil.curves for n in ('P0', 'P1', 'P2', 'P3', 'N0')]
        rows.append([tuple(s.value) for s in slots])
        if reel is not None:
            rot.append(tuple(reel.rotation_quaternion) if reel.rotation_mode == 'QUATERNION'
                       else tuple(reel.matrix_basis.to_quaternion()))
    fr = frames[pick]
    n = 0
    for j, s in enumerate(slots or ()):
        v = np.array([r[j] for r in rows], dtype=np.float64)
        if np.ptp(v, axis=0).max() < 1e-9:
            continue
        _keys.write(s, 'value', fr, v)
        keyed.append((s.id_data, (s.path_from_id('value'),), span))
        n += v.size
    if reel is not None and rot:
        reel.rotation_mode = 'QUATERNION'
        before = _keys.value_before(reel, 'rotation_quaternion', fr[0], 4)
        qs = _keys.quaternions_continuous(rot, before)
        if np.ptp(qs, axis=0).max() > 1e-9:
            _keys.write(reel, 'rotation_quaternion', fr, qs)
            keyed.append((reel, ('rotation_quaternion',), span))
            n += qs.size
    return n


def _store(job, rig):
    """the job's record of its physical keying (a RotaryJob keeps it in a slot, out of its dict)"""
    if '_physical' in getattr(type(job), '__slots__', ()):
        object.__setattr__(job, '_physical', rig)
    else:
        job._physical = rig


def unrig(job):
    """Remove what key_job made: the keys (in the frame range it keyed), the sliders and the followers' drivers, the
    chips' clock drivers. The pose on screen stays."""
    import bpy
    rig = getattr(job, '_physical', None)
    if not rig:
        return False
    from ..characters.robotics import rig as R
    robot = job.machine
    owners = {}
    for idb, paths, span in rig.get('keyed', ()):
        try:
            _keys.clear(idb, paths, frame_range=span)
            owners[idb.as_pointer()] = idb
        except ReferenceError:                      # removed with its robot already
            pass
    for ob, dp in rig.get('driven', ()):
        try:
            ob.driver_remove(dp)
        except (ReferenceError, TypeError):
            pass
    try:
        R.unrig_joints(robot)
    except ReferenceError:
        pass
    for idb in owners.values():
        try:
            _keys.prune(idb)
        except ReferenceError:
            pass
    _store(job, None)
    try:
        bpy.context.view_layer.update()
    except ReferenceError:
        pass
    return True
