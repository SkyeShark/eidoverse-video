"""Every rotary_carve option and the job's whole API (eidoverse/robotics/rotary.js), exercised on the cnc_rotary machine
with small programs, and every refusal rotaryCarve makes. Nothing renders.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_carve_options.py

Checks
  job state     seek() poses the tool tip, the A axis, the spindle (at the program's rpm, on the physical clock) and
                the stock; job.state carries position / stock_position / physical_time / playback_time; seek(NaN)
                refuses; duration maps playback onto the physical program
  on_done       called once when the job reaches its end, again only after it has left the end (the WebGPU flag)
  play / stop   play(start, speed, frames) keys the times (f - frame_start) / fps - start, times speed; auto_play
                keys the scene's range at build; stop() removes every key the job made and holds the stock
  options       quill (tailstock, quill, handwheel joints), color (the stock tint), engagement_resolution, seed,
                dust, max_particles, collection, the program's rate overrides (feed, plunge, rpm, rotation_speed,
                rapid, acceleration), a ball-nose cutter fitted to the machine, every preset material's stock and chips
  the stock     readback(), tiled() (the WebGPU tiled 2D layout, voxel for voxel), layout, cell_size, bounds,
                index, texture (the file written last, the hold file after stop), settings; the chuck turned by
                hand turns the stock; dispose(files=True) leaves no file and no cache folder
  refusals      no rotary chuck, no fitted cutter, no adjustable fixture, a tool or radius other than the
                installed cutter's, a moved axis or end stock, a bad duration, a path beyond the gantry's travel;
                none of them leaves an object behind
Prints PASS / FAIL.
"""

import math
import os
import re
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from bpy_extras import anim_utils                                                        # noqa: E402

from eidoblend.characters.robotics import make_robot                                    # noqa: E402
from eidoblend.fabrication._axes import color_linear                                    # noqa: E402
from eidoblend.fabrication.cutting import stock_profile                                 # noqa: E402
from eidoblend.fabrication.machine import rest_matrix                                   # noqa: E402
from eidoblend.fabrication.rotary import (TAU, rotary_carve, rotary_fixture_setup, rotary_program,  # noqa: E402
                                          sample_rotary)

OUT = os.path.join(HERE, 'out', 'carve_options')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
FAILS = []
SMALL = dict(angles=16, sample_step=.004, stepdown=.006, resolution=(64, 28, 28))


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def refusal(fn):
    try:
        fn()
    except Exception as e:                                          # noqa: BLE001
        return str(e)
    return None


def keys_on(ob):
    """keyframe points on an object's action (0 without one)"""
    ad = ob.animation_data
    if ad is None or ad.action is None:
        return 0
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return sum(len(fc.keyframe_points) for fc in cb.fcurves) if cb else 0


def chuck_angle(machine):
    """the chuck's turn about X relative to the fixture (the A axis), radians"""
    rel = machine.roots['rotary_fixture'].matrix_world.inverted() @ machine.roots['rotary_chuck'].matrix_world
    return math.atan2(rel[2][1], rel[1][1])


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def spindle_angle(machine):
    """the spindle rotor's turn from its rest about its own axis"""
    name = 'spindle_rotor'
    q = rest_matrix(machine, name).decompose()[1].inverted() @ machine.roots[name].matrix_basis.decompose()[1]
    axis = Vector(machine.specs[name].get('axis') or (0, 0, 1)).normalized()
    ang = 2 * math.atan2(Vector(q[1:]).dot(axis), q[0])
    return ang % TAU


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 24, 1.0
sc.frame_start, sc.frame_end = 1, 4
m = make_robot('cnc_rotary', textures=False)
print('machine axis limits', m.machine['axis_limits'], 'rest tip', tuple(round(v, 5) for v in m.machine['rest_tip']))

# ------------------------------------------------------------------------------------------ the job's state ---
done_calls = []
job = rotary_carve(m, sample_rotary, duration=5.0, cache_dir=os.path.join(OUT, 'state'),
                   on_done=lambda j: done_calls.append(j.time), **SMALL)
s = job.settings
st = job.seek(2.0)
bpy.context.view_layer.update()
want = job.path.sample(2.0 / 5.0 * job.path.duration)
tip = Vector((want['position'][0] + s['axis_x'], want['position'][1], want['position'][2] + s['axis_height']))
check('seek: playback time maps linearly onto the physical program', abs(st['physical_time'] - want['time']) < 1e-12
      and st['playback_time'] == 2.0 and job.time == 2.0 and not job.done)
