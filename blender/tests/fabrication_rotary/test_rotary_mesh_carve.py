"""Rotary carving from a supplied Blender model: Suzanne (subdivided, head along the rotary axis) carved in hardwood on
the cnc_rotary machine by the mesh planner (12 indexed orientations, lateral rasters). Builds, keys a probe's frames
over a 20 s film, checks the result and saves out/rotary_mesh_example.blend; render_rotary_probes.py renders it.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_mesh_carve.py \
        [-- frames=1,97,241,385,480 res=200,80,80]

Checks: the program's report (source triangles, reach-limited samples, retained end stock), the finished field holds
the fitted model wherever the cutter can reach it (no gouge), and the stock is cut down toward it. Prints PASS / FAIL.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups beside the saved builds
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.characters.robotics import make_robot, studio                              # noqa: E402
from eidoblend.characters.robotics.studio import make_camera                               # noqa: E402
from eidoblend.fabrication.rotary import StockField, rotary_carve                          # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
OUT = os.path.join(HERE, 'out')
FRAMES = [int(v) for v in args.get('frames', '1,97,241,385,480').split(',')]
RES = tuple(int(v) for v in args.get('res', '200,80,80').split(','))
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
blend = os.path.join(OUT, 'rotary_mesh_example.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1280, 900
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 480
studio(sc, grid=False)
bpy.ops.mesh.primitive_monkey_add(size=2)
model = bpy.context.active_object
model.name = 'supplied model (Suzanne)'
model.rotation_euler = (0.0, math.radians(90), 0.0)          # the crown toward -X (the chuck), the face toward -Y
sub = model.modifiers.new('subdivision', 'SUBSURF')
sub.levels = 2
bpy.context.view_layer.update()
machine = make_robot('cnc_rotary', scene=sc, primary='#b9c7c8', accent='#235b68')
t0 = time.time()
job = rotary_carve(machine, model, material='wood', duration=19, resolution=RES, cache_dir='//rotary_mesh_cache')
dt = time.time() - t0
model.hide_render = True                                      # the model is the target, not the stock
model.hide_set(True)
rep = job.program.report
check(f'mesh job: {len(job.program.moves)} moves from {rep.source["triangles"]} source triangles (modifiers applied), '
      f'{rep.orientations} orientations, {job.physical_duration / 60:.1f} min physical, built in {dt:.1f} s',
      rep.source['triangles'] > 7000 and len(job.program.moves) > 1000)
check(f'mesh job: reach-limited samples reported ({rep.reach_limited_samples}), retained end stock '
      f'{rep.retained_end_stock[0] * 1000:.0f} / {rep.retained_end_stock[1] * 1000:.0f} mm',
      abs(rep.retained_end_stock[0] - .029) < 1e-12 and abs(rep.retained_end_stock[1] - .018) < 1e-12)
cam = make_camera(36, 'mesh carve camera', sc)
cam.data.clip_start, cam.data.clip_end = .02, 10
sc.camera = cam
from mathutils import Vector                                                                # noqa: E402
bpy.context.view_layer.update()                    # the stock frame's world matrix is stale until the scene updates
c = job.mesh.matrix_world.translation.copy()
on_bed = machine.roots['gantry_base'].matrix_world.inverted() @ c
check('mesh carve: the camera aims at the stock frame on the A axis (not the world origin)',
      abs(on_bed.z - (machine.machine['bed_top'] + job.settings['axis_height'])) < 1e-6
      and abs(on_bed.x - job.settings['axis_x']) < 1e-6, f'stock frame at {tuple(round(v, 4) for v in on_bed)} (bed frame)')
cam.location = c + Vector((-0.13, -0.24, 0.12))
cam.rotation_quaternion = (c + Vector((0.004, 0, -0.004)) - cam.location).to_track_quat('-Z', 'Y')
fps = sc.render.fps
for f in FRAMES:
    job.seek(max(0.0, (f - 1) / fps - 1))
    job.key(f)
# the finished part against the fitted model: inside wherever the cutter reached
end = StockField(job.path, job.settings, RES)
end.update(job.path.sample(job.path.duration))
g = job.program.geometry
pts = g.triangles.reshape(-1, 3)
idx = np.round((pts - np.asarray(end.bounds['min'])) / np.asarray(end.cell)).astype(int)
idx = np.clip(idx, 0, np.asarray(end.resolution) - 1)
vals = end.field[idx[:, 0], idx[:, 1], idx[:, 2]]
cell = max(end.cell)
check('mesh carve: every vertex of the fitted model stays inside the finished stock (no gouge beyond a cell)',
      vals.max() < cell, f'max field at the model {vals.max() * 1000:.3f} mm, cell {cell * 1000:.2f} mm')
v0 = StockField(job.path, job.settings, RES).volume()
check(f'mesh carve: {(1 - end.volume() / v0) * 100:.0f} % of the blank is cut away', end.volume() < .8 * v0)
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
print('saved', blend)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
