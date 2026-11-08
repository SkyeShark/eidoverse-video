"""fabrication_feed_test.mjs ported: filament, tubing and material-aware CNC checks, with the same assertions.

All nine Deno tests, in their order (numbered below): 1 the reel payout, 2 frameCamera framing, 3 the dispenser
inside the assembled printer and loadPart extraction, 4 one physical clock for extrusion, retraction and the reel,
5 the seated PTFE entries, 6 wood and metal milling, 7 the authored build surfaces and process datums, 8 the shared
ball-tool / fixture atlas, 9 air cuts and rapid collisions; then the facade and the keyed playback, which the
Blender edition adds. Tests 2, 3, 7 and 8 check the robotics kit's assets through eidoblend.characters.robotics.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/test_fabrication_feed.py
"""
import json
import math
import os
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.characters.robotics import catalog, load_part, make_robot  # noqa: E402
from eidoblend.characters.robotics.io import ROOT as KIT_ROOT  # noqa: E402
from eidoblend.characters.robotics.studio import frame_camera, make_camera  # noqa: E402
from eidoblend.fabrication import three_geometry as tg  # noqa: E402
from eidoblend.fabrication.machine import world_matrix  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
check, near, rejects = U.check, U.near, U.rejects


def unit_box():
    return tg.make_object('unit box', tg.box(1, 1, 1))


# 1. payout stays embedded and continuous through full reel traversal and on the standalone dispenser
for rid in ('fdm', 'spool'):
    r = make_robot(rid, textures=False)
    f = fab.ensure_filament(r)
    ok_depth = ok_row = ok_jump = True
    previous = None
    length = 0.0
    worst = 0.0
    while length <= 32 + 1e-9:
        f.seek(length)
        p = f.curves[0].sample(0)
        info = f.payout
        ok_depth &= 0 < info.embedded_depth < .000875
        ok_row &= .5 < info.row < 28.5
        if previous is not None:
            worst = max(worst, float(np.linalg.norm(p - previous)))
        previous = p
        length += .01
    ok_jump = worst < .0002
    f.seek(.17)
    p = f.curves[0].sample(0)
    f.seek(20)
    f.seek(.17)
    check(f'{rid}: payout embedded in the winding (0 .. 0.875 mm) and inside the pack rows', ok_depth and ok_row)
    check(f'{rid}: payout never jumps at a winding boundary (32 m of feed)', ok_jump, f'largest step {worst * 1000:.4f} mm')
    check(f'{rid}: payout replays exactly', float(np.linalg.norm(p - f.curves[0].sample(0))) < 1e-10)

# 2. framing fits wide machine rows and narrow modules without clipping (three's sizes and direction, Blender axes)
scene = bpy.context.scene
for size, (rx, ry) in (((3, .8, .7), (1920, 1080)), ((.2, .32, .17), (650, 1000))):
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    cam = make_camera(36, 'framing camera', scene)
    half = Vector((size[0], size[2], size[1])) * .5                 # three (x, y, z) -> Blender (x, z-extent, y-extent)
    frame_camera(cam, [(-half, half)], direction=Vector((-.55, -1.2, .75)), margin=1.1)
    bpy.context.view_layer.update()
    proj = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=rx, y=ry)
    pv = proj @ cam.matrix_world.inverted()
    inside, extent = True, 0.0
    for x in (-half.x, half.x):
        for y in (-half.y, half.y):
            for z in (-half.z, half.z):
                h = pv @ Vector((x, y, z, 1.0))
                q = Vector((h.x / h.w, h.y / h.w, h.z / h.w))
                inside &= abs(q.x) < 1 and abs(q.y) < 1 and abs(q.z) < 1
                extent = max(extent, abs(q.x), abs(q.y))
    check(f'frame_camera fits a {size} box at aspect {rx / ry:.2f} without clipping, not loosely', inside and extent > .85,
          f'largest |ndc| {extent:.3f}')
    bpy.data.objects.remove(cam)

# 3. the dispenser shares its atlas in the assembled printer and preserves exact part extraction
cat = catalog()
p = make_robot('fdm', textures=False)
s = make_robot('spool', textures=False)
fp, fs = fab.ensure_filament(p), fab.ensure_filament(s)
parts = p.parts()
check('the printer carries the fixture bed, not the bare filament inlet',
      'G430 interchangeable fixture bed' in parts and 'EX filament inlet' not in parts)
