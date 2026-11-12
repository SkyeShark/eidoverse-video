"""The options the WebGPU tests do not reach, exercised one by one (no render): each changes what it should, or is
refused with the original's message.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/test_options.py
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.characters.robotics import make_robot  # noqa: E402
from eidoblend.fabrication import three_geometry as tg  # noqa: E402
from eidoblend.fabrication._nodes import modifier_input  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
check, near, rejects = U.check, U.near, U.rejects
box = tg.make_object('box', tg.box(1, 1, 1))
bpy.context.view_layer.update()

# --- source snapshots ----------------------------------------------------------------------------------------------
col = bpy.data.collections.new('parts')
bpy.context.scene.collection.children.link(col)
a = tg.make_object('part a', tg.box(.01, .01, .01), position=(-.02, .005, 0), collection=col)
b = tg.make_object('part b', tg.box(.01, .01, .01), position=(.02, .005, 0), collection=col)
bpy.context.view_layer.update()
g = fab.source_geometry(col)
check('a Collection is a source: both parts, two ranges', len(g.manufacturing_source['ranges']) == 2
      and near(g.bounding_box[0][0], -.025, 1e-7) and near(g.bounding_box[1][0], .025, 1e-7))
b.hide_render = True
check('visible_only leaves hidden parts out (and keeps them with visible_only=False)',
      len(fab.source_geometry(col).manufacturing_source['ranges']) == 1
      and len(fab.source_geometry(col, visible_only=False).manufacturing_source['ranges']) == 2)
b.hide_render = False
ok_, msg = rejects(lambda: fab.source_geometry(col, max_triangles=12), ['budget'])
check('max_triangles is a hard budget', ok_, msg)
ok_, msg = rejects(lambda: fab.source_geometry(col, space='parent'), ['world or local'])
check('space must be world or local', ok_, msg)
fit = fab.fit_source_geometry(col, bounds=((-.01, -.01, 0), (.01, .01, .01)))
check('fit into bounds: uniform, centred', near(fit.bounding_box[1][0] - fit.bounding_box[0][0], .02, 1e-8)
      and near(fit.bounding_box[0][2], .005 - .002, 1e-8) and near(fit.manufacturing_source['fit']['scale'], .4, 1e-8),
      f"scale {fit.manufacturing_source['fit']['scale']:.6f}, box {np.round(fit.bounding_box[0], 6)} .. "
      f"{np.round(fit.bounding_box[1], 6)}")

# --- slicing and printing ------------------------------------------------------------------------------------------
lo = fab.slice_geometry(box, size=.008, travel_lift=.0012)
hi = fab.slice_geometry(box, size=.008, travel_lift=.004)
top = lambda s: max(p['position'][2] for p in s['points'] if p['type'] == 'rapid')  # noqa: E731
check('travel_lift raises the travel moves', near(top(hi) - top(lo), .0028, 1e-9))
c = fab.slice_geometry(box, size=.008, center=(.03, -.02))
xs = np.array([p['position'][:2] for p in c['points'] if p['type'] == 'extrude'])
check('center places the part on the bed', near(xs[:, 0].mean(), .03, .001) and near(xs[:, 1].mean(), -.02, .001))
dense = fab.slice_geometry(box, size=.008, infill=1.0, solid_layers=0)
sparse = fab.slice_geometry(box, size=.008, infill=.1, solid_layers=0)
length = lambda s: sum(math.dist(s['points'][i - 1]['position'], s['points'][i]['position'])  # noqa: E731
                       for i in range(1, len(s['points'])) if s['points'][i]['type'] == 'extrude')
check('infill sets the deposited length', length(dense) > 2 * length(sparse),
      f'{length(dense):.3f} vs {length(sparse):.3f} m')
for bad, words in (({'infill': 1.5}, ['Infill']), ({'solid_layers': -1}, ['solidLayers']), ({'size': 0}, ['size'])):
    ok_, msg = rejects(lambda: fab.slice_geometry(box, **bad), words)
    check(f'slice_geometry refuses {bad}', ok_, msg)
p = make_robot('fdm')
job = fab.print(p, box, size=.008, retract_length=.0016, retract_speed=.02, fan_rpm=1200)
dw = [s for s in job.path.spans if s.type == 'retract']
check('retract_length / retract_speed set the dwells', dw and near(dw[0].t1 - dw[0].t0, .0016 / .02, 1e-12)
      and near(job.path.retract_length, .0016, 1e-12))
job.seek(job.duration / 2)
fan = p.roots['extruder_fan']
rest_q = p.rest[fan.name].to_quaternion()
angle = rest_q.rotation_difference(fan.matrix_basis.to_quaternion()).angle
expect = (job.state.time * 1200 / 60 * 2 * math.pi) % (2 * math.pi)
check('fan_rpm turns the fan on the physical clock', near(min(angle, 2 * math.pi - angle),
                                                          min(expect, 2 * math.pi - expect), 1e-4))
job.dispose()
for bad, words in (({'fan_rpm': -1}, ['fanRpm']), ({'plate_width': .5}, ['PEI sheet']),
                   ({'plate_depth': .6}, ['PEI sheet'])):
    ok_, msg = rejects(lambda: fab.print(p, box, size=.008, **bad), words)
    check(f'print refuses {bad}', ok_, msg)
ok_, msg = rejects(lambda: fab.print(p, box, size=.008, center=(.222, 0)), ['unobstructed area', 'physical bed', 'travel'])
check('a print off the sheet is refused', ok_, msg)
spec = fab.slice_geometry(box, size=.008)
from_spec = fab.print(p, spec, color='#e04b2e')
check('a slice spec prints as it is', from_spec.layers == spec['layers'])
from_spec.dispose()

# --- milling ---------------------------------------------------------------------------------------------------
c = make_robot('cnc')
ok_, msg = rejects(lambda: fab.mill(c, None, cutter='ball'), ['does not match'])
check('a ball nose is refused on the flat-end CNC', ok_, msg)
ok_, msg = rejects(lambda: fab.mill(c, None, stock_depth=.2), ['toe clamps'])
check('the toe clamps refuse a stock they cannot hold', ok_, msg)
own = fab.mill(c, None, stock_depth=.2, workholding=False, resolution=32, effects=False, material='wood')
check('workholding=False hides the clamps while the job lives; effects=False makes no debris',
      all(r.hide_render for r in own.workholding) and own.effects is None)
own.dispose()
check('disposing restores the clamps', all(not r.hide_render for r in own.workholding))
nodust = fab.mill(c, None, material='wood', resolution=32, effects={'dust': False, 'max_particles': 300, 'seed': 11})
check("effects={'dust': False} keeps shavings without fines", [pl.name for pl in nodust.effects.pools] == ['Wood shavings']
      and nodust.effects.particle_count == 300)
nodust.dispose()
pocket = fab.mill(c, None, material='aluminum', resolution=48, width=.03, depth=.05, stepover=.002, cut_depth=.002,
                  clearance=.01, effects=False)
xs = np.array([s.b for s in pocket.path.segments if s.type == 'cut'])
check('pocket width / depth / cut_depth reach the program', near(xs[:, 0].max(), .015 - .003, 1e-9)
      and near(xs[:, 1].max(), .025 - .003, 1e-9) and near(xs[:, 2].min(), .018, 1e-9))
pocket.set_color('#c08a3e')
check('set_color tints the stock finish', all(near(a, b, 1e-6) for a, b in zip(
    pocket.finish.tint.outputs[0].default_value[:3], fab.cutting.color_linear('#c08a3e'))))
pocket.dispose()
fast = fab.mill(c, None, material='aluminum', resolution=32, effects=False, rapid=.2, acceleration=.5, feed=.01)
slow = fab.mill(c, None, material='aluminum', resolution=32, effects=False)
check('feed / rapid / acceleration shorten the physical time', fast.physical_duration < slow.physical_duration * .6,
      f'{fast.physical_duration:.0f} vs {slow.physical_duration:.0f} s')
fast.dispose()
slow.dispose()

# --- relief inputs -------------------------------------------------------------------------------------------------
r = make_robot('cnc_relief')
cols, rows = 40, 60
xx, yy = np.meshgrid((np.arange(cols) / (cols - 1) - .5) * .078, (np.arange(rows) / (rows - 1) - .5) * .128)
field = {'width': .078, 'depth': .128, 'columns': cols, 'rows': rows,
         'heights': (.008 + .006 * np.exp(-(xx ** 2 + yy ** 2) / .0004)).ravel()}
hf = fab.carve(r, field, resolution=32, sample_step=.003, stepover=.002, effects=False)
check('carve takes a sampled heightfield', hf.program['stages'][-1]['name'] == 'finish' and hf.removal.removed_volume > 0)
hf.dispose()
dome = tg.make_object('dome', tg.capsule(.006, .0, 8, 24), position=(0, .012, 0))      # a ball, 6 .. 18 mm up
bpy.context.view_layer.update()
mesh = fab.carve(r, dome, resolution=32, sample_step=.003, stepover=.002, effects=False, floor=.005)
check('carve takes a mesh in stock coordinates', mesh.removal.removed_volume > 0 and mesh.program['stages'][-1]['name'] == 'finish')
mesh.dispose()
for bad, words in (({'stepover': .005}, ['unsupported strips']), ({'sample_step': .004}, ['sample step']),
                   ({'surface_tolerance': .001}, ['tolerance']), ({'width': .08}, ['inside the stock'])):
    ok_, msg = rejects(lambda: fab.relief_program(fab.sample_relief, **bad), words)
    check(f'relief_program refuses {bad}', ok_, msg)
ok_, msg = rejects(lambda: fab.relief_program(lambda x, y: .0005), ['1 mm or more above the bed'])
check('relief heights under 1 mm are refused', ok_, msg)
ok_, msg = rejects(lambda: fab.relief_program(fab.sample_relief, flute_length=.01), ['flute length'])
check('a relief deeper than the flutes is refused', ok_, msg)


def worst_gouge(prog, xs, ys):
    """how far the program's swept ball cuts below its own target, over the grid xs x ys of stock points"""
    target = prog['target']
    gx, gy = np.meshgrid(xs, ys)
    h = np.full(gx.shape, .02)
    P = prog['points']
    for i in range(1, len(P)):
        if P[i]['type'] != 'cut':
            continue
        a, b = P[i - 1]['position'], P[i]['position']
        i0, i1 = np.searchsorted(xs, min(a[0], b[0]) - .003), np.searchsorted(xs, max(a[0], b[0]) + .003, 'right')
        j0, j1 = np.searchsorted(ys, min(a[1], b[1]) - .003), np.searchsorted(ys, max(a[1], b[1]) + .003, 'right')
        if i0 < i1 and j0 < j1:
            sub = (slice(j0, j1), slice(i0, i1))
            h[sub] = np.minimum(h[sub], fab.swept_cutter_height_np(gx[sub], gy[sub], a, b, .003, 'ball'))
    want = target.many(gx, gy) if hasattr(target, 'many') else np.vectorize(target)(gx, gy)
    return float((want - h).max())


