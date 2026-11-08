"""The WebGPU edition's Deno tests for rotary carving, ported to Python with the same assertions:
eidoverse/robotics/tests/rotary_test.mjs (8 tests), rotary_mesh_test.mjs (3) and rotary_mount_test.mjs (1).
Positions are Blender's (three (x, y, z) -> (x, -z, y)): a height that was three's y is z here, three's z is -y.
Nothing renders.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_js_tests.py

One assertion cannot carry over and is replaced, as noted where it happens: the WebGPU rotaryCarve refused a job
without an initialised renderer; Blender meshes the stock with OpenVDB at build time and has no renderer object, so
that job is valid here and the test checks instead that disposing it leaves the machine as it was.
"""

import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.characters.robotics import make_robot                                    # noqa: E402
from eidoblend.fabrication.rotary import (RotaryPath, index_rotary_sweeps, rotary_blank_distance,  # noqa: E402
                                          rotary_carve, rotary_program, rotary_removal, sample_rotary, sweep_distance)
from eidoblend.fabrication.source_geometry import source_geometry                       # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []


def test(name, fn):
    try:
        fn()
        print('PASS ' + name, flush=True)
    except Exception as e:                                          # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL {name}: {e}', flush=True)
        FAILS.append(name)


def ok(v, m='Assertion failed'):
    if not v:
        raise AssertionError(m)


def near(a, b, e=1e-9):
    ok(abs(a - b) < e, f'{a} versus {b}')


def rejects(fn, pattern):
    err = None
    try:
        fn()
    except Exception as e:                                          # noqa: BLE001
        err = e
    ok(err is not None and re.search(pattern, str(err)), f'Expected {pattern}, got {err!r}')


def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def cast(objects, origin, direction):
    """the nearest hit of a world ray on these mesh objects: (distance, point) or None"""
    dg = bpy.context.evaluated_depsgraph_get()
    best = None
    for ob in objects:
        tree = BVHTree.FromObject(ob, dg)
        mw = ob.matrix_world
        inv = mw.inverted()
        o = inv @ Vector(origin)
        d = (inv.to_3x3() @ Vector(direction)).normalized()
        loc, _n, _i, _dist = tree.ray_cast(o, d)
        if loc is not None:
            dist = (mw @ loc - Vector(origin)).length
            if best is None or dist < best[0]:
                best = (dist, mw @ loc)
    return best


# ============================================================================================ rotary_test.mjs ===

def adjustable_blanks():
    """adjustable rectangular blanks retain jaw contact and enough gantry retraction"""
    reset()
    robot = make_robot('cnc_rotary', textures=False)
    for L, W, H in ((.08, .018, .026), (.18, .044, .050)):
        options = {'stock_length': L, 'stock_width': W, 'stock_height': H}
        robot.rotary_setup(L, W, H, 0.0)
        robot.set_joints({'rotary_output': .51})
        bpy.context.view_layer.update()
        chuck = robot.roots['rotary_chuck']
        for j in range(4):
            a3 = (0.0, math.cos(j * math.pi / 2), math.sin(j * math.pi / 2))      # three's chuck-local direction
            axis = Vector((a3[0], -a3[2], a3[1]))
            origin = Vector((-.063, 0, 0)) + axis * ((W if j % 2 else H) / 2 - .001)
            hit = cast(robot.part('RC independent jaw %d' % j), chuck.matrix_world @ origin,
                       chuck.matrix_world.to_3x3() @ axis)
            ok(hit, 'Jaw lost contact with rectangular stock')
            near(hit[0], .001, 2e-6)
        program = rotary_program(sample_rotary, **options, angles=16, sample_step=.005)
        s = program.settings
        for move in program.moves:
            p = (move['position'][0] + s['axis_x'], move['position'][1], move['position'][2] + s['axis_height'])
            robot.move_tool(p)
            ok((robot.tool_tip() - Vector(p)).length < 3e-7)
    robot.dispose()


def centre_seat():
    """prepared rotary blank seats a 60-degree live centre with pilot relief"""
    s = {'stock_length': .140, 'stock_height': .036, 'stock_width': .036}
    ok(rotary_blank_distance((0, 0, 0), s) < 0, 'Interior stock must remain solid')
    ok(rotary_blank_distance((.065, 0, 0), s) > 0, 'Pilot must clear the centre point')
    ok(rotary_blank_distance((.063, 0, 0), s) < 0, 'Pilot must have a closed floor')
    ok(rotary_blank_distance((-.069, 0, 0), s) < 0, 'Chuck end must remain solid')
    for a in (0, .39, 1.8, 4.7):
        x, r = .069, (.069 - .067) * math.tan(math.pi / 6)
        p = (x, -r * math.sin(a), r * math.cos(a))                     # three (x, r cos a, r sin a)
        near(rotary_blank_distance(p, s), 0, 1e-10)
        ok(rotary_blank_distance((x, p[1] * .95, p[2] * .95), s) > 0)
        ok(rotary_blank_distance((x, p[1] * 1.05, p[2] * 1.05), s) < 0)