check('seek: the tool tip is at the program position over the bed', (m.tool_tip() - tip).length < 1e-6,
      f'{(m.tool_tip() - tip).length * 1e6:.3f} um')
check('seek: job.state position = stock_position + (axis_x, 0, axis_height)',
      all(abs(st['position'][k] - (st['stock_position'][k] + (s['axis_x'], 0, s['axis_height'])[k])) < 1e-15
          for k in range(3)) and tuple(st['stock_position']) == tuple(want['position']))
check('seek: the chuck turns to the program\'s A angle', abs(wrap(chuck_angle(m) - want['angle'])) < 1e-6,
      f'{chuck_angle(m):.6f} vs {want["angle"]:.6f}')
expect_spin = math.fmod(want['time'] * s['rpm'] / 60 * TAU, TAU)
check(f'seek: the spindle turns at {s["rpm"]} rpm on the physical clock',
      abs(wrap(spindle_angle(m) - expect_spin)) < 1e-4, f'{spindle_angle(m):.5f} vs {expect_spin:.5f}')
check('seek: refuses a time that is not finite', re.search('finite', refusal(lambda: job.seek(math.nan)) or ''))
job.seek(5.0)
job.seek(7.0)
check('on_done: called once at the end (seeking past the end again does not repeat it)',
      done_calls == [5.0] and job.done and job.time == 5.0)
job.seek(1.0)
job.seek(5.0)
check('on_done: called again after the job left the end', done_calls == [5.0, 5.0])

# ------------------------------------------------------------------------------------- play, stop, the stock ---
job.play(start=.5, speed=3.0, frames=[1, 13, 25])
check('play(start, speed, frames): every frame keyed and its stock file written',
      job.stock.frames_written == [1, 13, 25] and keys_on(m.roots['rotary_chuck']) >= 3)
worst = 0.0
for f in (1, 13, 25):
    sc.frame_set(f)
    t = max(0.0, ((f - 1) / 24 - .5) * 3.0)
    w = job.path.sample(min(t, 5.0) / 5.0 * job.path.duration)
    p = Vector((w['position'][0] + s['axis_x'], w['position'][1], w['position'][2] + s['axis_height']))
    worst = max(worst, (m.tool_tip() - p).length)
check('play: frame f plays the job at ((f - frame_start) / fps - start) * speed', worst < 1e-5,
      f'worst {worst * 1e6:.2f} um')
check('stock.texture is the VDB file written last (frame 25 after play)', job.stock.texture == job.stock.frame_path(25)
      and os.path.exists(job.stock.texture))
job.seek(max(0.0, (12 / 24 - .5) * 3.0))
job.key(13)
check('stock.texture follows the write, not the frame number: frame 13 keyed again after 25 is the texture',
      job.stock.texture == job.stock.frame_path(13))
fld = job.stock.readback()
check('stock.readback(): a copy of the field, (nx, ny, nz) samples', fld.shape == tuple(job.stock.resolution)
      and fld is not job.stock.field and np.array_equal(fld, job.stock.field))
lay = job.stock.layout
img = job.stock.tiled()
nx, ny, nz = job.stock.resolution
rng = np.random.default_rng(3)
tiles_ok = True
for _ in range(500):
    x, y, z = int(rng.integers(nx)), int(rng.integers(ny)), int(rng.integers(nz))
    z3, y3 = ny - 1 - y, z                       # three's width index (its z = our -y) and height index (its y = z)
    r, c = divmod(z3, lay['cols'])
    tiles_ok &= img[r * nz + y3, c * nx + x] == fld[x, y, z]
check(f'stock.tiled(): the WebGPU tiled target ({lay["width"]} x {lay["height"]}, {lay["cols"]} columns of z '
      'slices), voxel for voxel', img.shape == (lay['height'], lay['width']) and tiles_ok
      and lay['cols'] == math.ceil(math.sqrt(ny)))
check('stock.layout is the WebGPU api.layout key for key, in three\'s axes: ny the height count, nz the width count, '
      'cols = ceil(sqrt(nz))', (lay['nx'], lay['ny'], lay['nz']) == (nx, nz, ny)
      and lay['cols'] == math.ceil(math.sqrt(lay['nz'])) and lay['width'] == lay['nx'] * lay['cols']
      and lay['height'] == lay['ny'] * math.ceil(lay['nz'] / lay['cols']))