# lift_over_steps (this edition's option): a smooth relief's program is unchanged; a walled mesh stops being gouged
same = fab.relief_program(fab.sample_relief, lift_over_steps=True, sample_step=.002, stepover=.0016)
base = fab.relief_program(fab.sample_relief, sample_step=.002, stepover=.0016)
check('lift_over_steps leaves a smooth relief\'s program exactly as the WebGPU planner makes it',
      [p['position'] for p in same['points']] == [p['position'] for p in base['points']], f"{len(base['points'])} points")
# the bracket as the inspector carves a supplied mesh (viewer.js: fitted into three's Box3 (-.032, .004, -.055) ..
# (.032, .019, .055)): 64 x 32 x 12.8 mm with vertical walls
bracket = fab.relief_from_mesh(fab.fit_source_geometry(fab.manufacturing_sample('bracket', as_parts=True),
                                                       bounds=((-.032, -.055, .004), (.032, .055, .019))))
gx, gy = np.linspace(-.03, .03, 121), np.linspace(-.054, .054, 217)
g_plain = worst_gouge(fab.relief_program(bracket), gx, gy)
g_lift = worst_gouge(fab.relief_program(bracket, lift_over_steps=True), gx, gy)
check('lift_over_steps keeps the cutter out of a walled mesh (the plain planner cuts in, as the WebGPU one does)',
      g_plain > .003 and g_lift < .00025, f'worst gouge {g_plain * 1000:.2f} mm plain, {g_lift * 1000:.3f} mm lifted')


