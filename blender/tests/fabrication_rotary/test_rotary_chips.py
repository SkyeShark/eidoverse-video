"""Chips in flight from the rotary cut: the job's removal events (rotary_removal) feeding the fabrication family's
cutting_debris, on the cnc_rotary machine, in hardwood (shavings and fines) and aluminium (swarf). Keys three moments
just after mid-program chip events per material, with a close camera on the cutter, and saves
out/rotary_chips_<material>.blend for render_rotary_probes.py.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_chips.py

Checks, per keyed frame (read back from the saved scene), 20 ms after a chip event: chips are in flight; that event
leaves from the cut (its origin within 12 mm of the cutter tip: its eighth of a stroke spreads it); and every chip lies
where a chip from an event still alive can be (within the fastest chip's 1.3 m/s times the event's age, plus 4 mm for
the emission offset and the chip itself, of that event's origin). Nothing flies before the first event.
Prints PASS / FAIL.
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups beside the saved builds
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.characters.robotics import make_robot, studio                              # noqa: E402
from eidoblend.characters.robotics.studio import make_camera                               # noqa: E402
from eidoblend.fabrication.rotary import rotary_carve, sample_rotary                       # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []
AGE = .02                                       # seconds after the chip event each frame shows
SPEED, SLACK, TTL = 1.3, .004, .25              # fastest chip (m/s), emission offset + chip size (m), longest life (s)


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def in_flight(pools):
    """world positions of every chip instance the pools evaluate to now"""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    names = {p.object.name for p in pools}
    return np.array([tuple(i.matrix_world.translation) for i in dg.object_instances
                     if i.is_instance and i.parent is not None and i.parent.original.name in names]).reshape(-1, 3)


def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.node_groups, bpy.data.volumes, bpy.data.actions,
                 bpy.data.lights, bpy.data.cameras, bpy.data.images, bpy.data.worlds):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


for material in ('wood', 'aluminum'):
    reset()
    blend = os.path.join(OUT, f'rotary_chips_{material}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)                     # the stock cache sits beside the .blend
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1280, 900
    sc.render.fps, sc.render.fps_base = 24, 1.0
    sc.frame_start, sc.frame_end = 1, 3
    sc.render.engine = 'BLENDER_EEVEE'
    studio(sc, grid=False)
    machine = make_robot('cnc_rotary', scene=sc, primary='#b9c7c8', accent='#235b68')
    job = rotary_carve(machine, sample_rotary, material=material, resolution=(192, 72, 72),
                       cache_dir=f'//rotary_chips_{material}_cache')      # physical timing: no duration
    ev = job.removal.events
    picks = [ev[int(len(ev) * f)] for f in (.3, .55, .8)]
    cam = make_camera(40, f'chips camera ({material})', sc)
    cam.data.clip_start = .005
    sc.camera = cam
    base = machine.roots['gantry_base']
    job.seek(max(0.0, ev[0]['time'] - .5))
    bpy.context.view_layer.update()
    check(f'{material}: nothing flies before the first chip event', len(in_flight(job.debris.pools)) == 0)
    for f, e in enumerate(picks, start=1):
        job.seek(e['time'] + AGE)
        job.key(f)
        bpy.context.view_layer.update()
        tip = machine.tool_tip(world=True)
        side = base.matrix_world.to_3x3() @ Vector((-.06, -.10, .035))
        cam.location = tip + side
        cam.rotation_quaternion = (tip + Vector((0, 0, -.004)) - cam.location).to_track_quat('-Z', 'Y')
        for path in ('location', 'rotation_quaternion'):
            cam.keyframe_insert(path, frame=f)
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    bed = base.matrix_world @ Matrix.Translation((0, 0, machine.machine['bed_top']))
    times = np.array([e['time'] for e in ev])
    origins = np.array([tuple(bed @ Vector(e['position'])) for e in ev])
    for f, e in zip((1, 2, 3), picks):                               # read back from the keyed scene
        sc.frame_set(f)
        t = e['time'] + AGE
        tip = np.array(machine.tool_tip(world=True))
        pts = in_flight(job.debris.pools)
        alive = (times <= t) & (times > t - TTL)
        age, org = t - times[alive], origins[alive]
        excess = np.array([(np.linalg.norm(org - p, axis=1) - SPEED * age).min() for p in pts]) if len(pts) else [np.inf]
        start = np.linalg.norm(np.array(tuple(bed @ Vector(e['position']))) - tip)
        check(f'{material} frame {f}: {len(pts)} chips in flight from {int(alive.sum())} live events, the newest '
              f'leaving the cut {start * 1000:.1f} mm from the tip; every chip inside the 1.3 m/s reach of a live event '
              f'(the nearest its edge {-max(excess) * 1000:.1f} mm inside; {SLACK * 1000:.0f} mm outside allowed)',
              len(pts) > 0 and start < .012 and max(excess) < SLACK)
    print('saved', blend, flush=True)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
