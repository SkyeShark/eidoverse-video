"""relief_test.mjs ported: relief compensation, swept stock and assembled machining, with the same assertions.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/test_relief.py
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
from eidoblend.fabrication import three_geometry as tg  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
check, near, rejects, t2b = U.check, U.near, U.rejects, U.t2b

# 1. swept ball and flat cutters agree with independent dense moving-tool samples
ok, worst = True, 0.0
t = np.linspace(0, 1, 50001)
for kind in ('flat', 'ball'):
    for dy in (-.014, 0, .017):
        a, b, r = t2b((-.012, .017, 0)), t2b((.014, .017 + dy, .005)), .003
        for x, z in ((-.012, 0), (.001, .004), (.014, .005), (.006, -.012)):
            y = -z
            dx = x - a[0] - (b[0] - a[0]) * t
            dyy = y - a[1] - (b[1] - a[1]) * t
            d2 = dx * dx + dyy * dyy
            inside = d2 <= r * r
            h = a[2] + (b[2] - a[2]) * t + ((r - np.sqrt(np.maximum(0, r * r - d2))) if kind == 'ball' else 0)
            minimum = float(h[inside].min()) if inside.any() else math.inf
            actual = fab.swept_cutter_height(x, y, a, b, r, kind)
            if minimum == math.inf:
                ok &= actual == math.inf
            else:
                ok &= actual <= minimum + 1e-10 and near(actual, minimum, 4e-7)
                worst = max(worst, abs(actual - minimum))
ok &= near(fab.swept_cutter_height(.001, 0, t2b((0, .014, 0)), t2b((0, .009, 0)), .003, 'ball'), .012 - math.sqrt(.000008),
           1e-12)
check('swept ball and flat envelopes agree with dense moving-tool samples', ok, f'worst {worst:.2e} m')

# 2. ball compensation protects a sloping relief and roughing precedes finishing
slope, r = .42, .003
p = fab.relief_program(lambda x, y: .012 + slope * x, stock_width=.036, stock_depth=.034, width=.024, depth=.020,
                       stock_height=.025, radius=r, sample_step=.0015, stepover=.001)
finish = p['stages'][-1]
ok = finish['name'] == 'finish' and len(p['stages']) > 1
gouge = False
for q in p['points'][finish['start_index']:finish['end_index'] + 1]:
    if q['type'] != 'cut':
        continue
    exact = .012 + slope * q['position'][0] + r * (math.sqrt(1 + slope * slope) - 1)
    gouge |= q['position'][2] < exact
    ok &= near(q['position'][2] - exact, p['surface_tolerance'], 2e-5)
ok &= all(s['end_distance'] > s['start_distance'] for s in p['stages'])
check('ball compensation never gouges a sloping plane; roughing precedes the finish', ok and not gouge)

# 3. spatial bins retain every candidate sweep including stock boundary cells
from eidoblend.fabrication._axes import Rec  # noqa: E402
cuts = [Rec(a=t2b((-.02, .02, -.02)), b=t2b((.02, .01, .02)))]
binning = fab.index_cutter_sweeps(cuts, .05, .05, .003)
tiles, headers, indices = binning['tiles'], binning['headers'], binning['indices']
ok = True
for zi in range(31):
    for xi in range(31):
        x, y = (xi / 30 - .5) * .05, -((zi / 30 - .5) * .05)
        if fab.swept_cutter_height(x, y, cuts[0].a, cuts[0].b, .003, 'ball') == math.inf:
            continue
        bx = min(tiles - 1, math.floor((x / .05 + .5) * tiles))
        by = min(tiles - 1, math.floor((y / .05 + .5) * tiles))
        start, count = int(headers[(by * tiles + bx) * 4]), int(headers[(by * tiles + bx) * 4 + 1])
        ok &= 0 in indices[start:start + count]
check('spatial bins hold every sweep that can reach their cells', ok)

# 4. mesh relief samples the transformed top envelope without changing its material
m = tg.make_object('relief box', tg.box(.010, .004, .010), position=(0, .010, 0))
mat = bpy.data.materials.new('box material')
m.data.materials.append(mat)
bpy.context.view_layer.update()
h = fab.relief_from_mesh(m, width=.024, depth=.024, stock_height=.020, floor=.004, columns=25, rows=25)
check('mesh relief: the top of the placed box and the floor elsewhere',
      near(h['heights'][12 * 25 + 12], .012, 1e-8) and near(h['heights'][0], .004, 1e-8) and m.data.materials[0] == mat,
      f"{h['heights'][12 * 25 + 12]:.9f}, {h['heights'][0]:.9f}")

# 5. assembled relief cutter follows XYZ stages, rewinds deterministically and keeps the shared fixtures
robot = make_robot('cnc_relief')
mach = fab.g430(robot)
check('cnc_relief carries the ball nose', mach.cutter.kind == 'ball')
job = fab.carve(robot, fab.sample_relief, material='wood', duration=18, resolution=64, sample_step=.002, stepover=.0015)
verts = np.array([v.co[:] for v in job.mesh.data.vertices])
states, ok_tip, ok_stage = [], True, True
worst = 0.0
for fraction in (0, .17, .62, .94, 1, .17):
    state = job.seek(fraction * 18)
    states.append([*state.position, state.distance])
    worst = max(worst, (robot.tool_tip() - Vector(state.position)).length)
    ok_stage &= isinstance(state.stage, str)
check('the tool tip follows the planned XYZ at every seek', worst < 2e-7, f'worst {worst:.2e} m')
check('every state names its stage', ok_stage, ', '.join(sorted({job.seek(f * 18).stage for f in (0, .3, .6, .99, 1)})))
check('rewinding replays exactly', all(near(a, b, 1e-8) for a, b in zip(states[1], states[-1])))
check('the program ends with the finish; material was removed',
      job.program['stages'][-1]['name'] == 'finish' and job.removal.removed_volume > 0)
check('seeking never edits the stock mesh', np.array_equal(verts, np.array([v.co[:] for v in job.mesh.data.vertices])))
check('the four toe clamps hold the stock, visible', len(job.workholding) == 4 and all(not r.hide_render for r in job.workholding))
ok_, msg = rejects(lambda: fab.mill(robot, None, flute_length=.050), ['exposed length'])
check('an option cannot lengthen the actual cutter', ok_, msg)
job.dispose()
check('disposing the job leaves the clamps on the table, visible', all(
    robot.roots[n].parent == robot.roots['gantry_base'] and not robot.roots[n].hide_render
    for n in robot.roots if n.startswith('cnc_clamp_')))
ok = U.summary('relief')
sys.exit(0 if ok else 1)