def walled(x, y):
    """a height function with walls of no width: a 16 mm block on a 6 mm land, and a 10 mm step across a diagonal"""
    if abs(x) < .012 and abs(y) < .02:
        return .016
    return .010 if x + 0.6 * y > .02 else .006


# measured off the walls' own lines (a grid point on a wall reads either side of the jump)
fx, fy = np.linspace(-.03, .03, 241) + 1.37e-5, np.linspace(-.054, .054, 433) + 1.91e-5
f_plain = worst_gouge(fab.relief_program(walled), fx, fy)
f_lift = worst_gouge(fab.relief_program(walled, lift_over_steps=True), fx, fy)
check('lift_over_steps keeps the cutter out of a height function\'s walls too: its rim read where this sample\'s or a '
      'neighbouring sample\'s ball rides a wall, its moves checked every 0.1 mm',
      f_plain > .005 and f_lift < .00025, f'worst gouge {f_plain * 1000:.2f} mm plain, {f_lift * 1000:.3f} mm lifted')

# the slicer's union snaps near-equal coordinates as polygon-clipping's rounder does
from eidoblend.fabrication.polygon_union import CoordRounder, union  # noqa: E402
rd = CoordRounder()
snapped = [rd.round(v) for v in (1.0, 1.0 + 2 ** -52, 2.0, 2.0 - 2 ** -52, 1e-17, -1e-17, 1.5)]
check(f'CoordRounder: values an ulp from one seen before take it, values within EPSILON of zero are zero ({snapped})',
      snapped == [1.0, 1.0, 2.0, 2.0, 0.0, 0.0, 1.5])