eps = max(s['stock_length'] / (nx - 4), s['stock_width'] / (ny - 4), s['stock_height'] / (nz - 4))
check('stock: bounds pad the blank by two cells, cell_size spans them, the stroke index is (40, 16, 16)',
      abs(job.stock.bounds['max'][0] - (s['stock_length'] / 2 + 2 * eps)) < 1e-15
      and abs(job.stock.cell_size[0] - (s['stock_length'] + 4 * eps) / (nx - 1)) < 1e-15
      and tuple(job.stock.index.dims) == (40, 16, 16) and job.stock.settings is job.settings)
job.stop()
check('stop(): every key the job made is gone and the stock holds its current field (texture = the hold file)',
      keys_on(m.roots['rotary_chuck']) == 0 and keys_on(m.roots['gantry_x']) == 0
      and not job.stock.volume_data.is_sequence and job.stock.texture == job.stock.hold_path
      and os.path.exists(job.stock.hold_path))
m.set_joints({'rotary_output': 1.0})
bpy.context.view_layer.update()
rel = m.roots['rotary_fixture'].matrix_world.inverted() @ job.mesh.matrix_world
check('the stock rides the chuck: the A axis turned by hand turns it', abs(math.atan2(rel[2][1], rel[1][1]) - 1.0) < 1e-6)
files = [job.stock.frame_path(f) for f in job.stock.frames_written] + [job.stock.hold_path]
cache = job.stock.cache_dir
n_before = len(bpy.data.objects)
job.dispose(files=True)
check('dispose(files=True): the job\'s objects, every stock file (each frame\'s and the hold file) and the emptied '
      'cache folder are gone', len(bpy.data.objects) < n_before and not any(os.path.exists(f) for f in files)
      and not os.path.exists(cache) and job.mesh is None)

# ---------------------------------------------------------------------------------------------- auto_play ---
sc.frame_start, sc.frame_end = 1, 4
job = rotary_carve(m, sample_rotary, duration=3.0, auto_play=True, cache_dir=os.path.join(OUT, 'auto'), **SMALL)
check('auto_play: the scene\'s frames are keyed at build (play())', job.stock.frames_written == [1, 2, 3, 4]
      and keys_on(m.roots['gantry_x']) >= 4)
job.dispose(files=True)

# ------------------------------------------------------------------------------------------ the options ---
L, quill = .12, .003
coll = bpy.data.collections.new('rotary job collection')
sc.collection.children.link(coll)
job = rotary_carve(m, sample_rotary, stock_length=L, quill=quill, color='#3366cc', engagement_resolution=(48, 16, 16),
                   max_particles=300, dust=False, collection=coll, cache_dir=os.path.join(OUT, 'options'), **SMALL)
setup = rotary_fixture_setup(stock_length=L, quill=quill)
check('quill: the fixture holds a 120 mm blank with the quill out 3 mm (tailstock, quill, handwheel joints)',
      all(abs(m.state[k] - v) < 1e-12 for k, v in setup['joints'].items())
      and abs(m.state['rotary_tailstock'] - (L - .140 - quill)) < 1e-12)
check('quill: the program keeps that blank\'s datums', job.settings['stock_length'] == L
      and abs(job.settings['start'] - setup['start']) < 1e-15 and abs(job.settings['axis_x'] - setup['axis_x']) < 1e-15)
tint = tuple(job.stock.finish.tint.outputs[0].default_value[:3])
check('color: the stock\'s finish takes the colour', np.allclose(tint, color_linear('#3366cc'), atol=1e-6),
      f'{tuple(round(v, 4) for v in tint)}')
check('engagement_resolution: the chip events are sampled on that grid', tuple(job.removal.resolution) == (48, 16, 16))
check('max_particles, dust=False: one pool of wood shavings, at most 300 chips',
      len(job.debris.pools) == 1 and job.debris.pools[0].name == 'Wood shavings' and job.debris.particle_count <= 300)