def metal_presets():
    """metal rotary presets alter actual cutting time and depth stages"""
    o = {'angles': 16, 'sample_step': .004}
    wood = rotary_program(sample_rotary, **o, material='wood')
    for p in (rotary_program(sample_rotary, **o, material='aluminum'), rotary_program(sample_rotary, **o, material='brass')):
        ok(p.settings.feed < wood.settings.feed)
        ok(p.settings.stepdown < wood.settings.stepdown)
        ok(len(p.stages) > len(wood.stages))
        ok(p.path.duration > wood.path.duration)
        for seg in p.path.segments:
            if seg['type'] == 'cut':
                ok(seg['feed'] <= p.settings.feed)


def retracts_and_stationary_index():
    """indexed carving retracts beyond all stock corners and keeps XYZ stationary while rotating"""
    p = rotary_program(sample_rotary, angles=32, sample_step=.002, stepdown=.006)
    s = p.settings
    ok(len(p.stages) > 1 and p.stages[-1]['name'] == 'finish')
    indexes = cuts = 0
    for seg in p.path.segments:
        for f in (0, .23, .67, 1):
            q = p.path.sample(seg['t0'] + (seg['t1'] - seg['t0']) * f)
            ok(all(math.isfinite(v) for v in q['position']) and math.isfinite(q['speed']))
            if seg['type'] == 'index':
                indexes += 1
                near((Vector(seg['a']) - Vector(seg['b'])).length, 0)
                ok(q['position'][2] > math.hypot(s.stock_height / 2, s.stock_width / 2) + .002)
            else:
                if seg['type'] == 'cut':
                    cuts += 1
                ok(seg['feed'] + 1e-8 >= q['speed'] >= 0)
                near(q['angle'], seg['a0'])
    ok(indexes > 32 and cuts > 100)
    q = p.path.sample(p.path.duration * .173)
    p.path.sample(p.path.duration)
    back = p.path.sample(p.path.duration * .173)
    ok(dict(q) == dict(back))
    rejects(lambda: p.path.sample(math.nan), 'finite')
    rejects(lambda: rotary_program(sample_rotary, stepdown=math.inf), 'finite')
    rejects(lambda: rotary_program(lambda x, a: .003, angles=16, sample_step=.004), 'cutting length')


def swept_capsule():
    """swept cutter agrees with dense independent moving capsule samples"""
    for angle in (0, .73, 2.1):
        for slope in (-.45, 0, .6):
            s3 = {'a': (-.008, .012, 0), 'b': (.011, .012 + slope * .019, 0), 'a0': angle}
            s = {'a': (s3['a'][0], -s3['a'][2], s3['a'][1]), 'b': (s3['b'][0], -s3['b'][2], s3['b'][1]), 'a0': angle}
            for point3 in ((.002, .014, .001), (-.01, .012, .002), (.010, .023, -.004)):
                point = (point3[0], -point3[2], point3[1])
                for fraction in (.17, .6, 1):
                    c, sn = math.cos(angle), math.sin(angle)
                    p = (point3[0], point3[1] * c - point3[2] * sn, point3[1] * sn + point3[2] * c)
                    f = fraction * np.arange(16001) / 16000
                    x = s3['a'][0] + (s3['b'][0] - s3['a'][0]) * f
                    y = s3['a'][1] + (s3['b'][1] - s3['a'][1]) * f
                    cy = np.clip(p[1], y + .003, y + .017)
                    expected = float((np.sqrt((p[0] - x) ** 2 + (p[1] - cy) ** 2 + p[2] ** 2) - .003).min())
                    near(sweep_distance(point, s, .003, .017, fraction), expected, 1.3e-6)


