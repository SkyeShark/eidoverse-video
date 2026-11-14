"""The inspector's physical process timing (set_timing('physical'): the job at its own speed, however long), keyed at
the program's events (eidoblend.fabrication.physical) instead of every frame:

    pocket mill   20 min, 28,556 frames: the tool tip, the progress, the lead screws and the spindle read off the keyed
                  and driven scene at random times (sub-frames, inside accelerations) against the program itself
    relief        7.8 hours, 675,637 frames (refused before): accepted, keyed in seconds, exact at random times up to
                  its last hour; at 48 fps it would end past Blender's last frame and is refused with the fps that fits
    print         15 min: the bead's progress exact, the reel, the strand and the feed tubes keyed (at most one every
                  FILAMENT_FRAMES frames), the cooling fan driven
    rotary        38 min (refused before): the gantry and the A axis exact (an index turn's smoothstep included), the
                  stock's file written for the frame set_time shows and for the stretch play() plays
    manual mode   a joint slider after physical keying leaves no physical rig behind; Reset keys the events again
    the file      saved and reopened, the job plays from its keys and simple-expression drivers alone

    bash run_blender.sh blender/tests/robotics/test_inspector_physical.py                # no render
    bash run_blender.sh blender/tests/robotics/test_inspector_physical.py -- --render    # + stills
    # the stills: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import math
import os
import random
import shutil
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters.robotics.inspector import inspector_scene  # noqa: E402
from eidoblend.characters.robotics.kit import decompose_three  # noqa: E402
from eidoblend.fabrication import physical  # noqa: E402

OUT = os.path.join(K.OUT, 'inspector_physical')
os.makedirs(OUT, exist_ok=True)
RENDER = '--render' in K.argv()
TAU = 2 * math.pi
rng = random.Random(7)


def at(sc, frame):
    """the scene at a (fractional) frame, evaluated"""
    sc.frame_set(int(math.floor(frame)), subframe=frame - math.floor(frame))
    bpy.context.view_layer.update()


def evaluated_turn(robot, name):
    """a module's turn about its joint axis from rest as the scene shows it (as rig.measure_joints reads it), 0..2 pi"""
    o = robot.roots[name]
    s = robot.specs[name]
    _l0, r0, _s0 = decompose_three(robot.rest[o.name])
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    _l, r, _s = decompose_three(ev.matrix_basis)
    rel = r0.inverted() @ r
    a = 2.0 * math.atan2(Vector((rel.x, rel.y, rel.z)).dot(Vector(s.get('axis') or (0, 0, 1)).normalized()), rel.w)
    return a % TAU


def adiff(a, b):
    d = (a - b) % TAU
    return min(d, TAU - d)


def sample_times(job, n, extra=()):
    """random program times, plus the middle of some accelerations (a quadratic there, a cubic's job to match)"""
    segs = job.path.segments
    ts = [rng.uniform(0, job.physical_duration) for _ in range(n)]
    for g in rng.sample(list(segs), min(n, len(segs))):
        if g.get('ta', 0) > 1e-3:
            ts.append(g['t0'] + g['ta'] * 0.5)
    return sorted(ts + list(extra))


def gantry_case(model, label, n=40, fps=24, extra=()):
    sc = K.clean_scene(fps)
    t0 = time.time()
    insp = inspector_scene(model, scene=sc, fps=fps, resolution=(640, 360))
    insp.set_timing('physical')
    job, r = insp['job'], insp['robot']
    took = time.time() - t0
    ek = job.event_keys
    frames = sc.frame_end - sc.frame_start + 1
    K.check(f"{label}: physical timing accepted: {job.duration:,.0f} s ({job.duration / 3600:.2f} h), {frames:,} "
            f"frames, {ek['events']:,} events keyed ({ek['keys']:,} keys) in {took:.0f} s",
            abs(job.duration - job.physical_duration) < 1e-9 and ek['events'] <= physical.event_count(job)
            and abs(sc.frame_end - (sc.frame_start + round(job.duration * fps))) <= 1)
    slot = job.mesh.modifiers['fabrication']
    from eidoblend.fabrication._nodes import modifier_input
    prog = modifier_input(slot, 'Progress')
    worst_p = worst_d = worst_screw = worst_spin = 0.0
    rpm = job.options.get('rpm', 1800)
    screws = [n for n in r.roots if n.startswith('gantry_') and 'screw' in n]
    import numpy as np
    over = 0.0
    for t in sample_times(job, n, extra):
        f = sc.frame_start + t * fps
        at(sc, f)
        st = job.path.sample(t)
        tip = Vector(r.tool_tip())
        worst_p = max(worst_p, (tip - Vector(st.position)).length)
        d = abs(prog.value - st.distance)                 # keys hold float32 values: the path is up to 800 m long
        worst_d = max(worst_d, d)
        over = max(over, d / max(5e-6, 2 * float(np.spacing(np.float32(st.distance)))))
        q = r.machine['to_axes'](st.position) if isinstance(r.machine, dict) else r.machine.to_axes(st.position)
        for s in screws:
            i = 0 if '_x_' in s else 1 if '_y_' in s else 2
            worst_screw = max(worst_screw, adiff(evaluated_turn(r, s), (q[i] / .008 * TAU) % TAU))
        if 'spindle_rotor' in r.roots:                    # whole frames: Blender's frame time is float32, and at
            whole = round(f)                              # 16,000 rpm a 1/16 frame step near frame 675,000 is 0.7 turns
            at(sc, whole)
            tw = (whole - sc.frame_start) / fps
            worst_spin = max(worst_spin, adiff(evaluated_turn(r, 'spindle_rotor'), (tw * rpm / 60 * TAU) % TAU))
    K.check(f'{label}: the tool tip follows the program exactly between events (worst {worst_p * 1e6:.2f} um at '
            f'{n}+ random times and mid-accelerations)', worst_p < 5e-6)
    K.check(f'{label}: the progress is the distance along the path (worst {worst_d * 1e6:.2f} um, within two float32 '
            'steps of the distance)', over <= 1.0)
    if screws:
        K.check(f'{label}: {len(screws)} lead screws turn with their axis (worst {math.degrees(worst_screw):.3f} deg)',
                worst_screw < math.radians(0.5))
    if 'spindle_rotor' in r.roots:
        K.check(f'{label}: the spindle turns at {rpm:,} rpm on the frame (worst {math.degrees(worst_spin):.4f} deg at '
                'whole frames)', worst_spin < math.radians(0.5))
    drivers = [fc for o in r.roots.values() if o.animation_data for fc in o.animation_data.drivers]
    K.check(f'{label}: every driver is a simple expression ({len(drivers)} drivers)',
            drivers and all(fc.driver.is_simple_expression for fc in drivers))
    return sc, insp


