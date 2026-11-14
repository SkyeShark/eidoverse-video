"""Two jobs keyed on one machine, seek's evaluated state, what dispose leaves, the chips' framing bounds and the tubes'
drawn side (no render).

  keys      one printer prints the bracket keyed into frames 1..48, then the handle into 49..96 (a film printing one
            part after another): at frames of each range the keyed tool tip is that job's feed clock; the second
            job's key() leaves the first range's keys; stopping the second job leaves the first job's keys; the
            quaternion keys stay in one hemisphere across the seam between the ranges
  seek      job.seek(t) alone (no keys) brings the evaluated bead, stock and chips to time t: chord counts, depths and
            alive chips equal those the keyed frames give at the same times
  dispose   print, mill and carve jobs played and disposed leave no objects, meshes, materials, node groups or actions
            of their own: the counts return to the loaded robots' own
  bounds    the chips' hidden templates are chip-sized (no metre-sized hidden mesh inside the robot), the hidden
            trajectory box is cutting.js's (stock +- .22 m across, -.04 .. height + .09 m), and the manufacturing
            example's wide camera stands where frame_camera puts it from the robots' boxes with the WebGPU's chip
            bounds: fabrication's hidden helpers add nothing more to framing
  tubes     PTFE tubes draw their front faces only (filament.js: side FrontSide); the last one disposed takes the
            shared tube node group with it

    bash run_blender.sh blender/tests/fabrication/test_job_keys_seek_dispose_framing_tubes.py
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.characters.robotics import make_robot  # noqa: E402
from eidoblend.characters.robotics.studio import world_box  # noqa: E402

check = U.check


def fresh(frames=96):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, frames
    return sc


def counts():
    return {k: len(getattr(bpy.data, k)) for k in ('objects', 'meshes', 'materials', 'node_groups', 'actions')}


# --- keys: two jobs, one printer ------------------------------------------------------------------------------------
sc = fresh()
printer = make_robot('fdm', scene=sc)
a = fab.print(printer, fab.manufacturing_sample('bracket', as_parts=True), size=.03, center=(-.04, 0), infill=.2,
              duration=2)
b = fab.print(printer, fab.manufacturing_sample('handle', as_parts=True), size=.03, center=(.04, 0), infill=.2,
              duration=2)
a.key(1, 48)
b.key(49, 96)


def tip_error(job, frames, first):
    worst = 0.0
    for f in frames:
        sc.frame_set(f)
        t = min((f - first) / 24, job.duration)
        want = Vector(job.path.sample(t / job.duration * job.path.duration).position)
        worst = max(worst, (Vector(printer.tool_tip()) - want).length)
    return worst


ea, eb = tip_error(a, (5, 20, 40, 48), 1), tip_error(b, (49, 55, 70, 90), 49)
check("the first job's frames 1..48 still drive the printer after the second job keyed 49..96", ea < 1e-5,
      f'worst tip error {ea * 1000:.4f} mm')
check("the second job's frames 49..96 drive the printer", eb < 1e-5, f'worst tip error {eb * 1000:.4f} mm')
from eidoblend.fabrication._keys import _channelbag  # noqa: E402


def keyed_frames(ob, path='location'):
    cb = _channelbag(ob)
    fc = cb.fcurves.find(path, index=0) if cb is not None else None
    if fc is None:
        return []
    co = np.empty(2 * len(fc.keyframe_points), np.float32)
    fc.keyframe_points.foreach_get('co', co)
    return co[0::2].tolist()


gx = printer.roots['gantry_x']
both = keyed_frames(gx)
check('the shared axis carries both ranges, one key per frame', both == [float(f) for f in range(1, 97)],
      f'{len(both)} keys, {both[:2]} .. {both[-2:]}')
flips = 0
for o in a._moving_objects():
    cb = _channelbag(o)
    if cb is None:
        continue
    q = np.array([[fc.evaluate(f) for fc in sorted((c for c in cb.fcurves if c.data_path == 'rotation_quaternion'),
                                                    key=lambda c: c.array_index)] for f in (48, 49)])
    if q.shape == (2, 4) and np.dot(q[0], q[1]) < 0:
        flips += 1
check('the quaternion keys stay in one hemisphere across the seam between the ranges', flips == 0, f'{flips} flips')
b.stop()
left = keyed_frames(gx)
ea2 = tip_error(a, (5, 20, 40, 48), 1)
check("stopping the second job removes its frames and leaves the first job's", left == [float(f) for f in range(1, 49)]
      and ea2 < 1e-5, f'{len(left)} keys left on the X axis; first job tip error {ea2 * 1000:.4f} mm')
a.stop()
check('stopping both leaves no fabrication action on the printer',
      not [act.name for act in bpy.data.actions if '|fabrication' in act.name],
      f"{[act.name for act in bpy.data.actions][:4]}")

# --- seek: the evaluated state follows seek alone -------------------------------------------------------------------
sc = fresh(18 * 24)
printer = make_robot('fdm', scene=sc)
cnc = make_robot('cnc', scene=sc, position=(.8, 0, 0))
pj = fab.print(printer, fab.manufacturing_sample('bracket', as_parts=True), size=.03, infill=.2, duration=18)
mj = fab.mill(cnc, None, material='wood', duration=18, resolution=64)
pools = {p.object.name for p in mj.effects.pools}


def evaluated_state():
    dg = bpy.context.evaluated_depsgraph_get()
    be = pj.mesh.evaluated_get(dg)
    chords = len(be.to_mesh().vertices) // 16
    be.to_mesh_clear()
    se = mj.mesh.evaluated_get(dg)
    low = min(v.co.z for v in se.to_mesh().vertices if v.co.z > 1e-6)
    se.to_mesh_clear()
    alive = sum(1 for i in dg.object_instances
                if i.is_instance and i.parent is not None and i.parent.original.name in pools)
    return chords, round(low * 1000, 4), alive


times = (3.0, 9.0, 13.0, 16.0)
by_seek = []
for t in times:
    pj.seek(t)
    mj.seek(t)
    bpy.context.view_layer.update()
    by_seek.append(evaluated_state())
pj.play(scene=sc)
mj.play(scene=sc)
by_keys = []
for t in times:
    sc.frame_set(sc.frame_start + int(round(t * 24)))
    by_keys.append(evaluated_state())
check('seek alone brings the evaluated bead, stock and chips to its time, as the keyed frames do',
      by_seek == by_keys and len(set(s[:2] for s in by_seek)) == len(times),
      f'(chords, lowest stock top mm, chips alive) by seek {by_seek}; by keys {by_keys}')

# --- dispose: what three jobs leave -----------------------------------------------------------------------------------
sc = fresh(20)
printer = make_robot('fdm', scene=sc)
cnc = make_robot('cnc', scene=sc, position=(.8, 0, 0))
relief = make_robot('cnc_relief', scene=sc, position=(1.6, 0, 0))
src = fab.manufacturing_sample('bracket', as_parts=True)
bpy.context.view_layer.update()
before = counts()
jobs = [fab.print(printer, src, size=.03, infill=.2, duration=6),
        fab.mill(cnc, None, material='wood', duration=6, resolution=48),
        fab.carve(relief, fab.sample_relief, material='wood', duration=6, resolution=48, sample_step=.002,
                  stepover=.0015)]
for j in jobs:
    j.play(scene=sc)
during = counts()
for j in jobs:
    j.dispose()
after = counts()
check('print, mill and carve played and disposed leave nothing of their own', after == before,
      f'robots {before}; with the jobs {during}; after dispose {after}')

# --- bounds: chips and framing ----------------------------------------------------------------------------------------
from eidoblend.fabrication.examples import EXAMPLES  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rec = EXAMPLES['manufacturing'](sc, width=960, height=540)
groups = [r.group for r in rec['robots']]
templates = [o for o in bpy.data.objects if o.name.endswith('| template')]
biggest = max(max(o.dimensions) for o in templates)
check('the chip templates are chip-sized (no metre-sized hidden mesh in the robots)', biggest < .005,
      f'{len(templates)} templates, largest {biggest * 1000:.2f} mm')
mill_job = rec['jobs'][1]
bounds = mill_job.effects.bounds
st = mill_job.stock
# hidden objects are not evaluated, so their matrix_world is stale: compose the parent chain's local transforms
from eidoblend.fabrication.machine import world_matrix  # noqa: E402

corners = [world_matrix(bounds) @ v.co for v in bounds.data.vertices]
lo = Vector([min(c[i] for c in corners) for i in range(3)])
hi = Vector([max(c[i] for c in corners) for i in range(3)])
origin = world_matrix(mill_job.mesh).translation
want_lo = origin + Vector((-st.width / 2 - .22, -st.depth / 2 - .22, -.04))
want_hi = origin + Vector((st.width / 2 + .22, st.depth / 2 + .22, st.height + .09))
check("the chips' trajectory box is cutting.js's (stock +- .22 m, -.04 .. height + .09 m)",
      (lo - want_lo).length < 1e-6 and (hi - want_hi).length < 1e-6,
      f'{tuple(round(v, 4) for v in lo)} .. {tuple(round(v, 4) for v in hi)}')
helpers = set()
for j in rec['jobs']:
    for ob in getattr(j, '_data_objects', []):
        helpers.add(ob.name)
    if j.effects is not None:
        helpers.update(o.name for o in [j.effects.group] + list(j.effects.group.children_recursive))
moved = {}
for name in helpers:                                # out of the hierarchy for a moment (local transforms kept)
    ob = bpy.data.objects[name]
    if ob.parent is not None and ob.type == 'MESH':
        moved[name] = (ob.parent, ob.matrix_parent_inverse.copy(), ob.matrix_basis.copy())
        ob.parent = None
plain_lo, plain_hi = world_box(groups)
for name, (parent, inverse, basis) in moved.items():
    ob = bpy.data.objects[name]
    ob.parent = parent
    ob.matrix_parent_inverse = inverse
    ob.matrix_basis = basis
chips = []
for j in rec['jobs']:
    if j.effects is not None:
        o = world_matrix(j.mesh).translation
        chips.append((o + Vector((-j.stock.width / 2 - .22, -j.stock.depth / 2 - .22, -.04)),
                      o + Vector((j.stock.width / 2 + .22, j.stock.depth / 2 + .22, j.stock.height + .09))))
want_box = world_box([(plain_lo, plain_hi)] + chips)        # the robots, plus where chips fly (the WebGPU bounds)
got_box = world_box(groups)                                  # what frame_camera measures, helpers included
check("fabrication's hidden helpers add nothing to the robots' framing box beyond the WebGPU's chip bounds",
      (got_box[0] - want_box[0]).length < 1e-6 and (got_box[1] - want_box[1]).length < 1e-6,
      f'with the helpers {tuple(round(v, 3) for v in got_box[0])} .. {tuple(round(v, 3) for v in got_box[1])}; '
      f'robots without them {tuple(round(v, 3) for v in plain_lo)} .. {tuple(round(v, 3) for v in plain_hi)}')
cam = rec['camera']
toward = Vector((-.55, -1.2, .75)).normalized()
centre = (want_box[0] + want_box[1]) / 2
d = (cam.location - centre).length
tan_v = math.tan(cam.data.angle_y / 2)
right = Vector((0, 0, 1)).cross(toward).normalized()
up = toward.cross(right).normalized()
need = .01
for x in (want_box[0].x, want_box[1].x):
    for y in (want_box[0].y, want_box[1].y):
        for z in (want_box[0].z, want_box[1].z):
            p = Vector((x, y, z)) - centre
            need = max(need, p.dot(toward) + 1.12 * max(abs(p.dot(right)) / (tan_v * 960 / 540), abs(p.dot(up)) / tan_v))
check("the example's wide camera stands where frameCamera puts it from those boxes", abs(d - need) < 1e-4,
      f'{d:.4f} m from the box centre, {need:.4f} m wanted')

# --- tubes: the drawn side, the shared node group ---------------------------------------------------------------------
fresh(10)                                           # no robot: these two are the only tubes
tube = fab.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .2), (.12, 0, .2), (.12, 0, 0)])
core = fab.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .2), (.12, 0, .2), (.12, 0, 0)], outer_diameter=.00175,
                            inner_diameter=0, color='#e2742b')
check('PTFE tubes and cores draw front faces only (filament.js FrontSide)',
      tube.material.use_backface_culling and core.material.use_backface_culling
      and tube.material.surface_render_method == 'BLENDED')
tube.dispose()
shared = 'eido.ptfe_tube' in bpy.data.node_groups
core.dispose()
check('the last tube disposed takes the shared tube node group with it',
      shared and 'eido.ptfe_tube' not in bpy.data.node_groups and not bpy.data.meshes and not bpy.data.materials,
      f'group kept while a tube lives: {shared}; left: {len(bpy.data.node_groups)} node groups, '
      f'{len(bpy.data.meshes)} meshes, {len(bpy.data.materials)} materials')

ok = U.summary('job_keys_seek_dispose_framing_tubes')
sys.exit(0 if ok else 1)