check('the push fitting rides the extruder; the carrier stands on the filament stand',
      p.roots['fdm_push_fitting'].parent == p.roots['extruder_fixed']
      and p.roots['filament_carrier'].parent == p.roots['filament_stand'])
check('no separate tube support; the dispenser foot and spine stay out of the printer',
      'fdm_tube_support' not in p.roots and 'FP dispenser foot' not in parts and 'FP swept dispenser spine' not in parts)
check('the live supply filament is one of the printer\'s parts', 'FP free supply filament' in parts)
check('the printer entry lists each part once', len(set(p.entry['parts'])) == len(p.entry['parts']))
missing = [n for n in cat['models']['manufacturing/filament_spool']['parts']
           if (n not in ('FP dispenser foot', 'FP swept dispenser spine') and n not in parts) or n not in s.parts()]
check('every dispenser part is in the printer (but its foot and spine) and in the dispenser', not missing, str(missing))
part = load_part('spool', 'FP front reel cheek', textures=False)
tris = part.stats()['triangles']
check('load_part extracts one part with its own triangles', len(part.parts()) == 1 and 0 < tris < 4404, f'{tris}')
before = tuple(p.palette.nodes['primary'].outputs[0].default_value)
fp.set_color('#dd6029')
check('filament recolour leaves the body primary', tuple(p.palette.nodes['primary'].outputs[0].default_value) == before)
check('two instances do not share a filament colour', tuple(fp.color) != tuple(fs.color))
part.dispose()
s.dispose()
p.dispose()

# 4. extrusion volume, retraction dwells, reel travel and replay use one physical clock
bpy.ops.wm.read_factory_settings(use_empty=True)
p = make_robot('fdm', textures=False)
g = unit_box()
j = fab.print(p, g, size=.008, infill=.3, duration=18)
d = p.filament.diameter
check('filament length x area = extruded volume', near(j.filament_length * math.pi * d * d / 4, j.extruded_volume, 1e-12))
dwells = [s for s in j.path.spans if s.type != 'move']
check('retract and prime dwells exist', any(s.type == 'retract' for s in dwells) and any(s.type == 'prime' for s in dwells))
ok = True
for s in dwells[:8]:
    a = j.path.sample(s.t0 + (s.t1 - s.t0) * .25)
    b = j.path.sample(s.t0 + (s.t1 - s.t0) * .75)
    ok &= near(a.speed, 0, 1e-7) and near(a.volume, b.volume, 1e-14) and math.dist(a.position, b.position) < 1e-7
    ok &= (b.filament_retraction > a.filament_retraction) if s.type == 'retract' else (b.filament_retraction < a.filament_retraction)
check('dwells hold the nozzle and the volume while the filament retracts / primes', ok)
j.seek(7)
saved = [p.filament.rotation, p.filament.consumed_length, *p.tool_tip()]
j.seek(18)
check('at the end the reel has paid out the whole print', near(p.filament.consumed_length, j.filament_length, 1e-7))
j.seek(7)
check('replay restores reel turn, consumed length and tool tip',
      all(near(a, b, 1e-7) for a, b in zip(saved, [p.filament.rotation, p.filament.consumed_length, *p.tool_tip()])))