def pocket():
    sc, insp = gantry_case('cnc', 'pocket mill')
    job, r = insp['job'], insp['robot']
    # manual mode after physical keying, then Reset
    insp.set_time(300.0)
    insp.set_joint('gantry_x', 0.05)
    left = [p for p in r.group.keys() if p.startswith('joint:')]
    manual_ok = insp.manual and job._physical is None and sorted(left) == sorted(insp['joints'].values())
    insp.reset()
    K.check('pocket mill: a joint slider after physical keying drops the physical rig (manual sliders only); Reset '
            f"keys the events again ({job.event_keys['events']:,})",
            manual_ok and not insp.manual and job._physical is not None)
    # the file on its own: saved, reopened (no Python objects left), the tool tip read off the evaluated scene
    path = os.path.join(OUT, 'pocket_physical.blend')
    names = (r.roots[r.machine['tool']].name, r.roots['gantry_base'].name)
    bed = r.machine['bed_top']
    times = (777.25, 1031.6)
    want = [Vector(job.path.sample(t).position) for t in times]
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc2 = bpy.context.scene
    worst = 0.0
    for t, w in zip(times, want):
        at(sc2, sc2.frame_start + t * 24)
        tool, base = bpy.data.objects[names[0]], bpy.data.objects[names[1]]
        tip = base.matrix_world.inverted() @ tool.matrix_world.translation - Vector((0, 0, bed))
        worst = max(worst, (tip - w).length)
    K.check(f'pocket mill: saved and reopened, the file plays the program from its keys and drivers alone (worst '
            f'{worst * 1e6:.2f} um at {times} s)', worst < 5e-6)
    os.remove(path)