x0, x1 = .1, float(np.nextafter(.1, 1.0))
left = [[(0.0, 0.0), (x0, 0.0), (x0, .1), (0.0, .1), (0.0, 0.0)]]
right = [[(x1, 0.0), (.2, 0.0), (.2, .1), (x1, .1), (x1, 0.0)]]
u = union(left, right)
check(f'two squares an ulp apart unite into one rectangle of four corners ({[len(r) - 1 for p in u for r in p]} corners)',
      len(u) == 1 and len(u[0]) == 1 and len(u[0][0]) == 5)
cols, rows = 129, 193
sx, sy = np.meshgrid((np.arange(cols) / (cols - 1) - .5) * .078, (np.arange(rows) / (rows - 1) - .5) * .128)
smooth = {'width': .078, 'depth': .128, 'columns': cols, 'rows': rows,
          'heights': np.vectorize(fab.sample_relief)(sx, sy).ravel()}
check('lift_over_steps leaves a smooth sampled heightfield\'s program unchanged too (the rim never has to lift it)',
      [p['position'] for p in fab.relief_program(smooth, lift_over_steps=True, sample_step=.002, stepover=.0016)['points']]
      == [p['position'] for p in fab.relief_program(smooth, sample_step=.002, stepover=.0016)['points']])


def last_rough_floor(prog):
    """the lowest cut of the last roughing stage, where the tip runs on its level (the allowance above the deepest)"""
    st = [s for s in prog['stages'] if s['name'].startswith('rough')][-1]
    return min(p['position'][2] for p in prog['points'][st['start_index']:st['end_index'] + 1] if p['type'] == 'cut')


coarse = dict(sample_step=.002, stepover=.0016)
thin, thick = (fab.relief_program(fab.sample_relief, rough_allowance=v, **coarse) for v in (.0005, .0015))
check('rough_allowance raises the last roughing level by the extra allowance',
      near(last_rough_floor(thick) - last_rough_floor(thin), .001, 1e-9),
      f'{last_rough_floor(thin) * 1000:.3f} -> {last_rough_floor(thick) * 1000:.3f} mm')