def sculpture_not_gouged():
    """sample sculpture remains inside the uncut side of every swept tool surface"""
    p = rotary_program(sample_rotary, angles=48, sample_step=.0015, stepdown=.006)
    s = p.settings
    bounds = {'min': (-.07, -.027, -.027), 'max': (.07, .027, .027)}
    index = index_rotary_sweeps(p.path, s, bounds, (32, 16, 16), 0)
    worst = math.inf
    for i in range(102):
        for j in range(137):
            x = s.start + (s.end - s.start) * i / 101
            a = j * math.pi * 2 / 137
            r = sample_rotary(x, a)
            q = (x, -r * math.sin(a), r * math.cos(a))
            b = [math.floor((q[k] - bounds['min'][k]) / index.cell[k]) for k in range(3)]
            for sid in index.bins[b[0] + 32 * (b[1] + 16 * b[2])]:
                worst = min(worst, sweep_distance(q, p.path.segments[sid], s.radius))
    ok(worst >= -1e-7, f'Sample target gouged by {-worst} m')


def removal_first_engagement():
    """removal emits only first engagement; air travel and repeated cuts add no stock volume"""
    def mk(repeat):
        m = [{'position': (-.025, 0, .014), 'angle': 0, 'type': 'rapid'},
             {'position': (.025, 0, .014), 'angle': 0, 'type': 'cut'}]
        if repeat:
            m += [{'position': (-.025, 0, .014), 'angle': 0, 'type': 'cut'},
                  {'position': (.025, 0, .014), 'angle': 0, 'type': 'cut'}]
        m += [{'position': (.025, 0, .04), 'angle': 0, 'type': 'rapid'},
              {'position': (-.025, 0, .04), 'angle': 0, 'type': 'cut'}]
        return RotaryPath(m)
    settings = {'stock_length': .07, 'stock_width': .036, 'stock_height': .036, 'radius': .003, 'flute_length': .017,
                'axis_x': 0, 'axis_height': .097}
    a = rotary_removal(mk(False), settings, (36, 20, 20))
    b = rotary_removal(mk(True), settings, (36, 20, 20))
    ok(a.removed_volume > 0 and len(a.events) > 0)
    near(a.removed_volume, b.removed_volume, 1e-14)
    t1 = mk(False).segments[0]['t1']
    ok(all(e['time'] <= t1 and e['position'][2] > .110 for e in a.events))
    near(sum(e['volume'] for e in a.events), a.removed_volume, 1e-13)


def fixture_and_invalid_jobs():
    """rotary fixture is a separate shared assembly and invalid jobs do not leave a stock object"""
    reset()
    fixture = make_robot('rotary_fixture', textures=False)
    fixture.sample('joints', 2)
    near(fixture.state['rotary_output'], fixture.state['rotary_chuck'], 1e-12)
    fixture.set_joints({'rotary_output': 1.2})
    near(fixture.state['rotary_chuck'], 1.2, 1e-12)
    rejects(lambda: fixture.set_joints({'rotary_output': .1, 'rotary_chuck': .5}), 'same A-axis')
    near(fixture.state['rotary_output'], 1.2, 1e-12)
    fixture.dispose()
    r = make_robot('cnc_rotary', textures=False)
    base = r.roots['gantry_base']
    before = len(base.children)
    count = len(bpy.data.objects)
    ok(r.machine['cutter']['kind'] == 'flat' and r.roots.get('rotary_chuck') and r.roots.get('rotary_output'))
    ok(not any(n.startswith('cnc_toe_clamp') for n in r.roots))
    cache = os.path.join(OUT, 'js_tests_cache')
    for options in ({'duration': 0}, {'axis_x': .04}, {'start': -.060}):
        rejects(lambda: rotary_carve(r, sample_rotary, angles=16, sample_step=.004, stepdown=.006, cache_dir=cache,
                                     **options), 'duration|calibrated|renderer')
    # Blender's own refusals (the stock grid, the chip pool, a cache folder relative to an unsaved file) are made
    # before the scene changes too
    for options in ({'resolution': (10, 10, 10), 'cache_dir': cache}, {'max_particles': -1, 'cache_dir': cache},
                    {'cache_dir': '//relative_to_an_unsaved_file'}):
        rejects(lambda: rotary_carve(r, sample_rotary, angles=16, sample_step=.004, stepdown=.006, **options),
                'resolution|maxParticles|cache_dir')
    ok(len(base.children) == before and len(bpy.data.objects) == count, 'An invalid job left objects behind')
    # the WebGPU {} case was refused for its uninitialised renderer; here it is a valid job: it builds, and its
    # dispose() leaves the machine and the file as they were
    job = rotary_carve(r, sample_rotary, angles=16, sample_step=.004, stepdown=.006, cache_dir=cache)
    ok(len(bpy.data.objects) > count)
    job.dispose(files=True)
    ok(len(base.children) == before and len(bpy.data.objects) == count, 'dispose() left objects behind')
    r.dispose()