j.set_color('#2c59bd')
bead = next(n for n in j.material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value
check('job colour = reel colour', all(near(a, b, 1e-6) for a, b in zip(bead[:3], p.filament.color[:3])))
physical = fab.print(p, g, size=.008, infill=.3)
check('without duration, playback is physical time', near(physical.duration, physical.physical_duration, 1e-9))
physical.seek(j.state.time)
check('physical replay meters the same filament', near(p.filament.consumed_length, j.state.filament_length, 1e-7))
ok_, msg = rejects(lambda: fab.print(p, g, filament_diameter=.00285), ['match', '1.75'])
check('a 2.85 mm filament is refused for the 1.75 mm reel', ok_, msg)
physical.dispose()
j.dispose()

# 5. short PTFE entries stay seated while the exposed feed follows travel without vertex uploads
bpy.ops.wm.read_factory_settings(use_empty=True)
p = make_robot('fdm', textures=False)
f = fab.ensure_filament(p)
fab.g430(p)
p.root.location = (.3, .2, .8)                             # three's position (.3, .8, -.2)
p.root.rotation_euler = Euler((.1, -.2, .6), 'XYZ')
p.root.scale = (1.2, 1.2, 1.2)
curves = f.tubes
lengths = [c.length for c in curves]
saved = [np.array([v.co[:] for v in c.mesh.data.vertices]) for c in curves]
ok_len = ok_seat = ok_cont = ok_norm = ok_tan = ok_guide = ok_total = True
worst_seat = worst_inlet = 0.0
for x in (-.19, 0, .19):
    for y in (-.235, 0, .235):
        for z in fab.g430(p).axis_limits[2]:
            p.axes([x, y, z])
            ok_total &= .14 < f.tube_length < .18
            ok_guide &= near(f.guide_tube.length, .034, 1e-8)
            ok_len &= all(near(c.length, lengths[i], 1e-6) for i, c in enumerate(curves))
            base_w = world_matrix(p.roots['gantry_base'])
            tube_end = base_w @ Vector(curves[-1].sample(1))
            inlet = world_matrix(p.roots['extruder_fixed']) @ Vector((0, 0, .115))
            worst_inlet = max(worst_inlet, (tube_end - inlet).length)
            sup, last = f.supplies[0], f.supplies[-1]
            ok_cont &= np.linalg.norm(curves[1].sample(1) - sup.sample(0)) < 1e-7
            ok_cont &= np.linalg.norm(last.sample(1) - curves[2].sample(0)) < 1e-7
            for k in range(1, len(f.supplies)):
                ok_cont &= np.linalg.norm(f.supplies[k - 1].sample(1) - f.supplies[k].sample(0)) < 1e-7
            for k in (1, 3):
                ok_cont &= np.linalg.norm(curves[k - 1].sample(1) - curves[k].sample(0)) < 1e-7
                ok_norm &= near(float(curves[k - 1].normal_at(1) @ curves[k].normal_at(0)), 1, 1e-7)
            start = base_w @ Vector(curves[0].sample(0))
            seat = world_matrix(p.roots['filament_stand']) @ Vector((.0415, -.155, .242))
            worst_seat = max(worst_seat, (start - seat).length)
            for a, b in ((curves[0], curves[1]), (curves[1], sup), (sup, last), (last, curves[2]), (curves[2], curves[3])):
                pa, pb = a.points, b.points
                ta = (pa[3] - pa[2]) / np.linalg.norm(pa[3] - pa[2])
                tb = (pb[1] - pb[0]) / np.linalg.norm(pb[1] - pb[0])
                ok_tan &= near(float(ta @ tb), 1, 1e-7)
check('the PTFE total stays 140..180 mm and the carrier liner 34 mm through 18 head positions', ok_total and ok_guide,
      f'{f.tube_length * 1000:.2f} mm')
check('each PTFE section keeps its length as the head moves', ok_len)
check('the head entry ends on the extruder inlet; the liner starts on the carrier seat',
      worst_inlet < 1e-6 and worst_seat < 1e-6, f'inlet {worst_inlet:.2e} m, seat {worst_seat:.2e} m')
check('sections and supply strands join end to end', ok_cont)
check('seated joints keep one normal and one tangent', ok_norm and ok_tan)
check('moving the head changes modifier inputs, never the tube meshes',
      all(np.array_equal(sv, np.array([v.co[:] for v in c.mesh.data.vertices])) for sv, c in zip(saved, curves)))
check('PTFE tubes are milky and partly transparent', all(
    c.material.surface_render_method == 'BLENDED' and 0 < next(n for n in c.material.node_tree.nodes if n.type ==
                                                                 'BSDF_PRINCIPLED').inputs['Alpha'].default_value < 1
    for c in curves))
check('a filament core runs inside every PTFE section', len(f.cores) == len(curves) and all(
    np.linalg.norm(c.sample(.5) - f.cores[i].sample(.5)) < 1e-9 for i, c in enumerate(curves)))
tube = fab.create_ptfe_tube(points=[tuple(v) for v in f.tubes[1].points])
check('a free tube measures its own cubic', near(tube.length, fab.bezier_length(tube.points), 1e-12))
ok_, msg = rejects(lambda: tube.set_points([(0, 0, 0), (0, 0, 0), (1, 0, 0), (2, 0, 0)]), ['Degenerate'])
check('a degenerate end tangent is refused', ok_, msg)
tube.dispose()

# 6. wood and metal keep material-specific feed and debris, with deterministic stock removal
bpy.ops.wm.read_factory_settings(use_empty=True)
c = make_robot('cnc', textures=False)
metal_duration = None
for material in fab.STOCK_MATERIALS:
    j = fab.mill(c, None, material=material, duration=18, resolution=64)
    names = [pl.name for pl in j.effects.pools]
    wood = fab.STOCK_MATERIALS[material]['kind'] == 'wood'
    ok = j.stock.removed_volume > 0 and all(e.volume > 0 for e in j.removal.events) and j.settings.material == material \
        and near(j.settings.rpm, fab.STOCK_MATERIALS[material]['rpm'], 1e-9) \
        and ('Wood shavings' if wood else 'Metal swarf') in names and ('Wood fines' in names) == wood
    j.seek(6)
    rot = c.roots['spindle_rotor'].matrix_basis.to_quaternion()
    j.seek(15)
    j.seek(6)
    ok &= rot.rotation_difference(c.roots['spindle_rotor'].matrix_basis.to_quaternion()).angle < 1e-6
    if material == 'aluminum':
        metal_duration = j.physical_duration
    if material == 'wood':
        ok &= j.physical_duration < metal_duration
    check(f'{material}: removal, rpm, debris kinds and spindle replay', ok,
          f'{j.stock.removed_volume * 1e6:.3f} cm3, {len(j.removal.events)} events, {names}, '
          f'{j.physical_duration:.0f} s')
    j.dispose()
for opts, words in (({'material': 'plastic'}, ['Unknown stock']), ({'flutes': 0}, ['flutes']),
                    ({'radius': .01}, ['3 mm radius']), ({'stock_width': 1}, ['physical bed'])):
    ok_, msg = rejects(lambda: fab.mill(c, None, **opts), words)
    check(f'mill refuses {opts}', ok_, msg)

# 7. authored build surfaces share one rectangular atlas and preserve process datums
bpy.ops.wm.read_factory_settings(use_empty=True)
cat = catalog()
p = make_robot('fdm', textures=False)
c = make_robot('cnc', textures=False)
fplate = make_robot('fdm_plate', textures=False)
mplate = make_robot('cnc_plate', textures=False)
images = [t for t in cat['textures'] if t['path'].startswith('textures/plates_')]
check('three plate maps, each 512 x 1024', len(images) == 3 and all(t['dimensions'] == [512, 1024] for t in images))
decks = [n for n in mplate.parts() if n.startswith('BP T-slot deck extrusion')]
check('the CNC plate has eight T-slot deck extrusions', len(decks) == 8, f'{len(decks)}')
ok_glb = True
for name in ('fdm_plate', 'cnc_plate', 'cnc_clamp', 'tube_support', 'push_fitting', 'fdm', 'cnc', 'cnc_relief'):
    with open(os.path.join(KIT_ROOT, cat['models']['manufacturing/' + name]['path']), 'rb') as fh:
        data = fh.read()
    size = struct.unpack_from('<I', data, 12)[0]
    glb = json.loads(data[20:20 + size].decode('utf-8'))
    plate_tex = [t for t in glb['textures'] if 'plates_' in (glb['images'][t['source']].get('uri') or '')]
    ok_glb &= len(plate_tex) >= 3 and all(
        ((glb['samplers'][t['sampler']].get('extras') or {}).get('eidoverse_anisotropy')) == 8 for t in plate_tex)
check('every assembly binds the plate maps with 8x anisotropic samplers', ok_glb)
check('the CNC carries no fixture bed', 'G430 interchangeable fixture bed' not in c.parts())
m = fab.g430(p)
bpy.context.view_layer.update()
inv = world_matrix(p.roots['gantry_base']).inverted()


def bed_box(objs, frame=inv):
    pts = np.array([tuple(frame @ (o.matrix_world @ v.co)) for o in objs for v in o.data.vertices])
    return pts.min(axis=0), pts.max(axis=0)


lo, hi = bed_box(p.part('BP removable PEI spring-steel sheet'))
check('the PEI sheet lies on the bed top, 0.65 mm thick, 458 mm wide, its pull tabs past the bed',
      near(lo[2], m.bed_top, 1e-6) and near(hi[2], m.bed_top + .00065, 1e-6)
      and near(lo[0], -.229, 1e-6) and near(hi[0], .229, 1e-6) and near(lo[1], -.298, 1e-6),
      f'z {lo[2]:.6f} .. {hi[2]:.6f}, x {lo[0]:.4f} .. {hi[0]:.4f}, y min {lo[1]:.4f}')
olo, ohi = bed_box(p.part('G430 interchangeable fixture bed'))
check('the original bed tops out at the bed datum; the sheet overhangs it, pull tabs 20 mm past its front',
      near(ohi[2], m.bed_top, 1e-6) and lo[0] < olo[0] and hi[0] > ohi[0] and lo[1] < olo[1] - .02,
      f'bed x {olo[0]:.4f} .. {ohi[0]:.4f}, front y {olo[1]:.4f}')
p.move_tool((0, 0, .00085))
check('move_tool / tool_tip round trip on the bed frame', near(p.tool_tip()[2], .00085, 1e-6))
mc = fab.g430(c)
cinv = world_matrix(c.roots['gantry_base']).inverted()
fixture = [o for o in [c.roots['cnc_fixture_plate']] + list(c.roots['cnc_fixture_plate'].children_recursive)
           if o.type == 'MESH']
flo, fhi = bed_box(fixture, cinv)
check('the CNC fixture plate tops out at its bed datum', near(fhi[2], mc.bed_top, 1e-6), f'{fhi[2]:.6f}')
deck_objs = [o for n in c.parts() if n.startswith('BP T-slot deck extrusion') for o in c.part(n)]
dg = bpy.context.evaluated_depsgraph_get()
verts, polys = [], []
for o in {o.name: o for o in deck_objs}.values():
    me = o.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    base_i = len(verts)
    verts += [tuple(o.matrix_world @ v.co) for v in me.vertices]
    polys += [tuple(base_i + i for i in t.vertices) for t in me.loop_triangles]
    o.evaluated_get(dg).to_mesh_clear()
deck = BVHTree.FromPolygons(verts, polys, all_triangles=True)
h0 = deck.ray_cast(Vector((0, 0, .1)), Vector((0, 0, -1)))[0]
h1 = deck.ray_cast(Vector((.025, 0, .1)), Vector((0, 0, -1)))[0]
check('a T-slot reads 38 mm at the centre and the deck 56 mm beside it',
      h0 is not None and h1 is not None and near(h0.z, .038, 1e-6) and near(h1.z, .056, 1e-6),
      f'{h0.z if h0 else None}, {h1.z if h1 else None}')
check('four toe clamps on the CNC', len([n for n in c.roots if n.startswith('cnc_clamp_')]) == 4)
g = unit_box()
j = fab.print(p, g, size=.008)
check('the job references the authored sheet', j.plate == p.roots['fdm_build_plate'])
j.dispose()
check('disposing the job keeps the shared hardware', p.roots['fdm_build_plate'].parent == p.roots['gantry_base'])
ok_, msg = rejects(lambda: fab.print(p, g, base=.012), ['removable PEI sheet'])
check('a custom base is refused while the sheet is fitted', ok_, msg)
custom = fab.print(p, g, base=.012, build_plate=False)
check('build_plate=False hides the sheet', p.roots['fdm_build_plate'].hide_render)
custom.dispose()
for r in (fplate, mplate, c, p):
    r.dispose()

# 8. ball tools and adjustable fixtures share their finished atlas across assemblies
maps = [t for t in cat['textures'] if t['path'].startswith('textures/rotary_workholding_')]
check('five rotary workholding maps, each 2048 x 2048', len(maps) == 5 and all(t['dimensions'] == [2048, 2048]
                                                                               for t in maps))
primary, ok_share = None, True
for name in ('ball_tool', 'rotary_fixture', 'cnc_relief', 'cnc_rotary'):
    robot = make_robot(name, textures=False)
    bindings = (robot.report.get('texture_bindings') or {}).get('rotary_workholding')
    ok_share &= bool(bindings) and len(bindings) == 5
    identity = json.dumps(sorted([k, bindings[k]['identity'], bindings[k]['uri']] for k in bindings)) if bindings else ''
    primary = primary or identity
    ok_share &= identity == primary
    robot.dispose()
check('the ball tool, rotary fixture, relief CNC and rotary CNC bind the same five finished maps', ok_share)

# 9. air cuts and repeated passes emit no false debris; rapid stock collisions are refused
opts = dict(width=.04, depth=.04, height=.02, radius=.003, resolution=128)


def path(points):
    return fab.FeedPath([{'position': U.t2b(q['position']), 'type': q['type']} for q in points], feed=.01, rapid=.08,
                        acceleration=.25, blend_tolerance=0)


air = fab.sample_removal(path([{'position': [-.01, .025, 0], 'type': 'rapid'}, {'position': [.01, .025, 0], 'type': 'cut'}]), **opts)
check('an air cut emits nothing', len(air.events) == 0)
pts = [{'position': [-.01, .03, 0], 'type': 'rapid'}, {'position': [-.01, .015, 0], 'type': 'cut'},
       {'position': [.01, .015, 0], 'type': 'cut'}]
first = fab.sample_removal(path(pts), **opts)
pts.append({'position': [-.01, .015, 0], 'type': 'cut'})
repeat = fab.sample_removal(path(pts), **opts)
check('a repeated pass removes nothing more and is not engaged', near(first.removed_volume, repeat.removed_volume, 1e-12)
      and not repeat.intervals[-1].engaged)
ok_, msg = rejects(lambda: fab.sample_removal(path([{'position': [-.01, .03, 0], 'type': 'rapid'},
                                                    {'position': [-.01, .015, 0], 'type': 'rapid'}]), **opts),
                   ['Rapid move intersects'])
check('a rapid through stock is refused', ok_, msg)
ok_, msg = rejects(lambda: fab.sample_removal(path([{'position': [0, .03, 0], 'type': 'rapid'},
                                                    {'position': [0, .001, 0], 'type': 'cut'}]), **opts), ['flute length'])
check('a cut below the flutes is refused', ok_, msg)

# the facade (fab_sim.js) and the job's keyed playback (play / stop / on_done / auto_play)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps, scene.frame_start, scene.frame_end = 24, 1, 49
F = fab.FabSim
check('FabSim: the material table, the relief sample, the pocket and relief planners, snapshots',
      F.stock_materials() is fab.STOCK_MATERIALS and F.sample_relief() is fab.sample_relief
      and len(F.pocket_program()) == len(fab.pocket_program()) and F.ready() is fab
      and len(F.relief_program(fab.sample_relief, sample_step=.003, stepover=.002, rough_stepover=.0024)['points']) > 0
      and F.source_geometry(tg.box(.01, .01, .01)).manufacturing_source['triangles'] == 12
      and abs(max(F.fit_source_geometry(tg.box(1, 2, 1), size=.02).size()) - .02) < 1e-12)
done = []
c = make_robot('cnc')
job = fab.CNCSim.mill(c, None, material='wood', duration=2, resolution=32, on_done=lambda j: done.append(j.time))
job.play()
scene.frame_set(25)
mid = fab.processes.modifier_input(job.mesh.modifiers['fabrication'], 'Progress').value
scene.frame_set(49)
end = fab.processes.modifier_input(job.mesh.modifiers['fabrication'], 'Progress').value
check('play keys the progress over the scene: half way at 1 s, the whole path at 2 s',
      0 < mid < end and near(end, job.path.length, 1e-3) and done and near(done[0], 2.0, 1e-9),
      f'progress {mid * 1000:.1f} / {end * 1000:.1f} mm of {job.path.length * 1000:.1f} mm; on_done at {done}')
job.stop()
scene.frame_set(25)
check('stop removes the keys (the pose stays)', near(fab.processes.modifier_input(job.mesh.modifiers['fabrication'],
                                                                                   'Progress').value, end, 1e-9))
job.dispose()
p = make_robot('fdm')
g = unit_box()
pj = fab.PrintSim.print(p, g, size=.008, infill=.3, duration=2, auto_play=True)
scene.frame_set(13)
check('auto_play keys the print at once', 0 < fab.processes.modifier_input(pj.mesh.modifiers['fabrication'],
                                                                          'Progress').value < pj.path.length)
ok = U.summary('feed')
sys.exit(0 if ok else 1)
