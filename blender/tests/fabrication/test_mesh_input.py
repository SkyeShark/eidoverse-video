"""mesh_input_test.mjs ported: arbitrary mesh input for slicing and relief, with the same assertions.

Sources are real Blender objects (empties, meshes, a Geometry Nodes instancer), so the object path of
source_geometry (evaluated meshes, parents, reflections, instances, local space) is what is tested.

    bash run_blender.sh blender/tests/fabrication/test_mesh_input.py
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
from eidoblend.fabrication import three_geometry as tg  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
check, near, rejects = U.check, U.near, U.rejects
mk = tg.make_object


def area(r):
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2)


# 1. solid skins close local ledges below taller features while keeping sparse internal fill
group = mk('ledge group')
mk('slab', tg.box(.04, .010, .02), position=(0, .005, 0), parent=group)
mk('tower', tg.box(.012, .010, .012), position=(0, .015, 0), parent=group)
bpy.context.view_layer.update()
spec = fab.slice_geometry(group, size=.04, base=0, layer_height=.001, bead_width=.0005, infill=.25, solid_layers=3)
segs = {}
for i in range(1, len(spec['points'])):
    a, b = spec['points'][i - 1]['position'], spec['points'][i]['position']
    if spec['points'][i]['type'] == 'extrude' and abs(a[2] - b[2]) < 1e-8:
        segs.setdefault(round(b[2], 6), []).append((a, b))


def distance(x, y, z):
    s = np.array([(a[0], a[1], b[0], b[1]) for a, b in segs.get(round(z + .0005, 6), [])])
    if not len(s):
        return math.inf
    dx, dy = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    f = np.clip(((x - s[:, 0]) * dx + (y - s[:, 1]) * dy) / (dx * dx + dy * dy), 0, 1)
    return float(np.hypot(x - s[:, 0] - dx * f, y - s[:, 1] - dy * f).min())


# the WebGPU test asks at layer heights .008 / .009 / .010 (bead centres half a layer above each slice)
ok = True
for z in (.0075, .0085, .0095):
    for x in np.arange(.009, .018, .0011):
        for y in np.arange(-.007, .007, .00037):
            ok &= distance(x, y, z) <= .000251 and distance(-x, y, z) <= .000251
check('solid skins roof the ledges either side of the tower', ok)
check('the slab interior keeps sparse infill', any(distance(x, y, .0045) > .0005 for x in (-.0049, -.0037, -.0023, .0011)
                                                    for y in (-.0031, -.0017, .0013, .0031)))

# 2. a disconnected solid inside a hollow shell survives single-mesh slicing
grp = mk('shell group')
mk('ring', tg.lathe([[.020, 0], [.030, 0], [.030, .010], [.020, .010], [.020, 0]], 48), parent=grp)
mk('core', tg.cylinder(.008, .008, .010, 32), position=(0, .005, 0), parent=grp)
bpy.context.view_layer.update()
g = fab.source_geometry(grp)
g.manufacturing_source = None                          # one STL-like mesh: no per-part ranges
rings = fab.mesh_slicer(g)(.005)
check('the inner solid is not erased by the shell hole', len(rings) == 3, f'{len(rings)} rings')

# 3. FDM honours the selected local orientation and source matrices
m = mk('rotated box', tg.box(.040, .010, .020), rotation=(0, 0, math.pi / 2))
bpy.context.view_layer.update()
world = fab.slice_geometry(m, size=.04, base=0, layer_height=.001, solid_layers=0)
local = fab.slice_geometry(m, space='local', size=.04, base=0, layer_height=.001, solid_layers=0)
check('world placement vs local orientation', world['layers'] == 40 and local['layers'] == 10,
      f"{world['layers']} / {local['layers']} layers")
transformed = fab.slice_geometry(m.data, matrix=tg.three_trs((0, 0, 0), (0, 0, math.pi / 2), (1, 1, 1)), size=.04,
                                 base=0, layer_height=.001, solid_layers=0)
check('an explicit source matrix applies before fitting', transformed['layers'] == 40, f"{transformed['layers']} layers")

# 4. snapshots keep parent, reflection and instance transforms without editing source vertices
root = mk('far root', None, position=(5, .2, -2), rotation=(0, .4, 0))
grp = mk('mirrored group', None, scale=(-1.2, .6, 1.1), rotation=(0, 0, .35), parent=root)
part = mk('part', tg.box(.012, .021, .008), position=(.007, .001, -.003), parent=grp)
bpy.context.view_layer.update()
original = np.array([v.co[:] for v in part.data.vertices])
snap = fab.source_geometry(grp)
mw = np.array(part.matrix_world)
pts = original @ mw[:3, :3].T + mw[:3, 3]
check('the snapshot bounds equal the placed part (parent, reflection, rotation)',
      np.allclose(snap.bounding_box[0], pts.min(axis=0), atol=1e-8) and np.allclose(snap.bounding_box[1], pts.max(axis=0), atol=1e-8))
check('the source vertices are untouched', np.array_equal(original, np.array([v.co[:] for v in part.data.vertices])))
proto = mk('instanced box', tg.box(.012, .021, .008))
proto.hide_render = proto.hide_viewport = True
inst_me = bpy.data.meshes.new('instance points')
inst_me.from_pydata([(-.02, 0, 0), (.03, 0, 0)], [], [])
inst = bpy.data.objects.new('instances', inst_me)
bpy.context.scene.collection.objects.link(inst)
ng = bpy.data.node_groups.new('two instances', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
iop, oi = ng.nodes.new('GeometryNodeInstanceOnPoints'), ng.nodes.new('GeometryNodeObjectInfo')
oi.inputs['Object'].default_value = proto
ng.links.new(gi.outputs[0], iop.inputs['Points'])
ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
ng.links.new(iop.outputs['Instances'], go.inputs[0])
inst.modifiers.new('instances', 'NODES').node_group = ng
bpy.context.view_layer.update()
ig = fab.source_geometry(inst)
check('instances keep their own placements and ranges',
      near(ig.bounding_box[0][0], -.026, 1e-7) and near(ig.bounding_box[1][0], .036, 1e-7)
      and len(ig.manufacturing_source['ranges']) == 2,
      f"x {ig.bounding_box[0][0]:.6f} .. {ig.bounding_box[1][0]:.6f}, {len(ig.manufacturing_source['ranges'])} ranges")
fitted = fab.fit_source_geometry(grp, size=.04, base=.00065)
check('fitting stands the part on the base at the requested size',
      near(fitted.bounding_box[0][2], .00065, 1e-8) and near(max(fitted.size()), .04, 1e-8))

# 5. overlapping supplied solids produce their union, with no internal perimeter or XOR gap
grp = mk('overlap group')
for x in (-.005, .005):
    mk(f'overlap box {x}', tg.box(.02, .008, .02), position=(x, .004, 0), parent=grp)
bpy.context.view_layer.update()
rings = fab.mesh_slicer(fab.source_geometry(grp))(.004)
check('overlapping boxes slice to one outline of their union', len(rings) == 1 and near(area(rings[0]), .03 * .02, 1e-10),
      f'{len(rings)} rings, area {area(rings[0]) if rings else 0:.3e}')
sliced = fab.slice_geometry(grp, size=.03, layer_height=.001, bead_width=.0006, solid_layers=0)
check('one contour per layer', all(sum(c['layer'] == k for c in sliced['contours']) == 1 for k in range(1, sliced['layers'] + 1)))
pts = sliced['points']
check('infill crosses the overlap', any(i and p['type'] == 'extrude' and p['position'][0] > 0 and pts[i - 1]['position'][0] < 0
                                        for i, p in enumerate(pts)))

# 6. arbitrary concave extruded outlines keep holes in perimeters and infill
outline = [(-.018, -.014), (.018, -.014), (.018, .014), (.004, .014), (.004, .006), (-.018, .006)]
hole = tg.circle_hole(-.008, -.004, .004, 0, math.pi * 2, True, curve_segments=24)
geo = tg.extrude(tg.shape(outline, [hole]), depth=.01, curve_segments=24).rotate_x(math.pi / 2)
ob = mk('outline with hole', geo)
bpy.context.view_layer.update()
fit = fab.fit_source_geometry(ob, size=.036, base=0)
check('the hole boundary survives slicing', len(fab.mesh_slicer(fit)(.005)) == 2)
spec = fab.slice_geometry(ob, size=.036, base=0, layer_height=.001, bead_width=.0005, solid_layers=0, infill=.25)
tx, ty, _ = fit.manufacturing_source['fit']['offset']
hx, hy = -.008 + tx, .004 + ty                         # three's hole centre (-.008, z -.004) is Blender y +.004
closest = math.inf
for i in range(1, len(spec['points'])):
    if spec['points'][i]['type'] != 'extrude':
        continue
    a, b = spec['points'][i - 1]['position'], spec['points'][i]['position']
    for k in range(1, 20):
        t = k / 20
        closest = min(closest, math.hypot(a[0] + (b[0] - a[0]) * t - hx, a[1] + (b[1] - a[1]) * t - hy))
check('no deposition crosses the designed hole', closest > .0039, f'closest {closest * 1000:.3f} mm from the bore axis')

# 7. relief mesh input includes transforms above the supplied subtree
parent = mk('relief parent', None, position=(.010, .010, 0))
mesh = mk('relief child', tg.box(.012, .004, .018), parent=parent)
bpy.context.view_layer.update()
res = fab.relief_from_mesh(mesh, width=.06, depth=.06, stock_height=.02, floor=.004, columns=61, rows=61)
check('the parent placement reaches the relief sampling', near(res['heights'][30 * 61 + 40], .012, 1e-7)
      and near(res['heights'][30 * 61 + 20], .004, 1e-8))

# 8. invalid open or non-finite manufacturing geometry fails instead of substituting a sample
ok_, msg = rejects(lambda: fab.slice_geometry(mk('open plane', tg.plane(.02, .02))), ['Open', 'nonmanifold', 'shorter', 'triangles'])
check('an open mesh is refused', ok_, msg)
bad = mk('nan box', tg.box(.02, .02, .02))
bad.data.vertices[0].co.x = float('nan')
ok_, msg = rejects(lambda: fab.source_geometry(bad), ['non-finite'])
check('non-finite coordinates are refused', ok_, msg)
ok = U.summary('mesh_input')
sys.exit(0 if ok else 1)