def relief():
    sc, insp = gantry_case('cnc_relief', 'relief', n=30, extra=(27000.0, 28100.0))
    job = insp['job']
    if RENDER:
        K.probe_render(sc, (960, 540), 16)
        for t in (3 * 3600.0, 6 * 3600.0):
            insp.set_time(t)
            insp.frame_work()
            p = os.path.join(OUT, f'relief_physical_t{int(t)}.png')
            K.check(f'relief at {t / 3600:.0f} h: still', K.still(sc, sc.camera, sc.frame_current, p))
    path = os.path.join(OUT, 'relief_physical.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    mb = os.path.getsize(path) / 1e6
    K.check(f"relief: the keyed file is {mb:.0f} MB ({job.event_keys['keys']:,} keys)", mb < 200)
    os.remove(path)
    # 7.8 hours at 48 fps would end past Blender's last frame: refused, with the fps that fits
    sc = K.clean_scene(48)
    insp = inspector_scene('cnc_relief', scene=sc, fps=48, resolution=(640, 360))
    try:
        insp.set_timing('physical')
        K.check('relief at 48 fps: refused past the last frame', False, 'accepted')
    except ValueError as e:
        K.check(f"relief at 48 fps: refused past Blender's last frame ({str(e)[60:170]}...)",
                "last frame" in str(e) and '37 fps' in str(e))


def print_job():
    sc = K.clean_scene()
    t0 = time.time()
    insp = inspector_scene('fdm', scene=sc, resolution=(640, 360))
    insp.set_timing('physical')
    job, r = insp['job'], insp['robot']
    ek = job.event_keys
    K.check(f"print: physical timing {job.duration:,.0f} s keyed at {ek['events']:,} events ({ek['keys']:,} keys) in "
            f'{time.time() - t0:.0f} s', ek['events'] > 0 and abs(job.duration - job.physical_duration) < 1e-9)
    from eidoblend.fabrication._nodes import modifier_input
    prog = modifier_input(job.mesh.modifiers['fabrication'], 'Progress')
    worst = 0.0
    strand = r.filament.strand
    s_p0 = []
    for t in sample_times(job, 25):
        at(sc, sc.frame_start + t * 24)
        st = job.path.sample(t)
        worst = max(worst, (Vector(r.tool_tip()) - Vector(st.position)).length, abs(prog.value - st.distance))
        s_p0.append(tuple(modifier_input(strand.modifier, 'P0').value))
    K.check(f'print: the nozzle and the bead front follow the program exactly (worst {worst * 1e6:.2f} um)',
            worst < 5e-6)
    reel = r.roots['filament_reel']
    fans = [n for n in r.roots if n.split(' / ')[-1] == 'extruder_fan']
    K.check(f'print: the reel is keyed, the strand pays out ({len(set(s_p0))} strand starts at 25+ times), '
            f'{len(fans)} cooling fan(s) driven',
            reel.animation_data is not None and len(set(s_p0)) > 5
            and all(r.roots[n].animation_data and r.roots[n].animation_data.drivers for n in fans))
    if RENDER:
        K.probe_render(sc, (960, 540), 16)
        insp.set_time(600.0)
        insp.frame_work()
        p = os.path.join(OUT, 'print_physical_t600.png')
        K.check('print at 10 min: still', K.still(sc, sc.camera, sc.frame_current, p))


def rotary():
    cache = os.path.join(OUT, '_rotary_cache')
    shutil.rmtree(cache, ignore_errors=True)
    try:
        sc = K.clean_scene(4)
        opts = {'cache_dir': cache, 'resolution': (128, 48, 48), 'max_particles': 400}
        insp = inspector_scene('cnc_rotary', scene=sc, fps=4, resolution=(640, 360), process_options=opts)
        t0 = time.time()
        insp.set_timing('physical')
        job, r = insp['job'], insp['robot']
        ek = job.event_keys
        K.check(f"rotary: physical timing accepted: {job.duration:,.0f} s at 4 fps, {ek['events']:,} events keyed in "
                f'{time.time() - t0:.0f} s; the stock written for the first frame only ({job.stock.run})',
                abs(job.duration - job.physical_duration) < 1e-9 and job.stock.run == (1, 1))
        worst_p = worst_a = 0.0
        idx = [g for g in job.path.segments if g['type'] == 'index']
        extra = [g['t0'] + (g['t1'] - g['t0']) * u for g in rng.sample(idx, 6) for u in (0.3, 0.5, 0.8)]
        for t in sample_times(job, 30, extra):
            at(sc, sc.frame_start + t * 4)
            st = job.path.sample(t)
            s = job.settings
            want = Vector((st['position'][0] + s['axis_x'], st['position'][1], st['position'][2] + s['axis_height']))
            worst_p = max(worst_p, (Vector(r.tool_tip()) - want).length)
            worst_a = max(worst_a, adiff(evaluated_turn(r, 'rotary_output'), st['angle'] % TAU))
        K.check(f'rotary: the tool tip and the A axis follow the program exactly, index turns included (worst '
                f'{worst_p * 1e6:.2f} um, {math.degrees(worst_a):.5f} deg)', worst_p < 5e-6 and worst_a < 1e-4)
        insp.set_time(600.0)
        f600 = sc.frame_start + 600 * 4
        K.check(f'rotary: set_time(600) writes the frame it shows ({job.stock.run})', job.stock.run == (f600, f600)
                and os.path.exists(job.stock.frame_path(f600)))
        insp.play(start=600.0, seconds=3.0)
        K.check(f'rotary: play(start=600, seconds=3) writes the stretch and plays it ({job.stock.run}, preview '
                f'{sc.frame_preview_start}..{sc.frame_preview_end})',
                job.stock.run == (f600, f600 + 12) and sc.use_preview_range
                and (sc.frame_preview_start, sc.frame_preview_end) == (f600, f600 + 12))
        try:
            job.stock.show_frames(1, f600)
            refused = 'shown'
        except ValueError as e:
            refused = str(e)
        K.check(f'rotary: show_frames refuses a stretch whose frames are not all written ({refused[:90]})',
                refused.startswith('show_frames') and job.stock.run == (f600, f600 + 12))
        if RENDER:
            K.probe_render(sc, (960, 540), 16)
            insp.set_time(601.0)
            insp.frame_work()
            p = os.path.join(OUT, 'rotary_physical_t601.png')
            K.check('rotary at 601 s: still', K.still(sc, sc.camera, sc.frame_current, p))
        insp.dispose()
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def main():
    for fn in (relief, print_job, rotary, pocket):
        try:
            fn()
        except Exception:  # noqa: BLE001
            K.check(fn.__name__, False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('inspector_physical')


main()