mine = {job.mesh.name, job.stock.mesh.name, job.stock.volume_object.name, job.debris.group.name}
check('collection: the job\'s frame, stock, field and chips go into it', mine <= {o.name for o in coll.objects})
grain = job.stock.material.node_tree.nodes.get('rotary grain (z, y, x)')
check('the stock finish reads the WebGPU rotary point (z, y, x): the grain swizzle is in its material',
      grain is not None and grain.outputs[0].is_linked)
job.dispose(files=True)


def chips(seed):
    """the chips' evaluated placements (the pool's instances) just after a mid-program event, for a seed"""
    j = rotary_carve(m, sample_rotary, seed=seed, cache_dir=os.path.join(OUT, 'seed'), **SMALL)
    e = j.removal.events[len(j.removal.events) // 2]
    j.debris.set_time(e['time'] + .05)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    pool = j.debris.pools[0].object
    co = np.array([tuple(inst.matrix_world.translation) for inst in dg.object_instances
                   if inst.is_instance and inst.parent is not None and inst.parent.original == pool]).ravel()
    pools = len(j.debris.pools)
    j.dispose(files=True)
    return co, pools


a, pools = chips(7319)
b, _ = chips(11)
check(f'seed: a different seed throws other chips on other arcs ({len(a) // 3} vs {len(b) // 3} in flight); dust on '
      f'by default for wood ({pools} pools)', len(a) > 0 and len(b) > 0 and (len(a) != len(b) or not np.allclose(a, b))
      and pools == 2)

job = rotary_carve(m, sample_rotary, feed=.02, plunge=.004, rpm=12000, rotation_speed=.4, rapid=.05,
                   acceleration=.2, rough_allowance=.001, cache_dir=os.path.join(OUT, 'rates'), **SMALL)
segs = job.path.segments
cut_ok = all(sg['feed'] <= .02 + 1e-15 for sg in segs if sg['type'] == 'cut')
plunges = [mv for mv in job.program.moves if mv['type'] == 'cut' and mv['feed'] == .004]
index_ok = all(abs((sg['t1'] - sg['t0']) - max(.02, abs(sg['a1'] - sg['a0']) * 1.5 / .4)) < 1e-12
               for sg in segs if sg['type'] == 'index')
rapid_ok = all(sg['peak'] <= .05 + 1e-15 for sg in segs if sg['type'] == 'rapid')
acc_ok = all(abs(sg['acceleration'] - .2 * .6) < 1e-15 for sg in segs if sg['type'] != 'index')
check('rates: feed, plunge, rotation_speed, rapid and acceleration reach the program and its timing',
      cut_ok and len(plunges) > 10 and index_ok and rapid_ok and acc_ok and job.settings['feed'] == .02
      and job.settings['plunge'] == .004)
job.seek(job.duration * .37)
expect_spin = math.fmod(job.state['physical_time'] * 12000 / 60 * TAU, TAU)
check('rpm: the spindle turns at the requested 12000 rpm', job.settings['rpm'] == 12000
      and abs(wrap(spindle_angle(m) - expect_spin)) < 1e-4)
job.dispose(files=True)

saved = dict(m.machine['cutter'])
m.machine['cutter'] = {'kind': 'ball', 'radius': .003, 'flute_length': .017}
job = rotary_carve(m, sample_rotary, cache_dir=os.path.join(OUT, 'ball'), **SMALL)
check('a ball-nose cutter fitted to the machine: the program uses it (17 mm flutes)',
      job.settings['tool'] == 'ball' and job.settings['flute_length'] == .017)
job.dispose(files=True)
refused_ball = refusal(lambda: rotary_carve(m, sample_rotary, tool='flat', cache_dir=os.path.join(OUT, 'ball'),
                                            **SMALL))
m.machine['cutter'] = saved
check('a ball-nose machine refuses a flat program', re.search('must match the installed cutter', refused_ball or ''))

for material, pool in (('aluminum', 'Metal swarf'), ('brass', 'Metal swarf'), ('steel', 'Metal swarf'),
                       ('plywood', 'Wood shavings')):
    job = rotary_carve(m, sample_rotary, material=material, cache_dir=os.path.join(OUT, material),
                       **dict(SMALL, stepdown=None))            # the preset's own depth steps
    prof = stock_profile(material)
    tint = tuple(job.stock.finish.tint.outputs[0].default_value[:3])
    metal = abs(next(n for n in job.stock.material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                .inputs['Metallic'].default_value - prof.metalness) < 1e-9
    check(f'{material}: its rates ({prof.feed * 1000:.1f} mm/s feed, {prof.stepdown * 1000:.1f} mm steps), its '
          f'finish and its chips ({pool})', job.settings['feed'] == prof.feed and job.settings['stepdown'] ==
          prof.stepdown and np.allclose(tint, color_linear(prof.color), atol=1e-6) and metal
          and [p.name for p in job.debris.pools][0] == pool)
    job.dispose(files=True)

# --------------------------------------------------------------- the machine placed and turned in the scene ---
from mathutils import Euler, Matrix                                                    # noqa: E402

m.group.matrix_world = Matrix.Translation((1.5, -.7, .3)) @ Euler((0.0, 0.0, 1.1)).to_matrix().to_4x4()
bpy.context.view_layer.update()
job = rotary_carve(m, sample_rotary, duration=4.0, cache_dir=os.path.join(OUT, 'placed'), **SMALL)
st = job.seek(1.7)
bpy.context.view_layer.update()
bed = m.roots['gantry_base'].matrix_world @ Matrix.Translation((0, 0, m.machine['bed_top']))
tip_world = bed @ Vector(st['position'])
on_axis = bed @ Vector((job.settings['axis_x'], 0.0, job.settings['axis_height']))
rel = bed.inverted() @ job.mesh.matrix_world
check('placed machine: the program, the stock and the chips follow its bed frame (moved 1.7 m, turned 63 degrees)',
      (m.tool_tip(world=True) - tip_world).length < 1e-6 and (job.mesh.matrix_world.translation - on_axis).length < 1e-6
      and abs(wrap(math.atan2(rel[2][1], rel[1][1]) - st['angle'])) < 1e-6
      and job.debris.group.parent == m.roots['gantry_base'],
      f'tip {(m.tool_tip(world=True) - tip_world).length * 1e6:.2f} um, stock axis '
      f'{(job.mesh.matrix_world.translation - on_axis).length * 1e6:.2f} um off')
job.dispose(files=True)
m.group.matrix_world = Matrix.Identity(4)
bpy.context.view_layer.update()

# ------------------------------------------------------------------------------ the mesh planner's options ---
# a supplied model given as a Collection; its tolerance and rough allowance where the cutter reaches it
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12)
ball = bpy.context.active_object
ball.scale = (2.2, 1.0, 1.0)
src = bpy.data.collections.new('supplied model collection')
sc.collection.children.link(src)
for c in list(ball.users_collection):
    c.objects.unlink(ball)
src.objects.link(ball)
bpy.context.view_layer.update()
MO = dict(angles=4, grid_step=.001, sample_step=.004, stepover=.003, stepdown=.008)
by_coll = rotary_program(src, **MO)
by_obj = rotary_program(ball, **MO)
check(f'mesh source: a Collection plans the same moves as its object ({len(by_coll.moves)} moves, '
      f'{by_coll.report.source["triangles"]} triangles)',
      [mv['position'] for mv in by_coll.moves] == [mv['position'] for mv in by_obj.moves])


def finish_heights(p):
    """the finish stage's cut heights (the tip above the axis) and whether each sits on the shank's reach floor"""
    first = next(s['first_move'] for s in p.stages if s['name'] == 'finish')
    cuts = [mv['position'][2] for mv in p.moves[first:] if mv['type'] == 'cut']
    return np.array(cuts), p.report.reach_floor


tight, floor = finish_heights(rotary_program(src, **MO, tolerance=.00005))
loose, _ = finish_heights(rotary_program(src, **MO, tolerance=.00035))
free = tight > floor + 1e-9                     # above the shank's reach floor the model sets the height
check(f'tolerance: raises the finish by exactly the extra 0.3 mm wherever the model sets it ({free.sum()} cuts)',
      len(tight) == len(loose) and free.sum() > 50 and np.allclose(loose[free] - tight[free], .0003, atol=1e-12)
      and np.all(loose >= tight - 1e-15))


def first_rough(p):
    a = next(s['first_move'] for s in p.stages if s['name'] == 'rough 1')
    b = next(s['first_move'] for s in p.stages if s['name'] != 'rough 1' and s['first_move'] > a)
    return np.array([mv['position'][2] for mv in p.moves[a:b] if mv['type'] == 'cut'])


r_small, r_big = (rotary_program(src, **MO, rough_allowance=a) for a in (.0005, .0015))
rs, rb = first_rough(r_small), first_rough(r_big)
check(f'rough_allowance: the first roughing level stays further off the model, never closer ({(rb > rs).sum()} of '
      f'{len(rs)} cuts higher), and the finish is unchanged', len(rs) == len(rb) and np.all(rb >= rs - 1e-15)
      and (rb > rs).any() and np.array_equal(finish_heights(r_small)[0], finish_heights(r_big)[0]))
bpy.data.objects.remove(ball, do_unlink=True)
bpy.data.collections.remove(src)

# ------------------------------------------------------------------------------------------------ refusals ---
objects = len(bpy.data.objects)
bad = {}
bad['tool'] = refusal(lambda: rotary_carve(m, sample_rotary, tool='ball', cache_dir=OUT, **SMALL))
bad['radius'] = refusal(lambda: rotary_carve(m, sample_rotary, radius=.002, cache_dir=OUT, **SMALL))
bad['axis'] = refusal(lambda: rotary_carve(m, sample_rotary, axis_height=.1, cache_dir=OUT, **SMALL))
bad['end'] = refusal(lambda: rotary_carve(m, sample_rotary, end=.06, cache_dir=OUT, **SMALL))
bad['duration'] = refusal(lambda: rotary_carve(m, sample_rotary, duration=-1, cache_dir=OUT, **SMALL))
bad['blank'] = refusal(lambda: rotary_carve(m, sample_rotary, stock_length=.2, cache_dir=OUT, **SMALL))
m.has_rotary_setup = False
bad['fixture'] = refusal(lambda: rotary_carve(m, sample_rotary, cache_dir=OUT, **SMALL))
m.has_rotary_setup = True
m.machine['cutter'] = dict(saved, kind='vee')
bad['cutter'] = refusal(lambda: rotary_carve(m, sample_rotary, cache_dir=OUT, **SMALL))
m.machine['cutter'] = saved
limits = [list(v) for v in m.machine['axis_limits']]
# the widest blanks the fixture takes stay inside the G430's travel; a narrower machine refuses the same path
margins = []
for blank in ((.08, .018, .018), (.18, .05, .05), (.18, .036, .05), (.13, .05, .036)):
    p = rotary_program(sample_rotary, stock_length=blank[0], stock_width=blank[1], stock_height=blank[2], angles=16,
                       sample_step=.004, tool='flat', flute_length=.018)
    pos = np.array([mv['position'] for mv in p.moves])
    rest, bed = m.machine['rest_tip'], m.machine['bed_top']
    q = np.stack([pos[:, 0] + p.settings['axis_x'] - rest[0], pos[:, 1] - rest[1],
                  pos[:, 2] + p.settings['axis_height'] + bed - rest[2]], 1)
    margins.append(min(min(q[:, k].min() - limits[k][0], limits[k][1] - q[:, k].max()) for k in range(3)))
m.machine['axis_limits'] = [limits[0], limits[1], [limits[2][0], limits[2][0] + .01]]
bad['travel'] = refusal(lambda: rotary_carve(m, sample_rotary, cache_dir=OUT, **SMALL))
m.machine['axis_limits'] = limits
fixture = make_robot('rotary_fixture', textures=False)
plain = {'roots': {}, 'machine': None}
bad['machine'] = refusal(lambda: rotary_carve(type('Bare', (), plain)(), sample_rotary, cache_dir=OUT, **SMALL))
fixture.dispose()
expected = {'tool': 'Requested tool must match the installed cutter', 'radius': 'Cutter radius must match',
            'axis': 'calibrated rotary axis', 'end': 'sacrificial end stock', 'duration': 'Invalid job duration',
            'blank': 'Fixture accepts 80', 'fixture': 'Load the adjustable rotary fixture',
            'cutter': 'fitted flat or ball-nose cutter', 'travel': 'exceeds Z travel', 'machine': 'Load cnc_rotary'}
for k, pattern in expected.items():
    check(f'refuses: {k} ({bad[k]})', bad[k] is not None and pattern in bad[k])
check(f'the four extreme blanks the fixture accepts keep at least {min(margins) * 1000:.1f} mm inside the gantry\'s '
      'travel (the travel check guards a narrower machine)', min(margins) > 0)
check('no refused job left an object behind', len(bpy.data.objects) == objects)
m.dispose()
shutil.rmtree(OUT, ignore_errors=True)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