# --- the rotary names fabrication.js re-exports, forwarded to the rotary machine's own package ---------------------
from eidoblend.fabrication import rotary  # noqa: E402
names = ('rotary_carve', 'rotary_program', 'rotary_mesh_program', 'sample_rotary', 'rotary_surface')
check('fab.rotary_carve / rotary_program / rotary_mesh_program / sample_rotary / rotary_surface are the rotary package\'s',
      all(getattr(fab, n) is getattr(rotary, n) for n in names) and fab.FabSim.sample_rotary() is rotary.sample_rotary)

# --- play(start, speed): playback time = (seconds since the first frame - start) * speed -------------------------
scene = bpy.context.scene
scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end = 24, 1.0, 1, 73
pr = make_robot('fdm')
pj = fab.print(pr, box, size=.008, infill=.3, duration=4)
pj.play(start=1.0, speed=2.0)
ok = True
for f in (1, 13, 25, 37, 49):
    scene.frame_set(f)
    keyed = modifier_input(pj.mesh.modifiers['fabrication'], 'Progress').value
    t = max(0.0, ((f - 1) / 24 - 1.0) * 2.0)
    want = pj.path.sample(min(t, 4) / 4 * pj.path.duration).distance
    ok &= near(keyed, want, 1e-6 * max(1.0, want))
check('play(start=1, speed=2) keys playback second (t - 1) * 2 at every frame', ok)
pj.stop()
pj.dispose()

# --- tubing helpers ------------------------------------------------------------------------------------------------
loop = fab.service_loop((0, 0, 0), (.1, 0, 0), .3)
check('service_loop makes a cubic of the asked length, handles raised along up',
      near(fab.bezier_length(loop), .3, 1e-6) and loop[1][2] > 0 and near(loop[1][2], loop[2][2], 1e-12),
      f'{fab.bezier_length(loop) * 1000:.3f} mm, handles {loop[1][2] * 1000:.1f} mm up')
side = fab.service_loop((0, 0, 0), (.1, 0, 0), .3, up=(0, 1, 0))
check('service_loop follows another up', side[1][1] > 0 and near(side[1][2], 0, 1e-12))
ok_, msg = rejects(lambda: fab.service_loop((0, 0, 0), (.1, 0, 0), .1), ['too short'])
check('a tube shorter than its span is refused', ok_, msg)
from eidoblend.characters.robotics import RoboticsKit  # noqa: E402
kt = RoboticsKit.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .1), (.05, 0, .1), (.05, 0, 0)])
check("the kit's RoboticsKit.create_ptfe_tube / service_loop are this package's (facade.FABRICATION)",
      isinstance(kt, fab.PTFETube) and near(fab.bezier_length(RoboticsKit.service_loop((0, 0, 0), (.1, 0, 0), .3)), .3, 1e-6))
kt.dispose()
spool = make_robot('spool')
check('a dispenser loaded after the import has its live filament at load (the INSTALLERS hook)',
      spool.filament is not None and len(spool.filament.curves) == 1 and spool.filament.payout is not None,
      f'{len(spool.filament.curves)} strand, payout row {spool.filament.payout.row:.2f}' if spool.filament else 'none')
check("the dispenser's filament-feed sample turns the reel",
      spool.sample('filament-feed', 4.0) is not None and near(spool.filament.consumed_length, .1, 1e-12))
route = fab.direct_feed_route((-.3, .1, .5), (0, 0, .2), (0, 0, -1))
check('direct_feed_route: two joined supply cubics ending on the seated liner, the liner on the inlet',
      np.allclose(route['strands'][0][3], route['strands'][1][0]) and np.allclose(route['strands'][1][3], route['entry'][0][0])
      and np.allclose(route['entry'][1][3], (0, 0, .2)) and near(fab.bezier_length(route['entry'][0]), .080, 1e-9))
ok = U.summary('options')
sys.exit(0 if ok else 1)