# ======================================================================================= rotary_mesh_test.mjs ===

def _mesh_object(name, verts, faces, location=(0, 0, 0), parent=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    if parent is not None:
        ob.parent = parent
    return ob


def _box(size):
    sx, sy, sz = (v / 2 for v in size)
    v = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def _cylinder_x(r, length, n):
    """three's CylinderGeometry(r, r, length, n, 1) turned onto the X axis (rotation.z = pi / 2)"""
    v, f = [], []
    for side in (-length / 2, length / 2):
        for k in range(n):
            a = 2 * math.pi * k / n
            v.append((side, r * math.sin(a), r * math.cos(a)))
    for k in range(n):
        f.append((k, (k + 1) % n, n + (k + 1) % n, n + k))
    f.append(tuple(range(n - 1, -1, -1)))
    f.append(tuple(range(n, 2 * n)))
    return v, f


def mesh_translated_details():
    """mesh CNC uses translated off-axis details and lateral tool travel; protects narrow features"""
    reset()
    group = bpy.data.objects.new('group', None)
    bpy.context.scene.collection.objects.link(group)
    _mesh_object('body', *_cylinder_x(.011, .060, 28), parent=group)
    ridge = _mesh_object('ridge', *_box((.045, .00008, .002)), location=(.002, -.0031, .012), parent=group)
    bpy.context.view_layer.update()
    o = dict(fit=False, angles=4, grid_step=.00065, sample_step=.003, stepover=.0035, stepdown=.006)
    p = rotary_program(group, **o)
    geometry = source_geometry(group)
    pos = geometry.triangles.reshape(-1, 3)
    ok(p.report.source['triangles'] == len(pos) // 3)
    ok(len({round(v['position'][1], 5) for v in p.moves if v['type'] == 'cut'}) > 8, 'Missing lateral rasters')
    bounds = {'min': (-.07, -.027, -.027), 'max': (.07, .027, .027)}
    index = index_rotary_sweeps(p.path, p.settings, bounds, (32, 16, 16), 0)
    worst, queries = math.inf, 0
    for q in pos:
        b = [math.floor((q[k] - bounds['min'][k]) / index.cell[k]) for k in range(3)]
        for sid in index.bins[b[0] + 32 * (b[1] + 16 * b[2])]:
            queries += 1
            worst = min(worst, sweep_distance(q, p.path.segments[sid], .003, .018, 1, 'flat'))
    ok(queries > 100, 'Independent surface queries absent')
    ok(worst >= -1e-8, f'Source was gouged by {-worst}')
    ridge.location.y = .005                                          # three's ridge.position.z = -.005
    bpy.context.view_layer.update()
    changed = rotary_program(group, **o)
    ok([dict(m) for m in p.moves] != [dict(m) for m in changed.moves], 'Input changed but toolpath did not')
    ok(all(v['type'] != 'index' or v['position'][2] >= p.settings.safe for v in p.moves))


def flat_endmill_membership():
    """flat endmill sweep has a flat tip and agrees with independent moving cylinder membership"""
    for angle in (0, .65):
        for delta in ((.016, 0), (.016, .009), (0, -.011)):
            s3 = {'a': (-.008, .007, .002), 'b': (-.008 + delta[0], .007 + delta[1], .002), 'a0': angle}
            s = {'a': (s3['a'][0], -s3['a'][2], s3['a'][1]), 'b': (s3['b'][0], -s3['b'][2], s3['b'][1]), 'a0': angle}
            seed = 17
            f = np.arange(4001) / 4000
            for _n in range(240):
                vals = []
                for _k in range(3):
                    seed = (seed * 16807) % 2147483647
                    vals.append(seed / 2147483647)
                point3 = (-.015 + vals[0] * .040, -.004 + vals[1] * .043, -.012 + vals[2] * .026)
                q = (point3[0], math.cos(angle) * point3[1] - math.sin(angle) * point3[2],
                     math.sin(angle) * point3[1] + math.cos(angle) * point3[2])
                x = s3['a'][0] + delta[0] * f
                y = s3['a'][1] + delta[1] * f
                radial = np.hypot(q[0] - x, q[2] - .002) - .003
                vertical = np.maximum(y - q[1], q[1] - y - .018)
                distance = float(np.maximum(radial, vertical).min())
                point = (point3[0], -point3[2], point3[1])
                if abs(distance) > .00001:
                    ok((sweep_distance(point, s, .003, .018, 1, 'flat') < 0) == (distance < 0),
                       'Flat sweep membership mismatch')
    s = {'a': (0, 0, 0), 'b': (.01, 0, 0), 'a0': 0}
    ok(sweep_distance((.005, 0, -.0001), s, .003, .018, 1, 'flat') > 0)
    ok(sweep_distance((.005, -.0028, .0001), s, .003, .018, 1, 'flat') < 0)


def reach_limited_and_no_substitute():
    """mesh planner reports reach-limited material and never silently substitutes an example"""
    v, f = _box((.060, .005, .003))
    me = bpy.data.meshes.new('flat box')
    me.from_pydata(v, [], f)
    o = dict(fit=False, angles=4, grid_step=.001, sample_step=.005, stepover=.004, stepdown=.008)
    p = rotary_program(me, **o)
    ok(p.target is me and p.report.reach_limited_samples > 0)
    rejects(lambda: rotary_program(me, **o, require_reach=True), 'reach')
    rejects(lambda: rotary_program({'sample': 'fake'}, **o), 'Supply')


# ====================================================================================== rotary_mount_test.mjs ===

def studs_engage_nuts():
    """rotary fixture studs engage actual T-slot nuts and retain visible nut floors"""
    reset()
    r = make_robot('cnc_rotary', textures=False)
    bpy.context.view_layer.update()
    fixture = r.roots['rotary_fixture']
    inv = fixture.matrix_world.inverted()
    fixings = [(x, z) for x in (-.18375, -.1275) for z in (-.070, .070)] + \
              [(x, z) for x in (.04125, .15375) for z in (-.060, .060)]

    def box(objs):
        lo, hi = Vector((math.inf,) * 3), Vector((-math.inf,) * 3)
        for ob in objs:
            m = inv @ ob.matrix_world
            for v in ob.data.vertices:
                p = m @ v.co
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
        return lo, hi
    for j, (x, z) in enumerate(fixings):
        nuts, studs = r.part('RC table T-nut %d' % j), r.part('RC table stud %d' % j)
        ok(nuts and studs, 'Missing nut/stud %d' % j)
        nlo, nhi = box(nuts)
        slo, shi = box(studs)
        ok(abs(nlo.x - x + .007) < 2e-7 and abs(nhi.x - x - .007) < 2e-7, 'Nut width / slot centre mismatch')
        ok(abs(nhi.z + .008) < 2e-7 and abs(nlo.z + .014) < 2e-7, 'Nut is not inside the slot undercut')
        ok(slo.z < -.0129 and shi.z > .0019, 'Stud lacks nut engagement or continuous slot crossing')
        ok(min(abs(x + .015 - k * .05625) for k in (-3, -2, -1, 0, 1, 2, 3)) < 1e-9, 'Missing bed slot')
        p = fixture.matrix_world @ Vector((x, z - .008, -.016))         # three's (x, -.016, -z + .008)
        hit = cast(nuts, p, fixture.matrix_world.to_3x3() @ Vector((0, 0, 1)))
        ok(hit and abs(hit[0] - .002) < 2e-7, 'Visible nut underside missing')
    ok(r.machine['cutter']['kind'] == 'flat' and r.part('SP two flute cutter'), 'Original cutter not restored')
    r.dispose()


for name, fn in (('rotary_test: ' + adjustable_blanks.__doc__, adjustable_blanks),
                 ('rotary_test: ' + centre_seat.__doc__, centre_seat),
                 ('rotary_test: ' + metal_presets.__doc__, metal_presets),
                 ('rotary_test: ' + retracts_and_stationary_index.__doc__, retracts_and_stationary_index),
                 ('rotary_test: ' + swept_capsule.__doc__, swept_capsule),
                 ('rotary_test: ' + sculpture_not_gouged.__doc__, sculpture_not_gouged),
                 ('rotary_test: ' + removal_first_engagement.__doc__, removal_first_engagement),
                 ('rotary_test: ' + fixture_and_invalid_jobs.__doc__, fixture_and_invalid_jobs),
                 ('rotary_mesh_test: ' + mesh_translated_details.__doc__, mesh_translated_details),
                 ('rotary_mesh_test: ' + flat_endmill_membership.__doc__, flat_endmill_membership),
                 ('rotary_mesh_test: ' + reach_limited_and_no_substitute.__doc__, reach_limited_and_no_substitute),
                 ('rotary_mount_test: ' + studs_engage_nuts.__doc__, studs_engage_nuts)):
    test(name, fn)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
